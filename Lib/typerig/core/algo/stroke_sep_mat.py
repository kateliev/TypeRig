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


def estimate_direction_from_path(path_nodes, lookback=8, curvature_bias=0.5):
	"""Curvature-aware direction estimate from accumulated MAT path history.

	Splits the lookback window into an older half and a recent half, then
	extrapolates the angular trend — so a curved stroke predicts where it is
	heading rather than just reporting its instantaneous tangent.

	Ported from Tegaki trace.ts ``estimateDirection``.

	Args:
		path_nodes:     list of MATNode — the path accumulated so far
		lookback:       number of historical nodes to consider (window size)
		curvature_bias: extrapolation weight
		                  0.0 = pure tangent from the recent half
		                  0.5 = moderate curvature extrapolation (default)
		                  1.0 = full extrapolation (continues turning at same rate)

	Returns:
		(dx, dy) — unnormalized direction vector
	"""
	n = len(path_nodes)
	window_size = min(n - 1, lookback)

	if window_size < 4 or curvature_bias == 0.0:
		# Not enough history or curvature disabled — simple endpoint vector
		old = path_nodes[n - 1 - window_size]
		cur = path_nodes[-1]
		return (cur.x - old.x, cur.y - old.y)

	half = window_size // 2
	cur = path_nodes[-1]
	mid = path_nodes[n - 1 - half]
	old = path_nodes[n - 1 - window_size]

	old_dx = mid.x - old.x
	old_dy = mid.y - old.y
	rec_dx = cur.x - mid.x
	rec_dy = cur.y - mid.y

	# Extrapolate: recent + bias * (recent - older)
	return (
		rec_dx + curvature_bias * (rec_dx - old_dx),
		rec_dy + curvature_bias * (rec_dy - old_dy),
	)


def peek_ahead_direction(from_node, start_nb, steps=6):
	"""Walk ahead along a MAT branch and return the direction to the endpoint.

	Follows the branch from ``from_node`` through ``start_nb`` for up to
	``steps`` nodes without modifying any graph state.  Stops early at forks
	or terminals (genuine structural endpoints).

	Ported from Tegaki trace.ts ``peekAhead``, adapted for the vector MAT graph
	(no visited-array needed — we just avoid backtracking).

	Args:
		from_node:  MATNode — origin of the direction vector
		start_nb:   MATNode — first step of the branch to probe
		steps:      how many nodes to walk ahead

	Returns:
		(dx, dy) — unnormalized vector from from_node to the reached point
	"""
	prev, cur = from_node, start_nb
	for _ in range(steps - 1):
		if cur.is_fork or cur.is_terminal:
			break
		nexts = [n for n in cur.neighbors if n is not prev]
		if not nexts:
			break
		prev, cur = cur, nexts[0]

	return (cur.x - from_node.x, cur.y - from_node.y)


def pick_best_branch(fork, path_nodes, candidates,
					 lookback=8, curvature_bias=0.5, peek_steps=6,
					 stop_cos=-2.0):
	"""Pick the best continuation branch at a fork using curvature-aware lookahead.

	Combines two ideas from Tegaki trace.ts:

	1. **Curvature-aware direction** (``estimateDirection``): uses the full path
	   history — not just the immediate 1-step tangent — and extrapolates the
	   ongoing curve trend via ``estimate_direction_from_path``.

	2. **Peek-ahead per candidate** (``pickStraightest`` + ``peekAhead``):
	   instead of comparing only the raw 1-step angle to the candidate node,
	   follows each candidate branch several steps ahead so the comparison uses
	   the actual branch direction rather than a noisy single-pixel vector.

	Args:
		fork:           MATNode — the fork node we just arrived at
		path_nodes:     list of MATNode — full path so far (fork is last entry)
		candidates:     list of MATNode — unvisited neighbors to evaluate
		lookback:       history window for direction estimation
		curvature_bias: extrapolation weight (see estimate_direction_from_path)
		peek_steps:     how many nodes to walk ahead per candidate branch
		stop_cos:       minimum cosine to accept a continuation; if the best
		                candidate scores below this, returns (None, best_cos).
		                Default -2.0 accepts any branch.

	Returns:
		(best_node, best_cos) — best MATNode and its cosine alignment score,
		or (None, best_cos) if no candidate clears stop_cos.
	"""
	dir_dx, dir_dy = estimate_direction_from_path(path_nodes, lookback, curvature_bias)
	dir_len = math.hypot(dir_dx, dir_dy)

	best_node = None
	best_cos  = -2.0

	for nb in candidates:
		peek_dx, peek_dy = peek_ahead_direction(fork, nb, peek_steps)
		peek_len = math.hypot(peek_dx, peek_dy)

		if dir_len < _EPS or peek_len < _EPS:
			continue

		cos_val = (dir_dx * peek_dx + dir_dy * peek_dy) / (dir_len * peek_len)
		if cos_val > best_cos:
			best_cos  = cos_val
			best_node = nb

	if best_node is None or best_cos < stop_cos:
		return None, best_cos

	return best_node, best_cos


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
def extract_stroke_paths(graph, lookback=8, curvature_bias=0.5, peek_steps=6):
	"""Extract complete stroke paths from terminal to terminal through forks.

	Fork disambiguation uses curvature-aware lookahead (pick_best_branch).
	The three optional parameters control that logic:

	Args:
		graph:          MATGraph from compute_mat()
		lookback:       history window for direction estimation (default 8)
		curvature_bias: curvature extrapolation weight, 0–1 (default 0.5)
		peek_steps:     nodes to walk ahead per candidate at forks (default 6)

	Returns:
		list of StrokePath namedtuples
	"""
	paths         = []
	visited_edges = set()

	for start_node in graph.terminals():
		for neighbor in start_node.neighbors:
			edge_key = (id(start_node), id(neighbor))
			if edge_key in visited_edges:
				continue

			path_nodes, end_terminal = _trace_full_path(
				start_node, neighbor, visited_edges,
				lookback=lookback, curvature_bias=curvature_bias,
				peek_steps=peek_steps,
			)

			if len(path_nodes) >= 2:
				forks_in_path    = [n for n in path_nodes if n.is_fork]
				terminals_in_path = [n for n in path_nodes if n.is_terminal]
				direction_angle  = _compute_path_direction(path_nodes)
				paths.append(StrokePath(
					nodes=path_nodes,
					terminals=terminals_in_path,
					forks=forks_in_path,
					direction_angle=direction_angle,
				))

	return paths


def _trace_full_path(start_node, first_neighbor, visited_edges,
					 lookback=8, curvature_bias=0.5, peek_steps=6):
	"""Trace a complete path from start through first_neighbor to next terminal.

	At fork nodes, uses curvature-aware lookahead (pick_best_branch) to choose
	the branch that best continues the stroke's ongoing trajectory.  Stops when
	no candidate scores above the cosine equivalent of a 45° deviation.
	"""
	# cos(45°) — stop if the best branch deviates more than 45° from estimated dir
	STOP_COS = math.cos(math.radians(45.0))

	path_nodes = [start_node]
	current    = first_neighbor
	prev       = start_node

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
			best_nb, _ = pick_best_branch(
				current, path_nodes, next_nodes,
				lookback=lookback, curvature_bias=curvature_bias,
				peek_steps=peek_steps, stop_cos=STOP_COS,
			)
			if best_nb is None:
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
