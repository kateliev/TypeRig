# MODULE: TypeRig / Proxy / FontLab / GUI / Toolbar Bars
# NOTE	: The Windows renderer of the TypeRig Toolbar: the shared button table as plain QToolBars with
#	  QActions on FontLab's main window - the way TypeRig toolbars worked before 3.0, which Windows
#	  handles natively: dock in all four toolbar areas, turn vertical when docked left / right, float,
#	  and move what does not fit into the >> overflow menu.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# One toolbar per section of toolbar_sections() (plus the scope masthead), created in table order, so the
# icon order is exactly the one of the native panel on macOS. Qt gives each bar its own grip, so the user
# can move them around one by one.
#
# Re-running the script keeps the bars themselves and swaps only their actions: the arrangement the user
# made survives, and the callbacks are always the freshly imported code. Old actions are parked, never
# deleted (PythonQt + a live connection = a double delete, see FL-native-panels.md section 8).
#
# Why not the native panel here: FontLab.exe exports no symbols on Windows, so registerCustomPanel can not
# be called at all - see Docs/Proxy/Documents/FL-native-panels.md, section 13.

# - Dependencies --------------------------
from __future__ import absolute_import, print_function

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont
from typerig.proxy.fl.gui.toolbar_buttons import toolbar_sections, TRToolbarMasthead
from typerig.proxy.fl.gui.toolbar_actions import TRToolbarState, TRToolbarActions, guarded

# - Init ----------------------------------
__version__ = '1.0'

OBJECT_PREFIX = 'TR_TOOLBAR_BAR_'
TOP_AREA = 4 # Qt.TopToolBarArea (plain int: PythonQt hands enums over as numbers)
LEGACY_PANELS = ('TR_TOOLBAR_PANEL', 'TR_TOOLBAR_DOCK_PANEL')

# Long lived state. FontLab resets script namespaces between runs, but modules imported from the library
# stay in sys.modules, so everything that must survive a re-run lives here.
_STATE = {'bars': [], 'refs': []}
_GRAVEYARD = [] # Retired actions, kept alive on purpose

# - Helpers -------------------------------
def is_alive(widget):
	try:
		widget.objectName
		return True
	except Exception:
		return False

def make_action(owner, spec, font):
	'''One toolbar action from a Button spec of the shared table (the icon font renders the token)'''
	action = QtGui.QAction(spec.token, owner)
	action.setToolTip(spec.tip or '')
	action.setFont(font)
	action.setCheckable(spec.checkable)

	if spec.checkable and spec.checked: action.setChecked(True)

	if spec.callback is None: action.setEnabled(False) # Placeholder cell
	else: action.triggered.connect(guarded(spec.callback, spec.name)) # guarded() swallows the checked flag

	return action

def make_action_group(owner):
	'''Exclusive group of actions. Returns (group, add) - see TRToolbarMasthead'''
	group = QtGui.QActionGroup(owner)
	group.setExclusive(True)
	return group, group.addAction

# - Toolbars ------------------------------
class TRToolbarBars(object):
	'''The TypeRig Toolbar as native QToolBars on FontLab's main window (Windows).'''
	def __init__(self, state=None, actions=None):
		self.state = state or TRToolbarState()
		self.actions = actions or TRToolbarActions(self.state)
		self.main_window = fl6.MainWindow()

	# - Bars -------------------------------
	def bar(self, key, caption):
		'''The bar for <key>: the one of an earlier run emptied of its actions, or a new one'''
		name = OBJECT_PREFIX + key
		bar = self.main_window.findChild(QtGui.QToolBar, name)

		if bar is not None and is_alive(bar):
			for action in bar.actions():
				bar.removeAction(action)
				action.setParent(None)
				_GRAVEYARD.append(action)
		else:
			bar = QtGui.QToolBar(caption, self.main_window)
			bar.setObjectName(name)
			bar.setWindowTitle(caption) # Shown in the toolbar context menu and when the bar floats
			bar.setAllowedAreas(QtCore.Qt.AllToolBarAreas)
			bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly) # The token IS the icon (icon font)
			bar.setMovable(True)
			bar.setFloatable(True)
			self.main_window.addToolBar(TOP_AREA, bar)

		_STATE['bars'].append(bar)
		return bar

	def retire_panel(self):
		'''TypeRig 3.1 briefly put the Windows toolbar in a QDockWidget: take it off the main window'''
		for dock in self.main_window.findChildren(QtGui.QDockWidget):
			if (dock.objectName or '') not in LEGACY_PANELS: continue
			self.main_window.removeDockWidget(dock)
			dock.hide()

	def pack_rows(self):
		'''Qt keeps every toolbar of an area on one row and squeezes the ones that do not fit into their
		>> menu. Break the row where it would overflow, so every bar is visible at once. Only the bars in
		the top area are packed: a bar the user moved to another edge (or floated) is left alone.'''
		bars = [bar for bar in _STATE['bars'] if int(self.main_window.toolBarArea(bar)) == TOP_AREA]
		limit = max(self.main_window.geometry.width() - 24, 200)
		used = 0

		# Re-append them in table order: breaks are placed by that order, and a bar that drifted
		# elsewhere in the top area would otherwise end up squeezed into somebody else's row
		for bar in bars: self.main_window.addToolBar(TOP_AREA, bar)

		for index, bar in enumerate(bars):
			self.main_window.removeToolBarBreak(bar)
			width = bar.sizeHint.width()

			if index and used + width > limit:
				self.main_window.insertToolBarBreak(bar)
				used = 0

			used += width

	# - Public API -------------------------
	def open(self):
		'''(Re)build the content of every bar and show them all. Returns the number of bars.'''
		self.retire_panel()

		_STATE['bars'] = []
		_STATE['refs'] = []
		refs = _STATE['refs']

		font = getTRIconFont()
		act = self.actions
		act.widgets.clear()
		groups = {}

		# - Masthead (layer scope, glyph scope) in its own bar
		bar = self.bar('scope', 'TypeRig Scope')
		masthead = TRToolbarMasthead(self.state, bar, font, make_action, make_action_group)
		refs.append(masthead)

		for action in masthead.layers + masthead.glyphs:
			bar.addAction(action)

		# - One bar per section, in table order
		for key, caption, section_groups in toolbar_sections(act):
			bar = self.bar(key, caption)

			for group in section_groups:
				for spec in group:
					action = make_action(bar, spec, font)

					if spec.exclusive:
						if spec.exclusive not in groups:
							groups[spec.exclusive] = make_action_group(bar)
							refs.append(groups[spec.exclusive][0])
						groups[spec.exclusive][1](action)

					act.widgets[spec.name] = action
					bar.addAction(action)

		refs.append(act)

		for bar in _STATE['bars']: bar.show()
		QtGui.QApplication.processEvents() # The bars need one pass before they report a size hint
		self.pack_rows()

		return len(_STATE['bars'])
