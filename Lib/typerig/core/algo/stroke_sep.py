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
__version__ = '0.3.1'

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

def merge_nearby_forks(forks, concavity_map, merge_radius=30.0):
	"""Merge nearby fork nodes into logical junctions.

	At oblique crossings (X, N, Z), the MAT produces multiple fork nodes
	within a few units of each other. These should be treated as a single
	junction with combined concavities.

	Args:
		forks: list of MATNode fork nodes
		concavity_map: dict {id(node) -> [concavities]} from compute_ligatures
		merge_radius: maximum distance to merge forks

	Returns:
		list of (representative_fork, combined_concavities) tuples
	"""
	if not forks:
		return []

	used = set()
	merged = []

	for i, f in enumerate(forks):
		if i in used:
			continue

		# Find all forks within merge_radius
		cluster = [f]
		cluster_indices = {i}
		for j, g in enumerate(forks):
			if j in used or j == i:
				continue
			dist = math.hypot(f.x - g.x, f.y - g.y)
			if dist < merge_radius:
				cluster.append(g)
				cluster_indices.add(j)

		used.update(cluster_indices)

		# Pick the fork with the largest radius as representative
		rep = max(cluster, key=lambda n: n.radius)

		# Combine concavities from all forks in cluster, deduplicate
		combined = []
		seen_positions = set()
		for node in cluster:
			for conc in concavity_map.get(id(node), []):
				pos = (round(conc[2], 1), round(conc[3], 1))
				if pos not in seen_positions:
					seen_positions.add(pos)
					combined.append(conc)

		merged.append((rep, combined))

	return merged


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


# - Path-based Ligatures (v2) ----------

class Ligature(object):
	"""A connected subgraph of M whose ribs terminate in a CSF's contact region.

	A ligature is the "glue" between the outline boundary of a concavity and
	the interior medial axis. Its nodes are exactly those M vertices whose
	inscribed circles intersect the CSF's contact arc (within tolerance).

	Attributes:
		csf:      the concave CSF this ligature connects to
		nodes:    list of MATNode ordered along M from contact-side toward forks
		forks:    list of MATNode that are forks and lie within this ligature
		node_ids: frozenset of id(node) for fast membership tests
	"""

	def __init__(self, csf, nodes):
		self.csf      = csf
		self.nodes    = nodes
		self.forks    = [n for n in nodes if n.is_fork]
		self.node_ids = frozenset(id(n) for n in nodes)

	@property
	def start(self):
		return self.nodes[0] if self.nodes else None

	@property
	def end(self):
		return self.nodes[-1] if self.nodes else None

	def __contains__(self, node):
		return id(node) in self.node_ids

	def __repr__(self):
		return '<Ligature: csf={} nodes={} forks={}>'.format(
			self.csf, len(self.nodes), len(self.forks))


def _rib_touches_contact(node, contact_region, tol):
	"""Return True if node's inscribed circle reaches any point in contact_region.

	The "rib" from an M vertex is the shortest line from the vertex to the
	outline (magnitude = node.radius).  If any outline sample in the contact
	region lies within node.radius + tol of the vertex, the rib terminates
	inside the contact region.

	Args:
		node:           MATNode
		contact_region: list of (x, y) from CSF.contact_region
		tol:            tolerance in font units

	Returns:
		bool
	"""
	limit_sq = (node.radius + tol) ** 2
	nx, ny   = node.x, node.y
	for cx, cy in contact_region:
		if (nx - cx) ** 2 + (ny - cy) ** 2 <= limit_sq:
			return True
	return False


def _bfs_connected(seed_ids, graph):
	"""BFS over graph.nodes restricted to a seed id-set, return connected component.

	Builds a subgraph adjacency from the full MAT graph, then BFS from the
	node in seed_ids whose id is smallest (deterministic starting point).

	Args:
		seed_ids: set of id(node) that are candidate ligature members
		graph:    MATGraph

	Returns:
		list of MATNode — the largest connected component within seed_ids
	"""
	# Build id → node map and restricted adjacency within seed
	id_to_node = {id(n): n for n in graph.nodes if id(n) in seed_ids}
	if not id_to_node:
		return []

	adjacency = defaultdict(list)
	for node in id_to_node.values():
		for nb in node.neighbors:
			if id(nb) in seed_ids:
				adjacency[id(node)].append(id(nb))

	# BFS from each unvisited seed; keep largest component
	visited   = set()
	best      = []
	for start_id in id_to_node:
		if start_id in visited:
			continue
		comp = []
		queue = [start_id]
		visited.add(start_id)
		while queue:
			cur_id  = queue.pop(0)
			comp.append(id_to_node[cur_id])
			for nb_id in adjacency[cur_id]:
				if nb_id not in visited:
					visited.add(nb_id)
					queue.append(nb_id)
		if len(comp) > len(best):
			best = comp

	return best


def _order_ligature_nodes(nodes, csf):
	"""Order ligature nodes along M, starting nearest the CSF extremum.

	Uses BFS over the restricted subgraph, starting from the node whose
	center is closest to csf.extremum. This gives a natural order from
	"contact side" outward toward internal forks.

	Args:
		nodes: list of MATNode (unordered)
		csf:   CSF whose extremum anchors the ordering

	Returns:
		list of MATNode in BFS order from the extremum-nearest node
	"""
	if not nodes:
		return []

	ex_x, ex_y = csf.extremum
	seed = min(nodes, key=lambda n: math.hypot(n.x - ex_x, n.y - ex_y))

	node_ids = {id(n) for n in nodes}
	id_to_node = {id(n): n for n in nodes}

	ordered  = []
	visited  = {id(seed)}
	queue    = [seed]
	while queue:
		cur = queue.pop(0)
		ordered.append(cur)
		for nb in cur.neighbors:
			if id(nb) in node_ids and id(nb) not in visited:
				visited.add(id(nb))
				queue.append(nb)

	return ordered


def compute_ligatures_v2(graph, csfs, tol=5.0):
	"""Compute path-based ligatures from concave CSFs (Berio et al. §4.3).

	For each concave CSF, finds every M vertex whose inscribed circle's rib
	terminates within the CSF's contact region (within tolerance `tol`).
	Those vertices form a connected subgraph of M — the ligature for that CSF.

	This replaces the older point-distance `compute_ligatures()` with a
	richer structure that:
	  - Stores the ordered list of M nodes in the ligature
	  - Identifies which forks lie within the ligature
	  - Supports fast node membership tests via frozenset of ids
	  - Enables protruding direction computation (see `protruding_direction`)

	Args:
		graph: MATGraph from compute_mat()
		csfs:  list of CSF objects from compute_csfs() — only concave ones used
		tol:   rib-contact tolerance in font units (default 5.0)

	Returns:
		list of Ligature objects, one per concave CSF that has at least one node
	"""
	ligatures = []
	concave_csfs = [c for c in csfs if c.csf_type == 'concave']

	for csf in concave_csfs:
		if not csf.contact_region:
			continue

		# 1. Collect all M nodes whose disk reaches the contact region
		seed_ids = set()
		for node in graph.nodes:
			if _rib_touches_contact(node, csf.contact_region, tol):
				seed_ids.add(id(node))

		if not seed_ids:
			continue

		# 2. Largest connected component within the MAT graph
		connected = _bfs_connected(seed_ids, graph)
		if not connected:
			continue

		# 3. Order nodes from contact side outward
		ordered = _order_ligature_nodes(connected, csf)

		ligatures.append(Ligature(csf, ordered))

	return ligatures


def ligature_node_set(ligatures):
	"""Return a set of id(node) for all nodes across all ligatures.

	Used for fast membership test: is a given M node inside ANY ligature?

	Args:
		ligatures: list of Ligature objects

	Returns:
		set of int (id values)
	"""
	result = set()
	for lig in ligatures:
		result.update(lig.node_ids)
	return result


def protruding_direction(fork, branch_neighbor, all_ligature_node_ids):
	"""Compute protruding direction P(b, f, C) for branch b at fork f.

	Walk along branch b (starting at fork f toward branch_neighbor).
	Skip over nodes that belong to any ligature (they are "shared" outline
	territory, not the stroke body). The FIRST non-ligature node's position
	relative to the last ligature node gives the protruding direction.

	If the entire branch is covered by ligatures, fall back to the tangent
	at the fork itself (direction toward branch_neighbor).

	Args:
		fork:                  MATNode — the fork to start from
		branch_neighbor:       MATNode — first step into branch b
		all_ligature_node_ids: set of int — union of all ligature node ids
		                       (from ligature_node_set())

	Returns:
		(dx, dy) — unit vector in the protruding direction
	"""
	prev, cur = fork, branch_neighbor
	last_lig  = fork   # last node still inside a ligature

	while cur is not None:
		if id(cur) not in all_ligature_node_ids:
			# First non-ligature node — tangent from last_lig to cur
			dx = cur.x - last_lig.x
			dy = cur.y - last_lig.y
			mag = math.hypot(dx, dy)
			if mag > _EPS:
				return (dx / mag, dy / mag)
			break

		last_lig = cur

		if cur.is_terminal:
			break

		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt:
			break
		if cur.is_fork and cur is not fork:
			# At an inner fork: continue toward the neighbor not coming from prev
			# that has the smallest disk (deepest into the junction)
			nxt.sort(key=lambda n: n.radius)

		prev, cur = cur, nxt[0]

	# Fallback: tangent at fork toward branch_neighbor
	dx = branch_neighbor.x - fork.x
	dy = branch_neighbor.y - fork.y
	mag = math.hypot(dx, dy)
	if mag > _EPS:
		return (dx / mag, dy / mag)
	return (1.0, 0.0)


# - Sector-based concavity-to-fork assignment (§4.4) ----------

class SectorAssignment(object):
	"""Concavity assignments for a single fork, organised by sector.

	A degree-3 fork has 3 sectors — one between each pair of branches.
	Sector i lies between branch[i] and branch[(i+1) % 3] (CCW order).

	Attributes:
		fork:         MATNode — the fork
		branches:     list of (angle_deg, neighbor_node) sorted CCW
		sectors:      list of 3 (angle_lo, angle_hi, midpoint_angle) triples
		assignments:  list of 3 entries, each None or CSF — best CSF per sector
		scores:       list of 3 float — radius-standardized distances (lower = closer)
	"""

	def __init__(self, fork, branches):
		self.fork        = fork
		self.branches    = branches      # [(angle, node), ...] sorted CCW, len >= 3
		self.sectors     = _compute_sectors(fork, branches)
		self.assignments = [None, None, None]
		self.scores      = [float('inf'), float('inf'), float('inf')]

	def assign(self, sector_idx, csf, score):
		"""Assign csf to sector if it scores better than the current occupant."""
		if score < self.scores[sector_idx]:
			self.assignments[sector_idx] = csf
			self.scores[sector_idx]      = score

	@property
	def assigned_csfs(self):
		"""List of (sector_idx, CSF) for all occupied sectors."""
		return [(i, c) for i, c in enumerate(self.assignments) if c is not None]

	def __repr__(self):
		n_assigned = sum(1 for c in self.assignments if c is not None)
		return '<SectorAssignment fork=({:.0f},{:.0f}) sectors={} assigned={}>'.format(
			self.fork.x, self.fork.y, len(self.sectors), n_assigned)


def _compute_sectors(fork, branches):
	"""Return 3 (angle_lo, angle_hi, angle_mid) tuples (degrees, CCW order).

	branches is a list of (angle_deg, node) pairs sorted CCW.  Each sector
	spans the angular gap between two consecutive branches, measured from
	the fork center.
	"""
	n = len(branches)
	sectors = []
	for i in range(n):
		a0 = branches[i][0]
		a1 = branches[(i + 1) % n][0]
		# Angular gap CCW from a0 to a1
		gap = (a1 - a0) % 360.0
		a_mid = (a0 + gap / 2.0) % 360.0
		sectors.append((a0, (a0 + gap) % 360.0, a_mid))
	return sectors


def _angle_in_sector(angle_deg, sector):
	"""Return True if angle_deg falls inside the sector (CCW arc from lo to hi)."""
	lo, hi, _mid = sector
	a = angle_deg % 360.0
	if lo <= hi:
		return lo <= a <= hi
	# Wraps through 0
	return a >= lo or a <= hi


def _geodesic_path(fork, csf, graph, max_hops=200):
	"""Walk M from fork toward csf.extremum via shortest BFS path.

	Returns (path_length, path_nodes) where path_length is the total
	Euclidean length of the walked edges.  Returns (inf, []) if no path
	is found within max_hops.

	Stops early if another fork with overlapping disk is encountered.
	"""
	ex_x, ex_y = csf.extremum

	# BFS with cumulative path length
	# State: (total_dist, node, path_nodes)
	import heapq
	heap  = [(0.0, id(fork), fork, [fork])]
	visited = {id(fork)}

	while heap:
		dist, _nid, node, path = heapq.heappop(heap)

		if len(path) > max_hops:
			break

		# Check if we've reached the concavity's vicinity
		d_to_ex = math.hypot(node.x - ex_x, node.y - ex_y)
		if d_to_ex <= node.radius + 10.0:
			return dist, path

		# Disambiguation rule 2: reached another fork with overlapping disk → stop
		if node is not fork and node.is_fork:
			d_ff = math.hypot(node.x - fork.x, node.y - fork.y)
			if d_ff < fork.radius + node.radius:
				return dist, path

		for nb in node.neighbors:
			if id(nb) in visited:
				continue
			visited.add(id(nb))
			edge_len = math.hypot(nb.x - node.x, nb.y - node.y)
			heapq.heappush(heap, (dist + edge_len, id(nb), nb, path + [nb]))

	return float('inf'), []


def _path_crosses_convex_rib(path, convex_csfs, tol=8.0):
	"""Return True if any path node is inside a convex CSF's inscribed disk.

	Disambiguation rule 1 (§4.4.1): if the geodesic from the fork to the
	concavity passes through a convex CSF's terminal disk, the concavity is
	part of a smooth bend, not a junction.  We approximate this by checking
	whether any path node's position is within the convex disk (radius +tol).
	"""
	for node in path[1:]:  # skip the fork itself
		for ccsf in convex_csfs:
			cx, cy, cr = ccsf.disk_center[0], ccsf.disk_center[1], ccsf.disk_radius
			if math.hypot(node.x - cx, node.y - cy) < cr + tol:
				return True
	return False


def assign_concavities_to_forks(graph, csfs, ligatures=None, max_hops=200):
	"""Assign each concave CSF to at most one sector per eligible fork (§4.4).

	Algorithm:
	  For every degree-3+ fork f:
	    1. Compute branch directions and angular sectors.
	    2. For each concave CSF c:
	       a. Compute the angle from f to c.extremum.
	       b. Find which sector it falls into (if any).
	       c. Walk the geodesic path through M from f toward c.extremum.
	       d. Apply disambiguation rules (convex rib, fork overlap).
	       e. Compute radius-standardized distance d_f = 2p / r².
	       f. Assign c to the sector if it beats the current occupant.

	Forks with degree > 3 are handled by treating every consecutive triple
	of branches as a potential sector set (same formula, more sectors).

	Args:
		graph:     MATGraph from compute_mat()
		csfs:      list of CSF from compute_csfs()
		ligatures: list of Ligature (optional, unused here but kept for API compat)
		max_hops:  BFS hop limit for geodesic search (default 200)

	Returns:
		dict: {id(fork) -> SectorAssignment}
	"""
	concave_csfs = [c for c in csfs if c.csf_type == 'concave']
	convex_csfs  = [c for c in csfs if c.csf_type == 'convex']

	if not concave_csfs:
		return {}

	result = {}

	for fork in graph.forks():
		# Branch directions sorted CCW (atan2, standard math convention)
		branches = []
		for nb in fork.neighbors:
			dx = nb.x - fork.x
			dy = nb.y - fork.y
			# Walk a few hops for a more stable direction estimate
			prev, cur = fork, nb
			for _ in range(3):
				nxt = [n for n in cur.neighbors if n is not prev]
				if not nxt or cur.is_fork or cur.is_terminal:
					break
				prev, cur = cur, nxt[0]
			dx = cur.x - fork.x
			dy = cur.y - fork.y
			angle = math.degrees(math.atan2(dy, dx)) % 360.0
			branches.append((angle, nb))

		branches.sort(key=lambda x: x[0])

		if len(branches) < 3:
			continue

		# For degree > 3: use only the 3 most-separated branches (largest gaps)
		if len(branches) > 3:
			gaps = []
			n = len(branches)
			for i in range(n):
				gap = (branches[(i+1) % n][0] - branches[i][0]) % 360.0
				gaps.append((gap, i))
			# Drop the branch that makes the smallest gap until we have 3
			while len(branches) > 3:
				gaps.sort()
				drop_idx = gaps[0][1]
				branches.pop(drop_idx)
				gaps = []
				n = len(branches)
				for i in range(n):
					gap = (branches[(i+1) % n][0] - branches[i][0]) % 360.0
					gaps.append((gap, i))

		sa = SectorAssignment(fork, branches)

		for csf in concave_csfs:
			ex_x, ex_y = csf.extremum

			# Angle from fork to concavity extremum
			angle_to_c = math.degrees(math.atan2(ex_y - fork.y, ex_x - fork.x)) % 360.0

			# Find which sector contains this angle
			sector_idx = None
			for si, sector in enumerate(sa.sectors):
				if _angle_in_sector(angle_to_c, sector):
					sector_idx = si
					break

			if sector_idx is None:
				continue

			# Geodesic path from fork to concavity
			path_len, path = _geodesic_path(fork, csf, graph, max_hops=max_hops)
			if path_len == float('inf'):
				continue

			# Disambiguation rule 1: convex rib on path → smooth bend, skip
			if _path_crosses_convex_rib(path, convex_csfs):
				continue

			# Radius-standardized distance d_f = 2p / r²
			r = csf.disk_radius
			if r < _EPS:
				continue
			score = 2.0 * path_len / (r * r)

			sa.assign(sector_idx, csf, score)

		if any(c is not None for c in sa.assignments):
			result[id(fork)] = sa

	return result


def fork_concavity_map(sector_assignments):
	"""Flatten sector assignments into a simple fork_id → [CSF] dict.

	Convenience wrapper for code that needs a flat concavity list per fork
	(e.g. junction classification, cut solving).

	Args:
		sector_assignments: dict from assign_concavities_to_forks()

	Returns:
		dict: {id(fork) -> list of CSF}
	"""
	result = {}
	for fork_id, sa in sector_assignments.items():
		csfs_for_fork = [c for c in sa.assignments if c is not None]
		if csfs_for_fork:
			result[fork_id] = csfs_for_fork
	return result


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

	Concavity-first approach (per Adobe StrokeStyles paper):
	- Concavities ARE the cut endpoints. They sit at the inner corners
	  of junctions where strokes meet.
	- 2 concavities → 1 cut connecting them
	- 3 concavities → pair best 2 for 1 cut (Y-junction)
	- 4 concavities → pair into 2 parallel cuts (X-junction)
	- 1 concavity → project from concavity across stroke to opposite edge
	- 0 concavities → no cut (taper/stroke end)

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
		return _pair_concavities_parallel(fork_node, fork_concavities)

	elif n == 3:
		# Y-junction: find best pair for 1 cut, optionally 2
		return _pair_concavities_y_junction(fork_node, fork_concavities)

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


def _pair_concavities_y_junction(fork_node, concavities):
	"""For Y-junctions with 3 concavities, produce 1 or 2 cuts.

	Strategy: find the pair of concavities that are closest together
	(on the same side of the diverging stroke), they define 1 cut.
	The remaining concavity can optionally pair with the fork center
	for a second cut.
	"""
	if len(concavities) < 3:
		return []

	# Find the pair with shortest distance — they're on the same
	# side of one stroke, forming the cut across the diverging branch
	best_pair = None
	best_dist = float('inf')
	for i in range(len(concavities)):
		for j in range(i + 1, len(concavities)):
			ci, cj = concavities[i], concavities[j]
			d = math.hypot(ci[2] - cj[2], ci[3] - cj[3])
			if d < best_dist:
				best_dist = d
				best_pair = (i, j)

	cuts = []
	if best_pair and best_dist > 5.0:
		ci = concavities[best_pair[0]]
		cj = concavities[best_pair[1]]
		cuts.append(((ci[2], ci[3]), (cj[2], cj[3])))

	# The remaining concavity defines a second cut with its nearest
	# partner from the pair
	remaining = [k for k in range(3) if k not in best_pair]
	if remaining:
		cr = concavities[remaining[0]]
		# Pair with the closer of the two already-used concavities
		d0 = math.hypot(cr[2] - concavities[best_pair[0]][2],
						cr[3] - concavities[best_pair[0]][3])
		d1 = math.hypot(cr[2] - concavities[best_pair[1]][2],
						cr[3] - concavities[best_pair[1]][3])
		partner = concavities[best_pair[0]] if d0 > d1 else concavities[best_pair[1]]
		# Use the farther one (it's across the stroke from the remaining)
		partner = concavities[best_pair[1]] if d0 > d1 else concavities[best_pair[0]]
		pdist = math.hypot(cr[2] - partner[2], cr[3] - partner[3])
		if pdist > 5.0:
			cuts.append(((cr[2], cr[3]), (partner[2], partner[3])))

	return cuts


def _project_from_concavity(fork_node, concavity, contours):
	"""Project from a single concavity point across the stroke.

	The concavity is on the outline. We project a ray from it through
	the fork center to find the opposite outline edge.
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

	from typerig.core.objects.point import Point
	from typerig.core.objects.line import Line

	ray_line = Line(Point(cx, cy), Point(*ray_end))
	origin = (cx, cy)

	pt = _intersect_ray_with_contours(ray_line, origin, contours,
									  max_dist=fork_node.radius * 4.0)
	if pt:
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
				perp_angle = (remaining_angle + 90) % 360
				# Try axis-snapped angle first (Gothic preference), fall back to original
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
	ray_len = fork_node.radius * 4
	max_dist = fork_node.radius * 4.0  # allow wider reach for corner forks
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

def _is_real_junction(fork, stroke_paths=None, concavity_count=0):
	"""Check if a fork is a real junction vs taper artifact.

	Concavity-first approach: a fork with concavities IS a real junction.
	Concavities appear at the inner corners of stroke meetings.
	Tapers (stroke ends) have no concavities.
	"""
	# If this fork has associated concavities, it's a real junction
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
