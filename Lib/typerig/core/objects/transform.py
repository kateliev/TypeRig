# MODULE: TypeRig / Core / Transform (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


# - Dependencies ------------------------
from __future__ import print_function, absolute_import
import math

# - Init -------------------------------
__version__ = '0.26.0'

# - Objects ----------------------------------------------------
# -- Affine transformations ------------------------------------
class Transform(object):
	'''Affine transformations (Object)'''
	def __init__(self, xx=1.0, xy=0.0, yx=0.0, yy=1.0, dx=0.0, dy=0.0):
		self.__affine = map(float, (xx, xy, yx, yy, dx, dy))

	def __normSinCos(self, v):
		EPSILON = 1e-15
		ONE_EPSILON = 1.0 - EPSILON
		MINUS_ONE_EPSILON = -1.0 + EPSILON

		if abs(v) < EPSILON:
			v = 0.0
		elif v > ONE_EPSILON:
			v = 1.0
		elif v < MINUS_ONE_EPSILON:
			v = -1.0
		return v

	def applyTransformation(self, x, y):
		x, y = float(x), float(y)
		xx, xy, yx, yy, dx, dy = map(float, self.__affine)
		return (xx * x + yx * y + dx, xy * x + yy * y + dy)

	def translate(self, dx, dy):
		return self.transform((1.0, 0.0, 0.0, 1.0, float(dx), float(dy)))

	def shift(self, dx, dy):
		return self.translate(dx, dy)

	def scale(self, sx, sy):
		return self.transform((float(sx), 0.0, 0.0, float(sy), 0.0, 0.0))

	def rotate(self, angle):
		c = self.__normSinCos(math.cos(math.radians(angle)))
		s = self.__normSinCos(math.sin(math.radians(angle)))
		return self.transform((c, s, -s, c, 0.0, 0.0))

	def skew(self, ax, ay):
		return self.transform((1.0, math.tan(math.radians(ay)), math.tan(math.radians(ax)), 1.0, 0.0, 0.0))

	def transform(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float, other)
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float, self.__affine)
		return self.__class__(
				xx1 * xx2 + xy1 * yx2,
				xx1 * xy2 + xy1 * yy2,
				yx1 * xx2 + yy1 * yx2,
				yx1 * xy2 + yy1 * yy2,
				xx2 * dx1 + yx2 * dy1 + dx2,
				xy2 * dx1 + yy2 * dy1 + dy2)

	def reverseTransform(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float, self.__affine)
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float, other)
		return self.__class__(
				xx1 * xx2 + xy1 * yx2,
				xx1 * xy2 + xy1 * yy2,
				yx1 * xx2 + yy1 * yx2,
				yx1 * xy2 + yy1 * yy2,
				xx2 * dx1 + yx2 * dy1 + dx2,
				xy2 * dx1 + yy2 * dy1 + dy2)

	def inverse(self):
		if self.__affine == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
			return self

		xx, xy, yx, yy, dx, dy = self.__affine
		det = float(xx*yy - yx*xy)

		xx, xy, yx, yy = yy / det, -xy / det, -yx / det, xx / det
		dx, dy = -xx * dx - yx * dy, - xy * dx - yy * dy

		return self.__class__(xx, xy, yx, yy, dx, dy)

	def __len__(self):
		return 6

	def __getitem__(self, index):
		return self.__affine[index]

	def __getslice__(self, i, j):
		return self.__affine[i:j]

	def __cmp__(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float(self.__affine))
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float(other))
		return cmp((xx1, xy1, yx1, yy1, dx1, dy1), (xx2, xy2, yx2, yy2, dx2, dy2))

	def __hash__(self):
		return hash(self.__affine)

	def __repr__(self):
		return '<%s [%s %s %s %s %s %s]>' %((self.__class__.__name__,) + tuple(map(str, self.__affine)))

# -- Adaptive scaling ------------------------------------
class AdaptiveScale(object):
	#import typerig.core.func.transform as utils
	#import typerig.core.objects.array as arrays

	def __init__(self, point_arrays, stem_arrays):
		pass

if __name__ == '__main__':
	a = AdaptiveScale((10,10), (10,20))