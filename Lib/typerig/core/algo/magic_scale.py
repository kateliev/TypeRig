# MODULE: TypeRig / Core / Algo / Magic Scale
# -----------------------------------------------------------
# Stem-preserving 1D warp of a single layer, per axis.
# On each axis the glyph is a run of alternating intervals:
#
#   lo |margin| stem |gap| stem |gap| stem |margin| hi
#
# Stems (ink) take L * stem_factor; gaps share what is left of
# the new extent, weighted by counter (interior vs margins,
# 中宫) and gravity (whitespace skew along the axis, 重心).
# Source and target knots define a monotone piecewise-linear
# map that every node coordinate on that axis goes through.
# X and Y are independent; alignment is part of each map.
#
# Pipeline:
#   detect_knot_refs  -> {'x': refs, 'y': refs}   (StemDetector, once)
#   build_axis_warp   -> AxisWarp                  (per axis, per tick)
#   warp_layer        -> WarpReport                (in place)
#
# gravity sign: 0 is neutral. gravity > 0 pushes whitespace
# toward the HIGH end of the axis, so the ink moves toward
# LOWER coordinates; gravity < 0 does the opposite.
#
# Known limitations:
#   - Exact only for axis-aligned stems. Diagonal and curved
#     strokes change thickness by roughly
#     sx*sy / sqrt((sx*cos t)^2 + (sy*sin t)^2) locally, and
#     unevenly where they cross ink and gap intervals. Diagonals
#     belong to the Stroke Scale track, not here.
#   - Large factors break the visual rhythm; this is for small
#     adjustments.
#   - Stems that overlap on one axis but belong to different
#     rows are merged into one wider ink block.
#   - The ink centroid assumes overlap-free outlines.
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
from bisect import bisect_right

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer
from typerig.core.objects.transform import TransformOrigin
from typerig.core.objects.utils import Bounds
from typerig.core.algo.stem_snap import (
	StemDetector, Axis, DetectMode, Topology,
	_make_rect_contour as _R, _make_cw_rect_contour as _RCW, _make_h_glyph,
)
from typerig.core.algo.cjk import glyph_centroid

__version__ = '0.1.0'


# - Tunables ----------------------------
_MERGE_TOL     = 1.0     # stems closer than this (units) merge into one ink block
_ZERO_LEN      = 1e-6    # gaps shorter than this are dropped at the ends
_MIN_EXTENT    = 1.0     # axes narrower than this are skipped
_MAX_STEM_FRAC = 0.3     # auto max_stem = this * extent

_AXES = ('x', 'y')
_STEM_AXIS = {'x': Axis.V, 'y': Axis.H}

# Codes resolved by Bounds.align_matrix. 'B' is the absolute origin (0, 0).
_ALIGN_CODES = ('BL', 'BM', 'BR', 'LM', 'C', 'RM', 'TL', 'TM', 'TR', 'B')
_HANDLE_MODES = ('anchored', 'direct')


# - Parameters --------------------------
class WarpParams(object):
	'''User controls for warp_layer / warp_masters / process.

	Per axis: scale_* (new extent multiplier), stem_v / stem_h (X-stem /
	Y-stem thickness factor), counter_* (interior-gap weight vs margins),
	gravity_* (0 = neutral, > 0 moves ink toward lower coordinates),
	centroid_* (None, or target ink centroid in font units; overrides
	gravity on that axis).
	'''
	__slots__ = (
		'scale_x', 'scale_y',
		'stem_v', 'stem_h',
		'counter_x', 'counter_y',
		'gravity_x', 'gravity_y',
		'centroid_x', 'centroid_y',
		'align',
		'frame',
		'max_stem',
		'min_gap',
		'handle_mode',
		'detect_mode', 'topology',
	)

	_DEFAULTS = {
		'scale_x': 1.0, 'scale_y': 1.0,
		'stem_v': 1.0, 'stem_h': 1.0,
		'counter_x': 1.0, 'counter_y': 1.0,
		'gravity_x': 0.0, 'gravity_y': 0.0,
		'centroid_x': None, 'centroid_y': None,
		'align': TransformOrigin.CENTER,
		'frame': None,
		'max_stem': None,
		'min_gap': 0.0,
		'handle_mode': 'anchored',
		'detect_mode': DetectMode.COINCIDENT,
		'topology': Topology.STRICT,
	}

	def __init__(self, **kwargs):
		unknown = [k for k in kwargs if k not in self._DEFAULTS]
		if unknown:
			raise ValueError('WarpParams: unknown keys {}'.format(sorted(unknown)))

		for key, value in self._DEFAULTS.items():
			setattr(self, key, kwargs.get(key, value))

		self.align = _coerce_align(self.align)

		for key in ('scale_x', 'scale_y', 'stem_v', 'stem_h', 'counter_x', 'counter_y'):
			value = float(getattr(self, key))
			if value <= 0.0:
				raise ValueError('WarpParams: {} must be > 0, got {}'.format(key, value))
			setattr(self, key, value)

		self.gravity_x = float(self.gravity_x)
		self.gravity_y = float(self.gravity_y)
		self.min_gap = max(0.0, float(self.min_gap))

		if self.handle_mode not in _HANDLE_MODES:
			raise ValueError('WarpParams: handle_mode must be one of {}'.format(_HANDLE_MODES))

		if self.frame is not None:
			xmin, ymin, xmax, ymax = [float(v) for v in self.frame]
			self.frame = (xmin, ymin, xmax, ymax)

	def __repr__(self):
		return 'WarpParams({})'.format(', '.join(
			'{}={!r}'.format(k, getattr(self, k)) for k in self.__slots__))

	@classmethod
	def from_dict(cls, d):
		'''Build from a dict, dropping unknown keys.
		Returns (params, ignored_keys).'''
		d = dict(d or {})
		ignored = sorted(k for k in d if k not in cls._DEFAULTS)
		for k in ignored:
			d.pop(k)
		return cls(**d), ignored


def _coerce_align(value):
	'''TransformOrigin, or a code / name string -> TransformOrigin (Bounds codes only).'''
	if isinstance(value, TransformOrigin):
		origin = value
	else:
		origin = None
		for item in TransformOrigin:
			if value in (item.code, item.value[0], item.name):
				origin = item
				break
		if origin is None:
			raise ValueError('align: unknown origin {!r}'.format(value))

	if origin.code not in _ALIGN_CODES:
		raise ValueError('align: {} is not resolvable from a frame; use one of {}'.format(
			origin.code, _ALIGN_CODES))
	return origin


def _axis_params(params, axis):
	'''(scale, stem_factor, counter, gravity) for one axis.'''
	if axis == 'x':
		return params.scale_x, params.stem_v, params.counter_x, params.gravity_x
	return params.scale_y, params.stem_h, params.counter_y, params.gravity_y


# - Axis map ----------------------------
class AxisWarp(object):
	'''Monotone piecewise-linear map for one axis. Alignment is included.

	refs  : list of (face_lo, face_hi) per ink interval; a face is a list
	        of (contour_idx, node_idx).
	flags : set of axis-local flags ('collapsed', 'no_stems', 'skipped').
	        Not in the handout's slot list; carries status to WarpReport.
	'''
	__slots__ = ('axis', 'src_knots', 'dst_knots', 'kinds', 'refs', 'flags')

	def __init__(self, axis, src_knots, dst_knots, kinds, refs=None, flags=None):
		self.axis = axis
		self.src_knots = list(src_knots)
		self.dst_knots = list(dst_knots)
		self.kinds = list(kinds)
		self.refs = list(refs or [])
		self.flags = set(flags or [])

	def __repr__(self):
		return 'AxisWarp({}, src={}, dst={}, kinds={}, flags={})'.format(
			self.axis,
			['{:.2f}'.format(v) for v in self.src_knots],
			['{:.2f}'.format(v) for v in self.dst_knots],
			self.kinds, sorted(self.flags))

	def _segment(self, v):
		# Ties go to the segment on the right; the last segment at hi.
		i = bisect_right(self.src_knots, v) - 1
		return min(max(i, 0), len(self.src_knots) - 2)

	def slope_at(self, v):
		i = self._segment(v)
		s0, s1 = self.src_knots[i], self.src_knots[i + 1]
		d0, d1 = self.dst_knots[i], self.dst_knots[i + 1]
		return (d1 - d0) / (s1 - s0)

	def map(self, v):
		i = self._segment(v)
		return self.dst_knots[i] + (v - self.src_knots[i]) * self.slope_at(v)

	def is_identity(self, tol=1e-9):
		return all(abs(s - d) <= tol for s, d in zip(self.src_knots, self.dst_knots))


# - Report ------------------------------
class WarpReport(object):
	'''flags: set of '<flag>_<axis>' strings; empty set = ok.'''
	__slots__ = ('warp_x', 'warp_y', 'flags', 'messages', 'gravity_solved', 'centroid_achieved')

	def __init__(self):
		self.warp_x = None
		self.warp_y = None
		self.flags = set()
		self.messages = []
		self.gravity_solved = {}
		self.centroid_achieved = {}

	def __repr__(self):
		return 'WarpReport(flags={}, gravity_solved={}, messages={})'.format(
			sorted(self.flags), self.gravity_solved, self.messages)


# - Frame -------------------------------
def _frame_of(layer, params):
	if params.frame is not None:
		return params.frame
	b = layer.bounds
	return (float(b.x), float(b.y), float(b.xmax), float(b.ymax))


def _axis_range(frame, axis):
	return (frame[0], frame[2]) if axis == 'x' else (frame[1], frame[3])


def _anchor_coord(frame, align, axis):
	ax, ay = Bounds([(frame[0], frame[1]), (frame[2], frame[3])]).align_matrix[align.code]
	return float(ax) if axis == 'x' else float(ay)


# - Detection ---------------------------
def _merge_intervals(intervals, lo, hi):
	'''intervals: [(a, b, face_a, face_b)] -> merged, clamped, sorted refs.'''
	clamped = []
	for a, b, fa, fb in intervals:
		a, b = max(a, lo), min(b, hi)
		if b - a > _ZERO_LEN:
			clamped.append((a, b, fa, fb))
	clamped.sort(key=lambda item: (item[0], item[1]))

	merged = []
	for a, b, fa, fb in clamped:
		if merged and a <= merged[-1][1] + _MERGE_TOL:
			ca, cb, cfa, cfb = merged[-1]
			if b > cb:
				merged[-1] = (ca, b, cfa, fb)
		else:
			merged.append((a, b, fa, fb))
	return [(fa, fb) for _a, _b, fa, fb in merged]


def detect_knot_refs(contours, frame, params):
	'''Run StemDetector once and return {'x': refs, 'y': refs}.

	refs: ink intervals in order, as (face_lo, face_hi); each face is a
	list of (contour_idx, node_idx). This is the only function that runs
	the detector; reuse its result for every slider tick and every master.
	'''
	detector = StemDetector(mode=params.detect_mode, topology=params.topology)
	candidates = detector.detect(contours) if contours else []
	out = {}

	for axis in _AXES:
		lo, hi = _axis_range(frame, axis)
		extent = hi - lo
		if extent < _MIN_EXTENT:
			out[axis] = []
			continue

		max_stem = params.max_stem if params.max_stem is not None else _MAX_STEM_FRAC * extent
		intervals = []
		for cand in candidates:
			if cand.axis != _STEM_AXIS[axis] or cand.measured_width > max_stem:
				continue
			ea, eb = cand.edge_a, cand.edge_b   # detector guarantees ea.coord <= eb.coord
			face_a = [(ea.contour_idx, ni) for ni in ea.node_indices]
			face_b = [(eb.contour_idx, ni) for ni in eb.node_indices]
			intervals.append((ea.coord, eb.coord, face_a, face_b))
		out[axis] = _merge_intervals(intervals, lo, hi)
	return out


def _face_coord(contours, face, axis):
	total = 0.0
	for ci, ni in face:
		node = contours[ci].nodes[ni]
		total += node.x if axis == 'x' else node.y
	return total / len(face)


def _intervals_from_refs(contours, axis, lo, hi, refs):
	'''Rebuild (a, b) per ink interval on this layer. Raises ValueError if the
	referenced faces are not in strictly increasing order (folded map).'''
	out = []
	prev = lo - 1.0
	for face_lo, face_hi in refs:
		a = min(max(_face_coord(contours, face_lo, axis), lo), hi)
		b = min(max(_face_coord(contours, face_hi, axis), lo), hi)
		if not (a < b and a > prev - _ZERO_LEN):
			raise ValueError('magic_scale: knots not increasing on axis {} ({:.2f}, {:.2f} after {:.2f})'.format(
				axis, a, b, prev))
		out.append((a, b))
		prev = b
	return out


# - Lengths -----------------------------
def _knots(intervals, lo, hi):
	knots, kinds = [lo], []
	for a, b in intervals:
		if a - knots[-1] > _ZERO_LEN:
			kinds.append('gap')
			knots.append(a)
		kinds.append('ink')
		knots.append(b)
	if hi - knots[-1] > _ZERO_LEN:
		kinds.append('gap')
		knots.append(hi)
	else:
		knots[-1] = hi   # last ink face sits on hi (within _ZERO_LEN)
	return knots, kinds


def _share_gaps(G, weights, min_gap):
	'''Split budget G by weight, keeping every gap >= min_gap.
	Returns (lengths, collapsed).'''
	n = len(weights)
	if G < n * min_gap - 1e-12:
		return [min_gap] * n, True

	fixed = set()
	while True:
		free = [i for i in range(n) if i not in fixed]
		if not free:
			return [min_gap] * n, False
		rest = G - min_gap * len(fixed)
		total_w = sum(weights[i] for i in free)
		lengths = [min_gap] * n
		for i in free:
			lengths[i] = rest * weights[i] / total_w if total_w > 0 else rest / len(free)
		below = [i for i in free if lengths[i] < min_gap - 1e-12]
		if not below:
			return lengths, False
		fixed.update(below)


def _warp_from_intervals(axis, intervals, lo, hi, params, gravity, anchor, refs=None):
	scale, stem, counter, _g = _axis_params(params, axis)
	flags = set()
	if not intervals:
		flags.add('no_stems')

	knots, kinds = _knots(intervals, lo, hi)
	lengths = [knots[i + 1] - knots[i] for i in range(len(kinds))]
	new = [0.0] * len(kinds)

	ink_total = 0.0
	for i, kind in enumerate(kinds):
		if kind == 'ink':
			new[i] = lengths[i] * stem
			ink_total += new[i]

	gaps = [i for i, kind in enumerate(kinds) if kind == 'gap']
	G = (hi - lo) * scale - ink_total

	if gaps:
		last = len(kinds) - 1
		interior = [i for i in gaps if 0 < i < last]
		weights = []
		for i in gaps:
			if interior and i in interior:
				t = ((knots[i] + knots[i + 1]) * 0.5 - lo) / (hi - lo)
				weights.append(lengths[i] * counter * math.exp(gravity * (t - 0.5)))
			else:
				weights.append(lengths[i])
		shared, collapsed = _share_gaps(G, weights, params.min_gap)
		if collapsed:
			flags.add('collapsed')
		for i, value in zip(gaps, shared):
			new[i] = value
	elif abs(G) > 1e-9:
		flags.add('collapsed')   # ink fills the frame; extent cannot follow scale

	dst = [lo]
	for value in new:
		dst.append(dst[-1] + value)

	# Alignment: the anchor is a point of the FRAME, not of the ink. Keep it
	# at the same relative position in the warped frame [dst[0], dst[-1]].
	# (Shifting so map(anchor) == anchor would pin whatever ink sits there.)
	f = (anchor - lo) / (hi - lo)
	shift = anchor - (dst[0] + f * (dst[-1] - dst[0]))
	return AxisWarp(axis, knots, [v + shift for v in dst], kinds, refs, flags)


def build_axis_warp(contours, axis, lo, hi, params, knot_refs=None, gravity=None):
	'''Build the AxisWarp for one axis ('x' or 'y').

	knot_refs None -> detect stems here; otherwise reuse the refs for this
	axis (the list returned in detect_knot_refs(...)[axis]).
	gravity None -> params.gravity_<axis>.
	'''
	params = params if isinstance(params, WarpParams) else WarpParams(**(params or {}))
	frame = params.frame
	if frame is None:
		frame = (lo, lo, hi, hi)   # only the axis range is read below
	if axis == 'x':
		frame = (lo, frame[1], hi, frame[3])
	else:
		frame = (frame[0], lo, frame[2], hi)

	if hi - lo < _MIN_EXTENT:
		return AxisWarp(axis, [lo, lo + 1.0], [lo, lo + 1.0], ['gap'], flags=['skipped'])

	if knot_refs is None:
		knot_refs = detect_knot_refs(contours, frame, params)[axis]

	if gravity is None:
		gravity = _axis_params(params, axis)[3]

	intervals = _intervals_from_refs(contours, axis, lo, hi, knot_refs)
	anchor = _anchor_coord(frame, params.align, axis)
	return _warp_from_intervals(axis, intervals, lo, hi, params, gravity, anchor, knot_refs)


# - Node application --------------------
def _apply_warps(contours, warp_x, warp_y, handle_mode):
	'''Map every node. All source coordinates are read before any write.'''
	for contour in contours:
		nodes = list(contour.nodes)
		n = len(nodes)
		src = [(nd.x, nd.y) for nd in nodes]
		closed = bool(getattr(contour, 'closed', True))
		out = []

		for i, nd in enumerate(nodes):
			x, y = src[i]
			parent = None

			if handle_mode == 'anchored' and not nd.is_on:
				# Same rule as Node.prev_on / next_on, walked by index so open
				# contour ends return None instead of wrapping.
				p = i - 1 if (i > 0 or closed) else None
				if p is not None and nodes[p % n].is_on:
					parent = p % n
				else:
					k = i + 1
					while k < n + i + 1:
						if k >= n and not closed:
							break
						if nodes[k % n].is_on:
							parent = k % n
							break
						k += 1

			if parent is None:
				out.append((warp_x.map(x), warp_y.map(y)))
			else:
				px, py = src[parent]
				out.append((warp_x.map(px) + (x - px) * warp_x.slope_at(px),
				            warp_y.map(py) + (y - py) * warp_y.slope_at(py)))

		for nd, (x, y) in zip(nodes, out):
			nd.x, nd.y = x, y


# - Centroid ----------------------------
def ink_centroid(contours, samples=16):
	'''Area-weighted ink centroid (cx, cy) over sampled contours, or None.
	Counters subtract through winding. Precondition: overlap-free
	outlines; with overlapping strokes the result is approximate.'''
	polys = [c.sample(samples) for c in contours]
	return glyph_centroid([p for p in polys if len(p) >= 3])


def solve_gravity(contours, axis, target, lo, hi, params, g_lo=-6.0, g_hi=6.0,
                  iterations=28, tol=0.25, knot_refs=None, samples=16):
	'''Bisect gravity on one axis so the ink centroid lands on target.
	No layer copies: the source is sampled once and each trial maps the
	sample coordinates through the trial AxisWarp (direct mapping).

	Returns (gravity, achieved, reachable).
	'''
	params = params if isinstance(params, WarpParams) else WarpParams(**(params or {}))
	frame = params.frame
	if frame is None:
		frame = (lo, lo, hi, hi)
	frame = (lo, frame[1], hi, frame[3]) if axis == 'x' else (frame[0], lo, frame[2], hi)

	if knot_refs is None:
		knot_refs = detect_knot_refs(contours, frame, params)[axis]

	intervals = _intervals_from_refs(contours, axis, lo, hi, knot_refs)
	anchor = _anchor_coord(frame, params.align, axis)
	polys = [p for p in (c.sample(samples) for c in contours) if len(p) >= 3]
	k = 0 if axis == 'x' else 1

	def measure(g):
		warp = _warp_from_intervals(axis, intervals, lo, hi, params, g, anchor)
		if k == 0:
			mapped = [[(warp.map(x), y) for x, y in poly] for poly in polys]
		else:
			mapped = [[(x, warp.map(y)) for x, y in poly] for poly in polys]
		c = glyph_centroid(mapped)
		return None if c is None else c[k]

	f_lo, f_hi = measure(g_lo), measure(g_hi)
	if f_lo is None or f_hi is None:
		return _axis_params(params, axis)[3], None, False

	if not (min(f_lo, f_hi) - tol <= target <= max(f_lo, f_hi) + tol):
		if abs(f_lo - target) <= abs(f_hi - target):
			return g_lo, f_lo, False
		return g_hi, f_hi, False

	a, b, fa = g_lo, g_hi, f_lo
	g, f = a, fa
	for _ in range(iterations):
		g = 0.5 * (a + b)
		f = measure(g)
		if abs(f - target) < tol:
			break
		if (fa - target) * (f - target) > 0:
			a, fa = g, f
		else:
			b = g
	return g, f, True


# - Layer level -------------------------
def _coerce_params(params):
	if params is None:
		return WarpParams(), []
	if isinstance(params, WarpParams):
		return params, []
	return WarpParams.from_dict(params)


def _plan_layer(layer, params, knot_refs=None):
	'''Build both AxisWarps and the report; does not modify the layer.
	Returns (warp_x, warp_y, report) or (None, None, report) when empty.'''
	report = WarpReport()
	contours = layer.contours
	if not contours or not any(len(c.nodes) for c in contours):
		return None, None, report

	frame = _frame_of(layer, params)
	if knot_refs is None:
		knot_refs = detect_knot_refs(contours, frame, params)

	warps = {}
	for axis in _AXES:
		lo, hi = _axis_range(frame, axis)
		target = params.centroid_x if axis == 'x' else params.centroid_y
		gravity = None
		local = WarpParams(**{k: getattr(params, k) for k in WarpParams.__slots__})
		local.frame = frame

		if target is not None and hi - lo >= _MIN_EXTENT:
			gravity, achieved, reachable = solve_gravity(
				contours, axis, float(target), lo, hi, local, knot_refs=knot_refs[axis])
			report.gravity_solved[axis] = gravity
			if not reachable:
				report.flags.add('centroid_unreachable_' + axis)
				report.messages.append('centroid_{} = {} not reachable; using gravity {:.3f}'.format(
					axis, target, gravity))

		warp = build_axis_warp(contours, axis, lo, hi, local, knot_refs=knot_refs[axis], gravity=gravity)
		for flag in warp.flags:
			report.flags.add('{}_{}'.format(flag, axis))
		warps[axis] = warp

	report.warp_x, report.warp_y = warps['x'], warps['y']
	return warps['x'], warps['y'], report


def _finish(layer, report):
	if report.gravity_solved:
		c = ink_centroid(layer.contours)
		for axis in report.gravity_solved:
			report.centroid_achieved[axis] = None if c is None else c[0 if axis == 'x' else 1]


def warp_layer(layer, params, knot_refs=None):
	'''Warp layer in place. knot_refs: result of detect_knot_refs for this
	layer (pass it to avoid detection on every call). Returns WarpReport.'''
	params, ignored = _coerce_params(params)
	warp_x, warp_y, report = _plan_layer(layer, params, knot_refs)
	for key in ignored:
		report.messages.append('ignored unknown key: {}'.format(key))
	if warp_x is None:
		return report
	_apply_warps(layer.contours, warp_x, warp_y, params.handle_mode)
	_finish(layer, report)
	return report


def warp_masters(layers, params, reference=0):
	'''Warp compatible layers with the same structural decisions.
	Stems are detected on layers[reference] only; each layer rebuilds its
	knots from the shared refs. Every warp is built before any layer is
	changed, so a failure leaves all layers untouched.'''
	params, _ignored = _coerce_params(params)
	if not layers:
		return []

	base = layers[reference].contours
	for li, layer in enumerate(layers):
		contours = layer.contours
		if len(contours) != len(base):
			raise ValueError('warp_masters: layer {} has {} contours, reference has {}'.format(
				li, len(contours), len(base)))
		for ci, (c, r) in enumerate(zip(contours, base)):
			if len(c.nodes) != len(r.nodes):
				raise ValueError('warp_masters: layer {} contour {} has {} nodes, reference has {}'.format(
					li, ci, len(c.nodes), len(r.nodes)))

	if not base:
		return [WarpReport() for _ in layers]

	refs = detect_knot_refs(base, _frame_of(layers[reference], params), params)

	plans = []
	for li, layer in enumerate(layers):
		try:
			plans.append(_plan_layer(layer, params, refs))
		except ValueError as e:
			raise ValueError('warp_masters: layer {}: {}'.format(li, e))

	reports = []
	for layer, (warp_x, warp_y, report) in zip(layers, plans):
		_apply_warps(layer.contours, warp_x, warp_y, params.handle_mode)
		_finish(layer, report)
		reports.append(report)
	return reports


def process(layer, params=None):
	'''Single entry point: params may be WarpParams, a dict or None.
	Unknown dict keys are reported in report.messages, not fatal.'''
	return warp_layer(layer, params)


# =====================================================================
# Self-tests.
# =====================================================================


def _approx(a, b, tol=1e-6):
	return abs(a - b) <= tol


def _layer(*contours):
	return Layer([Shape(list(contours))])


def _coords(layer):
	return [(n.x, n.y) for n in layer.nodes]


def _san():
	return _layer(_R(0, 0, 400, 40), _R(0, 280, 400, 40), _R(0, 560, 400, 40))


def _pillars():
	return _layer(_R(0, 0, 60, 600), _R(170, 0, 60, 600), _R(340, 0, 60, 600))


def _theta():
	return _layer(_R(0, 0, 400, 600), _RCW(80, 80, 240, 440), _R(80, 280, 240, 40))


def _ink_widths(warp):
	return [warp.dst_knots[i + 1] - warp.dst_knots[i] for i, k in enumerate(warp.kinds) if k == 'ink']


def _gap_widths(warp):
	return [warp.dst_knots[i + 1] - warp.dst_knots[i] for i, k in enumerate(warp.kinds) if k == 'gap']


def _bar_ys(layer):
	return sorted((min(n.y for n in c.nodes), max(n.y for n in c.nodes)) for c in layer.contours)


# --- Stage 1: identity ---
def _test_identity():
	layer = _layer(_make_h_glyph())
	before = _coords(layer)
	report = warp_layer(layer, WarpParams())
	after = _coords(layer)
	assert all(_approx(a[0], b[0], 1e-9) and _approx(a[1], b[1], 1e-9) for a, b in zip(before, after)), after
	assert report.warp_x.is_identity() and report.warp_y.is_identity(), report
	assert report.flags == set(), report.flags
	print('  identity: H unchanged, both maps identity [OK]')


# --- Stage 2: scale + stem factor on H ---
def _test_h_scale_and_stem():
	layer = _layer(_make_h_glyph())
	report = warp_layer(layer, WarpParams(scale_x=0.8, align='BL'))
	got = [round(v, 9) for v in report.warp_x.dst_knots]
	assert got == [0.0, 80.0, 240.0, 320.0], got
	assert report.warp_x.kinds == ['ink', 'gap', 'ink'], report.warp_x.kinds

	layer = _layer(_make_h_glyph())
	report = warp_layer(layer, WarpParams(stem_v=1.25, align='BL'))
	assert [round(v, 9) for v in _ink_widths(report.warp_x)] == [100.0, 100.0]
	assert _approx(_gap_widths(report.warp_x)[0], 200.0)
	assert _approx(layer.bounds.width, 400.0)
	print('  scale_x=0.8 -> knots 0,80,240,320; stem_v=1.25 -> stems 100, gap 200 [OK]')


# --- Stage 3: counter ---
def _test_counter():
	layer = _pillars()
	report = warp_layer(layer, WarpParams(counter_x=1.5, frame=(-50, 0, 450, 600)))
	w = report.warp_x
	assert w.kinds == ['gap', 'ink', 'gap', 'ink', 'gap', 'ink', 'gap'], w.kinds
	gaps = _gap_widths(w)
	assert gaps[1] > 110.0 and gaps[2] > 110.0, gaps
	assert gaps[0] < 50.0 and gaps[3] < 50.0, gaps
	assert _approx(w.dst_knots[-1] - w.dst_knots[0], 500.0)
	assert all(_approx(v, 60.0) for v in _ink_widths(w))
	assert 'no_stems_y' in report.flags   # 600-unit H "stems" removed by max_stem
	print('  counter_x=1.5: interior {:.1f}, margins {:.1f}, total 500, stems 60 [OK]'.format(gaps[1], gaps[0]))


# --- Stage 4: gravity sign ---
def _test_gravity_sign():
	src = _san()
	cy0 = ink_centroid(src.contours)[1]
	mids = {}
	for g in (2.0, -2.0):
		layer = _san()
		report = warp_layer(layer, WarpParams(gravity_y=g))
		bars = _bar_ys(layer)
		assert all(_approx(b - a, 40.0) for a, b in bars), bars
		assert 'no_stems_x' in report.flags   # 400-unit V "stems" removed by max_stem
		mids[g] = (bars[1][0] + bars[1][1]) * 0.5
		cy = ink_centroid(layer.contours)[1]
		assert (cy < cy0) if g > 0 else (cy > cy0), (g, cy, cy0)
	assert mids[2.0] < 300.0 < mids[-2.0], mids
	print('  gravity_y=+2 moves ink down ({:.1f}), -2 moves it up ({:.1f}) [OK]'.format(mids[2.0], mids[-2.0]))


# --- Stage 5: collapse ---
def _test_collapse():
	layer = _layer(_make_h_glyph())
	report = warp_layer(layer, WarpParams(scale_x=0.3))
	assert 'collapsed_x' in report.flags, report.flags
	assert all(_approx(v, 80.0) for v in _ink_widths(report.warp_x))
	assert all(v >= 0.0 for v in _gap_widths(report.warp_x))
	print('  scale_x=0.3: collapsed_x, stems 80, no negative gap [OK]')


# --- Stage 6: anchored handles ---
def _curve_fixture():
	stem = _R(0, 0, 80, 600)
	nodes = [
		Node(150, 200),
		Node(120, 230, type='curve'), Node(60, 280, type='curve'),
		Node(80, 300, smooth=True),
		Node(100, 320, type='curve'), Node(380, 380, type='curve'),
		Node(400, 400),   # frame 0..400 -> max_stem 120 keeps the 80-unit stem
	]
	return _layer(stem, Contour(nodes, closed=True))


def _cross_at_smooth(layer):
	nd = layer.contours[1].nodes
	h1, n, h2 = nd[2], nd[3], nd[4]
	return (n.x - h1.x) * (h2.y - n.y) - (n.y - h1.y) * (h2.x - n.x)


def _test_anchored_handles():
	layer = _curve_fixture()
	assert abs(_cross_at_smooth(layer)) < 1e-9
	warp_layer(layer, WarpParams(scale_x=0.8, handle_mode='anchored'))
	assert abs(_cross_at_smooth(layer)) < 1e-6, _cross_at_smooth(layer)

	layer = _curve_fixture()
	warp_layer(layer, WarpParams(scale_x=0.8, handle_mode='direct'))
	assert abs(_cross_at_smooth(layer)) > 1.0, _cross_at_smooth(layer)
	print('  anchored keeps handles collinear; direct breaks them (test has teeth) [OK]')


# --- Stage 7: alignment ---
def _test_alignment():
	for code, pick in (('BL', lambda b: (b.x, b.y)), ('TR', lambda b: (b.xmax, b.ymax))):
		layer = _layer(_make_h_glyph())
		before = pick(layer.bounds)
		warp_layer(layer, WarpParams(scale_x=0.8, scale_y=0.9, align=code))
		after = pick(layer.bounds)
		assert _approx(before[0], after[0]) and _approx(before[1], after[1]), (code, before, after)
	print('  BL and TR anchors stay fixed [OK]')


# --- Stage 8: centroid solve ---
def _test_centroid():
	cy0 = ink_centroid(_san().contours)[1]
	layer = _san()
	report = warp_layer(layer, WarpParams(centroid_y=cy0 + 20.0))
	assert 'y' in report.gravity_solved, report
	achieved = report.centroid_achieved['y']
	assert abs(achieved - (cy0 + 20.0)) < 0.25, (achieved, cy0)
	assert 'centroid_unreachable_y' not in report.flags
	solved = report.gravity_solved['y']

	layer = _san()
	report = warp_layer(layer, WarpParams(centroid_y=cy0 + 10000.0))
	assert 'centroid_unreachable_y' in report.flags, report.flags
	assert all(_approx(b - a, 40.0) for a, b in _bar_ys(layer))
	print('  centroid +20 reached ({:.2f}, g={:.3f}); absurd target flagged [OK]'.format(
		achieved - cy0, solved))


# --- Stage 9: warp_masters ---
def _stem_xs(layer):
	xs = sorted(set(round(n.x, 6) for n in layer.nodes))
	return xs


def _test_masters():
	a = _layer(_make_h_glyph(stem_w=60))
	b = _layer(_make_h_glyph(stem_w=120))
	reports = warp_masters([a, b], WarpParams(scale_x=0.9))
	for layer, stem in ((a, 60.0), (b, 120.0)):
		xs = _stem_xs(layer)
		assert _approx(xs[1] - xs[0], stem) and _approx(xs[3] - xs[2], stem), (stem, xs)
	assert reports[0].warp_x.refs == reports[1].warp_x.refs

	a = _layer(_make_h_glyph())
	b = _layer(_R(0, 0, 10, 10))
	before = _coords(a)
	try:
		warp_masters([a, b], WarpParams(scale_x=0.9))
		raise AssertionError('mismatch must raise')
	except ValueError:
		pass
	assert _coords(a) == before

	a = _layer(_make_h_glyph(stem_w=60))
	b = _layer(_make_h_glyph(stem_w=60))
	for ni in (1, 2, 9, 10):            # left stem's right face, moved left of x=0
		b.contours[0].nodes[ni].x = -10.0
	before_a, before_b = _coords(a), _coords(b)
	try:
		warp_masters([a, b], WarpParams(scale_x=0.9))
		raise AssertionError('swapped faces must raise')
	except ValueError as e:
		assert 'layer 1' in str(e), e
	assert _coords(a) == before_a and _coords(b) == before_b
	print('  masters keep own stems (60/120); mismatch and swapped faces raise, nothing changed [OK]')


# --- Stage 10: utilities and invariants ---
def _strictly_increasing(values):
	return all(values[i] < values[i + 1] for i in range(len(values) - 1))


def _test_utilities():
	layer = _theta()
	report = warp_layer(layer, WarpParams(scale_x=0.9, scale_y=0.9))
	for w in (report.warp_x, report.warp_y):
		assert _strictly_increasing(w.src_knots) and _strictly_increasing(w.dst_knots), w

	a, b = _layer(_make_h_glyph()), _layer(_make_h_glyph())
	ra = process(a, {'scale_x': 0.9, 'bogus': 1})
	warp_layer(b, WarpParams(scale_x=0.9))
	assert _coords(a) == _coords(b)
	assert any('bogus' in m for m in ra.messages), ra.messages

	empty = Layer([])
	report = warp_layer(empty, WarpParams(scale_x=0.5))
	assert report.flags == set() and report.warp_x is None

	tri = _layer(Contour([Node(0, 0), Node(400, 0), Node(200, 600)], closed=True))
	before = _coords(tri)
	report = warp_layer(tri, WarpParams(scale_x=0.8, scale_y=1.1, align='C'))
	assert {'no_stems_x', 'no_stems_y'} <= report.flags, report.flags
	for (x0, y0), (x1, y1) in zip(before, _coords(tri)):
		assert _approx(x1, 200 + (x0 - 200) * 0.8, 1e-9) and _approx(y1, 300 + (y0 - 300) * 1.1, 1e-9)

	src = _layer(_make_h_glyph())
	params = WarpParams(scale_x=0.85, gravity_y=1.0)
	refs = detect_knot_refs(src.contours, _frame_of(src, params), params)
	a, b = src.clone(), src.clone()
	warp_layer(a, params, knot_refs=refs)
	warp_layer(b, params)
	assert _coords(a) == _coords(b)
	print('  theta monotone; process(dict) == warp_layer; empty ok; no stems == affine; refs reuse [OK]')


def _run_stage1_tests(): print('Stage 1 - identity:');            _test_identity();             print('Stage 1: all tests passed.')
def _run_stage2_tests(): print('Stage 2 - scale and stem factor:'); _test_h_scale_and_stem();    print('Stage 2: all tests passed.')
def _run_stage3_tests(): print('Stage 3 - counter:');             _test_counter();              print('Stage 3: all tests passed.')
def _run_stage4_tests(): print('Stage 4 - gravity sign:');        _test_gravity_sign();         print('Stage 4: all tests passed.')
def _run_stage5_tests(): print('Stage 5 - collapse:');            _test_collapse();             print('Stage 5: all tests passed.')
def _run_stage6_tests(): print('Stage 6 - anchored handles:');    _test_anchored_handles();     print('Stage 6: all tests passed.')
def _run_stage7_tests(): print('Stage 7 - alignment:');           _test_alignment();            print('Stage 7: all tests passed.')
def _run_stage8_tests(): print('Stage 8 - centroid solve:');      _test_centroid();             print('Stage 8: all tests passed.')
def _run_stage9_tests(): print('Stage 9 - warp_masters:');        _test_masters();              print('Stage 9: all tests passed.')
def _run_stage10_tests(): print('Stage 10 - utilities:');         _test_utilities();            print('Stage 10: all tests passed.')


if __name__ == '__main__':
	_run_stage1_tests(); print()
	_run_stage2_tests(); print()
	_run_stage3_tests(); print()
	_run_stage4_tests(); print()
	_run_stage5_tests(); print()
	_run_stage6_tests(); print()
	_run_stage7_tests(); print()
	_run_stage8_tests(); print()
	_run_stage9_tests(); print()
	_run_stage10_tests(); print()
	print('magic_scale: ALL STAGES PASSED')
