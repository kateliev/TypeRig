# MODULE: TypeRig / Core / Delta (Objects)
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

try: #Py3+
	from collections.abc import Sequence
except ImportError: #Py2+
	from collections import Sequence

import typerig.core.func.transform as utils
from typerig.core.objects.point import Point, Void
from typerig.core.objects.array import PointArray

# - Init -------------------------------
__version__ = '0.10.9'

# - Objects ------------------------------------
# -- Interpolation -----------------------------
class DeltaArray(Sequence):
	''''''
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
		points = []
		ln = len(self.data[0])
		ix, iy, tx, ty = self.timer(global_time, extrapolate)
			
		for row in range(ln):
			x = utils.lerp(self.data[ix].x_tuple[row], self.data[ix+1].x_tuple[row], tx)
			y = utils.lerp(self.data[iy].y_tuple[row], self.data[iy+1].y_tuple[row], ty)
			points.append((x,y))

		return PointArray(points)

	def mixer(self, global_time):
		'''Will return the proper coordinate values for the selected global time.'''
		if isinstance(global_time, tuple):
			gx, gy = global_time
		else:
			gx = gy = global_time

		p0, p1 = [], []
		ln = len(self.data)
		ix = int(divmod(gx, 1)[0])
		iy = int(divmod(gy, 1)[0])

		if ix >= ln - 1: ix = ln - 2
		if iy >= ln - 1: iy = ln - 2

		for row in range(len(self.data[0])):
			x0 = self.data[ix].x_tuple[row]
			y0 = self.data[iy].y_tuple[row]
			x1 = self.data[ix+1].x_tuple[row]
			y1 = self.data[iy+1].y_tuple[row]
			
			p0.append((x0, y0))
			p1.append((x1, y1))

		return PointArray(p0), PointArray(p1)

	def timer(self, global_time, extrapolate=False):
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

		return ix, iy, tx, ty


class DeltaScale(Sequence):
	''''''
	def __init__(self, *argv):
		# - Init
		self.x, self.y, self.stems = [], [], []
		
		if len(argv) == 1 and isinstance(argv[0], self.__class__): # Clone
			self.load(argv[0])
		
		elif len(argv) == 2: # Build
			points, stems = argv
			assert len(points) > 1, 'ERROR:\tNot enough input arrays! Minimum 2 required!'
			assert len(stems) == len(points), 'ERROR:\tNot enough stems provided!'
			len_points = [len(item) for item in points]
			assert len(len_points) == len_points.count(min(len_points)), 'ERROR:\tInput arrays dimensions do not match!'

			for i in range(len(points)-1):
				a,b = [], []
				p_curr = points[i]
				p_next = points[i+1]
				p_c_st = stems[i]*len_points[0]
				p_n_st = stems[i+1]*len_points[0]
			
				for n in range(len(p_curr)):
					a.append((p_curr[n][0], p_next[n][0], p_c_st[n][0], p_n_st[n][0]))
					b.append((p_curr[n][1], p_next[n][1], p_c_st[n][1], p_n_st[n][1]))

				self.x.append(a)
				self.y.append(b)
				self.stems.append(((p_c_st[0][0], p_n_st[0][0]), (p_c_st[0][1], p_n_st[0][1])))
		
	# - Internals ----------------------------------
	def __repr__(self):
		return '<Delta Scale Array: {}>'.format(self.dim)

	def __len__(self):
		return len(self.x)

	def __getitem__(self, index):
		result = []
		for idx in range(self.dim[1]):
			result.append(zip(self.x[index][idx], self.y[index][idx]))
		return result

	__setitem__ = None

	@property
	def dim(self):
		return (len(self), len(self.x))	

	# - Special functions ----------------------------------
	def __timer(self, global_time, extrapolate=False):
		if isinstance(global_time, tuple):
			gx, gy = global_time
		else:
			gx = gy = global_time

		ln = self.dim[1]
		ix, tx = divmod(gx, 1)
		iy, ty = divmod(gy, 1)

		ix = int(ix)
		iy = int(iy)

		if ix > ln - 1:
			tx = ix - ln + 1 + tx if extrapolate else 1.
			ix = ln - 1
		elif ix < 0:
			tx = ix + tx if extrapolate else 0.
			ix = 0

		if iy > ln - 1:
			ty = iy - ln + 1 + ty if extrapolate else 1.
			iy = ln - 1
		elif iy < 0:
			ty = iy + ty if extrapolate else 0.		
			iy = 0

		return ix, iy, tx, ty

	def __mixer(self, tx, ty, extrapolate=False):
		ix, _iy, ntx, _ty = self.__timer(tx, extrapolate)
		_ix, iy, _tx, nty = self.__timer(ty, extrapolate)

		return self.x[ix], self.y[iy], ntx, nty

	def __delta_scale(self, x, y, tx, ty, sx, sy, cx, cy, dx, dy, i):
		return utils.adaptive_scale(((x[0],y[0]), (x[1],y[1])), (sx, sy), (dx, dy), (tx, ty), (cx,cy), i, (x[2], x[3], y[2], y[3]))

	def _stem_for_time(self, stx, sty, extrapolate=False):
		tx, ty = 0., 0.

		for sti in range(len(self.stems)):
			stx0, stx1 = self.stems[sti][0]
			sty0, sty1 = self.stems[sti][1]
			#if stx0 <= stx <= stx1 : tx = sti + utils.timer(stx, stx0, stx1, True)
			#if sty0 <= sty <= sty1 : ty = sti + utils.timer(sty, sty0, sty1, True)
			if stx0 <= stx: tx = sti + utils.timer(stx, stx0, stx1, True)
			if sty0 <= sty: ty = sti + utils.timer(sty, sty0, sty1, True)

		if extrapolate:
			stx0, stx1 = self.stems[0][0]
			sty0, sty1 = self.stems[0][1]

			if tx == 0 and stx < stx0 :	tx = utils.timer(stx, stx0, stx1, True)
			if ty == 0 and sty < sty0 :	ty = utils.timer(sty, sty0, sty1, True)

		return tx, ty

	# - IO ---------------------------------------
	def dump(self):
		return self.x, self.y, self.stems
	
	def load(self, other):
		if isinstance(other, self.__class__):
			self.x, self.y, self.stems = other.dump()
		elif isinstance(other, (tuple, list)) and len(other) == 3:
			self.x, self.y, self.stems = other

	# - Process ----------------------------------
	def scale_by_time(self, time, scale_or_dimension, compensation, shift, italic_angle, extrapolate=False, to_dimension=False):
		cx, cy = compensation
		dx, dy = shift
		i = italic_angle
		a0, a1, ntx, nty = self.__mixer(time[0], time[1], extrapolate)
		process_array = zip(a0, a1)

		if not to_dimension:
			sx, sy = scale_or_dimension
		else:
			w0 = max(a0, key= lambda i: i[0])[0] - min(a0, key= lambda i: i[0])[0]
			w1 = max(a0, key= lambda i: i[1])[1] - min(a0, key= lambda i: i[1])[1]
			h0 = max(a1, key= lambda i: i[0])[0] - min(a0, key= lambda i: i[0])[0]
			h1 = max(a1, key= lambda i: i[1])[1] - min(a0, key= lambda i: i[1])[1]
			sx, sy = utils.adjuster(((w0, w1), (h0, h1)), scale_or_dimension, (ntx, nty), (dx, dy), (a0[0][2], a0[0][3], a1[0][2], a1[0][3]))

		result = map(lambda arr: self.__delta_scale(arr[0], arr[1], ntx, nty, sx, sy, cx, cy, dx, dy, i), process_array)
		return result

	def scale_by_stem(self, stem, scale_or_dimension, compensation, shift, italic_angle, extrapolate=False, to_dimension=False):
		stx, sty = stem
		cx, cy = compensation
		dx, dy = shift
		i = italic_angle

		tx, ty = self._stem_for_time(stx, sty, extrapolate)
		result = self.scale_by_time((tx, ty), scale_or_dimension, compensation, shift, italic_angle, extrapolate, to_dimension)
		
		return result

if __name__ == '__main__':
	arr = PointArray([Point(10,10), Point(740,570), Point(70,50)])
	points = [	[(10,10), (20,20),(60,60)],
				[(30,30), (40,40),(70,70)],
				[(50,50), (60,60),(80,80)]]

	stems = [[(10,20)], [(30,50)], [(80,90)]]
	arr_lerp = DeltaArray(points)
	a = DeltaScale(points, stems)
	b = DeltaScale(a)
	#print(a.scale_by_time((1,1), (1,3), (1.0, 1.0), (0,0), 0))
	#print(a.scale_by_stem((40,25), (1,3), (1.0, 1.0), (0,0), 0))
	print(a.x)
	


