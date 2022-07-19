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
from typerig.proxy.fl.gui.dialogs import TR1SliderDLG
from typerig.proxy.fl.gui.widgets import getTRIconFont, getProcessGlyphs


# - Init --------------------------
tool_version = '1.51'
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

		# -- Insert and remove nodes
		self.btn_node_add = QtGui.QAction("node_add", self.grp_nodes)
		#self.dlg_node_add = TR1SliderDLG('Insert Node', 'Set time along bezier curve')
		#self.dlg_node_add.hide()
		self.btn_node_add.setToolTip("Insert Node")
		self.btn_node_add.setFont(TRToolFont)
		self.addAction(self.btn_node_add)

		self.btn_node_add_0 = QtGui.QAction("node_add_bgn", self.grp_nodes)
		self.btn_node_add_0.setToolTip("Insert Node at the beginning of bezier")
		self.btn_node_add_0.setFont(TRToolFont)
		self.addAction(self.btn_node_add_0)
		self.btn_node_add_0.triggered.connect(lambda: TRNodeActionCollector.node_insert(eGlyph(), pLayers, 0., get_modifier()))

		self.btn_node_add_5 = QtGui.QAction("node_add_mid", self.grp_nodes)
		self.btn_node_add_5.setToolTip("Insert Node at the middle of bezier")
		self.btn_node_add_5.setFont(TRToolFont)
		self.addAction(self.btn_node_add_5)
		self.btn_node_add_5.triggered.connect(lambda: TRNodeActionCollector.node_insert(eGlyph(), pLayers, .5, get_modifier()))

		self.btn_node_add_1 = QtGui.QAction("node_add_end", self.grp_nodes)
		self.btn_node_add_1.setToolTip("Insert Node at the end of bezier")
		self.btn_node_add_1.setFont(TRToolFont)
		self.addAction(self.btn_node_add_1)
		self.btn_node_add_1.triggered.connect(lambda: TRNodeActionCollector.node_insert(eGlyph(), pLayers, 1., get_modifier()))

	# - Procedures -----------------------------------
	
	
# - RUN ------------------------------
if __name__ == '__main__':
	toolbar_control = TRExternalToolBar(app.main)
	app.main.addToolBar(toolbar_control)

