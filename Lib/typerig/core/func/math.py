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

# -- Geometric primitives ---------------
def midpoint(p1, p2):
	'''Return the midpoint between two points.

	Arguments:
		p1, p2 (tuple): Points as (x, y).

	Returns:
		tuple: Midpoint (x, y).
	'''
	return ((p1[0] + p2[0]) / 2., (p1[1] + p2[1]) / 2.)

def reflect_point(point, axis_p1, axis_p2):
	'''Reflect a point across an arbitrary line defined by two points.

	Arguments:
		point (tuple): Point to reflect (x, y).
		axis_p1, axis_p2 (tuple): Two points defining the reflection axis.

	Returns:
		tuple: Reflected point (x, y).
	'''
	px, py = point
	x1, y1 = axis_p1
	x2, y2 = axis_p2

	dx, dy = x2 - x1, y2 - y1
	len_sq = dx * dx + dy * dy

	if len_sq < 1e-12:
		return point

	t = ((px - x1) * dx + (py - y1) * dy) / len_sq
	proj_x = x1 + t * dx
	proj_y = y1 + t * dy

	return (2. * proj_x - px, 2. * proj_y - py)

def rotate_points(points, center, angle_deg):
	'''Rotate a list of points around a center by a given angle.

	Arguments:
		points (list[tuple]): Points as [(x, y), ...].
		center (tuple): Center of rotation (x, y).
		angle_deg (float): Rotation angle in degrees (CCW positive).

	Returns:
		list[tuple]: Rotated points.
	'''
	cx, cy = center
	angle_rad = math.radians(angle_deg)
	cos_a = math.cos(angle_rad)
	sin_a = math.sin(angle_rad)

	result = []

	for px, py in points:
		dx = px - cx
		dy = py - cy
		result.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))

	return result

def perpendicular_bisector(p1, p2, length=1000.):
	'''Return two points defining the perpendicular bisector of a segment.

	Arguments:
		p1, p2 (tuple): Segment endpoints (x, y).
		length (float): Half-length of the returned bisector line.

	Returns:
		tuple: Two points ((x1, y1), (x2, y2)) on the bisector.
	'''
	mx, my = midpoint(p1, p2)
	dx, dy = p2[0] - p1[0], p2[1] - p1[1]
	seg_len = math.hypot(dx, dy)

	if seg_len < 1e-12:
		return ((mx, my - length), (mx, my + length))

	# Perpendicular direction (normalized)
	nx, ny = -dy / seg_len, dx / seg_len

	return ((mx - nx * length, my - ny * length), (mx + nx * length, my + ny * length))

def angle_bisector(p1, vertex, p2, length=1000.):
	'''Return two points defining the angle bisector at a vertex.

	Arguments:
		p1 (tuple): First ray endpoint (x, y).
		vertex (tuple): Vertex of the angle (x, y).
		p2 (tuple): Second ray endpoint (x, y).
		length (float): Length of the returned bisector ray from vertex.

	Returns:
		tuple: Two points (vertex, bisector_point) on the bisector.
	'''
	vx, vy = vertex

	# Unit vectors from vertex to each point
	d1x, d1y = p1[0] - vx, p1[1] - vy
	d2x, d2y = p2[0] - vx, p2[1] - vy
	len1 = math.hypot(d1x, d1y)
	len2 = math.hypot(d2x, d2y)

	if len1 < 1e-12 or len2 < 1e-12:
		return (vertex, vertex)

	u1x, u1y = d1x / len1, d1y / len1
	u2x, u2y = d2x / len2, d2y / len2

	# Bisector direction = sum of unit vectors
	bx, by = u1x + u2x, u1y + u2y
	blen = math.hypot(bx, by)

	if blen < 1e-12:
		# Points are opposite — bisector is perpendicular
		bx, by = -u1y, u1x
		blen = 1.

	bx, by = bx / blen, by / blen

	return (vertex, (vx + bx * length, vy + by * length))

# -- Ellipses ----------------------------
def two_point_ellipse(p1, p2):
	'''Axis-aligned ellipse inscribed in the rectangle defined by
	two diagonally opposite corners.

	Arguments:
		p1, p2 (tuple): Diagonal corners (x, y).

	Returns:
		tuple: (center, (semi_a, semi_b)) where center is (cx, cy)
			and semi_a, semi_b are the horizontal and vertical semi-axes.
	'''
	cx = (p1[0] + p2[0]) / 2.
	cy = (p1[1] + p2[1]) / 2.
	a = abs(p2[0] - p1[0]) / 2.
	b = abs(p2[1] - p1[1]) / 2.

	return ((cx, cy), (a, b))

def three_point_ellipse(center, p_width, p_height):
	'''Ellipse from center and a point on each axis.

	Arguments:
		center (tuple): Center (x, y).
		p_width (tuple): A point on the horizontal axis (x, y).
		p_height (tuple): A point on the vertical axis (x, y).

	Returns:
		tuple: (center, (semi_a, semi_b)).
	'''
	a = math.hypot(p_width[0] - center[0], p_width[1] - center[1])
	b = math.hypot(p_height[0] - center[0], p_height[1] - center[1])

	return (center, (a, b))

def ellipse_points(center, semi_a, semi_b, angle_deg=0., num_points=64):
	'''Sample points along an ellipse.

	Arguments:
		center (tuple): Center (x, y).
		semi_a (float): Horizontal semi-axis.
		semi_b (float): Vertical semi-axis.
		angle_deg (float): Rotation angle of the ellipse in degrees.
		num_points (int): Number of sample points.

	Returns:
		list[tuple]: Points along the ellipse [(x, y), ...].
	'''
	cx, cy = center
	angle_rad = math.radians(angle_deg)
	cos_r = math.cos(angle_rad)
	sin_r = math.sin(angle_rad)

	result = []

	for i in range(num_points):
		t = 2. * math.pi * i / num_points
		ex = semi_a * math.cos(t)
		ey = semi_b * math.sin(t)

		# Rotate
		rx = cx + ex * cos_r - ey * sin_r
		ry = cy + ex * sin_r + ey * cos_r
		result.append((rx, ry))

	return result

# -- Regular polygons --------------------
def n_gon(center, radius, n, start_angle=0.):
	'''Regular n-sided polygon vertices.

	Arguments:
		center (tuple): Center (x, y).
		radius (float): Circumscribed radius (center to vertex).
		n (int): Number of sides (3 = triangle, 5 = pentagon, etc.).
		start_angle (float): Rotation of first vertex in degrees.

	Returns:
		list[tuple]: Vertices [(x, y), ...] in CCW order.
	'''
	cx, cy = center
	result = []

	for i in range(n):
		angle = math.radians(start_angle + 360. * i / n)
		result.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

	return result

def star_polygon(center, outer_r, inner_r, n, start_angle=0.):
	'''Star polygon with alternating outer and inner vertices.

	Arguments:
		center (tuple): Center (x, y).
		outer_r (float): Outer (tip) radius.
		inner_r (float): Inner (valley) radius.
		n (int): Number of points/tips.
		start_angle (float): Rotation of first tip in degrees.

	Returns:
		list[tuple]: Vertices [(x, y), ...] alternating outer/inner.
	'''
	cx, cy = center
	result = []

	for i in range(n * 2):
		angle = math.radians(start_angle + 360. * i / (n * 2))
		r = outer_r if i % 2 == 0 else inner_r
		result.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

	return result

# -- Rectangles / Parallelograms ---------
def rectangle(origin, width, height):
	'''Axis-aligned rectangle from origin, width, and height.

	Arguments:
		origin (tuple): Bottom-left corner (x, y).
		width (float): Width.
		height (float): Height.

	Returns:
		list[tuple]: Four corners [(BL), (BR), (TR), (TL)] in CCW order.
	'''
	ox, oy = origin
	return [(ox, oy), (ox + width, oy), (ox + width, oy + height), (ox, oy + height)]

def parallelogram(origin, width, height, slant_angle):
	'''Parallelogram (slanted rectangle).

	Arguments:
		origin (tuple): Bottom-left corner (x, y).
		width (float): Base width.
		height (float): Height.
		slant_angle (float): Slant angle in degrees (0 = rectangle).

	Returns:
		list[tuple]: Four corners [(BL), (BR), (TR), (TL)] in CCW order.
	'''
	ox, oy = origin
	slant = height * math.tan(math.radians(slant_angle))

	return [
		(ox, oy),
		(ox + width, oy),
		(ox + width + slant, oy + height),
		(ox + slant, oy + height)
	]

def trapezoid(base_center, top_width, bottom_width, height):
	'''Symmetric trapezoid centered on a vertical axis.

	Arguments:
		base_center (tuple): Center of the bottom edge (x, y).
		top_width (float): Width of the top edge.
		bottom_width (float): Width of the bottom edge.
		height (float): Height.

	Returns:
		list[tuple]: Four corners [(BL), (BR), (TR), (TL)] in CCW order.
	'''
	cx, cy = base_center
	bw2 = bottom_width / 2.
	tw2 = top_width / 2.

	return [
		(cx - bw2, cy),
		(cx + bw2, cy),
		(cx + tw2, cy + height),
		(cx - tw2, cy + height)
	]

# -- Arcs --------------------------------
def circular_arc_3point(p1, p2, p3, num_points=32):
	'''Circular arc through three points. Returns sampled points
	along the arc from p1 through p2 to p3.

	Arguments:
		p1, p2, p3 (tuple): Three points (x, y) on the arc.
		num_points (int): Number of sample points.

	Returns:
		tuple: (points, center, radius) where points is list[(x, y)],
			or (None, None, None) if points are collinear.
	'''
	result = three_point_circle(p1, p2, p3)

	if result[0] is None:
		return (None, None, None)

	center, radius = result
	cx, cy = center

	# Compute angles for each point
	a1 = math.atan2(p1[1] - cy, p1[0] - cx)
	a2 = math.atan2(p2[1] - cy, p2[0] - cx)
	a3 = math.atan2(p3[1] - cy, p3[0] - cx)

	# Ensure arc goes p1 -> p2 -> p3 in the correct direction
	# Normalize angles relative to a1
	def normalize(a, ref):
		while a - ref < -math.pi:
			a += 2. * math.pi
		while a - ref > math.pi:
			a -= 2. * math.pi
		return a

	a2 = normalize(a2, a1)
	a3 = normalize(a3, a1)

	# If a2 is not between a1 and a3, flip direction
	if a3 > a1:
		if not (a1 <= a2 <= a3):
			a3 -= 2. * math.pi
	else:
		if not (a3 <= a2 <= a1):
			a3 += 2. * math.pi

	points = []

	for i in range(num_points):
		t = float(i) / (num_points - 1)
		angle = a1 + t * (a3 - a1)
		points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

	return (points, center, radius)

def annulus_sector(center, inner_r, outer_r, start_angle, end_angle, num_points=16):
	'''Ring sector (annulus segment) defined by inner/outer radii and angle range.
	Returns vertices forming the closed outline (outer arc + inner arc reversed).

	Arguments:
		center (tuple): Center (x, y).
		inner_r (float): Inner radius.
		outer_r (float): Outer radius.
		start_angle (float): Start angle in degrees.
		end_angle (float): End angle in degrees.
		num_points (int): Points per arc.

	Returns:
		list[tuple]: Vertices forming the sector outline.
	'''
	cx, cy = center
	outer_pts = []
	inner_pts = []

	for i in range(num_points):
		t = float(i) / (num_points - 1)
		angle = math.radians(start_angle + t * (end_angle - start_angle))
		cos_a = math.cos(angle)
		sin_a = math.sin(angle)
		outer_pts.append((cx + outer_r * cos_a, cy + outer_r * sin_a))
		inner_pts.append((cx + inner_r * cos_a, cy + inner_r * sin_a))

	# Outer arc forward, inner arc reversed to form closed outline
	return outer_pts + list(reversed(inner_pts))

# -- Tangent constructions ---------------
def tangent_circle_to_two_lines(line1_p1, line1_p2, line2_p1, line2_p2, radius):
	'''Find circles of given radius tangent to two lines.
	This is the geometric core of corner filleting — the fillet circle.

	Arguments:
		line1_p1, line1_p2 (tuple): Two points on the first line.
		line2_p1, line2_p2 (tuple): Two points on the second line.
		radius (float): Desired tangent circle radius.

	Returns:
		list[tuple]: List of (center, tangent_point_1, tangent_point_2) for each
			valid tangent circle (up to 4 solutions). Each center is (x, y),
			each tangent point is (x, y).
			Returns empty list if lines are parallel or radius is invalid.
	'''
	if radius <= 0.:
		return []

	# Direction vectors and normals for each line
	d1x = line1_p2[0] - line1_p1[0]
	d1y = line1_p2[1] - line1_p1[1]
	len1 = math.hypot(d1x, d1y)

	d2x = line2_p2[0] - line2_p1[0]
	d2y = line2_p2[1] - line2_p1[1]
	len2 = math.hypot(d2x, d2y)

	if len1 < 1e-12 or len2 < 1e-12:
		return []

	# Unit normals (two orientations each)
	n1x, n1y = -d1y / len1, d1x / len1
	n2x, n2y = -d2y / len2, d2x / len2

	results = []

	# Try all 4 combinations of normal orientations
	for s1 in (1., -1.):
		for s2 in (1., -1.):
			# Offset lines by radius along their normals
			# Line 1 offset: point + s1 * radius * normal
			o1x = line1_p1[0] + s1 * radius * n1x
			o1y = line1_p1[1] + s1 * radius * n1y

			o2x = line2_p1[0] + s2 * radius * n2x
			o2y = line2_p1[1] + s2 * radius * n2y

			# Intersect offset lines
			# Line 1: (o1x, o1y) + t * (d1x, d1y)
			# Line 2: (o2x, o2y) + s * (d2x, d2y)
			denom = d1x * d2y - d1y * d2x

			if abs(denom) < 1e-12:
				continue  # Parallel

			dx = o2x - o1x
			dy = o2y - o1y
			t = (dx * d2y - dy * d2x) / denom

			cx = o1x + t * d1x
			cy = o1y + t * d1y

			# Tangent points: project center onto each original line
			# Line 1: closest point on line to center
			t1 = ((cx - line1_p1[0]) * d1x + (cy - line1_p1[1]) * d1y) / (len1 * len1)
			tp1 = (line1_p1[0] + t1 * d1x, line1_p1[1] + t1 * d1y)

			t2 = ((cx - line2_p1[0]) * d2x + (cy - line2_p1[1]) * d2y) / (len2 * len2)
			tp2 = (line2_p1[0] + t2 * d2x, line2_p1[1] + t2 * d2y)

			results.append(((cx, cy), tp1, tp2))

	return results

def tangent_lines_to_two_circles(c1, r1, c2, r2):
	'''Find external and internal common tangent lines between two circles.

	Arguments:
		c1 (tuple): Center of first circle (x, y).
		r1 (float): Radius of first circle.
		c2 (tuple): Center of second circle (x, y).
		r2 (float): Radius of second circle.

	Returns:
		dict: {'external': [(p1, p2), ...], 'internal': [(p1, p2), ...]}
			where each (p1, p2) is a pair of tangent points, one on each circle.
			Returns empty lists for degenerate cases.
	'''
	dx = c2[0] - c1[0]
	dy = c2[1] - c1[1]
	d = math.hypot(dx, dy)

	result = {'external': [], 'internal': []}

	if d < 1e-12:
		return result

	# Base angle between centers
	base_angle = math.atan2(dy, dx)

	# External tangents (same side)
	if d >= abs(r1 - r2):
		if d > abs(r1 - r2) + 1e-12:
			angle = math.acos((r1 - r2) / d)
		else:
			angle = 0.

		for sign in (1., -1.):
			a = base_angle + sign * angle + math.pi / 2.
			tp1 = (c1[0] + r1 * math.cos(a), c1[1] + r1 * math.sin(a))
			tp2 = (c2[0] + r2 * math.cos(a), c2[1] + r2 * math.sin(a))
			result['external'].append((tp1, tp2))

	# Internal tangents (cross side)
	if d > r1 + r2 + 1e-12:
		angle = math.acos((r1 + r2) / d)

		for sign in (1., -1.):
			a1 = base_angle + sign * angle + math.pi / 2.
			a2 = a1 + math.pi  # opposite side for second circle
			tp1 = (c1[0] + r1 * math.cos(a1), c1[1] + r1 * math.sin(a1))
			tp2 = (c2[0] + r2 * math.cos(a2), c2[1] + r2 * math.sin(a2))
			result['internal'].append((tp1, tp2))

	return result

def tangent_circle_to_line_and_point(line_p1, line_p2, point, radius):
	'''Find circles of given radius tangent to a line and passing through a point.

	Arguments:
		line_p1, line_p2 (tuple): Two points on the line.
		point (tuple): The point the circle must pass through (x, y).
		radius (float): Circle radius.

	Returns:
		list[tuple]: List of centers (x, y) for valid circles (up to 4).
			Returns empty list if no solution exists.
	'''
	if radius <= 0.:
		return []

	px, py = point
	dx = line_p2[0] - line_p1[0]
	dy = line_p2[1] - line_p1[1]
	line_len = math.hypot(dx, dy)

	if line_len < 1e-12:
		return []

	# Normal to line (unit)
	nx, ny = -dy / line_len, dx / line_len

	results = []

	# Center lies on a line parallel to the given line at distance = radius
	for sign in (1., -1.):
		# Offset line: any point on it is line_p1 + sign * radius * normal + t * direction
		ox = line_p1[0] + sign * radius * nx
		oy = line_p1[1] + sign * radius * ny

		# Center must be at distance = radius from the point
		# |center - point| = radius
		# center = (ox + t * dx/line_len, oy + t * dy/line_len) parameterized by arc length
		# Substituting into distance equation:
		# (ox + t*ux - px)^2 + (oy + t*uy - py)^2 = radius^2
		ux, uy = dx / line_len, dy / line_len
		ax = ox - px
		ay = oy - py

		# Quadratic: t^2 + 2(ax*ux + ay*uy)*t + (ax^2 + ay^2 - r^2) = 0
		A = 1.
		B = 2. * (ax * ux + ay * uy)
		C = ax * ax + ay * ay - radius * radius
		disc = B * B - 4. * A * C

		if disc < 0.:
			continue

		sqrt_disc = math.sqrt(disc)

		for t in ((-B + sqrt_disc) / (2. * A), (-B - sqrt_disc) / (2. * A)):
			cx = ox + t * ux
			cy = oy + t * uy
			results.append((cx, cy))

	return results

def parallel_line(p1, p2, distance, side=1):
	'''Compute a parallel (offset) line at a given distance.

	Arguments:
		p1, p2 (tuple): Two points on the original line.
		distance (float): Offset distance.
		side (int): 1 = left side (CCW normal), -1 = right side.

	Returns:
		tuple: Two points ((x1, y1), (x2, y2)) on the parallel line.
	'''
	dx = p2[0] - p1[0]
	dy = p2[1] - p1[1]
	length = math.hypot(dx, dy)

	if length < 1e-12:
		return (p1, p2)

	# Normal direction (left = CCW)
	nx = -dy / length * side
	ny = dx / length * side

	offset = distance
	return (
		(p1[0] + nx * offset, p1[1] + ny * offset),
		(p2[0] + nx * offset, p2[1] + ny * offset)
	)

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

