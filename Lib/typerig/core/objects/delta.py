# MODULE: TypeRig / Core / Delta (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


# - Dependencies ------------------------

import math

from collections.abc import Sequence

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

			# Build one "segment" per adjacent master pair (Light->Regular,
			# Regular->Bold, ...). Each segment stores, per node, the packed
			# tuple (coord_current, coord_next, stem_current, stem_next) split
			# into an X table (self.x) and a Y table (self.y). This packing is
			# exactly what adaptive_scale() consumes: masters + their stems
			# travelling together so the transform can interpolate both at once.
			for i in range(len(points)-1):
				a,b = [], []
				p_curr = points[i]					# node coords of master i
				p_next = points[i+1]				# node coords of master i+1
				p_c_st = stems[i]*len_points[0]		# stem of master i, one copy per node
				p_n_st = stems[i+1]*len_points[0]	# stem of master i+1, one copy per node

				for n in range(len(p_curr)):
					# X row: (x_curr, x_next, stx_curr, stx_next)
					a.append((p_curr[n][0], p_next[n][0], p_c_st[n][0], p_n_st[n][0]))
					# Y row: (y_curr, y_next, sty_curr, sty_next)
					b.append((p_curr[n][1], p_next[n][1], p_c_st[n][1], p_n_st[n][1]))

				self.x.append(a)
				self.y.append(b)
				# Per-segment stem envelope: ((stx_curr, stx_next),(sty_curr, sty_next)).
				# Used by _stem_for_time() to map a target stem back to a time.
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
		# Split a global time into (segment index, local 0..1 time) for X and Y
		# independently (anisotropic). global_time 1.7 -> segment 1, local 0.7.
		# A scalar drives both axes with the same time.
		if isinstance(global_time, tuple):
			gx, gy = global_time
		else:
			gx = gy = global_time

		ln = self.dim[1]					# number of segments (master pairs)
		ix, tx = divmod(gx, 1)				# integer part = segment, frac = local time
		iy, ty = divmod(gy, 1)

		ix = int(ix)
		iy = int(iy)

		# Clamp out-of-range times to the end segments. When extrapolate is on we
		# keep the overshoot in the local time so adaptive_scale runs past 0..1;
		# otherwise we pin to the boundary (0. or 1.).
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
		# Pick the active X segment (from tx) and Y segment (from ty) plus their
		# local times. X and Y may resolve to different segments, so we run the
		# timer once per axis and keep each axis's own segment table.
		ix, _iy, ntx, _ty = self.__timer(tx, extrapolate)
		_ix, iy, _tx, nty = self.__timer(ty, extrapolate)

		return self.x[ix], self.y[iy], ntx, nty

	def __delta_scale(self, x, y, tx, ty, sx, sy, cx, cy, dx, dy, i):
		# Unpack one node's packed rows back into the adaptive_scale signature:
		#   coords ((x_curr,y_curr),(x_next,y_next)), stems (stx0,stx1,sty0,sty1).
		return utils.adaptive_scale(((x[0],y[0]), (x[1],y[1])), (sx, sy), (dx, dy), (tx, ty), (cx,cy), i, (x[2], x[3], y[2], y[3]))

	def _stem_for_time(self, stx, sty, extrapolate=False):
		# Inverse of the stem axis: given a TARGET stem (stx, sty), find the
		# global time whose interpolated stem equals it. Walk segments in order;
		# the last segment whose lower stem bound is <= target wins, and the
		# local time inside it is timer(target, seg_lo, seg_hi). Global time is
		# segment_index + local_time (so 1.4 == segment 1, 40% across).
		tx, ty = 0., 0.

		for sti in range(len(self.stems)):
			stx0, stx1 = self.stems[sti][0]			# X stem bounds of this segment
			sty0, sty1 = self.stems[sti][1]			# Y stem bounds of this segment
			#if stx0 <= stx <= stx1 : tx = sti + utils.timer(stx, stx0, stx1, True)
			#if sty0 <= sty <= sty1 : ty = sti + utils.timer(sty, sty0, sty1, True)
			if stx0 <= stx: tx = sti + utils.timer(stx, stx0, stx1, True)
			if sty0 <= sty: ty = sti + utils.timer(sty, sty0, sty1, True)

		# Below the lightest master: with extrapolate, run negative time off the
		# first segment; otherwise tx/ty stay pinned at 0 (the light master).
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
		'''Transform the outline at a given interpolation time.

		scale_or_dimension means (sx, sy) scale factors when to_dimension is
		False; when to_dimension is True it means a TARGET (width, height) and
		the scale factors are back-solved analytically via adjuster().

		NOTE (see WIDTH_MODE_SOLVER.md 2.3): the adjuster path is a first-order
		SEED, exact only at the base master. For an exact dimension hit, refine
		the scale with a secant step on the measured bbox — do not trust the
		one-shot result off the base master.
		'''
		cx, cy = compensation
		dx, dy = shift
		i = italic_angle
		# Resolve the active X/Y segments and local times, then pair up each
		# node's X row with its Y row for the transform.
		a0, a1, ntx, nty = self.__mixer(time[0], time[1], extrapolate)
		process_array = zip(a0, a1)

		if not to_dimension:
			sx, sy = scale_or_dimension
		else:
			# Measure the two masters' bbox extents from the packed rows:
			#   a0[n] = (x_curr, x_next, ...)  -> index 0 = current, 1 = next
			#   a1[n] = (y_curr, y_next, ...)
			w0 = max(a0, key= lambda i: i[0])[0] - min(a0, key= lambda i: i[0])[0]	# width, current master
			w1 = max(a0, key= lambda i: i[1])[1] - min(a0, key= lambda i: i[1])[1]	# width, next master
			h0 = max(a1, key= lambda i: i[0])[0] - min(a0, key= lambda i: i[0])[0]	# height, current master
			h1 = max(a1, key= lambda i: i[1])[1] - min(a0, key= lambda i: i[1])[1]	# height, next master
			# Closed-form scale that (approximately) lands the target dimension.
			sx, sy = utils.adjuster(((w0, w1), (h0, h1)), scale_or_dimension, (ntx, nty), (dx, dy), (a0[0][2], a0[0][3], a1[0][2], a1[0][3]))

		# Drive every node through adaptive_scale with the resolved (sx, sy).
		result = map(lambda arr: self.__delta_scale(arr[0], arr[1], ntx, nty, sx, sy, cx, cy, dx, dy, i), process_array)
		return result

	def scale_by_stem(self, stem, scale_or_dimension, compensation, shift, italic_angle, extrapolate=False, to_dimension=False):
		'''Same as scale_by_time but the interpolation time is derived from a
		TARGET stem (stx, sty) instead of being passed directly. This is the
		call the panels use: "put me where stem == X, then scale/size me."
		'''
		stx, sty = stem
		cx, cy = compensation
		dx, dy = shift
		i = italic_angle

		# Stem -> time, then defer to scale_by_time. Two-step so callers can hit
		# a weight by its physical stem value without knowing the axis geometry.
		tx, ty = self._stem_for_time(stx, sty, extrapolate)
		result = self.scale_by_time((tx, ty), scale_or_dimension, compensation, shift, italic_angle, extrapolate, to_dimension)

		return result

	# - Dimension solver -----------------------------------
	def solve_scale_for_dimension(self, stem, dimension, compensation=(0., 0.), shift=(0., 0.), italic_angle=0., extrapolate=False, tol=(1e-3, 1e-3), max_steps=24):
		'''Back-solve the scale factors (sx, sy) that make the outline hit a
		target bounding-box (width, height) at the weight given by `stem`,
		WITHOUT changing the stroke weight (compensation defaults to (0, 0) =
		stems preserved).

		Why this exists (see WIDTH_MODE_SOLVER.md 2.3-2.4):
		  - adjuster() gives a closed-form guess, but it is only a first-order
		    SEED: it models the stem ratio as stx1/stx0 while the real transform
		    uses stx1/cstx, so it drifts off the base master (measured ~9.6u off
		    at t=0.5). Trusting it one-shot mis-sizes the glyph.
		  - With compensation=0, width(sx) and height(sy) are EXACTLY affine, so
		    a secant step on the measured bbox lands the target to machine
		    precision. That is the real lever; the seed only saves an iteration.

		Args:
			stem       : (stx, sty) target stem — selects the interpolation time.
			dimension  : (width, height) target bbox. Either may be None to leave
			             that axis unconstrained (its scale stays 1.0).
			compensation, shift, italic_angle, extrapolate : passed straight
			             through to the transform (keep compensation=(0,0) for
			             stem preservation).
			tol        : (tol_w, tol_h) convergence tolerance in font units.
			max_steps  : iteration cap (converges in 1-3 for the affine case).

		Returns:
			(sx, sy) scale factors. Feed them back through scale_by_stem(...,
			(sx, sy), ..., to_dimension=False) to get the final outline, or apply
			the same pair to sibling attributes (metrics, anchors) so every array
			scales identically.
		'''
		target_w, target_h = dimension
		tol_w, tol_h = tol
		solve_x = target_w is not None
		solve_y = target_h is not None

		stx, sty = stem
		tx, ty = self._stem_for_time(stx, sty, extrapolate)

		# --- Measurement: run the actual transform, return the bbox (w, h).
		# This is the ground truth the solver drives to zero — no model, the
		# real adaptive_scale output, so italic shear and point-identity
		# switches are all accounted for.
		def measure(sx, sy):
			pts = list(self.scale_by_time((tx, ty), (sx, sy), compensation, shift, italic_angle, extrapolate, False))
			xs = [p[0] for p in pts]
			ys = [p[1] for p in pts]
			return (max(xs) - min(xs), max(ys) - min(ys))

		# --- Seed from the closed form (approximate but close, stem-aware).
		# Rebuild the same measurements adjuster() wants from the packed rows.
		# Height is taken purely from the Y table a1 (the original inline path
		# mixed a0 into the height min; harmless for a seed, but we keep it
		# clean here since the secant is what guarantees the final value).
		a0, a1, ntx, nty = self.__mixer(tx, ty, extrapolate)
		dx, dy = shift
		w0 = max(a0, key=lambda r: r[0])[0] - min(a0, key=lambda r: r[0])[0]	# width, current master
		w1 = max(a0, key=lambda r: r[1])[1] - min(a0, key=lambda r: r[1])[1]	# width, next master
		h0 = max(a1, key=lambda r: r[0])[0] - min(a1, key=lambda r: r[0])[0]	# height, current master
		h1 = max(a1, key=lambda r: r[1])[1] - min(a1, key=lambda r: r[1])[1]	# height, next master
		seed_x, seed_y = utils.adjuster(((w0, w1), (h0, h1)),
			(target_w if solve_x else w0, target_h if solve_y else h0),
			(ntx, nty), (dx, dy), (a0[0][2], a0[0][3], a1[0][2], a1[0][3]))

		sx = seed_x if solve_x else 1.0
		sy = seed_y if solve_y else 1.0

		# Internal iteration budgets. These are DELIBERATELY small constants and
		# NOT tied to max_steps: the affine root is found in ~1-2 secant steps, so
		# a caller passing a large max_iterations (Layer.scale_with_axis defaults
		# to 1000) must not blow the work up into millions of evaluations. That
		# runaway is what hangs the host on an unreachable (absurdly small/large)
		# target. max_steps only bounds the OUTER coupling loop.
		BRACKET_MAX = 40		# doublings/halvings while hunting a bracket
		ROOT_MAX = 40			# secant+bisection steps once bracketed
		MIN_SCALE = 1e-4		# floor for a clamped (unreachable-small) result,
								# avoids denormalised scale factors mangling geometry
		MAX_SCALE = 1e6			# ceiling for a clamped (unreachable-large) result
		outer_max = max(3, min(int(max_steps), 12))

		# --- 1-D root finder: bracket the root (clamping to the ACHIEVABLE range
		# so an impossible target returns the nearest limit instantly instead of
		# grinding), then false-position/secant with a bisection safeguard.
		# g(s) is the measured dimension as a function of one scale factor and is
		# monotonically increasing in s > 0.
		def solve_axis(g, target, seed, axis_tol):
			s0 = max(seed, 1e-6)
			g0 = g(s0)
			if abs(g0 - target) <= axis_tol:
				return s0

			if g0 < target:
				# Need a bigger scale: grow hi until it overshoots the target.
				lo, glo = s0, g0
				hi = s0
				bracketed = False
				for _ in range(BRACKET_MAX):
					hi *= 2.0
					ghi = g(hi)
					if ghi >= target:
						bracketed = True; break
					lo, glo = hi, ghi
				if not bracketed:
					return min(hi, MAX_SCALE)	# target ABOVE max achievable -> clamp
			else:
				# Need a smaller scale: shrink lo until it undershoots the target.
				hi, ghi = s0, g0
				lo = s0
				bracketed = False
				for _ in range(BRACKET_MAX):
					if lo * 0.5 < MIN_SCALE:
						return MIN_SCALE	# target BELOW min achievable -> clamp
					lo *= 0.5
					glo = g(lo)
					if glo <= target:
						bracketed = True; break
					hi, ghi = lo, glo
				if not bracketed:
					return MIN_SCALE	# target BELOW min achievable -> clamp

			# Root is bracketed in [lo, hi]. False-position (secant on the
			# bracket) converges in one step when g is affine; the midpoint
			# fallback keeps the guess inside the bracket so it can never diverge.
			for _ in range(ROOT_MAX):
				denom = ghi - glo
				c = lo + (target - glo) * (hi - lo) / denom if denom else 0.5 * (lo + hi)
				if not (lo < c < hi):
					c = 0.5 * (lo + hi)
				gc = g(c)
				if abs(gc - target) <= axis_tol:
					return c
				if gc < target: lo, glo = c, gc
				else: hi, ghi = c, gc
			return 0.5 * (lo + hi)

		# --- Outer loop handles X<->Y coupling from italic shear. With no shear
		# (italic_angle == 0) width depends only on sx and height only on sy, so
		# this converges in a single pass. The stagnation break exits immediately
		# once the scale factors stop moving -- which is exactly what happens when
		# the target is unreachable and each axis is clamped to its limit.
		prev = None
		for _ in range(outer_max):
			w, h = measure(sx, sy)
			done_x = (not solve_x) or abs(target_w - w) <= tol_w
			done_y = (not solve_y) or abs(target_h - h) <= tol_h
			if done_x and done_y:
				break
			if solve_x:
				sx = solve_axis(lambda s: measure(s, sy)[0], target_w, sx, tol_w)
			if solve_y:
				sy = solve_axis(lambda s: measure(sx, s)[1], target_h, sy, tol_h)
			if prev is not None and abs(sx - prev[0]) <= 1e-9 and abs(sy - prev[1]) <= 1e-9:
				break
			prev = (sx, sy)

		return sx, sy

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
	


