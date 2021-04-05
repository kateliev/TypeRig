#FLM: TypeRig: Filter
# ----------------------------------------
# (C) Vassil Kateliev, 2018-2020 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRVTabWidget

# -- Internals - Load toolpanels 
import Filter as Panel 

# - Init --------------------------
app_version = '2.15'
app_name = 'TypeRig Filter'
ignorePanel = '__'

# -- Global parameters
pMode = 0
pLayers = (True, False, False, False)

# -- Inital config for Get Layers dialog
column_names = ('Layer Name', 'Layer Type')
column_init = (None, None)
table_dict = {1:OrderedDict(zip(column_names, column_init))}
color_dict = {'Master': QtGui.QColor(0, 255, 0, 20), 'Service': QtGui.QColor(0, 0, 255, 20), 'Mask': QtGui.QColor(255, 0, 0, 20)}

# - Style -------------------------
ss_Toolbox_none = """/* EMPTY STYLESHEET */ """

# - Interface -----------------------------
# - Widgets --------------------------------
class TRTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
	
		# - Set 
		self.setTable(data)		
	
		# - Styling
		#self.setSortingEnabled(True)
		self.horizontalHeader().setStretchLastSection(True)
		self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)
		self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, color_dict=None, enable_check=False):
		self.clear()
		self.setSortingEnabled(False)
		self.blockSignals(True)
		self.model().sort(-1)
		self.horizontalHeader().setSortIndicator(-1, 0)

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
				
				if m == 0 and enable_check:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setCheckState(QtCore.Qt.Unchecked)
				
				if color_dict is not None:
					try:
						newitem.setBackground(color_dict[data[layer]['Layer Type']])
					except KeyError:
						pass
				

				self.setItem(n, m, newitem)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.resizeColumnsToContents()

		self.blockSignals(False)
		self.setSortingEnabled(True)

		self.horizontalHeader().setSectionResizeMode(0, QtGui.QHeaderView.Stretch)
		self.horizontalHeader().setSectionResizeMode(1, QtGui.QHeaderView.ResizeToContents)

	def getTable(self):
		return [self.item(row, 0).text() for row in range(self.rowCount) if self.item(row, 0).checkState() == QtCore.Qt.Checked]

# - Dialogs --------------------------------
class dlg_LayerSelect(QtGui.QDialog):
	def __init__(self, parent, mode):
		super(dlg_LayerSelect, self).__init__()
	
		# - Init
		self.parent_widget = parent
		
		# - Basic Widgets
		self.tab_masters = TRTableView(table_dict)
		self.table_populate(mode)
		self.tab_masters.cellChanged.connect(lambda: self.parent_widget.layers_refresh())

		# -- Buttons
		self.btn_tableCheck = QtGui.QPushButton('Select All')
		self.btn_tableCheckMasters = QtGui.QPushButton('Masters')
		self.btn_tableCheckMasks = QtGui.QPushButton('Masks')
		self.btn_tableCheckServices = QtGui.QPushButton('Services')

		self.btn_tableCheck.setToolTip('Click check all.\n<ALT> + Click uncheck all.')
		self.btn_tableCheckMasters.setToolTip('Click check all.\n<ALT> + Click uncheck all.')
		self.btn_tableCheckMasks.setToolTip('Click check all.\n<ALT> + Click uncheck all.')
		self.btn_tableCheckServices.setToolTip('Click check all.\n<ALT> + Click uncheck all.')
		
		if mode !=0:
			self.btn_tableCheckMasters.setEnabled(False)
			self.btn_tableCheckMasks.setEnabled(False)
			self.btn_tableCheckServices.setEnabled(False)
		
		self.btn_tableCheck.clicked.connect(lambda: self.table_check_all())
		self.btn_tableCheckMasters.clicked.connect(lambda: self.table_check_all('Master'))
		self.btn_tableCheckMasks.clicked.connect(lambda: self.table_check_all('Mask'))
		self.btn_tableCheckServices.clicked.connect(lambda: self.table_check_all('Service'))

		# - Build layout
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(self.btn_tableCheck, 				0, 0, 1, 2)
		layoutV.addWidget(self.btn_tableCheckMasters, 		0, 2, 1, 2)
		layoutV.addWidget(self.btn_tableCheckMasks, 		1, 0, 1, 2)
		layoutV.addWidget(self.btn_tableCheckServices, 		1, 2, 1, 2)
		layoutV.addWidget(self.tab_masters, 				2, 0, 20, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s | Select Layers' %(app_name, app_version))
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.setGeometry(500, 200, 300, 600)
		#self.show()

	# - Table operations
	def table_check_all(self, layer_type=None):
		modifiers = QtGui.QApplication.keyboardModifiers() # Listen to Shift - reverses the ratio

		for row in range(self.tab_masters.rowCount):
			if modifiers == QtCore.Qt.AltModifier:
				self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Unchecked)								
			else:
				if layer_type is None or self.tab_masters.item(row,1).text() == layer_type:
					self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Checked)
	
	def table_populate(self, mode):
		
		def check_type(layer):
			if layer.isMaskLayer: return 'Mask'
			if layer.isMasterLayer: return 'Master'
			if layer.isService: return 'Service'
		
		if fl6.CurrentFont() is not None and fl6.CurrentGlyph() is not None:
			active_font = pFont()
			active_glyph = pGlyph()

			if mode == 0:
				init_data = [(layer.name, check_type(layer)) for layer in active_glyph.layers() if '#' not in layer.name]
			else:
				init_data = [(master, 'Master') for master in active_font.pMasters.names]
		 	
		 	table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in enumerate(init_data)}
			self.tab_masters.clear()
			self.tab_masters.setTable(table_dict, color_dict=color_dict, enable_check=True)	

# -- Main Widget --------------------------
class typerig_Panel(QtGui.QDialog):
	def __init__(self):
		super(typerig_Panel, self).__init__()

		# - Init ----------------------------
		#self.setStyleSheet(ss_Toolbox_none)
		self.layers_selected = []
		
		# - Dialogs -------------------------
		self.layer_dialog = dlg_LayerSelect(self, pMode)

		# - Layers --------------------------
		self.chk_ActiveLayer = QtGui.QCheckBox('Active')
		self.chk_Masters = QtGui.QCheckBox('Masters')
		self.chk_Masks = QtGui.QCheckBox('Masks')
		self.chk_Service = QtGui.QCheckBox('Services')
		self.chk_Selected = QtGui.QCheckBox('Selected')

		self.chk_ActiveLayer.setCheckState(QtCore.Qt.Checked)

		self.chk_ActiveLayer.stateChanged.connect(self.layers_refresh)
		self.chk_Masters.stateChanged.connect(self.layers_refresh)
		self.chk_Masks.stateChanged.connect(self.layers_refresh)
		self.chk_Service.stateChanged.connect(self.layers_refresh)
		self.chk_Selected.stateChanged.connect(self.layers_refresh)

		self.layers_refresh()

		# - Glyphs --------------------------
		self.rad_glyph = QtGui.QRadioButton('Glyph')
		self.rad_window = QtGui.QRadioButton('Window')
		self.rad_selection = QtGui.QRadioButton('Selection')
		self.rad_font = QtGui.QRadioButton('Font')
		
		self.rad_glyph.toggled.connect(self.mode_refresh)
		self.rad_window.toggled.connect(self.mode_refresh)
		self.rad_selection.toggled.connect(self.mode_refresh)
		self.rad_font.toggled.connect(self.mode_refresh)
		
		self.rad_glyph.setChecked(True)

		self.rad_glyph.setEnabled(True)
		self.rad_window.setEnabled(True)
		self.rad_selection.setEnabled(True)
		self.rad_font.setEnabled(False)

		self.rad_glyph.setToolTip('Affect current glyph')
		self.rad_window.setToolTip('Affect glyphs in active window')
		self.rad_selection.setToolTip('Affect selected glyphs')
		self.rad_font.setToolTip('Affect the entire font')

		# - Buttons ------------------------
		self.btn_layersSelect = QtGui.QPushButton('Layers')
		self.btn_fold = QtGui.QPushButton('^')
		self.btn_unfold = QtGui.QPushButton('Restore Panel')
		
		self.btn_fold.setFixedHeight(self.chk_ActiveLayer.sizeHint.height()*2.5)
		self.btn_fold.setFixedWidth(self.chk_ActiveLayer.sizeHint.height())
		self.btn_unfold.setFixedHeight(self.chk_ActiveLayer.sizeHint.height() + 5)

		self.btn_fold.setToolTip('Fold Panel.')
		self.btn_unfold.setToolTip('Unfold Panel.')
		self.btn_layersSelect.setToolTip('Select layers for processing.')

		self.btn_fold.clicked.connect(self.fold)
		self.btn_unfold.clicked.connect(self.fold)
		self.flag_fold = False
				
		# - Tabs --------------------------
		panel_vers = {n:OrderedDict([	('Panel', toolName), ('Version', eval('Panel.%s.app_version' %toolName))])
										for n, toolName in enumerate(Panel.modules)} 

		self.options = TRTableView(panel_vers)
		self.options.verticalHeader().hide()

		# -- Dynamically load all tabs
		self.tabs = TRVTabWidget()

		# --- Load all tabs from this directory as modules. Check __init__.py 
		# --- <dirName>.modules tabs/modules manifest in list format
		for toolName in Panel.modules:
			if ignorePanel not in toolName:
				self.tabs.addTab(eval('Panel.%s.tool_tab()' %toolName), toolName)

		# --- Add options tab
		self.tabs.addTab(self.options, '...')

		# - Layouts -------------------------------
		layoutV = QtGui.QVBoxLayout() 
		layoutV.setContentsMargins(0,0,0,0)
		
		self.lay_controller = QtGui.QGridLayout()
		self.fr_controller = QtGui.QFrame()
		self.lay_controller.setContentsMargins(15,5,5,3)
		self.lay_controller.setSpacing(5)

		# -- Build layouts -------------------------------
		self.lay_controller.addWidget(self.chk_ActiveLayer,	0, 0, 1, 1)
		self.lay_controller.addWidget(self.chk_Masters, 	0, 1, 1, 1)
		self.lay_controller.addWidget(self.chk_Masks, 		0, 2, 1, 1)
		#self.lay_controller.addWidget(self.chk_Service, 	0, 3, 1, 1)
		self.lay_controller.addWidget(self.chk_Selected, 	0, 3, 1, 1)
		self.lay_controller.addWidget(self.btn_fold, 		0, 4, 2, 1)
		self.lay_controller.addWidget(self.rad_glyph, 		1, 0, 1, 1)
		self.lay_controller.addWidget(self.rad_window, 		1, 1, 1, 1)
		self.lay_controller.addWidget(self.rad_selection, 	1, 2, 1, 1)
		self.lay_controller.addWidget(self.rad_font, 		1, 3, 1, 1)
					 
		layoutV.addWidget(self.btn_unfold)
		self.fr_controller.setLayout(self.lay_controller)
		
		layoutV.addWidget(self.fr_controller)
		layoutV.addWidget(self.tabs)

		self.btn_unfold.hide()

		# - Set Widget -------------------------------
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(100, 100, 300, 600)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(330, self.sizeHint.height())

		self.show()

	# - Procedures -----------------------------------
	def mode_refresh(self):
		global pMode

		if self.rad_glyph.isChecked(): pMode = 0
		if self.rad_window.isChecked(): pMode = 1
		if self.rad_selection.isChecked(): pMode = 2
		if self.rad_font.isChecked(): pMode = 3

		self.layer_dialog.table_populate(pMode)

		for toolName in Panel.modules:
			exec('Panel.%s.pMode = %s' %(toolName, pMode))

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.chk_ActiveLayer.setChecked(False),
			self.chk_Masters.setChecked(False)
			self.chk_Masks.setChecked(False)
			self.chk_Service.setChecked(False)
			
			self.layer_dialog.show()
			pLayers = self.layer_dialog.tab_masters.getTable()

		else:
			self.chk_Selected.setChecked(False)
			self.layer_dialog.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), self.chk_Masks.isChecked(), self.chk_Service.isChecked())
	
		for toolName in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(toolName, pLayers))

	def fold(self):
		# - Init
		width_all = self.width
		height_folded = self.btn_unfold.sizeHint.height()
						
		# - Do
		if not self.flag_fold:
			self.tabs.hide()
			self.fr_controller.hide()
			self.btn_unfold.show()
			self.setMinimumHeight(height_folded)
			self.repaint()
			self.resize(width_all, height_folded)
			self.flag_fold = True

		else:
			QtGui.uiRefresh(self)
			self.tabs.show()
			self.fr_controller.show()
			self.btn_unfold.hide()
			self.adjustSize()
			self.resize(width_all, self.sizeHint.height()) # !!! Hotfix FL7 7355 
			self.repaint()
			self.flag_fold = False

# - RUN ------------------------------
dialog = typerig_Panel()

