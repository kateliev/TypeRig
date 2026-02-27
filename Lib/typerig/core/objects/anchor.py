# MODULE: TypeRig / Core / Anchor (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.point import Point
from typerig.core.objects.atom import Member

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

# - Init -------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
@register_xml_class
class Anchor(Member, XMLSerializable):
	'''A named position marker for mark attachment, component placement, 
	cursive connection and similar glyph-level positioning tasks.
	'''
	__slots__ = ('x', 'y', 'name', 'color', 'selected', 'identifier', 'parent', 'lib')

	XML_TAG = 'anchor'
	XML_ATTRS = ['x', 'y', 'name', 'color', 'identifier']
	XML_CHILDREN = {}
	XML_LIB_ATTRS = []

	def __init__(self, *args, **kwargs):
		super(Anchor, self).__init__(*args, **kwargs)

		# - Position
		x = y = 0.0

		if len(args) == 1:
			arg = args[0]

			if isinstance(arg, self.__class__):
				x, y = arg.x, arg.y
				kwargs.setdefault('name', arg.name)
				kwargs.setdefault('color', arg.color)

			elif isinstance(arg, Point):
				x, y = arg.x, arg.y

			elif isinstance(arg, (tuple, list)) and len(arg) >= 2:
				x, y = float(arg[0]), float(arg[1])
				
				if len(arg) >= 3:
					kwargs.setdefault('name', arg[2])

			else:
				raise TypeError('Single argument must be an Anchor, Point, or (x, y[, name]) tuple/list')

		elif len(args) == 2:
			if all(isinstance(a, (int, float)) for a in args):
				x, y = float(args[0]), float(args[1])
			else:
				raise TypeError('Two arguments must be numeric (x, y)')

		elif len(args) == 3:
			if all(isinstance(a, (int, float)) for a in args[:2]):
				x, y = float(args[0]), float(args[1])
				kwargs.setdefault('name', args[2])
			else:
				raise TypeError('Three arguments must be (x, y, name)')

		elif len(args) > 3:
			raise TypeError('Expected 0, 1, 2, or 3 positional arguments')

		# - Position
		self.x = kwargs.pop('x', x)
		self.y = kwargs.pop('y', y)

		# - Metadata
		self.name = kwargs.pop('name', '')
		self.color = kwargs.pop('color', None)
		self.selected = kwargs.pop('selected', False)

	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, x={}, y={}>'.format(
			self.__class__.__name__, self.name, self.x, self.y)

	def __eq__(self, other):
		if isinstance(other, self.__class__):
			return self.x == other.x and self.y == other.y and self.name == other.name
		return NotImplemented

	def __ne__(self, other):
		result = self.__eq__(other)
		if result is NotImplemented:
			return result
		return not result

	# -- Properties -----------------------------
	@property
	def point(self):
		'''Return position as Point for math operations'''
		return Point(self.x, self.y)

	@point.setter
	def point(self, other):
		if isinstance(other, Point):
			self.x = other.x
			self.y = other.y
		elif isinstance(other, (tuple, list)) and len(other) == 2:
			self.x = float(other[0])
			self.y = float(other[1])

	@property
	def tuple(self):
		'''Return position as (x, y) tuple'''
		return (self.x, self.y)

	# -- Functions ------------------------------
	def shift(self, delta_x, delta_y):
		'''Shift anchor by given amount'''
		self.x += delta_x
		self.y += delta_y

	def scale(self, sx, sy, center=(0., 0.)):
		'''Scale anchor position around center'''
		cx, cy = center
		self.x = cx + (self.x - cx) * sx
		self.y = cy + (self.y - cy) * sy

	# -- IO Format ------------------------------
	@classmethod
	def from_tuple(cls, coords, **kwargs):
		'''Create Anchor from (x, y) or (x, y, name) tuple'''
		return cls(*coords, **kwargs)

	@classmethod
	def from_point(cls, point, **kwargs):
		'''Create Anchor from Point object'''
		return cls(point.x, point.y, **kwargs)


if __name__ == '__main__':
	from pprint import pprint
	section = lambda s: '\n+{0}\n+ {1}\n+{0}'.format('-'*30, s)

	a = Anchor(100, 200, name='top')
	print(section('Anchor'))
	print(a)
	print('point:', a.point)
	print('tuple:', a.tuple)

	print(section('Anchor Math via Point'))
	print('shifted point:', a.point + Point(10, 20))

	print(section('Anchor Shift'))
	a.shift(5, 10)
	print(a)

	print(section('Anchor XML'))
	print(a.to_XML())

	print(section('Anchor Clone'))
	b = a.clone()
	print(b)
	print('equal:', a == b)
