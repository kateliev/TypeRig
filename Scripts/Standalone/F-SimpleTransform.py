#FLM: Font: Simple Transformations (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy import pFont, pGlyph, pShape
from typerig.brain import transform

# - Init --------------------------------
app_version = '0.01'
app_name = 'Font Slanter'

# -- Strings
text_layer = ['Active Layer', 'All Master Layers']
text_transform = ['Slant', 'Scale', 'Rotate']
text_glyphset = ['All Glyphs', 'Selection']

class dlg_transformFont(QtGui.QDialog):
	def __init__(self):
		super(dlg_transformFont, self).__init__()
	
		# - Init
		

		# - Widgets
		self.cmb_layer = QtGui.QComboBox()
		self.cmb_transform = QtGui.QComboBox()
		self.cmb_glyphset = QtGui.QComboBox()
		
		self.cmb_layer.addItems(text_layer)
		self.cmb_transform.addItems(text_transform)
		self.cmb_glyphset.addItems(text_glyphset)

		self.edt_x = QtGui.QLineEdit('0.0')
		self.edt_y = QtGui.QLineEdit('0.0')

		self.btn_apply = QtGui.QPushButton('Apply Transformation')
		self.btn_apply.clicked.connect(self.applyTransform)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Affine Transformations:'),0, 0, 1, 4)
		layoutV.addWidget(self.cmb_glyphset,		1, 0, 1, 4)
		layoutV.addWidget(self.cmb_layer, 			2, 0, 1, 4)
		layoutV.addWidget(self.cmb_transform, 		3, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('X:'),		4, 0, 1, 1)
		layoutV.addWidget(self.edt_x,				4, 1, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Y:'),		4, 2, 1, 1)
		layoutV.addWidget(self.edt_y,				4, 3, 1, 1)
		layoutV.addWidget(self.btn_apply, 			5, 0, 1, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 120)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def applyTransform(self):
		# - Init
		activeFont = pFont()
		inp_x, inp_y  =  float(self.edt_x.text), float(self.edt_y.text)

		def transformGlyph(glyph, layer, matrix):
			'''
			if glyph.hasLayer(layer):
				for shape in glyph.listUnboundShapes(layer):
					tShape = pShape(shape)
					
					if not tShape.isChanged():
						for node in tShape.nodes():
							tNode = matrix.applyTransformation(node.x, node.y)
							node.setXY(*tNode)

						tShape.fl.update()
				
				glyph.update()
				#glyph.updateObject(glyph.fl, 'DONE:\tTransform:\t Glyph /%s;\tLayer: %s' %(glyph.name, layer))
				print 'DONE:\tTransform:\t Glyph /%s;\tLayer: %s' %(glyph.name, layer)

			else:
				print 'ERROR:\tNot found:\t Glyph /%s;\tLayer: %s' %(glyph.name, layer)
			'''
			if glyph.hasLayer(layer):
				if not len(glyph.hasGlyphComponents()):
					for node in glyph.nodes(layer):
						tNode = matrix.applyTransformation(node.x, node.y)
						node.setXY(*tNode)
									
				glyph.update()
				glyph.updateObject(glyph.fl, 'DONE:\tTransform:\t Glyph /%s;\tLayer: %s' %(glyph.name, layer))
			else:
				print 'ERROR:\tNot found:\t Glyph /%s;\tLayer: %s' %(glyph.name, layer)

		# - Set parameters
		if self.cmb_glyphset.currentIndex == 0:
			workSet = activeFont.pGlyphs()
		elif self.cmb_glyphset.currentIndex == 1:
			workSet = activeFont.selected_pGlyphs()
		else:
			workSet = []

		if self.cmb_layer.currentIndex == 0:
			wLayer = None
		else:
			wLayer = activeFont.masters()

		# - Set Transformation
		
		if self.cmb_transform.currentIndex == 0:
			workTrans = transform().skew(inp_x, inp_y)
		elif self.cmb_transform.currentIndex == 2:
			workTrans = transform().rotate(inp_x)
		elif self.cmb_transform.currentIndex == 1:
			workTrans = transform().scale(inp_x, inp_y)

		for glyph in workSet:
			if wLayer is not None:
				for layer in wLayer:
					transformGlyph(glyph, layer, workTrans)
			else:
				transformGlyph(glyph, None, workTrans)

		activeFont.update()
		fl6.Update(CurrentFont())

	
# - RUN ------------------------------
dialog = dlg_transformFont()