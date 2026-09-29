# MODULE: TypeRig / Core / Actions — regression tests
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# Flat, dependency-free regression suite for core actions.
# Run with: python test_actions.py
# Prints PASS/FAIL per check; exits non-zero on any failure.
# No pytest — must run inside FontLab's bundled Python.

# - Dependencies ------------------------
import math
import os
import sys

# - Init -------------------------------
__version__ = '0.1.0'

# - Path bootstrap (repo checkout without install) ---
try:
	import typerig.core
except ImportError:
	_LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
	sys.path.insert(0, _LIB_DIR)

from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.node import Node, node_types
from typerig.core.objects.contour import Contour
from typerig.core.actions.node_actions import NodeActions

# - Harness ----------------------------
fails = []
total = [0]

def check(name, cond):
	total[0] += 1
	print(('PASS' if cond else 'FAIL'), '-', name)
	if not cond:
		fails.append(name)

def close(a, b, tol=1e-2):
	return abs(a - b) <= tol

def same_segment(segment, reference, tol=1e-2):
	if segment is None:
		return False

	return all(close(a[0], b[0], tol) and close(a[1], b[1], tol)
				for a, b in zip(segment.tuple, reference.tuple))


# ===========================================================
# - corner_rebuild: collapse a corner back to a cusp --------
# ===========================================================
# The tool takes a selection bracketing a rounded or multi-node corner and
# rebuilds the cusp at the crossing of the two surviving sides. Either side
# may be a line or a curve; a curve must come back with the curvature it had
# before the corner was rounded away, not straightened.

KAPPA = 4. * (math.sqrt(2.) - 1.) / 3.		# circular arc handle constant
ON = node_types['on']
CV = node_types['curve']

# - The reference corner throughout: a cusp at (200, 0) between a horizontal
#   line arriving from the left and a quarter arc leaving to (100, 100)
ARC_OUT = CubicBezier((200., 0.), (200., 100. * KAPPA), (200. - 100. * KAPPA, 100.), (100., 100.))
ARC_IN = CubicBezier((100., 100.), (100. + 100. * KAPPA, 100.), (200., 100. * KAPPA), (200., 0.))


# -- Line -- corner -- Curve: the case the tool used to get wrong ---------
_, _arc = ARC_OUT.solve_slice(.15)		# rounding ate the arc's first 15%

_c1 = Contour([
	Node(0., 0., type=ON),								# 0  line start
	Node(170., 0., type=ON),							# 1  line end     <- selected
	Node(185., 0., type=CV),							# 2  corner
	Node(_arc.p0.x, _arc.p0.y - 12., type=CV),			# 3  corner
	Node(_arc.p0.x, _arc.p0.y, type=ON),				# 4  arc start    <- selected
	Node(_arc.p1.x, _arc.p1.y, type=CV),				# 5
	Node(_arc.p2.x, _arc.p2.y, type=CV),				# 6
	Node(100., 100., type=ON),							# 7  arc end
	Node(0., 100., type=ON),							# 8
], closed=True)

check('A1 line/curve rebuilt', NodeActions.corner_rebuild(_c1, [1, 4]) is True)
check('A1 line/curve cusp at (200,0)', close(_c1.nodes[1].x, 200.) and close(_c1.nodes[1].y, 0.))
check('A1 line/curve arc restored', same_segment(_c1.nodes[1].segment, ARC_OUT))
check('A1 line/curve line projected', same_segment(_c1.nodes[0].segment, Line((0., 0.), (200., 0.))))
check('A1 line/curve corner dropped', len(_c1.nodes) == 6)
check('A1 line/curve cusp not smooth', _c1.nodes[1].smooth is False)


# -- Curve -- corner -- Line: mirrored ------------------------------------
_arc_in, _ = ARC_IN.solve_slice(.85)

_c2 = Contour([
	Node(100., 100., type=ON),							# 0  arc start
	Node(_arc_in.p1.x, _arc_in.p1.y, type=CV),			# 1
	Node(_arc_in.p2.x, _arc_in.p2.y, type=CV),			# 2
	Node(_arc_in.p3.x, _arc_in.p3.y, type=ON),			# 3  arc end      <- selected
	Node(_arc_in.p3.x + 6., _arc_in.p3.y - 10., type=CV),	# 4  corner
	Node(200., -20., type=CV),							# 5  corner
	Node(200., -30., type=ON),							# 6  line start   <- selected
	Node(200., -200., type=ON),							# 7  line end
	Node(0., -200., type=ON),							# 8
], closed=True)

check('A2 curve/line rebuilt', NodeActions.corner_rebuild(_c2, [3, 6]) is True)
check('A2 curve/line cusp at (200,0)', close(_c2.nodes[3].x, 200.) and close(_c2.nodes[3].y, 0.))
check('A2 curve/line arc restored', same_segment(_c2.nodes[0].segment, ARC_IN))
check('A2 curve/line outgoing stays a line', isinstance(_c2.nodes[3].segment, Line))


# -- Curve -- corner -- Curve: two arcs at a right-angle cusp -------------
_arc_b = CubicBezier((200., 0.), (200. + 100. * KAPPA, 0.), (300., 100. - 100. * KAPPA), (300., 100.))
_a_in, _ = ARC_IN.solve_slice(.80)
_, _b_out = _arc_b.solve_slice(.20)

_c3 = Contour([
	Node(100., 100., type=ON),							# 0
	Node(_a_in.p1.x, _a_in.p1.y, type=CV),				# 1
	Node(_a_in.p2.x, _a_in.p2.y, type=CV),				# 2
	Node(_a_in.p3.x, _a_in.p3.y, type=ON),				# 3  <- selected
	Node(_a_in.p3.x + 5., _a_in.p3.y - 8., type=CV),	# 4  corner
	Node(_b_out.p0.x - 8., _b_out.p0.y - 5., type=CV),	# 5  corner
	Node(_b_out.p0.x, _b_out.p0.y, type=ON),			# 6  <- selected
	Node(_b_out.p1.x, _b_out.p1.y, type=CV),			# 7
	Node(_b_out.p2.x, _b_out.p2.y, type=CV),			# 8
	Node(300., 100., type=ON),							# 9
	Node(100., 300., type=ON),							# 10
], closed=True)

check('A3 curve/curve rebuilt', NodeActions.corner_rebuild(_c3, [3, 6]) is True)
check('A3 curve/curve cusp at (200,0)', close(_c3.nodes[3].x, 200.) and close(_c3.nodes[3].y, 0.))
check('A3 curve/curve incoming restored', same_segment(_c3.nodes[0].segment, ARC_IN))
check('A3 curve/curve outgoing restored', same_segment(_c3.nodes[3].segment, _arc_b))
check('A3 curve/curve both sides kept handles', len(_c3.nodes) == 8)


# -- Line -- corner -- Line: the original behaviour must not regress ------
_c4 = Contour([
	Node(0., 0., type=ON),
	Node(170., 0., type=ON),							# 1  <- selected
	Node(200., -30., type=ON),							# 2  <- selected
	Node(200., -200., type=ON),
	Node(0., -200., type=ON),
], closed=True)

check('A4 line/line rebuilt', NodeActions.corner_rebuild(_c4, [1, 2]) is True)
check('A4 line/line cusp at (200,0)', close(_c4.nodes[1].x, 200.) and close(_c4.nodes[1].y, 0.))
check('A4 line/line corner dropped', len(_c4.nodes) == 4)


# -- A corner spanning several nodes collapses in one go ------------------
_c5 = Contour([
	Node(0., 0., type=ON),
	Node(150., 0., type=ON),							# 1  <- selected
	Node(175., 5., type=ON),							# 2  corner
	Node(190., 15., type=ON),							# 3  corner
	Node(200., -10., type=ON),							# 4  <- selected
	Node(200., -200., type=ON),
	Node(0., -200., type=ON),
], closed=True)

check('A5 multi-node corner rebuilt', NodeActions.corner_rebuild(_c5, [1, 4]) is True)
check('A5 multi-node cusp at (200,0)', close(_c5.nodes[1].x, 200.) and close(_c5.nodes[1].y, 0.))
check('A5 multi-node all dropped', len(_c5.nodes) == 4)


# -- The corner may straddle the contour's start point --------------------
# The selection is reported in contour order, so when the start point sits
# inside the corner the node AFTER the corner is reported first. Reading the
# ends in plain order would then take the corner the wrong way round and
# delete most of the contour. Every selected node has to end up inside the
# stretch that gets dropped, which is what settles the direction.

_c9 = Contour([
	Node(190., 10., type=ON),							# 0  corner  (start point!)
	Node(200., -10., type=ON),							# 1  <- reported first
	Node(200., -200., type=ON),							#    line end
	Node(0., -200., type=ON),
	Node(0., 0., type=ON),
	Node(150., 0., type=ON),							# 5  <- reported last
	Node(175., 5., type=ON),							# 6  corner
], closed=True)

check('A9 wrapped corner rebuilt', NodeActions.corner_rebuild(_c9, [0, 1, 5, 6]) is True)
check('A9 wrapped cusp at (200,0)',
		any(close(node.x, 200.) and close(node.y, 0.) for node in _c9.nodes))
check('A9 wrapped kept the far side', len(_c9.nodes) == 4)
check('A9 wrapped kept (0,-200)', any(close(n.x, 0.) and close(n.y, -200.) for n in _c9.nodes))
check('A9 wrapped kept (0,0)', any(close(n.x, 0.) and close(n.y, 0.) for n in _c9.nodes))
check('A9 wrapped dropped the corner nodes',
		not any(close(n.x, 190.) and close(n.y, 10.) for n in _c9.nodes)
		and not any(close(n.x, 175.) and close(n.y, 5.) for n in _c9.nodes))

# -- Winding must not matter: the same corner, contour reversed -----------
# Reversing the winding swaps which way round is "shorter"; the result has to
# be identical either way.

_c10 = Contour([
	Node(0., 0., type=ON),
	Node(150., 0., type=ON),							# 1  <- selected
	Node(175., 5., type=ON),							# 2  corner
	Node(190., 10., type=ON),							# 3  corner
	Node(200., -10., type=ON),							# 4  <- selected
	Node(200., -200., type=ON),
	Node(0., -200., type=ON),
], closed=True)
_c10.reverse()

_c10_sel = [i for i, n in enumerate(_c10.nodes)
			if any(close(n.x, x) and close(n.y, y)
					for x, y in ((150., 0.), (175., 5.), (190., 10.), (200., -10.)))]

check('A10 reversed winding rebuilt', NodeActions.corner_rebuild(_c10, _c10_sel) is True)
check('A10 reversed cusp at (200,0)',
		any(close(n.x, 200.) and close(n.y, 0.) for n in _c10.nodes))
check('A10 reversed kept the far side', len(_c10.nodes) == 4)


# -- Winding invariance, line/curve and curve/line ------------------------
# The same physical corner, built both ways round. Reversing a contour swaps
# which side of the corner is the incoming one, so LL--XX--AA in one winding
# is AA--XX--LL in the other. Both must land on the same cusp.

def _corner_contour(reverse):
	'''Line (0,0)->(170,0), rounded corner, quarter arc up to (100,100).
	Cusp of the two sides is (200, 0).'''
	_, arc = ARC_OUT.solve_slice(.15)
	contour = Contour([
		Node(0., 0., type=ON),							# 0
		Node(170., 0., type=ON),						# 1  <- selected
		Node(185., 0., type=CV),						# 2  corner
		Node(arc.p0.x, arc.p0.y - 12., type=CV),		# 3  corner
		Node(arc.p0.x, arc.p0.y, type=ON),				# 4  <- selected
		Node(arc.p1.x, arc.p1.y, type=CV),				# 5
		Node(arc.p2.x, arc.p2.y, type=CV),				# 6
		Node(100., 100., type=ON),						# 7
		Node(0., 100., type=ON),						# 8
	], closed=True)

	if reverse:
		contour.reverse()

	picked = [i for i, n in enumerate(contour.nodes)
				if n.is_on and (close(n.x, 170.) and close(n.y, 0.)
								or close(n.x, arc.p0.x) and close(n.y, arc.p0.y))]
	return contour, picked

for _rev in (False, True):
	_label = 'reversed' if _rev else 'forward'
	_cw, _sel = _corner_contour(_rev)

	check('A11 {} rebuilt'.format(_label), NodeActions.corner_rebuild(_cw, _sel) is True)
	check('A11 {} cusp at (200,0)'.format(_label),
			any(n.is_on and close(n.x, 200.) and close(n.y, 0.) for n in _cw.nodes))
	check('A11 {} arc survives as a curve'.format(_label),
			any(n.type == CV for n in _cw.nodes))
	check('A11 {} kept (100,100) and (0,100)'.format(_label),
			any(close(n.x, 100.) and close(n.y, 100.) for n in _cw.nodes)
			and any(close(n.x, 0.) and close(n.y, 100.) for n in _cw.nodes))
	check('A11 {} kept (0,0)'.format(_label),
			any(close(n.x, 0.) and close(n.y, 0.) for n in _cw.nodes))


# -- Restoring a circular cutout must not deform the circle ---------------
# A rectangle with a circle bitten out of one corner, the resulting cusp then
# rounded off. Rebuilding the cusp has to give the circle back untouched: the
# rounding trims the arc by de Casteljau, so extending it by de Casteljau
# restores the original cubic exactly - not approximately. If this ever drifts,
# restored arcs will look slack next to the untouched part of the cutout.

_R, _CX, _CY = 180., 180., 0.
_cut_arc = CubicBezier((_CX - _R, _CY), (_CX - _R, _CY + _R * KAPPA),
						(_CX - _R * KAPPA, _CY + _R), (_CX, _CY + _R))

def _circle_deviation(curve, samples=128):
	'''Worst distance between the curve and the true circle it approximates.'''
	worst = 0.

	for i in range(samples + 1):
		point = curve.solve_point(i / float(samples))
		worst = max(worst, abs(math.hypot(point.x - _CX, point.y - _CY) - _R))

	return worst

_baseline = _circle_deviation(_cut_arc)		# the cubic's own approximation error

for _radius in (10., 25., 60., 120.):
	_, _trimmed = _cut_arc.solve_slice_distance(_radius, from_start=True)
	_edge = Line((-400., 0.), (-_radius, 0.))
	_ni, _no, _pt = CubicBezier.corner_rebuild(_edge, _trimmed)

	check('A12 r={:.0f} cusp back at the circle/edge meeting point'.format(_radius),
			_pt is not None and close(_pt.x, 0., 1e-6) and close(_pt.y, 0., 1e-6))
	check('A12 r={:.0f} arc restored EXACTLY'.format(_radius),
			_no is not None and all(close(a[0], b[0], 1e-6) and close(a[1], b[1], 1e-6)
									for a, b in zip(_no.tuple, _cut_arc.tuple)))
	check('A12 r={:.0f} circle not deformed'.format(_radius),
			_no is not None and _circle_deviation(_no) <= _baseline + 1e-6)


# -- Refusals leave the contour exactly as it was -------------------------
_c6 = Contour([
	Node(0., 0., type=ON),
	Node(100., 0., type=ON),							# 1  <- selected
	Node(150., 0., type=ON),							# 2  <- selected
	Node(250., 0., type=ON),							# parallel: never crosses
	Node(250., 100., type=ON),
], closed=True)
_c6_before = [node.tuple for node in _c6.nodes]

check('A6 parallel sides refused', NodeActions.corner_rebuild(_c6, [1, 2]) is False)
check('A6 contour untouched', [node.tuple for node in _c6.nodes] == _c6_before)

_c7 = Contour([Node(0., 0., type=ON), Node(100., 0., type=ON), Node(100., 100., type=ON)], closed=True)
check('A7 single on-curve node refused', NodeActions.corner_rebuild(_c7, [1]) is False)


# -- cleanup=False only pulls the selection onto the cusp -----------------
_c8 = Contour([
	Node(0., 0., type=ON),
	Node(170., 0., type=ON),							# 1  <- selected
	Node(200., -30., type=ON),							# 2  <- selected
	Node(200., -200., type=ON),
	Node(0., -200., type=ON),
], closed=True)

check('A8 no-cleanup rebuilt', NodeActions.corner_rebuild(_c8, [1, 2], cleanup=False) is True)
check('A8 no-cleanup keeps node count', len(_c8.nodes) == 5)
check('A8 no-cleanup both on the cusp',
		close(_c8.nodes[1].x, 200.) and close(_c8.nodes[1].y, 0.)
		and close(_c8.nodes[2].x, 200.) and close(_c8.nodes[2].y, 0.))


# - Finish -----------------------------
print()
if fails:
	print('{} CHECK(S) FAILED:'.format(len(fails)))
	for name in fails:
		print('  FAIL -', name)
else:
	print('ALL PASS ({} checks)'.format(total[0]))

sys.exit(1 if fails else 0)
