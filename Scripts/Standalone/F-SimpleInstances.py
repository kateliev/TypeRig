#FLM: Font: Simple Instances Calculator (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
#import fontgate as fgt
from PythonQt import QtCore, QtGui

#from typerig.proxy import pFont, pGlyph, pShape
from typerig.brain import fontFamilly, linAxis, geoAxis, linspread, geospread

# - Init --------------------------------
app_version = '0.01'
app_name = 'Simple Instance Calc'

# -- Strings
text_prog = ['Geometric']

class dlg_sInstance(QtGui.QDialog):
	def __init__(self):
		super(dlg_sInstance, self).__init__()
	
		# - Init
		
		# - Widgets
		self.cmb_prog = QtGui.QComboBox()
		self.cmb_prog.addItems(text_prog)

		self.edt_wt0 = QtGui.QLineEdit()
		self.edt_wt1 = QtGui.QLineEdit()
		self.spb_weights = QtGui.QSpinBox()
		self.spb_widths = QtGui.QSpinBox()
		self.edt_result = QtGui.QTextEdit()
		
		self.spb_weights.setValue(2)
		self.spb_widths.setValue(1)

		self.edt_wt0.setPlaceholderText('Stem width')
		self.edt_wt1.setPlaceholderText('Stem width')
		self.edt_result.setPlaceholderText('Output instance locations')
		
		self.btn_calc = QtGui.QPushButton('Calculate instances')
		self.btn_calc.clicked.connect(self.calculateInstances)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Stem progression:'),	0, 0, 1, 4)
		layoutV.addWidget(self.cmb_prog, 			1, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Begin:'),	2, 0, 1, 1)
		layoutV.addWidget(self.edt_wt0,				2, 1, 1, 1)
		layoutV.addWidget(QtGui.QLabel('End:'),		2, 2, 1, 1)
		layoutV.addWidget(self.edt_wt1,				2, 3, 1, 1)

		layoutV.addWidget(QtGui.QLabel('Weights:'),	3, 0, 1, 1)
		layoutV.addWidget(self.spb_weights,			3, 1, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Widths:'),	3, 2, 1, 1)
		layoutV.addWidget(self.spb_widths,			3, 3, 1, 1)

		layoutV.addWidget(self.btn_calc, 			4, 0, 1, 4)
		layoutV.addWidget(self.edt_result, 			5, 0, 10, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 420)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def calculateInstances(self):
		newFamily = fontFamilly(wt0 = int(self.edt_wt0.text), wt1 = int(self.edt_wt1.text) , wt_steps = self.spb_weights.value, wd_steps = self.spb_widths.value)
		self.edt_result.setText('\n'.join(map(str, newFamily.instances)))

	

	
# - RUN ------------------------------
dialog = dlg_sInstance()