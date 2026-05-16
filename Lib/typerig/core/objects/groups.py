# MODULE: TypeRig / Core / Groups (Object)
# NOTE: UFO-style groups — flat dict of group name → [glyph names].
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# UFO groups model (mirrors UFO3 groups.plist):
#   - One flat dict, key = group name, value = list of glyph names.
#   - Reserved prefixes carry kerning-class semantics:
#       public.kern1.NAME  → first (left)  side of a kern pair
#       public.kern2.NAME  → second (right) side of a kern pair
#   - Any other name is a free-form user group.
#
# Kerning pairs reference group names directly (no "@" prefix; the
# public.kern1/kern2 prefix is the marker). A KernPair where `first`
# matches a public.kern1.* group name kerns the whole class on the left,
# and similarly for `second` with public.kern2.*.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member, Container
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.1.0'

KERN1_PREFIX = 'public.kern1.'
KERN2_PREFIX = 'public.kern2.'


# - Classes -----------------------------
@register_xml_class
class Group(Member, XMLSerializable):
	'''A single named group of glyph names (UFO groups model).

	Constructor:
		Group(name, members)
		Group('public.kern1.H', ['H', 'I', 'N', 'U'])
		Group('uppercase', ['A', 'B', 'C', ...])

	Attributes:
		name (str)     : group name. public.kern1.* / public.kern2.* are reserved
		                 for kerning classes; anything else is a user group.
		members (list) : ordered list of glyph name strings
	'''
	__slots__ = ('name', 'members', 'identifier', 'parent', 'lib')

	XML_TAG = 'group'
	XML_ATTRS = ['name']	# members serialized as space-separated string

	def __init__(self, *args, **kwargs):
		super(Group, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',    args[0])
		if len(args) >= 2: kwargs.setdefault('members', args[1])

		self.name    = kwargs.pop('name',    '')
		self.members = list(kwargs.pop('members', []))
		self.lib     = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: "{}" {} glyphs>'.format(
			self.__class__.__name__, self.name, len(self.members))

	def __contains__(self, glyph_name):
		return glyph_name in self.members

	def __len__(self):
		return len(self.members)

	# -- Kerning-class predicates -------
	@property
	def is_kern1(self):
		'''True if this group is a first/left kerning class.'''
		return self.name.startswith(KERN1_PREFIX)

	@property
	def is_kern2(self):
		'''True if this group is a second/right kerning class.'''
		return self.name.startswith(KERN2_PREFIX)

	@property
	def is_kern_class(self):
		return self.is_kern1 or self.is_kern2

	@property
	def side(self):
		'''Kerning side: "first", "second", or None for user groups.'''
		if self.is_kern1: return 'first'
		if self.is_kern2: return 'second'
		return None

	# -- Serialization override ---------
	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))
		if self.members:
			elem.set('members', ' '.join(str(m) for m in self.members))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		raw = element.get('members', '').strip()
		members = raw.split() if raw else []

		return cls(
			name    = element.get('name', ''),
			members = members,
		)


@register_xml_class
class Groups(Container, XMLSerializable):
	'''UFO-style flat group dictionary.

	Container of Group objects with dict-like access by group name.
	Holds both user groups and kerning classes (distinguished only by
	the public.kern1.* / public.kern2.* prefix).

	Usage:
		groups = Groups()
		groups.set('uppercase', ['A', 'B', 'C'])
		groups.set('public.kern1.H', ['H', 'I', 'N'])
		groups['public.kern1.H']           # → Group object
		groups.members('uppercase')        # → ['A', 'B', 'C']
		list(groups.kern1())               # → [Group, Group, ...] (kern1 only)
	'''
	__slots__ = ('identifier', 'parent', 'lib')

	XML_TAG = 'groups'
	XML_ATTRS = []
	XML_CHILDREN = {'group': 'data'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Group)
		super(Groups, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.lib = kwargs.pop('lib', {})

	def __repr__(self):
		k1 = sum(1 for g in self.data if g.is_kern1)
		k2 = sum(1 for g in self.data if g.is_kern2)
		other = len(self.data) - k1 - k2
		return '<{}: {} kern1, {} kern2, {} user>'.format(
			self.__class__.__name__, k1, k2, other)

	# -- Dict-like access ---------------
	def get(self, name):
		'''Return Group by name, or None.'''
		for group in self.data:
			if group.name == name:
				return group
		return None

	def __getitem__(self, key):
		if isinstance(key, str):
			return self.get(key)
		return super(Groups, self).__getitem__(key)

	def __contains__(self, name):
		return self.get(name) is not None

	def members(self, name):
		'''Return member list for a group, or []. '''
		group = self.get(name)
		return list(group.members) if group else []

	def set(self, name, members):
		'''Add or replace a group.'''
		existing = self.get(name)
		if existing is not None:
			existing.members = list(members)
		else:
			self.data.append(Group(name, list(members)))

	def remove(self, name):
		'''Remove group by name. No-op if not found.'''
		self.data = [g for g in self.data if g.name != name]

	def names(self):
		return [g.name for g in self.data]

	# -- Kerning class views ------------
	def kern1(self):
		'''Iterate kerning groups for the first (left) side of pairs.'''
		return [g for g in self.data if g.is_kern1]

	def kern2(self):
		'''Iterate kerning groups for the second (right) side of pairs.'''
		return [g for g in self.data if g.is_kern2]

	def user_groups(self):
		'''Iterate non-kerning user groups.'''
		return [g for g in self.data if not g.is_kern_class]
