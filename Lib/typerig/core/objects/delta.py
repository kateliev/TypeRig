# MODULE: TypeRig / Core / Delta (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


# - Dependencies ------------------------
from __future__ import print_function, absolute_import
from collections import Sequence
import math

import typerig.core.func.transform as utils
from typerig.core.objects.point import Point, Void
from typerig.core.objects.array import PointArray

# - Init -------------------------------
__version__ = '0.10.0'

# - Objects ------------------------------------
# -- Interpolation ------------------------------
class DeltaArray(Sequence):
	def __init__(self, data):
		# - Init
		assert len(data) > 1, 'ERROR:\tNot enough input arrays! Minimum 2 required!'
		check_data = [len(item) for item in data]
		assert len(check_data) == check_data.count(min(check_data)), 'ERROR:\tInput arrays dimensions do not match!'

		self.data = [PointArray(item) for item in data]
				
	# - Internals
	def __getitem__(self, i): 
		return self.data[i]

	def __len__(self): 
		return len(self.data)

	def __repr__(self):
		return '<Delta Array: {}>'.format(self.data)

	def __hash__(self):
		return hash(self.data)

	def __call__(self, global_time, extrapolate=False):
		'''Linear interpolation (LERP) with optional extrapolation.
		Interval (-inf) <-- (0 .. len(array)-1) --> (+inf) (supports negative indexing).
		'''

		if isinstance(global_time, tuple):
			gx, gy = global_time
		else:
			gx = gy = global_time

		ln = len(self.data[0])
		ix, tx = divmod(gx, 1)
		iy, ty = divmod(gy, 1)

		ix = int(ix)
		iy = int(iy)

		if ix > ln - 1:
			tx = ix - ln + 1 + tx if extrapolate else 1.
			ix = ln - 1
		elif ix < 0:
			tx = ix + 1 + tx if extrapolate else 0.
			ix = 0

		if iy > ln - 1:
			ty = iy - ln + 1 + ty if extrapolate else 1.
			iy = ln - 1
		elif iy < 0:
			ty = iy + 1 + ty if extrapolate else 0.		
			iy = 0
		
		points = []
		for row in range(ln):
			x = utils.lerp(self.data[ix].x_tuple[row], self.data[ix+1].x_tuple[row], tx)
			y = utils.lerp(self.data[iy].y_tuple[row], self.data[iy+1].y_tuple[row], ty)
			points.append((x,y))

		return PointArray(points)


class AdaptiveScale(object):
	def __init__(self, point_arrays, stem_arrays):
		self.points = DeltaArray(point_arrays)
		self.stems = DeltaArray(stem_arrays)

	def __compensate(global_time):
		pass

if __name__ == '__main__':
	arr = PointArray([Point(10,10), Point(740,570), Point(70,50)])
	points = [	[Point(10,10), Point(20,20)],
				[Point(30,30), Point(40,40)],
				[Point(50,50), Point(60,60)]]

	stems = [[(10,20)], [(30,50)], [(80,90)]]
	arr_lerp = DeltaArray(points)
	arr_mmx = AdaptiveScale(points, stems)
	print(arr_lerp(-3, 1))

