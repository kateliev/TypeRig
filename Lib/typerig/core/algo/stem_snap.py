# MODULE: TypeRig / Core / Algo / Stem Snap
# -----------------------------------------------------------
# Node-level stem detection, capture audit, and IUP-cascade
# snap. Operates on raw Contour nodes — no stroke decomposition,
# no medial axis. Companion to the heavier stroke_snap pipeline
# (see core/algo/stroke_snap.py).
#
# Pipeline:
#   StemDetector -> [StemCandidate]      (with topology gate)
#   StemAuditor  -> [StemViolation]      (capture semantics)
#   StemFixer    -> StemCorrectionPlan -> apply()
#
# Capture semantics: only stems whose width falls inside a
# declared target's band are captured and snapped to the
# target's canonical value. Stems outside every band are
# silently left alone — the allowlist makes no claim on them.
#
# Topology gate: a stem candidate is valid iff its two edges
# are on the same contour OR one contour strictly contains
# the other (counter-and-outer). Sibling-contour pairings
# (e.g. inter-stroke gaps in CJK 川) are rejected — they are
# not stems.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.algo._width_audit import (
	WidthTarget, WidthAllowlist, Violation,
)
# Reuse the layered containment predicate from matchmaker — bbox + area
# ratio + on-curve point-in-polygon. Already vetted for CJK siblings.
from typerig.core.algo.matchmaker import _contour_strictly_contains

__version__ = '0.2.0'


# - Axis enum ---------------------------
class Axis(object):
	V = 'V'   # vertical stem; faces walk along +/- Y
	H = 'H'   # horizontal stem; faces walk along +/- X


# - Detector mode enum ------------------
class DetectMode(object):
	EXTREMA   = 'extrema'    # tangent-based: needs proper extrema-inserted contours
	COINCIDENT = 'coincident' # geometry-only: clusters on-curves by shared coord


# - Topology mode enum ------------------
class Topology(object):
	'''Restrict which contour-pair relationships qualify as stems.

	STRICT (default): allow intra-contour pairs and counter/outer pairs
	                  (one contour strictly contains the other). Sibling
	                  pairings rejected.
	PERMISSIVE      : allow any pair satisfying the geometric rule
	                  (mutual-nearest + span overlap). Useful when you
	                  want to measure inter-stroke gaps as if they were
	                  stems.
	'''
	STRICT     = 'strict'
	PERMISSIVE = 'permissive'


# - Tunables ----------------------------
_DEFAULT_TANGENT_DEG       = 3.0    # tangent must be within this of the axis
_DEFAULT_COINCIDENT_TOL    = 1.0    # coord clustering tolerance (font units)
_DEFAULT_SPAN_OVERLAP_FRAC = 0.05   # required perpendicular overlap (fraction of min span)


# - Internal helpers --------------------
def _classify_dir(dx, dy, tangent_deg=_DEFAULT_TANGENT_DEG, eps_pos=1e-6):
	'''Classify a direction vector as V-aligned, H-aligned, or neither.

	Returns (axis, sign) where axis in {'V','H',None} and sign in {-1,+1,0}.
	  V/+1 = +Y (north); V/-1 = -Y (south).
	  H/+1 = +X (east);  H/-1 = -X (west).
	'''
	mag = math.hypot(dx, dy)
	if mag < eps_pos:
		return None, 0
	tol = math.radians(tangent_deg)
	sin_tol = math.sin(tol)
	if abs(dx) / mag <= sin_tol:
		return Axis.V, (1 if dy > 0 else -1)
	if abs(dy) / mag <= sin_tol:
		return Axis.H, (1 if dx > 0 else -1)
	return None, 0


def _outgoing_dir(node):
	nxt = node.next
	return (nxt.x - node.x, nxt.y - node.y)


def _incoming_dir(node):
	prv = node.prev
	return (node.x - prv.x, node.y - prv.y)


def _build_topology_matrix(contours):
	'''Returns a function ok(i, j) that tells whether the contour pair
	(i, j) qualifies as a stem-relationship topology under STRICT mode.

	Containment is computed once with a layered geometric test (bbox +
	area-ratio + point-in-polygon). Result cached in a 2D array.
	'''
	n = len(contours)
	# contains[i][j] == True iff contour i strictly contains contour j.
	contains = [[False] * n for _ in range(n)]
	for i in range(n):
		for j in range(n):
			if i == j:
				continue
			contains[i][j] = _contour_strictly_contains(contours[i], contours[j])

	def ok(i, j):
		if i == j:
			return True
		return contains[i][j] or contains[j][i]
	return ok


# - Edge dataclass ----------------------
class StemEdge(object):
	'''A maximal run of consecutive on-curve nodes whose local contour
	tangent is axis-aligned in a single direction. May be a single node
	(curve extremum) or many (straight stem face with intermediate nodes).
	'''
	__slots__ = ('axis', 'contour_idx', 'node_indices', 'coord',
	             'tangent_sign', 'span')

	def __init__(self, axis, contour_idx, node_indices, coord, tangent_sign, span):
		self.axis = axis
		self.contour_idx = contour_idx
		self.node_indices = list(node_indices)
		self.coord = float(coord)
		self.tangent_sign = int(tangent_sign)
		self.span = (float(span[0]), float(span[1]))

	def __repr__(self):
		return ('StemEdge({}, c={}, nodes={}, coord={:.2f}, '
		        'sign={:+d}, span=[{:.2f},{:.2f}])').format(
			self.axis, self.contour_idx, self.node_indices, self.coord,
			self.tangent_sign, self.span[0], self.span[1])


class StemCandidate(object):
	'''A pair of opposing stem edges plus the measured width between them.'''
	__slots__ = ('edge_a', 'edge_b', 'axis', 'measured_width')

	def __init__(self, edge_a, edge_b, axis, measured_width):
		self.edge_a = edge_a
		self.edge_b = edge_b
		self.axis = axis
		self.measured_width = float(measured_width)

	def __repr__(self):
		return 'StemCandidate(axis={}, w={:.2f})'.format(self.axis, self.measured_width)


# - Stem violation alias ----------------
class StemViolation(Violation):
	'''Violation whose .source is a StemCandidate.'''
	pass


# - Plan dataclass ----------------------
class StemCorrectionPlan(object):
	'''Ephemeral per-node delta map keyed by (contour_idx, node_idx).'''
	__slots__ = ('deltas', 'meta')

	def __init__(self):
		self.deltas = {}
		self.meta = {}

	def add(self, contour_idx, node_idx, dx, dy):
		key = (contour_idx, node_idx)
		cur = self.deltas.get(key)
		if cur is None:
			self.deltas[key] = [float(dx), float(dy)]
		else:
			cur[0] += float(dx)
			cur[1] += float(dy)

	def __len__(self):
		return len(self.deltas)


# - Detector ----------------------------
class StemDetector(object):
	'''Finds StemCandidates in one or more contours.

	mode      = EXTREMA / COINCIDENT (see DetectMode).
	topology  = STRICT (default) / PERMISSIVE (see Topology).
	'''
	def __init__(self,
	             mode=DetectMode.EXTREMA,
	             topology=Topology.STRICT,
	             tangent_deg=_DEFAULT_TANGENT_DEG,
	             coincident_tol=_DEFAULT_COINCIDENT_TOL,
	             span_overlap_frac=_DEFAULT_SPAN_OVERLAP_FRAC):
		self.mode = mode
		self.topology = topology
		self.tangent_deg = float(tangent_deg)
		self.coincident_tol = float(coincident_tol)
		self.span_overlap_frac = float(span_overlap_frac)

	def detect(self, contours, axis=None):
		'''Detect stem candidates across `contours`.

		Args:
			contours: list[Contour].
			axis: optionally restrict to Axis.V or Axis.H. None = both.

		Returns:
			list[StemCandidate]
		'''
		if self.mode == DetectMode.EXTREMA:
			edges = self._edges_extrema(contours, axis)
		elif self.mode == DetectMode.COINCIDENT:
			edges = self._edges_coincident(contours, axis)
		else:
			raise ValueError('unknown detector mode: {!r}'.format(self.mode))

		if self.topology == Topology.STRICT:
			topo_ok = _build_topology_matrix(contours)
		else:
			topo_ok = lambda i, j: True
		return self._pair_edges(edges, topo_ok)

	# -- extrema mode --
	def _edges_extrema(self, contours, axis_filter):
		'''Segment-based grouping. A "stem edge" is a maximal run of
		consecutive on-curves connected by axis-aligned segments of the
		same direction; or a curve extremum (smooth node where the
		tangent — bisector of in/out directions — is axis-aligned).
		'''
		all_edges = []
		classes = []
		for ax in (Axis.V, Axis.H):
			if axis_filter is not None and axis_filter != ax:
				continue
			classes.extend([(ax, +1), (ax, -1)])

		for ci, contour in enumerate(contours):
			nodes = list(contour.nodes)
			if not nodes:
				continue
			closed = bool(getattr(contour, 'closed', True))

			on_curve_indices = [i for i, nd in enumerate(nodes) if nd.is_on]
			m = len(on_curve_indices)
			if m == 0:
				continue

			seg_class = []
			for i in on_curve_indices:
				ax, sign = _classify_dir(*_outgoing_dir(nodes[i]),
				                          tangent_deg=self.tangent_deg)
				seg_class.append((ax, sign) if ax is not None else None)

			tangent_class = []
			for i in on_curve_indices:
				out_dir = _outgoing_dir(nodes[i])
				in_dir = _incoming_dir(nodes[i])
				avg = (out_dir[0] + in_dir[0], out_dir[1] + in_dir[1])
				ax, sign = _classify_dir(*avg, tangent_deg=self.tangent_deg)
				out_cls = _classify_dir(*out_dir, tangent_deg=self.tangent_deg)
				in_cls = _classify_dir(*in_dir, tangent_deg=self.tangent_deg)
				if (ax is not None and out_cls[0] == ax and in_cls[0] == ax
				    and out_cls[1] == sign and in_cls[1] == sign):
					tangent_class.append((ax, sign))
				else:
					tangent_class.append(None)

			for ax, sign in classes:
				hits = [seg_class[k] == (ax, sign) for k in range(m)]
				runs = []

				if any(hits):
					if closed and all(hits):
						runs.append([on_curve_indices[k] for k in range(m)])
					else:
						start = 0
						for k in range(m):
							prev = (k - 1) % m if closed else (k - 1)
							if prev < 0 or not hits[prev]:
								if hits[k]:
									start = k
									break
						cur_nodes = []
						count = 0
						k = start
						while count < m:
							if hits[k]:
								if not cur_nodes:
									cur_nodes = [on_curve_indices[k]]
								nxt = (k + 1) % m if closed else (k + 1)
								if 0 <= nxt < m:
									if not cur_nodes or cur_nodes[-1] != on_curve_indices[nxt]:
										cur_nodes.append(on_curve_indices[nxt])
							else:
								if cur_nodes:
									runs.append(cur_nodes)
									cur_nodes = []
							k = (k + 1) % m if closed else (k + 1)
							count += 1
							if not closed and k >= m:
								break
						if cur_nodes:
							runs.append(cur_nodes)

				for k in range(m):
					if tangent_class[k] != (ax, sign):
						continue
					if seg_class[k] == (ax, sign):
						continue
					prev = (k - 1) % m if closed else (k - 1)
					if 0 <= prev < m and seg_class[prev] == (ax, sign):
						continue
					runs.append([on_curve_indices[k]])

				for idxs in runs:
					if not idxs:
						continue
					if ax == Axis.V:
						coord = sum(nodes[i].x for i in idxs) / float(len(idxs))
						ys = [nodes[i].y for i in idxs]
						span = (min(ys), max(ys))
					else:
						coord = sum(nodes[i].y for i in idxs) / float(len(idxs))
						xs = [nodes[i].x for i in idxs]
						span = (min(xs), max(xs))
					all_edges.append(StemEdge(ax, ci, idxs, coord, sign, span))

		return all_edges

	# -- coincident mode --
	def _edges_coincident(self, contours, axis_filter):
		edges = []
		for ax in (Axis.V, Axis.H):
			if axis_filter is not None and axis_filter != ax:
				continue
			for ci, contour in enumerate(contours):
				nodes = list(contour.nodes)
				on_idxs = [i for i, nd in enumerate(nodes) if nd.is_on]
				if not on_idxs:
					continue
				key_of = (lambda nd: nd.x) if ax == Axis.V else (lambda nd: nd.y)
				perp_of = (lambda nd: nd.y) if ax == Axis.V else (lambda nd: nd.x)

				ordered = sorted(on_idxs, key=lambda i: key_of(nodes[i]))
				cluster = [ordered[0]]
				for i in ordered[1:]:
					if abs(key_of(nodes[i]) - key_of(nodes[cluster[-1]])) <= self.coincident_tol:
						cluster.append(i)
					else:
						if len(cluster) >= 2:
							self._emit_coincident_edge(edges, ax, ci, cluster, nodes,
							                           key_of, perp_of)
						cluster = [i]
				if len(cluster) >= 2:
					self._emit_coincident_edge(edges, ax, ci, cluster, nodes,
					                           key_of, perp_of)
		return edges

	def _emit_coincident_edge(self, edges, axis, ci, cluster, nodes, key_of, perp_of):
		coord = sum(key_of(nodes[i]) for i in cluster) / float(len(cluster))
		perps = [perp_of(nodes[i]) for i in cluster]
		edges.append(StemEdge(axis, ci, list(cluster), coord, 0,
		                     (min(perps), max(perps))))

	# -- pairing --
	def _pair_edges(self, edges, topo_ok):
		'''Mutual-nearest pairing among opposite-sign, span-overlapping
		edges, gated by the topology predicate.
		'''
		n = len(edges)
		nearest = [-1] * n
		for i, e1 in enumerate(edges):
			best = -1
			best_dist = float('inf')
			for j, e2 in enumerate(edges):
				if j == i:
					continue
				if e1.axis != e2.axis:
					continue
				if e1.tangent_sign != 0 and e2.tangent_sign != 0:
					if e1.tangent_sign == e2.tangent_sign:
						continue
				if not topo_ok(e1.contour_idx, e2.contour_idx):
					continue
				ov = self._overlap(e1.span, e2.span)
				min_span = min(e1.span[1] - e1.span[0], e2.span[1] - e2.span[0])
				if min_span > 0 and ov < min_span * self.span_overlap_frac:
					continue
				if min_span <= 0 and ov < 0:
					continue
				d = abs(e1.coord - e2.coord)
				if d < best_dist:
					best_dist = d
					best = j
			nearest[i] = best

		out = []
		seen = set()
		for i, j in enumerate(nearest):
			if j < 0:
				continue
			if nearest[j] != i:
				continue
			key = (i, j) if i < j else (j, i)
			if key in seen:
				continue
			seen.add(key)
			ea, eb = edges[i], edges[j]
			if ea.coord > eb.coord:
				ea, eb = eb, ea
			out.append(StemCandidate(ea, eb, ea.axis, abs(eb.coord - ea.coord)))
		return out

	@staticmethod
	def _overlap(span_a, span_b):
		lo = max(span_a[0], span_b[0])
		hi = min(span_a[1], span_b[1])
		return hi - lo


# - Auditor -----------------------------
class StemAuditor(object):
	'''Maps StemCandidate measurements to violations under capture
	semantics: only candidates whose measured_width falls inside some
	target's band become violations. Out-of-band stems are silently
	ignored.
	'''

	def __init__(self, allowlist, drop_zero_delta=False):
		'''If drop_zero_delta=True, measurements that are already exactly
		on a target value are filtered out (no entry in the violation
		list). Default False so callers can count "already-on-target"
		stems for QA.
		'''
		if not isinstance(allowlist, WidthAllowlist):
			raise TypeError('StemAuditor needs a WidthAllowlist')
		self.allowlist = allowlist
		self.drop_zero_delta = bool(drop_zero_delta)

	def audit(self, candidates):
		violations = []
		for cand in candidates:
			res = self.allowlist.capture(cand.axis, cand.measured_width)
			if res is None:
				continue
			target, delta = res
			if self.drop_zero_delta and delta == 0.0:
				continue
			violations.append(StemViolation(
				key=cand.axis,
				measured=cand.measured_width,
				target=target,
				delta=delta,
				source=cand,
			))
		return violations


# - Fixer (IUP cascade) -----------------
class StemFixer(object):
	'''Builds and applies a StemCorrectionPlan via the IUP cascade.'''

	def __init__(self, anchor='lower'):
		if anchor not in ('lower', 'upper'):
			raise ValueError('anchor must be \'lower\' or \'upper\'')
		self.anchor = anchor

	def plan_iup(self, violations, contours, eps=1e-6):
		plan = StemCorrectionPlan()

		for v in violations:
			cand = v.source
			if self.anchor == 'lower':
				anchor_edge, target_edge = cand.edge_a, cand.edge_b
				signed = +1
			else:
				anchor_edge, target_edge = cand.edge_b, cand.edge_a
				signed = -1

			delta_mag = v.target.value - cand.measured_width
			if delta_mag == 0.0:
				continue   # already on target — no shift needed
			d = signed * delta_mag

			cont = contours[target_edge.contour_idx]
			nodes = list(cont.nodes)
			cut = target_edge.coord

			if cand.axis == Axis.V:
				dx, dy = d, 0.0
				get = (lambda nd: nd.x)
			else:
				dx, dy = 0.0, d
				get = (lambda nd: nd.y)

			if self.anchor == 'lower':
				included = lambda v_, _cut=cut, _e=eps: v_ >= _cut - _e
			else:
				included = lambda v_, _cut=cut, _e=eps: v_ <= _cut + _e

			for ni, nd in enumerate(nodes):
				if included(get(nd)):
					plan.add(target_edge.contour_idx, ni, dx, dy)

		return plan

	def apply(self, plan, contours):
		for (ci, ni), (dx, dy) in plan.deltas.items():
			if dx == 0.0 and dy == 0.0:
				continue
			contours[ci].nodes[ni].shift(dx, dy)
		return contours


# =====================================================================
# Stage 7-style self-tests.
# =====================================================================

def _approx(a, b, tol=1e-6):
	return abs(a - b) <= tol


def _make_rect_contour(x, y, w, h):
	'''CCW rectangle: bottom-left -> bottom-right -> top-right -> top-left.'''
	nodes = [Node(x, y), Node(x + w, y), Node(x + w, y + h), Node(x, y + h)]
	return Contour(nodes, closed=True)


def _make_cw_rect_contour(x, y, w, h):
	'''CW rectangle (e.g. for an inner counter contour).'''
	nodes = [Node(x, y), Node(x, y + h), Node(x + w, y + h), Node(x + w, y)]
	return Contour(nodes, closed=True)


def _make_h_glyph(stem_w=80, bar_h=40, glyph_w=400, glyph_h=600):
	sw, gw, gh = stem_w, glyph_w, glyph_h
	mid_lo = (gh - bar_h) / 2.0
	mid_hi = (gh + bar_h) / 2.0
	pts = [
		(0, 0), (sw, 0), (sw, mid_lo), (gw - sw, mid_lo),
		(gw - sw, 0), (gw, 0), (gw, gh), (gw - sw, gh),
		(gw - sw, mid_hi), (sw, mid_hi), (sw, gh), (0, gh),
	]
	return Contour([Node(x, y) for (x, y) in pts], closed=True)


# --- Stage 1: capture-band semantics ---

def _test_target_captures():
	t = WidthTarget(29, 5, 5)   # band [24, 34], snap-to 29
	assert t.captures(24.0) and t.captures(34.0)
	assert t.captures(29.0)
	assert not t.captures(23.9) and not t.captures(34.1)
	assert _approx(t.correction(31.0), -2.0)
	assert _approx(t.correction(20.0), 9.0)
	# Symmetric band still snaps to value, not band centre (here they coincide).
	print('  WidthTarget(29, 5, 5) captures [24, 34], snaps to 29 [OK]')


def _test_allowlist_capture_in_band():
	al = WidthAllowlist({'V': [WidthTarget(29, 5, 5)]})
	res = al.capture('V', 31.0)
	assert res is not None
	t, d = res
	assert t.value == 29 and _approx(d, -2.0)
	print('  capture in-band: 31 -> target 29, d=-2 [OK]')


def _test_allowlist_out_of_band_silent():
	'''Out-of-band measurements MUST return None — the allowlist makes
	no claim on them. This is the core capture-semantic invariant.'''
	al = WidthAllowlist({'V': [WidthTarget(29, 5, 5)]})
	assert al.capture('V', 88.0) is None, 'out-of-band must be silent'
	assert al.capture('V', 23.9) is None
	assert al.capture('V', 34.1) is None
	print('  out-of-band measurements -> None (silent, no claim) [OK]')


def _test_allowlist_overlapping_bands_nearer_wins():
	al = WidthAllowlist({'V': [WidthTarget(25, 10, 10),
	                           WidthTarget(35, 10, 10)]})
	# 30 is captured by both bands ([15,35] and [25,45]). Closer-by-value
	# is 25 (dist 5) vs 35 (dist 5) — tie, earlier wins -> 25.
	res = al.capture('V', 30.0)
	assert res is not None and res[0].value == 25
	# 32 closer to 35.
	res2 = al.capture('V', 32.0)
	assert res2 is not None and res2[0].value == 35
	# 50 outside both -> None.
	assert al.capture('V', 50.0) is None
	print('  overlapping bands: nearer-by-value wins, ties to earlier [OK]')


def _run_stage1_tests():
	print('Stage 1 - capture semantics:')
	_test_target_captures()
	_test_allowlist_capture_in_band()
	_test_allowlist_out_of_band_silent()
	_test_allowlist_overlapping_bands_nearer_wins()
	print('Stage 1: all tests passed.')


# --- Stage 2: detector (extrema mode) ---

def _test_extrema_rect():
	c = _make_rect_contour(0, 0, 200, 100)
	det = StemDetector(mode=DetectMode.EXTREMA)
	cands = det.detect([c])
	axes = sorted(c.axis for c in cands)
	assert axes == [Axis.H, Axis.V]
	v = next(c_ for c_ in cands if c_.axis == Axis.V)
	h = next(c_ for c_ in cands if c_.axis == Axis.H)
	assert _approx(v.measured_width, 200.0)
	assert _approx(h.measured_width, 100.0)
	print('  rect: V=200, H=100 [OK]')


def _test_extrema_h_glyph():
	gly = _make_h_glyph(stem_w=80, bar_h=40, glyph_w=400, glyph_h=600)
	det = StemDetector(mode=DetectMode.EXTREMA)
	cands_v = det.detect([gly], axis=Axis.V)
	v_widths = sorted(round(c.measured_width, 3) for c in cands_v)
	assert v_widths.count(80.0) == 2, 'expected two V=80, got {}'.format(v_widths)
	cands_h = det.detect([gly], axis=Axis.H)
	h_widths = [round(c.measured_width, 3) for c in cands_h]
	assert 40.0 in h_widths, 'expected H=40 (bar) in {}'.format(h_widths)
	print('  H-glyph: 2x V=80, H bar=40 found [OK]')


def _run_stage2_tests():
	print('Stage 2 - StemDetector (extrema):')
	_test_extrema_rect()
	_test_extrema_h_glyph()
	print('Stage 2: all tests passed.')


# --- Stage 3: topology gate ---

def _test_topology_strict_rejects_siblings():
	'''Two sibling rectangles 30 units apart. Geometrically they look like
	a V-stem of width 30; topologically they're siblings (neither contains
	the other) — must be rejected under STRICT.'''
	a = _make_rect_contour(0,   0, 60, 600)    # right face at x=60
	b = _make_rect_contour(90,  0, 60, 600)    # left face at x=90; gap = 30
	det_strict = StemDetector(mode=DetectMode.EXTREMA, topology=Topology.STRICT)
	cands = det_strict.detect([a, b], axis=Axis.V)
	# Each rectangle has its own intra-contour stem of 60. The 30-unit
	# inter-contour sibling pair must NOT appear.
	widths = sorted(round(c.measured_width, 3) for c in cands)
	assert widths == [60.0, 60.0], \
		'STRICT: expected only intra-contour stems [60,60], got {}'.format(widths)
	# Confirm none of the candidates spans the two contours.
	for c in cands:
		assert c.edge_a.contour_idx == c.edge_b.contour_idx, \
			'STRICT must not pair across siblings: {}'.format(c)
	print('  STRICT: sibling-contour pair rejected; only intra-contour stems found [OK]')


def _test_topology_permissive_finds_siblings():
	'''PERMISSIVE re-enables the geometric-only behavior: the closer-than-
	intra inter-contour pair wins via mutual-nearest.'''
	a = _make_rect_contour(0,   0, 60, 600)    # intra stem = 60
	b = _make_rect_contour(90,  0, 60, 600)    # inter gap = 30
	det = StemDetector(mode=DetectMode.EXTREMA, topology=Topology.PERMISSIVE)
	cands = det.detect([a, b], axis=Axis.V)
	widths = sorted(round(c.measured_width, 3) for c in cands)
	# Mutual-nearest will pick the 30-unit pair (sibling) over 60s.
	assert 30.0 in widths, 'PERMISSIVE: expected 30 in {}'.format(widths)
	print('  PERMISSIVE: sibling pair allowed (width=30 detected) [OK]')


def _test_topology_counter_pair_allowed():
	'''Outer contour with a counter inside (an O-shape made of nested
	rectangles). The outer-right face and counter-right face form a real
	V-stem under STRICT — containment is not a sibling relationship.'''
	outer = _make_rect_contour(0, 0, 200, 600)        # CCW outer
	counter = _make_cw_rect_contour(40, 40, 120, 520) # CW inner counter
	det = StemDetector(mode=DetectMode.EXTREMA, topology=Topology.STRICT)
	cands = det.detect([outer, counter], axis=Axis.V)
	widths = sorted(round(c.measured_width, 3) for c in cands)
	# Expected stems on V: 40 (left wall) and 40 (right wall) — width =
	# (counter.x - outer.x) on the left, (outer.right - counter.right) on
	# the right. Both equal 40.
	# Plus the intra-contour widths of the counter (120) and outer (200).
	# Mutual-nearest will pair: outer-left ↔ counter-left (40), outer-right
	# ↔ counter-right (40). Counter and outer self-pairings lose to those.
	assert widths.count(40.0) >= 2, \
		'expected at least two 40-wide V-stems (counter walls), got {}'.format(widths)
	# Confirm at least one cross-contour pair survived (proving the
	# topology gate let the counter through).
	cross = [c for c in cands if c.edge_a.contour_idx != c.edge_b.contour_idx]
	assert cross, 'counter/outer pair was rejected under STRICT — gate bug'
	print('  STRICT: counter/outer pair allowed (containment OK) [OK]')


def _run_stage3_tests():
	print('Stage 3 - topology gate:')
	_test_topology_strict_rejects_siblings()
	_test_topology_permissive_finds_siblings()
	_test_topology_counter_pair_allowed()
	print('Stage 3: all tests passed.')


# --- Stage 4: capture audit ---

def _test_audit_in_band_captured():
	c = _make_rect_contour(0, 0, 31, 600)   # V=31, in [24,34]
	det = StemDetector()
	cands = det.detect([c], axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	assert len(violations) == 1
	v = violations[0]
	assert v.target.value == 29
	assert _approx(v.delta, -2.0)
	print('  in-band V=31 captured -> snap to 29, d=-2 [OK]')


def _test_audit_out_of_band_silent():
	c = _make_rect_contour(0, 0, 88, 600)   # V=88, well outside [24,34]
	det = StemDetector()
	cands = det.detect([c], axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	assert violations == [], 'out-of-band V=88 must NOT produce a violation'
	print('  out-of-band V=88 silent (no violation) [OK]')


def _test_audit_already_on_value():
	'''Default behavior: emit zero-delta violations (count "already-exact"
	stems for stats). drop_zero_delta=True filters them out.'''
	c = _make_rect_contour(0, 0, 29, 600)
	det = StemDetector()
	cands = det.detect([c], axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	v_default = StemAuditor(al).audit(cands)
	v_dropped = StemAuditor(al, drop_zero_delta=True).audit(cands)
	assert len(v_default) == 1 and v_default[0].delta == 0.0
	assert v_dropped == []
	print('  already-on-value: default keeps (d=0); drop_zero_delta filters [OK]')


def _test_audit_sibling_no_false_positive():
	'''The end-to-end concern: two sibling strokes 30 apart, allowlist
	29 +/- 5. Without the topology gate the sibling gap (30) would be
	captured and "fixed". With STRICT, the auditor sees no inter-contour
	candidate and emits no violation for the gap.'''
	a = _make_rect_contour(0,   0, 60, 600)
	b = _make_rect_contour(90,  0, 60, 600)
	det = StemDetector(topology=Topology.STRICT)
	cands = det.detect([a, b], axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	# Both intra-contour stems are 60 wide -> out of band -> silent.
	# The 30-unit sibling gap is rejected by topology gate -> no candidate.
	assert violations == [], \
		'STRICT must not capture sibling gap: violations={}'.format(violations)
	print('  STRICT: sibling 30-unit gap NOT captured (no false positive) [OK]')


def _run_stage4_tests():
	print('Stage 4 - capture audit:')
	_test_audit_in_band_captured()
	_test_audit_out_of_band_silent()
	_test_audit_already_on_value()
	_test_audit_sibling_no_false_positive()
	print('Stage 4: all tests passed.')


# --- Stage 5: cascade fix under capture semantics ---

def _test_fixer_capture_snap():
	'''V=31, target 29. Captured -> delta=-2. Cascade shifts right face by
	-2 to x=29. Width becomes 29 exactly.'''
	c = _make_rect_contour(0, 0, 31, 600)
	contours = [c]
	det = StemDetector()
	cands = det.detect(contours, axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	plan = StemFixer(anchor='lower').plan_iup(violations, contours)
	StemFixer().apply(plan, contours)
	cands2 = det.detect(contours, axis=Axis.V)
	assert _approx(cands2[0].measured_width, 29.0)
	xs = sorted(set(round(nd.x, 6) for nd in c.nodes))
	assert xs == [0.0, 29.0]
	print('  capture+cascade: V=31 -> snap to 29, left locked [OK]')


def _test_fixer_zero_delta_no_op():
	'''V=29 already on target. Audit emits a zero-delta violation; cascade
	must not move any node.'''
	c = _make_rect_contour(0, 0, 29, 600)
	contours = [c]
	original = [(nd.x, nd.y) for nd in c.nodes]
	det = StemDetector()
	cands = det.detect(contours, axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	plan = StemFixer().plan_iup(violations, contours)
	StemFixer().apply(plan, contours)
	current = [(nd.x, nd.y) for nd in c.nodes]
	assert original == current, 'zero-delta must not move any node'
	print('  zero-delta cascade: nodes unchanged [OK]')


def _test_fixer_out_of_band_untouched():
	'''V=88, target 29 +/- 5. Out-of-band -> no violation -> no plan ->
	contour identical after apply.'''
	c = _make_rect_contour(0, 0, 88, 600)
	contours = [c]
	original = [(nd.x, nd.y) for nd in c.nodes]
	det = StemDetector()
	cands = det.detect(contours, axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	plan = StemFixer().plan_iup(violations, contours)
	StemFixer().apply(plan, contours)
	current = [(nd.x, nd.y) for nd in c.nodes]
	assert original == current
	assert len(plan) == 0
	print('  out-of-band V=88: empty plan, contour untouched [OK]')


def _run_stage5_tests():
	print('Stage 5 - StemFixer (capture + cascade):')
	_test_fixer_capture_snap()
	_test_fixer_zero_delta_no_op()
	_test_fixer_out_of_band_untouched()
	print('Stage 5: all tests passed.')


# --- Stage 6: end-to-end with multi-target allowlist ---

def _test_e2e_multi_target_selectivity():
	'''Two strokes: one in [24, 34], one in [83, 93], one outside both.
	Allowlist has both targets. Each captured stroke snaps to its own
	target; the third is silently left alone.'''
	thin   = _make_rect_contour(0,   0, 31, 600)    # captured by 29
	thick  = _make_rect_contour(200, 0, 91, 600)    # captured by 88
	weird  = _make_rect_contour(400, 0, 60, 600)    # uncovered
	contours = [thin, thick, weird]
	det = StemDetector(topology=Topology.STRICT)
	cands = det.detect(contours, axis=Axis.V)
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5),
	                              WidthTarget(88, 5, 5)]})
	violations = StemAuditor(al).audit(cands)
	# Two captured violations, one each.
	assert len(violations) == 2
	by_target = {v.target.value: v for v in violations}
	assert 29 in by_target and 88 in by_target
	assert _approx(by_target[29].delta, -2.0)
	assert _approx(by_target[88].delta, -3.0)

	plan = StemFixer().plan_iup(violations, contours)
	StemFixer().apply(plan, contours)
	cands2 = det.detect(contours, axis=Axis.V)
	widths = sorted(round(c.measured_width, 3) for c in cands2)
	# After: thin = 29, thick = 88, weird = 60 (unchanged).
	assert widths == [29.0, 60.0, 88.0], 'after multi-target snap: {}'.format(widths)
	print('  multi-target: 31->29, 91->88, 60 untouched [OK]')


def _run_stage6_tests():
	print('Stage 6 - end-to-end:')
	_test_e2e_multi_target_selectivity()
	print('Stage 6: all tests passed.')


if __name__ == '__main__':
	_run_stage1_tests()
	print()
	_run_stage2_tests()
	print()
	_run_stage3_tests()
	print()
	_run_stage4_tests()
	print()
	_run_stage5_tests()
	print()
	_run_stage6_tests()
	print()
	print('stem_snap: ALL STAGES PASSED')
