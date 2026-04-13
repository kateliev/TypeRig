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


# - Cut Data Structures ----------------

class CutEndpoint(object):
	"""One endpoint of a cut, storing world coordinates and parametric contour location.

	Attributes:
		x, y:         float -- world coordinates
		contour_idx:  int   -- index into the contours list
		node_idx:     int   -- index of the on-curve node in contour.data that owns the segment
		t:            float -- parameter along that segment [0, 1]
	"""
	__slots__ = ('x', 'y', 'contour_idx', 'node_idx', 't')

	def __init__(self, x, y, contour_idx=-1, node_idx=-1, t=0.0):
		self.x = x
		self.y = y
		self.contour_idx = contour_idx
		self.node_idx = node_idx
		self.t = t

	@property
	def tuple(self):
		return (self.x, self.y)

	def __repr__(self):
		return '<CutEndpoint ({:.1f},{:.1f}) c{}:n{}:t={:.3f}>'.format(
			self.x, self.y, self.contour_idx, self.node_idx, self.t)


class CutPair(object):
	"""A cut defined by two endpoints, with backward-compatible tuple access.

	Supports ``cut[0]`` -> ``(x1, y1)`` and ``cut[1]`` -> ``(x2, y2)``
	so that existing code using tuple indexing works unchanged.

	Attributes:
		a, b:  CutEndpoint -- the two endpoints
	"""
	__slots__ = ('a', 'b')

	def __init__(self, a, b):
		self.a = a
		self.b = b

	def __getitem__(self, idx):
		if idx == 0:
			return (self.a.x, self.a.y)
		elif idx == 1:
			return (self.b.x, self.b.y)
		raise IndexError('CutPair index out of range')

	def __len__(self):
		return 2

	def __iter__(self):
		yield (self.a.x, self.a.y)
		yield (self.b.x, self.b.y)

	def __repr__(self):
		return '<CutPair ({:.1f},{:.1f})->({:.1f},{:.1f})>'.format(
			self.a.x, self.a.y, self.b.x, self.b.y)


def resolve_cut_parameters(raw_cuts, contours):
	"""Convert raw coordinate cuts into CutPair objects with parametric locations.

	Args:
		raw_cuts:  list of ((x1,y1), (x2,y2)) tuples
		contours:  list of Contour objects used during analysis

	Returns:
		list of CutPair with resolved contour_idx, node_idx, t for each endpoint
	"""
	result = []

	for cut in raw_cuts:
		endpoints = []
		for pt in (cut[0], cut[1]):
			px, py = pt[0], pt[1]
			best_ci = -1
			best_node_idx = -1
			best_t = 0.0
			best_dist = float('inf')

			for ci, contour in enumerate(contours):
				node, t, dist = find_parameter_on_contour(contour, px, py)
				if node is not None and dist < best_dist:
					best_dist = dist
					best_ci = ci
					best_node_idx = node.idx
					best_t = t

			endpoints.append(CutEndpoint(px, py, best_ci, best_node_idx, best_t))

		result.append(CutPair(endpoints[0], endpoints[1]))

	return result


def check_contour_compatibility(source_contours, target_contours):
	"""Check that two contour lists are structurally compatible for cross-master cuts.

	Compatible means: same number of contours, same number of nodes per contour,
	same node types at each position.

	Args:
		source_contours: list of Contour
		target_contours: list of Contour

	Returns:
		True if compatible

	Raises:
		ValueError with details if incompatible
	"""
	if len(source_contours) != len(target_contours):
		raise ValueError(
			'Contour count mismatch: source={} target={}'.format(
				len(source_contours), len(target_contours)))

	for ci, (sc, tc) in enumerate(zip(source_contours, target_contours)):
		s_nodes = list(sc.data)
		t_nodes = list(tc.data)
		if len(s_nodes) != len(t_nodes):
			raise ValueError(
				'Node count mismatch in contour {}: source={} target={}'.format(
					ci, len(s_nodes), len(t_nodes)))
		for ni, (sn, tn) in enumerate(zip(s_nodes, t_nodes)):
			if sn.type != tn.type:
				raise ValueError(
					'Node type mismatch at contour {} node {}: source={!r} target={!r}'.format(
						ci, ni, sn.type, tn.type))

	return True


# - Cross-Master Cut Application ------

def apply_cuts_to_layer(result, source_contours, target_contours):
	"""Apply cuts from an analyzed layer to a compatible target layer.

	Uses the parametric locations (contour_idx, node_idx, t) stored in each
	CutPair to evaluate new coordinates on the target contours, then splits
	at those coordinates.  No MAT recomputation is needed.

	Args:
		result:           StrokeSepResult from analyzing source_contours
		source_contours:  list[Contour] -- the contours that were analyzed
		target_contours:  list[Contour] -- compatible contours from another master

	Returns:
		list[Contour] -- target contours with cuts applied (new objects,
		                 target_contours are not modified)

	Raises:
		ValueError: if target_contours are not structurally compatible
	"""
	check_contour_compatibility(source_contours, target_contours)

	# Resolve target coordinates from parametric locations
	target_cuts = []
	for cut_pair in result.cuts:
		pts = []
		for ep in (cut_pair.a, cut_pair.b):
			target_contour = target_contours[ep.contour_idx]
			target_node = target_contour.data[ep.node_idx]
			segment = target_node.segment
			pt = segment.solve_point(ep.t)
			pts.append((pt.x, pt.y))
		target_cuts.append((pts[0], pts[1]))

	# Split target contours at the resolved coordinates
	working = [_fast_clone_contour(c) for c in target_contours]

	output = []
	for contour in working:
		applicable = []
		for cut in target_cuts:
			_, _, da = find_parameter_on_contour(contour, cut[0][0], cut[0][1])
			_, _, db = find_parameter_on_contour(contour, cut[1][0], cut[1][1])
			if da < 15.0 and db < 15.0:
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
				if da > 15.0 or db > 15.0:
					new_remaining.append(c)
					continue
				split = split_contour_at_points(c, cut[0], cut[1])
				if split is not None:
					new_remaining.extend(split)
				else:
					new_remaining.append(c)
			remaining = new_remaining

		# X-junction overlap: 2 parallel cuts producing 3 pieces
		# need the 2 smallest fragments joined into one overlapping stroke
		if len(applicable) == 2 and len(remaining) == 3:
			has_x = False
			for j in result.junctions:
				if hasattr(j, 'junction_type') and j.junction_type == 'X':
					has_x = True
					break
			if has_x:
				remaining = _join_fragments(remaining, applicable)

		output.extend(remaining)

	return output


# - Unified Result ---------------------

class StrokeSepResult(object):
	"""Unified analysis result returned by both V1 and V2 pipelines.

	V1-only fields are None/[] when produced by V2 and vice versa.
	The ``cuts`` list always contains CutPair objects with parametric
	contour locations, regardless of which pipeline produced the result.

	Attributes shared by both pipelines:
		pipeline:      str          -- 'v1' or 'v2'
		graph:         MATGraph     -- interior medial axis
		concavities:   list         -- raw concavity tuples from compute_mat
		cuts:          list[CutPair]

	V1-specific (None/[] when pipeline='v2'):
		junctions:     list[JunctionData]
		stroke_paths:  list[StrokePath]
		stroke_width:  float or None

	V2-specific (None/[] when pipeline='v1'):
		ext_graph:        MATGraph or None
		csfs:             list
		ligatures:        list[Ligature]
		links:            list[Link]
		protuberances:    list[JunctionResult]
		half_junctions:   list[JunctionResult]
		step3_junctions:  list[JunctionResult]
		stroke_graph:     StrokeGraph or None
	"""

	def __init__(self, pipeline, graph, concavities=None, cuts=None,
				 # V1 fields
				 junctions=None, stroke_paths=None, stroke_width=None,
				 # V2 fields
				 ext_graph=None, csfs=None, ligatures=None, links=None,
				 protuberances=None, half_junctions=None,
				 step3_junctions=None, stroke_graph=None):

		self.pipeline         = pipeline
		self.graph            = graph
		self.concavities      = concavities or []
		self.cuts             = cuts or []

		# V1
		self.junctions        = junctions or []
		self.stroke_paths     = stroke_paths or []
		self.stroke_width     = stroke_width

		# V2
		self.ext_graph        = ext_graph
		self.csfs             = csfs or []
		self.ligatures        = ligatures or []
		self.links            = links or []
		self.protuberances    = protuberances or []
		self.half_junctions   = half_junctions or []
		self.step3_junctions  = step3_junctions or []
		self.stroke_graph     = stroke_graph

		# V1 internals (computed lazily)
		self._junction_is_real = None

	# -- Computed properties (V1) --------

	@property
	def coordinated_cuts(self):
		"""Deduplicated cuts (V1). For V2, returns cuts as-is."""
		if self.pipeline == 'v1' and self.junctions:
			# Lazy import to avoid circular dependency
			from typerig.core.algo.stroke_sep_v1 import coordinate_cuts
			return coordinate_cuts(self.junctions, self.stroke_paths, self.stroke_width)
		return self.cuts

	def _compute_real_junctions(self):
		if self._junction_is_real is None:
			self._junction_is_real = {}
			if self.junctions:
				from typerig.core.algo.stroke_sep_v1 import _is_real_junction
				for jdata in self.junctions:
					fork = jdata.fork_node
					self._junction_is_real[id(fork)] = _is_real_junction(fork, self.stroke_paths)
		return self._junction_is_real

	def is_real_junction(self, fork):
		"""Check if a fork is a real junction (V1 only)."""
		return self._compute_real_junctions().get(id(fork), False)

	# -- Computed properties (V2) --------

	@property
	def all_junctions(self):
		"""All V2 junction results combined."""
		return self.protuberances + self.half_junctions + self.step3_junctions

	@property
	def strokes(self):
		"""Stroke IDs from the stroke graph (V2 only)."""
		if self.stroke_graph is not None:
			return self.stroke_graph.strokes()
		return []

	# -- Repr ----------------------------

	def __repr__(self):
		if self.pipeline == 'v2':
			return ('<StrokeSepResult[v2]: {} cuts | {} links | '
					'{} junctions>'.format(
						len(self.cuts), len(self.links), len(self.all_junctions)))
		else:
			real = sum(self._compute_real_junctions().values()) if self.junctions else 0
			return '<StrokeSepResult[v1]: {} junctions ({} real) | {} cuts | {} strokes>'.format(
				len(self.junctions), real, len(self.cuts), len(self.stroke_paths))


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
