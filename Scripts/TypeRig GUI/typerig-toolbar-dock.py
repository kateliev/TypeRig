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
from typerig.proxy.fl.gui.widgets import getTRIconFont, TRFlowLayout
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
	'''Scroll area that lays the toolbars out horizontally (wide panel: docked top/bottom or floating)
	or vertically (tall panel: docked left/right) following the shape of the panel.'''
	def __init__(self, *args, **kwargs):
		super(TRToolbarScroll, self).__init__(*args, **kwargs)
		self.setFrameShape(QtGui.QFrame.NoFrame)
		self.setWidgetResizable(False)
		# The size of the panel is decided by FontLab / the user, never by the content of the scroll area
		self.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
		self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.page_layout = None
		self.bars = []
		self.fitting = False
		self.last_size = None

		self.timer = QtCore.QTimer(self)
		self.timer.setInterval(120)
		self.timer.timeout.connect(self.watch_size)
		self.timer.start()

	def set_page(self, page, page_layout, bars):
		self.page_layout = page_layout
		self.bars = bars
		self.setWidget(page) # Replaces (and deletes) the previous page
		self.fit()

	def is_vertical(self):
		view = self.viewport().size
		return view.width() < view.height()

	def fit(self):
		if self.page_layout is None or self.fitting: return
		self.fitting = True

		try:
			layout, page = self.page_layout, self.widget()
			margins = layout.contentsMargins()
			view = self.viewport().size
			orientation = QtCore.Qt.Vertical if self.is_vertical() else QtCore.Qt.Horizontal

			if layout.orientation != orientation:
				layout.orientation = orientation
				for bar in self.bars: bar.setOrientation(orientation)
				layout.invalidate()

			if orientation == QtCore.Qt.Horizontal:
				width = view.width()
				height = layout.heightForWidth(width - margins.left() - margins.right()) + margins.top() + margins.bottom()

				if height > view.height(): # Vertical scrollbar will appear
					width -= self.verticalScrollBar().width
					height = layout.heightForWidth(width - margins.left() - margins.right()) + margins.top() + margins.bottom()

				page.resize(max(width, 1), max(height, 1))

			else:
				# TRFlowLayout.widthForHeight returns wrong values in vertical mode: measure the placed items instead
				height = view.height()
				layout.setGeometry(QtCore.QRect(margins.left(), margins.top(), 1, height - margins.top() - margins.bottom()))
				width = max([layout.itemAt(i).geometry().right() for i in range(layout.count())] + [0]) + 1 + margins.right()
				page.resize(max(width, 1), max(height, 1))

		finally:
			self.fitting = False

	def watch_size(self):
		# Virtual overrides (resizeEvent/event) are not callable through super() in PythonQt: poll the size instead
		size = self.viewport().size
		key = (size.width(), size.height())
		if key != self.last_size:
			self.last_size = key
			self.fit()

def build_toolbar_page():
	'''All toolbars on one flowing page. Returns (page, references to keep alive); refs[0] is the layout'''
	page = QtGui.QWidget()
	page_layout = TRFlowLayout(spacing=4)
	page_layout.setContentsMargins(6, 4, 6, 4)
	page.setLayout(page_layout)

	toolbar_control = TRToolbarController()
	toolbar_control.setParent(page)
	page_layout.addWidget(toolbar_control)
	refs = [page_layout, toolbar_control]

	# -- Import external toolbars
	# --- Load all toolbars from Toolbar directory as modules. Check __init__.py
	# --- <dirName>.modules tabs/modules manifest in list format
	for toolbar_name in Toolbar.modules:
		if ignore_toolbar not in toolbar_name:
			new_toolbar = eval('Toolbar.{}.TRExternalToolBar()'.format(toolbar_name))
			new_toolbar.setParent(page)
			page_layout.addWidget(new_toolbar)
			refs.append(new_toolbar)

	return page, refs

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
	panel, page = state['panel'], state['scroll'].widget()
	state['scroll'].fit() # Start horizontal: measure the wide layout
	yp_panel = find_ancestor(panel, 'YPanel')
	yp_dock = find_ancestor(panel, 'YDock')
	if yp_panel is None or yp_dock is None: return

	screen = QtGui.QApplication.desktop().availableGeometry()
	width = min(screen.width() - 120, 1700)
	margins = page.layout().contentsMargins()
	height = page.layout().heightForWidth(width - margins.left() - margins.right()) + margins.top() + margins.bottom() + panel_header

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
		page, refs = build_toolbar_page()
		state['scroll'].set_page(page, refs[0], [r for r in refs[1:] if isinstance(r, QtGui.QToolBar)])
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
