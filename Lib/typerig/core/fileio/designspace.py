# MODULE: TypeRig / IO / Designspace
# NOTE: Axes / masters / instances <-> .designspace (fontTools.designspaceLib)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
# ----------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# The design space part of a .designspace document, on the core objects
# Axis / Master / Instance — no glyph data, no UFOs:
#
#   build_document(axes, masters, instances, family_name, sources)
#   write_designspace(path, axes, masters, ...)      -> path
#   read_designspace(path_or_text, design=True)      -> dict(axes, masters,
#                                                       instances, warnings)
#   axes_from_document / instances_from_document / default_source
#
# Shared by the UFO converter (fileio/ufo.py: tr_to_designspace,
# designspace_to_tr, which add the UFO reading / writing) and the Delta
# Machine's Designspace tab (axes and masters only).
#
# Coordinates: Axis minimum / default / maximum are user values in a
# designspace, master locations design values. read_designspace(design=True)
# maps the axis values to design through the axis <map> so axes and masters
# share one space; design=False keeps them as written (the UFO converter).
# Discrete axes (format 5 'values') are skipped with a warning.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function

import os

from fontTools.designspaceLib import (
	DesignSpaceDocument, AxisDescriptor,
	SourceDescriptor, InstanceDescriptor,
)

from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Master
from typerig.core.objects.instance import Instances, Instance

# - Init --------------------------------
__version__ = '0.1.0'


# - Names -------------------------------
def safe_filename(name):
	'''Filesystem-safe filename fragment from a master / layer name.'''
	out = []
	for ch in str(name):
		out.append(ch if ch.isalnum() or ch in ('-', '_', '.') else '_')
	return ''.join(out) or 'master'


def ufo_filename(stem, master_name):
	'''"<stem>-<MasterName>.ufo", the UFO next to a .designspace.'''
	return '{}-{}.ufo'.format(stem, safe_filename(master_name))


def source_name(sd, prefer_style=False):
	'''Master name of a source. The UFO converter keeps its historical
	order (name, style name, layer); readers that match font masters by
	their visible name prefer the style name (fontmake writes name =
	"master.<style>").'''
	stem = os.path.splitext(os.path.basename(sd.filename or sd.path or ''))[0]
	order = (sd.styleName, sd.name) if prefer_style else (sd.name, sd.styleName)
	return next((n for n in order + (sd.layerName, stem) if n), 'Master')


# - Write -------------------------------
def build_document(axes, masters, instances=(), family_name='', sources=None):
	'''DesignSpaceDocument from core objects.

	axes      : [Axis] (minimum / default / maximum written as they are)
	masters   : [Master] (location {axis name: value})
	instances : [Instance]
	sources   : {master name: (filename, path or None[, layer name])};
	            masters missing from it get no filename.
	'''
	doc = DesignSpaceDocument()
	for axis in axes:
		ad = AxisDescriptor()
		ad.name    = axis.name
		ad.tag     = axis.tag
		ad.minimum = float(axis.minimum)
		ad.default = float(axis.default)
		ad.maximum = float(axis.maximum)
		doc.addAxis(ad)

	sources = sources or {}
	for master in masters:
		sd = SourceDescriptor()
		entry = tuple(sources.get(master.name, ())) + (None, None, None)
		filename, path, layer = entry[:3]
		if filename:
			sd.filename = filename
		if path:
			sd.path = path
		sd.familyName = family_name
		sd.styleName  = master.name
		sd.name       = master.name
		if layer:
			sd.layerName = layer
		sd.location   = dict(master.location)
		doc.addSource(sd)

	for inst in instances:
		id_ = InstanceDescriptor()
		id_.familyName = family_name
		id_.styleName  = inst.name
		id_.name       = inst.name
		id_.location   = dict(inst.location)
		doc.addInstance(id_)
	return doc


def write_designspace(path, axes, masters, instances=(), family_name='', sources=None):
	'''Write a .designspace (no UFOs). Sources default to
	"<stem>-<master>.ufo" next to the file.'''
	path = os.path.abspath(path)
	if sources is None:
		stem = os.path.splitext(os.path.basename(path))[0]
		sources = {m.name: (ufo_filename(stem, m.name), None) for m in masters}
	build_document(axes, masters, instances, family_name, sources).write(path)
	return path


# - Read --------------------------------
def _is_discrete(ad):
	return getattr(ad, 'values', None) is not None and getattr(ad, 'minimum', None) is None


def axes_from_document(doc, design=False, warnings=None):
	'''[Axis]; design=True maps minimum / default / maximum through the
	axis map to design values (the space of the master locations).'''
	axes = []
	for ad in doc.axes:
		if _is_discrete(ad):
			if warnings is not None:
				warnings.append('Discrete axis {} skipped.'.format(ad.name))
			continue
		fwd = ad.map_forward if design and getattr(ad, 'map', None) else (lambda v: v)
		axes.append(Axis(name=ad.name, tag=ad.tag, minimum=fwd(ad.minimum),
		                 default=fwd(ad.default), maximum=fwd(ad.maximum)))
	return axes


def instances_from_document(doc):
	out = []
	for id_ in doc.instances:
		out.append(Instance(
			name     = id_.name or id_.styleName or 'Instance',
			location = dict(id_.location or {}),
		))
	return Instances(out)


def default_source(doc, axes):
	'''The source at the axes' default location, else the first one.'''
	default_loc = {a.name: a.default for a in axes}
	sources = list(doc.sources)
	for sd in sources:
		if (sd.location or {}) == default_loc:
			return sd
	return sources[0] if sources else None


def read_designspace(source, design=True, prefer_style=True):
	'''Axes, masters and instances of a .designspace (path or XML text),
	without opening any UFO. Master names: see source_name; layer_name =
	the source's layer, else the name. Returns
	{'axes', 'masters', 'instances', 'warnings', 'document'}.'''
	if os.path.isfile(str(source)):
		doc = DesignSpaceDocument.fromfile(source)
	else:
		doc = DesignSpaceDocument.fromstring(source)
	warnings = []
	axes = axes_from_document(doc, design=design, warnings=warnings)
	names = {a.name for a in axes}
	default_loc = {a.name: a.default for a in axes}
	masters = []
	for sd in doc.sources:
		name = source_name(sd, prefer_style)
		location = {k: float(v) for k, v in (sd.location or {}).items() if k in names}
		for axis in axes:
			location.setdefault(axis.name, axis.default)
		if sd.layerName:
			warnings.append('Source {} is a sparse layer ({}).'.format(name, sd.layerName))
		masters.append(Master(name=name, layer_name=sd.layerName or name, location=location,
		                      is_default=all(abs(location[k] - v) < 1e-6 for k, v in default_loc.items())))
	defaults = [m for m in masters if m.is_default]
	for m in defaults[1:]:
		m.is_default = False
	if masters and not defaults:
		masters[0].is_default = True
		warnings.append('No source at the default location: {} taken as default.'.format(masters[0].name))
	for kind, items in (('rules', getattr(doc, 'rules', [])), ('variable fonts', getattr(doc, 'variableFonts', []))):
		if items:
			warnings.append('{} {} not read.'.format(len(items), kind))
	return {'axes': axes, 'masters': masters, 'instances': instances_from_document(doc),
	        'warnings': warnings, 'document': doc}
