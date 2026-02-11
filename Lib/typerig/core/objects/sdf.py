# MODULE: TypeRig / Core / Signed Distance Field (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

# - Init -------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
class SignedDistanceField(object):
	'''Signed distance field computed from a set of contour polylines.
	
	SDF value convention:
	  - Negative inside the glyph (filled area)
	  - Positive outside the glyph
	  - Zero on the outline

	Uses dense polyline sampling for distance queries and ray casting 
	for inside/outside classification.

	Usage:
		sdf = SignedDistanceField(contours, resolution=2.0, padding=50)
		sdf.compute()
		d = sdf.query(300, 400)
		nx, ny = sdf.gradient_at(300, 400)
	'''

	def __init__(self, contours, resolution=1.0, padding=50, steps_per_segment=64):
		'''Initialize SDF from contour objects.

		Args:
			contours: list of Contour objects (must have .sample() method)
			resolution (float): Grid cell size in font units. 
			padding (float): Extra space around contour bounds.
			steps_per_segment (int): Polyline sampling density per segment.
		'''
		self.resolution = resolution
		self.padding = padding
		self._steps = steps_per_segment

		# Precompute polylines
		self._polylines = [c.sample(steps_per_segment) for c in contours]

		# Compute bounds
		all_pts = sum(self._polylines, [])

		if not all_pts:
			self.x_min = self.x_max = 0.0
			self.y_min = self.y_max = 0.0
		else:
			xs = [p[0] for p in all_pts]
			ys = [p[1] for p in all_pts]
			self.x_min = min(xs) - padding
			self.x_max = max(xs) + padding
			self.y_min = min(ys) - padding
			self.y_max = max(ys) + padding

		self.grid = None
		self.nx = 0
		self.ny = 0

	@classmethod
	def from_polylines(cls, polylines, resolution=1.0, padding=50):
		'''Create SDF directly from pre-sampled polylines.

		Args:
			polylines: list of list of (x, y) tuples
			resolution (float): Grid cell size
			padding (float): Extra space around bounds

		Returns:
			SignedDistanceField instance
		'''
		instance = cls.__new__(cls)
		instance.resolution = resolution
		instance.padding = padding
		instance._steps = 0
		instance._polylines = polylines

		all_pts = sum(polylines, [])

		if not all_pts:
			instance.x_min = instance.x_max = 0.0
			instance.y_min = instance.y_max = 0.0
		else:
			xs = [p[0] for p in all_pts]
			ys = [p[1] for p in all_pts]
			instance.x_min = min(xs) - padding
			instance.x_max = max(xs) + padding
			instance.y_min = min(ys) - padding
			instance.y_max = max(ys) + padding

		instance.grid = None
		instance.nx = 0
		instance.ny = 0
		return instance

	# -- Grid computation -------------------------
	def compute(self, verbose=False):
		'''Compute the full SDF grid.

		O(grid_cells * polyline_edges). Call once, then query cheaply.

		Args:
			verbose (bool): Print progress.

		Returns:
			list of list of float: The grid (also stored as self.grid).
		'''
		res = self.resolution
		self.nx = int((self.x_max - self.x_min) / res) + 1
		self.ny = int((self.y_max - self.y_min) / res) + 1

		if verbose:
			print('SDF: computing {}x{} grid (res={})...'.format(self.nx, self.ny, res))

		self.grid = []

		for iy in range(self.ny):
			row = []
			py = self.y_min + iy * res

			for ix in range(self.nx):
				px = self.x_min + ix * res
				d = self._min_distance(px, py)

				if self._is_inside(px, py):
					d = -d

				row.append(d)

			self.grid.append(row)

			if verbose and iy % 50 == 0:
				print('  row {}/{}'.format(iy, self.ny))

		if verbose:
			print('SDF: computation complete.')

		return self.grid

	@property
	def is_computed(self):
		'''True if the SDF grid has been computed.'''
		return self.grid is not None

	# -- Queries -------------------------
	def query(self, px, py):
		'''Query SDF value at a point (bilinear interpolation from grid).

		Falls back to direct computation if grid not computed or point is
		outside grid bounds.

		Args:
			px, py (float): Point coordinates in font units.

		Returns:
			float: Signed distance. Negative=inside, positive=outside.
		'''
		if self.grid is None:
			return self._query_direct(px, py)

		gx = (px - self.x_min) / self.resolution
		gy = (py - self.y_min) / self.resolution

		ix = int(gx)
		iy = int(gy)

		if ix < 0 or iy < 0 or ix >= self.nx - 1 or iy >= self.ny - 1:
			return self._query_direct(px, py)

		fx = gx - ix
		fy = gy - iy

		v00 = self.grid[iy][ix]
		v10 = self.grid[iy][ix + 1]
		v01 = self.grid[iy + 1][ix]
		v11 = self.grid[iy + 1][ix + 1]

		return (v00 * (1. - fx) * (1. - fy) 
			  + v10 * fx * (1. - fy) 
			  + v01 * (1. - fx) * fy 
			  + v11 * fx * fy)

	def gradient_at(self, px, py, eps=1.0):
		'''SDF gradient (outward normal) via central differences.

		Points from inside toward outside — use as topology-aware
		offset direction.

		Args:
			px, py (float): Point coordinates.
			eps (float): Finite difference step.

		Returns:
			tuple(float, float): Normalized gradient (unit vector).
		'''
		dx = self.query(px + eps, py) - self.query(px - eps, py)
		dy = self.query(px, py + eps) - self.query(px, py - eps)
		mag = math.hypot(dx, dy)

		if mag < 1e-12:
			return (0.0, 0.0)

		return (dx / mag, dy / mag)

	def _query_direct(self, px, py):
		'''Direct SDF query without grid.'''
		d = self._min_distance(px, py)

		if self._is_inside(px, py):
			d = -d

		return d

	# -- Internal geometry -------------------------
	def _point_to_segment_dist(self, px, py, ax, ay, bx, by):
		'''Minimum distance from point to line segment.'''
		dx, dy = bx - ax, by - ay
		len_sq = dx * dx + dy * dy

		if len_sq < 1e-12:
			return math.hypot(px - ax, py - ay)

		t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
		proj_x = ax + t * dx
		proj_y = ay + t * dy
		return math.hypot(px - proj_x, py - proj_y)

	def _min_distance(self, px, py):
		'''Minimum unsigned distance to all polylines.'''
		min_d = float('inf')

		for poly in self._polylines:
			n = len(poly)
			for i in range(n):
				ax, ay = poly[i]
				bx, by = poly[(i + 1) % n]
				d = self._point_to_segment_dist(px, py, ax, ay, bx, by)

				if d < min_d:
					min_d = d

		return min_d

	def _is_inside(self, px, py):
		'''Ray casting: odd crossings = inside.'''
		crossings = 0

		for poly in self._polylines:
			n = len(poly)
			for i in range(n):
				ax, ay = poly[i]
				bx, by = poly[(i + 1) % n]

				if (ay <= py < by) or (by <= py < ay):
					t = (py - ay) / (by - ay)
					ix = ax + t * (bx - ax)

					if px < ix:
						crossings += 1

		return (crossings % 2) == 1
