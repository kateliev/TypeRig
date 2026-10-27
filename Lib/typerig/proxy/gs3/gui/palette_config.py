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


# - Section captions --------------------------------------------------------
# Optional title above each section of a Toolbar ("Nodes", "Align", ...).
# Space above a caption = the grid GAP after the last row + SEP.
#   SHOW   : False hides every caption (sections keep their spacing)
#   STYLE  : vanilla sizeStyle of the caption text ('mini' / 'small' / 'regular')
#   H      : height in px; None = natural height for STYLE
#   GAP    : space between the caption and the first row of its section
#   INDENT : x offset from PAD; negative moves the caption left
def _caption(show, style, gap, indent=0, h=None):
	return SimpleNamespace(SHOW=show, STYLE=style, H=h, GAP=gap, INDENT=indent)

_CAPTION_GS3 = _caption(True, 'regular', 8, indent=-4)
_CAPTION_GS4 = _caption(True, 'regular', 10, indent=-4)


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
	SEP      = 4,    # extra space between sections (on top of GAP)
	SEP_LINE = False,  # draw a thin line in the separator space
	CAPTION  = _CAPTION_GS3,  # section captions (above)
	ENTRY    = _ENTRY_GS3,  # entry-field presets (above)
)
_PALETTE_GS4 = SimpleNamespace(
	BTN      = 22,
	ICON_PT  = 22,
	BEZEL    = 16,   # same as TR Panel GS4 (.glass)
	GAP      = 18,
	PAD      = 14,
	COLS     = 5,
	SEP      = 4,
	SEP_LINE = False,
	CAPTION  = _CAPTION_GS4,
	ENTRY    = _ENTRY_GS4,
)
PALETTE = _PALETTE_GS3 if HOST_MAJOR == 3 else _PALETTE_GS4
PALETTE.W      = PALETTE.COLS * PALETTE.BTN + (PALETTE.COLS - 1) * PALETTE.GAP + 2 * PALETTE.PAD
PALETTE.MAST_H = PALETTE.BTN + 2 * PALETTE.PAD   # masthead band
PALETTE.MIN_H  = PALETTE.MAST_H + 2 * (PALETTE.BTN + PALETTE.GAP)  # masthead + two rows
# Masthead: 2 layer pills, then 3 glyph pills pushed to the right edge.
# TRMasthead adds group_gap ON TOP of the 4 normal gaps between 5 pills.
PALETTE.MAST_GROUP_GAP = max(0, PALETTE.W - 2 * PALETTE.PAD - 5 * PALETTE.BTN - 4 * PALETTE.GAP)

# - Toast (gui/layer_toast.py) --------------------------------------------
# Small label shown at the pointer, then faded out; switched from the
# Toolbar observer row. Colours name NSColor class methods. One set for
# GS3 + GS4.
PALETTE.TOAST = SimpleNamespace(
	OFFSET   = (20, 20),  # right, down from the pointer (pt)
	HOLD     = 0.8,       # seconds fully visible
	FADE     = 0.4,       # seconds fade-out
	FONT_PT  = 12,        # bold system font size
	PAD_X    = 8,         # label inset, horizontal
	PAD_Y    = 4,         # label inset, vertical
	RADIUS   = 6,         # corner radius
	BG       = 'blackColor',
	BG_ALPHA = 0.78,
	FG       = 'systemOrangeColor',
)

# - Stem probe (gui/stem_probe.py) ----------------------------------------
# Live stem measurement drawn in the edit view while the pointer is inside
# the outline: one chord through the pointer along the normal of the
# nearest outline (core algo/chord_probe.py). Sizes are screen pt (divided
# by the view scale when drawn). Colours name NSColor class methods. One
# set for GS3 + GS4.
PALETTE.PROBE = SimpleNamespace(
	STEPS    = 36,    # angles scanned over 180 deg (both sides: 72 directions, 5 deg apart)
	REFINE   = 10,    # golden-section steps after the scan (5 deg -> ~0.04 deg)
	DECIMALS = 1,     # digits after the point in the label
	STROKE   = 1.,    # chord line width
	DOT      = 2.5,   # chord end dot radius
	FONT_PT  = 10,    # label font size
	PAD_X    = 4,     # label badge inset, horizontal
	PAD_Y    = 1,     # label badge inset, vertical
	RADIUS   = 3,     # label badge corner radius
	COLOR    = 'systemOrangeColor',  # chord and badge
	TEXT     = 'whiteColor',         # label text on the badge
)

# - Node slide (gui/node_slider.py) ---------------------------------------
# Option-drag slides a node along its incoming segment, Cmd+Option along
# the outgoing one (core algo/node_slide.py). T is the time on the original
# segment; beyond 0 / 1 the segment is extended.
PALETTE.SLIDE = SimpleNamespace(
	HIT      = 8,     # screen pt: mouse down this close to a selected node grabs it
	EXTEND   = 1.,    # how far past the far end the node may go, in segment time
	MARGIN   = .01,   # keeps the node off the segment's other end (no zero-length segment)
)

# - Node add ghost (gui/node_ghost.py) ------------------------------------
# Ghost of the node Ctrl+Option+right click inserts: nearest point on the
# active layer's paths. Screen pt; NSColor class method names.
PALETTE.GHOST = SimpleNamespace(
	SNAP     = 12,    # show the ghost when the pointer is this close to a path
	R        = 4.,    # ghost node radius
	STROKE   = 1.5,   # ghost outline width
	ALPHA    = .35,   # ghost fill alpha
	COLOR    = 'systemOrangeColor',
)

