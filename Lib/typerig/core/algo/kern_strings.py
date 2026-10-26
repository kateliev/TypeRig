# MODULE: TypeRig / Core / Algo / Kern Strings
# -----------------------------------------------------------
# Proof strings and pair lists (FL Pairs panel, kept): pairs A x B or the
# pairs of a kerning table, set in a pattern with fillers.
#
# Pattern: space separated tokens (FL Pairs patterns load unchanged)
#   FL / FR   left / right filler        A / B   the two sides of the pair
#   |         a word space               \n      a new line
#   e.g. 'FL A B A FR', 'FL A | B FR \n FR B A FL'
# Fillers: text, characters and /glyphname mixed ('HH', 'HOII', '/H/O');
# 'auto' picks HOH or non by the case of the side's character.
#
# Output for an edit tab is /name text only (/H/H/T/o/H/H): Glyphs reads
# a /name up to the next / or space, so a literal character after a name
# would join it. Plain text (characters) is for other apps; pairs whose
# glyphs have no character are dropped there (and counted).
#
#   PATTERNS, FILLERS, AUTO_FILLER
#   tokens(text, char_map) -> [glyph names]
#   expand_side(text, kset, side, sets, char_map, glyphs) -> [glyph names]
#   ab_pairs(a, b, ...)  /  table_pairs(kset, master, pairs=None)
#   tab_text(pairs, pattern, fl, fr, char_map, glyph_chars, join) -> str
#   plain_text(...) -> (str, dropped)
#   kpx_text(pairs) -> str
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.algo.kern_model import LEFT, RIGHT, is_group, group_name, key_glyph

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
PATTERNS = (
	'FL A FR', 'FL B FR', 'FL A B A FR', 'FL B A B FR', 'FL A FL FR A FR', 'FL B FL FR B FR',
	'FL A B FL FR B A FR', 'FL A B FL A FL B A FL', 'FL A B FL B FL B A FL',
	'FL A | B FR', 'FL B | A FR', 'FL A | B FR \\n FR B A FL',
)
FILLERS = (('nn', 'nn'), ('oo', 'oo'), ('HH', 'HH'), ('OO', 'OO'), ('HOII', 'IIOH'), ('ll', 'll'),
           ('dll', 'llb'), ('hoii', 'iioh'))
AUTO_FILLER = 'auto'
AUTO_UPPER, AUTO_LOWER = 'HOH', 'non'
JOINS = (('newline', 'New line'), ('space', 'Space'), ('none', 'Nothing'))
SPACE_GLYPH = 'space'
SETS_TOKEN = '*'		# '*Uppercase' etc. in a side list: a glyph set of the host


# - Tokens -----------------------------------------------------------------
def tokens(text, char_map=None):
	'''Glyph names in a filler text: /name tokens and characters mixed.'''
	out = []
	text = str(text or '')
	i = 0
	while i < len(text):
		ch = text[i]
		if ch == '/':
			j = i + 1
			while j < len(text) and text[j] not in '/ ':
				j += 1
			if j > i + 1:
				out.append(text[i + 1:j])
			i = j
			continue
		if ch == ' ':
			out.append(SPACE_GLYPH)
		else:
			out.append(char_map.get(ch, ch) if char_map else ch)
		i += 1
	return out


def expand_side(text, kset=None, side=LEFT, sets=None, char_map=None, glyphs=None):
	'''A side list: space separated glyph names, characters, @group (its key
	glyph), @* (the key glyphs of every group of that side), *SetName
	(a glyph set of the host: sets {name: [glyphs]}). Unknown names dropped.'''
	glyphs = set(glyphs) if glyphs is not None else None
	out = []
	for token in str(text or '').split():
		if token == '@*' and kset is not None:
			found = [key_glyph(n, kset.groups[side][n]) for n in sorted(kset.groups[side])]
		elif token.startswith('@') and kset is not None:
			members = kset.groups[side].get(group_name(token), [])
			found = [key_glyph(group_name(token), members)] if members else []
		elif token.startswith(SETS_TOKEN) and sets is not None:
			found = list(sets.get(token[1:], []))
		elif glyphs is not None and token in glyphs:
			found = [token]
		elif len(token) == 1 and char_map and token in char_map:
			found = [char_map[token]]
		elif token.startswith('/'):
			found = [token[1:]]
		else:
			found = [token] if glyphs is None else []
		for glyph in found:
			if glyph and glyph not in out:
				out.append(glyph)
	return out


# - Pairs ------------------------------------------------------------------
def ab_pairs(lefts, rights, suffix=('', '')):
	return [(a + suffix[0], b + suffix[1]) for a in lefts for b in rights]


def table_pairs(kset, master, pairs=None):
	'''Glyph pairs standing for stored pairs (groups -> key glyphs), in order, no duplicates.'''
	out = []
	source = kset.pairs.get(master, {}) if pairs is None else pairs
	for left, right in sorted(source):
		glyph_pair = []
		for key, side in ((left, LEFT), (right, RIGHT)):
			if is_group(key):
				name = group_name(key)
				glyph_pair.append(key_glyph(name, kset.groups[side].get(name, [])) or key)
			else:
				glyph_pair.append(key)
		glyph_pair = tuple(glyph_pair)
		if glyph_pair not in out:
			out.append(glyph_pair)
	return out


# - Strings ----------------------------------------------------------------
def _filler(text, glyph, char_map, glyph_chars):
	if text == AUTO_FILLER:
		ch = (glyph_chars or {}).get(glyph, '')
		text = AUTO_UPPER if ch.isupper() else AUTO_LOWER
	return tokens(text, char_map)


def _expand(pair, pattern, fl, fr, char_map, glyph_chars):
	'''One pair in the pattern: a list of glyph names and '\\n'.'''
	out = []
	a, b = pair
	for token in str(pattern).split():
		if token == 'FL':
			out += _filler(fl, a, char_map, glyph_chars)
		elif token == 'FR':
			out += _filler(fr, b, char_map, glyph_chars)
		elif token == 'A':
			out.append(a)
		elif token == 'B':
			out.append(b)
		elif token == '|':
			out.append(SPACE_GLYPH)
		elif token in ('\\n', '\n'):
			out.append('\n')
		else:
			out += tokens(token, char_map)
	return out


_JOIN = {'newline': ['\n'], 'space': [SPACE_GLYPH], 'none': []}


def _sequence(pairs, pattern, fl, fr, char_map, glyph_chars, join):
	seq = []
	for i, pair in enumerate(pairs):
		if i:
			seq += _JOIN.get(join, ['\n'])
		seq += _expand(pair, pattern, fl, fr, char_map, glyph_chars)
	return seq


def tab_text(pairs, pattern='FL A B A FR', fl='HH', fr='HH', char_map=None, glyph_chars=None, join='newline'):
	'''Edit tab text: every glyph as /name, new lines as they are.'''
	out = []
	for item in _sequence(pairs, pattern, fl, fr, char_map, glyph_chars, join):
		out.append('\n' if item == '\n' else '/' + item)
	return ''.join(out)


def plain_text(pairs, pattern='FL A B A FR', fl='HH', fr='HH', char_map=None, glyph_chars=None, join='newline'):
	'''Text with characters; pairs with a glyph that has no character are
	dropped. Returns (text, dropped pairs).'''
	glyph_chars = dict(glyph_chars or {})
	glyph_chars.setdefault(SPACE_GLYPH, ' ')
	kept, dropped = [], []
	for pair in pairs:
		(kept if all(g in glyph_chars for g in pair) else dropped).append(pair)
	out = []
	for item in _sequence(kept, pattern, fl, fr, char_map, glyph_chars, join):
		if item == '\n':
			out.append('\n')
		elif item in glyph_chars:
			out.append(glyph_chars[item])
	return ''.join(out), dropped


def kpx_text(pairs):
	return '\n'.join('KPX %s %s' % pair for pair in pairs) + ('\n' if pairs else '')
