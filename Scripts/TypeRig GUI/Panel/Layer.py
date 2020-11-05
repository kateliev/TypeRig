#FLM: TR: Layers
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os
from math import radians
from collections import OrderedDict
from itertools import groupby
import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl import *
from typerig.core.base.message import *
from typerig.core.func.math import linInterp as lerp

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import *

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Layers', '2.02'

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
	def layer_add(parent):
		if parent.doCheck():
			user_input = TR1FieldDLG('Add new layer ', 'Please enter a name for the layer created.', 'Name:').values
			newLayer = fl6.flLayer()
			newLayer.name = str(user_input)
			parent.glyph.addLayer(newLayer)
			parent.glyph.updateObject(parent.glyph.fl, 'Add Layer: %s.' %newLayer.name)
			parent.refresh()

	@staticmethod
	def layer_duplicate(parent, ask_user=False):	
		if parent.doCheck():
			# - Ask user about rename pattern
			if ask_user:
				user_input = TR2FieldDLG('Duplicate Layer', 'Please enter prefix and/or suffix for duplicate layers', 'Prefix:', 'Suffix:').values
			
			layer_prefix = user_input[0] if ask_user else ''
			layer_suffux = user_input[1] if ask_user else parent.edt_name.text

			# - Duplicate 
			for layer_name in parent.lst_layers.getTable():
				parent.glyph.duplicateLayer(layer_name , '{1}{0}{2}'.format(layer_name, layer_prefix, layer_suffux))
			
			parent.glyph.updateObject(parent.glyph.fl, 'Duplicate Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_duplicate_mask(parent):	
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				# - Build mask layer
				srcShapes = parent.glyph.shapes(layer_name)
				newMaskLayer = parent.glyph.layer(layer_name).getMaskLayer(True)			

				# - Copy shapes to mask layer
				for shape in srcShapes:
					newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!
			
			parent.glyph.updateObject(parent.glyph.fl, 'New Mask Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_delete(parent):				
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				parent.glyph.removeLayer(layer_name)

			parent.glyph.updateObject(parent.glyph.fl, 'Delete Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_set_type(parent, type):
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				wLayer = parent.glyph.layer(layer_name)

				if type is 'Service': wLayer.isService = not wLayer.isService
				if type is 'Wireframe': wLayer.isWireframe = not wLayer.isWireframe

			parent.glyph.updateObject(parent.glyph.fl, 'Set Layer as <%s>: %s.' %(type, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
			parent.refresh()

	# - Layer: Content tools ---------------------------------------------------
	@staticmethod
	def layer_copy_shapes(glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
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

	@staticmethod
	def layer_copy_metrics(glyph, layerName, copy=True, mode='ADV', impSRC=None):
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

	@staticmethod
	def layer_copy_guides(glyph, layerName, copy=True, cleanDST=False):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName

		# -- Cleanup !!! Not implementable for now?! Why
		if cleanDST:
			pass

		glyph.layer(dstLayerName).appendGuidelines(glyph.guidelines(srcLayerName))

	@staticmethod
	def layer_copy_anchors(glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
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

	@staticmethod
	def layer_unlock(parent, locked_trigger=False):
		if parent.doCheck():
			if parent.chk_outline.isChecked():
				for layer_name in parent.lst_layers.getTable():
					for shape in parent.glyph.shapes(layer_name):
						shape.contentLocked = locked_trigger

			parent.glyph.updateObject(parent.glyph.fl, '%s shapes on Layer(s) | %s' %(['Unlock', 'Lock'][locked_trigger],'; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))


	@staticmethod
	def layer_swap(parent):
		if parent.doCheck():	
			if parent.chk_outline.isChecked():
				exportSRC = TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), True, True)
				TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), False, True, exportSRC)

			if parent.chk_guides.isChecked():
				pass

			if parent.chk_anchors.isChecked():
				pass

			if parent.chk_lsb.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'LSB')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'LSB', exportMetric)

			if parent.chk_adv.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'ADV')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'ADV', exportMetric)

			if parent.chk_rsb.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'RSB')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'RSB', exportMetric)

			parent.glyph.updateObject(parent.glyph.fl, 'Swap Layers | %s <-> %s.' %(parent.glyph.activeLayer().name, parent.lst_layers.currentItem().text()))


	@staticmethod
	def layer_pull(parent):
		if parent.doCheck():
			print parent.glyph
			if parent.chk_outline.isChecked():
				TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), True)
				
			if parent.chk_guides.isChecked():
				TRLayerActionCollector.layer_copy_guides(parent.glyph, parent.lst_layers.currentItem().text(), True)

			if parent.chk_anchors.isChecked():
				TRLayerActionCollector.layer_copy_anchors(parent.glyph, parent.lst_layers.currentItem().text(), True)

			if parent.chk_lsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'LSB')
				
			if parent.chk_adv.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'ADV')
				
			if parent.chk_rsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'RSB')
				
			parent.glyph.updateObject(parent.glyph.fl, 'Copy Layer | %s <- %s.' %(parent.glyph.activeLayer().name, parent.lst_layers.currentItem().text()))


	@staticmethod
	def layer_push(parent):
		if parent.doCheck():	
			if parent.chk_outline.isChecked():
				TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), False)
				
			if parent.chk_guides.isChecked():
				TRLayerActionCollector.layer_copy_guides(parent.glyph, parent.lst_layers.currentItem().text(), False)

			if parent.chk_anchors.isChecked():
				TRLayerActionCollector.layer_copy_anchors(parent.glyph, parent.lst_layers.currentItem().text(), False)

			if parent.chk_lsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'LSB')
				
			if parent.chk_adv.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'ADV')
				
			if parent.chk_rsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'RSB')
				
			parent.glyph.updateObject(parent.glyph.fl, 'Paste Layer | %s -> %s.' %(parent.glyph.activeLayer().name, parent.lst_layers.currentItem().text()))

	@staticmethod
	def layer_clean(parent):
		if parent.doCheck():	
			if parent.chk_outline.isChecked():
				for layer_name in parent.lst_layers.getTable():
					parent.glyph.layer(layer_name).removeAllShapes()

			if parent.chk_guides.isChecked():
				pass # TODO!!!!!

			if parent.chk_anchors.isChecked():
				pass # TODO!!!!!
			
			parent.glyph.updateObject(parent.glyph.fl, 'Clean Layer(s) | %s' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	# - Layer: Multilayer tools ---------------------------------------------------
	@staticmethod
	def layer_unfold(parent):
		if parent.doCheck() and len(parent.lst_layers.getTable()) > 1:
			# - Init
			wGlyph = parent.glyph

			# - Prepare Backup
			parent.backup = {layer_name:(wGlyph.getLSB(layer_name), wGlyph.getAdvance(layer_name)) for layer_name in parent.lst_layers.getTable()}

			# - Calculate metrics
			newLSB = 0
			nextLSB = 0
			newAdvance = sum([sum(layer_name) for layer_name in parent.backup.values()])
			
			for layer_name in parent.lst_layers.getTable():
				wLayer = layer_name
				
				newLSB += nextLSB + parent.backup[wLayer][0]
				nextLSB = parent.backup[wLayer][1]
				
				wGlyph.setLSB(newLSB, wLayer)
				wGlyph.setAdvance(newAdvance, wLayer)
				wGlyph.layer(wLayer).isVisible = True

			parent.glyph.updateObject(parent.glyph.fl, 'Unfold Layers: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	@staticmethod
	def layer_restore(parent):
		if parent.doCheck() and len(parent.backup.keys()):
			# - Resore metrics
			wGlyph = parent.glyph

			for layer, metrics in parent.backup.iteritems():
				wGlyph.setLSB(metrics[0], layer)
				wGlyph.setAdvance(metrics[1], layer)
				wGlyph.layer(layer).isVisible = False

			# - Reset
			parent.backup = {}
			parent.glyph.updateObject(parent.glyph.fl, 'Restore Layer metrics: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	@staticmethod
	def layer_copy_outline(parent):
		# - Init
		wGlyph = parent.glyph
		wContours = wGlyph.contours()
		parent.contourClipboard = {}
		
		# - Build initial contour information
		selectionTuples = wGlyph.selectedAtContours()
		selection = {key:[layer_name[1] for layer_name in value] if not wContours[key].isAllNodesSelected() else [] for key, value in groupby(selectionTuples, lambda x:x[0])}

		# - Process
		if len(selection.keys()):
			for layer_name in parent.lst_layers.getTable():
				wLayer = layer_name
				parent.contourClipboard[wLayer] = []

				for cid, nList in selection.iteritems():
					if len(nList):
						 parent.contourClipboard[wLayer].append(fl6.flContour([wGlyph.nodes(wLayer)[nid].clone() for nid in nList]))
					else:
						parent.contourClipboard[wLayer].append(wGlyph.contours(wLayer)[cid].clone())
			output(0, app_name, 'Copy outline; Glyph: %s; Layers: %s.' %(parent.glyph.fl.name, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
		
	@staticmethod
	def layer_paste_outline(parent):
		# - Init
		wGlyph = parent.glyph
		modifiers = QtGui.QApplication.keyboardModifiers()

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(parent.contourClipboard.keys()):
			for layerName, contours in parent.contourClipboard.iteritems():
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
		
			parent.glyph.updateObject(parent.glyph.fl, 'Paste outline; Glyph: %s; Layers: %s' %(parent.glyph.fl.name, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))


# - Sub widgets ------------------------
class TRWLayerSelect(QtGui.QVBoxLayout):
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

		# - Mode checks
		self.lay_checks = QtGui.QGridLayout()
		self.chk_outline = QtGui.QCheckBox('Outline')
		self.chk_guides = QtGui.QCheckBox('Guides')
		self.chk_anchors = QtGui.QCheckBox('Anchors')
		self.chk_lsb = QtGui.QCheckBox('LSB')
		self.chk_adv = QtGui.QCheckBox('Advance')
		self.chk_rsb = QtGui.QCheckBox('RSB')
		
		# - Set States
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

	# - Basics ---------------------------------------
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
		 	
		 	table_dict = {n : OrderedDict(zip(column_names, data)) for n, data in enumerate(init_data)}
		 	
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
			warnings.warn('Current active glyph: %s\tPanel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg), GlyphWarning)
			warnings.warn('Forcing refresh on panel: %s.' %app_name, TRPanelWarning)
			self.refresh()
			return 0
		return 1

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

class TRLayerMultiEdit(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRLayerMultiEdit, self).__init__()

		# - Init
		self.aux = aux
		self.backup = {}
		self.contourClipboard = {}

		# -- Custom controls
		self.tr_trans_ctrl = TRTransformCtrl()
		
		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_transform = QtGui.QPushButton('Transform')
		self.btn_trans_res = QtGui.QPushButton('Reset')

		self.btn_transform.setToolTip('Affine transform selected layers.')
		self.btn_trans_res.setToolTip('Reset transformation fileds.')

		self.btn_transform.clicked.connect(self.layer_transform)
		self.btn_trans_res.clicked.connect(self.tr_trans_ctrl.reset)
				
		self.lay_buttons.addWidget(self.tr_trans_ctrl, 			0, 0, 2, 8)
		self.lay_buttons.addWidget(self.btn_trans_res,			2, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_transform,			2, 4, 1, 4)
		
		self.tr_trans_ctrl.lay_controls.setMargin(0)
		
		self.addLayout(self.lay_buttons)
	
	def layer_transform(self):
		if self.aux.doCheck() and len(self.aux.lst_layers.getTable()):
			
			# - Init
			wGlyph = self.aux.glyph
			
			for layer_name in self.aux.lst_layers.getTable():
				wLayer = wGlyph.layer(layer_name)
				wBBox = wLayer.boundingBox
				new_transform, org_transform, rev_transform = self.tr_trans_ctrl.getTransform(wBBox)
				wLayer.applyTransform(org_transform)
				wLayer.applyTransform(new_transform)
				wLayer.applyTransform(rev_transform)

			self.aux.glyph.updateObject(self.aux.glyph.fl, ' Glyph: %s; Transform Layers: %s' %(self.aux.glyph.fl.name, '; '.join([layer_name for layer_name in self.aux.lst_layers.getTable()])))


class TRNewLayerBlend(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(TRNewLayerBlend, self).__init__()

		# - Init
		self.aux = aux
		self.process_array = []
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas(True)
		
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
			src_array_t0 = self.aux.glyph._getPointArray(selection[0])
			src_array_t1 = self.aux.glyph._getPointArray(selection[1])
			
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
			self.aux.glyph._setPointArray(dst_array)
			
			self.aux.glyph.update()
			self.active_canvas.refreshAll()

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	
	def __init__(self):
		super(tool_tab, self).__init__()

		# -- Layout and widgets -----------------------------------
		layoutV = QtGui.QVBoxLayout()

		self.layerSelector = TRWLayerSelect()

		self.blendTools = TRNewLayerBlend(self.layerSelector)
		self.unfoldLayers = TRLayerMultiEdit(self.layerSelector)

		layoutV.addLayout(self.layerSelector)
		
		self.tools_multiedit = TRCollapsibleBox('Transform (Layers selected)')
		self.tools_multiedit.setContentLayout(self.unfoldLayers)
		layoutV.addWidget(self.tools_multiedit)

		self.tools_blend = TRCollapsibleBox('Blend (Selection to Active Layer)')
		self.tools_blend.setContentLayout(self.blendTools)
		layoutV.addWidget(self.tools_blend)

		# -- Menus and Actions -----------------------------------
		self.act_layer_add = QtGui.QAction('New', self)
		self.act_layer_duplicate = QtGui.QAction('Duplicate', self)
		self.act_layer_duplicate_mask = QtGui.QAction('Duplicate to Mask', self)
		self.act_layer_delete = QtGui.QAction('Remove', self)

		self.menu_layer_type = QtGui.QMenu('Type', self)
		act_layer_set_type_mask = QtGui.QAction('Set as Mask', self)
		act_layer_set_type_wireframe = QtGui.QAction('Set as Wireframe', self)
		act_layer_set_type_service = QtGui.QAction('Set as Service', self)

		self.menu_layer_type.addAction(act_layer_set_type_mask)
		self.menu_layer_type.addAction(act_layer_set_type_wireframe)
		self.menu_layer_type.addAction(act_layer_set_type_service)
		
		self.menu_layer_content = QtGui.QMenu('Content', self)
		'''
		act_layer_push_shapes = QtGui.QAction('Push Shapes', self)
		act_layer_push_metrics = QtGui.QAction('Push Metrics', self)
		act_layer_push_guides = QtGui.QAction('Push Guidelines', self)
		act_layer_push_anchors = QtGui.QAction('Push Anchors', self)
		act_layer_pull_shapes = QtGui.QAction('Pull Shapes', self)
		act_layer_pull_metrics = QtGui.QAction('Pull Metrics', self)
		act_layer_pull_guides = QtGui.QAction('Pull Guidelines', self)
		act_layer_pull_anchors = QtGui.QAction('Pull Anchors', self)
		'''
		act_layer_swap = QtGui.QAction('Swap', self)
		act_layer_pull = QtGui.QAction('Pull', self)
		act_layer_push = QtGui.QAction('Push', self)
		act_layer_clean = QtGui.QAction('Clean', self)

		self.menu_layer_content.addAction(act_layer_swap)
		self.menu_layer_content.addAction(act_layer_pull)
		self.menu_layer_content.addAction(act_layer_push)
		self.menu_layer_content.addAction(act_layer_clean)
		'''
		self.menu_layer_content.addSeparator()
		self.menu_layer_content.addAction(act_layer_push_shapes)
		self.menu_layer_content.addAction(act_layer_push_metrics)
		self.menu_layer_content.addAction(act_layer_push_guides)
		self.menu_layer_content.addAction(act_layer_push_anchors)
		self.menu_layer_content.addSeparator()
		self.menu_layer_content.addAction(act_layer_pull_shapes)
		self.menu_layer_content.addAction(act_layer_pull_metrics)
		self.menu_layer_content.addAction(act_layer_pull_guides)
		self.menu_layer_content.addAction(act_layer_pull_anchors)
		'''

		self.menu_layer_elements = QtGui.QMenu('Elements', self)
		act_layer_unlock = QtGui.QAction('Unlock elements', self)
		act_layer_lock = QtGui.QAction('Lock elements', self)

		self.menu_layer_elements.addAction(act_layer_unlock)
		self.menu_layer_elements.addAction(act_layer_lock)

		self.menu_layer_outline = QtGui.QMenu('Outline', self)
		act_layer_copy_outline = QtGui.QAction('Copy Outline', self)
		act_layer_paste_outline = QtGui.QAction('Paste Outline', self)

		self.menu_layer_outline.addAction(act_layer_copy_outline)
		self.menu_layer_outline.addAction(act_layer_paste_outline)
		
		self.menu_layer_view = QtGui.QMenu('View', self)
		act_layer_unfold = QtGui.QAction('Unfold', self)
		act_layer_restore = QtGui.QAction('Fold', self)

		self.menu_layer_view.addAction(act_layer_unfold)
		self.menu_layer_view.addAction(act_layer_restore)

		# -- Set Triggers ------------------------------------
		self.act_layer_add.triggered.connect(lambda: TRLayerActionCollector.layer_add(self.layerSelector))
		self.act_layer_duplicate.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate(self.layerSelector, True))
		self.act_layer_duplicate_mask.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate_mask(self.layerSelector))
		self.act_layer_delete.triggered.connect(lambda: TRLayerActionCollector.layer_delete(self.layerSelector))
		
		#act_layer_set_type_mask.triggered.connect(lambda: TRLayerActionCollector.layer_set_type_mask(self.layerSelector))
		act_layer_set_type_wireframe.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Wireframe'))
		act_layer_set_type_service.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Service'))
		
		'''
		act_layer_push_shapes.triggered.connect(lambda: TRLayerActionCollector.layer_push_shapes(self.layerSelector))
		act_layer_push_metrics.triggered.connect(lambda: TRLayerActionCollector.layer_push_metrics(self.layerSelector))
		act_layer_push_guides.triggered.connect(lambda: TRLayerActionCollector.layer_push_guides(self.layerSelector))
		act_layer_push_anchors.triggered.connect(lambda: TRLayerActionCollector.layer_push_anchors(self.layerSelector))
		act_layer_pull_shapes.triggered.connect(lambda: TRLayerActionCollector.layer_pull_shapes(self.layerSelector))
		act_layer_pull_metrics.triggered.connect(lambda: TRLayerActionCollector.layer_pull_metrics(self.layerSelector))
		act_layer_pull_guides.triggered.connect(lambda: TRLayerActionCollector.layer_pull_guides(self.layerSelector))
		act_layer_pull_anchors.triggered.connect(lambda: TRLayerActionCollector.layer_pull_anchors(self.layerSelector))
		'''

		act_layer_swap.triggered.connect(lambda: TRLayerActionCollector.layer_swap(self.layerSelector))
		act_layer_pull.triggered.connect(lambda: TRLayerActionCollector.layer_pull(self.layerSelector))
		act_layer_push.triggered.connect(lambda: TRLayerActionCollector.layer_push(self.layerSelector))
		act_layer_clean.triggered.connect(lambda: TRLayerActionCollector.layer_clean(self.layerSelector))
		
		act_layer_unlock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self.layerSelector, False))
		act_layer_lock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self.layerSelector, True))
		act_layer_copy_outline.triggered.connect(lambda: TRLayerActionCollector.layer_copy_outline(self.layerSelector))
		act_layer_paste_outline.triggered.connect(lambda: TRLayerActionCollector.layer_paste_outline(self.layerSelector))
		
		act_layer_unfold.triggered.connect(lambda: TRLayerActionCollector.layer_unfold(self.layerSelector))
		act_layer_restore.triggered.connect(lambda: TRLayerActionCollector.layer_restore(self.layerSelector))

		# - Build ----------------------------------------
		scriptDir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
		self.setWindowIcon(QtGui.QIcon(scriptDir + os.path.sep + 'Resource' + os.path.sep + 'typerig-icon.svg'))
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
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_type)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_content)
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_outline)
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_elements)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_view)

		self.layerSelector.lst_layers.menu.popup(QtGui.QCursor.pos())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 700)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()