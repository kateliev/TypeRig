# MODULE: TypeRig / Core / Transform (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division, unicode_literals

import math

# - Init --------------------------------
__version__ = '0.26.6'

# - Functions ---------------------------
def lerp(t0, t1, t):
	return (t1 - t0)*t + t0

def compensator(sf, cf, st0, st1):
	b = float(st1)/st0
	try:
		q = float(sf**(cf - 1.) - b)/(1. - b)
	except ZeroDivisionError:
		q = 0
	return q

def timer(sw_c, sw_0, sw_1, fix_boundry=False):
	'''Get Interpolation time for stem value withing given interval.
	Args:
		sw_c -> Float : Target stem value
		sw_0, sw_1 -> Float : Stem values
	Returns:
		t -> Float : Interpolation time
	'''
	if fix_boundry and sw_c == sw_1: sw_1 += 1. # !!! Very crude boundry error fix

	try:
		t = (float(sw_c - sw_0)/(sw_1 - sw_0))*(1,-1)[sw_0 > sw_1] + (0,1)[sw_0 > sw_1]
	except ZeroDivisionError:
		t = 0.

	return t

def adjuster(s, r, t, d, st):
	''' Readjust scale factor based on interpolation time
	Args:
		s -> tuple(tuple((float(width0), float(width1)), (float(height0), float(height1))) : Joined BBox dimensions
		r -> tuple(float(width), float(height) -> Float: Target Width and Height
		t(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
		d(dx, dy) -> tuple((float, float) : Translation X, Y
		st(stx0, stx1, sty0, sty1) -> tuple((float, float, float, float) : Stems widths for weights t0, t1

	Returns:
		tuple(float, float): Readjusted scale factors
	'''
	tx, ty = t 							# Interpolate time tx, ty
	dx, dy = d 							# Translation dx, dy
	stx0, stx1, sty0, sty1 = st 		# Stem Values
	w, h = r 							# Target Width and Height

	w0, w1 = s[0] 						# Widths
	h0, h1 = s[1] 						# Heights

	bx = float(stx1)/stx0				# Stem ratio X
	by = float(sty1)/sty0				# Stem ratio Y
	wtx = lerp(w0, w1, tx)				# Interpolated width
	hty = lerp(h0, h1, ty)				# Interpolated height
	
	spx = (w*(1 - bx) - dx*(1 + bx) + w1 - wtx)/(w1 - bx*wtx)
	spy = (h*(1 - by) - dy*(1 + by) + h1 - hty)/(h1 - by*hty)
	
	return spx, spy

def adjuster_array(v, r, t, d, st):
	''' Readjust scale factor based on interpolation time
	Args:
		v(t0, t1) -> list(tuple((float, float), (float, float))...) : Joined coordinate arrays for both weights
		r -> tuple(float(width), float(height) -> Float: Target Width and Height
		t(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
		d(dx, dy) -> tuple((float, float) : Translation X, Y
		st(stx0, stx1, sty0, sty1) -> tuple((float, float, float, float) : Stems widths for weights t0, t1

	Returns:
		tuple(float, float): Readjusted scale factors
	'''
	# Helper
	diff = lambda l, i: max(l, key=lambda x:x[i])[i] - min(l, key=lambda x:x[i])[i] 

	# Coordinates (x0, y0) (x1, y1)
	v0, v1 = [], []

	for i in v:
		v0.append(i[0])
		v1.append(i[1])

	w0, w1 = diff(v0, 0), diff(v1, 0) 	# Widths
	h0, h1 = diff(v0, 1), diff(v1, 1) 	# Heights

	return adjuster(((w0, w1), (h0, h1)), r, t, d, st)

# -- Adaptive scaling --------------------------------------------
# Based on: A Multiple Master based method for scaling glyphs without changing the stroke characteristics
# By: Tim Ahrens 
# URL: https://remix-tools.com/pdf/Tim_Ahrens_MM_method.pdf

def adaptive_scale(v, s, d, t, c, i, st):
	'''Perform adaptive scaling by keeping the stem/stroke weights
	Args:
		v(t0, t1) -> tuple((float, float), (float, float)) : Joined coordinates for both weights
		s(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
		d(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
		t(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
		c(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		i -> (radians) : Angle of sharing (for italic designs)  
		st(stx0, stx1, sty0, sty1) -> tuple((float, float, float, float) : Stems widths for weights t0, t1

	Returns:
		tuple(float, float): Transformed coordinate data
	'''
	
	# - Init
	v0, v1 = v 						# Coordinates (x0, y0) (x1, y1)
	sx, sy = s 						# Scale X, Y
	dx, dy = d 						# Translate delta X, Y
	tx, ty = t 						# Interpolate time tx, ty
	cx, cy = c 						# Compensation x, y
	stx0, stx1, sty0, sty1 = st 	# Stems values

	# - Calculate
	vtx = lerp(v0[0], v1[0], tx)
	vty = lerp(v0[1], v1[1], ty)
	
	cstx = lerp(stx0, stx1, tx)
	csty = lerp(sty0, sty1, ty)

	qx = compensator(sx, cx, cstx, stx1)
	qy = compensator(sy, cy, csty, sty1)

	ry = sy*(qy*vty + (1 - qy)*v1[1]) + dy
	rx = sx*(qx*(vtx - vty*i) + (1 - qx)*(v1[0] - v1[1]*i)) + ry*i + dx

	return (rx, ry)

def adaptive_scale_array(a, s, d, t, c, i, st):
	'''Perform adaptive scaling by keeping the stem/stroke weights
	Args:
		a(t0, t1) -> list(tuple(float, float), (float, float)) : Joined coordinate arrays for both weights
		s(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
		d(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
		t(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
		c(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		i -> (radians) : Angle of sharing (for italic designs)  
		st(stx0, stx1, sty0, sty1) -> tuple((float, float, float, float) : Stems widths for weights t0, t1

	Returns:
		list(tuple(float, float)): Transformed coordinate data
	'''
	return list(map(lambda a_i: adaptive_scale(a_i, s, d, t, c, i, st), a))

def target_scale_array(a, w, h, d, t, c, i, st):
	'''Perform adaptive scaling by keeping the stem/stroke weights
	Args:
		a(t0, t1) -> list(tuple(float, float), (float, float)) : Joined coordinate arrays for both weights
		s(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
		d(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
		t(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
		c(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		i -> (radians) : Angle of sharing (for italic designs)  
		st(stx0, stx1, sty0, sty1) -> tuple((float, float, float, float) : Stems widths for weights t0, t1

	Returns:
		list(tuple(float, float)): Transformed coordinate data
	'''
	spx, spy = adjuster_array(a, (w, h), t, d, st)
	return list(map(lambda a_i: adaptive_scale(a_i, (spx, spy), d, t, c, i, st), a))

# -- Diagonal correction offset ----------------------------------------
# After naive anisotropic scaling by (sx, sy), diagonal strokes get
# distorted relative to cardinal-direction stems:
#   - Condensing (sx < 1, sy ≈ 1): diagonals get TOO FAT → need thinning
#   - Expanding  (sx > 1, sy ≈ 1): diagonals get TOO THIN → need growing
#
# The correction uses (sx - sy) as driver, so the sign flips naturally:
#   condensing → negative (contract)
#   expanding  → positive (expand)
#
# The angular window sin²(2θ) is zero at cardinals and peaks at 45°,
# ensuring horizontal and vertical strokes are never touched.
#
# Usage: scale naively first, then apply this as offset_outline correction.

def diagonal_correction_offset(theta, sx, sy, stx, sty, intensity=1.0):
	'''Compute the per-side normal offset to correct diagonal stroke weight 
	after naive (sx, sy) scaling.

	Returns a signed distance to offset along the contour normal:
	  positive = expand (thicken stroke)
	  negative = contract (thin stroke)

	The sign depends on the scaling direction:
	  sx < sy (condensing) → negative (thin diagonals that got too fat)
	  sx > sy (expanding)  → positive (grow diagonals that got too thin)
	  sx == sy             → zero (uniform scale, no correction needed)

	The correction is zero at theta=0 and theta=pi/2 (cardinal strokes
	are already correct after naive scaling) and peaks at 45 degrees.

	Args:
		theta (float): Tangent angle in radians (0=horizontal, pi/2=vertical)
		sx, sy (float): Scale factors that were applied (must be > 0)
		stx (float): Horizontal stem width (width of vertical strokes)
		sty (float): Vertical stem width (width of horizontal strokes)
		intensity (float): Correction strength. Default 1.0.
			0.0 = no correction (naive scaling)
			1.0 = standard correction
			>1.0 = amplified correction (for aggressive compensation)
			Typical range: 0.5 to 2.0

	Returns:
		float: Signed offset distance (per side)
	'''
	# Angular window: zero at cardinals, peaks at 45°
	sin_2t = math.sin(2.0 * theta)
	window = sin_2t * sin_2t  # sin²(2θ)

	# Estimated half-width at this angle from stems
	# Geometric interpolation between stem values:
	#   theta=0 (H tangent, H stroke): hw = sty/2
	#   theta=pi/2 (V tangent, V stroke): hw = stx/2
	sin2t = math.sin(theta) ** 2
	cos2t = math.cos(theta) ** 2
	hw = 0.5 * math.exp(sin2t * math.log(max(stx, 1e-6)) 
					   + cos2t * math.log(max(sty, 1e-6)))

	# Correction: proportional to anisotropy, windowed by angle
	return hw * window * intensity * (sx - sy)

# -- Contour orientation analysis ------------------------------------
# PCA-based dominant angle detection for stroke contours.
# Uses the principal component of on-curve node positions to determine
# the overall stroke direction. Works on decomposed stroke contours
# where each closed path represents a single stroke.
#
# Combined with stem adjustment, this enables per-contour weight
# control during DeltaMachine scaling — diagonal strokes get different
# interpolation positions than cardinal strokes.

def contour_dominant_angle(points):
	'''Compute the dominant orientation of a contour via PCA.

	Performs Principal Component Analysis on a set of 2D points
	and returns the angle of the first principal component — the
	direction of maximum variance, which corresponds to the stroke
	direction for decomposed stroke contours.

	Uses the standard 2x2 covariance matrix eigenvector formula:
	  theta = 0.5 * atan2(2 * Cxy, Cxx - Cyy)

	Results:
	  0       -> horizontal stroke
	  pi/4    -> 45° diagonal
	  pi/2    -> vertical stroke
	  -pi/4   -> -45° diagonal

	For nearly isotropic contours (circles, squares), returns 0.

	Args:
		points: list of (x, y) tuples — should be on-curve nodes only,
			off-curve (BCP) nodes would bias the result.

	Returns:
		float: Dominant angle in radians, range [-pi/2, pi/2]
	'''
	n = len(points)

	if n < 2:
		return 0.

	# Centroid
	cx = sum(p[0] for p in points) / n
	cy = sum(p[1] for p in points) / n

	# Covariance matrix elements
	cxx = 0.
	cyy = 0.
	cxy = 0.

	for p in points:
		dx = p[0] - cx
		dy = p[1] - cy
		cxx += dx * dx
		cyy += dy * dy
		cxy += dx * dy

	cxx /= n
	cyy /= n
	cxy /= n

	# Check for degenerate/isotropic case
	diff = cxx - cyy

	if abs(diff) < 1e-10 and abs(cxy) < 1e-10:
		return 0.

	# Angle of first principal component
	# Standard formula for 2x2 symmetric eigenvalue problem
	return 0.5 * math.atan2(2. * cxy, diff)

def adjust_stems_for_angle(target_stx, target_sty, angle, sx, sy, intensity=1.0):
	'''Adjust target stems based on contour orientation and scale direction.

	For diagonal stroke contours, shifts the target stems to compensate
	for the optical distortion caused by anisotropic scaling:

	  Condensing (sx < sy): diagonals appear too fat relative to stems
	    → reduce target stems → DeltaMachine interpolates lighter → thinner
	  
	  Expanding (sx > sy): diagonals appear too thin relative to stems
	    → increase target stems → DeltaMachine interpolates heavier → fatter

	At cardinal angles (0°, 90°), no adjustment is applied.
	At 45°, maximum adjustment is applied.

	Uses log(sx/sy) instead of (sx - sy) for two reasons:
	  1. Naturally gives ~35% more correction to contracting than expanding
	     at the same ratio, compensating for the DeltaMachine asymmetry
	     (reducing stems below the light master extrapolates with diminishing
	     returns, while increasing toward bold interpolates into real data)
	  2. Better normalized — intensity=1.0 gives a useful default correction
	     (about 10% stem shift at 45° for a 0.7x condense)

	Args:
		target_stx (float): Target horizontal stem width
		target_sty (float): Target vertical stem width
		angle (float): Contour dominant angle in radians (from contour_dominant_angle)
		sx (float): Horizontal scale factor being applied
		sy (float): Vertical scale factor being applied
		intensity (float): Correction strength. Default 1.0.
			0.0 = no adjustment (all contours get same stems)
			1.0 = standard adjustment (~10% at 45° for moderate condense)
			2.0 = strong adjustment
			Typical range: 0.5 to 2.0

	Returns:
		tuple(float, float): Adjusted (stx, sty)
	'''
	# Angular window: 0 at cardinals, 1 at 45°
	sin_2a = math.sin(2.0 * angle)
	window = sin_2a * sin_2a  # sin²(2α)

	# Log ratio of scale factors
	# log(sx/sy): negative for condense, positive for expand
	# |log(0.7)| = 0.357 > |log(1.3)| = 0.262 → natural boost for contracting
	ratio = sx / max(sy, 1e-12)
	log_aniso = math.log(max(ratio, 1e-6))

	# Normalization constant: 0.3 chosen so that intensity=1.0 at 45°
	# gives ~10% stem shift for a typical 0.7x condense
	# (0.3 × log(0.7) ≈ -0.107 → 10.7% reduction)
	factor = window * intensity * 0.3 * log_aniso

	# Proportional adjustment to stems
	# Clamp to prevent negative stems at extreme intensity values
	adj_stx = target_stx * (1.0 + factor)
	adj_sty = target_sty * (1.0 + factor)

	return (max(adj_stx, target_stx * 0.1),
			max(adj_sty, target_sty * 0.1))