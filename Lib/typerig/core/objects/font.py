# MODULE: TypeRig / Core / Font (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member, Container
from typerig.core.objects.glyph import Glyph

from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Master, Masters
from typerig.core.objects.instance import Instance, Instances
from typerig.core.objects.kern import Kerning
from typerig.core.objects.encoding import Encoding

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
@register_xml_class
class FontInfo(Member, XMLSerializable):
	'''Basic font identification and naming information.

	Stores the fields most relevant for a work format: family name,
	style, version, credits and contact. Extended OpenType name table
	entries live in lib if needed.

	Constructor:
		FontInfo(family_name, style_name, **kwargs)

	Attributes:
		family_name (str)     : font family name
		style_name (str)      : style/subfamily name
		version (str)         : version string
		designer (str)        : designer name
		designer_url (str)    : designer URL
		manufacturer (str)    : manufacturer name
		manufacturer_url (str): manufacturer URL
		copyright (str)       : copyright string
		trademark (str)       : trademark string
		description (str)     : free-form description
		lib (dict)            : arbitrary extra metadata
	'''
	__slots__ = (
		'family_name', 'style_name', 'version',
		'designer', 'designer_url',
		'manufacturer', 'manufacturer_url',
		'copyright', 'trademark', 'description',
		'identifier', 'parent', 'lib'
	)

	XML_TAG = 'info'
	# Serialized as <meta key="..." value="..."/> children rather than
	# flat attributes — keeps the element clean and extensible.
	XML_ATTRS = []
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	# Mapping between XML key strings and Python attribute names
	_FIELDS = {
		'family-name':		'family_name',
		'style-name':		'style_name',
		'version':			'version',
		'designer':			'designer',
		'designer-url':		'designer_url',
		'manufacturer':		'manufacturer',
		'manufacturer-url':	'manufacturer_url',
		'copyright':		'copyright',
		'trademark':		'trademark',
		'description':		'description',
	}

	def __init__(self, *args, **kwargs):
		super(FontInfo, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('family_name', args[0])
		if len(args) >= 2: kwargs.setdefault('style_name',  args[1])

		self.family_name 		= kwargs.pop('family_name',		 'Untitled')
		self.style_name 		= kwargs.pop('style_name',		 'Regular')
		self.version 			= kwargs.pop('version',			 '1.0')
		self.designer 			= kwargs.pop('designer',		 '')
		self.designer_url 		= kwargs.pop('designer_url',	 '')
		self.manufacturer 		= kwargs.pop('manufacturer',	 '')
		self.manufacturer_url 	= kwargs.pop('manufacturer_url', '')
		self.copyright 			= kwargs.pop('copyright',		 '')
		self.trademark 			= kwargs.pop('trademark',		 '')
		self.description 		= kwargs.pop('description',		 '')
		self.lib 				= kwargs.pop('lib',				 {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: "{} {}">'.format(
			self.__class__.__name__, self.family_name, self.style_name)

	# -- Serialization override ---------
	# Using <meta key="..." value="..."/> pattern for clean, extensible XML.

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)

		rev = {v: k for k, v in self._FIELDS.items()}
		for attr, xml_key in rev.items():
			val = getattr(self, attr, '')
			if val:
				meta = ET.SubElement(elem, 'meta')
				meta.set('key',   xml_key)
				meta.set('value', str(val))

		# Arbitrary lib entries
		if self.lib:
			lib_elem = ET.SubElement(elem, 'lib')
			for key, val in self.lib.items():
				entry = ET.SubElement(lib_elem, 'entry')
				entry.set('key',   str(key))
				entry.set('value', str(val))

		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		if element is None:
			return cls()

		kwargs = {}
		for meta in element.findall('meta'):
			xml_key = meta.get('key', '')
			if xml_key in cls._FIELDS:
				kwargs[cls._FIELDS[xml_key]] = meta.get('value', '')

		lib = {}
		lib_elem = element.find('lib')
		if lib_elem is not None:
			for entry in lib_elem.findall('entry'):
				lib[entry.get('key', '')] = entry.get('value', '')
		kwargs['lib'] = lib

		return cls(**kwargs)


@register_xml_class
class FontMetrics(Member, XMLSerializable):
	'''Font-level vertical metrics.

	Stores the primary vertical metrics used across all masters.
	Individual masters can override specific values where the design
	requires it (e.g. a bold master with a slightly taller ascender).

	Constructor:
		FontMetrics(upm, ascender, descender, x_height, cap_height, line_gap)

	Attributes:
		upm (int)        : units per em
		ascender (int)   : ascender value
		descender (int)  : descender value (negative)
		x_height (int)   : x-height value
		cap_height (int) : cap-height value
		line_gap (int)   : recommended line gap
	'''
	__slots__ = ('upm', 'ascender', 'descender', 'x_height', 'cap_height', 'line_gap',
	             'identifier', 'parent', 'lib')

	XML_TAG = 'metrics'
	XML_ATTRS = ['upm', 'ascender', 'descender', 'x-height', 'cap-height', 'line-gap']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(FontMetrics, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('upm',		   args[0])
		if len(args) >= 2: kwargs.setdefault('ascender',   args[1])
		if len(args) >= 3: kwargs.setdefault('descender',  args[2])
		if len(args) >= 4: kwargs.setdefault('x_height',   args[3])
		if len(args) >= 5: kwargs.setdefault('cap_height', args[4])
		if len(args) >= 6: kwargs.setdefault('line_gap',   args[5])

		self.upm 		= int(kwargs.pop('upm',		    1000))
		self.ascender 	= int(kwargs.pop('ascender',    800))
		self.descender 	= int(kwargs.pop('descender',   -200))
		self.x_height 	= int(kwargs.pop('x_height',    500))
		self.cap_height = int(kwargs.pop('cap_height',  700))
		self.line_gap 	= int(kwargs.pop('line_gap',    0))
		self.lib 		= kwargs.pop('lib', {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: UPM={} Asc={} Desc={}>'.format(
			self.__class__.__name__, self.upm, self.ascender, self.descender)

	# -- Serialization override ---------
	# XML uses hyphenated attribute names; Python uses underscores.

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('upm',		    str(self.upm))
		elem.set('ascender',    str(self.ascender))
		elem.set('descender',   str(self.descender))
		elem.set('x-height',    str(self.x_height))
		elem.set('cap-height',  str(self.cap_height))
		elem.set('line-gap',    str(self.line_gap))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		if element is None:
			return cls()

		def _int(attr, default):
			val = element.get(attr)
			return int(val) if val is not None else default

		return cls(
			upm 		= _int('upm', 		 1000),
			ascender 	= _int('ascender',   800),
			descender 	= _int('descender',  -200),
			x_height 	= _int('x-height',   500),
			cap_height 	= _int('cap-height', 700),
			line_gap 	= _int('line-gap',   0),
		)


@register_xml_class
class Font(Container, XMLSerializable):
	'''Core font object — Container of Glyph with full font-level metadata.

	Font holds glyphs as its primary Container data (ordered list), plus
	all the metadata needed to describe a multi-master font project:
	info, metrics, axes, masters, instances, encoding and kerning.

	Glyphs are stored as a list (Container data) for structural parity
	with Glyph → Layer → Shape → Contour. A name→index cache provides
	fast lookup without duplicating data.

	Constructor:
		Font(glyphs, **kwargs)
		Font([glyph_a, glyph_b], info=FontInfo('MyFamily'))

	Attributes:
		info (FontInfo)       : family name, designer, etc.
		metrics (FontMetrics) : font-level vertical metrics
		axes (list)           : [Axis, ...]
		masters (Masters)     : masters Container
		instances (Instances) : instances Container
		encoding (Encoding)   : unicode map
		kerning (Kerning)     : kern pairs and classes
		lib (dict)            : arbitrary font-level metadata
	'''
	__slots__ = (
		'info', 'metrics', 'axes', 'masters', 'instances',
		'encoding', 'kerning', 'identifier', 'parent', 'lib'
	)

	XML_TAG = 'font'
	XML_ATTRS = ['identifier']
	XML_CHILDREN = {}		# glyphs are NOT embedded in font.xml (separate .trglyph files)
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Glyph)
		super(Font, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.identifier = kwargs.pop('identifier', None)
			self.info 		= kwargs.pop('info',     FontInfo())
			self.metrics 	= kwargs.pop('metrics',  FontMetrics())
			self.axes 		= kwargs.pop('axes',     [])			# plain list of Axis
			self.masters 	= kwargs.pop('masters',  Masters())
			self.instances 	= kwargs.pop('instances',Instances())
			self.encoding 	= kwargs.pop('encoding', Encoding())
			self.kerning 	= kwargs.pop('kerning',  Kerning())
			self.lib 		= kwargs.pop('lib',      {})

		# Name → index cache for fast glyph lookup
		self._rebuild_cache()

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: "{} {}", {} glyphs, {} masters>'.format(
			self.__class__.__name__,
			self.info.family_name, self.info.style_name,
			len(self.data), len(self.masters))

	def _rebuild_cache(self):
		'''Rebuild the name → index lookup cache.'''
		self._name_index = {g.name: i for i, g in enumerate(self.data)}

	# -- Glyph Container override -------
	# Override append/insert/pop to keep the cache consistent.

	def append(self, item):
		super(Font, self).append(item)
		self._rebuild_cache()

	def insert(self, i, item):
		super(Font, self).insert(i, item)
		self._rebuild_cache()

	def pop(self, i=-1):
		result = super(Font, self).pop(i)
		self._rebuild_cache()
		return result

	# -- Properties ---------------------
	@property
	def name(self):
		return self.info.family_name

	@property
	def glyphs(self):
		return self.data

	@property
	def glyph_names(self):
		return [g.name for g in self.data]

	@property
	def selected_glyphs(self):
		return [g for g in self.data if g.selected]

	# -- Glyph access -------------------
	def glyph(self, name):
		'''Find glyph by name. Returns None if not found.'''
		idx = self._name_index.get(name)
		return self.data[idx] if idx is not None else None

	def __contains__(self, name):
		return name in self._name_index

	def __getitem__(self, key):
		if isinstance(key, str):
			return self.glyph(key)
		return super(Font, self).__getitem__(key)

	# -- Helpers ------------------------
	def unicodes(self, name):
		'''Unicodes for glyph name. Encoding takes priority over glyph.unicodes.'''
		enc = self.encoding.unicodes(name)
		if enc:
			return enc

		g = self.glyph(name)
		return list(g.unicodes) if g and g.unicodes else []

	def get_marks(self, *mark_values):
		marks = set(mark_values)
		return [g for g in self.data if g.mark in marks]

	# -- Serialization ------------------
	# Font.to_XML() produces the font descriptor (font.xml in a .trfont).
	# Glyphs are intentionally excluded — they live in separate .trglyph files.
	# The trfont fileio module handles the full folder round-trip.

	def _to_xml_element(self, exclude_attrs=[]):
		root = ET.Element(self.XML_TAG)

		if self.identifier:
			root.set('identifier', str(self.identifier))

		# Info and metrics as direct children
		root.append(self.info._to_xml_element())
		root.append(self.metrics._to_xml_element())

		# Axes as a wrapper group
		if self.axes:
			axes_elem = ET.SubElement(root, 'axes')
			for axis in self.axes:
				axes_elem.append(axis._to_xml_element())

		# Masters, instances, encoding, kerning as direct children
		if self.masters.data:
			root.append(self.masters._to_xml_element())

		if self.instances.data:
			root.append(self.instances._to_xml_element())

		if self.encoding.data:
			root.append(self.encoding._to_xml_element())

		if self.kerning.data or self.kerning.classes:
			root.append(self.kerning._to_xml_element())

		# Lib
		if self.lib:
			lib_elem = ET.SubElement(root, 'lib')
			for key, val in self.lib.items():
				entry = ET.SubElement(lib_elem, 'entry')
				entry.set('key',   str(key))
				entry.set('value', str(val))

		return root

	@classmethod
	def from_XML(cls, element, include_glyphs=True):
		'''Parse Font from a font.xml element.

		Args:
			element         : XML element or string
			include_glyphs  : if True, parse embedded <glyph> children.
			                  Set False when loading from .trfont where
			                  glyphs come from separate files.
		'''
		if isinstance(element, str):
			element = ET.fromstring(element)

		info 		= FontInfo.from_XML(element.find('info'))
		metrics 	= FontMetrics.from_XML(element.find('metrics'))

		axes = [Axis.from_XML(e) for e in element.findall('./axes/axis')]

		masters_elem = element.find('masters')
		masters = Masters.from_XML(masters_elem) if masters_elem is not None else Masters()

		instances_elem = element.find('instances')
		instances = Instances.from_XML(instances_elem) if instances_elem is not None else Instances()

		encoding_elem = element.find('encoding')
		encoding = Encoding.from_XML(encoding_elem) if encoding_elem is not None else Encoding()

		kerning_elem = element.find('kerning')
		kerning = Kerning.from_XML(kerning_elem) if kerning_elem is not None else Kerning()

		lib = {}
		lib_elem = element.find('lib')
		if lib_elem is not None:
			for entry in lib_elem.findall('entry'):
				lib[entry.get('key', '')] = entry.get('value', '')

		identifier = element.get('identifier', None)

		# Glyphs embedded directly in the element (not the trfont case)
		glyphs = []
		if include_glyphs:
			for g_elem in element.findall('glyph'):
				glyphs.append(Glyph.from_XML(g_elem))

		return cls(
			glyphs,
			identifier 	= identifier,
			info 		= info,
			metrics 	= metrics,
			axes 		= axes,
			masters 	= masters,
			instances 	= instances,
			encoding 	= encoding,
			kerning 	= kerning,
			lib 		= lib,
		)
