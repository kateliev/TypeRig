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

	def asList(self):
		return list(self.points)

	def __eq__(self, other):
		if not isinstance(other, QuadraticBezier):
			return False
		return (self.p0 == other.p0 and 
				self.p1 == other.p1 and 
				self.p2 == other.p2)

	def __ne__(self, other):
		return not self.__eq__(other)

	def __hash__(self):
		return hash((self.p0.tuple, self.p1.tuple, self.p2.tuple))

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
		denom = (d1.x**2 + d1.y**2)**1.5
		if abs(denom) < 1e-14:
			return 0.0
		return (d1.x * d2.y - d1.y * d2.x) / denom

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

	# -- Arc Length (Gauss-Legendre Quadrature) -------------------------
	_GAUSS_LEGENDRE_T = [
		-.06405689286260563, .06405689286260563,
		-.1911188674736163, .1911188674736163,
		-.3150426796961634, .3150426796961634,
		-.4337935076260451, .4337935076260451,
		-.5454214713888396, .5454214713888396,
		-.6480936519369755, .6480936519369755,
		-.7401241915785544, .7401241915785544,
		-.820001985973903, .820001985973903,
		-.8864155270044011, .8864155270044011,
		-.9382745520027328, .9382745520027328,
		-.9747285559713095, .9747285559713095,
		-.9951872199970213, .9951872199970213
	]

	_GAUSS_LEGENDRE_C = [
		.12793819534675216, .12793819534675216,
		.1258374563468283, .1258374563468283,
		.12167047292780339, .12167047292780339,
		.1155056680537256, .1155056680537256,
		.10744427011596563, .10744427011596563,
		.09761865210411388, .09761865210411388,
		.08619016153195327, .08619016153195327,
		.0733464814110803, .0733464814110803,
		.05929858491543678, .05929858491543678,
		.04427743881741981, .04427743881741981,
		.028531388628933663, .028531388628933663,
		.0123412297999872, .0123412297999872
	]

	def _arc_length_integrand(self, t):
		pt, d1, _ = self.solve_derivative_at_time(t)
		return math.sqrt(d1.x**2 + d1.y**2)

	def get_arc_length(self):
		length = 0.0
		a, b = 0.0, 1.0
		c = (b - a) * 0.5
		m = (b + a) * 0.5

		for i in range(0, len(self._GAUSS_LEGENDRE_T)):
			t = c * self._GAUSS_LEGENDRE_T[i] + m
			length += self._GAUSS_LEGENDRE_C[i] * self._arc_length_integrand(t)

		return length * 0.5 * (b - a)

	def get_arc_length_by_parts(self, parts=50):
		step = 1.0 / parts
		lengths = [0.0]
		total = 0.0

		for i in range(parts):
			t0 = i * step
			t1 = (i + 1) * step

			seg_len = 0.0
			c = (t1 - t0) * 0.5
			m = (t1 + t0) * 0.5

			for j in range(len(self._GAUSS_LEGENDRE_T)):
				t = c * self._GAUSS_LEGENDRE_T[j] + m
				seg_len += self._GAUSS_LEGENDRE_C[j] * self._arc_length_integrand(t)

			seg_len *= 0.5 * (t1 - t0)
			total += seg_len
			lengths.append(total)

		return lengths

	def get_bbox(self):
		extremes = self.solve_extremes()
		all_x = [self.p0.x, self.p2.x]
		all_y = [self.p0.y, self.p2.y]

		for pt, t in extremes:
			all_x.append(pt.x)
			all_y.append(pt.y)

		x = min(all_x)
		y = min(all_y)
		x_max = max(all_x)
		y_max = max(all_y)

		return {'x': x, 'y': y, 'x_max': x_max, 'y_max': y_max, 'width': x_max - x, 'height': y_max - y}

	def project_point(self, point, steps=50):
		# Step 1: coarse check using LUT
		lut = self.get_lut(steps)
		l = len(lut) - 1
		
		closest_idx = 0
		closest_dist = float('inf')
		
		for i, pt in enumerate(lut):
			dist = math.hypot(pt.x - point.x, pt.y - point.y)
			if dist < closest_dist:
				closest_dist = dist
				closest_idx = i
		
		# Step 2: fine check around closest segment
		mpos = closest_idx
		t1 = (mpos - 1) / l if mpos > 0 else 0
		t2 = (mpos + 1) / l if mpos < l else 1
		
		step = 0.1 / l
		mdist = closest_dist
		ft = t1
		
		t = t1
		while t < t2 + step:
			pt = self.solve_point(t)
			d = math.hypot(pt.x - point.x, pt.y - point.y)
			if d < mdist:
				mdist = d
				ft = t
			t += step
		
		# Clamp and refine with Newton-Raphson
		ft = max(0, min(1, ft))
		pt = self.solve_point(ft)
		
		# Newton-Raphson refinement
		for _ in range(10):
			d1 = self.solve_derivative_at_time(ft)[1]
			num = d1.x * (pt.x - point.x) + d1.y * (pt.y - point.y)
			denom = d1.x**2 + d1.y**2
			
			if abs(denom) < 1e-14:
				break
			
			t_new = ft - num / denom
			
			if t_new < 0 or t_new > 1:
				break
			
			pt_new = self.solve_point(t_new)
			d_new = math.hypot(pt_new.x - point.x, pt_new.y - point.y)
			
			if d_new < mdist:
				ft = t_new
				mdist = d_new
				pt = pt_new
			else:
				break
		
		return ft, mdist

	def scale(self, factor, origin=None):
		if origin is None:
			origin = self.p0

		return self.__class__(
			(self.p0.x - origin.x) * factor + origin.x,
			(self.p1.x - origin.x) * factor + origin.x,
			(self.p2.x - origin.x) * factor + origin.x,
			(self.p0.y - origin.y) * factor + origin.y,
			(self.p1.y - origin.y) * factor + origin.y,
			(self.p2.y - origin.y) * factor + origin.y
		)

	def get_lut(self, steps=50):
		return [self.solve_point(i / steps) for i in range(steps + 1)]

	def get_lut_with_lengths(self, steps=50):
		points = self.get_lut(steps)
		lengths = self.get_arc_length_by_parts(steps)
		return points, lengths

	def get_point_at_length(self, distance):
		total_length = self.get_arc_length()
		target = distance / total_length
		step = 1.0 / 1000
		accum = 0.0

		for i in range(1000):
			t0 = i * step
			t1 = (i + 1) * step
			pt0 = self.solve_point(t0)
			pt1 = self.solve_point(t1)
			seg_len = math.hypot(pt1.x - pt0.x, pt1.y - pt0.y)

			if accum + seg_len >= distance:
				remainder = distance - accum
				if seg_len > 0:
					frac = remainder / seg_len
					return Point(
						pt0.x + (pt1.x - pt0.x) * frac,
						pt0.y + (pt1.y - pt0.y) * frac
					)

			accum += seg_len

		return self.p2

	def divide_at_length(self, distance):
		total_length = self.get_arc_length()
		if distance <= 0:
			return self.__class__(self.p0, self.p0, self.p0), self

		if distance >= total_length:
			return self, self.__class__(self.p2, self.p2, self.p2)

		step = 1.0 / 1000
		accum = 0.0

		for i in range(1000):
			t0 = i * step
			t1 = (i + 1) * step
			pt0 = self.solve_point(t0)
			pt1 = self.solve_point(t1)
			seg_len = math.hypot(pt1.x - pt0.x, pt1.y - pt0.y)

			if accum + seg_len >= distance:
				remainder = distance - accum
				if seg_len > 0:
					frac = remainder / seg_len
					t_split = t0 + (t1 - t0) * frac
					return self.solve_slice(t_split)

			accum += seg_len

		return self.solve_slice(0.5)

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
