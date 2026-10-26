# MODULE: TypeRig / Core / Actions / Delta Kerning
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
'''Delta Machine kerning: the kerning of a target layer from its axis inputs.

Kerning rides the same axis as the outlines. Per pair and per baked side:
the inputs' values are interpolated at the side's V stem on the side's
axis (piecewise linear, as the Delta engine reads the stems; a pair missing
in an input counts as 0), then scaled by the mean of the two sides' width
factors (the row's Met. W when set, else its outline width scale):

	k = mean(k_left_axis(t_left), k_right_axis(t_right)) * (f_left + f_right) / 2

Host neutral. A kerning table is {(left, right): value}; a key that starts
with '@' is a kerning group (the side follows from its place in the pair),
any other key is a glyph (an exception). The host translates its own keys
(Glyphs: @MMK_L_ / @MMK_R_, glyph ids). Groups are used as given: this
module never adds, renames or removes a group.

Rules (Delta Machine Advanced, user 2026-10-26):
- group rule, a group whose baked members differ (rows / sizes):
  mean (default) | key (the member named like the group, else the first
  baked member) | refuse (the pair is not written, the group is reported);
- side rule, a pair side with no baked glyph (glyph in no row, or a row
  with Kern off): complete (default; factor 1, the pair is still computed,
  so the master is complete) | skip (only pairs with both sides baked are
  written; others are removed from the target) | keep (the target's own
  value stays; for a new / lib target the same as skip).
Pairs in the target that no input has are the user's own: never touched.
LTR only (RTL and vertical: later).
'''

from __future__ import absolute_import, print_function

from typerig.core.actions.delta_panel_actions import _axis_time

# - Init -------------------------------------------------------------------
LIB_KEY = 'com.typerig.delta.machine.kerning'	# font lib: kerning of targets that are not masters yet
LIB_FORMAT = 1
GROUP_RULES = (('mean', 'Mean of members'), ('key', 'Group key glyph'), ('refuse', 'Refuse (report)'))
SIDE_RULES = (('complete', 'Complete (factor 1)'), ('skip', 'Skip the pair'), ('keep', 'Keep existing'))
GROUP_RULE_DEFAULT = 'mean'
SIDE_RULE_DEFAULT = 'complete'
LEFT, RIGHT = 'left', 'right'
_REFUSED = object()


def is_group(key):
	return str(key).startswith('@')


def group_name(key):
	return str(key)[1:]


def group_key(name):
	return '@' + name


# - Factors ----------------------------------------------------------------
def side_factor(row, solved=None, scales=None):
	'''Width factor of a glyph baked on a resolved target row (1. = 100 %):
	the row's Met. W when set (spacing follows it), else the scale solved
	on the group's reference glyph, else the glyph's own solved scale
	(units row, core bake entry 'scales'), else the row's width percent.'''
	if row.get('msx') is not None:
		return float(row['msx']) / 100.
	if solved is not None:
		return float(solved[0]) / 100.
	if scales:
		return float(scales[0]) / 100.
	width = row.get('width') or {}
	if width.get('unit', '%') == '%':
		return float(width.get('value', 100.)) / 100.
	return 1.


def spot(row, axis, factor):
	'''A baked side: {'axis': axis name, 'vstem', 'factor'}.'''
	return {'axis': axis, 'vstem': float(row['vstem']), 'factor': float(factor)}


# - Interpolation ----------------------------------------------------------
def axis_value(inputs, tables, pair, vstem, extrapolate=True):
	'''Value of pair at vstem on an axis: the inputs' values (0 where an
	input lacks the pair or has no table) piecewise linear by V stem, in
	input order, extrapolated past the ends unless extrapolate is off.'''
	values = [float((tables.get(r['name']) or {}).get(pair, 0.)) for r in inputs]
	if not values:
		return 0.
	if len(values) == 1:
		return values[0]
	stems = [float(r['vstem']) for r in inputs]
	t = _axis_time(stems, float(vstem))
	if t is None:
		return values[0]
	if not extrapolate:
		t = min(max(t, 0.), len(values) - 1.)
	i = min(max(int(t // 1), 0), len(values) - 2)
	f = t - i
	return values[i] + (values[i + 1] - values[i]) * f


# - Sides ------------------------------------------------------------------
def _key_member(name, members, baked):
	if name in baked:
		return name
	return next((m for m in members if m in baked), None)


def side_spots(key, side, groups, sides, bases=None, rule=GROUP_RULE_DEFAULT):
	'''Baked spots of one pair side. key: '@group' or a glyph; side: LEFT
	(groups[LEFT]: the glyphs' right-side groups) or RIGHT. sides: {glyph:
	spot} of the glyphs baked in this target with Kern on. bases: {glyph:
	first component} — an exception on a composite uses its base glyph.
	Returns a list of spots, [] (no baked glyph: unprocessed) or _REFUSED.'''
	if is_group(key):
		name = group_name(key)
		members = (groups.get(side) or {}).get(name, [])
		baked = [m for m in members if m in sides]
		if not baked:
			return []
		found = [sides[m] for m in baked]
		if len(set((s['axis'], s['vstem'], s['factor']) for s in found)) <= 1:
			return found[:1]
		if rule == 'key':
			return [sides[_key_member(name, members, set(baked))]]
		if rule == 'refuse':
			return _REFUSED
		return found
	if key in sides:
		return [sides[key]]
	base = (bases or {}).get(key)
	return [sides[base]] if base in sides else []


def _mean(values):
	return sum(values) / float(len(values))


# - Target -----------------------------------------------------------------
def kern_target(axes, tables, sides, groups, bases=None, fallback=None,
                group_rule=GROUP_RULE_DEFAULT, side_rule=SIDE_RULE_DEFAULT, extrapolate=True):
	'''Kerning of one target layer.

	axes: {axis name: [{'name', 'vstem'}]} the inputs of every axis used;
	tables: {input layer name: {(left, right): value}};
	sides: {glyph: spot} baked in this target (Kern on);
	groups: {LEFT: {name: [glyphs]}, RIGHT: {name: [glyphs]}};
	bases: {composite: base glyph} for exceptions;
	fallback: spot of the target's first row (factor 1), for pairs with no
	baked side under the complete rule.

	Every pair of any input is computed or reported. Returns
	  {'pairs': {(l, r): value},       # to write (rounded)
	   'remove': [(l, r)],             # skip rule: pairs with an unprocessed side
	   'keep': [(l, r)],               # keep rule: the target's own value stays
	   'refused': {'@group': n pairs}, # group rule refuse
	   'counts': {'scaled', 'completed', 'skipped', 'kept', 'refused'}}'''
	universe = set()
	for name in set(r['name'] for inputs in axes.values() for r in inputs):
		universe.update((tables.get(name) or {}).keys())
	cache = {}

	def value(pair, s):
		k = (pair, s['axis'], s['vstem'])
		if k not in cache:
			cache[k] = axis_value(axes.get(s['axis'], []), tables, pair, s['vstem'], extrapolate)
		return cache[k]

	out = {'pairs': {}, 'remove': [], 'keep': [], 'refused': {},
	       'counts': {'scaled': 0, 'completed': 0, 'skipped': 0, 'kept': 0, 'refused': 0}}
	for pair in sorted(universe):
		left, right = pair
		got = (side_spots(left, LEFT, groups, sides, bases, group_rule),
		       side_spots(right, RIGHT, groups, sides, bases, group_rule))
		refused = [k for k, s in zip(pair, got) if s is _REFUSED]
		if refused:
			for k in refused:
				out['refused'][k] = out['refused'].get(k, 0) + 1
			out['counts']['refused'] += 1
			continue
		if not (got[0] and got[1]):
			if side_rule == 'skip':
				out['remove'].append(pair)
				out['counts']['skipped'] += 1
				continue
			if side_rule == 'keep':
				out['keep'].append(pair)
				out['counts']['kept'] += 1
				continue
		used = [s for s in got if s]
		if not used:
			if fallback is None:
				continue
			used = [[fallback]]
		v = _mean([_mean([value(pair, s) for s in spots]) for spots in used])
		f = _mean([_mean([s['factor'] for s in spots]) if spots else 1. for spots in got])
		out['pairs'][pair] = int(round(v * f))
		out['counts']['completed' if len(used) < 2 else 'scaled'] += 1
	return out


def kern_summary(layer, result):
	'''One line on a target's kerning result.'''
	c = result['counts']
	parts = ['%d pair(s)' % len(result['pairs'])]
	if c['completed']:
		parts.append('%d with an unbaked side (factor 1)' % c['completed'])
	if c['skipped']:
		parts.append('%d skipped' % c['skipped'])
	if c['kept']:
		parts.append('%d kept' % c['kept'])
	if c['refused']:
		parts.append('%d refused (groups: %s)' % (c['refused'], ' '.join(sorted(result['refused']))))
	return '%s: kerning %s' % (layer, ', '.join(parts))


# - Font lib ---------------------------------------------------------------
# Kerning of a target that is not a master: kept in the font lib until the
# target becomes a master (Designspace > Add master > From target, or the
# Advanced list: Bake checked to masters).
def lib_new():
	return {'format': LIB_FORMAT, 'targets': {}}


def lib_normalize(raw):
	'''Font lib entry -> {'format', 'targets': {layer: entry}} (bad -> empty).'''
	out = lib_new()
	if not isinstance(raw, dict):
		return out
	for layer, entry in (raw.get('targets') or {}).items():
		if not isinstance(entry, dict):
			continue
		pairs = []
		for p in entry.get('pairs') or []:
			try:
				pairs.append([str(p[0]), str(p[1]), int(round(float(p[2])))])
			except (TypeError, ValueError, IndexError):
				continue
		out['targets'][str(layer)] = {'pairs': pairs, 'remove': [[str(p[0]), str(p[1])] for p in entry.get('remove') or []
		                                                          if isinstance(p, (list, tuple)) and len(p) == 2],
		                              'baked': str(entry.get('baked', '')), 'master': str(entry.get('master', '')),
		                              'rules': dict(entry.get('rules') or {})}
	return out


def lib_store(lib, layer, result, baked='', master='', rules=None):
	'''Put a target's result into the lib (replaces the layer's entry).'''
	lib = lib_normalize(lib)
	lib['targets'][layer] = {'pairs': [[l, r, v] for (l, r), v in sorted(result['pairs'].items())],
	                         'remove': [[l, r] for l, r in result.get('remove', [])],
	                         'baked': baked, 'master': master, 'rules': dict(rules or {})}
	return lib


def lib_entry_result(entry):
	'''A lib entry back as a kern_target-like result (pairs / remove).'''
	return {'pairs': dict(((l, r), v) for l, r, v in entry['pairs']),
	        'remove': [tuple(p) for p in entry.get('remove', [])], 'keep': []}


def lib_table(entry):
	'''A lib entry as a kerning table (input of a later axis).'''
	return dict(((l, r), v) for l, r, v in entry['pairs'])


def lib_rows(lib, masters):
	'''Advanced list rows: [{'layer', 'pairs', 'baked', 'master'}]; master
	is 'yes' when a master of that name exists now.'''
	lib = lib_normalize(lib)
	names = set(masters)
	return [{'layer': layer, 'pairs': len(e['pairs']), 'baked': e['baked'],
	         'master': layer in names} for layer, e in sorted(lib['targets'].items())]


# - Write plan -------------------------------------------------------------
def write_plan(existing, result):
	'''What to change in a master's kerning: (set {pair: value}, remove
	[pair]). existing: {pair: value} of the master now. Pairs to keep and
	pairs no input has are left alone; equal values are not rewritten.'''
	sets = dict((p, v) for p, v in result['pairs'].items() if existing.get(p) != v)
	remove = [p for p in result.get('remove', []) if p in existing]
	return sets, remove
