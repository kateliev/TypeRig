# MODULE: TypeRig / Core / Analytic geometry (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
import math

# - Init --------------------------------
__version__ = '0.28.0'

# - Functions ---------------------------
# -- Point ------------------------------
def get_angle(x, y, degrees=True):
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
	triangle_list = list(triangle) + [triangle[0]]
	turns = [ccw(point, triangle_list[i], triangle_list[i+1]) for i in range(3)]
	# Point is inside when all turns agree — works for both CW and CCW triangles
	return all(turns) or not any(turns)

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

def point_rotate(center, point, angle, inDegrees=True):
	'''Rotate point around center point with angle (in degrees)
	Args: 
		center, point -> tuple(x, y); 
		angle -> float;
	
	Returns:
		new point coordinates -> tuple(x,y)
	'''
	px, py = point
	cx, cy = center
	rangle = math.radians(angle) if inDegrees else angle

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
	
# - Corners -----------------------------------------
def squircle_corner(vertex, prev_unit, next_unit, reach, smoothing):
	'''Figma-style squircle (superellipse) corner geometry.

	A central circular arc spanning turn*(1 - smoothing), flanked by two symmetric
	'ease' cubic Beziers that blend the arc into the straight edges: three cubic
	segments (ease-in, arc, ease-out), 4 on-curve and 6 off-curve points.

	Args:
		vertex -> tuple(x, y): the sharp corner vertex;
		prev_unit, next_unit -> tuple(x, y): unit vectors from the vertex along the
			incoming (previous) and outgoing (next) edges;
		reach -> float: distance from the vertex to where each straight edge ends;
		smoothing -> float: 0.0 (plain circular fillet) - 1.0; 0.6 = iOS.

	Returns:
		list(tuple(x, y)) -> [A, c, c, arc_in, c, c, arc_out, c, c, B], A on the
		incoming edge, B on the outgoing edge; or None for a degenerate corner.
	'''
	vx, vy = float(vertex[0]), float(vertex[1])
	ix, iy = float(prev_unit[0]), float(prev_unit[1])
	ox, oy = float(next_unit[0]), float(next_unit[1])

	full_angle = math.acos(max(-1., min(1., ix * ox + iy * oy)))	# interior angle at the vertex
	half_angle = full_angle / 2.
	turn_angle = math.pi - full_angle								# exterior turn of the outline

	if half_angle < 1e-6 or turn_angle < 1e-6 or reach <= 0.:
		return None

	s = max(0., min(1., float(smoothing)))

	# - Circular-arc radius from reach and smoothing: reach = (1 + s) * t0 ; t0 = r / tan(half_angle)
	radius = reach / (1. + s) * math.tan(half_angle)

	# - Arc centre on the bisector, and the direction from it back toward the vertex
	bx, by = ix + ox, iy + oy
	blen = math.hypot(bx, by)
	if blen < 1e-9 or radius <= 0.:
		return None

	offset = radius / math.sin(half_angle)
	cx, cy = vx + bx / blen * offset, vy + by / blen * offset
	dx, dy = (vx - cx) / offset, (vy - cy) / offset

	half_arc = turn_angle * (1. - s) / 2.

	def _rotate(x, y, a):
		ca, sa = math.cos(a), math.sin(a)
		return (x * ca - y * sa, x * sa + y * ca)

	def _intersect(p, d, q, e):
		# - Lines (p + t*d) and (q + u*e); None if parallel
		denom = d[0] * e[1] - d[1] * e[0]
		if abs(denom) < 1e-9: return None
		t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / denom
		return (p[0] + t * d[0], p[1] + t * d[1])

	dir_a, dir_b = _rotate(dx, dy, half_arc), _rotate(dx, dy, -half_arc)

	# - dir_a must point to the arc end on the incoming (prev) edge side
	if (dir_a[0] * ix + dir_a[1] * iy) < (dir_b[0] * ix + dir_b[1] * iy):
		dir_a, dir_b = dir_b, dir_a

	arc_in = (cx + dir_a[0] * radius, cy + dir_a[1] * radius)
	arc_out = (cx + dir_b[0] * radius, cy + dir_b[1] * radius)
	point_a = (vx + ix * reach, vy + iy * reach)
	point_b = (vx + ox * reach, vy + oy * reach)

	# - Arc tangent directions (perpendicular to the radii)
	tan_a, tan_b = (-dir_a[1], dir_a[0]), (-dir_b[1], dir_b[0])

	# - Ease control points: arc-tangent line meets the straight edge line
	p2_in = _intersect(point_a, (ix, iy), arc_in, tan_a) or arc_in
	p2_out = _intersect(point_b, (ox, oy), arc_out, tan_b) or arc_out
	p1_in = (point_a[0] + (p2_in[0] - point_a[0]) * 2. / 3., point_a[1] + (p2_in[1] - point_a[1]) * 2. / 3.)
	p1_out = (point_b[0] + (p2_out[0] - point_b[0]) * 2. / 3., point_b[1] + (p2_out[1] - point_b[1]) * 2. / 3.)

	# - Arc handles (single cubic approximation of the circular arc)
	k = (4. / 3.) * math.tan(half_arc / 2.) * radius if half_arc > 1e-9 else 0.
	fwd_a = tan_a if (tan_a[0] * (arc_out[0] - arc_in[0]) + tan_a[1] * (arc_out[1] - arc_in[1])) > 0 else (-tan_a[0], -tan_a[1])
	fwd_b = tan_b if (tan_b[0] * (arc_in[0] - arc_out[0]) + tan_b[1] * (arc_in[1] - arc_out[1])) > 0 else (-tan_b[0], -tan_b[1])
	arc_h0 = (arc_in[0] + fwd_a[0] * k, arc_in[1] + fwd_a[1] * k)
	arc_h1 = (arc_out[0] + fwd_b[0] * k, arc_out[1] + fwd_b[1] * k)

	return [point_a, p1_in, p2_in, arc_in, arc_h0, arc_h1, arc_out, p2_out, p1_out, point_b]

# - Angle/Connection --------------------------------
def checkSmooth(firstAngle, lastAngle, error=4):
	'''Check if connection is smooth within error margin.
	Adapted from RoboFont pens. (NOTE: To be deleted)
	'''
	if firstAngle is None or lastAngle is None: return True
	if math.isnan(firstAngle) or math.isnan(lastAngle): return False
	
	firstAngle = math.degrees(firstAngle)
	lastAngle = math.degrees(lastAngle)

	if int(firstAngle) + error >= int(lastAngle) >= int(firstAngle) - error: return True
	
	return False

def checkInnerOuter(firstAngle, lastAngle):
	'''Check if connection is inner or outer.
	Adapted from RoboFont pens. (NOTE: To be deleted)
	'''
	if firstAngle is None or lastAngle is None:	return True
	if math.isnan(firstAngle) or math.isnan(lastAngle): return False
	
	dirAngle = math.degrees(firstAngle) - math.degrees(lastAngle)

	if dirAngle > 180:		dirAngle = 180 - dirAngle
	elif dirAngle < -180:	dirAngle = -180 - dirAngle

	if dirAngle > 0:	return True
	if dirAngle <= 0:	return False

# - Ploygons ----------------------------------------
def poly_area_signed(vertices):
	'''Signed polygon area via the shoelace formula.
	Positive = CCW (y-up), negative = CW.
	'''
	corners = len(vertices)
	area = 0.0

	for i in range(corners):
		j = (i + 1) % corners
		area += vertices[i][0]*vertices[j][1] - vertices[j][0]*vertices[i][1]

	return area*0.5

def poly_area(vertices):
	'''Unsigned polygon area via the shoelace formula.
	The absolute value is taken over the SUM — per-term abs breaks for
	polygons whose cross terms change sign (any polygon away from the origin).
	'''
	return abs(poly_area_signed(vertices))

if __name__ == '__main__':
	A = (0,0); B = (0,200); C = (200,200); D = (200,0)
	print(get_angle(10, 35, degrees=True))
	print(ccw(A, B, C))
	print(intersect(A,B,C,D))
	print(point_in_triangle(D, (A, B, C)))
	print(point_in_polygon(D, (A, B, C, D)))
	print(point_rotate(A, A, 30, inDegrees=True))
	print(line_slope(A, C))
	print(line_angle(A, B, degrees=True))
	print(line_y_intercept(A, C))
	print(line_solve_y(A, B, 0))
	print(line_solve_x(A, B, 0))
	print(line_intersect(A, C, B, D))
	print(checkSmooth(90, 91, error=4))
	print(checkInnerOuter(90, 92))
	print(poly_area((A, B, C, D)))
