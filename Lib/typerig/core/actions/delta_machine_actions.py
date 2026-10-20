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
Axes and targets are apart (format 5): an axis is a set of input layers
with their stems (Weight lc: Regular 80 / Bold 160), a target row names the
axis it is computed from, so the lowercase and the capitals of one layer
can use different axes. A row without a group works on the selected
glyphs. A row may name several
groups, or All groups (every group of the document, also groups added
later); an override row under it changes the values for one of its groups
and inherits the cells it leaves empty (format 4). Width and height are
in percent (default) or in units, each on its own: 60 % wide and exactly
700 units high is one row. Units are measured on the group's reference
glyph when it has one (the scale found there is used for the whole group,
so overshoots and descenders keep their proportions), else on each glyph.

This module is host neutral: the document (normalize, validate), unit
parsing, machine_expand (rows -> one resolved row per group, overrides
first) and the plan that turns the rows into one core Delta setup per
glyph (delta_panel_actions.npa_delta_bake / npa_delta_solve_target).
'''

from __future__ import absolute_import, print_function

import copy
import json

from typerig.core.actions import delta_panel_actions as dpa
from typerig.core.actions import designspace_actions as dsa

# - Init -------------------------------------------------------------------
TOOL       = 'TypeRig Delta Machine'
VERSION    = '0.6'
FORMAT     = 5				# 5 (v0.6): axes hold inputs only; 'targets' at document level, each row names its 'axis'
							# (inheritable); 4 axes with targets read as rows of that axis.
							# 4 (v0.5): target 'groups' (list, '*' = all), 'id', 'parent', 'inherit'; 3 'group' reads
							# as a one-group row. 3 (v0.4): flag_* are Glyphs label colour indexes (1 / 2: RGBA ->
							# nearest label); optional target 'msx'. 2 (v0.3): advanced.italic_fix. 1 reads as 3 (fix off)
LIB_KEY    = 'com.typerig.delta.machine.setup'		# font lib; the panel keys are in core/base/lib_keys.py
SELECTION  = ''				# group of a row that works on the selected glyphs
SELECTION_LABEL = 'Selection'
ALL_GROUPS = '*'			# in a row's groups: every group of the document (also ones added later)
ALL_GROUPS_LABEL = 'All groups'
INHERIT_KEYS = ('axis', 'vstem', 'hstem', 'width', 'height', 'origin', 'anchors', 'metrics', 'msx', 'kerning')
INHERIT_MARK = '\u200b'		# leads a table cell value inherited from the general row (shown grey)
OVERRIDE_MARK = '\u21b3'	# Layer cell of an override row (its layer is the general row's)
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
	'layer': '', 'axis': '',	# axis: name of the axis the row is computed from
	'groups': [],				# [] = Selection, ['*'] = all groups, else group names
	'id': '', 'parent': '',		# parent: id of the general row an override row belongs to
	'inherit': [],				# override row: INHERIT_KEYS taken from the general row
	'vstem': 100., 'hstem': 100.,
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
	group = (row['group'] or SELECTION_LABEL) if 'group' in row else groups_label(row)
	text = '%s / %s: %s x %s' % (row['layer'], group,
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
		'axes': [],					# [{'name', 'inputs'}]
		'targets': [],				# target rows (norm_target), each names its axis
		'groups': [],
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
	out['axis'] = str(row.get('axis', '') or '').strip()
	out['groups'] = norm_groups(row.get('groups') if 'groups' in row else row.get('group', SELECTION))
	out['id'] = str(row.get('id', '') or '').strip()
	out['parent'] = str(row.get('parent', '') or '').strip()
	out['inherit'] = [k for k in INHERIT_KEYS if k in (row.get('inherit') or [])]
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


def norm_groups(value):
	'''A row's groups: list of names, ['*'] (all groups) or [] (Selection).
	Reads format 3 (one name, '' = Selection).'''
	if value is None or isinstance(value, (str, bytes)):
		value = [value] if value else []
	out = []
	for g in value:
		g = str(g or '').strip()
		if g and g not in out:
			out.append(g)
	return [ALL_GROUPS] if ALL_GROUPS in out else out


def groups_label(row):
	'''Group cell text: Selection, All groups, or the names.'''
	groups = row.get('groups', [])
	if not groups:
		return SELECTION_LABEL
	if groups == [ALL_GROUPS]:
		return ALL_GROUPS_LABEL
	return ', '.join(groups)


def covers(row, group, doc_groups=None):
	'''Does a row take group (a name; SELECTION = the selection)?'''
	groups = row.get('groups', [])
	if group == SELECTION:
		return not groups
	if groups == [ALL_GROUPS]:
		return doc_groups is None or group in doc_groups
	return group in groups


def overlap(a, b):
	'''Two groups lists take a common group (Selection only meets Selection).'''
	if not a or not b:
		return not a and not b
	if ALL_GROUPS in a or ALL_GROUPS in b:
		return True
	return bool(set(a) & set(b))


def is_override(row):
	return bool(row.get('parent'))


def resolve(row, parent):
	'''An override row with its inherited cells taken from the general row.'''
	out = copy.deepcopy(row)
	if parent is not None:
		for key in row.get('inherit', []):
			out[key] = copy.deepcopy(parent[key])
	return out


def new_row_id(targets):
	'''An id no row of targets has ('r1', 'r2', ...).'''
	used = set(t.get('id') for t in targets)
	n = 1
	while 'r%d' % n in used:
		n += 1
	return 'r%d' % n


def target_tree(targets):
	'''Rows ordered general row, then its overrides; ids unique (rows
	without overrides may have none: new_row_id gives one when needed);
	an override whose general row is missing (or is an override itself, or
	has no group to override) becomes a general row with its own values.'''
	used = set()
	for t in targets:
		if t['id'] in used:
			t['id'] = new_row_id(targets)
		if t['id']:
			used.add(t['id'])
	by_id = dict((t['id'], t) for t in targets)
	for t in targets:
		p = by_id.get(t['parent'])
		if not t['parent']:
			t['inherit'] = []
		elif p is None or p['parent'] or not p['groups'] or len(t['groups']) != 1 or t['groups'] == [ALL_GROUPS] \
				or not covers(p, t['groups'][0]) or p is t:
			t['parent'], t['inherit'] = '', []
	for t in targets:		# a second pass: a demoted general row may have been someone's parent
		if t['parent'] and by_id[t['parent']]['parent']:
			t['parent'], t['inherit'] = '', []
	out = []
	for t in targets:
		if not t['parent']:
			out.append(t)
			for c in targets:
				if c['parent'] and c['parent'] == t['id']:
					c['layer'] = t['layer']
					out.append(c)
	return out


def machine_expand(doc):
	'''The document as the bake sees it (the core Delta shape): every axis
	with the resolved rows computed from it. Each target row becomes one row
	per group (All groups = the document's groups; a group with an override
	row is left to it; Selection rows stay one row), inherited cells filled
	in, put under the axis it names. Expanded rows carry 'group' (one name,
	SELECTION), 'source' (index in doc['targets']) and 'rank' (0 override,
	1 named group, 2 Selection: machine_plan takes the lowest first).
	Rows of an unknown axis are left out (machine_validate names them).'''
	out = copy.deepcopy(doc)
	names = [g['name'] for g in doc.get('groups', [])]
	axes = dict((ax['name'], ax) for ax in out.get('axes', []))
	for ax in out.get('axes', []):
		ax['targets'] = []
	rows = doc.get('targets', [])
	by_id = dict((t['id'], t) for t in rows if t.get('id'))
	overridden = {}

	def put(row, group, i, rank):
		ax = axes.get(row.get('axis'))
		if ax is not None:
			ax['targets'].append(dict(row, group=group, source=i, rank=rank))

	for i, t in enumerate(rows):
		p = by_id.get(t.get('parent'))
		if t.get('parent') and p is not None:
			overridden.setdefault(p['id'], set()).add(t['groups'][0])
			put(resolve(t, p), t['groups'][0], i, 0)
	for i, t in enumerate(rows):
		if t.get('parent') and t['parent'] in by_id:
			continue
		groups = t.get('groups', [])
		if not groups:
			put(copy.deepcopy(t), SELECTION, i, 2)
			continue
		for g in (names if groups == [ALL_GROUPS] else groups):
			if g not in overridden.get(t.get('id'), ()):
				put(copy.deepcopy(t), g, i, 1)
	out['expanded'] = True
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
		name = unique_axis_name(ax['name'], doc['axes'])
		for t in ax['targets']:
			row = norm_target(dict(t, layer=t['name'], axis=name), origin=opts.get('origin', 'BS'))
			row['anchors'], row['metrics'] = bool(opts.get('anchors', True)), bool(opts.get('metrics', True))
			doc['targets'].append(row)
		doc['axes'].append({'name': name,
		                    'inputs': [{'name': r['name'], 'vstem': r['vstem'], 'hstem': r['hstem']} for r in ax['inputs']]})
	doc['targets'] = target_tree(doc['targets'])
	return doc


def unique_axis_name(name, axes):
	'''name, or "name 2", "name 3"... when an axis has it ('' -> "Axis").'''
	base = (name or '').strip() or 'Axis'
	used = set(a['name'] for a in axes)
	name, n = base, 1
	while name in used:
		n += 1
		name = '%s %d' % (base, n)
	return name


def _merge_rows(targets, rows):
	'''Append rows (one format 4 axis, tree-ordered) to targets; their ids
	are renamed where targets has them, parents follow.'''
	used = set(t['id'] for t in targets if t['id'])
	renamed = {}
	for t in rows:
		if t['id'] and t['id'] in used:
			new = new_row_id(targets + rows)
			renamed[t['id']] = new
			t['id'] = new
		if t['id']:
			used.add(t['id'])
	for t in rows:
		if t['parent'] in renamed:
			t['parent'] = renamed[t['parent']]
	targets.extend(rows)


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
	origin = doc['options']['origin']
	for ax in raw.get('axes', []) or []:
		if not isinstance(ax, dict):
			continue
		inputs = []
		for r in ax.get('inputs', []) or []:
			if isinstance(r, dict) and r.get('name'):
				inputs.append({'name': str(r['name']), 'vstem': _num(r.get('vstem'), r.get('vstem')),
				               'hstem': _num(r.get('hstem'), r.get('hstem'))})
		name = unique_axis_name(str(ax.get('name', '') or ''), doc['axes'])
		doc['axes'].append({'name': name, 'inputs': inputs})
		if ax.get('targets'):		# format 4 and older: the axis' rows are computed from it
			rows = [norm_target(dict(t, axis=name), origin=origin) for t in ax['targets'] if isinstance(t, dict)]
			_merge_rows(doc['targets'], target_tree(rows))
	doc['targets'].extend(norm_target(t, origin=origin) for t in raw.get('targets', []) or [] if isinstance(t, dict))
	doc['targets'] = target_tree(doc['targets'])
	doc['groups'] = [g for g in (norm_group(g) for g in raw.get('groups', []) or []) if g is not None]
	doc['designspace'] = dsa.plan_normalize(raw.get('designspace'))
	return doc


def machine_validate(doc):
	'''Errors that stop a bake (empty list = ready). doc: the document
	(not expanded); the values are checked as the bake sees them.'''
	errors = []
	groups = {}
	for g in doc.get('groups', []):
		if g['name'] in groups or g['name'] in (SELECTION_LABEL, ALL_GROUPS_LABEL, ALL_GROUPS):
			errors.append('Group names must be unique and not "%s" or "%s": %s.' % (
				SELECTION_LABEL, ALL_GROUPS_LABEL, g['name']))
		groups[g['name']] = g
	axis_names = [ax['name'] for ax in doc.get('axes', [])]
	for i, name in enumerate(axis_names):
		if not name or name in axis_names[:i]:
			errors.append('Axis names must be unique and not empty: "%s".' % name)
	rows = [] if doc.get('expanded') else doc.get('targets', [])
	by_id = dict((t['id'], t) for t in rows if t.get('id'))
	for i, t in enumerate(rows):
		if not t['layer']:
			errors.append('A target row has no layer name.')
		axis = resolve(t, by_id.get(t.get('parent')))['axis'] if is_override(t) else t['axis']
		if axis not in axis_names:
			errors.append('%s / %s: %s.' % (t['layer'], groups_label(t),
			                                 'unknown axis "%s"' % axis if axis else 'no axis (Set axis…)'))
		for g in t.get('groups', []):
			if g != ALL_GROUPS and g not in groups:
				errors.append('%s: unknown group "%s".' % (t['layer'], g))
		for j in range(i):
			u = rows[j]
			if u['layer'] != t['layer'] or is_override(u) != is_override(t):
				continue
			if is_override(t) and u['parent'] == t['parent'] and u['groups'] == t['groups']:
				errors.append('%s: two override rows for %s.' % (t['layer'], t['groups'][0]))
			elif not is_override(t) and overlap(u['groups'], t['groups']):
				errors.append('%s: rows "%s" and "%s" take the same glyphs; use an override row.' % (
					t['layer'], groups_label(u), groups_label(t)))
	xdoc = doc if doc.get('expanded') else machine_expand(doc)
	core_axes = [{'name': ax['name'], 'inputs': ax['inputs'],
	              'targets': [{'name': '%s / %s' % (t['layer'], t['group'] or SELECTION_LABEL)} for t in ax['targets']]}
	             for ax in xdoc.get('axes', [])]
	errors.extend(dpa.delta_setup_validate({'axes': core_axes}))
	for ax in xdoc.get('axes', []):
		for t in ax['targets']:
			for key in ('vstem', 'hstem'):
				if _num(t[key], 0.) <= 0:
					errors.append('Axis "%s" / %s: %s must be > 0.' % (ax['name'], t['layer'], key))
			for key in ('width', 'height'):
				if t[key]['value'] <= 0:
					errors.append('Axis "%s" / %s: %s must be > 0.' % (ax['name'], t['layer'], key))
			if t.get('msx') is not None and t['msx'] <= 0:
				errors.append('Axis "%s" / %s: metrics scale must be > 0.' % (ax['name'], t['layer']))
	return [e for i, e in enumerate(errors) if e not in errors[:i]]	# one per expanded group otherwise


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

	Works on the expanded document (machine_expand; a plain document is
	expanded here): row indexes are those of the expanded rows, each with
	one group and 'source' = the row in the document. Per glyph and (axis,
	layer) the first matching row wins: override rows, then rows with a
	named group, then Selection rows. Returns
	  {'glyphs': {glyph: [(axis_index, row_index), ...]},   # in font order of first appearance
	   'refs':   [{'axis', 'row', 'glyph'}],               # units rows solved on a reference glyph
	   'warnings': [...],
	   'doc': the expanded document (for core_setup / ref_setup)}'''
	if not doc.get('expanded'):
		doc = machine_expand(doc)
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

	# One order for every axis (a layer's rows may use different axes):
	# override rows, then named groups, then Selection; table order inside.
	axes = doc.get('axes', [])
	rows = [(r.get('rank', 1 if r['group'] else 2), r.get('source', i), a, i, r)
	        for a, ax in enumerate(axes) for i, r in enumerate(ax['targets'])]
	rows.sort(key=lambda x: (x[0], x[1]))
	taken = {}		# (glyph, layer) -> (axis index, row index)
	overlaps = {}
	for _rank, _src, a, i, row in rows:
		names = members(row)
		if not names:
			continue
		group = groups.get(row['group'])
		if group is not None and has_units(row):
			if not group['reference']:
				warnings.append('%s / %s: size in units, but the group has no reference glyph (Groups tab, Ref.); '
				                'each glyph is measured on its own.' % (row['layer'], row['group']))
			elif existing is None or group['reference'] in existing:
				refs.append({'axis': a, 'row': i, 'glyph': group['reference']})
			else:
				warnings.append('Group "%s": reference glyph %s is not in the font; each glyph is measured on its own.'
				                % (row['group'], group['reference']))
		for name in names:
			key = (name, row['layer'])
			if key in taken:
				fa, fi = taken[key]
				first = axes[fa]['targets'][fi]
				if row['group'] and first['group'] != row['group']:
					overlaps.setdefault((row['layer'], first['group'], row['group']), []).append(name)
				continue
			taken[key] = (a, i)
			if name not in picks:
				picks[name] = []
				order.append(name)
			picks[name].append((a, i))
	for (layer, first, second), names in overlaps.items():
		warnings.append('%s: %d glyph(s) in both "%s" and "%s" (first row wins): %s'
		                % (layer, len(names), first, second, ' '.join(names[:8])))
	if missing:
		warnings.append('%d group glyph(s) not in the font: %s' % (len(missing), ' '.join(sorted(missing)[:8])))
	return {'glyphs': {name: picks[name] for name in order}, 'refs': refs, 'warnings': warnings, 'doc': doc}


def core_setup(doc, picks, solved=None, italic_angle=0.):
	'''Core Delta setup for one glyph. picks: [(axis_index, row_index)]
	from machine_plan; solved: {(axis_index, row_index): (sx %, sy %)}
	from the reference pass. doc: the expanded document (machine_plan's
	'doc'); a plain document is expanded here.'''
	if not doc.get('expanded'):
		doc = machine_expand(doc)
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
	'''Core setup of the reference pass: one axis, the one units row
	(ref indexes the expanded document, as machine_plan gives it).'''
	if not doc.get('expanded'):
		doc = machine_expand(doc)
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

	out += ['', 'Axes']
	for ax in doc.get('axes', []):
		out.append('  %s: inputs %s' % (ax['name'], ', '.join(
			'%s (V %s / H %s)' % (r['name'], '%g' % _num(r['vstem'], 0.), '%g' % _num(r['hstem'], 0.)) for r in ax['inputs'])
			or 'none'))
	out += ['', 'Targets']
	by_id = dict((t['id'], t) for t in doc.get('targets', []) if t.get('id'))
	for t in doc.get('targets', []):
		parent = by_id.get(t.get('parent'))
		label = '%s / %s' % (t['layer'], groups_label(t))
		if parent is not None:
			label = '    %s (override of %s%s)' % (label, groups_label(parent),
			                                    '; own: ' + ', '.join(k for k in INHERIT_KEYS if k not in t['inherit'])
			                                    if len(t['inherit']) < len(INHERIT_KEYS) else '; all inherited')
			t = resolve(t, parent)
		out.append('  %s: axis %s, V %g, H %g, width %s, height %s, origin %s%s%s' % (
			label, t['axis'] or '(none)', _num(t['vstem'], 0.), _num(t['hstem'], 0.),
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
