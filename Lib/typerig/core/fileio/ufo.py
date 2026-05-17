# MODULE: TypeRig / IO / UFO (Converter)
# NOTE: Pure-Python UFO 3 ↔ .trfont converter.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
# ----------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# Transliteration between the .trfont work format and UFO 3.
# Uses fontTools.ufoLib for plist / .glif / layer handling and
# fontTools.designspaceLib for the masters/axes/instances sidecar.
#
# Direction summary:
#   tr_to_ufo: one Font  →  one .ufo (multi-layer) + sibling .designspace
#   ufo_to_tr: one .ufo (multi-layer) + optional .designspace  →  one Font
#
# No FontLab dependency. No proxy code is imported.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import os
import shutil
import sys
from types import SimpleNamespace

from fontTools.ufoLib import UFOReader, UFOWriter, UFOFormatVersion
from fontTools.ufoLib.glifLib import (
	writeGlyphToString, readGlyphFromString,
)
from fontTools.designspaceLib import (
	DesignSpaceDocument, AxisDescriptor,
	SourceDescriptor, InstanceDescriptor,
)

from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node
from typerig.core.objects.anchor import Anchor
from typerig.core.objects.guideline import Guideline
from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Masters, Master
from typerig.core.objects.instance import Instances, Instance
from typerig.core.objects.encoding import Encoding
from typerig.core.objects.kern import Kerning, KernPair
from typerig.core.objects.groups import Groups

# - Init --------------------------------
__version__ = '0.1.0'

# - Maps --------------------------------
# TR FontInfo attr  →  UFO fontinfo.plist key. The kebab→UFO map is *not* a
# pure dash-strip — UFO uses prefixed names for many fields. We keep this
# table small and explicit so it round-trips.
TR_TO_UFO_INFO = {
	'family_name':          'familyName',
	'style_name':           'styleName',
	'year':                 'year',
	'note':                 'note',
	'designer':             'openTypeNameDesigner',
	'designer_url':         'openTypeNameDesignerURL',
	'manufacturer':         'openTypeNameManufacturer',
	'manufacturer_url':     'openTypeNameManufacturerURL',
	'copyright':            'copyright',
	'trademark':            'trademark',
	'description':          'openTypeNameDescription',
	'license':              'openTypeNameLicense',
	'license_url':          'openTypeNameLicenseURL',
	'unique_id':            'openTypeNameUniqueID',
	'vendor_id':            'openTypeOS2VendorID',
	'weight_class':         'openTypeOS2WeightClass',
	'width_class':          'openTypeOS2WidthClass',
	'italic_angle':         'italicAngle',
	'underline_position':   'postscriptUnderlinePosition',
	'underline_thickness':  'postscriptUnderlineThickness',
	'postscript_font_name': 'postscriptFontName',
}

# version is special — TR stores a single string, UFO has versionMajor/Minor.
# Handled in _tr_info_to_ufo / _ufo_info_to_tr.

UFO_TO_TR_INFO = {ufo: tr for tr, ufo in TR_TO_UFO_INFO.items()}

# UFO field type hints. ufoLib validates types per the spec.
UFO_INFO_INT_FIELDS = {
	'openTypeOS2WeightClass', 'openTypeOS2WidthClass', 'year',
	'versionMajor', 'versionMinor',
}
UFO_INFO_FLOAT_FIELDS = {
	'italicAngle', 'postscriptUnderlinePosition', 'postscriptUnderlineThickness',
	'ascender', 'descender', 'xHeight', 'capHeight',
}

# TR node type semantics (NOT a flat 1:1 with UFO):
#   'on'    — any on-curve point. Maps to UFO 'line', 'curve', or 'qcurve'
#             depending on what off-curves preceded it.
#   'curve' — cubic control point (off-curve in geometric terms).
#             A cubic segment in TR is laid out [on, curve, curve, on].
#   'off'   — quadratic control point. TT/qcurve only.
#   'move'  — open-contour start.
#
# UFO has a different model: the on-curve point at the END of a segment
# carries the segmentType ('line', 'curve', 'qcurve'); intermediate
# off-curve points have segmentType=None and are not labelled cubic vs
# quadratic — that's inferred from the segmentType of the on-curve they
# precede.
#
# So conversion is contextual, not a flat lookup. See _draw_layer and
# _TrContourPen below.


# - Helpers -----------------------------
def _warn(msg, verbose=True):
	if verbose:
		print('[ufo] WARN: {}'.format(msg), file=sys.stderr)


# - TR lib bindings ---------------------
# All UFO-specific lib knowledge lives here. TR core objects are kept format-
# agnostic: this module is the only place that knows which TR attributes map
# to which UFO lib keys, and how. To add a new TR-only field that should
# round-trip through UFO, add an entry to LIB_BINDINGS or wire a new helper
# in collect_*_lib / apply_*_lib.

TR_LIB_PREFIX  = 'com.typerig.'
TR_LIB_VERSION = 1  # bump when the schema below changes

# Public UFO lib keys we honour
UFO_LIB_KEY_MARK_COLOR     = 'public.markColor'
# TR-namespaced lib keys
TR_LIB_KEY_VERSION         = TR_LIB_PREFIX + 'lib-version'
TR_LIB_KEY_FAMILY_STYLE    = TR_LIB_PREFIX + 'familyStyleName'
TR_LIB_KEY_LAYER_STEMS     = TR_LIB_PREFIX + 'layer-stems'      # glyph lib: {layer_name: [stx, sty]}
TR_LIB_KEY_CONTOUR_KINDS   = TR_LIB_PREFIX + 'contour-kinds'    # glyph lib: ['bezier'|'hobby', ...]

class LibField(object):
	'''One declarative binding for a TR attribute ↔ UFO lib key.

	Used for the simple direct-attribute cases (one attribute, one plist
	value, same scope). For aggregate fields that collect across multiple
	sub-objects (per-layer stems on a glyph, per-contour kinds), use a
	hand-written entry in collect_*_lib / apply_*_lib instead.

	Args:
		attr (str)         : TR attribute name on the bound object
		key (str)          : key suffix appended after TR_LIB_PREFIX. If None,
		                     defaults to `attr`. Ignored when `standard_key`
		                     is set.
		standard_key (str) : full UFO public key (e.g. "public.markColor")
		                     used instead of the TR-namespaced one.
		to_plist (callable): (tr_value) → plist_value. Identity if None.
		from_plist (callable): (plist_value) → tr_value. Identity if None.
		skip_if (callable) : (tr_value) → bool; True = don't write this entry.
		                     Default: skip when value is None/empty.
	'''
	__slots__ = ('attr', 'key', 'to_plist', 'from_plist', 'skip_if')

	def __init__(self, attr, key=None, standard_key=None,
	             to_plist=None, from_plist=None, skip_if=None):
		self.attr = attr
		if standard_key:
			self.key = standard_key
		else:
			self.key = TR_LIB_PREFIX + (key or attr)
		self.to_plist   = to_plist   or (lambda v: v)
		self.from_plist = from_plist or (lambda v: v)
		self.skip_if    = skip_if    or (lambda v: v is None or v == '' or v == [] or v == {})


# Bindings grouped by the TR class they read from / write to. The collectors
# below walk these; adding a new direct field is a one-line entry here.
LIB_BINDINGS = {
	Glyph: [
		LibField('mark',
		         standard_key=UFO_LIB_KEY_MARK_COLOR,
		         to_plist=lambda v: _mark_hex_to_color_str(v),
		         from_plist=lambda v: _mark_color_str_to_hex(v),
		         skip_if=lambda v: not v),
	],
	# Layer/Contour/Node aggregates handled in collect_glyph_lib /
	# apply_glyph_lib_to_layer (they fold into the GLYPH lib because UFO has
	# no native lib slot below the glyph level).
}


def _mark_hex_to_color_str(hex_str):
	'''TR Glyph.mark hex (#RRGGBB) → UFO public.markColor (floats).
	Returns None when the input isn't a clean hex string — collectors skip
	those entries.'''
	if not hex_str or not hex_str.startswith('#'):
		return None

	body = hex_str.lstrip('#')
	if len(body) != 6:
		return None
	try:
		r = int(body[0:2], 16) / 255.0
		g = int(body[2:4], 16) / 255.0
		b = int(body[4:6], 16) / 255.0
	except ValueError:
		return None
	return '{:g},{:g},{:g},1'.format(r, g, b)


def _mark_color_str_to_hex(color_str):
	'''UFO public.markColor (r,g,b[,a]) → TR mark hex.'''
	if not color_str:
		return None

	parts = [p.strip() for p in str(color_str).split(',')]

	if len(parts) < 3:
		return None

	try:
		r = float(parts[0])
		g = float(parts[1])
		b = float(parts[2])
	except ValueError:
		return None

	# Clamp [0,1] → 0..255
	def _to_byte(v):
		v = max(0.0, min(1.0, v))
		return int(round(v * 255))

	return '#{:02X}{:02X}{:02X}'.format(_to_byte(r), _to_byte(g), _to_byte(b))


# - Lib collectors / scatterers --------
# Walk LIB_BINDINGS plus the hand-written aggregate cases. Only this module
# knows the UFO lib shape; TR core objects stay format-pure.

def _apply_direct_bindings_to(target_obj, source_obj, lib_dict):
	'''Read TR attributes from `source_obj` via LIB_BINDINGS[type(source_obj)]
	and merge their plist forms into `lib_dict`.'''
	bindings = LIB_BINDINGS.get(type(source_obj), [])
	for field in bindings:
		raw = getattr(source_obj, field.attr, None)
		if field.skip_if(raw):
			continue
		plist_val = field.to_plist(raw)
		if plist_val is None:
			continue
		lib_dict[field.key] = plist_val


def _scatter_direct_bindings_from(target_obj, lib_dict):
	'''Apply LIB_BINDINGS[type(target_obj)] entries from `lib_dict` onto
	`target_obj`.'''
	bindings = LIB_BINDINGS.get(type(target_obj), [])
	for field in bindings:
		if field.key not in lib_dict:
			continue
		tr_val = field.from_plist(lib_dict[field.key])
		if tr_val is None:
			continue
		setattr(target_obj, field.attr, tr_val)


def collect_glyph_lib(glyph, font, is_default_master):
	'''Build the UFO glyph-lib dict for one TR Glyph.

	Direct-attribute bindings (e.g. mark) write on every UFO so the value
	survives even if a foreign tool only opens one master. Aggregate
	cross-layer data (stems map, contour kinds) only goes on the DEFAULT
	master's UFO — those are TR-flavoured and only matter to TR-aware
	consumers.
	'''
	lib = {}

	_apply_direct_bindings_to(lib, glyph, lib)

	if is_default_master:
		# Per-layer stems → {layer_name: [stx, sty]}
		stems_map = {}
		for lyr in glyph.layers:
			if getattr(lyr, 'has_stems', False):
				stems_map[lyr.name] = [lyr.stx, lyr.sty]
		if stems_map:
			lib[TR_LIB_KEY_LAYER_STEMS] = stems_map

		# Per-contour kinds — only emit when at least one is non-bezier;
		# bezier is the default and not worth the noise.
		first_layer = glyph.layers[0] if glyph.layers else None
		if first_layer is not None:
			kinds = []
			has_non_bezier = False
			for shape in first_layer.shapes:
				if shape.is_component:
					continue
				for contour in shape.contours:
					kind = getattr(contour, 'kind', 'bezier')
					kinds.append(kind)
					if kind != 'bezier':
						has_non_bezier = True
			if has_non_bezier:
				lib[TR_LIB_KEY_CONTOUR_KINDS] = kinds

	return lib


def apply_glyph_lib(glyph, default_layer, lib_dict):
	'''Scatter UFO glyph-lib data back onto a TR Glyph and its default layer.

	Called once per glyph with the LIB read from the default-master UFO's
	default-layer .glif. Per-layer entries are routed to the right TR layer.
	'''
	if not lib_dict:
		return

	# Direct attribute bindings (mark, …)
	_scatter_direct_bindings_from(glyph, lib_dict)

	# Per-layer stems
	stems_map = lib_dict.get(TR_LIB_KEY_LAYER_STEMS)
	if isinstance(stems_map, dict):
		for layer_name, stems in stems_map.items():
			lyr = glyph.layer(layer_name)
			if lyr is None:
				continue
			if isinstance(stems, (list, tuple)) and len(stems) == 2:
				lyr.stems = (stems[0], stems[1])

	# Per-contour kinds (applied to every layer so structure stays consistent)
	kinds = lib_dict.get(TR_LIB_KEY_CONTOUR_KINDS)
	if isinstance(kinds, list):
		for lyr in glyph.layers:
			i = 0
			for shape in lyr.shapes:
				if shape.is_component:
					continue
				for contour in shape.contours:
					if i < len(kinds):
						contour.kind = kinds[i]
					i += 1


def collect_font_lib(font):
	'''Build the UFO font-lib dict for the default-master UFO.

	Stores the TR lib-version stamp + family-level styleName (which the
	per-master UFOs override on their fontinfo).
	'''
	lib = {TR_LIB_KEY_VERSION: TR_LIB_VERSION}
	return lib


def read_family_style_name(lib_dict):
	'''Pull the family-level styleName from a font lib.'''
	if not lib_dict:
		return None
	return lib_dict.get(TR_LIB_KEY_FAMILY_STYLE)


def _guideline_to_dict(g):
	'''TR Guideline → UFO guideline data dict.'''
	d = {}
	if g.x is not None: d['x'] = g.x
	if g.y is not None: d['y'] = g.y
	if g.angle is not None: d['angle'] = g.angle
	if g.name: d['name'] = g.name
	if g.color: d['color'] = g.color
	if g.identifier: d['identifier'] = g.identifier
	return d


def _dict_to_guideline(d):
	'''UFO guideline data dict → TR Guideline.'''
	return Guideline(
		x          = d.get('x'),
		y          = d.get('y'),
		angle      = d.get('angle'),
		name       = d.get('name'),
		color      = d.get('color'),
		identifier = d.get('identifier'),
	)


def _anchor_to_dict(a):
	'''TR Anchor → UFO anchor data dict.'''
	d = {'x': a.x, 'y': a.y, 'name': a.name or ''}
	if getattr(a, 'color', None):
		d['color'] = a.color
	if getattr(a, 'identifier', None):
		d['identifier'] = a.identifier
	return d


def _dict_to_anchor(d, verbose=True):
	'''UFO anchor data dict → TR Anchor. Drops color/identifier with a warning.'''
	if 'color' in d or 'identifier' in d:
		_warn('anchor "{}" has color/identifier; not modelled in TR'.format(d.get('name', '')), verbose)

	return Anchor(
		x    = float(d.get('x', 0)),
		y    = float(d.get('y', 0)),
		name = d.get('name', '') or '',
	)


# - PointPen helpers --------------------
class _RawPoint(object):
	'''A single point recorded by the pen before TR-type assignment.'''
	__slots__ = ('x', 'y', 'segmentType', 'smooth', 'name')

	def __init__(self, x, y, segmentType, smooth, name):
		self.x = x
		self.y = y
		self.segmentType = segmentType
		self.smooth = smooth
		self.name = name


class _TrContourPen(object):
	'''Minimal PointPen that builds TR Contour / component shapes.

	UFO → TR conversion is contextual: an off-curve point (segmentType=None)
	is cubic (TR 'curve') or quadratic (TR 'off') depending on what kind of
	on-curve segment it precedes. We buffer raw points in beginPath/addPoint
	and resolve TR node types at endPath time once the full contour is known.
	'''
	def __init__(self):
		self.shapes = []				# [Shape, ...]
		self._raw = None
		self._warned_qcurve = False

	def beginPath(self, identifier=None):
		self._raw = []

	def addPoint(self, pt, segmentType=None, smooth=False, name=None,
	             identifier=None, **kwargs):
		if segmentType == 'qcurve' and not self._warned_qcurve:
			print('[ufo] WARN: qcurve points found; treating as cubic curves',
			      file=sys.stderr)
			self._warned_qcurve = True

		self._raw.append(_RawPoint(
			float(pt[0]), float(pt[1]),
			segmentType,
			bool(smooth),
			name or '',
		))

	def endPath(self):
		raw = self._raw or []
		self._raw = None

		# Open contour: a UFO open contour begins with segmentType='move'.
		# Closed: every off-curve run wraps around in the point sequence.
		is_open = bool(raw) and raw[0].segmentType == 'move'

		# Decide TR node type for each off-curve point by looking ahead to
		# the next on-curve and using its segmentType:
		#   next on-curve 'curve'           → TR 'curve' (cubic control)
		#   next on-curve 'qcurve'          → TR 'off'   (TT control)
		#   no following on-curve in run    → 'curve' (default to cubic)
		n = len(raw)
		tr_types = [None] * n

		for i, rp in enumerate(raw):
			if rp.segmentType in ('line', 'curve', 'qcurve'):
				tr_types[i] = 'on'
			elif rp.segmentType == 'move':
				tr_types[i] = 'move'
			elif rp.segmentType is None:
				# Walk forward (with wrap-around for closed contours) until
				# we hit an on-curve. Its segmentType decides cubic vs TT.
				j = i + 1
				steps = 0
				next_seg = None
				while steps < n:
					if not is_open:
						idx = j % n
					else:
						idx = j
						if idx >= n:
							break
					s = raw[idx].segmentType
					if s in ('line', 'curve', 'qcurve', 'move'):
						next_seg = s
						break
					j += 1
					steps += 1

				if next_seg == 'qcurve':
					tr_types[i] = 'off'
				else:
					tr_types[i] = 'curve'

		# Build TR Nodes
		nodes = []
		for rp, ttype in zip(raw, tr_types):
			nodes.append(Node(rp.x, rp.y,
			                  type=ttype,
			                  smooth=rp.smooth,
			                  name=rp.name))

		# UFO closed contours canonically start ON an on-curve point. TR's
		# cubic-segment ordering expects [on, curve, curve, on, ...]: the two
		# control points come *after* their segment's start on-curve and
		# *before* its end on-curve. UFO emits [on(curve-end), off, off,
		# on(curve-end), off, off, ...] where the leading on-curve carries
		# segmentType='curve' (it's the END of a segment whose controls wrap
		# around to the end of the array). We need to rotate so that any
		# trailing off-curves move to the front to sit before their owning
		# on-curve in TR ordering. Equivalently: rotate so the first node
		# is an on-curve whose segmentType is 'line' (or 'move'), or an
		# on-curve preceded by no off-curves.
		if not is_open and nodes:
			# Find an on-curve whose preceding node is also on-curve (or
			# there are no off-curves at all). That's the natural TR start.
			start = 0
			count = len(nodes)
			for i in range(count):
				if nodes[i].type == 'on':
					prev = nodes[(i - 1) % count]
					if prev.type == 'on':
						start = i
						break
			else:
				# All on-curves are preceded by off-curves → contour is a
				# pure curve loop. Start at the first on-curve.
				for i in range(count):
					if nodes[i].type == 'on':
						start = i
						break

			if start:
				nodes = nodes[start:] + nodes[:start]

		contour = Contour(closed=not is_open)
		contour.data = nodes
		for n_ in nodes:
			n_.parent = contour

		shape = Shape([contour])
		self.shapes.append(shape)

	def addComponent(self, baseGlyphName, transformation, identifier=None, **kwargs):
		shape = Shape(component=baseGlyphName)
		# UFO transformation is a 6-tuple (xx, xy, yx, yy, dx, dy)
		try:
			from typerig.core.objects.transform import Transform
			shape.transform = Transform(*transformation)
		except Exception:
			pass
		self.shapes.append(shape)


def _tr_to_ufo_segment_types(contour_nodes, is_closed):
	'''Return a list of UFO segmentTypes parallel to `contour_nodes`.

	For each TR node, determine the UFO segmentType:
	- TR 'move'   → 'move'
	- TR 'curve'  → None    (cubic offcurve)
	- TR 'off'    → None    (quadratic offcurve)
	- TR 'on'     → 'line', 'curve', or 'qcurve' depending on the run of
	                preceding off-curve types (looking back with wrap for
	                closed contours).
	'''
	n = len(contour_nodes)
	out = [None] * n

	for i, node in enumerate(contour_nodes):
		if node.type == 'move':
			out[i] = 'move'
			continue
		if node.type in ('curve', 'off'):
			out[i] = None		# offcurve
			continue

		# TR 'on'. Look back for any off-curve run that ends at this point.
		j = (i - 1) % n if is_closed else (i - 1)
		seen_cubic = False
		seen_tt    = False
		steps = 0
		while steps < n and j >= 0:
			prev = contour_nodes[j]
			if prev.type == 'curve':
				seen_cubic = True
			elif prev.type == 'off':
				seen_tt = True
			else:
				break
			j = (j - 1) % n if is_closed else (j - 1)
			steps += 1

		if seen_tt and not seen_cubic:
			out[i] = 'qcurve'
		elif seen_cubic:
			out[i] = 'curve'
		else:
			out[i] = 'line'

	return out


def _draw_layer(tr_layer, pen):
	'''Draw a TR Layer's shapes into a UFO PointPen.

	For closed cubic contours TR uses [on, curve, curve, on, curve, curve, ...]
	ordering (controls follow their start on-curve). UFO closed contours
	use [..., off, off, on(curve-end), off, off, on(curve-end), ...] where
	the on-curve at the END of the segment carries segmentType='curve'.
	We emit the same node sequence; segmentType assignment via
	_tr_to_ufo_segment_types handles the wrap-around lookback so the first
	on-curve gets 'curve' when the LAST nodes of the contour are its
	controls.
	'''
	for shape in tr_layer.shapes:
		if shape.is_component:
			t = shape.transform
			try:
				transformation = (t[0], t[1], t[2], t[3], t[4], t[5])
			except (TypeError, IndexError):
				transformation = (1, 0, 0, 1, 0, 0)
			pen.addComponent(shape.component, transformation)
			continue

		for contour in shape.contours:
			if getattr(contour, 'kind', 'bezier') == 'hobby':
				_warn('hobby contour in glyph layer "{}" — skipped (TR-only)'
				      .format(tr_layer.name), True)
				continue

			nodes = list(contour.nodes)
			is_closed = bool(contour.closed) and not (nodes and nodes[0].type == 'move')
			segments = _tr_to_ufo_segment_types(nodes, is_closed)

			pen.beginPath()
			for node, seg in zip(nodes, segments):
				pen.addPoint((node.x, node.y),
				             segmentType=seg,
				             smooth=bool(getattr(node, 'smooth', False)),
				             name=(getattr(node, 'name', None) or None))
			pen.endPath()


# - Glyph data carriers -----------------
class _GlyphLayerData(object):
	'''Carrier passed to writeGlyphToString / GlyphSet.writeGlyph.

	glifLib looks for these attributes on the object: width, height,
	unicodes, note, lib, image, guidelines, anchors. We expose only
	what TR knows about. drawPoints emits outline + component data.
	'''
	def __init__(self, tr_glyph, tr_layer, font, is_default_layer,
	             is_default_master=False, verbose=True):
		self.width  = float(tr_layer.advance_width)
		self.height = float(tr_layer.advance_height)
		self.lib    = {}

		# Anchors live on every layer in TR; same in UFO 3.
		self.anchors = [_anchor_to_dict(a) for a in tr_layer.anchors]

		# Layer guidelines always belong to the layer.
		guidelines = [_guideline_to_dict(g) for g in tr_layer.guidelines]

		if is_default_layer:
			# Unicodes, note and glyph-level guidelines live on the
			# default layer in UFO (UFO doesn't have a glyph-level
			# concept separate from its default-layer glif).
			unicodes = font.encoding.unicodes(tr_glyph.name) or list(tr_glyph.unicodes or [])
			self.unicodes = [int(u) for u in unicodes if u is not None]

			if tr_glyph.note:
				self.note = tr_glyph.note

			for g in (tr_glyph.guidelines or []):
				guidelines.append(_guideline_to_dict(g))

			# Glyph-scope TR-namespaced + public lib entries (mark, stems,
			# contour kinds, …). Cross-layer aggregates only land on the
			# default master's UFO; direct attribute bindings (mark) write
			# on every master so single-UFO consumers still see them.
			self.lib.update(collect_glyph_lib(tr_glyph, font, is_default_master))

		self.guidelines = guidelines
		self._tr_layer = tr_layer
		self._verbose  = verbose

	def drawPoints(self, pen):
		_draw_layer(self._tr_layer, pen)


# - Info conversion ---------------------
def _tr_info_to_ufo(tr_info, tr_metrics):
	'''Build a SimpleNamespace UFO info object from TR FontInfo + FontMetrics.'''
	ns = SimpleNamespace()

	for tr_attr, ufo_key in TR_TO_UFO_INFO.items():
		val = getattr(tr_info, tr_attr, None)
		if val is None or val == '':
			continue

		if ufo_key in UFO_INFO_INT_FIELDS:
			try:
				val = int(val)
			except (TypeError, ValueError):
				continue
		elif ufo_key in UFO_INFO_FLOAT_FIELDS:
			try:
				val = float(val)
			except (TypeError, ValueError):
				continue

		setattr(ns, ufo_key, val)

	# Version string → versionMajor / versionMinor
	version = getattr(tr_info, 'version', None)
	if version:
		try:
			major, _, minor = str(version).partition('.')
			ns.versionMajor = int(major) if major else 0
			ns.versionMinor = int(minor) if minor else 0
		except ValueError:
			pass

	# Metrics fields
	if tr_metrics is not None:
		ns.unitsPerEm = int(tr_metrics.upm)
		ns.ascender   = float(tr_metrics.ascender)
		ns.descender  = float(tr_metrics.descender)
		ns.xHeight    = float(tr_metrics.x_height)
		ns.capHeight  = float(tr_metrics.cap_height)
		ns.openTypeOS2TypoLineGap = int(tr_metrics.line_gap)

	return ns


def _ufo_info_to_tr(ufo_info):
	'''Build a TR FontInfo + FontMetrics pair from a UFO info object.'''
	info = FontInfo()
	for ufo_key, tr_attr in UFO_TO_TR_INFO.items():
		val = getattr(ufo_info, ufo_key, None)
		if val is None:
			continue
		setattr(info, tr_attr, val)

	major = getattr(ufo_info, 'versionMajor', None)
	minor = getattr(ufo_info, 'versionMinor', None)
	if major is not None or minor is not None:
		info.version = '{}.{:03d}'.format(int(major or 0), int(minor or 0))

	metrics = FontMetrics(
		upm        = int(getattr(ufo_info, 'unitsPerEm', 1000) or 1000),
		ascender   = int(getattr(ufo_info, 'ascender',   800)  or 800),
		descender  = int(getattr(ufo_info, 'descender', -200)  or -200),
		x_height   = int(getattr(ufo_info, 'xHeight',    500)  or 500),
		cap_height = int(getattr(ufo_info, 'capHeight',  700)  or 700),
		line_gap   = int(getattr(ufo_info, 'openTypeOS2TypoLineGap', 0) or 0),
	)

	return info, metrics


# - Designspace -------------------------
def _designspace_path_for(ufo_path):
	'''Sibling .designspace next to a .ufo path.'''
	base, _ = os.path.splitext(ufo_path)
	return base + '.designspace'


def _safe_filename(name):
	'''Make a filesystem-safe filename fragment from a master/layer name.'''
	out = []
	for ch in str(name):
		if ch.isalnum() or ch in ('-', '_', '.'):
			out.append(ch)
		else:
			out.append('_')
	return ''.join(out) or 'master'


def _read_designspace_axes(doc):
	axes = []
	for ad in doc.axes:
		axes.append(Axis(
			name    = ad.name,
			tag     = ad.tag,
			minimum = ad.minimum,
			default = ad.default,
			maximum = ad.maximum,
		))
	return axes


def _read_designspace_instances(doc):
	out = []
	for id_ in doc.instances:
		out.append(Instance(
			name     = id_.name or id_.styleName or 'Instance',
			location = dict(id_.location or {}),
		))
	return Instances(out)


# - Converter ---------------------------
class UfoConverter(object):
	'''Bidirectional UFO 3 ↔ Font converter.

	Two output layouts are supported:

	1. **designspace + one UFO per master** (preferred, standard layout)
	   - tr_to_designspace(font, ds_path) → writes ds_path plus a sibling
	     <stem>-<MasterName>.ufo per master.
	   - designspace_to_tr(ds_path) → loads each source UFO, pulls the
	     layer named by source.layerName (default layer if None), and
	     assembles a TR Font with one TR layer per master.

	2. **single multi-layer UFO** (compact, also valid UFO 3)
	   - tr_to_ufo(font, ufo_path) writes everything into one .ufo with
	     a UFO layer per master, plus an optional sibling .designspace.
	   - ufo_to_tr(ufo_path) reads it back the same way.

	to_ufo(font, path) / to_tr(path) dispatch on the path's extension —
	.designspace → layout (1), .ufo → layout (2).
	'''

	def __init__(self, verbose=True):
		self.verbose = verbose

	# -- Dispatch -----------------------
	def to_ufo(self, font, path):
		'''Write `font` choosing layout from `path` extension.'''
		ext = os.path.splitext(path)[1].lower()
		if ext == '.designspace':
			return self.tr_to_designspace(font, path)
		return self.tr_to_ufo(font, path)

	def to_tr(self, path):
		'''Read a TR Font from a .designspace or .ufo path.'''
		ext = os.path.splitext(path.rstrip(os.sep))[1].lower()
		if ext == '.designspace' or (os.path.isfile(path) and path.endswith('.designspace')):
			return self.designspace_to_tr(path)
		return self.ufo_to_tr(path)

	# -- TR → designspace (preferred) ---
	def tr_to_designspace(self, font, ds_path):
		'''Write `font` as a .designspace + one UFO per master.

		UFOs are named "<stem>-<MasterName>.ufo" next to the .designspace
		(e.g. mytypeface.designspace alongside mytypeface-Light.ufo,
		mytypeface-Black.ufo). Each UFO holds a single default layer
		containing that master's glyphs. Font-level groups, kerning and
		features are written to every UFO so each remains a complete UFO.
		'''
		ds_path = os.path.abspath(ds_path)
		ds_dir  = os.path.dirname(ds_path)
		stem    = os.path.splitext(os.path.basename(ds_path))[0]

		if not os.path.isdir(ds_dir):
			os.makedirs(ds_dir, exist_ok=True)

		masters = list(font.masters.data)
		if not masters:
			# No masters declared — synthesize one from the first layer
			# present on any glyph.
			first_layer = None
			for g in font.glyphs:
				if g.layers:
					first_layer = g.layers[0].name
					break
			first_layer = first_layer or 'Regular'
			masters = [Master(
				name=first_layer, layer_name=first_layer,
				location={}, is_default=True,
			)]

		default_master = None
		for m in masters:
			if m.is_default:
				default_master = m
				break
		if default_master is None:
			default_master = masters[0]

		doc = DesignSpaceDocument()

		for axis in font.axes:
			ad = AxisDescriptor()
			ad.name    = axis.name
			ad.tag     = axis.tag
			ad.minimum = float(axis.minimum)
			ad.default = float(axis.default)
			ad.maximum = float(axis.maximum)
			doc.addAxis(ad)

		written_ufos = []
		for master in masters:
			ufo_filename = '{}-{}.ufo'.format(stem, _safe_filename(master.name))
			ufo_path     = os.path.join(ds_dir, ufo_filename)
			self._write_master_ufo(font, master, ufo_path)
			written_ufos.append(ufo_filename)

			sd = SourceDescriptor()
			sd.filename   = ufo_filename
			sd.path       = ufo_path
			sd.familyName = font.info.family_name
			sd.styleName  = master.name
			sd.name       = master.name
			# Each UFO uses its default layer — no layerName needed.
			sd.location   = dict(master.location)
			doc.addSource(sd)

		for inst in font.instances.data:
			id_ = InstanceDescriptor()
			id_.familyName = font.info.family_name
			id_.styleName  = inst.name
			id_.name       = inst.name
			id_.location   = dict(inst.location)
			doc.addInstance(id_)

		doc.write(ds_path)
		return ds_path

	def _write_master_ufo(self, font, master, ufo_path):
		'''Write one UFO containing a single master's glyph layer.'''
		# UFOWriter treats an existing folder as edit-in-place and requires
		# a valid layercontents.plist. Wipe any pre-existing target so we
		# always start clean.
		if os.path.isdir(ufo_path):
			shutil.rmtree(ufo_path)
		writer = UFOWriter(ufo_path, formatVersion=UFOFormatVersion.FORMAT_3_0)

		# fontinfo: clone the font-level info, then specialize styleName per
		# master. The family-level style_name ("Variable" / "MM" / etc.) is
		# preserved in lib.plist so designspace_to_tr can restore it.
		ufo_info = _tr_info_to_ufo(font.info, font.metrics)
		original_style = getattr(ufo_info, 'styleName', None)
		ufo_info.styleName = master.name
		writer.writeInfo(ufo_info)

		# Font lib: schema version stamp + family-level styleName (only on
		# default master, where round-trips read it from).
		font_lib = collect_font_lib(font)
		if master.is_default and original_style and original_style != master.name:
			font_lib[TR_LIB_KEY_FAMILY_STYLE] = original_style
		if font_lib:
			writer.writeLib(font_lib)

		if font.groups and len(font.groups.data):
			writer.writeGroups({g.name: list(g.members) for g in font.groups.data})

		if font.kerning and len(font.kerning.data):
			writer.writeKerning({(p.first, p.second): int(p.value)
			                     for p in font.kerning.pairs})

		if font.features:
			writer.writeFeatures(font.features)

		# Single default-layer glyph set; pull each glyph's `master.layer_name`
		gs = writer.getGlyphSet(defaultLayer=True)

		for glyph in font.glyphs:
			tr_layer = glyph.layer(master.layer_name)
			if tr_layer is None:
				# Sparse master — UFO convention is to omit the glyph.
				continue
			name = glyph.name
			if not isinstance(name, str):
				_warn('glyph has non-string name {!r}; coercing to str'
				      .format(name), self.verbose)
				name = str(name)
			data = _GlyphLayerData(glyph, tr_layer, font,
			                       is_default_layer=True,
			                       is_default_master=bool(master.is_default),
			                       verbose=self.verbose)
			gs.writeGlyph(name, data, data.drawPoints)

		gs.writeContents()
		# The default UFO layer is the one we just wrote. ufoLib registers
		# it under the standard "public.default" name when defaultLayer=True.
		writer.writeLayerContents(['public.default'])
		writer.close()

	# -- designspace → TR ---------------
	def designspace_to_tr(self, ds_path):
		'''Read a .designspace and assemble a TR Font.

		Each source UFO contributes one TR layer per glyph — the layer
		whose name is `source.layerName`, or the UFO's default layer if
		`layerName` is unset.

		Font-level data (info, metrics, groups, kerning, features) is
		taken from the default master's UFO.
		'''
		ds_path = os.path.abspath(ds_path)
		if not os.path.isfile(ds_path):
			raise FileNotFoundError('No such designspace file: {}'.format(ds_path))

		doc    = DesignSpaceDocument.fromfile(ds_path)
		ds_dir = os.path.dirname(ds_path)

		axes      = _read_designspace_axes(doc)
		instances = _read_designspace_instances(doc)

		default_loc = {a.name: a.default for a in axes}

		# Resolve a source path against the .designspace folder
		def _resolve(sd):
			if sd.path and os.path.isabs(sd.path) and os.path.exists(sd.path):
				return sd.path
			if sd.filename:
				p = os.path.normpath(os.path.join(ds_dir, sd.filename))
				if os.path.exists(p):
					return p
			if sd.path:
				p = os.path.normpath(os.path.join(ds_dir, sd.path))
				if os.path.exists(p):
					return p
			raise FileNotFoundError(
				'Could not resolve UFO for source: {}'.format(sd.filename or sd.path))

		sources = list(doc.sources)
		if not sources:
			raise ValueError('Designspace has no <source> entries: {}'.format(ds_path))

		# Pick a default source
		default_source = None
		for sd in sources:
			if (sd.location or {}) == default_loc:
				default_source = sd
				break
		if default_source is None:
			default_source = sources[0]

		# Build masters + per-source TR layers
		masters_list   = []
		# {glyph_name: ordered list of TR Layer objects, parallel to masters_list}
		glyph_layers   = {}
		glyph_extras   = {}			# {glyph_name: extras dict from default UFO}
		glyph_order    = []

		default_path = _resolve(default_source)
		default_reader_holder = {'reader': None, 'info': None,
		                         'groups': {}, 'kerning': {}, 'features': ''}

		for sd in sources:
			ufo_path = _resolve(sd)
			reader = UFOReader(ufo_path, validate=False)

			if reader.formatVersionTuple[0] < 3:
				reader.close()
				raise ValueError(
					'UFO at {} is format {} — UFO 3 required'
					.format(ufo_path, reader.formatVersion))

			master_name = sd.name or sd.styleName or sd.layerName or os.path.basename(ufo_path)
			# Layer name inside the UFO. If unset, use the default layer.
			ufo_layer_name = sd.layerName or reader.getDefaultLayerName()
			# TR-side layer name: keep master name so font.layers are addressable.
			tr_layer_name  = master_name

			is_default = (ufo_path == default_path)
			masters_list.append(Master(
				name       = master_name,
				layer_name = tr_layer_name,
				location   = dict(sd.location or {}),
				is_default = is_default,
			))

			# Pull info/groups/kerning/features once from the default master
			if is_default:
				info_ns = SimpleNamespace()
				reader.readInfo(info_ns)
				default_reader_holder['info']     = info_ns
				default_reader_holder['groups']   = reader.readGroups() or {}
				default_reader_holder['kerning']  = reader.readKerning() or {}
				default_reader_holder['features'] = reader.readFeatures() or ''
				default_reader_holder['lib']      = reader.readLib() or {}

			gs = reader.getGlyphSet(layerName=ufo_layer_name)

			for glyph_name in gs.keys():
				if glyph_name not in glyph_layers:
					glyph_layers[glyph_name] = {}
					glyph_order.append(glyph_name)

				receiver = SimpleNamespace()
				receiver.guidelines = []
				receiver.anchors    = []
				receiver.lib        = {}
				receiver.unicodes   = []
				receiver.note       = None
				receiver.width      = 0
				receiver.height     = 0

				pen = _TrContourPen()
				gs.readGlyph(glyph_name, glyphObject=receiver, pointPen=pen)

				tr_layer = Layer(
					name   = tr_layer_name,
					width  = float(getattr(receiver, 'width', 0) or 0),
					height = float(getattr(receiver, 'height', 0) or 0),
				)
				tr_layer.data = pen.shapes
				for sh in pen.shapes:
					sh.parent = tr_layer

				tr_layer.anchors    = [_dict_to_anchor(a, self.verbose)
				                       for a in (receiver.anchors or [])]
				tr_layer.guidelines = [_dict_to_guideline(g)
				                       for g in (receiver.guidelines or [])]

				glyph_layers[glyph_name][tr_layer_name] = tr_layer

				if is_default:
					glyph_extras[glyph_name] = receiver

			reader.close()

		# Default-layer glyph ordering: pull from the default master's UFO
		default_reader = UFOReader(default_path, validate=False)
		default_layer_name = default_source.layerName or default_reader.getDefaultLayerName()
		default_gs = default_reader.getGlyphSet(layerName=default_layer_name)
		default_glyph_names = list(default_gs.keys())
		default_reader.close()

		ordered_glyph_names = []
		for n in default_glyph_names:
			if n in glyph_layers:
				ordered_glyph_names.append(n)
		# Append any glyphs only found in non-default masters
		for n in glyph_order:
			if n not in ordered_glyph_names:
				ordered_glyph_names.append(n)

		# Assemble Glyphs
		master_layer_names_in_order = [m.layer_name for m in masters_list]
		default_master_layer_name = None
		for m in masters_list:
			if m.is_default:
				default_master_layer_name = m.layer_name
				break

		glyphs = []
		for glyph_name in ordered_glyph_names:
			layers_map = glyph_layers.get(glyph_name, {})
			ordered_tr_layers = [layers_map[ln] for ln in master_layer_names_in_order
			                     if ln in layers_map]

			glyph = Glyph(ordered_tr_layers, name=glyph_name)
			receiver = glyph_extras.get(glyph_name)
			if receiver is not None:
				if getattr(receiver, 'unicodes', None):
					glyph.unicodes = [int(u) for u in receiver.unicodes]
				if getattr(receiver, 'note', None):
					glyph.note = receiver.note
				if hasattr(receiver, 'image') and receiver.image:
					_warn('glyph "{}" image dropped (not modelled in TR)'
					      .format(glyph_name), self.verbose)

				# All TR-specific glyph-scope state lives in the .glif lib.
				default_layer = glyph.layer(default_master_layer_name) \
				                if default_master_layer_name else None
				apply_glyph_lib(glyph, default_layer,
				                getattr(receiver, 'lib', {}) or {})

			glyphs.append(glyph)

		# Font-level data from the default master
		info_ns = default_reader_holder['info'] or SimpleNamespace()
		tr_info, tr_metrics = _ufo_info_to_tr(info_ns)
		# Restore family-level styleName from default UFO's lib if stashed there
		default_lib = default_reader_holder.get('lib') or {}
		family_style = read_family_style_name(default_lib)
		if family_style:
			tr_info.style_name = family_style

		groups = Groups()
		for name, members in (default_reader_holder['groups'] or {}).items():
			groups.set(name, list(members))

		kerning = Kerning()
		for (first, second), value in (default_reader_holder['kerning'] or {}).items():
			kerning.add_pair(first, second, int(value))

		font = Font(
			glyphs,
			info      = tr_info,
			metrics   = tr_metrics,
			axes      = axes,
			masters   = Masters(masters_list),
			instances = instances,
			groups    = groups,
			kerning   = kerning,
			features  = default_reader_holder['features'] or '',
			encoding  = Encoding(),
		)

		return font

	# -- TR → single UFO (single-master shortcut) -----
	def tr_to_ufo(self, font, ufo_path):
		ufo_path = os.path.abspath(ufo_path)
		if os.path.isdir(ufo_path):
			shutil.rmtree(ufo_path)

		# Determine layer order from masters; fallback to layer names
		# present on the first glyph.
		layer_order = []
		default_layer = None

		if font.masters.data:
			for m in font.masters.data:
				if m.layer_name not in layer_order:
					layer_order.append(m.layer_name)
				if m.is_default and default_layer is None:
					default_layer = m.layer_name

		# Fill in any layers seen on glyphs but missing from masters
		for g in font.glyphs:
			for lyr in g.layers:
				if lyr.name not in layer_order:
					layer_order.append(lyr.name)

		if default_layer is None:
			default_layer = layer_order[0] if layer_order else 'public.default'

		# Force the default layer to the front (UFO convention)
		layer_order = [default_layer] + [n for n in layer_order if n != default_layer]

		writer = UFOWriter(ufo_path, formatVersion=UFOFormatVersion.FORMAT_3_0)

		# fontinfo.plist
		ufo_info = _tr_info_to_ufo(font.info, font.metrics)
		writer.writeInfo(ufo_info)

		# Font lib — schema version + passthroughs. Single-UFO layout, so
		# this IS the default master; family-level styleName is the same
		# as font.info.style_name and doesn't need stashing.
		font_lib = collect_font_lib(font)
		if font_lib:
			writer.writeLib(font_lib)

		# groups.plist
		if font.groups and len(font.groups.data):
			groups_dict = {g.name: list(g.members) for g in font.groups.data}
			writer.writeGroups(groups_dict)

		# kerning.plist
		if font.kerning and len(font.kerning.data):
			kerning_dict = {(p.first, p.second): int(p.value) for p in font.kerning.pairs}
			writer.writeKerning(kerning_dict)

		# features.fea
		if font.features:
			writer.writeFeatures(font.features)

		# Per-layer glyph sets
		ufo_layer_order = []
		for layer_name in layer_order:
			is_default = (layer_name == default_layer)
			gs = writer.getGlyphSet(layerName=layer_name, defaultLayer=is_default)
			ufo_layer_order.append(layer_name)

			for glyph in font.glyphs:
				tr_layer = glyph.layer(layer_name)
				if tr_layer is None:
					continue
				name = glyph.name
				if not isinstance(name, str):
					_warn('glyph has non-string name {!r}; coercing to str'
					      .format(name), self.verbose)
					name = str(name)
				data = _GlyphLayerData(glyph, tr_layer, font,
				                       is_default_layer=is_default,
				                       is_default_master=is_default,
				                       verbose=self.verbose)
				gs.writeGlyph(name, data, data.drawPoints)

			gs.writeContents()

		# Layer order list (default first)
		writer.writeLayerContents(ufo_layer_order)
		writer.close()

		# Sibling .designspace describing masters/axes/instances
		self._write_single_ufo_designspace(font, ufo_path)

		return ufo_path

	def _write_single_ufo_designspace(self, font, ufo_path):
		'''Sidecar .designspace for the single-UFO layout — each source
		references the same UFO with a different `layer`.'''
		if not font.axes and not font.masters.data:
			return None

		doc = DesignSpaceDocument()
		for axis in font.axes:
			ad = AxisDescriptor()
			ad.name    = axis.name
			ad.tag     = axis.tag
			ad.minimum = float(axis.minimum)
			ad.default = float(axis.default)
			ad.maximum = float(axis.maximum)
			doc.addAxis(ad)

		ufo_filename = os.path.basename(ufo_path)
		for master in font.masters.data:
			sd = SourceDescriptor()
			sd.filename   = ufo_filename
			sd.path       = ufo_path
			sd.familyName = font.info.family_name
			sd.styleName  = master.name
			sd.name       = master.name
			sd.layerName  = master.layer_name
			sd.location   = dict(master.location)
			doc.addSource(sd)

		for inst in font.instances.data:
			id_ = InstanceDescriptor()
			id_.familyName = font.info.family_name
			id_.styleName  = inst.name
			id_.name       = inst.name
			id_.location   = dict(inst.location)
			doc.addInstance(id_)

		ds_path = _designspace_path_for(ufo_path)
		doc.write(ds_path)
		return ds_path

	# -- single UFO → TR ---------------
	def ufo_to_tr(self, ufo_path):
		ufo_path = os.path.abspath(ufo_path)

		if not os.path.isdir(ufo_path):
			raise FileNotFoundError('Not a UFO folder: {}'.format(ufo_path))

		reader = UFOReader(ufo_path, validate=False)

		# Reject UFO 1 / UFO 2
		if reader.formatVersionTuple[0] < 3:
			raise ValueError(
				'UFO format version {} not supported. UFO 3 required.'
				.format(reader.formatVersion))

		# Font-level data
		info_ns = SimpleNamespace()
		reader.readInfo(info_ns)
		tr_info, tr_metrics = _ufo_info_to_tr(info_ns)

		groups_dict  = reader.readGroups()  or {}
		kerning_dict = reader.readKerning() or {}
		features     = reader.readFeatures() or ''

		groups = Groups()
		for name, members in groups_dict.items():
			groups.set(name, list(members))

		kerning = Kerning()
		for (first, second), value in kerning_dict.items():
			kerning.add_pair(first, second, int(value))

		# Layers
		layer_names    = list(reader.getLayerNames())
		default_layer  = reader.getDefaultLayerName()

		# Read every glyph in every layer; assemble per-name into TR Glyph.
		# Default layer first so name/unicode/note land on the canonical glyph.
		ordered_layers = [default_layer] + [n for n in layer_names if n != default_layer]

		# {glyph_name: {layer_name: (layer_obj, default_layer_extras)}}
		glyph_data = {}
		glyph_order = []

		for layer_name in ordered_layers:
			gs = reader.getGlyphSet(layerName=layer_name)
			is_default = (layer_name == default_layer)

			for glyph_name in gs.keys():
				if glyph_name not in glyph_data:
					glyph_data[glyph_name] = {}
					if is_default:
						glyph_order.append(glyph_name)

				receiver = SimpleNamespace()
				receiver.guidelines = []
				receiver.anchors    = []
				receiver.lib        = {}
				receiver.unicodes   = []
				receiver.note       = None
				receiver.width      = 0
				receiver.height     = 0

				pen = _TrContourPen()
				gs.readGlyph(glyph_name, glyphObject=receiver, pointPen=pen)

				tr_layer = Layer(
					name   = layer_name,
					width  = float(getattr(receiver, 'width', 0) or 0),
					height = float(getattr(receiver, 'height', 0) or 0),
				)
				tr_layer.data       = pen.shapes
				for sh in pen.shapes:
					sh.parent = tr_layer

				tr_layer.anchors    = [_dict_to_anchor(a, self.verbose)
				                       for a in (getattr(receiver, 'anchors', []) or [])]
				tr_layer.guidelines = [_dict_to_guideline(g)
				                       for g in (getattr(receiver, 'guidelines', []) or [])]

				glyph_data[glyph_name][layer_name] = {
					'layer':    tr_layer,
					'receiver': receiver,
					'default':  is_default,
				}

		# Also collect default-layer glyphs from other layers if not yet seen
		# (some UFOs are sparse — non-default layers may have glyphs missing
		# from the default layer).
		for layer_name in ordered_layers:
			if layer_name == default_layer:
				continue
			gs = reader.getGlyphSet(layerName=layer_name)
			for glyph_name in gs.keys():
				if glyph_name not in glyph_order:
					glyph_order.append(glyph_name)

		# Assemble Glyphs in default-layer-first order
		glyphs = []
		for glyph_name in glyph_order:
			layers_for_glyph = glyph_data.get(glyph_name, {})

			# Order the layers consistent with the global layer order
			ordered_tr_layers = []
			for ln in ordered_layers:
				if ln in layers_for_glyph:
					ordered_tr_layers.append(layers_for_glyph[ln]['layer'])

			# Pull glyph-level metadata from the default layer if present
			default_entry = layers_for_glyph.get(default_layer)
			receiver = default_entry['receiver'] if default_entry else None

			glyph = Glyph(ordered_tr_layers, name=glyph_name)

			if receiver is not None:
				if getattr(receiver, 'unicodes', None):
					glyph.unicodes = [int(u) for u in receiver.unicodes]
				if getattr(receiver, 'note', None):
					glyph.note = receiver.note
				if hasattr(receiver, 'image') and receiver.image:
					_warn('glyph "{}" image dropped (not modelled in TR)'
					      .format(glyph_name), self.verbose)

				# TR-namespaced + public lib entries — mark, layer-stems,
				# contour kinds, etc. UFO doesn't separate glyph-level vs
				# layer-level guidelines on disk, so glyph.guidelines stays
				# empty and the per-layer guidelines we already parsed
				# during the read pass remain in place.
				tr_default_layer = glyph.layer(default_layer)
				apply_glyph_lib(glyph, tr_default_layer,
				                getattr(receiver, 'lib', {}) or {})

			glyphs.append(glyph)

		# Read designspace sidecar (axes / masters / instances)
		ds_path = _designspace_path_for(ufo_path)
		axes      = []
		masters   = None
		instances = Instances()

		if os.path.isfile(ds_path):
			doc = DesignSpaceDocument.fromfile(ds_path)
			axes      = _read_designspace_axes(doc)
			instances = _read_designspace_instances(doc)
			default_loc = {a.name: a.default for a in axes}
			masters_list = []
			for sd in doc.sources:
				name       = sd.name or sd.styleName or sd.layerName or 'Master'
				layer_name = sd.layerName or name
				is_default = (sd.location or {}) == default_loc
				masters_list.append(Master(
					name       = name,
					layer_name = layer_name,
					location   = dict(sd.location or {}),
					is_default = is_default,
				))
			masters = Masters(masters_list)

		if masters is None:
			# No designspace — synthesize one master per layer
			masters_list = []
			for ln in ordered_layers:
				masters_list.append(Master(
					name       = ln,
					layer_name = ln,
					location   = {},
					is_default = (ln == default_layer),
				))
			masters = Masters(masters_list)

		# Build font
		font = Font(
			glyphs,
			info      = tr_info,
			metrics   = tr_metrics,
			axes      = axes,
			masters   = masters,
			instances = instances,
			groups    = groups,
			kerning   = kerning,
			features  = features,
			encoding  = Encoding(),
		)

		reader.close()
		return font
