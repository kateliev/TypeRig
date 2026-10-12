# MODULE: TypeRig / Core / Algo / Outline Cleanup — Stage C2
# -----------------------------------------------------------
# Visvalingam-Whyatt elimination inside spans. The cost of an
# interior node is the error of refitting the ORIGINAL source
# under its two neighbouring segments with one cubic (Levien,
# then Schneider with max_segments=1). Lazy-deletion heap; the
# multi-master cost is the max over masters.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from typerig.core.algo.intersect import line_to_cubic
from typerig.core.algo.outline_cleanup_geom import Seg, start_tangent, end_tangent, arc_length, run_distance, interior_extrema, shear
from typerig.core.algo.outline_cleanup_fit_levien import fit_run
from typerig.core.algo.outline_cleanup_fit_schneider import fit_schneider, sample_run
from typerig.core.algo.outline_cleanup_convert import MContour
from typerig.core.algo.outline_cleanup_masters import worst

__version__ = '1.0.0'

INF = float('inf')


@dataclass(slots=True)
class _Piece:
	cur: list[Seg]			# current segment per master
	orig: list[list[Seg]]	# original source segments per master
	length: float			# arc length of the original source (master 0)
	knot: int				# index of the knot the piece starts at


# - Cost ---------------------------------
def fit_one(orig: list[Seg], opts) -> tuple[Seg, float] | None:
	'''Best single-segment fit of an original run within fit_tol.'''
	result = fit_run(orig, opts.fit_tol, opts.eps_point, opts.eps_handle)
	if result is not None:
		return result

	src = [s.p for s in orig]
	t_start = start_tangent(src[0], opts.eps_handle)
	t_end = end_tangent(src[-1], opts.eps_handle)
	if t_start is None or t_end is None:
		return None

	fit = fit_schneider(sample_run(src), t_start, t_end, opts.fit_tol, max_segments=1)
	if fit is None:
		return None

	err = run_distance(src, [fit[0].p], opts.fit_tol)
	if err > opts.fit_tol:
		return None

	return Seg(fit[0].p, (orig[0].src[0], orig[-1].src[1])), err


def _adds_extremum(orig: list[Seg], fit: Seg, slant: float) -> bool:
	'''The merged segment carries an H/V extremum none of its sources had
	inside them: the removed node sat on it.'''
	before = sum(interior_extrema(shear(s.p, slant)) for s in orig)
	return interior_extrema(shear(fit.p, slant)) > before


def _cost(left: _Piece, right: _Piece, opts):
	fits, errors = [], []
	slant = math.tan(math.radians(opts.italic_angle))
	for m in range(len(left.orig)):
		run = left.orig[m] + right.orig[m]
		result = fit_one(run, opts)
		if result is None or (opts.keep_extrema and _adds_extremum(run, result[0], slant)):
			return INF, None
		fits.append(result[0])
		errors.append(result[1])

	if any(s.is_line for s in fits) and not all(s.is_line for s in fits):
		fits = [Seg(line_to_cubic(*s.p), s.src) if s.is_line else s for s in fits]

	return worst(errors), fits


# - Simplifier ---------------------------
def _simplify_span(pieces: list[_Piece], opts) -> list[_Piece]:
	k = len(pieces)
	prev = list(range(-1, k - 1))
	nxt = list(range(1, k + 1))
	alive = [True] * k
	version = [0] * k
	fits = [None] * k
	heap = []

	def push(j):
		cost, fit = _cost(pieces[prev[j]], pieces[j], opts)
		version[j] += 1
		fits[j] = fit
		if cost <= opts.fit_tol:
			heapq.heappush(heap, (cost, pieces[prev[j]].length + pieces[j].length, j, version[j]))

	for j in range(1, k):
		push(j)

	while heap:
		cost, _, j, v = heapq.heappop(heap)
		if v != version[j] or not alive[j]:
			continue

		left, right = pieces[prev[j]], pieces[j]
		pieces[prev[j]] = _Piece(fits[j], [a + b for a, b in zip(left.orig, right.orig)], left.length + right.length, left.knot)
		alive[j] = False

		p, n = prev[j], nxt[j]
		nxt[p] = n
		if n < k:
			prev[n] = p
			push(n)
		if p > 0:
			push(p)

	return [pieces[j] for j in range(k) if alive[j]]


def simplify(mc: MContour, spans: list[tuple[int, int]], opts) -> MContour:
	n = len(mc.knots)
	n_m = mc.n_masters
	segs = [[] for _ in range(n_m)]
	knots = []

	for i0, i1 in spans:
		idx = [i % n for i in range(i0, i1)]
		pieces = [_Piece([mc.segs[m][i] for m in range(n_m)], [[mc.segs[m][i]] for m in range(n_m)], arc_length(mc.segs[0][i].p), i) for i in idx]

		if len(pieces) > 1 and all(mc.segs[0][i].is_cubic for i in idx):
			kept = _simplify_span(pieces, opts)
		else:
			kept = pieces

		for piece in kept:
			knots.append(mc.knots[piece.knot])
			for m in range(n_m):
				segs[m].append(piece.cur[m])

		if __debug__:
			for m in range(n_m):
				assert kept[0].cur[m].p[0] == mc.segs[m][idx[0]].p[0], 'locked start moved'
				assert kept[-1].cur[m].p[-1] == mc.segs[m][idx[-1]].p[-1], 'locked end moved'

	return MContour(segs, knots, mc.index)
