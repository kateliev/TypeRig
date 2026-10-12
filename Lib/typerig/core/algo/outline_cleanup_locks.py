# MODULE: TypeRig / Core / Algo / Outline Cleanup — Stage B
# -----------------------------------------------------------
# Locked on-curves are never removed or moved by the simplifier.
# A knot is locked if any rule fires in any master; locked knots
# split each contour into spans the simplifier works inside.
# Missing extrema are not inserted (later feature).
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

import math
from dataclasses import replace

from typerig.core.algo.outline_cleanup_geom import (
	start_tangent, end_tangent, angle_between, hv_deviation, point_at, signed_curvature, dist, unit, shear, Seg
)
from typerig.core.algo.outline_cleanup_convert import MContour
from typerig.core.algo.outline_cleanup_masters import some

__version__ = '1.0.0'

EXTREMUM_PROBE_T = .05		# how far into each neighbour the extremum test looks
CURVATURE_PROBE_T = .02		# endpoint offset for the curvature sign test


# - Rules --------------------------------
def _handles(seg_in, seg_out, eps):
	'''Non-degenerate handles adjacent to the knot between seg_in and seg_out.'''
	result = []
	if len(seg_in.p) > 2 and dist(seg_in.p[-1], seg_in.p[-2]) >= eps:
		result.append((seg_in.p[-1][0] - seg_in.p[-2][0], seg_in.p[-1][1] - seg_in.p[-2][1]))
	if len(seg_out.p) > 2 and dist(seg_out.p[0], seg_out.p[1]) >= eps:
		result.append((seg_out.p[1][0] - seg_out.p[0][0], seg_out.p[1][1] - seg_out.p[0][1]))
	return result


def _is_extremum(seg_in, seg_out, t_in, t_out, opts) -> bool:
	t = unit((t_in[0] + t_out[0], t_in[1] + t_out[1]))
	if t is None or hv_deviation(t) > opts.hv_angle:
		return False

	axis = 1 if abs(t[0]) > abs(t[1]) else 0		# horizontal tangent: y-extremum
	knot = seg_out.p[0][axis]
	da = point_at(seg_in.p, 1. - EXTREMUM_PROBE_T)[axis] - knot
	db = point_at(seg_out.p, EXTREMUM_PROBE_T)[axis] - knot
	return (da <= 0. and db <= 0.) or (da >= 0. and db >= 0.)


def _is_inflection(seg_in, seg_out) -> bool:
	k_in = signed_curvature(seg_in.p, 1. - CURVATURE_PROBE_T)
	k_out = signed_curvature(seg_out.p, CURVATURE_PROBE_T)
	return k_in * k_out < 0.


def _fires(seg_in, seg_out, opts) -> bool:
	if seg_in.is_line or seg_out.is_line:
		return True		# line/curve and line/line junctions

	# H/V and extremum tests run in the upright frame of an italic
	slant = math.tan(math.radians(opts.italic_angle))
	if slant:
		seg_in, seg_out = Seg(shear(seg_in.p, slant)), Seg(shear(seg_out.p, slant))

	t_in = end_tangent(seg_in.p, opts.eps_handle)
	t_out = start_tangent(seg_out.p, opts.eps_handle)

	if t_in is None or t_out is None or angle_between(t_in, t_out) > opts.corner_angle:
		return True

	if any(hv_deviation(h) <= opts.hv_angle for h in _handles(seg_in, seg_out, opts.eps_handle)):
		return True

	if opts.keep_extrema and _is_extremum(seg_in, seg_out, t_in, t_out, opts):
		return True

	if opts.keep_inflections and _is_inflection(seg_in, seg_out):
		return True

	return False


# - Stage --------------------------------
def compute_locks(mc: MContour, opts) -> list[bool]:
	n = len(mc.knots)
	locked = []

	for i in range(n):
		if i == 0 or mc.knots[i].locked:
			locked.append(True)
			continue

		locked.append(some(_fires(segs[i - 1], segs[i], opts) for segs in mc.segs))

	return locked


def spans(locked: list[bool]) -> list[tuple[int, int]]:
	'''(i0, i1) knot ranges between consecutive locked knots; i1 == n closes
	the contour back to knot 0. Knot 0 is always locked.'''
	n = len(locked)
	marks = [i for i, flag in enumerate(locked) if flag] + [n]
	return [(marks[k], marks[k + 1]) for k in range(len(marks) - 1)]


def apply_locks(mc: MContour, opts) -> tuple[MContour, list[tuple[int, int]]]:
	locked = compute_locks(mc, opts)
	mc = MContour([list(s) for s in mc.segs], [replace(k, fixed=f) for k, f in zip(mc.knots, locked)], mc.index)
	return mc, spans(locked)
