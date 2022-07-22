#FLM: TypeRig: Toolbar
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2022  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
import inspect
from platform import system

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs, TRVTabWidget, TRCheckTableView
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.dialogs import TRLayerSelectDLG

import Toolbar

# - Init --------------------------
tool_version = '1.61'
tool_name = 'TypeRig Controller'
ignore_toolbar = '__'

TRToolFont = getTRIconFont()
app = pWorkspace()
fl_runtime_platform = system()

# -- Global parameters
pMode = 0
pLayers = (True, False, False, False)

# -- Main Widget --------------------------
class TRToolbarController(QtGui.QToolBar):
	def __init__(self, *args, **kwargs):
		super(TRToolbarController, self).__init__(*args, **kwargs)

		# - Init 
		self.setWindowTitle("{} : {}".format(tool_name, tool_version))
		self.layers_selected = []
		
		# - Dialogs 
		self.dlg_layer = TRLayerSelectDLG(self, pMode)
		self.dlg_layer.hide()

		# - Actions and groups 
		self.grp_layers = QtGui.QActionGroup(self)
		self.grp_glyphs = QtGui.QActionGroup(self)

		self.chk_ActiveLayer = QtGui.QAction("layer_active", self.grp_layers)
		self.addAction(self.chk_ActiveLayer)
		self.chk_ActiveLayer.setToolTip("Active layer")

		self.chk_Masters = QtGui.QAction("layer_master", self.grp_layers)
		self.addAction(self.chk_Masters)
		self.chk_Masters.setToolTip("Master layers")

		self.chk_Selected = QtGui.QAction("select_option", self.grp_layers)
		self.addAction(self.chk_Selected)
		self.chk_Selected.setToolTip("Select layers")

		self.chk_glyph = QtGui.QAction("glyph_active", self.grp_glyphs)
		self.addAction(self.chk_glyph)
		self.chk_glyph.setToolTip("Active Glyph")

		self.chk_window = QtGui.QAction("select_window", self.grp_glyphs)
		self.addAction(self.chk_window)
		self.chk_window.setToolTip("Glyph window")

		self.chk_selection = QtGui.QAction("select_glyph", self.grp_glyphs)
		self.addAction(self.chk_selection)
		self.chk_selection.setToolTip("Font window selection")

		self.chk_ActiveLayer.setFont(TRToolFont)
		self.chk_Masters.setFont(TRToolFont)
		self.chk_Selected.setFont(TRToolFont)
		
		self.chk_glyph.setFont(TRToolFont)
		self.chk_window.setFont(TRToolFont)
		self.chk_selection.setFont(TRToolFont)
		
		self.chk_ActiveLayer.setCheckable(True)
		self.chk_Selected.setCheckable(True)
		self.chk_Masters.setCheckable(True)
		self.chk_Masters.setChecked(True)

		self.chk_glyph.setCheckable(True)
		self.chk_window.setCheckable(True)
		self.chk_selection.setCheckable(True)
		self.chk_glyph.setChecked(True)

		self.chk_ActiveLayer.triggered.connect(self.layers_refresh)
		self.chk_Masters.triggered.connect(self.layers_refresh)
		self.chk_Selected.triggered.connect(self.layers_refresh)

		self.chk_glyph.triggered.connect(self.mode_refresh)
		self.chk_window.triggered.connect(self.mode_refresh)
		self.chk_selection.triggered.connect(self.mode_refresh)

		self.layers_refresh()

	# - Procedures -----------------------------------
	def mode_refresh(self):
		global pMode

		if self.chk_glyph.isChecked(): pMode = 0
		if self.chk_window.isChecked(): pMode = 1
		if self.chk_selection.isChecked(): pMode = 2

		self.dlg_layer.table_populate(pMode)

		for toolbar_name in Toolbar.modules:
			exec('Toolbar.{}.pMode = {}'.format(toolbar_name, pMode))

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()

		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)

		for toolbar_name in Toolbar.modules:
			exec('Toolbar.{}.pLayers = {}'.format(toolbar_name, pLayers))
	
# - RUN ------------------------------
# - Init
toolbar_control = TRToolbarController()

# -- Platform specific fix for MacOs by Adam Twardoch (2022). Pt.1
# -- Fixes Mac's lack of visible QMainWindow, thus adding toolbars to invisible item renders them ivisible too :) 
# -- Note: the fix is temporary, we should find a better solution that suits all platforms...

if fl_runtime_platform == 'Darwin':
	app.main.show()
	app.main.setGeometry(0,0,0,0)
	toolbar_control.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
	toolbar_control.move(50,50)

app.main.addToolBar(toolbar_control)

# -- Import external toolbars
# --- Load all toolbars from Toolbar directory as modules. Check __init__.py 
# --- <dirName>.modules tabs/modules manifest in list format
for i, toolbar_name in enumerate(Toolbar.modules):
	if ignore_toolbar not in toolbar_name:
		
		new_toolbar = eval('Toolbar.{}.TRExternalToolBar()'.format(toolbar_name))
		app.main.addToolBar(new_toolbar) 

		# -- The above fix Pt.2
		if fl_runtime_platform == 'Darwin':
			new_toolbar.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint) #ADAM-MAC
			new_toolbar.move(50, 100 + 50 * i) #ADAM_MAC

# -- The above fix Pt.3
if fl_runtime_platform == 'Darwin':
	app.main.hide()



