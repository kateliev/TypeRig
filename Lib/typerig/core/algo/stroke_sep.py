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

from typerig.core.algo.mat import compute_mat, compute_exterior_mat, MATGraph, MATNode
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node
from typerig.core.func.geometry import line_intersect

# - Init -------------------------------
__version__ = '0.4.0'

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


# - Link Pipeline (§5) ----------

class Link(object):
	"""A candidate stroke-crossing line segment between two concave CSFs.

	Attributes:
		csf1, csf2:        the two concave CSFs whose extrema are the endpoints
		p1, p2:            (x, y) endpoint positions (= csf1.extremum, csf2.extremum)
		flow:              (fx, fy) unit flow vector = -(n1 + n2) / |...|
		link_type:         'normal' | 'compound' | None (unvalidated)
		fork:              MATNode — the fork that owns this link (normal links only)
		protruding_branch: MATNode — fork neighbor that is the protruding branch
		salience:          float — S(ℓ) = exp(...) + Φ
		good_continuation: float — Φ(ε1, ε2) alone
		valid:             bool — passed flow-vs-protruding-direction test
	"""

	__slots__ = (
		'csf1', 'csf2', 'p1', 'p2', 'flow',
		'link_type', 'fork', 'protruding_branch',
		'salience', 'good_continuation', 'valid',
	)

	def __init__(self, csf1, csf2):
		self.csf1 = csf1
		self.csf2 = csf2
		self.p1   = csf1.extremum
		self.p2   = csf2.extremum

		n1 = csf1.inward_normal or (0.0, 0.0)
		n2 = csf2.inward_normal or (0.0, 0.0)
		fx = -(n1[0] + n2[0])
		fy = -(n1[1] + n2[1])
		mag = math.hypot(fx, fy)
		self.flow = (fx / mag, fy / mag) if mag > _EPS else (1.0, 0.0)

		self.link_type         = None
		self.fork              = None
		self.protruding_branch = None
		self.salience          = 0.0
		self.good_continuation = 0.0
		self.valid             = False

	@property
	def length(self):
		return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])

	def __repr__(self):
		return '<Link: {} {} {} ({:.0f},{:.0f})<->({:.0f},{:.0f}) S={:.3f}>'.format(
			'VALID' if self.valid else 'invalid',
			self.link_type or '?',
			'n/a' if self.fork is None else 'f({:.0f},{:.0f})'.format(
				self.fork.x, self.fork.y),
			self.p1[0], self.p1[1], self.p2[0], self.p2[1],
			self.salience)


# ── A: inside-glyph segment test ──────────────────────────────────────────────

def _seg_intersects_seg(ax, ay, bx, by, cx, cy, dx, dy):
	"""Return True if open segment AB strictly intersects open segment CD."""
	def _cross2(ux, uy, vx, vy):
		return ux * vy - uy * vx

	rx = bx - ax;  ry = by - ay
	sx = dx - cx;  sy = dy - cy
	denom = _cross2(rx, ry, sx, sy)

	if abs(denom) < _EPS:
		return False  # parallel / collinear

	qax = cx - ax;  qay = cy - ay
	t = _cross2(qax, qay, sx, sy) / denom
	u = _cross2(qax, qay, rx, ry) / denom

	return 1e-6 < t < 1.0 - 1e-6 and 1e-6 < u < 1.0 - 1e-6


def _link_inside_glyph(p1, p2, contours, n_interior_checks=4):
	"""Return True if segment p1→p2 lies entirely inside the glyph outline.

	Strategy:
	  1. Reject if the segment crosses any contour edge.
	  2. Check n_interior_checks evenly-spaced interior samples with ray casting.
	     All must be inside the glyph.  This catches links that fit between
	     two contour boundary crossings (e.g. inside a letter counter).
	"""
	from typerig.core.algo.mat import _SpatialGrid, sample_contour as _sc

	x1, y1 = p1
	x2, y2 = p2

	# Build a quick polyline representation of each contour for intersection tests
	for contour in contours:
		pts = _sc(contour, step=4.0)
		n = len(pts)
		for i in range(n):
			ax, ay = pts[i]
			bx, by = pts[(i + 1) % n]
			if _seg_intersects_seg(x1, y1, x2, y2, ax, ay, bx, by):
				return False

	# Interior sampling via _SpatialGrid.is_inside (ray casting)
	polylines = []
	for contour in contours:
		pts = _sc(contour, step=4.0)
		if pts:
			polylines.append(pts)

	if not polylines:
		return True

	cell = max(20.0, math.hypot(x2 - x1, y2 - y1) / 5.0)
	grid = _SpatialGrid(polylines, cell_size=cell)

	for k in range(1, n_interior_checks + 1):
		t = k / float(n_interior_checks + 1)
		mx = x1 + t * (x2 - x1)
		my = y1 + t * (y2 - y1)
		if not grid.is_inside(mx, my):
			return False

	return True


# ── B: good-continuation / association fields (§5.3, Appendix B) ──────────────

# Paper constants (Appendix B)
_KAPPA1 = 0.27   # cocircularity concentration
_KAPPA2 = 0.47   # curvature-deviation concentration


def good_continuation(csf1, csf2, sigma):
	"""Compute association-field good-continuation Φ(ε₁, ε₂) (§5.3 / App B).

	Φ = Φ_a · Φ_r

	Φ_r = exp(-d² / (2σ²))  — Gaussian distance decay

	Φ_a = cosh(A·cos(β/2) + B·cos(α - β/2)) / cosh(A + B)

	  The cosh-ratio normalization maps Φ_a ∈ (0, 1]:
	  - Value 1.0 when β = 0 and α = 0 (perfect cocircularity / collinearity)
	  - Decreases as the two tangents deviate from a smooth circular arc

	  where:
	    d    = Euclidean distance between the two extrema
	    β    = signed angle from τ₁ to the connecting line direction
	           (measures deviation from collinearity on the ε₁ side)
	    α    = signed angle between the two tangent orientations τ₁ and τ₂
	           (measures total orientation difference)
	    A    = 4·κ₁·κ₂   — cocircularity concentration scale
	    B    = κ₁·κ₂    — curvature-deviation concentration scale

	  Paper constants: κ₁ = 0.27 (cocircularity), κ₂ = 0.47 (curvature deviation).
	  With these values A ≈ 0.508, B ≈ 0.127, so max_arg = A+B ≈ 0.635 and
	  cosh-ratio normalization keeps Φ_a ∈ (0, 1].

	For each concavity we pick the tangent from its tangent_pair that is most
	orthogonal to the link direction (most "edge-like" as seen from the link).

	Args:
		csf1, csf2: CSF objects (must have tangent_pair and inward_normal set)
		sigma:      Gaussian spread in font units (= 2 × max M non-ligature radius)

	Returns:
		float in [0, 1] — higher = better continuation
	"""
	x1, y1 = csf1.extremum
	x2, y2 = csf2.extremum
	d = math.hypot(x2 - x1, y2 - y1)

	if d < _EPS or sigma < _EPS:
		return 0.0

	# Φ_r — Gaussian distance decay
	phi_r = math.exp(-(d * d) / (2.0 * sigma * sigma))

	# Select representative tangent at each endpoint: most orthogonal to link
	lx = (x2 - x1) / d
	ly = (y2 - y1) / d

	def _best_tangent(csf):
		if csf.tangent_pair is None:
			n = csf.inward_normal or (0.0, 1.0)
			return (-n[1], n[0])
		t0, t1 = csf.tangent_pair
		d0 = abs(t0[0] * lx + t0[1] * ly)
		d1 = abs(t1[0] * lx + t1[1] * ly)
		return t0 if d0 <= d1 else t1

	tx1, ty1 = _best_tangent(csf1)
	tx2, ty2 = _best_tangent(csf2)

	# β: signed angle from τ₁ to the link direction
	beta  = math.atan2(lx * ty1 - ly * tx1, lx * tx1 + ly * ty1)

	# α: signed angle between τ₁ and τ₂
	alpha = math.atan2(tx1 * ty2 - ty1 * tx2, tx1 * tx2 + ty1 * ty2)

	# A = 4·κ₁·κ₂, B = κ₁·κ₂ — concentrations as direct multipliers.
	# With κ₁ = 0.27, κ₂ = 0.47: A ≈ 0.508, B ≈ 0.127, max_arg ≈ 0.635.
	# cosh(max_arg) ≈ 1.20 — normalization stays in [1, 1.20], so the ratio
	# Φ_a ∈ (0, 1] with value 1 for perfect cocircularity/collinearity.
	A = 4.0 * _KAPPA1 * _KAPPA2
	B = _KAPPA1 * _KAPPA2

	arg     = A * math.cos(beta / 2.0) + B * math.cos(alpha - beta / 2.0)
	max_arg = A + B

	phi_a = math.cosh(arg) / math.cosh(max_arg)

	return phi_a * phi_r


# ── C: branch salience σ(b, f) §4.1.2 ────────────────────────────────────────

def branch_salience(fork, branch_neighbor):
	"""Compute σ(b, f) = ℓ / (ℓ - ρ) (Berio et al. §4.1.2).

	ℓ = arc length of the branch (walk to next terminal/fork)
	ρ = radius of the fork disk

	A branch is salient (protruding) if σ > τ_σ = 2.3 (paper default).
	Non-salient branches are short tapers / caps at stroke ends.
	"""
	rho = fork.radius
	prev, cur = fork, branch_neighbor
	arc_len = 0.0
	while True:
		arc_len += math.hypot(cur.x - prev.x, cur.y - prev.y)
		if cur.is_terminal or cur.is_fork:
			break
		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt:
			break
		prev, cur = cur, nxt[0]

	denom = arc_len - rho
	if denom < _EPS:
		return float('inf')  # very short branch → salient
	return arc_len / denom


_TAU_SIGMA = 2.3  # salience threshold (paper default)


# ── D: link generation and validation ─────────────────────────────────────────

def _flow_projection(link, fork, branch_nb, all_lig_ids):
	"""Compute F(ℓ) · P(b, f, C) — used for normal-link validation (Eq. 2)."""
	p = protruding_direction(fork, branch_nb, all_lig_ids)
	return link.flow[0] * p[0] + link.flow[1] * p[1]


def _sector_idx_for_csf(sa, csf):
	"""Return the sector index that csf is assigned to in sa, or None."""
	for i, c in enumerate(sa.assignments):
		if c is csf:
			return i
	return None


def _protruding_branch_for_normal_link(link, fork, sa, all_lig_ids):
	"""For a normal link at fork, find the branch delimiting BOTH sectors.

	Both concavity sectors share exactly one branch boundary (the one between
	their two sectors). That shared branch is the protruding branch.

	Returns (branch_neighbor, flow_projection) or (None, -inf).
	"""
	si1 = _sector_idx_for_csf(sa, link.csf1)
	si2 = _sector_idx_for_csf(sa, link.csf2)
	if si1 is None or si2 is None:
		return None, float('-inf')

	n_sectors = len(sa.sectors)

	# The shared boundary branch between sector si1 and si2.
	# Sector i spans branches[i] → branches[i+1].
	# Boundary i separates sector (i-1) from sector i → branch index = i.
	# We want the boundary that is shared by both sectors si1 and si2.
	# Sectors are CCW: sector i borders branch i (left) and branch i+1 (right).
	# The boundary branch index between sector A and sector B is:
	#   B if B = (A + 1) % n   →  branch index = B
	#   A if A = (B + 1) % n   →  branch index = A

	# Collect all shared boundary indices
	shared = []
	for bi in range(n_sectors):
		# Branch bi borders sector (bi-1)%n on left and sector bi on right
		left_sector  = (bi - 1) % n_sectors
		right_sector = bi
		if {left_sector, right_sector} == {si1, si2}:
			shared.append(bi)

	best_nb   = None
	best_proj = float('-inf')

	for bi in shared:
		_, nb = sa.branches[bi % len(sa.branches)]
		proj = _flow_projection(link, fork, nb, all_lig_ids)
		if proj > best_proj:
			best_proj = proj
			best_nb   = nb

	return best_nb, best_proj


def generate_links(sector_assignments, contours, graph, ligatures,
				   min_length=5.0):
	"""Generate, validate, and score all candidate links (§5.1–5.3).

	Pass 1 — generation:
	  All pairs of concave CSFs that are both assigned to forks.
	  Segment must be entirely inside the glyph (no contour crossings,
	  all interior samples inside via ray casting).

	Pass 2 — validation (normal links):
	  A link is a normal link if ≥1 fork owns BOTH concavities.
	  The protruding branch is the one on the shared sector boundary.
	  Validate via F · P > 0.

	Pass 3 — validation (compound links):
	  If no normal link: check whether the link crosses ≥2 branches
	  from different forks, all non-salient, with overlapping disks.

	Pass 4 — salience:
	  S = exp(-(r1+r2)/(2·r_max)) + Φ
	  σ for Φ = 2 × max non-ligature fork radius.

	Args:
		sector_assignments: dict {id(fork) -> SectorAssignment}
		contours:           glyph contours (for inside-glyph test)
		graph:              MATGraph (for branch salience + protruding direction)
		ligatures:          list of Ligature (for ligature node set)
		min_length:         minimum link length in font units (default 5.0)

	Returns:
		list of Link objects with valid=True, sorted by descending salience
	"""
	# ── collect all assigned concavities ──────────────────────────────
	assigned_csfs = set()
	for sa in sector_assignments.values():
		for csf in sa.assignments:
			if csf is not None:
				assigned_csfs.add(id(csf))

	# Keep the actual CSF objects for pairing
	csf_by_id = {}
	for sa in sector_assignments.values():
		for csf in sa.assignments:
			if csf is not None:
				csf_by_id[id(csf)] = csf
	unique_csfs = list(csf_by_id.values())

	if len(unique_csfs) < 2:
		return []

	# ── build per-fork lookup: which two CSFs are co-assigned ─────────
	# fork_id → set of id(csf) assigned to that fork
	fork_csf_ids = {}
	for fork_id, sa in sector_assignments.items():
		ids = frozenset(id(c) for c in sa.assignments if c is not None)
		if ids:
			fork_csf_ids[fork_id] = ids

	# ── ligature node set for protruding direction ─────────────────────
	all_lig_ids = ligature_node_set(ligatures)

	# ── σ for good-continuation: 2 × max non-ligature fork radius ─────
	lig_fork_ids = {id(n) for lig in ligatures for n in lig.forks}
	non_lig_radii = [f.radius for f in graph.forks() if id(f) not in lig_fork_ids]
	sigma_phi = 2.0 * max(non_lig_radii) if non_lig_radii else 50.0

	# ── r_max for salience denominator ────────────────────────────────
	all_radii = [csf.disk_radius for csf in unique_csfs]
	r_max = max(all_radii) if all_radii else 1.0

	# ── generate + test all pairs ──────────────────────────────────────
	valid_links = []
	n = len(unique_csfs)

	for i in range(n):
		for j in range(i + 1, n):
			c1 = unique_csfs[i]
			c2 = unique_csfs[j]

			# Skip pairs on the same contour at nearly the same position
			if (c1.contour_idx == c2.contour_idx and
					math.hypot(c1.extremum[0] - c2.extremum[0],
							   c1.extremum[1] - c2.extremum[1]) < min_length):
				continue

			# Inside-glyph test
			if not _link_inside_glyph(c1.extremum, c2.extremum, contours):
				continue

			link = Link(c1, c2)
			if link.length < min_length:
				continue

			# ── normal link validation ─────────────────────────────────
			validated = False
			for fork_id, csf_ids in fork_csf_ids.items():
				if id(c1) in csf_ids and id(c2) in csf_ids:
					sa   = sector_assignments[fork_id]
					fork = sa.fork
					nb, proj = _protruding_branch_for_normal_link(
						link, fork, sa, all_lig_ids)
					if nb is not None and proj > 0.0:
						link.link_type         = 'normal'
						link.fork              = fork
						link.protruding_branch = nb
						link.valid             = True
						validated              = True
						break  # first valid assignment suffices

			# ── compound link validation ───────────────────────────────
			if not validated:
				validated = _try_compound_link(link, graph, sector_assignments,
											   all_lig_ids)

			if not link.valid:
				continue

			# ── good continuation ──────────────────────────────────────
			phi = good_continuation(c1, c2, sigma_phi)
			link.good_continuation = phi

			# ── salience ──────────────────────────────────────────────
			r1, r2 = c1.disk_radius, c2.disk_radius
			link.salience = math.exp(-(r1 + r2) / (2.0 * r_max)) + phi

			valid_links.append(link)

	valid_links.sort(key=lambda l: l.salience, reverse=True)
	return valid_links


def _try_compound_link(link, graph, sector_assignments, all_lig_ids):
	"""Test compound-link condition: ≥2 non-salient branches from different forks
	with overlapping disks crossed by the link segment (§5.1.2).

	Marks link.link_type='compound' and link.valid=True if condition met.
	Returns True on success.
	"""
	p1x, p1y = link.p1
	p2x, p2y = link.p2

	# Walk every branch in the graph; check if the link segment crosses it
	crossed_forks = {}  # fork_id → (fork, branch_nb, salience_value)

	for fork in graph.forks():
		for nb in fork.neighbors:
			# Branch segment: from fork toward nb (a few hops for direction)
			prev, cur = fork, nb
			branch_pts = [(fork.x, fork.y)]
			for _ in range(8):
				branch_pts.append((cur.x, cur.y))
				if cur.is_terminal or cur.is_fork:
					break
				nxt = [n for n in cur.neighbors if n is not prev]
				if not nxt:
					break
				prev, cur = cur, nxt[0]

			# Check if link crosses any edge of this branch poly
			crossed = False
			for k in range(len(branch_pts) - 1):
				ax, ay = branch_pts[k]
				bx, by = branch_pts[k + 1]
				if _seg_intersects_seg(p1x, p1y, p2x, p2y, ax, ay, bx, by):
					crossed = True
					break

			if not crossed:
				continue

			sal = branch_salience(fork, nb)
			if sal >= _TAU_SIGMA:
				# Salient branch → not a compound link
				return False

			fid = id(fork)
			if fid not in crossed_forks:
				crossed_forks[fid] = (fork, nb, sal)

	if len(crossed_forks) < 2:
		return False

	# Check overlapping disks between crossed forks
	fork_list = [v[0] for v in crossed_forks.values()]
	overlapping = False
	for a in range(len(fork_list)):
		for b in range(a + 1, len(fork_list)):
			fa, fb = fork_list[a], fork_list[b]
			d = math.hypot(fa.x - fb.x, fa.y - fb.y)
			if d < fa.radius + fb.radius:
				overlapping = True
				break
		if overlapping:
			break

	if not overlapping:
		return False

	link.link_type = 'compound'
	link.valid     = True
	return True


# ── E: incompatibility filtering ──────────────────────────────────────────────

def filter_incompatible_links(links):
	"""Remove geometrically incompatible links, keeping the highest-salience set.

	Two links are incompatible if their segments strictly cross (intersect in
	their interiors).  We greedily keep the highest-salience link and discard
	any that intersect it, then repeat.

	Args:
		links: list of Link, sorted by descending salience

	Returns:
		list of Link — mutually compatible subset
	"""
	kept = []
	for link in links:
		x1, y1 = link.p1
		x2, y2 = link.p2
		conflict = False
		for existing in kept:
			ex1, ey1 = existing.p1
			ex2, ey2 = existing.p2
			if _seg_intersects_seg(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
				conflict = True
				break
		if not conflict:
			kept.append(link)
	return kept


# ── §7: Iterative Junction Identification ─────────────────────────────────────
#
# Four-step procedure using auxiliary graph H (vertices = concavities assigned
# to forks, edges = valid links).  Junctions are identified iteratively so that
# each decision accounts for previously committed junctions.
#
# Steps:
#   8a. Protuberances  — compound links → protuberance junctions (H unchanged)
#   8b. Half-junctions — link pairs with Φ_c > 0.25, remove consumed items from H
#   8c. T/Y/L/Stroke-end/Null — per-fork pairwise-softmax selection, update H
#   8d. Convert close T-junction pairs to half-junctions


# ── 7.0: Data structures ──────────────────────────────────────────────────────

class JType(object):
	"""Junction type constants for the iterative pipeline (§6.1)."""
	PROTUBERANCE = 'protuberance'
	HALF         = 'half'
	T            = 'T'
	Y            = 'Y'
	L            = 'L'
	STROKE_END   = 'stroke_end'
	NULL         = 'null'


# Type-specific log weights ω (§7, Eq. 14)
_W_T           = math.log(1.10)   # favours T over Y
_W_NULL        = math.log(0.95)   # slightly disfavours null vs L
_W_DEFAULT     = 0.0              # log(1.0)

# Thresholds
_TAU_L         = 0.5    # L-junction: concavity radius must be < τ_L·r_fork·cos(θ/2)
_SIGMA_MIN     = 1.5    # minimum branch salience for non-root branches (T/Y/L)
_HALF_PHI_C_TH = 0.25  # Φ_c threshold for half-junction detection
_T_TO_HALF_PHI = 0.40  # good-continuation threshold for step-8d T→half conversion


class JunctionResult(object):
	"""Identified junction for a single fork after the iterative procedure.

	Attributes:
		fork:        MATNode — the MAT fork where the junction was identified
		jtype:       JType constant
		link:        primary Link (T, half, protuberance) or None
		links:       [Link, Link] for half-junctions (both links)
		rep_csf:     representative concave CSF for Y/L junctions, or None
		cut_points:  list of ((x1,y1),(x2,y2)) pairs — the actual cut lines
		score:       float — aggregated π score (for diagnostics)
	"""

	__slots__ = ('fork', 'jtype', 'link', 'links', 'rep_csf', 'cut_points', 'score')

	def __init__(self, fork, jtype):
		self.fork       = fork
		self.jtype      = jtype
		self.link       = None
		self.links      = []
		self.rep_csf    = None
		self.cut_points = []
		self.score      = 0.0

	def __repr__(self):
		if self.fork is not None:
			loc = '({:.0f},{:.0f})'.format(self.fork.x, self.fork.y)
		else:
			loc = '(?)'
		return '<JunctionResult: {} at {} cuts={}>'.format(
			self.jtype, loc, len(self.cut_points))


class AuxGraph(object):
	"""Auxiliary graph H: vertices = concavities, edges = valid links (§7).

	Supports O(1) removal of individual vertices (concavities) and edges (links).
	"""

	def __init__(self, links, sector_assignments):
		# Vertices: id(csf) → csf
		self._csfs = {}
		for sa in sector_assignments.values():
			for csf in sa.assignments:
				if csf is not None:
					self._csfs[id(csf)] = csf

		# Edges: id(link) → link; adjacency id(csf) → set[id(link)]
		self._links = {}
		self._adj   = defaultdict(set)
		for link in links:
			self._add_link(link)

	def _add_link(self, link):
		lid = id(link)
		self._links[lid] = link
		self._adj[id(link.csf1)].add(lid)
		self._adj[id(link.csf2)].add(lid)

	@property
	def links(self):
		return list(self._links.values())

	def links_for_fork(self, fork, sector_assignments):
		"""All H-links whose BOTH CSFs are assigned to this fork."""
		sa = sector_assignments.get(id(fork))
		if sa is None:
			return []
		fork_csf_ids = {id(c) for c in sa.assignments if c is not None and id(c) in self._csfs}
		return [l for l in self._links.values()
				if id(l.csf1) in fork_csf_ids and id(l.csf2) in fork_csf_ids]

	def csfs_for_fork(self, fork, sector_assignments):
		"""All CSFs in H that are currently assigned to this fork."""
		sa = sector_assignments.get(id(fork))
		if sa is None:
			return []
		return [c for c in sa.assignments if c is not None and id(c) in self._csfs]

	def remove_link(self, link):
		lid = id(link)
		if lid not in self._links:
			return
		del self._links[lid]
		self._adj[id(link.csf1)].discard(lid)
		self._adj[id(link.csf2)].discard(lid)

	def remove_csf(self, csf):
		cid = id(csf)
		if cid not in self._csfs:
			return
		del self._csfs[cid]
		for lid in list(self._adj.get(cid, set())):
			if lid in self._links:
				link = self._links.pop(lid)
				other = id(link.csf2) if id(link.csf1) == cid else id(link.csf1)
				self._adj[other].discard(lid)
		self._adj.pop(cid, None)

	def has_csf(self, csf):
		return id(csf) in self._csfs

	def has_link(self, link):
		return id(link) in self._links


# ── 7.1: Quality measures ─────────────────────────────────────────────────────

def _flamant_significance(csf, fork):
	"""Concavity significance via Flamant elastic half-plane model (§7, Eq. 6-9).

	Treats the concavity as a concentrated normal load at its extremum acting on
	the half-plane boundary at the fork.  The radial stress decays as 1/r:

	    σ_F(ε, f) = 2·r_ε / (π·d)

	where r_ε = concavity disk radius, d = distance from fork centre to extremum.

	Returns a non-negative float — larger means geometrically more prominent.
	"""
	d = math.hypot(csf.extremum[0] - fork.x, csf.extremum[1] - fork.y)
	d = max(d, fork.radius, _EPS)
	return 2.0 * csf.disk_radius / (math.pi * d)


def _estimate_branch_area(fork, branch_neighbor):
	"""Approximate swept area of a branch = ∫ 2r ds (rectangular cross-section)."""
	prev, cur = fork, branch_neighbor
	area = 0.0
	while True:
		step = math.hypot(cur.x - prev.x, cur.y - prev.y)
		r    = (prev.radius + cur.radius) * 0.5
		area += 2.0 * r * step
		if cur.is_terminal or cur.is_fork:
			break
		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt:
			break
		prev, cur = cur, nxt[0]
	return area


def _fork_branches(fork):
	"""Return [(angle_deg, neighbor_node), ...] sorted CCW around fork."""
	result = []
	for nb in fork.neighbors:
		dx = nb.x - fork.x
		dy = nb.y - fork.y
		mag = math.hypot(dx, dy)
		if mag < _EPS:
			continue
		ang = math.degrees(math.atan2(dy / mag, dx / mag)) % 360.0
		result.append((ang, nb))
	return sorted(result, key=lambda x: x[0])


def _coverage_I(fork, jtype, branches=None):
	"""Approximate coverage I = ln(A_after / A_before) (§7, Eq. 4).

	Estimates how well the junction type covers the glyph area.  Positive I
	means strokes overlap (acceptable for crossings); negative I means area
	is lost (discarded branches).
	"""
	if branches is None:
		branches = _fork_branches(fork)
	if not branches:
		return 0.0

	areas = [_estimate_branch_area(fork, nb) for _, nb in branches]
	A_before = max(sum(areas), _EPS)

	if jtype in (JType.T, JType.HALF, JType.PROTUBERANCE):
		A_after = A_before            # all branches accounted for
	elif jtype == JType.Y:
		A_after = A_before * 1.05    # slight overlap at ligature region
	elif jtype in (JType.L, JType.NULL):
		A_after = A_before - min(areas)   # discard one (least salient) branch
	elif jtype == JType.STROKE_END:
		sorted_areas = sorted(areas, reverse=True)
		# Keep only the most salient branch; discard the rest
		A_after = sorted_areas[0] if sorted_areas else A_before * 0.4
	else:
		A_after = A_before

	return math.log(max(A_after, _EPS) / A_before)


def _smoothness_G(link):
	"""Smoothness G = ln Φ of the link's good-continuation (§7, Eq. 5).

	For T-junctions the link already stores good_continuation; for Y/L we
	return 0 (no direct spine estimate available without full reconstruction).
	"""
	if link is not None:
		return math.log(max(link.good_continuation, _EPS))
	return 0.0


def _significance_C(fork, jtype, h_csfs, link=None):
	"""Concavity significance C via Flamant model (§7, Eq. 6-9).

	T-junction: harmonic mean of the two link CSF significances (favours balance).
	Y/L-junction: dominance ratio max(sig) / sum(sig) (favours one strong CSF).
	"""
	if not h_csfs:
		return 0.0

	if jtype == JType.T and link is not None:
		s1 = _flamant_significance(link.csf1, fork)
		s2 = _flamant_significance(link.csf2, fork)
		total = s1 + s2
		return 2.0 * s1 * s2 / total if total > _EPS else 0.0  # harmonic mean

	sigs  = [_flamant_significance(c, fork) for c in h_csfs]
	total = sum(sigs)
	return max(sigs) / total if total > _EPS else 0.0  # dominance ratio


def _omega(jtype):
	"""Type-specific log weight ω (§7, Eq. 14)."""
	if jtype == JType.T:
		return _W_T
	if jtype == JType.NULL:
		return _W_NULL
	return _W_DEFAULT


def _pi_score(I, G, C, S, omega, jtype_a, jtype_b):
	"""Compute π(J_a) for the pairwise comparison against J_b (§7, Eq. 14).

	π = I + δ_TYL·G + δ_TYL·C + δ_T·S + ω

	δ_TYL = 1 when both compared types are in {T, Y, L}
	δ_T   = 1 when both compared types are T
	"""
	TYL   = {JType.T, JType.Y, JType.L}
	d_TYL = 1.0 if (jtype_a in TYL and jtype_b in TYL) else 0.0
	d_T   = 1.0 if (jtype_a == JType.T and jtype_b == JType.T) else 0.0
	return I + d_TYL * G + d_TYL * C + d_T * S + omega


# ── 7.2: Candidate building and selection ────────────────────────────────────

class _Candidate(object):
	"""A candidate junction configuration for pairwise evaluation."""
	__slots__ = ('jtype', 'link', 'rep_csf', 'I', 'G', 'C', 'S', 'omega')

	def __init__(self, jtype, link=None, rep_csf=None, I=0.0, G=0.0, C=0.0, S=0.0):
		self.jtype   = jtype
		self.link    = link
		self.rep_csf = rep_csf
		self.I       = I
		self.G       = G
		self.C       = C
		self.S       = S
		self.omega   = _omega(jtype)


def _build_candidates(fork, aux_graph, sector_assignments, sigma_phi):
	"""Build the candidate set J_f for a fork (§7, Step 8c).

	Always includes null-junction and stroke-end.
	Adds T-junctions for each remaining link in H assigned to fork.
	Adds Y-junctions (2 configs per salient root branch) and L-junction
	from the most significant concavity when conditions are met.

	Returns list of _Candidate.
	"""
	branches = _fork_branches(fork)
	if not branches:
		return []

	h_links = aux_graph.links_for_fork(fork, sector_assignments)
	h_csfs  = aux_graph.csfs_for_fork(fork, sector_assignments)
	sals    = [branch_salience(fork, nb) for _, nb in branches]

	candidates = []

	# ── Null-junction (always) ────────────────────────────────────────
	candidates.append(_Candidate(JType.NULL, I=_coverage_I(fork, JType.NULL, branches)))

	# ── Stroke-end (when ≤1 salient branch) ──────────────────────────
	if sum(1 for s in sals if s > _TAU_SIGMA) <= 1:
		candidates.append(_Candidate(JType.STROKE_END,
									 I=_coverage_I(fork, JType.STROKE_END, branches)))

	# ── T-junction (one per valid link in H) ─────────────────────────
	for link in h_links:
		root_nb = link.protruding_branch
		non_root_ok = all(branch_salience(fork, nb) >= _SIGMA_MIN
						  for _, nb in branches if nb is not root_nb)
		if not non_root_ok:
			continue
		I = _coverage_I(fork, JType.T, branches)
		G = _smoothness_G(link)
		C = _significance_C(fork, JType.T, h_csfs, link=link)
		S = math.log(max(link.salience, _EPS))
		candidates.append(_Candidate(JType.T, link=link, I=I, G=G, C=C, S=S))

	# ── Y-junction (one config per salient root branch, requires H CSFs) ─
	if h_csfs:
		for (root_ang, root_nb), sal in zip(branches, sals):
			if sal <= _TAU_SIGMA:
				continue
			non_root_ok = all(branch_salience(fork, nb) >= _SIGMA_MIN
							  for _, nb in branches if nb is not root_nb)
			if not non_root_ok:
				continue
			# Representative = CSF most opposite the root branch
			opp_ang = (root_ang + 180.0) % 360.0
			def _ang_dist_to_opp(c, _opp=opp_ang):
				cx = c.extremum[0] - fork.x
				cy = c.extremum[1] - fork.y
				a  = math.degrees(math.atan2(cy, cx)) % 360.0
				d  = abs(a - _opp)
				return min(d, 360.0 - d)
			rep = min(h_csfs, key=_ang_dist_to_opp)
			I = _coverage_I(fork, JType.Y, branches)
			G = _smoothness_G(None)
			C = _significance_C(fork, JType.Y, h_csfs)
			candidates.append(_Candidate(JType.Y, rep_csf=rep, I=I, G=G, C=C))

	# ── L-junction (most significant CSF if radius constraint met) ────
	if h_csfs:
		sigs = [_flamant_significance(c, fork) for c in h_csfs]
		rep  = h_csfs[sigs.index(max(sigs))]

		sa = sector_assignments.get(id(fork))
		l_ok = False
		if sa is not None:
			for i, c in enumerate(sa.assignments):
				if c is rep and i < len(sa.sectors):
					lo, hi, _mid = sa.sectors[i]
					gap = (hi - lo) % 360.0
					cos_half = math.cos(math.radians(gap * 0.5))
					if rep.disk_radius < _TAU_L * fork.radius * max(cos_half, 0.1):
						l_ok = True
					break

		if l_ok and all(s >= _SIGMA_MIN for s in sals):
			I = _coverage_I(fork, JType.L, branches)
			G = _smoothness_G(None)
			C = _significance_C(fork, JType.L, h_csfs)
			candidates.append(_Candidate(JType.L, rep_csf=rep, I=I, G=G, C=C))

	return candidates


def _select_junction(candidates):
	"""Select the winning candidate via pairwise softmax aggregation (§7).

	For each pair (a, b) computes π(a|b) context-dependently (δ terms depend
	on both types).  Winner maximises the product of pairwise win-probabilities,
	accumulated as a sum of log-probabilities for numerical stability.

	Returns the winning _Candidate, or None if the list is empty.
	"""
	if not candidates:
		return None
	if len(candidates) == 1:
		return candidates[0]

	n = len(candidates)
	log_prods = [0.0] * n

	for a in range(n):
		ca = candidates[a]
		for b in range(n):
			if a == b:
				continue
			cb = candidates[b]
			pi_a = _pi_score(ca.I, ca.G, ca.C, ca.S, ca.omega, ca.jtype, cb.jtype)
			pi_b = _pi_score(cb.I, cb.G, cb.C, cb.S, cb.omega, cb.jtype, ca.jtype)
			# log p(a|b) = pi_a − logsumexp(pi_a, pi_b)  (numerically stable)
			m = max(pi_a, pi_b)
			log_p = pi_a - m - math.log(math.exp(pi_a - m) + math.exp(pi_b - m))
			log_prods[a] += log_p

	best = max(range(n), key=lambda i: log_prods[i])
	return candidates[best]


# ── 7.3: Step 8a — Protuberances ────────────────────────────────────────────

def identify_protuberances(valid_links):
	"""Step 8a: create a JunctionResult for each compound link (§7, Step 1).

	A compound link crosses ≥2 non-salient branches from different forks with
	overlapping disks — the hallmark of a small protuberance.

	Does NOT modify the auxiliary graph H.

	Args:
		valid_links: list of Link from filter_incompatible_links()

	Returns:
		list of JunctionResult with jtype=JType.PROTUBERANCE
	"""
	results = []
	for link in valid_links:
		if link.link_type != 'compound' or link.fork is None:
			continue
		jr = JunctionResult(link.fork, JType.PROTUBERANCE)
		jr.link       = link
		jr.cut_points = [(link.p1, link.p2)]
		results.append(jr)
	return results


# ── 7.4: Step 8b — Half-Junctions ───────────────────────────────────────────

def _phi_c(link_a, link_b, sigma_phi):
	"""Combined good-continuation Φ_c(ℓ, ℓ') for a link pair (§7, Step 2).

	Φ_c = Φ(ε₁, ε₃) · Φ(ε₂, ε₄) using the non-crossing endpoint assignment:
	choose the pairing with shorter total inter-link distance.
	"""
	c1a, c2a = link_a.csf1, link_a.csf2
	c1b, c2b = link_b.csf1, link_b.csf2

	d_straight = (math.hypot(c1a.extremum[0] - c1b.extremum[0],
							  c1a.extremum[1] - c1b.extremum[1]) +
				  math.hypot(c2a.extremum[0] - c2b.extremum[0],
							  c2a.extremum[1] - c2b.extremum[1]))
	d_crossed  = (math.hypot(c1a.extremum[0] - c2b.extremum[0],
							  c1a.extremum[1] - c2b.extremum[1]) +
				  math.hypot(c2a.extremum[0] - c1b.extremum[0],
							  c2a.extremum[1] - c1b.extremum[1]))

	if d_straight <= d_crossed:
		return (good_continuation(c1a, c1b, sigma_phi) *
				good_continuation(c2a, c2b, sigma_phi))
	return (good_continuation(c1a, c2b, sigma_phi) *
			good_continuation(c2a, c1b, sigma_phi))


def _branch_node_set(link, max_hops=60):
	"""Walk the protruding branch from a link's fork; return set of node ids."""
	nb = link.protruding_branch
	if nb is None:
		return set()
	nodes = set()
	prev  = link.fork
	cur   = nb
	for _ in range(max_hops):
		nodes.add(id(cur))
		if cur.is_terminal or cur.is_fork:
			break
		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt:
			break
		prev, cur = cur, nxt[0]
	return nodes


def identify_half_junctions(valid_links, ligatures, sector_assignments,
							 aux_graph, sigma_phi=50.0):
	"""Step 8b: identify half-junctions from link pairs with Φ_c > 0.25 (§7, Step 2).

	For each pair of links that:
	  - Do not share a concavity
	  - Are not nested (protruding branches don't overlap)
	  - Satisfy Φ_c(ℓ, ℓ') > _HALF_PHI_C_TH

	Process in decreasing Φ_c order; skip pairs where either link was already
	committed.  Update H by removing both links and any link whose protruding
	branch overlaps the crossing path.

	Args:
		valid_links:        list of Link (compatible, sorted by salience)
		ligatures:          list of Ligature (unused directly; for future grouping)
		sector_assignments: dict {id(fork) → SectorAssignment}
		aux_graph:          AuxGraph H (modified in-place)
		sigma_phi:          spread for good_continuation (same as generate_links)

	Returns:
		list of JunctionResult with jtype=JType.HALF
	"""
	# Collect candidate pairs and their Φ_c scores
	pairs = []
	n = len(valid_links)
	for i in range(n):
		la = valid_links[i]
		if not aux_graph.has_link(la):
			continue
		for j in range(i + 1, n):
			lb = valid_links[j]
			if not aux_graph.has_link(lb):
				continue
			# Must not share a concavity
			if {id(la.csf1), id(la.csf2)} & {id(lb.csf1), id(lb.csf2)}:
				continue
			phi = _phi_c(la, lb, sigma_phi)
			if phi > _HALF_PHI_C_TH:
				pairs.append((phi, la, lb))

	pairs.sort(key=lambda x: x[0], reverse=True)

	committed = set()
	results   = []

	for phi, la, lb in pairs:
		if id(la) in committed or id(lb) in committed:
			continue
		if not aux_graph.has_link(la) or not aux_graph.has_link(lb):
			continue

		# Nesting check: protruding branches must not share nodes
		nodes_a = _branch_node_set(la)
		nodes_b = _branch_node_set(lb)
		if nodes_a & nodes_b:
			continue

		# Anchor half-junction at the fork of the higher-salience link
		anchor = la if la.salience >= lb.salience else lb
		fork   = anchor.fork
		if fork is None:
			fork = la.fork or lb.fork
		if fork is None:
			continue

		jr            = JunctionResult(fork, JType.HALF)
		jr.links      = [la, lb]
		jr.link       = anchor
		jr.cut_points = [(la.p1, la.p2), (lb.p1, lb.p2)]
		results.append(jr)

		committed.add(id(la))
		committed.add(id(lb))

		# Update H: remove both links
		aux_graph.remove_link(la)
		aux_graph.remove_link(lb)

		# Remove links whose protruding branch overlaps the crossing path
		crossing_nodes = nodes_a | nodes_b
		for other in list(aux_graph.links):
			if _branch_node_set(other) & crossing_nodes:
				aux_graph.remove_link(other)

	return results


# ── 7.5: Step 8c — T/Y/L/Stroke-end/Null ───────────────────────────────────

def _build_fork_order(graph, aux_graph, sector_assignments):
	"""Return forks sorted by processing priority (§7, Eq. 14).

	Priority (high → low):
	  Group 0: forks with ≥1 link remaining in H
	  Group 1: forks with ≥1 concavity remaining in H
	  Group 2: all other forks

	Within each group: decreasing minimum branch salience (depth-first).
	"""
	def _key(fork):
		h_links = aux_graph.links_for_fork(fork, sector_assignments)
		h_csfs  = aux_graph.csfs_for_fork(fork, sector_assignments)
		if h_links:
			group = 0
		elif h_csfs:
			group = 1
		else:
			group = 2
		brs = _fork_branches(fork)
		min_sal = min((branch_salience(fork, nb) for _, nb in brs),
					  default=0.0)
		return (group, -min_sal)   # lower group + higher salience first

	return sorted(graph.forks(), key=_key)


def _project_cut_from_csf(fork, csf):
	"""Project a cut from csf.extremum through the fork to the opposing side.

	Returns (p1, p2) where p1 = extremum and p2 = mirror point past the fork.
	"""
	ex, ey = csf.extremum
	dx = fork.x - ex
	dy = fork.y - ey
	mag = math.hypot(dx, dy)
	if mag < _EPS:
		return ((ex, ey), (fork.x + fork.radius, fork.y))
	t  = (mag + fork.radius) / mag
	p2 = (ex + dx * t, ey + dy * t)
	return ((ex, ey), p2)


def _candidate_to_result(fork, cand):
	"""Convert a _Candidate to a JunctionResult, filling in cut_points."""
	jr         = JunctionResult(fork, cand.jtype)
	jr.link    = cand.link
	jr.rep_csf = cand.rep_csf
	jr.score   = cand.I + cand.omega   # lightweight score proxy

	if cand.jtype == JType.T and cand.link is not None:
		jr.cut_points = [(cand.link.p1, cand.link.p2)]
	elif cand.jtype in (JType.Y, JType.L) and cand.rep_csf is not None:
		jr.cut_points = [_project_cut_from_csf(fork, cand.rep_csf)]

	return jr


def _update_H_after_junction(jr, aux_graph, sector_assignments):
	"""Update H after a junction has been identified (§7.3.8)."""
	if jr.jtype == JType.T and jr.link is not None:
		link = jr.link
		if link.good_continuation > _T_TO_HALF_PHI:
			# Remove both concavities — they are fully consumed
			aux_graph.remove_csf(link.csf1)
			aux_graph.remove_csf(link.csf2)
		else:
			aux_graph.remove_link(link)

	elif jr.jtype == JType.Y and jr.rep_csf is not None:
		aux_graph.remove_csf(jr.rep_csf)

	elif jr.jtype in (JType.L, JType.NULL, JType.STROKE_END):
		for csf in aux_graph.csfs_for_fork(jr.fork, sector_assignments):
			aux_graph.remove_csf(csf)


def identify_junctions_step3(graph, sector_assignments, aux_graph, contours,
							  sigma_phi=50.0):
	"""Step 8c: identify T/Y/L/Stroke-end/Null junctions (§7, Step 3).

	Processes forks in priority order (Eq. 14).  For each fork builds the
	candidate set J_f, runs pairwise softmax selection, records the winner,
	and updates H.

	Args:
		graph:              MATGraph (interior MAT)
		sector_assignments: dict {id(fork) → SectorAssignment}
		aux_graph:          AuxGraph H (modified in-place)
		contours:           glyph contours (currently unused; reserved for area tests)
		sigma_phi:          spread for good_continuation

	Returns:
		list of JunctionResult (all fork types, including null/stroke-end)
	"""
	results = []

	for fork in _build_fork_order(graph, aux_graph, sector_assignments):
		candidates = _build_candidates(fork, aux_graph, sector_assignments, sigma_phi)
		if not candidates:
			continue

		winner = _select_junction(candidates)
		if winner is None:
			continue

		jr = _candidate_to_result(fork, winner)
		results.append(jr)

		_update_H_after_junction(jr, aux_graph, sector_assignments)

	return results


# ── 7.6: Step 8d — Convert close T-junction pairs to half-junctions ─────────

def convert_T_pairs_to_half(step3_results, sigma_phi=50.0):
	"""Step 8d: merge nearby T-junction pairs into half-junctions (§7, Step 4).

	Two T-junctions are merged when:
	  - Their forks are closer than the sum of their radii
	  - Good-continuation between any endpoint pair exceeds _T_TO_HALF_PHI

	Args:
		step3_results: list of JunctionResult from identify_junctions_step3()
		sigma_phi:     spread for good_continuation

	Returns:
		Updated list (T-pairs replaced by single JType.HALF results).
	"""
	t_jrs = [(i, jr) for i, jr in enumerate(step3_results)
			 if jr.jtype == JType.T and jr.link is not None]

	merged = set()
	extra  = []

	for a_pos in range(len(t_jrs)):
		i, jra = t_jrs[a_pos]
		if i in merged:
			continue
		for b_pos in range(a_pos + 1, len(t_jrs)):
			j, jrb = t_jrs[b_pos]
			if j in merged:
				continue

			d_ff  = math.hypot(jra.fork.x - jrb.fork.x, jra.fork.y - jrb.fork.y)
			r_sum = jra.fork.radius + jrb.fork.radius
			if d_ff >= r_sum:
				continue

			# Check good-continuation (best of both endpoint pairings)
			phi = max(
				good_continuation(jra.link.csf1, jrb.link.csf1, sigma_phi),
				good_continuation(jra.link.csf1, jrb.link.csf2, sigma_phi),
				good_continuation(jra.link.csf2, jrb.link.csf1, sigma_phi),
				good_continuation(jra.link.csf2, jrb.link.csf2, sigma_phi),
			)
			if phi < _T_TO_HALF_PHI:
				continue

			# Anchor at the fork with the more-salient branches
			brs_a   = _fork_branches(jra.fork)
			brs_b   = _fork_branches(jrb.fork)
			max_a   = max((branch_salience(jra.fork, nb) for _, nb in brs_a), default=0.0)
			max_b   = max((branch_salience(jrb.fork, nb) for _, nb in brs_b), default=0.0)
			anchor  = jra if max_a >= max_b else jrb

			half_jr            = JunctionResult(anchor.fork, JType.HALF)
			half_jr.links      = [jra.link, jrb.link]
			half_jr.link       = anchor.link
			half_jr.cut_points = jra.cut_points + jrb.cut_points

			merged.add(i)
			merged.add(j)
			extra.append(half_jr)
			break  # each T-junction merges with at most one partner

	return [r for k, r in enumerate(step3_results) if k not in merged] + extra


# ── 7.7: Main entry point ────────────────────────────────────────────────────

def identify_junctions(valid_links, ligatures, sector_assignments, graph,
					   contours, sigma_phi=50.0):
	"""Run the full 4-step iterative junction identification procedure (§7).

	Steps 8a-8d as specified in Berio et al. 2022:
	  8a. Protuberances  — compound links (H not modified)
	  8b. Half-junctions — link pairs with Φ_c > 0.25 (H updated)
	  8c. T/Y/L/Stroke-end/Null — per-fork pairwise softmax (H updated)
	  8d. Close T-junction pairs → half-junctions

	Args:
		valid_links:        list of Link from filter_incompatible_links()
		ligatures:          list of Ligature from compute_ligatures_v2()
		sector_assignments: dict {id(fork) → SectorAssignment}
		graph:              MATGraph (interior MAT)
		contours:           glyph contours
		sigma_phi:          spread for good_continuation (default 50.0 font units)

	Returns:
		(protuberances, half_junctions, step3_junctions) — three lists of
		JunctionResult.  step3_junctions includes null and stroke-end results
		(with empty cut_points) as well as actual T/Y/L cuts.
	"""
	aux = AuxGraph(valid_links, sector_assignments)

	protuberances  = identify_protuberances(valid_links)
	half_junctions = identify_half_junctions(
		valid_links, ligatures, sector_assignments, aux, sigma_phi)
	step3          = identify_junctions_step3(
		graph, sector_assignments, aux, contours, sigma_phi)
	step3          = convert_T_pairs_to_half(step3, sigma_phi)

	return protuberances, half_junctions, step3


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


# ── §9: Stroke Graph S and Structural Operations ──────────────────────────────
#
# Stroke graph S: one vertex per MAT branch, edges = "same stroke" connections.
# Initially disconnected; junction operations build connectivity.
# For CJK separation we need cut positions and stroke identity, not full spines.


# ── 9.1: Branch extraction ───────────────────────────────────────────────────

class BranchVertex(object):
	"""One vertex in stroke graph S: a maximal path in M between topology nodes.

	A topology node is any fork or terminal. Degree-2 intermediate nodes sit
	inside the branch and are included in path[] but are not branch endpoints.

	Attributes:
		bid:         int — unique id
		start:       MATNode (fork or terminal)
		end:         MATNode (fork or terminal)
		path:        [MATNode] ordered from start to end
		length:      total Euclidean arc length of branch
		discarded:   bool — marked for removal by junction ops
		stroke_id:   int or None — assigned by StrokeGraph.finalize_strokes()
		multitraced: bool — True when shared between 2 strokes (overlap zone)
	"""

	__slots__ = ('bid', 'start', 'end', 'path', 'length',
				 'discarded', 'stroke_id', 'multitraced')

	def __init__(self, bid, start, end, path):
		self.bid         = bid
		self.start       = start
		self.end         = end
		self.path        = path
		self.discarded   = False
		self.stroke_id   = None
		self.multitraced = False

		total = 0.0
		for k in range(len(path) - 1):
			total += math.hypot(path[k+1].x - path[k].x, path[k+1].y - path[k].y)
		self.length = total

	def neighbor_from(self, node):
		"""Return the first path node immediately after *node* along this branch."""
		if self.start is node and len(self.path) > 1:
			return self.path[1]
		if self.end is node and len(self.path) > 1:
			return self.path[-2]
		return None

	def salience_at(self, fork):
		"""σ(branch, fork) using the existing branch_salience() helper."""
		nb = self.neighbor_from(fork)
		if nb is None:
			return 0.0
		return branch_salience(fork, nb)

	def __repr__(self):
		state = 'discarded' if self.discarded else (
			'multitrace' if self.multitraced else 'active')
		return '<Branch #{} ({:.0f},{:.0f})→({:.0f},{:.0f}) L={:.0f} {}>'.format(
			self.bid,
			self.start.x, self.start.y,
			self.end.x,   self.end.y,
			self.length, state)


def extract_branches(graph):
	"""Extract all MAT branches as BranchVertex objects (§4.1).

	Walks the graph from every topology node (fork + terminal), enumerating
	maximal degree-2 paths.  Each undirected path is visited exactly once.

	Returns:
		list of BranchVertex
	"""
	topology   = frozenset(id(n) for n in list(graph.forks()) + list(graph.terminals()))
	vis_edges  = set()   # frozenset({id(a), id(b)}) of directed edge a→b
	branches   = []
	bid_counter = [0]

	def walk(start, first_nb):
		edge_key = frozenset([id(start), id(first_nb)])
		if edge_key in vis_edges:
			return
		vis_edges.add(edge_key)

		path = [start, first_nb]
		prev, cur = start, first_nb
		while id(cur) not in topology:
			nxt = [n for n in cur.neighbors if n is not prev]
			if not nxt:
				break
			prev, cur = cur, nxt[0]
			path.append(cur)
			# Also mark the reverse edge so we don't re-walk
			vis_edges.add(frozenset([id(prev), id(cur)]))

		b = BranchVertex(bid_counter[0], start, cur, path)
		bid_counter[0] += 1
		branches.append(b)

	for node in list(graph.forks()) + list(graph.terminals()):
		for nb in node.neighbors:
			walk(node, nb)

	return branches


# ── 9.2: Stroke graph ─────────────────────────────────────────────────────────

class StrokeGraph(object):
	"""Graph S: vertices = branches, edges = same-stroke connections (§6.2).

	Connectivity is managed with a union-find so that connect() runs in near O(1).
	discarded branches are excluded from strokes().

	Operations (§6.2.3):
	  connect(b1, b2)      — same stroke
	  multitrace(b)         — branch shared by 2 strokes (overlap zone)
	  discard(b, recursive) — remove branch (+ optionally hanging subtree)
	"""

	def __init__(self, branches):
		self._branches = {b.bid: b for b in branches}
		self._parent   = {b.bid: b.bid for b in branches}   # union-find

		# Lookup: id(MATNode) → [BranchVertex] touching that node
		self._node_to_b = defaultdict(list)
		for b in branches:
			self._node_to_b[id(b.start)].append(b)
			if b.end is not b.start:
				self._node_to_b[id(b.end)].append(b)

	# ── union-find ─────────────────────────────────────────────────────────
	def _find(self, bid):
		while self._parent[bid] != bid:
			self._parent[bid] = self._parent[self._parent[bid]]   # path compression
			bid = self._parent[bid]
		return bid

	def _union(self, bid1, bid2):
		r1, r2 = self._find(bid1), self._find(bid2)
		if r1 != r2:
			self._parent[r2] = r1

	# ── public operations ──────────────────────────────────────────────────
	def connect(self, b1, b2):
		"""Mark b1 and b2 as belonging to the same stroke."""
		if b1 is None or b2 is None or b1.discarded or b2.discarded:
			return
		self._union(b1.bid, b2.bid)

	def multitrace(self, branch):
		"""Mark branch as the overlap zone between two strokes."""
		if branch is not None:
			branch.multitraced = True

	def discard(self, branch, recursive=False):
		"""Remove branch from the graph; optionally prune its hanging subtree."""
		if branch is None or branch.discarded:
			return
		branch.discarded = True
		if not recursive:
			return
		# Walk the far end: if it terminates (not a fork), prune further branches
		far_end = branch.end if branch.start.is_fork else branch.start
		if far_end.is_terminal:
			return
		for nb_branch in self._node_to_b.get(id(far_end), []):
			if nb_branch is branch or nb_branch.discarded:
				continue
			# Only recurse into branches that lead to a terminal (hanging tree)
			other = nb_branch.end if nb_branch.start is far_end else nb_branch.start
			if other.is_terminal or _all_paths_terminal(nb_branch, far_end, depth=5):
				self.discard(nb_branch, recursive=True)

	def branches_at(self, mat_node):
		"""Return active (non-discarded) branches touching mat_node."""
		return [b for b in self._node_to_b.get(id(mat_node), [])
				if not b.discarded]

	@property
	def active_branches(self):
		return [b for b in self._branches.values() if not b.discarded]

	def strokes(self):
		"""Return list of stroke groups (connected components, excluding discarded).

		Each group is a list of BranchVertex in the same connected component of S.
		"""
		groups = defaultdict(list)
		for b in self._branches.values():
			if b.discarded:
				continue
			root = self._find(b.bid)
			groups[root].append(b)
		return list(groups.values())

	def finalize_strokes(self):
		"""Assign integer stroke_id to each active branch based on connectivity."""
		for sid, group in enumerate(self.strokes()):
			for b in group:
				b.stroke_id = sid


def _all_paths_terminal(branch, entry_node, depth):
	"""Return True if all reachable branches from branch (away from entry_node)
	eventually lead to terminals within *depth* hops.  Used for subtree pruning.
	"""
	if depth <= 0:
		return False
	far = branch.end if branch.start is entry_node else branch.start
	if far.is_terminal:
		return True
	if far.is_fork:
		return False   # another fork = not a hanging leaf
	# degree-2 intermediate — shouldn't reach here in practice
	return True


# ── 9.3: Per-junction structural operations ───────────────────────────────────

def _branch_toward(branches_at_fork, fork, target_nb):
	"""Among branches at fork, find the one whose first step from fork is target_nb."""
	for b in branches_at_fork:
		if b.neighbor_from(fork) is target_nb:
			return b
	return None


def _apply_T_to_graph(jr, sg):
	"""T-junction: connect 2 non-protruding branches; multitrace the protruding one."""
	fork = jr.fork
	link = jr.link
	if link is None or fork is None:
		return
	at_fork  = sg.branches_at(fork)
	prot_nb  = link.protruding_branch
	prot_b   = _branch_toward(at_fork, fork, prot_nb)
	non_prot = [b for b in at_fork if b is not prot_b]
	if len(non_prot) >= 2:
		sg.connect(non_prot[0], non_prot[1])
	if prot_b is not None:
		sg.multitrace(prot_b)   # protruding stroke overlaps continuing stroke


def _apply_Y_to_graph(jr, sg):
	"""Y-junction: connect the 2 most salient branches (the through-stroke)."""
	fork = jr.fork
	if fork is None:
		return
	at_fork = sg.branches_at(fork)
	if len(at_fork) < 2:
		return
	sals = sorted(at_fork, key=lambda b: b.salience_at(fork), reverse=True)
	sg.connect(sals[0], sals[1])


def _apply_L_to_graph(jr, sg):
	"""L-junction: discard root (least salient), connect remaining 2."""
	fork = jr.fork
	if fork is None:
		return
	at_fork = sg.branches_at(fork)
	if not at_fork:
		return
	root = min(at_fork, key=lambda b: b.salience_at(fork))
	sg.discard(root, recursive=True)
	remaining = [b for b in at_fork if b is not root and not b.discarded]
	if len(remaining) >= 2:
		sg.connect(remaining[0], remaining[1])


def _apply_half_to_graph(jr, sg):
	"""Half-junction: for each link, multitrace its protruding branch and
	connect the two non-protruding branches (the crossing strokes).
	"""
	for link in jr.links:
		if link is None or link.fork is None:
			continue
		fork    = link.fork
		at_fork = sg.branches_at(fork)
		prot_nb = link.protruding_branch
		prot_b  = _branch_toward(at_fork, fork, prot_nb)
		if prot_b is not None:
			sg.multitrace(prot_b)
		non_prot = [b for b in at_fork if b is not prot_b]
		if len(non_prot) >= 2:
			sg.connect(non_prot[0], non_prot[1])


def _apply_stroke_end_to_graph(jr, sg):
	"""Stroke-end: discard all but the most salient branch at the fork."""
	fork = jr.fork
	if fork is None:
		return
	at_fork = sg.branches_at(fork)
	if not at_fork:
		return
	sals = sorted(at_fork, key=lambda b: b.salience_at(fork), reverse=True)
	for b in sals[1:]:
		sg.discard(b, recursive=True)


def _apply_protuberance_to_graph(jr, sg):
	"""Protuberance: discard non-salient branches; connect remaining salient ones."""
	fork = jr.fork
	if fork is None:
		return
	at_fork    = sg.branches_at(fork)
	salient    = [b for b in at_fork if b.salience_at(fork) >= _TAU_SIGMA]
	non_sal    = [b for b in at_fork if b.salience_at(fork) < _TAU_SIGMA]
	for b in non_sal:
		sg.discard(b)
	if len(salient) >= 2:
		sg.connect(salient[0], salient[1])


def _apply_null_to_graph(jr, sg):
	"""Null-junction: discard least salient branch; connect remaining 2."""
	fork = jr.fork
	if fork is None:
		return
	at_fork = sg.branches_at(fork)
	if not at_fork:
		return
	sals = sorted(at_fork, key=lambda b: b.salience_at(fork))
	sg.discard(sals[0])
	remaining = [b for b in sals[1:] if not b.discarded]
	if len(remaining) >= 2:
		sg.connect(remaining[0], remaining[1])


_JUNCTION_OPS = {
	JType.T:           _apply_T_to_graph,
	JType.Y:           _apply_Y_to_graph,
	JType.L:           _apply_L_to_graph,
	JType.HALF:        _apply_half_to_graph,
	JType.STROKE_END:  _apply_stroke_end_to_graph,
	JType.PROTUBERANCE: _apply_protuberance_to_graph,
	JType.NULL:        _apply_null_to_graph,
}


# ── 9.4: Build stroke graph ───────────────────────────────────────────────────

def build_stroke_graph(mat_graph, protuberances, half_junctions, step3_junctions):
	"""Build stroke graph S and apply all junction structural operations (§6.2).

	Args:
		mat_graph:         MATGraph (interior)
		protuberances:     list[JunctionResult] from identify_junctions step 8a
		half_junctions:    list[JunctionResult] from step 8b
		step3_junctions:   list[JunctionResult] from steps 8c+8d

	Returns:
		StrokeGraph with all operations applied and stroke IDs assigned
	"""
	branches = extract_branches(mat_graph)
	sg       = StrokeGraph(branches)

	for jr in protuberances + half_junctions + step3_junctions:
		op = _JUNCTION_OPS.get(jr.jtype)
		if op is not None:
			op(jr, sg)

	sg.finalize_strokes()
	return sg


# ── 9.5: Cut extraction ───────────────────────────────────────────────────────

def cuts_from_junction_results(protuberances, half_junctions, step3_junctions):
	"""Collect all outline cut pairs from identified junctions.

	Only T, Y, Half, and Protuberance junctions produce geometric cuts.
	L, Stroke-end, and Null produce no cuts (the glyph outline is continuous).

	Args:
		protuberances, half_junctions, step3_junctions: lists of JunctionResult

	Returns:
		list of ((x1,y1), (x2,y2)) — ready to pass to split_contour_at_points()
	"""
	CUT_TYPES = {JType.T, JType.Y, JType.HALF, JType.PROTUBERANCE}
	cuts = []
	for jr in protuberances + half_junctions + step3_junctions:
		if jr.jtype in CUT_TYPES:
			cuts.extend(jr.cut_points)
	return cuts


# ── 9.6: Result and main class ────────────────────────────────────────────────

class StrokeGraphResult(object):
	"""Full analysis result for the StrokeSepV2 pipeline.

	Attributes:
		graph:           MATGraph — interior medial axis
		ext_graph:       MATGraph — exterior medial axis M*
		csfs:            list[CSF] — all curvilinear shape features
		ligatures:       list[Ligature]
		links:           list[Link] — compatible links after filtering
		protuberances:   list[JunctionResult] — step 8a
		half_junctions:  list[JunctionResult] — step 8b
		step3_junctions: list[JunctionResult] — steps 8c+8d (T/Y/L/null/end)
		stroke_graph:    StrokeGraph — final S with connectivity + stroke IDs
		cuts:            list[((x1,y1),(x2,y2))] — outline cut positions
	"""

	def __init__(self, graph, ext_graph, csfs, ligatures, links,
				 protuberances, half_junctions, step3_junctions,
				 stroke_graph, cuts):
		self.graph            = graph
		self.ext_graph        = ext_graph
		self.csfs             = csfs
		self.ligatures        = ligatures
		self.links            = links
		self.protuberances    = protuberances
		self.half_junctions   = half_junctions
		self.step3_junctions  = step3_junctions
		self.stroke_graph     = stroke_graph
		self.cuts             = cuts

	@property
	def all_junctions(self):
		return self.protuberances + self.half_junctions + self.step3_junctions

	@property
	def strokes(self):
		return self.stroke_graph.strokes()

	def __repr__(self):
		t = sum(1 for j in self.step3_junctions if j.jtype == JType.T)
		y = sum(1 for j in self.step3_junctions if j.jtype == JType.Y)
		h = len(self.half_junctions)
		return ('<StrokeGraphResult: {} cuts | {} strokes | '
				'T={} Y={} half={} links={}>'.format(
					len(self.cuts), len(self.strokes), t, y, h, len(self.links)))


class StrokeSepV2(object):
	"""Full StrokeStyles (Berio et al. 2022) pipeline for CJK stroke separation.

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

		# ── Step 1: Interior MAT ──────────────────────────────────────────
		graph, _concavities = compute_mat(
			contours,
			sample_step=self.sample_step,
			beta_min=self.beta_min,
		)

		# ── Step 2: Exterior MAT M* ───────────────────────────────────────
		_ext_graph, exterior_terminals = compute_exterior_mat(
			contours,
			beta_min=self.beta_min,
			sample_step=self.sample_step,
		)

		# ── Steps 3+4: CSFs ───────────────────────────────────────────────
		csfs = compute_csfs(
			contours, graph, exterior_terminals,
			sample_step=self.sample_step,
		)

		# ── Step 5: Ligatures v2 ──────────────────────────────────────────
		ligatures = compute_ligatures_v2(graph, csfs)

		# ── Step 6: Sector assignment ─────────────────────────────────────
		sector_assignments = assign_concavities_to_forks(graph, csfs, ligatures)

		# ── Step 7: Links ─────────────────────────────────────────────────
		links = generate_links(sector_assignments, contours, graph, ligatures)
		links = filter_incompatible_links(links)

		# σ for good-continuation: 2 × max non-ligature fork radius
		lig_fork_ids  = {id(n) for lig in ligatures for n in lig.forks}
		non_lig_radii = [f.radius for f in graph.forks() if id(f) not in lig_fork_ids]
		sigma_phi     = 2.0 * max(non_lig_radii) if non_lig_radii else 50.0

		# ── Step 8: Junction identification ───────────────────────────────
		proturbs, halfs, step3 = identify_junctions(
			links, ligatures, sector_assignments, graph, contours, sigma_phi)

		# ── Step 9: Stroke graph + cut positions ──────────────────────────
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
		)

	def execute(self, result, contours):
		"""Apply cuts and return a list of separated Contour objects.

		When the new pipeline produces no cuts (e.g. single-stroke glyph),
		falls back to the geometry-based StrokeSeparator.

		Args:
			result:   StrokeGraphResult from analyze()
			contours: original list of TypeRig Contour objects

		Returns:
			list of Contour — original contours with junction cuts applied
		"""
		if not result.cuts:
			fallback = StrokeSeparator(
				beta_min=self.beta_min, sample_step=self.sample_step)
			fb_result = fallback.analyze(contours)
			return fallback.execute(fb_result, contours)

		_SNAP = 15.0   # maximum distance (font units) for a cut to snap to a contour

		working = [Contour([n.clone() for n in c.data], closed=c.closed)
				   for c in contours]
		output = []

		for contour in working:
			# Find cuts whose both endpoints lie near this contour
			applicable = []
			for cut in result.cuts:
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

		return output
