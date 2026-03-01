# MODULE: TypeRig / Core / FontFile (Object)
# NOTE: Font data container with .trfont serialization
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# FontFile is the core font data object that maps to the .trfont
# file format. Unlike the general-purpose Font (Container of Glyphs),
# this is designed around the trfont structure:
#   - glyphs stored as a dict (name → Glyph) for fast lookup
#   - carries TrFontInfo, TrMetrics, TrAxes, TrEncoding directly
#   - save() / load() round-trip through the .trfont folder format
#   - glyph order is explicit (preserved list of names)

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import os

from typerig.core.objects.glyph import Glyph
from typerig.core.fileio.trfont import (
	TrFont, TrFontInfo, TrMetrics, TrAxes, TrAxis,
	TrMaster, TrInstance, TrEncoding, TrGlyphManifest,
	GLYPHS_DIR, TRGLYPH_EXT
)

# - Init --------------------------------
__version__ = '0.1.0'

# - Class -------------------------------
class FontFile(object):
	'''Core font data container with .trfont serialization.

	Holds all font data in pure Python objects — no FL dependencies.
	Glyphs are stored as a dict keyed by name; glyph order is tracked
	in a separate list so iteration order is always deterministic.

	Attributes:
		info (TrFontInfo)           : family name, designer, etc.
		metrics (TrMetrics)         : font-level vertical metrics
		axes (TrAxes)               : axes, masters, instances
		encoding (TrEncoding)       : unicode map (highest priority)
		_glyphs (dict)              : {name: Glyph}
		_order (list)               : ordered glyph names
	'''

	def __init__(self, **kwargs):
		self.info 		= kwargs.pop('info', 	TrFontInfo())
		self.metrics 	= kwargs.pop('metrics', TrMetrics())
		self.axes 		= kwargs.pop('axes', 	TrAxes())
		self.encoding 	= kwargs.pop('encoding', TrEncoding())

		self._glyphs 	= {}  	# {name: Glyph}
		self._order 	= [] 	# ordered glyph names

		# Bulk-load glyphs if passed
		glyphs = kwargs.pop('glyphs', None)
		if glyphs:
			if isinstance(glyphs, dict):
				for name, glyph in glyphs.items():
					self.add_glyph(glyph, name=name)
			else:
				for glyph in glyphs:
					self.add_glyph(glyph)

	# -- Internals ----------------------
	def __repr__(self):
		return '<FontFile: "{} {}", {} glyphs, {} masters>'.format(
			self.info.family_name, self.info.style_name,
			len(self._glyphs), len(self.axes.masters))

	def __len__(self):
		return len(self._order)

	def __iter__(self):
		'''Iterate glyphs in order.'''
		for name in self._order:
			yield self._glyphs[name]

	def __contains__(self, name):
		return name in self._glyphs

	def __getitem__(self, key):
		'''Access glyph by name or index.'''
		if isinstance(key, int):
			return self._glyphs[self._order[key]]
		return self._glyphs[key]

	# -- Glyph management ---------------
	def add_glyph(self, glyph, name=None, index=None):
		'''Add a Glyph to the font.

		Args:
			glyph (Glyph) : glyph to add
			name (str)    : override glyph name (uses glyph.name if None)
			index (int)   : insert at position; appends if None
		'''
		name = name or glyph.name
		self._glyphs[name] = glyph

		if name not in self._order:
			if index is None:
				self._order.append(name)
			else:
				self._order.insert(index, name)

	def remove_glyph(self, name):
		'''Remove glyph by name.'''
		self._glyphs.pop(name, None)
		try:
			self._order.remove(name)
		except ValueError:
			pass

	def get_glyph(self, name, default=None):
		'''Get glyph by name without raising KeyError.'''
		return self._glyphs.get(name, default)

	@property
	def glyph_names(self):
		'''Ordered list of glyph names.'''
		return list(self._order)

	@property
	def glyphs(self):
		'''Ordered list of Glyph objects.'''
		return [self._glyphs[n] for n in self._order]

	# -- Encoding helpers ---------------
	def unicodes(self, name):
		'''Unicodes for glyph name. Encoding map takes priority over glyph.unicodes.'''
		enc = self.encoding.unicodes(name)
		if enc:
			return enc

		# Fall back to baked-in glyph value
		glyph = self._glyphs.get(name)
		if glyph is not None:
			return list(glyph.unicodes) if glyph.unicodes else []

		return []

	# -- Master helpers -----------------
	@property
	def master_names(self):
		'''Layer names for all masters, in master order.'''
		return [m.layer_name for m in self.axes.masters]

	@property
	def default_master(self):
		return self.axes.default_master

	# -- IO: save -----------------------
	def save(self, path, embed_glyphs=True):
		'''Write font to a .trfont folder at path.

		Args:
			path (str)          : destination folder (will be created)
			embed_glyphs (bool) : copy .trglyph files into the font folder
		'''
		trfont = TrFont(
			path 		= path,
			info 		= self.info,
			metrics 	= self.metrics,
			axes 		= self.axes,
			encoding 	= self.encoding,
		)

		# Write folder skeleton (axes, encoding, font.xml)
		os.makedirs(path, exist_ok=True)
		trfont.write()

		# Write individual glyph files + build manifest
		glyph_dir = os.path.join(path, GLYPHS_DIR)
		if embed_glyphs:
			os.makedirs(glyph_dir, exist_ok=True)

		manifest = TrGlyphManifest()

		for name in self._order:
			glyph = self._glyphs[name]
			filename = name + TRGLYPH_EXT
			rel_path = os.path.join(GLYPHS_DIR, filename)
			glyph_path = os.path.join(path, rel_path)

			if embed_glyphs:
				xml_str = glyph.to_XML()
				with open(glyph_path, 'w', encoding='utf-8') as fh:
					fh.write(xml_str)

			manifest.add(name, rel_path)

		# Write manifest
		trfont.manifest = manifest
		manifest.write(os.path.join(path, 'glyphs.xml'))

	# -- IO: load -----------------------
	@classmethod
	def load(cls, path):
		'''Load a .trfont folder and return a populated FontFile.

		Reads font.xml → axes.xml → encoding.xml → glyphs.xml,
		then loads each referenced .trglyph file into a Glyph object.

		Args:
			path (str) : path to .trfont folder

		Returns:
			FontFile
		'''
		trfont = TrFont.read(path)

		font = cls(
			info 		= trfont.info,
			metrics 	= trfont.metrics,
			axes 		= trfont.axes,
			encoding 	= trfont.encoding,
		)

		# Load glyphs in manifest order
		for entry in trfont.manifest.glyphs:
			glyph_path = trfont.manifest.resolve_path(entry, path)

			if glyph_path is None or not os.path.isfile(glyph_path):
				# Missing file — create empty placeholder glyph
				placeholder = Glyph(name=entry.project_name)
				font.add_glyph(placeholder, name=entry.project_name)
				continue

			with open(glyph_path, 'r', encoding='utf-8') as fh:
				xml_str = fh.read()

			glyph = Glyph.from_XML(xml_str)

			# Apply encoding override if present
			enc_unicodes = trfont.encoding.unicodes(entry.project_name)
			if enc_unicodes:
				glyph.unicodes = enc_unicodes

			font.add_glyph(glyph, name=entry.project_name)

		return font
