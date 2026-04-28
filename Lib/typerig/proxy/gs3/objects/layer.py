# MODULE: Typerig / Proxy / GS3 / Layer (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import GlyphsApp

from typerig.proxy.gs3.objects.shape  import trShape, _build_gs_shape
from typerig.proxy.gs3.objects.anchor import trAnchor, _build_gs_anchor
from typerig.proxy.gs3.objects.contour import _build_gs_path
from typerig.core.objects.layer import Layer

# - Init ---------------------------------
__version__ = '0.1.0'

# - Classes ------------------------------
class trLayer(Layer):
	'''Proxy to GSLayer object.

	Layer data (self.data) is laid out as:
	  [trShape(outline)]          — one virtual outline shape wrapping all GSPaths;
	                                absent when the layer has no paths
	  [trShape(comp), ...]        — one trShape per GSComponent

	Constructor:
		trLayer(GSLayer)

	Attributes:
		.host (GSLayer): wrapped GlyphsApp layer
	'''
	# advance_width / advance_height need None-guarding (vertWidth can be None)
	# so they are explicit properties; only name goes through __meta__
	__meta__ = {'name': 'name'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, layer, **kwargs):
		self.host = layer
		shapes = self._build_shapes()
		super(trLayer, self).__init__(shapes, default_factory=trShape, proxy=True, **kwargs)

	# - Internals ----------------------------
	def _build_shapes(self):
		shapes = []
		if list(self.host.paths):
			shapes.append(trShape(self.host))
		for comp in self.host.components:
			shapes.append(trShape(comp))
		return shapes

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

	# - Properties ---------------------------
	@property
	def advance_width(self):
		return float(self.host.width)

	@advance_width.setter
	def advance_width(self, value):
		self.host.width = float(value)

	@property
	def advance_height(self):
		vh = self.host.vertWidth
		return float(vh) if vh is not None else 0.

	@advance_height.setter
	def advance_height(self, value):
		if value:
			self.host.vertWidth = float(value)

	@property
	def anchors(self):
		return [trAnchor(a, parent=self) for a in self.host.anchors]

	@anchors.setter
	def anchors(self, other):
		new_anchors = []
		for a in other:
			if isinstance(a, trAnchor):
				new_anchors.append(a.host)
			else:
				new_anchors.append(_build_gs_anchor(a))
		self.host.anchors = new_anchors

	# - Host sync ----------------------------
	def _sync_host(self):
		'''No-op: outline trShape writes to layer.paths directly.'''
		pass

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Layer.'''
		core_shapes  = [s.eject() for s in self.data]
		core_anchors = [trAnchor(a).eject() for a in self.host.anchors]

		return Layer(
			core_shapes,
			name=self.name,
			width=self.advance_width,
			height=self.advance_height,
			anchors=core_anchors,
		)

	def mount(self, core_layer):
		'''Write core Layer data back into the GS3 host.
		Replaces all paths, components, and anchors, then updates metrics.

		Args:
			core_layer (Layer): Pure core Layer with data to apply.

		Example:
			>>> tr_g = trGlyph()
			>>> core_layer = tr_g[0].eject()
			>>> core_layer.shift(10, 20)
			>>> tr_g[0].mount(core_layer)
			>>> tr_g.update()
		'''
		# Separate outline shapes from component shapes
		outline_shapes   = [s for s in core_layer.shapes if not s.lib.get('component_name')]
		component_shapes = [s for s in core_layer.shapes if s.lib.get('component_name')]

		# Rebuild paths from all outline shape contours
		new_paths = []
		for core_shape in outline_shapes:
			for core_contour in core_shape.contours:
				new_paths.append(_build_gs_path(core_contour))
		self.host.paths = new_paths

		# Rebuild components
		new_components = []
		for comp_shape in component_shapes:
			comp = GlyphsApp.GSComponent(comp_shape.lib['component_name'])
			t    = comp_shape.lib.get('component_transform')
			if t is not None:
				from Foundation import NSAffineTransform, NSAffineTransformStruct
				struct = NSAffineTransformStruct(
					m11=float(t[0]), m12=float(t[1]),
					m21=float(t[2]), m22=float(t[3]),
					tX =float(t[4]), tY =float(t[5])
				)
				transform = NSAffineTransform.transform()
				transform.transformStruct = struct
				comp.transform = transform
			new_components.append(comp)
		self.host.components = new_components

		# Rebuild anchors
		self.host.anchors = [_build_gs_anchor(a) for a in core_layer.anchors]

		# Metrics
		self.host.width = float(core_layer.advance_width)
		if core_layer.advance_height:
			self.host.vertWidth = float(core_layer.advance_height)

		# Rebuild proxy data
		self.data = self._build_shapes()
