# MODULE: Gui | Typerig
# VER 	: 0.01
# NOTE	: Assorted Gui Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
from PythonQt import QtCore, QtGui

# - Classes -------------------------------
# -- Messages -----------------------------
class trMsgSimple(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(trMsgSimple, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

# -- Sliders ------------------------------
class trSliderCtrl(QtGui.QGridLayout):
	def __init__(self, edt_0, edt_1, edt_pos, spb_step):
		super(trSliderCtrl, self).__init__()
		
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
		self.addWidget(self.sld_axis, 			0, 0, 1, 5)
		self.addWidget(self.edt_pos, 			0, 5, 1, 1)		
		self.addWidget(QtGui.QLabel('Min:'),	1, 0, 1, 1)
		self.addWidget(self.edt_0, 				1, 1, 1, 1)
		self.addWidget(QtGui.QLabel('Max:'), 	1, 2, 1, 1)
		self.addWidget(self.edt_1, 				1, 3, 1, 1)
		self.addWidget(QtGui.QLabel('Step:'),	1, 4, 1, 1)
		self.addWidget(self.spb_step, 			1, 5, 1, 1)


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