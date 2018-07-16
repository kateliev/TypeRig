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
app_name, app_version = 'TypeRig | Guidelines', '0.30'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Tabs -------------------------------
class QDropGuide(QtGui.QGridLayout):
	def __init__(self):
		super(QDropGuide, self).__init__()

		# -- Editi fileds
		self.edt_guideName = QtGui.QLineEdit()
		self.edt_guideName.setPlaceholderText('New Guideline')

		# -- Combo box
		self.cmb_wSelect = QtGui.QComboBox()
		self.cmb_cSelect = QtGui.QComboBox()
		
		self.cmb_wSelect.addItems(['Advance width', 'BBox width'])
		colorNames = QtGui.QColor.colorNames()
		for i in range(len(colorNames)):
			self.cmb_cSelect.addItem(colorNames[i])
			self.cmb_cSelect.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

		self.cmb_cSelect.setCurrentIndex(colorNames.index('red'))

		# -- SpinBox
		self.spb_width_percent =  QtGui.QSpinBox()
		self.spb_width_percent.setMaximum(100)
		self.spb_width_percent.setSuffix('%')

		# -- Button
		self.btn_dropGuide = QtGui.QPushButton('Drop')
		self.btn_dropFlipX = QtGui.QPushButton('Drop: Flip &X')
		self.btn_dropFlipY = QtGui.QPushButton('Drop: Flip &Y')
		self.btn_dropLayer = QtGui.QPushButton('Drop')

		self.btn_dropGuide.setToolTip('Drop guideline between any two selected nodes.\nIf single node is selected a vertical guide is\ndropped (using the italic angle if present).')
		self.btn_dropFlipX.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_dropFlipY.setToolTip('Drop flipped guideline between any two selected nodes.')
		
		self.btn_dropGuide.clicked.connect(lambda: self.dropGuideSelected((1,1)))
		self.btn_dropFlipX.clicked.connect(lambda: self.dropGuideSelected((-1,1)))
		self.btn_dropFlipY.clicked.connect(lambda: self.dropGuideSelected((1,-1)))
		self.btn_dropLayer.clicked.connect(self.dropGuideWidth)
		
		# - Build
		self.addWidget(QtGui.QLabel('N:'), 						0, 0, 1, 1)
		self.addWidget(self.edt_guideName, 						0, 1, 1, 4)
		self.addWidget(QtGui.QLabel('C:'), 						0, 5, 1, 1)
		self.addWidget(self.cmb_cSelect  , 						0, 6, 1, 4)
		self.addWidget(QtGui.QLabel('Selected Nodes:'), 		1, 0, 1, 9)
		self.addWidget(self.btn_dropGuide, 						2, 1, 1, 3)
		self.addWidget(self.btn_dropFlipX, 						2, 4, 1, 3)
		self.addWidget(self.btn_dropFlipY, 						2, 7, 1, 3)
		self.addWidget(QtGui.QLabel('Glyph Layer:'), 			4, 0, 1, 9)
		self.addWidget(self.cmb_wSelect, 						5, 1, 1, 3)
		self.addWidget(self.spb_width_percent, 					5, 4, 1, 3)
		self.addWidget(self.btn_dropLayer, 						5, 7, 1, 3)

	# - Procedures
	def dropGuideSelected(self, flip):
		glyph = eGlyph()
		glyph.dropGuide(layers=pLayers, name=self.edt_guideName.text, color=self.cmb_cSelect.currentText, flip=flip)
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

	def dropGuideWidth(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = 0 #glyph.package.italicAngle_value

		for layerName in wLayers:
			if 'BBox' in self.cmb_wSelect.currentText:
				width = glyph.layer(layerName).boundingBox.width()
				origin = glyph.layer(layerName).boundingBox.x()
			
			elif 'Advance' in self.cmb_wSelect.currentText:
				width = glyph.getAdvance(layerName)
				origin = 0.

			#print width, origin , width + origin, float(width)*self.spb_width_percent.value/100 + origin

			guidePos = (float(width)*self.spb_width_percent.value/100 + origin, 0)
			glyph.addGuideline(guidePos, layer=layerName, angle=italicAngle, name=self.edt_guideName.text, color=self.cmb_cSelect.currentText)
			
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