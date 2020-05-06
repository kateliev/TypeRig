#FLM: TypeRig: Manager
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
#import fontlab as fl6
#import fontgate as fgt

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import getProcessGlyphs, TRHTabWidget

# -- Internals - Load toolpanels 
import Manager

# - Init --------------------------
app_version = '0.11'
app_name = 'TypeRig Managers'
ignorePanel = '__'

# - Style -------------------------
ss_Toolbox_none = """/* EMPTY STYLESHEET */ """

# - Interface -----------------------------
# -- Main Widget --------------------------
class typerig_Manager(QtGui.QDialog):
	def __init__(self):
		super(typerig_Manager, self).__init__()
	
		#self.setStyleSheet(ss_Toolbox_none)
				
		# - Tabs --------------------------
		# -- Dynamically load all tabs
		self.tabs = TRHTabWidget()

		# --- Load all tabs from this directory as modules. Check __init__.py 
		# --- <dirName>.modules tabs/modules manifest in list format
		for toolName in Manager.modules:
			if ignorePanel not in toolName:
				self.tabs.addTab(eval('Manager.%s.tool_tab()' %toolName), toolName)
		
		# - Layouts -------------------------------
		layoutV = QtGui.QVBoxLayout() 
		layoutV.setContentsMargins(0,0,0,0)
		
		self.lay_layers = QtGui.QGridLayout()
		self.lay_layers.setContentsMargins(15,5,5,3)

		# -- Build layouts -------------------------------
		layoutV.addWidget(self.tabs)

		# - Set Widget -------------------------------
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 900, 440)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		#self.setMinimumWidth(300)
		self.show()

# - RUN ------------------------------
dialog = typerig_Manager()

