#FLM: TypeRig: Modify Layers
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2021 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import os, warnings
from math import radians
from collections import OrderedDict
from itertools import groupby

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import *

# - Init --------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Modify Layers', '1.30'

# -- Inital config for Get Layers dialog
column_names = ('Name', 'Type', 'Color')
column_init = (None, None, QtGui.QColor(0, 255, 0, 10))
init_table_dict = {1 : OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 10), 'Service': QtGui.QColor(0, 0, 255, 10), 'Mask': QtGui.QColor(255, 0, 0, 10)}

# - Actions ------------------------------------------------------------------
class TRLayerActionCollector(object):
	''' Collection of all layer based tools'''

	# - Layer: Basic tools ---------------------------------------------------
	@staticmethod
	def layer_toggle_visible(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		do_update = False

		for glyph in glyphs_source:
			for layer_name in process_layers:
				if glyph.layer(layer_name) is not None:
					glyph.layer(layer_name).isVisible = not glyph.layer(layer_name).isVisible
					do_update = True

			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Toggle Visibility | Glyph: {} Layer: {}.'.format(glyph.name, '; '.join(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Toggle Visibility | Glyphs: {} Layer: {}.'.format(len(glyphs_source), '; '.join(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_add(parent):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		user_input = TR1FieldDLG('Add new layer ', 'Please enter a name for the layer created.', 'Name:').values

		# - Process
		for glyph in glyphs_source:
			newLayer = fl6.flLayer()
			newLayer.name = str(user_input)
			glyph.addLayer(newLayer)
			
			if pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Add Layer | Glyph: {} Layer: {}.'.format(glyph.name, user_input))

		# - Finish
		if pMode == 3 or len(glyphs_source) > 5:
			parent.font.updateObject(parent.font.fl, 'Add Layer | Glyphs: {} Layer: {}.'.format(len(glyphs_source), user_input))
		
		parent.refresh()

	@staticmethod
	def layer_duplicate(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		do_update = False
		
		# - Ask user about rename pattern
		user_input = TR2FieldDLG('Duplicate Layer', 'Please enter prefix and/or suffix for duplicate layers', 'Prefix:', 'Suffix:').values
		layer_prefix = user_input[0]
		layer_suffux = user_input[1]

		# - Process
		for glyph in glyphs_source:	
			# - Duplicate 
			for layer_name in process_layers:
				if glyph.layer(layer_name) is not None: 
					glyph.duplicateLayer(layer_name , '{1}{0}{2}'.format(layer_name, layer_prefix, layer_suffux))
					do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Duplicate Layer | Glyph: {} Layer: {}.'.format(glyph.name, '; '.join(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Duplicate Layer | Glyphs: {} Layer: {}.'.format(len(glyphs_source), '; '.join(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_duplicate_mask(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		do_update = False

		# - Process
		for glyph in glyphs_source:	
			for layer_name in process_layers:
				if glyph.layer(layer_name) is not None:
					# - Build mask layer
					srcShapes = glyph.shapes(layer_name)
					newMaskLayer = glyph.layer(layer_name).getMaskLayer(True)			

					# - Copy shapes to mask layer
					for shape in srcShapes:
						newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!

					do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Duplicate to Mask | Glyph: {} Layer: {}.'.format(glyph.name, '; '.join(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Duplicate to Mask | Glyphs: {} Layer: {}.'.format(len(glyphs_source), '; '.join(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_delete(parent):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		do_update = False

		# - Process
		for glyph in glyphs_source:			
			for layer_name in process_layers:
				if glyph.layer(layer_name) is not None:
					glyph.removeLayer(layer_name)
					do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Remove Layer | Glyph: {} Layer: {}.'.format(glyph.name, '; '.join(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Remove Layer | Glyphs: {} Layer: {}.'.format(len(glyphs_source), '; '.join(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_set_type(parent, type):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable()
		do_update = False

		# - Process
		for glyph in glyphs_source:		
			for layer_name in process_layers:
				wLayer = glyph.layer(layer_name)

				if wLayer is not None:
					if type is 'Service': wLayer.isService = not wLayer.isService
					if type is 'Wireframe': wLayer.isWireframe = not wLayer.isWireframe
					do_update = True

			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Set Layer Type | Glyph: {} Layer: {}.'.format(glyph.name, '; '.join(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Set Layer Type  | Glyphs: {} Layer: {}.'.format(len(glyphs_source), '; '.join(process_layers)))
		
		parent.refresh()

# - Sub widgets ------------------------
class TRWLayerSelect(QtGui.QVBoxLayout):
	def __init__(self):
		super(TRWLayerSelect, self).__init__()

		# - Init
		self.font = None

		# - Buttons
		self.btn_refresh = QtGui.QPushButton('Refresh')
		self.btn_refresh.clicked.connect(lambda: self.refresh())

		# - Radios
		self.rad_selection = QtGui.QRadioButton('Selection')
		self.rad_font = QtGui.QRadioButton('Font')
		
		self.rad_selection.setChecked(True)

		# -- Head
		self.lay_head = QtGui.QHBoxLayout()
		self.lay_head.addWidget(QtGui.QLabel('Source:'))
		self.lay_head.addWidget(self.rad_selection)
		self.lay_head.addWidget(self.rad_font)
		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)

		# -- Layer List
		self.lst_layers = TRWMasterTableView(init_table_dict)
		self.lst_layers.selectionModel().selectionChanged.connect(self.set_selected)
		self.addWidget(self.lst_layers)
		self.refresh()

	# - Basics ---------------------------------------
	def refresh(self):
		def check_type(layer):
			if layer.isMaskLayer: 	return 'Mask'
			if layer.isMasterLayer: return 'Master'
			if layer.isService: 	return 'Service'
		
		# - Set work mode
		global pMode
		if self.rad_selection.isChecked(): pMode = 2
		if self.rad_font.isChecked(): pMode = 3

		# - Populate table
		if fl6.CurrentFont() is not None:
			self.font = pFont()
			glyphs_source = getProcessGlyphs(mode=pMode)
			init_data = []

			for glyph in glyphs_source:
				init_data += [(layer.name, check_type(layer), layer.wireframeColor.name()) for layer in glyph.layers() if '#' not in layer.name]
		 	
		 	filter_data = set(init_data)
		 	table_dict = {n : OrderedDict(zip(column_names, data)) for n, data in enumerate(filter_data)}
		 	
		 	self.lst_layers.setTable(table_dict)

	def set_selected(self):
		selected_rows = [si.row() for si in self.lst_layers.selectionModel().selectedRows()]
		
		for row in range(self.lst_layers.rowCount):
			if row in selected_rows:
				self.lst_layers.item(row,0).setCheckState(QtCore.Qt.Checked)
			else:
				self.lst_layers.item(row,0).setCheckState(QtCore.Qt.Unchecked)
	
class TRWMasterTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRWMasterTableView, self).__init__()
		#self.setMaximumHeight(600)
		#self.setMinimumHeight(400)
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
		self.header = self.horizontalHeader()

		# - Set 
		self.setTable(data)		
	
		# - Styling
		self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)

	def setTable(self, data):
		# - Fix sorting
		self.clear()
		self.setSortingEnabled(False)
		self.blockSignals(True)
		self.model().sort(-1)
		self.horizontalHeader().setSortIndicator(-1, 0)

		# - Init
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
				
				if m == 0:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setData(QtCore.Qt.DecorationRole, QtGui.QColor(data[layer]['Color']))
					newitem.setCheckState(QtCore.Qt.Unchecked) 

				newitem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

				if data[layer]['Type']: newitem.setBackground(color_dict[data[layer]['Type']])

				self.setItem(n, m, newitem)

		self.verticalHeader().hide()
		self.setVerticalHeaderLabels(name_row)
		self.setHorizontalHeaderLabels(name_column)
		
		self.header.setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		self.header.setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)
		self.header.setSectionResizeMode(2, QtGui.QHeaderView.ResizeToContents)

		self.blockSignals(False)
		self.setSortingEnabled(True)
		self.setColumnHidden(2, True)
	
	def getTable(self):
		return [self.item(row, 0).text() for row in range(self.rowCount) if self.item(row, 0).checkState() == QtCore.Qt.Checked]

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	
	def __init__(self):
		super(tool_tab, self).__init__()

		# -- Layout and widgets -----------------------------------
		layoutV = QtGui.QVBoxLayout()

		self.layerSelector = TRWLayerSelect()
		layoutV.addLayout(self.layerSelector)
		
		# -- Menus and Actions -----------------------------------
		self.act_layer_add = QtGui.QAction('New', self)
		self.act_layer_duplicate = QtGui.QAction('Duplicate', self)
		self.act_layer_duplicate_mask = QtGui.QAction('Duplicate to Mask', self)
		self.act_layer_delete = QtGui.QAction('Remove', self)
		self.act_layer_visible = QtGui.QAction('Toggle Visible', self)

		self.menu_layer_type = QtGui.QMenu('Type', self)
		act_layer_set_type_wireframe = QtGui.QAction('Set as Wireframe', self)
		act_layer_set_type_service = QtGui.QAction('Set as Service', self)

		self.menu_layer_type.addAction(act_layer_set_type_wireframe)
		self.menu_layer_type.addAction(act_layer_set_type_service)
		self.menu_layer_type.addAction(act_layer_set_type_service)

		# -- Set Triggers ------------------------------------
		self.act_layer_add.triggered.connect(lambda: TRLayerActionCollector.layer_add(self.layerSelector))
		self.act_layer_duplicate.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate(self.layerSelector))
		self.act_layer_duplicate_mask.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate_mask(self.layerSelector))
		self.act_layer_delete.triggered.connect(lambda: TRLayerActionCollector.layer_delete(self.layerSelector))
		self.act_layer_visible.triggered.connect(lambda: TRLayerActionCollector.layer_toggle_visible(self.layerSelector))
		
		act_layer_set_type_wireframe.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Wireframe'))
		act_layer_set_type_service.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Service'))
		
		# - Build ----------------------------------------
		scriptDir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())
		
	# - Menus -------------------------------------------
	def contextMenuEvent(self, event):
		# - Init
		self.layerSelector.lst_layers.menu = QtGui.QMenu(self)
		self.layerSelector.lst_layers.menu.setTitle('Actions:')
		
		# - Build menus
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_add)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_duplicate)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_duplicate_mask)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_visible)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_delete)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_type)

		self.layerSelector.lst_layers.menu.popup(QtGui.QCursor.pos())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 700)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()