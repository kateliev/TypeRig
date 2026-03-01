# MODULE: TypeRig / Core / Encoding (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member, Container
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
@register_xml_class
class EncodingEntry(Member, XMLSerializable):
	'''Unicode assignment for a single glyph.

	Stores one or more unicode codepoints for a glyph name (or alias).
	Multiple unicodes cover cases like ligatures with multiple encodings,
	or duplicate encodings for legacy compatibility.

	When stored in an Encoding container, entries here take priority
	over unicodes baked into the .trglyph file.

	Constructor:
		EncodingEntry(name, unicodes)
		EncodingEntry('A', [0x0041])
		EncodingEntry('fi', [0xFB01])

	Attributes:
		name (str)      : glyph name or alias as used in this font project
		unicodes (list) : list of unicode codepoints as ints
	'''
	__slots__ = ('name', 'unicodes', 'identifier', 'parent', 'lib')

	XML_TAG = 'entry'
	XML_ATTRS = ['name']		# unicodes handled separately (hex formatting)
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(EncodingEntry, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',	 args[0])
		if len(args) >= 2: kwargs.setdefault('unicodes', args[1])

		self.name 	  = kwargs.pop('name',	   '')
		self.unicodes = kwargs.pop('unicodes', [])
		self.lib 	  = kwargs.pop('lib',	   {})

	# -- Internals ----------------------
	def __repr__(self):
		hex_codes = ['{:04X}'.format(u) for u in self.unicodes]
		return '<{}: "{}" → [{}]>'.format(
			self.__class__.__name__, self.name, ', '.join(hex_codes))

	# -- Properties ---------------------
	@property
	def unicode(self):
		'''First unicode codepoint, or None.'''
		return self.unicodes[0] if self.unicodes else None

	# -- Convenience --------------------
	def set(self, *codepoints):
		'''Set codepoints from ints or hex strings.'''
		parsed = []
		for cp in codepoints:
			if isinstance(cp, int):
				parsed.append(cp)
			else:
				parsed.append(int(str(cp), 16))
		self.unicodes = parsed

	# -- Serialization override ---------
	# unicodes are serialized as space-separated hex strings (no U+ prefix)

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))
		if self.unicodes:
			elem.set('unicodes', ' '.join('{:04X}'.format(u) for u in self.unicodes))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		name = element.get('name', '')
		raw  = element.get('unicodes', '').strip()
		unicodes = [int(tok, 16) for tok in raw.split()] if raw else []

		return cls(name=name, unicodes=unicodes)


@register_xml_class
class Encoding(Container, XMLSerializable):
	'''Unicode encoding map for a font project.

	Container of EncodingEntry objects with dict-like access by glyph name.
	Entries here take priority over unicodes baked into .trglyph files —
	this is the intended design: the encoding file is the authoritative
	unicode source for the font project.

	Supports multiple unicodes per glyph (ligatures, legacy compat) and
	reverse lookup (codepoint → glyph name).

	Usage:
		enc = Encoding()
		enc.set('A', 0x0041)
		enc.set('fi', 0xFB01)
		enc.unicodes('A')        # → [65]
		enc.glyph(0x0041)        # → 'A'
	'''
	__slots__ = ('identifier', 'parent', 'lib')

	XML_TAG = 'encoding'
	XML_ATTRS = []
	XML_CHILDREN = {'entry': 'entries'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', EncodingEntry)
		super(Encoding, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.lib = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: {} entries>'.format(self.__class__.__name__, len(self.data))

	# -- Properties ---------------------
	@property
	def entries(self):
		return self.data

	# -- Dict-like access ---------------
	def get_entry(self, name):
		'''Find entry by glyph name. Returns None if not found.'''
		for entry in self.data:
			if entry.name == name:
				return entry
		return None

	def unicodes(self, name):
		'''Return list of unicode codepoints for glyph name, or [].'''
		entry = self.get_entry(name)
		return entry.unicodes if entry else []

	def unicode(self, name):
		'''Return first unicode codepoint for glyph name, or None.'''
		entry = self.get_entry(name)
		return entry.unicode if entry else None

	def set(self, name, *codepoints):
		'''Set or update encoding for a glyph name.

		Accepts codepoints as ints or hex strings.
		Replaces existing entry if found, otherwise adds new entry.
		'''
		entry = self.get_entry(name)

		if entry is None:
			entry = EncodingEntry(name=name)
			self.data.append(entry)

		entry.set(*codepoints)

	def remove(self, name):
		'''Remove encoding entry for glyph name.'''
		self.data = [e for e in self.data if e.name != name]

	def reverse(self):
		'''Return {codepoint_int: glyph_name} reverse lookup dict.

		Last entry wins on duplicate codepoints — put canonical glyphs last.
		'''
		rev = {}
		for entry in self.data:
			for cp in entry.unicodes:
				rev[cp] = entry.name
		return rev

	def glyph(self, codepoint):
		'''Return glyph name for a codepoint, or None.'''
		return self.reverse().get(codepoint)

	def __contains__(self, name):
		return self.get_entry(name) is not None

	# -- Serialization override ---------
	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		for entry in self.data:
			elem.append(entry._to_xml_element(exclude_attrs))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		entries = [EncodingEntry.from_XML(e) for e in element.findall('entry')]
		return cls(entries)
