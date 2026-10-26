# MODULE: TypeRig / Core / Algo / Kern Rules
# -----------------------------------------------------------
# Kerning by analogy (FL Copy Kerning, kept): one rule per line,
#   destination pairs = source pair [@adjust]      # comment
#   Y|A A|Y A|V = V|A
#   Ö|V Ä|V = O|V @*1.1
# The syntax of the FL rule files is kept, so old .txt files load. Extras:
#   - a side may be a character, /glyphname, a glyph name, or @group;
#   - the adjust may be @*k, @+c, @-c or @*k+c (no eval);
#   - wildcard rules derive suffixed glyphs: *.sc|*.sc = *|*
#     (every kerned glyph pair a b of the source, with a.sc and b.sc in
#     the font, gives a.sc b.sc = value).
# The source value is what the font renders for the source glyph pair
# (a @group side stands for its key glyph). Class mode (the FL default)
# writes a destination glyph as its group when it has one.
#
#   parse_rules(text, char_map, glyphs) -> (rules, errors)
#   rules_plan(kset, rule_sets, masters, base, char_map, glyphs) -> (ChangeSet, report)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2026  (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import re

from typerig.core.algo.kern_model import (ChangeSet, LEFT, RIGHT, is_group, group_name, to_int)

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
SYN_PAIR, SYN_ADJUST, SYN_COMMENT, SYN_EQUAL, SYN_WILD = '|', '@', '#', '=', '*'
_ADJUST = re.compile(r'^(?:\*\s*(-?\d+(?:\.\d+)?))?\s*(?:([+-])\s*(\d+(?:\.\d+)?))?$')

RULE_SET_DEFAULTS = {'name': 'Rules', 'text': '', 'live': False, 'class': True, 'masters': ''}	# masters '' = all


def rule_set(**kwargs):
	out = dict(RULE_SET_DEFAULTS)
	out.update({k: v for k, v in kwargs.items() if k in RULE_SET_DEFAULTS})
	return out


def normalize_sets(data):
	'''Stored rule sets (font lib) with defaults; junk dropped.'''
	out = []
	for item in data or []:
		if isinstance(item, dict):
			out.append(rule_set(**item))
	return out


# - Parse ------------------------------------------------------------------
def parse_adjust(text):
	'''"*1.1", "+5", "-5", "*0.9+5" -> (k, c). Raises ValueError.'''
	text = str(text or '').strip()
	if not text:
		return 1., 0.
	match = _ADJUST.match(text)
	if not match or not (match.group(1) or match.group(3)):
		raise ValueError('Bad adjust "%s" (use *k, +c, -c or *k+c)' % text)
	k = float(match.group(1)) if match.group(1) else 1.
	c = float(match.group(3)) * (-1 if match.group(2) == '-' else 1) if match.group(3) else 0.
	return k, c


def _side(token, char_map, glyphs):
	'''A rule side as a glyph name or @group key, or a wildcard ('*', suffix).'''
	if token.startswith(SYN_WILD):
		return (SYN_WILD, token[1:])
	if token.startswith('/') and len(token) > 1:
		return token[1:]
	if token.startswith('@') and len(token) > 1:
		return token
	if glyphs is not None and token in glyphs:
		return token
	if len(token) == 1 and char_map and token in char_map:
		return char_map[token]
	if glyphs is None and not char_map:
		return token		# nothing to check against
	if len(token) == 1:
		raise ValueError('No glyph for the character "%s"' % token)
	if glyphs is None:
		return token
	raise ValueError('Unknown glyph "%s" (use /name for glyph names)' % token)


def _pair(text, char_map, glyphs):
	parts = text.split(SYN_PAIR)
	if len(parts) != 2 or not parts[0] or not parts[1]:
		raise ValueError('Bad pair "%s" (use left|right)' % text)
	return _side(parts[0], char_map, glyphs), _side(parts[1], char_map, glyphs)


def _is_wild(side):
	return isinstance(side, tuple)


def parse_rules(text, char_map=None, glyphs=None):
	'''Parse rule text. glyphs: the font's glyph names (None: no check).
	Returns (rules, errors): rules [{'line', 'dst': [pairs], 'src': pair, 'k', 'c'}],
	errors [(line number, message)].'''
	glyphs = set(glyphs) if glyphs is not None else None
	rules, errors = [], []
	for number, raw in enumerate(str(text or '').splitlines(), 1):
		line = raw.split(SYN_COMMENT, 1)[0].strip()
		if not line:
			continue
		if SYN_EQUAL not in line:
			errors.append((number, 'No "=" in the rule'))
			continue
		try:
			dst_text, src_text = line.split(SYN_EQUAL, 1)
			src_parts = src_text.split(SYN_ADJUST, 1)
			k, c = parse_adjust(src_parts[1] if len(src_parts) > 1 else '')
			src = _pair(src_parts[0].strip(), char_map, glyphs)
			dst = [_pair(item, char_map, glyphs) for item in dst_text.split()]
			if not dst:
				raise ValueError('No destination pair')
			wild = [_is_wild(s) for s in src] + [_is_wild(s) for p in dst for s in p]
			if any(wild) and not all(wild):
				raise ValueError('A wildcard rule needs * on every side, e.g. *.sc|*.sc = *|*')
			rules.append({'line': number, 'dst': dst, 'src': src, 'k': k, 'c': c})
		except ValueError as e:
			errors.append((number, str(e)))
	return rules, errors


# - Plan -------------------------------------------------------------------
def _effective(kset, master, base):
	table = dict(kset.pairs.get(master, {}))
	entry = base.pairs.get(master) if base is not None else None
	if entry:
		for pair in entry['remove']:
			table.pop(pair, None)
		table.update(entry['set'])
	return table


def _glyph_of(kset, side, pos):
	'''A source side as a glyph: a @group stands for its key glyph.'''
	if is_group(side):
		name = group_name(side)
		return kset.leader(name, pos)
	return side


def _wild_map(src_suffix, dst_suffix, glyph, glyphs):
	'''Destination glyph for a source glyph, or None.'''
	if src_suffix:
		if not glyph.endswith(src_suffix):
			return None
		glyph = glyph[:-len(src_suffix)]
	out = glyph + dst_suffix
	return out if glyphs is None or out in glyphs else None


def rules_plan(kset, rule_sets, masters=None, base=None, char_map=None, glyphs=None):
	'''ChangeSet that applies rule sets (dicts as rule_set()) on top of base.
	Returns (cs, report) - report: {'applied', 'no_source': [(set, line, pair, master)],
	'errors': [(set, line, message)], 'written': n}.'''
	cs = ChangeSet('rules')
	report = {'applied': 0, 'no_source': [], 'errors': [], 'written': 0}
	glyph_set = set(glyphs) if glyphs is not None else None
	for rs in rule_sets:
		rules, errors = parse_rules(rs.get('text', ''), char_map, glyph_set)
		report['errors'] += [(rs.get('name', ''), n, m) for n, m in errors]
		class_mode = bool(rs.get('class', True))
		chosen = rs.get('masters') or ''
		set_masters = [m for m in (masters or kset.masters) if not chosen or m == chosen]
		for master in set_masters:
			table = _effective(kset, master, base)
			for rule in rules:
				report['applied'] += 1
				if _is_wild(rule['src'][0]):
					writes = _wild_writes(kset, master, table, rule, glyph_set)
				else:
					a, b = _glyph_of(kset, rule['src'][0], LEFT), _glyph_of(kset, rule['src'][1], RIGHT)
					value, key, _level = kset.resolve(master, a, b, table)
					if key is None:
						report['no_source'].append((rs.get('name', ''), rule['line'], (a, b), master))
						continue
					value = to_int(value * rule['k'] + rule['c'])
					writes = [(pair, value) for pair in rule['dst']]
				for (da, db), value in writes:
					if class_mode:
						da = da if is_group(da) else kset.side_key(da, LEFT)
						db = db if is_group(db) else kset.side_key(db, RIGHT)
					if table.get((da, db)) != value:
						if cs.set(master, (da, db), value, kset.locks):
							report['written'] += 1
	return cs, report


def _wild_writes(kset, master, table, rule, glyphs):
	'''Destination pairs of a wildcard rule from the kerned glyph pairs of the source.'''
	(_, ls), (_, rs) = rule['src']
	out = []
	for (a, b), value in sorted(kset.flatten(master, table).items()):
		for (_, ld), (_, rd) in rule['dst']:
			da, db = _wild_map(ls, ld, a, glyphs), _wild_map(rs, rd, b, glyphs)
			if da and db and (da, db) != (a, b):
				out.append(((da, db), to_int(value * rule['k'] + rule['c'])))
	return out


def report_text(report):
	lines = ['Rules: %d applied, %d pair(s) to write.' % (report['applied'], report['written'])]
	for name, line, message in report['errors'][:20]:
		lines.append('  %s, line %d: %s' % (name, line, message))
	for name, line, pair, master in report['no_source'][:20]:
		lines.append('  %s, line %d: no kerning for %s %s in %s (skipped)' % (name, line, pair[0], pair[1], master))
	more = len(report['errors']) + len(report['no_source']) - 40
	if more > 0:
		lines.append('  … %d more' % more)
	return '\n'.join(lines) + '\n'
