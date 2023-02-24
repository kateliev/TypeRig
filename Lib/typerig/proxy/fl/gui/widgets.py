# MODULE: Typerig / GUI / Widgets
# NOTE	: Assorted Gui Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
from __future__ import absolute_import
from collections import OrderedDict
from math import radians
from random import randint


import os
import fontlab as fl6

from PythonQt import QtCore, QtGui
#from typerig.proxy.fl.gui import QtGui

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init ----------------------------------
__version__ = '0.5.6'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# -- Fonts -------------------------------
def getTRIconFont(font_pixel_size=20):
	font_path = [os.path.dirname(__file__), 'resource' , 'typerig-icons.ttf']
	font_loaded = QtGui.QFontDatabase.addApplicationFont(os.path.join(*font_path))

	TRIconFont = QtGui.QFont()
	TRIconFont.setFamily("TypeRig Icons")
	TRIconFont.setPixelSize(font_pixel_size)

	return TRIconFont

def getTRIconFontPath():
	return os.path.join(os.path.dirname(__file__), 'resource' , 'typerig-icons.ttf')

# -- Colors ------------------------------
# Fontlab Name, Fontlab Value, QtColor Name
fontMarkColors = [
					(u'white', 0, u'white'),
					(u'red', 1, u'red'),
					(u'coral', 16, u'coral'),
					(u'sienna', 20, u'sienna'),
					(u'bisque', 37, u'bisque'),
					(u'gold', 50, u'gold'),
					(u'yellow', 61, u'yellow'),
					(u'yellow green', 79, u'yellowgreen'),
					(u'sulu', 90, u'chartreuse'),
					(u'green', 121, u'green'),
					(u'spring green', 145, u'springgreen'),
					(u'aquamarine', 151, u'aquamarine'),
					(u'turquoise', 174, u'turquoise'),
					(u'cyan', 181, u'cyan'),
					(u'skyblue', 195, u'skyblue'),
					(u'maya blue', 210, u'cornflowerblue'),
					(u'blue', 241, u'blue'),
					(u'heliotrope', 271, u'blueviolet'),
					(u'indigo', 274, u'indigo'),
					(u'magenta', 301, u'magenta'),
					(u'rose', 330, u'hotpink'),
					(u'pink', 350, u'pink'),
					(u'gray', 361, u'lightgray')
					]

# - Functions --------------------------
def getProcessGlyphs(mode=0, font=None, workspace=None):
	'''Returns a list of glyphs for processing in TypeRig gui apps

	Args:
		mode (int): 0 - Current active glyph; 1 - All glyphs in current window; 2 - All selected glyphs; 3 - All glyphs in font
		font (fgFont) - Font file (object)
		workspace (flWorkspace) - Workspace
	
	Returns:
		list(eGlyph)
	'''
	# - Init
	process_glyphs = []
	active_workspace = pWorkspace()
	active_font = pFont(font)
		
	# - Collect process glyphs
	if mode == 0: process_glyphs.append(eGlyph())
	if mode == 1: process_glyphs = [eGlyph(glyph) for glyph in active_workspace.getTextBlockGlyphs()]
	if mode == 2: process_glyphs = active_font.selectedGlyphs(extend=eGlyph) 
	if mode == 3: process_glyphs = active_font.glyphs(extend=eGlyph)
	
	return process_glyphs
	
def FLIcon(icon_path, icon_size):
	new_label = QtGui.QLabel()
	new_label.setPixmap(QtGui.QIcon(icon_path).pixmap(icon_size))
	return new_label

def FLIconButton(button_text, icon_path, icon_size=32, checkable=False):
	new_button = QtGui.QPushButton(button_text)
	new_button.setCheckable(checkable)
	new_button.setStyleSheet(css_fl_button)

	if len(icon_path):
		new_button.setIcon(QtGui.QIcon(icon_path))
		new_button.setIconSize(QtCore.QSize(icon_size,icon_size))
	return new_button

# - Classes -------------------------------
# -- Basics -------------------------------
class CustomPushButton(QtGui.QPushButton):
	def __init__(self, button_text, checkable=False, checked=False, enabled=True, tooltip=None, obj_name=None):
		super(CustomPushButton, self).__init__(button_text)

		self.setCheckable(checkable)
		self.setChecked(checked)
		self.setEnabled(enabled)

		if tooltip is not None:	self.setToolTip(tooltip)
		if obj_name is not None: self.setObjectName(obj_name)

class CustomLabel(QtGui.QLabel):
	def __init__(self, label_text, tooltip=None, obj_name=None):
		super(CustomLabel, self).__init__(label_text)

		if tooltip is not None: self.setToolTip(tooltip)
		if obj_name is not None: self.setObjectName(obj_name)

class CustomSpinBox(QtGui.QDoubleSpinBox):
	def __init__(self, init_values=(0., 100., 0., 1.), tooltip=None, suffix=None, obj_name=None):
		super(CustomSpinBox, self).__init__()

		if any([isinstance(n, float) for n in init_values]):
			self.setDecimals(2)
			init_values = [float(n) for n in init_values]
		else:
			self.setDecimals(0)
		
		# - Init
		spb_min, spb_max, spb_value, spb_step = init_values

		# - Set
		self.setMinimum(spb_min)
		self.setMaximum(spb_max)
		self.setValue(spb_value)
		self.setSingleStep(spb_step)

		if tooltip is not None: self.setToolTip(tooltip)
		if suffix is not None: self.setSuffix(suffix)
		if obj_name is not None: self.setObjectName(obj_name)

# -- Miniwidgets --------------------------
class CustomSpinLabel(QtGui.QWidget):
	def __init__(self, label_text, init_values=(0., 100., 0., 1.), tooltip=None, suffix=None, obj_name=(None, None)):
		super(CustomSpinLabel, self).__init__()

		# - Init
		input_obj_name, lbl_obj_name = None, None
		
		if len(obj_name) == 2:	
			input_obj_name, lbl_obj_name = obj_name

		# - Widgets
		self.label = CustomLabel(label_text, tooltip, lbl_obj_name)
		self.input = CustomSpinBox(init_values, tooltip, suffix, input_obj_name)

		# - Layout
		self.box = QtGui.QHBoxLayout()
		self.box.setContentsMargins(0, 0, 0, 0)
		self.box.addWidget(self.label)
		self.box.addWidget(self.input)
		self.setLayout(self.box)
		self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

class CustomSpinButton(QtGui.QWidget):
	def __init__(self, button_text, init_values=(0., 100., 0., 1.), tooltip=(None, None), obj_name=(None, None)):
		super(CustomSpinButton, self).__init__()

		# - Init
		input_obj_name, btn_obj_name = None, None
		input_obj_tooltip, btn_obj_tooltip = None, None
		
		if len(obj_name) == 2:	
			input_obj_name, btn_obj_name = obj_name

		if len(tooltip) == 2:
			input_obj_tooltip, btn_obj_tooltip = tooltip

		# - Widgets
		self.button = CustomPushButton(button_text, tooltip=btn_obj_tooltip, obj_name=btn_obj_name)
		self.input = CustomSpinBox(init_values, input_obj_tooltip, None, input_obj_name)

		# - Layout
		self.box = QtGui.QHBoxLayout()
		self.box.setContentsMargins(0, 0, 0, 0)
		self.box.addWidget(self.input)
		self.box.addWidget(self.button)
		self.setLayout(self.box)
		self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)

class CustomHorizontalSlider(QtGui.QSlider):
	def __init__(self, init_values=(0., 100., 0., 1.), tooltip=None, obj_name=None):
		super(CustomHorizontalSlider, self).__init__(QtCore.Qt.Horizontal)

		# - Init
		spb_min, spb_max, spb_value, spb_step = init_values

		# - Set
		self.setMinimum(spb_min)
		self.setMaximum(spb_max)
		self.setValue(spb_value)
		self.setSingleStep(spb_step)

		if tooltip is not None: self.setToolTip(tooltip)
		if obj_name is not None: self.setObjectName(obj_name)

# - Controlles ------------------------------------------------
class TRCustomSpinController(QtGui.QWidget):
	def __init__(self, control_name, control_values, control_suffix, control_tooltip, double=False):
		super(TRCustomSpinController, self).__init__()		
		
		# - Helper
		func_change_value = lambda spn_object, value: spn_object.setValue(spn_object.value + value)

		# - Label
		ctrl_lbl = CustomLabel(control_name, obj_name='lbl_panel')
		
		# - Controls
		# -- Slider
		self.ctrl_slider = CustomHorizontalSlider(init_values=control_values, tooltip=control_tooltip, obj_name='sld_panel')
		
		# -- Spinbox
		if double:
			self.spin_box = CustomSpinBox(init_values=control_values, tooltip=control_tooltip, obj_name='spn_panel')
		else:
			self.spin_box = CustomSpinBox(init_values=control_values, tooltip=control_tooltip, obj_name='spn_panel')

		self.spin_box.setSuffix(control_suffix)
		self.spin_box.setMinimumWidth(70)
		self.spin_box.valueChanged.connect(lambda: self.__set_slider_no_signal(self.spin_box.value))

		self.ctrl_slider.valueChanged.connect(lambda: self.setValue(self.ctrl_slider.value))

		# -- Buttons
		self.ctrl_btn_dec_10 = CustomPushButton('value_decrease_double', checkable=False, checked=False, tooltip='-10', obj_name='btn_panel')
		self.ctrl_btn_dec_1 = CustomPushButton('value_decrease', checkable=False, checked=False, tooltip='-1', obj_name='btn_panel')
		self.ctrl_btn_inc_1 = CustomPushButton('value_increase', checkable=False, checked=False, tooltip='+1', obj_name='btn_panel')
		self.ctrl_btn_inc_10 = CustomPushButton('value_increase_double', checkable=False, checked=False, tooltip='+10', obj_name='btn_panel')
		self.opt_sliders = CustomPushButton('value_sliders', checkable=True, checked=False, tooltip='Show Slider Controls', obj_name='btn_panel_opt')

		self.ctrl_btn_dec_10.clicked.connect(lambda: func_change_value(self.spin_box, -10))
		self.ctrl_btn_dec_1.clicked.connect(lambda: func_change_value(self.spin_box, -1))
		self.ctrl_btn_inc_1.clicked.connect(lambda: func_change_value(self.spin_box, 1))
		self.ctrl_btn_inc_10.clicked.connect(lambda: func_change_value(self.spin_box, 10))
		self.opt_sliders.clicked.connect(lambda: self.__toggle_slider())

		self.__toggle_slider()

		# - Layout
		self.lay_box = QtGui.QVBoxLayout()
		lay_controls = QtGui.QHBoxLayout()

		lay_controls.addWidget(ctrl_lbl)
		lay_controls.addWidget(self.spin_box)
		lay_controls.addWidget(self.ctrl_btn_dec_10)
		lay_controls.addWidget(self.ctrl_btn_dec_1)
		lay_controls.addWidget(self.ctrl_btn_inc_1)
		lay_controls.addWidget(self.ctrl_btn_inc_10)
		lay_controls.addWidget(self.opt_sliders)
		lay_controls.setContentsMargins(0, 0, 0, 0)

		self.lay_box.addLayout(lay_controls)
		self.lay_box.addWidget(self.ctrl_slider)
		self.lay_box.setContentsMargins(0, 0, 0, 0)
		
		box_controls = QtGui.QGroupBox()
		box_controls.setObjectName('box_group')
		box_controls.setLayout(self.lay_box)
		
		lay_main = QtGui.QHBoxLayout()
		lay_main.addWidget(box_controls)
		lay_main.setContentsMargins(0, 0, 0, 0)

		self.setLayout(lay_main)

	# - Functions
	# -- Internal
	def __set_slider_no_signal(self, value):
		self.ctrl_slider.blockSignals(True)
		self.ctrl_slider.setValue(value)
		self.ctrl_slider.blockSignals(False)

	def __toggle_slider(self):
		if self.opt_sliders.isChecked():
			self.ctrl_slider.show()
		else:
			self.ctrl_slider.hide()

	# -- External
	def contract(self):
		self.spin_box.setMinimumWidth(45)
		self.spin_box.setMaximumWidth(45)
		self.ctrl_btn_dec_10.hide()
		self.ctrl_btn_dec_1.hide()
		self.ctrl_btn_inc_1.hide()
		self.ctrl_btn_inc_10.hide()
		self.opt_sliders.hide()
		self.ctrl_slider.hide()

	def expand(self):
		self.spin_box.setMinimumWidth(70)
		self.spin_box.setMaximumWidth(70)
		self.ctrl_btn_dec_10.show()
		self.ctrl_btn_dec_1.show()
		self.ctrl_btn_inc_1.show()
		self.ctrl_btn_inc_10.show()	
		self.opt_sliders.show()
		self.__toggle_slider()

	def blockSignals(self, state):
		self.spin_box.blockSignals(state)
		self.ctrl_btn_dec_10.blockSignals(state)
		self.ctrl_btn_dec_1.blockSignals(state)
		self.ctrl_btn_inc_1.blockSignals(state)
		self.ctrl_btn_inc_10.blockSignals(state)
		self.ctrl_slider.blockSignals(state)

	def setEnabled(self, state):
		self.spin_box.setEnabled(state)
		self.ctrl_btn_dec_10.setEnabled(state)
		self.ctrl_btn_dec_1.setEnabled(state)
		self.ctrl_btn_inc_1.setEnabled(state)
		self.ctrl_btn_inc_10.setEnabled(state)
		self.opt_sliders.setEnabled(state)
		self.ctrl_slider.setEnabled(state)

	def setValue(self, value):
		self.spin_box.setValue(value)
		self.__set_slider_no_signal(value)

	def getValue(self):
		return self.spin_box.value

# -- Sub Dialogs --------------------------
class TRLayerSelectDLG(QtGui.QDialog):
	def __init__(self, parent, mode, font=None, glyph=None):
		super(TRLayerSelectDLG, self).__init__()
	
		# - Init
		self.parent_widget = parent
		self.column_names = ('Layer Name', 'Layer Type')
		self.color_dict = {'Master': QtGui.QColor(0, 255, 0, 20), 'Service': QtGui.QColor(0, 0, 255, 20), 'Mask': QtGui.QColor(255, 0, 0, 20)}
		column_init = (None, None)
		table_dict = {1:OrderedDict(zip(self.column_names, column_init))}
		
		# - Basic Widgets
	
		# - Search Box
		self.edt_search_field = QtGui.QLineEdit()
		self.edt_search_field.setPlaceholderText('Filter: Layer Name')
		self.edt_search_field.textChanged.connect(self.table_filter)
		self.btn_search_field = QtGui.QPushButton('Clear')
		self.btn_search_field.clicked.connect(lambda: self.edt_search_field.setText(''))

		# -- Layer Buttons
		self.btn_tableCheck = QtGui.QPushButton('Select All')
		self.btn_tableSwap = QtGui.QPushButton('Swap Selection')
		self.btn_tableCheckMasters = QtGui.QPushButton('Masters')
		self.btn_tableCheckMasks = QtGui.QPushButton('Masks')
		self.btn_tableCheckServices = QtGui.QPushButton('Services')

		self.btn_tableCheck.setToolTip('Click check all.\n<Shift> + Click uncheck all.')
		self.btn_tableCheckMasters.setToolTip('Click check all.\n<Shift> + Click uncheck all.')
		self.btn_tableCheckMasks.setToolTip('Click check all.\n<Shift> + Click uncheck all.')
		self.btn_tableCheckServices.setToolTip('Click check all.\n<Shift> + Click uncheck all.')
		
		self.btn_tableCheck.clicked.connect(lambda: self.table_check_all())
		self.btn_tableSwap.clicked.connect(lambda: self.table_check_all(do_swap=True))
		self.btn_tableCheckMasters.clicked.connect(lambda: self.table_check_all('Master'))
		self.btn_tableCheckMasks.clicked.connect(lambda: self.table_check_all('Mask'))
		self.btn_tableCheckServices.clicked.connect(lambda: self.table_check_all('Service'))

		# -- Table 
		self.tab_masters = TRCheckTableView(table_dict)
		self.table_populate(mode, font, glyph)
		self.tab_masters.cellChanged.connect(lambda: self.parent_widget.layers_refresh())

		# - Build layout
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(self.btn_tableCheck, 				0, 0, 1, 2)
		layoutV.addWidget(self.btn_tableSwap, 				0, 2, 1, 2)
		layoutV.addWidget(self.btn_tableCheckMasters, 		1, 0, 1, 2)
		layoutV.addWidget(self.btn_tableCheckMasks, 		1, 2, 1, 1)
		layoutV.addWidget(self.btn_tableCheckServices, 		1, 3, 1, 1)
		layoutV.addWidget(self.edt_search_field,	 		2, 0, 1, 3)
		layoutV.addWidget(self.btn_search_field, 			2, 3, 1, 1)
		layoutV.addWidget(self.tab_masters, 				3, 0, 20, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('Select Layers')
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.setGeometry(500, 200, 300, 600)

	# - Table operations
	def table_filter(self):
		search_string = self.edt_search_field.text

		for row in range(self.tab_masters.rowCount):
			if len(search_string):
				if search_string.lower() not in self.tab_masters.item(row, 0).text().lower():
					self.tab_masters.hideRow(row)
			else:
				self.tab_masters.showRow(row)

	def table_check_all(self, layer_type=None, do_swap=False):
		modifiers = QtGui.QApplication.keyboardModifiers() # Listen to Shift - reverses the ratio

		for row in range(self.tab_masters.rowCount):
			if modifiers == QtCore.Qt.AltModifier or do_swap: # Toggle state
				if self.tab_masters.item(row, 0).checkState() == QtCore.Qt.Checked:
					self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Unchecked)
				else:
					self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Checked)		

			elif modifiers == QtCore.Qt.ShiftModifier: # Uncheck all
				if not self.tab_masters.isRowHidden(row):
					self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Unchecked)								

			else: # Check all
				if layer_type is None or self.tab_masters.item(row,1).text() == layer_type:
					if not self.tab_masters.isRowHidden(row):
						self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Checked)
	
	def table_populate(self, mode, font=None, glyph=None):
		if mode !=0:
			self.btn_tableCheckMasters.hide()
			self.btn_tableCheckMasks.hide()
			self.btn_tableCheckServices.hide()
		else:
			self.btn_tableCheckMasters.show()
			self.btn_tableCheckMasks.show()
			self.btn_tableCheckServices.show()

		# - Helper	
		def check_type(layer):
			if layer.isMaskLayer: return 'Mask'
			if layer.isMasterLayer: return 'Master'
			if layer.isService: return 'Service'
		
		# - Set Table
		if fl6.CurrentFont() is not None and fl6.CurrentGlyph() is not None:
			active_font = pFont() if font is None else font
			active_glyph = eGlyph() if glyph is None else glyph

			if mode == 0:
				init_data = [(layer.name, check_type(layer)) for layer in active_glyph.layers() if '#' not in layer.name]
			else:
				init_data = [(master, 'Master') for master in active_font.pMasters.names]
			
			table_dict = {n:OrderedDict(zip(self.column_names, data)) for n, data in enumerate(init_data)}
			self.tab_masters.clear()
			self.tab_masters.setTable(table_dict, color_dict=self.color_dict, enable_check=True)		

# -- Trees --------------------------------
class TRDeltaLayerTree(QtGui.QTreeWidget):
	def __init__(self, data=None, headers=None):
		super(TRDeltaLayerTree, self).__init__()
		
		# - Init
		if data is not None: self.setTree(data, headers)
		self.itemChanged.connect(self._redecorateItem)
		self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.expandAll()
		self.setAlternatingRowColors(True)

		# - Drag and drop
		self.setDragDropMode(self.InternalMove)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)

		# - Contextual Menu
		self.menu = QtGui.QMenu(self)
		self.menu.setTitle('Actions:')

		act_addItem = QtGui.QAction('Add', self)
		act_delItem = QtGui.QAction('Remove', self)
		act_dupItem = QtGui.QAction('Duplicate', self)
		act_uneItem = QtGui.QAction('Unnest', self)

		self.menu.addAction(act_addItem)
		self.menu.addAction(act_dupItem)
		self.menu.addAction(act_uneItem)
		self.menu.addAction(act_delItem)
		
		act_addItem.triggered.connect(lambda: self._addItem())
		act_dupItem.triggered.connect(lambda: self._duplicateItems())
		act_uneItem.triggered.connect(lambda: self._unnestItem())
		act_delItem.triggered.connect(lambda: self._removeItems())

	# - Internals --------------------------
	def contextMenuEvent(self, event):
		self.menu.popup(QtGui.QCursor.pos())	

	def _rand_hex(self):
		rand_color = lambda: randint(0,255)
		return '#%02X%02X%02X' %(rand_color(), rand_color(), rand_color())

	def _removeItems(self):
		root = self.invisibleRootItem()
		
		for item in self.selectedItems():
			(item.parent() or root).removeChild(item)

	def _addItem(self, parent=None, data=None):
		new_item_data = ['New', '', '', 100., 100., self._rand_hex()] if data is None else data

		if parent is None:
			root = self.selectedItems()[0].parent() if len(self.selectedItems()) else self.invisibleRootItem()
		else:
			root = parent

		new_item = QtGui.QTreeWidgetItem(root, new_item_data)
		color_decorator = QtGui.QColor(new_item_data[-1]) if not isinstance(new_item_data[-1], QtGui.QColor) else new_item_data[-1]
		new_item.setData(0, QtCore.Qt.DecorationRole, color_decorator)
		new_item.setFlags(new_item.flags() & ~QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEditable)

	def _duplicateItems(self):
		root = self.invisibleRootItem()
		
		for item in self.selectedItems():
			duplicate_data = [item.text(c) for c in range(item.columnCount())]
			self._addItem(item.parent(), duplicate_data)
		
	def _unnestItem(self):
		root = self.invisibleRootItem()
		
		for item in reversed(self.selectedItems()):
			old_parent = item.parent()
			new_parent = old_parent.parent()
			ix = old_parent.indexOfChild(item)
			item_without_parent = old_parent.takeChild(ix)
			root.addChild(item_without_parent)

	def _setItemData(self, data, column, position=1, strip=False):
		for item in self.selectedItems():
			old_text = item.text(column)

			if position == 1:
				item.setText(column, data if not strip else old_text.strip(data))
			if position == 0:
				item.setText(column, data + old_text)
			if position == -1:
				item.setText(column, old_text + data)

	def _redecorateItem(self, item):
		color_decorator = QtGui.QColor(item.text(item.columnCount()-1))
		item.setData(0, QtCore.Qt.DecorationRole, color_decorator)
		#item.setFlags(item.flags() & ~QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEditable)

	# - Getter/Setter -----------------------
	def setTree(self, data, headers):
		self.blockSignals(True)
		self.clear()
		self.setHeaderLabels(headers)

		# - Insert 
		for key, value in data.items():
			master = QtGui.QTreeWidgetItem(self, [key])

			for data in value:
				self._addItem(master, data)
				
		# - Fit data
		for c in range(self.columnCount):
			self.resizeColumnToContents(c)	

		self.invisibleRootItem().setFlags(self.invisibleRootItem().flags() & ~QtCore.Qt.ItemIsDropEnabled)
		self.expandAll()
		self.hideColumn(5)
		self.blockSignals(False)

	def getTree(self):
		returnDict = OrderedDict()
		root = self.invisibleRootItem()

		for i in range(root.childCount()):
			item = root.child(i)
			returnDict[item.text(0)] = [[item.child(n).text(c) for c in range(item.child(n).columnCount())] for n in range(item.childCount())]
		
		return returnDict

# -- ListViews ----------------------------
class TRGlyphSelect(QtGui.QWidget):
	# - Split/Break contour 
	def __init__(self, font=None, parent=None):
		super(TRGlyphSelect, self).__init__()

		# - Init
		self.active_font = font
		self.parentWgt = self.parent if parent is None else parent

		# - Widgets
		# -- Buttons
		self.btn_filter = QtGui.QPushButton('Refresh')
		self.btn_filter.clicked.connect(self.refresh)

		self.chk_glyphName = QtGui.QCheckBox('Name')
		self.chk_glyphMark = QtGui.QCheckBox('Mark')
		self.chk_glyphUnicode = QtGui.QCheckBox('Unicode')
		self.chk_glyphChecked = QtGui.QCheckBox('Check all')

		self.chk_glyphName.setChecked(True)
		self.chk_glyphMark.setChecked(True)
		self.chk_glyphUnicode.setChecked(True)
		self.chk_glyphChecked.setChecked(True)
		
		# -- Fileds
		self.edt_filter = QtGui.QLineEdit()
		self.edt_filter.setPlaceholderText('Filter glyphnames')
		self.edt_filter.textChanged.connect(self.__filterClicked)

		self.lst_glyphNames = QtGui.QListView(self.parentWgt)
		self.model = QtGui.QStandardItemModel(self.lst_glyphNames)
		
		if self.active_font is not None:
			self.refresh()
		
		# -- Build Layout
		self.layout = QtGui.QGridLayout()
		self.layout.addWidget(QtGui.QLabel('Destination Glyphs:'),	0,0,1,4)
		self.layout.addWidget(self.edt_filter,			1,0,1,3)
		self.layout.addWidget(self.btn_filter,			1,3,1,1)
		self.layout.addWidget(self.chk_glyphName,		2,0,1,1)
		self.layout.addWidget(self.chk_glyphUnicode,	2,1,1,1)
		self.layout.addWidget(self.chk_glyphMark,		2,2,1,1)
		self.layout.addWidget(self.chk_glyphChecked,	2,3,1,1)
		self.layout.addWidget(self.lst_glyphNames,		3,0,1,4)
		
	def refresh(self):
		# - Init
		self.model.removeRows(0, self.model.rowCount())
		self.data_glyphs = getProcessGlyphs(pMode)

		# - Set Items
		for glyph in self.data_glyphs:
			glyph_name = ''

			# - GlyphName
			if self.chk_glyphUnicode.isChecked():
				try:
					glyph_name += str(hex(glyph.unicode)).upper() + '\t'
				except TypeError:
					glyph_name += ' '*6 + '\t'

			if self.chk_glyphName.isChecked():
				glyph_name += glyph.name			
			
			item = QtGui.QStandardItem(glyph_name)

			# - Set Mark
			if self.chk_glyphMark.isChecked():
				new_color = QtGui.QColor(fontMarkColors[glyph.mark])
				new_color.setAlpha(30)
				item.setBackground(QtGui.QBrush(new_color))
			
			# - Set Check
			item.setCheckable(True)
			if self.chk_glyphChecked.isChecked():
				item.setChecked(True)

			self.model.appendRow(item)
		
		self.lst_glyphNames.setModel(self.model)

	def __filterClicked(self):
		filter_text = self.edt_filter.text.lower()
		
		for row in range(self.model.rowCount()):
			if filter_text in self.model.item(row).text().lower():
				self.lst_glyphNames.setRowHidden(row, False)
			else:
				self.lst_glyphNames.setRowHidden(row, True)
				self.lst_glyphNames.item(row),setChecked(False)

	def getGlyphs(self):
		selected_glyphs = []
		for row in range(self.model.rowCount()):
			if self.model.item(row).checkState() == QtCore.Qt.Checked:
				selected_glyphs.append(self.model.item(row).text())

		return selected_glyphs

# - Special controls ----------------------------------------------
class TREdit2Spin(QtGui.QWidget):
	def __init__(self, filed_t, edit_t=''):
		super(TREdit2Spin, self).__init__()

		# - Widgets
		self.lbl_filed = QtGui.QLabel(filed_t)
		
		self.edt_field = TRGLineEdit()
		self.edt_field.setPlaceholderText(edit_t)
		
		self.spb_prc = QtGui.QSpinBox()
		self.spb_prc.setMaximum(100)
		self.spb_prc.setSuffix('%')

		self.spb_unit =  QtGui.QSpinBox()
		self.spb_unit.setMaximum(100)
		self.spb_unit.setMinimum(-100)
		self.spb_unit.setSuffix(' U')

		# - Layout
		self.lay_main = QtGui.QHBoxLayout()
		self.lay_main.addWidget(lbl_field)
		self.lay_main.addWidget(edt_field)
		self.lay_main.addWidget(spb_prc)
		self.lay_main.addWidget(spb_unit)

	def get_values():
		return [self.edt_field.currentText, self.spb_prc.value, self.spb_unit.value]

class TRCombo2Spin(QtGui.QWidget):
	def __init__(self, filed_t, combo_items):
		super(TREdit2Spin, self).__init__()

		# - Widgets
		self.lbl_filed = QtGui.QLabel(filed_t)
		
		self.cmb_field = QComboBox()
		self.cmb_field.addItems(combo_items)
		
		self.spb_prc = QtGui.QSpinBox()
		self.spb_prc.setMaximum(100)
		self.spb_prc.setSuffix('%')

		self.spb_unit =  QtGui.QSpinBox()
		self.spb_unit.setMaximum(100)
		self.spb_unit.setMinimum(-100)
		self.spb_unit.setSuffix(' U')

		# - Layout
		self.lay_main = QtGui.QHBoxLayout()
		self.lay_main.addWidget(lbl_field)
		self.lay_main.addWidget(cmb_field)
		self.lay_main.addWidget(spb_prc)
		self.lay_main.addWidget(spb_unit)

	def get_values():
		return [self.cmb_field.currentText, self.spb_prc.value, self.spb_unit.value]

class TRColorCombo(QtGui.QComboBox):
	def __init__(self, *args, **kwargs):
		super(TRColorCombo, self).__init__(*args, **kwargs)

		# - Init
		self.color_codes = {name:value for name, value, discard in fontMarkColors}
		
		# - Build
		for i in range(len(fontMarkColors)):
			self.addItem(fontMarkColors[i][0])
			self.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

	def getValue(self):
		return self.color_codes[self.currentText]
			
# - Line Edit -----------------------------------------------------
class TRGLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		
		super(TRGLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		curret_glyph = eGlyph()
		menu.addSeparator()
		menu.addAction(u'Get {Glyph Name}', lambda: self.setText(curret_glyph.name))
		menu.addAction(u'Get {Glyph Unicodes}', lambda: self.setText(' '.join(map(str,curret_glyph.unicodes))))
		menu.addAction(u'Get {Glyph Tags}', lambda: self.setText(' '.join(map(str,curret_glyph.tags))))
		menu.addSeparator()
		menu.addAction(u'To Lowercase', lambda: self.setText(self.text.lower()))
		menu.addAction(u'To Uppercase', lambda: self.setText(self.text.upper()))
		menu.addAction(u'To Titlecase', lambda: self.setText(self.text.title()))
		menu.addSeparator()
		menu.addAction(u'.salt', lambda: self.setText('%s.salt' %self.text))
		menu.addAction(u'.calt', lambda: self.setText('%s.calt' %self.text))
		menu.addAction(u'.ss0', lambda: self.setText('%s.ss0' %self.text))
		menu.addAction(u'.locl', lambda: self.setText('%s.locl' %self.text))
		menu.addAction(u'.smcp', lambda: self.setText('%s.smcp' %self.text))
		menu.addAction(u'.cscp', lambda: self.setText('%s.cscp' %self.text))
		menu.addAction(u'.onum', lambda: self.setText('%s.onum' %self.text))
		menu.addAction(u'.pnum', lambda: self.setText('%s.pnum' %self.text))
		menu.addAction(u'.tnum', lambda: self.setText('%s.tnum' %self.text))
		menu.addAction(u'.bak', lambda: self.setText('%s.bak' %self.text))

# -- Transform Controls -----------------------------------------------
class TRTransformCtrl(QtGui.QWidget):
	def __init__(self):
		super(TRTransformCtrl, self).__init__()

		# - Init
		self.lay_main = QtGui.QVBoxLayout()
		self.lay_main.setContentsMargins(0,0,0,0)
		
		self.lay_box = QtGui.QVBoxLayout()
		self.lay_box.setContentsMargins(0,0,0,0)
		
		box_transform = QtGui.QGroupBox()
		box_transform.setObjectName('box_group')

		# - Origin of transformation 
		self.grp_options = QtGui.QButtonGroup()
		self.grp_options.setExclusive(True)

		self.lay_options = TRFlowLayout(spacing=10)

		tooltip_button = "Transform at Origin"
		self.chk_or = CustomPushButton("node_align_bottom_left", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_or, 1)
		self.lay_options.addWidget(self.chk_or)

		tooltip_button = "Transform at Bottom Left corner"
		self.chk_bl = CustomPushButton("node_bottom_left", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_bl, 2)
		self.lay_options.addWidget(self.chk_bl)

		tooltip_button = "Transform at Bottom Right corner"
		self.chk_br = CustomPushButton("node_bottom_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_br, 4)
		self.lay_options.addWidget(self.chk_br)
		
		tooltip_button = "Transform at Center"
		self.chk_ce = CustomPushButton("node_center", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_ce, 6)
		self.lay_options.addWidget(self.chk_ce)

		tooltip_button = "Transform at Top Left corner"
		self.chk_tl = CustomPushButton("node_top_left", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_tl, 3)
		self.lay_options.addWidget(self.chk_tl)


		tooltip_button = "Transform at Top Right corner"
		self.chk_tr = CustomPushButton("node_top_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_options.addButton(self.chk_tr, 5)
		self.lay_options.addWidget(self.chk_tr)

		self.lay_box.addLayout(self.lay_options)

		# - Spinboxes
		self.lay_controls = TRFlowLayout(spacing=10) 

		tooltip_button = "Scale X"
		self.spb_scale_x = CustomSpinLabel('scale_x', (-999., 999., 100., 1.), tooltip_button, ' %', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_scale_x)

		tooltip_button = "Scale Y"
		self.spb_scale_y = CustomSpinLabel('scale_y', (-999., 999., 100., 1.), tooltip_button, ' %', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_scale_y)

		tooltip_button = "Translate X"
		self.spb_translate_x = CustomSpinLabel('translate_x', (-999., 999, 0., 1.), tooltip_button, ' u', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_translate_x)

		tooltip_button = "Translate Y"
		self.spb_translate_y = CustomSpinLabel('translate_y', (-999., 999., 0., 1.), tooltip_button, ' u', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_translate_y)

		tooltip_button = "Skew/Slant"
		self.spb_shear = CustomSpinLabel('skew', (-90., 90., 0., 1.), tooltip_button, ' °', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_shear)

		tooltip_button = "Rotate"
		self.spb_rotate = CustomSpinLabel('rotate', (-360., 360., 0., 1.), tooltip_button, ' °', ('spn_panel_inf', 'lbl_panel'))
		self.lay_controls.addWidget(self.spb_rotate)

		tooltip_button = "Reset fields"
		self.btn_reset = CustomPushButton("refresh", tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_options.addWidget(self.btn_reset)
		self.btn_reset.clicked.connect(self.reset)

		tooltip_button = "Transform selected contours"
		self.btn_transform = CustomPushButton("action_play", tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_controls.addWidget(self.btn_transform)

		self.lay_box.addLayout(self.lay_controls)

		box_transform.setLayout(self.lay_box)
		self.lay_main.addWidget(box_transform)

		self.setLayout(self.lay_main)
		
	def reset(self):
		self.spb_scale_x.input.setValue(100)
		self.spb_scale_y.input.setValue(100)
		self.spb_translate_x.input.setValue(0)
		self.spb_translate_y.input.setValue(0)
		self.spb_shear.input.setValue(0)
		self.spb_rotate.input.setValue(0)

	def calcTransform(self, transform_values, obj_rect=QtCore.QRectF(.0, .0, .0, .0)):
		# - Init
		scale_x, scale_y, translate_x, translate_y, shear, rotate = transform_values

		origin_transform = QtGui.QTransform()
		rev_origin_transform = QtGui.QTransform()
		return_transform = QtGui.QTransform()
		
		m11 = float(scale_x)/100.
		m13 = float(translate_x)
		m22 = float(scale_y)/100.
		m23 = float(translate_y)

		# - Transform
		if self.chk_or.isChecked():	transform_origin = QtCore.QPointF(.0, .0)
		if self.chk_bl.isChecked():	transform_origin = obj_rect.topLeft()
		if self.chk_br.isChecked():	transform_origin = obj_rect.topRight()
		if self.chk_tl.isChecked():	transform_origin = obj_rect.bottomLeft()
		if self.chk_tr.isChecked():	transform_origin = obj_rect.bottomRight()
		if self.chk_ce.isChecked():	transform_origin = obj_rect.center()
		
		origin_transform.translate(-transform_origin.x(), -transform_origin.y())
		rev_origin_transform.translate(transform_origin.x(), transform_origin.y())

		return_transform.scale(m11, m22)
		return_transform.rotate(-float(rotate))
		return_transform.shear(radians(float(shear)), 0.)
		return_transform.translate(m13, m23)

		return return_transform, origin_transform, rev_origin_transform

	def getTransform(self, obj_rect=QtCore.QRectF(.0, .0, .0, .0)):
		transform_values = (self.spb_scale_x.input.value,
							self.spb_scale_y.input.value,
							self.spb_translate_x.input.value,
							self.spb_translate_y.input.value,
							self.spb_shear.input.value,
							self.spb_rotate.input.value,
							)
		return self.calcTransform(transform_values, obj_rect)

# -- Sliders --------------------------------------------------------------
class TRSliderCtrl(QtGui.QGridLayout):
	def __init__(self, edt_0, edt_1, edt_pos, spb_step):
		super(TRSliderCtrl, self).__init__()
		
		# - Init
		self.initValues = (edt_0, edt_1, edt_pos, spb_step)

		self.edt_0 = QtGui.QLineEdit(edt_0)
		self.edt_1 = QtGui.QLineEdit(edt_1)
		self.edt_pos = QtGui.QLineEdit(edt_pos)

		self.spb_step = QtGui.QSpinBox()
		self.spb_step.setValue(spb_step)

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.sld_axis.valueChanged.connect(self.sliderChange)
		self.refreshSlider()
		
		self.edt_0.editingFinished.connect(self.refreshSlider)
		self.edt_1.editingFinished.connect(self.refreshSlider)
		self.spb_step.valueChanged.connect(self.refreshSlider)
		self.edt_pos.editingFinished.connect(self.refreshSlider)

		# - Layout		
		self.addWidget(self.sld_axis, 			0, 0, 1, 5)
		self.addWidget(self.edt_pos, 			0, 5, 1, 1)		
		self.addWidget(QtGui.QLabel('Min:'),	1, 0, 1, 1)
		self.addWidget(self.edt_0, 				1, 1, 1, 1)
		self.addWidget(QtGui.QLabel('Max:'), 	1, 2, 1, 1)
		self.addWidget(self.edt_1, 				1, 3, 1, 1)
		self.addWidget(QtGui.QLabel('Step:'),	1, 4, 1, 1)
		self.addWidget(self.spb_step, 			1, 5, 1, 1)


	def refreshSlider(self):
		self.sld_axis.blockSignals(True)
		self.sld_axis.setMinimum(float(self.edt_0.text.strip()))
		self.sld_axis.setMaximum(float(self.edt_1.text.strip()))
		self.sld_axis.setValue(float(self.edt_pos.text.strip()))
		self.sld_axis.setSingleStep(int(self.spb_step.value))
		self.sld_axis.blockSignals(False)
				
	def reset(self):
		self.edt_0.setText(self.initValues[0])
		self.edt_1.setText(self.initValues[1])
		self.edt_pos.setText(self.initValues[2])
		self.spb_step.setValue(self.initValues[3])
		self.refreshSlider()

	def sliderChange(self):
		self.edt_pos.setText(self.sld_axis.value)

# -- Tables ------------------------------------------------------
class TRTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRTableView, self).__init__()

		# - Init
		self.flag_valueChanged = QtGui.QColor('powderblue')

		# - Set 
		if data is not None: self.setTable(data)
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)
		self.setSortingEnabled(False)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, sortData=(True, True), indexColCheckable=None):
		name_row, name_column = [], []
		self.blockSignals(True)

		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Populate
		for row, value in enumerate(sorted(data.keys()) if sortData[0] else data.keys()):
			name_row.append(value)
			
			for col, key in enumerate(sorted(data[value].keys()) if sortData[1] else data[value].keys()):
				name_column.append(key)
				rowData = data[value][key]
				
				if isinstance(rowData, basestring):
					newitem = QtGui.QTableWidgetItem(str(rowData))
				else:
					newitem = QtGui.QTableWidgetItem()
					newitem.setData(QtCore.Qt.EditRole, rowData)
									
				# - Make the columnt checkable
				if indexColCheckable is not None and col in indexColCheckable:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
					newitem.setCheckState(QtCore.Qt.Unchecked) 

				self.setItem(row, col, newitem)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self, raw=False):
		return_list = []

		for row in range(self.rowCount):
			if not raw:
				return_list.append((self.verticalHeaderItem(row).text(), {self.horizontalHeaderItem(col).text():float(self.item(row, col).text()) for col in range(self.columnCount)}))
			else:
				return_list.append((self.verticalHeaderItem(row).text(), [(self.horizontalHeaderItem(col).text(), self.item(row, col).text()) for col in range(self.columnCount)]))

		if raw:	return return_list			
		return dict(return_list)
		

	def markChange(self, item):
		item.setBackground(self.flag_valueChanged)

class TRCheckTableView(QtGui.QTableWidget):
	def __init__(self, data, color_dict=None, enable_check=False):
		super(TRCheckTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
	
		# - Set 
		if data is not None:
			self.setTable(data, color_dict, enable_check)		
	
		# - Styling
		#self.setSortingEnabled(True)
		self.horizontalHeader().setStretchLastSection(True)
		self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)
		self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, color_dict=None, enable_check=False):
		self.clear()
		self.setSortingEnabled(False)
		self.blockSignals(True)
		self.model().sort(-1)
		self.horizontalHeader().setSortIndicator(-1, 0)

		name_row, name_column = [], []

		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Populate
		for n, layer in enumerate(data.keys()):
			name_row.append(layer)

			for m, key in enumerate(data[layer].keys()):
				
				# -- Build name column
				name_column.append(key)
				
				# -- Selectively add data
				newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
				
				if m == 0 and enable_check:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setCheckState(QtCore.Qt.Unchecked)
				
				try:
					newitem.setData(QtCore.Qt.DecorationRole, data[layer]['Layer Color'])
				except KeyError:
					pass
				
				if color_dict is not None:
					try:
						newitem.setBackground(color_dict[data[layer]['Layer Type']])
					except KeyError:
						pass
		
				self.setItem(n, m, newitem)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.resizeColumnsToContents()

		self.blockSignals(False)
		self.setSortingEnabled(True)

		self.horizontalHeader().setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		self.horizontalHeader().setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)

	def getTable(self):
		return [self.item(row, 0).text() for row in range(self.rowCount) if self.item(row, 0).checkState() == QtCore.Qt.Checked]

# - Folder/collapsible widgets ---------------------------------------
class TRCollapsibleBox(QtGui.QWidget):
	def __init__(self, title="", parent=None):
		super(TRCollapsibleBox, self).__init__(parent)

		self.toggle_button = QtGui.QToolButton()
		self.toggle_button.text = '  ' + title
		self.toggle_button.checkable = True
		self.toggle_button.checked = True
		self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; vertical-align: middle }")
		self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
		self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
		self.toggle_button.setIconSize(QtCore.QSize(5,5))
		self.toggle_button.clicked.connect(self.on_pressed)

		self.toggle_animation = QtCore.QParallelAnimationGroup(self)

		self.content_area = QtGui.QScrollArea()
		self.content_area.maximumHeight = 0
		self.content_area.minimumHeight = 0

		self.content_area.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
		self.content_area.setFrameShape(QtGui.QFrame.NoFrame)

		lay = QtGui.QVBoxLayout(self)
		lay.setSpacing(0)
		lay.setContentsMargins(0, 0, 0, 0)
		lay.addWidget(self.toggle_button)
		lay.addWidget(self.content_area)

		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self.content_area, b"maximumHeight"))

	def on_pressed(self):
		checked = self.toggle_button.isChecked()
		
		self.toggle_button.setArrowType(QtCore.Qt.DownArrow if not checked else QtCore.Qt.RightArrow)
		self.toggle_animation.setDirection(QtCore.QAbstractAnimation.Forward if not checked	else QtCore.QAbstractAnimation.Backward)
		self.toggle_animation.start()

	def setContentLayout(self, layout):
		lay = self.content_area.layout()
		del lay
		self.content_area.setLayout(layout)
		collapsed_height = (self.sizeHint.height() - self.content_area.maximumHeight)
		content_height = layout.sizeHint().height()

		for i in range(self.toggle_animation.animationCount()):
			animation = self.toggle_animation.animationAt(i)
			animation.setDuration(100)
			animation.setStartValue(collapsed_height)
			animation.setEndValue(collapsed_height + content_height)

		content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
		content_animation.setDuration(100)
		content_animation.setStartValue(0)
		content_animation.setEndValue(content_height)


# - Tab Widgets -----------------------------------------------------------
class TRHTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		

class TRVTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		self.setUsesScrollButtons(True)
		self.setTabPosition(QtGui.QTabWidget.East)
		

# - Layouts ----------------------------------------
class TRFlowLayout(QtGui.QLayout):
	# As adapted from https://stackoverflow.com/questions/60398756/pyqt-oriented-flow-layout
	
	def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None, margin=0, spacing=-1):
		super(TRFlowLayout, self).__init__(parent)
		self.orientation = orientation

		if parent is not None:
			self.setContentsMargins(margin, margin, margin, margin)

		self.setSpacing(spacing)
		self.itemList = []

	def __del__(self):
		item = self.takeAt(0)
		while item:
			item = self.takeAt(0)

	def addItem(self, item):
		self.itemList.append(item)

	def count(self):
		return len(self.itemList)

	def itemAt(self, index):
		if index >= 0 and index < len(self.itemList):
			return self.itemList[index]

		return None

	def takeAt(self, index):
		if index >= 0 and index < len(self.itemList):
			return self.itemList.pop(index)

		return None

	def expandingDirections(self):
		return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

	def hasHeightForWidth(self):
		return self.orientation == QtCore.Qt.Horizontal

	def heightForWidth(self, width):
		return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

	def hasWidthForHeight(self):
		return self.orientation == QtCore.Qt.Vertical

	def widthForHeight(self, height):
		return self.doLayout(QtCore.QRect(0, 0, 0, height), True)

	def setGeometry(self, rect):
		#super().setGeometry(rect)
		self.doLayout(rect, False)

	def sizeHint(self):
		return self.minimumSize()

	def minimumSize(self):
		size = QtCore.QSize()

		for item in self.itemList:
			size = size.expandedTo(item.minimumSize())

		size += QtCore.QSize(2 * self.margin, 2 * self.margin)

		return size

	def doLayout(self, rect, testOnly):
		x = rect.x()
		y = rect.y()
		lineHeight = columnWidth = heightForWidth = 0

		for item in self.itemList:
			widget = item.widget()
			spaceX = self.spacing + widget.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
			spaceY = self.spacing + widget.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Vertical)
			
			if self.orientation == QtCore.Qt.Horizontal:
				nextX = x + item.sizeHint().width() + spaceX
				
				if nextX - spaceX > rect.right() and lineHeight > 0:
					x = rect.x()
					y = y + lineHeight + spaceY
					nextX = x + item.sizeHint().width() + spaceX
					lineHeight = 0

				if not testOnly:
					item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

				x = nextX
				lineHeight = max(lineHeight, item.sizeHint().height())
			
			else:
				nextY = y + item.sizeHint().height() + spaceY
				
				if nextY - spaceY > rect.bottom() and columnWidth > 0:
					x = x + columnWidth + spaceX
					y = rect.y()
					nextY = y + item.sizeHint().height() + spaceY
					columnWidth = 0

				heightForWidth += item.sizeHint().height() + spaceY
				if not testOnly:
					item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

				y = nextY
				columnWidth = max(columnWidth, item.sizeHint().width())

		if self.orientation == QtCore.Qt.Horizontal:
			return y + lineHeight - rect.y()
		
		else:
			return heightForWidth - rect.y()
