# MODULE: Typerig / Proxy / GS3 / Layer (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# --- GS3 + GS4 host-write quirks: SINGLE SOURCE OF TRUTH ---
#
# This module is the ONE place where host-side mutation of a GSLayer's
# outline is written. Panels and plugin bundles MUST route all writes
# (new paths, appends, clears, replacements) through the trLayer methods
# below, never by importing GSPath / GSNode / GSLINE / ... directly.
#
# Why: GS3 and GS4 differ on how a layer's path collection is written.
#   GS3  — layer.paths is a mutable list; .append() works.
#   GS4  — layer.paths is a read-only proxy (GSProxyShapes); .append()
#          raises. The portable write surface is layer.shapes, assigned
#          as a fresh list that mixes GSPath + GSComponent.
# The dual-safe idiom is: `layer.shapes = list(layer.shapes) + [new]`.
# It works on both versions; use it everywhere via trLayer helpers.
#
# Node construction uses the string API ('line' / 'curve' / 'offcurve')
# which is accepted on both GS3 and GS4. Do NOT import GSLINE / GSCURVE /
# GSOFFCURVE constants in callers; those are GS-version-sensitive and
# unnecessary.
#
# Any new path/shape construction helper belongs here (or in contour.py
# for the GSPath builder). If you find yourself writing a local
# _build_gs_path or layer.paths.append in a panel, you are off-pattern —
# add the helper here and call it. See porting_guide.md anti-pattern #14.
# ---------------------------------------------------------------------

# - Dependencies -------------------------
from __future__ import print_function

import copy

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

	# Sidebearings come from the host: Glyphs measures the true outline
	# (components included) and its setters move everything on the layer.
	# Core Layer.LSB / RSB use the control box of the paths only.
	@property
	def LSB(self):
		return float(self.host.LSB)

	@LSB.setter
	def LSB(self, value):
		self.host.LSB = float(value)

	@property
	def RSB(self):
		return float(self.host.RSB)

	@RSB.setter
	def RSB(self, value):
		self.host.RSB = float(value)

	@property
	def visible(self):
		'''Layer visibility in the edit view (eye icon in the Layers panel).'''
		return bool(getattr(self.host, 'visible', False))

	@visible.setter
	def visible(self, value):
		self.host.visible = bool(value)

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

	# - Host-write API (GS3 + GS4 safe) -----
	# These are the ONLY sanctioned entry points for mutating a layer's
	# shape collection from panels / plugins. See module header.

	def set_shapes(self, shapes):
		'''Replace all shapes (GSPath + GSComponent) on the host layer.

		Args:
			shapes: iterable of GSPath / GSComponent (or trShape — unwrapped).

		GS4-safe: assigns a fresh list to layer.shapes rather than mutating
		the layer.paths proxy.
		'''
		raw = []
		for s in shapes:
			raw.append(s.host if isinstance(s, trShape) else s)
		self.host.shapes = raw
		self.data = self._build_shapes()

	def clear_shapes(self):
		'''Remove every path and component from the host layer.'''
		self.host.shapes = []
		self.data = self._build_shapes()

	def append_shape(self, shape):
		'''Append one GSPath or GSComponent to the host layer.

		GS4-safe: rebuilds the shapes list; never calls layer.paths.append
		or layer.shapes.append (both unreliable or unavailable in GS4).
		'''
		raw = shape.host if isinstance(shape, trShape) else shape
		self.host.shapes = list(self.host.shapes) + [raw]
		self.data = self._build_shapes()

	def append_contour(self, core_contour):
		'''Append a core Contour as a new GSPath on the host layer.

		Converts via _build_gs_path (string-typed, GS3+GS4 compatible) and
		assigns through the GS4-safe shapes idiom. Returns the new GSPath.
		'''
		gs_path = _build_gs_path(core_contour)
		self.host.shapes = list(self.host.shapes) + [gs_path]
		self.data = self._build_shapes()
		return gs_path

	def copy_shapes_from(self, other, clean=False):
		'''Append copies of other's paths and components (clean=True: replace).

		Args:
			other (trLayer): source layer.

		Returns:
			bool: True if other had shapes.
		'''
		incoming = [copy.copy(s) for s in other.host.shapes]
		kept = [] if clean else list(self.host.shapes)
		self.host.shapes = kept + incoming
		self.data = self._build_shapes()
		return bool(incoming)

	def swap_shapes(self, other):
		'''Exchange all paths and components with another trLayer.'''
		mine = [copy.copy(s) for s in self.host.shapes]
		self.set_shapes([copy.copy(s) for s in other.host.shapes])
		other.set_shapes(mine)

	def copy_to_background(self):
		'''Append copies of this layer's shapes to its background
		(Glyphs' counterpart of the FL mask layer).'''
		# Native Path > Copy to Background (GS3 + GS4 GlyphsCore): whole layer
		# (checkSelection False), old background kept (FL: add to the mask).
		# Writing background.shapes from Python stores the shapes but does
		# not show them on Glyphs 4 (user test, 2026-10-17).
		native = getattr(self.host, 'contentToBackgroundCheckSelection_keepOldBackground_', None)
		if native is not None:
			native(False, True)
			return
		# A layer without a background may answer None: start it from a copy
		# of the layer (the documented `layer.background = layer.copy()`).
		# Otherwise append, then assign the background back so a lazily
		# created one is stored on the layer.
		background = self.host.background
		if background is None:
			self.host.background = self.host.copy()
			return
		background.shapes = list(background.shapes) + [copy.copy(s) for s in self.host.shapes]
		self.host.background = background

	def set_locked(self, locked=True):
		'''Lock / unlock every path and component on the layer.'''
		for shape in self.host.shapes:
			shape.locked = bool(locked)

	# - Guides ---------------------------------
	@property
	def _guides_attr(self):
		return 'guides' if hasattr(self.host, 'guides') else 'guideLines'	# GS3+ / GS2

	def copy_guides_from(self, other, clean=False):
		'''Append copies of other's guides (clean=True: replace).'''
		incoming = [copy.copy(g) for g in getattr(other.host, other._guides_attr)]
		kept = [] if clean else list(getattr(self.host, self._guides_attr))
		setattr(self.host, self._guides_attr, kept + incoming)
		return bool(incoming)

	def clear_guides(self):
		setattr(self.host, self._guides_attr, [])

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
		# Separate outline shapes from component shapes using the new Core API.
		# shape.is_component is True when shape.component is a non-empty string.
		# Plain Shape() objects created by the snap tools have component='' → outline.
		outline_shapes   = [s for s in core_layer.shapes if not s.is_component]
		component_shapes = [s for s in core_layer.shapes if s.is_component]

		# Rebuild paths from all outline shape contours
		new_paths = []
		for core_shape in outline_shapes:
			for core_contour in core_shape.contours:
				new_paths.append(_build_gs_path(core_contour))

		# Rebuild components
		new_components = []
		for comp_shape in component_shapes:
			comp = GlyphsApp.GSComponent(comp_shape.component)
			t    = list(comp_shape.transform)   # Transform → [xx, xy, yx, yy, dx, dy]
			if t and t != [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]:
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

		# GSLayer.paths and .components have no setters in GS3 —
		# layer.shapes is the single writable master list.
		self.host.shapes = new_paths + new_components

		# Rebuild anchors
		self.host.anchors = [_build_gs_anchor(a) for a in core_layer.anchors]

		# Metrics
		self.host.width = float(core_layer.advance_width)
		if core_layer.advance_height:
			self.host.vertWidth = float(core_layer.advance_height)

		# Rebuild proxy data
		self.data = self._build_shapes()
