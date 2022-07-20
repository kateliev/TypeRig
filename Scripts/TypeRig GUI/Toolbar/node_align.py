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
tool_version = '1.15'
tool_name = 'TypeRig Nodes: Align'

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

		# - Groups
		self.grp_align_options_shift = QtGui.QActionGroup(self)
		self.grp_align_options_other = QtGui.QActionGroup(self)
		self.grp_align_actions = QtGui.QActionGroup(self)

		# - Options
		self.chk_shift_smart = QtGui.QAction("shift_smart", self.grp_align_options_shift)
		self.chk_shift_smart.setFont(TRToolFont)
		self.addAction(self.chk_shift_smart)
		self.chk_shift_smart.setToolTip("Smart Shift")
		self.chk_shift_smart.setCheckable(True)
		self.chk_shift_smart.setChecked(False)

		self.chk_shift_dumb = QtGui.QAction("shift_dumb", self.grp_align_options_shift)
		self.chk_shift_dumb.setFont(TRToolFont)
		self.addAction(self.chk_shift_dumb)
		self.chk_shift_dumb.setToolTip("Smart Shift")
		self.chk_shift_dumb.setCheckable(True)
		self.chk_shift_dumb.setChecked(True)

		self.chk_shift_keep_dimension = QtGui.QAction("shift_keep_dimension", self.grp_align_options_other)
		self.chk_shift_keep_dimension.setFont(TRToolFont)
		self.addAction(self.chk_shift_keep_dimension)
		self.chk_shift_keep_dimension.setToolTip("Keep relations between selected nodes")
		self.chk_shift_keep_dimension.setCheckable(True)
		self.chk_shift_keep_dimension.setChecked(False)

		self.chk_shift_intercept = QtGui.QAction("shift_intercept", self.grp_align_options_other)
		self.chk_shift_intercept.setFont(TRToolFont)
		self.addAction(self.chk_shift_intercept)
		self.chk_shift_intercept.setToolTip("Intercept vertical position")
		self.chk_shift_intercept.setCheckable(True)
		self.chk_shift_intercept.setChecked(False)

		# - Actions
		self.btn_node_align_left = QtGui.QAction("node_align_left", self.grp_align_actions)
		self.btn_node_align_left.setToolTip("Align selected nodes left")
		self.btn_node_align_left.setFont(TRToolFont)
		self.addAction(self.btn_node_align_left)
		self.btn_node_align_left.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'L', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_right = QtGui.QAction("node_align_right", self.grp_align_actions)
		self.btn_node_align_right.setToolTip("Align selected nodes right")
		self.btn_node_align_right.setFont(TRToolFont)
		self.addAction(self.btn_node_align_right)
		self.btn_node_align_right.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'R', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_top = QtGui.QAction("node_align_top", self.grp_align_actions)
		self.btn_node_align_top.setToolTip("Align selected nodes top")
		self.btn_node_align_top.setFont(TRToolFont)
		self.addAction(self.btn_node_align_top)
		self.btn_node_align_top.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'T', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_bottom = QtGui.QAction("node_align_bottom", self.grp_align_actions)
		self.btn_node_align_bottom.setToolTip("Align selected nodes bottom")
		self.btn_node_align_bottom.setFont(TRToolFont)
		self.addAction(self.btn_node_align_bottom)
		self.btn_node_align_bottom.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'L', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_selection_x = QtGui.QAction("node_align_selection_x", self.grp_align_actions)
		self.btn_node_align_selection_x.setToolTip("Align selected nodes to horizontal center of selection")
		self.btn_node_align_selection_x.setFont(TRToolFont)
		self.addAction(self.btn_node_align_selection_x)
		self.btn_node_align_selection_x.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'C', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_selection_y = QtGui.QAction("node_align_selection_y", self.grp_align_actions)
		self.btn_node_align_selection_y.setToolTip("Align selected nodes to vertical center of selection")
		self.btn_node_align_selection_y.setFont(TRToolFont)
		self.addAction(self.btn_node_align_selection_y)
		self.btn_node_align_selection_y.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'E', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_neigh_x = QtGui.QAction("node_align_neigh_x", self.grp_align_actions)
		self.btn_node_align_neigh_x.setToolTip("Align selected node in the horizontal middle of its direct neighbors")
		self.btn_node_align_neigh_x.setFont(TRToolFont)
		self.addAction(self.btn_node_align_neigh_x)
		self.btn_node_align_neigh_x.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_neigh_y = QtGui.QAction("node_align_neigh_y", self.grp_align_actions)
		self.btn_node_align_neigh_y.setToolTip("Align selected node in the horizontal middle of its direct neighbors")
		self.btn_node_align_neigh_y.setFont(TRToolFont)
		self.addAction(self.btn_node_align_neigh_y)
		self.btn_node_align_neigh_y.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_outline_x = QtGui.QAction("node_align_outline_x", self.grp_align_actions)
		self.btn_node_align_outline_x.setToolTip("Align selected nodes to the horizontal middle of outline bounding box.")
		self.btn_node_align_outline_x.setFont(TRToolFont)
		self.addAction(self.btn_node_align_outline_x)
		self.btn_node_align_outline_x.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))

		self.btn_node_align_outline_y = QtGui.QAction("node_align_outline_y", self.grp_align_actions)
		self.btn_node_align_outline_y.setToolTip("Align selected nodes to the vertical middle of outline bounding box.")
		self.btn_node_align_outline_y.setFont(TRToolFont)
		self.addAction(self.btn_node_align_outline_y)
		self.btn_node_align_outline_y.triggered.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked()))


# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

