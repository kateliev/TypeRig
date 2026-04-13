# MODULE: TypeRig / Core / Algo / Stroke Separator — Common Utilities
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Shared helpers used by all stroke-separation sub-modules.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node
from typerig.core.func.geometry import line_intersect

# - Constants --------------------------
_EPS = 1e-9


# - Fast node cloning (avoids deepcopy overhead) ------
def _fast_clone_node(node):
	"""Clone a Node without copy.deepcopy. ~100x faster for contour splitting."""
	from typerig.core.objects.transform import Transform
	n = Node.__new__(Node)
	n.x = node.x
	n.y = node.y
	n.type = node.type
	n.name = getattr(node, 'name', '')
	n.smooth = getattr(node, 'smooth', False)
	n.g2 = getattr(node, 'g2', False)
	n.selected = False
	n.angle = getattr(node, 'angle', 0)
	n.transform = Transform()
	n.identifier = getattr(node, 'identifier', False)
	n.complex_math = getattr(node, 'complex_math', True)
	n.weight = Point(0., 0.)
	n.parent = None
	n.lib = getattr(node, 'lib', None)
	return n


def _fast_clone_contour(contour):
	"""Clone a Contour using fast node cloning."""
	return Contour([_fast_clone_node(n) for n in contour.data], closed=contour.closed)


# - Segment Intersection ------
def _seg_intersects_seg(ax, ay, bx, by, cx, cy, dx, dy):
	"""Return True if open segment AB strictly intersects open segment CD."""
	rx = bx - ax;  ry = by - ay
	sx = dx - cx;  sy = dy - cy
	denom = rx * sy - ry * sx

	if abs(denom) < _EPS:
		return False  # parallel / collinear

	qax = cx - ax;  qay = cy - ay
	t = (qax * sy - qay * sx) / denom
	u = (qax * ry - qay * rx) / denom

	return 1e-6 < t < 1.0 - 1e-6 and 1e-6 < u < 1.0 - 1e-6


# - Ray / Contour Intersection ------
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


# - Angle Normalisation ------
def _normalize_angle(angle):
	"""Normalize angle to [0, 180) for direction grouping."""
	return int(angle % 180)


# - Contour Parameter / Splitting ------
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
			t, d = segment.project_point(query_pt, steps=15)

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
	work = _fast_clone_contour(contour)

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

	nodes_1 = [_fast_clone_node(n) for n in all_nodes[idx_a:idx_b + 1]]
	nodes_2 = [_fast_clone_node(n) for n in all_nodes[idx_b:] + all_nodes[:idx_a + 1]]

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
