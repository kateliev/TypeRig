# MODULE: TypeRig / Core / Algo / Stroke Separator — V2 Pipeline
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# V2 full StrokeStyles (Berio et al. 2022) pipeline:
# Steps 1-9 producing junction graph, stroke graph, and cut positions.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.algo.mat import compute_mat, compute_exterior_mat

from typerig.core.algo.stroke_sep_common import (
	_fast_clone_contour,
	find_parameter_on_contour,
	split_contour_at_points,
	_find_nearest_on_node,
	_fast_clone_node,
)
from typerig.core.algo.stroke_sep_mat import compute_ligatures_v2
from typerig.core.algo.stroke_sep_csf import assign_concavities_to_forks
from typerig.core.algo.stroke_sep_links import generate_links, filter_incompatible_links
from typerig.core.algo.stroke_sep_junctions import identify_junctions
from typerig.core.algo.stroke_sep_graph import (
	build_stroke_graph,
	cuts_from_junction_results,
	StrokeGraphResult,
)
from typerig.core.algo.stroke_sep_v1 import StrokeSeparator

from typerig.core.objects.contour import Contour


# ── Cross-contour cut helpers ─────────────────────────────────────────────────

def _find_contour_for_point(contours, pt, snap):
	"""Return index of the contour closest to pt, or None if > snap."""
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


def _merge_contours_at_cut(contour_a, contour_b, pt_a, pt_b, snap):
	"""Merge two contours by connecting them at two cut points.

	pt_a should be near contour_a, pt_b near contour_b.  The merge creates
	a single closed contour that goes:
	  ... contour_a nodes up to pt_a -> straight to pt_b ->
	  contour_b nodes from pt_b all the way around back to pt_b ->
	  straight back to pt_a -> remaining contour_a nodes ...

	Returns a single merged Contour or None on failure.
	"""
	work_a = _fast_clone_contour(contour_a)
	work_b = _fast_clone_contour(contour_b)

	# Find and insert cut points on each contour
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
	if nearest_b and math.hypot(nearest_b.x - pt_b[0], nearest_b.y - pt_b[1]) < 2.0:
		cut_b = nearest_b
	else:
		result_b = node_b.insert_after(t_b)
		cut_b = node_b.next_on if isinstance(result_b, tuple) else result_b

	if cut_a is None or cut_b is None:
		return None

	# Build merged node list:
	# contour_a from cut_a onwards (wrapping) + contour_b from cut_b onwards (wrapping)
	nodes_a = list(work_a.data)
	nodes_b = list(work_b.data)

	idx_a = cut_a.idx
	idx_b = cut_b.idx

	# Rotate A so cut_a is first
	rotated_a = nodes_a[idx_a:] + nodes_a[:idx_a]
	# Rotate B so cut_b is first
	rotated_b = nodes_b[idx_b:] + nodes_b[:idx_b]

	# Merge: all of A (starting at cut_a) + bridge node + all of B + bridge back
	merged_nodes = []
	for n in rotated_a:
		merged_nodes.append(_fast_clone_node(n))
	# Bridge to B's cut point (already at same position as pt_b)
	for n in rotated_b:
		merged_nodes.append(_fast_clone_node(n))

	if len(merged_nodes) < 3:
		return None

	merged = Contour(merged_nodes, closed=True)

	# Match winding to the outer contour (contour_a assumed outer)
	if contour_a.is_ccw != merged.is_ccw:
		merged.reverse()

	return merged


class StrokeSepV2(object):
	"""Full StrokeStyles (Berio et al. 2022) pipeline for stroke separation.

	Runs Steps 1-9 of the paper to produce cut positions from the junction graph,
	then splits the outline contours at those positions.  Falls back to the
	simple geometry-based StrokeSeparator when no links/junctions are found.

	Usage:
		sep    = StrokeSepV2(beta_min=1.5, sample_step=5.0)
		result = sep.analyze(contours)        # StrokeGraphResult
		new_contours = sep.execute(result, contours)

	Inspectable intermediate results on StrokeGraphResult:
		.graph, .ext_graph, .csfs, .ligatures, .links
		.protuberances, .half_junctions, .step3_junctions
		.stroke_graph, .cuts, .strokes
	"""

	def __init__(self, beta_min=1.5, sample_step=5.0):
		self.beta_min    = beta_min
		self.sample_step = sample_step

	def analyze(self, contours):
		"""Run the complete pipeline and return a StrokeGraphResult.

		Args:
			contours: list of TypeRig Contour objects (closed)

		Returns:
			StrokeGraphResult
		"""
		from typerig.core.algo.csf import compute_csfs

		# -- Step 1: Interior MAT --
		graph, _concavities = compute_mat(
			contours,
			sample_step=self.sample_step,
			beta_min=self.beta_min,
		)

		# -- Step 2: Exterior MAT M* --
		_ext_graph, exterior_terminals = compute_exterior_mat(
			contours,
			beta_min=self.beta_min,
			sample_step=self.sample_step,
		)

		# -- Steps 3+4: CSFs --
		csfs = compute_csfs(
			contours, graph, exterior_terminals,
			sample_step=self.sample_step,
		)

		# -- Step 5: Ligatures v2 --
		ligatures = compute_ligatures_v2(graph, csfs)

		# -- Step 6: Sector assignment --
		sector_assignments = assign_concavities_to_forks(graph, csfs, ligatures)

		# -- Step 7: Links --
		links = generate_links(sector_assignments, contours, graph, ligatures,
							   sample_step=self.sample_step)
		links = filter_incompatible_links(links)

		# sigma for good-continuation: 2 x max non-ligature fork radius
		lig_fork_ids  = {id(n) for lig in ligatures for n in lig.forks}
		non_lig_radii = [f.radius for f in graph.forks() if id(f) not in lig_fork_ids]
		sigma_phi     = 2.0 * max(non_lig_radii) if non_lig_radii else 50.0

		# -- Step 8: Junction identification --
		proturbs, halfs, step3 = identify_junctions(
			links, ligatures, sector_assignments, graph, contours, sigma_phi)

		# -- Step 9: Stroke graph + cut positions --
		stroke_graph = build_stroke_graph(graph, proturbs, halfs, step3)
		cuts         = cuts_from_junction_results(proturbs, halfs, step3)

		return StrokeGraphResult(
			graph=graph,
			ext_graph=_ext_graph,
			csfs=csfs,
			ligatures=ligatures,
			links=links,
			protuberances=proturbs,
			half_junctions=halfs,
			step3_junctions=step3,
			stroke_graph=stroke_graph,
			cuts=cuts,
			concavities=_concavities,
		)

	def execute(self, result, contours, use_fallback=True):
		"""Apply cuts and return a list of separated Contour objects.

		Args:
			result:       StrokeGraphResult from analyze()
			contours:     original list of TypeRig Contour objects
			use_fallback: if True and the v2 pipeline produces no cuts, fall back
			              to the geometry-based v1 StrokeSeparator.  Set False to
			              diagnose link/cut generation issues.

		Returns:
			list of Contour -- original contours with junction cuts applied
		"""

		if not result.cuts:
			if use_fallback:
				fallback = StrokeSeparator(
					beta_min=self.beta_min, sample_step=self.sample_step)
				# Reuse already-computed interior MAT to avoid duplicate work
				fb_result = fallback.analyze(
					contours, precomputed_graph=(result.graph, result.concavities))
				return fallback.execute(fb_result, contours)
			else:
				# No cuts and no fallback -- return contours unchanged
				return list(contours)

		_SNAP = 15.0   # maximum distance (font units) for a cut to snap to a contour

		working = [_fast_clone_contour(c) for c in contours]

		# -- Pre-pass: merge contours connected by cross-contour cuts --
		cross_cuts = []
		same_cuts  = []
		for cut in result.cuts:
			ci_a = _find_contour_for_point(working, cut[0], _SNAP)
			ci_b = _find_contour_for_point(working, cut[1], _SNAP)
			if ci_a is not None and ci_b is not None and ci_a != ci_b:
				cross_cuts.append((cut, ci_a, ci_b))
			else:
				same_cuts.append(cut)

		# Apply cross-contour merges
		for cut, ci_a, ci_b in cross_cuts:
			# Indices may shift after merges -- re-find
			ci_a = _find_contour_for_point(working, cut[0], _SNAP)
			ci_b = _find_contour_for_point(working, cut[1], _SNAP)
			if ci_a is None or ci_b is None or ci_a == ci_b:
				# Already merged or lost -- treat as same-contour cut
				same_cuts.append(cut)
				continue
			merged = _merge_contours_at_cut(working[ci_a], working[ci_b],
											cut[0], cut[1], _SNAP)
			if merged is not None:
				# Replace the two contours with the merged one
				new_working = []
				for k, c in enumerate(working):
					if k != ci_a and k != ci_b:
						new_working.append(c)
				new_working.append(merged)
				working = new_working
				# Now this cut becomes a same-contour cut on the merged contour
				same_cuts.append(cut)
			else:
				same_cuts.append(cut)

		# -- Main pass: apply same-contour cuts --
		output = []
		for contour in working:
			applicable = []
			for cut in same_cuts:
				_, _, da = find_parameter_on_contour(contour, cut[0][0], cut[0][1])
				_, _, db = find_parameter_on_contour(contour, cut[1][0], cut[1][1])
				if da < _SNAP and db < _SNAP:
					applicable.append(cut)

			if not applicable:
				output.append(contour)
				continue

			remaining = [contour]
			for cut in applicable:
				new_remaining = []
				for c in remaining:
					_, _, da = find_parameter_on_contour(c, cut[0][0], cut[0][1])
					_, _, db = find_parameter_on_contour(c, cut[1][0], cut[1][1])
					if da > _SNAP or db > _SNAP:
						new_remaining.append(c)
						continue
					split = split_contour_at_points(c, cut[0], cut[1])
					if split is not None:
						new_remaining.extend(split)
					else:
						new_remaining.append(c)
				remaining = new_remaining

			output.extend(remaining)

		# Remove degenerate (zero-area) contours from splitting artifacts
		_MIN_AREA = 100.0
		output = [c for c in output
				  if not hasattr(c, 'signed_area') or abs(c.signed_area) > _MIN_AREA]

		return output
