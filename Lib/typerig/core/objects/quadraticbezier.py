# MODULE: TypeRig / Core / Quadratic Bezier (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2016-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import math
from typerig.core.func.math import linInterp as lerp
from typerig.core.func.math import ratfrac
from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.transform import Transform
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line

# - Init -------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
class QuadraticBezier(object):
	def __init__(self, *argv):
		if len(argv) == 1:
			if isinstance(argv[0], self.__class__): # Clone
				self.p0, self.p1, self.p2 = argv[0].p0, argv[0].p1, argv[0].p2

			if isMultiInstance(argv[0], (tuple, list)):
				self.p0, self.p1, self.p2 = [Point(item) for item in argv[0]]

		if len(argv) == 3:
			if isMultiInstance(argv, Point):
				self.p0, self.p1, self.p2 = argv

			if isMultiInstance(argv, (tuple, list)):
				self.p0, self.p1, self.p2 = [Point(item) for item in argv]

		if len(argv) == 6:
			if isMultiInstance(argv, (float, int)):
				self.p0, self.p1, self.p2 = [Point(argv[i], argv[i+1]) for i in range(0, len(argv), 2)]

		self.transform = Transform()

	def __add__(self, other):
		return self.__class__([p + other for p in self.points])

	def __sub__(self, other):
		return self.__class__([p - other for p in self.points])

	def __mul__(self, other):
		return self.__class__([p * other for p in self.points])

	__rmul__ = __mul__

	def __div__(self, other):
		return self.__class__([p / other for p in self.points])

	def __and__(self, other):
		return self.intersect_line(other)

	def __len__(self):
		return len(self.tuple)

	def __repr__(self):
		return '<{}: {},{},{}>'.format(self.__class__.__name__, self.p0.tuple, self.p1.tuple, self.p2.tuple)

	# -- Properties
	@property
	def tuple(self):
		return (self.p0.tuple, self.p1.tuple, self.p2.tuple)

	@property
	def points(self):
		return [self.p0, self.p1, self.p2]

	@property
	def line(self):
		return Line(self.p0, self.p2)

	@property
	def x(self):
		return min(self.p0.x, self.p1.x, self.p2.x)

	@property
	def y(self):
		return min(self.p0.y, self.p1.y, self.p2.y)

	@property
	def x_max(self):
		return max(self.p0.x, self.p1.x, self.p2.x)

	@property
	def y_max(self):
		return max(self.p0.y, self.p1.y, self.p2.y)

	@property
	def width(self):
		return abs(self.x_max - self.x)

	@property
	def height(self):
		return abs(self.y_max - self.y)

	# -- Modifiers
	def align_to(self, other_line):
		tx = other_line.p0.x
		ty = other_line.p0.y
		angle = -other_line.angler
		result = []

		for p in self.points:
			x = (p.x - tx)*math.cos(angle) - (p.y - ty)*math.sin(angle)
			y = (p.x - tx)*math.sin(angle) + (p.y - ty)*math.cos(angle)
			result.append((x, y))

		return self.__class__(result)

	def asList(self):
		return

	def doSwap(self):
		return self.__class__(self.p2.tuple, self.p1.tuple, self.p0.tuple)

	def doTransform(self, transform=None):
		if transform is None: transform = self.transform
		self.p0.doTransform(transform)
		self.p1.doTransform(transform)
		self.p2.doTransform(transform)

	# -- Solvers
	def find_coeffs(self):
		'''Quadratic Bernstein coefficients: B(t) = a*t^2 + b*t + c'''
		a = self.p0 - 2. * self.p1 + self.p2
		b = -2. * self.p0 + 2. * self.p1
		c = self.p0

		return (a, b, c)

	def find_roots(self):
		'''Find roots of quadratic bezier (where curve crosses zero).
		Returns roots for X and Y dimensions separately.
		'''
		def root_dim(a, b, c):
			# Finds roots in one dimension: a*t^2 + b*t + c = 0
			if abs(a) < 1e-12:
				# Linear case
				if abs(b) < 1e-12:
					return []
				t = -c / b
				return [t] if 0 <= t <= 1. else []

			discriminant = b*b - 4.*a*c

			if discriminant < 0:
				return []

			elif abs(discriminant) < 1e-12:
				t = -b / (2.*a)
				return [t] if 0 <= t <= 1. else []

			else:
				sqrt_d = math.sqrt(discriminant)
				t1 = (-b + sqrt_d) / (2.*a)
				t2 = (-b - sqrt_d) / (2.*a)
				return [t for t in [t1, t2] if 0 <= t <= 1.]

		# - Init
		a, b, c = self.find_coeffs()

		# - Calculate
		return root_dim(a.x, b.x, c.x), root_dim(a.y, b.y, c.y)

	def intersect_line(self, other_line):
		'''Find curve and line intersection'''
		aligned_bezier = self.align_to(other_line)
		intersect_times_x, intersect_times_y = aligned_bezier.find_roots()
		intersect_points_x = [self.solve_point(t) for t in intersect_times_x]
		intersect_points_y = [self.solve_point(t) for t in intersect_times_y]
		intersect_points_x = [p for p in intersect_points_x if other_line.hasPoint(p)]
		intersect_points_y = [p for p in intersect_points_y if other_line.hasPoint(p)]

		return (intersect_times_x, intersect_times_y), (intersect_points_x, intersect_points_y)

	def solve_point(self, time):
		'''Find point on quadratic bezier at given time'''
		rtime = 1 - time
		pt = (rtime**2)*self.p0 + 2*rtime*time*self.p1 + (time**2)*self.p2
		return pt

	def solve_derivative_at_time(self, time):
		'''Returns point of on-curve point at given time and vector of 1st and 2nd derivative.'''
		a, b, c = self.find_coeffs()

		pt = a * time**2 + b * time + c
		d1 = 2. * a * time + b
		d2 = 2. * a  # Constant for quadratic

		return pt, d1, d2

	def solve_normal_at_time(self, time):
		'''Returns point that is the unit vector of normal at given time.'''
		_d, d1, _d2 = self.solve_derivative_at_time(time)
		q = math.sqrt(d1.x*d1.x + d1.y*d1.y)
		return Point(-d1.y/q, d1.x/q)

	def solve_tangent_at_time(self, time):
		'''Returns point that is the unit vector of tangent at given time.'''
		_d, d1, _d2 = self.solve_derivative_at_time(time)
		return d1.unit

	def solve_curvature(self, time):
		'''Find curvature of on-curve point at given time'''
		pt, d1, d2 = self.solve_derivative_at_time(time)
		return (d1.x * d2.y - d1.y * d2.x) / (d1.x**2 + d1.y**2)**1.5

	def solve_slice(self, time):
		'''Returns two segments representing quadratic bezier sliced at given time.
		Uses De Casteljau subdivision.
		Output: tuple of two QuadraticBezier objects
		'''
		x0, y0 = self.p0.x, self.p0.y
		x1, y1 = self.p1.x, self.p1.y
		x2, y2 = self.p2.x, self.p2.y

		# First level interpolation
		x01 = (x1 - x0)*time + x0
		y01 = (y1 - y0)*time + y0

		x12 = (x2 - x1)*time + x1
		y12 = (y2 - y1)*time + y1

		# Second level — on-curve split point
		x012 = (x12 - x01)*time + x01
		y012 = (y12 - y01)*time + y01

		slices = (self.__class__((x0, y0), (x01, y01), (x012, y012)),
				  self.__class__((x012, y012), (x12, y12), (x2, y2)))

		return slices

	def solve_distance_start(self, distance, timeStep=.01):
		'''Returns time at which the given distance to beginning of bezier is met.
		Probing is executed withing timeStep in range from 0 to 1. The finer the step the preciser the results.
		'''
		measure = 0
		time = 0

		while measure < distance and time < 1.:
			cNode = self.solve_point(time)
			measure = math.hypot(-self.p0.x + cNode.x, -self.p0.y + cNode.y)
			time += timeStep

		return time

	def solve_distance_end(self, distance, timeStep=.01):
		'''Returns time at which the given distance to end of bezier is met.
		Probing is executed withing timeStep in range from 0 to 1. The finer the step the preciser the results.
		'''
		measure = 0
		time = 1

		while measure < distance and time > 0:
			cNode = self.solve_point(time)
			measure = math.hypot(-self.p2.x + cNode.x, -self.p2.y + cNode.y)
			time -= timeStep

		return time

	def solve_slice_distance(self, distance, from_start=True, timeStep=.001):
		'''Slices bezier at time which the given distance is met.'''
		slice_time = self.solve_distance_start(distance, timeStep) if from_start else self.solve_distance_end(distance, timeStep)
		return self.solve_slice(slice_time)

	def solve_extremes(self):
		'''Finds curve extremes and returns [(extreme_x, extreme_y, extreme_t)...]
		For quadratic bezier, extremes are found by solving B'(t) = 0 which is linear.
		'''
		tvalues, points = [], []
		x0, y0 = self.p0.x, self.p0.y
		x1, y1 = self.p1.x, self.p1.y
		x2, y2 = self.p2.x, self.p2.y

		# B'(t) = 2*(1-t)*(P1-P0) + 2*t*(P2-P1) = 0
		# Simplifies to: t = (P0-P1) / (P0 - 2*P1 + P2)
		for i in range(0, 2):
			if i == 0:
				# X dimension
				a = float(x0 - 2 * x1 + x2)
				b = float(x1 - x0)
			else:
				# Y dimension
				a = float(y0 - 2 * y1 + y2)
				b = float(y1 - y0)

			if abs(a) < 1e-12:
				continue

			t = -b / a  # From 2*a*t + 2*b = 0

			if 0 < t and t < 1:
				tvalues.append(t)

		for t in tvalues:
			mt = 1 - t
			x = mt*mt*x0 + 2*mt*t*x1 + t*t*x2
			y = mt*mt*y0 + 2*mt*t*y1 + t*t*y2
			points.append((Point(x, y), t))

		return points

	def solve_parallel(self, vector, fullOutput=False):
		'''Finds the t value along a quadratic Bezier where a tangent (1st derivative) 
		is parallel with the direction vector.
		vector: a pair of values representing the direction of interest (magnitude is ignored).
		returns 0.0 <= t <= 1.0 or None
		'''
		# B'(t) = 2*a*t + b, where a = P0 - 2*P1 + P2, b = -2*P0 + 2*P1
		# For parallel: B'(t) x V = 0 (cross product = 0)
		# (2*a.x*t + b.x)*V.y - (2*a.y*t + b.y)*V.x = 0
		# t*(2*a.x*V.y - 2*a.y*V.x) + (b.x*V.y - b.y*V.x) = 0

		vx, vy = vector[0], vector[1]
		a, b, c = self.find_coeffs()

		denom = 2. * (a.x * vy - a.y * vx)
		numer = -(b.x * vy - b.y * vx)

		if abs(denom) < 1e-12:
			return None

		t = numer / denom

		if fullOutput:
			return t

		if 0 <= t <= 1:
			return t

		return None

	@staticmethod
	def _nr_roots_unclamped(p0v, p1v, p2v, target):
		'''Newton-Raphson: find all real t where the 1D bezier component equals target.
		Unclamped — returns t outside [0,1] for extrapolation beyond segment endpoints.
		'''
		a = p0v - 2.*p1v + p2v
		b = -2.*p0v + 2.*p1v
		c = p0v - target

		# Quadratic: a*t^2 + b*t + c = 0
		if abs(a) < 1e-12:
			# Linear fallback
			if abs(b) < 1e-12:
				return []
			return [-c / b]

		discriminant = b*b - 4.*a*c

		if discriminant < 0:
			return []

		sqrt_d = math.sqrt(max(0., discriminant))
		t1 = (-b + sqrt_d) / (2.*a)
		t2 = (-b - sqrt_d) / (2.*a)

		unique = [t1]
		if abs(t2 - t1) > 1e-9:
			unique.append(t2)

		return unique

	def find_t_for_y(self, target_y):
		'''All real t where B_y(t) == target_y. Includes extrapolation (t outside [0,1]).'''
		return self._nr_roots_unclamped(self.p0.y, self.p1.y, self.p2.y, target_y)

	def find_t_for_x(self, target_x):
		'''All real t where B_x(t) == target_x. Includes extrapolation (t outside [0,1]).'''
		return self._nr_roots_unclamped(self.p0.x, self.p1.x, self.p2.x, target_x)

	def solve_proportional_handles(self, ratio=.3):
		'''Equalizes handle position to given float ratio along p0-p2 baseline.'''
		hl = Line(self.p0, self.p2)
		new_p1 = hl.solve_point(ratio)

		# Project onto original handle direction
		phi = math.atan2(self.p1.y - self.p0.y, self.p1.x - self.p0.x)
		dist = self.p0.diff_to(self.p2) * ratio
		new_x = self.p0.x + math.cos(phi) * dist
		new_y = self.p0.y + math.sin(phi) * dist

		return self.__class__(self.p0.tuple, (new_x, new_y), self.p2.tuple)

	# -- Conversion
	def to_cubic(self):
		'''Degree-elevate to cubic bezier (lossless).
		Q0 -> C0, (Q0 + 2*Q1)/3 -> C1, (2*Q1 + Q2)/3 -> C2, Q2 -> C3
		'''
		from typerig.core.objects.cubicbezier import CubicBezier

		c0 = self.p0
		c1 = (self.p0 + 2. * self.p1) * (1./3.)
		c2 = (2. * self.p1 + self.p2) * (1./3.)
		c3 = self.p2

		return CubicBezier(c0, c1, c2, c3)


if __name__ == '__main__':
	# - Basic construction test
	q = QuadraticBezier((100, 100), (200, 300), (300, 100))
	print(q)
	print('Point at t=0.5:', q.solve_point(0.5).tuple)
	print('Extremes:', q.solve_extremes())

	# - Slicing test
	s1, s2 = q.solve_slice(0.5)
	print('Slice 1:', s1)
	print('Slice 2:', s2)

	# - Degree elevation test
	cubic = q.to_cubic()
	print('Cubic:', cubic)
	print('Cubic at t=0.5:', cubic.solve_point(0.5).tuple)
