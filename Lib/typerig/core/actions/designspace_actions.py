# MODULE: TypeRig / Core / Actions / Design space plan
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
'''Design space plan: axes and masters, edited away from the font and
applied in one step (Delta Machine, Designspace tab).

Axes are defined as in FontLab (name, tag, minimum / default / maximum)
and may be driven: the coordinate of a master on a driven axis comes from
its stems or its width / height percent in the Delta setup, so a Weight
axis can simply be the V stem. Masters are rows with one coordinate per
axis; a master is in the font, new (empty, copy of a master, or made from
a Delta target layer), or marked for removal.

Host neutral. The host reads the font into a plan (axes / masters with
their font ids), the user edits it, plan_diff() lists what applying would
change, the host applies it.

Plan shape:
  {'axes':    [{'key', 'id', 'name', 'tag', 'min', 'default', 'max',
                'driver', 'hidden'}],
   'masters': [{'key', 'id', 'name', 'source': {'kind', 'from'},
                'location': {axis key: float}, 'default': bool,
                'remove': bool}]}
  axis 'key' / master 'key': stable within the plan (renames keep them);
  'id': the font's axisId / master id ('' = not in the font yet);
  source kind: 'font' (in the font), 'copy' (from: master name), 'target'
  (from: target layer name; the layers of every glyph are copied),
  'empty'; driver: see DRIVERS.
'''

from __future__ import absolute_import, print_function

import copy

# - Init -------------------------------------------------------------------
DRIVERS = (	# (key, label) — where a driven axis takes a master's coordinate
	('manual', 'Manual'),
	('vstem',  'V stem'),
	('hstem',  'H stem'),
	('width',  'Width %'),
	('height', 'Height %'),
)
DRIVER_KEYS = tuple(k for k, _ in DRIVERS)
DRIVER_MARKS = {'manual': '', 'vstem': 'V', 'hstem': 'H', 'width': 'W%', 'height': 'H%'}	# short, for column titles

REGISTERED = {	# tag -> (name, min, default, max) for new axes
	'wght': ('Weight', 100., 400., 900.),
	'wdth': ('Width', 50., 100., 200.),
	'opsz': ('Optical size', 6., 12., 72.),
	'ital': ('Italic', 0., 0., 1.),
	'slnt': ('Slant', -15., 0., 0.),
}

SOURCE_KINDS = ('font', 'copy', 'target', 'empty')


def _num(value, default=None):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _new_key(prefix, used):
	n = 1
	while '{}{}'.format(prefix, n) in used:
		n += 1
	return '{}{}'.format(prefix, n)


# - Plan -------------------------------------------------------------------
def plan_new():
	return {'axes': [], 'masters': []}


def norm_axis(axis, used_keys=()):
	axis = dict(axis or {})
	tag = str(axis.get('tag', '') or '')[:4]
	name = str(axis.get('name', '') or '').strip()
	reg = REGISTERED.get(tag)
	lo = _num(axis.get('min'), reg[1] if reg else 0.)
	hi = _num(axis.get('max'), reg[3] if reg else 1000.)
	df = _num(axis.get('default'), reg[2] if reg else lo)
	driver = axis.get('driver', 'manual')
	return {'key': axis.get('key') or _new_key('a', used_keys), 'id': str(axis.get('id', '') or ''),
	        'name': name or (reg[0] if reg else 'Axis'), 'tag': tag,
	        'min': lo, 'default': df, 'max': hi,
	        'driver': driver if driver in DRIVER_KEYS else 'manual', 'hidden': bool(axis.get('hidden', False))}


def norm_master(master, axis_keys, used_keys=()):
	master = dict(master or {})
	source = dict(master.get('source') or {})
	kind = source.get('kind', 'font' if master.get('id') else 'empty')
	location = master.get('location') or {}
	return {'key': master.get('key') or _new_key('m', used_keys), 'id': str(master.get('id', '') or ''),
	        'name': str(master.get('name', '') or '').strip() or 'Master',
	        'source': {'kind': kind if kind in SOURCE_KINDS else 'empty', 'from': str(source.get('from', '') or '')},
	        'location': {k: _num(location.get(k), 0.) for k in axis_keys},
	        'default': bool(master.get('default', False)), 'remove': bool(master.get('remove', False))}


def plan_normalize(raw):
	'''Any stored plan -> the current shape (keys filled, locations per axis).'''
	plan = plan_new()
	if not isinstance(raw, dict):
		return plan
	for axis in raw.get('axes', []) or []:
		plan['axes'].append(norm_axis(axis, {a['key'] for a in plan['axes']}))
	keys = [a['key'] for a in plan['axes']]
	for master in raw.get('masters', []) or []:
		plan['masters'].append(norm_master(master, keys, {m['key'] for m in plan['masters']}))
	return plan


def add_axis(plan, tag='', name=''):
	'''A new axis; registered tags (wght, wdth, ...) get their FontLab-style
	defaults. Masters get the axis default as their coordinate.'''
	used_names = {a['name'] for a in plan['axes']}
	used_tags = {a['tag'] for a in plan['axes']}
	if not tag:
		tag = next((t for t in REGISTERED if t not in used_tags), '')
	if not tag or tag in used_tags:
		n = 1
		while 'ax{:02d}'.format(n) in used_tags:
			n += 1
		tag = 'ax{:02d}'.format(n)
	axis = norm_axis({'tag': tag, 'name': name}, {a['key'] for a in plan['axes']})
	base, n = axis['name'], 1
	while axis['name'] in used_names:
		n += 1
		axis['name'] = '{} {}'.format(base, n)
	plan['axes'].append(axis)
	for m in plan['masters']:
		m['location'][axis['key']] = axis['default']
	return axis


def remove_axis(plan, key):
	plan['axes'] = [a for a in plan['axes'] if a['key'] != key]
	for m in plan['masters']:
		m['location'].pop(key, None)


def add_master(plan, name, kind='empty', source_from='', location=None):
	used = {m['name'] for m in plan['masters']}
	base, n, unique = name or 'Master', 1, name or 'Master'
	while unique in used:
		n += 1
		unique = '{} {}'.format(base, n)
	keys = [a['key'] for a in plan['axes']]
	loc = dict((a['key'], a['default']) for a in plan['axes'])
	loc.update(location or {})
	master = norm_master({'name': unique, 'source': {'kind': kind, 'from': source_from}, 'location': loc},
	                     keys, {m['key'] for m in plan['masters']})
	if not plan['masters']:
		master['default'] = True
	plan['masters'].append(master)
	return master


# - Driven coordinates -------------------------------------------------------
def master_layer(master):
	'''The layer whose stems drive a master: its own name (in the font, or a
	copy of a master: that master), or the target layer it is made from.'''
	kind, src = master['source']['kind'], master['source']['from']
	if kind == 'target':
		return src
	if kind == 'copy':
		return src
	return master['name']


def driven_locations(plan, measures):
	'''Coordinates of driven axes. measures: callable(layer name) ->
	{'vstem', 'hstem', 'width', 'height'} (any missing / None = unknown).
	Returns {master key: {axis key: value}} for the driven axes it could
	fill; manual axes are not listed.'''
	out = {}
	for m in plan['masters']:
		values = measures(master_layer(m)) or {}
		for a in plan['axes']:
			if a['driver'] == 'manual':
				continue
			v = _num(values.get(a['driver']))
			if v is not None:
				out.setdefault(m['key'], {})[a['key']] = v
	return out


def resolved(plan, measures=None):
	'''Plan copy with driven coordinates filled in (manual ones as stored).'''
	plan = copy.deepcopy(plan)
	if measures is not None:
		for mkey, values in driven_locations(plan, measures).items():
			for m in plan['masters']:
				if m['key'] == mkey:
					m['location'].update(values)
	return plan


def fit_range(plan, axis_key, measures):
	'''Set a driven axis' range to its masters: min / max = the span of the
	driven coordinates, default = the default master's. Returns True when
	the masters gave values.'''
	res = resolved(plan, measures)
	axis = next(a for a in plan['axes'] if a['key'] == axis_key)
	live = [m for m in res['masters'] if not m['remove']]
	values = [m['location'][axis_key] for m in live if axis_key in m['location']]
	if not values:
		return False
	axis['min'], axis['max'] = min(values), max(values)
	default = next((m['location'][axis_key] for m in live if m['default']), None)
	axis['default'] = default if default is not None else axis['min']
	return True


# - Checks -----------------------------------------------------------------
def master_status(plan):
	'''{master key: text} for the Status column: Default, Remove, a location
	shared with another master, coordinates outside an axis range.'''
	status = {}
	live = [m for m in plan['masters'] if not m['remove']]
	seen = {}
	for m in live:
		loc = tuple(round(m['location'].get(a['key'], 0.), 3) for a in plan['axes'])
		seen.setdefault(loc, []).append(m['name'])
	for m in plan['masters']:
		notes = []
		if m['remove']:
			notes.append('remove')
		else:
			if m['default']:
				notes.append('default')
			loc = tuple(round(m['location'].get(a['key'], 0.), 3) for a in plan['axes'])
			others = [n for n in seen.get(loc, []) if n != m['name']]
			if plan['axes'] and others:
				notes.append('same place as ' + ', '.join(others))
			for a in plan['axes']:
				v = m['location'].get(a['key'], 0.)
				if not a['min'] <= v <= a['max']:
					notes.append('{} {:g} outside {:g}..{:g}'.format(a['tag'] or a['name'], v, a['min'], a['max']))
		status[m['key']] = '; '.join(notes)
	return status


def plan_validate(plan):
	'''Errors that stop Apply (empty list = ready).'''
	errors = []
	names, tags = set(), set()
	for a in plan['axes']:
		if not a['name'] or a['name'] in names:
			errors.append('Axis names must be unique and not empty: "%s".' % a['name'])
		if len(a['tag']) != 4 or a['tag'] in tags:
			errors.append('Axis tags must be 4 characters and unique: "%s".' % a['tag'])
		if not a['min'] <= a['default'] <= a['max']:
			errors.append('Axis %s: minimum <= default <= maximum.' % a['name'])
		names.add(a['name'])
		tags.add(a['tag'])
	live = [m for m in plan['masters'] if not m['remove']]
	if not live:
		errors.append('The font needs at least one master.')
	mnames = set()
	for m in live:
		if m['name'] in mnames:
			errors.append('Master names must be unique: "%s".' % m['name'])
		mnames.add(m['name'])
		if m['source']['kind'] in ('copy', 'target') and not m['source']['from']:
			errors.append('Master %s: nothing to make it from.' % m['name'])
	if len([m for m in live if m['default']]) != 1:
		errors.append('Mark exactly one master as the default (variable font origin).')
	if plan['axes']:
		places = {}
		for m in live:
			loc = tuple(round(m['location'].get(a['key'], 0.), 3) for a in plan['axes'])
			if loc in places:
				errors.append('Masters %s and %s are at the same place.' % (places[loc], m['name']))
			places[loc] = m['name']
	return errors


def plan_diff(font_plan, plan):
	'''What applying plan to a font read as font_plan changes: a list of
	lines for the confirmation dialog.'''
	lines = []
	f_axes = {a['id']: a for a in font_plan['axes'] if a['id']}
	ids = {a['id'] for a in plan['axes'] if a['id']}
	for a in plan['axes']:
		old = f_axes.get(a['id'])
		if old is None:
			lines.append('Add axis %s (%s) %g / %g / %g' % (a['name'], a['tag'], a['min'], a['default'], a['max']))
		else:
			if (old['name'], old['tag']) != (a['name'], a['tag']):
				lines.append('Axis %s (%s) -> %s (%s)' % (old['name'], old['tag'], a['name'], a['tag']))
			if (old['min'], old['default'], old['max']) != (a['min'], a['default'], a['max']):
				lines.append('Axis %s range %g / %g / %g' % (a['name'], a['min'], a['default'], a['max']))
	for aid, old in f_axes.items():
		if aid not in ids:
			lines.append('Remove axis %s (%s)' % (old['name'], old['tag']))
	f_masters = {m['id']: m for m in font_plan['masters'] if m['id']}
	f_axis_by_id = {a['id']: a['key'] for a in font_plan['axes'] if a['id']}
	for m in plan['masters']:
		old = f_masters.get(m['id'])
		if m['remove']:
			if old is not None:
				lines.append('REMOVE master %s and all its layers and kerning' % old['name'])
			continue
		if old is None:
			how = {'copy': 'copy of %s' % m['source']['from'], 'target': 'from target layer %s' % m['source']['from'],
			       'empty': 'empty'}.get(m['source']['kind'], '')
			lines.append('Add master %s (%s)' % (m['name'], how))
			continue
		if old['name'] != m['name']:
			lines.append('Rename master %s -> %s' % (old['name'], m['name']))
		moves = []
		for a in plan['axes']:
			old_key = f_axis_by_id.get(a['id'])
			before = old['location'].get(old_key) if old_key else None
			after = m['location'].get(a['key'])
			if before is None or abs(before - after) > 1e-6:
				moves.append('%s %s -> %g' % (a['tag'] or a['name'], '-' if before is None else '%g' % before, after))
		if moves:
			lines.append('Move master %s: %s' % (m['name'], ', '.join(moves)))
	f_default = next((m['id'] for m in font_plan['masters'] if m['default']), None)
	new_default = next((m for m in plan['masters'] if m['default'] and not m['remove']), None)
	if new_default is not None and new_default['id'] != f_default:
		lines.append('Default master (variable font origin): %s' % new_default['name'])
	return lines


# - Core objects (.designspace files) ------------------------------------------
# Files are read / written by core fileio/designspace.py (fontTools
# designspaceLib) on the core Axis / Master objects; these convert the plan.
# Coordinates are design values (the file is written without <map>, so
# user = design; files with a <map> are read in design values).
def plan_to_core(plan):
	'''Plan -> ([Axis], [Master], warnings) for a .designspace. Live masters
	only. An axis default is the default master's coordinate (designspace
	rule) and its range is widened to every master.'''
	from typerig.core.objects.axis import Axis
	from typerig.core.objects.master import Master
	warnings = []
	live = [m for m in plan['masters'] if not m['remove']]
	default = next((m for m in live if m['default']), live[0] if live else None)
	axes = []
	for a in plan['axes']:
		values = [m['location'].get(a['key'], a['default']) for m in live]
		df = default['location'].get(a['key'], a['default']) if default is not None else a['default']
		if df != a['default']:
			warnings.append('Axis %s: default %g written as %g (the default master).' % (a['name'], a['default'], df))
		axes.append(Axis(name=a['name'], tag=a['tag'], minimum=min([a['min']] + values),
		                 default=df, maximum=max([a['max']] + values)))
	masters = [Master(name=m['name'], layer_name=m['name'], is_default=m is default,
	                  location={a['name']: m['location'].get(a['key'], a['default']) for a in plan['axes']})
	           for m in live]
	return axes, masters, warnings


def plan_from_core(axes, masters):
	'''[Axis], [Master] (e.g. read from a .designspace) -> plan. Masters
	are new ('empty', from = their layer name); the caller matches them to
	font masters.'''
	plan = plan_new()
	by_name = {}
	for axis in axes:
		a = norm_axis({'name': axis.name, 'tag': axis.tag, 'min': axis.minimum, 'default': axis.default,
		               'max': axis.maximum}, {x['key'] for x in plan['axes']})
		plan['axes'].append(a)
		by_name[axis.name] = a
	keys = [a['key'] for a in plan['axes']]
	for master in masters:
		location = {by_name[n]['key']: v for n, v in dict(master.location).items() if n in by_name}
		m = norm_master({'name': master.name, 'source': {'kind': 'empty', 'from': master.layer_name or ''},
		                 'location': dict((a['key'], a['default']) for a in plan['axes']), 'default': master.is_default},
		                keys, {x['key'] for x in plan['masters']})
		m['location'].update(location)
		plan['masters'].append(m)
	return plan
