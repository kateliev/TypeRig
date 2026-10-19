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
#           'keep_directions': bool, # italic: put horizontal / vertical /
#                                  # slanted handles back after the bake
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
	adaptive_scale de-slants with x - y*i, so i must be a slope (tan), not
	an angle in radians.'''
	return math.tan(math.radians(-float(opts.get('italic_angle', 0.0) or 0.0)))


# - Direction lock (italic) ----------------------------------------
# In italic mode adaptive_scale de-slants, scales X and Y apart, then
# re-slants. Horizontal and on-slant handles survive an anisotropic
# scale, true vertical handles lean by ~ angle * (1 - sx/sy). The lock
# labels every handle that is horizontal / vertical / on the slant in
# ALL inputs and puts it back after the bake (before host rounding).
# See TypeRig-Glyphs Handouts/delta_italic_handles_handout.md.
LOCK_TOLERANCE = 0.5		# units: max off-direction drift in the inputs

_LOCK_H, _LOCK_V, _LOCK_S = 'h', 'v', 's'


def _handle_owners(layer):
	'''[(off_index, on_index)] in point_array order: each off-curve that
	sits next to an on-curve is that node's handle. Off-curves between two
	on-curves (quadratic) or between two off-curves are skipped. Contours
	wrap (open contours end on on-curves, so the wrap never pairs them).
	Also returns {on_index: smooth}.'''
	pairs, smooth, base = [], {}, 0
	for shape in layer.shapes:
		for contour in shape.contours:
			nodes = list(contour.data)
			n = len(nodes)
			for k, node in enumerate(nodes):
				if node.is_on:
					smooth[base + k] = bool(getattr(node, 'smooth', False))
					continue
				if n < 2: continue
				p, q = (k - 1) % n, (k + 1) % n
				prev_on, next_on = nodes[p].is_on, nodes[q].is_on
				if prev_on and not next_on:
					pairs.append((base + k, base + p))
				elif next_on and not prev_on:
					pairs.append((base + k, base + q))
			base += n
	return pairs, smooth


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


def direction_labels(input_layers, slope, tol=LOCK_TOLERANCE):
	'''Lock plan for an axis: {'pairs': [(off, on, label)], 'smooth': {on: bool}}.
	A handle is labelled only when it has the same direction in every input.
	Returns None when there is nothing to lock (upright design, < 2 inputs).'''
	if not slope or len(input_layers) < 2:
		return None
	pairs, smooth = _handle_owners(input_layers[0])
	arrays = [list(l.point_array.tuple) for l in input_layers]
	size = len(arrays[0])
	if any(len(a) != size for a in arrays):
		return None
	locked = []
	for off, on in pairs:
		labels = set(_direction_of(a[on], a[off], slope, tol) for a in arrays)
		if len(labels) == 1 and None not in labels:
			locked.append((off, on, labels.pop()))
	if not locked:
		return None
	return {'pairs': locked, 'handles': pairs, 'smooth': smooth, 'size': size}


def lock_directions(points, plan, slope):
	'''Put labelled handles back on their direction (points: list of (x, y),
	changed in place and returned). Vertical: x = node x (Y kept). Slant:
	back on the slant line through the node (Y kept). Horizontal: y = node y.
	A smooth node with one locked handle turns its other handle to stay in
	line (length kept). Returns (points, moved, max_drift).'''
	if not plan or len(points) != plan['size']:
		return points, 0, 0.
	moved, drift, locked_by_on = 0, 0., {}
	for off, on, label in plan['pairs']:
		nx, ny = points[on]
		hx, hy = points[off]
		if label == _LOCK_V:
			new = (nx, hy)
		elif label == _LOCK_S:
			new = (nx + (hy - ny) * slope, hy)
		else:
			new = (hx, ny)
		d = math.hypot(new[0] - hx, new[1] - hy)
		if d > 1e-9:
			moved += 1
			drift = max(drift, d)
		points[off] = new
		locked_by_on.setdefault(on, []).append(off)

	# Smooth nodes: keep the free handle in line with the locked one
	handles = {}
	for off, on in plan['handles']:
		handles.setdefault(on, []).append(off)
	for on, offs in locked_by_on.items():
		if len(offs) != 1 or not plan['smooth'].get(on):
			continue
		others = [o for o in handles.get(on, []) if o not in offs]
		if len(others) != 1:
			continue
		nx, ny = points[on]
		lx, ly = points[offs[0]][0] - nx, points[offs[0]][1] - ny
		ll = math.hypot(lx, ly)
		ox, oy = points[others[0]]
		ol = math.hypot(ox - nx, oy - ny)
		if ll < 1e-9 or ol < 1e-9:
			continue
		new = (nx - lx / ll * ol, ny - ly / ll * ol)
		d = math.hypot(new[0] - ox, new[1] - oy)
		if d > 1e-9:
			moved += 1
			drift = max(drift, d)
		points[others[0]] = new
	return points, moved, drift


def _bake_target_stems(base_layer, vaxis, target, italic_rad,
                       extrapolate, global_origin, source_bounds, lock=None, report=None):
	'''Stems-mode: drive DeltaScale.scale_by_stem for every viable
	attribute, write into a clone of base_layer, realign to chosen
	origin (skip when origin is BASELINE — that's scale_by_stem's native
	reference). lock: a direction_labels plan; when given, labelled
	handles are put back on their direction (italic direction lock).
	report: optional dict, gets 'locked' (handles moved) and 'drift'
	(largest move, units).
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
		if attrib == 'point_array' and lock:
			result, moved, drift = lock_directions(result, lock, italic_rad)
			if report is not None:
				report['locked'] = report.get('locked', 0) + moved
				report['drift'] = max(report.get('drift', 0.), drift)
		_apply_array(new_layer, attrib, result)

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
	'keep_directions': True,
}


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
	italic_rad = _italic_slope(opts)		# a slope (tan), named for the engine argument
	keep_directions = bool(opts.get('keep_directions', True))
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
		lock = direction_labels(input_layers, italic_rad) if keep_directions else None

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
			if lock_report.get('locked'):
				entry['locked'] = lock_report['locked']
				entry['drift'] = round(lock_report['drift'], 2)
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
		'lock': (direction_labels(snap_layers, _italic_slope(opts))
		         if opts.get('keep_directions', True) and not sel_indices else None),
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
		new_layer = _bake_target_stems(
			base_layer, state['vaxis'], target,
			state['italic_rad'], state['extrapolate'],
			global_origin, source_bounds, state.get('lock'))
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

	return {'ok': True}


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
