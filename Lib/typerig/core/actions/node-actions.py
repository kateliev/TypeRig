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

# - Init ------------------------------------------------------------------------
__version__ = '1.0'

# - Helpers ---------------------------------------------------------------------
def _scale_offset(node, offset_x, offset_y, width, height):
	'''Calculate scaled offset - coordinates as percent of bounding box dimensions.'''
	new_x = -node.x + width * (float(node.x) / width + offset_x)
	new_y = -node.y + height * (float(node.y) / height + offset_y)
	return (new_x, new_y)

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
	def corner_round(node, rounding_size=5, proportion=None, curvature=None, is_radius=False):
		'''Round a corner at the given on-curve node.

		Arguments:
			node (Node): The on-curve corner node.
			rounding_size (float): Size of the rounding.
			proportion (tuple or None): Proportional handle placement.
			curvature (tuple or None): Hobby curvature parameters (e.g. (1., 1.)).
			is_radius (bool): Interpret rounding_size as radius.

		Returns:
			tuple(Node, Node, Node, Node) or None: The corner segment
				(on, bcp_out, bcp_in, on) or None on failure.
		'''
		if not node.is_on:
			return None

		return node.corner_round(rounding_size, proportion, curvature, is_radius)

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
