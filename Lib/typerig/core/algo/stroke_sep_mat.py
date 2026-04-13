# MODULE: TypeRig / Core / Algo / Stroke Separator — MAT Structures
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# MAT-level structures: ligatures, branch salience, stroke paths.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict, namedtuple

from typerig.core.algo.stroke_sep_common import _EPS


# - Stroke Path Structure ---------------
StrokePath = namedtuple('StrokePath', ['nodes', 'terminals', 'forks', 'direction_angle'])


# - Fork Merging ----------
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


# - Point-distance Ligatures (v1) ----------
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
	"""Return True if node's inscribed circle reaches any point in contact_region."""
	limit_sq = (node.radius + tol) ** 2
	nx, ny   = node.x, node.y
	for cx, cy in contact_region:
		if (nx - cx) ** 2 + (ny - cy) ** 2 <= limit_sq:
			return True
	return False


def _bfs_connected(seed_ids, graph):
	"""BFS over graph.nodes restricted to a seed id-set, return connected component."""
	id_to_node = {id(n): n for n in graph.nodes if id(n) in seed_ids}
	if not id_to_node:
		return []

	adjacency = defaultdict(list)
	for node in id_to_node.values():
		for nb in node.neighbors:
			if id(nb) in seed_ids:
				adjacency[id(node)].append(id(nb))

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
	"""Order ligature nodes along M, starting nearest the CSF extremum."""
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

		seed_ids = set()
		for node in graph.nodes:
			if _rib_touches_contact(node, csf.contact_region, tol):
				seed_ids.add(id(node))

		if not seed_ids:
			continue

		connected = _bfs_connected(seed_ids, graph)
		if not connected:
			continue

		ordered = _order_ligature_nodes(connected, csf)
		ligatures.append(Ligature(csf, ordered))

	return ligatures


def ligature_node_set(ligatures):
	"""Return a set of id(node) for all nodes across all ligatures."""
	result = set()
	for lig in ligatures:
		result.update(lig.node_ids)
	return result


# - Protruding Direction ----------
def protruding_direction(fork, branch_neighbor, all_ligature_node_ids):
	"""Compute protruding direction P(b, f, C) for branch b at fork f.

	Walk along branch b (starting at fork f toward branch_neighbor).
	Skip over nodes that belong to any ligature (they are "shared" outline
	territory, not the stroke body). The FIRST non-ligature node's position
	relative to the last ligature node gives the protruding direction.

	Returns:
		(dx, dy) — unit vector in the protruding direction
	"""
	prev, cur = fork, branch_neighbor
	last_lig  = fork

	while cur is not None:
		if id(cur) not in all_ligature_node_ids:
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
			nxt.sort(key=lambda n: n.radius)

		prev, cur = cur, nxt[0]

	# Fallback: tangent at fork toward branch_neighbor
	dx = branch_neighbor.x - fork.x
	dy = branch_neighbor.y - fork.y
	mag = math.hypot(dx, dy)
	if mag > _EPS:
		return (dx / mag, dy / mag)
	return (1.0, 0.0)


# - Branch Salience ----------
def branch_salience(fork, branch_neighbor):
	"""Compute σ(b, f) = ℓ / (ℓ - ρ) (Berio et al. §4.1.2).

	ℓ = arc length of the branch (walk to next terminal/fork)
	ρ = radius of the fork disk

	A branch is salient (protruding) if σ > τ_σ = 2.3 (paper default).
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


# - Branch Direction / Angles ----------
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


# - Stroke Path Extraction ----------
def extract_stroke_paths(graph):
	"""Extract complete stroke paths from terminal to terminal through forks.

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
	"""Trace a complete path from start through first_neighbor to next terminal."""
	COLLINEAR_THRESHOLD = 45.0

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
			in_dx = current.x - prev.x
			in_dy = current.y - prev.y
			in_angle = math.degrees(math.atan2(in_dy, in_dx)) % 360

			best_nb = None
			best_deviation = float('inf')

			for nb in next_nodes:
				out_dx = nb.x - current.x
				out_dy = nb.y - current.y
				out_angle = math.degrees(math.atan2(out_dy, out_dx)) % 360

				diff = abs(out_angle - in_angle)
				diff = min(diff, 360 - diff)
				deviation = abs(diff - 180)

				if deviation < best_deviation:
					best_deviation = deviation
					best_nb = nb

			if best_deviation > COLLINEAR_THRESHOLD:
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
