# MODULE: TypeRig / Core / Actions / Delta Machine
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
'''Delta Machine: stem-driven interpolation targets per glyph group.

The Delta Machine bakes target layers from virtual axes, like the Delta
panel's Bake, but each target row also names a glyph group, so one layer
can get different stems and sizes for different glyphs (Vassil for the
lowercase with one set of values, Vassil for the uppercase with another).
A row without a group works on the selected glyphs. Width and height are
in percent (default) or in units, each on its own: 60 % wide and exactly
700 units high is one row. Units are measured on the group's reference
glyph when it has one (the scale found there is used for the whole group,
so overshoots and descenders keep their proportions), else on each glyph.

This module is host neutral: the document (normalize, validate), unit
parsing, and the plan that turns the rows into one core Delta setup per
glyph (delta_panel_actions.npa_delta_bake / npa_delta_solve_target).
'''

from __future__ import absolute_import, print_function

import copy
import json

from typerig.core.actions import delta_panel_actions as dpa

# - Init -------------------------------------------------------------------
TOOL       = 'TypeRig Delta Machine'
VERSION    = '0.1'
FORMAT     = 1
LIB_KEY    = 'com.typerig.delta.machine.setup'		# font lib; the panel uses ...axissetup / panel.delta.live
SELECTION  = ''				# group of a row that works on the selected glyphs
SELECTION_LABEL = 'Selection'
UNITS      = ('%', 'u')		# percent of the base input, font units
ORIGINS    = ('BS', 'BL', 'BM', 'BR', 'LM', 'CE', 'RM', 'TL', 'TM', 'TR')
ORIGIN_LABELS = (		# (code, label) — the per-row Origin popup
	('BS', 'Baseline'), ('BL', 'Bottom left'), ('BM', 'Bottom middle'), ('BR', 'Bottom right'),
	('LM', 'Left middle'), ('CE', 'Center'), ('RM', 'Right middle'),
	('TL', 'Top left'), ('TM', 'Top middle'), ('TR', 'Top right'),
)

OPTION_DEFAULTS = {
	'origin': 'BS',				# legacy (v0.1): one origin for all rows; rows have their own now
	'extrapolate': True,
	'selection_only': False,	# named groups: only their selected glyphs
	'skip_composites': True,	# composites (and mixed glyphs) get no delta: target layer + metrics only
}

# Advanced tab: stored, not used yet (the engine options of later versions)
ADVANCED_DEFAULTS = {
	'engine': 'delta-scale',	# delta-scale | piecewise | adaptive
	'interpolation': 'linear',	# linear | clamp (no extrapolation past the inputs)
	'stems': 'table',			# table | self-metered (measure each glyph's own stems)
	'italic': 'master',			# master | none | custom
	'italic_angle': 0.,
	'notes': '',
}

TARGET_DEFAULTS = {
	'layer': '', 'group': SELECTION, 'vstem': 100., 'hstem': 100.,
	'width': {'value': 100., 'unit': '%'}, 'height': {'value': 100., 'unit': '%'},
	'origin': 'BS',				# transform origin of the row (BS = baseline, 0 / 0)
	'anchors': True, 'metrics': True, 'kerning': False,
}


def _num(value, default=None):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


# - Dimensions -------------------------------------------------------------
def parse_dimension(value, default_unit='%'):
	'''Width / height cell -> {'value', 'unit'} or None.
	'60', '60%', '60 %' -> percent; '700u', '700 u', '700 units' -> units.
	A dict {'value', 'unit'} is checked and passed through.'''
	if isinstance(value, dict):
		number, unit = _num(value.get('value')), value.get('unit', default_unit)
		return {'value': number, 'unit': unit} if number is not None and unit in UNITS else None
	if isinstance(value, (int, float)):
		return {'value': float(value), 'unit': default_unit}
	text = str(value or '').strip().lower().replace(' ', '')
	unit = default_unit
	for suffix, u in (('units', 'u'), ('unit', 'u'), ('u', 'u'), ('%', '%')):
		if text.endswith(suffix):
			text, unit = text[:-len(suffix)], u
			break
	number = _num(text)
	return {'value': number, 'unit': unit} if number is not None else None


def format_dimension(dim):
	'''{'value', 'unit'} -> '60 %' / '700 u'.'''
	return '{:g} {}'.format(dim['value'], dim['unit'])


# - Document ---------------------------------------------------------------
def machine_new(masters=()):
	'''An empty document. masters: master names (the axis input candidates).'''
	return {
		'tool': TOOL, 'version': VERSION, 'format': FORMAT, 'about': __doc__.strip(),
		'font': {}, 'saved': '',
		'options': dict(OPTION_DEFAULTS),
		'masters': [{'name': str(n)} for n in masters],
		'axes': [], 'groups': [],
		'advanced': dict(ADVANCED_DEFAULTS),
	}


def norm_target(row, origin='BS'):
	'''Any target row -> the document shape (missing keys get defaults;
	origin: for rows saved without one).'''
	out = copy.deepcopy(TARGET_DEFAULTS)
	out['origin'] = origin if origin in ORIGINS else 'BS'
	if not isinstance(row, dict):
		return out
	if row.get('origin') in ORIGINS:
		out['origin'] = row['origin']
	out['layer'] = str(row.get('layer', row.get('name', '')) or '').strip()
	out['group'] = str(row.get('group', SELECTION) or SELECTION).strip()
	for key in ('vstem', 'hstem'):
		out[key] = _num(row.get(key), out[key])
	for key, legacy_pct, legacy_units in (('width', 'sx', 'w'), ('height', 'sy', 'h')):
		dim = parse_dimension(row[key]) if key in row else None
		if dim is None and row.get('mode') == 'dimensions' and _num(row.get(legacy_units)) is not None:
			dim = {'value': float(row[legacy_units]), 'unit': 'u'}
		if dim is None and _num(row.get(legacy_pct)) is not None:
			dim = {'value': float(row[legacy_pct]), 'unit': '%'}
		if dim is not None:
			out[key] = dim
	for key in ('anchors', 'metrics', 'kerning'):
		if isinstance(row.get(key), bool):
			out[key] = row[key]
	return out


def norm_group(group):
	if not isinstance(group, dict):
		return None
	name = str(group.get('name', '') or '').strip()
	if not name:
		return None
	glyphs = []
	for g in group.get('glyphs', []) or []:
		g = str(g)
		if g and g not in glyphs:
			glyphs.append(g)
	return {'name': name, 'color': str(group.get('color', '') or ''),
	        'reference': str(group.get('reference', '') or '').strip(), 'glyphs': glyphs}


def _from_delta_setup(raw):
	'''TR Panel / FontRig / FL Delta setup -> document (targets as Selection rows).'''
	setup = dpa.delta_setup_normalize(raw)
	doc = machine_new()
	doc['masters'] = [{'name': m['name']} for m in setup['masters']]
	opts = setup['options']
	doc['options'].update(origin=opts.get('origin', 'BS'), extrapolate=bool(opts.get('extrapolate', True)))
	for ax in setup['axes']:
		targets = []
		for t in ax['targets']:
			row = norm_target(dict(t, layer=t['name']), origin=opts.get('origin', 'BS'))
			row['anchors'], row['metrics'] = bool(opts.get('anchors', True)), bool(opts.get('metrics', True))
			targets.append(row)
		doc['axes'].append({'name': ax['name'],
		                    'inputs': [{'name': r['name'], 'vstem': r['vstem'], 'hstem': r['hstem']} for r in ax['inputs']],
		                    'targets': targets})
	return doc


def machine_normalize(raw):
	'''A Delta Machine document (dict or JSON string) -> the current shape.
	A Delta panel / FontRig / FL setup is converted (its targets become
	Selection rows). Raises ValueError when raw cannot be read.'''
	if isinstance(raw, (str, bytes)):
		raw = json.loads(raw)
	if not isinstance(raw, dict):
		raise ValueError('Delta Machine document must be a dict')
	if raw.get('tool') != TOOL:
		return _from_delta_setup(raw)

	doc = machine_new()
	for key in ('font', 'saved'):
		if key in raw:
			doc[key] = copy.deepcopy(raw[key])
	opts = raw.get('options') or {}
	doc['options'].update({k: opts[k] for k in OPTION_DEFAULTS if k in opts})
	if doc['options']['origin'] not in ORIGINS:
		doc['options']['origin'] = 'BS'
	adv = raw.get('advanced') or {}
	doc['advanced'].update({k: adv[k] for k in ADVANCED_DEFAULTS if k in adv})
	doc['masters'] = [{'name': str(m.get('name'))} for m in raw.get('masters', []) or []
	                  if isinstance(m, dict) and m.get('name')]
	for ax in raw.get('axes', []) or []:
		if not isinstance(ax, dict):
			continue
		inputs = []
		for r in ax.get('inputs', []) or []:
			if isinstance(r, dict) and r.get('name'):
				inputs.append({'name': str(r['name']), 'vstem': _num(r.get('vstem'), r.get('vstem')),
				               'hstem': _num(r.get('hstem'), r.get('hstem'))})
		doc['axes'].append({'name': str(ax.get('name', '') or '').strip(), 'inputs': inputs,
		                    'targets': [norm_target(t, origin=doc['options']['origin'])
		                                for t in ax.get('targets', []) or [] if isinstance(t, dict)]})
	doc['groups'] = [g for g in (norm_group(g) for g in raw.get('groups', []) or []) if g is not None]
	return doc


def machine_validate(doc):
	'''Errors that stop a bake (empty list = ready).'''
	errors = []
	core_axes = [{'name': ax['name'], 'inputs': ax['inputs'],
	              'targets': [{'name': '%s / %s' % (t['layer'], t['group'] or SELECTION_LABEL)} for t in ax['targets']]}
	             for ax in doc.get('axes', [])]
	errors.extend(dpa.delta_setup_validate({'axes': core_axes}))
	groups = {}
	for g in doc.get('groups', []):
		if g['name'] in groups or g['name'] == SELECTION_LABEL:
			errors.append('Group names must be unique and not "%s": %s.' % (SELECTION_LABEL, g['name']))
		groups[g['name']] = g
	for ax in doc.get('axes', []):
		for t in ax['targets']:
			if not t['layer']:
				errors.append('Axis "%s": a target has no layer name.' % ax['name'])
			if t['group'] and t['group'] not in groups:
				errors.append('Axis "%s" / %s: unknown group "%s".' % (ax['name'], t['layer'], t['group']))
			for key in ('vstem', 'hstem'):
				if _num(t[key], 0.) <= 0:
					errors.append('Axis "%s" / %s: %s must be > 0.' % (ax['name'], t['layer'], key))
			for key in ('width', 'height'):
				if t[key]['value'] <= 0:
					errors.append('Axis "%s" / %s: %s must be > 0.' % (ax['name'], t['layer'], key))
	return errors


# - Plan -------------------------------------------------------------------
def target_to_core(row, scales=None):
	'''Document target row -> core target. scales: (sx %, sy %) solved on a
	reference glyph; the row then bakes as plain stems mode.'''
	w, h = row['width'], row['height']
	core = {'name': row['layer'], 'vstem': float(row['vstem']), 'hstem': float(row['hstem']),
	        'anchors': bool(row['anchors']), 'metrics': bool(row['metrics']),
	        'origin': row.get('origin', 'BS'), 'color': ''}
	if scales is not None:
		core.update(mode='stems', sx=float(scales[0]), sy=float(scales[1]))
		return core
	fit = ''.join(c for c, d in (('w', w), ('h', h)) if d['unit'] == 'u')
	core['sx'] = w['value'] if w['unit'] == '%' else 100.
	core['sy'] = h['value'] if h['unit'] == '%' else 100.
	if not fit:
		core['mode'] = 'stems'
	else:
		core.update(mode='mixed', fit=fit,
		            w=w['value'] if w['unit'] == 'u' else None,
		            h=h['value'] if h['unit'] == 'u' else None)
	return core


def has_units(row):
	return row['width']['unit'] == 'u' or row['height']['unit'] == 'u'


def machine_plan(doc, selection, existing=None):
	'''Which rows bake which glyphs.

	selection: glyph names the Selection rows work on (and, with the
	selection_only option, the only glyphs named groups may touch).
	existing: glyph names in the font (None = no check).

	Per glyph and (axis, layer) the first matching row wins; rows with a
	named group come before Selection rows. Returns
	  {'glyphs': {glyph: [(axis_index, row_index), ...]},   # in font order of first appearance
	   'refs':   [{'axis', 'row', 'glyph'}],               # units rows solved on a reference glyph
	   'warnings': [...]}'''
	opts = doc.get('options', OPTION_DEFAULTS)
	selection = [g for g in selection if existing is None or g in existing]
	selected = set(selection)
	groups = {g['name']: g for g in doc.get('groups', [])}
	warnings, refs, picks, order = [], [], {}, []
	missing = set()

	def members(row):
		if not row['group']:
			return selection
		group = groups.get(row['group'])
		if group is None:
			return []
		names = group['glyphs']
		if existing is not None:
			missing.update(n for n in names if n not in existing)
			names = [n for n in names if n in existing]
		if opts.get('selection_only'):
			names = [n for n in names if n in selected]
		return names

	for a, ax in enumerate(doc.get('axes', [])):
		rows = list(enumerate(ax['targets']))
		rows = [r for r in rows if r[1]['group']] + [r for r in rows if not r[1]['group']]
		taken = {}		# (glyph, layer) -> row index
		overlaps = {}
		for i, row in rows:
			names = members(row)
			if not names:
				continue
			group = groups.get(row['group'])
			if group is not None and group['reference'] and has_units(row):
				if existing is None or group['reference'] in existing:
					refs.append({'axis': a, 'row': i, 'glyph': group['reference']})
				else:
					warnings.append('Group "%s": reference glyph %s is not in the font; each glyph is measured on its own.'
					                % (row['group'], group['reference']))
			for name in names:
				key = (name, row['layer'])
				if key in taken:
					first = ax['targets'][taken[key]]
					if row['group'] and first['group'] != row['group']:
						overlaps.setdefault((row['layer'], first['group'], row['group']), []).append(name)
					continue
				taken[key] = i
				if name not in picks:
					picks[name] = []
					order.append(name)
				picks[name].append((a, i))
		for (layer, first, second), names in overlaps.items():
			warnings.append('Axis "%s" / %s: %d glyph(s) in both "%s" and "%s" (first row wins): %s'
			                % (ax['name'], layer, len(names), first, second, ' '.join(names[:8])))
	if missing:
		warnings.append('%d group glyph(s) not in the font: %s' % (len(missing), ' '.join(sorted(missing)[:8])))
	return {'glyphs': {name: picks[name] for name in order}, 'refs': refs, 'warnings': warnings}


def core_setup(doc, picks, solved=None, italic_angle=0.):
	'''Core Delta setup for one glyph. picks: [(axis_index, row_index)]
	from machine_plan; solved: {(axis_index, row_index): (sx %, sy %)}
	from the reference pass.'''
	solved = solved or {}
	by_axis = {}
	for a, i in picks:
		by_axis.setdefault(a, []).append(i)
	axes = []
	for a, rows in sorted(by_axis.items()):
		ax = doc['axes'][a]
		axes.append({'name': ax['name'], 'inputs': ax['inputs'],
		             'targets': [target_to_core(ax['targets'][i], solved.get((a, i))) for i in rows]})
	opts = doc.get('options', OPTION_DEFAULTS)
	return {'axes': axes, 'options': {
		'origin': opts.get('origin', 'BS'), 'extrapolate': bool(opts.get('extrapolate', True)),
		'metrics': True, 'anchors': True, 'italic_angle': float(italic_angle)}}


def ref_setup(doc, ref, italic_angle=0.):
	'''Core setup of the reference pass: one axis, the one units row.'''
	ax = doc['axes'][ref['axis']]
	return {'axes': [{'name': ax['name'], 'inputs': ax['inputs'],
	                  'targets': [target_to_core(ax['targets'][ref['row']])]}],
	        'options': {'extrapolate': bool(doc.get('options', OPTION_DEFAULTS).get('extrapolate', True)),
	                    'italic_angle': float(italic_angle)}}


def machine_dump(doc):
	'''Human readable JSON (indent 2; tool / version / about first).'''
	first = ('tool', 'version', 'format', 'about', 'font', 'saved', 'options')
	ordered = {k: doc[k] for k in first if k in doc}
	ordered.update({k: v for k, v in doc.items() if k not in ordered})
	return json.dumps(ordered, indent=2, ensure_ascii=False)
