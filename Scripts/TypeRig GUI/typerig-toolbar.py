#FLM: TypeRig: Toolbar
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Description ------------------
# The one TypeRig Toolbar. One button table (typerig.proxy.fl.gui.toolbar_buttons.toolbar_sections), two
# renderers - each platform gets the UI that actually works there, with the same icons in the same order.
#
# macOS  : a native FontLab panel (Window > Panels > Custom Panels) that drags and docks on every edge,
#          tabs with FontLab's own panels and reflows its buttons - rows when wide, columns when docked
#          left / right.
# Windows: the classic TypeRig toolbars - one native QToolBar per section on the main window. Windows
#          handles them natively: dock on all four toolbar areas, vertical when docked left / right,
#          wrapped into rows with a >> overflow menu. A native FontLab panel is impossible here, since
#          FontLab.exe exports no symbols at all (measured - see FL-native-panels.md, section 13).
#
# Contents and order follow the TypeRig Glyphs palette, driven by the full TypeRig controller:
# layers Active / Masters / Selected (+ layer dialog) and glyph scope active glyph / glyph window /
# font window selection.
#
# Re-running the script re-uses the registered panel (FontLab can not unregister a panel) and
# rebuilds its content with the current code.
#
# All logic lives in typerig.proxy.fl.gui: toolbar_buttons (THE button table + the macOS widget builder),
# toolbar_bars (the Windows QToolBars), native_panel (the macOS panel + its layout), toolbar_actions
# (scope state + callbacks). See Docs/Proxy/Documents/FL-native-panels.md and FL-toolbar-parity.md.

# - Dependencies -----------------
from __future__ import absolute_import, print_function

from platform import system

# - Init --------------------------
tool_version = '3.2'
tool_name = 'TypeRig Toolbar'

panel_id = 7210 # Must be unique among FontLab panels
panel_title = 'TypeRig Toolbar'

# - RUN ------------------------------
if system() == 'Windows':
	from typerig.proxy.fl.gui.toolbar_bars import TRToolbarBars

	TRToolbarBars().open()

else:
	from typerig.proxy.fl.gui.native_panel import TRNativePanel
	from typerig.proxy.fl.gui.toolbar_buttons import TRToolbarBuilder

	TRNativePanel(panel_id, panel_title, TRToolbarBuilder()).open()
