# MODULE: TypeRig / Core / Actions / Kern Font
# -----------------------------------------------------------
# TR Kern host on a core Font (objects/font.py): the same interface as the
# Glyphs host (proxy/gs3/objects/kern.GlyphsKernHost), so the TR Kern
# engine, a command line tool or FontRig can work on a .trfont, a UFO or a
# designspace read into core.
#
# Keys: UFO groups public.kern1.NAME / public.kern2.NAME <-> core '@NAME'
# (side from the place in the pair); other groups are not kerning groups.
# Kerning per master: Font.kerning_for(master). TR Kern settings (locks,
# rules, ...) live in font.lib under kern_actions.LIB_KEY as JSON text.
#
#   CoreFontKernHost(font, path=None)
#   kernset_from_font(font) -> KernSet       apply_to_font(font, cs)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import json
import os
import unicodedata

from typerig.core.algo.kern_model import KernSet, LEFT, RIGHT, SIDES, is_group, group_name, group_key
from typerig.core.objects.groups import KERN1_PREFIX, KERN2_PREFIX

__version__ = '0.1.0'

PREFIX = {LEFT: KERN1_PREFIX, RIGHT: KERN2_PREFIX}


# - Keys -------------------------------------------------------------------
def core_key(key, side):
	'''UFO kerning key -> core key.'''
	key = str(key)
	if key.startswith(PREFIX[side]):
		return group_key(key[len(PREFIX[side]):])
	return key


def ufo_key(key, side):
	'''Core key -> UFO kerning key.'''
	if is_group(key):
		return PREFIX[side] + group_name(key)
	return key


# - Bridge -----------------------------------------------------------------
def master_names(font):
	names = [m.name for m in font.masters.data]
	return names or ['Default']


def master_locations(font):
	'''{master: {axis: value}} from the font's masters.'''
	return {m.name: dict(m.location or {}) for m in font.masters.data}


def kernset_from_font(font, masters=None):
	'''The font's kerning (every master, or the named ones) as a KernSet.'''
	names = master_names(font) if masters is None else list(masters)
	groups = {LEFT: {}, RIGHT: {}}
	for group in font.groups.data:
		for side in SIDES:
			if group.name.startswith(PREFIX[side]):
				groups[side][group.name[len(PREFIX[side]):]] = list(group.members)
	pairs = {}
	for name in names:
		kerning = font.kerning_for(name if font.masters.data else None)
		pairs[name] = {(core_key(p.first, LEFT), core_key(p.second, RIGHT)): p.value
		               for p in (kerning.data if kerning is not None else [])}
	return KernSet(names, pairs=pairs, groups=groups,
	               locations={m: loc for m, loc in master_locations(font).items() if m in names})


def apply_to_font(font, cs):
	'''Write a ChangeSet into a core Font (groups, then pairs per master).
	Returns {master: (set, removed, 0)}.'''
	for side in SIDES:
		for name, members in cs.groups[side].items():
			full = PREFIX[side] + name
			if members is None:
				font.groups.remove(full)
			else:
				# a glyph is in one kerning group per side
				for group in font.groups.data:
					if group.name.startswith(PREFIX[side]) and group.name != full:
						group.members = [g for g in group.members if g not in members]
				font.groups.set(full, list(members))
	out = {}
	for master, entry in cs.pairs.items():
		kerning = font.kerning_for(master if font.masters.data else None, create=True)
		for left, right in entry['remove']:
			kerning.remove_pair(ufo_key(left, LEFT), ufo_key(right, RIGHT))
		for (left, right), value in entry['set'].items():
			kerning.add_pair(ufo_key(left, LEFT), ufo_key(right, RIGHT), value)
		out[master] = (len(entry['set']), len(entry['remove']), 0)
	return out


# - Host -------------------------------------------------------------------
class CoreFontKernHost(object):
	'''TR Kern host on a core Font. path: where the font file lives (snapshots).'''

	def __init__(self, font, path=None):
		self.font = font
		self.path = path
		self.tabs = []		# open_tab texts (no editor: kept for the caller)

	def font_key(self):
		return id(self.font)

	def font_info(self):
		return {'family': str(self.font.info.family_name or ''),
		        'file': os.path.basename(self.path) if self.path else ''}

	def font_path(self):
		return self.path

	def font_dir(self):
		return os.path.dirname(self.path) if self.path else None

	def master_names(self):
		return master_names(self.font)

	def master_id(self, name):
		return name

	def master_locations(self):
		return master_locations(self.font)

	def read_kernset(self, masters=None):
		return kernset_from_font(self.font, masters)

	def apply(self, cs):
		return apply_to_font(self.font, cs)

	def name_tables(self):
		names, unicodes = [], {}
		for glyph in self.font.glyphs:
			names.append(glyph.name)
			for code in self.font.unicodes(glyph.name):
				try:
					unicodes.setdefault(int(code), glyph.name)
				except (TypeError, ValueError):
					pass
		return names, {}, unicodes

	def glyph_sets(self):
		'''Sets by the Unicode category of each glyph's character (no Glyphs data here).'''
		sets = {k: [] for k in ('Uppercase', 'Lowercase', 'Smallcaps', 'Figures', 'Marks', 'Other',
		                        'Alternates', 'Ligatures')}
		_names, _prod, unicodes = self.name_tables()
		chars = {}
		for code, glyph in unicodes.items():
			chars.setdefault(glyph, code)
		for glyph in self.font.glyphs:
			name = glyph.name
			code = chars.get(name)
			cat = unicodedata.category(chr(code)) if code is not None else ''
			if name.endswith(('.sc', '.smcp', '.c2sc')):
				sets['Smallcaps'].append(name)
			elif cat == 'Lu':
				sets['Uppercase'].append(name)
			elif cat == 'Ll':
				sets['Lowercase'].append(name)
			elif cat == 'Nd':
				sets['Figures'].append(name)
			elif cat.startswith('M'):
				sets['Marks'].append(name)
			else:
				sets['Other'].append(name)
			if '.' in name.strip('.'):
				sets['Alternates'].append(name)
			if '_' in name.strip('_'):
				sets['Ligatures'].append(name)
		return sets

	def components(self):
		'''{glyph: [component names]} of the default master layer, where core layers carry components.'''
		out = {}
		default = self.font.default_master_name()
		for glyph in self.font.glyphs:
			layer = None
			try:
				layer = glyph.layer(default) if default else (glyph.layers[0] if glyph.layers else None)
			except Exception:
				layer = None
			names = []
			for comp in (getattr(layer, 'components', None) or []):
				name = getattr(comp, 'name', None) or getattr(comp, 'base', None)
				if name:
					names.append(str(name))
			if names:
				out[glyph.name] = names
		return out

	def selected_names(self):
		return [g.name for g in self.font.glyphs if getattr(g, 'selected', False)]

	def current_pair(self):
		return None

	def open_tab(self, text):
		self.tabs.append(text)

	def show_pairs(self, pairs):
		self.tabs.append('\n'.join('/%s/%s' % p for p in pairs))

	def redraw(self):
		pass

	def load_data(self, key):
		raw = self.font.lib.get(key) if self.font.lib else None
		try:
			return json.loads(raw) if raw else None
		except (TypeError, ValueError):
			return None

	def save_data(self, key, data):
		if self.font.lib is None:
			self.font.lib = {}
		self.font.lib[key] = json.dumps(data)
		return True
