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

from PythonQt import QtCore, QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, TRTransformCtrl, CustomLabel, CustomSpinLabel, CustomPushButton, TRFlowLayout, TRSliderCtrl, TRCustomSpinController
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init --------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Layers', '2.55'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# -- Inital config for Get Layers dialog
column_names = ('Name', 'Type', 'Color')
column_init = (None, None, QtGui.QColor(0, 255, 0, 10))
init_table_dict = {1 : OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 10), 'Service': QtGui.QColor(0, 0, 255, 10), 'Mask': QtGui.QColor(255, 0, 0, 10)}

# - Sub widgets ------------------------
class TRWMasterTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRWMasterTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
		self.header = self.horizontalHeader()
		self.header.setDefaultAlignment(QtCore.Qt.AlignLeft)

		# - Set 
		self.setTable(data)		
	
		# - Styling
		self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)

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
					newitem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setData(QtCore.Qt.DecorationRole, data[layer]['Color'])

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
		return [self.item(index.row(), 0).text() for index in self.selectionModel().selectedRows()]

# - Widgets ---------------------------	
class TRLayerActions(QtGui.QWidget):
	def __init__(self):
		super(TRLayerActions, self).__init__()

		# - Init
		self.glyph = None
		self.lerp_array = []
		self.active_workspace = None
		self.active_canvas = None
		
		lay_main = QtGui.QVBoxLayout()
		lay_main.setContentsMargins(0,0,0,0)

		# -- Head
		box_head = QtGui.QGroupBox()
		box_head.setObjectName('box_group')
		lay_head = QtGui.QHBoxLayout()

		lbl_head = CustomLabel('label', obj_name='lbl_panel')
		lay_head.addWidget(lbl_head)
		lay_head.setContentsMargins(0, 0, 0, 0)

		self.edt_glyphName = QtGui.QLineEdit()
		lay_head.addWidget(self.edt_glyphName)

		self.btn_refresh = CustomPushButton('refresh', tooltip='Refresh', obj_name='btn_panel')
		self.btn_refresh.clicked.connect(self.refresh)
		lay_head.addWidget(self.btn_refresh)

		box_head.setLayout(lay_head)
		lay_main.addWidget(box_head)

		# -- Layer List
		self.lst_layers = TRWMasterTableView(init_table_dict)
		lay_main.addWidget(self.lst_layers)
		self.refresh()

		# - Layer options
		box_options = QtGui.QGroupBox()
		box_options.setObjectName('box_group')

		lay_options = TRFlowLayout(spacing=10)

		'''
		tooltip_button = 'Outline'
		self.chk_outline = CustomPushButton("bbox", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_outline)

		tooltip_button = 'Guidelines'
		self.chk_guides = CustomPushButton("guide_horizontal", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_guides)

		tooltip_button = 'Anchors'
		self.chk_anchors = CustomPushButton("icon_anchor", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_anchors)

		tooltip_button = 'Metrics LSB'
		self.chk_lsb = CustomPushButton("metrics_lsb", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_lsb)

		tooltip_button = 'Advance width'
		self.chk_adv = CustomPushButton("metrics_advance", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_adv)

		tooltip_button = 'Metrics RSB'
		self.chk_rsb = CustomPushButton("metrics_rsb", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_rsb)
		'''

		tooltip_button = 'Show interpolation controls'
		self.chk_interpolate = CustomPushButton("interpolate", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_interpolate)
		

		tooltip_button = 'Show transformation controls'
		self.chk_transform = CustomPushButton("diagonal_bottom_up", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_transform)


		box_options.setLayout(lay_options)
		lay_main.addWidget(box_options)

		# - Transform controls -------------------
		self.ctrl_transform = TRTransformCtrl()
		lay_main.addWidget(self.ctrl_transform)

		tooltip_button = "Transform selected contours"
		self.btn_transform = CustomPushButton("action_play", tooltip=tooltip_button, obj_name='btn_panel')
		self.ctrl_transform.lay_options.addWidget(self.btn_transform)
		self.btn_transform.clicked.connect(self.layer_transform)

		# - Interpolation controls ---------------
		lay_lerp_options = QtGui.QHBoxLayout()

		tooltip_button = 'Set axis'
		self.btn_axis_set = CustomPushButton('axis_set', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_lerp_options.addWidget(self.btn_axis_set)
		self.btn_axis_set.clicked.connect(lambda: self.__lerp_set_axis())

		tooltip_button = 'Reset axis'
		self.btn_axis_reset = CustomPushButton('axis_remove', tooltip=tooltip_button, obj_name='btn_panel')
		lay_lerp_options.addWidget(self.btn_axis_reset)
		self.btn_axis_reset.clicked.connect(lambda: self.__lerp_reset_axis())

		tooltip_button = 'Swap axis masters'
		self.btn_axis_swap = CustomPushButton('contour_reverse', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_lerp_options.addWidget(self.btn_axis_swap)
		
		lay_lerp_options.addStretch()

		tooltip_button = 'Anisotropic interpolation coefficient'
		self.spn_axis_anisotropy = CustomSpinLabel('delta_y', (0., 2., 1., .01), tooltip_button, None, ('spn_panel_inf', 'lbl_panel'))
		lay_lerp_options.addWidget(self.spn_axis_anisotropy)

		self.cpn_lerp = TRCustomSpinController('interpolate', (0, 1000., 0, 1.), '', 'Time along axis')
		self.cpn_lerp.lay_box.addLayout(lay_lerp_options) # Inject the above option buttons into the control
		lay_main.addWidget(self.cpn_lerp)
		self.cpn_lerp.spin_box.valueChanged.connect(lambda: self.layer_lerp())

		# -- Set toggle controls 
		self.ctrl_transform.hide()
		self.cpn_lerp.hide()
		self.chk_interpolate.clicked.connect(lambda: self.__toggle(self.chk_interpolate, self.cpn_lerp))
		self.chk_transform.clicked.connect(lambda: self.__toggle(self.chk_transform, self.ctrl_transform))
		
		# - Layer actions and menu
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
		self.act_layer_add.triggered.connect(lambda: TRLayerActionCollector.layer_add(self))
		self.act_layer_duplicate.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate(self, True))
		self.act_layer_duplicate_mask.triggered.connect(lambda: TRLayerActionCollector.layer_duplicate_mask(self))
		self.act_layer_delete.triggered.connect(lambda: TRLayerActionCollector.layer_delete(self))
		self.act_layer_visible.triggered.connect(lambda: TRLayerActionCollector.layer_toggle_visible(self))
		self.act_layer_visible_on.triggered.connect(lambda: TRLayerActionCollector.layer_set_visible(self, True))
		self.act_layer_visible_off.triggered.connect(lambda: TRLayerActionCollector.layer_set_visible(self, False))
		
		act_layer_set_type_mask.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self, 'Mask'))
		act_layer_set_type_wireframe.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self, 'Wireframe'))
		act_layer_set_type_service.triggered.connect(lambda: TRLayerActionCollector.layer_set_type(self, 'Service'))

		act_layer_element_swap.triggered.connect(lambda: TRLayerActionCollector.layer_swap(self))
		act_layer_element_pull.triggered.connect(lambda: TRLayerActionCollector.layer_pull(self))
		act_layer_element_push.triggered.connect(lambda: TRLayerActionCollector.layer_push(self))
		act_layer_element_clean.triggered.connect(lambda: TRLayerActionCollector.layer_clean(self))
		
		act_layer_unlock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self, False))
		act_layer_lock.triggered.connect(lambda: TRLayerActionCollector.layer_unlock(self, True))
		
		act_layer_contour_pull.triggered.connect(lambda: TRLayerActionCollector.layer_ditto(self, False))
		act_layer_contour_push.triggered.connect(lambda: TRLayerActionCollector.layer_ditto(self, True))
		act_layer_contour_copy.triggered.connect(lambda: TRLayerActionCollector.layer_copy_outline(self))
		act_layer_contour_paste_byName.triggered.connect(lambda: TRLayerActionCollector.layer_paste_outline(self))
		act_layer_contour_paste.triggered.connect(lambda: TRLayerActionCollector.layer_paste_outline_selection(self))
		act_layer_side_by_side.triggered.connect(lambda: TRLayerActionCollector.layer_side_by_side(self))

		# -- Set Menu 
		self.menu = QtGui.QMenu(self)
		self.menu.setTitle('Actions:')
		
		# -- Build menus
		self.menu.addAction(self.act_layer_add)
		self.menu.addAction(self.act_layer_duplicate)
		self.menu.addAction(self.act_layer_duplicate_mask)
		self.menu.addAction(self.act_layer_delete)
		self.menu.addSeparator()
		self.menu.addAction(self.act_layer_visible_on)
		self.menu.addAction(self.act_layer_visible_off)
		self.menu.addAction(self.act_layer_visible)
		self.menu.addSeparator()
		self.menu.addMenu(self.menu_layer_type)
		self.menu.addSeparator()
		self.menu.addMenu(self.menu_layer_element)
		self.menu.addMenu(self.menu_layer_outline)
		self.menu.addSeparator()
		self.menu.addMenu(self.menu_layer_view)

		# - Finish it
		self.setLayout(lay_main)

	# - Internals ------------------------------------
	def __toggle(self, trigger, widget):
		if trigger.isChecked():
			widget.show()
		else:
			widget.hide()

	def contextMenuEvent(self, event):
		self.menu.popup(QtGui.QCursor.pos())

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
	
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			warnings.warn('Current active glyph: %s\tPanel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg), GlyphWarning)
			warnings.warn('Forcing refresh on panel: %s.' %app_name, TRPanelWarning)
			self.refresh()
			return 0
		return 1

	def __lerp_set_axis(self, reverse=False):
		selection = self.lst_layers.getTable()

		if len(selection) > 1:
			self.active_workspace = pWorkspace()
			self.active_canvas = self.active_workspace.getCanvas(True)
			
			src_array_t0 = self.glyph._getPointArray(selection[0])
			src_array_t1 = self.glyph._getPointArray(selection[1])
			
			self.lerp_array = list(zip(src_array_t0, src_array_t1))
		else:
			warnings.warn('Axis requires exactly two layers to be selected: %s.' %app_name, TRPanelWarning)
			self.btn_axis_set.setChecked(False)
		
	def __lerp_reset_axis(self):
			self.btn_axis_set.setChecked(False)
			self.lerp_array = []

	def __lerp_function(self, t0, t1, tx, ty):
		if self.btn_axis_swap.isChecked():
			return (lerp(t1[0], t0[0], tx), lerp(t1[1], t0[1], ty))
		else:
			return (lerp(t0[0], t1[0], tx), lerp(t0[1], t1[1], ty))
	
	# - Procedures --------------------------------
	def layer_transform(self):
		selected_layers = self.lst_layers.getTable()

		if self.doCheck() and len(selected_layers):
			for layer_name in selected_layers:
				wLayer = self.glyph.layer(layer_name)
				wBBox = wLayer.boundingBox
				new_transform, org_transform, rev_transform = self.ctrl_transform.getTransform(wBBox)
				wLayer.applyTransform(org_transform)
				wLayer.applyTransform(new_transform)
				wLayer.applyTransform(rev_transform)

			self.glyph.updateObject(self.glyph.fl, ' Glyph: %s; Transform Layers: %s' %(self.glyph.name, '; '.join([layer_name for layer_name in selected_layers])))

	def layer_lerp(self):
		if self.btn_axis_set.isChecked():
			try:
				tx = self.cpn_lerp.getValue()/1000.
				ty = tx * self.spn_axis_anisotropy.input.value
			except ZeroDivisionError:
				tx = 0.
				ty = 0
			
			try:
				dst_array = [self.__lerp_function(item[0], item[1], tx, ty) for item in self.lerp_array]
				self.glyph._setPointArray(dst_array)
				
				self.glyph.update()
				self.active_canvas.refreshAll()

			except IndexError:
				warnings.warn('Current layer is not compatible to axis masers: %s.' %app_name, TRPanelWarning)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init 
		self.setStyleSheet(css_tr_button)

		# -- Layout and widgets
		layoutV = QtGui.QVBoxLayout()

		self.layer_actions = TRLayerActions()
		layoutV.addWidget(self.layer_actions)
		
		# - Build ----------------------------------------
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