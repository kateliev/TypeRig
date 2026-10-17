# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — reusable masthead
#
# The row of scope pills (Active / Masters / Selected layers, then Glyph /
# Window / Selection) lifted from main_panel.TRMainPanel._build_masthead so
# any host (sidebar palette, later TR Panel) can place it on a vanilla.Group
# and have it write into its own TRScopeState.
#
#   state = TRScopeState(font_resolver=...)
#   group.mast = vanilla.Group((0, 0, -0, PALETTE.MAST_H))
#   mast = TRMasthead(group.mast, state, height=PALETTE.MAST_H,
#                     show_selected=False, show_fold=False)
#
# on_change(masthead) runs after every pill click, once the state is
# updated. A host with a layer picker reads masthead.selected_on() there
# and replaces state.pLayers with the picker's checked rows.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

from functools import partial

from .widgets import IconButton
from .config  import UI


class TRMasthead(object):
	'''Scope pills on `group`, writing into `state` (a TRScopeState).'''

	def __init__(self, group, state, on_change=None, show_selected=True,
	             show_fold=False, on_fold=None, height=None,
	             btn=None, gap=None, margin=None, group_gap=None, icon_pt=None,
	             button_class=IconButton):
		'''btn / gap / margin / group_gap / icon_pt override the TR Panel
		metrics (UI.BTN, UI.LAYOUT) so a palette can put the pills on its
		own grid. group_gap is the space between the layer and glyph pills;
		button_class=GridIconButton for a dense grid.'''
		self.group     = group
		self.state     = state
		self.on_change = on_change

		BTN    = UI.BTN.SIZE      if btn    is None else btn
		GAP    = UI.LAYOUT.GAP    if gap    is None else gap
		MARGIN = UI.LAYOUT.MARGIN if margin is None else margin
		GROUP  = GAP * 2          if group_gap is None else group_gap
		H      = UI.MASTHEAD.H    if height is None else height
		Y      = (H - BTN) // 2
		pill   = partial(button_class, size=icon_pt)

		# Layer mode pills (mutually exclusive radio behaviour, manual).
		x = MARGIN
		group.btn_active_layer = pill(
			(x, Y, BTN, BTN), 'layer_active',
			tooltip='Active layer',
			checkable=True, callback=self._on_layer_mode,
		)
		x += BTN + GAP

		group.btn_masters = pill(
			(x, Y, BTN, BTN), 'layer_master',
			tooltip='Master layers',
			checkable=True, callback=self._on_layer_mode,
		)
		x += BTN + GAP

		self.layer_buttons = [group.btn_active_layer, group.btn_masters]
		if show_selected:
			group.btn_selected = pill(
				(x, Y, BTN, BTN), 'select_option',
				tooltip='Selected layers',
				checkable=True, callback=self._on_layer_mode,
			)
			self.layer_buttons.append(group.btn_selected)
			x += BTN + GAP
		x += GROUP		# wider gap between the two pill groups

		# Glyph mode pills.
		group.btn_glyph = pill(
			(x, Y, BTN, BTN), 'glyph_active',
			tooltip='Active glyph',
			checkable=True, callback=self._on_glyph_mode,
		)
		x += BTN + GAP

		group.btn_window = pill(
			(x, Y, BTN, BTN), 'select_window',
			tooltip='Glyph window',
			checkable=True, callback=self._on_glyph_mode,
		)
		x += BTN + GAP

		group.btn_selection = pill(
			(x, Y, BTN, BTN), 'select_glyph',
			tooltip='Font window selection',
			checkable=True, callback=self._on_glyph_mode,
		)
		self.glyph_buttons = [group.btn_glyph, group.btn_window, group.btn_selection]

		# Fold button — far right.
		if show_fold:
			group.btn_fold = pill(
				(-BTN - MARGIN, Y, BTN, BTN), 'fold_up',
				tooltip='Fold panel',
				callback=on_fold,
			)

		self.sync_from_state()

	# - State <-> pills -------------------------------------------------
	def sync_from_state(self):
		'''Check the pills that match the current state.'''
		p_layers = self.state.pLayers
		checked_rows = not (isinstance(p_layers, tuple) and p_layers and isinstance(p_layers[0], bool))
		if checked_rows and self.selected_button() is not None:
			flags = [False, False, True]
		elif checked_rows or not (p_layers[0] or p_layers[1]):
			flags = [True, False, False]
		else:
			flags = [bool(p_layers[0]), not p_layers[0] and bool(p_layers[1]), False]
		for b, on in zip(self.layer_buttons, flags):
			b.setChecked(on)

		mode = self.state.pMode if self.state.pMode in (0, 1, 2) else 0
		for i, b in enumerate(self.glyph_buttons):
			b.setChecked(i == mode)

	def selected_button(self):
		return self.layer_buttons[2] if len(self.layer_buttons) > 2 else None

	def selected_on(self):
		b = self.selected_button()
		return b is not None and b.isChecked()

	# - Callbacks -------------------------------------------------------
	@staticmethod
	def _radio(buttons, sender):
		# At least one stays on; clicking another flips the others off.
		if not any(b.isChecked() for b in buttons):
			sender.setChecked(True)
		elif sender.isChecked():
			for b in buttons:
				if b is not sender:
					b.setChecked(False)

	def _on_layer_mode(self, sender):
		self._radio(self.layer_buttons, sender)
		self.state.pLayers = (
			self.layer_buttons[0].isChecked(),
			self.layer_buttons[1].isChecked(),
			self.selected_on(),
			False,
		)
		self._changed()

	def _on_glyph_mode(self, sender):
		self._radio(self.glyph_buttons, sender)
		for i, b in enumerate(self.glyph_buttons):
			if b.isChecked():
				self.state.pMode = i
		self._changed()

	def _changed(self):
		if self.on_change is not None:
			self.on_change(self)
