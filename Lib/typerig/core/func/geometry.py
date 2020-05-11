# MODULE: TypeRig / Core / Analytic geometry (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import
import math

# - Init --------------------------------
__version__ = '0.26.1'

# - Functions ---------------------------
# -- Point ------------------------------
def get_angle(x,y, degrees=True):
	'''Return angle for given X,Y displacement from origin'''
	angle = math.atan2(float(x), float(y))
	return math.degrees(angle) if degrees else angle
		
def ccw(A, B, C):
	'''Tests whether the turn formed by points A, B, and C is Counter clock wise (CCW)'''
	return (B[0] - A[0]) * (C[1] - A[1]) > (B[1] - A[1]) * (C[0] - A[0])

def intersect(A,B,C,D):
	'''Tests whether A,B and C,D intersect'''
	return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

def point_in_triangle(point, triangle):
	'''Point in triangle test
	Args: 
		point -> tuple(x, y); 
		triangle -> tuple(tuple(x0, y0), tuple(x1, y1), tuple(x2, y2))

	Returns:
		Bool
	'''
	trinagle_list = list(triangle) + triangle[0]
	return all([ccw(p, trinagle_list[i], trinagle_list[i+1]) for i in range(3)])

def point_in_polygon(point, polygon):
	'''Point in Polygon test
	Args: 
		point -> tuple(x, y); 
		polygon -> tuple(tuple(x0, y1)...tuple(xn, yn));
	
	Returns:
		Bool
	'''
	x, y = point
	p1x, p1y = polygon[0]
	polygon_len = len(polygon)
	point_inside = False

	for i in range(polygon_len + 1):
		p2x,p2y = polygon[i % polygon_len]
		
		if all([y > min(p1y, p2y), y <= max(p1y, p2y), x <= max(p1x, p2x)]):
			if p1y != p2y:
				x_intersection = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x

			if p1x == p2x or x <= x_intersection:
				point_inside = not point_inside

		p1x, p1y = p2x, p2y

	return point_inside

def point_rotate(center, point, angle):
	'''Rotate point around center point with angle (in degrees)
	Args: 
		center, point -> tuple(x, y); 
		angle -> float;
	
	Returns:
		new point coordinates -> tuple(x,y)
	'''
	px, py = point
	cx, xy = center
	rangle = math.radians(angle)

	nx = math.cos(rangle) * (px - cx) - math.sin(rangle) * (py - cy) + cx
	ny = math.sin(rangle) * (px - cx) + math.cos(rangle) * (py - cy) + cy

	return nx, ny

# -- Line ------------------------------
def line_slope(p0, p1):
	'''Find slope between two points forming a line
	Args: 
		p0, p1 -> tuple(x, y)
			
	Returns:
		float or NAN
	'''
	p0x, p0y = p0
	p1x, p1y = p1
	
	diff_x = p1x - p0x
	diff_y = p1y - p0y

	try:
		return diff_y / float(diff_x)
	except ZeroDivisionError:
		return float('nan')

def line_angle(p0, p1, degrees=True):
	'''Find angle between two points forming a line
	Args: 
		p0, p1 -> tuple(x, y);
		degrees -> bool
			
	Returns:
		radians or degrees
	'''
	p0x, p0y = p0
	p1x, p1y = p1
	
	diff_x = p1x - p0x
	diff_y = p1y - p0y

	rangle = math.atan2(diff_y, diff_x)
	return math.degrees(rangle) if degrees else rangle

def line_y_intercept(p0, p1):
	'''Find Y intercept of line equation for line formed by two points
	Args: 
		p0, p1 -> tuple(x, y)

	Returns:
		intercept node -> tuple(x,y)
	'''
	from typerig.core.func.geometry import line_slope

	p0x, p0y = p0
	slope = line_slope(p0, p1)

	return p0y - slope * p0x if not math.isnan(slope) and slope != 0 else p0y

def line_solve_y(p0, p1, x):
	'''Solve line equation for Y coordinate by given X.'''
	from typerig.core.func.geometry import line_slope, line_y_intercept
	
	p0x, p0y = p0
	slope = line_slope(p0, p1)
	y_intercept = line_y_intercept(p0, p1)

	return slope * x + y_intercept if not math.isnan(slope) and slope != 0 else p0y
					
def line_solve_x(p0, p1, y):
	'''Solve line equation for X coordinate by given Y.'''
	from typerig.core.func.geometry import line_slope, line_y_intercept

	p0x, p0y = p0
	slope = line_slope(p0, p1)
	y_intercept = line_y_intercept(p0, p1)

	return (float(y) - y_intercept) / float(slope) if not math.isnan(slope) and slope != 0 else p0x

def line_intersect(a0, a1, b0, b1):
	'''Find intersection between two lines
	Args: 
		a0, a1, b0, b1 -> tuple(x, y); 
	Returns:
		intersect node -> tuple(x,y)
	'''
	import sys
	from typerig.core.func.geometry import line_slope

	a0x, a0y = a0
	a1x, a1y = a1
	b0x, b0y = b0
	b1x, b1y = b1

	slope_a = line_slope(a0, a1)
	slope_b = line_slope(b0, b1)

	if abs(a1x - a0x) < sys.float_info.epsilon:
	  x = a0x
	  y = slope_b * (x - b0x) + b0y
	  return x, y

	if abs(b1x - b0x) < sys.float_info.epsilon:
	  x = b0x
	  y = slope_a * (x - a0x) + a0y
	  return x, y

	if abs(slope_a - slope_b) < sys.float_info.epsilon: 
		return
	
	x = (slope_a * a0x - a0y - slope_b * b0x + b0y) / (slope_a - slope_b)
	y = slope_a * (x - a0x) + a0y

	return x, y
	
# - Angle/Connection --------------------------------
def checkSmooth(firstAngle, lastAngle, error=4):
	'''Check if connection is smooth within error margin.
	Adapted from RoboFont pens. (NOTE: To be deleted)
	'''
	if firstAngle is None or lastAngle is None: return True
	
	firstAngle = math.degrees(firstAngle)
	lastAngle = math.degrees(lastAngle)

	if int(firstAngle) + error >= int(lastAngle) >= int(firstAngle) - error: return True
	
	return False

def checkInnerOuter(firstAngle, lastAngle):
	'''Check if connection is inner or outer.
	Adapted from RoboFont pens. (NOTE: To be deleted)
	'''
	if firstAngle is None or lastAngle is None:	return True
	
	dirAngle = math.degrees(firstAngle) - math.degrees(lastAngle)

	if dirAngle > 180:		dirAngle = 180 - dirAngle
	elif dirAngle < -180:	dirAngle = -180 - dirAngle

	if dirAngle > 0:	return True
	if dirAngle <= 0:	return False
