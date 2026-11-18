#FLM: TypeRig: Toolbar (Dock)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Description ------------------
# macOS variant of typerig-toolbar.py.
#
# On macOS FontLab's QMainWindow is hidden (the visible UI is made of YDock/YFrameWindow
# windows), so Qt toolbars can not dock into it. Instead all TypeRig toolbars are placed
# in a *native FontLab panel* (YPanelWidget) that FontLab itself opens in a YDock. This
# gives the regular FontLab panel behavior: header buttons, drag & dock, tabbing with
# other panels, Window menu and the right-click panel list.
#
# NOTE: Panels must be registered with FontLab (MainWindow::registerCustomPanel), otherwise
# FontLab crashes when it enumerates docks. That function is not exposed to Python, so it is
# called through ctypes (exported symbol). If it is not found (different FontLab build) the
# script stops without touching FontLab's UI - use toolbar-mac.py (floating window) instead.
#
# Orientation follows the panel shape: wide panel = horizontal toolbars, tall panel (docked
# left/right) = vertical toolbars wrapped in columns.
#
# Re-running the script re-uses the already registered panel (FontLab can not unregister a
# panel) and rebuilds its content with the current code, no restart needed.

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import re
import ctypes
from platform import system

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont
from typerig.proxy.fl.gui.dialogs import TRLayerSelectNEW

import Toolbar

# - Init --------------------------
tool_version = '2.0'
tool_name = 'TypeRig Controller'
ignore_toolbar = '__'

panel_id = 7210 # Must be unique among FontLab panels
panel_title = 'TypeRig'
panel_margin = 4
panel_header = 19 # Height of FontLab's panel header
register_symbol = '_ZN10MainWindow19registerCustomPanelEP12YPanelWidget'

TRToolFont = getTRIconFont()

# -- Global parameters
pMode = 0
pLayers = (True, False, False, False)

# -- Native panel helpers -----------------
def get_pointer(qt_object):
	'''PythonQt wrappers print their C++ address: Class(0x7f..., name="...")'''
	return int(re.search(r'\(0x([0-9a-f]+)', repr(qt_object)).group(1), 16)

def register_native_panel(main_window, panel):
	'''Register panel with FontLab (adds it to Window > Panels > Custom Panels)'''
	register = getattr(ctypes.CDLL(None), register_symbol)
	register.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
	register.restype = None
	register(get_pointer(main_window), get_pointer(panel))

def find_panel_action(main_window):
	command_id = 'Window.Panels.Custom.' + panel_title
	for action in main_window.findChildren(QtGui.QAction):
		if action.property('fontlab.commandId') == command_id:
			return action

def find_ancestor(widget, class_name):
	while widget is not None and type(widget).__name__ != class_name:
		widget = widget.parent()
	return widget

def panel_alive(panel):
	try:
		panel.objectName
		return True
	except Exception:
		return False

# -- Main Widget --------------------------
class TRToolbarController(QtGui.QToolBar):
	def __init__(self, *args, **kwargs):
		super(TRToolbarController, self).__init__(*args, **kwargs)

		# - Init
		self.setWindowTitle("{} : {}".format(tool_name, tool_version))
		self.layers_selected = []

		# - Dialogs
		self.dlg_layer = TRLayerSelectNEW(self, pMode)
		self.dlg_layer.hide()

		# - Actions and groups
		self.grp_layers = QtGui.QActionGroup(self)
		self.grp_glyphs = QtGui.QActionGroup(self)

		self.chk_ActiveLayer = QtGui.QAction("layer_active", self.grp_layers)
		self.addAction(self.chk_ActiveLayer)
		self.chk_ActiveLayer.setToolTip("Active layer")

		self.chk_Masters = QtGui.QAction("layer_master", self.grp_layers)
		self.addAction(self.chk_Masters)
		self.chk_Masters.setToolTip("Master layers")

		self.chk_Selected = QtGui.QAction("select_option", self.grp_layers)
		self.addAction(self.chk_Selected)
		self.chk_Selected.setToolTip("Select layers")

		self.chk_glyph = QtGui.QAction("glyph_active", self.grp_glyphs)
		self.addAction(self.chk_glyph)
		self.chk_glyph.setToolTip("Active Glyph")

		self.chk_window = QtGui.QAction("select_window", self.grp_glyphs)
		self.addAction(self.chk_window)
		self.chk_window.setToolTip("Glyph window")

		self.chk_selection = QtGui.QAction("select_glyph", self.grp_glyphs)
		self.addAction(self.chk_selection)
		self.chk_selection.setToolTip("Font window selection")

		for action in (self.chk_ActiveLayer, self.chk_Masters, self.chk_Selected, self.chk_glyph, self.chk_window, self.chk_selection):
			action.setFont(TRToolFont)
			action.setCheckable(True)

		self.chk_Masters.setChecked(True)
		self.chk_glyph.setChecked(True)

		self.chk_ActiveLayer.triggered.connect(self.layers_refresh)
		self.chk_Masters.triggered.connect(self.layers_refresh)
		self.chk_Selected.triggered.connect(self.layers_refresh)

		self.chk_glyph.triggered.connect(self.mode_refresh)
		self.chk_window.triggered.connect(self.mode_refresh)
		self.chk_selection.triggered.connect(self.mode_refresh)

		self.layers_refresh()

	# - Procedures -----------------------------------
	def mode_refresh(self):
		global pMode

		if self.chk_glyph.isChecked(): pMode = 0
		if self.chk_window.isChecked(): pMode = 1
		if self.chk_selection.isChecked(): pMode = 2

		self.dlg_layer.table_populate(pMode)

		for toolbar_name in Toolbar.modules:
			exec('Toolbar.{}.pMode = {}'.format(toolbar_name, pMode))

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()
		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)

		for toolbar_name in Toolbar.modules:
			exec('Toolbar.{}.pLayers = {}'.format(toolbar_name, pLayers))

class TRToolbarScroll(QtGui.QScrollArea):
	'''Scroll area that flows the toolbar BUTTONS (not whole toolbars) as rows when the panel is wide
	(docked top/bottom or floating) or as columns when it is tall (docked left/right).

	Layout rules that avoid flicker:
	- Sizes are taken from maximumViewportSize() (ignores scrollbars) and room for a scrollbar is
	  reserved explicitly, so a scrollbar appearing can not trigger another layout pass.
	- Orientation uses hysteresis, so a panel near square does not flip back and forth.
	- A new size is applied only after it stayed the same for a few ticks (dragging/docking in FontLab
	  passes through many transient sizes).
	'''
	margin = 4
	gap = 2
	group_gap = 10 # Extra gap in front of the first button of every toolbar
	tick = 40 # ms
	settle_ticks = 2

	def __init__(self, *args, **kwargs):
		super(TRToolbarScroll, self).__init__(*args, **kwargs)
		self.setFrameShape(QtGui.QFrame.NoFrame)
		self.setWidgetResizable(False)
		self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		# The size of the panel is decided by FontLab / the user, never by the content of the scroll area
		self.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)

		self.page = None
		self.buttons = []
		self.vertical = False
		self.fitting = False
		self.seen_size = None
		self.applied_size = None
		self.stable = 0

		self.timer = QtCore.QTimer(self)
		self.timer.setInterval(self.tick)
		self.timer.timeout.connect(self.watch_size)
		self.timer.start()

	def set_page(self, page, buttons):
		self.page = page
		self.buttons = buttons
		self.setWidget(page) # Replaces (and deletes) the previous page
		self.applied_size = None
		self.fit()

	# - Layout --------------------------------
	def flow(self, limit, vertical, apply):
		'''Flow the buttons along one axis wrapping at <limit> (width for rows, height for columns).
		Returns the size of the content including margins.'''
		margin, gap = self.margin, self.gap
		pos, across, line, used = 0, 0, 0, 0

		for button in self.buttons:
			size = button.sizeHint
			size_along, size_across = (size.height(), size.width()) if vertical else (size.width(), size.height())
			extra = self.group_gap if (pos > 0 and button.property('trGroupStart')) else 0
			start = pos + gap + extra if pos > 0 else 0

			if pos > 0 and start + size_along > limit:
				across += line + gap
				line, start = 0, 0

			if apply:
				button.resize(size)
				button.move(margin + across, margin + start) if vertical else button.move(margin + start, margin + across)

			pos = start + size_along
			line = max(line, size_across)
			used = max(used, pos)

		along_total, across_total = used + 2 * margin, across + line + 2 * margin
		return (across_total, along_total) if vertical else (along_total, across_total)

	def content_height(self, width):
		'''Height needed by a horizontal layout at <width> (used to size a newly opened panel)'''
		return self.flow(width - 2 * self.margin, False, False)[1]

	def fit(self):
		if self.page is None or self.fitting: return
		self.fitting = True
		self.page.setUpdatesEnabled(False)

		try:
			view = self.maximumViewportSize() # Size WITHOUT scrollbars
			view_w, view_h = view.width(), view.height()
			if view_w < 1 or view_h < 1: return

			# Hysteresis: tall -> wide needs clearly wide, wide -> tall needs clearly tall
			self.vertical = not (view_w > view_h * 1.25) if self.vertical else (view_w < view_h * 0.8)
			m2 = 2 * self.margin

			if not self.vertical:
				limit = view_w - m2
				width, height = self.flow(limit, False, False)
				if height > view_h: # Vertical scrollbar needed: reserve its width
					limit = view_w - self.verticalScrollBar().sizeHint.width() - m2
				self.flow(limit, False, True)
				width, height = self.flow(limit, False, False)
				self.page.resize(max(limit + m2, 1), max(height, 1))

			else:
				limit = view_h - m2
				width, height = self.flow(limit, True, False)
				if width > view_w: # Horizontal scrollbar needed: reserve its height
					limit = view_h - self.horizontalScrollBar().sizeHint.height() - m2
				self.flow(limit, True, True)
				width, height = self.flow(limit, True, False)
				self.page.resize(max(width, 1), max(limit + m2, 1))

			self.applied_size = (view_w, view_h)

		finally:
			self.page.setUpdatesEnabled(True)
			self.fitting = False

	def watch_size(self):
		# Virtual overrides (resizeEvent/event) are not callable through super() in PythonQt: poll instead
		view = self.maximumViewportSize()
		size = (view.width(), view.height())

		if size != self.seen_size:
			self.seen_size = size
			self.stable = 0

		elif size != self.applied_size:
			self.stable += 1
			if self.stable >= self.settle_ticks: self.fit()

def action_button(page, action, group_start):
	'''Button that mirrors a toolbar action (icon font, checked state, tooltip, enabled state)'''
	button = QtGui.QToolButton(page)
	button.setDefaultAction(action)
	button.setAutoRaise(True)
	button.setFocusPolicy(QtCore.Qt.NoFocus)
	button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
	button.setFont(action.font)
	button.setProperty('trGroupStart', group_start)
	return button

def build_toolbar_page():
	'''Controller + all toolbars. The QToolBars stay hidden and only own the actions; their actions are
	shown as individual buttons so the panel can reflow them freely. Returns (page, refs, buttons)'''
	page = QtGui.QWidget()
	refs, buttons = [], []

	toolbars = [TRToolbarController()]

	# -- Import external toolbars
	# --- Load all toolbars from Toolbar directory as modules. Check __init__.py
	# --- <dirName>.modules tabs/modules manifest in list format
	for toolbar_name in Toolbar.modules:
		if ignore_toolbar not in toolbar_name:
			toolbars.append(eval('Toolbar.{}.TRExternalToolBar()'.format(toolbar_name)))

	for toolbar in toolbars:
		toolbar.setParent(page)
		toolbar.hide()
		refs.append(toolbar)

		first = True
		for action in toolbar.actions():
			if action.isSeparator(): continue
			buttons.append(action_button(page, action, first))
			first = False

	return page, refs, buttons

def create_native_panel(main_window):
	'''Create, fill and register the panel. Returns state dict'''
	panel = fl6.CreatePanel(panel_id, panel_title)
	panel.setWindowTitle(panel_title) # Must be set BEFORE registering - used for the menu entry
	panel.setObjectName('TR_TOOLBAR_DOCK_PANEL')

	panel_layout = QtGui.QVBoxLayout(panel)
	panel_layout.setContentsMargins(0, 0, 0, 0)

	scroll = TRToolbarScroll()
	panel_layout.addWidget(scroll)

	register_native_panel(main_window, panel)
	return {'panel': panel, 'scroll': scroll, 'layout': panel_layout, 'refs': []}

def renew_scroll(state):
	'''Swap the scroll area for a fresh instance of the current class. A registered panel can not be
	unregistered, so an older run (or older version of this script) may have left stale code in it.'''
	old = state.get('scroll')
	if old is not None:
		# Do NOT destroy it: its timer is connected to a bound method of the scroll area itself and
		# PythonQt double-deletes the widget during destruction (crashes FontLab). Park it hidden.
		old.timer.stop()
		state['layout'].removeWidget(old)
		old.hide()
		Toolbar._dock_graveyard = getattr(Toolbar, '_dock_graveyard', []) + [old]

	scroll = TRToolbarScroll()
	state['layout'].addWidget(scroll)
	state['scroll'] = scroll

def size_and_place(state):
	'''FontLab opens custom panels at minimum size (50x69). Resize the YPanel itself (not the YDock)'''
	panel, scroll = state['panel'], state['scroll']
	yp_panel = find_ancestor(panel, 'YPanel')
	yp_dock = find_ancestor(panel, 'YDock')
	if yp_panel is None or yp_dock is None: return

	screen = QtGui.QApplication.desktop().availableGeometry()
	width = min(screen.width() - 120, 1700)
	height = scroll.content_height(width) + panel_header

	yp_panel.resize(width, height)
	yp_dock.setGeometry(screen.x() + 60, screen.y() + 60, width, height)

# - RUN ------------------------------
if system() != 'Darwin':
	print('{} {}: This is the macOS variant. Use typerig-toolbar.py on this platform.'.format(tool_name, tool_version))

else:
	main_window = fl6.MainWindow()
	state = getattr(Toolbar, '_dock_state', None)
	is_new = False

	if state is None or not panel_alive(state['panel']):
		try:
			state = create_native_panel(main_window)
			Toolbar._dock_state = state
			is_new = True
		except AttributeError:
			state = None
			print('{} {}: FontLab symbol {} not found (different FontLab build?). Use toolbar-mac.py instead.'.format(tool_name, tool_version, register_symbol))

	if state is not None:
		# -- (Re)build toolbar content
		if not is_new: renew_scroll(state)
		page, refs, buttons = build_toolbar_page()
		state['scroll'].set_page(page, buttons)
		state['refs'] = refs

		# -- Let FontLab open the panel. Its slot only handles senders named 'QAction'
		action = find_panel_action(main_window)
		if action is not None:
			action.setObjectName('QAction')
			action.setText(panel_title)

			if is_new or not state['panel'].isVisible():
				action.trigger()
				QtGui.QApplication.processEvents()
				size_and_place(state)
		else:
			print('{} {}: Panel registered but menu action not found.'.format(tool_name, tool_version))
