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

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.func.utils import isMultiInstance
from typerig.core.func.transform import adaptive_scale, lerp
from typerig.core.func.math import zero_matrix, solve_equations, hobby_control_points

from typerig.core.objects.atom import Container
from typerig.core.objects.node import Node, Knot

# - Init -------------------------------
__version__ = '0.3.9'

# - Classes -----------------------------
@register_xml_class
class Contour(Container, XMLSerializable): 
	__slots__ = ('name', 'closed', 'clockwise', 'transform', 'parent', 'lib')

	XML_TAG = 'contour'
	XML_ATTRS = ['name', 'identifier']
	XML_CHILDREN = {'point': 'nodes'}
	XML_LIB_ATTRS = ['transform', 'closed', 'clockwise']

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Node)
		super(Contour, self).__init__(data, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		
		# - Metadata
		self.name = kwargs.pop('name', None)
		self.closed = kwargs.pop('closed', False)
		self.clockwise = kwargs.pop('clockwise', self.get_winding())

	# -- Properties -----------------------------
	@property
	def nodes(self):
		return self.data

	@nodes.setter
	def nodes(self, other):
		if isinstance(other, self.__class__):
			self.data = other

		if isinstance(other, (tuple, list)):
			for item in other:
				if not isinstance(item, self._subclass):
					item = self._subclass(item, parent=self)
					self.data.append(item)

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

class HobbySpline(Container): 
	'''Adapted from mp2tikz.py (c) 2012 JL Diaz'''

	def __init__(self, data=None, **kwargs):
		# - Init
		factory = kwargs.pop('default_factory', Knot)

		super(HobbySpline, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		self.tension = kwargs.pop('tension', 1.)
		self.transform = kwargs.pop('transform', Transform())
		self.name = kwargs.pop('name', '')
		self.closed = kwargs.pop('closed', False)
		self.clockwise = kwargs.pop('clockwise', self.get_winding())
		self.curl_start = kwargs.pop('curl_start', 1.)
		self.curl_end = kwargs.pop('curl_end', self.curl_start)

	# - Internals ------------------------------
	def __getitem__(self, index):
		"""Gets the point [i] of the list, but assuming the list is
		circular and thus allowing for indexes greater than the list
		length"""
		index %= len(self.data)
		return self.data[index]

	# - Functions ------------------------------
	def __build_coefficients(self):
		'''This function creates five vectors which are coefficients of a
		linear system which allows finding the right values of 'theta' at
		each point of the path (being 'theta' the angle of departure of the
		path at each point). The theory is from METAFONT book.'''
		
		# - Init
		A=[]; B=[]; C=[]; D=[]; R=[];

		if not self.closed:
			A.append(0) 
			B.append(0)
			
			xi_0 = (self[0].alpha**2) * self.curl_start / (self[1].beta**2)
			
			C.append(xi_0*self[0].alpha + 3 - self[1].beta)
			D.append((3 - self[0].alpha)*xi_0 + self[1].beta)
			R.append(-D[0]*self[1].xi)
		
		for k in self.knot_count:
			A.append(   self[k-1].alpha  / ((self[k].beta**2)  * self[k].d_ant))
			B.append((3-self[k-1].alpha) / ((self[k].beta**2)  * self[k].d_ant))
			C.append((3-self[k+1].beta)  / ((self[k].alpha**2) * self[k].d_post))
			D.append(   self[k+1].beta   / ((self[k].alpha**2) * self[k].d_post))
			R.append(-B[k] * self[k].xi  - D[k] * self[k+1].xi)
		
		if not self.closed:
			n = len(R)
			C.append(0)
			D.append(0)

			xi_n = (self[n].beta**2) * self.curl_end / (self[n-1].alpha**2)

			A.append((3 - self[n].beta)*xi_n + self[n-1].alpha)
			B.append(self[n].beta*xi_n + 3 - self[n-1].alpha)
			R.append(0)

		return (A, B, C, D, R)
		
	# - Procedures ----------------------------
	def __solve_for_thetas(self, A, B, C, D, R):
		'''This function receives the five vectors created by
		__build_coefficients() and uses them to build a linear system with N
		unknonws (being N the number of points in the path). Solving the system
		finds the value for theta (departure angle) at each point'''
		L=len(R)
		a = zero_matrix(L, L)
		b = [[i] for i in R]
		
		for k in range(L):
			prev = (k-1)%L
			post = (k+1)%L
			a[k][prev] = A[k]
			a[k][k]    = B[k]+C[k]
			a[k][post] = D[k]
			
		v = solve_equations(a, b)

		return sum(v,[])

	def __solve_angles(self):
		'''This function receives a path in which each point is 'open', i.e. it
		does not specify any direction of departure or arrival at each node,
		and finds these directions in such a way which minimizes 'mock
		curvature'. The theory is from METAFONT book.'''

		# Basically it solves
		# a linear system which finds all departure angles (theta), and from
		# these and the turning angles at each point, the arrival angles (phi)
		# can be obtained, since theta + phi + xi = 0  at each knot'''

		x = self.__solve_for_thetas(*self.__build_coefficients())
		L = len(self)

		for k in range(L):
			self[k].theta = x[k]

		for k in range(L):
			self[k].phi = - self[k].theta - self[k].xi

	def __find_controls(self):
		'''This function receives a path in which, for each point, the values
		of theta and phi (leave and enter directions) are known, either because
		they were previously stored in the structure, or because it was
		computed by function __solve_angles(). From this path description
		this function computes the control points for each knot and stores
		it in the path. After this, it is possible to print path to get
		a string suitable to be feed to tikz.'''

		# - Calculate bezier control points
		for kid in range(len(self.knots)):
			z0 = self[kid].complex
			z1 = self[kid + 1].complex
			theta = self[kid].theta
			phi = self[kid + 1].phi
			alpha = self[kid].alpha
			beta = self[kid + 1].beta

			u, v = hobby_control_points(z0, z1, theta, phi, alpha, beta)

			self[kid].u_right = u
			self[kid + 1].v_left = v

	def reverse(self):
		self.data = list(reversed(self.data))
		#self.clockwise = self.get_winding()
		self.clockwise = not self.clockwise

	def set_start(self, index):
		index = self.nodes[index].prev_on.idx if not self.nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index] 

	def get_winding(self):
		'''Check if contour has clockwise winding direction'''
		return self.get_area() > 0

	def get_area(self):
		'''Get contour area using on curve points only'''
		polygon_area = []

		for knot in self.knots:
			edge_sum = (knot.next.x - knot.x)*(knot.next.y + knot.y)
			polygon_area.append(edge_sum)

		return sum(polygon_area)*0.5

	# - Transformation --------------------------
	def apply_transform(self):
		for knot in self.knots:
			knot.x, knot.y = self.transform.applyTransformation(knot.x, knot.y)

	def shift(self, delta_x, delta_y):
		for knot in self.knots:
			knot.point += Point(delta_x, delta_y)

	# - Properties -----------------------------------
	@property
	def knots(self):
		return self.data

	@knots.setter
	def knots(self, other):
		if isinstance(other, self.__class__):
			self.data = other

		if isinstance(other, (tuple, list)):
			for item in other:
				if not isinstance(item, self._subclass):
					item = self._subclass(item, parent=self)
					self.data.append(item)

	@property
	def knot_count(self):
		if self.closed:
			return range(len(self.data))
		else:
			return range(1, len(self.data) - 1)

	@property
	def tension(self):
		return self.global_tension

	@tension.setter
	def tension(self, other):
		self.global_tension = other
		
		for knot in self.knots:
			knot.alpha = other
			knot.beta = other

	@property
	def bounds(self):
		assert len(self.knots) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.knots))
		return Bounds([knot.point.tuple for knot in self.knots])

	@property
	def nodes(self):
		self.__solve_angles()
		self.__find_controls()

		# - Init
		return_nodes = []
		count = len(self.knots)
		last = 1

		# - Calculate beziers
		if self.closed:
			last = 0

		for kid in range(count - last):
			post = (kid + 1) %count
			z = self.knots[kid].point
			u = Point(self.knots[kid].u_right.real, self.knots[kid].u_right.imag)
			v = Point(self.knots[post].v_left.real, self.knots[post].v_left.imag)
			return_nodes.append([Node(z.x, z.y, type='on'), Node(u.x, u.y, type='curve'), Node(v.x, v.y, type='curve')])
		
		if self.closed:
			last_z = self[0].point
		else:
			last_z = self[-1].point
		
		return_nodes.append([Node(last_z.x, last_z.y, type='on')])
		
		return sum(return_nodes, [])



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

	hobby_test = HobbySpline([(0,320), (320,640), (640,320), (320,0)])
	hobby_test.tension = 1.1
	print(hobby_test.knots)
	print(hobby_test.nodes)
	'''
	print(section('Serialization'))
	print(frame.to_XML())
	

	
	
