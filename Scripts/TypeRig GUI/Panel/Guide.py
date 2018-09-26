#FLM: Glyph: Guidelines
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Guidelines', '0.31'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph
from typerig.proxy import pFontMetrics

# - Tabs -------------------------------
class QDropGuide(QtGui.QGridLayout):
	def __init__(self):
		super(QDropGuide, self).__init__()

		# -- Editi fileds
		self.edt_guideName = QtGui.QLineEdit()
		self.edt_guideName.setPlaceholderText('New Guideline')

		# -- Combo box
		self.cmb_select_V = QtGui.QComboBox()
		self.cmb_select_H = QtGui.QComboBox()
		self.cmb_select_color = QtGui.QComboBox()
		
		self.cmb_select_V.addItems(['BBox width', 'Adv. width'])
		self.cmb_select_H.addItems(['BBox height', 'X-Height', 'Caps Height', 'Ascender', 'Descender', 'Adv. height'])

		colorNames = QtGui.QColor.colorNames()
		for i in range(len(colorNames)):
			self.cmb_select_color.addItem(colorNames[i])
			self.cmb_select_color.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

		self.cmb_select_color.setCurrentIndex(colorNames.index('red'))

		# -- SpinBox
		self.spb_prc_V =  QtGui.QSpinBox()
		self.spb_prc_V.setMaximum(100)
		self.spb_prc_V.setSuffix('%')
		self.spb_prc_V.setMinimumWidth(45)

		self.spb_prc_H =  QtGui.QSpinBox()
		self.spb_prc_H.setMaximum(100)
		self.spb_prc_H.setSuffix('%')
		self.spb_prc_H.setMinimumWidth(45)

		self.spb_unit_V =  QtGui.QSpinBox()
		self.spb_unit_V.setMaximum(100)
		self.spb_unit_V.setMinimum(-100)
		self.spb_unit_V.setSuffix(' U')
		self.spb_unit_V.setMinimumWidth(45)

		self.spb_unit_H =  QtGui.QSpinBox()
		self.spb_unit_H.setMaximum(100)
		self.spb_unit_H.setMinimum(-100)
		self.spb_unit_H.setSuffix(' U')
		self.spb_unit_H.setMinimumWidth(45)

		# -- Button
		self.btn_dropGuide = QtGui.QPushButton('&Drop')
		self.btn_dropFlipX = QtGui.QPushButton('Drop: Flip &X')
		self.btn_dropFlipY = QtGui.QPushButton('Drop: Flip &Y')
		self.btn_dropLayer_V = QtGui.QPushButton('Vertical')
		self.btn_dropLayer_H = QtGui.QPushButton('Horizontal')

		self.btn_dropGuide.setToolTip('Drop guideline between any two selected nodes.\nIf single node is selected a vertical guide is\ndropped (using the italic angle if present).')
		self.btn_dropFlipX.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_dropFlipY.setToolTip('Drop flipped guideline between any two selected nodes.')
		
		self.btn_dropGuide.clicked.connect(lambda: self.drop_guide_nodes((1,1)))
		self.btn_dropFlipX.clicked.connect(lambda: self.drop_guide_nodes((-1,1)))
		self.btn_dropFlipY.clicked.connect(lambda: self.drop_guide_nodes((1,-1)))
		self.btn_dropLayer_V.clicked.connect(self.drop_guide_V)
		self.btn_dropLayer_H.clicked.connect(self.drop_guide_H)
		
		# - Build
		self.addWidget(QtGui.QLabel('Name:'), 					1, 0, 1, 6)
		self.addWidget(QtGui.QLabel('Color:'), 					1, 6, 1, 6)
		self.addWidget(self.edt_guideName, 						2, 0, 1, 6)
		self.addWidget(self.cmb_select_color  , 				2, 6, 1, 6)
		self.addWidget(QtGui.QLabel('Selected Nodes:'), 		3, 0, 1, 9)
		self.addWidget(self.btn_dropGuide, 						4, 0, 1, 4)
		self.addWidget(self.btn_dropFlipX, 						4, 4, 1, 4)
		self.addWidget(self.btn_dropFlipY, 						4, 8, 1, 4)
		self.addWidget(QtGui.QLabel('Glyph Layer:'), 			5, 0, 1, 9)
		self.addWidget(self.cmb_select_V, 						6, 0, 1, 4)
		self.addWidget(self.spb_prc_V, 							6, 4, 1, 2)
		self.addWidget(self.spb_unit_V, 						6, 6, 1, 2)
		self.addWidget(self.btn_dropLayer_V, 					6, 8, 1, 4)
		self.addWidget(self.cmb_select_H, 						7, 0, 1, 4)
		self.addWidget(self.spb_prc_H, 							7, 4, 1, 2)
		self.addWidget(self.spb_unit_H, 						7, 6, 1, 2)
		self.addWidget(self.btn_dropLayer_H, 					7, 8, 1, 4)

	# - Procedures
	def drop_guide_nodes(self, flip):
		glyph = eGlyph()
		glyph.dropGuide(layers=pLayers, name=self.edt_guideName.text, color=self.cmb_select_color.currentText, flip=flip)
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

	def drop_guide_V(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = 0 #glyph.package.italicAngle_value

		for layerName in wLayers:
			if 'BBox' in self.cmb_select_V.currentText:
				width = glyph.layer(layerName).boundingBox.width()
				origin = glyph.layer(layerName).boundingBox.x()
			
			elif 'Advance' in self.cmb_select_V.currentText:
				width = glyph.getAdvance(layerName)
				origin = 0.

			#print width, origin , width + origin, float(width)*self.spb_prc_V.value/100 + origin

			guidePos = (float(width)*self.spb_prc_V.value/100 + origin + self.spb_unit_V.value, 0)
			glyph.addGuideline(guidePos, layer=layerName, angle=italicAngle, name=self.edt_guideName.text, color=self.cmb_select_color.currentText)
			
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

	def drop_guide_H(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = 0 #glyph.package.italicAngle_value
		
		for layerName in wLayers:
			metrics = pFontMetrics(glyph.package)

			if 'BBox' in self.cmb_select_H.currentText:
				height = glyph.layer(layerName).boundingBox.height()
				origin = glyph.layer(layerName).boundingBox.y()
			
			elif 'Adv' in self.cmb_select_H.currentText:
				height = glyph.layer(layerName).advanceHeight
				origin = 0.

			elif 'X-H' in self.cmb_select_H.currentText:
				height = metrics.getXHeight(layerName)
				origin = 0.

			elif 'Caps' in self.cmb_select_H.currentText:
				height = metrics.getCapsHeight(layerName)
				origin = 0.

			elif 'Ascender' in self.cmb_select_H.currentText:
				height = metrics.getAscender(layerName)
				origin = 0.			

			elif 'Descender' in self.cmb_select_H.currentText:
				height = metrics.getDescender(layerName)
				origin = 0.		

			guidePos = (0, float(height)*self.spb_prc_H.value/100 + origin + self.spb_unit_H.value)
			glyph.addGuideline(guidePos, layer=layerName, angle=90, name=self.edt_guideName.text, color=self.cmb_select_color.currentText)
			
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