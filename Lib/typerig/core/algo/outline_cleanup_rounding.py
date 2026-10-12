# MODULE: TypeRig / Core / Algo / Outline Cleanup — Integer rounding
# -----------------------------------------------------------
# Round half away from zero, then rerun Stage A (rounding can
# create coincident nodes, zero handles and spikes) until stable.
# Locked H/V handles stay exactly H/V. A lightweight take on
# iterated snap rounding (Halperin & Packer 2002).
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

from typerig.core.algo.outline_cleanup_geom import Seg, hv_deviation
from typerig.core.algo.outline_cleanup_convert import MContour
from typerig.core.algo.outline_cleanup_degenerate import stage_a

__version__ = '1.0.0'

MAX_ROUNDS = 4
ROUNDING_SLACK = .71		# half a unit diagonal


def round_half_away(value: float) -> float:
	return math.copysign(math.floor(abs(value) + .5), value) + 0.


def _round_point(q):
	return (round_half_away(q[0]), round_half_away(q[1]))


def _snap_handle(handle, on, new_on, opts):
	'''Round a handle; keep it exactly H/V to its rounded on-curve.'''
	new = _round_point(handle)
	v = (handle[0] - on[0], handle[1] - on[1])
	if v == (0., 0.) or hv_deviation(v) > opts.hv_angle:
		return new
	if abs(v[0]) >= abs(v[1]):
		return (new[0], new_on[1])
	return (new_on[0], new[1])


def round_mcontour(mc: MContour, opts) -> MContour:
	n = len(mc.knots)
	result = []

	for segs in mc.segs:
		out = []
		for i, seg in enumerate(segs):
			p = seg.p
			q = [_round_point(pt) for pt in p]

			if len(p) > 2:
				if mc.knots[i].fixed:
					q[1] = _snap_handle(p[1], p[0], q[0], opts)
				if mc.knots[(i + 1) % n].fixed:
					q[-2] = _snap_handle(p[-2], p[-1], q[-1], opts) if len(p) == 4 else _snap_handle(q[-2], p[-1], q[-1], opts)

			out.append(Seg(tuple(q), seg.src))
		result.append(out)

	return MContour(result, list(mc.knots), mc.index)


def round_loop(mcs: list[MContour], opts) -> list[MContour]:
	'''round -> Stage A until nothing changes, max MAX_ROUNDS.'''
	changed = True
	for _ in range(MAX_ROUNDS):
		mcs = [round_mcontour(mc, opts) for mc in mcs]
		mcs, changed = stage_a(mcs, opts)
		if not changed:
			break

	if changed:
		mcs = [round_mcontour(mc, opts) for mc in mcs]

	return mcs
