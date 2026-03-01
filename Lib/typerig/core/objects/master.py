# MODULE: TypeRig / Core / Master (Object)
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
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class, _convert_xml_attr

# - Init --------------------------------
__version__ = '0.1.0'

# - Helpers -----------------------------
def _location_to_element(location):
	'''Serialize a {axis_name: value} dict as a <location> element.'''
	elem = ET.Element('location')
	for axis_name, value in location.items():
		dim = ET.SubElement(elem, 'dim')
		dim.set('name',  str(axis_name))
		dim.set('value', str(value))
	return elem

def _location_from_element(parent_elem):
	'''Parse a <location> child element into a {axis_name: value} dict.'''
	loc_elem = parent_elem.find('location')
	if loc_elem is None:
		return {}
	return {
		dim.get('name', ''): _convert_xml_attr(dim.get('value', '0'))
		for dim in loc_elem.findall('dim')
	}

# - Classes -----------------------------
@register_xml_class
class Master(Member, XMLSerializable):
	'''A single master definition — one point in design space.

	Each master maps a location on the design axes to a named layer
	inside every .trglyph file. The layer_name must match the actual
	layer name stored in the glyph. If a glyph is missing that layer,
	the default master is used as fallback (UFO convention).

	Constructor:
		Master(name, layer_name, location, identifier, is_default)

	Attributes:
		name (str)       : master name (e.g. "Regular", "Bold")
		layer_name (str) : matching layer name inside .trglyph files
		location (dict)  : {axis_name: value, ...}
		is_default (bool): fallback master for sparse glyphs
	'''
	__slots__ = ('name', 'layer_name', 'location', 'is_default', 'identifier', 'parent', 'lib')

	XML_TAG = 'master'
	# location and is_default are handled in custom _to_xml_element / from_XML
	XML_ATTRS = ['name', 'identifier', 'layer_name']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(Master, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',		args[0])
		if len(args) >= 2: kwargs.setdefault('layer_name',	args[1])
		if len(args) >= 3: kwargs.setdefault('location',	args[2])

		self.name 		 = kwargs.pop('name',		 '')
		self.layer_name  = kwargs.pop('layer_name',  self.name)
		self.location 	 = kwargs.pop('location',	 {})
		self.is_default  = kwargs.pop('is_default',  False)
		self.lib 		 = kwargs.pop('lib',		 {})

	# -- Internals ----------------------
	def __repr__(self):
		default_flag = ' [default]' if self.is_default else ''
		return '<{}: "{}"{} layer="{}" {}>'.format(
			self.__class__.__name__,
			self.name, default_flag, self.layer_name, self.location)

	# -- Serialization override ---------
	# location needs a <location><dim.../></location> wrapper that
	# xmlio's flat XML_CHILDREN can't produce — handle it manually.

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))

		if self.identifier:
			elem.set('identifier', str(self.identifier))

		# layer_name serializes as 'layer' attribute for readability
		elem.set('layer', str(self.layer_name))

		if self.is_default:
			elem.set('default', 'true')

		if self.location:
			elem.append(_location_to_element(self.location))

		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		return cls(
			name 		= element.get('name', 		''),
			identifier 	= element.get('identifier',	None),
			layer_name 	= element.get('layer', 		element.get('name', '')),
			is_default 	= element.get('default', 'false').lower() == 'true',
			location 	= _location_from_element(element),
		)


@register_xml_class
class Masters(Container, XMLSerializable):
	'''Ordered list of Master objects.

	Container of Master objects. The first master marked is_default=True
	is the fallback for sparse glyphs; if none is marked, first master wins.
	'''
	__slots__ = ('identifier', 'parent', 'lib')

	XML_TAG = 'masters'
	XML_ATTRS = []
	XML_CHILDREN = {'master': 'masters'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Master)
		super(Masters, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.lib = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: {} masters>'.format(self.__class__.__name__, len(self.data))

	# -- Accessor -----------------------
	@property
	def masters(self):
		return self.data

	@property
	def default(self):
		'''Return the default master (flagged or first).'''
		for m in self.data:
			if m.is_default:
				return m
		return self.data[0] if self.data else None

	def get(self, name):
		'''Find master by name or identifier.'''
		for m in self.data:
			if m.name == name or m.identifier == name:
				return m
		return None

	# -- Serialization override ---------
	# Masters is a simple wrapper — use standard xmlio but call
	# each child's own _to_xml_element so location is handled correctly.

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		for master in self.data:
			elem.append(master._to_xml_element(exclude_attrs))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		masters = [Master.from_XML(e) for e in element.findall('master')]
		return cls(masters)
