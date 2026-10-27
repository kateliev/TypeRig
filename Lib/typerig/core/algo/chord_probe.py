# MODULE: TypeRig / Core / Algo / Chord Probe
# -----------------------------------------------------------
# Stem width at a point: the chord of the outline through a
# point inside it, along the normal of the nearest outline.
#
# The nearest outline point N to the probe point P is where the
# outline is perpendicular to P-N, so the chord through P in
# that direction crosses the stem square to its nearer side:
# the stem width on straight, diagonal and curved stems alike.
# The direction is found by casting rays: the one with the
# closest hit (either side), scanned and then refined.
#
#   chord_at(cast, x, y, angle, reach)        one chord
#   normal_chord(cast, x, y, reach, ...)      chord along the normal
#
# The host supplies the ray cast: cast(p0, p1) returns the
# outline hits on segment p0-p1 as (x, y) pairs, in any order;
# p0 and p1 themselves may be in the list (Glyphs adds them).
# Pure math — no host objects.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

import math

__version__ = '0.2.0'

# - Config -------------------------------
END_EPS = 1e-6			# hits this close (relative) to the ray ends are the ends, not outline
GOLDEN = (math.sqrt(5.) - 1.) / 2.
INF = float('inf')


# - Objects ------------------------------
class Chord(object):
	'''Outline chord through a probe point p.
	a, b   : end points (x, y) on the outline, a behind p, b in front
	angle  : direction a -> b in degrees, [0, 180)
	length : distance a - b
	back   : distance p - a
	front  : distance p - b
	'''
	__slots__ = ('a', 'b', 'angle', 'length', 'back', 'front')

	def __init__(self, a, b, angle, back, front):
		self.a, self.b = a, b
		self.angle  = angle % 180.
		self.back, self.front = back, front
		self.length = back + front

	@property
	def mid(self):
		return ((self.a[0] + self.b[0]) * .5, (self.a[1] + self.b[1]) * .5)

	def __repr__(self):
		return '<Chord: %.2f @ %.2f deg>' % (self.length, self.angle)


# - Probe --------------------------------
def chord_at(cast, x, y, angle, reach):
	'''Chord through (x, y) at `angle` degrees; reach = half ray length,
	longer than any chord of the outline. None when the ray leaves the
	outline on one side without a hit.'''
	rad = math.radians(angle)
	dx, dy = math.cos(rad), math.sin(rad)
	p0 = (x - dx * reach, y - dy * reach)
	p1 = (x + dx * reach, y + dy * reach)
	limit = reach * (1. - END_EPS)

	back = front = None
	for hx, hy in cast(p0, p1):
		t = (hx - x) * dx + (hy - y) * dy		# signed distance along the ray
		if abs(t) >= limit:
			continue
		if t < 0.:
			if back is None or t > back:
				back = t
		elif t > 0.:
			if front is None or t < front:
				front = t

	if back is None or front is None:
		return None
	return Chord((x + dx * back, y + dy * back), (x + dx * front, y + dy * front), angle, -back, front)


def _golden(f, lo, hi, steps):
	'''Golden-section search for the minimum of f(angle) -> (value, chord)
	on [lo, hi]. Returns the best (value, chord) evaluated.'''
	m1 = hi - GOLDEN * (hi - lo)
	m2 = lo + GOLDEN * (hi - lo)
	r1, r2 = f(m1), f(m2)
	best = min(r1, r2, key=lambda r: r[0])
	for _ in range(steps):
		if r1[0] < r2[0]:
			hi, m2, r2 = m2, m1, r1
			m1 = hi - GOLDEN * (hi - lo)
			r1 = f(m1)
		else:
			lo, m1, r1 = m1, m2, r2
			m2 = lo + GOLDEN * (hi - lo)
			r2 = f(m2)
		best = min(best, r1, r2, key=lambda r: r[0])
	return best


def normal_chord(cast, x, y, reach, steps=36, refine=10):
	'''Chord through (x, y) along the normal of the nearest outline.
	Scans `steps` angles over 180 degrees (each chord gives both sides, so
	2 * steps directions), then golden-section refines the closest side
	`refine` times within one scan step. None when (x, y) is not enclosed.'''
	step = 180. / steps
	best = None		# (distance, angle, side: 0 back / 1 front, chord)
	for i in range(steps):
		angle = i * step
		c = chord_at(cast, x, y, angle, reach)
		if c is None:
			continue
		for side, d in ((0, c.back), (1, c.front)):
			if best is None or d < best[0]:
				best = (d, angle, side, c)
	if best is None:
		return None

	dist, angle, side, chord = best

	def nearest(a):
		c = chord_at(cast, x, y, a, reach)
		if c is None:
			return (INF, None)
		return ((c.front if side else c.back), c)

	d, c = _golden(nearest, angle - step, angle + step, refine)
	return c if c is not None and d < dist else chord


# - Test -----------------------------------
if __name__ == '__main__':
	def polygon_cast(polys):
		'''cast() over closed polygons: segment-segment hits.'''
		def cast(p0, p1):
			hits = []
			(ax, ay), (bx, by) = p0, p1
			for poly in polys:
				for i in range(len(poly)):
					(cx, cy), (dx, dy) = poly[i], poly[(i + 1) % len(poly)]
					den = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
					if abs(den) < 1e-12:
						continue
					t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / den
					u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / den
					if 0. <= t <= 1. and 0. <= u <= 1.:
						hits.append((ax + t * (bx - ax), ay + t * (by - ay)))
			return [p0] + hits + [p1]
		return cast

	def rotated(poly, deg):
		r = math.radians(deg)
		c, s = math.cos(r), math.sin(r)
		return [(px * c - py * s, px * s + py * c) for px, py in poly]

	def circle(r, n=1440):
		return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]

	def angle_off(a, b):
		d = abs(a - b) % 180.
		return min(d, 180. - d)

	# Vertical stem 80 x 700, probe off-centre and near an end
	stem = polygon_cast([[(100, 0), (180, 0), (180, 700), (100, 700)]])
	for px, py in ((120, 300), (170, 350), (140, 150)):
		m = normal_chord(stem, px, py, 2000)
		assert abs(m.length - 80) < 1e-3 and angle_off(m.angle, 0.) < .05, (px, py, m)

	# Diagonal stem 90 wide, rotated 33 degrees: normal at 33
	diag = polygon_cast([rotated([(0, -1000), (90, -1000), (90, 1000), (0, 1000)], 33.)])
	for px in (10, 45, 80):
		p = rotated([(px, 0)], 33.)[0]
		m = normal_chord(diag, p[0], p[1], 5000)
		assert abs(m.length - 90) < .01 and angle_off(m.angle, 33.) < .05, (px, m)

	# Curved stem: ring 300 / 220, probe off the middle line -> radial, 80
	ring = polygon_cast([circle(300), circle(220)])
	for r, deg in ((240, 20), (285, 135), (260, 250)):
		px, py = r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))
		m = normal_chord(ring, px, py, 2000)
		assert abs(m.length - 80) < .1 and angle_off(m.angle, deg) < .2, (r, deg, m)

	# Probe outside the outline: no chord
	assert normal_chord(stem, 50, 300, 2000) is None
	print('chord_probe: all tests passed.')
