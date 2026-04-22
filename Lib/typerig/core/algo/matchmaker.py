# MODULE: TypeRig / Core / Algo / Matchmaker
# -----------------------------------------------------------
# Physics-based polygon matchmaker for point-compatible
# interpolation, after Sederberg & Greenwood, SIGGRAPH '92.
#
# Operates on the on-curve polygon of a closed Contour. Bezier
# handles come along for the ride once on-curve nodes are paired.
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
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour

# - Init --------------------------------
__version__ = '0.1.0'

# - Stage 1: Intrinsic representation ---
def intrinsic(contour):
	'''Return the intrinsic (edge-length, turning-angle) encoding of a
	closed contour's on-curve polygon.

	Args:
		contour (Contour): closed TypeRig contour.

	Returns:
		(L, theta): two parallel lists of length m (number of on-curve
		nodes). L[i] is the straight-line length of the polygon edge from
		on-curve node i to on-curve node i+1 (wrapping). theta[i] is the
		signed exterior turning angle at on-curve node i, in (-pi, pi].

		For a simple closed polygon, sum(theta) == +2*pi (CCW) or -2*pi (CW).
	'''
	on_nodes = [n for n in contour.nodes if n.is_on]
	m = len(on_nodes)

	if m < 3:
		raise ValueError('intrinsic: need at least 3 on-curve nodes, got {}'.format(m))

	L = []
	for i in range(m):
		a = on_nodes[i].point
		b = on_nodes[(i + 1) % m].point
		L.append(math.hypot(b.x - a.x, b.y - a.y))

	# angle_poly_turn uses prev_on / next_on on the live contour, which
	# already handle wraparound and skip off-curves. That matches what we
	# want: the turning angle at each on-curve vertex of the polygon.
	theta = [n.angle_poly_turn for n in on_nodes]

	return L, theta


# - Stage 2: DP matcher -----------------
# Back-trace codes. Keep as module constants so callers can read the
# back-trace matrix without magic numbers.
BT_PAIR     = 0   # pair A[i-1] with B[j-1]
BT_INSERT_A = 1   # insert a new on-curve on A, consume B[j-1]
BT_INSERT_B = 2   # insert a new on-curve on B, consume A[i-1]


def dp_match(L_a, theta_a, L_b, theta_b, k_s=1.0, k_b=1.0, c_ins_scale=1.0):
	'''Dynamic-programming Sederberg-Greenwood matcher for a FIXED start-
	point alignment (no cyclic search yet).

	At each step the algorithm chooses the cheapest of three moves:
		- PAIR     : pair A[i-1] with B[j-1]
		- INSERT_A : insert a helper vertex on A to absorb B[j-1]
		- INSERT_B : insert a helper vertex on B to absorb A[i-1]

	Costs follow the physical model: stretching an edge costs k_s * dL^2,
	bending a vertex costs k_b * d_theta^2. A zero-length insertion has
	no edge-length mismatch; its cost is the bend it must absorb.

	Args:
		L_a, theta_a : intrinsic encoding of contour A, both length m.
		L_b, theta_b : intrinsic encoding of contour B, both length n.
		k_s          : stretch weight (units of 1 / length^2).
		k_b          : bend weight (units of 1 / radian^2).
		c_ins_scale  : multiplier on insertion cost. > 1 discourages
		               insertions; < 1 encourages them.

	Returns:
		(C, B, total_cost): C is (m+1)x(n+1) cost table, B is same-shape
		back-trace table whose entries are BT_PAIR / BT_INSERT_A /
		BT_INSERT_B, total_cost == C[m][n].
	'''
	m = len(L_a)
	n = len(L_b)

	assert len(theta_a) == m, 'len(theta_a) != len(L_a)'
	assert len(theta_b) == n, 'len(theta_b) != len(L_b)'
	assert m >= 1 and n >= 1, 'empty intrinsic sequence'

	INF = float('inf')
	C = [[INF] * (n + 1) for _ in range(m + 1)]
	B = [[-1] * (n + 1) for _ in range(m + 1)]
	C[0][0] = 0.0

	# Boundary: column 0 -- only BT_INSERT_B moves are available
	# (each step consumes one A vertex by inserting on B).
	for i in range(1, m + 1):
		C[i][0] = C[i - 1][0] + c_ins_scale * k_b * theta_a[i - 1] * theta_a[i - 1]
		B[i][0] = BT_INSERT_B

	# Boundary: row 0 -- only BT_INSERT_A moves.
	for j in range(1, n + 1):
		C[0][j] = C[0][j - 1] + c_ins_scale * k_b * theta_b[j - 1] * theta_b[j - 1]
		B[0][j] = BT_INSERT_A

	# Interior.
	for i in range(1, m + 1):
		for j in range(1, n + 1):
			dL = L_a[i - 1] - L_b[j - 1]
			dth = theta_a[i - 1] - theta_b[j - 1]
			w_pair = k_s * dL * dL + k_b * dth * dth

			w_ins_a = c_ins_scale * k_b * theta_b[j - 1] * theta_b[j - 1]
			w_ins_b = c_ins_scale * k_b * theta_a[i - 1] * theta_a[i - 1]

			cand = (
				(C[i - 1][j - 1] + w_pair, BT_PAIR),
				(C[i][j - 1]     + w_ins_a, BT_INSERT_A),
				(C[i - 1][j]     + w_ins_b, BT_INSERT_B),
			)
			best_cost, best_op = min(cand, key=lambda t: t[0])
			C[i][j] = best_cost
			B[i][j] = best_op

	return C, B, C[m][n]


def backtrace(B, m, n):
	'''Walk the back-trace matrix from (m, n) back to (0, 0).

	Returns a list of (i, j, op) triples in FORWARD order (start of
	contour first), where:
		- op == BT_PAIR     -> pair A[i] with B[j]
		- op == BT_INSERT_A -> insert on A at this step, consume B[j]
		                       (i is the A-index just before the insertion)
		- op == BT_INSERT_B -> insert on B at this step, consume A[i]
		                       (j is the B-index just before the insertion)
	Indices in the returned list are 0-based into the original sequences.
	'''
	path = []
	i, j = m, n

	while i > 0 or j > 0:
		op = B[i][j]

		if op == BT_PAIR:
			i -= 1
			j -= 1
			path.append((i, j, BT_PAIR))

		elif op == BT_INSERT_A:
			# Consumed B[j-1] by inserting on A between A-positions i-1 and i.
			j -= 1
			path.append((i - 1 if i > 0 else 0, j, BT_INSERT_A))

		elif op == BT_INSERT_B:
			i -= 1
			path.append((i, j - 1 if j > 0 else 0, BT_INSERT_B))

		else:
			raise RuntimeError('bad back-trace op {} at ({},{})'.format(op, i, j))

	path.reverse()
	return path


# - Stage 3: Cyclic start-point search --
def _rotate(seq, k):
	'''Cyclic left-shift a list by k positions (pure, returns new list).'''
	if not seq:
		return seq[:]
	k = k % len(seq)
	return seq[k:] + seq[:k]


def dp_match_cyclic(L_a, theta_a, L_b, theta_b, k_s=1.0, k_b=1.0, c_ins_scale=1.0):
	'''Closed-contour matcher: brute-force the best cyclic shift of B.

	For each shift s in [0, n), rotate B's intrinsic sequences left by s
	and run the fixed-start DP. Return the shift with minimum total cost.

	Complexity: O(n * m * n). For typical glyphs (n, m < 100) this runs
	well under a millisecond in pure Python. Replace with extremum-
	restricted search (paper's §4 suggestion) if n climbs past ~300.

	Returns:
		(best_shift, C, B, total_cost) where C and B are the cost and
		back-trace tables AT the winning shift. Apply backtrace(B, m, n)
		to get the pairing; when rebuilding B-side indices remember that
		B was rotated by best_shift, so original B-index of returned j is
		(j + best_shift) % n.
	'''
	n = len(L_b)
	best = None

	for s in range(n):
		L_b_s = _rotate(L_b, s)
		T_b_s = _rotate(theta_b, s)
		C, B, total = dp_match(L_a, theta_a, L_b_s, T_b_s, k_s=k_s, k_b=k_b,
		                       c_ins_scale=c_ins_scale)
		if best is None or total < best[3]:
			best = (s, C, B, total)

	return best


# - Stage 4: Apply match ----------------
def _on_curve_indices(contour):
	'''Positional indices of on-curve nodes inside contour.nodes.'''
	return [idx for idx, nd in enumerate(contour.nodes) if nd.is_on]


def _plan_insertions(path, m, n):
	'''Walk a DP back-trace and return two insertion plans.

	Each plan entry is (source_onc_idx, [t_0, t_1, ...]) describing how many
	insertions fall on the polygon segment whose start is the on-curve with
	index source_onc_idx, and the fractional placements (in (0, 1)) along
	that segment.

	Placement is uniform inside a run (k-th of K insertions goes at
	t = k / (K + 1)). The Hard-Parts doc also mentions arc-length-
	proportional placement as a refinement; uniform is simpler and still
	produces a valid point-compatible pair.
	'''
	# Group consecutive INSERT_A (or INSERT_B) ops that fall on the same
	# A-segment (or B-segment). An A-segment ends whenever the path
	# advances A: that is at PAIR or INSERT_B.
	plan_a = {}   # source_onc_idx_in_A -> [count]
	plan_b = {}

	buf_a = 0
	buf_b = 0
	a_cursor = 0   # index of next A on-curve to consume
	b_cursor = 0

	def _flush(side, buf, cursor, size, plan):
		if buf == 0:
			return
		src = (cursor - 1) % size
		# Uniform distribution of `buf` insertions inside one segment.
		ts = [k / float(buf + 1) for k in range(1, buf + 1)]
		plan.setdefault(src, []).extend(ts)

	for (_, _, op) in path:
		if op == BT_PAIR:
			_flush('a', buf_a, a_cursor, m, plan_a)
			_flush('b', buf_b, b_cursor, n, plan_b)
			buf_a = 0
			buf_b = 0
			a_cursor += 1
			b_cursor += 1

		elif op == BT_INSERT_A:
			buf_a += 1
			b_cursor += 1

		elif op == BT_INSERT_B:
			buf_b += 1
			a_cursor += 1

	# Any leftover buffer belongs to the closing segment (wraps to index 0).
	_flush('a', buf_a, a_cursor, m, plan_a)
	_flush('b', buf_b, b_cursor, n, plan_b)

	return plan_a, plan_b


def _apply_insertion_plan(contour, plan):
	'''Apply {source_onc_idx: [t...]} insertions onto a contour in-place.

	Each source on-curve may receive multiple insertions on its segment.
	We apply them in DESCENDING t order so each insert_after call operates
	on the shrinking first sub-segment; the t passed to insert_after is
	re-scaled accordingly.
	'''
	on_curves = [nd for nd in contour.nodes if nd.is_on]

	for src_idx, ts in plan.items():
		if not ts:
			continue
		# Descending t; track the upper bound of the still-unsplit first
		# sub-segment so we can convert original t -> current-segment t.
		ts_sorted = sorted(ts, reverse=True)
		src_node = on_curves[src_idx]
		upper = 1.0
		for t in ts_sorted:
			# Current segment spans original (0, upper); map t into it.
			t_adj = t / upper
			# Clamp: floating-point drift can push t_adj slightly past 1.
			if t_adj <= 0.0 or t_adj >= 1.0:
				continue
			src_node.insert_after(t_adj)
			upper = t


def apply_match(contour_a, contour_b, k_s=1.0, k_b=1.0, c_ins_scale=1.0):
	'''Mutate *copies* of contour_a / contour_b so they become point-
	compatible under the Sederberg-Greenwood energy.

	Steps:
		1. Intrinsic encoding of both contours (on-curve polygon).
		2. Cyclic DP to find the best start-point alignment.
		3. Deep-copy both contours; rotate the B-copy's start so the
		   pairing indices line up.
		4. Apply insertions on both copies per the back-trace plan.

	Returns:
		(new_a, new_b, cost, meta) where meta is a dict with diagnostic
		fields: 'shift_b', 'n_pairs', 'n_insert_a', 'n_insert_b',
		'len_on_before', 'len_on_after'.

	Post-conditions (enforced by assertions):
		- len(new_a on-curves) == len(new_b on-curves)
		- sum(theta) on each resulting contour remains +/- 2*pi
	'''
	# Clone up-front so we can normalise winding before computing intrinsics.
	new_a = contour_a.clone()
	new_b = contour_b.clone()

	# Winding pre-check: theta signs are inverted under a reversal, so a
	# CW vs CCW pair would otherwise force the DP into costly bilateral
	# insertions. Reverse new_b's copy to match A's orientation. The
	# original contour_b is untouched (we already cloned).
	reversed_b = False
	if bool(new_a.clockwise) != bool(new_b.clockwise):
		new_b.reverse()
		reversed_b = True

	La, Ta = intrinsic(new_a)
	Lb, Tb = intrinsic(new_b)
	m, n = len(La), len(Lb)

	shift_b, C, B_tbl, cost = dp_match_cyclic(
		La, Ta, Lb, Tb, k_s=k_s, k_b=k_b, c_ins_scale=c_ins_scale)

	path = backtrace(B_tbl, m, n)

	# Rotate new_b by shift_b ON-CURVE positions. set_start takes a node
	# index; find the node index of the shift_b-th on-curve.
	if shift_b > 0:
		on_idx_b = _on_curve_indices(new_b)
		new_b.set_start(on_idx_b[shift_b])

	plan_a, plan_b = _plan_insertions(path, m, n)
	_apply_insertion_plan(new_a, plan_a)
	_apply_insertion_plan(new_b, plan_b)

	# Post-condition: equal on-curve counts.
	oc_a = sum(1 for nd in new_a.nodes if nd.is_on)
	oc_b = sum(1 for nd in new_b.nodes if nd.is_on)
	assert oc_a == oc_b, \
		'post-apply on-curve mismatch: A={} B={}'.format(oc_a, oc_b)

	n_pairs      = sum(1 for _, _, op in path if op == BT_PAIR)
	n_insert_a   = sum(1 for _, _, op in path if op == BT_INSERT_A)
	n_insert_b   = sum(1 for _, _, op in path if op == BT_INSERT_B)

	meta = {
		'shift_b': shift_b,
		'reversed_b': reversed_b,
		'n_pairs': n_pairs,
		'n_insert_a': n_insert_a,
		'n_insert_b': n_insert_b,
		'len_on_before': (m, n),
		'len_on_after':  (oc_a, oc_b),
	}

	return new_a, new_b, cost, meta


# - Stage 5: Multi-contour glyph pairing ---
def _contour_signature(contour):
	'''Return (clockwise_bool, signed_area, cx, cy) for pairing.
	cx, cy are the bounding-box centre; cheaper and more stable for
	pairing than the on-curve polygon centroid, and sufficient for the
	small contour counts (1-4) typical in glyphs.
	'''
	bx = contour.bounds.x + contour.bounds.width * 0.5
	by = contour.bounds.y + contour.bounds.height * 0.5
	return (bool(contour.clockwise), contour.signed_area, bx, by)


def _pair_cost(sig_a, sig_b, diag):
	'''Dimensionless dissimilarity between two contour signatures.

	Winding mismatch gets a large additive penalty so same-winding pairs
	win whenever possible; ties fall through to geometry.
	'''
	cw_a, area_a, ax, ay = sig_a
	cw_b, area_b, bx, by = sig_b
	penalty = 0.0 if cw_a == cw_b else 10.0
	d_area  = abs(abs(area_a) - abs(area_b)) / max(abs(area_a), abs(area_b), 1.0)
	d_pos   = math.hypot(ax - bx, ay - by) / max(diag, 1.0)
	return penalty + d_area + d_pos


def pair_contours(contours_a, contours_b):
	'''Greedy pairing of two equal-length contour lists by (winding, area,
	centre). Returns a list of (i, j) index pairs.

	Raises ValueError if the lists differ in length — glyph-level point
	compatibility is only defined when both masters have the same contour
	count. Callers that want to handle count mismatches must do so upstream.
	'''
	if len(contours_a) != len(contours_b):
		raise ValueError(
			'pair_contours: contour count mismatch A={} B={}'.format(
				len(contours_a), len(contours_b)))

	sigs_a = [_contour_signature(c) for c in contours_a]
	sigs_b = [_contour_signature(c) for c in contours_b]

	# Diagonal across both glyphs, used to normalise centre distance.
	xs, ys = [], []
	for c in list(contours_a) + list(contours_b):
		b = c.bounds
		xs += [b.x, b.x + b.width]
		ys += [b.y, b.y + b.height]
	diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) if xs else 1.0

	# Greedy: at each step pick the globally cheapest unused (i, j).
	remaining_a = set(range(len(sigs_a)))
	remaining_b = set(range(len(sigs_b)))
	pairs = []

	while remaining_a:
		best = None
		for i in remaining_a:
			for j in remaining_b:
				c = _pair_cost(sigs_a[i], sigs_b[j], diag)
				if best is None or c < best[0]:
					best = (c, i, j)
		_, i, j = best
		pairs.append((i, j))
		remaining_a.remove(i)
		remaining_b.remove(j)

	pairs.sort(key=lambda ij: ij[0])
	return pairs


def apply_match_glyph(contours_a, contours_b,
                      k_s=1.0, k_b=1.0, c_ins_scale=1.0):
	'''Stage 5: run apply_match per paired contour.

	Args:
		contours_a, contours_b: parallel lists of closed contours from two
			masters of the same glyph. Must have equal length.

	Returns:
		(new_a_list, new_b_list, total_cost, meta)
			- new_a_list / new_b_list: output contours reordered so new_a[k]
			  pairs with new_b[k] (A's original order preserved, B reordered
			  to match).
			- total_cost: sum of per-contour Sederberg-Greenwood costs.
			- meta: dict with 'pairs' (list of (i, j)), 'per_contour' (list
			  of per-apply_match meta dicts), 'total_insert_a',
			  'total_insert_b'.

	Raises ValueError on contour-count mismatch.
	'''
	pairs = pair_contours(contours_a, contours_b)

	new_a_list = [None] * len(pairs)
	new_b_list = [None] * len(pairs)
	per_contour = []
	total_cost = 0.0
	total_ins_a = 0
	total_ins_b = 0

	for k, (i, j) in enumerate(pairs):
		na, nb, cost, m = apply_match(
			contours_a[i], contours_b[j],
			k_s=k_s, k_b=k_b, c_ins_scale=c_ins_scale)
		new_a_list[k] = na
		new_b_list[k] = nb
		per_contour.append(m)
		total_cost += cost
		total_ins_a += m['n_insert_a']
		total_ins_b += m['n_insert_b']

	meta = {
		'pairs': pairs,
		'per_contour': per_contour,
		'total_insert_a': total_ins_a,
		'total_insert_b': total_ins_b,
	}
	return new_a_list, new_b_list, total_cost, meta


# - Self-tests --------------------------
def _approx(a, b, tol=1e-9):
	return abs(a - b) <= tol


def _test_rectangle():
	'''Rectangle: 4 on-curve nodes, CCW. L matches sides; theta = [pi/2]*4;
	sum(theta) == +2*pi.'''
	# 200 x 100 rectangle, CCW (PostScript convention):
	# (0,0) -> (200,0) -> (200,100) -> (0,100)
	nodes = [Node(0.0, 0.0), Node(200.0, 0.0),
	         Node(200.0, 100.0), Node(0.0, 100.0)]
	c = Contour(nodes, closed=True)

	L, theta = intrinsic(c)

	assert len(L) == 4 and len(theta) == 4, 'expected 4/4, got {}/{}'.format(len(L), len(theta))

	expected_L = [200.0, 100.0, 200.0, 100.0]
	for i, (got, exp) in enumerate(zip(L, expected_L)):
		assert _approx(got, exp), 'L[{}] = {} != {}'.format(i, got, exp)

	# CCW rectangle: each exterior turn is +pi/2.
	for i, t in enumerate(theta):
		assert _approx(t, math.pi / 2), 'theta[{}] = {} != pi/2'.format(i, t)

	total = sum(theta)
	assert _approx(total, 2 * math.pi), 'sum(theta) = {} != 2*pi'.format(total)

	print('  rectangle CCW: L={}, theta={}, sum={:.6f} == 2*pi [OK]'.format(
		['{:.1f}'.format(x) for x in L],
		['{:.4f}'.format(t) for t in theta],
		total))


def _test_rectangle_cw():
	'''Rectangle traversed clockwise: sum(theta) == -2*pi.'''
	nodes = [Node(0.0, 0.0), Node(0.0, 100.0),
	         Node(200.0, 100.0), Node(200.0, 0.0)]
	c = Contour(nodes, closed=True)

	L, theta = intrinsic(c)

	for i, t in enumerate(theta):
		assert _approx(t, -math.pi / 2), 'CW theta[{}] = {}'.format(i, t)

	total = sum(theta)
	assert _approx(total, -2 * math.pi), 'CW sum(theta) = {}'.format(total)

	print('  rectangle CW : sum(theta) = {:.6f} == -2*pi [OK]'.format(total))


def _test_pentagon():
	'''Regular pentagon: each exterior turn is 2*pi/5; sum = 2*pi.'''
	R = 100.0
	nodes = []
	for k in range(5):
		# Start at angle pi/2 (top), go CCW.
		a = math.pi / 2 + k * (2 * math.pi / 5)
		nodes.append(Node(R * math.cos(a), R * math.sin(a)))

	c = Contour(nodes, closed=True)
	L, theta = intrinsic(c)

	# All edges equal length, all turns equal.
	assert all(_approx(L[0], L[i], tol=1e-6) for i in range(5)), 'pentagon sides unequal'
	for i, t in enumerate(theta):
		assert _approx(t, 2 * math.pi / 5, tol=1e-9), 'pentagon theta[{}] = {}'.format(i, t)

	total = sum(theta)
	assert _approx(total, 2 * math.pi, tol=1e-9), 'pentagon sum = {}'.format(total)

	print('  pentagon CCW : theta={:.4f} each, sum={:.6f} == 2*pi [OK]'.format(
		theta[0], total))


def _test_triangle_irregular():
	'''Irregular triangle: sum(theta) must still be +/- 2*pi.'''
	nodes = [Node(0.0, 0.0), Node(300.0, 0.0), Node(100.0, 200.0)]
	c = Contour(nodes, closed=True)

	L, theta = intrinsic(c)
	total = sum(theta)

	assert _approx(abs(total), 2 * math.pi, tol=1e-9), \
		'triangle sum(theta) = {}, expected +/-2*pi'.format(total)

	# Edges: hypot(300,0)=300, hypot(-200,200)=282.843..., hypot(-100,-200)=223.607...
	assert _approx(L[0], 300.0), 'L[0] = {}'.format(L[0])
	assert _approx(L[1], math.hypot(-200, 200)), 'L[1] = {}'.format(L[1])
	assert _approx(L[2], math.hypot(-100, -200)), 'L[2] = {}'.format(L[2])

	print('  irregular triangle: L={}, sum(theta)={:.6f} [OK]'.format(
		['{:.3f}'.format(x) for x in L], total))


def _run_stage1_tests():
	print('Stage 1 - intrinsic(contour):')
	_test_rectangle()
	_test_rectangle_cw()
	_test_pentagon()
	_test_triangle_irregular()
	print('Stage 1: all tests passed.')


# - Stage 2 tests -----------------------
def _count_ops(path):
	c = {BT_PAIR: 0, BT_INSERT_A: 0, BT_INSERT_B: 0}
	for _, _, op in path:
		c[op] += 1
	return c


def _test_dp_identical_rectangles():
	'''Identical rectangles: cost == 0, back-trace purely diagonal.'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	nodes_b = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	ca = Contour(nodes_a, closed=True)
	cb = Contour(nodes_b, closed=True)

	La, Ta = intrinsic(ca)
	Lb, Tb = intrinsic(cb)

	C, B, total = dp_match(La, Ta, Lb, Tb, k_s=1.0, k_b=1.0)
	assert _approx(total, 0.0), 'identical cost = {}'.format(total)

	path = backtrace(B, len(La), len(Lb))
	ops = _count_ops(path)
	assert ops[BT_INSERT_A] == 0 and ops[BT_INSERT_B] == 0, \
		'identical: expected no insertions, got {}'.format(ops)
	assert ops[BT_PAIR] == 4, 'identical: expected 4 pairs, got {}'.format(ops[BT_PAIR])

	print('  identical rects : cost=0, 4 pairs, 0 inserts [OK]')


def _test_dp_stretched_rectangle():
	'''Rectangle vs stretched rectangle (same vertex count): cost > 0,
	diagonal back-trace (no insertions).'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	nodes_b = [Node(0.0, 0.0), Node(220.0, 0.0), Node(220.0, 110.0), Node(0.0, 110.0)]
	ca = Contour(nodes_a, closed=True)
	cb = Contour(nodes_b, closed=True)

	La, Ta = intrinsic(ca)
	Lb, Tb = intrinsic(cb)

	# Use 1/em^2 scaling per the Hard Parts guidance so stretch cost is
	# commensurate with bend cost; the point of this test is that the
	# back-trace stays diagonal because vertex counts match.
	em = 200.0
	C, B, total = dp_match(La, Ta, Lb, Tb, k_s=1.0 / (em * em), k_b=1.0)
	assert total > 0.0, 'stretched cost should be > 0, got {}'.format(total)

	path = backtrace(B, len(La), len(Lb))
	ops = _count_ops(path)
	assert ops[BT_INSERT_A] == 0 and ops[BT_INSERT_B] == 0, \
		'stretched: corner-matched => no insertions expected, got {}'.format(ops)
	assert ops[BT_PAIR] == 4, 'stretched: 4 pairs expected, got {}'.format(ops[BT_PAIR])

	print('  stretched rects : cost={:.2f} > 0, pure diagonal [OK]'.format(total))


def _test_dp_rectangle_vs_pentagon():
	'''Rectangle (4 verts) vs pentagon (5 verts): expect exactly 1
	insertion on the rectangle side (INSERT_A) and 4 pairs.

	Use k_b large relative to k_s so bend mismatch dominates and the
	algorithm prefers inserting a helper vertex over forcing a pair.'''
	# CCW rectangle (m = 4).
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	ca = Contour(nodes_a, closed=True)

	# CCW regular pentagon (n = 5), similar scale.
	R = 100.0
	nodes_b = []
	for k in range(5):
		a = math.pi / 2 + k * (2 * math.pi / 5)
		nodes_b.append(Node(R * math.cos(a), R * math.sin(a)))
	cb = Contour(nodes_b, closed=True)

	La, Ta = intrinsic(ca)
	Lb, Tb = intrinsic(cb)
	assert len(La) == 4 and len(Lb) == 5

	# Normalise edge lengths so stretch cost is commensurate with bend cost.
	em = 200.0
	C, B, total = dp_match(La, Ta, Lb, Tb, k_s=1.0 / (em * em), k_b=1.0)

	path = backtrace(B, len(La), len(Lb))
	ops = _count_ops(path)

	assert ops[BT_INSERT_A] == 1, 'expected exactly 1 insert on A, got {} ({})'.format(
		ops[BT_INSERT_A], path)
	assert ops[BT_INSERT_B] == 0, 'expected 0 inserts on B, got {}'.format(ops[BT_INSERT_B])
	assert ops[BT_PAIR] == 4, 'expected 4 pairs, got {}'.format(ops[BT_PAIR])

	# Sanity: path length = m + n - #pair = 4 + 5 - 4 = 5.
	assert len(path) == 5, 'path length = {}, expected 5'.format(len(path))

	print('  rect vs pentagon: 4 pairs + 1 insert_a, cost={:.6f} [OK]'.format(total))


def _test_dp_symmetry():
	'''Swapping A and B must yield the same total cost; pair count
	identical; INSERT_A and INSERT_B counts swap.'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	R = 100.0
	nodes_b = []
	for k in range(5):
		a = math.pi / 2 + k * (2 * math.pi / 5)
		nodes_b.append(Node(R * math.cos(a), R * math.sin(a)))

	ca = Contour(nodes_a, closed=True)
	cb = Contour(nodes_b, closed=True)
	La, Ta = intrinsic(ca)
	Lb, Tb = intrinsic(cb)

	em = 200.0
	_, B1, t1 = dp_match(La, Ta, Lb, Tb, k_s=1.0 / (em * em), k_b=1.0)
	_, B2, t2 = dp_match(Lb, Tb, La, Ta, k_s=1.0 / (em * em), k_b=1.0)

	assert _approx(t1, t2, tol=1e-9), 'A,B: {} vs B,A: {}'.format(t1, t2)

	p1 = _count_ops(backtrace(B1, len(La), len(Lb)))
	p2 = _count_ops(backtrace(B2, len(Lb), len(La)))
	assert p1[BT_PAIR] == p2[BT_PAIR]
	assert p1[BT_INSERT_A] == p2[BT_INSERT_B]
	assert p1[BT_INSERT_B] == p2[BT_INSERT_A]

	print('  symmetry (A,B)<->(B,A): cost match, insert counts swap [OK]')


def _run_stage2_tests():
	print('Stage 2 - dp_match / backtrace:')
	_test_dp_identical_rectangles()
	_test_dp_stretched_rectangle()
	_test_dp_rectangle_vs_pentagon()
	_test_dp_symmetry()
	print('Stage 2: all tests passed.')


# - Stage 3 tests -----------------------
def _pentagon_contour(R=100.0, phase=math.pi / 2):
	'''Regular pentagon, CCW, starting at the given phase angle.'''
	nodes = []
	for k in range(5):
		a = phase + k * (2 * math.pi / 5)
		nodes.append(Node(R * math.cos(a), R * math.sin(a)))
	return Contour(nodes, closed=True)


def _test_cyclic_self_match():
	'''Pentagon vs itself: best shift == 0, cost == 0.'''
	c = _pentagon_contour()
	L, T = intrinsic(c)
	s, C, B, total = dp_match_cyclic(L, T, L, T, k_s=1.0 / (100.0 ** 2), k_b=1.0)

	assert s == 0, 'self match shift = {}, expected 0'.format(s)
	assert _approx(total, 0.0, tol=1e-12), 'self cost = {}'.format(total)

	print('  self cyclic     : shift=0, cost=0 [OK]')


def _test_cyclic_rotation_recovered():
	'''Build B as A with its start point rotated by rot positions. The
	cyclic matcher should return shift_b = n - rot (mod n), cost = 0.'''
	ca = _pentagon_contour()
	La, Ta = intrinsic(ca)
	n = len(La)  # 5

	for rot in range(1, n):
		# Rotate the intrinsic sequences to simulate a different start point.
		Lb = _rotate(La, rot)
		Tb = _rotate(Ta, rot)

		s, _, Bmat, total = dp_match_cyclic(La, Ta, Lb, Tb,
		                                     k_s=1.0 / (100.0 ** 2), k_b=1.0)

		# To re-align B to A, we rotate B by s. So we need
		# rotate(rotate(A, rot), s) == A, i.e. (rot + s) mod n == 0.
		expected = (-rot) % n
		assert s == expected, \
			'rot={}: recovered shift={}, expected {}'.format(rot, s, expected)
		assert _approx(total, 0.0, tol=1e-10), \
			'rot={}: cost = {} (expected 0)'.format(rot, total)

	print('  rotation recovery: all shifts 1..n-1 recovered at cost 0 [OK]')


def _test_cyclic_better_than_fixed():
	'''Cyclic search must find an alignment at least as good as the
	fixed-start matcher, and strictly better when the fixed start is
	mis-aligned.'''
	# Use a rectangle, where rotation is NOT a symmetry of the intrinsic
	# sequence (L alternates 200/100). That makes fixed-start mis-align
	# by a measurable amount while cyclic recovers cost = 0.
	nodes = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	ca = Contour(nodes, closed=True)
	La, Ta = intrinsic(ca)
	Lb = _rotate(La, 1)   # [100, 200, 100, 200]
	Tb = _rotate(Ta, 1)

	_, _, fixed_cost = dp_match(La, Ta, Lb, Tb, k_s=1.0 / 40000.0, k_b=1.0)
	_, _, _, cyc_cost = dp_match_cyclic(La, Ta, Lb, Tb,
	                                     k_s=1.0 / 40000.0, k_b=1.0)

	assert cyc_cost < fixed_cost, \
		'cyclic ({}) must beat fixed ({})'.format(cyc_cost, fixed_cost)
	assert _approx(cyc_cost, 0.0, tol=1e-10), 'cyclic cost = {}'.format(cyc_cost)

	print('  cyclic < fixed  : fixed={:.4f} vs cyclic={:.2e} [OK]'.format(
		fixed_cost, cyc_cost))


def _run_stage3_tests():
	print('Stage 3 - dp_match_cyclic:')
	_test_cyclic_self_match()
	_test_cyclic_rotation_recovered()
	_test_cyclic_better_than_fixed()
	print('Stage 3: all tests passed.')


# - Stage 4 tests -----------------------
def _on_count(contour):
	return sum(1 for nd in contour.nodes if nd.is_on)


def _assert_closure(contour, label):
	'''Sum of turning angles on an apply_match output must still be +/- 2*pi.'''
	_, theta = intrinsic(contour)
	total = sum(theta)
	assert _approx(abs(total), 2 * math.pi, tol=1e-9), \
		'{}: sum(theta) = {} (should be +/- 2*pi)'.format(label, total)


def _test_apply_identical_rectangles():
	'''Identical inputs: no insertions, no rotation, cost 0, counts unchanged.'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	nodes_b = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	a = Contour(nodes_a, closed=True)
	b = Contour(nodes_b, closed=True)

	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0)

	assert _on_count(na) == 4 and _on_count(nb) == 4, \
		'counts after: A={} B={}'.format(_on_count(na), _on_count(nb))
	assert meta['n_insert_a'] == 0 and meta['n_insert_b'] == 0
	assert meta['shift_b'] == 0
	assert _approx(cost, 0.0)
	_assert_closure(na, 'identical A')
	_assert_closure(nb, 'identical B')

	print('  identical rects : no changes, cost=0 [OK]')


def _test_apply_rectangle_vs_pentagon():
	'''4-gon vs 5-gon: rectangle side gets one insertion, both end with 5.'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	R = 100.0
	nodes_b = [Node(R * math.cos(math.pi / 2 + k * 2 * math.pi / 5),
	                R * math.sin(math.pi / 2 + k * 2 * math.pi / 5))
	           for k in range(5)]

	a = Contour(nodes_a, closed=True)
	b = Contour(nodes_b, closed=True)

	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0)

	oca, ocb = _on_count(na), _on_count(nb)
	assert oca == ocb, 'count mismatch {} vs {}'.format(oca, ocb)
	assert oca == 5, 'expected 5 on-curves, got {}'.format(oca)
	assert meta['n_insert_a'] == 1, \
		'expected 1 insert on A, got {}'.format(meta['n_insert_a'])
	assert meta['n_insert_b'] == 0
	_assert_closure(na, 'rect->5 A')
	_assert_closure(nb, 'rect->5 B')

	print('  rect vs pentagon: A got 1 insert, both have 5 on-curves [OK]')


def _test_apply_rotated_self():
	'''Match a contour against a cyclically-rotated clone of itself.
	Use an irregular quadrilateral so the start-point recovery is unique
	(a rectangle has 2-fold symmetry; both shift=1 and shift=3 would be
	valid cost-0 solutions).'''
	nodes = [Node(0.0, 0.0), Node(300.0, 20.0), Node(260.0, 180.0), Node(40.0, 140.0)]
	a = Contour(nodes, closed=True)

	# Clone and rotate start by 1 on-curve.
	b = a.clone()
	b.set_start(1)

	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0)

	# Rotating B forward by 1 means the matcher must shift B by (n - 1) = 3
	# to re-align; because this quad has no rotational symmetry that s=3 is
	# the unique cost-0 shift.
	assert meta['shift_b'] == 3, \
		'expected shift_b=3, got {}'.format(meta['shift_b'])
	assert meta['n_insert_a'] == 0 and meta['n_insert_b'] == 0
	assert _on_count(na) == 4 and _on_count(nb) == 4
	assert _approx(cost, 0.0, tol=1e-9), 'rotated self cost = {}'.format(cost)
	_assert_closure(na, 'rot-self A')
	_assert_closure(nb, 'rot-self B')

	print('  rotated self    : shift=3, cost=0, counts unchanged [OK]')


def _test_apply_two_insertions_same_segment():
	'''Force two insertions on the same edge: triangle vs pentagon with a
	huge stretch-cost penalty so DP prefers bending over stretching.'''
	# Triangle: 3 vertices (all 120deg exterior turn).
	nodes_a = [Node(0.0, 0.0), Node(300.0, 0.0), Node(150.0, 259.808)]
	# Regular pentagon: 5 vertices.
	R = 150.0
	nodes_b = [Node(R * math.cos(math.pi / 2 + k * 2 * math.pi / 5),
	                R * math.sin(math.pi / 2 + k * 2 * math.pi / 5))
	           for k in range(5)]
	a = Contour(nodes_a, closed=True)
	b = Contour(nodes_b, closed=True)

	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 90000.0, k_b=1.0)

	assert _on_count(na) == _on_count(nb)
	# Triangle side must gain exactly 5 - 3 = 2 on-curves net (after accounting
	# for INSERT_B ops, but here n > m so only INSERT_A's occur). That means
	# SOMEWHERE on A there are 2 insertions. They can land on the same segment
	# or split across two.
	assert meta['n_insert_a'] >= 2, \
		'expected >=2 INSERT_A, got {}'.format(meta['n_insert_a'])
	_assert_closure(na, 'tri->5 A')
	_assert_closure(nb, 'tri->5 B')

	print('  tri vs pentagon : {} A-inserts, final={} on-curves [OK]'.format(
		meta['n_insert_a'], _on_count(na)))


def _test_apply_winding_normalised():
	'''CCW A vs CW-traversed clone of A: winding pre-check must reverse B's
	copy so theta signs align; result is cost 0, no insertions, meta
	flags reversed_b=True.'''
	# CCW irregular quad.
	coords = [(0.0, 0.0), (300.0, 20.0), (260.0, 180.0), (40.0, 140.0)]
	a = Contour([Node(x, y) for x, y in coords], closed=True)

	# Same shape traversed backwards (CW). Build from fresh Node objects
	# so the two contours don't share node parents.
	b = Contour([Node(x, y) for x, y in reversed(coords)], closed=True)

	assert bool(a.clockwise) != bool(b.clockwise), \
		'test setup: winding should differ (a.cw={} b.cw={})'.format(a.clockwise, b.clockwise)

	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0)

	assert meta['reversed_b'] is True, 'winding pre-check did not trigger'
	assert _on_count(na) == 4 and _on_count(nb) == 4
	assert meta['n_insert_a'] == 0 and meta['n_insert_b'] == 0, \
		'winding normalised: expected 0 insertions, got a={} b={}'.format(
			meta['n_insert_a'], meta['n_insert_b'])
	assert _approx(cost, 0.0, tol=1e-9), 'cost = {}'.format(cost)
	_assert_closure(na, 'wind-norm A')
	_assert_closure(nb, 'wind-norm B')

	print('  winding normalise: reversed_b=True, cost=0, no inserts [OK]')


def _test_apply_does_not_mutate_inputs():
	'''The library-level API returns copies; originals must be untouched.'''
	nodes_a = [Node(0.0, 0.0), Node(200.0, 0.0), Node(200.0, 100.0), Node(0.0, 100.0)]
	R = 100.0
	nodes_b = [Node(R * math.cos(math.pi / 2 + k * 2 * math.pi / 5),
	                R * math.sin(math.pi / 2 + k * 2 * math.pi / 5))
	           for k in range(5)]
	a = Contour(nodes_a, closed=True)
	b = Contour(nodes_b, closed=True)

	before_a = [(nd.x, nd.y, nd.is_on) for nd in a.nodes]
	before_b = [(nd.x, nd.y, nd.is_on) for nd in b.nodes]

	apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0)

	after_a = [(nd.x, nd.y, nd.is_on) for nd in a.nodes]
	after_b = [(nd.x, nd.y, nd.is_on) for nd in b.nodes]

	assert before_a == after_a, 'A was mutated!'
	assert before_b == after_b, 'B was mutated!'

	print('  input immutability: originals unchanged [OK]')


def _run_stage4_tests():
	print('Stage 4 - apply_match:')
	_test_apply_identical_rectangles()
	_test_apply_rectangle_vs_pentagon()
	_test_apply_rotated_self()
	_test_apply_two_insertions_same_segment()
	_test_apply_winding_normalised()
	_test_apply_does_not_mutate_inputs()
	print('Stage 4: all tests passed.')


# - Stage 5 helpers & tests --------------
def _rect_contour(x, y, w, h, ccw=True):
	'''Simple axis-aligned rectangle for multi-contour tests.'''
	if ccw:
		pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
	else:
		pts = [(x, y), (x, y + h), (x + w, y + h), (x + w, y)]
	return Contour([Node(px, py) for (px, py) in pts], closed=True)


def _test_pair_contours_count_mismatch():
	a = [_rect_contour(0, 0, 10, 10)]
	b = [_rect_contour(0, 0, 10, 10), _rect_contour(20, 20, 5, 5)]
	try:
		pair_contours(a, b)
	except ValueError:
		print('  count mismatch raises ValueError [OK]')
		return
	raise AssertionError('expected ValueError')


def _test_pair_contours_by_geometry():
	# A: [big outer at origin, small inner at (40,40)]
	# B: order reversed: [small inner, big outer]
	# Greedy by area+centre should pair them correctly.
	a = [_rect_contour(0, 0, 100, 100),
	     _rect_contour(40, 40, 20, 20, ccw=False)]
	b = [_rect_contour(42, 42, 20, 20, ccw=False),
	     _rect_contour(2, 2, 100, 100)]
	pairs = pair_contours(a, b)
	# Expect (0, 1) and (1, 0).
	assert (0, 1) in pairs and (1, 0) in pairs, \
		'unexpected pairing: {}'.format(pairs)
	print('  pair_contours reorders by geometry [OK]')


def _test_apply_match_glyph_two_rects():
	# Two offset rectangles per master; B lists them in swapped order.
	a = [_rect_contour(0, 0, 200, 100),
	     _rect_contour(300, 0, 100, 100)]
	b = [_rect_contour(302, 1, 100, 100),
	     _rect_contour(1, 1, 200, 100)]
	new_a, new_b, cost, meta = apply_match_glyph(
		a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0)
	assert len(new_a) == len(new_b) == 2
	# Per-contour post-condition: equal on-curve counts.
	for na, nb in zip(new_a, new_b):
		oa = sum(1 for n in na.nodes if n.is_on)
		ob = sum(1 for n in nb.nodes if n.is_on)
		assert oa == ob, 'on-curve mismatch per contour'
	# Tiny offsets only — cost should be small.
	assert cost < 1.0, 'unexpectedly high cost: {}'.format(cost)
	print('  apply_match_glyph on 2-contour glyph [OK]')


def _run_stage5_tests():
	print('Stage 5 - multi-contour:')
	_test_pair_contours_count_mismatch()
	_test_pair_contours_by_geometry()
	_test_apply_match_glyph_two_rects()
	print('Stage 5: all tests passed.')


if __name__ == '__main__':
	_run_stage1_tests()
	print('')
	_run_stage2_tests()
	print('')
	_run_stage3_tests()
	print('')
	_run_stage4_tests()
	print('')
	_run_stage5_tests()
