# MODULE: TypeRig / Core / Axis (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.atom import Member
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
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
	__slots__ = ('name', 'tag', 'minimum', 'default', 'maximum', 'identifier', 'parent', 'lib')

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
		self.lib 	 = kwargs.pop('lib',	 {})

	# -- Internals ----------------------
	def __repr__(self):
		return '<{}: {} [{}] {}..{}..{}>'.format(
			self.__class__.__name__,
			self.name, self.tag,
			self.minimum, self.default, self.maximum)

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
