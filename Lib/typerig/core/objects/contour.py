# MODULE: TypeRig / Core / Contour (Object)
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
from typerig.core.objects.line import Line
from typerig.core.objects.array import PointArray
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.func.utils import isMultiInstance
from typerig.core.func.transform import adaptive_scale, lerp

from typerig.core.objects.atom import Container
from typerig.core.objects.node import Node

# - Init -------------------------------
__version__ = '0.3.4'

# - Classes -----------------------------
class Contour(Container): 
	__slots__ = ('name', 'closed', 'clockwise', 'transform', 'parent', 'lib')

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Node)
		super(Contour, self).__init__(data, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', '')
			self.closed = kwargs.pop('closed', False)
			self.clockwise = kwargs.pop('clockwise', self.get_winding())

	# -- Properties -----------------------------
	@property
	def nodes(self):
		return self.data

	@property
	def selected_nodes(self):
		return [node for node in self.nodes if node.selected]

	@property
	def selected_indices(self):
		return [idx for idx in range(len(self.nodes)) if self.nodes[idx].selected]
	
	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		return Bounds([node.point.tuple for node in self.data])

	@property
	def node_segments(self):
		return self.get_segments(get_point=False)

	@property
	def point_segments(self):
		return self.get_segments(get_point=True)

	@property
	def segments(self):
		obj_segments = []

		for segment in self.point_segments:
			if len(segment) == 2:
				obj_segments.append(Line(*segment))

			elif len(segment) == 3:
				# Placeholder for simple TT curves
				raise NotImplementedError

			elif len(segment) == 4:
				obj_segments.append(CubicBezier(*segment))

			else:
				# Placeholder for complex TT curves
				raise NotImplementedError

		return obj_segments

	@property
	def point_array(self):
		return PointArray([node.point for node in self.nodes])

	@point_array.setter
	def point_array(self, other):
		contour_nodes = self.nodes

		if isinstance(other, PointArray) and len(other) == len(contour_nodes):
			for idx in range(len(contour_nodes)):
				contour_nodes[idx].point = other[idx]
		
	# -- Functions ------------------------------
	def set_start(self, index):
		index = self.nodes[index].prev_on.idx if not self.nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index] 

	def get_winding(self):
		'''Check if contour has clockwise winding direction'''
		return self.get_on_area() > 0

	def get_on_area(self):
		'''Get contour area using on curve points only'''
		polygon_area = []

		for node in self.nodes:
			edge_sum = (node.next_on.x - node.x)*(node.next_on.y + node.y)
			polygon_area.append(edge_sum)

		return sum(polygon_area)*0.5

	def get_segments(self, get_point=False):
		assert len(self.data) > 1, 'Cannot return segments for contour with length {}'.format(len(self.data))
		contour_segments = []
		contour_nodes = self.data[:]
		if self.closed: contour_nodes.append(contour_nodes[0])

		while len(contour_nodes):
			node = contour_nodes[0]
			contour_nodes= contour_nodes[1:]
			segment = [node.point] if get_point else [node]

			for node in contour_nodes:
				segment.append(node.point if get_point else node)
				if node.is_on: break

			contour_segments.append(segment)
			contour_nodes = contour_nodes[len(segment)-2:]

		return contour_segments[:-1]

	def reverse(self):
		self.data = list(reversed(self.data))
		#self.clockwise = self.get_winding()
		self.clockwise = not self.clockwise
	
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
		'''Shift the contour by given amout'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=('C','C'), align=(True, True)):
		'''Align contour to a node or line given.
		Arguments:
			entity (Contour, Point, tuple(x,y)):
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
	
	def lerp_function(self, other):
		'''Linear interpolation function to Node or Point
		Args:
			other -> Contour
			
		Returns:
			lerp function(tx, ty) with parameters:
			tx, ty (float, float) : Interpolation times (anisotropic X, Y) 
		'''
		node_array = [(n0.point, n1.point) for n0, n1 in zip(self.nodes, other.nodes)]

		def func(tx, ty):
			for idx in range(len(self.nodes)):
				self.nodes[idx].point = Point(lerp(node_array[idx][0].x, node_array[idx][1].x, tx), lerp(node_array[idx][0].y, node_array[idx][1].y, ty))

		return func	

	def delta_function(self, other):
		'''Adaptive scaling function to Node
		Args:
			other -> Contour

		Returns:
			Delta function(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)) with parameters:
				scale(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
				time(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
				translate(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
				angle -> (radians) : Angle of sharing (for italic designs)  
				compensate(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		'''
		node_array = [(n0.point.tuple, n1.point.tuple, n0.weight.tuple, n1.weight.tuple) for n0, n1 in zip(self.nodes, other.nodes)]
		
		def func(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)):
			for idx in range(len(self.nodes)):
				self.nodes[idx].point = Point(adaptive_scale((node_array[idx][0], node_array[idx][1]), scale, transalte, time, compensate, angle, (node_array[idx][2][0], node_array[idx][3][0], node_array[idx][2][1], node_array[idx][3][1])))

		return func

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

	# - Test Sources
	src_frame = [	Node(200.0, 280.0, type='on'),
					Node(760.0, 280.0, type='on'),
					Node(804.0, 280.0, type='curve'),
					Node(840.0, 316.0, type='curve'),
					Node(840.0, 360.0, type='on'),
					Node(840.0, 600.0, type='on'),
					Node(840.0, 644.0, type='curve'),
					Node(804.0, 680.0, type='curve'),
					Node(760.0, 680.0, type='on', selected=True),
					Node(200.0, 680.0, type='on'),
					Node(156.0, 680.0, type='curve'),
					Node(120.0, 644.0, type='curve'),
					Node(120.0, 600.0, type='on'),
					Node(120.0, 360.0, type='on'),
					Node(120.0, 316.0, type='curve'),
					Node(156.0, 280.0, type='curve')]

	src_square = [	Node(200.0, 280.0, type='on'),
					Node(280.0, 280.0, type='on', selected=True),
					Node(280.0, 200.0, type='on'),
					Node(200.0, 200.0, type='on')]

	src_circle = [	Node(161.0, 567.0, type='on'),
					Node(161.0, 435.0, type='curve'),
					Node(268.0, 328.0, type='curve'),
					Node(400.0, 328.0, type='on', selected=True),
					Node(531.0, 328.0, type='curve'),
					Node(638.0, 435.0, type='curve'),
					Node(638.0, 567.0, type='on'),
					Node(638.0, 698.0, type='curve'),
					Node(531.0, 805.0, type='curve'),
					Node(400.0, 805.0, type='on'),
					Node(268.0, 805.0, type='curve'),
					Node(161.0, 698.0, type='curve')]

	# - Tests
	frame = Contour(src_frame, closed=True)
	square = Contour(src_square, closed=True)
	circle = Contour(src_circle, closed=True)
	print(section('Contour'))
	pprint(frame)
	
	# - rounded_frame segments
	print(section('Segments Nodes'))
	pprint(frame.node_segments)

	print(section('Object Segments'))
	pprint(frame.segments)

	print(section('Truth rounded_frames'))
	print(frame[0] == frame.node_segments[0][0] == frame.segments[0].p0)

	'''
	print(section('Value assignment'))
	tl = frame.segments[0]
	tl.p0.x = 999.999999999
	print(tl, c[0])

	print(section('Change assignment'))
	pprint(c)
	c[0].point -= 900

	print(section('Next and previous on curve finder'))
	print(c[1],c[1].next_on.prev_on)
	'''

	print(section('Bounds'))
	print(frame.bounds)

	print(section('Node operations'))
	print(frame.selected_nodes[0].clockwise)
	print(frame.selected_nodes[0].segment)

	'''
	print(section('Node operations'))
	print(c.selected_nodes[0].triad)
	c.selected_nodes[0].smart_shift(10,10)
	print(c.selected_nodes[0].triad)
	'''
	'''
	print(section('Corner Mitre'))
	pprint(c.nodes)
	print(c.selected_nodes[0].corner_mitre(10))
	pprint(c.nodes)

	print(section('Corner Round'))
	pprint(square.nodes)
	ss = square.selected_nodes[0].corner_round(10, proportion=.5)
	pprint(square.nodes)
	'''
	print(section('Insert After'))
	#pprint(circle.nodes)
	print(circle[0].next)

	print(section('Contour winding'))
	print(frame)
	print(frame.clockwise)
	frame.reverse()
	print(frame.clockwise)
	print(frame)

	

	
	
