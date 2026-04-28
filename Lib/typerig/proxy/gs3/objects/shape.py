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

# - Init ---------------------------------
__version__ = '0.1.0'

# - Helpers ------------------------------
def _build_gs_shape(core_shape):
	'''Build a list of GSPaths from a core Shape.
	Component shapes (identified by lib key) return None — caller must handle.
	'''
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
		'''Rebuild GSLayer.paths from current proxy contour list (outline only).'''
		if not self.is_component:
			self.host.paths = [c.host for c in self.data]

	# - Basics --------------------------------
	def reverse(self):
		if not self.is_component:
			self.data = list(reversed(self.data))
			self.host.paths = [c.host for c in self.data]

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Shape.

		For component shapes the component metadata is preserved in shape.lib
		so it can be round-tripped via mount().
		'''
		if self.is_component:
			core_shape = Shape([], name=self.component_name or '')
			core_shape.lib = {
				'component_name':      self.component_name,
				'component_transform': self.component_transform,
			}
			return core_shape

		# Outline: eject each contour from the live layer paths
		core_contours = [trContour(p).eject() for p in self.host.paths]
		return Shape(core_contours)

	def mount(self, core_shape):
		'''Write core Shape data back into the GS3 host.

		For outline shapes, all GSPaths in the host layer are replaced.
		For component shapes, componentName and transform are updated.

		Args:
			core_shape (Shape): Pure core Shape.  Component shapes must carry
			    the 'component_name' key in core_shape.lib.
		'''
		if self.is_component:
			lib        = getattr(core_shape, 'lib', None) or {}
			comp_name  = lib.get('component_name')
			if comp_name:
				self.host.componentName = comp_name
			comp_transform = lib.get('component_transform')
			if comp_transform:
				self.component_transform = comp_transform
			return

		# Outline: rebuild paths from core contours
		new_paths = [_build_gs_path(c) for c in core_shape.contours]
		self.host.paths = new_paths
		self.data = [trContour(p, parent=self) for p in self.host.paths]

		if self.parent is not None and hasattr(self.parent, '_sync_host'):
			self.parent._sync_host()
