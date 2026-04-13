# MODULE: TypeRig / Core / Algo / Stroke Separator — Facade
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Re-export facade: imports every public symbol from the split
# sub-modules so that existing ``from typerig.core.algo.stroke_sep import X``
# statements continue to work unchanged.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

# - Init --------------------------------
__version__ = '0.6.0'

# ── Common utilities ─────────────────────────────────────────────────────────
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
	CutEndpoint,
	CutPair,
	resolve_cut_parameters,
	check_contour_compatibility,
	apply_cuts_to_layer,
	StrokeSepResult,
)

# ── MAT structures ───────────────────────────────────────────────────────────
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
	branch_angles_at_fork,
	extract_stroke_paths,
)

# ── CSF / Fork assignment ────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_csf import (
	SectorAssignment,
	_angle_in_sector,
	_path_crosses_convex_rib,
	assign_concavities_to_forks,
	fork_concavity_map,
)

# ── Links ─────────────────────────────────────────────────────────────────────
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

# ── Junctions ─────────────────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_junctions import (
	JType,
	JunctionResult,
	identify_junctions,
)

# ── Stroke graph ──────────────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_graph import (
	BranchVertex,
	extract_branches,
	StrokeGraph,
	build_stroke_graph,
	cuts_from_junction_results,
	StrokeGraphResult,
)

# ── V1 pipeline ──────────────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_v1 import (
	JunctionType,
	JunctionData,
	classify_junction,
	solve_cut_points,
	coordinate_cuts,
	StrokeSeparator,
)

# ── V2 pipeline ──────────────────────────────────────────────────────────────
from typerig.core.algo.stroke_sep_v2 import (
	StrokeSepV2,
)
