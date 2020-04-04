# MODULE: Fontlab 6 Proxy | Typerig
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.74.5'

# - Dependencies --------------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt
import FL as legacy
#from struct import calcsize

# - Init
#sys64bit = calcsize('P')*8 == 64

# - Procedures/Functions ------------------
def openFont(file_path):
	''' Loads Font file from path (str) and returns opened fgFont object'''
	fl6.flItems.requestLoadingFont(file_path)
	return fl6.CurrentFont()

# - Classes -------------------------------
class pWorkspace(object):
	'''Proxy to flWorkspace object

	Constructor:
		pWorkspace()

	Attributes:
		.fl (flWorkspace): Current workspace
		.main (QWidget): Main QWidget's window
	'''

	def __init__(self):
		self.fl = fl6.flWorkspace.instance()
		self.main = self.fl.mainWindow
		self.name = self.fl.name

	def getCanvas(self, atCursor=False):
		return self.fl.getActiveCanvas() if not atCursor else self.fl.getCanvasUnderCursor()

	def getCanvasList(self):
		return self.fl.canvases()

	def getSelectedNodes(self):
		return [nif.node for nif in self.getCanvas().selectedNodes()]

	def getTextBlockList(self, atCursor=False):
		return self.getCanvas(atCursor).textBlocks()

	def getTextBlockGlyphs(self, tbi=0):
		return [info.glyph for info in self.getTextBlockList()[tbi].getAllGlyphs()]

	def getActiveGlyphInfo(self, tbi=0):
		return self.getTextBlockList()[tbi].getActiveGlyph()

	def getActiveGlyph(self, tbi=0):
		return self.getActiveGlyphInfo(tbi).glyph

	def getPrevGlyphInfo(self, tbi=0):
		tb = self.getTextBlockList()[tbi]
		return tb.getPrevGlyphInLine(self.getActiveIndex(tbi))

	def getNextGlyphInfo(self, tbi=0):
		tb = self.getTextBlockList()[tbi]
		return tb.getNextGlyphInLine(self.getActiveIndex(tbi))

	def getActiveKernPair(self, tbi=0):
		return (self.getPrevGlyphInfo(tbi).glyph.name, self.getActiveGlyphInfo(tbi).glyph.name)

	def getActiveIndex(self, tbi=0):
		return self.getActiveLine(tbi).index(self.getActiveGlyphInfo(tbi))		

	def getActiveLine(self, tbi=0):
		return self.getTextBlockList()[tbi].getGlyphsInLine(self.getActiveGlyphInfo(tbi))

	def createFrame(self, string, x, y):
		active_canvas = self.getCanvas()
		fg_text = fl6.fgSymbolList(string)
		active_canvas.createFrame([fg_text], pqt.QtCore.QPointF(float(x),float(y)))
		active_canvas.update()


class pTextBlock(object):
	'''Proxy to flTextBlock object

	Constructor:
		pTextBlock(flTextBlock)

	Attributes:
		.fl (flTextBlock): flTextBlock Parent		
	'''

	def __init__(self, textBlock):
		self.fl = textBlock
		self.fontSize = self.getFontSize()
		self.textFrame = self.getFrameSize()
		self.textWarp = self.getWrapState()
		
		# - Page Sizes: in Pixels 72 DPI (EQ to points) and  *.96 DPI
		self.pageSizes = { 
							'Letter':(612, 792),
							'Tabloid':(792, 1224), 
							'Ledger':(1224, 792), 
							'Legal':(612, 1008), 
							'Statement':(396, 612), 
							'Executive':(540, 720), 
							'A0':(2384, 3371), 
							'A1':(1685, 2384), 
							'A2':(1190, 1684), 
							'A3':(842, 1190), 
							'A4':(595, 842), 
							'A5':(420, 595), 
							'B4':(729, 1032), 
							'B5':(516, 729), 
							'Folio':(612, 936), 
							'Quarto':(610, 780),
							'A0.96':(3179, 4494),
							'A1.96':(2245, 3179),
							'A2.96':(1587, 2245),
							'A3.96':(1123, 1587),
							'A4.96':(794, 1123),
							'A5.96':(559, 794),
							'A6.96':(397, 559),
							'A7.96':(280, 397),
							'A8.96':(197, 280),
							'A9.96':(140, 197)
						}

	def getFontSize(self):
		return self.fl.fontSize

	def setFontSize(self, fontSize):
		self.fl.fontSize = fontSize
		return self.update()

	def getFrameSize(self):
		return self.fl.frameRect

	def setFrameSize(self, width, height):
		self.fl.setFrameSize(pqt.QtCore.QSizeF(width, height))

	def setPageSize(self, sizeName, fixedHeight=(True, True)):
		self.setFrameSize(*self.pageSizes[sizeName])
		self.setWrapState(True)
		self.fl.setFixedHeight(*fixedHeight)
		return self.update()

	def setFrameWidth(self, width):
		self.fl.setFrameWidth(width)

	def getGlyphBounds(self):
		return self.fl.glyphsBoundsOnCanvas('emEditText')

	def setTextWrap(self, width):
		self.setFrameWidth(width)
		self.setWrapState(True)
		return self.update()

	def getWrapState(self):
		return self.fl.formatMode

	def setWrapState(self, wrapText=True):
		self.fl.formatMode = wrapText 

	def getString(self):
		self.fl.symbolList().string(True)

	def update(self):
		#self.fl.reformat()
		#self.fl.formatChanged()
		return self.fl.update()

	def clone(self):
		return self.fl.clone()

	def getTransform(self):
		return self.fl.transform
		
	def setTransform(self, newTransform):
		self.fl.transform = newTransform
		self.update()

	def resetTransform(self):
		oldTransform = self.fl.transform
		oldTransform.reset()
		self.setTransform(oldTransform)	

	def x(self):
		return self.fl.transform.m31()

	def y(self):
		return self.fl.transform.m32()

	def width(self):
		return self.fl.frameRect.width()

	def height(self):
		return self.fl.frameRect.height()

	def reloc(self, x, y):
		#'''
		oldTM = self.fl.transform
		newTM = pqt.QtGui.QTransform(oldTM.m11(), oldTM.m12(), oldTM.m13(), oldTM.m21(), oldTM.m22(), oldTM.m23(), float(x), float(y), oldTM.m33())
		self.setTransform(newTM)
		#'''
		'''
		frame = self.fl.frameRect
		frame.setX(x); frame.setY(y)
		self.fl.frameRect = frame
		'''
		self.update()

	def __repr__(self):
		return '<%s (%s, %s, %s, %s) fontSize=%s glyphs=%s>' % (self.__class__.__name__, self.x(), self.y(), self.width(), self.height(), self.fl.fontSize, self.fl.glyphsCount())	

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
		self.selected = self.fl.selected
		self.id = self.fl.id
		self.isOn = self.fl.isOn()
		self.type = self.fl.type
		self.x, self.y = float(self.fl.x), float(self.fl.y)
		self.angle = float(self.fl.angle)

	def __repr__(self):
		return '<%s (%s, %s) index=%s time=%s on=%s>' % (self.__class__.__name__, self.x, self.y, self.index, self.getTime(), self.isOn)
	
	# - Basics -----------------------------------------------
	def getTime(self):
		return self.contour.getT(self.fl)

	def getNext(self, naked=True):
		return self.fl.nextNode() if naked else self.__class__(self.fl.nextNode())

	def getNextOn(self, naked=True):
		nextNode = self.fl.nextNode()
		nextNodeOn = nextNode if nextNode.isOn() else nextNode.nextNode().getOn()
		return nextNodeOn if naked else self.__class__(nextNodeOn)

	def getPrevOn(self, naked=True):
		prevNode = self.fl.prevNode()
		prevNodeOn = prevNode if prevNode.isOn() else prevNode.prevNode().getOn()
		return prevNodeOn if naked else self.__class__(prevNodeOn)

	def getPrev(self, naked=True):
		return self.fl.prevNode() if naked else self.__class__(self.fl.prevNode())

	def getOn(self, naked=True):
		return self.fl.getOn() if naked else self.__class__(self.fl.getOn())

	def getMaxY(self, naked=True):
		next_node = self.getNextOn()
		prev_node = self.getPrevOn()

		if next_node.position.y() > prev_node.position.y():
			return next_node if naked else self.__class__(next_node)

		return prev_node if naked else self.__class__(prev_node)

	def getMinY(self, naked=True):
		next_node = self.getNextOn()
		prev_node = self.getPrevOn()

		if next_node.position.y() < prev_node.position.y():
			return next_node if naked else self.__class__(next_node)

		return prev_node if naked else self.__class__(prev_node)

	def getSegment(self, relativeTime=0):
		return self.contour.segment(self.getTime() + relativeTime)

	def getSegmentNodes(self, relativeTime=0):
		if len(self.getSegment(relativeTime)) == 4:
			currNode = self.fl if self.fl.isOn() else self.fl.getOn()
			
			if currNode != self.fl:
				tempNode = self.__class__(currNode)

				if tempNode.getTime() != self.getTime():
					currNode = tempNode.getPrevOn()

			currNode_bcpOut = currNode.nextNode()
			nextNode_bcpIn = currNode_bcpOut.nextNode()
			nextNode = nextNode_bcpIn.getOn()
		
			return (currNode, currNode_bcpOut, nextNode_bcpIn, nextNode)
		
		elif len(self.getSegment(relativeTime)) == 2:
			return (self.fl, self.fl.nextNode())

	def getContour(self):
		return self.fl.contour

	def distanceTo(self, node):
		if isinstance(node, self.__class__):
			return self.fl.distanceTo(node.fl.position)
		else:
			return self.fl.distanceTo(node.position)

	def distanceToNext(self):
		return self.fl.distanceTo(self.getNext().position)

	def distanceToPrev(self):
		return self.fl.distanceTo(self.getPrev().position)

	def angleTo(self, node):
		if isinstance(node, self.__class__):
			return self.fl.angleTo(node.fl.position)
		else:
			return self.fl.angleTo(node.position)

	def angleToNext(self):
		return self.fl.angleTo(self.getNext().position)

	def angleToPrev(self):
		return self.fl.angleTo(self.getPrev().position)

	def insertAfter(self, time):
		return self.contour.insertNodeTo(self.getTime() + time)

	def insertBefore(self, time):
		return self.contour.insertNodeTo(self.getPrevOn(False).getTime() + time)

	def insertAfterDist(self, distance):
		from typerig.brain import ratfrac
		return self.insertAfter(ratfrac(distance, self.distanceToNext(), 1))

	def insertBeforeDist(self, distance):
		from typerig.brain import ratfrac
		return self.insertBefore(1 - ratfrac(distance, self.distanceToPrev(), 1))

	def remove(self):
		self.contour.removeOne(self.fl)

	def update(self):
		self.fl.update()
		self.x, self.y = float(self.fl.x), float(self.fl.y)

	# - Transformation -----------------------------------------------
	def reloc(self, newX, newY):
		'''Relocate the node to new coordinates'''
		self.fl.x, self.fl.y = newX, newY
		self.x, self.y = newX, newY	
		#self.update()
	
	def shift(self, deltaX, deltaY):
		'''Shift the node by given amout'''
		self.fl.x += deltaX
		self.fl.y += deltaY
		self.x, self.y = self.fl.x, self.fl.y 
		#self.update()

	def smartReloc(self, newX, newY):
		'''Relocate the node and adjacent BCPs to new coordinates'''
		self.smartShift(newX - self.fl.x, newY - self.fl.y)

	def smartShift(self, deltaX, deltaY):
		'''Shift the node and adjacent BCPs by given amout'''
		if self.isOn:	
			nextNode = self.getNext(False)
			prevNode = self.getPrev(False)

			for node, mode in [(prevNode, not prevNode.isOn), (self, self.isOn), (nextNode, not nextNode.isOn)]:
				if mode: node.shift(deltaX, deltaY)
		else:
			self.shift(deltaX, deltaY)

	# - Effects --------------------------------
	def getSmartAngle(self):
		return (self.fl.isSmartAngle(), self.fl.smartAngleR)

	def setSmartAngle(self, radius):
		self.fl.smartAngleR = radius
		return self.fl.setSmartAngleEnbl(True)

	def delSmartAngle(self):
		return self.fl.setSmartAngleEnbl(False)

	def setSmartAngleRadius(self, radius):
		self.fl.smartAngleR = radius

	def getSmartAngleRadius(self):
		return self.fl.smartAngleR

class pNodesContainer(object):
	'''Abstract nodes container

	Constructor:
		pNodesContainer(list(flNode))

	Attributes:
		
	'''
	def __init__(self, nodeList, extend=pNode):
		
		# - Init
		if extend is not None: 
			self.nodes = [extend(node) for node in nodeList]
		else:
			self.nodes = nodeList
		
		self.extender = extend
		self.bounds = self.getBounds()
		self.x = lambda : self.getBounds().x
		self.y = lambda : self.getBounds().y
		self.width = lambda : self.getBounds().width
		self.height  = lambda : self.getBounds().height

	def __getitem__(self, index):
		return self.nodes.__getitem__(index)

	def __setitem__(self, index, value):
		return self.nodes.__setitem__(index, value)

	def __delitem__(self, index):
		self.nodes.__delitem__(index)

	def __repr__(self):
		return '<%s (%s, %s, %s, %s) nodes=%s>' %(self.__class__.__name__, self.bounds.x, self.bounds.y, self.bounds.width, self.bounds.height, len(self.nodes))

	def __len__(self):
		return len(self.nodes)

	def __hash__(self):
		return self.nodes.__hash__()

	def clone(self):
		try:
			return self.__class__([node.fl.clone() for node in self.nodes], extend=self.extender)
		except AttributeError:
			return self.__class__([node.clone() for node in self.nodes], extend=self.extender)

	def reverse(self):
		return self.__class__(list(reversed(self.nodes)), extend=None)

	def insert(self, index, value):
		self.nodes.insert(index, value)

	def append(self, index):
		self.nodes.append(index)

	def getPosition(self):
		return [(node.x, node.y) for node in self.nodes]

	def getCoord(self):
		from typerig.brain import Coord
		return [Coord(node) for node in self.nodes]

	def getBounds(self):
		from typerig.brain import bounds
		return bounds(self.getPosition())

	def shift(self, dx, dy):
		for node in self.nodes:
			node.shift(dx, dy)

	def smartShift(self, dx, dy):
		for node in self.nodes:
			node.smartShift(dx, dy)

	def applyTransform(self, transform):
		for node in self.nodes:
			try:
				node.fl.applyTransform(transform)
			except AttributeError:
				node.applyTransform(transform)

	def cloneTransform(self, transform):
		temp_container = self.clone()
		temp_container.applyTransform(transform)
		return temp_container

class pContour(object):
	'''Proxy to flContour object

	Constructor:
		pContour(flContour)

	Attributes:
		.fl (flContour): Original flContour 
	'''
	def __init__(self, contour):
		# - Properties
		self.fl = contour
		self.id = self.fl.id
		self.name = self.fl.name
		self.closed = self.fl.closed
		self.start = self.fl.first
		self.glyph = self.fl.glyph
		self.font = self.fl.font
		self.layer = self.fl.layer
		self.reversed = self.fl.reversed
		self.transform = self.fl.transform

		# - Functions
		self.bounds = lambda : self.fl.bounds # (xMin, yMin, xMax, yMax)
		self.x = lambda : self.bounds()[0]
		self.y = lambda : self.bounds()[1]
		self.width = lambda : self.bounds()[2] - self.bounds()[0]
		self.height  = lambda : self.bounds()[3] - self.bounds()[1]

		self.selection = lambda : self.fl.selection
		self.setStart = self.fl.setStartPoint
		self.segments = self.fl.segments
		self.nodes = self.fl.nodes
		self.update = self.fl.update
		self.applyTransform = self.fl.applyTransform
		self.shift = lambda dx, dy: self.fl.move(pqt.QtCore.QPointF(dx, dy))

	def __repr__(self):
		return '<%s (%s, %s) nodes=%s ccw=%s closed=%s>' % (self.__class__.__name__, self.x(), self.y(), len(self.nodes()), self.isCCW(), self.closed)

	def reverse(self):
		self.fl.reverse()

	def isCW(self):
		# FL has an error here or.... just misnamed the method?
		return not self.fl.clockwise

	def isCCW(self):
		return self.fl.clockwise

	def setCW(self):
		if not self.isCW(): self.reverse()

	def setCCW(self):
		if not self.isCCW(): self.reverse()

	def isAllSelected(self):
		'''Is the whole contour selected '''
		return all(self.selection())

	def translate(self, dx, dy):
		self.fl.transform = self.fl.transform.translate(dx, dy)
		self.fl.applyTransform()

	def scale(self, sx, sy):
		self.fl.transform = self.fl.transform.scale(dx, dy)
		self.fl.applyTransform()

	def slant(self, deg):
		from math import tan, radians
		self.fl.transform = self.fl.transform.shear(tan(radians(deg)), 0)
		self.fl.applyTransform()
		
	def rotate(self, deg):
		from math import tan, radians
		self.fl.transform = self.fl.transform.rotate(tan(radians(deg)))
		self.fl.applyTransform()
		

class pShape(object):
	'''Proxy to flShape, flShapeData and flShapeInfo objects

	Constructor:
		pShape(flShape)

	Attributes:
		.fl (flNode): Original flNode 
		.parent (flContour): parent contour
		.contour (flContour): parent contour
	'''
	def __init__(self, shape, layer=None, glyph=None):
		self.fl = shape
		self.shapeData = self.data()
		self.refs = self.shapeData.referenceCount
		self.container = self.includesList = self.fl.includesList
		
		self.currentName = self.fl.name
		self.name = self.shapeData.name

		self.bounds = lambda: self.fl.boundingBox
		self.x = lambda : self.bounds().x()
		self.y = lambda : self.bounds().y()
		self.width = lambda : self.bounds().width()
		self.height  = lambda : self.bounds().height()

		self.parent = glyph
		self.layer = layer

	def __repr__(self):
		return '<%s name=%s references=%s contours=%s contains=%s>' % (self.__class__.__name__, self.name, self.refs, len(self.contours()), len(self.container))

	# - Basics -----------------------------------------------
	def data(self):
		''' Return flShapeData Object'''
		return self.fl.shapeData

	def info(self):
		''' Return flShapeInfo Object'''
		pass

	def builder(self):
		''' Return flShapeBuilder Object'''
		return self.fl.shapeBuilder

	def container(self):
		''' Returns a list of flShape Objects that are contained within this shape.'''
		return self.fl.includesList

	def tag(self, tagString):
		self.data().tag(tagString)

	def isChanged(self):
		return self.data().hasChanges

	def update(self):
		return self.fl.update()

	# - Management ---------------------------------
	def setName(self, shape_name):
		self.data().name = shape_name

	# - Position, composition ---------------------------------
	def decompose(self):
		self.fl.decomposite()

	def goUp(self):
		return self.data().goUp()

	def goDown(self):
		return self.data().goDown()

	def goFrontOf(self, flShape):
		return self.data().sendToFront(flShape)

	def goBackOf(self, flShape):
		return self.data().sendToBack(flShape)

	def goLayerBack(self):
		if self.layer is not None:
			return self.goBackOf(self.layer.shapes[0])
		return False

	def goLayerFront(self):
		if self.layer is not None:
			return self.goFrontOf(self.layer.shapes[-1])
		return False

	# - Contours, Segmets, Nodes ------------------------------
	def segments(self):
		return self.data().segments

	def contours(self):
		return self.data().contours

	def nodes(self):
		return [node for contour in self.contours() for node in contour.nodes()]

	# - Complex shapes, builders and etc. ---------------------
	def copyBuilder(self, source):
		if isinstance(source, fl6.flShapeBuilder):
			self.fl.shapeBuilder = source.clone()
		elif isinstance(source, fl6.flShape):
			self.fl.shapeBuilder = source.flShapeBuilder.clone()

		self.fl.update()

	# - Transformation ----------------------------------------
	def reset_transform(self):
		temp_transform = self.fl.transform
		temp_transform.reset()
		self.fl.transform = temp_transform

	def shift(self, dx, dy, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.translate(dx, dy)

	def rotate(self, angle, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.rotate(angle)

	def scale(self, sx, sy, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.scale(sx, sy)

	def shear(self, sh, sv, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.shear(sh, sv)

	# - Pens -----------------------------------------------
	def draw(self, pen):
		''' Utilizes the Pen protocol'''
		for contour in self.fl.contours:
			contour.convertToFgContour(shape.fl_transform.transform).draw(pen)


class pGlyph(object):
	'''Proxy to flGlyph and fgGlyph combined into single entity.

	Constructor:
		pGlyph() : default represents the current glyph and current font
		pGlyph(flGlyph)
		pGlyph(fgFont, fgGlyph)
	
	Methods:

	Attributes:
		.parent (fgFont)
		.fg (fgGlyph)
		.fl (flGlyph)
		...
	'''

	def __init__(self, *argv):
		
		if len(argv) == 0:
			self.parent = fl6.CurrentFont()
			self.fg = fl6.CurrentGlyph()
			self.fl = fl6.flGlyph(fl6.CurrentGlyph(), fl6.CurrentFont())
		
		elif len(argv) == 1 and isinstance(argv[0], fl6.flGlyph):
			'''
			# - Kind of not working as the reslting glyph is detached (-1 orphan) from the fgFont
			self.fl = argv[0]
			self.fg = self.fl.fgGlyph
			self.parent = self.fl.fgPackage
			'''

			# - Alternate way - will use that way
			font, glyph = argv[0].fgPackage, argv[0].fgPackage[argv[0].name]
			self.parent = font
			self.fg = glyph
			self.fl = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[0], fgt.fgFont) and isinstance(argv[1], fgt.fgGlyph):
			font, glyph = argv
			self.parent = font
			self.fg = glyph
			self.fl = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[1], fgt.fgFont) and isinstance(argv[0], fgt.fgGlyph):
			glyph, font = argv
			self.parent = font
			self.fg = glyph
			self.fl = fl6.flGlyph(glyph, font)
			
		self.name = self.fg.name
		self.index = self.fg.index
		self.id = self.fl.id
		self.mark = self.fl.mark
		self.tags = self.fl.tags
		self.unicode = self.fg.unicode
		self.package = fl6.flPackage(self.fl.package)
		self.builders = {}

	def __repr__(self):
		return '<%s name=%s index=%s unicode=%s>' % (self.__class__.__name__, self.name, self.index, self.unicode)

	# - Basics -----------------------------------------------
	def version(self): return self.fl.lastModified

	def activeLayer(self): return self.fl.activeLayer

	def fg_activeLayer(self): return self.fg.layer

	def mask(self): return self.fl.activeLayer.getMaskLayer(True)

	def activeGuides(self): return self.fl.activeLayer.guidelines

	def mLine(self): return self.fl.measurementLine()

	def object(self): return fl6.flObject(self.fl.id)

	def italicAngle(self): return self.package.italicAngle_value

	def setMark(self, mark_color): self.fl.mark = mark_color; self.mark = self.fl.mark

	def nodes(self, layer=None, extend=None, deep=False):
		'''Return all nodes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer.
			extend (class): A class construct with extended functionality to be applied on every node.
		Returns:
			list[flNodes]
		'''
		# - Default
		layer_contours = self.contours(layer, deep=deep)

		if extend is None:
			return [node for contour in layer_contours for node in contour.nodes()]
		else:
			return [extend(node) for contour in layer_contours for node in contour.nodes()]

	def fg_nodes(self, layer=None):
		'''Return all FontGate nodes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[fgNodes]
		'''
		return sum([contour.nodes.asList() for contour in self.fg_contours(layer)], [])

	def contours(self, layer=None, deep=True, extend=None):
		'''Return all contours at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flContours]
		'''
		layer_contours = self.layer(layer).getContours()
		
		# - Dig deeper in grouped components and shapebuilders (filters)
		if deep:
			glyph_components = self.components(layer)

			if len(glyph_components):
				layer_contours = [contour for component in glyph_components for contour in component.contours]

		if extend is None:
			return layer_contours
		else:
			return [extend(contour) for contour in layer_contours]

	def fg_contours(self, layer=None):
		'''Return all FontGate contours at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[fgContours]
		'''
		return sum([shape.contours.asList() for shape in self.fg_shapes(layer)],[])

	def layers(self):
		'''Return all layers'''
		return self.fl.layers

	def fg_layers(self, asDict=False):
		'''Return all FotnGate layers'''
		return self.fg.layers if not asDict else {layer.name:layer for layer in self.fg.layers}

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

	def fg_layer(self, layer=None):
		'''Returns FontGate layer no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			fgLayer
		'''
		if layer is None:
			return self.fg.activeLayer
		else:
			if isinstance(layer, int):
				return self.fg.layers[layer]

			elif isinstance(layer, basestring):
				try:
					return self.fg_layers(True)[layer]
				except KeyError:
					return None

	def hasLayer(self, layerName):
		return True if self.fl.findLayer(layerName) is not None else False

	def fg_hasLayer(self, layerName):
		return self.fg.fgData().findLayer(layer)

	def shapes(self, layer=None, extend=None):
		'''Return all shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapes]
		'''
		if extend is None:
			return self.layer(layer).shapes
		else:
			return [extend(shape) for shape in self.layer(layer).shapes]

	def dereference(self, layer=None):
		'''Remove all shape references but leave components.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapes]
		'''
		wLayer = self.layer(layer)
		shapes = self.shapes(layer)
		components = self.containers(layer)
		only_shapes = [shape for shape in shapes if shape not in components]
		clones = [shape.cloneTopLevel() for shape in only_shapes]

		wLayer.removeAllShapes()
		for clone in clones: wLayer.addShape(clone)

		return clones

	def containers(self, layer=None, extend=None):
		'''Return all complex shapes that contain other shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapes]
		'''
		if extend is None:
			return [shape for shape in self.layer(layer).shapes if len(shape.includesList)]
		else:
			return [extend(shape) for shape in self.layer(layer).shapes if len(shape.includesList)]

	def decompose(self, layer=None):
		'''Decompose all complex shapes that contain other shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		for container in self.containers(layer):
			container.decomposite()

	def getBuilders(self, layer=None, store=False):
		shape_builders = {}

		for shape in self.shapes(layer):
			wBuilder = shape.shapeBuilder

			if wBuilder is not None and wBuilder.isValid:
				shape_builders.setdefault(wBuilder.title, []).append(wBuilder)

		if store: self.builders = shape_builders
		
		return shape_builders

	def addShape(self, shape, layer=None, clone=False):
		'''Add a new shape at given layer.
		Args:
			shape (flShape): Shape to be added
		Returns:
			flShape
		'''
		if clone:
			return self.layer(layer).addShape(shape.cloneTopLevel())
		else:
			return self.layer(layer).addShape(shape)

	def replaceShape(self, old_shape, new_shape, layer=None):
		'''Repalce a shape at given layer.
		Args:
			old_shape, new_shape (flShape): Shapes
			layer (str): Layer name
		Returns:
			None
		'''
		self.layer(layer).replaceShape(old_shape, new_shape)

	def removeShape(self, shape, layer=None, recursive=True):
		'''Remove a new shape at given layer.
		Args:
			old_shape, new_shape (flShape): Shapes
			layer (str): Layer name
			recursive (bool): 
		Returns:
			None
		'''
		self.layer(layer).removeShape(shape, recursive)

	def addShapeContainer(self, shapeList, layer=None, remove=True):
		'''Add a new shape container* at given layer.
		A flShape containing all of the shapes given that
		could be transformed to Shape-group or shape-filter.
		Args:
			shapeList list(flShape): List if Shapes to be grouped.
		Returns:
			flShape
		'''
		shape_container = fl6.flShape()

		if remove:
			shape_container.include(shapeList, self.layer(layer))
		else:
			shape_container.include(shapeList)

		return self.addShape(shape_container, layer, clone=False)

	def findShape(self, shapeName, layer=None):
		'''Finds shape by name on given layer
		Args:
			shapeName (str): Shape name
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			flShape or None
		'''
		for shape in self.shapes(layer):
			if shapeName == shape.shapeData.name:
				return shape
				
	def shapes_data(self, layer=None):
		'''Return all flShapeData objects at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapeData]
		'''
		return [shape.shapeData for shape in self.shapes(layer)]

	def fg_shapes(self, layer=None):
		'''Return all FontGate shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[fgShapes]
		'''
		activeLayer = self.fg_layer(layer)
		return [activeLayer[sid] for sid in range(activeLayer.countShapes())]

	# - Composite glyph --------------------------------------------
	# !!! Note: Too much nested loops revisit!
	
	def listGlyphComponents(self, layer=None, extend=None):
		'''Return all glyph components in glyph'''
		return [(shape, shape.includesList) for shape in self.shapes(layer, extend) if len(shape.includesList)]

	def listUnboundShapes(self, layer=None):
		'''Return all glyph shapes that are not glyph references or those belonging to the original (master) glyph'''
		return [shape for shape in self.shapes(layer) if self.package.isComponent(shape.shapeData)[0] is None or self.package.isComponent(shape.shapeData)[0] == self.fl]		

	def components(self, layer=None, extend=None):
		'''Return all glyph components besides glyph.'''
		return [comp for pair in self.listGlyphComponents(layer, extend) for comp in pair[1]]

	def getCompositionString(self, layer=None, legacy=True):
		'''Return glyph composition string for Generate Glyph command.'''
		comp_names = self.getCompositionNames(layer)

		if legacy:
			return '%s=%s' %('+'.join(comp_names[1:]), comp_names[0])

	def getCompositionNames(self, layer=None):
		'''Return name of glyph and the parts it is made of.'''
		return [self.name] + [shape.shapeData.name for shape in self.components(layer)]

	def getCompositionDict(self, layer=None, extend=None):
		'''Return composition dict of a glyph. Elements!'''
		return {shape.shapeData.name:shape for shape in self.components(layer, extend)}

	def getContainersDict(self, layer=None, extend=None):
		'''Return composition dict of a glyph. Composites!'''
		return {container.includesList[0].shapeData.name:container for container in self.containers(layer, extend)}	#TODO: Make it better! This references only first shape in container!

	# - Layers -----------------------------------------------------
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
			layer (flLayer or fgLayer)
			toBack (bool): Send layer to back
		Returns:
			None
		'''
		if isinstance(layer, fl6.flLayer):
			self.fl.addLayer(layer, toBack)

		elif isinstance(layer, fgt.fgLayer):
			self.fg.layers.append(layer)

	def removeLayer(self, layer):
		'''Removes a layer from glyph.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		self.fl.removeLayer(self.layer(layer))

	def duplicateLayer(self, layer=None, newLayerName='New Layer'):
		'''Duplicates a layer with new name and adds it to glyph's layers.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			toBack(bool): send to back
		Returns:
			flLayer
		'''
		options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': True}
		self.copyLayer(layer, newLayerName, options, True, True)

	def copyLayer(self, srcLayerName, dstLayerName, options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': True}, addLayer=False, cleanDST=True, toBack=True):
		'''Copies a layer within the glyph.
		Args:
			srcLayerName, dstLayerName (string): Source and destination layer names
			options (dict): Copy Options as follows {'out': Outline, 'gui': Guidelines, 'anc': Anchors, 'lsb': LSB, 'adv': Advance, 'rsb': RSB, 'lnk': Linked metrics, 'ref': References}, addLayer=False):
			addLayer (bool): Create a new layer
			cleanDST (bool): Clean destination layer
			toBack (bool): Add layer to back of the layer stack
		Returns:
			flLayer
		'''
		# - Init
		srcLayer = self.layer(srcLayerName)
		
		# -- Create new layer
		newLayer = fl6.flLayer()
		newLayer.name = str(dstLayerName)

		# -- Assign same styling
		newLayer.advanceHeight = srcLayer.advanceHeight
		newLayer.advanceWidth = srcLayer.advanceWidth
		newLayer.wireframeColor = srcLayer.wireframeColor
		newLayer.mark = srcLayer.mark
		newLayer.assignStyle(srcLayer)

		if self.layer(dstLayerName) is None and addLayer:
			# -- Add to glyph
			self.addLayer(newLayer, toBack)

		# -- Outline
		if options['out']:
			# --- Get shapes
			srcShapes = self.shapes(srcLayerName)

			# --- Cleanup destination layers
			if cleanDST:
				self.layer(dstLayerName).removeAllShapes()
			
			# --- Copy/Paste shapes
			for shape in srcShapes:
				if addLayer:
					newShape = self.layer(dstLayerName).addShape(shape.cloneTopLevel())
				else:
					newLayer.addShape(shape.cloneTopLevel())

		if addLayer: # Ugly!!! Refactor!
			# -- Metrics
			if options['lsb']: 
				self.setLSB(self.getLSB(srcLayerName), dstLayerName)
			
			if options['adv']: 
				self.setAdvance(self.getAdvance(srcLayerName), dstLayerName)
			
			if options['rsb']: 
				self.setRSB(self.getRSB(srcLayerName), dstLayerName)

			if options['lnk']:
				self.setLSBeq(self.getSBeq(srcLayerName)[0], dstLayerName)
				self.setRSBeq(self.getSBeq(srcLayerName)[1], dstLayerName)

			# -- Anchors
			if options['anc']:
				if cleanDST:
					self.clearAnchors(dstLayerName)

				for src_anchor in self.anchors(srcLayerName):
					self.addAnchor((src_anchor.point.x(), src_anchor.point.y()), src_anchor.name, dstLayerName)

		return newLayer

	def isCompatible(self, strong=False):
		'''Test if glyph is ready for interpolation - all master layers are compatible.'''
		from itertools import combinations
		glyph_masters = self.masters()
		layer_pairs = combinations(glyph_masters, 2)
		return all([layerA.isCompatible(layerB, strong) for layerA, layerB in layer_pairs])

	def isMixedReference(self):
		'''Test if glyph has mixed references - components on some layers and referenced shapes on others'''
		'''
		from itertools import combinations
		glyph_masters = self.masters()
		layer_pairs = combinations(glyph_masters, 2)
		return not all([len(self.components(layerA.name))==len(self.components(layerB.name)) for layerA, layerB in layer_pairs])
		'''
		#!!! Far simpler code
		master_components_count = []
		for layer in self.fl.layers:
			if layer.isMasterLayer:
				pShapes = layer.shapes
				counter = 0
				if len(pShapes):
					for shape in pShapes:
						counter += len(shape.includesList)

				master_components_count.append(counter)

		return not len(set(master_components_count)) == 1	
			
	def reportLayerComp(self, strong=False):
		'''Returns a layer compatibility report'''
		from itertools import combinations
		return [(layerA.name, layerB.name, layerA.isCompatible(layerB, strong)) for layerA, layerB in combinations(self.layers(), 2)]

	# - Update ----------------------------------------------
	def update(self, fl=True, fg=False):
		'''Updates the glyph and sends notification to the editor.
		Args:
			fl (bool): Update the flGlyph
			fg (bool): Update the fgGlyph
		'''
		# !TODO: Undo?
		if fl:self.fl.update()
		if fg:self.fg.update()
	
	def updateObject(self, flObject, undoMessage='TypeRig', verbose=True):
		'''Updates a flObject sends notification to the editor as well as undo/history item.
		Args:
			flObject (flGlyph, flLayer, flShape, flNode, flContour): Object to be update and set undo state
			undoMessage (string): Message to be added in undo/history list.'''
		
		# - General way ---- pre 6774 worked fine!
		fl6.flItems.notifyChangesApplied(undoMessage[:20], flObject, True)
		if verbose: print 'DONE:\t%s' %undoMessage
		
		# - New from 6774 on
		for contour in self.contours():
			contour.changed()
		
		fl6.flItems.notifyPackageContentUpdated(self.fl.fgPackage.id)
		#fl6.Update()
		
		'''# - Type specific way 
		# -- Covers flGlyph, flLayer, flShape
		if isinstance(flObject, fl6.flGlyph) or isinstance(flObject, fl6.flLayer) or isinstance(flObject, fl6.flShape):
			fl6.flItems.notifyChangesApplied(undoMessage, flObject, True)
		
		# -- Covers flNode, flContour, (flShape.shapeData)
		elif isinstance(flObject, fl6.flContour) or isinstance(flObject, fl6.flNode):
			fl6.flItems.notifyChangesApplied(undoMessage, flObject.shapeData)
		'''

	# - Glyph Selection -----------------------------------------------
	def selectedNodesOnCanvas(self, filterOn=False):
		from typerig.proxy import pWorkspace
		workspace = pWorkspace()
		allNodes = workspace.getSelectedNodes()

		if not filterOn:
			return [allNodes.index(node) for node in allNodes if node.selected]
		else:
			return [allNodes.index(node) for node in allNodes if node.selected and node.isOn()]

	def selectedNodeIndices(self, filterOn=False, deep=False):
		'''Return all indices of nodes selected at current layer.
		Args:
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[int]
		'''
		allNodes = self.nodes(deep=deep)

		if not filterOn:
			return [allNodes.index(node) for node in allNodes if node.selected]
		else:
			return [allNodes.index(node) for node in allNodes if node.selected and node.isOn()]
	
	def selected(self, filterOn=False, deep=False):
		'''Return all selected nodes indexes at current layer.
		Args:
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[int]
		'''
		return self.selectedNodeIndices(filterOn, deep)

	def selectedNodes(self, layer=None, filterOn=False, extend=None, deep=False):
		'''Return all selected nodes at given layer.
		Args:
			filterOn (bool): Return only on-curve nodes
			extend (class): A class construct with extended functionality to be applied on every node.
		Returns:
			list[flNode]
		'''
		return [self.nodes(layer, extend, deep)[nid] for nid in self.selectedNodeIndices(filterOn, deep)]
		#return [node for node in self.nodes(layer, extend, deep) if node.selected]

	def nodesForIndices(self, indices, layer=None, filterOn=False, extend=None, deep=False):
		return [self.nodes(layer, extend, deep)[nid] for nid in indices]
	
	def selectedAtContours(self, index=True, layer=None, filterOn=False, deep=False):	
		'''Return all selected nodes and the contours they rest upon at current layer.
		Args:
			index (bool): If True returns only indexes, False returns flContour, flNode
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[tuple(int, int)]: [(contourID, nodeID)..()] or 
			list[tuple(flContour, flNode)]
		'''
		allContours = self.contours(layer)
		
		if index:
			return [(allContours.index(node.contour), node.index) for node in self.selectedNodes(layer, filterOn, deep=deep)]
		else:
			return [(node.contour, node) for node in self.selectedNodes(layer, filterOn, deep=deep)]

	def selectedAtShapes(self, index=True, filterOn=False, layer=None, deep=False):
		'''Return all selected nodes and the shapes they belong at current layer.
		Args:
			index (bool): If True returns only indexes, False returns flShape, flNode
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[tuple(int, int)]: [(shapeID, nodeID)..()] or
			list[tuple(flShape, flNode)]

		!TODO: Make it working with layers as selectedAtContours(). This is legacy mode so other scripts would work!
		'''
		allContours = self.contours(layer=layer, deep=deep)
		allShapes = self.shapes(layer) if not deep else self.components(layer)

		if index:
			return [(allShapes.index(shape), allContours.index(contour), node.index) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(layer=layer, filterOn=filterOn, deep=deep)]
		else:
			return [(shape, contour, node) for shape in allShapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(layer=layer, filterOn=filterOn, deep=deep)]

	def selectedShapeIndices(self, select_all=False, deep=False):
		'''Return all indices of nodes selected at current layer.
		Args:
			select_all (bool): True all nodes on Shape should be selected. False any node will do.
		Returns:
			list[int]
		'''
		selection_mode = ['AnyNodeSelected', 'AllContourSelected'][select_all]
		allShapes = self.shapes() if not deep else self.components()

		return [allShapes.index(shape) for shape in allShapes if shape.hasSelected(selection_mode)]
		

	def selectedShapes(self, layer=None, select_all=False, deep=False, extend=None):
		'''Return all shapes that have a node selected.
		'''
		selection_mode = ['AnyNodeSelected', 'AllContourSelected'][select_all]
		allShapes = self.shapes(layer) if not deep else self.components(layer)

		if extend is None:
			return [allShapes[sid] for sid in self.selectedShapeIndices(select_all, deep)]
		else:
			return [extend(allShapes[sid]) for sid in self.selectedShapeIndices(select_all, deep)]

	def selectedCoords(self, layer=None, filterOn=False, applyTransform=False):
		'''Return the coordinates of all selected nodes at the current layer or other.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			filterOn (bool): Return only on-curve nodes
			applyTransform (bool) : Gets local shape transformation matrix and applies it to the node coordinates
		Returns:
			list[QPointF]
		'''
		pLayer = self.layer(layer)
		
		if not applyTransform:
			nodelist = self.selectedAtContours(filterOn=filterOn, deep=False)
			#return [pLayer.getContours()[item[0]].nodes()[item[1]].position for item in nodelist]
			return [self.contours(layer)[cid].nodes()[nid].position for cid, nid in nodelist]

		else:
			nodelist = self.selectedAtShapes(filterOn=filterOn, deep=False)
			#return [pLayer.getShapes(1)[item[0]].transform.map(pLayer.getContours()[item[1]].nodes()[item[2]].position) for item in nodelist]
			return [self.shapes(layer)[sid].transform.map(self.contours(layer)[cid].nodes()[nid].position) for sid, cid, nid in nodelist]

	def selectedSegments(self, layer=None):
		'''Returns list of currently selected segments
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		return [self.contours(layer)[cID].segment(self.mapNodes2Times(layer)[cID][nID]) for cID, nID in self.selectedAtContours()]

	def findNode(self, nodeName, layer=None):
		'''Find node by name/tag'''
		return self.layer(layer).findNode(nodeName)

	def findNodeCoords(self, nodeName, layer=None):
		'''Find node coordinates by name/tag'''
		temp = self.findNode(nodeName, layer)
		if temp is not None: return temp[1]

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
				countOn += node.isOn() # Hack-ish but working
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
		
		#nodes = self.nodes(layer)
		nodes = self.contours(layer)[cID].nodes()
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
			#self.contours(layer)[cID].updateIndices()

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

	def getBounds(self, layer=None):
		'''Get Glyph's Boundig Box at given layer (int or str). Returns QRectF.'''
		return self.layer(layer).boundingBox

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

	def setLSBeq(self, equationStr, layer=None):
		'''Set LSB metric equation on given layer'''
		self.layer(layer).metricsLeft = equationStr

	def setRSBeq(self, equationStr, layer=None):
		'''Set RSB metric equation on given layer'''
		self.layer(layer).metricsRight = equationStr

	def setADVeq(self, equationStr, layer=None):
		'''Set Advance width metric equation on given layer'''
		self.layer(layer).metricsWidth = equationStr

	def getSBeq(self, layer=None):
		'''GET LSB, RSB metric equations on given layer'''
		return self.layer(layer).metricsLeft, self.layer(layer).metricsRight

	def fontMetricsInfo(self, layer=None):
		'''Returns Font(layer) metrics no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			FontMetrics (object)
		'''
		if layer is None:
			return fl6.FontMetrics(self.package, self.fl.activeLayer.name)
		else:
			if isinstance(layer, int):
				return fl6.FontMetrics(self.package, self.fl.layers[layer].name) 

			elif isinstance(layer, basestring):
				return fl6.FontMetrics(self.package, layer)

	# - Anchors and pins -----------------------------------------------
	def anchors(self, layer=None):
		# BUGFIX FL7 build 7234
		'''Return list of anchors (list[flAnchor]) at given layer (int or str)'''
		# Shouls work but it is not....
		# return self.layer(layer).anchors 
		
		# So a workaround:
		work_layer = self.layer(layer)
		anchor_names = [obj.name for obj in work_layer.anchors]
		anchors = [work_layer.findAnchor(name) for name in anchor_names]
		return anchors

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
		
		self.layer(layer).addAnchor(newAnchor)

	def newAnchor(self, coordTuple, name, anchorType=1):
		'''	
		Not working
		'''
		newAnchor = fl6.flPinPoint(pqt.QtCore.QPointF(*coordTuple), anchorType)
		newAnchor.name = name
		
		return newAnchor

	def clearAnchors(self, layer=None):
		'''Remove all anchors at given layer (int or str)'''
		return self.layer(layer).clearAnchors()

	def findAnchor(self, anchorName, layer=None):
		'''Find anchor by name/tag'''
		return self.layer(layer).findAnchor(anchorName)

	def findAnchorCoords(self, anchorName, layer=None):
		'''Find anchor coordinates by name/tag '''
		temp = self.findAnchor(anchorName, layer=None)
		if temp is not None: return temp.point

	# - Guidelines -----------------------------------------------
	def guidelines(self, layer=None):
		'''Return list of guidelines (list[flGuideline]) at given layer (int or str)'''
		return self.layer(layer).guidelines

	def addGuideline(self, coordTuple, layer=None, angle=0, name='', tag='', color='darkMagenta', style='gsGlyphGuideline'):
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
		newGuideline.color = pqt.QtGui.QColor(color)
		newGuideline.style = style
		newGuideline.tag(tag.replace(' ', '').split(','))
			
		self.layer(layer).appendGuidelines([newGuideline])

	# - Tags ------------------------------------------------------
	def getTags(self):
		return self.fl.tags

	def setTags(self, tagList, append=True):
		if append:
			old_tags = self.getTags()
			self.fl.tags = sorted(old_tags + tagList)
		else:
			self.fl.tags = tagList

	def tag(self, newTag):
		self.setTags([newTag], True)

	# - Pens -----------------------------------------------
	def draw(self, pen, layer=None):
		''' Utilizes the Pen protocol'''
			
		for shape in self.shapes(layer):
			for contour in shape.contours:
				contour.convertToFgContour(shape.fl_transform.transform).draw(pen)

		'''
		for anchor in self.anchors(layer):
			anchor.draw(pen)

		for component in self.components(layer):
			component.draw(pen)

		'''


class pFontMetrics(object):
	'''
	An Abstract Font Metrics getter/setter of a flPackage.

	Constructor:
		pFontMetrics() - default represents the current glyph and current font
		pFontMetrics(flPackage)
	
	'''
	def __init__(self, font):
		self.fl = font
		
	# - Getters
	def getAscender (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.ascender_value

	def getCapsHeight (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.capsHeight_value

	def getDescender (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.descender_value

	def getLineGap (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.lineGap_value

	'''
	def getUpm (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.upm
	'''

	def getXHeight (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.xHeight_value

	def getItalicAngle (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.italicAngle_value

	def getCaretOffset (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.caretOffset_value

	'''
	cornerTension_value
	curveTension_value
	inktrapLen_value
	measurement_value
	underlinePosition_value
	underlineThickness_value
	'''

	# - Setters
	def setAscender (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.ascender_value = value

	def setCapsHeight (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.capsHeight_value = value

	def setDescender (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.descender_value = value

	def setLineGap (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.lineGap_value = value

	'''
	def setUpm (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.upm = value
	'''

	def setXHeight (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.xHeight_value = value

	def setItalicAngle (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.italicAngle_value = value

	def setCaretOffset (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.caretOffset_value = value

	# - Export & Import
	def asDict(self, layer=None):
		# - Genius!!!!
		getterFunctions = [func for func in dir(self) if callable(getattr(self, func)) and not func.startswith("__") and 'get' in func]
		return {getter.replace('get',''):getattr(self, getter)(layer) for getter in getterFunctions} 

	def fromDict(self, metricDict, layer=None):
		for func, value in metricDict.iteritems():
			eval("self.set%s(%s, '%s')" %(func, value, layer))


class pFont(object):
	'''
	A Proxy Font representation of Fonlab fgFont and flPackage.

	Constructor:
		pFont(None) : Default represents the current glyph and current font
		pFont(fgFont) : Creates a pFont object from FontGate fgFont object
		pFont(file_path) : Loats a existing font form file_path (str) and creates a pFont object
	
	'''

	def __init__(self, font=None):

		if font is not None:
			if isinstance(font, fgt.fgFont):
				self.fg = font
				self.fl = fl6.flPackage(font)

			elif isinstance(font, basestring):
				fl6.flItems.requestLoadingFont(font)
				self.fg = fl6.CurrentFont()
				self.fl = fl6.flPackage(fl6.CurrentFont())
			
		else:
			self.fg = fl6.CurrentFont()
			self.fl = fl6.flPackage(fl6.CurrentFont())

		# - Basics
		self.italic_angle = self.getItalicAngle()
		self.info = self.fg.info
		self.familyName = self.info.familyName
		self.name = self.familyName # Change later
		self.OTfullName = self.info.openTypeNameCompatibleFullName
		self.PSfullName = self.info.postscriptFullName
		self.path = self.fg.path

		# - Special 
		self.__altMarks = {'liga':'_', 'alt':'.', 'hide':'__'}
		self.__diactiricalMarks = ['grave', 'dieresis', 'macron', 'acute', 'cedilla', 'uni02BC', 'circumflex', 'caron', 'breve', 'dotaccent', 'ring', 'ogonek', 'tilde', 'hungarumlaut', 'caroncomma', 'commaaccent', 'cyrbreve'] # 'dotlessi', 'dotlessj'
		self.__specialGlyphs = ['.notdef', 'CR', 'NULL', 'space', '.NOTDEF']
		self.__kern_group_type = {'L':'KernLeft', 'R':'KernRight', 'B': 'KernBothSide'}
		self.__kern_pair_mode = ('glyphMode', 'groupMode')
		
		# - Design space related
		self.pMasters = self.pMasters(self)
		self.pSpace = self.pDesignSpace(self)
	
	def __repr__(self):
		return '<%s name=%s glyphs=%s path=%s>' % (self.__class__.__name__, self.fg.info.familyName, len(self.fg), self.fg.path)

	# Classes ----------------------------------------------------
	class pMasters(object):
	# -- Aliasing some master related commands in common group
		def __init__(self, parent):
			self.add = parent.fl.addMaster
			self.clear = parent.fl.clearMasters
			self.container = parent.fl.mastersContainer
			self.count = parent.fl.mastersCount
			self.default = parent.fl.defaultMaster
			self.has = parent.fl.hasMaster
			self.isActive = parent.fl.can_interpolate
			self.locate = parent.fl.location
			self.names = parent.fl.masters
			self.remove = parent.fl.removeMaster
			self.rename = parent.fl.renameMaster
			self.setActive = parent.fl.set_interpolate
			self.setLocation = parent.fl.setLocation
			self.setMaster = parent.fl.setMaster

		def __repr__(self):
			return '<%s masters=%s>' % (self.__class__.__name__, ';'.join(self.names))

	class pDesignSpace(object):
	# -- Aliasing some axis related commands
		def __init__(self, parent):
			self.add = parent.fl.addAxis
			self.axes = parent.fl.axes
			self.prepare = parent.fl.prepareAxes
			
		def __repr__(self):
			return '<%s axes=%s>' % (self.__class__.__name__, ';'.join([axis.name for axis in self.axes]))

	# Functions ---------------------------------------------------
	# - Font Basics -----------------------------------------------
	def getSelectedIndices(self):
		# WARN: Legacy syntax used, as of current 6722 build there is no way to get the selected glyphs in editor
		return [index for index in range(len(legacy.fl.font)) if legacy.fl.Selected(index)]

	def setSelectedIndices(self, indList):
		# WARN: Legacy syntax used, as of current 6722 build there is no way to get the selected glyphs in editor
		for index in indList:
			legacy.fl.Select(index)

	def selectGlyphs(self, glyphNameList):
		for glyphName in glyphNameList:
			if self.fg.has_key(glyphName):
				legacy.fl.Select(self.fg[glyphName].index)

	def unselectAll(self):
		legacy.fl.Unselect()

	def selected_pGlyphs(self):
		'''Return TypeRig proxy glyph object for each selected glyph'''
		selection = self.getSelectedIndices()
		return self.pGlyphs(self.selectedGlyphs()) if len(selection) else []

	def selectedGlyphs(self, extend=None):
		'''Return TypeRig proxy glyph object for each selected glyph'''
		selection = self.getSelectedIndices()
		return self.glyphs(selection, extend) if len(selection) else []
		
	def glyph(self, glyph, extend=None):
		'''Return TypeRig proxy glyph object (pGlyph) by index (int) or name (str).'''
		if isinstance(glyph, int) or isinstance(glyph, basestring):
			return pGlyph(self.fg, self.fg[glyph]) if extend is None else extend(self.fg, self.fg[glyph])
		else:
			return pGlyph(self.fg, glyph) if extend is None else extend(self.fg, self.fg[glyph])

	def symbol(self, gID):
		'''Return fgSymbol by glyph index (int)'''
		return fl6.fgSymbol(gID, self.fg)

	def glyphs(self, indexList=[], extend=None):
		'''Return list of FontGate glyph objects (list[fgGlyph]).'''
		if extend is None:
			return self.fg.glyphs if not len(indexList) else [self.fg.glyphs[index] for index in indexList]
		else:
			if not len(indexList):
				return [extend(glyph, self.fg) for glyph in self.fg.glyphs]
			else:
				return [extend(glyph, self.fg) for glyph in [self.fg.glyphs[index] for index in indexList]]

	def symbols(self):
		'''Return list of FontGate symbol objects (list[fgSymbol]).'''
		return [self.symbol(gID) for gID in range(len(self.fg.glyphs))]
	
	def pGlyphs(self, fgGlyphList=[]):
		'''Return list of TypeRig proxy Glyph objects glyph objects (list[pGlyph]).'''
		return [self.glyph(glyph) for glyph in self.fg] if not len(fgGlyphList) else [self.glyph(glyph) for glyph in fgGlyphList]

	def findShape(self, shapeName, master=None):
		'''Search for element (flShape) in font and return it'''
		for glyph in self.pGlyphs():
			foundShape = glyph.findShape(shapeName, master)
			if foundShape is not None:
				return foundShape

	# - Font metrics -----------------------------------------------
	def getItalicAngle(self):
		return self.fl.italicAngle_value

	def fontMetricsInfo(self, layer):
		'''Returns Font(layer) metrics no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			FontMetrics (object)
		'''
		if isinstance(layer, int):
			return fl6.FontMetrics(self.fl, self.fl.masters[layer]) 

		elif isinstance(layer, basestring):
			return fl6.FontMetrics(self.fl, layer)

	def fontMetrics(self):
		'''Returns pFontMetrics Object with getter/setter functionality'''
		from typerig.proxy import pFontMetrics
		return pFontMetrics(self.fl)

	def updateObject(self, flObject, undoMessage='TypeRig', verbose=True):
		'''Updates a flObject sends notification to the editor as well as undo/history item.
		Args:
			flObject (flGlyph, flLayer, flShape, flNode, flContour): Object to be update and set undo state
			undoMessage (string): Message to be added in undo/history list.
		'''
		fl6.flItems.notifyChangesApplied(undoMessage, flObject, True)
		if verbose: print 'DONE:\t%s' %undoMessage

	def update(self):
		self.updateObject(self.fl, verbose=False)

	# - Axes and MM ----------------------------------------------------
	def axes(self):
		return self.fl.axes

	def masters(self):
		return self.fl.masters

	def hasMaster(self, layerName):
		return self.fl.hasMaster(layerName)

	def instances(self):
		return self.fl.instances

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

	def getZones(self, layer=None, HintingDataType=0):
		'''Returns font alignment (blue) zones (list[flGuideline]). Note: HintingDataType = {'HintingPS': 0, 'HintingTT': 1}'''
		backMasterName = self.fl.master
		if layer is not None: self.fl.setMaster(layer)
		zoneQuery = (self.fl.zones(HintingDataType, True), self.fl.zones(HintingDataType, False)) # tuple(top, bottom) zones
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)	
		return zoneQuery

	def setZones(self, fontZones, layer=None):
		backMasterName = self.fl.master

		if layer is not None: self.fl.setMaster(layer)
		self.fl.convertZonesToGuidelines(*fontZones) # Dirty register zones	
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)

		self.update()

	def zonesToTuples(self, layer=None, HintingDataType=0):
		fontZones = self.getZones(layer, HintingDataType)
		return [(zone.position, zone.width, zone.name) for zone in fontZones[0]] + [(zone.position, -zone.width, zone.name) for zone in fontZones[1]]

	def zonesFromTuples(self, zoneTupleList, layer=None, forceNames=False):
		fontZones = ([], [])

		for zoneData in zoneTupleList:
			isTop = zoneData[1] >= 0
			newZone = fl6.flZone(zoneData[0], abs(zoneData[1]))
			
			if forceNames and len(zoneData) > 2: newZone.name = zoneData[2]
			newZone.guaranteeName(isTop)
			
			fontZones[not isTop].append(newZone)

		if not len(fontZones[1]):
			fontZones[1].append(fl6.flZone())

		self.setZones(fontZones, layer)

	def addZone(self, position, width, layer=None):
		''' A very dirty way to add a new Zone to Font'''
		isTop = width >= 0
		backMasterName = self.fl.master
		fontZones = self.getZones(layer)
		
		newZone, killZone = fl6.flZone(position, abs(width)), fl6.flZone()
		newZone.guaranteeName(isTop)

		fontZones[not isTop].append([newZone, killZone][not isTop])
		fontZones[isTop].append([newZone, killZone][isTop])
				
		if layer is not None: self.fl.setMaster(layer)
		self.fl.convertZonesToGuidelines(*fontZones)
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)	

		self.update()
		
	def hinting(self):
		'''Returns fonts hinting'''
		return self.fg.hinting

	# - Charset -----------------------------------------------
	# -- Return Names
	def getGlyphNames(self):
		return [glyph.name for glyph in self.glyphs()]

	def getGlyphNameDict(self):
		# -- Init
		nameDict = {}

		# --- Controls and basic latin: 0000 - 0080
		nameDict['Latin_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin 1 Supplement: 0080 - 00FF
		nameDict['Latin1_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin1_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin A: unicode range 0100 - 017F
		nameDict['LatinA_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinA_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin B: unicode range 0180 - 024F
		nameDict['LatinB_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinB_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Cyrillic: unicode range 0400 - 04FF
		nameDict['Cyrillic_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Cyrillic_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]
		
		return nameDict

	def getGlyphUnicodeDict(self, encoding='utf-8'):
		# -- Init
		nameDict = {}

		# --- Controls and basic latin: 0000 - 0080
		nameDict['Latin_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin 1 Supplement: 0080 - 00FF
		nameDict['Latin1_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin1_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin A: unicode range 0100 - 017F
		nameDict['LatinA_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinA_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin B: unicode range 0180 - 024F
		nameDict['LatinB_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinB_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Cyrillic: unicode range 0400 - 04FF
		nameDict['Cyrillic_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Cyrillic_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]
		
		return nameDict	
	
	# -- Return Glyphs
	def uppercase(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isupper()] # Skip Private ranges - glyph.unicode < 10000

	def lowercase(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).islower()]		

	def figures(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isdigit()]	

	def symbols(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and not unichr(glyph.unicode).isdigit() and not unichr(glyph.unicode).isalpha()]

	def ligatures(self, namesOnly=False):
		'''Returns all ligature characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if self.__altMarks['liga'] in glyph.name and not self.__altMarks['hide'] in glyph.name and glyph.name not in self.__specialGlyphs]

	def alternates(self, namesOnly=False):
		'''Returns all alternate characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if self.__altMarks['alt'] in glyph.name and not self.__altMarks['hide'] in glyph.name and glyph.name not in self.__specialGlyphs]

	# - Glyph generation ------------------------------------------
	def addGlyph(self, glyph):
		'''Adds a Glyph (fgGlyph or flGlyph) to font'''
		if isinstance(glyph, fgt.fgGlyph):
			glyph = fl6.flGlyph(glyph)
		
		self.fl.addGlyph(glyph)

	def addGlyphList(self, glyphList):
		'''Adds a List of Glyphs [fgGlyph or flGlyph] to font'''
		for glyph in glyphList:
			self.addGlyph(glyph)

	def newGlyph(self, glyph_name, layers=[], unicode_int=None):
		'''Creates new glyph and adds it to the font'''
		# - Build
		base_glyph = fl6.flGlyph()
		base_glyph.name = glyph_name
		self.addGlyph(base_glyph)

		# - Get the newly added glyph (all sane methods exhausted)
		new_glyph = self.glyph(glyph_name)

		# - Set Unicode
		if unicode_int is not None: new_glyph.fg.setUnicode(unicode_int)
		
		# - Add layers
		if len(layers):
			for layer in layers:
				if isinstance(layer, basestring):
					new_layer = fl6.flLayer()
					new_layer.name = layer
					new_glyph.addLayer(new_layer)
				
				elif isinstance(layer, fl6.flLayer):
					new_glyph.addLayer(layer)

		# - Add to font
		return new_glyph

	def newGlyphFromRecipe(self, glyph_name, recipe, layers=[], unicode_int=None, rtl=False):
		''' Generate new glyph (glyph_name) using String Recipe (recipe)'''		
		
		# - Prepare
		advanceWidth = 0 #!!! Figure it out later
		prepared_layers = []

		for layer_name in layers:
			layer_fontMetrics = fl6.FontMetrics(self.fl, layer_name)
			new_layer = fl6.flLayer(layer_name)
			gen_component = self.fl.generateGlyph(recipe, layer_name, layer_fontMetrics, rtl)
			new_layer.setGlyphComponents(gen_component, advanceWidth, self.fl, True)
			prepared_layers.append(new_layer)

		new_glyph = self.newGlyph(glyph_name, prepared_layers, unicode_int)
		return new_glyph

	def duplicateGlyph(self, src_name, dst_name, dst_unicode=None):
		src_glyph = self.glyph(src_name)
		options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': True}
		prepared_layers = [src_glyph.copyLayer(layer.name, layer.name, options, False, False) for layer in src_glyph.layers()]

		new_glyph = self.newGlyph(dst_name, prepared_layers, dst_unicode)
		return new_glyph

	# - Information -----------------------------------------------
	def info(self):
		return self.info

	# - OpenType and features -------------------------------------
	def getFeatures(self):
		return self.fg.features

	def clearFeatures(self):
		return self.fg.features.clear()

	def getFeatureTags(self):
		return self.fg.features.keys()

	def getFeaPrefix(self):
		return self.fg.features.get_prefix()

	def setFeaPrefix(self, feaString):
		return self.fg.features.get_prefix(feaString)

	def hasFeature(self, tag):
		return self.fg.features.has_key(tag)

	def getFeature(self, tag):
		return self.fg.features.get_feature(tag)

	def setFeature(self, tag, feaString):
		return self.fg.features.set_feature(tag, feaString)

	def delFeature(self, tag):
		return self.fg.features.remove(tag)

	def newOTgroup(self, groupName, glyphList):
		return fgt.fgGroup(groupName, glyphList,'FeaClassGroupMode', 'mainglyphname')

	def addOTgroup(self, groupName, glyphList):
		temp_groups = self.fg.groups.asDict()
		new_group = self.newOTgroup(groupName, glyphList)
		temp_groups[groupName] = new_group
		self.fg.groups.fromDict(temp_groups)

	def getOTgroups(self):
		return self.fg.groups

	# - Kerning and Groups -------------------------------------
	def kerning(self, layer=None):
		'''Return the fonts kerning object (fgKerning) no matter the reference.'''
		if layer is None:
			return self.fl.kerning()
		else:
			if isinstance(layer, int):
				return self.fl.kerning(self.masters[layer])

			elif isinstance(layer, basestring):
				return self.fl.kerning(layer)

	def kerning_to_list(self, layer=None):
		# Structure:
		# 	fgKerning{fgKernigPair(fgKerningObject(glyph A, mode), fgKerningObject(glyph B, mode)) : kern value, ...}
		layer_kernig = self.kerning(layer)
		kern_list = []

		for key, value in layer_kernig.asDict().iteritems():
			kern_list.append([[item.asTuple() for item in key.asTuple()], value])

		return kern_list

	def kerning_groups(self, layer=None):
		'''Return the fonts kerning groups object (fgKerningGroups) no matter the reference.'''
		return self.kerning(layer).groups

	def fl_kerning_groups(self, layer=None):
		return list(filter(lambda x: x[0], self.fl.getAllGroups()))

	def fl_kerning_groups_to_dict(self, layer=None):
		from typerig.brain import extBiDict
		return extBiDict({item[1]: item[-1] for item in self.fl_kerning_groups(layer)})

	def kerning_groups_to_dict(self, layer=None):
		# - Semi working fixup of Build 6927 Bug
		kerning_groups = self.kerning_groups(layer)
		return {key: (list(set(kerning_groups[key][0])), kerning_groups[key][1]) for key in kerning_groups.keys()}

	def dict_to_kerning_groups (self, groupDict, layer=None):
		# - Build Group kerning from dictionary
		kerning_groups = self.kerning_groups(layer)
		
		for key, value in groupDict.iteritems():
			kerning_groups[key] = value

	def reset_kerning_groups(self, layer=None):
		# - Delete all group kerning at given layer
		self.kerning_groups(layer).clear()		

	def add_kerning_group(self, key, glyphNameList, type, layer=None):
		'''Adds a new group to fonts kerning groups.
		Args:
			key (string): Group name
			glyphNameList (list(string)): List of glyph names
			type (string): Kern group types: L - Left group (1st), R - Right group (2nd), B - Both (1st and 2nd)
			layer (None, Int, String)
		
		Returns:
			None
		'''
		self.kerning_groups(layer)[key] = (glyphNameList, self.__kern_group_type[type.upper()])

	def remove_kerning_group(self, key, layer=None):
		'''Remove a group from fonts kerning groups at given layer.'''
		del self.kerning_groups(layer)[key]

	def rename_kerning_group(self, oldkey, newkey, layer=None):
		'''Rename a group in fonts kerning groups at given layer.'''
		self.kerning_groups(layer).rename(oldkey, newkey)

	def newKernPair(self, glyphLeft, glyphRight, modeLeft, modeRight):
		if not isinstance(modeLeft, str): modeLeft = self.__kern_pair_mode[modeLeft]
		if not isinstance(modeRight, str): modeRight = self.__kern_pair_mode[modeRight]
		return fgt.fgKerningObjectPair(glyphLeft, glyphRight, modeLeft, modeRight)


class pKerning(object):
	'''Proxy to fgKerning object

	Constructor:
		pKerning(fgKerning)

	Attributes:
		.fg (fgKerning): Original Fontgate Kerning object 
		.groups (fgKerningGroups): Fontgate Group kerning object
	'''
	def __init__(self, fgKerningObject, externalGroupData=None):
		self.fg = self.kerning = fgKerningObject
		self.useExternalGroupData = False
		self.external_groups = None

		
		if externalGroupData is not None:
			self.external_groups = externalGroupData
			self.useExternalGroupData = True

		self.__kern_group_type = {'L':'KernLeft', 'R':'KernRight', 'B': 'KernBothSide'}
		self.__kern_pair_mode = ('glyphMode', 'groupMode')
		
		#self.groups = self.groups()
		
	def __repr__(self):
		return '<%s pairs=%s groups=%s external=%s>' % (self.__class__.__name__, len(self.kerning), len(self.groups().keys()), self.useExternalGroupData)

	# - Basic functions -------------------------------------
	def groups(self):
		if not self.useExternalGroupData:
			return self.fg.groups
		else:
			return self.external_groups

	def setExternalGroupData(self, externalGroupData):
		self.external_groups = externalGroupData
		self.useExternalGroupData = True	

	def storeExternalGroupData(self):
		for key, value in self.useExternalGroupData.iteritems():
			self.fg.groups[key] = value

	def resetGroups(self):
		# - Delete all group kerning at given layer
		self.groups().clear()	

	def asDict(self):
		return self.fg.asDict()

	def asList(self):
		# Structure:
		# 	fgKerning{fgKernigPair(fgKerningObject(glyph A, mode), fgKerningObject(glyph B, mode)) : kern value, ...}
		return [[[item.asTuple() for item in key.asTuple()], value] for key, value in self.kerning.asDict().iteritems()]

	def groupsAsDict(self):
		# - Semi working fixup of Build 6927 Bug
		if not self.useExternalGroupData:
			return self.fg.groups.asDict()
		else:
			return self.external_groups

	def groupsBiDict(self):
		from typerig.brain import extBiDict
		temp_data = {}

		for key, value in self.groupsAsDict().iteritems():
			temp_data.setdefault(value[1], {}).update({key : value[0]})

		return {key:extBiDict(value) for key, value in temp_data.iteritems()}

	def groupsFromDict(self, groupDict):
		# - Build Group kerning from dictionary
		kerning_groups = self.groups()
		
		for key, value in groupDict.iteritems():
			kerning_groups[key] = value

	def removeGroup(self, key):
		'''Remove a group from fonts kerning groups at given layer.'''
		del self.groups()[key]

	def renameGroup(self, oldkey, newkey):
		'''Rename a group in fonts kerning groups at given layer.'''
		self.groups().rename(oldkey, newkey)

	def addGroup(self, key, glyphNameList, type):
		'''Adds a new group to fonts kerning groups.
		Args:
			key (string): Group name
			glyphNameList (list(string)): List of glyph names
			type (string): Kern group types: L - Left group (1st), R - Right group (2nd), B - Both (1st and 2nd)
			layer (None, Int, String)
		
		Returns:
			None
		'''
		self.groups()[key] = (glyphNameList, self.__kern_group_type[type.upper()])

	def getPairObject(self, pairTuple):
		left, right = pairTuple
		modeLeft, modeRight = 0, 0
		groupsBiDict = self.groupsBiDict()
		
		if len(groupsBiDict.keys()):
			if groupsBiDict['KernLeft'].inverse.has_key(left):
				left = groupsBiDict['KernLeft'].inverse[left]
				modeLeft = 1

			elif groupsBiDict['KernBothSide'].inverse.has_key(left):
				left = groupsBiDict['KernBothSide'].inverse[left]
				modeLeft = 1

			if groupsBiDict['KernRight'].inverse.has_key(right):
				right = groupsBiDict['KernRight'].inverse[right]
				modeRight = 1

			elif groupsBiDict['KernBothSide'].inverse.has_key(right):
				right = groupsBiDict['KernBothSide'].inverse[right]
				modeRight = 1

		
		return self.newPair(left[0], right[0], modeLeft, modeRight)

	def getPair(self, pairTuple):
		pairObject = self.getPairObject(pairTuple)
		kern_pairs = self.fg.keys()

		if pairObject in kern_pairs:
			return (pairObject, self.fg[kern_pairs.index(pairObject)])

	def getKerningForLeaders(self, transformLeft=None, transformRight=None):
		''' Now in FL6 we do not have leaders, but this returns the first glyph name in the group '''
		kerning_data = self.fg.items()
		return_data = []

		for kern_pair, kern_value in kerning_data:
			left_name, right_name = kern_pair.left.id, kern_pair.right.id
			left_mode, right_mode = kern_pair.left.mode, kern_pair.right.mode

			left_leader = left_name if left_mode == self.__kern_pair_mode[0] else self.groups()[left_name][0][0]
			right_leader = right_name if right_mode == self.__kern_pair_mode[0] else self.groups()[right_name][0][0]

			left_leader = left_leader if transformLeft is None else transformLeft(left_leader)
			right_leader = right_leader if transformRight is None else transformRight(right_leader)

			return_data.append(((left_leader, right_leader), kern_value))

		return return_data
	
	def newPair(self, glyphLeft, glyphRight, modeLeft, modeRight):
		if not isinstance(modeLeft, str): modeLeft = self.__kern_pair_mode[modeLeft]
		if not isinstance(modeRight, str): modeRight = self.__kern_pair_mode[modeRight]
		return fgt.fgKerningObjectPair(glyphLeft, glyphRight, modeLeft, modeRight)