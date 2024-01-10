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
tool_version = '1.62'
tool_name = 'TypeRig Nodes'

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

		# - Actions and dialogs
		self.grp_nodes = QtGui.QActionGroup(self)
		self.grp_corner = QtGui.QActionGroup(self)

		# -- Insert and remove nodes
		self.btn_node_add = QtGui.QAction("node_add", self.grp_nodes)
		self.btn_node_add.setToolTip("Insert Node")
		self.btn_node_add.setFont(TRToolFont)
		self.addAction(self.btn_node_add)
		self.btn_node_add.triggered.connect(lambda: TRNodeActionCollector.node_insert_dlg(pMode, pLayers, get_modifier()))

		self.btn_node_remove = QtGui.QAction("node_remove", self.grp_nodes)
		self.btn_node_remove.setToolTip("Remove Node")
		self.btn_node_remove.setFont(TRToolFont)
		self.addAction(self.btn_node_remove)
		self.btn_node_remove.triggered.connect(lambda: TRNodeActionCollector.node_remove(pMode, pLayers))
		
		self.btn_node_add_0 = QtGui.QAction("node_add_bgn", self.grp_nodes)
		self.btn_node_add_0.setToolTip("Insert Node at the beginning of a bezier.\n<ALT + Mouse Left> Use single node mode.")
		self.btn_node_add_0.setFont(TRToolFont)
		self.addAction(self.btn_node_add_0)
		self.btn_node_add_0.triggered.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 0., get_modifier()))

		self.btn_node_add_5 = QtGui.QAction("node_add_mid", self.grp_nodes)
		self.btn_node_add_5.setToolTip("Insert Node at the middle of a bezier.\n<ALT + Mouse Left> Use single node mode.")
		self.btn_node_add_5.setFont(TRToolFont)
		self.addAction(self.btn_node_add_5)
		self.btn_node_add_5.triggered.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, .5, get_modifier()))

		self.btn_node_add_1 = QtGui.QAction("node_add_end", self.grp_nodes)
		self.btn_node_add_1.setToolTip("Insert Node at the end of a bezier.\n<ALT + Mouse Left> Use single node mode.")
		self.btn_node_add_1.setFont(TRToolFont)
		self.addAction(self.btn_node_add_1)
		self.btn_node_add_1.triggered.connect(lambda: TRNodeActionCollector.node_insert(pMode, pLayers, 1., get_modifier()))

		self.btn_node_extreme = QtGui.QAction("node_add_extreme_alt", self.grp_nodes)
		self.btn_node_extreme.setToolTip("Add Node at Extreme")
		self.btn_node_extreme.setFont(TRToolFont)
		self.addAction(self.btn_node_extreme)
		self.btn_node_extreme.triggered.connect(lambda: TRNodeActionCollector.node_insert_extreme(pMode, pLayers))

		self.btn_node_round = QtGui.QAction("node_round", self.grp_nodes)
		self.btn_node_round.setToolTip("Round selected nodes to integer coordinates.\n<Mouse Left> Ceil.\n<ALT + Mouse Left> Floor.\n<... + Shift> Round all nodes.")
		self.btn_node_round.setFont(TRToolFont)
		self.addAction(self.btn_node_round)
		self.btn_node_round.triggered.connect(lambda: TRNodeActionCollector.node_round(pMode, pLayers, get_modifier(QtCore.Qt.AltModifier), get_modifier(QtCore.Qt.ShiftModifier)))

		self.btn_corner_mitre = QtGui.QAction("corner_mitre", self.grp_corner)
		self.btn_corner_mitre.setToolTip("Corner Mitre")
		self.btn_corner_mitre.setFont(TRToolFont)
		self.addAction(self.btn_corner_mitre)
		self.btn_corner_mitre.triggered.connect(lambda: TRNodeActionCollector.corner_mitre_dlg(pMode, pLayers))

		self.btn_corner_round = QtGui.QAction("corner_round", self.grp_corner)
		self.btn_corner_round.setToolTip("Corner Round")
		self.btn_corner_round.setFont(TRToolFont)
		self.addAction(self.btn_corner_round)
		self.btn_corner_round.triggered.connect(lambda: TRNodeActionCollector.corner_round_dlg(pMode, pLayers))

		self.btn_corner_loop = QtGui.QAction("corner_loop", self.grp_corner)
		self.btn_corner_loop.setToolTip("Corner Loop")
		self.btn_corner_loop.setFont(TRToolFont)
		self.addAction(self.btn_corner_loop)
		self.btn_corner_loop.triggered.connect(lambda: TRNodeActionCollector.corner_loop_dlg(pMode, pLayers))

		self.btn_corner_trap = QtGui.QAction("corner_trap", self.grp_corner)
		self.btn_corner_trap.setToolTip("Create Ink Trap\n<ALT + Mouse Left> Create non-smooth basic trap.")
		self.btn_corner_trap.setFont(TRToolFont)
		self.addAction(self.btn_corner_trap)
		self.btn_corner_trap.triggered.connect(lambda: TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, get_modifier()))

		self.btn_corner_rebuild = QtGui.QAction("corner_rebuild", self.grp_corner)
		self.btn_corner_rebuild.setToolTip("Rebuild Corner")
		self.btn_corner_rebuild.setFont(TRToolFont)
		self.addAction(self.btn_corner_rebuild)
		self.btn_corner_rebuild.triggered.connect(lambda: TRNodeActionCollector.corner_rebuild(pMode, pLayers))


# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

