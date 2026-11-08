# MODULE: TypeRig / Proxy / FontLab / Devtools / State
# -----------------------------------------------------------
# Plain-data glyph snapshots and a readable diff, to check what
# a tool changed and whether Undo really restored it.
#
# Node coordinates are element-local, so snapshots also keep
# each element's transform: a tool that flips or moves an
# element changes only the transform.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import absolute_import, print_function

from typerig.proxy.fl.devtools.app import qv

# - Init --------------------------------
__version__ = '0.1.0'

_ROUND = 4

# - Snapshot ----------------------------
def _glyph(name=None):
	from typerig.proxy.fl.objects.glyph import pGlyph
	from typerig.proxy.fl.objects.font import pFont
	return pGlyph() if name is None else pFont().glyph(name)

def _transform(shape):
	'''Element transform as (m11, m12, m21, m22, dx, dy), or None.'''
	try:
		t = qv(shape, 'transform')
		return tuple(round(v, _ROUND) for v in (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()))
	except Exception:
		return None

def _anchors(layer):
	out = {}
	try:
		for a in layer.anchors:
			out[a.name] = (round(a.point.x(), _ROUND), round(a.point.y(), _ROUND))
	except Exception:
		pass
	return out

def snapshot(glyph=None, layers=None):
	'''Snapshot of a glyph as plain data:
		{layer name: {'adv': float,
		              'shapes': [[[(x, y, type), ...] per contour] per element],
		              'tx': [element transform per element],
		              'anchors': {name: (x, y)}}}
	glyph: name, or None for the current glyph. layers: names, or None for all.'''
	out = {}
	for layer in _glyph(glyph).layers():
		if layers and layer.name not in layers: continue
		shapes, tx = [], []
		for shape in layer.shapes:
			shapes.append([[(round(n.x, _ROUND), round(n.y, _ROUND), str(n.type)) for n in contour.nodes()]
						   for contour in shape.contours])
			tx.append(_transform(shape))
		out[layer.name] = {'adv': round(layer.advanceWidth, _ROUND), 'shapes': shapes,
						   'tx': tx, 'anchors': _anchors(layer)}
	return out

# - Diff --------------------------------
def _diff_layer(name, la, lb, tol, out):
	if abs(la['adv'] - lb['adv']) > tol:
		out.append('{}: adv {} -> {}'.format(name, la['adv'], lb['adv']))
	if len(la['shapes']) != len(lb['shapes']):
		out.append('{}: elements {} -> {}'.format(name, len(la['shapes']), len(lb['shapes'])))

	for si, (ta, tb) in enumerate(zip(la.get('tx', []), lb.get('tx', []))):
		if ta != tb:
			out.append('{} e{}: transform {} -> {}'.format(name, si, ta, tb))

	for si, (sa, sb) in enumerate(zip(la['shapes'], lb['shapes'])):
		if len(sa) != len(sb):
			out.append('{} e{}: contours {} -> {}'.format(name, si, len(sa), len(sb)))
		for ci, (ca, cb) in enumerate(zip(sa, sb)):
			if len(ca) != len(cb):
				out.append('{} e{} c{}: nodes {} -> {}'.format(name, si, ci, len(ca), len(cb)))
				continue
			for ni, (na, nb) in enumerate(zip(ca, cb)):
				moved = abs(na[0] - nb[0]) > tol or abs(na[1] - nb[1]) > tol
				if moved or na[2] != nb[2]:
					retyped = '' if na[2] == nb[2] else ' type {} -> {}'.format(na[2], nb[2])
					out.append('{} e{} c{} n{}: ({:g}, {:g}) -> ({:g}, {:g}){}'.format(
						name, si, ci, ni, na[0], na[1], nb[0], nb[1], retyped))

	for an in sorted(set(la['anchors']) | set(lb['anchors'])):
		if la['anchors'].get(an) != lb['anchors'].get(an):
			out.append('{} anchor {}: {} -> {}'.format(name, an, la['anchors'].get(an), lb['anchors'].get(an)))

def diff(a, b, tol=1e-3, limit=60):
	'''Readable differences between two snapshots; [] when equal within tol.
	Addresses: layer e<element> c<contour> n<node>.'''
	out = []
	for name in sorted(set(a) | set(b)):
		if name not in a: out.append('+ layer {}'.format(name)); continue
		if name not in b: out.append('- layer {}'.format(name)); continue
		_diff_layer(name, a[name], b[name], tol, out)
	if len(out) > limit:
		out = out[:limit] + ['... {} more'.format(len(out) - limit)]
	return out
