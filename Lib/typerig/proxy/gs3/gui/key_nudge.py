# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — keyboard nudge (observer)
#
# While on, the arrow keys in the edit view move the selected nodes by a
# per-master X / Y step instead of Glyphs' 1 unit: left / right use X,
# up / down use Y. Shift x10, Shift + Cmd x100 (PALETTE.KEYS). Handles move
# with their node (core NodeActions.nodes_move 'SMART', the TR Panel Node
# move). Option+click the Toolbar button to set the steps per master
# (TRMasterStepsDialog; font.userData NODE_KEY_STEPS_LIB_KEY).
#
# Follows the window's Toolbar masthead: Active moves the active layer,
# Masters moves every master, each by its own master's steps (a brace /
# bracket layer uses its master's). Concept from FL TR Panel Node (X / Y
# shift values, "Capture keyboard"); no slope / italic walkers here.
#
# Keys pass through to Glyphs when the edit view is not the first
# responder (a text field has focus), with the Text tool, with no node
# selected, or with other modifiers (Option / Ctrl / Cmd alone).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

from GlyphsApp import Glyphs
from AppKit import (NSEventMaskKeyDown, NSEventModifierFlagShift, NSEventModifierFlagControl,
                    NSEventModifierFlagOption, NSEventModifierFlagCommand)

from typerig.core.base.lib_keys import NODE_KEY_STEPS_LIB_KEY

from .observer          import TRObserver, scope_for
from .palette_config    import PALETTE
from .dialogs           import TRMasterStepsDialog, read_master_steps
from .typerig_bootstrap import get_node_actions

KEYS = PALETTE.KEYS

# macOS virtual key codes -> (x sign, y sign)
ARROWS = {123: (-1, 0), 124: (1, 0), 125: (0, -1), 126: (0, 1)}

_MODS = NSEventModifierFlagShift | NSEventModifierFlagControl | NSEventModifierFlagOption | NSEventModifierFlagCommand
MULTIPLIERS = {
	0                                                       : 1.,
	NSEventModifierFlagShift                                : KEYS.SHIFT,
	NSEventModifierFlagShift | NSEventModifierFlagCommand   : KEYS.SHIFT_CMD,
}


def layer_steps(gs_glyph, layer_name, steps):
	'''(x, y) step for a layer: its master's entry in steps, else KEYS.DEFAULT.'''
	for layer in gs_glyph.layers:
		if layer.name == layer_name:
			master = layer.master
			key = master.name if master is not None else layer_name
			return steps.get(key, KEYS.DEFAULT)
	return KEYS.DEFAULT


def move_selection(gs_glyph, sign, multiplier, steps, state=None):
	'''Move the selected nodes of gs_glyph in the masthead scope (`state`, a
	TRScopeState; None = active layer), each layer by its own step.'''
	from typerig.proxy.gs3.objects.glyph import trGlyph
	from .scope import scope_layers

	tr_g = trGlyph(gs_glyph)
	if state is not None:
		names = scope_layers(state.pMode, state.pLayers, tr_g)
	else:
		names = [tr_g.active_layer]
	NodeActions, npa = get_node_actions()

	gs_glyph.beginUndo()
	try:
		for name in names:
			sx, sy = layer_steps(gs_glyph, name, steps)
			npa.npa_move(tr_g, [name], NodeActions,
			             sign[0] * sx * multiplier, sign[1] * sy * multiplier, KEYS.METHOD)
	finally:
		gs_glyph.endUndo()
	tr_g.update()
	return names


class KeyNudge(TRObserver):
	key         = 'com.typerig.observer.keyNudge'
	name        = 'keyboard'
	event_mask  = NSEventMaskKeyDown
	has_options = True

	def configure(self):
		font = Glyphs.font
		if font is None:
			return
		TRMasterStepsDialog(font, NODE_KEY_STEPS_LIB_KEY, title='Keyboard steps',
		                    default=KEYS.DEFAULT).run_modal()

	def _target(self, event):
		'''Active layer of the edit view the key goes to, or None.'''
		font = Glyphs.font
		tab = font.currentTab if font is not None else None
		if tab is None:
			return None
		view = tab.graphicView()
		window = view.window()
		if event.window() != window or window.firstResponder() != view:
			return None
		try:
			if font.tool == 'TextTool':
				return None
		except Exception:
			pass
		layer = view.activeLayer()
		if layer is None:
			return None
		for path in layer.paths:
			for node in path.nodes:
				if node.selected:
					return layer
		return None

	def on_event(self, event):
		sign = ARROWS.get(event.keyCode())
		if sign is None:
			return event
		multiplier = MULTIPLIERS.get(event.modifierFlags() & _MODS)
		if multiplier is None:
			return event
		layer = self._target(event)
		if layer is None:
			return event
		glyph = layer.parent
		font = glyph.parent
		move_selection(glyph, sign, multiplier,
		               read_master_steps(font, NODE_KEY_STEPS_LIB_KEY, KEYS.DEFAULT),
		               scope_for(font))
		return None


observer = KeyNudge()
