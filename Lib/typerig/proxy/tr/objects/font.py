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

# Folder-level IO
from typerig.core.fileio.trfont import TrFontIO

# - Init --------------------------------
__version__ = '0.3.0'

# - Helpers -----------------------------
def _fl_info(fg_font):
	'''Extract basic font info from fgFont → FontInfo.'''
	get = lambda attr: getattr(fg_font, attr, '') or ''

	info = FontInfo(
		family_name = get('familyName'),
		style_name  = get('styleName'),
	)
	info.version 		  = get('version')
	info.designer 		  = get('designer')
	info.designer_url 	  = get('designerURL')
	info.manufacturer 	  = get('manufacturer')
	info.manufacturer_url = get('manufacturerURL')
	info.copyright 		  = get('copyright')
	info.trademark 		  = get('trademark')

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

	def _eject_glyph(self, fg_glyph):
		tr_g = trGlyph(fg_glyph, self.fg)
		return tr_g.eject()

	# -- Eject --------------------------
	def eject(self, glyph_names=None, include_encoding=True, include_axes=True, verbose=False):
		'''Eject FL font (or subset of glyphs) to a pure core Font.

		Args:
			glyph_names (list|None) : names to export; None → all glyphs
			include_encoding (bool) : build Encoding from glyph unicodes
			include_axes (bool)     : extract axes / masters / instances
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

		font = Font(
			info 	  = info,
			metrics   = metrics,
			axes 	  = axes_list,
			masters   = masters,
			instances = instances,
			encoding  = encoding,
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
	def save(self, path, glyph_names=None, include_encoding=True, include_axes=True, verbose=False):
		'''Eject + write to .trfont folder in one call.

		Args:
			path (str)               : destination .trfont folder
			glyph_names (list|None)  : subset to export; None → all
			include_encoding (bool)  : export encoding map
			include_axes (bool)      : export axes / masters / instances
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

	def mount(self, font):
	
		for glyph_name in font.glyph_names:
			core_glyph = font[glyph_name]

			if self.has_glyph(glyph_name):
				tr_glyph = self.glyph(glyph_name)
			else:
				layer_names = [layer.name for layer in core_glyph.layers if '#' not in layer.name]
				tr_glyph = self.create_glyph(glyph_name, layer_names)

			unicodes = font.encoding.unicodes(glyph_name) if font.encoding else []
			if len(unicodes): tr_glyph.unicodes = unicodes

			for core_layer in core_glyph.layers:
				if '#' not in layer.name: continue

				fl_layer_proxy = tr_glyph.find_layer(core_layer.name)

				if fl_layer_proxy is None:
					fl_layer_proxy = tr_glyph.add_layer(core_layer.name)

				fl_layer_proxy.mount(core_layer)

