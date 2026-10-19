# encoding: utf-8
"""
TypeRig Delta Italic Lab — UI configuration.

Sizes of the Delta Italic Lab window (TypeRig Delta Italic Lab.glyphsPlugin):
one narrow, fixed window, top to bottom: Live Axis list, sliders, options,
italic fix switches, buttons, status. Buttons, gaps, entry fields and form
rows come from config.py (UI); only what is particular to this window lives
here.

Same rules as config.py: no layout literal in the plugin; add a field here
first, then alias it.

    from typerig.proxy.gs3.gui.lab_config import LAB
    WIN_W = LAB.WIN.W
"""
from __future__ import division, print_function, unicode_literals

from types import SimpleNamespace

from .config import _LIST_ROW_H, _LIST_HEADER_H

# - Window ----------------------------------------------------------------
WIN = SimpleNamespace(
	W = 440,              # fixed width: slider rows and the two check box columns fit
)

# - Live Axis list --------------------------------------------------------
_ROWS = 4
LIST = SimpleNamespace(
	ROWS = _ROWS,
	H    = _LIST_HEADER_H + _ROWS * _LIST_ROW_H + 4,   # table height (+ border)
)

# - Slider rows -----------------------------------------------------------
# Caption | slider (stretches) | value field (UI.ENTRY.NUM).
SLIDER = SimpleNamespace(
	LABEL_W   = 90,       # caption column
	STYLE     = 'small',  # slider and caption size
	SX_RANGE  = (40, 160),   # width %, slider ends
	SY_RANGE  = (40, 160),   # height %, slider ends
	STEM_SPAN = (.25, 1.75), # stem slider ends: x min / max Live Axis stem
)

# - Check boxes and numbers ----------------------------------------------
FORM = SimpleNamespace(
	COLUMNS   = 2,        # italic switches: two columns
	NUM_LABEL_W = 150,    # caption of the italic number fields
	STATUS_LINES = 4,     # status text lines (fix report + messages)
)

LAB = SimpleNamespace(WIN=WIN, LIST=LIST, SLIDER=SLIDER, FORM=FORM)
