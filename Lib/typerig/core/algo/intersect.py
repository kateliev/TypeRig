# MODULE: TypeRig / Core / Algo / Intersect
# -----------------------------------------------------------
# Curve-curve intersection via bezier clipping (recursive
# subdivision on control-polygon bounding boxes). Pure math on
# 4-point tuples — no FontLab, no Qt, no object dependencies.
#
#   curve_curve_intersections(c1, c2, tol)   cubic vs cubic
#   line_to_cubic(p0, p1)                    degree-elevate a segment
#   split_cubic(curve, t)                    de Casteljau split
#
# Object-level wrappers live on CubicBezier.intersect_curve()
# and Contour.intersections() / self_intersections().
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '1.0.0'

# - Config -------------------------------
MAX_DEPTH = 40			# recursion cap — bounds work on coincident/overlapping curves
DEDUP_T = 1e-4			# t1 distance below which two hits are the same point
CLUSTER_T = 5e-3		# looser (t1, t2) clustering for adjacent leaf boxes


# - Primitives ---------------------------
def line_to_cubic(p0, p1):
	'''Degree-elevate a straight segment to a cubic 4-point tuple.
	(p0, p0 + d/3, p0 + 2d/3, p1) — exact representation of the line.
	'''
	x0, y0 = p0
	x1, y1 = p1
	dx = (x1 - x0) / 3.
	dy = (y1 - y0) / 3.

	return ((x0, y0), (x0 + dx, y0 + dy), (x0 + 2. * dx, y0 + 2. * dy), (x1, y1))


def split_cubic(curve, t=0.5):
	'''De Casteljau split of a 4-point tuple cubic at parameter t.
	Returns (left, right) 4-point tuples.
	'''
	(x0, y0), (x1, y1), (x2, y2), (x3, y3) = curve

	x01 = x0 + (x1 - x0) * t;   y01 = y0 + (y1 - y0) * t
	x12 = x1 + (x2 - x1) * t;   y12 = y1 + (y2 - y1) * t
	x23 = x2 + (x3 - x2) * t;   y23 = y2 + (y3 - y2) * t

	x012 = x01 + (x12 - x01) * t;   y012 = y01 + (y12 - y01) * t
	x123 = x12 + (x23 - x12) * t;   y123 = y12 + (y23 - y12) * t

	xm = x012 + (x123 - x012) * t;  ym = y012 + (y123 - y012) * t

	left = ((x0, y0), (x01, y01), (x012, y012), (xm, ym))
	right = ((xm, ym), (x123, y123), (x23, y23), (x3, y3))

	return left, right


def curve_bbox(curve):
	'''Control-polygon bounding box (xmin, ymin, xmax, ymax).
	Contains the curve by the convex-hull property; not tight.
	'''
	xs = (curve[0][0], curve[1][0], curve[2][0], curve[3][0])
	ys = (curve[0][1], curve[1][1], curve[2][1], curve[3][1])

	return (min(xs), min(ys), max(xs), max(ys))


def _boxes_overlap(a, b):
	return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


# - Intersection -------------------------
def curve_curve_intersections(c1, c2, tolerance=0.1):
	'''All intersections of two cubic beziers given as 4-point tuples
	((x0,y0),(x1,y1),(x2,y2),(x3,y3)).

	Bezier clipping via recursive subdivision: disjoint control-polygon
	boxes prune the pair; when both boxes are smaller than `tolerance`
	in both dimensions the accumulated (t1, t2) interval midpoints are
	reported as a hit. Results whose t1 nearly coincide are merged.

	NOTE: overlapping-COINCIDENT curves (identical or sharing an arc)
	intersect everywhere; the depth cap makes the call terminate but the
	returned hits are an unspecified sample of the overlap region.

	Args:
		c1, c2      : 4-point tuple cubics
		tolerance   : spatial precision of reported points (font units)

	Returns:
		list of (t1, t2, (x, y)) sorted by t1
	'''
	candidates = []

	stack = [(c1, 0., 1., c2, 0., 1., 0)]

	while stack:
		a, a_lo, a_hi, b, b_lo, b_hi, depth = stack.pop()

		box_a = curve_bbox(a)
		box_b = curve_bbox(b)

		if not _boxes_overlap(box_a, box_b):
			continue

		a_small = (box_a[2] - box_a[0]) <= tolerance and (box_a[3] - box_a[1]) <= tolerance
		b_small = (box_b[2] - box_b[0]) <= tolerance and (box_b[3] - box_b[1]) <= tolerance

		if (a_small and b_small) or depth >= MAX_DEPTH:
			x = ((box_a[0] + box_a[2]) * 0.5 + (box_b[0] + box_b[2]) * 0.5) * 0.5
			y = ((box_a[1] + box_a[3]) * 0.5 + (box_b[1] + box_b[3]) * 0.5) * 0.5
			candidates.append(((a_lo + a_hi) * 0.5, (b_lo + b_hi) * 0.5, (x, y)))
			continue

		a_mid = (a_lo + a_hi) * 0.5
		b_mid = (b_lo + b_hi) * 0.5

		if a_small:
			# Only split b
			b1, b2 = split_cubic(b)
			stack.append((a, a_lo, a_hi, b1, b_lo, b_mid, depth + 1))
			stack.append((a, a_lo, a_hi, b2, b_mid, b_hi, depth + 1))
		elif b_small:
			# Only split a
			a1, a2 = split_cubic(a)
			stack.append((a1, a_lo, a_mid, b, b_lo, b_hi, depth + 1))
			stack.append((a2, a_mid, a_hi, b, b_lo, b_hi, depth + 1))
		else:
			# Split both
			a1, a2 = split_cubic(a)
			b1, b2 = split_cubic(b)
			stack.append((a1, a_lo, a_mid, b1, b_lo, b_mid, depth + 1))
			stack.append((a1, a_lo, a_mid, b2, b_mid, b_hi, depth + 1))
			stack.append((a2, a_mid, a_hi, b1, b_lo, b_mid, depth + 1))
			stack.append((a2, a_mid, a_hi, b2, b_mid, b_hi, depth + 1))

	# - Deduplicate: exact near-misses (DEDUP_T) plus adjacent leaf boxes
	# that straddle one true crossing (CLUSTER_T on both parameters).
	candidates.sort(key=lambda hit: hit[0])
	result = []

	for t1, t2, pt in candidates:
		merged = False

		for kept in result:
			if abs(t1 - kept[0]) < DEDUP_T or (abs(t1 - kept[0]) < CLUSTER_T and abs(t2 - kept[1]) < CLUSTER_T):
				merged = True
				break

		if not merged:
			result.append((t1, t2, pt))

	return result


# - Test ---------------------------------
if __name__ == '__main__':
	fail = [0]

	def check(name, cond):
		print('{}: {}'.format('PASS' if cond else 'FAIL', name))
		if not cond:
			fail[0] += 1

	# Two straight-line "cubics" crossing at (50, 50)
	l1 = line_to_cubic((0., 0.), (100., 100.))
	l2 = line_to_cubic((0., 100.), (100., 0.))
	hits = curve_curve_intersections(l1, l2)
	check('cross lines: 1 hit', len(hits) == 1)
	check('cross lines: at (50,50)', abs(hits[0][2][0] - 50.) <= 0.2 and abs(hits[0][2][1] - 50.) <= 0.2)

	# Arch vs mirrored arch — 2 hits symmetric about x = 50
	arch = ((0., 0.), (0., 100.), (100., 100.), (100., 0.))
	mirror = ((0., 75.), (0., -25.), (100., -25.), (100., 75.))
	hits = curve_curve_intersections(arch, mirror)
	check('arch/mirror: 2 hits', len(hits) == 2)
	if len(hits) == 2:
		check('arch/mirror: symmetric', abs(hits[0][2][0] + hits[1][2][0] - 100.) <= 0.5)

	# Disjoint
	far = ((500., 500.), (550., 600.), (650., 600.), (700., 500.))
	check('disjoint: no hits', curve_curve_intersections(arch, far) == [])

	# Identical curves: depth cap terminates, sample of hits (unspecified)
	hits = curve_curve_intersections(arch, arch)
	check('identical: terminates', True)

	print('-' * 30)
	print('{} failure(s)'.format(fail[0]))
	raise SystemExit(1 if fail[0] else 0)
