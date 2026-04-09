# MODULE: TypeRig / Core / Algo / Stroke Separator
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# CJK stroke separation algorithm
# Adapted from StrokeStyles (Berio et al., ACM TOG 2022)
# Targeting Gothic/Hei style only

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict

from typerig.core.algo.mat import compute_mat, MATGraph, MATNode
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node
from typerig.core.func.geometry import line_intersect

# - Init -------------------------------
__version__ = '0.1.0'

# - Constants --------------------------
_EPS = 1e-9


# - Junction Types ---------------------
class JunctionType(object):
	T_JUNCTION = 'T'    # One branch continues, one branches off perpendicularly
	L_JUNCTION = 'L'    # Two branches meeting at a corner, no continuation
	Y_JUNCTION = 'Y'    # Three branches roughly equal angles (~120 deg)
	STROKE_END = 'END'  # Degree-1 terminal
	UNKNOWN    = '?'    # Unclassified


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


class StrokeSepResult(object):
	"""Full analysis result for a glyph."""
	def __init__(self, graph, concavities, junctions):
		self.graph = graph
		self.concavities = concavities
		self.junctions = junctions

	@property
	def cuts(self):
		return [cut for j in self.junctions for cut in j.cuts]

	def __repr__(self):
		return '<StrokeSepResult: {} junctions, {} cuts>'.format(
			len(self.junctions), len(self.cuts))


# - Stage 2: Junction Classification --

def compute_ligatures(graph, concavities, rib_distance_threshold=5.0):
	"""For each MAT node, find concavities within its inscribed circle reach.

	A MAT node's inscribed circle "touches a concavity" if:
		distance(node, concavity) < node.radius + rib_distance_threshold

	Args:
		graph: MATGraph from compute_mat
		concavities: list of (contour_idx, node_idx, x, y, angle)
		rib_distance_threshold: tolerance in font units

	Returns:
		dict: {id(mat_node) -> list of concavity tuples}
	"""
	node_to_concavities = defaultdict(list)

	for node in graph.nodes:
		nr = node.radius + rib_distance_threshold
		for conc in concavities:
			c_x, c_y = conc[2], conc[3]
			dx = node.x - c_x
			dy = node.y - c_y
			if dx * dx + dy * dy <= nr * nr:
				node_to_concavities[id(node)].append(conc)

	return node_to_concavities


def _branch_direction(from_node, to_node, steps=3):
	"""Walk steps nodes along a branch, return unit direction vector."""
	prev, cur = from_node, to_node
	for _ in range(steps - 1):
		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt or cur.is_fork or cur.is_terminal:
			break
		prev, cur = cur, nxt[0]

	dx = cur.x - from_node.x
	dy = cur.y - from_node.y
	mag = math.hypot(dx, dy)
	if mag < _EPS:
		return (0.0, 0.0)
	return (dx / mag, dy / mag)


def branch_angles_at_fork(fork_node):
	"""Compute the angle of each branch departing from a fork node.

	Returns: list of (angle_degrees, neighbor_node) sorted CCW
	"""
	angles = []
	for nb in fork_node.neighbors:
		direction = _branch_direction(fork_node, nb, steps=3)
		angle = math.degrees(math.atan2(direction[1], direction[0]))
		angles.append((angle % 360, nb))

	return sorted(angles, key=lambda x: x[0])


def classify_junction(fork_node, node_to_concavities):
	"""Classify a fork node into a junction type.

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

	if n == 3:
		# Check for T: find if any two angles are ~180 deg apart
		for i in range(n):
			for j in range(i + 1, n):
				diff = abs(angles[i] - angles[j])
				diff = min(diff, 360 - diff)
				if abs(diff - 180) < 30:
					return JunctionType.T_JUNCTION

		# Check for Y: all angle gaps roughly equal
		gaps = []
		for i in range(n):
			gap = (angles[(i + 1) % n] - angles[i]) % 360
			gaps.append(gap)
		if all(80 < g < 160 for g in gaps):
			return JunctionType.Y_JUNCTION

		return JunctionType.L_JUNCTION

	# degree > 3: complex junction
	return JunctionType.Y_JUNCTION


# - Stage 3: Cut Point Solving --------

def solve_cut_points(fork_node, junction_type, concavities,
					 node_to_concavities, contours):
	"""Compute cut point pairs for a classified fork.

	For T-junction: 1 cut across the crossing stroke.
	For L-junction: 1 cut across the corner.
	For Y-junction: up to 3 cuts.

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

	if fork_concavities:
		cuts = _solve_cuts_by_concavity_pairing(fork_node, junction_type, fork_concavities, contours)
		if cuts:
			return cuts

	# Fallback: projection method
	return _solve_cuts_by_projection(fork_node, junction_type, contours)


def _solve_cuts_by_concavity_pairing(fork_node, junction_type,
									  fork_concavities, contours):
	"""Pair concavities across the stroke to form cut lines.

	Pairing rule: two concavities are paired if their midpoint is
	near the fork and their distance is ~2 * radius.
	"""
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

			# The midpoint should be near the fork
			mid_x = (ax + bx) * 0.5
			mid_y = (ay + by) * 0.5
			dist_to_fork = math.hypot(mid_x - fork_node.x, mid_y - fork_node.y)

			# The pair distance should be ~2 * radius
			pair_dist = math.hypot(ax - bx, ay - by)
			expected_dist = 2.0 * fork_node.radius
			score = dist_to_fork + abs(pair_dist - expected_dist) * 0.5

			if score < best_score:
				best_score = score
				best_j = j

		if best_j is not None and best_score < fork_node.radius * 1.5:
			cb = fork_concavities[best_j]
			pair_dist = math.hypot(ax - cb[2], ay - cb[3])
			if pair_dist > 5.0:  # skip degenerate zero-length cuts
				cuts.append(((ax, ay), (cb[2], cb[3])))
			used.add(i)
			used.add(best_j)

	return cuts


def _solve_cuts_by_projection(fork_node, junction_type, contours):
	"""Fallback: project perpendicular from fork along each branch
	direction and intersect with the outline."""
	cuts = []
	angles_and_neighbors = branch_angles_at_fork(fork_node)

	if junction_type == JunctionType.T_JUNCTION:
		perp_branch = _find_perpendicular_branch(angles_and_neighbors)
		if perp_branch:
			perp_angle_rad = math.radians(perp_branch[0] + 90)
			cut = _cast_cut_ray(fork_node, perp_angle_rad, contours)
			if cut:
				cuts.append(cut)

	elif junction_type in (JunctionType.L_JUNCTION, JunctionType.Y_JUNCTION):
		# For L/Y: cast a cut perpendicular to each branch
		for angle_deg, _nb in angles_and_neighbors:
			perp_rad = math.radians(angle_deg + 90)
			cut = _cast_cut_ray(fork_node, perp_rad, contours)
			if cut:
				# Avoid duplicate cuts (same pair within tolerance)
				is_dup = False
				for existing in cuts:
					d0 = math.hypot(cut[0][0] - existing[0][0], cut[0][1] - existing[0][1])
					d1 = math.hypot(cut[1][0] - existing[1][0], cut[1][1] - existing[1][1])
					if d0 < 5.0 and d1 < 5.0:
						is_dup = True
						break
				if not is_dup:
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
	ray_len = fork_node.radius * 3
	dx = math.cos(angle_rad) * ray_len
	dy = math.sin(angle_rad) * ray_len

	fwd_start = (fork_node.x, fork_node.y)
	fwd_end = (fork_node.x + dx, fork_node.y + dy)
	bwd_end = (fork_node.x - dx, fork_node.y - dy)

	ray_fwd = Line(Point(*fwd_start), Point(*fwd_end))
	ray_bwd = Line(Point(*fwd_start), Point(*bwd_end))

	pt_fwd = _intersect_ray_with_contours(ray_fwd, fwd_start, contours)
	pt_bwd = _intersect_ray_with_contours(ray_bwd, fwd_start, contours)

	if pt_fwd and pt_bwd:
		return (pt_fwd, pt_bwd)
	return None


def _on_segment(px, py, seg_p0, seg_p1, tol=0.5):
	"""Check if point (px,py) lies within the bounding box of the segment."""
	min_x = min(seg_p0[0], seg_p1[0]) - tol
	max_x = max(seg_p0[0], seg_p1[0]) + tol
	min_y = min(seg_p0[1], seg_p1[1]) - tol
	max_y = max(seg_p0[1], seg_p1[1]) + tol
	return min_x <= px <= max_x and min_y <= py <= max_y


def _on_ray(px, py, origin, ray_end):
	"""Check if point is in the forward direction of the ray from origin to ray_end."""
	dx = ray_end[0] - origin[0]
	dy = ray_end[1] - origin[1]
	dot = (px - origin[0]) * dx + (py - origin[1]) * dy
	return dot > 0


def _intersect_ray_with_contours(ray_line, origin, contours):
	"""Find nearest intersection of ray with any contour segment.

	Returns: (x, y) of nearest intersection, or None
	"""
	best_pt = None
	best_dist = float('inf')
	ray_end = (ray_line.p1.x, ray_line.p1.y)

	for contour in contours:
		for segment in contour.segments:
			if isinstance(segment, Line):
				pt = line_intersect(
					ray_line.p0.tuple, ray_line.p1.tuple,
					segment.p0.tuple, segment.p1.tuple
				)
				if pt is None:
					continue
				# line_intersect returns infinite line intersection;
				# check it lies on the segment and in the ray direction
				if not _on_segment(pt[0], pt[1], segment.p0.tuple, segment.p1.tuple):
					continue
				if not _on_ray(pt[0], pt[1], origin, ray_end):
					continue
				d = math.hypot(pt[0] - origin[0], pt[1] - origin[1])
				if 1.0 < d < best_dist:
					best_dist = d
					best_pt = pt

			elif isinstance(segment, CubicBezier):
				result = segment.intersect_line(ray_line)
				_times, (points_x, points_y) = result
				for ipt in list(points_x) + list(points_y):
					if ipt is not None:
						if not _on_ray(ipt.x, ipt.y, origin, ray_end):
							continue
						d = math.hypot(ipt.x - origin[0], ipt.y - origin[1])
						if 1.0 < d < best_dist:
							best_dist = d
							best_pt = (ipt.x, ipt.y)

	return best_pt


# - Stage 4: Contour Cutting ----------

def find_parameter_on_contour(contour, target_x, target_y):
	"""Find segment and parameter t closest to target point.

	Returns: (on_curve_node, t_parameter, distance)
	"""
	query_pt = Point(target_x, target_y)
	best_node = None
	best_t = 0.0
	best_dist = float('inf')

	for node in contour.data:
		if not node.is_on:
			continue

		segment = node.segment
		if segment is None:
			continue

		if isinstance(segment, Line):
			dx = segment.p1.x - segment.p0.x
			dy = segment.p1.y - segment.p0.y
			len_sq = dx * dx + dy * dy
			if len_sq < 1e-12:
				continue
			t = max(0.0, min(1.0,
				((target_x - segment.p0.x) * dx +
				 (target_y - segment.p0.y) * dy) / len_sq
			))
			pt = segment.solve_point(t)
			d = math.hypot(pt.x - target_x, pt.y - target_y)
		else:
			t, d = segment.project_point(query_pt, steps=30)

		if d < best_dist:
			best_dist = d
			best_t = t
			best_node = node

	return best_node, best_t, best_dist


def _find_nearest_on_node(contour, x, y):
	"""Find nearest on-curve node to (x, y)."""
	best = None
	best_d = float('inf')
	for node in contour.data:
		if node.is_on:
			d = math.hypot(node.x - x, node.y - y)
			if d < best_d:
				best_d = d
				best = node
	return best


def split_contour_at_points(contour, pt_a, pt_b):
	"""Split a closed contour into two closed contours at two cut points.

	Does NOT modify the input contour — works on a clone.

	Args:
		contour: TypeRig Contour (must be closed)
		pt_a: (x, y) first cut point
		pt_b: (x, y) second cut point

	Returns:
		(contour_1, contour_2) or None if cut fails
	"""
	# Work on a clone
	work = Contour([n.clone() for n in contour.data], closed=True)

	SNAP_THRESHOLD = 2.0

	# Insert first cut point
	node_a, t_a, dist_a = find_parameter_on_contour(work, pt_a[0], pt_a[1])
	if node_a is None:
		return None

	# Check distance to nearest existing on-curve node (not segment)
	nearest_a = _find_nearest_on_node(work, pt_a[0], pt_a[1])
	node_dist_a = math.hypot(nearest_a.x - pt_a[0], nearest_a.y - pt_a[1]) if nearest_a else float('inf')

	if node_dist_a < SNAP_THRESHOLD:
		new_node_a = nearest_a
	else:
		result_a = node_a.insert_after(t_a)
		if isinstance(result_a, tuple):
			new_node_a = node_a.next_on
		else:
			new_node_a = result_a

	# Insert second cut point (re-find after first insertion)
	node_b, t_b, dist_b = find_parameter_on_contour(work, pt_b[0], pt_b[1])
	if node_b is None:
		return None

	nearest_b = _find_nearest_on_node(work, pt_b[0], pt_b[1])
	node_dist_b = math.hypot(nearest_b.x - pt_b[0], nearest_b.y - pt_b[1]) if nearest_b else float('inf')

	if node_dist_b < SNAP_THRESHOLD:
		new_node_b = nearest_b
	else:
		result_b = node_b.insert_after(t_b)
		if isinstance(result_b, tuple):
			new_node_b = node_b.next_on
		else:
			new_node_b = result_b

	if new_node_a is None or new_node_b is None:
		return None

	# Get indices
	idx_a = new_node_a.idx
	idx_b = new_node_b.idx

	if idx_a == idx_b:
		return None

	if idx_a > idx_b:
		idx_a, idx_b = idx_b, idx_a

	# Extract two node subsequences
	all_nodes = list(work.data)

	nodes_1 = [n.clone() for n in all_nodes[idx_a:idx_b + 1]]
	nodes_2 = [n.clone() for n in all_nodes[idx_b:] + all_nodes[:idx_a + 1]]

	if len(nodes_1) < 3 or len(nodes_2) < 3:
		return None

	contour_1 = Contour(nodes_1, closed=True)
	contour_2 = Contour(nodes_2, closed=True)

	# Match winding to original
	if contour.is_ccw != contour_1.is_ccw:
		contour_1.reverse()
	if contour.is_ccw != contour_2.is_ccw:
		contour_2.reverse()

	return contour_1, contour_2


# - Main Entry Point -------------------

class StrokeSeparator(object):
	"""CJK Gothic stroke separator.

	Usage:
		sep = StrokeSeparator(beta_min=1.5, sample_step=5.0)
		result = sep.analyze(contours)
		# result.cuts — list of cut pairs
		# result.junctions — list of JunctionData
		# result.graph — MATGraph for visualization
		new_contours = sep.execute(result, contours)
	"""

	def __init__(self, beta_min=1.5, sample_step=5.0, quality='normal'):
		self.beta_min = beta_min
		self.sample_step = sample_step
		self.quality = quality

	def analyze(self, contours):
		"""Run full analysis: MAT, junction classification, cut solving.

		Args:
			contours: list of TypeRig Contour objects

		Returns:
			StrokeSepResult
		"""
		graph, concavities = compute_mat(
			contours,
			sample_step=self.sample_step,
			beta_min=self.beta_min,
			quality=self.quality
		)

		ligatures = compute_ligatures(graph, concavities)

		junctions = []
		for fork in graph.forks():
			jtype = classify_junction(fork, ligatures)
			cuts = solve_cut_points(fork, jtype, concavities, ligatures, contours)
			junctions.append(JunctionData(fork, jtype, cuts))

		return StrokeSepResult(graph, concavities, junctions)

	def execute(self, result, contours):
		"""Apply all cuts. Returns new list of Contour objects.

		Does NOT modify input contours.

		Args:
			result: StrokeSepResult from analyze()
			contours: original contour list

		Returns:
			list of Contour objects
		"""
		# Clone contours
		working = [Contour([n.clone() for n in c.data], closed=c.closed) for c in contours]

		output = []
		for contour in working:
			applicable_cuts = []
			for jdata in result.junctions:
				for cut in jdata.cuts:
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
					result_split = split_contour_at_points(c, cut[0], cut[1])
					if result_split is not None:
						new_remaining.extend(result_split)
					else:
						new_remaining.append(c)
				remaining = new_remaining

			output.extend(remaining)

		return output
