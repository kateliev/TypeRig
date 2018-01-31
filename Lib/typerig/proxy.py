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
class pNode(object):
	'''Proxy to flNode object

	Constructor:
		pNode(flNode)

	Attributes:
		.fl (flNode): Original flNode 
		.parent (flContour): parent contour
		.contour (flContour): parent contour
	'''
	def __init__(self, node):
		self.fl = node
		self.parent = self.contour = self.fl.contour
		self.name = self.fl.name
		self.index = self.fl.index
		self.id = self.fl.id
		self.isOn = self.fl.isOn
		self.x, self.y = self.fl.x, self.fl.y
		self.angle = self.fl.angle

	# - Basics -----------------------------------------------
	def getTime(self):
		return self.contour.getT(self.fl)

	def getNext(self):
		return self.fl.getNext()

	def getNextOn(self):
		nextNode = self.fl.getNext()
		return  nextNode if nextNode.isOn() else nextNode.getNext().getOn()

	def getNextOn(self):
		prevNode = self.fl.getPrev()
		return  prevNode if prevNode.isOn() else prevNode.getPrev().getOn()

	def getPrev(self):
		return self.fl.getPrev()

	def getOn(slef):
		return self.fl.getOn()

	def getSegment(self, relativeTime=0):
		return self.contour.segment(self.getTime() + relativeTime)	


class pGlyph(object):
	'''Proxy to flGlyph and fgGlyph combined into single entity.

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
		'''Return all nodes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flNodes]
		'''
		return sum([contour.nodes() for contour in self.layer(layer).getContours()], [])

	def contours(self, layer=None):
		'''Return all contours at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flContours]
		'''
		return [contour for contour in self.layer(layer).getContours()]

	def layers(self):
		'''Return all layers'''
		return self.fl.layers

	def layer(self, layer=None):
		'''Returns layer no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			flLayer
		'''
		if layer is None:
			return self.fl.activeLayer
		else:
			if isinstance(layer, int):
				return self.fl.layers[layer]

			elif isinstance(layer, basestring):
				return self.fl.getLayerByName(layer)

	def shapes(self, layer=None):
		'''Return all shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapes]
		'''
		if layer is None:
			return self.fl.activeLayer.shapes
		else:
			if isinstance(layer, int):
				return self.fl.layers[layer].shapes

			elif isinstance(layer, basestring):
				return self.fl.getLayerByName(layer).shapes

	def masters(self):
		'''Returns all master layers.'''
		return [layer for layer in self.layers() if layer.isMasterLayer]

	def masks(self):
		'''Returns all mask layers.'''
		return [layer for layer in self.layers() if layer.isMaskLayer]

	def services(self):
		'''Returns all service layers.'''
		return [layer for layer in self.layers() if layer.isService]

	def addLayer(self, layer, toBack=False):
		'''Adds a layer to glyph.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			toBack (bool): Send layer to back
		Returns:
			None
		'''
		if isinstance(layer, fl6.flLayer):
			self.fl.addLayer(layer, toBack)

		elif isinstance(layer, fgt.fgLayer):
			self.fg.layers.append(layer)

	def update(self, fl=True, fg=False):
		'''Updates the glyph and sends notification to the editor.
		Args:
			fl (bool): Update the flGlyph
			fg (bool): Update the fgGlyph
		'''
		# !TODO: Undo?
		if fl:self.fl.update()
		if fg:self.fg.update()

		fl6.flItems.notifyGlyphUpdated(self.package.id, self.id)

	# - Glyph Selection -----------------------------------------------
	def selected(self, filterOn=False):
		'''Return all selected nodes indexes at current layer.
		Args:
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[int]
		'''
		allNodes = self.nodes()
		return [allNodes.index(node) for node in self.selectedNodes(filterOn)]

	def selectedNodes(self, filterOn=False):
		'''Return all selected nodes at current layer.
		Args:
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[flNode]
		'''
		
		if not filterOn:
			return [node for node in self.nodes() if node.selected]
		else:
			return [node for node in self.nodes() if node.selected and node.isOn]

	def selectedAtContours(self, index=True, filterOn=False):	
		'''Return all selected nodes and the contours they rest upon at current layer.
		Args:
			index (bool): If True returns only indexes, False returns flContour, flNode
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[tuple(int, int)]: [(contourID, nodeID)..()] or 
			list[tuple(flContour, flNode)]
		'''
		allContours = self.contours()
		
		if index:
			return [(allContours.index(node.contour), node.index) for node in self.selectedNodes(filterOn)]
		else:
			return [(node.contour, node) for node in self.selectedNodes(filterOn)]

	def selectedAtShapes(self, index=True, filterOn=False):
		'''Return all selected nodes and the shapes they belong at current layer.
		Args:
			index (bool): If True returns only indexes, False returns flShape, flNode
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[tuple(int, int)]: [(shapeID, nodeID)..()] or
			list[tuple(flShape, flNode)]
		'''
		allContours = self.contours()
		allShapes = self.shapes()

		if index:
			return [(allShapes.index(shape), allContours.index(contour), node.index) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(filterOn)]
		else:
			return [(shape, contour, node) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(filterOn)]

	def selectedCoords(self, layer=None, filterOn=False):
		'''Return the coordinates of all selected nodes at the current layer or other.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[QPointF]
		'''
		nodelist = self.selectedAtContours(filterOn=filterOn)
		pLayer = self.layer(layer)
			
		return [pLayer.getContours()[item[0]].nodes()[item[1]].pointf for item in nodelist]

	def selectedSegments(self, layer=None):
		'''Returns list of currently selected segments
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		return [self.contours(layer)[cID].segment(self.mapNodes2Times(layer)[cID][nID]) for cID, nID in self.selectedAtContours()]

	# - Outline -----------------------------------------------
	def _mapOn(self, layer=None):
		'''Create map of onCurve Nodes for every contour in given layer
		Returns:
			dict: {contour_index : {True_Node_Index : on_Curve__Node_Index}...}
		'''
		contourMap = {}		
		allContours = self.contours(layer)
		
		for contour in allContours:
			nodeMap = {}
			countOn = -1

			for node in contour.nodes():
				countOn += node.isOn # Hack-ish but working
				nodeMap[node.index] = countOn
				
			contourMap[allContours.index(contour)] = nodeMap

		return contourMap

	def mapNodes2Times(self, layer=None):
		'''Create map of Nodes at contour times for every contour in given layer
		Returns:
			dict{Contour index (int) : dict{Contour Time (int): Node Index (int) }}
		'''
		return self._mapOn(layer)

	def mapTimes2Nodes(self, layer=None):
		'''Create map of Contour times at node indexes for every contour in given layer
		Returns:
			dict{Contour index (int) : dict{Node Index (int) : Contour Time (int) }}
		'''
		n2tMap = self._mapOn(layer)
		t2nMap = {}

		for cID, nodeMap in n2tMap.iteritems():
			tempMap = {}
			
			for nID, time in nodeMap.iteritems():
				tempMap.setdefault(time, []).append(nID)

			t2nMap[cID] = tempMap

		return t2nMap

	def getSegment(self, cID, nID, layer=None):
		'''Returns contour segment of the node specified at given layer
		Args:
			cID (int): Contour index
			nID (int): Node of insertion index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			CurveEx
		'''
		return self.contours(layer)[cID].segment(self._mapOn(layer)[cID][nID])

	def segments(self, cID, layer=None):
		'''Returns all contour segments at given layer
		Args:
			cID (int): Contour index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		return self.contours(layer)[cID].segments()

	def nodes4segments(self, cID, layer=None):
		'''Returns all contour segments and their corresponding nodes at given layer
		Args:
			cID (int): Contour index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			dict{time(int):(CurveEx, list[flNode]}
		'''

		segments = self.segments(cID, layer)
		
		nodes = self.nodes(layer)
		nodes.append(nodes[0]) # Dirty Close contour

		timeTable = self.mapTimes2Nodes(layer)[cID]
		n4sMap = {}

		for time, nodeIndexes in timeTable.iteritems():
			n4sMap[time] = (segments[time], [nodes[nID] for nID in nodeIndexes] + [nodes[nodeIndexes[-1] + 1]]) # Should be closed otherwise fail

		return n4sMap

	def insertNodesAt(self, cID, nID, nodeList, layer=None):
		'''Inserts a list of nodes to specified contour, starting at given index all on layer specified.
		Args:
			cID (int): Contour index
			nID (int): Node of insertion index
			nodeList (list): List of flNode objects
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		self.contours(layer)[cID].insert(nID, nodeList)

	def removeNodes(self, cID, nodeList, layer=None):
		'''Removes a list of nodes from contour at layer specified.
		Args:
			cID (int): Contour index
			nodeList (list): List of flNode objects
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		for node in nodeList:
			self.contours(layer)[cID].removeOne(node)

	def insertNodeAt(self, cID, nID_time, layer=None):
		''' Inserts node in contour at specified layer
		Arg:
			cID (int): Contour Index
			nID_time (float): Node index + float time
			layer (int or str): Layer index or name. If None returns ActiveLayer

		!NOTE: FL6 treats contour insertions (as well as nodes) as float times along contour,
		so inserting a node at .5 t between nodes with indexes 3 and 4 will be 3 (index) + 0.5 (time) = 3.5
		'''
		self.contours(layer)[cID].insertNodeTo(nID_time)

	def removeNodeAt(self, cID, nID, layer=None):
		'''Removes a node from contour at layer specified.
		Args:
			cID (int): Contour index
			nID (int): Index of Node to be removed
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		self.contours(layer)[cID].removeAt(nID)

	def translate(self, dx, dy, layer=None):
		'''Translate (shift) outline at given layer.
		Args:
			dx (float), dy (float): delta (shift) X, Y
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.translate(dx, dy)
		pLayer.applyTransform(pTransform)

	def scale(self, sx, sy, layer=None):
		'''Scale outline at given layer.
		Args:
			sx (float), sy (float): delta (scaling) X, Y
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.scale(sx, sy)
		pLayer.applyTransform(pTransform)

	def slant(self, deg, layer=None):
		'''Slant outline at given layer.
		Args:
			deg (float): degrees of slant
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		from math import tan, radians
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.shear(tan(radians(deg)), 0)
		pLayer.applyTransform(pTransform)

	def rotate(self, deg, layer=None):
		'''Rotate outline at given layer.
		Args:
			deg (float): degrees of slant
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.rotate(deg)
		pLayer.applyTransform(pTransform)

	# - Interpolation  -----------------------------------------------
	def _shape2fg(self, flShape):
		'''Convert flShape to fgShape'''
		tempFgShape = fgt.fgShape()
		flShape.convertToFgShape(tempFgShape)
		return tempFgShape

	def blendShapes(self, shapeA, shapeB, blendTimes, outputFL=True, blendMode=0, engine='fg'):
		'''Blend two shapes at given times (anisotropic support).
		Args:
			shapeA (flShape), shapeB (flShape): Shapes to be interpolated
			blendTimes (int or float or tuple(float, float)): (int) for percent 0%-100% or (float) time for both X,Y or tuple(float,float) times for anisotropic blending
			outputFL (bool): Return blend native format or flShape (default)
			blendMode (int): ?
			engine (str): 'fg' for FontGate (in-build).

		Returns:
			Native (interpolation engine dependent) or flShape (default)
		'''

		if engine.lower() == 'fg': # Use FontGate engine for blending/interpolation
			if isinstance(shapeA, fl6.flShape): shapeA = self._shape2fg(shapeA)
			if isinstance(shapeB, fl6.flShape):	shapeB = self._shape2fg(shapeB)
			
			if isinstance(blendTimes, tuple): blendTimes = pqt.QtCore.QPointF(*blendTimes)
			if isinstance(blendTimes, int): blendTimes = pqt.QtCore.QPointF(float(blendTimes)/100, float(blendTimes)/100)
			if isinstance(blendTimes, float): blendTimes = pqt.QtCore.QPointF(blendTimes, blendTimes)

			tempBlend = fgt.fgShape(shapeA, shapeB, blendTimes.x(), blendTimes.y(), blendMode)
			return fl6.flShape(tempBlend) if outputFL else tempBlend

	# - Metrics -----------------------------------------------
	def getLSB(self, layer=None):
		'''Get the Left Side-bearing at given layer (int or str)'''
		pLayer = self.layer(layer)
		return int(pLayer.boundingBox.x())
	
	def getAdvance(self, layer=None):
		'''Get the Advance Width at given layer (int or str)'''
		pLayer = self.layer(layer)
		return int(pLayer.advanceWidth)

	def getRSB(self, layer=None):
		'''Get the Right Side-bearing at given layer (int or str)'''
		pLayer = self.layer(layer)
		return int(pLayer.advanceWidth - (pLayer.boundingBox.x() + pLayer.boundingBox.width()))

	def setLSB(self, newLSB, layer=None):
		'''Set the Left Side-bearing (int) at given layer (int or str)'''
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		shiftDx = newLSB - int(pLayer.boundingBox.x())
		pTransform.translate(shiftDx, 0)
		pLayer.applyTransform(pTransform)

	def setRSB(self, newRSB, layer=None):
		'''Set the Right Side-bearing (int) at given layer (int or str)'''
		pLayer = self.layer(layer)
		pRSB = pLayer.advanceWidth - (pLayer.boundingBox.x() + pLayer.boundingBox.width())
		pLayer.advanceWidth += newRSB - pRSB

	def setAdvance(self, newAdvance, layer=None):
		'''Set the Advance Width (int) at given layer (int or str)'''
		pLayer = self.layer(layer)
		pLayer.advanceWidth = newAdvance

	# - Anchors and pins -----------------------------------------------
	def anchors(self, layer=None):
		'''Return list of anchors (list[flAnchor]) at given layer (int or str)'''
		return self.layer(layer).anchors

	def addAnchor(self, coordTuple, name, layer=None, isAnchor=True):
		'''	Adds named Anchor at given layer.
		Args:
			coordTuple (tuple(float,float)): Anchor coordinates X, Y
			name (str): Anchor name
			layer (int or str): Layer index or name. If None returns ActiveLayer
			isAnchor (bool): True creates a true flAnchor, False ? (flPinPoint)
		Returns:
			None
		'''
		newAnchor = fl6.flPinPoint(pqt.QtCore.QPointF(*coordTuple))
		newAnchor.name = name
		newAnchor.anchor = isAnchor

		self.anchors(layer).append(newAnchor)

	# - Guidelines -----------------------------------------------
	def guidelines(self, layer=None):
		'''Return list of guidelines (list[flGuideline]) at given layer (int or str)'''
		return self.layer(layer).guidelines

	def addGuideline(self, coordTuple, name='', angle=0, layer=None):
		'''Adds named Guideline at given layer
		Args:
			coordTuple (tuple(float,float) or tuple(float,float,float,float)): Guideline coordinates X, Y and given angle or two node reference x1,y1 and x2,y2
			name (str): Anchor name
			angle (float): Incline of the guideline
			layer (int or str): Layer index or name. If None returns ActiveLayer			
		Returns:
			None
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
		'''Return TypeRig proxy glyph object (pGlyph) by index (int) or name (str).'''
		if isinstance(glyph, int) or isinstance(glyph, basestring):
			return pGlyph(self.fg, self.fg[glyph])
		else:
			return pGlyph(self.fg, glyph)

	def symbol(self, gID):
		'''Return fgSymbol by glyph index (int)'''
		return fl6.fgSymbol(gID, self.fg)

	def glyphs(self):
		'''Return list of FontGate glyph objects (list[fgGlyph]).'''
		return self.fg.glyphs

	def symbols(self):
		'''Return list of FontGate symbol objects (list[fgSymbol]).'''
		return [self.symbol(gID) for gID in range(len(self.fg.glyphs))]
	
	def pGlyphs(self, processList=None):
		'''Return list of TypeRig proxy Glyph objects glyph objects (list[pGlyph]).'''
		return [self.glyph(glyph) for glyph in self.fg] if not processList else [self.glyph(glyph) for glyph in processList]

	# - Guides & Hinting Basics ----------------------------------------
	def guidelines(self, hostInf=False, fontgate=False):
		'''Return font guidelines
		Args:
			hostInf (bool): If True Return flHostInfo guidelines host objects
			fontgate (bool): If True return FontGate font guideline objects
		Returns
			list[flGuideline] or list[fgGuideline]
		'''
		if not fontgate:
			return self.fl.guidelines if not hostInf else self.fl.guidelinesHost.guidelines
		else:
			return self.fg.guides

	def addGuideline(self, flGuide):
		'''Adds a guideline (flGuide) to font guidelines'''
		self.fl.guidelinesHost.appendGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def delGuideline(self, flGuide):
		'''Removes a guideline (flGuide) from font guidelines'''
		self.fl.guidelinesHost.removeGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def clearGuidelines(self):
		'''Removes all font guidelines'''
		self.fl.guidelinesHost.clearGuidelines()
		self.fl.guidelinesHost.guidelinesChanged()

	def zones(self, fontgate=False):
		'''Returns font alignment (blue) zones (list[flGuideline])'''
		if not fontgate:
			return (self.fl.zones(True), self.fl.zones(False)) # tuple(top, bottom) zones
		else:
			return self.fg.hinting.familyZones # Empty/non working currently (as well as .masters)

	def hinting(self):
		'''Returns fonts hinting'''
		return self.fg.hinting

	# - Charset -----------------------------------------------
	def uppercase(self):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isupper()] # Skip Private ranges - glyph.unicode < 10000

	def lowercase(self):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).islower()]		

	def figures(self):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isdigit()]	

	def symbols(self):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and not unichr(glyph.unicode).isdigit() and not unichr(glyph.unicode).isalpha()]

	def ligatures(self):
		'''Returns all ligature characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if self.__altMarks['liga'] in glyph.name and not self.__altMarks['hide'] in glyph.name]

	def alternates(self):
		'''Returns all alternate characters (list[fgGlyph])'''
		return [glyph for glyph in self.fg if self.__altMarks['alt'] in glyph.name and not self.__altMarks['hide'] in glyph.name]

	# - Information -----------------------------------------------
	def info(self):
		return self.info
