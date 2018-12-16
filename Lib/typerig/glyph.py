# MODULE: Fontlab 6 Custom Glyph Objects | Typerig
# VER 	: 0.25
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pGlyph

# - Classes -------------------------------
class eGlyph(pGlyph):
	'''Extended representation of the Proxy Glyph, adding some advanced functionality

	Constructor:
		pGlyph() - default represents the current glyph and current font
		pGlyph(fgFont, fgGlyph)
	'''
	# - Internal ------------------------------------------
	def _prepareLayers(self, layers):
		'''Internal! Prepares layers to be used in tools using GUI
		Args:
			layers (Bool control tuple(active_layer, masters, masks, services)). Note If all are set to False only the active layer is used.
		Returns:
			list: List of layer names
		'''
		layerBanList = ['#', 'img'] #! Parts or names of layers that are banned for manipulation

		if layers is None:
			return [layer.name for layer in self.layers() if all([item not in layer.name for item in layerBanList])]
		
		elif isinstance(layers, tuple):
			bpass = lambda condition, value: value if condition else []
			
			tempLayers = [] + bpass(layers[0], [self.activeLayer()]) + bpass(layers[1], self.masters()) + bpass(layers[2], self.masks()) + bpass(layers[3], self.services())
			return list(set([layer.name for layer in tempLayers if all([item not in layer.name for item in layerBanList])]))
		else:
			print 'ERROR:\tIncorrect layer triple!'

	def _compatibleLayers(self, layerName=None):
		return [layer.isCompatible(self.layer(layerName), True) for layer in self.layers()]
			
	def _getCoordArray(self, layer=None):
		from typerig.brain import coordArray
		coords = coordArray()
		for node in self.nodes(layer):
			
			# - Followiong will work on Cubic beziers only! Think of better way!
			nodeType = 0
			if node.isOn() and node.nextNode().isOn():				
				nodeType = 2
			if node.isOn() and not node.nextNode().isOn():				
				nodeType = 4

			coords.append((float(node.x), float(node.y)), nodeType)

		return coords

	def _setCoordArray(self, coordArray, layer=None):
		nodeArray = self.nodes(layer)
		if len(coordArray) == len(nodeArray):
			for nid in range(len(coordArray)):
				nodeArray[nid].x, nodeArray[nid].y = coordArray[nid]
		else:
			print 'ERROR:\t Incompatible coordinate array provided.'			

	# - Nodes ----------------------------------------------
	def breakContour(self, contourId, nodeId, layer=None, expand=0):
		'''Split Contour at given node and layer. Extrapolate line endings if needed.
		Args:
			contourId (int): Contour Index
			nodeId (int): Node Index
			layer (int or str): Layer index or name, works with both
			expand (float): Will extrapolate the line endings at that given value

		Returns:
			flContour
		'''

		if expand == 0:
			return self.contours(layer)[contourId].breakContour(nodeId)
		else:
			return self.contours(layer)[contourId].breakContourExpanded(nodeId, expand)

	def splitContour(self, scnPairs=None, layers=None, expand=0, close=False):
		'''Split Contour at given node and combinations of compatible layers. Extrapolate line endings and close contour if needed.
		
		Args:
			scnPairs (list(tuple)): Shape-contour-node pairs for the selected nodes [(Shape Index, Contour Index, Node Index)..()]
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			expand (float): Will extrapolate the line endings at that given value
			close (bool): True = Close contour 

		Return:
			None
		'''
		# - Init
		if scnPairs is None:
			scnPairs = self.selectedAtShapes()

		pLayers = self._prepareLayers(layers)

		# - Process ----------------------------
		for layerName in pLayers:
			relID = 0 # Relative ID to the last split

			for sID, cID, nID in scnPairs:
				#print layerName, sID, cID, nID, len(self.nodes())
				tempContour = self.breakContour(cID, nID - relID, layer=layerName, expand=expand)
				relID = nID

				if tempContour is not None:
					self.layer(layerName).shapes[sID].addContour(tempContour, True)

			if close: # Close all opened contours
				for contour in self.contours(layerName):
					if not contour.closed:
						contour.closed = True
						contour.update()


	# - Guidelines -----------------------------------------
	def dropGuide(self, nodes=None, layers=None, name='*DropGuideline', tag='', color='darkMagenta', flip=(1,1), style='gsGlyphGuideline'):
		'''Build guideline trough *any two* given points or the *first two of the current selection*.

		If *single point* is given will create a vertical guideline trough that point,
		with guideline inclined according to the font's Italic Angle.

		if process layers (pLayers) is None guideline will be created in all compatible layers,
		otherwise the bool control tuple (active_layer (True or False), masters (True or False), masks (True or False), services (True or False)) is used. 
		If all are set to False only the active layer is used.

		Args:
			nodes (list(int)): List of node indexes
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			name (str): Name of the guideline to be build
			color (str): Color of the guideline according to QtCore colors
			style (str): Style of the guideline according to FontLab 6

		Returns:
			None
		'''

		#!!!NOTE: It seems that composite/element glyphs with different delta/transforamtion could affect the positioning!
		#!!!NOTE: As elements are bidirectional now, try to check and adapt for the current QTransform!
		
		from PythonQt.QtCore import QLineF
		from PythonQt.QtGui import QTransform, QColor

		# - Init
		italicAngle = self.italicAngle()
		origin = pqt.QtCore.QPointF(0,0)
		pLayers = self._prepareLayers(layers)

		if nodes is None:
			coordDict = {name:self.selectedCoords(name, applyTransform=True) for name in pLayers if self.layer(name).isCompatible(self.activeLayer(), True)}
			processSingle = len(self.selected()) < 2
		else:
			# TODO: Make it qTransform aware! as the one above!
			coordDict = {name:[self.nodes(name)[nid].pointf for nid in nodes] for name in pLayers if self.layer(name).isCompatible(self.activeLayer(), True)}
			processSingle = len(nodes) < 2

		# - Process
		for layerName, layerCoords in coordDict.iteritems():
						
			if not processSingle:
				vector = QLineF(layerCoords[0], layerCoords[1])
			else:
				vector = QLineF(layerCoords[0], origin)
				vector.setAngle(90 - italicAngle)

			vTransform = QTransform()
			vTransform.scale(float(flip[0]), float(flip[1]))
			vector = vTransform.map(vector)

			# - Build
			newg = fl6.flGuideLine(vector)
			newg.name, newg.color, newg.style = name, QColor(color), style
			newg.tag(tag.replace(' ', '').split(','))
			self.layer(layerName).appendGuidelines([newg])

	# - Metrics -----------------------------------------
	def copyLSBbyName(self, glyphName, layers=None, order=0, adjustPercent=100, adjustUnits=0):
		'''Copy LSB from another glyph specified by Glyph Name.
		
		Args:
			glyphName (str): Name of source glyph
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			order (bool or int): Use source LSB (0 False) or RSB (1 True). Flips the metric copied.
			adjustPercent (int): Adjust the copied metric by percent (100 default)
			adjustUnits (int): Adjust the copied metric by units (0 default)

		Return:
			None
		'''
		srcGlyph = self.__class__(self.package.findName(glyphName))
		srcLayers = srcGlyph._prepareLayers(layers)		
		dstLayers = self._prepareLayers(layers)

		safeLayers = list(set(srcLayers) & set(dstLayers))

		for layer in safeLayers:
			self.setLSB((srcGlyph.getLSB(layer), srcGlyph.getRSB(layer))[order]*adjustPercent/100 + adjustUnits, layer)

	def copyRSBbyName(self, glyphName, layers=None, order=0, adjustPercent=100, adjustUnits=0):
		'''Copy RSB from another glyph specified by Glyph Name.
		
		Args:
			glyphName (str): Name of source glyph
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			order (bool or int): Use source LSB (0 False) or RSB (1 True). Flips the metric copied.
			adjustPercent (int): Adjust the copied metric by percent (100 default)
			adjustUnits (int): Adjust the copied metric by units (0 default)

		Return:
			None
		'''
		srcGlyph = self.__class__(self.package.findName(glyphName))
		srcLayers = srcGlyph._prepareLayers(layers)		
		dstLayers = self._prepareLayers(layers)

		safeLayers = list(set(srcLayers) & set(dstLayers))

		for layer in safeLayers:
			self.setRSB((srcGlyph.getRSB(layer), srcGlyph.getLSB(layer))[order]*adjustPercent/100 + adjustUnits, layer)

	def copyADVbyName(self, glyphName, layers=None, adjustPercent=100, adjustUnits=0):
		'''Copy Advance width from another glyph specified by Glyph Name.
		
		Args:
			glyphName (str): Name of source glyph
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			adjustPercent (int): Adjust the copied metric by percent (100 default)
			adjustUnits (int): Adjust the copied metric by units (0 default)

		Return:
			None
		'''
		srcGlyph = self.__class__(self.package.findName(glyphName))
		srcLayers = srcGlyph._prepareLayers(layers)		
		dstLayers = self._prepareLayers(layers)

		safeLayers = list(set(srcLayers) & set(dstLayers))

		for layer in safeLayers:
			self.setAdvance(srcGlyph.getAdvance(layer)*adjustPercent/100 + adjustUnits, layer)

	def copyMetricsbyName(self, metricTriple=(None, None, None), layers=None, order=(0, 0, 0), adjustPercent=(100, 100, 100), adjustUnits=(0,0,0)):
		'''Copy LSB, RSB and Advance width from glyphs specified by Glyph Name.
		
		Args:
			metricTriple tuple(str): Names of source glyphs for (LSB, RSB, ADV)
			layers tuple(bool): Bool control tuple(active_layer, masters, masks, services). Note If all are set to False only the active layer is used.
			order tuple(bool): Use source LSB (0 False) or RSB (1 True). Flips the metric copied. (LSB, RSB, 0)
			adjustPercent tuple(int): Adjust the copied metric by percent (100 default) - (LSB, RSB, ADV)
			adjustUnits tuple(int): Adjust the copied metric by units (0 default) - (LSB, RSB, ADV)

		Return:
			None
		'''
		if metricTriple[0] is not None:	self.copyLSBbyName(metricTriple[0], layers, order[0], adjustPercent[0], adjustUnits[0])
		if metricTriple[1] is not None:	self.copyRSBbyName(metricTriple[1], layers, order[1], adjustPercent[1], adjustUnits[1])
		if metricTriple[2] is not None:	self.copyADVbyName(metricTriple[2], layers, adjustPercent[2], adjustUnits[2])
		
	def bindCompMetrics(self, layer=None, bindIndex=None):
		'''Auto bind metrics to the base composite glyph or to specified shape index'''
		from typerig.string import diactiricalMarks

		base_shapes = [shape for shape in self.shapes(layer) + self.components(layer) if len(shape.shapeData.name) and shape.shapeData.name not in diactiricalMarks]
		
		if len(base_shapes):
			wShape = base_shapes[bindIndex] if bindIndex is not None else base_shapes[0]
			transform = wShape.transform
				
			if len(wShape.shapeData.name):
				if transform.m11() > 0:
					self.setLSBeq('=%s' %wShape.shapeData.name, layer)
					self.setRSBeq('=%s' %wShape.shapeData.name, layer)
				else:
					self.setLSBeq('=rsb("%s")' %wShape.shapeData.name, layer)
					self.setRSBeq('=lsb("%s")' %wShape.shapeData.name, layer)

				return True		

	# - Interpolation  ---------------------------------------
	def blendLayers(self, layerA, layerB, blendTimes, outputFL=True, blendMode=0, engine='fg'):
		'''Blend two layers at given times (anisotropic support).
		Args:
			layerA (flLayer), layerB (flLayer): Shapes to be interpolated
			blendTimes (int or float or tuple(float, float)): (int) for percent 0%-100% or (float) time for both X,Y or tuple(float,float) times for anisotropic blending
			outputFL (bool): Return blend native format or flShape (default)
			blendMode (int): ?
			engine (str): 'fg' for FontGate (in-build).

		Returns:
			flLayer
		'''
		from typerig.brain import linInterp

		if isinstance(blendTimes, tuple): blendTimes = pqt.QtCore.QPointF(*blendTimes)
		if isinstance(blendTimes, int): blendTimes = pqt.QtCore.QPointF(float(blendTimes)/100, float(blendTimes)/100)
		if isinstance(blendTimes, float): blendTimes = pqt.QtCore.QPointF(blendTimes, blendTimes)

		if layerA.isCompatible(layerB, True):
			# - Init
			blendLayer = fl6.flLayer('B:%s %s, t:%s' %(layerA.name, layerB.name, str(blendTimes)))
			
			# - Set and interpolate metrics
			blendLayer.advanceWidth = int(linInterp(layerA.advanceWidth, layerB.advanceWidth, blendTimes.x()))
			
			# - Interpolate shapes
			for shapeA in layerA.shapes:
				for shapeB in layerB.shapes:
					if shapeA.isCompatible(shapeB, True):
						tempBlend = self.blendShapes(shapeA, shapeB, blendTimes, outputFL, blendMode, engine)
						blendLayer.addShape(tempBlend)

			return blendLayer

	def lerpLayerFg(self, l0_Name, l1_Name):
		l0, l1 = self.layer(l0_Name), self.layer(l1_Name)

		if l0.isCompatible(l1):
			l0_fgShapes = [self._shape2fg(shape) for shape in l0.shapes]
			l1_fgShapes = [self._shape2fg(shape) for shape in l1.shapes]

			shapes = zip(l0_fgShapes, l1_fgShapes)

			def fgInterpolator(tx, ty):
				tempLayer = fl6.flLayer('B:%s %s, t:%s' %(l0.name, l1.name, (tx, ty)))
				
				for shapePair in shapes:
					tempBlend = fl6.flShape(fgt.fgShape(shapePair[0], shapePair[1], tx, ty, 0))
					tempLayer.addShape(tempBlend)

				return tempLayer
			
			return fgInterpolator

	# - Anchors & Pins -----------------------------------------
	def getAttachmentCenters(self, layer, tolerance=5, applyTransform=False):
		'''Return X center of lowest, highest Y of [glyph] for [layer] within given [tolerance]
		Note: Determine diacritic to glyph attachment positions (for anchor placement)
		'''
		from operator import itemgetter
		
		if not applyTransform:
			nodeCoords = [(node.position.x(), node.position.y()) for node in self.nodes(layer) if node.isOn()]
		else:
			nodeCoords = []
			for shape in self.shapes(layer):
				for contour in shape.getContours():
					for node in contour.nodes():
						if node.isOn():
							transCoords = shape.transform.map(node.position)
							nodeCoords.append((transCoords.x(), transCoords.y()))

		minValY = min(nodeCoords, key=itemgetter(1))[1]
		maxValY = max(nodeCoords, key=itemgetter(1))[1]

		coordsAtMinY = [item for item in nodeCoords if abs(item[1] - minValY) < tolerance]
		coordsAtMaxY = [item for item in nodeCoords if abs(item[1] - maxValY) < tolerance]

		XminY = (min(coordsAtMinY, key=itemgetter(0))[0] + max(coordsAtMinY, key=itemgetter(0))[0])/2
		XmaxY = (min(coordsAtMaxY, key=itemgetter(0))[0] + max(coordsAtMaxY, key=itemgetter(0))[0])/2

		return XminY, XmaxY

	def dropAnchor(self, name, layer, coordTuple, alignTuple=(None,None), tolerance=5, move=False, italic=False):
		'''Drop anchor at given layer
		Args:
			name (str): Anchor Name
			layer (int or str): Layer index or name, works with both
			coordTuple (int, int): New anchor coordinates or auto aligment offsets*
			alignTuple (str,str): New anchor aligment*
			tolerance (int): Outline feature auto detection tolerance*

		*Aligment rules: (width, height)
			- (None,None) - Uses coordinates given
			- width - (L) Left; (R) Right; (A) Auto Bottom with tolerance; (AT) Auto Top with tolerance; (C) Center;
			- height - (T) Top; (B) Bottom; (C) Center;
		Returns:
			None
			
		'''
		# - Init
		x, y = coordTuple
		alignX, alignY = alignTuple
		bbox = self.layer(layer).boundingBox

		# - Process
		if alignX is not None and 'A' in alignX :
			XminY, XmaxY = self.getAttachmentCenters(layer, tolerance, True)
			x += XmaxY if 'T' in alignX else XminY

		elif alignX == 'L':	x = bbox.x() + x*[1,-1][bbox.x() < 0]
		elif alignX == 'R':	x += bbox.width() + bbox.x()
		elif alignX == 'C':	x += bbox.width()/2 + bbox.x()

		if alignY == 'B':	y = bbox.y() + y*[1,-1][bbox.y() < 0]
		elif alignY == 'T':	y += bbox.height() + bbox.y()
		elif alignY == 'C':	y += bbox.height()/2 + bbox.y()

		if italic:
			from typerig.brain import _Point
			bPoint = _Point(x,y)
			bPoint.setAngle(-self.italicAngle())
			x = bPoint.getWidth()

		if not move:
			self.addAnchor((x, y), name, layer)
		else:
			anchor = self.layer(layer).findAnchor(name)
			anchor.point = pqt.QtCore.QPointF(x,y)


