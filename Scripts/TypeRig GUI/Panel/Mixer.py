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
app_name, app_version = 'TypeRig | Mixer', '0.09'

useFortran = True
warnMessage = 'This Panel requires some precompiled FontRig | TypeRig modules.'

# - Dependencies -----------------
from math import radians

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy import pFont
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.brain import coordArray, linInterp

# -- Check for MathRig instalaltion
try:
    if useFortran:
    	import fontrig.transform as transform			# Fortran 95 code
    else:
    	import fontrig.numpy.transform as transform 	# Numpy reimplementation of original Fortran 95 code.
    sysReady = True

except ImportError:
    sysReady = False


# - Sub widgets ------------------------
class message(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(message, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

class mixerHead(QtGui.QGridLayout):
	def __init__(self):
		super(mixerHead, self).__init__()

		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_stemV0 = QtGui.QLineEdit('1')
		self.edt_stemV1 = QtGui.QLineEdit('1')
		self.edt_stemH0 = QtGui.QLineEdit('1')
		self.edt_stemH1 = QtGui.QLineEdit('1')
		
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_setaxis = QtGui.QPushButton('Set &Axis')
		self.btn_getVstem = QtGui.QPushButton('Get &V Stems')
		self.btn_getHstem = QtGui.QPushButton('Get &H Stems')

		self.spb_compV = QtGui.QDoubleSpinBox()
		self.spb_compH = QtGui.QDoubleSpinBox()
		self.spb_compV.setValue(0.)
		self.spb_compH.setValue(0.)
		self.spb_compV.setSingleStep(.01)
		self.spb_compH.setSingleStep(.01)

		self.cmb_0 = QtGui.QComboBox()
		self.cmb_1 = QtGui.QComboBox()

		self.addWidget(QtGui.QLabel('Glyph:'),		0, 0, 1, 1)
		self.addWidget(self.edt_glyphName,			0, 1, 1, 6)
		self.addWidget(self.btn_refresh,			0, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Axis:'),		1, 0, 1, 1)
		self.addWidget(self.cmb_0, 					1, 1, 1, 3)
		self.addWidget(self.cmb_1, 					1, 4, 1, 3)
		self.addWidget(self.btn_setaxis, 			1, 7, 1, 1)
		self.addWidget(QtGui.QLabel('V Stems:'),	2, 0, 1, 1)
		self.addWidget(self.edt_stemV0,				2, 1, 1, 3)
		self.addWidget(self.edt_stemV1,				2, 4, 1, 3)
		self.addWidget(self.btn_getVstem, 			2, 7, 1, 1)
		self.addWidget(QtGui.QLabel('H Stems:'),	3, 0, 1, 1)
		self.addWidget(self.edt_stemH0,				3, 1, 1, 3)
		self.addWidget(self.edt_stemH1,				3, 4, 1, 3)
		self.addWidget(self.btn_getHstem, 			3, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Adj.V/H:'),	4, 0, 1, 1)
		self.addWidget(self.spb_compV,				4, 1, 1, 3)
		self.addWidget(self.spb_compH,				4, 4, 1, 3)

class sliderCtrl(QtGui.QGridLayout):
	def __init__(self, edt_0, edt_1, edt_pos, spb_step):
		super(sliderCtrl, self).__init__()
		
		# - Init
		self.initValues = (edt_0, edt_1, edt_pos, spb_step)

		self.edt_0 = QtGui.QLineEdit(edt_0)
		self.edt_1 = QtGui.QLineEdit(edt_1)
		self.edt_pos = QtGui.QLineEdit(edt_pos)

		self.spb_step = QtGui.QSpinBox()
		self.spb_step.setValue(spb_step)

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.sld_axis.valueChanged.connect(self.sliderChange)
		self.refreshSlider()
		
		self.edt_0.editingFinished.connect(self.refreshSlider)
		self.edt_1.editingFinished.connect(self.refreshSlider)
		self.spb_step.valueChanged.connect(self.refreshSlider)
		self.edt_pos.editingFinished.connect(self.refreshSlider)

		# - Layout		
		self.addWidget(self.sld_axis, 		0, 0, 1, 5)
		self.addWidget(self.edt_pos, 		0, 5, 1, 1)		
		self.addWidget(QtGui.QLabel('Min:'),	1, 0, 1, 1)
		self.addWidget(self.edt_0, 			1, 1, 1, 1)
		self.addWidget(QtGui.QLabel('Max:'), 1, 2, 1, 1)
		self.addWidget(self.edt_1, 			1, 3, 1, 1)
		self.addWidget(QtGui.QLabel('Step:'),1, 4, 1, 1)
		self.addWidget(self.spb_step, 		1, 5, 1, 1)


	def refreshSlider(self):
		self.sld_axis.setMinimum(float(self.edt_0.text.strip()))
		self.sld_axis.setMaximum(float(self.edt_1.text.strip()))
		self.sld_axis.setValue(float(self.edt_pos.text.strip()))
		self.sld_axis.setSingleStep(int(self.spb_step.value))
				
	def reset(self):
		self.edt_0.setText(self.initValues[0])
		self.edt_1.setText(self.initValues[1])
		self.edt_pos.setText(self.initValues[2])
		self.spb_step.setValue(self.initValues[3])
		self.refreshSlider()

	def sliderChange(self):
		self.edt_pos.setText(self.sld_axis.value)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
		# - Build panel
		if sysReady:			
			self.head = mixerHead()
			self.head.btn_refresh.clicked.connect(self.refresh)
			self.head.btn_setaxis.clicked.connect(self.setAxis)
			self.head.btn_getVstem.clicked.connect(self.getVStems)
			self.head.btn_getHstem.clicked.connect(self.getHStems)
			layoutV.addLayout(self.head)
			layoutV.addSpacing(15)

			# -- Set Sliders
			# --- Mixer
			layoutV.addWidget(QtGui.QLabel('Single Axis Mixer'))
			self.mixer = sliderCtrl('1', '1000', '0', 10)
			self.mixer.sld_axis.valueChanged.connect(self.intelliScale)		
			layoutV.addLayout(self.mixer)
			layoutV.addSpacing(25)

			# --- Scaler
			layoutV.addWidget(QtGui.QLabel('Compensative scaler: Width'))
			self.scalerX = sliderCtrl('1', '200', '100', 10)
			self.scalerX.sld_axis.valueChanged.connect(self.intelliScale)		
			layoutV.addLayout(self.scalerX)
			layoutV.addSpacing(15)

			layoutV.addWidget(QtGui.QLabel('Compensative scaler: Height'))
			self.scalerY = sliderCtrl('1', '200', '100', 10)
			self.scalerY.sld_axis.valueChanged.connect(self.intelliScale)		
			layoutV.addLayout(self.scalerY)
		
			# -- Initialize
			self.refresh()

			# -- Finish
			layoutV.addStretch()

		else:
			# - Throw an error
			layoutV.addLayout(message(warnMessage))

		# - Set panel
		self.setLayout(layoutV)

	def refresh(self):
		# - Init
		layerBanList = ['#', 'img']
		self.glyph = eGlyph()
		self.head.edt_glyphName.setText(eGlyph().name)
		self.italic_angle = pFont().getItalicAngle()
		
		self.layers = sorted([layer.name for layer in self.glyph.layers() if all([item not in layer.name for item in layerBanList])])
		
		self.head.cmb_0.clear()
		self.head.cmb_1.clear()
		self.head.cmb_0.addItems(self.layers)
		self.head.cmb_1.addItems(self.layers)
		self.head.cmb_0.setCurrentIndex(0)
		self.head.cmb_1.setCurrentIndex(0)
		self.axis = []

		self.head.edt_stemV0.setText('1')
		self.head.edt_stemV1.setText('1')
		self.head.edt_stemH0.setText('1')
		self.head.edt_stemH1.setText('1')

		self.mixer.reset()
		self.scalerX.reset()
		self.scalerY.reset()

	def getVStems(self):
		stemNodes0 = self.glyph.selectedNodes(self.head.cmb_0.currentText, True)
		stemNodes1 = self.glyph.selectedNodes(self.head.cmb_1.currentText, True)
		wt_0 = abs(stemNodes0[0].x - stemNodes0[-1].x)
		wt_1 = abs(stemNodes1[0].x - stemNodes1[-1].x)
		self.head.edt_stemV0.setText(wt_0)
		self.head.edt_stemV1.setText(wt_1)
		self.mixer.edt_0.setText(min(wt_0, wt_1))
		self.mixer.edt_1.setText(max(wt_0, wt_1))
		self.mixer.edt_pos.setText(wt_0)
		self.mixer.refreshSlider()

	def getHStems(self):
		stemNodes0 = self.glyph.selectedNodes(self.head.cmb_0.currentText, True)
		stemNodes1 = self.glyph.selectedNodes(self.head.cmb_1.currentText, True)
		wt_0 = abs(stemNodes0[0].y - stemNodes0[-1].y)
		wt_1 = abs(stemNodes1[0].y - stemNodes1[-1].y)
		self.head.edt_stemH0.setText(wt_0)
		self.head.edt_stemH1.setText(wt_1)		

	def setAxis(self):
		self.axis = [self.glyph._getCoordArray(self.head.cmb_0.currentText), self.glyph._getCoordArray(self.head.cmb_1.currentText)]
		self.glyph.updateObject(self.glyph.fl, 'Mixer Snapshot @ %s' %self.glyph.layer().name)
	
	def intelliScale(self):
		if len(self.axis):
			# - Axis
			a = self.axis[0]
			b = self.axis[1]
			
			# - Compensation
			scmp = float(self.head.spb_compH.value), float(self.head.spb_compV.value)
			
			# - Italic Angle
			angle = radians(-float(self.italic_angle))
			
			# - Stems
			sw_V = (float(self.head.edt_stemV0.text), float(self.head.edt_stemV1.text))
			sw_H = (float(self.head.edt_stemH0.text), float(self.head.edt_stemH1.text))

			curr_sw_V = float(self.mixer.sld_axis.value)
			sw_V0, sw_V1 = min(*sw_V), max(*sw_V)
			
			# - Interpolation
			tx = ((curr_sw_V - sw_V0)/(sw_V1 - sw_V0))*(1,-1)[sw_V[0] > sw_V[1]] + (0,1)[sw_V[0] > sw_V[1]]

			# - Scaling
			sx = 100./float(self.scalerX.edt_1.text) + float(self.scalerX.sld_axis.value)/float(self.scalerX.edt_1.text)
			sy = 100./float(self.scalerY.edt_1.text) + float(self.scalerY.sld_axis.value)/float(self.scalerY.edt_1.text)
			dx, dy = 0.0, 0.0
						
			# - Build
			if useFortran: # Original Fortran 95 implementation
				mms = lambda sx, sy, t : transform.adaptive_scale([a.x, a.y], [b.x, b.y], [sw_V[0], sw_H[0]], [sw_V[1], sw_H[1]], [sx, sy], [dx, dy], [t, t], scmp, angle)

			else: # NumPy implementation
				 mms = lambda sx, sy, t : transform.adaptive_scale([a.x, a.y], [b.x, b.y], sx, sy, dx, dy, t, t, scmp, scmp, angle, sw_V0, sw_V1)
			
			self.glyph._setCoordArray(mms(sx,sy, tx))
			
			self.glyph.update()
			fl6.Update(fl6.CurrentGlyph())

	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 280, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()