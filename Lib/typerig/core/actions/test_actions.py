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
# inside the corner the node AFTER the corner is reported first. The corner is
# the shorter way round, not the longer one; getting this wrong would take
# most of the contour for "the corner".

_c9 = Contour([
	Node(190., 10., type=ON),							# 0  corner  (start point!)
	Node(200., -10., type=ON),							# 1  <- reported first
	Node(200., -200., type=ON),							#    line end
	Node(0., -200., type=ON),
	Node(0., 0., type=ON),
	Node(150., 0., type=ON),							# 5  <- reported last
	Node(175., 5., type=ON),							# 6  corner
], closed=True)

check('A9 wrapped corner rebuilt', NodeActions.corner_rebuild(_c9, [1, 5]) is True)
check('A9 wrapped cusp at (200,0)',
		any(close(node.x, 200.) and close(node.y, 0.) for node in _c9.nodes))
check('A9 wrapped kept the far side', len(_c9.nodes) == 4)
check('A9 wrapped kept (0,-200)', any(close(n.x, 0.) and close(n.y, -200.) for n in _c9.nodes))
check('A9 wrapped kept (0,0)', any(close(n.x, 0.) and close(n.y, 0.) for n in _c9.nodes))


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
