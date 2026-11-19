# MODULE: TypeRig / Proxy / trFont (Objects)
# NOTE: FontLab proxy — bridges FL font to core Font + TrFontIO
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# trFontProxy wraps an flPackage and provides:
#   eject(...)   → pure core Font (no FL dependency after this)
#   save(path)   → eject + TrFontIO.write in one call
#   load(path)   → TrFontIO.read, returns core Font
#   inject(font) → push a core Font's geometry back into live FL session
#
# What is bridged from FL:
#   FontInfo  — family/style name, designer, copyright, etc.
#   FontMetrics — UPM, ascender, descender, x-height, cap-height
#   Axes / Masters / Instances — from flPackage.axes / .masters / .instances
#                                with a graceful single-master fallback
#   Encoding  — from fgGlyph.unicodes for every glyph
#   Glyphs    — via existing trGlyph → trLayer eject chain
#
# What is NOT bridged (not yet implemented in FL side):
#   Kerning, Features, Groups — left as empty defaults

# - Dependencies ------------------------
from __future__ import print_function

import os

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.tr.objects.glyph import trGlyph
from typerig.proxy.tr.objects.layer import trLayer

# Core objects (new model)
from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Master, Masters
from typerig.core.objects.instance import Instance, Instances
from typerig.core.objects.encoding import Encoding
from typerig.core.objects.kern import Kerning
from typerig.core.objects.groups import Groups, Group, KERN1_PREFIX, KERN2_PREFIX

# Folder-level IO
from typerig.core.fileio.trfont import TrFontIO

# - Init --------------------------------
__version__ = '0.3.0'

# - Helpers -----------------------------
# FontInfo attribute -> fg.info attribute (UFO fontinfo names), verified on
# FL9 (2026-11). NOTE: fgFont itself has none of these; they all live on
# fg.info. proxy/tr/audit.py keeps its own copy on purpose (the audit must
# not share code paths with the bridge it checks).
FL_INFO_MAP = {
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

# fg.info fields NOT carried in FontInfo.lib:
#   version*        -> composed into FontInfo.version
#   unitsPerEm      -> FontMetrics.upm
#   ascender, descender, xHeight, capHeight -> per-master metrics (A.2);
#                      fg.info only mirrors the key master
#   openTypeHeadModified -> rewritten by FontLab on every save
FL_INFO_SKIP = {'versionMajor', 'versionMinor', 'unitsPerEm',
                'ascender', 'descender', 'xHeight', 'capHeight',
                'openTypeHeadModified', 'dict'}

def fl_info_fields(info):
	'''All plain fg.info fields: {ufo_name: value}. Idiom from spike 0.4:
	dir(fg.info) minus private names, `dict` and callables.'''
	out = {}
	for name in dir(info):
		if name.startswith('_') or name == 'dict':
			continue
		value = getattr(info, name, None)
		if callable(value):
			continue
		out[name] = value
	return out

def _fl_info(fg_font):
	'''fg.info -> FontInfo. Mapped fields go to FontInfo attributes; every
	other non-empty fg.info field goes to FontInfo.lib under its UFO name.'''
	fields = fl_info_fields(fg_font.info)
	mapped = set(FL_INFO_MAP.values())

	kwargs = {}
	for attr, ufo in FL_INFO_MAP.items():
		value = fields.get(ufo)
		if value is not None:
			kwargs[attr] = value

	major, minor = fields.get('versionMajor'), fields.get('versionMinor')
	kwargs['version'] = '{}.{:03d}'.format(int(major), int(minor or 0)) if major is not None else ''

	info = FontInfo(**kwargs)
	info.lib = {name: value for name, value in sorted(fields.items())
	            if name not in mapped and name not in FL_INFO_SKIP and value is not None}
	return info

def _info_into_fl(fg_font, info, problems=None, step=None):
	'''FontInfo -> fg.info (inverse of _fl_info). Problems are collected,
	not raised: one unwritable field must not abort a font build.'''
	problems = problems if problems is not None else []
	target = fg_font.info

	def put(name, value):
		if step is not None:
			step('  info.{}'.format(name))
		try:
			setattr(target, name, value)
		except Exception as e:
			problems.append('fg.info.{} <- {!r}: {}'.format(name, value, e))

	for attr, ufo in FL_INFO_MAP.items():
		value = getattr(info, attr, None)
		if value is None or value == '':
			continue
		put(ufo, value)

	version = getattr(info, 'version', '') or ''
	if version:
		major, _, minor = str(version).partition('.')
		try:
			put('versionMajor', int(major))
			put('versionMinor', int(minor or 0))
		except ValueError:
			problems.append('version {!r} is not "major.minor"'.format(version))

	for name, value in (getattr(info, 'lib', None) or {}).items():
		if name in FL_INFO_SKIP:
			continue
		put(name, value)
	return problems

class _FLMetricsReader(object):
	def __init__(self, package):
		self.ascender   = package.ascender_value
		self.descender  = package.descender_value
		self.x_height   = package.xHeight_value
		self.cap_height = package.capsHeight_value
		self.line_gap   = package.lineGap_value

def _fl_master_metrics(fl_package, upm):
	'''{master name: FontMetrics}. FL keeps vertical metrics per master and
	exposes them only for the current master (setMaster + *_value); the
	current master is always restored.'''
	out = {}
	current = fl_package.master
	try:
		for name in [str(m) for m in fl_package.masters]:
			fl_package.setMaster(name)
			r = _FLMetricsReader(fl_package)
			out[name] = FontMetrics(upm, r.ascender, r.descender, r.x_height, r.cap_height, r.line_gap)
	finally:
		if current:
			fl_package.setMaster(current)
	return out

def _fl_metrics(fl_package):
	'''Font-level FontMetrics = the default master's metrics (+ upm).'''
	upm = fl_package.upm
	per_master = _fl_master_metrics(fl_package, upm)
	default = str(fl_package.defaultMaster) if per_master else None
	return per_master.get(default) or FontMetrics(upm)

def _metrics_into_fl(fl_package, master_name, metrics):
	fl_package.setMaster(master_name)
	fl_package.ascender_value   = metrics.ascender
	fl_package.descender_value  = metrics.descender
	fl_package.xHeight_value    = metrics.x_height
	fl_package.capsHeight_value = metrics.cap_height
	fl_package.lineGap_value    = metrics.line_gap

def _fl_groups(fg_font):
	'''Extract fgGroups → UFO-style Groups.

	FL groups carry a `mode` and per-side flags that indicate whether the
	group is a kerning class (and on which side) or a free user/OT group.
	Side information is renamed onto the UFO reserved prefixes:
	  - first/left  → public.kern1.<name>
	  - second/right → public.kern2.<name>
	  - both sides  → emit two entries, one for each prefix
	  - none        → keep as a user group with the original name

	FL's mode strings and side-attribute names vary across builds, so this
	probes a handful of likely property names and degrades gracefully.
	'''
	groups = Groups()

	try:
		fg_groups = fg_font.groups
	except AttributeError:
		return groups

	# fgGroups exposes .asDict() {name: fgGroup}; fall back to iteration
	try:
		raw = fg_groups.asDict()
		items = list(raw.items())
	except Exception:
		try:
			items = [(g.name, g) for g in fg_groups]
		except Exception:
			return groups

	def _side_flags(fg_group):
		'''Return (is_first, is_second). Probes a few known attribute names.'''
		mode = getattr(fg_group, 'mode', '') or ''
		# Property variants observed across FL builds
		first  = bool(getattr(fg_group, 'isKerningOnLeft',  False)
		           or getattr(fg_group, 'kerning1',         False)
		           or getattr(fg_group, 'firstSide',        False)
		           or ('KernLeft' in mode))
		second = bool(getattr(fg_group, 'isKerningOnRight', False)
		           or getattr(fg_group, 'kerning2',         False)
		           or getattr(fg_group, 'secondSide',       False)
		           or ('KernRight' in mode))
		if 'KernBothSide' in mode:
			first = second = True
		return first, second

	def _members(fg_group):
		for attr in ('names', 'glyphs', 'members'):
			value = getattr(fg_group, attr, None)
			if value is not None:
				try:
					return [str(g) for g in value]
				except TypeError:
					pass
		return []

	for name, fg_group in items:
		members = _members(fg_group)
		if not members:
			continue
		first, second = _side_flags(fg_group)

		if first:
			groups.set(KERN1_PREFIX + name, members)
		if second:
			groups.set(KERN2_PREFIX + name, members)
		if not (first or second):
			# Free user/OT group — keep original name
			groups.set(name, members)

	return groups


# - Kerning (Stage B) -------------------
# FontLab keeps pairs AND kerning classes per master on
# flPackage.kerning(master) (the FL-tested pFont/pKerning API). The name
# mapping to the UFO model is pure and unit-tested: proxy/tr/kern_map.py.

def _fl_pair_sides(pair):
	'''fgKerningObjectPair -> ((name, mode), (name, mode)).'''
	left, right = pair.asTuple()
	return tuple(left.asTuple()), tuple(right.asTuple())

def _fl_kerning(fl_package, problems=None):
	'''-> ({master name: Kerning}, {ufo group name: [members]}).

	Classes are taken from the default master; a master whose classes
	differ is reported (the UFO model has one Groups table per font).
	'''
	from typerig.proxy.tr.kern_map import fl_groups_to_ufo, fl_pair_to_ufo
	problems = problems if problems is not None else []

	names = [str(m) for m in fl_package.masters]
	default = str(fl_package.defaultMaster) if names else None
	kerning, groups_by_master = {}, {}

	for name in names:
		fl_kern = fl_package.kerning(name)
		groups_by_master[name] = fl_groups_to_ufo(dict(fl_kern.groups.asDict()))
		pairs = {}
		for pair, value in fl_kern.items():
			(l, lm), (r, rm) = _fl_pair_sides(pair)
			pairs[fl_pair_to_ufo(l, lm, r, rm)] = value
		kerning[name] = Kerning.from_pairs(pairs)

	groups = groups_by_master.get(default, {})
	for name, g in groups_by_master.items():
		if g != groups:
			problems.append('master {}: kerning classes differ from the default master; default kept'.format(name))
	return kerning, groups

def _kerning_into_fl(fl_package, font, problems=None):
	'''Core kerning + kerning classes -> every master of an flPackage.'''
	from typerig.proxy.tr.kern_map import ufo_groups_to_fl, ufo_pair_to_fl
	problems = problems if problems is not None else []

	ufo_groups = {g.name: list(g.members) for g in font.groups.data}
	fl_groups, rename = ufo_groups_to_fl(ufo_groups, problems)

	for master in [str(m) for m in fl_package.masters]:
		fl_kern = fl_package.kerning(master)
		fl_kern.clear()					# pairs (and classes, if FL ties them)
		fl_kern.groups.clear()
		for name, (members, mode) in fl_groups.items():
			fl_kern.groups[name] = (list(members), mode)

		core_kern = font.kerning_for(master)
		for p in (core_kern.data if core_kern is not None else []):
			(l, lm), (r, rm) = ufo_pair_to_fl(p.first, p.second, rename)
			# fgKerning.set(fgKerningObjectPair | (name1, name2), value) is the
			# documented setter (fontlab-python-docs); __setitem__ is not
			# documented. Explicit modes first: a glyph and a class may share a
			# name. FontLab kerning is integer-only.
			try:
				fl_kern.set(fgt.fgKerningObjectPair(l, r, lm, rm), int(p.value))
			except Exception:
				fl_kern.set((l, r), int(p.value))
	return problems

def _split_fea_blocks(fea_text):
	'''Split an opaque .fea blob into (prefix_text, [(tag, block_text), ...]).

	The prefix is everything before the first `feature TAG { ... } TAG;` block.
	Each block is matched non-greedily and kept intact (including the wrapper),
	since FL's `fg.features.set_feature(tag, body)` accepts the full block.

	Returns ('', []) on empty input.
	'''
	import re
	if not fea_text:
		return '', []

	# Match: `feature <tag> { ... } <tag>;`  with `tag` = 4 chars max + alnum/underscore.
	# Non-greedy on the body so nested braces in lookups still terminate at the
	# matching outer `}`. FL accepts the full block as the "body" argument.
	pattern = re.compile(
		r'feature\s+(\w{1,4})\s*\{.*?\}\s*\1\s*;',
		re.DOTALL,
	)

	blocks = []
	last_end = 0
	prefix_chunks = []
	for m in pattern.finditer(fea_text):
		if m.start() > last_end:
			prefix_chunks.append(fea_text[last_end:m.start()])
		blocks.append((m.group(1), m.group(0)))
		last_end = m.end()
	# Anything after the last feature block is treated as trailing prefix-like
	# content (rare; concat onto prefix to avoid silent loss).
	if last_end < len(fea_text):
		prefix_chunks.append(fea_text[last_end:])

	prefix = ''.join(prefix_chunks).strip()
	return prefix, blocks


def _features_into_fl(fg_font, fea_text):
	'''Push opaque FEA text into fgFont.features (prefix + per-tag blocks).

	FL's `fg.features.set_feature(tag, body)` accepts the full
	`feature TAG { ... } TAG;` block as the body argument (the same shape
	the export side produces). The prefix (top-level classes, lookups,
	languagesystems) goes through `set_prefix(text)`.
	'''
	try:
		feats = fg_font.features
	except AttributeError:
		return

	prefix, blocks = _split_fea_blocks(fea_text or '')

	# fontport (NATIVE-FEATURES guide) documents a native heap over-read in
	# FontLab's feature loader on a tagless trailing `feature` keyword, and
	# refuses it before any native call. Do the same: anything the block
	# splitter left over that still says `feature` is not sent.
	import re
	if re.search(r'\bfeature\b', prefix or ''):
		raise ValueError('features: text outside complete "feature TAG {...} TAG;" blocks '
		                 'contains the keyword "feature"; not sent to FontLab (known native crash)')

	# Clear stale state first so feature removal is also captured on inject.
	try:
		feats.clear()
	except AttributeError:
		pass

	if prefix:
		try:
			feats.set_prefix(prefix)
		except AttributeError:
			pass

	for tag, block_text in blocks:
		try:
			feats.set_feature(tag, block_text)
		except AttributeError:
			break


def _groups_into_fl(fg_font, groups, skip_kerning_classes=False):
	'''Push core Groups into fg_font.groups.

	UFO reserved-prefix names map back to FL kerning groups with the FL-side
	"left"/"right" tag preserved; user/OT groups go in as plain feature-class
	groups. FL's exact mode-string contract varies by build, so we use the
	known `fgGroup(name, members, mode, leader)` constructor and let FL pick
	its representation; if a build refuses a mode string, we fall back to
	the default OT-class mode.
	'''
	from typerig.core.objects.groups import KERN1_PREFIX, KERN2_PREFIX

	try:
		fg_groups = fg_font.groups
	except AttributeError:
		return

	try:
		current = fg_groups.asDict()
	except Exception:
		current = {}

	def _make_group(name, members, mode_hint):
		try:
			return fgt.fgGroup(name, list(members), mode_hint, 'mainglyphname')
		except Exception:
			# Fallback for builds that don't accept the mode hint
			return fgt.fgGroup(name, list(members), 'FeaClassGroupMode', 'mainglyphname')

	for group in groups.data:
		name = group.name
		if skip_kerning_classes and (group.is_kern1 or group.is_kern2):
			continue		# written per master by _kerning_into_fl
		if group.is_kern1:
			fl_name = name[len(KERN1_PREFIX):]
			current[fl_name] = _make_group(fl_name, group.members, 'KernLeftMode')
		elif group.is_kern2:
			fl_name = name[len(KERN2_PREFIX):]
			current[fl_name] = _make_group(fl_name, group.members, 'KernRightMode')
		else:
			current[name] = _make_group(name, group.members, 'FeaClassGroupMode')

	try:
		fg_groups.fromDict(current)
	except AttributeError:
		pass


def _fl_features(fg_font):
	'''Extract OpenType feature source from fgFont as a single opaque FEA string.

	Concatenates the FEA prefix (classes, lookups, languagesystems declared at
	top of feature file) with each named feature block. Result is suitable
	for writing as `features.fea` in UFO style. The inject side (text → FL)
	is not yet implemented; FL's API surface for re-ingesting a single FEA
	blob needs review (similar to guideline API quirks — pending walkthrough).
	'''
	try:
		feats = fg_font.features
	except AttributeError:
		return ''

	parts = []
	try:
		prefix = feats.get_prefix() or ''
		if prefix.strip():
			parts.append(prefix.rstrip())
	except Exception:
		pass

	try:
		tags = list(feats.keys())
	except Exception:
		tags = []

	for tag in tags:
		try:
			body = feats.get_feature(tag) or ''
		except Exception:
			continue
		body = body.strip()
		if not body:
			continue
		# If FL hands back a bare body, wrap it; if it already includes the
		# feature header, pass through unchanged.
		if body.startswith('feature '):
			parts.append(body)
		else:
			parts.append('feature {} {{\n{}\n}} {};'.format(tag, body, tag))

	return '\n\n'.join(parts)

def _axis_map(fl_axis):
	'''flAxis.map -> [(user, design), ...]. Empty in BasilMM; the shape of
	a populated map is unverified (handout, Stage A notes).'''
	m = fl_axis.map
	if not m:
		return []
	return [(float(u), float(d)) for u, d in m]

def _fl_location(fl_location, axes):
	'''flLocation -> {axis name: value}. flLocation has no introspection
	API in PythonQt; it subscripts by axis shortName (verified FL9).'''
	out = {}
	for axis in axes:
		value = fl_location[axis.shortName]
		if value is not None:
			out[str(axis.name)] = float(value)
	return out

def _to_fl_location(location, axes):
	'''{axis name: value} -> flLocation keyed by axis shortName.'''
	short = {str(a.name): str(a.short_name or a.name) for a in axes}
	return fl6.flLocation({short.get(name, name): float(value) for name, value in location.items()})

def _fl_axes(fl_package):
	'''Build (axes_list, Masters, Instances) from an flPackage.

	Verified FL9 facts this relies on (handout §3.2-3.4):
	  - flPackage.masters is a list of master NAMES (str);
	  - locations come from flPackage.location(name) / flInstance.location;
	  - flAxis range is minimal/default/maximum (+ designMin/Def/Max);
	  - the default master is flPackage.defaultMaster, not index 0;
	  - FL master name == glyph layer name (Master.layer_name contract).
	'''
	fl_axes = list(fl_package.axes)
	axes_list = [Axis(
		name    = str(ax.name),
		tag     = str(ax.tag),
		minimum = float(ax.minimal),
		default = float(ax.default),
		maximum = float(ax.maximum),
		short_name     = str(ax.shortName),
		design_minimum = float(ax.designMin),
		design_default = float(ax.designDef),
		design_maximum = float(ax.designMax),
		map            = _axis_map(ax),
	) for ax in fl_axes]

	names = [str(m) for m in fl_package.masters]
	default = str(fl_package.defaultMaster) if names else None
	per_master = _fl_master_metrics(fl_package, fl_package.upm)

	masters = Masters([Master(
		name       = name,
		layer_name = name,
		location   = _fl_location(fl_package.location(name), fl_axes),
		is_default = (name == default),
		metrics    = per_master.get(name),
	) for name in names])

	instances = Instances([Instance(
		name     = str(inst.name),
		location = _fl_location(inst.location, fl_axes),
	) for inst in fl_package.instances])

	return axes_list, masters, instances

def _design_space_into_fl(fl_package, font, problems=None):
	'''Axes, masters (names, locations, default, metrics) and instances of a
	core Font -> a fresh flPackage (one master, no axes: what flPackage()
	gives). Masters are created in core order.'''
	problems = problems if problems is not None else []

	# - Axes. designDef defaults to the axis midpoint in FL, so the design
	#   range is always written explicitly.
	for axis in font.axes:
		ax = fl6.flAxis()
		ax.name = axis.name
		ax.tag = axis.tag
		ax.shortName = axis.short_name or axis.tag or axis.name[:2]
		ax.minimal = axis.minimum
		ax.default = axis.default
		ax.maximum = axis.maximum
		ax.designMin = axis.minimum if axis.design_minimum is None else axis.design_minimum
		ax.designDef = axis.default if axis.design_default is None else axis.design_default
		ax.designMax = axis.maximum if axis.design_maximum is None else axis.design_maximum
		if axis.map:
			problems.append('axis {}: map not written (FL map format unverified)'.format(axis.name))
		fl_package.addAxis(ax)

	# - Masters: rename the initial master to the first core master, add the rest
	masters = list(font.masters.data)
	if not masters:
		return problems

	first = str(fl_package.masters[0])
	if first != masters[0].name:
		fl_package.renameMaster(first, masters[0].name)
	fl_package.setLocation(_to_fl_location(masters[0].location, font.axes), masters[0].name)

	for master in masters[1:]:
		fl_package.addMaster(master.name, False, fl_package, masters[0].name, False, False,
		                     _to_fl_location(master.location, font.axes))

	default = font.default_master_name()
	if default:
		fl_package.defaultMaster = default

	for master in masters:
		_metrics_into_fl(fl_package, master.name, master.metrics or font.metrics)
	fl_package.setMaster(default or masters[0].name)

	# - Instances
	for instance in font.instances.data:
		inst = fl6.flInstance()
		inst.name = instance.name
		inst.location = _to_fl_location(instance.location, font.axes)
		fl_package.addInstance(inst)

	return problems

def _fl_encoding(fg_font):
	'''Extract unicode assignments from fgFont.glyphs → Encoding.'''
	enc = Encoding()
	for glyph in fg_font.glyphs:
		if glyph.unicodes:
			enc.set(glyph.name, *list(glyph.unicodes))
	return enc


# - Class -------------------------------
class trFontProxy(object):
	'''FontLab proxy for .trfont export / import.

	Wraps an flPackage and provides a clean path from a live FL session
	to a .trfont folder on disk and back. All per-element serialization
	goes through the core objects; this class handles only the FL ↔ core
	mapping and glyph dispatch.

	Constructor:
		trFontProxy()                   → uses CurrentFont()
		trFontProxy(fl6.flPackage(...)) → specific package
		trFontProxy(fgt.fgFont(...))    → fgFont directly

	Attributes:
		.host (fl6.flPackage) : wrapped FL package
		.fg   (fgt.fgFont)    : shorthand to fgPackage
	'''

	def __init__(self, *argv):
		if len(argv) == 0:
			self.host = fl6.flPackage(fl6.CurrentFont())

		elif len(argv) == 1 and isinstance(argv[0], fl6.flPackage):
			self.host = argv[0]

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgFont):
			self.host = fl6.flPackage(argv[0])

		else:
			raise TypeError('trFontProxy: unexpected argument type')

	def __repr__(self):
		try:
			name = self.host.fgPackage.info.familyName or '<unnamed>'
		except Exception:
			name = '<unknown>'
		return '<trFontProxy: "{}">'.format(name)

	# -- Shorthands ---------------------
	@property
	def fg(self):
		return self.host.fgPackage

	@property
	def fl(self):
		return self.host

	@property
	def all_glyph_names(self):
		'''All glyph names in font order.'''
		return [g.name for g in self.fg.glyphs]

	@property
	def selected_glyph_names(self):
		'''Names of currently selected glyphs in the FL font window.

		FL exposes selected glyphs via flPackage.selectedGlyphs (returns
		fgGlyph list). Falls back to checking .mark if that attr is absent.
		'''
		try:
			selected = self.host.selectedGlyphs
			if selected is not None:
				return [g.name for g in selected]
		except AttributeError:
			pass

		# Fallback: glyphs with non-zero mark are treated as selected
		try:
			return [g.name for g in self.fg.glyphs if g.mark]
		except Exception:
			return []

	# -- Basics -------------------------
	def glyph(self, glyph, extend=None):
		'''Return TypeRig proxy glyph object (trGlyph) by index (int) or name (str).'''
		if isinstance(glyph, int) or isinstance(glyph, str):
			return trGlyph(self.fg, self.fg[glyph])
		else:
			return trGlyph(self.fg, glyph)

	def has_glyph(self, glyphName):
		return self.fg.has_key(glyphName)

	def add_glyph(self, glyph):
		'''Adds a Glyph (fgGlyph or flGlyph) to font'''
		if isinstance(glyph, fgt.fgGlyph):
			glyph = fl6.flGlyph(glyph)
		
		self.fl.addGlyph(glyph)

	def create_glyph(self, glyph_name, layers=[], unicode_int=None):
		'''Creates new glyph and adds it to the font
		Args:
			glyph_name (str): New glyph name
			layers (list(str) or list(flLayer)): List of layers to be added to the new glyph
			unicode_int (int): Unicode int of the new glyph
		Returns:
			pGlyph
		'''

		# - Build
		base_glyph = fl6.flGlyph()
		base_glyph.name = glyph_name
		self.add_glyph(base_glyph)

		# - Get the newly added glyph (all sane methods exhausted)
		new_glyph = self.glyph(glyph_name)

		# - Set Unicode
		if unicode_int is not None: new_glyph.fg.setUnicode(unicode_int)
		
		# - Add layers
		if len(layers):
			for layer in layers:
				if isinstance(layer, str):
					new_layer = fl6.flLayer()
					new_layer.name = layer
					new_glyph.host.addLayer(new_layer)
				
				elif isinstance(layer, fl6.flLayer):
					new_glyph.host.addLayer(layer)

		# - Add to font
		return new_glyph

	# -- FL → core ----------------------
	def _build_info(self):
		return _fl_info(self.fg)

	def _build_metrics(self):
		return _fl_metrics(self.host)

	def _build_axes(self):
		return _fl_axes(self.host)	# returns (axes_list, Masters, Instances)

	def _build_encoding(self):
		return _fl_encoding(self.fg)

	def _build_features(self):
		return _fl_features(self.fg)

	def _build_groups(self):
		return _fl_groups(self.fg)

	def _eject_glyph(self, fg_glyph):
		tr_g = trGlyph(fg_glyph, self.fg)
		return tr_g.eject()

	# -- Eject --------------------------
	def eject(self, glyph_names=None, include_encoding=True, include_axes=True, include_features=True, include_groups=True, include_kerning=True, verbose=False):
		'''Eject FL font (or subset of glyphs) to a pure core Font.

		Args:
			glyph_names (list|None) : names to export; None → all glyphs
			include_encoding (bool) : build Encoding from glyph unicodes
			include_axes (bool)     : extract axes / masters / instances
			include_features (bool) : extract OpenType FEA as opaque text
			include_groups (bool)   : extract groups + kerning classes (UFO model)
			verbose (bool)          : print per-glyph progress

		Returns:
			Font — fully populated, no FL dependency after this point
		'''
		info    = self._build_info()
		metrics = self._build_metrics()

		if include_axes:
			axes_list, masters, instances = self._build_axes()
		else:
			axes_list, masters, instances = [], Masters(), Instances()

		encoding = self._build_encoding() if include_encoding else Encoding()
		features = self._build_features() if include_features else ''
		groups   = self._build_groups()   if include_groups   else Groups()

		font = Font(
			info 	  = info,
			metrics   = metrics,
			axes 	  = axes_list,
			masters   = masters,
			instances = instances,
			encoding  = encoding,
			features  = features,
			groups    = groups,
		)

		# Stage B: pairs + kerning classes, per master
		self.problems = []
		if include_kerning and masters.data:
			kerning, kern_groups = _fl_kerning(self.host, self.problems)
			for master_name, master_kerning in kerning.items():
				font.set_kerning_for(master_name, master_kerning)
			for group_name, members in kern_groups.items():
				font.groups.set(group_name, members)

		names = glyph_names if glyph_names is not None else self.all_glyph_names

		for name in names:
			fg_glyph = self.fg[name]
			if fg_glyph is None:
				if verbose:
					print('  SKIP: glyph not found — {}'.format(name))
				continue

			try:
				core_glyph = self._eject_glyph(fg_glyph)
				font.append(core_glyph)

				if verbose:
					print('  ejected: {} ({} layers)'.format(name, len(core_glyph.layers)))

			except Exception as e:
				if verbose:
					print('  ERROR ejecting {}: {}'.format(name, e))

		return font

	# -- Save ---------------------------
	def save(self, path, glyph_names=None, include_encoding=True, include_axes=True, include_features=True, include_groups=True, include_kerning=True, verbose=False):
		'''Eject + write to .trfont folder in one call.

		Args:
			path (str)               : destination .trfont folder
			glyph_names (list|None)  : subset to export; None → all
			include_encoding (bool)  : export encoding map
			include_axes (bool)      : export axes / masters / instances
			include_features (bool)  : export OpenType FEA as features.fea
			include_groups (bool)    : export groups + kerning classes
			verbose (bool)           : print progress

		Returns:
			Font — the ejected core font object
		'''
		if verbose:
			print('Exporting → {}'.format(path))

		font = self.eject(
			glyph_names      = glyph_names,
			include_encoding = include_encoding,
			include_axes     = include_axes,
			include_features = include_features,
			include_groups   = include_groups,
			include_kerning  = include_kerning,
			verbose          = verbose,
		)

		TrFontIO.write(font, path)

		if verbose:
			print('Done. {} glyphs written.'.format(len(font)))

		return font

	# -- Load ---------------------------
	@staticmethod
	def load_raw(path):
		'''Read a .trfont folder and return a pure core Font.

		This is a static method — no FL connection needed.

		Args:
			path (str) : path to .trfont folder

		Returns:
			Font
		'''
		return TrFontIO.read(path)

	# -- Mount --------------------------
	def mount(self, font, include_features=True, include_groups=True, include_kerning=True, verbose=False, step=None):
		'''Push a core Font back into the live FL session.

		Mounts geometry + metadata for every glyph, and (optionally) features
		and groups at the font level. Missing glyphs/layers are created;
		matching ones are updated in place.

		Args:
			font (Font)             : source core Font
			include_features (bool) : inject FEA text via fg.features
			include_groups (bool)   : inject groups + kerning classes
			verbose (bool)          : print per-glyph progress
		'''
		for glyph_name in font.glyph_names:
			core_glyph = font[glyph_name]
			if core_glyph is None:
				continue
			if step is not None:
				step('  glyph {}'.format(glyph_name))

			if self.has_glyph(glyph_name):
				tr_glyph = self.glyph(glyph_name)
			else:
				layer_names = [l.name for l in core_glyph.layers]
				tr_glyph = self.create_glyph(glyph_name, layer_names)

			# Font-level encoding wins over per-glyph unicodes
			unicodes = font.encoding.unicodes(glyph_name) if font.encoding else []
			if unicodes:
				tr_glyph.unicodes = unicodes

			# Ensure every core layer has a matching FL layer
			for core_layer in core_glyph.layers:
				if tr_glyph.find_layer(core_layer.name) is None:
					tr_glyph.add_layer(core_layer.name)

			try:
				tr_glyph.mount(core_glyph)
				if verbose:
					print('  mounted: {}'.format(glyph_name))
			except Exception as e:
				if verbose:
					print('  ERROR mounting {}: {}'.format(glyph_name, e))

		if include_features and getattr(font, 'features', ''):
			try:
				_features_into_fl(self.fg, font.features)
				if verbose:
					print('  injected features ({} chars)'.format(len(font.features)))
			except Exception as e:
				if verbose:
					print('  ERROR injecting features: {}'.format(e))

		if include_kerning and font.masters.data:
			if step is not None:
				step('kerning')
			try:
				problems = _kerning_into_fl(self.host, font)
				self.problems = list(getattr(self, 'problems', []) or []) + problems
			except Exception as e:
				if verbose:
					print('  ERROR injecting kerning: {}'.format(e))

		if include_groups and getattr(font, 'groups', None) is not None and len(font.groups.data):
			if step is not None:
				step('groups')
			try:
				_groups_into_fl(self.fg, font.groups, skip_kerning_classes=include_kerning)
				if verbose:
					print('  injected {} groups'.format(len(font.groups.data)))
			except Exception as e:
				if verbose:
					print('  ERROR injecting groups: {}'.format(e))

	@classmethod
	def create_font(cls, font, include_features=True, include_groups=True, include_kerning=True, verbose=False, step_log=None):
		'''Build a NEW FontLab font from a core Font and return its proxy.

		A round trip must produce a fresh VFC, so this does not touch any open
		font: new flPackage -> workspace -> UPM -> info -> axes / masters /
		metrics / instances -> glyphs (mount) -> drop starter glyphs the core
		font does not have. Save it with File > Save As (or the fontlab MCP
		save_font).

		step_log (str|None): file that gets one line per step, flushed and
			fsync'd BEFORE the step runs. If FontLab crashes, the last line
			names the step that took it down.

		Returns:
			trFontProxy, with .problems listing anything not written.
		'''
		def step(text):
			if verbose:
				print('  create_font: ' + text)
			if step_log:
				with open(step_log, 'a', encoding='utf-8') as fh:
					fh.write(text + chr(10))
					fh.flush()
					os.fsync(fh.fileno())

		step('new flPackage + addPackage')
		package = fl6.flPackage()
		fl6.flWorkspace.instance().addPackage(package)
		proxy = cls(package)
		problems = []

		# UPM first: flPackage.upm is read-only, fg.info.unitsPerEm is not.
		step('upm')
		package.fgPackage.info.unitsPerEm = font.metrics.upm
		step('info')
		_info_into_fl(package.fgPackage, font.info, problems, step=step)
		step('design space')
		_design_space_into_fl(package, font, problems)

		starters = [g.name for g in package.fgPackage.glyphs]
		step('mount {} glyphs'.format(len(font)))
		proxy.mount(font, include_features=include_features, include_groups=include_groups,
		            include_kerning=include_kerning, verbose=verbose, step=step)

		for name in starters:
			if font.glyph(name) is None:
				step('remove starter glyph {}'.format(name))
				package.fgPackage.removeGlyph(name)
		step('done')

		proxy.problems = problems + list(getattr(proxy, 'problems', []) or [])
		if verbose:
			for p in problems:
				print('  PROBLEM: {}'.format(p))
		return proxy

	def load_and_mount(self, path, **kwargs):
		'''Read a .trfont folder and immediately mount it into the live FL session.'''
		font = TrFontIO.read(path)
		self.mount(font, **kwargs)
		return font

