# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — editable List2 cells without Auto Layout
#
# vanilla's List2 cells pin their controls with Auto Layout, which leaked
# into fixed-frame windows (the TR Panel list collapse of 2026-10-18, see
# tint_list.py). TRTintList ships read-only frame-based cells (TRTextCell,
# TRImageCell); these are the editable ones, same build:
#   TREditCell  — editable text (alignment left / center / right)
#   TRCheckCell — check box, centred; enabled=False greys it out
#
#     dict(identifier='vstem', title='V st.', editable=True, width=52,
#          cellClass=TREditCell, cellClassArguments=dict(alignment='right'))
#     dict(identifier='kerning', title='K', editable=True, width=30,
#          cellClass=TRCheckCell, cellClassArguments=dict(enabled=False))
#
# List2 protocol: a cell has _nsObject, set(value), get(); for an editable
# column vanilla passes callback=<data source cellEditCallback>, which the
# cell calls with itself when the user commits a value. The data source
# then writes the value into the item (dict key = column identifier) and
# calls the list's editCallback.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import AppKit
from vanilla.vanillaBase import VanillaCallbackWrapper

from .config import UI

TL = UI.TINTLIST

_FLEX_W  = AppKit.NSViewWidthSizable
_FLEX_TB = AppKit.NSViewMinYMargin | AppKit.NSViewMaxYMargin
_FLEX_LR = AppKit.NSViewMinXMargin | AppKit.NSViewMaxXMargin

_ALIGN = {
	'left':   AppKit.NSTextAlignmentLeft,
	'center': AppKit.NSTextAlignmentCenter,
	'right':  AppKit.NSTextAlignmentRight,
}


class _Cell(object):
	def _wire(self, control, callback):
		# The wrapper is the control's target; keep it alive on the cell
		self._target = VanillaCallbackWrapper(self._action) if callback else None
		self._callback = callback if callable(callback) else None
		if self._target is not None:
			control.setTarget_(self._target)
			control.setAction_('action:')

	def _action(self, sender):
		if self._callback is not None:
			self._callback(self)


class TREditCell(_Cell):
	'''Editable text cell; commits on Return / Tab / focus loss.'''
	def __init__(self, editable=False, callback=None, alignment='left', **kwargs):
		field = AppKit.NSTextField.alloc().initWithFrame_(((0, 0), (TL.CELL_W, 0)))
		field.setBezeled_(False)
		field.setBordered_(False)
		field.setDrawsBackground_(False)
		field.setEditable_(bool(editable))
		field.setSelectable_(bool(editable))
		field.setAlignment_(_ALIGN.get(alignment, AppKit.NSTextAlignmentLeft))
		field.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
		field.cell().setSendsActionOnEndEditing_(True)
		h = field.intrinsicContentSize().height
		pad = TL.CELL_PAD
		view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (TL.CELL_W, h + 2 * pad)))
		field.setFrame_(((pad, pad), (TL.CELL_W - 2 * pad, h)))
		field.setAutoresizingMask_(_FLEX_W | _FLEX_TB)
		view.addSubview_(field)
		self._nsObject, self._field = view, field
		self._wire(field, callback if editable else None)

	def set(self, value):
		self._field.setStringValue_('' if value is None else str(value))

	def get(self):
		return self._field.stringValue()


class TRCheckCell(_Cell):
	'''Check box cell (no title), centred both ways.'''
	def __init__(self, editable=False, callback=None, enabled=True, **kwargs):
		button = AppKit.NSButton.alloc().initWithFrame_(((0, 0), (0, 0)))
		button.setButtonType_(AppKit.NSButtonTypeSwitch)
		button.setTitle_('')
		button.sizeToFit()
		w, h = button.frame().size.width, button.frame().size.height
		pad = TL.CELL_PAD
		view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (w + 2 * pad, h + 2 * pad)))
		button.setFrameOrigin_((pad, pad))
		button.setAutoresizingMask_(_FLEX_LR | _FLEX_TB)
		button.setEnabled_(bool(editable and enabled))
		view.addSubview_(button)
		self._nsObject, self._button = view, button
		self._wire(button, callback if editable and enabled else None)

	def set(self, value):
		self._button.setState_(AppKit.NSControlStateValueOn if value else AppKit.NSControlStateValueOff)

	def get(self):
		return bool(self._button.state())
