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
from typerig.core.func.transform import adaptive_scale, lerp

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line, Vector
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.transform import Transform

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.5.4'
node_types = {'on':'on', 'off':'off', 'curve':'curve', 'move':'move'}

# - Classes -----------------------------
@register_xml_class
class Node(Member, XMLSerializable): 
	__slots__ = ('x', 'y', 'type', 'name', 'smooth', 'g2', 'selected', 'angle', 'transform', 'identifier','complex_math','weight', 'parent', 'lib')

	XML_TAG = 'node'
	XML_ATTRS = ['x', 'y', 'type', 'smooth']
	XML_LIB_ATTRS = ['g2', 'transform']


	def __init__(self, *args, **kwargs):
		super(Node, self).__init__(*args, **kwargs)

		# - Basics
		x = y = 0.0

		if len(args) == 1:
			arg = args[0]

			if isinstance(arg, (Point, self.__class__)):
				x, y = arg.x, arg.y

			elif isinstance(arg, (tuple, list)) and len(arg) == 2:
				x, y = map(float, arg)

			else:
				raise TypeError(
					"Single argument must be a Point, Node, or (x, y) tuple/list"
				)

		elif len(args) == 2:
			if all(isinstance(a, (int, float)) for a in args):
				x, y = map(float, args)
			else:
				raise TypeError("Two arguments must be numeric (x, y)")

		elif len(args) > 2:
			raise TypeError("Expected 0, 1, or 2 positional arguments")

		# - Basic
		self.x = kwargs.pop('x', x)
		self.y = kwargs.pop('y', y)

		# - Basic
		self.angle = kwargs.pop('angle', 0)
		self.transform = kwargs.pop('transform', Transform())
		self.complex_math = kwargs.pop('complex', True)
		self.weight = Point(kwargs.pop('weight', (0.,0.)))

		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.type = kwargs.pop('type', node_types['on'])
			self.name = kwargs.pop('name', '')
			self.identifier = kwargs.pop('identifier', False)
			self.smooth = kwargs.pop('smooth', False)
			self.selected = kwargs.pop('selected', False)
			self.g2 = kwargs.pop('g2', False)

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
	def tuple(self):
		return (self.x, self.y)

	@property
	def complex(self):
		return complex(self.x, self.y)

	@tuple.setter
	def tuple(self, other):
		if isinstance(other, (tuple, list)) and len(other)==2:
			self.x = float(other[0])
			self.y = float(other[1])

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

	@property
	def angle_poly_turn(self):
		temp_point = (self.next_on.point - self.point)/(self.point - self.prev_on.point)
		return math.atan2(temp_point.y, temp_point.x) # Arg (Argument): math.atan2(z.imag, z.real)

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

	# - Drawing ------------------------------------------------------
	def line_to(self, other):
		if not isinstance(other, self.__class__):
			other = self.__class__(other)

		self.parent.insert(self.idx + 1, other)
		
		return other

	def curve_to(self, self_bcp_out, other_bcp_in, other):
		if not isinstance(self_bcp_out, self.__class__):
			self_bcp_out = self.__class__(self_bcp_out)
			self_bcp_out.type = node_types['curve']

		if not isinstance(other_bcp_in, self.__class__):
			other_bcp_in = self.__class__(other_bcp_in)
			other_bcp_in.type = node_types['curve']

		if not isinstance(other, self.__class__):
			other = self.__class__(other)
			other.type = node_types['on']

		self.parent.insert(self.idx + 1, self_bcp_out)
		self.parent.insert(self.idx + 2, other_bcp_in)
		self.parent.insert(self.idx + 3, other)
		
		return self_bcp_out, other_bcp_in, other

	# - Transformation -----------------------------------------------
	def apply_transform(self):
		self.x, self.y = self.transform.applyTransformation(self.x, self.y)
		
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
		new_x, new_y = 0., 0.

		if isinstance(entity, (self.__class__, Point)):
			new_x = entity.x if align[0] else self.x
			new_y = entity.y if align[1] else self.y
				
		elif isinstance(entity, (Line, Vector)):
			new_x = entity.solve_x(self.y) if align[0] else self.x
			new_y = entity.solve_y(self.x) if align[1] else self.y
		
		else: return

		if smart:
			self.smart_reloc(new_x, new_y)
		else:
			self.reloc(new_x, new_y)

	def lerp_to(self, entity, time):
		'''Perform linear interpolation
		Args:
			entity -> Node or Point : Object to make delta to
			time(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 

		Returns:
			None
		'''
		tx, ty = time
		self.point = Point(lerp(self.x, entity.x, tx), lerp(self.y, entity.y, ty))

	def lerp_function(self, entity):
		'''Linear interpolation function to Node or Point
		Args:
			entity -> Node or Point : Object to make delta to
			
		Returns:
			lerp function(tx, ty) with parameters:
			tx, ty (float, float) : Interpolation times (anisotropic X, Y) 
		'''
		x0, y0 = self.point.tuple
		x1, y1 = entity.x, entity.y

		def func(tx, ty):
			self.point = Point(lerp(x0, x1, tx), lerp(y0, y1, ty))

		return func

	def delta_to(self, other, scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)):
		'''Perform adaptive scaling by keeping the stem/stroke weights
		Args:
			other -> Node: Object to make delta to
			scale(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
			time(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
			translate(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
			angle -> (radians) : Angle of sharing (for italic designs)  
			compensate(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)

		Returns:
			None
		'''
		self.point = Point(adaptive_scale(((self.x, self.y), (other.x, other.y)), scale, transalte, time, compensate, angle, (self.weight.x, self.weight.y, other.weight.x, other.weight.y)))

	def delta_function(self, other):
		'''Adaptive scaling function to Node
		Args:
			other -> Node: Object to make delta to

		Returns:
			Delta function(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)) with parameters:
				scale(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
				time(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
				translate(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
				angle -> (radians) : Angle of sharing (for italic designs)  
				compensate(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		'''
		x0, y0 = self.point.tuple
		x1, y1 = other.point.tuple
		weights = (self.weight.x, other.weight.x, self.weight.y, other.weight.y)
		
		def func(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)):
			self.point = Point(adaptive_scale(((x0, y0), (x1, y1)), scale, transalte, time, compensate, angle, weights))

		return func

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
		return f'{x} {y}'

	def to_VFJ(self):
		flags = [
			self.string,
			's' if self.smooth else None,
			'o' if not self.is_on else None,
			'g2' if self.g2 else None
		]
		return ' '.join(filter(None, flags))

	@classmethod
	def from_VFJ(cls, string):
		parts = string.split()
		flags = set(parts[2:])  # All parts after x and y coordinates
		
		return cls(
			float(parts[0]),
			float(parts[1]),
			type=node_types['off'] if 'o' in flags else node_types['on'],
			smooth='s' in flags,
				g2='g2' in flags,
				name=None,
				identifier=None
			)

	@classmethod
	def from_tuple(cls, coords, **kwargs):
		'''Create Node from tuple/list of coordinates.'''
		return cls(coords[0], coords[1], **kwargs)
	
	@classmethod
	def from_object(cls, other, **kwargs):
		'''Clone Node from another Object (Node or Point) instance.'''
		return cls(other.x, other.y, **kwargs)

class Knot(Member):
	def __init__(self, x=0., y=0. , **kwargs):
		super(Knot, self).__init__(**kwargs)

		self.x = float(x)
		self.y = float(y)

		# - Metadata
		self.type = 'on'
		self.name = kwargs.pop('name', '')
		self.identifier = kwargs.pop('identifier', False)
		self.parent = kwargs.pop('parent', None)
		self.angle = kwargs.pop('angle', 0)
		self.transform = kwargs.pop('transform', Transform())
		self.complex_math = kwargs.pop('complex', True)

		# - Hobby Specific
		# -- Tension at point (1. by default)
		self.alpha = kwargs.pop('alpha', 1.) 
		self.beta = kwargs.pop('beta', 1.)
		
		# -- Angle at which the path leaves
		self.theta = kwargs.pop('theta', 0.)
		
		# -- Angle at which the path enters
		self.phi = kwargs.pop('phi', 0.)

		# -- Control points of the Bezier curve at this point
		self.v_left = complex(0,0)
		self.u_right = complex(0,0)
	
	# -- Properties -----------------------------
	@property
	def index(self):
		return self.idx

	@property
	def contour(self):
		return self.parent

	@property
	def tuple(self):
		return (self.x, self.y)

	@property
	def complex(self):
		return complex(self.x, self.y)

	@tuple.setter
	def tuple(self, other):
		if isinstance(other, (tuple, list)) and len(other)==2:
			self.x = float(other[0])
			self.y = float(other[1])

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
	def distance_to_next(self):
		return self.distance_to(self.next)

	@property
	def distance_to_prev(self):
		return self.distance_to(self.prev)

	@property
	def angle_to_next(self):
		return self.angle_to(self.next)

	@property
	def angle_to_prev(self):
		return self.angle_to(self.prev)

	@property
	def angle_poly_turn(self):
		temp_point = (self.next.point - self.point)/(self.point - self.prev.point)
		return math.atan2(temp_point.y, temp_point.x) # Arg (Argument): math.atan2(z.imag, z.real)

	# -- Angle turned by the polyline at this point
	@property
	def xi(self):
		return self.angle_poly_turn        
	
	# -- Distance to previous point in the path
	@property
	def d_ant(self):
		return self.distance_to_prev   
	
	# -- Distance to next point in the path
	@property
	def d_post(self):
		return self.distance_to_next


	# - Functions ----------------------------
	def distance_to(self, other):
		return self.point.diff_to(other.point)

	def angle_to(self, other):
		return self.point.angle_to(other.point)

	# - Transformation ------------------------
	def apply_transform(self):
		self.x, self.y = self.transform.applyTransformation(self.x, self.y)
		
	def reloc(self, new_x, new_y):
		'''Relocate the node to new coordinates'''
		self.point = Point(new_x, new_y)
	
	def shift(self, delta_x, delta_y):
		'''Shift the node by given amout'''
		self.point += Point(delta_x, delta_y)

	# -- IO Format ------------------------------
	@classmethod
	def from_tuple(cls, coords, **kwargs):
		'''Create Node from tuple/list of coordinates.'''
		return cls(coords[0], coords[1], **kwargs)
	
	@classmethod
	def from_object(cls, other, **kwargs):
		'''Clone Node from another Object (Node or Point) instance.'''
		return cls(other.x, other.y, **kwargs)

if __name__ == '__main__':
	# - Test initialization, normal and from VFJ
	n0 = Node.from_VFJ('10 20 s g2')
	n1 = Node.from_VFJ('20 30 s')
	n2 = Node(35, 55.65)
	n3 = Node(44, 67, type='smooth')
	n4 = Node.from_object(n3)
	print(n3, n4)
	
	# - Test math and VFJ export
	n3.point = Point(34,88)
	n3.point += 30
	print(n3.to_VFJ())
	
	# - Test Containers and VFJ export 
	#c = Container([], default_factory=Node.from_tuple)
	#c.append((99,99))
	print(n0)
	n0.lerp_to(n1, (.5,.5))
	print(n0)
	n0.tuple = (1,2)
	
	ns = n0.to_XML()
	nz = Node.from_XML(ns)
	print(n0, nz)
	
