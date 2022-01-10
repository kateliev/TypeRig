# MODULE: Typerig / Proxy / Glyph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
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

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.string import diactiricalMarks

# - Init -------------------------------------------
__version__ = '0.29.1'

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

	@name.setter
	def name(self, name):
		self.fg.name = name

	@property
	def index(self):
		return self.fg.index

	@property
	def id(self):
		return self.fg.id

	@property
	def mark(self):
		return self.fl.mark

	@mark.setter
	def mark(self, mark):
		self.fl.mark = mark

	@property
	def tags(self):
		return self.fl.tags

	@tags.setter
	def tags(self, tags):
		self.fl.tags = tags

	@property
	def unicode(self):
		return self.fg.unicode

	@unicode.setter
	def unicode(self, unicode):
		self.fg.unicode = unicode

	@property
	def unicodes(self):
		return self.fg.unicodes

	@unicodes.setter
	def unicodes(self, unicodes):
		self.fg.unicodes = unicodes

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

	def replaceShapeAdv(self, old_shape_name, new_shape, layer=None):
		'''Advanced Repalce a shape at given layer. Will look inside groups and swap there.
		Args:
			old_shape_name (str): Shape name to search for
			new_shape (flShape): Replace all occurances with the following flShape
			layer (str): Layer name
		Returns:
			old_shapes (list): List of all shapes that were replaced
		'''
		# - Init
		deep_shapes = [(shape, shape.includesList) for shape in self.layer(layer).shapes]
		base_shapes, nested_shapes = [], []

		# - Collect data
		for shape, included_shapes in deep_shapes:
			if old_shape_name == shape.shapeData.name: 
				base_shapes.append(shape)
				continue

			ix = 0
			for inc_shape in included_shapes:
				if old_shape_name == inc_shape.shapeData.name: 
					nested_shapes.append((shape, inc_shape, ix))

				ix += 1

		# - Replace shapes
		# -- Replace base shapes
		for shape in base_shapes:
			new_shape.transform = shape.transform
			self.layer(layer).replaceShape(shape, new_shape)

		# -- Replace included/grouped shapes
		for base, shape, ix in nested_shapes:
			new_shape.transform = shape.transform
			base.eject(shape)
			base.includeTo(ix, new_shape)

		return base_shapes + [item[1] for item in nested_shapes]

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

	def findShape(self, shapeName, layer=None, deep=True):
		'''Finds shape by name on given layer
		Args:
			shapeName (str): Shape name
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			flShape or None
		'''
		for shape in self.shapes(layer, deep=deep):
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
		self.copyLayer(layer, newLayerName, options, True, True, True)

	def copyLayer(self, srcLayerName, dstLayerName, options, addLayer, cleanDST, toBack):
		return self.importLayer(self, srcLayerName, dstLayerName, options, addLayer, cleanDST, toBack, mode='new')

	def importLayer(self, srcGlyph, srcLayerName, dstLayerName, options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': True}, addLayer=False, cleanDST=True, toBack=True, mode='new'):
		'''Copies (imports) a layer from another glyph.
		Args:
			srcGlyph (pGlyph): Source glyph
			srcLayerName, dstLayerName (string): Source and destination layer names
			options (dict): Copy Options as follows {'out': Outline, 'gui': Guidelines, 'anc': Anchors, 'lsb': LSB, 'adv': Advance, 'rsb': RSB, 'lnk': Linked metrics, 'ref': References}, addLayer=False):
			addLayer (bool): Create a new layer
			cleanDST (bool): Clean destination layer
			toBack (bool): Add layer to back of the layer stack
			mode (string): 'new' - creates new layer; 'insert' - inserts into existing layer; 'mask' - creates and inserts into a mask layer;
		Returns:
			flLayer
		'''
		# !!! UGLY CODE - REFACTOR !!!!!!

		def __addNewLayer():
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

			return newLayer

		# - Init
		srcLayer = srcGlyph.layer(srcLayerName)
		layer_names = [layer.name for layer in self.layers()]
		
		if mode == 'new':
			dstLayerName = dstLayerName if dstLayerName not in layer_names else str(dstLayerName) + '.copy'
			newLayer = __addNewLayer()

		elif mode == 'insert':
			if dstLayerName not in layer_names:
				newLayer = __addNewLayer()
			else:
				newLayer = self.layer(dstLayerName)

		elif mode == 'mask':
			if dstLayerName not in layer_names:
				newLayer = __addNewLayer()

			newLayer = self.layer(dstLayerName).getMaskLayer(True)
			dstLayerName = newLayer.name

		# -- Outline
		if options['out']:
			# --- Get shapes
			srcShapes = srcGlyph.shapes(srcLayerName)

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
			self.setLSB(srcGlyph.getLSB(srcLayerName), dstLayerName)
		
		if options['adv']: 
			self.setAdvance(srcGlyph.getAdvance(srcLayerName), dstLayerName)
		
		if options['rsb']: 
			self.setRSB(srcGlyph.getRSB(srcLayerName), dstLayerName)

		if options['lnk']:
			self.setLSBeq(srcGlyph.getSBeq(srcLayerName)[0], dstLayerName)
			self.setRSBeq(srcGlyph.getSBeq(srcLayerName)[1], dstLayerName)

		# -- Anchors
		if options['anc']:
			if cleanDST:
				self.clearAnchors(dstLayerName)

			for src_anchor in srcGlyph.anchors(srcLayerName):
				self.addAnchor((src_anchor.point.x(), src_anchor.point.y()), src_anchor.name, dstLayerName)

		if not addLayer:
			self.removeLayer(newLayer.name)

		return newLayer

	def isEmpty(self, strong=True):
		if strong: return all([layer.shapesCount == 0  for layer in self.layers()])
		return any([layer.shapesCount == 0  for layer in self.layers()])

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
	def update(self):
		'''Updates the glyph and sends notification to the editor.	'''
		for contour in self.contours():
			contour.changed()
	
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

	# - Glyph Selection -----------------------------------------------
	def selectedNodesOnCanvas(self, filterOn=False):
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

	def selectedContours(self, layer=None, allNodesSelected=False, deep=False):
		selection_mode = 3 if allNodesSelected else 1
		return [contour for contour in self.contours(layer, deep=deep) if contour.hasSelected(selection_mode)]

	def selectedShapes(self, layer=None, allNodesSelected=False, deep=False):
		selection_mode = 3 if allNodesSelected else 1
		return [shape for shape in self.shapes(layer, deep=deep) if shape.hasSelected(selection_mode)]

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
		all_contours = self.contours(layer, deep=deep)
		
		if index:
			return [(all_contours.index(node.contour), node.index) for node in self.selectedNodes(layer, filterOn, deep=deep)]
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
		all_contours = self.contours(layer=layer, deep=deep)
		all_shapes = self.shapes(layer, deep=deep)

		if index:
			return [(all_shapes.index(shape), all_contours.index(contour), node.index) for shape in all_shapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(layer=layer, filterOn=filterOn, deep=deep)]
		else:
			return [(shape, contour, node) for shape in all_shapes for contour in shape.contours for node in contour.nodes() if node in self.selectedNodes(layer=layer, filterOn=filterOn, deep=deep)]

	def selectedShapeIndices(self, layer=None, select_all=False, deep=False):
		'''Return all indices of nodes selected at current layer.
		Args:
			select_all (bool): True all nodes on Shape should be selected. False any node will do.
		Returns:
			list[int]
		'''
		selection_mode = ['AnyNodeSelected', 'AllContourSelected'][select_all]
		all_shapes = self.shapes(layer, deep=deep)

		return [all_shapes.index(shape) for shape in all_shapes if shape.hasSelected(selection_mode)]
		
	def selectedShapes(self, layer=None, select_all=False, deep=False, extend=None):
		'''Return all shapes that have a node selected.
		'''
		selection_mode = ['AnyNodeSelected', 'AllContourSelected'][select_all]
		all_shapes = self.shapes(layer, deep=deep)

		if extend is None:
			return [all_shapes[sid] for sid in self.selectedShapeIndices(layer, select_all=select_all, deep=deep)]
		else:
			return [extend(all_shapes[sid]) for sid in self.selectedShapeIndices(layer, select_all=select_all, deep=deep)]

	def selectedCoords(self, layer=None, filterOn=False, applyTransform=False, deep=False):
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
			nodelist = self.selectedAtContours(filterOn=filterOn, deep=deep)
			#return [pLayer.getContours()[item[0]].nodes()[item[1]].position for item in nodelist]
			return [self.contours(layer, deep=deep)[cid].nodes()[nid].position for cid, nid in nodelist]

		else:
			nodelist = self.selectedAtShapes(filterOn=filterOn, deep=False)
			#return [pLayer.getShapes(1)[item[0]].transform.map(pLayer.getContours()[item[1]].nodes()[item[2]].position) for item in nodelist]
			return [self.shapes(layer, deep=deep)[sid].transform.map(self.contours(layer, deep=deep)[cid].nodes()[nid].position) for sid, cid, nid in nodelist]

	def selectedSegments(self, layer=None, deep=False):
		'''Returns list of currently selected segments
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			list[CurveEx]
		'''
		return [self.contours(layer, deep=deep)[cID].segment(self.mapNodes2Times(layer)[cID][nID]) for cID, nID in self.selectedAtContours(deep=deep)]

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
		all_contours = self.contours(layer)
		
		for contour in all_contours:
			nodeMap = {}
			countOn = -1

			for node in contour.nodes():
				countOn += node.isOn() # Hack-ish but working
				nodeMap[node.index] = countOn
				
			contourMap[all_contours.index(contour)] = nodeMap

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
		pLayer = self.layer(layer)
		pTransform = pLayer.transform
		pTransform.shear(math.tan(math.radians((deg)), 0))
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

	def hasSBeq(self, layer=None):
		'''Returns True if glyph has any SB equation set'''
		left, right = self.getSBeq(layer)
		return len(left) or len(right)

	def getSBeq(self, layer=None):
		'''Get LSB, RSB metric equations on given layer'''
		active_layer = self.layer(layer)
		return active_layer.metricsLeft, active_layer.metricsRight

	def setSBeq(self, equationTuple, layer=None):
		'''Set LSB, RSB metric equations on given layer'''
		active_layer = self.layer(layer)
		active_layer.metricsLeft = equationTuple[0]		
		active_layer.metricsRight = equationTuple[1]

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

	# - Anchors and pins ---------------------------------------
	def anchors(self, layer=None):
		'''Return list of anchors (list[flAnchor]) at given layer (int or str)'''
		
		'''
		# BUGFIX FL7 build 7234, 7515
		work_layer = self.layer(layer)
		anchor_names = [obj.name for obj in work_layer.anchors]
		anchors = [work_layer.findAnchor(name) for name in anchor_names]
		return anchors
		'''
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
		
		self.layer(layer).addAnchor(newAnchor)
		
		return newAnchor

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

	# - Guidelines -----------------------------------------
	def guidelines(self, layer=None):
		'''Return list of guidelines (list[flGuideline]) at given layer (int or str)'''
		return self.layer(layer).guidelines

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
		if len(coordTuple) == 2:
			origin = pqt.QtCore.QPointF(0,0)
			position = pqt.QtCore.QPointF(*coordTuple)

			vector = pqt.QtCore.QLineF(position, origin)
			vector.setAngle(90 - angle)
		else:
			vector = pqt.QtCore.QLineF(*coordTuple)

		newGuideline = fl6.flGuideLine(vector)
		
		if angle == 0:
			newGuideline.snapFlags = self._guide_types['vertical']
		elif angle == 90:
			newGuideline.snapFlags = self._guide_types['horizontal']
		else:
			newGuideline.snapFlags = self._guide_types['vector']

		if len(name): newGuideline.name =  name
		if len(color): newGuideline.color = pqt.QtGui.QColor(color)
		if len(style): newGuideline.style = style
		if len(tag): newGuideline.tag(tag.replace(' ', '').split(','))
		if len(expression): newGuideline.expression = expression
			
		self.layer(layer).appendGuidelines([newGuideline])
		return newGuideline


	# - Tags -----------------------------------------------
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
				current_transform = shape.fl_transform.transform
				temp_contour = contour.convertToFgContour(current_transform)
				
				# - Fix mirrored shapes
				if current_transform.m11() < 0. or current_transform.m22() < 0.:
					if not (current_transform.m11() < 0. and current_transform.m22() < 0.):
						temp_contour.reverse()
				
				temp_contour.draw(pen)

		'''
		# - Process
		for shape in self.shapes(layer):
			for contour in shape.contours:
				if use_fg:
					contour.convertToFgContour(shape.fl_transform.transform).draw(pen)
				else:
					contour.draw(pen)
		'''

		'''
		for anchor in self.anchors(layer):
			anchor.draw(pen)

		for component in self.components(layer):
			component.draw(pen)

		'''

	def drawPoints(self, pen, layer=None):
		''' Utilizes the PointPen protocol'''
		for shape in self.shapes(layer):
			for contour in shape.contours:
				current_transform = shape.fl_transform.transform
				temp_contour = contour.convertToFgContour(current_transform)
				
				# - Fix mirrored shapes
				if current_transform.m11() < 0. or current_transform.m22() < 0.:
					if not (current_transform.m11() < 0. and current_transform.m22() < 0.):
						temp_contour.reverse()
				
				temp_contour.drawPoints(pen)

		'''
		for shape in self.shapes(layer):
			for contour in shape.contours:
				contour.convertToFgContour(shape.fl_transform.transform).drawPoints(pen)
		'''


# -- Exensions -------------------------------------------
class eGlyph(pGlyph):
	'''Extended representation of the Proxy Glyph, adding some advanced functionality

	Constructor:
		pGlyph() - default represents the current glyph and current font
		pGlyph(fgFont, fgGlyph)
	'''
	# - Internal ------------------------------------------
	def _prepareLayers(self, layers, compatible=True):
		'''Internal! Prepares layers to be used in tools using GUI
		Args:
			layers (Bool control tuple(active_layer, masters, masks, services)). Note If all are set to False only the active layer is used.
		Returns:
			list: List of layer names
		'''
		active_layer = self.activeLayer()
		layerBanList = ['#', 'img'] #! Parts or names of layers that are banned for manipulation

		if layers is None:
			return [layer.name for layer in self.layers() if all([item not in layer.name for item in layerBanList])]
		
		elif isinstance(layers, tuple):
			bpass = lambda condition, value: value if condition else []
			
			tempLayers = [] + bpass(layers[0], [active_layer]) + bpass(layers[1], self.masters()) + bpass(layers[2], self.masks()) + bpass(layers[3], self.services())
			layers = list(set([layer.name for layer in tempLayers if all([item not in layer.name for item in layerBanList])]))

			if compatible:
				compatible_layers = []

				for layer_name in layers:
					if active_layer.isCompatible(self.layer(layer_name), True):
						compatible_layers.append(layer_name)

				return compatible_layers
			
			return layers
		
		elif isinstance(layers, list):
			return list(set([layer for layer in layers if all([item not in layer for item in layerBanList])]))	
		else:
			print('ERROR:\tIncorrect layer control definition!')

	def _compatibleLayers(self, layerName=None):
		return [layer.isCompatible(self.layer(layerName), True) for layer in self.layers()]
			
	def _getPointArray(self, layer=None):
		return [(float(node.x), float(node.y)) for node in self.nodes(layer)]

	def _setPointArray(self, PointArray, layer=None, keep_center=False):
		nodeArray = self.nodes(layer)
		
		if keep_center:
			layer_BBox = self.getBounds(layer)
			array_BBox = (	min(PointArray, key= lambda t: t[0])[0], 
							min(PointArray, key= lambda t: t[1])[1],
							max(PointArray, key= lambda t: t[0])[0], 
							max(PointArray, key= lambda t: t[1])[1])

			layer_center = layer_BBox.center()
			center_array = pqt.QtCore.QPointF((array_BBox[0] + array_BBox[2])/2., (array_BBox[1] + array_BBox[3])/2)
			recenter_shift = layer_center - center_array

		if len(PointArray) == len(nodeArray):
			for nid in range(len(PointArray)):
				if keep_center:
					nodeArray[nid].x = PointArray[nid][0] + recenter_shift.x()
					nodeArray[nid].y = PointArray[nid][1] + recenter_shift.y()
				else:
					nodeArray[nid].x, nodeArray[nid].y = PointArray[nid]
		else:
			print('ERROR:\t Incompatible coordinate array provided.')

	def _getServiceArray(self, layer=None):
		layer_advance = [(float(self.layer(layer).advanceWidth), float(self.layer(layer).advanceHeight))]
		layer_anchors = [(float(anchor.point.x()), float(anchor.point.y())) for anchor in self.anchors(layer)]
		return layer_advance + layer_anchors

	def _setServiceArray(self, PointArray, layer=None, set_metrics=True, set_anchors=True):
		if len(PointArray) > 2:
			
			if set_metrics:
				layer_advance = PointArray[0]
				self.setAdvance(layer_advance[0], layer)

			if set_anchors:
				layer_anchors = PointArray[1:]
				anchorArray = self.anchors(layer)

				if len(layer_anchors) == len(anchorArray):
					for aid in range(len(layer_anchors)):
						anchorArray[aid].point = pqt.QtCore.QPointF(*layer_anchors[aid])
			else:
				print('ERROR:\t Incompatible coordinate array provided.')


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

	def setStart(self, layer=None, control=(0,0)):
		contours = self.contours(layer)

		if control == (0,0): 	# BL
			criteria = lambda node : (node.y, node.x)
		elif control == (0,1): 	# TL
			criteria = lambda node : (-node.y, node.x)
		elif control == (1,0): 	# BR
			criteria = lambda node : (node.y, -node.x)
		elif control == (1,1): 	# TR
			criteria = lambda node : (-node.y, -node.x)
		
		for contour in contours:
			onNodes = [node for node in contour.nodes() if node.isOn()]
			newFirstNode = sorted(onNodes, key=criteria)[0]
			contour.setStartPoint(newFirstNode.index)

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
				vector = pqt.QtCore.QLineF(layerCoords[0], layerCoords[1])
			else:
				vector = pqt.QtCore.QLineF(layerCoords[0], origin)
				vector.setAngle(90 - italicAngle)

			vTransform = pqt.QtGui.QTransform()
			vTransform.scale(float(flip[0]), float(flip[1]))
			vector = vTransform.map(vector)

			# - Build
			newg = fl6.flGuideLine(vector)
			newg.name, newg.color, newg.style = name, pqt.QtGui.QColor(color), style
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
		base_shapes = [shape for shape in self.shapes(layer) + self.components(layer) if len(shape.shapeData.name) and shape.shapeData.name not in diactiricalMarks]
		
		if len(base_shapes):
			wShape = base_shapes[bindIndex] if bindIndex is not None else base_shapes[0]
			transform = wShape.transform
				
			if len(wShape.shapeData.name):
				if transform.m11() > 0:
					self.setLSBeq('={}'.format(wShape.shapeData.name, layer))
					self.setRSBeq('={}'.format(wShape.shapeData.name, layer))
				else:
					self.setLSBeq('=rsb("{}")'.format(wShape.shapeData.name, layer))
					self.setRSBeq('=lsb("{}")'.format(wShape.shapeData.name, layer))

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
		

		if isinstance(blendTimes, tuple): blendTimes = pqt.QtCore.QPointF(*blendTimes)
		if isinstance(blendTimes, int): blendTimes = pqt.QtCore.QPointF(float(blendTimes)/100, float(blendTimes)/100)
		if isinstance(blendTimes, float): blendTimes = pqt.QtCore.QPointF(blendTimes, blendTimes)

		if layerA.isCompatible(layerB, True):
			# - Init
			blendLayer = fl6.flLayer('B:{} {}, t:{}'.format(layerA.name, layerB.name, str(blendTimes)))
			
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
				tempLayer = fl6.flLayer('B:{} {}, t:{}'.format(l0.name, l1.name, (tx, ty)))
				
				for shapePair in shapes:
					tempBlend = fl6.flShape(fgt.fgShape(shapePair[0], shapePair[1], tx, ty, 0))
					tempLayer.addShape(tempBlend)

				return tempLayer
			
			return fgInterpolator

	# - Anchors & Pins -----------------------------------------
	def getAttachmentCenters(self, layer, tolerance=5, applyTransform=True, getAll=False):
		'''Return X center of lowest, highest Y of [glyph] for [layer] within given [tolerance]
		Note: Determine diacritic to glyph attachment positions (for anchor placement)
		'''
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

		XminY_left 	= min(coordsAtMinY, key=itemgetter(0))[0]
		XminY_right	= max(coordsAtMinY, key=itemgetter(0))[0]
		XmaxY_left	= min(coordsAtMaxY, key=itemgetter(0))[0]
		XmaxY_right	= max(coordsAtMaxY, key=itemgetter(0))[0]

		XminY_center = (XminY_left + XminY_right)/2
		XmaxY_center = (XmaxY_left + XmaxY_right)/2

		if getAll:
			return XminY_left, XminY_right, XmaxY_left, XmaxY_right, XminY_center, XmaxY_center
		else:
			return XminY, XmaxY

	def getNewBaseCoords(self, layer, adjustTuple, alignTuple, tolerance=5, italic=False, initPosTuple=(0.,0.)):
		'''Calculate Anchor base position
		Args:
			layer (int or str): Layer index or name, works with both
			coordTuple (int/float, int/float): New anchor coordinates or auto aligment offsets*
			alignTuple (str,str): New anchor aligment*
			tolerance (int/float): Outline feature auto detection tolerance*
			initPosTuple (int/float, int/float): Itinital anchor position

		*Aligment rules: (width, height)
			- (None,None) - Uses coordinates given
			- width - (L) Left; (R) Right; (A) Auto Bottom with tolerance; (AT) Auto Top with tolerance; (C) Center;
			- height - (T) Top; (B) Bottom; (C) Center;
		Returns:
			x, y (int/float)
			
		'''
		# - Init
		x, y = adjustTuple
		alignX, alignY = alignTuple
		old_x, old_y = initPosTuple
		bbox = self.layer(layer).boundingBox

		stat_pen = statisticsPen.StatisticsPen()
		self.draw(stat_pen, layer)

		# - Calculate position
		# -- Precalc all base locations
		x_base_dict, y_base_dict = {}, {}

		# --- X
		# X: Auto
		x_base_dict['AL'], x_base_dict['AR'], x_base_dict['ATL'], x_base_dict['ATR'], x_base_dict['A'], x_base_dict['AT'] = self.getAttachmentCenters(layer, tolerance, True, True) 

		x_base_dict['L'] = bbox.x() 							# X: Left
		x_base_dict['R'] = bbox.width() + bbox.x()				# X: Right
		x_base_dict['C'] = bbox.width()/2 + bbox.x()			# X: Center
		x_base_dict['M'] = stat_pen.meanX 						# X: Center of mass
		x_base_dict['S'] = old_x								# X: Shift

		# --- Y
		y_base_dict['B'] = bbox.y()								# Y: Bottom
		y_base_dict['T'] = bbox.height() + bbox.y()				# Y: Top
		y_base_dict['C'] = bbox.height()/2 + bbox.y()			# Y: Center
		y_base_dict['W'] = stat_pen.meanY						# Y: Center of mass
		y_base_dict['S'] = old_y 								# Y: Shift 

		# --- Metrics
		x_base_dict['LSB'] = 0.									# X: Left Side Bearing
		x_base_dict['RSB'] = self.getAdvance(layer)				# X: Right Side Bearing (Advance width)
		x_base_dict['ADM'] = self.getAdvance(layer)/2			# X: Half of the Advance widht (Middle)


		# -- Post calc
		x_base = x_base_dict[alignX] if alignX is not None else 0.
		y_base = y_base_dict[alignY] if alignY is not None else 0.

		if not italic:
			x += x_base 	# x = x + x_base*[1,-1][x_base < 0]
			y += y_base 	# y = y + y_base*[1,-1][y_base < 0]

		else:
			if alignY == 'S' and int(y) == 0:
				y_bases = sorted([0, y_base_dict['B'], y_base_dict['C'], y_base_dict['T']])
				y_base = min(y_bases, key=lambda x:abs(x - old_y)) # Find to which Y value the initial Y value is close to
				y = abs(y_base - old_y)

			base_point = Point(float(x_base), float(y_base))
			base_point.angle = self.italicAngle()

			y += y_base 				# y = y + y_base*[1,-1][y_base < 0]
			x += base_point.solve_width(y)	# point_width = base_point.getWidth(y); x = x + point_width*[1,-1][point_width < 0]

		return x,y

	def dropAnchor(self, name, layer, coordTuple, alignTuple=(None,None), tolerance=5, italic=False):
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
		x, y = self.getNewBaseCoords(layer, coordTuple, alignTuple, tolerance, italic)
		return self.addAnchor((x, y), name, layer)

	def moveAnchor(self, name, layer, coordTuple=(0,0), alignTuple=(None,None), tolerance=5, italic=False):
		'''Move anchor at given layer
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
			flPinPoint
		'''
		# - Init
		anchor = self.layer(layer).findAnchor(name)

		if anchor is not None:
			x, y = self.getNewBaseCoords(layer, coordTuple, alignTuple, tolerance, italic, (anchor.point.x(), anchor.point.y()))
			anchor.point = pqt.QtCore.QPointF(x,y)

		return anchor

	def exprAnchor(self, name, layer, expression_x=None, expression_y=None):
		'''Set anchor expressions at given layer
		Args:
			name (str): Anchor Name
			layer (int or str): Layer index or name, works with both
			expression_x (str): Expression for evaluating anchors X coordinate
			expression_Y (str): Expression for evaluating anchors Y coordinate

		Returns:
			flPinPoint
		'''
		# - Init
		anchor = self.layer(layer).findAnchor(name)

		if anchor is not None:
			if expression_x is not None: anchor.expressionX = expression_x
			if expression_y is not None: anchor.expressionY = expression_y

		return anchor

	# - Shapes (Elements) ---------------------------------------
	def reorder_shapes(self, layer=None, mode=(0,0)):
		'''Auto reorder shapes on given layer using criteria.
		Args:
			layer (int or str): Layer index or name, works with both
			mode (bool, bool): Mode of shape reordering/sorting by (X, Y)
		
		Returns:
			None
		'''
		# - Init
		sort_bbox = []

		# - Process
		for shape in self.shapes(layer):
			bbox = shape.boundingBox
			trans = shape.fl_transform.transform
			base = trans.map(pqt.QtCore.QPointF(bbox.x(), bbox.y()))
			sort_bbox.append((base, shape.id)) # Base of BBoX (X,Y); FL Shape ID uInt
		
		sort_bbox = sorted(sort_bbox, key=lambda a: (a[0].x()*[1,-1][mode[0]], a[0].y()*[1,-1][mode[1]]))
		new_order = [i[1] for i in sort_bbox]

		# - Finish
		self.layer(layer).reorderShapes(new_order) # Reorders shapes by ID

	def ungroup_all_shapes(self, layer=None, applyTransform=True):
		'''Ungroup all shapes at given layer.
		Args:
			layer (int or str): Layer index or name, works with both
			applyTransform (bool): Apply transformation at shape.
		
		Returns:
			None
		'''
		# - Init
		ejected_shapes = [(shape, shape.ejectTo(False, applyTransform)) for shape in self.shapes(layer, deep=False) if len(shape.includesList)]
		
		# - Process
		for shape, eject in ejected_shapes:
			self.layer(layer).addShapes(eject)
			self.layer(layer).removeShape(shape)

	