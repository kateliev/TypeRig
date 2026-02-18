# MODULE: TypeRig / Core / Math (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math, cmath, random

# - Init --------------------------------
__version__ = '0.28.0'

epsilon = 0.000001

# - Functions ---------------------------
# -- Linear algebra ---------------------
def zero_matrix(rows, cols):
	'''Creates a matrix filled with zeros '''
	M = []
	while len(M) < rows:
		M.append([])
		while len(M[-1]) < cols:
			M[-1].append(0.0)

	return M

def solve_equations(AM, BM):
	'''Pure python implementaton of numpy.linalg.solve as explained by:
	https://integratedmlai.com/system-of-equations-solution/
	'''
	for fd in range(len(AM)):
		fdScaler = 1.0 / AM[fd][fd]
		for j in range(len(AM)):
			AM[fd][j] *= fdScaler
		BM[fd][0] *= fdScaler
		for i in list(range(len(AM)))[0:fd] + list(range(len(AM)))[fd+1:]:
			crScaler = AM[i][fd]
			for j in range(len(AM)):
				AM[i][j] = AM[i][j] - crScaler * AM[fd][j]
			BM[i][0] = BM[i][0] - crScaler * BM[fd][0]
	return BM

# -- Data sets --------------------------
def normalize2max(values):
	'''Normalize all values to the maximum value in a given list. 
	
	Arguments:
		values (list(int of float));
	Returns: 
		list(float)
	'''
	return sorted([float(item)/max(values) for item in values])

def normalize2sum(values):
	'''Normalize all values to the sum of given list so the resuting sum is always 1.0 or close as possible. 
	
	Arguments: 
		values (list(int of float));
	Returns: 
		list(float)
	'''
	valSum = sum(values)
	return sorted([float(item)/valSum for item in values])

def renormalize(values, newRange, oldRange=None):
	'''Normalize all values to the maximum value in a given list and remap them in a new given range. 
	
	Arguments: 
		values (list(int of float)) : a list of values to be normalized
		newRange (tuple(float,float)): a new range for remapping (20,250)
		oldRange (tuple(float,float)) or None: the original range of values if None range is auto extracted from values given.
	Returns:
		list(float)
	'''
	if oldRange is not None:
		return sorted([(max(newRange) - min(newRange))*item + min(newRange) for item in [float(item - min(oldRange))/(max(oldRange) - min(oldRange)) for item in values]])
	else:
		return sorted([(max(newRange) - min(newRange))*item + min(newRange) for item in [float(item - min(values))/(max(values) - min(values)) for item in values]])

def maploc(axis_range, map_value):
	''' Return mapped location over specified axis by piecewise interpolation brtween neighboring location.
	Args:
		axis_range list(tuple(user_space, design_space)) : Given axis range
		map_value int : Desired location to be mapped
	Returns:
		int : new user location value
	Example: 
		axis_range = [(100, 28), (200, 40), (300, 60), (400, 80), (500, 91), (600, 106), (700, 126), (746, 140)]
		
		maploc(axis_range, 140)
		>>> 746
		
		maploc(axis_range, 150)
		>>> 778
	''' 
	def remapper(low, high, value):
		normal = (high[0] - low[0], high[1] - low[1])
		return int(low[0] + normal[0]*(float(value - low[1])/float(normal[1])))

	if len(axis_range) >= 2:
		sorted_axis = sorted(axis_range, key=lambda n: n[0])
		min_axis, max_axis = sorted_axis[0], sorted_axis[-1]
		
		if map_value < min_axis[1]:
			return remapper(sorted_axis[0], sorted_axis[1], map_value)

		elif map_value > max_axis[1]:
			return remapper(sorted_axis[-2], sorted_axis[-1], map_value)

		else:
			for i in range(len(sorted_axis)-1):
				low, high = sorted_axis[i], sorted_axis[i+1]
				if low[1] <= map_value <= high[1]:
					return remapper(low, high, map_value)

# -- Misc -------------------------------
def isclose(a, b, abs_tol = 1, rel_tol = 0.0):
	'''Tests approximate equality for values [a] and [b] within relative [rel_tol*] and/or absolute tolerance [abs_tol]

	*[rel_tol] is the amount of error allowed,relative to the larger absolute value of a or b. For example,
	to set a tolerance of 5%, pass tol=0.05. The default tolerance is 1e-9, which assures that the
	two values are the same within about9 decimal digits. rel_tol must be greater than 0.0
	'''
	if abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol):	return True
	return False

def isBetween(x, a, b):
	'''A broader test if a value is between two others'''
	return True if a <= x <= b or isclose(x, a, abs_tol=epsilon) or isclose(x, b, abs_tol=epsilon) else False

def roundFloat(f, error=1000000.):
	return round(f*error)/error

def round2base(x, base = 5):
	'''Rounds a value using given base increments'''
	return int(base * round(float(x)/base))

# -- Progressions & Fractions ----------------------------
def ratfrac(part, whole, fraction = 100):
	'''Calculates the ratio of part to whole expressed as fraction (percentage: 100 (default); mileage: 1000) '''
	return fraction*(float(part)/float(whole))

def linspread(start, end, count):
	'''Linear space generator object: will generate equally spaced numbers within given range'''
	yield float(start)

	for i in range(1, count-1):
		yield float(start + i*(end-start)/float((count-1))) #Adapted from NumPy.linespace

	yield float(end)

def geospread(start, end, count):
	'''Geometric space generator object: will generate elements of geometric progression within given range'''
	yield float(start)

	georate = math.sqrt(start*end)/start

	for i in range(1, count-1):
		yield start*(georate**(float(i*2)/(count-1)))

	yield float(end)

def randomize(value, constrain):
	'''Returns a random value within given constrain'''
	randomAngle = random.uniform(0.0,2*math.pi)
	value += int(math.cos(randomAngle)*constrain)

	return value  

# -- Interpolation --------------------------------------------------
def linInterp(t0, t1, t):
	'''Linear Interpolation: Returns value for given normal value (time) t within the range t0-t1.'''
	#return (max(t0,t1)-min(t0,t1))*t + min(t0,t1)
	return (t1 - t0)*t + t0

def bilinInterp(x, y, points):
	'''Bilinear Interpolate (x,y) from values associated with four points.

	The four points are a list of four triplets:  (x, y, value).
	The four points can be in any order.  They should form a rectangle.

		>>> bilinear_interpolation(12, 5.5,
		...                        [(10, 4, 100),
		...                         (20, 4, 200),
		...                         (10, 6, 150),
		...                         (20, 6, 300)])
		165.0

	'''
	# See formula at:  http://en.wikipedia.org/wiki/Bilinear_interpolation
	# Copy from https://stackoverflow.com/questions/8661537/how-to-perform-bilinear-interpolation-in-python
	# Note: ReAdapt!

	points = sorted(points)               # order points by x, then by y
	(x1, y1, q11), (_x1, y2, q12), (x2, _y1, q21), (_x2, _y2, q22) = points

	if x1 != _x1 or x2 != _x2 or y1 != _y1 or y2 != _y2:
		raise ValueError('points do not form a rectangle')
	if not x1 <= x <= x2 or not y1 <= y <= y2:
		raise ValueError('(x, y) not within the rectangle')

	return (q11 * (x2 - x) * (y2 - y) +
			q21 * (x - x1) * (y2 - y) +
			q12 * (x2 - x) * (y - y1) +
			q22 * (x - x1) * (y - y1)
		   ) / ((x2 - x1) * (y2 - y1) + 0.0)
	
def slerp_angle(a0, a1, t):
	'''Interpolate two angles along the shorter arc.
	Both angles in radians. Returns angle in radians.
	'''
	# Difference normalised to [-pi, pi]
	diff = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
	return a0 + diff * t

def interpolate_directional(data_a, data_b, t, t_angle=None):
	from typerig.core.objects.node import DirectionalNode
	
	'''Interpolate two directional contour descriptions.

	Interpolates on-curve positions linearly and handle angles
	angularly (short-arc SLERP on the unit circle). Magnitudes
	interpolate linearly. This produces smoother intermediate
	shapes than naive XY handle interpolation — the curve stays
	"on course" through the blend.

	Args:
		data_a, data_b : list[DirectionalNode] — must be same length
		t              : float — interpolation factor (0=a, 1=b)
		t_angle        : float or None — separate time for angle
		                 interpolation; defaults to t when None.
		                 Pass a different value for anisotropic blends.

	Returns:
		list[DirectionalNode]
	'''
	assert len(data_a) == len(data_b), \
		'Incompatible: {} vs {} DirectionalNode elements'.format(len(data_a), len(data_b))

	if t_angle is None:
		t_angle = t

	result = []

	for a, b in zip(data_a, data_b):
		# Linear position
		x = a.x + (b.x - a.x) * t
		y = a.y + (b.y - a.y) * t

		# Angular SLERP (short arc) for handle directions
		a_out = slerp_angle(a.angle_out, b.angle_out, t_angle)
		a_in  = slerp_angle(a.angle_in,  b.angle_in,  t_angle)

		# Linear magnitude
		m_out = a.mag_out + (b.mag_out - a.mag_out) * t
		m_in  = a.mag_in  + (b.mag_in  - a.mag_in)  * t

		result.append(DirectionalNode(
			x=x, y=y,
			angle_out=a_out, mag_out=m_out,
			angle_in=a_in,   mag_in=m_in,
			smooth=a.smooth,
		))

	return result

# -- Drawing ---------------------------------------------------------
def two_point_circle(p1, p2):
	'''Calculate the center point and radius of a circle 
	based on two points on the circle's diameter'''

	cx = (p1[0] + p2[0]) / 2
	cy = (p1[1] + p2[1]) / 2
	distance = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
	radius = distance / 2

	return ((cx, cy), radius)

def three_point_circle(p1, p2, p3):
	'''Three point circle implementation: Return the center and 
	radius of a circle that passes through three given points p1, p2, p3.
	Source: https://codegolf.stackexchange.com/questions/2289/circle-through-three-points
	'''
	
	temp = p2[0]*p2[0] + p2[1]*p2[1]
	bc = (p1[0]*p1[0] + p1[1]*p1[1] - temp) / 2
	cd = (temp - p3[0]*p3[0] - p3[1]*p3[1]) / 2
	det = (p1[0] - p2[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0])*(p1[1] - p2[1])

	if abs(det) < 1.0e-6: return (None, None)

	cx = (bc*(p2[1] - p3[1]) - cd * (p1[1] - p2[1])) / det
	cy = ((p1[0] - p2[0]) * cd - (p2[0] - p3[0]) * bc) / det

	radius = math.sqrt((cx - p1[0])**2 + (cy - p1[1])**2)
	return ((cx, cy), radius)

def two_point_square(p1, p2):
	'''Two point square implementation, where the two points given p1 and p2 form the square's diagonal.
	Source: https://math.stackexchange.com/questions/506785/given-two-diagonally-opposite-points-on-a-square-how-to-calculate-the-other-two
	'''
	x1, y1 = p1 	 # First corner
	x2, y2 = p2 	 # Third corner

	xc = (x1 + x2)/2    
	yc = (y1 + y2)/2 # Center point

	xd = (x1 - x2)/2    
	yd = (y1 - y2)/2 # Half-diagonal

	x3 = xc - yd  	 # Second corner
	y3 = yc + xd

	x4 = xc + yd 	 # Fourth corner
	y4 = yc - xd 	

	return (p1, (x3,y3), p2, (x4, y4))

def two_mid_square(m1, m2):
	'''Find a square by given midpoints m1 and m2 of two adjacent sides. 
	Ideal for finding squares that inscribe a circle 
	'''
	mx1, my1 = m1 # First midpoint
	mx2, my2 = m2 # Second midpoint

	mxc = (mx1 + mx2)/2    
	myc = (my1 + my2)/2  

	mxd = (mx1 - mx2)/2    
	myd = (my1 - my2)/2 

	xc = mxc + myd 	# Square center
	yc = myc - mxd 	
	
	x2 = mxc - myd	# Second corner
	y2 = myc + mxd

	xd = xc - x2   
	yd = yc - y2

	x1 = xc - yd	# First corner
	y1 = yc + xd

	x3 = xc + yd	# Third corner
	y3 = yc - xd

	x4 = xc + xd	# Forth corner
	y4 = yc + yd

	return ((x1,y1), (x2,y2), (x3,y3), (x4,y4))

def hobby_velocity(theta, phi):
	'''From John Hobby and METAFONT book'''
	n = 2 + math.sqrt(2)*(math.sin(theta) - math.sin(phi)/16)*(math.sin(phi) - math.sin(theta)/16)*(math.cos(theta) - math.cos(phi))
	m = 3*(1 + 0.5*(math.sqrt(5)-1)*math.cos(theta) + 0.5*(3 - math.sqrt(5))*math.cos(phi))
	return n/m

def hobby_control_points(z0, z1, theta=0., phi=0., alpha=1., beta=1.):
	'''Given two points in a path, and the angles of departure and arrival
	at each one, this function finds the appropiate control points of the
	Bezier's curve, using John Hobby's algorithm (METAFONT book)'''
	i = complex(0,1)
	u = z0 + cmath.exp(i*theta)*(z1 - z0)*hobby_velocity(theta, phi)/alpha #was *alpha
	v = z1 - cmath.exp(-i*phi)*(z1 - z0)*hobby_velocity(phi, theta)/beta #was *beta
	return (u,v)

# - Test ----------------------------------------------------------------	
if __name__ == '__main__':
	r = range(105,415,10)
	a = 0.5
	b = 0.7
	x = 8.0000008
	points = [(10, 4, 100), (20, 4, 200), (10, 6, 150), (20, 6, 300)]
	axis_range = [(100, 28), (200, 40), (300, 60), (400, 80), (500, 91), (600, 106), (700, 126), (746, 140)]

	print(normalize2max(r))
	print(normalize2sum(r))
	print(renormalize(r, (20,500), oldRange=None))
	print(isclose(a, b, abs_tol = 0.1, rel_tol = 0.0))
	print(isBetween(0.67, a, b))
	print(roundFloat(x, error=1000000.))
	print(round2base(x, base = 5))
	print(ratfrac(a, b, fraction = 100))
	print(list(linspread(100, 700, 11)))
	print(list(geospread(100, 700, 11)))
	print(randomize(a, 2))
	print(linInterp(10, 20, .5))
	print(bilinInterp(12, 5.5, points))
	print(maploc(axis_range, 140))
	print(three_point_circle((10,10), (20,20), (3,5)))
	print(two_point_square((0,0), (10,10)))
	print(find_square((50,0), (100,50)))
	print(two_point_square((0,0), (34,138)))
	print(find_square((60,95), (-9,112)))

