# MODULE: TypeRig / Core / Algo / Stroke Separator — V3 Hybrid Pipeline
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# V3 Hybrid: V1's working analysis + fixed cross-contour execution
# Designed for multi-contour glyphs (P, B, D, R) and CJK

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.algo.mat import compute_mat
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

from typerig.core.algo.stroke_sep_common import (
	_EPS,
	_fast_clone_contour,
	_fast_clone_node,
	_intersect_ray_with_contours,
	find_parameter_on_contour,
	split_contour_at_points,
	_join_fragments,
	_extend_pieces_at_cuts,
	CutEndpoint,
	CutPair,
	resolve_cut_parameters,
	StrokeSepResult,
)

from typerig.core.algo.stroke_sep_v1 import (
	compute_ligatures,
	merge_nearby_forks,
	classify_junction,
	solve_cut_points,
	extract_stroke_paths,
	JunctionType,
	JunctionData,
)


# - Init --------------------------------
__version__ = '0.1.0'


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
# V3 Main Class
# ============================================================

class StrokeSepV3(object):
	"""Hybrid stroke separator - V1 analysis + fixed cross-contour execution.
	
	Uses V1's proven analysis pipeline but adds proper handling for
	multi-contour glyphs (P, B, D, R, CJK with inner counters).
	
	Usage:
		sep = StrokeSepV3(beta_min=1.5, sample_step=20.0, debug=False)
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
		
		# Step 1: Compute MAT
		graph, concavities = compute_mat(
			contours,
			sample_step=self.sample_step,
			beta_min=self.beta_min,
		)
		
		if self.debug:
			print("  Nodes: {} | Forks: {} | Terminals: {}".format(
				len(graph.nodes), len(graph.forks()), len(graph.terminals())))
			print("  Concavities: {}".format(len(concavities)))
			for i, c in enumerate(concavities[:10]):  # Show first 10
				print("    {}: contour={} pos=({},{})".format(
					i, c[0], c[2], c[3]))
			if len(concavities) > 10:
				print("    ... and {} more".format(len(concavities) - 10))
		
		# Step 2: Compute ligatures
		ligatures = compute_ligatures(graph, concavities)
		
		# Step 3: Merge nearby forks
		merged = merge_nearby_forks(graph.forks(), ligatures, merge_radius=30.0)
		
		if self.debug:
			print("  Merged forks: {}".format(len(merged)))
		
		# Step 4: Classify junctions and solve cuts
		junctions = []
		raw_cuts = []
		
		for rep_fork, combined_concavities in merged:
			jtype = classify_junction(rep_fork, ligatures)
			cuts = solve_cut_points(rep_fork, jtype, concavities, ligatures, contours)
			
			if self.debug and cuts:
				print("  Fork ({:.0f},{:.0f}): {} -> {} cuts".format(
					rep_fork.x, rep_fork.y, jtype, len(cuts)))
			
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
		
		# Step 2: Process cross-contour cuts FIRST
		# Each cross-contour cut merges two contours, then we split
		for cut, ci_a, ci_b in cross_cuts:
			if self.debug:
				print("  Merging contour {} + {} at cut points...".format(ci_a, ci_b))
			
			# Re-find indices in case previous merge shifted them
			ci_a = _find_contour_for_point(working, cut[0], _SNAP)
			ci_b = _find_contour_for_point(working, cut[1], _SNAP)
			
			if ci_a is None or ci_b is None or ci_a == ci_b:
				if self.debug:
					print("    -> Failed to find contours, treating as same-contour")
				same_cuts.append(cut)
				continue
			
			merged = _bridge_contours(
				working[ci_a], working[ci_b],
				cut[0], cut[1], _SNAP
			)
			
			if merged is None:
				if self.debug:
					print("    -> Bridge failed, treating as same-contour")
				same_cuts.append(cut)
				continue
			
			if self.debug:
				print("    -> Success: merged into {} nodes".format(len(merged.data)))
			
			# Replace the two contours with the merged one
			new_working = []
			for k, c in enumerate(working):
				if k != ci_a and k != ci_b:
					new_working.append(c)
			new_working.append(merged)
			working = new_working
			
			# The cross-contour cut now becomes a same-contour cut on merged
			# We need to find its new position in the merged contour
			new_idx = len(working) - 1  # merged is at end
			merged = working[new_idx]
			
			# Split the merged contour at the cut points
			split_result = split_contour_at_points(merged, cut[0], cut[1])
			if split_result is not None:
				if self.debug:
					print("    -> Split into {} pieces".format(len(split_result)))
				# Replace merged with split pieces
				working[new_idx:new_idx+1] = split_result
			else:
				if self.debug:
					print("    -> Split failed")
		
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
	sep = StrokeSepV3(beta_min=beta_min, sample_step=sample_step, debug=debug)
	result = sep.analyze(contours)
	return sep.execute(result, contours, overlap=overlap)