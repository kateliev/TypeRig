# MODULE: TypeRig / Core / FontFile (Object)
# NOTE: Thin compatibility wrapper over Font + TrFontIO
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# FontFile predates the trfont rewrite (2026-07): it used to carry its
# own TrFontInfo/TrMetrics/TrAxes containers and folder round-trip. All
# of that now lives on the core Font object (objects/font.py) and the
# TrFontIO reader/writer (fileio/trfont.py). This module remains as a
# thin dict-like wrapper so callers keep the {name: Glyph} access model:
#   - glyphs addressable by name OR index, order preserved
#   - save() / load() delegate to TrFontIO (.trfont folder format)
# New code should use Font + TrFontIO directly.

# - Dependencies ------------------------

from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.glyph import Glyph
from typerig.core.fileio.trfont import TrFontIO, GLYPHS_DIR, TRGLYPH_EXT

# - Init --------------------------------
__version__ = '0.2.0'

# - Class -------------------------------
class FontFile(object):
	'''Dict-like compatibility wrapper around a core Font.

	Holds all font data in pure Python objects — no FL dependencies.
	Glyphs are addressable by name or index; order is preserved by the
	underlying Font container (which also keeps a name → index cache).

	Constructor kwargs (all forwarded to Font):
		info (FontInfo)       : family name, designer, etc.
		metrics (FontMetrics) : font-level vertical metrics
		axes (list)           : [Axis, ...]
		masters (Masters)     : masters Container
		instances (Instances) : instances Container
		encoding (Encoding)   : unicode map (highest priority)
		kerning (Kerning)     : kern pairs
		groups (Groups)       : UFO-style groups
		features (str)        : raw OpenType .fea source
		glyphs (list | dict)  : initial glyphs
	'''

	def __init__(self, **kwargs):
		glyphs = kwargs.pop('glyphs', None)
		font = kwargs.pop('font', None)

		self.font = font if font is not None else Font(**kwargs)

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
			len(self.font.data), len(self.font.masters))

	def __len__(self):
		return len(self.font.data)

	def __iter__(self):
		'''Iterate glyphs in order.'''
		return iter(self.font.data)

	def __contains__(self, name):
		return name in self.font

	def __getitem__(self, key):
		'''Access glyph by name or index.'''
		if isinstance(key, int):
			return self.font.data[key]
		return self.font.glyph(key)

	# -- Delegated font parts -----------
	@property
	def info(self):
		return self.font.info

	@info.setter
	def info(self, value):
		self.font.info = value

	@property
	def metrics(self):
		return self.font.metrics

	@metrics.setter
	def metrics(self, value):
		self.font.metrics = value

	@property
	def axes(self):
		return self.font.axes

	@axes.setter
	def axes(self, value):
		self.font.axes = value

	@property
	def encoding(self):
		return self.font.encoding

	@encoding.setter
	def encoding(self, value):
		self.font.encoding = value

	# -- Glyph management ---------------
	def add_glyph(self, glyph, name=None, index=None):
		'''Add a Glyph to the font.

		Args:
			glyph (Glyph) : glyph to add
			name (str)    : override glyph name (uses glyph.name if None)
			index (int)   : insert at position; appends if None
		'''
		if name is not None:
			glyph.name = name

		if index is None:
			self.font.append(glyph)
		else:
			self.font.insert(index, glyph)

	def remove_glyph(self, name):
		'''Remove glyph by name. No-op if not found.'''
		glyph = self.font.glyph(name)

		if glyph is not None:
			self.font.data.remove(glyph)
			self.font._rebuild_cache()

	def get_glyph(self, name, default=None):
		'''Get glyph by name without raising KeyError.'''
		glyph = self.font.glyph(name)
		return glyph if glyph is not None else default

	@property
	def glyph_names(self):
		'''Ordered list of glyph names.'''
		return self.font.glyph_names

	@property
	def glyphs(self):
		'''Ordered list of Glyph objects.'''
		return self.font.glyphs

	# -- Encoding helpers ---------------
	def unicodes(self, name):
		'''Unicodes for glyph name. Encoding map takes priority over glyph.unicodes.'''
		return self.font.unicodes(name)

	# -- Master helpers -----------------
	@property
	def master_names(self):
		'''Layer names for all masters, in master order.'''
		return [m.layer_name for m in self.font.masters]

	# -- IO -----------------------------
	def save(self, path, embed_glyphs=True):
		'''Write font to a .trfont folder at path (delegates to TrFontIO).

		Args:
			path (str)          : destination folder (will be created)
			embed_glyphs (bool) : write .trglyph files into the font folder
		'''
		TrFontIO.write(self.font, path, embed_glyphs=embed_glyphs)

	@classmethod
	def load(cls, path):
		'''Load a .trfont folder and return a populated FontFile
		(delegates to TrFontIO).

		Args:
			path (str) : path to .trfont folder

		Returns:
			FontFile
		'''
		return cls(font=TrFontIO.read(path))
