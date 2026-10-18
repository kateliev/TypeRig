# encoding: utf-8
"""
TypeRig Panel — UI configuration.

Single source of truth for every visual / layout / sizing parameter
in the GS3 plugin. There is exactly ONE place in the codebase where
a pixel value, a font point size, a gap, a padding, or a default
window dimension may be declared: this file, on the `UI` namespace.

WHY THIS FILE EXISTS
--------------------
`vanilla` has no layout engine. Every widget is positioned by an
absolute (x, y, w, h) tuple, so size / gap / padding constants leak
into every panel module. Without discipline they drift: `BTN = 28`
in one file, `BTN_W = 28` in another, an inline `4` somewhere else.
Bumping a button by one pixel then becomes a six-file grep. Vanilla
is a boilerplate nightmare compared to PyQt — the only way to keep
it under control is to centralise every magic number.

This module is that one place. Bump `UI.BTN.SIZE` here and every
panel, the masthead, and the configurator move in lockstep.

ORGANISATION
------------
Fields are grouped under sub-namespaces by concern:

    UI.BTN        — buttons (size, icon point size)
    UI.LAYOUT     — universal spacing (gap, pad, margin, section title)
    UI.ENTRY      — Panel entry fields, one preset per kind (STYLE / W / H)
    UI.SPN        — numeric EditText dimensions (legacy: dialogs, IconAssist)
    UI.LBL        — single-char label column, label-to-field gap
    UI.FORM     — label + field grids, check boxes, text buttons
    UI.LIST       — table (vanilla.List) dimensions
    UI.TINTLIST   — colour-coded list: dots + row tint (gui/tint_list.py)
    UI.THUMB      — outline thumbnails and the thumbnail grid (gui/thumbnail.py)
    UI.STATUS     — status / warning text block
    UI.WIN        — main window dimensions and minimums
    UI.MASTHEAD   — masthead band geometry
    UI.ASSETS     — asset filenames

All field names are ALL CAPS to mark them as compile-time constants.

THE RULES (these are not suggestions)
-------------------------------------
1. NO layout literal may appear in any `gui/`, `Panel/`,
   `main_panel.py`, or `configurator.py` file. Sizes, gaps, paddings,
   row heights, font sizes, window dimensions — all live here as
   fields on `UI.<GROUP>`.

2. If you need a new metric, add a field here FIRST, then import it.
   Never inline a number "just for now". Pick the right sub-namespace
   or add a new one — do not flatten into the wrong group.

3. New widgets register their tuning parameters here. A new slider
   widget adds `UI.SLIDER.H`, `UI.SLIDER.TRACK`, etc. The widget
   reads from `UI` internally; callers never pass raw pixel sizes
   through the widget's API.

4. New panels follow the same pattern: alias the fields you use at
   the top of the file, then use the short names in body code:

       from gui.config import UI
       BTN  = UI.BTN.SIZE
       GAP  = UI.LAYOUT.GAP
       PAD  = UI.LAYOUT.PAD
       TIT  = UI.LAYOUT.TIT
       ...
       btn = IconButton((x, y, BTN, BTN), 'token', ...)

   The aliases are local readability sugar; the values still live
   in exactly one place. Do NOT redeclare `BTN = 28` — that creates
   the second source of truth this file exists to prevent.

5. Sub-namespaces keep things browsable. If a group grows past ~8
   fields, split it. If a field doesn't clearly belong to one of
   the existing groups, add a new group rather than dumping it on
   the top level.
"""
from __future__ import division, print_function, unicode_literals

from types import SimpleNamespace


# - Host detection --------------------------------------------------------
# Returns the Glyphs major version (3 or 4). Default is 4 — the primary
# target per Lib/porting_guide.md §10a. We detect at module-import time
# so every per-host-tuned constant below can branch on HOST_MAJOR with
# zero runtime overhead.
def _detect_glyphs_major():
	try:
		from GlyphsApp import Glyphs
	except Exception:
		return 4
	# buildNumber is the most reliable signal: 3xxx = GS3, 4xxx = GS4.
	try:
		build = int(getattr(Glyphs, 'buildNumber', 0) or 0)
		if build >= 4000:
			return 4
		if build >= 3000:
			return 3
	except Exception:
		pass
	# Fallback: parse applicationVersion / versionString strings ("4.1.1").
	for attr in ('applicationVersion', 'versionString'):
		try:
			v = str(getattr(Glyphs, attr, '') or '')
			if v:
				return int(v.split('.')[0])
		except Exception:
			continue
	return 4

HOST_MAJOR = _detect_glyphs_major()


# - Buttons ---------------------------------------------------------------
# NSBezelStyle numeric values — current as of macOS 14 (Sonoma) + macOS 26.
# Apple renamed the enum in macOS 14; the OLD names in parentheses still
# work via numeric value but are deprecated and may now RENDER as their
# modern replacement, which is often why the old square styles look thick
# or oversized on GS4 — they're being drawn by AppKit as the modern style.
# Styles marked (deprecated) emit no warning but may change appearance in
# future releases.
#
#   1  .push               — pill button, height-capped (~24pt). Old: Rounded
#   2  .flexiblePush       — square, honours height. Old: RegularSquare
#   3  (ThickSquare)       — deprecated; redraws as flexiblePush
#   4  (ThickerSquare)     — deprecated; redraws as flexiblePush
#   5  .disclosure         — triangle disclosure arrow
#   6  (ShadowlessSquare)  — deprecated; redraws as flexiblePush (flat)
#   7  .circular           — fixed-size round, icon-only
#   8  (TexturedSquare)    — deprecated; redraws as flexiblePush
#   9  .helpButton         — round "?" button
#  10  .smallSquare        — compact square, honours height
#  11  .toolbar            — toolbar pill (was TexturedRounded)
#  12  .accessoryBarAction — small flat action in a bar
#  13  .accessoryBar       — inset bar background (was Recessed)
#  14  .pushDisclosure     — pill + disclosure arrow
#  15  .badge              — small pill / circle on macOS 14+ (was Inline)
#  16  .glass              — new in macOS 26; frosted/vibrant glass effect
#
# ICON_PT / SIZE sets the air around the glyph; 0.60–0.70 reads comfortable.
# GS3-era defaults were SIZE 26, ICON_PT 22, BEZEL 2 (RegularSquare).
#
# Per-host presets, picked by HOST_MAJOR (above). Each new per-host-tuned
# constant group follows the same pattern: a `_<name>_GS3` and a
# `_<name>_GS4`, then one line that selects. Keeps the branches visible
# at the top of the file and avoids per-usage `if HOST_MAJOR ==` checks.
_BTN_GS3 = SimpleNamespace(
	SIZE     = 26,   # GS3-era frame
	ICON_PT  = 22,
	BEZEL    = 2,    # .flexiblePush (RegularSquare on GS3)
	ICON_KICK = -0.1,
)
_BTN_GS4 = SimpleNamespace(
	SIZE     = 22,   # tuned by hand for GS4
	ICON_PT  = 22,
	BEZEL    = 16,   # .glass — new in macOS 26
	ICON_KICK = -0.1,
)
BTN = _BTN_GS3 if HOST_MAJOR == 3 else _BTN_GS4

# - Universal spacing -----------------------------------------------------
# Per-host presets (same split pattern as BTN above). GS3 values are the
# pre-split originals from commit 3bbdded; GS4 values are tuned to match
# macOS 15+ breathing room — the GS3 numbers read as cramped on GS4 and
# the GS4 numbers read as oversized on GS3.
_LAYOUT_GS3 = SimpleNamespace(
	GAP       = 12,   # inter-widget gap on a row
	PAD       = 14,   # group-box inner padding
	MARGIN    = 12,   # window edge inset (masthead x-start, fold offset)
	TIT       = 18,   # section title (TextBox) height
	TIT_GAP   = 2,    # tight gap below a section title before its widgets
	TAB_INSET = 10,   # tab-inner inset for configurator / tab contents
)
_LAYOUT_GS4 = SimpleNamespace(
	GAP       = 16,
	PAD       = 18,
	MARGIN    = 18,
	TIT       = 22,
	TIT_GAP   = 2,
	TAB_INSET = 10,
)
LAYOUT = _LAYOUT_GS3 if HOST_MAJOR == 3 else _LAYOUT_GS4

# - Entry fields (TR Panel) -----------------------------------------------
# Every non-button control a Panel tab places on a button row: numeric and
# text fields, popups, combo boxes, segmented switches, check boxes, sliders
# and form labels. Each kind takes the same three parameters (same scheme as
# the Toolbar's PALETTE.ENTRY in palette_config.py, but in px — the Panel
# has no grid):
#   STYLE : vanilla sizeStyle — 'mini', 'small' or 'regular' (NSControlSize);
#           sets the font size and the natural height of the control
#   W     : width in px; None = to the right edge of the tab (-LAYOUT.PAD)
#   H     : height in px; None = the control's natural height for STYLE.
#           Taller text fields keep their text at the top (AppKit), so
#           prefer a bigger STYLE over a bigger H
# Place them with gui/entry.py (add_entry): the control is centred
# vertically on the BTN row and keeps CLEAR px from the buttons on both
# sides. CLEAR covers vanilla's +6 px frame padding around every
# vanilla.Button (frameAdjustments 'regular' = (-6, -8, 12, 12)), the
# control's own padding (popup 3 px) and a visible gap. A field placed
# right after `x += BTN + small_gap` runs into the button's drawn bezel.
def _entry(style, w, h=None):
	return SimpleNamespace(STYLE=style, W=w, H=h)

_ENTRY_GS3 = SimpleNamespace(
	NUM     = _entry('regular', 50),    # numeric EditText (sizes, angles, transforms)
	TEXT    = _entry('regular', None),  # free-text EditText (names, lists)
	POPUP   = _entry('regular', 120),   # PopUpButton (mode / layer choice)
	COMBO   = _entry('regular', 120),   # ComboBox (choice or typed value)
	SEGMENT = _entry('regular', 120),   # SegmentedButton (view switch)
	CHECK   = _entry('regular', 150),   # CheckBox with a short title
	SLIDER  = _entry('regular', 120),   # Slider
	LABEL   = _entry('regular', 80),    # TextBox caption ("Collinear:") before a field
	CLEAR   = 10,                       # space between a vanilla.Button and a control (>= 6 + 3 + gap)
)
_ENTRY_GS4 = SimpleNamespace(
	NUM     = _entry('regular', 50),
	TEXT    = _entry('regular', None),
	POPUP   = _entry('regular', 120),
	COMBO   = _entry('regular', 120),
	SEGMENT = _entry('regular', 120),
	CHECK   = _entry('regular', 150),
	SLIDER  = _entry('regular', 120),
	LABEL   = _entry('regular', 80),
	CLEAR   = 12,
)
ENTRY = _ENTRY_GS3 if HOST_MAJOR == 3 else _ENTRY_GS4

# - Numeric EditText (legacy) ---------------------------------------------
# TR Panel tabs use ENTRY above. SPN is kept for gui/dialogs.py and the
# IconAssist panels; do not use it in new code.
SPN = SimpleNamespace(
	W          = 44,         # standard numeric edit width
	W_WIDE     = 50,         # wider — for angles, long transforms, big ranges
	H          = BTN.SIZE,   # match button height; do NOT hardcode a value
	SIZE_STYLE = 'small',    # None, 'small', or 'mini' — apply everywhere
	GAP_AFTER  = 2,          # tight gap between a spinbox and the next widget
)

# - Short single-char labels (X / Y axis letters etc.) --------------------
# Narrow ENTRY.LABEL columns placed immediately before a field.
LBL = SimpleNamespace(
	W         = 14,  # single-char label column width
	GAP_AFTER = 4,   # gap between a label (any width) and its field
)

# - Form rows (label + field grids, check boxes, text buttons) -----------
# Dense parameter tabs (Cleanup, Stem Snap) lay out "Label: [field]" pairs
# in columns. Each row is a BTN-high slot (fields centred on it, as on a
# button row); ROW = BTN.SIZE + ROW_GAP. ROW_GAP must keep the drawn
# frames of regular popups (24 px + vanilla padding 6) apart.
_FORM_GS3 = SimpleNamespace(
	ROW_GAP    = 6,       # vertical gap between form rows
	CHK_H      = 22,      # check-box grid row pitch (regular CheckBox: 16 + 4 padding)
	BTN_W      = 90,      # text button width (three per row at WIN.W)
	BTN_STYLE  = 'small', # NSControlSize for text buttons
)
_FORM_GS4 = SimpleNamespace(
	ROW_GAP    = 8,
	CHK_H      = 22,
	BTN_W      = 90,
	BTN_STYLE  = 'small',
)
FORM = _FORM_GS3 if HOST_MAJOR == 3 else _FORM_GS4
FORM.ROW = BTN.SIZE + FORM.ROW_GAP   # form row pitch (derived)

# - Table (vanilla.List) --------------------------------------------------
# Column widths named by purpose so panels can reference them instead of
# inlining raw numbers in columnDescriptions dicts.
_LIST_ROW_H    = 19  # row pitch incl. intercell spacing (17 + 2 on pre-26 macOS; 17 on macOS 26)
_LIST_HEADER_H = 28  # header view height (macOS 26; 23-25 earlier)
_LIST_ROWS     = 6   # minimum visible rows (3 masters + room)

LIST = SimpleNamespace(
	ROWS        = _LIST_ROWS,
	H           = _LIST_HEADER_H + _LIST_ROWS * _LIST_ROW_H + 4,  # table height for ROWS rows (+ border)
	COL_W       = 56,   # numeric column width (default)
	COL_CHECK_W = 20,   # checkbox column (tight)
	COL_TAG_W   = 32,   # short tag column (On, Version)
	COL_TYPE_W  = 80,   # layer-type column
	COL_NARROW_W = 40,  # narrow numeric column (Delta targets)
	COL_UNITS_W = 36,   # checkbox column with a short title (Delta target Units)
	CELL_GAP    = 4,    # horizontal intercell spacing for dense tables (macOS 26 default is 17)
)

# - Colour-coded list (gui/tint_list.py, TRTintList) ---------------------
# A vanilla.List2 whose rows are colour coded by a "kind" value: a dot
# column (filled or hollow circle) and a light full-row tint. Colours name
# NSColor class methods (system colours follow light / dark mode); None =
# no colour for that kind. LAYER_COLORS is the default map (layer types as
# gui/dialogs.layer_kind names them). One set for GS3 + GS4.
TINTLIST = SimpleNamespace(
	DOT_D          = 10,     # dot diameter (pt)
	DOT_LINE       = 1.5,    # outline width of a hollow dot (pt)
	DOT_COL_W      = 22,     # dot column width
	TINT           = 0.12,   # row tint alpha; 0 = no tint
	FILLED         = False,  # default dot: hollow
	FILL_ON_SELECT = True,   # selected rows flip their dot (hollow <-> filled)
	LAYER_COLORS   = {
		'Master'  : 'systemGreenColor',
		'Brace'   : 'systemBlueColor',
		'Bracket' : 'systemPurpleColor',
		'Color'   : 'systemOrangeColor',
		'Mask'    : 'systemRedColor',
		'Layer'   : None,
	},
)

# - Outline thumbnails (gui/thumbnail.py) --------------------------------
# Contours drawn as images: thumb_image() and the TRThumbGrid picker
# (Clipboard bank and later part pickers). SIZES are the cell edge in pt;
# the grid cycles through them. Stroke and node sizes are in thumbnail pt,
# so they stay the same at every SIZE. TONES name NSColor class methods
# (system colours follow light / dark mode); a tone is picked per item.
_THUMB_GS3 = SimpleNamespace(
	SIZES      = (48, 64, 96, 128),  # cell edge (pt), cycled by the grid
	SIZE_INDEX = 1,                  # default entry in SIZES
	INSET      = 6,      # outline-to-cell-edge margin inside the image
	PAD        = 8,      # grid inset from the scroll view edge
	GAP        = 8,      # space between grid cells
	CAP_H      = 14,     # caption height under a cell (0 = no caption)
	CAP_STYLE  = 'mini', # NSControlSize for captions
	STROKE     = 1.5,    # open-contour stroke width (pt)
	NODE       = 2.,     # on-curve node dot radius (pt)
	BEZEL      = 2,      # cell button bezel (.flexiblePush honours height; shows the on state)
	WINDING    = 'nonzero',  # fill rule: 'nonzero' (Glyphs, direction matters) or 'evenodd'
)
_THUMB_GS4 = SimpleNamespace(**vars(_THUMB_GS3))
THUMB = _THUMB_GS3 if HOST_MAJOR == 3 else _THUMB_GS4
THUMB.TONES = {
	'label'  : 'labelColor',          # default outline
	'muted'  : 'tertiaryLabelColor',  # context drawn behind a part
	'accent' : 'controlAccentColor',
	'green'  : 'systemGreenColor',    # Clipboard: all masters copied
	'blue'   : 'systemBlueColor',     # Clipboard: some masters
	'red'    : 'systemRedColor',      # Clipboard: one layer only
}

# - Status text -----------------------------------------------------------
STATUS = SimpleNamespace(
	H          = 34,       # two-line status / warning text under a panel
	SIZE_STYLE = 'small',  # NSControlSize for status labels
)

# - Main window -----------------------------------------------------------
WIN = SimpleNamespace(
	W        = 420,  # default FloatingWindow width (Delta Bake targets table: name + 5 columns)
	H        = 780,  # default FloatingWindow height (picker folded away); fits Delta Bake with 6-row tables
	MIN_W    = 300,  # minSize width
	MIN_H    = 300,  # minSize height
)

# - Masthead band ---------------------------------------------------------
MASTHEAD = SimpleNamespace(
	H        = 44,   # masthead band height (>= BTN.SIZE + top inset)
	TITLEBAR = 20,   # approximate macOS title-bar height; used by fold
)

# - Dialogs (compact modeless windows) ------------------------------------
# Deliberately tighter than LAYOUT so dialogs feel compact. Covers
# TRMasterValuesDialog and the legacy TRLayerSelectDialog in gui/dialogs.py.
# One set for GS3 + GS4 — tune if dialog chrome needs splitting later.
# Prefix convention: unprefixed = shared tight spacing; LP_ = legacy
# layer-picker; MV_ = master-values dialog (slightly roomier set).
DIALOG = SimpleNamespace(
	# Shared tight dialog spacing
	PAD        = 8,
	ROW_H      = 28,
	BTN_W      = 28,
	BTN_GAP    = 4,
	SEARCH_H   = 22,
	# Legacy TRLayerSelectDialog (unused since inline picker landed)
	LP_W       = 320,
	LP_H       = 520,
	LP_MIN_W   = 260,
	LP_MIN_H   = 320,
	# TRMasterValuesDialog (its own slightly roomier spacing)
	MV_PAD     = 10,
	MV_LBL_H   = 36,
	MV_BTN_H   = 24,
	MV_BTN_GAP = 8,
	MV_NAME_W  = 160,
	MV_W       = 420,
	MV_H       = 380,
	MV_MIN_W   = 360,
	MV_MIN_H   = 280,
)

# - Inline layer-picker band ----------------------------------------------
# Lives below the masthead inside a SplitView; collapsible. Replaces the
# former floating layer-picker dialog, which crashed Glyphs 4 on close
# via its own X button under this Python 3.14 / pyobjc build.
# The band must fit the action row (BTN) + search row (SPN) + at least
# a few table rows; 260 gives ~168 px of table at default.
PICKER = SimpleNamespace(
	H        = 260,  # default expanded height; user can drag to resize
	MIN_H    = 92,   # min that still shows action row + search row
)

# - Assets ----------------------------------------------------------------
ASSETS = SimpleNamespace(
	ICON_TTF = 'typerig-icons.ttf',  # icon-font filename inside Resources/
)


# Top-level UI namespace — the only symbol importers should reach for.
UI = SimpleNamespace(
	BTN      = BTN,
	LAYOUT   = LAYOUT,
	ENTRY    = ENTRY,
	SPN      = SPN,
	LBL      = LBL,
	FORM     = FORM,
	LIST     = LIST,
	TINTLIST = TINTLIST,
	THUMB    = THUMB,
	STATUS   = STATUS,
	WIN      = WIN,
	MASTHEAD = MASTHEAD,
	PICKER   = PICKER,
	DIALOG   = DIALOG,
	ASSETS   = ASSETS,
)
