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
from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer

# - Init --------------------------------
__version__ = '0.2.0'


# - Ordering enum -----------------------
class Corner(object):
	'''Which bbox corner is used as the reference for canonical ordering.

	Shared between canonicalize_start (picks that corner's extremal on-curve
	as the new start) and canonicalize_contour_order (sorts contours by the
	same corner's key). Plain-class enum for Py2/PythonQt compatibility —
	values are (y_sign, x_sign) where +1 means "smaller is first".
	'''
	BOTTOM_LEFT  = ( 1,  1)   # y ascending (bottom first), x ascending (left first)
	TOP_LEFT     = (-1,  1)   # y descending (top first),   x ascending (left first)
	BOTTOM_RIGHT = ( 1, -1)
	TOP_RIGHT    = (-1, -1)

	_ALL = (BOTTOM_LEFT, TOP_LEFT, BOTTOM_RIGHT, TOP_RIGHT)


def _corner_key(corner):
	'''Resolve a Corner value to a (y_sign, x_sign) tuple, tolerating raw
	tuples for callers that prefer them.'''
	if isinstance(corner, tuple) and len(corner) == 2:
		return corner
	raise ValueError('unknown corner value: {!r}'.format(corner))

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

	# Turning angle at each on-curve vertex. angle_poly_turn does a
	# complex division (next-cur)/(cur-prev), so stacked on-curves (zero-
	# length adjacent edges) blow up with ZeroDivisionError. That pattern
	# is intentional in type design — designers stack nodes as interpolation
	# placeholders — so we defend against it: if either incident edge has
	# zero length the turn is undefined; treat it as 0 and let the stretch
	# term carry the signal.
	theta = []
	for i in range(m):
		L_in  = L[(i - 1) % m]
		L_out = L[i]
		if L_in == 0.0 or L_out == 0.0:
			theta.append(0.0)
			continue
		try:
			theta.append(on_nodes[i].angle_poly_turn)
		except ZeroDivisionError:
			theta.append(0.0)

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


# - Segment-type reconciliation ---------
def _segment_span(contour, on_idx_start, on_idx_next):
	'''Count nodes strictly between two on-curve indices (the off-curves
	of that segment). Handles wrap-around when on_idx_next < on_idx_start.
	'''
	n = len(contour.nodes)
	if on_idx_next > on_idx_start:
		return on_idx_next - on_idx_start - 1
	# Wrap: segment spans end → 0.
	return (n - on_idx_start - 1) + on_idx_next


def _promote_line_to_cubic(contour, on_idx_start, on_idx_next):
	'''Insert two curve-type off-curves between the two on-curves so the
	segment becomes a cubic bezier. Handles wrap. Mutates in place. Returns
	the number of nodes inserted (always 2).
	'''
	nodes = contour.nodes
	a = nodes[on_idx_start]
	b = nodes[on_idx_next]
	dx = b.point.x - a.point.x
	dy = b.point.y - a.point.y
	p1 = Node(a.point.x + dx / 3.0,       a.point.y + dy / 3.0,       type='curve')
	p2 = Node(a.point.x + 2.0 * dx / 3.0, a.point.y + 2.0 * dy / 3.0, type='curve')
	# Insert in reverse so the earlier position isn't shifted by the later insert.
	insert_pos = on_idx_start + 1
	if on_idx_next > on_idx_start:
		contour.insert(insert_pos, p2)
		contour.insert(insert_pos, p1)
	else:
		# Wrap: segment runs from on_idx_start to end, then 0 → on_idx_next.
		# Safest: append the two controls right after on_idx_start.
		contour.insert(insert_pos, p2)
		contour.insert(insert_pos, p1)
	return 2


def _reconcile_segment_types(contour_a, contour_b):
	'''After pairing, promote line→cubic wherever the paired segments
	have different types. Mutates both contours in place.

	Preconditions:
		- Both contours have equal on-curve counts (apply_match invariant).

	Returns:
		(n_promoted_a, n_promoted_b): number of segments promoted on each side.
	'''
	promoted_a = 0
	promoted_b = 0

	# Walk paired segments in REVERSE so inserts don't shift earlier indices
	# we haven't processed yet.
	def _pair_iter():
		on_a = _on_curve_indices(contour_a)
		on_b = _on_curve_indices(contour_b)
		assert len(on_a) == len(on_b)
		m = len(on_a)
		out = []
		for k in range(m):
			k_next = (k + 1) % m
			span_a = _segment_span(contour_a, on_a[k], on_a[k_next])
			span_b = _segment_span(contour_b, on_b[k], on_b[k_next])
			out.append((k, on_a[k], on_a[k_next], span_a,
			               on_b[k], on_b[k_next], span_b))
		return out

	for k, ia, ja, span_a, ib, jb, span_b in reversed(_pair_iter()):
		# Line = 0 off-curves, Cubic = 2 curve-type off-curves.
		# Only handle the Line ↔ Cubic case; other mixes (quadratic,
		# multi-off-curve TT) are out of scope and left untouched.
		if span_a == 0 and span_b == 2:
			_promote_line_to_cubic(contour_a, ia, ja)
			promoted_a += 1
		elif span_b == 0 and span_a == 2:
			_promote_line_to_cubic(contour_b, ib, jb)
			promoted_b += 1

	return promoted_a, promoted_b


# - Canonicalization helpers ------------
def canonicalize_start(contour, corner=Corner.BOTTOM_LEFT):
	'''Return a clone of contour with its start rotated to the on-curve
	node nearest the chosen bbox corner.

	Ties (two nodes with equal sort key — common for circles and
	rectangles) are broken by cyclic position: the earliest tied node in
	contour order wins. For geometric symmetry where even that depends
	on upstream construction order, fall back to the node whose vector
	from the bbox centre points closest to the corner direction — this
	gives a deterministic choice across masters built differently.

	Args:
		contour (Contour): closed contour to normalise (NOT mutated).
		corner (Corner|tuple): which bbox corner to anchor the start to.

	Returns:
		Contour: new contour with start rotated; if the contour is
			already starting at the canonical node, returns a plain clone.
	'''
	y_sign, x_sign = _corner_key(corner)

	work = contour.clone()
	on_idx = _on_curve_indices(work)
	if not on_idx:
		return work

	nodes = work.nodes
	# Primary key: (y_sign * y, x_sign * x) — smaller-is-first sort.
	# Secondary tiebreak: angle from bbox centre toward the target corner.
	bnds = work.bounds
	cx = bnds.x + bnds.width  * 0.5
	cy = bnds.y + bnds.height * 0.5
	target_dx = -x_sign   # +1 means "left first" → target points left (-x)
	target_dy = -y_sign

	def _key(idx):
		n = nodes[idx]
		nx = n.point.x
		ny = n.point.y
		primary = (y_sign * ny, x_sign * nx)
		# Tiebreaker: angular distance from node vector (centre→node) to
		# the desired corner direction. Closer ≈ smaller angular diff.
		dx = nx - cx
		dy = ny - cy
		# Dot product with target direction, negated so larger dot = smaller key.
		align = -(dx * target_dx + dy * target_dy)
		return (primary, align)

	best_idx = min(on_idx, key=_key)
	if best_idx != on_idx[0]:
		work.set_start(best_idx)
	return work


def canonicalize_contour_order(contours, corner=Corner.TOP_LEFT):
	'''Return contours sorted by the same Corner convention used for
	start-point canonicalization. Default TOP_LEFT = reading order.

	Does NOT mutate input contours. Returns a new list.
	'''
	y_sign, x_sign = _corner_key(corner)

	def _key(c):
		bnds = c.bounds
		# Use bbox centre so a contour that barely crosses a neighbour's
		# bounds doesn't outrank it because one corner point did.
		cx = bnds.x + bnds.width  * 0.5
		cy = bnds.y + bnds.height * 0.5
		return (y_sign * cy, x_sign * cx)

	return sorted(contours, key=_key)


def apply_match(contour_a, contour_b,
                k_s=1.0, k_b=1.0, c_ins_scale=1.0,
                align_start='respect'):
	'''Mutate *copies* of contour_a / contour_b so they become point-
	compatible under the Sederberg-Greenwood energy.

	Steps:
		1. Clone both contours; optionally canonicalize start nodes.
		2. Winding pre-check: reverse B's clone if winding differs.
		3. Intrinsic encoding of both contours (on-curve polygon).
		4. DP match (fixed or cyclic per `align_start`).
		5. Rotate B's start if cyclic picked a non-zero shift.
		6. Apply insertions on both copies per the back-trace plan.

	Args:
		align_start: how to align start points between A and B.
			'respect'   — trust designer: shift_b = 0, fixed DP (default).
			'canonical' — run canonicalize_start(BOTTOM_LEFT) on clones of
			              both A and B before DP, then shift_b = 0.
			'auto'      — cyclic DP picks the cheapest shift (legacy).

	Returns:
		(new_a, new_b, cost, meta) where meta contains 'shift_b',
		'reversed_b', 'align_start', 'n_pairs', 'n_insert_a',
		'n_insert_b', 'len_on_before', 'len_on_after'.

	Post-conditions (enforced by assertions):
		- len(new_a on-curves) == len(new_b on-curves)
		- sum(theta) on each resulting contour remains +/- 2*pi
	'''
	if align_start not in ('respect', 'canonical', 'auto'):
		raise ValueError(
			"align_start must be one of 'respect','canonical','auto'; got {!r}".format(
				align_start))

	# Canonicalize THEN clone by using canonicalize_start (which clones).
	if align_start == 'canonical':
		new_a = canonicalize_start(contour_a, corner=Corner.BOTTOM_LEFT)
		new_b = canonicalize_start(contour_b, corner=Corner.BOTTOM_LEFT)
	else:
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

	if align_start == 'auto':
		shift_b, _C, B_tbl, cost = dp_match_cyclic(
			La, Ta, Lb, Tb, k_s=k_s, k_b=k_b, c_ins_scale=c_ins_scale)
	else:
		# 'respect' and 'canonical' both pin shift=0.
		_C, B_tbl, cost = dp_match(
			La, Ta, Lb, Tb, k_s=k_s, k_b=k_b, c_ins_scale=c_ins_scale)
		shift_b = 0

	path = backtrace(B_tbl, m, n)

	# Rotate new_b by shift_b ON-CURVE positions if cyclic moved it.
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

	# Rule 4: reconcile segment types (line ↔ cubic) between paired segments.
	promoted_a, promoted_b = _reconcile_segment_types(new_a, new_b)

	n_pairs      = sum(1 for _, _, op in path if op == BT_PAIR)
	n_insert_a   = sum(1 for _, _, op in path if op == BT_INSERT_A)
	n_insert_b   = sum(1 for _, _, op in path if op == BT_INSERT_B)

	meta = {
		'shift_b': shift_b,
		'reversed_b': reversed_b,
		'align_start': align_start,
		'n_pairs': n_pairs,
		'n_insert_a': n_insert_a,
		'n_insert_b': n_insert_b,
		'n_promoted_a': promoted_a,
		'n_promoted_b': promoted_b,
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

	Uses |signed_area| (shape size) + bbox-centre distance only.
	Winding direction is NOT used here: apply_match's per-contour
	pre-check reverses B as needed, so if a whole glyph comes in with
	reversed winding we still want outer-to-outer and inner-to-inner
	pairing. A winding penalty actively pairs outer-to-inner in that
	case and poisons the DP.
	'''
	_cw_a, area_a, ax, ay = sig_a
	_cw_b, area_b, bx, by = sig_b
	d_area = abs(abs(area_a) - abs(area_b)) / max(abs(area_a), abs(area_b), 1.0)
	d_pos  = math.hypot(ax - bx, ay - by) / max(diag, 1.0)
	return d_area + d_pos


def pair_contours(contours_a, contours_b, pair_mode='respect'):
	'''Pair two equal-length contour lists.

	Args:
		contours_a, contours_b: parallel lists of contours.
		pair_mode:
			'respect' — identity pairing (i, i). Trust the designer's
			            contour order; the companion canonicalize_contour_order
			            can be used beforehand to normalise both sides
			            (default).
			'auto'    — greedy geometric pairing by |signed_area| + bbox
			            centre distance. Useful when masters came from
			            independent sources and ordering isn't consistent.

	Returns:
		list of (i, j) index pairs.

	Raises:
		ValueError on length mismatch — glyph-level compatibility is only
		defined when both masters have the same contour count.
	'''
	if len(contours_a) != len(contours_b):
		raise ValueError(
			'pair_contours: contour count mismatch A={} B={}'.format(
				len(contours_a), len(contours_b)))

	if pair_mode == 'respect':
		return [(i, i) for i in range(len(contours_a))]

	if pair_mode != 'auto':
		raise ValueError(
			"pair_mode must be 'respect' or 'auto'; got {!r}".format(pair_mode))

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
                      k_s=1.0, k_b=1.0, c_ins_scale=1.0,
                      align_start='respect', pair_mode='respect'):
	'''Stage 5: run apply_match per paired contour.

	Args:
		contours_a, contours_b: parallel lists of closed contours from two
			masters of the same glyph. Must have equal length.
		align_start: see apply_match (default 'respect').
		pair_mode:   see pair_contours (default 'respect').

	Returns:
		(new_a_list, new_b_list, total_cost, meta)
			- new_a_list / new_b_list: output contours reordered so new_a[k]
			  pairs with new_b[k] (A's original order preserved, B reordered
			  to match).
			- total_cost: sum of per-contour Sederberg-Greenwood costs.
			- meta: dict with 'pairs', 'per_contour', 'total_insert_a',
			  'total_insert_b', 'align_start', 'pair_mode'.

	Raises ValueError on contour-count mismatch.
	'''
	pairs = pair_contours(contours_a, contours_b, pair_mode=pair_mode)

	new_a_list = [None] * len(pairs)
	new_b_list = [None] * len(pairs)
	per_contour = []
	total_cost = 0.0
	total_ins_a = 0
	total_ins_b = 0
	total_prom_a = 0
	total_prom_b = 0

	for k, (i, j) in enumerate(pairs):
		na, nb, cost, m = apply_match(
			contours_a[i], contours_b[j],
			k_s=k_s, k_b=k_b, c_ins_scale=c_ins_scale,
			align_start=align_start)
		new_a_list[k] = na
		new_b_list[k] = nb
		per_contour.append(m)
		total_cost += cost
		total_ins_a += m['n_insert_a']
		total_ins_b += m['n_insert_b']
		total_prom_a += m.get('n_promoted_a', 0)
		total_prom_b += m.get('n_promoted_b', 0)

	meta = {
		'pairs': pairs,
		'per_contour': per_contour,
		'total_insert_a': total_ins_a,
		'total_insert_b': total_ins_b,
		'total_promoted_a': total_prom_a,
		'total_promoted_b': total_prom_b,
		'align_start': align_start,
		'pair_mode': pair_mode,
	}
	return new_a_list, new_b_list, total_cost, meta


# - Standalone: match_contour_order ----
# Independent of the Sederberg-Greenwood pipeline. Reorders one layer's
# contours to match another's order using a multi-signal cost:
#   1. Containment depth (hard gate — topology is dispositive).
#   2. Relative centroid position within glyph bbox.
#   3. Relative |signed area| vs total glyph area.
#   4. Log aspect ratio.
#   5. On-curve count mismatch (topological tiebreaker).


def _bbox_strictly_contains(outer_bounds, inner_bounds, tol=1e-6):
	'''True iff outer's bbox strictly encloses inner's bbox.'''
	return (outer_bounds.x - tol <= inner_bounds.x
	        and outer_bounds.y - tol <= inner_bounds.y
	        and outer_bounds.x + outer_bounds.width  + tol >= inner_bounds.x + inner_bounds.width
	        and outer_bounds.y + outer_bounds.height + tol >= inner_bounds.y + inner_bounds.height
	        and (outer_bounds.width  > inner_bounds.width
	             or outer_bounds.height > inner_bounds.height))


# Tunables for geometric containment. Area ratio above this threshold means
# the 'inner' bbox is too close in size to the 'outer' — almost certainly
# two overlapping siblings rather than true nesting.
_CONTAIN_BBOX_AREA_RATIO_MAX = 0.8


def _point_in_polygon(px, py, poly_pts):
	'''Even-odd ray-crossing test. poly_pts is a list of (x, y).
	Points exactly on an edge may return either result — good enough for
	classification since we only care about interior-ness in aggregate.
	'''
	n = len(poly_pts)
	if n < 3:
		return False
	inside = False
	j = n - 1
	for i in range(n):
		xi, yi = poly_pts[i]
		xj, yj = poly_pts[j]
		if ((yi > py) != (yj > py)):
			# Horizontal ray from (px, py) crosses edge i-j?
			x_cross = (xj - xi) * (py - yi) / (yj - yi + 1e-30) + xi
			if px < x_cross:
				inside = not inside
		j = i
	return inside


def _on_curve_points(contour):
	'''Polyline approximation using on-curve nodes only.
	NOTE: For cubic contours this ignores off-curve bulge. For containment
	classification this is accurate enough on typical glyphs. Future work:
	optional flattening (sample cubics at a few t values) for pathological
	cases where a curve bulges well outside its on-curve polygon.
	'''
	return [(nd.x, nd.y) for nd in contour.nodes if nd.is_on]


def _contour_strictly_contains(outer, inner):
	'''Layered geometric containment. Three tests, cheap to expensive:

	  1. Bbox must strictly enclose inner's bbox (fast reject).
	  2. Inner-vs-outer bbox area ratio must be below threshold (rejects
	     the CJK case where a curved stroke has a huge sweeping bbox that
	     happens to enclose a nearby sibling stroke's bbox).
	  3. ALL of inner's on-curve points must lie inside outer's polygon
	     (point-in-polygon via even-odd rule).
	'''
	ob = outer.bounds
	ib = inner.bounds

	# 1. Bbox gate.
	if not _bbox_strictly_contains(ob, ib):
		return False

	# 2. Area-ratio gate — only meaningful when outer's bbox has area.
	outer_area = max(ob.width * ob.height, 1e-9)
	inner_area = ib.width * ib.height
	if inner_area / outer_area > _CONTAIN_BBOX_AREA_RATIO_MAX:
		return False

	# 3. Point-in-polygon gate on on-curves.
	outer_poly = _on_curve_points(outer)
	if len(outer_poly) < 3:
		# Degenerate outer — can't do PIP. Fall back to bbox result (already
		# true from step 1). Rare; don't overthink.
		return True
	for (px, py) in _on_curve_points(inner):
		if not _point_in_polygon(px, py, outer_poly):
			return False
	return True


def _containment_depth(idx, contours):
	'''Number of contours that strictly contain contours[idx]. Uses layered
	geometric containment: bbox → area-ratio → point-in-polygon. Handles
	the CJK case where separate strokes have overlapping bboxes but no
	actual nesting.
	'''
	me = contours[idx]
	depth = 0
	for j, other in enumerate(contours):
		if j == idx:
			continue
		if _contour_strictly_contains(other, me):
			depth += 1
	return depth


def _order_signature(contour, glyph_bbox, glyph_area, depth):
	'''Dimensionless signature for reorder pairing.'''
	b = contour.bounds
	cx = b.x + b.width  * 0.5
	cy = b.y + b.height * 0.5

	# Normalise centroid against the glyph bbox so two masters of
	# different absolute size still see the same relative positions.
	gw = max(glyph_bbox.width,  1.0)
	gh = max(glyph_bbox.height, 1.0)
	rel_cx = (cx - glyph_bbox.x) / gw
	rel_cy = (cy - glyph_bbox.y) / gh

	area = abs(contour.signed_area)
	rel_area = area / max(glyph_area, 1.0)

	# Log aspect ratio: symmetric in w/h and h/w. Zero when square.
	w = max(b.width,  1e-6)
	h = max(b.height, 1e-6)
	log_aspect = math.log(w / h)

	on_count = sum(1 for n in contour.nodes if n.is_on)

	return {
		'depth':      depth,
		'rel_cx':     rel_cx,
		'rel_cy':     rel_cy,
		'rel_area':   rel_area,
		'log_aspect': log_aspect,
		'on_count':   on_count,
	}


def _order_pair_cost(sig_a, sig_b):
	'''Weighted dissimilarity. Depth mismatch is a hard gate via the
	large constant — within-depth pairings always beat cross-depth.'''
	depth_gate = 0.0 if sig_a['depth'] == sig_b['depth'] else 100.0

	d_pos    = math.hypot(sig_a['rel_cx']   - sig_b['rel_cx'],
	                       sig_a['rel_cy']   - sig_b['rel_cy'])
	d_area   = abs(sig_a['rel_area']   - sig_b['rel_area'])
	d_aspect = abs(sig_a['log_aspect'] - sig_b['log_aspect'])

	max_oc = max(sig_a['on_count'], sig_b['on_count'], 1)
	d_topol = abs(sig_a['on_count'] - sig_b['on_count']) / float(max_oc)

	return (depth_gate
	        + 2.0 * d_pos
	        + 1.5 * d_area
	        + 1.0 * d_aspect
	        + 0.5 * d_topol)


def _glyph_bbox(contours):
	'''Union bbox over all contours. Returns an object with .x, .y,
	.width, .height — matching the shape of Contour.bounds so downstream
	code can use the same accessors.'''
	assert contours, 'glyph has no contours'
	xs, ys, xs_max, ys_max = [], [], [], []
	for c in contours:
		b = c.bounds
		xs.append(b.x);                 ys.append(b.y)
		xs_max.append(b.x + b.width);   ys_max.append(b.y + b.height)
	x_min, y_min = min(xs), min(ys)
	x_max, y_max = max(xs_max), max(ys_max)

	class _BBox(object):
		pass
	bb = _BBox()
	bb.x = x_min
	bb.y = y_min
	bb.width  = x_max - x_min
	bb.height = y_max - y_min
	return bb


def _glyph_area(contours):
	return sum(abs(c.signed_area) for c in contours)


def _as_contour_list(obj):
	'''Accept a core Layer (or any object exposing .contours), a single
	Shape (.contours), or a plain list of Contours. Returns a list.'''
	if obj is None:
		return []
	if isinstance(obj, (list, tuple)):
		return list(obj)
	contours = getattr(obj, 'contours', None)
	if contours is not None:
		return list(contours)
	# Last resort: treat as iterable of contours.
	return list(obj)


def match_contour_order(ref, tgt):
	'''Reorder tgt contours so that result[i] corresponds to ref[i].

	Uses multi-signal cost pairing (containment depth as a hard gate, plus
	relative position, relative area, log aspect ratio, on-curve count).
	Within each depth level, a greedy assignment picks the lowest-cost
	unused pair until all contours are placed.

	Inputs are NOT mutated. The returned list references the original
	target contours (no clones) in the new order.

	Args:
		ref: reference — a core Layer, Shape, or list of Contours.
		     Defines the target order.
		tgt: target — same forms accepted. This is what gets reordered.

	Returns:
		(new_tgt, pairs, confidence)
			- new_tgt: reordered target. Output type mirrors the tgt input:
			    * Layer in → Layer out (metadata copied; reordered contours
			      are wrapped in a single Shape, flattening any original
			      shape grouping).
			    * Shape in → Shape out.
			    * list in  → list of contours out.
			- pairs: list of (ref_idx, tgt_idx) sorted by ref_idx.
			- confidence: list of per-pair costs (same order as pairs).
			  Lower is better; use it to flag suspicious assignments.

	Raises:
		ValueError on contour-count mismatch or on depth-level population
		mismatch (e.g. ref has 2 depth-0 contours but tgt has 1 — meaning
		the containment topologies don't match, an unsolvable case here).
	'''
	contours_ref = _as_contour_list(ref)
	contours_tgt = _as_contour_list(tgt)

	if len(contours_ref) != len(contours_tgt):
		raise ValueError(
			'match_contour_order: contour count mismatch ref={} tgt={}'.format(
				len(contours_ref), len(contours_tgt)))

	n = len(contours_ref)
	if n == 0:
		return [], [], []

	# Signatures for both sides.
	gbb_ref = _glyph_bbox(contours_ref)
	gbb_tgt = _glyph_bbox(contours_tgt)
	ga_ref  = _glyph_area(contours_ref)
	ga_tgt  = _glyph_area(contours_tgt)

	sigs_ref = []
	sigs_tgt = []
	for i, c in enumerate(contours_ref):
		d = _containment_depth(i, contours_ref)
		sigs_ref.append(_order_signature(c, gbb_ref, ga_ref, d))
	for j, c in enumerate(contours_tgt):
		d = _containment_depth(j, contours_tgt)
		sigs_tgt.append(_order_signature(c, gbb_tgt, ga_tgt, d))

	# Depth-level check: populations must match level-for-level.
	from collections import Counter
	depths_ref = Counter(s['depth'] for s in sigs_ref)
	depths_tgt = Counter(s['depth'] for s in sigs_tgt)
	if depths_ref != depths_tgt:
		raise ValueError(
			'match_contour_order: containment topology differs '
			'ref={} tgt={} — the layers are not structurally paired.'.format(
				dict(depths_ref), dict(depths_tgt)))

	# Per-depth greedy assignment.
	remaining_tgt = set(range(n))
	pairs = []
	confidence = []

	# Iterate ref in depth order (outers first), then original index. This
	# stabilises output when multiple ties exist across depth levels.
	ref_order = sorted(range(n), key=lambda i: (sigs_ref[i]['depth'], i))

	for ri in ref_order:
		best = None
		for tj in remaining_tgt:
			c = _order_pair_cost(sigs_ref[ri], sigs_tgt[tj])
			if best is None or c < best[0]:
				best = (c, tj)
		cost, tj = best
		pairs.append((ri, tj))
		confidence.append(cost)
		remaining_tgt.remove(tj)

	# Build reordered target list indexed by ref position.
	new_tgt_list = [None] * n
	for (ri, tj), c in zip(pairs, confidence):
		new_tgt_list[ri] = contours_tgt[tj]

	# Sort pairs + confidence by ref_idx for caller convenience.
	combined = sorted(zip(pairs, confidence), key=lambda pc: pc[0][0])
	pairs = [p for p, _ in combined]
	confidence = [c for _, c in combined]

	# Mirror output type to input type.
	if isinstance(tgt, Layer):
		new_shape = Shape(new_tgt_list)
		new_layer = Layer(
			[new_shape],
			name=getattr(tgt, 'name', None),
			width=getattr(tgt, 'advance_width', 0.),
			height=getattr(tgt, 'advance_height', 1000.),
			mark=getattr(tgt, 'mark', 0),
			anchors=list(getattr(tgt, 'anchors', []) or []),
		)
		return new_layer, pairs, confidence

	if isinstance(tgt, Shape):
		return Shape(new_tgt_list), pairs, confidence

	return new_tgt_list, pairs, confidence



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

	# align_start='auto' — we explicitly test the cyclic recovery.
	na, nb, cost, meta = apply_match(a, b, k_s=1.0 / 40000.0, k_b=1.0,
	                                 align_start='auto')

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
	# pair_mode='auto' — geometric greedy pairing.
	pairs = pair_contours(a, b, pair_mode='auto')
	# Expect (0, 1) and (1, 0).
	assert (0, 1) in pairs and (1, 0) in pairs, \
		'unexpected pairing: {}'.format(pairs)
	print('  pair_contours(auto) reorders by geometry [OK]')


def _test_apply_match_glyph_two_rects():
	# Two offset rectangles per master; B lists them in swapped order.
	a = [_rect_contour(0, 0, 200, 100),
	     _rect_contour(300, 0, 100, 100)]
	b = [_rect_contour(302, 1, 100, 100),
	     _rect_contour(1, 1, 200, 100)]
	# Use pair_mode='auto' because B is given in swapped order.
	new_a, new_b, cost, meta = apply_match_glyph(
		a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0, pair_mode='auto')
	assert len(new_a) == len(new_b) == 2
	# Per-contour post-condition: equal on-curve counts.
	for na, nb in zip(new_a, new_b):
		oa = sum(1 for n in na.nodes if n.is_on)
		ob = sum(1 for n in nb.nodes if n.is_on)
		assert oa == ob, 'on-curve mismatch per contour'
	# Tiny offsets only — cost should be small.
	assert cost < 1.0, 'unexpectedly high cost: {}'.format(cost)
	print('  apply_match_glyph on 2-contour glyph [OK]')


def _test_pair_contours_globally_reversed():
	# A = ['b'-like glyph]: CCW outer + CW inner.
	# B = same geometry but winding globally reversed: CW outer + CCW inner.
	# With the old winding-penalty cost, outer-A (CCW) would pair with
	# inner-B (CCW after reversal) because that's the only winding match
	# — catastrophic for interpolation. Verify we pair outer↔outer.
	outer_ccw = _rect_contour(0, 0, 400, 400, ccw=True)
	inner_cw  = _rect_contour(100, 100, 200, 200, ccw=False)
	outer_cw  = _rect_contour(0, 0, 400, 400, ccw=False)
	inner_ccw = _rect_contour(100, 100, 200, 200, ccw=True)

	a = [outer_ccw, inner_cw]
	b = [outer_cw,  inner_ccw]

	# This is the regression that motivated dropping winding from pair_cost:
	# test the auto mode which uses _pair_cost.
	pairs = pair_contours(a, b, pair_mode='auto')
	# Expect outer (idx 0) ↔ outer (idx 0), inner (idx 1) ↔ inner (idx 1).
	assert (0, 0) in pairs and (1, 1) in pairs, \
		'globally-reversed winding paired wrong: {}'.format(pairs)
	print('  globally-reversed winding still pairs by area/centre [OK]')


def _test_intrinsic_stacked_nodes():
	# Triangle with an extra on-curve stacked on top of node 0. Zero-length
	# adjacent edges must not raise ZeroDivisionError from angle_poly_turn.
	nodes = [Node(0.0, 0.0), Node(0.0, 0.0),    # stacked
	         Node(200.0, 0.0), Node(100.0, 150.0)]
	c = Contour(nodes, closed=True)
	L, theta = intrinsic(c)
	assert len(L) == 4 and len(theta) == 4
	# Two zero-length edges around the stacked pair.
	zero_edges = sum(1 for x in L if x == 0.0)
	assert zero_edges >= 1, 'expected at least one zero edge, got L={}'.format(L)
	# θ at the degenerate vertex must be finite (we set it to 0).
	for t in theta:
		assert math.isfinite(t), 'theta has non-finite: {}'.format(theta)
	print('  intrinsic handles stacked (zero-length) nodes [OK]')


def _test_apply_match_stacked_nodes():
	# A: a quad. B: same quad but with a stacked node added. Matcher
	# should not raise and should yield equal on-curve counts.
	a_nodes = [Node(0.0, 0.0), Node(200.0, 0.0),
	           Node(200.0, 100.0), Node(0.0, 100.0)]
	b_nodes = [Node(0.0, 0.0), Node(0.0, 0.0),    # stacked
	           Node(200.0, 0.0),
	           Node(200.0, 100.0), Node(0.0, 100.0)]
	a = Contour(a_nodes, closed=True)
	b = Contour(b_nodes, closed=True)
	new_a, new_b, cost, meta = apply_match(a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0)
	oa = sum(1 for n in new_a.nodes if n.is_on)
	ob = sum(1 for n in new_b.nodes if n.is_on)
	assert oa == ob, 'stacked-node match produced {} vs {}'.format(oa, ob)
	print('  apply_match survives stacked node on B [OK]')


def _run_stage5_tests():
	print('Stage 5 - multi-contour:')
	_test_pair_contours_count_mismatch()
	_test_pair_contours_by_geometry()
	_test_pair_contours_globally_reversed()
	_test_apply_match_glyph_two_rects()
	_test_intrinsic_stacked_nodes()
	_test_apply_match_stacked_nodes()
	print('Stage 5: all tests passed.')


# - Stage 6: Respect-by-default modes + segment-type reconciliation
def _test_respect_starts_no_rotation():
	'''A rectangle with B rotated one on-curve. align_start='respect'
	must NOT rotate B back — shift_b stays 0 even though auto would
	recover a rotation at cost 0.'''
	a = _rect_contour(0, 0, 200, 100)
	# B: same rectangle but start rotated 1 on-curve (equiv to set_start)
	b = _rect_contour(0, 0, 200, 100)
	on_idx = _on_curve_indices(b)
	b.set_start(on_idx[1])
	_, _, _cost, meta = apply_match(a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0,
	                                align_start='respect')
	assert meta['shift_b'] == 0, 'respect mode must not rotate B, got shift={}'.format(meta['shift_b'])
	print('  respect: no rotation even when auto would find one [OK]')


def _test_auto_recovers_rotation():
	'''Same setup, align_start='auto' finds shift=3 (or equivalent) at zero cost.'''
	a = _rect_contour(0, 0, 200, 100)
	b = _rect_contour(0, 0, 200, 100)
	on_idx = _on_curve_indices(b)
	b.set_start(on_idx[1])
	_, _, cost, meta = apply_match(a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0,
	                               align_start='auto')
	assert cost < 1e-6, 'auto should find zero-cost alignment, got {}'.format(cost)
	print('  auto: recovers rotation at zero cost (shift={}) [OK]'.format(meta['shift_b']))


def _test_canonical_start_bottom_left():
	'''canonicalize_start picks the node nearest BL. For a rectangle
	(0,0)→(200,0)→(200,100)→(0,100), that's (0,0).'''
	# Start from the top-right corner to make it non-trivial.
	nodes = [Node(200.0, 100.0), Node(0.0, 100.0),
	         Node(0.0, 0.0), Node(200.0, 0.0)]
	c = Contour(nodes, closed=True)
	canon = canonicalize_start(c, corner=Corner.BOTTOM_LEFT)
	# After canonicalization, nodes[0] should be (0,0).
	first = canon.nodes[0]
	assert (first.point.x, first.point.y) == (0.0, 0.0), \
		'expected (0,0) as start, got ({},{})'.format(first.point.x, first.point.y)
	# Original untouched.
	assert (c.nodes[0].point.x, c.nodes[0].point.y) == (200.0, 100.0), \
		'input contour was mutated'
	print('  canonicalize_start(BL) rotates to bottom-left extremum [OK]')


def _test_canonicalize_contour_order_reading():
	'''Three contours: bottom-right, top-left, bottom-left. Default
	TOP_LEFT sort gives reading order: top-left first, then two bottom
	contours left-to-right.'''
	c_br = _rect_contour(200, 0, 50, 50)
	c_tl = _rect_contour(0, 200, 50, 50)
	c_bl = _rect_contour(0, 0, 50, 50)
	ordered = canonicalize_contour_order([c_br, c_tl, c_bl])
	# Expect TL (y-centre=225), then BL (y-centre=25, x-centre=25), then BR.
	centres = [(c.bounds.x + c.bounds.width/2, c.bounds.y + c.bounds.height/2)
	           for c in ordered]
	assert centres[0][1] > centres[1][1], \
		'top contour should come first: {}'.format(centres)
	assert centres[1][0] < centres[2][0], \
		'then left-of-two-bottom: {}'.format(centres)
	print('  canonicalize_contour_order(TL) gives reading order [OK]')


def _test_pair_respect_identity():
	a = [_rect_contour(0, 0, 100, 100), _rect_contour(40, 40, 20, 20, ccw=False)]
	b = [_rect_contour(42, 42, 20, 20, ccw=False), _rect_contour(2, 2, 100, 100)]
	# pair_mode='respect' trusts given order.
	pairs = pair_contours(a, b, pair_mode='respect')
	assert pairs == [(0, 0), (1, 1)], 'respect must be identity: {}'.format(pairs)
	# pair_mode='auto' reorders geometrically.
	pairs_auto = pair_contours(a, b, pair_mode='auto')
	assert (0, 1) in pairs_auto and (1, 0) in pairs_auto, \
		'auto must reorder: {}'.format(pairs_auto)
	print('  pair_contours: respect=identity, auto=greedy [OK]')


def _test_segment_type_line_to_cubic():
	'''A is a rectangle (all-line). B is a rectangle with one cubic segment.
	After apply_match, both sides should have the same segment structure
	on that segment — A's line should be promoted.'''
	# A: plain 200x100 rect.
	a = _rect_contour(0, 0, 200, 100)
	# B: same corners but first segment is a cubic. Build manually.
	b_nodes = [
		Node(0.0, 0.0, type='on'),
		Node(67.0, 0.0, type='curve'),
		Node(133.0, 0.0, type='curve'),
		Node(200.0, 0.0, type='on'),
		Node(200.0, 100.0, type='on'),
		Node(0.0, 100.0, type='on'),
	]
	b = Contour(b_nodes, closed=True)
	new_a, new_b, _cost, meta = apply_match(
		a, b, k_s=1.0 / (1000.0 * 1000.0), k_b=1.0, align_start='respect')
	# After reconciliation, new_a's first segment (on[0]→on[1]) should
	# contain 2 curve nodes.
	on_a = _on_curve_indices(new_a)
	span_a_seg0 = _segment_span(new_a, on_a[0], on_a[1])
	assert span_a_seg0 == 2, \
		'expected line→cubic promotion on A seg 0, got span={}'.format(span_a_seg0)
	assert meta['n_promoted_a'] == 1, \
		'expected 1 promotion on A, got {}'.format(meta['n_promoted_a'])
	assert meta['n_promoted_b'] == 0
	print('  segment-type: line promoted to cubic on A [OK]')


def _run_stage6_tests():
	print('Stage 6 - respect modes + segment types:')
	_test_respect_starts_no_rotation()
	_test_auto_recovers_rotation()
	_test_canonical_start_bottom_left()
	_test_canonicalize_contour_order_reading()
	_test_pair_respect_identity()
	_test_segment_type_line_to_cubic()
	print('Stage 6: all tests passed.')


# - Stage 7: match_contour_order -------------------------------------------

def _test_match_contour_order_shuffled_identity():
	'''Ref and tgt are the same contours, just shuffled. Must recover ref order.'''
	c0 = _rect_contour(0, 0, 100, 100)
	c1 = _rect_contour(200, 0, 50, 50)
	c2 = _rect_contour(400, 0, 80, 80)
	ref = [c0, c1, c2]
	tgt = [c2, c0, c1]  # shuffled
	new_tgt, pairs, conf = match_contour_order(ref, tgt)
	assert new_tgt[0] is c0 and new_tgt[1] is c1 and new_tgt[2] is c2, \
		'shuffled identity not recovered: {}'.format(pairs)
	# Every pair cost should be (near) zero — positions/areas are identical.
	assert all(c < 1e-6 for c in conf), 'nonzero cost on identity: {}'.format(conf)
	print('  shuffled identity recovered [OK]')


def _test_match_contour_order_similar_not_equal():
	'''Slightly different tgt (simulating Bold vs Regular): still recoverable.'''
	ref = [_rect_contour(0, 0, 100, 100),      # big outer
	       _rect_contour(300, 10, 50, 50),     # small right
	       _rect_contour(600, 0, 80, 90)]      # medium far-right
	# Bold-ish: slightly bigger and nudged, shuffled order.
	tgt = [_rect_contour(595, -5, 90, 100),    # ~matches ref[2]
	       _rect_contour(-5, -5, 110, 110),    # ~matches ref[0]
	       _rect_contour(295, 8, 60, 55)]      # ~matches ref[1]
	new_tgt, pairs, _conf = match_contour_order(ref, tgt)
	# new_tgt[0] should be tgt[1] (big outer), etc.
	assert new_tgt[0] is tgt[1], 'ref[0] mispaired: pairs={}'.format(pairs)
	assert new_tgt[1] is tgt[2], 'ref[1] mispaired: pairs={}'.format(pairs)
	assert new_tgt[2] is tgt[0], 'ref[2] mispaired: pairs={}'.format(pairs)
	print('  Regular-vs-Bold-style reorder [OK]')


def _test_match_contour_order_containment_gate():
	'''Depth-0 and depth-1 contours must not swap even if geometry would
	otherwise suggest it.'''
	outer_ref = _rect_contour(0, 0, 400, 400)
	inner_ref = _rect_contour(100, 100, 200, 200, ccw=False)
	# tgt: inner and outer listed in reverse order.
	inner_tgt = _rect_contour(100, 100, 200, 200, ccw=False)
	outer_tgt = _rect_contour(0, 0, 400, 400)
	ref = [outer_ref, inner_ref]
	tgt = [inner_tgt, outer_tgt]  # reversed
	new_tgt, pairs, _conf = match_contour_order(ref, tgt)
	assert new_tgt[0] is outer_tgt, 'outer↔inner swapped: {}'.format(pairs)
	assert new_tgt[1] is inner_tgt, 'inner↔outer swapped: {}'.format(pairs)
	print('  containment depth gates pairing [OK]')


def _test_match_contour_order_count_mismatch():
	ref = [_rect_contour(0, 0, 10, 10)]
	tgt = [_rect_contour(0, 0, 10, 10), _rect_contour(20, 20, 5, 5)]
	try:
		match_contour_order(ref, tgt)
	except ValueError:
		print('  count mismatch raises ValueError [OK]')
		return
	raise AssertionError('expected ValueError on count mismatch')


def _test_match_contour_order_topology_mismatch():
	'''Same count, different containment topologies → unsolvable.'''
	# ref: two depth-0 contours (side by side).
	ref = [_rect_contour(0, 0, 100, 100),
	       _rect_contour(200, 0, 100, 100)]
	# tgt: one depth-0 + one depth-1 (nested).
	tgt = [_rect_contour(0, 0, 400, 400),
	       _rect_contour(100, 100, 200, 200, ccw=False)]
	try:
		match_contour_order(ref, tgt)
	except ValueError:
		print('  containment topology mismatch raises ValueError [OK]')
		return
	raise AssertionError('expected ValueError on topology mismatch')


def _test_match_contour_order_empty():
	new_tgt, pairs, conf = match_contour_order([], [])
	assert new_tgt == [] and pairs == [] and conf == []
	print('  empty input returns empty [OK]')


def _test_match_contour_order_layer_in_layer_out():
	'''Passing a Layer for tgt returns a Layer with reordered contours.'''
	c0 = _rect_contour(0, 0, 100, 100)
	c1 = _rect_contour(200, 0, 50, 50)
	ref_layer = Layer([Shape([c0, c1])], name='Regular', width=300)
	# tgt layer with contours in reverse order, different metadata.
	t0 = _rect_contour(200, 0, 50, 50)
	t1 = _rect_contour(0, 0, 100, 100)
	tgt_layer = Layer([Shape([t0, t1])], name='Bold', width=320, mark=42)
	new_layer, pairs, _conf = match_contour_order(ref_layer, tgt_layer)
	assert isinstance(new_layer, Layer), 'expected Layer, got {}'.format(type(new_layer))
	assert new_layer.name == 'Bold', 'layer name not preserved: {}'.format(new_layer.name)
	assert new_layer.advance_width == 320
	assert new_layer.mark == 42
	out_contours = list(new_layer.contours)
	assert len(out_contours) == 2
	# Ref[0] is c0 (big, at 0,0) → should get t1 (big, at 0,0).
	assert out_contours[0] is t1
	assert out_contours[1] is t0
	print('  Layer in → Layer out (metadata preserved) [OK]')


def _test_match_contour_order_shape_in_shape_out():
	c0 = _rect_contour(0, 0, 100, 100)
	c1 = _rect_contour(200, 0, 50, 50)
	ref_shape = Shape([c0, c1])
	tgt_shape = Shape([_rect_contour(200, 0, 50, 50),
	                    _rect_contour(0, 0, 100, 100)])
	new_shape, _pairs, _conf = match_contour_order(ref_shape, tgt_shape)
	assert isinstance(new_shape, Shape), 'expected Shape, got {}'.format(type(new_shape))
	out = list(new_shape.contours)
	assert len(out) == 2
	# Big outer first.
	assert abs(out[0].signed_area) > abs(out[1].signed_area)
	print('  Shape in → Shape out [OK]')


def _test_containment_cjk_sibling_strokes():
	'''CJK-like case: a tall thin 'curved stroke' whose bbox happens to
	enclose a small sibling stroke. Bbox containment would say yes; the
	PIP gate must say no.

	Outer: an L-shaped polyline approximated by its on-curve points —
	we fake it with a concave quadrilateral that has a big bbox but a
	small interior.
	'''
	# Outer: thin L-shape. On-curve points outline a narrow polygon that
	# hugs the left + bottom edges of its bbox, leaving the top-right
	# corner empty (but still inside the bbox).
	outer_nodes = [
		Node(0.0,   0.0),
		Node(400.0, 0.0),
		Node(400.0, 50.0),
		Node(50.0,  50.0),
		Node(50.0,  400.0),
		Node(0.0,   400.0),
	]
	outer = Contour(outer_nodes, closed=True)
	# Sibling stroke sitting in the top-right empty area. Its bbox
	# (200..300, 200..300) is inside outer's bbox (0..400, 0..400) →
	# bbox-only check would falsely flag it as nested.
	sibling = _rect_contour(200, 200, 100, 100)

	contours = [outer, sibling]
	d_outer = _containment_depth(0, contours)
	d_sib   = _containment_depth(1, contours)
	assert d_outer == 0, 'outer depth should be 0, got {}'.format(d_outer)
	assert d_sib == 0, \
		'sibling should NOT be nested (PIP says outside), got depth={}'.format(d_sib)
	print('  CJK sibling strokes: bbox-encloses but PIP rejects [OK]')


def _test_containment_real_nesting_still_works():
	'''Regression: a real O-glyph (outer + hole) must still report
	depth 0 and depth 1 after the refinement.'''
	outer = _rect_contour(0, 0, 400, 400)
	hole  = _rect_contour(100, 100, 200, 200, ccw=False)
	contours = [outer, hole]
	assert _containment_depth(0, contours) == 0
	assert _containment_depth(1, contours) == 1
	print('  real O-glyph nesting preserved [OK]')


def _test_containment_area_ratio_rejects_overlap():
	'''Two rectangles of similar size: the larger one's bbox encloses the
	smaller by a hair, but they're clearly overlapping siblings. The area
	ratio gate should reject this.'''
	big   = _rect_contour(0, 0, 100, 100)
	small = _rect_contour(2, 2, 96, 96)    # 92% of big's area
	contours = [big, small]
	# Without area-ratio gate: small would be "nested" in big.
	# With it: rejected (ratio > 0.8).
	assert _containment_depth(1, contours) == 0, \
		'area-ratio gate failed to reject sibling overlap'
	print('  area-ratio gate rejects near-same-size overlap [OK]')


def _run_stage7_tests():
	print('Stage 7 - match_contour_order:')
	_test_match_contour_order_shuffled_identity()
	_test_match_contour_order_similar_not_equal()
	_test_match_contour_order_containment_gate()
	_test_match_contour_order_count_mismatch()
	_test_match_contour_order_topology_mismatch()
	_test_match_contour_order_empty()
	_test_match_contour_order_layer_in_layer_out()
	_test_match_contour_order_shape_in_shape_out()
	_test_containment_cjk_sibling_strokes()
	_test_containment_real_nesting_still_works()
	_test_containment_area_ratio_rejects_overlap()
	print('Stage 7: all tests passed.')


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
	print('')
	_run_stage6_tests()
	print('')
	_run_stage7_tests()
