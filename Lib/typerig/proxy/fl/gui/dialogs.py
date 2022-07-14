# MODULE: Typerig / Proxy / FontLab / GUI / Dialogs
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2022 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import os
import fontlab as fl6

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import TRCheckTableView, TRSliderCtrl

# - Init ----------------------------------
__version__ = '0.1.2'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# -- Messages -------------------------------------------------------------------
class TRMsgSimple(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(TRMsgSimple, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

# -- Dialogs ---------------------------------------------------------------------
class TR1FieldDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_size=(300, 300, 300, 100)):
		super(TR1FieldDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.edt_field_t = QtGui.QLineEdit() # Top field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		2, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	2, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = self.edt_field_t.text

class TR2FieldDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_field_b, dlg_size=(300, 300, 300, 100)):
		super(TR2FieldDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.lbl_field_b = QtGui.QLabel(dlg_field_b)
		
		self.edt_field_t = QtGui.QLineEdit() # Top field
		self.edt_field_b = QtGui.QLineEdit() # Bottom field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.lbl_field_b,	2, 0, 1, 2)
		main_layout.addWidget(self.edt_field_b,	2, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = (self.edt_field_t.text, self.edt_field_b.text)

class TR1SliderDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_init_values=(0., 100., 50., 1.), dlg_size=(300, 300, 300, 100)):
		super(TR1SliderDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.sld_variable_t = TRSliderCtrl(*dlg_init_values) # Top field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 		0, 0, 1, 4)
		main_layout.addLayout(self.sld_variable_t,	1, 0, 1, 4)
		main_layout.addWidget(self.btn_ok,			2, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,		2, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = self.sld_variable_t.value

class TR2ComboDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_field_b, dlg_field_b_items, dlg_size=(300, 300, 300, 100)):
		super(TR2ComboDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.lbl_field_b = QtGui.QLabel(dlg_field_b)
		
		self.edt_field_t = QtGui.QLineEdit() # Top field
		self.cmb_field_b = QtGui.QComboBox() # Bottom Combo Box
		self.cmb_field_b.addItems(dlg_field_b_items)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.lbl_field_b,	2, 0, 1, 2)
		main_layout.addWidget(self.cmb_field_b,	2, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = (self.edt_field_t.text, self.cmb_field_b.currentIndex)

class TRColorDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_size=(300, 300, 300, 100)):
		super(TRColorDLG, self).__init__()
		
		# - Init
		from typerig.proxy.fl.gui.widgets import fontMarkColors
		self.values = (None, None)
		self.color_codes = {name:value for name, discard, value in fontMarkColors}
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_color = QtGui.QLabel('\nColor Presets:')
		
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, discard, value in fontMarkColors}
		
		for i in range(len(fontMarkColors)):
			self.cmb_select_color.addItem(fontMarkColors[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 			0, 0, 1, 4)
		main_layout.addWidget(self.lbl_color, 			1, 0, 1, 4)
		main_layout.addWidget(self.cmb_select_color,	2, 0, 1, 4)
		main_layout.addWidget(self.btn_ok,				3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,			3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		selection_name = self.color_codes[self.cmb_select_color.currentText]
		self.values = (selection_name,  QtGui.QColor(selection_name))

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