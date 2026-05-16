# MODULE: TypeRig / Core / Kern (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# UFO-aligned kerning model:
#   - Kerning holds only pairs (KernPair).
#   - Either side of a pair may reference a glyph name OR a group name
#     from Font.groups. Group-based pair sides use the UFO reserved
#     prefixes public.kern1.* (first/left) and public.kern2.* (second/right).
#   - Kerning classes live in Font.groups (see core/objects/groups.py),
#     not here. Removing KernClass aligns this format with UFO and gives
#     a single source of truth for class membership.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member, Container
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class
from typerig.core.objects.groups import KERN1_PREFIX, KERN2_PREFIX

# - Init --------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
@register_xml_class
class KernPair(Member, XMLSerializable):
	'''A single kerning pair — first, second, value.

	Each side may name a glyph or a group from Font.groups. Group sides
	use the UFO reserved prefixes:
	  - public.kern1.NAME on the first  (left)  side
	  - public.kern2.NAME on the second (right) side

	Constructor:
		KernPair(first, second, value)
		KernPair('A', 'V', -50)
		KernPair('public.kern1.H', 'public.kern2.A', -30)

	Attributes:
		first (str)  : left glyph or kern1 group name
		second (str) : right glyph or kern2 group name
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
	def first_is_group(self):
		return self.first.startswith(KERN1_PREFIX)

	@property
	def second_is_group(self):
		return self.second.startswith(KERN2_PREFIX)

	@property
	def is_class_pair(self):
		'''True if either side references a kern group.'''
		return self.first_is_group or self.second_is_group

	@property
	def key(self):
		return (self.first, self.second)


@register_xml_class
class Kerning(Container, XMLSerializable):
	'''Kerning table — flat list of kern pairs (UFO model).

	Dict-like access: kerning[('A', 'V')] → kern value or None.
	Class membership is resolved against Font.groups by the caller;
	this object stores raw pairs only.

	Usage:
		kern = Kerning()
		kern.add_pair('A', 'V', -50)
		kern[('public.kern1.H', 'public.kern2.A')] = -30
		kern.value('A', 'V')    # → -50
	'''
	__slots__ = ('identifier', 'parent', 'lib')

	XML_TAG = 'kerning'
	XML_ATTRS = []
	# 'pair' children deserialize into `data` (the Container backing list),
	# exposed through the .pairs property.
	XML_CHILDREN = {'pair': 'data'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', KernPair)
		super(Kerning, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.lib = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: {} pairs>'.format(self.__class__.__name__, len(self.data))

	def __getitem__(self, key):
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
