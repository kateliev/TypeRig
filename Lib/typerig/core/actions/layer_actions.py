# MODULE: TypeRig / Core / Actions / Layer
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function, division

import copy

from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour

# - Init ------------------------------------------------------------------------
__version__ = '1.1'

# - Actions ---------------------------------------------------------------------
class LayerActions(object):
	'''Collection of layer-related actions operating on the TypeRig Core API.

	All methods are static. They operate directly on Layer/Shape objects
	and return True on success, False on failure or no-op.
	'''

	# -- Layer: Basic tools -----------------------------------------------------
	@staticmethod
	def layer_add(parent_container, name='New Layer'):
		'''Add a new empty layer.

		Arguments:
			parent_container: The container (e.g., Glyph) that holds layers.
				Must support .append() for Layer objects.
			name (str): Name for the new layer.

		Returns:
			Layer: The newly created layer.
		'''
		new_layer = Layer(name=name)
		parent_container.append(new_layer)
		return new_layer

	@staticmethod
	def layer_duplicate(source_layer, suffix='_copy'):
		'''Create a deep copy of a layer with a new name.

		Arguments:
			source_layer (Layer): The layer to duplicate.
			suffix (str): Suffix to append to the layer name.

		Returns:
			Layer: The duplicated layer.
		'''
		new_layer = copy.deepcopy(source_layer)
		new_layer.name = source_layer.name + suffix
		return new_layer

	@staticmethod
	def layer_delete(parent_container, layer):
		'''Remove a layer from its parent container.

		Arguments:
			parent_container: The container holding the layers.
				Must support .remove() for Layer objects.
			layer (Layer): The layer to remove.

		Returns:
			bool: True if the layer was removed.
		'''
		try:
			parent_container.remove(layer)
			return True
		except (ValueError, AttributeError):
			return False

	# -- Layer: Content tools ---------------------------------------------------
	@staticmethod
	def layer_copy_shapes(source_layer, target_layer, clean_target=False):
		'''Copy all shapes from one layer to another.

		Arguments:
			source_layer (Layer): The layer to copy shapes from.
			target_layer (Layer): The layer to copy shapes to.
			clean_target (bool): If True, remove existing shapes from
				the target layer before copying.

		Returns:
			bool: True if shapes were copied.
		'''
		if not source_layer.shapes:
			return False

		if clean_target:
			target_layer.data = []

		for shape in source_layer.shapes:
			new_shape = copy.deepcopy(shape)
			target_layer.append(new_shape)

		return True

	@staticmethod
	def layer_copy_metrics(source_layer, target_layer, mode='ADV'):
		'''Copy metrics (advance width, LSB, RSB) from one layer to another.

		Arguments:
			source_layer (Layer): The layer to copy metrics from.
			target_layer (Layer): The layer to copy metrics to.
			mode (str): Which metric to copy. One of:
				'ADV' - Advance width.
				'LSB' - Left sidebearing.
				'RSB' - Right sidebearing.
				'ALL' - All metrics.

		Returns:
			bool: True if metrics were copied.
		'''
		copied = False
		mode = mode.upper()

		if 'ADV' in mode or 'ALL' in mode:
			if hasattr(source_layer, 'advance_width') and hasattr(target_layer, 'advance_width'):
				target_layer.advance_width = source_layer.advance_width
				copied = True

			if hasattr(source_layer, 'advance_height') and hasattr(target_layer, 'advance_height'):
				target_layer.advance_height = source_layer.advance_height
				copied = True

		if 'LSB' in mode or 'ALL' in mode:
			if hasattr(source_layer, 'LSB') and hasattr(target_layer, 'LSB'):
				target_layer.LSB = source_layer.LSB
				copied = True

		if 'RSB' in mode or 'ALL' in mode:
			if hasattr(source_layer, 'RSB') and hasattr(target_layer, 'RSB'):
				target_layer.RSB = source_layer.RSB
				copied = True

		return copied

	@staticmethod
	def layer_swap_shapes(layer_a, layer_b):
		'''Swap all shapes between two layers.

		Arguments:
			layer_a (Layer): First layer.
			layer_b (Layer): Second layer.

		Returns:
			bool: True if shapes were swapped.
		'''
		temp_shapes = copy.deepcopy(layer_a.data)
		layer_a.data = copy.deepcopy(layer_b.data)
		layer_b.data = temp_shapes
		return True

	@staticmethod
	def layer_swap_metrics(layer_a, layer_b, mode='ADV'):
		'''Swap metrics between two layers.

		Arguments:
			layer_a (Layer): First layer.
			layer_b (Layer): Second layer.
			mode (str): Which metric to swap. One of:
				'ADV' - Advance width.
				'LSB' - Left sidebearing.
				'RSB' - Right sidebearing.
				'ALL' - All metrics.

		Returns:
			bool: True if metrics were swapped.
		'''
		swapped = False
		mode = mode.upper()

		if 'ADV' in mode or 'ALL' in mode:
			if hasattr(layer_a, 'advance_width') and hasattr(layer_b, 'advance_width'):
				layer_a.advance_width, layer_b.advance_width = layer_b.advance_width, layer_a.advance_width
				swapped = True

			if hasattr(layer_a, 'advance_height') and hasattr(layer_b, 'advance_height'):
				layer_a.advance_height, layer_b.advance_height = layer_b.advance_height, layer_a.advance_height
				swapped = True

		if 'LSB' in mode or 'ALL' in mode:
			if hasattr(layer_a, 'LSB') and hasattr(layer_b, 'LSB'):
				layer_a.LSB, layer_b.LSB = layer_b.LSB, layer_a.LSB
				swapped = True

		if 'RSB' in mode or 'ALL' in mode:
			if hasattr(layer_a, 'RSB') and hasattr(layer_b, 'RSB'):
				layer_a.RSB, layer_b.RSB = layer_b.RSB, layer_a.RSB
				swapped = True

		return swapped

	@staticmethod
	def layer_copy_anchors(source_layer, target_layer, clean_target=False):
		'''Copy anchors from one layer to another. Anchors are unique by name:
		a source anchor replaces a target anchor of the same name.

		Arguments:
			source_layer (Layer): The layer to copy anchors from.
			target_layer (Layer): The layer to copy anchors to.
			clean_target (bool): If True, drop all target anchors first.

		Returns:
			bool: True if anchors were copied.
		'''
		if not source_layer.anchors:
			return False

		detach = lambda a: a.eject() if hasattr(a, 'eject') else copy.deepcopy(a)
		incoming = [detach(a) for a in source_layer.anchors]
		names = set(a.name for a in incoming)
		kept = [] if clean_target else [detach(a) for a in target_layer.anchors if a.name not in names]
		target_layer.anchors = kept + incoming
		return True

	@staticmethod
	def layer_transform(layer, scale_x=100., scale_y=100.,
	                    translate_x=0., translate_y=0.,
	                    rotate=0., skew_x=0., skew_y=0.,
	                    origin='C'):
		'''Apply an affine transform to all nodes and anchors of a layer
		around an origin on the layer bounding box.

		Arguments:
			layer (Layer): The layer to transform.
			scale_x, scale_y (float): Percent scale (100 = identity).
			translate_x, translate_y (float): Translation in font units.
			rotate (float): Rotation in degrees (positive = counter-clockwise).
			skew_x, skew_y (float): Skew angles in degrees.
			origin (str): Bounds.align_matrix code ('BL', 'BM', 'BR', 'TL',
				'TM', 'TR', 'LM', 'C', 'RM') or 'O' for absolute origin (0, 0).

		Returns:
			bool: True if anything was transformed.
		'''
		from typerig.core.objects.transform import Transform
		from typerig.core.objects.utils import Bounds

		nodes = layer.nodes
		if not nodes:
			return False

		if origin == 'O':
			ox, oy = 0., 0.
		else:
			# Bounds of the nodes: Layer.bounds asserts on component shapes
			matrix = Bounds([n.tuple for n in nodes]).align_matrix
			ox, oy = matrix.get(origin, matrix['C'])

		# Chain written in reverse of application order (see ContourActions.contour_transform)
		t = (Transform()
			.translate(ox + float(translate_x), oy + float(translate_y))
			.skew(skew_x, skew_y)
			.rotate(rotate)
			.scale(float(scale_x) / 100., float(scale_y) / 100.)
			.translate(-ox, -oy))

		for node in nodes:
			node.x, node.y = t.applyTransformation(node.x, node.y)

		for anchor in layer.anchors:
			anchor.x, anchor.y = t.applyTransformation(anchor.x, anchor.y)

		return True

	@staticmethod
	def layer_clean_shapes(layer):
		'''Remove all shapes from a layer.

		Arguments:
			layer (Layer): The layer to clean.

		Returns:
			bool: True if any shapes were removed.
		'''
		if not layer.data:
			return False

		layer.data = []
		return True

	# -- Layer: Node coordinate tools -------------------------------------------
	@staticmethod
	def layer_pull_coordinates(source_layer, target_layer, node_indices=None):
		'''Pull (copy) node coordinates from a source layer to a target layer.
		Both layers must have compatible contour structures.

		Arguments:
			source_layer (Layer): The layer to copy coordinates from.
			target_layer (Layer): The layer to copy coordinates to.
			node_indices (list[int] or None): If provided, only copy
				coordinates for nodes at these indices. If None, copy all.

		Returns:
			bool: True if coordinates were copied.
		'''
		source_nodes = source_layer.nodes
		target_nodes = target_layer.nodes

		if len(source_nodes) != len(target_nodes):
			return False

		copied = False

		if node_indices is None:
			for i in range(len(source_nodes)):
				target_nodes[i].x = source_nodes[i].x
				target_nodes[i].y = source_nodes[i].y
				copied = True
		else:
			for i in node_indices:
				if 0 <= i < len(source_nodes):
					target_nodes[i].x = source_nodes[i].x
					target_nodes[i].y = source_nodes[i].y
					copied = True

		return copied

	@staticmethod
	def layer_push_coordinates(source_layer, target_layers, node_indices=None):
		'''Push (copy) node coordinates from a source layer to multiple target layers.

		Arguments:
			source_layer (Layer): The layer to copy coordinates from.
			target_layers (list[Layer]): The layers to copy coordinates to.
			node_indices (list[int] or None): If provided, only copy
				coordinates for nodes at these indices. If None, copy all.

		Returns:
			bool: True if coordinates were copied to at least one layer.
		'''
		pushed = False

		for target_layer in target_layers:
			result = LayerActions.layer_pull_coordinates(source_layer, target_layer, node_indices)

			if result:
				pushed = True

		return pushed
