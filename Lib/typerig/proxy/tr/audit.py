# MODULE: TypeRig / Proxy / TR / Audit
# NOTE: FontLab side of the .trfont round-trip audit
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# dump_fl(package) emits the SAME schema as core
# typerig.core.fileio.trfont_audit.dump_font(font), straight from the raw
# FontLab API. It deliberately does NOT go through the trGlyph/trLayer
# proxies: the audit exists to catch what those proxies lose, so it must
# not share their code paths (the eject bugs of 2026-11 were all silent
# getattr fallbacks inside the proxies).
#
# Two comparisons, two purposes:
#   GATE        dump_fl(source VFC)  vs dump_fl(round-tripped VFC)
#               convention-free: both sides are read the same way.
#   DIAGNOSTIC  dump_fl(source VFC)  vs dump_font(core Font read from .trfont)
#               localizes a loss to the eject direction. Two fields use FL
#               conventions here and may differ for that reason alone:
#               info fields that the core FontInfo does not carry yet.
#               Guides use one canonical form on both sides (canonical_guide).
#
# Usage inside FontLab (Python console, or the fontlab MCP run_python —
# mind its ~5 s per call: dump a subset with glyph_names=, or write files):
#   from typerig.proxy.tr import audit
#   d = audit.dump_fl(stage='a')                     # current font
#   audit.save_json(d, r'D:\tmp\basil_src_a.json')
#   lines = audit.eject_report(r'D:\tmp\rt', stage='a', glyph_names=['A', 'Aacute'])
# Plan: Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md

# - Dependencies ------------------------
import os
import json

import fontlab as fl6

from typerig.core.func.string import hue_to_hex
from typerig.core.fileio.trfont_audit import (
	_num, _str, _newlines, _stage_at_least, diff, dump_font, canonical_guide,
	dump_axis, dump_metrics, dump_value,
)

# - Init --------------------------------
__version__ = '0.1.0'

_MISSING = object()

# Core FontInfo attribute -> fg.info attribute (UFO fontinfo names).
# Verified to exist on fgFontInfo in FL9 (2026-11). `version` is composed
# from versionMajor/versionMinor (UFO convention: 1 / 2 -> "1.002").
INFO_MAP = {
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
# fg.info fields that are compared elsewhere or are volatile (own copy of
# the bridge's skip list, on purpose): version* -> info.version,
# unitsPerEm -> upm, ascender/descender/xHeight/capHeight -> per-master
# metrics, openTypeHeadModified -> rewritten by FontLab on every save.
_INFO_EXTRA_SKIP = {'versionMajor', 'versionMinor', 'unitsPerEm', 'ascender', 'descender',
                    'xHeight', 'capHeight', 'openTypeHeadModified', 'dict'}

_PACKAGE_FIELDS = ('tfn', 'tsn', 'psn', 'sgn', 'ffn', 'weight_value', 'width_value',
                   'underlinePosition_value', 'underlineThickness_value')

def _dump_info_extra(info, package=None):
	mapped = set(INFO_MAP.values())
	out = {}
	if package is not None:
		for attr in _PACKAGE_FIELDS:
			value = getattr(package, attr, None)
			if value is not None:
				out['com.fontlab.package.' + attr] = dump_value(value)
	for name in sorted(dir(info)):
		if name.startswith('_') or name in mapped or name in _INFO_EXTRA_SKIP:
			continue
		value = getattr(info, name, None)
		if callable(value) or value is None:
			continue
		out[name] = dump_value(value)
	return out

_NUMERIC_INFO = {'year', 'weight_class', 'width_class', 'italic_angle', 'underline_position', 'underline_thickness'}

# - Live reload (FontLab session) -------
# xmlio keeps a class registry that the core object modules fill at import.
# Reloading xmlio alone empties it and every <layer>/<shape>/... child is
# then silently skipped on read. Reload in this order instead.
RELOAD_ORDER = [
	'typerig.core.fileio.xmlio',
	'typerig.core.objects.node', 'typerig.core.objects.contour', 'typerig.core.objects.shape',
	'typerig.core.objects.anchor', 'typerig.core.objects.guideline', 'typerig.core.objects.layer',
	'typerig.core.objects.glyph', 'typerig.core.objects.metrics', 'typerig.core.objects.axis',
	'typerig.core.objects.master', 'typerig.core.objects.instance', 'typerig.core.objects.encoding',
	'typerig.core.objects.kern', 'typerig.core.objects.groups', 'typerig.core.objects.font',
	'typerig.core.fileio.trfont', 'typerig.core.fileio.trfont_audit',
	'typerig.proxy.tr.objects.guideline', 'typerig.proxy.tr.objects.node',
	'typerig.proxy.tr.objects.contour', 'typerig.proxy.tr.objects.shape',
	'typerig.proxy.tr.objects.anchor', 'typerig.proxy.tr.objects.layer',
	'typerig.proxy.tr.objects.glyph', 'typerig.proxy.tr.objects.font',
	'typerig.proxy.tr.audit',
]

def reload_typerig():
	'''Reload the trfont stack in dependency order (after editing the repo
	while FontLab is running). Re-import audit afterwards to get the new one.'''
	import sys, importlib
	for name in RELOAD_ORDER:
		if name in sys.modules:
			importlib.reload(sys.modules[name])
		else:
			importlib.import_module(name)

# - Helpers -----------------------------
def _package(package=None):
	return package if package is not None else fl6.flPackage(fl6.CurrentFont())

def _info_version(info):
	major = getattr(info, 'versionMajor', None)
	minor = getattr(info, 'versionMinor', None)
	if major is None:
		return ''
	return '{}.{:03d}'.format(int(major), int(minor or 0))

def _dump_info(info, problems):
	out = {}
	for attr in sorted(list(INFO_MAP) + ['version']):
		if attr == 'version':
			out[attr] = _info_version(info)
			continue
		value = getattr(info, INFO_MAP[attr], _MISSING)
		if value is _MISSING:
			problems.append('fg.info has no attribute {}'.format(INFO_MAP[attr]))
			value = None
		out[attr] = _num(value) if attr in _NUMERIC_INFO else _str(value)
	return out

def _qtransform(t):
	'''QTransform -> (xx, xy, yx, yy, dx, dy). Same order as core Transform:
	x' = m11*x + m21*y + dx ; y' = m12*x + m22*y + dy.'''
	return (_num(t.m11()), _num(t.m12()), _num(t.m21()), _num(t.m22()), _num(t.dx()), _num(t.dy()))

def _mark(hue):
	'''FL glyph mark is an int hue; 0 means "no mark".'''
	return '' if not hue else hue_to_hex(hue)

def _qline(line):
	return ((float(line.p1().x()), float(line.p1().y())), (float(line.p2().x()), float(line.p2().y())))

def _kern_side(obj):
	'''fgKerningObject -> "glyph" or "@class" (FL's own naming, not UFO's).
	obj.asTuple() -> (name, 'glyphMode' | 'groupMode'), as pFont uses it.'''
	name, mode = obj.asTuple()
	return '@' + _str(name) if mode == 'groupMode' else _str(name)

def _dump_layer(layer):
	shapes = []
	for shape in layer.shapes:
		data = shape.shapeData
		shapes.append({
			# The element name lives on shapeData; flShape.name is usually ''.
			'name':      _str(data.name if data is not None else shape.name),
			'transform': _qtransform(shape.transform),
			'contours':  [{
				'closed': bool(contour.closed),
				'nodes':  [(_num(n.x), _num(n.y), _str(n.type), bool(n.smooth), _str(n.name)) for n in contour.nodes()],
			} for contour in shape.contours],
		})

	return {
		'width':   _num(layer.advanceWidth),
		'height':  _num(layer.advanceHeight),
		'anchors': sorted((_str(a.name), _num(a.point.x()), _num(a.point.y())) for a in layer.anchors),
		# The line is extLinef (font space). Not .vector (a direction) and not
		# .center (can sit off the line for metric-offset guides).
		'guides':  sorted((canonical_guide(line=_qline(g.extLinef), name=g.name) for g in layer.guidelines), key=repr),
		'shapes':  shapes,
	}

class _Metrics(object):
	'''Read the current master's vertical metrics off an flPackage.'''
	def __init__(self, package):
		self.ascender   = package.ascender_value
		self.descender  = package.descender_value
		self.x_height   = package.xHeight_value
		self.cap_height = package.capsHeight_value
		self.line_gap   = package.lineGap_value

def _master_metrics(package, master):
	return dump_metrics(_Metrics(package))

def _axis_map(axis):
	'''flAxis.map -> [(user, design), ...]. None/empty in BasilMM; the
	shape of a populated map is unverified (Stage A note).'''
	m = axis.map
	if not m:
		return []
	try:
		return [(float(u), float(d)) for u, d in m]
	except (TypeError, ValueError):
		return [('unparsed', str(m))]

# - Dump --------------------------------
def dump_fl(package=None, stage='a', glyph_names=None, problems=None):
	'''Dump a live flPackage to the trfont_audit schema.

	Args:
		package      : flPackage; None -> CurrentFont()
		stage        : 'a' | 'b' | 'c' (cumulative field sets)
		glyph_names  : subset to dump (glyph_order still lists every glyph)
		problems     : optional list; API surprises are appended, not raised

	Font-level 'metrics' are the default master's; every master record
	carries its own metrics (FL keeps them per master).
	'''
	package = _package(package)
	problems = problems if problems is not None else []
	fg = package.fgPackage
	axes = list(package.axes)
	master_names = [str(m) for m in package.masters]
	default_master = str(package.defaultMaster) if master_names else None

	def location(loc):
		return {str(a.name): _num(loc[a.shortName]) for a in axes}

	# Per-master metrics need setMaster; always restore the current master.
	current = package.master
	per_master = {}
	try:
		for name in master_names:
			package.setMaster(name)
			per_master[name] = _master_metrics(package, name)
	finally:
		if current:
			package.setMaster(current)

	out = {
		'upm':     _num(package.upm),
		'metrics': per_master.get(default_master, {}),
		'info':    _dump_info(fg.info, problems),
		'info_extra': _dump_info_extra(fg.info, package),
		'axes': [dump_axis(a.name, a.tag, a.shortName, a.minimal, a.default, a.maximum,
		                   a.designMin, a.designDef, a.designMax, _axis_map(a))
		         for a in axes],
		'masters': [{
			'name': name, 'layer': name, 'default': name == default_master,
			'location': location(package.location(name)),
			'metrics': per_master.get(name, {}),
		} for name in master_names],
		'instances': [{
			'name': _str(i.name), 'location': location(i.location),
		} for i in package.instances],
		'glyph_order': [g.name for g in fg.glyphs],
		'glyphs': {},
	}

	wanted = set(glyph_names) if glyph_names is not None else None
	for fg_glyph in fg.glyphs:
		name = fg_glyph.name
		if wanted is not None and name not in wanted:
			continue
		glyph = package.findName(name)
		if glyph is None:
			problems.append('findName returned None for {}'.format(name))
			continue
		out['glyphs'][name] = {
			'unicodes': [int(u) for u in (fg_glyph.unicodes or [])],
			'mark':     _mark(glyph.mark),
			'note':     _newlines(glyph.note),
			'layers':   {_str(l.name): _dump_layer(l) for l in glyph.layers if not str(l.name).startswith('#')},
		}

	if _stage_at_least(stage, 'b'):
		# FL-native form (names '@class' for groupMode sides): this is the
		# GATE form, compared FL vs FL. For FL vs core use kern_map.
		kerning, classes = {}, {}
		for name in master_names:
			fl_kern = package.kerning(name)
			pairs = []
			for key, value in fl_kern.items():
				left, right = key.asTuple()
				pairs.append((_kern_side(left), _kern_side(right), int(value)))
			kerning[name] = sorted(pairs)
			classes[name] = {str(k): (list(v[0]), str(v[1])) for k, v in sorted(dict(fl_kern.groups.asDict()).items())}
		out['kerning'] = kerning
		out['kerning_classes'] = classes
		out['groups'] = None		# fg.groups (OT classes): record pending an FL probe
		out['features'] = None		# FEA text: record pending an FL probe of fg.features

	return out

# - Reports -----------------------------
def save_json(dump, path):
	with open(path, 'w', encoding='utf-8') as fh:
		json.dump(dump, fh, indent=1, sort_keys=True)

def load_json(path):
	with open(path, encoding='utf-8') as fh:
		return json.load(fh)

def _jsonable(dump):
	'''Round a dump through JSON so tuples/lists compare alike on both sides.'''
	return json.loads(json.dumps(dump, sort_keys=True))

def eject_report(work_dir, package=None, stage='a', glyph_names=None, limit=200):
	'''DIAGNOSTIC: FL dump vs core dump of the ejected-and-reread .trfont.

	Ejects through trFontProxy (the code under test), writes
	<work_dir>/eject.trfont, reads it back, and diffs it against the raw FL
	dump. Returns the diff lines (plus any API problems, prefixed "!").
	'''
	from typerig.proxy.tr.objects.font import trFontProxy
	from typerig.core.fileio.trfont import TrFontIO

	package = _package(package)
	problems = []
	fl_dump = dump_fl(package, stage, glyph_names, problems)

	path = os.path.join(work_dir, 'eject.trfont')
	trFontProxy(package).save(path, glyph_names=glyph_names)
	core_dump = dump_font(TrFontIO.read(path), stage)

	if glyph_names is not None:
		core_dump['glyph_order'] = fl_dump['glyph_order']		# subset eject: order compared on full runs only

	return ['! ' + p for p in problems] + diff(_jsonable(fl_dump), _jsonable(core_dump), limit=limit)
