# MODULE: TypeRig / Core / Layer (Object)
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
from typerig.core.objects.shape import Shape

# - Init -------------------------------
__version__ = '0.0.3'

# - Classes -----------------------------
class Layer(Container): 
	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Shape)
		super(Layer, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		self.name = kwargs.pop('name', hash(self))
		self.transform = kwargs.pop('transform', Transform())
		self.identifier = kwargs.pop('identifier', None)
	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Shapes={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def shapes(self):
		return self.data

	@property
	def nodes(self):
		layer_nodes = []
		for shape in self.shapes:
			layer_nodes += shape.nodes

		return layer_nodes

	@property
	def selectedNodes(self):
		selection = []
		for shape in self.shapes:
			selection += shape.selectedNodes

		return selection

	@property
	def selectedIndices(self):
		selection = []
		for shape in self.shapes:
			selection += shape.selectedIndices

		return selection

	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		contour_bounds = [shape.bounds for shape in self.data]
		bounds = sum([[(bound.x, bound.y), (bound.xmax, bound.ymax)] for bound in contour_bounds],[])
		return Bounds(bounds)

	# -- IO Format ------------------------------
	def toVFJ(self):
		raise NotImplementedError

	@staticmethod
	def fromVFJ(string):
		raise NotImplementedError

	@staticmethod
	def toXML(self):
		raise NotImplementedError

	@staticmethod
	def fromXML(string):
		raise NotImplementedError


if __name__ == '__main__':
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

	l = Layer([[test]])
	print(section('Layer'))
	pprint(l)
		
	print(section('Layer Bounds'))
	pprint(l.bounds)

	





	
	
