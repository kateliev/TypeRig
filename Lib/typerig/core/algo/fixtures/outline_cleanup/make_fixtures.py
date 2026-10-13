# Regenerates the remove-overlap fixtures for test_outline_cleanup.py.
# Dev tool only: needs skia-pathops (pip install skia-pathops).
# Glyphs are built from overlapping strokes and unioned, so the JSON
# holds genuine remove-overlap output (split curves, junction nodes).
#   python make_fixtures.py

import json, math, os

import pathops
from fontTools.pens.recordingPen import RecordingPen

HERE = os.path.dirname(os.path.abspath(__file__))
K = 0.5522847498


def poly(pen, pts):
	pen.moveTo(pts[0])
	for p in pts[1:]:
		pen.lineTo(p)
	pen.closePath()


def stroke(pen, a, b, w):
	dx, dy = b[0] - a[0], b[1] - a[1]
	l = math.hypot(dx, dy)
	nx, ny = -dy / l * w / 2, dx / l * w / 2
	poly(pen, [(a[0] + nx, a[1] + ny), (a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny)])


def ellipse(pen, cx, cy, rx, ry, reverse=False):
	pts = [(cx + rx, cy), (cx, cy + ry), (cx - rx, cy), (cx, cy - ry)]
	if reverse:
		pts = pts[::-1]
	pen.moveTo(pts[0])
	for i in range(4):
		p0, p3 = pts[i], pts[(i + 1) % 4]
		# tangent handles for an axis-aligned ellipse
		if p0[1] == cy:
			c1 = (p0[0], p0[1] + (K * ry if (p3[1] > cy) else -K * ry))
		else:
			c1 = (p0[0] + (K * rx if (p3[0] > cx) else -K * rx), p0[1])
		if p3[1] == cy:
			c2 = (p3[0], p3[1] + (K * ry if (p0[1] > cy) else -K * ry))
		else:
			c2 = (p3[0] + (K * rx if (p0[0] > cx) else -K * rx), p3[1])
		pen.curveTo(c1, c2, p3)
	pen.closePath()


def arc_stroke(pen, cx, cy, r, w, a0, a1):
	'''Thick circular arc from angle a0 to a1 (degrees) as one closed contour.'''
	def arc(radius, s, e):
		n = max(1, int(math.ceil(abs(e - s) / 90.)))
		pts = []
		for i in range(n):
			t0 = math.radians(s + (e - s) * i / n)
			t1 = math.radians(s + (e - s) * (i + 1) / n)
			k = 4. / 3. * math.tan((t1 - t0) / 4.)
			p0 = (cx + radius * math.cos(t0), cy + radius * math.sin(t0))
			p3 = (cx + radius * math.cos(t1), cy + radius * math.sin(t1))
			c1 = (p0[0] - k * radius * math.sin(t0), p0[1] + k * radius * math.cos(t0))
			c2 = (p3[0] + k * radius * math.sin(t1), p3[1] - k * radius * math.cos(t1))
			pts.append((c1, c2, p3))
		return pts

	ro, ri = r + w / 2, r - w / 2
	pen.moveTo((cx + ro * math.cos(math.radians(a0)), cy + ro * math.sin(math.radians(a0))))
	for c1, c2, p3 in arc(ro, a0, a1):
		pen.curveTo(c1, c2, p3)
	pen.lineTo((cx + ri * math.cos(math.radians(a1)), cy + ri * math.sin(math.radians(a1))))
	for c1, c2, p3 in arc(ri, a1, a0):
		pen.curveTo(c1, c2, p3)
	pen.closePath()


GLYPHS = {
	'A': lambda p: (stroke(p, (60, 0), (300, 700), 90), stroke(p, (540, 0), (300, 700), 80), poly(p, [(140, 180), (460, 180), (460, 250), (140, 250)])),
	'X': lambda p: (stroke(p, (60, 0), (540, 700), 90), stroke(p, (540, 0), (60, 700), 80)),
	'H': lambda p: (poly(p, [(60, 0), (150, 0), (150, 700), (60, 700)]), poly(p, [(450, 0), (540, 0), (540, 700), (450, 700)]), poly(p, [(150, 320), (450, 320), (450, 400), (150, 400)])),
	'zhe': lambda p: (poly(p, [(355, 0), (445, 0), (445, 500), (355, 500)]),
					poly(p, [(100, 230), (700, 230), (700, 290), (100, 290)]),
					arc_stroke(p, 400, 260, 330, 80, 140, 220),
					arc_stroke(p, 400, 260, 330, 80, -40, 40)),
	'eight': lambda p: (ellipse(p, 300, 200, 220, 200), ellipse(p, 300, 200, 130, 115, True),
					ellipse(p, 300, 540, 180, 170), ellipse(p, 300, 540, 95, 90, True)),
	'o_bar': lambda p: (ellipse(p, 300, 350, 260, 350), ellipse(p, 300, 350, 170, 260, True), poly(p, [(0, 330), (600, 330), (600, 380), (0, 380)])),
}


def to_json(rec):
	contours, cur = [], None
	for op, args in rec.value:
		if op == 'moveTo':
			cur = [{'x': args[0][0], 'y': args[0][1], 'type': 'on'}]
		elif op == 'lineTo':
			cur.append({'x': args[0][0], 'y': args[0][1], 'type': 'on'})
		elif op == 'curveTo':
			cur += [{'x': args[0][0], 'y': args[0][1], 'type': 'curve'},
					{'x': args[1][0], 'y': args[1][1], 'type': 'curve'},
					{'x': args[2][0], 'y': args[2][1], 'type': 'on'}]
		elif op in ('closePath', 'endPath'):
			last = cur[-1]
			if last['type'] == 'on' and (last['x'], last['y']) == (cur[0]['x'], cur[0]['y']):
				cur.pop()		# closing duplicate
			elif last['type'] == 'on' and cur[-2]['type'] == 'curve' and (last['x'], last['y']) == (cur[0]['x'], cur[0]['y']):
				cur.pop()
			contours.append(cur)
		else:
			raise ValueError(op)
	return contours


if __name__ == '__main__':
	for name, build in GLYPHS.items():
		path = pathops.Path()
		build(path.getPen())
		path.simplify(fix_winding=True)
		rec = RecordingPen()
		path.draw(rec)
		with open(os.path.join(HERE, name + '.json'), 'w') as f:
			json.dump({'name': name, 'source': 'skia-pathops union', 'contours': to_json(rec)}, f, indent=1)
		print(name, [len(c) for c in to_json(rec)])
