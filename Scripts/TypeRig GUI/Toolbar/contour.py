#FLM: TypeRig: Contour Toolbar
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

from typerig.proxy.fl.actions.contour import TRContourActionCollector
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs


# - Init --------------------------
tool_version = '1.2'
tool_name = 'TypeRig Contour'

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
		self.contour_bank_A = {}
		self.contour_bank_B = {}

		# - Groups
		self.grp_contour_options = QtGui.QActionGroup(self)
		self.grp_contour_actions = QtGui.QActionGroup(self)
		self.grp_contour_options.setExclusive(False)

		# - Options
		'''
		self.chk_slope_copy = QtGui.QAction("slope_copy", self.grp_contour_options)
		self.chk_slope_copy.setFont(TRToolFont)
		self.addAction(self.chk_slope_copy)
		self.chk_slope_copy.setToolTip("Copy slope between selected nodes")
		self.chk_slope_copy.setCheckable(True)
		self.chk_slope_copy.setChecked(False)
		self.chk_slope_copy.triggered.connect(self.act_slope_copy)
		'''

		# - Actions
		'''
		self.btn_contour_break = QtGui.QAction("slope_break", self.grp_contour_actions)
		self.btn_contour_break.setToolTip("Paste slope to selected nodes pivoting around the one with lowest vertical coordinates")
		self.btn_contour_break.setFont(TRToolFont)
		self.addAction(self.btn_contour_break)
		self.btn_contour_break.triggered.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, False)))
		'''
		self.btn_contour_close = QtGui.QAction("contour_close", self.grp_contour_actions)
		self.btn_contour_close.setToolTip("Close selected contours")
		self.btn_contour_close.setFont(TRToolFont)
		self.addAction(self.btn_contour_close)
		self.btn_contour_close.triggered.connect(lambda: TRContourActionCollector.contour_close(pMode, pLayers))

		self.btn_contour_union = QtGui.QAction("contour_union", self.grp_contour_actions)
		self.btn_contour_union.setToolTip("Remove overlap for selected contours")
		self.btn_contour_union.setFont(TRToolFont)
		self.addAction(self.btn_contour_union)
		self.btn_contour_union.triggered.connect(lambda: TRContourActionCollector.contour_bool_union(pMode, pLayers))

		# !!! TODO: Implement Boolean operations as recently added in FontGate

		self.btn_contour_cw = QtGui.QAction("contour_cw_alt", self.grp_contour_actions)
		self.btn_contour_cw.setToolTip("Set clockwise winding direction (TrueType)")
		self.btn_contour_cw.setFont(TRToolFont)
		self.addAction(self.btn_contour_cw)
		self.btn_contour_cw.triggered.connect(lambda: TRContourActionCollector.contour_set_winding(pMode, pLayers, False))

		self.btn_contour_ccw = QtGui.QAction("contour_ccw_alt", self.grp_contour_actions)
		self.btn_contour_ccw.setToolTip("Set counterclockwise winding direction (PostScript)")
		self.btn_contour_ccw.setFont(TRToolFont)
		self.addAction(self.btn_contour_ccw)
		self.btn_contour_ccw.triggered.connect(lambda: TRContourActionCollector.contour_set_winding(pMode, pLayers, True))

		self.btn_contour_set_start = QtGui.QAction("node_start", self.grp_contour_actions)
		self.btn_contour_set_start.setToolTip("Set start node")
		self.btn_contour_set_start.setFont(TRToolFont)
		self.addAction(self.btn_contour_set_start)
		self.btn_contour_set_start.triggered.connect(lambda: TRContourActionCollector.contour_set_start(pMode, pLayers))

		self.btn_contour_set_start_bottom_left = QtGui.QAction("node_bottom_left", self.grp_contour_actions)
		self.btn_contour_set_start_bottom_left.setToolTip("Set start node to bottom left")
		self.btn_contour_set_start_bottom_left.setFont(TRToolFont)
		self.addAction(self.btn_contour_set_start_bottom_left)
		self.btn_contour_set_start_bottom_left.triggered.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (0, 0)))

		self.btn_contour_set_start_bottom_right = QtGui.QAction("node_bottom_right", self.grp_contour_actions)
		self.btn_contour_set_start_bottom_right.setToolTip("Set start node to bottom right")
		self.btn_contour_set_start_bottom_right.setFont(TRToolFont)
		self.addAction(self.btn_contour_set_start_bottom_right)
		self.btn_contour_set_start_bottom_right.triggered.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (1, 0)))

		self.btn_contour_set_start_top_left = QtGui.QAction("node_top_left", self.grp_contour_actions)
		self.btn_contour_set_start_top_left.setToolTip("Set start node to top left")
		self.btn_contour_set_start_top_left.setFont(TRToolFont)
		self.addAction(self.btn_contour_set_start_top_left)
		self.btn_contour_set_start_top_left.triggered.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (0, 1)))

		self.btn_contour_set_start_top_right = QtGui.QAction("node_top_right", self.grp_contour_actions)
		self.btn_contour_set_start_top_right.setToolTip("Set start node to top right")
		self.btn_contour_set_start_top_right.setFont(TRToolFont)
		self.addAction(self.btn_contour_set_start_top_right)
		self.btn_contour_set_start_top_right.triggered.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (1, 1)))

		self.btn_contour_sort_y = QtGui.QAction("contour_sort_y", self.grp_contour_actions)
		self.btn_contour_sort_y.setToolTip("Reorder contours from top to bottom")
		self.btn_contour_sort_y.setFont(TRToolFont)
		self.addAction(self.btn_contour_sort_y)
		self.btn_contour_sort_y.triggered.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (True, None), False))

		self.btn_contour_sort_x = QtGui.QAction("contour_sort_x", self.grp_contour_actions)
		self.btn_contour_sort_x.setToolTip("Reorder contours from left to right")
		self.btn_contour_sort_x.setFont(TRToolFont)
		self.addAction(self.btn_contour_sort_x)
		self.btn_contour_sort_x.triggered.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (None, True), False))

		self.btn_contour_sort_y_rev = QtGui.QAction("contour_sort_y_rev", self.grp_contour_actions)
		self.btn_contour_sort_y_rev.setToolTip("Reorder contours from bottom to top")
		self.btn_contour_sort_y_rev.setFont(TRToolFont)
		self.addAction(self.btn_contour_sort_y_rev)
		self.btn_contour_sort_y_rev.triggered.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (True, None), True))

		self.btn_contour_sort_x_rev = QtGui.QAction("contour_sort_x_rev", self.grp_contour_actions)
		self.btn_contour_sort_x_rev.setToolTip("Reorder contours from right to left")
		self.btn_contour_sort_x_rev.setFont(TRToolFont)
		self.addAction(self.btn_contour_sort_x_rev)
		self.btn_contour_sort_x_rev.triggered.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (None, True), True))




# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

