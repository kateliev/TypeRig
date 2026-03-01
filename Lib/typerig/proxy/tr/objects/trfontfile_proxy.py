# MODULE: TypeRig / Proxy / FontFile (Objects)
# NOTE: FontLab proxy — ejects FL font to core FontFile / .trfont format
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# trFontFile wraps an flPackage and provides:
#   eject()      → pure core FontFile (no FL dependency after this)
#   save(path)   → eject + write .trfont in one call
#   inject(font) → push a FontFile back into the live FL session
#
# For testing: instantiate with no args to use CurrentFont().
# To test specific fonts: trFontFile(some_fl_package)

# - Dependencies ------------------------
from __future__ import print_function

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.tr.objects.glyph import trGlyph
from typerig.proxy.tr.objects.layer import trLayer

from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape

from typerig.core.fileio.trfont import (
	TrFontInfo, TrMetrics, TrAxes, TrAxis,
	TrMaster, TrInstance, TrEncoding
)

# FontFile lives alongside this module; import from core
from typerig.core.objects.fontfile import FontFile

# - Init --------------------------------
__version__ = '0.1.0'

# - Helpers -----------------------------
def _fl_info_to_trfont(fg_font):
	'''Extract basic font info from an fgFont into a TrFontInfo.'''
	info = TrFontInfo(
		family_name 	= getattr(fg_font, 'familyName', '') 	or '',
		style_name  	= getattr(fg_font, 'styleName', '')  	or '',
	)

	info.designer 			= getattr(fg_font, 'designer', '')		or ''
	info.designer_url 		= getattr(fg_font, 'designerURL', '') 	or ''
	info.manufacturer 		= getattr(fg_font, 'manufacturer', '') 	or ''
	info.manufacturer_url 	= getattr(fg_font, 'manufacturerURL', '')	or ''
	info.copyright 			= getattr(fg_font, 'copyright', '') 	or ''
	info.trademark 			= getattr(fg_font, 'trademark', '') 	or ''

	return info

def _fl_metrics_to_trfont(fg_font):
	'''Extract vertical metrics from an fgFont into TrMetrics.'''
	get = lambda attr, default: getattr(fg_font, attr, default) or default

	return TrMetrics(
		upm 		= get('upm', 		1000),
		ascender 	= get('ascender', 	800),
		descender 	= get('descender', 	-200),
		x_height 	= get('xHeight', 	500),
		cap_height 	= get('capHeight', 	700),
		line_gap 	= get('lineGap', 	0),
	)

def _fl_masters_to_traxes(fl_package):
	'''Build TrAxes from the masters/axes of an flPackage.

	FL's concept of masters maps to TrMaster; the layer_name
	for each master is the master's name (which matches layer
	names inside each glyph — the standard FL convention).
	'''
	tr_axes = TrAxes()

	# - Axes: FL exposes them via axes list on the package
	try:
		for ax in fl_package.axes:
			tr_axes.axes.append(TrAxis(
				name 	 = ax.name,
				tag  	 = ax.tag if hasattr(ax, 'tag') else ax.name[:4].upper(),
				minimum  = ax.minimum if hasattr(ax, 'minimum') else 0,
				default  = ax.default  if hasattr(ax, 'default')  else 0,
				maximum  = ax.maximum  if hasattr(ax, 'maximum')  else 1000,
			))
	except (AttributeError, TypeError):
		pass  # Font has no axes defined — single-master

	# - Masters
	try:
		for i, master in enumerate(fl_package.masters):
			tr_axes.masters.append(TrMaster(
				name 		= master.name,
				layer_name 	= master.name,  # FL: master name == layer name
				location 	= dict(master.location) if hasattr(master, 'location') else {},
				is_default 	= (i == 0), 	# first master = default
			))
	except (AttributeError, TypeError):
		# Fallback: single unnamed master derived from first layer name
		try:
			first_glyph = next(iter(fl_package.fgPackage.glyphs), None)
			if first_glyph and first_glyph.layers:
				layer_name = first_glyph.layers[0].name
			else:
				layer_name = 'Regular'

			tr_axes.masters.append(TrMaster(
				name 		= layer_name,
				layer_name 	= layer_name,
				is_default 	= True,
			))
		except Exception:
			tr_axes.masters.append(TrMaster('Regular', 'Regular', is_default=True))

	# - Instances
	try:
		for inst in fl_package.instances:
			tr_axes.instances.append(TrInstance(
				name 		= inst.name,
				location 	= dict(inst.location) if hasattr(inst, 'location') else {},
			))
	except (AttributeError, TypeError):
		pass

	return tr_axes

def _fl_encoding_to_trfont(fg_font):
	'''Build TrEncoding from fgFont glyph unicode data.'''
	enc = TrEncoding()

	for glyph in fg_font.glyphs:
		if glyph.unicodes:
			enc.mapping[glyph.name] = list(glyph.unicodes)

	return enc


# - Class -------------------------------
class trFontFile(object):
	'''FontLab proxy for .trfont export/import.

	Wraps an flPackage and provides a clean path from a live
	FontLab session to a .trfont folder on disk and back.

	Constructor:
		trFontFile()                   → uses CurrentFont()
		trFontFile(fl6.flPackage(...)) → specific package
		trFontFile(fgt.fgFont(...))    → fgFont directly

	Attributes:
		.host (fl6.flPackage) : wrapped FL package
	'''

	def __init__(self, *argv):
		if len(argv) == 0:
			self.host = fl6.flPackage(fl6.CurrentFont())

		elif len(argv) == 1 and isinstance(argv[0], fl6.flPackage):
			self.host = argv[0]

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgFont):
			self.host = fl6.flPackage(argv[0])

		else:
			raise TypeError('trFontFile: unexpected argument type')

	def __repr__(self):
		try:
			name = self.host.fgPackage.familyName or '<unnamed>'
		except Exception:
			name = '<unknown>'
		return '<trFontFile: "{}">'.format(name)

	# -- Properties ---------------------
	@property
	def fg(self):
		'''fgFont (fontgate font object).'''
		return self.host.fgPackage

	@property
	def glyph_names(self):
		'''All glyph names in the font, in order.'''
		return [g.name for g in self.fg.glyphs]

	# -- Core font construction ---------
	def _build_info(self):
		return _fl_info_to_trfont(self.fg)

	def _build_metrics(self):
		return _fl_metrics_to_trfont(self.fg)

	def _build_axes(self):
		return _fl_masters_to_traxes(self.host)

	def _build_encoding(self):
		return _fl_encoding_to_trfont(self.fg)

	def _eject_glyph(self, fg_glyph):
		'''Eject a single fgGlyph to a core Glyph with all its layers.'''
		tr_glyph = trGlyph(fg_glyph, self.fg)
		return tr_glyph.eject()

	# -- Main eject ---------------------
	def eject(self, glyph_names=None, verbose=False):
		'''Eject the font (or a subset of glyphs) to a pure core FontFile.

		Args:
			glyph_names (list or None) : subset of glyph names to eject;
			                             None ejects all glyphs
			verbose (bool)             : print progress per glyph

		Returns:
			FontFile — fully populated core font, no FL dependency
		'''
		font = FontFile(
			info 		= self._build_info(),
			metrics 	= self._build_metrics(),
			axes 		= self._build_axes(),
			encoding 	= self._build_encoding(),
		)

		names = glyph_names if glyph_names is not None else self.glyph_names

		for name in names:
			fg_glyph = self.fg[name]
			if fg_glyph is None:
				if verbose:
					print('trFontFile.eject: glyph not found — {}'.format(name))
				continue

			try:
				core_glyph = self._eject_glyph(fg_glyph)
				font.add_glyph(core_glyph, name=name)

				if verbose:
					print('  ejected: {} ({} layers)'.format(name, len(core_glyph.layers)))

			except Exception as e:
				if verbose:
					print('  ERROR ejecting {}: {}'.format(name, e))

		return font

	# -- Save convenience ---------------
	def save(self, path, glyph_names=None, verbose=False):
		'''Eject + save to a .trfont folder in one call.

		Args:
			path (str)                 : destination .trfont folder path
			glyph_names (list or None) : subset to save; None saves all
			verbose (bool)             : print progress

		Returns:
			FontFile — the ejected font object (in case caller needs it)
		'''
		if verbose:
			print('trFontFile.save → {}'.format(path))

		font = self.eject(glyph_names=glyph_names, verbose=verbose)
		font.save(path)

		if verbose:
			print('Done. {} glyphs written.'.format(len(font)))

		return font

	# -- Inject (load back into FL) -----
	def inject(self, font_file, layer_names=None, verbose=False):
		'''Push a FontFile back into the live FL session.

		Injects glyph geometry back into matching FL glyphs by mounting
		each layer. Only layers that exist in both the FontFile and the
		FL glyph are updated. New glyphs or new layers are not created —
		this is a geometry update, not a structural import.

		Args:
			font_file (FontFile)        : source data to push
			layer_names (list or None)  : restrict to specific layer names;
			                             None means all masters in font_file
			verbose (bool)              : print progress
		'''
		target_layers = layer_names or font_file.master_names

		for name in font_file.glyph_names:
			fg_glyph = self.fg[name]
			if fg_glyph is None:
				if verbose:
					print('inject: glyph not found in FL — {}'.format(name))
				continue

			core_glyph = font_file.get_glyph(name)
			if core_glyph is None:
				continue

			tr_glyph = trGlyph(fg_glyph, self.fg)

			for layer_name in target_layers:
				core_layer = core_glyph.layer(layer_name)
				fl_layer_proxy = None

				# Find matching FL layer by name
				for fl_layer in tr_glyph.host.layers:
					if fl_layer.name == layer_name:
						fl_layer_proxy = trLayer(fl_layer)
						break

				if core_layer is None or fl_layer_proxy is None:
					continue

				try:
					fl_layer_proxy.mount(core_layer)
					if verbose:
						print('  injected: {} / {}'.format(name, layer_name))
				except Exception as e:
					if verbose:
						print('  ERROR injecting {} / {}: {}'.format(name, layer_name, e))

			tr_glyph.update()
