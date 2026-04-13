# MODULE: TypeRig / Core / Algo / Stroke Separator — Junction Identification
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Iterative junction identification (§7).

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict

from typerig.core.algo.stroke_sep_common import _EPS
from typerig.core.algo.stroke_sep_mat import branch_salience, _TAU_SIGMA
from typerig.core.algo.stroke_sep_links import good_continuation, Link


# ── §7: Iterative Junction Identification ─────────────────────────────────────
#
# Four-step procedure using auxiliary graph H (vertices = concavities assigned
# to forks, edges = valid links).
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
_W_T           = math.log(1.10)
_W_NULL        = math.log(0.95)
_W_DEFAULT     = 0.0

# Thresholds
_TAU_L         = 0.5
_SIGMA_MIN     = 1.5
_SIGMA_MIN_T   = 1.001
_HALF_PHI_C_TH = 0.25
_T_TO_HALF_PHI = 0.40


class JunctionResult(object):
	"""Identified junction for a single fork after the iterative procedure.

	Attributes:
		fork:        MATNode
		jtype:       JType constant
		link:        primary Link (T, half, protuberance) or None
		links:       [Link, Link] for half-junctions
		rep_csf:     representative concave CSF for Y/L junctions, or None
		cut_points:  list of ((x1,y1),(x2,y2)) pairs
		score:       float — aggregated π score
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
		# Vertices: id(csf) → csf — from link endpoints
		self._csfs = {}
		for link in links:
			self._csfs[id(link.csf1)] = link.csf1
			self._csfs[id(link.csf2)] = link.csf2

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

	def _fork_csf_ids(self, sa):
		"""CSF ids for this fork: primaries + link-participating candidates."""
		ids = set()
		for csf in sa.assignments:
			if csf is not None and id(csf) in self._csfs:
				ids.add(id(csf))
		for csf in sa.all_csfs:
			if id(csf) in self._csfs:
				ids.add(id(csf))
		return ids

	def links_for_fork(self, fork, sector_assignments):
		"""All H-links whose BOTH CSFs are candidates at this fork."""
		sa = sector_assignments.get(id(fork))
		if sa is None:
			return []
		fids = self._fork_csf_ids(sa)
		return [l for l in self._links.values()
				if id(l.csf1) in fids and id(l.csf2) in fids]

	def csfs_for_fork(self, fork, sector_assignments):
		"""All CSFs in H that are candidates at this fork and in the graph."""
		sa = sector_assignments.get(id(fork))
		if sa is None:
			return []
		return [csf for csf in sa.all_csfs if id(csf) in self._csfs]

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
	"""Concavity significance via Flamant elastic half-plane model (§7, Eq. 6-9)."""
	d = math.hypot(csf.extremum[0] - fork.x, csf.extremum[1] - fork.y)
	d = max(d, fork.radius, _EPS)
	return 2.0 * csf.disk_radius / (math.pi * d)


def _estimate_branch_area(fork, branch_neighbor):
	"""Approximate swept area of a branch = ∫ 2r ds."""
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
	"""Approximate coverage I = ln(A_after / A_before) (§7, Eq. 4)."""
	if branches is None:
		branches = _fork_branches(fork)
	if not branches:
		return 0.0

	areas = [_estimate_branch_area(fork, nb) for _, nb in branches]
	A_before = max(sum(areas), _EPS)

	if jtype in (JType.T, JType.HALF, JType.PROTUBERANCE):
		A_after = A_before
	elif jtype == JType.Y:
		A_after = A_before * 1.05
	elif jtype in (JType.L, JType.NULL):
		A_after = A_before - min(areas)
	elif jtype == JType.STROKE_END:
		sorted_areas = sorted(areas, reverse=True)
		A_after = sorted_areas[0] if sorted_areas else A_before * 0.4
	else:
		A_after = A_before

	return math.log(max(A_after, _EPS) / A_before)


def _smoothness_G(link):
	"""Smoothness G = ln Φ of the link's good-continuation (§7, Eq. 5)."""
	if link is not None:
		return math.log(max(link.good_continuation, _EPS))
	return 0.0


def _significance_C(fork, jtype, h_csfs, link=None):
	"""Concavity significance C via Flamant model (§7, Eq. 6-9)."""
	if not h_csfs:
		return 0.0

	if jtype == JType.T and link is not None:
		s1 = _flamant_significance(link.csf1, fork)
		s2 = _flamant_significance(link.csf2, fork)
		total = s1 + s2
		return 2.0 * s1 * s2 / total if total > _EPS else 0.0

	sigs  = [_flamant_significance(c, fork) for c in h_csfs]
	total = sum(sigs)
	return max(sigs) / total if total > _EPS else 0.0


def _omega(jtype):
	"""Type-specific log weight ω (§7, Eq. 14)."""
	if jtype == JType.T:
		return _W_T
	if jtype == JType.NULL:
		return _W_NULL
	return _W_DEFAULT


def _pi_score(I, G, C, S, omega, jtype_a, jtype_b):
	"""Compute π(J_a) for the pairwise comparison against J_b (§7, Eq. 14)."""
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

	Returns list of _Candidate.
	"""
	branches = _fork_branches(fork)
	if not branches:
		return []

	h_links = aux_graph.links_for_fork(fork, sector_assignments)
	h_csfs  = aux_graph.csfs_for_fork(fork, sector_assignments)
	sals    = [branch_salience(fork, nb) for _, nb in branches]

	candidates = []

	# Null-junction (always)
	candidates.append(_Candidate(JType.NULL, I=_coverage_I(fork, JType.NULL, branches)))

	# Stroke-end (when ≤1 salient branch)
	if sum(1 for s in sals if s > _TAU_SIGMA) <= 1:
		candidates.append(_Candidate(JType.STROKE_END,
									 I=_coverage_I(fork, JType.STROKE_END, branches)))

	# T-junction (one per valid link in H)
	for link in h_links:
		root_nb = link.protruding_branch
		non_root_ok = all(branch_salience(fork, nb) >= _SIGMA_MIN_T
						  for _, nb in branches if nb is not root_nb)
		if not non_root_ok:
			continue
		I = _coverage_I(fork, JType.T, branches)
		G = _smoothness_G(link)
		C = _significance_C(fork, JType.T, h_csfs, link=link)
		S = math.log(max(link.salience, _EPS))
		candidates.append(_Candidate(JType.T, link=link, I=I, G=G, C=C, S=S))

	# Y-junction (one config per salient root branch, requires H CSFs)
	if h_csfs:
		for (root_ang, root_nb), sal in zip(branches, sals):
			if sal <= _TAU_SIGMA:
				continue
			non_root_ok = all(branch_salience(fork, nb) >= _SIGMA_MIN
							  for _, nb in branches if nb is not root_nb)
			if not non_root_ok:
				continue
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

	# L-junction (most significant CSF if radius constraint met)
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
	"""Select the winning candidate via pairwise softmax aggregation (§7)."""
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
			m = max(pi_a, pi_b)
			log_p = pi_a - m - math.log(math.exp(pi_a - m) + math.exp(pi_b - m))
			log_prods[a] += log_p

	best = max(range(n), key=lambda i: log_prods[i])
	return candidates[best]


# ── 7.3: Step 8a — Protuberances ────────────────────────────────────────────

def identify_protuberances(valid_links):
	"""Step 8a: create a JunctionResult for each compound link (§7, Step 1)."""
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
	"""Combined good-continuation Φ_c(ℓ, ℓ') for a link pair (§7, Step 2)."""
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
	"""Step 8b: identify half-junctions from link pairs with Φ_c > 0.25 (§7, Step 2)."""
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
			if {id(la.csf1), id(la.csf2)} & {id(lb.csf1), id(lb.csf2)}:
				continue
			phi = _phi_c(la, lb, sigma_phi)
			if phi > _HALF_PHI_C_TH:
				pairs.append((phi, la, lb))

	pairs.sort(key=lambda x: x[0], reverse=True)

	committed = set()
	results   = []

	_bns_cache = {}
	def _cached_branch_node_set(link):
		lid = id(link)
		if lid not in _bns_cache:
			_bns_cache[lid] = _branch_node_set(link)
		return _bns_cache[lid]

	for phi, la, lb in pairs:
		if id(la) in committed or id(lb) in committed:
			continue
		if not aux_graph.has_link(la) or not aux_graph.has_link(lb):
			continue

		nodes_a = _cached_branch_node_set(la)
		nodes_b = _cached_branch_node_set(lb)
		if nodes_a & nodes_b:
			continue

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

		aux_graph.remove_link(la)
		aux_graph.remove_link(lb)

		crossing_nodes = nodes_a | nodes_b
		for other in list(aux_graph.links):
			if _cached_branch_node_set(other) & crossing_nodes:
				aux_graph.remove_link(other)

	return results


# ── 7.5: Step 8c — T/Y/L/Stroke-end/Null ───────────────────────────────────

def _build_fork_order(graph, aux_graph, sector_assignments):
	"""Return forks sorted by processing priority (§7, Eq. 14)."""
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
		return (group, -min_sal)

	return sorted(graph.forks(), key=_key)


def _project_cut_from_csf(fork, csf):
	"""Project a cut from csf.extremum through the fork to the opposing side."""
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
	jr.score   = cand.I + cand.omega

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
			aux_graph.remove_csf(link.csf1)
			aux_graph.remove_csf(link.csf2)
		else:
			aux_graph.remove_link(link)

	elif jr.jtype == JType.Y and jr.rep_csf is not None:
		aux_graph.remove_csf(jr.rep_csf)

	elif jr.jtype == JType.L:
		for csf in aux_graph.csfs_for_fork(jr.fork, sector_assignments):
			aux_graph.remove_csf(csf)


def identify_junctions_step3(graph, sector_assignments, aux_graph, contours,
							  sigma_phi=50.0):
	"""Step 8c: identify T/Y/L/Stroke-end/Null junctions (§7, Step 3)."""
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
	"""Step 8d: merge nearby T-junction pairs into half-junctions (§7, Step 4)."""
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

			phi = max(
				good_continuation(jra.link.csf1, jrb.link.csf1, sigma_phi),
				good_continuation(jra.link.csf1, jrb.link.csf2, sigma_phi),
				good_continuation(jra.link.csf2, jrb.link.csf1, sigma_phi),
				good_continuation(jra.link.csf2, jrb.link.csf2, sigma_phi),
			)
			if phi < _T_TO_HALF_PHI:
				continue

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
			break

	return [r for k, r in enumerate(step3_results) if k not in merged] + extra


# ── 7.7: Main entry point ────────────────────────────────────────────────────

def identify_junctions(valid_links, ligatures, sector_assignments, graph,
					   contours, sigma_phi=50.0):
	"""Run the full 4-step iterative junction identification procedure (§7).

	Returns:
		(protuberances, half_junctions, step3_junctions)
	"""
	aux = AuxGraph(valid_links, sector_assignments)

	protuberances  = identify_protuberances(valid_links)
	half_junctions = identify_half_junctions(
		valid_links, ligatures, sector_assignments, aux, sigma_phi)
	step3          = identify_junctions_step3(
		graph, sector_assignments, aux, contours, sigma_phi)
	step3          = convert_T_pairs_to_half(step3, sigma_phi)

	return protuberances, half_junctions, step3
