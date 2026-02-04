#FLM: TypeRig: Toolbar (Float)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.proxy.fl.actions.contour import TRContourActionCollector
from typerig.proxy.fl.actions.curve import TRCurveActionCollector
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.application.app import pWorkspace

from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, TRFlowLayout
from typerig.proxy.fl.gui.dialogs import TRLayerSelectNEW
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init --------------------------
tool_version = '1.2'
tool_name = 'TypeRig Toolbar (Float)'

app = pWorkspace()
TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# -- Global parameters
global pMode
global pLayers
pMode = 0
pLayers = (True, False, False, False)
hide_title = True

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

# -- Main Widget --------------------------
class TRToolbarPanel(QtGui.QDialog):
	def __init__(self):
		super(TRToolbarPanel, self).__init__()

		# - Init
		self.layers_selected = []

		# - Data banks for copy/paste operations
		self.ext_target = {}
		self.slope_bank = {}

		# - Masthead/controller
		self.dlg_layer = TRLayerSelectNEW(self, pMode)
		self.dlg_layer.hide()

		# -- Window toggle button (Mac specific - frameless window)
		self.chk_ToggleTitle = CustomPushButton('window', True, True, True, 'Toggle toolbar window title', obj_name='btn_panel_opt')
		self.chk_ToggleTitle.clicked.connect(self._toggle_window)

		# -- Layer selection buttons
		self.chk_ActiveLayer = CustomPushButton('layer_active', True, True, True, 'Active layer', obj_name='btn_panel_opt')
		self.chk_Masters = CustomPushButton('layer_master', True, False, True, 'Master layers', obj_name='btn_panel_opt')
		self.chk_Selected = CustomPushButton('select_option', True, False, True, 'Selected layers', obj_name='btn_panel_opt')

		# -- Glyph selection buttons
		self.chk_glyph = CustomPushButton('glyph_active', True, True, True, 'Active glyph', obj_name='btn_panel_opt')
		self.chk_window = CustomPushButton('select_window', True, False, True, 'Glyph window', obj_name='btn_panel_opt')
		self.chk_selection = CustomPushButton('select_glyph', True, False, True, 'Font window selection', obj_name='btn_panel_opt')

		# -- Connect signals
		self.chk_ActiveLayer.clicked.connect(self.layers_refresh)
		self.chk_Masters.clicked.connect(self.layers_refresh)
		self.chk_Selected.clicked.connect(self.layers_refresh)

		self.chk_glyph.clicked.connect(self.mode_refresh)
		self.chk_window.clicked.connect(self.mode_refresh)
		self.chk_selection.clicked.connect(self.mode_refresh)

		# - Button groups for exclusive selection
		self.grp_layers = QtGui.QButtonGroup()
		self.grp_glyphs = QtGui.QButtonGroup()

		self.grp_layers.addButton(self.chk_ActiveLayer, 1)
		self.grp_layers.addButton(self.chk_Masters, 2)
		self.grp_layers.addButton(self.chk_Selected, 3)

		self.grp_glyphs.addButton(self.chk_glyph, 1)
		self.grp_glyphs.addButton(self.chk_window, 2)
		self.grp_glyphs.addButton(self.chk_selection, 3)

		# - Single flow layout for everything (masthead + tools)
		self.lay_main = TRFlowLayout(spacing=6)
		self.lay_main.setContentsMargins(12, 12, 12, 12)

		# - Add masthead buttons to flow layout
		self.lay_main.addWidget(self.chk_ToggleTitle)
		
		for button in self.grp_layers.buttons() + self.grp_glyphs.buttons():
			self.lay_main.addWidget(button)

		# - Build all tools (adds directly to lay_main)
		self._build_node_tools()
		self._build_curve_tools()
		self._build_corner_tools()
		self._build_contour_tools()
		self._build_align_tools()
		self._build_slope_tools()

		# - Set Widget
		# Get screen geometry to avoid going off-screen
		screen = QtGui.QApplication.desktop().screenGeometry()
		
		self.setLayout(self.lay_main)
		self.setContentsMargins(6, 6, 6, 6)
		self.setWindowTitle('%s %s' %(tool_name, tool_version))
		self.setGeometry(10, 100, screen.width() - 200, 100)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

		# - Apply style
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)
		self.dlg_layer.setStyleSheet(set_stylesheet)

		self.layers_refresh()
		self.show()

	# - Tool builders ----------------------------------------
	def _build_node_tools(self):
		'''Build node insertion and removal tools'''
		tooltip_button = 'Insert Node'
		self.btn_node_add = CustomPushButton('node_add', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_add)
		self.btn_node_add.clicked.connect(lambda: TRNodeActionCollector.node_insert_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Remove Node'
		self.btn_node_remove = CustomPushButton('node_remove', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_remove)
		self.btn_node_remove.clicked.connect(lambda: TRNodeActionCollector.node_remove(pMode, pLayers))

		tooltip_button = 'Insert Node at the beginning of a Bezier.\n<ALT + Click> Use single node mode.'
		self.btn_node_add_0 = CustomPushButton('node_add_bgn', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_add_0)
		self.btn_node_add_0.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 0., get_modifier()))

		tooltip_button = 'Insert Node at the middle of a Bezier.\n<ALT + Click> Use single node mode.'
		self.btn_node_add_5 = CustomPushButton('node_add_mid', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_add_5)
		self.btn_node_add_5.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, .5, get_modifier()))

		tooltip_button = 'Insert Node at the end of a Bezier.\n<ALT + Click> Use single node mode.'
		self.btn_node_add_1 = CustomPushButton('node_add_end', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_add_1)
		self.btn_node_add_1.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 1., get_modifier()))

		tooltip_button = 'Add Node at Extreme'
		self.btn_node_extreme = CustomPushButton('node_add_extreme_alt', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_extreme)
		self.btn_node_extreme.clicked.connect(lambda: TRNodeActionCollector.node_insert_extreme(pMode, pLayers))

		tooltip_button = 'Round selected nodes to integer coordinates.\n<Click> Ceil.\n<ALT + Click> Floor.\n<Shift + ...> Round all nodes.'
		self.btn_node_round = CustomPushButton('node_round', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_round)
		self.btn_node_round.clicked.connect(lambda: TRNodeActionCollector.node_round(pMode, pLayers, get_modifier(QtCore.Qt.AltModifier), get_modifier(QtCore.Qt.ShiftModifier)))

	def _build_curve_tools(self):
		'''Build curve manipulation tools'''
		tooltip_button = 'Convert node to smooth'
		self.btn_node_smooth = CustomPushButton('node_smooth', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_smooth)
		self.btn_node_smooth.clicked.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, True))

		tooltip_button = 'Convert node to sharp'
		self.btn_node_sharp = CustomPushButton('node_sharp', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_sharp)
		self.btn_node_sharp.clicked.connect(lambda: TRNodeActionCollector.node_smooth(pMode, pLayers, False))

		tooltip_button = 'Convert selected segment to curve'
		self.btn_line_to_curve = CustomPushButton('line_to_curve', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_line_to_curve)
		self.btn_line_to_curve.clicked.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, True))

		tooltip_button = 'Convert selected segment to line'
		self.btn_curve_to_line = CustomPushButton('curve_to_line', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_to_line)
		self.btn_curve_to_line.clicked.connect(lambda: TRCurveActionCollector.segment_convert(pMode, pLayers, False))

		tooltip_button = 'Optimize curve: Tunni'
		self.btn_curve_tunni = CustomPushButton('curve_tunni', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_tunni)
		self.btn_curve_tunni.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'tunni'))

		tooltip_button = 'Optimize curve: Copy handle proportions to masters'
		self.btn_curve_tension_push = CustomPushButton('curve_copy', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_tension_push)
		self.btn_curve_tension_push.clicked.connect(lambda: TRCurveActionCollector.hobby_tension_push(pMode, pLayers))

		tooltip_button = 'Optimize curve: Set Hobby curvature'
		self.btn_curve_hobby = CustomPushButton('curve_hobby', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_hobby)
		self.btn_curve_hobby.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'hobby'))

		tooltip_button = 'Optimize curve: Set Hobby curvature to 1.'
		self.btn_curve_hobby_1 = CustomPushButton('curve_hobby_1', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_hobby_1)
		self.btn_curve_hobby_1.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', 1., 1.)))

		tooltip_button = 'Optimize curve: Set Hobby curvature to .95'
		self.btn_curve_hobby_95 = CustomPushButton('curve_hobby_95', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_hobby_95)
		self.btn_curve_hobby_95.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .95, .95)))

		tooltip_button = 'Optimize curve: Set Hobby curvature to .90'
		self.btn_curve_hobby_90 = CustomPushButton('curve_hobby_90', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_hobby_90)
		self.btn_curve_hobby_90.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('hobby', .90, .90)))

		tooltip_button = 'Optimize curve: Set handle proportion relative to curve length'
		self.btn_curve_prop = CustomPushButton('curve_prop_alt', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_prop)
		self.btn_curve_prop.clicked.connect(lambda: TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, 'proportional'))

		tooltip_button = 'Optimize curve: Set handle proportion to 30%% of curve length'
		self.btn_curve_prop_30 = CustomPushButton('curve_prop_30', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_prop_30)
		self.btn_curve_prop_30.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .3, .3)))

		tooltip_button = 'Optimize curve: Set handle proportion to 50%% of curve length'
		self.btn_curve_prop_50 = CustomPushButton('curve_prop_50', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_prop_50)
		self.btn_curve_prop_50.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', .5, .5)))

		tooltip_button = 'Retract curve handles'
		self.btn_curve_prop_0 = CustomPushButton('curve_retract_alt', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_curve_prop_0)
		self.btn_curve_prop_0.clicked.connect(lambda: TRCurveActionCollector.curve_optimize(pMode, pLayers, ('proportional', 0., 0.)))

	def _build_corner_tools(self):
		'''Build corner manipulation tools'''
		tooltip_button = 'Corner Mitre'
		self.btn_corner_mitre = CustomPushButton('corner_mitre', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_mitre)
		self.btn_corner_mitre.clicked.connect(lambda: TRNodeActionCollector.corner_mitre_dlg(pMode, pLayers))

		tooltip_button = 'Corner Round'
		self.btn_corner_round = CustomPushButton('corner_round', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_round)
		self.btn_corner_round.clicked.connect(lambda: TRNodeActionCollector.corner_round_dlg(pMode, pLayers))

		tooltip_button = 'Corner Loop'
		self.btn_corner_loop = CustomPushButton('corner_loop', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_loop)
		self.btn_corner_loop.clicked.connect(lambda: TRNodeActionCollector.corner_loop_dlg(pMode, pLayers))

		tooltip_button = 'Create Ink Trap\n<ALT + Click> Create non-smooth basic trap.'
		self.btn_corner_trap = CustomPushButton('corner_trap', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_trap)
		self.btn_corner_trap.clicked.connect(lambda: TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Rebuild Corner'
		self.btn_corner_rebuild = CustomPushButton('corner_rebuild', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_rebuild)
		self.btn_corner_rebuild.clicked.connect(lambda: TRNodeActionCollector.corner_rebuild(pMode, pLayers))

	def _build_contour_tools(self):
		'''Build contour manipulation tools'''
		tooltip_button = 'Close selected contours'
		self.btn_contour_close = CustomPushButton('contour_close', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_close)
		self.btn_contour_close.clicked.connect(lambda: TRContourActionCollector.contour_close(pMode, pLayers))

		tooltip_button = 'Boolean Add operation for selected contours\n<ALT + Click> Reverse order'
		self.btn_contour_union = CustomPushButton('contour_union', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_union)
		self.btn_contour_union.clicked.connect(lambda: TRContourActionCollector.contour_bool(pMode, pLayers, 'add', get_modifier()))

		tooltip_button = 'Boolean Subtract operation for selected contours\n<ALT + Click> Reverse order'
		self.btn_contour_subtract = CustomPushButton('contour_subtract', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_subtract)
		self.btn_contour_subtract.clicked.connect(lambda: TRContourActionCollector.contour_bool(pMode, pLayers, 'subtract', get_modifier()))

		tooltip_button = 'Boolean Intersect operation for selected contours\n<ALT + Click> Reverse order'
		self.btn_contour_intersect = CustomPushButton('contour_intersect', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_intersect)
		self.btn_contour_intersect.clicked.connect(lambda: TRContourActionCollector.contour_bool(pMode, pLayers, 'intersect', get_modifier()))

		tooltip_button = 'Boolean Exclude operation for selected contours\n<ALT + Click> Reverse order'
		self.btn_contour_difference = CustomPushButton('contour_difference', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_difference)
		self.btn_contour_difference.clicked.connect(lambda: TRContourActionCollector.contour_bool(pMode, pLayers, 'exclude', get_modifier()))

		tooltip_button = 'Set clockwise winding direction (TrueType)'
		self.btn_contour_cw = CustomPushButton('contour_cw_alt', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_cw)
		self.btn_contour_cw.clicked.connect(lambda: TRContourActionCollector.contour_set_winding(pMode, pLayers, False))

		tooltip_button = 'Set counterclockwise winding direction (PostScript)'
		self.btn_contour_ccw = CustomPushButton('contour_ccw_alt', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_ccw)
		self.btn_contour_ccw.clicked.connect(lambda: TRContourActionCollector.contour_set_winding(pMode, pLayers, True))

		tooltip_button = 'Set start node'
		self.btn_contour_set_start = CustomPushButton('node_start', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_set_start)
		self.btn_contour_set_start.clicked.connect(lambda: TRContourActionCollector.contour_set_start(pMode, pLayers))

		tooltip_button = 'Set start node to bottom left'
		self.btn_contour_set_start_bottom_left = CustomPushButton('node_bottom_left', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_set_start_bottom_left)
		self.btn_contour_set_start_bottom_left.clicked.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (0, 0)))

		tooltip_button = 'Set start node to bottom right'
		self.btn_contour_set_start_bottom_right = CustomPushButton('node_bottom_right', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_set_start_bottom_right)
		self.btn_contour_set_start_bottom_right.clicked.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (1, 0)))

		tooltip_button = 'Set start node to top left'
		self.btn_contour_set_start_top_left = CustomPushButton('node_top_left', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_set_start_top_left)
		self.btn_contour_set_start_top_left.clicked.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (0, 1)))

		tooltip_button = 'Set start node to top right'
		self.btn_contour_set_start_top_right = CustomPushButton('node_top_right', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_set_start_top_right)
		self.btn_contour_set_start_top_right.clicked.connect(lambda: TRContourActionCollector.contour_smart_start(pMode, pLayers, (1, 1)))

		tooltip_button = 'Reorder contours from top to bottom'
		self.btn_contour_sort_y = CustomPushButton('contour_sort_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_sort_y)
		self.btn_contour_sort_y.clicked.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (True, None), False))

		tooltip_button = 'Reorder contours from left to right'
		self.btn_contour_sort_x = CustomPushButton('contour_sort_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_sort_x)
		self.btn_contour_sort_x.clicked.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (None, True), False))

		tooltip_button = 'Reorder contours from bottom to top'
		self.btn_contour_sort_y_rev = CustomPushButton('contour_sort_y_rev', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_sort_y_rev)
		self.btn_contour_sort_y_rev.clicked.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (True, None), True))

		tooltip_button = 'Reorder contours from right to left'
		self.btn_contour_sort_x_rev = CustomPushButton('contour_sort_x_rev', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_sort_x_rev)
		self.btn_contour_sort_x_rev.clicked.connect(lambda: TRContourActionCollector.contour_set_order(pMode, pLayers, (None, True), True))

	def _build_align_tools(self):
		'''Build node alignment tools'''
		# - Options
		self.grp_align_options_shift = QtGui.QButtonGroup()
		self.grp_align_options_other = QtGui.QButtonGroup()
		self.grp_align_options_other.setExclusive(False)

		tooltip_button = 'Smart Shift: Shift oncurve nodes together with their respective offcurve nodes even when they are not explicitly selected.'
		self.chk_shift_smart = CustomPushButton('shift_smart', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_shift.addButton(self.chk_shift_smart, 1)
		self.lay_main.addWidget(self.chk_shift_smart)

		tooltip_button = 'Simple Shift: Shift only selected nodes.'
		self.chk_shift_dumb = CustomPushButton('shift_dumb', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_shift.addButton(self.chk_shift_dumb, 2)
		self.lay_main.addWidget(self.chk_shift_dumb)

		tooltip_button = 'Keep relations between selected nodes'
		self.chk_shift_keep_dimension = CustomPushButton('shift_keep_dimension', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_other.addButton(self.chk_shift_keep_dimension, 1)
		self.lay_main.addWidget(self.chk_shift_keep_dimension)

		tooltip_button = 'Intercept vertical position'
		self.chk_shift_intercept = CustomPushButton('shift_intercept', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_other.addButton(self.chk_shift_intercept, 2)
		self.lay_main.addWidget(self.chk_shift_intercept)

		tooltip_button = 'Pick target node for alignment'
		self.chk_node_target = CustomPushButton('node_target', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_align_options_other.addButton(self.chk_node_target, 3)
		self.lay_main.addWidget(self.chk_node_target)
		self.chk_node_target.clicked.connect(self.target_set)

		# - Actions
		tooltip_button = 'Align selected nodes left'
		self.btn_node_align_left = CustomPushButton('node_align_left', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_left)
		self.btn_node_align_left.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'L', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes right'
		self.btn_node_align_right = CustomPushButton('node_align_right', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_right)
		self.btn_node_align_right.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'R', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes top'
		self.btn_node_align_top = CustomPushButton('node_align_top', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_top)
		self.btn_node_align_top.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'T', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes bottom'
		self.btn_node_align_bottom = CustomPushButton('node_align_bottom', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_bottom)
		self.btn_node_align_bottom.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'B', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to horizontal center of selection'
		self.btn_node_align_selection_x = CustomPushButton('node_align_selection_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_selection_x)
		self.btn_node_align_selection_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'C', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to vertical center of selection'
		self.btn_node_align_selection_y = CustomPushButton('node_align_selection_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_selection_y)
		self.btn_node_align_selection_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'E', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to the horizontal middle of outline bounding box.'
		self.btn_node_align_outline_x = CustomPushButton('node_align_outline_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_outline_x)
		self.btn_node_align_outline_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to the vertical middle of outline bounding box.'
		self.btn_node_align_outline_y = CustomPushButton('node_align_outline_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_outline_y)
		self.btn_node_align_outline_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected node in the horizontal middle of its direct neighbors'
		self.btn_node_align_neigh_x = CustomPushButton('node_align_neigh_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_neigh_x)
		self.btn_node_align_neigh_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected node in the vertical middle of its direct neighbors'
		self.btn_node_align_neigh_y = CustomPushButton('node_align_neigh_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_neigh_y)
		self.btn_node_align_neigh_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to an imaginary line running between highest and lowest node in selection'
		self.btn_node_align_min_max_Y = CustomPushButton('node_align_min_max_Y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_min_max_Y)
		self.btn_node_align_min_max_Y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'Y', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to an imaginary line running between lowest and highest node in selection'
		self.btn_node_align_min_max_X = CustomPushButton('node_align_min_max_X', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_min_max_X)
		self.btn_node_align_min_max_X.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'X', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Collapse all selected nodes to target'
		self.btn_node_target_collapse = CustomPushButton('node_target_collapse', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_target_collapse)
		self.btn_node_target_collapse.clicked.connect(self.target_collapse)

		# - Font metrics alignment
		tooltip_button = 'Align selected nodes to Font metrics: Ascender height'
		self.btn_node_dimension_ascender = CustomPushButton('dimension_ascender', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_ascender)
		self.btn_node_dimension_ascender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_0', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to Font metrics: Caps height'
		self.btn_node_dimension_caps = CustomPushButton('dimension_caps', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_caps)
		self.btn_node_dimension_caps.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_1', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to Font metrics: X height'
		self.btn_node_dimension_xheight = CustomPushButton('dimension_xheight', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_xheight)
		self.btn_node_dimension_xheight.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_3', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to Font metrics: Baseline'
		self.btn_node_dimension_baseline = CustomPushButton('dimension_baseline', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_baseline)
		self.btn_node_dimension_baseline.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_4', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to Font metrics: Descender'
		self.btn_node_dimension_descender = CustomPushButton('dimension_descender', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_descender)
		self.btn_node_dimension_descender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_2', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

		tooltip_button = 'Align selected nodes to Measurement line'
		self.btn_node_dimension_guide = CustomPushButton('dimension_guide', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_dimension_guide)
		self.btn_node_dimension_guide.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_5', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))

	def _build_slope_tools(self):
		'''Build slope copy/paste tools'''
		self.grp_slope_options = QtGui.QButtonGroup()
		self.grp_slope_options.setExclusive(False)

		tooltip_button = 'Copy slope between selected nodes'
		self.chk_slope_copy = CustomPushButton('slope_copy', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_slope_options.addButton(self.chk_slope_copy)
		self.lay_main.addWidget(self.chk_slope_copy)
		self.chk_slope_copy.clicked.connect(self.act_slope_copy)

		tooltip_button = 'Use fonts italic angle as slope'
		self.chk_slope_italic = CustomPushButton('slope_italic', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_slope_options.addButton(self.chk_slope_italic)
		self.lay_main.addWidget(self.chk_slope_italic)
		self.chk_slope_italic.clicked.connect(self.act_slope_italic)

		tooltip_button = 'Paste slope to selected nodes pivoting around the one with lowest vertical coordinates'
		self.btn_slope_paste_min = CustomPushButton('slope_paste_min', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_slope_paste_min)
		self.btn_slope_paste_min.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, False)))

		tooltip_button = 'Paste slope to selected nodes pivoting around the one with highest vertical coordinates'
		self.btn_slope_paste_max = CustomPushButton('slope_paste_max', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_slope_paste_max)
		self.btn_slope_paste_max.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, False)))

		tooltip_button = 'Paste horizontally flipped slope to selected nodes pivoting around the one with lowest vertical coordinates'
		self.btn_slope_paste_min_flip = CustomPushButton('slope_paste_min_flip', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_slope_paste_min_flip)
		self.btn_slope_paste_min_flip.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (False, True)))

		tooltip_button = 'Paste horizontally flipped slope to selected nodes pivoting around the one with highest vertical coordinates'
		self.btn_slope_paste_max_flip = CustomPushButton('slope_paste_max_flip', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_slope_paste_max_flip)
		self.btn_slope_paste_max_flip.clicked.connect(lambda: TRNodeActionCollector.slope_paste(pMode, pLayers, self.slope_bank, (True, True)))

	# - Procedures -----------------------------------
	def _toggle_window(self):
		global hide_title
		if hide_title:
			self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
			hide_title = False
		else:
			self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
			hide_title = True

		self.chk_ToggleTitle.setChecked(hide_title)
		self.show()

	def mode_refresh(self):
		global pMode

		if self.chk_glyph.isChecked(): pMode = 0
		if self.chk_window.isChecked(): pMode = 1
		if self.chk_selection.isChecked(): pMode = 2

		self.dlg_layer.table_populate(pMode)

	def layers_refresh(self):
		global pLayers

		if self.chk_Selected.isChecked():
			self.dlg_layer.show()
			pLayers = self.dlg_layer.tab_masters.getTable()
		else:
			self.dlg_layer.hide()
			pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), False, False)

	def target_set(self):
		if self.chk_node_target.isChecked():
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer)

				if len(selection) > 1:
					# Set target in the middle of selection
					med_x = round(sum([n.x for n in selection])/len(selection))
					med_y = round(sum([n.y for n in selection])/len(selection))
					self.ext_target[layer] = fl6.flNode(QtCore.QPointF(med_x, med_y))
				else:
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

	def act_slope_italic(self):
		if self.chk_slope_italic.isChecked():
			self.slope_bank = TRNodeActionCollector.slope_italic(eGlyph(), pLayers)
		else:
			self.slope_bank = {}

# - RUN ------------------------------
dialog = TRToolbarPanel()