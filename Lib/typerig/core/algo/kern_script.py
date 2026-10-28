# MODULE: TypeRig / Core / Algo / Kern Script
# -----------------------------------------------------------
# The writing system (Unicode Script, ISO 15924 code) of a glyph, for the
# TR Kern scope checks and shape groups. OpenType kerning is looked up per
# script, so a pair of two scripts never applies.
#
#   char_script(code)      script of a code point: fontTools.unicodedata
#                          when present, else a compact range table
#                          (pure Python, Pyodide-safe)
#   glyph_scripts(names, unicodes, components, overrides)
#                          {glyph: script}. An unencoded glyph takes the
#                          script of its base: its components (the first
#                          one with a real script), else its name without
#                          the suffix (a.sc -> a, de-cy.loclBGR -> de-cy),
#                          else the parts of a ligature (f_f), else the
#                          Glyphs script suffix of its name (-cy, -gr ...).
#                          overrides {glyph: script} win.
#   NEUTRAL                scripts that kern with every script: Common,
#                          Inherited, Unknown
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import bisect

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
COMMON, INHERITED, UNKNOWN = 'Zyyy', 'Zinh', 'Zzzz'
NEUTRAL = (COMMON, INHERITED, UNKNOWN)
SCRIPT_NAMES = {'Latn': 'Latin', 'Cyrl': 'Cyrillic', 'Grek': 'Greek', 'Armn': 'Armenian', 'Hebr': 'Hebrew',
                'Arab': 'Arabic', 'Geor': 'Georgian', 'Deva': 'Devanagari', 'Thai': 'Thai',
                COMMON: 'Common', INHERITED: 'Inherited', UNKNOWN: 'Unknown'}
# Glyphs glyph-name script suffixes (glyph 'de-cy', group 'A-cy'): suffix -> script
NAME_SUFFIXES = {'cy': 'Cyrl', 'gr': 'Grek', 'ar': 'Arab', 'hb': 'Hebr', 'armn': 'Armn', 'geor': 'Geor',
                 'deva': 'Deva', 'thai': 'Thai', 'latn': 'Latn'}

# (first, last, script); the gaps below U+3000 are Common. Letters of the
# scripts TR Kern meets most; fontTools gives the full table when present.
_RANGES = sorted([
	(0x0041, 0x005A, 'Latn'), (0x0061, 0x007A, 'Latn'), (0x00AA, 0x00AA, 'Latn'), (0x00BA, 0x00BA, 'Latn'),
	(0x00C0, 0x00D6, 'Latn'), (0x00D8, 0x00F6, 'Latn'), (0x00F8, 0x02AF, 'Latn'), (0x1D00, 0x1D25, 'Latn'),
	(0x1E00, 0x1EFF, 'Latn'), (0x2C60, 0x2C7F, 'Latn'), (0xA722, 0xA7FF, 'Latn'), (0xAB30, 0xAB5A, 'Latn'),
	(0xFB00, 0xFB06, 'Latn'), (0xFF21, 0xFF3A, 'Latn'), (0xFF41, 0xFF5A, 'Latn'),
	(0x0300, 0x036F, INHERITED), (0x1AB0, 0x1AFF, INHERITED), (0x1DC0, 0x1DFF, INHERITED),
	(0x20D0, 0x20FF, INHERITED), (0xFE20, 0xFE2D, INHERITED),
	(0x0370, 0x0373, 'Grek'), (0x0375, 0x037D, 'Grek'), (0x037F, 0x0383, 'Grek'), (0x0386, 0x0386, 'Grek'),
	(0x0388, 0x03E1, 'Grek'), (0x03F0, 0x03FF, 'Grek'), (0x1F00, 0x1FFF, 'Grek'),
	(0x0400, 0x0484, 'Cyrl'), (0x0487, 0x052F, 'Cyrl'), (0x1C80, 0x1C8F, 'Cyrl'), (0x2DE0, 0x2DFF, 'Cyrl'),
	(0xA640, 0xA69F, 'Cyrl'),
	(0x0531, 0x058F, 'Armn'), (0xFB13, 0xFB17, 'Armn'),
	(0x0591, 0x05FF, 'Hebr'), (0xFB1D, 0xFB4F, 'Hebr'),
	(0x0600, 0x0604, 'Arab'), (0x0606, 0x060B, 'Arab'), (0x060D, 0x061A, 'Arab'), (0x061C, 0x061E, 'Arab'),
	(0x0620, 0x063F, 'Arab'), (0x0641, 0x064A, 'Arab'), (0x0656, 0x066F, 'Arab'), (0x0671, 0x06DC, 'Arab'),
	(0x06DE, 0x06FF, 'Arab'), (0x0750, 0x077F, 'Arab'), (0x08A0, 0x08FF, 'Arab'), (0xFB50, 0xFDFF, 'Arab'),
	(0xFE70, 0xFEFF, 'Arab'),
	(0x10A0, 0x10FF, 'Geor'), (0x1C90, 0x1CBF, 'Geor'), (0x2D00, 0x2D2F, 'Geor'),
	(0x0900, 0x0950, 'Deva'), (0x0955, 0x0963, 'Deva'), (0x0966, 0x097F, 'Deva'),
	(0x0E01, 0x0E3A, 'Thai'), (0x0E40, 0x0E5B, 'Thai'),
])
_STARTS = [r[0] for r in _RANGES]

try:
	from fontTools import unicodedata as _ftud		# full Unicode Script table
except Exception:
	_ftud = None


# - Code points --------------------------------------------------------------
def _table_script(code):
	i = bisect.bisect_right(_STARTS, code) - 1
	if i >= 0 and _RANGES[i][0] <= code <= _RANGES[i][1]:
		return _RANGES[i][2]
	return COMMON if code < 0x3000 or 0xFE30 <= code <= 0xFFEF else UNKNOWN


def char_script(code, table_only=False):
	'''ISO 15924 script code of a code point.'''
	if _ftud is not None and not table_only:
		try:
			return str(_ftud.script(chr(code)))
		except (ValueError, OverflowError):
			return UNKNOWN
	return _table_script(code)


def is_neutral(script):
	return script in NEUTRAL


# - Glyphs -------------------------------------------------------------------
def _name_suffix_script(name):
	'''Script of a Glyphs name suffix: 'de-cy' -> Cyrl, 'alpha-gr.sc' -> Grek, else None.'''
	stem = name.split('.')[0]
	if '-' in stem:
		return NAME_SUFFIXES.get(stem.rsplit('-', 1)[1].lower())
	return None


def glyph_scripts(names, unicodes=None, components=None, overrides=None):
	'''{glyph: script} for every name.
	unicodes: {glyph: code or [codes]}; components: {glyph: [names]}; overrides: {glyph: script}.'''
	names = list(names)
	known = set(names)
	unicodes = unicodes or {}
	components = components or {}
	overrides = overrides or {}
	out = {}

	def own(glyph):
		codes = unicodes.get(glyph)
		if codes is None:
			return None
		codes = codes if isinstance(codes, (list, tuple)) else [codes]
		scripts = [char_script(int(c)) for c in codes]
		real = [s for s in scripts if not is_neutral(s)]
		return real[0] if real else scripts[0] if scripts else None

	def solve(glyph, seen):
		if glyph not in out:
			out[glyph] = find(glyph, seen)
		return out[glyph]

	def find(glyph, seen):
		if glyph in overrides:
			return overrides[glyph]
		if glyph in seen:
			return UNKNOWN		# a component loop (not cached: the outer call decides)
		seen = seen | {glyph}
		script = own(glyph)
		if script is not None:
			return script
		found = []
		for comp in components.get(glyph, ()):
			if comp in known or comp in unicodes:
				found.append(solve(comp, seen))
		if not found and '.' in glyph.strip('.'):
			base = glyph.split('.')[0]
			if base and base != glyph and (base in known or base in unicodes):
				found.append(solve(base, seen))
		if not found and '_' in glyph.split('.')[0].strip('_'):
			found += [solve(part, seen) for part in glyph.split('.')[0].split('_') if part in known or part in unicodes]
		real = [s for s in found if not is_neutral(s)]
		if real:
			return real[0]
		suffix = _name_suffix_script(glyph)
		if suffix:
			return suffix
		return found[0] if found else UNKNOWN

	for name in names:
		solve(name, frozenset())
	return dict((name, out[name]) for name in names)


def side_scripts(members, scripts):
	'''{script: count} of the members with a real (not neutral) script.'''
	out = {}
	for glyph in members:
		script = scripts.get(glyph, UNKNOWN)
		if not is_neutral(script):
			out[script] = out.get(script, 0) + 1
	return out
