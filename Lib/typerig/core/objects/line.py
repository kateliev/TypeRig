# MODULE: TypeRig / Core / Line (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2024 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.func.math import linInterp as lerp
from typerig.core.func.math import isBetween
from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.transform import Transform
from typerig.core.objects.point import Point, Void

# - Init -------------------------------
__version__ = '0.27.0'

# - Classes -----------------------------
class Line(object):
	def __init__(self, *argv):
		if len(argv) == 1:
			if isinstance(argv[0], self.__class__): # Clone
				self.p0, self.p1 = argv[0].p0, argv[0].p1

			if isMultiInstance(argv[0], (tuple, list)):
				self.p0, self.p1 = [Point(item) for item in argv[0]]

		if len(argv) > 1:
			'''
			if isMultiInstance(argv[0], (tuple, list)):
				self.p0, self.p1 = Point(argv[0]), Point(argv[1])
			'''

			if isMultiInstance(argv, Point):
				self.p0, self.p1 = argv

			if isMultiInstance(argv, (tuple, list)):
				self.p0, self.p1 = Point(argv[0]), Point(argv[1])

			if isMultiInstance(argv, (float, int)):
				self.p0, self.p1 = Point(argv[0], argv[1]), Point(argv[2], argv[3])

		self.transform = Transform()

	def __add__(self, other):
		return self.__class__(self.p0 + other, self.p1 + other)

	def __sub__(self, other):
		return self.__class__(self.p0 - other, self.p1 - other)

	def __mul__(self, other):
		return self.__class__(self.p0 * other, self.p1 * other)

	__rmul__ = __mul__

	def __div__(self, other):
		return self.__class__(self.p0 / other, self.p1 / other)	

	def __and__(self, other):
		return self.intersect_line(other)

	def __len__(self):
		return len(self.tuple)

	def __repr__(self):
		return '<{}: {}, {}>'.format(self.__class__.__name__, self.p0.tuple, self.p1.tuple)

	# -- Properties
	@property
	def tuple(self):
		return (self.p0.tuple, self.p1.tuple)

	@property
	def points(self):
		return [self.p0, self.p1]

	@property
	def diff_x(self):		
		return self.p1.x - self.p0.x

	@property
	def diff_y(self):		
		return self.p1.y - self.p0.y

	@property
	def x(self):
		return min(self.p0.x, self.p1.x)

	@property
	def y(self):
		return min(self.p0.y, self.p1.y)

	@property
	def x_max(self):
		return max(self.p0.x, self.p1.x)

	@property
	def y_max(self):
		return max(self.p0.y, self.p1.y)

	@property
	def width(self):
		return abs(self.x_max - self.x)

	@property
	def height(self):
		return abs(self.y_max - self.y)
	
	@property
	def length(self):
		return math.hypot(self.p0.x - self.p1.x, self.p0.y - self.p1.y)

	@property
	def slope(self):
		try:
			return self.diff_y / float(self.diff_x)
		except ZeroDivisionError:
			return float('nan')

	@property
	def angle(self):
		return math.degrees(math.atan2(self.diff_y, self.diff_x))

	@property
	def angler(self):
		return math.atan2(self.diff_y, self.diff_x)

	@property
	def y_intercept(self):
		'''Get the Y intercept of a line segment'''
		return self.p0.y - self.slope * self.p0.x if not math.isnan(self.slope) and self.slope != 0 else self.p0.y

	# -- Query
	def hasPoint(self, other):
		min_x, min_y = min(self.p0.x, self.p1.x), min(self.p0.y, self.p1.y)
		max_x, max_y = max(self.p0.x, self.p1.x), max(self.p0.y, self.p1.y)

		return True if isBetween(other.x, min_x, max_x) and isBetween(other.y, min_y, max_y) else False

	# -- Solvers
	def solve_y(self, x):
		'''Solve line equation for Y coordinate.'''
		return self.slope * x + self.y_intercept if not math.isnan(self.slope) and self.slope != 0 else self.p0.y
					
	def solve_x(self, y):
		'''Solve line equation for X coordinate.'''
		return (float(y) - self.y_intercept) / float(self.slope) if not math.isnan(self.slope) and self.slope != 0 else self.p0.x
		
	def solve_point(self, time):
		'''Find point on the line at given time'''
		return self.p0 * (1. - time) + self.p1 * time

	def solve_distance_start(self, distance):
		'''Find time at which given distance from start is met. 
		Providing API call similar to the one in cubicbezier.py'''
		return distance/self.length

	def solve_distance_end(self, distance):
		'''Find time at which given distance from start is met. 
		Providing API call similar to the one in cubicbezier.py'''
		return 1 - distance/self.length	

	def solve_length(self, length, mode=0):
		'''Find a indentical line with different length. Solve for anchored p0 (mode = 0), p1 (mode = 1) or center (mode = -1)'''
		time = length/self.length
		
		if mode == 0: # Solve for p0 anchored
			new_p0 = self.p0
			new_p1 = self.solve_point(time)

		elif mode == 1: # Solve for p1 anchored
			new_p0 = self.doSwap().solve_point(time)
			new_p1 = self.p1

		elif mode == -1: # Solve for mid
			new_line = self.__class__(self.p0, self.solve_point(time))
			center_diff = new_line.solve_point(.5) - self.solve_point(.5)

			new_p0 = new_line.p0 - center_diff
			new_p1 = new_line.p1 - center_diff

		return self.__class__(new_p0, new_p1)

	def solve_slice(self, time):
		'''Slice line at given time'''
		return self.__class__(self.p0.tuple, self.solve_point(time).tuple), self.__class__(self.solve_point(time).tuple, self.p1.tuple)

	def solve_slice_distance(self, distance, from_start=True):
		if distance == 0: distance = .000001 # Nasty hack: avoid Zero devision but get slice at all cost
		slice_time = distance/self.length if from_start else 1 - distance/self.length
		return self.solve_slice(slice_time)

	def lerp(self, time):
		return self.solve_point(time)

	def lerp_xy(self, time_x, time_y)	:
		return Point(self.p0.x * (1. - time_x) + self.p1.x * time_x, self.p0.y * (1 - time_y) + self.p1.y * time_y)

	def intersect_line(self, other_line, projection=False):
		'''Find intersection point (X, Y) for two lines.
		Returns Void() point  if lines do not intersect.'''
		
		diff_x = Point(self.p0.x - self.p1.x, other_line.p0.x - other_line.p1.x)
		diff_y = Point(self.p0.y - self.p1.y, other_line.p0.y - other_line.p1.y)

		div = diff_x | diff_y
		if div == 0: return Void() # (None, None)

		d = Point(self.p0 | self.p1, other_line.p0 | other_line.p1)
		x = (d | diff_x) / div
		y = (d | diff_y) / div
		
		if projection:
			return Point(x, y)
		else:
			if self.hasPoint(Point(x,y)) and other_line.hasPoint(Point(x,y)):
				return Point(x, y)
			
			return Void() # (None, None)
		
	def shift(self, dx, dy):
		'''Shift coordinates by dx, dy'''
		self.p0.x += dx
		self.p1.x += dx
		self.p0.y += dy
		self.p1.y += dy

	# -- Modifiers
	def doSwap(self):
		return self.__class__(self.p1, self.p0)

	def doTransform(self, transform=None):
		if transform is None: transform = self.transform
		self.p0.doTransform(transform)
		self.p1.doTransform(transform)

class Vector(Line):
	def __init__(self, *argv):
		super(Vector, self).__init__(*argv)

		self._angle = self.getAngle()
		self._slope = self.getSlope()
		self.p1 = Void(self.p1.tuple) # Deactivate second node

	def __repr__(self):
		return '<Vector: {}, slope={}, angle={}>'.format(self.p0.tuple, self.slope, self.angle)

	# - Properties
	@property
	def x(self):
		return self.p0.x

	@property
	def y(self):
		return self.p0.y

	@property
	def angle(self):
		return self._angle

	@angle.setter
	def angle(self, value):
		self._angle = value

	@property
	def slope(self):
		return self._slope

	@slope.setter
	def slope(self, value):
		self._slope	= value
	
	# - Getters
	def getSlope(self):
		try:
			return self.diff_y / float(self.diff_x)
		except ZeroDivisionError:
			return float('nan')
	
	def getAngle(self):
		return math.degrees(math.atan2(self.diff_y, self.diff_x))

if __name__ == '__main__':
	a = Line(Point(0,0), Point(4,0))
	b = a.solve_length(10,-1)
	print(a.length, b.length, a, b)