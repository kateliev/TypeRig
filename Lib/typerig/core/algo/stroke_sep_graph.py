# MODULE: TypeRig / Core / Algo / Stroke Separator — Stroke Graph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Stroke graph S and structural operations (§9).

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict

from typerig.core.algo.stroke_sep_mat import branch_salience, _TAU_SIGMA
from typerig.core.algo.stroke_sep_junctions import JType, JunctionResult


# ── 9.1: Branch extraction ───────────────────────────────────────────────────

class BranchVertex(object):
	"""One vertex in stroke graph S: a maximal path in M between topology nodes.

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

	Returns:
		list of BranchVertex
	"""
	topology   = frozenset(id(n) for n in list(graph.forks()) + list(graph.terminals()))
	vis_edges  = set()
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
	"""Graph S: vertices = branches, edges = same-stroke connections (§6.2)."""

	def __init__(self, branches):
		self._branches = {b.bid: b for b in branches}
		self._parent   = {b.bid: b.bid for b in branches}

		self._node_to_b = defaultdict(list)
		for b in branches:
			self._node_to_b[id(b.start)].append(b)
			if b.end is not b.start:
				self._node_to_b[id(b.end)].append(b)

	def _find(self, bid):
		while self._parent[bid] != bid:
			self._parent[bid] = self._parent[self._parent[bid]]
			bid = self._parent[bid]
		return bid

	def _union(self, bid1, bid2):
		r1, r2 = self._find(bid1), self._find(bid2)
		if r1 != r2:
			self._parent[r2] = r1

	def connect(self, b1, b2):
		if b1 is None or b2 is None or b1.discarded or b2.discarded:
			return
		self._union(b1.bid, b2.bid)

	def multitrace(self, branch):
		if branch is not None:
			branch.multitraced = True

	def discard(self, branch, recursive=False):
		if branch is None or branch.discarded:
			return
		branch.discarded = True
		if not recursive:
			return
		far_end = branch.end if branch.start.is_fork else branch.start
		if far_end.is_terminal:
			return
		for nb_branch in self._node_to_b.get(id(far_end), []):
			if nb_branch is branch or nb_branch.discarded:
				continue
			other = nb_branch.end if nb_branch.start is far_end else nb_branch.start
			if other.is_terminal or _all_paths_terminal(nb_branch, far_end, depth=5):
				self.discard(nb_branch, recursive=True)

	def branches_at(self, mat_node):
		return [b for b in self._node_to_b.get(id(mat_node), [])
				if not b.discarded]

	@property
	def active_branches(self):
		return [b for b in self._branches.values() if not b.discarded]

	def strokes(self):
		groups = defaultdict(list)
		for b in self._branches.values():
			if b.discarded:
				continue
			root = self._find(b.bid)
			groups[root].append(b)
		return list(groups.values())

	def finalize_strokes(self):
		for sid, group in enumerate(self.strokes()):
			for b in group:
				b.stroke_id = sid


def _all_paths_terminal(branch, entry_node, depth):
	"""Return True if all reachable branches lead to terminals within *depth* hops."""
	if depth <= 0:
		return False
	far = branch.end if branch.start is entry_node else branch.start
	if far.is_terminal:
		return True
	if far.is_fork:
		return False
	return True


# ── 9.3: Per-junction structural operations ───────────────────────────────────

def _branch_toward(branches_at_fork, fork, target_nb):
	for b in branches_at_fork:
		if b.neighbor_from(fork) is target_nb:
			return b
	return None


def _apply_T_to_graph(jr, sg):
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
		sg.multitrace(prot_b)


def _apply_Y_to_graph(jr, sg):
	fork = jr.fork
	if fork is None:
		return
	at_fork = sg.branches_at(fork)
	if len(at_fork) < 2:
		return
	sals = sorted(at_fork, key=lambda b: b.salience_at(fork), reverse=True)
	sg.connect(sals[0], sals[1])


def _apply_L_to_graph(jr, sg):
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
	"""Build stroke graph S and apply all junction structural operations (§6.2)."""
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
	"""Collect all outline cut pairs from identified junctions."""
	CUT_TYPES = {JType.T, JType.Y, JType.HALF, JType.PROTUBERANCE}
	cuts = []
	for jr in protuberances + half_junctions + step3_junctions:
		if jr.jtype in CUT_TYPES:
			cuts.extend(jr.cut_points)
	return cuts


# ── 9.6: Result class ────────────────────────────────────────────────────────

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
		step3_junctions: list[JunctionResult] — steps 8c+8d
		stroke_graph:    StrokeGraph — final S with connectivity + stroke IDs
		cuts:            list[((x1,y1),(x2,y2))]
	"""

	def __init__(self, graph, ext_graph, csfs, ligatures, links,
				 protuberances, half_junctions, step3_junctions,
				 stroke_graph, cuts, concavities=None):
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
		self.concavities      = concavities or []

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
