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
from typerig.core.objects.transform import TransformOrigin

# Map (align_x, align_y) → TransformOrigin matching Bounds.align_matrix keys.
# align_x ∈ {'L','R','C'}; align_y ∈ {'B','T','E'} (after K/X keep-flag handling).
_ALIGN_ORIGIN = {
	('L', 'B'): TransformOrigin.BOTTOM_LEFT,
	('C', 'B'): TransformOrigin.BOTTOM_MIDDLE,
	('R', 'B'): TransformOrigin.BOTTOM_RIGHT,
	('L', 'T'): TransformOrigin.TOP_LEFT,
	('C', 'T'): TransformOrigin.TOP_MIDDLE,
	('R', 'T'): TransformOrigin.TOP_RIGHT,
	('L', 'E'): TransformOrigin.CENTER_LEFT,
	('C', 'E'): TransformOrigin.CENTER,
	('R', 'E'): TransformOrigin.CENTER_RIGHT,
}

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
	def contour_align(contours, mode='CC', align_x='C', align_y='E',
	                  layer_bounds=None, target_node=None,
	                  contours_A=None, contours_B=None):
		'''Align contours to each other or to a computed target.

		Arguments:
			contours (list[Contour]): Contours to align (CC/CL/CN modes).
			mode (str): Alignment mode. One of:
				'CC' - Contour to contour (pairwise or to selection bounds).
				'CL' - Contour to layer bounding box (pass `layer_bounds`).
				'CN' - Contour to a target node (pass `target_node`); the
					first contour in `contours` is assumed to host the
					target and is excluded from the move.
				'AB' - Group A to group B (pass `contours_A`, `contours_B`);
					group A is shifted as a whole so that its origin lands
					on group B's origin.
			align_x (str): 'L' / 'R' / 'C' / 'K' (keep).
			align_y (str): 'B' / 'T' / 'E' / 'X' (keep).
			layer_bounds (Bounds|None): required for mode='CL'.
			target_node (Node|Point|tuple|None): required for mode='CN'.
			contours_A (list[Contour]|None): required for mode='AB'.
			contours_B (list[Contour]|None): required for mode='AB'.

		Returns:
			bool: True if any contours were moved.
		'''
		# - Determine keep flags
		keep_x = align_x != 'K'
		keep_y = align_y != 'X'

		if not keep_x:
			align_x = 'L'
		if not keep_y:
			align_y = 'B'

		origin = _ALIGN_ORIGIN[(align_x, align_y)]
		align_mode = (origin, origin)

		def _bounds_target(bounds):
			x, y = bounds.align_matrix[origin.code]
			return Point(x, y)

		if mode == 'CC':
			if not contours or len(contours) < 2:
				return False

			if len(contours) == 2:
				contours[0].align_to(contours[1], align_mode, (keep_x, keep_y))
			else:
				all_points = []
				for contour in contours:
					all_points.extend([n.tuple for n in contour.nodes])

				target = _bounds_target(Bounds(all_points))

				for contour in contours:
					contour.align_to(target, align_mode, (keep_x, keep_y))

			return True

		if mode == 'CL':
			if not contours or layer_bounds is None:
				return False
			target = _bounds_target(layer_bounds)
			for contour in contours:
				contour.align_to(target, align_mode, (keep_x, keep_y))
			return True

		if mode == 'CN':
			if not contours or target_node is None or len(contours) < 2:
				return False
			# First contour hosts the target node; align the rest.
			target_x = float(target_node.x)
			target_y = float(target_node.y)
			target = Point(target_x, target_y)
			for contour in contours[1:]:
				contour.align_to(target, align_mode, (keep_x, keep_y))
			return True

		if mode == 'AB':
			if not contours_A or not contours_B:
				return False
			a_pts = [n.tuple for c in contours_A for n in c.nodes]
			b_pts = [n.tuple for c in contours_B for n in c.nodes]
			a_origin = _bounds_target(Bounds(a_pts))
			b_origin = _bounds_target(Bounds(b_pts))
			delta_x = (b_origin.x - a_origin.x) if keep_x else 0.
			delta_y = (b_origin.y - a_origin.y) if keep_y else 0.
			for contour in contours_A:
				contour.shift(delta_x, delta_y)
			return True

		return False

	# -- Contour transform tools ------------------------------------------------
	@staticmethod
	def contour_transform(contours, scale_x=100., scale_y=100.,
	                      translate_x=0., translate_y=0.,
	                      rotate=0., skew_x=0., skew_y=0.,
	                      origin='C'):
		'''Apply an affine transform to a group of contours around a shared origin.

		Arguments:
			contours (list[Contour]): Contours to transform.
			scale_x, scale_y (float): Percent scale (100 = identity).
			translate_x, translate_y (float): Translation in font units.
			rotate (float): Rotation in degrees (positive = counter-clockwise).
			skew_x, skew_y (float): Skew angles in degrees.
			origin (str): Origin code from Bounds.align_matrix:
				'BL', 'BM', 'BR', 'TL', 'TM', 'TR', 'LM', 'C', 'RM',
				or 'O' for absolute origin (0, 0).

		Returns:
			bool: True on success.
		'''
		from typerig.core.objects.transform import Transform

		if not contours:
			return False

		# - Compute group origin
		if origin == 'O':
			ox, oy = 0., 0.
		else:
			all_points = []
			for c in contours:
				all_points.extend([n.tuple for n in c.nodes])
			bounds = Bounds(all_points)
			ox, oy = bounds.align_matrix.get(origin, bounds.align_matrix['C'])

		sx = float(scale_x) / 100.
		sy = float(scale_y) / 100.

		# Transform composition note: `self.transform(other)` returns `self ∘ other`,
		# so when the matrix is applied to a point the LATEST chained method runs
		# FIRST against the point. The chain below is therefore written in reverse
		# of the intended application order (translate-to-origin, scale, rotate,
		# skew, translate-back-plus-offset).
		t = (Transform()
			.translate(ox + float(translate_x), oy + float(translate_y))
			.skew(skew_x, skew_y)
			.rotate(rotate)
			.scale(sx, sy)
			.translate(-ox, -oy))

		for contour in contours:
			contour.transform = t
			contour.apply_transform()

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

	# -- Cut / slice / weld -----------------------------------------------------
	@staticmethod
	def contour_slice(shape, selection_triples, expanded=False):
		'''Slice contours at selected on-curve nodes. Mirrors
		``TRContourActionCollector.contour_slice`` (FL) on core objects.

		The first and last triples in `selection_triples` define the cut.
		If they are on the **same contour**, that contour is sliced into two
		closed pieces. If they are on **different contours** of the same shape,
		the two contours are welded into one closed contour at the cut points.

		Arguments:
			shape (Shape): shape whose contours are mutated in place.
			selection_triples (list[tuple]): list of ``(sid, cid, nid)`` —
				same shape that ``eGlyph.selectedAtShapes()`` returns. Only
				the first and last entries are consumed; intermediate entries
				are ignored. All entries must share the same `sid`.
			expanded (bool): if True, offset the cut endpoints visually.

		Returns:
			bool: True if a slice/weld was performed.
		'''
		if not selection_triples or len(selection_triples) < 2:
			return False

		first_sid, first_cid, first_nid = selection_triples[0]
		last_sid, last_cid, last_nid = selection_triples[-1]

		if first_sid != last_sid:
			return False

		contours = list(shape.contours)
		if first_cid >= len(contours) or last_cid >= len(contours):
			return False

		if first_cid != last_cid:
			# Cross-contour: weld two contours into one at the cut points.
			first_contour = contours[first_cid]
			last_contour = contours[last_cid]

			first_parts = first_contour.split(first_nid, expanded=expanded)
			last_parts = last_contour.split(last_nid, expanded=expanded)

			if first_parts is not None and last_parts is not None:
				# Both inputs were already open: weld the returned pieces too.
				first_parts.glue(last_parts)
				shape.contours.append(first_parts)

			first_contour.glue(last_contour)
			shape.contours.remove(last_contour)
			return True

		# Same contour: slice into two closed pieces.
		first_contour = contours[first_cid]
		# Snapshot the last node reference before mutating; its idx is live.
		last_node = first_contour.data[last_nid]

		first_contour.split(first_nid, expanded=expanded)
		cutout = first_contour.split(last_node.idx, expanded=expanded)
		first_contour.closed = True

		if cutout is not None:
			cutout.closed = True
			shape.contours.append(cutout)

		return True

	@staticmethod
	def node_neighbor_pairs(contour, nodes):
		'''Group a list of on-curve nodes into pairs of neighbors via the
		contour's segment traversal. Replaces ``eNode.getNextOn/getPrevOn``
		usage in ``popup-contour-cut.py`` for the auto-align tool.

		Arguments:
			contour (Contour): parent contour the nodes live on.
			nodes (list[Node]): selected on-curve nodes (typically 4 — two
				pairs at a cut junction).

		Returns:
			tuple(list, list): ``(pair_first, pair_second)`` — at most two
			2-element lists of neighbouring nodes. Empty lists when no pair
			can be formed.
		'''
		if len(nodes) < 4:
			return [], []

		pairs = []
		used = set()

		for i, node in enumerate(nodes):
			if i in used:
				continue
			try:
				next_on = node.next_on
				prev_on = node.prev_on
			except (AttributeError, IndexError):
				continue

			for j, other in enumerate(nodes):
				if j in used or i == j:
					continue
				if next_on is other or prev_on is other:
					pairs.append((node, other))
					used.add(i)
					used.add(j)
					break

		if len(pairs) >= 2:
			return list(pairs[0]), list(pairs[1])
		if len(pairs) == 1:
			return list(pairs[0]), []
		return [], []

	@staticmethod
	def junction_align_mode(pair):
		'''Classify a 2-node pair at a cut junction into ``'C'``, ``'T'``,
		or ``'B'`` by inspecting the direction of each node's interior
		segment. 1:1 port of ``popup-contour-cut.py:_auto_align_mode``.

		Arguments:
			pair (list[Node]): two on-curve nodes that are contour neighbors.

		Returns:
			str: ``'C'`` (centre x), ``'T'`` (top y), or ``'B'`` (bottom y).
		'''
		if len(pair) != 2:
			return 'C'

		n1, n2 = pair
		total_dx = 0.0
		total_dy = 0.0
		interior_ys = []

		for node, other in ((n1, n2), (n2, n1)):
			try:
				next_on = node.next_on
				prev_on = node.prev_on
			except (AttributeError, IndexError):
				continue

			interior = None
			if next_on is not None and next_on is not other:
				interior = next_on
			elif prev_on is not None and prev_on is not other:
				interior = prev_on

			if interior is None:
				continue

			total_dx += abs(interior.x - node.x)
			total_dy += abs(interior.y - node.y)
			interior_ys.append(interior.y)

		# Horizontal interior segments → arm side → centre x
		if not interior_ys or total_dx >= total_dy:
			return 'C'

		# Vertical interior segments → stem side
		avg_y_pair = (n1.y + n2.y) / 2.0

		if all(y > avg_y_pair for y in interior_ys):
			return 'B'   # all interior above → junction at bottom
		if all(y < avg_y_pair for y in interior_ys):
			return 'T'   # all interior below → junction at top
		return 'C'       # T-junction: interior on both sides

	@staticmethod
	def contour_pair_align(pair, mode):
		'''Align a 2-node pair at a cut junction.

		Arguments:
			pair (list[Node]): two on-curve nodes.
			mode (str): ``'T'`` (both to max y), ``'B'`` (both to min y),
				``'C'`` (both to mean x).

		Returns:
			bool: True on align, False on no-op.
		'''
		if len(pair) != 2:
			return False

		n1, n2 = pair

		if mode == 'T':
			target_y = max(n1.y, n2.y)
			n1.y = target_y
			n2.y = target_y
		elif mode == 'B':
			target_y = min(n1.y, n2.y)
			n1.y = target_y
			n2.y = target_y
		elif mode == 'C':
			target_x = (n1.x + n2.x) / 2.0
			n1.x = target_x
			n2.x = target_x
		else:
			return False

		return True
