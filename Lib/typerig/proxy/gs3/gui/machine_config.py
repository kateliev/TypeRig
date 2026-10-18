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
	W           = 1060,   # default window width: the left third holds the input buttons row
	MIN_W       = 1060,   # = W: the service row and the left column's button bar do not reflow
	TABS_TOP    = 8,      # tab view inset from the window top
	TABS_CHROME = 30,     # tab view height beyond its item view (tab bar + frame; macOS 26)
	TABS_SIDE   = 16,     # tab view width beyond its content (frame, both sides)
	INSET       = 10,     # inset of a tab's content from the tab frame
)
_WIN_GS4 = SimpleNamespace(
	W           = 1060,
	MIN_W       = 1060,
	TABS_TOP    = 10,
	TABS_CHROME = 30,
	TABS_SIDE   = 16,
	INSET       = 12,
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
	STEM    = 52,       # V st. / H st.
	DIM     = 66,       # Width / Height ('60 %', '700 u')
	GROUP   = 110,      # Group name (targets)
	CHECK   = 40,       # Anchors / Metrics / Kerning check boxes
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
)

MACHINE = SimpleNamespace(
	WIN      = _WIN_GS3 if HOST_MAJOR == 3 else _WIN_GS4,
	LIST     = LIST,
	COLUMNS  = COLUMNS,
	SERVICE  = SERVICE,
	ADVANCED = ADVANCED,
	COLORS   = COLORS,
)
