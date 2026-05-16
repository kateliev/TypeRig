# MODULE: TypeRig / Proxy / trFont (Objects)
# NOTE: FontLab proxy — bridges FL font to core Font + TrFontIO
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

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
def _fl_info(fg_font):
	'''Extract font info from fgFont → FontInfo (UFO-aligned fields).'''
	def gs(attr):
		return getattr(fg_font, attr, '') or ''

	def gn(attr):
		'''Get numeric or None; FL often returns 0 for "unset" so we keep 0
		unless the attribute is missing entirely.'''
		val = getattr(fg_font, attr, None)
		return val if val is not None else None

	info = FontInfo(
		family_name = gs('familyName'),
		style_name  = gs('styleName'),
	)
	info.version              = gs('version')
	info.year                 = gn('year')
	info.note                 = gs('note')
	info.designer             = gs('designer')
	info.designer_url         = gs('designerURL')
	info.manufacturer         = gs('manufacturer')
	info.manufacturer_url     = gs('manufacturerURL')
	info.copyright            = gs('copyright')
	info.trademark            = gs('trademark')
	info.description          = gs('description')
	info.license              = gs('license')
	info.license_url          = gs('licenseURL')
	info.unique_id            = gs('uniqueID')
	info.vendor_id            = gs('vendorID')
	info.weight_class         = gn('weightClass')
	info.width_class          = gn('widthClass')
	info.italic_angle         = gn('italicAngle_value') if hasattr(fg_font, 'italicAngle_value') else gn('italicAngle')
	info.underline_position   = gn('underlinePosition_value') if hasattr(fg_font, 'underlinePosition_value') else gn('underlinePosition')
	info.underline_thickness  = gn('underlineThickness_value') if hasattr(fg_font, 'underlineThickness_value') else gn('underlineThickness')
	info.postscript_font_name = gs('postscriptFontName') or gs('fontName')

	return info

def _fl_metrics(fg_font):
	'''Extract vertical metrics from fgFont → FontMetrics.'''
	get = lambda attr, default: getattr(fg_font, attr, default) or default

	return FontMetrics(
		upm 		= get('upm', 		1000),
		ascender 	= get('ascender', 	800),
		descender 	= get('descender', 	-200),
		x_height 	= get('xHeight', 	500),
		cap_height 	= get('capHeight', 	700),
		line_gap 	= get('lineGap', 	0),
	)

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


def _groups_into_fl(fg_font, groups):
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

def _fl_axes(fl_package):
	'''Build (axes_list, Masters, Instances) from an flPackage.

	FL's master concept maps directly to Master.layer_name — in FL the
	master name IS the layer name inside every glyph.

	Returns tuple: (axes_list, Masters, Instances)
	'''
	axes_list = []
	masters   = Masters()
	instances = Instances()

	# -- Axes
	try:
		for ax in fl_package.axes:
			axes_list.append(Axis(
				name    = ax.name,
				tag     = ax.tag if hasattr(ax, 'tag') and ax.tag else ax.name[:4].upper(),
				minimum = float(ax.minimum) if hasattr(ax, 'minimum') else 0.,
				default = float(ax.default)  if hasattr(ax, 'default')  else 0.,
				maximum = float(ax.maximum)  if hasattr(ax, 'maximum')  else 1000.,
			))
	except (AttributeError, TypeError):
		pass

	# -- Masters
	try:
		for i, master in enumerate(fl_package.masters):
			loc = {}
			if hasattr(master, 'location') and master.location:
				try:
					loc = {k: float(v) for k, v in dict(master.location).items()}
				except Exception:
					pass

			masters.append(Master(
				name 	   = master.name,
				layer_name = master.name,	# FL convention: master name == layer name
				location   = loc,
				is_default = (i == 0),		# first master is default
			))

	except (AttributeError, TypeError):
		# Single-master fallback: derive layer name from first glyph's first layer
		try:
			first_g = next(iter(fl_package.fgPackage.glyphs), None)
			if first_g and first_g.layers:
				layer_name = first_g.layers[0].name
			else:
				layer_name = 'Regular'
		except Exception:
			layer_name = 'Regular'

		masters.append(Master(
			name 	   = layer_name,
			layer_name = layer_name,
			is_default = True,
		))

	# -- Instances
	try:
		for inst in fl_package.instances:
			loc = {}
			if hasattr(inst, 'location') and inst.location:
				try:
					loc = {k: float(v) for k, v in dict(inst.location).items()}
				except Exception:
					pass

			instances.append(Instance(
				name 	 = inst.name,
				location = loc,
			))

	except (AttributeError, TypeError):
		pass

	return axes_list, masters, instances

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
			name = self.host.fgPackage.familyName or '<unnamed>'
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
		return _fl_metrics(self.fg)

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
	def eject(self, glyph_names=None, include_encoding=True, include_axes=True, include_features=True, include_groups=True, verbose=False):
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
	def save(self, path, glyph_names=None, include_encoding=True, include_axes=True, include_features=True, include_groups=True, verbose=False):
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
	def mount(self, font, include_features=True, include_groups=True, verbose=False):
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

		if include_groups and getattr(font, 'groups', None) is not None and len(font.groups.data):
			try:
				_groups_into_fl(self.fg, font.groups)
				if verbose:
					print('  injected {} groups'.format(len(font.groups.data)))
			except Exception as e:
				if verbose:
					print('  ERROR injecting groups: {}'.format(e))

	def load_and_mount(self, path, **kwargs):
		'''Read a .trfont folder and immediately mount it into the live FL session.'''
		font = TrFontIO.read(path)
		self.mount(font, **kwargs)
		return font

