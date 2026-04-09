# MODULE: TypeRig / Core / Algo / Medial Axis Transform
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
import heapq
from collections import defaultdict

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.quadraticbezier import QuadraticBezier
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.objects.sdf import SignedDistanceField
from typerig.core.func.geometry import point_in_polygon
from typerig.core.func.math import three_point_circle

# - Init -------------------------------
__version__ = '0.1.0'

# - Constants --------------------------
_EPS = 1e-9

# - Data Structures --------------------
class MATNode(object):
	"""A node in the Medial Axis Transform graph."""

	def __init__(self, x, y, radius):
		self.x = float(x)
		self.y = float(y)
		self.radius = float(radius)
		self.neighbors = []
		self.node_type = None  # 'terminal' | 'regular' | 'fork' | 'isolated'

	def __repr__(self):
		return '<MATNode: ({:.1f}, {:.1f}) r={:.1f} type={} deg={}>'.format(
			self.x, self.y, self.radius, self.node_type, self.degree)

	@property
	def point(self):
		"""Return as TypeRig Point for interop."""
		return Point(self.x, self.y)

	@property
	def degree(self):
		return len(self.neighbors)

	@property
	def is_terminal(self):
		return self.degree == 1

	@property
	def is_fork(self):
		return self.degree >= 3

	def connect(self, other):
		if other not in self.neighbors:
			self.neighbors.append(other)
		if self not in other.neighbors:
			other.neighbors.append(self)

	def disconnect(self, other):
		self.neighbors = [n for n in self.neighbors if n is not other]
		other.neighbors = [n for n in other.neighbors if n is not self]


class MATGraph(object):
	"""The full MAT graph for a glyph contour set."""

	def __init__(self):
		self.nodes = []
		self.exterior_nodes = []

	def __repr__(self):
		n_term = len(self.terminals())
		n_fork = len(self.forks())
		return '<MATGraph: {} nodes, {} terminals, {} forks>'.format(
			len(self.nodes), n_term, n_fork)

	def add_node(self, node):
		self.nodes.append(node)
		return node

	def terminals(self):
		return [n for n in self.nodes if n.is_terminal]

	def forks(self):
		return [n for n in self.nodes if n.is_fork]

	def branches(self):
		"""Return list of (node_a, node_b) edges."""
		seen = set()
		edges = []
		for node in self.nodes:
			for nb in node.neighbors:
				key = (min(id(node), id(nb)), max(id(node), id(nb)))
				if key not in seen:
					seen.add(key)
					edges.append((node, nb))
		return edges

	def walk_branch(self, start, direction):
		"""Walk along a branch from start through direction until fork/terminal.

		Args:
			start: MATNode to start from
			direction: MATNode — the first step direction

		Returns:
			list of MATNode along the branch (including start and end)
		"""
		path = [start]
		prev, cur = start, direction
		while cur is not None:
			path.append(cur)
			if cur.is_fork or cur.is_terminal:
				break
			nxt = [n for n in cur.neighbors if n is not prev]
			if not nxt:
				break
			prev, cur = cur, nxt[0]
		return path

	def extract_branches(self):
		"""Extract all skeleton branches as ordered point sequences.

		Each branch runs from a terminal or fork to the next terminal or fork,
		passing through regular (degree-2) nodes.

		Returns:
			list of lists of MATNode — one list per branch
		"""
		branches = []
		visited_edges = set()

		# Start from every terminal and fork
		start_nodes = [n for n in self.nodes if n.degree != 2]

		for start in start_nodes:
			for nb in start.neighbors:
				edge_key = (min(id(start), id(nb)), max(id(start), id(nb)))
				if edge_key in visited_edges:
					continue

				branch = self.walk_branch(start, nb)

				# Mark all edges in this branch as visited
				for i in range(len(branch) - 1):
					a, b = branch[i], branch[i + 1]
					ek = (min(id(a), id(b)), max(id(a), id(b)))
					visited_edges.add(ek)

				branches.append(branch)

		return branches

	def to_contours(self, smooth=True, simplify_tolerance=1.0):
		"""Convert MAT skeleton to TypeRig Contours for visual inspection.

		Each branch becomes an open Contour. If smooth=True, cubic Bezier
		curves are fitted to the point sequence. Otherwise, simplified
		polyline (line segments only).

		The radius at each on-curve node is stored in node.lib['radius']
		for downstream use (e.g. MetaPen nib sizing).

		Args:
			smooth: if True, fit cubic Bezier curves; if False, polyline only
			simplify_tolerance: max deviation (font units) for point reduction.
				Lower = more points, higher fidelity.

		Returns:
			list of TypeRig Contour objects (open contours)
		"""
		contours = []

		for branch in self.extract_branches():
			if len(branch) < 2:
				continue

			if smooth and len(branch) >= 3:
				contour = _branch_to_cubic_contour(branch, simplify_tolerance)
			else:
				contour = _branch_to_line_contour(branch, simplify_tolerance)

			if contour is not None:
				contours.append(contour)

		return contours

	def to_contours_with_radii(self, smooth=True, simplify_tolerance=1.0):
		"""Convert MAT skeleton to contours, also returning per-node radii.

		Returns:
			contours: list of TypeRig Contour objects (open)
			radii: list of lists of float — one radius list per contour,
				aligned with on-curve nodes in each contour
		"""
		contours = []
		all_radii = []

		for branch in self.extract_branches():
			if len(branch) < 2:
				continue

			if smooth and len(branch) >= 3:
				contour, radii = _branch_to_cubic_contour(branch, simplify_tolerance, return_radii=True)
			else:
				contour, radii = _branch_to_line_contour(branch, simplify_tolerance, return_radii=True)

			if contour is not None:
				contours.append(contour)
				all_radii.append(radii)

		return contours, all_radii


# - Skeleton to Contour helpers ----------
def _simplify_branch(branch, tolerance):
	"""Reduce dense MAT branch to key points using Douglas-Peucker.

	Preserves first, last, and points where deviation exceeds tolerance.
	Returns indices into the original branch list.
	"""
	if len(branch) <= 2:
		return list(range(len(branch)))

	def _perpendicular_dist(pt, line_start, line_end):
		dx = line_end.x - line_start.x
		dy = line_end.y - line_start.y
		len_sq = dx * dx + dy * dy
		if len_sq < _EPS:
			return math.hypot(pt.x - line_start.x, pt.y - line_start.y)
		t = max(0.0, min(1.0, ((pt.x - line_start.x) * dx + (pt.y - line_start.y) * dy) / len_sq))
		proj_x = line_start.x + t * dx
		proj_y = line_start.y + t * dy
		return math.hypot(pt.x - proj_x, pt.y - proj_y)

	def _dp(indices, tol):
		if len(indices) <= 2:
			return indices

		start = branch[indices[0]]
		end = branch[indices[-1]]

		max_dist = 0.0
		max_idx = 0
		for i in range(1, len(indices) - 1):
			d = _perpendicular_dist(branch[indices[i]], start, end)
			if d > max_dist:
				max_dist = d
				max_idx = i

		if max_dist > tol:
			left = _dp(indices[:max_idx + 1], tol)
			right = _dp(indices[max_idx:], tol)
			return left + right[1:]
		else:
			return [indices[0], indices[-1]]

	all_indices = list(range(len(branch)))
	return _dp(all_indices, tolerance)


def _catmull_rom_tangent(prev_pt, curr_pt, next_pt):
	"""Compute Catmull-Rom tangent at curr_pt given its neighbors.

	Returns a unit tangent vector. For open-path endpoints where
	prev or next is None, falls back to the chord direction.
	"""
	if prev_pt is not None and next_pt is not None:
		tx = next_pt[0] - prev_pt[0]
		ty = next_pt[1] - prev_pt[1]
	elif next_pt is not None:
		tx = next_pt[0] - curr_pt[0]
		ty = next_pt[1] - curr_pt[1]
	elif prev_pt is not None:
		tx = curr_pt[0] - prev_pt[0]
		ty = curr_pt[1] - prev_pt[1]
	else:
		return (1.0, 0.0)

	mag = math.hypot(tx, ty)
	if mag < _EPS:
		return (1.0, 0.0)
	return (tx / mag, ty / mag)


def _branch_to_line_contour(branch, simplify_tolerance=0.0, return_radii=False):
	"""Convert a MAT branch to a polyline Contour (on-curve nodes only).

	Args:
		branch: list of MATNode
		simplify_tolerance: if > 0, reduce points via Douglas-Peucker
		return_radii: if True, also return radii at retained nodes
	"""
	if len(branch) < 2:
		if return_radii:
			return None, []
		return None

	# Simplify if requested
	if simplify_tolerance > 0 and len(branch) > 2:
		key_indices = _simplify_branch(branch, simplify_tolerance)
		branch = [branch[i] for i in key_indices]

	nodes = []
	radii = []
	for mat_node in branch:
		n = Node((mat_node.x, mat_node.y), type='on')
		n.lib = {'radius': mat_node.radius}
		nodes.append(n)
		radii.append(mat_node.radius)

	contour = Contour(nodes, closed=False)

	if return_radii:
		return contour, radii
	return contour


def _branch_to_cubic_contour(branch, tolerance=1.0, return_radii=False):
	"""Convert a MAT branch to a smooth cubic Bezier Contour.

	1. Simplify dense points via Douglas-Peucker to key knots
	2. Compute Catmull-Rom tangent at each knot from its neighbors
	3. Place BCPs at knot +/- tangent * (chord / 3)
	4. Build Contour with on, curve, curve, on node pattern

	The Catmull-Rom approach guarantees well-behaved handles:
	tangent direction comes from the neighbor knots, and handle
	length is always proportional to chord length (never overshoots).

	Args:
		branch: list of MATNode
		tolerance: simplification tolerance in font units
		return_radii: if True, also return radii at on-curve nodes

	Returns:
		Contour (or (Contour, radii) if return_radii=True)
	"""
	if len(branch) < 2:
		if return_radii:
			return None, []
		return None

	# Simplify to key points
	key_indices = _simplify_branch(branch, tolerance)
	if len(key_indices) < 2:
		key_indices = [0, len(branch) - 1]

	knots = [(branch[i].x, branch[i].y) for i in key_indices]
	knot_radii = [branch[i].radius for i in key_indices]
	n_knots = len(knots)

	# Two points only — single cubic that's effectively a line
	if n_knots == 2:
		p0, p3 = Point(*knots[0]), Point(*knots[1])
		p1 = p0 + (p3 - p0) * (1.0 / 3.0)
		p2 = p0 + (p3 - p0) * (2.0 / 3.0)

		on0 = Node((p0.x, p0.y), type='on')
		on0.lib = {'radius': knot_radii[0]}
		bcp0 = Node((p1.x, p1.y), type='curve')
		bcp1 = Node((p2.x, p2.y), type='curve')
		on1 = Node((p3.x, p3.y), type='on')
		on1.lib = {'radius': knot_radii[1]}

		contour = Contour([on0, bcp0, bcp1, on1], closed=False)
		if return_radii:
			return contour, [knot_radii[0], knot_radii[1]]
		return contour

	# Compute tangent at each knot (Catmull-Rom: direction from prev to next)
	tangents = []
	for i in range(n_knots):
		prev_pt = knots[i - 1] if i > 0 else None
		next_pt = knots[i + 1] if i < n_knots - 1 else None
		tangents.append(_catmull_rom_tangent(prev_pt, knots[i], next_pt))

	# Build contour: for each consecutive pair of knots, place BCPs
	contour_nodes = []
	radii = []

	for seg_i in range(n_knots - 1):
		ax, ay = knots[seg_i]
		bx, by = knots[seg_i + 1]
		chord = math.hypot(bx - ax, by - ay)

		# Handle length = chord / 3 — the standard Catmull-Rom to Bezier ratio
		handle_len = chord / 3.0

		# BCP out from knot[seg_i]: along tangent
		tx0, ty0 = tangents[seg_i]
		p1x = ax + tx0 * handle_len
		p1y = ay + ty0 * handle_len

		# BCP in to knot[seg_i+1]: against tangent (arriving)
		tx1, ty1 = tangents[seg_i + 1]
		p2x = bx - tx1 * handle_len
		p2y = by - ty1 * handle_len

		if seg_i == 0:
			on_node = Node((ax, ay), type='on')
			on_node.lib = {'radius': knot_radii[seg_i]}
			contour_nodes.append(on_node)
			radii.append(knot_radii[seg_i])

		bcp_out = Node((p1x, p1y), type='curve')
		bcp_in = Node((p2x, p2y), type='curve')
		is_inner = seg_i < n_knots - 2
		on_end = Node((bx, by), type='on', smooth=is_inner)
		on_end.lib = {'radius': knot_radii[seg_i + 1]}

		contour_nodes.append(bcp_out)
		contour_nodes.append(bcp_in)
		contour_nodes.append(on_end)
		radii.append(knot_radii[seg_i + 1])

	if len(contour_nodes) < 2:
		if return_radii:
			return None, []
		return None

	contour = Contour(contour_nodes, closed=False)
	if return_radii:
		return contour, radii
	return contour


# - Step 1: Contour Sampling ----------
def sample_contour(contour, step=3.0):
	"""Sample points along a contour at approximately `step` unit intervals.

	Uses arc-length stepping for CubicBezier segments and uniform
	parametric stepping for Line and QuadraticBezier segments.

	Args:
		contour: TypeRig Contour object
		step: approximate spacing in font units (2-4 is good for 1000 UPM)

	Returns:
		list of (x, y) tuples, ordered along the contour
	"""
	points = []

	for segment in contour.segments:
		if isinstance(segment, Line):
			seg_len = segment.length
			if seg_len < _EPS:
				continue
			n_samples = max(1, int(seg_len / step))
			for i in range(n_samples):
				t = i / float(n_samples)
				pt = segment.solve_point(t)
				points.append((pt.x, pt.y))

		elif isinstance(segment, CubicBezier):
			seg_len = segment.get_arc_length()
			if seg_len < _EPS:
				continue
			n_samples = max(1, int(seg_len / step))
			for i in range(n_samples):
				dist = i * step
				if dist > seg_len:
					dist = seg_len
				t = segment.solve_distance_start(dist, timeStep=0.001)
				pt = segment.solve_point(t)
				points.append((pt.x, pt.y))

		elif isinstance(segment, QuadraticBezier):
			seg_len = segment.get_arc_length()
			if seg_len < _EPS:
				continue
			n_samples = max(1, int(seg_len / step))
			for i in range(n_samples):
				t = i / float(n_samples)
				pt = segment.solve_point(t)
				points.append((pt.x, pt.y))

	return points


# - Step 2: Bowyer-Watson Delaunay + Voronoi Dualization ----------
class BowyerWatson(object):
	"""Incremental Delaunay triangulation via Bowyer-Watson algorithm.

	Pure Python, no dependencies beyond stdlib.
	Dualizes to Voronoi diagram via circumcenter computation.
	"""

	def __init__(self):
		self._points = []

	def triangulate(self, points):
		"""Compute Delaunay triangulation of 2D point set.

		Args:
			points: list of (x, y) tuples

		Returns:
			list of (i, j, k) index triples into `points`
		"""
		self._points = list(points)
		n = len(self._points)
		if n < 3:
			return []

		# Compute bounding box for super-triangle
		xs = [p[0] for p in self._points]
		ys = [p[1] for p in self._points]
		x_min, x_max = min(xs), max(xs)
		y_min, y_max = min(ys), max(ys)
		dx = x_max - x_min
		dy = y_max - y_min
		dmax = max(dx, dy, 1.0)
		x_mid = (x_min + x_max) * 0.5
		y_mid = (y_min + y_max) * 0.5

		# Super-triangle vertices (indices n, n+1, n+2)
		margin = 20.0
		st0 = (x_mid - margin * dmax, y_mid - dmax)
		st1 = (x_mid + margin * dmax, y_mid - dmax)
		st2 = (x_mid, y_mid + margin * dmax)

		self._points.append(st0)
		self._points.append(st1)
		self._points.append(st2)

		# Initial triangulation: just the super-triangle
		# Each triangle stored as (i, j, k) with CCW ordering
		triangles = set()
		triangles.add((n, n + 1, n + 2))

		# Circumcircle cache: tri -> (cx, cy, r_sq)
		# Inlined computation avoids function-call overhead in tight loop
		circ_cache = {}
		pts = self._points  # local ref for speed

		def _compute_circ(tri):
			"""Compute and cache circumcircle for a triangle."""
			i, j, k = tri
			p1x, p1y = pts[i]
			p2x, p2y = pts[j]
			p3x, p3y = pts[k]
			# Inlined three_point_circle
			temp = p2x * p2x + p2y * p2y
			bc = (p1x * p1x + p1y * p1y - temp) * 0.5
			cd = (temp - p3x * p3x - p3y * p3y) * 0.5
			det = (p1x - p2x) * (p2y - p3y) - (p2x - p3x) * (p1y - p2y)
			if abs(det) < 1e-6:
				cx = (p1x + p2x + p3x) / 3.0
				cy = (p1y + p2y + p3y) / 3.0
				val = (cx, cy, float('inf'))
			else:
				inv_det = 1.0 / det
				cx = (bc * (p2y - p3y) - cd * (p1y - p2y)) * inv_det
				cy = ((p1x - p2x) * cd - (p2x - p3x) * bc) * inv_det
				r_sq = (cx - p1x) ** 2 + (cy - p1y) ** 2
				val = (cx, cy, r_sq)
			circ_cache[tri] = val
			return val

		# Pre-compute circumcircle for super-triangle
		_compute_circ((n, n + 1, n + 2))

		# Insert points one by one
		for p_idx in range(n):
			px, py = pts[p_idx]

			# Find all triangles whose circumcircle contains the point
			bad_triangles = []
			cache = circ_cache  # local ref
			for tri in triangles:
				cc = cache.get(tri)
				if cc is None:
					cc = _compute_circ(tri)
				cx, cy, r_sq = cc
				if r_sq == float('inf') or (px - cx) * (px - cx) + (py - cy) * (py - cy) < r_sq:
					bad_triangles.append(tri)

			# Find boundary polygon (edges shared by exactly one bad triangle)
			edge_count = defaultdict(int)
			for tri in bad_triangles:
				i, j, k = tri
				e1 = (i, j) if i < j else (j, i)
				e2 = (j, k) if j < k else (k, j)
				e3 = (i, k) if i < k else (k, i)
				edge_count[e1] += 1
				edge_count[e2] += 1
				edge_count[e3] += 1

			boundary = [e for e, c in edge_count.items() if c == 1]

			# Remove bad triangles
			for tri in bad_triangles:
				triangles.discard(tri)
				cache.pop(tri, None)

			# Re-triangulate hole with new point
			for a, b in boundary:
				new_tri = tuple(sorted((a, b, p_idx)))
				triangles.add(new_tri)

		# Remove triangles that reference super-triangle vertices
		super_indices = {n, n + 1, n + 2}
		triangles = {tri for tri in triangles
					 if not (set(tri) & super_indices)}

		# Remove super-triangle points
		self._points = self._points[:n]

		return list(triangles)

	def voronoi_from_delaunay(self, points, triangles):
		"""Dualize Delaunay triangulation to Voronoi diagram.

		Each triangle's circumcenter becomes a Voronoi vertex.
		Each shared triangle edge becomes a Voronoi edge connecting
		the two circumcenters.

		Args:
			points: list of (x, y) — the original site points
			triangles: list of (i, j, k) from triangulate()

		Returns:
			vertices: list of (x, y) Voronoi vertex positions
			edges: list of (v_idx_a, v_idx_b) Voronoi edge index pairs
		"""
		if not triangles:
			return [], []

		# Compute circumcenter for each triangle
		tri_to_idx = {}
		vertices = []

		for tri in triangles:
			i, j, k = tri
			p1, p2, p3 = points[i], points[j], points[k]
			result = three_point_circle(p1, p2, p3)

			if result[0] is None:
				# Degenerate — use centroid
				cx = (p1[0] + p2[0] + p3[0]) / 3.0
				cy = (p1[1] + p2[1] + p3[1]) / 3.0
			else:
				center, _radius = result
				cx, cy = center

			tri_key = tuple(sorted(tri))
			tri_to_idx[tri_key] = len(vertices)
			vertices.append((cx, cy))

		# Build edge-to-triangle adjacency
		# An edge shared by two triangles produces a Voronoi edge
		edge_to_tris = defaultdict(list)
		for tri in triangles:
			tri_key = tuple(sorted(tri))
			i, j, k = tri_key
			for edge in ((i, j), (i, k), (j, k)):
				edge_to_tris[edge].append(tri_key)

		edges = []
		for edge, tris in edge_to_tris.items():
			if len(tris) == 2:
				v_a = tri_to_idx[tris[0]]
				v_b = tri_to_idx[tris[1]]
				edges.append((v_a, v_b))

		return vertices, edges


# - Spatial Grid for fast proximity queries ----------
class _SpatialGrid(object):
	"""Uniform grid spatial index for fast nearest-edge queries.

	Buckets polyline edges into grid cells so that distance/inside
	queries only check edges in nearby cells instead of all edges.
	"""

	def __init__(self, polylines, cell_size):
		self._cell = float(cell_size)
		self._grid = defaultdict(list)  # (gx, gy) -> [(ax, ay, bx, by), ...]
		self._polylines = polylines

		# Index all edges into grid cells (for min_distance)
		# and into y-buckets (for is_inside ray casting)
		self._y_buckets = defaultdict(list)
		for poly in polylines:
			n = len(poly)
			for i in range(n):
				ax, ay = poly[i]
				bx, by = poly[(i + 1) % n]
				self._insert_edge(ax, ay, bx, by)
				# Y-bucket: insert edge into all y-rows it spans
				gy0 = int(math.floor(min(ay, by) / self._cell))
				gy1 = int(math.floor(max(ay, by) / self._cell))
				edge_data = (ax, ay, bx, by)
				for gy in range(gy0, gy1 + 1):
					self._y_buckets[gy].append(edge_data)

	def _cell_key(self, x, y):
		return (int(math.floor(x / self._cell)), int(math.floor(y / self._cell)))

	def _insert_edge(self, ax, ay, bx, by):
		"""Insert edge into all cells it overlaps."""
		edge = (ax, ay, bx, by)
		gx0 = int(math.floor(min(ax, bx) / self._cell))
		gx1 = int(math.floor(max(ax, bx) / self._cell))
		gy0 = int(math.floor(min(ay, by) / self._cell))
		gy1 = int(math.floor(max(ay, by) / self._cell))
		for gx in range(gx0, gx1 + 1):
			for gy in range(gy0, gy1 + 1):
				self._grid[(gx, gy)].append(edge)

	def min_distance(self, px, py):
		"""Minimum unsigned distance from (px, py) to any polyline edge.

		Searches outward from the point's grid cell until the search
		radius exceeds the best distance found so far.
		"""
		gx0, gy0 = self._cell_key(px, py)
		min_d = float('inf')
		ring = 0

		while True:
			# Search cells in current ring
			found_any = False
			for gx in range(gx0 - ring, gx0 + ring + 1):
				for gy in range(gy0 - ring, gy0 + ring + 1):
					# Only process cells on the ring boundary (skip interior on ring > 0)
					if ring > 0 and (gx0 - ring < gx < gx0 + ring) and (gy0 - ring < gy < gy0 + ring):
						continue
					edges = self._grid.get((gx, gy))
					if edges:
						found_any = True
						for ax, ay, bx, by in edges:
							d = _point_to_seg_dist(px, py, ax, ay, bx, by)
							if d < min_d:
								min_d = d

			# If best distance is within this ring's guaranteed reach, we're done
			if min_d <= ring * self._cell:
				break

			ring += 1

			# Safety: if we've searched far enough with no edges found, fall back
			if ring > 100 and not found_any:
				break

		return min_d

	def is_inside(self, px, py):
		"""Ray casting odd-crossing test using y-bucketed edges for speed."""
		crossings = 0
		y_buckets = self._y_buckets
		cell = self._cell
		gy = int(math.floor(py / cell))

		# Only check edges in y-buckets that straddle py
		edges = y_buckets.get(gy)
		if edges:
			for ax, ay, bx, by in edges:
				if (ay <= py < by) or (by <= py < ay):
					t = (py - ay) / (by - ay)
					ix = ax + t * (bx - ax)
					if px < ix:
						crossings += 1

		return (crossings % 2) == 1


def _point_to_seg_dist(px, py, ax, ay, bx, by):
	"""Minimum distance from point (px, py) to line segment (ax,ay)-(bx,by)."""
	dx, dy = bx - ax, by - ay
	len_sq = dx * dx + dy * dy
	if len_sq < 1e-12:
		return math.hypot(px - ax, py - ay)
	t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
	proj_x = ax + t * dx
	proj_y = ay + t * dy
	return math.hypot(px - proj_x, py - proj_y)


# - Step 3: Interior/Exterior Filtering ----------
def filter_interior_vertices_sdf(voronoi_vertices, contours, sdf=None, spatial_grid=None):
	"""Classify Voronoi vertices as interior or exterior using ray casting.

	Args:
		voronoi_vertices: list of (x, y) tuples from Voronoi computation
		contours: list of TypeRig Contour objects
		sdf: optional pre-built SignedDistanceField (avoids duplicate creation)
		spatial_grid: optional _SpatialGrid for fast is_inside queries

	Returns:
		interior_indices: set of vertex indices inside the glyph
		exterior_indices: set of vertex indices outside the glyph
	"""
	if sdf is None and spatial_grid is None:
		sdf = SignedDistanceField(contours, resolution=1.0, padding=20, steps_per_segment=64)

	interior = set()
	exterior = set()

	if spatial_grid is not None:
		for idx, (vx, vy) in enumerate(voronoi_vertices):
			if spatial_grid.is_inside(vx, vy):
				interior.add(idx)
			else:
				exterior.add(idx)
	else:
		for idx, (vx, vy) in enumerate(voronoi_vertices):
			if sdf._is_inside(vx, vy):
				interior.add(idx)
			else:
				exterior.add(idx)

	return interior, exterior


# - Step 5: Build MAT Graph ----------
def build_mat_graph(voronoi_vertices, voronoi_edges, interior_indices, contours, sdf=None, spatial_grid=None):
	"""Build MATGraph from interior Voronoi vertices.

	Args:
		voronoi_vertices: list of (x, y) from Voronoi computation
		voronoi_edges: list of (v_idx_a, v_idx_b) from Voronoi
		interior_indices: set of vertex indices inside the glyph
		contours: glyph contours (for radius computation)
		sdf: optional pre-built SignedDistanceField
		spatial_grid: optional _SpatialGrid for fast radius queries

	Returns:
		MATGraph
	"""
	if sdf is None and spatial_grid is None:
		sdf = SignedDistanceField(contours, resolution=1.0, padding=20, steps_per_segment=64)

	# Create MATNode for each interior vertex
	nodes = {}
	for idx in interior_indices:
		x, y = voronoi_vertices[idx]
		if spatial_grid is not None:
			r = spatial_grid.min_distance(x, y)
		else:
			r = sdf._min_distance(x, y)
		node = MATNode(x, y, r)
		nodes[idx] = node

	# Connect nodes where both endpoints are interior
	graph = MATGraph()
	for a_idx, b_idx in voronoi_edges:
		if a_idx in nodes and b_idx in nodes:
			nodes[a_idx].connect(nodes[b_idx])

	for node in nodes.values():
		graph.add_node(node)

	return graph


# - Step 6: Branch Pruning (Scale Axis Transform) ----------
def prune_mat(graph, beta_min=1.5):
	"""Remove spurious terminal branches from the MAT graph.

	A terminal branch is pruned if the maximum inscribed radius
	along the branch is small relative to the fork radius:
		max_radius_on_branch / radius_at_fork < 1 / beta_min

	This distinguishes real stroke branches (which taper from large
	to small toward outline corners) from noise branches caused by
	digitization artifacts (which have uniformly small radii).

	Iterates until no more branches are pruned.

	Args:
		graph: MATGraph (modified in place)
		beta_min: threshold ratio (1.5 is the paper default)

	Returns:
		graph (modified in place)
	"""
	changed = True
	while changed:
		changed = False
		for node in list(graph.nodes):
			if node.is_terminal and node in graph.nodes:
				if not node.neighbors:
					continue

				# Walk the branch from terminal toward the fork
				branch = graph.walk_branch(node, node.neighbors[0])

				# The last node in the walk is the fork (or another terminal)
				fork = branch[-1]
				fork_radius = fork.radius

				# Use max radius along the branch (excluding the fork)
				branch_nodes = branch[:-1] if len(branch) > 1 else branch
				max_branch_radius = max(n.radius for n in branch_nodes)

				if max_branch_radius / max(fork_radius, _EPS) < 1.0 / beta_min:
					# Remove all nodes in this branch except the fork
					for n in branch[:-1]:
						for nb in list(n.neighbors):
							n.disconnect(nb)
						if n in graph.nodes:
							graph.nodes.remove(n)
					changed = True

	return graph


# - Step 7: Node Classification ----------
def classify_nodes(graph):
	"""Assign node_type to each MATNode based on degree.

	Also sorts each fork's neighbors counter-clockwise by branch angle.
	Uses standard atan2(dy, dx) — NOT get_angle which has unusual convention.
	"""
	for node in graph.nodes:
		d = node.degree
		if d == 0:
			node.node_type = 'isolated'
		elif d == 1:
			node.node_type = 'terminal'
		elif d == 2:
			node.node_type = 'regular'
		else:
			node.node_type = 'fork'
			# Sort neighbors CCW by angle from fork
			node.neighbors.sort(
				key=lambda nb: math.atan2(nb.y - node.y, nb.x - node.x)
			)


# - Step 8: Concavity Detection ----------
def find_concavities(contours, angle_threshold=150.0):
	"""Find concave vertices on the outline.

	A vertex is concave if the interior angle is less than angle_threshold
	and the turn direction indicates inward bending.

	For CCW (outer) contours: concave = CW turn (cross < 0).
	For CW (inner) contours: concave = CCW turn (cross > 0).

	Args:
		contours: list of TypeRig Contour objects
		angle_threshold: maximum exterior angle (degrees) to qualify as concavity

	Returns:
		list of (contour_idx, node_idx, x, y, exterior_angle_degrees) tuples
	"""
	concavities = []

	for c_idx, contour in enumerate(contours):
		is_outer = contour.is_ccw

		# Iterate on-curve nodes
		on_nodes = [n for n in contour.nodes if n.is_on]
		n_nodes = len(on_nodes)

		if n_nodes < 3:
			continue

		for i in range(n_nodes):
			prev_node = on_nodes[(i - 1) % n_nodes]
			curr_node = on_nodes[i]
			next_node = on_nodes[(i + 1) % n_nodes]

			# Incoming and outgoing direction vectors
			dx_in = curr_node.x - prev_node.x
			dy_in = curr_node.y - prev_node.y
			dx_out = next_node.x - curr_node.x
			dy_out = next_node.y - curr_node.y

			# Cross product: positive = CCW turn, negative = CW turn
			cross = dx_in * dy_out - dy_in * dx_out

			# Interior angle via dot product
			dot = dx_in * dx_out + dy_in * dy_out
			mag_in = math.hypot(dx_in, dy_in)
			mag_out = math.hypot(dx_out, dy_out)

			if mag_in < _EPS or mag_out < _EPS:
				continue

			cos_angle = max(-1.0, min(1.0, dot / (mag_in * mag_out)))
			exterior_angle = math.degrees(math.acos(cos_angle))

			# For outer (CCW) contour: concave = CW turn (cross < 0)
			# For inner (CW) contour: concave = CCW turn (cross > 0)
			is_concave = (cross < 0) if is_outer else (cross > 0)

			if is_concave and exterior_angle < angle_threshold:
				concavities.append((c_idx, i, curr_node.x, curr_node.y, exterior_angle))

	return concavities


# - Quality presets ----------
_QUALITY_PRESETS = {
	'draft':  {'sample_step': 10.0, 'sdf_steps': 32},
	'normal': {'sample_step':  5.0, 'sdf_steps': 48},
	'fine':   {'sample_step':  3.0, 'sdf_steps': 64},
}


# - Step 9: Main Entry Point ----------
def compute_mat(contours, sample_step=None, beta_min=1.5, quality='normal'):
	"""Compute the Medial Axis Transform of a glyph.

	Args:
		contours: list of TypeRig Contour objects (the glyph outline)
		sample_step: outline sampling density in font units.
			If None, determined by quality preset.
		beta_min: pruning threshold (1.5 = paper default)
		quality: 'draft' (fast preview), 'normal' (default), or 'fine' (highest fidelity)

	Returns:
		graph: MATGraph — the pruned interior MAT
		concavities: list of concave outline points as
			(contour_idx, node_idx, x, y, angle) tuples
	"""
	# Resolve quality preset
	preset = _QUALITY_PRESETS.get(quality, _QUALITY_PRESETS['normal'])
	if sample_step is None:
		sample_step = preset['sample_step']
	sdf_steps = preset['sdf_steps']

	# 0. Ensure cubic-only contours
	cubic_contours = []
	for c in contours:
		if c.has_quadratic:
			cubic_contours.append(c.to_cubic_contour())
		else:
			cubic_contours.append(c)

	# 1. Sample outline
	all_points = []
	for contour in cubic_contours:
		all_points.extend(sample_contour(contour, step=sample_step))

	if len(all_points) < 3:
		return MATGraph(), []

	# 2. Remove duplicate points (within epsilon)
	unique_points = []
	seen = set()
	for pt in all_points:
		key = (round(pt[0], 4), round(pt[1], 4))
		if key not in seen:
			seen.add(key)
			unique_points.append(pt)
	all_points = unique_points

	if len(all_points) < 3:
		return MATGraph(), []

	# 3. Voronoi (via Bowyer-Watson + dualization)
	voronoi = BowyerWatson()
	triangles = voronoi.triangulate(all_points)
	vertices, edges = voronoi.voronoi_from_delaunay(all_points, triangles)

	if not vertices:
		return MATGraph(), []

	# 4. Build SDF once — shared by filtering and radius computation
	sdf = SignedDistanceField(cubic_contours, resolution=1.0, padding=20, steps_per_segment=sdf_steps)

	# 5. Build spatial grid for fast radius queries
	spatial_grid = _SpatialGrid(sdf._polylines, cell_size=max(sample_step * 10, 20.0))

	# 6. Filter interior (use spatial grid for fast ray casting)
	interior_indices, exterior_indices = filter_interior_vertices_sdf(vertices, cubic_contours,
																	  sdf=sdf, spatial_grid=spatial_grid)

	if not interior_indices:
		return MATGraph(), []

	# 7. Build graph with radii (use spatial grid for fast distance)
	graph = build_mat_graph(vertices, edges, interior_indices, cubic_contours,
							sdf=sdf, spatial_grid=spatial_grid)

	# 8. Prune
	graph = prune_mat(graph, beta_min=beta_min)

	# 9. Classify
	classify_nodes(graph)

	# 10. Concavities (from outline geometry, not exterior MAT)
	concavities = find_concavities(cubic_contours)

	return graph, concavities
