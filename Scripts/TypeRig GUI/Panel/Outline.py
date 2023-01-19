#FLM: TR: Outline
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import warnings
from collections import OrderedDict
from math import degrees

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.application.app import pWorkspace

from PythonQt import QtCore, QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomLabel, CustomPushButton, TRFlowLayout, getProcessGlyphs, TRTableView
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init --------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Outline', '3.1'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

active_workspace = pWorkspace()
# - Sub widgets ------------------------
class TRContourSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(TRContourSelect, self).__init__()

		# -- Init
		self.table_dict = {0:{0:None}} # Empty table
		self.layer_names = [] # Empty layer list
		self.table_columns = 'Index, Shape, Contour, X, Y, Type, Distance, Angle'.split(', ')

		# -- Widgets
		# --- Head
		box_head = QtGui.QGroupBox()
		box_head.setObjectName('box_group')
		
		lay_head = QtGui.QGridLayout()
		lay_head.setContentsMargins(0, 0, 0, 0)

		lbl_head = CustomLabel('label', obj_name='lbl_panel')
		lay_head.addWidget(lbl_head, 0,0,1,1)

		self.edt_glyphName = QtGui.QLineEdit()
		lay_head.addWidget(self.edt_glyphName, 0,1,1,5)

		self.btn_refresh = CustomPushButton('refresh', tooltip='Refresh', obj_name='btn_panel')
		self.btn_refresh.clicked.connect(self.refresh)
		lay_head.addWidget(self.btn_refresh, 0,6,1,1)

		lbl_layer = CustomLabel('layer_master', obj_name='lbl_panel')
		lay_head.addWidget(lbl_layer, 1,0,1,1)
		
		self.cmb_layer = QtGui.QComboBox()
		lay_head.addWidget(self.cmb_layer,	1,1,1,5)

		self.btn_apply = CustomPushButton('action_play', tooltip='Refresh', obj_name='btn_panel')
		self.btn_apply.clicked.connect(self.refresh)
		lay_head.addWidget(self.btn_apply, 1,6,1,1)

		box_head.setLayout(lay_head)
		self.addWidget(box_head)
		
		# -- Row options
		box_opt = QtGui.QGroupBox()
		box_opt.setObjectName('box_group')
		
		self.lay_opt = TRFlowLayout(spacing=10)
		self.lay_opt.setContentsMargins(0, 0, 0, 0)

		tooltip_button = 'Node Index'
		self.opt_view_index = CustomPushButton('select_list', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_index)
		self.opt_view_index.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Element Index'
		self.opt_view_shape = CustomPushButton('shape', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_shape)
		self.opt_view_shape.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Contour Index'
		self.opt_view_contour = CustomPushButton('contour', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_contour)
		self.opt_view_contour.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Node Coordinates'
		self.opt_view_coords = CustomPushButton('coordinates', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_coords)
		self.opt_view_coords.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Node Type'
		self.opt_view_type = CustomPushButton('node', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_type)
		self.opt_view_type.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Distance to previous node'
		self.opt_view_dist = CustomPushButton('distance', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_dist)
		self.opt_view_dist.clicked.connect(lambda: self.toggle_columns())

		tooltip_button = 'Angle to previous node'
		self.opt_view_angle = CustomPushButton('angle', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_opt.addWidget(self.opt_view_angle)
		self.opt_view_angle.clicked.connect(lambda: self.toggle_columns())

		box_opt.setLayout(self.lay_opt)
		self.addWidget(box_opt)

		# -- Node List Table
		self.tab_nodes = TRTableView(self.table_dict)
		self.addWidget(self.tab_nodes)

		self.btn_refresh.clicked.connect(lambda: self.refresh())
		self.cmb_layer.currentIndexChanged.connect(lambda: self.changeLayer())

		# -- Table Styling
		self.tab_nodes.horizontalHeader().setStretchLastSection(False)
		self.tab_nodes.setSortingEnabled(True)
		self.tab_nodes.horizontalHeader().sortIndicatorChanged.connect(lambda: self.tab_nodes.resizeColumnsToContents())
		self.tab_nodes.verticalHeader().hide()
		self.tab_nodes.resizeColumnsToContents()
		self.tab_nodes.selectionModel().selectionChanged.connect(self.selectionChanged)
		self.tab_nodes.itemChanged.connect(self.valueChanged)

	def toggle_columns(self):
		if len(self.table_dict):
			if self.opt_view_index.isChecked():
				self.tab_nodes.showColumn(0)
			else:
				self.tab_nodes.hideColumn(0)

			if self.opt_view_shape.isChecked():
				self.tab_nodes.showColumn(1)
			else:
				self.tab_nodes.hideColumn(1)

			if self.opt_view_contour.isChecked():
				self.tab_nodes.showColumn(2)
			else:
				self.tab_nodes.hideColumn(2)

			if self.opt_view_coords.isChecked():
				self.tab_nodes.showColumn(3)
				self.tab_nodes.showColumn(4)
			else:
				self.tab_nodes.hideColumn(3)
				self.tab_nodes.hideColumn(4)

			if self.opt_view_type.isChecked():
				self.tab_nodes.showColumn(5)
			else:
				self.tab_nodes.hideColumn(5)

			if self.opt_view_dist.isChecked():
				self.tab_nodes.showColumn(6)
			else:
				self.tab_nodes.hideColumn(6)

			if self.opt_view_angle.isChecked():
				self.tab_nodes.showColumn(7)
			else:
				self.tab_nodes.hideColumn(7)


	def refresh(self, layer=None):
		# - Init
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
				
		self.table_dict = {}
		node_count = 0

		# - Populate layers
		if layer is None:
			self.layer_names = [item.name for item in self.glyph.layers() if '#' not in item.name]
			self.cmb_layer.clear()
			self.cmb_layer.addItems(self.layer_names)
			self.cmb_layer.setCurrentIndex(self.layer_names.index(self.glyph.activeLayer().name))			
			
		# - Populate table
		try: # Dirty Quick Fix - Solve later
			for sID, shape in enumerate(self.glyph.shapes(layer)):
				for cID, contour in enumerate(shape.contours):
					for nID, node in enumerate(contour.nodes()):
						x = round(node.x, 2)
						y = round(node.y, 2)

						node_type = node.type
						if node_type == 'on': node_type = ['sharp', 'smooth'][node.smooth]
							
						distance = round(eNode(node).distanceToPrev(),2)
						angle = round(degrees(eNode(node).angleToPrev()),1)
						
						table_values = [node_count, sID, cID, x, y, node_type, distance, angle]
						
						self.table_dict[node_count] = OrderedDict(zip(self.table_columns, table_values))
						node_count += 1
			
			self.tab_nodes.setTable(self.table_dict, (False, False))
			self.tab_nodes.resizeColumnsToContents()
		
		except AttributeError: 
			pass
		
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			warnings.warn('Glyph mismatch! No action taken! Forcing refresh!', GlyphWarning)
			self.refresh()
			return 0
		return 1

	def changeLayer(self):
		if self.doCheck():
			self.refresh(self.cmb_layer.currentText)

	def selectionChanged(self):
		if self.doCheck():	
			if self.cmb_layer.currentText == self.glyph.activeLayer().name:
				# - Prepare
				self.glyph.fl.unselectAllNodes()

				# - Process
				for cel_coords in self.tab_nodes.selectionModel().selectedIndexes:
					selected_nid = int(self.tab_nodes.item(cel_coords.row(), 0).text())
					self.glyph.nodes(self.cmb_layer.currentText)[selected_nid].selected = True
				
				# - Finish
				self.glyph.update()
				active_workspace.getCanvas(True).refreshAll()
				#self.glyph.updateObject(self.glyph.fl, verbose=False)

	def valueChanged(self, item):
		if self.doCheck():
			try: # Dirty Quick Fix - Solve later
				# - Init
				x_col, y_col = self.table_columns.index('X'), self.table_columns.index('Y')
				active_nid = int(self.tab_nodes.item(item.row(), 0).text())

				# - Process
				if item.column() == x_col or item.column() == y_col:
					new_x = float(self.tab_nodes.item(item.row(), x_col).text())
					new_y = float(self.tab_nodes.item(item.row(), y_col).text())

					active_node = eNode(self.glyph.nodes(self.cmb_layer.currentText)[active_nid])
					active_node.reloc(new_x, new_y)

					# -- Finish
					self.glyph.update()
					self.glyph.updateObject(self.glyph.fl, verbose=False)
			
			except AttributeError:
				pass

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init 
		self.setStyleSheet(css_tr_button)

		layoutV = QtGui.QVBoxLayout()
		self.outline = TRContourSelect()
		layoutV.addLayout(self.outline)
		
		# - Build
		#layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()