#FLM: TR: Delta
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2023 	(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import json
import math
import os
import warnings
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.core.base.message import *
from typerig.core.func import transform
from typerig.core.objects.delta import DeltaArray, DeltaScale
from typerig.core.objects.transform import Transform

from PythonQt import QtCore, QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, getTRIconFontPath, CustomPushButton, TRFlowLayout, TRDeltaLayerTree, TRCustomSpinController
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Delta', '5.5'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# -- Strings ---------------------------
tree_column_names = ('Master Layers','V st.', 'H st.', 'Width', 'Height', 'Color')
tree_masters_group_name = 'Master Layers'
tree_axis_group_name = 'Virtual Axis'
tree_axis_target_name = 'Target Layers'
fileFormats = 'TypeRig Delta Panel Target (*.json);;'

# - Configuration ----------------------
default_sx = '100.'
default_sy = '100.'

# - Tabs -------------------------------
class TRDeltaPanel(QtGui.QWidget):
	def __init__(self):
		super(TRDeltaPanel, self).__init__()

		# - Init
		self.active_font = pFont()
		self.active_workspace = pWorkspace()
		self.active_layer = None
		self.axis_data = []
		self.axis_stems = []
		self.glyph_arrays = {}
		self.value_array = None

		# - Build Layout
		lay_main = QtGui.QVBoxLayout()

		# -- Layer selector
		self.tree_layer = TRDeltaLayerTree()

		# --- Layer selector: Actions (Context Menu)
		act_resetAxis = QtGui.QAction('Clear all', self)
		act_getVstem = QtGui.QAction('Get Vertical Stems', self)
		act_getHstem = QtGui.QAction('Get Horizontal Stems', self)

		self.tree_layer.menu.addSeparator()	
		self.tree_layer.menu.addAction(act_getVstem)
		self.tree_layer.menu.addAction(act_getHstem)
		self.tree_layer.menu.addSeparator()	
		self.tree_layer.menu.addAction(act_resetAxis)

		act_resetAxis.triggered.connect(lambda: self.__reset_all())
		act_getVstem.triggered.connect(lambda: self.get_stem(False))
		act_getHstem.triggered.connect(lambda: self.get_stem(True))

		# --  Layer selector: Set
		self.tree_layer.setTree(self.__init_tree(), tree_column_names)
		lay_main.addWidget(self.tree_layer)

		# -- Buttons: Delta Actions
		box_delta_actions = QtGui.QGroupBox()
		box_delta_actions.setObjectName('box_group')

		lay_actions = TRFlowLayout(spacing=10)

		tooltip_button = 'Execute delta scale'
		self.btn_execute_scale = CustomPushButton('action_play', tooltip=tooltip_button, enabled=False, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_execute_scale)
		self.btn_execute_scale.clicked.connect(lambda: self.execute_target())

		tooltip_button = 'Get vertical stems'
		self.btn_get_stem_x = CustomPushButton('stem_vertical_alt', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_get_stem_x)
		self.btn_get_stem_x.clicked.connect(lambda: self.get_stem(False))

		tooltip_button = 'Get horizontal stems'
		self.btn_get_stem_y = CustomPushButton('stem_horizontal_alt', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_get_stem_y)
		self.btn_get_stem_y.clicked.connect(lambda: self.get_stem(True))

		tooltip_button = 'Make undo snapshot'
		self.btn_undo_snapshot = CustomPushButton('undo_snapshot', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_undo_snapshot)
		self.btn_undo_snapshot.clicked.connect(lambda: self.__undo_snapshot())

		tooltip_button = 'Set axis'
		self.btn_axis_set = CustomPushButton('axis_set', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_axis_set)
		self.btn_axis_set.clicked.connect(lambda: self.__set_axis(True))

		tooltip_button = 'Reset axis'
		self.btn_axis_reset = CustomPushButton('axis_remove', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_axis_reset)
		self.btn_axis_reset.clicked.connect(lambda: self.__reset_axis(True))

		tooltip_button = 'Reset all data'
		self.btn_axis_reset_all = CustomPushButton('refresh', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_axis_reset_all)
		self.btn_axis_reset_all.clicked.connect(lambda: self.__reset_all(True))

		tooltip_button = 'Save axis data to external file'
		self.btn_file_save = CustomPushButton('file_save', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_file_save)
		self.btn_file_save.clicked.connect(lambda: self.file_save_axis_data())

		tooltip_button = 'Load axis data from external file'
		self.btn_file_open = CustomPushButton('file_open', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_file_open)
		self.btn_file_open.clicked.connect(lambda: self.file_open_axis_data())

		tooltip_button = 'Save axis data to font file'
		self.btn_font_save = CustomPushButton('font_save', tooltip=tooltip_button, enabled=False, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_font_save)
		#self.btn_font_save.clicked.connect(lambda: self.__reset_all())

		tooltip_button = 'Load axis data from font file'
		self.btn_font_open = CustomPushButton('font_open', tooltip=tooltip_button, enabled=False, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_font_open)
		#self.btn_file_open.clicked.connect(lambda: self.__reset_all())

		box_delta_actions.setLayout(lay_actions)
		lay_main.addWidget(box_delta_actions)

		# -- Buttons: Delta options
		box_delta_options = QtGui.QGroupBox()
		box_delta_options.setObjectName('box_group')

		lay_options = TRFlowLayout(spacing=10)

		tooltip_button = 'Process metrics'
		self.chk_metrics = CustomPushButton("metrics_advance_alt", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_metrics)

		tooltip_button = 'Process anchors'
		self.chk_anchors = CustomPushButton("icon_anchor", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_anchors)

		tooltip_button = 'Allow extrapolation'
		self.chk_extrapolate = CustomPushButton("extrapolate", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_extrapolate)

		tooltip_button = 'Use target'
		self.chk_target = CustomPushButton("node_target", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_target)
		self.chk_target.clicked.connect(lambda: self.__prepare_target())

		tooltip_button = 'Proportional scale mode'
		self.chk_proportional = CustomPushButton("diagonal_bottom_up", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_proportional)
		self.chk_proportional.clicked.connect(lambda: self.__toggle_proportional_scale())
		
		tooltip_button = 'Scale from center'
		self.chk_center = CustomPushButton("node_target_expand", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_center)
		
		tooltip_button = 'Show extended controls'
		self.chk_toggle_controls = CustomPushButton("value_controls", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_toggle_controls)
		self.chk_toggle_controls.clicked.connect(lambda: self.__toggle_controls())

		box_delta_options.setLayout(lay_options)
		lay_main.addWidget(box_delta_options)

		# -- Delta controls
		lay_controls = TRFlowLayout(spacing=10)

		self.cpn_value_width = TRCustomSpinController('width', (-999, 999, 100, 1), ' %', 'Width')
		lay_controls.addWidget(self.cpn_value_width)
		self.cpn_value_width.spin_box.valueChanged.connect(lambda: self.execute_scale())
		
		self.cpn_value_height = TRCustomSpinController('height', (-999, 999, 100, 1), ' %', 'Height')
		lay_controls.addWidget(self.cpn_value_height)
		self.cpn_value_height.spin_box.valueChanged.connect(lambda: self.execute_scale())

		self.cpn_value_stem_x = TRCustomSpinController('stem_vertical_alt', (-300, 300, 1, 1), ' u', 'Vertical stem width')
		lay_controls.addWidget(self.cpn_value_stem_x)
		self.cpn_value_stem_x.spin_box.valueChanged.connect(lambda: self.execute_scale())

		self.cpn_value_stem_y = TRCustomSpinController('stem_horizontal_alt', (-300, 300, 1, 1), ' u', 'Horizontal stem width')
		lay_controls.addWidget(self.cpn_value_stem_y)
		self.cpn_value_stem_y.spin_box.valueChanged.connect(lambda: self.execute_scale())

		self.cpn_value_lerp_t = TRCustomSpinController('interpolate', (-300, 300, 0, 1), ' %', 'Time along axis')
		lay_controls.addWidget(self.cpn_value_lerp_t)
		self.cpn_value_lerp_t.spin_box.valueChanged.connect(lambda: self.execute_scale(True))

		self.cpn_value_ital = TRCustomSpinController('slope_italic', (-20, 20, self.active_font.italic_angle, 1), ' °', 'Italic angle')
		lay_controls.addWidget(self.cpn_value_ital)
		self.cpn_value_ital.spin_box.valueChanged.connect(lambda: self.execute_scale())

		lay_main.addLayout(lay_controls)
		self.__toggle_controls()

		# --- Set styling 
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		
	# - Functions -----------------------------------------
	# -- Events and triggers
	def contextMenuEvent(self, event):
		self.tree_layer.menu.popup(QtGui.QCursor.pos())	
	
	# -- Internal
	def __toggle_controls(self):
		if self.chk_toggle_controls.isChecked():
			self.cpn_value_width.expand()
			self.cpn_value_height.expand()
			self.cpn_value_ital.expand()
			self.cpn_value_stem_x.expand()
			self.cpn_value_stem_y.expand()
			self.cpn_value_lerp_t.expand()
		else:
			self.cpn_value_width.contract()
			self.cpn_value_height.contract()
			self.cpn_value_ital.contract()
			self.cpn_value_stem_x.contract()
			self.cpn_value_stem_y.contract()
			self.cpn_value_lerp_t.contract()

	def __toggle_proportional_scale(self):
		if self.chk_proportional.isChecked():
			self.cpn_value_height.setEnabled(False)
		else:
			self.cpn_value_height.setEnabled(True)

	def __change_value(self, cpn_object, value):
		cpn_object.setValue(cpn_object.getValue() + value)

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

	def __prepare_delta(self):
		# - Tests
		if not len(self.axis_data):
			self.__set_axis()
			self.__refresh_ui()
			warnings.warn('Axis not set! Setting axis automatically...', TRDeltaAxisWarning)
			return False

		if not len(self.glyph_arrays):
			self.__refresh_arrays()
			self.__refresh_ui()
			warnings.warn('Deltas not set! Setting delta arrays automatically...', TRDeltaArrayWarning)
			return False

		if pMode == 0:
			if fl6.CurrentGlyph().name not in self.glyph_arrays.keys():
				warnings.warn('Active glyph changed! Forcing refresh...', GlyphWarning)
				self.__refresh_arrays()
				self.__refresh_ui()
				return False

		if pMode == 1:
			active_glyph_names = [glyph.name for glyph in self.active_workspace.getTextBlockGlyphs()]
			if sorted(active_glyph_names) != sorted(self.glyph_arrays.keys()):
				warnings.warn('Glyph(s) changed! Forcing refresh...', GlyphWarning)
				self.__refresh_arrays()
				self.__refresh_ui()
				return False

		if self.active_glyph.layer().name != self.active_layer:
			self.__refresh_ui()
			self.active_layer = self.active_glyph.layer().name
			warnings.warn('Layer changed! Forcing refresh...', LayerWarning)
			return False

		# - Default
		return True

	def __prepare_target(self):
		if self.chk_target.isChecked():
			self.cpn_value_width.setEnabled(False)
			self.cpn_value_height.setEnabled(False)
			self.cpn_value_stem_x.setEnabled(False)
			self.cpn_value_stem_y.setEnabled(False)
			self.cpn_value_lerp_t.setEnabled(False)
			self.cpn_value_ital.setEnabled(False)

			self.btn_execute_scale.setEnabled(True)
		else:
			self.cpn_value_width.setEnabled(True)
			self.cpn_value_height.setEnabled(True)
			self.cpn_value_stem_x.setEnabled(True)
			self.cpn_value_stem_y.setEnabled(True)
			self.cpn_value_lerp_t.setEnabled(True)
			self.cpn_value_ital.setEnabled(True)

			self.btn_execute_scale.setEnabled(False)

	def __refresh_ui(self):
		self.cpn_value_width.setValue(100)
		self.cpn_value_height.setValue(100)
		self.value_array = DeltaScale(self.axis_stems, self.axis_stems)
		all_layers = sum(self.masters_data.values(),[])
		
		if len(self.axis_data):
			self.cpn_value_stem_x.setValue(float(self.__where(all_layers, self.active_glyph.layer().name, 1)))
			self.cpn_value_stem_y.setValue(float(self.__where(all_layers, self.active_glyph.layer().name, 2)))
		
		self.cpn_value_ital.setValue(self.active_font.italic_angle)

	def __refresh_arrays(self):
		# - Init
		self.active_canvas = self.active_workspace.getCanvas(True)

		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			temp_outline = [glyph._getPointArray(layer_data[0]) for layer_data in self.axis_data]
			temp_service = [glyph._getServiceArray(layer_data[0]) for layer_data in self.axis_data]
			self.glyph_arrays[glyph.name] = [glyph, DeltaScale(temp_outline, self.axis_stems), DeltaScale(temp_service, self.axis_stems)]

	def __set_axis(self, verbose=False):
		self.masters_data = self.tree_layer.getTree()
		self.axis_data = self.masters_data[tree_axis_group_name]
		self.axis_stems = []

		if not len(self.axis_data):
			warnings.warn('Axis not set! Please add two or more layers!', TRDeltaAxisWarning)
			return
		
		for layer_data in self.axis_data:
			try:
				x_stem, y_stem = float(layer_data[1]), float(layer_data[2])
				self.axis_stems.append([(x_stem, y_stem)])

			except ValueError:
				warnings.warn('Missing or invalid stem data!', TRDeltaStemWarning)
				return

		self.__refresh_ui()
		if verbose: output(0, '%s %s' %(app_name, app_version), 'Font: %s; Axis set.' %(self.active_font.name))

	def __reset_axis(self, verbose=False):
		self.axis_data = []
		self.axis_stems = []
		self.glyph_arrays = {}

		if verbose: output(0, '%s %s' %(app_name, app_version), 'Font: %s; Axis data cleared.' %(self.active_font.name))

	def __reset_all(self, verbose=False):
		self.tree_layer.setTree(self.__init_tree(), tree_column_names)
		self.__reset_axis()

		self.cpn_value_width.blockSignals(True)
		self.cpn_value_height.blockSignals(True)
		self.cpn_value_stem_x.blockSignals(True)
		self.cpn_value_stem_y.blockSignals(True)
		self.cpn_value_lerp_t.blockSignals(True)
		self.cpn_value_ital.blockSignals(True)

		self.cpn_value_width.setValue(100)
		self.cpn_value_height.setValue(100)
		self.cpn_value_stem_x.setValue(100)
		self.cpn_value_stem_y.setValue(100)
		self.cpn_value_lerp_t.setValue(0)
		self.cpn_value_ital.setValue(self.active_font.italic_angle)

		self.cpn_value_width.blockSignals(False)
		self.cpn_value_height.blockSignals(False)
		self.cpn_value_stem_x.blockSignals(False)
		self.cpn_value_stem_y.blockSignals(False)
		self.cpn_value_lerp_t.blockSignals(False)
		self.cpn_value_ital.blockSignals(False)

		if verbose: output(0, '%s %s' %(app_name, app_version), 'Reset.')

	def __undo_snapshot(self, verbose=True):
		# - Init
		process_glyphs = getProcessGlyphs(pMode)
		process_glyphs_names = [glyph.name for glyph in process_glyphs]
		undo_message = '{} {} | Undo Snapshot for glyphs: {};'.format(app_name, app_version, '; '.join(process_glyphs_names))

		# - Set undo 
		if len(process_glyphs) > 2:
			self.active_font.updateObject(self.active_font.fl, undo_message, verbose)
		else:
			glyph = process_glyphs[0]
			glyph.updateObject(glyph.fl, undo_message, verbose)

	# -- File operations
	def file_save_axis_data(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save axis data to file', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tree_layer.getTree(), exportFile)
				output(7, app_name, 'Font: %s; Axis data saved to: %s.' %(self.active_font.name, fname))
				
	def file_open_axis_data(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load axis data from file', fontPath, fileFormats)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
								
				self.masters_data = imported_data
				self.tree_layer.setTree(self.masters_data, tree_column_names)
				output(6, app_name, 'Font: %s; Axis data loaded from: %s.' %(self.active_font.name, fname))

	# -- Delta operation
	def get_stem(self, get_y=False):
		self.masters_data = self.tree_layer.getTree()
		self.active_glyph = eGlyph()

		for group, data in self.masters_data.items():
			for layer_data in data:
				try:
					selection = self.active_glyph.selectedNodes(layer_data[0], True)
					
					if get_y:
						layer_data[2] = round(abs(selection[0].y - selection[-1].y), 2)
					else:
						layer_data[1] = round(abs(selection[0].x - selection[-1].x), 2)
				except IndexError:
					warnings.warn('Missing or incompatible layer: %s!' %layer_data[0], LayerWarning)
					continue

		self.tree_layer.setTree(OrderedDict(self.masters_data), tree_column_names)

	def execute_scale(self, use_time=False):
		# - Init
		system_ready = self.__prepare_delta()
		if not system_ready: return

		if pMode == 0:
			system_process = [self.glyph_arrays[fl6.CurrentGlyph().name]]
		else:
			system_process = self.glyph_arrays.values()
		
		# - Process
		for glyph, delta_outline, delta_service in system_process:

			# - Init
			intervals = len(delta_outline)

			# - Scaling
			sx = float(self.cpn_value_width.getValue())/100.

			if self.chk_proportional.isChecked():
				sy = sx
				self.cpn_value_height.blockSignals(True)
				self.cpn_value_height.setValue(self.cpn_value_width.getValue())
				self.cpn_value_height.blockSignals(False)
			else:
				sy = float(self.cpn_value_height.getValue())/100.
			
			# - Italic
			# Note: Use italic only in the context of Delta calculation not for actuall slanting
			it = math.radians(-float(self.active_font.italic_angle)) 

			# - Options
			opt_extrapolate = self.chk_extrapolate.isChecked()
			opt_center = self.chk_center.isChecked()
			opt_metrics = self.chk_metrics.isChecked()
			opt_anchors = self.chk_anchors.isChecked()

			if not use_time:
				# - Use Stems
				curr_sw_dx = float(self.cpn_value_stem_x.getValue())
				curr_sw_dy = float(self.cpn_value_stem_y.getValue())

				# - Process
				outline_scale = delta_outline.scale_by_stem((curr_sw_dx, curr_sw_dy), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate)
				service_scale = delta_service.scale_by_stem((curr_sw_dx, curr_sw_dy), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate)
				
				tx, ty = delta_outline._stem_for_time(curr_sw_dx, curr_sw_dy, opt_extrapolate)

				self.cpn_value_lerp_t.blockSignals(True)
				self.cpn_value_lerp_t.setValue(round(tx / intervals * 100))
				self.cpn_value_lerp_t.blockSignals(False)

			else:
				# - Use Times
				curr_tx = curr_ty = float(self.cpn_value_lerp_t.getValue()) * intervals / 100

				# - Process
				outline_scale = map(lambda i: (round(i[0]), round(i[1])), delta_outline.scale_by_time((curr_tx, curr_ty), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate))
				service_scale = map(lambda i: (round(i[0]), round(i[1])), delta_service.scale_by_time((curr_tx, curr_ty), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate))
				
				# - Set stem values to controls
				curr_sw_dx, curr_sw_dy = list(self.value_array.scale_by_time((curr_tx, curr_ty), (sx,sy), (0.,0.), (0.,0.), it, extrapolate=opt_extrapolate))[0]

				self.cpn_value_stem_x.blockSignals(True)
				self.cpn_value_stem_y.blockSignals(True)
				self.cpn_value_stem_x.setValue(round(curr_sw_dx))
				self.cpn_value_stem_y.setValue(round(curr_sw_dy))
				self.cpn_value_stem_x.blockSignals(False)
				self.cpn_value_stem_y.blockSignals(False)
			
			# - Process slant transform
			new_transform = Transform()
			new_transform = new_transform.skew(self.cpn_value_ital.getValue(), 0.)
			outline_scale = list(map(lambda i: (new_transform.applyTransformation(*i)), outline_scale))
			service_scale = list(map(lambda i: (new_transform.applyTransformation(*i)), service_scale))

			# - Apply transformations
			glyph._setPointArray(outline_scale, keep_center=opt_center)
			glyph._setServiceArray(service_scale, set_metrics=opt_metrics, set_anchors=opt_anchors)

			glyph.update()

		# - Update viewport
		try:
			self.active_canvas.refreshAll()
		except:
			pass

	def execute_target(self):
		# - Init
		glyphs_done = []

		system_ready = self.__prepare_delta()
		if not system_ready: return

		process_target = self.masters_data[tree_axis_target_name]
		if not len(process_target): return

		if pMode == 0:
			system_process = [self.glyph_arrays[fl6.CurrentGlyph().name]]
		else:
			system_process = self.glyph_arrays.values()
			
		# - Process
		for glyph, delta_outline, delta_service in system_process:
			for process_layer_data in process_target:
				# - Unpack axis data
				layer_name, curr_sw_dx, curr_sw_dy, sx, sy, _ = process_layer_data

				curr_sw_dx = float(curr_sw_dx)
				curr_sw_dy = float(curr_sw_dy)
				sx = float(sx)/100.
				sy = float(sy)/100.
				it = math.radians(-float(self.active_font.italic_angle)) 

				# - Options
				opt_extrapolate = self.chk_extrapolate.isChecked()
				opt_center = self.chk_center.isChecked()
				opt_metrics = self.chk_metrics.isChecked()
				opt_anchors = self.chk_anchors.isChecked()

				# - Process
				outline_scale = delta_outline.scale_by_stem((curr_sw_dx, curr_sw_dy), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate)
				service_scale = delta_service.scale_by_stem((curr_sw_dx, curr_sw_dy), (sx, sy), (0., 0.), (0., 0.), it, extrapolate=opt_extrapolate)

				# - Apply transformations
				glyph._setPointArray(outline_scale, layer=layer_name, keep_center=opt_center)
				glyph._setServiceArray(service_scale, layer=layer_name, set_metrics=opt_metrics, set_anchors=opt_anchors)

			glyphs_done.append(glyph.name)
			glyph.update()

		# - Update viewport
		try:
			self.active_canvas.refreshAll()
		except:
			pass

		# - Finish it
		self.__undo_snapshot(False)
		output(0, '%s %s' %(app_name, app_version), 'Font: %s;' %(self.active_font.name))
		output(0, '%s %s' %(app_name, app_version), 'Glyph(s): %s.' %('; '.join(glyphs_done)))
					
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)
		
		lay_main = QtGui.QVBoxLayout()
		lay_main.setContentsMargins(0, 0, 0, 0)
		
		# - Add widgets to main dialog 
		lay_main.addWidget(TRDeltaPanel())

		# - Build 
		self.setLayout(lay_main)

# - Test ----------------------
if __name__ == '__main__':
	delta_panel = tool_tab()
	delta_panel.setWindowTitle('%s %s' %(app_name, app_version))
	delta_panel.setGeometry(100, 100, 300, 400)
	delta_panel.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
	
	delta_panel.show()