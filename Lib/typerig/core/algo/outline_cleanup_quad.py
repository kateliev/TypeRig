# MODULE: TypeRig / Core / Algo / Outline Cleanup — Quadratic output
# -----------------------------------------------------------
# All simplification runs in cubic space; quadratics exist only
# at the boundary. Cubics go back to TrueType splines with one
# fontTools cu2qu call per segment for all masters (compatible
# off-curve counts), then exact-midpoint on-curves are dropped.
# Native quadratic simplification (knot removal) is a later phase.
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

from typerig.core.algo.outline_cleanup_geom import Seg
from typerig.core.algo.outline_cleanup_convert import Knot, MContour
from typerig.core.algo.outline_cleanup_masters import every

__version__ = '1.0.0'

MIDPOINT_EPS = 1e-9		# midpoint test tolerance for unrounded output
MAX_RETRIES = 4			# cu2qu tolerance doublings before giving up


def _splines(curves, tol):
	# fontTools is imported only when quadratic output is asked for,
	# so the cubic pipeline runs without it (e.g. inside FontLab)
	try:
		from fontTools.cu2qu import curves_to_quadratic
		from fontTools.cu2qu.errors import ApproxNotFoundError
	except ImportError:
		raise ImportError('Quadratic output needs fontTools (pip install fonttools); use output="cubic"')

	for _ in range(MAX_RETRIES + 1):
		try:
			return curves_to_quadratic(curves, [tol] * len(curves))
		except ApproxNotFoundError:
			tol *= 2.
	raise ApproxNotFoundError(curves)


def to_quadratic(mcs: list[MContour], opts) -> list[MContour]:
	result = []

	for mc in mcs:
		segs = [[] for _ in range(mc.n_masters)]
		knots = []

		for i, knot in enumerate(mc.knots):
			column = [s[i] for s in mc.segs]

			if not column[0].is_cubic:
				knots.append(knot)
				for m, seg in enumerate(column):
					segs[m].append(seg)
				continue

			splines = _splines([seg.p for seg in column], opts.quad_tol)
			n_offs = len(splines[0]) - 2
			knots.append(knot)
			knots.extend(Knot(implied=True, smooth=True) for _ in range(n_offs - 1))

			for m, (spline, seg) in enumerate(zip(splines, column)):
				spline = [tuple(map(float, q)) for q in spline]
				offs = spline[1:-1]
				start = seg.p[0]
				for j, q in enumerate(offs):
					end = seg.p[-1] if j == len(offs) - 1 else ((q[0] + offs[j + 1][0]) * .5, (q[1] + offs[j + 1][1]) * .5)
					segs[m].append(Seg((start, q, end), seg.src))
					start = end

		result.append(MContour(segs, knots, mc.index))

	return result


def _is_midpoint(on, a, b, exact: bool) -> bool:
	if exact:
		return 2. * on[0] == a[0] + b[0] and 2. * on[1] == a[1] + b[1]
	return abs(2. * on[0] - a[0] - b[0]) <= MIDPOINT_EPS and abs(2. * on[1] - a[1] - b[1]) <= MIDPOINT_EPS


def remove_implied(mcs: list[MContour], opts) -> list[MContour]:
	'''Lossless: write an on-curve as implied when it is the exact midpoint
	of its two quadratic off-curves in every master. Caller locks and
	Stage B locks on input on-curves are kept.'''
	result = []

	for mc in mcs:
		n = len(mc.knots)
		knots = list(mc.knots)

		for i in range(1, n):
			knot = knots[i]
			if knot.locked or (knot.fixed and not knot.implied):
				continue
			if not (mc.segs[0][i - 1].is_quad and mc.segs[0][i].is_quad):
				continue
			if every(_is_midpoint(s[i].p[0], s[i - 1].p[1], s[i].p[1], opts.round_ints) for s in mc.segs):
				knots[i] = replace(knot, omit=True)

		result.append(MContour([list(s) for s in mc.segs], knots, mc.index))

	return result
