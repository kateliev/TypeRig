# SPDX-License-Identifier: AGPL-3.0-only
# MODULE: TypeRig / Core / Actions / Delta Calculator
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
'''Delta Machine calculator: Input value and Desired value per input ->
Percent through the Delta Machine, with no glyph and no font
(dm_percent_desired; dm_percent / dm_value: one wanted value, or a percent).

A value (a distance in units: a sidebearing, an advance, a stem, a
counter...) is typed per input of an axis. The Delta Machine moves it as it
moves any distance of an outline: interpolated at the target stem, then
scaled with the stems preserved (compensation 0). With compensation 0 the
result is affine in the scale, not proportional:

    d(s) = d_t + (s - 1) * (d_heavy - b * d_t) / (1 - b)

d_t: the value at the target stem (= the result at 100 %); d_heavy: the
value on the heavier input of the segment; b: heavier input stem / target
stem. So the percent that gives a wanted value is not wanted / d_t (the
plain ratio) unless the value is the same on every input. A value that
changes like the stem (d_heavy / d_t = b) does not change with the scale.

The math is the core Delta itself, not a copy: a two-point DeltaScale
(0 and the value, per input) is driven by DeltaScale.scale_by_stem and the
percent is solved by delta_panel_actions._solve_scale (the solver of the
units sizes) with a signed measure. Axes with more inputs and
extrapolation work as in the bake.

Desired values per input (a client's sidebearings for each master): the
wanted value on the target is the desired values interpolated at the target
stem (the same DeltaScale at 100 %), then solved as above.

Affine metrics (Delta Machine default since 2026-11-06, Advanced > Delta
metrics off): a Met. W percent multiplies the sidebearings interpolated at
the target stem, so its percent is the plain ratio (affine_percent).
Width / Height stay Delta Machine percents.

Host neutral; nothing is written anywhere.
'''

from __future__ import absolute_import, division, print_function

from typerig.core.objects.delta import DeltaScale
from typerig.core.actions import delta_panel_actions as dpa
from typerig.core.actions import delta_machine_actions as dma

# - Init -------------------------------------------------------------------
DIRECTIONS = ('h', 'v')		# h: horizontal distance (V stems, Width / Met. W %); v: vertical (H stems, Height %)
DIRECTION_LABELS = (('h', 'Horizontal (V stems, Width / Met. W %)'),
                    ('v', 'Vertical (H stems, Height %)'))
TOL = 1e-6					# solver tolerance, units (the measure is affine: two steps)


def _num(value, default=None):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


# - Setup ------------------------------------------------------------------
def calc_axes(doc):
	'''Axes of a Delta Machine document: [{'name', 'inputs': [{'name',
	'vstem', 'hstem'}]}], in document order.'''
	return [{'name': ax['name'], 'inputs': [dict(r) for r in ax.get('inputs', [])]}
	        for ax in doc.get('axes', [])]


def calc_rows(doc):
	'''Target rows of a document, resolved (override rows with their
	inherited cells): [{'label', 'axis', 'vstem', 'hstem', 'sx'}]. label: as
	the bake report names a row; sx: the Width as a scale (1. = 100 %), None
	for a Width in units.'''
	rows = doc.get('targets', [])
	by_id = dict((r.get('id'), r) for r in rows if r.get('id'))
	out = []
	for row in rows:
		r = dma.resolve(row, by_id.get(row.get('parent')) if row.get('parent') else None)
		try:
			label = dma.row_label(r)
		except (KeyError, TypeError):
			label = r.get('layer', '')
		if dma.is_override(row):
			label = dma.OVERRIDE_MARK + ' ' + label
		width = r.get('width') or {}
		sx = _num(width.get('value'), 100.) / 100. if width.get('unit', '%') == '%' else None
		out.append({'label': label, 'axis': r.get('axis', ''),
		            'vstem': _num(r.get('vstem'), 0.), 'hstem': _num(r.get('hstem'), 0.), 'sx': sx})
	return out


# - Math -------------------------------------------------------------------
def _delta(inputs, values, direction):
	'''Two-point DeltaScale: per input the points 0 and value on the
	direction's coordinate; stems from the inputs.'''
	points, stems = [], []
	for inp, value in zip(inputs, values):
		v = float(value)
		points.append([(0., 0.), (v, 0.) if direction == 'h' else (0., v)])
		stems.append([(float(inp['vstem']), float(inp['hstem']))])	# one (V, H) per input, as glyph.create_virtual_axis
	return DeltaScale(points, stems)


def _measure(delta, stem, scale, italic_rad, extrapolate):
	'''Signed (dx, dy) of the two points (a value may be negative).'''
	(x0, y0), (x1, y1) = list(delta.scale_by_stem(stem, scale, (0., 0.), (0., 0.), 0., extrapolate))
	return x1 - x0, y1 - y0


def _check(inputs, values):
	if len(inputs) < 2:
		raise ValueError('The axis needs at least 2 inputs.')
	if len(values) != len(inputs):
		raise ValueError('One value per input is needed (%d inputs, %d values).' % (len(inputs), len(values)))
	for inp in inputs:
		if _num(inp.get('vstem')) is None or _num(inp.get('hstem')) is None:
			raise ValueError('Input "%s" has no stems.' % inp.get('name', ''))


def dm_value(inputs, values, stem, percent, direction='h', extrapolate=True):
	'''The value the Delta Machine gives at stem (vstem, hstem) and percent.
	inputs: the axis inputs [{'name', 'vstem', 'hstem'}]; values: one per
	input, units. Only the direction's percent is used.'''
	_check(inputs, values)
	i = DIRECTIONS.index(direction)
	scale = [1., 1.]
	scale[i] = float(percent) / 100.
	return _measure(_delta(inputs, values, direction), tuple(stem), tuple(scale), 0., extrapolate)[i]


def dm_percent(inputs, values, stem, output, direction='h', extrapolate=True):
	'''Percent that makes the Delta Machine give output at stem.

	Returns {'percent', 'at100' (the value at 100 %), 'plain' (output /
	at100 in percent, None when at100 is 0), 'result' (the value at the
	solved percent), 'residual', 'converged', 'fixed' (True: the value does
	not change with the scale, no percent can reach another one)}.'''
	_check(inputs, values)
	i = DIRECTIONS.index(direction)
	delta = _delta(inputs, values, direction)
	stem = tuple(stem)
	output = float(output)
	at100 = _measure(delta, stem, (1., 1.), 0., extrapolate)[i]
	at200 = _measure(delta, stem, (2., 2.), 0., extrapolate)[i]
	plain = output / at100 * 100. if at100 else None
	out = {'at100': at100, 'plain': plain, 'fixed': abs(at200 - at100) <= TOL}
	if out['fixed']:
		out.update(percent=None, result=at100, residual=abs(output - at100),
		           converged=abs(output - at100) <= TOL)
		return out
	dims = [None, None]
	dims[i] = output
	scales, ok, res = dpa._solve_scale(delta, stem, (1., 1.), tuple(dims), 0., extrapolate,
	                                   tol=TOL, measure=_measure)
	result = _measure(delta, stem, scales, 0., extrapolate)[i]
	out.update(percent=scales[i] * 100., result=result, residual=res[i], converged=ok)
	return out


def affine_percent(inputs, values, stem, output, direction='h', extrapolate=True, sx=None):
	'''Percent for an affine value (the Delta Machine's sidebearings with
	Advanced > Delta metrics off): the value interpolated at stem times the
	percent, so percent = output / value at stem. Same dict as dm_percent
	('affine': True); no percent when the value at stem is 0.

	A negative value at stem (an overhang, 'negative': True) follows the
	kerning rule in the bake: output = value * sx * sx / m, so
	m = sx * sx * value / output. It needs the row's Width (sx, 1. = 100 %)
	and a negative output; else no percent.'''
	_check(inputs, values)
	at100 = dm_value(inputs, values, stem, 100., direction, extrapolate)
	output = float(output)
	if at100 > 0.:
		plain = output / at100 * 100.
	elif at100 < 0. and sx and output < 0.:
		plain = sx * sx * at100 / output * 100.
	else:
		plain = None
	out = {'at100': at100, 'plain': plain, 'fixed': plain is None, 'affine': True, 'negative': at100 < 0.}
	if plain is None:
		out.update(percent=None, result=at100, residual=abs(output - at100), converged=abs(output - at100) <= TOL)
	else:
		out.update(percent=plain, result=output, residual=0., converged=True)
	return out


def dm_percent_desired(inputs, values, desired, stem, direction='h', extrapolate=True, affine=False, sx=None):
	'''Percent that turns the input values into the desired values, at the
	target stem: the desired values are interpolated at stem (as the Delta
	Machine interpolates at 100 %), the percent is solved for that value
	(dm_percent; affine: affine_percent, the plain ratio, for a Met. W
	with affine metrics; sx: the row's Width, for a negative value).
	values / desired: one per input, units.

	Returns the dm_percent dict and 'wanted' (the desired value at stem).'''
	_check(inputs, desired)
	wanted = dm_value(inputs, desired, stem, 100., direction, extrapolate)
	if affine:
		out = affine_percent(inputs, values, stem, wanted, direction, extrapolate, sx)
	else:
		out = dm_percent(inputs, values, stem, wanted, direction, extrapolate)
	out['wanted'] = wanted
	return out
