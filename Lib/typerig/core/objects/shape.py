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

from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.objects.atom import Container
from typerig.core.objects.contour import Contour

# - Init -------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
class Shape(Container):
	__slots__ = ('name', 'transform', 'identifier', 'parent')

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Contour)
		super(Shape, self).__init__(data, default_factory=factory, **kwargs)
		
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

	# -- IO Format ------------------------------
	def to_VFJ(self):
		raise NotImplementedError

	@staticmethod
	def from_VFJ(string):
		raise NotImplementedError

	@staticmethod
	def to_XML(self):
		raise NotImplementedError

	@staticmethod
	def from_XML(string):
		raise NotImplementedError


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

	s = Shape([test], closed=True)

	new = s[0].clone()
	for node in new:
		node.point += 100
	
	s.append(new)
	print(section('Shape'))
	print(s)

	print(section('Shape Bounds'))
	pprint(s.bounds.align_matrix)

	print(section('Shape Contour'))
	pprint(s[0].next)

	print(section('Shape Nodes'))
	print(s.nodes)

	





	
	
