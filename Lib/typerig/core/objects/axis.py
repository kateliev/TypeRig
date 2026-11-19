# MODULE: TypeRig / Core / Axis (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------

from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
def _fmt(value):
	'''Stable number text: 1000 not 1000.0, so write -> read -> write is byte-stable.'''
	value = float(value)
	return str(int(value)) if value.is_integer() else repr(value)

@register_xml_class
class Axis(Member, XMLSerializable):
	'''A single design axis definition.

	Describes one dimension of a design space — the axis a font
	can vary along (e.g. Weight, Width, Optical Size).

	Constructor:
		Axis(name, tag, minimum, default, maximum)
		Axis(name='Weight', tag='wght', minimum=100, default=400, maximum=900)

	Attributes:
		name (str)     : human-readable axis name
		tag (str)      : four-letter OpenType axis tag
		minimum (float): minimum axis value
		default (float): default axis value
		maximum (float): maximum axis value
	'''
	__slots__ = ('name', 'tag', 'minimum', 'default', 'maximum',
	             'short_name', 'design_minimum', 'design_default', 'design_maximum', 'map')

	XML_TAG = 'axis'
	XML_ATTRS = ['name', 'tag', 'minimum', 'default', 'maximum', 'identifier']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(Axis, self).__init__(*args, **kwargs)

		if len(args) >= 1: kwargs.setdefault('name',	args[0])
		if len(args) >= 2: kwargs.setdefault('tag',		args[1])
		if len(args) >= 3: kwargs.setdefault('minimum',	args[2])
		if len(args) >= 4: kwargs.setdefault('default',	args[3])
		if len(args) >= 5: kwargs.setdefault('maximum',	args[4])

		self.name 	 = kwargs.pop('name',	 '')
		self.tag 	 = kwargs.pop('tag',	 '')
		self.minimum = kwargs.pop('minimum', 0.)
		self.default = kwargs.pop('default', 0.)
		self.maximum = kwargs.pop('maximum', 1000.)

		# FontLab short name (e.g. 'wt'): FL locations are keyed by it.
		self.short_name 	= kwargs.pop('short_name', '')
		# Design-space range; None = same as the user-space value.
		self.design_minimum = kwargs.pop('design_minimum', None)
		self.design_default = kwargs.pop('design_default', None)
		self.design_maximum = kwargs.pop('design_maximum', None)
		# Axis map: [(user, design), ...] (designspace <map input output>).
		self.map 			= [tuple(pair) for pair in kwargs.pop('map', None) or []]

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: {} [{}] {}..{}..{}>'.format(
			self.__class__.__name__,
			self.name, self.tag,
			self.minimum, self.default, self.maximum)

	# -- Serialization override ---------
	# Optional fields only appear when set; old files read unchanged.
	_OPTIONAL = (('short-name', 'short_name', str),
	             ('design-minimum', 'design_minimum', float),
	             ('design-default', 'design_default', float),
	             ('design-maximum', 'design_maximum', float))

	def _to_xml_element(self, exclude_attrs=[]):
		elem = ET.Element(self.XML_TAG)
		elem.set('name', str(self.name))
		elem.set('tag', str(self.tag))
		for attr in ('minimum', 'default', 'maximum'):
			elem.set(attr, _fmt(getattr(self, attr)))
		if getattr(self, 'identifier', None):
			elem.set('identifier', str(self.identifier))
		for xml_key, attr, kind in self._OPTIONAL:
			value = getattr(self, attr, None)
			if value not in (None, ''):
				elem.set(xml_key, value if kind is str else _fmt(value))
		if self.map:
			map_elem = ET.SubElement(elem, 'map')
			for user, design in self.map:
				entry = ET.SubElement(map_elem, 'entry')
				entry.set('input', _fmt(user))
				entry.set('output', _fmt(design))
		return elem

	@classmethod
	def from_XML(cls, element):
		if isinstance(element, str):
			element = ET.fromstring(element)

		kwargs = dict(
			name 		= element.get('name', ''),
			tag 		= element.get('tag', ''),
			minimum 	= float(element.get('minimum', 0.)),
			default 	= float(element.get('default', 0.)),
			maximum 	= float(element.get('maximum', 1000.)),
			identifier 	= element.get('identifier', None),
		)
		for xml_key, attr, kind in cls._OPTIONAL:
			raw = element.get(xml_key)
			if raw is not None:
				kwargs[attr] = kind(raw)
		kwargs['map'] = [(float(e.get('input')), float(e.get('output'))) for e in element.findall('./map/entry')]
		return cls(**kwargs)

	# -- Properties ---------------------
	@property
	def range(self):
		return (self.minimum, self.maximum)

	def normalize(self, value):
		'''Normalize a user-space value to 0..1 range relative to this axis.'''
		span = self.maximum - self.minimum
		if span == 0:
			return 0.
		return (value - self.minimum) / span
