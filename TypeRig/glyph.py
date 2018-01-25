# MODULE: Fontlab 6 Custom Glyph Objects | TypeRig
# VER 	: 0.20
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

from TypeRig.proxy import pGlyph

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

		if layers is None:
			return [layer.name for layer in self.layers() if '#' not in layer.name]
		
		elif isinstance(layers, tuple):
			bpass = lambda condition, value: value if condition else []
			
			tempLayers = [] + bpass(layers[0], [self.activeLayer()]) + bpass(layers[1], self.masters()) + bpass(layers[2], self.masks()) + bpass(layers[3], self.services())
			return list(set([layer.name for layer in tempLayers if '#' not in layer.name]))
		else:
			print 'ERROR:\tIncorrect layer triple!'
			
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

				if tempContour.isValid: # When contour is cut at two nodes it becomes "standalone" and Valid, thus should be reinserted into glyph
					self.layer(layerName).shapes[sID].addContour(tempContour, True)

			if close: # Close all opened contours
				for contour in self.contours(layerName):
					if not contour.closed:
						contour.closed = True
						contour.update()


	# - Guidelines -----------------------------------------
	def dropGuide(self, nodes=None, layers=None, name='*DropGuideline', color='darkMagenta', style='gsGlyphGuideline'):
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
		
		# - Init
		italicAngle = fl6.flPackage(self.parent).italicAngle_value
		origin = pqt.QtCore.QPointF(0,0)
		pLayers = self._prepareLayers(layers)

		if nodes is None:
			coordDict = {name:self.selectedCoords(name) for name in pLayers if self.layer(name).isCompatible(self.activeLayer())}
			processSingle = len(self.selected()) < 2
		else:
			coordDict = {name:[self.nodes(name)[nid].pointf for nid in nodes] for name in pLayers if self.layer(name).isCompatible(self.activeLayer())}
			processSingle = len(nodes) < 2

		# - Process
		for layerName, layerCoords in coordDict.iteritems():
						
			if not processSingle:
				vector = pqt.QtCore.QLineF(layerCoords[0], layerCoords[1])
			else:
				vector = pqt.QtCore.QLineF(layerCoords[0], origin)
				vector.setAngle(90 - italicAngle)				

			# - Build
			newg = fl6.flGuideLine(vector)
			newg.name, newg.color, newg.style = name, color, style
			self.layer(layerName).appendGuidelines([newg])

	# - Metrics -----------------------------------------
	def copyMetricsSB(self, LSBGlyphName, RSBGlyphName, layer='all', srcFont=None, order=(0,1), adjustPercent=100, adjustUnits=(0,0)):
		'''
		Copy Glyph Side-bearings (LSB, RSB) form another glyph(s) referenced by name.
		'''
		
		# - Init
		if srcFont is None:	srcFont = fl6.CurrentFont()
		pGlyphLSB = pGlyph(srcFont, srcFont[LSBGlyphName])
		pGlyphRSB = pGlyph(srcFont, srcFont[RSBGlyphName])

		# - Process
		if layer == 'all':
			layerNames = lambda g: [g.layer(lid).name for lid in range(len(g.layers()))]

			glyphLayerNames = [self.layer(lid).name for lid in range(len(self.layers()))]

			safeLSBlayers = list(set(glyphLayerNames) & set(layerNames(pGlyphLSB)))
			safeRSBlayers = list(set(glyphLayerNames) & set(layerNames(pGlyphRSB)))

			LSBmargins = {lname:((pGlyphLSB.getLSB(lname), pGlyphLSB.getRSB(lname))[order[0]]*adjustPercent)/100 + adjustUnits[0] for lname in safeLSBlayers}
			RSBmargins = {lname:((pGlyphRSB.getLSB(lname), pGlyphRSB.getRSB(lname))[order[1]]*adjustPercent)/100 + adjustUnits[1] for lname in safeRSBlayers}

		else:
			LSBmargins = {pGlyphLSB.layer(layer).name:((pGlyphLSB.getLSB(layer), pGlyphLSB.getRSB(layer))[order[0]]*adjustPercent)/100 + adjustUnits[0]}
			RSBmargins = {pGlyphRSB.layer(layer).name:((pGlyphRSB.getLSB(layer), pGlyphRSB.getRSB(layer))[order[1]]*adjustPercent)/100 + adjustUnits[1]}

		# - Set
		for layer, lsb in LSBmargins.iteritems():
			self.setLSB(lsb, layer)

		for layer, rsb in RSBmargins.iteritems():
			self.setRSB(rsb, layer)

	# - Interpolation  ---------------------------------------
	def blendLayers(self, layerA, layerB, blendTimes, outputFL=True, blendMode=0, engine='fg'):
		from TypeRig.utils import linInterp

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

	# - Anchors & Pins -----------------------------------------
	def getAttachmentCenters(self, layer, tolerance=5):
		'''
		Return X center of lowest, highest Y of [glyph] for [layer] within given [tolerance]
		Note: Determine diacritic to glyph attachment positions (for anchor placement)
		'''
		from operator import itemgetter
		
		nodeCoords = [(node.pointf.x(), node.pointf.y()) for node in self.nodes(layer) if node.isOn]

		minValY = min(nodeCoords, key=itemgetter(1))[1]
		maxValY = max(nodeCoords, key=itemgetter(1))[1]

		coordsAtMinY = [item for item in nodeCoords if abs(item[1] - minValY) < tolerance]
		coordsAtMaxY = [item for item in nodeCoords if abs(item[1] - maxValY) < tolerance]

		XminY = (min(coordsAtMinY, key=itemgetter(0))[0] + max(coordsAtMinY, key=itemgetter(0))[0])/2
		XmaxY = (min(coordsAtMaxY, key=itemgetter(0))[0] + max(coordsAtMaxY, key=itemgetter(0))[0])/2

		# !TODO: Italic compensation - re-adapt FontBrain Module + Component tuner
		return XminY, XmaxY

	def dropAnchor(self, yHeight, name, alignTop=True, layer='all'):
		
		# - Init
		def __drop(yHeight, name, layer, alignTop):
			XminY, XmaxY = self.getAttachmentCenters(layer)
			xWidth = XmaxY if alignTop else XminY
			self.addAnchor((xWidth, yHeight), name, layer)

		# - Process
		if layer == 'all':
			for layer in range(len(self.layers())):
				__drop(yHeight, name, layer, alignTop)
		else:
			__drop(yHeight, name, layer, alignTop)

		





