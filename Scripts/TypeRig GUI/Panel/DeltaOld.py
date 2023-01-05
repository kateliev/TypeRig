#FLM: TR: Delta Old
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import warnings, os, json, random
from math import radians
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.core.base.message import *
from typerig.core.func.math import linInterp, ratfrac
from typerig.core.func import transform
from typerig.core.objects.array import PointArray
from typerig.core.objects.delta import DeltaArray, DeltaScale

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import * 
from typerig.proxy.fl.gui.dialogs import TR2ComboDLG

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Delta', '4.48'

# -- Strings
tree_column_names = ('Layer','X', 'Y', 'Width', 'Height', 'Color')
tree_masters_group_name = 'Master Layers'
tree_axis_group_name = 'Virtual Axis'
tree_axis_target_name = 'Target Layers'
fileFormats = 'TypeRig Delta Panel Target (*.json);;'

default_sx = '100.'
default_sy = '100.'

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init

		# - Widgets
		# - Glyph list
		self.lst_glyphName = QtGui.QListWidget()
		self.lst_glyphName.setMinimumHeight(50)
		self.lst_glyphName.setAlternatingRowColors(True)
		
		# -- Buttons
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_setAxis = QtGui.QPushButton('Set &Axis')
		self.btn_setAxis_c = QtGui.QPushButton('Set &Axis')
		self.btn_resetAxis = QtGui.QPushButton('Reset Axis')
		self.btn_getVstem = QtGui.QPushButton('Get &Vertical Stems')
		self.btn_getHstem = QtGui.QPushButton('Get &Horizontal Stems')
		self.btn_setLayer = QtGui.QPushButton('Layer changed')
		self.btn_execute = QtGui.QPushButton('Execute')
		self.btn_file_load_patchboard = QtGui.QPushButton('Load')
		self.btn_file_save_patchboard = QtGui.QPushButton('Save')
		
		# -- Options
		self.btn_opt_extrapolate = QtGui.QPushButton('Extrapolate')
		self.btn_opt_italic = QtGui.QPushButton('Italic')
		self.btn_opt_update_preview = QtGui.QPushButton('Live preview')
		self.btn_opt_keep_center = QtGui.QPushButton('Keep Center')
		self.btn_opt_metrics = QtGui.QPushButton('Metrics')
		self.btn_opt_anchors = QtGui.QPushButton('Anchors')
		self.btn_opt_target = QtGui.QPushButton('Use Target')		

		self.btn_opt_extrapolate.setCheckable(True)
		self.btn_opt_italic.setCheckable(True) 
		self.btn_opt_update_preview.setCheckable(True)
		self.btn_opt_keep_center.setCheckable(True)
		self.btn_opt_metrics.setCheckable(True)
		self.btn_opt_anchors.setCheckable(True)
		self.btn_opt_target.setCheckable(True)

		#self.btn_opt_extrapolate.setChecked(True)
		#self.btn_opt_keep_center.setChecked(True)
		#self.btn_opt_target.setChecked(True)

		self.btn_refresh.clicked.connect(self.refresh)
		self.btn_setAxis.clicked.connect(self.set_axis)
		self.btn_setAxis_c.clicked.connect(self.set_axis)
		self.btn_resetAxis.clicked.connect(self.reset_axis)
		self.btn_getVstem.clicked.connect(lambda: self.get_stem(False))
		self.btn_getHstem.clicked.connect(lambda: self.get_stem(True))
		self.btn_setLayer.clicked.connect(self.set_current_layer)
		self.btn_execute.clicked.connect(lambda: self.execute_scale(True))

		self.btn_file_save_patchboard.clicked.connect(self.file_save_patchboard)
		self.btn_file_load_patchboard.clicked.connect(self.file_load_patchboard)

		# -- Layer selector
		self.tree_layer = TRDeltaLayerTree()

		# -- Additional Actions (Context Menu)
		act_setItem_mask = QtGui.QAction('Set mask', self)
		act_setItem_unmask = QtGui.QAction('Remove mask', self)
		act_setItem_value = QtGui.QAction('Set value', self)

		act_setAxis = QtGui.QAction('Set Axis', self)
		act_resetAxis = QtGui.QAction('Reset Axis', self)
		act_getVstem = QtGui.QAction('Get Vertical Stems', self)
		act_getHstem = QtGui.QAction('Get Horizontal Stems', self)

		self.tree_layer.menu.addSeparator()	
		self.tree_layer.menu.addAction(act_setItem_mask )
		self.tree_layer.menu.addAction(act_setItem_unmask )
		self.tree_layer.menu.addAction(act_setItem_value )
		self.tree_layer.menu.addSeparator()	
		self.tree_layer.menu.addAction(act_getVstem)
		self.tree_layer.menu.addAction(act_getHstem)
		self.tree_layer.menu.addSeparator()	
		self.tree_layer.menu.addAction(act_setAxis)
		self.tree_layer.menu.addAction(act_resetAxis)

		act_setItem_mask.triggered.connect(lambda: self.tree_layer._setItemData('mask.', 0, 0, False))
		act_setItem_unmask.triggered.connect(lambda: self.tree_layer._setItemData('mask.', 0, 1, True))
		act_setItem_value.triggered.connect(lambda: self.tree_layer._setItemData(*TR2ComboDLG('Delta Setup', 'Please enter new value for selected columns', 'Value:', 'Column:', tree_column_names).values))
		
		act_setAxis.triggered.connect(lambda: self.set_axis())
		act_resetAxis.triggered.connect(lambda: self.reset_axis())
		
		act_getVstem.triggered.connect(lambda: self.get_stem(False))
		act_getHstem.triggered.connect(lambda: self.get_stem(True))
		
		# - Build Layout
		layoutV = QtGui.QVBoxLayout()

		# -- Layer selector
		layoutV.addWidget(self.tree_layer)

		# -- Set Glyph list
		self.fld_glyphs = TRCollapsibleBox('Process Glyphs')
		lay_glyphs = QtGui.QVBoxLayout()
		lay_glyphs_b = QtGui.QHBoxLayout()
		lay_glyphs.addWidget(self.lst_glyphName)
		lay_glyphs_b.addWidget(self.btn_refresh)
		lay_glyphs_b.addWidget(self.btn_setAxis_c)
		lay_glyphs.addLayout(lay_glyphs_b)
		self.fld_glyphs.setContentLayout(lay_glyphs)
		layoutV.addWidget(self.fld_glyphs)
		
		# -- Delta Setup controls
		self.fld_setup = TRCollapsibleBox('Delta Setup') 
		layoutG = QtGui.QGridLayout()
		layoutG.addWidget(QtGui.QLabel('Axis Setup:'),		0, 0, 1, 10)
		layoutG.addWidget(self.btn_getVstem, 				1, 0, 1, 5)
		layoutG.addWidget(self.btn_getHstem, 				1, 5, 1, 5)
		layoutG.addWidget(self.btn_resetAxis, 				2, 0, 1, 5)
		layoutG.addWidget(self.btn_setAxis, 				2, 5, 1, 5)
		layoutG.addWidget(self.btn_file_save_patchboard,	3, 0, 1, 5)
		layoutG.addWidget(self.btn_file_load_patchboard,	3, 5, 1, 5)

		layoutG.addWidget(QtGui.QLabel('Options:'),			4, 0, 1, 10)
		layoutG.addWidget(self.btn_opt_extrapolate, 		5, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_italic, 				5, 5, 1, 5)
		layoutG.addWidget(self.btn_opt_anchors, 			6, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_metrics, 			6, 5, 1, 5)
		layoutG.addWidget(self.btn_opt_target, 				8, 0, 1, 5)
		layoutG.addWidget(self.btn_opt_keep_center, 		8, 5, 1, 5)
		layoutG.addWidget(self.btn_opt_update_preview, 		9, 0, 1, 10)
		
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
		self.tree_layer.setTree(self.__init_tree(), tree_column_names)
		self.setLayout(layoutV)
		self.setMinimumSize(300, self.sizeHint.height())
		
	# - Functions -----------------------------------------
	# - File operations
	def file_save_patchboard(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Axis Patch-board to file', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tree_layer.getTree(), exportFile)
				output(7, app_name, 'Font: %s; Patch-board saved to: %s.' %(self.active_font.name, fname))
				
	def file_load_patchboard(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load Axis Patch-board from file', fontPath, fileFormats)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
								
				self.masters_data = imported_data
				self.tree_layer.setTree(self.masters_data, tree_column_names)
				output(6, app_name, 'Font: %s; Patch-board loaded from: %s.' %(self.active_font.name, fname))

	# -- Special
	def __where(self, data, search, ret=1):
		for item in data:
			if search == item[0]: return item[ret]
		
		warnings.warn('Axis/target missing layer: %s!' %search, TRDeltaAxisWarning)
		return 0

	def __init_tree(self):
		return_data = []
		return_data.append((tree_masters_group_name, [(layer, '', '', default_sx, default_sy, eGlyph().layer(layer).wireframeColor) for layer in self.active_font.masters()]))
		return_data.append((tree_axis_group_name,[]))
		return_data.append((tree_axis_target_name,[]))
		return OrderedDict(return_data)

	def __doCheck(self):
		if pMode > 0: return 1
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

		self.working_names = [glyph.name for glyph in self.data_glyphs] if len(self.data_glyphs) > 1 else [self.active_glyph.name]
		self.lst_glyphName.clear()
		self.lst_glyphName.addItems(self.working_names)
				
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

	def get_stem(self, get_y=False):
		if self.__doCheck():
			self.masters_data = self.tree_layer.getTree()
			self.active_glyph = eGlyph()

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

			self.tree_layer.setTree(OrderedDict(self.masters_data), tree_column_names)
	
	def set_current_layer(self):
		try:
			if not self.btn_opt_target.isChecked():
				max_dx = max(self.axis_data, key=lambda i: float(i[1]))[1]
				max_dy = max(self.axis_data, key=lambda i: float(i[2]))[2]
				min_dx = min(self.axis_data, key=lambda i: float(i[1]))[1]
				min_dy = min(self.axis_data, key=lambda i: float(i[2]))[2]
				self.mixer_dx.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 1))))
				self.mixer_dy.edt_pos.setText(round(float(self.__where(self.axis_data, self.active_glyph.layer().name, 2))))
			else:
				max_dx = max(self.masters_data[tree_axis_target_name], key=lambda i: float(i[1]))[1]
				max_dy = max(self.masters_data[tree_axis_target_name], key=lambda i: float(i[2]))[2]
				min_dx = min(self.masters_data[tree_axis_target_name], key=lambda i: float(i[1]))[1]
				min_dy = min(self.masters_data[tree_axis_target_name], key=lambda i: float(i[2]))[2]
				self.mixer_dx.edt_pos.setText(round(float(self.__where(self.masters_data[tree_axis_target_name], self.active_glyph.layer().name, 1))))
				self.mixer_dy.edt_pos.setText(round(float(self.__where(self.masters_data[tree_axis_target_name], self.active_glyph.layer().name, 2))))
		
		
			self.mixer_dx.edt_1.setText(min_dx)
			self.mixer_dy.edt_1.setText(min_dy)
			self.mixer_dx.edt_1.setText(max_dx)
			self.mixer_dy.edt_1.setText(max_dy)

			self.mixer_dx.refreshSlider()
			self.mixer_dy.refreshSlider()
		
		except (ValueError, IndexError):
			warnings.warn('Invalid Axis/Target or Axis/Target not set!', TRDeltaAxisWarning)

	def reset_axis(self):
		self.masters_data = self.tree_layer.getTree()
		#self.masters_data[tree_masters_group_name] += self.masters_data[tree_axis_group_name]
		self.masters_data[tree_axis_group_name] = []
		self.masters_data[tree_axis_target_name] = []
		self.tree_layer.setTree(self.masters_data, tree_column_names)

	def set_axis(self):
		self.masters_data = self.tree_layer.getTree()
		self.axis_data = self.masters_data[tree_axis_group_name]

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
			self.active_font.updateObject(self.active_font.fl, 'Glyph(s): {} Axis :{} @ {}'.format('; '.join(self.working_names), ' :'.join([item[0] for item in self.axis_data]), self.active_glyph.layer().name))
	
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
					if self.btn_opt_target.isChecked():
						process_target = self.masters_data[tree_axis_target_name]
						
						if len(process_target):
							for process_layer_data in process_target:
								layer_name, layer_dx, layer_dy, layer_width, layer_height, _color = process_layer_data

								if not self.btn_opt_update_preview.isChecked():
									# - Stems
									curr_sw_dx = float(layer_dx)
									curr_sw_dy = float(layer_dy)

									# - Scaling
									sx = float(layer_width)/100.
									sy = float(layer_height)/100.
								
								outline_scale = self.glyph_arrays[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
								wGlyph._setPointArray(outline_scale, layer_name, keep_center=self.btn_opt_keep_center.isChecked())
						
								service_scale = self.glyph_arrays_service[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
								wGlyph._setServiceArray(service_scale, layer_name, opt_metrics, opt_anchors)

							if not self.btn_opt_update_preview.isChecked():
								output(0, app_name, 'Processed: %s' %wGlyph.name)

						else:
							warnings.warn('Empty/Invalid Target Table provided! No action taken!', GlyphWarning)
					else:
						outline_scale = self.glyph_arrays[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
						wGlyph._setPointArray(outline_scale, keep_center=self.btn_opt_keep_center.isChecked())
						
						service_scale = self.glyph_arrays_service[wGlyph.name].scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), opt_italic, extrapolate=opt_extrapolate)
						wGlyph._setServiceArray(service_scale, set_metrics=opt_metrics, set_anchors=opt_anchors)
						
					wGlyph.update()
					
					try:
						self.active_canvas.refreshAll()
					except:
						pass
				
				if opt_metrics: self.active_font.fl.changed()

	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 280, 800)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()