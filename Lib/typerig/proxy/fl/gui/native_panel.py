# MODULE: TypeRig / Proxy / FontLab / GUI / Native Panel
# NOTE	: A reflowing widget panel that lives in a *native FontLab panel* (YPanelWidget):
#	  drag & dock on every edge, tabbing with other panels, header menu, Window menu.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# Everything here is distilled from Docs/Proxy/Documents/FL-native-panels.md - read it first.
#
# Usage:
#	def build(panel):
#		page = QtGui.QWidget()
#		buttons = [...]  # child widgets of <page>; property 'trGroupStart' / 'trSectionStart' = extra gap
#		return page, buttons, refs  # refs: objects that must stay alive (QActions, QToolBars...)
#
#	TRNativePanel(7210, 'TypeRig Toolbar', build).open()
#
# Platform strategy (registration is the only platform specific part):
#	macOS   : MainWindow::registerCustomPanel through ctypes (Itanium symbol). FontLab 8 + 9.
#	Windows : the MSVC symbol is looked up in the main module; ONLY if it resolves it is used (UNVERIFIED -
#	          see FL-native-panels.md, section 11). If it does not resolve, the same content is docked
#	          as a regular QToolBar in app.main (explicit fallback strategy).
#	other   : clean no-op with one message.

# - Dependencies --------------------------
from __future__ import absolute_import, print_function
import re
import ctypes
from platform import system

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui

# - Init ----------------------------------
__version__ = '1.0'

MAC_SYMBOL = '_ZN10MainWindow19registerCustomPanelEP12YPanelWidget'
WIN_SYMBOL = '?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@@Z' # Expected MSVC name, UNVERIFIED
PANEL_HEADER = 19 # Height of FontLab's panel header

# Long lived state. FontLab resets script namespaces between runs, but modules imported from the library
# stay in sys.modules, so everything that must survive a re-run lives here.
_STATE = {} # panel_id -> state dict
_GRAVEYARD = [] # Retired widgets (never destroyed, see FL-native-panels.md section 8)

# - Helpers -------------------------------
def get_pointer(qt_object):
	'''PythonQt wrappers print their C++ address: Class(0x7f..., name="...")'''
	return int(re.search(r'\(0x([0-9a-f]+)', repr(qt_object)).group(1), 16)

def find_ancestor(widget, class_name):
	while widget is not None and type(widget).__name__ != class_name:
		widget = widget.parent()
	return widget

def is_alive(widget):
	try:
		widget.objectName
		return True
	except Exception:
		return False

def resolve_register():
	'''Return a callable(main_window_ptr, panel_ptr) that registers a custom panel, or None when this
	platform / FontLab build does not offer it. Never raises, prints one line on failure.'''
	platform_name = system()

	try:
		if platform_name == 'Darwin':
			register = getattr(ctypes.CDLL(None), MAC_SYMBOL)
			register.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
			register.restype = None
			return register

		if platform_name == 'Windows':
			kernel = ctypes.WinDLL('kernel32')
			kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
			kernel.GetModuleHandleW.restype = ctypes.c_void_p
			kernel.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
			kernel.GetProcAddress.restype = ctypes.c_void_p
			address = kernel.GetProcAddress(kernel.GetModuleHandleW(None), WIN_SYMBOL.encode('ascii'))

			if address:
				return ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(address) # x64: one calling convention

			print('TypeRig native panel: symbol {} is not exported by this FontLab build.'.format(WIN_SYMBOL))
			return None

	except (AttributeError, OSError) as error:
		print('TypeRig native panel: registerCustomPanel not available ({}).'.format(error))
		return None

	print('TypeRig native panel: platform {} is not supported.'.format(platform_name))
	return None

def park(widget):
	'''Retire a widget WITHOUT destroying it: its QTimer is connected to a bound method of the widget itself and
	PythonQt would double-delete it (FontLab crash in QWidget::~QWidget).'''
	if widget is None or not is_alive(widget): return
	for timer in widget.findChildren(QtCore.QTimer):
		timer.stop()
	widget.hide()
	_GRAVEYARD.append(widget)

# - Scroll / flow area ----------------------
class TRToolbarScroll(QtGui.QScrollArea):
	'''Scroll area that flows its widgets as rows when the panel is wide (docked top/bottom or floating) or as
	columns when it is tall (docked left/right).

	Layout rules that avoid flicker:
	- Sizes are taken from maximumViewportSize() (ignores scrollbars) and room for a scrollbar is
	  reserved explicitly, so a scrollbar appearing can not trigger another layout pass.
	- Orientation uses hysteresis, so a panel near square does not flip back and forth.
	- A new size is applied only after it stayed the same for a few ticks (dragging/docking in FontLab
	  passes through many transient sizes).
	'''
	margin = 4
	gap = 2
	group_gap = 10 # Extra gap in front of the first widget of a group (property 'trGroupStart')
	section_gap = 18 # Extra gap in front of the first widget of a section (property 'trSectionStart')
	tick = 40 # ms
	settle_ticks = 2

	def __init__(self, *args, **kwargs):
		super(TRToolbarScroll, self).__init__(*args, **kwargs)
		self.setObjectName('TR_NATIVE_SCROLL')
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
		self.filled_for = None
		self.stable = 0
		self.fit_count = 0 # Number of layout passes (diagnostics)

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
		'''Flow the widgets along one axis wrapping at <limit> (width for rows, height for columns).
		Returns the size of the content including margins.'''
		margin, gap = self.margin, self.gap
		pos, across, line, used = 0, 0, 0, 0

		for button in self.buttons:
			size = button.sizeHint
			size_along, size_across = (size.height(), size.width()) if vertical else (size.width(), size.height())

			extra = 0
			if pos > 0:
				if button.property('trSectionStart'): extra = self.section_gap
				elif button.property('trGroupStart'): extra = self.group_gap
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

	def dock_context(self):
		'''Returns (YDock, YPanel, number of panels in the dock). FontLab 8 keeps a docked panel at its old
		height inside a full height dock, so the dock tells more about where the panel was docked.'''
		widget, yp_panel, yp_dock = self, None, None
		while widget is not None:
			if type(widget).__name__ == 'YPanel' and yp_panel is None: yp_panel = widget
			if type(widget).__name__ == 'YDock': yp_dock = widget; break
			widget = widget.parent()

		count = len([c for c in yp_dock.children() if type(c).__name__ == 'YPanel']) if yp_dock is not None else 0
		return yp_dock, yp_panel, count

	def state_key(self):
		view = self.maximumViewportSize()
		dock = self.dock_context()[0]
		dock_w, dock_h = (dock.geometry.width(), dock.geometry.height()) if dock is not None else (0, 0)
		return (view.width(), view.height(), dock_w, dock_h)

	def fill_dock(self, dock, panel):
		'''Stretch a lone panel to the full height of its (tall) dock'''
		if dock is None or panel is None: return
		dock_h, panel_h = dock.geometry.height(), panel.geometry.height()
		if dock_h - panel_h > 60:
			panel.resize(panel.geometry.width(), dock_h - panel.geometry.y() - 6)

	def fit(self):
		if self.page is None or self.fitting: return
		self.fitting = True
		self.page.setUpdatesEnabled(False)

		try:
			view = self.maximumViewportSize() # Size WITHOUT scrollbars
			view_w, view_h = view.width(), view.height()
			if view_w < 1 or view_h < 1: return
			self.fit_count += 1

			# Orientation follows the larger of panel and dock: a docked dock is tall even if the panel is not.
			dock, panel, panel_count = self.dock_context()
			shape_w = max(view_w, dock.geometry.width() if dock is not None else 0)
			shape_h = max(view_h, dock.geometry.height() if dock is not None else 0)

			# Hysteresis: tall -> wide needs clearly wide, wide -> tall needs clearly tall
			was_vertical = self.vertical
			self.vertical = not (shape_w > shape_h * 1.25) if self.vertical else (shape_w < shape_h * 0.8)

			# Vertical dock with a short, lone panel (FontLab 8): let the panel use the whole dock height
			if self.vertical and panel_count == 1 and (not was_vertical or self.filled_for != (shape_w, shape_h)):
				self.filled_for = (shape_w, shape_h)
				self.fill_dock(dock, panel)
				view = self.maximumViewportSize()
				view_w, view_h = view.width(), view.height()

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

			self.applied_size = self.state_key()

		finally:
			self.page.setUpdatesEnabled(True)
			self.fitting = False

	def watch_size(self):
		# Virtual overrides (resizeEvent/event) are not callable through super() in PythonQt: poll instead
		size = self.state_key()

		if size != self.seen_size:
			self.seen_size = size
			self.stable = 0

		elif size != self.applied_size:
			self.stable += 1
			if self.stable >= self.settle_ticks: self.fit()

# - Panel ---------------------------------
class TRNativePanel(object):
	'''A native FontLab panel (or, on Windows without the symbol, a docked QToolBar) showing reflowing widgets.

	content_builder(panel) -> (page, buttons, refs)
		page	: QWidget that owns the widgets
		buttons	: widgets to flow, in order; property 'trGroupStart' / 'trSectionStart' adds a gap before it
		refs	: objects to keep alive (QActions, hidden QToolBars, dialogs...)
	'''
	def __init__(self, panel_id, title, content_builder, object_name='TR_TOOLBAR_PANEL', legacy_names=('TR_TOOLBAR_DOCK_PANEL',)):
		self.panel_id = panel_id
		self.title = title
		self.content_builder = content_builder
		self.object_name = object_name
		self.legacy_names = tuple(legacy_names)
		self.main_window = fl6.MainWindow()
		self.mode = None # 'native' | 'toolbar' (set by open())

	# - State ------------------------------
	@property
	def state(self):
		return _STATE.get(self.panel_id)

	@property
	def scroll(self):
		return self.state['scroll'] if self.state else None

	@property
	def panel(self):
		return self.state['panel'] if self.state else None

	# - Action lookup ----------------------
	def find_action(self):
		'''Find the Window > Panels > Custom Panels action created by registerCustomPanel.
		FontLab 9 tags it with a "fontlab.commandId" property, FontLab 8 does not. Both store the panel id
		as action data, so that is the common key.'''
		command_id = 'Window.Panels.Custom.' + self.title

		def scan():
			by_data = None
			for action in self.main_window.findChildren(QtGui.QAction):
				if action.property('fontlab.commandId') == command_id:
					return action
				if by_data is None and action.data() == self.panel_id:
					by_data = action
			return by_data

		action = scan()
		if action is not None: return action

		# The menu may be populated lazily: let FontLab build it by showing the menus for a moment
		try:
			menu = [a for a in self.main_window.menuBar().actions() if a.text.replace('&', '') == 'Window'][0].menu()
			for _ in range(3):
				menu.popup(QtCore.QPoint(-4000, -4000))
				QtGui.QApplication.processEvents()
				menu.hide()
				for sub in [a.menu() for a in menu.actions() if a.menu() is not None]:
					sub.popup(QtCore.QPoint(-4000, -4000))
					QtGui.QApplication.processEvents()
					sub.hide()
		except Exception:
			pass

		return scan()

	def describe_actions(self):
		'''Diagnostics for a failed lookup'''
		candidates = [a for a in self.main_window.findChildren(QtGui.QAction) if a.data() == self.panel_id]
		custom = self.main_window.findChild(QtGui.QMenu, 'menuCustomPanels')
		return 'actions with data={}: {} | menuCustomPanels: {}'.format(
			self.panel_id, [(a.text, a.objectName) for a in candidates],
			[(a.text, a.data()) for a in custom.actions()] if custom is not None else 'not found')

	# - Create / adopt ---------------------
	def create_native(self, register):
		panel = fl6.CreatePanel(self.panel_id, self.title)
		panel.setWindowTitle(self.title) # Must be set BEFORE registering - used for the menu entry
		panel.setObjectName(self.object_name)

		layout = QtGui.QVBoxLayout(panel)
		layout.setContentsMargins(0, 0, 0, 0)

		register(get_pointer(self.main_window), get_pointer(panel))
		return {'mode': 'native', 'panel': panel, 'layout': layout, 'scroll': None, 'refs': [], 'new': True}

	def adopt_native(self):
		'''FontLab can not unregister a panel. When the registry is gone (module purged, an older script ran
		before) find the already registered panel and reuse it.'''
		names = (self.object_name,) + self.legacy_names

		for widget in QtGui.QApplication.allWidgets():
			if type(widget).__name__ == 'YPanelWidget' and widget.objectName in names and is_alive(widget):
				layout = widget.layout()
				if layout is None: continue
				for old in widget.findChildren(QtGui.QScrollArea): park(old) # Stale code from an older run
				widget.setWindowTitle(self.title)
				return {'mode': 'native', 'panel': widget, 'layout': layout, 'scroll': None, 'refs': [], 'new': False}

		return None

	def create_toolbar(self):
		'''Windows fallback: same content in a regular QToolBar docked in app.main'''
		toolbar = QtGui.QToolBar(self.title, self.main_window)
		toolbar.setObjectName(self.object_name)
		toolbar.setAllowedAreas(QtCore.Qt.AllToolBarAreas)
		self.main_window.addToolBar(toolbar)
		return {'mode': 'toolbar', 'panel': toolbar, 'layout': None, 'scroll': None, 'refs': [], 'new': True}

	# - Public API -------------------------
	def open(self):
		'''Create (or reuse) the panel, (re)build its content and show it. Returns True when a panel is showing.'''
		state = self.state
		if state is not None and not is_alive(state['panel']):
			state = None

		if state is None:
			state = self.adopt_native() if system() != 'Windows' else None

			if state is None:
				register = resolve_register()

				if register is not None:
					state = self.create_native(register)
				elif system() == 'Windows':
					print('TypeRig native panel: falling back to a docked QToolBar (not a native FontLab panel).')
					state = self.create_toolbar()
				else:
					print('TypeRig native panel: not opened - no panel support on this FontLab build. FontLab is untouched.')
					return False

			_STATE[self.panel_id] = state

		self.mode = state['mode']
		is_new = state.pop('new', False)
		self.rebuild()

		if self.mode == 'toolbar':
			state['panel'].show()
			return True

		# -- Let FontLab open the panel. Its slot only handles senders named 'QAction'
		action = self.find_action()

		if action is None:
			print('TypeRig native panel: registered, but the menu action was not found. {}'.format(self.describe_actions()))
			return False

		action.setObjectName('QAction')
		action.setText(self.title)

		if is_new or not state['panel'].isVisible():
			action.trigger()
			QtGui.QApplication.processEvents()
			self.size_and_place()

		return True

	def rebuild(self):
		'''Swap the content for a fresh scroll area + a new page from content_builder. The old scroll area is
		parked, not destroyed (a registered panel can not be unregistered and may hold stale code).'''
		state = self.state
		if state is None: return

		park(state.get('scroll'))
		if state['layout'] is not None and state.get('scroll') is not None:
			state['layout'].removeWidget(state['scroll'])

		scroll = TRToolbarScroll()

		if state['mode'] == 'native':
			state['layout'].addWidget(scroll)
		else:
			scroll.setMinimumSize(320, 44)
			for action in state['panel'].actions(): state['panel'].removeAction(action)
			state['panel'].addWidget(scroll)

		state['scroll'] = scroll
		page, buttons, refs = self.content_builder(self)
		scroll.set_page(page, buttons)
		state['refs'] = refs

	def size_and_place(self):
		'''FontLab opens custom panels at minimum size (50x69). Resize the YPanel itself (not the YDock)'''
		state = self.state
		yp_panel = find_ancestor(state['panel'], 'YPanel')
		yp_dock = find_ancestor(state['panel'], 'YDock')
		if yp_panel is None or yp_dock is None: return

		screen = QtGui.QApplication.desktop().availableGeometry()
		width = min(screen.width() - 120, 1700)
		height = state['scroll'].content_height(width) + PANEL_HEADER

		yp_panel.resize(width, height)
		yp_dock.setGeometry(screen.x() + 60, screen.y() + 60, width, height)
