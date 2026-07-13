# MODULE: TypeRig / Core / Algo / CJK — pure-math tests
# -----------------------------------------------------------
# Stand-alone tests for cjk.py — no FontLab, no Qt needed.
#   cd Lib/typerig/core/algo && python -m pytest test_cjk.py
# (or just `python test_cjk.py` to run the asserts directly)
# -----------------------------------------------------------

from __future__ import absolute_import, division

try:
	from typerig.core.algo import cjk				# installed / on sys.path
except Exception:
	import os, sys
	sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
	import cjk


def _close(a, b, tol=1e-6):
	return abs(a - b) <= tol


# - Tier 1 : vector centroid ------------------------------------------
def test_square_centroid():
	sq = [(0, 0), (100, 0), (100, 100), (0, 100)]
	cx, cy = cjk.glyph_centroid([sq])
	assert _close(cx, 50.0) and _close(cy, 50.0)


def test_square_with_hole_centroid():
	outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
	hole  = [(25, 25), (25, 75), (75, 75), (75, 25)]	# reversed winding
	cx, cy = cjk.glyph_centroid([outer, hole])
	assert _close(cx, 50.0) and _close(cy, 50.0)


def test_offset_ring_centroid():
	outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
	hole  = [(10, 10), (10, 40), (40, 40), (40, 10)]	# CW
	cx, cy = cjk.glyph_centroid([outer, hole])
	assert cx > 50.0 and cy > 50.0


def test_empty_centroid_is_none():
	assert cjk.glyph_centroid([]) is None
	assert cjk.glyph_centroid([[(10, 10)]]) is None		# single point


# - Tier 2 : gray centroid + nine-grid --------------------------------
def _solid_ink(S):
	return [255.0] * (S * S)


def test_gray_centroid_centre_of_solid():
	S = 6
	col, row = cjk.gray_centroid(_solid_ink(S), S, y_weight=1.0)
	assert _close(col, (S - 1) / 2.0) and _close(row, (S - 1) / 2.0)


def test_gray_centroid_empty_is_none():
	S = 4
	assert cjk.gray_centroid([0.0] * (S * S), S) is None


def test_gray_centroid_left_heavy():
	S = 8
	ink = [0.0] * (S * S)
	for r in range(S):
		for c in range(S // 2):
			ink[r * S + c] = 255.0
	col, _ = cjk.gray_centroid(ink, S)
	assert col < (S - 1) / 2.0


def test_nine_grid_sums_to_one():
	S = 6
	cells, imb = cjk.nine_grid(_solid_ink(S), S)
	assert _close(sum(cells), 1.0)
	assert _close(imb, 1.0, tol=1e-6)


def test_nine_grid_empty():
	S = 6
	cells, imb = cjk.nine_grid([0.0] * (S * S), S)
	assert sum(cells) == 0.0 and imb == 0.0


def test_grid_mass_generalizes():
	S = 8
	for n in (3, 4, 6, 8):
		cells, _imb = cjk.grid_mass(_solid_ink(S), S, n)
		assert len(cells) == n * n
		assert _close(sum(cells), 1.0)
	ink = _fill_rect(_blank(S), S, 0, S // 2, 0, S)
	cells, _ = cjk.grid_mass(ink, S, 4)
	left_col  = sum(cells[r * 4 + 0] for r in range(4))
	right_col = sum(cells[r * 4 + 3] for r in range(4))
	assert left_col > right_col


# - Central palace (中宫) ---------------------------------------------
def test_central_palace_uniform():
	S = 12
	vseps, hseps = cjk.central_palace(_solid_ink(S), S)
	for seps in (vseps, hseps):
		assert _close(seps[0], 0.25, 0.06)
		assert _close(seps[1], 0.50, 0.06)
		assert _close(seps[2], 0.75, 0.06)
	assert cjk.central_palace_uniformity(vseps, hseps) > 0.9


def test_central_palace_left_crowded():
	S = 12
	ink = [0.0] * (S * S)
	for r in range(S):
		for c in range(S // 4):
			ink[r * S + c] = 255.0
	vseps, _ = cjk.central_palace(ink, S)
	assert vseps[1] < 0.40


def test_central_palace_empty():
	S = 8
	v, h = cjk.central_palace([0.0] * (S * S), S)
	assert v is None and h is None
	assert cjk.central_palace_uniformity(v, h) is None


# - Quadrant balance --------------------------------------------------
def test_quadrant_uniform():
	S = 8
	qb = cjk.quadrant_balance(_solid_ink(S), S)
	assert _close(qb['left'], 0.5) and _close(qb['right'], 0.5)
	assert _close(qb['top'], 0.5) and _close(qb['bottom'], 0.5)


def test_quadrant_left_heavy():
	S = 8
	ink = [0.0] * (S * S)
	for r in range(S):
		for c in range(S // 2):
			ink[r * S + c] = 255.0
	qb = cjk.quadrant_balance(ink, S)
	assert qb['left'] > qb['right']


def test_quadrant_empty():
	S = 8
	assert cjk.quadrant_balance([0.0] * (S * S), S) is None


# - synthetic raster builders -----------------------------------------
def _blank(S):
	return [0.0] * (S * S)


def _fill_rect(ink, S, c0, c1, r0, r1, val=255.0):
	for r in range(r0, r1):
		for c in range(c0, c1):
			ink[r * S + c] = val
	return ink


# - Face --------------------------------------------------------------
def test_face_frame_full_ink():
	S = 16
	face = cjk.face_frame(_solid_ink(S), S, q=0.0)
	c0, r0, c1, r1 = face
	assert _close(c0, 0.0, 0.5) and _close(c1, S, 0.5)
	assert _close(r0, 0.0, 0.5) and _close(r1, S, 0.5)


def test_face_rate_half_box():
	S = 16
	ink = _fill_rect(_blank(S), S, S // 4, 3 * S // 4, S // 4, 3 * S // 4)
	lin, area = cjk.face_rate(cjk.face_frame(ink, S, q=0.0), S)
	assert _close(lin, 0.5, 0.08) and _close(area, 0.25, 0.08)


def test_face_outward_scale_raises_rate():
	S = 24
	small = _fill_rect(_blank(S), S, 9, 15, 9, 15)
	big   = _fill_rect(_blank(S), S, 7, 17, 7, 17)
	ls, _ = cjk.face_rate(cjk.face_frame(small, S, q=0.0), S)
	lb, _ = cjk.face_rate(cjk.face_frame(big, S, q=0.0), S)
	assert lb > ls


def test_face_empty():
	S = 8
	assert cjk.face_frame(_blank(S), S) is None
	assert cjk.face_rate(None, S) is None


# - Kurtosis ----------------------------------------------------------
def test_kurtosis_uniform_near_minus_1_2():
	S = 16
	kx, ky = cjk.marginal_kurtosis(_solid_ink(S), S)
	assert _close(kx, -1.2, 0.15) and _close(ky, -1.2, 0.15)


def _peaked(S):
	ink = _fill_rect(_blank(S), S, S // 2 - 1, S // 2 + 1, 0, S, 255.0)
	_fill_rect(ink, S, 0, S, S // 2, S // 2 + 1, 40.0)
	return ink


def _bimodal(S):
	ink = _fill_rect(_blank(S), S, 2, S // 3, 0, S, 255.0)
	_fill_rect(ink, S, 2 * S // 3, S - 2, 0, S, 255.0)
	return ink


def test_kurtosis_peaked_positive():
	S = 32
	kx, _ = cjk.marginal_kurtosis(_peaked(S), S)
	assert kx > 0.0


def test_kurtosis_open_vs_tight_ordering():
	S = 32
	kt, _ = cjk.marginal_kurtosis(_peaked(S), S)
	ko, _ = cjk.marginal_kurtosis(_bimodal(S), S)
	assert ko < kt
	assert ko < -1.0


# - White evenness ----------------------------------------------------
def test_white_cv_rises_when_crowded_while_centroid_holds():
	S = 40
	even = _blank(S)
	for c in (10, 20, 30):
		_fill_rect(even, S, c, c + 2, 4, S - 4)
	crowd = _blank(S)
	for c in (10, 20, 25):
		_fill_rect(crowd, S, c, c + 2, 4, S - 4)

	face_e = cjk.face_frame(even, S, q=0.0)
	face_c = cjk.face_frame(crowd, S, q=0.0)
	cvh_e = cjk.white_gap_stats(even, S, face_e)[0]
	cvh_c = cjk.white_gap_stats(crowd, S, face_c)[0]
	assert cvh_e is not None and cvh_c is not None
	assert cvh_c > cvh_e * 1.5

	def rects_to_contours(cols):
		out = []
		for c in cols:
			out.append([(c, 4), (c + 2, 4), (c + 2, S - 4), (c, S - 4)])
		return out
	ce = cjk.glyph_centroid(rects_to_contours([10, 20, 30]))
	cc = cjk.glyph_centroid(rects_to_contours([10, 20, 25]))
	assert abs(cc[0] - ce[0]) < 3.0


def test_white_gap_empty():
	S = 8
	assert cjk.white_gap_stats(_blank(S), S, None) is None


# - Second center line ------------------------------------------------
def test_component_axes_two_groups():
	left  = [(8, 8), (12, 8), (12, 12), (8, 12)]
	right = [(88, 8), (92, 8), (92, 12), (88, 12)]
	contours = [left, right]
	axes = cjk.component_axes(contours, [[0], [1]])
	assert len(axes) == 2
	assert _close(axes[0][1], 10.0, 0.5) and _close(axes[1][1], 90.0, 0.5)


def test_component_shift_moves_axis_and_moment():
	left  = [(8, 8), (12, 8), (12, 12), (8, 12)]
	right = [(88, 8), (92, 8), (92, 12), (88, 12)]
	right2 = [(108, 8), (112, 8), (112, 12), (108, 12)]
	a1 = cjk.component_axes([left, right],  [[0], [1]])
	a2 = cjk.component_axes([left, right2], [[0], [1]])
	assert _close(a2[0][1], a1[0][1], 0.5)
	assert _close(a2[1][1] - a1[1][1], 20.0, 0.5)
	d1 = a1[1][1] - a1[0][1]
	d2 = a2[1][1] - a2[0][1]
	assert _close(d2 - d1, 20.0, 0.5)
	m1 = cjk.composition_moment(a1, 50.0, 1000.0)
	m2 = cjk.composition_moment(a2, 50.0, 1000.0)
	assert m2 > m1


def test_split_by_valley_two_bars():
	S = 40
	ink = _two_bars(S, gap_cols=10)
	split = cjk.split_by_projection_valley(ink, S)
	assert split is not None and S // 2 - 6 < split < S // 2 + 6
	col = cjk.marginals(ink, S)[0]
	parts = cjk.split_components(col, split)
	assert parts[0][1] < split < parts[1][1]


def _two_bars(S, gap_cols):
	ink = _blank(S)
	left_c = S // 2 - gap_cols // 2 - 2
	_fill_rect(ink, S, left_c, left_c + 2, 2, S - 2)
	right_c = left_c + 2 + gap_cols
	_fill_rect(ink, S, right_c, right_c + 2, 2, S - 2)
	return ink


def test_split_solid_no_valley():
	S = 24
	assert cjk.split_by_projection_valley(_solid_ink(S), S) is None


# - Coordinate mapping ------------------------------------------------
def test_image_to_font_centre():
	S = 48
	frame = (0.0, -200.0, 1000.0, 800.0)
	fx, fy = cjk.image_to_font((S - 1) / 2.0, (S - 1) / 2.0, S, frame)
	assert _close(fx, 500.0, tol=12.0) and _close(fy, 300.0, tol=12.0)


# - Rasterizer (new; pure AA scanline) --------------------------------
def test_rasterize_empty():
	S = 16
	ink = cjk.rasterize_contours([], (0.0, 0.0, 100.0, 100.0), S)
	assert len(ink) == S * S and sum(ink) == 0.0


def test_rasterize_full_square_fills():
	# A square covering the whole frame -> essentially all-ink, centroid centre.
	S = 32
	sq = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink = cjk.rasterize_contours([sq], frame, S)
	# interior pixels are full ink
	assert ink[(S // 2) * S + (S // 2)] > 250.0
	g = cjk.gray_centroid(ink, S)
	assert _close(g[0], (S - 1) / 2.0, 0.6) and _close(g[1], (S - 1) / 2.0, 0.6)


def test_rasterize_hole_subtracts():
	# Square with a centred counter (reversed winding) -> centre pixel is white.
	S = 40
	outer = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
	hole  = [(300, 300), (300, 700), (700, 700), (700, 300)]	# CW hole
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink = cjk.rasterize_contours([outer, hole], frame, S)
	centre = ink[(S // 2) * S + (S // 2)]
	corner = ink[2 * S + 2]			# solid ring
	assert centre < 10.0 and corner > 240.0


def test_rasterize_left_half_marginals():
	# Ink only in the left half of the frame -> column mass concentrated left.
	S = 32
	rect = [(0, 0), (500, 0), (500, 1000), (0, 1000)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink = cjk.rasterize_contours([rect], frame, S)
	col, _row = cjk.marginals(ink, S)
	assert sum(col[:S // 2]) > sum(col[S // 2:]) * 20


def test_rasterize_valley_between_two_bars():
	# Two vertical bars with a gap -> a clean column valley near the gap centre.
	S = 48
	bar_l = [(150, 100), (300, 100), (300, 900), (150, 900)]
	bar_r = [(700, 100), (850, 100), (850, 900), (700, 900)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink = cjk.rasterize_contours([bar_l, bar_r], frame, S)
	split = cjk.split_by_projection_valley(ink, S)
	assert split is not None
	# left bar ends ~col 14, right bar starts ~col 33: split lands in the empty gap.
	assert 14 <= split <= 33


def test_rasterize_area_coverage():
	# Total ink / 255 == fraction of the frame the polygon covers. Catches winding
	# and AA-coverage bugs the shape tests don't quantify.
	S = 64
	frame = (0.0, 0.0, 1000.0, 1000.0)
	def frac(conts):
		return sum(cjk.rasterize_contours(conts, frame, S)) / 255.0 / (S * S)
	rect = [(100, 100), (400, 100), (400, 600), (100, 600)]			# 0.3 x 0.5
	assert _close(frac([rect]), 0.15, 0.005)
	tri = [(0, 0), (1000, 0), (0, 1000)]							# half the frame
	assert _close(frac([tri]), 0.50, 0.01)
	outer = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
	hole  = [(300, 300), (300, 700), (700, 700), (700, 300)]		# 0.16 counter
	assert _close(frac([outer, hole]), 0.84, 0.01)
	clip = [(-500, 0), (500, 0), (500, 1000), (-500, 1000)]			# half outside frame
	assert _close(frac([clip]), 0.50, 0.01)
	cw = [(100, 100), (100, 600), (400, 600), (400, 100)]			# CW winding still fills
	assert _close(frac([cw]), 0.15, 0.005)


# - IDC slot model ----------------------------------------------------
def test_idc_slots_binary_split():
	# ⿰ at split 0.4: left slot is 0..0.4 wide, right is 0.4..1.0.
	slots = cjk.idc_slots('⿰', split=0.4)
	assert len(slots) == 2
	assert _close(slots[0][2], 0.4) and _close(slots[1][0], 0.4)
	# ⿱ top occupies fraction s of the height at the top of the frame.
	top, bot = cjk.idc_slots('⿱', split=0.4)
	assert _close(top[3], 1.0) and _close(top[1], 0.6)		# top band 0.6..1.0
	assert _close(bot[1], 0.0) and _close(bot[3], 0.6)


def test_idc_slots_thirds_and_grid():
	assert len(cjk.idc_slots('⿲')) == 3
	assert len(cjk.idc_slots('⿳')) == 3
	assert len(cjk.idc_slots('▦')) == 9


def test_idc_slots_clamped():
	# Extreme splits clamp into (0.05, 0.95).
	lo = cjk.idc_slots('⿰', split=-1.0)
	hi = cjk.idc_slots('⿰', split=2.0)
	assert lo[0][2] >= 0.05 and hi[0][2] <= 0.95


def test_slots_union():
	slots = cjk.idc_slots('⿲')					# three columns
	u = cjk.slots_union(slots, {0, 1})			# left+middle merged
	assert _close(u[0], 0.0) and _close(u[2], 2.0 / 3.0, 1e-6)
	assert cjk.slots_union(slots, set()) is None


# - boundary_ratio (shared Measure / Scan) ----------------------------
def test_boundary_ratio_horizontal_split():
	# ⿰: left part narrower -> ratio < 0.5. Two bars, gap at ~40% of the face.
	S = 48
	bar_l = [(100, 100), (300, 100), (300, 900), (100, 900)]
	bar_r = [(450, 100), (850, 100), (850, 900), (450, 900)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink  = cjk.rasterize_contours([bar_l, bar_r], frame, S)
	marg = cjk.marginals(ink, S)
	face = cjk.face_frame(ink, S, marg=marg)
	ratio = cjk.boundary_ratio(marg, face, '⿰')
	assert ratio is not None and 0.2 < ratio < 0.6


def test_boundary_ratio_none_for_solid():
	S = 32
	sq = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	ink  = cjk.rasterize_contours(sq, frame, S)
	marg = cjk.marginals(ink, S)
	face = cjk.face_frame(ink, S, marg=marg)
	assert cjk.boundary_ratio(marg, face, '⿰') is None		# no valley
	assert cjk.boundary_ratio(marg, None, '⿰') is None		# no face
	assert cjk.boundary_ratio(marg, face, '⿴') is None		# not measurable


# - Region frame helpers (reference-frame policy, region placement) ----
def test_rect_in_frame():
	# Frame offset from origin; y-UP top slot of a 50/50 ⿱ maps to the upper half.
	frame = (100.0, -200.0, 1100.0, 800.0)		# (l,b,r,t): w=1000, h=1000
	top = cjk.idc_slots('⿱', split=0.5)[0]		# (0, 0.5, 1, 1)
	x0, y0, x1, y1 = cjk.rect_in_frame(frame, top)
	assert _close(x0, 100.0) and _close(x1, 1100.0)
	assert _close(y0, 300.0) and _close(y1, 800.0)	# upper half in font-up space


def test_face_frame_reliable():
	em = (0.0, -200.0, 1000.0, 800.0)			# w=1000, h=1000
	full = (50.0, -150.0, 950.0, 750.0)			# ~90% each side -> reliable
	stub = (0.0, 0.0, 120.0, 120.0)				# 12% side -> rejected
	assert cjk.face_frame_reliable(full, em) is True
	assert cjk.face_frame_reliable(stub, em) is False


def test_reference_frame_captured_or_em_never_live():
	em = (0.0, -200.0, 1000.0, 800.0)
	face = (50.0, -150.0, 950.0, 750.0)
	stub = (0.0, 0.0, 120.0, 120.0)
	# use_face off -> em regardless of a good face
	assert cjk.reference_frame(face, em, use_face=False) == em
	# no captured face -> em (the fix: never fall back to a live face)
	assert cjk.reference_frame(None, em, use_face=True) == em
	# a reliable captured face is used
	assert cjk.reference_frame(face, em, use_face=True) == face
	# a degenerate/stub captured face is rejected in favour of the em band
	assert cjk.reference_frame(stub, em, use_face=True) == em


def test_inset_frame():
	frame = (0.0, -200.0, 1000.0, 800.0)		# w=1000, h=1000
	assert cjk.inset_frame(frame, 0.0) == frame
	l, b, r, t = cjk.inset_frame(frame, 0.1)
	assert _close(l, 100.0) and _close(r, 900.0)
	assert _close(b, -100.0) and _close(t, 700.0)
	# clamped to 0.45
	l2, b2, r2, t2 = cjk.inset_frame(frame, 0.9)
	assert _close(l2, 450.0) and _close(r2, 550.0)


def test_reference_frame_fallback_chain():
	em = (0.0, -200.0, 1000.0, 800.0)
	face = (50.0, -150.0, 950.0, 750.0)			# reliable
	other = (30.0, -170.0, 970.0, 770.0)		# reliable default (active layer)
	stub = (0.0, 0.0, 120.0, 120.0)
	# own captured face wins over a default_face
	assert cjk.reference_frame(face, em, default_face=other) == face
	# no own face -> reliable default_face (active layer face) beats em/imaginary
	assert cjk.reference_frame(None, em, default_face=other, margin=0.1) == other
	# no own, no default -> imaginary face (em inset by margin)
	assert cjk.reference_frame(None, em, default_face=None, margin=0.1) == cjk.inset_frame(em, 0.1)
	# stub default is rejected -> falls through to imaginary
	assert cjk.reference_frame(None, em, default_face=stub, margin=0.1) == cjk.inset_frame(em, 0.1)
	# nothing usable -> em
	assert cjk.reference_frame(None, em, default_face=None, margin=None) == em


# - reduce_ratios -----------------------------------------------------
def test_reduce_ratios():
	assert cjk.reduce_ratios([]) is None
	red = cjk.reduce_ratios([0.5, 0.5, 0.5])
	assert red['measured'] == 3 and _close(red['ratio_mean'], 0.5) and _close(red['ratio_sd'], 0.0)
	red2 = cjk.reduce_ratios([0.05, 0.95], hist_bins=10)
	assert red2['ratio_min'] == 0.05 and red2['ratio_max'] == 0.95
	assert sum(red2['hist']) == 2


# - compute_gauges (pure, ink-in) -------------------------------------
def test_compute_gauges_basic():
	S = 40
	# Left/right two-bar glyph over a 1000x1000 frame.
	bar_l = [(150, 100), (300, 100), (300, 900), (150, 900)]
	bar_r = [(700, 100), (850, 100), (850, 900), (700, 900)]
	frame = (0.0, 0.0, 1000.0, 1000.0)
	contours = [bar_l, bar_r]
	ink = cjk.rasterize_contours(contours, frame, S)
	g = cjk.compute_gauges(contours, ink, frame, groups=[[0], [1]], S=S)
	# Symmetric layout -> centroid near centre, small dx.
	assert 'gray_dx' in g and abs(g['gray_dx']) < 0.05
	assert 'face_lin' in g and 'mesh_v1' in g
	# Two components on the x axis -> a D_norm and moment present.
	assert 'D_norm' in g and 'M' in g


def test_compute_gauges_degenerate_frame():
	assert cjk.compute_gauges([], [], (0.0, 0.0, 0.0, 0.0), S=8) == {}


if __name__ == '__main__':
	import sys
	failures = 0
	for name, fn in sorted(globals().items()):
		if name.startswith('test_') and callable(fn):
			try:
				fn()
				print('PASS', name)
			except AssertionError as e:
				failures += 1
				print('FAIL', name, e)
			except Exception as e:
				failures += 1
				print('ERROR', name, repr(e))
	print('\n%d failure(s)' % failures)
	sys.exit(1 if failures else 0)
