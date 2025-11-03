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

from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform, TransformOrigin
from typerig.core.objects.utils import Bounds

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.objects.atom import Container
from typerig.core.objects.contour import Contour

# - Init -------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
@register_xml_class
class Shape(Container, XMLSerializable):
	__slots__ = ('name', 'transform', 'identifier', 'parent', 'lib')

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
	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Contours={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def contours(self):
		return self.data

	@property
	def nodes(self):
		shape_nodes = []
		for contour in self.contours:
			shape_nodes += contour.nodes

		return shape_nodes

	@property
	def selected_nodes(self):
		selection = []
		for contour in self.contours:
			selection += contour.selected_nodes

		return selection

	@property
	def selected_indices(self):
		selection = []
		for contour in self.contours:
			selection += contour.selected_indices

		return selection
	
	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		contour_bounds = [contour.bounds for contour in self.data]
		bounds = sum([[(bound.x, bound.y), (bound.xmax, bound.ymax)] for bound in contour_bounds],[])
		return Bounds(bounds)

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
		
		This is an improved version that uses TransformOrigin enum for type safety
		and consistency with other transformation methods.
		
		Arguments:
			entity (Shape, Point, tuple(x,y)):
				Object to align to

			mode (tuple(TransformOrigin, TransformOrigin)):
				Alignment origins for (self, other). Uses TransformOrigin enum.
				For backward compatibility, also accepts string tuples like ('C', 'C')

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
		delta_x, delta_y = 0., 0.
		align_matrix = self.bounds.align_matrix
		
		# Handle mode - support both TransformOrigin enum and legacy string codes
		self_mode = mode[0]
		if isinstance(self_mode, TransformOrigin):
			self_code = self_mode.code
		elif isinstance(self_mode, str):
			self_code = self_mode.upper()
		else:
			raise TypeError('mode[0] must be TransformOrigin or string, got {}'.format(type(self_mode)))
		
		self_x, self_y = align_matrix[self_code]

		if isinstance(entity, self.__class__):
			# Aligning to another shape
			other_align_matrix = entity.bounds.align_matrix
			
			other_mode = mode[1]
			if isinstance(other_mode, TransformOrigin):
				other_code = other_mode.code
			elif isinstance(other_mode, str):
				other_code = other_mode.upper()
			else:
				raise TypeError('mode[1] must be TransformOrigin or string, got {}'.format(type(other_mode)))
			
			other_x, other_y = other_align_matrix[other_code]

			delta_x = other_x - self_x if align[0] else 0.
			delta_y = other_y - self_y if align[1] else 0.

		elif isinstance(entity, Point):
			# Aligning to a point
			delta_x = entity.x - self_x if align[0] else 0.
			delta_y = entity.y - self_y if align[1] else 0.

		elif isinstance(entity, (tuple, list)) and len(entity) == 2:
			# Aligning to a coordinate tuple
			delta_x = entity[0] - self_x if align[0] else 0.
			delta_y = entity[1] - self_y if align[1] else 0.

		else:
			raise TypeError('entity must be Shape, Point, or tuple(x, y), got {}'.format(type(entity)))

		self.shift(delta_x, delta_y)

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
