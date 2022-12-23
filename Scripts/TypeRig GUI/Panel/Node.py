#FLM: TR: Nodes
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
from math import degrees

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.actions.curve import TRCurveActionCollector
from typerig.proxy.fl.application.app import pWorkspace
#from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomLabel, CustomPushButton, CustomSpinButton, CustomDoubleSpinBox, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Nodes', '3.26'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Styling ----------------------------
temp_css = '''
'''
# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

# - Sub widgets ------------------------
class TRNodeBasics(QtGui.QWidget):
	def __init__(self):
		super(TRNodeBasics, self).__init__()
		
		# - Init 
		self.ext_target = {}
		self.slope_bank = {}
		self.angle_bank = {}
		self.node_bank = {}
		self.node_align_state = 'LT'

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		
		# - Widgets and tools -------------------------------------------------
		# -- Node tools -------------------------------------------------------
		box_node = QtGui.QGroupBox()
		box_node.setObjectName('box_group')
		
		lay_node = TRFlowLayout(spacing=10)

		tooltip_button = 'Insert Node'
		self.btn_node_add = CustomSpinButton('node_add', (0., 1., .5, .01), (tooltip_button + ' time', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_node.addWidget(self.btn_node_add)
		self.btn_node_add.button.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, self.btn_node_add.input.value, get_modifier()))

		tooltip_button = 'Remove Node'
		self.btn_node_remove = CustomPushButton('node_remove', tooltip=tooltip_button, obj_name='btn_panel')
		lay_node.addWidget(self.btn_node_remove)
		self.btn_node_remove.clicked.connect(lambda: TRNodeActionCollector.node_remove(pMode, pLayers))

		tooltip_button = 'Insert Node at the beginning of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_0 = CustomPushButton('node_add_bgn', tooltip=tooltip_button, obj_name='btn_panel')
		lay_node.addWidget(self.btn_node_add_0)
		self.btn_node_add_0.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 0., get_modifier()))

		tooltip_button = 'Insert Node at the middle of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_5 = CustomPushButton('node_add_mid', tooltip=tooltip_button, obj_name='btn_panel')
		lay_node.addWidget(self.btn_node_add_5)
		self.btn_node_add_5.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, .5, get_modifier()))
		
		tooltip_button = 'Insert Node at the end of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_1 = CustomPushButton('node_add_end', tooltip=tooltip_button, obj_name='btn_panel')
		lay_node.addWidget(self.btn_node_add_1)
		self.btn_node_add_1.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 1., get_modifier()))
		
		box_node.setLayout(lay_node)
		self.lay_main.addWidget(box_node)
		
		# -- Curve Tools -------------------------------------------------------
		box_curve = QtGui.QGroupBox()
		box_curve.setObjectName('box_group')
		
		lay_curve = TRFlowLayout(spacing=10)

		# - Actions
		tooltip_button = "Convert node to smooth"
		self.btn_node_smooth = CustomPushButton("node_smooth", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_node_smooth)
		self.btn_node_smooth.clicked.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, True))

		tooltip_button = "Convert node to sharp"
		self.btn_node_sharp = CustomPushButton("node_sharp", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_node_sharp)
		self.btn_node_sharp.clicked.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, False))

		tooltip_button = "Convert selected segment to curve"
		self.btn_line_to_curve = CustomPushButton("line_to_curve", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_line_to_curve)
		self.btn_line_to_curve.clicked.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, True))

		tooltip_button = "Convert selected segment to line"
		self.btn_curve_to_line = CustomPushButton("curve_to_line", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_to_line)
		self.btn_curve_to_line.clicked.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, False))

		tooltip_button = "Optimize curve: Tunni"
		self.btn_curve_tunni = CustomPushButton("curve_tunni", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_tunni)
		self.btn_curve_tunni.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'tunni'))

		tooltip_button = "Optimize curve: Set Hobby curvature"
		self.btn_curve_hobby = CustomPushButton("curve_hobby", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_hobby)
		self.btn_curve_hobby.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'hobby'))

		tooltip_button = "Optimize curve: Set Hobby curvature to 1."
		self.btn_curve_hobby_1 = CustomPushButton("curve_hobby_1", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_hobby_1)
		self.btn_curve_hobby_1.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', 1., 1.)))

		tooltip_button = "Optimize curve: Set Hobby curvature to .95"
		self.btn_curve_hobby_95 = CustomPushButton("curve_hobby_95", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_hobby_95)
		self.btn_curve_hobby_95.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .95, .95)))

		tooltip_button = "Optimize curve: Set Hobby curvature to .90"
		self.btn_curve_hobby_90 = CustomPushButton("curve_hobby_90", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_hobby_90)
		self.btn_curve_hobby_90.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .90, .90)))

		tooltip_button = "Optimize curve: Set handle proportion relative to curve length"
		self.btn_curve_prop = CustomPushButton("curve_prop_alt", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_prop)
		self.btn_curve_prop.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'proportional'))

		tooltip_button = "Optimize curve: Set handle proportion to 30%% of curve length"
		self.btn_curve_prop_30 = CustomPushButton("curve_prop_30", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_prop_30)
		self.btn_curve_prop_30.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .3, .3)))

		tooltip_button = "Optimize curve: Set handle proportion to 50%% of curve length"
		self.btn_curve_prop_50 = CustomPushButton("curve_prop_50", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_prop_50)
		self.btn_curve_prop_50.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .5, .5)))

		tooltip_button = "Retract curve handles"
		self.btn_curve_prop_0 = CustomPushButton("curve_retract_alt", tooltip=tooltip_button, obj_name='btn_panel')
		lay_curve.addWidget(self.btn_curve_prop_0)
		self.btn_curve_prop_0.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', 0., 0.)))

		box_curve.setLayout(lay_curve)
		self.lay_main.addWidget(box_curve)

		# -- Corner Tools -------------------------------------------------------
		box_corner = QtGui.QGroupBox()
		box_corner.setObjectName('box_group')
		
		lay_corner = TRFlowLayout(spacing=10)
		lay_corner.setContentsMargins(0, 0, 0, 0)

		tooltip_button = 'Corner Mitre'
		self.btn_corner_mitre = CustomSpinButton('corner_mitre', (0., 300., 0., 1.), (tooltip_button + ' value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_mitre)
		self.btn_corner_mitre.button.clicked.connect(lambda: TRNodeActionCollector.corner_mitre(pMode, pLayers, self.btn_corner_mitre.input.value))

		tooltip_button = 'Corner Round'
		self.btn_corner_round = CustomSpinButton('corner_round', (0., 300., 0., 1.), (tooltip_button + ' value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_round)
		self.btn_corner_round.button.clicked.connect(lambda: TRNodeActionCollector.corner_round(pMode, pLayers, self.btn_corner_round.input.value))

		tooltip_button = 'Corner Loop'
		self.btn_corner_loop = CustomSpinButton('corner_loop', (0., 300., 0., 1.), (tooltip_button + ' value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_loop)
		self.btn_corner_loop.button.clicked.connect(lambda: TRNodeActionCollector.corner_loop(pMode, pLayers, self.btn_corner_loop.input.value))
		
		tooltip_button = 'Create Ink Trap\n<ALT + Mouse Left> Create non-smooth basic trap.'
		self.btn_corner_trap = CustomPushButton('corner_trap', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_corner_trap)
		self.btn_corner_trap.clicked.connect(lambda: TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Rebuild Corner'
		self.btn_corner_rebuild = CustomPushButton('corner_rebuild', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_corner_rebuild)
		self.btn_corner_rebuild.clicked.connect(lambda: TRNodeActionCollector.corner_rebuild(pMode, pLayers))

		tooltip_button = 'Round cap\nCreate a rounded cap between selected two nodes.'
		self.btn_cap_round = CustomPushButton('cap_round', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_cap_round)
		self.btn_cap_round.clicked.connect(lambda: TRNodeActionCollector.cap_round(eGlyph(), pLayers, get_modifier()))

		tooltip_button = 'Square cap\nCreate/resore a rounded cap to square form between all selected round cap nodes.'
		self.btn_cap_square = CustomPushButton('cap_restore', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_cap_square)
		self.btn_cap_square.clicked.connect(lambda: TRNodeActionCollector.cap_rebuild(eGlyph(), pLayers))

		#lay_corner.setColumnStretch(lay_corner.columnCount(), 1)
		box_corner.setLayout(lay_corner)
		self.lay_main.addWidget(box_corner)

		# -- Align Tools -------------------------------------------------------
		box_align = QtGui.QGroupBox()
		box_align.setObjectName('box_group')

		self.grp_align_options_shift = QtGui.QButtonGroup()
		self.grp_align_options_other = QtGui.QButtonGroup()
		self.grp_align_actions = QtGui.QButtonGroup()

		lay_align = QtGui.QVBoxLayout()
		lay_align_options = QtGui.QHBoxLayout()
		lay_align_options.setSpacing(9)
		lay_align_actions = TRFlowLayout(spacing=10)

		tooltip_button = "Smart Shift: Shift oncurve nodes together with their respective offcurve nodes even when they are not explicitly selected,"
		self.chk_shift_smart = CustomPushButton("shift_smart", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_shift.addButton(self.chk_shift_smart, 1)
		lay_align_options.addWidget(self.chk_shift_smart)

		tooltip_button = "Simple Shift: Shift only selected nodes."
		self.chk_shift_dumb = CustomPushButton("shift_dumb", checkable=True, cheked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_shift.addButton(self.chk_shift_dumb, 2)
		lay_align_options.addWidget(self.chk_shift_dumb)

		tooltip_button = "Keep relations between selected nodes"
		self.chk_shift_keep_dimension = CustomPushButton("shift_keep_dimension", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_other.addButton(self.chk_shift_keep_dimension, 1)
		lay_align_options.addWidget(self.chk_shift_keep_dimension)

		tooltip_button = "Intercept vertical position"
		self.chk_shift_intercept = CustomPushButton("shift_intercept", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_other.addButton(self.chk_shift_intercept, 2)
		lay_align_options.addWidget(self.chk_shift_intercept)

		tooltip_button = "Pick target node for alignment"
		self.chk_node_target = CustomPushButton("node_target", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.chk_node_target.clicked.connect(self.target_set)
		self.grp_align_options_other.addButton(self.chk_node_target, 3)
		lay_align_options.addWidget(self.chk_node_target)

		# --- Actions
		tooltip_button = "Align selected nodes left"
		self.btn_node_align_left = CustomPushButton("node_align_left", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_left.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'L', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_left)
		lay_align_actions.addWidget(self.btn_node_align_left)

		tooltip_button = "Align selected nodes right"
		self.btn_node_align_right = CustomPushButton("node_align_right", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_right.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'R', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_right)
		lay_align_actions.addWidget(self.btn_node_align_right)

		tooltip_button = "Align selected nodes top"
		self.btn_node_align_top = CustomPushButton("node_align_top", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_top.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'T', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_top)
		lay_align_actions.addWidget(self.btn_node_align_top)

		tooltip_button = "Align selected nodes bottom"
		self.btn_node_align_bottom = CustomPushButton("node_align_bottom", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_bottom.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'B', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_bottom)
		lay_align_actions.addWidget(self.btn_node_align_bottom)

		tooltip_button = "Collapse all selected nodes to target"
		self.btn_node_target_collapse = CustomPushButton("node_target_collapse", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_target_collapse.clicked.connect(self.target_collapse)
		self.grp_align_actions.addButton(self.btn_node_target_collapse)
		lay_align_actions.addWidget(self.btn_node_target_collapse)

		tooltip_button = "Align selected nodes to horizontal center of selection"
		self.btn_node_align_selection_x = CustomPushButton("node_align_selection_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_selection_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'C', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_selection_x)
		lay_align_actions.addWidget(self.btn_node_align_selection_x)

		tooltip_button = "Align selected nodes to vertical center of selection"
		self.btn_node_align_selection_y = CustomPushButton("node_align_selection_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_selection_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'E', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_selection_y)
		lay_align_actions.addWidget(self.btn_node_align_selection_y)

		tooltip_button = "Align selected nodes to the horizontal middle of outline bounding box."
		self.btn_node_align_outline_x = CustomPushButton("node_align_outline_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_outline_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_outline_x)
		lay_align_actions.addWidget(self.btn_node_align_outline_x)

		tooltip_button = "Align selected nodes to the vertical middle of outline bounding box."
		self.btn_node_align_outline_y = CustomPushButton("node_align_outline_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_outline_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_outline_y)
		lay_align_actions.addWidget(self.btn_node_align_outline_y)
		
		tooltip_button = "Align selected node in the horizontal middle of its direct neighbors"
		self.btn_node_align_neigh_x = CustomPushButton("node_align_neigh_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_neigh_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_neigh_x)
		lay_align_actions.addWidget(self.btn_node_align_neigh_x)

		tooltip_button = "Align selected node in the vertical middle of its direct neighbors"
		self.btn_node_align_neigh_y = CustomPushButton("node_align_neigh_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_neigh_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_neigh_y)
		lay_align_actions.addWidget(self.btn_node_align_neigh_y)

		tooltip_button = "Align selected nodes to an imaginary line runnig between highest and lowest node in selection"
		self.btn_node_align_min_max_Y = CustomPushButton("node_align_min_max_Y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_min_max_Y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'Y', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_min_max_Y)
		lay_align_actions.addWidget(self.btn_node_align_min_max_Y)

		tooltip_button = "Align selected nodes to an imaginary line runnig between lowest and highest node in selection"
		self.btn_node_align_min_max_X = CustomPushButton("node_align_min_max_X", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_min_max_X.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'X', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_min_max_X)
		lay_align_actions.addWidget(self.btn_node_align_min_max_X)

		tooltip_button = 'Align selected nodes to integer grid (Round coordinates).\n<Mouse Left> Ceil.\n<ALT + Mouse Left> Floor.\n<... + Shift> Round all nodes.'
		self.btn_node_round = CustomPushButton('node_round', tooltip=tooltip_button, obj_name='btn_panel')
		lay_align_actions.addWidget(self.btn_node_round)
		self.btn_node_round.clicked.connect(lambda: TRNodeActionCollector.node_round(pMode, pLayers, get_modifier(QtCore.Qt.AltModifier), get_modifier(QtCore.Qt.ShiftModifier)))

		tooltip_button = "Align selected nodes to Font metrics: Ascender height"
		self.btn_node_dimension_ascender = CustomPushButton("dimension_ascender", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_ascender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_0', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_ascender)
		lay_align_actions.addWidget(self.btn_node_dimension_ascender)

		tooltip_button = "Align selected nodes to Font metrics: Caps height"
		self.btn_node_dimension_caps = CustomPushButton("dimension_caps", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_caps.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_1', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_caps)
		lay_align_actions.addWidget(self.btn_node_dimension_caps)

		tooltip_button = "Align selected nodes to Font metrics: X height"
		self.btn_node_dimension_xheight = CustomPushButton("dimension_xheight", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_xheight.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_3', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_xheight)
		lay_align_actions.addWidget(self.btn_node_dimension_xheight)

		tooltip_button = "Align selected nodes to Font metrics: Baseline"
		self.btn_node_dimension_baseline = CustomPushButton("dimension_baseline", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_baseline.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_4', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_baseline)
		lay_align_actions.addWidget(self.btn_node_dimension_baseline)

		tooltip_button = "Align selected nodes to Font metrics: Descender"
		self.btn_node_dimension_descender = CustomPushButton("dimension_descender", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_descender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_2', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_descender)
		lay_align_actions.addWidget(self.btn_node_dimension_descender)

		tooltip_button = "Align selected nodes to Measurment line"
		self.btn_node_dimension_guide = CustomPushButton("dimension_guide", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_guide.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_5', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_guide)
		lay_align_actions.addWidget(self.btn_node_dimension_guide)

		lay_align_options.addStretch()
		lay_align.addLayout(lay_align_options)
		lay_align.addLayout(lay_align_actions)
		box_align.setLayout(lay_align)
		self.lay_main.addWidget(box_align)

		# -- Slope tools -------------------------------------------------------
		box_slope = QtGui.QGroupBox()
		box_slope.setObjectName('box_group')

		self.grp_slope_options = QtGui.QButtonGroup()

		lay_slope =TRFlowLayout(spacing=10)
		lay_slope.setContentsMargins(0, 0, 0, 0)

		# --- Options 
		tooltip_button =  "Copy slope between selected nodes"
		self.chk_slope_copy = CustomPushButton("slope_copy", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_slope_options.addButton(self.chk_slope_copy)
		lay_slope.addWidget(self.chk_slope_copy)
		self.chk_slope_copy.clicked.connect(self.act_slope_copy)

		tooltip_button =  "Use fonts italic angle as slope"
		self.chk_slope_italic = CustomPushButton("slope_italic", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_slope_options.addButton(self.chk_slope_italic)
		lay_slope.addWidget(self.chk_slope_italic)
		self.chk_slope_italic.clicked.connect(self.act_slope_italic)

		# - Actions
		tooltip_button =  "Paste slope to selected nodes pivoting around the one with lowest vertical coordinates"
		self.btn_slope_paste_min = CustomPushButton("slope_paste_min", tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_slope_options.addButton(self.btn_slope_paste_min)
		lay_slope.addWidget(self.btn_slope_paste_min)
		self.btn_slope_paste_min.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, False)))

		tooltip_button =  "Paste slope to selected nodes pivoting around the one with highest vertical coordinates"
		self.btn_slope_paste_max = CustomPushButton("slope_paste_max", tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_slope_options.addButton(self.btn_slope_paste_max)
		lay_slope.addWidget(self.btn_slope_paste_max)
		self.btn_slope_paste_max.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, False)))

		tooltip_button =  "Paste horizontally flipped slope to selected nodes pivoting around the one with lowest vertical coordinates"
		self.btn_slope_paste_min_flip = CustomPushButton("slope_paste_min_flip", tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_slope_options.addButton(self.btn_slope_paste_min_flip)
		lay_slope.addWidget(self.btn_slope_paste_min_flip)
		self.btn_slope_paste_min_flip.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, True)))

		tooltip_button =  "Paste horizontally flipped slope to selected nodes pivoting around the one with highest vertical coordinates"
		self.btn_slope_paste_max_flip = CustomPushButton("slope_paste_max_flip", tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_slope_options.addButton(self.btn_slope_paste_max_flip)
		lay_slope.addWidget(self.btn_slope_paste_max_flip)
		self.btn_slope_paste_max_flip.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, True)))

		#lay_slope.setColumnStretch(lay_slope.columnCount(), 1)
		box_slope.setLayout(lay_slope)
		self.lay_main.addWidget(box_slope)

		# -- Copy Nodes ------------------------------------------------------
		box_copy_nodes = QtGui.QGroupBox()
		box_copy_nodes.setObjectName('box_group')

		self.grp_copy_nodes_options = QtGui.QButtonGroup()

		lay_copy_nodes = TRFlowLayout(spacing=10)
		lay_copy_nodes.setContentsMargins(0, 0, 0, 0)

		# --- Options
		tooltip_button =  "Paste Align Top Left"
		self.chk_paste_top_left = CustomPushButton("node_align_top_left", checkable=True, cheked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_copy_nodes_options.addButton(self.chk_paste_top_left)
		lay_copy_nodes.addWidget(self.chk_paste_top_left)
		self.chk_paste_top_left.clicked.connect(lambda: self.act_node_align_state('LT'))

		tooltip_button =  "Paste: Align Top Right"
		self.chk_paste_top_right = CustomPushButton("node_align_top_right", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_copy_nodes_options.addButton(self.chk_paste_top_right)
		lay_copy_nodes.addWidget(self.chk_paste_top_right)
		self.chk_paste_top_right.clicked.connect(lambda: self.act_node_align_state('RT'))

		tooltip_button =  "Paste: Align Center"
		self.chk_paste_center = CustomPushButton("node_center", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_copy_nodes_options.addButton(self.chk_paste_center)
		lay_copy_nodes.addWidget(self.chk_paste_center)
		self.chk_paste_top_right.clicked.connect(lambda: self.act_node_align_state('CE'))

		tooltip_button =  "Paste: Align Bottom Left"
		self.chk_paste_bottom_left = CustomPushButton("node_align_bottom_left", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_copy_nodes_options.addButton(self.chk_paste_bottom_left)
		lay_copy_nodes.addWidget(self.chk_paste_bottom_left)
		self.chk_paste_bottom_left.clicked.connect(lambda: self.act_node_align_state('LB'))

		tooltip_button =  "Paste: Align Bottom Right"
		self.chk_paste_bottom_right = CustomPushButton("node_align_bottom_right", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_copy_nodes_options.addButton(self.chk_paste_bottom_right)
		lay_copy_nodes.addWidget(self.chk_paste_bottom_right)
		self.chk_paste_bottom_right.clicked.connect(lambda: self.act_node_align_state('RB'))

		tooltip_button =  "Paste: Flip horizontally"
		self.chk_paste_flip_h = CustomPushButton("flip_horizontal", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		#self.grp_paste_nodes_options.addButton(self.chk_paste_flip_h)
		lay_copy_nodes.addWidget(self.chk_paste_flip_h)
		#self.chk_paste_flip_h.clicked.connect(...)

		tooltip_button =  "Paste: Flip vertically"
		self.chk_paste_flip_v = CustomPushButton("flip_vertical", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		#self.grp_paste_nodes_options.addButton(self.chk_paste_flip_v)
		lay_copy_nodes.addWidget(self.chk_paste_flip_v)
		#self.chk_paste_flip_v.clicked.connect(...)

		tooltip_button =  "Paste: Reverse Order"
		self.chk_paste_reverse = CustomPushButton("contour_reverse", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		#self.grp_copy_nodes_options.addButton(self.chk_paste_reverse)
		lay_copy_nodes.addWidget(self.chk_paste_reverse)
		#self.chk_paste_reverse.clicked.connect(...)

		tooltip_button =  "Copy: Selected Nodes to Memory"
		self.chk_copy_nodes = CustomPushButton("node_copy", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		#self.grp_copy_nodes_options.addButton(self.chk_copy_nodes)
		lay_copy_nodes.addWidget(self.chk_copy_nodes)
		self.chk_copy_nodes.clicked.connect(self.act_node_copy)

		tooltip_button =  "Paste: Nodes stored in Memory"
		self.btn_paste_nodes = CustomPushButton("node_paste", checkable=False, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		#self.grp_copy_nodes_options.addButton(self.btn_paste_nodes)
		lay_copy_nodes.addWidget(self.btn_paste_nodes)
		self.btn_paste_nodes.clicked.connect(lambda: TRNodeActionCollector.nodes_paste(eGlyph(), pLayers, self.node_bank, self.node_align_state, (self.chk_paste_flip_h.isChecked(), self.chk_paste_flip_v.isChecked(), self.chk_paste_reverse.isChecked(), False, False, False)))
		
		#lay_copy_nodes.setColumnStretch(lay_copy_nodes.columnCount(), 1)
		box_copy_nodes.setLayout(lay_copy_nodes)
		self.lay_main.addWidget(box_copy_nodes)

		# -- Move Nodes ------------------------------------------------------
		box_move_nodes = QtGui.QGroupBox()
		box_move_nodes.setObjectName('box_group')

		self.grp_move_nodes_options = QtGui.QButtonGroup()

		lay_move_nodes = QtGui.QGridLayout()
		lay_move_nodes.setContentsMargins(0, 0, 0, 0)

		# --- Options
		tooltip_button =  "Smart Shift:\n Move off-curve nodes together with on-curve ones"
		self.chk_shift_smart = CustomPushButton("shift_smart", checkable=True, cheked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_move_nodes_options.addButton(self.chk_shift_smart)
		lay_move_nodes.addWidget(self.chk_shift_smart, 0, 0, 1, 1)

		tooltip_button =  "Shift:\n Do not move off-curve nodes together with on-curve ones"
		self.chk_shift_dumb = CustomPushButton("shift_dumb", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_move_nodes_options.addButton(self.chk_shift_dumb)
		lay_move_nodes.addWidget(self.chk_shift_dumb, 0, 1, 1, 1)

		tooltip_button =  "Interpolated shift"
		self.chk_shift_lerp = CustomPushButton("shift_interpolate", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_move_nodes_options.addButton(self.chk_shift_lerp)
		lay_move_nodes.addWidget(self.chk_shift_lerp, 0, 2, 1, 1)
		#self.chk_paste_top_left.clicked.connect(...)

		tooltip_button =  "Italic walker:\n Vertical shift along the font's italic angle"
		self.chk_shift_italic = CustomPushButton("shift_slope_italik", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_move_nodes_options.addButton(self.chk_shift_italic)
		lay_move_nodes.addWidget(self.chk_shift_italic, 0, 3, 1, 1)

		tooltip_button =  "Slope walker:\n Vertical shift along a given slope"
		self.chk_shift_slope = CustomPushButton("shift_slope_walk", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_move_nodes_options.addButton(self.chk_shift_slope)
		lay_move_nodes.addWidget(self.chk_shift_slope, 0, 4, 1, 1)

		tooltip_button =  "Copy slope between selected nodes"
		self.btn_shift_slope_copy = CustomPushButton("slope_copy", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_move_nodes.addWidget(self.btn_shift_slope_copy, 0, 5, 1, 1)
		self.btn_shift_slope_copy.clicked.connect( self.act_shift_angle_copy)

		lbl_x = CustomLabel('width_x', obj_name='lbl_panel')
		lay_move_nodes.addWidget(lbl_x, 1, 0, 1, 1)

		self.spn_move_x = CustomDoubleSpinBox(init_values=(-999., 999., 1., 1.), tooltip='Horizontal shift value', obj_name='spn_panel')
		lay_move_nodes.addWidget(self.spn_move_x, 1, 1, 1, 2)

		lbl_y = CustomLabel('width_y', obj_name='lbl_panel')
		lay_move_nodes.addWidget(lbl_y, 2, 0, 1, 1)

		self.spn_move_y = CustomDoubleSpinBox(init_values=(-999., 999., 1., 1.), tooltip='Vertical shift value', obj_name='spn_panel')
		lay_move_nodes.addWidget(self.spn_move_y, 2, 1, 1, 2)

		tooltip_button = "Shift Left"
		self.btn_shift_left = CustomPushButton("arrow_left", checkable=False, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_move_nodes.addWidget(self.btn_shift_left, 1, 3, 1, 1)
		self.btn_shift_left.clicked.connect(lambda: self.act_node_move(-self.spn_move_x.value, 0)) 

		tooltip_button = "Shift Right"
		self.btn_shift_right = CustomPushButton("arrow_right", checkable=False, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_move_nodes.addWidget(self.btn_shift_right, 1, 4, 1, 1)
		self.btn_shift_right.clicked.connect(lambda: self.act_node_move(self.spn_move_x.value, 0))

		tooltip_button = "Shift Up"
		self.btn_shift_up = CustomPushButton("arrow_up", checkable=False, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_move_nodes.addWidget(self.btn_shift_up, 2, 3, 1, 1)
		self.btn_shift_up.clicked.connect(lambda: self.act_node_move(0, self.spn_move_y.value))

		tooltip_button = "Shift Down"
		self.btn_shift_down = CustomPushButton("arrow_down", checkable=False, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_move_nodes.addWidget(self.btn_shift_down, 2, 4, 1, 1)
		self.btn_shift_down.clicked.connect(lambda: self.act_node_move(0, -self.spn_move_y.value))

		tooltip_button =  "Percent of BBox:\n Interpret new positional coordinates as if they were scaled by percent given in (X,Y)\nEquivalent to affine scaling of selected nodes in respect to the Layers BoundingBox"
		self.chk_shift_bbox_percent = CustomPushButton("bbox_percent", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_move_nodes.addWidget(self.chk_shift_bbox_percent, 0, 6, 1, 1)
		
		tooltip_button =  "Capture keyboard:\n Capture input from the keyboard arrow keys"
		self.chk_shift_capture = CustomPushButton("keyboard_arows", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.chk_shift_capture.setEnabled(False)
		lay_move_nodes.addWidget(self.chk_shift_capture, 2, 5, 1, 1)
		
		lay_move_nodes.setColumnStretch(lay_move_nodes.columnCount(), 1)
		box_move_nodes.setLayout(lay_move_nodes)
		self.lay_main.addWidget(box_move_nodes)
		
		# -- Finish it -------------------------------------------------------
		self.setLayout(self.lay_main)

	# - Procedures ------------------------------------------------
	def target_set(self):
		if self.chk_node_target.isChecked():
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				self.ext_target[layer] = glyph.selectedNodes(layer)[0]

		else:
			self.ext_target = {}

	def target_collapse(self):
		if self.chk_node_target.isChecked() and len(self.ext_target.keys()):
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				if layer in self.ext_target.keys():
					for node in glyph.selectedNodes(layer):
						node.x = self.ext_target[layer].x
						node.y = self.ext_target[layer].y

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: {}; Nodes collapsed; Layers:\t {}'.format(glyph.name, '; '.join(wLayers)))

	def act_slope_copy(self):
		if self.chk_slope_copy.isChecked():
			self.slope_bank = TRNodeActionCollector.slope_copy(eGlyph(), pLayers)
		else:
			self.slope_bank = {}

	def act_shift_angle_copy(self):
		if self.btn_shift_slope_copy.isChecked():
			self.angle_bank = TRNodeActionCollector.angle_copy(eGlyph(), pLayers)
		else:
			self.angle_bank = {}
		print(self.angle_bank)

	def act_slope_italic(self):
		if self.chk_slope_italic.isChecked():
			self.slope_bank = TRNodeActionCollector.slope_italic(eGlyph(), pLayers)
		else:
			self.slope_bank = {}

	def act_node_copy(self):
		if self.chk_copy_nodes.isChecked():
			self.node_bank = TRNodeActionCollector.nodes_copy(eGlyph(), pLayers)
		else:
			self.node_bank = {}

	def act_node_align_state(self, align_state):
		self.node_align_state = align_state

	def act_node_move(self, offset_x, offset_y):
		if self.chk_shift_smart.isChecked():
			method = 'SMART'
		elif self.chk_shift_dumb.isChecked():
			method = 'MOVE'
		elif self.chk_shift_lerp.isChecked():
			method = 'LERP'
		elif self.chk_shift_italic.isChecked():
			method = 'SLANT'
		elif self.chk_shift_slope.isChecked():
			method = 'SLOPE'
		else:
			method = None

		if self.chk_shift_bbox_percent.isChecked():
			percent_of_bbox = True
			offset_x /= 100
			offset_y /= 100
		else:
			percent_of_bbox = False

		TRNodeActionCollector.nodes_move(eGlyph(), pLayers, offset_x, offset_y, method, self.angle_bank, percent_of_bbox)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		self.setStyleSheet(css_tr_button)
		layoutV = QtGui.QVBoxLayout()
		layoutV.setContentsMargins(0, 0, 0, 0)

		
		# - Add widgets to main dialog -------------------------
		layoutV.addWidget(TRNodeBasics())

		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()