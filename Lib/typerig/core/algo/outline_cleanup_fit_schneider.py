# MODULE: TypeRig / Core / Algo / Outline Cleanup — Schneider fit
# -----------------------------------------------------------
# Least-squares cubic fit with fixed end tangents, Newton-Raphson
# reparameterization and recursive splitting. Port of FitCurves.c
# (P. J. Schneider, Graphics Gems I, 1990). Fallback for runs the
# Levien fit rejects; recursive mode is for the trace front end.
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

from typerig.core.algo.outline_cleanup_geom import Seg, Point, point_at, derivative_at, second_derivative_at, unit, dist

__version__ = '1.0.0'

MAX_ITERATIONS = 4
SAMPLES_PER_SEGMENT = 8


# - Helpers ------------------------------
def sample_run(segs) -> list[Point]:
	'''SAMPLES_PER_SEGMENT points per source segment plus every on-curve.'''
	points = []
	for p in segs:
		points.extend(point_at(p, k / float(SAMPLES_PER_SEGMENT)) for k in range(SAMPLES_PER_SEGMENT))
	points.append(segs[-1][-1])
	return points


def _chord_length_parameterize(d, first, last):
	u = [0.]
	for i in range(first + 1, last + 1):
		u.append(u[-1] + dist(d[i], d[i - 1]))
	total = u[-1]
	if total <= 0.:
		return [k / float(last - first) for k in range(last - first + 1)]
	return [x / total for x in u]


def _generate_bezier(d, first, last, u, t_hat1, t_hat2):
	'''Least-squares handle lengths alpha_l, alpha_r for fixed tangents.
	t_hat2 points from the last point back into the curve (FitCurves).'''
	p0, p3 = d[first], d[last]
	c00 = c01 = c11 = x0 = x1 = 0.

	for i, t in enumerate(u):
		mt = 1. - t
		b0, b1, b2, b3 = mt * mt * mt, 3. * t * mt * mt, 3. * t * t * mt, t * t * t
		a0 = (t_hat1[0] * b1, t_hat1[1] * b1)
		a1 = (t_hat2[0] * b2, t_hat2[1] * b2)

		c00 += a0[0] * a0[0] + a0[1] * a0[1]
		c01 += a0[0] * a1[0] + a0[1] * a1[1]
		c11 += a1[0] * a1[0] + a1[1] * a1[1]

		q = d[first + i]
		tx = q[0] - (p0[0] * (b0 + b1) + p3[0] * (b2 + b3))
		ty = q[1] - (p0[1] * (b0 + b1) + p3[1] * (b2 + b3))
		x0 += a0[0] * tx + a0[1] * ty
		x1 += a1[0] * tx + a1[1] * ty

	det_c0_c1 = c00 * c11 - c01 * c01
	det_c0_x = c00 * x1 - c01 * x0
	det_x_c1 = x0 * c11 - x1 * c01

	if det_c0_c1 == 0.:
		det_c0_c1 = c00 * c11 * 10e-12

	alpha_l = det_x_c1 / det_c0_c1 if det_c0_c1 else 0.
	alpha_r = det_c0_x / det_c0_c1 if det_c0_c1 else 0.

	seg_length = dist(p0, p3)
	epsilon = 1.0e-6 * seg_length

	if alpha_l < epsilon or alpha_r < epsilon:
		# Wu-Barsky heuristic
		alpha_l = alpha_r = seg_length / 3.

	return (p0,
			(p0[0] + t_hat1[0] * alpha_l, p0[1] + t_hat1[1] * alpha_l),
			(p3[0] + t_hat2[0] * alpha_r, p3[1] + t_hat2[1] * alpha_r),
			p3)


def _newton_raphson_root_find(curve, q, u):
	x, y = point_at(curve, u)
	dx, dy = derivative_at(curve, u)
	ddx, ddy = second_derivative_at(curve, u)
	numerator = (x - q[0]) * dx + (y - q[1]) * dy
	denominator = dx * dx + dy * dy + (x - q[0]) * ddx + (y - q[1]) * ddy
	if denominator == 0.:
		return u
	return u - numerator / denominator


def _reparameterize(d, first, curve, u):
	'''Newton per sample, clamped to [0, 1] and kept in order (a hardening
	over FitCurves, which can push parameters out of range or past each other).'''
	out = []
	for i, t in enumerate(u):
		t = min(1., max(0., _newton_raphson_root_find(curve, d[first + i], t)))
		out.append(max(t, out[-1]) if out else t)
	return out


def _compute_max_error(d, first, last, curve, u):
	'''Max squared distance between each point and the curve at its parameter.'''
	split_point = (last - first + 1) // 2
	max_dist = 0.
	for i in range(first + 1, last):
		x, y = point_at(curve, u[i - first])
		d2 = (x - d[i][0]) ** 2 + (y - d[i][1]) ** 2
		if d2 >= max_dist:
			max_dist = d2
			split_point = i
	return max_dist, split_point


def _compute_center_tangent(d, center):
	v1 = (d[center - 1][0] - d[center][0], d[center - 1][1] - d[center][1])
	v2 = (d[center][0] - d[center + 1][0], d[center][1] - d[center + 1][1])
	return unit(((v1[0] + v2[0]) * .5, (v1[1] + v2[1]) * .5))


# - Fit ----------------------------------
def _fit_cubic(d, first, last, t_hat1, t_hat2, error, budget):
	'''Returns a list of 4-point curves, or None when more than budget
	curves would be needed.'''
	iteration_error = error * 4.
	n_pts = last - first + 1

	if n_pts == 2:
		length = dist(d[last], d[first]) / 3.
		return [(d[first],
				(d[first][0] + t_hat1[0] * length, d[first][1] + t_hat1[1] * length),
				(d[last][0] + t_hat2[0] * length, d[last][1] + t_hat2[1] * length),
				d[last])]

	u = _chord_length_parameterize(d, first, last)
	curve = _generate_bezier(d, first, last, u, t_hat1, t_hat2)
	max_error, split_point = _compute_max_error(d, first, last, curve, u)

	if max_error < error:
		return [curve]

	# FitCurves skips reparameterization when far off and splits instead;
	# when splitting is not allowed there is nothing to lose by iterating.
	if max_error < iteration_error or (budget is not None and budget < 2):
		for _ in range(MAX_ITERATIONS):
			u_prime = _reparameterize(d, first, curve, u)
			cand = _generate_bezier(d, first, last, u_prime, t_hat1, t_hat2)
			cand_error, cand_split = _compute_max_error(d, first, last, cand, u_prime)
			if cand_error >= max_error:
				break		# keep the best iteration, not the last
			curve, max_error, split_point, u = cand, cand_error, cand_split, u_prime
			if max_error < error:
				return [curve]

	if budget is not None and budget < 2:
		return None

	t_hat_center = _compute_center_tangent(d, split_point)
	if t_hat_center is None:
		return None

	left = _fit_cubic(d, first, split_point, t_hat1, t_hat_center, error, None if budget is None else budget - 1)
	if left is None:
		return None

	t_neg = (-t_hat_center[0], -t_hat_center[1])
	right = _fit_cubic(d, split_point, last, t_neg, t_hat2, error, None if budget is None else budget - len(left))
	if right is None:
		return None

	return left + right


def fit_schneider(points: list[Point], t_start: Point, t_end: Point, tol: float, max_segments: int | None = None) -> list[Seg] | None:
	'''Fit cubics to points with fixed unit end tangents. Both tangents are
	travel directions (t_end arrives at the last point). Returns None when
	the fit needs more than max_segments cubics.'''
	if len(points) < 2:
		return None

	t_hat2 = (-t_end[0], -t_end[1])
	curves = _fit_cubic(points, 0, len(points) - 1, t_start, t_hat2, tol * tol, max_segments)

	if curves is None:
		return None

	return [Seg(c, (0, 0)) for c in curves]
