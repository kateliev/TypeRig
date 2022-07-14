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
from typerig.proxy.fl.gui.dialogs import TRMsgSimple, TR2FieldDLG, TRColorDLG

# - Init --------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Modify Layers', '1.53'

# -- Inital config for Get Layers dialog
column_names = ('Name', 'Type', 'Color')
column_init = (None, None, QtGui.QColor(0, 255, 0, 10))
init_table_dict = {1 : OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 10),
			  'Service': QtGui.QColor(0, 0, 255, 10),
			  'Mask': QtGui.QColor(255, 0, 0, 10),
			  'Any': QtGui.QColor(255, 255, 255, 0)}

# - Functions ----------------------------------------------------------------
def check_type(layer):
	if layer.isMaskLayer: 	return 'Mask'
	if layer.isMasterLayer: return 'Master'
	if layer.isService: 	return 'Service'

# - Actions ------------------------------------------------------------------
class TRLayerActionCollector(object):
	''' Collection of all layer based tools'''

	# - Layer: Basic tools ---------------------------------------------------
	@staticmethod
	def layer_toggle_visible(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		do_update = False

		for glyph in glyphs_source:
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue

				# - Process
				wLayer.isVisible = not wLayer.isVisible
				do_update = True

			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Toggle Visibility | Glyph: {} Layers: {}.'.format(glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Toggle Visibility | Glyphs: {} Layers: {}.'.format(len(glyphs_source), len(process_layers)))
		
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
				glyph.updateObject(glyph.fl, 'Add Layer | Glyph: {} Layers: {}.'.format(glyph.name, user_input))

		# - Finish
		if pMode == 3 or len(glyphs_source) > 5:
			parent.font.updateObject(parent.font.fl, 'Add Layer | Glyphs: {} Layers: {}.'.format(len(glyphs_source), user_input))
		
		parent.refresh()

	@staticmethod
	def layer_duplicate(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		do_update = False
		
		# - Ask user about rename pattern
		user_input = TR2FieldDLG('Duplicate Layer', 'Please enter prefix and/or suffix for duplicate layers', 'Prefix:', 'Suffix:').values
		layer_prefix = user_input[0]
		layer_suffux = user_input[1]

		# - Process
		for glyph in glyphs_source:	
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue

				# - Duplicate 
				glyph.duplicateLayer(layer_name , '{1}{0}{2}'.format(layer_name, layer_prefix, layer_suffux))
				do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Duplicate Layer | Glyph: {} Layers: {}.'.format(glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Duplicate Layer | Glyphs: {} Layers: {}.'.format(len(glyphs_source), len(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_duplicate_mask(parent):	
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		do_update = False

		# - Process
		for glyph in glyphs_source:	
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue
				
				# - Build mask layer
				srcShapes = glyph.shapes(layer_name)
				newMaskLayer = wLayer.getMaskLayer(True)			

				# - Copy shapes to mask layer
				for shape in srcShapes:
					newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!

				do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Duplicate to Mask | Glyph: {} Layers: {}.'.format(glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Duplicate to Mask | Glyphs: {} Layers: {}.'.format(len(glyphs_source), len(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_delete(parent):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		do_update = False

		# - Process
		for glyph in glyphs_source:			
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue

				# - Process
				glyph.removeLayer(layer_name)
				do_update = True
			
			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Remove Layer | Glyph: {} Layers: {}.'.format(glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Remove Layer | Glyphs: {} Layers: {}.'.format(len(glyphs_source), len(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_set_type(parent, type):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		do_update = False

		# - Process
		for glyph in glyphs_source:		
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue

				# - Process
				if type == 'Service': wLayer.isService = not wLayer.isService
				if type == 'Wireframe': wLayer.isWireframe = not wLayer.isWireframe
				do_update = True

			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Set Layer Type | Glyph: {} Layers: {}.'.format(glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Set Layer Type  | Glyphs: {} Layers: {}.'.format(len(glyphs_source), len(process_layers)))
		
		parent.refresh()

	@staticmethod
	def layer_set_color(parent):
		# - Init
		glyphs_source = getProcessGlyphs(mode=pMode)
		process_layers = parent.lst_layers.getTable(parent.chk_names.isChecked(), parent.chk_type.isChecked(), parent.chk_color.isChecked())
		user_input = TRColorDLG('Pick layer color', 'Please select a new layer color.').values
		if not user_input: return
		do_update = False

		# - Process
		for glyph in glyphs_source:		
			for layer_name, layer_type, layer_color in process_layers:
				wLayer = glyph.layer(layer_name)
				
				# - Precision
				if wLayer is None: continue
				if layer_type is not None and layer_type != check_type(wLayer): continue
				if layer_color is not None and layer_color != wLayer.wireframeColor.name(): continue

				# - Process
				wLayer.wireframeColor = user_input[1]
				do_update = True

			if do_update and pMode != 3 and len(glyphs_source) <= 5:
				glyph.updateObject(glyph.fl, 'Set Layer Color: {} | Glyph: {} Layers: {}.'.format(user_input[0], glyph.name, len(process_layers)))

		# - Finish
		if do_update and (pMode == 3 or len(glyphs_source) > 5):
			parent.font.updateObject(parent.font.fl, 'Set Layer Color: {} | Glyphs: {} Layers: {}.'.format(user_input[0], len(glyphs_source), len(process_layers)))
		
		parent.refresh()

# - Sub widgets ------------------------
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
		for row, layer in enumerate(data.keys()):
			name_row.append(layer)

			for column, key in enumerate(data[layer].keys()):
				
				# -- Build name column
				name_column.append(key)
				
				# -- Selectively add data
				newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
				
				if column == 0:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setData(QtCore.Qt.DecorationRole, QtGui.QColor(data[layer]['Color']))
					newitem.setCheckState(QtCore.Qt.Unchecked) 

				newitem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

				if data[layer]['Type']: newitem.setBackground(color_dict[data[layer]['Type']])

				self.setItem(row, column, newitem)

		self.verticalHeader().hide()
		self.setVerticalHeaderLabels(name_row)
		self.setHorizontalHeaderLabels(name_column)
		
		self.header.setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		self.header.setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)
		self.header.setSectionResizeMode(2, QtGui.QHeaderView.ResizeToContents)

		self.blockSignals(False)
		self.setSortingEnabled(True)
		self.setColumnHidden(2, True)
	
	def getTable(self, get_name=True, get_type=False, get_color=False):
		table_data = []
		for row in range(self.rowCount):
			if self.item(row, 0).checkState() == QtCore.Qt.Checked:
				layer_name = self.item(row, 0).text() if get_name else None
				layer_type = self.item(row, 1).text() if get_type else None
				layer_color = self.item(row, 2).text() if get_color else None

				table_data.append((layer_name, layer_type, layer_color))

		return table_data

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

		# - Checks
		self.chk_names = QtGui.QCheckBox('Name')
		self.chk_type = QtGui.QCheckBox('Type')
		self.chk_color = QtGui.QCheckBox('Color')
		self.chk_names.setChecked(True)
		self.chk_names.setEnabled(False)

		# -- Head
		self.lay_head = QtGui.QGridLayout()
		self.lay_head.addWidget(QtGui.QLabel('Source:'),		1, 0, 1, 1)
		self.lay_head.addWidget(self.rad_selection,				1, 1, 1, 1)
		self.lay_head.addWidget(self.rad_font,					1, 2, 1, 1)
		self.lay_head.addWidget(self.btn_refresh,				1, 3, 1, 1)
		self.lay_head.addWidget(QtGui.QLabel('Precision:'),		2, 0, 1, 1)
		self.lay_head.addWidget(self.chk_names,					2, 1, 1, 1)
		self.lay_head.addWidget(self.chk_type,					2, 2, 1, 1)
		self.lay_head.addWidget(self.chk_color,					2, 3, 1, 1)
		self.addLayout(self.lay_head)

		# -- Layer List
		self.lst_layers = TRWMasterTableView(init_table_dict)
		self.lst_layers.selectionModel().selectionChanged.connect(self.set_selected)
		self.addWidget(self.lst_layers)
		self.refresh()

	# - Basics ---------------------------------------
	def refresh(self):
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
				glyph_data = []
				for layer in glyph.layers():
					if '#' not in layer.name:
						layer_name = layer.name if self.chk_names.isChecked() else 'Any'
						layer_type = check_type(layer) if self.chk_type.isChecked() else 'Any'
						layer_color = layer.wireframeColor.name() if self.chk_color.isChecked() else 'lightgray'
						glyph_data.append((layer_name, layer_type, layer_color))
				
				init_data += glyph_data 
			
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
		self.act_layer_color = QtGui.QAction('Change Color', self)
		#self.act_layer_color_new = ColorAction(self)
			

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
		self.act_layer_color.triggered.connect(lambda: TRLayerActionCollector.layer_set_color(self.layerSelector))
		
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
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_delete)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_visible)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_color)
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