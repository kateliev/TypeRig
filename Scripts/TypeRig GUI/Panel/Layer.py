#FLM: TR: Layers
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
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
from typerig.proxy.fl.actions.layer import TRLayerActionCollector
from typerig.core.func.math import linInterp as lerp
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import *

# - Init --------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Layers', '2.40'

# -- Inital config for Get Layers dialog
column_names = ('Name', 'Type', 'Color')
column_init = (None, None, QtGui.QColor(0, 255, 0, 10))
init_table_dict = {1 : OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 10), 'Service': QtGui.QColor(0, 0, 255, 10), 'Mask': QtGui.QColor(255, 0, 0, 10)}

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
		
		'''
		# !!! Hide until UI facelift 
		self.tools_multiedit = TRCollapsibleBox('Transform (Layers selected)')
		self.tools_multiedit.setContentLayout(self.unfoldLayers)
		layoutV.addWidget(self.tools_multiedit)
		'''

		self.tools_blend = TRCollapsibleBox('Blend (Selection to Active Layer)')
		self.tools_blend.setContentLayout(self.blendTools)
		layoutV.addWidget(self.tools_blend)

		# -- Menus and Actions -----------------------------------
		# !!! TODO: Add metrics, anchors, guidelines and etc...

		# --- Layer operations
		self.act_layer_add = QtGui.QAction('New', self)
		self.act_layer_duplicate = QtGui.QAction('Duplicate', self)
		self.act_layer_duplicate_mask = QtGui.QAction('Duplicate to Mask', self)
		self.act_layer_delete = QtGui.QAction('Remove', self)
		self.act_layer_visible = QtGui.QAction('Toggle Visible', self)
		self.act_layer_visible_on = QtGui.QAction('Set Visible', self)
		self.act_layer_visible_off = QtGui.QAction('Set Invisible', self)

		self.menu_layer_type = QtGui.QMenu('Type', self)
		act_layer_set_type_mask = QtGui.QAction('Set as Mask', self)
		act_layer_set_type_wireframe = QtGui.QAction('Set as Wireframe', self)
		act_layer_set_type_service = QtGui.QAction('Set as Service', self)

		self.menu_layer_type.addAction(act_layer_set_type_mask)
		self.menu_layer_type.addAction(act_layer_set_type_wireframe)
		self.menu_layer_type.addAction(act_layer_set_type_service)
		self.menu_layer_type.addAction(act_layer_set_type_service)

		# --- Element (Shape) operations
		self.menu_layer_element = QtGui.QMenu('Element', self)
		
		act_layer_element_swap = QtGui.QAction('Swap Elements', self)
		act_layer_element_pull = QtGui.QAction('Pull Elements', self)
		act_layer_element_push = QtGui.QAction('Push Elements', self)
		act_layer_element_clean = QtGui.QAction('Clean Elements', self)
		act_layer_unlock = QtGui.QAction('Unlock elements', self)
		act_layer_lock = QtGui.QAction('Lock elements', self)

		self.menu_layer_element.addAction(act_layer_element_swap)
		self.menu_layer_element.addAction(act_layer_element_pull)
		self.menu_layer_element.addAction(act_layer_element_push)
		self.menu_layer_element.addAction(act_layer_element_clean)
		self.menu_layer_element.addSeparator()
		self.menu_layer_element.addAction(act_layer_unlock)
		self.menu_layer_element.addAction(act_layer_lock)
		
		# --- Contour operations
		self.menu_layer_outline = QtGui.QMenu('Contour', self)
		
		act_layer_contour_pull = QtGui.QAction('Pull Nodes', self)
		act_layer_contour_push = QtGui.QAction('Push Nodes', self)
		act_layer_contour_copy = QtGui.QAction('Copy Nodes', self)
		act_layer_contour_paste = QtGui.QAction('Paste Nodes', self)
		act_layer_contour_paste_byName = QtGui.QAction('Paste by Layer', self)

		self.menu_layer_outline.addAction(act_layer_contour_pull)
		self.menu_layer_outline.addAction(act_layer_contour_push)
		self.menu_layer_outline.addSeparator()
		self.menu_layer_outline.addAction(act_layer_contour_copy)
		self.menu_layer_outline.addAction(act_layer_contour_paste)
		self.menu_layer_outline.addAction(act_layer_contour_paste_byName)
		
		# --- Layer Unfold/Stack Operations
		self.menu_layer_view = QtGui.QMenu('View', self)
		act_layer_side_by_side = QtGui.QAction('Side by side', self)
		self.menu_layer_view.addAction(act_layer_side_by_side)

		# -- Set Triggers ------------------------------------
		self.act_layer_add.triggered.connect(lambda: TRLayerActionCollector.layer_add(self.layerSelector))
		self.act_layer_duplicate.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate(self.layerSelector, True))
		self.act_layer_duplicate_mask.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate_mask(self.layerSelector))
		self.act_layer_delete.triggered.connect(lambda: TRLayerActionCollector.layer_delete(self.layerSelector))
		self.act_layer_visible.triggered.connect(lambda: TRLayerActionCollector.layer_toggle_visible(self.layerSelector))
		self.act_layer_visible_on.triggered.connect(lambda: TRLayerActionCollector.layer_set_visible(self.layerSelector, True))
		self.act_layer_visible_off.triggered.connect(lambda: TRLayerActionCollector.layer_set_visible(self.layerSelector, False))
		
		act_layer_set_type_wireframe.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Wireframe'))
		act_layer_set_type_service.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self.layerSelector, 'Service'))

		act_layer_element_swap.triggered.connect(lambda: TRLayerActionCollector.layer_swap(self.layerSelector))
		act_layer_element_pull.triggered.connect(lambda: TRLayerActionCollector.layer_pull(self.layerSelector))
		act_layer_element_push.triggered.connect(lambda: TRLayerActionCollector.layer_push(self.layerSelector))
		act_layer_element_clean.triggered.connect(lambda: TRLayerActionCollector.layer_clean(self.layerSelector))
		
		act_layer_unlock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self.layerSelector, False))
		act_layer_lock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self.layerSelector, True))
		
		act_layer_contour_pull.triggered.connect(lambda: TRLayerActionCollector.layer_ditto(self.layerSelector, False))
		act_layer_contour_push.triggered.connect(lambda: TRLayerActionCollector.layer_ditto(self.layerSelector, True))
		act_layer_contour_copy.triggered.connect(lambda: TRLayerActionCollector.layer_copy_outline(self.layerSelector))
		act_layer_contour_paste_byName.triggered.connect(lambda: TRLayerActionCollector.layer_paste_outline(self.layerSelector))
		act_layer_contour_paste.triggered.connect(lambda: TRLayerActionCollector.layer_paste_outline_selection(self.layerSelector))
		
		act_layer_side_by_side.triggered.connect(lambda: TRLayerActionCollector.layer_side_by_side(self.layerSelector))

		# - Build ----------------------------------------
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
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_visible_on)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_visible_off)
		self.layerSelector.lst_layers.menu.addAction(self.act_layer_visible)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_type)
		self.layerSelector.lst_layers.menu.addSeparator()
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_element)
		self.layerSelector.lst_layers.menu.addMenu(self.menu_layer_outline)
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