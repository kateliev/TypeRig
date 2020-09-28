#FLM: TR: Auto metrics
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json
from itertools import groupby
from operator import itemgetter
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.proxy.fl import *

from typerig.gui import QtGui
from typerig.gui.widgets import TRTableView, TRSliderCtrl, getProcessGlyphs

# - Init
global pLayers
global pMode
pLayers = (True, True, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Auto Metrics', '0.5'

# -- Strings

# - Sub widgets ------------------------
class TRAutoMetrics(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self, parentWidget):
		super(TRAutoMetrics, self).__init__()
		self.upper_widget = parentWidget

		# -- Init
		self.active_font = pFont()
		self.active_sampler = MetricSampler(self.active_font)
		self.font_masters = self.active_font.masters()
		self.empty_preset = lambda row: OrderedDict([(row, OrderedDict([('Preset', 'Preset %s' %row)] + [(master, '0') for master in self.font_masters]))])
		self.table_dict = self.empty_preset(0)
		self.__max_value = 10000

		# -- Widgets
		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_glyphName.setPlaceholderText('Glyph name')

		# -- Buttons
		self.btn_addPreset = QtGui.QPushButton('Add')
		self.btn_delPreset = QtGui.QPushButton('Remove')
		self.btn_resetPreset = QtGui.QPushButton('Reset')
		self.btn_loadPreset = QtGui.QPushButton('Load')
		self.btn_savePreset = QtGui.QPushButton('Save')
		self.btn_get_lsb = QtGui.QPushButton('LSB')
		self.btn_get_rsb = QtGui.QPushButton('RSB')
		self.btn_get_both = QtGui.QPushButton('Set Metrics')
		self.btn_advanced = QtGui.QPushButton('Use Advanced options')

		self.btn_advanced.setCheckable(True)
		self.btn_advanced.setChecked(False)
		self.btn_advanced.setEnabled(False)

		self.btn_get_lsb.clicked.connect(lambda: self.set_sidebearings('lsb'))
		self.btn_get_rsb.clicked.connect(lambda: self.set_sidebearings('rsb'))
		self.btn_get_both.clicked.connect(lambda: self.set_sidebearings('bth'))

		# -- Checkbox
		self.chk_area_draw = QtGui.QCheckBox('Draw sampled area')
		self.chk_area_cache = QtGui.QCheckBox('Cache sampled area')

		# -- Spinbox
		self.spb_window_min = QtGui.QSpinBox()
		self.spb_window_max = QtGui.QSpinBox()
		self.spb_depth = QtGui.QSpinBox()
		self.spb_mul_area = QtGui.QDoubleSpinBox()

		self.spb_window_min.setMaximum(self.__max_value)
		self.spb_window_max.setMaximum(self.__max_value)
		self.spb_window_min.setMinimum(-self.__max_value)
		self.spb_window_max.setMinimum(-self.__max_value)
		self.spb_depth.setMaximum(self.__max_value)
		self.spb_mul_area.setMaximum(20.)
		self.spb_mul_area.setMinimum(-20.)
		
		self.spb_mul_area.setSingleStep(0.01)
		
		self.spb_window_min.setSuffix(' u')
		self.spb_window_max.setSuffix(' u')
		self.spb_depth.setSuffix(' u')

		self.spb_window_min.setValue(self.active_sampler.sample_window[0])
		self.spb_window_max.setValue(self.active_sampler.sample_window[1])
		
		self.spb_depth.setValue(self.active_sampler.cutout_x)
		self.spb_mul_area.setValue(0.5)

		self.spb_window_min.valueChanged.connect(lambda: self.update_sampler_config())
		self.spb_window_max.valueChanged.connect(lambda: self.update_sampler_config())
		self.spb_depth.valueChanged.connect(lambda: self.update_sampler_config())

		# -- Preset Table
		self.tab_presets = TRTableView(None)

		# -- Build Layout
		self.lay_head = QtGui.QGridLayout()
		self.frame_advanced = QtGui.QFrame()
		self.lay_advanced = QtGui.QGridLayout()

		self.lay_head.addWidget(QtGui.QLabel('Sampling Options:'),	0, 0, 1, 8)
		self.lay_head.addWidget(QtGui.QLabel('Min (Y):'),		 	1, 0, 1, 2)
		self.lay_head.addWidget(self.spb_window_min, 				1, 2, 1, 2)
		self.lay_head.addWidget(QtGui.QLabel('Max (Y):'), 			1, 4, 1, 2)
		self.lay_head.addWidget(self.spb_window_max, 				1, 6, 1, 2)
		self.lay_head.addWidget(QtGui.QLabel('Depth (X):'), 		2, 0, 1, 2)
		self.lay_head.addWidget(self.spb_depth, 					2, 2, 1, 2)
		self.lay_head.addWidget(QtGui.QLabel('Area (mult.):'),	 	2, 4, 1, 2)
		self.lay_head.addWidget(self.spb_mul_area,					2, 6, 1, 2)
		self.lay_head.addWidget(self.chk_area_draw,					3, 0, 1, 4)
		self.lay_head.addWidget(self.chk_area_cache,				3, 4, 1, 4)
		self.lay_head.addWidget(self.btn_get_lsb,					4, 0, 1, 2)
		self.lay_head.addWidget(self.btn_get_both,					4, 2, 1, 4)
		self.lay_head.addWidget(self.btn_get_rsb,					4, 6, 1, 2)
		self.lay_head.addWidget(self.btn_advanced,					5, 0, 1, 8)
		self.lay_head.addWidget(self.frame_advanced,				6, 0, 15, 8)
		
		self.frame_advanced.setLayout(self.lay_advanced)
		#self.lay_advanced.addWidget(QtGui.QLabel('Advanced configuration:'), 0, 0, 1, 6)
		self.lay_advanced.addWidget(self.btn_addPreset,				1, 0, 1, 2)
		self.lay_advanced.addWidget(self.btn_delPreset,				1, 2, 1, 2)
		self.lay_advanced.addWidget(self.btn_resetPreset,			1, 4, 1, 2)
		self.lay_advanced.addWidget(self.tab_presets,				2, 0, 5, 6)
		self.lay_advanced.addWidget(self.btn_loadPreset,			10, 0, 1, 3)
		self.lay_advanced.addWidget(self.btn_savePreset,			10, 3, 1, 3)
		
		self.frame_advanced.setFrameStyle(1)
		self.frame_advanced.hide()
		self.btn_advanced.clicked.connect(lambda: self.frame_advanced.show() if self.btn_advanced.isChecked() else self.frame_advanced.hide())

		self.addLayout(self.lay_head)

	# - Basics -----------------------------------------------------------
	def update_sampler_config(self):
		self.active_sampler.sample_window[0] = self.spb_window_min.value
		self.active_sampler.sample_window[1] = self.spb_window_max.value
		self.active_sampler.cutout_x = self.spb_depth.value

	def set_sidebearings(self, mode='bth'):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				new_lsb, new_rsb = self.active_sampler.getGlyphSB(glyph, layer, self.spb_mul_area.value, not self.chk_area_cache.isChecked(), self.chk_area_draw.isChecked())
				if mode != 'rsb': glyph.setLSB(int(new_lsb), layer)
				if mode != 'lsb': glyph.setRSB(int(new_rsb), layer)
			
			if len(process_glyphs) == 1:
				glyph.updateObject(glyph.fl, 'Set Metrics @ %s.' %'; '.join(wLayers))

		if len(process_glyphs) > 1:
			self.active_font.updateObject(self.active_font.fl, 'Set Metrics for glyphs %s @ %s.' %('; '.join([glyph.name for glyph in process_glyphs]), '; '.join(wLayers)))		

	# - Presets management ------------------------------------------------
	def preset_reset(self):
		self.builder = None
		self.active_font = pFont()
		self.font_masters = self.active_font.masters()
		
		self.table_dict = self.empty_preset(0)
		self.tab_presets.clear()
		self.tab_presets.setTable(self.table_dict, sortData=(False, False))
		self.tab_presets.horizontalHeader().setStretchLastSection(False)
		self.tab_presets.verticalHeader().hide()
		#self.tab_presets.resizeColumnsToContents()

	def preset_modify(self, delete=False):
		table_rawList = self.tab_presets.getTable(raw=True)
		
		if delete:
			for selection in self.tab_presets.selectionModel().selectedIndexes:
				table_rawList.pop(selection.row())
				print selection.row()

		new_entry = OrderedDict()
		
		for key, data in table_rawList:
			new_entry[key] = OrderedDict(data)

		if not delete: new_entry[len(table_rawList)] = self.empty_preset(len(table_rawList)).items()[0][1]
		self.tab_presets.setTable(new_entry, sortData=(False, False))

	def preset_load(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upper_widget, 'Load presets from file', fontPath, 'TypeRig JSON (*.json)')
		
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
			
			# - Convert Data
			new_data = OrderedDict()
			for key, data in imported_data:
				new_data[key] = OrderedDict(data)

			self.tab_presets.setTable(new_data, sortData=(False, False))
			print 'LOAD:\t Font:%s; Presets loaded from: %s.' %(self.active_font.name, fname)

	def preset_save(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save presets to file', fontPath, 'TypeRig JSON (*.json)')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tab_presets.getTable(raw=True), exportFile)

			print 'SAVE:\t Font:%s; Presets saved to: %s.' %(self.active_font.name, fname)

	def getPreset(self):
		table_raw = self.tab_presets.getTable(raw=True)
		'''
		try:
			active_preset_index = self.tab_presets.selectionModel().selectedIndexes[0].row()
		except IndexError:
			active_preset_index = None
		'''
		active_preset_index = self.tab_presets.selectionModel().selectedIndexes[0].row()

		if active_preset_index is None: 
			active_preset_index = self.last_preset
		else:
			self.last_preset = active_preset_index

		return dict(table_raw[active_preset_index][1][1:])


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.smart_corner = TRAutoMetrics(self)
		layoutV.addLayout(self.smart_corner)
		
		# - Build
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()