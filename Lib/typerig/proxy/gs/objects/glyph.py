# MODULE: Typerig / Glyphs App Proxy / Glyph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------------------------
from __future__ import print_function
import math
from itertools import combinations
from operator import itemgetter

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from fontTools.pens import statisticsPen

from typerig.core.objects.point import Point
from typerig.core.func.math import linInterp

#from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.string import diactiricalMarks

# - Init -------------------------------------------
__version__ = '0.28.1'

# - Classes -----------------------------------------
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
			
		self.builders = {}
		self._guide_types = {'vertical': 16512, 'horizontal': 8193, 'vector': 4224, 'measure': 32}

	def __repr__(self):
		return '<{} name={} index={} unicode={}>'.format(self.__class__.__name__, self.name, self.index, self.unicode)

	# - Properties -------------------------------------------
	# TODO: Add setters
	@property
	def name(self):
		return self.fg.name

	@property
	def index(self):
		return self.fg.index

	@property
	def id(self):
		return self.fg.id

	@property
	def mark(self):
		return self.fl.mark

	@property
	def tags(self):
		return self.fl.tags

	@property
	def unicode(self):
		return self.fg.unicode

	@property
	def unicodes(self):
		return self.fg.unicodes

	@property
	def package(self):
		return fl6.flPackage(self.fl.package)

	# - Basics -----------------------------------------------
	def version(self): return self.fl.lastModified

	def activeLayer(self): return self.fl.activeLayer

	def fg_activeLayer(self): return self.fg.layer

	def mask(self): return self.fl.activeLayer.getMaskLayer(True)

	def activeGuides(self): return self.fl.activeLayer.guidelines

	def mLine(self): return self.fl.measurementLine()

	def object(self): return fl6.flObject(self.fl.id)

	def italicAngle(self): return self.package.italicAngle_value

	def setMark(self, mark_color, layer=None): 
		if layer is None:
			self.fl.mark = self.mark = mark_color
		else:
			self.layers(layer).mark = mark_color

	def setName(self, glyph_name): self.fl.name = self.fg.name = self.name = glyph_name

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

	def contours(self, layer=None, deep=False, extend=None):
		'''Return all contours at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flContours]
		'''
		
		if deep: # Dig deeper in grouped components and shapebuilders (filters)
			glyph_shapes = self.shapes(layer, deep=deep)
			layer_contours = sum([shape.contours for shape in glyph_shapes], [])
		else:
			layer_contours = self.layer(layer).getContours()

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

	def shapes(self, layer=None, extend=None, deep=False):
		'''Return all shapes at given layer.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[flShapes]
		'''
		layer_shapes = self.layer(layer).shapes 
		deep_shapes = sum([shape.includesList for shape in self.containers(layer)], [])
		all_shapes = deep_shapes if deep and len(deep_shapes) else layer_shapes # Fallback!
		
		if extend is None:
			return all_shapes
		else:
			return [extend(shape) for shape in all_shapes]

	def getElementNames(self, layer=None):
		'''Return names of elements references used in glyph.'''
		return [shape.shapeData.name for shape in self.shapes(layer)]

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
	def elements(self, layer=None, extend=None):
		'''Return all glyph elements in glyph'''
		return [shape.includesList for shape in self.shapes(layer, extend) if len(shape.includesList)]

	def noncomplex(self, layer=None,  extend=None):
		'''Return all glyph shapes that are not glyph references or components'''
		special = self.components(layer) + self.elements(layer) +  self.containers(layer)
		return [shape for shape in self.shapes(layer, extend) if shape not in special]		
	
	def components(self, layer=None, extend=None):
		'''Return all glyph components besides glyph.'''
		return [shape for shape in self.shapes(layer, extend) if shape.shapeData.isComponent]

	def getCompositionNames(self, layer=None):
		'''Return name of glyph and the parts it is made of.'''
		return [shape.shapeData.componentGlyph for shape in self.components(layer)]

	def getCompositionDict(self, layer=None):
		'''Return composition dict of a glyph. Elements!'''
		return {shape.shapeData.componentGlyph:shape for shape in self.components(layer)}

	def addComponents(self, componentConfig, layer=None, useAnchors=True, colorize=False):
		'''Adds a components to given glyph layer.
		Args:
			componentConfig (list(tuple(glyph_name (str), glyph_transform (QTransform), layer_pointer (str)))): List contianign component configuration.  
			layer (int or str): Layer index or name. If None returns ActiveLayer
			useAnchors (bool): Compose using anchors
			colorize (bool): Flag new glyphs
		Returns:
			list(flShapes): List of components added
		'''
		
		# - Init
		font = pFont(self.parent)
		component_add = []
		component_fin = []
		component_widths = []
		component_pointers = {}
		component_snapshot = self.components(layer)
		
		for glyph_name, glyph_transform, layer_pointer in componentConfig:
			new_component = fl6.GlyphComponent(glyph_name)
			if glyph_transform is not None: new_component.transform = glyph_transform
			new_component.use_anchors = useAnchors
			
			component_pointers[glyph_name] = layer_pointer
			component_add.append(new_component)
			component_widths.append(font.glyph(glyph_name).getAdvance(layer))

		if len(component_add):
			self.layer(layer).setGlyphComponents(component_add, max(component_widths), font.fl, colorize)
			
			for shape in self.components(layer):
				shape_name = shape.shapeData.componentGlyph
				
				if shape not in component_snapshot:
					if shape_name in component_pointers.keys():	
						shape.shapeData.componentLayer = component_pointers[shape_name] # Set layer reference
					
					component_fin.append(shape)
		
		return component_fin


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

	def duplicateLayer(self, layer=None, newLayerName='New Layer', references=False):
		'''Duplicates a layer with new name and adds it to glyph's layers.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			toBack(bool): send to back
		Returns:
			flLayer
		'''
		options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': references}
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
		dstLayerName = str(dstLayerName) if self.layer(dstLayerName) is None else str(dstLayerName) + '.copy'

		# -- Create new layer
		newLayer = fl6.flLayer()
		newLayer.name = dstLayerName

		# -- Assign same styling
		newLayer.advanceHeight = srcLayer.advanceHeight
		newLayer.advanceWidth = srcLayer.advanceWidth
		newLayer.wireframeColor = srcLayer.wireframeColor
		newLayer.mark = srcLayer.mark
		newLayer.assignStyle(srcLayer)

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
				if options['ref']:
					newShape = self.layer(dstLayerName).addShape(shape)
				else:
					newShape = self.layer(dstLayerName).addShape(shape.cloneTopLevel())
		
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

		if not addLayer:
			self.removeLayer(newLayer.name)

		return newLayer

	def isCompatible(self, strong=False):
		'''Test if glyph is ready for interpolation - all master layers are compatible.'''
		glyph_masters = self.masters()
		layer_pairs = combinations(glyph_masters, 2)
		return all([layerA.isCompatible(layerB, strong) for layerA, layerB in layer_pairs])

	def isMixedReference(self):
		'''Test if glyph has mixed references - components on some layers and referenced shapes on others'''
		'''
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
		if verbose: print('DONE:\t{}'.format(undoMessage))
		
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
		raise NotImplementedError

	def selectedContours(self, layer=None, allNodesSelected=False, deep=False):
		raise NotImplementedError

	def selectedShapes(self, layer=None, allNodesSelected=False, deep=False):
		raise NotImplementedError

	def nodesForIndices(self, indices, layer=None, filterOn=False, extend=None, deep=False):
		raise NotImplementedError
	
	def selectedAtContours(self, index=True, layer=None, filterOn=False, deep=False):	
		'''Return all selected nodes and the contours they rest upon at current layer.
		Args:
			index (bool): If True returns only indexes, False returns flContour, flNode
			filterOn (bool): Return only on-curve nodes
		Returns:
			list[tuple(int, int)]: [(contourID, nodeID)..()] or 
			list[tuple(flContour, flNode)]
		'''
		raise NotImplementedError
		
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
		raise NotImplementedError

	def selectedShapeIndices(self, layer=None, select_all=False, deep=False):
		'''Return all indices of nodes selected at current layer.
		Args:
			select_all (bool): True all nodes on Shape should be selected. False any node will do.
		Returns:
			list[int]
		'''
		raise NotImplementedError
		
	def selectedShapes(self, layer=None, select_all=False, deep=False, extend=None):
		'''Return all shapes that have a node selected.
		'''
		raise NotImplementedError

	def selectedCoords(self, layer=None, filterOn=False, applyTransform=False, deep=False):
		'''Return the coordinates of all selected nodes at the current layer or other.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
			filterOn (bool): Return only on-curve nodes
			applyTransform (bool) : Gets local shape transformation matrix and applies it to the node coordinates
		Returns:
			list[QPointF]
		'''
		raise NotImplementedError

	def selectedSegments(self, layer=None, deep=False):
		'''Returns list of currently selected segments
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		raise NotImplementedError

	def findNode(self, nodeName, layer=None):
		'''Find node by name/tag'''
		raise NotImplementedError

	def findNodeCoords(self, nodeName, layer=None):
		'''Find node coordinates by name/tag'''
		raise NotImplementedError

	# - Outline -----------------------------------------------
	def _mapOn(self, layer=None):
		'''Create map of onCurve Nodes for every contour in given layer
		Returns:
			dict: {contour_index : {True_Node_Index : on_Curve__Node_Index}...}
		'''
		raise NotImplementedError

	def mapNodes2Times(self, layer=None):
		'''Create map of Nodes at contour times for every contour in given layer
		Returns:
			dict{Contour index (int) : dict{Contour Time (int): Node Index (int) }}
		'''
		raise NotImplementedError

	def mapTimes2Nodes(self, layer=None):
		'''Create map of Contour times at node indexes for every contour in given layer
		Returns:
			dict{Contour index (int) : dict{Node Index (int) : Contour Time (int) }}
		'''
		raise NotImplementedError

	def getSegment(self, cID, nID, layer=None):
		'''Returns contour segment of the node specified at given layer
		Args:
			cID (int): Contour index
			nID (int): Node of insertion index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			CurveEx
		'''
		raise NotImplementedError

	def segments(self, cID, layer=None):
		'''Returns all contour segments at given layer
		Args:
			cID (int): Contour index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		raise NotImplementedError

	def nodes4segments(self, cID, layer=None):
		'''Returns all contour segments and their corresponding nodes at given layer
		Args:
			cID (int): Contour index
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			dict{time(int):(CurveEx, list[flNode]}
		'''
		raise NotImplementedError

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
		raise NotImplementedError

	def removeNodes(self, cID, nodeList, layer=None):
		'''Removes a list of nodes from contour at layer specified.
		Args:
			cID (int): Contour index
			nodeList (list): List of flNode objects
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	def insertNodeAt(self, cID, nID_time, layer=None):
		''' Inserts node in contour at specified layer
		Arg:
			cID (int): Contour Index
			nID_time (float): Node index + float time
			layer (int or str): Layer index or name. If None returns ActiveLayer

		!NOTE: FL6 treats contour insertions (as well as nodes) as float times along contour,
		so inserting a node at .5 t between nodes with indexes 3 and 4 will be 3 (index) + 0.5 (time) = 3.5
		'''
		raise NotImplementedError

	def removeNodeAt(self, cID, nID, layer=None):
		'''Removes a node from contour at layer specified.
		Args:
			cID (int): Contour index
			nID (int): Index of Node to be removed
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	def translate(self, dx, dy, layer=None):
		'''Translate (shift) outline at given layer.
		Args:
			dx (float), dy (float): delta (shift) X, Y
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	def scale(self, sx, sy, layer=None):
		'''Scale outline at given layer.
		Args:
			sx (float), sy (float): delta (scaling) X, Y
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	def slant(self, deg, layer=None):
		'''Slant outline at given layer.
		Args:
			deg (float): degrees of slant
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	def rotate(self, deg, layer=None):
		'''Rotate outline at given layer.
		Args:
			deg (float): degrees of slant
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			None
		'''
		raise NotImplementedError

	# - Metrics -----------------------------------------------
	def getLSB(self, layer=None):
		'''Get the Left Side-bearing at given layer (int or str)'''
		raise NotImplementedError
	
	def getAdvance(self, layer=None):
		'''Get the Advance Width at given layer (int or str)'''
		raise NotImplementedError

	def getRSB(self, layer=None):
		'''Get the Right Side-bearing at given layer (int or str)'''
		raise NotImplementedError

	def getBounds(self, layer=None):
		'''Get Glyph's Boundig Box at given layer (int or str). Returns QRectF.'''
		raise NotImplementedError

	def setLSB(self, newLSB, layer=None):
		'''Set the Left Side-bearing (int) at given layer (int or str)'''
		raise NotImplementedError

	def setRSB(self, newRSB, layer=None):
		'''Set the Right Side-bearing (int) at given layer (int or str)'''
		raise NotImplementedError

	def setAdvance(self, newAdvance, layer=None):
		'''Set the Advance Width (int) at given layer (int or str)'''
		raise NotImplementedError

	def setLSBeq(self, equationStr, layer=None):
		'''Set LSB metric equation on given layer'''
		raise NotImplementedError

	def setRSBeq(self, equationStr, layer=None):
		'''Set RSB metric equation on given layer'''
		raise NotImplementedError

	def setADVeq(self, equationStr, layer=None):
		'''Set Advance width metric equation on given layer'''
		raise NotImplementedError

	def hasSBeq(self, layer=None):
		'''Returns True if glyph has any SB equation set'''
		raise NotImplementedError

	def getSBeq(self, layer=None):
		'''Get LSB, RSB metric equations on given layer'''
		raise NotImplementedError

	def setSBeq(self, equationTuple, layer=None):
		'''Set LSB, RSB metric equations on given layer'''
		raise NotImplementedError

	def fontMetricsInfo(self, layer=None):
		'''Returns Font(layer) metrics no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			FontMetrics (object)
		'''
		raise NotImplementedError

	# - Anchors and pins ---------------------------------------
	def anchors(self, layer=None):
		'''Return list of anchors (list[flAnchor]) at given layer (int or str)'''
		raise NotImplementedError

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
		raise NotImplementedError

	def newAnchor(self, coordTuple, name, anchorType=1):
		'''	
		Creates new anchor
		Args:
			coordTuple (tuple(float,float)): Anchor coordinates X, Y
			name (str): Anchor name
			anchorType: 
		Returns:
			flPinPoint
		'''
		raise NotImplementedError

	def clearAnchors(self, layer=None):
		'''Remove all anchors at given layer (int or str)'''
		raise NotImplementedError

	def findAnchor(self, anchorName, layer=None):
		'''Find anchor by name/tag'''
		raise NotImplementedError

	def findAnchorCoords(self, anchorName, layer=None):
		'''Find anchor coordinates by name/tag '''
		raise NotImplementedError

	# - Guidelines -----------------------------------------
	def guidelines(self, layer=None):
		'''Return list of guidelines (list[flGuideline]) at given layer (int or str)'''
		raise NotImplementedError

	def addGuideline(self, coordTuple, layer=None, angle=0, name='', tag='', color='darkMagenta', style='gsGlyphGuideline', expression=''):
		'''Adds named Guideline at given layer
		Args:
			coordTuple (tuple(float,float) or tuple(float,float,float,float)): Guideline coordinates X, Y and given angle or two node reference x1,y1 and x2,y2
			name (str): Anchor name
			angle (float): Incline of the guideline
			layer (int or str): Layer index or name. If None returns ActiveLayer			
		Returns:
			flGuideLine
		'''
		raise NotImplementedError

	# - Tags -----------------------------------------------
	def getTags(self):
		raise NotImplementedError

	def setTags(self, tagList, append=True):
		raise NotImplementedError

	def tag(self, newTag):
		raise NotImplementedError

	# - Pens -----------------------------------------------
	def draw(self, pen, layer=None):
		''' Utilizes the Pen protocol'''
		raise NotImplementedError

	def drawPoints(self, pen, layer=None):
		''' Utilizes the PointPen protocol'''
		raise NotImplementedError
