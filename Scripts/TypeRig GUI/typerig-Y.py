#FLM: Typerig Y-Panel
# A experimental reimplementation as FL6 YPanelWidget
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

# -- Internals - Load toolpanels 
import Panel 

# - Init --------------------------
app_version = '0.38'
app_name = 'TypeRig Panel'
ignorePanel = '__'

# -- Main Widget --------------------------
class typerig_Panel(QtGui.QVBoxLayout):
	def __init__(self):
		super(typerig_Panel, self).__init__()
	
		# - Layers --------------------------
		self.chk_ActiveLayer = QtGui.QCheckBox('Active')
		self.chk_Masters = QtGui.QCheckBox('Masters')
		self.chk_Masks = QtGui.QCheckBox('Masks')
		self.chk_Service = QtGui.QCheckBox('Services')

		self.chk_ActiveLayer.setCheckState(QtCore.Qt.Checked)
		
		self.chk_ActiveLayer.stateChanged.connect(self.refreshLayers)
		self.chk_Masters.stateChanged.connect(self.refreshLayers)
		self.chk_Masks.stateChanged.connect(self.refreshLayers)
		self.chk_Service.stateChanged.connect(self.refreshLayers)

		self.refreshLayers()

		# - Tabs --------------------------
		# -- Dynamically load all tabs
		self.tabs = QtGui.QTabWidget()
		#self.tabs.setTabPosition(QtGui.QTabWidget.East)

		# --- Load all tabs from this directory as modules. Check __init__.py 
		# --- <dirName>.modules tabs/modules manifest in list format
		for toolName in Panel.modules:
			if ignorePanel not in toolName:
				self.tabs.addTab(eval('Panel.%s.tool_tab()' %toolName), toolName)
		
		# - Layouts -------------------------------
		#self.setContentsMargins(0,0,0,0)
		
		self.lay_layers = QtGui.QGridLayout()
		self.lay_layers.setContentsMargins(15,10,5,5)
				
		# -- Build layouts -------------------------------
		self.lay_layers.addWidget(self.chk_ActiveLayer, 0, 0)
		self.lay_layers.addWidget(self.chk_Masters, 0 , 1)
		self.lay_layers.addWidget(self.chk_Masks, 0, 2)
		self.lay_layers.addWidget(self.chk_Service, 0, 3)
							 
		self.addLayout(self.lay_layers)
		self.addWidget(self.tabs)

	def refreshLayers(self):
		global pLayers
		pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), self.chk_Masks.isChecked(), self.chk_Service.isChecked())
		
		for toolName in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(toolName, pLayers))


# - Set Widget -------------------------------
TRpanel = fl6.YPanelWidget(0)
TRLayout = typerig_Panel()
TRpanel.title = '%s %s' %(app_name, app_version)
TRpanel.minimumPanelSize = QtCore.QSize(240, 440)
TRpanel.qwidget.setLayout(TRLayout)
	
# - RUN ------------------------------
fl6.YPanelManager().activatePanel(TRpanel)


