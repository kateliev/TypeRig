# MODULE: TypeRig / Core / Algo / Outline Cleanup — tests
# -----------------------------------------------------------
# Stand-alone tests for outline_cleanup*.py — no FontLab needed.
#   cd Lib/typerig/core/algo && python -m pytest test_outline_cleanup.py
# (or just `python test_outline_cleanup.py` to run the asserts directly)
# Fixtures: fixtures/outline_cleanup/*.json (skia-pathops union output,
# regenerate with make_fixtures.py).
# -----------------------------------------------------------

from __future__ import annotations

import json, math, os, random, time

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.algo.outline_cleanup import clean, clean_single, locked_nodes, CleanOptions, IncompatibleMasters, contour_deviation
from typerig.core.algo.outline_cleanup_geom import Seg, area_moment, split, point_at, run_distance
from typerig.core.algo.outline_cleanup_fit_levien import fit_run, candidate_area, candidate_moment
from typerig.core.algo.outline_cleanup_fit_schneider import fit_schneider
from typerig.core.algo.outline_cleanup_rounding import ROUNDING_SLACK
from typerig.core.algo import outline_cleanup_trace

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'outline_cleanup')
EXACT = CleanOptions(round_ints=False)


# - Builders -----------------------------
def contour(spec, closed=True):
	'''spec: list of (x, y) on-curves or (x, y, type) tuples.'''
	nodes = []
	for item in spec:
		kind = item[2] if len(item) > 2 else 'on'
		nodes.append(Node(float(item[0]), float(item[1]), type=kind))
	return Contour(nodes, closed=closed)


def from_segments(segs):
	'''Closed contour from a list of 2/4-point tuples (end of i = start of i+1).'''
	nodes = []
	for p in segs:
		nodes.append(Node(p[0][0], p[0][1], type='on'))
		if len(p) == 4:
			nodes.append(Node(p[1][0], p[1][1], type='curve'))
			nodes.append(Node(p[2][0], p[2][1], type='curve'))
	return Contour(nodes, closed=True)


def circle_segments(n, r=500., cx=0., cy=0.):
	k = 4. / 3. * math.tan(math.pi / (2 * n))
	segs = []
	for i in range(n):
		a, b = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
		p0 = (cx + r * math.cos(a), cy + r * math.sin(a))
		p3 = (cx + r * math.cos(b), cy + r * math.sin(b))
		segs.append((p0, (p0[0] - k * r * math.sin(a), p0[1] + k * r * math.cos(a)),
					(p3[0] + k * r * math.sin(b), p3[1] - k * r * math.cos(b)), p3))
	return segs


def split_many(curve, ts):
	pieces, rest, done = [], curve, 0.
	for t in sorted(ts):
		a, rest = split(rest, (t - done) / (1. - done))
		pieces.append(a)
		done = t
	return pieces + [rest]


def load_fixture(name):
	with open(os.path.join(FIXTURES, name)) as f:
		data = json.load(f)
	return [contour([(n['x'], n['y'], n['type']) for n in c]) for c in data['contours']]


def fixtures():
	return sorted(f for f in os.listdir(FIXTURES) if f.endswith('.json'))


def on_curves(c):
	return [(n.x, n.y) for n in c.nodes if n.is_on]


def signature(contours):
	return [tuple(n.type for n in c.nodes) for c in contours]


def coords(contours):
	return [[(n.x, n.y, n.type) for n in c.nodes] for c in contours]


def deviation(a_list, b_list):
	return max(contour_deviation(a, b) for a, b in zip(a_list, b_list))


def warp(contours, sx=1.2, sy=.9, wobble=6.):
	'''Second master: non-uniform scale plus a smooth non-affine wobble.'''
	out = []
	for c in contours:
		nodes = [Node(n.x * sx + wobble * math.sin(n.y / 97.), n.y * sy + wobble * math.cos(n.x / 113.), type=n.type) for n in c.nodes]
		out.append(Contour(nodes, closed=True))
	return out


# - Fit kernels --------------------------
def test_area_closed_form_matches_quadrature():
	rnd = random.Random(7)
	for _ in range(500):
		th0, th1 = rnd.uniform(-3., 3.), rnd.uniform(-3., 3.)
		d0, d1 = rnd.uniform(0., 1.5), rnd.uniform(0., 1.5)
		c = ((0., 0.), (d0 * math.cos(th0), d0 * math.sin(th0)), (1. - d1 * math.cos(th1), d1 * math.sin(th1)), (1., 0.))
		g, mx = area_moment(c)
		assert abs(candidate_area(d0, d1, th0, th1) + g) < 1e-9
		assert abs(candidate_moment(d0, d1, th0, th1) - mx) < 1e-9


def test_fit_run_split_at_03_07():
	c = ((0., 0.), (100., 300.), (400., 350.), (500., 0.))
	pieces = split_many(c, [.3, .7])
	seg, err = fit_run([Seg(p, (i, i + 1)) for i, p in enumerate(pieces)], 1.)
	assert seg.is_cubic and err < 1e-6
	assert max(math.dist(a, b) for a, b in zip(seg.p, c)) < 1e-6


def test_schneider_recovers_cubic():
	c = ((0., 0.), (100., 300.), (400., 350.), (500., 0.))
	pts = [point_at(c, k / 40.) for k in range(41)]
	t0 = (100. / math.hypot(100., 300.), 300. / math.hypot(100., 300.))
	t1 = (100. / math.hypot(100., 350.), -350. / math.hypot(100., 350.))
	fit = fit_schneider(pts, t0, t1, 2., max_segments=1)
	assert fit is not None and len(fit) == 1
	assert run_distance([c], [fit[0].p]) < 2.
	assert fit_schneider(pts, t0, t1, .01, max_segments=1) is None


def test_schneider_recursive_splits():
	pts = [(x, 100. * math.sin(x / 40.)) for x in range(0, 400, 4)]
	fit = fit_schneider(pts, (1., 0.), (1., 0.), .5)
	assert fit is not None and len(fit) > 1


# - Simplification -----------------------
def test_split_cubic_in_contour_becomes_one():
	c = ((0., 0.), (100., 300.), (400., 350.), (500., 0.))
	src = from_segments(split_many(c, [.3, .7]) + [((500., 0.), (0., 0.))])
	out = clean_single([src], EXACT)[0]
	assert len(out.nodes) == 4	# on, curve, curve, on + closing line
	assert contour_deviation(src, out) < 1e-6


def test_split_cubic_ten_pieces():
	rnd = random.Random(3)
	c = ((0., 0.), (150., 100.), (350., 400.), (500., 500.))
	src = from_segments(split_many(c, [rnd.uniform(.03, .97) for _ in range(9)]) + [((500., 500.), (500., 0.)), ((500., 0.), (0., 0.))])
	out = clean_single([src], EXACT)[0]
	assert len(on_curves(out)) == 3
	assert contour_deviation(src, out) < 1e-3


def test_circle_eight_to_four():
	src = from_segments(circle_segments(8))
	out = clean_single([src])[0]
	assert len(on_curves(out)) == 4
	assert contour_deviation(src, out) <= 1.


def test_rectangle_extra_nodes():
	src = contour([(0, 0), (50, 0), (100, 0), (100, 50), (100, 100), (50, 100), (0, 100), (0, 50)])
	out = clean_single([src])[0]
	assert on_curves(out) == [(0., 0.), (100., 0.), (100., 100.), (0., 100.)]


# - Degeneracies -------------------------
def test_coincident_on_curves():
	src = contour([(0, 0), (100, 0), (100.2, 0.1), (100, 100), (0, 100)])
	out = clean_single([src], EXACT)[0]
	assert len(out.nodes) == 4


def test_zero_handle_and_flat_cubic():
	# bottom: cubic with a 0.3-unit handle; right: flat cubic with handles on the chord
	src = contour([(0, 0), (0.3, 0, 'curve'), (60, 40, 'curve'), (100, 0),
				(100, 30, 'curve'), (100, 70, 'curve'), (100, 100), (0, 100)])
	out = clean_single([src], EXACT)[0]
	segs = out.node_segments
	assert len(segs[0]) == 4 and (segs[0][1].x, segs[0][1].y) == (0., 0.)	# handle retracted
	assert len(segs[1]) == 2												# flat cubic -> line


def test_spike_removed():
	src = contour([(0, 0), (100, 0), (100, 50), (160, 50), (100, 50), (100, 100), (0, 100)])
	out = clean_single([src])[0]
	assert on_curves(out) == [(0., 0.), (100., 0.), (100., 100.), (0., 100.)]


def test_tiny_contour_dropped():
	big = contour([(0, 0), (100, 0), (100, 100), (0, 100)])
	tiny = contour([(200, 200), (202, 200), (202, 201), (200, 201)])	# area 2
	out = clean_single([big, tiny])
	assert len(out) == 1


# - Locks --------------------------------
def test_caller_lock_kept():
	src = from_segments(circle_segments(8))
	locked = src.nodes[3]	# 45 deg on-curve, removable otherwise
	locked.lib = {'locked': True}
	out = clean_single([src])[0]
	assert (round(locked.x), round(locked.y)) in on_curves(out)
	out = clean_single([src], EXACT)[0]
	assert (locked.x, locked.y) in on_curves(out)


def test_corner_between_curves_kept():
	segs = [((0., 0.), (100., 100.), (200., 150.), (300., 150.)),			# arrives horizontal
			((300., 150.), (300., 100.), (320., 50.), (400., 0.)),			# leaves vertical: 90 deg corner
			((400., 0.), (0., 0.))]
	src = from_segments(segs)
	out = clean_single([src], CleanOptions(fit_tol=50., round_ints=False))[0]
	assert (300., 150.) in on_curves(out)


# - Multi-master -------------------------
def test_node_removable_in_one_master_only():
	m0 = from_segments(circle_segments(8))
	m1 = Contour([Node(n.x * (1.25 if i == 3 else 1.), n.y * (1.25 if i == 3 else 1.), type=n.type) for i, n in enumerate(m0.nodes)], closed=True)
	out = clean([[m0], [m1]])
	assert len(on_curves(out[0][0])) == len(on_curves(out[1][0])) > 4
	assert signature(out[0]) == signature(out[1])


def test_incompatible_input_raises():
	a = contour([(0, 0), (100, 0), (100, 100), (0, 100)])
	b = contour([(0, 0), (100, 0), (100, 100)])
	try:
		clean([[a], [b]])
	except IncompatibleMasters:
		return
	assert False, 'IncompatibleMasters not raised'


# - Fixtures -----------------------------
def test_fixtures_within_tolerance_and_no_growth():
	for name in fixtures():
		src = load_fixture(name)
		out = clean_single(src)
		assert sum(len(c.nodes) for c in out) <= sum(len(c.nodes) for c in src), name
		assert deviation(src, out) <= EXACT.fit_tol + ROUNDING_SLACK, name


def test_fixtures_idempotent():
	for name in fixtures():
		once = clean_single(load_fixture(name))
		twice = clean_single(once)
		assert coords(once) == coords(twice), name


def test_fixtures_start_and_direction():
	for name in fixtures():
		src = load_fixture(name)
		out = clean_single(src)
		for a, b in zip(src, out):
			assert (round(a.nodes[0].x), round(a.nodes[0].y)) == (b.nodes[0].x, b.nodes[0].y), name
			assert (a.get_signed_area('sampled') > 0) == (b.get_signed_area('sampled') > 0), name


def test_fixtures_two_masters_compatible():
	for name in fixtures():
		m0 = load_fixture(name)
		m1 = warp(m0)
		out = clean([m0, m1])
		assert signature(out[0]) == signature(out[1]), name
		assert deviation(m1, out[1]) <= EXACT.fit_tol + ROUNDING_SLACK, name


# - Quadratic ----------------------------
def test_truetype_round_trip():
	from fontTools.cu2qu import curve_to_quadratic

	# TrueType 'o': explicit on-curves at the extrema, implied ones between
	nodes = []
	for seg in circle_segments(4, 300., 300., 300.):
		spline = curve_to_quadratic(seg, .2)
		nodes.append(Node(round(spline[0][0]), round(spline[0][1]), type='on'))
		nodes += [Node(round(q[0]), round(q[1]), type='off') for q in spline[1:-1]]
	m0 = Contour(nodes, closed=True)
	m1 = Contour([Node(n.x * 1.1 + 5, n.y, type=n.type) for n in m0.nodes], closed=True)
	explicit = [on_curves(m0), on_curves(m1)]

	opts = CleanOptions(output='quad')
	out = clean([[m0], [m1]], opts)
	assert signature(out[0]) == signature(out[1])
	assert 'curve' not in signature(out[0])[0]

	for src, res in ((m0, out[0][0]), (m1, out[1][0])):
		assert contour_deviation(src, res) <= opts.fit_tol + opts.quad_tol + ROUNDING_SLACK

	def midpoint(nodes, i):
		a, n, b = nodes[i - 1], nodes[i], nodes[(i + 1) % len(nodes)]
		return n.is_on and a.type == b.type == 'off' and 2 * n.x == a.x + b.x and 2 * n.y == a.y + b.y

	a, b = out[0][0].nodes, out[1][0].nodes
	for i in range(1, len(a)):
		if midpoint(a, i) and midpoint(b, i):
			assert (a[i].x, a[i].y) in explicit[0], 'explicit midpoint on-curve left at {}'.format(i)


# - Noise --------------------------------
def test_noisy_autotrace():
	rnd = random.Random(11)
	r, n = 400., 60
	segs = []
	pts = [(r * math.cos(2 * math.pi * i / n) + rnd.uniform(-.15, .15), r * math.sin(2 * math.pi * i / n) + rnd.uniform(-.15, .15)) for i in range(n)]
	for i in range(n):
		p0, p3 = pts[i], pts[(i + 1) % n]
		pa, pb = pts[i - 1], pts[(i + 2) % n]
		t0 = ((p3[0] - pa[0]) / 6., (p3[1] - pa[1]) / 6.)		# Catmull-Rom handles
		t1 = ((pb[0] - p0[0]) / 6., (pb[1] - p0[1]) / 6.)
		segs.append((p0, (p0[0] + t0[0], p0[1] + t0[1]), (p3[0] - t1[0], p3[1] - t1[1]), p3))
	src = from_segments(segs)
	opts = CleanOptions(round_ints=False)
	out = clean_single([src], opts)[0]
	assert len(out.nodes) < len(src.nodes) // 2
	assert contour_deviation(src, out) <= opts.fit_tol


# - Lifted guards -----------------------
def test_merge_may_not_add_extremum():
	from typerig.core.algo.outline_cleanup_simplify import _adds_extremum
	orig = [Seg(((0., 0.), (40., 30.), (80., 50.), (120., 60.))), Seg(((120., 60.), (160., 70.), (200., 74.), (240., 75.)))]
	assert not _adds_extremum(orig, Seg(((0., 0.), (80., 60.), (160., 74.5), (240., 75.))), 0.)	# monotone fit
	assert _adds_extremum(orig, Seg(((0., 0.), (80., 60.), (160., 90.), (240., 75.))), 0.)		# overshoot bump


def test_italic_extrema_locked():
	slant = math.tan(math.radians(12.))
	segs = [tuple((x + y * slant, y) for x, y in seg) for seg in circle_segments(8)]
	src = from_segments(segs)
	ons = on_curves(src)
	out = clean_single([src], CleanOptions(italic_angle=12., round_ints=False))[0]
	assert all(ons[k] in on_curves(out) for k in (0, 2, 4, 6))
	assert len(on_curves(out)) == 4


def test_options_for_upm():
	opts = CleanOptions().for_upm(2048)
	assert abs(opts.fit_tol - 2.048) < 1e-12 and abs(opts.min_contour_area - 4. * 2.048 ** 2) < 1e-9


def test_degeneracies_only_mode():
	src = from_segments(circle_segments(8))
	assert len(on_curves(clean_single([src], CleanOptions(simplify=False))[0])) == 8
	rect = contour([(0, 0), (50, 0), (100, 0), (100, 100), (0, 100)])
	assert len(clean_single([rect], CleanOptions(simplify=False))[0].nodes) == 4


def test_locked_nodes_report():
	src = from_segments(circle_segments(8))		# on-curves at node 0, 3, 6, ... (45 deg apart)
	locks = locked_nodes([[src]])
	assert locks == [[0, 6, 12, 18]]				# start + the 3 other extrema


def test_trace_stub():
	try:
		outline_cleanup_trace.trace(None)
	except NotImplementedError:
		return
	assert False


if __name__ == '__main__':
	import sys
	failures = 0
	for name, fn in sorted(globals().items()):
		if name.startswith('test_') and callable(fn):
			try:
				t = time.perf_counter()
				fn()
				print('PASS', name, '%.2fs' % (time.perf_counter() - t))
			except AssertionError as e:
				failures += 1
				print('FAIL', name, e)
			except Exception as e:
				failures += 1
				print('ERROR', name, repr(e))
	print('\n%d failure(s)' % failures)
	sys.exit(1 if failures else 0)
