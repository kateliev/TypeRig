# MODULE: TypeRig / Core / Kern (Object)
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
class KernPair(Member, XMLSerializable):
	'''A single kerning pair — first, second, value.

	Both first and second can reference glyph names or kern class names.
	Kern class names are conventionally prefixed with "@" to distinguish
	them from glyph names (e.g. "@H_left", "@V_right").

	Constructor:
		KernPair(first, second, value)
		KernPair('A', 'V', -50)
		KernPair('@H_left', '@A_right', -30)

	Attributes:
		first (str)  : left glyph or class name
		second (str) : right glyph or class name
		value (int)  : kern value in font units
	'''
	__slots__ = ('first', 'second', 'value', 'identifier', 'parent', 'lib')

	XML_TAG = 'pair'
	XML_ATTRS = ['first', 'second', 'value']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(KernPair, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('first',  args[0])
		if len(args) >= 2: kwargs.setdefault('second', args[1])
		if len(args) >= 3: kwargs.setdefault('value',  args[2])

		self.first  = kwargs.pop('first',  '')
		self.second = kwargs.pop('second', '')
		self.value  = int(kwargs.pop('value', 0))
		self.lib    = kwargs.pop('lib', {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: "{}" + "{}" = {}>'.format(
			self.__class__.__name__, self.first, self.second, self.value)

	def __eq__(self, other):
		if isinstance(other, self.__class__):
			return self.first == other.first and self.second == other.second
		return NotImplemented

	def __hash__(self):
		return hash((self.first, self.second))

	# -- Properties ---------------------
	@property
	def is_class_pair(self):
		'''True if either side references a kern class (starts with @).'''
		return self.first.startswith('@') or self.second.startswith('@')

	@property
	def key(self):
		return (self.first, self.second)


@register_xml_class
class KernClass(Member, XMLSerializable):
	'''A kern class — a named group of glyphs that kern together.

	Kern classes are used on one side of a kern pair. By convention
	the class name is prefixed with "@". The side attribute declares
	whether this class is used as the first (left) or second (right)
	member of a pair.

	Constructor:
		KernClass(name, members, side)
		KernClass('@H_left', ['H', 'I', 'N', 'U'], side='first')

	Attributes:
		name (str)      : class name, conventionally @prefixed
		members (list)  : ordered list of glyph name strings
		side (str)      : 'first' or 'second'
	'''
	__slots__ = ('name', 'members', 'side', 'identifier', 'parent', 'lib')

	XML_TAG = 'class'
	XML_ATTRS = ['name', 'side']	# members serialized as space-separated string
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(KernClass, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',    args[0])
		if len(args) >= 2: kwargs.setdefault('members', args[1])
		if len(args) >= 3: kwargs.setdefault('side',    args[2])

		self.name    = kwargs.pop('name',    '')
		self.members = list(kwargs.pop('members', []))
		self.side    = kwargs.pop('side',    'first')	# 'first' or 'second'
		self.lib     = kwargs.pop('lib', {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: "{}" [{}] {} glyphs>'.format(
			self.__class__.__name__, self.name, self.side, len(self.members))

	def __contains__(self, glyph_name):
		return glyph_name in self.members

	# -- Serialization override ---------
	# members are stored as a space-separated string attribute

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))
		elem.set('side', str(self.side))
		if self.members:
			elem.set('members', ' '.join(str(m) for m in self.members))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		raw_members = element.get('members', '').strip()
		members = raw_members.split() if raw_members else []

		return cls(
			name    = element.get('name',    ''),
			side    = element.get('side',    'first'),
			members = members,
		)


@register_xml_class
class Kerning(Container, XMLSerializable):
	'''Kerning table — kern pairs and kern classes.

	Container of KernPair objects. Also holds KernClass objects in
	a separate list (not as Container children — classes are not pairs).

	Dict-like access: kerning[('A', 'V')] → kern value or None.
	Class lookup for composing class-based kern pairs is intentionally
	left to the caller — Kerning stores raw data, not resolved lookups.

	Usage:
		kern = Kerning()
		kern.add_pair('A', 'V', -50)
		kern.add_class('@H_left', ['H', 'I', 'N'], side='first')
		kern[('@H_left', '@A_right')] = -30
		kern.value('A', 'V')    # → -50
	'''
	__slots__ = ('classes', 'identifier', 'parent', 'lib')

	XML_TAG = 'kerning'
	XML_ATTRS = []
	XML_CHILDREN = {'pair': 'pairs'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', KernPair)
		super(Kerning, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.classes = kwargs.pop('classes', [])
			self.lib     = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: {} pairs, {} classes>'.format(
			self.__class__.__name__, len(self.data), len(self.classes))

	def __getitem__(self, key):
		# Support both index access (Container) and (first, second) tuple access
		if isinstance(key, tuple):
			entry = self.get_pair(*key)
			return entry.value if entry else None
		return super(Kerning, self).__getitem__(key)

	def __setitem__(self, key, value):
		if isinstance(key, tuple):
			first, second = key
			entry = self.get_pair(first, second)
			if entry is not None:
				entry.value = int(value)
			else:
				self.add_pair(first, second, value)
		else:
			super(Kerning, self).__setitem__(key, value)

	# -- Properties ---------------------
	@property
	def pairs(self):
		return self.data

	# -- Pair management ----------------
	def add_pair(self, first, second, value):
		'''Add or overwrite a kern pair.'''
		existing = self.get_pair(first, second)
		if existing is not None:
			existing.value = int(value)
		else:
			self.data.append(KernPair(first, second, int(value)))

	def remove_pair(self, first, second):
		'''Remove a kern pair by first/second. No-op if not found.'''
		self.data = [p for p in self.data
		             if not (p.first == first and p.second == second)]

	def get_pair(self, first, second):
		'''Return KernPair for (first, second), or None.'''
		for pair in self.data:
			if pair.first == first and pair.second == second:
				return pair
		return None

	def value(self, first, second):
		'''Return kern value for (first, second), or None.'''
		pair = self.get_pair(first, second)
		return pair.value if pair else None

	# -- Class management ---------------
	def add_class(self, name, members, side='first'):
		'''Add or replace a kern class.'''
		existing = self.get_class(name)
		if existing is not None:
			existing.members = list(members)
			existing.side = side
		else:
			self.classes.append(KernClass(name, members, side=side))

	def remove_class(self, name):
		'''Remove kern class by name. No-op if not found.'''
		self.classes = [c for c in self.classes if c.name != name]

	def get_class(self, name):
		'''Return KernClass by name, or None.'''
		for kc in self.classes:
			if kc.name == name:
				return kc
		return None

	# -- Serialization override ---------
	# Pairs go in as XML_CHILDREN would handle them; classes are
	# separate <class> children. Override to write both.

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)

		for pair in self.data:
			elem.append(pair._to_xml_element(exclude_attrs))

		for kern_class in self.classes:
			elem.append(kern_class._to_xml_element(exclude_attrs))

		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		pairs   = [KernPair.from_XML(e)  for e in element.findall('pair')]
		classes = [KernClass.from_XML(e) for e in element.findall('class')]

		obj = cls(pairs)
		obj.classes = classes
		return obj
