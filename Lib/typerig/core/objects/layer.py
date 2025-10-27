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

from typerig.core.objects.array import PointArray
from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.objects.atom import Container
from typerig.core.objects.shape import Shape

# - Init -------------------------------
__version__ = '0.2.1'

# - Classes -----------------------------
@register_xml_class
class Layer(Container, XMLSerializable): 
	__slots__ = ('name', 'stx', 'sty', 'transform', 'mark', 'advance_width', 'advance_height', 'identifier', 'parent', 'lib')

	XML_TAG = 'layer'
	XML_ATTRS = ['name', 'identifier', 'width', 'height']
	XML_CHILDREN = {'shape': 'shapes'}
	XML_LIB_ATTRS = ['transform', 'stx', 'sty']
	
	def __init__(self, shapes=None, **kwargs):
		factory = kwargs.pop('default_factory', Shape)
		super(Layer, self).__init__(shapes, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		
		self.stx = kwargs.pop('stx', None) 
		self.sty = kwargs.pop('sty', None) 
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', hash(self))
			self.identifier = kwargs.pop('identifier', None)
			self.mark = kwargs.pop('mark', 0)
			self.advance_width = kwargs.pop('width', 0.) 
			self.advance_height = kwargs.pop('height', 1000.) 
	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Shapes={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def has_stems(self):
		return self.stx is not None and self.sty is not None

	@property
	def stems(self):
		return (self.stx, self.sty)

	@stems.setter
	def stems(self, other):
		if isinstance(other, (tuple, list)) and len(other) == 2:
			self.stx, self.sty = other

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
	def signature(self):
		return hash(tuple([node.type for node in self.nodes]))

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

	# - Delta related retrievers -----------
	@property
	def point_array(self):
		return PointArray([node.point for node in self.nodes])

	@point_array.setter
	def point_array(self, other):
		layer_nodes = self.nodes

		if isinstance(other, PointArray) and len(other) == len(layer_nodes):
			for idx in range(len(layer_nodes)):
				layer_nodes[idx].point = other[idx]

	@property
	def anchor_array(self):
		#return [node.tuple for node in self.nodes]
		pass

	@anchor_array.setter
	def anchor_array(self, other):
		'''
		layer_nodes = self.nodes

		if isinstance(other, (tuple, list)) and len(other) == len(layer_nodes):
			for idx in range(len(layer_nodes)):
				layer_nodes[idx].tuple = other[idx]
		'''
		pass

	@property
	def metric_array(self):
		return [(0.,0.), (self.ADV, self.VADV)]

	@metric_array.setter
	def metric_array(self, other):
		if isinstance(other, (tuple, list)) and len(other) == 2 and len(other[1]) == 2:
			#self.ADV, self.VADV = other[1] # Skip VADV for now...
			self.ADV = other[1][0]

	# - Functions --------------------------
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

	# - Delta --------------------------------
	def lerp_function(self, other):
		if not isinstance(other, self.__class__) and not self.is_compatible(other): return

		t0 = self.point_array
		t1 = other.point_array
		func = lambda tx, ty: (t1 - t0) * (tx, ty) + t0

		return func

	def delta_scale_to(self, virtual_axis, width, height, fix_scale_direction=-1, main="node_array" ,extrapolate=False):
		'''Delta Bruter: Brute-force to given dimensions'''
		
		# - Init
		main_array = getattr(self, main)
		main_bounds = Bounds(main_array)
		process_axis = {}

		direction = [1,-1][extrapolate] # Negative for deltas that behave in reverse - investigate?! correlates with extrapolation!
		precision_x = 1.
		precision_y = 1.

		# -- Safety
		sentinel = 0
		cutoff = 1000
		
		# -- Set source and target
		target_x = width
		source_x = main_bounds.width
		diff_x = prev_diff_x = (target_x - source_x)

		target_y = height
		source_y = main_bounds.height
		diff_y = prev_diff_y = (target_y - source_y)

		# -- Set scale and precision
		scale_x = prev_scale_x = 0.99
		scale_y = prev_scale_y = 0.99

		# -- Process
		while (abs(round(diff_x)) != 0 and abs(round(diff_y)) != 0) if fix_scale_direction != -1 else (abs(round(diff_x)) != 0 or abs(round(diff_y)) != 0):
			if sentinel == cutoff:	break

			if abs(diff_x) > abs(prev_diff_x):
				scale_x = prev_scale_x
				precision_x /= 10

			if abs(diff_y) > abs(prev_diff_y):
				scale_y = prev_scale_y
				precision_y /= 10

			prev_scale_x, prev_diff_x = scale_x, diff_x
			prev_scale_y, prev_diff_y = scale_y, diff_y

			scale_x += [+direction,-direction][diff_x < 0]*precision_x
			scale_y += [+direction,-direction][diff_y < 0]*precision_y

			scale_x = scale_x if fix_scale_direction != 1 else scale_y
			scale_y = scale_y if fix_scale_direction != 0 else scale_x

			for attrib, delta_array in virtual_axis.items():
				delta_scale = delta_array.scale_by_stem((self.stx, self.sty), (scale_x, scale_y), (0.,0.), (0.,0.), False, extrapolate)
				process_axis[attrib] = list(delta_scale)
			
			main_bounds = Bounds(process_axis[main])
			
			diff_x = (target_x - main_bounds.width)
			diff_y = (target_y - main_bounds.height)
			
			sentinel += 1

		# - Set Glyph  
		for attrib, data in process_axis.items():
			setattr(self, attrib, data)

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

	new_test = [(t[0]+100, t[1]+100) for t in test]

	l = Layer([[test]])
	print(section('Layer'))
	pprint(l)
		
	print(section('Layer Bounds'))
	pprint(l)

	print(section('Layer Array'))
	pprint(l.point_array)


	print(l.has_stems)
	print(Bounds([(0,0),(100,200)]))

	print(l.to_XML())

	





	
	
