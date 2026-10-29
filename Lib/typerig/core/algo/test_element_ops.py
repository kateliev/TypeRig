# MODULE: TypeRig / Core / Algo / Element Ops — pure-math tests
# -----------------------------------------------------------
# Stand-alone tests for element_ops.py — no FontLab, no Qt needed.
#   cd Lib/typerig/core/algo && python -m pytest test_element_ops.py
# (or just `python test_element_ops.py` to run the asserts directly)
# -----------------------------------------------------------

from __future__ import absolute_import, division

try:
	from typerig.core.algo import element_ops as eo		# installed / on sys.path
except Exception:
	import os, sys
	sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
	import element_ops as eo


def _close(a, b, tol=1e-6):
	return all(abs(x - y) <= tol for x, y in zip(a, b))

def _square(x0, y0, x1, y1):
	return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# - Affine ---------------------------------------------------------------
def test_compose_order_scale_then_translate():
	a = eo.compose((2., 0., 0., 2., 0., 0.), eo.translate(10, 0))
	assert _close(eo.map_point(a, 1, 1), (12, 2))

def test_invert_roundtrip():
	a = eo.compose(eo.compose((1.5, .3, -.2, .8, 0., 0.), eo.translate(40, -7)), eo.scale_about(-1, 1, 100, 0))
	ai = eo.invert(a)
	assert eo.is_identity(eo.compose(a, ai))
	assert _close(eo.map_point(ai, *eo.map_point(a, 13, 17)), (13, 17))

def test_invert_singular():
	assert eo.invert((1., 0., 0., 0., 5., 5.)) is None

def test_move_between_shapes_keeps_global_position():
	# Contour local to src; re-expressed in dst space must land at the same global point
	src = eo.compose((1., 0., 0., 1., 0., 0.), eo.translate(100, 50))
	dst = eo.compose((2., 0., 0., 2., 0., 0.), eo.translate(-30, 10))
	move = eo.compose(src, eo.invert(dst))
	local_dst = eo.map_point(move, 7, 9)
	assert _close(eo.map_point(dst, *local_dst), eo.map_point(src, 7, 9))

def test_mirror_about_center():
	flip = eo.scale_about(-1, 1, 50, 0)
	assert _close(eo.map_point(flip, 0, 3), (100, 3))

def test_map_bounds_rotated():
	rot90 = (0., 1., -1., 0., 0., 0.)
	assert _close(eo.map_bounds(rot90, (0, 0, 10, 20)), (-20, 0, 0, 10))


# - Bounds ---------------------------------------------------------------
def test_align_left_and_keep_y():
	shifts = eo.align_shifts([(10, 0, 20, 5), (30, 7, 50, 9)], (0, 0, 100, 100), 'L', None)
	assert shifts == [(-10, 0.), (-30, 0.)]

def test_align_centers():
	shifts = eo.align_shifts([(0, 0, 10, 10)], (0, 0, 100, 50), 'C', 'E')
	assert _close(shifts[0], (45, 20))

def test_distribute_equal_gaps():
	boxes = [(0, 0, 10, 1), (12, 0, 22, 1), (90, 0, 100, 1), (60, 0, 80, 1)]
	shifts = eo.distribute_shifts(boxes)
	moved = sorted((b[0] + s[0], b[2] + s[0]) for b, s in zip(boxes, shifts))
	gaps = [moved[i + 1][0] - moved[i][1] for i in range(len(moved) - 1)]
	assert _close(gaps, [gaps[0]]*3)
	assert moved[0][0] == 0 and moved[-1][1] == 100

def test_distribute_two_items_noop():
	assert eo.distribute_shifts([(0, 0, 1, 1), (5, 0, 6, 1)], True) == [(0., 0.), (0., 0.)]


# - Z-order --------------------------------------------------------------
def test_up_one_step():
	assert eo.reorder_up(4, [1]) == [0, 2, 1, 3]

def test_up_block_stays_together_at_top():
	assert eo.reorder_up(4, [2, 3]) == [0, 1, 2, 3]
	assert eo.reorder_up(4, [1, 2]) == [0, 3, 1, 2]

def test_down_one_step():
	assert eo.reorder_down(4, [2]) == [0, 2, 1, 3]

def test_front_back():
	assert eo.reorder_front(5, [0, 2]) == [1, 3, 4, 0, 2]
	assert eo.reorder_back(5, [3, 1]) == [1, 3, 0, 2, 4]

def test_reverse_selected_only():
	assert eo.reorder_reverse(5, [0, 2, 4]) == [4, 1, 2, 3, 0]


# - Islands --------------------------------------------------------------
def test_point_in_polygon():
	assert eo.point_in_polygon(5, 5, _square(0, 0, 10, 10))
	assert not eo.point_in_polygon(15, 5, _square(0, 0, 10, 10))

def test_islands_letter_B_like():
	outer = _square(0, 0, 100, 200)
	hole_a = _square(20, 20, 80, 90)
	hole_b = _square(20, 110, 80, 180)
	dot = _square(200, 0, 220, 20)
	assert eo.group_islands([hole_a, outer, dot, hole_b]) == [[1, 0, 3], [2]]

def test_islands_shape_in_counter_is_new_island():
	ring_outer = _square(0, 0, 100, 100)
	ring_hole = _square(10, 10, 90, 90)
	inner = _square(40, 40, 60, 60)
	assert eo.group_islands([ring_outer, ring_hole, inner]) == [[0, 1], [2]]

def test_islands_separate():
	assert eo.group_islands([_square(0, 0, 1, 1), _square(5, 5, 6, 6)]) == [[0], [1]]


if __name__ == '__main__':
	tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_')]
	for name, fn in tests:
		fn()
	print('{}/{} passed'.format(len(tests), len(tests)))
