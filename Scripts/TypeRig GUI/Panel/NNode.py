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

# - Sub widgets ------------------------
# -- Layouts ---------------------------
class TRNodeBasics(QtGui.QWidget):
	def __init__(self):
		super(TRNodeBasics, self).__init__()
		
		# - Init 

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		
		# - Widgets
		self.lay_main.addWidget(QtGui.QLabel('Node: Basic Operations'))

		tooltip_button = 'Insert Node'
		self.btn_node_add = CustomSpinButton('node_add', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_add)
		self.btn_node_add.button.clicked.connect(lambda: TRNodeActionCollector.node_insert_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Insert Node at the beginning of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_0 = CustomSpinButton('node_add_bgn', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_add_0)
		self.btn_node_add_0.button.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 0., get_modifier()))

		tooltip_button = 'Insert Node at the middle of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_5 = CustomSpinButton('node_add_mid', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_add_5)
		self.btn_node_add_5.button.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, .5, get_modifier()))

		tooltip_button = 'Insert Node at the end of a bezier.\n<ALT + Mouse Left> Use single node mode.'
		self.btn_node_add_1 = CustomSpinButton('node_add_end', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_add_1)
		self.btn_node_add_1.button.clicked.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 1., get_modifier()))

		tooltip_button = 'Remove Node'
		self.btn_node_remove = CustomSpinButton('node_remove', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_remove)
		self.btn_node_remove.button.clicked.connect(lambda: TRNodeActionCollector.node_remove(pMode, pLayers))

		tooltip_button = 'Round selected nodes to integer coordinates.\n<Mouse Left> Ceil.\n<ALT + Mouse Left> Floor.\n<... + Shift> Round all nodes.'
		self.btn_node_round = CustomSpinButton('node_round', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_node_round)
		self.btn_node_round.button.clicked.connect(lambda: TRNodeActionCollector.node_round(pMode, pLayers, get_modifier(QtCore.Qt.AltModifier), get_modifier(QtCore.Qt.ShiftModifier)))

		tooltip_button = 'Corner Mitre'
		self.btn_corner_mitre = CustomSpinButton('corner_mitre', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_corner_mitre)
		self.btn_corner_mitre.button.clicked.connect(lambda: TRNodeActionCollector.corner_mitre_dlg(pMode, pLayers))

		tooltip_button = 'Corner Round'
		self.btn_corner_round = CustomSpinButton('corner_round', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_corner_round)
		self.btn_corner_round.button.clicked.connect(lambda: TRNodeActionCollector.corner_round_dlg(pMode, pLayers))

		tooltip_button = 'Corner Loop'
		self.btn_corner_loop = CustomSpinButton('corner_loop', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_corner_loop)
		self.btn_corner_loop.button.clicked.connect(lambda: TRNodeActionCollector.corner_loop_dlg(pMode, pLayers))

		tooltip_button = 'Create Ink Trap\n<ALT + Mouse Left> Create non-smooth basic trap.'
		self.btn_corner_trap = CustomSpinButton('corner_trap', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_corner_trap)
		self.btn_corner_trap.button.clicked.connect(lambda: TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, get_modifier()))

		tooltip_button = 'Rebuild Corner'
		self.btn_corner_rebuild = CustomSpinButton('corner_rebuild', (0., 100., 0., 1.), ('Set value', tooltip_button), ('spn_panel', 'btn_mast'))
		self.lay_main.addWidget(self.btn_corner_rebuild)
		self.btn_corner_rebuild.button.clicked.connect(lambda: TRNodeActionCollector.corner_rebuild(pMode, pLayers))

		self.setLayout(self.lay_main)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		self.setStyleSheet(css_tr_button)
		layoutV = QtGui.QVBoxLayout()
		
		# - Add widgets to main dialog -------------------------
		layoutV.addWidget(TRNodeBasics())

		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()