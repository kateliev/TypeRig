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
	FLD_STYLE = 'small',  # NSControlSize for a one-cell numeric field
)
_PALETTE_GS4 = SimpleNamespace(
	BTN      = 22,
	ICON_PT  = 22,
	BEZEL    = 16,   # same as TR Panel GS4 (.glass)
	GAP      = 18,
	PAD      = 14,
	COLS     = 5,
	SEP      = 18,
	FLD_STYLE = 'small',
)
PALETTE = _PALETTE_GS3 if HOST_MAJOR == 3 else _PALETTE_GS4
PALETTE.W      = PALETTE.COLS * PALETTE.BTN + (PALETTE.COLS - 1) * PALETTE.GAP + 2 * PALETTE.PAD
PALETTE.MAST_H = PALETTE.BTN + 2 * PALETTE.PAD   # masthead band
PALETTE.MIN_H  = PALETTE.MAST_H + 2 * (PALETTE.BTN + PALETTE.GAP)  # masthead + two rows
# Masthead: 2 layer pills, then 3 glyph pills pushed to the right edge.
# TRMasthead adds group_gap ON TOP of the 4 normal gaps between 5 pills.
PALETTE.MAST_GROUP_GAP = max(0, PALETTE.W - 2 * PALETTE.PAD - 5 * PALETTE.BTN - 4 * PALETTE.GAP)

