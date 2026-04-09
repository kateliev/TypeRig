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
		circ_cache = {}

		def circumcircle(tri):
			if tri in circ_cache:
				return circ_cache[tri]
			i, j, k = tri
			p1 = self._points[i]
			p2 = self._points[j]
			p3 = self._points[k]
			result = three_point_circle(p1, p2, p3)
			if result[0] is None:
				# Degenerate (collinear) — use very large circle
				cx = (p1[0] + p2[0] + p3[0]) / 3.0
				cy = (p1[1] + p2[1] + p3[1]) / 3.0
				circ_cache[tri] = (cx, cy, float('inf'))
			else:
				center, radius = result
				circ_cache[tri] = (center[0], center[1], radius * radius)
			return circ_cache[tri]

		def in_circumcircle(tri, px, py):
			cx, cy, r_sq = circumcircle(tri)
			if r_sq == float('inf'):
				return True
			dist_sq = (px - cx) ** 2 + (py - cy) ** 2
			return dist_sq < r_sq - _EPS

		# Insert points one by one
		for p_idx in range(n):
			px, py = self._points[p_idx]

			# Find all triangles whose circumcircle contains the point
			bad_triangles = set()
			for tri in triangles:
				if in_circumcircle(tri, px, py):
					bad_triangles.add(tri)

			# Find boundary polygon (edges shared by exactly one bad triangle)
			edge_count = defaultdict(int)
			edge_to_tri = {}
			for tri in bad_triangles:
				i, j, k = tri
				for edge in ((i, j), (j, k), (k, i)):
					e = (min(edge), max(edge))
					edge_count[e] += 1
					edge_to_tri[e] = tri

			boundary = []
			for edge, count in edge_count.items():
				if count == 1:
					boundary.append(edge)

			# Remove bad triangles
			for tri in bad_triangles:
				triangles.discard(tri)
				circ_cache.pop(tri, None)

			# Re-triangulate hole with new point
			for edge in boundary:
				a, b = edge
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


# - Step 3: Interior/Exterior Filtering ----------
def filter_interior_vertices_sdf(voronoi_vertices, contours):
	"""Classify Voronoi vertices as interior or exterior using SDF ray casting.

	Args:
		voronoi_vertices: list of (x, y) tuples from Voronoi computation
		contours: list of TypeRig Contour objects

	Returns:
		interior_indices: set of vertex indices inside the glyph
		exterior_indices: set of vertex indices outside the glyph
	"""
	sdf = SignedDistanceField(contours, resolution=1.0, padding=20, steps_per_segment=64)

	interior = set()
	exterior = set()

	for idx, (vx, vy) in enumerate(voronoi_vertices):
		if sdf._is_inside(vx, vy):
			interior.add(idx)
		else:
			exterior.add(idx)

	return interior, exterior


# - Step 4: Radius Computation (via SDF) ----------
def _inscribed_radius_sdf(px, py, sdf):
	"""Unsigned distance to nearest boundary using SDF polylines."""
	return sdf._min_distance(px, py)


# - Step 5: Build MAT Graph ----------
def build_mat_graph(voronoi_vertices, voronoi_edges, interior_indices, contours, sdf=None):
	"""Build MATGraph from interior Voronoi vertices.

	Args:
		voronoi_vertices: list of (x, y) from Voronoi computation
		voronoi_edges: list of (v_idx_a, v_idx_b) from Voronoi
		interior_indices: set of vertex indices inside the glyph
		contours: glyph contours (for radius computation)
		sdf: optional pre-built SignedDistanceField

	Returns:
		MATGraph
	"""
	if sdf is None:
		sdf = SignedDistanceField(contours, resolution=1.0, padding=20, steps_per_segment=64)

	# Create MATNode for each interior vertex
	nodes = {}
	for idx in interior_indices:
		x, y = voronoi_vertices[idx]
		r = _inscribed_radius_sdf(x, y, sdf)
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


# - Step 9: Main Entry Point ----------
def compute_mat(contours, sample_step=3.0, beta_min=1.5):
	"""Compute the Medial Axis Transform of a glyph.

	Args:
		contours: list of TypeRig Contour objects (the glyph outline)
		sample_step: outline sampling density in font units (2-4 for 1000 UPM)
		beta_min: pruning threshold (1.5 = paper default)

	Returns:
		graph: MATGraph — the pruned interior MAT
		concavities: list of concave outline points as
			(contour_idx, node_idx, x, y, angle) tuples
	"""
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

	# 4. Build SDF for radius computation and inside/outside testing
	sdf = SignedDistanceField(cubic_contours, resolution=1.0, padding=20, steps_per_segment=64)

	# 5. Filter interior
	interior_indices, exterior_indices = filter_interior_vertices_sdf(vertices, cubic_contours)

	if not interior_indices:
		return MATGraph(), []

	# 6. Build graph with radii
	graph = build_mat_graph(vertices, edges, interior_indices, cubic_contours, sdf=sdf)

	# 7. Prune
	graph = prune_mat(graph, beta_min=beta_min)

	# 8. Classify
	classify_nodes(graph)

	# 9. Concavities (from outline geometry, not exterior MAT)
	concavities = find_concavities(cubic_contours)

	return graph, concavities
