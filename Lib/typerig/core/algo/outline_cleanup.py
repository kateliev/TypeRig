# MODULE: TypeRig / Core / Algo / Outline Cleanup
# -----------------------------------------------------------
# Remove redundant nodes and geometric debris from closed
# contours within a tolerance in font units. Works on cubic and
# quadratic outlines and on interpolation-compatible masters.
#
#   convert -> A degeneracy -> B locks -> C simplify (Levien,
#   Schneider fallback) -> [cu2qu] -> [round + A] -> [implied]
#
#   clean(masters, opts)          masters[m][c]: TypeRig Contour
#   clean_single(contours, opts)
#   locked_nodes(masters, opts)   node indices Stage B would lock
#
# Output is cubic by default; 'quad' (or 'auto' on TrueType input)
# needs fontTools cu2qu, imported lazily.
# Caller locks: node.lib['locked'] = True on an on-curve node.
# Open and hobby contours pass through unchanged.
#
# Future (speed): ~0.3 s for a 200-node all-smooth contour, target
# 0.2 s. The error metric dominates (Newton per sample on near-exact
# fits). Options: cap source samples on long runs, solve the Levien
# polynomial by root isolation instead of the 300-step scan, reuse
# neighbour costs that were already +inf.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Literal

from typerig.core.algo.outline_cleanup_geom import Seg, run_distance
from typerig.core.algo.outline_cleanup_convert import MContour, to_mcontour, from_mcontour, clone_contour, is_cleanable
from typerig.core.algo.outline_cleanup_masters import IncompatibleMasters, assert_compatible, assert_compatible_segments
from typerig.core.algo.outline_cleanup_degenerate import stage_a
from typerig.core.algo.outline_cleanup_locks import apply_locks
from typerig.core.algo.outline_cleanup_simplify import simplify
from typerig.core.algo.outline_cleanup_rounding import round_loop, ROUNDING_SLACK
from typerig.core.algo.outline_cleanup_quad import to_quadratic, remove_implied

__version__ = '1.0.0'
__all__ = ['clean', 'clean_single', 'locked_nodes', 'CleanOptions', 'IncompatibleMasters', 'contour_deviation']

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanOptions:
	eps_point: float = .5			# on-curves closer than this are coincident
	eps_handle: float = .5			# handles shorter than this are zero
	eps_collinear: float = .25		# max distance from a line to count as on it
	corner_angle: float = 5.		# deg; tangent difference above this is a corner
	hv_angle: float = .5			# deg; tangent this close to 0/90 is H/V
	fit_tol: float = 1.				# max distance between source and simplified outline
	quad_tol: float = 1.			# max error of cubic to quadratic conversion
	keep_extrema: bool = True
	keep_inflections: bool = False
	output: Literal['cubic', 'quad', 'auto'] = 'cubic'	# 'quad' / 'auto' need fontTools
	round_ints: bool = True
	min_contour_area: float = 4.	# square units; smaller contours are dropped
	italic_angle: float = 0.		# deg; H/V and extremum tests run upright
	simplify: bool = True			# False: degeneracy passes only (no node fitting)

	def __post_init__(self):
		if self.output not in ('cubic', 'quad', 'auto'):
			raise ValueError('output must be cubic, quad or auto')

	def for_upm(self, upm: float) -> 'CleanOptions':
		'''Defaults are tuned for 1000 UPM: scale the distances (and the area)
		so they behave the same at any UPM.'''
		s = upm / 1000.
		lengths = ('eps_point', 'eps_handle', 'eps_collinear', 'fit_tol', 'quad_tol')
		return replace(self, min_contour_area=self.min_contour_area * s * s, **{k: getattr(self, k) * s for k in lengths})


# - Deviation ----------------------------
def _rebase(mc: MContour) -> MContour:
	'''Make the current segments the reference: segment i covers [i, i+1).'''
	return MContour([[Seg(s.p, (i, i + 1)) for i, s in enumerate(segs)] for segs in mc.segs], mc.knots, mc.index)


def _deviation(mc: MContour, refs, bound: float) -> float:
	'''Max two-sided distance between each run of output segments with the
	same traceback range and the reference segments in that range.'''
	result = 0.

	for m, segs in enumerate(mc.segs):
		ref = refs[m]
		n_ref = len(ref)
		groups = []
		for seg in segs:
			if groups and groups[-1][0] == seg.src:
				groups[-1][1].append(seg.p)
			else:
				groups.append((seg.src, [seg.p]))

		for (a, b), out in groups:
			if b <= a:
				b += n_ref
			run = [ref[k % n_ref] for k in range(a, b)]
			result = max(result, run_distance(run, out, bound))

	return result


def contour_deviation(a, b) -> float:
	'''Two-sided distance between two TypeRig contours (whole outline).'''
	sa = [s.p for s in to_mcontour([a]).segs[0]]
	sb = [s.p for s in to_mcontour([b]).segs[0]]
	return run_distance(sa, sb)


# - Pipeline -----------------------------
def clean(masters: list[list], opts: CleanOptions | None = None) -> list[list]:
	'''masters[m][c] is contour c of master m (TypeRig Contours). Returns new
	contours; the input is not modified.'''
	opts = opts or CleanOptions()
	if not masters:
		return []

	assert_compatible(masters, 'input')
	n_m, n_c = len(masters), len(masters[0])

	quad_in = any(c.is_bezier and c.has_quadratic for c in masters[0])
	quad_out = opts.output == 'quad' or (opts.output == 'auto' and quad_in)

	work, passthrough = [], {}
	for c in range(n_c):
		group = [masters[m][c] for m in range(n_m)]
		if is_cleanable(group[0]):
			work.append(to_mcontour(group, c))
		else:
			passthrough[c] = [clone_contour(x) for x in group]

	# - Stage A: degeneracies; its output is the reference geometry
	work, _ = stage_a(work, opts)
	work = [_rebase(mc) for mc in work]
	refs = {mc.index: [[s.p for s in segs] for segs in mc.segs] for mc in work}

	# - Stage B + C: locks and simplification per span
	simplified = []
	for mc in work:
		mc, spans = apply_locks(mc, opts)
		simplified.append(simplify(mc, spans, opts) if opts.simplify else mc)
	work = simplified
	assert_compatible_segments(work, 'simplify')

	if quad_out:
		work = to_quadratic(work, opts)

	if opts.round_ints:
		work = round_loop(work, opts)

	if quad_out:
		work = remove_implied(work, opts)

	assert_compatible_segments(work, 'output')

	limit = opts.fit_tol + (opts.quad_tol if quad_out else 0.) + (ROUNDING_SLACK if opts.round_ints else 0.)
	for mc in work:
		err = _deviation(mc, refs[mc.index], limit)
		if err > limit:
			log.warning('Outline cleanup: contour %s deviates %.3f units (limit %.3f)', mc.index, err, limit)

	# - Out
	by_index = {mc.index: from_mcontour(mc, [masters[m][mc.index] for m in range(n_m)]) for mc in work}
	result = [[] for _ in range(n_m)]
	for c in range(n_c):
		group = passthrough.get(c) or by_index.get(c)
		if group is None:
			continue	# dropped as tiny
		for m in range(n_m):
			result[m].append(group[m])

	assert_compatible(result, 'output')
	return result


def clean_single(contours: list, opts: CleanOptions | None = None) -> list:
	return clean([contours], opts)[0]


def locked_nodes(masters: list[list], opts: CleanOptions | None = None) -> list[list[int]]:
	'''Per input contour, the indices of the on-curve nodes Stage B locks
	(after Stage A). Dropped, open and hobby contours give [].'''
	opts = opts or CleanOptions()
	if not masters:
		return []

	assert_compatible(masters, 'input')
	n_m = len(masters)
	work = [to_mcontour([masters[m][c] for m in range(n_m)], c) for c in range(len(masters[0])) if is_cleanable(masters[0][c])]
	work, _ = stage_a(work, opts)

	result = [[] for _ in masters[0]]
	for mc in work:
		mc, _ = apply_locks(mc, opts)
		result[mc.index] = [k.src for k in mc.knots if k.fixed and k.src >= 0]

	return result
