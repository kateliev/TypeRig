# MODULE: TypeRig / Core / Algo / CJK
# -----------------------------------------------------------
# Pure-python CJK design analysis and per-glyph measurement.
# NO FontLab, NO Qt, NO numpy — everything takes plain lists /
# numbers in and returns numbers out, so the whole pipeline is
# importable and unit-testable outside FontLab (see test_cjk.py).
#
# Consolidated from the Project Ganying Balance Probe (probe.py)
# and Advanced Clipboard (IDC slot model). This is the single
# home for the mass/centroid, central-palace, face, white-
# evenness, valley-split, composition-moment and IDC-structure
# math that was previously duplicated across panels.
#
# Contents:
#   - rasterize_contours()  pure AA scanline raster (the "squint"
#                           blur); matches the Qt bridge's ink
#                           contract so bands/zones stay portable.
#   - Tier 1  glyph_centroid()   signed-area (Green's theorem).
#   - Tier 2  gray_centroid()    centre of mass of the raster.
#   - grids / marginals / central palace / face / kurtosis /
#     white gaps / valley splits / composition moment / quadrant.
#   - IDC positional slot model (idc_slots, IDC_INFO) + the
#     shared ⿰/⿱ boundary_ratio() measurement.
#   - compute_gauges()    normalized, cross-glyph gauge vector.
#   - reduce_ratios()     mean/sd/histogram aggregation.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, division, print_function

import math
from collections import OrderedDict

__version__ = '1.0.0'


# =====================================================================
# - Rasterizer : pure AA scanline (font contours -> ink list) ---------
# =====================================================================
def rasterize_contours(contours, frame, S, samples=4):
	'''Antialiased raster of flattened contours over the em-square frame.

	contours : list[list[(x, y)]] - closed polygons in font units.
	frame    : (x0, y0, x1, y1) font-space band mapped onto the S x S image.
	S        : raster edge length.
	samples  : vertical sub-scanlines per pixel row for AA (horizontal
	           coverage is analytic, so this only refines the y axis).

	returns  : flat list[float] of length S*S, ink = 0..255, row-major with
	           the TOP image row first (row 0 == the ascender / y1). This is
	           the same contract the Qt bridge's rasterize() emits, so gray_
	           centroid / nine_grid / marginals accept either interchangeably.
	           All-zeros for an empty path or a degenerate frame.

	Non-zero winding fill: counters (opposite winding) subtract automatically,
	exactly like the vector centroid, so holes read as white. This is the
	FontLab-free fallback; the Qt path in the proxy bridge is faster but must
	produce the identical layout.
	'''
	ink = [0.0] * (S * S)

	x0, y0, x1, y1 = frame
	fw = x1 - x0
	fh = y1 - y0
	if fw <= 0.0 or fh <= 0.0:
		return ink

	# Map font space -> image space. Image y points down: the top of the image
	# (row 0) corresponds to the ascender (y1).  sx = (x-x0)/fw*S ;  sy = (y1-y)/fh*S
	sxk = S / fw
	syk = S / fh

	# Build edges as (iy0, iy1, ix0, ix1) in image space, dropping horizontals.
	edges = []
	for pts in contours:
		n = len(pts)
		if n < 3:
			continue
		for i in range(n):
			ax, ay = pts[i]
			bx, by = pts[(i + 1) % n]
			iay = (y1 - ay) * syk
			iby = (y1 - by) * syk
			if iay == iby:
				continue
			iax = (ax - x0) * sxk
			ibx = (bx - x0) * sxk
			edges.append((iay, iby, iax, ibx))

	if not edges:
		return ink

	inv = 1.0 / samples
	weight = 255.0 * inv

	for r in range(S):
		row_base = r * S
		for k in range(samples):
			sy = r + (k + 0.5) * inv			# sub-scanline y (image space)
			xs = []								# (x, winding_dir)
			for iay, iby, iax, ibx in edges:
				lo, hi = (iay, iby) if iay < iby else (iby, iay)
				if sy < lo or sy >= hi:
					continue
				t = (sy - iay) / (iby - iay)
				x = iax + t * (ibx - iax)
				xs.append((x, 1 if iby > iay else -1))
			if len(xs) < 2:
				continue
			xs.sort()
			wind = 0
			prev_x = 0.0
			for x, d in xs:
				if wind != 0:
					_add_span(ink, row_base, prev_x, x, weight, S)
				wind += d
				prev_x = x

	# Clamp (overlapping same-winding spans can exceed 255 before clamping).
	for i in range(len(ink)):
		if ink[i] > 255.0:
			ink[i] = 255.0
	return ink


def _add_span(ink, row_base, xa, xb, weight, S):
	'''Add `weight` * horizontal-coverage of the span [xa, xb] to a raster row.
	Fractional pixel coverage at the span ends gives horizontal AA.'''
	if xb <= xa:
		return
	if xa < 0.0:
		xa = 0.0
	if xb > S:
		xb = float(S)
	if xb <= xa:
		return
	c0 = int(math.floor(xa))
	c1 = int(math.floor(xb - 1e-9))
	if c0 == c1:
		ink[row_base + c0] += weight * (xb - xa)
		return
	ink[row_base + c0] += weight * ((c0 + 1) - xa)		# left partial
	for c in range(c0 + 1, c1):
		ink[row_base + c] += weight						# full pixels
	ink[row_base + c1] += weight * (xb - c1)			# right partial


# =====================================================================
# - Tier 1 : vector centroid ------------------------------------------
# =====================================================================
def glyph_centroid(contours):
	'''Signed-area centroid over all flattened contours (Green's theorem).

	contours : list[list[(x, y)]] - closed polygons in font units.
	returns  : (cx, cy) in font units, or None for empty / degenerate input.

	Holes (counters) subtract automatically through the winding sign; do not
	special-case them and do not "fix" an overall-reversed winding - the
	formula yields the correct centroid regardless of total-area sign.
	'''
	A = Cx = Cy = 0.0

	for pts in contours:
		n = len(pts)
		if n < 3:
			continue

		for i in range(n):
			x0, y0 = pts[i]
			x1, y1 = pts[(i + 1) % n]
			cross = x0 * y1 - x1 * y0
			A  += cross
			Cx += (x0 + x1) * cross
			Cy += (y0 + y1) * cross

	if abs(A) < 1e-9:
		return None						# degenerate / empty

	A *= 0.5
	return Cx / (6.0 * A), Cy / (6.0 * A)


# =====================================================================
# - Tier 2 : gray (blurred-raster) centroid ---------------------------
# =====================================================================
def gray_centroid(ink, S, y_weight=1.0):
	'''Centre of mass of an antialiased raster.

	ink      : list of S*S floats, row-major, top row first (image space).
	S        : raster edge length.
	y_weight : optional horizontal-vertical illusion correction applied to
	           Tier 2 only (default 1.05 in the panel, range 1.00-1.10).

	returns  : (col, row) in *image* fractional cell units - col left->right,
	           row bottom->top (already flipped back to font orientation) -
	           or None for an empty raster. Feed the result to image_to_font()
	           to obtain font units.
	'''
	m = mx = my = 0.0

	for r in range(S):
		y  = (S - 1 - r)				# flip back to font-space orientation
		wy = y * y_weight
		row = r * S

		for c in range(S):
			v = ink[row + c]
			if v:
				m  += v
				mx += v * c
				my += v * wy

	if m == 0.0:
		return None

	return mx / m, (my / (m * y_weight))


# =====================================================================
# - Grid mass readout -------------------------------------------------
# =====================================================================
def grid_mass(ink, S, n):
	'''n x n partition of the raster.

	returns (cells, imbalance) where:
	  cells     : list of n*n floats, row-major *top row first* (image order),
	              normalized to sum 1.0 (all zeros if the raster is empty).
	  imbalance : max_cell / min_nonzero_cell, or 0.0 if empty / single cell.
	'''
	cells = [0.0] * (n * n)

	for r in range(S):
		gr = (r * n) // S				# row band, top->bottom in image space
		row = r * S
		base = gr * n

		for c in range(S):
			v = ink[row + c]
			if v:
				gc = (c * n) // S		# col band, left->right
				cells[base + gc] += v

	total = sum(cells)

	if total <= 0.0:
		return cells, 0.0

	cells = [v / total for v in cells]

	nonzero = [v for v in cells if v > 0.0]
	imbalance = (max(cells) / min(nonzero)) if len(nonzero) > 1 else 0.0

	return cells, imbalance


def nine_grid(ink, S):
	'''3x3 grid mass + imbalance. The semantic 中宫 partition (centre cell is
	cells[4]); kept fixed for palace-fill / imbalance regardless of the heat
	visual's resolution.'''
	return grid_mass(ink, S, 3)


# =====================================================================
# - Central palace (中宫) — elastic-mesh separators -------------------
# =====================================================================
# Sun et al. 2015 (IJCAI), features f12-f17: the positions of 3 separators
# that split the ink histogram into 4 equal-mass quarters. A perfectly uniform
# glyph yields separators at 25/50/75%; a top- or left-crowded glyph bunches
# them. Far more sensitive to *where* mass sits than the global centroid.

def _quartile_separators(hist):
	'''Positions (fraction 0..1) splitting a 1-D mass histogram into quarters.

	hist : list of bin masses, ordered low->high along the axis.
	returns [p25, p50, p75] as fractions of the axis length, or None if empty.
	Linear interpolation within the crossing bin gives sub-bin precision.
	'''
	total = sum(hist)
	if total <= 0.0:
		return None

	n       = len(hist)
	targets = (0.25, 0.50, 0.75)
	seps    = []
	acc     = 0.0
	ti      = 0

	for i in range(n):
		prev = acc
		acc += hist[i]
		while ti < 3 and acc >= targets[ti] * total:
			need    = targets[ti] * total - prev
			frac_in = (need / hist[i]) if hist[i] > 0.0 else 0.0
			seps.append((i + frac_in) / n)
			ti += 1

	while len(seps) < 3:
		seps.append(seps[-1] if seps else 0.5)

	return seps


# - Shared marginals (compute once per refresh, pass via marg=) -------
def marginals(ink, S):
	'''Column- and row-mass histograms of the raster.

	returns (col, row): col[c] = ink summed down column c (left->right),
	row[r] = ink summed across row r (image order, TOP row first). Many gauges
	read only these, so callers compute them once and share them.
	'''
	col = [0.0] * S
	row = [0.0] * S
	for r in range(S):
		base = r * S
		rsum = 0.0
		for c in range(S):
			v = ink[base + c]
			if v:
				col[c] += v
				rsum   += v
		row[r] = rsum
	return col, row


def _cum_pos(hist, target):
	'''Fractional index where the cumulative sum of hist first reaches target.
	Linear interpolation within the crossing bin; clamps to len(hist).
	'''
	acc = 0.0
	for i in range(len(hist)):
		prev = acc
		acc += hist[i]
		# Only an in-mass bin can be the crossing - skip leading/empty bins so a
		# zero target lands on the first ink cell, not index 0.
		if acc >= target and acc > prev:
			frac = (target - prev) / hist[i]
			return i + frac
	return float(len(hist))


def central_palace(ink, S, marg=None):
	'''Elastic-mesh separators for the raster.

	returns (vseps, hseps), each [p25, p50, p75] fractions (or None):
	  vseps - vertical separators, left->right (column-mass histogram).
	  hseps - horizontal separators, bottom->top (row-mass histogram, flipped
	          from image order so it reads in font orientation).
	'''
	col, row = marg if marg is not None else marginals(ink, S)
	vseps = _quartile_separators(col)
	hseps = _quartile_separators(row[::-1])			# image-top first -> bottom->top
	return vseps, hseps


def central_palace_uniformity(vseps, hseps):
	'''Single 0..1 score: 1.0 = separators exactly at the even quartiles.

	Mean absolute deviation of the 6 separators from (0.25, 0.5, 0.75),
	scaled so a deviation of 0.25 (a fully crowded glyph) maps to ~0.
	'''
	ideal = (0.25, 0.50, 0.75)
	devs  = []
	for seps in (vseps, hseps):
		if seps:
			devs.extend(abs(s - i) for s, i in zip(seps, ideal))

	if not devs:
		return None

	mad = sum(devs) / len(devs)
	return max(0.0, 1.0 - mad / 0.25)


# =====================================================================
# - Face (字面) -------------------------------------------------------
# =====================================================================
def face_frame(ink, S, q=0.005, marg=None):
	'''Robust letter-face extent in image coords.

	Trims hairline outliers by taking the [q, 1-q] mass quantiles of each
	marginal. returns (c0, r0, c1, r1) image coords (c0<c1 cols left->right,
	r0<r1 rows top->bottom), or None if there is no ink.
	'''
	col, row = marg if marg is not None else marginals(ink, S)
	total = sum(col)
	if total <= 0.0:
		return None
	c0 = _cum_pos(col, q * total)
	c1 = _cum_pos(col, (1.0 - q) * total)
	r0 = _cum_pos(row, q * total)
	r1 = _cum_pos(row, (1.0 - q) * total)
	return (c0, r0, c1, r1)


def face_rate(face, S):
	'''(linear, area) face rate as fractions of the em band, or None.

	linear = mean(face_w/band_w, face_h/band_h) ; area = face_w*face_h / band^2.
	'''
	if face is None:
		return None
	c0, r0, c1, r1 = face
	fw = (c1 - c0) / S
	fh = (r1 - r0) / S
	return ((fw + fh) / 2.0, fw * fh)


def contour_bbox(contours):
	'''Exact vector bbox of all contour points: (x0, y0, x1, y1) or None.'''
	xs0 = ys0 = xs1 = ys1 = None
	for pts in contours:
		for x, y in pts:
			if xs0 is None or x < xs0: xs0 = x
			if xs1 is None or x > xs1: xs1 = x
			if ys0 is None or y < ys0: ys0 = y
			if ys1 is None or y > ys1: ys1 = y
	if xs0 is None:
		return None
	return (xs0, ys0, xs1, ys1)


# =====================================================================
# - Palace tightness (中宫 as kurtosis) ------------------------------
# =====================================================================
def _excess_kurtosis(w):
	'''Excess kurtosis of a 1-D weight distribution over positions 0..n-1.
	None if total weight or variance is degenerate. Uniform -> ~ -1.2.
	'''
	tot = sum(w)
	if tot <= 0.0:
		return None
	n = len(w)
	mean = 0.0
	for i in range(n):
		mean += i * w[i]
	mean /= tot
	var = m4 = 0.0
	for i in range(n):
		d  = i - mean
		d2 = d * d
		var += w[i] * d2
		m4  += w[i] * d2 * d2
	var /= tot
	m4  /= tot
	if var < 1e-9:
		return None
	return m4 / (var * var) - 3.0


def marginal_kurtosis(ink, S, marg=None):
	'''(Kx, Ky) excess kurtosis of the column / row marginals. Either may be
	None if degenerate. Lower (more negative) = flatter = more open palace.
	'''
	col, row = marg if marg is not None else marginals(ink, S)
	return _excess_kurtosis(col), _excess_kurtosis(row)


# =====================================================================
# - White evenness (アキ均等) ----------------------------------------
# =====================================================================
def _cv(xs):
	'''Coefficient of variation (population stdev / mean) of a list, 0 if empty.'''
	n = len(xs)
	if n == 0:
		return 0.0
	m = sum(xs) / n
	if m <= 0.0:
		return 0.0
	var = sum((x - m) ** 2 for x in xs) / n
	return (var ** 0.5) / m


def _interior_gaps(values, lo, hi, cut):
	'''Lengths of white runs strictly between the first and last ink cell in
	values[lo:hi] (ink = value > cut). [] if fewer than two ink cells.
	'''
	first = last = None
	for k in range(lo, hi):
		if values[k] > cut:
			if first is None:
				first = k
			last = k
	if first is None or last <= first:
		return []
	gaps = []
	run = 0
	for k in range(first + 1, last):
		if values[k] > cut:
			if run > 0:
				gaps.append(run)
				run = 0
		else:
			run += 1
	return gaps


def white_gap_stats(ink, S, face, thresh=0.5):
	'''Uniformity of interior white gaps inside the face (Jiyukobo "even white").

	returns (cv_h, cv_v, worst_rows, worst_cols):
	  cv_h/cv_v - CV of all horizontal / vertical interior gap lengths
	              (None if fewer than 4 gaps on that axis).
	  worst_*   - up to 2 scanline indices with the highest own-gap CV.
	None if face is None.
	'''
	if face is None:
		return None
	c0, r0, c1, r1 = face
	ci0 = max(0, int(math.floor(c0)))
	ci1 = min(S, int(math.ceil(c1)))
	ri0 = max(0, int(math.floor(r0)))
	ri1 = min(S, int(math.ceil(r1)))
	cut = thresh * 255.0

	h_gaps, row_cv = [], []
	for r in range(ri0, ri1):
		base = r * S
		gaps = _interior_gaps(ink, base + ci0, base + ci1, cut)
		if gaps:
			h_gaps.extend(gaps)
			row_cv.append((_cv(gaps), r))

	# Column scan: build a strided view per column.
	v_gaps, col_cv = [], []
	for c in range(ci0, ci1):
		colvals = [ink[r * S + c] for r in range(ri0, ri1)]
		gaps = _interior_gaps(colvals, 0, len(colvals), cut)
		if gaps:
			v_gaps.extend(gaps)
			col_cv.append((_cv(gaps), c))

	cv_h = _cv(h_gaps) if len(h_gaps) >= 4 else None
	cv_v = _cv(v_gaps) if len(v_gaps) >= 4 else None
	worst_rows = [r for _cv_val, r in sorted(row_cv, reverse=True)[:2]]
	worst_cols = [c for _cv_val, c in sorted(col_cv, reverse=True)[:2]]
	return (cv_h, cv_v, worst_rows, worst_cols)


# =====================================================================
# - Second center line (第二中心线) ----------------------------------
# =====================================================================
def _centroid_area(contours, indices=None):
	'''Signed area and centroid (Green) over a subset of contours.
	returns (signed_area, cx, cy) or None if degenerate.
	'''
	idxs = range(len(contours)) if indices is None else indices
	A = Cx = Cy = 0.0
	for k in idxs:
		pts = contours[k]
		n = len(pts)
		if n < 3:
			continue
		for i in range(n):
			x0, y0 = pts[i]
			x1, y1 = pts[(i + 1) % n]
			cross = x0 * y1 - x1 * y0
			A  += cross
			Cx += (x0 + x1) * cross
			Cy += (y0 + y1) * cross
	if abs(A) < 1e-9:
		return None
	A *= 0.5
	return (A, Cx / (6.0 * A), Cy / (6.0 * A))


def component_axes(contours, groups):
	'''Per component group: (mass, cx, cy) via signed-area centroid.
	mass = abs(signed area). Groups that are degenerate are skipped.
	'''
	out = []
	for grp in groups:
		res = _centroid_area(contours, grp)
		if res is None:
			continue
		A, cx, cy = res
		out.append((abs(A), cx, cy))
	return out


def composition_moment(axes, center, span, axis='x'):
	'''Lever balance of components about a center line (Xie & Chen 天平 model).

	axes   - list of (mass, cx, cy).
	center - the center-line coordinate (font units) on the chosen axis.
	span   - normalizing length (band width or height) in font units.
	returns dimensionless M = Σ m·(coord-center) / (Σ m · span), or None.
	'''
	if not axes or span <= 0.0:
		return None
	num = den = 0.0
	for m, cx, cy in axes:
		coord = cx if axis == 'x' else cy
		num += m * (coord - center)
		den += m
	if den <= 0.0:
		return None
	return num / (den * span)


def _deepest_valley(hist, lo, hi):
	'''Deepest interior valley in hist[lo..hi] (inclusive) whose prominence
	exceeds 0.35 * mean non-zero bin, else None. Shared by valley_split (mass
	window) and valley_split_face (positional window).'''
	if hi - lo < 2:
		return None

	vmin = vpos = None
	for c in range(lo, hi + 1):
		if vmin is None or hist[c] < vmin:
			vmin, vpos = hist[c], c

	peak_l = max(hist[lo:vpos + 1]) if vpos > lo else hist[vpos]
	peak_r = max(hist[vpos:hi + 1]) if vpos < hi else hist[vpos]
	depth  = min(peak_l, peak_r) - vmin

	nonzero = [x for x in hist if x > 0.0]
	mean_marg = (sum(nonzero) / len(nonzero)) if nonzero else 0.0
	if depth < 0.35 * mean_marg:
		return None
	return vpos


def valley_split(hist):
	'''Deepest interior valley of a 1-D mass histogram between its 25% and 75%
	mass quantiles. returns the split index, or None if the dip is too shallow
	(prominence < 0.35 * mean non-zero bin) to be a real division. Axis-agnostic:
	feed a column marginal for a left/right split, a row marginal for top/bottom.
	'''
	total = sum(hist)
	if total <= 0.0:
		return None
	lo = int(math.ceil(_cum_pos(hist, 0.25 * total)))
	hi = int(math.floor(_cum_pos(hist, 0.75 * total)))
	return _deepest_valley(hist, lo, hi)


def valley_split_face(hist, lo, hi, margin=0.12):
	'''Deepest valley within a POSITIONAL window [lo, hi] (bin indices, e.g. the
	face extent), inset by `margin` of the span. Unlike valley_split this does NOT
	depend on the mass distribution, so it finds the true component gap even when
	one part carries far more ink than the other — the usual case for vertical
	(⿱) CJK where the mass-quantile window drifts toward the heavier part and
	misses (or mis-places) the boundary. Used for IDC split measurement.
	'''
	lo = int(math.ceil(lo))
	hi = int(math.floor(hi))
	span = hi - lo
	if span < 2:
		return None
	a = lo + int(round(margin * span))
	b = hi - int(round(margin * span))
	if b - a < 2:
		a, b = lo, hi
	return _deepest_valley(hist, a, b)


def split_by_projection_valley(ink, S, marg=None):
	'''Left/right split column via the column-marginal valley (see valley_split).
	Kept as the T5 entry point; delegates to the axis-agnostic valley_split.
	'''
	col, _row = marg if marg is not None else marginals(ink, S)
	return valley_split(col)


def split_components(col, split):
	'''Two pseudo-components from a column marginal split at `split`.
	returns [(mass_L, cx_L), (mass_R, cx_R)] with cx in image-column units.
	'''
	mL = sum(col[:split])
	mR = sum(col[split:])
	cxL = (sum(c * col[c] for c in range(split)) / mL) if mL > 0.0 else split / 2.0
	cxR = (sum(c * col[c] for c in range(split, len(col))) / mR) if mR > 0.0 else float(split)
	return [(mL, cxL), (mR, cxR)]


# =====================================================================
# - Quadrant balance --------------------------------------------------
# =====================================================================
def quadrant_balance(ink, S):
	'''Ink fractions per half/quadrant, split at the raster centre.

	returns dict with left/right/top/bottom fractions (sum L+R = T+B = 1) and
	quad = (TL, TR, BL, BR) fractions in *image* orientation (top = visual top),
	or None for an empty raster. Sensitive to asymmetry the centroid averages out.
	'''
	half = S / 2.0
	left = right = top = bottom = 0.0
	tl = tr = bl = br = 0.0
	total = 0.0

	for r in range(S):
		base   = r * S
		is_top = r < half
		for c in range(S):
			v = ink[base + c]
			if not v:
				continue
			total += v
			is_left = c < half
			if is_left:
				left += v
			else:
				right += v
			if is_top:
				top += v
				if is_left: tl += v
				else:       tr += v
			else:
				bottom += v
				if is_left: bl += v
				else:       br += v

	if total <= 0.0:
		return None

	inv = 1.0 / total
	return {
		'left':   left   * inv,
		'right':  right  * inv,
		'top':    top    * inv,
		'bottom': bottom * inv,
		'quad':   (tl * inv, tr * inv, bl * inv, br * inv),
	}


# =====================================================================
# - Coordinate mapping ------------------------------------------------
# =====================================================================
def image_to_font(col, row, S, frame):
	'''Map a Tier 2 image-space result back to font units.

	col, row : output of gray_centroid() (col left->right, row bottom->top).
	S        : raster edge length.
	frame    : (x0, y0, x1, y1) font-space rectangle the raster covers
	           (the em-square frame: x0..x1 = advance band, y0..y1 = desc..asc).

	returns  : (fx, fy) in font units. Cell centres are sampled (+0.5).
	'''
	x0, y0, x1, y1 = frame
	fx = x0 + (col + 0.5) / S * (x1 - x0)
	fy = y0 + (row + 0.5) / S * (y1 - y0)
	return fx, fy


# =====================================================================
# - IDC positional slot model -----------------------------------------
# =====================================================================
# Conventional component slots per Ideographic Description Character, expressed
# as fraction rects (x0, y0, x1, y1) over the design frame, y-UP, 0..1.
#   split (0..1) -> primary division for binary splits (⿰ ⿱)
#   inset (0..1) -> enclosure depth for surrounds
# Ternary IDCs (⿲ ⿳) use equal thirds. The outer/enclosure slot of a surround
# is non-rectangular, so it maps to the FULL frame (the enclosing radical spans
# the writing square); only the inner enclosed slot is a real inset rect.

IDC_SET = set('⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻')

# Only ⿰ and ⿱ carry a single, cleanly measurable projection-valley boundary.
MEASURABLE_IDC = ('⿰', '⿱')

IDC_INFO = OrderedDict([
	('⿰', ('Left / Right', 2)),
	('⿱', ('Above / Below', 2)),
	('⿲', ('Left / Middle / Right', 3)),
	('⿳', ('Above / Middle / Below', 3)),
	('⿴', ('Full surround', 2)),
	('⿵', ('Surround from above', 2)),
	('⿶', ('Surround from below', 2)),
	('⿷', ('Surround from left', 2)),
	('⿸', ('Surround upper-left', 2)),
	('⿹', ('Surround upper-right', 2)),
	('⿺', ('Surround lower-left', 2)),
	('⿻', ('Overlaid', 2)),
])

# IDCs whose adjustable parameter is a binary split (vs. a surround inset).
_IDC_SPLIT_TYPE = set('⿰⿱⿲⿳⿻')


def idc_slots(idc, split=0.5, inset=0.2):
	'''Return the list of fraction rects (x0,y0,x1,y1; y-up, 0..1) for an IDC.

	split -> primary division for binary splits (⿰ ⿱ …); clamped 0.05..0.95.
	inset -> enclosure depth for surrounds (⿴ ⿵ …);      clamped 0.0..0.45.
	'⿰'..'⿻' follow IDC_INFO; '▦' is a free 3×3 grid (split/inset ignored).
	'''
	s = min(0.95, max(0.05, float(split)))
	d = min(0.45, max(0.0, float(inset)))
	t1, t2 = 1.0 / 3.0, 2.0 / 3.0

	if idc == '⿰':	# left | right
		return [(0.0, 0.0, s, 1.0), (s, 0.0, 1.0, 1.0)]
	if idc == '⿱':	# top / bottom (top occupies fraction s of the height)
		return [(0.0, 1.0 - s, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0 - s)]
	if idc == '⿲':	# three columns
		return [(0.0, 0.0, t1, 1.0), (t1, 0.0, t2, 1.0), (t2, 0.0, 1.0, 1.0)]
	if idc == '⿳':	# three rows (top to bottom)
		return [(0.0, t2, 1.0, 1.0), (0.0, t1, 1.0, t2), (0.0, 0.0, 1.0, t1)]
	if idc == '⿴':	# full surround: outer ring (full frame) + inner inset
		return [(0.0, 0.0, 1.0, 1.0), (d, d, 1.0 - d, 1.0 - d)]
	if idc == '⿵':	# surround from above (open bottom) — inner flush to bottom
		return [(0.0, 0.0, 1.0, 1.0), (d, 0.0, 1.0 - d, 1.0 - d)]
	if idc == '⿶':	# surround from below (open top) — inner flush to top
		return [(0.0, 0.0, 1.0, 1.0), (d, d, 1.0 - d, 1.0)]
	if idc == '⿷':	# surround from left (open right) — inner flush to right
		return [(0.0, 0.0, 1.0, 1.0), (d, d, 1.0, 1.0 - d)]
	if idc == '⿸':	# surround upper-left (open lower-right) — inner to lower-right
		return [(0.0, 0.0, 1.0, 1.0), (d, 0.0, 1.0, 1.0 - d)]
	if idc == '⿹':	# surround upper-right (open lower-left) — inner to lower-left
		return [(0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0 - d, 1.0 - d)]
	if idc == '⿺':	# surround lower-left (open upper-right) — inner to upper-right
		return [(0.0, 0.0, 1.0, 1.0), (d, d, 1.0, 1.0)]
	if idc == '⿻':	# overlaid — both span the full frame
		return [(0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)]
	if idc == '▦':	# free 3×3 grid (split/inset ignored; merge cells to taste)
		cells = []
		for r in range(3):			# row 0 = top
			for c in range(3):
				cells.append((c / 3.0, 1.0 - (r + 1) / 3.0, (c + 1) / 3.0, 1.0 - r / 3.0))
		return cells
	return [(0.0, 0.0, 1.0, 1.0)]


def slots_union(slots, selected):
	'''Union bounding rect (x0,y0,x1,y1) of the `selected` slot indices, or None.
	Lets several adjacent slots merge into one paste region (e.g. ⿲ left+middle).'''
	rects = [slots[i] for i in selected if 0 <= i < len(slots)]
	if not rects:
		return None
	return (min(r[0] for r in rects), min(r[1] for r in rects),
			max(r[2] for r in rects), max(r[3] for r in rects))


def boundary_ratio(marg, face, idc):
	'''Measured split of a ⿰ / ⿱ glyph as a fraction of the FACE, or None.

	marg : (col, row) marginals of the glyph raster (see marginals()).
	face : (c0, r0, c1, r1) face extent in image coords (see face_frame()).
	idc  : '⿰' -> left-part width fraction (0..1 across the face width);
	       '⿱' -> top-part  height fraction (0..1 down the face height).

	Uses the positional valley_split_face inside the face window so it locates
	the real component gap even when one part carries far more ink. Returns None
	when there is no clean valley or it falls outside the face core (<=0.05 or
	>=0.95). This is the single implementation shared by the per-glyph Measure
	and the whole-font zones scan.
	'''
	if face is None:
		return None
	col, row = marg
	c0, r0, c1, r1 = face

	if idc == '⿰':
		split = valley_split_face(col, c0, c1)			# column valley (L|R)
		if split is None or c1 - c0 <= 1e-6:
			return None
		ratio = (split - c0) / (c1 - c0)
	elif idc == '⿱':
		split = valley_split_face(row, r0, r1)			# row valley (T/B, image top-first)
		if split is None or r1 - r0 <= 1e-6:
			return None
		ratio = (split - r0) / (r1 - r0)
	else:
		return None

	if ratio <= 0.05 or ratio >= 0.95:					# valley outside the face core
		return None
	return ratio


# =====================================================================
# - Gauge vector (shared by panel z-scores, batch runner, calibrate) --
# =====================================================================
# Gauge keys (all normalized / dimensionless so they compare across glyphs):
GAUGE_KEYS = (
	'vec_dx', 'vec_dy', 'gray_dx', 'gray_dy', 'face_lin', 'face_area',
	'kx', 'ky', 'palace_fill', 'white_cv_h', 'white_cv_v',
	'mesh_v0', 'mesh_v1', 'mesh_v2', 'mesh_h0', 'mesh_h1', 'mesh_h2',
	'D_norm', 'M',
)


def compute_gauges(contours, ink, frame, groups=None, S=48, y_weight=1.05):
	'''Normalized gauge vector for one glyph: {key: float} (finite only).

	contours : list[list[(x, y)]] flattened contours (font units).
	ink      : precomputed raster over `frame` at edge S (rasterize_contours or
	           the Qt bridge). Passed in so the caller controls the raster source.
	frame    : (x0, y0, x1, y1) em-square band.
	groups   : list[list[contour_index]] by component, for the second-line gauge.

	Centroid offsets are normalized by band width/height; mesh separators and
	face rates are already fractions; D is normalized by span; M is dimensionless.
	This makes every gauge directly comparable across glyphs for family/anchor
	bands and live z-scores.
	'''
	x0, y0, x1, y1 = frame
	fw, fh = x1 - x0, y1 - y0
	if fw <= 0.0 or fh <= 0.0:
		return {}

	cxc = (x0 + x1) / 2.0
	cyc = (y0 + y1) / 2.0

	marg = marginals(ink, S)
	out  = {}

	vc = glyph_centroid(contours)
	if vc is not None:
		out['vec_dx'] = (vc[0] - cxc) / fw
		out['vec_dy'] = (vc[1] - cyc) / fh

	g = gray_centroid(ink, S, y_weight)
	if g is not None:
		gx, gy = image_to_font(g[0], g[1], S, frame)
		out['gray_dx'] = (gx - cxc) / fw
		out['gray_dy'] = (gy - cyc) / fh

	face = face_frame(ink, S, marg=marg)
	fr   = face_rate(face, S)
	if fr is not None:
		out['face_lin'], out['face_area'] = fr

	kx, ky = marginal_kurtosis(ink, S, marg=marg)
	if kx is not None: out['kx'] = kx
	if ky is not None: out['ky'] = ky

	cells, _imb = nine_grid(ink, S)
	if cells:
		out['palace_fill'] = cells[4]

	ws = white_gap_stats(ink, S, face)
	if ws is not None:
		if ws[0] is not None: out['white_cv_h'] = ws[0]
		if ws[1] is not None: out['white_cv_v'] = ws[1]

	vseps, hseps = central_palace(ink, S, marg=marg)
	if vseps:
		for i, v in enumerate(vseps): out['mesh_v%d' % i] = v
	if hseps:
		for i, v in enumerate(hseps): out['mesh_h%d' % i] = v

	groups = groups or []
	if len(groups) >= 2:
		axes = component_axes(contours, groups)
		if len(axes) >= 2:
			xs = [a[1] for a in axes]
			ys = [a[2] for a in axes]
			axis   = 'x' if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 'y'
			coords = sorted((a[1] if axis == 'x' else a[2]) for a in axes)
			span   = fw if axis == 'x' else fh
			center = cxc if axis == 'x' else cyc
			if len(coords) == 2:
				out['D_norm'] = (coords[1] - coords[0]) / span
			m = composition_moment(axes, center, span, axis=axis)
			if m is not None:
				out['M'] = m

	return out


# =====================================================================
# - Aggregation (family bands / IDC zones) ----------------------------
# =====================================================================
def stats(values):
	'''(mean, sd, n) of a list of floats; sd is population stdev.'''
	n = len(values)
	if n == 0:
		return (0.0, 0.0, 0)
	mean = sum(values) / n
	var  = sum((v - mean) ** 2 for v in values) / n
	return (mean, var ** 0.5, n)


def reduce_ratios(ratios, hist_bins=10):
	'''mean / sd / min / max / histogram for a list of split ratios, or None.
	Shared reducer for the IDC-zones scan (part-fraction-of-face distributions).'''
	n = len(ratios)
	if n == 0:
		return None
	mean = sum(ratios) / n
	sd   = (sum((v - mean) ** 2 for v in ratios) / n) ** 0.5
	hist = [0] * hist_bins
	for v in ratios:
		b = int(v * hist_bins)
		if b >= hist_bins:
			b = hist_bins - 1
		hist[b] += 1
	return {
		'measured': n,
		'ratio_mean': mean,
		'ratio_sd': sd,
		'ratio_min': min(ratios),
		'ratio_max': max(ratios),
		'hist': hist,
		'hist_edges': [i / hist_bins for i in range(hist_bins + 1)],
	}
