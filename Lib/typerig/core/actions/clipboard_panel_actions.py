# ===================================================================
# TypeRig / Core / Actions / Clipboard Panel Actions
# ===================================================================
# Dispatchers for the TypeRig Clipboard panel (FL Panel/Clipboard.py):
# a bank of copied outline parts, pasted back as contours, over a node
# selection, or traced into one path.
#
# Every public npa_clip_* function receives (glyph, scope_layers) first:
# the glyph proxy (or a core Glyph) and the layer names to work on.
# A bank item is a core Glyph: one Layer per copied layer, holding one
# Shape of closed contours, or a single open contour (a partial copy).
# The panel keeps the bank; nothing here holds state.
#
# Paste modes (contours and nodes):
#   'plain' — at the copied coordinates (contours) / aligned (nodes)
#   'fit'   — affine scale into the bounds of the node selection
#   'delta' — Delta Machine scale into the selection bounds, stems kept;
#             axis: the Delta panel's Live Axis (clip_live_axis)
# Then flip around its own centre and align its `align` corner onto
# the same corner of the selection bounds (codes: Bounds.align_matrix).
#
# Backgrounds are addressed as 'mask.<layer>' (FL naming; the Glyphs
# proxy trGlyph resolves them). Host writes go through the proxy
# methods when present (append_contour, trContour.mount), else core.
# ===================================================================

from __future__ import absolute_import, print_function, division

import copy
import json
import xml.etree.ElementTree as ET
from collections import OrderedDict

from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour
from typerig.core.objects.transform import TransformOrigin
from typerig.core.objects.utils import Bounds

MASK_PREFIX   = 'mask.'						# background of a layer (FL naming)
XML_EXCLUDE   = ['transform', 'g2']			# FL: more compact clipboard files
ALIGN_CODES   = ('TL', 'TR', 'C', 'BL', 'BR')	# corners offered by the panel
PASTE_MODES   = ('plain', 'fit', 'delta')


# ===================================================================
# Internal helpers
# ===================================================================
def _detach(obj):
	"""Pure core copy of a proxy (eject) or core object (deep copy)."""
	return obj.eject() if hasattr(obj, 'eject') else copy.deepcopy(obj)


def _clean(node):
	node = copy.deepcopy(node)
	node.selected = False
	return node


def _selected_contour_map(layer):
	"""{contour index: [selected node indices]}, [] meaning the whole contour."""
	out = OrderedDict()
	for ci, contour in enumerate(layer.contours):
		idx = [i for i, n in enumerate(contour.data) if n.selected]
		if idx:
			out[ci] = [] if len(idx) == len(contour.data) else idx
	return out


def _selected_nodes(layer):
	"""Selected nodes of a layer, in contour / node order."""
	return [n for contour in layer.contours for n in contour.data if n.selected]


def _selection_bounds(layer):
	nodes = _selected_nodes(layer) if layer is not None else []
	return Bounds([(n.x, n.y) for n in nodes]) if nodes else None


def _all_nodes(layer):
	return [n for contour in layer.contours for n in contour.data]


def _points_bounds(nodes):
	return Bounds([(n.x, n.y) for n in nodes])


def _pairs(bank, scope_layers):
	"""[(target layer name, bank Layer)]: a one-layer item goes to every
	scope layer, otherwise each scope layer takes the bank layer of its name."""
	if len(bank.layers) == 1:
		return [(name, bank.layers[0]) for name in scope_layers]
	return [(name, bank.layer(name)) for name in scope_layers if bank.layer(name) is not None]


def _append_contour(layer, contour):
	if hasattr(layer, 'append_contour'):
		layer.append_contour(contour)
		return
	outlines = [s for s in layer.shapes if not getattr(s, 'is_component', False)]
	if outlines:
		outlines[0].append(contour)
	else:
		layer.append(Shape([contour]))


def _mount_contour(contour, core):
	if hasattr(contour, 'mount'):
		contour.mount(core)
	else:
		contour.data = core.data


def _round(nodes):
	for n in nodes:
		n.x, n.y = float(round(n.x)), float(round(n.y))


def _flip(nodes, flip_h, flip_v):
	"""Mirror nodes around the centre of their own bounds."""
	if not (flip_h or flip_v) or not nodes:
		return
	b = _points_bounds(nodes)
	cx, cy = (b.x + b.xmax) / 2., (b.y + b.ymax) / 2.
	for n in nodes:
		if flip_h: n.x = 2 * cx - n.x
		if flip_v: n.y = 2 * cy - n.y


def _scale_fit(nodes, target):
	"""Unconstrained affine scale of nodes into target bounds (own centre)."""
	b = _points_bounds(nodes)
	if not b.width or not b.height:
		return
	sx, sy = target.width / float(b.width), target.height / float(b.height)
	cx, cy = (b.x + b.xmax) / 2., (b.y + b.ymax) / 2.
	for n in nodes:
		n.x = (n.x - cx) * sx + cx
		n.y = (n.y - cy) * sy + cy


def _align(nodes, target, code):
	"""Move nodes so their `code` corner lands on target's `code` corner."""
	if target is None or not code or not nodes:
		return
	src = _points_bounds(nodes).align_matrix[code]
	dst = target.align_matrix[code]
	dx, dy = dst[0] - src[0], dst[1] - src[1]
	for n in nodes:
		n.x += dx
		n.y += dy


def _reverse_contour(contour):
	if contour.closed:
		contour.reverse()
	else:		# open path: plain reversal, ends stay ends
		contour.data = list(reversed(contour.data))


# ===================================================================
# Delta Machine axis
# ===================================================================
def _stems(row):
	try:
		return (float(row.get('vstem')), float(row.get('hstem')))
	except (TypeError, ValueError):
		return None


def clip_live_axis(live):
	"""Delta paste axis from the Delta panel's Live Axis data
	({'inputs': [{'name', 'vstem', 'hstem'}], 'options': {...}}, a dict or
	its JSON text).

	Returns {'name': 'Live', 'inputs': OrderedDict layer -> (vstem, hstem)
	sorted by vstem (DeltaScale needs a monotonic axis), 'extrapolate': bool},
	or None when the Live Axis has fewer than two layers with stems."""
	if isinstance(live, (str, bytes)):
		live = json.loads(live)
	if not isinstance(live, dict):
		return None
	rows = [(r.get('name'), _stems(r)) for r in live.get('inputs', []) or [] if isinstance(r, dict)]
	inputs = OrderedDict(sorted(((n, s) for n, s in rows if n and s), key=lambda kv: kv[1][0]))
	if len(inputs) < 2:
		return None
	options = live.get('options') or {}
	return {'name': 'Live', 'inputs': inputs, 'extrapolate': bool(options.get('extrapolate', True))}


def _delta_ready(bank, delta):
	"""(working copy of bank, virtual axis) or (None, reason)."""
	if delta is None:
		return None, 'Delta: no Live Axis (two or more layers with stems).'
	inputs = delta['inputs']
	work = copy.deepcopy(bank)
	names = [n for n in inputs if work.layer(n) is not None]
	if len(names) < 2:
		return None, 'Delta: the item has %s; the Live Axis needs %s.' % (
			', '.join(l.name for l in bank.layers), ', '.join(inputs))
	for n in names:
		work.layer(n).stems = inputs[n]
	return (work, work.virtual_axis(names)), None


def _delta_scale(layer, vaxis, delta, stem_name, target, origin=TransformOrigin.CENTER):
	"""Scaled copy of a bank layer, or (None, reason)."""
	stems = delta['inputs'].get(stem_name)
	if stems is None:
		return None, '%s is not on the Live Axis (no stems)' % stem_name
	layer.stems = stems
	try:
		return layer.scale_with_axis(vaxis, target.width, target.height, extrapolate=delta.get('extrapolate', True),
		                             transform_origin=origin), None
	except (ZeroDivisionError, ValueError) as error:		# degenerate axis (e.g. masters differ in stems only)
		return None, 'Delta could not solve %s: %s' % (stem_name, error)


def _prepare(bank, mode, delta):
	"""Source glyph and virtual axis for a paste mode, or a reason it cannot run."""
	if mode != 'delta':
		return bank, None, None
	ready, reason = _delta_ready(bank, delta)
	if ready is None:
		return None, None, reason
	return ready[0], ready[1], None


# ===================================================================
# 1. COPY
# ===================================================================
def npa_clip_copy(glyph, scope_layers, source):
	"""Copy the contours selected on source, taken from every scope layer.

	Whole contours are kept as closed contours. If any contour is only
	partly selected, the selected nodes of all of them become one open
	contour (a partial path). Layers whose contours do not match source
	are left out. Returns (bank Glyph or None, partial)."""
	src = glyph.layer(source)
	selection = _selected_contour_map(src) if src is not None else {}
	if not selection:
		return None, False
	partial = any(idx for idx in selection.values())
	bank = Glyph(name=glyph.name)
	for name in scope_layers:
		lyr = glyph.layer(name)
		if lyr is None:
			continue
		contours = lyr.contours
		if max(selection) >= len(contours):
			continue
		cores = [(_detach(contours[ci]), idx) for ci, idx in selection.items()]
		if any(idx and max(idx) >= len(core.data) for core, idx in cores):
			continue
		if partial:
			nodes = [_clean(core.data[i]) for core, idx in cores for i in (idx or range(len(core.data)))]
			out = [Contour(nodes, closed=False)]
		else:
			out = [Contour([_clean(n) for n in core.data], closed=True) for core, _ in cores]
		bank.append(Layer([Shape(out)], name=name))
	return (bank if len(bank.layers) else None), partial


# ===================================================================
# 2. PASTE
# ===================================================================
def npa_clip_paste_contours(glyph, scope_layers, banks, mode='plain', align='C',
                            flip=(False, False), to_background=False, rounding=False, delta=None):
	"""Paste closed bank items as new contours on every scope layer.

	banks : bank Glyphs (partial items are skipped)
	mode  : 'plain' | 'fit' | 'delta' — fit and delta need a node selection
	        on the target layer (its bounds); plain keeps the copied place
	to_background : paste into 'mask.<layer>'
	delta : clip_live_axis() result (mode 'delta')
	Returns (done layer names, skipped lines)."""
	done, skipped = [], []
	flip_h, flip_v = flip
	for bank in banks:
		if is_partial(bank):
			skipped.append('%s: partial path (use paste nodes or trace)' % bank.name)
			continue
		src, vaxis, reason = _prepare(bank, mode, delta)
		if src is None:
			skipped.append('%s: %s' % (bank.name, reason))
			continue
		for name, layer in _pairs(src, scope_layers):
			target_name = MASK_PREFIX + name if to_background else name
			target = glyph.layer(target_name)
			if target is None:
				skipped.append('%s: no layer %s' % (bank.name, target_name))
				continue
			bounds = _selection_bounds(glyph.layer(name))
			if mode != 'plain' and bounds is None:
				skipped.append('%s: select nodes on %s (target bounds)' % (bank.name, name))
				continue
			if mode == 'delta':
				work, why = _delta_scale(layer, vaxis, delta, layer.name, bounds)
				if work is None:
					skipped.append('%s: %s' % (bank.name, why))
					continue
			else:
				work = copy.deepcopy(layer)
			nodes = _all_nodes(work)
			if mode == 'fit':
				_scale_fit(nodes, bounds)
			_flip(nodes, flip_h, flip_v)
			if mode != 'plain':
				_align(nodes, bounds, align)
			if rounding:
				_round(nodes)
			for contour in work.contours:
				_append_contour(target, Contour([_clean(n) for n in contour.data], closed=contour.closed))
			if name not in done:
				done.append(name)
	return done, skipped


def npa_clip_paste_nodes(glyph, scope_layers, bank, align='TL', flip=(False, False),
                         overwrite=False, rounding=False, delta=None):
	"""Paste a bank item's nodes over the node selection of every scope layer.

	The item is flipped, then its `align` corner is put on the same corner
	of the selection bounds (delta: first scaled into those bounds).
	overwrite=False: move the selected nodes onto the pasted ones (counts
	must match). overwrite=True: replace the selected run of nodes (one
	contour, first to last selected) with the pasted nodes.
	Returns (done layer names, skipped lines)."""
	done, skipped = [], []
	src, vaxis, reason = _prepare(bank, 'delta' if delta is not None else 'plain', delta)
	if src is None:
		return done, [reason]
	plan = []		# first pass: work out every layer before writing any
	for name, layer in _pairs(src, scope_layers):
		target = glyph.layer(name)
		dst = _selected_nodes(target) if target is not None else []
		if not dst:
			skipped.append('%s: no node selection' % name)
			continue
		bounds = _points_bounds(dst)
		if delta is not None:
			work, why = _delta_scale(layer, vaxis, delta, layer.name, bounds, TransformOrigin.BASELINE)
			if work is None:
				skipped.append('%s: %s' % (name, why))
				continue
		else:
			work = copy.deepcopy(layer)
		nodes = [_clean(n) for n in _all_nodes(work)]
		_flip(nodes, *flip)
		_align(nodes, bounds, align)
		if rounding:
			_round(nodes)
		if overwrite:
			hits = [(ci, [i for i, n in enumerate(c.data) if n.selected])
			        for ci, c in enumerate(target.contours)]
			hits = [(ci, idx) for ci, idx in hits if idx]
			if len(hits) != 1:
				skipped.append('%s: overwrite needs a selection in one contour' % name)
				continue
			plan.append((name, 'overwrite', (target.contours[hits[0][0]], hits[0][1], nodes)))
		elif len(dst) != len(nodes):
			skipped.append('%s: %d nodes selected, item has %d' % (name, len(dst), len(nodes)))
		else:
			plan.append((name, 'move', (dst, nodes)))

	for name, kind, data in plan:
		if kind == 'move':
			for d, s in zip(*data):
				d.x, d.y = s.x, s.y
		else:
			contour, idx, nodes = data
			core = _detach(contour)
			core.data = core.data[:idx[0]] + nodes + core.data[idx[-1] + 1:]
			_mount_contour(contour, Contour([_clean(n) for n in core.data], closed=core.closed))
		done.append(name)
	return done, skipped


def npa_clip_trace(glyph, scope_layers, banks, close=True, rounding=False):
	"""Join the nodes of the bank items (in order) into one new contour on
	every scope layer. Returns (done layer names, skipped lines)."""
	done, skipped = [], []
	for name in scope_layers:
		target = glyph.layer(name)
		if target is None:
			continue
		nodes = []
		for bank in banks:
			pairs = dict(_pairs(bank, [name]))
			if name in pairs:
				nodes += [_clean(n) for n in _all_nodes(pairs[name])]
			else:
				skipped.append('%s: no layer %s' % (bank.name, name))
		if not nodes:
			continue
		if rounding:
			_round(nodes)
		_append_contour(target, Contour(nodes, closed=close))
		done.append(name)
	return done, skipped


# ===================================================================
# 3. BANK ITEMS
# ===================================================================
def is_partial(bank):
	"""True for a partial-path item (its contours are open)."""
	for layer in bank.layers:
		for contour in layer.contours:
			return not contour.closed
	return False


def clip_info(bank):
	"""{'name', 'nodes', 'contours', 'partial', 'layers'} of a bank item
	(counts from its first layer; all layers match)."""
	first = bank.layers[0] if bank.layers else None
	return {
		'name':     bank.name,
		'nodes':    len(_all_nodes(first)) if first is not None else 0,
		'contours': len(first.contours) if first is not None else 0,
		'partial':  is_partial(bank),
		'layers':   [layer.name for layer in bank.layers],
	}


def clip_reverse(bank):
	"""Reverse every contour of a bank item in place."""
	for layer in bank.layers:
		for contour in layer.contours:
			_reverse_contour(contour)


# ===================================================================
# 4. FILES (FL clipboard XML: <clipboard><item uid=..><glyph>..)
# ===================================================================
def clip_bank_to_xml(items):
	"""items: [(uid, bank Glyph)] -> XML text."""
	parts = ['<?xml version="1.0" encoding="UTF-8"?><clipboard>']
	for uid, bank in items:
		parts.append('<item uid="%s">%s</item>' % (uid, bank.to_XML(XML_EXCLUDE)))
	parts.append('</clipboard>')
	return ''.join(parts)


def clip_bank_from_xml(text):
	"""XML text -> [(uid, bank Glyph)]; uid is an int when it reads as one."""
	out = []
	root = ET.fromstring(text.encode('utf-8') if isinstance(text, str) else text)
	for item in root.findall('item'):
		elem = item.find('glyph')
		if elem is None:
			continue
		uid = item.get('uid')
		try:
			uid = int(uid)
		except (TypeError, ValueError):
			pass
		out.append((uid, Glyph.from_XML(ET.tostring(elem, encoding='unicode'))))
	return out
