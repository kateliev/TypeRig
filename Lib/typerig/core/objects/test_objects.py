# MODULE: TypeRig / Core / Objects — regression tests
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# Flat, dependency-free regression suite for core objects and func.
# Run with: python test_objects.py
# Prints PASS/FAIL per check; exits non-zero on any failure.
# No pytest — must run inside FontLab's bundled Python.

# - Dependencies ------------------------
import math
import os
import sys

# - Init -------------------------------
__version__ = '0.2.0'

# - Path bootstrap (repo checkout without install) ---
try:
	import typerig.core
except ImportError:
	_LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
	sys.path.insert(0, _LIB_DIR)

from typerig.core.func.math import normalize2max, renormalize, isclose
from typerig.core.func.geometry import poly_area, point_in_triangle
from typerig.core.func.string import is_hex
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.transform import Transform
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.quadraticbezier import QuadraticBezier
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.utils import linAxis
from typerig.core.objects.atom import Linker

# - Harness ----------------------------
fails = []
total = [0]

def check(name, cond):
	total[0] += 1
	print(('PASS' if cond else 'FAIL'), '-', name)
	if not cond:
		fails.append(name)

def close(a, b, tol=1e-6):
	return abs(a - b) <= tol


# ===========================================================
# - S1 regression checks (ported from verify_s1_fixes.py) ---
# ===========================================================

# 1. Point component-wise mul/div (complex=False)
p = Point(2., 3.); p.complex_math = False
q = Point(4., 5.); q.complex_math = False
r = p * q
check('Point.__mul__ component-wise', (r.x, r.y) == (8., 15.))
r = p / q
check('Point.__div__ component-wise', (r.x, r.y) == (0.5, 0.6))

# 2. Point equality / hash
check('Point eq value-based', Point(1, 2) == Point(1, 2))
check('Point eq tuple', Point(1, 2) == (1., 2.))
check('Point hash consistent', hash(Point(1, 2)) == hash(Point(1, 2)))

# 3. Bezier equality
c1 = CubicBezier((0,0), (10,10), (20,10), (30,0))
c2 = CubicBezier((0,0), (10,10), (20,10), (30,0))
check('CubicBezier eq value-based', c1 == c2)
check('QuadraticBezier eq value-based',
	QuadraticBezier((0,0), (5,5), (10,0)) == QuadraticBezier((0,0), (5,5), (10,0)))

# 4. truediv on Line & beziers
half = Line(Point(0,0), Point(10,10)) / 2
check('Line / scalar', half.p1 == (5., 5.))
check('CubicBezier / scalar', (c1 / 2).p3 == (15., 0.))
check('QuadraticBezier / scalar', (QuadraticBezier((0,0), (5,5), (10,0)) / 2).p2 == (5., 0.))

# 5. Clone constructors deep-copy points
la = Line(Point(0,0), Point(10,0)); lb = Line(la); lb.shift(5, 5)
check('Line clone independent', la.p0 == (0., 0.))
ca = CubicBezier(c1); ca.p0.x = 999
check('CubicBezier clone independent', c1.p0.x == 0)

# 6. 8-scalar ctor + scale()
c8 = CubicBezier(0., 0., 10., 10., 20., 10., 30., 0.)
check('CubicBezier 8-scalar ctor', c8 == c1)
cs = c1.scale(2.0)
check('CubicBezier.scale', cs.p3 == (60., 0.) and cs.p1 == (20., 20.))
qs = QuadraticBezier((0,0), (5,5), (10,0)).scale(2.0)
check('QuadraticBezier.scale', qs.p2 == (20., 0.) and qs.p1 == (10., 10.))

# 7. asList
check('CubicBezier.asList', c1.asList() == c1.points)
check('QuadraticBezier.asList', QuadraticBezier((0,0), (5,5), (10,0)).asList() is not None)

# 8. find_roots quadratic fallback (cubic coefficient vanishes in x)
cq = CubicBezier((0,-10), (10,30), (20,30), (30,-10))
rx, ry = cq.find_roots()
check('find_roots y-roots on degenerate-x cubic', len(ry) == 2)

line = Line(Point(0, 5), Point(30, 5))
times, points = cq.intersect_line(line)
check('intersect_line finds crossings', len(points[1]) == 2)

# 9. Inflection points closed form
s_curve = CubicBezier((0,0), (50,100), (50,-100), (100,0))
infl = s_curve.get_inflection_points()
check('inflection on S-curve == 1', len(infl) == 1 and abs(infl[0][1] - 0.5) < 1e-9)
arc = CubicBezier((0,0), (0,55), (45,100), (100,100))
check('inflection on arc == 0', len(arc.get_inflection_points()) == 0)

# 10. get_handle_length uses correct handles
gh = CubicBezier((0,0), (0,10), (50,20), (100,20)).get_handle_length()
check('get_handle_length distinct handles', abs(gh[0][1] - 10.) < 1e-9 and abs(gh[1][1] - 50.) < 1e-9)

# 11. poly_area translation-invariant
sq0 = [(0,0), (200,0), (200,200), (0,200)]
sq1 = [(100,100), (300,100), (300,300), (100,300)]
check('poly_area translated square', poly_area(sq0) == poly_area(sq1) == 40000)

# 12. point_in_triangle both windings
tri_ccw = ((0,0), (10,0), (5,10)); tri_cw = ((0,0), (5,10), (10,0))
check('point_in_triangle CCW', point_in_triangle((5,3), tri_ccw))
check('point_in_triangle CW', point_in_triangle((5,3), tri_cw))
check('point_in_triangle outside', not point_in_triangle((50,50), tri_ccw))

# 13. normalizers preserve order
vals = [30, 10, 20]
check('normalize2max order', normalize2max(vals) == [1.0, 1/3, 2/3])
check('renormalize order', renormalize(vals, (0, 100)) == [100.0, 0.0, 50.0])

# 14. isclose sane default
check('isclose default strict', not isclose(1.0, 1.5))
check('isclose explicit loose', isclose(1.0, 1.5, abs_tol=1))

# 15. Transform eq/hash
t1 = Transform().shift(10, 10); t2 = Transform().shift(10, 10)
check('Transform eq', t1 == t2)
check('Transform hash', hash(t1) == hash(t2))
check('Transform inverse roundtrip',
	t1.inverse().applyTransformation(*t1.applyTransformation(3, 4)) == (3., 4.))

# 16. is_hex guards
check('is_hex int', not is_hex(30))
check('is_hex empty', not is_hex(''))
check('is_hex valid', is_hex('#FF3B30'))

# 17. Glyph unicode setter + set_mark(int)
g = Glyph([Layer([], name='Regular')], name='test')
g.unicodes = [65]
g.unicode = 97
check('Glyph.unicode setter', g.unicode == 97)
g.set_mark(120)  # int hue — used to crash
check('Glyph.set_mark(int)', isinstance(g.mark, str) and g.mark.startswith('#'))
g.set_mark('Red')
check('Glyph.set_mark(name)', g.mark == '#FF3B30')

# 18. linAxis nonzero minimum position
ax = linAxis({100: 50, 900: 750}, 3)
check('linAxis endpoints map to axis range', min(ax.instances) == 100 and max(ax.instances) == 900)

# 19. Node.smart_shift call sites (randomize should not raise)
src = [Node(0.,0.,type='on'), Node(100.,0.,type='on'), Node(100.,100.,type='on'), Node(0.,100.,type='on')]
cont = Contour(src, closed=True)
cont.nodes[0].randomize(2, 2)
check('Node.randomize runs', True)

# lerp_shift on line-line corner
src2 = [Node(0.,0.,type='on'), Node(100.,0.,type='on'), Node(100.,100.,type='on'), Node(0.,100.,type='on')]
cont2 = Contour(src2, closed=True)
cont2.nodes[1].lerp_shift(5, 5)
check('Node.lerp_shift line-line runs', cont2.nodes[1].x == 105.)

# 20. Linker tail removal
a, b = Linker(1), Linker(2)
a + b
a - b
check('Linker remove tail', a.next is None)

# 21. solve_parallel semantics
arch = CubicBezier((0,0), (0,100), (100,100), (100,0))
t = arch.solve_parallel((1, 0))
check('solve_parallel horizontal tangent at t=0.5', t is not None and abs(t - 0.5) < 1e-9)

skew = CubicBezier((0,0), (30,90), (80,110), (100,0))
t2 = skew.solve_parallel((1, 1))
if t2 is not None:
	d1 = skew.solve_derivative_at_time(t2)[1]
	check('solve_parallel general parallelism', abs(d1.x*1 - d1.y*1) < 1e-6)
else:
	check('solve_parallel general returned a root', False)

qb = QuadraticBezier((0,0), (50,100), (100,0))
tq = qb.solve_parallel((1, 0))
tcu = qb.to_cubic().solve_parallel((1, 0))
check('solve_parallel cubic/quad agree', tq is not None and tcu is not None and abs(tq - tcu) < 1e-9)

# 22. Shape/Layer lerp_function guard rejects incompatible
s_a = Shape([Contour([Node(0,0,type='on'), Node(10,0,type='on'), Node(10,10,type='on')], closed=True)])
s_b = Shape([Contour([Node(0,0,type='on'), Node(10,0,type='on'), Node(10,10,type='curve')], closed=True)])
check('Shape.lerp_function rejects incompatible', s_a.lerp_function(s_b) is None)


# ===========================================================
# - Structural round-trips (Stage 0 additions) --------------
# ===========================================================

# 23. Contour XML round-trip: node count, types, coordinates
src_mixed = [
	Node(200.0, 280.0, type='on'),
	Node(760.0, 280.0, type='on'),
	Node(804.0, 280.0, type='curve'),
	Node(840.0, 316.0, type='curve'),
	Node(840.0, 360.0, type='on'),
	Node(200.0, 360.0, type='on'),
]
cont_xml = Contour([n.clone() for n in src_mixed], closed=True)
restored = Contour.from_XML(cont_xml.to_XML())
check('XML round-trip node count', len(restored.nodes) == len(cont_xml.nodes))
check('XML round-trip node types',
	[n.type for n in restored.nodes] == [n.type for n in cont_xml.nodes])
check('XML round-trip coordinates',
	all(close(a.x, b.x) and close(a.y, b.y) for a, b in zip(restored.nodes, cont_xml.nodes)))
check('XML round-trip closed flag', restored.closed == cont_xml.closed)

# 24. Directional round-trip: on-curve coordinates within 1e-6
src_circle = [
	Node(161.0, 567.0, type='on'),
	Node(161.0, 435.0, type='curve'),
	Node(268.0, 328.0, type='curve'),
	Node(400.0, 328.0, type='on'),
	Node(531.0, 328.0, type='curve'),
	Node(638.0, 435.0, type='curve'),
	Node(638.0, 567.0, type='on'),
	Node(638.0, 698.0, type='curve'),
	Node(531.0, 805.0, type='curve'),
	Node(400.0, 805.0, type='on'),
	Node(268.0, 805.0, type='curve'),
	Node(161.0, 698.0, type='curve'),
]
circle = Contour(src_circle, closed=True)
directional = circle.to_directional()
rebuilt = Contour.from_directional(directional, closed=True)
orig_on = [(n.x, n.y) for n in circle.nodes if n.is_on]
new_on = [(n.x, n.y) for n in rebuilt.nodes if n.is_on]
check('directional round-trip on-curve count', len(orig_on) == len(new_on))
check('directional round-trip on-curve coords',
	all(close(a[0], b[0]) and close(a[1], b[1]) for a, b in zip(orig_on, new_on)))

# 25. solve_slice(0.5): both halves share the point solve_point(0.5)
known = CubicBezier((0,0), (10,90), (90,90), (100,0))
mid = known.solve_point(0.5)
first_half, second_half = known.solve_slice(0.5)
check('solve_slice shared point (first half end)',
	close(first_half.p3.x, mid.x, 1e-9) and close(first_half.p3.y, mid.y, 1e-9))
check('solve_slice shared point (second half start)',
	close(second_half.p0.x, mid.x, 1e-9) and close(second_half.p0.y, mid.y, 1e-9))

# 26. get_arc_length of straight-line cubic == 100
straight = CubicBezier((0,0), (25,0), (75,0), (100,0))
check('get_arc_length straight cubic == 100', close(straight.get_arc_length(), 100.0))


# ===========================================================
# - Stage 1: PointsArithmetic mixin -------------------------
# ===========================================================

lm = Line((0,0), (10,10)) * 2
check('Line * scalar type', isinstance(lm, Line))
check('Line * scalar coords', lm.p0 == (0., 0.) and lm.p1 == (20., 20.))

crm = 2 * CubicBezier((0,0), (10,10), (20,10), (30,0))
check('scalar * CubicBezier type', isinstance(crm, CubicBezier))
check('scalar * CubicBezier coords', crm.p1 == (20., 20.) and crm.p3 == (60., 0.))

qd = QuadraticBezier((0,0), (5,5), (10,0)) / 2
check('QuadraticBezier / scalar type', isinstance(qd, QuadraticBezier))
check('QuadraticBezier / scalar coords', qd.p1 == (2.5, 2.5) and qd.p2 == (5., 0.))

cadd = CubicBezier((0,0), (10,10), (20,10), (30,0)) + (5, 5)
check('CubicBezier + tuple type', isinstance(cadd, CubicBezier))
check('CubicBezier + tuple coords', cadd.p0 == (5., 5.) and cadd.p3 == (35., 5.))

check('legacy __div__ alias', (Line((0,0), (10,10)).__div__(2)).p1 == (5., 5.))


# ===========================================================
# - Stage 2: effective __slots__ ----------------------------
# ===========================================================

check('Node has no __dict__', not hasattr(Node(0, 0), '__dict__'))
check('Contour has no __dict__', not hasattr(Contour([Node(0,0,type='on'), Node(10,0,type='on')], closed=False), '__dict__'))
check('Layer has no __dict__', not hasattr(Layer([], name='x'), '__dict__'))
check('Glyph has no __dict__', not hasattr(Glyph([Layer([], name='x')], name='g'), '__dict__'))

# Member-initialized lib is present and per-instance
n_lib = Node(0, 0)
check('Node.lib initialized', n_lib.lib == {})

# scale_with_axis result still exposes diagnostics via getattr contract
sq_a = [[(0.,0.), (100.,0.), (100.,100.), (0.,100.)]]
sq_b = [[(0.,0.), (200.,0.), (200.,200.), (0.,200.)]]
lay_a = Layer([sq_a], name='A', width=120.)
lay_b = Layer([sq_b], name='B', width=240.)
lay_a.stems = (80., 80.)
lay_b.stems = (140., 140.)
g_axis = Glyph([lay_a, lay_b], name='sq')
vaxis = g_axis.create_virtual_axis(['A', 'B'])
scaled = g_axis.layer('A').scale_with_axis(vaxis, target_width=150.)
check('scale_with_axis _scale_converged exposed',
	getattr(scaled, '_scale_converged', None) is not None)
check('scale_with_axis _scale_factors exposed',
	isinstance(getattr(scaled, '_scale_factors', None), tuple))
check('scale_with_axis hits target width',
	abs(scaled.bounds.width - 150.) <= 1.0)


# ===========================================================
# - Stage 3: unified signed area ----------------------------
# ===========================================================

from typerig.core.func.geometry import poly_area_signed

unit_ccw = [Node(0.,0.,type='on'), Node(1.,0.,type='on'), Node(1.,1.,type='on'), Node(0.,1.,type='on')]
unit_cw = [Node(0.,0.,type='on'), Node(0.,1.,type='on'), Node(1.,1.,type='on'), Node(1.,0.,type='on')]
c_ccw = Contour([n.clone() for n in unit_ccw], closed=True)
c_cw = Contour([n.clone() for n in unit_cw], closed=True)

check('signed area CCW square == +1 (on)', close(c_ccw.get_signed_area('on'), 1.0))
check('signed area CCW square == +1 (sampled)', close(c_ccw.get_signed_area('sampled'), 1.0))
check('signed area CCW square == +1 (knots)', close(c_ccw.get_signed_area('knots'), 1.0))
check('signed area CW square == -1 (on)', close(c_cw.get_signed_area('on'), -1.0))
check('signed area CW square == -1 (sampled)', close(c_cw.get_signed_area('sampled'), -1.0))
check('signed area CW square == -1 (knots)', close(c_cw.get_signed_area('knots'), -1.0))

check('signed_area property alias', close(c_ccw.signed_area, c_ccw.get_signed_area('sampled')))
check('get_on_area historical sign (CW positive)', c_cw.get_on_area() > 0 and c_ccw.get_on_area() < 0)

# get_winding unchanged for the three contour.py __main__ test contours
src_frame = [
	Node(200.,280.,type='on'), Node(760.,280.,type='on'), Node(804.,280.,type='curve'),
	Node(840.,316.,type='curve'), Node(840.,360.,type='on'), Node(840.,600.,type='on'),
	Node(840.,644.,type='curve'), Node(804.,680.,type='curve'), Node(760.,680.,type='on'),
	Node(200.,680.,type='on'), Node(156.,680.,type='curve'), Node(120.,644.,type='curve'),
	Node(120.,600.,type='on'), Node(120.,360.,type='on'), Node(120.,316.,type='curve'),
	Node(156.,280.,type='curve')]
src_square_cw = [
	Node(200.,280.,type='on'), Node(280.,280.,type='on'),
	Node(280.,200.,type='on'), Node(200.,200.,type='on')]
check('get_winding frame (CCW)', Contour(src_frame, closed=True).get_winding() == False)
check('get_winding square (CW)', Contour(src_square_cw, closed=True).get_winding() == True)
src_circle_ccw = [
	Node(161.,567.,type='on'), Node(161.,435.,type='curve'), Node(268.,328.,type='curve'),
	Node(400.,328.,type='on'), Node(531.,328.,type='curve'), Node(638.,435.,type='curve'),
	Node(638.,567.,type='on'), Node(638.,698.,type='curve'), Node(531.,805.,type='curve'),
	Node(400.,805.,type='on'), Node(268.,805.,type='curve'), Node(161.,698.,type='curve')]
check('get_winding circle (CCW)', Contour(src_circle_ccw, closed=True).get_winding() == False)

# 'on' mode ignores BCPs: add a BCP far outside, on-curve area unchanged
sq_curve = Contour([
	Node(0.,0.,type='on'), Node(100.,0.,type='on'),
	Node(5000.,5000.,type='curve'), Node(5000.,-5000.,type='curve'),
	Node(100.,100.,type='on'), Node(0.,100.,type='on')], closed=True)
check('on mode ignores far BCPs', close(sq_curve.get_signed_area('on'), 100.*100.))

# poly_area_signed in func/geometry
check('poly_area_signed CCW', poly_area_signed([(0,0),(1,0),(1,1),(0,1)]) == 0.5 + 0.5)
check('poly_area_signed CW', poly_area_signed([(0,0),(0,1),(1,1),(1,0)]) == -1.0)
check('poly_area abs of signed', poly_area([(10,10),(10,11),(11,11),(11,10)]) == 1.0)


# ===========================================================
# - Stage 4: arc-length parameterization --------------------
# ===========================================================

# Straight-line cubic: t at half length lands at (50, 0)
straight2 = CubicBezier((0,0), (25,0), (75,0), (100,0))
t_half = straight2.solve_t_at_length(50.)
pt_half = straight2.solve_point(t_half)
check('solve_t_at_length straight midpoint', close(pt_half.x, 50., 1e-4) and close(pt_half.y, 0., 1e-4))

# Additivity: len(0,t) + len(t,1) == total for several t
curved = CubicBezier((0,0), (10,90), (90,90), (100,0))
total_len = curved.get_arc_length()
check('_arc_length_between additivity',
	all(close(curved._arc_length_between(0., t) + curved._arc_length_between(t, 1.), total_len)
		for t in (0.25, 0.5, 0.75)))

# divide_at_length: both halves have equal arc length +- 0.01
h1, h2 = curved.divide_at_length(total_len / 2.)
check('divide_at_length equal halves',
	abs(h1.get_arc_length() - h2.get_arc_length()) <= 0.01)

# divide_at_length degenerate ends preserved
d1, d2 = curved.divide_at_length(-5.)
check('divide_at_length <=0 degenerate', d2 is curved and d1.p0 == d1.p3)
d1, d2 = curved.divide_at_length(total_len + 5.)
check('divide_at_length >=total degenerate', d1 is curved and d2.p0 == d2.p3)

# get_point_at_length agrees with solve_point(solve_t_at_length)
gp = curved.get_point_at_length(total_len * 0.3)
tp = curved.solve_point(curved.solve_t_at_length(total_len * 0.3))
check('get_point_at_length via solver', close(gp.x, tp.x) and close(gp.y, tp.y))

# Quadratic: same API and behavior
q_curved = QuadraticBezier((0,0), (50,100), (100,0))
q_total = q_curved.get_arc_length()
qt = q_curved.solve_t_at_length(q_total / 2.)
check('quad solve_t_at_length symmetric midpoint', close(qt, 0.5, 1e-6))
qh1, qh2 = q_curved.divide_at_length(q_total / 2.)
check('quad divide_at_length equal halves',
	abs(qh1.get_arc_length() - qh2.get_arc_length()) <= 0.01)
check('quad arc additivity',
	close(q_curved._arc_length_between(0., 0.3) + q_curved._arc_length_between(0.3, 1.), q_total))


# ===========================================================
# - Stage 5: eval/exec removal ------------------------------
# ===========================================================

from typerig.core.objects.collection import ndList

nd = ndList([[1, 2, 3], [4, 5, 6]])
check('ndList tuple get', nd[1, 2] == 6)
nd[0, 1] = 99
check('ndList tuple set', nd[0, 1] == 99 and nd.data[0][1] == 99)
check('ndList plain index', nd[1] == [4, 5, 6])

lk_a, lk_b, lk_c = Linker(10), Linker(20), Linker(30)
lk_a + lk_b
lk_b + lk_c
found = list(lk_a.where(lambda link: link.data > 15))
check('Linker.where predicate', [l.data for l in found] == [20, 30])


# ===========================================================
# - Stage 6: solve_equations partial pivoting ---------------
# ===========================================================

from typerig.core.func.math import solve_equations
import copy as _copy

# Zero pivot first — old code raised ZeroDivisionError
am_zp = [[0., 1.], [1., 0.]]
bm_zp = [[1.], [2.]]
sol_zp = solve_equations(am_zp, bm_zp)
check('solve_equations zero pivot', close(sol_zp[0][0], 2.) and close(sol_zp[1][0], 1.))

# Well-conditioned 3x3: x=1, y=2, z=3 for this system
am_3 = [[2., 1., -1.], [-3., -1., 2.], [-2., 1., 2.]]
bm_3 = [[1.], [1.], [6.]]  # 2+2-3=1; -3-2+6=1; -2+2+6=6
am_3_ref = _copy.deepcopy(am_3)
bm_3_ref = _copy.deepcopy(bm_3)
sol_3 = solve_equations(am_3, bm_3)
check('solve_equations 3x3 solution',
	close(sol_3[0][0], 1., 1e-9) and close(sol_3[1][0], 2., 1e-9) and close(sol_3[2][0], 3., 1e-9))
check('solve_equations inputs not mutated', am_3 == am_3_ref and bm_3 == bm_3_ref)

# Singular matrix raises ValueError
try:
	solve_equations([[1., 2.], [2., 4.]], [[1.], [2.]])
	check('solve_equations singular raises', False)
except ValueError:
	check('solve_equations singular raises', True)


# ===========================================================
# - Stage 7: Bounds utilities -------------------------------
# ===========================================================

from typerig.core.objects.utils import Bounds

# Empty input raises with a clear message
try:
	Bounds([])
	check('Bounds([]) raises ValueError', False)
except ValueError:
	check('Bounds([]) raises ValueError', True)

# Union of two disjoint boxes
box_a = Bounds([(0., 0.), (10., 10.)])
box_b = Bounds([(20., 20.), (30., 40.)])
u = box_a.union(box_b)
check('Bounds.union disjoint', (u.x, u.y, u.xmax, u.ymax) == (0., 0., 30., 40.))
u2 = Bounds.from_bounds([box_a, box_b])
check('Bounds.from_bounds matches union', (u2.x, u2.y, u2.xmax, u2.ymax) == (u.x, u.y, u.xmax, u.ymax))

# contains: inclusive edges
check('Bounds.contains inside', box_a.contains(5., 5.))
check('Bounds.contains edge inclusive', box_a.contains(0., 0.) and box_a.contains(10., 10.))
check('Bounds.contains outside', not box_a.contains(10.0001, 5.))

# inflate: negative shrink
inf = box_a.inflate(5.)
check('Bounds.inflate grow', (inf.x, inf.y, inf.xmax, inf.ymax) == (-5., -5., 15., 15.))
shr = box_a.inflate(-2., -3.)
check('Bounds.inflate shrink xy', (shr.x, shr.y, shr.xmax, shr.ymax) == (2., 3., 8., 7.))

# Shape.bounds / Layer.bounds unchanged for layer.py __main__ test data
# (expected values recorded from pre-refactor run: 120, 280, 840, 680, 720x400)
frame_pts = [(200.0,280.0),(760.0,280.0),(804.0,280.0),(840.0,316.0),(840.0,360.0),
	(840.0,600.0),(840.0,644.0),(804.0,680.0),(760.0,680.0),(200.0,680.0),
	(156.0,680.0),(120.0,644.0),(120.0,600.0),(120.0,360.0),(120.0,316.0),(156.0,280.0)]
lb = Layer([[frame_pts]]).bounds
check('Layer.bounds unchanged',
	(lb.x, lb.y, lb.xmax, lb.ymax, lb.width, lb.height) == (120.0, 280.0, 840.0, 680.0, 720.0, 400.0))
sb = Shape([frame_pts]).bounds
check('Shape.bounds unchanged',
	(sb.x, sb.y, sb.xmax, sb.ymax, sb.width, sb.height) == (120.0, 280.0, 840.0, 680.0, 720.0, 400.0))


# ===========================================================
# - S3 feature gates ----------------------------------------
# ===========================================================

_s3_src_circle = [
	Node(161.0, 567.0, type='on'), Node(161.0, 435.0, type='curve'),
	Node(268.0, 328.0, type='curve'), Node(400.0, 328.0, type='on'),
	Node(531.0, 328.0, type='curve'), Node(638.0, 435.0, type='curve'),
	Node(638.0, 567.0, type='on'), Node(638.0, 698.0, type='curve'),
	Node(531.0, 805.0, type='curve'), Node(400.0, 805.0, type='on'),
	Node(268.0, 805.0, type='curve'), Node(161.0, 698.0, type='curve')]

def _s3_circle():
	return Contour([n.clone() for n in _s3_src_circle], closed=True)

# -- F1: tight (curve-accurate) bounds ----------------------
s3_circle = _s3_circle()
tb = s3_circle.tight_bounds
check('F1 circle tight bounds == on-curve extrema',
	(tb.x, tb.y, tb.xmax, tb.ymax) == (161.0, 328.0, 638.0, 805.0))
cb = s3_circle.bounds
check('F1 circle control box unchanged',
	(cb.x, cb.y, cb.xmax, cb.ymax) == (161.0, 328.0, 638.0, 805.0))

# Contour with BCPs overshooting the on-curve box
overshoot = Contour([
	Node(0.0, 0.0, type='on'), Node(60.0, 110.0, type='curve'),
	Node(40.0, -10.0, type='curve'), Node(100.0, 100.0, type='on')], closed=False)
check('F1 overshoot: control box hits BCPs', overshoot.bounds.ymax == 110.0)
check('F1 overshoot: tight box smaller',
	overshoot.tight_bounds.ymax < 110.0 and overshoot.tight_bounds.y > -10.0)

# Shape / Layer delegation + tight_align_matrix
s3_layer = Layer([Shape([_s3_circle()])])
check('F1 Layer.tight_bounds', s3_layer.tight_bounds.ymax == 805.0)
check('F1 Layer.tight_align_matrix has tiers',
	'TL' in s3_layer.tight_align_matrix and 'ADV' in s3_layer.tight_align_matrix)

# -- F2: point-in-contour / point-in-layer ------------------
s3_square = Contour([Node(200,280,type='on'), Node(280,280,type='on'),
	Node(280,200,type='on'), Node(200,200,type='on')], closed=True)
check('F2 square inside', s3_square.contains_point((240, 240)) is True)
check('F2 square outside', s3_square.contains_point((100, 100)) is False)
check('F2 circle center', _s3_circle().contains_point((400, 567)) is True)
check('F2 circle bbox corner outside', _s3_circle().contains_point((165, 332)) is False)

_outer = Contour([Node(0,0,type='on'), Node(100,0,type='on'), Node(100,100,type='on'), Node(0,100,type='on')], closed=True)
_counter = Contour([Node(40,40,type='on'), Node(60,40,type='on'), Node(60,60,type='on'), Node(40,60,type='on')], closed=True)
_hole_layer = Layer([Shape([_outer, _counter])])
check('F2 layer: counter is empty (even-odd)', _hole_layer.contains_point((50, 50)) is False)
check('F2 layer: between outer and counter', _hole_layer.contains_point((20, 20)) is True)

# -- F3: compatibility diagnosis ----------------------------
la = Layer([Shape([_s3_circle()])])
lb = Layer([Shape([_s3_circle()])])
check('F3 compatible -> []', la.diff_compatibility(lb) == [])
check('F3 compatible -> empty report', la.report_compatibility(lb) == '')

lb.shapes[0].contours[0].nodes[4].type = 'on'
_diff = la.diff_compatibility(lb)
check('F3 one node_type record', len(_diff) == 1 and _diff[0]['kind'] == 'node_type')
check('F3 record has full location',
	_diff[0]['index'] == 4 and _diff[0]['shape'] == 0 and _diff[0]['contour'] == 0)
check('F3 is_compatible False', la.is_compatible(lb) is False)
check('F3 report line format',
	la.report_compatibility(lb) == "shape[0] contour[0] node[4]: type 'curve' != 'on'")

lc = Layer([Shape([_s3_circle(), Contour([n.clone() for n in _s3_src_circle], closed=True)])])
_diff = la.diff_compatibility(lc)
check('F3 contour_count single record', len(_diff) == 1 and _diff[0]['kind'] == 'contour_count')

# -- F4: curve-curve intersection ---------------------------
from typerig.core.algo.intersect import curve_curve_intersections, line_to_cubic

_hits = curve_curve_intersections(line_to_cubic((0.,0.),(100.,100.)), line_to_cubic((0.,100.),(100.,0.)))
check('F4 crossing lines: 1 hit at (50,50)',
	len(_hits) == 1 and abs(_hits[0][2][0] - 50.) <= 0.2 and abs(_hits[0][2][1] - 50.) <= 0.2)

_arch = ((0., 0.), (0., 100.), (100., 100.), (100., 0.))
_mirror = ((0., 75.), (0., -25.), (100., -25.), (100., 75.))
_hits = curve_curve_intersections(_arch, _mirror)
check('F4 arch vs mirror: 2 symmetric hits',
	len(_hits) == 2 and abs(_hits[0][2][0] + _hits[1][2][0] - 100.) <= 0.5)
check('F4 disjoint -> []',
	curve_curve_intersections(_arch, ((500.,500.),(550.,600.),(650.,600.),(700.,500.))) == [])
curve_curve_intersections(_arch, _arch)		# identical curves must terminate (depth cap)
check('F4 identical curves terminate', True)

_arch_b = CubicBezier(*_arch)
_t_pairs, _pts = _arch_b.intersect_curve(CubicBezier(*_mirror))
check('F4 CubicBezier.intersect_curve wrapper', len(_t_pairs) == 2 and len(_pts) == 2)

_bowtie = Contour([Node(0,0,type='on'), Node(100,100,type='on'), Node(100,0,type='on'), Node(0,100,type='on')], closed=True)
_si = _bowtie.self_intersections()
check('F4 figure-eight: exactly 1 crossing', len(_si) == 1)
check('F4 crossing near (50,50)',
	len(_si) == 1 and abs(_si[0][4][0] - 50.) <= 0.5 and abs(_si[0][4][1] - 50.) <= 0.5)
check('F4 convex contour: no self-crossings', _s3_circle().self_intersections() == [])

_sq2 = Contour([Node(50,50,type='on'), Node(150,50,type='on'), Node(150,150,type='on'), Node(50,150,type='on')], closed=True)
check('F4 Contour.intersections: 2 hits', len(_outer.intersections(_sq2)) == 2)

# -- F6: offset loop cleanup --------------------------------
_plain = _s3_circle().offset_outline(-30)
_clean = _s3_circle().offset_outline_clean(-30)
check('F6 convex: node count preserved', len(_clean.nodes) == len(_plain.nodes))
check('F6 convex: converged', _clean._offset_clean_converged is True)

# Chamfered square: the short 45-degree edge inverts on inward offset and
# the adjacent long edges cross. (A plain L never self-crosses with miter
# joins — it inverts globally — so the chamfer is the concave gate case.)
_CH = [(0,0),(270,0),(300,30),(300,300),(0,300)]
_cham = Contour([Node(x, y, type='on') for x, y in _CH], closed=True)
_plain = _cham.offset_outline(-80)
check('F6 concave: plain offset self-intersects', len(_plain.self_intersections()) >= 1)
_clean = _cham.offset_outline_clean(-80)
check('F6 concave: clean has no self-intersections', _clean.self_intersections() == [])
check('F6 concave: converged flag', _clean._offset_clean_converged is True)

# Shoelace counts the inverted loop negatively -> pruning it recovers area
_a_plain = Contour._segments_area(_plain.segments, steps=32)
_a_clean = Contour._segments_area(_clean.segments, steps=32)
check('F6 concave: loop area recovered',
	_a_clean > _a_plain and (_a_clean - _a_plain) / _a_plain < 0.05)

# Multi-crossing case exercises the iterative passes
_cham2 = Contour([Node(x, y, type='on') for x, y in _CH], closed=True)
check('F6 multi-crossing input', len(_cham2.offset_outline(-60).self_intersections()) == 3)
check('F6 multi-crossing cleaned', _cham2.offset_outline_clean(-60).self_intersections() == [])

# Idempotence: cleaning an already-clean contour changes nothing
_again = _clean.offset_outline_clean(0)
check('F6 idempotent', len(_again.nodes) == len(_clean.nodes) and _again.self_intersections() == [])

# -- F7: serialization round-trip ---------------------------
import typerig.core.objects.fontfile as _fontfile_mod
check('F7 import typerig.core.objects.fontfile', hasattr(_fontfile_mod, 'FontFile'))

from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.master import Master, Masters
from typerig.core.objects.kern import Kerning
from typerig.core.objects.groups import Groups

def _s3_glyph(name, dx=0):
	sq = Contour([Node(0+dx,0,type='on'), Node(100+dx,0,type='on'),
		Node(100+dx,100,type='on'), Node(0+dx,100,type='on')], closed=True)
	return Glyph([Layer([Shape([sq])], name='Regular', width=120)], name=name)

_features = 'feature kern {\n\tpos A V -50;\n} kern;\n# <weird & chars>\n'
_kern = Kerning(); _kern.add_pair('A', 'V', -50)
_groups = Groups(); _groups.set('public.kern1.H', ['H', 'I', 'N'])

_font = Font([_s3_glyph('A'), _s3_glyph('V', 10)],
	info=FontInfo('TestFam', 'Regular'),
	metrics=FontMetrics(1000, 800, -200, 500, 700, 0),
	masters=Masters([Master('Regular', 'Regular')]),
	kerning=_kern, groups=_groups, features=_features)

_font2 = Font.from_XML(_font.to_XML())
check('F7 info round-trip', _font2.info.family_name == 'TestFam')
check('F7 metrics round-trip', _font2.metrics.upm == 1000 and _font2.metrics.descender == -200)
check('F7 masters round-trip', len(_font2.masters.data) == 1)
check('F7 kerning round-trip', _font2.kerning[('A', 'V')] == -50)
check('F7 groups round-trip', _font2.groups.members('public.kern1.H') == ['H', 'I', 'N'])
check('F7 features byte-equal', _font2.features == _features)

# -- F8: piecewise multi-master axis ------------------------
from typerig.core.objects.delta import PiecewiseAxis

def _s3_master(name, w, stem):
	c = Contour([Node(0,0,type='on'), Node(w,0,type='on'), Node(w,100,type='on'), Node(0,100,type='on')], closed=True)
	layer = Layer([Shape([c])], name=name, width=w + 20)
	layer.stems = stem
	return layer

_pw_glyph = Glyph([
	_s3_master('Light', 100, (40, 40)),
	_s3_master('Regular', 200, (80, 80)),
	_s3_master('Bold', 400, (160, 160))], name='pwtest')

_axis = _pw_glyph.create_piecewise_axis(['Light', 'Regular', 'Bold'])
_pw = _axis['point_array']
check('F8 PiecewiseAxis type', isinstance(_pw, PiecewiseAxis) and len(_pw) == 2)
check('F8 segment selection', _pw.segment_for_stem((60, 60))[0] == 0 and _pw.segment_for_stem((120, 120))[0] == 1)
check('F8 clamping', _pw.segment_for_stem((10, 10))[0] == 0 and _pw.segment_for_stem((999, 999))[0] == 1)

def _pw_width(stem, extrapolate=False):
	pts = list(_pw.scale_by_stem((stem, stem), (1., 1.), (0., 0.), (0., 0.), 0., extrapolate))
	xs = [p[0] for p in pts]
	return max(xs) - min(xs)

check('F8 stem 60 -> width 150', close(_pw_width(60), 150., 0.5))
check('F8 stem 120 -> width 300', close(_pw_width(120), 300., 0.5))
check('F8 stem 200 extrapolated -> width 500', close(_pw_width(200, True), 500., 1.))
check('F8 knot continuity at stem 80', abs(_pw_width(80 - 1e-4) - _pw_width(80 + 1e-4)) <= 0.1)

_scaled = _pw_glyph.layer('Regular').scale_with_axis(_axis, target_width=300)
check('F8 scale_with_axis duck-type', abs(_scaled.bounds.width - 300.) <= 1.0)
check('F8 scale_with_axis converged', _scaled._scale_converged is True)


# - Finish -----------------------------
print()
if fails:
	print('{} CHECK(S) FAILED:'.format(len(fails)))
	for name in fails:
		print('  FAIL -', name)
else:
	print('ALL PASS ({} checks)'.format(total[0]))

sys.exit(1 if fails else 0)
