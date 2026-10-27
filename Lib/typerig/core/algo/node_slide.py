# MODULE: TypeRig / Core / Algo / Node Slide
# -----------------------------------------------------------
# Slide an on-curve node along one of its segments, keeping the
# segment's shape: the node moves to B(t) of the original
# segment and the segment is trimmed (t inside) or extended
# (t outside) by de Casteljau. Works on core Line and
# CubicBezier, whose solve_point / solve_slice are valid for
# any t, so the slide interpolates and extrapolates.
#
#   project_time(segment, point, lo, hi)     t of the nearest B(t)
#   slide_end(segment, t)                     node = segment end (incoming)
#   slide_start(segment, t)                   node = segment start (outgoing)
#   turn_handle(node, handle, direction)      handle on a new tangent
#
# The host maps a dragged node to its incoming or outgoing
# segment and writes the result back.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

import math

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier

__version__ = '0.1.0'

# - Config -------------------------------
SAMPLES = 64			# coarse samples over [lo, hi] for a cubic
REFINE  = 24			# golden-section steps inside the best sample bracket
GOLDEN  = (math.sqrt(5.) - 1.) / 2.


# - Helpers ------------------------------
def _dist2(a, b):
	return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def project_time(segment, point, lo, hi, samples=SAMPLES, refine=REFINE):
	'''t in [lo, hi] where segment.solve_point(t) is nearest to point.
	lo / hi may lie outside [0, 1]: the segment is extended.'''
	point = Point(point)
	if isinstance(segment, Line):
		d = segment.p1 - segment.p0
		len2 = d.x * d.x + d.y * d.y
		if len2 == 0.:
			return min(max(0., lo), hi)
		t = ((point.x - segment.p0.x) * d.x + (point.y - segment.p0.y) * d.y) / len2
		return min(max(t, lo), hi)

	f = lambda t: _dist2(segment.solve_point(t), point)
	step = (hi - lo) / float(samples)
	best_i = min(range(samples + 1), key=lambda i: f(lo + i * step))
	a = lo + max(best_i - 1, 0) * step
	b = lo + min(best_i + 1, samples) * step

	m1, m2 = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
	f1, f2 = f(m1), f(m2)
	for _ in range(refine):
		if f1 < f2:
			b, m2, f2 = m2, m1, f1
			m1 = b - GOLDEN * (b - a)
			f1 = f(m1)
		else:
			a, m1, f1 = m1, m2, f2
			m2 = a + GOLDEN * (b - a)
			f2 = f(m2)
	t = (a + b) * .5
	return t if f(t) <= f(lo + best_i * step) else lo + best_i * step


# - Slide --------------------------------
def slide_end(segment, t):
	'''Segment trimmed / extended so that it ends at B(t): the incoming
	segment of a node slid to t. Same type as segment.'''
	if isinstance(segment, Line):
		return Line(Point(segment.p0), segment.solve_point(t))
	return segment.solve_slice(t)[0]


def slide_start(segment, t):
	'''Segment trimmed / extended so that it starts at B(t): the outgoing
	segment of a node slid to t. Same type as segment.'''
	if isinstance(segment, Line):
		return Line(segment.solve_point(t), Point(segment.p1))
	return segment.solve_slice(t)[1]


def end_direction(segment):
	'''Unit tangent at the segment end, pointing along the segment.'''
	if isinstance(segment, Line):
		return (segment.p1 - segment.p0).unit
	d = segment.p3 - segment.p2
	if d.magnitude == 0.:
		d = segment.p3 - segment.p1
	if d.magnitude == 0.:
		d = segment.p3 - segment.p0
	return d.unit


def start_direction(segment):
	'''Unit tangent at the segment start, pointing along the segment.'''
	if isinstance(segment, Line):
		return (segment.p1 - segment.p0).unit
	d = segment.p1 - segment.p0
	if d.magnitude == 0.:
		d = segment.p2 - segment.p0
	if d.magnitude == 0.:
		d = segment.p3 - segment.p0
	return d.unit


def turn_handle(node, handle, direction):
	'''Handle point at the same distance from node, along unit direction
	(keeps a smooth node smooth after its other side turned).'''
	node, handle = Point(node), Point(handle)
	return node + direction * (handle - node).magnitude


# - Test -----------------------------------
if __name__ == '__main__':
	def close(a, b, tol=1e-6):
		return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol

	# Line: projection, interpolate and extrapolate
	ln = Line((0, 0), (100, 0))
	assert abs(project_time(ln, (30, 50), -1., 2.) - .3) < 1e-9
	assert abs(project_time(ln, (150, 5), -1., 2.) - 1.5) < 1e-9
	assert project_time(ln, (500, 0), -1., 2.) == 2.
	assert close(slide_end(ln, 1.5).p1.tuple, (150, 0))
	assert close(slide_start(ln, .25).p0.tuple, (25, 0)) and close(slide_start(ln, .25).p1.tuple, (100, 0))

	# Cubic: the slid segment keeps the curve (sub-curve of the original)
	cb = CubicBezier((0, 0), (0, 55), (45, 100), (100, 100))
	for t in (.3, .8, 1.2):
		q = cb.solve_point(t)
		assert abs(project_time(cb, q.tuple, -1., 2.) - t) < 1e-4, t
		end = slide_end(cb, t)
		assert close(end.p3.tuple, q.tuple)
		for s in (.25, .5, .75):	# a point of the new segment lies on the original
			assert close(end.solve_point(s).tuple, cb.solve_point(s * t).tuple, 1e-6)
		start = slide_start(cb, t)
		assert close(start.p0.tuple, q.tuple) and close(start.p3.tuple, (100, 100))
		for s in (.25, .5, .75):
			assert close(start.solve_point(s).tuple, cb.solve_point(t + s * (1 - t)).tuple, 1e-6)

	# Smooth handle follows the new tangent, same length
	h = turn_handle((10, 0), (10, 30), Point(1, 0))
	assert close(h.tuple, (40, 0))
	print('node_slide: all tests passed.')
