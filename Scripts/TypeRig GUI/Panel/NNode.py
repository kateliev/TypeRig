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
app_name, app_version = 'TypeRig | Nodes', '3.00'

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

		# - Finish it
		self.setLayout(self.lay_main)


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