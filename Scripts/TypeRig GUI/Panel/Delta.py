#FLM: TR: Delta
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import warnings
import os, json
from math import radians
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl import *
from typerig.core.base.message import *

from typerig.core.func.math import linInterp, ratfrac
from typerig.core.func import transform
from typerig.core.objects.array import PointArray
from typerig.core.objects.delta import DeltaArray, DeltaScale

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import *

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Delta', '3.17'

# -- Strings
column_names = ('Layer'+' '*45,'V St.', 'H St.')
masters_group_name = 'Glyph Masters'
axis_group_name = 'Virtual Axis'

# - Sub widgets ------------------------
class TRWLayerTree(QtGui.QTreeWidget):
	def __init__(self, data=None, headers=None):
		super(TRWLayerTree, self).__init__()
		
		if data is not None: self.setTree(data, headers)

	  	self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.setDragDropMode(self.InternalMove)
		#self.setDragDropMode(self.DragDrop)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)

		self.expandAll()
		self.setAlternatingRowColors(True)

	# - Getter/Setter -----------------------
	def setTree(self, data, headers):
		self.blockSignals(True)
		self.clear()
		self.setHeaderLabels(headers)

		# - Insert 
		for key, value in data.items():
			master = QtGui.QTreeWidgetItem(self, [key])

			for item in value:
				new_item = QtGui.QTreeWidgetItem(master, item)
				color_decorator = QtGui.QColor(item[-1]) if not isinstance(item[-1], QtGui.QColor) else item[-1]
				new_item.setData(0, QtCore.Qt.DecorationRole, color_decorator)
				new_item.setFlags(new_item.flags() & ~QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsEditable)
				
		# - Fit data
		for c in range(self.columnCount):
			self.resizeColumnToContents(c)	

		self.invisibleRootItem().setFlags(self.invisibleRootItem().flags() & ~QtCore.Qt.ItemIsDropEnabled)
		self.expandAll()
		self.blockSignals(False)

	def getTree(self):
		returnDict = OrderedDict()
		root = self.invisibleRootItem()

		for i in range(root.childCount()):
			item = root.child(i)
			returnDict[item.text(0)] = [[item.child(n).text(c) for c in range(item.child(n).columnCount())] for n in range(item.childCount())]
		
		return returnDict

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init

		# - Widgets
		# -- Buttons
		self.edt_glyphName = QtGui.QLineEdit()
		
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_setAxis = QtGui.QPushButton('Set &Axis')
		self.btn_resetAxis = QtGui.QPushButton('Reset Axis')
		self.btn_getVstem = QtGui.QPushButton('Get &Vertical Stems')
		self.btn_getHstem = QtGui.QPushButton('Get &Horizontal Stems')
		self.btn_setLayer = QtGui.QPushButton('Layer changed')
		self.btn_execute = QtGui.QPushButton('Execute')
		
		# -- Options
		self.btn_opt_extrapolate = QtGui.QPushButton('Extrapolate')
		self.btn_opt_italic = QtGui.QPushButton('Italic')
		self.btn_opt_update_preview = QtGui.QPushButton('Live preview')
		self.btn_opt_update_layer = QtGui.QPushButton('Auto Layer')
		self.btn_opt_metrics = QtGui.QPushButton('Metrics')
		self.btn_opt_anchors = QtGui.QPushButton('Anchors')

		self.btn_opt_extrapolate.setCheckable(True)
		self.btn_opt_italic.setCheckable(True) 
		self.btn_opt_update_preview.setCheckable(True)
		self.btn_opt_update_layer.setCheckable(True)
		self.btn_opt_metrics.setCheckable(True)
		self.btn_opt_anchors.setCheckable(True)

		self.btn_opt_update_layer.setEnabled(False)

		self.btn_opt_update_preview.setChecked(True)
		self.btn_opt_metrics.setChecked(True)
		self.btn_opt_anchors.setChecked(True)

		self.btn_refresh.clicked.connect(self.refresh)
		self.btn_setAxis.clicked.connect(self.set_axis)
		self.btn_resetAxis.clicked.connect(self.reset_axis)
		self.btn_getVstem.clicked.connect(lambda: self.get_stem(False))
		self.btn_getHstem.clicked.connect(lambda: self.get_stem(True))
		self.btn_setLayer.clicked.connect(self.set_current_layer)
		self.btn_execute.clicked.connect(lambda: self.execute_scale(True))

		# -- Layer selector
		self.layer_selector = TRWLayerTree()
		
		# -- Actions (Context Menu)
		self.layer_selector.menu = QtGui.QMenu(self)
		self.layer_selector.menu.setTitle('Actions:')

		act_setAxis = QtGui.QAction('Set Axis', self)
		act_resetAxis = QtGui.QAction('Reset Axis', self)
		act_getVstem = QtGui.QAction('Get Vertical Stems', self)
		act_getHstem = QtGui.QAction('Get Horizontal Stems', self)

		self.layer_selector.menu.addAction(act_getVstem)
		self.layer_selector.menu.addAction(act_getHstem)
		self.layer_selector.menu.addSeparator()	
		self.layer_selector.menu.addAction(act_setAxis)
		self.layer_selector.menu.addAction(act_resetAxis)

		act_setAxis.triggered.connect(self.set_axis)
		act_resetAxis.triggered.connect(self.reset_axis)
		act_getVstem.triggered.connect(lambda: self.get_stem(False))
		act_getHstem.triggered.connect(lambda: self.get_stem(True))

		
		# - Build Layout
		layoutV = QtGui.QVBoxLayout()

		# -- Head
		layoutH = QtGui.QGridLayout()
		layoutH.addWidget(QtGui.QLabel('G:'),			0, 0, 1, 1)
		layoutH.addWidget(self.edt_glyphName,			0, 1, 1, 6)
		layoutH.addWidget(self.btn_refresh,				0, 7, 1, 3)
		layoutV.addLayout(layoutH)

		# -- Layer selector
		layoutV.addWidget(self.layer_selector)
		
		# -- Delta Setup controls
		self.fld_setup = TRCollapsibleBox('Delta Setup') 
		layoutG = QtGui.QGridLayout()
		layoutG.addWidget(QtGui.QLabel('Axis Setup:'),		0, 0, 1, 10)
		layoutG.addWidget(self.btn_getVstem, 				1, 0, 1, 5)
		layoutG.addWidget(self.btn_getHstem, 				1, 5, 1, 5)
		layoutG.addWidget(self.btn_resetAxis, 				2, 0, 1, 5)
		layoutG.addWidget(self.btn_setAxis, 				2, 5, 1, 5)

		layoutG.addWidget(QtGui.QLabel('Options:'),			3, 0, 1, 10)
		layoutG.addWidget(self.btn_opt_extrapolate, 		4, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_italic, 				4, 5, 1, 5)
		layoutG.addWidget(self.btn_opt_anchors, 			5, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_metrics, 			5, 5, 1, 5)
		layoutG.addWidget(self.btn_opt_update_preview, 		7, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_update_layer, 		7, 5, 1, 5)
		
		self.fld_setup.setContentLayout(layoutG)
		layoutV.addWidget(self.fld_setup)

		# -- Set Sliders
		self.fld_weight = TRCollapsibleBox('Stem Weight Control')
		self.fld_scale = TRCollapsibleBox('Compensative scaler')

		lay_weight = QtGui.QVBoxLayout()
		lay_scale = QtGui.QVBoxLayout()
		
		# --- Mixer
		lay_weight.addWidget(QtGui.QLabel('Vertical Stem Weight (X):'))
		self.mixer_dx = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dx.sld_axis.valueChanged.connect(self.execute_scale)		
		lay_weight.addLayout(self.mixer_dx)
		lay_weight.addSpacing(10)
		
		lay_weight.addWidget(QtGui.QLabel('Horizontal Stem Weight (Y):'))
		self.mixer_dy = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dy.sld_axis.valueChanged.connect(self.execute_scale)		
		lay_weight.addLayout(self.mixer_dy)
		
		self.fld_weight.setContentLayout(lay_weight)
		layoutV.addWidget(self.fld_weight)

		# --- Scaler
		lay_scale.addWidget(QtGui.QLabel('Width'))
		self.scalerX = TRSliderCtrl('1', '200', '100', 1)
		self.scalerX.sld_axis.valueChanged.connect(self.execute_scale)		
		lay_scale.addLayout(self.scalerX)
		lay_scale.addSpacing(10)

		lay_scale.addWidget(QtGui.QLabel('Height'))
		self.scalerY = TRSliderCtrl('1', '200', '100', 1)
		self.scalerY.sld_axis.valueChanged.connect(self.execute_scale)		
		lay_scale.addLayout(self.scalerY)

		self.fld_scale.setContentLayout(lay_scale)
		layoutV.addWidget(self.fld_scale)
		
		# -- Tail 
		layoutE = QtGui.QHBoxLayout()
		layoutE.addWidget(self.btn_setLayer)
		layoutE.addWidget(self.btn_execute)
		layoutV.addLayout(layoutE)

		self.__lbl_warn = QtGui.QLabel('')
		layoutV.addWidget(self.__lbl_warn)
		self.__lbl_warn.hide()

		# -- Finish
		self.refresh()
		self.setLayout(layoutV)
		self.setMinimumSize(300, self.sizeHint.height())
		
	# - Functions -----------------------------------------
	# -- Internal
	def contextMenuEvent(self, event):
		self.layer_selector.menu.popup(QtGui.QCursor.pos())	

	# -- Special
	def __where(self, data, search, ret=1):
		for item in data:
			if search == item[0]: return item[ret]
		
		warnings.warn('Axis missing layer: %s!' %search, TRDeltaAxisWarning)
		return 0

	def __get_layers(self, glyph):
		return_data = []
		return_data.append((masters_group_name, [(layer.name, '', '', layer.wireframeColor) for layer in reversed(glyph.masters())]))
		return_data.append((axis_group_name,[]))
		return OrderedDict(return_data)

	def __doCheck(self):
		if self.active_glyph.fg.id != fl6.CurrentGlyph().id and self.active_glyph.fl.name != fl6.CurrentGlyph().name:
			warnings.warn('Glyph mismatch! No action taken! Forcing refresh!', GlyphWarning)
			self.refresh()
			return 0
		return 1

	# -- Operation
	def refresh(self):
		# - Init
		self.axis_points = []
		self.axis_stems = []
		self.data_glyphs = getProcessGlyphs(pMode)
		self.data_glyphs = [glyph for glyph in self.data_glyphs if not glyph.isEmpty()]
		self.glyph_arrays = {}
		self.glyph_arrays_service = {}

		self.active_glyph = eGlyph()
		self.active_font = pFont()
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas(True)

		self.working_names = '; '.join([glyph.name for glyph in self.data_glyphs]) if len(self.data_glyphs) > 1 else self.active_glyph.name
		self.edt_glyphName.setText(self.working_names)
				
		if len(self.active_font.masters()) > 1:
			# - Activate
			self.__lbl_warn.setText('')
			self.__lbl_warn.setStyleSheet('')
			self.btn_setAxis.setEnabled(True)
			self.btn_getVstem.setEnabled(True)
			self.btn_getHstem.setEnabled(True)

			self.mixer_dx.reset()
			self.mixer_dy.reset()
			self.scalerX.reset()
			self.scalerY.reset()
		else:
			# - Deactivate
			self.__lbl_warn.show()
			self.__lbl_warn.setText('<b>Insufficient number of Master layers!</b><br>Delta Panel is currently disabled!')
			self.__lbl_warn.setStyleSheet('padding: 10; font-size: 10pt; background: lightpink;')
			self.btn_setAxis.setEnabled(False)
			self.btn_getVstem.setEnabled(False)
			self.btn_getHstem.setEnabled(False)

		self.masters_data = self.__get_layers(self.active_glyph)
		self.layer_selector.setTree(self.masters_data, column_names)

	def get_stem(self, get_y=False):
		if self.__doCheck():
			self.masters_data = self.layer_selector.getTree()

			for group, data in self.masters_data.items():
				for layer_data in data:
					try:
						selection = self.active_glyph.selectedNodes(layer_data[0], True)
						
						if get_y:
							layer_data[2] = abs(selection[0].y - selection[-1].y)
						else:
							layer_data[1] = abs(selection[0].x - selection[-1].x)
					except IndexError:
						warnings.warn('Missing or incompatible layer: %s!' %layer_data[0], LayerWarning)
						continue

			self.layer_selector.setTree(OrderedDict(self.masters_data), column_names)
	
	def set_current_layer(self):
		self.mixer_dx.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 1))))
		self.mixer_dy.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 2))))
		self.mixer_dx.refreshSlider()
		self.mixer_dy.refreshSlider()

	def reset_axis(self):
		self.masters_data = self.layer_selector.getTree()
		self.masters_data[masters_group_name] += self.masters_data[axis_group_name]
		self.masters_data[axis_group_name] = []
		self.layer_selector.setTree(self.masters_data, column_names)

	def set_axis(self):
		self.masters_data = self.layer_selector.getTree()
		self.axis_data = self.masters_data[axis_group_name]

		if len(self.axis_data):
			# - Init
			self.axis_stems = []
			for layer_data in self.axis_data:
				try:
					x_stem, y_stem = float(layer_data[1]), float(layer_data[2])
					self.axis_stems.append([(x_stem, y_stem)])

				except ValueError:
					warnings.warn('Missing or invalid stem data!', TRDeltaStemWarning)
					return

			for wGlyph in self.data_glyphs:
				temp_outline = [wGlyph._getPointArray(layer_data[0]) for layer_data in self.axis_data]
				temp_service = [wGlyph._getServiceArray(layer_data[0]) for layer_data in self.axis_data]
				self.glyph_arrays[wGlyph.name] = DeltaScale(temp_outline, self.axis_stems)
				self.glyph_arrays_service[wGlyph.name] = DeltaScale(temp_service, self.axis_stems)

			# - Set Sliders
			# -- X
			self.mixer_dx.edt_0.setText(round(float(self.axis_data[0][1])))
			self.mixer_dx.edt_1.setText(round(float(self.axis_data[-1][1])))
			self.mixer_dx.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 1))))
			self.mixer_dx.refreshSlider()
			# -- Y
			self.mixer_dy.edt_0.setText(round(float(self.axis_data[0][2])))
			self.mixer_dy.edt_1.setText(round(float(self.axis_data[-1][2])))
			self.mixer_dy.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 2))))
			self.mixer_dy.refreshSlider()

			# - Build
			self.active_font.updateObject(self.active_font.fl, 'Glyph(s): {} Axis :{} @ {}'.format(self.working_names, ' :'.join([item[0] for item in self.axis_data]), self.active_glyph.layer().name))
	
	def execute_scale(self, force_preview=False):
		if len(self.glyph_arrays.keys()):
			if self.btn_opt_update_preview.isChecked() or force_preview:
				# - Stems
				curr_sw_dx = float(self.mixer_dx.sld_axis.value)
				curr_sw_dy = float(self.mixer_dy.sld_axis.value)

				# - Scaling
				sx = float(self.scalerX.sld_axis.value)/100.
				sy = float(self.scalerY.sld_axis.value)/100.
				
				# - Options
				opt_extrapolate = self.btn_opt_extrapolate.isChecked()
				opt_italic = radians(-float(self.active_font.italic_angle)) if self.btn_opt_italic.isChecked() else 0.
				opt_metrics = self.btn_opt_metrics.isChecked()
				opt_anchors = self.btn_opt_anchors.isChecked()

				# - Process
				for wGlyph in self.data_glyphs:
					
					outline_scale = self.glyph_arrays[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
					wGlyph._setPointArray(outline_scale)
						
					service_scale = self.glyph_arrays_service[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
					wGlyph._setServiceArray(service_scale, set_metrics=opt_metrics, set_anchors=opt_anchors)
						
					wGlyph.update()
					
					self.active_canvas.refreshAll()
				
				if opt_metrics: self.active_font.fl.changed()

	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 280, 800)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()