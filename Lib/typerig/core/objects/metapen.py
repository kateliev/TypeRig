# MODULE: TypeRig / Core / MetaPen (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Pen stroke envelope system.
# Based on MetaType1 plain_ex.mp by Bogusław Jackowski 
# and Janusz Nowacki, adapted to Python/TypeRig.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math
import cmath

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.quadraticbezier import QuadraticBezier
from typerig.core.objects.node import Node, node_types
from typerig.core.objects.contour import Contour

from typerig.core.objects.hobbyspline import (
	robust_direction,
	robust_direction_end,
	turning_angle,
	is_line_segment,
	force_convex,
	extrapolate_segment,
)

# - Init --------------------------------
__version__ = '0.3.0'

# - Constants ---------------------------
# Default miter limit — ratio of miter length to half stroke width.
# When exceeded, miter falls back to bevel. SVG default is 4.0.
MITER_LIMIT_DEFAULT = 4.0
# Join types at corners
JOIN_ROUND = 'round'    # Pen arc (linejoin:=rounded)
JOIN_MITER = 'miter'    # Extrapolate edges until intersection (linejoin:=mitered)
JOIN_BEVEL = 'bevel'    # Connect endpoints with straight line (linejoin:=beveled)

# Cap types at open path ends
CAP_ROUND = 'round'     # Pen arc (linecap:=rounded)
CAP_BUTT = 'butt'       # Cut perpendicular to path direction (linecap:=butt)

# Stroke method — controls how envelope edges are computed
METHOD_DIRECTION = 0    # Edges built from direction constraints (MetaType1 default)
METHOD_EXPLICIT = 1     # Explicit control points with convexity forcing
METHOD_FREE = 2         # Explicit control points without forcing

# - Nib shapes --------------------------
class Nib(object):
	'''Pen nib shape — a closed path representing the pen cross-section.

	The nib is centered at origin and can be elliptic or razor (line).
	Provides tangent_point() — the key operation for envelope construction:
	given a direction of pen movement, find the point on the nib outline 
	where the tangent is parallel to that direction.

	Attributes:
		path     : list of complex — nib outline as closed path
		                              [(on, bcp_out, bcp_in, on, ...)]
		is_razor : bool — True if this is a degenerate (line) nib
	'''

	def __init__(self, path=None, is_razor=False):
		self.path = path or []
		self.is_razor = is_razor

	def __repr__(self):
		kind = 'razor' if self.is_razor else 'elliptic'
		return '<Nib {} nodes={}>'.format(kind, self.node_count)

	@property
	def node_count(self):
		'''Number of on-curve nodes'''
		if self.is_razor:
			return 2
		# Count on-curve nodes (every 3rd point in cubic path)
		return len(self.segments)

	@property
	def segments(self):
		'''Return nib as list of (p0, p1, p2, p3) cubic segments.
		For a razor nib returns a single line segment.
		'''
		if self.is_razor:
			return [(self.path[0], self.path[0], self.path[1], self.path[1])]

		result = []
		n = len(self.path)

		# Path layout: on0, bcp_out0, bcp_in1, on1, bcp_out1, bcp_in2, on2, ...
		# Each segment: (on_i, bcp_out_i, bcp_in_i+1, on_i+1)
		seg_count = n // 3

		for i in range(seg_count):
			idx = i * 3
			p0 = self.path[idx]
			p1 = self.path[idx + 1]
			p2 = self.path[idx + 2]
			p3 = self.path[(idx + 3) % n]
			result.append((p0, p1, p2, p3))

		return result

	def shifted(self, z):
		'''Return a copy of this nib shifted by complex z'''
		return Nib(
			[p + z for p in self.path],
			is_razor=self.is_razor
		)

	def scaled(self, factor):
		'''Return a copy scaled uniformly'''
		return Nib(
			[p * factor for p in self.path],
			is_razor=self.is_razor
		)

	def xyscaled(self, sx, sy):
		'''Return a copy scaled independently in x and y'''
		return Nib(
			[complex(p.real * sx, p.imag * sy) for p in self.path],
			is_razor=self.is_razor
		)

	def rotated(self, angle_deg):
		'''Return a copy rotated by angle in degrees'''
		r = cmath.exp(1j * math.radians(angle_deg))
		return Nib(
			[p * r for p in self.path],
			is_razor=self.is_razor
		)

	def tangent_point(self, direction):
		'''Find the point on the nib where the tangent is parallel
		to the given direction vector (complex).

		For elliptic nibs: solves analytically. The tangent of a cubic
		segment is quadratic in t; requiring its cross product with the
		direction to be zero gives a quadratic equation with closed-form
		roots. Exact — no sampling.

		For razor nibs: returns the endpoint whose normal faces
		the direction. Based on MetaType1 tangent_point.

		Args:
			direction : complex — direction of pen movement

		Returns:
			complex — point on nib outline
		'''
		if abs(direction) < 1e-10:
			return self.path[0] if self.path else complex(0, 0)

		d = direction / abs(direction)  # Normalize

		if self.is_razor:
			p0, p1 = self.path[0], self.path[1]
			edge = p1 - p0

			if abs(edge) < 1e-10:
				return p0

			ta = turning_angle(direction, edge)

			if ta is None:
				return (p0 + p1) * 0.5

			if ta < 0:
				return p0
			else:
				return p1

		# Elliptic nib: analytical directiontime.
		# For each cubic segment (z0,z1,z2,z3), the tangent is:
		#   T(t) = 3(1-t)²(z1-z0) + 6(1-t)t(z2-z1) + 3t²(z3-z2)
		# We need T(t) × d = 0 (cross product, i.e. T parallel to d).
		# Writing T(t) = At² + Bt + C and expanding the cross product
		# gives a quadratic in t.
		segs = self.segments
		best_dot = -2.
		best_point = self.path[0]

		dx, dy = d.real, d.imag

		for z0, z1, z2, z3 in segs:
			# Tangent coefficients: T(t) = A*t² + B*t + C
			# where C = 3(z1-z0), B = 6(z2-z1) - 6(z1-z0), A = 3(z3-z2) - 6(z2-z1) + 3(z1-z0)
			c0 = z1 - z0
			c1 = z2 - z1
			c2 = z3 - z2

			C = 3. * c0
			B = 6. * (c1 - c0)
			A = 3. * (c2 - 2. * c1 + c0)

			# Cross product T(t) × d = (Tx*dy - Ty*dx) = 0
			# Expand: (Ax*dy - Ay*dx)t² + (Bx*dy - By*dx)t + (Cx*dy - Cy*dx) = 0
			qa = A.real * dy - A.imag * dx
			qb = B.real * dy - B.imag * dx
			qc = C.real * dy - C.imag * dx

			# Collect candidate t values
			candidates = []

			if abs(qa) < 1e-12:
				# Linear or constant
				if abs(qb) > 1e-12:
					candidates.append(-qc / qb)
			else:
				disc = qb * qb - 4. * qa * qc

				if disc >= 0:
					sq = math.sqrt(disc)
					candidates.append((-qb + sq) / (2. * qa))
					candidates.append((-qb - sq) / (2. * qa))

			# Evaluate candidates within [0, 1]
			for t in candidates:
				if t < -1e-6 or t > 1. + 1e-6:
					continue

				t = max(0., min(1., t))
				mt = 1. - t

				# Tangent at t (for dot-product check)
				tangent = mt * mt * C + mt * t * (C + B) + t * t * (C + B + A)

				if abs(tangent) < 1e-10:
					continue

				tn = tangent / abs(tangent)
				dot = (d.conjugate() * tn).real

				if dot > best_dot:
					best_dot = dot

					# Evaluate point on curve
					best_point = (mt**3 * z0 + 3. * mt**2 * t * z1 +
								  3. * mt * t**2 * z2 + t**3 * z3)

		return best_point

	def arc_between(self, dir_a, dir_b, center):
		'''DEPRECATED — kept for compatibility. Use _emit_round_join() or
		_compute_cap() instead, which anchor arcs to actual edge endpoints
		and use the correct kappa formula.

		Original: extract the nib arc between two directions using coarse
		tangent_point sampling and approximate BCP placement.

		Args:
			dir_a  : complex — first direction (arrival)
			dir_b  : complex — second direction (departure)
			center : complex — center point to shift nib to

		Returns:
			list of complex — arc points (on-curves and BCPs)
		'''
		if self.is_razor:
			# Razor nib at a corner: just connect the two tangent points
			p_a = self.tangent_point(dir_a) + center
			p_b = self.tangent_point(dir_b) + center
			return [p_a, p_b]

		# Elliptic nib: find the subpath between tangent times
		shifted = self.shifted(center)
		p_a = shifted.tangent_point(dir_a)
		p_b = shifted.tangent_point(dir_b)

		# For now, return a simple arc approximation
		# TODO: exact subpath extraction from nib path
		ta = turning_angle(dir_a, dir_b)

		if ta is None or abs(ta) < 0.01:
			return [p_a, p_b]

		# Create a simple arc through the midpoint
		mid_dir = dir_a * cmath.exp(1j * ta * 0.5)
		p_mid = shifted.tangent_point(mid_dir)

		# Approximate with cubic: p_a .. p_mid .. p_b
		# Use 1/3 rule for circular arc approximation
		chord_a = p_mid - p_a
		chord_b = p_b - p_mid
		kappa = 4. / 3. * math.tan(abs(ta) / 4)

		bcp_out_a = p_a + kappa * complex(-chord_a.imag, chord_a.real) * (1 if ta > 0 else -1) * 0.5
		bcp_in_mid = p_mid - kappa * complex(-chord_a.imag, chord_a.real) * (1 if ta > 0 else -1) * 0.5
		bcp_out_mid = p_mid + kappa * complex(-chord_b.imag, chord_b.real) * (1 if ta > 0 else -1) * 0.5
		bcp_in_b = p_b - kappa * complex(-chord_b.imag, chord_b.real) * (1 if ta > 0 else -1) * 0.5

		return [p_a, bcp_out_a, bcp_in_mid, p_mid, bcp_out_mid, bcp_in_b, p_b]

	# - Factory methods -------------------------
	@classmethod
	def razor(cls, width, angle=0.):
		'''Create a razor (line) nib.
		Equivalent to MetaType1 fix_razor_nib.

		Args:
			width : float — total width of the razor
			angle : float — rotation angle in degrees
		'''
		half = width / 2.
		r = cmath.exp(1j * math.radians(angle))
		p0 = complex(-half, 0) * r
		p1 = complex(half, 0) * r
		return cls([p0, p1], is_razor=True)

	@classmethod
	def elliptic(cls, x_diam, y_diam, angle=0.):
		'''Create an elliptic nib approximation.
		Equivalent to MetaType1 fix_elliptic_nib.

		Uses a 4-point Bézier approximation of an ellipse with the 
		standard kappa = 4*(sqrt(2)-1)/3 ≈ 0.5522847 handle factor.

		Args:
			x_diam : float — horizontal diameter
			y_diam : float — vertical diameter
			angle  : float — rotation angle in degrees
		'''
		if x_diam == 0 and y_diam == 0:
			raise ValueError('Null pen not allowed')

		if y_diam == 0:
			return cls.razor(x_diam, angle)

		if x_diam == 0:
			return cls.razor(y_diam, angle + 90)

		# 4-point ellipse approximation
		kappa = 4. * (math.sqrt(2) - 1) / 3.
		rx, ry = x_diam / 2., y_diam / 2.
		r = cmath.exp(1j * math.radians(angle))

		# On-curve points at cardinal directions
		top = complex(0, ry)
		right = complex(rx, 0)
		bottom = complex(0, -ry)
		left = complex(-rx, 0)

		# BCP handle offsets
		hx = rx * kappa
		hy = ry * kappa

		# Build path: top → right → bottom → left → cycle
		# Each segment: (on, bcp_out, bcp_in, next_on)
		path = [
			top,                              # on: top
			complex(hx, ry),                  # bcp_out: top→right
			complex(rx, hy),                  # bcp_in:  top→right

			right,                            # on: right
			complex(rx, -hy),                 # bcp_out: right→bottom
			complex(hx, -ry),                 # bcp_in:  right→bottom

			bottom,                           # on: bottom
			complex(-hx, -ry),                # bcp_out: bottom→left
			complex(-rx, -hy),                # bcp_in:  bottom→left

			left,                             # on: left
			complex(-rx, hy),                 # bcp_out: left→top
			complex(-hx, ry),                 # bcp_in:  left→top
		]

		# Apply rotation
		path = [p * r for p in path]

		return cls(path, is_razor=False)

	@classmethod
	def circle(cls, diameter):
		'''Shorthand for circular nib'''
		return cls.elliptic(diameter, diameter, 0.)

	@classmethod 
	def from_width_contrast(cls, width, contrast=1., angle=0.):
		'''Create nib from width and contrast ratio.
		Convenient for type design: contrast < 1 thins the perpendicular axis.

		Args:
			width    : float — stroke width (max diameter)
			contrast : float — ratio of thin to thick (0..1)
			angle    : float — broadnib angle in degrees
		'''
		return cls.elliptic(width, width * contrast, angle)


# - Node-level stroke options -----------
class NodeStrokeOpts(object):
	'''Per-node configuration for pen stroke expansion.
	Equivalent to MetaType1's nib/cut/tip/ignore_directions options.

	Attributes:
		nib_left     : Nib or None — custom nib for left edge at this node
		nib_right    : Nib or None — custom nib for right edge at this node
		cut_angle    : float or None — cut angle in degrees (butt cap)
		cut_relative : bool — if True, cut_angle is relative to path direction
		tip          : tuple(float, float) or None — (pre_elongation, post_elongation) 
		               for miter join at this node
		ignore_dir_l : bool — don't force direction on left edge
		ignore_dir_r : bool — don't force direction on right edge
	'''

	def __init__(self, **kwargs):
		self.nib_left = kwargs.pop('nib_left', None)
		self.nib_right = kwargs.pop('nib_right', None)
		self.cut_angle = kwargs.pop('cut_angle', None)
		self.cut_relative = kwargs.pop('cut_relative', False)
		self.tip = kwargs.pop('tip', None)
		self.ignore_dir_l = kwargs.pop('ignore_dir_l', False)
		self.ignore_dir_r = kwargs.pop('ignore_dir_r', False)

	def __repr__(self):
		parts = []
		if self.nib_left or self.nib_right:
			parts.append('nib')
		if self.cut_angle is not None:
			parts.append('cut({}{})'.format(
				'rel ' if self.cut_relative else '', self.cut_angle))
		if self.tip is not None:
			parts.append('tip({},{})'.format(*self.tip))
		if self.ignore_dir_l:
			parts.append('ignore_l')
		if self.ignore_dir_r:
			parts.append('ignore_r')
		return '<NodeStrokeOpts {}>'.format(' '.join(parts) if parts else 'default')

	@property
	def has_custom_nib(self):
		return self.nib_left is not None or self.nib_right is not None

	@property
	def has_cut(self):
		return self.cut_angle is not None

	@property
	def has_tip(self):
		return self.tip is not None

	@property
	def is_default(self):
		return not (self.has_custom_nib or self.has_cut or self.has_tip or
					self.ignore_dir_l or self.ignore_dir_r)

	# - Factory helpers -------------------------
	@classmethod
	def nib(cls, pen, nodes_lr='both'):
		'''Create options that set a custom nib.
		nodes_lr: 'left', 'right', or 'both'
		'''
		opts = cls()
		if nodes_lr in ('left', 'both'):
			opts.nib_left = pen
		if nodes_lr in ('right', 'both'):
			opts.nib_right = pen
		return opts

	@classmethod
	def cut(cls, angle, relative=False):
		'''Create options for a butt cut at given angle'''
		return cls(cut_angle=angle, cut_relative=relative)

	@classmethod
	def miter(cls, pre_elongation=0.5, post_elongation=0.5):
		'''Create options for a miter (tip) join'''
		return cls(tip=(pre_elongation, post_elongation))

	@classmethod
	def bevel(cls):
		'''Create options for a bevel join (tip with zero elongation)'''
		return cls(tip=(0., 0.))


# - Stroke result container -------------
class StrokeResult(object):
	'''Container for pen stroke expansion results.

	Each edge/cap stores both geometry (complex points) and parallel
	node type tags ('on' or 'curve') so that to_nodes() can produce
	correct PS cubic contours without guessing.

	Attributes:
		right       : list of complex — right edge points
		right_types : list of str — node types for right edge
		left        : list of complex — left edge points
		left_types  : list of str — node types for left edge
		begin       : list of complex — begin cap points
		begin_types : list of str — node types for begin cap
		end         : list of complex — end cap points
		end_types   : list of str — node types for end cap
	'''

	def __init__(self, closed=False):
		self.right = []
		self.right_types = []
		self.left = []
		self.left_types = []
		self.begin = []
		self.begin_types = []
		self.end = []
		self.end_types = []
		self._closed = closed

	@property
	def is_closed_path(self):
		'''True if this result comes from a closed skeleton path (no caps).
		Set by expand() — not inferred from cap contents, since butt caps
		are empty lists.
		'''
		return self._closed

	@property
	def outline(self):
		'''Complete outline path(s) as a flat point list.

		Open path:  single closed contour — right + end_cap + left + begin_cap.
		Closed path: single flat list — right + left (for backward compatibility).
		             Prefer to_contours() for closed paths which returns two
		             separate contours (outer and inner).
		'''
		if not self.is_closed_path:
			return self.right + self.end + self.left + self.begin
		else:
			return self.right + self.left

	@property
	def outline_types(self):
		'''Parallel node type list for outline.'''
		if not self.is_closed_path:
			return self.right_types + self.end_types + self.left_types + self.begin_types
		else:
			return self.right_types + self.left_types

	def to_nodes(self):
		'''Convert outline to Node list for Contour construction.
		Uses tracked node types — no heuristic guessing.

		For open paths: returns nodes for one closed contour.
		For closed paths: returns all nodes flat (use to_contours() instead).
		'''
		points = self.outline
		types = self.outline_types

		if not points:
			return []

		return [Node(z.real, z.imag, type=t) for z, t in zip(points, types)]

	def to_contours(self):
		'''Convert to Contour objects — the preferred output method.

		Open path:  returns [contour] — one closed contour with caps.
		Closed path: returns [outer_contour, inner_contour] — two separate
		             closed contours with correct winding for PS/OT rendering.
		'''
		if not self.is_closed_path:
			# Open path: single closed contour
			nodes = self.to_nodes()

			if nodes:
				return [Contour(nodes, closed=True)]

			return []
		else:
			# Closed path: two separate contours (outer + inner)
			contours = []

			if self.right and self.right_types:
				outer_nodes = [Node(z.real, z.imag, type=t)
							   for z, t in zip(self.right, self.right_types)]
				contours.append(Contour(outer_nodes, closed=True))

			if self.left and self.left_types:
				inner_nodes = [Node(z.real, z.imag, type=t)
							   for z, t in zip(self.left, self.left_types)]
				contours.append(Contour(inner_nodes, closed=True))

			return contours

	def to_node_lists(self):
		'''Return separate Node lists for right edge, left edge, caps'''
		def to_nodes(points, types):
			return [Node(z.real, z.imag, type=t) for z, t in zip(points, types)]

		return {
			'right': to_nodes(self.right, self.right_types),
			'left': to_nodes(self.left, self.left_types),
			'begin': to_nodes(self.begin, self.begin_types),
			'end': to_nodes(self.end, self.end_types),
			'outline': self.to_nodes(),
		}


# - Envelope edge construction ----------
def _bezier_at(z0, z1, z2, z3, t):
	'''Evaluate cubic Bézier at parameter t'''
	mt = 1 - t
	return mt**3 * z0 + 3 * mt**2 * t * z1 + 3 * mt * t**2 * z2 + t**3 * z3

def _bezier_tangent(z0, z1, z2, z3, t):
	'''Tangent (first derivative) of cubic Bézier at parameter t'''
	mt = 1 - t
	return 3 * mt**2 * (z1 - z0) + 6 * mt * t * (z2 - z1) + 3 * t**2 * (z3 - z2)

def _segment_to_complex(segment):
	'''Convert a CubicBezier, QuadraticBezier, or Line to tuple of 4 complex numbers'''
	if isinstance(segment, Line):
		z0 = complex(segment.p0.x, segment.p0.y)
		z3 = complex(segment.p1.x, segment.p1.y)
		return (z0, z0, z3, z3)  # Degenerate cubic

	elif isinstance(segment, QuadraticBezier):
		# Degree-elevate: quad (p0, p1, p2) → cubic (p0, q1, q2, p2)
		z0 = complex(segment.p0.x, segment.p0.y)
		z1q = complex(segment.p1.x, segment.p1.y)
		z3 = complex(segment.p2.x, segment.p2.y)
		z1 = z0 + (2.0 / 3.0) * (z1q - z0)
		z2 = z3 + (2.0 / 3.0) * (z1q - z3)
		return (z0, z1, z2, z3)

	else:
		return (complex(segment.p0.x, segment.p0.y),
				complex(segment.p1.x, segment.p1.y),
				complex(segment.p2.x, segment.p2.y),
				complex(segment.p3.x, segment.p3.y))

def _is_line(z0, z1, z2, z3):
	'''Quick line test for envelope segments'''
	return is_line_segment(z0, z1, z2, z3, tolerance=0.5)

def pen_stroke_edge_segment(z0, z1, z2, z3, nib_start, nib_end, method=METHOD_DIRECTION):
	'''Compute one edge segment of the pen envelope for a single Bézier.

	This is the core operation from MetaType1 pen_stroke_edge_.
	Given skeleton segment z0..z3 and nibs at start/end, offset 
	the segment by the nib tangent points.

	Args:
		z0, z1, z2, z3 : complex — skeleton Bézier control points
		nib_start       : Nib — pen at segment start
		nib_end         : Nib — pen at segment end
		method          : int — stroke method (0, 1, or 2)

	Returns:
		tuple of complex — (q0, q1, q2, q3) offset segment control points
	'''
	# Directions at start and end
	dir_start = robust_direction(z0, z1, z2, z3)
	dir_end = robust_direction_end(z0, z1, z2, z3)

	# Tangent points on nibs
	tp_start = nib_start.tangent_point(dir_start)
	tp_end = nib_end.tangent_point(dir_end)

	# Offset on-curve points
	qa = z0 + tp_start
	qb = z3 + tp_end

	if _is_line(z0, z1, z2, z3):
		# Line segment: offset is also a line
		return (qa, qa, qb, qb)

	if method == METHOD_DIRECTION:
		# Method 0: Use hobby-style direction constraints
		# The edge goes from qa{dir_start} to {dir_end}qb
		# Approximate with cubic using 1/3 chord heuristic
		chord = qb - qa
		chord_len = abs(chord)

		if chord_len < 1e-10:
			return (qa, qa, qb, qb)

		# Scale handle lengths proportionally to original
		orig_chord = abs(z3 - z0)

		if orig_chord < 1e-10:
			ratio = 1.
		else:
			ratio = chord_len / orig_chord

		# Use original handle directions with scaled lengths
		r_start = abs(z1 - z0) * ratio
		r_end = abs(z2 - z3) * ratio

		if abs(dir_start) > 1e-10:
			q1 = qa + (dir_start / abs(dir_start)) * r_start
		else:
			q1 = qa

		if abs(dir_end) > 1e-10:
			q2 = qb - (dir_end / abs(dir_end)) * r_end
		else:
			q2 = qb

		return (qa, q1, q2, qb)

	elif method in (METHOD_EXPLICIT, METHOD_FREE):
		# Methods 1,2: Explicit control points via proportional scaling
		# Heuristic from MetaType1: length(q_handle)/length(p_handle) ≈ length(q_chord)/length(p_chord)
		orig_chord = abs(z3 - z0)
		new_chord = abs(qb - qa)

		if orig_chord < 1e-10 or 2 * orig_chord < new_chord:
			# Too close or degenerate: fall back to direction method
			return pen_stroke_edge_segment(z0, z1, z2, z3, nib_start, nib_end, METHOD_DIRECTION)

		scale = new_chord / orig_chord
		ra = (z1 - z0) * scale
		rb = (z2 - z3) * scale
		q1 = qa + ra
		q2 = qb + rb

		# Apply convexity correction for method 1
		if method == METHOD_EXPLICIT:
			q1, q2 = force_convex(qa, q1, q2, qb)

		return (qa, q1, q2, qb)

	return (qa, qa, qb, qb)  # Fallback


def pen_stroke_edge(segments, nibs, method=METHOD_DIRECTION, ignore_dirs=None, is_closed=False, join=JOIN_ROUND, miter_limit=MITER_LIMIT_DEFAULT):
	'''Compute a full edge of the pen envelope.

	Processes each segment of the skeleton path, computing the offset
	edge and joining consecutive edge segments at corners.

	Args:
		segments     : list of (z0, z1, z2, z3) — skeleton segments as complex tuples
		nibs         : list of Nib — one per skeleton node (len = len(segments) + 1 for open,
		               len(segments) for closed)
		method       : int — stroke method
		ignore_dirs  : set of int or None — node indices where direction forcing is disabled
		is_closed    : bool — whether the skeleton path is closed
		join         : str — join type at corners ('round', 'miter', 'bevel')
		miter_limit  : float — max miter length / half stroke width before bevel fallback

	Returns:
		tuple of (list of complex, list of str) — edge path points and parallel node types
	'''
	if not segments:
		return [], []

	if ignore_dirs is None:
		ignore_dirs = set()

	n_seg = len(segments)

	# Compute each edge segment
	edge_segs = []

	for i in range(n_seg):
		z0, z1, z2, z3 = segments[i]
		nib_i = nibs[i % len(nibs)]
		nib_next = nibs[(i + 1) % len(nibs)]
		edge = pen_stroke_edge_segment(z0, z1, z2, z3, nib_i, nib_next, method)
		edge_segs.append(edge)

	# Assemble edge path with corner joins
	result = []
	types = []

	def _emit(point, ntype):
		result.append(point)
		types.append(ntype)

	def _emit_round_join(from_pt, to_pt, center):
		'''Emit a circular arc join from from_pt to to_pt around center.
		Only emits interior points (BCPs + mid on-curve). The caller
		must emit from_pt and to_pt as on-curves.
		Uses the same geometric approach as cap computation.
		'''
		r_from = from_pt - center
		r_to = to_pt - center

		# Angle between the two radii
		dot = r_from.real * r_to.real + r_from.imag * r_to.imag
		r_len = (abs(r_from) + abs(r_to)) * 0.5

		if r_len < 1e-6:
			return

		cos_a = max(-1.0, min(1.0, dot / (abs(r_from) * abs(r_to))))
		full_angle = math.acos(cos_a)

		if full_angle < 0.01:
			return  # Nearly coincident — no arc needed

		# Arc midpoint: bisect the angle
		mid_dir = r_from / abs(r_from) + r_to / abs(r_to)

		if abs(mid_dir) < 1e-10:
			# 180° — perpendicular bisector
			cross_check = r_from.real * r_to.imag - r_from.imag * r_to.real
			mid_dir = r_from * (1j if cross_check > 0 else -1j)

		r_mid = mid_dir / abs(mid_dir) * r_len
		p_mid = center + r_mid

		# Determine rotation sense from cross product
		cross = r_from.real * r_mid.imag - r_from.imag * r_mid.real
		rot = 1j if cross > 0 else -1j

		# Kappa for each half-arc: standard formula k = 4/3 * tan(θ/4)
		# where θ is the arc angle of each half
		half_angle = full_angle * 0.5
		kappa = 4.0 / 3.0 * math.tan(half_angle / 4.0)

		# First half: from_pt → p_mid
		bcp1 = from_pt + kappa * (r_from * rot)
		bcp2 = p_mid - kappa * (r_mid * rot)

		# Second half: p_mid → to_pt
		bcp3 = p_mid + kappa * (r_mid * rot)
		bcp4 = to_pt - kappa * (r_to * rot)

		_emit(bcp1, 'curve')
		_emit(bcp2, 'curve')
		_emit(p_mid, 'on')
		_emit(bcp3, 'curve')
		_emit(bcp4, 'curve')

	def _compute_miter(from_pt, to_pt, from_dir, to_dir):
		'''Compute miter join analytically via line-line intersection.
		Extends the edge lines from from_pt along from_dir and
		from to_pt along -to_dir, and finds where they meet.
		Returns the intersection point, or None if parallel.
		'''
		# Line 1: from_pt + t * from_dir
		# Line 2: to_pt - s * to_dir
		# Solve: from_pt + t * from_dir = to_pt - s * to_dir
		d1 = from_dir
		d2 = -to_dir
		dx = to_pt - from_pt

		denom = d1.real * d2.imag - d1.imag * d2.real

		if abs(denom) < 1e-10:
			return None  # Parallel — no intersection

		t = (dx.real * d2.imag - dx.imag * d2.real) / denom
		return from_pt + t * d1

	for i in range(n_seg):
		qa, q1, q2, qb = edge_segs[i]

		if i == 0:
			_emit(qa, 'on')

		# Add BCPs (skip for lines)
		if not _is_line(qa, q1, q2, qb):
			_emit(q1, 'curve')
			_emit(q2, 'curve')

		# Corner join to next segment
		if i < n_seg - 1 or is_closed:
			next_i = (i + 1) % n_seg
			qa_next = edge_segs[next_i][0]

			# Check gap between end of this edge and start of next
			gap = abs(qb - qa_next)

			if gap > 0.5:
				# Skeleton corner position
				node_pos = segments[i][3]

				if join == JOIN_MITER:
					# Analytical line-line intersection with miter limit
					dir_pre = robust_direction_end(*segments[i])
					dir_post = robust_direction(*segments[next_i])
					miter_pt = _compute_miter(qb, qa_next, dir_pre, dir_post)

					if miter_pt is not None:
						# Check miter limit: distance from corner to miter point
						# vs half the nib width (approximate stroke radius)
						nib_corner = nibs[(i + 1) % len(nibs)]
						half_width = abs(nib_corner.tangent_point(dir_pre))
						miter_len = abs(miter_pt - node_pos)

						if half_width > 1e-6 and miter_len / half_width > miter_limit:
							# Exceeds limit — fall back to bevel
							_emit(qb, 'on')
						else:
							_emit(miter_pt, 'on')
					else:
						# Parallel — fall back to bevel
						_emit(qb, 'on')

					_emit(qa_next, 'on')

				elif join == JOIN_ROUND:
					# Geometric arc from qb to qa_next around skeleton corner
					_emit(qb, 'on')
					_emit_round_join(qb, qa_next, node_pos)
					_emit(qa_next, 'on')

				else:
					# Bevel: qb and qa_next as on-curves (straight line)
					_emit(qb, 'on')
					_emit(qa_next, 'on')
			else:
				_emit(qb, 'on')
		else:
			_emit(qb, 'on')

	return result, types


# - Cut (butt cap) computation ----------
def compute_cut(nib, direction, angle, center, relative=False):
	'''Compute a razor cut across the stroke at a given angle. Still in active use.
	Based on MetaType1 cut macro.

	Projects the nib along the path direction onto a line at the 
	given angle. Returns the two endpoints of the cut.

	Args:
		nib       : Nib — pen at this node
		direction : complex — path direction at this node
		angle     : float — cut angle in degrees
		center    : complex — node position
		relative  : bool — if True, angle is relative to path direction

	Returns:
		(complex, complex) — two endpoints of the cut line
	'''
	if relative:
		base_angle = cmath.phase(direction)
		cut_dir = cmath.exp(1j * (base_angle + math.radians(angle)))
	else:
		cut_dir = cmath.exp(1j * math.radians(angle))

	# Find tangent points on nib for the path direction and its opposite
	tp_fwd = nib.tangent_point(direction) + center
	tp_bwd = nib.tangent_point(-direction) + center

	# Project tangent points onto the cut line through center
	if abs(cut_dir) < 1e-10:
		return (tp_fwd, tp_bwd)

	# Project: find point on cut line closest to each tangent point
	def project_onto_line(point, line_dir, line_origin):
		v = point - line_origin
		t = (v.real * line_dir.real + v.imag * line_dir.imag) / abs(line_dir)**2
		return line_origin + t * line_dir

	p0 = project_onto_line(tp_fwd, cut_dir, center)
	p1 = project_onto_line(tp_bwd, cut_dir, center)

	return (p0, p1)


# - Tip (miter) computation -------------
def compute_tip(edge_pre, edge_post, pre_elongation=0.5, post_elongation=0.5):
	'''DEPRECATED — kept for compatibility. Use _compute_miter() instead,
	which solves line-line intersection analytically.

	Original: compute miter join by brute-force 21x21 sampling of two
	extrapolated edge segments. Based on MetaType1 tip macro.

	Args:
		edge_pre       : tuple of 4 complex — preceding edge segment
		edge_post      : tuple of 4 complex — following edge segment
		pre_elongation : float — how far to extend pre-edge (0..1, fraction of segment)
		post_elongation: float — how far to extend post-edge

	Returns:
		list of complex — miter path points, or straight line if no intersection
	'''
	# Extrapolate pre-edge forward
	if pre_elongation > 0:
		t1_pre = 0.
		t2_pre = 1. / (1. + pre_elongation)
		ext_pre = extrapolate_segment(*edge_pre, t1_pre, t2_pre)
	else:
		ext_pre = edge_pre

	# Extrapolate post-edge backward
	if post_elongation > 0:
		t1_post = post_elongation / (1. + post_elongation)
		t2_post = 1.
		ext_post = extrapolate_segment(*edge_post, t1_post, t2_post)
	else:
		ext_post = edge_post

	# Find intersection of the two extrapolated segments
	# Sample both at many points and find closest approach
	best_dist = float('inf')
	best_pa = ext_pre[3]   # Default: end of pre
	best_pb = ext_post[0]  # Default: start of post

	for i in range(21):
		ta = i / 20.
		pa = _bezier_at(*ext_pre, ta)

		for j in range(21):
			tb = j / 20.
			pb = _bezier_at(*ext_post, tb)

			dist = abs(pa - pb)
			if dist < best_dist:
				best_dist = dist
				best_pa = pa
				best_pb = pb

	if best_dist < 1.:
		# Found intersection — use midpoint
		intersection = (best_pa + best_pb) * 0.5
		return [intersection]
	else:
		# No intersection — bevel (straight line)
		return [ext_pre[3], ext_post[0]]


# - Cap primitives ----------------------
# Public top-level primitives for building path caps from two stem-corner
# anchor points and their stem tangents. Used by both the stroke envelope
# expander (PenStroke._compute_cap) and panel-level cap actions
# (NodeActions.cap_butt / cap_round / cap_angular / cap_rebuild).
#
# Convention:
#   point_a, point_b : complex — the two on-curve corners where the cap
#                      meets the stems
#   tangent_a        : complex — unit tangent at A of the stem segment that
#                      TERMINATES at A, in forward direction. Points outward
#                      (into the cap region, away from the glyph body).
#   tangent_b        : complex — unit tangent at B of the stem segment that
#                      ORIGINATES at B, in forward direction. Points inward
#                      (out of the cap region, into the glyph body).
#
# For a perpendicular cap on a straight stem, tangent_a == -tangent_b. For
# italic / skewed stems, both point along the stem axis but the chord A-B
# is not perpendicular to that axis.

def compute_cap_outward_direction(tangent_a, tangent_b, point_a=None, point_b=None):
	'''Compute the unit stem axis pointing outward (away from the glyph body)
	from the two stem-corner tangents.

	The construction averages the two outward-pointing tangents:
	tangent_a already points outward; tangent_b points inward, so we negate
	it before averaging.

	Falls back to the perpendicular of chord A-B when tangents are degenerate
	(near-zero or near-parallel-but-opposite-sign), which guarantees a usable
	direction for any stem geometry.

	Args:
		tangent_a : complex — see module docstring
		tangent_b : complex — see module docstring
		point_a   : complex or None — A, used only for fallback
		point_b   : complex or None — B, used only for fallback

	Returns:
		complex — unit vector along the stem axis, outward
	'''
	# Negate B's tangent so both vectors point outward, then average
	t_a = tangent_a
	t_b_out = -tangent_b

	la = abs(t_a)
	lb = abs(t_b_out)

	if la > 1e-10:
		t_a = t_a / la
	if lb > 1e-10:
		t_b_out = t_b_out / lb

	avg = t_a + t_b_out
	mag = abs(avg)

	if mag > 1e-6:
		return avg / mag

	# Degenerate (tangents cancel or are zero): use chord perpendicular
	if point_a is not None and point_b is not None:
		chord = point_b - point_a
		cl = abs(chord)
		if cl > 1e-10:
			# Perpendicular; sign chosen toward whichever tangent we have
			perp = chord / cl * 1j
			ref = t_a if la > 1e-10 else (-t_b_out if lb > 1e-10 else perp)
			# Flip if the perpendicular points opposite to the available reference
			if (perp.real * ref.real + perp.imag * ref.imag) < 0:
				perp = -perp
			return perp

	# Last-resort: arbitrary unit vector
	return complex(0, 1)


def compute_cap_round_arc(point_a, point_b, outward_direction, curvature=1.0):
	'''Italic-aware circular cap as two cubic Bezier arcs.

	Constructs a circle of radius |AB|/2 centred at midpoint(A, B). Tip of
	the cap is the point on that circle in the outward stem direction —
	NOT the perpendicular bisector of AB. For a perpendicular cap (outward
	direction perpendicular to the chord), the tip lies on the perpendicular
	bisector and the two arcs are equal 90° quarters. For italic / skewed
	caps, the tip stays on the stem axis and the two arcs are unequal but
	still sum to 180° (since A and B are diametrically opposed on the
	circle).

	Each half-arc is approximated by a single cubic Bezier with handle
	length L = (4/3) * tan(theta/4) * radius * curvature, where theta is
	the arc's subtended angle.

	Args:
		point_a           : complex — first corner
		point_b           : complex — second corner
		outward_direction : complex — unit vector along stem axis, outward
		                    (typically from compute_cap_outward_direction)
		curvature         : float — handle-length scale (1.0 = true circle)

	Returns:
		tuple of 5 complex — (h_a_out, h_tip_in, p_tip, h_tip_out, h_b_in)
		These are the INTERIOR points of the cap. Caller emits point_a
		first and point_b last.

		Returns None if A and B coincide.
	'''
	chord = point_b - point_a
	chord_len = abs(chord)

	if chord_len < 1e-10:
		return None

	r = chord_len / 2.0
	mid = (point_a + point_b) / 2.0

	# Normalise outward direction
	od_mag = abs(outward_direction)
	if od_mag < 1e-10:
		# Degenerate — fall back to chord perpendicular (arbitrary side)
		d = chord / chord_len * 1j
	else:
		d = outward_direction / od_mag

	# Tip lies on the circle in the outward direction
	p_tip = mid + r * d

	# Radii from centre to each on-curve point
	r_a = point_a - mid       # length r
	r_tip = p_tip - mid       # length r
	r_b = point_b - mid       # length r, == -r_a

	# Determine arc rotation sense: CCW (1j) if cross(r_a, r_tip) > 0
	cross = r_a.real * r_tip.imag - r_a.imag * r_tip.real
	rot = 1j if cross > 0 else -1j

	# Half-arc angles. r_a and r_tip are both length r, so:
	dot_a = (r_a.real * r_tip.real + r_a.imag * r_tip.imag) / (r * r)
	dot_a = max(-1.0, min(1.0, dot_a))
	theta_a = math.acos(dot_a)
	theta_b = math.pi - theta_a   # because A and B are diametrically opposite

	# Kappa per half-arc (4/3 * tan(theta/4))
	kappa_a = 4.0 / 3.0 * math.tan(theta_a / 4.0) * curvature
	kappa_b = 4.0 / 3.0 * math.tan(theta_b / 4.0) * curvature

	# Tangent at each on-curve = radius rotated 90° in arc direction.
	# Handles point ALONG the arc (forward at start, backward at end).
	h_a_out  = point_a + kappa_a * (r_a   * rot)
	h_tip_in = p_tip   - kappa_a * (r_tip * rot)
	h_tip_out= p_tip   + kappa_b * (r_tip * rot)
	h_b_in   = point_b - kappa_b * (r_b   * rot)

	return (h_a_out, h_tip_in, p_tip, h_tip_out, h_b_in)


def compute_cap_angular_tip(point_a, point_b, tangent_a, tangent_b):
	'''Pointed (miter) cap tip — analytical line-line intersection.

	Casts a ray from A along tangent_a (which already points outward) and
	a ray from B along -tangent_b (negated so it points outward), and
	returns their intersection. This is the same math as a stroke miter
	join, exposed at the cap level.

	Args:
		point_a   : complex
		point_b   : complex
		tangent_a : complex — outward-pointing stem tangent at A
		tangent_b : complex — inward-pointing stem tangent at B (will be negated)

	Returns:
		complex — intersection point, or None if tangents are parallel
		(no well-defined tip).
	'''
	d1 = tangent_a
	d2 = -tangent_b
	dx = point_b - point_a

	denom = d1.real * d2.imag - d1.imag * d2.real

	if abs(denom) < 1e-10:
		return None  # Parallel — no intersection

	t = (dx.real * d2.imag - dx.imag * d2.real) / denom
	return point_a + t * d1


# - Main pen_stroke function ------------
class PenStroke(object):
	'''Pen stroke envelope expander.

	Takes a skeleton path (as HobbySpline segments or CubicBezier/Line list),
	a default nib, and per-node options. Produces the expanded stroke outline.

	Equivalent to MetaType1 pen_stroke macro.

	Usage:
		nib = Nib.elliptic(50, 50, 0)
		stroke = PenStroke(segments, nib)
		stroke.set_option(0, NodeStrokeOpts.cut(90, relative=True))
		result = stroke.expand()
	'''

	def __init__(self, segments, default_nib, **kwargs):
		'''
		Args:
			segments     : list — CubicBezier/Line objects or (z0,z1,z2,z3) complex tuples
			default_nib  : Nib — default pen shape
			closed       : bool — whether path is closed
			method       : int — stroke method (0, 1, or 2)
			cap          : str — cap type for open paths ('round' or 'butt')
			join         : str — default join type at corners ('round', 'miter', 'bevel')
			miter_limit  : float — miter length limit as ratio of half stroke width.
			               When exceeded, miter falls back to bevel. Default 4.0.
		'''
		self.default_nib = default_nib
		self.closed = kwargs.pop('closed', False)
		self.method = kwargs.pop('method', METHOD_DIRECTION)
		self.cap = kwargs.pop('cap', CAP_ROUND)
		self.join = kwargs.pop('join', JOIN_ROUND)
		self.miter_limit = kwargs.pop('miter_limit', MITER_LIMIT_DEFAULT)

		# Convert segments to complex tuples
		self._segments = []

		for seg in segments:
			if isinstance(seg, (tuple, list)) and len(seg) == 4:
				# Already complex tuples
				self._segments.append(tuple(seg))
			elif isinstance(seg, (CubicBezier, Line)):
				self._segments.append(_segment_to_complex(seg))
			else:
				raise TypeError('Segment must be CubicBezier, Line, or 4-tuple of complex')

		# Per-node options (indexed by node number)
		self._node_opts = {}

		# Number of nodes
		n_seg = len(self._segments)
		self._n_nodes = n_seg if self.closed else n_seg + 1

	@property
	def node_count(self):
		return self._n_nodes

	def set_option(self, node_index, opts):
		'''Set stroke options at a specific node.

		Args:
			node_index : int — node index (0-based), or -1 for last
			opts       : NodeStrokeOpts
		'''
		if node_index < 0:
			node_index = self._n_nodes + node_index
		self._node_opts[node_index] = opts

	def set_nib(self, nib, *node_indices):
		'''Set custom nib at specified nodes.
		Shorthand for set_option with NodeStrokeOpts.nib.
		'''
		for idx in node_indices:
			self.set_option(idx, NodeStrokeOpts.nib(nib))

	def set_cut(self, angle, *node_indices, **kwargs):
		'''Set butt cut at specified nodes.'''
		relative = kwargs.get('relative', False)
		for idx in node_indices:
			self.set_option(idx, NodeStrokeOpts.cut(angle, relative))

	def set_tip(self, *node_indices, **kwargs):
		'''Set miter join at specified nodes.'''
		pre = kwargs.get('pre', 0.5)
		post = kwargs.get('post', 0.5)
		for idx in node_indices:
			self.set_option(idx, NodeStrokeOpts.miter(pre, post))

	# - Nib resolution -------------------------
	def _get_nib(self, node_index, side='right'):
		'''Resolve the nib to use at a given node for a given side.

		Args:
			node_index : int
			side       : 'left' or 'right'

		Returns:
			Nib
		'''
		opts = self._node_opts.get(node_index)

		if opts is not None:
			if opts.has_cut:
				# Cut: compute razor nib from projection
				direction = self._direction_at_node(node_index)
				angle = opts.cut_angle

				if opts.cut_relative and abs(direction) > 1e-10:
					angle += math.degrees(cmath.phase(direction))

				# Project default nib onto cut line
				width = self._nib_projected_width(node_index, angle)
				return Nib.razor(width, angle)

			if side == 'left' and opts.nib_left is not None:
				return opts.nib_left
			if side == 'right' and opts.nib_right is not None:
				return opts.nib_right

		return self.default_nib

	def _direction_at_node(self, node_index):
		'''Get path direction at a given node'''
		n_seg = len(self._segments)

		if node_index < n_seg:
			z0, z1, z2, z3 = self._segments[node_index]
			return robust_direction(z0, z1, z2, z3)
		elif node_index > 0:
			z0, z1, z2, z3 = self._segments[node_index - 1]
			return robust_direction_end(z0, z1, z2, z3)
		else:
			return complex(1, 0)

	def _nib_projected_width(self, node_index, angle):
		'''Get the width of the default nib projected onto a line at given angle'''
		direction = self._direction_at_node(node_index)
		nib = self.default_nib

		tp_fwd = nib.tangent_point(direction)
		tp_bwd = nib.tangent_point(-direction)

		# Project onto the angle direction
		cut_dir = cmath.exp(1j * math.radians(angle))

		def project_scalar(point, direction):
			return (point.real * direction.real + point.imag * direction.imag) / abs(direction)

		w1 = project_scalar(tp_fwd, cut_dir)
		w2 = project_scalar(tp_bwd, cut_dir)

		return abs(w1 - w2)

	# - Main expansion --------------------------
	def expand(self):
		'''Expand the stroke and return StrokeResult.

		This is the main operation — equivalent to MetaType1 pen_stroke.
		Computes right and left edges of the envelope, then joins them 
		with appropriate caps or corner joins.

		Returns:
			StrokeResult
		'''
		result = StrokeResult(closed=self.closed)
		n_seg = len(self._segments)

		if n_seg == 0:
			return result

		# Build nib lists for right and left edges
		nibs_right = [self._get_nib(i, 'right') for i in range(self._n_nodes)]
		nibs_left = [self._get_nib(i, 'left') for i in range(self._n_nodes)]

		# Collect ignore_dirs sets
		ignore_r = set()
		ignore_l = set()

		for idx, opts in self._node_opts.items():
			if opts.ignore_dir_r:
				ignore_r.add(idx)
			if opts.ignore_dir_l:
				ignore_l.add(idx)

		# Compute right edge (following path direction)
		result.right, result.right_types = pen_stroke_edge(
			self._segments, nibs_right, self.method,
			ignore_r, self.closed, self.join, self.miter_limit
		)

		# Compute left edge (reverse path direction)
		# Reverse each segment: swap z0↔z3, z1↔z2
		reversed_segs = [(z3, z2, z1, z0) for z0, z1, z2, z3 in reversed(self._segments)]
		reversed_nibs = list(reversed(nibs_left))

		result.left, result.left_types = pen_stroke_edge(
			reversed_segs, reversed_nibs, self.method,
			ignore_l, self.closed, self.join, self.miter_limit
		)

		# Caps for open paths
		if not self.closed:
			# Begin cap: connects left edge end to right edge start
			result.begin, result.begin_types = self._compute_cap(
				0,  # start node
				result.left[-1] if result.left else complex(0, 0),
				result.right[0] if result.right else complex(0, 0),
				forward=False
			)

			# End cap: connects right edge end to left edge start
			result.end, result.end_types = self._compute_cap(
				self._n_nodes - 1,  # end node
				result.right[-1] if result.right else complex(0, 0),
				result.left[0] if result.left else complex(0, 0),
				forward=True
			)

		return result

	def _compute_cap(self, node_index, from_point, to_point, forward=True):
		'''Compute a path cap at an open path endpoint.

		Returns only INTERIOR points — the boundary on-curves (from_point
		and to_point) are already emitted by the edge lists. For a closed
		contour the adjacent on-curves connect with an implicit line (butt)
		or through the returned BCPs/mid-points (round).

		Args:
			node_index : int
			from_point : complex — end of outgoing edge (already in outline)
			to_point   : complex — start of return edge (already in outline)
			forward    : bool — True for end cap, False for begin cap

		Returns:
			tuple of (list of complex, list of str) — interior cap points and node types
		'''
		# Per-node cut overrides everything — butt (straight line, no interior)
		opts = self._node_opts.get(node_index)

		if opts is not None and opts.has_cut:
			return [], []

		# Butt cap: straight line — no interior points needed
		if self.cap == CAP_BUTT:
			return [], []

		# Round cap: semicircular arc anchored to actual edge endpoints
		direction = self._direction_at_node(node_index)

		if not forward:
			direction = -direction

		# Midpoint of the arc — on the nib outline in the outward direction
		# (the direction the cap bulges: forward past end, backward past start)
		nib = self._get_nib(node_index, 'right')
		node_pos = self._segments[min(node_index, len(self._segments) - 1)][0 if node_index == 0 else 3]

		shifted = nib.shifted(node_pos)
		# Support point (farthest in outward direction) = tangent_point
		# rotated -90°. tangent_point(d) gives where tangent ∥ d, but we
		# need where the NORMAL points in direction d (= farthest point).
		p_mid = shifted.tangent_point(direction * (-1j))

		# Approximate semicircle with two quarter-circle cubic arcs:
		#   from_point → p_mid → to_point
		#
		# For a quarter arc, BCPs lie along the tangent at each on-curve
		# point, at a distance of kappa * radius from that point.
		# Tangent at a point on a circle is perpendicular to the radius.
		# Kappa for quarter-circle: 4/3 * tan(π/4) ≈ 0.5522847
		kappa = 0.5522847498

		# Radii from center to each on-curve point
		r_from = from_point - node_pos
		r_mid = p_mid - node_pos
		r_to = to_point - node_pos

		# Tangent at each point = radius rotated 90° in arc direction.
		# Arc goes from_point → p_mid → to_point (outward semicircle).
		# Determine arc rotation sense from cross product.
		cross = r_from.real * r_mid.imag - r_from.imag * r_mid.real
		rot = 1j if cross > 0 else -1j

		# First quarter: from_point → p_mid
		bcp1 = from_point + kappa * (r_from * rot)
		bcp2 = p_mid - kappa * (r_mid * rot)

		# Second quarter: p_mid → to_point
		bcp3 = p_mid + kappa * (r_mid * rot)
		bcp4 = to_point - kappa * (r_to * rot)

		# Return interior only: bcp, bcp, mid_on, bcp, bcp
		# (from_point and to_point are already in the edges)
		return (
			[bcp1, bcp2, p_mid, bcp3, bcp4],
			['curve', 'curve', 'on', 'curve', 'curve']
		)

	# - Convenience API -------------------------
	@classmethod
	def from_hobby_spline(cls, hobby_spline, nib, **kwargs):
		'''Create PenStroke from a HobbySpline object.

		Args:
			hobby_spline : HobbySpline
			nib          : Nib — default pen
			**kwargs     : passed to PenStroke constructor
		'''
		return cls(
			hobby_spline.segments,
			nib,
			closed=hobby_spline.closed,
			**kwargs
		)


# =====================================================================
# METAFONT-inspired extensions (v0.3.0)
# =====================================================================
# The following classes and functions implement concepts from Knuth's
# METAFONT and Hobby's MetaPost that go beyond the original MetaType1
# control-polygon-offsetting approach:
#
# 1. NibPolygon — convex polygon pen (METAFONT's native pen type)
# 2. Polygon envelope — exact translated Béziers + pen edge connectors
# 3. PenPos / VarStroke — variable-width strokes (MetaPost penstroke)
# 4. turning_number — winding validation (METAFONT turningcheck)
# 5. find_offset_cusps — cusp detection in offset curves
# =====================================================================

# - Constants (METAFONT extensions) -----
_CUSP_SAMPLES = 64          # Sampling density for cusp detection
_POLY_CIRCLE_VERTS = 12     # Default polygon vertices for circle approximation

# - NibPolygon --------------------------
class NibPolygon(object):
	'''Convex polygon pen — METAFONT's native pen representation.

	In METAFONT, every pen (including pencircle) is ultimately a convex
	polygon. The key advantage: offsetting by a polygon vertex is an
	exact translation of the Bézier — no approximation error.

	The polygon is stored as CCW-ordered vertices. Each edge has a
	precomputed direction (complex unit vector) used for critical angle
	detection.

	Attributes:
		vertices   : list of complex — CCW polygon vertices
		edges      : list of complex — unit direction of each edge (v[i] → v[i+1])
		edge_angles: list of float  — angle in radians of each edge direction
	'''

	def __init__(self, vertices):
		'''Create from a list of complex vertices (must be convex, CCW).

		Args:
			vertices : list of complex — at least 2 vertices, convex hull, CCW order
		'''
		if len(vertices) < 2:
			raise ValueError('NibPolygon needs at least 2 vertices')

		self.vertices = list(vertices)
		n = len(self.vertices)

		# Precompute edge directions and angles
		self.edges = []
		self.edge_angles = []

		for i in range(n):
			edge = self.vertices[(i + 1) % n] - self.vertices[i]

			if abs(edge) < 1e-12:
				# Degenerate edge — use previous direction or default
				if self.edges:
					self.edges.append(self.edges[-1])
					self.edge_angles.append(self.edge_angles[-1])
				else:
					self.edges.append(complex(1, 0))
					self.edge_angles.append(0.0)
			else:
				d = edge / abs(edge)
				self.edges.append(d)
				self.edge_angles.append(cmath.phase(d))

	def __repr__(self):
		return '<NibPolygon vertices={}>'.format(len(self.vertices))

	def __len__(self):
		return len(self.vertices)

	@property
	def n(self):
		'''Number of vertices'''
		return len(self.vertices)

	def shifted(self, z):
		'''Return copy shifted by complex z'''
		return NibPolygon([v + z for v in self.vertices])

	def scaled(self, factor):
		'''Return copy scaled uniformly'''
		return NibPolygon([v * factor for v in self.vertices])

	def rotated(self, angle_deg):
		'''Return copy rotated by angle in degrees'''
		r = cmath.exp(1j * math.radians(angle_deg))
		return NibPolygon([v * r for v in self.vertices])

	def support_vertex(self, direction):
		'''Find the vertex farthest in the given direction (support point).

		This is the polygon equivalent of Nib.tangent_point(d * (-1j)).
		Returns the vertex index and point.

		Args:
			direction : complex — query direction

		Returns:
			(int, complex) — (vertex_index, vertex_point)
		'''
		if abs(direction) < 1e-10:
			return 0, self.vertices[0]

		d = direction / abs(direction)
		best_i = 0
		best_dot = -1e30

		for i, v in enumerate(self.vertices):
			dot = v.real * d.real + v.imag * d.imag

			if dot > best_dot:
				best_dot = dot
				best_i = i

		return best_i, self.vertices[best_i]

	def active_vertex(self, direction):
		'''Find the active vertex for a given path direction.

		The active vertex on the RIGHT side of the path is the one whose
		two adjacent edges "straddle" the path direction. Specifically,
		vertex i is active when the path direction falls in the angular
		range between edge[i-1] and edge[i] (measuring CCW).

		This is METAFONT's offset_prep core logic.

		Args:
			direction : complex — path tangent direction

		Returns:
			int — index of the active vertex for the right-side envelope
		'''
		if abs(direction) < 1e-10:
			return 0

		d_angle = cmath.phase(direction)
		n = self.n

		for i in range(n):
			# Edge before vertex i
			prev_edge_angle = self.edge_angles[(i - 1) % n]
			# Edge after vertex i
			curr_edge_angle = self.edge_angles[i]

			# Check if d_angle is between prev_edge_angle and curr_edge_angle
			# (in the CCW angular sense)
			if _angle_between_ccw(d_angle, prev_edge_angle, curr_edge_angle):
				return i

		# Fallback: closest edge direction
		return self._closest_vertex(d_angle)

	def _closest_vertex(self, d_angle):
		'''Fallback: find vertex whose incoming edge direction is closest.'''
		best_i = 0
		best_diff = 1e30

		for i in range(self.n):
			diff = abs(_wrap_angle(d_angle - self.edge_angles[i]))

			if diff < best_diff:
				best_diff = diff
				best_i = (i + 1) % self.n

		return best_i

	# - Factory methods -------------------------
	@classmethod
	def regular(cls, n_sides, radius):
		'''Create a regular polygon with n sides inscribed in a circle.

		Args:
			n_sides : int — number of sides (>=3)
			radius  : float — circumscribed circle radius
		'''
		if n_sides < 3:
			raise ValueError('Regular polygon needs at least 3 sides')

		verts = []

		for i in range(n_sides):
			angle = 2.0 * math.pi * i / n_sides + math.pi / 2  # Start from top
			verts.append(complex(radius * math.cos(angle), radius * math.sin(angle)))

		return cls(verts)

	@classmethod
	def from_circle(cls, diameter, n_vertices=_POLY_CIRCLE_VERTS):
		'''Approximate a circular pen as a regular polygon.

		METAFONT's pencircle: a circle approximated by a polygon whose
		vertex count is tuned for good results. Default 12 vertices
		(dodecagon) gives max error of ~3.4% of radius — imperceptible
		in font work.

		Args:
			diameter   : float — circle diameter
			n_vertices : int — number of polygon vertices (default 12)
		'''
		return cls.regular(n_vertices, diameter / 2.0)

	@classmethod
	def from_ellipse(cls, x_diam, y_diam, angle=0.0, n_vertices=_POLY_CIRCLE_VERTS):
		'''Approximate an elliptic pen as a polygon.

		Args:
			x_diam     : float — horizontal diameter
			y_diam     : float — vertical diameter
			angle      : float — rotation in degrees
			n_vertices : int — vertex count
		'''
		rx, ry = x_diam / 2.0, y_diam / 2.0
		r = cmath.exp(1j * math.radians(angle))
		verts = []

		for i in range(n_vertices):
			a = 2.0 * math.pi * i / n_vertices + math.pi / 2
			p = complex(rx * math.cos(a), ry * math.sin(a))
			verts.append(p * r)

		return cls(verts)

	@classmethod
	def from_nib(cls, nib, n_vertices=_POLY_CIRCLE_VERTS):
		'''Convert an existing Nib (cubic Bézier representation) to polygon
		by sampling its outline.

		Args:
			nib        : Nib — elliptic or razor nib
			n_vertices : int — how many sample points
		'''
		if nib.is_razor:
			return cls(list(nib.path))

		# Sample the nib outline at n_vertices evenly-spaced angles
		verts = []

		for i in range(n_vertices):
			angle = 2.0 * math.pi * i / n_vertices
			d = complex(math.cos(angle), math.sin(angle))
			# tangent_point(d * (-1j)) gives the support point in direction d
			p = nib.tangent_point(d * (-1j))
			verts.append(p)

		# Ensure CCW order (should already be, but verify)
		if _polygon_signed_area(verts) < 0:
			verts.reverse()

		return cls(verts)

	@classmethod
	def rectangle(cls, width, height, angle=0.0):
		'''Create a rectangular (calligraphic) pen.

		Args:
			width  : float — pen width
			height : float — pen height
			angle  : float — rotation in degrees
		'''
		hw, hh = width / 2.0, height / 2.0
		r = cmath.exp(1j * math.radians(angle))
		verts = [
			complex(-hw, -hh) * r,
			complex(hw, -hh) * r,
			complex(hw, hh) * r,
			complex(-hw, hh) * r,
		]

		# Ensure CCW
		if _polygon_signed_area(verts) < 0:
			verts.reverse()

		return cls(verts)


# - Angle utilities ---------------------
def _wrap_angle(a):
	'''Wrap angle to (-π, π]'''
	while a > math.pi:
		a -= 2.0 * math.pi
	while a <= -math.pi:
		a += 2.0 * math.pi
	return a


def _angle_between_ccw(angle, start, end):
	'''Check if angle lies in the CCW arc from start to end.

	All angles in radians. Returns True if going CCW from start you
	reach angle before reaching end.
	'''
	# Normalize all to [0, 2π)
	def norm(a):
		a = a % (2.0 * math.pi)
		return a if a >= 0 else a + 2.0 * math.pi

	a = norm(angle)
	s = norm(start)
	e = norm(end)

	if s <= e:
		# Normal arc: s ≤ a ≤ e
		return s <= a <= e
	else:
		# Arc wraps around 0: a >= s or a <= e
		return a >= s or a <= e


def _polygon_signed_area(verts):
	'''Signed area of polygon. Positive = CCW, negative = CW.'''
	n = len(verts)
	area = 0.0

	for i in range(n):
		v0 = verts[i]
		v1 = verts[(i + 1) % n]
		area += v0.real * v1.imag - v1.real * v0.imag

	return area * 0.5


# - Critical angle subdivision ---------
def find_critical_params(z0, z1, z2, z3, nib_poly):
	'''Find parameter values where the path tangent crosses a critical angle.

	A critical angle is the direction of a polygon edge — at these
	angles, the active pen vertex switches. This is METAFONT's
	offset_prep logic.

	The tangent of cubic Bézier (z0,z1,z2,z3) is quadratic:
	  T(t) = A·t² + B·t + C
	For each edge direction d_k of the polygon, we solve:
	  T(t) × d_k = 0  (cross product = 0, meaning T ∥ d_k)
	This is a quadratic in t — same solver as Nib.tangent_point.

	Args:
		z0, z1, z2, z3 : complex — skeleton segment
		nib_poly        : NibPolygon

	Returns:
		list of (float, int, int) — sorted list of (t, vertex_before, vertex_after)
		where vertex_before is active for t < t_crit and vertex_after for t > t_crit
	'''
	# Tangent coefficients
	c0 = z1 - z0
	c1 = z2 - z1
	c2 = z3 - z2

	C = 3.0 * c0
	B = 6.0 * (c1 - c0)
	A = 3.0 * (c2 - 2.0 * c1 + c0)

	crits = []

	for k in range(nib_poly.n):
		d = nib_poly.edges[k]
		dx, dy = d.real, d.imag

		# Cross product T(t) × d = 0 → quadratic
		qa = A.real * dy - A.imag * dx
		qb = B.real * dy - B.imag * dx
		qc = C.real * dy - C.imag * dx

		candidates = []

		if abs(qa) < 1e-12:
			if abs(qb) > 1e-12:
				candidates.append(-qc / qb)
		else:
			disc = qb * qb - 4.0 * qa * qc

			if disc >= 0:
				sq = math.sqrt(disc)
				candidates.append((-qb + sq) / (2.0 * qa))
				candidates.append((-qb - sq) / (2.0 * qa))

		for t in candidates:
			if t <= 1e-6 or t >= 1.0 - 1e-6:
				continue  # Only interior splits

			t = max(0.0, min(1.0, t))

			# vertex_before = k+1 (the vertex after this edge),
			# vertex_after = k+1's successor... actually we need to
			# determine which vertex is active on each side.
			# When tangent crosses edge k (direction from v[k] to v[k+1]),
			# the active vertex transitions from v[k+1] to v[k] or vice versa,
			# depending on whether we're looking at right or left side.
			# For the RIGHT side: vertex k+1 is active before the crossing,
			# vertex (k+2) mod n is active after (the next vertex in CCW order).
			v_before = (k + 1) % nib_poly.n
			v_after = (k + 2) % nib_poly.n
			crits.append((t, v_before, v_after))

	# Sort by parameter
	crits.sort(key=lambda x: x[0])

	# Remove duplicates (two edges may give nearly the same t)
	filtered = []
	for c in crits:
		if not filtered or abs(c[0] - filtered[-1][0]) > 1e-6:
			filtered.append(c)

	return filtered


def subdivide_bezier(z0, z1, z2, z3, t):
	'''Subdivide cubic Bézier at parameter t using de Casteljau.

	Returns:
		((a0,a1,a2,a3), (b0,b1,b2,b3)) — left and right sub-segments
	'''
	# Level 1
	p01 = z0 + t * (z1 - z0)
	p12 = z1 + t * (z2 - z1)
	p23 = z2 + t * (z3 - z2)

	# Level 2
	p012 = p01 + t * (p12 - p01)
	p123 = p12 + t * (p23 - p12)

	# Level 3 — split point
	p0123 = p012 + t * (p123 - p012)

	return ((z0, p01, p012, p0123), (p0123, p123, p23, z3))


def subdivide_at_params(z0, z1, z2, z3, params):
	'''Subdivide a cubic Bézier at multiple parameter values.

	Args:
		z0, z1, z2, z3 : complex — segment
		params          : list of float — parameter values in (0,1), SORTED

	Returns:
		list of (z0,z1,z2,z3) — sub-segments
	'''
	if not params:
		return [(z0, z1, z2, z3)]

	result = []
	current = (z0, z1, z2, z3)
	consumed = 0.0  # How much of the original [0,1] range has been consumed

	for t in params:
		# Remap t into the remaining segment's local parameter
		remaining = 1.0 - consumed

		if remaining < 1e-10:
			break

		t_local = (t - consumed) / remaining
		t_local = max(0.0, min(1.0, t_local))

		left, right = subdivide_bezier(*current, t_local)
		result.append(left)
		current = right
		consumed = t

	result.append(current)
	return result


# - Polygon envelope computation --------
def pen_stroke_edge_polygon(segments, nib_poly, is_closed=False, join=JOIN_ROUND, miter_limit=MITER_LIMIT_DEFAULT):
	'''Compute a full edge of the pen envelope using METAFONT's polygon
	decomposition method.

	NOTE: This method produces many nodes due to pen-edge connectors at
	every vertex transition. It is designed for analysis/debugging and
	matches METAFONT's rasterization-oriented approach. For clean outline
	output with minimal nodes, use pen_stroke_edge() with a Bézier Nib,
	or use pen_stroke_edge_hybrid() which uses polygon analysis to guide
	Bézier offsetting.

	Instead of approximating offset curves (Tiller-Hanson), this:
	1. For each Bézier segment, finds critical angles where the active
	   pen vertex switches
	2. Subdivides at those parameters
	3. Translates each sub-segment by its active vertex (EXACT)
	4. Connects transitions with pen edge segments (straight lines)

	Zero approximation error in the curve geometry.

	Args:
		segments    : list of (z0,z1,z2,z3) — skeleton segments
		nib_poly    : NibPolygon — polygon pen
		is_closed   : bool — closed skeleton path
		join        : str — join type at skeleton corners
		miter_limit : float — miter limit ratio

	Returns:
		tuple of (list of complex, list of str) — edge points and node types
	'''
	if not segments:
		return [], []

	n_seg = len(segments)
	result = []
	types = []

	def _emit(point, ntype):
		result.append(point)
		types.append(ntype)

	# Process each skeleton segment
	prev_end_pt = None
	prev_end_dir = None

	for i in range(n_seg):
		z0, z1, z2, z3 = segments[i]

		# Find critical parameter values for this segment
		crits = find_critical_params(z0, z1, z2, z3, nib_poly)
		params = [c[0] for c in crits]

		# Subdivide the skeleton segment
		sub_segs = subdivide_at_params(z0, z1, z2, z3, params)

		# Determine active vertex for each sub-segment
		# Start vertex: determined by direction at segment start
		dir_start = robust_direction(z0, z1, z2, z3)
		start_vi = nib_poly.active_vertex(dir_start)

		# Build list: [(sub_seg, active_vertex_index), ...]
		active_vertices = [start_vi]

		for ci, (t, v_before, v_after) in enumerate(crits):
			# After crossing critical angle, vertex switches
			# We use the tangent direction just after the split to confirm
			if ci + 1 < len(sub_segs):
				sub = sub_segs[ci + 1]
				d_after = robust_direction(*sub)
				active_vertices.append(nib_poly.active_vertex(d_after))

		# Emit offset sub-segments with pen-edge connectors
		for si, sub in enumerate(sub_segs):
			vi = active_vertices[min(si, len(active_vertices) - 1)]
			offset = nib_poly.vertices[vi]

			# Translate sub-segment by offset (EXACT — the key insight)
			qa = sub[0] + offset
			q1 = sub[1] + offset
			q2 = sub[2] + offset
			qb = sub[3] + offset

			if si == 0 and i == 0:
				# Very first point of the whole edge
				_emit(qa, 'on')
			elif si == 0:
				# First sub-segment of a new skeleton segment →
				# corner join from previous segment's endpoint.
				# _join_polygon emits from_pt, join interior, and to_pt,
				# so we do NOT emit qa here (it's the to_pt of the join).
				if prev_end_pt is not None:
					gap = abs(prev_end_pt - qa)

					if gap > 0.5:
						_join_polygon(result, types, prev_end_pt, qa,
									  segments[i - 1][3], prev_end_dir,
									  robust_direction(*segments[i]),
									  nib_poly, join, miter_limit, _emit)
					else:
						# Coincident — just emit once
						_emit(qa, 'on')
				else:
					_emit(qa, 'on')
			else:
				# Pen-edge connector between sub-segments (vertex transition)
				# Emit prev endpoint, then new start (straight pen-edge line)
				_emit(prev_end_pt, 'on')

				if abs(prev_end_pt - qa) > 0.5:
					_emit(qa, 'on')

			# Emit curve BCPs (skip for lines)
			if not _is_line(qa, q1, q2, qb):
				_emit(q1, 'curve')
				_emit(q2, 'curve')

			prev_end_pt = qb
			prev_end_dir = robust_direction_end(*sub)

		# Emit endpoint only for the LAST skeleton segment (open path)
		# or not at all for closed paths. Intermediate segment endpoints
		# are handled by the join logic of the next segment's si==0 branch.
		if i == n_seg - 1 and not is_closed:
			_emit(prev_end_pt, 'on')

	# Close: join last segment back to first
	if is_closed and n_seg > 0 and result:
		first_pt = result[0]
		gap = abs(prev_end_pt - first_pt)

		if gap > 0.5:
			_join_polygon(result, types, prev_end_pt, first_pt,
						  segments[-1][3], prev_end_dir,
						  robust_direction(*segments[0]),
						  nib_poly, join, miter_limit, _emit)
		else:
			_emit(prev_end_pt, 'on')

	return result, types


def _join_polygon(result, types, from_pt, to_pt, corner_pos,
				  dir_pre, dir_post, nib_poly, join, miter_limit, _emit):
	'''Emit a join between two edge segments for polygon envelope.

	Args:
		from_pt, to_pt : complex — edge endpoints to join
		corner_pos     : complex — skeleton corner position
		dir_pre        : complex — direction arriving at corner
		dir_post       : complex — direction leaving corner
		nib_poly       : NibPolygon
		join           : str — join type
		miter_limit    : float
		_emit          : callable(point, type)
	'''
	if join == JOIN_MITER:
		# Analytical line-line intersection
		d1 = dir_pre
		d2 = -dir_post
		dx = to_pt - from_pt
		denom = d1.real * d2.imag - d1.imag * d2.real

		if abs(denom) > 1e-10:
			t = (dx.real * d2.imag - dx.imag * d2.real) / denom
			miter_pt = from_pt + t * d1

			# Miter limit check
			miter_len = abs(miter_pt - corner_pos)
			_, sv = nib_poly.support_vertex(dir_pre)
			half_width = abs(sv)

			if half_width > 1e-6 and miter_len / half_width > miter_limit:
				# Exceed limit → bevel
				_emit(from_pt, 'on')
			else:
				_emit(miter_pt, 'on')
		else:
			# Parallel → bevel
			_emit(from_pt, 'on')

		_emit(to_pt, 'on')

	elif join == JOIN_ROUND:
		_emit(from_pt, 'on')
		# Circular arc between endpoints around corner
		_emit_round_join_standalone(result, types, from_pt, to_pt, corner_pos, _emit)
		_emit(to_pt, 'on')

	else:
		# Bevel
		_emit(from_pt, 'on')
		_emit(to_pt, 'on')


def _emit_round_join_standalone(result, types, from_pt, to_pt, center, _emit):
	'''Emit round join interior points (same logic as pen_stroke_edge's version).'''
	r_from = from_pt - center
	r_to = to_pt - center

	dot = r_from.real * r_to.real + r_from.imag * r_to.imag
	r_len = (abs(r_from) + abs(r_to)) * 0.5

	if r_len < 1e-6:
		return

	cos_a = max(-1.0, min(1.0, dot / (abs(r_from) * abs(r_to))))
	full_angle = math.acos(cos_a)

	if full_angle < 0.01:
		return

	mid_dir = r_from / abs(r_from) + r_to / abs(r_to)

	if abs(mid_dir) < 1e-10:
		cross_check = r_from.real * r_to.imag - r_from.imag * r_to.real
		mid_dir = r_from * (1j if cross_check > 0 else -1j)

	r_mid = mid_dir / abs(mid_dir) * r_len
	p_mid = center + r_mid

	cross = r_from.real * r_mid.imag - r_from.imag * r_mid.real
	rot = 1j if cross > 0 else -1j

	half_angle = full_angle * 0.5
	kappa = 4.0 / 3.0 * math.tan(half_angle / 4.0)

	bcp1 = from_pt + kappa * (r_from * rot)
	bcp2 = p_mid - kappa * (r_mid * rot)
	bcp3 = p_mid + kappa * (r_mid * rot)
	bcp4 = to_pt - kappa * (r_to * rot)

	_emit(bcp1, 'curve')
	_emit(bcp2, 'curve')
	_emit(p_mid, 'on')
	_emit(bcp3, 'curve')
	_emit(bcp4, 'curve')


# - Hybrid envelope (Bézier output + polygon-guided subdivision) ----
def pen_stroke_edge_hybrid(segments, nib, method=METHOD_DIRECTION, ignore_dirs=None,
						   is_closed=False, join=JOIN_ROUND, miter_limit=MITER_LIMIT_DEFAULT,
						   cusp_subdivide=True, offset_distance=None):
	'''Compute a full edge using Bézier offsetting with optional cusp-aware
	subdivision.

	This is the recommended method for production outline output. It uses
	the classic Bézier nib for clean curves (minimal nodes) but optionally
	subdivides segments at cusp points before offsetting, preventing the
	self-intersection artifacts that occur when stroke width > curve radius.

	Args:
		segments         : list of (z0,z1,z2,z3)
		nib              : Nib (Bézier nib, not polygon)
		method           : int — stroke method
		ignore_dirs      : set of int or None
		is_closed        : bool
		join             : str — join type
		miter_limit      : float
		cusp_subdivide   : bool — if True, subdivide at cusp points
		offset_distance  : float or None — signed offset distance for cusp
		                   detection (auto-estimated from nib if None)

	Returns:
		tuple of (list of complex, list of str) — edge points and node types
	'''
	if not cusp_subdivide or not segments:
		# Fall back to standard Bézier offsetting
		return pen_stroke_edge(segments, [nib] * (len(segments) + (0 if is_closed else 1)),
							   method, ignore_dirs, is_closed, join, miter_limit)

	# Auto-estimate offset distance from nib
	if offset_distance is None:
		# Use the support point magnitude as half-width
		tp = nib.tangent_point(complex(1, 0) * (-1j))
		offset_distance = abs(tp)

	# Pre-process: subdivide segments at cusp points
	processed_segs = []

	for seg in segments:
		cusps = find_offset_cusps(*seg, -offset_distance)

		if cusps:
			# Subdivide at cusp parameters
			subs = subdivide_at_params(*seg, cusps)
			processed_segs.extend(subs)
		else:
			processed_segs.append(seg)

	# Build nib list for processed segments
	n_nibs = len(processed_segs) + (0 if is_closed else 1)
	nibs = [nib] * n_nibs

	return pen_stroke_edge(processed_segs, nibs, method, ignore_dirs,
						   is_closed, join, miter_limit)


# - Polygon-based PenStroke expander ----
class PolyPenStroke(object):
	'''Stroke expander using METAFONT's polygon decomposition method.

	NOTE: Produces many nodes due to pen-edge connectors. Use for
	analysis/debugging. For production output, use PenStroke (classic)
	or HybridPenStroke (cusp-aware Bézier offsetting).

	Like PenStroke but uses NibPolygon instead of Nib. Produces
	exact translated Bézier offset segments (zero approximation error)
	connected by pen-edge straight lines at vertex transitions.

	Usage:
		nib = NibPolygon.from_circle(80)
		stroke = PolyPenStroke(segments, nib)
		result = stroke.expand()
	'''

	def __init__(self, segments, nib_poly, **kwargs):
		'''
		Args:
			segments    : list — CubicBezier/Line or (z0,z1,z2,z3) tuples
			nib_poly    : NibPolygon — polygon pen
			closed      : bool — closed path
			cap         : str — cap type ('round' or 'butt')
			join        : str — join type ('round', 'miter', 'bevel')
			miter_limit : float — miter limit ratio
		'''
		self.nib_poly = nib_poly
		self.closed = kwargs.pop('closed', False)
		self.cap = kwargs.pop('cap', CAP_ROUND)
		self.join = kwargs.pop('join', JOIN_ROUND)
		self.miter_limit = kwargs.pop('miter_limit', MITER_LIMIT_DEFAULT)

		# Convert segments to complex tuples
		self._segments = []

		for seg in segments:
			if isinstance(seg, (tuple, list)) and len(seg) == 4:
				self._segments.append(tuple(seg))
			elif isinstance(seg, (CubicBezier, Line)):
				self._segments.append(_segment_to_complex(seg))
			else:
				raise TypeError('Segment must be CubicBezier, Line, or 4-tuple of complex')

	def expand(self):
		'''Expand stroke and return StrokeResult.

		Returns:
			StrokeResult
		'''
		result = StrokeResult(closed=self.closed)
		n_seg = len(self._segments)

		if n_seg == 0:
			return result

		# Right edge: polygon envelope following path direction
		result.right, result.right_types = pen_stroke_edge_polygon(
			self._segments, self.nib_poly, self.closed,
			self.join, self.miter_limit
		)

		# Left edge: reversed path with mirrored polygon
		# Mirror polygon: negate all vertices (equivalent to using -nib on reversed path)
		mirrored_nib = NibPolygon([-v for v in self.nib_poly.vertices])
		reversed_segs = [(z3, z2, z1, z0) for z0, z1, z2, z3 in reversed(self._segments)]

		result.left, result.left_types = pen_stroke_edge_polygon(
			reversed_segs, mirrored_nib, self.closed,
			self.join, self.miter_limit
		)

		# Caps for open paths
		if not self.closed:
			result.begin, result.begin_types = self._compute_cap(
				True,  # is_begin
				result.left[-1] if result.left else 0j,
				result.right[0] if result.right else 0j
			)
			result.end, result.end_types = self._compute_cap(
				False,  # is_begin
				result.right[-1] if result.right else 0j,
				result.left[0] if result.left else 0j
			)

		return result

	def _compute_cap(self, is_begin, from_point, to_point):
		'''Compute cap for open path endpoint.

		Returns interior points only (from_point and to_point are in edges).
		'''
		if self.cap == CAP_BUTT:
			return [], []

		# Round cap: semicircular arc
		if is_begin:
			node_pos = self._segments[0][0]
			direction = -robust_direction(*self._segments[0])
		else:
			node_pos = self._segments[-1][3]
			direction = robust_direction_end(*self._segments[-1])

		# Support point as arc midpoint
		_, sv = self.nib_poly.support_vertex(direction)
		p_mid = node_pos + sv

		kappa = 0.5522847498

		r_from = from_point - node_pos
		r_mid = p_mid - node_pos
		r_to = to_point - node_pos

		cross = r_from.real * r_mid.imag - r_from.imag * r_mid.real
		rot = 1j if cross > 0 else -1j

		bcp1 = from_point + kappa * (r_from * rot)
		bcp2 = p_mid - kappa * (r_mid * rot)
		bcp3 = p_mid + kappa * (r_mid * rot)
		bcp4 = to_point - kappa * (r_to * rot)

		return (
			[bcp1, bcp2, p_mid, bcp3, bcp4],
			['curve', 'curve', 'on', 'curve', 'curve']
		)


# - Hybrid PenStroke expander -----------
class HybridPenStroke(PenStroke):
	'''Stroke expander with cusp-aware subdivision.

	Inherits all PenStroke functionality but pre-subdivides segments
	at cusp points (where curvature = 1/offset_distance) before
	offsetting. This prevents inner-offset self-intersections on
	tight curves with large stroke widths.

	For most font work the classic PenStroke is sufficient. Use this
	when you see artifacts on tight curves with thick strokes.

	Usage:
		nib = Nib.circle(80)
		stroke = HybridPenStroke(segments, nib, closed=True)
		result = stroke.expand()
	'''

	def expand(self):
		'''Expand with cusp-aware subdivision.'''
		result = StrokeResult(closed=self.closed)
		n_seg = len(self._segments)

		if n_seg == 0:
			return result

		# Estimate offset distance from default nib
		tp = self.default_nib.tangent_point(complex(1, 0) * (-1j))
		offset_dist = abs(tp)

		# Pre-subdivide segments at cusp points
		processed = []
		seg_map = []  # Maps processed index back to original segment index

		for i, seg in enumerate(self._segments):
			cusps = find_offset_cusps(*seg, -offset_dist)

			if cusps:
				subs = subdivide_at_params(*seg, cusps)
				processed.extend(subs)
				seg_map.extend([i] * len(subs))
			else:
				processed.append(seg)
				seg_map.append(i)

		# Build nib lists for the processed (potentially longer) segment list
		n_proc = len(processed)
		n_nodes_proc = n_proc if self.closed else n_proc + 1

		nibs_right = []
		nibs_left = []

		for j in range(n_nodes_proc):
			# Map back to original node index for nib resolution
			if j < len(seg_map):
				orig_i = seg_map[j]
			else:
				orig_i = self._n_nodes - 1

			nibs_right.append(self._get_nib(min(orig_i, self._n_nodes - 1), 'right'))
			nibs_left.append(self._get_nib(min(orig_i, self._n_nodes - 1), 'left'))

		# Compute edges using processed segments
		ignore_r = set()
		ignore_l = set()

		for idx, opts in self._node_opts.items():
			if opts.ignore_dir_r:
				ignore_r.add(idx)
			if opts.ignore_dir_l:
				ignore_l.add(idx)

		result.right, result.right_types = pen_stroke_edge(
			processed, nibs_right, self.method,
			ignore_r, self.closed, self.join, self.miter_limit
		)

		reversed_segs = [(z3, z2, z1, z0) for z0, z1, z2, z3 in reversed(processed)]
		reversed_nibs = list(reversed(nibs_left))

		result.left, result.left_types = pen_stroke_edge(
			reversed_segs, reversed_nibs, self.method,
			ignore_l, self.closed, self.join, self.miter_limit
		)

		# Caps for open paths (same as PenStroke)
		if not self.closed:
			result.begin, result.begin_types = self._compute_cap(
				0,
				result.left[-1] if result.left else 0j,
				result.right[0] if result.right else 0j,
				forward=False
			)
			result.end, result.end_types = self._compute_cap(
				self._n_nodes - 1,
				result.right[-1] if result.right else 0j,
				result.left[0] if result.left else 0j,
				forward=True
			)

		return result


# - PenPos / Variable-width strokes ----
class PenPos(object):
	'''MetaPost-style pen position at a skeleton point.

	Defines a local cross-section: width and angle at a single point.
	The left and right offset points are computed from:
		z_right = center + (width/2) * e^(i·angle)
		z_left  = center - (width/2) * e^(i·angle)

	This is exactly MetaPost's penpos macro.
	'''

	def __init__(self, width, angle_deg=0.0):
		'''
		Args:
			width     : float — local stroke width
			angle_deg : float — pen angle in degrees (0 = horizontal)
		'''
		self.width = width
		self.angle_deg = angle_deg

	def __repr__(self):
		return '<PenPos w={:.1f} a={:.1f}°>'.format(self.width, self.angle_deg)

	def offsets(self):
		'''Return (right_offset, left_offset) as complex numbers.

		These are relative to center — add to skeleton point to get
		absolute positions.
		'''
		half = self.width / 2.0
		d = cmath.exp(1j * math.radians(self.angle_deg))
		return (half * d, -half * d)

	def right(self, center):
		'''Absolute right-side point'''
		r, _ = self.offsets()
		return center + r

	def left(self, center):
		'''Absolute left-side point'''
		_, l = self.offsets()
		return center + l

	@classmethod
	def uniform(cls, width):
		'''Constant-width penpos (angle follows path tangent automatically).'''
		return cls(width, 0.0)


def var_stroke(skeleton_points, pen_positions, closed=False):
	'''MetaPost-style penstroke: variable-width stroke expansion.

	Given skeleton points and a PenPos at each point, computes
	separate left and right offset point sequences, then interpolates
	curves through each side independently.

	This is MetaPost's:
		fill z0r..z1r..z2r -- reverse(z0l..z1l..z2l) -- cycle;

	For smooth results, the caller should provide skeleton points from
	a smooth curve (e.g., Hobby spline nodes or Bézier on-curve points).

	Args:
		skeleton_points : list of complex — skeleton path points
		pen_positions   : list of PenPos — one per skeleton point
		closed          : bool — closed path

	Returns:
		StrokeResult — with right/left edges as point sequences.
		               Use to_contours() for output.
	'''
	if len(skeleton_points) != len(pen_positions):
		raise ValueError('Need one PenPos per skeleton point (got {} points, {} penpos)'.format(
			len(skeleton_points), len(pen_positions)))

	n = len(skeleton_points)

	if n < 2:
		return StrokeResult(closed=closed)

	# Compute right and left point sequences
	rights = []
	lefts = []

	for i in range(n):
		z = skeleton_points[i]
		pp = pen_positions[i]

		# If angle is 0, orient perpendicular to path tangent
		if pp.angle_deg == 0.0:
			# Estimate tangent direction from neighbors
			if i == 0:
				tangent = skeleton_points[1] - skeleton_points[0]
			elif i == n - 1:
				tangent = skeleton_points[-1] - skeleton_points[-2]
			else:
				tangent = skeleton_points[i + 1] - skeleton_points[i - 1]

			if abs(tangent) > 1e-10:
				# Perpendicular to tangent
				perp = tangent * 1j / abs(tangent)
			else:
				perp = complex(0, 1)

			half = pp.width / 2.0
			rights.append(z + half * perp)
			lefts.append(z - half * perp)
		else:
			rights.append(pp.right(z))
			lefts.append(pp.left(z))

	# Build contour segments from point sequences
	# Use Catmull-Rom → Bézier conversion for smooth interpolation
	right_segs = _catmull_rom_to_bezier(rights, closed)
	left_segs = _catmull_rom_to_bezier(lefts, closed)

	# Assemble result
	result = StrokeResult(closed=closed)

	# Right edge: flatten segments to point + type lists
	for si, seg in enumerate(right_segs):
		if si == 0:
			result.right.append(seg[0])
			result.right_types.append('on')

		if not _is_line(seg[0], seg[1], seg[2], seg[3]):
			result.right.append(seg[1])
			result.right_types.append('curve')
			result.right.append(seg[2])
			result.right_types.append('curve')

		result.right.append(seg[3])
		result.right_types.append('on')

	# Left edge: reverse for correct winding
	left_segs_rev = [(z3, z2, z1, z0) for z0, z1, z2, z3 in reversed(left_segs)]

	for si, seg in enumerate(left_segs_rev):
		if si == 0:
			result.left.append(seg[0])
			result.left_types.append('on')

		if not _is_line(seg[0], seg[1], seg[2], seg[3]):
			result.left.append(seg[1])
			result.left_types.append('curve')
			result.left.append(seg[2])
			result.left_types.append('curve')

		result.left.append(seg[3])
		result.left_types.append('on')

	return result


def _catmull_rom_to_bezier(points, closed=False):
	'''Convert a point sequence to cubic Bézier segments via Catmull-Rom.

	Catmull-Rom splines pass through all control points and have C1
	continuity. Each segment is converted to cubic Bézier form.

	Args:
		points : list of complex — interpolation points
		closed : bool — closed curve

	Returns:
		list of (z0,z1,z2,z3) — cubic Bézier segments
	'''
	n = len(points)

	if n < 2:
		return []

	if n == 2:
		# Straight line
		z0, z3 = points[0], points[1]
		return [(z0, z0, z3, z3)]

	segments = []
	count = n if closed else n - 1

	for i in range(count):
		# Four Catmull-Rom control points: P_{i-1}, P_i, P_{i+1}, P_{i+2}
		if closed:
			p0 = points[(i - 1) % n]
			p1 = points[i]
			p2 = points[(i + 1) % n]
			p3 = points[(i + 2) % n]
		else:
			p0 = points[max(0, i - 1)]
			p1 = points[i]
			p2 = points[min(n - 1, i + 1)]
			p3 = points[min(n - 1, i + 2)]

		# Catmull-Rom → cubic Bézier (alpha=0.5, tau=0 → standard uniform)
		# BCP1 = P1 + (P2 - P0) / 6
		# BCP2 = P2 - (P3 - P1) / 6
		bcp1 = p1 + (p2 - p0) / 6.0
		bcp2 = p2 - (p3 - p1) / 6.0

		segments.append((p1, bcp1, bcp2, p2))

	return segments


# - Turning number / winding validation -
def turning_number_from_segments(segments, closed=True):
	'''Compute the turning number of a path defined by Bézier segments.

	The turning number is the total tangent rotation divided by 2π.
	For a simple closed CCW path it is +1, for CW it is -1.
	Self-intersecting paths give 0 or other values.

	This is METAFONT's turningcheck.

	Args:
		segments : list of (z0,z1,z2,z3) — Bézier segments
		closed   : bool — must be True for meaningful result

	Returns:
		float — turning number (should be ±1 for simple contours)
	'''
	if not segments or not closed:
		return 0.0

	total_angle = 0.0
	n_samples = 16  # Samples per segment for tangent tracking

	prev_angle = None

	for seg in segments:
		z0, z1, z2, z3 = seg

		for j in range(n_samples):
			t = j / float(n_samples)
			tangent = _bezier_tangent(z0, z1, z2, z3, t)

			if abs(tangent) < 1e-10:
				continue

			angle = cmath.phase(tangent)

			if prev_angle is not None:
				delta = _wrap_angle(angle - prev_angle)
				total_angle += delta

			prev_angle = angle

	# Final segment end → first segment start
	if prev_angle is not None:
		first_tangent = _bezier_tangent(*segments[0], 0.0)

		if abs(first_tangent) > 1e-10:
			angle = cmath.phase(first_tangent)
			delta = _wrap_angle(angle - prev_angle)
			total_angle += delta

	return total_angle / (2.0 * math.pi)


def validate_contour_winding(segments, closed=True, tolerance=0.3):
	'''Check if a closed contour has valid winding (turning number ≈ ±1).

	Returns:
		(bool, float) — (is_valid, turning_number)
	'''
	tn = turning_number_from_segments(segments, closed)
	is_valid = abs(abs(tn) - 1.0) < tolerance
	return is_valid, tn


# - Cusp detection ----------------------
def bezier_curvature(z0, z1, z2, z3, t):
	'''Compute signed curvature of cubic Bézier at parameter t.

	κ(t) = (x'·y'' - y'·x'') / (x'² + y'²)^(3/2)

	Returns:
		float — signed curvature (positive = CCW bending)
	'''
	mt = 1.0 - t

	# First derivative
	d1 = 3.0 * mt * mt * (z1 - z0) + 6.0 * mt * t * (z2 - z1) + 3.0 * t * t * (z3 - z2)

	# Second derivative
	d2 = 6.0 * mt * (z2 - 2.0 * z1 + z0) + 6.0 * t * (z3 - 2.0 * z2 + z1)

	# Cross product of d1 and d2
	cross = d1.real * d2.imag - d1.imag * d2.real
	speed_sq = d1.real * d1.real + d1.imag * d1.imag
	speed_cubed = speed_sq * math.sqrt(speed_sq) if speed_sq > 1e-20 else 1e-30

	return cross / speed_cubed


def find_offset_cusps(z0, z1, z2, z3, offset_distance, n_samples=_CUSP_SAMPLES):
	'''Find parameter values where the offset curve develops cusps.

	A cusp occurs where the curvature κ(t) = ±1/offset_distance,
	meaning the center of curvature coincides with the offset curve.
	At these points the inner offset self-intersects.

	Uses sampling + bisection refinement for robustness.

	Args:
		z0, z1, z2, z3  : complex — skeleton segment
		offset_distance  : float — signed offset distance (positive = right)
		n_samples        : int — initial sampling density

	Returns:
		list of float — parameter values where cusps occur, sorted
	'''
	if abs(offset_distance) < 1e-10:
		return []

	target_curvature = 1.0 / offset_distance
	cusps = []

	# Sample curvature and look for sign changes of (κ - target)
	prev_val = None
	prev_t = 0.0

	for i in range(n_samples + 1):
		t = i / float(n_samples)
		k = bezier_curvature(z0, z1, z2, z3, t)
		val = k - target_curvature

		if prev_val is not None and prev_val * val < 0:
			# Sign change — bisect to find exact crossing
			t_cusp = _bisect_curvature(z0, z1, z2, z3, prev_t, t, target_curvature)
			cusps.append(t_cusp)

		prev_val = val
		prev_t = t

	return cusps


def _bisect_curvature(z0, z1, z2, z3, t_lo, t_hi, target, max_iter=20):
	'''Bisection search for parameter where curvature equals target.'''
	for _ in range(max_iter):
		t_mid = (t_lo + t_hi) * 0.5
		k_mid = bezier_curvature(z0, z1, z2, z3, t_mid)
		k_lo = bezier_curvature(z0, z1, z2, z3, t_lo)

		if (k_mid - target) * (k_lo - target) < 0:
			t_hi = t_mid
		else:
			t_lo = t_mid

		if t_hi - t_lo < 1e-10:
			break

	return (t_lo + t_hi) * 0.5


# - Test ----------------------------------------------------------------
if __name__ == '__main__':
	from pprint import pprint

	section = lambda s: '\n--- {} {}'.format(s, '-' * (40 - len(s)))

	# -- Test 1: Nib creation
	print(section('Nib creation'))
	nib_circle = Nib.circle(50)
	print('Circle nib:', nib_circle)
	print('  tangent_point(right):', nib_circle.tangent_point(complex(1, 0)))
	print('  tangent_point(up):', nib_circle.tangent_point(complex(0, 1)))

	nib_razor = Nib.razor(80, 45)
	print('Razor nib:', nib_razor)
	print('  tangent_point(right):', nib_razor.tangent_point(complex(1, 0)))

	nib_elliptic = Nib.elliptic(60, 30, 30)
	print('Elliptic nib:', nib_elliptic)

	nib_contrast = Nib.from_width_contrast(50, contrast=0.3, angle=25)
	print('Contrast nib:', nib_contrast)

	# -- Test 2: Simple straight stroke
	print(section('Straight stroke'))
	segments = [(0+0j, 33+0j, 66+0j, 100+0j)]
	nib = Nib.circle(20)
	stroke = PenStroke(segments, nib, closed=False)
	result = stroke.expand()
	print('Right edge:', len(result.right), 'points')
	print('Left edge:', len(result.left), 'points')
	print('Outline:', len(result.outline), 'points')

	# -- Test 3: Curved stroke
	print(section('Curved stroke'))
	segments = [(0+0j, 50+80j, 150+80j, 200+0j)]
	stroke = PenStroke(segments, nib, closed=False)
	result = stroke.expand()
	print('Right edge:', len(result.right), 'points')
	print('Left edge:', len(result.left), 'points')
	for z in result.right:
		print('  R: ({:.1f}, {:.1f})'.format(z.real, z.imag))

	# -- Test 4: Multi-segment with corner
	print(section('Multi-segment stroke'))
	segments = [
		(0+0j, 30+50j, 70+80j, 100+80j),
		(100+80j, 130+80j, 170+50j, 200+0j),
	]
	stroke = PenStroke(segments, nib, closed=False)
	result = stroke.expand()
	print('Right:', len(result.right), 'points')
	print('Left:', len(result.left), 'points')

	# -- Test 5: With cut at endpoints
	print(section('Butt cut'))
	stroke2 = PenStroke(segments, nib, closed=False)
	stroke2.set_cut(90, 0, relative=True)
	stroke2.set_cut(90, -1, relative=True)
	result2 = stroke2.expand()
	print('Begin cap:', result2.begin)
	print('End cap:', result2.end)

	# -- Test 6: NodeStrokeOpts
	print(section('Options'))
	print(NodeStrokeOpts())
	print(NodeStrokeOpts.cut(45))
	print(NodeStrokeOpts.cut(90, relative=True))
	print(NodeStrokeOpts.miter(0.5, 0.5))
	print(NodeStrokeOpts.bevel())
	print(NodeStrokeOpts.nib(Nib.circle(30)))

	# -- Test 7: Closed path
	print(section('Closed path'))
	segments = [
		(0+100j, 50+150j, 150+150j, 200+100j),
		(200+100j, 250+50j, 250-50j, 200-100j),
		(200-100j, 150-150j, 50-150j, 0-100j),
		(0-100j, -50-50j, -50+50j, 0+100j),
	]
	stroke = PenStroke(segments, Nib.circle(30), closed=True)
	result = stroke.expand()
	print('Right:', len(result.right), 'points')
	print('Left:', len(result.left), 'points')
	print('Outline:', len(result.outline), 'points')

	# -- Test 8: HobbySpline integration
	print(section('HobbySpline integration'))
	try:
		from typerig.core.objects.hobbyspline import HobbySpline
		hs = HobbySpline([(0, 0), (100, 150), (200, 0)], closed=False)
		nib = Nib.from_width_contrast(40, contrast=0.5, angle=30)
		stroke = PenStroke.from_hobby_spline(hs, nib)
		result = stroke.expand()
		print('Hobby → PenStroke: outline has', len(result.outline), 'points')
	except ImportError:
		print('HobbySpline not available, skipping')
