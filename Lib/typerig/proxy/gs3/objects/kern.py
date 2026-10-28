# MODULE: TypeRig / Proxy / Glyphs 3 / Kern
# -----------------------------------------------------------
# Glyphs 3 / 4 kerning I/O in core keys (core/algo/kern_model.py):
# '@name' for a group (side from its place in the pair), a glyph name
# for an exception. Glyphs keeps:
#   - kerning per master: font.kerning[master.id][left][right] (LTR);
#     left keys @MMK_L_<glyph.rightKerningGroup> or a glyph id,
#     right keys @MMK_R_<glyph.leftKerningGroup> or a glyph id;
#   - groups per glyph, font wide: rightKerningGroup is the group a glyph
#     has on the LEFT side of a pair, leftKerningGroup on the RIGHT side.
# Writes go through font.setKerningForPair / removeKerningForPair (names,
# not ids). LTR only (RTL / vertical: later).
#
# Functions take a GSFont, so any Glyphs host can use them (TR Kern,
# Delta Machine). GlyphsKernHost is TR Kern's document access.
# All GlyphsApp imports are lazy: engines run headless with a fake host.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os

from typerig.core.algo.kern_model import KernSet, LEFT, RIGHT, SIDES, is_group, group_name

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
GS_LEFT, GS_RIGHT = '@MMK_L_', '@MMK_R_'
GROUP_ATTR = {LEFT: 'rightKerningGroup', RIGHT: 'leftKerningGroup'}	# glyph attribute per pair side


# - Keys -------------------------------------------------------------------
def core_key(font, key):
	'''Glyphs kerning key -> core key ('@name' or glyph name).'''
	key = str(key)
	if key.startswith(GS_LEFT) or key.startswith(GS_RIGHT):
		return '@' + key[len(GS_LEFT):]
	if key.startswith('@'):
		return key
	glyph = font.glyphForId_(key) if hasattr(font, 'glyphForId_') else None
	if glyph is None:
		try:
			glyph = font.glyphs[key]
		except Exception:
			glyph = None
	return str(glyph.name) if glyph is not None else key


def gs_key(key, side):
	'''Core key -> the name setKerningForPair takes.'''
	key = str(key)
	if is_group(key):
		return (GS_LEFT if side == LEFT else GS_RIGHT) + group_name(key)
	return key


# - Read -------------------------------------------------------------------
def master_table(font, master_id):
	'''LTR kerning of a master as {(left, right): value}, core keys.'''
	if font is None or master_id is None:
		return {}
	try:
		table = font.kerning[master_id]
	except Exception:
		return {}
	out = {}
	for left, rights in (table or {}).items():
		l = core_key(font, left)
		for right, value in rights.items():
			try:
				out[(l, core_key(font, right))] = float(value)
			except (TypeError, ValueError):
				pass
	return out


def kerning_groups(font):
	'''{'left': {group: [glyphs]}, 'right': {group: [glyphs]}} from the glyphs.'''
	out = {LEFT: {}, RIGHT: {}}
	for glyph in (font.glyphs if font is not None else []):
		for side in SIDES:
			name = getattr(glyph, GROUP_ATTR[side], None)
			if name:
				out[side].setdefault(str(name), []).append(str(glyph.name))
	return out


def name_tables(font):
	'''(glyph names, {production name: glyph}, {codepoint: glyph}) for import name mapping.'''
	names, production, unicodes = [], {}, {}
	for glyph in (font.glyphs if font is not None else []):
		name = str(glyph.name)
		names.append(name)
		try:
			prod = glyph.productionName
		except Exception:
			prod = None
		if prod and str(prod) != name:
			production[str(prod)] = name
		for uni in (getattr(glyph, 'unicodes', None) or []):
			try:
				unicodes.setdefault(int(str(uni), 16), name)
			except ValueError:
				pass
	return names, production, unicodes


# - Write ------------------------------------------------------------------
def write_pairs(font, master_id, sets, remove=()):
	'''Set pairs {(left, right): value} and remove pairs in a master (LTR,
	core keys). Removes first. Returns (set, removed, failed).'''
	if font is None or master_id is None:
		return 0, 0, len(sets) + len(remove)
	done = gone = failed = 0
	try:
		font.disableUpdateInterface()
	except Exception:
		pass
	try:
		for (left, right) in remove:
			try:
				font.removeKerningForPair(master_id, gs_key(left, LEFT), gs_key(right, RIGHT))
				gone += 1
			except Exception:
				failed += 1
		for (left, right), value in sets.items():
			try:
				font.setKerningForPair(master_id, gs_key(left, LEFT), gs_key(right, RIGHT), value)
				done += 1
			except Exception:
				failed += 1
	finally:
		try:
			font.enableUpdateInterface()
		except Exception:
			pass
	return done, gone, failed


def write_groups(font, side, name, members):
	'''Make group `name` on a side hold exactly `members` (None removes the
	group). Glyphs not in the font are skipped. Returns glyphs changed.'''
	attr = GROUP_ATTR[side]
	wanted = set(members or [])
	changed = 0
	for glyph in font.glyphs:
		current = getattr(glyph, attr, None)
		gname = str(glyph.name)
		if gname in wanted and current != name:
			setattr(glyph, attr, name)
			changed += 1
		elif gname not in wanted and current == name:
			setattr(glyph, attr, None)
			changed += 1
	return changed


# - Host -------------------------------------------------------------------
class GlyphsKernHost(object):
	'''Glyphs 3 / 4 access for the TR Kern engine (fake it in tests).'''

	def _font(self):
		from GlyphsApp import Glyphs
		return Glyphs.font

	def font_key(self):
		'''Identity of the current font: the ObjC pointer (Glyphs may hand
		out a new Python wrapper on each access).'''
		font = self._font()
		if font is None:
			return None
		try:
			import objc
			return objc.pyobjc_id(font)
		except Exception:
			return id(font)

	def font_info(self):
		font = self._font()
		if font is None:
			return {}
		path = getattr(font, 'filepath', None)
		return {'family': str(font.familyName or ''), 'file': os.path.basename(path) if path else ''}

	def font_path(self):
		font = self._font()
		path = getattr(font, 'filepath', None) if font is not None else None
		return str(path) if path else None

	def font_dir(self):
		path = self.font_path()
		return os.path.dirname(path) if path else None

	def master_names(self):
		font = self._font()
		return [str(m.name) for m in font.masters] if font is not None else []

	def master_id(self, name):
		font = self._font()
		if font is None:
			return None
		return next((m.id for m in font.masters if m.name == name), None)

	def master_locations(self):
		'''{master: {axis name: value}} (Glyphs 3 / 4 master axis values).'''
		font = self._font()
		out = {}
		if font is None:
			return out
		axes = [str(getattr(a, 'name', '') or getattr(a, 'axisTag', '')) for a in (getattr(font, 'axes', None) or [])]
		for master in font.masters:
			values = getattr(master, 'axes', None)
			if values is None:
				values = getattr(master, 'internalAxesValues', None)
			try:
				values = list(values or [])
			except TypeError:
				values = []
			out[str(master.name)] = {a: float(v) for a, v in zip(axes, values) if a}
		return out

	def read_kernset(self, masters=None):
		'''The font's kerning as a KernSet (all masters, or the named ones), with master locations.'''
		font = self._font()
		names = self.master_names() if masters is None else list(masters)
		pairs = {name: master_table(font, self.master_id(name)) for name in names}
		locations = {m: loc for m, loc in self.master_locations().items() if m in names}
		return KernSet(names, pairs=pairs, groups=kerning_groups(font), locations=locations)

	def name_tables(self):
		return name_tables(self._font())

	def apply(self, cs):
		'''Write a ChangeSet (groups, then pairs per master).
		Returns {master: (set, removed, failed)}.'''
		font = self._font()
		out = {}
		if font is None:
			return out
		for side in SIDES:
			for name, members in cs.groups[side].items():
				write_groups(font, side, name, members)
		for master, entry in cs.pairs.items():
			out[master] = write_pairs(font, self.master_id(master), entry['set'], entry['remove'])
		return out

	def selected_names(self):
		'''Glyphs selected in Glyphs: the Font view selection, or the selected glyphs of the edit tab.'''
		font = self._font()
		names = []
		for layer in (font.selectedLayers or []) if font is not None else []:
			glyph = getattr(layer, 'parent', None)		# GSControlLayer line breaks have none
			name = getattr(glyph, 'name', None)
			if name and str(name) not in names:
				names.append(str(name))
		return names

	def components(self):
		'''{glyph: [component glyph names]} of the first master layer (auto groups).'''
		font = self._font()
		out = {}
		if font is None or not len(font.masters):
			return out
		mid = font.masters[0].id
		for glyph in font.glyphs:
			layer = glyph.layers[mid]
			names = [str(c.componentName) for c in (getattr(layer, 'components', None) or []) if c.componentName]
			if names:
				out[str(glyph.name)] = names
		return out

	def glyph_sets(self):
		'''{set name: [glyphs]} for proof strings (*Uppercase, *Lowercase, ...).'''
		from typerig.proxy.gs3.gui.glyph_filters import glyph_kind
		names = {'Figure': 'Figures', 'Mark': 'Marks'}
		sets = {k: [] for k in ('Uppercase', 'Lowercase', 'Smallcaps', 'Figures', 'Marks', 'Other',
		                        'Alternates', 'Ligatures')}
		font = self._font()
		for glyph in (font.glyphs if font is not None else []):
			name = str(glyph.name)
			try:
				kind = glyph_kind(glyph)
			except Exception:
				kind = 'Other'
			sets[names.get(kind, kind)].append(name)
			if '.' in name.strip('.'):
				sets['Alternates'].append(name)
			if '_' in name.strip('_'):
				sets['Ligatures'].append(name)
		return sets

	def current_pair(self):
		'''(left, right) glyph names around the text cursor of the active edit tab, or None.'''
		font = self._font()
		tab = getattr(font, 'currentTab', None) if font is not None else None
		if tab is None:
			return None
		try:
			layers = list(tab.layers)
			cursor = int(tab.textCursor)
		except Exception:
			return None
		if not 0 < cursor < len(layers):
			return None
		glyphs = [getattr(layers[i], 'parent', None) for i in (cursor - 1, cursor)]
		if any(g is None or not getattr(g, 'name', None) for g in glyphs):
			return None		# a line break (GSControlLayer) on one side
		return str(glyphs[0].name), str(glyphs[1].name)

	def open_tab(self, text):
		font = self._font()
		if font is not None and text:
			font.newTab(text)

	def show_pairs(self, pairs):
		'''The (left, right) glyph pairs as the text of the active edit tab
		(a new tab when none), one per line, the text cursor between the
		first two glyphs.'''
		font = self._font()
		if font is None or not pairs:
			return
		text = '\n'.join('/%s/%s' % p for p in pairs)
		tab = getattr(font, 'currentTab', None)
		if tab is None:
			tab = font.newTab(text)
		else:
			tab.text = text
		try:
			tab.textCursor = 1
			tab.textRange = 0
		except Exception:
			pass

	def redraw(self):
		try:
			from GlyphsApp import Glyphs
			Glyphs.redraw()
		except Exception:
			pass

	# - Font storage ----------------------------------------------------------
	def load_data(self, key):
		'''JSON stored in font.userData[key] (None when there is none).'''
		font = self._font()
		if font is None:
			return None
		try:
			raw = font.userData[key]
			return json.loads(raw) if raw else None
		except Exception:
			return None

	def save_data(self, key, data):
		font = self._font()
		if font is None:
			return False
		try:
			font.userData[key] = json.dumps(data)
			return True
		except Exception:
			return False
