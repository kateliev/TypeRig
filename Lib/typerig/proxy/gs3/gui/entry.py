# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — entry-field placement
#
# Every non-button control a Panel tab puts on a button row (EditText,
# PopUpButton, ComboBox, SegmentedButton, CheckBox, Slider, TextBox) goes
# through add_entry(), so all of them size and align the same way:
#
#   - size from a UI.ENTRY.<KIND> preset (STYLE / W / H), see gui/config.py
#   - height = preset.H, else the control's natural height for its STYLE,
#     centred vertically on the BTN-high row at y
#   - UI.ENTRY.CLEAR px from the vanilla.Button on either side: vanilla
#     pads a button's NSView frame by 6 px per side, so a field placed
#     right after `x += BTN + small_gap` overlaps the drawn bezel.
#
# x is a cursor: the right edge of the widget to the left (button posSize
# x + w), or the row start with lead=0. add_entry returns the x where the
# next button may start (field end + CLEAR).
#
#     x = PAD
#     fld, x = add_entry(g, 'spn_mitre', x, y, ENTRY.NUM,
#                        lambda ps, st: vanilla.EditText(ps, '5', sizeStyle=st), lead=0)
#     g.btn_mitre = IconButton((x, y, BTN, BTN), 'corner_mitre', ...)
#     x += BTN                                      # next field: add_entry(..., x, ...)
#
# The Toolbar (sidebar palettes) has its own grid version of this:
# TRToolbarBase.entry with PALETTE.ENTRY.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

from .config import UI

BTN   = UI.BTN.SIZE
PAD   = UI.LAYOUT.PAD
CLEAR = UI.ENTRY.CLEAR


def natural_height(ctrl):
	'''Natural height of a vanilla control for its sizeStyle (intrinsicContentSize).'''
	h = ctrl._nsObject.intrinsicContentSize().height		# vanilla has no common public NSView accessor
	return h if h > 0 else BTN		# no intrinsic height -> button height


def entry_frame(x, y, preset, h, w=None, lead=None):
	'''posSize of an entry on the button row at y, and the x after it.

	x     : cursor — right edge of the widget to the left, or the row start
	h     : control height (preset.H or natural_height)
	w     : width override, a UI value; negative = anchored to the right edge
	        (vanilla). None = preset.W; preset.W None = to the right edge (-PAD)
	lead  : space before the control; None = CLEAR (a button on the left)
	Returns (posSize, x_next); x_next = field end + CLEAR, None when the
	field is anchored to the right edge.
	'''
	x += CLEAR if lead is None else lead
	if w is None:
		w = preset.W if preset.W is not None else -PAD
	top = y + (BTN - h) / 2.
	if top < 0:		# vanilla reads a negative y as anchored to the bottom of the parent
		raise ValueError('entry %r px above its group: start the row lower (row y %r, h %r)' % (-top, y, h))
	pos = (x, top, w, h)
	return pos, (x + w + CLEAR if w > 0 else None)


def add_entry(parent, attr, x, y, preset, factory, w=None, lead=None, tooltip=None):
	'''Create, size and place one entry; store it as parent.<attr>.

	factory : callable(posSize, sizeStyle) -> vanilla control
	Other arguments as entry_frame. Returns (control, x_next).
	'''
	ctrl = factory((x, y, preset.W or BTN, BTN), preset.STYLE)
	h = preset.H or natural_height(ctrl)
	pos, x_next = entry_frame(x, y, preset, h, w, lead)
	ctrl.setPosSize(pos)
	if tooltip:
		ctrl.setToolTip(tooltip)
	setattr(parent, attr, ctrl)
	return ctrl, x_next
