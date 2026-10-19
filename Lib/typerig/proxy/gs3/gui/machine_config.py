# encoding: utf-8
"""
TypeRig Delta Machine — UI configuration.

Sizes of the Delta Machine window (TypeRig Delta Machine.glyphsPlugin):
a wide window with three tabs and list pairs (1/3 | 2/3). Buttons, gaps,
entry fields, lists and the colour-coded list come from config.py (UI), as
in TR Panel; only what is particular to this window lives here.

Same rules as config.py: no layout literal in the plugin; add a field here
first, then alias it. GS3 / GS4 presets, picked by HOST_MAJOR.

    from typerig.proxy.gs3.gui.machine_config import MACHINE
    WIN_W = MACHINE.WIN.W
"""
from __future__ import division, print_function, unicode_literals

from types import SimpleNamespace

from .config import HOST_MAJOR, _LIST_ROW_H, _LIST_HEADER_H


# - Window ----------------------------------------------------------------
# Resizable both ways: the lists stretch, the columns keep COLUMNS.SPLIT.
# The default height comes from the tab content at LIST.ROWS rows.
_WIN_GS3 = SimpleNamespace(
	W           = 1340,   # default window width: the targets table fits without scrolling (Layer ~150 px)
	MIN_W       = 1100,   # the service row and the left column's button bar do not reflow
	TABS_TOP    = 8,      # tab view inset from the window top
	TABS_CHROME = 30,     # tab view height beyond its item view (tab bar + frame; macOS 26)
	TABS_SIDE   = 16,     # tab view width beyond its content (frame, both sides)
	INSET       = 10,     # inset of a tab's content from the tab frame
	PROGRESS_H  = 12,     # bake progress bar above the status line
	PROGRESS_GAP = 6,     # progress bar to status line
)
_WIN_GS4 = SimpleNamespace(
	W           = 1340,
	MIN_W       = 1100,
	TABS_TOP    = 10,
	TABS_CHROME = 30,
	TABS_SIDE   = 16,
	INSET       = 12,
	PROGRESS_H  = 12,
	PROGRESS_GAP = 6,
)

# - Lists -----------------------------------------------------------------
# Row pitch and header height as config.py's UI.LIST (macOS 26 values).
# The window is resizable: lists open at ROWS and stretch with the window;
# MIN_ROWS sets the smallest window height.
_ROWS, _MIN_ROWS = 14, 6
LIST = SimpleNamespace(
	ROWS     = _ROWS,                                         # visible rows at the default height
	H        = _LIST_HEADER_H + _ROWS * _LIST_ROW_H + 4,       # table height (+ border)
	MIN_ROWS = _MIN_ROWS,
	MIN_H    = _LIST_HEADER_H + _MIN_ROWS * _LIST_ROW_H + 4,
)

# - Columns ---------------------------------------------------------------
# The list pair of a tab: left = SPLIT of the content width, right = the
# rest (GAP between them). Column widths of the tables (the first text
# column of each table takes the remaining width).
COLUMNS = SimpleNamespace(
	SPLIT   = 1. / 3,   # left list share of the tab width
	STEM    = 48,       # V st. / H st.
	DIM     = 60,       # Width / Height ('60 %', '700 u')
	GROUP   = 100,      # Group name (targets)
	CHECK   = 38,       # Anchors / Metrics / Kerning check boxes
	RESULT  = 64,       # last bake of a row: '12/14 +3c'
	ORIGIN  = 108,      # transform origin popup of a row ('Bottom middle')
	LAYER_MIN = 100,    # target layer name: never narrower (the table scrolls instead)
	AX_TAG  = 48,       # Designspace tab, axes: tag
	AX_NUM  = 46,       # Designspace tab, axes: min / default / max
	AX_NAME_MIN = 80,   # Designspace tab, axes: name never narrower
	DRIVER  = 84,       # Designspace tab, axes: 'Driven by' popup
	M_NAME  = 130,      # Designspace tab, masters: name
	SOURCE  = 150,      # Designspace tab, masters: where a new master comes from
	COORD   = 76,       # Designspace tab, masters: one coordinate column per axis
	DEFAULT = 52,       # Designspace tab, masters: default (origin) check box
	COUNT   = 44,       # glyph count (groups)
	REF     = 52,       # reference glyph (groups)
	UNICODE = 56,       # Unicode (glyphs of a group)
	CASE    = 84,       # case / category (glyphs of a group)
)

# - Setup service row ----------------------------------------------------
# Four check boxes share the row with seven buttons and two popups, so they
# are sized to their titles ('Skip composites' is the longest) instead of
# UI.ENTRY.CHECK.W.
SERVICE = SimpleNamespace(
	CHECK_W = 128,
)

# - Advanced tab ---------------------------------------------------------
ADVANCED = SimpleNamespace(
	LABEL_W = 150,      # form label column
	FIELD_W = 220,      # popups / fields
	NOTES_H = 120,      # notes text box
	NOTE_H  = 34,       # two-line explanation above the form
	# Glyph flags / Log sections above the mock-up form
	CHECK_W = 190,      # section check boxes ('Flag processed glyphs')
	SWATCH_LABEL_W = 70,   # 'Done:' / 'Warnings:' / 'Failed:' before a colour well
	COLOR   = SimpleNamespace(STYLE=None, W=44, H=24),   # vanilla.ColorWell (add_entry preset; it has no sizeStyle)
	PATH    = SimpleNamespace(STYLE='small', W=420, H=None),   # log folder (TextBox, truncated in the middle)
	SECTION_GAP = 10,   # extra space above a section title
	# Italic block (v0.3): beside the Engine mock-up form, from its title down
	ITALIC_X       = 560,  # left edge of the block (the Engine form and the notes end before it)
	ITALIC_LABEL_W = 110,  # 'Italic angle:' and number captions
	ITALIC_COLUMNS = 2,    # italic fix check boxes per row
	ITALIC_CHECK_W = 200,  # one check box column
)

# - Colours ----------------------------------------------------------------
# NSColor class-method names (follow light / dark mode). Groups get the
# next colour of GROUP_COLORS when they are made; the colour is stored in
# the group. Selection rows are grey. CASE_COLORS colour the glyphs of a
# group by case / category (glyph_filters.glyph_kind).
COLORS = SimpleNamespace(
	SELECTION    = 'systemGrayColor',
	GROUP_COLORS = ('systemBlueColor', 'systemOrangeColor', 'systemGreenColor', 'systemPurpleColor',
	                'systemPinkColor', 'systemTealColor', 'systemYellowColor', 'systemRedColor',
	                'systemBrownColor', 'systemIndigoColor'),
	CASE_COLORS  = {
		'Uppercase': 'systemBlueColor',
		'Lowercase': 'systemGreenColor',
		'Smallcaps': 'systemTealColor',
		'Figure'   : 'systemOrangeColor',
		'Mark'     : 'systemPurpleColor',
		'Other'    : None,
		'Missing'  : 'systemRedColor',     # in the group, not in the font
	},
	MASTER_COLORS = {	# Designspace tab: masters by what Apply does with them
		'Font'  : 'systemGreenColor',      # in the font
		'New'   : 'systemBlueColor',       # added on Apply (empty or a copy)
		'Target': 'systemOrangeColor',     # added on Apply from a Delta target layer
		'Remove': 'systemRedColor',        # removed on Apply
	},
	AXIS_COLORS = {
		'Font'  : 'systemGreenColor',
		'New'   : 'systemBlueColor',
	},
)

MACHINE = SimpleNamespace(
	WIN      = _WIN_GS3 if HOST_MAJOR == 3 else _WIN_GS4,
	LIST     = LIST,
	COLUMNS  = COLUMNS,
	SERVICE  = SERVICE,
	ADVANCED = ADVANCED,
	COLORS   = COLORS,
)
