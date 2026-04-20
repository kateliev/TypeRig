# MODULE: TypeRig / Core / Algo / Stroke Separator — Solver
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Geometry-based stroke separation solver: junction classification,
# cut solving, cut coordination, StrokeSeparator. Consumed by the
# `StrokeSep` pipeline in stroke_sep.py. Previously named stroke_sep_v1.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import namedtuple

from typerig.core.algo.mat import compute_mat
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line

from typerig.core.algo.stroke_sep_common import (
	_EPS,
	_fast_clone_contour,
	_intersect_ray_with_contours,
	find_parameter_on_contour,
	split_contour_at_points,
	_join_fragments,
	_extend_pieces_at_cuts,
	resolve_cut_parameters,
	StrokeSepResult,
)
from typerig.core.algo.stroke_sep_mat import (
	StrokePath,
	merge_nearby_forks,
	compute_ligatures,
	extract_stroke_paths,
	branch_angles_at_fork,
)


# - Junction Types ---------------------
class JunctionType(object):
	T_JUNCTION = 'T'     # One branch continues, one branches off perpendicularly
	X_JUNCTION = 'X'     # Four-way crossing (two perpendicular pairs)
	L_JUNCTION = 'L'     # Two branches meeting at a corner, no continuation
	Y_JUNCTION = 'Y'     # Three branches roughly equal angles (~120 deg)
	STROKE_END = 'END'   # Degree-1 terminal
	UNKNOWN    = '?'     # Unclassified


# - Result Data Structures -------------
class JunctionData(object):
	"""Classification and cut data for a single fork node."""
	def __init__(self, fork_node, junction_type, cuts):
		self.fork_node = fork_node
		self.junction_type = junction_type
		self.cuts = cuts  # list of ((x1,y1), (x2,y2))

	def __repr__(self):
		return '<Junction: {} at ({:.0f},{:.0f}) cuts={}>'.format(
			self.junction_type, self.fork_node.x, self.fork_node.y, len(self.cuts))


# StrokeSepResult is now imported from stroke_sep_common


# - Junction Classification -----------

def classify_junction(fork_node, node_to_concavities):
	"""Classify a fork node into a junction type.

	X-JUNCTION (degree=4): Two pairs of collinear branches (crossing)
	T-JUNCTION (degree=3): Two branches nearly collinear (~180 deg),
		one nearly perpendicular.
	L-JUNCTION (degree=3): Two branches meeting at angle < 150 deg,
		no collinear continuation.
	Y-JUNCTION (degree=3): All three angles ~120 deg apart.

	Args:
		fork_node: MATNode with degree >= 3
		node_to_concavities: dict from compute_ligatures

	Returns:
		JunctionType string
	"""
	if fork_node.degree == 1:
		return JunctionType.STROKE_END

	if fork_node.degree < 3:
		return JunctionType.UNKNOWN

	angles_and_neighbors = branch_angles_at_fork(fork_node)
	angles = [a for a, _ in angles_and_neighbors]
	n = len(angles)

	if n == 4:
		collinear_pairs = _find_collinear_pairs(angles_and_neighbors)
		if len(collinear_pairs) == 2:
			return JunctionType.X_JUNCTION
		return JunctionType.Y_JUNCTION

	if n == 3:
		collinear_pair = _find_collinear_pair(angles)
		if collinear_pair is not None:
			return JunctionType.T_JUNCTION

		gaps = []
		for i in range(n):
			gap = (angles[(i + 1) % n] - angles[i]) % 360
			gaps.append(gap)
		if all(80 < g < 160 for g in gaps):
			return JunctionType.Y_JUNCTION

		return JunctionType.L_JUNCTION

	return JunctionType.Y_JUNCTION


def _find_collinear_pairs(angles_and_neighbors):
	"""Find pairs of collinear branches in a 4-way junction.

	Returns list of (idx1, idx2) pairs where branches are collinear.
	"""
	pairs = []
	n = len(angles_and_neighbors)
	angles = [a for a, _ in angles_and_neighbors]

	for i in range(n):
		for j in range(i + 1, n):
			diff = abs(angles[i] - angles[j])
			diff = min(diff, 360 - diff)
			if abs(diff - 180) < 30:
				pairs.append((i, j))

	return pairs


def _find_collinear_pair(angles):
	"""Find if any two angles are ~180 deg apart."""
	n = len(angles)
	for i in range(n):
		for j in range(i + 1, n):
			diff = abs(angles[i] - angles[j])
			diff = min(diff, 360 - diff)
			if abs(diff - 180) < 30:
				return (i, j)
	return None


# - Cut Point Solving ------------------

def solve_cut_points(fork_node, junction_type, concavities,
					 node_to_concavities, contours):
	"""Compute cut point pairs for a classified fork.

	Concavity-first approach (per Adobe StrokeStyles paper):
	- Concavities ARE the cut endpoints. They sit at the inner corners
	  of junctions where strokes meet.
	- 2 concavities -> 1 cut connecting them
	- 3 concavities -> pair best 2 for 1 cut (Y-junction)
	- 4 concavities -> pair into 2 parallel cuts (X-junction)
	- 1 concavity -> project from concavity across stroke to opposite edge
	- 0 concavities -> no cut (taper/stroke end)

	Args:
		fork_node: MATNode
		junction_type: JunctionType string
		concavities: full list from compute_mat
		node_to_concavities: dict from compute_ligatures
		contours: glyph contours

	Returns:
		list of ((x1,y1), (x2,y2)) cut pairs
	"""
	fork_concavities = node_to_concavities.get(id(fork_node), [])

	if not fork_concavities:
		return []  # No concavities = no cut (taper/stroke end)

	return _solve_cuts_from_concavities(fork_node, fork_concavities, contours)


def _solve_cuts_from_concavities(fork_node, fork_concavities, contours):
	"""Solve cuts purely from concavity positions.

	The number of concavities determines the junction type and cut strategy.
	"""
	n = len(fork_concavities)

	if n >= 4:
		# X-junction: pair into 2 parallel cuts
		return _pair_concavities_parallel(fork_node, fork_concavities, contours)

	elif n == 3:
		# Y-junction: find best pair for 1 cut, optionally 2
		return _pair_concavities_y_junction(fork_node, fork_concavities, contours)

	elif n == 2:
		# T/L-junction: 1 cut connecting the 2 concavities
		ca, cb = fork_concavities[0], fork_concavities[1]
		dist = math.hypot(ca[2] - cb[2], ca[3] - cb[3])
		if dist > 5.0:
			return [((ca[2], ca[3]), (cb[2], cb[3]))]
		return []

	elif n == 1:
		# Single concavity: project from it across the stroke
		return _project_from_concavity(fork_node, fork_concavities[0], contours)

	return []


def _outline_walk(ca, cb, contours):
	"""Outline-walk distance between two concavities, in on-curve-node steps.

	Concavities from find_concavities() are tuples (c_idx, node_idx, x, y, ext).
	node_idx indexes the on-curve nodes of contour c_idx. The walk is the
	shortest arc around the closed contour between the two nodes.

	Returns float('inf') when the two concavities live on different contours
	or when contours is None (caller wants Euclidean only).
	"""
	if contours is None or ca[0] != cb[0]:
		return float('inf')
	contour = contours[ca[0]]
	n_on = sum(1 for n in contour.nodes if n.is_on)
	if n_on == 0:
		return float('inf')
	diff = abs(ca[1] - cb[1])
	return min(diff, n_on - diff)


def _pair_concavities_y_junction(fork_node, concavities, contours=None):
	"""For Y-junctions with 3 concavities, produce 1 or 2 cuts.

	Pair selection uses outline-walk distance between concavities on the same
	contour (a purely topological measure: concavities that are outline-adjacent
	across the junction interior are same-side). Euclidean distance is the
	tiebreaker for ties or for cross-contour pairs.
	"""
	if len(concavities) < 3:
		return []

	def _score(i, j):
		ci, cj = concavities[i], concavities[j]
		walk = _outline_walk(ci, cj, contours)
		dist = math.hypot(ci[2] - cj[2], ci[3] - cj[3])
		return (walk, dist)

	# Primary cut: the two concavities with the shortest outline walk
	# (falling back to Euclidean via the score tuple).
	best_pair = None
	best_score = (float('inf'), float('inf'))
	for i in range(len(concavities)):
		for j in range(i + 1, len(concavities)):
			s = _score(i, j)
			if s < best_score:
				best_score = s
				best_pair = (i, j)

	cuts = []
	if best_pair and best_score[1] > 5.0:
		ci = concavities[best_pair[0]]
		cj = concavities[best_pair[1]]
		cuts.append(((ci[2], ci[3]), (cj[2], cj[3])))

	# Optional second cut: remaining concavity + whichever of the primary
	# pair gives the shorter outline walk (same-side neighbour).
	remaining = [k for k in range(3) if k not in best_pair]
	if remaining:
		cr = concavities[remaining[0]]
		sa = _score(remaining[0], best_pair[0])
		sb = _score(remaining[0], best_pair[1])
		partner = concavities[best_pair[0]] if sa <= sb else concavities[best_pair[1]]
		pdist = math.hypot(cr[2] - partner[2], cr[3] - partner[3])
		if pdist > 5.0:
			cuts.append(((cr[2], cr[3]), (partner[2], partner[3])))

	return cuts


def _project_from_concavity(fork_node, concavity, contours):
	"""Project from a single concavity point across the stroke.

	The concavity is on the outline. We project a ray from it through the
	fork center to find the opposite outline edge, then SNAP the landing
	point to the nearest on-curve node when one is close enough — so a
	corner cut (shape_quad) lands exactly on an existing outline node and
	no new node is inserted. When no node is within tolerance, the raw
	ray-outline intersection is used (smooth join case, e.g. P/B/D bowls).
	"""
	cx, cy = concavity[2], concavity[3]

	# Direction: from concavity through fork center
	dx = fork_node.x - cx
	dy = fork_node.y - cy
	mag = math.hypot(dx, dy)
	if mag < _EPS:
		return []

	# Normalize and extend past the fork
	dx /= mag
	dy /= mag
	ray_len = fork_node.radius * 4.0

	# Cast ray from concavity in the direction of the fork
	ray_end = (cx + dx * ray_len, cy + dy * ray_len)

	ray_line = Line(Point(cx, cy), Point(*ray_end))
	origin = (cx, cy)

	pt = _intersect_ray_with_contours(ray_line, origin, contours,
									  max_dist=fork_node.radius * 4.0)
	if pt:
		# Snap to nearest on-curve node if within tolerance — prefers existing
		# outline vertices (convex corners on frames, corner miters) over
		# freshly-inserted points.
		snap_tol = max(fork_node.radius * 0.5, 5.0)
		best_node = None
		best_d = snap_tol
		for contour in contours:
			for node in contour.data:
				if not node.is_on:
					continue
				d = math.hypot(node.x - pt[0], node.y - pt[1])
				if d < best_d:
					best_d = d
					best_node = node
		if best_node is not None:
			pt = (best_node.x, best_node.y)

		dist = math.hypot(pt[0] - cx, pt[1] - cy)
		if dist > 5.0:
			return [((cx, cy), pt)]

	return []


def _solve_cuts_by_concavity_pairing(fork_node, junction_type,
									  fork_concavities, contours):
	"""Pair concavities across the stroke to form cut lines.

	For X-junctions (4 concavities): produces 2 PARALLEL cuts by
	grouping concavities on the same side and pairing across.

	For T/Y/L-junctions (2 concavities): produces 1 cut connecting them.
	"""
	if len(fork_concavities) < 2:
		return []

	# For X-junctions with 4 concavities: pair same-side concavities
	# to produce parallel cuts (not diagonal)
	if junction_type == JunctionType.X_JUNCTION and len(fork_concavities) == 4:
		return _pair_concavities_parallel(fork_node, fork_concavities, contours)

	# For other junction types: pair closest concavities across the stroke
	cuts = []
	used = set()

	for i, ca in enumerate(fork_concavities):
		if i in used:
			continue
		ax, ay = ca[2], ca[3]

		best_j = None
		best_score = float('inf')

		for j, cb in enumerate(fork_concavities):
			if j == i or j in used:
				continue
			bx, by = cb[2], cb[3]

			# Prefer pairs whose distance is ~2 * radius (opposite sides of stroke)
			pair_dist = math.hypot(ax - bx, ay - by)
			expected_dist = 2.0 * fork_node.radius
			score = abs(pair_dist - expected_dist)

			if score < best_score:
				best_score = score
				best_j = j

		if best_j is not None:
			cb = fork_concavities[best_j]
			pair_dist = math.hypot(ax - cb[2], ay - cb[3])
			if pair_dist > 5.0:
				cuts.append(((ax, ay), (cb[2], cb[3])))
			used.add(i)
			used.add(best_j)

	return cuts


def _pair_concavities_parallel(fork_node, concavities, contours=None):
	"""Pair 4 concavities into 2 parallel cuts for X-junctions.

	Concavities are sorted by angle from the fork centre to form a cyclic
	sequence. The two ways of pairing adjacent entries are then scored by
	total outline walk distance (shorter walk = same-side neighbours along
	the contour). Euclidean distance breaks ties and handles the 3-concavity
	overflow / degenerate cases.
	"""
	if len(concavities) < 4:
		return []

	# Sort concavities by angle around the fork.
	angled = []
	for c in concavities:
		dx = c[2] - fork_node.x
		dy = c[3] - fork_node.y
		angle = math.degrees(math.atan2(dy, dx)) % 360
		angled.append((angle, c))
	angled.sort(key=lambda x: x[0])

	cs = [a[1] for a in angled]

	def _pair_cost(i, j):
		ci, cj = cs[i], cs[j]
		walk = _outline_walk(ci, cj, contours)
		dist = math.hypot(ci[2] - cj[2], ci[3] - cj[3])
		return walk, dist

	# Option A: pair (0,1) + (2,3)
	walk_a0, dist_a0 = _pair_cost(0, 1)
	walk_a1, dist_a1 = _pair_cost(2, 3)
	score_a = (walk_a0 + walk_a1, dist_a0 + dist_a1)

	# Option B: pair (1,2) + (3,0)
	walk_b0, dist_b0 = _pair_cost(1, 2)
	walk_b1, dist_b1 = _pair_cost(3, 0)
	score_b = (walk_b0 + walk_b1, dist_b0 + dist_b1)

	if score_a <= score_b:
		pair_a, pair_b = (cs[0], cs[1]), (cs[2], cs[3])
		min_dist = min(dist_a0, dist_a1)
	else:
		pair_a, pair_b = (cs[1], cs[2]), (cs[3], cs[0])
		min_dist = min(dist_b0, dist_b1)

	cuts = []
	if min_dist > 5.0:
		cuts.append(((pair_a[0][2], pair_a[0][3]), (pair_a[1][2], pair_a[1][3])))
		cuts.append(((pair_b[0][2], pair_b[0][3]), (pair_b[1][2], pair_b[1][3])))

	return cuts


def _find_best_collinear_pair(angles):
	"""Find the pair of angles closest to being collinear (180 deg apart).

	Unlike _find_collinear_pair which uses a strict threshold,
	this always returns the best pair regardless of deviation.

	Returns: (idx_a, idx_b) or None if fewer than 2 angles.
	"""
	if len(angles) < 2:
		return None
	best_pair = None
	best_dev = float('inf')
	for i in range(len(angles)):
		for j in range(i + 1, len(angles)):
			diff = abs(angles[i] - angles[j])
			diff = min(diff, 360 - diff)
			dev = abs(diff - 180)
			if dev < best_dev:
				best_dev = dev
				best_pair = (i, j)
	return best_pair


def _snap_to_axis(angle, threshold=50):
	"""Snap angle to nearest axis (0, 90, 180, 270) if within threshold degrees."""
	axes = [0, 90, 180, 270, 360]
	a = angle % 360
	for ax in axes:
		if abs(a - ax) <= threshold:
			return ax % 360
	return angle


def _try_snapped_then_original(fork_node, perp_angle, contours, threshold=50):
	"""Try axis-snapped cut angle first; fall back to original if snapped misses.

	Only falls back to diagonal if the fork is NOT at a stroke-end corner
	(i.e., has no short terminal branches). Corner forks should only cut
	axis-aligned; a diagonal fallback at a corner produces wrong sliver cuts.
	"""
	snapped = _snap_to_axis(perp_angle, threshold)
	if snapped != perp_angle % 360:
		# Try snapped first (prefer axis-aligned cuts for Gothic)
		cut = _cast_cut_ray(fork_node, math.radians(snapped), contours)
		if cut:
			return cut

		# Check if fork has short terminal branches (corner fork)
		has_short_terminal = False
		for nb in fork_node.neighbors:
			prev, cur = fork_node, nb
			steps, path_len = 0, 0.0
			while cur is not None and steps < 500:
				steps += 1
				path_len += math.hypot(cur.x - prev.x, cur.y - prev.y)
				if cur.is_terminal:
					if path_len < fork_node.radius * 3.0:
						has_short_terminal = True
					break
				if cur.is_fork:
					break
				nxt = [n for n in cur.neighbors if n is not prev]
				if not nxt:
					break
				prev, cur = cur, nxt[0]
			if has_short_terminal:
				break

		# Don't fall back to diagonal at corner forks
		if has_short_terminal:
			return None

	# Fall back to original angle (non-corner fork)
	return _cast_cut_ray(fork_node, math.radians(perp_angle), contours)


def _solve_cuts_by_projection(fork_node, junction_type, contours):
	"""Compute cuts by projecting perpendicular rays from the fork.

	Gothic-specific strategy:
	- T-junction: 1 cut perpendicular to the perpendicular branch
	- X-junction: 1 cut perpendicular to one collinear pair
	- Y/L-junction: 1 cut perpendicular to the diverging branch
	  (the branch NOT part of the best collinear pair)
	"""
	cuts = []
	angles_and_neighbors = branch_angles_at_fork(fork_node)
	angles = [a for a, _ in angles_and_neighbors]

	if junction_type == JunctionType.T_JUNCTION:
		perp_branch = _find_perpendicular_branch(angles_and_neighbors)
		if perp_branch:
			perp_angle = (perp_branch[0] + 90) % 360
			cut = _try_snapped_then_original(fork_node, perp_angle, contours)
			if cut:
				cuts.append(cut)

	elif junction_type == JunctionType.X_JUNCTION:
		# For X-junction: cut perpendicular to ONE collinear pair only
		collinear_pairs = _find_collinear_pairs(angles_and_neighbors)
		if collinear_pairs:
			i, j = collinear_pairs[0]
			branch_angle = angles_and_neighbors[i][0]
			perp_angle_rad = math.radians(branch_angle + 90)
			cut = _cast_cut_ray(fork_node, perp_angle_rad, contours)
			if cut:
				cuts.append(cut)

	elif junction_type in (JunctionType.L_JUNCTION, JunctionType.Y_JUNCTION):
		# Find the best collinear pair (the continuing stroke direction).
		# Cut perpendicular to the REMAINING branch (the diverging stroke).
		best_pair = _find_best_collinear_pair(angles)

		if best_pair is not None and len(angles) >= 3:
			remaining = [k for k in range(len(angles)) if k not in best_pair]
			if remaining:
				remaining_angle = angles[remaining[0]]
				perp_angle = (remaining_angle + 90) % 360
				cut = _try_snapped_then_original(fork_node, perp_angle, contours)
				if cut:
					cuts.append(cut)
		elif len(angles) >= 2:
			# Only 2 branches (L-junction): cut perpendicular to the bisector
			bisector = (angles[0] + angles[1]) / 2.0
			perp_angle = (bisector + 90) % 360
			cut = _try_snapped_then_original(fork_node, perp_angle, contours)
			if cut:
				cuts.append(cut)

	return cuts


def _find_perpendicular_branch(angles_and_neighbors):
	"""Among 3 branches at a T-junction, find the perpendicular one."""
	angles = [a for a, _ in angles_and_neighbors]
	n = len(angles)

	for i in range(n):
		for j in range(i + 1, n):
			diff = abs(angles[i] - angles[j])
			diff = min(diff, 360 - diff)
			if abs(diff - 180) < 30:
				remaining = [k for k in range(n) if k != i and k != j]
				if remaining:
					return angles_and_neighbors[remaining[0]]
	return None


def _cast_cut_ray(fork_node, angle_rad, contours):
	"""Cast a ray from fork in both directions, intersect with outline.

	Returns: ((x1,y1), (x2,y2)) or None
	"""
	ray_len = fork_node.radius * 4
	max_dist = fork_node.radius * 4.0
	dx = math.cos(angle_rad) * ray_len
	dy = math.sin(angle_rad) * ray_len

	fwd_start = (fork_node.x, fork_node.y)
	fwd_end = (fork_node.x + dx, fork_node.y + dy)
	bwd_end = (fork_node.x - dx, fork_node.y - dy)

	ray_fwd = Line(Point(*fwd_start), Point(*fwd_end))
	ray_bwd = Line(Point(*fwd_start), Point(*bwd_end))

	pt_fwd = _intersect_ray_with_contours(ray_fwd, fwd_start, contours, max_dist)
	pt_bwd = _intersect_ray_with_contours(ray_bwd, fwd_start, contours, max_dist)

	if pt_fwd and pt_bwd:
		return (pt_fwd, pt_bwd)
	return None


# - Cut Coordination ------------------

def _is_real_junction(fork, stroke_paths=None, concavity_count=0):
	"""Check if a fork is a real junction vs taper artifact.

	Concavity-first approach: a fork with concavities IS a real junction.
	Concavities appear at the inner corners of stroke meetings.
	Tapers (stroke ends) have no concavities.
	"""
	if concavity_count > 0:
		return True

	return False


def coordinate_cuts(junctions, stroke_paths, min_stroke_width=20.0):
	"""Coordinate cuts for universal stroke separation.

	Key principle: Only cut at junction forks where distinct stroke
	bodies meet. Skip taper forks (stroke-end artifacts) that have
	2 short branches to terminals and 1 branch into the stroke body.

	Args:
		junctions: list of JunctionData with cuts
		stroke_paths: list of StrokePath from extract_stroke_paths
		min_stroke_width: minimum cut length to consider valid

	Returns:
		list of coordinated cut pairs
	"""
	all_cuts = []

	for jdata in junctions:
		fork = jdata.fork_node

		# No need for _is_real_junction check: solve_cut_points already
		# returns [] for 0-concavity forks (tapers/stroke ends)
		for cut in jdata.cuts:
			if not _is_valid_cut(cut, min_stroke_width):
				continue
			# Deduplicate: skip cuts that are essentially identical to existing ones
			is_dup = False
			cut_mid = ((cut[0][0] + cut[1][0]) / 2, (cut[0][1] + cut[1][1]) / 2)
			for existing in all_cuts:
				# Check endpoint proximity (either orientation)
				d1 = math.hypot(cut[0][0] - existing[0][0], cut[0][1] - existing[0][1])
				d2 = math.hypot(cut[1][0] - existing[1][0], cut[1][1] - existing[1][1])
				d3 = math.hypot(cut[0][0] - existing[1][0], cut[0][1] - existing[1][1])
				d4 = math.hypot(cut[1][0] - existing[0][0], cut[1][1] - existing[0][1])
				if (d1 + d2) < 10.0 or (d3 + d4) < 10.0:
					is_dup = True
					break
				# Check midpoint proximity (parallel nearby cuts)
				ex_mid = ((existing[0][0] + existing[1][0]) / 2,
						  (existing[0][1] + existing[1][1]) / 2)
				mid_dist = math.hypot(cut_mid[0] - ex_mid[0], cut_mid[1] - ex_mid[1])
				if mid_dist < 15.0:
					is_dup = True
					break
			if not is_dup:
				all_cuts.append(cut)

	return all_cuts


def _cut_length(cut):
	"""Get the length of a cut."""
	p1, p2 = cut
	return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _is_valid_cut(cut, min_stroke_width):
	"""Check if a cut is valid (non-degenerate, minimum length)."""
	p1, p2 = cut
	dx = p2[0] - p1[0]
	dy = p2[1] - p1[1]
	length = math.hypot(dx, dy)

	if length < 1.0:
		return False

	if length < min_stroke_width * 0.3:
		return False

	if abs(p1[0] - p2[0]) < 1.0 and abs(p1[1] - p2[1]) < 1.0:
		return False

	return True


def _filter_trivial_cuts(cuts, min_stroke_width):
	"""Filter out trivial cuts (too short, degenerate)."""
	valid = []
	for cut in cuts:
		if _is_valid_cut(cut, min_stroke_width):
			valid.append(cut)
	return valid


def _compute_cut_angle(cut):
	"""Compute the angle of a cut line."""
	p1, p2 = cut
	dx = p2[0] - p1[0]
	dy = p2[1] - p1[1]
	if abs(dx) < _EPS and abs(dy) < _EPS:
		return 0.0
	return math.degrees(math.atan2(dy, dx)) % 360


def _select_best_cuts(cuts_forks, stroke_paths):
	"""Select the best cuts to keep from a group of parallel cuts.

	Strategy: For cuts along the same direction, keep the ones that:
	1. Are associated with real stroke crossings (not just corner effects)
	2. Have the longest extent
	3. Don't overlap
	"""
	if not cuts_forks:
		return []

	if len(cuts_forks) == 1:
		return [cuts_forks[0][0]]

	cut_angle = _compute_cut_angle(cuts_forks[0][0])
	perp_angle = math.radians(cut_angle + 90)

	all_points = []
	for cut, fork in cuts_forks:
		all_points.append((cut[0], fork))
		all_points.append((cut[1], fork))

	if len(all_points) < 2:
		return []

	min_pt = min(all_points, key=lambda p:
		p[0][0] * math.cos(perp_angle) + p[0][1] * math.sin(perp_angle))
	max_pt = max(all_points, key=lambda p:
		p[0][0] * math.cos(perp_angle) + p[0][1] * math.sin(perp_angle))

	pt1_x = min_pt[0][0]
	pt1_y = min_pt[0][1]
	pt2_x = max_pt[0][0]
	pt2_y = max_pt[0][1]

	spanning_cut = ((pt1_x, pt1_y), (pt2_x, pt2_y))

	if _is_valid_cut(spanning_cut, 20.0):
		return [spanning_cut]

	best_cut = max(cuts_forks, key=lambda cf: _cut_length(cf[0]))
	if _is_valid_cut(best_cut[0], 20.0):
		return [best_cut[0]]

	return []


def _collect_all_cuts(junctions):
	"""Fallback: collect all cuts without coordination."""
	return [cut for j in junctions for cut in j.cuts]


# - Main Entry Point -------------------

class StrokeSeparator(object):
	"""Geometry-based stroke separator (V1 pipeline).

	Usage:
		sep = StrokeSeparator(beta_min=1.5, sample_step=5.0)
		result = sep.analyze(contours)
		# result.cuts -- list of cut pairs
		# result.coordinated_cuts -- merged cuts per stroke direction
		# result.junctions -- list of JunctionData
		# result.stroke_paths -- list of StrokePath
		# result.graph -- MATGraph for visualization
		new_contours = sep.execute(result, contours)
	"""

	def __init__(self, beta_min=1.5, sample_step=5.0, quality='normal'):
		self.beta_min = beta_min
		self.sample_step = sample_step
		self.quality = quality

	def analyze(self, contours, precomputed_graph=None):
		"""Run full analysis: MAT, junction classification, cut solving.

		Args:
			contours: list of TypeRig Contour objects
			precomputed_graph: optional (MATGraph, concavities) tuple to skip MAT

		Returns:
			StrokeSepResult
		"""
		if precomputed_graph is not None:
			graph, concavities = precomputed_graph
		else:
			graph, concavities = compute_mat(
				contours,
				sample_step=self.sample_step,
				beta_min=self.beta_min,
				quality=self.quality
			)

		ligatures = compute_ligatures(graph, concavities)
		stroke_paths = extract_stroke_paths(graph)

		# Merge nearby forks into logical junctions (handles oblique crossings)
		merged = merge_nearby_forks(graph.forks(), ligatures, merge_radius=30.0)

		# Update ligatures map so merged concavities are accessible via representative fork
		for rep_fork, combined_concavities in merged:
			ligatures[id(rep_fork)] = combined_concavities

		junctions = []
		for rep_fork, combined_concavities in merged:
			jtype = classify_junction(rep_fork, ligatures)
			cuts = solve_cut_points(rep_fork, jtype, concavities, ligatures, contours)
			junctions.append(JunctionData(rep_fork, jtype, cuts))

		# Collect raw cuts and resolve parametric locations
		raw_cuts = [cut for j in junctions for cut in j.cuts]
		cut_pairs = resolve_cut_parameters(raw_cuts, contours)

		# Estimate stroke width
		stroke_width = 50.0
		if graph.nodes:
			radii = sorted([n.radius for n in graph.nodes])
			stroke_width = 2.0 * radii[len(radii) // 2]

		return StrokeSepResult(
			pipeline='v1',
			graph=graph,
			concavities=concavities,
			cuts=cut_pairs,
			junctions=junctions,
			stroke_paths=stroke_paths,
			stroke_width=stroke_width,
		)

	def execute(self, result, contours, coordinated=True, overlap=0):
		"""Apply all cuts. Returns new list of Contour objects.

		Does NOT modify input contours.

		Args:
			result: StrokeSepResult from analyze()
			contours: original contour list
			coordinated: if True, use coordinated_cuts; else use raw cuts
			overlap: float -- extension past cut boundaries (font units, default 0)

		Returns:
			list of Contour objects
		"""
		working = [_fast_clone_contour(c) for c in contours]

		cuts_to_apply = result.coordinated_cuts if coordinated else result.cuts

		output = []
		for contour in working:
			applicable_cuts = []
			for cut in cuts_to_apply:
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
					# Re-check distance on each sub-contour before splitting
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

			# If 2 parallel cuts from an X-junction produced 3 pieces,
			# join the 2 smallest fragments into an overlapping stroke.
			if len(applicable_cuts) == 2 and len(remaining) == 3:
				has_x_junction = any(
					j.junction_type == JunctionType.X_JUNCTION
					for j in result.junctions
				)
				if has_x_junction:
					remaining = _join_fragments(remaining, applicable_cuts)

			# Extend pieces past cut boundaries for stroke overlap
			if overlap > 0:
				_extend_pieces_at_cuts(remaining, applicable_cuts, overlap)

			output.extend(remaining)

		return output
