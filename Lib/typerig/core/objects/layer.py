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

from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.objects.atom import Container
from typerig.core.objects.shape import Shape

# - Init -------------------------------
__version__ = '0.1.7'

# - Classes -----------------------------
class Layer(Container): 
	__slots__ = ('name', 'transform', 'advance_width', 'advance_height', 'identifier', 'parent', 'lib')
	
	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Shape)
		super(Layer, self).__init__(data, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		self.advance_width = kwargs.pop('advance', 0.) 
		self.advance_height = kwargs.pop('advance', 1000.) 
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', hash(self))
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
	def contours(self):
		layer_contours = []
		for shape in self.shapes:
			layer_contours += shape.contours

		return layer_contours

	@property
	def selected_nodes(self):
		selection = []
		for shape in self.shapes:
			selection += shape.selected_nodes

		return selection

	@property
	def selected_indices(self):
		selection = []
		for shape in self.shapes:
			selection += shape.selected_indices

		return selection

	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		contour_bounds = [shape.bounds for shape in self.data]
		bounds = sum([[(bound.x, bound.y), (bound.xmax, bound.ymax)] for bound in contour_bounds],[])
		return Bounds(bounds)

	@property
	def LSB(self):
		'''Layer's Left sidebearing'''
		return self.bounds.x

	@LSB.setter
	def LSB(self, value):
		delta = value - self.LSB
		self.shift(delta, 0.)

	@property
	def RSB(self):
		'''Layer's Right sidebearing'''
		layer_bounds = self.bounds
		return self.ADV - (layer_bounds.x + layer_bounds.width)

	@RSB.setter
	def RSB(self, value):
		delta = value - self.RSB
		self.ADV += delta

	@property
	def BSB(self):
		'''Layer's Bottom sidebearing'''
		return self.bounds.y

	@BSB.setter
	def BSB(self, value):
		delta = value - self.BSB
		self.shift(0., delta)

	@property
	def TSB(self):
		'''Layer's Top sidebearing'''
		layer_bounds = self.bounds
		return layer_bounds.y + layer_bounds.height

	@TSB.setter
	def TSB(self, value):
		delta = value - self.TSB
		self.VADV += delta

	@property
	def ADV(self):
		'''Layer's Advance width'''
		return self.advance_width

	@ADV.setter
	def ADV(self, value):
		self.advance_width = value

	@property
	def VADV(self):
		'''Layer's Advance height'''
		return self.advance_height

	@VADV.setter
	def VADV(self, value):
		self.advance_height = value

	# - Functions --------------------------
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
		'''Shift the layer by given amout'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=('C','C'), align=(True, True)):
		'''Align contour to a node or line given.
		Arguments:
			entity (Layer, Point, tuple(x,y)):
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
	pprint(l)

	





	
	
