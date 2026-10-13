# MODULE: TypeRig / Proxy / FontLab / GUI / Overlay Math
# -----------------------------------------------------------
# Pure, Qt-free helpers for on-canvas overlays (canvas_overlay.py
# and the tools built on it). Nothing here imports Qt or FontLab,
# so the unit tests run in plain CPython:
#
#   python overlay_math.py
#
# Contents:
#   - 2D affine algebra in Qt's QTransform convention
#   - drag model (delta from press point, axis lock, fine mode)
#   - handle shapes: extents, hit-testing, mask rects, picking
#   - contour -> path-op walker (move/line/cubic/quad/close)
#   - small runtime utilities (rate-limited logging, throttle)
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
import time
import traceback

__version__ = '0.1.0'

# - Affine ------------------------------
# An affine is the tuple (m11, m12, m21, m22, dx, dy), the same
# layout as QTransform's 2D part:
#	x' = m11*x + m21*y + dx
#	y' = m12*x + m22*y + dy
AFFINE_IDENTITY = (1., 0., 0., 1., 0., 0.)

def affine_apply(a, x, y):
	m11, m12, m21, m22, dx, dy = a
	return (m11*x + m21*y + dx, m12*x + m22*y + dy)

def affine_compose(a, b):
	'''Return the affine that applies a first, then b (Qt: a * b).'''
	a11, a12, a21, a22, adx, ady = a
	b11, b12, b21, b22, bdx, bdy = b
	return (a11*b11 + a12*b21,
			a11*b12 + a12*b22,
			a21*b11 + a22*b21,
			a21*b12 + a22*b22,
			adx*b11 + ady*b21 + bdx,
			adx*b12 + ady*b22 + bdy)

def affine_det(a):
	return a[0]*a[3] - a[1]*a[2]

def affine_is_invertible(a, eps=1e-12):
	return abs(affine_det(a)) > eps

def affine_invert(a):
	'''Inverse affine. Raises ValueError if singular.'''
	m11, m12, m21, m22, dx, dy = a
	det = affine_det(a)
	if abs(det) <= 1e-12:
		raise ValueError('affine_invert: singular transform')

	i11 = m22 / det
	i12 = -m12 / det
	i21 = -m21 / det
	i22 = m11 / det
	idx = -(dx*i11 + dy*i21)
	idy = -(dx*i12 + dy*i22)
	return (i11, i12, i21, i22, idx, idy)

def affine_from_points(src, dst):
	'''Solve the affine mapping three source points onto three targets.
	Args:
		src, dst: three (x, y) pairs each; src must not be collinear.
	Returns:
		affine tuple (m11, m12, m21, m22, dx, dy)
	'''
	(x0, y0), (x1, y1), (x2, y2) = src
	(u0, v0), (u1, v1), (u2, v2) = dst

	ax, ay = x1 - x0, y1 - y0
	bx, by = x2 - x0, y2 - y0
	det = ax*by - ay*bx

	if abs(det) <= 1e-12:
		raise ValueError('affine_from_points: source points are collinear')

	# - Linear part L with L*(a) = du, L*(b) = dv, columns as Qt rows
	du_x, du_y = u1 - u0, v1 - v0
	dv_x, dv_y = u2 - u0, v2 - v0

	m11 = (du_x*by - dv_x*ay) / det
	m21 = (dv_x*ax - du_x*bx) / det
	m12 = (du_y*by - dv_y*ay) / det
	m22 = (dv_y*ax - du_y*bx) / det
	dx = u0 - (m11*x0 + m21*y0)
	dy = v0 - (m12*x0 + m22*y0)
	return (m11, m12, m21, m22, dx, dy)

def affine_scale(a):
	'''Uniform scale estimate (sqrt |det|); equals |m11| for a pure scale/flip.'''
	return math.sqrt(abs(affine_det(a)))

def affine_close(a, b, tol=1e-9):
	return all(abs(p - q) <= tol for p, q in zip(a, b))

# - Drag model --------------------------
AXIS_X = 'x'
AXIS_Y = 'y'
AXIS_XY = 'xy'
AXIS_DOMINANT = 'dominant'		# lock to whichever axis moved most

FINE_FACTOR = 0.1

def constrain_delta(dx, dy, axis):
	'''Apply a drag axis constraint to a delta.'''
	if axis == AXIS_X: return (dx, 0.)
	if axis == AXIS_Y: return (0., dy)
	if axis == AXIS_DOMINANT: return (dx, 0.) if abs(dx) >= abs(dy) else (0., dy)
	return (dx, dy)

def drag_delta(press, cur, axis=AXIS_XY, fine=False, fine_factor=FINE_FACTOR):
	'''Delta from the press point (never accumulated, so no drift).
	Args:
		press, cur (x, y): press point and current point
		axis (str): 'x' | 'y' | 'xy' | 'dominant'
		fine (bool): scale the delta by fine_factor (Shift mode)
	'''
	dx, dy = constrain_delta(cur[0] - press[0], cur[1] - press[1], axis)
	if fine:
		dx *= fine_factor
		dy *= fine_factor
	return (dx, dy)

def drag_point(press, cur, axis=AXIS_XY, fine=False, fine_factor=FINE_FACTOR):
	'''Effective dragged point: press + constrained (and possibly fine) delta.'''
	dx, dy = drag_delta(press, cur, axis, fine, fine_factor)
	return (press[0] + dx, press[1] + dy)

def clamp(value, lo, hi):
	return lo if value < lo else hi if value > hi else value

def scale_from_drag(anchor, press, cur, eps=1e-9):
	'''Generic 1D scale from dragging a point away from/toward a fixed anchor.
	All arguments are scalars on one axis. Returns 1.0 if press is on the anchor.
	'''
	ref = press - anchor
	if abs(ref) < eps:
		return 1.
	return (cur - anchor) / ref

# - Handle shapes -----------------------
SHAPE_CIRCLE = 'circle'
SHAPE_SQUARE = 'square'
SHAPE_DIAMOND = 'diamond'
SHAPE_BAR_H = 'bar_h'		# wide, flat bar (lies along a horizontal edge)
SHAPE_BAR_V = 'bar_v'		# tall, thin bar (lies along a vertical edge)

HANDLE_SHAPES = (SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_DIAMOND, SHAPE_BAR_H, SHAPE_BAR_V)

BAR_LONG = 2.0		# bar half-length as multiple of radius
BAR_SHORT = 0.6		# bar half-thickness as multiple of radius

def shape_half_extents(shape, radius):
	'''(half_width, half_height) of a handle shape in screen px.'''
	if shape == SHAPE_BAR_H: return (radius*BAR_LONG, radius*BAR_SHORT)
	if shape == SHAPE_BAR_V: return (radius*BAR_SHORT, radius*BAR_LONG)
	return (radius, radius)

def hit_test_shape(shape, cx, cy, radius, px, py, tol=3.):
	'''True if (px, py) hits the handle drawn at (cx, cy), with tolerance in px.
	Shapes grow by tol on every side (circle: radius + tol, etc.).
	'''
	dx, dy = px - cx, py - cy

	if shape == SHAPE_CIRCLE:
		r = radius + tol
		return dx*dx + dy*dy <= r*r

	if shape == SHAPE_DIAMOND:
		# Diamond |x| + |y| <= r, grown by tol measured along its normal
		return abs(dx) + abs(dy) <= radius + tol*math.sqrt(2.)

	hw, hh = shape_half_extents(shape, radius)
	return abs(dx) <= hw + tol and abs(dy) <= hh + tol

def shape_hit_rect(shape, cx, cy, radius, tol=3., pad=0.):
	'''Axis-aligned rect (x0, y0, x1, y1) that covers the hit region plus pad.'''
	if shape == SHAPE_DIAMOND:
		e = radius + tol*math.sqrt(2.)
		hw = hh = e
	else:
		hw, hh = shape_half_extents(shape, radius)
		hw += tol
		hh += tol
	return (cx - hw - pad, cy - hh - pad, cx + hw + pad, cy + hh + pad)

def pick_handle(items, px, py, tol=3.):
	'''Pick the topmost hit among items.
	Args:
		items: ordered list of (shape, cx, cy, radius); later items are drawn on top.
	Returns:
		index into items, or -1.
	'''
	for i in range(len(items) - 1, -1, -1):
		shape, cx, cy, radius = items[i]
		if hit_test_shape(shape, cx, cy, radius, px, py, tol):
			return i
	return -1

# - Contour walker ----------------------
# Path ops in font units, ready to feed a QPainterPath (or anything else):
#	('move', (x, y)) ('line', (x, y)) ('cubic', c1, c2, p) ('quad', q, p) ('close',)
_OFF_CUBIC = 'curve'
_OFF_QUAD = 'off'

def _node_kind(node):
	'''Return 'on', 'curve' (cubic off) or 'off' (quadratic off) for a duck-typed node.'''
	kind = getattr(node, 'type', None)
	if kind in ('on', 'move', 'line'): return 'on'
	if kind in (_OFF_CUBIC, _OFF_QUAD): return kind
	is_on = getattr(node, 'is_on', None)
	if is_on is not None: return 'on' if is_on else _OFF_CUBIC
	return 'on'

def _quad_run_ops(start, offs, end):
	'''TrueType run: implied on-curves at off-curve midpoints.'''
	ops = []
	for i, q in enumerate(offs):
		if i < len(offs) - 1:
			nq = offs[i + 1]
			p = ((q[0] + nq[0])*.5, (q[1] + nq[1])*.5)
		else:
			p = end
		ops.append(('quad', q, p))
	return ops

def _segment_ops(start, offs, offs_kinds, end):
	if not offs:
		return [('line', end)]

	if len(offs) == 2 and offs_kinds[0] == _OFF_CUBIC:
		return [('cubic', offs[0], offs[1], end)]

	if all(k == _OFF_QUAD for k in offs_kinds):
		return _quad_run_ops(start, offs, end)

	if len(offs) == 1:
		# Lone cubic-tagged handle: degree-elevate the quadratic
		q = offs[0]
		c1 = (start[0] + 2./3.*(q[0] - start[0]), start[1] + 2./3.*(q[1] - start[1]))
		c2 = (end[0] + 2./3.*(q[0] - end[0]), end[1] + 2./3.*(q[1] - end[1]))
		return [('cubic', c1, c2, end)]

	# Malformed run (mixed or >2 cubic handles): treat as a TT run, never crash
	return _quad_run_ops(start, offs, end)

def contour_ops(nodes, closed=True):
	'''Walk one contour's nodes into path ops (font units).
	Args:
		nodes: sequence of objects with .x, .y and .type ('on' | 'curve' | 'off')
			or .is_on (core Node, flNode-like, simple stand-ins).
		closed (bool): close the contour.
	Returns:
		list of path ops; empty for fewer than two nodes.
	'''
	pts = [(float(n.x), float(n.y)) for n in nodes]
	kinds = [_node_kind(n) for n in nodes]
	count = len(pts)
	if count < 2: return []

	on_idx = [i for i, k in enumerate(kinds) if k == 'on']

	# - All off-curve closed TT contour: start on an implied midpoint
	if not on_idx:
		if not closed or count < 2: return []
		start = ((pts[-1][0] + pts[0][0])*.5, (pts[-1][1] + pts[0][1])*.5)
		ops = [('move', start)]
		ops.extend(_quad_run_ops(start, pts, start))
		ops.append(('close',))
		return ops

	# - Rotate so we start on an on-curve (closed); open contours keep order
	first = on_idx[0] if closed else 0
	order = list(range(first, count)) + list(range(0, first))
	pts = [pts[i] for i in order]
	kinds = [kinds[i] for i in order]

	if not closed:
		# Leading off-curves on an open contour are dangling handles: drop them
		while kinds and kinds[0] != 'on':
			pts.pop(0); kinds.pop(0)
		if not pts: return []

	ops = [('move', pts[0])]
	start = pts[0]
	offs, offs_kinds = [], []

	walk = list(range(1, len(pts)))
	if closed: walk.append(0)

	for i in walk:
		if kinds[i] == 'on':
			ops.extend(_segment_ops(start, offs, offs_kinds, pts[i]))
			start = pts[i]
			offs, offs_kinds = [], []
		else:
			offs.append(pts[i])
			offs_kinds.append(kinds[i])

	if closed:
		ops.append(('close',))
	return ops

def iter_core_contours(obj):
	'''Yield core Contour objects from a core Layer, Shape, Contour or list of those.'''
	if obj is None: return
	if isinstance(obj, (list, tuple)):
		for item in obj:
			for c in iter_core_contours(item): yield c
		return
	if hasattr(obj, 'contours') and not hasattr(obj, 'closed'):
		for c in obj.contours: yield c
		return
	yield obj

def layer_ops(obj):
	'''Path ops for every contour in a core Layer/Shape/Contour (or list).'''
	ops = []
	for contour in iter_core_contours(obj):
		nodes = list(getattr(contour, 'nodes', contour))
		ops.extend(contour_ops(nodes, bool(getattr(contour, 'closed', True))))
	return ops

def ops_bounds(ops):
	'''Control-point bounds (xmin, ymin, xmax, ymax) of path ops, or None.'''
	xs, ys = [], []
	for op in ops:
		for p in op[1:]:
			xs.append(p[0]); ys.append(p[1])
	if not xs: return None
	return (min(xs), min(ys), max(xs), max(ys))

# - Runtime utilities -------------------
class LogOnce(object):
	'''Rate-limited console reporter: each distinct message prints at most once
	per interval seconds; repeats are counted and summarised on the next print.
	'''
	__slots__ = ('interval', 'clock', 'printer', '_last', '_muted')

	def __init__(self, interval=10., clock=None, printer=None):
		self.interval = interval
		self.clock = clock or time.time
		self.printer = printer or print
		self._last = {}
		self._muted = {}

	def __call__(self, key, text=None):
		now = self.clock()
		last = self._last.get(key)

		if last is not None and now - last < self.interval:
			self._muted[key] = self._muted.get(key, 0) + 1
			return False

		muted = self._muted.pop(key, 0)
		self._last[key] = now
		suffix = ' (+{} repeats suppressed)'.format(muted) if muted else ''
		self.printer('{}{}'.format(text if text is not None else key, suffix))
		return True

	def exception(self, where):
		'''Report the active exception, keyed by location and message.'''
		tb = traceback.format_exc()
		lines = tb.strip().splitlines()
		key = '{}: {}'.format(where, lines[-1] if lines else '?')
		return self(key, 'TypeRig Overlay ERROR in {}:\n{}'.format(where, tb))

class Throttle(object):
	'''Gate expensive work to at most one run per interval seconds.'''
	__slots__ = ('interval', 'clock', '_last')

	def __init__(self, interval=0.033, clock=None):
		self.interval = interval
		self.clock = clock or time.time
		self._last = None

	def ready(self):
		now = self.clock()
		if self._last is None or now - self._last >= self.interval:
			self._last = now
			return True
		return False

	def reset(self):
		self._last = None

def round_sig(values, digits=3):
	'''Round a sequence of floats into a hashable tuple (for view signatures).'''
	return tuple(round(float(v), digits) for v in values)

# - Tests -------------------------------
def _approx(a, b, tol=1e-9):
	return abs(a - b) <= tol

def _approx_pt(p, q, tol=1e-9):
	return _approx(p[0], q[0], tol) and _approx(p[1], q[1], tol)

def _test_affine():
	# Verified FontLab sample: font -> canvas, Y flipped
	f2c = (0.540625, 0., 0., -0.540625, 129.75, 700.65)
	src = [(0., 0.), (1000., 0.), (0., 1000.)]
	dst = [affine_apply(f2c, *p) for p in src]
	solved = affine_from_points(src, dst)
	assert affine_close(solved, f2c, 1e-9), solved

	# General (sheared, rotated) affine round trip
	a = (1.3, 0.2, -0.4, 0.9, 12., -7.)
	solved = affine_from_points([(3., 4.), (-10., 2.), (7., -5.)], [affine_apply(a, *p) for p in [(3., 4.), (-10., 2.), (7., -5.)]])
	assert affine_close(solved, a, 1e-9)

	# Compose order: a first, then b
	b = (1.088, 0., 0., 1.088, 404.6, 22.7)
	ab = affine_compose(f2c, b)
	for p in [(0., 0.), (500., 0.), (0., 500.), (123., -45.)]:
		two_step = affine_apply(b, *affine_apply(f2c, *p))
		assert _approx_pt(affine_apply(ab, *p), two_step, 1e-9)

	# Inverse
	inv = affine_invert(ab)
	for p in [(0., 0.), (100., 0.), (-7., 33.)]:
		assert _approx_pt(affine_apply(inv, *affine_apply(ab, *p)), p, 1e-9)
	assert affine_close(affine_compose(ab, inv), AFFINE_IDENTITY, 1e-9)

	# Scale estimate
	assert _approx(affine_scale(ab), 0.540625*1.088, 1e-12)

	# Errors
	for bad in [lambda: affine_from_points([(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 0), (0, 1)]),
				lambda: affine_invert((1., 2., 2., 4., 0., 0.))]:
		try:
			bad(); assert False, 'expected ValueError'
		except ValueError:
			pass
	assert not affine_is_invertible((0., 0., 0., 0., 1., 1.))
	print('  affine: ok')

def _test_drag():
	press = (100., 200.)

	# Delta from press: the intermediate path does not matter (no accumulation)
	path = [(103., 199.), (180., 260.), (90., 150.), (150., 230.)]
	for cur in path: d = drag_delta(press, cur)
	assert d == (50., 30.)
	# Re-evaluating the same point gives the same answer regardless of history
	assert drag_delta(press, (150., 230.)) == d

	assert drag_delta(press, (150., 230.), AXIS_X) == (50., 0.)
	assert drag_delta(press, (150., 230.), AXIS_Y) == (0., 30.)
	assert drag_delta(press, (150., 230.), AXIS_DOMINANT) == (50., 0.)
	assert drag_delta(press, (110., 260.), AXIS_DOMINANT) == (0., 60.)

	fd = drag_delta(press, (150., 230.), fine=True)
	assert _approx_pt(fd, (5., 3.))
	assert _approx_pt(drag_point(press, (150., 230.), AXIS_X, fine=True), (105., 200.))

	# Verified FontLab round trip: px delta -> font delta through the full chain
	f2v = affine_compose((0.540625, 0., 0., -0.540625, 129.75, 700.65), (1.088, 0., 0., 1.088, 404.6, 22.7))
	v2f = affine_invert(f2v)
	p0 = affine_apply(v2f, 500., 400.)
	p1 = affine_apply(v2f, 500. - 263., 400. + 303.)
	dfx, dfy = drag_delta(p0, p1)
	# (the probe's 1.088 is rounded, hence the 0.5 unit tolerance)
	assert _approx(dfx, -447.2, 0.5) and _approx(dfy, -515.3, 0.5), (dfx, dfy)

	# 100 font units right/up -> view px -> back is 100, signs preserved
	v0 = affine_apply(f2v, 0., 0.)
	v1 = affine_apply(f2v, 100., 100.)
	assert v1[0] > v0[0] and v1[1] < v0[1]	# right on screen, up on screen
	b = affine_apply(v2f, *v1)
	assert _approx_pt(b, (100., 100.), 1e-9)

	assert clamp(5., 0., 3.) == 3. and clamp(-1., 0., 3.) == 0. and clamp(2., 0., 3.) == 2.
	assert scale_from_drag(0., 100., 150.) == 1.5
	assert scale_from_drag(50., 50., 80.) == 1.
	assert scale_from_drag(100., 0., -50.) == 1.5	# anchor on the right
	print('  drag: ok')

def _test_hit():
	r = 6.
	# Circle: inside, on tolerance rim, outside
	assert hit_test_shape(SHAPE_CIRCLE, 0, 0, r, 6., 0.)
	assert hit_test_shape(SHAPE_CIRCLE, 0, 0, r, 9., 0.)
	assert not hit_test_shape(SHAPE_CIRCLE, 0, 0, r, 9.1, 0.)
	assert not hit_test_shape(SHAPE_CIRCLE, 0, 0, r, 7., 7.)		# corner of bbox

	# Square: corners count
	assert hit_test_shape(SHAPE_SQUARE, 0, 0, r, 8.9, 8.9)
	assert not hit_test_shape(SHAPE_SQUARE, 0, 0, r, 9.1, 0.)

	# Diamond: axis tips are farther than diagonal corners
	tip = r + 3.*math.sqrt(2.)
	assert hit_test_shape(SHAPE_DIAMOND, 0, 0, r, tip - 0.01, 0.)
	assert not hit_test_shape(SHAPE_DIAMOND, 0, 0, r, tip + 0.01, 0.)
	assert not hit_test_shape(SHAPE_DIAMOND, 0, 0, r, 7., 7.)

	# Bars: anisotropic
	assert hit_test_shape(SHAPE_BAR_H, 0, 0, r, r*BAR_LONG + 2.9, 0.)
	assert not hit_test_shape(SHAPE_BAR_H, 0, 0, r, 0., r*BAR_SHORT + 3.1)
	assert hit_test_shape(SHAPE_BAR_V, 0, 0, r, 0., r*BAR_LONG + 2.9)
	assert not hit_test_shape(SHAPE_BAR_V, 0, 0, r, r*BAR_SHORT + 3.1, 0.)

	# Hit rects cover every hit and include the padding
	for shape in HANDLE_SHAPES:
		x0, y0, x1, y1 = shape_hit_rect(shape, 10., 20., r, 3., 4.)
		for ang in range(0, 360, 5):
			for rad in [0., 3., 6., 9., 12., 15.]:
				px = 10. + rad*math.cos(math.radians(ang))
				py = 20. + rad*math.sin(math.radians(ang))
				if hit_test_shape(shape, 10., 20., r, px, py, 3.):
					assert x0 + 4. <= px <= x1 - 4. and y0 + 4. <= py <= y1 - 4., (shape, px, py)

	# Topmost wins
	items = [(SHAPE_CIRCLE, 0., 0., r), (SHAPE_SQUARE, 4., 0., r), (SHAPE_CIRCLE, 100., 0., r)]
	assert pick_handle(items, 2., 0.) == 1
	assert pick_handle(items, -7., 0.) == 0
	assert pick_handle(items, 100., 0.) == 2
	assert pick_handle(items, 50., 50.) == -1
	assert pick_handle([], 0., 0.) == -1
	print('  hit: ok')

class _N(object):
	__slots__ = ('x', 'y', 'type')
	def __init__(self, x, y, t='on'):
		self.x, self.y, self.type = x, y, t

def _test_contour_ops():
	# Rectangle
	rect = [_N(0, 0), _N(100, 0), _N(100, 50), _N(0, 50)]
	ops = contour_ops(rect)
	assert [o[0] for o in ops] == ['move', 'line', 'line', 'line', 'line', 'close']
	assert ops[-2][1] == (0., 0.)

	# Cubic contour starting on an off-curve (rotation)
	base = [_N(0, 0), _N(100, 0), _N(100, 55, 'curve'), _N(55, 100, 'curve'), _N(0, 100)]
	nodes = base[2:] + base[:2]		# off-curve first
	ops = contour_ops(nodes)
	assert ops[0] == ('move', (0., 100.)), ops[0]
	kinds = [o[0] for o in ops]
	assert kinds == ['move', 'line', 'line', 'cubic', 'close'], kinds
	assert ops[3] == ('cubic', (100., 55.), (55., 100.), (0., 100.)), ops[3]

	# TT run with implied on-curve
	tt = [_N(0, 0), _N(50, 100, 'off'), _N(150, 100, 'off'), _N(200, 0)]
	ops = contour_ops(tt)
	assert [o[0] for o in ops] == ['move', 'quad', 'quad', 'line', 'close']
	assert ops[1] == ('quad', (50., 100.), (100., 100.))
	assert ops[2] == ('quad', (150., 100.), (200., 0.))

	# All-off TT circle
	circ = [_N(0, 100, 'off'), _N(100, 100, 'off'), _N(100, 0, 'off'), _N(0, 0, 'off')]
	ops = contour_ops(circ)
	assert ops[0] == ('move', (0., 50.)) and len(ops) == 6 and ops[-2][2] == (0., 50.)

	# Open contour: no close, no wraparound segment, dangling lead handle dropped
	op = [_N(-5, -5, 'curve'), _N(0, 0), _N(100, 0)]
	ops = contour_ops(op, closed=False)
	assert ops == [('move', (0., 0.)), ('line', (100., 0.))]

	# Robustness: empty, single node, malformed run
	assert contour_ops([]) == []
	assert contour_ops([_N(1, 2)]) == []
	bad = [_N(0, 0), _N(10, 10, 'curve'), _N(20, 10, 'curve'), _N(30, 10, 'curve'), _N(40, 0)]
	assert contour_ops(bad)[0][0] == 'move'

	# is_on duck typing
	class _M(object):
		def __init__(self, x, y, on): self.x, self.y, self.is_on = x, y, on
	ops = contour_ops([_M(0, 0, True), _M(10, 0, True)])
	assert [o[0] for o in ops] == ['move', 'line', 'line', 'close']

	assert ops_bounds(contour_ops(rect)) == (0., 0., 100., 50.)
	assert ops_bounds([]) is None
	print('  contour ops: ok')

def _test_core_layer_ops():
	try:
		from typerig.core.objects.node import Node
		from typerig.core.objects.contour import Contour
		from typerig.core.objects.shape import Shape
		from typerig.core.objects.layer import Layer
	except ImportError:
		print('  core layer ops: skipped (typerig.core not on path)')
		return

	c = Contour([Node(0, 0), Node(0, 100), Node(100, 100), Node(100, 0)], closed=True)
	layer = Layer([Shape([c])])
	ops = layer_ops(layer)
	assert [o[0] for o in ops] == ['move', 'line', 'line', 'line', 'line', 'close'], ops
	assert ops_bounds(ops) == (0., 0., 100., 100.)
	assert layer_ops(c) == ops
	print('  core layer ops: ok')

def _test_runtime():
	t = [0.]
	out = []
	log = LogOnce(interval=10., clock=lambda: t[0], printer=out.append)
	assert log('a') and not log('a') and not log('a')
	assert log('b')
	t[0] = 11.
	assert log('a')
	assert out[-1] == 'a (+2 repeats suppressed)', out

	try:
		raise RuntimeError('boom')
	except RuntimeError:
		assert log.exception('paintEvent')
		assert not log.exception('paintEvent')
	assert 'boom' in out[-1]

	th = Throttle(0.033, clock=lambda: t[0])
	assert th.ready() and not th.ready()
	t[0] += 0.034
	assert th.ready()

	assert round_sig([1.23456, 2.]) == (1.235, 2.)
	print('  runtime: ok')

if __name__ == '__main__':
	print('overlay_math tests:')
	_test_affine()
	_test_drag()
	_test_hit()
	_test_contour_ops()
	_test_core_layer_ops()
	_test_runtime()
	print('overlay_math: ALL TESTS PASSED')
