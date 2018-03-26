#FLM: TAB Guidelines
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Guidelines', '0.25'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Tabs -------------------------------
class QDropGuide(QtGui.QGridLayout):
	def __init__(self):
		super(QDropGuide, self).__init__()

		# -- Guide Name
		self.edt_guideName = QtGui.QLineEdit()
		self.edt_guideName.setText('DropGuideline')

		# -- Guide Color Selector
		self.cmb_cSelect = QtGui.QComboBox()
		colorNames = QtGui.QColor.colorNames()
		
		for i in range(len(colorNames)):
			self.cmb_cSelect.addItem(colorNames[i])
			self.cmb_cSelect.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

		self.cmb_cSelect.setCurrentIndex(colorNames.index('red'))

		# -- Guide button
		self.btn_dropGuide = QtGui.QPushButton('&Drop')
		self.btn_dropFlipX = QtGui.QPushButton('Drop flip &X')
		self.btn_dropFlipY = QtGui.QPushButton('Drop flip &Y')
		self.btn_dropGuide.setToolTip('Drop guideline between any two selected nodes.\nIf single node is selected a vertical guide is\ndropped (using the italic angle if present).')
		self.btn_dropFlipX.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_dropFlipY.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_dropGuide.clicked.connect(lambda: self.dropGuideline((1,1)))
		self.btn_dropFlipX.clicked.connect(lambda: self.dropGuideline((-1,1)))
		self.btn_dropFlipY.clicked.connect(lambda: self.dropGuideline((1,-1)))
		
		# - Build
		self.addWidget(QtGui.QLabel('N:'), 0, 0, 1, 1)
		self.addWidget(self.edt_guideName, 0, 1, 1, 4)
		self.addWidget(QtGui.QLabel('C:'), 0, 5, 1, 1)
		self.addWidget(self.cmb_cSelect  , 0, 6, 1, 4)
		self.addWidget(self.btn_dropGuide, 1, 1, 1, 3)
		self.addWidget(self.btn_dropFlipX, 1, 4, 1, 3)
		self.addWidget(self.btn_dropFlipY, 1, 7, 1, 3)
		
	# - Procedures
	def dropGuideline(self, flip):
			glyph = eGlyph()
			glyph.dropGuide(layers=pLayers, name=self.edt_guideName.text, color=self.cmb_cSelect.currentText, flip=flip)
			glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
			glyph.update()
			
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.dropGuide = QDropGuide()

		# - Build ---------------------------
		layoutV.addLayout(self.dropGuide)

		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()