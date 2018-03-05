#FLM: TAB Mixer Tools 0.01
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
		
		self.cmb_0 = QtGui.QComboBox()
		self.cmb_1 = QtGui.QComboBox()
		self.edt_0 = QtGui.QLineEdit('0')
		self.edt_1 = QtGui.QLineEdit('1000')
		self.edt_step = QtGui.QLineEdit('10')

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.refreshSlider()

		self.addWidget(self.cmb_0, 			0, 0, 1, 3)
		self.addWidget(self.cmb_1, 			0, 5, 1, 3)
		self.addWidget(self.sld_axis, 		1, 0, 1, 8)
		self.addWidget(QtGui.QLabel('0:'),	2, 0, 1, 1)
		self.addWidget(self.edt_0, 			2, 1, 1, 1)
		self.addWidget(QtGui.QLabel('S:'), 	2, 2, 1, 1)
		self.addWidget(self.edt_step, 		2, 3, 1, 2)
		self.addWidget(QtGui.QLabel('1:'), 	2, 5, 1, 1)
		self.addWidget(self.edt_1, 			2, 6, 1, 1)


	def refreshSlider(self):
		self.sld_axis.setMinimum(int(self.edt_0.text))
		self.sld_axis.setMaximum(int(self.edt_1.text))
		self.sld_axis.setSingleStep(int(self.edt_step.text))
		self.sld_axis.setTickInterval(int(self.edt_step.text)*2)
		

	def eqContour(self, method):
		pass
		#glyph.updateObject(glyph.fl, 'Optimize %s @ %s.' %(method, '; '.join(wLayers)))
		#glyph.update()


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
				
		if sysOK:
			layoutV.addWidget(QtGui.QLabel('Single Axis Mixer'))
			layoutV.addLayout(mixer1d())
			layoutV.addStretch()
		else:
			layoutV.addLayout(message(warnMessage))

		 # - Build ---------------------------
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 280, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()