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
#		buttons = [...]  # child widgets of <page>, flowed one after the other in this order
#		return page, buttons, refs  # refs: objects that must stay alive (QActions, QToolBars...)
#
#	TRNativePanel(7210, 'TypeRig Toolbar', build).open()
#
# Platform strategy (registration is the only platform specific part):
#	macOS   : MainWindow::registerCustomPanel through ctypes (Itanium symbol). FontLab 8 + 9.
#	Windows : FontLab.exe exports NO symbols (verified on FontLab 9 / Windows: its export directory is
#	          empty, only the Qt DLLs export anything), so registerCustomPanel can not be called and a
#	          native FontLab panel is impossible. The MSVC symbol is still looked up - should a future
#	          build export it, the native path is taken. Otherwise the same content goes into a real
#	          QDockWidget on app.main: drag & dock on all four edges, float, tab with other QDockWidgets,
#	          resize by the dock separator - everything a native panel does except tabbing with FontLab's
#	          own Y panels.
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
__version__ = '1.2'

MAC_SYMBOL = '_ZN10MainWindow19registerCustomPanelEP12YPanelWidget'
WIN_SYMBOL = '?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@@Z' # Expected MSVC name, never exported so far
PANEL_HEADER = 19 # Height of FontLab's panel header

# Qt dock areas (plain ints: PythonQt hands enums over as numbers)
DOCK_LEFT, DOCK_RIGHT, DOCK_TOP, DOCK_BOTTOM = 1, 2, 4, 8

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

			return None # Expected on Windows: FontLab.exe exports nothing. The caller says so once.

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
	- <host> (the TRNativePanel) may dictate the orientation: a QDockWidget knows the dock area it sits
	  in, which beats guessing from geometry. Without a host hint the shape decides, with hysteresis, so
	  a panel near square does not flip back and forth.
	- A new size is applied only after it stayed the same for a few ticks (dragging/docking in FontLab
	  passes through many transient sizes).
	'''
	margin = 4
	gap = 2
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

		self.host = None # TRNativePanel: orientation hint + dock sizing
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

			start = pos + gap if pos > 0 else 0

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
		'''Height needed by a horizontal (row) layout at <width> (used to size a newly opened panel)'''
		return self.flow(width - 2 * self.margin, False, False)[1]

	def content_width(self, height):
		'''Width needed by a vertical (column) layout at <height> (used to size a left / right dock)'''
		return self.flow(height - 2 * self.margin, True, False)[0]

	def orientation_hint(self):
		'''True = columns, False = rows, None = decide from the shape'''
		return self.host.orientation_hint() if self.host is not None else None

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
		return (view.width(), view.height(), dock_w, dock_h, self.orientation_hint())

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

			hint = self.orientation_hint()
			was_vertical = self.vertical

			if hint is not None:
				# The host knows where it is docked (QDockWidget area): no guessing
				self.vertical = hint
			else:
				# Hysteresis: tall -> wide needs clearly wide, wide -> tall needs clearly tall
				self.vertical = not (shape_w > shape_h * 1.25) if self.vertical else (shape_w < shape_h * 0.8)

			# Vertical dock with a short, lone panel (FontLab 8): let the panel use the whole dock height
			if hint is None and self.vertical and panel_count == 1 and (not was_vertical or self.filled_for != (shape_w, shape_h)):
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

		if self.host is not None:
			self.host.after_fit(self) # Dock hosts give themselves a cross size that fits the content

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
	'''A native FontLab panel (or, on Windows, a QDockWidget on the main window) showing reflowing widgets.

	content_builder(panel) -> (page, buttons, refs)
		page	: QWidget that owns the widgets
		buttons	: widgets to flow, in order, one after the other (no separators)
		refs	: objects to keep alive (QActions, hidden QToolBars, dialogs...)
	'''
	def __init__(self, panel_id, title, content_builder, object_name='TR_TOOLBAR_PANEL', legacy_names=('TR_TOOLBAR_DOCK_PANEL',)):
		self.panel_id = panel_id
		self.title = title
		self.content_builder = content_builder
		self.object_name = object_name
		self.legacy_names = tuple(legacy_names)
		self.main_window = fl6.MainWindow()
		self.mode = None # 'native' | 'dock' (set by open())

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

	# - Dock widget (Windows) --------------
	def create_dock(self):
		'''Windows: the same content in a QDockWidget on app.main - dockable on all four edges, floatable,
		resizable by its dock separator and tabbing with other QDockWidgets.'''
		dock = QtGui.QDockWidget(self.title, self.main_window)
		dock.setObjectName(self.object_name)
		dock.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
		dock.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable | QtGui.QDockWidget.DockWidgetClosable)
		self.main_window.addDockWidget(QtCore.Qt.TopDockWidgetArea, dock)
		return {'mode': 'dock', 'panel': dock, 'layout': None, 'scroll': None, 'refs': [], 'new': True}

	def adopt_dock(self):
		'''Re-use the dock widget of an earlier run (the module may have been purged, keeping the widget)'''
		names = (self.object_name,) + self.legacy_names

		for widget in QtGui.QApplication.allWidgets():
			if not (widget.inherits('QDockWidget') and widget.objectName in names and is_alive(widget)): continue
			if not self.is_mine(widget): continue # Orphaned by an earlier run: let it rot, make a new one

			for old in widget.findChildren(QtGui.QScrollArea): park(old) # Stale code from an older run
			widget.setWindowTitle(self.title)
			return {'mode': 'dock', 'panel': widget, 'layout': None, 'scroll': None, 'refs': [], 'new': False}

		return None

	def is_mine(self, widget):
		'''True when <widget> still belongs to this main window (a floating QDockWidget does too)'''
		parent = widget.parent()
		try:
			return parent is not None and get_pointer(parent) == get_pointer(self.main_window)
		except Exception:
			return False

	def retire_toolbar(self):
		'''TypeRig up to 3.0 docked a QToolBar on Windows (it could not be resized and never reflowed).
		Take it off the main window so the dock widget does not come up underneath it.'''
		names = (self.object_name,) + self.legacy_names

		for widget in QtGui.QApplication.allWidgets():
			if widget.inherits('QToolBar') and widget.objectName in names and is_alive(widget):
				for old in widget.findChildren(QtGui.QScrollArea): park(old)
				self.main_window.removeToolBar(widget)
				park(widget)

	def dock_area(self):
		'''The Qt dock area the panel sits in, or None when it is floating / not a dock widget'''
		state = self.state
		if state is None or state['mode'] != 'dock': return None

		dock = state['panel']
		if not is_alive(dock) or dock.isFloating(): return None

		area = int(self.main_window.dockWidgetArea(dock))
		return area if area in (DOCK_LEFT, DOCK_RIGHT, DOCK_TOP, DOCK_BOTTOM) else None

	def orientation_hint(self):
		'''True = columns (docked left / right), False = rows (docked top / bottom), None = let the shape decide'''
		area = self.dock_area()
		if area is None: return None
		return area in (DOCK_LEFT, DOCK_RIGHT)

	def after_fit(self, scroll):
		'''Called after every layout pass: when the panel has just been docked somewhere else, give the dock
		the cross size its content asks for (height when docked top / bottom, width when left / right).
		Done once per dock area, so a size the user drags afterwards is left alone.'''
		state = self.state
		if state is None or state['mode'] != 'dock': return

		area = self.dock_area()

		if area is None: # Floating: the user owns the size. Fit again when it is docked somewhere.
			state['sized_for'] = None
			return

		if area == state.get('sized_for'): return
		state['sized_for'] = area

		dock = state['panel']
		view = scroll.maximumViewportSize()

		if scroll.vertical:
			want = scroll.content_width(max(view.height(), 1)) + max(dock.geometry.width() - view.width(), 0)
			self.main_window.resizeDocks([dock], [want], QtCore.Qt.Horizontal)
		else:
			want = scroll.content_height(max(view.width(), 1)) + max(dock.geometry.height() - view.height(), 0)
			self.main_window.resizeDocks([dock], [want], QtCore.Qt.Vertical)

	# - Public API -------------------------
	def open(self):
		'''Create (or reuse) the panel, (re)build its content and show it. Returns True when a panel is showing.'''
		on_windows = system() == 'Windows'
		if on_windows: self.retire_toolbar() # Leftover from TypeRig <= 3.0

		state = self.state
		if state is not None and (not is_alive(state['panel']) or state['mode'] == 'toolbar'):
			state = None

		if state is None:
			state = self.adopt_dock() if on_windows else self.adopt_native()

			if state is None:
				register = resolve_register()

				if register is not None:
					state = self.create_native(register)
				elif on_windows:
					print('TypeRig native panel: this FontLab build exports no panel registration - using a QDockWidget on the main window.')
					state = self.create_dock()
				else:
					print('TypeRig native panel: not opened - no panel support on this FontLab build. FontLab is untouched.')
					return False

			_STATE[self.panel_id] = state

		self.mode = state['mode']
		is_new = state.pop('new', False)
		self.rebuild()

		if self.mode == 'dock':
			state['panel'].show()
			QtGui.QApplication.processEvents()

			# The first layout ran on the widget's pre-dock size: lay out again now that the dock has
			# its real width, then let after_fit() give the dock the height that content asks for.
			state['sized_for'] = None
			state['scroll'].fit()
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

		old_scroll = state.get('scroll')
		park(old_scroll)

		if old_scroll is not None:
			old_scroll.host = None
			if state['layout'] is not None:
				state['layout'].removeWidget(old_scroll)
			else:
				old_scroll.setParent(None) # QDockWidget.setWidget() keeps the old widget as a child

		scroll = TRToolbarScroll()
		scroll.host = self

		if state['mode'] == 'native':
			state['layout'].addWidget(scroll)
		else:
			# Small enough that the user can drag the dock down to a single row, big enough that
			# Qt never collapses the dock to nothing
			scroll.setMinimumSize(48, 40)
			state['panel'].setWidget(scroll)

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
