# MODULE: TypeRig / Core / Algo / Design Transfer
# -----------------------------------------------------------
# Contour-level design-change transfer by best-fit 2D affine
# plus a bbox-normalised per-point residual.
#
# Given two point-compatible contours (src -> dst) describing
# a design change in one master, and a target contour (tgt)
# from a different master, reproduce the change on tgt.
#
# The contours must be point-compatible: same node count and
# corresponding node order. Isomorphism is a precondition,
# not something this module checks.
#
# Stages:
#   1. fit_affine        - least-squares 2x3 affine, src -> dst
#   2. decompose_affine  - polar split into rotation / shear
#                          / scale (diagnostics only)
#   3. compute_residual  - per-node leftover after the affine
#                          fit, normalised by src bbox extent
#   4. apply_transfer    - rebuild tgt under the fitted affine,
#                          pivoted at tgt's own centroid, with
#                          residual rescaled by tgt bbox extent
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

# - Init --------------------------------
__version__ = '0.1.0'

_EPS = 1e-12
_POLAR_ITER_MAX = 16
_POLAR_TOL = 1e-10


# - Helpers -----------------------------
def _xy(p):
	'''Coerce p to a (float, float) tuple. Accepts Point, tuple, list, object with .x/.y.'''
	if hasattr(p, 'x') and hasattr(p, 'y'):
		return (float(p.x), float(p.y))
	return (float(p[0]), float(p[1]))


def _centroid(points):
	'''Arithmetic mean of the point list. O(N), one pass.'''
	n = len(points)
	if n == 0:
		return (0.0, 0.0)
	sx = sy = 0.0
	for p in points:
		x, y = _xy(p)
		sx += x
		sy += y
	return (sx / n, sy / n)


def _bbox(points):
	'''Tiny wrapper around Bounds that tolerates Point/tuple/object inputs.'''
	return Bounds([_xy(p) for p in points])


def _solve_3x3_sym(G, b):
	'''Solve G * x = b for a symmetric 3x3 G via cofactor inverse.
	Returns the 3-vector x, or None if G is near-singular.
	G is given as nine scalars in row-major order.
	'''
	g00, g01, g02, g10, g11, g12, g20, g21, g22 = G

	# Cofactor expansion along row 0.
	c00 = g11 * g22 - g12 * g21
	c01 = g12 * g20 - g10 * g22
	c02 = g10 * g21 - g11 * g20
	det = g00 * c00 + g01 * c01 + g02 * c02

	if abs(det) < _EPS:
		return None

	c10 = g02 * g21 - g01 * g22
	c11 = g00 * g22 - g02 * g20
	c12 = g01 * g20 - g00 * g21
	c20 = g01 * g12 - g02 * g11
	c21 = g02 * g10 - g00 * g12
	c22 = g00 * g11 - g01 * g10

	# Inverse[i][j] = cofactor[j][i] / det  (transpose of cofactor matrix).
	inv_det = 1.0 / det
	b0, b1, b2 = b
	x0 = (c00 * b0 + c10 * b1 + c20 * b2) * inv_det
	x1 = (c01 * b0 + c11 * b1 + c21 * b2) * inv_det
	x2 = (c02 * b0 + c12 * b1 + c22 * b2) * inv_det
	return (x0, x1, x2)


def _polar_2x2(a, b, c, d):
	'''Polar decomposition of a 2x2 matrix L = [[a, b], [c, d]] = R * S,
	where R is a rotation (orthogonal with det > 0 when possible) and S is
	symmetric. Uses Higham's iteration R_{k+1} = 0.5 * (R_k + R_k^-T),
	which converges quadratically to the closest rotation of L.

	Returns (R_tuple, S_tuple) = ((ra, rb, rc, rd), (sa, sb, sc, sd)).
	Falls back to identity when L is singular.
	'''
	ra, rb, rc, rd = a, b, c, d

	for _ in range(_POLAR_ITER_MAX):
		det = ra * rd - rb * rc
		if abs(det) < _EPS:
			# Degenerate linear part. Give up gracefully with identity R.
			ra, rb, rc, rd = 1.0, 0.0, 0.0, 1.0
			break

		# inv(R)^T: inverse of [[ra, rb], [rc, rd]] is 1/det * [[rd, -rb], [-rc, ra]];
		# transposed -> [[rd, -rc], [-rb, ra]] / det.
		ia = rd / det
		ib = -rc / det
		ic = -rb / det
		id_ = ra / det

		na = 0.5 * (ra + ia)
		nb = 0.5 * (rb + ib)
		nc = 0.5 * (rc + ic)
		nd = 0.5 * (rd + id_)

		delta = abs(na - ra) + abs(nb - rb) + abs(nc - rc) + abs(nd - rd)
		ra, rb, rc, rd = na, nb, nc, nd
		if delta < _POLAR_TOL:
			break

	# S = R^T * L.
	sa = ra * a + rc * c
	sb = ra * b + rc * d
	sc = rb * a + rd * c
	sd = rb * b + rd * d

	return (ra, rb, rc, rd), (sa, sb, sc, sd)


# - Stage 1: Affine fit ------------------
def fit_affine(src_points, dst_points):
	'''Least-squares 2D affine fit, src -> dst.

	Fits parameters (xx, xy, yx, yy, dx, dy) of the typerig Transform
	convention such that for each pair (sx, sy) -> (tx, ty):

		tx ~ xx * sx + yx * sy + dx
		ty ~ xy * sx + yy * sy + dy

	The two rows of the affine are independent 3-parameter regressions
	that share the same 3x3 Gram matrix

		G = sum over points of [[sx sx, sx sy, sx],
		                        [sy sx, sy sy, sy],
		                        [sx,    sy,    1 ]]

	so we invert G once and apply it to two right-hand sides.

	Args:
	    src_points: iterable of (x, y) or Point, length N >= 3
	    dst_points: iterable of (x, y) or Point, same length

	Returns:
	    (Transform, rms_residual)
	        Transform  - fitted affine, typerig convention
	        rms_residual - sqrt(mean(|dst - A(src)|^2)) in input units;
	                       0 for perfectly affine pairs

	Raises:
	    ValueError on length mismatch, fewer than 3 points, or a degenerate
	    point configuration (all src points collinear).
	'''
	src = [_xy(p) for p in src_points]
	dst = [_xy(p) for p in dst_points]

	n = len(src)
	if n != len(dst):
		raise ValueError('fit_affine: src/dst length mismatch: {} vs {}'.format(n, len(dst)))
	if n < 3:
		raise ValueError('fit_affine: need at least 3 points, got {}'.format(n))

	# Assemble Gram matrix and two right-hand sides.
	sxx = sxy = syy = sx = sy = 0.0
	bx0 = bx1 = bx2 = 0.0
	by0 = by1 = by2 = 0.0

	for (u, v), (p, q) in zip(src, dst):
		sxx += u * u
		sxy += u * v
		syy += v * v
		sx  += u
		sy  += v
		bx0 += u * p
		bx1 += v * p
		bx2 += p
		by0 += u * q
		by1 += v * q
		by2 += q

	G = (sxx, sxy, sx,
	     sxy, syy, sy,
	     sx,  sy,  float(n))

	row_x = _solve_3x3_sym(G, (bx0, bx1, bx2))
	row_y = _solve_3x3_sym(G, (by0, by1, by2))

	if row_x is None or row_y is None:
		raise ValueError('fit_affine: degenerate point configuration (collinear or coincident points)')

	xx, yx, dx = row_x
	xy, yy, dy = row_y

	xform = Transform(xx, xy, yx, yy, dx, dy)

	# Residual RMS in input units.
	sq = 0.0
	for (u, v), (p, q) in zip(src, dst):
		px, py = xform.applyTransformation(u, v)
		ex, ey = p - px, q - py
		sq += ex * ex + ey * ey
	rms = math.sqrt(sq / n)

	return xform, rms


# - Stage 2: Decomposition (diagnostics) -
def decompose_affine(xform):
	'''Decompose an affine's linear part via polar decomposition.

	The linear 2x2 block L is written R * S where R is a rotation and S is
	symmetric. Rotation angle, uniform + anisotropic scale, and shear are
	read off S. Values are advisory only - intended for UI feedback and
	for thresholding "is this close to a rigid motion?" decisions.

	Args:
	    xform: Transform (typerig convention)

	Returns:
	    dict with keys:
	        rotation_deg   - signed rotation angle extracted from R, degrees
	        scale_x        - diagonal of S in the first principal direction
	        scale_y        - diagonal of S in the second principal direction
	        shear          - off-diagonal of S normalised by avg scale
	        determinant    - det(L); negative means R is a reflection
	        translation    - (dx, dy)
	'''
	xx, xy, yx, yy, dx, dy = (xform[0], xform[1], xform[2], xform[3], xform[4], xform[5])

	# typerig stores the linear part so that applied = (xx*x + yx*y, xy*x + yy*y);
	# the column-vector 2x2 is [[xx, yx], [xy, yy]].
	a, b, c, d = xx, yx, xy, yy

	R, S = _polar_2x2(a, b, c, d)
	ra, rb, rc, rd = R
	sa, sb, sc, sd = S

	# Rotation angle from R = [[cos, -sin], [sin, cos]].
	rotation_deg = math.degrees(math.atan2(rc, ra))

	scale_x = sa
	scale_y = sd
	avg_scale = 0.5 * (abs(sa) + abs(sd))
	shear = sb / avg_scale if avg_scale > _EPS else 0.0

	det = a * d - b * c

	return {
		'rotation_deg': rotation_deg,
		'scale_x': scale_x,
		'scale_y': scale_y,
		'shear': shear,
		'determinant': det,
		'translation': (dx, dy),
	}


# - Stage 3: Residual --------------------
def compute_residual(src_points, dst_points, xform, src_bbox=None):
	'''Per-point leftover after affine prediction, normalised by src bbox.

	Residual_i = (dst_i - A(src_i)) / (src_bbox.width, src_bbox.height)

	Normalising to unit space lets the residual be reapplied on a target
	contour of different size by rescaling with the target's bbox extent
	(see apply_transfer). Zero bbox extent on an axis disables residual
	on that axis.

	Args:
	    src_points: iterable of (x, y) or Point
	    dst_points: same length as src_points
	    xform: Transform from fit_affine
	    src_bbox: optional precomputed Bounds over src_points

	Returns:
	    list of (rx, ry) tuples in unit space, length len(src_points)
	'''
	src = [_xy(p) for p in src_points]
	dst = [_xy(p) for p in dst_points]

	if len(src) != len(dst):
		raise ValueError('compute_residual: length mismatch')

	if src_bbox is None:
		src_bbox = _bbox(src)

	w = src_bbox.width if src_bbox.width > _EPS else 0.0
	h = src_bbox.height if src_bbox.height > _EPS else 0.0

	inv_w = 1.0 / w if w > 0.0 else 0.0
	inv_h = 1.0 / h if h > 0.0 else 0.0

	out = []
	for (u, v), (p, q) in zip(src, dst):
		px, py = xform.applyTransformation(u, v)
		out.append(((p - px) * inv_w, (q - py) * inv_h))
	return out


# - Stage 4: Apply transfer --------------
def apply_transfer(tgt_points, xform, residual_norm=None,
                   tgt_bbox=None, src_bbox=None,
                   src_centroid=None, dst_centroid=None,
                   tgt_centroid=None,
                   mode='affine_residual'):
	'''Apply a fitted design change to a target contour.

	The fitted affine represents the change "src becomes dst". We do NOT
	apply it to tgt in absolute coordinates - that would drag tgt toward
	src's world position. Instead we pivot the linear part of the affine
	at tgt's own centroid and add the inter-centroid translation on top.
	Let L be the 2x2 linear block and c_s, c_d, c_t the src/dst/tgt
	centroids; for each target point t:

	    t_new = L * (t - c_t) + c_t + (c_d - c_s) + residual_term

	residual_term is the per-point residual from compute_residual,
	rescaled from src bbox units to tgt bbox units per axis.

	Modes:
	    'affine_only'     - skip residual even if supplied
	    'affine_residual' - apply L + centroid delta + residual (default)
	    'bbox_fallback'   - mimic the legacy rigid-body path: use only
	                        diagonal of L (scale_x, scale_y) and centroid
	                        delta; no rotation, no shear, no residual

	Args:
	    tgt_points: iterable of (x, y) or Point
	    xform: Transform from fit_affine (src -> dst)
	    residual_norm: output of compute_residual, or None
	    tgt_bbox, src_bbox: Bounds; used only for residual rescaling
	    src_centroid, dst_centroid: (x, y); if supplied, the centroid
	        delta is c_d - c_s exactly. If omitted, delta is reconstructed
	        from the fit's translation using src_bbox centre as a proxy
	        for c_s - accurate for symmetric contours; prefer the
	        explicit form for asymmetric shapes.
	    tgt_centroid: (x, y); if omitted, computed from tgt_points.
	    mode: see above
	'''
	tgt = [_xy(p) for p in tgt_points]
	n = len(tgt)
	if n == 0:
		return []

	if mode not in ('affine_only', 'affine_residual', 'bbox_fallback'):
		raise ValueError('apply_transfer: unknown mode {!r}'.format(mode))

	# Target centroid: pivot point for the linear part.
	if tgt_centroid is not None:
		ctx, cty = _xy(tgt_centroid)
	else:
		ctx, cty = _centroid(tgt)

	# Extract affine components in typerig convention:
	#   applied = (xx*x + yx*y + dx, xy*x + yy*y + dy)
	xx, xy_, yx, yy, dx, dy = (xform[0], xform[1], xform[2], xform[3], xform[4], xform[5])

	# Centroid delta = c_d - c_s.
	if src_centroid is not None and dst_centroid is not None:
		csx, csy = _xy(src_centroid)
		cdx, cdy = _xy(dst_centroid)
		centroid_dx = cdx - csx
		centroid_dy = cdy - csy
	elif src_bbox is not None:
		# Reconstruct from fit: c_d - c_s = (L - I) * c_s + t_fit. Uses
		# src bbox centre as a proxy for c_s.
		csx = src_bbox.x + 0.5 * src_bbox.width
		csy = src_bbox.y + 0.5 * src_bbox.height
		lmi_cs_x = (xx - 1.0) * csx + yx * csy
		lmi_cs_y = xy_ * csx + (yy - 1.0) * csy
		centroid_dx = lmi_cs_x + dx
		centroid_dy = lmi_cs_y + dy
	else:
		centroid_dx = dx
		centroid_dy = dy

	# Bbox-fallback mode strips to diagonal L.
	if mode == 'bbox_fallback':
		sx_diag = xx
		sy_diag = yy
		xx_use, xy_use, yx_use, yy_use = sx_diag, 0.0, 0.0, sy_diag
	else:
		xx_use, xy_use, yx_use, yy_use = xx, xy_, yx, yy

	# Residual scaling: unit-space residual -> tgt-bbox units, per axis.
	use_residual = (mode == 'affine_residual' and residual_norm is not None)
	if use_residual:
		if len(residual_norm) != n:
			raise ValueError('apply_transfer: residual length {} != tgt length {}'.format(len(residual_norm), n))
		if tgt_bbox is None:
			tgt_bbox = _bbox(tgt)
		scale_rx = tgt_bbox.width
		scale_ry = tgt_bbox.height
	else:
		scale_rx = scale_ry = 0.0

	out = []
	for i, (tx, ty) in enumerate(tgt):
		# Pivot at target centroid: linear part acts on (t - c_t).
		ux = tx - ctx
		uy = ty - cty
		# L * u  (typerig convention).
		lx = xx_use * ux + yx_use * uy
		ly = xy_use * ux + yy_use * uy
		# Reassemble: L*(t-c_t) + c_t + centroid_delta.
		nx = lx + ctx + centroid_dx
		ny = ly + cty + centroid_dy
		if use_residual:
			rx, ry = residual_norm[i]
			nx += rx * scale_rx
			ny += ry * scale_ry
		out.append((nx, ny))
	return out


# - Convenience: one-shot per-contour pipeline ---
def transfer_contour(src_points, dst_points, tgt_points, mode='affine_residual'):
	'''End-to-end per-contour transfer: fit src->dst, reproduce on tgt.

	This is the function intended for callers (e.g. FontLab scripts).
	Handles centroid extraction, bbox extraction, residual, and
	apply_transfer in one call.

	Args:
	    src_points: iterable of (x, y) or Point - the OLD master state
	    dst_points: same length - the NEW master state
	    tgt_points: iterable of (x, y) or Point - the receiver contour
	    mode: 'affine_only' | 'affine_residual' | 'bbox_fallback'

	Returns:
	    (new_tgt_points, info) where
	        new_tgt_points: list of (x, y) tuples, length == len(tgt_points)
	        info: dict with diagnostic fields:
	            rms_residual  - affine fit quality (source units)
	            max_residual  - largest per-point residual magnitude
	                            (source units) - 0 if no residual computed
	            rotation_deg, scale_x, scale_y, shear - from decompose_affine
	            determinant   - of the 2x2 linear part
	'''
	src = [_xy(p) for p in src_points]
	dst = [_xy(p) for p in dst_points]
	tgt = [_xy(p) for p in tgt_points]

	if len(src) != len(dst):
		raise ValueError('transfer_contour: src/dst length mismatch')
	# tgt may differ in length from src/dst only if the caller is doing
	# something unusual; normally compatibility is enforced upstream.

	A, rms = fit_affine(src, dst)
	info = decompose_affine(A)
	info['rms_residual'] = rms
	info['max_residual'] = 0.0

	src_bb = _bbox(src)
	tgt_bb = _bbox(tgt)
	src_c = _centroid(src)
	dst_c = _centroid(dst)
	tgt_c = _centroid(tgt)

	residual = None
	if mode == 'affine_residual':
		residual = compute_residual(src, dst, A, src_bb)
		if residual:
			# Max magnitude in source units (residual is unit-space).
			mx = 0.0
			for rx, ry in residual:
				mag_sq = (rx * src_bb.width) ** 2 + (ry * src_bb.height) ** 2
				if mag_sq > mx:
					mx = mag_sq
			info['max_residual'] = math.sqrt(mx)

	new_tgt = apply_transfer(tgt, A, residual_norm=residual,
	                          tgt_bbox=tgt_bb, src_bbox=src_bb,
	                          src_centroid=src_c, dst_centroid=dst_c,
	                          tgt_centroid=tgt_c, mode=mode)
	return new_tgt, info


# - Self-tests --------------------------
def _approx(a, b, tol=1e-6):
	return abs(a - b) <= tol


def _approx_pt(p, q, tol=1e-6):
	return _approx(p[0], q[0], tol) and _approx(p[1], q[1], tol)


def _make_rect(x, y, w, h):
	# 8 points: 4 corners + 4 midpoints, traversed CCW.
	return [
		(x,         y),
		(x + w / 2, y),
		(x + w,     y),
		(x + w,     y + h / 2),
		(x + w,     y + h),
		(x + w / 2, y + h),
		(x,         y + h),
		(x,         y + h / 2),
	]


def _apply_xform(pts, xform):
	return [xform.applyTransformation(x, y) for (x, y) in pts]


def _test_fit_identity():
	src = _make_rect(0, 0, 100, 100)
	A, rms = fit_affine(src, src)
	assert _approx(rms, 0.0), 'identity rms={}'.format(rms)
	assert _approx(A[0], 1.0) and _approx(A[3], 1.0), 'identity L not I: {}'.format(list(A))
	assert _approx(A[1], 0.0) and _approx(A[2], 0.0), 'identity off-diagonals: {}'.format(list(A))
	assert _approx(A[4], 0.0) and _approx(A[5], 0.0), 'identity translation: {}'.format(list(A))
	print('  identity fit [OK]')


def _test_fit_translation():
	src = _make_rect(10, 20, 100, 50)
	dst = [(x + 30, y - 15) for (x, y) in src]
	A, rms = fit_affine(src, dst)
	assert _approx(rms, 0.0), 'translation rms={}'.format(rms)
	assert _approx(A[4], 30.0, 1e-5), 'dx={}'.format(A[4])
	assert _approx(A[5], -15.0, 1e-5), 'dy={}'.format(A[5])
	print('  pure translation [OK]')


def _test_fit_scale():
	src = _make_rect(0, 0, 100, 100)
	# Scale around origin by (2, 3).
	dst = [(2.0 * x, 3.0 * y) for (x, y) in src]
	A, rms = fit_affine(src, dst)
	assert _approx(rms, 0.0), 'scale rms={}'.format(rms)
	info = decompose_affine(A)
	assert _approx(info['scale_x'], 2.0, 1e-5), 'sx={}'.format(info['scale_x'])
	assert _approx(info['scale_y'], 3.0, 1e-5), 'sy={}'.format(info['scale_y'])
	assert _approx(info['rotation_deg'], 0.0, 1e-4), 'rot={}'.format(info['rotation_deg'])
	print('  pure scale [OK]')


def _test_fit_rotation():
	src = _make_rect(-50, -50, 100, 100)  # centered so rotation has no translation
	angle = 30.0
	c = math.cos(math.radians(angle))
	s = math.sin(math.radians(angle))
	dst = [(c * x - s * y, s * x + c * y) for (x, y) in src]
	A, rms = fit_affine(src, dst)
	assert _approx(rms, 0.0, 1e-5), 'rotation rms={}'.format(rms)
	info = decompose_affine(A)
	assert _approx(info['rotation_deg'], angle, 1e-3), 'rot={}'.format(info['rotation_deg'])
	assert _approx(info['scale_x'], 1.0, 1e-5), 'sx={}'.format(info['scale_x'])
	assert _approx(info['scale_y'], 1.0, 1e-5), 'sy={}'.format(info['scale_y'])
	assert abs(info['shear']) < 1e-5, 'shear={}'.format(info['shear'])
	print('  pure rotation [OK]')


def _test_fit_shear():
	src = _make_rect(-50, -50, 100, 100)
	k = 0.3  # horizontal shear
	dst = [(x + k * y, y) for (x, y) in src]
	A, rms = fit_affine(src, dst)
	assert _approx(rms, 0.0, 1e-5), 'shear rms={}'.format(rms)
	# The input transform has det=1 and a non-zero shear component.
	# Polar decomposition will attribute part to a small rotation and the
	# rest to S; we sanity-check via round-trip, not decomposition values.
	recon = _apply_xform(src, A)
	for p, q in zip(dst, recon):
		assert _approx_pt(p, q, 1e-4), 'shear roundtrip: {} vs {}'.format(p, q)
	print('  pure shear roundtrip [OK]')


def _test_fit_combined():
	src = _make_rect(10, 20, 80, 60)
	# Combine rotation, scale, translation.
	angle = 20.0
	c = math.cos(math.radians(angle))
	s = math.sin(math.radians(angle))
	sx, sy = 1.5, 0.75
	tx, ty = 40.0, -10.0
	dst = [(sx * (c * x - s * y) + tx, sy * (s * x + c * y) + ty) for (x, y) in src]
	A, rms = fit_affine(src, dst)
	assert _approx(rms, 0.0, 1e-4), 'combined rms={}'.format(rms)
	recon = _apply_xform(src, A)
	for p, q in zip(dst, recon):
		assert _approx_pt(p, q, 1e-3), 'combined roundtrip: {} vs {}'.format(p, q)
	print('  combined affine roundtrip [OK]')


def _test_fit_degenerate_collinear():
	src = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
	dst = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
	try:
		fit_affine(src, dst)
	except ValueError:
		print('  collinear -> ValueError [OK]')
		return
	raise AssertionError('expected ValueError on collinear src')


def _test_residual_sculpted():
	# Take a scale change and add a localised bump on one node.
	src = _make_rect(0, 0, 100, 100)
	dst = [(2.0 * x, 2.0 * y) for (x, y) in src]
	# Bump node 4 (top-right) outward by (10, 5) - this is non-affine.
	bump_idx = 4
	dst[bump_idx] = (dst[bump_idx][0] + 10.0, dst[bump_idx][1] + 5.0)

	A, rms = fit_affine(src, dst)
	assert rms > 0.5, 'expected non-zero rms for non-affine input, got {}'.format(rms)

	src_bb = _bbox(src)
	residual = compute_residual(src, dst, A, src_bb)

	# Most residuals should be small; the bump node should dominate.
	mags = [math.hypot(rx, ry) for (rx, ry) in residual]
	assert mags[bump_idx] == max(mags), 'bump should be largest residual'

	# Reapplying (affine + residual) on src should exactly recover dst.
	recon = apply_transfer(src, A, residual,
	                       tgt_bbox=src_bb, src_bbox=src_bb,
	                       mode='affine_residual')
	for p, q in zip(dst, recon):
		assert _approx_pt(p, q, 1e-4), 'reapply src: {} vs {}'.format(p, q)
	print('  residual captures sculpted bump [OK]')


def _test_transfer_scale_to_light():
	# src: Regular rect; dst: Regular scaled to 2x around its centroid.
	# tgt: Light rect at a different position, smaller.
	# Expected: Light scales 2x around its own centroid.
	src = _make_rect(100, 100, 100, 100)    # centroid (150, 150)
	dst = [(150 + 2.0 * (x - 150), 150 + 2.0 * (y - 150)) for (x, y) in src]
	tgt = _make_rect(500, 500, 50, 50)      # centroid (525, 525)

	A, _ = fit_affine(src, dst)
	src_bb = _bbox(src)
	tgt_bb = _bbox(tgt)
	out = apply_transfer(tgt, A, residual_norm=None,
	                     tgt_bbox=tgt_bb, src_bbox=src_bb,
	                     mode='affine_only')

	# Expected: Light doubles around (525, 525) and NO extra shift, because
	# src and dst centroids coincide (both at 150,150 thanks to how we
	# constructed dst).
	expected = [(525 + 2.0 * (x - 525), 525 + 2.0 * (y - 525)) for (x, y) in tgt]
	for p, q in zip(expected, out):
		assert _approx_pt(p, q, 1e-3), 'scale-transfer: {} vs {}'.format(p, q)
	print('  scale-around-centroid transfers to tgt [OK]')


def _test_transfer_translation_to_light():
	# src -> dst is pure translation; Light should shift by the same delta.
	src = _make_rect(100, 100, 100, 100)
	dst = [(x + 40, y - 25) for (x, y) in src]
	tgt = _make_rect(500, 500, 50, 50)

	A, _ = fit_affine(src, dst)
	src_bb = _bbox(src)
	tgt_bb = _bbox(tgt)
	out = apply_transfer(tgt, A, residual_norm=None,
	                     tgt_bbox=tgt_bb, src_bbox=src_bb,
	                     mode='affine_only')

	expected = [(x + 40, y - 25) for (x, y) in tgt]
	for p, q in zip(expected, out):
		assert _approx_pt(p, q, 1e-3), 'translation-transfer: {} vs {}'.format(p, q)
	print('  pure translation transfers to tgt [OK]')


def _test_transfer_rotation_to_light():
	# src -> dst is rotation around src's own centroid.
	# Expected: Light rotates around Light's own centroid by the same angle.
	src = _make_rect(100, 100, 100, 100)  # centroid (150, 150)
	angle = 30.0
	c = math.cos(math.radians(angle))
	s = math.sin(math.radians(angle))
	dst = [(150 + c * (x - 150) - s * (y - 150),
	        150 + s * (x - 150) + c * (y - 150)) for (x, y) in src]
	tgt = _make_rect(500, 500, 50, 50)    # centroid (525, 525)

	A, _ = fit_affine(src, dst)
	src_bb = _bbox(src)
	tgt_bb = _bbox(tgt)
	out = apply_transfer(tgt, A, residual_norm=None,
	                     tgt_bbox=tgt_bb, src_bbox=src_bb,
	                     mode='affine_only')

	expected = [(525 + c * (x - 525) - s * (y - 525),
	             525 + s * (x - 525) + c * (y - 525)) for (x, y) in tgt]
	for p, q in zip(expected, out):
		assert _approx_pt(p, q, 1e-3), 'rotation-transfer: {} vs {}'.format(p, q)
	print('  rotation transfers around tgt centroid [OK]')


def _test_bbox_fallback_matches_legacy():
	# bbox_fallback mode must strip to diagonal L + centroid delta, which
	# is what the prior rigid-body script computed.
	src = _make_rect(100, 100, 100, 100)
	# Anisotropic scale 1.2 x 0.8 + translation by (10, -5).
	dst = [(150 + 1.2 * (x - 150) + 10,
	        150 + 0.8 * (y - 150) - 5) for (x, y) in src]
	tgt = _make_rect(500, 500, 50, 50)    # centroid (525, 525)

	A, _ = fit_affine(src, dst)
	src_bb = _bbox(src)
	tgt_bb = _bbox(tgt)
	out = apply_transfer(tgt, A, residual_norm=None,
	                     tgt_bbox=tgt_bb, src_bbox=src_bb,
	                     mode='bbox_fallback')

	# Legacy expectation: scale around tgt centroid + translate by (10, -5).
	expected = [(525 + 1.2 * (x - 525) + 10,
	             525 + 0.8 * (y - 525) - 5) for (x, y) in tgt]
	for p, q in zip(expected, out):
		assert _approx_pt(p, q, 1e-3), 'bbox-fallback: {} vs {}'.format(p, q)
	print('  bbox_fallback matches legacy rigid-body [OK]')


def _test_transfer_contour_pipeline():
	# End-to-end: rotation + bump in src->dst, applied to a Light tgt.
	src = _make_rect(100, 100, 100, 100)
	angle = 15.0
	c = math.cos(math.radians(angle))
	s = math.sin(math.radians(angle))
	dst = [(150 + c * (x - 150) - s * (y - 150),
	        150 + s * (x - 150) + c * (y - 150)) for (x, y) in src]
	# Add a small bump on node 2.
	dst[2] = (dst[2][0] + 3.0, dst[2][1] + 4.0)

	tgt = _make_rect(500, 500, 50, 50)

	out, info = transfer_contour(src, dst, tgt, mode='affine_residual')
	assert len(out) == len(tgt)
	assert info['rms_residual'] > 0.0, 'non-affine input must have rms>0'
	assert info['max_residual'] > 0.0
	assert abs(info['rotation_deg'] - angle) < 1.0, 'rotation ~15 deg, got {}'.format(info['rotation_deg'])
	print('  transfer_contour end-to-end [OK]')


def _run_tests():
	print('design_transfer - Stage 1 kernel tests:')
	_test_fit_identity()
	_test_fit_translation()
	_test_fit_scale()
	_test_fit_rotation()
	_test_fit_shear()
	_test_fit_combined()
	_test_fit_degenerate_collinear()
	_test_residual_sculpted()
	_test_transfer_translation_to_light()
	_test_transfer_scale_to_light()
	_test_transfer_rotation_to_light()
	_test_bbox_fallback_matches_legacy()
	_test_transfer_contour_pipeline()
	print('design_transfer: all tests passed.')


if __name__ == '__main__':
	_run_tests()
