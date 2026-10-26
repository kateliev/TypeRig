# MODULE: TypeRig / Core / Algo / Kern Reclass
# -----------------------------------------------------------
# Put flat glyph-glyph kerning (an autokerner's AFM, a KRN with values,
# a flattened font) onto a font's existing kerning groups. Groups are
# read only: this module never adds, renames or removes a group.
#
# Per group pair (bucket) the class value is chosen by a rule:
#   key    the leaders' pair (stored leader, else the member named like
#          the group), else mode
#   mode   the value most members agree with (within tolerance)
#   median the middle value (median_low, so it is a real member value)
# Members that differ by more than the tolerance become exceptions,
# compressed to glyph-group (a|@R) or group-glyph (@L|b) where one
# override replaces several glyph-glyph pairs. A final pass resolves
# every member pair through the result and adds glyph-glyph pairs where
# it still differs, so the result is right by construction.
#
# Absent pairs (user decision 2026-10-26): 'zero' (default) - a covered
# glyph pair missing from the source is 0 (autokerners omit zero pairs);
# 'none' - no opinion, the member just inherits the class value.
# Coverage = the glyphs the source knows (AFM CharMetrics, or every
# glyph named in its pairs). Glyphs outside it are never judged.
#
#   prefilter(flat, ...)          round / drop small / clamp
#   reclass(flat, groups, ...)    -> (table, report)
#   self_check(kset, m, flat, ..) -> mismatches of the written result
#   name_map(names, glyphs, ...)  source names -> font glyph names
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import re
from collections import Counter

from typerig.core.algo.kern_model import (KernSet, LEFT, RIGHT, is_group, group_key, group_name, to_int)

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
RULE_KEY, RULE_MODE, RULE_MEDIAN = 'key', 'mode', 'median'
VALUE_RULES = ((RULE_KEY, 'Key glyph'), (RULE_MODE, 'Mode'), (RULE_MEDIAN, 'Median'))
ABSENT_ZERO, ABSENT_NONE = 'zero', 'none'
ABSENT_RULES = ((ABSENT_ZERO, 'Absent = 0'), (ABSENT_NONE, 'No opinion'))
RULE_DEFAULT, ABSENT_DEFAULT = RULE_KEY, ABSENT_ZERO


# - Filters ----------------------------------------------------------------
def prefilter(flat, round_to=0, min_abs=0, clamp=None):
	'''Round to a base, drop |v| < min_abs, clamp to +/- clamp. Returns a new dict.
	Rounding happens first, so a value that rounds to 0 is dropped as small.'''
	out = {}
	for pair, value in flat.items():
		value = float(value)
		if round_to:
			value = round_to * round(value / round_to)
		if clamp:
			value = max(-clamp, min(clamp, value))
		value = to_int(value)
		if min_abs and abs(value) < min_abs:
			continue
		out[tuple(pair)] = value
	return out


# - Names ------------------------------------------------------------------
_UNI = re.compile(r'^uni([0-9A-Fa-f]{4})$')
_U = re.compile(r'^u([0-9A-Fa-f]{4,6})$')


def name_map(names, glyphs, production=None, unicodes=None):
	'''Map source glyph names to font glyph names.
	glyphs: font glyph names; production: {production name: glyph};
	unicodes: {codepoint: glyph}. Order: as is, production name, uniXXXX / uXXXXX.
	Returns ({source: glyph}, [unmapped source names]).'''
	glyphs = set(glyphs)
	production = production or {}
	unicodes = unicodes or {}
	mapping, missing = {}, []
	for name in names:
		if name in glyphs:
			mapping[name] = name
			continue
		if name in production:
			mapping[name] = production[name]
			continue
		match = _UNI.match(name) or _U.match(name)
		if match and int(match.group(1), 16) in unicodes:
			mapping[name] = unicodes[int(match.group(1), 16)]
			continue
		missing.append(name)
	return mapping, missing


def rename_pairs(flat, mapping):
	'''Flat pairs with names mapped; pairs with an unmapped side are dropped.'''
	out = {}
	for (a, b), value in flat.items():
		if a in mapping and b in mapping:
			out[(mapping[a], mapping[b])] = value
	return out


# - Class value ------------------------------------------------------------
def _mode(values, tolerance, prefer=None):
	'''Value that most members agree with (|x - v| <= tolerance). Ties: the
	preferred value if tied, else the tied value nearest the median.'''
	counts = Counter(values)
	scored = {}
	for candidate in counts:
		scored[candidate] = sum(n for v, n in counts.items() if abs(v - candidate) <= tolerance)
	best = max(scored.values())
	tied = sorted(v for v, s in scored.items() if s == best)
	if prefer is not None and prefer in tied:
		return prefer
	middle = sorted(values)[(len(values) - 1) // 2]
	return min(tied, key=lambda v: (abs(v - middle), v))


def class_value(values, rule, tolerance, key_value=None):
	'''values: member values of a bucket; key_value: the key pair's value or None.'''
	if rule == RULE_KEY and key_value is not None:
		return key_value
	if rule == RULE_MEDIAN:
		return sorted(values)[(len(values) - 1) // 2]
	return _mode(values, tolerance, key_value)


# - Reclass ----------------------------------------------------------------
def reclass(flat, groups, rule=RULE_DEFAULT, tolerance=0, absent=ABSENT_DEFAULT, coverage=None, keys=None):
	'''Turn flat glyph pairs into class kerning on the given groups.

	Args:
		flat (dict)      : {(glyph, glyph): value}
		groups (dict)    : {'left': {name: [glyphs]}, 'right': {...}} (or a KernSet)
		rule (str)       : 'key' | 'mode' | 'median'
		tolerance (int)  : members within it agree with the class value
		absent (str)     : 'zero' | 'none'
		coverage (iter)  : glyphs the source knows; default: every glyph in flat
		keys (dict)      : optional {'left': {group: glyph}, 'right': {...}} key glyphs

	Returns:
		(table, report): table {(left key, right key): value};
		report {'buckets', 'cells' (member pairs judged), 'present' (of them in the source),
		        'kinds': Counter, 'key_fallback': [bucket], 'outside': set(glyphs)}
	'''
	kset = groups if isinstance(groups, KernSet) else KernSet(groups=groups)
	flat = {tuple(p): to_int(v) for p, v in flat.items()}
	if coverage is None:
		coverage = set(g for pair in flat for g in pair)
	else:
		coverage = set(coverage)
	keys = keys or {}

	# - Buckets: (left key, right key) -> {(a, b): value}
	buckets = {}
	for (a, b), value in flat.items():
		buckets.setdefault((kset.side_key(a, LEFT), kset.side_key(b, RIGHT)), {})[(a, b)] = value

	def side_members(key, side):
		return [g for g in kset.members(key, side) if g in coverage]

	def side_key_glyph(key, side):
		if not is_group(key):
			return key
		name = group_name(key)
		chosen = (keys.get(side) or {}).get(name)
		return chosen or kset.leader(name, side)

	table, desired = {}, {}
	report = {'buckets': 0, 'cells': 0, 'present': 0, 'kinds': Counter(), 'key_fallback': [], 'outside': set()}

	for (lkey, rkey), present in sorted(buckets.items()):
		if absent == ABSENT_ZERO:
			lefts, rights = side_members(lkey, LEFT), side_members(rkey, RIGHT)
			cells = {(a, b): present.get((a, b), 0) for a in lefts for b in rights}
		else:
			cells = dict(present)
		if not any(cells.values()):
			continue
		report['buckets'] += 1
		report['cells'] += len(cells)
		report['present'] += sum(1 for pair in cells if pair in present)
		desired.update(cells)

		key_pair = (side_key_glyph(lkey, LEFT), side_key_glyph(rkey, RIGHT))
		key_value = cells.get(key_pair)
		if rule == RULE_KEY and key_value is None:
			report['key_fallback'].append((lkey, rkey))
		value = class_value(list(cells.values()), rule, tolerance, key_value)
		if value:
			table[(lkey, rkey)] = value

		# - Row overrides a|@R, then column overrides @L|b, where they save pairs
		if is_group(lkey) and is_group(rkey):
			_compress(cells, table, lkey, rkey, value, tolerance, row=True)
			_compress(cells, table, lkey, rkey, value, tolerance, row=False)

	# - Final pass: glyph-glyph wherever the result still differs
	for (a, b), want in desired.items():
		got = kset.resolve(None, a, b, table)[0]
		if abs(got - want) > tolerance:
			table[(a, b)] = want

	# - Drop pairs that resolve to what they would be without them
	_prune(kset, table, desired, tolerance)

	for pair in table:
		report['kinds'][('C' if is_group(pair[0]) else 'G') + ('C' if is_group(pair[1]) else 'G')] += 1
	report['outside'] = set(g for pair in flat for g in pair) - coverage
	return table, report


def _compress(cells, table, lkey, rkey, class_v, tolerance, row=True):
	'''One override per row (glyph a against group rkey) or column (group
	lkey against glyph b) when it replaces more than one exception.'''
	lines = {}
	for (a, b), v in cells.items():
		if not row and (a, rkey) in table:
			continue	# a row override (a|@R) wins over any column override
		lines.setdefault(a if row else b, []).append(v)
	for glyph, values in sorted(lines.items()):
		if len(values) < 2:
			continue
		off = sum(1 for v in values if abs(v - class_v) > tolerance)
		if off < 2:
			continue
		line_v = _mode(values, tolerance)
		after = 1 + sum(1 for v in values if abs(v - line_v) > tolerance)
		if after < off and abs(line_v - class_v) > tolerance:
			table[(glyph, rkey) if row else (lkey, glyph)] = line_v


def _prune(kset, table, desired, tolerance):
	'''Remove exceptions that change no covered member pair.'''
	for pair in sorted([p for p in table if not (is_group(p[0]) and is_group(p[1]))]):
		value = table.pop(pair)
		lefts = kset.members(pair[0], LEFT)
		rights = kset.members(pair[1], RIGHT)
		needed = False
		for a in lefts:
			for b in rights:
				if (a, b) in desired and abs(kset.resolve(None, a, b, table)[0] - desired[(a, b)]) > tolerance:
					needed = True
					break
			if needed:
				break
		if needed:
			table[pair] = value


# - Self check -------------------------------------------------------------
def self_check(kset, master, flat, tolerance=0, absent=ABSENT_DEFAULT, coverage=None):
	'''Compare what the master renders with the source.
	Returns [(a, b, expected, got)] beyond tolerance. Under 'zero', pairs
	the master kerns between covered glyphs but the source does not are
	checked against 0; under 'none' only source pairs are checked.'''
	flat = {tuple(p): to_int(v) for p, v in flat.items()}
	coverage = set(g for p in flat for g in p) if coverage is None else set(coverage)
	out = []
	for (a, b), want in sorted(flat.items()):
		got = kset.resolve(master, a, b)[0]
		if abs(got - want) > tolerance:
			out.append((a, b, want, got))
	if absent == ABSENT_ZERO:
		for (a, b), got in sorted(kset.flatten(master).items()):
			if (a, b) in flat or a not in coverage or b not in coverage:
				continue
			if abs(got) > tolerance:
				out.append((a, b, 0, got))
	return out
