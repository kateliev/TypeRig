#FLM: TR: Guidelines
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Guidelines', '0.42'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl import *

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import getProcessGlyphs

# - Sub widgets ------------------------
class TRGLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		
		super(TRGLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction('lower_case', lambda: self.setText('lower_case'))
		menu.addAction('upper_case', lambda: self.setText('upper_case'))
		menu.addAction('small_caps', lambda: self.setText('small_caps'))
		menu.addAction('figure', lambda: self.setText('figure'))
		menu.addAction('symbol', lambda: self.setText('symbol'))
		menu.addAction('LC', lambda: self.setText('LC'))
		menu.addAction('UC', lambda: self.setText('UC'))
		menu.addAction('SC', lambda: self.setText('SC'))
		menu.addAction('FIG', lambda: self.setText('FIG'))
		menu.addAction('SYM', lambda: self.setText('SYM'))
		menu.addAction('LAT', lambda: self.setText('LAT'))
		menu.addAction('CYR', lambda: self.setText('CYR'))
		
# - Tabs -------------------------------
class TRDropGuide(QtGui.QGridLayout):
	def __init__(self):
		super(TRDropGuide, self).__init__()

		# -- Editing fields
		self.edt_guideName = QtGui.QLineEdit()
		self.edt_guideName.setPlaceholderText('New Guideline')

		self.edt_guideTag = TRGLineEdit()
		self.edt_guideTag.setPlaceholderText('Tag')

		self.edt_sourceName = QtGui.QLineEdit()
		self.edt_sourceName.setPlaceholderText('Source name / Current')
		self.edt_sourceName.setToolTip('Source glyph name, or Active Glyph if Blank')

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

		self.cmb_select_color.setMinimumWidth(40)
		self.edt_guideName.setMinimumWidth(40)
		self.edt_guideTag.setMinimumWidth(40)

		# -- SpinBox
		self.spb_prc_V =  QtGui.QSpinBox()
		self.spb_prc_V.setMaximum(300)
		self.spb_prc_V.setSuffix('%')
		self.spb_prc_V.setMinimumWidth(45)

		self.spb_prc_H =  QtGui.QSpinBox()
		self.spb_prc_H.setMaximum(300)
		self.spb_prc_H.setSuffix('%')
		self.spb_prc_H.setMinimumWidth(45)

		self.spb_unit_V =  QtGui.QSpinBox()
		self.spb_unit_V.setMaximum(300)
		self.spb_unit_V.setMinimum(-300)
		self.spb_unit_V.setSuffix(' U')
		self.spb_unit_V.setMinimumWidth(45)

		self.spb_unit_H =  QtGui.QSpinBox()
		self.spb_unit_H.setMaximum(300)
		self.spb_unit_H.setMinimum(-300)
		self.spb_unit_H.setSuffix(' U')
		self.spb_unit_H.setMinimumWidth(45)

		# -- Button
		self.btn_dropGuide = QtGui.QPushButton('&Drop')
		self.btn_dropFlipX = QtGui.QPushButton('Drop: Flip &X')
		self.btn_dropFlipY = QtGui.QPushButton('Drop: Flip &Y')
		self.btn_dropLayer_V = QtGui.QPushButton('Vertical')
		self.btn_dropLayer_H = QtGui.QPushButton('Horizontal')
		self.btn_getName = QtGui.QPushButton('Get &Name')

		self.btn_dropGuide.setToolTip('Drop guideline between any two selected nodes.\nIf single node is selected a vertical guide is\ndropped (using the italic angle if present).')
		self.btn_dropFlipX.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_dropFlipY.setToolTip('Drop flipped guideline between any two selected nodes.')
		self.btn_getName.setToolTip('Get the name of the current active glyph')
		
		self.btn_dropGuide.clicked.connect(lambda: self.drop_guide_nodes((1,1)))
		self.btn_dropFlipX.clicked.connect(lambda: self.drop_guide_nodes((-1,1)))
		self.btn_dropFlipY.clicked.connect(lambda: self.drop_guide_nodes((1,-1)))
		self.btn_getName.clicked.connect(lambda: self.edt_sourceName.setText(pGlyph().name))
		self.btn_dropLayer_V.clicked.connect(self.drop_guide_V)
		self.btn_dropLayer_H.clicked.connect(self.drop_guide_H)
		
		# - Build
		self.addWidget(QtGui.QLabel('Name:'), 					1, 0, 1, 4)
		self.addWidget(QtGui.QLabel('Tag:'), 					1, 4, 1, 4)
		self.addWidget(QtGui.QLabel('Color:'), 					1, 8, 1, 4)
		self.addWidget(self.edt_guideName, 						2, 0, 1, 4)
		self.addWidget(self.cmb_select_color, 					2, 8, 1, 4)
		self.addWidget(self.edt_guideTag, 						2, 4, 1, 4)
		self.addWidget(QtGui.QLabel('Selected Nodes:'), 		3, 0, 1, 9)
		self.addWidget(self.btn_dropGuide, 						4, 0, 1, 4)
		self.addWidget(self.btn_dropFlipX, 						4, 4, 1, 4)
		self.addWidget(self.btn_dropFlipY, 						4, 8, 1, 4)
		self.addWidget(QtGui.QLabel('Glyph Layer:'), 			5, 0, 1, 4)
		self.addWidget(self.edt_sourceName, 					6, 0, 1, 8)
		self.addWidget(self.btn_getName, 						6, 8, 1, 4)
		self.addWidget(self.cmb_select_V, 						7, 0, 1, 4)
		self.addWidget(self.spb_prc_V, 							7, 4, 1, 2)
		self.addWidget(self.spb_unit_V, 						7, 6, 1, 2)
		self.addWidget(self.btn_dropLayer_V, 					7, 8, 1, 4)
		self.addWidget(self.cmb_select_H, 						8, 0, 1, 4)
		self.addWidget(self.spb_prc_H, 							8, 4, 1, 2)
		self.addWidget(self.spb_unit_H, 						8, 6, 1, 2)
		self.addWidget(self.btn_dropLayer_H, 					8, 8, 1, 4)

	# - Procedures
	def drop_guide_nodes(self, flip):
		glyph = eGlyph()
		glyph.dropGuide(layers=pLayers, name=self.edt_guideName.text, tag=self.edt_guideTag.text, color=self.cmb_select_color.currentText, flip=flip)
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

	def drop_guide_V(self):
		font = pFont()
		glyph = eGlyph()
		src_glyph = glyph
		src_name = self.edt_sourceName.text

		if len(src_name) and font.hasGlyph(src_name):
			src_glyph = font.glyph(src_name)

		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = 0 #glyph.package.italicAngle_value
		guide_name = self.edt_guideName.text if len(self.edt_guideName.text) else '%s:%s:%s%%'%(src_name, self.cmb_select_V.currentText, self.spb_prc_V.value)

		for layerName in wLayers:
			if 'BBox' in self.cmb_select_V.currentText:
				width = src_glyph.layer(layerName).boundingBox.width()
				origin = glyph.layer(layerName).boundingBox.x()
			
			elif 'Adv' in self.cmb_select_V.currentText:
				width = src_glyph.getAdvance(layerName)
				origin = 0.

			#print width, origin , width + origin, float(width)*self.spb_prc_V.value/100 + origin

			guidePos = (float(width)*self.spb_prc_V.value/100 + origin + self.spb_unit_V.value, 0)
			glyph.addGuideline(guidePos, layer=layerName, angle=italicAngle, name=guide_name, tag=self.edt_guideTag.text, color=self.cmb_select_color.currentText)
			
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

	def drop_guide_H(self):
		font = pFont()
		glyph = eGlyph()
		src_glyph = glyph
		src_name = self.edt_sourceName.text
		
		if len(src_name) and font.hasGlyph(src_name):
			src_glyph = font.glyph(src_name)

		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = 0 #glyph.package.italicAngle_value
		guide_name = self.edt_guideName.text if len(self.edt_guideName.text) else '%s:%s:%s%%'%(src_name,self.cmb_select_H.currentText, self.spb_prc_H.value)
		
		for layerName in wLayers:
			metrics = pFontMetrics(glyph.package)

			if 'BBox' in self.cmb_select_H.currentText:
				height = src_glyph.layer(layerName).boundingBox.height()
				origin = glyph.layer(layerName).boundingBox.y()
			
			elif 'Adv' in self.cmb_select_H.currentText:
				height = src_glyph.layer(layerName).advanceHeight
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
			glyph.addGuideline(guidePos, layer=layerName, angle=90, name=guide_name, tag=self.edt_guideTag.text, color=self.cmb_select_color.currentText)
			
		glyph.updateObject(glyph.fl, 'Drop Guide <%s> @ %s.' %(self.edt_guideName.text, '; '.join(glyph._prepareLayers(pLayers))))
		glyph.update()

class TRGlyphTag(QtGui.QGridLayout):
	def __init__(self):
		super(TRGlyphTag, self).__init__()

		# - Widget & Layout 
		self.edt_tagString = TRGLineEdit()
		self.edt_tagString.setPlaceholderText('Glyph tags')
		self.edt_tagString.setToolTip('A comma separated list of tags.')

		self.edt_tagStringNode = QtGui.QLineEdit()
		self.edt_tagStringNode.setPlaceholderText('Node name')
		self.edt_tagStringNode.setToolTip('A single node name.')

		self.btn_tagGlyph = QtGui.QPushButton('Glyph')
		self.btn_tagWindow = QtGui.QPushButton('Window')
		self.btn_tagSelection = QtGui.QPushButton('Selection')

		self.btn_tagNodes = QtGui.QPushButton('Glyph')
		self.btn_tagWindowNodes = QtGui.QPushButton('Window')
		self.btn_tagNodesClear = QtGui.QPushButton('Clear')

		self.btn_tagGlyph.clicked.connect(lambda: self.tag_glyphs('G'))
		self.btn_tagWindow .clicked.connect(lambda: self.tag_glyphs('W'))
		self.btn_tagSelection .clicked.connect(lambda: self.tag_glyphs('S'))
		self.btn_tagNodes.clicked.connect(lambda: self.tag_nodes('G'))
		self.btn_tagWindowNodes.clicked.connect(lambda: self.tag_nodes('W'))
		self.btn_tagNodesClear.clicked.connect(lambda: self.edt_tagStringNode.clear())

		self.btn_tagGlyph.setToolTip('Add tags to current glyph.')
		self.btn_tagWindow.setToolTip('Add tags to all glyphs in current Glyph window.')
		self.btn_tagSelection.setToolTip('Add tags to current selection in Font window.')
		self.btn_tagNodes.setToolTip('Add name selected nodes at current glyph.')
		self.btn_tagWindowNodes.setToolTip('Add name to selected nodes at all glyphs in current Glyph window.')
		self.btn_tagNodesClear.setToolTip('Clear/Reset input filed.')
		
		# - Build
		self.addWidget(QtGui.QLabel('Glyph tagging:'),			1, 0, 1, 9)
		self.addWidget(self.edt_tagString, 						2, 0, 1, 9)
		self.addWidget(self.btn_tagGlyph, 						3, 0, 1, 3)
		self.addWidget(self.btn_tagWindow, 						3, 3, 1, 3)
		self.addWidget(self.btn_tagSelection, 					3, 6, 1, 3)
		self.addWidget(QtGui.QLabel('Node naming:'),			4, 0, 1, 9)
		self.addWidget(self.edt_tagStringNode, 					5, 0, 1, 9)
		self.addWidget(self.btn_tagNodes, 						6, 0, 1, 3)
		self.addWidget(self.btn_tagWindowNodes, 				6, 3, 1, 3)
		self.addWidget(self.btn_tagNodesClear, 					6, 6, 1, 3)

	# - Procedures
	def tag_glyphs(self, mode):
		# - Init
		new_tags = self.edt_tagString.text.replace(' ', '').split(',')

		# - Helper
		def tag(glyph, tagList):
			glyph.setTags(tagList)
			glyph.updateObject(glyph.fl, 'Glyph: %s; Add tags: %s ' %(glyph.name, tagList))
			glyph.update()

		# - Process
		if mode == 'G':
			glyph = eGlyph()
			tag(glyph, new_tags)
			
		else:
			process_glyphs = []
			
			if mode == 'W':
				process_glyphs = [pGlyph(glyph) for glyph in pWorkspace().getTextBlockGlyphs()]

			elif mode == 'S':
				process_glyphs = pFont().selected_pGlyphs()
			
			for glyph in process_glyphs:
				tag(glyph, new_tags)

		self.edt_tagString.clear()

	def tag_nodes(self, mode):
		# - Init
		new_name = self.edt_tagStringNode.text.strip()

		# - Helper
		def tag(glyph, newName):
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				for node in glyph.selectedNodes(layer):
					node.name = newName
			
			glyph.updateObject(glyph.fl, 'Glyph: %s; Nodes named: %s ' %(glyph.name, new_name))
			glyph.update()

		# - Process
		if mode == 'G':
			glyph = eGlyph()
			tag(glyph, new_name)
			
		elif mode == 'W':
			process_glyphs = []
			process_glyphs = [eGlyph(glyph) for glyph in pWorkspace().getTextBlockGlyphs()]
					
			for glyph in process_glyphs:
				tag(glyph, new_name)
			
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.dropGuide = TRDropGuide()
		self.glyphTags = TRGlyphTag()

		# - Build ---------------------------
		layoutV.addLayout(self.dropGuide)
		layoutV.addLayout(self.glyphTags)

		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()