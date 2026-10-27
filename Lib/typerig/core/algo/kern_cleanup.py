# MODULE: TypeRig / Core / Algo / Kern Cleanup
# -----------------------------------------------------------
# TR Kern cleanup (FL CleanKerning, rethought): every check finds first
# (a report), a fix is a separate ChangeSet. All checks use the font's
# own lookup order (glyph + glyph > glyph + group > group + glyph >
# group + group), so a fix that says "rendering kept" keeps every glyph
# pair as it was (within the tolerance, measured against the original).
#
#   redundant      a stored pair whose removal changes no glyph pair (any kind)
#   compress       a group pair region rewritten with fewer pairs, same rendering
#                  (flat pairs that fit a class, a class value that the
#                  exceptions disagree with, piles of exceptions)
#   mismatch       pairs missing in some masters: covered (a class still gives
#                  a value) / uncovered (0); fix: fill resolved | copy from | remove
#   orphans        pairs that name a missing group or glyph
#   small          |value| below a threshold (fix: remove; changes rendering)
#   outliers       a pair whose sign flips across masters, or whose spread is large
#
#   CHECKS, find(kset, check, options) -> findings
#   fix(kset, check, findings, options) -> ChangeSet
#   report_text(check, findings)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.algo import kern_reclass as krc
from typerig.core.algo.kern_model import (ChangeSet, LEFT, RIGHT, is_group, group_name, pair_kind, apply)

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
CHECKS = (	# (key, title, keeps rendering)
	('redundant', 'Pairs that change nothing', True),
	('compress', 'Compress group pairs (same rendering)', True),
	('mismatch', 'Pairs missing in some masters', True),
	('orphans', 'Pairs with a missing group or glyph', True),
	('small', 'Small values', False),
	('outliers', 'Sign flips and large spreads across masters', False),
)
MISMATCH_FIXES = (('fill', 'Fill resolved'), ('copy', 'Copy from master'), ('nearest', 'Copy nearest master'),
                  ('interpolate', 'Interpolate (location)'), ('remove', 'Remove everywhere'))
OPTION_DEFAULTS = {'tolerance': 0, 'small': 5, 'spread': 60, 'mismatch_fix': 'fill', 'copy_from': ''}
_ORDER = {'GG': 0, 'GC': 1, 'CG': 2, 'CC': 3}


def options(data=None):
	out = dict(OPTION_DEFAULTS)
	out.update({k: v for k, v in (data or {}).items() if k in OPTION_DEFAULTS})
	for key in ('tolerance', 'small', 'spread'):
		try:
			out[key] = max(0, int(out[key] or 0))
		except (TypeError, ValueError):
			out[key] = OPTION_DEFAULTS[key]
	if out['mismatch_fix'] not in dict(MISMATCH_FIXES):
		out['mismatch_fix'] = OPTION_DEFAULTS['mismatch_fix']
	return out


# - Helpers -------------------------------------------------------------------
def _cells(kset, pair):
	'''Glyph pairs a stored pair can reach.'''
	return [(a, b) for a in kset.members(pair[0], LEFT) for b in kset.members(pair[1], RIGHT)]


def _bucket(kset, pair):
	'''The group pair region of a stored pair: (left key, right key) of its sides' groups.'''
	left = pair[0] if is_group(pair[0]) else kset.side_key(pair[0], LEFT)
	right = pair[1] if is_group(pair[1]) else kset.side_key(pair[1], RIGHT)
	return left, right


# - Redundant -----------------------------------------------------------------------
def find_redundant(kset, tolerance=0):
	'''[(master, pair, value)] whose removal keeps every glyph pair within
	tolerance of its original value. Exceptions are judged first.'''
	out = []
	for master in kset.masters:
		original = kset.pairs[master]
		table = dict(original)
		for pair in sorted(original, key=lambda p: (_ORDER[pair_kind(p)], p)):
			value = table.pop(pair)
			ok = True
			for a, b in _cells(kset, pair):
				want = kset.resolve(master, a, b, original)[0]
				if abs(kset.resolve(master, a, b, table)[0] - want) > tolerance:
					ok = False
					break
			if ok:
				out.append((master, pair, value))
			else:
				table[pair] = value
	return out


# - Compress ------------------------------------------------------------------------
def find_compress(kset, tolerance=0, min_saving=1):
	'''[(master, bucket, old pairs {pair: value}, new pairs {pair: value})] where a
	group pair region can be written with fewer pairs and the same rendering.'''
	out = []
	for master in kset.masters:
		table = kset.pairs[master]
		buckets = {}
		for pair in table:
			buckets.setdefault(_bucket(kset, pair), []).append(pair)
		for bucket, pairs in sorted(buckets.items()):
			if not (is_group(bucket[0]) or is_group(bucket[1])):
				continue		# glyph + glyph without groups: nothing to compress
			if any(p in kset.locks for p in pairs):
				continue		# a locked pair would stay while its region is rewritten
			lefts, rights = kset.members(bucket[0], LEFT), kset.members(bucket[1], RIGHT)
			flat = {(a, b): kset.resolve(master, a, b, table)[0] for a in lefts for b in rights}
			region = {p: table[p] for p in pairs}
			# keep pairs outside the region that reach it (glyph + group of another bucket cannot)
			new, _rep = krc.reclass(flat, kset, krc.RULE_MODE, tolerance, krc.ABSENT_ZERO, lefts + rights)
			new = {p: v for p, v in new.items() if _bucket(kset, p) == bucket}
			if len(new) + min_saving <= len(region) and _same(kset, master, table, region, new, flat, tolerance):
				out.append((master, bucket, region, new))
	return out


def _same(kset, master, table, old, new, flat, tolerance):
	trial = dict(table)
	for pair in old:
		trial.pop(pair, None)
	trial.update(new)
	return all(abs(kset.resolve(master, a, b, trial)[0] - v) <= tolerance for (a, b), v in flat.items())


# - Mismatch -----------------------------------------------------------------------
def _fill_value(kset, master, pair):
	'''Value that makes pair explicit in master without changing rendering:
	(value, exact, covered). The glyph pairs the pair would control there
	(no pair of higher precedence) are measured; exact when they agree.'''
	table = kset.pairs.get(master, {})
	trial = dict(table)
	trial[pair] = None		# sentinel: which glyph pairs would it reach?
	values = []
	for a, b in _cells(kset, pair):
		if kset.resolve(master, a, b, trial)[1] == pair:
			values.append(kset.resolve(master, a, b, table)[0])
	if not values:
		return 0, True, False
	counts = {}
	for v in values:
		counts[v] = counts.get(v, 0) + 1
	value = max(sorted(counts), key=lambda v: counts[v])
	return value, len(counts) == 1, any(v != 0 for v in values)


def find_mismatch(kset):
	'''[(pair, info)] for pairs some masters have and others do not. info:
	'missing' [masters], 'values' {master: value or None}, 'fill' {master: value
	that keeps rendering}, 'exact' {master: bool}, 'covered' {master: value} where
	something else gives those glyph pairs a value now.'''
	out = []
	keys = set()
	for table in kset.pairs.values():
		keys.update(table)
	for pair in sorted(keys):
		values = {m: kset.pairs[m].get(pair) for m in kset.masters}
		missing = [m for m, v in values.items() if v is None]
		if not missing or len(missing) == len(kset.masters):
			continue
		info = {'missing': missing, 'values': values, 'fill': {}, 'exact': {}, 'covered': {}}
		for m in missing:
			value, exact, covered = _fill_value(kset, m, pair)
			info['fill'][m], info['exact'][m] = value, exact
			if covered:
				info['covered'][m] = value
		out.append((pair, info))
	return out


# - Locations: nearest master, interpolation --------------------------------------
def _distance(kset, a, b):
	'''Distance of two masters by location (axes both have); by master order without locations.'''
	la, lb = kset.locations.get(a), kset.locations.get(b)
	if la and lb:
		axes = set(la) & set(lb)
		if axes:
			return sum((la[x] - lb[x]) ** 2 for x in axes) ** .5
	order = kset.masters
	return abs(order.index(a) - order.index(b)) if a in order and b in order else float('inf')


def nearest_value(kset, master, values):
	'''(value, source master): the value of the nearest master that has one.'''
	have = [m for m, v in values.items() if v is not None and m != master]
	if not have:
		return None, None
	source = min(have, key=lambda m: (_distance(kset, master, m), kset.masters.index(m)))
	return values[source], source


def interpolated_value(kset, master, values):
	'''(value, how): piecewise linear along the one axis on which the masters differ,
	from the masters that have the pair; outside their range or with several axes:
	the nearest master ('nearest').'''
	have = {m: v for m, v in values.items() if v is not None and m != master}
	loc = kset.locations.get(master) or {}
	axes = set()
	for m in list(have) + [master]:
		axes |= set(kset.locations.get(m) or {})
	moving = [x for x in sorted(axes)
	          if len(set((kset.locations.get(m) or {}).get(x) for m in list(have) + [master])) > 1]
	if len(moving) == 1 and len(have) >= 2 and moving[0] in loc:
		axis = moving[0]
		points = sorted(((kset.locations[m][axis], v) for m, v in have.items() if axis in (kset.locations.get(m) or {})))
		t = loc[axis]
		for (x0, v0), (x1, v1) in zip(points, points[1:]):
			if x0 <= t <= x1 and x1 != x0:
				return int(round(v0 + (v1 - v0) * (t - x0) / (x1 - x0))), 'interpolate'
	value, _source = nearest_value(kset, master, values)
	return value, 'nearest'


# - Orphans / small / outliers --------------------------------------------------------------
def find_orphans(kset, glyphs=None):
	glyphs = set(glyphs) if glyphs is not None else None
	out = []
	for master in kset.masters:
		for pair, value in sorted(kset.pairs[master].items()):
			for key, side in zip(pair, (LEFT, RIGHT)):
				if is_group(key):
					bad = not kset.groups[side].get(group_name(key))
				else:
					bad = glyphs is not None and key not in glyphs
				if bad:
					out.append((master, pair, value))
					break
	return out


def find_small(kset, threshold=5):
	return [(m, p, v) for m in kset.masters for p, v in sorted(kset.pairs[m].items()) if abs(v) < threshold]


def find_outliers(kset, spread=60):
	'''[(pair, values, reason)]: sign flips (one master kerns +, another -) or max - min > spread.'''
	out = []
	keys = set()
	for table in kset.pairs.values():
		keys.update(table)
	for pair in sorted(keys):
		values = {m: kset.pairs[m][pair] for m in kset.masters if pair in kset.pairs[m]}
		if len(values) < 2:
			continue
		vals = list(values.values())
		if min(vals) < 0 < max(vals):
			out.append((pair, values, 'sign'))
		elif max(vals) - min(vals) > spread:
			out.append((pair, values, 'spread'))
	return out


# - Find / fix ---------------------------------------------------------------------
def find(kset, check, opts=None, glyphs=None):
	opts = options(opts)
	if check == 'redundant':
		return find_redundant(kset, opts['tolerance'])
	if check == 'compress':
		return find_compress(kset, opts['tolerance'])
	if check == 'mismatch':
		return find_mismatch(kset)
	if check == 'orphans':
		return find_orphans(kset, glyphs)
	if check == 'small':
		return find_small(kset, opts['small'])
	if check == 'outliers':
		return find_outliers(kset, opts['spread'])
	raise ValueError('Unknown check: %s' % check)


def fix(kset, check, findings, opts=None):
	'''ChangeSet that fixes findings (outliers: report only, empty ChangeSet).'''
	opts = options(opts)
	cs = ChangeSet('cleanup %s' % check)
	if check in ('redundant', 'orphans', 'small'):
		for master, pair, _value in findings:
			cs.remove(master, pair, kset.locks)
	elif check == 'compress':
		for master, _bucket, old, new in findings:
			for pair in old:
				if pair not in new:
					cs.remove(master, pair, kset.locks)
			for pair, value in new.items():
				if old.get(pair) != value:
					cs.set(master, pair, value, kset.locks)
	elif check == 'mismatch':
		how = opts['mismatch_fix']
		for pair, info in findings:
			if how == 'remove':
				for master, value in info['values'].items():
					if value is not None:
						cs.remove(master, pair, kset.locks)
			elif how == 'copy':
				source = info['values'].get(opts['copy_from'])
				if source is None:
					continue
				for master in info['missing']:
					cs.set(master, pair, source, kset.locks)
			elif how in ('nearest', 'interpolate'):
				for master in info['missing']:
					if how == 'nearest':
						value, _src = nearest_value(kset, master, info['values'])
					else:
						value, used = interpolated_value(kset, master, info['values'])
						if used == 'nearest':
							cs.log.append('%s %s in %s: nearest master (not between masters on one axis)'
							              % (pair[0], pair[1], master))
					if value is not None:
						cs.set(master, pair, value, kset.locks)
			else:
				for master in info['missing']:
					cs.set(master, pair, info['fill'][master], kset.locks)
	cs.log.append('%s: %d change(s)' % (check, cs.count('set') + cs.count('remove')))
	return cs


def count(check, findings):
	return len(findings)


def report_text(check, findings, limit=40):
	title = dict((k, t) for k, t, _r in CHECKS)[check]
	lines = ['%s: %d' % (title, len(findings))]
	for item in findings[:limit]:
		if check in ('redundant', 'orphans', 'small'):
			master, pair, value = item
			lines.append('  %s %s = %s  (%s)' % (pair[0], pair[1], value, master))
		elif check == 'compress':
			master, bucket, old, new = item
			lines.append('  %s %s  (%s): %d pairs -> %d' % (bucket[0], bucket[1], master, len(old), len(new)))
		elif check == 'mismatch':
			pair, info = item
			parts = ['%s %s%s' % (m, 'covered %s' % info['covered'][m] if m in info['covered'] else 'uncovered',
			                      '' if info['exact'][m] else ' (glyph pairs differ: fill is approximate)')
			         for m in info['missing']]
			lines.append('  %s %s  missing in %s' % (pair[0], pair[1], ', '.join(parts)))
		elif check == 'outliers':
			pair, values, reason = item
			lines.append('  %s %s  %s: %s' % (pair[0], pair[1], reason, ', '.join('%s %s' % mv for mv in values.items())))
	if len(findings) > limit:
		lines.append('  … %d more' % (len(findings) - limit))
	return '\n'.join(lines) + '\n'
