# MODULE: TypeRig / Core / Algo / Stroke Separator
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Stroke separator — public entry point.
#
# Defines the `StrokeSep` pipeline class (MAT analysis + planar
# slicer execution) and re-exports every public symbol from the split
# sub-modules so callers can write `from typerig.core.algo.stroke_sep
# import X` without caring about the internal layout.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.algo.mat import compute_mat, compute_exterior_mat
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

# ── Common utilities (re-exported) ───────────────────────────────────────────
from typerig.core.algo.stroke_sep_common import (
	_EPS,
	_fast_clone_node,
	_fast_clone_contour,
	_seg_intersects_seg,
	_on_segment,
	_on_ray,
	_intersect_ray_with_contours,
	_normalize_angle,
	find_parameter_on_contour,
	_find_nearest_on_node,
	split_contour_at_points,
	_join_fragments,
	_extend_pieces_at_cuts,
	CutEndpoint,
	CutPair,
	resolve_cut_parameters,
	check_contour_compatibility,
	apply_cuts_to_layer,
	StrokeSepResult,
)

# ── MAT structures (re-exported) ─────────────────────────────────────────────
from typerig.core.algo.stroke_sep_mat import (
	StrokePath,
	merge_nearby_forks,
	compute_ligatures,
	Ligature,
	compute_ligatures_v2,
	ligature_node_set,
	protruding_direction,
	branch_salience,
	_TAU_SIGMA,
	estimate_direction_from_path,
	peek_ahead_direction,
	pick_best_branch,
	branch_angles_at_fork,
	extract_stroke_paths,
	expand_fork_ligatures,
)

# ── CSF / Fork assignment (dormant sub-system, re-exported) ──────────────────
from typerig.core.algo.stroke_sep_csf import (
	SectorAssignment,
	_angle_in_sector,
	_path_crosses_convex_rib,
	assign_concavities_to_forks,
	fork_concavity_map,
)

# ── Links (dormant sub-system, re-exported) ──────────────────────────────────
from typerig.core.algo.stroke_sep_links import (
	Link,
	_precompute_glyph_edges,
	_link_inside_glyph,
	good_continuation,
	_flow_projection,
	_sector_idx_for_csf,
	_protruding_branch_for_normal_link,
	generate_links,
	filter_incompatible_links,
)

# ── Junctions (dormant sub-system, re-exported) ──────────────────────────────
from typerig.core.algo.stroke_sep_junctions import (
	JType,
	JunctionResult,
	identify_junctions,
)

# ── Stroke graph (dormant sub-system, re-exported) ───────────────────────────
from typerig.core.algo.stroke_sep_graph import (
	BranchVertex,
	extract_branches,
	StrokeGraph,
	build_stroke_graph,
	cuts_from_junction_results,
	StrokeGraphResult,
)

# ── Planar slicer ────────────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_slicer import slice_contours

# ── Solver (geometry-based classification + cut solving) ────────────────────
from typerig.core.algo.stroke_sep_solver import (
	JunctionType,
	JunctionData,
	classify_junction,
	solve_cut_points,
	coordinate_cuts,
	StrokeSeparator,
)


# - Init --------------------------------
__version__ = '0.7.0'


# ============================================================
# Exterior-concavity augmentation
# ============================================================

def _snap_point_to_node(contours, x, y):
	"""Snap an arbitrary point (x, y) to the nearest on-curve node across
	all contours.

	Returns (c_idx, node_idx, nx, ny, dist) where node_idx is the index
	within the on-curve node list of contours[c_idx] — matching the node-idx
	convention used by find_concavities(). Returns (None, None, x, y, inf)
	if the contour list is empty.
	"""
	best = (None, None, x, y, float('inf'))
	for ci, contour in enumerate(contours):
		on_nodes = [n for n in contour.nodes if n.is_on]
		for ni, node in enumerate(on_nodes):
			d = math.hypot(node.x - x, node.y - y)
			if d < best[4]:
				best = (ci, ni, node.x, node.y, d)
	return best


def _augment_exterior_concavities(contours, interior_concavities,
								  sample_step=5.0, beta_min=1.5,
								  snap_tol_mult=1.5, dedup_tol=2.0):
	"""Return pseudo-concavity tuples derived from the exterior MAT.

	The exterior MAT detects two kinds of outline features that the interior
	`find_concavities` misses:
	  1. Inner-corner vertices of a hole contour (frame topology — shape_quad).
	     Contact is at or near an on-curve vertex; we snap it.
	  2. Smooth bowl-to-stem joins on P, B, D, R — contact is mid-edge on a
	     curve, no vertex exists. We still snap to the nearest node; if the
	     snap distance exceeds tolerance we fall back to the raw contact
	     coordinate and leave node_idx = -1. Downstream code treats tuples
	     with node_idx >= 0 as outline-walk candidates and the rest as
	     free-point concavities.

	Pseudo-concavities overlapping existing interior concavities (within
	dedup_tol font units) are discarded to avoid double-counting sharp
	corners that both MATs happen to see.

	Args:
		contours: list of TypeRig Contour
		interior_concavities: list from find_concavities() — used for dedup
		sample_step, beta_min: passed to compute_exterior_mat
		snap_tol_mult: multiplier on the exterior terminal's radius to decide
			whether the contact belongs to an existing on-curve node
		dedup_tol: Euclidean tolerance for deduplication against interior

	Returns:
		list of (c_idx, node_idx, x, y, ext_angle_sentinel) tuples. node_idx
		is -1 when the contact is not close enough to any on-curve node.
	"""
	_, ext_terms = compute_exterior_mat(
		contours, sample_step=sample_step, beta_min=beta_min)
	if not ext_terms:
		return []

	# Build a set of interior-concavity positions for dedup
	interior_keys = [(c[2], c[3]) for c in interior_concavities]

	out = []
	seen = set()
	for tx, ty, tr, cx, cy in ext_terms:
		ci, ni, nx, ny, d = _snap_point_to_node(contours, cx, cy)
		if ci is None:
			continue
		# Decide: snap to node, or keep free contact point
		snap_tol = max(tr * snap_tol_mult, 3.0)
		if d <= snap_tol:
			px, py, p_ni = nx, ny, ni
		else:
			px, py, p_ni = cx, cy, -1

		# Dedup against interior concavities (sharp corners both MATs see)
		skip = False
		for ix, iy in interior_keys:
			if math.hypot(px - ix, py - iy) < dedup_tol:
				skip = True
				break
		if skip:
			continue

		# Dedup against previously-added exterior pseudo-concavities
		key = (round(px, 1), round(py, 1))
		if key in seen:
			continue
		seen.add(key)

		# Sentinel exterior-angle value — not used for anything downstream,
		# but chosen outside the find_concavities threshold so it's unambiguous.
		out.append((ci, p_ni, px, py, 180.0))

	return out


# ============================================================
# Cross-Contour Helpers (Fixed from V2)
# ============================================================

def _find_contour_for_point(contours, pt, snap):
	"""Return index of contour closest to pt, or None if > snap."""
	best_idx = None
	best_dist = float('inf')
	for i, c in enumerate(contours):
		_, _, d = find_parameter_on_contour(c, pt[0], pt[1])
		if d < best_dist:
			best_dist = d
			best_idx = i
	if best_dist < snap:
		return best_idx
	return None


def _bridge_contours(contour_a, contour_b, pt_a, pt_b, snap=15.0):
	"""Merge two contours by connecting them at two cut points.
	
	This is a FIXED version of V2's broken _merge_contours_at_cut:
	- Properly detects outer (CCW) vs inner (CW) contours
	- Reverses inner contour nodes when winding differs
	- Adds duplicate bridge nodes (zero-width passage)
	- Fixes index shifting after merge
	
	Args:
		contour_a, contour_b: Contour objects to merge
		pt_a, pt_b: (x, y) points where contours should connect
		snap: max distance for snapping to existing nodes
	
	Returns:
		Merged Contour or None on failure
	"""
	work_a = _fast_clone_contour(contour_a)
	work_b = _fast_clone_contour(contour_b)
	
	# Step 1: Find and insert cut points on each contour
	node_a, t_a, da = find_parameter_on_contour(work_a, pt_a[0], pt_a[1])
	node_b, t_b, db = find_parameter_on_contour(work_b, pt_b[0], pt_b[1])
	if node_a is None or node_b is None or da > snap or db > snap:
		return None
	
	# Snap or insert on contour A
	nearest_a = _find_nearest_on_node(work_a, pt_a[0], pt_a[1])
	if nearest_a and math.hypot(nearest_a.x - pt_a[0], nearest_a.y - pt_a[1]) < 2.0:
		cut_a = nearest_a
	else:
		result_a = node_a.insert_after(t_a)
		cut_a = node_a.next_on if isinstance(result_a, tuple) else result_a
	
	# Snap or insert on contour B
	nearest_b = _find_nearest_on_node(work_b, pt_b[0], pt_b[1])
	if nearest_b and math.hypot(nearest_b.x - pt_b[0], nearest_b.y - pt_b[0]) < 2.0:
		cut_b = nearest_b
	else:
		result_b = node_b.insert_after(t_b)
		cut_b = node_b.next_on if isinstance(result_b, tuple) else result_b
	
	if cut_a is None or cut_b is None:
		return None
	
	# Step 2: Handle winding direction
	# If contours have opposite winding (outer=CCW, inner=CW), reverse inner
	outer_a = contour_a.is_ccw
	outer_b = contour_b.is_ccw
	
	if outer_a != outer_b:
		# Reverse the inner contour's nodes
		if not outer_b:
			work_b = _reverse_contour_nodes(work_b)
		else:
			work_a = _reverse_contour_nodes(work_a)
	
	# Re-find cut points after potential reversal
	node_a, t_a, _ = find_parameter_on_contour(work_a, pt_a[0], pt_a[1])
	node_b, t_b, _ = find_parameter_on_contour(work_b, pt_b[0], pt_b[1])
	
	# Re-snap after reversal
	nearest_a = _find_nearest_on_node(work_a, pt_a[0], pt_a[1])
	if nearest_a and math.hypot(nearest_a.x - pt_a[0], nearest_a.y - pt_a[1]) < 2.0:
		cut_a = nearest_a
	else:
		result_a = node_a.insert_after(t_a)
		cut_a = node_a.next_on if isinstance(result_a, tuple) else result_a
	
	nearest_b = _find_nearest_on_node(work_b, pt_b[0], pt_b[1])
	if nearest_b and math.hypot(nearest_b.x - pt_b[0], nearest_b.y - pt_b[1]) < 2.0:
		cut_b = nearest_b
	else:
		result_b = node_b.insert_after(t_b)
		cut_b = node_b.next_on if isinstance(result_b, tuple) else result_b
	
	# Step 3: Build merged node list with BRIDGE NODE DUPLICATES
	# This creates a zero-width passage between contours
	nodes_a = list(work_a.data)
	nodes_b = list(work_b.data)
	
	idx_a = cut_a.idx
	idx_b = cut_b.idx
	
	# Rotate A so cut_a is first
	rotated_a = nodes_a[idx_a:] + nodes_a[:idx_a]
	# Rotate B so cut_b is first
	rotated_b = nodes_b[idx_b:] + nodes_b[:idx_b]
	
	# Create bridge node at pt_a
	bridge_a = Node(x=pt_a[0], y=pt_a[1], node_type='on')
	# Create bridge node at pt_b
	bridge_b = Node(x=pt_b[0], y=pt_b[1], node_type='on')
	
	# Build merged: A from cut_a -> bridge_a -> bridge_b -> B from cut_b -> bridge_b -> bridge_a -> A
	merged_nodes = []
	for n in rotated_a:
		merged_nodes.append(_fast_clone_node(n))
	
	# First bridge: A to B
	merged_nodes.append(_fast_clone_node(bridge_b))
	
	for n in rotated_b:
		merged_nodes.append(_fast_clone_node(n))
	
	# Second bridge: B back to A (completes the zero-width passage)
	merged_nodes.append(_fast_clone_node(bridge_a))
	
	if len(merged_nodes) < 3:
		return None
	
	merged = Contour(merged_nodes, closed=True)
	
	# Fix winding to match outer contour
	# (After bridge insertion, merged winding may be wrong; fix by ensuring outer winding)
	if contour_a.is_ccw != merged.is_ccw:
		merged.reverse()
	
	return merged


def _reverse_contour_nodes(contour):
	"""Reverse the node order in a contour (for inner contour winding fix)."""
	cloned = _fast_clone_contour(contour)
	cloned.data.reverse()
	return cloned


def _find_nearest_on_node(contour, x, y):
	"""Find the on-curve node closest to (x, y) within threshold."""
	best = None
	best_dist = 2.0  # Snap threshold
	for node in contour.data:
		if node.is_on:
			d = math.hypot(node.x - x, node.y - y)
			if d < best_dist:
				best_dist = d
				best = node
	return best


# ============================================================
# Multi-cut frame slicing
# ============================================================

def _nearest_on_node_idx(contour, pt, snap=5.0):
	"""Return (on-curve index, Node) of nearest on-curve node within snap.
	Returns (None, None) if no node is close enough.
	"""
	best_i = None
	best_node = None
	best_d = snap
	for i, node in enumerate([n for n in contour.data if n.is_on]):
		d = math.hypot(node.x - pt[0], node.y - pt[1])
		if d < best_d:
			best_d = d
			best_i = i
			best_node = node
	return best_i, best_node


def _slice_frame(contour_A, contour_B, cuts, snap=5.0):
	"""Slice two cross-linked contours into N closed pieces using N cuts.

	Each cut in `cuts` is ((ax, ay), (bx, by)) with (ax, ay) snapping to an
	on-curve node of contour_A and (bx, by) snapping to one of contour_B.

	This is the correct operation for frame-like topologies (hollow
	rectangles, ring-in-box) and any shape where multiple cross-contour
	cuts link the same pair of contours. Each consecutive pair of cuts
	(sorted by position on A) plus the corresponding arcs on A and B
	bounds one output piece.

	The walk preserves off-curve handle nodes — a cubic segment A -> H1 ->
	H2 -> B stays intact (or is traversed in reverse as B -> H2 -> H1 -> A
	when the arc runs against the contour direction).

	Returns a list of N new Contour objects, or None if the preconditions
	fail (any cut endpoint not snappable, fewer than 2 cuts, or a node
	appears in more than one cut).
	"""
	if len(cuts) < 2:
		return None

	# Build the full-node arrays and on-curve->all-nodes index maps.
	# We need on-curve indices for cut endpoints (so the cut lands on a
	# corner/vertex, not a handle) but all-nodes indices for walking so
	# the output preserves bezier handle geometry.
	all_A = list(contour_A.data)
	all_B = list(contour_B.data)
	nA_all = len(all_A)
	nB_all = len(all_B)
	on_to_all_A = [i for i, n in enumerate(all_A) if n.is_on]
	on_to_all_B = [i for i, n in enumerate(all_B) if n.is_on]
	nA = len(on_to_all_A)
	nB = len(on_to_all_B)
	if nA < len(cuts) or nB < len(cuts):
		return None

	cut_pairs = []
	used_A = set()
	used_B = set()
	for cut in cuts:
		ia, _ = _nearest_on_node_idx(contour_A, cut[0], snap)
		ib, _ = _nearest_on_node_idx(contour_B, cut[1], snap)
		if ia is None or ib is None:
			return None
		if ia in used_A or ib in used_B:
			# Two cuts land on the same node — not a clean frame.
			return None
		used_A.add(ia)
		used_B.add(ib)
		cut_pairs.append((ia, ib))

	# Sort cuts by position on A.
	cut_pairs.sort(key=lambda p: p[0])
	N = len(cut_pairs)

	# Walking direction on B for the "return" arc (b_end -> b_start):
	# If A and B have opposite windings (typical frame: outer CCW + inner
	# CW), walking B forward already reverses the angular direction, so the
	# return arc walks B forward. If they share a winding, the return arc
	# must walk B backward against its winding.
	b_walk_forward = (contour_A.is_ccw != contour_B.is_ccw)

	def _walk_all(all_nodes, on_to_all, start_on_idx, end_on_idx, n_all, forward):
		"""Walk all nodes (on + off-curve) in index-space between two
		on-curve endpoints, around the closed cycle. Inclusive of both ends.

		start_on_idx / end_on_idx are indices into the on-curve-only view
		(matching `cut_pairs`). We convert to the full data-array index and
		step through every node in between, preserving handle nodes.

		A reversed walk (forward=False) traverses the node sequence in
		reverse, which is exactly the correct geometric reverse for cubic
		segments: A -> H1 -> H2 -> B becomes B -> H2 -> H1 -> A with the
		two handles swapping roles automatically.
		"""
		i_start = on_to_all[start_on_idx]
		i_end = on_to_all[end_on_idx]
		out = [all_nodes[i_start]]
		idx = i_start
		step = 1 if forward else -1
		# Safety bound — can never take more than n_all steps on a cycle
		for _ in range(n_all):
			if idx == i_end:
				break
			idx = (idx + step) % n_all
			out.append(all_nodes[idx])
		return out

	pieces = []
	for i in range(N):
		a_start, b_start = cut_pairs[i]
		a_end, b_end = cut_pairs[(i + 1) % N]

		arc_A = _walk_all(all_A, on_to_all_A, a_start, a_end, nA_all,
						  forward=True)
		# B's arc runs from b_end back to b_start (the "return" arm of the
		# quad). Direction is opposite of A's forward walk: if B winds the
		# same way as A the return arm walks forward; if B winds opposite
		# (CW inner for CCW outer), it also walks forward because "opposite
		# winding + reversed endpoints" = forward.
		arc_B_rev = _walk_all(all_B, on_to_all_B, b_end, b_start, nB_all,
							  forward=b_walk_forward)

		piece_nodes = [_fast_clone_node(n) for n in arc_A]
		piece_nodes.extend(_fast_clone_node(n) for n in arc_B_rev)

		# Require at least 3 on-curve nodes to form a valid closed region.
		on_count = sum(1 for n in piece_nodes if n.is_on)
		if on_count < 3:
			return None

		piece = Contour(piece_nodes, closed=True)
		# Normalize winding to CCW so downstream tools see consistent output
		if not piece.is_ccw:
			piece.reverse()
		pieces.append(piece)

	return pieces


# ============================================================
# Main Class
# ============================================================

class StrokeSep(object):
	"""Stroke separator pipeline: MAT analysis + planar slicer execution.

	Handles multi-contour glyphs (P, B, D, R, CJK with inner counters)
	by dispatching cross-contour cuts through the planar face walker in
	``stroke_sep_slicer`` rather than the legacy per-pair merge path.

	Usage:
		sep = StrokeSep(beta_min=1.5, sample_step=20.0, debug=False)
		result = sep.analyze(contours)        # Returns StrokeSepResult
		new_contours = sep.execute(result, contours)

	Args:
		beta_min: MAT pruning threshold (default 1.5)
		sample_step: outline sampling density (default 20.0)
		debug: if True, print detailed debug info
	"""
	
	def __init__(self, beta_min=1.5, sample_step=20.0, debug=False):
		self.beta_min = beta_min
		self.sample_step = sample_step
		self.debug = debug
	
	def analyze(self, contours):
		"""Run full analysis: MAT, junction classification, cut solving.
		
		Uses V1's proven pipeline with debug output.
		
		Args:
			contours: list of TypeRig Contour objects
			
		Returns:
			StrokeSepResult with cuts including contour_idx info
		"""
		if self.debug:
			print("=== V3 Analyze ===")
			print("  Contours: {}".format(len(contours)))
		
		# Step 1: Compute MAT (interior)
		graph, concavities = compute_mat(
			contours,
			sample_step=self.sample_step,
			beta_min=self.beta_min,
		)

		# Step 1b: Augment with exterior-MAT "hidden" concavities.
		# For a closed frame (e.g. rectangular ring) or a smooth bowl-to-stem
		# join (P, B, D, R), the interior outline has no sharp concave vertex,
		# so find_concavities() returns nothing near the junction. The exterior
		# MAT detects these as terminals whose inscribed disk grazes the outline.
		# Each such terminal contributes a pseudo-concavity snapped to the
		# nearest on-curve node of the contour it contacts.
		ext_concavities = _augment_exterior_concavities(
			contours, concavities,
			sample_step=self.sample_step,
			beta_min=self.beta_min)
		concavities.extend(ext_concavities)

		if self.debug:
			print("  Nodes: {} | Forks: {} | Terminals: {}".format(
				len(graph.nodes), len(graph.forks()), len(graph.terminals())))
			print("  Concavities: {} ({} interior + {} exterior)".format(
				len(concavities), len(concavities) - len(ext_concavities),
				len(ext_concavities)))
			for i, c in enumerate(concavities[:10]):  # Show first 10
				print("    {}: contour={} pos=({},{})".format(
					i, c[0], c[2], c[3]))
			if len(concavities) > 10:
				print("    ... and {} more".format(len(concavities) - 10))

		# Step 2: Compute ligatures
		ligatures = compute_ligatures(graph, concavities)

		# Step 3: Merge nearby forks
		merged = merge_nearby_forks(graph.forks(), ligatures, merge_radius=30.0)

		# Update ligatures: each rep_fork now owns the combined concavity list
		# from all forks merged into it. Without this, solve_cut_points looks up
		# id(rep_fork) and sees only the rep's pre-merge concavities, causing
		# a 4-concavity X-junction to be misdispatched as a 3-concavity Y.
		for rep_fork, combined_concavities in merged:
			ligatures[id(rep_fork)] = combined_concavities

		if self.debug:
			print("  Merged forks: {}".format(len(merged)))

		# Step 4: Classify junctions and solve cuts
		junctions = []
		raw_cuts = []
		
		for rep_fork, combined_concavities in merged:
			jtype = classify_junction(rep_fork, ligatures)
			cuts = solve_cut_points(rep_fork, jtype, concavities, ligatures, contours)
			
			if self.debug:
				print("  Fork ({:.0f},{:.0f}): {} -> {} cuts (lig_concavities={})".format(
					rep_fork.x, rep_fork.y, jtype, len(cuts),
					len(ligatures.get(id(rep_fork), []))))
			
			junctions.append(JunctionData(rep_fork, jtype, cuts))
			raw_cuts.extend(cuts)
		
		# Step 5: Resolve cut parameters (includes contour_idx tracking)
		cut_pairs = resolve_cut_parameters(raw_cuts, contours)
		
		if self.debug:
			print("  Raw cuts resolved: {}".format(len(cut_pairs)))
			for i, cp in enumerate(cut_pairs[:5]):
				# Use .a and .b attributes, not [0] and [1] which return tuples
				c_a = cp.a.contour_idx
				c_b = cp.b.contour_idx
				cross = "CROSS" if c_a != c_b else "SAME"
				print("    cut {}: c{} -> c{} ({})".format(i, c_a, c_b, cross))
			if len(cut_pairs) > 5:
				print("    ... and {} more".format(len(cut_pairs) - 5))
		
		# Estimate stroke width
		stroke_width = 50.0
		if graph.nodes:
			radii = sorted([n.radius for n in graph.nodes])
			stroke_width = 2.0 * radii[len(radii) // 2]
		
		return StrokeSepResult(
			pipeline='v3',
			graph=graph,
			concavities=concavities,
			cuts=cut_pairs,
			junctions=junctions,
			stroke_paths=extract_stroke_paths(graph),
			stroke_width=stroke_width,
		)
	
	def execute(self, result, contours, coordinated=True, overlap=0):
		"""Apply all cuts with proper cross-contour handling.
		
		Does NOT modify input contours.
		
		Args:
			result: StrokeSepResult from analyze()
			contours: original contour list
			coordinated: if True, use coordinated_cuts; else use raw cuts
			overlap: float -- extension past cut boundaries (font units)
			
		Returns:
			list of Contour objects
		"""
		if self.debug:
			print("\n=== V3 Execute ===")
		
		working = [_fast_clone_contour(c) for c in contours]
		
		cuts_to_apply = result.coordinated_cuts if coordinated else result.cuts
		
		# Step 1: Classify cuts into same-contour and cross-contour
		cross_cuts = []  # (cut, ci_a, ci_b)
		same_cuts = []
		
		_SNAP = 15.0
		
		for cut in cuts_to_apply:
			ci_a = _find_contour_for_point(working, cut[0], _SNAP)
			ci_b = _find_contour_for_point(working, cut[1], _SNAP)
			
			if ci_a is not None and ci_b is not None and ci_a != ci_b:
				cross_cuts.append((cut, ci_a, ci_b))
				if self.debug:
					print("  CROSS-CONTOUR cut: contour {} <-> {}".format(ci_a, ci_b))
			else:
				same_cuts.append(cut)
		
		if self.debug:
			print("  Total: {} cross-contour, {} same-contour".format(
				len(cross_cuts), len(same_cuts)))
		
		# Step 2a: General planar-face slicer.
		#
		# Dispatches ALL cross-contour cuts at once to a unified N-contour
		# planar face walker (stroke_sep_slicer.slice_contours). The walker
		# treats every involved contour exactly once — critical for glyphs
		# where three or more contours share cross-cuts (B: outer + 2 bowl
		# counters; uni5C4A: outer + many inner counters; CJK frames).
		#
		# The prior approach grouped cross-cuts by contour-pair and called
		# a pair-specific `_slice_frame` per group. When a single outer
		# contour participated in multiple pair groups, each call operated
		# on the *original* outer (state between iterations wasn't updated)
		# — producing duplicate, overlapping geometry.
		#
		# Falls back to the per-cut single-bridge path only if the planar
		# walker reports a precondition failure (unsnappable endpoints,
		# 1-endpoint contour, twin-resolve anomaly).
		cross_only_cuts = [c for c, _, _ in cross_cuts]
		remaining_cross = []
		consumed_contours = set()
		sliced_pieces = []

		if cross_only_cuts:
			sliced_pieces, involved = slice_contours(
				working, cross_only_cuts, snap=_SNAP, debug=self.debug)

			if sliced_pieces is None:
				# Planar walker failed — route every cross-cut to the
				# bridge/split fallback below.
				if self.debug:
					print("  Planar slicer failed, falling back to bridge-merge")
				remaining_cross = list(cross_cuts)
				sliced_pieces = []
				consumed_contours = set()
			else:
				consumed_contours = involved
				if self.debug:
					print("  Planar slicer: {} involved contours -> {} pieces".format(
						len(involved), len(sliced_pieces)))

		# Remove contours consumed by the planar slicer and add new pieces.
		if consumed_contours:
			working = [c for k, c in enumerate(working)
					   if k not in consumed_contours]
			working.extend(sliced_pieces)

		# Step 2b: Process remaining cross-contour cuts via single-bridge merge.
		# A single cross-contour cut (e.g. P-bowl) works fine with merge+split;
		# any remaining multi-cut pairs that the frame-slice path rejected
		# fall through to this code too.
		for cut, _ci_a, _ci_b in remaining_cross:
			# Re-find indices: previous merges may have reindexed `working`.
			ci_a = _find_contour_for_point(working, cut[0], _SNAP)
			ci_b = _find_contour_for_point(working, cut[1], _SNAP)

			if ci_a is None or ci_b is None:
				# Endpoint no longer on any contour — give up on this cut.
				if self.debug:
					print("  Cross cut lost endpoint; dropping")
				continue

			if ci_a == ci_b:
				# A previous bridge already unified these two contours;
				# the cut is now same-contour and will be handled below.
				same_cuts.append(cut)
				continue

			if self.debug:
				print("  Bridging contour {} + {} ...".format(ci_a, ci_b))

			merged = _bridge_contours(
				working[ci_a], working[ci_b],
				cut[0], cut[1], _SNAP
			)

			if merged is None:
				if self.debug:
					print("    -> Bridge failed, leaving as cross-cut fallback")
				same_cuts.append(cut)
				continue

			if self.debug:
				print("    -> merged into {} nodes".format(len(merged.data)))

			# Replace the two original contours with the single merged one.
			new_working = [c for k, c in enumerate(working)
						   if k != ci_a and k != ci_b]
			new_working.append(merged)
			working = new_working

			# The bridge already inserted the cut endpoints as duplicate nodes
			# on the merged contour; the subsequent same-contour split pass
			# will cut there.
			same_cuts.append(cut)
		
		# Step 3: Process same-contour cuts (V1 logic)
		output = []
		for contour in working:
			applicable_cuts = []
			for cut in same_cuts:
				_, _, dist_a = find_parameter_on_contour(contour, cut[0][0], cut[0][1])
				_, _, dist_b = find_parameter_on_contour(contour, cut[1][0], cut[1][1])
				if dist_a < 10.0 and dist_b < 10.0:
					applicable_cuts.append(cut)
			
			if not applicable_cuts:
				output.append(contour)
				continue
			
			remaining = [contour]
			for cut in applicable_cuts:
				new_remaining = []
				for c in remaining:
					_, _, da = find_parameter_on_contour(c, cut[0][0], cut[0][1])
					_, _, db = find_parameter_on_contour(c, cut[1][0], cut[1][1])
					if da > 10.0 or db > 10.0:
						new_remaining.append(c)
						continue
					result_split = split_contour_at_points(c, cut[0], cut[1])
					if result_split is not None:
						new_remaining.extend(result_split)
					else:
						new_remaining.append(c)
				remaining = new_remaining
			
			# Step 4: X-junction fragment joining (DISABLED)
			# The _join_fragments feature was designed for the "+" shape but causes
			# false merging on other glyphs (M, A, etc.). Disabled per user request.
			# Original code kept for reference:
			# if len(applicable_cuts) == 2 and len(remaining) == 3:
			#     has_x_junction = any(...)
			#     if has_x_junction:
			#         remaining = _join_fragments(remaining, applicable_cuts)
			pass
			
			# Step 5: Overlap extension (from V1)
			if overlap > 0:
				_extend_pieces_at_cuts(remaining, applicable_cuts, overlap)
			
			output.extend(remaining)
		
		if self.debug:
			print("  Result: {} strokes".format(len(output)))
		
		return output


# ============================================================
# Convenience function for quick use
# ============================================================

def separate_strokes(contours, beta_min=1.5, sample_step=20.0, debug=False, overlap=0):
	"""Convenience function to separate strokes in a glyph.
	
	Args:
		contours: list of TypeRig Contour objects
		beta_min: MAT pruning threshold
		sample_step: outline sampling density
		debug: print debug info
		overlap: stroke overlap extension
		
	Returns:
		list of separated Contour objects
	"""
	sep = StrokeSep(beta_min=beta_min, sample_step=sample_step, debug=debug)
	result = sep.analyze(contours)
	return sep.execute(result, contours, overlap=overlap)