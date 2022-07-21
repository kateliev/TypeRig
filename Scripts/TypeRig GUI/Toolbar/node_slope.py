#FLM: TypeRig: Node Toolbar
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
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs


# - Init --------------------------
tool_version = '1.2'
tool_name = 'TypeRig Nodes: Slope'

TRToolFont = getTRIconFont()
app = pWorkspace()

# -- Global parameters
global pMode
global pLayers
pMode = 0
pLayers = (True, False, False, False)

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

# -- Main Widget --------------------------
class TRExternalToolBar(QtGui.QToolBar):
	def __init__(self, *args, **kwargs):
		super(TRExternalToolBar, self).__init__(*args, **kwargs)

		# - Init 
		self.setWindowTitle("{} : {}".format(tool_name, tool_version))
		self.slope_bank = {}

		# - Groups
		self.grp_slope_options = QtGui.QActionGroup(self)
		self.grp_slope_actions = QtGui.QActionGroup(self)
		self.grp_slope_options.setExclusive(False)

		# - Options
		self.chk_slope_copy = QtGui.QAction("slope_copy", self.grp_slope_options)
		self.chk_slope_copy.setFont(TRToolFont)
		self.addAction(self.chk_slope_copy)
		self.chk_slope_copy.setToolTip("Copy slope between selected nodes")
		self.chk_slope_copy.setCheckable(True)
		self.chk_slope_copy.setChecked(False)
		self.chk_slope_copy.triggered.connect(self.act_slope_copy)

		self.chk_slope_italic = QtGui.QAction("slope_italic", self.grp_slope_options)
		self.chk_slope_italic.setFont(TRToolFont)
		self.addAction(self.chk_slope_italic)
		self.chk_slope_italic.setToolTip("Use fonts italic angle as slope")
		self.chk_slope_italic.setCheckable(True)
		self.chk_slope_italic.setChecked(False)
		self.chk_slope_italic.triggered.connect(self.act_slope_italic)

		# - Actions
		self.btn_slope_paste_min = QtGui.QAction("slope_paste_min", self.grp_slope_actions)
		self.btn_slope_paste_min.setToolTip("Paste slope to selected nodes pivoting around the one with lowest vertical coordinates")
		self.btn_slope_paste_min.setFont(TRToolFont)
		self.addAction(self.btn_slope_paste_min)
		self.btn_slope_paste_min.triggered.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, False)))

		self.btn_slope_paste_max = QtGui.QAction("slope_paste_max", self.grp_slope_actions)
		self.btn_slope_paste_max.setToolTip("Paste slope to selected nodes pivoting around the one with highest vertical coordinates")
		self.btn_slope_paste_max.setFont(TRToolFont)
		self.addAction(self.btn_slope_paste_max)
		self.btn_slope_paste_max.triggered.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, False)))

		self.btn_slope_paste_min_flip = QtGui.QAction("slope_paste_min_flip", self.grp_slope_actions)
		self.btn_slope_paste_min_flip.setToolTip("Paste horizontally flipped slope to selected nodes pivoting around the one with lowest vertical coordinates")
		self.btn_slope_paste_min_flip.setFont(TRToolFont)
		self.addAction(self.btn_slope_paste_min_flip)
		self.btn_slope_paste_min_flip.triggered.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, True)))

		self.btn_slope_paste_max_flip = QtGui.QAction("slope_paste_max_flip", self.grp_slope_actions)
		self.btn_slope_paste_max_flip.setToolTip("Paste horizontally flipped slope to selected nodes pivoting around the one with highest vertical coordinates")
		self.btn_slope_paste_max_flip.setFont(TRToolFont)
		self.addAction(self.btn_slope_paste_max_flip)
		self.btn_slope_paste_max_flip.triggered.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, True)))

	# - Procedures -------------------------	
	def act_slope_copy(self):
		if self.chk_slope_copy.isChecked():
			self.slope_bank = TRNodeActionCollector.slope_copy(eGlyph(), pLayers)
		else:
			self.slope_bank = {}

	def act_slope_italic(self):
		if self.chk_slope_italic.isChecked():
			self.slope_bank = TRNodeActionCollector.slope_italic(eGlyph(), pLayers)
		else:
			self.slope_bank = {}

# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

