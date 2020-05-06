#FLM: TR: Layers
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from math import radians
from collections import OrderedDict
from itertools import groupby

import fontlab as fl6
import fontgate as fgt

from typerig.proxy import *

from typerig.core.func.math import linInterp as lerp

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import getProcessGlyphs, TRSliderCtrl

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Layers', '1.28'

# -- Inital config for Get Layers dialog
column_names = ('Name', 'Type', 'Color')
column_init = (None, None, QtGui.QColor(0, 255, 0, 10))
init_table_dict = {1:OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 10), 'Service': QtGui.QColor(0, 0, 255, 10), 'Mask': QtGui.QColor(255, 0, 0, 10)}

# - Sub widgets ------------------------
class TRWLayerSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(TRWLayerSelect, self).__init__()

		# - Init
		self.glyph = None

		# -- Head
		self.lay_head = QtGui.QHBoxLayout()
		self.edt_glyphName = QtGui.QLineEdit()
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_refresh.clicked.connect(self.refresh)

		self.lay_head.addWidget(QtGui.QLabel('G:'))
		self.lay_head.addWidget(self.edt_glyphName)
		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)

		# -- Layer List
		self.lst_layers = TRWMasterTableView(init_table_dict)
		self.lst_layers.selectionModel().selectionChanged.connect(self.set_selected)
		self.addWidget(self.lst_layers)
		self.refresh()

	def refresh(self, master_mode=False):
		def check_type(layer):
			if layer.isMaskLayer: 	return 'Mask'
			if layer.isMasterLayer: return 'Master'
			if layer.isService: 	return 'Service'
		
		if fl6.CurrentFont() is not None and fl6.CurrentGlyph() is not None:
			self.glyph = eGlyph()
			self.edt_glyphName.setText(self.glyph.name)

			if master_mode:
				init_data = [(layer, 'Master', layer.wireframeColor) for layer in self.glyph.layers() if layer.isMasterLayer]
			else:
				init_data = [(layer.name, check_type(layer), layer.wireframeColor) for layer in self.glyph.layers() if '#' not in layer.name]
		 	
		 	table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in enumerate(init_data)}
		 	
		 	self.lst_layers.setTable(init_table_dict)
		 	self.lst_layers.setTable(table_dict)

	def set_selected(self):
		selected_rows = [si.row() for si in self.lst_layers.selectionModel().selectedRows()]
		
		for row in range(self.lst_layers.rowCount):
			if row in selected_rows:
				self.lst_layers.item(row,0).setCheckState(QtCore.Qt.Checked)
			else:
				self.lst_layers.item(row,0).setCheckState(QtCore.Qt.Unchecked)
				
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			print '\nERRO:\tGlyph mismatch:\n\tCurrent active glyph: %s\n\tLayers panel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg)
			print 'WARN:\tNo action taken! Forcing refresh!' 
			self.refresh()
			return 0
		return 1

class TRWMasterTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRWMasterTableView, self).__init__()
		self.setMaximumHeight(200)
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
		self.header = self.horizontalHeader()

		# - Set 
		self.setTable(data)		
	
		# - Styling
		self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		#self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)
		#self.resizeColumnsToContents()
		#self.resizeRowsToContents()
	
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
					newitem.setData(QtCore.Qt.DecorationRole, data[layer]['Color'])
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

class TRLayerBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRLayerBasic, self).__init__()

		# - Init
		self.aux = aux

		# -- Basic Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_add = QtGui.QPushButton('Add')
		self.btn_del = QtGui.QPushButton('Remove')
		self.btn_dup = QtGui.QPushButton('Duplicate')
		self.btn_setServ = QtGui.QPushButton('Service')
		self.btn_setMask = QtGui.QPushButton('Mask')
		self.btn_setWire = QtGui.QPushButton('Wireframe')
				
		self.btn_add.setToolTip('Add new layer with name')
		self.btn_dup.setToolTip('Duplicate selected with suffix')
		self.btn_del.setToolTip('Delete selected layers')
		self.btn_setServ.setToolTip('Set selected layers as Service')
		self.btn_setWire.setToolTip('Set selected layers as Wireframe')

		self.edt_name = QtGui.QLineEdit('New')
		self.edt_name.setToolTip('Name or suffix')
	
		self.btn_add.clicked.connect(self.addLayer)
		self.btn_dup.clicked.connect(self.duplicateLayers)
		self.btn_del.clicked.connect(self.deleteLayers)
		self.btn_setMask.clicked.connect(self.addMaskLayers)

		self.btn_setServ.clicked.connect(lambda: self.setLayer('Service'))
		self.btn_setWire.clicked.connect(lambda: self.setLayer('Wireframe'))

		self.lay_buttons.addWidget(QtGui.QLabel('Suffix/Name:'),	0, 0, 1, 1)
		self.lay_buttons.addWidget(self.edt_name, 					0, 1, 1, 2)
		self.lay_buttons.addWidget(self.btn_add, 					1, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_del, 					1, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_dup, 					1, 2, 1, 1)
		self.lay_buttons.addWidget(self.btn_setServ, 				2, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_setMask, 				2, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_setWire, 				2, 2, 1, 1)
	 
		self.addLayout(self.lay_buttons)

	def addLayer(self):
		if self.aux.doCheck():
			newLayer = fl6.flLayer()
			newLayer.name = str(self.edt_name.text)
			self.aux.glyph.addLayer(newLayer)
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Add Layer: %s.' %newLayer.name)
			self.aux.glyph.update()
			self.aux.refresh()

	def duplicateLayers(self):	
		if self.aux.doCheck():	
			# - Duplicate 
			for layer_name in self.aux.lst_layers.getTable():
				self.aux.glyph.duplicateLayer(layer_name , '%s%s' %(layer_name, self.edt_name.text))			
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Duplicate Layer: %s.' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()
			self.aux.refresh()

	def addMaskLayers(self):	
		if self.aux.doCheck():	
			for layer_name in self.aux.lst_layers.getTable():
				# - Build mask layer
				srcShapes = self.aux.glyph.shapes(layer_name)
				newMaskLayer = self.aux.glyph.layer(layer_name).getMaskLayer(True)			

				# - Copy shapes to mask layer
				for shape in srcShapes:
					newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'New Mask Layer: %s.' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()
			self.aux.refresh()

	def deleteLayers(self):				
		if self.aux.doCheck():	
			for layer_name in self.aux.lst_layers.getTable():
				self.aux.glyph.removeLayer(layer_name)

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Delete Layer: %s.' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()
			self.aux.refresh()

	def setLayer(self, type):
		if self.aux.doCheck():	
			for layer_name in self.aux.lst_layers.getTable():
				wLayer = self.aux.glyph.layer(layer_name)

				if type is 'Service': wLayer.isService = not wLayer.isService
				if type is 'Wireframe': wLayer.isWireframe = not wLayer.isWireframe

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Set Layer as <%s>: %s.' %(type, '; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()])))
			self.aux.glyph.update()
			self.aux.refresh()

class TRLayerTools(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRLayerTools, self).__init__()

		# - Init
		self.aux = aux

		# -- Mode checks
		self.lay_checks = QtGui.QGridLayout()
		self.chk_outline = QtGui.QCheckBox('Outline')
		self.chk_guides = QtGui.QCheckBox('Guides')
		self.chk_anchors = QtGui.QCheckBox('Anchors')
		self.chk_lsb = QtGui.QCheckBox('LSB')
		self.chk_adv = QtGui.QCheckBox('Advance')
		self.chk_rsb = QtGui.QCheckBox('RSB')
		
		# -- Set States
		self.chk_outline.setCheckState(QtCore.Qt.Checked)
		self.chk_adv.setCheckState(QtCore.Qt.Checked)
	
		# -- Build
		self.lay_checks.addWidget(self.chk_outline, 0, 0)
		self.lay_checks.addWidget(self.chk_guides, 	0, 1)
		self.lay_checks.addWidget(self.chk_anchors, 0, 2)
		self.lay_checks.addWidget(self.chk_lsb, 	1, 0)
		self.lay_checks.addWidget(self.chk_adv, 	1, 1)
		self.lay_checks.addWidget(self.chk_rsb, 	1, 2)
		
		self.addLayout(self.lay_checks)

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_swap = QtGui.QPushButton('Swap')
		self.btn_copy = QtGui.QPushButton('Copy')
		self.btn_paste = QtGui.QPushButton('Paste')
		self.btn_clean = QtGui.QPushButton('Empty')
		self.btn_unlock = QtGui.QPushButton('Unlock')
		self.btn_expand = QtGui.QPushButton('Expand')

		#self.btn_unlock.setEnabled(False)
		self.btn_expand.setEnabled(False)
		
		self.btn_swap.setToolTip('Swap Selected Layer with Active Layer')
		self.btn_copy.setToolTip('Copy Active Layer to Selected Layer')
		self.btn_paste.setToolTip('Paste Selected Layer to Active Layer')
		self.btn_clean.setToolTip('Remove contents from selected layers')
		self.btn_unlock.setToolTip('Unlock all locked references.\nSHIFT+Click will lock all references.')
		self.btn_expand.setToolTip('Expand transformations for selected layers')

		self.btn_swap.clicked.connect(self.layer_swap)
		self.btn_copy.clicked.connect(self.layer_copy)
		self.btn_paste.clicked.connect(self.layer_paste)
		self.btn_clean.clicked.connect(self.layer_clean)
		self.btn_unlock.clicked.connect(self.layer_unlock)
		#self.btn_expand.clicked.connect(self.expand)
				
		self.lay_buttons.addWidget(self.btn_swap,	0, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_copy,	0, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_paste,	0, 2, 1, 1)
		self.lay_buttons.addWidget(self.btn_clean,	1, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_unlock,	1, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_expand,	1, 2, 1, 1)

		self.addLayout(self.lay_buttons)
					
	# - Helper Procedures ----------------------------------------------
	def Copy_Paste_Layer_Shapes(self, glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTShapes = None
		
		# -- Get shapes
		srcShapes = glyph.shapes(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup destination layers
		if cleanDST:
			exportDSTShapes = glyph.shapes(dstLayerName)
			glyph.layer(dstLayerName).removeAllShapes()
		
		# -- Copy/Paste
		for shape in srcShapes:
			glyph.layer(dstLayerName).addShape(shape.cloneTopLevel())

		return exportDSTShapes

	def Copy_Paste_Layer_Metrics(self, glyph, layerName, copy=True, mode='ADV', impSRC=None):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		
		if 'LSB' in mode.upper():
			exportMetric = glyph.getLSB(dstLayerName) 
			glyph.setLSB(glyph.getLSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			glyph.setLSBeq(glyph.getSBeq(srcLayerName)[0], dstLayerName)
			return exportMetric

		if 'ADV' in mode.upper():
			exportMetric = glyph.getAdvance(dstLayerName)
			glyph.setAdvance(glyph.getAdvance(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			return exportMetric

		if 'RSB' in mode.upper():
			exportMetric = glyph.getRSB(dstLayerName)
			glyph.setRSB(glyph.getRSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			glyph.setRSBeq(glyph.getSBeq(srcLayerName)[1], dstLayerName)
			return exportMetric

	def Copy_Paste_Layer_Guides(self, glyph, layerName, copy=True, cleanDST=False):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName

		# -- Cleanup !!! Not implementable for now?! Why
		if cleanDST:
			pass

		glyph.layer(dstLayerName).appendGuidelines(glyph.guidelines(srcLayerName))

	def Copy_Paste_Layer_Anchors(self, glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTAnchors = None

		# -- Get anchors
		srcAnchors = glyph.anchors(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup !!! Not working
		if cleanDST:
			exportDSTAnchors = glyph.anchors(dstLayerName)

			for anchor in glyph.anchors(dstLayerName):
					glyph.layer(dstLayerName).removeAnchor(anchor)

		for anchor in srcAnchors:
				glyph.anchors(dstLayerName).append(anchor)

		return exportDSTAnchors

	# - Button procedures ---------------------------------------------------
	def layer_unlock(self):
		if self.aux.doCheck():
			modifiers = QtGui.QApplication.keyboardModifiers()

			if self.chk_outline.isChecked():
				for layer_name in self.aux.lst_layers.getTable():
					for shape in self.aux.glyph.shapes(layer_name):
						
						if modifiers == QtCore.Qt.ShiftModifier: # Shift + Click will lock
							shape.contentLocked = True
						else:
							shape.contentLocked = False

			self.aux.glyph.updateObject(self.aux.glyph.fl, '%s shapes on Layer(s) | %s' %(['Unlock', 'Lock'][modifiers == QtCore.Qt.ShiftModifier],'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()])))
			self.aux.glyph.update()


	def layer_swap(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				exportSRC = self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, True)
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, True, exportSRC)

			if self.chk_guides.isChecked():
				pass

			if self.chk_anchors.isChecked():
				pass

			if self.chk_lsb.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'LSB')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'LSB', exportMetric)

			if self.chk_adv.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'ADV')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'ADV', exportMetric)

			if self.chk_rsb.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'RSB')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'RSB', exportMetric)

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Swap Layers | %s <-> %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()


	def layer_copy(self):
		if self.aux.doCheck():
			if self.chk_outline.isChecked():
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)
				
			if self.chk_guides.isChecked():
				self.Copy_Paste_Layer_Guides(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)

			if self.chk_anchors.isChecked():
				self.Copy_Paste_Layer_Anchors(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)

			if self.chk_lsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'LSB')
				
			if self.chk_adv.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'ADV')
				
			if self.chk_rsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'RSB')
				
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Copy Layer | %s <- %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()

	def layer_paste(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)
				
			if self.chk_guides.isChecked():
				self.Copy_Paste_Layer_Guides(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)

			if self.chk_anchors.isChecked():
				self.Copy_Paste_Layer_Anchors(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)

			if self.chk_lsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'LSB')
				
			if self.chk_adv.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'ADV')
				
			if self.chk_rsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'RSB')
				
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Paste Layer | %s -> %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()

	def layer_clean(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				for layer_name in self.aux.lst_layers.getTable():
					self.aux.glyph.layer(layer_name).removeAllShapes()

			if self.chk_guides.isChecked():
				pass # TODO!!!!!

			if self.chk_anchors.isChecked():
				pass # TODO!!!!!
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Clean Layer(s) | %s' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()

class TRLayerMultiEdit(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRLayerMultiEdit, self).__init__()

		# - Init
		self.aux = aux
		self.backup = {}
		self.contourClipboard = {}

		# -- Edit fileds
		self.edt_shift = QtGui.QLineEdit('0.0, 0.0')
		self.edt_scale = QtGui.QLineEdit('100, 100')
		self.edt_slant = QtGui.QLineEdit('0.0')
		self.edt_rotate = QtGui.QLineEdit('0.0')

		self.edt_shift.setToolTip('Translate Layer by X, Y (comma separated)')
		self.edt_scale.setToolTip('Scale Layer by X percent, Y percent(comma separated)')
		self.edt_slant.setToolTip('Slant/Shear degrees')
		self.edt_rotate.setToolTip('Rotate degrees')

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_unfold = QtGui.QPushButton('Unfold Layers')
		self.btn_restore = QtGui.QPushButton('Fold Layers')
		self.btn_copy = QtGui.QPushButton('Copy Outline')
		self.btn_paste = QtGui.QPushButton('Paste Outline')
		self.btn_transform = QtGui.QPushButton('Transform Layer')
		self.btn_transform_shape = QtGui.QPushButton('Transform Elements')

		self.btn_restore.setEnabled(False)
		self.btn_paste.setEnabled(False)
		
		self.btn_unfold.setToolTip('Reposition selected layers side by side. Selection order does matter!')
		self.btn_restore.setToolTip('Restore Layer Metrics.')
		self.btn_copy.setToolTip('Copy selected outline to cliboard for each of selected layers.')
		self.btn_paste.setToolTip('Paste outline from cliboard layer by layer (by name).\nNon existing layers are discarded!\nClick: New Element is created upon Paste.\nSHIFT+Click: Paste inside currently selected Element.')
		self.btn_transform.setToolTip('Affine transform selected layers.')

		self.btn_unfold.clicked.connect(self.layers_unfold)
		self.btn_restore.clicked.connect(self.layers_restore)
		self.btn_copy.clicked.connect(self.outline_copy)
		self.btn_paste.clicked.connect(self.outline_paste)
		self.btn_transform.clicked.connect(lambda: self.layer_transform(False))
		self.btn_transform_shape.clicked.connect(lambda: self.layer_transform(True))
				
		self.lay_buttons.addWidget(self.btn_unfold,				0, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_restore,			0, 4, 1, 4)
		self.lay_buttons.addWidget(self.btn_copy,				1, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_paste,				1, 4, 1, 4)
		self.lay_buttons.addWidget(QtGui.QLabel('Translate:'),	2, 0, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Scale:'),		2, 2, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Shear:'),		2, 4, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Rotate:'),		2, 6, 1, 2)
		self.lay_buttons.addWidget(self.edt_shift,				3, 0, 1, 2)
		self.lay_buttons.addWidget(self.edt_scale,				3, 2, 1, 2)
		self.lay_buttons.addWidget(self.edt_slant,				3, 4, 1, 2)
		self.lay_buttons.addWidget(self.edt_rotate,				3, 6, 1, 2)
		self.lay_buttons.addWidget(self.btn_transform,			4, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_transform_shape,	4, 4, 1, 4)

		self.addLayout(self.lay_buttons)

	# - Button procedures ---------------------------------------------------
	def layers_unfold(self):
		if self.aux.doCheck() and len(self.aux.lst_layers.getTable()) > 1:
			# - Init
			wGlyph = self.aux.glyph

			# - Prepare Backup
			self.backup = {layer_name:(wGlyph.getLSB(layer_name), wGlyph.getAdvance(layer_name)) for layer_name in self.aux.lst_layers.getTable()}
			self.btn_restore.setEnabled(True)

			# - Calculate metrics
			newLSB = 0
			nextLSB = 0
			newAdvance = sum([sum(layer_name) for layer_name in self.backup.values()])
			
			for layer_name in self.aux.lst_layers.getTable():
				wLayer = layer_name
				
				newLSB += nextLSB + self.backup[wLayer][0]
				nextLSB = self.backup[wLayer][1]
				
				wGlyph.setLSB(newLSB, wLayer)
				wGlyph.setAdvance(newAdvance, wLayer)
				wGlyph.layer(wLayer).isVisible = True

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Unfold Layers (Side By Side): %s.' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()

	def layers_restore(self):
		if self.aux.doCheck() and len(self.backup.keys()):
			# - Resore metrics
			wGlyph = self.aux.glyph

			for layer, metrics in self.backup.iteritems():
				wGlyph.setLSB(metrics[0], layer)
				wGlyph.setAdvance(metrics[1], layer)
				wGlyph.layer(layer).isVisible = False

			# - Reset
			self.backup = {}
			self.btn_restore.setEnabled(False)

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Restore Layer metrics: %s.' %'; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
			self.aux.glyph.update()

	def outline_copy(self):
		# - Init
		wGlyph = self.aux.glyph
		wContours = wGlyph.contours()
		self.contourClipboard = {}
		
		# - Build initial contour information
		selectionTuples = wGlyph.selectedAtContours()
		selection = {key:[layer_name[1] for layer_name in value] if not wContours[key].isAllNodesSelected() else [] for key, value in groupby(selectionTuples, lambda x:x[0])}

		# - Process
		if len(selection.keys()):
			self.btn_paste.setEnabled(True)
						
			for layer_name in self.aux.lst_layers.getTable():
				wLayer = layer_name
				self.contourClipboard[wLayer] = []

				for cid, nList in selection.iteritems():
					if len(nList):
						 self.contourClipboard[wLayer].append(fl6.flContour([wGlyph.nodes(wLayer)[nid].clone() for nid in nList]))
					else:
						self.contourClipboard[wLayer].append(wGlyph.contours(wLayer)[cid].clone())


			print 'DONE:\t Copy outline; Glyph: %s; Layers: %s.' %(self.aux.glyph.fl.name, '; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()]))
		
	def outline_paste(self):
		# - Init
		wGlyph = self.aux.glyph
		modifiers = QtGui.QApplication.keyboardModifiers()

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(self.contourClipboard.keys()):
			for layerName, contours in self.contourClipboard.iteritems():
				wLayer = wGlyph.layer(layerName)

				if wLayer is not None:
					if modifiers == QtCore.Qt.ShiftModifier:
						# - Insert contours into currently selected shape
						selected_shapes_list = wGlyph.selectedAtShapes(index=False, layer=layerName, deep=False)

						if len(selected_shapes_list):
							selected_shape = selected_shapes_list[0][0]
							selected_shape.addContours(contours, True)
						else:
							add_new_shape(wLayer, contours)	# Fallback
					else:
						# - Create new shape
						add_new_shape(wLayer, contours)
		
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Paste outline; Glyph: %s; Layers: %s' %(self.aux.glyph.fl.name, '; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()])))
			self.aux.glyph.update()

	def layer_transform(self, shapes=False):
		if self.aux.doCheck() and len(self.aux.lst_layers.getTable()):
			
			# - Init
			wGlyph = self.aux.glyph

			inpShift = self.edt_shift.text.split(',') if len(self.edt_shift.text) and ',' in self.edt_shift.text else '0.0, 0.0'
			inpScale = self.edt_scale.text.split(',') if len(self.edt_scale.text) and ',' in self.edt_scale.text else '100, 100'

			wSift_x = float(inpShift[0].strip())
			wSift_y = float(inpShift[1].strip())

			wScale_x = float(inpScale[0].strip())/100
			wScale_y = float(inpScale[1].strip())/100

			wSlant =  radians(float(self.edt_slant.text.strip())) if len(self.edt_slant.text) else 0.
			wRotate =  -float(self.edt_rotate.text.strip()) if len(self.edt_rotate.text) else 0.
			
			# m11, m12, m13, m21, m22, m23, m31, m32, m33 = 1
			# ! Note: wrong but will do...
			new_transform = QtGui.QTransform().scale(wScale_x, wScale_y).rotate(wRotate).shear(wSlant, 0).translate(wSift_x, wSift_y)
			
			for layer_name in self.aux.lst_layers.getTable():
				wLayer = wGlyph.layer(layer_name)
				
				if not shapes:
					# - Transform at origin
					wBBox = wLayer.boundingBox
					wCenter = (wBBox.width()/2 + wBBox.x(), wBBox.height()/2 + wBBox.y())
					transform_to_origin = QtGui.QTransform().translate(-wCenter[0], -wCenter[1])
					transform_from_origin = QtGui.QTransform().translate(*wCenter)
					
					# - Transform
					if wRotate != 0: wLayer.applyTransform(transform_to_origin) # Transform at origin only if we have rotation!
					wLayer.applyTransform(new_transform)
					if wRotate != 0: wLayer.applyTransform(transform_from_origin)
				else:
					wShapes = wGlyph.shapes(layer_name)
					
					for shape in wShapes:
						'''
						# - Transform at origin and move to new location according to transformation
						wBBox = shape.boundingBox
						wCenter = (wBBox.width()/2 + wBBox.x(), wBBox.height()/2 + wBBox.y())
						newCenter = new_transform.map(QtCore.QPointF(*wCenter))

						transform_to_origin = QtGui.QTransform().translate(-wCenter[0], -wCenter[1])
						transform_from_origin = QtGui.QTransform().translate(newCenter.x(), wCenter[1])
						#transform_from_origin = QtGui.QTransform().translate(*wCenter)

						# - Transform
						shape.applyTransform(transform_to_origin)
						shape.applyTransform(new_transform)
						shape.applyTransform(transform_from_origin)
						'''
						edit_transform = shape.transform.scale(wScale_x, wScale_y).rotate(wRotate).shear(wSlant, 0).translate(wSift_x, wSift_y)
						shape.transform = edit_transform
						#shape.update()

			self.aux.glyph.updateObject(self.aux.glyph.fl, ' Glyph: %s; Transform Layers: %s' %(self.aux.glyph.fl.name, '; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()])))
			self.aux.glyph.update()

class TRNewLayerBlend(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRNewLayerBlend, self).__init__()

		# - Init
		self.aux = aux
		self.process_array = []
		
		# - Interface
		self.lay_buttons = QtGui.QGridLayout()
		
		self.chk_setAxis = QtGui.QPushButton('Set Axis')
		self.chk_swapAxis = QtGui.QPushButton('Swap')

		self.chk_setAxis.setCheckable(True)
		self.chk_swapAxis.setCheckable(True)

		self.chk_setAxis.clicked.connect(lambda: self.prepare_lerp())

		# -- Blend active layer to single selected layer
		self.mixer_dx = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dx.sld_axis.valueChanged.connect(lambda: self.process_lerp())		

		self.lay_buttons.addWidget(self.chk_setAxis,	0, 0, 1, 1)
		self.lay_buttons.addWidget(self.chk_swapAxis,	0, 1, 1, 1)

		self.addLayout(self.lay_buttons)
		self.addLayout(self.mixer_dx)
		
	def prepare_lerp(self):
		if self.chk_setAxis.isChecked():
			self.chk_setAxis.setText('Reset Axis')
			
			selection = self.aux.lst_layers.getTable()
			src_array_t0 = self.aux.glyph._getCoordArray(selection[0]).asPairs()
			src_array_t1 = self.aux.glyph._getCoordArray(selection[1]).asPairs()
			
			self.process_array = zip(src_array_t0, src_array_t1)
		
		else:
			self.process_array = []
			self.mixer_dx.reset()
			self.chk_setAxis.setText('Set Axis')			

	def lerpXY(self, t0, t1, tx, ty):
		if self.chk_swapAxis.isChecked():
			return (lerp(t1[0], t0[0], tx), lerp(t1[1], t0[1], ty))
		else:
			return (lerp(t0[0], t1[0], tx), lerp(t0[1], t1[1], ty))

	def process_lerp(self):
		if self.chk_setAxis.isChecked():
			try:
				tx = self.mixer_dx.sld_axis.value/float(self.mixer_dx.edt_1.text)
			except ZeroDivisionError:
				tx = 0.
			
			dst_array = [self.lerpXY(item[0], item[1], tx, tx) for item in self.process_array]
			
			self.aux.glyph._setCoordArray(dst_array)
			
			self.aux.glyph.update()
			fl6.Update(self.aux.glyph.fl)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		#self.layerSelector = TRLayerSelect()
		self.layerSelector = TRWLayerSelect()
		self.quickTools = TRLayerTools(self.layerSelector)
		#self.blendTools = QlayerBlend(self.layerSelector)
		self.blendTools = TRNewLayerBlend(self.layerSelector)
		self.basicTools = TRLayerBasic(self.layerSelector)
		self.unfoldLayers = TRLayerMultiEdit(self.layerSelector)

		layoutV.addLayout(self.layerSelector)
		layoutV.addWidget(QtGui.QLabel('Basic Tools (Layers selected)'))
		layoutV.addLayout(self.basicTools)
		layoutV.addWidget(QtGui.QLabel('Content Tools (Active Layer to selection)'))
		layoutV.addLayout(self.quickTools)
		layoutV.addWidget(QtGui.QLabel('Layer Multi-editing (Layers selected)'))
		layoutV.addLayout(self.unfoldLayers)
		layoutV.addWidget(QtGui.QLabel('Interpolate/Blend (Selection to Active Layer)'))
		layoutV.addLayout(self.blendTools)


		# - Build ---------------------------
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 700)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()