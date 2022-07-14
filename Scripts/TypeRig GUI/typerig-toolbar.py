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

import fontlab as fl6
from PythonQt import QtCore

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs, TRVTabWidget, TRCheckTableView
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.dialogs import TRLayerSelectDLG


# - Init --------------------------
tool_version = '1.10'
tool_name = 'TypeRig Controller'
ignore_toolbar = '__'

TRToolFont = getTRIconFont()
app = pWorkspace()

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

		self.rad_glyph = QtGui.QAction("glyph_active", self.grp_glyphs)
		self.addAction(self.rad_glyph)
		self.rad_glyph.setToolTip("Active Glyph")

		self.rad_window = QtGui.QAction("select_window", self.grp_glyphs)
		self.addAction(self.rad_window)
		self.rad_window.setToolTip("Glyph window")

		self.rad_selection = QtGui.QAction("select_glyph", self.grp_glyphs)
		self.addAction(self.rad_selection)
		self.rad_selection.setToolTip("Font window selection")

		self.chk_ActiveLayer.setFont(TRToolFont)
		self.chk_Masters.setFont(TRToolFont)
		self.chk_Selected.setFont(TRToolFont)
		
		self.rad_glyph.setFont(TRToolFont)
		self.rad_window.setFont(TRToolFont)
		self.rad_selection.setFont(TRToolFont)
		
		self.chk_ActiveLayer.setCheckable(True)
		self.chk_Selected.setCheckable(True)
		self.chk_Masters.setCheckable(True)

		self.rad_glyph.setCheckable(True)
		self.rad_window.setCheckable(True)
		self.rad_selection.setCheckable(True)

		self.chk_ActiveLayer.triggered.connect(self.layers_refresh)
		self.chk_Masters.triggered.connect(self.layers_refresh)
		self.chk_Selected.triggered.connect(self.layers_refresh)

		self.rad_glyph.triggered.connect(self.mode_refresh)
		self.rad_window.triggered.connect(self.mode_refresh)
		self.rad_selection.triggered.connect(self.mode_refresh)

		self.layers_refresh()

	# - Procedures -----------------------------------
	def mode_refresh(self):
		global pMode

		if self.rad_glyph.isChecked(): pMode = 0
		if self.rad_window.isChecked(): pMode = 1
		if self.rad_selection.isChecked(): pMode = 2

		self.dlg_layer.table_populate(pMode)

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()

		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)
	
# - RUN ------------------------------
toolbar_control = TRToolbarController(app.main)
app.main.addToolBar(toolbar_control)

