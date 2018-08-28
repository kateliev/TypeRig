#FLM: Typerig Panel
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
from PythonQt import QtCore, QtGui

# -- Internals - Load toolpanels 
import Panel 

# - Init --------------------------
app_version = '0.41'
app_name = 'TypeRig Panel'
ignorePanel = '__'

# - Style -------------------------
ss_Toolbox_none = """/* EMPTY STYLESHEET */ """

# - Interface -----------------------------
# -- Main Widget --------------------------
class typerig_Panel(QtGui.QDialog):
	def __init__(self):
		super(typerig_Panel, self).__init__()
	
		self.setStyleSheet(ss_Toolbox_none)
		
		# - Layers --------------------------
		self.chk_ActiveLayer = QtGui.QCheckBox('Active')
		self.chk_Masters = QtGui.QCheckBox('Masters')
		self.chk_Masks = QtGui.QCheckBox('Masks')
		self.chk_Service = QtGui.QCheckBox('Services')

		self.chk_ActiveLayer.setCheckState(QtCore.Qt.Checked)
		#self.chk_ActiveLayer.setStyleSheet('QCheckBox::indicator:checked {background-color: limegreen; border: 1px Solid limegreen;}')
			
		self.chk_ActiveLayer.stateChanged.connect(self.refreshLayers)
		self.chk_Masters.stateChanged.connect(self.refreshLayers)
		self.chk_Masks.stateChanged.connect(self.refreshLayers)
		self.chk_Service.stateChanged.connect(self.refreshLayers)

		self.refreshLayers()

		# - Fold Button ---------------------
		self.btn_fold = QtGui.QPushButton('^')
		self.btn_fold.setFixedHeight(self.chk_ActiveLayer.sizeHint.height())
		self.btn_fold.setFixedWidth(self.chk_ActiveLayer.sizeHint.height())
		self.btn_fold.setToolTip('Fold Panel')
		self.btn_fold.clicked.connect(self.fold)
		self.flag_fold = False
				
		# - Tabs --------------------------
		# -- Dynamically load all tabs
		self.tabs = QtGui.QTabWidget()
		self.tabs.setTabPosition(QtGui.QTabWidget.East)

		# --- Load all tabs from this directory as modules. Check __init__.py 
		# --- <dirName>.modules tabs/modules manifest in list format
		for toolName in Panel.modules:
			if ignorePanel not in toolName:
				self.tabs.addTab(eval('Panel.%s.tool_tab()' %toolName), toolName)
		
		# - Layouts -------------------------------
		layoutV = QtGui.QVBoxLayout() 
		layoutV.setContentsMargins(0,0,0,0)
		
		self.lay_layers = QtGui.QGridLayout()
		self.lay_layers.setContentsMargins(15,10,5,5)
				
		# -- Build layouts -------------------------------
		self.lay_layers.addWidget(self.chk_ActiveLayer, 0, 0)
		self.lay_layers.addWidget(self.chk_Masters, 0 , 1)
		self.lay_layers.addWidget(self.chk_Masks, 0, 2)
		self.lay_layers.addWidget(self.chk_Service, 0, 3)
		self.lay_layers.addWidget(self.btn_fold, 0, 4)
					 
		layoutV.addLayout(self.lay_layers)
		layoutV.addWidget(self.tabs)

		# - Set Widget -------------------------------
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 240, 440)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		#self.setMinimumWidth(300)
		
		self.show()

	def refreshLayers(self):
		global pLayers
		pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), self.chk_Masks.isChecked(), self.chk_Service.isChecked())
		
		for toolName in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(toolName, pLayers))

	def fold(self):
		if not self.flag_fold:
			self.tabs.hide()
			self.setFixedHeight(self.chk_ActiveLayer.sizeHint.height() + 15)
			self.repaint()
			self.flag_fold = True
		else:
			self.setFixedHeight(self.tabs.sizeHint.height() + 40) #Fix this! + 40 Added because Nodes tab breaks
			self.tabs.show()
			self.repaint()
			self.flag_fold = False
	
# - STYLE OVERRIDE -------------------
# -- Following (uncommented) will override the default OS styling for Qt Widgets on Mac OS.
from platform import system
if system() == 'Darwin':
	QtGui.QApplication.setStyle(QtGui.QStyleFactory.create('Fusion')) # Options: Windows, WindowsXP, WindowsVista, Fusion

# - RUN ------------------------------
dialog = typerig_Panel()

