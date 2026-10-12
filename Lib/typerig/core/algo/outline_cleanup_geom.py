# MODULE: TypeRig / Core / Algo / Outline Cleanup — Geometry kernel
# -----------------------------------------------------------
# Tuple-based segment math for the outline cleanup pipeline.
# A segment is a tuple of 2 (line), 3 (quadratic) or 4 (cubic)
# (x, y) points. Hot loops stay on plain tuples for speed; the
# cubic split/elevate primitives come from algo/intersect.py and
# the Gauss-Legendre table from objects/cubicbezier.py.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.algo.intersect import split_cubic, line_to_cubic

__version__ = '1.0.0'

Point = tuple[float, float]

# - Config -------------------------------
LUT_STEPS = 64			# coarse nearest-point search resolution
NEWTON_STEPS = 3		# refinement steps after the coarse search
SRC_SAMPLES = 16		# samples per source segment in the error metric
CAND_SAMPLES = 32		# samples per candidate segment in the error metric
RESOLUTION = 1e-3		# font units; distances below this read as zero

# Gauss-Legendre on [0, 1], remapped from the [-1, 1] table on CubicBezier.
_GL = tuple(((x + 1.) * .5, w * .5) for x, w in zip(CubicBezier._GAUSS_LEGENDRE_T, CubicBezier._GAUSS_LEGENDRE_C))


# - Data ---------------------------------
@dataclass(slots=True)
class Seg:
	p: tuple[Point, ...]			# 2 points = line, 3 = quadratic, 4 = cubic
	src: tuple[int, int] = (0, 0)	# reference segment range [src0, src1) covered, for traceback

	@property
	def is_line(self) -> bool:
		return len(self.p) == 2

	@property
	def is_quad(self) -> bool:
		return len(self.p) == 3

	@property
	def is_cubic(self) -> bool:
		return len(self.p) == 4

	@property
	def start(self) -> Point:
		return self.p[0]

	@property
	def end(self) -> Point:
		return self.p[-1]


# - Vectors ------------------------------
def dist(a: Point, b: Point) -> float:
	return math.hypot(b[0] - a[0], b[1] - a[1])


def unit(v: Point) -> Point | None:
	length = math.hypot(v[0], v[1])
	if length < 1e-12:
		return None
	return (v[0] / length, v[1] / length)


def angle_between(a: Point, b: Point) -> float:
	'''Unsigned angle in degrees between two direction vectors.'''
	cross = a[0] * b[1] - a[1] * b[0]
	dot = a[0] * b[0] + a[1] * b[1]
	return abs(math.degrees(math.atan2(cross, dot)))


def hv_deviation(v: Point) -> float:
	'''Angle in degrees from v to the nearest of the horizontal/vertical axes.'''
	a = abs(math.degrees(math.atan2(v[1], v[0]))) % 90.
	return min(a, 90. - a)


def line_distance(q: Point, a: Point, b: Point) -> float:
	'''Perpendicular distance from q to the infinite line through a, b.'''
	dx, dy = b[0] - a[0], b[1] - a[1]
	length = math.hypot(dx, dy)
	if length < 1e-12:
		return dist(q, a)
	return abs((q[0] - a[0]) * dy - (q[1] - a[1]) * dx) / length


def line_param(q: Point, a: Point, b: Point) -> float:
	'''Projection parameter of q onto segment a-b (0 at a, 1 at b).'''
	dx, dy = b[0] - a[0], b[1] - a[1]
	length2 = dx * dx + dy * dy
	if length2 < 1e-24:
		return 0.
	return ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / length2


# - Segment evaluation -------------------
def elevate_quad(p0: Point, q: Point, p2: Point) -> tuple[Point, Point, Point, Point]:
	'''Exact degree elevation: C1 = P0 + 2/3 (Q - P0), C2 = P2 + 2/3 (Q - P2).'''
	return (p0,
			(p0[0] + 2. / 3. * (q[0] - p0[0]), p0[1] + 2. / 3. * (q[1] - p0[1])),
			(p2[0] + 2. / 3. * (q[0] - p2[0]), p2[1] + 2. / 3. * (q[1] - p2[1])),
			p2)


def as_cubic(p: tuple[Point, ...]) -> tuple[Point, Point, Point, Point]:
	if len(p) == 4:
		return p
	if len(p) == 3:
		return elevate_quad(*p)
	return line_to_cubic(p[0], p[1])


def point_at(p: tuple[Point, ...], t: float) -> Point:
	n = len(p)
	mt = 1. - t

	if n == 4:
		a = mt * mt * mt; b = 3. * mt * mt * t; c = 3. * mt * t * t; d = t * t * t
		return (a * p[0][0] + b * p[1][0] + c * p[2][0] + d * p[3][0],
				a * p[0][1] + b * p[1][1] + c * p[2][1] + d * p[3][1])
	if n == 3:
		a = mt * mt; b = 2. * mt * t; c = t * t
		return (a * p[0][0] + b * p[1][0] + c * p[2][0],
				a * p[0][1] + b * p[1][1] + c * p[2][1])

	return (mt * p[0][0] + t * p[1][0], mt * p[0][1] + t * p[1][1])


def derivative_at(p: tuple[Point, ...], t: float) -> Point:
	n = len(p)
	mt = 1. - t

	if n == 4:
		a = 3. * mt * mt; b = 6. * mt * t; c = 3. * t * t
		return (a * (p[1][0] - p[0][0]) + b * (p[2][0] - p[1][0]) + c * (p[3][0] - p[2][0]),
				a * (p[1][1] - p[0][1]) + b * (p[2][1] - p[1][1]) + c * (p[3][1] - p[2][1]))
	if n == 3:
		return (2. * mt * (p[1][0] - p[0][0]) + 2. * t * (p[2][0] - p[1][0]),
				2. * mt * (p[1][1] - p[0][1]) + 2. * t * (p[2][1] - p[1][1]))

	return (p[1][0] - p[0][0], p[1][1] - p[0][1])


def second_derivative_at(p: tuple[Point, ...], t: float) -> Point:
	n = len(p)

	if n == 4:
		a = 6. * (1. - t); b = 6. * t
		return (a * (p[2][0] - 2. * p[1][0] + p[0][0]) + b * (p[3][0] - 2. * p[2][0] + p[1][0]),
				a * (p[2][1] - 2. * p[1][1] + p[0][1]) + b * (p[3][1] - 2. * p[2][1] + p[1][1]))
	if n == 3:
		return (2. * (p[2][0] - 2. * p[1][0] + p[0][0]), 2. * (p[2][1] - 2. * p[1][1] + p[0][1]))

	return (0., 0.)


def split(p: tuple[Point, ...], t: float) -> tuple[tuple[Point, ...], tuple[Point, ...]]:
	'''De Casteljau split of a line, quadratic or cubic at t.'''
	if len(p) == 4:
		return split_cubic(p, t)

	m = point_at(p, t)

	if len(p) == 3:
		a = (p[0][0] + (p[1][0] - p[0][0]) * t, p[0][1] + (p[1][1] - p[0][1]) * t)
		b = (p[1][0] + (p[2][0] - p[1][0]) * t, p[1][1] + (p[2][1] - p[1][1]) * t)
		return (p[0], a, m), (m, b, p[2])

	return (p[0], m), (m, p[1])


def signed_curvature(p: tuple[Point, ...], t: float) -> float:
	'''Sign-carrying curvature numerator cross(B', B''). Zero for lines.'''
	d1 = derivative_at(p, t)
	d2 = second_derivative_at(p, t)
	return d1[0] * d2[1] - d1[1] * d2[0]


def interior_extrema(p: tuple[Point, ...], margin: float = 1e-4) -> int:
	'''Number of horizontal/vertical tangents strictly inside the segment
	(roots of B'x and B'y in (margin, 1 - margin)).'''
	if len(p) == 2:
		return 0
	c = as_cubic(p)
	count = 0
	for k in (0, 1):
		a, b, d = c[1][k] - c[0][k], c[2][k] - c[1][k], c[3][k] - c[2][k]
		qa, qb, qc = a - 2. * b + d, 2. * (b - a), a
		if abs(qa) < 1e-12:
			roots = [-qc / qb] if abs(qb) > 1e-12 else []
		else:
			disc = qb * qb - 4. * qa * qc
			if disc < 0.:
				continue
			r = math.sqrt(disc)
			roots = [(-qb + r) / (2. * qa), (-qb - r) / (2. * qa)]
		count += sum(1 for t in roots if margin < t < 1. - margin)
	return count


def shear(p: tuple[Point, ...], slant: float) -> tuple[Point, ...]:
	'''Upright the italic: x' = x - y * slant (slant = tan(italic angle)).'''
	if not slant:
		return p
	return tuple((q[0] - q[1] * slant, q[1]) for q in p)


# - Tangents -----------------------------
def start_tangent(p: tuple[Point, ...], eps: float) -> Point | None:
	'''Unit travel direction leaving p[0]: toward the nearest control point
	not within eps of it. None when the segment is degenerate.'''
	p0 = p[0]
	for q in p[1:]:
		if dist(p0, q) >= eps:
			return unit((q[0] - p0[0], q[1] - p0[1]))
	return None


def end_tangent(p: tuple[Point, ...], eps: float) -> Point | None:
	'''Unit travel direction arriving at p[-1].'''
	pn = p[-1]
	for q in reversed(p[:-1]):
		if dist(pn, q) >= eps:
			return unit((pn[0] - q[0], pn[1] - q[1]))
	return None


# - Integrals ----------------------------
def area_moment(p: tuple[Point, ...]) -> tuple[float, float]:
	'''Green area G = int (x y' - y x')/2 dt and first moment about the
	y-axis Mx = int x^2/2 y' dt over one segment. Gauss-Legendre is exact
	for these polynomial degrees.'''
	g = mx = 0.
	for t, w in _GL:
		x, y = point_at(p, t)
		dx, dy = derivative_at(p, t)
		g += w * (x * dy - y * dx)
		mx += w * x * x * dy
	return g * .5, mx * .5


def run_area_moment(segs) -> tuple[float, float]:
	g = mx = 0.
	for p in segs:
		a, m = area_moment(p)
		g += a
		mx += m
	return g, mx


def area(segs) -> float:
	'''Signed area of a closed run of segments (positive = CCW, y-up).'''
	return sum(area_moment(p)[0] for p in segs)


def arc_length(p: tuple[Point, ...]) -> float:
	if len(p) == 2:
		return dist(p[0], p[1])
	length = 0.
	for t, w in _GL:
		dx, dy = derivative_at(p, t)
		length += w * math.hypot(dx, dy)
	return length


# - Sampling and nearest point -----------
def sample(p: tuple[Point, ...], n: int) -> list[Point]:
	'''n samples at uniform t, endpoints included.'''
	return [point_at(p, i / (n - 1.)) for i in range(n)]


_LUT_T = tuple(i / float(LUT_STEPS) for i in range(LUT_STEPS + 1))


@lru_cache(maxsize=8192)
def _lut(p: tuple[Point, ...]) -> tuple[Point, ...]:
	return tuple(point_at(p, t) for t in _LUT_T)


@lru_cache(maxsize=8192)
def _lut_box(p: tuple[Point, ...]) -> tuple[float, float, float, float]:
	lut = _lut(p)
	xs, ys = [q[0] for q in lut], [q[1] for q in lut]
	return min(xs), min(ys), max(xs), max(ys)


@lru_cache(maxsize=8192)
def _sagitta(p: tuple[Point, ...]) -> float:
	'''Bound on the distance between the segment and its LUT polyline:
	h^2 / 8 * max |B''| with h = 1 / LUT_STEPS (B'' is linear in t).'''
	if len(p) == 2:
		return 0.
	acc = max(math.hypot(*second_derivative_at(p, 0.)), math.hypot(*second_derivative_at(p, 1.)))
	return acc / (8. * LUT_STEPS * LUT_STEPS)


def _chord_distance2(qx, qy, a, b) -> float:
	dx, dy = b[0] - a[0], b[1] - a[1]
	ex, ey = qx - a[0], qy - a[1]
	length2 = dx * dx + dy * dy
	if length2 > 0.:
		t = (ex * dx + ey * dy) / length2
		if t > 0.:
			if t >= 1.:
				ex, ey = qx - b[0], qy - b[1]
			else:
				ex, ey = ex - t * dx, ey - t * dy
	return ex * ex + ey * ey


@lru_cache(maxsize=8192)
def _power(p: tuple[Point, ...]) -> tuple[float, ...]:
	'''Power-basis coefficients (ax, bx, cx, dx, ay, by, cy, dy) of the
	segment as a cubic: B(t) = ((a t + b) t + c) t + d.'''
	(x0, y0), (x1, y1), (x2, y2), (x3, y3) = as_cubic(p)
	return (-x0 + 3. * x1 - 3. * x2 + x3, 3. * x0 - 6. * x1 + 3. * x2, 3. * (x1 - x0), x0,
			-y0 + 3. * y1 - 3. * y2 + y3, 3. * y0 - 6. * y1 + 3. * y2, 3. * (y1 - y0), y0)


def _newton(pw, qx: float, qy: float, t: float, d2: float) -> tuple[float, float]:
	'''(distance, t) from q to the power-basis cubic pw: up to NEWTON_STEPS
	steps on (B(t) - q) . B'(t) = 0 from the coarse hit t (squared
	distance d2), t clamped to [0, 1].'''
	ax, bx, cx, dx, ay, by, cy, dy = pw
	dx -= qx
	dy -= qy
	t0 = t

	for _ in range(NEWTON_STEPS):
		ex = ((ax * t + bx) * t + cx) * t + dx
		ey = ((ay * t + by) * t + cy) * t + dy
		d1x = (3. * ax * t + 2. * bx) * t + cx
		d1y = (3. * ay * t + 2. * by) * t + cy
		den = d1x * d1x + d1y * d1y + ex * (6. * ax * t + 2. * bx) + ey * (6. * ay * t + 2. * by)
		if abs(den) < 1e-12:
			break
		t_new = t - (ex * d1x + ey * d1y) / den
		t_new = 0. if t_new < 0. else (1. if t_new > 1. else t_new)
		if abs(t_new - t) < 1e-12:
			t = t_new
			break
		t = t_new

	ex = ((ax * t + bx) * t + cx) * t + dx
	ey = ((ay * t + by) * t + cy) * t + dy
	d = ex * ex + ey * ey
	return (math.sqrt(d), t) if d < d2 else (math.sqrt(d2), t0)


def _refine(p: tuple[Point, ...], q: Point, t: float, d2: float) -> tuple[float, float]:
	if len(p) == 2:
		t = min(1., max(0., line_param(q, p[0], p[1])))
		x, y = point_at(p, t)
		return math.hypot(x - q[0], y - q[1]), t
	return _newton(_power(p), q[0], q[1], t, d2)


def nearest(p: tuple[Point, ...], q: Point) -> float:
	'''Distance from q to segment p: coarse search over LUT_STEPS samples,
	then NEWTON_STEPS refinement steps.'''
	qx, qy = q
	best_i, best_d = 0, float('inf')
	for i, (x, y) in enumerate(_lut(p)):
		d = (x - qx) * (x - qx) + (y - qy) * (y - qy)
		if d < best_d:
			best_i, best_d = i, d
	return _refine(p, q, _LUT_T[best_i], best_d)[0]


def _distances(queries, run, bound: float, floor: float = 0.) -> float:
	'''Max over ordered query points of the distance to a run of segments
	(0 when nothing exceeds floor).
	Each query hill-climbs the run LUT from the previous hit, since the
	nearest point moves along the run with the queries. A climbed hit is an
	upper bound, so only a query that would raise the max gets an exact
	full scan (which also re-syncs the climb).'''
	pts, owner = [], []
	for j, p in enumerate(run):
		pts.extend(_lut(p))
		owner.extend((j,) * (LUT_STEPS + 1))
	sag = [_sagitta(p) for p in run]
	pws = [_power(p) if len(p) > 2 else None for p in run]
	last = len(run) - 1

	n = len(pts)
	worst = 0.
	floor = max(RESOLUTION, floor)
	i = 0

	boxes = [_lut_box(p) for p in run]
	step = LUT_STEPS + 1

	def scan(qx, qy, best_k, best_d):
		'''Exact LUT argmin; segments whose LUT box is farther than the
		current best are skipped.'''
		for j, (x0, y0, x1, y1) in enumerate(boxes):
			ex = x0 - qx if qx < x0 else (qx - x1 if qx > x1 else 0.)
			ey = y0 - qy if qy < y0 else (qy - y1 if qy > y1 else 0.)
			if ex * ex + ey * ey >= best_d:
				continue
			base = j * step
			for k in range(base, base + step):
				x, y = pts[k]
				dk = (x - qx) * (x - qx) + (y - qy) * (y - qy)
				if dk < best_d:
					best_k, best_d = k, dk
		return best_k, best_d

	def one(j, qx, qy, t, d):
		pw = pws[j]
		if pw is None:
			return _refine(run[j], (qx, qy), t, d)
		return _newton(pw, qx, qy, t, d)

	def refine(k, d, qx, qy):
		j = owner[k]
		dist_q, t = one(j, qx, qy, _LUT_T[k % step], d)
		# the nearest point may sit just across a segment junction
		if t == 1. and j < last:
			dist_q = min(dist_q, one(j + 1, qx, qy, 0., d)[0])
		elif t == 0. and j > 0:
			dist_q = min(dist_q, one(j - 1, qx, qy, 1., d)[0])
		return dist_q

	for qx, qy in queries:
		x, y = pts[i]
		d = (x - qx) * (x - qx) + (y - qy) * (y - qy)
		start = i
		while i + 1 < n:
			x, y = pts[i + 1]
			dk = (x - qx) * (x - qx) + (y - qy) * (y - qy)
			if dk > d:
				break
			i, d = i + 1, dk
		if i == start:
			while i > 0:
				x, y = pts[i - 1]
				dk = (x - qx) * (x - qx) + (y - qy) * (y - qy)
				if dk >= d:
					break
				i, d = i - 1, dk

		if d <= floor * floor:
			continue

		# polyline distance plus the sagitta bound is a cheap upper bound
		ub = d
		if i > 0:
			ub = min(ub, _chord_distance2(qx, qy, pts[i - 1], pts[i]))
		if i + 1 < n:
			ub = min(ub, _chord_distance2(qx, qy, pts[i], pts[i + 1]))
		if math.sqrt(ub) + max(sag[owner[i - 1] if i else 0], sag[owner[i]], sag[owner[i + 1] if i + 1 < n else owner[i]]) <= floor:
			continue

		dist_q = refine(i, d, qx, qy)
		if dist_q <= floor:
			continue

		i, d = scan(qx, qy, i, d)
		dist_q = refine(i, d, qx, qy)
		if dist_q > floor:
			worst = floor = dist_q
			if worst > bound:
				return worst

	return worst


def run_distance(src, cand, bound: float = float('inf'), samples: tuple[int, int] = (SRC_SAMPLES, CAND_SAMPLES)) -> float:
	'''Two-sided distance between two runs of segments (tuples of points):
	SRC_SAMPLES per source segment against the candidate and CAND_SAMPLES
	per candidate segment against the source; the max of both directions.
	Stops early and returns the running max once it exceeds bound.'''
	worst = 0.

	for runs, other, n in ((src, cand, samples[0]), (cand, src, samples[1])):
		queries = [q for p in runs for q in sample(p, n)]
		worst = max(worst, _distances(queries, other, bound, worst))
		if worst > bound:
			break

	return worst
