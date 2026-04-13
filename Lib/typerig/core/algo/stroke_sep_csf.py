# MODULE: TypeRig / Core / Algo / Stroke Separator — CSF/Fork Assignment
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Sector-based assignment of concave CSFs to MAT forks (§4.4).

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
import heapq

from typerig.core.algo.stroke_sep_common import _EPS


# - Sector Assignment ----------

_MAX_CANDIDATES_PER_SECTOR = 3   # keep top-N candidates per sector

class SectorAssignment(object):
	"""Concavity assignments for a single fork, organised by sector.

	A degree-3 fork has 3 sectors — one between each pair of branches.
	Sector i lies between branch[i] and branch[(i+1) % 3] (CCW order).

	Each sector tracks up to _MAX_CANDIDATES_PER_SECTOR candidates ranked
	by score.  The primary winner (``assignments[i]``) is the best-scoring
	candidate and is used for junction classification.  Runner-up candidates
	are available via ``candidates(i)`` and are used during link generation
	so that a concavity pair that fails the inside-glyph test (common for
	large-radius bowl-curve concavities in multi-contour glyphs) can fall
	back to a tighter nearby concavity.

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
		# _candidates[i] = sorted list of (score, csf) for sector i
		self._candidates = [[] for _ in range(3)]

	def assign(self, sector_idx, csf, score):
		"""Assign csf to sector if it scores better than the current occupant."""
		cands = self._candidates[sector_idx]
		# Insert in sorted order (ascending score)
		inserted = False
		for k, (s, _) in enumerate(cands):
			if score < s:
				cands.insert(k, (score, csf))
				inserted = True
				break
		if not inserted:
			cands.append((score, csf))
		# Trim to max
		if len(cands) > _MAX_CANDIDATES_PER_SECTOR:
			cands[:] = cands[:_MAX_CANDIDATES_PER_SECTOR]
		# Update primary assignment
		if cands:
			self.scores[sector_idx]      = cands[0][0]
			self.assignments[sector_idx] = cands[0][1]

	def candidates(self, sector_idx):
		"""Return list of CSFs for this sector, ordered by score (best first)."""
		return [csf for _, csf in self._candidates[sector_idx]]

	@property
	def all_csfs(self):
		"""All unique candidate CSFs across all sectors (not just winners)."""
		seen = set()
		result = []
		for cands in self._candidates:
			for _, csf in cands:
				cid = id(csf)
				if cid not in seen:
					seen.add(cid)
					result.append(csf)
		return result

	@property
	def assigned_csfs(self):
		"""List of (sector_idx, CSF) for all occupied sectors."""
		return [(i, c) for i, c in enumerate(self.assignments) if c is not None]

	def __repr__(self):
		n_assigned = sum(1 for c in self.assignments if c is not None)
		return '<SectorAssignment fork=({:.0f},{:.0f}) sectors={} assigned={}>'.format(
			self.fork.x, self.fork.y, len(self.sectors), n_assigned)


def _compute_sectors(fork, branches):
	"""Return 3 (angle_lo, angle_hi, angle_mid) tuples (degrees, CCW order)."""
	n = len(branches)
	sectors = []
	for i in range(n):
		a0 = branches[i][0]
		a1 = branches[(i + 1) % n][0]
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


# - Geodesic Path ----------
def _geodesic_path(fork, csf, graph, max_hops=200):
	"""Walk M from fork toward csf.extremum via shortest BFS path.

	Returns (path_length, path_nodes) where path_length is the total
	Euclidean length of the walked edges.  Returns (inf, []) if no path
	is found within max_hops.
	"""
	ex_x, ex_y = csf.extremum

	fork_id = id(fork)
	heap = [(0.0, fork_id, fork)]
	visited = {fork_id}
	dist_map = {fork_id: 0.0}
	pred = {fork_id: None}
	node_map = {fork_id: fork}
	hops = {fork_id: 0}

	def _reconstruct(end_id):
		path = []
		cur_id = end_id
		while cur_id is not None:
			path.append(node_map[cur_id])
			cur_id = pred[cur_id]
		path.reverse()
		return path

	while heap:
		dist, _nid, node = heapq.heappop(heap)

		if dist > dist_map.get(_nid, float('inf')):
			continue

		if hops[_nid] > max_hops:
			break

		d_to_ex = math.hypot(node.x - ex_x, node.y - ex_y)
		if d_to_ex <= node.radius + 10.0:
			return dist, _reconstruct(_nid)

		if node is not fork and node.is_fork:
			d_ff = math.hypot(node.x - fork.x, node.y - fork.y)
			if d_ff < fork.radius + node.radius:
				return dist, _reconstruct(_nid)

		for nb in node.neighbors:
			nb_id = id(nb)
			if nb_id in visited:
				continue
			visited.add(nb_id)
			edge_len = math.hypot(nb.x - node.x, nb.y - node.y)
			new_dist = dist + edge_len
			if new_dist < dist_map.get(nb_id, float('inf')):
				dist_map[nb_id] = new_dist
				pred[nb_id] = _nid
				node_map[nb_id] = nb
				hops[nb_id] = hops[_nid] + 1
				heapq.heappush(heap, (new_dist, nb_id, nb))

	return float('inf'), []


def _path_crosses_convex_rib(path, convex_csfs, tol=8.0, _convex_disks=None):
	"""Return True if any path node is inside a convex CSF's inscribed disk."""
	if _convex_disks is None:
		_convex_disks = [(c.disk_center[0], c.disk_center[1],
						  (c.disk_radius + tol) ** 2) for c in convex_csfs]

	for node in path[1:]:  # skip the fork itself
		nx, ny = node.x, node.y
		for cx, cy, cr_sq in _convex_disks:
			dx = nx - cx
			dy = ny - cy
			if dx * dx + dy * dy < cr_sq:
				return True
	return False


# - Main Assignment ----------
def assign_concavities_to_forks(graph, csfs, ligatures=None, max_hops=200):
	"""Assign each concave CSF to at most one sector per eligible fork (§4.4).

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

	_convex_disks = [(c.disk_center[0], c.disk_center[1],
					  (c.disk_radius + 8.0) ** 2) for c in convex_csfs]

	result = {}

	csf_positions = {}
	for csf in concave_csfs:
		csf_positions[id(csf)] = csf

	for fork in graph.forks():
		branches = []
		for nb in fork.neighbors:
			dx = nb.x - fork.x
			dy = nb.y - fork.y
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

		if len(branches) > 3:
			gaps = []
			n = len(branches)
			for i in range(n):
				gap = (branches[(i+1) % n][0] - branches[i][0]) % 360.0
				gaps.append((gap, i))
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

		# Single-source Dijkstra from this fork
		fork_id = id(fork)
		heap = [(0.0, fork_id, fork)]
		visited = {fork_id}
		dist_to = {fork_id: 0.0}
		pred = {fork_id: None}
		node_map = {fork_id: fork}

		csf_found = {}

		while heap:
			dist, _nid, node = heapq.heappop(heap)

			if dist > dist_to.get(_nid, float('inf')):
				continue

			for csf in concave_csfs:
				cid = id(csf)
				if cid in csf_found:
					continue
				ex_x, ex_y = csf.extremum
				d_to_ex = math.hypot(node.x - ex_x, node.y - ex_y)
				if d_to_ex <= node.radius + 10.0:
					csf_found[cid] = (dist, _nid)
					if len(csf_found) == len(concave_csfs):
						heap = []
						break

			if node is not fork and node.is_fork:
				d_ff = math.hypot(node.x - fork.x, node.y - fork.y)
				if d_ff < fork.radius + node.radius:
					continue

			for nb in node.neighbors:
				nb_id = id(nb)
				if nb_id in visited:
					continue
				visited.add(nb_id)
				edge_len = math.hypot(nb.x - node.x, nb.y - node.y)
				new_dist = dist + edge_len
				if new_dist < dist_to.get(nb_id, float('inf')):
					dist_to[nb_id] = new_dist
					pred[nb_id] = _nid
					node_map[nb_id] = nb
					heapq.heappush(heap, (new_dist, nb_id, nb))

		# Assign found concavities to sectors
		for csf in concave_csfs:
			cid = id(csf)
			if cid not in csf_found:
				continue

			path_len, end_nid = csf_found[cid]
			ex_x, ex_y = csf.extremum

			angle_to_c = math.degrees(math.atan2(ex_y - fork.y, ex_x - fork.x)) % 360.0

			sector_idx = None
			for si, sector in enumerate(sa.sectors):
				if _angle_in_sector(angle_to_c, sector):
					sector_idx = si
					break

			if sector_idx is None:
				continue

			# Reconstruct path for convex-rib disambiguation
			path = []
			cur_id = end_nid
			while cur_id is not None:
				path.append(node_map[cur_id])
				cur_id = pred[cur_id]
			path.reverse()

			if _path_crosses_convex_rib(path, convex_csfs, _convex_disks=_convex_disks):
				continue

			r = csf.disk_radius
			if r < _EPS:
				continue
			score = 2.0 * path_len / (r * r)

			sa.assign(sector_idx, csf, score)

		if any(c is not None for c in sa.assignments):
			result[id(fork)] = sa

	return result


def fork_concavity_map(sector_assignments):
	"""Flatten sector assignments into a simple fork_id → [CSF] dict."""
	result = {}
	for fork_id, sa in sector_assignments.items():
		csfs_for_fork = [c for c in sa.assignments if c is not None]
		if csfs_for_fork:
			result[fork_id] = csfs_for_fork
	return result
