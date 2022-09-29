#FLM: TR: New Nodes
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.application.app import pWorkspace
#from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, CustomSpinButton
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Nodes', '3.01'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Styling ----------------------------
temp_css = '''
QGroupBox#box_group {
	background: #edeeef;
    border-radius: 5px;
    padding-top: 5px;
  	padding-bottom: 5px;
  	padding-right: 5px;
  	padding-left: 5px;
    margin-top: 0px;
  	margin-bottom: 5px;
  	margin-right: 0px;
  	margin-left: 0px;
    border: none;
}

QDoubleSpinBox#spn_panel {
    max-height: 20px;
}

QPushButton#btn_panel {
    color: #212121;
    font-family: "TypeRig Icons";
    font-size: 18px;
    background: none;
    border-radius: 5px;
    /*margin: 2 0 2 0;*/
    /*padding: 2 0 2 0;*/
    max-height: 26px;
    max-width: 26px;
    min-height: 26px;
    min-width: 26px;
}

QPushButton#btn_panel:checked {
    background-color: #9c9e9f;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
    color: #ffffff;
}

QPushButton#btn_panel:checked:hover {
	background-color: #9c9e9f;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
    color: #ffffff;
   
}

QPushButton#btn_panel:hover {
    background-color: #ffffff;
    color: #212121;
}

QPushButton#btn_panel:pressed {
    background-color: #9c9e9f;
    color: #ffffff;
}

QPushButton#btn_panel:disabled {
    background-color: transparent;
    border: none;
}

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

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		
		# - Widgets and tools
		# -- Node tools
		box_node = QtGui.QGroupBox()
		box_node.setObjectName('box_group')
		
		lay_node = QtGui.QHBoxLayout()
		lay_node.setContentsMargins(0, 0, 0, 0)

		tooltip_button = 'Insert Node'
		self.btn_node_add = CustomSpinButton('node_add', (0., 1., .5, .01), ('Set value', tooltip_button), ('spn_panel', 'btn_panel'))
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
		
		# -- Corner Tools
		box_corner = QtGui.QGroupBox()
		box_corner.setObjectName('box_group')
		
		lay_corner = QtGui.QGridLayout()
		lay_corner.setContentsMargins(0, 0, 0, 0)

		tooltip_button = 'Corner Mitre'
		self.btn_corner_mitre = CustomSpinButton('corner_mitre', (0., 300., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_mitre, 1, 0, 1, 3)
		self.btn_corner_mitre.button.clicked.connect(lambda: TRNodeActionCollector.corner_mitre(pMode, pLayers, self.btn_corner_mitre.input.value))

		tooltip_button = 'Corner Round'
		self.btn_corner_round = CustomSpinButton('corner_round', (0., 300., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_round, 1, 3, 1, 3)
		self.btn_corner_round.button.clicked.connect(lambda: TRNodeActionCollector.corner_round(pMode, pLayers, self.btn_corner_round.input.value))

		tooltip_button = 'Corner Loop'
		self.btn_corner_loop = CustomSpinButton('corner_loop', (0., 300., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_panel'))
		lay_corner.addWidget(self.btn_corner_loop, 2, 0, 1, 3)
		self.btn_corner_loop.button.clicked.connect(lambda: TRNodeActionCollector.corner_loop(pMode, pLayers, self.btn_corner_loop.input.value))

		tooltip_button = 'Rebuild Corner'
		self.btn_corner_rebuild = CustomPushButton('corner_rebuild', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_corner_rebuild, 2, 3, 0, 1)
		self.btn_corner_rebuild.clicked.connect(lambda: TRNodeActionCollector.corner_rebuild(pMode, pLayers))
		
		tooltip_button = 'Create Ink Trap\n<ALT + Mouse Left> Create non-smooth basic trap.'
		self.btn_corner_trap = CustomPushButton('corner_trap', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_corner_trap, 2, 4, 0, 1)
		self.btn_corner_trap.clicked.connect(lambda: TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Round selected nodes to integer coordinates.\n<Mouse Left> Ceil.\n<ALT + Mouse Left> Floor.\n<... + Shift> Round all nodes.'
		self.btn_node_round = CustomPushButton('node_round', tooltip=tooltip_button, obj_name='btn_panel')
		lay_corner.addWidget(self.btn_node_round, 2, 5, 0, 1)
		self.btn_node_round.clicked.connect(lambda: TRNodeActionCollector.node_round(pMode, pLayers, get_modifier(QtCore.Qt.AltModifier), get_modifier(QtCore.Qt.ShiftModifier)))

		box_corner.setLayout(lay_corner)
		self.lay_main.addWidget(box_corner)

		# -- Align Tools
		box_align = QtGui.QGroupBox()
		box_align.setObjectName('box_group')

		self.grp_align_options_shift = QtGui.QButtonGroup()
		self.grp_align_options_other = QtGui.QButtonGroup()
		self.grp_align_actions = QtGui.QButtonGroup()

		lay_align = QtGui.QGridLayout()
		lay_align.setContentsMargins(0, 0, 0, 0)

		tooltip_button = "Smart Shift: Shift oncurve nodes together with their respective offcurve nodes even when they are not explicitly selected,"
		self.chk_shift_smart = CustomPushButton("shift_smart", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_align_options_shift.addButton(self.chk_shift_smart, 1)
		lay_align.addWidget(self.chk_shift_smart, 0, 0)

		tooltip_button = "Simple Shift: Shift only selected nodes."
		self.chk_shift_dumb = CustomPushButton("shift_dumb", checkable=True, cheked=True, tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_align_options_shift.addButton(self.chk_shift_dumb, 2)
		lay_align.addWidget(self.chk_shift_dumb, 0, 1)

		tooltip_button = "Keep relations between selected nodes"
		self.chk_shift_keep_dimension = CustomPushButton("shift_keep_dimension", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_align_options_other.addButton(self.chk_shift_keep_dimension, 1)
		lay_align.addWidget(self.chk_shift_keep_dimension, 0, 2)

		tooltip_button = "Intercept vertical position"
		self.chk_shift_intercept = CustomPushButton("shift_intercept", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		self.grp_align_options_other.addButton(self.chk_shift_intercept, 2)
		lay_align.addWidget(self.chk_shift_intercept, 0, 3)

		tooltip_button = "Pick target node for alignment"
		self.chk_node_target = CustomPushButton("node_target", checkable=True, cheked=False, tooltip=tooltip_button, obj_name='btn_panel')
		self.chk_node_target.clicked.connect(self.target_set)
		self.grp_align_options_other.addButton(self.chk_node_target, 3)
		lay_align.addWidget(self.chk_node_target, 0, 4)

		# - Actions
		tooltip_button = "Align selected nodes left"
		self.btn_node_align_left = CustomPushButton("node_align_left", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_left.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'L', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_left)
		lay_align.addWidget(self.btn_node_align_left, 1, 0)

		tooltip_button = "Align selected nodes right"
		self.btn_node_align_right = CustomPushButton("node_align_right", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_right.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'R', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_right)
		lay_align.addWidget(self.btn_node_align_right, 1, 1)

		tooltip_button = "Align selected nodes top"
		self.btn_node_align_top = CustomPushButton("node_align_top", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_top.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'T', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_top)
		lay_align.addWidget(self.btn_node_align_top, 1, 2)

		tooltip_button = "Align selected nodes bottom"
		self.btn_node_align_bottom = CustomPushButton("node_align_bottom", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_bottom.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'B', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_bottom)
		lay_align.addWidget(self.btn_node_align_bottom, 1, 3)

		tooltip_button = "Collapse all selected nodes to target"
		self.btn_node_target_collapse = CustomPushButton("node_target_collapse", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_target_collapse.clicked.connect(self.target_collapse)
		self.grp_align_actions.addButton(self.btn_node_target_collapse)
		lay_align.addWidget(self.btn_node_target_collapse, 1, 4)

		tooltip_button = "Align selected nodes to horizontal center of selection"
		self.btn_node_align_selection_x = CustomPushButton("node_align_selection_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_selection_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'C', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_selection_x)
		lay_align.addWidget(self.btn_node_align_selection_x, 2, 0)

		tooltip_button = "Align selected nodes to vertical center of selection"
		self.btn_node_align_selection_y = CustomPushButton("node_align_selection_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_selection_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'E', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_selection_y)
		lay_align.addWidget(self.btn_node_align_selection_y, 2, 1)

		tooltip_button = "Align selected nodes to the horizontal middle of outline bounding box."
		self.btn_node_align_outline_x = CustomPushButton("node_align_outline_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_outline_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_outline_x)
		lay_align.addWidget(self.btn_node_align_outline_x, 2, 2)

		tooltip_button = "Align selected nodes to the vertical middle of outline bounding box."
		self.btn_node_align_outline_y = CustomPushButton("node_align_outline_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_outline_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'BBoxCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_outline_y)
		lay_align.addWidget(self.btn_node_align_outline_y, 2, 3)

		tooltip_button = "Align selected nodes to Measurment line"
		self.btn_node_dimension_guide = CustomPushButton("dimension_guide", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_guide.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_5', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_guide)
		lay_align.addWidget(self.btn_node_dimension_guide, 2, 4)
		
		tooltip_button = "Align selected node in the horizontal middle of its direct neighbors"
		self.btn_node_align_neigh_x = CustomPushButton("node_align_neigh_x", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_neigh_x.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterX', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_neigh_x)
		lay_align.addWidget(self.btn_node_align_neigh_x, 3, 0)

		tooltip_button = "Align selected node in the vertical middle of its direct neighbors"
		self.btn_node_align_neigh_y = CustomPushButton("node_align_neigh_y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_neigh_y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'peerCenterY', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_neigh_y)
		lay_align.addWidget(self.btn_node_align_neigh_y, 3, 1)

		tooltip_button = "Align selected nodes to an imaginary line runnig between highest and lowest node in selection"
		self.btn_node_align_min_max_Y = CustomPushButton("node_align_min_max_Y", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_min_max_Y.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'Y', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_min_max_Y)
		lay_align.addWidget(self.btn_node_align_min_max_Y, 3, 2)

		tooltip_button = "Align selected nodes to an imaginary line runnig between lowest and highest node in selection"
		self.btn_node_align_min_max_X = CustomPushButton("node_align_min_max_X", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_align_min_max_X.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'X', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_align_min_max_X)
		lay_align.addWidget(self.btn_node_align_min_max_X, 3, 3)

		tooltip_button = "Align selected nodes to Font metrics: Ascender height"
		self.btn_node_dimension_ascender = CustomPushButton("dimension_ascender", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_ascender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_0', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_ascender)
		lay_align.addWidget(self.btn_node_dimension_ascender, 5, 0)

		tooltip_button = "Align selected nodes to Font metrics: Caps height"
		self.btn_node_dimension_caps = CustomPushButton("dimension_caps", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_caps.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_1', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_caps)
		lay_align.addWidget(self.btn_node_dimension_caps, 5, 1)

		tooltip_button = "Align selected nodes to Font metrics: X height"
		self.btn_node_dimension_xheight = CustomPushButton("dimension_xheight", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_xheight.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_3', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_xheight)
		lay_align.addWidget(self.btn_node_dimension_xheight, 5, 2)

		tooltip_button = "Align selected nodes to Font metrics: Baseline"
		self.btn_node_dimension_baseline = CustomPushButton("dimension_baseline", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_baseline.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_4', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_baseline)
		lay_align.addWidget(self.btn_node_dimension_baseline, 5, 3)

		tooltip_button = "Align selected nodes to Font metrics: Descender"
		self.btn_node_dimension_descender = CustomPushButton("dimension_descender", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_node_dimension_descender.clicked.connect(lambda: TRNodeActionCollector.nodes_align(pMode, pLayers, 'FontMetrics_2', self.chk_shift_intercept.isChecked(), self.chk_shift_keep_dimension.isChecked(), self.chk_shift_smart.isChecked(), self.ext_target))
		self.grp_align_actions.addButton(self.btn_node_dimension_descender)
		lay_align.addWidget(self.btn_node_dimension_descender, 5, 4)

		box_align.setLayout(lay_align)
		self.lay_main.addWidget(box_align)
		
		# - Finish it
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


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		self.setStyleSheet(temp_css)
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
	test.setGeometry(100, 100, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()