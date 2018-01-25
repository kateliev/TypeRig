# MODULE: Fontlab 6 Proxy | Typerig
# VER 	: 0.22
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

# - Classes -------------------------------
class pGlyph(object):
	'''
	Proxy to flGlyph and fgGlyph combined into single entity.

	Constructor:
		pGlyph() - default represents the current glyph and current font
		pGlyph(fgFont, fgGlyph)
	
	Methods:

	Attributes:
		.parent (fgFont)
		.fg (fgGlyph)
		.fl (flGlyph)
	'''

	def __init__(self, font=None, glyph=None):

		if font is not None and glyph is not None:
			self.parent = font
			self.fg = glyph
			self.fl = fl6.flGlyph(glyph, font)
			self.package = self.fl.package
			
		else:
			self.parent = fl6.CurrentFont()
			self.fg = fl6.CurrentGlyph()
			self.fl = fl6.flGlyph(fl6.CurrentGlyph(), fl6.CurrentFont())
			self.package = self.fl.package

		self.name = self.fg.name
		self.index = self.fg.index
		self.id = self.fl.id
		self.mark = self.fl.mark
		self.tags = self.fl.tags
		self.unicode = self.fg.unicode

	def __repr__(self):
		return '<%s name=%s index=%s unicode=%s>' % (self.__class__.__name__, self.name, self.index, self.unicode)

	# - Basics -----------------------------------------------
	def activeLayer(self): return self.fl.activeLayer

	def mask(self): return self.fl.activeLayer.getMaskLayer(True)

	def activeGuides(self): return self.fl.activeLayer.guidelines

	def nodes(self, layer=None):
		# - Return all nodes at given layer
		return sum([contour.nodes() for contour in self.layer(layer).getContours()], [])

	def contours(self, layer=None):
		# - Return all contours at given layer
		return [contour for contour in self.layer(layer).getContours()]

	def layers(self):
		# - Return all layers
		return self.fl.layers

	def layer(self, layer=None):
		# - Return a layer no matter the reference
		if layer is None:
			return self.fl.activeLayer
		else:
			if isinstance(layer, int):
				return self.fl.layers[layer]

			elif isinstance(layer, basestring):
				return self.fl.getLayerByName(layer)

	def shapes(self, layer=None):
		if layer is None:
			return self.fl.activeLayer.shapes
		else:
			if isinstance(layer, int):
				return self.fl.layers[layer].shapes

			elif isinstance(layer, basestring):
				return self.fl.getLayerByName(layer).shapes

	def masters(self):
		# - Return all master layers
		return [layer for layer in self.layers() if layer.isMasterLayer]

	def masks(self):
		# - Return all mask layers
		return [layer for layer in self.layers() if layer.isMaskLayer]

	def services(self):
		# - Return all service layers
		return [layer for layer in self.layers() if layer.isService]

	def addLayer(self, layer, toBack=False):
		if isinstance(layer, fl6.flLayer):
			self.fl.addLayer(layer, toBack)

		elif isinstance(layer, fgt.fgLayer):
			self.fg.layers.append(layer)

	def update(self, fl=True, fg=False):
		# !TODO: Undo?
		if fl:self.fl.update()
		if fg:self.fg.update()

		fl6.flItems.notifyGlyphUpdated(self.package.id, self.id)

	# - Glyph Selection -----------------------------------------------
	def selected(self):
		allNodes = self.nodes()
		return [allNodes.index(node) for node in self.selectedNodes()]

	def selectedNodes(self):	
		# - Return flGlyph's activeLayer selected nodes as [(contourID, nodeID)..()]
		return [node for node in self.nodes() if node.selected]

	def selectedAtContours(self, index=True):	
		# - Return flGlyph's activeLayer selected nodes as [(contourID, nodeID)..()]
		allContours = self.contours()
		
		if index:
			return [(allContours.index(node.contour), node.index) for node in self.selectedNodes()]
		else:
			return [(node.contour, node) for node in self.selectedNodes()]

	def selectedAtShapes(self, index=True):
		allContours = self.contours()
		allShapes = self.shapes()

		if index:
			return [(allShapes.index(shape), allContours.index(contour), node.index) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes()]
		else:
			return [(shape, contour, node) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes()]

	def selectedCoords(self, layer=None):
		# - Return a list of coordinates for all selected nodes indexes in flGlyph's layer or activeLayer
		nodelist = self.selectedAtContours()
		pLayer = self.layer(layer)
			
		return [pLayer.getContours()[item[0]].nodes()[item[1]].pointf for item in nodelist]

	# - Outline -----------------------------------------------
	def insertNodes(self, cID, nID, nodeList, layer=None):
		self.contours(layer)[cID].insert(nID, nodeList)

	def removeNodes(self, cID, nID, nodeList, layer=None):
		for node in nodeList:
			self.contours(layer)[cID].removeOne(node)

	def insertNodeAt(self, cID, nID, layer=None):
		self.contours(layer)[cID].insertNodeTo(nID)

	def removeNodeAt(self, cID, nID, layer=None):
		self.contours(layer)[cID].removeAt(nID)

	def translate(self, dx, dy, layer=None):
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.translate(dx, dy)
		pLayer.applyTransform(pTransform)

	def scale(self, sx, sy, layer=None):
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.scale(sx, sy)
		pLayer.applyTransform(pTransform)

	def slant(self, deg, layer=None):
		from math import tan, radians
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.shear(tan(radians(deg)), 0)
		pLayer.applyTransform(pTransform)

	def rotate(self, deg, layer=None):
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.rotate(deg)
		pLayer.applyTransform(pTransform)

	def shape2fg(self, flShape):
		tempFgShape = fgt.fgShape()
		flShape.convertToFgShape(tempFgShape)
		return tempFgShape

	# - Interpolation  -----------------------------------------------
	def blendShapes(self, shapeA, shapeB, blendTimes, outputFL=True, blendMode=0, engine='fg'):
		if engine.lower() == 'fg': # Use FontGate engine for blending/interpolation
			if isinstance(shapeA, fl6.flShape): shapeA = self.shape2fg(shapeA)
			if isinstance(shapeB, fl6.flShape):	shapeB = self.shape2fg(shapeB)
			
			if isinstance(blendTimes, tuple): blendTimes = pqt.QtCore.QPointF(*blendTimes)
			if isinstance(blendTimes, int): blendTimes = pqt.QtCore.QPointF(float(blendTimes)/100, float(blendTimes)/100)
			if isinstance(blendTimes, float): blendTimes = pqt.QtCore.QPointF(blendTimes, blendTimes)

			tempBlend = fgt.fgShape(shapeA, shapeB, blendTimes.x(), blendTimes.y(), blendMode)
			return fl6.flShape(tempBlend) if outputFL else tempBlend

	def blendLayers(self, layerA, layerB, blendTimes, outputFL=True, blendMode=0, engine='fg'):
		from typerig.utils import linInterp

		if isinstance(blendTimes, tuple): blendTimes = pqt.QtCore.QPointF(*blendTimes)
		if isinstance(blendTimes, int): blendTimes = pqt.QtCore.QPointF(float(blendTimes)/100, float(blendTimes)/100)
		if isinstance(blendTimes, float): blendTimes = pqt.QtCore.QPointF(blendTimes, blendTimes)

		if layerA.isCompatible(layerB):
			# - Init
			blendLayer = fl6.flLayer('B:%s %s, t:%s' %(layerA.name, layerB.name, str(blendTimes)))
			
			# - Set and interpolate metrics
			blendLayer.advanceWidth = int(linInterp(layerA.advanceWidth, layerB.advanceWidth, blendTimes.x()))
			
			# - Interpolate shapes
			for shapeA in layerA.shapes:
				for shapeB in layerB.shapes:
					if shapeA.isCompatible(shapeB):
						tempBlend = self.blendShapes(shapeA, shapeB, blendTimes, outputFL, blendMode, engine)
						blendLayer.addShape(tempBlend)

			return blendLayer

			
	# - Metrics -----------------------------------------------
	def getLSB(self, layer=None):
		pLayer = self.layer(layer)
		return int(pLayer.boundingBox.x())
	
	def getAdvance(self, layer=None):
		pLayer = self.layer(layer)
		return int(pLayer.advanceWidth)

	def getRSB(self, layer=None):
		pLayer = self.layer(layer)
		return int(pLayer.advanceWidth - (pLayer.boundingBox.x() + pLayer.boundingBox.width()))

	def setLSB(self, newLSB, layer=None):
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		shiftDx = newLSB - int(pLayer.boundingBox.x())
		pTransform.translate(shiftDx, 0)
		pLayer.applyTransform(pTransform)

	def setRSB(self, newRSB, layer=None):
		pLayer = self.layer(layer)
		pRSB = pLayer.advanceWidth - (pLayer.boundingBox.x() + pLayer.boundingBox.width())
		pLayer.advanceWidth += newRSB - pRSB

	def setAdvance(self, newAdvance, layer=None):
		pLayer = self.layer(layer)
		pLayer.advanceWidth = newAdvance

	# - Anchors and pins -----------------------------------------------
	def anchors(self, layer=None):
		return self.layer(layer).anchors

	def addAnchor(self, coordTuple, name, layer=None, isAnchor=True):
		'''
		Adds named Anchor at layer (None = Current Layer) with coordinates (x,y)
		'''
		newAnchor = fl6.flPinPoint(pqt.QtCore.QPointF(*coordTuple))
		newAnchor.name = name
		newAnchor.anchor = isAnchor

		self.anchors(layer).append(newAnchor)

	# - Guidelines -----------------------------------------------
	def guidelines(self, layer=None):
		return self.layer(layer).guidelines

	def addGuideline(self, coordTuple, name='', angle=0, layer=None):
		'''
		Adds named Guideline at layer (None = Current Layer) with:
		- coordinates (x,y) and angle
		- coordinates (x1, y1, x2, y2)
		'''
		if len(coordTuple) == 2:
			origin = pqt.QtCore.QPointF(0,0)
			position = pqt.QtCore.QPointF(*coordTuple)

			vector = pqt.QtCore.QLineF(position, origin)
			vector.setAngle(90 - angle)
		else:
			vector = pqt.QtCore.QLineF(*coordTuple)

		newGuideline = fl6.flGuideLine(vector)
		newGuideline.name =  name
		newGuideline.style = 'gsGlyphGuideline'
		
		self.layer(layer).appendGuidelines([newGuideline])


class pFont(object):
	'''
	A Proxy Font representation of Fonlab fgFont and flPackage.

	Constructor:
		pFont() - default represents the current glyph and current font
		pFont(fgFont)
	
	'''

	def __init__(self, font=None):

		if font is not None:
			self.fg = font
			self.fl = fl6.flPackage(font)
			
		else:
			self.fg = fl6.CurrentFont()
			self.fl = fl6.flPackage(fl6.CurrentFont())

		# - Special 
		self.__altMarks = {'liga':'_', 'alt':'.', 'hide':'__'}
		self.__diactiricalMarks = ['grave', 'dieresis', 'macron', 'acute', 'cedilla', 'uni02BC', 'circumflex', 'caron', 'breve', 'dotaccent', 'ring', 'ogonek', 'tilde', 'hungarumlaut', 'caroncomma', 'commaaccent', 'cyrbreve'] # 'dotlessi', 'dotlessj'

	
	def __repr__(self):
		return '<%s name=%s glyphs=%s path=%s>' % (self.__class__.__name__, self.fg.info.familyName, len(self.fg), self.fg.path)

	# - Font Basics -----------------------------------------------
	def glyph(self, glyph):
		if isinstance(glyph, int) or isinstance(glyph, basestring):
			return pGlyph(self.fg, self.fg[glyph])
		else:
			return pGlyph(self.fg, glyph)

	def symbol(self, gID):
		return fl6.fgSymbol(gID, self.fg)

	def glyphs(self):
		return self.fg.glyphs

	def symbols(self):
		return [self.symbol(gID) for gID in range(len(self.fg.glyphs))]
	
	def pGlyphs(self, processList=None):
		return [self.glyph(glyph) for glyph in self.fg] if not processList else [self.glyph(glyph) for glyph in processList]

	# - Guides & Hinting Basics ----------------------------------------
	def guidelines(self, hostInf=False, fontgate=False):
		if not fontgate:
			return self.fl.guidelines if not hostInf else self.fl.guidelinesHost.guidelines
		else:
			return self.fg.guides

	def addGuideline(self, flGuide):
		self.fl.guidelinesHost.appendGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def delGuideline(self, flGuide):
		self.fl.guidelinesHost.removeGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def clearGuidelines(self):
		self.fl.guidelinesHost.clearGuidelines()
		self.fl.guidelinesHost.guidelinesChanged()

	def zones(self, fontgate=False):
		if not fontgate:
			return (self.fl.zones(True), self.fl.zones(False)) # tuple(top, bottom) zones
		else:
			return self.fg.hinting.familyZones # Empty/non working currently (as well as .masters)

	def hinting(self):
		return self.fg.hinting

	# - Charset -----------------------------------------------
	def uppercase(self):
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isupper()] # Skip Private ranges - glyph.unicode < 10000

	def lowercase(self):
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).islower()]		

	def figures(self):
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isdigit()]	

	def symbols(self):
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and not unichr(glyph.unicode).isdigit() and not unichr(glyph.unicode).isalpha()]

	def ligatures(self):
		return [glyph for glyph in self.fg if self.__altMarks['liga'] in glyph.name and not self.__altMarks['hide'] in glyph.name]

	def alternates(self):
		return [glyph for glyph in self.fg if self.__altMarks['alt'] in glyph.name and not self.__altMarks['hide'] in glyph.name]

	# - Information -----------------------------------------------
	def info(self):
		return self.info
