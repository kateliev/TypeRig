# MODULE: TypeRig / Core / Actions / Contour
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.contour import Contour
from typerig.core.objects.shape import Shape
from typerig.core.objects.point import Point
from typerig.core.objects.utils import Bounds

# - Init ------------------------------------------------------------------------
__version__ = '1.0'

# - Actions ---------------------------------------------------------------------
class ContourActions(object):
	'''Collection of contour-related actions operating on the TypeRig Core API.

	All methods are static. They operate directly on Contour/Shape objects
	and return True on success, False on failure or no-op.
	'''

	# -- Basic contour tools ----------------------------------------------------
	@staticmethod
	def contour_close(contour):
		'''Close an open contour.

		Arguments:
			contour (Contour): The contour to close.

		Returns:
			bool: True if the contour was closed, False if already closed.
		'''
		if contour.closed:
			return False

		contour.closed = True
		return True

	@staticmethod
	def contour_open(contour):
		'''Open a closed contour.

		Arguments:
			contour (Contour): The contour to open.

		Returns:
			bool: True if the contour was opened, False if already open.
		'''
		if not contour.closed:
			return False

		contour.closed = False
		return True

	# -- Start point tools ------------------------------------------------------
	@staticmethod
	def contour_set_start(contour, node_index):
		'''Set the start point of a contour to the given on-curve node index.

		Arguments:
			contour (Contour): The contour to operate on.
			node_index (int): Index of the on-curve node to set as start.

		Returns:
			bool: True if the start point was changed.
		'''
		if node_index < 0 or node_index >= len(contour.nodes):
			return False

		node = contour.nodes[node_index]

		if not node.is_on:
			return False

		contour.set_start(node_index)
		return True

	@staticmethod
	def contour_set_start_next(contour, forward=True):
		'''Move the start point to the next (or previous) on-curve node.

		Arguments:
			contour (Contour): The contour to operate on.
			forward (bool): If True, move to the next on-curve node;
				if False, move to the previous one.

		Returns:
			bool: True if the start point was changed.
		'''
		nodes = contour.nodes

		if not nodes:
			return False

		search_nodes = nodes[1:] if forward else list(reversed(nodes[1:]))

		for i, node in enumerate(search_nodes):
			if node.is_on:
				# - Find original index in contour
				original_index = nodes.index(node)
				contour.set_start(original_index)
				return True

		return False

	@staticmethod
	def contour_smart_start(contour, control=(0, 0)):
		'''Set the start point to the on-curve node closest to the given
		corner of the bounding box.

		Arguments:
			contour (Contour): The contour to operate on.
			control (tuple(int, int)): Corner selection:
				(0, 0) - Bottom-Left
				(0, 1) - Top-Left
				(1, 0) - Bottom-Right
				(1, 1) - Top-Right

		Returns:
			bool: True if the start point was changed.
		'''
		on_nodes = [(i, node) for i, node in enumerate(contour.nodes) if node.is_on]

		if not on_nodes:
			return False

		if control == (0, 0):		# BL
			criteria = lambda item: (item[1].y, item[1].x)
		elif control == (0, 1):		# TL
			criteria = lambda item: (-item[1].y, item[1].x)
		elif control == (1, 0):		# BR
			criteria = lambda item: (item[1].y, -item[1].x)
		elif control == (1, 1):		# TR
			criteria = lambda item: (-item[1].y, -item[1].x)
		else:
			return False

		best_index, _ = sorted(on_nodes, key=criteria)[0]
		contour.set_start(best_index)
		return True

	# -- Winding direction tools ------------------------------------------------
	@staticmethod
	def contour_set_winding(contour, ccw=True):
		'''Set the winding direction of a contour.

		Arguments:
			contour (Contour): The contour to operate on.
			ccw (bool): If True, set counter-clockwise (CCW);
				if False, set clockwise (CW).

		Returns:
			bool: True if the winding was changed.
		'''
		is_cw = contour.get_winding()

		if ccw and is_cw:
			contour.reverse()
			return True
		elif not ccw and not is_cw:
			contour.reverse()
			return True

		return False

	@staticmethod
	def contour_reverse(contour):
		'''Reverse the direction of a contour.

		Arguments:
			contour (Contour): The contour to reverse.

		Returns:
			bool: Always True.
		'''
		contour.reverse()
		return True

	# -- Contour ordering tools -------------------------------------------------
	@staticmethod
	def contour_set_order(shape, sort_direction=0, sort_mode='BL'):
		'''Sort the contours within a shape by their bounding box position.

		Arguments:
			shape (Shape): The shape whose contours will be reordered.
			sort_direction (int): Sort direction (0 = ascending, 1 = descending).
			sort_mode (str): Sort anchor corner. One of:
				'BL' - Bottom-Left
				'TL' - Top-Left
				'BR' - Bottom-Right
				'TR' - Top-Right

		Returns:
			bool: True if any contours were reordered.
		'''
		if len(shape.contours) < 2:
			return False

		shape.sort(sort_direction, sort_mode)
		return True

	@staticmethod
	def contour_reverse_order(shape):
		'''Reverse the order of contours within a shape.

		Arguments:
			shape (Shape): The shape whose contour order will be reversed.

		Returns:
			bool: True if the order was reversed.
		'''
		if len(shape.contours) < 2:
			return False

		shape.reverse()
		return True

	# -- Contour alignment tools ------------------------------------------------
	@staticmethod
	def contour_align(contours, mode='CC', align_x='C', align_y='E'):
		'''Align contours to each other or to a computed target.

		Arguments:
			contours (list[Contour]): Contours to align.
			mode (str): Alignment mode. One of:
				'CC' - Align contours to contours (pairwise or to
					selection bounds).
			align_x (str): Horizontal alignment. One of:
				'L' - Left, 'R' - Right, 'C' - Center, 'K' - Keep
			align_y (str): Vertical alignment. One of:
				'B' - Bottom, 'T' - Top, 'E' - Center, 'X' - Keep

		Returns:
			bool: True if any contours were moved.
		'''
		if not contours or len(contours) < 2:
			return False

		# - Determine keep flags
		keep_x = align_x != 'K'
		keep_y = align_y != 'X'

		if not keep_x:
			align_x = 'L'
		if not keep_y:
			align_y = 'B'

		align_mode = align_x + align_y

		if mode == 'CC':
			if len(contours) == 2:
				contours[0].align_to(contours[1], align_mode, (keep_x, keep_y))
			else:
				# - Align all contours to selection bounds center
				all_points = []
				for contour in contours:
					all_points.extend([n.tuple for n in contour.nodes])

				bounds = Bounds(all_points)

				align_map = {
					'L': bounds.x,
					'R': bounds.x + bounds.width,
					'C': bounds.x + bounds.width / 2.,
					'B': bounds.y,
					'T': bounds.y + bounds.height,
					'E': bounds.y + bounds.height / 2.
				}

				target = Point(align_map.get(align_x, 0.), align_map.get(align_y, 0.))

				for contour in contours:
					contour.align_to(target, align_mode, (keep_x, keep_y))

		return True

	@staticmethod
	def contour_distribute_horizontal(contours):
		'''Distribute contours evenly along the horizontal axis.

		Arguments:
			contours (list[Contour]): Contours to distribute (at least 3).

		Returns:
			bool: True if contours were distributed.
		'''
		if len(contours) < 3:
			return False

		# - Sort contours by their left edge
		sorted_contours = sorted(contours, key=lambda c: c.bounds.x)

		# - Calculate total span and individual widths
		all_points = []
		for contour in sorted_contours:
			all_points.extend([n.tuple for n in contour.nodes])

		total_bounds = Bounds(all_points)
		total_width = total_bounds.width

		contour_widths = [c.bounds.width for c in sorted_contours]
		gap = (total_width - sum(contour_widths)) / (len(contour_widths) - 1)

		# - Calculate new X positions
		positions = []
		current_x = total_bounds.x

		for width in contour_widths:
			positions.append(current_x)
			current_x += width + gap

		# - Apply alignment
		for i, contour in enumerate(sorted_contours):
			dx = positions[i] - contour.bounds.x
			if dx != 0.:
				for node in contour.nodes:
					node.x += dx

		return True

	@staticmethod
	def contour_flip(contours, horizontal=True):
		'''Flip (mirror) contours around their collective bounding box centre.

		Arguments:
			contours (list[Contour]): Contours to flip.
			horizontal (bool): If True, flip horizontally (mirror left/right);
				if False, flip vertically (mirror top/bottom).

		Returns:
			bool: True if any contours were flipped.
		'''
		if not contours:
			return False

		all_points = []
		for contour in contours:
			all_points.extend([n.tuple for n in contour.nodes])

		if not all_points:
			return False

		bounds = Bounds(all_points)

		if horizontal:
			cx = bounds.x + bounds.width / 2.
			for contour in contours:
				for node in contour.nodes:
					node.x = 2. * cx - node.x
		else:
			cy = bounds.y + bounds.height / 2.
			for contour in contours:
				for node in contour.nodes:
					node.y = 2. * cy - node.y

		return True

	@staticmethod
	def contour_distribute_vertical(contours):
		'''Distribute contours evenly along the vertical axis.

		Arguments:
			contours (list[Contour]): Contours to distribute (at least 3).

		Returns:
			bool: True if contours were distributed.
		'''
		if len(contours) < 3:
			return False

		# - Sort contours by their bottom edge
		sorted_contours = sorted(contours, key=lambda c: c.bounds.y)

		# - Calculate total span and individual heights
		all_points = []
		for contour in sorted_contours:
			all_points.extend([n.tuple for n in contour.nodes])

		total_bounds = Bounds(all_points)
		total_height = total_bounds.height

		contour_heights = [c.bounds.height for c in sorted_contours]
		gap = (total_height - sum(contour_heights)) / (len(contour_heights) - 1)

		# - Calculate new Y positions
		positions = []
		current_y = total_bounds.y

		for height in contour_heights:
			positions.append(current_y)
			current_y += height + gap

		# - Apply alignment
		for i, contour in enumerate(sorted_contours):
			dy = positions[i] - contour.bounds.y
			if dy != 0.:
				for node in contour.nodes:
					node.y += dy

		return True
