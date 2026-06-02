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
#                   # stems-mode target
#                   {'mode': 'stems', 'name': str,
#                    'vstem': float, 'hstem': float,
#                    'sx': float, 'sy': float,          # percent
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
#           'origin':      'BL'|'BR'|'TL'|'TR'|'CE'|'BS',  # global, stems mode
#           'italic_angle': float                          # degrees (signed)
#       }
#   }
#
# Returns a status dict — JS reads it via the bridge.

from __future__ import absolute_import, print_function

import json
import math
import copy

from typerig.core.objects.array import PointArray
from typerig.core.objects.layer import Layer
from typerig.core.objects.transform import TransformOrigin


# - Module-level state (banks). Empty for now; available for v2 ----
_last_setup = None


# - Origin code → TransformOrigin map -----------------------------
_ORIGIN_FROM_CODE = {
	'BL': TransformOrigin.BOTTOM_LEFT,
	'BR': TransformOrigin.BOTTOM_RIGHT,
	'TL': TransformOrigin.TOP_LEFT,
	'TR': TransformOrigin.TOP_RIGHT,
	'CE': TransformOrigin.CENTER,
	'BS': TransformOrigin.BASELINE,
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
	'''Return the layer named target_name. If it doesn't exist on the
	glyph, clone base_layer (so the new layer inherits metrics, anchor
	shape, etc.) and append it. Mirrors host_duplicate_layer from the
	FL panel.
	'''
	existing = glyph.layer(target_name)
	if existing is not None:
		return existing
	new_layer = _clone_layer_geometry(base_layer, target_name)
	glyph.layers.append(new_layer)
	return new_layer


def _apply_array(layer, attrib, data):
	if attrib == 'point_array':
		layer.point_array = PointArray(data)
	else:
		setattr(layer, attrib, data)


def _bake_target_stems(base_layer, vaxis, target, italic_rad,
                       extrapolate, global_origin, source_bounds):
	'''Stems-mode: drive DeltaScale.scale_by_stem for every viable
	attribute, write into a clone of base_layer, realign to chosen
	origin (skip when origin is BASELINE — that's scale_by_stem's native
	reference).
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

	if global_origin is not None and global_origin != TransformOrigin.BASELINE:
		try:
			sx0, sy0 = source_bounds.align_matrix[global_origin.code]
			dest_bounds = new_layer.bounds
			dx0, dy0 = dest_bounds.align_matrix[global_origin.code]
			new_layer.shift(sx0 - dx0, sy0 - dy0)
		except Exception:
			pass

	return new_layer


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


# - Dispatchers ---------------------------------------------------
def npa_delta_bake(glyph, scope_layers, NodeActions, setup_json):
	'''Bake all targets across all axes in the supplied setup against
	the active glyph. Returns a JSON-serialisable status dict.

	scope_layers is ignored — Delta operates over the layers named in
	the setup, not over the layer-mode scope. The host is expected to
	keep glyph current.
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
	italic_deg = float(opts.get('italic_angle', 0.0))
	italic_rad = math.radians(-italic_deg)
	extrapolate = bool(opts.get('extrapolate', True))
	global_origin = _origin_of(opts)

	requested = ['point_array']
	if opts.get('metrics', True): requested.append('metric_array')
	if opts.get('anchors', True): requested.append('anchor_array')

	warnings = []
	targets_baked = 0
	axes_built = 0

	for axis in axes:
		axis_name = axis.get('name', '<unnamed>')
		inputs = axis.get('inputs', [])
		if len(inputs) < 2:
			warnings.append('Axis "%s": needs at least 2 inputs.' % axis_name)
			continue

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
			continue

		# Decide attribs viable across all surviving inputs.
		viable, skipped = _viable_attribs(input_layers, requested)
		for s in skipped:
			warnings.append('Axis "%s": %s — skipped.' % (axis_name, s))
		if 'point_array' not in viable:
			warnings.append('Axis "%s": no usable point_array.' % axis_name)
			continue

		# Build the virtual axis once.
		try:
			vaxis = glyph.create_virtual_axis(
				[l.name for l in input_layers], attributes=viable)
		except Exception as e:
			warnings.append('Axis "%s": create_virtual_axis failed: %s'
				% (axis_name, e))
			continue

		axes_built += 1

		base_layer = input_layers[0]
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
			try:
				if mode == 'stems':
					new_layer = _bake_target_stems(
						base_layer, vaxis, target,
						italic_rad, extrapolate,
						global_origin, source_bounds)
				else:
					new_layer = _bake_target_dims(
						base_layer, vaxis, target, extrapolate)
			except Exception as e:
				warnings.append('Axis "%s" / target "%s": bake failed: %s'
					% (axis_name, t_name, e))
				continue

			new_layer.name = t_name
			# Ensure FL/host layer exists, then copy our scaled geometry in.
			dst = _ensure_target_layer(glyph, base_layer, t_name)
			dst.point_array = new_layer.point_array
			if 'metric_array' in viable:
				dst.metric_array = new_layer.metric_array
			if 'anchor_array' in viable:
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

	return {
		'ok': True,
		'axes_built': axes_built,
		'targets_baked': targets_baked,
		'warnings': warnings,
	}


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


def npa_delta_master_names(glyph, scope_layers, NodeActions):
	'''Convenience: return the list of layer names on the active glyph.
	Used by the host to seed the master pool.
	'''
	return [l.name for l in glyph.layers]
