# Targeted verification of the S1 bug fixes
import sys, math
sys.path.insert(0, r'D:\Remote\GitHub\TypeRig\Lib')

from typerig.core.func.math import normalize2max, renormalize, isclose, two_mid_square
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
from typerig.core.objects.utils import linAxis
from typerig.core.objects.atom import Linker

fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), '-', name)
    if not cond: fails.append(name)

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

# 3. Bezier equality now works
c1 = CubicBezier((0,0),(10,10),(20,10),(30,0))
c2 = CubicBezier((0,0),(10,10),(20,10),(30,0))
check('CubicBezier eq value-based', c1 == c2)
check('QuadraticBezier eq value-based',
      QuadraticBezier((0,0),(5,5),(10,0)) == QuadraticBezier((0,0),(5,5),(10,0)))

# 4. truediv on Line & beziers
half = Line(Point(0,0), Point(10,10)) / 2
check('Line / scalar', half.p1 == (5., 5.))
check('CubicBezier / scalar', (c1 / 2).p3 == (15., 0.))
check('QuadraticBezier / scalar', (QuadraticBezier((0,0),(5,5),(10,0)) / 2).p2 == (5., 0.))

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
qs = QuadraticBezier((0,0),(5,5),(10,0)).scale(2.0)
check('QuadraticBezier.scale', qs.p2 == (20., 0.) and qs.p1 == (10., 10.))

# 7. asList restored
check('CubicBezier.asList', c1.asList() == c1.points)
check('QuadraticBezier.asList', QuadraticBezier((0,0),(5,5),(10,0)).asList() is not None)

# 8. find_roots quadratic fallback: curve exactly quadratic in x
# x(t) linear-ish: p0..p3 x evenly spaced -> cubic coef 0 in x
cq = CubicBezier((0,-10),(10,30),(20,30),(30,-10))
rx, ry = cq.find_roots()
check('find_roots y-roots on degenerate-x cubic', len(ry) == 2)

# intersect_line with vertical crossing (old code returned nothing for such curves)
line = Line(Point(0, 5), Point(30, 5))
times, points = cq.intersect_line(line)
check('intersect_line finds crossings', len(points[1]) == 2)

# 9. Inflection points closed form: S-curve has exactly one, arc has none
s_curve = CubicBezier((0,0),(50,100),(50,-100),(100,0))
infl = s_curve.get_inflection_points()
check('inflection on S-curve == 1', len(infl) == 1 and abs(infl[0][1] - 0.5) < 1e-9)
arc = CubicBezier((0,0),(0,55),(45,100),(100,100))
check('inflection on arc == 0', len(arc.get_inflection_points()) == 0)

# 10. get_handle_length uses correct handles
gh = CubicBezier((0,0),(0,10),(50,20),(100,20)).get_handle_length()
check('get_handle_length distinct handles', abs(gh[0][1] - 10.) < 1e-9 and abs(gh[1][1] - 50.) < 1e-9)

# 11. poly_area translation-invariant
sq0 = [(0,0),(200,0),(200,200),(0,200)]
sq1 = [(100,100),(300,100),(300,300),(100,300)]
check('poly_area translated square', poly_area(sq0) == poly_area(sq1) == 40000)

# 12. point_in_triangle both windings
tri_ccw = ((0,0),(10,0),(5,10)); tri_cw = ((0,0),(5,10),(10,0))
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
check('Transform inverse roundtrip', t1.inverse().applyTransformation(*t1.applyTransformation(3, 4)) == (3., 4.))

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

# 21. solve_parallel: tangent parallel to given vector (docstring semantics).
# Horizontal tangent at the arch apex -> vector (1,0).
arch = CubicBezier((0,0),(0,100),(100,100),(100,0))
t = arch.solve_parallel((1, 0))
check('solve_parallel horizontal tangent at t=0.5', t is not None and abs(t - 0.5) < 1e-9)

# Asymmetric curve: returned tangent must actually be parallel to query vector
skew = CubicBezier((0,0),(30,90),(80,110),(100,0))
t2 = skew.solve_parallel((1, 1))
if t2 is not None:
    d1 = skew.solve_derivative_at_time(t2)[1]
    # parallel to (1,1): cross == 0
    check('solve_parallel general parallelism', abs(d1.x*1 - d1.y*1) < 1e-6)
else:
    check('solve_parallel general returned a root', False)

# Cubic and quadratic implementations agree on an elevated curve
q = QuadraticBezier((0,0),(50,100),(100,0))
tq = q.solve_parallel((1, 0))
tcu = q.to_cubic().solve_parallel((1, 0))
check('solve_parallel cubic/quad agree', tq is not None and tcu is not None and abs(tq - tcu) < 1e-9)

# 22. Shape/Layer lerp_function guard rejects incompatible
from typerig.core.objects.shape import Shape
s_a = Shape([Contour([Node(0,0,type='on'), Node(10,0,type='on'), Node(10,10,type='on')], closed=True)])
s_b = Shape([Contour([Node(0,0,type='on'), Node(10,0,type='on'), Node(10,10,type='curve')], closed=True)])
check('Shape.lerp_function rejects incompatible', s_a.lerp_function(s_b) is None)

print()
print('{} checks failed'.format(len(fails)) if fails else 'ALL CHECKS PASSED')
sys.exit(1 if fails else 0)
