# MODULE: TypeRig / Core / Algo / Kern Query
# -----------------------------------------------------------
# TR Kern search grammar (user decision 2026-10-26, handout section 9.6):
# one query string; the window's filter widgets write into it.
#
#   ;            OR between clauses
#   space        AND between terms of a clause
#   left|right   pair term; a side is a glyph name, @group, *, /regex/
#                or a character. A glyph also matches its group on that
#                side: T|* finds @T pairs as well as T pairs.
#   T            one glyph / @group / /regex/ alone: either side
#   <-50 >=10 =0 !=0       value terms (any master, or master:NAME)
#   missing  missing:Bold  the pair is missing in some master / in Bold
#   spread>20    max - min of the values across the masters
#   kind:GG,CC   pair kinds (CC group-group, CG, GC, GG glyph-glyph)
#   in:@O  in:O  either side is group O or a glyph of group O
#   master:Bold  value / missing terms of this clause test Bold only
#   locked unlocked
#   ?A|V  ?A V   explain the glyph pair instead of filtering
# Names with spaces go in quotes: master:"Semi Bold".
#
#   parse(text, char_map=None) -> Query (.match(row, kset), .explain)
#   grid_rows(kset, pending=None)  rows the grid and the query use
#   explain_text(kset, a, b)       the lookup chain, per master, as text
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
import shlex

from typerig.core.algo.kern_model import (LEFT, RIGHT, is_group, group_name, group_key, pair_kind)

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
KINDS = ('CC', 'CG', 'GC', 'GG')
_VALUE = re.compile(r'^(spread)?(<=|>=|!=|==|=|<|>)(-?\d+(?:\.\d+)?)$')
_OPS = {
	'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
	'=': lambda a, b: a == b, '==': lambda a, b: a == b, '!=': lambda a, b: a != b,
}


class QueryError(ValueError):
	pass


# - Rows -------------------------------------------------------------------
def grid_rows(kset, pending=None):
	'''One row per stored pair (any master), pending changes on top:
	{'pair', 'kind', 'values': {master: value or None}, 'locked', 'pending': set(masters)}.'''
	pairs = set()
	for table in kset.pairs.values():
		pairs.update(table)
	changed = {}
	if pending is not None:
		for master, entry in pending.pairs.items():
			pairs.update(entry['set'])
			for pair in entry['set']:
				changed.setdefault(pair, {})[master] = entry['set'][pair]
			for pair in entry['remove']:
				changed.setdefault(pair, {})[master] = None
	rows = []
	for pair in sorted(pairs):
		values = {}
		for master in kset.masters:
			values[master] = kset.pairs.get(master, {}).get(pair)
		marks = changed.get(pair, {})
		values.update(marks)
		if not any(v is not None for v in values.values()) and not marks:
			continue
		rows.append({'pair': pair, 'kind': pair_kind(pair), 'values': values,
		             'locked': pair in kset.locks, 'pending': set(marks)})
	return rows


# - Query ------------------------------------------------------------------
class Query(object):
	'''A parsed query. clauses: [[term, ...], ...]; explain: (a, b) or None.'''
	def __init__(self, clauses=None, explain=None, text=''):
		self.clauses = clauses or []
		self.explain = explain
		self.text = text

	def is_empty(self):
		return not self.clauses and self.explain is None

	def match(self, row, kset):
		if not self.clauses:
			return True
		return any(all(term(row, kset) for term in clause) for clause in self.clauses)

	def filter(self, rows, kset):
		return [row for row in rows if self.match(row, kset)]


def _glyph(token, char_map):
	'''A side token as a glyph name: the name itself, else the glyph of a character.'''
	if char_map and len(token) == 1 and token in char_map:
		return char_map[token]
	return token


def _side(token, side, char_map):
	'''Predicate on one key of a pair for a side token.'''
	if token in ('*', ''):
		return lambda key, kset: True
	if len(token) > 1 and token.startswith('/') and token.endswith('/'):
		try:
			rx = re.compile(token[1:-1])
		except re.error as e:
			raise QueryError('Bad regex %s: %s' % (token, e))
		return lambda key, kset: rx.search(key) is not None
	if is_group(token):
		return lambda key, kset: key == token
	glyph = _glyph(token, char_map)
	return lambda key, kset: key == glyph or key == kset.side_key(glyph, side)


def _values(row, master):
	if master is None:
		return [v for v in row['values'].values() if v is not None]
	value = row['values'].get(master)
	return [] if value is None else [value]


def _term(token, char_map, scope):
	'''Predicate for one token; scope is a one-item list holding the clause master.'''
	low = token.lower()
	match = _VALUE.match(token)
	if match:
		spread, op, number = match.group(1), _OPS[match.group(2)], float(match.group(3))
		if spread:
			def term(row, kset):
				vals = _values(row, None)
				return bool(vals) and op(max(vals) - min(vals), number)
			return term
		return lambda row, kset: any(op(v, number) for v in _values(row, scope[0]))
	if low == 'missing':
		return lambda row, kset: any(row['values'].get(m) is None
		                             for m in ([scope[0]] if scope[0] is not None else kset.masters))
	if low.startswith('missing:'):
		master = token.split(':', 1)[1]
		return lambda row, kset: row['values'].get(master) is None
	if low.startswith('kind:'):
		kinds = set(k.strip().upper() for k in token.split(':', 1)[1].split(',') if k.strip())
		bad = kinds - set(KINDS)
		if bad:
			raise QueryError('Unknown kind %s (use %s)' % (', '.join(sorted(bad)), ', '.join(KINDS)))
		return lambda row, kset: row['kind'] in kinds
	if low.startswith('in:'):
		name = group_name(token.split(':', 1)[1]) if token.split(':', 1)[1].startswith('@') else token.split(':', 1)[1]
		key = group_key(name)
		def term(row, kset):
			left, right = row['pair']
			return (left == key or kset.group_of(left, LEFT) == name
			        or right == key or kset.group_of(right, RIGHT) == name)
		return term
	if low == 'locked':
		return lambda row, kset: row['locked']
	if low == 'unlocked':
		return lambda row, kset: not row['locked']
	if '|' in token:
		left, right = token.split('|', 1)
		lp, rp = _side(left, LEFT, char_map), _side(right, RIGHT, char_map)
		return lambda row, kset: lp(row['pair'][0], kset) and rp(row['pair'][1], kset)
	# One side token alone: either side
	lp, rp = _side(token, LEFT, char_map), _side(token, RIGHT, char_map)
	return lambda row, kset: lp(row['pair'][0], kset) or rp(row['pair'][1], kset)


def _split(text):
	try:
		return shlex.split(text, posix=True)
	except ValueError as e:
		raise QueryError('Bad quotes: %s' % e)


def parse(text, char_map=None):
	'''Parse a query string. Raises QueryError with a short message.'''
	text = str(text or '').strip()
	query = Query(text=text)
	for raw in text.split(';'):
		raw = raw.strip()
		if not raw:
			continue
		if raw.startswith('?'):
			body = raw[1:].replace('|', ' ').split()
			if len(body) != 2:
				raise QueryError('Explain needs two glyphs: ?A|V')
			query.explain = (_glyph(body[0], char_map), _glyph(body[1], char_map))
			continue
		scope = [None]
		terms = []
		for token in _split(raw):
			if token.lower().startswith('master:'):
				scope[0] = token.split(':', 1)[1]
				continue
			terms.append(_term(token, char_map, scope))
		if terms or scope[0] is not None:
			if not terms:		# master:X alone = pairs present in X
				terms.append(lambda row, kset, _s=scope: row['values'].get(_s[0]) is not None)
			query.clauses.append(terms)
	return query


# - Filter widgets ------------------------------------------------------------
_WIDGET = re.compile(r'(?:^|\s)(kind:\S+|missing(?::\S+)?)(?=\s|$)', re.I)


def set_widget_terms(text, kind=None, missing=False):
	'''The query text with the widget terms of its first clause replaced:
	kind (one of KINDS or None) and missing (bool). Other terms stay.'''
	clauses = str(text or '').split(';')
	first = _WIDGET.sub(' ', clauses[0]).split()
	if kind:
		first.append('kind:' + kind)
	if missing:
		first.append('missing')
	clauses[0] = ' '.join(first)
	return ';'.join(clauses).strip()


def widget_terms(text):
	'''(kind or None, missing) read from the first clause of a query text.'''
	first = str(text or '').split(';')[0].split()
	kind = next((t.split(':', 1)[1].upper() for t in first if t.lower().startswith('kind:')), None)
	return (kind if kind in KINDS else None), any(t.lower() == 'missing' for t in first)


# - Explain --------------------------------------------------------------------
def row_glyphs(kset, pair):
	'''A glyph pair standing for a stored pair (groups -> their key glyphs).'''
	out = []
	for key, side in zip(pair, (LEFT, RIGHT)):
		if is_group(key):
			out.append(kset.leader(group_name(key), side) or key)
		else:
			out.append(key)
	return tuple(out)


def explain_text(kset, a, b):
	'''The lookup chain of glyph pair (a, b), per master, as text.'''
	level_names = {'GG': 'glyph + glyph', 'GC': 'glyph + group', 'CG': 'group + glyph', 'CC': 'group + group'}
	lines = ['%s %s' % (a, b)]
	la, rb = kset.side_key(a, LEFT), kset.side_key(b, RIGHT)
	lines.append('  groups: %s | %s' % (la if is_group(la) else '(none)', rb if is_group(rb) else '(none)'))
	for master, info in kset.explain(a, b).items():
		used = level_names[info['level']] if info['level'] else 'nothing (0)'
		lines.append('  %s: %s  from %s%s' % (master, info['value'], used,
		                                     '  %s %s' % info['key'] if info['key'] else ''))
		seen = set([info['key']])
		for level, key, value in info['chain']:
			if value is not None and key not in seen:
				seen.add(key)
				lines.append('      also %s %s = %s (%s, not used)' % (key[0], key[1], value, level_names[level]))
	return '\n'.join(lines) + '\n'
