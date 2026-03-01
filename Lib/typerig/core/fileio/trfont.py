# MODULE: TypeRig / IO / TrFont (Format)
# NOTE: Folder-level serialization for the .trfont work format
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# This module handles what xmlio cannot: the .trfont folder structure.
# A .trfont folder contains separate XML files for each font part and
# one .trglyph file per glyph. All per-element XML serialization is
# handled by the core objects themselves (via XMLSerializable).
#
# What lives here:
#   - folder creation and discovery
#   - font.xml as a thin container of file pointers
#   - glyphs.xml manifest (name → path, optional alias, search paths)
#   - Font.write(path)  — scatter a Font object into a .trfont folder
#   - Font.read(path)   — assemble a Font object from a .trfont folder
#
# Folder layout:
#   MyFont.trfont/
#   ├── font.xml        thin container: font descriptor + file pointers
#   ├── glyphs.xml      glyph manifest: name/alias → file path + search paths
#   └── glyphs/         embedded glyph files (optional)
#       ├── A.trglyph
#       └── ...
#
# font.xml embeds: <info>, <metrics>, <axes>, <masters>, <instances>,
#                  <encoding>, <kerning> — all serialized by the objects.
# glyphs.xml is separate because it is a runtime manifest (paths change
# when the font moves) and because it may reference external shared pools.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import os
from xml.etree import ElementTree as ET
from xml.dom import minidom

from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Masters, Master
from typerig.core.objects.instance import Instances, Instance
from typerig.core.objects.encoding import Encoding
from typerig.core.objects.kern import Kerning
from typerig.core.objects.glyph import Glyph

# - Init --------------------------------
__version__ = '0.1.0'

TRFONT_EXT 	= '.trfont'
TRGLYPH_EXT = '.trglyph'
GLYPHS_DIR 	= 'glyphs'
FILE_FONT 	= 'font.xml'
FILE_GLYPHS = 'glyphs.xml'

# - Helpers -----------------------------
def _pretty_xml(element):
	'''Return indented XML string from an Element.'''
	raw = ET.tostring(element, encoding='unicode')
	parsed = minidom.parseString(raw)
	# Strip the minidom declaration — we write our own
	lines = parsed.toprettyxml(indent='\t').split('\n')
	return '\n'.join(lines[1:])

def _write_xml(path, element):
	content = '<?xml version="1.0" encoding="UTF-8"?>\n' + _pretty_xml(element)
	with open(path, 'w', encoding='utf-8') as fh:
		fh.write(content)

def _read_xml(path):
	if not os.path.isfile(path):
		return None
	return ET.parse(path).getroot()

# - Manifest ----------------------------
class GlyphEntry(object):
	'''Single glyph entry in the manifest.

	name (str)  : canonical glyph name
	path (str)  : path to .trglyph (relative to .trfont or absolute)
	alias (str) : optional project-local alias (name as seen in this font)
	'''
	__slots__ = ('name', 'path', 'alias')

	def __init__(self, name, path, alias=None):
		self.name  = name
		self.path  = path
		self.alias = alias

	def __repr__(self):
		alias_part = ' alias="{}"'.format(self.alias) if self.alias else ''
		return '<GlyphEntry: "{}"{} → {}>'.format(self.name, alias_part, self.path)

	@property
	def project_name(self):
		'''Name as seen by this font project.'''
		return self.alias if self.alias else self.name

	def to_element(self):
		elem = ET.Element('glyph')
		elem.set('name', self.name)
		elem.set('src',  self.path)
		if self.alias:
			elem.set('alias', self.alias)
		return elem

	@classmethod
	def from_element(cls, elem):
		return cls(
			name  = elem.get('name', ''),
			path  = elem.get('src',  ''),
			alias = elem.get('alias', None),
		)


class GlyphManifest(object):
	'''Glyph manifest (glyphs.xml) — ordered list of glyph file references.

	Maintains glyph order (= font glyph order) and resolves paths
	for both local-embedded and shared-pool glyphs.

	Search paths: fallback directories tried when a glyph entry has
	no explicit src path. Paths are relative to the .trfont folder
	or absolute.

	Usage:
		manifest = GlyphManifest()
		manifest.add('A', 'glyphs/A.trglyph')
		manifest.add('uni4E00', '/shared/CJK/uni4E00.trglyph', alias='CJK_1')
		manifest.search_paths.append('../SharedGlyphs')
	'''

	def __init__(self, entries=None, search_paths=None):
		self.entries 		= entries 		or []	# [GlyphEntry, ...]
		self.search_paths 	= search_paths 	or []	# [str, ...]

	def __repr__(self):
		return '<GlyphManifest: {} glyphs, {} search paths>'.format(
			len(self.entries), len(self.search_paths))

	def __len__(self):
		return len(self.entries)

	def get(self, name):
		'''Find entry by name or alias.'''
		for entry in self.entries:
			if entry.name == name or entry.alias == name:
				return entry
		return None

	def add(self, name, path, alias=None):
		self.entries.append(GlyphEntry(name, path, alias))

	def remove(self, name):
		self.entries = [e for e in self.entries
		                if e.name != name and e.alias != name]

	def names(self):
		'''Ordered project names (alias if set, otherwise name).'''
		return [e.project_name for e in self.entries]

	def resolve_path(self, entry, font_dir):
		'''Return absolute path to the .trglyph file, or None if missing.'''
		src = entry.path

		# Absolute path — check directly
		if os.path.isabs(src):
			return src if os.path.isfile(src) else None

		# Relative to font folder
		candidate = os.path.normpath(os.path.join(font_dir, src))
		if os.path.isfile(candidate):
			return candidate

		# Search paths fallback
		filename = entry.name + TRGLYPH_EXT
		for sp in self.search_paths:
			root = sp if os.path.isabs(sp) else os.path.join(font_dir, sp)
			candidate = os.path.join(root, filename)
			if os.path.isfile(candidate):
				return candidate

		return None

	# -- Serialization ------------------
	def to_element(self):
		root = ET.Element('glyphs')

		if self.search_paths:
			search = ET.SubElement(root, 'search')
			for sp in self.search_paths:
				path_elem = ET.SubElement(search, 'path')
				path_elem.set('value', sp)

		for entry in self.entries:
			root.append(entry.to_element())

		return root

	def write(self, path):
		_write_xml(path, self.to_element())

	@classmethod
	def read(cls, path):
		root = _read_xml(path)
		if root is None:
			return cls()
		search_paths = [e.get('value', '') for e in root.findall('./search/path')]
		entries = [GlyphEntry.from_element(e) for e in root.findall('glyph')]
		return cls(entries=entries, search_paths=search_paths)


# - Font IO -----------------------------
class TrFontIO(object):
	'''Read and write Font objects as .trfont folder packages.

	All per-element XML serialization is delegated to the Font object
	and its children via their own _to_xml_element / from_XML methods.
	TrFontIO only handles the folder structure and glyph file dispatch.

	Usage:
		# Write
		TrFontIO.write(font, '/path/to/MyFont.trfont')

		# Read
		font = TrFontIO.read('/path/to/MyFont.trfont')

		# Shared-pool glyphs (external references)
		TrFontIO.write(font, path, glyph_paths={'A': '/shared/A.trglyph'})
	'''

	@staticmethod
	def write(font, path, glyph_paths=None, embed_glyphs=True):
		'''Write a Font object to a .trfont folder.

		Args:
			font (Font)          : core Font object to serialize
			path (str)           : destination .trfont folder
			glyph_paths (dict)   : {glyph_name: absolute_path} for shared-pool
			                       glyphs that should not be embedded locally.
			                       Glyphs not in this dict are embedded.
			embed_glyphs (bool)  : write .trglyph files locally when True.
			                       Set False to write manifest-only (paths must
			                       already exist externally).
		'''
		os.makedirs(path, exist_ok=True)

		glyph_paths = glyph_paths or {}
		manifest    = GlyphManifest()

		# Write font.xml — the font descriptor (no glyphs embedded)
		font_elem = font._to_xml_element()
		_write_xml(os.path.join(path, FILE_FONT), font_elem)

		# Write glyph files + build manifest
		glyph_dir = os.path.join(path, GLYPHS_DIR)
		if embed_glyphs:
			os.makedirs(glyph_dir, exist_ok=True)

		for glyph in font.glyphs:
			name = glyph.name

			if name in glyph_paths:
				# External shared-pool reference — just record path, no copy
				manifest.add(name, glyph_paths[name])
			else:
				# Embed locally
				filename = name + TRGLYPH_EXT
				rel_path = os.path.join(GLYPHS_DIR, filename)

				if embed_glyphs:
					abs_path = os.path.join(path, rel_path)
					xml_str  = glyph.to_XML()
					with open(abs_path, 'w', encoding='utf-8') as fh:
						fh.write(xml_str)

				manifest.add(name, rel_path)

		manifest.write(os.path.join(path, FILE_GLYPHS))

	@staticmethod
	def read(path):
		'''Read a .trfont folder and return a populated Font object.

		Reads font.xml first (info, metrics, axes, masters, instances,
		encoding, kerning), then loads glyphs from the manifest.
		Encoding values in font.xml override unicodes in individual glyphs.

		Args:
			path (str) : path to .trfont folder

		Returns:
			Font
		'''
		if not os.path.isdir(path):
			raise FileNotFoundError('Not a .trfont folder: {}'.format(path))

		# Parse the font descriptor
		font_root = _read_xml(os.path.join(path, FILE_FONT))

		if font_root is not None:
			# Parse without embedded glyphs (they come from separate files)
			font = Font.from_XML(font_root, include_glyphs=False)
		else:
			font = Font()

		# Load manifest
		manifest = GlyphManifest.read(os.path.join(path, FILE_GLYPHS))

		# Load each glyph in manifest order
		for entry in manifest.entries:
			glyph_path = manifest.resolve_path(entry, path)

			if glyph_path is None or not os.path.isfile(glyph_path):
				# Missing file — placeholder glyph keeps the order intact
				font.append(Glyph(name=entry.project_name))
				continue

			with open(glyph_path, 'r', encoding='utf-8') as fh:
				xml_str = fh.read()

			glyph = Glyph.from_XML(xml_str)

			# Apply alias as glyph name if set
			if entry.alias:
				glyph.name = entry.alias

			# Encoding override: font-level encoding wins over glyph-baked value
			enc_unicodes = font.encoding.unicodes(entry.project_name)
			if enc_unicodes:
				glyph.unicodes = enc_unicodes

			font.append(glyph)

		return font

	@staticmethod
	def new(path, family_name='Untitled', style_name='Regular'):
		'''Create a new empty .trfont folder with a minimal Font skeleton.

		Returns the empty Font object.
		'''
		font = Font(
			info    = FontInfo(family_name, style_name),
			metrics = FontMetrics(),
		)
		TrFontIO.write(font, path)
		return font
