# MODULE: TypeRig / Core / Instance (Object)
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
from typerig.core.objects.master import _location_to_element, _location_from_element

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
@register_xml_class
class Instance(Member, XMLSerializable):
	'''A named static instance — one fixed point in design space.

	Instances are named positions on the design axes that represent
	common variants a designer wants to generate or preview
	(e.g. "SemiBold", "Condensed Bold").

	Constructor:
		Instance(name, location, identifier)

	Attributes:
		name (str)      : instance name (e.g. "SemiBold")
		location (dict) : {axis_name: value, ...}
		identifier (str): optional unique id
	'''
	__slots__ = ('name', 'location', 'identifier', 'parent', 'lib')

	XML_TAG = 'instance'
	XML_ATTRS = ['name', 'identifier']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(Instance, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',	 args[0])
		if len(args) >= 2: kwargs.setdefault('location', args[1])

		self.name 	  = kwargs.pop('name',	   '')
		self.location = kwargs.pop('location', {})
		self.lib 	  = kwargs.pop('lib',	   {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: "{}" {}>'.format(
			self.__class__.__name__, self.name, self.location)

	# -- Serialization override ---------
	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))

		if self.identifier:
			elem.set('identifier', str(self.identifier))

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
			location 	= _location_from_element(element),
		)


@register_xml_class
class Instances(Container, XMLSerializable):
	'''Ordered list of Instance objects.'''
	__slots__ = ('identifier', 'parent', 'lib')

	XML_TAG = 'instances'
	XML_ATTRS = []
	XML_CHILDREN = {'instance': 'instances'}
	XML_LIB_ATTRS = []

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Instance)
		super(Instances, self).__init__(data, default_factory=factory, **kwargs)

		if not kwargs.pop('proxy', False):
			self.lib = kwargs.pop('lib', {})

	def __repr__(self):
		return '<{}: {} instances>'.format(self.__class__.__name__, len(self.data))

	@property
	def instances(self):
		return self.data

	def get(self, name):
		'''Find instance by name or identifier.'''
		for inst in self.data:
			if inst.name == name or inst.identifier == name:
				return inst
		return None

	# -- Serialization override ---------
	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		for inst in self.data:
			elem.append(inst._to_xml_element(exclude_attrs))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		instances = [Instance.from_XML(e) for e in element.findall('instance')]
		return cls(instances)
