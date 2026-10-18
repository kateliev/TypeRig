# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — glyph filters (group builders)
#
# Glyph name lists for group builders (Delta Machine Groups tab):
#   builtin_filters()          the Font view's categories: Uppercase,
#                              Lowercase, Small caps, Figures, ... (GS3 + GS4)
#   custom_filters()           the user's Glyphs custom filters
#                              (CustomFilter.plist: glyph lists and
#                              predicates; empty when there are none)
#   filter_glyphs(font, f)     names of the font's glyphs a filter takes
#   match_pattern(names, pat)  glob patterns: '*.sc  a* -a.alt'
#   glyph_kind(glyph)          colour key: Uppercase / Lowercase / Smallcaps /
#                              Figure / Mark / Other
#
# Case: GS3.2+ and GS4 have glyph.case (GSUppercase = 1, GSLowercase = 2,
# GSSmallcaps = 3, GSMinor = 4); older GS3 used subCategory 'Uppercase' /
# 'Lowercase' / 'Smallcaps'. Both are read. A glyph without category
# info falls back to its Unicode character and a '.sc' / '.smcp' suffix.
#
# GlyphsApp / Foundation imports are lazy: the pure parts run headless.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import fnmatch
import os
import plistlib

_CASES = {1: 'Uppercase', 2: 'Lowercase', 3: 'Smallcaps', 4: 'Minor'}
_SC_SUFFIXES = ('.sc', '.smcp', '.c2sc')

CUSTOM_FILTER_FILES = (
	'~/Library/Application Support/Glyphs 4/CustomFilter.plist',
	'~/Library/Application Support/Glyphs 3/CustomFilter.plist',
)


def _attr(glyph, name):
	try:
		return getattr(glyph, name)
	except Exception:
		return None


def glyph_case(glyph):
	'''Uppercase / Lowercase / Smallcaps / Minor / None.'''
	case = _attr(glyph, 'case')
	if isinstance(case, int) and case in _CASES:
		return _CASES[case]
	sub = _attr(glyph, 'subCategory')
	if sub in ('Uppercase', 'Lowercase', 'Smallcaps'):
		return sub
	name = str(_attr(glyph, 'name') or '')
	if name.endswith(_SC_SUFFIXES):
		return 'Smallcaps'
	char = _char(glyph)
	if char and char.isupper():
		return 'Uppercase'
	if char and char.islower():
		return 'Lowercase'
	return None


def _char(glyph):
	code = _attr(glyph, 'unicode')
	try:
		return chr(int(str(code), 16)) if code else ''
	except (TypeError, ValueError):
		return ''


def _category(glyph):
	category = _attr(glyph, 'category')
	if category:
		return str(category)
	char = _char(glyph)
	if char.isalpha():
		return 'Letter'
	if char.isdigit():
		return 'Number'
	return ''


def glyph_kind(glyph):
	'''Colour key of a glyph row (machine_config COLORS.CASE_COLORS).'''
	category = _category(glyph)
	if category == 'Number':
		return 'Figure'
	if category == 'Mark':
		return 'Mark'
	case = glyph_case(glyph)
	if case in ('Uppercase', 'Lowercase', 'Smallcaps'):
		return case
	return 'Other'


def glyph_info(glyph):
	'''{'name', 'unicode', 'category', 'kind'} for a glyph list row.'''
	category = _category(glyph)
	case = glyph_case(glyph)
	sub = _attr(glyph, 'subCategory')
	label = ' '.join(str(x) for x in (category, case or (sub if sub and sub != case else '')) if x)
	return {'name': str(_attr(glyph, 'name') or ''), 'unicode': str(_attr(glyph, 'unicode') or ''),
	        'category': label, 'kind': glyph_kind(glyph)}


# - Filters ----------------------------------------------------------------
# A filter: {'name': label, 'kind': 'builtin' | 'list' | 'predicate', 'value': ...}
def _is_letter_case(case):
	return lambda g: _category(g) == 'Letter' and glyph_case(g) == case

_BUILTIN = (
	('Uppercase letters', _is_letter_case('Uppercase')),
	('Lowercase letters', _is_letter_case('Lowercase')),
	('Small caps', lambda g: glyph_case(g) == 'Smallcaps'),
	('All letters', lambda g: _category(g) == 'Letter'),
	('Figures', lambda g: _category(g) == 'Number'),
	('Punctuation', lambda g: _category(g) == 'Punctuation'),
	('Symbols', lambda g: _category(g) == 'Symbol'),
	('Marks', lambda g: _category(g) == 'Mark'),
	('Ligatures', lambda g: _attr(g, 'subCategory') == 'Ligature'),
	('Separators', lambda g: _category(g) == 'Separator'),
	('Exported glyphs', lambda g: _attr(g, 'export') is not False),
	('All glyphs', lambda g: True),
)


def builtin_filters():
	return [{'name': name, 'kind': 'builtin', 'value': name} for name, _ in _BUILTIN]


def _walk_filters(node, out):
	'''CustomFilter.plist: dicts with 'name' and 'list' or 'predicate',
	possibly nested in folders ('subGroup' / any list value).'''
	if isinstance(node, dict):
		name = node.get('name')
		if name and isinstance(node.get('list'), list):
			out.append({'name': str(name), 'kind': 'list', 'value': [str(n) for n in node['list']]})
		elif name and isinstance(node.get('predicate'), str):
			out.append({'name': str(name), 'kind': 'predicate', 'value': node['predicate']})
		for key, value in node.items():
			if key not in ('list', 'predicate') and isinstance(value, (list, dict)):
				_walk_filters(value, out)
	elif isinstance(node, list):
		for item in node:
			_walk_filters(item, out)


def custom_filters(paths=CUSTOM_FILTER_FILES):
	'''The user's Glyphs custom filters (first file found).'''
	for path in paths:
		path = os.path.expanduser(path)
		if not os.path.exists(path):
			continue
		try:
			with open(path, 'rb') as f:
				data = plistlib.load(f)
		except Exception:
			continue
		out = []
		_walk_filters(data, out)
		return out
	return []


def _predicate(text):
	from Foundation import NSPredicate
	return NSPredicate.predicateWithFormat_(text)


def filter_glyphs(glyphs, flt):
	'''Names of glyphs (GSGlyphs, font order) that the filter takes.'''
	kind, value = flt.get('kind'), flt.get('value')
	if kind == 'builtin':
		test = dict(_BUILTIN).get(value)
		return [g.name for g in glyphs if test is not None and test(g)]
	if kind == 'list':
		wanted = set(value)
		return [g.name for g in glyphs if g.name in wanted]
	if kind == 'predicate':
		try:
			predicate = _predicate(value)
		except Exception:
			return []
		out = []
		for g in glyphs:
			try:
				if predicate.evaluateWithObject_(g):
					out.append(g.name)
			except Exception:
				pass
		return out
	return []


def match_pattern(names, pattern):
	'''Glob patterns, space separated; a leading '-' removes matches.
	'*.sc a*  -a.alt' -> every .sc glyph and a..., except a.alt.'''
	words = (pattern or '').split()
	take = [w for w in words if not w.startswith('-')]
	drop = [w[1:] for w in words if w.startswith('-') and len(w) > 1]
	out = []
	for name in names:
		if take and not any(fnmatch.fnmatchcase(name, w) for w in take):
			continue
		if any(fnmatch.fnmatchcase(name, w) for w in drop):
			continue
		if take:
			out.append(name)
	return out
