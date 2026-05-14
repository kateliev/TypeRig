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
import json
import fontlab as fl6

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import TRCheckTableView, TRSliderCtrl, CustomPushButton, CustomLabel, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init ----------------------------------
__version__ = '0.1.6'

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

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
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

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
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

class TR1SpinDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_init_values=(0., 100., 0., 1.), dlg_size=(300, 300, 300, 100)):
		super(TR1SpinDLG, self).__init__()
		# - Init
		self.values = None
		spb_min, spb_max, spb_value, spb_step = dlg_init_values
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.spb_value = QtGui.QDoubleSpinBox()
		self.spb_value.setMinimum(spb_min)
		self.spb_value.setMaximum(spb_max)
		self.spb_value.setValue(spb_value)
		self.spb_value.setSingleStep(spb_step)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.spb_value,	1, 2, 1, 2)
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
		self.values = self.spb_value.value

class TRNSpinDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_fields_dict={'Value 01':(0., 100., 0., 1.)}, dlg_size=(300, 300, 300, 100)):
		super(TRNSpinDLG, self).__init__()
		# - Init
		self.values = None
		self.fields = []
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
		# - Build 
		# -- Main layout
		main_layout = QtGui.QVBoxLayout() 
		main_layout.addWidget(self.lbl_main)

		# -- Auto layout
		for new_field_label, dlg_init_values in dlg_fields_dict.items():
			# --- Init
			spb_min, spb_max, spb_value, spb_step = dlg_init_values
			temp_layout = QtGui.QHBoxLayout()

			# --- Add
			lbl_field = QtGui.QLabel(new_field_label)
			spb_temp = QtGui.QDoubleSpinBox()
			spb_temp.setMinimum(spb_min)
			spb_temp.setMaximum(spb_max)
			spb_temp.setValue(spb_value)
			spb_temp.setSingleStep(spb_step)
			temp_layout.addWidget(lbl_field)
			temp_layout.addWidget(spb_temp)
			
			main_layout.addLayout(temp_layout)
			self.fields.append(spb_temp)

		# - Ok/Cancel
		end_layout = QtGui.QHBoxLayout()
		end_layout.addWidget(self.btn_ok)
		end_layout.addWidget(self.btn_cancel)
		main_layout.addLayout(end_layout)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = [spin.value for spin in self.fields]

class TR1SliderDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_init_values=(0., 100., 50., 1.), dlg_size=(300, 300, 300, 100)):
		super(TR1SliderDLG, self).__init__()
		# - Init
		self.values = None
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.sld_variable_t = TRSliderCtrl(*dlg_init_values) # Top field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
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
		self.values = self.sld_variable_t.sld_axis.value

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

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
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

		self.btn_ok.clicked.connect(lambda: self.return_values())
		self.btn_cancel.clicked.connect(lambda: self.reject())
		
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
			if layer_type is None or self.tab_masters.item(row,1).text() == layer_type:
				if modifiers == QtCore.Qt.AltModifier or do_swap: # Toggle state
					if self.tab_masters.item(row, 0).checkState() == QtCore.Qt.Checked:
						self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Unchecked)
					else:
						self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Checked)		

				elif modifiers == QtCore.Qt.ShiftModifier: # Uncheck all
					if not self.tab_masters.isRowHidden(row):
						self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Unchecked)								

				else: # Check all
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

class TRLayerSelectNEW(QtGui.QDialog):
	def __init__(self, parent, mode, font=None, glyph=None):
		super(TRLayerSelectNEW, self).__init__()
	
		# - Init
		self.parent_widget = parent
		self.column_names = ('Layer Name', 'Layer Type')
		self.color_dict = {'Master': QtGui.QColor(0, 255, 0, 20), 'Service': QtGui.QColor(0, 0, 255, 20), 'Mask': QtGui.QColor(255, 0, 0, 20)}
		column_init = (None, None)
		table_dict = {1:OrderedDict(zip(self.column_names, column_init))}
		
		# - Basic Widgets
		box_head = QtGui.QGroupBox()
		box_head.setObjectName('box_group')

		lay_main = QtGui.QVBoxLayout()
		
		lay_head = QtGui.QVBoxLayout() 
		lay_head.setContentsMargins(0, 0, 0, 0)
		
		lay_actions = QtGui.QHBoxLayout() 
		lay_actions.setContentsMargins(0, 0, 0, 0)
		
		lay_search = QtGui.QHBoxLayout() 
		lay_search.setContentsMargins(0, 0, 0, 0)
	
		# - Search Box
		self.edt_search_field = QtGui.QLineEdit()
		self.edt_search_field.setPlaceholderText('Filter: Layer Name')
		self.edt_search_field.textChanged.connect(self.table_filter)
		self.btn_search_field = CustomPushButton("close", tooltip='Clear search', obj_name='btn_panel')
		self.btn_search_field.clicked.connect(lambda: self.edt_search_field.setText(''))

		# -- Layer Buttons
		self.btn_tableCheck = CustomPushButton("select_all", tooltip='Select all\n<Shift> + Click deselect all.', obj_name='btn_panel')
		self.btn_tableSwap = CustomPushButton("select_swap", tooltip='Swap selection', obj_name='btn_panel')
		self.btn_tableCheckMasters = CustomPushButton("layer_master", tooltip='Master layers\n<Shift> + Click deselect all.', obj_name='btn_panel')
		self.btn_tableCheckMasks = CustomPushButton("layer_mask", tooltip='Mask layers\n<Shift> + Click deselect all.', obj_name='btn_panel')
		self.btn_tableCheckServices = CustomPushButton("layer_service", tooltip='Service layers\n<Shift> + Click deselect all.', obj_name='btn_panel')
		self.btn_table_refresh = CustomPushButton("refresh", tooltip='Refresh layer list', obj_name='btn_panel')
		
		self.btn_tableCheck.clicked.connect(lambda: self.table_check_all())
		self.btn_tableSwap.clicked.connect(lambda: self.table_check_all(do_swap=True))
		self.btn_tableCheckMasters.clicked.connect(lambda: self.table_check_all('Master'))
		self.btn_tableCheckMasks.clicked.connect(lambda: self.table_check_all('Mask'))
		self.btn_tableCheckServices.clicked.connect(lambda: self.table_check_all('Service'))
		self.btn_table_refresh.clicked.connect(lambda: self.table_populate(0))

		# -- Table 
		self.tab_masters = TRCheckTableView(table_dict)
		self.tab_masters.verticalHeader().hide()
		self.table_populate(mode, font, glyph)
		self.tab_masters.cellChanged.connect(lambda: self.parent_widget.layers_refresh())

		# - Build layout
		lay_actions.addWidget(self.btn_tableCheck) 	
		lay_actions.addWidget(self.btn_tableSwap) 		
		lay_actions.addWidget(self.btn_tableCheckMasters) 
		lay_actions.addWidget(self.btn_tableCheckMasks) 
		lay_actions.addWidget(self.btn_tableCheckServices)
		lay_actions.addStretch()
		lay_actions.addWidget(self.btn_table_refresh)
		
		lay_search.addWidget(CustomLabel('search', obj_name='lbl_panel'))
		lay_search.addWidget(self.edt_search_field)
		lay_search.addWidget(self.btn_search_field)

		lay_head.addLayout(lay_actions)
		lay_head.addLayout(lay_search)
		
		box_head.setLayout(lay_head)
		lay_main.addWidget(box_head)
		lay_main.addWidget(self.tab_masters)

		# - Set Widget
		self.setLayout(lay_main)
		self.setStyleSheet(css_tr_button)
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
			if layer_type is None or self.tab_masters.item(row,1).text() == layer_type:
				if modifiers == QtCore.Qt.AltModifier or do_swap: # Toggle state
					if self.tab_masters.item(row, 0).checkState() == QtCore.Qt.Checked:
						self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Unchecked)
					else:
						self.tab_masters.item(row, 0).setCheckState(QtCore.Qt.Checked)		

				elif modifiers == QtCore.Qt.ShiftModifier: # Uncheck all
					if not self.tab_masters.isRowHidden(row):
						self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Unchecked)								

				else: # Check all
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

# -- Universal per-master numeric value editor ----------------------------------
TR_LIB_KEY_PREFIX = 'com.typerig.'
TR_MASTER_VALUES_FORMAT = 'typerig.master_values/1'

class TRMasterValuesDLG(QtGui.QDialog):
	'''Universal dialog: one numeric value per font master, persisted in
	the font lib under a caller-supplied reverse-domain key, with JSON
	export/import.

	The dialog is intentionally generic so any panel/tool can reuse it for
	per-master snap targets, italic offsets, ink-trap depths, etc.

	Args:
		font          : pFont - required; provides masters list and packageLib I/O
		lib_key       : str   - required; full reverse-domain key (must start
		                with 'com.typerig.'), e.g.
		                'com.typerig.panel.node.tool.monoline'
		title         : str   - window title (default derived from lib_key)
		message       : str   - instruction text shown above the table
		value_label   : str   - header for the value column (default 'Value')
		value_type    : type  - float (default) or int
		value_default : float - shown for masters that have no entry yet
		value_range   : tuple - (min, max, step) for the spin editor
		autoload      : bool  - if True, load values from font lib on open
		size          : tuple - (x, y, w, h) initial geometry

	After exec_():
		self.values   : dict[str, float] | None - final values, None if cancelled
		self.changed  : bool - whether the user edited anything
	'''

	# Column indices for the 2-column table
	_COL_NAME  = 0
	_COL_VALUE = 1

	def __init__(self, font, lib_key,
	             title=None, message=None,
	             value_label='Value', value_type=float,
	             value_default=0.0, value_range=(-10000.0, 10000.0, 1.0),
	             autoload=True, size=(300, 300, 420, 360), parent=None):
		super(TRMasterValuesDLG, self).__init__(parent)

		# - Validate the key contract up front
		if not isinstance(lib_key, basestring) or not lib_key.startswith(TR_LIB_KEY_PREFIX):
			raise ValueError("TRMasterValuesDLG: lib_key must start with %r (got %r)"
			                 % (TR_LIB_KEY_PREFIX, lib_key))

		# - Init state
		self.tr_font          = font
		self.lib_key       = lib_key
		self.value_label   = value_label
		self.value_type    = value_type
		self.value_default = float(value_default)
		self.value_min, self.value_max, self.value_step = value_range
		self.values        = None     # final dict or None on cancel
		self.changed       = False
		self._initial_data = {}       # snapshot taken after first populate

		# Master ordering frozen at open-time; orphans appended below
		self.master_names = list(self.tr_font.masters())

		# - Widgets
		self.lbl_main = QtGui.QLabel(message or 'Set a value for each master:')
		self.lbl_main.setWordWrap(True)

		self.tbl = QtGui.QTableWidget(0, 2)
		self.tbl.setHorizontalHeaderLabels(['Master', self.value_label])
		self.tbl.horizontalHeader().setStretchLastSection(True)
		self.tbl.verticalHeader().setVisible(False)
		self.tbl.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.tbl.setEditTriggers(QtGui.QAbstractItemView.AllEditTriggers)
		self.tbl.itemChanged.connect(self._on_item_changed)

		self.btn_font_load = QtGui.QPushButton('Load from Font')
		self.btn_font_save = QtGui.QPushButton('Save to Font')
		self.btn_file_load = QtGui.QPushButton('Load from JSON')
		self.btn_file_save = QtGui.QPushButton('Save to JSON')
		self.btn_ok        = QtGui.QPushButton('OK')
		self.btn_cancel    = QtGui.QPushButton('Cancel')

		self.btn_font_load.clicked.connect(self._font_load)
		self.btn_font_save.clicked.connect(self._font_save)
		self.btn_file_load.clicked.connect(self._file_load)
		self.btn_file_save.clicked.connect(self._file_save)
		self.btn_ok.clicked.connect(self._on_ok)
		self.btn_cancel.clicked.connect(self.reject)

		# - Layout
		main = QtGui.QGridLayout()
		main.addWidget(self.lbl_main,      0, 0, 1, 4)
		main.addWidget(self.tbl,           1, 0, 1, 4)
		main.addWidget(self.btn_font_load, 2, 0, 1, 2)
		main.addWidget(self.btn_font_save, 2, 2, 1, 2)
		main.addWidget(self.btn_file_load, 3, 0, 1, 2)
		main.addWidget(self.btn_file_save, 3, 2, 1, 2)
		main.addWidget(self.btn_cancel,    4, 0, 1, 2)
		main.addWidget(self.btn_ok,        4, 2, 1, 2)
		self.setLayout(main)

		# - Populate. Always start with defaults; optionally overlay font lib.
		self._dict_to_table({})
		if autoload:
			loaded, present = self._read_font_lib()
			if present and loaded:
				self._dict_to_table(loaded)
		# Snapshot for the "changed" flag
		self._initial_data = self._table_to_dict()

		# - Window
		self.setWindowTitle(title or 'Master values - %s' % lib_key)
		self.setGeometry(*size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

	# -- Public helpers -----------------------------------------------------

	def get_values(self):
		'''Return current table contents as dict[master_name -> value].'''
		return self._table_to_dict()

	# -- Table <-> dict marshalling ----------------------------------------

	def _table_to_dict(self):
		out = {}
		for row in range(self.tbl.rowCount):
			name_item  = self.tbl.item(row, self._COL_NAME)
			value_item = self.tbl.item(row, self._COL_VALUE)
			if name_item is None or value_item is None:
				continue
			name = name_item.text
			try:
				v = float(value_item.text)
			except (TypeError, ValueError):
				continue
			if self.value_type is int:
				v = int(round(v))
			out[name] = v
		return out

	def _dict_to_table(self, data):
		'''Populate the table from a dict. Known masters first (in font order),
		orphan keys (in dict but not in font) appended in red.

		Uses pre-allocated row count + explicit indices so we don't rely on
		PythonQt's possibly-stale rowCount attribute mid-update.
		'''
		self.tbl.blockSignals(True)

		known = set(self.master_names)
		known_rows = [(name, data.get(name, self.value_default), False)
		              for name in self.master_names]
		orphan_rows = [(k, data[k], True)
		               for k in sorted(data.keys()) if k not in known]
		all_rows = known_rows + orphan_rows

		# Wipe existing rows first, then resize to the exact target.
		self.tbl.clearContents()
		self.tbl.setRowCount(0)
		self.tbl.setRowCount(len(all_rows))

		for row, (name, value, orphan) in enumerate(all_rows):
			self._set_row(row, name, value, orphan)

		self.tbl.blockSignals(False)

	def _set_row(self, row, master_name, value, orphan=False):
		name_item = QtGui.QTableWidgetItem(master_name)
		# Read-only name cell: enabled + selectable, but not editable.
		name_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

		if self.value_type is int:
			value_text = str(int(round(float(value))))
		else:
			value_text = '{:g}'.format(float(value))
		value_item = QtGui.QTableWidgetItem(value_text)

		if orphan:
			red = QtGui.QColor(255, 80, 80, 60)
			name_item.setBackground(red)
			value_item.setBackground(red)
			name_item.setToolTip('Orphan: master "%s" not present in current font.' % master_name)

		self.tbl.setItem(row, self._COL_NAME,  name_item)
		self.tbl.setItem(row, self._COL_VALUE, value_item)

	def _on_item_changed(self, item):
		# Validate numeric input; revert on bad value.
		if item.column != self._COL_VALUE:
			return
		try:
			float(item.text)
		except (TypeError, ValueError):
			self.tbl.blockSignals(True)
			item.setText('{:g}'.format(self.value_default))
			self.tbl.blockSignals(False)

	# -- Font lib I/O ------------------------------------------------------

	def _read_font_lib(self):
		'''Returns (data_dict, present_flag). data_dict is empty when the key
		is missing or malformed; present_flag distinguishes "no data yet"
		from "data exists but is empty".'''
		try:
			pkg_lib = self.tr_font.fl.packageLib
		except Exception as ex:
			QtGui.QMessageBox.warning(self, 'Font lib unavailable', str(ex))
			return {}, False

		# packageLib is a Qt-flavoured dict; key membership via try/except.
		try:
			data = pkg_lib[self.lib_key]
		except Exception:
			return {}, False

		if not isinstance(data, dict):
			return {}, False

		clean = {}
		for k, v in data.items():
			try:
				clean[str(k)] = float(v)
			except (TypeError, ValueError):
				continue
		return clean, True

	def _font_load(self):
		data, present = self._read_font_lib()
		if not present:
			QtGui.QMessageBox.information(
				self, 'Load from Font',
				'No data found in font lib under key:\n%s' % self.lib_key)
			return
		self._dict_to_table(data)

	def _font_save(self):
		# Mirror Delta: read-modify-write the whole packageLib dict.
		data = self._table_to_dict()
		
		pkg_lib = self.tr_font.fl.packageLib
		# packageLib values must be plain Python types. Force-cast.
		pkg_lib[self.lib_key] = {str(k): float(v) for k, v in data.items()}
		self.tr_font.fl.packageLib = pkg_lib
	
			
		QtGui.QMessageBox.information(
			self, 'Save to Font',
			'%d value(s) saved to font lib under key:\n%s'
			% (len(data), self.lib_key))

	# -- JSON file I/O -----------------------------------------------------

	def _default_dir(self):
		try:
			return os.path.split(self.tr_font.fg.path)[0]
		except Exception:
			return ''

	def _suggested_filename(self):
		# Strip the mandatory prefix for a friendlier default.
		stem = self.lib_key[len(TR_LIB_KEY_PREFIX):] if self.lib_key.startswith(TR_LIB_KEY_PREFIX) else self.lib_key
		return stem + '.json'

	def _file_save(self):
		default = os.path.join(self._default_dir(), self._suggested_filename())
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save master values to JSON', default, '*.json')
		if not fname:
			return
		payload = {
			'format': TR_MASTER_VALUES_FORMAT,
			'key':    self.lib_key,
			'values': self._table_to_dict(),
		}
		try:
			with open(fname, 'w') as f:
				json.dump(payload, f, indent='\t', sort_keys=True)
		except Exception as ex:
			QtGui.QMessageBox.warning(self, 'Save to JSON failed', str(ex))

	def _file_load(self):
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load master values from JSON', self._default_dir(), '*.json')
		if not fname:
			return
		try:
			with open(fname, 'r') as f:
				blob = json.load(f)
		except Exception as ex:
			QtGui.QMessageBox.warning(self, 'Load from JSON failed', str(ex))
			return

		# Accept either wrapped {format,key,values} or bare dict.
		if isinstance(blob, dict) and 'values' in blob and isinstance(blob['values'], dict):
			data = blob['values']
			loaded_key = blob.get('key')
			if loaded_key and loaded_key != self.lib_key:
				QtGui.QMessageBox.information(
					self, 'Key mismatch',
					'JSON was saved under key %r; loading into %r anyway.'
					% (loaded_key, self.lib_key))
		elif isinstance(blob, dict):
			data = blob
		else:
			QtGui.QMessageBox.warning(self, 'Load from JSON failed',
			                          'Unrecognized file shape (expected a dict).')
			return

		# Coerce values to float; ignore non-numeric entries.
		clean = {}
		for k, v in data.items():
			try:
				clean[str(k)] = float(v)
			except (TypeError, ValueError):
				continue
		self._dict_to_table(clean)

	# -- Result ------------------------------------------------------------

	def _on_ok(self):
		self.values = self._table_to_dict()
		self.changed = (self.values != self._initial_data)
		self.accept()

# - Test ----------------------
if __name__ == '__main__':
	#test_dialog_return = TR1SliderDLG('Insert Node', 'Set time along bezier curve')
	#test_dialog_return = TR1SpinDLG('Round corner', 'Set corner radius', 'Radius')
	test_dialog_return = TRNSpinDLG('Round corner', 'Set corner radius', {'Radius':(0.,100.,5.,1), 'Handle length %':(0.,100.,30.,1)})
	print(test_dialog_return.values)