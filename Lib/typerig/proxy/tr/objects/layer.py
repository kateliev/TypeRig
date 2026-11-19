# MODULE: Typerig / Proxy / Layer (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import math 

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.tr.objects.shape import trShape, _build_fl_shape, _transform_to_qt
from typerig.proxy.tr.objects.anchor import trAnchor, _build_fl_anchor
from typerig.proxy.tr.objects.guideline import _build_fl_guideline, _fl_to_guideline
from typerig.core.objects.layer import Layer

# - Init --------------------------------
__version__ = '0.1.1'

# - Element references -------------------
def _outline_key(core_shape):
	'''Comparable outline of a core Shape (element space, no transform).'''
	return tuple(
		(bool(c.closed), tuple((float(n.x), float(n.y), str(n.type), bool(n.smooth)) for n in c.nodes))
		for c in core_shape.contours)

def _add_element_reference(fl_layer, fl_shape, transform):
	'''Add a reference to an existing (live) element: the new shape shares
	its flShapeData. Returns the new flShape.

	FontLab 9.0.9809: fl6.flShape(<flShapeData>) no longer works ("Error
	creating object of type flShapeBuilder"); flLayer.addShape(<existing
	flShape>) shares the data, but a single add does not register in
	referenceCount and a later removal under-counts it. Adding twice and
	removing the first registers correctly — the trick ElementComposer
	("Insert") has used since FL6.
	'''
	temp = fl_layer.addShape(fl_shape)
	new = fl_layer.addShape(fl_shape)
	fl_layer.removeShape(temp)
	if transform is not None:
		new.transform = _transform_to_qt(transform)
	return new

# - Classes -----------------------------
class trLayer(Layer):
	'''Proxy to flLayer object

	Constructor:
		trLayer(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'transform', 'identifier', 'parent')
	__meta__ = {'name':'name', 'mark':'mark', 'advance':'advanceWidth', 'advance_width':'advanceWidth', 'advance_height':'advanceHeight'}
	__meta_keys = frozenset(__meta__.keys())
		
	# - Initialize 
	def __init__(self, layer, **kwargs):
		self.host = layer
		super(trLayer, self).__init__(self.host.shapes, default_factory=trShape, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trLayer.__meta_keys:
			return self.host.__getattribute__(trLayer.__meta__[name])
		else:
			return Layer.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trLayer.__meta_keys:
			self.host.__setattr__(trLayer.__meta__[name], value)
		else:
			Layer.__setattr__(self, name, value)

	# - Properties -------------------------------
	@property
	def anchors(self):
		return [trAnchor(a, parent=self) for a in self.host.anchors]

	@anchors.setter
	def anchors(self, other):
		# Clear existing
		while len(self.host.anchors):
			self.host.removeAnchor(self.host.anchors[0])
		# Add new
		for a in other:
			if isinstance(a, trAnchor):
				self.host.addAnchor(a.host)
			else:
				self.host.addAnchor(_build_fl_anchor(a))

	# - Host sync --------------------------------
	def _sync_host(self):
		'''Sync host layer shapes with proxy data.
		Call after individual shape.mount() changes structure.
		'''
		self.host.shapes = [s.host for s in self.data]

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Layer with current FL values.
		The returned Layer has no FL bindings and can be freely manipulated.

		Returns:
			Layer: Pure core Layer with geometry and metrics copied from host.
		'''
		core_shapes = [trShape(s).eject() for s in self.host.shapes]
		core_anchors = [trAnchor(a).eject() for a in self.host.anchors]
		core_guidelines = [_fl_to_guideline(g) for g in (self.host.guidelines or [])]

		return Layer(
			core_shapes,
			name=self.name,
			width=self.advance_width,
			height=self.advance_height,
			mark=self.mark,
			anchors=core_anchors,
			guidelines=core_guidelines,
		)

	def mount(self, core_layer, elements=None):
		'''Write core Layer data back into the FL host.
		Rebuilds all FL shapes from core data and updates metrics.

		Args:
			core_layer (Layer): Pure core Layer with data to apply.

		Example:
			>>> tr_g = trGlyph()
			>>> core_layer = tr_g[0].eject()     # eject first layer
			>>> core_layer.shift(10, 20)          # manipulate
			>>> tr_g[0].mount(core_layer)        # push back
			>>> tr_g.update()                     # notify FL
		'''
		# - Remove existing shapes from host
		for shape in list(self.host.shapes):
			self.host.removeShape(shape)

		# - Build and add new shapes from core data.
		#   elements (dict or None): shared registry {(layer name, element
		#   name): (live flShape, outline key)} across the glyphs of one
		#   mount. A named shape whose outline equals an already mounted
		#   element of the same name on the same layer is LINKED to it (one
		#   shared flShapeData), not rebuilt — the .trfont element model
		#   (handout Stage C.1): the element name on every use is the link.
		for core_shape in core_layer.shapes:
			key = (str(self.host.name), str(core_shape.name)) if (elements is not None and core_shape.name) else None
			outline = _outline_key(core_shape) if key else None

			if key in (elements or {}) and elements[key][1] == outline:
				_add_element_reference(self.host, elements[key][0], core_shape.transform)
				continue

			fl_shape = _build_fl_shape(core_shape)
			self.host.addShape(fl_shape)
			if key and key not in elements:
				elements[key] = (self.host.shapes[-1], outline)

		# - Node smooth flags and names on the LIVE nodes. Set on detached
		#   flNodes before flContour() they read back True in memory but are
		#   not stored on save (verified via .vfj, FL 9.0.9809, 2026-11-19).
		#   Setting smooth on a live node makes FontLab re-align its handles
		#   (uni044B.sc Bold: a handle moved 66 -> 67), so the coordinates are
		#   written back afterwards: the source geometry wins.
		for fl_shape, core_shape in zip(self.host.shapes, core_layer.shapes):
			for fl_contour, core_contour in zip(fl_shape.contours, core_shape.contours):
				fl_nodes = fl_contour.nodes()
				for fl_node, core_node in zip(fl_nodes, core_contour.nodes):
					if core_node.smooth:
						fl_node.smooth = True
					name = getattr(core_node, 'name', '')
					if name:
						fl_node.name = name
				for fl_node, core_node in zip(fl_nodes, core_contour.nodes):
					fl_node.x = float(core_node.x)
					fl_node.y = float(core_node.y)

		while len(self.host.anchors):
			self.host.removeAnchor(self.host.anchors[0])

		for core_anchor in core_layer.anchors:
			self.host.addAnchor(_build_fl_anchor(core_anchor))

		# - Replace guidelines
		# FL's flLayer exposes guideline mutation via clearGuidelines /
		# appendGuidelines. Fall back to removing one-by-one if the bulk
		# clear API isn't available.
		try:
			self.host.clearGuidelines()
		except AttributeError:
			while len(self.host.guidelines):
				try:
					self.host.removeGuideline(self.host.guidelines[0])
				except AttributeError:
					break

		core_guidelines = getattr(core_layer, 'guidelines', None) or []
		if core_guidelines:
			self.host.appendGuidelines([_build_fl_guideline(g) for g in core_guidelines])

		# - Copy metrics
		self.host.advanceWidth = core_layer.advance_width
		self.host.advanceHeight = core_layer.advance_height

		# - Rebuild proxy data
		self.data = [trShape(s, parent=self) for s in self.host.shapes]
