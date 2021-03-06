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