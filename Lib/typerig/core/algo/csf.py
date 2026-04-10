# MODULE: TypeRig / Core / Algo / Curvilinear Shape Features (CSFs)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026     (http://www.kateliev.com)
# (C) Karandash Type Foundry         (http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Based on: Berio, Leymarie, Asente, Echevarria.
# "StrokeStyles: Stroke-Based Segmentation and Stylization of Fonts."
# ACM Trans. Graph., 2022.  Section 4.2 — Curvilinear Shape Features.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict

from typerig.core.algo.mat import sample_contour, MATNode, MATGraph

# - Init --------------------------------
__version__ = '0.1.1'
_EPS = 1e-9

# τ_c: concave CSF disk radius limit = τ_c × glyph_height (paper default 0.15)
_TAU_C = 0.15

# Disk overlap fraction threshold for Tait-Kneser spiral filter (paper: 0.98)
_TAU_SPIRAL = 0.98


# ============================================================
# Data structure
# ============================================================

class CSF(object):
	"""Curvilinear Shape Feature descriptor (Berio et al. 2022, §4.2).

	A CSF captures a curvature extremum on the glyph outline. Taken
	together, the CSFs of a glyph FULLY COVER the outline — adjacent CSFs
	share exactly one support segment with no gaps between them.

	Attributes:
		csf_type:        'convex' (from M terminal) or 'concave' (from M* terminal)
		disk_center:     (x, y) — inscribed-circle center of the terminal disk
		disk_radius:     float  — disk radius = min distance to outline
		contact_region:  list of (x, y) — outline sample points inside the disk arc
		extremum:        (x, y) — midpoint of the contact region; canonical CSF position
		axis:            list of (x, y) — local symmetry axis from terminal toward fork
		support_segments:(left_pts, right_pts) — outline arcs on each side of contact
		contour_idx:     int   — which input contour this CSF belongs to
		arc_param:       float — arc-length s of extremum (used for ordering)
		arc_start:       float — arc-length start of contact region
		arc_end:         float — arc-length end of contact region

	Concave-only attributes (populated by compute_csfs):
		tangent_pair:    ((tx, ty), (tx', ty')) — unit tangents at contact endpoints
		inward_normal:   (nx, ny) — -(τ + τ') normalised, pointing toward extremum
	"""

	__slots__ = (
		'csf_type', 'disk_center', 'disk_radius',
		'contact_region', 'extremum', 'axis',
		'support_segments', 'contour_idx',
		'arc_param', 'arc_start', 'arc_end',
		'tangent_pair', 'inward_normal',
	)

	def __init__(self, csf_type, disk_center, disk_radius, contact_region,
				 extremum, axis, contour_idx=0, arc_param=0.0,
				 arc_start=0.0, arc_end=0.0):
		self.csf_type       = csf_type
		self.disk_center    = disk_center
		self.disk_radius    = float(disk_radius)
		self.contact_region = contact_region   # list of (x, y)
		self.extremum       = extremum         # (x, y)
		self.axis           = axis             # list of (x, y)
		self.support_segments = ([], [])       # (left, right)
		self.contour_idx    = int(contour_idx)
		self.arc_param      = float(arc_param)
		self.arc_start      = float(arc_start)
		self.arc_end        = float(arc_end)
		self.tangent_pair   = None
		self.inward_normal  = None

	def __repr__(self):
		return '<CSF: {} at ({:.1f},{:.1f}) r={:.1f}>'.format(
			self.csf_type, self.extremum[0], self.extremum[1], self.disk_radius)


# ============================================================
# Internal geometry helpers
# ============================================================

def _unit_vec(dx, dy):
	"""Return unit vector (dx, dy) or (1, 0) for zero-length input."""
	mag = math.hypot(dx, dy)
	if mag < _EPS:
		return (1.0, 0.0)
	return (dx / mag, dy / mag)


def _parameterize_contour(contour, step):
	"""Sample contour and accumulate arc length.

	Returns:
		list of (x, y, s) where s is cumulative arc length from the first sample.
	"""
	raw = sample_contour(contour, step=step)
	if not raw:
		return []
	result = [(raw[0][0], raw[0][1], 0.0)]
	s = 0.0
	for i in range(1, len(raw)):
		s += math.hypot(raw[i][0] - raw[i-1][0], raw[i][1] - raw[i-1][1])
		result.append((raw[i][0], raw[i][1], s))
	return result


def _find_contact_region(cx, cy, r, params, tol=None):
	"""Collect outline samples within the terminal disk.

	Args:
		cx, cy: disk center
		r:      disk radius
		params: list of (x, y, s) for a contour
		tol:    search tolerance beyond r; default = max(3.0, r * 0.12)

	Returns:
		list of (x, y, s) already sorted by s (params is pre-sorted).
	"""
	if tol is None:
		tol = max(3.0, r * 0.12)
	limit_sq = (r + tol) ** 2
	return [(x, y, s) for x, y, s in params
			if (x - cx) ** 2 + (y - cy) ** 2 <= limit_sq]


def _extract_axis(terminal):
	"""Walk a MAT terminal toward its fork, collecting node positions.

	Returns:
		list of (x, y) from terminal through regular nodes to the first fork.
	"""
	axis = [(terminal.x, terminal.y)]
	if not terminal.neighbors:
		return axis
	prev, cur = terminal, terminal.neighbors[0]
	while cur is not None:
		axis.append((cur.x, cur.y))
		if cur.is_fork or cur.is_terminal:
			break
		nxt = [n for n in cur.neighbors if n is not prev]
		if not nxt:
			break
		prev, cur = cur, nxt[0]
	return axis


def _extract_arc(params, s_from, s_to, total_s):
	"""Extract outline points between arc-length positions s_from and s_to.

	Handles closed-contour wrap-around (s_to < s_from) by returning points
	from s_from → total_s concatenated with 0 → s_to.

	Args:
		params:  list of (x, y, s)
		s_from:  start arc length
		s_to:    end arc length
		total_s: total arc length of the closed contour

	Returns:
		list of (x, y)
	"""
	if not params:
		return []

	if s_to >= s_from:
		return [(x, y) for x, y, s in params if s_from <= s <= s_to]

	# Wrap-around: end-of-contour then start-of-contour
	right = [(x, y) for x, y, s in params if s >= s_from]
	left  = [(x, y) for x, y, s in params if s <= s_to]
	return right + left


def _find_idx_by_s(params, s_target):
	"""Binary search: index of the sample in params nearest to arc-length s_target.

	params must be sorted by s (third element). Handles boundary clamping.
	"""
	n = len(params)
	if n == 0:
		return 0
	if s_target <= params[0][2]:
		return 0
	if s_target >= params[-1][2]:
		return n - 1

	lo, hi = 0, n - 1
	while lo < hi - 1:
		mid = (lo + hi) >> 1
		if params[mid][2] < s_target:
			lo = mid
		else:
			hi = mid

	# Return whichever of lo/hi is closer to s_target
	if abs(params[hi][2] - s_target) < abs(params[lo][2] - s_target):
		return hi
	return lo


def _estimate_tangent(params, px, py, look_arc=20.0, one_sided=None):
	"""Robust outline tangent using a windowed chord (sleeve approximation).

	Rather than a single-step finite difference (which gives a diagonal at
	sharp corners), this draws a chord of arc-length `look_arc` centred on,
	or starting/ending at, the sample nearest to (px, py).  The chord
	direction is a stable estimate of the local tangent even at corners.

	Args:
		params:     list of (x, y, s) — parameterized contour, sorted by s.
		px, py:     query position; the nearest sample is used as the anchor.
		look_arc:   arc-length window size in font units.
		one_sided:  None     → symmetric: chord from (s0 - look_arc) to (s0 + look_arc).
		            'back'   → backward:  chord from (s0 - look_arc) to s0.
		                        Gives the incoming direction at the anchor.
		            'fwd'    → forward:   chord from s0 to (s0 + look_arc).
		                        Gives the outgoing direction at the anchor.

	Returns:
		(tx, ty) — unit tangent oriented in the outline traversal direction.
	"""
	n = len(params)
	if n < 2:
		return (1.0, 0.0)

	# Locate nearest sample
	best_idx, best_d = 0, float('inf')
	for idx, (x, y, _s) in enumerate(params):
		d = math.hypot(x - px, y - py)
		if d < best_d:
			best_d, best_idx = d, idx

	s0 = params[best_idx][2]
	total_s = params[-1][2]

	if one_sided == 'back':
		# Backward one-sided: chord from (s0 - look_arc) → s0
		# Gives the approach direction at px, py (from the left support side).
		s_from = max(0.0, s0 - look_arc)
		s_to   = s0
	elif one_sided == 'fwd':
		# Forward one-sided: chord from s0 → (s0 + look_arc)
		# Gives the departure direction at px, py (into the right support side).
		s_from = s0
		s_to   = min(total_s, s0 + look_arc)
	else:
		# Symmetric: chord centred on s0
		s_from = max(0.0,       s0 - look_arc)
		s_to   = min(total_s,   s0 + look_arc)

	idx_from = _find_idx_by_s(params, s_from)
	idx_to   = _find_idx_by_s(params, s_to)

	# Degenerate: both sides collapsed to the same index (very short contour)
	if idx_from == idx_to:
		if idx_from > 0:
			p0, p1 = params[idx_from - 1], params[idx_from]
		else:
			p0, p1 = params[0], params[1]
		return _unit_vec(p1[0] - p0[0], p1[1] - p0[1])

	p_from = params[idx_from]
	p_to   = params[idx_to]
	return _unit_vec(p_to[0] - p_from[0], p_to[1] - p_from[1])


# ============================================================
# Curvature analysis for Pass 2
# ============================================================

def _discrete_curvature(pts):
	"""Compute signed discrete curvature at each interior point.

	Uses the Menger curvature formula on three consecutive points.
	Positive curvature = CCW turn (convex outline feature for CCW contours).
	Negative curvature = CW turn (concave feature).

	Args:
		pts: list of (x, y)

	Returns:
		list of float, length = len(pts) - 2, indexed to interior points pts[1:-1].
	"""
	n = len(pts)
	if n < 3:
		return []

	result = []
	for i in range(1, n - 1):
		p0, p1, p2 = pts[i-1], pts[i], pts[i+1]

		v1x = p1[0] - p0[0];  v1y = p1[1] - p0[1]
		v2x = p2[0] - p1[0];  v2y = p2[1] - p1[1]

		cross = v1x * v2y - v1y * v2x

		d1 = math.hypot(v1x, v1y)
		d2 = math.hypot(v2x, v2y)
		d3 = math.hypot(p2[0] - p0[0], p2[1] - p0[1])

		denom = d1 * d2 * d3
		result.append(2.0 * cross / denom if denom > _EPS else 0.0)

	return result


def _find_curvature_extrema(pts, curvatures, min_abs_k=None):
	"""Find local maxima of |curvature| among interior points of pts.

	Args:
		pts:        list of (x, y) — the support segment
		curvatures: list of float from _discrete_curvature (length = len(pts)-2)
		min_abs_k:  minimum |k| to report (filters noise); default 1/5000

	Returns:
		list of (x, y, radius, sign, nx, ny) where:
			(x, y):   extremum position on the outline
			radius:   osculating circle radius = 1 / |k|
			sign:     +1 convex, -1 concave
			(nx, ny): inward unit normal at the extremum (toward osculating center
			          for convex; away from it for concave — matches MAT interior)
	"""
	if min_abs_k is None:
		min_abs_k = 1.0 / 5000.0

	n_k = len(curvatures)
	if n_k < 3:
		return []

	extrema = []
	for i in range(1, n_k - 1):
		k     = curvatures[i]
		k_prv = curvatures[i - 1]
		k_nxt = curvatures[i + 1]

		if abs(k) < min_abs_k:
			continue

		# Local maximum of |k|
		if abs(k) <= abs(k_prv) or abs(k) <= abs(k_nxt):
			continue

		# Corresponding outline point is pts[i + 1] (curvatures[0] ↔ pts[1])
		pt = pts[i + 1]
		r = 1.0 / abs(k)

		# Inward normal: perpendicular to tangent, pointing toward oscillating center
		# Tangent from pts[i] to pts[i+2]
		tx, ty = _unit_vec(pts[i+2][0] - pts[i][0], pts[i+2][1] - pts[i][1])
		# Left normal (CCW rotation of tangent = inward for CCW outer contour)
		lnx, lny = -ty, tx

		sign = 1 if k > 0 else -1

		# For CONVEX (k > 0 on CCW contour): oscillating center is to the left → inward
		# For CONCAVE (k < 0): oscillating center is to the right → outward
		nx, ny = (lnx, lny) if sign > 0 else (-lnx, -lny)

		extrema.append((pt[0], pt[1], r, sign, nx, ny))

	return extrema


# ============================================================
# Spiral filter (Tait-Kneser theorem, Appendix A)
# ============================================================

def _circle_overlap_fraction(cx1, cy1, r1, cx2, cy2, r2):
	"""Intersection area / area of the smaller circle.

	Returns value in [0, 1]: 0 = no overlap, 1 = smaller circle fully inside larger.
	"""
	d = math.hypot(cx2 - cx1, cy2 - cy1)
	r_min = min(r1, r2)
	r_max = max(r1, r2)

	if d >= r1 + r2:
		return 0.0
	if d <= r_max - r_min:
		return 1.0

	# Lens formula
	cos_a = max(-1.0, min(1.0, (d*d + r1*r1 - r2*r2) / (2.0 * d * r1)))
	cos_b = max(-1.0, min(1.0, (d*d + r2*r2 - r1*r1) / (2.0 * d * r2)))

	a1 = r1 * r1 * math.acos(cos_a)
	a2 = r2 * r2 * math.acos(cos_b)

	# Triangle height from Heron's formula
	s = (r1 + r2 + d) * 0.5
	tri_sq = max(0.0, s * (s - r1) * (s - r2) * (s - d))
	intersection = a1 + a2 - math.sqrt(tri_sq)

	area_min = math.pi * r_min * r_min
	if area_min < _EPS:
		return 0.0
	return min(1.0, max(0.0, intersection / area_min))


def _apply_spiral_filter(new_csfs, existing_csfs, threshold=_TAU_SPIRAL):
	"""Discard new CSFs whose disk is nearly contained within a smaller existing disk.

	The Tait-Kneser theorem guarantees that spiraling arcs have no curvature
	extrema. If a new disk overlaps > threshold fraction with a SMALLER existing
	disk, the new CSF is a spiral artifact.

	Args:
		new_csfs:      candidate CSFs found in Pass 2+
		existing_csfs: already accepted CSFs (Pass 1 + previous passes)
		threshold:     overlap fraction above which the new CSF is discarded (default 0.98)

	Returns:
		filtered list of new_csfs with spiral artifacts removed
	"""
	kept = []
	for nc in new_csfs:
		nx, ny, nr = nc.disk_center[0], nc.disk_center[1], nc.disk_radius
		spiral = False
		for ec in existing_csfs:
			if ec.disk_radius >= nr:
				# Only filter against SMALLER existing disks
				continue
			frac = _circle_overlap_fraction(
				nx, ny, nr,
				ec.disk_center[0], ec.disk_center[1], ec.disk_radius)
			if frac > threshold:
				spiral = True
				break
		if not spiral:
			kept.append(nc)
	return kept


def _deduplicate_csfs(csfs, tol=8.0):
	"""Remove near-duplicate CSFs (same type, close extremum), keeping smaller disk."""
	if len(csfs) <= 1:
		return csfs
	kept = []
	for csf in csfs:
		dup = False
		for ex in kept:
			if ex.csf_type != csf.csf_type:
				continue
			d = math.hypot(csf.extremum[0] - ex.extremum[0],
						   csf.extremum[1] - ex.extremum[1])
			if d < tol:
				if csf.disk_radius < ex.disk_radius:
					kept.remove(ex)
					kept.append(csf)
				dup = True
				break
		if not dup:
			kept.append(csf)
	return kept


# ============================================================
# CSF construction (Pass 1)
# ============================================================

def _csf_from_mat_terminal(terminal, all_params):
	"""Create a convex CSF from an interior MAT terminal.

	The terminal is INSIDE the glyph. Its inscribed disk touches the nearest
	contour from inside. The contact region is the set of outline samples
	within disk radius + tolerance of the terminal position.

	Args:
		terminal:   MATNode with is_terminal == True
		all_params: list of parameterized contour data (one per contour)

	Returns:
		CSF or None if no contact region can be found.
	"""
	tx, ty, r = terminal.x, terminal.y, terminal.radius
	if r < _EPS:
		return None

	# Find the contour with the most samples in range
	best_c_idx  = -1
	best_contact = []
	for c_idx, params in enumerate(all_params):
		contact = _find_contact_region(tx, ty, r, params)
		if len(contact) > len(best_contact):
			best_contact = contact
			best_c_idx   = c_idx

	if not best_contact or best_c_idx < 0:
		# Fallback: just the single nearest sample on any contour
		best_d = float('inf')
		for c_idx, params in enumerate(all_params):
			for x, y, s in params:
				d = math.hypot(x - tx, y - ty)
				if d < best_d:
					best_d       = d
					best_c_idx   = c_idx
					best_contact = [(x, y, s)]
		if not best_contact:
			return None

	mid           = len(best_contact) // 2
	extremum      = (best_contact[mid][0], best_contact[mid][1])
	arc_param     = best_contact[mid][2]
	arc_start     = best_contact[0][2]
	arc_end       = best_contact[-1][2]
	contact_pts   = [(x, y) for x, y, _s in best_contact]
	axis          = _extract_axis(terminal)

	return CSF(
		csf_type='convex',
		disk_center=(tx, ty),
		disk_radius=r,
		contact_region=contact_pts,
		extremum=extremum,
		axis=axis,
		contour_idx=best_c_idx,
		arc_param=arc_param,
		arc_start=arc_start,
		arc_end=arc_end,
	)


def _csf_from_ext_terminal(tx, ty, r, cx, cy, all_params):
	"""Create a concave CSF from an exterior MAT terminal (from M*).

	The terminal disk is in the exterior space. The contact point (cx, cy)
	is the closest point on the glyph outline.  The contact region is the arc
	of outline samples near (cx, cy), and the axis points outward from the
	contact toward the exterior terminal.

	Args:
		tx, ty: exterior terminal disk center
		r:      disk radius
		cx, cy: closest contact point on the glyph outline
		all_params: list of parameterized contour data

	Returns:
		CSF or None.
	"""
	# Find which contour (cx, cy) belongs to
	best_c_idx = -1
	best_s     = 0.0
	best_d     = float('inf')
	for c_idx, params in enumerate(all_params):
		for x, y, s in params:
			d = math.hypot(x - cx, y - cy)
			if d < best_d:
				best_d     = d
				best_c_idx = c_idx
				best_s     = s

	if best_c_idx < 0:
		return None

	params = all_params[best_c_idx]

	# Contact region: outline samples near the contact point, radius ≈ disk radius
	# (the exterior disk just touches the outline, so the contact arc is small)
	contact = _find_contact_region(cx, cy, r, params, tol=max(3.0, r * 0.15))
	if not contact:
		contact = [(cx, cy, best_s)]

	mid        = len(contact) // 2
	extremum   = (contact[mid][0], contact[mid][1])
	arc_param  = contact[mid][2]
	arc_start  = contact[0][2]
	arc_end    = contact[-1][2]
	contact_pts = [(x, y) for x, y, _s in contact]

	# Simple 2-point axis: from contact point outward toward exterior terminal
	axis = [(cx, cy), (tx, ty)]

	return CSF(
		csf_type='concave',
		disk_center=(tx, ty),
		disk_radius=r,
		contact_region=contact_pts,
		extremum=extremum,
		axis=axis,
		contour_idx=best_c_idx,
		arc_param=arc_param,
		arc_start=arc_start,
		arc_end=arc_end,
	)


# ============================================================
# Support segment assignment
# ============================================================

def _sort_and_assign(csfs, all_params):
	"""Sort CSFs by contour and arc position, then assign support segments.

	Each contour's CSFs are sorted by arc_param. The support segment between
	consecutive CSFs is the outline arc from CSF_i.arc_end to CSF_{i+1}.arc_start.
	Adjacent CSFs share the same segment object (Python reference).

	Modifies support_segments in-place. Returns the same csfs list.
	"""
	# Group by contour
	by_contour = defaultdict(list)
	for csf in csfs:
		by_contour[csf.contour_idx].append(csf)

	for c_idx, c_csfs in by_contour.items():
		params = all_params[c_idx]
		if not params:
			continue
		total_s = params[-1][2]

		# Reset and sort
		for csf in c_csfs:
			csf.support_segments = ([], [])
		c_csfs.sort(key=lambda c: c.arc_param)
		n = len(c_csfs)

		# Compute each inter-CSF support arc once
		segs = []
		for i in range(n):
			csf_a = c_csfs[i]
			csf_b = c_csfs[(i + 1) % n]
			seg   = _extract_arc(params, csf_a.arc_end, csf_b.arc_start, total_s)
			segs.append(seg)

		# Assign: CSF_i.left = segs[i-1], CSF_i.right = segs[i]
		for i in range(n):
			c_csfs[i].support_segments = (segs[(i - 1) % n], segs[i])

	return csfs


# ============================================================
# Pass 2+: Iterative support-segment search
# ============================================================

def _search_support_segments(csfs, all_params, concave_r_limit, sample_step):
	"""Search every right-hand support segment for curvature extrema.

	Each segment is only searched once (right segment of each CSF). New CSFs
	found here represent outline features that M and M* missed — typically
	smooth curvature transitions with no sharp vertex.

	Args:
		csfs:              current CSF list (after Pass 1 or previous iteration)
		all_params:        parameterized contour data
		concave_r_limit:   τ_c × glyph_height; new concave CSFs with larger radius
		                   are discarded (smooth curves, not structural features)
		sample_step:       outline sampling step, used to set minimum segment length

	Returns:
		list of new CSF objects (not yet spiral-filtered or deduplicated).
	"""
	min_seg_len = sample_step * 8   # skip very short segments
	new_csfs    = []
	seen_segs   = set()             # avoid processing shared-reference segments twice

	for csf in csfs:
		seg = csf.support_segments[1]  # right segment — processed once per shared ref
		seg_id = id(seg)
		if seg_id in seen_segs or not seg:
			continue
		seen_segs.add(seg_id)

		if len(seg) < 5:
			continue

		seg_len = sum(
			math.hypot(seg[i][0] - seg[i-1][0], seg[i][1] - seg[i-1][1])
			for i in range(1, len(seg))
		)
		if seg_len < min_seg_len:
			continue

		curvatures = _discrete_curvature(seg)
		if not curvatures:
			continue

		extrema = _find_curvature_extrema(seg, curvatures)

		c_idx   = csf.contour_idx
		params  = all_params[c_idx]
		total_s = params[-1][2] if params else 1.0

		for ex_x, ex_y, ex_r, ex_sign, ex_nx, ex_ny in extrema:
			ex_type = 'concave' if ex_sign < 0 else 'convex'

			# Concave CSFs: only below the τ_c radius threshold
			if ex_type == 'concave' and ex_r >= concave_r_limit:
				continue

			# Disk center: osculating circle center (inward from outline)
			# For convex (sign>0): center offset inward along normal
			# For concave (sign<0): center offset outward (ex_ny already points out)
			disk_cx = ex_x + ex_r * ex_nx
			disk_cy = ex_y + ex_r * ex_ny

			# Locate this extremum in the parameterized contour data
			best_s, best_d = 0.0, float('inf')
			for x, y, s in params:
				d = math.hypot(x - ex_x, y - ex_y)
				if d < best_d:
					best_d, best_s = d, s

			# Contact region around the extremum point
			contact = _find_contact_region(ex_x, ex_y, ex_r, params,
										   tol=max(3.0, ex_r * 0.10))
			if not contact:
				contact_pts = [(ex_x, ex_y)]
				arc_s = arc_e = best_s
			else:
				contact_pts = [(x, y) for x, y, _s in contact]
				arc_s = contact[0][2]
				arc_e = contact[-1][2]

			new_csfs.append(CSF(
				csf_type=ex_type,
				disk_center=(disk_cx, disk_cy),
				disk_radius=ex_r,
				contact_region=contact_pts,
				extremum=(ex_x, ex_y),
				axis=[(ex_x, ex_y), (disk_cx, disk_cy)],
				contour_idx=c_idx,
				arc_param=best_s,
				arc_start=arc_s,
				arc_end=arc_e,
			))

	return _deduplicate_csfs(new_csfs, tol=sample_step * 3)


# ============================================================
# Concavity features (§4.2.2)
# ============================================================

def _compute_concavity_features(csf, all_params):
	"""Set tangent_pair and inward_normal for a concave CSF (§4.2.2).

	tangent_pair (τ, τ'): unit tangents at the two endpoints of the contact
	   region, oriented in the outline traversal direction.

	   τ  (at arc_start): approach tangent — one-sided backward look from the
	      start of the contact region into the LEFT support segment.  This
	      captures the direction the outline is coming FROM as it enters the
	      concavity, avoiding the corner bisector that a symmetric difference
	      would give at a sharp junction.

	   τ' (at arc_end): departure tangent — one-sided forward look from the
	      end of the contact region into the RIGHT support segment.  This
	      captures the direction the outline departs TOWARD after the concavity.

	inward_normal n = -(τ + τ') / |τ + τ'|.  Because τ and τ' both follow
	   the outline traversal direction, their sum points roughly along the
	   outline; negating it yields a vector that points into the shape (toward
	   the junction interior).

	   Fallback when τ + τ' ≈ 0 (symmetric concavity, tangents cancel):
	   use the chord-perpendicular of the contact region, oriented toward the
	   exterior disk center.

	Look-arc window: max(15, disk_radius × 0.5) font units.  Large enough to
	   clear the contact boundary noise; small enough not to span another CSF.
	"""
	params  = all_params[csf.contour_idx]
	contact = csf.contact_region

	if not contact:
		csf.tangent_pair  = ((1.0, 0.0), (1.0, 0.0))
		csf.inward_normal = (0.0, 0.0)
		return

	# Scale look distance to the feature size but keep it at least 15 units
	look_arc = max(15.0, csf.disk_radius * 0.5)

	if len(contact) == 1:
		# Degenerate contact (single point, e.g. sharp corner): symmetric estimate
		tau = _estimate_tangent(params, contact[0][0], contact[0][1], look_arc)
		csf.tangent_pair  = (tau, tau)
		csf.inward_normal = (0.0, 0.0)
		return

	# τ : approach tangent at the START of the contact region (into left support)
	tau_start = _estimate_tangent(
		params, contact[0][0], contact[0][1], look_arc, one_sided='back')

	# τ': departure tangent at the END of the contact region (into right support)
	tau_end = _estimate_tangent(
		params, contact[-1][0], contact[-1][1], look_arc, one_sided='fwd')

	csf.tangent_pair = (tau_start, tau_end)

	# n = -(τ + τ') normalised
	nx = -(tau_start[0] + tau_end[0])
	ny = -(tau_start[1] + tau_end[1])
	mag = math.hypot(nx, ny)

	if mag > _EPS:
		csf.inward_normal = (nx / mag, ny / mag)
	else:
		# Tangents cancel (symmetric concavity).
		# Fallback: chord-perpendicular of the contact region endpoints, oriented
		# toward the exterior disk center (which is outside the glyph).
		dx = contact[-1][0] - contact[0][0]
		dy = contact[-1][1] - contact[0][1]
		mag2 = math.hypot(dx, dy)
		if mag2 > _EPS:
			# Left normal of the contact chord
			perp = (-dy / mag2, dx / mag2)
			# Flip if it points away from the disk (disk is in exterior space)
			dc = csf.disk_center
			ex = csf.extremum
			if (dc[0] - ex[0]) * perp[0] + (dc[1] - ex[1]) * perp[1] < 0:
				perp = (-perp[0], -perp[1])
			csf.inward_normal = perp
		else:
			csf.inward_normal = (0.0, 1.0)


# ============================================================
# Main entry point
# ============================================================

def compute_csfs(contours, mat_graph, exterior_terminals,
				 sample_step=3.0, tau_c=_TAU_C, max_passes=3):
	"""Compute Curvilinear Shape Features (CSFs) for a glyph.

	Two-pass algorithm (Berio et al. §4.2):

	  Pass 1: Create initial CSFs from M terminals (convex) and M* terminals
	          (concave).  These capture the major outline features.

	  Pass 2+: Iteratively search each support segment for additional CSFs
	           that the medial axes missed (smooth curves, slight concavities).
	           New concave CSFs are accepted only if radius < τ_c × glyph_height.
	           Spiral artifacts (Tait-Kneser) are discarded.

	The returned CSFs fully cover the outline: adjacent CSFs share one
	support segment, with no gaps.

	Args:
		contours:           list of TypeRig Contour objects (the glyph outline)
		mat_graph:          MATGraph from compute_mat() — interior medial axis M
		exterior_terminals: list of (x, y, radius, cx, cy) from compute_exterior_mat()
		                    — exterior medial axis M* terminals that touch the outline
		sample_step:        outline sampling density in font units (default 3.0)
		tau_c:              radius threshold for new concave CSFs as fraction of
		                    glyph height (paper default: 0.15)
		max_passes:         maximum iterative refinement passes (default: 3)

	Returns:
		list of CSF objects
	"""
	# ── Estimate glyph height ──────────────────────────────────────────
	all_y = []
	for c in contours:
		for _x, y in sample_contour(c, step=sample_step * 2):
			all_y.append(y)
	glyph_height = (max(all_y) - min(all_y)) if all_y else 700.0
	concave_r_limit = tau_c * glyph_height

	# ── Parameterize every contour ─────────────────────────────────────
	all_params = [_parameterize_contour(c, sample_step) for c in contours]

	# ── Pass 1a: Convex CSFs from interior MAT terminals (M) ──────────
	csfs = []
	for terminal in mat_graph.terminals():
		csf = _csf_from_mat_terminal(terminal, all_params)
		if csf is not None:
			csfs.append(csf)

	# ── Pass 1b: Concave CSFs from exterior MAT terminals (M*) ────────
	for tx, ty, r, cx, cy in exterior_terminals:
		csf = _csf_from_ext_terminal(tx, ty, r, cx, cy, all_params)
		if csf is not None:
			csfs.append(csf)

	# ── Initial support segment assignment ────────────────────────────
	csfs = _sort_and_assign(csfs, all_params)

	# ── Pass 2+: Iterative search for missed curvature features ───────
	for _ in range(max_passes):
		new_csfs = _search_support_segments(
			csfs, all_params, concave_r_limit, sample_step)
		if not new_csfs:
			break
		new_csfs = _apply_spiral_filter(new_csfs, csfs)
		if not new_csfs:
			break
		csfs.extend(new_csfs)
		csfs = _sort_and_assign(csfs, all_params)

	# ── Concavity features (§4.2.2) ───────────────────────────────────
	for csf in csfs:
		if csf.csf_type == 'concave':
			_compute_concavity_features(csf, all_params)

	return csfs
