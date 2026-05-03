# MODULE: TypeRig / Core / Actions / Curve
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.line import Line

# - Init ------------------------------------------------------------------------
__version__ = '1.0'

# - Actions ---------------------------------------------------------------------
class CurveActions(object):
	'''Collection of curve-related actions operating on the TypeRig Core API.

	All methods are static. They operate directly on Node/Contour objects
	and return True on success, False on failure or no-op.
	'''

	# -- Segment conversion tools -----------------------------------------------
	@staticmethod
	def segment_convert_to_line(contour, node_indices):
		'''Convert curve segments to line segments at the given on-curve
		node indices. Removes the off-curve handles between consecutive
		on-curve nodes.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes whose
				incoming segments will be converted to lines.

		Returns:
			bool: True if at least one segment was converted.
		'''
		converted = False

		for nid in sorted(node_indices, reverse=True):
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			prev_on = node.prev_on

			if prev_on is None:
				continue

			# - Collect off-curve nodes between prev_on and node
			to_remove = []
			cursor = prev_on.next

			while cursor is not None and cursor is not node:
				if not cursor.is_on:
					to_remove.append(cursor)
				cursor = cursor.next

			if to_remove:
				for rm_node in reversed(to_remove):
					rm_node.remove()
				converted = True

		return converted

	@staticmethod
	def segment_convert_to_curve(contour, node_indices):
		'''Convert line segments to curve segments at the given on-curve
		node indices. Inserts two off-curve handles between consecutive
		on-curve nodes at 1/3 and 2/3 of the line.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes whose
				incoming segments will be converted to curves.

		Returns:
			bool: True if at least one segment was converted.
		'''
		converted = False

		for nid in sorted(node_indices, reverse=True):
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			prev_on = node.prev_on

			if prev_on is None:
				continue

			# - Check that segment is currently a line (no off-curves between)
			is_line = True
			cursor = prev_on.next

			while cursor is not None and cursor is not node:
				if not cursor.is_on:
					is_line = False
					break
				cursor = cursor.next

			if not is_line:
				continue

			# - Insert two off-curve handles at 1/3 and 2/3 of the line.
			# insert_before / insert_after on Node take a float 't' parameter, NOT a
			# node — so we capture the insertion index and call contour.insert directly.
			bcp1_x = prev_on.x + (node.x - prev_on.x) / 3.
			bcp1_y = prev_on.y + (node.y - prev_on.y) / 3.
			bcp2_x = prev_on.x + 2. * (node.x - prev_on.x) / 3.
			bcp2_y = prev_on.y + 2. * (node.y - prev_on.y) / 3.

			bcp1 = Node(bcp1_x, bcp1_y, type='curve')
			bcp2 = Node(bcp2_x, bcp2_y, type='curve')

			insert_at = prev_on.idx + 1
			contour.insert(insert_at,     bcp1)   # → prev_on, bcp1, node
			contour.insert(insert_at + 1, bcp2)   # → prev_on, bcp1, bcp2, node

			converted = True

		return converted

	# -- Curve optimization tools -----------------------------------------------
	@staticmethod
	def curve_optimize(contour, node_indices, method='tunni', curvature=(1., 1.), proportion=(0.3, 0.3)):
		'''Optimize curve segments using various algorithms.

		Arguments:
			contour (Contour): The contour to operate on.
			node_indices (list[int]): Indices of on-curve nodes whose
				outgoing segments will be optimized. Both endpoints of
				a segment must be in the selection for it to be processed.
			method (str): Optimization method. One of:
				'tunni' - Eduardo Tunni's proportional handle method.
				'hobby' - John Hobby's mock-curvature smoothness.
				'proportional' - Set handles to proportional lengths.
			curvature (tuple(float, float)): Curvature parameters for
				the Hobby method (alpha, beta).
			proportion (tuple(float, float)): Handle length proportions
				for the proportional method (p0_ratio, p1_ratio).

		Returns:
			bool: True if at least one segment was optimized.
		'''
		optimized = False
		selected_set = set(node_indices)

		for nid in node_indices:
			node = contour.nodes[nid]

			if not node.is_on:
				continue

			segment = node.segment

			if not isinstance(segment, CubicBezier):
				continue

			# - Check that the other endpoint is also selected
			next_on = node.next_on

			if next_on is None:
				continue

			# Use next_on.idx (atom index via self.parent.data) instead of
			# contour.nodes.index(next_on): calling contour.nodes again rebuilds
			# the proxy list as a fresh set of wrapper objects, making the old
			# next_on reference unfindable (ValueError for proxy contours).
			next_on_index = next_on.idx

			if next_on_index not in selected_set:
				continue

			# - Get segment nodes for coordinate update
			seg_nodes = node.segment_nodes

			if seg_nodes is None or len(seg_nodes) != 4:
				continue

			if method == 'tunni':
				result = segment.solve_tunni()

				if result is not None:
					seg_nodes[1].x = result.p1.x
					seg_nodes[1].y = result.p1.y
					seg_nodes[2].x = result.p2.x
					seg_nodes[2].y = result.p2.y
					optimized = True

			elif method == 'hobby':
				result = segment.solve_hobby(curvature)

				if result is not None:
					seg_nodes[1].x = result.p1.x
					seg_nodes[1].y = result.p1.y
					seg_nodes[2].x = result.p2.x
					seg_nodes[2].y = result.p2.y
					optimized = True

			elif method == 'proportional':
				# - Set handle lengths as proportion of chord length
				chord = Line(segment.p0, segment.p3)
				chord_len = chord.length

				if chord_len > 0.:
					p0_len = chord_len * proportion[0]
					p1_len = chord_len * proportion[1]

					# - Direction from on-curve to existing handle
					dx1 = segment.p1.x - segment.p0.x
					dy1 = segment.p1.y - segment.p0.y
					len1 = (dx1 ** 2 + dy1 ** 2) ** 0.5

					dx2 = segment.p2.x - segment.p3.x
					dy2 = segment.p2.y - segment.p3.y
					len2 = (dx2 ** 2 + dy2 ** 2) ** 0.5

					if len1 > 0. and len2 > 0.:
						seg_nodes[1].x = segment.p0.x + dx1 / len1 * p0_len
						seg_nodes[1].y = segment.p0.y + dy1 / len1 * p0_len
						seg_nodes[2].x = segment.p3.x + dx2 / len2 * p1_len
						seg_nodes[2].y = segment.p3.y + dy2 / len2 * p1_len
						optimized = True

		return optimized

	# -- Hobby curvature tools --------------------------------------------------
	@staticmethod
	def hobby_curvature_get(contour, node_index):
		'''Get the Hobby curvature coefficients for the curve segment
		starting at the given on-curve node.

		Arguments:
			contour (Contour): The contour to query.
			node_index (int): Index of the on-curve node at the start
				of the segment.

		Returns:
			tuple(complex, complex) or None: The (alpha, beta) curvature
				coefficients, or None if the segment is not a cubic curve.
		'''
		node = contour.nodes[node_index]

		if not node.is_on:
			return None

		segment = node.segment

		if not isinstance(segment, CubicBezier):
			return None

		return segment.solve_hobby_curvature()

	@staticmethod
	def hobby_curvature_apply(contour, node_index, curvature):
		'''Apply Hobby curvature coefficients to the curve segment
		starting at the given on-curve node.

		Arguments:
			contour (Contour): The contour to operate on.
			node_index (int): Index of the on-curve node at the start
				of the segment.
			curvature (tuple(float, float)): The (alpha, beta) curvature
				coefficients to apply.

		Returns:
			bool: True if the curvature was applied.
		'''
		node = contour.nodes[node_index]

		if not node.is_on:
			return False

		segment = node.segment

		if not isinstance(segment, CubicBezier):
			return False

		seg_nodes = node.segment_nodes

		if seg_nodes is None or len(seg_nodes) != 4:
			return False

		result = segment.solve_hobby(curvature)

		if result is not None:
			seg_nodes[1].x = result.p1.x
			seg_nodes[1].y = result.p1.y
			seg_nodes[2].x = result.p2.x
			seg_nodes[2].y = result.p2.y
			return True

		return False

	@staticmethod
	def hobby_curvature_copy_paste(source_contour, source_index, target_contour, target_index, swap=False):
		'''Copy Hobby curvature from one segment and apply it to another.

		Arguments:
			source_contour (Contour): The contour containing the source segment.
			source_index (int): Index of the on-curve node at the start
				of the source segment.
			target_contour (Contour): The contour containing the target segment.
			target_index (int): Index of the on-curve node at the start
				of the target segment.
			swap (bool): If True, swap alpha and beta before applying.

		Returns:
			bool: True if the curvature was transferred.
		'''
		curvature = CurveActions.hobby_curvature_get(source_contour, source_index)

		if curvature is None:
			return False

		if swap:
			curvature = (curvature[1], curvature[0])

		return CurveActions.hobby_curvature_apply(target_contour, target_index, curvature)
