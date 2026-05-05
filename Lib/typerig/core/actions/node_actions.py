# MODULE: TypeRig / Core / Actions / Node
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

from typerig.core.objects.node import Node, node_types
from typerig.core.objects.contour import Contour
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line, Vector
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.utils import Bounds

from typerig.core.objects.metapen import (
	compute_cap_outward_direction,
	compute_cap_round_arc,
	compute_cap_angular_tip,
)

# - Init ------------------------------------------------------------------------
__version__ = '1.0'

# - Helpers ---------------------------------------------------------------------
def _scale_offset(node, offset_x, offset_y, width, height):
	'''Calculate scaled offset - coordinates as percent of bounding box dimensions.'''
	new_x = -node.x + width * (float(node.x) / width + offset_x)
	new_y = -node.y + height * (float(node.y) / height + offset_y)
	return (new_x, new_y)

def _segment_forward_tangent(segment, at_start):
	'''Unit tangent of a segment in forward direction (from p0 toward p1/p3).

	Args:
		segment  : Line | CubicBezier
		at_start : bool — True for tangent at p0 (start), False for tangent at end.

	Returns:
		Point or None — unit tangent vector, or None on degenerate segment.
	'''
	if isinstance(segment, CubicBezier):
		return segment.solve_tangent_at_time(0.0 if at_start else 1.0)

	if isinstance(segment, Line):
		dx = segment.p1.x - segment.p0.x
		dy = segment.p1.y - segment.p0.y
		length = math.hypot(dx, dy)
		if length < 1e-10:
			return None
		return Point(dx / length, dy / length)

	return None


def _intersect_perpendicular_with_segment(origin_point, perp_direction, segment):
	'''Cast a doubly-infinite line through origin_point along perp_direction,
	find the closest intersection with segment, and return (foot_point, time_on_segment).

	"Closest" = smallest distance from origin_point to the intersection. This
	naturally selects the side of the perpendicular pointing toward the segment.

	Args:
		origin_point   : Point
		perp_direction : Point — unit perpendicular vector
		segment        : Line | CubicBezier

	Returns:
		(Point, float) or (None, None)
	'''
	long = 100000.0

	end0 = Point(origin_point.x - perp_direction.x * long,
				 origin_point.y - perp_direction.y * long)
	end1 = Point(origin_point.x + perp_direction.x * long,
				 origin_point.y + perp_direction.y * long)
	ray = Line(end0.tuple, end1.tuple)

	if isinstance(segment, Line):
		hit = segment.intersect_line(ray, projection=False)
		# Void detection — Void.x and Void.y are None
		if hit is None or getattr(hit, 'x', None) is None:
			return None, None

		# Compute time on segment
		seg_dx = segment.p1.x - segment.p0.x
		seg_dy = segment.p1.y - segment.p0.y
		seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy
		if seg_len_sq < 1e-10:
			return None, None
		t = ((hit.x - segment.p0.x) * seg_dx + (hit.y - segment.p0.y) * seg_dy) / seg_len_sq
		if not (0.0 <= t <= 1.0):
			return None, None
		return hit, t

	if isinstance(segment, CubicBezier):
		(times_x, times_y), (points_x, points_y) = segment.intersect_line(ray)
		# Aggregate all hits with their times; pick the closest to origin_point
		candidates = []
		for t, p in zip(times_x, points_x):
			if 0.0 <= t <= 1.0:
				candidates.append((t, p))
		for t, p in zip(times_y, points_y):
			if 0.0 <= t <= 1.0:
				candidates.append((t, p))
		if not candidates:
			return None, None

		def dist2(p):
			return (p.x - origin_point.x) ** 2 + (p.y - origin_point.y) ** 2

		t, p = min(candidates, key=lambda tp: dist2(tp[1]))
		return p, t

	return None, None


def _remove_inclusive_range_forward(start_node, stop_node):
	'''Remove start_node and every node forward of it up to (but not including)
	stop_node. start_node itself IS removed.
	'''
	cursor = start_node
	to_remove = []
	guard = 10000

	while cursor is not None and cursor is not stop_node and guard > 0:
		to_remove.append(cursor)
		cursor = cursor.next
		guard -= 1

	for n in reversed(to_remove):
		n.remove()


def _get_crossing(node_list):
	'''Find the intersection (crossing) point of the incoming and outgoing
	tangent lines at the first and last on-curve nodes in a selection.
	Used for rebuilding corners back to sharp points.
	'''
	on_nodes = [node for node in node_list if node.is_on]
	first_node, last_node = on_nodes[0], on_nodes[-1]

	# - Build tangent lines from prev/next on-curve neighbors
	line_in = Line(first_node.prev_on.point, first_node.point)
	line_out = Line(last_node.point, last_node.next_on.point)

	crossing = line_in.intersect_line(line_out, True)
	return crossing

# - Actions ---------------------------------------------------------------------
class NodeActions(object):
	'''Collection of node-related actions operating on the TypeRig Core API.

	All methods are static. They operate directly on Contour/Node objects
	and return True on success, False on failure or no-op.
	'''

	# -- Basic node tools -------------------------------------------------------
	@staticmethod
	def node_insert(contour, node_indices, time=0.5):
		'''Insert a new node at parametric time along the segment starting
		at each given on-curve node index.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes whose outgoing
				segments will be split. Processed in reverse order to keep
				indices stable.
			time (float): Parametric position along the segment (0.0 to 1.0).

		Returns:
			bool: True if at least one node was inserted.
		'''
		if not (0. <= time <= 1.):
			return False

		inserted = False

		for nid in sorted(node_indices, reverse=True):
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			result = node.insert_after(time)

			if result is not None:
				inserted = True

		return inserted

	@staticmethod
	def node_insert_at_extremes(contour, node_indices):
		'''Insert nodes at the extrema of curve segments starting at the
		given on-curve node indices.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes. Only segments
				that are CubicBezier curves are processed.

		Returns:
			bool: True if at least one extreme node was inserted.
		'''
		inserted = False

		for nid in sorted(node_indices, reverse=True):
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			segment = node.segment

			if not isinstance(segment, CubicBezier):
				continue

			extremes = segment.solve_extremes()

			if len(extremes):
				# - Insert at each extreme, in reverse t-order to keep earlier t values valid
				for extreme_point, extreme_t in sorted(extremes, key=lambda e: e[1], reverse=True):
					node.insert_after(extreme_t)

				inserted = True

		return inserted

	@staticmethod
	def node_remove(contour, node_indices):
		'''Remove on-curve nodes at the given indices and their associated
		off-curve handles. Removal proceeds in reverse index order to keep
		indices stable.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes to remove.

		Returns:
			bool: True if at least one node was removed.
		'''
		removed = False

		for nid in sorted(node_indices, reverse=True):
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			# - Remove the on-curve node and its associated off-curve handles
			# -- Collect nodes in the segment between prev_on and next_on
			prev_on = node.prev_on
			next_on = node.next_on

			# -- Gather nodes to remove (between prev_on exclusive and next_on exclusive)
			to_remove = []
			cursor = prev_on.next

			while cursor is not None and cursor is not next_on:
				to_remove.append(cursor)
				cursor = cursor.next

			for rm_node in reversed(to_remove):
				rm_node.remove()

			removed = True

		return removed

	@staticmethod
	def node_round_coordinates(nodes, round_up=True):
		'''Round node coordinates to integer values.

		Arguments:
			nodes (list[Node]): Nodes whose coordinates will be rounded.
			round_up (bool): If True, use ceil; if False, use floor.

		Returns:
			bool: True if any coordinates were changed.
		'''
		changed = False
		round_func = math.ceil if round_up else math.floor

		for node in nodes:
			new_x = round_func(node.x)
			new_y = round_func(node.y)

			if new_x != node.x or new_y != node.y:
				node.x = new_x
				node.y = new_y
				changed = True

		return changed

	@staticmethod
	def node_set_smooth(nodes, smooth=True):
		'''Set the smooth flag on the given nodes.

		Arguments:
			nodes (list[Node]): Nodes to modify.
			smooth (bool): True for smooth, False for sharp.

		Returns:
			bool: True if any flags were changed.
		'''
		changed = False

		for node in nodes:
			if node.smooth != smooth:
				node.smooth = smooth
				changed = True

		return changed

	# -- Corner tools -----------------------------------------------------------
	@staticmethod
	def corner_mitre(node, mitre_size=5, is_radius=False):
		'''Mitre a corner at the given on-curve node.

		Arguments:
			node (Node): The on-curve corner node.
			mitre_size (float): Size of the mitre. Interpreted as radius if
				is_radius is True, otherwise as the mitre cut distance.
			is_radius (bool): Interpret mitre_size as radius.

		Returns:
			tuple(Node, Node) or None: The two new corner nodes, or None on failure.
		'''
		if not node.is_on:
			return None

		return node.corner_mitre(mitre_size, is_radius)

	@staticmethod
	def corner_round(node, rounding_size=5, is_radius=False):
		'''Round a corner at the given on-curve node using an inscribed circle of radius rounding_size.

		Arguments:
			node (Node): The on-curve corner node.
			rounding_size (float): Inscribed circle radius.
			is_radius (bool): Unused, kept for call-site compatibility.

		Returns:
			tuple(Node, Node, Node, Node) or None: The corner segment
				(on, bcp_out, bcp_in, on) or None on failure.
		'''
		if not node.is_on:
			return None

		return node.corner_round(rounding_size, is_radius)

	@staticmethod
	def corner_loop(node, overlap=20, is_radius=True):
		'''Create a loop (overlap) at a corner by applying a negative mitre.

		Arguments:
			node (Node): The on-curve corner node.
			overlap (float): Size of the loop overlap.
			is_radius (bool): Interpret overlap as radius.

		Returns:
			tuple(Node, Node) or None: The two new loop nodes, or None on failure.
		'''
		if not node.is_on:
			return None

		return node.corner_mitre(-overlap, is_radius)

	@staticmethod
	def corner_trap(node, parameter=10, depth=50, trap=2, smooth=True, incision=True):
		'''Create an ink trap at a corner node.

		Arguments:
			node (Node): The on-curve corner node.
			parameter (float): Incision depth or mouth width depending on
				incision flag.
			depth (float): Trap side length.
			trap (float): Trap bottom width.
			smooth (bool): Create smooth trap transitions.
			incision (bool): If True, parameter controls incision depth;
				if False, it controls mouth width.

		Returns:
			tuple(Node, ...) or None: The trap nodes, or None on failure.
		'''
		if not node.is_on:
			return None

		return node.corner_trap(parameter, depth, trap, smooth, incision)

	@staticmethod
	def corner_rebuild(contour, node_indices, cleanup=True):
		'''Rebuild (collapse) a rounded or modified corner back to a sharp point.
		Finds the intersection of the incoming/outgoing tangent lines and
		moves the selection to that crossing point.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of selected nodes (must include
				at least 2 on-curve nodes that bracket the corner region).
			cleanup (bool): If True, remove intermediate nodes after collapsing.

		Returns:
			bool: True if the corner was rebuilt.
		'''
		selected_nodes = [contour.nodes[nid] for nid in node_indices]
		on_nodes = [n for n in selected_nodes if n.is_on]

		if len(on_nodes) < 2:
			return False

		crossing = _get_crossing(selected_nodes)

		if crossing is None:
			return False

		if cleanup:
			first_on = on_nodes[0]
			last_on = on_nodes[-1]

			# - Move first node to crossing
			first_on.smart_reloc(crossing.x, crossing.y)

			# - Remove nodes between first and last on-curve
			cursor = first_on.next
			to_remove = []

			while cursor is not None and cursor is not last_on:
				to_remove.append(cursor)
				cursor = cursor.next

			# - Also remove the last on-curve (it collapses into first)
			to_remove.append(last_on)

			for rm_node in reversed(to_remove):
				rm_node.remove()
		else:
			for node in selected_nodes:
				node.reloc(crossing.x, crossing.y)

		return True

	# -- Cap tools --------------------------------------------------------------
	# Cap operations work on two stem-corner on-curve nodes A and B that bracket
	# the cap region of an open- or closed-stem terminal. They produce a flat
	# (butt), circular (round), or pointed (angular) cap by replacing whatever
	# nodes lie between A and B with the appropriate geometry. cap_rebuild is
	# the universal "flatten any existing cap" tool — works on any contiguous
	# selection inside a cap, not a fixed node count.
	#
	# The math primitives live in typerig.core.objects.metapen:
	#   compute_cap_outward_direction, compute_cap_round_arc, compute_cap_angular_tip
	# This keeps cap construction shared with the stroke envelope expander.

	@staticmethod
	def cap_butt(contour, idx_a, idx_b, side='auto'):
		'''Build a perpendicular flat (butt) cap between two stem-corner nodes.

		Drops a perpendicular from one corner onto the opposite stem segment.
		The new on-curve replaces both A and B and any nodes between them; the
		surviving stem segment on the kept side is split at the perpendicular foot.

		Arguments:
			contour : Contour
			idx_a   : int — first stem corner (cap region begins after A in contour order)
			idx_b   : int — second stem corner (cap region ends at B in contour order)
			side    : 'a' | 'b' | 'auto' — which stem to keep.
				'a' projects from B onto the segment behind A (keeps prev_on(A)
				    intact and clean-cuts seg_in_a).
				'b' projects from A onto the segment ahead of B (keeps next_on(B)
				    intact and clean-cuts seg_out_b).
				'auto' picks the side whose perpendicular foot lies closer to the
				    opposite corner — i.e. the shorter cut.

		Returns:
			Node or None — the inserted on-curve replacing the cap, or None on failure.
		'''
		nodes = contour.nodes
		node_a = nodes[idx_a]
		node_b = nodes[idx_b]

		if not node_a.is_on or not node_b.is_on or node_a is node_b:
			return None

		seg_in_a = node_a.prev_on.segment    # segment ending at A
		seg_out_b = node_b.segment           # segment starting at B

		if seg_in_a is None or seg_out_b is None:
			return None

		tangent_a = _segment_forward_tangent(seg_in_a, at_start=False)
		tangent_b = _segment_forward_tangent(seg_out_b, at_start=True)

		if tangent_a is None or tangent_b is None:
			return None

		# Perpendiculars (rotate 90° CCW)
		perp_a = Point(-tangent_a.y, tangent_a.x)
		perp_b = Point(-tangent_b.y, tangent_b.x)

		# Candidate 'a': cut on seg_in_a using B's perpendicular
		foot_a, time_a = _intersect_perpendicular_with_segment(node_b.point, perp_b, seg_in_a)
		# Candidate 'b': cut on seg_out_b using A's perpendicular
		foot_b, time_b = _intersect_perpendicular_with_segment(node_a.point, perp_a, seg_out_b)

		# Reject "trivial" intersections where the foot lands AT the cap corner
		# (time near 1.0 on seg_in_a == foot at A; time near 0.0 on seg_out_b == foot at B).
		# These mean the chord A-B is already perpendicular to the stem on that side
		# — there's nothing to cut. Caller (e.g. cap_rebuild) handles the no-cut fallback.
		eps = 1e-3
		if time_a is not None and time_a > 1.0 - eps:
			foot_a, time_a = None, None
		if time_b is not None and time_b < eps:
			foot_b, time_b = None, None

		if side == 'auto':
			if foot_a is None and foot_b is None:
				return None
			if foot_a is None:
				chosen = 'b'
			elif foot_b is None:
				chosen = 'a'
			else:
				dist_a = math.hypot(foot_a.x - node_b.point.x, foot_a.y - node_b.point.y)
				dist_b = math.hypot(foot_b.x - node_a.point.x, foot_b.y - node_a.point.y)
				chosen = 'a' if dist_a <= dist_b else 'b'
		elif side == 'a':
			if foot_a is None:
				return None
			chosen = 'a'
		elif side == 'b':
			if foot_b is None:
				return None
			chosen = 'b'
		else:
			return None

		if chosen == 'a':
			# Insert foot on seg_in_a (before A). Keep B as the second cap corner.
			# Remove A and any cap interior between A and B (exclusive of B).
			prev_a = node_a.prev_on
			prev_a.insert_after(time_a)
			new_node = prev_a.next_on
			new_node.point = foot_a   # snap to exact foot
			new_node.smooth = False
			_remove_inclusive_range_forward(new_node.next, node_b)
		else:
			# Insert foot on seg_out_b (after B). Keep A as the first cap corner.
			# Remove B and any cap interior between A and B (exclusive of A).
			node_b.insert_after(time_b)
			new_node = node_b.next_on
			new_node.point = foot_b
			new_node.smooth = False
			_remove_inclusive_range_forward(node_a.next, new_node)

		return new_node

	@staticmethod
	def cap_round(contour, idx_a, idx_b, curvature=1.0, keep_length=False):
		'''Build an italic-aware circular cap between two stem-corner nodes.

		Two placement modes:
		  * keep_length=False (default) — the cap extends OUTWARD past the chord
		    A-B by radius r along the stem axis. The original stems are kept
		    intact and the round cap adds length to the overall path. The tip
		    sits on the circle of radius |AB|/2 centred at midpoint(A,B), in the
		    outward stem direction.
		  * keep_length=True — the cap fits INSIDE the original stems. Each
		    stem segment is shortened by r so the new corners A', B' sit at
		    distance r INSIDE the original A, B along the stem. Overall path
		    length is preserved (matches original FL cap_round behavior).

		Italic-aware in both modes: the cap tip lies along the averaged stem
		axis, not the chord-perpendicular. See compute_cap_round_arc.

		Arguments:
			contour     : Contour
			idx_a       : int — first stem corner
			idx_b       : int — second stem corner
			curvature   : float — handle-length multiplier (1.0 = true circle).
			keep_length : bool — preserve overall path length (FL behaviour).

		Returns:
			Node or None — the tip on-curve, or None on failure.
		'''
		from typerig.core.objects.node import node_types

		nodes = contour.nodes
		node_a = nodes[idx_a]
		node_b = nodes[idx_b]

		if not node_a.is_on or not node_b.is_on or node_a is node_b:
			return None

		seg_in_a = node_a.prev_on.segment
		seg_out_b = node_b.segment

		if seg_in_a is None or seg_out_b is None:
			return None

		tangent_a_pt = _segment_forward_tangent(seg_in_a, at_start=False)
		tangent_b_pt = _segment_forward_tangent(seg_out_b, at_start=True)

		if tangent_a_pt is None or tangent_b_pt is None:
			return None

		# Radius derived from the original chord A-B (not from the post-shortening
		# chord, matching FL convention — keeps r self-consistent for italics).
		import math
		dx = node_b.point.x - node_a.point.x
		dy = node_b.point.y - node_a.point.y
		chord_len = math.hypot(dx, dy)
		if chord_len < 1e-6:
			return None
		r = chord_len / 2.0

		Cls = node_a.__class__

		# keep_length=True: insert two new on-curves at distance r INSIDE the
		# stem segments, then use those as the new cap corners. The original
		# A, B (and any cap interior) are removed afterward.
		if keep_length:
			# Compute parametric times at distance r from the cap-end of each stem
			if isinstance(seg_in_a, CubicBezier):
				t_in_a = seg_in_a.solve_distance_end(r, 0.001)
			else:  # Line
				if seg_in_a.length < r:
					return None
				t_in_a = 1.0 - (r / seg_in_a.length)

			if isinstance(seg_out_b, CubicBezier):
				t_out_b = seg_out_b.solve_distance_start(r, 0.001)
			else:
				if seg_out_b.length < r:
					return None
				t_out_b = r / seg_out_b.length

			if not (0.0 < t_in_a < 1.0) or not (0.0 < t_out_b < 1.0):
				return None

			# Insert A' on stem-into-A at t_in_a (before A). Capture the parent
			# reference BEFORE insertion — after insertion, node_a.prev_on walks
			# back to the newly-inserted A', so node_a.prev_on.next_on would
			# return node_a itself. Holding the parent ref keeps the lookup
			# pointing at the actual inserted on-curve.
			parent_a = node_a.prev_on
			parent_a.insert_after(t_in_a)
			a_prime = parent_a.next_on
			# Insert B' on stem-out-of-B at t_out_b (after B). node_b doesn't move,
			# so node_b.next_on correctly returns the inserted on-curve.
			node_b.insert_after(t_out_b)
			b_prime = node_b.next_on

			# New cap corners and the geometry that drives the circular arc
			pa_pt = a_prime.point
			pb_pt = b_prime.point
			pa = complex(pa_pt.x, pa_pt.y)
			pb = complex(pb_pt.x, pb_pt.y)

			# Tangents at the new corners — read from the SHORTENED stem segments.
			seg_in_a_short = a_prime.prev_on.segment
			seg_out_b_short = b_prime.segment
			tan_a_short = _segment_forward_tangent(seg_in_a_short, at_start=False) if seg_in_a_short else tangent_a_pt
			tan_b_short = _segment_forward_tangent(seg_out_b_short, at_start=True) if seg_out_b_short else tangent_b_pt
			t_a = complex((tan_a_short or tangent_a_pt).x, (tan_a_short or tangent_a_pt).y)
			t_b = complex((tan_b_short or tangent_b_pt).x, (tan_b_short or tangent_b_pt).y)

			outward = compute_cap_outward_direction(t_a, t_b, pa, pb)
			arc = compute_cap_round_arc(pa, pb, outward, curvature=curvature)
			if arc is None:
				return None
			h_a_out, h_tip_in, p_tip, h_tip_out, h_b_in = arc

			# Now remove everything between a_prime and b_prime (exclusive),
			# i.e. the original A, B, and any prior cap interior, plus the
			# segment off-curves that were on the cap-side of A and B.
			_remove_inclusive_range_forward(a_prime.next, b_prime)

			# Insert the round cap interior between a_prime and b_prime.
			insert_at = a_prime.idx + 1
			contour.insert(insert_at + 0, Cls((h_a_out.real,  h_a_out.imag),  type=node_types['curve']))
			contour.insert(insert_at + 1, Cls((h_tip_in.real, h_tip_in.imag), type=node_types['curve']))
			new_tip = Cls((p_tip.real, p_tip.imag), type=node_types['on'], smooth=True)
			contour.insert(insert_at + 2, new_tip)
			contour.insert(insert_at + 3, Cls((h_tip_out.real, h_tip_out.imag), type=node_types['curve']))
			contour.insert(insert_at + 4, Cls((h_b_in.real,    h_b_in.imag),    type=node_types['curve']))

			a_prime.smooth = True
			b_prime.smooth = True

			return new_tip

		# keep_length=False: original behavior — cap extends past chord A-B.
		pa = complex(node_a.point.x, node_a.point.y)
		pb = complex(node_b.point.x, node_b.point.y)
		t_a = complex(tangent_a_pt.x, tangent_a_pt.y)
		t_b = complex(tangent_b_pt.x, tangent_b_pt.y)

		outward = compute_cap_outward_direction(t_a, t_b, pa, pb)
		arc = compute_cap_round_arc(pa, pb, outward, curvature=curvature)
		if arc is None:
			return None
		h_a_out, h_tip_in, p_tip, h_tip_out, h_b_in = arc

		_remove_inclusive_range_forward(node_a.next, node_b)
		insert_at = node_a.idx + 1
		contour.insert(insert_at + 0, Cls((h_a_out.real,  h_a_out.imag),  type=node_types['curve']))
		contour.insert(insert_at + 1, Cls((h_tip_in.real, h_tip_in.imag), type=node_types['curve']))
		new_tip = Cls((p_tip.real, p_tip.imag), type=node_types['on'], smooth=True)
		contour.insert(insert_at + 2, new_tip)
		contour.insert(insert_at + 3, Cls((h_tip_out.real, h_tip_out.imag), type=node_types['curve']))
		contour.insert(insert_at + 4, Cls((h_b_in.real,    h_b_in.imag),    type=node_types['curve']))

		node_a.smooth = True
		node_b.smooth = True

		return new_tip

	@staticmethod
	def cap_angular(contour, idx_a, idx_b):
		'''Build a pointed (miter) cap between two stem-corner nodes.

		Extends the two stem tangents from A and B until they intersect; the
		intersection becomes the cap tip. Single sharp on-curve replacing any
		existing cap interior. Returns None if the tangents are parallel (no
		well-defined tip).

		Arguments:
			contour : Contour
			idx_a   : int — first stem corner
			idx_b   : int — second stem corner

		Returns:
			Node or None — the tip on-curve.
		'''
		from typerig.core.objects.node import node_types

		nodes = contour.nodes
		node_a = nodes[idx_a]
		node_b = nodes[idx_b]

		if not node_a.is_on or not node_b.is_on or node_a is node_b:
			return None

		seg_in_a = node_a.prev_on.segment
		seg_out_b = node_b.segment

		if seg_in_a is None or seg_out_b is None:
			return None

		tangent_a_pt = _segment_forward_tangent(seg_in_a, at_start=False)
		tangent_b_pt = _segment_forward_tangent(seg_out_b, at_start=True)

		if tangent_a_pt is None or tangent_b_pt is None:
			return None

		pa = complex(node_a.point.x, node_a.point.y)
		pb = complex(node_b.point.x, node_b.point.y)
		t_a = complex(tangent_a_pt.x, tangent_a_pt.y)
		t_b = complex(tangent_b_pt.x, tangent_b_pt.y)

		tip = compute_cap_angular_tip(pa, pb, t_a, t_b)

		if tip is None:
			return None

		# Remove existing cap interior
		_remove_inclusive_range_forward(node_a.next, node_b)

		Cls = node_a.__class__
		new_tip = Cls((tip.real, tip.imag), type=node_types['on'], smooth=False)
		contour.insert(node_a.idx + 1, new_tip)

		return new_tip

	@staticmethod
	def cap_rebuild(contour, node_indices, target='butt'):
		'''Universal "flatten an existing cap" — collapses any cap region back to
		a straight butt cut.

		Detects the two boundary on-curves at the ends of the selection range
		(these are the cap-corner stem ends), then runs cap_butt against them.
		Works on any contiguous selection — the previous fixed-7-node restriction
		of the FL implementation is gone.

		Arguments:
			contour       : Contour
			node_indices  : iterable[int] — indices of selected nodes inside the cap
			target        : str — only 'butt' is implemented currently. Reserved
				for future 'round'/'angular' rebuild targets.

		Returns:
			Node or None — the new on-curve replacing the cap, or None on failure.
		'''
		if target != 'butt':
			return None

		nodes = contour.nodes
		selected_on = [nodes[i] for i in sorted(node_indices) if nodes[i].is_on]

		if len(selected_on) < 2:
			return None

		# The two boundary on-curves — first and last in contour order
		node_a = selected_on[0]
		node_b = selected_on[-1]

		# Try the perpendicular butt cut first (handles italic caps).
		result = NodeActions.cap_butt(contour, node_a.idx, node_b.idx, side='auto')
		if result is not None:
			return result

		# Fallback: cap is already perpendicular to the stem (or the geometry is
		# degenerate). Just remove the interior and keep A, B as the flat-cap corners.
		_remove_inclusive_range_forward(node_a.next, node_b)
		node_a.smooth = False
		node_b.smooth = False
		return node_a

	# -- Curve alignment --------------------------------------------------------
	@staticmethod
	def make_collinear(contour, node_indices, mode=-1, equalize=False, target_width=None):
		'''Align two selected curve segments to be collinear at their handle
		directions — typically the two parallel-stem-side curves of a stem
		so the stem starts and ends straight.

		Selection model:
		  - A "selected curve" is an on-curve A whose forward segment is a
		    CubicBezier, and whose 4 segment nodes (A, bcp_out, bcp_in, next_on)
		    are ALL in node_indices.
		  - Exactly 2 selected curves are required. With 0, 1, or 3+, the
		    operation returns 0 (no-op).
		  - The walk uses contour.nodes order, so a selection that wraps past
		    the contour start is handled correctly (no hash-dedup, no
		    first-and-last heuristic — the previous bug source).

		Direction swapping is delegated to CubicBezier.make_collinear, which
		uses match_direction_to to detect and handle parallel-stem curves
		drawn in opposite contour directions.

		Arguments:
			contour       : Contour
			node_indices  : iterable[int] — selected node indices
			mode          : int — 0 = lock to first selected curve,
			                       1 = lock to second,
			                      -1 = average (default)
			equalize      : bool — equalize stem width to target_width
			target_width  : float | None — width for equalize; None = current average

		Returns:
			int — number of curve pairs aligned (0 or 1).
		'''
		selected = set(node_indices)
		nodes = contour.nodes

		selected_curves = []   # list of (start_on_node, CubicBezier segment)

		for node in nodes:
			if not node.is_on or node.idx not in selected:
				continue

			seg = node.segment
			if not isinstance(seg, CubicBezier):
				continue

			end_on = node.next_on
			if end_on is None or end_on.idx not in selected:
				continue

			# Walk between node and end_on collecting off-curves
			bcps = []
			cursor = node.next
			guard = 0
			while cursor is not None and cursor is not end_on and guard < 8:
				if not cursor.is_on:
					bcps.append(cursor)
				cursor = cursor.next
				guard += 1

			if len(bcps) != 2:
				continue
			if not all(b.idx in selected for b in bcps):
				continue

			selected_curves.append((node, seg))

		if len(selected_curves) != 2:
			return 0

		(start_a, curve_a), (start_b, curve_b) = selected_curves

		new_a, new_b = curve_a.make_collinear(
			curve_b, mode=mode, equalize=equalize, target_width=target_width
		)

		# Write new control points back to the contour
		def _apply(start_on, new_curve):
			bcp1 = start_on.next
			bcp2 = bcp1.next
			end_on = bcp2.next
			start_on.point = new_curve.p0
			bcp1.point = new_curve.p1
			bcp2.point = new_curve.p2
			end_on.point = new_curve.p3

		_apply(start_a, new_a)
		_apply(start_b, new_b)

		return 1

	@staticmethod
	def make_monoline(contour, node_indices, target_width=None, preserve_taper=False):
		'''Regularize two selected curve segments as +/- offsets of their
		shared control-polygon median (monoline-pen model).

		Selection model is identical to make_collinear: exactly 2 selected
		curves, each consisting of A, bcp_out, bcp_in, next_on all in
		node_indices. Returns 0 (no-op) for any other selection count.

		Direction swapping is delegated to CubicBezier.make_monoline, which
		uses match_direction_to to handle parallel-stem curves drawn in
		opposite contour directions.

		Arguments:
			contour        : Contour
			node_indices   : iterable[int] - selected node indices
			target_width   : float | None - uniform stem width;
			                 None = average of the perpendicular widths
			                 measured at the two endpoints
			preserve_taper : bool - if True, keep separate widths at each end

		Returns:
			int - number of curve pairs aligned (0 or 1).
		'''
		selected = set(node_indices)
		nodes = contour.nodes

		selected_curves = []   # list of (start_on_node, CubicBezier segment)

		for node in nodes:
			if not node.is_on or node.idx not in selected:
				continue

			seg = node.segment
			if not isinstance(seg, CubicBezier):
				continue

			end_on = node.next_on
			if end_on is None or end_on.idx not in selected:
				continue

			# Walk between node and end_on collecting off-curves
			bcps = []
			cursor = node.next
			guard = 0
			while cursor is not None and cursor is not end_on and guard < 8:
				if not cursor.is_on:
					bcps.append(cursor)
				cursor = cursor.next
				guard += 1

			if len(bcps) != 2:
				continue
			if not all(b.idx in selected for b in bcps):
				continue

			selected_curves.append((node, seg))

		if len(selected_curves) != 2:
			return 0

		(start_a, curve_a), (start_b, curve_b) = selected_curves

		new_a, new_b = curve_a.make_monoline(
			curve_b, target_width=target_width, preserve_taper=preserve_taper
		)

		def _apply(start_on, new_curve):
			bcp1 = start_on.next
			bcp2 = bcp1.next
			end_on = bcp2.next
			start_on.point = new_curve.p0
			bcp1.point = new_curve.p1
			bcp2.point = new_curve.p2
			end_on.point = new_curve.p3

		_apply(start_a, new_a)
		_apply(start_b, new_b)

		return 1

	# -- Node alignment ---------------------------------------------------------
	@staticmethod
	def nodes_align(nodes, mode='L'):
		'''Align nodes to a computed target based on the alignment mode.

		Arguments:
			nodes (list[Node]): The nodes to align.
			mode (str): Alignment mode. One of:
				'L' - Align to leftmost X
				'R' - Align to rightmost X
				'T' - Align to topmost Y
				'B' - Align to bottommost Y
				'C' - Align to horizontal center of selection
				'E' - Align to vertical center of selection
				'BBoxCenterX' - Align to X center of bounding box
				'BBoxCenterY' - Align to Y center of bounding box
				'peerCenterX' - Align each node to midpoint of its prev/next on-curve X
				'peerCenterY' - Align each node to midpoint of its prev/next on-curve Y
				'Y' - Align to imaginary line between Y-min and Y-max of selection (project X)
				'X' - Align to imaginary line between X-min and X-max of selection (project Y)

		Returns:
			bool: True if any nodes were moved.
		'''
		if not nodes:
			return False

		moved = False

		# - Selection-relative alignment modes
		if mode == 'L':
			target_x = min(n.x for n in nodes)
			for node in nodes:
				if node.x != target_x:
					node.smart_reloc(target_x, node.y)
					moved = True

		elif mode == 'R':
			target_x = max(n.x for n in nodes)
			for node in nodes:
				if node.x != target_x:
					node.smart_reloc(target_x, node.y)
					moved = True

		elif mode == 'T':
			target_y = max(n.y for n in nodes)
			for node in nodes:
				if node.y != target_y:
					node.smart_reloc(node.x, target_y)
					moved = True

		elif mode == 'B':
			target_y = min(n.y for n in nodes)
			for node in nodes:
				if node.y != target_y:
					node.smart_reloc(node.x, target_y)
					moved = True

		elif mode == 'C':
			min_x = min(n.x for n in nodes)
			max_x = max(n.x for n in nodes)
			target_x = (min_x + max_x) / 2.
			for node in nodes:
				if node.x != target_x:
					node.smart_reloc(target_x, node.y)
					moved = True

		elif mode == 'E':
			min_y = min(n.y for n in nodes)
			max_y = max(n.y for n in nodes)
			target_y = (min_y + max_y) / 2.
			for node in nodes:
				if node.y != target_y:
					node.smart_reloc(node.x, target_y)
					moved = True

		elif mode == 'BBoxCenterX':
			bounds = Bounds([n.tuple for n in nodes])
			target_x = bounds.x + bounds.width / 2.
			for node in nodes:
				if node.x != target_x:
					node.smart_reloc(target_x, node.y)
					moved = True

		elif mode == 'BBoxCenterY':
			bounds = Bounds([n.tuple for n in nodes])
			target_y = bounds.y + bounds.height / 2.
			for node in nodes:
				if node.y != target_y:
					node.smart_reloc(node.x, target_y)
					moved = True

		elif mode == 'peerCenterX':
			for node in nodes:
				if node.is_on:
					target_x = node.x + (node.prev_on.x + node.next_on.x - 2 * node.x) / 2.
					if node.x != target_x:
						node.smart_reloc(target_x, node.y)
						moved = True

		elif mode == 'peerCenterY':
			for node in nodes:
				if node.is_on:
					target_y = node.y + (node.prev_on.y + node.next_on.y - 2 * node.y) / 2.
					if node.y != target_y:
						node.smart_reloc(node.x, target_y)
						moved = True

		elif mode == 'Y':
			# - Align to imaginary line between Y-min and Y-max nodes (project onto X)
			min_node = min(nodes, key=lambda n: n.y)
			max_node = max(nodes, key=lambda n: n.y)
			target_line = Vector(min_node.point, max_node.point)

			for node in nodes:
				new_x = target_line.solve_x(node.y)
				if node.x != new_x:
					node.smart_reloc(new_x, node.y)
					moved = True

		elif mode == 'X':
			# - Align to imaginary line between X-min and X-max nodes (project onto Y)
			min_node = min(nodes, key=lambda n: n.x)
			max_node = max(nodes, key=lambda n: n.x)
			target_line = Vector(min_node.point, max_node.point)

			for node in nodes:
				new_y = target_line.solve_y(node.x)
				if node.y != new_y:
					node.smart_reloc(node.x, new_y)
					moved = True

		return moved

	@staticmethod
	def nodes_align_to_target(nodes, target, align=(True, True), smart=True):
		'''Align nodes to an explicit target (Point, Node, or Line/Vector).

		Arguments:
			nodes (list[Node]): Nodes to align.
			target (Point, Node, Line, or Vector): Alignment target.
			align (tuple(bool, bool)): (Align_X, Align_Y).
			smart (bool): If True, use smart_reloc to move adjacent BCPs.

		Returns:
			bool: True if any nodes were moved.
		'''
		moved = False

		for node in nodes:
			old_x, old_y = node.x, node.y
			node.align_to(target, align, smart)

			if node.x != old_x or node.y != old_y:
				moved = True

		return moved

	# -- Slope tools ------------------------------------------------------------
	@staticmethod
	def slope_from_nodes(node_a, node_b):
		'''Compute the slope between two nodes.

		Arguments:
			node_a (Node): First node.
			node_b (Node): Second node.

		Returns:
			float: The slope value.
		'''
		return Vector(node_a.point, node_b.point).slope

	@staticmethod
	def angle_from_nodes(node_a, node_b):
		'''Compute the angle between two nodes.

		Arguments:
			node_a (Node): First node.
			node_b (Node): Second node.

		Returns:
			float: The angle in degrees.
		'''
		return Vector(node_a.point, node_b.point).angle

	@staticmethod
	def slope_apply(nodes, slope, mode=(False, False)):
		'''Apply a slope to the selection by constructing a target vector
		and aligning nodes to it.

		Arguments:
			nodes (list[Node]): Nodes to align.
			slope (float): The slope value to apply.
			mode (tuple(bool, bool)): (use_max_y, flip_slope).
				use_max_y=False: vector from min_y to max_y node.
				use_max_y=True: vector from max_y to min_y node.
				flip_slope: negate the slope before applying.

		Returns:
			bool: True if any nodes were moved.
		'''
		if not nodes:
			return False

		use_max, flip = mode

		if use_max:
			target_vector = Vector(
				max(nodes, key=lambda n: n.y).point,
				min(nodes, key=lambda n: n.y).point
			)
		else:
			target_vector = Vector(
				min(nodes, key=lambda n: n.y).point,
				max(nodes, key=lambda n: n.y).point
			)

		target_vector.slope = -slope if flip else slope

		moved = False
		for node in nodes:
			old_x = node.x
			node.align_to(target_vector, (True, False))
			if node.x != old_x:
				moved = True

		return moved

	# -- Node movement ----------------------------------------------------------
	@staticmethod
	def nodes_move(nodes, offset_x, offset_y, method='MOVE', angle=0., slope=None, bounds=None):
		'''Move nodes using different movement strategies.

		Arguments:
			nodes (list[Node]): Nodes to move.
			offset_x (float): Horizontal offset. If bounds is provided, treated
				as a percentage of the bounding box width.
			offset_y (float): Vertical offset. Same percentage interpretation
				if bounds is provided.
			method (str): Movement strategy. One of:
				'MOVE'  - Simple shift of all nodes.
				'SMART' - Shift on-curve nodes and their adjacent BCPs.
				'LERP'  - Interpolated nudge (preserves curve shape).
				'SLANT' - Move in italic/slanted space at given angle.
				'SLOPE' - Move along a user-defined slope angle.
			angle (float): Italic angle in degrees (used by SLANT method).
			slope (float or None): Slope angle in degrees (used by SLOPE method).
			bounds (Bounds or None): If provided, offset_x/offset_y are treated
				as percentages of the bounding box width/height.

		Returns:
			bool: True if any nodes were moved.
		'''
		if not nodes:
			return False

		moved = False

		for node in nodes:
			# - Calculate actual offset
			if bounds is not None:
				dx, dy = _scale_offset(node, offset_x, offset_y, bounds.width, bounds.height)
			else:
				dx, dy = offset_x, offset_y

			if method == 'MOVE':
				node.shift(dx, dy)
				moved = True

			elif method == 'SMART':
				if node.is_on:
					node.smart_shift(dx, dy)
					moved = True

			elif method == 'LERP':
				if node.is_on:
					node.lerp_shift(dx, dy)
					moved = True

			elif method == 'SLANT':
				if angle != 0.:
					node.slant_shift(dx, dy, angle)
				else:
					node.smart_shift(dx, dy)
				moved = True

			elif method == 'SLOPE':
				if slope is not None:
					node.slant_shift(dx, dy, -90 + slope)
					moved = True

		return moved
