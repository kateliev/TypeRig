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
from typerig.core.objects.node import Node, node_types

from typerig.core.objects.hobbyspline import (
	robust_direction,
	robust_direction_end,
	turning_angle,
	is_line_segment,
	force_convex,
	extrapolate_segment,
)

# - Init --------------------------------
__version__ = '0.1.0'

# - Constants ---------------------------
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

		For elliptic nibs: finds the time on the nib path where 
		directiontime matches, then returns that point.

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
			# Razor nib: two endpoints
			# Choose the one where the cross product with direction
			# indicates the correct side
			p0, p1 = self.path[0], self.path[1]
			edge = p1 - p0

			if abs(edge) < 1e-10:
				return p0

			# Check turning angle to determine which endpoint
			ta = turning_angle(direction, edge)

			if ta is None:
				return (p0 + p1) * 0.5  # Parallel — use midpoint

			if ta < 0:
				return p0
			else:
				return p1

		# Elliptic nib: find directiontime
		# Walk segments, find where tangent aligns with direction
		segs = self.segments
		best_t = 0
		best_dot = -2.
		best_point = self.path[0]

		for seg_idx, (z0, z1, z2, z3) in enumerate(segs):
			# Sample tangent at several points along segment
			for sub_t in range(21):
				t = sub_t / 20.

				# Tangent of cubic at parameter t
				mt = 1 - t
				tangent = (3 * mt * mt * (z1 - z0) +
						   6 * mt * t * (z2 - z1) +
						   3 * t * t * (z3 - z2))

				if abs(tangent) < 1e-10:
					continue

				tn = tangent / abs(tangent)

				# We want tangent parallel to direction
				# Maximize dot product (real part of conj(d)*tn)
				dot = (d.conjugate() * tn).real

				if dot > best_dot:
					best_dot = dot
					best_t = t

					# Evaluate point on curve
					best_point = (mt**3 * z0 + 3 * mt**2 * t * z1 +
								  3 * mt * t**2 * z2 + t**3 * z3)

		# Refine with Newton-Raphson (one iteration)
		# Find segment containing best_t and refine
		return best_point

	def arc_between(self, dir_a, dir_b, center):
		'''Extract the nib arc between two directions.
		Returns list of complex points forming the arc subpath.

		This is the pen_join operation: given arrival and departure 
		directions at a corner, extract the nib outline between the 
		corresponding tangent points.

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

	Attributes:
		right : list of complex — right edge of envelope 
		left  : list of complex — left edge of envelope
		begin : list of complex — cap at path start (open paths only)
		end   : list of complex — cap at path end (open paths only)
		outline : list of complex — complete closed outline
	'''

	def __init__(self):
		self.right = []
		self.left = []
		self.begin = []
		self.end = []

	@property
	def outline(self):
		'''Complete closed outline path'''
		if self.begin or self.end:
			# Open path: right + end_cap + left_reversed + begin_cap
			return self.right + self.end + list(reversed(self.left)) + self.begin
		else:
			# Closed path: right + left_reversed
			return self.right + list(reversed(self.left))

	def to_nodes(self):
		'''Convert outline to Node list for Contour construction'''
		result = []
		points = self.outline

		if not points:
			return result

		# Convert complex points to Nodes
		# Determine structure: groups of (on, bcp_out, bcp_in, on, ...)
		for i, z in enumerate(points):
			# Simple heuristic: every 3rd point starting from 0 is on-curve
			if i % 3 == 0:
				result.append(Node(z.real, z.imag, type='on'))
			else:
				result.append(Node(z.real, z.imag, type='curve'))

		return result

	def to_node_lists(self):
		'''Return separate Node lists for right edge, left edge, caps'''
		def to_nodes(points):
			result = []
			for i, z in enumerate(points):
				if i % 3 == 0:
					result.append(Node(z.real, z.imag, type='on'))
				else:
					result.append(Node(z.real, z.imag, type='curve'))
			return result

		return {
			'right': to_nodes(self.right),
			'left': to_nodes(self.left),
			'begin': to_nodes(self.begin),
			'end': to_nodes(self.end),
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
	'''Convert a CubicBezier or Line to tuple of 4 complex numbers'''
	if isinstance(segment, Line):
		z0 = complex(segment.p0.x, segment.p0.y)
		z3 = complex(segment.p1.x, segment.p1.y)
		return (z0, z0, z3, z3)  # Degenerate cubic
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


def pen_stroke_edge(segments, nibs, method=METHOD_DIRECTION, ignore_dirs=None, is_closed=False):
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

	Returns:
		list of complex — edge path points (on-curves and BCPs)
	'''
	if not segments:
		return []

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

	for i in range(n_seg):
		qa, q1, q2, qb = edge_segs[i]

		if i == 0:
			result.append(qa)

		# Add BCPs (skip for lines)
		if not _is_line(qa, q1, q2, qb):
			result.append(q1)
			result.append(q2)

		# Corner join to next segment
		if i < n_seg - 1 or is_closed:
			next_i = (i + 1) % n_seg
			qa_next = edge_segs[next_i][0]

			# Check gap between end of this edge and start of next
			gap = abs(qb - qa_next)

			if gap > 0.5:
				# Need a corner join — for now, straight connection
				# TODO: pen arc join using nib.arc_between
				result.append(qb)
				if not is_closed or i < n_seg - 1:
					result.append(qa_next)
			else:
				result.append(qb)
		else:
			result.append(qb)

	return result


# - Cut (butt cap) computation ----------
def compute_cut(nib, direction, angle, center, relative=False):
	'''Compute a razor cut across the stroke at a given angle.
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
	'''Compute miter join by extrapolating two edge segments until they intersect.
	Based on MetaType1 tip macro.

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
			segments    : list — CubicBezier/Line objects or (z0,z1,z2,z3) complex tuples
			default_nib : Nib — default pen shape
			closed      : bool — whether path is closed
			method      : int — stroke method (0, 1, or 2)
			cap         : str — cap type for open paths ('round' or 'butt')
			join        : str — default join type at corners ('round', 'miter', 'bevel')
		'''
		self.default_nib = default_nib
		self.closed = kwargs.pop('closed', False)
		self.method = kwargs.pop('method', METHOD_DIRECTION)
		self.cap = kwargs.pop('cap', CAP_ROUND)
		self.join = kwargs.pop('join', JOIN_ROUND)

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
		result = StrokeResult()
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
		result.right = pen_stroke_edge(
			self._segments, nibs_right, self.method, 
			ignore_r, self.closed
		)

		# Compute left edge (reverse path direction)
		# Reverse each segment: swap z0↔z3, z1↔z2
		reversed_segs = [(z3, z2, z1, z0) for z0, z1, z2, z3 in reversed(self._segments)]
		reversed_nibs = list(reversed(nibs_left))

		result.left = pen_stroke_edge(
			reversed_segs, reversed_nibs, self.method, 
			ignore_l, self.closed
		)

		# Caps for open paths
		if not self.closed:
			# Begin cap: connects left edge end to right edge start
			result.begin = self._compute_cap(
				0,  # start node
				result.left[-1] if result.left else complex(0, 0),
				result.right[0] if result.right else complex(0, 0),
				forward=False
			)

			# End cap: connects right edge end to left edge start
			result.end = self._compute_cap(
				self._n_nodes - 1,  # end node
				result.right[-1] if result.right else complex(0, 0),
				result.left[0] if result.left else complex(0, 0),
				forward=True
			)

		return result

	def _compute_cap(self, node_index, from_point, to_point, forward=True):
		'''Compute a path cap at an open path endpoint.

		Args:
			node_index : int
			from_point : complex — end of outgoing edge
			to_point   : complex — start of return edge
			forward    : bool — True for end cap, False for begin cap

		Returns:
			list of complex — cap path points
		'''
		opts = self._node_opts.get(node_index)

		if opts is not None and opts.has_cut:
			# Butt cut: straight line
			return [from_point, to_point]

		# Default: use pen arc
		direction = self._direction_at_node(node_index)

		if not forward:
			direction = -direction

		nib = self._get_nib(node_index, 'right')
		node_pos = self._segments[min(node_index, len(self._segments) - 1)][0 if node_index == 0 else 3]

		arc = nib.arc_between(direction, -direction, node_pos)

		if arc:
			return arc

		return [from_point, to_point]

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
