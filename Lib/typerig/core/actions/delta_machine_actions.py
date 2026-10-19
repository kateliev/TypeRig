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
from typerig.core.actions import designspace_actions as dsa

# - Init -------------------------------------------------------------------
TOOL       = 'TypeRig Delta Machine'
VERSION    = '0.4'
FORMAT     = 3				# 3 (v0.4): flag_* are Glyphs label colour indexes (1 / 2: RGBA -> nearest label);
							# optional target 'msx'. 2 (v0.3): advanced.italic_fix. 1 reads as 3 (fix off)
LIB_KEY    = 'com.typerig.delta.machine.setup'		# font lib; the panel keys are in core/base/lib_keys.py
SELECTION  = ''				# group of a row that works on the selected glyphs
SELECTION_LABEL = 'Selection'
UNITS      = ('%', 'u')		# percent of the base input, font units
METRICS_SCALE_OFF = '—'		# Met. W cell of a row with Met. off (shown grey, not editable)
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

# Glyph status after a bake, mildest first: a glyph keeps the worst status
# any of its layers reached (flag colour, log section)
STATUSES = ('done', 'warning', 'failed')
STATUS_LABELS = {'done': 'Done', 'warning': 'Warnings', 'failed': 'Failed'}

# Italic fix of the bake (core delta_panel_actions options, same keys):
# all off by default, so a document without it bakes as before.
ITALIC_FIX_DEFAULTS = dict((k, dpa.DELTA_OPTION_DEFAULTS[k]) for k in dpa.ITALIC_FIX_KEYS)
ITALIC_SOURCES = ('master', 'none', 'custom')

# Glyphs' label colours (glyph.color index): (name, approximate RGB for the
# swatches). Glyph flags use these only, so a flag is a colour the Font
# view filter knows. Older documents stored RGBA: the nearest label is used.
LABEL_COLORS = (
	('Red', (0.96, 0.29, 0.25)), ('Orange', (1.00, 0.58, 0.20)), ('Brown', (0.62, 0.43, 0.24)),
	('Yellow', (1.00, 0.85, 0.15)), ('Light green', (0.55, 0.90, 0.35)), ('Dark green', (0.20, 0.60, 0.25)),
	('Light blue', (0.50, 0.80, 1.00)), ('Dark blue', (0.15, 0.40, 0.90)), ('Purple', (0.60, 0.35, 0.85)),
	('Magenta', (0.95, 0.35, 0.75)), ('Light gray', (0.75, 0.75, 0.75)), ('Charcoal', (0.35, 0.35, 0.35)),
)

# Advanced tab. flag* / log* work since v0.2: glyphs are coloured by status
# after a bake (a Glyphs label colour, format 3), a text log is written to log_dir ('' = the
# font's folder). Since v0.3 (format 2) italic / italic_angle choose the
# bake's italic angle and italic_fix holds the italic fix options. The
# engine options (engine, interpolation, stems) are stored, not used yet.
ADVANCED_DEFAULTS = {
	'flag': False,				# colour the processed glyphs by status (overwrites their colour)
	'flag_done': 4,				# label colour index (LABEL_COLORS): light green
	'flag_warning': 3,			# yellow
	'flag_failed': 0,			# red
	'log': False,				# write a log file per bake
	'log_dir': '',				# folder of the log; '' = next to the font file
	'engine': 'delta-scale',	# delta-scale | piecewise | adaptive
	'interpolation': 'linear',	# linear | clamp (no extrapolation past the inputs)
	'stems': 'table',			# table | self-metered (measure each glyph's own stems)
	'italic': 'master',			# master (italic angle of the first input's master) | none | custom
	'italic_angle': 0.,			# custom angle, degrees, Glyphs sign (positive leans right)
	'italic_fix': dict(ITALIC_FIX_DEFAULTS),
	'notes': '',
}
FLAG_KEYS = {status: 'flag_' + status for status in STATUSES}

TARGET_DEFAULTS = {
	'layer': '', 'group': SELECTION, 'vstem': 100., 'hstem': 100.,
	'width': {'value': 100., 'unit': '%'}, 'height': {'value': 100., 'unit': '%'},
	'origin': 'BS',				# transform origin of the row (BS = baseline, 0 / 0)
	'anchors': True, 'metrics': True, 'kerning': False,
	'msx': None,				# metrics scale, percent (Met. W); None = the metrics follow the outline
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


def parse_metrics_scale(value):
	'''Met. W cell -> (ok, percent | None). '' / None -> (True, None):
	the metrics follow the outline. '90', '90%', '90 %' -> (True, 90.).
	Percent only: units ('600 u') and other text -> (False, None).
	The sidebearings are the ones DM gives at this percent (core
	delta_panel_actions, target 'msx'), never a numeric scale of LSB / RSB.'''
	if value is None:
		return True, None
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		return True, float(value)
	text = str(value).strip().replace(' ', '')
	if not text:
		return True, None
	if text.endswith('%'):
		text = text[:-1]
	number = _num(text)
	return (True, number) if number is not None else (False, None)


def format_metrics_scale(msx):
	'''percent | None -> '90 %' / ''.'''
	return '' if msx is None else '{:g} %'.format(msx)


def row_label(row):
	'''Target row -> 'Small caps / Lowercase: 80 % / metrics 90 %' (bake
	report: the rows with a metrics scale).'''
	text = '%s / %s: %s x %s' % (row['layer'], row['group'] or SELECTION_LABEL,
	                             format_dimension(row['width']), format_dimension(row['height']))
	if row.get('metrics') and row.get('msx') is not None:
		text += ' / metrics ' + format_metrics_scale(row['msx'])
	return text


def norm_label(value, default):
	'''Glyph flag colour -> a label colour index (0..11, LABEL_COLORS).
	An index passes; [r, g, b(, a)] in 0..1 (formats 1 / 2) -> the nearest
	label; anything else -> default.'''
	if isinstance(value, bool):
		return default
	if isinstance(value, (int, float)):
		return int(value) if float(value) == int(value) and 0 <= value < len(LABEL_COLORS) else default
	try:
		rgb = [min(1., max(0., float(c))) for c in value][:3]
	except (TypeError, ValueError):
		return default
	if len(rgb) < 3:
		return default
	return min(range(len(LABEL_COLORS)), key=lambda i: sum((a - b) ** 2 for a, b in zip(LABEL_COLORS[i][1], rgb)))


# - Document ---------------------------------------------------------------
def machine_new(masters=()):
	'''An empty document. masters: master names (the axis input candidates).'''
	return {
		'tool': TOOL, 'version': VERSION, 'format': FORMAT, 'about': __doc__.strip(),
		'font': {}, 'saved': '',
		'options': dict(OPTION_DEFAULTS),
		'masters': [{'name': str(n)} for n in masters],
		'axes': [], 'groups': [],
		'designspace': dsa.plan_new(),		# Designspace tab: font axes + masters plan
		'advanced': copy.deepcopy(ADVANCED_DEFAULTS),
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
	ok, msx = parse_metrics_scale(row.get('msx'))		# older documents: none -> None
	out['msx'] = msx if ok else None
	return out


def norm_italic_fix(raw):
	'''advanced.italic_fix -> every key of ITALIC_FIX_DEFAULTS (bool switches,
	float numbers >= 0); missing (format 1) -> the defaults: fix off.'''
	out = dict(ITALIC_FIX_DEFAULTS)
	raw = raw if isinstance(raw, dict) else {}
	for key, default in ITALIC_FIX_DEFAULTS.items():
		if key not in raw:
			continue
		if isinstance(default, bool):
			out[key] = bool(raw[key])
		else:
			out[key] = max(0., _num(raw[key], default))
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
	doc['advanced'].update({k: adv[k] for k in ADVANCED_DEFAULTS if k in adv and k != 'italic_fix'})
	doc['advanced']['italic_fix'] = norm_italic_fix(adv.get('italic_fix'))	# format 1: none -> off
	if doc['advanced']['italic'] not in ITALIC_SOURCES:
		doc['advanced']['italic'] = 'master'
	doc['advanced']['italic_angle'] = _num(doc['advanced']['italic_angle'], 0.)
	for key in FLAG_KEYS.values():
		doc['advanced'][key] = norm_label(doc['advanced'][key], ADVANCED_DEFAULTS[key])
	doc['advanced']['flag'] = bool(doc['advanced']['flag'])
	doc['advanced']['log'] = bool(doc['advanced']['log'])
	doc['advanced']['log_dir'] = str(doc['advanced']['log_dir'] or '')
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
	doc['designspace'] = dsa.plan_normalize(raw.get('designspace'))
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
			if t.get('msx') is not None and t['msx'] <= 0:
				errors.append('Axis "%s" / %s: metrics scale must be > 0.' % (ax['name'], t['layer']))
	return errors


# - Plan -------------------------------------------------------------------
def target_to_core(row, scales=None):
	'''Document target row -> core target. scales: (sx %, sy %) solved on a
	reference glyph; the row then bakes as plain stems mode.'''
	w, h = row['width'], row['height']
	core = {'name': row['layer'], 'vstem': float(row['vstem']), 'hstem': float(row['hstem']),
	        'anchors': bool(row['anchors']), 'metrics': bool(row['metrics']),
	        'origin': row.get('origin', 'BS'), 'color': ''}
	if row.get('msx') is not None:
		core['msx'] = float(row['msx'])		# a fixed percent, also after the reference pass
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
	options = {'origin': opts.get('origin', 'BS'), 'extrapolate': bool(opts.get('extrapolate', True)),
	           'metrics': True, 'anchors': True, 'italic_angle': float(italic_angle)}
	options.update(italic_fix(doc))
	return {'axes': axes, 'options': options}


def italic_fix(doc):
	'''The document's italic fix options (core option keys).'''
	return norm_italic_fix((doc.get('advanced') or {}).get('italic_fix'))


def bake_italic_angle(doc, master_angle):
	'''Bake italic angle, Glyphs sign, by advanced.italic: master ->
	master_angle (of the axis' first input), none -> 0, custom -> italic_angle.'''
	adv = doc.get('advanced') or {}
	source = adv.get('italic', 'master')
	if source == 'none':
		return 0.
	if source == 'custom':
		return _num(adv.get('italic_angle'), 0.)
	return float(master_angle or 0.)


def ref_setup(doc, ref, italic_angle=0.):
	'''Core setup of the reference pass: one axis, the one units row.'''
	ax = doc['axes'][ref['axis']]
	options = {'extrapolate': bool(doc.get('options', OPTION_DEFAULTS).get('extrapolate', True)),
	           'italic_angle': float(italic_angle)}
	options.update(italic_fix(doc))
	return {'axes': [{'name': ax['name'], 'inputs': ax['inputs'],
	                  'targets': [target_to_core(ax['targets'][ref['row']])]}],
	        'options': options}


def machine_dump(doc):
	'''Human readable JSON (indent 2; tool / version / about first).'''
	first = ('tool', 'version', 'format', 'about', 'font', 'saved', 'options')
	ordered = {k: doc[k] for k in first if k in doc}
	ordered.update({k: v for k, v in doc.items() if k not in ordered})
	return json.dumps(ordered, indent=2, ensure_ascii=False)


def italic_summary(doc):
	'''One line: angle source and the italic fix switches that are on.'''
	adv = doc.get('advanced') or ADVANCED_DEFAULTS
	source = adv.get('italic', 'master')
	angle = {'master': 'master angle', 'none': 'upright (no angle)'}.get(
		source, 'custom %g deg' % _num(adv.get('italic_angle'), 0.))
	fix = italic_fix(doc)
	titles = dict((k, t) for k, t, _h in dpa.ITALIC_FIX_SWITCHES)
	on = [titles[k].lower() for k, _t, _h in dpa.ITALIC_FIX_SWITCHES if fix.get(k)]
	if not fix.get('keep_directions'):
		on = [t for t in on if t == titles['italic_tan'].lower()]	# the rest needs Lock directions
	numbers = ', '.join('%s %g' % (t.lower(), fix[k]) for k, t, _h in dpa.ITALIC_FIX_NUMBERS) \
		if fix.get('keep_directions') else ''
	return '%s; fix %s%s' % (angle, ', '.join(on) if on else 'off', ' (%s)' % numbers if numbers else '')


# - Bake log ---------------------------------------------------------------
def worst_status(a, b):
	'''The worse of two glyph statuses (STATUSES order; None = not set).'''
	if a is None:
		return b
	return a if STATUSES.index(a) >= STATUSES.index(b or 'done') else b


def log_file_name(family, stamp):
	'''<Family>-delta-machine-<YYYYMMDD-HHMMSS>.log; stamp: a datetime.'''
	safe = ''.join(c for c in (family or 'font') if c.isalnum() or c in '-_') or 'font'
	return '%s-delta-machine-%s.log' % (safe, stamp.strftime('%Y%m%d-%H%M%S'))


def _wrapped(names, width=96, indent='  '):
	lines, line = [], ''
	for name in names:
		if line and len(line) + 1 + len(name) > width:
			lines.append(indent + line)
			line = name
		else:
			line = (line + ' ' + name) if line else name
	if line:
		lines.append(indent + line)
	return lines


def machine_log(doc, run):
	'''Text of a bake log. run (the engine fills it):
		started (str), seconds (float), font {'family', 'version', 'file'},
		app (str), jobs [{'layer', 'glyphs', 'composites'}],
		glyphs {name: {'status', 'notes': [str]}} in bake order,
		warnings [str] (not tied to one glyph), summary (str).'''
	font = run.get('font') or {}
	glyphs = run.get('glyphs') or {}
	by_status = {s: [n for n, g in glyphs.items() if g['status'] == s] for s in STATUSES}
	opts = doc.get('options', OPTION_DEFAULTS)
	out = ['%s %s — bake log' % (TOOL, VERSION), '',
	       'Date:     %s (%.1f s)' % (run.get('started', ''), run.get('seconds', 0.)),
	       'Font:     %s %s%s' % (font.get('family') or '(no family name)', font.get('version', ''),
	                              ' (%s)' % font['file'] if font.get('file') else ' (not saved)')]
	if run.get('app'):
		out.append('App:      %s' % run['app'])
	out.append('Options:  extrapolate %s, selected only %s, skip composites %s' % (
		'on' if opts.get('extrapolate', True) else 'off', 'on' if opts.get('selection_only') else 'off',
		'on' if opts.get('skip_composites', True) else 'off'))
	out.append('Italic:   %s' % italic_summary(doc))

	out += ['', 'Setup']
	for ax in doc.get('axes', []):
		out.append('  Axis "%s": inputs %s' % (ax['name'], ', '.join(
			'%s (V %s / H %s)' % (r['name'], '%g' % _num(r['vstem'], 0.), '%g' % _num(r['hstem'], 0.)) for r in ax['inputs'])
			or 'none'))
		for t in ax['targets']:
			out.append('    %s / %s: V %g, H %g, width %s, height %s, origin %s%s%s' % (
				t['layer'], t['group'] or SELECTION_LABEL, _num(t['vstem'], 0.), _num(t['hstem'], 0.),
				format_dimension(t['width']), format_dimension(t['height']),
				dict(ORIGIN_LABELS).get(t.get('origin', 'BS'), t.get('origin', 'BS')),
				'' if t['anchors'] else ', no anchors',
				', metrics %s' % format_metrics_scale(t['msx']) if t['metrics'] and t.get('msx') is not None
				else '' if t['metrics'] else ', no metrics'))

	out += ['', 'Jobs']
	for i, job in enumerate(run.get('jobs', [])):
		out.append('  %d/%d %s: %d glyph(s)%s' % (i + 1, len(run['jobs']), job['layer'], job['glyphs'],
		                                         ', %d composite(s)' % job['composites'] if job.get('composites') else ''))
	if not run.get('jobs'):
		out.append('  none')

	out += ['', 'Result: %d glyph(s): %d done, %d with warnings, %d failed' % (
		len(glyphs), len(by_status['done']), len(by_status['warning']), len(by_status['failed']))]
	if run.get('summary'):
		out.append('  ' + run['summary'])
	for status in ('failed', 'warning'):
		if by_status[status]:
			out += ['', '%s (%d)' % (STATUS_LABELS[status], len(by_status[status]))]
			for name in by_status[status]:
				notes = glyphs[name]['notes'] or ['(no reason given)']
				out.append('  %s: %s' % (name, notes[0]))
				out.extend('  %s  %s' % (' ' * len(name), n) for n in notes[1:])
	if by_status['done']:
		out += ['', '%s (%d)' % (STATUS_LABELS['done'], len(by_status['done']))]
		out += _wrapped(by_status['done'])
	if run.get('warnings'):
		out += ['', 'Other warnings (%d)' % len(run['warnings'])]
		out += ['  ' + w for w in run['warnings']]
	return '\n'.join(out) + '\n'
