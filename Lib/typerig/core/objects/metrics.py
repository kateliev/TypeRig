# MODULE: TypeRig / Core / Metrics (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# FontMetrics lives in its own module so both Font (font-level metrics)
# and Master (per-master metrics) can use it without a circular import.
# typerig.core.objects.font re-exports it.

# - Dependencies ------------------------
from xml.etree import ElementTree as ET

from typerig.core.objects.atom import Member
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.2.0'

# - Helpers -----------------------------
def _intish(value):
	'''Integral values as int (1000, not 1000.0); real fractions stay float.
	FontLab hands metrics over as floats (674.0); a fraction must survive.'''
	value = float(value)
	return int(value) if value.is_integer() else value

# - Classes -----------------------------
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
	__slots__ = ('upm', 'ascender', 'descender', 'x_height', 'cap_height', 'line_gap')

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

		self.upm 		= _intish(kwargs.pop('upm',		    1000))
		self.ascender 	= _intish(kwargs.pop('ascender',    800))
		self.descender 	= _intish(kwargs.pop('descender',   -200))
		self.x_height 	= _intish(kwargs.pop('x_height',    500))
		self.cap_height = _intish(kwargs.pop('cap_height',  700))
		self.line_gap 	= _intish(kwargs.pop('line_gap',    0))

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
			return _intish(val) if val is not None else default

		return cls(
			upm 		= _int('upm', 		 1000),
			ascender 	= _int('ascender',   800),
			descender 	= _int('descender',  -200),
			x_height 	= _int('x-height',   500),
			cap_height 	= _int('cap-height', 700),
			line_gap 	= _int('line-gap',   0),
		)
