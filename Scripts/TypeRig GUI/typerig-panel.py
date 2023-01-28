#FLM: TypeRig: Panel
# ----------------------------------------
# (C) Vassil Kateliev, 2018-2021 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
import os
import json

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

#from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, getProcessGlyphs, CustomPushButton, TRVTabWidget, TRCheckTableView, TRFlowLayout
from typerig.proxy.fl.gui.dialogs import TRLayerSelectNEW
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.styles import css_tr_button

# -- Internals - Load tool panels 
import Panel 

# - Init --------------------------
app_version = '3.10'
app_name = 'TypeRig Panel'
ignore_panel = '__'
panel_path = 'Panel' # ./Panel/
panel_cfg_filename = 'typerig-panel-config.json'

app = pWorkspace()
TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# -- Global parameters
pMode = 0
pLayers = (True, False, False, False)

# - Sub widget ----------------------------
class TROptionsPanel(QtGui.QWidget):
	def __init__(self, config=None):
		super(TROptionsPanel, self).__init__()

		# - Init
		lay_main = QtGui.QVBoxLayout()

		# - Panel visibility options
		self.options = QtGui.QTableWidget()
		self.set_table(config)
		lay_main.addWidget(self.options)
		
		# - Save/load config files
		box_main_cfg = QtGui.QGroupBox()
		box_main_cfg.setObjectName('box_group')

		lay_main_cfg = TRFlowLayout(spacing=10)

		tooltip_button = 'Save panel configuration'
		self.btn_file_save = CustomPushButton('file_save', tooltip=tooltip_button, obj_name='btn_panel')
		lay_main_cfg.addWidget(self.btn_file_save)
		self.btn_file_save.clicked.connect(lambda: self.file_save_config())

		tooltip_button = 'Load panel configuration'
		self.btn_file_open = CustomPushButton('file_open', tooltip=tooltip_button, obj_name='btn_panel')
		lay_main_cfg.addWidget(self.btn_file_open)
		self.btn_file_open.clicked.connect(lambda: self.file_open_config())

		lbl_note = QtGui.QLabel('')
		lay_main_cfg.addWidget(lbl_note)

		box_main_cfg.setLayout(lay_main_cfg)
		lay_main.addWidget(box_main_cfg)

		# - Set
		self.setLayout(lay_main)

	# -- Tool/panel config 
	def set_table(self, data):
		name_row, name_column = [], []
		self.options.blockSignals(True)

		self.options.setColumnCount(max(map(len, data.values())))
		self.options.setRowCount(len(data.keys()))

		options_header = self.options.horizontalHeader()
		options_header.setStretchLastSection(True)
		options_header.setDefaultAlignment(QtCore.Qt.AlignLeft)
		self.options.verticalHeader().hide()
		
		self.options.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.options.setAlternatingRowColors(True)
		self.options.setShowGrid(False)
		
		self.options.resizeColumnsToContents()
		self.options.resizeRowsToContents()

		# - Populate
		for row, value in enumerate(data.keys()):
			name_row.append(value)
			
			for col, key in enumerate(data[value].keys()):
				name_column.append(key)
				rowData = data[value][key]
				
				newitem = QtGui.QTableWidgetItem(str(rowData))
				
				if col == 0:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
					newitem.setCheckState(QtCore.Qt.Unchecked)

				self.options.setItem(row, col, newitem)

		self.options.setHorizontalHeaderLabels(name_column)
		self.options.setVerticalHeaderLabels(name_row)
		self.options.blockSignals(False)

		options_header.setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		options_header.setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)

	# - Getter/setters --------------------------------
	def get_table(self):
		return [(self.options.item(row, 0).text(), self.options.item(row, 1).text(), self.options.item(row, 0).checkState()) for row in range(self.options.rowCount)]

	def get_states(self):
		return [(self.options.item(row, 0).text(), self.options.item(row, 0).checkState()) for row in range(self.options.rowCount)]

	def set_states(self, data):
		panel_names = [self.options.item(row, 0).text() for row in range(self.options.rowCount)]

		for panel, state in data:
			try:
				panel_index = panel_names.index(panel)

				if state:
					self.options.item(panel_index, 0).setCheckState(QtCore.Qt.Checked) 
				else:
					self.options.item(panel_index, 0).setCheckState(QtCore.Qt.Unchecked)

			except ValueError: 
				# !!! TODO: Add some subroutine for adding mising pannels to list
				pass

	# -- File operations
	def file_save_config(self):
		config_path = os.path.join(os.path.split(__file__)[0], panel_path)
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save TypeRig panel configuration', config_path, 'TypeRig panel config (*.json);;')
		exported_data = self.get_states()

		if fname != None:
			with open(fname, 'w') as export_file:
				json.dump(exported_data, export_file)
				output(7, app_name, 'TypeRig panel configuration saved to: %s.' %(fname))
				output(1, app_name, 'Script restart is required for changes to take effect! %s.' %(fname))
				
	def file_open_config(self):
		config_path = os.path.join(os.path.split(__file__)[0], panel_path)
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load TypeRig panel configuration', config_path, 'TypeRig panel config (*.json);;')
			
		if fname != None:
			with open(fname, 'r') as import_file:
				imported_data = json.load(import_file)
								
				self.set_states(imported_data)
				output(6, app_name, 'TypeRig panel configuration loaded from: %s.' %(fname))
				output(1, app_name, 'Script restart is required for changes to take effect! %s.' %(fname))

		return imported_data


# -- Main Widget --------------------------
class TRMainPanel(QtGui.QDialog):
	def __init__(self):
		super(TRMainPanel, self).__init__()

		# - Init ----------------------------
		self.setStyleSheet(css_tr_button)
		self.layers_selected = []
		self.flag_fold = False
		
		# - Masthead/controller ------------
		self.dlg_layer = TRLayerSelectNEW(self, pMode)
		self.dlg_layer.hide()

		self.chk_ActiveLayer = CustomPushButton('layer_active', True, True, True, 'Active layer', 'btn_mast')
		self.chk_Masters = CustomPushButton('layer_master', True, False, True, 'Master layers', 'btn_mast')
		self.chk_Selected = CustomPushButton('select_option', True, False, True, 'Selected layers', 'btn_mast')
		self.chk_glyph = CustomPushButton('glyph_active', True, True, True, 'Active glyph', 'btn_mast')
		self.chk_window = CustomPushButton('select_window', True, False, True, 'Glyph window', 'btn_mast')
		self.chk_selection = CustomPushButton('select_glyph', True, False, True, 'Font window selection', 'btn_mast')
		self.btn_fold = CustomPushButton('fold_up', False, False, True, 'Fold panel', 'btn_mast')

		self.chk_ActiveLayer.clicked.connect(self.layers_refresh)
		self.chk_Masters.clicked.connect(self.layers_refresh)
		self.chk_Selected.clicked.connect(self.layers_refresh)

		self.chk_glyph.clicked.connect(self.mode_refresh)
		self.chk_window.clicked.connect(self.mode_refresh)
		self.chk_selection.clicked.connect(self.mode_refresh)
		self.btn_fold.clicked.connect(self.fold)

		# - Layout ----------------------------------
		self.grp_layers = QtGui.QButtonGroup()
		self.grp_glyphs = QtGui.QButtonGroup()

		self.lay_mast = QtGui.QHBoxLayout()

		self.grp_layers.addButton(self.chk_ActiveLayer, 1)
		self.grp_layers.addButton(self.chk_Masters, 2)
		self.grp_layers.addButton(self.chk_Selected, 3)

		self.grp_glyphs.addButton(self.chk_glyph, 1)
		self.grp_glyphs.addButton(self.chk_window, 2)
		self.grp_glyphs.addButton(self.chk_selection, 3)
		self.lay_mast.setContentsMargins(4, 4, 4, 4)

		for button in self.grp_layers.buttons() + self.grp_glyphs.buttons() + (self.btn_fold,):
			self.lay_mast.addWidget(button)
				
		# - Tabs --------------------------
		panel_vers = {n:{'Panel':panel_tool_name, 'Version': eval('Panel.%s.app_version' %panel_tool_name)}	for n, panel_tool_name in enumerate(Panel.modules)} 

		# - Panel Configuiration
		self.options = TROptionsPanel(panel_vers)
		
		# -- Load panel config
		config_file = os.path.join(os.path.split(__file__)[0], panel_path, panel_cfg_filename)
		
		if os.path.isfile(config_file):
			with open(config_file, 'r') as import_file:
				config_enabled_panels = json.load(import_file)
		else:
			config_enabled_panels = []

		self.options.set_states(config_enabled_panels)
		config_enabled_panels_dict = dict(config_enabled_panels)

		# -- Dynamically load all tabs
		self.tabs = TRVTabWidget()

		# --- Load all tabs from this directory as modules. Check __init__.py 
		# --- <dirName>.modules tabs/modules manifest in list format
		for panel_tool_name in Panel.modules:
			if ignore_panel not in panel_tool_name:
				if panel_tool_name in config_enabled_panels_dict and config_enabled_panels_dict[panel_tool_name]:
					self.tabs.addTab(eval('Panel.%s.tool_tab()' %panel_tool_name), panel_tool_name)

		# --- Add options tab
		self.tabs.addTab(self.options, '...')

		# - Layouts -------------------------------
		self.lay_main = QtGui.QVBoxLayout() 
		self.lay_main.setContentsMargins(0, 0, 0, 0)
		self.lay_main.addLayout(self.lay_mast)
		self.lay_main.addWidget(self.tabs)

		# - Set Widget -------------------------------
		self.setLayout(self.lay_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(100, 100, 300, 600)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

		# !!! Hotfix FL7 7355 
		#self.setMinimumSize(330, self.sizeHint.height())
		
		self.layers_refresh()
		self.show()

	# - Procedures -----------------------------------
	def mode_refresh(self):
		global pMode

		if self.chk_glyph.isChecked(): pMode = 0
		if self.chk_window.isChecked(): pMode = 1
		if self.chk_selection.isChecked(): pMode = 2
		#if self.chk_font.isChecked(): pMode = 3

		self.dlg_layer.table_populate(pMode)

		for panel_tool_name in Panel.modules:
			exec('Panel.%s.pMode = %s' %(panel_tool_name, pMode))

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()

		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)

		for panel_tool_name in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(panel_tool_name, pLayers))

	def fold(self):
		# - Init
		width_all = self.width
		height_folded = self.btn_fold.sizeHint.height() + 7
						
		# - Do
		if not self.flag_fold:
			self.tabs.hide()
			self.btn_fold.setText('fold_down')
			self.setMinimumHeight(height_folded)
			self.repaint()
			self.resize(width_all, height_folded)
			self.flag_fold = True

		else:
			#QtGui.uiRefresh(self)
			self.tabs.show()
			self.btn_fold.setText('fold_up')
			self.adjustSize()
			self.resize(width_all, self.sizeHint.height()) # !!! Hotfix FL7 7355 
			self.repaint()
			self.flag_fold = False

# - RUN ------------------------------
dialog = TRMainPanel()

