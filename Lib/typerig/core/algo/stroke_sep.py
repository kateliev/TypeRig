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
from collections import defaultdict, namedtuple

from typerig.core.algo.mat import compute_mat, MATGraph, MATNode
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node
from typerig.core.func.geometry import line_intersect

# - Init -------------------------------
__version__ = '0.3.0'

# - Constants --------------------------
_EPS = 1e-9


# - Junction Types ---------------------
class JunctionType(object):
	T_JUNCTION = 'T'    # One branch continues, one branches off perpendicularly
	X_JUNCTION = 'X'     # Four-way crossing (two perpendicular pairs)
	L_JUNCTION = 'L'    # Two branches meeting at a corner, no continuation
	Y_JUNCTION = 'Y'    # Three branches roughly equal angles (~120 deg)
	STROKE_END = 'END'  # Degree-1 terminal
	UNKNOWN    = '?'    # Unclassified


# - Stroke Path Structure ---------------
StrokePath = namedtuple('StrokePath', ['nodes', 'terminals', 'forks', 'direction_angle'])


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
	def __init__(self, graph, concavities, junctions, stroke_paths=None, stroke_width=None):
		self.graph = graph
		self.concavities = concavities
		self.junctions = junctions
		self.stroke_paths = stroke_paths or []
		self.stroke_width = stroke_width or self._estimate_stroke_width()
		self._junction_is_real = self._compute_real_junctions()

	@property
	def cuts(self):
		return [cut for j in self.junctions for cut in j.cuts]

	@property
	def coordinated_cuts(self):
		return coordinate_cuts(self.junctions, self.stroke_paths, self.stroke_width)

	def _estimate_stroke_width(self):
		"""Estimate stroke width from all node radii (not just terminals).
		
		Uses median of all radii for robustness against outliers.
		"""
		if not self.graph.nodes:
			return 50.0
		
		radii = sorted([n.radius for n in self.graph.nodes])
		median_radius = radii[len(radii) // 2]
		return 2.0 * median_radius

	def _compute_real_junctions(self):
		"""Compute which forks are real junctions vs corner effects.
		
		A real junction: a stroke path passes through the fork
		A corner effect: strokes stop and turn at the fork
		"""
		is_real = {}
		
		for jdata in self.junctions:
			fork = jdata.fork_node
			is_real[id(fork)] = _is_real_junction(fork, self.stroke_paths)
		
		return is_real

	def is_real_junction(self, fork):
		"""Check if a fork is a real junction (not just a corner effect)."""
		return self._junction_is_real.get(id(fork), False)

	def __repr__(self):
		return '<StrokeSepResult: {} junctions ({} real), {} cuts, {} strokes>'.format(
			len(self.junctions), sum(self._junction_is_real.values()), 
			len(self.cuts), len(self.stroke_paths))


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

	For X-junctions (4 concavities): produces 2 PARALLEL cuts by
	grouping concavities on the same side and pairing across.

	For T/Y/L-junctions (2 concavities): produces 1 cut connecting them.
	"""
	if len(fork_concavities) < 2:
		return []

	# For X-junctions with 4 concavities: pair same-side concavities
	# to produce parallel cuts (not diagonal)
	if junction_type == JunctionType.X_JUNCTION and len(fork_concavities) == 4:
		return _pair_concavities_parallel(fork_node, fork_concavities)

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


def _pair_concavities_parallel(fork_node, concavities):
	"""Pair 4 concavities into 2 parallel cuts for X-junctions.

	Groups concavities by their angle from the fork center,
	then pairs adjacent concavities (same side) rather than
	opposite concavities (which would create diagonal cuts).
	"""
	# Compute angle of each concavity from fork center
	angled = []
	for c in concavities:
		dx = c[2] - fork_node.x
		dy = c[3] - fork_node.y
		angle = math.degrees(math.atan2(dy, dx)) % 360
		angled.append((angle, c))

	angled.sort(key=lambda x: x[0])

	# 4 concavities at roughly 4 quadrant positions.
	# Adjacent concavities (by angle) are on the same "side" of one stroke.
	# Pair: (0,1) and (2,3) — or (1,2) and (3,0) — pick the grouping
	# where pairs have smaller internal distance (same-side pairs).
	cuts_a = []
	cuts_b = []

	# Option A: pair (0,1) + (2,3)
	d_01 = math.hypot(angled[0][1][2] - angled[1][1][2],
					  angled[0][1][3] - angled[1][1][3])
	d_23 = math.hypot(angled[2][1][2] - angled[3][1][2],
					  angled[2][1][3] - angled[3][1][3])

	# Option B: pair (1,2) + (3,0)
	d_12 = math.hypot(angled[1][1][2] - angled[2][1][2],
					  angled[1][1][3] - angled[2][1][3])
	d_30 = math.hypot(angled[3][1][2] - angled[0][1][2],
					  angled[3][1][3] - angled[0][1][3])

	if (d_01 + d_23) < (d_12 + d_30):
		# Option A: shorter total distance → pairs are on same side
		c0, c1 = angled[0][1], angled[1][1]
		c2, c3 = angled[2][1], angled[3][1]
	else:
		c0, c1 = angled[1][1], angled[2][1]
		c2, c3 = angled[3][1], angled[0][1]

	cuts = []
	if d_01 > 5.0 or d_12 > 5.0:  # at least some distance
		cuts.append(((c0[2], c0[3]), (c1[2], c1[3])))
		cuts.append(((c2[2], c2[3]), (c3[2], c3[3])))

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
			perp_angle_rad = math.radians(perp_branch[0] + 90)
			cut = _cast_cut_ray(fork_node, perp_angle_rad, contours)
			if cut:
				cuts.append(cut)

	elif junction_type == JunctionType.X_JUNCTION:
		# For X-junction: cut perpendicular to ONE collinear pair only
		# This produces 1 cut through the center; the second cut comes
		# from the concavity pairing if available
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
				perp_rad = math.radians(remaining_angle + 90)
				cut = _cast_cut_ray(fork_node, perp_rad, contours)
				if cut:
					cuts.append(cut)
		elif len(angles) >= 2:
			# Only 2 branches (L-junction): cut perpendicular to the bisector
			bisector = (angles[0] + angles[1]) / 2.0
			perp_rad = math.radians(bisector + 90)
			cut = _cast_cut_ray(fork_node, perp_rad, contours)
			if cut:
				cuts.append(cut)

	return cuts


def _normalize_angle(angle):
	"""Normalize angle to [0, 180) for direction grouping."""
	return int(angle % 180)


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
	max_dist = fork_node.radius * 2.5  # cut should span ~stroke width
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


def _intersect_ray_with_contours(ray_line, origin, contours, max_dist=None):
	"""Find nearest intersection of ray with any contour segment.

	Args:
		max_dist: maximum allowed distance from origin (None = unlimited)

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
				if max_dist is not None and d > max_dist:
					continue
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
						if max_dist is not None and d > max_dist:
							continue
						if 1.0 < d < best_dist:
							best_dist = d
							best_pt = (ipt.x, ipt.y)

	return best_pt


# - Stage 2.5: Stroke Path Extraction -----------------------------------

def extract_stroke_paths(graph):
	"""Extract complete stroke paths from terminal to terminal through forks.
	
	A complete stroke path traces from one terminal through regular nodes,
	passing through any forks, to the next terminal.
	
	Returns:
		list of StrokePath namedtuples
	"""
	paths = []
	visited_edges = set()
	
	for start_node in graph.terminals():
		for neighbor in start_node.neighbors:
			edge_key = (id(start_node), id(neighbor))
			if edge_key in visited_edges:
				continue
			
			path_nodes, end_terminal = _trace_full_path(start_node, neighbor, visited_edges)
			
			if len(path_nodes) >= 2:
				forks_in_path = [n for n in path_nodes if n.is_fork]
				terminals_in_path = [n for n in path_nodes if n.is_terminal]
				
				direction_angle = _compute_path_direction(path_nodes)
				paths.append(StrokePath(
					nodes=path_nodes,
					terminals=terminals_in_path,
					forks=forks_in_path,
					direction_angle=direction_angle
				))
	
	return paths


def _trace_full_path(start_node, first_neighbor, visited_edges):
	"""Trace a complete path from start through first_neighbor to next terminal.

	At forks, follows the most collinear continuation (straightest path).
	If no neighbor is within COLLINEAR_THRESHOLD degrees of straight-through,
	the path STOPS at the fork — the stroke ends there.

	Returns: (list of nodes, end_terminal)
	"""
	COLLINEAR_THRESHOLD = 45.0  # max deviation from 180 deg to count as continuation

	path_nodes = [start_node]
	current = first_neighbor
	prev = start_node

	edge_key = (id(start_node), id(first_neighbor))
	visited_edges.add(edge_key)

	while current is not None:
		path_nodes.append(current)

		if current.is_terminal:
			break

		next_nodes = [n for n in current.neighbors if n is not prev]
		if not next_nodes:
			break

		if current.is_fork:
			# At a fork: find the neighbor most collinear with incoming direction
			in_dx = current.x - prev.x
			in_dy = current.y - prev.y
			in_angle = math.degrees(math.atan2(in_dy, in_dx)) % 360

			best_nb = None
			best_deviation = float('inf')

			for nb in next_nodes:
				out_dx = nb.x - current.x
				out_dy = nb.y - current.y
				out_angle = math.degrees(math.atan2(out_dy, out_dx)) % 360

				# Deviation from straight-through (180 deg)
				diff = abs(out_angle - in_angle)
				diff = min(diff, 360 - diff)
				deviation = abs(diff - 180)

				if deviation < best_deviation:
					best_deviation = deviation
					best_nb = nb

			if best_deviation > COLLINEAR_THRESHOLD:
				# No collinear continuation — stroke ends at this fork
				break

			next_node = best_nb
		else:
			next_node = next_nodes[0]

		edge_key = (id(current), id(next_node))
		if edge_key in visited_edges:
			break
		visited_edges.add(edge_key)
		prev, current = current, next_node

	end_terminal = path_nodes[-1] if path_nodes[-1].is_terminal else None
	return path_nodes, end_terminal


def _compute_path_direction(path_nodes):
	"""Compute the primary direction angle of a path."""
	if len(path_nodes) < 2:
		return 0.0
	
	start = path_nodes[0]
	end = path_nodes[-1]
	dx = end.x - start.x
	dy = end.y - start.y
	
	if abs(dx) < _EPS and abs(dy) < _EPS:
		return 0.0
	
	return math.degrees(math.atan2(dy, dx)) % 360


# - Stage 2.6: Cut Coordination -----------------------------------------

def _is_real_junction(fork, stroke_paths=None):
	"""Check if a fork is a real junction (stroke crossing) vs taper artifact.

	A **taper fork** sits at the end of a rectangular stroke where the MAT
	splits into two short branches reaching the stroke-end corners.
	Pattern: exactly 2 branches lead to terminals, 1 to another fork.

	A **junction fork** connects different stroke bodies.
	Pattern: 2+ branches lead to other forks, 0 lead to terminals.
	"""
	n_fork_branches = 0
	n_term_branches = 0

	for nb in fork.neighbors:
		prev, cur = fork, nb
		steps = 0
		target = '?'
		while cur is not None and steps < 500:
			steps += 1
			if cur.is_terminal:
				target = 'T'
				break
			if cur.is_fork:
				target = 'F'
				break
			nxt = [n for n in cur.neighbors if n is not prev]
			if not nxt:
				break
			prev, cur = cur, nxt[0]

		if target == 'F':
			n_fork_branches += 1
		elif target == 'T':
			n_term_branches += 1

	# Junction: 2+ branches connect to other forks (stroke bodies)
	return n_fork_branches >= 2


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

		if not _is_real_junction(fork):
			continue

		for cut in jdata.cuts:
			if not _is_valid_cut(cut, min_stroke_width):
				continue
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
	
	fork_x = min_pt[1].x
	fork_y = min_pt[1].y
	
	origin_x = min_pt[0][0]
	origin_y = min_pt[0][1]
	
	pt1_x = origin_x
	pt1_y = origin_y
	pt2_x = max_pt[0][0]
	pt2_y = max_pt[0][1]
	
	spanning_cut = ((pt1_x, pt1_y), (pt2_x, pt2_y))
	
	if _is_valid_cut(spanning_cut, 20.0):
		return [spanning_cut]
	
	best_cut = max(cuts_forks, key=lambda cf: _cut_length(cf[0]))
	if _is_valid_cut(best_cut[0], 20.0):
		return [best_cut[0]]
	
	return []


def _cut_length(cut):
	"""Get the length of a cut."""
	p1, p2 = cut
	return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _collect_all_cuts(junctions):
	"""Fallback: collect all cuts without coordination."""
	return [cut for j in junctions for cut in j.cuts]


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


# - Fragment Joining --------------------

def _join_fragments(pieces, cuts):
	"""After parallel cuts produce 3+ pieces, join the 2 smallest fragments.

	When 2 parallel cuts split a single contour (e.g., X-junction on a cross),
	they produce 3 pieces: 1 complete stroke + 2 fragments of the other stroke.
	This function joins the 2 fragments into a single closed overlapping contour.

	Args:
		pieces: list of Contour objects (from splitting)
		cuts: list of cut pairs that produced these pieces

	Returns:
		list of Contour objects (with fragments merged if applicable)
	"""
	if len(pieces) != 3 or len(cuts) < 2:
		return pieces

	# Sort by area — 2 smallest are the fragments to join
	areas = []
	for p in pieces:
		a = abs(p.signed_area) if hasattr(p, 'signed_area') else 0
		areas.append(a)

	indexed = sorted(enumerate(areas), key=lambda x: x[1])
	frag_indices = [indexed[0][0], indexed[1][0]]
	main_idx = indexed[2][0]

	frag1 = pieces[frag_indices[0]]
	frag2 = pieces[frag_indices[1]]
	main = pieces[main_idx]

	# Get on-curve nodes
	nodes1 = [n for n in frag1.data if n.is_on]
	nodes2 = [n for n in frag2.data if n.is_on]

	if len(nodes1) < 2 or len(nodes2) < 2:
		return pieces

	# Try both concat orders, pick the one with smallest connection gap
	# Order A: frag1 then frag2
	gap_a = (math.hypot(nodes1[-1].x - nodes2[0].x, nodes1[-1].y - nodes2[0].y) +
			 math.hypot(nodes2[-1].x - nodes1[0].x, nodes2[-1].y - nodes1[0].y))

	# Order B: frag2 then frag1
	gap_b = (math.hypot(nodes2[-1].x - nodes1[0].x, nodes2[-1].y - nodes1[0].y) +
			 math.hypot(nodes1[-1].x - nodes2[0].x, nodes1[-1].y - nodes2[0].y))

	if gap_a <= gap_b:
		combined = nodes1 + nodes2
	else:
		combined = nodes2 + nodes1

	merged_nodes = [Node((n.x, n.y), type='on') for n in combined]
	merged = Contour(merged_nodes, closed=True)

	# Match winding direction to the original main piece
	if main.is_ccw != merged.is_ccw:
		merged.reverse()

	return [main, merged]


# - Main Entry Point -------------------

class StrokeSeparator(object):
	"""CJK Gothic stroke separator.

	Usage:
		sep = StrokeSeparator(beta_min=1.5, sample_step=5.0)
		result = sep.analyze(contours)
		# result.cuts — list of cut pairs
		# result.coordinated_cuts — merged cuts per stroke direction
		# result.junctions — list of JunctionData
		# result.stroke_paths — list of StrokePath
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
		stroke_paths = extract_stroke_paths(graph)

		junctions = []
		for fork in graph.forks():
			jtype = classify_junction(fork, ligatures)
			cuts = solve_cut_points(fork, jtype, concavities, ligatures, contours)
			junctions.append(JunctionData(fork, jtype, cuts))

		return StrokeSepResult(graph, concavities, junctions, stroke_paths)

	def execute(self, result, contours, coordinated=True):
		"""Apply all cuts. Returns new list of Contour objects.

		Does NOT modify input contours.

		Args:
			result: StrokeSepResult from analyze()
			contours: original contour list
			coordinated: if True, use coordinated_cuts; else use raw cuts

		Returns:
			list of Contour objects
		"""
		working = [Contour([n.clone() for n in c.data], closed=c.closed) for c in contours]

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
			prev_count = len(remaining)
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
			# Only do this for X-junction cuts (from the same fork).
			if len(applicable_cuts) == 2 and len(remaining) == 3:
				has_x_junction = any(
					j.junction_type == JunctionType.X_JUNCTION
					for j in result.junctions
				)
				if has_x_junction:
					remaining = _join_fragments(remaining, applicable_cuts)

			output.extend(remaining)

		return output
