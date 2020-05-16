# MODULE: TypeRig / Core / Cubic Bezier (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2016-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import print_function
import math
from typerig.core.func.math import linInterp as lerp
from typerig.core.func.math import ratfrac
from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.transform import Transform
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line

# - Init -------------------------------
__version__ = '0.26.5'

# - Classes -----------------------------
class CubicBezier(object):
	def __init__(self, *argv):
		if len(argv) == 1:
			if isinstance(argv[0], self.__class__): # Clone
				self.p0, self.p1, self.p2, self.p3 = argv[0].p0, argv[0].p1, argv[0].p2, argv[0].p3
			
			if isMultiInstance(argv[0], (tuple, list)):
				self.p0, self.p1, self.p2, self.p3 = [Point(item) for item in argv[0]]

		if len(argv) == 4:
			if isMultiInstance(argv, (tuple, list)):
				self.p0, self.p1, self.p2, self.p3 = [Point(item) for item in argv]

			if isMultiInstance(argv, Point):
				self.p0, self.p1, self.p2, self.p3 = argv

		if len(argv) == 8:
			if isMultiInstance(argv, (float, int)):
				self.p0, self.p1, self.p2, self.p3 = [Point(argv[i], argv[i+1]) for i in range(len(argv)-1)]

		self.transform = Transform()
								
	def __repr__(self):
		return '<Cubic Bezier: {},{},{},{}>'.format(self.p0.tuple, self.p1.tuple, self.p2.tuple, self.p3.tuple)

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
	def asList(self):
		return 

	def doSwap(self):
		return self.__class__(self.p3, self.p2, self.p1, self.p0)

	def doTransform(self, transform=None):
		if transform is None: transform = self.transform
		self.p0.doTransform(transform)
		self.p1.doTransform(transform)
		self.p2.doTransform(transform)
		self.p3.doTransform(transform)
		
	# -- Solvers
	def solve_point(self, time):
		'''Find point on cubic bezier at given time '''
		rtime = 1 - time
		pt = (rtime**3)*self.p0 + 3*(rtime**2)*time*self.p1 + 3*rtime*(time**2)*self.p2 + (time**3)*self.p3
		return pt

	def solve_derivative(self, time):
		'''Returns point of on-curve point at given time and vector of 1st and 2nd derivative.'''
		a = -self.p0 + 3. * self.p1 - 3. * self.p2 + self.p3
		b = 3. * self.p0 - 6. * self.p1 + 3. * self.p2
		c = -3. * self.p0 + 3. * self.p1
		d = self.p0

		pt = a * time**3 + b * time**2 + c * time + d
		d1 = 3. * a * time**2 + 2. * b * time + c
		d2 = 6. * a * time + 2.* b
		
		return pt, d1, d2

	def solve_curvature(self, time):
		'''Find Curvature of on-curve point at given time'''
		pt, d1, d2 = self.solve_derivative(time)
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

	def solve_distance_start(self, distance, timeStep = .01 ):
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

	def solve_proportional_handles(self, proportion=.3):
		'''Equalizes handle length to given float(proportion)'''

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
		eqDistance = (a + b + c) * proportion

		new_p1 = getNewPoint(self.p1, self.p0, self.p2, eqDistance)
		new_p2 = getNewPoint(self.p2, self.p3, self.p1, eqDistance)

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
			st, ct = math.sin(theta), math.cos(theta)
			sp, cp = math.sin(phi), math.cos(phi)
			velocity = (2 + math.sqrt(2) * (st - 1/16*sp) * (sp - 1/16*st) * (ct - cp)) / (3 * (1 + 0.5*(math.sqrt(5) - 1) * ct + 0.5*(3 - math.sqrt(5)) * cp))
			return velocity

		def controls(z0, w0, alpha, beta, w1, z1):
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			u = z0 + math.e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / alpha
			v = z1 - math.e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / beta
			return u, v
		
		delta0 = complex(self.p1.x, self.p1.y) - complex(self.p0.x, self.p0.y)
		rad0 = atan2(delta0.real, delta0.imag)
		w0 = complex(math.sin(rad0), math.cos(rad0))
		
		delta1 = complex(self.p3.x, self.p3.y) - complex(self.p2.x, self.p2.y)
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
			return None

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

		return self.__class__(self.p0, self.p1, self.p2, self.p3)

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

		return self.__class__(self.p0, self.p1, self.p2, self.p3)