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

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

#from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, getProcessGlyphs, CustomPushButton, TRVTabWidget, TRCheckTableView
from typerig.proxy.fl.gui.dialogs import TRLayerSelectDLG
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.styles import css_tr_button

# -- Internals - Load tool panels 
import Panel 

# - Init --------------------------
app_version = '3.00'
app_name = 'TypeRig Panel'
ignorePanel = '__'

app = pWorkspace()
TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# -- Global parameters
pMode = 0
pLayers = (True, False, False, False)

# - Style -------------------------


# -- Main Widget --------------------------
class TRMainPanel(QtGui.QDialog):
	def __init__(self):
		super(TRMainPanel, self).__init__()

		# - Init ----------------------------
		self.setStyleSheet(css_tr_button)
		self.layers_selected = []
		self.flag_fold = False
		
		# - Masthead/controller ------------
		self.dlg_layer = TRLayerSelectDLG(self, pMode)
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
		panel_vers = {n:OrderedDict([	('Panel', toolName), ('Version', eval('Panel.%s.app_version' %toolName))])
										for n, toolName in enumerate(Panel.modules)} 

		self.options = TRCheckTableView(panel_vers)
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
		self.setMinimumSize(330, self.sizeHint.height())
		
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

		for toolName in Panel.modules:
			exec('Panel.%s.pMode = %s' %(toolName, pMode))

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()

		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)

		for toolName in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(toolName, pLayers))

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

