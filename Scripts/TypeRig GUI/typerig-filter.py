#FLM: Typerig Filter
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
from typerig import QtGui

# -- Internals - Load toolpanels
import Filter as Panel

# - Init --------------------------
app_version = '0.26'
app_name = 'TypeRig Filter'
ignorePanel = '__'

# - Style -------------------------
ss_Toolbox_none = """/* EMPTY STYLESHEET */ """

# - Interface -----------------------------
# -- Main Widget --------------------------
class typerig_filter(QtGui.QDialog):
	def __init__(self):
		super(typerig_filter, self).__init__()

		#self.setStyleSheet(ss_Toolbox_none)

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

		# - Glyphs --------------------------
		self.rad_glyph = QtGui.QRadioButton('Glyph')
		self.rad_window = QtGui.QRadioButton('Window')
		self.rad_selection = QtGui.QRadioButton('Selection')
		self.rad_font = QtGui.QRadioButton('Font')

		self.rad_glyph.toggled.connect(self.refreshMode)
		self.rad_window.toggled.connect(self.refreshMode)
		self.rad_selection.toggled.connect(self.refreshMode)
		self.rad_font.toggled.connect(self.refreshMode)

		self.rad_glyph.setChecked(True)

		self.rad_glyph.setEnabled(True)
		self.rad_window.setEnabled(True)
		self.rad_selection.setEnabled(True)
		self.rad_font.setEnabled(False)

		self.rad_glyph.setToolTip('Affect current glyph')
		self.rad_window.setToolTip('Affect glyphs in active window')
		self.rad_selection.setToolTip('Affect selected glyphs')
		self.rad_font.setToolTip('Affect the entire font')

		# - Fold Button ---------------------
		self.btn_fold = QtGui.QPushButton('^')
		self.btn_unfold = QtGui.QPushButton('Restore Panel')

		self.btn_fold.setFixedHeight(self.chk_ActiveLayer.sizeHint.height()*2.5)
		self.btn_fold.setFixedWidth(self.chk_ActiveLayer.sizeHint.height())
		self.btn_unfold.setFixedHeight(self.chk_ActiveLayer.sizeHint.height() + 5)

		self.btn_fold.setToolTip('Fold Panel')
		self.btn_unfold.setToolTip('Unfold Panel')

		self.btn_fold.clicked.connect(self.fold)
		self.btn_unfold.clicked.connect(self.fold)
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

		self.lay_controller = QtGui.QGridLayout()
		self.fr_controller = QtGui.QFrame()
		self.lay_controller.setContentsMargins(15,5,5,3)

		# -- Build layouts -------------------------------
		self.lay_controller.addWidget(self.chk_ActiveLayer,	0, 0, 1, 1)
		self.lay_controller.addWidget(self.chk_Masters, 	0, 1, 1, 1)
		self.lay_controller.addWidget(self.chk_Masks, 		0, 2, 1, 1)
		self.lay_controller.addWidget(self.chk_Service, 	0, 3, 1, 1)
		self.lay_controller.addWidget(self.btn_fold, 		0, 4, 2, 1)
		self.lay_controller.addWidget(self.rad_glyph, 		1, 0, 1, 1)
		self.lay_controller.addWidget(self.rad_window, 		1, 1, 1, 1)
		self.lay_controller.addWidget(self.rad_selection, 	1, 2, 1, 1)
		self.lay_controller.addWidget(self.rad_font, 		1, 3, 1, 1)

		layoutV.addWidget(self.btn_unfold)
		self.fr_controller.setLayout(self.lay_controller)

		layoutV.addWidget(self.fr_controller)
		layoutV.addWidget(self.tabs)

		self.btn_unfold.hide()

		# - Set Widget -------------------------------
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 240, 440)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		
		# !!! Hotfix FL7 7355 
		self.setMinimumSize(350,self.sizeHint.height())

		self.show()

	def refreshLayers(self):
		global pLayers
		pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), self.chk_Masks.isChecked(), self.chk_Service.isChecked())

		for toolName in Panel.modules:
			exec('Panel.%s.pLayers = %s' %(toolName, pLayers))

	def refreshMode(self):
		global pMode
		pMode = 0

		if self.rad_glyph.isChecked(): pMode = 0
		if self.rad_window.isChecked(): pMode = 1
		if self.rad_selection.isChecked(): pMode = 2
		if self.rad_font.isChecked(): pMode = 3

		for toolName in Panel.modules:
			exec('Panel.%s.pMode = %s' %(toolName, pMode))

	def fold(self):
		# - Init
		width_all = self.width
		height_folded = self.btn_unfold.sizeHint.height()
						
		# - Do
		if not self.flag_fold:
			self.tabs.hide()
			self.fr_controller.hide()
			self.btn_unfold.show()
			self.setMinimumHeight(height_folded)
			self.repaint()
			self.resize(width_all, height_folded)
			self.flag_fold = True

		else:
			self.tabs.show()
			self.fr_controller.show()
			self.btn_unfold.hide()
			self.adjustSize()
			self.resize(350, self.sizeHint.height()) # !!! Hotfix FL7 7355 
			self.repaint()
			self.flag_fold = False

# - STYLE OVERRIDE -------------------
# -- Following (uncommented) will override the default OS styling for Qt Widgets on Mac OS.
from platform import system
if system() == 'Darwin':
	QtGui.QApplication.setStyle(QtGui.QStyleFactory.create('macintosh')) # Options: Windows, WindowsXP, WindowsVista, Fusion

# - RUN ------------------------------
dialog = typerig_filter()
