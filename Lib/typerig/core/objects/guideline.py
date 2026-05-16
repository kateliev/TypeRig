# MODULE: TypeRig / Core / Guideline (Object)
# NOTE: UFO-spec guideline (per-glyph and per-layer).
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# UFO guideline model (mirrors UFO3 GLIF <guideline/>):
#
#   - only x present  → vertical line at x
#   - only y present  → horizontal line at y
#   - both x and y    → line through (x, y) at `angle` degrees
#
# Attributes: x, y, angle, name, color, identifier — all optional per the
# spec. We keep this minimal on purpose; FontLab's guideline API is
# notoriously inconsistent and TR↔FL translation happens in the proxy
# layer, not here.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.atom import Member
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
@register_xml_class
class Guideline(Member, XMLSerializable):
	'''A single guideline (UFO model).

	Constructor:
		Guideline(x=None, y=None, angle=None, name=None, color=None, identifier=None)

	Examples:
		Guideline(x=200)                  # vertical guide at x=200
		Guideline(y=500)                  # horizontal guide at y=500
		Guideline(x=100, y=200, angle=45) # angled guide through (100,200)

	Attributes:
		x, y (number, optional)
		angle (number, optional) : only meaningful when both x and y are set
		name (str, optional)
		color (str, optional)    : "r,g,b,a" with components in [0,1]
		identifier (str, optional)
	'''
	__slots__ = ('x', 'y', 'angle', 'name', 'color', 'identifier', 'parent', 'lib')

	XML_TAG = 'guideline'
	XML_ATTRS = ['x', 'y', 'angle', 'name', 'color', 'identifier']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(Guideline, self).__init__(*args, **kwargs)
		self.x          = kwargs.pop('x',          None)
		self.y          = kwargs.pop('y',          None)
		self.angle      = kwargs.pop('angle',      None)
		self.name       = kwargs.pop('name',       None)
		self.color      = kwargs.pop('color',      None)
		self.identifier = kwargs.pop('identifier', None)
		self.lib        = kwargs.pop('lib',        {})

	def __repr__(self):
		parts = []
		if self.x is not None: parts.append('x={}'.format(self.x))
		if self.y is not None: parts.append('y={}'.format(self.y))
		if self.angle is not None: parts.append('angle={}'.format(self.angle))
		if self.name: parts.append('"{}"'.format(self.name))
		return '<{}: {}>'.format(self.__class__.__name__, ', '.join(parts) or 'empty')

	# -- Properties ---------------------
	@property
	def is_vertical(self):
		'''Vertical line at x — only x is set (or angle == 90 with both).'''
		if self.x is not None and self.y is None:
			return True
		if self.x is not None and self.y is not None and self.angle is not None:
			return self.angle % 180 == 90
		return False

	@property
	def is_horizontal(self):
		'''Horizontal line at y — only y is set (or angle == 0 with both).'''
		if self.y is not None and self.x is None:
			return True
		if self.x is not None and self.y is not None and self.angle is not None:
			return self.angle % 180 == 0
		return False
