# MODULE: Typerig / Proxy / Application
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.76.3'


# - Dependencies --------------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Procedures/Functions ------------------
def loadFont(file_path):
	''' Loads Font file from path (str) and returns opened fgFont object'''
	fl6.flItems.requestLoadingFont(file_path)
	return fl6.CurrentFont()

# - Classes -------------------------------
class pItems(object):
	'''Proxy to flItems object

	Constructor:
		pItems()

	Attributes:
		.fl (flItems): Current workspace
	'''
	def __init__(self):
		self.fl = fl6.flItems()

	# - Output and string related -------------------------
	def outputString(self, string, cursor_location=0):
		'''Output text to the application'''
		self.fl.requestContent(fl6.fgSymbolList(string), cursor_location)

	def outputGlyphNames(self, glyphNamesList, layerList=[], cursor_location=0):
		'''Output text string using glyph names and layers specified'''
		fgSymbols = [fl6.fgSymbol(glyph_name) for glyph_name in glyphNamesList]
		
		if not len(layerList):
			layerList = ['']

		if len(layerList) == len(fgSymbols):
			pass
		elif len(layerList) == 1:
			layerList = layerList*len(fgSymbols)
		else:
			layerList = layerList[0]*len(fgSymbols)

		fgSymbol_layer_pair = zip(fgSymbols, layerList)

		for symbol, layer in fgSymbol_layer_pair:
			symbol.layerName = layer

		self.fl.requestContent(fl6.fgSymbolList(fgSymbols), cursor_location)

	# - Font related ------------------------------------
	def openFont(self, font_package):
		self.fl.requestPackageBorn(font_package)

	def loadFont(self):
		self.fl.requestLoadingFont(file_path)


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
		return '<{} ({}, {}, {}, {}) fontSize={} glyphs={}>'.format(self.__class__.__name__, self.x(), self.y(), self.width(), self.height(), self.fl.fontSize, self.fl.glyphsCount())	