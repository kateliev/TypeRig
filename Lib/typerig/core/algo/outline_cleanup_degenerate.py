# MODULE: TypeRig / Core / Algo / Outline Cleanup — Stage A
# -----------------------------------------------------------
# Degeneracy passes: zero segments, coincident on-curves, zero
# handles, flat cubics, collinear line nodes, spikes, tiny
# contours. Each pass takes an MContour and returns a new one
# plus a changed flag; removals are decided for all masters at
# once. Passes 1, 2, 5, 6, 7 accept quadratic segments too.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

from dataclasses import replace

from typerig.core.algo.outline_cleanup_geom import Seg, dist, line_distance, line_param, angle_between, area, start_tangent, end_tangent
from typerig.core.algo.outline_cleanup_convert import Knot, MContour
from typerig.core.algo.outline_cleanup_masters import every

__version__ = '1.0.0'

MAX_ROUNDS = 8
SPIKE_ANGLE = 179.


# - Helpers ------------------------------
def _anchored(knots: list[Knot], i: int) -> bool:
	'''Merge priority: the start knot, then caller locks, then Stage B locks.'''
	return i == 0 or knots[i].locked or knots[i].fixed


def _move_start(seg: Seg, pt) -> Seg:
	p = seg.p
	if len(p) == 4:
		dx, dy = pt[0] - p[0][0], pt[1] - p[0][1]
		return Seg((pt, (p[1][0] + dx, p[1][1] + dy), p[2], p[3]), seg.src)
	return Seg((pt,) + p[1:], seg.src)


def _move_end(seg: Seg, pt) -> Seg:
	p = seg.p
	if len(p) == 4:
		dx, dy = pt[0] - p[3][0], pt[1] - p[3][1]
		return Seg((p[0], p[1], (p[2][0] + dx, p[2][1] + dy), pt), seg.src)
	return Seg(p[:-1] + (pt,), seg.src)


def _drop_segment(mc: MContour, i: int, positions, meta: int) -> None:
	'''Remove segment i in place and weld its two knots into one at
	positions[m], carrying the metadata of knot meta. The welded knot
	keeps slot i, or slot 0 when the segment closes the contour.'''
	n = len(mc.knots)
	a, b = i, (i + 1) % n
	keep, gone = (b, a) if b == 0 else (a, b)

	survivor = replace(mc.knots[meta],
					locked=mc.knots[a].locked or mc.knots[b].locked,
					fixed=mc.knots[a].fixed or mc.knots[b].fixed)

	for m, segs in enumerate(mc.segs):
		pt = positions[m]
		removed = segs[i]
		prev_i, next_i = (i - 1) % n, (i + 1) % n
		segs[prev_i] = _move_end(segs[prev_i], pt)
		nxt = _move_start(segs[next_i], pt)
		segs[next_i] = Seg(nxt.p, (removed.src[0], nxt.src[1]))
		del segs[i]

	mc.knots[keep] = survivor
	del mc.knots[gone]


def _join_lines(mc: MContour, i: int) -> None:
	'''Remove knot i (between line i-1 and line i) in place.'''
	n = len(mc.knots)
	prev_i = (i - 1) % n

	for segs in mc.segs:
		a, b = segs[prev_i], segs[i]
		segs[prev_i] = Seg((a.p[0], b.p[-1]), (a.src[0], b.src[1]))
		del segs[i]

	del mc.knots[i]


# - Passes -------------------------------
def zero_segments(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 1: drop a segment whose points all lie within eps_point of its start.'''
	mc = mc.copy()
	changed = False
	i = 0

	while i < len(mc.knots) and len(mc.knots) > 2:
		if every(all(dist(segs[i].p[0], q) < opts.eps_point for q in segs[i].p[1:]) for segs in mc.segs):
			b = (i + 1) % len(mc.knots)
			anchor = b if b == 0 or (_anchored(mc.knots, b) and not _anchored(mc.knots, i)) else i
			_drop_segment(mc, i, [segs[i].p[0] if anchor == i else segs[i].p[-1] for segs in mc.segs], anchor)
			changed = True
		else:
			i += 1

	return mc, changed


def coincident(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 2: merge two consecutive on-curves closer than eps_point at their
	midpoint, or into the anchored one.'''
	mc = mc.copy()
	changed = False
	i = 0

	while i < len(mc.knots) and len(mc.knots) > 2:
		if every(dist(segs[i].p[0], segs[i].p[-1]) < opts.eps_point for segs in mc.segs):
			n = len(mc.knots)
			b = (i + 1) % n
			anchored_a, anchored_b = _anchored(mc.knots, i), _anchored(mc.knots, b)

			if anchored_b and (b == 0 or not anchored_a):
				positions, meta = [segs[i].p[-1] for segs in mc.segs], b
			elif anchored_a:
				positions, meta = [segs[i].p[0] for segs in mc.segs], i
			else:
				positions, meta = [((segs[i].p[0][0] + segs[i].p[-1][0]) * .5, (segs[i].p[0][1] + segs[i].p[-1][1]) * .5) for segs in mc.segs], i

			_drop_segment(mc, i, positions, meta)
			changed = True
		else:
			i += 1

	return mc, changed


def zero_handles(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 3: retract cubic handles shorter than eps_handle; a cubic with
	both handles retracted becomes a line.'''
	mc = mc.copy()
	changed = False

	for i in range(len(mc.knots)):
		if not mc.segs[0][i].is_cubic:
			continue

		len_in = [dist(segs[i].p[0], segs[i].p[1]) for segs in mc.segs]
		len_out = [dist(segs[i].p[3], segs[i].p[2]) for segs in mc.segs]
		short_in = every(d < opts.eps_handle for d in len_in) and any(len_in)
		short_out = every(d < opts.eps_handle for d in len_out) and any(len_out)

		for segs in mc.segs:
			p = segs[i].p
			p1 = p[0] if short_in else p[1]
			p2 = p[3] if short_out else p[2]
			segs[i] = Seg((p[0], p1, p2, p[3]), segs[i].src)

		changed = changed or short_in or short_out

		if every(segs[i].p[1] == segs[i].p[0] and segs[i].p[2] == segs[i].p[3] for segs in mc.segs):
			for segs in mc.segs:
				segs[i] = Seg((segs[i].p[0], segs[i].p[3]), segs[i].src)
			changed = True

	return mc, changed


def _is_flat(p, eps) -> bool:
	a, b = p[0], p[3]
	if line_distance(p[1], a, b) > eps or line_distance(p[2], a, b) > eps:
		return False
	t1, t2 = line_param(p[1], a, b), line_param(p[2], a, b)
	return 0. <= t1 <= t2 <= 1.


def _smooth_to_cubic(segs, i, opts) -> bool:
	'''Segment i joins a neighbouring cubic without a corner.'''
	n = len(segs)
	seg, prev, nxt = segs[i], segs[(i - 1) % n], segs[(i + 1) % n]
	pairs = []
	if prev.is_cubic and prev is not seg:
		pairs.append((end_tangent(prev.p, opts.eps_handle), start_tangent(seg.p, opts.eps_handle)))
	if nxt.is_cubic and nxt is not seg:
		pairs.append((end_tangent(seg.p, opts.eps_handle), start_tangent(nxt.p, opts.eps_handle)))
	return any(a is not None and b is not None and angle_between(a, b) <= opts.corner_angle for a, b in pairs)


def flat_cubics(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 4: a cubic whose handles sit on the chord, in order, becomes a line.
	A flat piece that continues a neighbouring cubic smoothly stays a cubic:
	as a line it would kink the curve and lock the junction; the simplifier
	absorbs it instead.'''
	mc = mc.copy()
	changed = False

	for i in range(len(mc.knots)):
		if not mc.segs[0][i].is_cubic or not every(_is_flat(segs[i].p, opts.eps_collinear) for segs in mc.segs):
			continue
		if any(_smooth_to_cubic(segs, i, opts) for segs in mc.segs):
			continue

		for segs in mc.segs:
			segs[i] = Seg((segs[i].p[0], segs[i].p[3]), segs[i].src)
		changed = True

	return mc, changed


def _line_joint(mc: MContour, i: int) -> bool:
	n = len(mc.knots)
	return mc.segs[0][(i - 1) % n].is_line and mc.segs[0][i].is_line


def collinear(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 5: remove a line-line node that lies on, and between, its neighbours.'''
	mc = mc.copy()
	changed = False
	i = 1

	def test(segs):
		a, b, c = segs[i - 1].p[0], segs[i].p[0], segs[i].p[1]
		return line_distance(b, a, c) <= opts.eps_collinear and 0. < line_param(b, a, c) < 1.

	while i < len(mc.knots) and len(mc.knots) > 2:
		if not mc.knots[i].locked and _line_joint(mc, i) and every(test(segs) for segs in mc.segs):
			_join_lines(mc, i)
			changed = True
		else:
			i += 1

	return mc, changed


def spikes(mc: MContour, opts) -> tuple[MContour, bool]:
	'''Pass 6: remove the tip of a line-line joint that folds back (> 179 deg).'''
	mc = mc.copy()
	changed = False
	i = 1

	def test(segs):
		a, b, c = segs[i - 1].p[0], segs[i].p[0], segs[i].p[1]
		d_in, d_out = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
		if d_in == (0., 0.) or d_out == (0., 0.):
			return False
		return angle_between(d_in, d_out) > SPIKE_ANGLE

	while i < len(mc.knots) and len(mc.knots) > 2:
		if not mc.knots[i].locked and _line_joint(mc, i) and every(test(segs) for segs in mc.segs):
			_join_lines(mc, i)
			changed = True
			i = max(1, i - 1)
		else:
			i += 1

	return mc, changed


def is_tiny(mc: MContour, opts) -> bool:
	'''Pass 7 test. Fewer than 3 segments only drops a contour that cannot
	enclose ink (a lens of two curves is a legitimate shape).'''
	n = len(mc.knots)
	if n < 2 or (n == 2 and all(s.is_line for s in mc.segs[0])):
		return True
	return every(abs(area([s.p for s in segs])) < opts.min_contour_area for segs in mc.segs)


PASSES = (zero_segments, coincident, zero_handles, flat_cubics, collinear, spikes)


def stage_a(mcs: list[MContour], opts) -> tuple[list[MContour], bool]:
	'''Run all passes until a full round changes nothing (max 8 rounds).'''
	any_change = False

	for _ in range(MAX_ROUNDS):
		changed = False
		result = []

		for mc in mcs:
			for fn in PASSES:
				mc, ch = fn(mc, opts)
				changed = changed or ch

			if is_tiny(mc, opts):
				changed = True
			else:
				result.append(mc)

		mcs = result
		any_change = any_change or changed
		if not changed:
			break

	return mcs, any_change
