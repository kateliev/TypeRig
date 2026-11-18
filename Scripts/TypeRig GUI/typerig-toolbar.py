#FLM: TypeRig: Toolbar
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Description ------------------
# The one TypeRig Toolbar: a native FontLab panel (Window > Panels > Custom Panels) that drags and docks
# on every edge, tabs with other panels and reflows its buttons: rows when wide, columns when docked
# left / right. FontLab 8 and 9, macOS and Windows.
#
# Contents and order follow the TypeRig Glyphs palette, driven by the full TypeRig controller:
# layers Active / Masters / Selected (+ layer dialog) and glyph scope active glyph / glyph window /
# font window selection.
#
# Re-running the script re-uses the registered panel (FontLab can not unregister a panel) and
# rebuilds its content with the current code.
#
# All logic lives in typerig.proxy.fl.gui: native_panel (panel + layout), toolbar_buttons (button table),
# toolbar_actions (scope state + callbacks). See Docs/Proxy/Documents/FL-native-panels.md and
# FL-toolbar-parity.md.

# - Dependencies -----------------
from __future__ import absolute_import, print_function

from typerig.proxy.fl.gui.native_panel import TRNativePanel
from typerig.proxy.fl.gui.toolbar_buttons import TRToolbarBuilder

# - Init --------------------------
tool_version = '3.0'
tool_name = 'TypeRig Toolbar'

panel_id = 7210 # Must be unique among FontLab panels
panel_title = 'TypeRig Toolbar'

# - RUN ------------------------------
TRNativePanel(panel_id, panel_title, TRToolbarBuilder()).open()
