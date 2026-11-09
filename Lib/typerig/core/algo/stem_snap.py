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
# SPDX-License-Identifier: AGPL-3.0-only
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

__version__ = '0.3.0'


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
	INK             : STRICT plus sibling counters of one outer: the wall
	                  between two holes is ink, so the inner bars of a
	                  window (日 田) count as stems. Sibling outers and
	                  islands inside a hole stay rejected: white between.
	'''
	STRICT     = 'strict'
	PERMISSIVE = 'permissive'
	INK        = 'ink'


# - Cascade scope enum ------------------
class Cascade(object):
	'''Which contours a stem correction moves (StemFixer.plan_cascade).

	STEM   : only the contour(s) holding the two stem faces.
	FAMILY : the faces' contours plus everything they contain or are
	         contained by (outer + counters). Default: an 'o' keeps both
	         walls when one is snapped; separate CJK strokes stay put.
	LAYER  : every contour in the layer moves with the cascade.
	'''
	STEM   = 'stem'
	FAMILY = 'family'
	LAYER  = 'layer'


# - Tunables ----------------------------
_DEFAULT_TANGENT_DEG       = 3.0    # tangent must be within this of the axis
_DEFAULT_COINCIDENT_TOL    = 1.0    # coord clustering tolerance (font units)
_DEFAULT_SPAN_OVERLAP_FRAC = 0.05   # required perpendicular overlap (fraction of min span)
_DEFAULT_ALIGN_TOL         = 0.5    # faces this close before a fix count as aligned (font units)


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


def _build_topology_matrix(contours, sibling_counters=False):
	'''Returns a function ok(i, j) that tells whether the contour pair
	(i, j) qualifies as a stem-relationship topology under STRICT mode,
	or under INK mode with sibling_counters=True.

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

	# Nesting depth and direct parent: odd depth = hole.
	depth = [sum(1 for k in range(n) if contains[k][i]) for i in range(n)]
	parent = [next((k for k in range(n) if contains[k][i] and depth[k] == depth[i] - 1), -1)
	          for i in range(n)]

	def ok(i, j):
		if i == j:
			return True
		if contains[i][j] or contains[j][i]:
			return True
		return (sibling_counters and depth[i] == depth[j] and depth[i] % 2 == 1
		        and parent[i] == parent[j])
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

	def contains_point(self, point, strict=True):
		'''True iff `point` lies inside the rectangle bounded by the two face
		coords on the normal axis and by the intersection of the two faces'
		spans on the parallel axis.

		strict=True (default) excludes the boundary (open test).
		strict=False includes the boundary (closed test).
		'''
		px, py = point[0], point[1]
		c_lo = min(self.edge_a.coord, self.edge_b.coord)
		c_hi = max(self.edge_a.coord, self.edge_b.coord)
		span_lo = max(self.edge_a.span[0], self.edge_b.span[0])
		span_hi = min(self.edge_a.span[1], self.edge_b.span[1])
		if self.axis == Axis.V:
			normal_v, parallel_v = px, py
		else:
			normal_v, parallel_v = py, px
		if strict:
			return (c_lo < normal_v < c_hi) and (span_lo < parallel_v < span_hi)
		return (c_lo <= normal_v <= c_hi) and (span_lo <= parallel_v <= span_hi)


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

		if self.topology in (Topology.STRICT, Topology.INK):
			topo_ok = _build_topology_matrix(contours, sibling_counters=self.topology == Topology.INK)
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

			# Only line segments form straight faces. A curve segment's
			# outgoing direction is its handle, not the segment: an extremum
			# with an axis-aligned handle would otherwise be joined to the
			# next on-curve (e.g. right extremum + top extremum of an 'o').
			# Curve extrema are picked up below by tangent_class.
			seg_class = []
			for i in on_curve_indices:
				if not nodes[(i + 1) % len(nodes)].is_on:
					seg_class.append(None)
					continue
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
		if anchor not in ('lower', 'upper', 'center'):
			raise ValueError('anchor must be \'lower\', \'upper\' or \'center\'')
		self.anchor = anchor

	def plan_iup(self, violations, contours, eps=1e-6):
		'''Legacy plan: shift the nodes of the target-edge contour that lie
		beyond the cut. See plan_cascade() for the interpolating version.'''
		if self.anchor == 'center':
			raise ValueError('plan_iup supports \'lower\' / \'upper\' only; use plan_cascade')
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

	def plan_cascade(self, violations, contours, scope=Cascade.FAMILY, keep=(), pin_extremes=True, whole=False,
	                 protect_aligned=False, align_tol=_DEFAULT_ALIGN_TOL, eps=1e-6):
		'''IUP plan along each axis: stem faces are knots, everything else is
		interpolated between them (TrueType IUP on one axis).

		Each captured stem gives two knots: its lower face moves by d_lo and
		its upper face by d_hi, with (d_lo, d_hi) = (0, d) for anchor
		'lower', (-d, 0) for 'upper' and (-d/2, +d/2) for 'center',
		d = target - measured. Nodes between knots are interpolated (the
		counters absorb the change); nodes beyond the outermost knots move
		with the nearest one. Face nodes and their handles take their face
		value exactly, so every stem lands on target even when knots of
		different stems interleave.

		keep: StemCandidates that must not change width (e.g. stems already
		on target). Both their faces get the map's value at their centre,
		so interpolation between moved stems cannot bend them.

		pin_extremes: the lowest / highest coordinate of each group stays
		put unless it is a stem face (baseline, cap height, the side of a
		glyph beyond its last stem): the counters absorb the change.
		False: parts beyond the outermost stems move with them.

		whole: the outline will be rounded to integers afterwards. A
		'center' correction of a whole number of units is then split into
		whole units, (-(d // 2), d - d // 2): for an odd d the centre
		shifts half a unit up / right. Half-unit moves would round back
		(half to even) and leave the stem untouched or a unit off target.

		protect_aligned: with anchor 'center', a face already level with
		something the correction does not carry along stays put and the
		other face takes the whole correction, so aligned strokes do not
		drift apart. "Something" is an edge facing the same way (top with
		top) on a contour outside the stem's group, or a face of another
		stem. A level edge that also touches the face along its length
		outranks one elsewhere in the glyph; the better aligned face stays.
		With both faces equally aligned the stem is centred as usual.
		plan.meta lists the stems: 'aligned_kept' and 'aligned_both'.
		Explicit 'lower' / 'upper' anchors are not changed.

		scope picks the contours a stem acts on (see Cascade): the two
		face contours, their containment family (outer + counters, default)
		or the whole layer. Each group gets its own map, built from the
		stems with a face in it.

		Duplicate candidates (same axis, faces and contour set) count once.
		'''
		plan = StemCorrectionPlan()
		plan.meta.update(aligned_kept=[], aligned_both=[])
		protect = protect_aligned and self.anchor == 'center'
		family = contour_families(contours) if scope == Cascade.FAMILY else None

		def group_of(ci):
			if scope == Cascade.LAYER:
				return 0
			if scope == Cascade.FAMILY:
				return min(family[ci])
			return ci

		def members_of(cand):
			if scope == Cascade.LAYER:
				return set(range(len(contours)))
			if scope == Cascade.FAMILY:
				return family[cand.edge_a.contour_idx] | family[cand.edge_b.contour_idx]
			return {cand.edge_a.contour_idx, cand.edge_b.contour_idx}

		def evaluate(knots, c):
			if not knots:
				return 0.0
			if c <= knots[0][0]:
				return knots[0][1]
			if c >= knots[-1][0]:
				return knots[-1][1]
			for (c0, v0), (c1, v1) in zip(knots, knots[1:]):
				if c0 <= c <= c1:
					return v0 if c1 - c0 <= eps else v0 + (v1 - v0) * (c - c0) / (c1 - c0)
			return knots[-1][1]

		def merged(raw):
			'''Sort knots by coord; equal coords average.'''
			out = []
			for c, v in sorted(raw):
				if out and abs(out[-1][0] - c) <= eps:
					out[-1][2].append(v)
				else:
					out.append([c, None, [v]])
			return [(c, sum(vs) / len(vs)) for c, _, vs in out]

		def stem_key(cand):
			return (round(cand.edge_a.coord, 3), round(cand.edge_b.coord, 3))

		for axis in (Axis.V, Axis.H):
			raw = {}		# group -> [(coord, value)]
			face = {}		# (ci, ni) -> value
			touched = {}	# group -> members
			seen = set()

			edges = StemDetector()._edges_extrema(contours, axis) if protect else ()
			stem_faces = [(edge, stem_key(c)) for c in [v.source for v in violations] + list(keep)
			              if c.axis == axis for edge in (c.edge_a, c.edge_b)] if protect else ()

			def alignment(face, cand, members):
				'''How firmly a face is aligned with an edge the correction
				leaves behind or a face of another stem: 0 not aligned,
				1 level and facing the same way, 2 also touching along it.'''
				others = [e for e in edges if e.contour_idx not in members]
				others += [e for e, owner in stem_faces if owner != stem_key(cand)]
				level = [e for e in others if abs(e.coord - face.coord) <= align_tol
				         and (e.tangent_sign == face.tangent_sign or 0 in (e.tangent_sign, face.tangent_sign))]
				if not level:
					return 0
				touching = any(min(e.span[1], face.span[1]) - max(e.span[0], face.span[0]) >= -align_tol for e in level)
				return 2 if touching else 1

			for v in violations:
				cand = v.source
				d = v.target.value - cand.measured_width
				if cand.axis != axis or abs(d) <= eps:
					continue
				members = members_of(cand)
				key = (round(cand.edge_a.coord, 3), round(cand.edge_b.coord, 3), tuple(sorted(members)))
				if key in seen:
					continue
				seen.add(key)

				anchor = self.anchor
				if protect:
					low = alignment(cand.edge_a, cand, members)
					high = alignment(cand.edge_b, cand, members)
					if low != high:
						plan.meta['aligned_kept'].append(cand)
						anchor = 'lower' if low > high else 'upper'
					elif low:
						plan.meta['aligned_both'].append(cand)

				if anchor == 'lower':
					d_lo, d_hi = 0.0, d
				elif anchor == 'upper':
					d_lo, d_hi = -d, 0.0
				elif whole and abs(d - round(d)) <= eps:
					half = float(int(round(d)) // 2)
					d_lo, d_hi = -half, round(d) - half
				else:
					d_lo, d_hi = -0.5 * d, 0.5 * d

				for ci in members:
					g = group_of(ci)
					touched.setdefault(g, set()).add(ci)
					raw.setdefault(g, []).extend(((cand.edge_a.coord, d_lo), (cand.edge_b.coord, d_hi)))
				for edge, value in ((cand.edge_a, d_lo), (cand.edge_b, d_hi)):
					for ni in _with_handles(contours[edge.contour_idx], edge.node_indices):
						face[(edge.contour_idx, ni)] = value

			if not raw:
				continue

			# - Pinned extremes (unless a face sits there)
			pins = {}		# group -> [pinned coords]
			if pin_extremes:
				for g, members in touched.items():
					coords = [nd.x if axis == Axis.V else nd.y
					          for ci in members for nd in contours[ci].nodes]
					faces = [c for c, _ in raw[g]]
					for c in (min(coords), max(coords)):
						if all(abs(c - f) > eps for f in faces):
							raw[g].append((c, 0.0))
							pins.setdefault(g, []).append(c)

			# - Rigid stems: both faces follow the map at their centre
			knots = {g: merged(r) for g, r in raw.items()}
			for cand in keep:
				if cand.axis != axis:
					continue
				for ci in members_of(cand):
					g = group_of(ci)
					if g not in knots:
						continue
					lo, hi = cand.edge_a.coord, cand.edge_b.coord
					if any(lo - eps <= c <= hi + eps for c in pins.get(g, ())):
						value = 0.0		# the stem is the pinned extreme
					else:
						value = evaluate(knots[g], 0.5 * (lo + hi))
					raw[g].extend(((cand.edge_a.coord, value), (cand.edge_b.coord, value)))
					for edge in (cand.edge_a, cand.edge_b):
						for ni in _with_handles(contours[edge.contour_idx], edge.node_indices):
							face.setdefault((edge.contour_idx, ni), value)
			knots = {g: merged(r) for g, r in raw.items()}

			for g, members in touched.items():
				for ci in members:
					for ni, nd in enumerate(contours[ci].nodes):
						value = face.get((ci, ni))
						if value is None:
							value = evaluate(knots[g], nd.x if axis == Axis.V else nd.y)
						if value == 0.0:
							continue
						if axis == Axis.V:
							plan.add(ci, ni, value, 0.0)
						else:
							plan.add(ci, ni, 0.0, value)

		return plan

	def apply(self, plan, contours):
		for (ci, ni), (dx, dy) in plan.deltas.items():
			if dx == 0.0 and dy == 0.0:
				continue
			contours[ci].nodes[ni].shift(dx, dy)
		return contours


def _with_handles(contour, node_indices):
	'''Node indices plus the off-curve handles attached to them.'''
	nodes = contour.nodes
	n = len(nodes)
	out = set()
	for i in node_indices:
		out.add(i)
		for j in ((i - 1) % n, (i + 1) % n):
			if not nodes[j].is_on:
				out.add(j)
	return out


def contour_families(contours):
	'''Containment families: {contour_idx: set(contour indices)} where a
	family is the transitive closure of "strictly contains" (outer and its
	counters, counters' islands, ...). Siblings stay in separate families.'''
	n = len(contours)
	parent = list(range(n))

	def find(i):
		while parent[i] != i:
			parent[i] = parent[parent[i]]
			i = parent[i]
		return i

	for i in range(n):
		for j in range(n):
			if i != j and _contour_strictly_contains(contours[i], contours[j]):
				parent[find(j)] = find(i)

	groups = {}
	for i in range(n):
		groups.setdefault(find(i), set()).add(i)
	return {i: groups[find(i)] for i in range(n)}


def _shear(contours, slope):
	'''x -= y * slope for every node (slope = tan(italic angle)).'''
	if slope == 0.0:
		return
	for c in contours:
		for nd in c.nodes:
			nd.x -= nd.y * slope


class StemSnapReport(object):
	'''Result of snap_stems().

	candidates  -- every StemCandidate the detector found (after the
	               selection filter).
	captured    -- StemViolations inside some target band (zero deltas
	               included: "already on target").
	moved       -- the captured stems that needed a correction.
	out_of_band -- candidates no target claims (left alone).
	plan        -- the StemCorrectionPlan (empty on a dry run with
	               nothing to do).
	applied     -- True when the contours were changed.
	groups      -- [StemGroup] from equalize_stems(); empty for snap_stems().
	'''
	__slots__ = ('candidates', 'captured', 'moved', 'out_of_band', 'plan', 'applied', 'groups')

	def __init__(self):
		self.candidates, self.captured, self.moved, self.out_of_band = [], [], [], []
		self.plan = StemCorrectionPlan()
		self.applied = False
		self.groups = []

	def nodes(self, which='moved'):
		'''(contour_idx, node_idx) of the face nodes of `which` stems.'''
		out = set()
		for v in getattr(self, which):
			for e in (v.source.edge_a, v.source.edge_b):
				out.update((e.contour_idx, i) for i in e.node_indices)
		return out


def snap_stems(contours, allowlist, detector=None, axis=None,
               anchor='center', scope=Cascade.FAMILY, italic_angle=0.0,
               selected=None, round_ints=False, pin_extremes=True, apply=True,
               auditor=None, protect_aligned=True):
	'''Detect, audit and snap axis-aligned stems in one call.

	contours     -- list[Contour]; changed IN PLACE when apply is True.
	allowlist    -- WidthAllowlist keyed Axis.V / Axis.H (None with auditor).
	detector     -- StemDetector (default: extrema mode, strict topology).
	axis         -- Axis.V / Axis.H / None (both).
	anchor       -- 'lower' / 'upper' / 'center' (see StemFixer.plan_cascade).
	scope        -- Cascade.STEM / FAMILY / LAYER.
	italic_angle -- degrees; the outline is deslanted for detection and
	                the correction, then slanted back. Vertical stems of
	                an italic are measured perpendicular to the slant axis
	                in the upright frame (i.e. horizontally, as designers
	                and hinting stems measure them).
	selected     -- optional set of (contour_idx, node_idx): only stems
	                with a face node in it are processed.
	round_ints   -- round the moved nodes to integers.
	pin_extremes -- keep glyph extremes that are not stem faces in place
	                (see StemFixer.plan_cascade).
	apply        -- False = dry run; contours keep their coordinates.
	auditor      -- object with audit(candidates) -> [StemViolation] used
	                instead of StemAuditor(allowlist); see StemEqualizer.
	protect_aligned -- with anchor 'center', faces level with another part
	                stay put (see StemFixer.plan_cascade).

	Returns a StemSnapReport.
	'''
	det = detector if detector is not None else StemDetector()
	audit = auditor if auditor is not None else StemAuditor(allowlist)
	slope = math.tan(math.radians(italic_angle)) if italic_angle else 0.0
	report = StemSnapReport()

	_shear(contours, slope)
	try:
		found = det.detect(contours, axis=axis)
		cands = found
		if selected is not None:
			selected = set(selected)
			cands = [c for c in cands
			         if any((e.contour_idx, i) in selected
			                for e in (c.edge_a, c.edge_b) for i in e.node_indices)]
		report.candidates = cands
		report.captured = audit.audit(cands)
		report.groups = list(getattr(audit, 'groups', ()))
		report.moved = [v for v in report.captured if v.delta != 0.0]
		claimed = set(id(v.source) for v in report.captured)
		report.out_of_band = [c for c in cands if id(c) not in claimed]

		if report.moved:
			# Every stem not snapped stays rigid unless it overlaps a snapped one
			spans = [(v.source.axis, v.source.edge_a.coord, v.source.edge_b.coord) for v in report.moved]
			moving = set(id(v.source) for v in report.moved)
			keep = [c for c in found if id(c) not in moving
			        and not any(a == c.axis and c.edge_a.coord < hi and lo < c.edge_b.coord
			                    for a, lo, hi in spans)]
			report.plan = StemFixer(anchor=anchor).plan_cascade(
				report.moved, contours, scope=scope, keep=keep, pin_extremes=pin_extremes, whole=round_ints,
				protect_aligned=protect_aligned)
		if apply and len(report.plan):
			StemFixer(anchor=anchor).apply(report.plan, contours)
			report.applied = True
	finally:
		_shear(contours, -slope)

	if report.applied and round_ints:
		for ci, ni in report.plan.deltas:
			nd = contours[ci].nodes[ni]
			nd.x, nd.y = float(round(nd.x)), float(round(nd.y))

	return report


# =====================================================================
# - Uncommon stems: equalize an element's stems among themselves -------
# =====================================================================
DEFAULT_EQUALIZE_STEP = 10.0     # percent of the thinner neighbour
DEFAULT_EQUALIZE_ASPECT = 2.0    # width / common face length above this is not a stem


def group_widths(values, step=DEFAULT_EQUALIZE_STEP, percent=True, key=None):
	'''Split values into groups of similar stem width, thinnest group first.

	Walking up the sorted widths, a value joins the current group when it
	is within `step` of its thinner neighbour and within 2 * step of the
	group's thinnest member (no chaining up a long ladder of small gaps).
	Otherwise it starts a new group: the "step" between deliberate weights.

	percent -- step is a percentage of the thinner width, else font units.
	key     -- width of an item, when values are not plain numbers.

	[105, 115, 115, 125] -> one group; [95, 105, 115] -> [95], [105, 115];
	[60, 65, 70, 105, 115] -> [60, 65, 70], [105, 115] (step 10 %).
	'''
	width = key if key is not None else (lambda item: item)
	reach = (lambda w: w * step / 100.0) if percent else (lambda w: step)
	eps = 1e-6
	groups = []
	for item in sorted(values, key=width):
		w = width(item)
		if groups:
			last = groups[-1]
			if (w - width(last[-1]) <= reach(width(last[-1])) + eps
			    and w - width(last[0]) <= 2.0 * reach(width(last[0])) + eps):
				last.append(item)
				continue
		groups.append([item])
	return groups


def common_width(widths, allowlist=None, key=None):
	'''(value, source) for one group of stem widths. The result is a
	standard stem or a width already in the group, never a value in between.

	The group's own width is the single most frequent one (whole units,
	seen at least twice), else the median. Then, first match wins:
	  'standard' -- it falls in a standard stem's band: that stem.
	  'dominant' -- the most frequent width.
	  'median'   -- the median, when it is one of the widths.
	  'member'   -- the median fell between two widths: the width nearest a
	                standard stem of this axis; without any, nearest the
	                median; ties go to the thinner (less black).
	  'single'   -- a stem alone in its group, kept.

	allowlist, key -- the WidthAllowlist and its key (Axis.V / Axis.H).
	'''
	counts = {}
	for w in widths:
		k = int(round(w))
		counts[k] = counts.get(k, 0) + 1
	top = max(counts.values())
	leaders = [k for k, c in counts.items() if c == top]
	dominant = top > 1 and len(leaders) == 1
	value = float(leaders[0]) if dominant else float(_median(widths))

	if allowlist is not None:
		res = allowlist.capture(key, value)
		if res is not None:
			return res[0].value, 'standard'

	if len(widths) == 1:
		return value, 'single'
	if dominant:
		return value, 'dominant'
	if any(abs(w - value) <= 1e-6 for w in widths):
		return value, 'median'

	def off_standard(w):
		near = allowlist.nearest(key, w) if allowlist is not None else None
		return abs(w - near) if near is not None else 0.0

	return float(min(widths, key=lambda w: (off_standard(w), abs(w - value), w))), 'member'


class StemGroup(object):
	'''Stems of one axis and pool that equalize to one width.

	axis -- Axis.V / Axis.H; pool -- index in equalize_stems(pools=...);
	target -- the common width; source -- how it was chosen (see
	common_width); stems -- [StemCandidate].
	'''
	__slots__ = ('axis', 'pool', 'target', 'source', 'stems')

	def __init__(self, axis, pool, target, source, stems):
		self.axis, self.pool, self.target, self.source, self.stems = axis, pool, target, source, stems

	@property
	def widths(self):
		return [c.measured_width for c in self.stems]

	def __repr__(self):
		return 'StemGroup({}, pool={}, target={:g}, {}, widths={})'.format(
			self.axis, self.pool, self.target, self.source, [round(w, 2) for w in self.widths])


class StemEqualizer(object):
	'''Auditor for snap_stems(): stems are grouped among themselves and each
	group lands on one width. V and H are never mixed. Each group of similar
	widths (group_widths) gets its common width (common_width): a standard
	stem from `allowlist` when one is in reach, else a width from the group.

	Candidates that are not stems are left out: a bar's two ends pair up as
	a "stem" as wide as the bar is long, so a width above max_aspect times
	the length the faces share is rejected. Curve extrema have no length
	and always pass. With standard stems for the axis, a width above the
	heaviest one's band is rejected too: wide blocks and counters that are
	long enough to pass the first test. Thinner than the thinnest standard
	stays a stem: that is a deliberately light inner stem.

	pools -- optional list of contour-index collections equalized apart
	(one per element); None puts every stem in one pool.
	'''
	def __init__(self, allowlist=None, step=DEFAULT_EQUALIZE_STEP, percent=True, pools=None,
	             max_aspect=DEFAULT_EQUALIZE_ASPECT, round_ints=False):
		self.allowlist = allowlist
		self.step = float(step)
		self.percent = bool(percent)
		self.max_aspect = float(max_aspect)
		self.round_ints = bool(round_ints)
		self.pool_of = {}
		for index, members in enumerate(pools or ()):
			for ci in members:
				self.pool_of[ci] = index
		self.groups = []

	def is_stem(self, cand):
		targets = self.allowlist.targets_by_key.get(cand.axis) if self.allowlist is not None else None
		if targets and cand.measured_width > max(t.value + t.tol_plus for t in targets):
			return False
		a, b = cand.edge_a.span, cand.edge_b.span
		if min(a[1] - a[0], b[1] - b[0]) <= 0.0:
			return True
		return cand.measured_width <= (min(a[1], b[1]) - max(a[0], b[0])) * self.max_aspect

	def audit(self, candidates):
		self.groups = []
		pools = {}
		for cand in candidates:
			if self.is_stem(cand):
				pools.setdefault((self.pool_of.get(cand.edge_a.contour_idx, 0), cand.axis), []).append(cand)

		violations = []
		for pool, axis in sorted(pools):
			for stems in group_widths(pools[(pool, axis)], self.step, self.percent,
			                          key=lambda c: c.measured_width):
				target, source = common_width([c.measured_width for c in stems], self.allowlist, axis)
				if self.round_ints and source != 'single':
					target = float(round(target))
				self.groups.append(StemGroup(axis, pool, target, source, stems))
				for cand in stems:
					violations.append(StemViolation(key=axis, measured=cand.measured_width,
					                                target=WidthTarget(target),
					                                delta=target - cand.measured_width, source=cand))
		return violations


def equalize_stems(contours, allowlist=None, step=DEFAULT_EQUALIZE_STEP, percent=True, pools=None,
                   max_aspect=DEFAULT_EQUALIZE_ASPECT, detector=None, axis=None,
                   anchor='center', scope=Cascade.FAMILY, italic_angle=0.0,
                   selected=None, round_ints=False, pin_extremes=True, apply=True,
                   protect_aligned=True):
	'''Uncommon stems: make the stems of an element equal among themselves
	and land them on the font's standard stems. V and H stems are handled
	apart; within an axis, stems further apart than `step` stay in separate
	groups, so a deliberately lighter inner stem is not forced onto the
	outer frame.

	contours  -- list[Contour]; changed IN PLACE when apply is True. Pass
	             only the element's contours (e.g. a pasted part), or use
	             `selected` / `pools` to work on a part of a layer.
	allowlist -- WidthAllowlist of standard stems keyed Axis.V / Axis.H;
	             its bands decide what a group's width may snap to. A group
	             no standard stem reaches lands on one of its own widths
	             (see common_width), also when allowlist is None.
	step, percent -- see group_widths.
	pools, max_aspect -- see StemEqualizer.
	detector -- default: extrema mode, Topology.INK (inner bars count).
	The other arguments are those of snap_stems().

	Returns a StemSnapReport; report.groups holds the [StemGroup].
	'''
	return snap_stems(contours, None,
	                  detector=detector if detector is not None else StemDetector(topology=Topology.INK),
	                  axis=axis, anchor=anchor, scope=scope, italic_angle=italic_angle,
	                  selected=selected, round_ints=round_ints, pin_extremes=pin_extremes, apply=apply,
	                  protect_aligned=protect_aligned,
	                  auditor=StemEqualizer(allowlist=allowlist, step=step, percent=percent, pools=pools,
	                                        max_aspect=max_aspect, round_ints=round_ints))


def family_selection(contours, indices):
	'''`selected` argument for snap_stems() / equalize_stems() from contour
	indices: every node of those contours and of their outer / counters.
	Together they are the element, and an inner bar lies between two
	counters. Indices that do not exist are ignored.'''
	family = contour_families(contours)
	picked = set(ci for start in indices if start in family for ci in family[start])
	return set((ci, ni) for ci in picked for ni in range(len(contours[ci].nodes)))


# =====================================================================
# - Representative stem measurement (for stem-preserving delta scale) --
# =====================================================================
def _median(values):
	s = sorted(values)
	n = len(s)
	if n == 0:
		return None
	mid = n // 2
	return s[mid] if n % 2 else 0.5 * (s[mid - 1] + s[mid])


def _mode(values, center=None):
	'''Most frequent value (dominant). Ties break toward `center` (else the
	larger value). Values are bucketed exactly, so pre-snapped inputs collapse
	onto their canonical stems.'''
	if not values:
		return None
	counts = {}
	order = {}
	for i, v in enumerate(values):
		counts[v] = counts.get(v, 0) + 1
		order.setdefault(v, i)
	best = max(counts.values())
	tied = [v for v, c in counts.items() if c == best]
	if len(tied) == 1:
		return tied[0]
	if center is not None:
		return min(tied, key=lambda v: (abs(v - center), -v))
	return max(tied)


def measure_stems(contours, allowlist=None, mode=DetectMode.COINCIDENT, detector=None):
	'''Representative (stx, sty) stem widths for a set of Contours.

	stx = vertical-stem width (Axis.V candidates), sty = horizontal-stem width
	(Axis.H). Uses StemDetector (CJK-aware topology gate) to find candidates.

	When `allowlist` is given (keyed 'V'/'H'), each candidate is SNAPPED to the
	nearest allowed stem and the result is the **most frequent** snapped stem —
	i.e. the dominant real hinting stem, guaranteed to be an allowed value (not a
	between-stems median). Without an allowlist, the raw MEDIAN is returned (raw
	widths don't bucket, so a median is the stable representative there). Either
	value is None when no candidate of that axis is found.

	mode defaults to COINCIDENT (geometry-only; needs no inserted extrema), which
	suits arbitrary pasted parts.'''
	det = detector if detector is not None else StemDetector(mode=mode)
	cands = det.detect(contours)
	v = [c.measured_width for c in cands if c.axis == Axis.V]
	h = [c.measured_width for c in cands if c.axis == Axis.H]

	def reduce_axis(widths, key):
		if not widths:
			return None
		if allowlist is not None:
			# Use the standard stems as a FILTER: capture() keeps only candidates
			# that fall inside a real stem's band and snaps them to it; wide
			# artifacts (stroke junctions, the whole-part span) fall outside every
			# band and are dropped — so they can't drag the estimate up. Median the
			# survivors, then snap the median onto a real stem.
			captured = []
			for w in widths:
				res = allowlist.capture(key, w)
				if res is not None:
					captured.append(res[0].value)
			if not captured:
				return None			# nothing near a real stem -> let caller fall back
			m = _median(sorted(captured))
			near = allowlist.nearest(key, m)
			return near if near is not None else m
		return _median(widths)

	return (reduce_axis(v, Axis.V), reduce_axis(h, Axis.H))


def stem_widths(contours, mode=DetectMode.COINCIDENT, detector=None):
	'''Raw sorted (v_widths, h_widths) stem-candidate widths — diagnostics only,
	so callers can see what the detector actually found before aggregation.'''
	det = detector if detector is not None else StemDetector(mode=mode)
	cands = det.detect(contours)
	v = sorted(c.measured_width for c in cands if c.axis == Axis.V)
	h = sorted(c.measured_width for c in cands if c.axis == Axis.H)
	return (v, h)


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


def _test_contains_point_v_stem():
	'''V-stem 60 wide, 600 tall at x=[0,60]. contains_point on interior,
	boundary (strict vs non-strict), and outside on each axis.
	'''
	c = _make_rect_contour(0, 0, 60, 600)
	det = StemDetector(mode=DetectMode.EXTREMA)
	cand = next(k for k in det.detect([c]) if k.axis == Axis.V)
	# Interior
	assert cand.contains_point((30.0, 300.0)) is True
	assert cand.contains_point((30.0, 300.0), strict=False) is True
	# On the normal-axis boundary
	assert cand.contains_point((0.0, 300.0)) is False
	assert cand.contains_point((0.0, 300.0), strict=False) is True
	# On the span boundary
	assert cand.contains_point((30.0, 0.0)) is False
	assert cand.contains_point((30.0, 0.0), strict=False) is True
	# Outside on normal axis
	assert cand.contains_point((-1.0, 300.0), strict=False) is False
	# Outside in the span gap (above)
	assert cand.contains_point((30.0, 700.0), strict=False) is False
	print('  contains_point(V-stem): interior / boundary (strict|closed) / outside [OK]')


def _test_contains_point_h_stem():
	'''H-stem 600 wide, 50 tall. Same matrix on the H axis.'''
	c = _make_rect_contour(0, 0, 600, 50)
	det = StemDetector(mode=DetectMode.EXTREMA)
	cand = next(k for k in det.detect([c]) if k.axis == Axis.H)
	assert cand.contains_point((300.0, 25.0)) is True
	assert cand.contains_point((300.0, 0.0)) is False
	assert cand.contains_point((300.0, 0.0), strict=False) is True
	assert cand.contains_point((-1.0, 25.0), strict=False) is False
	print('  contains_point(H-stem): interior / boundary / outside [OK]')


def _run_stage3_tests():
	print('Stage 3 - topology gate:')
	_test_topology_strict_rejects_siblings()
	_test_topology_permissive_finds_siblings()
	_test_topology_counter_pair_allowed()
	_test_contains_point_v_stem()
	_test_contains_point_h_stem()
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


# --- Stage 7: representative stem measurement (measure_stems) ---

def _test_measure_stems_raw():
	c = [_make_h_glyph(stem_w=80, bar_h=40)]
	stx, sty = measure_stems(c)
	assert _approx(stx, 80.0) and _approx(sty, 40.0)
	# empty input -> (None, None)
	assert measure_stems([]) == (None, None)
	print('  measure_stems raw: H-glyph -> stx=80, sty=40 [OK]')


def _test_measure_stems_snapped():
	from typerig.core.algo._width_audit import allowlist_from_stems
	c = [_make_h_glyph(stem_w=80, bar_h=40)]
	al = allowlist_from_stems([(78, 'V'), (120, 'V'), (42, 'H')], tol_frac=0.25)
	stx, sty = measure_stems(c, allowlist=al)
	assert _approx(stx, 78.0) and _approx(sty, 42.0)		# snapped to nearest std
	# nearest() ignores the band: an off-grid value still lands on the closest std
	assert _approx(al.nearest('V', 200.0), 120.0)
	assert al.nearest('H', 999.0) == 42.0
	assert al.nearest('X', 10.0) is None					# no targets for key
	print('  measure_stems snapped: 80->78, 40->42; nearest 200->120 [OK]')


def _run_stage7_tests():
	print('Stage 7 - measure_stems:')
	_test_measure_stems_raw()
	_test_measure_stems_snapped()
	print('Stage 7: all tests passed.')


# --- Stage 8: cascade planner + snap_stems ---

def _o_glyph(wall_l=40, wall_r=40, counter_w=120, h=600, top=40):
	outer = _make_rect_contour(0, 0, wall_l + counter_w + wall_r, h)
	counter = _make_cw_rect_contour(wall_l, top, counter_w, h - 2 * top)
	return [outer, counter]


def _v_widths(contours):
	return sorted(round(c.measured_width, 3)
	              for c in StemDetector().detect(contours, axis=Axis.V))


def _test_cascade_o_both_walls():
	'''Both walls 40 -> 38. Family cascade must move the counter AND the
	outer right face; plan_iup (one contour only) gets the right wall wrong.'''
	al = WidthAllowlist({Axis.V: [WidthTarget(38, 5, 5)]})
	for anchor in ('lower', 'upper', 'center'):
		cs = _o_glyph()
		r = snap_stems(cs, al, axis=Axis.V, anchor=anchor)
		assert r.applied and len(r.moved) == 2
		assert _v_widths(cs).count(38.0) == 2, (anchor, _v_widths(cs))
	print('  family cascade: o walls 40/40 -> 38/38 for lower/upper/center [OK]')


def _test_cascade_center_keeps_centre():
	cs = [_make_rect_contour(100, 0, 31, 600)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	snap_stems(cs, al, axis=Axis.V, anchor='center')
	xs = sorted(set(nd.x for nd in cs[0].nodes))
	assert _approx(xs[0], 101.0) and _approx(xs[1], 130.0), xs
	print('  center anchor: 100..131 -> 101..130 [OK]')


def _test_cascade_two_stems_one_contour():
	gly = [_make_h_glyph(stem_w=31, bar_h=40)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	snap_stems(gly, al, axis=Axis.V, anchor='lower')
	assert _v_widths(gly).count(29.0) == 2, _v_widths(gly)
	print('  cascade: H with two 31 stems -> both 29 [OK]')


def _test_cascade_siblings_untouched():
	a = _make_rect_contour(0, 0, 31, 600)
	b = _make_rect_contour(200, 0, 60, 600)
	before = [(nd.x, nd.y) for nd in b.nodes]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	snap_stems([a, b], al, anchor='lower', scope=Cascade.FAMILY)
	assert [(nd.x, nd.y) for nd in b.nodes] == before
	snap_stems([a, b], WidthAllowlist({Axis.V: [WidthTarget(27, 5, 5)]}),
	           anchor='lower', scope=Cascade.LAYER)
	assert [(nd.x, nd.y) for nd in b.nodes] == before		# rigid + pinned extreme
	snap_stems([a, b], WidthAllowlist({Axis.V: [WidthTarget(25, 5, 5)]}),
	           anchor='lower', scope=Cascade.LAYER, pin_extremes=False)
	assert _approx(b.nodes[0].x, 198.0), b.nodes[0].x
	print('  family scope leaves sibling alone; layer scope moves it (pins off) [OK]')


def _test_dry_run_and_selection():
	cs = [_make_rect_contour(0, 0, 31, 600), _make_rect_contour(200, 0, 31, 600)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	r = snap_stems(cs, al, axis=Axis.V, apply=False)
	assert not r.applied and len(r.moved) == 2 and _v_widths(cs) == [31.0, 31.0]
	r = snap_stems(cs, al, axis=Axis.V, selected={(1, 0)})
	assert len(r.moved) == 1 and _v_widths(cs) == [29.0, 31.0], _v_widths(cs)
	print('  dry run changes nothing; selection limits to picked stem [OK]')


def _test_italic_deslant():
	'''Parallelogram stem slanted 10deg, horizontal width 31 -> 29.'''
	t = math.tan(math.radians(10.0))
	pts = [(0, 0), (31, 0), (31 + 600 * t, 600), (600 * t, 600)]
	cs = [Contour([Node(x, y) for x, y in pts], closed=True)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	assert not snap_stems(cs, al, axis=Axis.V, apply=False).captured
	r = snap_stems(cs, al, axis=Axis.V, italic_angle=10.0, anchor='lower')
	assert len(r.moved) == 1
	n = cs[0].nodes
	assert _approx(n[1].x - n[0].x, 29.0) and _approx(n[2].x - n[3].x, 29.0)
	assert _approx(n[3].x, 600 * t)
	print('  italic: 10deg slanted stem 31 -> 29, slant kept [OK]')


def _test_round_ints():
	cs = [_make_rect_contour(0, 0, 30, 600)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	snap_stems(cs, al, axis=Axis.V, anchor='center', round_ints=True)
	assert all(nd.x == int(nd.x) for nd in cs[0].nodes)
	print('  round_ints: moved nodes on integers [OK]')

	# Center + round lands exactly on target for odd and even corrections
	# (half-unit moves used to round back: 30 -> 29 stayed 30, 80 -> 77 gave 76)
	for x0, w, target in ((0, 30, 29), (1, 30, 29), (0, 28, 29), (10, 82, 81), (0, 80, 77), (0, 80, 83), (3, 84, 80)):
		cs = [_make_rect_contour(x0, 0, w, 600)]
		al = WidthAllowlist({Axis.V: [WidthTarget(target, 5, 5)]})
		snap_stems(cs, al, axis=Axis.V, anchor='center', round_ints=True)
		xs = sorted(set(nd.x for nd in cs[0].nodes))
		assert xs[1] - xs[0] == target, (x0, w, target, xs)
		assert abs((xs[0] + xs[1]) * .5 - (x0 + w * .5)) <= .5, (x0, w, target, xs)

	# Same for a slanted stem (deslanted width, slanted integer nodes)
	t = math.tan(math.radians(12.))
	cs = [Contour([Node(x + round(y * t), y) for x, y in ((0, 0), (31, 0), (31, 600), (0, 600))], closed=True)]
	snap_stems(cs, WidthAllowlist({Axis.V: [WidthTarget(28, 5, 5)]}), axis=Axis.V, anchor='center',
	           italic_angle=math.degrees(math.atan(round(600 * t) / 600.)), round_ints=True)
	bottom = sorted(nd.x for nd in cs[0].nodes if nd.y == 0)
	top = sorted(nd.x for nd in cs[0].nodes if nd.y == 600)
	assert bottom[1] - bottom[0] == 28 and top[1] - top[0] == 28, (bottom, top)
	print('  round_ints + center: odd / even corrections land on target, centre within 0.5 [OK]')


def _ellipse(cx, cy, rx, ry, ccw=True, k=0.5523):
	'''Four-extrema cubic ellipse.'''
	P = [(cx + rx, cy), (cx, cy + ry), (cx - rx, cy), (cx, cy - ry)]
	T = [(0, ry), (-rx, 0), (0, -ry), (rx, 0)]
	nodes = []
	for i in range(4):
		p, q, t0, t1 = P[i], P[(i + 1) % 4], T[i], T[(i + 1) % 4]
		nodes += [Node(p[0], p[1], type='on'),
		          Node(p[0] + t0[0] * k, p[1] + t0[1] * k, type='curve'),
		          Node(q[0] - t1[0] * k, q[1] - t1[1] * k, type='curve')]
	if not ccw:
		nodes = [Node(n.x, n.y, type=n.type) for n in reversed(nodes)]
	return Contour(nodes, closed=True)


def _test_curved_o():
	'''Round 'o': walls 38 (V) and 40 (H) at the extrema. Snap to 36:
	extrema land on target and handles stay axis-aligned.'''
	cs = [_ellipse(300, 300, 300, 320), _ellipse(300, 300, 262, 280, ccw=False)]
	al = WidthAllowlist({Axis.V: [WidthTarget(36, 5, 5)], Axis.H: [WidthTarget(36, 5, 5)]})
	r = snap_stems(cs, al)
	assert sorted((v.key, round(v.measured, 3)) for v in r.moved) == \
		[('H', 40.0), ('H', 40.0), ('V', 38.0), ('V', 38.0)], r.moved
	widths = sorted((c.axis, round(c.measured_width, 3)) for c in StemDetector().detect(cs))
	assert widths == [('H', 36.0)] * 2 + [('V', 36.0)] * 2, widths
	for c in cs:
		for i, on in enumerate(c.nodes):
			if not on.is_on:
				continue
			for h in (c.nodes[i - 1], c.nodes[(i + 1) % len(c.nodes)]):
				assert _approx(on.x, h.x) or _approx(on.y, h.y), 'handle tilted'
	print('  curved o: extrema stems 38/40 -> 36, handles stay H/V [OK]')


def _test_cascade_counters_absorb():
	'''H with two 31 stems, center anchor: each stem keeps its centre,
	the counter absorbs, the outline shrinks by 1 per side only.'''
	gly = [_make_h_glyph(stem_w=31, bar_h=40, glyph_w=400)]
	snap_stems(gly, WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]}), axis=Axis.V, anchor='center')
	xs = sorted(set(nd.x for nd in gly[0].nodes))
	assert xs == [1.0, 30.0, 370.0, 399.0], xs
	print('  center: H 0|31..369|400 -> 1|30..370|399, counter absorbs [OK]')


def _test_cascade_keeps_on_target_stem():
	'''Comb: stems 31 | 29 | 31 at x 0, 100, 200 in one layer. Snapping the
	outer two must not bend the middle one (already on target).'''
	cs = [_make_rect_contour(0, 0, 31, 600), _make_rect_contour(100, 0, 29, 600),
	      _make_rect_contour(200, 0, 31, 600)]
	al = WidthAllowlist({Axis.V: [WidthTarget(29, 5, 5)]})
	snap_stems(cs, al, axis=Axis.V, anchor='lower', scope=Cascade.LAYER)
	assert _v_widths(cs) == [29.0, 29.0, 29.0], _v_widths(cs)
	print('  on-target stem between moved stems stays rigid [OK]')


def _test_pin_extremes():
	'''H crossbar 42 -> 40 centered: baseline and top stay put.'''
	gly = [_make_h_glyph(stem_w=80, bar_h=42)]
	al = WidthAllowlist({Axis.H: [WidthTarget(40, 5, 5)]})
	snap_stems(gly, al, axis=Axis.H, anchor='center')
	ys = sorted(set(round(nd.y, 6) for nd in gly[0].nodes))
	assert ys == [0.0, 280.0, 320.0, 600.0], ys
	gly = [_make_h_glyph(stem_w=80, bar_h=42)]
	snap_stems(gly, al, axis=Axis.H, anchor='center', pin_extremes=False)
	ys = sorted(set(round(nd.y, 6) for nd in gly[0].nodes))
	assert ys == [1.0, 280.0, 320.0, 599.0], ys
	print('  pin_extremes: bar 42 -> 40, baseline / top kept (off: they follow) [OK]')


def _run_stage8_tests():
	print('Stage 8 - plan_cascade / snap_stems:')
	_test_cascade_o_both_walls()
	_test_cascade_center_keeps_centre()
	_test_cascade_two_stems_one_contour()
	_test_cascade_siblings_untouched()
	_test_dry_run_and_selection()
	_test_italic_deslant()
	_test_round_ints()
	_test_curved_o()
	_test_cascade_counters_absorb()
	_test_cascade_keeps_on_target_stem()
	_test_pin_extremes()
	print('Stage 8: all tests passed.')


# --- Stage 9: uncommon stems (equalize_stems) ---

def _make_window(left, right, inners, bar=60, cell=150, height=600):
	'''One-row window: outer rect + CW counters. V stems, left to right:
	left, inners..., right; top and bottom bars are `bar` thick.'''
	width = left + right + sum(inners) + cell * (len(inners) + 1)
	out = [_make_rect_contour(0, 0, width, height)]
	x = left
	for inner in list(inners) + [None]:
		out.append(_make_cw_rect_contour(x, bar, cell, height - 2 * bar))
		x += cell + (inner or 0)
	return out


def _ink_widths(contours, axis):
	cands = StemDetector(topology=Topology.INK).detect(contours, axis=axis)
	return sorted(round(c.measured_width, 3) for c in cands)


def _test_group_widths_examples():
	assert group_widths([105, 115, 115, 125]) == [[105, 115, 115, 125]]
	assert group_widths([95, 105, 115]) == [[95], [105, 115]]
	assert group_widths([75, 105, 115]) == [[75], [105, 115]]
	assert group_widths([60, 65, 70, 105, 115]) == [[60, 65, 70], [105, 115]]
	assert group_widths([100, 109, 118, 127, 136]) == [[100, 109, 118], [127, 136]], 'no chaining'
	assert group_widths([100, 112], step=12, percent=False) == [[100, 112]]
	print('  group_widths: the brief\'s four sets; ladder does not chain [OK]')


def _standards(v=(), h=(), band=5):
	return WidthAllowlist({Axis.V: [WidthTarget(x, band, band) for x in v],
	                       Axis.H: [WidthTarget(x, band, band) for x in h]})


def _test_common_width():
	assert common_width([105, 115, 115, 125]) == (115.0, 'dominant')
	assert common_width([60, 65, 70]) == (65.0, 'median')
	assert common_width([95]) == (95.0, 'single')
	assert common_width([105, 115]) == (105.0, 'member'), 'no invented 110'
	assert common_width([105, 105, 115, 115])[1] == 'member', 'tie is no dominant'
	print('  common_width: dominant, else median, never a value between widths [OK]')


def _test_common_width_standards():
	def pick(widths, *stems):
		return common_width(widths, _standards(v=stems), Axis.V)
	assert pick([105, 115], 110) == (110.0, 'standard')
	assert pick([130, 135], 135) == (135.0, 'standard')
	assert pick([130, 135], 130) == (130.0, 'standard')
	assert pick([130, 135], 130, 135) == (130.0, 'standard'), 'tie: earlier stem'
	assert pick([130, 135], 120, 139) == (135.0, 'member'), 'nearest a standard'
	assert pick([130, 135], 120, 150) == (130.0, 'member'), 'nearest a standard'
	assert pick([130, 135]) == (130.0, 'member'), 'no standards: thinner'
	assert pick([105, 115, 115, 125], 112) == (112.0, 'standard'), 'standard beats dominant'
	assert pick([115, 115], 200) == (115.0, 'dominant')
	assert pick([78], 80) == (80.0, 'standard'), 'single in band lands too'
	assert pick([95], 110) == (95.0, 'single'), 'single out of band kept'
	h_only = common_width([130, 135], _standards(h=[132]), Axis.V)
	assert h_only == (130.0, 'member'), 'H standards do not apply to V'
	print('  common_width: lands on standards; 130 135 never 132 [OK]')


def _test_topology_ink_finds_inner_stems():
	cs = _make_window(105, 115, [75])
	assert _ink_widths(cs, Axis.V) == [75.0, 105.0, 115.0], _ink_widths(cs, Axis.V)
	strict = StemDetector(topology=Topology.STRICT).detect(cs, axis=Axis.V)
	assert 75.0 not in [round(c.measured_width, 3) for c in strict]
	a, b = _make_rect_contour(0, 0, 60, 600), _make_rect_contour(90, 0, 60, 600)
	assert _ink_widths([a, b], Axis.V) == [60.0, 60.0], 'gap between outers is not ink'
	print('  INK: wall between sibling counters is a stem, gap between outers is not [OK]')


def _test_equalize_dominant():
	cs = _make_window(105, 125, [115, 115])
	report = equalize_stems(cs, round_ints=True)
	assert _ink_widths(cs, Axis.V) == [115.0] * 4, _ink_widths(cs, Axis.V)
	assert [g.source for g in report.groups if g.axis == Axis.V] == ['dominant']
	print('  105 115 115 125 -> all 115 (dominant) [OK]')


def _test_equalize_keeps_lighter_inner():
	for inner in (95, 75):
		cs = _make_window(105, 115, [inner])
		equalize_stems(cs, _standards(v=[110]), round_ints=True)
		assert _ink_widths(cs, Axis.V) == [float(inner), 110.0, 110.0], _ink_widths(cs, Axis.V)
	print('  frame 105 115 -> standard 110, inner 95 / 75 kept [OK]')


def _test_equalize_grid_two_groups():
	cs = _make_window(105, 115, [65, 70, 60])
	equalize_stems(cs, _standards(v=[110]), round_ints=True)
	assert _ink_widths(cs, Axis.V) == [65.0, 65.0, 65.0, 110.0, 110.0], _ink_widths(cs, Axis.V)
	print('  grid: frame -> standard 110, inner 65 70 60 -> 65 [OK]')


def _test_equalize_lands_on_a_real_stem():
	cs = _make_window(130, 135, [75])
	equalize_stems(cs, _standards(v=[135]), round_ints=True)
	assert _ink_widths(cs, Axis.V) == [75.0, 135.0, 135.0], _ink_widths(cs, Axis.V)
	cs = _make_window(130, 135, [75])
	equalize_stems(cs, round_ints=True)
	assert _ink_widths(cs, Axis.V) == [75.0, 130.0, 130.0], _ink_widths(cs, Axis.V)
	print('  130 135 -> the standard, or one of the two; never 132 [OK]')


def _test_equalize_axes_apart():
	cs = _make_window(105, 115, [75], bar=40)
	report = equalize_stems(cs, round_ints=True)
	assert set(_ink_widths(cs, Axis.H)) == {40.0}, _ink_widths(cs, Axis.H)
	assert all(g.target != 40.0 for g in report.groups if g.axis == Axis.V)
	cs = _make_window(105, 115, [75])
	equalize_stems(cs, axis=Axis.H, round_ints=True)
	assert _ink_widths(cs, Axis.V) == [75.0, 105.0, 115.0], 'axis=H must not touch V'
	print('  V and H never mix; axis filter respected [OK]')


def _test_equalize_ignores_bar_length():
	cs = [_make_rect_contour(0, 0, 400, 30), _make_rect_contour(0, 100, 410, 30)]
	report = equalize_stems(cs, round_ints=True)
	assert not report.moved, report.moved
	assert sorted(max(nd.x for nd in c.nodes) for c in cs) == [400.0, 410.0]
	blocks = [_make_rect_contour(0, 0, 200, 600), _make_rect_contour(400, 0, 201, 600)]
	report = equalize_stems(blocks, _standards(v=[110, 150]), round_ints=True)
	assert not report.moved and len(report.out_of_band) >= 2, report.groups
	thin = [_make_rect_contour(0, 0, 60, 600), _make_rect_contour(400, 0, 62, 600)]
	report = equalize_stems(thin, _standards(v=[110, 150]), round_ints=True)
	assert report.moved, 'thinner than every standard is still a stem'
	print('  bar lengths and blocks above the heaviest standard are not stems [OK]')


def _test_equalize_pools():
	def bars():
		return [_make_rect_contour(0, 0, 100, 600), _make_rect_contour(300, 0, 104, 600)]
	cs = bars()
	equalize_stems(cs, round_ints=True)
	assert _ink_widths(cs, Axis.V) == [100.0, 100.0], _ink_widths(cs, Axis.V)
	cs = bars()
	report = equalize_stems(cs, pools=[[0], [1]], round_ints=True)
	assert not report.moved and _ink_widths(cs, Axis.V) == [100.0, 104.0]
	print('  pools: elements equalize apart [OK]')


def _test_family_selection():
	window = _make_window(105, 115, [75])
	other = _make_rect_contour(1000, 0, 100, 600)
	cs = window + [other]
	picked = family_selection(cs, [0, 99])
	assert set(ci for ci, _ in picked) == {0, 1, 2}, picked
	assert len(picked) == 12
	report = equalize_stems(cs, _standards(v=[110]), selected=family_selection(cs, [1]), axis=Axis.V, apply=False)
	assert all(c.edge_a.contour_idx != 3 for c in report.candidates)
	print('  family_selection: a contour brings its outer and counters, nothing else [OK]')


def _test_equalize_dry_run():
	cs = _make_window(105, 115, [75])
	report = equalize_stems(cs, _standards(v=[110]), apply=False)
	assert len(report.moved) == 2 and not report.applied
	assert _ink_widths(cs, Axis.V) == [75.0, 105.0, 115.0]
	print('  dry run reports, changes nothing [OK]')


def _tops(contours):
	return [max(nd.y for nd in c.nodes) for c in contours]


def _bottoms(contours):
	return [min(nd.y for nd in c.nodes) for c in contours]


def _test_aligned_top_stays():
	'''The uni80EF case: a 134 bar and a tall stem share the top line at 821.'''
	def part():
		return [_make_rect_contour(137, 687, 238, 134), _make_rect_contour(69, -95, 135, 916)]
	cs = part()
	report = snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert _tops(cs) == [821.0, 821.0] and _bottoms(cs) == [691.0, -95.0], (_tops(cs), _bottoms(cs))
	assert len(report.plan.meta['aligned_kept']) == 1
	cs = part()
	snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True, protect_aligned=False)
	assert _tops(cs) == [819.0, 821.0], 'without it the top drifts: {}'.format(_tops(cs))
	print('  aligned top stays, the other face takes the correction [OK]')


def _test_aligned_not_fooled_by_far_edges():
	'''uni80EF again, with what broke it: far away, a TOP face level with the
	bar's BOTTOM (opposite facing), then a far BOTTOM face (same facing).'''
	def part(far):
		return [_make_rect_contour(137, 686, 238, 135), _make_rect_contour(69, -95, 135, 916), far]
	cs = part(_make_rect_contour(676, 381, 130, 305))		# top at 686
	report = snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert (_tops(cs)[0], _bottoms(cs)[0]) == (821.0, 691.0), (_tops(cs), _bottoms(cs))
	assert len(report.plan.meta['aligned_kept']) == 1 and not report.plan.meta['aligned_both']
	cs = part(_make_rect_contour(676, 686, 130, 305))		# bottom at 686
	report = snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert (_tops(cs)[0], _bottoms(cs)[0]) == (821.0, 691.0), (_tops(cs), _bottoms(cs))
	print('  opposite-facing edge ignored; touching alignment beats a far one [OK]')


def _test_aligned_bottom_stays():
	cs = [_make_rect_contour(137, 0, 238, 134), _make_rect_contour(69, 0, 135, 900)]
	snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert _bottoms(cs) == [0.0, 0.0] and _tops(cs) == [130.0, 900.0], (_bottoms(cs), _tops(cs))
	print('  aligned bottom stays [OK]')


def _test_aligned_different_corrections():
	'''Two bars, tops level, different corrections: the tops must stay level.'''
	cs = [_make_rect_contour(0, 500, 200, 134), _make_rect_contour(300, 502, 200, 132)]
	equalize_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert _tops(cs) == [634.0, 634.0], _tops(cs)
	assert sorted(_bottoms(cs)) == [504.0, 504.0], _bottoms(cs)
	print('  level tops with different corrections stay level [OK]')


def _test_aligned_both_faces_centred():
	cs = [_make_rect_contour(0, 500, 200, 134), _make_rect_contour(300, 500, 200, 134)]
	report = snap_stems(cs, _standards(h=[130]), axis=Axis.H, round_ints=True)
	assert _tops(cs) == [632.0, 632.0] and _bottoms(cs) == [502.0, 502.0], (_tops(cs), _bottoms(cs))
	assert len(report.plan.meta['aligned_both']) == 2
	print('  both faces aligned: centred and reported [OK]')


def _test_aligned_window_not_fooled():
	'''Counters of one window share the wall line: that is not an alignment.'''
	cs = _make_window(105, 115, [75])
	report = equalize_stems(cs, _standards(v=[110]), axis=Axis.V, round_ints=True)
	assert not report.plan.meta['aligned_kept'], report.plan.meta
	assert min(nd.x for nd in cs[0].nodes) == -2.0
	print('  window walls stay centred [OK]')


def _test_aligned_explicit_anchor():
	cs = [_make_rect_contour(137, 687, 238, 134), _make_rect_contour(69, -95, 135, 916)]
	snap_stems(cs, _standards(h=[130]), axis=Axis.H, anchor='lower', round_ints=True)
	assert _tops(cs) == [817.0, 821.0], _tops(cs)
	print('  explicit anchor is respected [OK]')


def _run_stage9_tests():
	print('Stage 9 - uncommon stems:')
	_test_group_widths_examples()
	_test_common_width()
	_test_common_width_standards()
	_test_topology_ink_finds_inner_stems()
	_test_equalize_dominant()
	_test_equalize_keeps_lighter_inner()
	_test_equalize_grid_two_groups()
	_test_equalize_lands_on_a_real_stem()
	_test_equalize_axes_apart()
	_test_equalize_ignores_bar_length()
	_test_equalize_pools()
	_test_family_selection()
	_test_equalize_dry_run()
	_test_aligned_top_stays()
	_test_aligned_not_fooled_by_far_edges()
	_test_aligned_bottom_stays()
	_test_aligned_different_corrections()
	_test_aligned_both_faces_centred()
	_test_aligned_window_not_fooled()
	_test_aligned_explicit_anchor()
	print('Stage 9: all tests passed.')


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
	_run_stage7_tests()
	print()
	_run_stage8_tests()
	print()
	_run_stage9_tests()
	print()
	print('stem_snap: ALL STAGES PASSED')
