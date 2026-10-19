# MODULE: TypeRig / Core / Algo / Outline Cleanup — Stage C1
# -----------------------------------------------------------
# Levien area/moment fit: replace a run of cubics with one cubic
# that keeps the endpoints and end tangent directions and matches
# the signed area and first x-moment of the source run.
#
# In the normalized frame (start (0,0), end (1,0)) the candidate
# moment is a cubic polynomial in the handle lengths (d0, d1).
# Substituting d0 = N(d1)/D(d1) from the area constraint and
# clearing D^3 gives a polynomial P(d1) whose sign changes are
# scanned and bisected.
#
# Ref: R. Levien, Fitting cubic Bezier curves (2021);
#      kurbo fit.rs / simplify.rs
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

from typerig.core.algo.outline_cleanup_geom import (
	Seg, _GL, start_tangent, end_tangent, run_area_moment, run_distance, dist
)

__version__ = '1.0.0'

# - Config -------------------------------
D_MAX = 1.5				# max normalized handle length
SCAN_STEPS = 300
BISECT_STEPS = 50
DEN_EPS = 1e-9
SIN_EPS = 1e-6			# |sin theta| below this: tangent lies on the chord
LINE_ANGLE = 1e-6		# rad; both tangents this close to the chord ...
LINE_AREA = 1e-9		# ... and normalized area below this: straight run
PRESCREEN = (4, 8)		# sparse samples (source, candidate) to rank candidates


# - Candidate moment constants -----------
# Bernstein pieces of the candidate x(t) = X0 + d0 c0 B1 - d1 c1 B2,
# y(t) = d0 s0 B1 + d1 s1 B2. K[i][j] = 1/2 int f_i g_j dt with
# f = (X0^2, B1^2, B2^2, X0 B1, X0 B2, B1 B2) and g = (B1', B2').
def _moment_constants():
	k = [[0., 0.] for _ in range(6)]
	for t, w in _GL:
		mt = 1. - t
		b1, b2, b3 = 3. * mt * mt * t, 3. * mt * t * t, t * t * t
		x0 = b2 + b3
		f = (x0 * x0, b1 * b1, b2 * b2, x0 * b1, x0 * b2, b1 * b2)
		g = (3. * mt * (1. - 3. * t), 3. * t * (2. - 3. * t))
		for i in range(6):
			for j in range(2):
				k[i][j] += .5 * w * f[i] * g[j]
	return k


_K = _moment_constants()


def candidate_area(d0: float, d1: float, th0: float, th1: float) -> float:
	'''Closed-form signed area between the candidate and its chord (= -G).'''
	return .15 * (2. * d0 * math.sin(th0) + 2. * d1 * math.sin(th1) - d0 * d1 * math.sin(th0 + th1))


def _moment_terms(th0: float, th1: float) -> dict:
	'''Candidate Mx as {(a, b): coef} for monomials d0^a d1^b.'''
	s0, c0, s1, c1 = math.sin(th0), math.cos(th0), math.sin(th1), math.cos(th1)
	K = _K
	terms = {}

	def add(key, value):
		terms[key] = terms.get(key, 0.) + value

	add((1, 0), s0 * K[0][0])
	add((3, 0), s0 * c0 * c0 * K[1][0])
	add((1, 2), s0 * c1 * c1 * K[2][0])
	add((2, 0), 2. * s0 * c0 * K[3][0])
	add((1, 1), -2. * s0 * c1 * K[4][0])
	add((2, 1), -2. * s0 * c0 * c1 * K[5][0])

	add((0, 1), s1 * K[0][1])
	add((2, 1), s1 * c0 * c0 * K[1][1])
	add((0, 3), s1 * c1 * c1 * K[2][1])
	add((1, 1), 2. * s1 * c0 * K[3][1])
	add((0, 2), -2. * s1 * c1 * K[4][1])
	add((1, 2), -2. * s1 * c0 * c1 * K[5][1])

	return terms


def candidate_moment(d0: float, d1: float, th0: float, th1: float) -> float:
	return sum(c * d0 ** a * d1 ** b for (a, b), c in _moment_terms(th0, th1).items())


# - Polynomials (coefficients low -> high)
def _pmul(a, b):
	r = [0.] * (len(a) + len(b) - 1)
	for i, x in enumerate(a):
		for j, y in enumerate(b):
			r[i + j] += x * y
	return r


def _padd(a, b, scale=1.):
	r = list(a) + [0.] * max(0, len(b) - len(a))
	for i, y in enumerate(b):
		r[i] += scale * y
	return r


def _ppow(a, n):
	r = [1.]
	for _ in range(n):
		r = _pmul(r, a)
	return r


def _peval(p, x):
	r = 0.
	for c in reversed(p):
		r = r * x + c
	return r


def _moment_polynomial(terms, N, D, mx_target):
	'''D^3 * (Mx(N/D, d1) - mx_target) as a polynomial in d1.'''
	poly = _padd([0.], _ppow(D, 3), -mx_target)
	for (a, b), c in terms.items():
		mono = _pmul(_pmul(_ppow(N, a), _ppow(D, 3 - a)), [0.] * b + [1.])
		poly = _padd(poly, mono, c)
	return poly


def _roots(poly, D):
	'''Sign changes of poly on (0, D_MAX], refined by bisection. Scan points
	where the linear denominator D vanishes are skipped.'''
	coefs = poly[::-1]
	d0, d1 = D
	roots = []
	prev_x = prev_v = None

	for k in range(1, SCAN_STEPS + 1):
		x = D_MAX * k / SCAN_STEPS
		if abs(d0 + d1 * x) < DEN_EPS:
			prev_x = prev_v = None
			continue

		v = 0.
		for c in coefs:
			v = v * x + c

		if v == 0.:
			roots.append(x)
		elif prev_v is not None and prev_v != 0. and (prev_v < 0.) != (v < 0.):
			lo, hi, f_lo = prev_x, x, prev_v
			for _ in range(BISECT_STEPS):
				mid = (lo + hi) * .5
				f_mid = 0.
				for c in coefs:
					f_mid = f_mid * mid + c
				if (f_mid < 0.) == (f_lo < 0.):
					lo, f_lo = mid, f_mid
				else:
					hi = mid
			roots.append((lo + hi) * .5)

		prev_x, prev_v = x, v

	return roots


# - Fit ----------------------------------
def fit_run(segs: list[Seg], tol: float, eps_point: float = .5, eps_handle: float = .5,
            t_start: Point | None = None, t_end: Point | None = None) -> tuple[Seg, float] | None:
	'''Replace a run of segments with one cubic (or a line for a straight
	run). Returns (segment, max error) or None if nothing is within tol.
	t_start / t_end: optional unit travel directions to use at the ends
	instead of the run's own tangents (t_end arrives at the last point).'''
	src = [s.p for s in segs]
	span = (segs[0].src[0], segs[-1].src[1])
	p0, p3 = src[0][0], src[-1][-1]

	length = dist(p0, p3)
	if length < eps_point:
		return None

	t0 = t_start if t_start is not None else start_tangent(src[0], eps_handle)
	t1 = t_end if t_end is not None else end_tangent(src[-1], eps_handle)
	if t0 is None or t1 is None:
		return None

	# - Normalize: start at (0, 0), end at (1, 0)
	ca, sa = (p3[0] - p0[0]) / length, (p3[1] - p0[1]) / length

	def to_frame(q):
		dx, dy = q[0] - p0[0], q[1] - p0[1]
		return ((dx * ca + dy * sa) / length, (-dx * sa + dy * ca) / length)

	def from_frame(q):
		return (p0[0] + length * (q[0] * ca - q[1] * sa), p0[1] + length * (q[0] * sa + q[1] * ca))

	th0 = math.atan2(-t0[0] * sa + t0[1] * ca, t0[0] * ca + t0[1] * sa)
	u1 = (-(t1[0] * ca + t1[1] * sa), -(-t1[0] * sa + t1[1] * ca))
	th1 = math.atan2(u1[1], -u1[0])

	g, mx_target = run_area_moment([tuple(to_frame(q) for q in p) for p in src])
	target_area = -g

	# - Straight run
	if abs(th0) < LINE_ANGLE and abs(th1) < LINE_ANGLE and abs(target_area) < LINE_AREA:
		err = run_distance(src, [(p0, p3)], tol)
		return (Seg((p0, p3), span), err) if err <= tol else None

	s0, s1 = math.sin(th0), math.sin(th1)
	if abs(s0) < SIN_EPS or abs(s1) < SIN_EPS:
		return None		# S-curve with an end on the chord: Schneider handles it

	# - Area constraint: d0 = N(d1) / D(d1); moment constraint: P(d1) = 0
	N = [20. / 3. * target_area, -2. * s1]
	D = [2. * s0, -math.sin(th0 + th1)]
	poly = _moment_polynomial(_moment_terms(th0, th1), N, D, mx_target)

	cands = []
	for d1 in _roots(poly, D):
		d0 = _peval(N, d1) / _peval(D, d1)
		if d0 <= 0. or d0 > D_MAX:
			continue

		cand = (p0,
				from_frame((d0 * math.cos(th0), d0 * s0)),
				from_frame((1. - d1 * math.cos(th1), d1 * s1)),
				p3)
		cands.append((run_distance(src, [cand], tol, PRESCREEN), cand))

	# A sparse max never exceeds the full one: rank by it, and skip any
	# candidate whose sparse error already loses to the best full error.
	best = None
	for coarse, cand in sorted(cands, key=lambda item: item[0]):
		bound = tol if best is None else best[1]
		if coarse > bound:
			break
		err = run_distance(src, [cand], bound)
		if err <= bound and (best is None or err < best[1]):
			best = (cand, err)

	if best is None:
		return None

	return Seg(best[0], span), best[1]
