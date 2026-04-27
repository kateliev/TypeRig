# MODULE: TypeRig / Core / Algo / Stroke Snap
# -----------------------------------------------------------
# Stroke-level width detection, classification, capture audit,
# and symmetric-offset snap. Operates on already-separated
# stroke contours (one per stroke) — pair with stroke_sep.
# CJK-first; Latin works as a degenerate case.
#
# Pipeline:
#   StrokeMeasurer    -> StrokeMeasurement (width profile + axis)
#   StrokeClassifier  -> stroke type (CJK 横/竖/撇/捺/点 + diagonal/dot)
#   StrokeAuditor     -> [StrokeViolation]    (capture against per-type allowlist)
#   StrokeFixer       -> StrokeCorrectionPlan -> apply()
#                          via Contour.offset_outline (symmetric, advance-preserving)
#
# Capture semantics: only strokes whose width falls inside a
# declared per-type target's band get snapped. Out-of-band
# strokes are silently left alone.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.algo.mat import compute_mat
from typerig.core.algo._width_audit import (
	WidthTarget, WidthAllowlist, Violation,
)

__version__ = '0.2.0'


# - Stroke type taxonomy ---------------
class StrokeType(object):
	'''Coarse CJK-aware bins. Names follow Mandarin pinyin so callers can
	read the allowlist alongside a designer's stem table.

	  HORIZONTAL ('horizontal') -- 横 (heng)
	  VERTICAL   ('vertical')   -- 竖 (shu)
	  PIE        ('pie')        -- 撇 (pie)  : negative-slope diagonal
	  NA         ('na')         -- 捺 (na)   : positive-slope diagonal
	  DOT        ('dot')        -- 点 (dian) : low aspect ratio (length/width < threshold)
	  DIAGONAL   ('diagonal')   -- generic diagonal not within PIE/NA bins
	  UNKNOWN    ('unknown')    -- could not classify
	'''
	HORIZONTAL = 'horizontal'
	VERTICAL   = 'vertical'
	PIE        = 'pie'
	NA         = 'na'
	DOT        = 'dot'
	DIAGONAL   = 'diagonal'
	UNKNOWN    = 'unknown'


# - Tunables ----------------------------
_DEFAULT_AXIS_TOL_DEG  = 15.0
_DEFAULT_DOT_ASPECT    = 1.5
_DEFAULT_MAT_QUALITY   = 'normal'


# - Measurement dataclass ---------------
class StrokeMeasurement(object):
	'''Per-stroke geometry summary.

	stroke         -- the input single-stroke Contour (not modified).
	axis_angle_deg -- principal-axis angle in [0, 180), from PCA on MAT
	                  node positions (or bbox fallback).
	length         -- extent along the principal axis.
	width          -- extent perpendicular to the principal axis.
	aspect         -- length / width.
	radii          -- list of MAT-node inscribed-disk radii. Empty if
	                  MAT was degenerate.
	width_min      -- 2 * min(radii)  (or bbox-min)
	width_median   -- 2 * median(radii) (or bbox)
	width_max      -- 2 * max(radii)  (or bbox-max)
	taper          -- (width_max - width_min) / max(width_median, eps).
	stroke_type    -- one of StrokeType.* (filled by StrokeClassifier).
	'''
	__slots__ = ('stroke', 'axis_angle_deg', 'length', 'width',
	             'aspect', 'radii',
	             'width_min', 'width_median', 'width_max', 'taper',
	             'stroke_type')

	def __init__(self, stroke):
		self.stroke = stroke
		self.axis_angle_deg = 0.0
		self.length = 0.0
		self.width = 0.0
		self.aspect = 0.0
		self.radii = []
		self.width_min = 0.0
		self.width_median = 0.0
		self.width_max = 0.0
		self.taper = 0.0
		self.stroke_type = StrokeType.UNKNOWN

	def __repr__(self):
		return ('StrokeMeasurement(type={}, axis={:.1f}deg, '
		        'w_med={:.1f}, taper={:.2f})').format(
			self.stroke_type, self.axis_angle_deg,
			self.width_median, self.taper)


# - Violation alias ---------------------
class StrokeViolation(Violation):
	'''Violation whose .source is a StrokeMeasurement.'''
	pass


# - Plan dataclass ----------------------
class StrokeCorrectionPlan(object):
	'''Per-stroke offset deltas. Keyed by stroke index in the input list.'''
	__slots__ = ('offsets', 'meta')

	def __init__(self):
		self.offsets = {}
		self.meta = {}

	def set(self, stroke_index, distance):
		self.offsets[int(stroke_index)] = float(distance)

	def __len__(self):
		return len(self.offsets)


# - Helpers -----------------------------
def _median(xs):
	if not xs:
		return 0.0
	s = sorted(xs)
	n = len(s)
	mid = n // 2
	if n % 2 == 1:
		return s[mid]
	return 0.5 * (s[mid - 1] + s[mid])


def _pca_axis_angle(points):
	n = len(points)
	if n < 2:
		return 0.0
	cx = sum(p[0] for p in points) / n
	cy = sum(p[1] for p in points) / n
	sxx = syy = sxy = 0.0
	for x, y in points:
		dx = x - cx
		dy = y - cy
		sxx += dx * dx
		syy += dy * dy
		sxy += dx * dy
	if abs(sxx - syy) < 1e-12 and abs(sxy) < 1e-12:
		return 0.0
	angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
	deg = math.degrees(angle) % 180.0
	return deg


def _project_extents(points, angle_deg):
	if not points:
		return 0.0, 0.0, 0.0, 0.0
	rad = math.radians(angle_deg)
	cs, sn = math.cos(rad), math.sin(rad)
	axis_vals = [p[0] * cs + p[1] * sn for p in points]
	perp_vals = [-p[0] * sn + p[1] * cs for p in points]
	return min(axis_vals), max(axis_vals), min(perp_vals), max(perp_vals)


# - Measurer ----------------------------
class StrokeMeasurer(object):
	'''Computes a StrokeMeasurement for a single stroke contour. Uses MAT
	to sample inscribed-disk radii along the stroke skeleton; falls back
	to bbox width if MAT is degenerate.
	'''
	def __init__(self, mat_quality=_DEFAULT_MAT_QUALITY, use_mat=True):
		self.mat_quality = mat_quality
		self.use_mat = bool(use_mat)

	def measure(self, stroke):
		m = StrokeMeasurement(stroke)
		on_pts = [(nd.x, nd.y) for nd in stroke.nodes if nd.is_on]
		if not on_pts:
			return m

		mat_radii = []
		mat_pts = []
		if self.use_mat:
			try:
				graph, _conc = compute_mat([stroke], quality=self.mat_quality)
				for nd in graph.nodes:
					mat_pts.append((nd.x, nd.y))
					if nd.radius > 0:
						mat_radii.append(nd.radius)
			except Exception:
				mat_pts = []
				mat_radii = []

		pca_pts = mat_pts if len(mat_pts) >= 2 else on_pts
		m.axis_angle_deg = _pca_axis_angle(pca_pts)

		ax_lo, ax_hi, perp_lo, perp_hi = _project_extents(on_pts, m.axis_angle_deg)
		m.length = ax_hi - ax_lo
		m.width = perp_hi - perp_lo
		m.aspect = (m.length / m.width) if m.width > 1e-9 else 0.0

		if mat_radii:
			m.radii = list(mat_radii)
			m.width_min = 2.0 * min(mat_radii)
			m.width_max = 2.0 * max(mat_radii)
			m.width_median = 2.0 * _median(mat_radii)
		else:
			m.radii = []
			m.width_min = m.width
			m.width_max = m.width
			m.width_median = m.width

		denom = max(m.width_median, 1e-9)
		m.taper = (m.width_max - m.width_min) / denom
		return m


# - Classifier --------------------------
class StrokeClassifier(object):
	'''Bins a StrokeMeasurement by aspect ratio and axis angle.'''
	def __init__(self, axis_tol_deg=_DEFAULT_AXIS_TOL_DEG,
	             dot_aspect=_DEFAULT_DOT_ASPECT):
		self.axis_tol_deg = float(axis_tol_deg)
		self.dot_aspect = float(dot_aspect)

	def classify(self, measurement):
		m = measurement
		if m.aspect > 0 and m.aspect < self.dot_aspect:
			m.stroke_type = StrokeType.DOT
			return m

		angle = m.axis_angle_deg % 180.0
		tol = self.axis_tol_deg
		def near(target):
			d = abs(angle - target)
			d = min(d, 180.0 - d)
			return d <= tol

		if near(0.0):
			m.stroke_type = StrokeType.HORIZONTAL
		elif near(90.0):
			m.stroke_type = StrokeType.VERTICAL
		elif near(45.0):
			m.stroke_type = StrokeType.NA
		elif near(135.0):
			m.stroke_type = StrokeType.PIE
		else:
			m.stroke_type = StrokeType.DIAGONAL
		return m


# - Auditor -----------------------------
class StrokeAuditor(object):
	'''Capture-semantics audit against a per-type allowlist.

	match_on selects which width signal feeds the capture lookup:
	  - 'median' (default): forgiving on tapered strokes
	  - 'min'             : catches anorexic tapers
	  - 'max'             : catches over-thick swells
	'''
	def __init__(self, allowlist, match_on='median', drop_zero_delta=False):
		if not isinstance(allowlist, WidthAllowlist):
			raise TypeError('StrokeAuditor needs a WidthAllowlist')
		if match_on not in ('median', 'min', 'max'):
			raise ValueError('match_on must be \'median\', \'min\', or \'max\'')
		self.allowlist = allowlist
		self.match_on = match_on
		self.drop_zero_delta = bool(drop_zero_delta)

	def _measured(self, m):
		if self.match_on == 'median': return m.width_median
		if self.match_on == 'min':    return m.width_min
		return m.width_max

	def audit(self, measurements):
		violations = []
		for m in measurements:
			measured = self._measured(m)
			res = self.allowlist.capture(m.stroke_type, measured)
			if res is None:
				continue
			target, delta = res
			if self.drop_zero_delta and delta == 0.0:
				continue
			violations.append(StrokeViolation(
				key=m.stroke_type,
				measured=measured,
				target=target,
				delta=delta,
				source=m,
			))
		return violations


# - Fixer (symmetric offset) ------------
class StrokeFixer(object):
	'''Builds and applies a StrokeCorrectionPlan via Contour.offset_outline.

	For each captured violation, distance = delta / 2. offset_outline
	applies its distance to BOTH faces, so width changes by delta exactly.
	Centerline and advance preserved.
	'''
	def __init__(self, curvature_correction=True):
		self.curvature_correction = bool(curvature_correction)

	def plan(self, violations, strokes):
		plan = StrokeCorrectionPlan()
		idx_of = {id(c): i for i, c in enumerate(strokes)}
		for v in violations:
			ci = idx_of.get(id(v.source.stroke))
			if ci is None:
				continue
			plan.set(ci, v.delta * 0.5)
		return plan

	def apply(self, plan, strokes):
		out = list(strokes)
		for ci, dist in plan.offsets.items():
			if 0 <= ci < len(out) and dist != 0.0:
				try:
					out[ci] = strokes[ci].offset_outline(
						dist, curvature_correction=self.curvature_correction)
				except Exception:
					pass
		return out


# =====================================================================
# Stage 7-style self-tests.
# =====================================================================

def _approx(a, b, tol=1e-3):
	return abs(a - b) <= tol


def _make_rect_contour(x, y, w, h):
	nodes = [Node(x, y), Node(x + w, y), Node(x + w, y + h), Node(x, y + h)]
	return Contour(nodes, closed=True)


# --- Stage 1: PCA + projections ---

def _test_pca_horizontal_rect():
	pts = [(0, 0), (600, 0), (600, 50), (0, 50)]
	a = _pca_axis_angle(pts)
	a_norm = min(a, 180.0 - a)
	assert a_norm < 5.0
	print('  PCA horizontal rect: axis ~ 0 deg [OK]')


def _test_pca_vertical_rect():
	pts = [(0, 0), (50, 0), (50, 600), (0, 600)]
	a = _pca_axis_angle(pts)
	assert abs(a - 90.0) < 5.0
	print('  PCA vertical rect: axis ~ 90 deg [OK]')


def _test_project_extents_horizontal():
	pts = [(0, 0), (600, 0), (600, 50), (0, 50)]
	ax_lo, ax_hi, perp_lo, perp_hi = _project_extents(pts, 0.0)
	assert _approx(ax_hi - ax_lo, 600.0)
	assert _approx(perp_hi - perp_lo, 50.0)
	print('  project_extents @0deg: length=600, width=50 [OK]')


def _run_stage1_tests():
	print('Stage 1 - PCA / projections:')
	_test_pca_horizontal_rect()
	_test_pca_vertical_rect()
	_test_project_extents_horizontal()
	print('Stage 1: all tests passed.')


# --- Stage 2: Measurer (with MAT) ---

def _test_measurer_horizontal():
	c = _make_rect_contour(0, 0, 600, 50)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	assert _approx(m.width_median, 50.0, tol=4.0)
	assert m.aspect > 5.0
	print('  measurer: 600x50 -> width_median ~50, aspect={:.1f} [OK]'.format(m.aspect))


def _test_measurer_vertical():
	c = _make_rect_contour(0, 0, 50, 600)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	assert _approx(m.width_median, 50.0, tol=4.0)
	assert abs(m.axis_angle_deg - 90.0) < 5.0
	print('  measurer: 50x600 -> width_median ~50, axis ~90 [OK]')


def _test_measurer_dot():
	c = _make_rect_contour(0, 0, 60, 60)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	assert m.aspect < 1.5
	print('  measurer: 60x60 -> aspect={:.2f} (DOT region) [OK]'.format(m.aspect))


def _run_stage2_tests():
	print('Stage 2 - StrokeMeasurer:')
	_test_measurer_horizontal()
	_test_measurer_vertical()
	_test_measurer_dot()
	print('Stage 2: all tests passed.')


# --- Stage 3: Classifier ---

def _test_classifier_horizontal():
	c = _make_rect_contour(0, 0, 600, 50)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	StrokeClassifier().classify(m)
	assert m.stroke_type == StrokeType.HORIZONTAL
	print('  600x50 -> HORIZONTAL [OK]')


def _test_classifier_vertical():
	c = _make_rect_contour(0, 0, 50, 600)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	StrokeClassifier().classify(m)
	assert m.stroke_type == StrokeType.VERTICAL
	print('  50x600 -> VERTICAL [OK]')


def _test_classifier_dot():
	c = _make_rect_contour(0, 0, 60, 60)
	m = StrokeMeasurer(mat_quality='draft').measure(c)
	StrokeClassifier().classify(m)
	assert m.stroke_type == StrokeType.DOT
	print('  60x60 -> DOT [OK]')


def _run_stage3_tests():
	print('Stage 3 - StrokeClassifier:')
	_test_classifier_horizontal()
	_test_classifier_vertical()
	_test_classifier_dot()
	print('Stage 3: all tests passed.')


# --- Stage 4: capture audit (per-type) ---

def _test_audit_in_band_capture():
	'''heng=31, allowlist horizontal target=29 +/- 5 -> captured.'''
	heng = _make_rect_contour(0, 0, 600, 31)
	measurer = StrokeMeasurer(mat_quality='draft')
	classifier = StrokeClassifier()
	m = classifier.classify(measurer.measure(heng))
	al = WidthAllowlist({StrokeType.HORIZONTAL: [WidthTarget(29, 5, 5)]})
	violations = StrokeAuditor(al).audit([m])
	assert len(violations) == 1
	v = violations[0]
	assert v.target.value == 29
	# Allow some MAT noise on the median measurement.
	assert abs(v.delta - (29 - v.measured)) < 1e-6
	print('  heng width~31 captured -> snap to 29 (delta={:+.2f}) [OK]'.format(v.delta))


def _test_audit_out_of_band_silent():
	'''shu=88, allowlist vertical 29 +/- 5 -> silent (out of band).'''
	shu = _make_rect_contour(0, 0, 88, 600)
	measurer = StrokeMeasurer(mat_quality='draft')
	classifier = StrokeClassifier()
	m = classifier.classify(measurer.measure(shu))
	al = WidthAllowlist({StrokeType.VERTICAL: [WidthTarget(29, 5, 5)]})
	violations = StrokeAuditor(al).audit([m])
	assert violations == [], 'out-of-band stroke must be silent'
	print('  shu width=88 vs target 29+/-5: silent (no violation) [OK]')


def _test_audit_per_type_isolation():
	'''Allowlist defines only HORIZONTAL; a VERTICAL stroke must not be
	captured even if its width happens to be in band.'''
	shu = _make_rect_contour(0, 0, 31, 600)   # vertical, width 31
	m = StrokeClassifier().classify(StrokeMeasurer(mat_quality='draft').measure(shu))
	assert m.stroke_type == StrokeType.VERTICAL
	al = WidthAllowlist({StrokeType.HORIZONTAL: [WidthTarget(29, 5, 5)]})
	violations = StrokeAuditor(al).audit([m])
	assert violations == [], 'per-type isolation broken: {}'.format(violations)
	print('  per-type isolation: VERTICAL not captured by HORIZONTAL allowlist [OK]')


def _run_stage4_tests():
	print('Stage 4 - capture audit (per type):')
	_test_audit_in_band_capture()
	_test_audit_out_of_band_silent()
	_test_audit_per_type_isolation()
	print('Stage 4: all tests passed.')


# --- Stage 5: Fixer (symmetric offset) ---

def _test_fixer_symmetric_capture():
	'''heng width~31, target 29. Symmetric offset (delta=-2) shrinks each
	face by 1; centerline preserved.'''
	stroke = _make_rect_contour(0, 0, 600, 31).to_cubic_contour()
	measurer = StrokeMeasurer(mat_quality='draft')
	classifier = StrokeClassifier()
	m = classifier.classify(measurer.measure(stroke))
	on_y = [nd.y for nd in stroke.nodes if nd.is_on]
	cy_before = sum(on_y) / len(on_y)

	al = WidthAllowlist({StrokeType.HORIZONTAL: [WidthTarget(29, 5, 5)]})
	violations = StrokeAuditor(al).audit([m])
	plan = StrokeFixer().plan(violations, [stroke])
	new_strokes = StrokeFixer().apply(plan, [stroke])
	m2 = classifier.classify(measurer.measure(new_strokes[0]))
	on_y_after = [nd.y for nd in new_strokes[0].nodes if nd.is_on]
	cy_after = sum(on_y_after) / len(on_y_after)
	assert _approx(m2.width_median, 29.0, tol=2.0), \
		'after capture+fix: width_median={}'.format(m2.width_median)
	assert _approx(cy_before, cy_after, tol=1.0), \
		'centerline drift: {} -> {}'.format(cy_before, cy_after)
	print('  capture+offset: heng~31 -> 29, centerline preserved [OK]')


def _test_fixer_out_of_band_no_op():
	'''shu width=88, target 29. Out of band -> no plan -> unchanged.'''
	stroke = _make_rect_contour(0, 0, 88, 600).to_cubic_contour()
	measurer = StrokeMeasurer(mat_quality='draft')
	classifier = StrokeClassifier()
	m = classifier.classify(measurer.measure(stroke))
	al = WidthAllowlist({StrokeType.VERTICAL: [WidthTarget(29, 5, 5)]})
	violations = StrokeAuditor(al).audit([m])
	plan = StrokeFixer().plan(violations, [stroke])
	new_strokes = StrokeFixer().apply(plan, [stroke])
	assert len(plan) == 0
	assert new_strokes[0] is stroke
	print('  out-of-band shu=88: empty plan, identity passthrough [OK]')


def _run_stage5_tests():
	print('Stage 5 - StrokeFixer (symmetric offset):')
	_test_fixer_symmetric_capture()
	_test_fixer_out_of_band_no_op()
	print('Stage 5: all tests passed.')


if __name__ == '__main__':
	_run_stage1_tests()
	print()
	_run_stage2_tests()
	print()
	_run_stage3_tests()
	print()
	_run_stage4_tests()
	print()
	_run_stage5_tests()
	print()
	print('stroke_snap: ALL STAGES PASSED')
