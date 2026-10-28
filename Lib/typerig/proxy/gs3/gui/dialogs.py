# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — dialogs
#
# ask_choices(): modal alert with one popup per choice (a deliberate,
# confirmed choice before an operation, e.g. TR Kern Analyze > Fix). It is
# an NSAlert, not a second vanilla window (Memory/feedback_vanilla_pyobjc_crashes).
#
# TRLayerSelectDialog: vanilla port of FontLab's TRLayerSelectNEW.
# Modeless, always-on-top, single-instance picker bound to the masthead's
# "Selected layers" pill. Mutates the controller's selected_layer_names
# list live as the user toggles checkboxes. Mirrors FL/FontRig parity in
# behaviour; only the *display* of layer types uses native Glyphs naming.
#
# Layer-type display (Glyphs-accurate, per user's instruction):
#   Master   — green tint
#   Mask     — red tint    (user-named mask layers, if any)
#   Brace    — blue tint   (intermediate / "brace" layers)
#   Bracket  — blue tint   (alternate / "bracket" layers)
#   Color    — white       (color-palette layers)
#   Layer    — white       (anything else)
#
# pLayers contract (FL-identical, polymorphic):
#   * tuple form  : (active_bool, masters_bool, False, False)
#   * checked-rows form (Selected mode):
#       [(layer_name, layer_type), ...]   — only the *checked* rows
#   gui/scope.scope_layers() handles both shapes.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import json
import os

import vanilla
from AppKit import (
	NSFloatingWindowLevel,
	NSOpenPanel,
	NSSavePanel,
)
from objc import python_method

from .widgets import IconButton
from .config  import UI

# - Reverse-domain key contract (mirrors FL TRMasterValuesDLG) ----------------
TR_LIB_KEY_PREFIX        = 'com.typerig.'
TR_MASTER_VALUES_FORMAT  = 'typerig.master_values/1'

# - Layout constants ------------------------------------------------------
# Dialog-specific tight layout. Values live on UI.DIALOG (single source of
# truth); the aliases below are local readability sugar only.
WIN_W, WIN_H   = UI.DIALOG.LP_W, UI.DIALOG.LP_H   # legacy TRLayerSelectDialog
PAD            = UI.DIALOG.PAD
ROW_H          = UI.DIALOG.ROW_H
BTN_W          = UI.DIALOG.BTN_W
BTN_GAP        = UI.DIALOG.BTN_GAP
SEARCH_H       = UI.DIALOG.SEARCH_H
TABLE_TOP      = PAD + ROW_H + ROW_H + PAD


# - Layer-kind detection (Glyphs-accurate naming) -------------------------
def layer_kind(layer):
	'''Return the Glyphs-accurate type name for a GSLayer.'''
	# Order matters: Master takes precedence; explicit mask layers (rare in
	# pure GS3 but possible via naming) come next; brace/bracket are
	# variant-like layers; color = colour-palette layer; otherwise generic.
	try:
		if getattr(layer, 'isMasterLayer', False):
			return 'Master'
	except Exception:
		pass
	# Glyphs marks mask layers via the layer name (`_<master>` etc.) or
	# attributes — be defensive and check several spellings.
	for attr in ('isMaskLayer', '_isMask', 'isMask'):
		try:
			if getattr(layer, attr, False):
				return 'Mask'
		except Exception:
			pass
	try:
		if getattr(layer, 'isBraceLayer', False):
			return 'Brace'
	except Exception:
		pass
	try:
		if getattr(layer, 'isBracketLayer', False):
			return 'Bracket'
	except Exception:
		pass
	try:
		if getattr(layer, 'isColorPaletteLayer', False):
			return 'Color'
	except Exception:
		pass
	return 'Layer'


# - Inline layer picker (preferred since 2026-10-16) ----------------------
#
# Replaces TRLayerSelectDialog's second FloatingWindow. The dialog form is
# retained in this file as legacy only — it crashed Glyphs 4 on close via
# its own X button on the current pyobjc build, and nesting two vanilla
# FloatingWindows that reference each other proved fragile. The inline
# picker lives inside the main panel's own FloatingWindow and has the
# same public API (refresh / set_mode / get_table / get_checked_names),
# so the controller side is unchanged in shape.

class TRLayerPickerInline(object):
	'''Inline (non-dialog) layer picker embedded in the main panel.

	Args:
		container: a vanilla.Group (or any container that accepts
			attribute-based child widgets) created by the main panel.
			The picker builds its own action row + search + table into it.
		controller: TRMainPanel-like object exposing `layers_refresh()`
			and `selected_layer_names` (list[str]) which this picker
			keeps in sync. The controller is also responsible for the
			Selected pill; the picker calls back to activate it when
			the user checks any row (see `_push_state`).
		mode (int): 0 = current glyph's layers (with type column);
			1 = font masters list.
	'''

	def __init__(self, container, controller, mode=0):
		self.container  = container
		self.controller = controller
		self.mode       = mode
		self._font      = None
		self._glyph     = None

		# Row storage: master list and filtered view.
		self._all_rows     = []
		self._visible_rows = []

		# Layout constants pulled from the UI namespace so the picker's
		# action-row buttons line up with the masthead above it.
		MARGIN   = UI.LAYOUT.MARGIN
		GAP      = UI.LAYOUT.GAP
		BTN      = UI.BTN.SIZE
		TOP      = MARGIN
		ROW2_Y   = TOP + BTN + GAP
		TABLE_Y  = ROW2_Y + UI.SPN.H + GAP

		# Action row (left-aligned actions, refresh on the right) ---------
		x = MARGIN
		self.container.btn_check = IconButton(
			(x, TOP, BTN, BTN), 'select_all',
			tooltip='Select all\n<Shift> + Click deselect all\n<Alt> + Click swap selection',
			callback=self._on_check_all,
		)
		x += BTN + GAP
		self.container.btn_swap = IconButton(
			(x, TOP, BTN, BTN), 'select_swap',
			tooltip='Swap selection',
			callback=self._on_swap,
		)
		x += BTN + GAP
		self.container.btn_master = IconButton(
			(x, TOP, BTN, BTN), 'layer_master',
			tooltip='Master layers\n<Shift> + Click deselect all',
			callback=self._on_check_masters,
		)
		x += BTN + GAP
		self.container.btn_mask = IconButton(
			(x, TOP, BTN, BTN), 'layer_mask',
			tooltip='Mask layers\n<Shift> + Click deselect all',
			callback=self._on_check_masks,
		)
		self.container.btn_refresh = IconButton(
			(-MARGIN - BTN, TOP, BTN, BTN), 'refresh',
			tooltip='Refresh layer list',
			callback=lambda s: self.refresh(),
		)

		# Search row
		self.container.search = vanilla.EditText(
			(MARGIN, ROW2_Y, -MARGIN - BTN - GAP, UI.SPN.H),
			placeholder='Filter: Layer Name',
			sizeStyle=UI.SPN.SIZE_STYLE,
			callback=self._on_search,
		)
		self.container.btn_clear = IconButton(
			(-MARGIN - BTN, ROW2_Y, BTN, BTN), 'close',
			tooltip='Clear search',
			callback=lambda s: self._set_search(''),
		)

		# Table — fills the rest of the picker band.
		self.container.table = vanilla.List(
			(0, TABLE_Y, -0, -0),
			[],
			columnDescriptions=[
				dict(title='', key='checked',
				     cell=vanilla.CheckBoxListCell(),
				     width=UI.LIST.COL_CHECK_W, editable=True),
				dict(title='Layer Name', key='name', editable=False),
				dict(title='Layer Type', key='type', editable=False,
				     width=UI.LIST.COL_TYPE_W),
			],
			editCallback=self._on_cell_edit,
			showColumnTitles=True,
			drawFocusRing=False,
		)

		self.refresh()

	# - Public API ---------------------------------------------------------
	def set_mode(self, mode):
		if mode != self.mode:
			self.mode = mode
			self.refresh()

	def get_table(self):
		'''[(name, type), …] for the *checked* rows — the FL-shaped pLayers.'''
		return [(r['name'], r['type']) for r in self._all_rows if r['checked']]

	def get_checked_names(self):
		return [r['name'] for r in self._all_rows if r['checked']]

	def refresh(self, font=None, glyph=None):
		previously_checked = {r['name'] for r in self._all_rows if r['checked']}

		font  = font  or self._font  or self._resolve_font()
		glyph = glyph or self._glyph or self._resolve_glyph(font)

		rows = []
		if self.mode == 0 and glyph is not None:
			for layer in glyph.layers:
				name = layer.name
				if not name or name.startswith('#'):
					continue
				rows.append({
					'name':    name,
					'type':    layer_kind(layer),
					'checked': name in previously_checked,
				})
		elif font is not None:
			for master in font.masters:
				name = master.name
				rows.append({
					'name':    name,
					'type':    'Master',
					'checked': name in previously_checked,
				})

		self._all_rows = rows
		self._apply_filter()

	# - Internals ----------------------------------------------------------
	def _resolve_font(self):
		try:
			from GlyphsApp import Glyphs
			return Glyphs.font
		except Exception:
			return None

	def _resolve_glyph(self, font):
		try:
			if font and font.selectedLayers:
				return font.selectedLayers[0].parent
		except Exception:
			pass
		return None

	def _apply_filter(self):
		needle = (self.container.search.get() or '').strip().lower()
		if needle:
			self._visible_rows = [r for r in self._all_rows
			                      if needle in r['name'].lower()]
		else:
			self._visible_rows = list(self._all_rows)
		self.container.table.set(self._visible_rows)
		try:
			self.container.table.getNSTableView().reloadData()
		except Exception:
			pass

	def _set_search(self, text):
		self.container.search.set(text)
		self._apply_filter()

	def _push_state(self):
		'''Sync checked rows → controller.selected_layer_names and tell
		the controller to re-broadcast pLayers to the panel modules.'''
		try:
			self.controller.selected_layer_names = self.get_checked_names()
		except Exception:
			pass
		try:
			self.controller.layers_refresh()
		except Exception:
			pass

	# - Callbacks ----------------------------------------------------------
	def _on_search(self, sender):
		self._apply_filter()

	def _on_cell_edit(self, sender):
		visible = sender.get()
		state_by_name = {r['name']: bool(r['checked']) for r in visible}
		for r in self._all_rows:
			if r['name'] in state_by_name:
				r['checked'] = state_by_name[r['name']]
		self._push_state()

	def _modifiers(self):
		try:
			from AppKit import NSEvent, NSEventModifierFlagShift, NSEventModifierFlagOption
			flags = NSEvent.modifierFlags()
			return bool(flags & NSEventModifierFlagShift), bool(flags & NSEventModifierFlagOption)
		except Exception:
			return False, False

	def _set_checked(self, predicate, value=True, swap=False):
		for r in self._all_rows:
			if predicate(r):
				if swap:
					r['checked'] = not r['checked']
				else:
					r['checked'] = bool(value)
		self._apply_filter()
		self._push_state()

	def _on_check_all(self, sender):
		shift, alt = self._modifiers()
		if alt:
			self._set_checked(lambda r: True, swap=True)
		elif shift:
			self._set_checked(lambda r: True, value=False)
		else:
			visible_names = {r['name'] for r in self._visible_rows}
			self._set_checked(lambda r: r['name'] in visible_names, value=True)

	def _on_swap(self, sender):
		self._set_checked(lambda r: True, swap=True)

	def _on_check_masters(self, sender):
		shift, _alt = self._modifiers()
		self._set_checked(lambda r: r['type'] == 'Master',
		                  value=False if shift else True)

	def _on_check_masks(self, sender):
		shift, _alt = self._modifiers()
		self._set_checked(lambda r: r['type'] == 'Mask',
		                  value=False if shift else True)


# - The legacy dialog (unused since 2026-10-16; kept for reference) -------
class TRLayerSelectDialog(object):
	'''Modeless layer-picker dialog.

	Args:
		controller: TRMainPanel-like object exposing `layers_refresh()`
			(called on every checkbox change) and `selected_layer_names`
			(list[str]) which this dialog keeps in sync.
		mode (int): 0 = current glyph's layers (with type column);
		            1 = font masters list.
		font: optional Glyphs font object; if None, resolved from
			`Glyphs.font` at refresh time.
		glyph: optional GSGlyph; if None, resolved from
			`Glyphs.font.selectedLayers[0].parent` at refresh time.
	'''
	def __init__(self, controller, mode=0, font=None, glyph=None):
		self.controller = controller
		self.mode       = mode
		self._font      = font
		self._glyph     = glyph

		# Internal data: master list of {'name', 'type', 'checked'}.
		self._all_rows     = []
		self._visible_rows = []

		# - Window
		self.w = vanilla.FloatingWindow(
			(WIN_W, WIN_H),
			'Select Layers',
			minSize=(UI.DIALOG.LP_MIN_W, UI.DIALOG.LP_MIN_H),
			autosaveName='com.kateliev.TypeRigPanel.layerselect',
		)
		self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)

		# - Action row (5 IconButtons; FL parity, no per-kind shortcuts)
		x = PAD
		self.w.btn_check  = IconButton((x, PAD, BTN_W, BTN_W), 'select_all',
			tooltip='Select all\n<Shift> + Click deselect all\n<Alt> + Click swap selection',
			callback=self._on_check_all)
		x += BTN_W + BTN_GAP
		self.w.btn_swap   = IconButton((x, PAD, BTN_W, BTN_W), 'select_swap',
			tooltip='Swap selection',
			callback=self._on_swap)
		x += BTN_W + BTN_GAP
		self.w.btn_master = IconButton((x, PAD, BTN_W, BTN_W), 'layer_master',
			tooltip='Master layers\n<Shift> + Click deselect all',
			callback=self._on_check_masters)
		x += BTN_W + BTN_GAP
		self.w.btn_mask   = IconButton((x, PAD, BTN_W, BTN_W), 'layer_mask',
			tooltip='Mask layers\n<Shift> + Click deselect all',
			callback=self._on_check_masks)
		# Refresh on the far right of the action row.
		self.w.btn_refresh = IconButton((-PAD - BTN_W, PAD, BTN_W, BTN_W), 'refresh',
			tooltip='Refresh layer list',
			callback=lambda s: self.refresh())

		# - Search row
		y2 = PAD + BTN_W + BTN_GAP
		self.w.search = vanilla.EditText(
			(PAD, y2, -PAD - BTN_W - BTN_GAP, SEARCH_H),
			placeholder='Filter: Layer Name',
			callback=self._on_search,
		)
		self.w.btn_clear = IconButton(
			(-PAD - BTN_W, y2 - 3, BTN_W, BTN_W), 'close',
			tooltip='Clear search',
			callback=lambda s: self._set_search(''),
		)

		# - Table
		self.w.table = vanilla.List(
			(0, TABLE_TOP, -0, -0),
			[],
			columnDescriptions=[
				dict(title='', key='checked',
				     cell=vanilla.CheckBoxListCell(),
				     width=UI.LIST.COL_CHECK_W, editable=True),
				dict(title='Layer Name', key='name', editable=False),
				dict(title='Layer Type', key='type', editable=False,
				     width=UI.LIST.COL_TYPE_W),
			],
			editCallback=self._on_cell_edit,
			showColumnTitles=True,
			drawFocusRing=False,
		)

		# Initial population.
		self.refresh()

	# - Public API ---------------------------------------------------------
	def show(self):
		self.w.show()
		self.w.getNSWindow().makeKeyAndOrderFront_(None)

	def hide(self):
		self.w.hide()

	def set_mode(self, mode):
		'''Switch between glyph-layers (0) and font-masters (1).'''
		if mode != self.mode:
			self.mode = mode
			self.refresh()

	def get_table(self):
		'''Return the FL-shaped list of *checked* rows: [(name, type), ...].

		This is what the controller assigns to `pLayers` when in Selected
		mode, mirroring FL's `dlg_layer.tab_masters.getTable()`.
		'''
		return [(r['name'], r['type']) for r in self._all_rows if r['checked']]

	def get_checked_names(self):
		'''Convenience: just the list of checked layer names.'''
		return [r['name'] for r in self._all_rows if r['checked']]

	def refresh(self, font=None, glyph=None):
		'''Repopulate the table from the current font/glyph.'''
		# Preserve check state across refreshes by name.
		previously_checked = {r['name'] for r in self._all_rows if r['checked']}

		font  = font  or self._font  or self._resolve_font()
		glyph = glyph or self._glyph or self._resolve_glyph(font)

		rows = []
		if self.mode == 0 and glyph is not None:
			for layer in glyph.layers:
				name = layer.name
				if not name or name.startswith('#'):
					continue
				rows.append({
					'name':    name,
					'type':    layer_kind(layer),
					'checked': name in previously_checked,
				})
		elif font is not None:
			for master in font.masters:
				name = master.name
				rows.append({
					'name':    name,
					'type':    'Master',
					'checked': name in previously_checked,
				})

		self._all_rows = rows
		self._apply_filter()

	# - Internals ----------------------------------------------------------
	def _resolve_font(self):
		try:
			from GlyphsApp import Glyphs
			return Glyphs.font
		except Exception:
			return None

	def _resolve_glyph(self, font):
		try:
			if font and font.selectedLayers:
				return font.selectedLayers[0].parent
		except Exception:
			pass
		return None

	def _apply_filter(self):
		needle = (self.w.search.get() or '').strip().lower()
		if needle:
			self._visible_rows = [r for r in self._all_rows
			                      if needle in r['name'].lower()]
		else:
			self._visible_rows = list(self._all_rows)
		self.w.table.set(self._visible_rows)
		# Re-tint after data change.
		try:
			self.w.table.getNSTableView().reloadData()
		except Exception:
			pass

	def _set_search(self, text):
		self.w.search.set(text)
		self._apply_filter()

	def _push_state(self):
		'''Sync the controller's selection list and notify it.'''
		try:
			self.controller.selected_layer_names = self.get_checked_names()
		except Exception:
			pass
		try:
			self.controller.layers_refresh()
		except Exception:
			pass

	# - Callbacks ----------------------------------------------------------
	def _on_search(self, sender):
		self._apply_filter()

	def _on_cell_edit(self, sender):
		# Sync visible_rows back into all_rows by name.
		visible = sender.get()
		state_by_name = {r['name']: bool(r['checked']) for r in visible}
		for r in self._all_rows:
			if r['name'] in state_by_name:
				r['checked'] = state_by_name[r['name']]
		self._push_state()

	def _modifiers(self):
		'''Read live keyboard modifiers (Shift / Alt). Returns (shift, alt).'''
		try:
			from AppKit import NSEvent, NSEventModifierFlagShift, NSEventModifierFlagOption
			flags = NSEvent.modifierFlags()
			return bool(flags & NSEventModifierFlagShift), bool(flags & NSEventModifierFlagOption)
		except Exception:
			return False, False

	def _set_checked(self, predicate, value=True, swap=False):
		'''Apply a check operation to all rows where predicate(row) is True.'''
		for r in self._all_rows:
			if predicate(r):
				if swap:
					r['checked'] = not r['checked']
				else:
					r['checked'] = bool(value)
		self._apply_filter()
		self._push_state()

	def _on_check_all(self, sender):
		shift, alt = self._modifiers()
		if alt:
			self._set_checked(lambda r: True, swap=True)
		elif shift:
			self._set_checked(lambda r: True, value=False)
		else:
			# Only apply to currently-visible (filtered) rows, like FL.
			visible_names = {r['name'] for r in self._visible_rows}
			self._set_checked(lambda r: r['name'] in visible_names, value=True)

	def _on_swap(self, sender):
		self._set_checked(lambda r: True, swap=True)

	def _on_check_masters(self, sender):
		shift, _alt = self._modifiers()
		self._set_checked(lambda r: r['type'] == 'Master',
		                  value=False if shift else True)

	def _on_check_masks(self, sender):
		shift, _alt = self._modifiers()
		self._set_checked(lambda r: r['type'] == 'Mask',
		                  value=False if shift else True)


# - Universal per-master numeric value editor --------------------------------
# Vanilla port of FontLab's TRMasterValuesDLG (in
# typerig/proxy/fl/gui/dialogs.py). Same constructor contract, same JSON
# file format, same lib_key reverse-domain prefix, so values round-trip
# between hosts via either packageLib<->userData (manual) or JSON export.
#
# Storage in Glyphs: font.userData[lib_key] -> dict[master_name -> float]
def read_master_values(font, lib_key):
	'''Per-master values stored by TRMasterValuesDialog: font.userData[lib_key]
	as dict[master_name -> float], or {} if absent or malformed. Same reading
	as TR Panel Node's _read_lib_dict, shared for Toolbars.'''
	if font is None:
		return {}
	try:
		ud  = font.userData
		raw = ud.get(lib_key) if hasattr(ud, 'get') else ud[lib_key]
	except Exception:
		return {}
	if raw is None:
		return {}
	try:
		items = raw.items() if hasattr(raw, 'items') else dict(raw).items()
	except Exception:
		return {}
	out = {}
	for k, v in items:
		try:
			out[str(k)] = float(v)
		except (TypeError, ValueError):
			continue
	return out


class TRMasterValuesDialog(object):
	'''Modal-style per-master numeric value editor.

	Args:
		font          : GSFont      - required; provides .masters and .userData
		lib_key       : str         - required; full reverse-domain key
		                              (must start with 'com.typerig.')
		title         : str         - window title (default derived from lib_key)
		message       : str         - text shown above the table
		value_label   : str         - header for the value column
		value_type    : type        - float (default) or int
		value_default : float       - shown for masters with no entry yet
		value_range   : tuple       - (min, max, step) - reserved for future use
		autoload      : bool        - load from font.userData on open
		size          : tuple       - (w, h) initial window size
		callback      : callable    - on OK: callback(values_dict). On Cancel: not called.

	After exec(): self.values is dict[master_name -> value] or None on cancel.
	'''

	# Column widths
	_NAME_W = UI.DIALOG.MV_NAME_W

	def __init__(self, font, lib_key,
	             title=None, message=None,
	             value_label='Value', value_type=float,
	             value_default=0.0, value_range=(-10000.0, 10000.0, 1.0),
	             autoload=True, size=(UI.DIALOG.MV_W, UI.DIALOG.MV_H),
	             callback=None):

		if not isinstance(lib_key, str) or not lib_key.startswith(TR_LIB_KEY_PREFIX):
			raise ValueError("TRMasterValuesDialog: lib_key must start with %r (got %r)"
			                 % (TR_LIB_KEY_PREFIX, lib_key))

		self.tr_font       = font
		self.lib_key       = lib_key
		self.value_label   = value_label
		self.value_type    = value_type
		self.value_default = float(value_default)
		self.values        = None
		self.changed       = False
		self._callback     = callback
		self._initial_data = {}

		# Master ordering frozen at open-time
		try:
			self.master_names = [m.name for m in self.tr_font.masters]
		except Exception:
			self.master_names = []
		self._known_set = set(self.master_names)

		w, h = size
		self.w = vanilla.Window(
			(w, h),
			title or 'Master values - %s' % lib_key,
			minSize=(UI.DIALOG.MV_MIN_W, UI.DIALOG.MV_MIN_H),
		)
		self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)

		# - Layout constants (local aliases; values live on UI.DIALOG)
		PAD     = UI.DIALOG.MV_PAD
		LBL_H   = UI.DIALOG.MV_LBL_H
		BTN_H   = UI.DIALOG.MV_BTN_H
		BTN_GAP = UI.DIALOG.MV_BTN_GAP
		BTN_ROW = BTN_H + BTN_GAP

		# - Message
		self.w.lbl = vanilla.TextBox(
			(PAD, PAD, -PAD, LBL_H),
			message or 'Set a value for each master:',
		)

		# - Table
		table_top    = PAD + LBL_H
		table_bottom = -(PAD + BTN_ROW * 3)
		self.w.table = vanilla.List(
			(0, table_top, -0, table_bottom),
			[],
			columnDescriptions=[
				dict(title='Master',         key='name',  width=self._NAME_W, editable=False),
				dict(title=self.value_label, key='value',                       editable=True),
			],
			editCallback=self._on_cell_edit,
			showColumnTitles=True,
			drawFocusRing=False,
		)

		# - Buttons: 2x2 grid for I/O + Cancel/OK row
		half = (w - PAD * 3) // 2
		y = -(PAD + BTN_ROW * 3)

		self.w.btn_font_load = vanilla.Button(
			(PAD,           y, half, BTN_H), 'Load from Font',
			callback=self._on_font_load)
		self.w.btn_font_save = vanilla.Button(
			(PAD * 2 + half, y, half, BTN_H), 'Save to Font',
			callback=self._on_font_save)
		y += BTN_ROW

		self.w.btn_file_load = vanilla.Button(
			(PAD,           y, half, BTN_H), 'Load from JSON',
			callback=self._on_file_load)
		self.w.btn_file_save = vanilla.Button(
			(PAD * 2 + half, y, half, BTN_H), 'Save to JSON',
			callback=self._on_file_save)
		y += BTN_ROW

		self.w.btn_cancel = vanilla.Button(
			(PAD,           y, half, BTN_H), 'Cancel',
			callback=self._on_cancel)
		self.w.btn_ok = vanilla.Button(
			(PAD * 2 + half, y, half, BTN_H), 'OK',
			callback=self._on_ok)

		# - Populate
		self._dict_to_table({})
		if autoload:
			data, present = self._read_font_lib()
			if present and data:
				self._dict_to_table(data)
		self._initial_data = self._table_to_dict()

	# - Public ----------------------------------------------------------------
	def show(self):
		'''Non-modal show. Use run_modal() if you need a blocking dialog.'''
		self.w.open()
		self.w.getNSWindow().makeKeyAndOrderFront_(None)

	def run_modal(self):
		'''Show as a true modal window using NSApp's modal loop.

		Returns the user's values dict, or None if they cancelled. Blocks
		until the user clicks OK/Cancel; widgets remain responsive because
		NSApp drives the run loop properly (a hand-rolled
		nextEventMatchingMask spin loop will freeze vanilla widgets).
		'''
		from AppKit import NSApp
		ns_window = self.w.getNSWindow()
		# vanilla.Window doesn't open the NSWindow until .open(); do it
		# ourselves so runModalForWindow_ has a window to attach to.
		self.w.open()
		ns_window.makeKeyAndOrderFront_(None)
		self._modal_session = NSApp().beginModalSessionForWindow_(ns_window)
		try:
			# Loop until OK/Cancel calls _stop_modal().
			from AppKit import NSRunContinuesResponse
			while NSApp().runModalSession_(self._modal_session) == NSRunContinuesResponse:
				pass
		finally:
			NSApp().endModalSession_(self._modal_session)
			self._modal_session = None
		return self.values

	def _stop_modal(self):
		try:
			from AppKit import NSApp
			NSApp().stopModal()
		except Exception:
			pass

	def get_values(self):
		return self._table_to_dict()

	# - Table <-> dict --------------------------------------------------------
	def _format_value(self, v):
		try:
			fv = float(v)
		except (TypeError, ValueError):
			fv = self.value_default
		if self.value_type is int:
			return str(int(round(fv)))
		# strip trailing zeros for compact display
		s = ('{:g}'.format(fv))
		return s

	def _parse_value(self, s):
		try:
			fv = float(s)
		except (TypeError, ValueError):
			return None
		if self.value_type is int:
			return int(round(fv))
		return fv

	def _table_to_dict(self):
		out = {}
		for row in self.w.table.get():
			name = row.get('name')
			val  = self._parse_value(row.get('value'))
			if name and val is not None:
				out[name] = val
		return out

	def _dict_to_table(self, data):
		'''Repopulate the table. Known masters in font order, orphans last.'''
		known_rows = [{'name': name,
		               'value': self._format_value(data.get(name, self.value_default))}
		              for name in self.master_names]
		orphan_rows = [{'name': k,
		                'value': self._format_value(data[k])}
		               for k in sorted(data.keys()) if k not in self._known_set]
		self.w.table.set(known_rows + orphan_rows)

	def _on_cell_edit(self, sender):
		# Validate; revert bad cells to value_default.
		rows = sender.get()
		dirty = False
		for r in rows:
			if self._parse_value(r.get('value')) is None:
				r['value'] = self._format_value(self.value_default)
				dirty = True
		if dirty:
			sender.set(rows)

	# - Font lib I/O (Glyphs.font.userData) -----------------------------------
	def _read_font_lib(self):
		try:
			ud = self.tr_font.userData
		except Exception as ex:
			self._alert('Font lib unavailable', str(ex))
			return {}, False

		if ud is None:
			return {}, False

		try:
			raw = ud.get(self.lib_key) if hasattr(ud, 'get') else ud[self.lib_key]
		except Exception:
			return {}, False

		if raw is None:
			return {}, False

		# Coerce NSDictionary etc. into plain dict[str -> float]
		clean = {}
		try:
			items = raw.items() if hasattr(raw, 'items') else dict(raw).items()
		except Exception:
			return {}, False
		for k, v in items:
			try:
				clean[str(k)] = float(v)
			except (TypeError, ValueError):
				continue
		return clean, True

	def _on_font_load(self, sender):
		data, present = self._read_font_lib()
		if not present:
			self._alert('Load from Font',
			            'No data found in font lib under key:\n%s' % self.lib_key)
			return
		self._dict_to_table(data)

	def _on_font_save(self, sender):
		data = {str(k): float(v) for k, v in self._table_to_dict().items()}
		try:
			# Glyphs userData behaves like a dict; assign directly.
			self.tr_font.userData[self.lib_key] = data
		except Exception as ex:
			self._alert('Save to Font failed',
			            '%s\n\n%s' % (type(ex).__name__, str(ex)))
			return
		self._alert('Save to Font',
		            '%d value(s) saved to font lib under key:\n%s'
		            % (len(data), self.lib_key))

	# - JSON I/O --------------------------------------------------------------
	def _default_dir(self):
		try:
			path = self.tr_font.filepath
			if path:
				return os.path.dirname(str(path))
		except Exception:
			pass
		return os.path.expanduser('~')

	def _suggested_filename(self):
		stem = self.lib_key[len(TR_LIB_KEY_PREFIX):] \
			if self.lib_key.startswith(TR_LIB_KEY_PREFIX) else self.lib_key
		return stem + '.json'

	def _on_file_save(self, sender):
		panel = NSSavePanel.savePanel()
		panel.setTitle_('Save master values to JSON')
		panel.setNameFieldStringValue_(self._suggested_filename())
		panel.setAllowedFileTypes_(['json'])
		from AppKit import NSURL
		panel.setDirectoryURL_(NSURL.fileURLWithPath_(self._default_dir()))
		if panel.runModal() != 1:
			return
		fname = str(panel.URL().path())

		payload = {
			'format': TR_MASTER_VALUES_FORMAT,
			'key':    self.lib_key,
			'values': self._table_to_dict(),
		}
		try:
			with open(fname, 'w') as f:
				json.dump(payload, f, indent='\t', sort_keys=True)
		except Exception as ex:
			self._alert('Save to JSON failed', str(ex))

	def _on_file_load(self, sender):
		panel = NSOpenPanel.openPanel()
		panel.setTitle_('Load master values from JSON')
		panel.setAllowsMultipleSelection_(False)
		panel.setAllowedFileTypes_(['json'])
		from AppKit import NSURL
		panel.setDirectoryURL_(NSURL.fileURLWithPath_(self._default_dir()))
		if panel.runModal() != 1:
			return
		fname = str(panel.URL().path())

		try:
			with open(fname, 'r') as f:
				blob = json.load(f)
		except Exception as ex:
			self._alert('Load from JSON failed', str(ex))
			return

		# Accept wrapped {format, key, values} or bare dict.
		if isinstance(blob, dict) and 'values' in blob and isinstance(blob['values'], dict):
			data = blob['values']
			loaded_key = blob.get('key')
			if loaded_key and loaded_key != self.lib_key:
				self._alert('Key mismatch',
				            'JSON was saved under key %r; loading into %r anyway.'
				            % (loaded_key, self.lib_key))
		elif isinstance(blob, dict):
			data = blob
		else:
			self._alert('Load from JSON failed',
			            'Unrecognized file shape (expected a dict).')
			return

		clean = {}
		for k, v in data.items():
			try:
				clean[str(k)] = float(v)
			except (TypeError, ValueError):
				continue
		self._dict_to_table(clean)

	# - Result ----------------------------------------------------------------
	def _on_ok(self, sender):
		self.values  = self._table_to_dict()
		self.changed = (self.values != self._initial_data)
		try:
			if self._callback:
				self._callback(self.values)
		finally:
			self._stop_modal()
			self.w.close()

	def _on_cancel(self, sender):
		self.values  = None
		self.changed = False
		self._stop_modal()
		self.w.close()

	# - Helpers ---------------------------------------------------------------
	@python_method
	def _alert(self, title, message):
		try:
			from AppKit import NSAlert
			alert = NSAlert.alloc().init()
			alert.setMessageText_(title)
			alert.setInformativeText_(message)
			alert.runModal()
		except Exception:
			print('[TypeRig Panel] %s: %s' % (title, message))


# - Per-master X / Y steps ----------------------------------------------------
# Storage in Glyphs: font.userData[lib_key] -> dict[master_name -> [x, y]]
def read_master_steps(font, lib_key, default=(1., 1.)):
	'''Per-master (x, y) steps stored by TRMasterStepsDialog, as
	dict[master_name -> (x, y)]; {} if absent. Malformed entries get `default`.'''
	if font is None:
		return {}
	try:
		ud  = font.userData
		raw = ud.get(lib_key) if hasattr(ud, 'get') else ud[lib_key]
		items = raw.items() if hasattr(raw, 'items') else dict(raw).items()
	except Exception:
		return {}
	out = {}
	for k, v in items:
		try:
			out[str(k)] = (float(v[0]), float(v[1]))
		except (TypeError, ValueError, IndexError, KeyError):
			out[str(k)] = tuple(default)
	return out


class TRMasterStepsDialog(object):
	'''Modal per-master X / Y step editor.

	A table Master | X | Y (editable), and X / Y fields with Set selected /
	Set all to give the selected rows or every master the same pair. OK
	writes font.userData[lib_key] and returns dict[master_name -> (x, y)];
	Cancel returns None.
	'''
	_NAME_W = UI.DIALOG.MV_NAME_W

	def __init__(self, font, lib_key, title=None, message=None,
	             default=(1., 1.), size=(UI.DIALOG.MV_W, UI.DIALOG.MV_H)):
		if not isinstance(lib_key, str) or not lib_key.startswith(TR_LIB_KEY_PREFIX):
			raise ValueError("TRMasterStepsDialog: lib_key must start with %r (got %r)"
			                 % (TR_LIB_KEY_PREFIX, lib_key))
		self.tr_font = font
		self.lib_key = lib_key
		self.default = (float(default[0]), float(default[1]))
		self.values  = None
		self._modal_session = None

		try:
			names = [m.name for m in font.masters]
		except Exception:
			names = []

		w, h = size
		PAD     = UI.DIALOG.MV_PAD
		LBL_H   = UI.DIALOG.MV_LBL_H
		BTN_H   = UI.DIALOG.MV_BTN_H
		BTN_ROW = BTN_H + UI.DIALOG.MV_BTN_GAP

		self.w = vanilla.Window((w, h), title or 'Keyboard steps',
		                        minSize=(UI.DIALOG.MV_MIN_W, UI.DIALOG.MV_MIN_H))
		self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)
		self.w.lbl = vanilla.TextBox((PAD, PAD, -PAD, LBL_H),
		                             message or 'X and Y step of the arrow keys, per master:')

		self.w.table = vanilla.List(
			(0, PAD + LBL_H, -0, -(PAD + BTN_ROW * 2)),
			[],
			columnDescriptions=[
				dict(title='Master', key='name', width=self._NAME_W, editable=False),
				dict(title='X',      key='x',    editable=True),
				dict(title='Y',      key='y',    editable=True),
			],
			editCallback=self._on_cell_edit,
			showColumnTitles=True,
			drawFocusRing=False,
		)

		# Row: X, Y, Set selected, Set all
		quarter = (w - PAD * 5) // 4
		y = -(PAD + BTN_ROW * 2)
		self.w.fld_x = vanilla.EditText((PAD, y, quarter, BTN_H), self._fmt(self.default[0]), placeholder='X')
		self.w.fld_y = vanilla.EditText((PAD * 2 + quarter, y, quarter, BTN_H), self._fmt(self.default[1]), placeholder='Y')
		self.w.btn_set_sel = vanilla.Button((PAD * 3 + quarter * 2, y, quarter, BTN_H), 'Set selected',
		                                    callback=lambda s: self._set_rows(selected=True))
		self.w.btn_set_all = vanilla.Button((PAD * 4 + quarter * 3, y, quarter, BTN_H), 'Set all',
		                                    callback=lambda s: self._set_rows(selected=False))
		y += BTN_ROW

		half = (w - PAD * 3) // 2
		self.w.btn_cancel = vanilla.Button((PAD, y, half, BTN_H), 'Cancel', callback=self._on_cancel)
		self.w.btn_ok     = vanilla.Button((PAD * 2 + half, y, half, BTN_H), 'OK', callback=self._on_ok)

		stored = read_master_steps(font, lib_key, self.default)
		self.w.table.set([{'name': n,
		                   'x': self._fmt(stored.get(n, self.default)[0]),
		                   'y': self._fmt(stored.get(n, self.default)[1])} for n in names])

	# Same modal loop as TRMasterValuesDialog (uses self.w / self.values)
	run_modal   = TRMasterValuesDialog.run_modal
	_stop_modal = TRMasterValuesDialog._stop_modal

	# - Helpers ---------------------------------------------------------------
	@staticmethod
	def _fmt(v):
		return '{:g}'.format(float(v))

	@staticmethod
	def _parse(s):
		try:
			return float(s)
		except (TypeError, ValueError):
			return None

	def _on_cell_edit(self, sender):
		rows, dirty = sender.get(), False
		for r in rows:
			for key, d in (('x', self.default[0]), ('y', self.default[1])):
				if self._parse(r.get(key)) is None:
					r[key] = self._fmt(d)
					dirty = True
		if dirty:
			sender.set(rows)

	def _set_rows(self, selected):
		x, y = self._parse(self.w.fld_x.get()), self._parse(self.w.fld_y.get())
		rows = self.w.table.get()
		picked = set(self.w.table.getSelection()) if selected else set(range(len(rows)))
		for i, r in enumerate(rows):
			if i in picked:
				if x is not None:
					r['x'] = self._fmt(x)
				if y is not None:
					r['y'] = self._fmt(y)
		self.w.table.set(rows)

	def _on_ok(self, sender):
		values = {}
		for r in self.w.table.get():
			x, y = self._parse(r.get('x')), self._parse(r.get('y'))
			values[r['name']] = (self.default[0] if x is None else x, self.default[1] if y is None else y)
		try:
			self.tr_font.userData[self.lib_key] = dict((k, [v[0], v[1]]) for k, v in values.items())
			self.values = values
		finally:
			self._stop_modal()
			self.w.close()

	def _on_cancel(self, sender):
		self.values = None
		self._stop_modal()
		self.w.close()


# - Choice alert ------------------------------------------------------------------
def ask_choices(message, info, choices, ok_title='OK', cancel_title='Cancel'):
	"""Modal alert: a message, an informative text and one popup per choice.
	choices: [(key, caption, [(value, title), ...], default value)].
	Returns {key: value} on OK, None on Cancel. No vanilla window is made."""
	from AppKit import NSAlert, NSView, NSTextField, NSPopUpButton, NSAlertFirstButtonReturn
	D = UI.DIALOG
	step = D.CH_LABEL_H + D.CH_POPUP_H + D.CH_GAP
	height = max(0, len(choices) * step - D.CH_GAP)
	view = NSView.alloc().initWithFrame_(((0, 0), (D.CH_W, height)))
	popups = []
	for i, (key, caption, options, default) in enumerate(choices):
		top = height - i * step		# AppKit y grows upwards
		label = NSTextField.labelWithString_(caption)
		label.setFrame_(((0, top - D.CH_LABEL_H), (D.CH_W, D.CH_LABEL_H)))
		view.addSubview_(label)
		popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
			((0, top - D.CH_LABEL_H - D.CH_POPUP_H), (D.CH_W, D.CH_POPUP_H)), False)
		popup.addItemsWithTitles_([title for _v, title in options])
		values = [v for v, _t in options]
		popup.selectItemAtIndex_(values.index(default) if default in values else 0)
		view.addSubview_(popup)
		popups.append((key, values, popup))
	alert = NSAlert.alloc().init()
	alert.setMessageText_(message)
	alert.setInformativeText_(info)
	if choices:
		alert.setAccessoryView_(view)
	alert.addButtonWithTitle_(ok_title)
	alert.addButtonWithTitle_(cancel_title)
	if alert.runModal() != NSAlertFirstButtonReturn:
		return None
	return dict((key, values[popup.indexOfSelectedItem()]) for key, values, popup in popups)
