# MODULE: TypeRig / Core / Cubic Bezier (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2016-2024 	(http://www.kateliev.com)
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
__version__ = '0.30.1'

# - Classes -----------------------------
class CubicBezier(object):
	def __init__(self, *argv):
		if len(argv) == 1:
			if isinstance(argv[0], self.__class__): # Clone
				self.p0, self.p1, self.p2, self.p3 = argv[0].p0, argv[0].p1, argv[0].p2, argv[0].p3
			
			if isMultiInstance(argv[0], (tuple, list)):
				self.p0, self.p1, self.p2, self.p3 = [Point(item) for item in argv[0]]

		if len(argv) == 4:
			if isMultiInstance(argv, Point):
				self.p0, self.p1, self.p2, self.p3 = argv

			if isMultiInstance(argv, (tuple, list)):
				self.p0, self.p1, self.p2, self.p3 = [Point(item) for item in argv]


		if len(argv) == 8:
			if isMultiInstance(argv, (float, int)):
				self.p0, self.p1, self.p2, self.p3 = [Point(argv[i], argv[i+1]) for i in range(len(argv)-1)]

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
		return '<{}: {},{},{},{}>'.format(self.__class__.__name__, self.p0.tuple, self.p1.tuple, self.p2.tuple, self.p3.tuple)

	# -- Properties
	@property
	def tuple(self):
		return (self.p0.tuple, self.p1.tuple, self.p2.tuple, self.p3.tuple)

	@property
	def points(self):
		return [self.p0, self.p1, self.p2, self.p3]	
	
	@property
	def line(self):
		return Line(self.p0, self.p3)

	@property
	def x(self):
		return min(self.p0.x, self.p1.x, self.p2.x, self.p3.x)

	@property
	def y(self):
		return min(self.p0.y, self.p1.y, self.p2.y, self.p3.y)

	@property
	def x_max(self):
		return max(self.p0.x, self.p1.x, self.p2.x, self.p3.x)

	@property
	def y_max(self):
		return max(self.p0.y, self.p1.y, self.p2.y, self.p3.y)

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
			result.append((x,y))

		return self.__class__(result)

	def asList(self):
		return 

	def doSwap(self):
		return self.__class__(self.p3.tuple, self.p2.tuple, self.p1.tuple, self.p0.tuple)

	def doTransform(self, transform=None):
		if transform is None: transform = self.transform
		self.p0.doTransform(transform)
		self.p1.doTransform(transform)
		self.p2.doTransform(transform)
		self.p3.doTransform(transform)
		
	# -- Solvers
	def find_coeffs(self):
		a = -self.p0 + 3. * self.p1 - 3. * self.p2 + self.p3
		b = 3. * self.p0 - 6. * self.p1 + 3. * self.p2
		c = -3. * self.p0 + 3. * self.p1
		d = self.p0

		return (a, b, c, d)

	def find_roots(self):
		'''Find roots of cubic bezier.
		Adapted from bezier.js library by Pomax : https://github.com/Pomax/bezierjs
		'''
		
		# - Helpers
		def crt(v):
			# A real-cuberoots-only helper function
			if v < 0: 
				return -math.pow(-v, 1./3.)
			return math.pow(v, 1./3.)

		def root_dim(a, b, c, d):
			# Finds roots in one dimension
			if d == 0: return []

			a /= d
			b /= d
			c /= d

			p = (3.*b - a*a)/3.
			p3 = p/3.
			q = (2.*a*a*a - 9.*a*b + 27.*c) / 27.
			q2 = q/2.
			discriminant = q2*q2 + p3*p3*p3

			if discriminant < 0:
				mp3 = -p/3.
				mp33 = mp3*mp3*mp3
				r = math.sqrt(mp33)
				t = -q/(2*r)
				
				if t < -1:
					cosphi = -1
				elif t > 1:
					cosphi = 1
				else:
					cosphi = t

				phi = math.acos(cosphi)
				crtr = crt(r)
				
				t1 = 2.*crtr
				x1 = t1*math.cos(phi/3.) - a/3.
				x2 = t1*math.cos((phi + tau)/3.) - a/3.
				x3 = t1*math.cos((phi + 2.*tau)/3.) - a/3.
				
				return [x for x in [x1, x2, x3] if 0 <= x <= 1.]

			elif discriminant == 0:
				u1 = crt(-q2) if q2 < 0 else -crt(q2)
				x1 = 2.*u1 - a/3.
				x2 = -u1 - a/3.
				
				return [x for x in [x1, x2] if 0 <= x <= 1.]

			else:
				sd = math.sqrt(discriminant)
				u1 = crt(-q2 + sd)
				v1 = crt(q2 + sd)
				res = u1 - v1 - a/3
				
				return [res] if 0 <= res <= 1. else []

		# - Init
		pi = math.pi
		tau = 2 * pi
		d, a, b, c = self.find_coeffs()
		
		# - Calculate
		return root_dim(a.x, b.x, c.x, d.x), root_dim(a.y, b.y, c.y, d.y)
		
	def intersect_line(self, other_line):
		'''Find Curve and line intersection
		Adapted from bezier.js library by Pomax : https://github.com/Pomax/bezierjs
		'''
		aligned_bezier = self.align_to(other_line)
		intersect_times_x, intersect_times_y = aligned_bezier.find_roots()
		intersect_points_x = [self.solve_point(t) for t in intersect_times_x]
		intersect_points_y = [self.solve_point(t) for t in intersect_times_y]
		intersect_points_x = [p for p in intersect_points_x if other_line.hasPoint(p)]
		intersect_points_y = [p for p in intersect_points_y if other_line.hasPoint(p)]
		
		return (intersect_times_x, intersect_times_y), (intersect_points_x, intersect_points_y)

	def solve_point(self, time):
		'''Find point on cubic bezier at given time '''
		rtime = 1 - time
		pt = (rtime**3)*self.p0 + 3*(rtime**2)*time*self.p1 + 3*rtime*(time**2)*self.p2 + (time**3)*self.p3
		return pt

	@staticmethod
	def _nr_roots_unclamped(p0v, p1v, p2v, p3v, target):
		'''Newton-Raphson: find all real t where the 1D bezier component equals target.
		Unclamped — returns t outside [0,1] for extrapolation beyond segment endpoints.
		'''
		a =  -p0v + 3.*p1v - 3.*p2v + p3v
		b =  3.*p0v - 6.*p1v + 3.*p2v
		c = -3.*p0v + 3.*p1v
		d =  p0v - target
		results = []
		for t0 in (-0.5, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5):
			t = float(t0)
			for _ in range(100):
				ft  = a*t**3 + b*t**2 + c*t + d
				ftp = 3.*a*t**2 + 2.*b*t + c
				if abs(ftp) < 1e-14:
					break
				dt = ft / ftp
				t -= dt
				if abs(dt) < 1e-9:
					if abs(a*t**3 + b*t**2 + c*t + d) < 1e-3:
						results.append(t)
					break
		unique = []
		for t in results:
			if not any(abs(t - u) < 1e-4 for u in unique):
				unique.append(t)
		return unique

	def find_t_for_y(self, target_y):
		'''All real t where B_y(t) == target_y. Includes extrapolation (t outside [0,1]).'''
		return self._nr_roots_unclamped(self.p0.y, self.p1.y, self.p2.y, self.p3.y, target_y)

	def find_t_for_x(self, target_x):
		'''All real t where B_x(t) == target_x. Includes extrapolation (t outside [0,1]).'''
		return self._nr_roots_unclamped(self.p0.x, self.p1.x, self.p2.x, self.p3.x, target_x)

	def solve_derivative_at_time(self, time):
		'''Returns point of on-curve point at given time and vector of 1st and 2nd derivative.'''
		a, b, c, d = self.find_coeffs()

		pt = a * time**3 + b * time**2 + c * time + d
		d1 = 3. * a * time**2 + 2. * b * time + c
		d2 = 6. * a * time + 2.* b
		
		return pt, d1, d2

	def solve_normal_at_time(self, time):
		'''Returns point that is the unit vector of normal at given time.'''
		_d, d1, _d2 = self.solve_derivative_at_time(time)
		q = math.sqrt(d1.x*d1.x + d1.y*d1.y);
		return Point(-d1.y/q, d1.x/q)

	def solve_tangent_at_time(self, time):
		'''Returns point that is the unit vector of tangent at given time.'''
		_d, d1, _d2 = self.solve_derivative_at_time(time)
		return d1.unit

	def solve_curvature(self, time):
		'''Find Curvature of on-curve point at given time'''
		pt, d1, d2 = self.solve_derivative_at_time(time)
		return (d1.x * d2.y - d1.y * d2.x) / (d1.x**2 + d1.y**2)**1.5

	def solve_slice(self, time):
		'''Returns two segments representing cubic bezier sliced at given time. 
		Output: list [(Start), (Start_BCP_out), (Slice_BCP_in), (Slice), (Slice_BCP_out), (End_BCP_in), (End)] of tuples (x,y)
		'''
		x1, y1 = self.p0.x, self.p0.y
		x2, y2 = self.p1.x, self.p1.y
		x3, y3 = self.p2.x, self.p2.y
		x4, y4 = self.p3.x, self.p3.y

		x12 = (x2 - x1)*time + x1
		y12 = (y2 - y1)*time + y1

		x23 = (x3 - x2)*time + x2
		y23 = (y3 - y2)*time + y2

		x34 = (x4 - x3)*time + x3
		y34 = (y4 - y3)*time + y3

		x123 = (x23 - x12)*time + x12
		y123 = (y23 - y12)*time + y12

		x234 = (x34 - x23)*time + x23
		y234 = (y34 - y23)*time + y23

		x1234 = (x234 - x123)*time + x123
		y1234 = (y234 - y123)*time + y123

		slices = (self.__class__((x1,y1), (x12,y12), (x123,y123), (x1234,y1234)), 
				  self.__class__((x1234,y1234), (x234,y234), (x34,y34), (x4,y4)))
		
		return slices

	def solve_distance_start(self, distance, timeStep = .01):
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

	def solve_distance_end(self, distance, timeStep = .01 ):
		'''Returns time at which the given distance to end of bezier is met. 
		Probing is executed withing timeStep in range from 0 to 1. The finer the step the preciser the results.
		'''
		measure = 0
		time = 1

		while measure < distance and time > 0:
			cNode = self.solve_point(time)
			measure = math.hypot(-self.p3.x + cNode.x, -self.p3.y + cNode.y)
			time -= timeStep

		return time

	def solve_slice_distance(self, distance, from_start=True, timeStep = .001):
		'''Slices bezier at time which the given distance is met. 
		Output: list [(Start), (Start_BCP_out), (Slice_BCP_in), (Slice), (Slice_BCP_out), (End_BCP_in), (End)] of tuples (x,y)
		'''
		slice_time = self.solve_distance_start(distance, timeStep) if from_start else self.solve_distance_end(distance, timeStep)
		return self.solve_slice(slice_time)

	def solve_extremes(self):
		'''Finds curve extremes and returns [(extreme_01_x, extreme_01_y, extreme_01_t)...(extreme_n_x, extreme_n_y, extreme_n_t)]'''

		tvalues, points = [], []
		x0, y0 = self.p0.x, self.p0.y
		x1, y1 = self.p1.x, self.p1.y
		x2, y2 = self.p2.x, self.p2.y
		x3, y3 = self.p3.x, self.p3.y

		for i in range(0,2):
			if i == 0:
				b = float(6 * x0 - 12 * x1 + 6 * x2)
				a = float(-3 * x0 + 9 * x1 - 9 * x2 + 3 * x3)
				c = float(3 * x1 - 3 * x0)

			else:
				b = float(6 * y0 - 12 * y1 + 6 * y2)
				a = float(-3 * y0 + 9 * y1 - 9 * y2 + 3 * y3)
				c = float(3 * y1 - 3 * y0)

			if abs(a) < 1e-12:        # Numerical robustness
				if abs(b) < 1e-12:    # Numerical robustness
					continue

				t = -c / b

				if 0 < t and t < 1:
					tvalues.append(t)

				continue

			b2ac = float(b * b - 4 * c * a)

			if b2ac < 0:
				continue
			else:
				sqrtb2ac = math.sqrt(b2ac)

			t1 = (-b + sqrtb2ac) / (2 * a)
			if 0 < t1 and t1 < 1:
				tvalues.append(t1)

			t2 = (-b - sqrtb2ac) / (2 * a)
			if 0 < t2 and t2 < 1:
				tvalues.append(t2)

		for j in range(0,len(tvalues)):
			t = tvalues[j]
			mt = 1 - t
			x = (mt * mt * mt * x0) + (3 * mt * mt * t * x1) + (3 * mt * t * t * x2) + (t * t * t * x3)
			y = (mt * mt * mt * y0) + (3 * mt * mt * t * y1) + (3 * mt * t * t * y2) + (t * t * t * y3)

			points.append((Point(x, y), t))

		return points

	def solve_parallel(self, vector, fullOutput = False):
		'''Finds the t value along a cubic Bezier where a tangent (1st derivative) is parallel with the direction vector.
		vector: a pair of values representing the direction of interest (magnitude is ignored).
		returns 0.0 <= t <= 1.0 or None
		
		# Solving the dot product of cubic beziers first derivate to the vector given B'(t) x V. Two vectors are perpendicular if their dot product is zero. 
		# So if you could find the (1) perpendicular of V it will be collinear == tangent of the curve so the equation to be solved is:
		# B'(t) x V(x,y) = 0; -(a*t^2 + b*t + c)*x + (g*t^2 + h*t + i)*y = 0 solved for t, where a,b,c are coefs for X and g,h,i for Y B'(t) derivate of curve
		# 
		# Inspired by answer given by 'unutbu' on the stackoverflow question: http://stackoverflow.com/questions/20825173/how-to-find-a-point-if-any-on-quadratic-bezier-with-a-given-tangent-direction
		# Recoded and recalculated for qubic beziers. Used 'Rearrange It' app at http://www.wolframalpha.com/widgets/view.jsp?id=4be4308d0f9d17d1da68eea39de9b2ce was invaluable.
		#
		# DOTO: Fix calculation optimization error - will yield false positive result in cases #1 and #2 if vector is 45 degrees
		'''
		from math import sqrt

		def polyCoef(p): # Helper function
			a = float(-3 * p[0] + 9 * p[1] - 9 * p[2] + 3 * p[3])
			b = float(6 * p[0] - 12 * p[1] + 6 * p[2])
			c = float(3 * p[1] - 3 * p[0])
			return a, b, c

		# - Get Coefs
		x , y = vector[0], vector[1]
		a, b, c = polyCoef([self.p0.x, self.p1.x, self.p2.x, self.p3.x])
		g, h, i = polyCoef([self.p0.y, self.p1.y, self.p2.y, self.p3.y])

		# -- Support eq
		bx_hy = float(b*x - h*y)
		cx_iy = float(c*x - i*y)
		ax_gy = float(a*x - g*i)

		if x == 0 and y != 0 and g == 0 and h != 0 : #1 Optimisation
			t = -i/h
			return t

		elif x != 0 and a == (g*y)/x and bx_hy != 0: #2 Optimisation
			t = -cx_iy/bx_hy
			return t

		elif ax_gy != 0: #3 Regular result
			longPoly = float(bx_hy*bx_hy - 4*cx_iy*ax_gy)
			
			if longPoly > 0:
				sqrtLongPoly = sqrt(longPoly)
				
				numrPos = sqrtLongPoly - bx_hy
				numrNeg = -sqrtLongPoly - bx_hy
				
				dnom = 2*ax_gy

				ts = [numrPos/dnom, numrNeg/dnom] # solved t's for numrPos and numrNeg
				tc = [t for t in ts if 0 <= t <= 1] # get correct t
				
				if fullOutput:
					return ts
				else:
					if len(tc) and len(tc) < 2:
						return tc[0]
					else:
						return None # Undefined point of intersection - two t's		
				
			else:
				return None

	def solve_proportional_handles(self, ratio=(.3,.3)):
		'''Equalizes handle length to given float(ratio_p1, ratio_p2 )'''

		def getNewPoint(targetPoint, referencePoint, alternateReferencePoint, distance):
			if targetPoint.y == referencePoint.y and targetPoint.x == referencePoint.x:
				phi = math.atan2(alternateReferencePoint.y - referencePoint.y, alternateReferencePoint.x - referencePoint.x)
			else:
				phi = math.atan2(targetPoint.y - referencePoint.y, targetPoint.x - referencePoint.x)
			
			x = referencePoint.x + math.cos(phi) * distance
			y = referencePoint.y + math.sin(phi) * distance

			return (x, y)
		
		# - Get distances
		a = math.hypot(self.p0.x - self.p1.x, self.p0.y - self.p1.y) 
		b = math.hypot(self.p1.x - self.p2.x, self.p1.y - self.p2.y)
		c = math.hypot(self.p2.x - self.p3.x, self.p2.y - self.p3.y)

		#- Calculate equal distance
		eqDistance_p1 = (a + b + c) * ratio[0]
		eqDistance_p2 = (a + b + c) * ratio[1]

		new_p1 = getNewPoint(self.p1, self.p0, self.p2, eqDistance_p1)
		new_p2 = getNewPoint(self.p2, self.p3, self.p1, eqDistance_p2)

		return self.__class__(self.p0.tuple, new_p1, new_p2, self.p3.tuple)

	def solve_handle_distance_from_base(self, ratio=(.5,.5)):
		'''Finds new handle positions for given ratio from base points.'''
		from typerig.core.func.geometry import line_intersect

		handle_intersection  = Point(line_intersect(*self.tuple))
		hl0i = Line(self.p0, handle_intersection)
		hl1i = Line(self.p3, handle_intersection)

		new_p1 = hl0i.solve_point(ratio[0])
		new_p2 = hl1i.solve_point(ratio[1])

		return self.__class__(self.p0.tuple, new_p1.tuple, new_p2.tuple, self.p3.tuple)

	def get_handle_length(self):
		'''Returns handle length and radii from base points.'''
		from typerig.core.func.geometry import line_intersect

		hl0 = Line(self.p0, self.p1)
		hl1 = Line(self.p2, self.p3)
		
		handle_intersection  = Point(line_intersect(*self.tuple))

		hl0i = Line(self.p0, handle_intersection)
		hl1i = Line(self.p3, handle_intersection)

		radius_0 = hl0i.length if not math.isnan(hl0i.length) else 0.
		radius_1 = hl1i.length if not math.isnan(hl1i.length) else 0.

		handle_0 = hl0.length if not math.isnan(hl0.length) else 0.
		handle_1 = hl0.length if not math.isnan(hl1.length) else 0.

		#ratio_0 = ratfrac(hl0.length, radius_0, 1.)
		#ratio_1 = ratfrac(hl1.length, radius_1, 1.)

		return (radius_0, handle_0), (radius_1, handle_1)

	def solve_hobby(self, curvature=(.9,.9)):
		'''Calculates and applies John Hobby's mock-curvature-smoothness by given curvature - tuple(float,float) or (float)
		Based on Metapolator's Hobby Spline by Juraj Sukop, Lasse Fister, Simon Egli
		'''
		from math import atan2, degrees, pi, sin, cos, radians, e, sqrt
		
		def arg(x): # Phase
			return math.atan2(x.imag, x.real)

		def hobby(theta, phi):
			'''John Hobby and METAFONT book: "Velocity" function'''
			st, ct = math.sin(theta), math.cos(theta)
			sp, cp = math.sin(phi), math.cos(phi)
			velocity = (2 + math.sqrt(2) * (st - 1/16*sp) * (sp - 1/16*st) * (ct - cp)) / (3 * (1 + 0.5*(math.sqrt(5) - 1) * ct + 0.5*(3 - math.sqrt(5)) * cp))
			return velocity

		def controls(z0, w0, alpha, beta, w1, z1):
			'''Given two points in a path, and the angles of departure and arrival
			at each one, this function finds the appropiate control points of the
			Bezier's curve, using John Hobby's algorithm'''
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			u = z0 + math.e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / alpha
			v = z1 - math.e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / beta
			return u, v
		
		delta0 = complex(self.p1.x, self.p1.y) - complex(self.p0.x, self.p0.y)
		if delta0 == 0: return self # Retracted handle, do not modify

		rad0 = atan2(delta0.real, delta0.imag)
		w0 = complex(math.sin(rad0), math.cos(rad0)) 
		
		delta1 = complex(self.p3.x, self.p3.y) - complex(self.p2.x, self.p2.y)
		if delta1 == 0: return self  # Retracted handle, do not modify

		rad1 = atan2(delta1.real, delta1.imag)
		w1 = complex(math.sin(rad1), math.cos(rad1))
		
		if isinstance(curvature, tuple):
			alpha, beta = curvature
		else:
			alpha = beta = curvature

		u, v = controls(complex(self.p0.x, self.p0.y), w0, alpha, beta, w1, complex(self.p3.x, self.p3.y))
		
		return self.__class__(self.p0.tuple, (u.real, u.imag), (v.real, v.imag), self.p3.tuple)		

	def solve_hobby_curvature(self):
		'''Returns current curvature coefficients (complex(alpha), complex(beta)) for 
		both handles according to John Hobby's mock-curvature calculation
		'''
		def arg(x): # Phase
			return math.atan2(x.imag, x.real)

		def hobby(theta, phi):
			'''John Hobby and METAFONT book: "Velocity" function'''
			st, ct = math.sin(theta), math.cos(theta)
			sp, cp = math.sin(phi), math.cos(phi)
			velocity = (2 + math.sqrt(2) * (st - 1/16*sp) * (sp - 1/16*st) * (ct - cp)) / (3 * (1 + 0.5*(math.sqrt(5) - 1) * ct + 0.5*(3 - math.sqrt(5)) * cp))
			return velocity

		def getCurvature(z0, w0, u, v, w1, z1):
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			alpha=  math.e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / (u - z0)
			beta =  -math.e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / (v - z1)
			return alpha, beta
		
		delta0 = complex(self.p1.x, self.p1.y) - complex(self.p0.x, self.p0.y)
		rad0 = math.atan2(delta0.real, delta0.imag)
		w0 = complex(math.sin(rad0), math.cos(rad0))
		
		delta1 = complex(self.p3.x, self.p3.y) - complex(self.p2.x, self.p2.y)
		rad1 = math.atan2(delta1.real, delta1.imag)
		w1 = complex(math.sin(rad1), math.cos(rad1))

		u = complex(self.p1.x, self.p1.y)
		v = complex(self.p2.x, self.p2.y)
		
		alpha, beta = getCurvature(complex(self.p0.x, self.p0.y), w0, u, v, w1, complex(self.p3.x, self.p3.y))
		return alpha, beta

	def solve_tunni(self):
		'''Make proportional handles keeping curvature and on-curve point positions 
		Based on modified Andres Torresi implementation of Eduardo Tunni's method for control points
		'''
		practicalInfinity = Point(100000, 100000)

		# - Helper functions
		def getCrossing(p0, p1, p2, p3):
			# - Init
			diffA = p1 - p0 						# p1.x - p0.x, p1.y - p0.y
			prodA = p1 & Point(p0.y,-p0.x) 			# p1.x * p0.y - p0.x * p1.y
			
			diffB = p3 - p2 								
			prodB = p3 & Point(p2.y,-p2.x) 

			# - Get intersection
			det = diffA & Point(diffB.y, -diffB.x) 	# diffA.x * diffB.y - diffB.x * diffA.y
			x = diffB.x * prodA - diffA.x * prodB
			y = diffB.y * prodA - diffA.y * prodB

			try:
				return Point(x / det, y / det)

			except ZeroDivisionError:
				return practicalInfinity

		def setProportion(pointA, pointB, prop):
			# - Set proportions according to Edaurdo Tunni
			sign = lambda x: (1, -1)[x < 0] # Helper function
			xDiff = max(pointA.x, pointB.x) - min(pointA.x, pointB.x)
			yDiff = max(pointA.y, pointB.y) - min(pointA.y, pointB.y)
			xEnd = pointA.x + xDiff * prop * sign(pointB.x - pointA.x)
			yEnd = pointA.y + yDiff * prop * sign(pointB.y - pointA.y)

			return Point(xEnd, yEnd)

		# - Run ------------------
		# -- Init
		crossing = getCrossing(self.p3, self.p2, self.p0, self.p1)
		
		if crossing != practicalInfinity:
			node2extrema = math.hypot(self.p3.x - crossing.x, self.p3.y - crossing.y)
			node2bcp = math.hypot(self.p3.x - self.p2.x, self.p3.y - self.p2.y)
			proportion = (node2bcp / node2extrema)

			# -- Calculate
			bcp2b = setProportion(self.p0, crossing, proportion)
			propA = math.hypot(self.p0.x - self.p1.x , self.p0.y - self.p1.y) / math.hypot(self.p0.x - crossing.x, self.p0.y - crossing.y)
			propB = math.hypot(self.p0.x - bcp2b.x, self.p0.y - bcp2b.y) / math.hypot(self.p0.x - crossing.x, self.p0.y - crossing.y)
			propMean = (propA + propB) / 2

			bcp2c = setProportion(self.p0, crossing, propMean)
			bcp1b = setProportion(self.p3, crossing, propMean)

			return self.__class__(self.p0.tuple, (bcp2c.x, bcp2c.y), (bcp1b.x, bcp1b.y), self.p3.tuple)
		else:
			return self

	def lerp_first(self, shift):
		diffBase = self.p3 - self.p0
		diffP1 = self.p3 - self.p1
		diffP2 = self.p3 - self.p2

		if diffBase.x != 0:
			self.p1.x += (diffP1.x/diffBase.x)*shift.x
			self.p2.x += (diffP2.x/diffBase.x)*shift.x

		if diffBase.y != 0:
			self.p1.y += (diffP1.y/diffBase.y)*shift.y
			self.p2.y += (diffP2.y/diffBase.y)*shift.y

		self.p0 += shift

		return self.__class__(self.p0.tuple, self.p1.tuple, self.p2.tuple, self.p3.tuple)

	def lerp_last(self, shift):
		diffBase = self.p0 - self.p3
		diffP1 = self.p0 - self.p1
		diffP2 = self.p0 - self.p2

		if diffBase.x != 0:
			self.p1.x += (diffP1.x/diffBase.x)*shift.x
			self.p2.x += (diffP2.x/diffBase.x)*shift.x
			
		if diffBase.y != 0:
			self.p1.y += (diffP1.y/diffBase.y)*shift.y
			self.p2.y += (diffP2.y/diffBase.y)*shift.y

		self.p3 += shift

		return self.__class__(self.p0.tuple, self.p1.tuple, self.p2.tuple, self.p3.tuple)

	# -- Collinearity / Channel Processing ---------------------------
	def match_direction_to(self, other):
		'''
		Check if this curve needs direction reversal to match another curve.
		
		Args:
			other: CubicBezier object to match
		
		Returns:
			(matched_curve, was_reversed): Tuple of matched curve and reversal flag
		'''
		dist_same = self.p0.diff_to(other.p0) + self.p3.diff_to(other.p3)
		dist_reversed = self.p0.diff_to(other.p3) + self.p3.diff_to(other.p0)
		
		if dist_reversed < dist_same:
			return self.doSwap(), True
		
		return self, False

	def _set_handle_polar(self, base_point, angle, length):
		'''
		Calculate handle position using polar coordinates.
		Internal helper method.
		
		Args:
			base_point: Point object (anchor point)
			angle: Angle in radians
			length: Handle length
		
		Returns:
			Point object (handle position)
		'''
		if math.isnan(angle) or math.isnan(length) or length == 0:
			return Point(base_point.x, base_point.y)
		
		return Point(
			base_point.x + length * math.cos(angle),
			base_point.y + length * math.sin(angle)
		)

	def _equalize_points(self, point_0, point_1, target_distance):
		'''
		Position two points equidistant from their centerline.
		Internal helper method.
		
		Args:
			point_0, point_1: Point objects
			target_distance: Desired distance between points
		
		Returns:
			(new_point_0, new_point_1): Tuple of repositioned points
		'''
		# Calculate centerline
		center_x = (point_0.x + point_1.x) / 2.0
		center_y = (point_0.y + point_1.y) / 2.0
		
		# Get angle from center to point_0
		dx = point_0.x - center_x
		dy = point_0.y - center_y
		angle = math.atan2(dy, dx)
		
		# Position points at half target distance from center
		half_dist = target_distance / 2.0
		
		new_point_0 = Point(
			center_x + half_dist * math.cos(angle),
			center_y + half_dist * math.sin(angle)
		)
		
		new_point_1 = Point(
			center_x - half_dist * math.cos(angle),
			center_y - half_dist * math.sin(angle)
		)
		
		return new_point_0, new_point_1

	def make_collinear(self, other, mode=0, equalize=False, target_width=None):
		'''
		Make this curve collinear with another curve by aligning control point handles.
		Optionally equalize the distance between curves for uniform stems.
		
		Args:
			other: CubicBezier object to align with
			mode: 0 = use self angles, 1 = use other angles, -1 = average
			equalize: If True, make curves equidistant (uniform stem width)
			target_width: If set, use this specific distance. If None, use average
		
		Returns:
			(modified_self, modified_other): Tuple of two aligned CubicBezier objects
		
		Example:
			>>> curve_a = CubicBezier(...)
			>>> curve_b = CubicBezier(...)
			>>> # Align with averaged angles
			>>> aligned_a, aligned_b = curve_a.make_collinear(curve_b, mode=-1)
			>>> # Align and equalize for uniform stem
			>>> aligned_a, aligned_b = curve_a.make_collinear(curve_b, mode=-1, equalize=True)
		'''
		
		# Match curve directions
		other_matched, was_reversed = other.match_direction_to(self)
		
		c0 = self
		c1 = other_matched
		
		# Calculate target distances if equalizing
		if equalize:
			dist_start = c0.p0.diff_to(c1.p0)
			dist_end = c0.p3.diff_to(c1.p3)
			
			if target_width is None:
				# Use average of start and end distances
				target_width = (dist_start + dist_end) / 2.0
			
			# Equalize on-curve points
			new_p0_0, new_p0_1 = c0._equalize_points(c0.p0, c1.p0, target_width)
			new_p3_0, new_p3_1 = c0._equalize_points(c0.p3, c1.p3, target_width)
		else:
			# Keep original positions
			new_p0_0 = Point(c0.p0.x, c0.p0.y)
			new_p0_1 = Point(c1.p0.x, c1.p0.y)
			new_p3_0 = Point(c0.p3.x, c0.p3.y)
			new_p3_1 = Point(c1.p3.x, c1.p3.y)
		
		# Process first handle pair (p0->p1)
		# Use add=0 to get raw angle without 90-degree offset
		angle_0_out = c0.p0.angle_to(c0.p1, add=0)
		angle_1_out = c1.p0.angle_to(c1.p1, add=0)
		
		length_0_out = c0.p0.diff_to(c0.p1)
		length_1_out = c1.p0.diff_to(c1.p1)
		
		if (not math.isnan(angle_0_out) and not math.isnan(angle_1_out) and 
			length_0_out > 0 and length_1_out > 0):
			
			# Calculate target angle based on mode
			if mode == 0:
				target_angle_out = angle_0_out
			elif mode == 1:
				target_angle_out = angle_1_out
			else:  # mode == -1
				target_angle_out = (angle_0_out + angle_1_out) / 2.0
			
			# Apply target angle (from new positions if equalized)
			new_p1_0 = c0._set_handle_polar(new_p0_0, target_angle_out, length_0_out)
			new_p1_1 = c0._set_handle_polar(new_p0_1, target_angle_out, length_1_out)
		else:
			# Keep original handles
			new_p1_0 = Point(c0.p1.x, c0.p1.y)
			new_p1_1 = Point(c1.p1.x, c1.p1.y)
		
		# Process second handle pair (p3->p2)
		angle_0_in = c0.p3.angle_to(c0.p2, add=0)
		angle_1_in = c1.p3.angle_to(c1.p2, add=0)
		
		length_0_in = c0.p3.diff_to(c0.p2)
		length_1_in = c1.p3.diff_to(c1.p2)
		
		if (not math.isnan(angle_0_in) and not math.isnan(angle_1_in) and 
			length_0_in > 0 and length_1_in > 0):
			
			# Calculate target angle based on mode
			if mode == 0:
				target_angle_in = angle_0_in
			elif mode == 1:
				target_angle_in = angle_1_in
			else:  # mode == -1
				target_angle_in = (angle_0_in + angle_1_in) / 2.0
			
			# Apply target angle (from new positions if equalized)
			new_p2_0 = c0._set_handle_polar(new_p3_0, target_angle_in, length_0_in)
			new_p2_1 = c0._set_handle_polar(new_p3_1, target_angle_in, length_1_in)
		else:
			# Keep original handles
			new_p2_0 = Point(c0.p2.x, c0.p2.y)
			new_p2_1 = Point(c1.p2.x, c1.p2.y)
		
		# Create new curves
		result_0 = self.__class__(new_p0_0.tuple, new_p1_0.tuple, new_p2_0.tuple, new_p3_0.tuple)
		result_1 = self.__class__(new_p0_1.tuple, new_p1_1.tuple, new_p2_1.tuple, new_p3_1.tuple)
		
		# If other was reversed, reverse result back
		if was_reversed:
			result_1 = result_1.doSwap()
		
		return result_0, result_1


	# -- Corner operations -----------------------------------------
	def solve_distance_extended(self, distance, from_start=True, timeStep=.001):
		'''Find time t at which chord distance from an endpoint equals given distance.
		Supports extrapolation (t outside [0,1]) for extension beyond curve endpoints.
		Uses de Casteljau via solve_slice for proper handle adjustment.
		
		Args:
			distance: Positive = inward along curve, negative = outward (extrapolation beyond endpoint)
			from_start: If True measure from p0, if False measure from p3
			timeStep: Probing resolution
		
		Returns:
			float: t parameter (may be outside [0,1] for extrapolation)
		'''
		if from_start:
			ref = self.p0
			t = 0.
			step = timeStep if distance >= 0 else -timeStep
		else:
			ref = self.p3
			t = 1.
			step = -timeStep if distance >= 0 else timeStep

		target = abs(distance)
		measure = 0.

		while measure < target:
			t += step

			# - Safety: do not extrapolate too far
			if abs(t) > 3. or abs(1. - t) > 3.:
				break

			pt = self.solve_point(t)
			measure = math.hypot(pt.x - ref.x, pt.y - ref.y)

		return t

	def trim_at_start(self, distance, timeStep=.001):
		'''Trim (positive) or extend (negative) the curve from the p0 side.
		Uses de Casteljau splitting to properly adjust control point handles.
		Positive distance moves p0 towards p3 (shorter curve).
		Negative distance extends p0 away from p3 (longer curve, extrapolated).
		
		Returns:
			CubicBezier: New curve with adjusted start point and handles.
		'''
		t = self.solve_distance_extended(distance, from_start=True, timeStep=timeStep)
		_, result = self.solve_slice(t)
		return result

	def trim_at_end(self, distance, timeStep=.001):
		'''Trim (positive) or extend (negative) the curve from the p3 side.
		Uses de Casteljau splitting to properly adjust control point handles.
		Positive distance moves p3 towards p0 (shorter curve).
		Negative distance extends p3 away from p0 (longer curve, extrapolated).
		
		Returns:
			CubicBezier: New curve with adjusted end point and handles.
		'''
		t = self.solve_distance_extended(distance, from_start=False, timeStep=timeStep)
		result, _ = self.solve_slice(t)
		return result

	@staticmethod
	def corner_mitre(segment_in, segment_out, mitre_size, is_radius=False):
		'''Mitre or loop a corner between two segments meeting at a point.
		Works with both CubicBezier curves and Line segments, properly 
		extrapolating/interpolating along curves via de Casteljau.

		Args:
			segment_in: CubicBezier or Line ending at the corner (p3 for curves, p1 for lines)
			segment_out: CubicBezier or Line starting from the corner (p0 for curves and lines)
			mitre_size: Positive for mitre (trim inward), negative for loop/overlap (extend outward).
			is_radius: If True, |mitre_size| is used directly as the shift distance along each segment.
					   If False, mitre_size is the desired mitre edge length and shift is calculated
					   from the angle between the tangent directions at the corner.

		Returns:
			tuple: (new_segment_in, new_segment_out) - modified segments.
				   CubicBezier inputs yield CubicBezier outputs with proper handles.
				   Line inputs yield Line outputs.
		'''
		# - Determine tangent directions at the corner point
		# -- Direction pointing AWAY from the corner, back along the incoming segment
		if isinstance(segment_in, CubicBezier):
			in_tangent = segment_in.p3 - segment_in.p2

			# Handle retracted BCPs (p2 == p3): fall back to chord direction
			if math.hypot(in_tangent.x, in_tangent.y) < 1e-10:
				in_tangent = segment_in.p3 - segment_in.p0

			prev_dir = Point(-in_tangent.x, -in_tangent.y)
		else:
			# Line: p0 -> p1 where p1 is at the corner
			prev_dir = segment_in.p0 - segment_in.p1

		# -- Direction pointing AWAY from the corner, forward along the outgoing segment
		if isinstance(segment_out, CubicBezier):
			out_tangent = segment_out.p1 - segment_out.p0

			# Handle retracted BCPs (p0 == p1): fall back to chord direction
			if math.hypot(out_tangent.x, out_tangent.y) < 1e-10:
				out_tangent = segment_out.p3 - segment_out.p0

			next_dir = Point(out_tangent.x, out_tangent.y)
		else:
			# Line: p0 is at the corner, p1 is away
			next_dir = segment_out.p1 - segment_out.p0

		# - Normalize to unit vectors
		prev_len = math.hypot(prev_dir.x, prev_dir.y)
		next_len = math.hypot(next_dir.x, next_dir.y)

		if prev_len < 1e-10 or next_len < 1e-10:
			return segment_in, segment_out  # Degenerate: coincident points

		prev_unit = Point(prev_dir.x / prev_len, prev_dir.y / prev_len)
		next_unit = Point(next_dir.x / next_len, next_dir.y / next_len)

		# - Calculate shift distance
		if not is_radius:
			# Angle between the two directions away from the corner
			cross = prev_unit.x * next_unit.y - prev_unit.y * next_unit.x
			dot = prev_unit.x * next_unit.x + prev_unit.y * next_unit.y
			angle = math.atan2(abs(cross), dot)

			if abs(math.sin(angle / 2.)) < 1e-10:
				return segment_in, segment_out  # Nearly straight, no mitre needed

			radius = abs((float(mitre_size) / 2.) / math.sin(angle / 2.))
		else:
			radius = abs(mitre_size)

		# - Apply sign: positive mitre_size = trim inward, negative = extend outward
		shift = radius if mitre_size >= 0 else -radius

		# - Trim/extend incoming segment at its end (p3 side)
		if isinstance(segment_in, CubicBezier):
			new_in = segment_in.trim_at_end(shift)
		else:
			new_end = Point(segment_in.p1.x + prev_unit.x * shift,
							segment_in.p1.y + prev_unit.y * shift)
			new_in = Line(segment_in.p0, new_end)

		# - Trim/extend outgoing segment at its start (p0 side)
		if isinstance(segment_out, CubicBezier):
			new_out = segment_out.trim_at_start(shift)
		else:
			new_start = Point(segment_out.p0.x + next_unit.x * shift,
							  segment_out.p0.y + next_unit.y * shift)
			new_out = Line(new_start, segment_out.p1)

		return new_in, new_out


if __name__ == "__main__":
	a = Line(((113.73076629638672, 283.6538391113281), (357.96154022216797, 415.3846130371094)))
	b = CubicBezier((145.7924041748047, 367.8679504394531), (222.71548461914062, 405.3679504394531), (317.9077911376953, 376.5217971801758), (328.48471450805664, 229.40641021728516))

	c = b.intersect_line(a)
	print(b.doSwap())
	
	f = CubicBezier((150, 370), (220, 400), (320, 380), (330, 230))
	print(f.lerp_last(Point(10,0)))

	curve_a = CubicBezier(Point(100, 100), Point(150, 120), Point(250, 130), Point(300, 110))
	curve_b = CubicBezier(Point(100, 200), Point(150, 180), Point(250, 170), Point(300, 190))
	
	# Just align handles (keep original positions)
	aligned_a, aligned_b = curve_a.make_collinear(curve_b, mode=-1)
	# Align handles + equalize distance (uniform stem)
	aligned_a, aligned_b = curve_a.make_collinear(curve_b, mode=-1, equalize=True)
	
	# Align + specific stem width
	aligned_a, aligned_b = curve_a.make_collinear(curve_b, mode=-1, equalize=True, target_width=120.0)