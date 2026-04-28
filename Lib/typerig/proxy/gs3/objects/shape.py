# MODULE: Typerig / Proxy / GS3 / Shape (Objects)
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

from typerig.proxy.gs3.objects.contour import trContour, _build_gs_path
from typerig.core.objects.shape import Shape
from typerig.core.objects.transform import Transform

# - Init ---------------------------------
__version__ = '0.1.0'

# - Helpers ------------------------------
def _build_gs_shape(core_shape):
	'''Build a list of GSPaths from a core Shape.
	Component shapes (shape.is_component is True) return an empty list — caller must handle.
	'''
	if core_shape.is_component:
		return []
	return [_build_gs_path(c) for c in core_shape.contours]

# - Classes ------------------------------
class trShape(Shape):
	'''Proxy bridging the Core Shape model to GlyphsApp.

	GlyphsApp has no explicit "shape" grouping: a layer holds GSPath objects
	and GSComponent objects directly.  trShape handles both cases:

	  Outline shape  — host is the parent GSLayer.
	                   self.data = [trContour per GSPath in layer.paths]
	                   One outline trShape per layer groups all paths.

	  Component shape — host is a GSComponent.
	                    self.data is empty (no editable contours).
	                    Component metadata is accessed via properties.

	Constructor:
		trShape(GSLayer)      — outline shape
		trShape(GSComponent)  — component shape

	Attributes:
		.host:         GSLayer (outline) or GSComponent (component)
		.is_component: True when wrapping a GSComponent
	'''
	__meta__ = {}
	__meta_keys = frozenset()

	_OUTLINE   = 'outline'
	_COMPONENT = 'component'

	# - Initialize ---------------------------
	def __init__(self, host, **kwargs):
		self.host = host

		if isinstance(host, GlyphsApp.GSLayer):
			self._kind = self._OUTLINE
			paths = list(host.paths)
			super(trShape, self).__init__(paths, default_factory=trContour, proxy=True, **kwargs)

		elif isinstance(host, GlyphsApp.GSComponent):
			self._kind = self._COMPONENT
			super(trShape, self).__init__([], default_factory=trContour, proxy=True, **kwargs)

		else:
			raise TypeError('Expected GSLayer or GSComponent, got {}'.format(type(host)))

	# - Internals ----------------------------
	def __getattribute__(self, name):
		if name in trShape.__meta_keys:
			return self.host.__getattribute__(trShape.__meta__[name])
		else:
			return Shape.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trShape.__meta_keys:
			self.host.__setattr__(trShape.__meta__[name], value)
		else:
			Shape.__setattr__(self, name, value)

	# - Properties ---------------------------
	@property
	def is_component(self):
		return self._kind == self._COMPONENT

	@property
	def name(self):
		if self.is_component:
			return self.host.componentName
		return ''

	@name.setter
	def name(self, value):
		if self.is_component:
			self.host.componentName = str(value)

	# --- Component-specific -----------------
	@property
	def component_name(self):
		'''Referenced glyph name (component shapes only).'''
		if self.is_component:
			return self.host.componentName
		return None

	@component_name.setter
	def component_name(self, value):
		if self.is_component:
			self.host.componentName = str(value)

	@property
	def component_transform(self):
		'''Affine transform as a 6-tuple (a, b, c, d, tx, ty) (component only).'''
		if self.is_component:
			t = self.host.transform
			# GS3 returns NSAffineTransformStruct; unpack to plain tuple
			return (float(t.m11), float(t.m12),
					float(t.m21), float(t.m22),
					float(t.tX),  float(t.tY))
		return None

	@component_transform.setter
	def component_transform(self, value):
		'''Set affine transform from a 6-tuple (a, b, c, d, tx, ty).'''
		if self.is_component and value is not None:
			from Foundation import NSAffineTransform, NSAffineTransformStruct
			struct = NSAffineTransformStruct(
				m11=float(value[0]), m12=float(value[1]),
				m21=float(value[2]), m22=float(value[3]),
				tX =float(value[4]), tY =float(value[5])
			)
			transform = NSAffineTransform.transform()
			transform.transformStruct = struct
			self.host.transform = transform

	@property
	def component_offset(self):
		'''Translation offset as (x, y) (component only).'''
		if self.is_component:
			t = self.component_transform
			if t is not None:
				return (t[4], t[5])
		return (0., 0.)

	@component_offset.setter
	def component_offset(self, value):
		'''Set translation while preserving scale/rotation.'''
		if self.is_component:
			t = list(self.component_transform or (1, 0, 0, 1, 0, 0))
			t[4], t[5] = float(value[0]), float(value[1])
			self.component_transform = tuple(t)

	# - Host sync ----------------------------
	def _sync_host(self):
		'''Rebuild the GSLayer shapes list (paths only) from the current proxy contour list.

		GSLayer.paths has no setter in GS3 — layer.shapes is the writable master list.
		Existing GSComponent objects are preserved at the tail of the list.
		'''
		if not self.is_component:
			existing_comps = [s for s in self.host.shapes
			                  if isinstance(s, GlyphsApp.GSComponent)]
			self.host.shapes = [c.host for c in self.data] + existing_comps

	# - Basics --------------------------------
	def reverse(self):
		if not self.is_component:
			self.data = list(reversed(self.data))
			existing_comps = [s for s in self.host.shapes
			                  if isinstance(s, GlyphsApp.GSComponent)]
			self.host.shapes = [c.host for c in self.data] + existing_comps

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Shape.

		Component shapes produce a Shape with:
		  .component  = base glyph name (str)
		  .transform  = placement transform (Transform)
		  .contours   = [] (empty)

		Outline shapes produce a Shape with their contours ejected.
		'''
		if self.is_component:
			t = self.component_transform or (1, 0, 0, 1, 0, 0)
			return Shape(
				[],
				name=self.component_name or '',
				component=self.component_name or '',
				transform=Transform(t[0], t[1], t[2], t[3], t[4], t[5]),
			)

		# Outline: eject each contour from the live layer paths
		core_contours = [trContour(p).eject() for p in self.host.paths]
		return Shape(core_contours)

	def mount(self, core_shape):
		'''Write core Shape data back into the GS3 host.

		For outline shapes, all GSPaths in the host layer are replaced.
		For component shapes, componentName and transform are updated.

		Args:
			core_shape (Shape): Pure core Shape.
			    Component shapes must have core_shape.component set to the base glyph name.
		'''
		if self.is_component:
			if core_shape.is_component:
				self.host.componentName = core_shape.component
				t = list(core_shape.transform)  # Transform supports iteration → [xx,xy,yx,yy,dx,dy]
				if t:
					self.component_transform = tuple(t)
			return

		# Outline: rebuild paths from core contours.
		# GSLayer.paths has no setter — write through layer.shapes instead.
		new_paths      = [_build_gs_path(c) for c in core_shape.contours]
		existing_comps = [s for s in self.host.shapes
		                  if isinstance(s, GlyphsApp.GSComponent)]
		self.host.shapes = new_paths + existing_comps
		self.data = [trContour(p, parent=self) for p in self.host.paths]

		if self.parent is not None and hasattr(self.parent, '_sync_host'):
			self.parent._sync_host()
