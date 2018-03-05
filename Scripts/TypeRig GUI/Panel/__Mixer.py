#FLM: TAB Mixer
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Mixer', '0.01'

# - Dependencies -----------------
import imp

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.brain import coordArray

# - Check for SciPy and NumPy
try:
    imp.find_module('scipy')
    imp.find_module('numpy')
    sysOK = True

except ImportError:
    sysOK = False

if sysOK:
	from typerig.sci import lerp1d

# - Init
warnMessage = 'This Panel requires the modules <a href="https://www.scipy.org/">SciPy</a> and <a href="http://www.numpy.org/">NumPy</a>	to be installed on your system. For Windows systems please take a look at the following <a href="https://www.lfd.uci.edu/~gohlke/pythonlibs/">precompiled libraries</a>.'

# - Sub widgets ------------------------
class message(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(message, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

class mixer1d(QtGui.QGridLayout):
	# - Single axis mixer
	def __init__(self):
		super(mixer1d, self).__init__()
		
		# - Init
		self.cmb_0 = QtGui.QComboBox()
		self.cmb_1 = QtGui.QComboBox()

		self.edt_0 = QtGui.QLineEdit('0')
		self.edt_1 = QtGui.QLineEdit('1000')
		self.edt_time = QtGui.QLineEdit('0')

		self.spb_step = QtGui.QSpinBox()
		self.spb_step.setValue(10)

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.sld_axis.valueChanged.connect(self.sliderChange)
		self.refreshSlider()
		
		self.edt_0.textChanged.connect(self.refreshSlider)
		self.edt_1.textChanged.connect(self.refreshSlider)
		self.spb_step.valueChanged.connect(self.refreshSlider)
		self.edt_time.textChanged.connect(self.refreshSlider)

		# - Layout
		self.addWidget(self.cmb_0, 			0, 0, 1, 4)
		self.addWidget(QtGui.QLabel('t:'),	0, 4, 1, 1)
		self.addWidget(self.edt_time, 		0, 5, 1, 3)
		self.addWidget(self.cmb_1, 			0, 8, 1, 4)
		self.addWidget(self.sld_axis, 		1, 0, 1, 12)
		self.addWidget(QtGui.QLabel('0:'),	2, 0, 1, 1)
		self.addWidget(self.edt_0, 			2, 1, 1, 3)
		self.addWidget(QtGui.QLabel('S:'), 	2, 4, 1, 1)
		self.addWidget(self.spb_step, 		2, 5, 1, 3)
		self.addWidget(QtGui.QLabel('1:'), 	2, 8, 1, 1)
		self.addWidget(self.edt_1, 			2, 9, 1, 3)

	def refreshSlider(self):
		self.sld_axis.setValue(int(self.edt_time.text))
		self.sld_axis.setMinimum(int(self.edt_0.text))
		self.sld_axis.setMaximum(int(self.edt_1.text))
		self.sld_axis.setSingleStep(int(self.spb_step.value))
		
	def sliderChange(self):
		self.edt_time.setText(self.sld_axis.value)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.fInterp = lambda x:x

		if sysOK:
			# -- Head
			self.lay_head = QtGui.QHBoxLayout()
			self.edt_glyphName = QtGui.QLineEdit()
			self.btn_refresh = QtGui.QPushButton('&Refresh')
			self.btn_refresh.clicked.connect(self.refresh)

			self.lay_head.addWidget(QtGui.QLabel('G:'))
			self.lay_head.addWidget(self.edt_glyphName)
			self.lay_head.addWidget(self.btn_refresh)
			layoutV.addLayout(self.lay_head)

			# -- Axes
			self.mixer_01 = mixer1d()
			self.refresh()
			#self.prepareInterp()
			self.mixer_01.sld_axis.valueChanged.connect(self.interpolate)
			
			layoutV.addWidget(QtGui.QLabel('Single Axis Mixer'))
			layoutV.addLayout(self.mixer_01)

			layoutV.addStretch()

		else:
			# -- Throw an error if NumPy and SciPy are not installed
			layoutV.addLayout(message(warnMessage))

		 # - Build ---------------------------
		self.setLayout(layoutV)

	def refresh(self):
		# - Init
		layerBanList = ['#', 'img']
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
		
		self.layers = sorted([layer.name for layer in self.glyph.layers() if all([item not in layer.name for item in layerBanList])])
		self.mixer_01.cmb_0.clear()
		self.mixer_01.cmb_1.clear()
		self.mixer_01.cmb_0.addItems(self.layers)
		self.mixer_01.cmb_1.addItems(self.layers)

		self.mixer_01.cmb_0.currentIndexChanged.connect(self.prepareInterp)
		self.mixer_01.cmb_1.currentIndexChanged.connect(self.prepareInterp)
		self.interpDict = {}

		self.mixer_01.cmb_0.setCurrentIndex(0)
		self.mixer_01.cmb_1.setCurrentIndex(1)

	def prepareInterp(self):
		self.interpDict = {int(self.mixer_01.edt_0.text):self.glyph._getCoordArray(self.mixer_01.cmb_0.currentText), int(self.mixer_01.edt_1.text):self.glyph._getCoordArray(self.mixer_01.cmb_1.currentText)}
		self.fInterp = lerp1d(self.interpDict)

	def interpolate(self):
		self.glyph._setCoordArray(self.fInterp(self.mixer_01.sld_axis.value))
	
		#self.glyph.updateObject(self.glyph.fl, 'Interpolate', False)
		self.glyph.update()
		Update(CurrentGlyph())
	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 280, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()