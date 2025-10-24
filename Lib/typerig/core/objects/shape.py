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
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.objects.atom import Container
from typerig.core.objects.contour import Contour

# - Init -------------------------------
__version__ = '0.1.7'

# - Classes -----------------------------
@register_xml_class
class Shape(Container, XMLSerializable):
	__slots__ = ('name', 'transform', 'identifier', 'parent', 'lib')

	XML_TAG = 'shape'
	XML_ATTRS = ['name', 'identifier']
	XML_CHILDREN = {'contour': 'contours'}
	XML_LIB_ATTRS = ['transform']

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Contour)
		super(Shape, self).__init__(data, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())

		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', None)
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
		'''Shift the shape by given amout'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=('C','C'), align=(True, True)):
		'''Align contour to a node or line given.
		Arguments:
			entity (Shape, Point, tuple(x,y)):
				Object to align to

			align (tuple(bool, bool)):
				Align X, Align Y

			mode tuple(string, string):
				A special tuple(self, other) that is Bounds().align_matrix:
				'TL', 'TM', 'TR', 'LM', 'C', 'RM', 'BL', 'BM', 'BR', 
				where T(top), B(bottom), L(left), R(right), M(middle), C(center)
		
		Returns:
			Nothing
		'''
		delta_x, delta_y = 0., 0.
		align_matrix = self.bounds.align_matrix
		self_x, self_y = align_matrix[mode[0].upper()]

		if isinstance(entity, self.__class__):
			other_align_matrix = entity.bounds.align_matrix
			other_x, other_y = other_align_matrix[mode[1].upper()]

			delta_x = other_x - self_x if align[0] else 0.
			delta_y = other_y - self_y if align[1] else 0.

		elif isinstance(entity, Point):
			delta_x = entity.x - self_x if align[0] else 0.
			delta_y = entity.y - self_y if align[1] else 0.

		elif isinstance(entity, tuple):
			delta_x = entity.x - entity[0] if align[0] else 0.
			delta_y = entity.y - entity[1] if align[1] else 0.

		else: return

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

	





	
	
