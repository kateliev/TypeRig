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
#               guide angles (FL `angle`), and info fields that the core
#               FontInfo does not carry yet.
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
	_num, _str, _newlines, _stage_at_least, diff, dump_font,
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
_NUMERIC_INFO = {'year', 'weight_class', 'width_class', 'italic_angle', 'underline_position', 'underline_thickness'}

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

def _kern_side(obj):
	'''fgKerningObject -> "glyph" or "@group" (FL's own naming, not UFO's).'''
	name = _str(getattr(obj, 'id', obj))
	return '@' + name if 'group' in _str(getattr(obj, 'mode', '')).lower() else name

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
				'nodes':  [(_num(n.x), _num(n.y), _str(n.type), bool(n.smooth)) for n in contour.nodes()],
			} for contour in shape.contours],
		})

	return {
		'width':   _num(layer.advanceWidth),
		'height':  _num(layer.advanceHeight),
		'anchors': sorted((_str(a.name), _num(a.point.x()), _num(a.point.y())) for a in layer.anchors),
		# FL convention: position from .vector (an flNode), angle from .angle
		'guides':  sorted((_num(g.vector.x), _num(g.vector.y), _num(g.angle), _str(g.name)) for g in layer.guidelines),
		'shapes':  shapes,
	}

def _master_metrics(package, master):
	return {
		'ascender':   _num(package.ascender_value),
		'descender':  _num(package.descender_value),
		'x_height':   _num(package.xHeight_value),
		'cap_height': _num(package.capsHeight_value),
		'line_gap':   _num(package.lineGap_value),
	}

# - Dump --------------------------------
def dump_fl(package=None, stage='a', glyph_names=None, problems=None):
	'''Dump a live flPackage to the trfont_audit schema.

	Args:
		package      : flPackage; None -> CurrentFont()
		stage        : 'a' | 'b' | 'c' (cumulative field sets)
		glyph_names  : subset to dump (glyph_order still lists every glyph)
		problems     : optional list; API surprises are appended, not raised

	Font-level 'metrics' are the default master's (matches core Font.metrics
	until per-master metrics land in Stage A.2); every master record also
	carries its own metrics under 'metrics' for the A.2 comparison.
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
		'axes': [{
			'name': _str(a.name), 'tag': _str(a.tag),
			'minimum': _num(a.minimal), 'default': _num(a.default), 'maximum': _num(a.maximum),
		} for a in axes],
		'masters': [{
			'name': name, 'layer': name, 'default': name == default_master,
			'location': location(package.location(name)),
		} for name in master_names],
		'instances': [{
			'name': _str(i.name), 'location': location(i.location),
		} for i in package.instances],
		'glyph_order': [g.name for g in fg.glyphs],
		'glyphs': {},
	}
	# Extra, FL-only: per-master metrics (compared once Stage A.2 lands)
	out['master_metrics'] = per_master

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
			'layers':   {_str(l.name): _dump_layer(l) for l in glyph.layers},
		}

	if _stage_at_least(stage, 'b'):
		kerning = {}
		for name in master_names:
			pairs = []
			for key, value in package.kerning(name).items():
				left, right = tuple(key)
				pairs.append((_kern_side(left), _kern_side(right), int(value)))
			kerning[name] = sorted(pairs)
		out['kerning'] = kerning
		out['groups'] = None		# filled in Stage B (FL group mode/side flags need their own record)
		out['features'] = None		# filled in Stage B

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
	fl_dump.pop('master_metrics', None)

	path = os.path.join(work_dir, 'eject.trfont')
	trFontProxy(package).save(path, glyph_names=glyph_names)
	core_dump = dump_font(TrFontIO.read(path), stage)

	if glyph_names is not None:
		core_dump['glyph_order'] = fl_dump['glyph_order']		# subset eject: order compared on full runs only

	return ['! ' + p for p in problems] + diff(_jsonable(fl_dump), _jsonable(core_dump), limit=limit)
