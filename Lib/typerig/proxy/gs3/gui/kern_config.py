# encoding: utf-8
"""
TR Kern — UI configuration.

Sizes of the TR Kern window (TypeRig Kern.glyphsPlugin): tabs Pairs,
Groups, Cleanup, Analyze, Rules, Strings, Import, Job (blocks | items | preview), Help. Buttons, gaps, entry fields and lists come from config.py
(UI), as in TR Panel; only what is particular to this window lives here.

Same rules as config.py: no layout literal in the plugin; add a field here
first, then alias it. GS3 / GS4 presets, picked by HOST_MAJOR.

    from typerig.proxy.gs3.gui.kern_config import KERN
    WIN_W = KERN.WIN.W
"""
from __future__ import division, print_function, unicode_literals

from types import SimpleNamespace

from .config import HOST_MAJOR, _LIST_ROW_H, _LIST_HEADER_H


# - Window ----------------------------------------------------------------
# Resizable both ways: lists and reports stretch, columns keep COLUMNS.SPLIT.
_WIN_GS3 = SimpleNamespace(
	W           = 1160,   # default window width: the sources table fits without scrolling
	MIN_W       = 1000,   # the Pairs operations and the button bars do not reflow
	TABS_TOP    = 8,      # tab view inset from the window top
	TABS_CHROME = 30,     # tab view height beyond its item view (tab bar + frame; macOS 26)
	TABS_SIDE   = 16,     # tab view width beyond its content (frame, both sides)
	INSET       = 10,     # inset of a tab's content from the tab frame
)
_WIN_GS4 = SimpleNamespace(
	W           = 1160,
	MIN_W       = 1000,
	TABS_TOP    = 10,
	TABS_CHROME = 30,
	TABS_SIDE   = 16,
	INSET       = 12,
)

# - Lists -----------------------------------------------------------------
_ROWS, _MIN_ROWS = 16, 8
LIST = SimpleNamespace(
	ROWS     = _ROWS,                                         # visible rows at the default height
	H        = _LIST_HEADER_H + _ROWS * _LIST_ROW_H + 4,       # table height (+ border)
	MIN_H    = _LIST_HEADER_H + _MIN_ROWS * _LIST_ROW_H + 4,
)

# - Columns ---------------------------------------------------------------
# Import tab: sources (left SPLIT of the content width) | options + report.
# Column widths of the sources table (the file name takes the rest).
COLUMNS = SimpleNamespace(
	SPLIT   = .5,       # left column share of the tab width
	FILE_MIN = 140,     # file name: never narrower (the table scrolls instead)
	MASTER  = 100,      # master a source goes to
	COUNT   = 52,       # pairs / glyphs / not-in-font counts
	PAIRS_SPLIT = .6,   # Pairs tab: grid share of the tab width (operations panel: the rest)
	KEY     = 120,      # Pairs grid: left / right side (glyph or @group)
	TYPE    = 40,       # Pairs grid: kind (CC / CG / GC / GG)
	VALUE   = 62,       # Pairs grid: one value column per master
	SPREAD  = 56,       # Pairs grid: max - min across the masters
	RULES_SPLIT = 1. / 3,  # Rules tab: rule sets list share (the editor takes the rest)
	RULE_CHECK = 44,    # Rules list: Live / Class check boxes
	JOB_SPLIT = (.25, .33),  # Job tab: blocks | items | preview (the rest), shares of the tab width
	GROUPS_SPLIT = .5,  # Groups tab: groups list share (members: the rest)
	CLEANUP_SPLIT = .5, # Cleanup tab: checks + options share (report: the rest)
	ANALYZE_SPLIT = .4, # Analyze tab: analyses + options share (report tree: the rest)
	FOUND   = 52,       # Cleanup / Analyze lists: findings count
	SAFE    = 66,       # Cleanup list: keeps rendering / changes it
	LEADER  = 110,      # Groups list: leader glyph
	LEAD_MARK = 30,     # Members list: leader mark column
)

# - Forms -----------------------------------------------------------------
# Import options and the Job form: 'Label: [field]' rows, one per option.
FORM = SimpleNamespace(
	LABEL_W = 110,      # caption column ('Class value:', 'Absent pairs:')
	FIELD_W = 190,      # popups
	NUM_W   = 60,       # numbers (tolerance, round, drop, clamp)
	TEXT_W  = 420,      # A / B pair lists (Job)
	CHECK_W = 160,      # 'Use groups'
	BTN_W   = 120,      # text buttons before they are sized to their titles
	OP_W    = 150,      # Pairs: bulk operation popup
	MASTER_W = 130,     # Pairs: master popups (From / To / Mix with / Masters)
	MODE_W  = 140,      # Pairs: copy mode popup
	KIND_W  = 100,      # Pairs: kind filter popup
	SEARCH_MIN = 200,   # Pairs: search field never narrower
	SHORT_LABEL_W = 44, # Pairs: 'From:', 'To:', 'Mix:', 'In:' captions
	TINY_LABEL_W = 20,  # Pairs: one-character captions ('t', '\u00d7', '+')
)
EXPLAIN = SimpleNamespace(
	MIN_H = 120,        # Pairs: explain view never lower
)
RULES = SimpleNamespace(
	REPORT_H = 96,      # Rules: report under the editor
	EDIT_MIN_H = 120,   # Rules: editor never lower
)
GROUPS = SimpleNamespace(
	REPORT_H = 96,      # Groups: report (validate, CLA leaders, log) under the members
	MEMBERS_MIN_H = 120,  # Groups: members list never lower
	NAME_W = 110,       # Groups: new group name field
)
_CLEAN_ROWS, _CHECK_ROW_H = 6, 24   # check-cell rows are taller than text rows (measured at build time too)
CLEANUP = SimpleNamespace(
	LIST_H   = _LIST_HEADER_H + _CLEAN_ROWS * _CHECK_ROW_H + 6,   # the checks list: never lower than this
	LIST_PAD = 6,       # measured list height: border + a little air
	ROWS     = 5,       # option rows under the list
)
_ANALYZE_ROWS = 5
ANALYZE = SimpleNamespace(
	LIST_H   = _LIST_HEADER_H + _ANALYZE_ROWS * _CHECK_ROW_H + 6,   # the analyses list: never lower than this
	LIST_PAD = 6,       # measured list height: border + a little air
	ROWS     = 6,       # option rows under the list (master; nine numbers, two per row)
	LABEL_W  = 76,      # option captions on the number rows ('Extreme:', 'Pressure %:')
)
STRINGS = SimpleNamespace(
	COMBO_W  = 260,     # pattern combo box
	FILLER_W = 110,     # filler combo boxes
	SUFFIX_W = 70,      # suffix fields
	OUT_MIN_H = 120,    # output text never lower
)
NUDGE = SimpleNamespace(	# Pairs grid keys + / -: value step
	STEP   = 5,         # plain
	SHIFT  = 1,         # with Shift (fine)
	OPTION = 25,        # with Option (coarse)
)

# - Report / Help ----------------------------------------------------------
REPORT = SimpleNamespace(
	PAD   = 6,          # text inset inside the report view
	MIN_H = 120,        # report never lower (the window minimum keeps it)
)
HELP = SimpleNamespace(
	PAD = 10,           # text inset inside the help view (both axes)
)

# - Colours ----------------------------------------------------------------
# NSColor class-method names (follow light / dark mode). Sources by state.
COLORS = SimpleNamespace(
	SOURCE = {
		'ready'    : 'systemGreenColor',    # master set, pairs read
		'nomaster' : 'systemOrangeColor',   # no master matched yet
		'empty'    : 'systemRedColor',      # no pairs in the file
	},
	CHECK = {	# Cleanup list: fixes that keep the rendering / that change it
		'safe'     : None,
		'changes'  : 'systemOrangeColor',
	},
	RULE = {	# Rules list: live sets re-run after every change
		'live'     : 'systemGreenColor',
		'plain'    : None,
	},
	PAIR = {	# Pairs grid rows by kind; pending / locked win over the kind
		'pending'  : 'systemOrangeColor',   # changed, not written yet
		'locked'   : 'systemGrayColor',     # never changed by an operation
		'CC'       : None,                  # group + group
		'CG'       : 'systemBlueColor',     # group + glyph (exception)
		'GC'       : 'systemBlueColor',     # glyph + group (exception)
		'GG'       : 'systemPurpleColor',   # glyph + glyph (exception)
	},
)

KERN = SimpleNamespace(
	WIN     = _WIN_GS3 if HOST_MAJOR == 3 else _WIN_GS4,
	LIST    = LIST,
	COLUMNS = COLUMNS,
	FORM    = FORM,
	REPORT  = REPORT,
	EXPLAIN = EXPLAIN,
	RULES   = RULES,
	GROUPS  = GROUPS,
	CLEANUP = CLEANUP,
	ANALYZE = ANALYZE,
	STRINGS = STRINGS,
	NUDGE   = NUDGE,
	HELP    = HELP,
	COLORS  = COLORS,
)
