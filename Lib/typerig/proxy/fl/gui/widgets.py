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
from platform import system

import os
import fontlab as fl6

from PythonQt import QtCore, QtGui
#from typerig.proxy.fl.gui import QtGui

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

# - Init ----------------------------------
__version__ = '0.3.6'

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
	
# - Classes -------------------------------
# -- Basics -------------------------------
def CustomPushButton(button_text, checkable=False, cheked=False, enabled=True, tooltip=None, obj_name=None):
	new_button = QtGui.QPushButton(button_text)
	new_button.setCheckable(checkable)
	new_button.setChecked(cheked)
	new_button.setEnabled(enabled)

	if tooltip is not None:
		new_button.setToolTip(tooltip)

	if obj_name is not None:
		new_button.setObjectName(obj_name)

	return new_button

def CustomLabel(label_text, obj_name=None):
	new_label = QtGui.QLabel(label_text)

	if obj_name is not None:
		new_label.setObjectName(obj_name)
		
	return new_label

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

# -- Miniwidgets --------------------------
class CustomSpinButton(QtGui.QWidget):
	def __init__(self, button_text, init_values=(0., 100., 0., 1.), tooltip=(None, None), obj_name=(None, None)):
		super(CustomSpinButton, self).__init__()

		# - Init
		spb_min, spb_max, spb_value, spb_step = init_values

		# - Widgets
		self.button = QtGui.QPushButton(button_text)

		self.input = QtGui.QDoubleSpinBox()
		self.input.setMinimum(spb_min)
		self.input.setMaximum(spb_max)
		self.input.setValue(spb_value)
		self.input.setSingleStep(spb_step)

		if len(tooltip) == 2:
			if tooltip[0] is not None:
				self.input.setToolTip(tooltip[0])

			if tooltip[1] is not None:
				self.button.setToolTip(tooltip[1])

		if len(obj_name) == 2:
			if obj_name[0] is not None:
				self.input.setObjectName(obj_name[0])

			if obj_name[1] is not None:
				self.button.setObjectName(obj_name[1])

		# - Layout
		self.box = QtGui.QHBoxLayout()
		self.box.addWidget(self.input)
		self.box.addWidget(self.button)
		self.setLayout(self.box)

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

		# - Combos 
		self.rad_or = QtGui.QRadioButton('ORG')
		self.rad_bl = QtGui.QRadioButton('BL')
		self.rad_tl = QtGui.QRadioButton('TL')
		self.rad_br = QtGui.QRadioButton('BR')
		self.rad_tr = QtGui.QRadioButton('TR')
		self.rad_ce = QtGui.QRadioButton('CEN')

		# - Spinboxes
		self.spb_scale_x = QtGui.QSpinBox()
		self.spb_scale_y = QtGui.QSpinBox()
		self.spb_translate_x = QtGui.QSpinBox()
		self.spb_translate_y = QtGui.QSpinBox()
		self.spb_shear = QtGui.QSpinBox()
		self.spb_rotate = QtGui.QSpinBox()

		self.spb_scale_x.setMinimum(-999)
		self.spb_scale_y.setMinimum(-999)
		self.spb_translate_x.setMinimum(-9999)
		self.spb_translate_y.setMinimum(-9999)
		self.spb_shear.setMinimum(-90)
		self.spb_rotate.setMinimum(-360)

		self.spb_scale_x.setMaximum(999)
		self.spb_scale_y.setMaximum(999)
		self.spb_translate_x.setMaximum(9999)
		self.spb_translate_y.setMaximum(9999)
		self.spb_shear.setMaximum(90)
		self.spb_rotate.setMaximum(360)

		self.reset()

		# - Build
		self.lay_controls = QtGui.QGridLayout()
		self.lay_controls.addWidget(QtGui.QLabel('Scale X:'),			0, 0, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Scale Y:'),			0, 1, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Trans. X:'),			0, 2, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Trans. Y:'),			0, 3, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Shear:'),				0, 4, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Rotate:'),			0, 5, 1, 1)
		self.lay_controls.addWidget(self.spb_scale_x,					1, 0, 1, 1)
		self.lay_controls.addWidget(self.spb_scale_y,					1, 1, 1, 1)
		self.lay_controls.addWidget(self.spb_translate_x,				1, 2, 1, 1)
		self.lay_controls.addWidget(self.spb_translate_y,				1, 3, 1, 1)
		self.lay_controls.addWidget(self.spb_shear,						1, 4, 1, 1)
		self.lay_controls.addWidget(self.spb_rotate,					1, 5, 1, 1)
		self.lay_controls.addWidget(self.rad_or,						2, 0, 1, 1)
		self.lay_controls.addWidget(self.rad_bl,						2, 1, 1, 1)
		self.lay_controls.addWidget(self.rad_tl,						2, 2, 1, 1)
		self.lay_controls.addWidget(self.rad_br,						2, 3, 1, 1)
		self.lay_controls.addWidget(self.rad_tr,						2, 4, 1, 1)
		self.lay_controls.addWidget(self.rad_ce,						2, 5, 1, 2)
				
		self.setLayout(self.lay_controls)
		
	def reset(self):
		self.spb_scale_x.setValue(100)
		self.spb_scale_y.setValue(100)
		self.spb_translate_x.setValue(0)
		self.spb_translate_y.setValue(0)
		self.spb_shear.setValue(0)
		self.spb_rotate.setValue(0)
		self.rad_or.setChecked(True)

	def getTransform(self, obj_rect=QtCore.QRectF(.0, .0, .0, .0)):
		# - Init
		origin_transform = QtGui.QTransform()
		rev_origin_transform = QtGui.QTransform()
		return_transform = QtGui.QTransform()
		
		m11 = float(self.spb_scale_x.value)/100.
		m13 = float(self.spb_translate_x.value)
		m22 = float(self.spb_scale_y.value)/100.
		m23 = float(self.spb_translate_y.value)

		# - Transform
		if self.rad_or.isChecked():	transform_origin = QtCore.QPointF(.0, .0)
		if self.rad_bl.isChecked():	transform_origin = obj_rect.topLeft()
		if self.rad_br.isChecked():	transform_origin = obj_rect.topRight()
		if self.rad_tl.isChecked():	transform_origin = obj_rect.bottomLeft()
		if self.rad_tr.isChecked():	transform_origin = obj_rect.bottomRight()
		if self.rad_ce.isChecked():	transform_origin = obj_rect.center()
		
		origin_transform.translate(-transform_origin.x(), -transform_origin.y())
		rev_origin_transform.translate(transform_origin.x(), transform_origin.y())

		return_transform.scale(m11, m22)
		return_transform.rotate(-float(self.spb_rotate.value))
		return_transform.shear(radians(float(self.spb_shear.value)), 0.)
		return_transform.translate(m13, m23)

		return return_transform, origin_transform, rev_origin_transform

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
	def __init__(self, data):
		super(TRCheckTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
	
		# - Set 
		self.setTable(data)		
	
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
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-bottom: 10px;
				padding: 5px 7px 4px 7px; 
				margin-right: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')

class TRVTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		self.setUsesScrollButtons(True)
		self.setTabPosition(QtGui.QTabWidget.East)
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-left: 11px;
				padding: 5px 4px 5px 5px; 
				margin-bottom: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')

# - Layouts ----------------------------------------
'''
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
		return self.doLayout(QRect(0, 0, width, 0), True)

	def hasWidthForHeight(self):
		return self.orientation == QtCore.Qt.Vertical

	def widthForHeight(self, height):
		return self.doLayout(QRect(0, 0, 0, height), True)

	def setGeometry(self, rect):
		super().setGeometry(rect)
		self.doLayout(rect, False)

	def sizeHint(self):
		return self.minimumSize()

	def minimumSize(self):
		size = QtCore.QSize()

		for item in self.itemList:
			size = size.expandedTo(item.minimumSize())

		margin, _, _, _ = self.getContentsMargins()

		size += QtCore.QSize(2 * margin, 2 * margin)
		return size

	def doLayout(self, rect, testOnly):
		x = rect.x()
		y = rect.y()
		lineHeight = columnWidth = heightForWidth = 0

		for item in self.itemList:
			wid = item.widget()
			spaceX = self.spacing() + wid.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
			spaceY = self.spacing() + wid.style().layoutSpacing(QtGui.QSizePolicy.PushButton, QtGui.QSizePolicy.PushButton, QtCore.Qt.Vertical)
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
'''