# MODULE: TypeRig / Core / Algo / Element Ops
# -----------------------------------------------------------
# Pure math behind element (shape) management: the parts of
# merge / split / arrange / align that do not need FontLab.
#
#   Affine transforms as 6-tuples (m11, m12, m21, m22, dx, dy)
#   in Qt's row-vector convention: p' = p * A, so compose(A, B)
#   means "apply A, then B" — the same order QTransform uses.
#
#   compose, invert, translate, scale_about, map_point, map_bounds
#   union_bounds, align_shifts, distribute_shifts	(bounds math)
#   reorder_up/down/front/back/reverse				(z-order permutations)
#   point_in_polygon, polygon_area, group_islands	(outer + counters)
#
# No FontLab, no Qt. The FL glue lives in proxy/fl/actions/element.py
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

__version__ = '1.0.0'

# - Affine -------------------------------------------------
IDENTITY = (1., 0., 0., 1., 0., 0.)

def compose(a, b):
	'''Return the affine that applies a, then b (row-vector convention, as QTransform a * b).'''
	a11, a12, a21, a22, adx, ady = a
	b11, b12, b21, b22, bdx, bdy = b

	return (a11*b11 + a12*b21,
			a11*b12 + a12*b22,
			a21*b11 + a22*b21,
			a21*b12 + a22*b22,
			adx*b11 + ady*b21 + bdx,
			adx*b12 + ady*b22 + bdy)

def invert(a, eps=1e-12):
	'''Inverse affine or None when singular.'''
	m11, m12, m21, m22, dx, dy = a
	det = m11*m22 - m12*m21

	if abs(det) < eps: return None

	return (m22/det, -m12/det, -m21/det, m11/det,
			(m21*dy - m22*dx)/det,
			(m12*dx - m11*dy)/det)

def is_identity(a, tol=1e-9):
	return all(abs(v - i) <= tol for v, i in zip(a, IDENTITY))

def translate(dx, dy):
	return (1., 0., 0., 1., float(dx), float(dy))

def scale_about(sx, sy, cx, cy):
	'''Scale (or mirror with -1) about point (cx, cy).'''
	return compose(compose(translate(-cx, -cy), (float(sx), 0., 0., float(sy), 0., 0.)), translate(cx, cy))

def map_point(a, x, y):
	m11, m12, m21, m22, dx, dy = a
	return (x*m11 + y*m21 + dx, x*m12 + y*m22 + dy)

def map_bounds(a, bounds):
	'''Axis aligned bounds (xmin, ymin, xmax, ymax) of the mapped rectangle.'''
	x0, y0, x1, y1 = bounds
	pts = [map_point(a, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
	xs, ys = [p[0] for p in pts], [p[1] for p in pts]
	return (min(xs), min(ys), max(xs), max(ys))

# - Bounds ------------------------------------------------
def union_bounds(bounds_list):
	bounds_list = [b for b in bounds_list if b is not None]
	if not len(bounds_list): return None

	return (min(b[0] for b in bounds_list), min(b[1] for b in bounds_list),
			max(b[2] for b in bounds_list), max(b[3] for b in bounds_list))

def bounds_anchor(bounds, key):
	'''Coordinate of an alignment key on bounds: L, C, R (x) or B, E, T (y).'''
	x0, y0, x1, y1 = bounds
	return {'L': x0, 'C': (x0 + x1)/2., 'R': x1,
			'B': y0, 'E': (y0 + y1)/2., 'T': y1}[key]

def align_shifts(bounds_list, target, align_x=None, align_y=None):
	'''Shifts (dx, dy) that put every bounds' align key onto the target bounds' key.
	Args:
		bounds_list (list(tuple)): (xmin, ymin, xmax, ymax) per item
		target (tuple): target bounds
		align_x (str or None): L, C, R or None to keep X
		align_y (str or None): B, E, T or None to keep Y
	'''
	shifts = []

	for bounds in bounds_list:
		dx = bounds_anchor(target, align_x) - bounds_anchor(bounds, align_x) if align_x else 0.
		dy = bounds_anchor(target, align_y) - bounds_anchor(bounds, align_y) if align_y else 0.
		shifts.append((dx, dy))

	return shifts

def distribute_shifts(bounds_list, vertical=False):
	'''Shifts (dx, dy) giving equal gaps between items. The two outermost items stay put.'''
	count = len(bounds_list)
	shifts = [(0., 0.)]*count
	if count < 3: return shifts

	lo, hi = (1, 3) if vertical else (0, 2)
	order = sorted(range(count), key=lambda i: bounds_list[i][lo])
	span_lo = bounds_list[order[0]][lo]
	span_hi = max(b[hi] for b in bounds_list)
	sizes = [bounds_list[i][hi] - bounds_list[i][lo] for i in order]
	gap = (span_hi - span_lo - sum(sizes))/(count - 1)

	position = span_lo
	for i, size in zip(order, sizes):
		delta = position - bounds_list[i][lo]
		shifts[i] = (0., delta) if vertical else (delta, 0.)
		position += size + gap

	return shifts

# - Z-order ----------------------------------------------
# Stack lists run back to front (index 0 = bottom), as flLayer.shapes.
# Each function returns the new order as a list of old indices.

def reorder_up(count, selected):
	order = list(range(count))
	selected = set(selected)

	for pos in range(count - 2, -1, -1):
		if order[pos] in selected and order[pos + 1] not in selected:
			order[pos], order[pos + 1] = order[pos + 1], order[pos]

	return order

def reorder_down(count, selected):
	order = list(range(count))
	selected = set(selected)

	for pos in range(1, count):
		if order[pos] in selected and order[pos - 1] not in selected:
			order[pos], order[pos - 1] = order[pos - 1], order[pos]

	return order

def reorder_front(count, selected):
	selected = set(selected)
	return [i for i in range(count) if i not in selected] + [i for i in range(count) if i in selected]

def reorder_back(count, selected):
	selected = set(selected)
	return [i for i in range(count) if i in selected] + [i for i in range(count) if i not in selected]

def reorder_reverse(count, selected):
	'''Reverse the stacking of the selected items among their own slots.'''
	selected = sorted(set(selected))
	order = list(range(count))

	for slot, index in zip(selected, reversed(selected)):
		order[slot] = index

	return order

# - Islands ----------------------------------------------
def point_in_polygon(x, y, polygon):
	'''Even-odd ray cast. Polygon is a list of (x, y).'''
	inside = False
	count = len(polygon)

	for i in range(count):
		x0, y0 = polygon[i]
		x1, y1 = polygon[(i + 1) % count]

		if (y0 > y) != (y1 > y):
			cross_x = x0 + (y - y0)*(x1 - x0)/(y1 - y0)
			if x < cross_x: inside = not inside

	return inside

def polygon_area(polygon):
	'''Absolute area (shoelace).'''
	count = len(polygon)
	twice = sum(polygon[i][0]*polygon[(i + 1) % count][1] - polygon[(i + 1) % count][0]*polygon[i][1] for i in range(count))
	return abs(twice)/2.

def _polygon_bounds(polygon):
	xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
	return (min(xs), min(ys), max(xs), max(ys))

def group_islands(polygons, probes=None):
	'''Group contours into islands: an outer contour together with its counters.
	Nesting depth decides the role: even depth = outer, odd depth = counter of the
	smallest contour around it. A shape inside a counter starts a new island.

	Args:
		polygons (list(list(tuple))): contour point lists (control polygons are fine)
		probes (list(tuple) or None): one point per contour used for the inside test;
			defaults to each polygon's first point
	Returns:
		list(list(int)): islands as contour indices, outer first, in input order of outers
	'''
	count = len(polygons)
	if probes is None: probes = [polygon[0] for polygon in polygons]

	bounds = [_polygon_bounds(polygon) for polygon in polygons]
	areas = [polygon_area(polygon) for polygon in polygons]

	def encloses(outer, inner):
		ob, ib = bounds[outer], bounds[inner]
		if not (ob[0] <= ib[0] and ob[1] <= ib[1] and ob[2] >= ib[2] and ob[3] >= ib[3]): return False
		if areas[outer] <= areas[inner]: return False
		return point_in_polygon(probes[inner][0], probes[inner][1], polygons[outer])

	containers = [[j for j in range(count) if j != i and encloses(j, i)] for i in range(count)]
	depth = [len(c) for c in containers]

	islands, owner = [], {}

	for i in range(count):
		if depth[i] % 2 == 0:
			owner[i] = len(islands)
			islands.append([i])

	for i in range(count):
		if depth[i] % 2 == 1:
			parents = [j for j in containers[i] if j in owner]

			if len(parents): # Overlapping, not nested, contours can leave a counter without an outer
				islands[owner[min(parents, key=lambda j: areas[j])]].append(i)
			else:
				islands.append([i])

	return islands
