# MODULE: TypeRig / Core / Shape (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import math

from typerig.core.objects.array import PointArray
from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform, TransformOrigin
from typerig.core.objects.utils import Bounds

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.objects.atom import Container
from typerig.core.objects.contour import Contour
from typerig.core.objects.sdf import SignedDistanceField

# - Init -------------------------------
__version__ = '0.3.2'

# - Classes -----------------------------
@register_xml_class
class Shape(Container, XMLSerializable):
	__slots__ = ('name', 'transform', 'identifier', 'parent', 'lib', '_sdf')

	XML_TAG = 'shape'
	XML_ATTRS = ['name', 'identifier']
	XML_CHILDREN = {'contour': 'contours'}
	XML_LIB_ATTRS = ['transform']

	def __init__(self, contours=None, **kwargs):
		factory = kwargs.pop('default_factory', Contour)
		super(Shape, self).__init__(contours, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())

		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', '')
			self.identifier = kwargs.pop('identifier', None)

		# - SDF cache (not serialized)
		self._sdf = None
	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Contours={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def contours(self):
		return self.data

	@property
	def nodes(self):
		return self._collect('nodes')

	@property
	def selected_nodes(self):
		return self._collect('selected_nodes')

	@property
	def selected_indices(self):
		return self._collect('selected_indices')
	
	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		contour_bounds = [contour.bounds for contour in self.data]
		bounds = sum([[(bound.x, bound.y), (bound.xmax, bound.ymax)] for bound in contour_bounds],[])
		return Bounds(bounds)

	@property
	def signature(self):
		return hash(tuple([node.type for node in self.nodes]))

	# -- SDF -----------------------------
	@property
	def sdf(self):
		'''Cached SignedDistanceField for this shape. 
		None if not yet computed. Use compute_sdf() to populate.
		'''
		return self._sdf

	# -- Delta related retrievers -----------
	@property
	def point_array(self):
		return PointArray([node.point for node in self.nodes])

	@point_array.setter
	def point_array(self, other):
		shape_nodes = self.nodes

		if isinstance(other, PointArray) and len(other) == len(shape_nodes):
			for idx in range(len(shape_nodes)):
				shape_nodes[idx].point = other[idx]

	# - Functions -------------------------------
	def reverse(self):
		self.data = list(reversed(self.data))

	def sort(self, direction=0, mode='BL'):
		contour_bounds = [(contour, contour.bounds.align_matrix[mode.upper()]) for contour in self.contours]
		self.data = [contour_pair[0] for contour_pair in sorted(contour_bounds, key=lambda d: d[1][direction])]

	def set_weight(self, wx, wy):
		'''Set x and y weights (a.k.a. stems) for all nodes'''
		for node in self.nodes:
			node.weight.x = wx
			node.weight.y = wy

	def is_compatible(self, other):
		return self.signature == other.signature

	# - Transformation --------------------------
	def apply_transform(self):
		for node in self.nodes:
			node.x, node.y = self.transform.applyTransformation(node.x, node.y)

	def shift(self, delta_x, delta_y):
		'''Shift the shape by given amount'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=(TransformOrigin.CENTER, TransformOrigin.CENTER), 
	             align=(True, True)):
		'''Align shape to another entity using transformation origins.
		
		Arguments:
			entity (Shape, Point, tuple(x,y)):
				Object to align to

			mode (tuple(TransformOrigin, TransformOrigin)):
				Alignment origins for (self, other). Must use TransformOrigin enum.
				Examples:
				- (TransformOrigin.CENTER, TransformOrigin.CENTER) - align centers
				- (TransformOrigin.BASELINE, TransformOrigin.BASELINE) - align baselines

			align (tuple(bool, bool)):
				Align X, Align Y. Set to False to disable alignment on that axis.
		
		Returns:
			Nothing (modifies shape in place)
			
		Example:
			>>> from typerig.core.objects.transform import TransformOrigin
			>>> 
			>>> # Align shape centers
			>>> shape1.align_to(shape2)  # Uses CENTER by default
			>>> 
			>>> # Align shape1's baseline to shape2's baseline
			>>> shape1.align_to(
			...     shape2,
			...     mode=(TransformOrigin.BASELINE, TransformOrigin.BASELINE)
			... )
			>>> 
			>>> # Align only X axis (Y stays the same)
			>>> shape1.align_to(
			...     shape2,
			...     mode=(TransformOrigin.CENTER_LEFT, TransformOrigin.CENTER_LEFT),
			...     align=(True, False)
			... )
		'''
		align_matrix = self.bounds.align_matrix
		self_x, self_y = align_matrix[mode[0].code]

		if isinstance(entity, self.__class__):
			other_x, other_y = entity.bounds.align_matrix[mode[1].code]
			delta_x = other_x - self_x if align[0] else 0.
			delta_y = other_y - self_y if align[1] else 0.

		elif isinstance(entity, Point):
			delta_x = entity.x - self_x if align[0] else 0.
			delta_y = entity.y - self_y if align[1] else 0.

		elif isinstance(entity, (tuple, list)):
			delta_x = entity[0] - self_x if align[0] else 0.
			delta_y = entity[1] - self_y if align[1] else 0.

		self.shift(delta_x, delta_y)

	# - Delta --------------------------------
	def lerp_function(self, other):
		'''Linear interpolation function between two compatible shapes.
		Args:
			other -> Shape

		Returns:
			lerp function(tx, ty) -> PointArray
		'''
		if not isinstance(other, self.__class__) and not self.is_compatible(other): return

		t0 = self.point_array
		t1 = other.point_array
		func = lambda tx, ty: (t1 - t0) * (tx, ty) + t0

		return func

	def delta_function(self, other):
		'''Adaptive scaling function aggregated over all contours.
		Args:
			other -> Shape: Shape to make delta to (must be compatible)

		Returns:
			Delta function(scale, time, transalte, angle, compensate) that
			modifies this shape's nodes in place.
		'''
		from typerig.core.func.transform import adaptive_scale

		node_array = [(n0.point.tuple, n1.point.tuple, n0.weight.tuple, n1.weight.tuple) for n0, n1 in zip(self.nodes, other.nodes)]
		
		def func(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)):
			for idx in range(len(self.nodes)):
				self.nodes[idx].point = Point(adaptive_scale((node_array[idx][0], node_array[idx][1]), scale, transalte, time, compensate, angle, (node_array[idx][2][0], node_array[idx][3][0], node_array[idx][2][1], node_array[idx][3][1])))

		return func

	# -- SDF methods --------------------------------
	def compute_sdf(self, resolution=10.0, padding=50, steps_per_segment=64, verbose=False):
		'''Compute and cache a SignedDistanceField for all contours in this shape.

		The SDF is stored in self._sdf and can be accessed via the .sdf property.
		Subsequent calls recompute and replace the cached SDF.

		Args:
			resolution (float): Grid cell size in font units.
			padding (float): Extra space around contour bounds.
			steps_per_segment (int): Polyline sampling density.
			verbose (bool): Print progress.

		Returns:
			SignedDistanceField: The computed SDF (also cached as self._sdf).
		'''
		self._sdf = SignedDistanceField(
			self.contours, 
			resolution=resolution, 
			padding=padding, 
			steps_per_segment=steps_per_segment
		)
		self._sdf.compute(verbose=verbose)
		return self._sdf

	def clear_sdf(self):
		'''Clear the cached SDF to free memory.'''
		self._sdf = None

	# -- Outline tools --------------------------------
	def offset_outline(self, distance, curvature_correction=True):
		'''Offset all contours using analytical Bezier normals with miter joins.
		Returns a NEW Shape — does not modify the original.

		Args:
			distance (float): Offset amount in font units.
				Positive = expand (thicken strokes)
				Negative = contract (thin strokes)
			curvature_correction (bool): Scale handles by (1 + d * kappa).

		Returns:
			Shape: New shape with offset contours.
		'''
		new_contours = [contour.offset_outline(distance, curvature_correction) for contour in self.contours]
		return self.__class__(new_contours, name=self.name, transform=self.transform.clone(), proxy=False)

	def offset_outline_inplace(self, distance, curvature_correction=True):
		'''Offset all contours in place using analytical Bezier normals.

		Args:
			distance (float): Offset amount in font units.
			curvature_correction (bool): Scale handles by (1 + d * kappa).
		'''
		for contour in self.contours:
			contour.offset_outline_inplace(distance, curvature_correction)

	def offset_outline_sdf(self, distance, sdf=None, curvature_correction=True, clamp_factor=0.9):
		'''Offset all contours using analytical normals with SDF distance clamping.
		Returns a NEW Shape — does not modify the original.

		Falls back to analytical offset if no SDF is available.

		Args:
			distance (float): Offset amount in font units.
			sdf (SignedDistanceField): Precomputed SDF. Uses cached self._sdf if None.
			curvature_correction (bool): Scale handles by (1 + d * kappa).
			clamp_factor (float): Fraction of medial axis to allow (0.0-1.0).

		Returns:
			Shape: New shape with offset contours.
		'''
		use_sdf = sdf if sdf is not None else self._sdf
		new_contours = [contour.offset_outline_sdf(distance, use_sdf, curvature_correction, clamp_factor) for contour in self.contours]
		return self.__class__(new_contours, name=self.name, transform=self.transform.clone(), proxy=False)

	def offset_outline_sdf_inplace(self, distance, sdf=None, curvature_correction=True, clamp_factor=0.9):
		'''Offset all contours in place using analytical normals with SDF clamping.

		Falls back to analytical offset if no SDF is available.

		Args:
			distance (float): Offset amount in font units.
			sdf (SignedDistanceField): Precomputed SDF. Uses cached self._sdf if None.
			curvature_correction (bool): Scale handles by (1 + d * kappa).
			clamp_factor (float): Fraction of medial axis to allow (0.0-1.0).
		'''
		use_sdf = sdf if sdf is not None else self._sdf

		for contour in self.contours:
			new_contour = contour.offset_outline_sdf(distance, use_sdf, curvature_correction, clamp_factor)
			new_nodes = new_contour.nodes

			if len(new_nodes) == len(contour.nodes):
				for i in range(len(contour.nodes)):
					contour.nodes[i].x = new_nodes[i].x
					contour.nodes[i].y = new_nodes[i].y

	# -- Angle-compensated scaling --------------------------------
	def analyze_contours(self):
		'''Compute dominant orientation angle for each contour in this shape.

		Uses PCA on on-curve node positions to determine the overall
		stroke direction of each contour.

		Returns:
			list[tuple]: List of (contour_index, angle_radians, angle_degrees)
				for each contour in this shape.
		'''
		from typerig.core.func.transform import contour_dominant_angle

		result = []

		for ci, contour in enumerate(self.contours):
			on_curve = [(n.x, n.y) for n in contour.nodes if n.type == 'on']
			angle = contour_dominant_angle(on_curve)
			result.append((ci, angle, math.degrees(angle)))

		return result

	def scale_compensated(self, sx, sy, stx, sty, intensity=1.0,
						  transform_origin=TransformOrigin.BASELINE):
		'''Scale shape with diagonal stroke weight compensation.
		Returns a NEW Shape — does not modify the original.

		Two-pass approach per contour:
		  1. Naive affine scale by (sx, sy)
		  2. Corrective normal offset for diagonal stroke weights

		Args:
			sx (float): Horizontal scale factor (must be > 0)
			sy (float): Vertical scale factor (must be > 0)
			stx (float): Horizontal stem width (vertical stroke width)
			sty (float): Vertical stem width (horizontal stroke width)
			intensity (float): Correction strength. Default 1.0.
			transform_origin (TransformOrigin): Anchor point for scaling.

		Returns:
			Shape: New shape with compensated scaling applied.
		'''
		new_contours = []

		# Get origin point before scaling
		if transform_origin != TransformOrigin.BASELINE:
			source_bounds = self.bounds
			ox, oy = source_bounds.align_matrix[transform_origin.code]

		for contour in self.contours:
			new_contours.append(contour.scale_compensated(sx, sy, stx, sty, intensity))

		result = self.__class__(new_contours, name=self.name, transform=self.transform.clone(), proxy=False)

		# Realign to preserve transformation origin
		if transform_origin != TransformOrigin.BASELINE:
			dest_bounds = result.bounds
			dest_ox, dest_oy = dest_bounds.align_matrix[transform_origin.code]
			result.shift(ox - dest_ox, oy - dest_oy)

		return result

	def scale_compensated_inplace(self, sx, sy, stx, sty, intensity=1.0,
								  transform_origin=TransformOrigin.BASELINE):
		'''Scale shape in place with diagonal stroke weight compensation.

		Two-pass approach per contour:
		  1. Naive affine scale by (sx, sy)
		  2. Corrective normal offset for diagonal stroke weights

		Args:
			sx (float): Horizontal scale factor (must be > 0)
			sy (float): Vertical scale factor (must be > 0)
			stx (float): Horizontal stem width (vertical stroke width)
			sty (float): Vertical stem width (horizontal stroke width)
			intensity (float): Correction strength. Default 1.0.
			transform_origin (TransformOrigin): Anchor point for scaling.
		'''
		# Get origin point before scaling
		if transform_origin != TransformOrigin.BASELINE:
			source_bounds = self.bounds
			ox, oy = source_bounds.align_matrix[transform_origin.code]
			self.shift(-ox, -oy)

		# Apply compensated scale to each contour
		for ci in range(len(self.contours)):
			new_contour = self.contours[ci].scale_compensated(
				sx, sy, stx, sty, intensity
			)
			# Write back node positions
			old_nodes = self.contours[ci].nodes
			new_nodes = new_contour.nodes

			if len(new_nodes) == len(old_nodes):
				for i in range(len(old_nodes)):
					old_nodes[i].x = new_nodes[i].x
					old_nodes[i].y = new_nodes[i].y

		# Restore origin
		if transform_origin != TransformOrigin.BASELINE:
			self.shift(ox, oy)

if __name__ == '__main__':
	from typerig.core.objects.node import Node
	from pprint import pprint
	section = lambda s: '\n+{0}\n+ {1}\n+{0}'.format('-'*30, s)

	test = [(200.0, 280.0),
			(760.0, 280.0),
			(804.0, 280.0),
			(840.0, 316.0),
			(840.0, 360.0),
			(840.0, 600.0),
			(840.0, 644.0),
			(804.0, 680.0),
			(760.0, 680.0),
			(200.0, 680.0),
			(156.0, 680.0),
			(120.0, 644.0),
			(120.0, 600.0),
			(120.0, 360.0),
			(120.0, 316.0),
			(156.0, 280.0)]

	s = Shape([Contour(test, closed=True)])

	new = s[0].clone()
	for node in new:
		node.point += 100
	
	s.append(new)
	print(section('Shape'))
	print(s[0].closed)

	print(section('Shape Bounds'))
	pprint(s.bounds.align_matrix)

	print(section('Shape Contour'))
	pprint(s[0].next)

	print(section('Shape Nodes'))
	print(s.to_XML())