#FLM: TypeRig: Curve Toolbar
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2024  	(http://www.kateliev.com)
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

from typerig.proxy.fl.actions.curve import TRCurveActionCollector
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs


# - Init --------------------------
tool_version = '1.3'
tool_name = 'TypeRig Curves'

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
		self.grp_curve_actions = QtGui.QActionGroup(self)

		# - Actions
		self.btn_node_smooth = QtGui.QAction("node_smooth", self.grp_curve_actions)
		self.btn_node_smooth.setToolTip("Convert node to smooth")
		self.btn_node_smooth.setFont(TRToolFont)
		self.addAction(self.btn_node_smooth)
		self.btn_node_smooth.triggered.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, True))

		self.btn_node_sharp = QtGui.QAction("node_sharp", self.grp_curve_actions)
		self.btn_node_sharp.setToolTip("Convert node to sharp")
		self.btn_node_sharp.setFont(TRToolFont)
		self.addAction(self.btn_node_sharp)
		self.btn_node_sharp.triggered.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, False))

		self.btn_line_to_curve = QtGui.QAction("line_to_curve", self.grp_curve_actions)
		self.btn_line_to_curve.setToolTip("Convert selected segment to curve")
		self.btn_line_to_curve.setFont(TRToolFont)
		self.addAction(self.btn_line_to_curve)
		self.btn_line_to_curve.triggered.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, True))

		self.btn_curve_to_line = QtGui.QAction("curve_to_line", self.grp_curve_actions)
		self.btn_curve_to_line.setToolTip("Convert selected segment to line")
		self.btn_curve_to_line.setFont(TRToolFont)
		self.addAction(self.btn_curve_to_line)
		self.btn_curve_to_line.triggered.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, False))

		self.btn_curve_tunni = QtGui.QAction("curve_tunni", self.grp_curve_actions)
		self.btn_curve_tunni.setToolTip("Optimize curve: Tunni")
		self.btn_curve_tunni.setFont(TRToolFont)
		self.addAction(self.btn_curve_tunni)
		self.btn_curve_tunni.triggered.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'tunni'))

		self.btn_curve_tension_push = QtGui.QAction("curve_copy", self.grp_curve_actions)
		self.btn_curve_tension_push.setToolTip("Optimize curve: Copy handle proportions to masters")
		self.btn_curve_tension_push.setFont(TRToolFont)
		self.addAction(self.btn_curve_tension_push)
		self.btn_curve_tension_push.triggered.connect(lambda: TRCurveActionCollector.hobby_tension_push(pMode, pLayers))

		self.btn_curve_hobby = QtGui.QAction("curve_hobby", self.grp_curve_actions)
		self.btn_curve_hobby.setToolTip("Optimize curve: Set Hobby curvature")
		self.btn_curve_hobby.setFont(TRToolFont)
		self.addAction(self.btn_curve_hobby)
		self.btn_curve_hobby.triggered.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'hobby'))

		self.btn_curve_hobby_1 = QtGui.QAction("curve_hobby_1", self.grp_curve_actions)
		self.btn_curve_hobby_1.setToolTip("Optimize curve: Set Hobby curvature to 1.")
		self.btn_curve_hobby_1.setFont(TRToolFont)
		self.addAction(self.btn_curve_hobby_1)
		self.btn_curve_hobby_1.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', 1., 1.)))

		self.btn_curve_hobby_95 = QtGui.QAction("curve_hobby_95", self.grp_curve_actions)
		self.btn_curve_hobby_95.setToolTip("Optimize curve: Set Hobby curvature to .95")
		self.btn_curve_hobby_95.setFont(TRToolFont)
		self.addAction(self.btn_curve_hobby_95)
		self.btn_curve_hobby_95.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .95, .95)))

		self.btn_curve_hobby_90 = QtGui.QAction("curve_hobby_90", self.grp_curve_actions)
		self.btn_curve_hobby_90.setToolTip("Optimize curve: Set Hobby curvature to .90")
		self.btn_curve_hobby_90.setFont(TRToolFont)
		self.addAction(self.btn_curve_hobby_90)
		self.btn_curve_hobby_90.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .90, .90)))

		self.btn_curve_prop = QtGui.QAction("curve_prop_alt", self.grp_curve_actions)
		self.btn_curve_prop.setToolTip("Optimize curve: Set handle proportion relative to curve length")
		self.btn_curve_prop.setFont(TRToolFont)
		self.addAction(self.btn_curve_prop)
		self.btn_curve_prop.triggered.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'proportional'))

		self.btn_curve_prop_30 = QtGui.QAction("curve_prop_30", self.grp_curve_actions)
		self.btn_curve_prop_30.setToolTip("Optimize curve: Set handle proportion to 30%% of curve length")
		self.btn_curve_prop_30.setFont(TRToolFont)
		self.addAction(self.btn_curve_prop_30)
		self.btn_curve_prop_30.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .3, .3)))

		self.btn_curve_prop_50 = QtGui.QAction("curve_prop_50", self.grp_curve_actions)
		self.btn_curve_prop_50.setToolTip("Optimize curve: Set handle proportion to 50%% of curve length")
		self.btn_curve_prop_50.setFont(TRToolFont)
		self.addAction(self.btn_curve_prop_50)
		self.btn_curve_prop_50.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .5, .5)))

		self.btn_curve_prop_0 = QtGui.QAction("curve_retract_alt", self.grp_curve_actions)
		self.btn_curve_prop_0.setToolTip("Retract curve handles")
		self.btn_curve_prop_0.setFont(TRToolFont)
		self.addAction(self.btn_curve_prop_0)
		self.btn_curve_prop_0.triggered.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', 0., 0.)))

		

# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

