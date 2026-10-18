# encoding: utf-8
"""
TypeRig sidebar palettes — UI configuration.

Single source of truth for the layout of every TR palette in the Glyphs
sidebar (TypeRig Toolbar.glyphsPalette, and later palettes). Palettes are
a different surface from TR Panel: a fixed-width sidebar section with a
dense icon grid instead of a floating window with tabs. TR Panel's sizes
live in config.py (UI); nothing here is shared with it.

Same rules as config.py: no layout literal in palette code; add a field
here first, then alias it. GS3 / GS4 presets, picked by HOST_MAJOR.

    from typerig.proxy.gs3.gui.palette_config import PALETTE
    BTN = PALETTE.BTN
"""
from __future__ import division, print_function, unicode_literals

from types import SimpleNamespace

from .config import HOST_MAJOR


# - Entry fields ----------------------------------------------------------
# Every non-button control a palette places on the grid. Each kind takes the
# same three parameters, so new widgets reuse them instead of new numbers:
#   STYLE : vanilla sizeStyle — 'mini', 'small' or 'regular' (NSControlSize);
#           sets the font size and the natural height of the control
#   CELLS : width in grid cells (buttons, with the gaps between them);
#           None = the full row (COLS)
#   H     : height in px; None = the control's natural height for STYLE.
#           Taller text fields keep their text at the top (AppKit), so
#           prefer a bigger STYLE over a bigger H
# Entries are centred vertically on the button row; one that does not fit
# the rest of the row starts a new row.
def _entry(style, cells, h=None):
	return SimpleNamespace(STYLE=style, CELLS=cells, H=h)

_ENTRY_GS3 = SimpleNamespace(
	NUM    = _entry('regular', 2),     # numeric EditText (sizes, angles, counts)
	TEXT   = _entry('regular', None),  # free-text EditText (names, expressions)
	POPUP  = _entry('regular', 3),     # PopUpButton (mode / preset choice)
	COMBO  = _entry('regular', 3),     # ComboBox (choice or typed value)
	CHECK  = _entry('regular', 2),     # CheckBox with a short title
	SLIDER = _entry('regular', 3),     # Slider
	LABEL  = _entry('regular', 2),     # TextBox (short caption)
)
_ENTRY_GS4 = SimpleNamespace(
	NUM    = _entry('regular', 2),
	TEXT   = _entry('regular', None),
	POPUP  = _entry('regular', 3),
	COMBO  = _entry('regular', 3),
	CHECK  = _entry('regular', 2),
	SLIDER = _entry('regular', 3),
	LABEL  = _entry('regular', 2),
)


# - Grid ------------------------------------------------------------------
# vanilla cannot reflow live, so palettes flow their buttons once, at build
# time, into a grid of COLS columns. Glyphs' own palettes are built
# 150-170 px wide (GS3: Transform 160, Dimensions 150-170) but the sidebar
# is wider in use, so the grid takes ~200 px. It stays left-aligned.
# W is derived — change COLS / BTN / GAP / PAD. Buttons are GridIconButton
# with TR Panel's bezels (2 GS3, 16 glass GS4). Those keep vanilla's +6 px
# frame padding per side, as in TR Panel, so keep GAP >= 12 or the padded
# frames overlap. BEZEL 10 (.smallSquare) instead draws exactly BTN x BTN
# with no padding (see widgets.GridIconButton).
_PALETTE_GS3 = SimpleNamespace(
	BTN      = 26,   # grid button size, as drawn (square)
	ICON_PT  = 22,   # icon point size inside a grid button
	BEZEL    = 2,    # same as TR Panel GS3 (.flexiblePush / RegularSquare)
	GAP      = 12,   # gap between grid cells, both directions
	PAD      = 12,   # inset from the palette edge
	COLS     = 5,    # buttons per row; sections reflow at build time
	SEP      = 17,   # vertical space taken by a section separator line
	ENTRY    = _ENTRY_GS3,  # entry-field presets (above)
)
_PALETTE_GS4 = SimpleNamespace(
	BTN      = 22,
	ICON_PT  = 22,
	BEZEL    = 16,   # same as TR Panel GS4 (.glass)
	GAP      = 18,
	PAD      = 14,
	COLS     = 5,
	SEP      = 18,
	ENTRY    = _ENTRY_GS4,
)
PALETTE = _PALETTE_GS3 if HOST_MAJOR == 3 else _PALETTE_GS4
PALETTE.W      = PALETTE.COLS * PALETTE.BTN + (PALETTE.COLS - 1) * PALETTE.GAP + 2 * PALETTE.PAD
PALETTE.MAST_H = PALETTE.BTN + 2 * PALETTE.PAD   # masthead band
PALETTE.MIN_H  = PALETTE.MAST_H + 2 * (PALETTE.BTN + PALETTE.GAP)  # masthead + two rows
# Masthead: 2 layer pills, then 3 glyph pills pushed to the right edge.
# TRMasthead adds group_gap ON TOP of the 4 normal gaps between 5 pills.
PALETTE.MAST_GROUP_GAP = max(0, PALETTE.W - 2 * PALETTE.PAD - 5 * PALETTE.BTN - 4 * PALETTE.GAP)

