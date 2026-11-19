# MODULE: TypeRig / IO / TrFont Audit
# NOTE: Declarative dump + diff for the .trfont round trip
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# The round trip VFC -> .trfont -> VFC is judged by one rule: dump both
# sides to the same plain-dict schema and diff them. An empty diff on the
# field set of a stage means that stage passes.
#
# This module is pure core (no FontLab). It owns:
#   - the schema (STAGES, and the shape of every record),
#   - the number normalization (one place: _num),
#   - dump_font(core Font)  -> dict
#   - diff(a, b)            -> [str]
#   - xml_dir_diff(d1, d2)  -> [str]  (folder-level XML idempotence)
#
# The FontLab dumper (typerig.proxy.tr.audit) emits the SAME schema from a
# live flPackage, so FL dump vs core dump vs FL dump all diff the same way.
# Plan and stage definitions: Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md

# - Dependencies ------------------------
import os
from xml.etree import ElementTree as ET

# - Init --------------------------------
__version__ = '0.1.0'

# Field sets are cumulative: stage 'b' dumps everything 'a' does and more.
STAGES = ('a', 'b', 'c')

# Numbers are rounded here and only here. 1e-6 hides float noise from
# FL's QTransform and XML text round trips, not real edits.
ROUND = 6

# - Normalization -----------------------
def _num(value):
	'''Normalize a number: round, collapse -0.0, keep ints as floats.'''
	if value is None:
		return None
	try:
		v = round(float(value), ROUND)
	except (TypeError, ValueError):
		return value
	return 0.0 if v == 0 else v

def _str(value):
	'''Normalize a string field: None and '' are the same "unset".'''
	return '' if value is None else str(value)

def _newlines(text):
	return _str(text).replace('\r\n', '\n').replace('\r', '\n')

def _location(loc):
	return {str(k): _num(v) for k, v in (loc or {}).items()}

def _transform(t):
	'''6-tuple (xx, xy, yx, yy, dx, dy); identity when missing.'''
	if t is None:
		return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
	return tuple(_num(t[i]) for i in range(6))

def canonical_guide(x=None, y=None, angle=None, line=None, name=''):
	'''One comparable form for a guide, from UFO fields or from a line.

	UFO: x only = vertical, y only = horizontal, else (x, y, angle) degrees
	counter-clockwise. line = ((x1, y1), (x2, y2)) in font space (FL).
	Returns ('v', x, name) | ('h', y, name) | ('a', fx, fy, angle, name),
	where (fx, fy) is the foot of the perpendicular from the origin, so any
	two points on the same line give the same record.
	'''
	import math
	if line is not None:
		(x1, y1), (x2, y2) = line
		a = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
		x, y, angle = x1, y1, a
	elif x is not None and y is None:
		return ('v', _num(x), _str(name))
	elif y is not None and x is None:
		return ('h', _num(y), _str(name))
	else:
		x, y, angle = float(x or 0.0), float(y or 0.0), float(angle or 0.0) % 180.0

	if abs(angle - 90.0) < 1e-6:
		return ('v', _num(x), _str(name))
	if angle < 1e-6 or abs(angle - 180.0) < 1e-6:
		return ('h', _num(y), _str(name))
	r = math.radians(angle)
	dx, dy = math.cos(r), math.sin(r)
	t = x * dx + y * dy
	return ('a', _num(x - t * dx), _num(y - t * dy), _num(angle), _str(name))

def dump_value(value):
	'''Normalize a free-form value (info extras): numbers rounded, lists kept.'''
	if isinstance(value, bool) or value is None:
		return value
	if isinstance(value, (int, float)):
		return _num(value)
	if isinstance(value, (list, tuple)):
		return [dump_value(v) for v in value]
	return _str(value)

def dump_metrics(m):
	'''Vertical metrics record (upm is font-level and dumped separately).'''
	return {
		'ascender': _num(m.ascender), 'descender': _num(m.descender),
		'x_height': _num(m.x_height), 'cap_height': _num(m.cap_height),
		'line_gap': _num(m.line_gap),
	}

def dump_axis(name, tag, short_name, minimum, default, maximum,
              design_minimum=None, design_default=None, design_maximum=None, axis_map=None):
	'''Axis record. A design value left unset means "same as user space".'''
	pick = lambda design, user: _num(user if design is None else design)
	return {
		'name': _str(name), 'tag': _str(tag), 'short_name': _str(short_name),
		'minimum': _num(minimum), 'default': _num(default), 'maximum': _num(maximum),
		'design': (pick(design_minimum, minimum), pick(design_default, default), pick(design_maximum, maximum)),
		'map': [(_num(u), _num(d)) for u, d in (axis_map or [])],
	}

def _stage_at_least(stage, minimum):
	return STAGES.index(stage) >= STAGES.index(minimum)

# - Core dump ---------------------------
def _dump_contour(contour):
	return {
		'closed': bool(contour.closed),
		'nodes': [(_num(n.x), _num(n.y), _str(n.type), bool(n.smooth), _str(getattr(n, 'name', ''))) for n in contour.nodes],
	}

def _dump_layer(layer):
	return {
		'width':   _num(layer.advance_width),
		'height':  _num(layer.advance_height),
		'anchors': sorted((_str(a.name), _num(a.x), _num(a.y)) for a in layer.anchors),
		'guides':  sorted((canonical_guide(g.x, g.y, g.angle, name=g.name) for g in (layer.guidelines or [])), key=repr),
		'shapes':  [{
			'name':      _str(s.name),
			'transform': _transform(getattr(s, 'transform', None)),
			'contours':  [_dump_contour(c) for c in s.contours],
		} for s in layer.shapes],
	}

def _dump_info(info):
	return {attr: (_num(getattr(info, attr, None)) if attr in info._NUMERIC_FIELDS else _str(getattr(info, attr, None)))
	        for attr in sorted(info._FIELDS.values())}

def dump_font(font, stage='a'):
	'''Dump a core Font to the audit schema for a stage.

	Layers are keyed by name (FL glyph layer order is not master order).
	'''
	m = font.metrics
	out = {
		'upm': _num(m.upm),
		'metrics': dump_metrics(m),
		'info': _dump_info(font.info),
		# every other font-info field (UFO names), carried in FontInfo.lib
		'info_extra': {str(k): dump_value(v) for k, v in sorted((getattr(font.info, 'lib', None) or {}).items())},
		'axes': [dump_axis(
			a.name, a.tag, getattr(a, 'short_name', ''), a.minimum, a.default, a.maximum,
			getattr(a, 'design_minimum', None), getattr(a, 'design_default', None),
			getattr(a, 'design_maximum', None), getattr(a, 'map', None))
			for a in font.axes],
		'masters': [{
			'name': _str(ms.name), 'layer': _str(ms.layer_name),
			'default': bool(ms.is_default), 'location': _location(ms.location),
			# effective metrics: the master's own, else the font's
			'metrics': dump_metrics(getattr(ms, 'metrics', None) or m),
		} for ms in font.masters.data],
		'instances': [{
			'name': _str(i.name), 'location': _location(i.location),
		} for i in font.instances.data],
		'glyph_order': list(font.glyph_names),
		'glyphs': {},
	}

	for glyph in font.glyphs:
		out['glyphs'][glyph.name] = {
			'unicodes': [int(u) for u in font.unicodes(glyph.name)],
			'mark':     _str(glyph.mark),
			'note':     _newlines(getattr(glyph, 'note', None)),
			'layers':   {_str(l.name): _dump_layer(l) for l in glyph.layers},
		}

	if _stage_at_least(stage, 'b'):
		# per-glyph OpenType glyph/mark class (GDEF), FontLab names in Glyph.lib
		for glyph in font.glyphs:
			lib = getattr(glyph, 'lib', None) or {}
			out['glyphs'][glyph.name]['ot_class'] = (int(lib.get('com.fontlab.otGlyphClass', 0)),
			                                          int(lib.get('com.fontlab.otMarkClass', 0)))
		kerning = {}
		master_names = [ms.name for ms in font.masters.data] or [None]
		for name in master_names:
			k = font.kerning_for(name)
			kerning[_str(name)] = sorted((p.first, p.second, int(p.value)) for p in (k.data if k is not None else []))
		out['kerning']  = kerning
		out['groups']   = {g.name: list(g.members) for g in font.groups.data}
		out['features'] = _newlines(font.features)

	return out

# - Diff --------------------------------
def diff(a, b, path='', limit=200):
	'''Recursive structural diff. Returns human-readable lines; [] == equal.

	Lists of equal length are compared item by item; otherwise the length
	mismatch is reported once (node-level noise would bury the real cause).
	'''
	out = []
	_diff(a, b, path or '$', out, limit)
	return out

def _diff(a, b, path, out, limit):
	if len(out) >= limit:
		return

	if isinstance(a, dict) and isinstance(b, dict):
		for key in sorted(set(a) | set(b), key=str):
			p = '{}.{}'.format(path, key)
			if key not in a:
				out.append('{}: missing on left'.format(p))
			elif key not in b:
				out.append('{}: missing on right'.format(p))
			else:
				_diff(a[key], b[key], p, out, limit)
		return

	if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and not _is_record(a):
		if len(a) != len(b):
			out.append('{}: length {} != {}'.format(path, len(a), len(b)))
			return
		for i, (x, y) in enumerate(zip(a, b)):
			_diff(x, y, '{}[{}]'.format(path, i), out, limit)
		return

	if _norm(a) != _norm(b):
		out.append('{}: {!r} != {!r}'.format(path, a, b))

def _is_record(value):
	'''A flat tuple of scalars (node, anchor, pair) compares as one value.'''
	return isinstance(value, tuple) and all(not isinstance(v, (list, tuple, dict)) for v in value)

def _norm(value):
	return tuple(value) if isinstance(value, (list, tuple)) else value

# - XML folder idempotence --------------
def _canon(elem):
	'''Canonical form of an element: tag, sorted attributes, stripped text, children.'''
	text = (elem.text or '').strip()
	return (elem.tag, tuple(sorted(elem.attrib.items())), text, tuple(_canon(c) for c in elem))

def xml_dir_diff(dir_a, dir_b):
	'''Compare every XML file (and features.fea) of two .trfont folders.

	Paths are compared relative to each folder; attribute order and
	indentation are ignored, element order is not.
	'''
	out = []

	def files(root):
		found = {}
		for base, _, names in os.walk(root):
			for name in names:
				full = os.path.join(base, name)
				found[os.path.relpath(full, root).replace(os.sep, '/')] = full
		return found

	fa, fb = files(dir_a), files(dir_b)
	for rel in sorted(set(fa) | set(fb)):
		if rel not in fa or rel not in fb:
			out.append('{}: only in {}'.format(rel, 'right' if rel not in fa else 'left'))
			continue
		if rel.endswith('.fea'):
			with open(fa[rel], encoding='utf-8') as h1, open(fb[rel], encoding='utf-8') as h2:
				if h1.read() != h2.read():
					out.append('{}: text differs'.format(rel))
			continue
		try:
			ca = _canon(ET.parse(fa[rel]).getroot())
			cb = _canon(ET.parse(fb[rel]).getroot())
		except ET.ParseError as e:
			out.append('{}: parse error {}'.format(rel, e))
			continue
		if ca != cb:
			out.append('{}: XML differs'.format(rel))
	return out

# - Summary -----------------------------
def summarize(lines):
	'''Collapse diff lines into {field pattern: count}.

	Glyph and layer names become "*", list indices "[]", values are dropped:
	  $.glyphs.Aacute.layers.Bold.shapes[1].transform[4]: 308.0 != 0.0
	  -> $.glyphs.*.layers.*.shapes[].transform[4]
	The transform/tuple slot index is kept (it names the field).
	'''
	import re
	counts = {}
	for line in lines:
		path = line.split(': ', 1)[0]
		path = re.sub(r'^\$\.glyphs\.[^.]+\.', '$.glyphs.*.', path)
		path = re.sub(r'\.layers\.[^.]+\.', '.layers.*.', path)
		path = re.sub(r'\.(shapes|contours|nodes|guides|anchors)\[\d+\]', r'.\1[]', path)
		counts[path] = counts.get(path, 0) + 1
	return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
