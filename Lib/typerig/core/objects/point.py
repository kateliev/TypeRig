# MODULE: TypeRig / Core / Point (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.transform import Transform

# - Init -------------------------------
__version__ = '0.27.2'

# - Classes -----------------------------
class Point(object): 
	def __init__(self, *args, **kwargs):
		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.x, self.y = args[0].x, args[0].y

			if isinstance(args[0], (tuple, list)):
				self.x, self.y = args[0]

		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				self.x, self.y = float(args[0]), float(args[1])
		
		else:
			self.x, self.y = 0., 0.

		self.angle = kwargs.get('angle', 0)
		self.transform = kwargs.get('transform', Transform())
		self.complex_math = kwargs.get('complex', True)

	# -- Operators
	def __add__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(self.x + other.x, self.y + other.y)
		
		elif isinstance(other, int):
			return self.__class__(self.x + other, self.y + other)

		elif isinstance(other, float):
			return self.__class__(self.x + other, self.y + other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x + other[0], self.y + other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print('ERROR:\t Cannot evaluate {} <<{}, {}>> with {}'.format(type(self.__class__), self.x, self.y, type(other)))

	def __sub__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(self.x - other.x, self.y - other.y)
		
		elif isinstance(other, int):
			return self.__class__(self.x - other, self.y - other)

		elif isinstance(other, float):
			return self.__class__(self.x - other, self.y - other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x - other[0], self.y - other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print('ERROR:\t Cannot evaluate {} <<{}, {}>> with {}'.format(type(self.__class__), self.x, self.y, type(other)))

	def __mul__(self, other):
		if isinstance(other, self.__class__):
			if self.complex_math:
				a = complex(self.x , self.y)
				b = complex(other.x, other.y)
				product = a * b
				return self.__class__(product.real, product.imag)
			else:
				return self.__class__(self.x * other.x, self.y * other.x)
		
		elif isinstance(other, int):
			return self.__class__(self.x * other, self.y * other)

		elif isinstance(other, float):
			return self.__class__(self.x * other, self.y * other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x * other[0], self.y * other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print('ERROR:\t Cannot evaluate {} <<{}, {}>> with {}'.format(type(self.__class__), self.x, self.y, type(other)))

	__rmul__ = __mul__

	def __div__(self, other):
		if isinstance(other, self.__class__):
			if self.complex_math:
				a = complex(self.x , self.y)
				b = complex(other.x, other.y)
				product = a / b
				return self.__class__(product.real, product.imag)
			else:
				return self.__class__(self.x // other.x, self.y // other.x)
		
		elif isinstance(other, int):
			return self.__class__(self.x / other, self.y / other)

		elif isinstance(other, float):
			return self.__class__(self.x // other, self.y // other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x // other[0], self.y // other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print('ERROR:\t Cannot evaluate {} <<{}, {}>> with {}'.format(type(self.__class__), self.x, self.y, type(other)))

	__rdiv__ = __div__
	__truediv__ = __div__

	# - Scalar product and cross product --------------------
	# -- Usable in determining angle between unit vectors 
	# -- example: atan2(nextUnit|prevUnit, nextUnit & prevUnit)

	def __and__(self, other):
		'''self & other: Used as for Scalar product'''
		if isinstance(other, self.__class__):
			return self.x * other.x + self.y * other.y
		
		elif isinstance(other, int):
			return self.x * other + self.y * other

		elif isinstance(other, float):
			return self.x * other + self.y * other
		
		elif isinstance(other, tuple):
			return self.x * other[0] + self.y * other[1]
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

	def __or__(self, other):
		'''self | other: Used as for Cross product'''
		if isinstance(other, self.__class__):
			return self.x * other.y - self.y * other.x
		
		elif isinstance(other, int):
			return self.x * other - self.y * other

		elif isinstance(other, float):
			return self.x * other - self.y * other
		
		elif isinstance(other, tuple):
			return self.x * other[1] - self.y * other[0]
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

	def __abs__(self):
		return math.sqrt(self.x**2 + self.y**2)

	def __neg__(self):
		return self.__class__(-self.x, -self.y)

	def __repr__(self):
		return '<{}: {}, {}>'.format(self.__class__.__name__, self.x, self.y)

	def __len__(self):
		return 1

	def __iter__(self):
		for value in self.tuple:
			yield value

	# -- Properties
	@property
	def angle(self):
		return self.__angle

	@angle.setter
	def angle(self, angle):
		self.__angle = angle

	@property
	def magnitude(self):
		return math.hypot(self.x, self.y)

	@property
	def unit(self):
		return self*(1.0/self.magnitude) if self.magnitude != 0 else self.__class__(0,0)

	@property
	def slope(self):
		return float(math.tan(math.radians(90 - self.angle)))

	@property
	def y_intercept(self):
		return float(self.y - self.slope * self.x)

	@property
	def swap(self):
		return self.doSwap()

	@property
	def tuple(self):
		return (self.x, self.y)

	@tuple.setter
	def tuple(self, other):
		self.x, self.y = other

	# -- Solvers
	def solve_width(self, y=0):
		'''Get width - find adjacent X by opposite Y'''
		return self.x + float(self.y - y)/self.slope

	def solve_y(self, x):
		return self.slope * float(x) + self.y_intercept

	def solve_x(self, y):
		return (float(y) - self.y_intercept) / self.slope

	def diff_to(self, other):
		return math.hypot(self.x - other.x, self.y - other.y)

	def angle_to(self, other, add=90):
		''' Angle to another point in radians'''
		b = float(other.x - self.x)
		a = float(other.y - self.y)
		c = self.diff_to(other)
		
		if c == 0: return float('nan')
		if add is None:	return b/c

		cosAngle = math.degrees(math.acos(b/c))
		sinAngle = math.degrees(math.asin(a/c))

		if sinAngle < 0: cosAngle = 360 - cosAngle
			
		return math.radians(cosAngle + add)

	# -- Modifiers
	def doSwap(self):
		return self.__class__(self.y, self.x)

	def doFlip(self, sign=(True,True)):
		return self.__class__(self.x * [1,-1][sign[0]], self.y * [1,-1][sign[1]])

	def doTransform(self, transform=None):
		if transform is None:
			transform = self.transform

		self.x, self.y = transform.applyTransformation(self.x, self.y)

	# -- Specials
	@property
	def string(self):
		x = int(self.x) if isinstance(self.x, float) and self.x.is_integer() else self.x
		y = int(self.y) if isinstance(self.y, float) and self.y.is_integer() else self.y
		return '{0}{2}{1}'.format(x, y, ' ')

	def dumps(self):
		return self.string

	@staticmethod
	def loads(string):
		xs, ys = string.split(' ')
		return Point(float(xs), float(ys))

class Void(Point):
	def __init__(self, *argv):
		super(Void, self).__init__(float('nan'), float('nan'))

if __name__ == '__main__':
	p = Point(10,10)
	t = Transform()
	p.doTransform(t.shift(10,10))
	print(p)