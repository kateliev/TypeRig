# MODULE: TypeRig / Core / Transform (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
import copy
from enum import Enum

# - Init -------------------------------
__version__ = '0.27.0'

# - Objects ----------------------------------------------------
class TransformOrigin(Enum):
	# - Tier 1: Bounding box origins (resolved by Bounds.align_matrix)
	BASELINE 		= ('baseline',		'B')
	BOTTOM_LEFT 	= ('bottom_left', 	'BL')
	BOTTOM_MIDDLE 	= ('bottom_middle', 'BM')
	BOTTOM_RIGHT 	= ('bottom_right', 	'BR')
	TOP_LEFT 		= ('top_left', 		'TL')
	TOP_MIDDLE 		= ('top_middle', 	'TM')
	TOP_RIGHT 		= ('top_right', 	'TR')
	CENTER_LEFT		= ('center_left', 	'LM')
	CENTER 			= ('center', 		'C')
	CENTER_RIGHT	= ('center_right', 	'RM')

	# - Tier 2: Metrics origins (resolved by Layer — require advance width/height)
	METRICS_LSB 			= ('metrics_lsb',				'LSB')
	METRICS_RSB 			= ('metrics_rsb',				'RSB')
	METRICS_ADVANCE 		= ('metrics_advance',			'ADV')
	METRICS_ADVANCE_MIDDLE 	= ('metrics_advance_middle',	'ADM')

	# - Tier 3: Outline analysis origins (resolved by Layer — require on-curve node analysis)
	OUTLINE_BOTTOM_LEFT		= ('outline_bottom_left',		'OBL')
	OUTLINE_BOTTOM_RIGHT	= ('outline_bottom_right',		'OBR')
	OUTLINE_BOTTOM_CENTER	= ('outline_bottom_center',		'OBM')
	OUTLINE_TOP_LEFT		= ('outline_top_left',			'OTL')
	OUTLINE_TOP_RIGHT		= ('outline_top_right',			'OTR')
	OUTLINE_TOP_CENTER		= ('outline_top_center',		'OTM')

	# - Tier 4: Statistical origins (resolved by Layer — require area/centroid computation)
	CENTER_OF_MASS			= ('center_of_mass',			'COM')

	@property
	def text(self):
		return self.value[0]

	@property
	def caption(self):
		return self.value[0].replace('_',' ').title()

	@property
	def code(self):
		return self.value[1]

	@property
	def is_bounds(self):
		'''True if this origin can be resolved by Bounds.align_matrix alone'''
		return self.code in ('B', 'BL', 'BM', 'BR', 'TL', 'TM', 'TR', 'LM', 'C', 'RM')

	@property
	def is_metrics(self):
		'''True if this origin requires metrics (advance width) to resolve'''
		return self.code in ('LSB', 'RSB', 'ADV', 'ADM')

	@property
	def is_outline(self):
		'''True if this origin requires outline analysis to resolve'''
		return self.code in ('OBL', 'OBR', 'OBM', 'OTL', 'OTR', 'OTM')

	@property
	def is_statistical(self):
		'''True if this origin requires area/centroid computation to resolve'''
		return self.code in ('COM',)


# -- Affine transformations ------------------------------------
class Transform(object):
	'''Affine transformations (Object)'''
	def __init__(self, xx=1.0, xy=0.0, yx=0.0, yy=1.0, dx=0.0, dy=0.0):
		self.__affine = list(map(float, (xx, xy, yx, yy, dx, dy)))

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
		xx, xy, yx, yy, dx, dy = list(map(float, self.__affine))
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
		xx1, xy1, yx1, yy1, dx1, dy1 = list(map(float, other))
		xx2, xy2, yx2, yy2, dx2, dy2 = list(map(float, self.__affine))
		return self.__class__(
				xx1 * xx2 + xy1 * yx2,
				xx1 * xy2 + xy1 * yy2,
				yx1 * xx2 + yy1 * yx2,
				yx1 * xy2 + yy1 * yy2,
				xx2 * dx1 + yx2 * dy1 + dx2,
				xy2 * dx1 + yy2 * dy1 + dy2)

	def reverseTransform(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = list(map(float, self.__affine))
		xx2, xy2, yx2, yy2, dx2, dy2 = list(map(float, other))
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

	def clone(self):
		return copy.deepcopy(self)

	def __len__(self):
		return 6

	def __getitem__(self, index):
		return self.__affine[index]

	def __getslice__(self, i, j):
		return self.__affine[i:j]

	def __cmp__(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = list(map(float(self.__affine)))
		xx2, xy2, yx2, yy2, dx2, dy2 = list(map(float(other)))
		return cmp((xx1, xy1, yx1, yy1, dx1, dy1), (xx2, xy2, yx2, yy2, dx2, dy2))

	def __hash__(self):
		return hash(self.__affine)

	def __repr__(self):
		return '<%s [%s %s %s %s %s %s]>' %((self.__class__.__name__,) + tuple(map(str, self.__affine)))


if __name__ == '__main__':
	pass
