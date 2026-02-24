# MODULE: TypeRig / Core / HobbySpline (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
import cmath

from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds
from typerig.core.objects.atom import Container, Member
from typerig.core.objects.node import Node, node_types

from typerig.core.func.math import (
	zero_matrix, 
	solve_equations, 
	hobby_velocity, 
	hobby_control_points
)

# - Init --------------------------------
__version__ = '0.1.0'

# - Constants ---------------------------
# Segment type tags — describe connection from this knot to NEXT
HOBBY = 'hobby'		# Solver finds optimal handles
LINE = 'line'		# Straight segment, no off-curves
FIXED = 'fixed'		# User-provided BCPs, solver ignores

# - Utilities ---------------------------
# Ported and adapted from MetaType1 plain_ex.mp
# by Bogusław Jackowski and Janusz Nowacki

def robust_direction(z0, z1, z2, z3):
	'''Tangent direction at start of Bézier segment z0..controls z1 and z2..z3
	using de l'Hôpital fallback chain.

	When a control point coincides with its on-curve node (retracted handle),
	the naive z1 - z0 gives zero. The MetaPost approach cascades:
	try z1-z0, if degenerate try z2-z0, if degenerate try z3-z0.

	All arguments are complex numbers. Returns complex direction vector.
	Returns (0+0j) if the segment is fully degenerate.
	'''
	d = z1 - z0
	if abs(d) > 1e-10:
		return d

	d = z2 - z0
	if abs(d) > 1e-10:
		return d

	d = z3 - z0
	if abs(d) > 1e-10:
		return d

	return complex(0, 0)

def robust_direction_end(z0, z1, z2, z3):
	'''Tangent direction at end of Bézier segment z0..controls z1 and z2..z3.
	Same de l'Hôpital cascade but from the endpoint perspective:
	try z3-z2, if degenerate try z3-z1, if degenerate try z3-z0.
	'''
	d = z3 - z2
	if abs(d) > 1e-10:
		return d

	d = z3 - z1
	if abs(d) > 1e-10:
		return d

	d = z3 - z0
	if abs(d) > 1e-10:
		return d

	return complex(0, 0)

def turning_angle(za, zb):
	'''Signed turning angle between two direction vectors.
	Uses complex-number reflection method from MetaType1/METAFONT.
	Arguments are complex numbers. Returns angle in radians.
	Returns None if either vector is near-zero.
	'''
	if abs(za) < 1e-10 or abs(zb) < 1e-10:
		return None

	# unitvector(za) * conj(unitvector(zb)) gives rotation from zb to za
	ua = za / abs(za)
	ub = zb / abs(zb)
	rotation = ua * ub.conjugate()
	return cmath.phase(rotation)

def is_line_segment(z0, z1, z2, z3, tolerance=0.5):
	'''Check whether a Bézier segment is effectively a straight line.
	Uses arc-length vs chord-length comparison plus optional 
	control-point-to-secant distance check from MetaType1.

	All arguments are complex numbers.
	tolerance: max acceptable distance of control points from secant.
	'''
	chord = abs(z3 - z0)

	if chord < 1e-10:
		# Degenerate segment — all points coincide
		return abs(z1 - z0) < 1e-10 and abs(z2 - z0) < 1e-10

	# Check control point distances from the secant line z0→z3
	secant = z3 - z0
	secant_len = abs(secant)

	for cp in (z1, z2):
		v = cp - z0
		# Signed distance = Im(v / secant) * |secant|  
		# = cross product / |secant|
		cross = v.real * secant.imag - v.imag * secant.real
		dist = abs(cross) / secant_len

		if dist > tolerance:
			return False

	return True

def recover_tension(z0, z1, z2, z3):
	'''Extract effective Hobby tension from an existing Bézier segment.
	Based on MetaType1 posttension/pretension (METAFONT book ex. 14.15).

	Compares actual handle lengths against what default tension-1 
	Hobby algorithm would produce for the same directions.

	Returns (alpha, beta) tension pair.
	'''
	# Get directions at endpoints
	dir_start = robust_direction(z0, z1, z2, z3)
	dir_end = robust_direction_end(z0, z1, z2, z3)

	if abs(dir_start) < 1e-10 or abs(dir_end) < 1e-10:
		return (1., 1.)  # Fallback: default tension

	# Compute theta and phi from directions relative to chord
	chord = z3 - z0
	if abs(chord) < 1e-10:
		return (1., 1.)

	theta = cmath.phase(dir_start / chord)
	phi = cmath.phase(chord / dir_end)

	# What hobby_velocity gives for tension=1
	try:
		vel_post = hobby_velocity(theta, phi)
		vel_pre = hobby_velocity(phi, theta)
	except (ZeroDivisionError, ValueError):
		return (1., 1.)

	# Actual handle lengths relative to chord
	actual_post = abs(z1 - z0)
	actual_pre = abs(z3 - z2)
	chord_len = abs(chord)

	if actual_post < 1e-10 or actual_pre < 1e-10:
		return (1., 1.)

	# Reference handle lengths at tension=1
	ref_post = chord_len * vel_post
	ref_pre = chord_len * vel_pre

	if ref_post < 1e-10 or ref_pre < 1e-10:
		return (1., 1.)

	# tension = reference / actual (higher tension = shorter handles)
	alpha = ref_post / actual_post
	beta = ref_pre / actual_pre

	# Clamp to reasonable range
	alpha = max(0.1, min(alpha, 10.))
	beta = max(0.1, min(beta, 10.))

	return (alpha, beta)

def force_convex(z0, z1, z2, z3):
	'''Handle-flip correction from MetaType1 force_convex_edge.
	Detects when control points produce an inflection where none 
	should exist and clamps handles to the intersection of the 
	two handle lines.

	All arguments are complex numbers.
	Returns corrected (z1, z2) control points.
	'''
	chord = abs(z3 - z0)
	d01 = abs(z1 - z0)
	d12 = abs(z2 - z1)
	d23 = abs(z3 - z2)

	# Degenerate check — if sum of handle segments <= chord, it's a line
	if (-chord + d01 + d12 + d23) <= chord * 1e-10:
		return (z1, z2)

	if chord < 0.01 or d01 < 0.01 or d12 < 0.01 or d23 < 0.01:
		return (z1, z2)

	# Check for sign changes in cross products (convexity test)
	def sign(x):
		if x > 0: return 1
		elif x < 0: return -1
		else: return 0

	def cross(a, b):
		return a.real * b.imag - a.imag * b.real

	# Normals of successive edges, dotted with next edge
	s0 = sign(cross(z1 - z0, z0 - z3))
	s1 = sign(cross(z2 - z1, z1 - z0))
	s2 = sign(cross(z3 - z2, z2 - z1))
	s3 = sign(cross(z0 - z3, z3 - z2))

	# If sign changes occur between consecutive edges, handles crossed
	if (s0 != s1 or s1 != s2) and s0 == s3:
		# Find intersection of handle lines z0→z1 and z3→z2
		d_a = z1 - z0
		d_b = z2 - z3

		denom = d_a.real * d_b.imag - d_a.imag * d_b.real

		if abs(denom) > 1e-10:
			diff = z3 - z0
			t_a = (diff.real * d_b.imag - diff.imag * d_b.real) / denom
			t_b = (diff.real * d_a.imag - diff.imag * d_a.real) / denom

			# Clamp: only correct if intersection lies on the forward side
			intersection = z0 + t_a * d_a

			new_z1 = intersection if t_a < 1 else z1
			new_z2 = intersection if t_b < 1 else z2

			return (new_z1, new_z2)

	return (z1, z2)

def extrapolate_segment(z0, z1, z2, z3, t1, t2):
	'''Inverse of subpath — given a Bézier that was cut at (t1, t2),
	reconstruct the full segment. Based on MetaType1 extrapolate 
	using de Casteljau evaluation.

	Arguments: four complex control points, two time parameters.
	Returns: (Z0, Z1, Z2, Z3) — the extrapolated control points.
	'''
	if abs(t2 - t1) < 1e-10:
		return (z0, z1, z2, z3)

	# We need to find Z0..Z3 such that subpath(t1,t2) of Z == z0..z3
	# Use 4 evaluation points at t1, 1/3-way, 2/3-way, t2 on the 
	# unknown curve, matched against our known segment at 0, 1/3, 2/3, 1.

	def casteljau(Z0, Z1, Z2, Z3, t):
		'''de Casteljau evaluation at parameter t'''
		a = (1 - t) * Z0 + t * Z1
		b = (1 - t) * Z1 + t * Z2
		c = (1 - t) * Z2 + t * Z3
		d = (1 - t) * a + t * b
		e = (1 - t) * b + t * c
		return (1 - t) * d + t * e

	def eval_known(t):
		'''Evaluate our known segment at t'''
		return casteljau(z0, z1, z2, z3, t)

	# The four target points on the full curve
	P0 = eval_known(0.)   # = z0
	P1 = eval_known(1/3)
	P2 = eval_known(2/3)
	P3 = eval_known(1.)   # = z3

	# Map these to parameter space of the full curve
	T0 = t1
	T1 = t1 + (t2 - t1) / 3
	T2 = t1 + 2 * (t2 - t1) / 3
	T3 = t2

	# Solve for Z0..Z3 using Bernstein basis
	# P_i = B(T_i) where B is the full Bézier with unknowns Z0..Z3
	# This is a 4x4 linear system (separable into x and y)
	def bernstein_row(t):
		t1 = 1 - t
		return [t1**3, 3*t1**2*t, 3*t1*t**2, t**3]

	# Build the system
	M = [bernstein_row(T0), bernstein_row(T1), bernstein_row(T2), bernstein_row(T3)]
	Px = [P0.real, P1.real, P2.real, P3.real]
	Py = [P0.imag, P1.imag, P2.imag, P3.imag]

	# Solve via Gaussian elimination (reuse existing solver)
	bx = [[v] for v in Px]
	by = [[v] for v in Py]

	try:
		Zx = sum(solve_equations([row[:] for row in M], bx), [])
		Zy = sum(solve_equations([row[:] for row in M], by), [])
	except (ZeroDivisionError, ValueError):
		return (z0, z1, z2, z3)

	return tuple(complex(x, y) for x, y in zip(Zx, Zy))


# - Classes -----------------------------
class HobbyKnot(Member):
	'''Extended knot for HobbySpline with mixed segment type support.
	Carries all METAFONT solving state plus segment classification 
	and optional direction/handle constraints.

	Attributes:
		x, y           : knot position
		alpha, beta    : tension (departure/arrival)
		theta, phi     : solved departure/arrival angles
		u_right, v_left: solved control points (complex)
		d_ant, d_post  : distances to prev/next (computed)
		xi             : turning angle of polyline (computed)
		segment_type   : 'hobby', 'line', or 'fixed' — describes 
		                 connection to NEXT knot
		fixed_bcp_out  : explicit outgoing BCP (complex) for 'fixed' segments
		fixed_bcp_in   : explicit incoming BCP (complex) for 'fixed' segments
		dir_out        : pinned departure direction (radians), None = free
		dir_in         : pinned arrival direction (radians), None = free
	'''

	def __init__(self, x=0., y=0., **kwargs):
		super(HobbyKnot, self).__init__(**kwargs)

		# Handle tuple/list input from Container._coerce
		if isinstance(x, (tuple, list)):
			x, y = float(x[0]), float(x[1])

		self.x = float(x)
		self.y = float(y)

		# - Metadata
		self.type = 'on'
		self.name = kwargs.pop('name', '')
		self.identifier = kwargs.pop('identifier', False)
		self.parent = kwargs.pop('parent', None)
		self.angle = kwargs.pop('angle', 0)
		self.transform = kwargs.pop('transform', Transform())
		self.complex_math = kwargs.pop('complex', True)

		# - Hobby solving state
		# -- Tension at point (1. by default)
		self.alpha = kwargs.pop('alpha', 1.)
		self.beta = kwargs.pop('beta', 1.)

		# -- Departure angle (solved by METAFONT system)
		self.theta = kwargs.pop('theta', 0.)

		# -- Arrival angle (solved by METAFONT system)
		self.phi = kwargs.pop('phi', 0.)

		# -- Control points of the Bézier curve at this point
		self.v_left = complex(0, 0)
		self.u_right = complex(0, 0)

		# - Segment classification
		# -- Describes connection from THIS knot to NEXT knot
		self.segment_type = kwargs.pop('segment_type', HOBBY)

		# - Fixed handle constraints
		# -- Explicit BCPs for 'fixed' segments (complex coords)
		self.fixed_bcp_out = kwargs.pop('fixed_bcp_out', None)  # outgoing from this knot
		self.fixed_bcp_in = kwargs.pop('fixed_bcp_in', None)    # incoming to this knot

		# - Direction constraints (METAFONT {dir} equivalent)
		# -- Pinned directions in radians, None = free for solver
		self.dir_out = kwargs.pop('dir_out', None)  # departure direction
		self.dir_in = kwargs.pop('dir_in', None)    # arrival direction

	# -- Representation -------------------------
	def __repr__(self):
		return '<{} x={} y={} seg={} alpha={} beta={}>'.format(
			self.__class__.__name__, self.x, self.y, 
			self.segment_type, self.alpha, self.beta
		)

	# -- Properties -----------------------------
	@property
	def index(self):
		return self.idx

	@property
	def contour(self):
		return self.parent

	@property
	def tuple(self):
		return (self.x, self.y)

	@property
	def complex(self):
		return complex(self.x, self.y)

	@tuple.setter
	def tuple(self, other):
		if isinstance(other, (tuple, list)) and len(other) == 2:
			self.x = float(other[0])
			self.y = float(other[1])

	@property
	def point(self):
		return Point(self.x, self.y, angle=self.angle, transform=self.transform, complex=self.complex_math)

	@point.setter
	def point(self, other):
		if isinstance(other, (self.__class__, Point)):
			self.x = other.x
			self.y = other.y

	@property
	def clockwise(self):
		from typerig.core.func.geometry import ccw
		return not ccw(self.prev.point.tuple, self.point.tuple, self.next.point.tuple)

	@property
	def is_on(self):
		return self.type == node_types['on']

	@property
	def distance_to_next(self):
		return self.distance_to(self.next)

	@property
	def distance_to_prev(self):
		return self.distance_to(self.prev)

	@property
	def angle_to_next(self):
		return self.angle_to(self.next)

	@property
	def angle_to_prev(self):
		return self.angle_to(self.prev)

	# -- Angle turned by the polyline at this point
	@property
	def xi(self):
		temp_point = (self.next.point - self.point) / (self.point - self.prev.point)
		return math.atan2(temp_point.y, temp_point.x)

	# -- Distance to previous point in the path
	@property
	def d_ant(self):
		return self.distance_to_prev

	# -- Distance to next point in the path
	@property
	def d_post(self):
		return self.distance_to_next

	# -- Helpers --------------------------------
	def distance_to(self, other):
		return math.hypot(other.x - self.x, other.y - self.y)

	def angle_to(self, other):
		return math.atan2(other.y - self.y, other.x - self.x)

	# -- Direction constraint helpers -----------
	@property
	def has_dir_out(self):
		'''Whether departure direction is pinned (by constraint or by segment type)'''
		return self.dir_out is not None

	@property
	def has_dir_in(self):
		'''Whether arrival direction is pinned (by constraint or by segment type)'''
		return self.dir_in is not None

	def pin_dir_out_toward(self, target_knot):
		'''Pin departure direction toward another knot (for line segments)'''
		self.dir_out = self.angle_to(target_knot)

	def pin_dir_in_from(self, source_knot):
		'''Pin arrival direction from another knot (for line segments)'''
		self.dir_in = math.atan2(self.y - source_knot.y, self.x - source_knot.x)


class HobbySpline(Container):
	'''Mixed-segment path builder using John Hobby's algorithm.

	Supports three segment types between consecutive knots:
	  - HOBBY  : solver finds optimal handles via METAFONT equations
	  - LINE   : straight connection, no off-curve points
	  - FIXED  : user-provided explicit control points

	The METAFONT linear system is split into "free runs" — contiguous 
	stretches of hobby-type segments. Lines and fixed-handle segments 
	pin the departure/arrival angles at their endpoints, serving as 
	boundary conditions for adjacent free runs.

	Direction constraints ({dir} in METAFONT) are supported: pin the 
	departure or arrival angle at a knot while letting the solver 
	compute the handle magnitude.

	Backward compatible with the original HobbySpline tuple-list API.
	'''

	def __init__(self, data=None, **kwargs):
		# - Init
		factory = kwargs.pop('default_factory', HobbyKnot)
		super(HobbySpline, self).__init__(data, default_factory=factory, **kwargs)

		# - Metadata
		self.global_tension = kwargs.pop('tension', 1.)
		self.transform = kwargs.pop('transform', Transform())
		self.name = kwargs.pop('name', '')
		self.closed = kwargs.pop('closed', False)
		self.clockwise = kwargs.pop('clockwise', self.get_winding())
		self.curl_start = kwargs.pop('curl_start', 1.)
		self.curl_end = kwargs.pop('curl_end', self.curl_start)

		# Apply global tension to all knots
		self._apply_global_tension()

	# - Internals ------------------------------
	def __getitem__(self, index):
		'''Circular indexing for closed paths'''
		index %= len(self.data)
		return self.data[index]

	def _apply_global_tension(self):
		'''Set alpha/beta on all knots that haven't been individually configured'''
		for knot in self.data:
			if knot.alpha == 1.:
				knot.alpha = self.global_tension
			if knot.beta == 1.:
				knot.beta = self.global_tension

	# - Builder API ----------------------------
	def add_knot(self, position, **kwargs):
		'''Add a knot to the path with optional segment type and constraints.

		Args:
			position    : (x, y) tuple or Point
			segment     : 'hobby', 'line', or 'fixed' — connection to NEXT knot
			alpha       : departure tension (default: global)
			beta        : arrival tension (default: global)
			bcp_out     : (x, y) explicit outgoing BCP for 'fixed' segments
			bcp_in      : (x, y) explicit incoming BCP for 'fixed' segments
			dir_out     : departure direction in radians, None = free
			dir_in      : arrival direction in radians, None = free
		'''
		if isinstance(position, (tuple, list)):
			x, y = float(position[0]), float(position[1])
		elif isinstance(position, Point):
			x, y = position.x, position.y
		else:
			raise TypeError('Position must be tuple, list, or Point')

		segment = kwargs.pop('segment', HOBBY)
		alpha = kwargs.pop('alpha', self.global_tension)
		beta = kwargs.pop('beta', self.global_tension)

		# Fixed BCPs
		bcp_out = kwargs.pop('bcp_out', None)
		bcp_in = kwargs.pop('bcp_in', None)

		if bcp_out is not None:
			bcp_out = complex(float(bcp_out[0]), float(bcp_out[1]))
		if bcp_in is not None:
			bcp_in = complex(float(bcp_in[0]), float(bcp_in[1]))

		# Direction constraints
		dir_out = kwargs.pop('dir_out', None)
		dir_in = kwargs.pop('dir_in', None)

		knot = HobbyKnot(
			x, y,
			alpha=alpha,
			beta=beta,
			segment_type=segment,
			fixed_bcp_out=bcp_out,
			fixed_bcp_in=bcp_in,
			dir_out=dir_out,
			dir_in=dir_in,
			parent=self,
		)

		# Use Container's append to properly set up linked list
		knot._parent_list = self.data
		self.data.append(knot)
		return knot

	# - Free run identification ----------------
	def _classify_segments(self):
		'''Tag each knot→next connection and compute boundary angles.
		Returns list of segment types parallel to knot indices.
		For N knots in a closed path: N segments (last wraps to first).
		For N knots in an open path: N-1 segments.
		'''
		n = len(self.data)
		count = n if self.closed else n - 1
		seg_types = []

		for i in range(count):
			seg_types.append(self.data[i].segment_type)

		return seg_types

	def _find_free_runs(self, seg_types):
		'''Identify contiguous stretches of HOBBY segments.

		A "free run" is a maximal sequence of consecutive knot indices 
		where all connecting segments are HOBBY type.

		Returns list of tuples: (start_index, end_index, is_boundary_start, is_boundary_end)
		where start/end are knot indices and boundary flags indicate
		whether the run endpoints have pinned angles from adjacent 
		non-hobby segments.
		'''
		n = len(self.data)
		count = len(seg_types)

		if count == 0:
			return []

		# Check if ALL segments are hobby (common case, fast path)
		all_hobby = all(s == HOBBY for s in seg_types)

		if all_hobby:
			# Entire path is one run — use original solver path
			return [(0, n - 1, False, False)]

		# Find runs of consecutive hobby segments
		runs = []
		i = 0

		while i < count:
			if seg_types[i] == HOBBY:
				# Start of a hobby run
				start = i
				while i < count and seg_types[i] == HOBBY:
					i += 1
				end = i  # end is the index of the first non-hobby, or count

				# The run involves knots [start..end] 
				# (segment start→start+1 through segment end-1→end)

				# Boundary flags: does the run border a non-hobby segment?
				has_prev_boundary = start > 0 or (self.closed and seg_types[-1] != HOBBY)
				has_next_boundary = end < count or (self.closed and seg_types[0] != HOBBY)

				runs.append((start, end, has_prev_boundary, has_next_boundary))
			else:
				i += 1

		# Handle closed path wraparound: if first and last runs connect
		if self.closed and len(runs) >= 2:
			first = runs[0]
			last = runs[-1]

			# Check if last run's end wraps to first run's start
			if last[1] == count and first[0] == 0:
				# Merge: the run wraps around
				merged = (last[0], first[1] + n, last[2], first[3])
				runs = [merged] + runs[1:-1]

		return runs

	# - Boundary angle computation -------------
	def _compute_boundary_theta(self, knot_idx, direction='out'):
		'''Compute pinned angle at a knot from adjacent non-hobby segment.

		For a line segment prev→knot: arrival angle points from prev to knot.
		For a fixed segment prev→knot: arrival angle derived from the fixed BCP.
		For a direction-constrained knot: use the pinned direction directly.

		Args:
			knot_idx  : index into self.data
			direction : 'out' (departure) or 'in' (arrival)

		Returns: angle in radians relative to the chord, or None if free.
		'''
		knot = self[knot_idx]
		n = len(self.data)

		if direction == 'out':
			# Check explicit direction constraint first
			if knot.dir_out is not None:
				return knot.dir_out

			# Check segment type of the OUTGOING segment
			# (segment from knot_idx to knot_idx+1)
			# Not relevant here — we want what PINS this knot's departure
			# That comes from the INCOMING segment (prev→this)
			prev_idx = (knot_idx - 1) % n
			prev_knot = self[prev_idx]

			if prev_knot.segment_type == LINE:
				# Line from prev to knot pins the arrival at knot
				# which in turn constrains departure if this is a smooth joint
				return math.atan2(knot.y - prev_knot.y, knot.x - prev_knot.x)

			elif prev_knot.segment_type == FIXED:
				# Fixed BCP: direction determined by the incoming BCP
				if knot.fixed_bcp_in is not None:
					d = knot.complex - knot.fixed_bcp_in
					if abs(d) > 1e-10:
						return cmath.phase(d)

			return None

		else:  # direction == 'in'
			# Check explicit direction constraint first
			if knot.dir_in is not None:
				return knot.dir_in

			# Check segment type of the OUTGOING segment from this knot
			if knot.segment_type == LINE:
				next_idx = (knot_idx + 1) % n
				next_knot = self[next_idx]
				return math.atan2(next_knot.y - knot.y, next_knot.x - knot.x)

			elif knot.segment_type == FIXED:
				if knot.fixed_bcp_out is not None:
					d = knot.fixed_bcp_out - knot.complex
					if abs(d) > 1e-10:
						return cmath.phase(d)

			return None

	# - Per-run METAFONT solver ----------------
	def _solve_run(self, start, end, boundary_start, boundary_end):
		'''Solve the METAFONT linear system for a single free run.

		Args:
			start, end       : knot indices defining the run
			boundary_start   : pinned theta at run start (radians) or None
			boundary_end     : pinned phi at run end (radians) or None
		'''
		n = len(self.data)

		# Collect knot indices for this run
		if end > n:
			# Wrapped run in closed path
			indices = list(range(start, n)) + list(range(0, end - n + 1))
		else:
			indices = list(range(start, end + 1))

		run_len = len(indices)

		if run_len < 2:
			return  # Nothing to solve

		# Build METAFONT coefficient system for this run
		# Following the same logic as the original __build_coefficients
		# but only for knots in this run, with boundary conditions
		A = []; B = []; C = []; D = []; R = []

		# Determine if this sub-path is effectively open or closed
		is_run_closed = self.closed and not boundary_start and not boundary_end and run_len == n

		if is_run_closed:
			# Full closed path, no boundaries — original algorithm
			for k in range(run_len):
				ki = indices[k]
				kp = indices[(k - 1) % run_len]  # prev in run
				kn = indices[(k + 1) % run_len]  # next in run

				A.append(self[kp].alpha / (self[ki].beta**2 * self[ki].d_ant))
				B.append((3 - self[kp].alpha) / (self[ki].beta**2 * self[ki].d_ant))
				C.append((3 - self[kn].beta) / (self[ki].alpha**2 * self[ki].d_post))
				D.append(self[kn].beta / (self[ki].alpha**2 * self[ki].d_post))
				R.append(-B[k] * self[ki].xi - D[k] * self[kn].xi)
		else:
			# Open run (or sub-run with boundaries)
			# First knot boundary condition
			ki_0 = indices[0]
			ki_1 = indices[1]

			if boundary_start is not None:
				# Pinned departure: theta[0] is known
				# Set equation: theta[0] = boundary_value
				# Implemented as: 0*theta[-1] + 1*theta[0] + 0*theta[1] = boundary_value
				# But we need to express boundary_start as theta relative to chord
				chord_angle = math.atan2(
					self[ki_1].y - self[ki_0].y,
					self[ki_1].x - self[ki_0].x
				)
				theta_0 = boundary_start - chord_angle

				A.append(0)
				B.append(1)  # Will be added to C[0] in the diagonal
				C.append(0)
				D.append(0)
				R.append(theta_0)
			else:
				# Natural boundary (curl) — same as original
				xi_0 = (self[ki_0].alpha**2) * self.curl_start / (self[ki_1].beta**2)

				A.append(0)
				B.append(0)
				C.append(xi_0 * self[ki_0].alpha + 3 - self[ki_1].beta)
				D.append((3 - self[ki_0].alpha) * xi_0 + self[ki_1].beta)
				R.append(-D[0] * self[ki_1].xi)

			# Interior knots
			for k in range(1, run_len - 1):
				ki = indices[k]
				kp = indices[k - 1]
				kn = indices[k + 1]

				A.append(self[kp].alpha / (self[ki].beta**2 * self[ki].d_ant))
				B.append((3 - self[kp].alpha) / (self[ki].beta**2 * self[ki].d_ant))
				C.append((3 - self[kn].beta) / (self[ki].alpha**2 * self[ki].d_post))
				D.append(self[kn].beta / (self[ki].alpha**2 * self[ki].d_post))
				R.append(-B[k] * self[ki].xi - D[k] * self[kn].xi)

			# Last knot boundary condition
			ki_n = indices[-1]
			ki_nm1 = indices[-2]

			if boundary_end is not None:
				# Pinned arrival: phi at end is known
				# theta[end] + phi[end] + xi[end] = 0
				# So theta[end] = -phi[end] - xi[end]
				chord_angle = math.atan2(
					self[ki_n].y - self[ki_nm1].y,
					self[ki_n].x - self[ki_nm1].x
				)
				phi_n = chord_angle - boundary_end
				theta_n = -phi_n - self[ki_n].xi

				k = run_len - 1
				A.append(0)
				B.append(1)
				C.append(0)
				D.append(0)
				R.append(theta_n)
			else:
				# Natural boundary (curl) — same as original
				k = run_len - 1
				xi_n = (self[ki_n].beta**2) * self.curl_end / (self[ki_nm1].alpha**2)

				C.append(0)
				D.append(0)
				A.append((3 - self[ki_n].beta) * xi_n + self[ki_nm1].alpha)
				B.append(self[ki_n].beta * xi_n + 3 - self[ki_nm1].alpha)
				R.append(0)

		# Solve the linear system
		L = len(R)

		if L < 1:
			return

		a = zero_matrix(L, L)
		b = [[v] for v in R]

		for k in range(L):
			prev = (k - 1) % L
			post = (k + 1) % L
			a[k][prev] = A[k]
			a[k][k] = B[k] + C[k]
			a[k][post] = D[k]

		try:
			v = solve_equations(a, b)
			thetas = sum(v, [])
		except (ZeroDivisionError, ValueError):
			# Solver failed — fall back to zero angles
			thetas = [0.] * L

		# Store solved angles on knots
		for k in range(L):
			ki = indices[k]
			self[ki].theta = thetas[k]
			self[ki].phi = -self[ki].theta - self[ki].xi

	# - Control point computation ---------------
	def _compute_hobby_controls(self, k0_idx, k1_idx):
		'''Compute Hobby control points for a single hobby segment.'''
		z0 = self[k0_idx].complex
		z1 = self[k1_idx].complex
		theta = self[k0_idx].theta
		phi = self[k1_idx].phi
		alpha = self[k0_idx].alpha
		beta = self[k1_idx].beta

		u, v = hobby_control_points(z0, z1, theta, phi, alpha, beta)

		self[k0_idx].u_right = u
		self[k1_idx].v_left = v

	# - Main solve pipeline --------------------
	def solve(self):
		'''Run the complete solving pipeline:
		1. Classify segments
		2. Pin boundary angles from lines/fixed segments
		3. Find free runs
		4. Solve each run independently
		5. Compute control points for all hobby segments
		'''
		n = len(self.data)

		if n < 2:
			return

		seg_types = self._classify_segments()

		# Pre-compute pinned directions from line/fixed segments
		count = len(seg_types)

		for i in range(count):
			knot = self.data[i]
			next_idx = (i + 1) % n

			if knot.segment_type == LINE:
				# Line pins departure at this knot and arrival at next
				knot.pin_dir_out_toward(self[next_idx])
				self[next_idx].pin_dir_in_from(knot)

			elif knot.segment_type == FIXED:
				# Fixed BCPs pin directions at both endpoints
				if knot.fixed_bcp_out is not None:
					d = knot.fixed_bcp_out - knot.complex
					if abs(d) > 1e-10:
						knot.dir_out = cmath.phase(d)

				next_knot = self[next_idx]
				if next_knot.fixed_bcp_in is not None:
					d = next_knot.complex - next_knot.fixed_bcp_in
					if abs(d) > 1e-10:
						next_knot.dir_in = cmath.phase(d)

		# Find and solve free runs
		runs = self._find_free_runs(seg_types)

		for start, end, has_prev_bound, has_next_bound in runs:
			# Compute boundary angles for this run
			bound_start = None
			bound_end = None

			if has_prev_bound:
				run_start = start % n
				bound_start = self._compute_boundary_theta(run_start, 'out')

			end_idx = end % n if end < 2 * n else end % n
			if has_next_bound:
				bound_end = self._compute_boundary_theta(end_idx, 'in')

			self._solve_run(start % n, end_idx, bound_start, bound_end)

		# Compute control points for all hobby segments
		for i in range(count):
			if seg_types[i] == HOBBY:
				next_idx = (i + 1) % n
				self._compute_hobby_controls(i, next_idx)

	# - Output ---------------------------------
	@property
	def nodes(self):
		'''Solve and return flat list of Node objects.
		Same output format as the original HobbySpline.nodes.
		'''
		self.solve()

		# - Init
		return_nodes = []
		n = len(self.data)
		count = n if self.closed else n - 1

		# - Assemble segments
		for i in range(count):
			knot = self.data[i]
			next_idx = (i + 1) % n
			next_knot = self[next_idx]

			# On-curve node
			z = knot.point
			return_nodes.append(Node(z.x, z.y, type='on'))

			if knot.segment_type == HOBBY:
				# Hobby-solved BCPs
				u = knot.u_right
				v = next_knot.v_left

				# Apply convexity correction
				z0 = knot.complex
				z3 = next_knot.complex
				u, v = force_convex(z0, u, v, z3)

				return_nodes.append(Node(u.real, u.imag, type='curve'))
				return_nodes.append(Node(v.real, v.imag, type='curve'))

			elif knot.segment_type == LINE:
				# No off-curve points for lines
				pass

			elif knot.segment_type == FIXED:
				# User-provided BCPs
				bcp_out = knot.fixed_bcp_out
				bcp_in = next_knot.fixed_bcp_in

				if bcp_out is None:
					bcp_out = knot.complex
				if bcp_in is None:
					bcp_in = next_knot.complex

				return_nodes.append(Node(bcp_out.real, bcp_out.imag, type='curve'))
				return_nodes.append(Node(bcp_in.real, bcp_in.imag, type='curve'))

		# Terminal on-curve node
		if self.closed:
			last_z = self[0].point
		else:
			last_z = self[-1].point

		return_nodes.append(Node(last_z.x, last_z.y, type='on'))

		return return_nodes

	@property
	def segments(self):
		'''Return list of CubicBezier/Line segment objects.'''
		from typerig.core.objects.cubicbezier import CubicBezier
		from typerig.core.objects.line import Line

		self.solve()

		result = []
		n = len(self.data)
		count = n if self.closed else n - 1

		for i in range(count):
			knot = self.data[i]
			next_idx = (i + 1) % n
			next_knot = self[next_idx]

			if knot.segment_type == LINE:
				result.append(Line(knot.point, next_knot.point))

			elif knot.segment_type == HOBBY:
				u = knot.u_right
				v = next_knot.v_left
				z0, z3 = knot.complex, next_knot.complex
				u, v = force_convex(z0, u, v, z3)

				result.append(CubicBezier(
					knot.point.tuple,
					(u.real, u.imag),
					(v.real, v.imag),
					next_knot.point.tuple
				))

			elif knot.segment_type == FIXED:
				bcp_out = knot.fixed_bcp_out or knot.complex
				bcp_in = next_knot.fixed_bcp_in or next_knot.complex

				result.append(CubicBezier(
					knot.point.tuple,
					(bcp_out.real, bcp_out.imag),
					(bcp_in.real, bcp_in.imag),
					next_knot.point.tuple
				))

		return result

	# - Path query utilities -------------------
	def get_winding(self):
		'''Check if contour has clockwise winding direction'''
		return self.get_area() > 0

	def get_area(self):
		'''Get contour area using on-curve points only (shoelace formula)'''
		n = len(self.data)

		if n < 3:
			return 0.

		area = 0.
		for i in range(n):
			j = (i + 1) % n
			area += (self.data[j].x - self.data[i].x) * (self.data[j].y + self.data[i].y)

		return area * 0.5

	def reverse(self):
		'''Reverse path direction'''
		self.data = list(reversed(self.data))
		self.clockwise = not self.clockwise

		# Swap segment types: each knot's segment_type described connection 
		# to next, so after reversal we need to shift them
		n = len(self.data)

		if n < 2:
			return

		# Collect old segment types and fixed BCPs
		old_types = [k.segment_type for k in self.data]
		old_bcp_out = [k.fixed_bcp_out for k in self.data]
		old_bcp_in = [k.fixed_bcp_in for k in self.data]
		old_dir_out = [k.dir_out for k in self.data]
		old_dir_in = [k.dir_in for k in self.data]

		# After reversal, the segment that was between original knots [i] and [i+1]
		# is now between reversed knots [n-2-i] and [n-1-i]
		# The segment_type was on original knot[i], now needs to be on reversed position
		count = n if self.closed else n - 1

		for k in self.data:
			k.segment_type = HOBBY
			k.fixed_bcp_out = None
			k.fixed_bcp_in = None
			k.dir_out = None
			k.dir_in = None

		for i in range(count):
			# Original segment i→i+1 had type old_types[i]
			# After reverse, this becomes segment (n-2-i)→(n-1-i) in new indexing
			new_idx = n - 2 - i if not self.closed else (n - 1 - i) % n
			self.data[new_idx].segment_type = old_types[i]

			# Swap BCPs: out becomes in and vice versa
			self.data[new_idx].fixed_bcp_out = old_bcp_in[i + 1] if i + 1 < n else old_bcp_in[0]
			self.data[(new_idx + 1) % n].fixed_bcp_in = old_bcp_out[i]

			# Swap directions
			if old_dir_in[i + 1 if i + 1 < n else 0] is not None:
				self.data[new_idx].dir_out = old_dir_in[i + 1 if i + 1 < n else 0] + math.pi
			if old_dir_out[i] is not None:
				self.data[(new_idx + 1) % n].dir_in = old_dir_out[i] + math.pi

	# - Conversion utilities -------------------
	@classmethod
	def from_contour(cls, contour, **kwargs):
		'''Create HobbySpline from an existing Contour object.
		Auto-detects segment types using line detection and 
		recovers tension from existing Bézier handles.

		Args:
			contour   : Contour object with Node data
			tolerance : line detection tolerance (default 0.5)
		'''
		tolerance = kwargs.pop('tolerance', 0.5)
		hs = cls(closed=contour.closed, **kwargs)

		# Get on-curve nodes and their segments
		on_nodes = [n for n in contour.nodes if n.is_on]

		for i, node in enumerate(on_nodes):
			# Get the segment following this on-curve node
			seg = node.segment  # returns (on, bcp_out, bcp_in, next_on) or (on, next_on)

			if seg is None or len(seg) <= 2:
				# Line segment
				hs.add_knot((node.x, node.y), segment=LINE)

			else:
				# Cubic segment — check if it's effectively a line
				z0 = complex(seg[0].x, seg[0].y)
				z1 = complex(seg[1].x, seg[1].y)
				z2 = complex(seg[2].x, seg[2].y)
				z3 = complex(seg[3].x, seg[3].y)

				if is_line_segment(z0, z1, z2, z3, tolerance):
					hs.add_knot((node.x, node.y), segment=LINE)
				else:
					# Recover tension from existing handles
					alpha, beta = recover_tension(z0, z1, z2, z3)

					hs.add_knot(
						(node.x, node.y),
						segment=HOBBY,
						alpha=alpha,
						beta=beta
					)

		return hs

	def to_contour(self):
		'''Convert to a Contour object.'''
		from typerig.core.objects.contour import Contour
		return Contour(self.nodes, closed=self.closed)

	# - Post-processing -------------------------
	def insert_extremes(self):
		'''Insert nodes at curve extreme points.
		Returns a new list of Nodes with additional on-curve points
		at horizontal and vertical extremes. Based on MetaType1 
		insert_extremes — essential for font production.
		'''
		from typerig.core.objects.cubicbezier import CubicBezier

		segments = self.segments
		result_nodes = []

		for seg in segments:
			if isinstance(seg, CubicBezier):
				# Add the starting on-curve
				result_nodes.append(Node(seg.p0.x, seg.p0.y, type='on'))

				# Find extremes
				extremes = seg.solve_extremes()

				if extremes:
					# Sort by t value
					extremes.sort(key=lambda e: e[1])

					# Split at each extreme
					remaining = seg
					t_offset = 0.

					for point, t in extremes:
						# Adjust t for previous splits
						adj_t = (t - t_offset) / (1. - t_offset)

						if 0.01 < adj_t < 0.99:
							parts = remaining.solve_slice(adj_t)

							# First part: add its BCPs
							result_nodes.append(Node(parts[0][1][0], parts[0][1][1], type='curve'))
							result_nodes.append(Node(parts[0][2][0], parts[0][2][1], type='curve'))

							# Extreme point as on-curve
							result_nodes.append(Node(point.x, point.y, type='on'))

							# Continue with second part
							remaining = CubicBezier(*parts[1])
							t_offset = t

					# Final part BCPs
					result_nodes.append(Node(remaining.p1.x, remaining.p1.y, type='curve'))
					result_nodes.append(Node(remaining.p2.x, remaining.p2.y, type='curve'))

				else:
					# No extremes — just add BCPs
					result_nodes.append(Node(seg.p1.x, seg.p1.y, type='curve'))
					result_nodes.append(Node(seg.p2.x, seg.p2.y, type='curve'))

			else:
				# Line segment — just add start point
				result_nodes.append(Node(seg.p0.x, seg.p0.y, type='on'))

		# Terminal node
		if self.closed:
			result_nodes.append(Node(self[0].x, self[0].y, type='on'))
		else:
			last = self[-1]
			result_nodes.append(Node(last.x, last.y, type='on'))

		return result_nodes

	# - Properties -----------------------------------
	@property
	def knots(self):
		return self.data

	@knots.setter
	def knots(self, other):
		if isinstance(other, self.__class__):
			self.data = other.data
		elif isinstance(other, (tuple, list)):
			self.data = [self._coerce(item) for item in other]

	@property
	def knot_count(self):
		if self.closed:
			return range(len(self.data))
		else:
			return range(1, len(self.data) - 1)

	@property
	def tension(self):
		return self.global_tension

	@tension.setter
	def tension(self, other):
		self.global_tension = other

		for knot in self.knots:
			knot.alpha = other
			knot.beta = other

	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(
			self.__class__.__name__, len(self.data))
		return Bounds([knot.point.tuple for knot in self.data])

	# - Transformation --------------------------
	def apply_transform(self):
		for knot in self.data:
			knot.x, knot.y = self.transform.applyTransformation(knot.x, knot.y)

	def shift(self, delta_x, delta_y):
		for knot in self.data:
			knot.point += Point(delta_x, delta_y)


# - Test ----------------------------------------------------------------
if __name__ == '__main__':
	from pprint import pprint
	section = lambda s: '\n--- {} {}'.format(s, '-' * (40 - len(s)))

	# -- Test 1: Backward compatible — all hobby (tuple list)
	print(section('All Hobby (closed)'))
	hs = HobbySpline([(0, 320), (320, 640), (640, 320), (320, 0)], closed=True)
	hs.tension = 1.
	pprint(hs.nodes)

	# -- Test 2: Mixed segments — hobby + line
	print(section('Mixed: hobby + line'))
	hs2 = HobbySpline(closed=True)
	hs2.add_knot((0, 320))
	hs2.add_knot((320, 640))
	hs2.add_knot((640, 320), segment=LINE)
	hs2.add_knot((320, 0))
	pprint(hs2.nodes)

	# -- Test 3: Fixed handles
	print(section('Fixed handles'))
	hs3 = HobbySpline(closed=False)
	hs3.add_knot((0, 0))
	hs3.add_knot((100, 200), segment=FIXED, bcp_out=(130, 250), bcp_in=(70, 150))
	hs3.add_knot((300, 200))
	hs3.add_knot((400, 0))
	pprint(hs3.nodes)

	# -- Test 4: Direction constraint
	print(section('Direction constraint'))
	hs4 = HobbySpline(closed=False)
	hs4.add_knot((0, 0), dir_out=math.pi / 4)  # depart at 45°
	hs4.add_knot((200, 200))
	hs4.add_knot((400, 0), dir_in=-math.pi / 4)  # arrive at -45°
	pprint(hs4.nodes)

	# -- Test 5: All lines
	print(section('All lines'))
	hs5 = HobbySpline(closed=True)
	hs5.add_knot((0, 0), segment=LINE)
	hs5.add_knot((100, 0), segment=LINE)
	hs5.add_knot((100, 100), segment=LINE)
	hs5.add_knot((0, 100), segment=LINE)
	pprint(hs5.nodes)

	# -- Test 6: Utility functions
	print(section('Utilities'))
	print('turning_angle:', turning_angle(complex(1, 0), complex(0, 1)))
	print('is_line:', is_line_segment(0+0j, 33+0j, 66+0j, 100+0j))
	print('is_line (false):', is_line_segment(0+0j, 0+50j, 100+50j, 100+0j))
	print('recover_tension:', recover_tension(0+0j, 33+15j, 66+15j, 100+0j))
