# MODULE: TypeRig / Proxy / FontLab / Devtools
# -----------------------------------------------------------
# Developer tools for driving and inspecting TypeRig inside a
# running FontLab: press TypeRig Panel controls, click and drag
# on the glyph canvas, take screenshots, snapshot and diff glyph
# data, read the History panel, reload TypeRig code in place.
#
# Made for live testing by people and by coding agents (for
# example over FontLab's MCP bridge, run_python). Nothing here
# knows about MCP, and nothing in TypeRig imports this package:
# it runs only when you import it.
#
# WARNING: canvas actions move the REAL mouse pointer (FontLab
# reads the cursor position, not the event position) and put it
# back afterwards. Do not use the mouse while a test runs.
#
# Usage (FontLab Python, Macro panel or run_python):
#   import typerig.proxy.fl.devtools as dt
#   print(dt.info())
#   dt.panel_open(); print(dt.controls('Element'))
#   a = dt.snapshot(layers=['Regular'])
#   dt.drag((100, 200), (150, 200))
#   print(dt.diff(a, dt.snapshot(layers=['Regular'])))
#   print(dt.shot('canvas', crop='glyph'))
#   dt.undo(); print(dt.history())
#   dt.reload_typerig()     # pick up code edits without restarting
#
# Modules:
#   app     - Qt helpers, FontLab actions, undo/redo, History panel
#   canvas  - glyph canvas: mapping, mouse and key input, glyph window
#   trpanel - TypeRig Panel: open, tabs, list/find/press/set controls
#   state   - glyph snapshots (nodes, element transforms, metrics) + diff
#   shots   - screenshots of the canvas, panel or main window
#   session - overlays, reload of TypeRig modules, info()
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import absolute_import, print_function

from typerig.proxy.fl.devtools.app import qv, app, pump, wait, main_window, actions, action, undo, redo, history
from typerig.proxy.fl.devtools.canvas import viewport, mapping, to_px, to_font, hover, click, drag, key, open_glyph, current, glyph_box
from typerig.proxy.fl.devtools.trpanel import panel, panel_open, panel_close, tabs, tab, controls, find, press, set_value
from typerig.proxy.fl.devtools.state import snapshot, diff
from typerig.proxy.fl.devtools.shots import shot, output_dir, set_output_dir
from typerig.proxy.fl.devtools.session import overlays, stop_overlays, reload_typerig, info

# - Init --------------------------------
__version__ = '0.1.0'
