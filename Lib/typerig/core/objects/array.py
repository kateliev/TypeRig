# MODULE: TypeRig / Core / Array (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

try: # Py3+
	from collections.abc import Sequence
except ImportError: # Py2+
	from collections import Sequence

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.collection import CustomList
from typerig.core.objects.point import Point, Void
from typerig.core.objects.line import Line

# - Init -------------------------------
__version__ = '0.26.8'

# - Classes -----------------------------
# -- Point Collections ------------------
class PointArray(CustomList):
	def __init__(self, data, useVoid=False):
		if not isMultiInstance(data, Point):
			data = [Point(item) for item in data]

		super(PointArray, self).__init__(data)
		self.__useVoid = useVoid

	# - Internals
	def __add__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__([item[0] + item[1] for item in zip(self.data, other.data)])
		else:
			return self.__class__([item + other for item in self.data])

	__radd__ = __add__
	__iadd__ = None
	
	def __sub__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__([item[0] - item[1] for item in zip(self.data, other.data)])
		else:
			return self.__class__([item - other for item in self.data])

	__rsub__ = __sub__
	__isub__ = None
	
	def __mul__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__([item[0] * item[1] for item in zip(self.data, other.data)])
		else:
			return self.__class__([item * other for item in self.data])

	__rmul__ = __mul__
	__imul__ = None

	def __div__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__([item[0] / item[1] for item in zip(self.data, other.data)])
		else:
			return self.__class__([item / other for item in self.data])

	__rdiv__ = __div__
	__truediv__ = __div__
	__idiv__ = None

	def __delitem__(self, i): 
		if self.__useVoid:
			self.data[i] = Void()
		else:
			del self.data[i]

	def __repr__(self):
		return '<Point Array: {}>'.format(self.data)

	# - Properties 
	@property
	def tuple(self):
		return tuple((item.tuple for item in self.data))
	
	@property
	def x_tuple(self):
		return tuple((item.x for item in self.data))

	@property
	def y_tuple(self):
		return tuple((item.y for item in self.data))

	@property
	def x(self):
		return min(self.x_tuple)

	@property
	def y(self):
		return min(self.y_tuple)

	@property
	def height(self):
		return max(self.y_tuple) - min(self.y_tuple)

	@property
	def width(self):
		return max(self.x_tuple) - min(self.x_tuple)

	@property
	def center(self):
		return (self.width/2 + self.x, self.height/2 + self.y)

	@property
	def bounds(self):
		return (self.x, self.y, self.width, self.height)

	@property
	def diffs(self):
		return [self.data[i].diff_to(self.data[i+1]) for i in range(len(self.data) - 1)]

	@property
	def angles(self):
		return [self.data[i].angle_to(self.data[i+1]) for i in range(len(self.data) - 1)]

	def pop(self, i=-1): 
		if self.__useVoid:
			ret_item = self.data[i]
			self.data[i] = Void()
			return ret_item
		else:
			return self.data.pop(i)

	def remove(self, item): 
		if self.__useVoid:
			i = self.data.index(item)
			self.data[i] = Void()
		else:
			self.data.remove(item)

	def doTransform(self, transform=None):
		for item in self.data:
			item.doTransform(transform)