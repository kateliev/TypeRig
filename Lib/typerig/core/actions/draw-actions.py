# MODULE: TypeRig / Core / Actions / Draw
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function, division

import math

from typerig.core.objects.node import Node, Knot
from typerig.core.objects.contour import Contour
from typerig.core.objects.hobbyspline import HobbySpline, HobbyKnot, HOBBY, LINE, FIXED
from typerig.core.objects.shape import Shape
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.func.math import three_point_circle, two_point_circle, two_point_square, two_mid_square

# - Init ------------------------------------------------------------------------
__version__ = '1.1'

# - Helpers ---------------------------------------------------------------------
def _make_circle_contour(center, radius):
	'''Create a closed circular contour using Hobby splines.

	Arguments:
		center (tuple(float, float)): Center coordinates (x, y).
		radius (float): Circle radius.

	Returns:
		Contour: A closed circular contour.
	'''
	x, y = center
	new_spline = HobbySpline(
		[(x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)],
		closed=True
	)

	new_nodes = [Node(n.x, n.y, type=n.type) for n in new_spline.nodes]

	# - Remove the duplicate closing node
	if len(new_nodes) > 1:
		new_nodes = new_nodes[:-1]

	return Contour(new_nodes, closed=True)

def _make_circle_from_points(points, mode=1):
	'''Create a circular contour from 2 or 3 points.

	Arguments:
		points (list[Point|Node]): 2 or 3 points defining the circle.
		mode (int): 0 = two-point circle (diameter), 1 = three-point circle.

	Returns:
		tuple(Contour, tuple, float): (circle_contour, center, radius)
			or (None, None, None) on failure.
	'''
	if len(points) < 2:
		return None, None, None

	if len(points) == 2 or mode == 0:
		c, r = two_point_circle(points[0].tuple, points[1].tuple)
	elif len(points) >= 3 and mode > 0:
		c, r = three_point_circle(points[0].tuple, points[1].tuple, points[2].tuple)
	else:
		return None, None, None

	if c is None or r is None:
		return None, None, None

	contour = _make_circle_contour(c, r)
	return contour, c, r

def _make_square_from_points(points, mode=0):
	'''Create a square contour from 2 points.

	Arguments:
		points (list[Point|Node]): 2 points defining the square.
		mode (int): 0 = from diagonal, 1 = from midpoints of adjacent sides.

	Returns:
		Contour or None: A closed square contour, or None on failure.
	'''
	if len(points) < 2:
		return None

	if mode == 0:
		square_points = two_point_square(points[0].tuple, points[1].tuple)
	elif mode == 1:
		square_points = two_mid_square(points[0].tuple, points[1].tuple)
	else:
		return None

	if square_points is None:
		return None

	new_nodes = [Node(p[0], p[1]) for p in square_points]
	return Contour(new_nodes, closed=True)

# - Actions ---------------------------------------------------------------------
class DrawActions(object):
	'''Collection of drawing-related actions operating on the TypeRig Core API.

	All methods are static. They operate directly on Shape/Contour/Node objects
	and return the created object on success, or None on failure.
	'''

	# -- Primitive drawing tools ------------------------------------------------
	@staticmethod
	def draw_circle(points, mode=1, rotated=False):
		'''Create a circular contour from selected points.

		Arguments:
			points (list[Point|Node]): 2 or 3 points defining the circle.
			mode (int): 0 = two-point (diameter), 1 = three-point circle.
			rotated (bool): If True, rotate the circle to match the angle
				of the line between the first and last points.

		Returns:
			Contour or None: The created circle contour, or None on failure.
		'''
		if len(points) < 2:
			return None

		new_circle, center, radius = _make_circle_from_points(points, mode)

		if new_circle is None:
			return None

		if rotated and len(points) >= 2:
			new_line = Line(points[0].tuple, points[-1].tuple)
			angle_rad = math.radians(new_line.angle)
			cx, cy = center

			cos_a = math.cos(angle_rad)
			sin_a = math.sin(angle_rad)

			for node in new_circle.nodes:
				dx = node.x - cx
				dy = node.y - cy
				node.x = cx + dx * cos_a - dy * sin_a
				node.y = cy + dx * sin_a + dy * cos_a

		return new_circle

	@staticmethod
	def draw_circle_to_shape(shape, points, mode=1, rotated=False):
		'''Create a circular contour and add it to a shape.

		Arguments:
			shape (Shape): The shape to add the circle to.
			points (list[Point|Node]): 2 or 3 points defining the circle.
			mode (int): 0 = two-point (diameter), 1 = three-point circle.
			rotated (bool): If True, rotate to match point angle.

		Returns:
			bool: True if the circle was created and added.
		'''
		new_circle = DrawActions.draw_circle(points, mode, rotated)

		if new_circle is None:
			return False

		shape.append(new_circle)
		return True

	@staticmethod
	def draw_square(points, mode=0):
		'''Create a square contour from two points.

		Arguments:
			points (list[Point|Node]): 2 points defining the square.
			mode (int): 0 = from diagonal, 1 = from midpoints of sides.

		Returns:
			Contour or None: The created square contour, or None on failure.
		'''
		return _make_square_from_points(points, mode)

	@staticmethod
	def draw_square_to_shape(shape, points, mode=0):
		'''Create a square contour and add it to a shape.

		Arguments:
			shape (Shape): The shape to add the square to.
			points (list[Point|Node]): 2 points defining the square.
			mode (int): 0 = from diagonal, 1 = from midpoints of sides.

		Returns:
			bool: True if the square was created and added.
		'''
		new_square = DrawActions.draw_square(points, mode)

		if new_square is None:
			return False

		shape.append(new_square)
		return True

	# -- Trace and outline tools ------------------------------------------------
	@staticmethod
	def trace_nodes(nodes, mode=0, closed=True):
		'''Create a contour by tracing through a list of nodes.

		Arguments:
			nodes (list[Node]): Nodes to trace through.
			mode (int): Trace mode:
				0 = Keep nodes as they are (preserve on/off-curve types).
				1 = Draw lines only (use only on-curve nodes).
				2 = Draw Hobby splines (fit smooth curves through on-curve nodes).
			closed (bool): Whether the resulting contour should be closed.

		Returns:
			Contour or None: The created contour, or None on failure.
		'''
		if not nodes:
			return None

		if mode == 0:
			new_nodes = [Node(n.x, n.y, type=n.type) for n in nodes]
			return Contour(new_nodes, closed=closed)

		elif mode == 1:
			on_nodes = [n for n in nodes if n.is_on]

			if not on_nodes:
				return None

			new_nodes = [Node(n.x, n.y) for n in on_nodes]
			return Contour(new_nodes, closed=closed)

		elif mode == 2:
			on_nodes = [n for n in nodes if n.is_on]

			if not on_nodes:
				return None

			new_spline = HobbySpline(
				[(n.x, n.y) for n in on_nodes],
				closed=closed
			)

			new_nodes = [Node(n.x, n.y, type=n.type) for n in new_spline.nodes]
			return Contour(new_nodes, closed=closed)

		return None

	@staticmethod
	def trace_nodes_to_shape(shape, nodes, mode=0, closed=True):
		'''Create a contour by tracing through nodes and add it to a shape.

		Arguments:
			shape (Shape): The shape to add the traced contour to.
			nodes (list[Node]): Nodes to trace through.
			mode (int): Trace mode (see trace_nodes).
			closed (bool): Whether the resulting contour should be closed.

		Returns:
			bool: True if the contour was created and added.
		'''
		new_contour = DrawActions.trace_nodes(nodes, mode, closed)

		if new_contour is None:
			return False

		shape.append(new_contour)
		return True


class HobbyDrawActions(object):
	'''Collection of Hobby spline drawing actions operating on the TypeRig Core API.

	Provides tools for creating and manipulating paths using John Hobby's
	METAFONT algorithm with full support for mixed segment types (hobby, line,
	fixed), per-knot tension, direction constraints, and contour conversion.

	All methods are static. They return HobbySpline, Contour, or bool objects.
	'''

	# -- Path creation ----------------------------------------------------------
	@staticmethod
	def hobby_path(knot_positions, closed=False, tension=1.):
		'''Create a Hobby spline path from a list of point positions.
		All segments use the Hobby algorithm with uniform tension.

		Arguments:
			knot_positions (list[tuple(float, float)]): On-curve knot coordinates.
			closed (bool): Whether to close the path.
			tension (float): Global tension (1.0 = default METAFONT, higher = tighter).

		Returns:
			HobbySpline or None: The created spline, or None if fewer than 2 points.
		'''
		if len(knot_positions) < 2:
			return None

		return HobbySpline(knot_positions, closed=closed, tension=tension)

	@staticmethod
	def hobby_path_with_tension(knot_data, closed=False, tension=1.):
		'''Create a Hobby spline path with per-knot tension control.

		Arguments:
			knot_data (list[dict]): Each dict defines a knot:
				'position' (tuple): Required. (x, y) coordinates.
				'alpha' (float): Optional. Departure tension (default: global).
				'beta' (float): Optional. Arrival tension (default: global).
			closed (bool): Whether to close the path.
			tension (float): Global tension for knots without explicit values.

		Returns:
			HobbySpline or None: The created spline.

		Example:
			knot_data = [
				{'position': (0, 0), 'alpha': 1.2},
				{'position': (200, 400)},
				{'position': (400, 0), 'beta': 0.8}
			]
			path = HobbyDrawActions.hobby_path_with_tension(knot_data, closed=True)
		'''
		if len(knot_data) < 2:
			return None

		hs = HobbySpline(closed=closed, tension=tension)

		for kd in knot_data:
			pos = kd['position']
			kwargs = {}

			if 'alpha' in kd:
				kwargs['alpha'] = kd['alpha']
			if 'beta' in kd:
				kwargs['beta'] = kd['beta']

			hs.add_knot(pos, **kwargs)

		return hs

	@staticmethod
	def hobby_path_mixed(knot_data, closed=False, tension=1.):
		'''Create a Hobby spline with mixed segment types — the full
		METAFONT-style path definition with hobby curves, straight lines,
		fixed handles, and direction constraints.

		Arguments:
			knot_data (list[dict]): Each dict defines a knot with:
				'position' (tuple): Required. (x, y) coordinates.
				'segment' (str): Optional. Segment type to NEXT knot:
					'hobby' - Solver finds optimal handles (default).
					'line' - Straight segment, no off-curves.
					'fixed' - User-provided explicit control points.
				'alpha' (float): Optional. Departure tension.
				'beta' (float): Optional. Arrival tension.
				'bcp_out' (tuple): Optional. Explicit outgoing BCP for 'fixed' segments.
				'bcp_in' (tuple): Optional. Explicit incoming BCP for 'fixed' segments.
				'dir_out' (float): Optional. Pinned departure direction in radians.
				'dir_in' (float): Optional. Pinned arrival direction in radians.
			closed (bool): Whether to close the path.
			tension (float): Global tension for knots without explicit values.

		Returns:
			HobbySpline or None: The created spline.

		Example:
			# A path mixing curves, lines, and direction constraints:
			knot_data = [
				{'position': (0, 0), 'dir_out': math.pi / 4},	# depart 45 degrees
				{'position': (200, 400)},						# hobby curve
				{'position': (400, 400), 'segment': 'line'},	# straight to next
				{'position': (600, 200)},						# resume hobby
				{'position': (800, 0), 'dir_in': -math.pi / 4}	# arrive at -45 degrees
			]
			path = HobbyDrawActions.hobby_path_mixed(knot_data, closed=False)
		'''
		if len(knot_data) < 2:
			return None

		hs = HobbySpline(closed=closed, tension=tension)

		for kd in knot_data:
			pos = kd['position']
			kwargs = {}

			for key in ('segment', 'alpha', 'beta', 'bcp_out', 'bcp_in', 'dir_out', 'dir_in'):
				if key in kd:
					kwargs[key] = kd[key]

			hs.add_knot(pos, **kwargs)

		return hs

	# -- Path to Contour conversion ---------------------------------------------
	@staticmethod
	def hobby_to_contour(hobby_spline):
		'''Convert a HobbySpline to a Contour by solving and extracting nodes.

		Arguments:
			hobby_spline (HobbySpline): The spline to convert.

		Returns:
			Contour or None: The resulting contour with on-curve and off-curve nodes.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 2:
			return None

		return hobby_spline.to_contour()

	@staticmethod
	def hobby_to_contour_with_extremes(hobby_spline):
		'''Convert a HobbySpline to a Contour, inserting nodes at all
		horizontal and vertical extremes. Essential for font production.

		Arguments:
			hobby_spline (HobbySpline): The spline to convert.

		Returns:
			Contour or None: The resulting contour with extreme nodes inserted.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 2:
			return None

		extreme_nodes = hobby_spline.insert_extremes()
		return Contour(extreme_nodes, closed=hobby_spline.closed)

	@staticmethod
	def contour_to_hobby(contour, tolerance=0.5):
		'''Convert an existing Contour to a HobbySpline by analyzing its
		segments: detects lines, recovers Hobby tension from existing
		Bezier handles.

		Arguments:
			contour (Contour): The contour to convert.
			tolerance (float): Line detection tolerance. Segments with
				control points closer than this to the chord are treated
				as lines.

		Returns:
			HobbySpline or None: The Hobby representation of the contour.
		'''
		if contour is None or len(contour.nodes) < 2:
			return None

		return HobbySpline.from_contour(contour, tolerance=tolerance)

	# -- Re-solving (smoothing) -------------------------------------------------
	@staticmethod
	def hobby_resmooth(contour, tension=1., tolerance=0.5):
		'''Re-solve a contour through the Hobby algorithm: convert to
		HobbySpline, apply new tension, convert back. This effectively
		smooths the contour while preserving on-curve positions.

		Arguments:
			contour (Contour): The contour to re-smooth.
			tension (float): New global tension to apply.
			tolerance (float): Line detection tolerance for conversion.

		Returns:
			Contour or None: A new smoothed contour.
		'''
		hs = HobbyDrawActions.contour_to_hobby(contour, tolerance)

		if hs is None:
			return None

		hs.tension = tension
		return hs.to_contour()

	@staticmethod
	def hobby_resmooth_with_extremes(contour, tension=1., tolerance=0.5):
		'''Re-solve a contour through Hobby and insert extreme nodes.
		Combines re-smoothing with font-production-ready extreme insertion.

		Arguments:
			contour (Contour): The contour to re-smooth.
			tension (float): New global tension to apply.
			tolerance (float): Line detection tolerance for conversion.

		Returns:
			Contour or None: A new smoothed contour with extreme nodes.
		'''
		hs = HobbyDrawActions.contour_to_hobby(contour, tolerance)

		if hs is None:
			return None

		hs.tension = tension
		extreme_nodes = hs.insert_extremes()
		return Contour(extreme_nodes, closed=contour.closed)

	# -- Tension manipulation ---------------------------------------------------
	@staticmethod
	def hobby_set_tension(hobby_spline, tension):
		'''Set uniform tension on all knots.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			tension (float): Tension value (1.0 = default METAFONT,
				higher = tighter curves, lower = looser curves).

		Returns:
			bool: True on success.
		'''
		if hobby_spline is None:
			return False

		hobby_spline.tension = tension
		return True

	@staticmethod
	def hobby_set_knot_tension(hobby_spline, knot_index, alpha=None, beta=None):
		'''Set tension on a specific knot.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot to modify.
			alpha (float or None): Departure tension. None = keep current.
			beta (float or None): Arrival tension. None = keep current.

		Returns:
			bool: True if the knot was modified.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		knot = hobby_spline.data[knot_index]

		if alpha is not None:
			knot.alpha = float(alpha)

		if beta is not None:
			knot.beta = float(beta)

		return True

	# -- Knot manipulation ------------------------------------------------------
	@staticmethod
	def hobby_add_knot(hobby_spline, position, **kwargs):
		'''Add a knot to the end of a HobbySpline path.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			position (tuple(float, float)): Knot coordinates.
			**kwargs: Optional knot parameters:
				segment (str): 'hobby', 'line', or 'fixed'.
				alpha (float): Departure tension.
				beta (float): Arrival tension.
				bcp_out (tuple): Explicit outgoing BCP for 'fixed' segments.
				bcp_in (tuple): Explicit incoming BCP for 'fixed' segments.
				dir_out (float): Departure direction in radians.
				dir_in (float): Arrival direction in radians.

		Returns:
			HobbyKnot or None: The added knot, or None on failure.
		'''
		if hobby_spline is None:
			return None

		return hobby_spline.add_knot(position, **kwargs)

	@staticmethod
	def hobby_remove_knot(hobby_spline, knot_index):
		'''Remove a knot from a HobbySpline path.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot to remove.

		Returns:
			bool: True if the knot was removed.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		hobby_spline.data.pop(knot_index)
		return True

	@staticmethod
	def hobby_move_knot(hobby_spline, knot_index, x, y):
		'''Move a knot to new coordinates.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot to move.
			x (float): New X coordinate.
			y (float): New Y coordinate.

		Returns:
			bool: True if the knot was moved.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		hobby_spline.data[knot_index].x = float(x)
		hobby_spline.data[knot_index].y = float(y)
		return True

	@staticmethod
	def hobby_shift_knot(hobby_spline, knot_index, dx, dy):
		'''Shift a knot by a delta offset.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot to shift.
			dx (float): Horizontal offset.
			dy (float): Vertical offset.

		Returns:
			bool: True if the knot was shifted.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		hobby_spline.data[knot_index].x += float(dx)
		hobby_spline.data[knot_index].y += float(dy)
		return True

	# -- Direction constraints --------------------------------------------------
	@staticmethod
	def hobby_set_direction(hobby_spline, knot_index, dir_out=None, dir_in=None):
		'''Pin departure and/or arrival direction at a knot.
		This is the METAFONT {dir} equivalent — the solver will honor
		the pinned direction while computing optimal handle lengths.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot.
			dir_out (float or None): Departure direction in radians.
				None = clear constraint (let solver decide).
			dir_in (float or None): Arrival direction in radians.
				None = clear constraint (let solver decide).

		Returns:
			bool: True if the direction was set.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		hobby_spline.data[knot_index].dir_out = dir_out
		hobby_spline.data[knot_index].dir_in = dir_in
		return True

	@staticmethod
	def hobby_set_direction_degrees(hobby_spline, knot_index, dir_out=None, dir_in=None):
		'''Pin departure and/or arrival direction at a knot using degrees.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot.
			dir_out (float or None): Departure direction in degrees.
			dir_in (float or None): Arrival direction in degrees.

		Returns:
			bool: True if the direction was set.
		'''
		out_rad = math.radians(dir_out) if dir_out is not None else None
		in_rad = math.radians(dir_in) if dir_in is not None else None
		return HobbyDrawActions.hobby_set_direction(hobby_spline, knot_index, out_rad, in_rad)

	@staticmethod
	def hobby_set_direction_toward(hobby_spline, knot_index, target_point, mode='out'):
		'''Pin departure or arrival direction at a knot, pointing toward
		a target point. Useful for aiming a curve at a specific location.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot.
			target_point (tuple(float, float)): Target (x, y) to point toward.
			mode (str): 'out' = departure direction, 'in' = arrival direction.

		Returns:
			bool: True if the direction was set.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		knot = hobby_spline.data[knot_index]
		tx, ty = float(target_point[0]), float(target_point[1])
		angle = math.atan2(ty - knot.y, tx - knot.x)

		if mode == 'out':
			knot.dir_out = angle
		elif mode == 'in':
			knot.dir_in = angle
		else:
			return False

		return True

	# -- Segment type manipulation ----------------------------------------------
	@staticmethod
	def hobby_set_segment_type(hobby_spline, knot_index, segment_type, bcp_out=None, bcp_in=None):
		'''Set the segment type from a knot to the next knot.

		Arguments:
			hobby_spline (HobbySpline): The spline to modify.
			knot_index (int): Index of the knot (segment goes to knot_index + 1).
			segment_type (str): 'hobby', 'line', or 'fixed'.
			bcp_out (tuple or None): Explicit outgoing BCP (x, y) for 'fixed' type.
			bcp_in (tuple or None): Explicit incoming BCP (x, y) for 'fixed' type.

		Returns:
			bool: True if the segment type was set.
		'''
		if hobby_spline is None:
			return False

		if knot_index < 0 or knot_index >= len(hobby_spline.data):
			return False

		knot = hobby_spline.data[knot_index]
		knot.segment_type = segment_type

		if segment_type == FIXED:
			if bcp_out is not None:
				knot.fixed_bcp_out = complex(float(bcp_out[0]), float(bcp_out[1]))
			if bcp_in is not None:
				n = len(hobby_spline.data)
				next_idx = (knot_index + 1) % n
				hobby_spline.data[next_idx].fixed_bcp_in = complex(float(bcp_in[0]), float(bcp_in[1]))
		else:
			knot.fixed_bcp_out = None

		return True

	# -- Path operations --------------------------------------------------------
	@staticmethod
	def hobby_reverse(hobby_spline):
		'''Reverse the direction of a Hobby spline path. Swaps segment
		types and direction constraints accordingly.

		Arguments:
			hobby_spline (HobbySpline): The spline to reverse.

		Returns:
			bool: True if the path was reversed.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 2:
			return False

		hobby_spline.reverse()
		return True

	@staticmethod
	def hobby_close(hobby_spline):
		'''Close an open Hobby spline path.

		Arguments:
			hobby_spline (HobbySpline): The spline to close.

		Returns:
			bool: True if the path was closed, False if already closed.
		'''
		if hobby_spline is None:
			return False

		if hobby_spline.closed:
			return False

		hobby_spline.closed = True
		return True

	@staticmethod
	def hobby_open(hobby_spline):
		'''Open a closed Hobby spline path.

		Arguments:
			hobby_spline (HobbySpline): The spline to open.

		Returns:
			bool: True if the path was opened, False if already open.
		'''
		if hobby_spline is None:
			return False

		if not hobby_spline.closed:
			return False

		hobby_spline.closed = False
		return True

	@staticmethod
	def hobby_shift(hobby_spline, dx, dy):
		'''Shift (translate) all knots in a Hobby spline.

		Arguments:
			hobby_spline (HobbySpline): The spline to shift.
			dx (float): Horizontal offset.
			dy (float): Vertical offset.

		Returns:
			bool: True on success.
		'''
		if hobby_spline is None:
			return False

		hobby_spline.shift(dx, dy)
		return True

	# -- Query tools ------------------------------------------------------------
	@staticmethod
	def hobby_get_segments(hobby_spline):
		'''Get solved segments as CubicBezier and Line objects.

		Arguments:
			hobby_spline (HobbySpline): The spline to query.

		Returns:
			list[CubicBezier|Line] or None: Solved segment objects.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 2:
			return None

		return hobby_spline.segments

	@staticmethod
	def hobby_get_nodes(hobby_spline):
		'''Get solved flat node list (on-curve + off-curve nodes).

		Arguments:
			hobby_spline (HobbySpline): The spline to query.

		Returns:
			list[Node] or None: Solved node list.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 2:
			return None

		return hobby_spline.nodes

	@staticmethod
	def hobby_get_bounds(hobby_spline):
		'''Get the bounding box of a Hobby spline's knot positions.

		Arguments:
			hobby_spline (HobbySpline): The spline to query.

		Returns:
			Bounds or None: The bounding box.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 1:
			return None

		return hobby_spline.bounds

	@staticmethod
	def hobby_get_winding(hobby_spline):
		'''Get the winding direction of a Hobby spline.

		Arguments:
			hobby_spline (HobbySpline): The spline to query.

		Returns:
			bool or None: True = clockwise, False = counter-clockwise.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 3:
			return None

		return hobby_spline.get_winding()

	@staticmethod
	def hobby_get_area(hobby_spline):
		'''Get the signed area enclosed by a Hobby spline.

		Arguments:
			hobby_spline (HobbySpline): The spline to query.

		Returns:
			float or None: The signed area.
		'''
		if hobby_spline is None or len(hobby_spline.data) < 3:
			return None

		return hobby_spline.get_area()

	# -- Convenience builders ---------------------------------------------------
	@staticmethod
	def hobby_polygon(knot_positions, closed=True):
		'''Create a polygon (all line segments) from knot positions.

		Arguments:
			knot_positions (list[tuple(float, float)]): Vertex coordinates.
			closed (bool): Whether to close the polygon.

		Returns:
			HobbySpline or None: A spline with all line segments.
		'''
		if len(knot_positions) < 2:
			return None

		hs = HobbySpline(closed=closed)

		for pos in knot_positions:
			hs.add_knot(pos, segment=LINE)

		return hs

	@staticmethod
	def hobby_superellipse(center, width, height, tension=1., closed=True):
		'''Create a superellipse (rounded rectangle) using Hobby splines.
		With tension=1.0 produces a circle-like shape. Higher tension
		produces more rectangular shapes, lower tension produces more
		diamond-like shapes.

		Arguments:
			center (tuple(float, float)): Center coordinates (x, y).
			width (float): Full width.
			height (float): Full height.
			tension (float): Hobby tension (1.0 = default).
			closed (bool): Whether to close the shape.

		Returns:
			HobbySpline or None: The superellipse path.
		'''
		cx, cy = float(center[0]), float(center[1])
		hw, hh = width / 2., height / 2.

		knots = [
			(cx, cy - hh),		# Bottom
			(cx + hw, cy),		# Right
			(cx, cy + hh),		# Top
			(cx - hw, cy)		# Left
		]

		return HobbySpline(knots, closed=closed, tension=tension)

	@staticmethod
	def hobby_arc(center, radius, start_angle, end_angle, tension=1., num_knots=None):
		'''Create an arc using Hobby splines.

		Arguments:
			center (tuple(float, float)): Center coordinates.
			radius (float): Arc radius.
			start_angle (float): Start angle in degrees.
			end_angle (float): End angle in degrees.
			tension (float): Hobby tension.
			num_knots (int or None): Number of intermediate knots.
				If None, auto-calculated from arc span (1 per 90 degrees).

		Returns:
			HobbySpline or None: The arc path (open).
		'''
		cx, cy = float(center[0]), float(center[1])
		radius = float(radius)

		if radius <= 0.:
			return None

		span = end_angle - start_angle

		if num_knots is None:
			num_knots = max(2, int(abs(span) / 90.) + 1)

		if num_knots < 2:
			num_knots = 2

		angles = [math.radians(start_angle + span * i / (num_knots - 1)) for i in range(num_knots)]
		knots = [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]

		hs = HobbySpline(closed=False, tension=tension)

		for i, pos in enumerate(knots):
			# - Pin tangent directions perpendicular to radius
			angle = angles[i]
			tangent = angle + math.pi / 2. if span >= 0. else angle - math.pi / 2.

			hs.add_knot(pos, dir_out=tangent, dir_in=tangent)

		return hs

	@staticmethod
	def hobby_rounded_rect(origin, width, height, corner_radius, tension=1.):
		'''Create a rounded rectangle using Hobby splines with mixed
		segment types — lines for straight edges, hobby curves for corners.

		Arguments:
			origin (tuple(float, float)): Bottom-left corner coordinates.
			width (float): Rectangle width.
			height (float): Rectangle height.
			corner_radius (float): Corner rounding radius.
			tension (float): Hobby tension for rounded corners.

		Returns:
			HobbySpline or None: The rounded rectangle path.
		'''
		ox, oy = float(origin[0]), float(origin[1])
		w, h = float(width), float(height)
		r = min(float(corner_radius), w / 2., h / 2.)

		if w <= 0. or h <= 0.:
			return None

		if r <= 0.:
			# - Degenerate to rectangle
			return HobbyDrawActions.hobby_polygon([
				(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h)
			], closed=True)

		hs = HobbySpline(closed=True, tension=tension)

		# Bottom edge: left corner end -> right corner start
		hs.add_knot((ox + r, oy), segment=LINE)			# BL corner end
		hs.add_knot((ox + w - r, oy))						# BR corner start -> hobby
		hs.add_knot((ox + w, oy + r), segment=LINE)		# BR corner end
		hs.add_knot((ox + w, oy + h - r))					# TR corner start -> hobby
		hs.add_knot((ox + w - r, oy + h), segment=LINE)	# TR corner end
		hs.add_knot((ox + r, oy + h))						# TL corner start -> hobby
		hs.add_knot((ox, oy + h - r), segment=LINE)		# TL corner end
		hs.add_knot((ox, oy + r))							# BL corner start -> hobby

		return hs
