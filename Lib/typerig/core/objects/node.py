# MODULE: TypeRig / Core / Node (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math, copy

from typerig.core.func.geometry import ccw
from typerig.core.func.math import ratfrac, randomize

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line, Vector
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.transform import Transform

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.4.0'
node_types = {'on':'on', 'off':'off', 'curve':'curve', 'move':'move'}

# - Classes -----------------------------
class Node(Member): 
	__slots__ = ('x', 'y', 'type', 'name', 'smooth', 'g2', 'selected', 'angle', 'transform', 'identifier','complex_math', 'parent', 'lib')

	def __init__(self, *args, **kwargs):
		super(Node, self).__init__(*args, **kwargs)
		self.parent = kwargs.get('parent', None)

		# - Basics
		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.x, self.y = args[0].x, args[0].y

			if isinstance(args[0], (tuple, list)):
				self.x, self.y = args[0]

		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				self.x, self.y = float(args[0]), float(args[1])
		
		else:
			self.x, self.y = 0., 0.

		self.angle = kwargs.get('angle', 0)
		self.transform = kwargs.get('transform', Transform())
		self.complex_math = kwargs.get('complex', True)

		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.type = kwargs.get('type', node_types['on'])
			self.name = kwargs.get('name', '')
			self.identifier = kwargs.get('identifier', False)
			self.smooth = kwargs.get('smooth', False)
			self.selected = kwargs.get('selected', False)
			self.g2 = kwargs.get('g2', False)

	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: x={}, y={}, type={}>'.format(self.__class__.__name__, self.x, self.y, self.type)

	# -- Properties -----------------------------
	@property
	def index(self):
		return self.idx

	@property
	def contour(self):
		return self.parent

	@property
	def point(self):
		return Point(self.x, self.y, angle=self.angle, transform=self.transform, complex=self.complex_math)

	@point.setter
	def point(self, other):
		if isinstance(other, (self.__class__, Point)):
			self.x = other.x 
			self.y = other.y 
			self.angle = other.angle 
			self.transform = other.transform 
			self.complex_math = other.complex_math 
	
	@property
	def clockwise(self):
		return not ccw(self.prev.point.tuple, self.point.tuple, self.next.point.tuple)
		
	@property
	def is_on(self):
		return self.type == node_types['on']

	@property
	def next_on(self):
		assert self.parent is not None, 'Orphan Node: Cannot find Next on-curve node!'
		currentNode = self.next
		
		while currentNode is not None and not currentNode.is_on:
			currentNode = currentNode.next
		
		return currentNode

	@property
	def prev_on(self):
		assert self.parent is not None, 'Orphan Node: Cannot find Previous on-curve node!'
		currentNode = self.prev
		
		while currentNode is not None and not currentNode.is_on:
			currentNode = currentNode.prev
		
		return currentNode

	@property
	def segment_nodes(self):
		for segment in self.parent.node_segments:
			if self in segment[:1]: return segment
		return
	
	@property
	def segment(self):
		for si in range(len(self.parent.node_segments)):
			if self in self.parent.node_segments[si][:1]: return self.parent.segments[si]
		return

	@property
	def triad(self):
		return (self.prev, self, self.next)

	@property
	def triad_on(self):
		return (self.prev_on, self, self.next_on)

	@property
	def triad_on_max_y(self):
		if self.next_on.point.y > self.prev_on.point.y:
			return self.next_on

		return self.prev_on

	@property
	def triad_on_min_y(self):
		if self.next_on.point.y < self.prev_on.point.y:
			return self.next_on

		return self.prev_on
	
	@property
	def distance_to_next(self):
		return self.distance_to(self.next)

	@property
	def distance_to_prev(self):
		return self.distance_to(self.prev)

	@property
	def distance_to_next_on(self):
		return self.distance_to(self.next_on)

	@property
	def distance_to_prev_on(self):
		return self.distance_to(self.prev_on)

	@property
	def angle_to_next(self):
		return self.angle_to(self.next)

	@property
	def angle_to_prev(self):
		return self.angle_to(self.prev)

	@property
	def angle_to_next_on(self):
		return self.angle_to(self.next_on)

	@property
	def angle_to_prev_on(self):
		return self.angle_to(self.prev_on)
	
	# - Functions ----------------------------
	def distance_to(self, other):
		return self.point.diff_to(other.point)

	def angle_to(self, other):
		return self.point.angle_to(other.point)

	def insert_after(self, time):
		time = float(time)

		if time == 0.:
			new_node = self.clone()
			self.parent.insert(self.idx + 1, new_node)
			return (new_node)

		elif time == 1.:
			new_node = self.next_on.clone()
			self.parent.insert(self.idx + 1, new_node)
			return (new_node)

		elif 0. < time < 1.:
			segment = self.segment
			if isinstance(segment, Line):
				new_node = self.__class__(self.segment.solve_point(time).tuple, type=node_types['on'])
				self.parent.insert(self.idx + 1, new_node)
				return (new_node)

			if isinstance(segment, CubicBezier):
				slices = self.segment.solve_slice(time)

				self.next.point = slices[0].p1
				new_curve_in = self.__class__(slices[0].p2.tuple, type=node_types['curve'])
				new_on = self.__class__(slices[1].p0.tuple, type=node_types['on'], smooth=True)
				new_curve_out = self.__class__(slices[1].p1.tuple, type=node_types['curve'])
				self.next.next.point = slices[1].p2

				self.parent.insert(self.idx + 2, new_curve_in)
				self.parent.insert(self.idx + 3, new_on)
				self.parent.insert(self.idx + 4, new_curve_out)
				
				return (self.segment, self.next_on.segment)	
		return

	def insert_before(self, time):
		return self.prev_on.insert_after(time)

	def insert_after_distance(self, distance): 
		# Note distance is linear only (for now... for Cubic use .solve_distance_start())
		return self.insert_after(ratfrac(distance, self.distance_to_next_on, 1.))

	def insert_before_distance(self, distance):
		# Note distance is linear only (for now... for Cubic use .solve_distance_start())
		return self.insert_before(1. - ratfrac(distance, self.distance_to_prev_on, 1.))

	def remove(self):
		return self.parent.pop(self.idx)

	def update(self):
		raise NotImplementedError

	# - Transformation -----------------------------------------------
	def reloc(self, new_x, new_y):
		'''Relocate the node to new coordinates'''
		self.point = Point(new_x, new_y)
	
	def shift(self, delta_x, delta_y):
		'''Shift the node by given amout'''
		self.point += Point(delta_x, delta_y)

	def smart_reloc(self, new_x, new_y):
		'''Relocate the node and adjacent BCPs to new coordinates'''
		self.smart_shift(new_x - self.x, new_y - self.y)

	def smart_shift(self, delta_x, delta_y):
		'''Shift the node and adjacent BCPs by given amout'''
		
		if self.is_on:	
			for node, test in [(self.prev, not self.prev.is_on), (self, self.is_on), (self.next, not self.next.is_on)]:
				if test: node.shift(delta_x, delta_y)
		else:
			self.shift(delta_x, delta_y)

	def lerp_shift(self, delta_x, delta_y):
		'''Interpolated shift aka Interpolated Nudge.
		
		Arguments:
			shift_x, shift_y (float)
		'''
		if self.is_on:
			# - Init 
			shift = Point(delta_x, delta_y)
			curr_segmet_nodes,  curr_segment = self.segment_nodes, self.segment
			prev_segment_nodes, prev_segment = self.prev_on.segment_nodes, self.prev_on.segment

			# - Process segments
			if isinstance(curr_segment, CubicBezier):
				new_curr = curr_segment.lerp_first(shift)
				
				for node, point in zip(curr_segmet_nodes, new_curr.tuple):
					node.smart_reloc(*point)
				
			# - Process segments
			if isinstance(prev_segment, CubicBezier):
				new_prev = prev_segment.lerp_last(shift)
				
				for node, point in zip(prev_segment_nodes, new_prev.tuple):
					node.smart_reloc(*point)

			if isinstance(curr_segment, Line) and isinstance(prev_segment, Line):
				self.smartShift(*shift.tuple)

	def slant_shift(self, shift_x, shift_y, angle):
		'''Slanted move - move a node (in inclined space) according to Y coordinate slanted at given angle.
		
		Arguments:
			shift_x, shift_y (float)
			angle (float): Angle in degrees
		'''
		# - Init
		new_point = Point((self.x + shift_x, self.y))
		new_point.angle = angle
		
		# - Calculate & set
		new_x = new_point.solve_width(new_point.y + shift_y)
		self.smart_reloc(new_x, self.y + shift_y)

	def randomize(self, cx, cy, bleed_mode=0):
		'''Randomizes the node coordinates within given constrains cx and cy.
		Bleed control trough bleed_mode parameter: 0 - any; 1 - positive bleed; 2 - negative bleed;
		'''
		shift_x, shift_y = randomize(0, cx), randomize(0, cy)
		self.smartShift(shift_x, shift_y)
		
		if bleed_mode > 0:
			if (bleed_mode == 2 and not self.clockwise) or (bleed_mode == 1 and self.clockwise):
				self.smartShift(-shift_x, -shift_y)		

	def align_to(self, entity, align=(True, True), smart=True):
		'''Align current node to a node or line given.
		Arguments:
			entity (Node, Point or Line)
			align (tuple(Align_X (bool), Align_Y (bool)) 
		'''
		if isinstance(entity, (self.__class__, Point)):
			new_x = entity.x if align[0] else self.x
			new_y = entity.y if align[1] else self.y
				
			if smart:
				self.smart_reloc(new_x, new_y)
			else:
				self.reloc(new_x, new_y)

		elif isinstance(entity, (Line, Vector)):
			new_x = entity.solve_x(self.y) if align[0] else self.x
			new_y = entity.solve_y(self.x) if align[1] else self.y

			if smart:
				self.smart_reloc(new_x, new_y)
			else:
				self.reloc(new_x, new_y)

	# - Special ---------------------------------
	def corner_mitre(self, mitre_size=5, is_radius=False):
		# - Calculate unit vectors and shifts
		next_unit = (self.next_on.point - self.point).unit
		prev_unit = (self.prev_on.point - self.point).unit
		
		if not is_radius:
			angle = math.atan2(next_unit | prev_unit, next_unit & prev_unit)
			radius = abs((float(mitre_size)/2.)/math.sin(angle/2.))
		else:
			radius = mitre_size

		next_shift = next_unit * radius
		prev_shift = prev_unit * radius

		# - Insert Node and process
		next_node = self.insert_after(0.) 
		self.shift(*prev_shift.tuple)
		next_node.shift(*next_shift.tuple)

		return (self, next_node)

	def corner_round(self, rounding_size=5, proportion=None, curvature=None, is_radius=False):
		curr_node, next_node = self.corner_mitre(rounding_size, is_radius)
		
		# -- Make round corner
		bcp_out = curr_node.insert_after(0.)
		bcp_in = next_node.insert_before(0.)
		bcp_out.type = node_types['curve']
		bcp_in.type = node_types['curve']

		# -- Curvature and handle length 
		segment = (curr_node, bcp_out, bcp_in, next_node)
		curve = CubicBezier(*[node.point for node in segment])

		if proportion is not None: 
			new_curve = curve.solve_proportional_handles(proportion)
			bcp_out.point = new_curve.p1
			bcp_in.point = new_curve.p2
								
		if curvature is not None: 
			new_curve = curve.solve_hobby(curvature)
			bcp_out.point = new_curve.p1
			bcp_in.point = new_curve.p2
			
		return segment

	def corner_trap(self, parameter=10, depth=50, trap=2, smooth=True, incision=True):
		'''Trap a corner by given incision into the glyph flesh.
		
		Arguments:
			parameter (float): If (incision==False) Width of the traps mouth (opening);
							   If (incision==True) How much to cut into glyphs flesh based from that corner inward;
			depth (float): Length of the traps sides;
			trap (float): Width of the traps bottom;
			smooth (bool): Creates a smooth trap;
			incision (bool): Trapping algorithm control.

		Returns:
			tuple(Node) Ink-trap nodes.
		'''
		# - Calculate for aperture postision and structure
		next_unit = (self.next_on.point - self.point).unit
		prev_unit = (self.prev_on.point - self.point).unit
		
		angle = math.atan2(next_unit | prev_unit, next_unit & prev_unit)
		remains = depth - parameter
		aperture = abs(2*(remains/math.sin(math.radians(90) - angle/2)*math.sin(angle/2))) if incision else parameter

		adjust = float(aperture - trap)/2
		radius = abs((float(aperture)/2.)/math.sin(angle/2.))
		
		# - Calculate points
		b_point = self.point + (next_unit * -radius)
		c_point = self.point + (prev_unit * -radius)

		a_point = self.point + (prev_unit * radius)
		d_point = self.point + (next_unit * radius)

		# - Calculate for depth
		ab_unit = (a_point - b_point).unit
		dc_unit = (d_point - c_point).unit

		b_point = a_point + ab_unit*-depth
		c_point = d_point + dc_unit*-depth

		# - Calculate for trap (size)
		bc_unit = (b_point - c_point).unit
		cb_unit = (c_point - b_point).unit

		b_point += bc_unit*-adjust
		c_point += cb_unit*-adjust

		# - Insert Nodes and cleanup
		b = self.insert_after(0.)
		c = b.insert_after(0.)
		d = c.insert_after(0.)

		# - Position nodes
		self.smart_reloc(*a_point.tuple)
		b.smart_reloc(*b_point.tuple)
		d.smart_reloc(*d_point.tuple)
		c.smart_reloc(*c_point.tuple)

		# - Make smooth trap transition
		if smooth: 
			# -- Create bpcs
			bpc_a = self.insert_after(.6)
			bpc_b = b.insert_before(1.)
			bpc_c = c.insert_after(0.)
			bpc_d = d.insert_before(.4)

			bpc_a.type = node_types['curve']
			bpc_c.type = node_types['curve']
			bpc_b.type = node_types['curve']
			bpc_d.type = node_types['curve']
			self.smooth = True
			d.smooth = True
			return (self, bpc_a, bpc_b, b, c, bpc_c, bpc_d, d)
			
		return (self, b, c, d)

	# -- IO Format ------------------------------
	@property
	def string(self):
		x = int(self.x) if isinstance(self.x, float) and self.x.is_integer() else self.x
		y = int(self.y) if isinstance(self.y, float) and self.y.is_integer() else self.y
		return '{0}{2}{1}'.format(x, y, ' ')

	def to_VFJ(self):
		node_config = []
		node_config.append(self.string)
		if self.smooth: node_config.append('s')
		if not self.is_on: node_config.append('o')
		if self.g2: node_config.append('g2')

		return ' '.join(node_config)

	@staticmethod
	def from_VFJ(string):
		string_list = string.split(' ')
		node_smooth = True if len(string_list) >= 3 and 's' in string_list else False
		node_type = node_types['off'] if len(string_list) >= 3 and 'o' in string_list else node_types['on']
		node_g2 = True if len(string_list) >= 3 and 'g2' in string_list else False

		return Node(float(string_list[0]), float(string_list[1]), type=node_type, smooth=node_smooth, g2=node_g2, name=None, identifier=None)

	@staticmethod
	def to_XML(self):
		raise NotImplementedError

	@staticmethod
	def from_XML(string):
		raise NotImplementedError


if __name__ == '__main__':
	# - Test initialization, normal and rom VFJ
	n0 = Node.from_VFJ('10 20 s g2')
	n1 = Node.from_VFJ('20 30 s')
	n2 = Node(35, 55.65)
	n3 = Node(44, 67, type='smooth')
	n4 = Node(n3)
	print(n3, n4)
	
	# - Test math and VFJ export
	n3.point = Point(34,88)
	n3.point += 30
	print(n3.to_VFJ())
	
	# - Test Containers and VFJ export 
	c = Container([n0, n1, n2, n3, n4], default_factory=Node)
	c.append((99,99))
	print(n0.next)
	
