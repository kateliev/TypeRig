# MODULE: TypeRig / Core / Actions / Delta Panel Dispatchers
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
# Dispatchers for the Delta Machine panel. Glyph-scoped; the
# host (FL panel, FontRig browser, Glyphs plugin) builds a
# setup dict and hands it in; we drive the deltas.
#
# Setup dict shape — keep this stable across hosts:
#
#   setup = {
#       'masters': [                                   # informational
#           {'name': str, 'vstem': str, 'hstem': str,
#            'color': str}
#       ],
#       'axes': [
#           {
#               'name':   str,                          # unique
#               'inputs': [                             # >= 2 entries
#                   {'name': str, 'vstem': float, 'hstem': float,
#                    'color': str}
#               ],
#               'targets': [
#                   # any target may add 'metrics' / 'anchors': bool
#                   # (default: the option of the same name); stems and
#                   # mixed targets may add 'origin' (default: options)
#                   # stems-mode target
#                   {'mode': 'stems', 'name': str,
#                    'vstem': float, 'hstem': float,
#                    'sx': float, 'sy': float,          # percent
#                    'color': str},
#                   # mixed-mode target: target stems, width and / or
#                   # height in units ('fit' names the units axes), the
#                   # other axis in percent (Delta Machine)
#                   {'mode': 'mixed', 'name': str,
#                    'vstem': float, 'hstem': float,
#                    'fit': 'w'|'h'|'wh',
#                    'sx': float, 'sy': float,          # percent, axes not in fit
#                    'w': float, 'h': float,            # units, axes in fit
#                    'color': str},
#                   # dimensions-mode target
#                   {'mode': 'dimensions', 'name': str,
#                    'w': float, 'h': float,
#                    'origin': 'BL'|'BR'|'TL'|'TR'|'CE'|'BS',
#                    'color': str},
#               ]
#           }, ...
#       ],
#       'options': {
#           'metrics':     bool,   # process metric_array
#           'anchors':     bool,   # process anchor_array
#           'extrapolate': bool,
#           'origin':      'BS'|'BL'|'BM'|'BR'|'LM'|'CE'|'RM'|'TL'|'TM'|'TR',
#                                  # global, stems mode (BS = baseline 0, 0)
#           'italic_angle': float, # degrees (signed)
#           # italic fix: all off by default (see DELTA_OPTION_DEFAULTS)
#           'italic_tan': bool,    # exact slope tan(angle) (off: radians)
#           'keep_directions': bool, # put horizontal / vertical / slanted
#                                  # handles back after the bake
#           'keep_extremes': bool, # move upright extremes to the new
#                                  # vertical extreme (needs keep_directions)
#           'keep_tension': bool,  # curves get the inputs' Hobby tension
#                                  # back (needs keep_directions)
#           'balanced' / 'live_balanced': bool, 'extreme_tol' / 'lock_tol' /
#           'tension_scale': float, 'tension_on_rebuilt': bool
#           'selection':   bool    # live: drive only the selected nodes
#       }
#   }
#
# Returns a status dict — JS reads it via the bridge.

from __future__ import absolute_import, print_function

import json
import math
import copy

from typerig.core.objects.array import PointArray
from typerig.core.objects.delta import DeltaScale
from typerig.core.objects.layer import Layer
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.transform import TransformOrigin
from typerig.core.objects.utils import Bounds


# - Module-level state (banks). Persists across runPython calls.
_last_setup = None

# Live-drive snapshot. Stores cloned input layers (frozen at the
# moment the user enabled Live mode) plus the DeltaScale dict built
# from them. Every live tick reads from this snapshot — never from the
# host glyph — so editing the active layer doesn't feed back into the
# deltas. Cleared on live-off or when the live axis fingerprint changes.
_live_snapshot = None


# - Origin code → TransformOrigin map -----------------------------
_ORIGIN_FROM_CODE = {
	'BL': TransformOrigin.BOTTOM_LEFT,
	'BR': TransformOrigin.BOTTOM_RIGHT,
	'TL': TransformOrigin.TOP_LEFT,
	'TR': TransformOrigin.TOP_RIGHT,
	'CE': TransformOrigin.CENTER,
	'BS': TransformOrigin.BASELINE,
	'BM': TransformOrigin.BOTTOM_MIDDLE,
	'TM': TransformOrigin.TOP_MIDDLE,
	'LM': TransformOrigin.CENTER_LEFT,
	'RM': TransformOrigin.CENTER_RIGHT,
}


# - Helpers -------------------------------------------------------
def _attr_len(layer, attrib):
	value = getattr(layer, attrib, None)
	if value is None: return 0
	try:
		return len(value)
	except TypeError:
		return 0


def _viable_attribs(layers, requested):
	'''Filter requested attribs to those DeltaScale can actually consume
	across all input layers. Skips attribs where any layer has zero
	entries (the IndexError trigger inside DeltaScale.__init__) or where
	layers disagree on count (the AssertionError trigger).
	'''
	viable = []
	skipped = []
	for attrib in requested:
		lengths = [_attr_len(l, attrib) for l in layers]
		if lengths and max(lengths) == 0:
			continue		# nothing to process (e.g. a glyph without anchors): not a problem
		if not lengths or min(lengths) == 0:
			skipped.append('%s: empty on at least one input' % attrib)
			continue
		if max(lengths) != min(lengths):
			skipped.append('%s: count mismatch %s' % (attrib, lengths))
			continue
		viable.append(attrib)
	return viable, skipped


def _origin_of(opts):
	return _ORIGIN_FROM_CODE.get(opts.get('origin', 'BS'),
	                             TransformOrigin.BASELINE)


def _clone_layer_geometry(src_layer, new_name):
	'''Deep-copy a layer's shapes / anchors / metrics so we can mutate
	it without touching the source. Mirrors trGlyph.duplicateLayer
	semantics: a fresh layer ready to receive new geometry.
	'''
	new_layer = src_layer.clone()
	new_layer.name = new_name
	return new_layer


def _ensure_target_layer(glyph, base_layer, target_name):
	'''Return (layer, rebuilt) for target_name. If it doesn't exist on
	the glyph, clone base_layer (so the new layer inherits metrics, anchor
	shape, etc.) and append it. Mirrors host_duplicate_layer from the
	FL panel. An existing layer whose outline is not compatible with
	base_layer (node count) is replaced in place by a clone — the FL
	panel's mount overwrites the whole layer too. rebuilt is True when
	the layer was created or replaced.
	'''
	existing = glyph.layer(target_name)
	if existing is not None and existing is not base_layer:
		if _attr_len(existing, 'point_array') == _attr_len(base_layer, 'point_array'):
			return existing, False
		new_layer = _clone_layer_geometry(base_layer, target_name)
		idx = next(i for i, l in enumerate(glyph.layers) if l is existing)
		glyph.pop(idx)
		glyph.insert(idx, new_layer)
		return new_layer, True
	if existing is not None:
		return existing, False
	new_layer = _clone_layer_geometry(base_layer, target_name)
	glyph.layers.append(new_layer)
	return new_layer, True


def _apply_array(layer, attrib, data):
	if attrib == 'point_array':
		layer.point_array = PointArray(data)
	else:
		setattr(layer, attrib, data)


def _italic_slope(opts):
	'''Engine slope (dx per dy) for options.italic_angle (degrees, core sign).
	adaptive_scale de-slants with x - y*i. Default (italic_tan off): the
	angle in radians is used as the slope, as Delta always did (12 deg ->
	11.83 deg effective). italic_tan: the exact slope tan(angle).'''
	angle = math.radians(-float(opts.get('italic_angle', 0.0) or 0.0))
	return math.tan(angle) if opts.get('italic_tan', DELTA_OPTION_DEFAULTS['italic_tan']) else angle


# - Italic fix: direction lock, re-extremize, tension ------------
# In italic mode adaptive_scale de-slants, scales X and Y apart, then
# re-slants. Horizontal and on-slant handles survive an anisotropic
# scale; true vertical handles lean by ~ angle * (1 - sx/sy), and the
# point where the curve is really vertical slides along the curve
# (narrow counters most). After the bake, on the baked core layer and
# before host rounding:
#   1. re-extremize: a smooth node whose handles are vertical in ALL
#      inputs moves along the baked curve to its new vertical extreme
#      (exact; the leftover merges into the neighbour segment). When
#      that merge misses by more than EXTREME_FIT_TOLERANCE, bakes look
#      for a balanced position between the old node and the extreme
#      where both segments fit (Live: plain lock);
#   2. lock: other labelled handles go back to H / V / slant;
#   3. tension: each curve gets the Hobby tension of the inputs back
#      (interpolated at the target stem; TENSION_ON_REBUILT: also the
#      curves re-extremize rebuilt).
# Only coordinates move: node count, order and types never change.
# Built on core Contour.node_segments, CubicBezier (solve_parallel,
# solve_slice, solve_hobby), hobbyspline.recover_tension and the
# outline cleanup fitters (fit_one, Levien fit_run).
# See TypeRig-Glyphs Handouts/delta_italic_handles_handout.md.
# Defaults of the tunable options (setup options lock_tol / extreme_tol /
# tension_scale / tension_on_rebuilt; see DELTA_OPTION_DEFAULTS).
LOCK_TOLERANCE = 1.		# units: max off-direction drift in the inputs (lab: 1)
EXTREME_FIT_TOLERANCE = 10.	# units: max shape change when re-extremizing; else snap (lab: 10+ looks good)
EXTREME_MARGIN = 0.02		# segment time kept clear of the far node
BALANCE_SCAN = 8			# balanced search: coarse samples, then golden steps
BALANCE_REFINE = 10
TENSION_SCALE = 1.			# multiplier on the restored tension (1 = as in the inputs)
TENSION_RANGE = (.5, 2.)	# restored Hobby tension is clamped to this
TENSION_ON_REBUILT = False	# restore tension on curves re-extremize rebuilt too (lab: bad with it on)

_LOCK_H, _LOCK_V, _LOCK_S = 'h', 'v', 's'


def _contours_of(layer):
	'''[((shape index, contour index), contour)] of a core layer.'''
	return [((si, ci), contour) for si, shape in enumerate(layer.shapes)
	        for ci, contour in enumerate(shape.contours)]


def _cubic_runs(contour):
	'''Node-index quads (i0, i1, i2, i3) of the cubic segments of a core
	contour (Contour.node_segments; off-curves of type 'curve').'''
	index = dict((id(node), i) for i, node in enumerate(contour.data))
	return [tuple(index[id(n)] for n in seg) for seg in contour.node_segments
	        if len(seg) == 4 and not seg[1].is_on and seg[1].type == 'curve']


def _direction_of(node, handle, slope, tol):
	dx, dy = handle[0] - node[0], handle[1] - node[1]
	if abs(dx) <= tol and abs(dy) <= tol:
		return None							# retracted handle
	if abs(dy) <= tol:
		return _LOCK_H
	if abs(dx) <= tol:
		return _LOCK_V
	if abs(dx - dy * slope) <= tol:
		return _LOCK_S
	return None


def _tension_of(pts):
	'''Hobby tension (alpha, beta) of a cubic (4 (x, y) points) by core
	recover_tension, or None for a straight segment or a retracted handle.'''
	from typerig.core.objects.hobbyspline import recover_tension, is_line_segment
	z = [complex(p[0], p[1]) for p in pts]
	if abs(z[1] - z[0]) < 1e-6 or abs(z[3] - z[2]) < 1e-6 or is_line_segment(*z):
		return None
	return recover_tension(*z)


def direction_labels(input_layers, slope, tol=LOCK_TOLERANCE):
	'''Italic fix plan for an axis, from its compatible input layers (stems
	set). Nodes are addressed (shape, contour, node) by index, the same in
	every compatible layer. Keys:
	  'shape':    [((si, ci), node count)] of the first input;
	  'segments': [(key0, key1, key2, key3)] cubic segments;
	  'pairs':    [(off key, on key, label)] handles with one direction
	              ('h' / 'v' / 's') in every input;
	  'handles':  {on key: [off keys]};  'smooth': {on key: bool};
	  'extremes': [(on key, segment in, segment out)] smooth nodes with both
	              handles vertical and a cubic on each side;
	  'tension':  {segment: [(alpha, beta) per input]};
	  'stems':    [vstem per input] ([] when not set).
	Returns None for an upright design (slope 0) or incompatible inputs.'''
	if not slope or len(input_layers) < 2:
		return None
	shapes = [_contours_of(layer) for layer in input_layers]
	shape = [(key, len(c.data)) for key, c in shapes[0]]
	if any([(key, len(c.data)) for key, c in other] != shape for other in shapes[1:]):
		return None

	segments, handles, smooth = [], {}, {}
	for (si, ci), contour in shapes[0]:
		for i0, i1, i2, i3 in _cubic_runs(contour):
			keys = tuple((si, ci, i) for i in (i0, i1, i2, i3))
			segments.append(keys)
			handles.setdefault(keys[0], []).append(keys[1])
			handles.setdefault(keys[3], []).append(keys[2])
		for i, node in enumerate(contour.data):
			if node.is_on:
				smooth[(si, ci, i)] = bool(getattr(node, 'smooth', False))

	def xy(layer, key):
		node = layer.shapes[key[0]].contours[key[1]].data[key[2]]
		return (node.x, node.y)

	pairs = []
	for on, offs in handles.items():
		for off in offs:
			labels = set(_direction_of(xy(l, on), xy(l, off), slope, tol) for l in input_layers)
			if len(labels) == 1 and None not in labels:
				pairs.append((off, on, labels.pop()))

	vertical = {}
	for off, on, label in pairs:
		if label == _LOCK_V:
			vertical.setdefault(on, []).append(off)
	seg_in = dict((seg[3], k) for k, seg in enumerate(segments))
	seg_out = dict((seg[0], k) for k, seg in enumerate(segments))
	extremes = [(on, seg_in[on], seg_out[on]) for on, offs in sorted(vertical.items())
	            if len(offs) == 2 and smooth.get(on) and on in seg_in and on in seg_out
	            and seg_in[on] != seg_out[on]]

	tension = {}
	for k, seg in enumerate(segments):
		values = [_tension_of([xy(l, key) for key in seg]) for l in input_layers]
		if None not in values:
			tension[k] = values

	stems = []
	for layer in input_layers:
		try:
			stems.append(float(layer.stems[0]))
		except (AttributeError, TypeError, ValueError, IndexError):
			stems = []						# no stems: tension is not restored
			break

	return {'shape': shape, 'segments': segments, 'pairs': pairs, 'handles': handles,
	        'smooth': smooth, 'extremes': extremes, 'tension': tension, 'stems': stems}


def _axis_time(stems, value):
	'''Position of value on the input stems (0 = first input, 1 = second, ...),
	piecewise linear, extrapolated past the ends. None if stems are flat.'''
	n = len(stems)
	for i in range(n - 1):
		lo, hi = stems[i], stems[i + 1]
		if hi == lo: continue
		if min(lo, hi) <= value <= max(lo, hi) or (i == 0 and (value - lo) * (hi - lo) < 0) or i == n - 2:
			return i + (value - lo) / (hi - lo)
	return None


def _target_tension(plan, k, vstem):
	'''Inputs' Hobby tension of segment k at vstem (interpolated, clamped to
	TENSION_RANGE), or None (not measured / no stems).'''
	values = plan['tension'].get(k)
	if values is None or len(plan['stems']) < 2 or vstem is None:
		return None
	t = _axis_time(plan['stems'], vstem)
	if t is None:
		return None
	i = min(max(int(math.floor(t)), 0), len(values) - 2)
	f = t - i
	lo, hi = TENSION_RANGE
	scale = plan.get('tension_scale', TENSION_SCALE)
	return tuple(min(max((values[i][j] + (values[i + 1][j] - values[i][j]) * f) * scale, lo), hi)
	             for j in (0, 1))


class _FitOptions(object):
	'''Options for core outline_cleanup_simplify.fit_one.'''
	def __init__(self, tol):
		self.fit_tol, self.eps_point, self.eps_handle = tol, .5, .5


def _merge_fit(run, tol):
	'''One cubic for a run of cubics with the run's end tangents (core
	fit_one: Levien area / moment fit, then Schneider). Returns (points,
	error) or None when nothing is within tol.'''
	from typerig.core.algo.outline_cleanup_geom import Seg
	from typerig.core.algo.outline_cleanup_simplify import fit_one
	fit = fit_one([Seg(tuple(seg)) for seg in run], _FitOptions(tol))
	if fit is None or len(fit[0].p) != 4:
		return None
	return tuple(tuple(p) for p in fit[0].p), fit[1]


def _tangent_fit(run, tol, t_start=None, t_end=None):
	'''One cubic for a run with given end directions (core Levien fit_run).
	Returns (points, error) or None.'''
	from typerig.core.algo.outline_cleanup_geom import Seg
	from typerig.core.algo.outline_cleanup_fit_levien import fit_run
	fit = fit_run([Seg(tuple(seg)) for seg in run], tol, .5, .5, t_start, t_end)
	if fit is None or len(fit[0].p) != 4:
		return None
	return tuple(tuple(p) for p in fit[0].p), fit[1]


class _Fixer(object):
	'''The italic fix on one baked core layer (see lock_directions).'''
	def __init__(self, layer, plan, slope):
		self.plan, self.slope = plan, slope
		self.contours = dict(_contours_of(layer))

	def node(self, key):
		return self.contours[key[:2]].data[key[2]]

	def xy(self, key):
		node = self.node(key)
		return (node.x, node.y)

	def put(self, key, p):
		node = self.node(key)
		node.x, node.y = float(p[0]), float(p[1])

	def cubic(self, seg):
		from typerig.core.objects.cubicbezier import CubicBezier
		return CubicBezier(*[self.xy(key) for key in seg])

	def write(self, seg, pts):
		for key, p in zip(seg, pts):
			self.put(key, p)

	# - Re-extremize
	def extreme(self, on, k_in, k_out, tol, balanced):
		'''Move one extreme node. Returns ('exact' | 'balanced', error) or None.'''
		segs = self.plan['segments']
		A, B = self.cubic(segs[k_in]), self.cubic(segs[k_out])

		def vertical_times(seg, lo, hi):
			return [t for t in (seg.solve_parallel((0., 1.), fullOutput=True) or []) if lo <= t <= hi]

		cand = [(1. - t, 'in', t) for t in vertical_times(A, EXTREME_MARGIN, 1.)]
		cand += [(t, 'out', t) for t in vertical_times(B, 0., 1. - EXTREME_MARGIN)]
		if not cand:
			return None
		gap, side, t = min(cand)
		if gap < 1e-6:
			return 'exact', 0.					# already on the extreme

		# Exact: the piece with the extreme stays, the rest merges
		if side == 'in':
			kept, piece = A.solve_slice(t)
			fit = _merge_fit([piece.tuple, B.tuple], tol)
			result = (kept.tuple, fit[0]) if fit else None
		else:
			piece, kept = B.solve_slice(t)
			fit = _merge_fit([A.tuple, piece.tuple], tol)
			result = (fit[0], kept.tuple) if fit else None
		if result is not None:
			self.done(on, segs[k_in], segs[k_out], result)
			return 'exact', fit[1]
		if not balanced:
			return None

		# Balanced: slide part way (time u on the side that holds the extreme),
		# vertical handles, both segments fitted; minimise the worse error.
		up = (piece.p3.y - piece.p2.y) if side == 'out' else (piece.p1.y - piece.p0.y)
		vdir = (0., 1. if up >= 0. else -1.)
		bound = tol * 3.

		def trial(u):
			if side == 'out':
				lo, hi = B.solve_slice(u)
				left = _tangent_fit([A.tuple, lo.tuple], bound, t_end=vdir)
				right = _tangent_fit([hi.tuple], bound, t_start=vdir)
			else:
				lo, hi = A.solve_slice(u)
				left = _tangent_fit([lo.tuple], bound, t_end=vdir)
				right = _tangent_fit([hi.tuple, B.tuple], bound, t_start=vdir)
			if left is None or right is None:
				return float('inf'), None
			return max(left[1], right[1]), (left[0], right[0])

		a, b = (0., t) if side == 'out' else (t, 1.)
		a, b = a + (b - a) * .02, b - (b - a) * .02	# keep clear of both ends
		samples = [a + (b - a) * k / float(BALANCE_SCAN - 1) for k in range(BALANCE_SCAN)]
		scored = [(trial(u), u) for u in samples]
		best_i = min(range(len(scored)), key=lambda k: scored[k][0][0])
		lo_u = samples[max(best_i - 1, 0)]
		hi_u = samples[min(best_i + 1, len(samples) - 1)]
		best, best_u = scored[best_i]
		g = (math.sqrt(5.) - 1.) / 2.			# golden section on the bracket
		x1, x2 = hi_u - g * (hi_u - lo_u), lo_u + g * (hi_u - lo_u)
		f1, f2 = trial(x1), trial(x2)
		for _ in range(BALANCE_REFINE):
			for f, x in ((f1, x1), (f2, x2)):
				if f[0] < best[0]:
					best, best_u = f, x
			if f1[0] <= f2[0]:
				hi_u, x2, f2 = x2, x1, f1
				x1 = hi_u - g * (hi_u - lo_u)
				f1 = trial(x1)
			else:
				lo_u, x1, f1 = x1, x2, f2
				x2 = lo_u + g * (hi_u - lo_u)
				f2 = trial(x2)
		if best[1] is None or best[0] > tol:
			return None
		self.done(on, segs[k_in], segs[k_out], best[1])
		return 'balanced', best[0]

	def done(self, on, seg_in, seg_out, result):
		new_a, new_b = result
		self.write(seg_in, new_a)
		self.write(seg_out, new_b)
		x = self.node(on).x						# exact vertical
		for key in (seg_in[2], seg_out[1]):
			self.put(key, (x, self.node(key).y))

	# - Lock
	def lock(self, skip):
		'''Labelled handles back on their direction; smooth partners in line.
		Returns (moved, max drift).'''
		moved, drift, locked_by_on = 0, 0., {}
		for off, on, label in self.plan['pairs']:
			if on in skip:
				continue
			nx, ny = self.xy(on)
			hx, hy = self.xy(off)
			if label == _LOCK_V:
				new = (nx, hy)
			elif label == _LOCK_S:
				new = (nx + (hy - ny) * self.slope, hy)
			else:
				new = (hx, ny)
			d = math.hypot(new[0] - hx, new[1] - hy)
			if d > 1e-9:
				moved += 1
				drift = max(drift, d)
			self.put(off, new)
			locked_by_on.setdefault(on, []).append(off)

		for on, offs in locked_by_on.items():
			if len(offs) != 1 or not self.plan['smooth'].get(on):
				continue
			others = [o for o in self.plan['handles'].get(on, []) if o not in offs]
			if len(others) != 1:
				continue
			nx, ny = self.xy(on)
			lx, ly = self.xy(offs[0])[0] - nx, self.xy(offs[0])[1] - ny
			ox, oy = self.xy(others[0])
			ll, ol = math.hypot(lx, ly), math.hypot(ox - nx, oy - ny)
			if ll < 1e-9 or ol < 1e-9:
				continue
			new = (nx - lx / ll * ol, ny - ly / ll * ol)
			d = math.hypot(new[0] - ox, new[1] - oy)
			if d > 1e-9:
				moved += 1
				drift = max(drift, d)
			self.put(others[0], new)
		return moved, drift

	# - Tension
	def tension(self, vstem, skip_segments):
		'''Inputs' Hobby tension back on every measured cubic not in
		skip_segments (core CubicBezier.solve_hobby keeps handle directions).'''
		changed = 0
		for k in self.plan['tension']:
			if k in skip_segments:
				continue
			tension = _target_tension(self.plan, k, vstem)
			if tension is None:
				continue
			seg = self.plan['segments'][k]
			cubic = self.cubic(seg)
			if _tension_of(cubic.tuple) is None:
				continue						# baked curve straight / retracted: leave it
			try:
				new = cubic.solve_hobby(tension).tuple
			except (ZeroDivisionError, ValueError, OverflowError):
				continue
			if not all(math.isfinite(v) for p in new for v in p):
				continue
			self.put(seg[1], new[1])
			self.put(seg[2], new[2])
			changed += 1
		return changed


def lock_directions(layer, plan, slope, vstem=None):
	'''Italic fix on a baked core layer (changed in place), switched by the
	plan (_italic_plan): re-extremize ('keep_extremes'; 'balanced': search a
	balanced position when the exact move misses 'fit_tol'), lock the
	labelled handles, restore tension ('keep_tension', needs vstem;
	'tension_on_rebuilt', 'tension_scale'). Vertical lock: x = node x (Y kept); slant: back on the
	slant line through the node (Y kept); horizontal: y = node y. A smooth
	node with one locked handle turns its other handle in line (length
	kept). Returns a report {'locked', 'drift', 'extremes', 'balanced',
	'fit_error', 'fallbacks', 'tension'}.'''
	report = {'locked': 0, 'drift': 0., 'extremes': 0, 'balanced': 0,
	          'fit_error': 0., 'fallbacks': 0, 'tension': 0}
	if not plan:
		return report
	if [(key, len(c.data)) for key, c in _contours_of(layer)] != plan['shape']:
		return report							# not the layout the plan was built on

	fixer = _Fixer(layer, plan, slope)
	done, rebuilt = set(), set()
	if plan.get('keep_extremes'):
		for on, k_in, k_out in plan['extremes']:
			res = fixer.extreme(on, k_in, k_out, plan.get('fit_tol', EXTREME_FIT_TOLERANCE),
			                    plan.get('balanced', False))
			if res is None:
				report['fallbacks'] += 1
				continue
			kind, error = res
			done.add(on)
			if error > 0.:
				rebuilt.update((k_in, k_out))
				report['extremes' if kind == 'exact' else 'balanced'] += 1
				report['fit_error'] = max(report['fit_error'], error)

	report['locked'], report['drift'] = fixer.lock(done)
	if plan.get('keep_tension') and vstem is not None and plan.get('tension'):
		on_rebuilt = plan.get('tension_on_rebuilt', TENSION_ON_REBUILT)
		report['tension'] = fixer.tension(vstem, set() if on_rebuilt else rebuilt)
	return report


def _italic_plan(input_layers, slope, opts, live=False):
	'''direction_labels plan with the option switches and knobs, or None when
	the italic fix is off (keep_directions) or not needed. live: the
	balanced search follows 'live_balanced' instead of 'balanced'.'''
	opt = lambda key: opts.get(key, DELTA_OPTION_DEFAULTS[key])	# defaults: one place for every host
	if not opt('keep_directions'):
		return None
	plan = direction_labels(input_layers, slope, float(opt('lock_tol')))
	if plan is not None:
		plan.update(keep_extremes=bool(opt('keep_extremes')), keep_tension=bool(opt('keep_tension')),
		            balanced=bool(opt('live_balanced' if live else 'balanced')),
		            fit_tol=float(opt('extreme_tol')), tension_scale=float(opt('tension_scale')),
		            tension_on_rebuilt=bool(opt('tension_on_rebuilt')))
	return plan


def _bake_target_stems(base_layer, vaxis, target, italic_rad,
                       extrapolate, global_origin, source_bounds, lock=None, report=None):
	'''Stems-mode: drive DeltaScale.scale_by_stem for every viable
	attribute, write into a clone of base_layer, realign to chosen
	origin (skip when origin is BASELINE — that's scale_by_stem's native
	reference). lock: an _italic_plan; when given, the italic fix runs on
	the baked layer (lock_directions, switched by the plan's
	'keep_extremes' / 'keep_tension' / 'balanced'). report: optional dict,
	gets the summed lock_directions report.
	'''
	new_layer = base_layer.clone()

	stem = (float(target['vstem']), float(target['hstem']))
	scale = (float(target.get('sx', 100.0)) / 100.0,
	         float(target.get('sy', 100.0)) / 100.0)

	for attrib, delta_scale in vaxis.items():
		try:
			result = list(delta_scale.scale_by_stem(
				stem, scale, (0., 0.), (0., 0.),
				italic_rad, extrapolate,
			))
		except (IndexError, ValueError, AssertionError):
			continue
		_apply_array(new_layer, attrib, result)
		if attrib == 'point_array' and lock:
			fix = lock_directions(new_layer, lock, italic_rad, stem[0])
			if report is not None:
				for key, value in fix.items():
					worst = key in ('drift', 'fit_error')
					report[key] = max(report.get(key, 0.), value) if worst else report.get(key, 0) + value

	if global_origin is not None and global_origin != TransformOrigin.BASELINE:
		try:
			sx0, sy0 = source_bounds.align_matrix[global_origin.code]
			dest_bounds = new_layer.bounds
			dx0, dy0 = dest_bounds.align_matrix[global_origin.code]
			new_layer.shift(sx0 - dx0, sy0 - dy0)
		except Exception:
			pass

	return new_layer


def _measure_box(delta, stem, scale, italic_rad, extrapolate):
	'''(width, height) of the point box that delta gives for stem / scale.'''
	pts = list(delta.scale_by_stem(stem, scale, (0., 0.), (0., 0.), italic_rad, extrapolate))
	if not pts:
		return 0., 0.
	xs = [p[0] for p in pts]
	ys = [p[1] for p in pts]
	return max(xs) - min(xs), max(ys) - min(ys)


def _solve_scale(delta, stem, scale, dims, italic_rad, extrapolate, tol=0.01, steps=16):
	'''Scale factors (sx, sy) that make the point box of delta hit dims.

	scale: (sx, sy) start; an axis whose dims entry is None keeps its value
	(fixed percent). dims: (width | None, height | None) in units.
	With compensation 0 the box is affine in each scale, so a secant on the
	measured box converges in one or two steps; the fixed axis is held at
	its own value while solving, so an italic shear (x depends on y) is
	part of the measure. Returns ((sx, sy), converged, (res_w, res_h)).
	'''
	s = [float(scale[0]), float(scale[1])]
	solve = [i for i in (0, 1) if dims[i] is not None]
	prev_s = prev_m = None
	m = _measure_box(delta, stem, tuple(s), italic_rad, extrapolate)
	for _ in range(steps):
		if all(abs(m[i] - dims[i]) <= tol for i in solve):
			break
		new = list(s)
		for i in solve:
			slope = None
			if prev_s is not None and s[i] != prev_s[i]:
				slope = (m[i] - prev_m[i]) / (s[i] - prev_s[i])
			if slope:
				new[i] = s[i] - (m[i] - dims[i]) / slope
			elif m[i]:
				new[i] = s[i] * dims[i] / m[i]		# proportional seed
		prev_s, prev_m, s = s, m, new
		m = _measure_box(delta, stem, tuple(s), italic_rad, extrapolate)
	res = tuple(abs(m[i] - dims[i]) if dims[i] is not None else 0. for i in (0, 1))
	return (s[0], s[1]), all(r <= max(tol, 0.5) for r in res), res


def _mixed_scale(vaxis, target, italic_rad, extrapolate):
	'''Mixed-mode scales in percent: the % axes as given, the units axes
	(target['fit'] in 'w', 'h', 'wh') solved on the point_array box.
	Returns ((sx %, sy %), converged, residual).'''
	fit = target.get('fit', '') or ''
	stem = (float(target['vstem']), float(target['hstem']))
	scale = (float(target.get('sx', 100.)) / 100. if 'w' not in fit else 1.,
	         float(target.get('sy', 100.)) / 100. if 'h' not in fit else 1.)
	dims = (float(target['w']) if 'w' in fit else None,
	        float(target['h']) if 'h' in fit else None)
	if dims == (None, None):
		return (scale[0] * 100., scale[1] * 100.), True, (0., 0.)
	(sx, sy), ok, res = _solve_scale(vaxis['point_array'], stem, scale, dims, italic_rad, extrapolate)
	return (sx * 100., sy * 100.), ok, res


def _bake_target_mixed(base_layer, vaxis, target, italic_rad,
                       extrapolate, global_origin, source_bounds, lock=None, report=None):
	'''Mixed-mode: target stems (like stems mode) with width and / or
	height in units. The units axes are solved first, then the target is
	baked as stems mode with the solved percentages. Unlike dimensions
	mode, the target stems are used. Returns (layer, converged, scales).'''
	scales, ok, _res = _mixed_scale(vaxis, target, italic_rad, extrapolate)
	as_stems = dict(target, sx=scales[0], sy=scales[1])
	layer = _bake_target_stems(base_layer, vaxis, as_stems, italic_rad,
	                           extrapolate, global_origin, source_bounds, lock, report)
	return layer, ok, scales


def _bake_target_dims(base_layer, vaxis, target, extrapolate):
	'''Dimensions-mode: delegate to core's iterative scale_with_axis.'''
	origin = _ORIGIN_FROM_CODE.get(target.get('origin', 'BL'),
	                               TransformOrigin.BOTTOM_LEFT)
	return base_layer.scale_with_axis(
		vaxis,
		target_width=float(target['w']),
		target_height=float(target['h']),
		transform_origin=origin,
		extrapolate=extrapolate,
	)


# - Setup normalisation (shared by all hosts) ---------------------
# Hosts store setups in different shapes:
#   core / FontRig  — the setup dict documented at the top of this module
#                     (+ 'liveAxis': {'name': 'Live', 'inputs': [...]});
#   FL DeltaNew     — tree dict: rows are lists [name, vstem, hstem, sx,
#                     sy, color]; key 'live_axis'; targets are dicts of
#                     strings;
#   FL legacy Delta — {'Master Layers': rows, 'Virtual Axis': rows,
#                     'Target Layers': rows}.
# delta_setup_normalize() reads any of them and returns the core shape,
# so a setup saved by one host loads in every other.
DELTA_OPTION_DEFAULTS = {
	'metrics': True, 'anchors': True, 'extrapolate': True,
	'origin': 'BS', 'italic_angle': 0., 'selection': False,
	# Italic fix (TypeRig-Glyphs Handouts/delta_italic_handles_handout.md):
	# all off by default (2026-10-19, user): Delta bakes as it always did.
	# The Delta Italic Lab switches them for trials.
	'italic_tan': False,			# exact slope tan(angle); off = radians as slope (original)
	'keep_directions': False,		# lock H / V / slant handles (master switch of the fix)
	'keep_extremes': False,			# move upright extremes to the new vertical extreme
	'keep_tension': False,			# inputs' Hobby tension back on every curve
	'balanced': True,				# bakes: balanced extreme search when the exact move misses
	'live_balanced': False,			# Live: the same (slower per tick)
	'extreme_tol': EXTREME_FIT_TOLERANCE,	# units
	'lock_tol': LOCK_TOLERANCE,		# units
	'tension_scale': TENSION_SCALE,
	'tension_on_rebuilt': TENSION_ON_REBUILT,
}

# Italic fix fields for the hosts' option forms (Delta Machine Advanced,
# Delta Italic Lab): (option key, title, tooltip). Order = form order.
ITALIC_FIX_SWITCHES = (
	('italic_tan', 'Exact slope (tan)',
	 'Use tan(angle) as the de-slant slope. Off: the angle in radians, as Delta always did.'),
	('keep_directions', 'Lock directions',
	 'Put handles that are horizontal / vertical / on the slant in every input back on that direction.\n'
	 'Master switch: the other switches need it.'),
	('keep_extremes', 'Re-extremize',
	 'Move upright side extremes to where the scaled curve is really vertical.'),
	('balanced', 'Balanced search',
	 'When the exact move bends the curve more than the fit tolerance, stop part way so both curves fit.'),
	('keep_tension', 'Restore tension',
	 'Curves get the Hobby tension of the inputs back (interpolated at the V stem).'),
	('tension_on_rebuilt', 'Tension on moved curves',
	 'Restore tension also on the curves next to a moved extreme (lab: looks bad).'),
)
ITALIC_FIX_NUMBERS = (
	('extreme_tol', 'Fit tolerance (u)',
	 'Largest shape change a moved extreme may cause; else the node only gets its handles locked.'),
	('lock_tol', 'Lock tolerance (u)',
	 'How far off a direction an input handle may be and still count as on it.'),
	('tension_scale', 'Tension scale', 'Multiplier on the restored tension (1 = as in the inputs).'),
)
ITALIC_FIX_KEYS = tuple(k for k, _t, _h in ITALIC_FIX_SWITCHES + ITALIC_FIX_NUMBERS)


def _to_float(value, default=None):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _row_field(row, key, index, default=''):
	'''Read a field from a tree row (list) or a core row (dict).'''
	if isinstance(row, dict):
		return row.get(key, default)
	if isinstance(row, (list, tuple)) and len(row) > index:
		return row[index]
	return default


def _norm_input(row):
	'''Axis / Live Axis input row → {'name', 'vstem', 'hstem', 'color'}.
	Stems that do not parse stay as given (validate reports them).'''
	vstem = _row_field(row, 'vstem', 1)
	hstem = _row_field(row, 'hstem', 2)
	return {
		'name':  str(_row_field(row, 'name', 0) or ''),
		'vstem': _to_float(vstem, vstem),
		'hstem': _to_float(hstem, hstem),
		'color': _row_field(row, 'color', 5) or '',
	}


def _norm_target(t):
	mode = t.get('mode')
	mode = 'dimensions' if mode in ('dimensions', 'dims') else 'mixed' if mode == 'mixed' else 'stems'
	out = {'mode': mode, 'name': str(t.get('name', '') or ''), 'color': t.get('color', '') or ''}
	for key in ('anchors', 'metrics'):		# per-target switches (Delta Machine)
		if isinstance(t.get(key), bool):
			out[key] = t[key]
	if mode != 'dimensions' and t.get('origin') in _ORIGIN_FROM_CODE:
		out['origin'] = t['origin']		# per-target transform origin (Delta Machine)
	if mode in ('stems', 'mixed'):
		out.update(vstem=_to_float(t.get('vstem'), 100.), hstem=_to_float(t.get('hstem'), 100.),
		           sx=_to_float(t.get('sx'), 100.), sy=_to_float(t.get('sy'), 100.))
		if mode == 'mixed':
			fit = ''.join(c for c in 'wh' if c in str(t.get('fit', '') or ''))
			out.update(fit=fit, w=_to_float(t.get('w'), 600.), h=_to_float(t.get('h'), 700.))
	else:
		origin = t.get('origin', 'BL')
		out.update(w=_to_float(t.get('w'), 600.), h=_to_float(t.get('h'), 700.),
		           origin=origin if origin in _ORIGIN_FROM_CODE else 'BL')
	# Keep the other mode's numbers when a host stores both (Glyphs toggles
	# a row between stems and units without losing them); bake ignores them.
	for key in ('vstem', 'hstem', 'sx', 'sy', 'w', 'h'):
		if key not in out and _to_float(t.get(key)) is not None:
			out[key] = float(t[key])
	return out


def _legacy_to_tree(d):
	'''FL legacy Delta save → FL DeltaNew tree dict (FL _migrate_legacy).'''
	axis = {'name': 'Virtual Axis', 'inputs': [], 'targets': []}
	for r in d.get('Virtual Axis', []):
		axis['inputs'].append([r[0], r[1], r[2], '', '', ''])
	for r in d.get('Target Layers', []):
		axis['targets'].append({'mode': 'stems', 'name': r[0], 'vstem': r[1], 'hstem': r[2],
		                        'sx': r[3], 'sy': r[4], 'color': r[5] if len(r) > 5 else ''})
	masters = [[r[0], r[1], r[2], '', '', r[5] if len(r) > 5 else ''] for r in d.get('Master Layers', [])]
	return {'masters': masters, 'live_axis': {'inputs': []}, 'axes': [axis]}


def delta_setup_normalize(raw):
	'''Any known Delta setup shape (dict or JSON string) → core setup dict
	{'masters', 'liveAxis', 'axes', 'options'}. Unknown keys are dropped;
	missing parts get empty / default values. Raises ValueError when raw
	is not a dict or a JSON string of one.
	'''
	if isinstance(raw, (str, bytes)):
		raw = json.loads(raw)
	if not isinstance(raw, dict):
		raise ValueError('Delta setup must be a dict')

	if 'Virtual Axis' in raw and 'Master Layers' in raw:
		raw = _legacy_to_tree(raw)

	masters = []
	for row in raw.get('masters', []) or []:
		name = _row_field(row, 'name', 0)
		if name in (None, '', 'Master Layers'):
			continue
		masters.append({'name': str(name),
		                'vstem': _row_field(row, 'vstem', 1), 'hstem': _row_field(row, 'hstem', 2),
		                'color': _row_field(row, 'color', 5) or ''})

	live = raw.get('liveAxis', raw.get('live_axis')) or {}
	live_inputs = [_norm_input(r) for r in (live.get('inputs', []) if isinstance(live, dict) else [])]
	live_inputs = [r for r in live_inputs if r['name']]

	axes = []
	for ax in raw.get('axes', []) or []:
		if not isinstance(ax, dict):
			continue
		inputs = [_norm_input(r) for r in ax.get('inputs', []) or []]
		axes.append({
			'name':    str(ax.get('name', '') or '').strip(),
			'inputs':  [r for r in inputs if r['name']],
			'targets': [_norm_target(t) for t in ax.get('targets', []) or [] if isinstance(t, dict)],
		})

	options = dict(DELTA_OPTION_DEFAULTS)
	options.update({k: v for k, v in (raw.get('options') or {}).items() if k in DELTA_OPTION_DEFAULTS})

	return {'masters': masters, 'liveAxis': {'name': 'Live', 'inputs': live_inputs},
	        'axes': axes, 'options': options}


def delta_setup_validate(setup):
	'''Check a core setup dict before a bake (FL DeltaNew tree rules).
	Returns a list of error strings; empty when the setup can bake.'''
	errors = []
	axis_names = set()
	for ax in setup.get('axes', []):
		name = ax.get('name', '').strip()
		if not name:
			errors.append('Axis has no name.')
			continue
		if name in axis_names:
			errors.append('Duplicate axis name: %s' % name)
			continue
		axis_names.add(name)

		good = 0
		for inp in ax.get('inputs', []):
			if _to_float(inp.get('vstem')) is None or _to_float(inp.get('hstem')) is None:
				errors.append('Axis "%s": input "%s" has invalid stems.' % (name, inp.get('name')))
			else:
				good += 1
		if good < 2:
			errors.append('Axis "%s" needs at least 2 inputs.' % name)

		target_names = set()
		for t in ax.get('targets', []):
			t_name = t.get('name', '').strip()
			if not t_name:
				errors.append('Axis "%s": target without a name.' % name)
			elif t_name in target_names:
				errors.append('Axis "%s": duplicate target "%s".' % (name, t_name))
			target_names.add(t_name)
	return errors


# - Dispatchers ---------------------------------------------------
def _build_axis(glyph, axis, requested, warnings):
	'''Resolve an axis' input layers (stems set) and build its virtual axis.
	Returns (vaxis, base_layer, viable, input_layers) or None (warnings say why).'''
	axis_name = axis.get('name', '<unnamed>')
	inputs = axis.get('inputs', [])
	if len(inputs) < 2:
		warnings.append('Axis "%s": needs at least 2 inputs.' % axis_name)
		return None

	# Resolve input layers + set stems. Skip empties.
	input_layers = []
	empty = []
	missing = []
	for inp in inputs:
		name = inp.get('name')
		layer = glyph.layer(name)
		if layer is None:
			missing.append(name)
			continue
		if _attr_len(layer, 'point_array') == 0:
			empty.append(name)
			continue
		try:
			layer.stems = (float(inp['vstem']), float(inp['hstem']))
		except (KeyError, ValueError, TypeError):
			warnings.append('Axis "%s": input "%s" has invalid stems.'
				% (axis_name, name))
			continue
		input_layers.append(layer)

	if missing:
		warnings.append('Axis "%s": missing layers %s.'
			% (axis_name, ', '.join(missing)))
	if empty:
		warnings.append('Axis "%s": empty input layers %s.'
			% (axis_name, ', '.join(empty)))
	if len(input_layers) < 2:
		warnings.append('Axis "%s": fewer than 2 usable inputs.'
			% axis_name)
		return None

	# Decide attribs viable across all surviving inputs.
	viable, skipped = _viable_attribs(input_layers, requested)
	for s in skipped:
		warnings.append('Axis "%s": %s — skipped.' % (axis_name, s))
	if 'point_array' not in viable:
		warnings.append('Axis "%s": no usable point_array.' % axis_name)
		return None

	# Build the virtual axis once.
	try:
		vaxis = glyph.create_virtual_axis(
			[l.name for l in input_layers], attributes=viable)
	except Exception as e:
		warnings.append('Axis "%s": create_virtual_axis failed: %s'
			% (axis_name, e))
		return None
	return vaxis, input_layers[0], viable, input_layers


def _requested_attribs(opts, axes):
	'''Attributes to build: point_array, plus metrics / anchors when the
	options or any target ask for them (targets may switch them per row).'''
	targets = [t for ax in axes for t in ax.get('targets', [])]
	requested = ['point_array']
	for attrib, key in (('metric_array', 'metrics'), ('anchor_array', 'anchors')):
		default = opts.get(key, True)
		if any(t.get(key, default) for t in targets) or (default and not targets):
			requested.append(attrib)
	return requested


def npa_delta_bake(glyph, scope_layers, NodeActions, setup_json):
	'''Bake all targets across all axes in the supplied setup against
	the active glyph. Returns a JSON-serialisable status dict.

	scope_layers is ignored — Delta operates over the layers named in
	the setup, not over the layer-mode scope. The host is expected to
	keep glyph current.

	A target may carry its own 'metrics' / 'anchors' (bool, default: the
	option); when off, that attribute is left out of the entry's 'viable'
	and the target layer keeps its own metrics / anchors.
	'''
	global _last_setup

	try:
		setup = json.loads(setup_json)
	except (TypeError, ValueError) as e:
		return {'ok': False, 'error': 'setup_json parse failed: %s' % e}

	_last_setup = setup

	axes = setup.get('axes', [])
	if not axes:
		return {'ok': False, 'error': 'No axes defined.'}

	opts = setup.get('options', {}) or {}
	italic_rad = _italic_slope(opts)		# the engine's slope argument (see _italic_slope)
	extrapolate = bool(opts.get('extrapolate', True))
	global_origin = _origin_of(opts)
	requested = _requested_attribs(opts, axes)

	warnings = []
	targets_baked = 0
	axes_built = 0
	baked = []			# [{'axis', 'name', 'base', 'rebuilt', 'viable'}] — layers the host writes back

	for axis in axes:
		axis_name = axis.get('name', '<unnamed>')
		built = _build_axis(glyph, axis, requested, warnings)
		if built is None:
			continue
		vaxis, base_layer, viable, input_layers = built
		axes_built += 1
		lock = _italic_plan(input_layers, italic_rad, opts)

		base_name = base_layer.name
		try:
			source_bounds = base_layer.bounds
		except Exception:
			source_bounds = None

		for target in axis.get('targets', []):
			t_name = target.get('name')
			if not t_name:
				warnings.append('Axis "%s": skipped target with no name.'
					% axis_name)
				continue
			mode = target.get('mode', 'stems')
			entry = {}
			lock_report = {}
			# A stems / mixed target may carry its own origin (Delta Machine rows)
			origin = _ORIGIN_FROM_CODE.get(target.get('origin'), global_origin)
			try:
				if mode == 'stems':
					new_layer = _bake_target_stems(
						base_layer, vaxis, target,
						italic_rad, extrapolate,
						origin, source_bounds, lock, lock_report)
				elif mode == 'mixed':
					new_layer, converged, scales = _bake_target_mixed(
						base_layer, vaxis, target,
						italic_rad, extrapolate,
						origin, source_bounds, lock, lock_report)
					entry['scales'] = list(scales)
					if not converged:
						warnings.append('Axis "%s" / target "%s": size not reached.'
							% (axis_name, t_name))
				else:
					new_layer = _bake_target_dims(
						base_layer, vaxis, target, extrapolate)
			except Exception as e:
				warnings.append('Axis "%s" / target "%s": bake failed: %s'
					% (axis_name, t_name, e))
				continue

			t_viable = [a for a in viable
			            if not (a == 'metric_array' and not target.get('metrics', opts.get('metrics', True)))
			            and not (a == 'anchor_array' and not target.get('anchors', opts.get('anchors', True)))]

			new_layer.name = t_name
			# Ensure FL/host layer exists, then copy our scaled geometry in.
			dst, rebuilt = _ensure_target_layer(glyph, base_layer, t_name)
			dst.point_array = new_layer.point_array
			if 'metric_array' in t_viable:
				dst.metric_array = new_layer.metric_array
			if 'anchor_array' in t_viable:
				dst.anchor_array = new_layer.anchor_array
			# Origin realignment for stems mode already baked into new_layer;
			# mirror by shifting dst to match new_layer's bounds origin.
			try:
				dst_offset_x = new_layer.bounds.x - dst.bounds.x
				dst_offset_y = new_layer.bounds.y - dst.bounds.y
				if dst_offset_x or dst_offset_y:
					dst.shift(dst_offset_x, dst_offset_y)
			except Exception:
				pass

			targets_baked += 1
			for key in ('locked', 'extremes', 'balanced', 'fallbacks', 'tension'):
				if lock_report.get(key):
					entry[key] = lock_report[key]
			for key in ('drift', 'fit_error'):
				if lock_report.get(key):
					entry[key] = round(lock_report[key], 2)
			entry.update({'axis': axis_name, 'name': t_name, 'base': base_name,
			              'rebuilt': rebuilt, 'viable': t_viable})
			baked.append(entry)

	return {
		'ok': True,
		'axes_built': axes_built,
		'targets_baked': targets_baked,
		'baked': baked,
		'warnings': warnings,
	}


def npa_delta_solve_target(glyph, scope_layers, NodeActions, setup_json):
	'''Solve the scales of every mixed-mode target on this glyph without
	writing anything: the first pass of a reference-glyph bake (solve on
	H, then bake the whole group with these percentages).

	Returns {'ok', 'scales': [{'axis', 'name', 'sx', 'sy', 'converged',
	'residual'}], 'warnings'}; sx / sy in percent. Stems targets echo their
	own sx / sy; dimensions targets are skipped.
	'''
	try:
		setup = json.loads(setup_json)
	except (TypeError, ValueError) as e:
		return {'ok': False, 'error': 'setup_json parse failed: %s' % e}
	opts = setup.get('options', {}) or {}
	italic_rad = _italic_slope(opts)
	extrapolate = bool(opts.get('extrapolate', True))

	warnings, scales = [], []
	for axis in setup.get('axes', []):
		axis_name = axis.get('name', '<unnamed>')
		built = _build_axis(glyph, axis, ['point_array'], warnings)
		if built is None:
			continue
		vaxis = built[0]
		for target in axis.get('targets', []):
			mode = target.get('mode', 'stems')
			if mode == 'dimensions':
				continue
			try:
				if mode == 'mixed':
					(sx, sy), ok, res = _mixed_scale(vaxis, target, italic_rad, extrapolate)
				else:
					sx, sy = float(target.get('sx', 100.)), float(target.get('sy', 100.))
					ok, res = True, (0., 0.)
			except Exception as e:
				warnings.append('Axis "%s" / target "%s": solve failed: %s'
					% (axis_name, target.get('name'), e))
				continue
			scales.append({'axis': axis_name, 'name': target.get('name'), 'sx': sx, 'sy': sy,
			               'converged': ok, 'residual': list(res)})
	return {'ok': bool(scales), 'scales': scales, 'warnings': warnings}


def npa_delta_measure_stem(glyph, scope_layers, NodeActions, layer_name, axis):
	'''Measure |Δ| along axis ('x' or 'y') between the first and last
	selected on-curve nodes on layer_name. Returns a float or None.

	The host sets node.selected before this call (FontRig's syncToPython
	does it; the FL panel reads its own live selection differently).
	'''
	layer = glyph.layer(layer_name)
	if layer is None:
		return None

	selected = []
	for shape in layer.shapes:
		for contour in shape.contours:
			for node in contour.data:
				if getattr(node, 'selected', False):
					selected.append(node)

	if len(selected) < 2:
		return None

	if axis == 'y':
		return round(abs(selected[0].y - selected[-1].y), 2)
	return round(abs(selected[0].x - selected[-1].x), 2)


def _selected_index_pair(layer):
	'''Walk a layer and return the (shape, contour, node) indices of the
	first and last selected on-curve nodes, or None if fewer than 2 are
	selected.
	'''
	idx_list = []
	for si, shape in enumerate(layer.shapes):
		for ci, contour in enumerate(shape.contours):
			for ni, node in enumerate(contour.data):
				if getattr(node, 'selected', False):
					idx_list.append((si, ci, ni))
	if len(idx_list) < 2:
		return None
	return (idx_list[0], idx_list[-1])


def _node_at(layer, idx):
	si, ci, ni = idx
	try:
		return layer.shapes[si].contours[ci].data[ni]
	except (IndexError, AttributeError):
		return None


def npa_delta_measure_stems_all(glyph, scope_layers, NodeActions, axis):
	'''Compatibility-aware stem measurement across every layer of the
	glyph. Finds the index pair from whichever layer carries the live
	selection (host-side selection is single-layer in FontRig; in FL
	this still works because the active layer carries the selection),
	then looks up those same indices on every other layer and returns
	{layer_name: float_or_None} as a JSON string.

	The host (JS or FL) picks the values it cares about for the rows
	it has and silently skips layers where the index pair doesn't exist
	(incompatible / different topology).
	'''
	import json as _json

	# Find the layer that carries the selection. We accept any layer —
	# usually it's the active one, but if a future host mirrors the
	# selection elsewhere this still works.
	pair = None
	for lyr in glyph.layers:
		pair = _selected_index_pair(lyr)
		if pair is not None:
			break

	if pair is None:
		return _json.dumps({})

	first_idx, last_idx = pair
	result = {}
	for lyr in glyph.layers:
		n_first = _node_at(lyr, first_idx)
		n_last  = _node_at(lyr, last_idx)
		if n_first is None or n_last is None:
			result[lyr.name] = None
			continue
		try:
			if axis == 'y':
				result[lyr.name] = round(abs(n_first.y - n_last.y), 2)
			else:
				result[lyr.name] = round(abs(n_first.x - n_last.x), 2)
		except AttributeError:
			result[lyr.name] = None

	return _json.dumps(result)


def npa_delta_master_names(glyph, scope_layers, NodeActions):
	'''Convenience: return the list of layer names on the active glyph.
	Used by the host to seed the master pool.
	'''
	return [l.name for l in glyph.layers]


# =====================================================================
# Live-drive dispatchers — snapshot once, drive cheap on every tick.
# =====================================================================

def _layer_nodes(layer):
	'''All nodes of a layer in point_array order (shapes -> contours -> data).'''
	return [node for shape in layer.shapes for contour in shape.contours for node in contour.data]


def _selected_indices(layer):
	'''Flat indices (point_array order) of the selected nodes of a layer.'''
	if layer is None: return []
	return [i for i, node in enumerate(_layer_nodes(layer)) if getattr(node, 'selected', False)]


def npa_delta_live_set(glyph, scope_layers, NodeActions, setup_json, selection_layer=None):
	'''Snapshot the input layers of the Live Axis and pre-build the
	DeltaScale dict. Subsequent npa_delta_live_drive calls operate on
	this frozen snapshot — they never re-read from the host glyph, so
	driving the active layer doesn't feed back into the deltas.

	The setup_json shape matches the bake setup but is expected to
	contain exactly one axis (the Live Axis) and no real targets.

	Selection mode (options.selection and selection_layer given): the
	snapshot covers only the nodes selected on selection_layer (the
	host's active layer). Each input's point_array is sliced by those
	indices and a DeltaScale is built from the slices — filter at the
	snapshot, not at the write. Nothing selected -> whole layer.
	Geometry only: metrics and anchors are not driven in this mode.
	'''
	global _live_snapshot
	import json as _json

	try:
		setup = _json.loads(setup_json)
	except (TypeError, ValueError) as e:
		_live_snapshot = None
		return {'ok': False, 'error': 'setup_json parse failed: %s' % e}

	axes = setup.get('axes', [])
	if not axes:
		_live_snapshot = None
		return {'ok': False, 'error': 'No live axis in setup.'}

	axis = axes[0]
	inputs = axis.get('inputs', [])
	if len(inputs) < 2:
		_live_snapshot = None
		return {'ok': False, 'error': 'Live Axis needs at least 2 inputs.'}

	# Take the snapshot: clone each input layer from the host glyph,
	# set stems, and stash. clone() is deepcopy, so the snapshot is
	# fully detached from the host glyph.
	snap_layers = []
	missing = []
	empty = []
	for inp in inputs:
		name = inp.get('name')
		layer = glyph.layer(name)
		if layer is None:
			missing.append(name); continue
		if _attr_len(layer, 'point_array') == 0:
			empty.append(name); continue
		try:
			snap = layer.clone()
			snap.stems = (float(inp['vstem']), float(inp['hstem']))
		except (KeyError, ValueError, TypeError):
			continue
		snap_layers.append(snap)

	if len(snap_layers) < 2:
		_live_snapshot = None
		return {'ok': False, 'error': 'Fewer than 2 usable inputs.',
		        'missing': missing, 'empty': empty}

	# Decide viable attribs across the snapshot inputs (same filter as
	# the bake path — drops anchor_array if any layer has 0 anchors,
	# etc.).
	requested = ['point_array']
	opts = setup.get('options', {}) or {}
	if opts.get('metrics', True): requested.append('metric_array')
	if opts.get('anchors', True): requested.append('anchor_array')
	viable, skipped = _viable_attribs(snap_layers, requested)

	if 'point_array' not in viable:
		_live_snapshot = None
		return {'ok': False, 'error': 'No usable point_array on snapshot.',
		        'skipped': skipped}

	sel_indices = None
	if opts.get('selection', False) and selection_layer:
		sel_indices = _selected_indices(glyph.layer(selection_layer)) or None

	if sel_indices:
		try:
			data_array, stem_array = [], []
			for layer in snap_layers:
				points = list(layer.point_array.tuple)
				data_array.append([points[i] for i in sel_indices if i < len(points)])
				stem_array.append([layer.stems])
			vaxis = {'point_array': DeltaScale(data_array, stem_array)}
			viable = ['point_array']
		except Exception as e:
			_live_snapshot = None
			return {'ok': False, 'error': 'Selection snapshot failed: %s' % e}
	else:
		snap_glyph = Glyph(snap_layers, name=glyph.name)
		try:
			vaxis = snap_glyph.create_virtual_axis(
				[l.name for l in snap_layers], attributes=viable)
		except Exception as e:
			_live_snapshot = None
			return {'ok': False,
			        'error': 'create_virtual_axis failed: %s' % e}

	_live_snapshot = {
		'snap_layers': snap_layers,
		'vaxis': vaxis,
		'viable': viable,
		'options': opts,
		'italic_rad': _italic_slope(opts),
		'lock': _italic_plan(snap_layers, _italic_slope(opts), opts, live=True) if not sel_indices else None,
		'extrapolate': bool(opts.get('extrapolate', True)),
		'global_origin': _origin_of(opts),
		'sel_indices': sel_indices,
	}
	return {'ok': True, 'inputs': len(snap_layers),
	        'viable': viable, 'skipped': skipped,
	        'used': [l.name for l in snap_layers],
	        'selection': len(sel_indices) if sel_indices else None}


def npa_delta_live_drive(glyph, scope_layers, NodeActions,
                          target_name, vstem, hstem, sx, sy, origin=None):
	'''Drive the named layer on the live glyph from the cached snapshot.

	The snapshot was captured by the most recent npa_delta_live_set.
	Reading from the snapshot — not from the live glyph — is what
	prevents the cascade (each tick computes from the original frozen
	inputs).

	origin: optional transform-origin code for this call (see
	_ORIGIN_FROM_CODE); None keeps the snapshot's options.origin.
	Whole layer: the result's origin point lands on the same point of
	the base input's bounds. Selection mode: on the same point of the
	current selection bounds (BS: no realignment).
	'''
	global _live_snapshot
	state = _live_snapshot
	if state is None:
		return {'ok': False, 'error': 'No live snapshot — call live_set first.'}

	dst = glyph.layer(target_name)
	if dst is None:
		return {'ok': False, 'error': 'Target layer "%s" not on glyph.' % target_name}

	global_origin = state['global_origin']
	if origin is not None:
		if origin not in _ORIGIN_FROM_CODE:
			return {'ok': False, 'error': 'Unknown origin code "%s".' % origin}
		global_origin = _ORIGIN_FROM_CODE[origin]

	if state.get('sel_indices'):
		return _live_drive_selection(state, dst, global_origin,
		                             (float(vstem), float(hstem)),
		                             (float(sx) / 100.0, float(sy) / 100.0))

	base_layer = state['snap_layers'][0]
	try:
		source_bounds = base_layer.bounds
	except Exception:
		source_bounds = None

	target = {
		'mode': 'stems',
		'vstem': float(vstem), 'hstem': float(hstem),
		'sx': float(sx), 'sy': float(sy),
	}
	try:
		italic = {}
		new_layer = _bake_target_stems(
			base_layer, state['vaxis'], target,
			state['italic_rad'], state['extrapolate'],
			global_origin, source_bounds, state.get('lock'), italic)
	except Exception as e:
		return {'ok': False, 'error': 'Bake failed: %s' % e}

	# Write only the parts that the snapshot built — partial vaxis is
	# legitimate (anchor_array can be missing if inputs lacked anchors).
	viable = state['viable']
	dst.point_array = new_layer.point_array
	if 'metric_array' in viable:
		try: dst.metric_array = new_layer.metric_array
		except Exception: pass
	if 'anchor_array' in viable:
		try: dst.anchor_array = new_layer.anchor_array
		except Exception: pass

	result = {'ok': True}
	if state.get('lock'):
		result['italic'] = italic		# italic fix report (lock_directions)
	return result


def _live_drive_selection(state, dst, global_origin, stem, scale):
	'''Selection mode: scale the snapshot slice and write it in place into
	the destination nodes at the snapshot indices (node identity, and so
	the host selection, survive).'''
	sel = state['sel_indices']
	nodes = _layer_nodes(dst)
	if max(sel) >= len(nodes):
		return {'ok': False, 'error': 'Target layer is incompatible with the selection snapshot.'}

	current = [i for i, node in enumerate(nodes) if getattr(node, 'selected', False)]
	if current and current != sel:
		return {'ok': False, 'error': 'Selection changed since snapshot — re-snapshot.'}

	try:
		result = list(state['vaxis']['point_array'].scale_by_stem(
			stem, scale, (0., 0.), (0., 0.),
			state['italic_rad'], state['extrapolate']))
	except Exception as e:
		return {'ok': False, 'error': 'Selection drive failed: %s' % e}

	ox = oy = 0.
	if global_origin is not None and global_origin != TransformOrigin.BASELINE:
		try:
			src_b = Bounds([(nodes[i].x, nodes[i].y) for i in sel])
			dst_b = Bounds(result)
			sx0, sy0 = src_b.align_matrix[global_origin.code]
			dx0, dy0 = dst_b.align_matrix[global_origin.code]
			ox, oy = sx0 - dx0, sy0 - dy0
		except Exception:
			ox = oy = 0.

	for i, pos in zip(sel, result):
		nodes[i].x = pos[0] + ox
		nodes[i].y = pos[1] + oy

	return {'ok': True, 'selection': len(sel)}


def npa_delta_live_clear(glyph, scope_layers, NodeActions):
	'''Drop the live snapshot. Called when the user toggles Live off
	or when the host detects that the Live Axis inputs have changed.
	'''
	global _live_snapshot
	_live_snapshot = None
	return {'ok': True}
