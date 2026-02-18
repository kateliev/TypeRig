# MODULE: TypeRig / Core / Layer (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import math

from typerig.core.objects.atom import Container
from typerig.core.objects.array import PointArray
from typerig.core.objects.point import Point
from typerig.core.objects.node import DirectionalNode
from typerig.core.objects.transform import Transform, TransformOrigin
from typerig.core.objects.utils import Bounds
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour
from typerig.core.objects.sdf import SignedDistanceField
from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class
from typerig.core.func.math import slerp_angle, interpolate_directional

# - Init -------------------------------
__version__ = '0.4.0'

# - Classes -----------------------------
@register_xml_class
class Layer(Container, XMLSerializable): 
	__slots__ = ('name', 'stx', 'sty', 'transform', 'mark', 'advance_width', 'advance_height', 'identifier', 'parent', 'lib', '_sdf')

	XML_TAG = 'layer'
	XML_ATTRS = ['name', 'identifier', 'width', 'height']
	XML_CHILDREN = {'shape': 'shapes'}
	XML_LIB_ATTRS = ['transform', 'stx', 'sty']
	
	def __init__(self, shapes=None, **kwargs):
		factory = kwargs.pop('default_factory', Shape)
		super(Layer, self).__init__(shapes, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		
		self.stx = kwargs.pop('stx', None) 
		self.sty = kwargs.pop('sty', None) 
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', hash(self))
			self.identifier = kwargs.pop('identifier', None)
			self.mark = kwargs.pop('mark', 0)
			self.advance_width = kwargs.pop('width', 0.) 
			self.advance_height = kwargs.pop('height', 1000.) 

		# - SDF cache (not serialized)
		self._sdf = None
	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Shapes={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def sdf(self):
		'''Cached SignedDistanceField for this layer. 
		None if not yet computed. Use compute_sdf() to populate.
		'''
		return self._sdf

	# -- Properties -----------------------------
	@property
	def has_stems(self):
		return self.stx is not None and self.sty is not None

	@property
	def stems(self):
		return (self.stx, self.sty)

	@stems.setter
	def stems(self, other):
		if isinstance(other, (tuple, list)) and len(other) == 2:
			self.stx, self.sty = other

	@property
	def shapes(self):
		return self.data

	@shapes.setter
	def shapes(self, other):
		if isinstance(other, self.__class__):
			self.data = other.data
		elif isinstance(other, (tuple, list)):
			self.data = [self._coerce(item) for item in other]

	@property
	def nodes(self):
		return self._collect('nodes')

	@property
	def contours(self):
		return self._collect('contours')

	@property
	def selected_nodes(self):
		return self._collect('selected_nodes')

	@property
	def selected_indices(self):
		return self._collect('selected_indices')

	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		contour_bounds = [shape.bounds for shape in self.data]
		bounds = sum([[(bound.x, bound.y), (bound.xmax, bound.ymax)] for bound in contour_bounds],[])
		return Bounds(bounds)

	@property
	def signature(self):
		return hash(tuple([node.type for node in self.nodes]))

	@property
	def LSB(self):
		'''Layer's Left sidebearing'''
		return self.bounds.x

	@LSB.setter
	def LSB(self, value):
		delta = value - self.LSB
		self.shift(delta, 0.)

	@property
	def RSB(self):
		'''Layer's Right sidebearing'''
		layer_bounds = self.bounds
		return self.ADV - (layer_bounds.x + layer_bounds.width)

	@RSB.setter
	def RSB(self, value):
		delta = value - self.RSB
		self.ADV += delta

	@property
	def BSB(self):
		'''Layer's Bottom sidebearing'''
		return self.bounds.y

	@BSB.setter
	def BSB(self, value):
		delta = value - self.BSB
		self.shift(0., delta)

	@property
	def TSB(self):
		'''Layer's Top sidebearing'''
		layer_bounds = self.bounds
		return layer_bounds.y + layer_bounds.height

	@TSB.setter
	def TSB(self, value):
		delta = value - self.TSB
		self.VADV += delta

	@property
	def ADV(self):
		'''Layer's Advance width'''
		return self.advance_width

	@ADV.setter
	def ADV(self, value):
		self.advance_width = value

	@property
	def VADV(self):
		'''Layer's Advance height'''
		return self.advance_height

	@VADV.setter
	def VADV(self, value):
		self.advance_height = value

	# - Delta related retrievers -----------
	@property
	def point_array(self):
		return PointArray([node.point for node in self.nodes])

	@point_array.setter
	def point_array(self, other):
		layer_nodes = self.nodes

		if isinstance(other, PointArray) and len(other) == len(layer_nodes):
			for idx in range(len(layer_nodes)):
				layer_nodes[idx].point = other[idx]

	@property
	def anchor_array(self):
		#return [node.tuple for node in self.nodes]
		pass

	@anchor_array.setter
	def anchor_array(self, other):
		'''
		layer_nodes = self.nodes

		if isinstance(other, (tuple, list)) and len(other) == len(layer_nodes):
			for idx in range(len(layer_nodes)):
				layer_nodes[idx].tuple = other[idx]
		'''
		pass

	@property
	def metric_array(self):
		return [(0.,0.), (self.ADV, self.VADV)]

	@metric_array.setter
	def metric_array(self, other):
		if isinstance(other, (tuple, list)) and len(other) == 2 and len(other[1]) == 2:
			#self.ADV, self.VADV = other[1] # Skip VADV for now...
			self.ADV = other[1][0]

	# - Functions --------------------------
	def set_weight(self, wx, wy):
		'''Set x and y weights (a.k.a. stems) for all nodes'''
		for node in self.nodes:
			node.weight.x = wx
			node.weight.y = wy

	def is_compatible(self, other):
		return self.signature == other.signature
	
	# - Transformation --------------------------
	def apply_transform(self):
		for node in self.nodes:
			node.x, node.y = self.transform.applyTransformation(node.x, node.y)

	def shift(self, delta_x, delta_y):
		'''Shift the layer by given amount'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=(TransformOrigin.CENTER, TransformOrigin.CENTER), align=(True, True)):
		'''Align layer to another entity using transformation origins.
		
		Arguments:
			entity (Layer, Point, tuple(x,y)):
				Object to align to

			mode (tuple(TransformOrigin, TransformOrigin)):
				Alignment origins for (self, other). Must use TransformOrigin enum.
				Examples:
				- (TransformOrigin.CENTER, TransformOrigin.CENTER) - align centers
				- (TransformOrigin.BASELINE, TransformOrigin.BASELINE) - align baselines
				- (TransformOrigin.TOP_LEFT, TransformOrigin.BOTTOM_LEFT) - align top to bottom

			align (tuple(bool, bool)):
				Align X, Align Y. Set to False to disable alignment on that axis.
		
		Returns:
			Nothing (modifies layer in place)
			
		Example:
			>>> from typerig.core.objects.transform import TransformOrigin
			>>> 
			>>> # Align layer centers
			>>> layer1.align_to(layer2)  # Uses CENTER by default
			>>> 
			>>> # Align layer1's baseline to layer2's baseline
			>>> layer1.align_to(
			...     layer2,
			...     mode=(TransformOrigin.BASELINE, TransformOrigin.BASELINE)
			... )
			>>> 
			>>> # Align layer1's top-left to a specific point
			>>> layer1.align_to(
			...     Point(100, 200),
			...     mode=(TransformOrigin.TOP_LEFT, None)
			... )
			>>> 
			>>> # Align only X axis (Y stays the same)
			>>> layer1.align_to(
			...     layer2,
			...     mode=(TransformOrigin.CENTER_LEFT, TransformOrigin.CENTER_LEFT),
			...     align=(True, False)
			... )
		'''
		align_matrix = self.bounds.align_matrix
		self_x, self_y = align_matrix[mode[0].code]

		if isinstance(entity, self.__class__):
			other_x, other_y = entity.bounds.align_matrix[mode[1].code]
			delta_x = other_x - self_x if align[0] else 0.
			delta_y = other_y - self_y if align[1] else 0.

		elif isinstance(entity, Point):
			delta_x = entity.x - self_x if align[0] else 0.
			delta_y = entity.y - self_y if align[1] else 0.

		elif isinstance(entity, (tuple, list)):
			delta_x = entity[0] - self_x if align[0] else 0.
			delta_y = entity[1] - self_y if align[1] else 0.

		self.shift(delta_x, delta_y)

	# - Delta --------------------------------
	def lerp_function(self, other):
		if not isinstance(other, self.__class__) and not self.is_compatible(other): return

		t0 = self.point_array
		t1 = other.point_array
	
		def func(tx, ty):
			new_layer = self.clone()
			new_layer.point_array = (t1 - t0) * (tx, ty) + t0
			return new_layer

		return func

	def scale_with_axis(self, virtual_axis, target_width=None, target_height=None, 
						fix_scale_direction=-1, main_attribute='point_array', 
						extrapolate=False, precision=(1.0, 1.0), max_iterations=1000,
						transform_origin=TransformOrigin.BASELINE):
		'''Scale layer to target dimensions using a virtual axis (non-destructive).
		
		IMPORTANT: This method properly handles transformation origins, meaning the 
		specified origin point stays fixed while the glyph scales around it.
		
		Args:
			virtual_axis (dict): Virtual axis dictionary from Glyph.create_virtual_axis()
			target_width (float, optional): Target width. If None, width is not constrained.
			target_height (float, optional): Target height. If None, height is not constrained.
			fix_scale_direction (int): -1=independent x/y, 0=use x for both, 1=use y for both
			main_attribute (str): Main attribute to measure ('point_array' usually)
			extrapolate (bool): Allow extrapolation beyond source layers
			precision (tuple): Starting precision for x and y (default: (1.0, 1.0))
			max_iterations (int): Maximum iterations to prevent infinite loops (default: 1000)
			transform_origin (TransformOrigin): Where to anchor the transformation:
				- TransformOrigin.BASELINE (default): Left sidebearing + baseline (0)
				- TransformOrigin.BOTTOM_LEFT: Bottom-left corner
				- TransformOrigin.BOTTOM_MIDDLE: Bottom-center
				- TransformOrigin.BOTTOM_RIGHT: Bottom-right corner
				- TransformOrigin.CENTER: Absolute center of bounding box
				- TransformOrigin.CENTER_LEFT: Center-left
				- TransformOrigin.CENTER_RIGHT: Center-right
				- TransformOrigin.TOP_LEFT: Top-left corner
				- TransformOrigin.TOP_MIDDLE: Top-center
				- TransformOrigin.TOP_RIGHT: Top-right corner
		
		Returns:
			Layer: New scaled layer with transformation origin preserved
			
		Example:
			>>> from typerig.core.objects.transform import TransformOrigin
			>>> axis = glyph.create_virtual_axis(['Light', 'Regular', 'Bold'])
			>>> 
			>>> # Scale from baseline (typical for type design)
			>>> scaled = glyph.layer('Regular').scale_with_axis(
			...     axis, target_width=600, target_height=700
			... )  # Uses BASELINE by default
			>>> 
			>>> # Scale from center
			>>> centered = glyph.layer('Regular').scale_with_axis(
			...     axis, target_width=600, 
			...     transform_origin=TransformOrigin.CENTER
			... )
			>>> 
			>>> # Scale from bottom-left corner
			>>> corner = glyph.layer('Regular').scale_with_axis(
			...     axis, target_width=600,
			...     transform_origin=TransformOrigin.BOTTOM_LEFT
			... )
		'''
		# Create a copy to work with (non-destructive)
		result_layer = self.clone()
		
		# Validate inputs
		if main_attribute not in virtual_axis:
			raise ValueError('Attribute "{}" not in virtual_axis. Available: {}'.format(
				main_attribute, list(virtual_axis.keys())))
		
		if target_width is None and target_height is None:
			raise ValueError('At least one of target_width or target_height must be specified')
		
		# STEP 1: Get the transformation origin point BEFORE scaling
		source_bounds = result_layer.bounds
		source_origin_x, source_origin_y = source_bounds.align_matrix[transform_origin.code]
		
		# Get initial bounds
		main_array = getattr(result_layer, main_attribute)
		main_bounds = Bounds(main_array.tuple if hasattr(main_array, 'tuple') else main_array)
		
		# Set up targets and sources
		source_width = main_bounds.width
		source_height = main_bounds.height
		
		# If target not specified, use source
		if target_width is None:
			target_width = source_width
		if target_height is None:
			target_height = source_height
		
		# Calculate initial differences
		diff_x = target_width - source_width
		diff_y = target_height - source_height
		prev_diff_x = diff_x
		prev_diff_y = diff_y
		
		# Initialize scales and precisions
		direction = [1, -1][extrapolate]
		precision_x, precision_y = precision
		scale_x = prev_scale_x = 1.
		scale_y = prev_scale_y = 1.
		
		# Storage for processed data
		process_axis = {}
		
		# Iteration counter
		iteration = 0
		
		# STEP 2: Iterative scaling loop (scales from origin 0,0 initially)
		while iteration < max_iterations:
			# Check convergence
			x_converged = abs(round(diff_x)) == 0
			y_converged = abs(round(diff_y)) == 0
			
			if fix_scale_direction != -1:
				# Both must converge
				if x_converged and y_converged:
					break
			else:
				# Either can converge independently
				if x_converged or y_converged:
					if x_converged and target_width != source_width:
						break
					if y_converged and target_height != source_height:
						break
					if x_converged and y_converged:
						break
			
			# Adjust precision if we're oscillating
			if abs(diff_x) > abs(prev_diff_x):
				scale_x = prev_scale_x
				precision_x /= 10
			
			if abs(diff_y) > abs(prev_diff_y):
				scale_y = prev_scale_y
				precision_y /= 10
			
			# Store previous values
			prev_scale_x, prev_diff_x = scale_x, diff_x
			prev_scale_y, prev_diff_y = scale_y, diff_y
			
			# Update scales
			scale_x += [+direction, -direction][diff_x < 0] * precision_x
			scale_y += [+direction, -direction][diff_y < 0] * precision_y
			
			# Apply scale direction constraint
			if fix_scale_direction == 1:  # Use Y for both
				scale_x = scale_y
			elif fix_scale_direction == 0:  # Use X for both
				scale_y = scale_x
			
			# Scale all attributes using the virtual axis
			# Note: delta scale operates from origin (0, 0) by design
			for attrib, delta_array in virtual_axis.items():
				delta_scale = delta_array.scale_by_stem(
					result_layer.stems, 
					(scale_x, scale_y), 
					(0., 0.),  # compensation - scale from origin
					(0., 0.),  # shift - no additional shift
					False,     # italic_angle
					extrapolate
				)
				# Convert to list for storage
				process_axis[attrib] = list(delta_scale)
			
			# Update bounds measurement
			main_data = process_axis[main_attribute]
			main_bounds = Bounds(main_data)
			
			# Calculate new differences
			diff_x = target_width - main_bounds.width
			diff_y = target_height - main_bounds.height
			
			iteration += 1
		
		# STEP 3: Apply the final scaled data to the result layer
		for attrib, data in process_axis.items():
			if attrib == 'point_array':
				# Convert back to PointArray
				setattr(result_layer, attrib, PointArray(data))
			else:
				setattr(result_layer, attrib, data)
		
		# STEP 4: Realign to preserve transformation origin
		# This is the key step that makes scaling happen around the chosen origin point!
		if transform_origin != TransformOrigin.BASELINE:
			# Get where the transformation origin ended up after scaling
			dest_bounds = result_layer.bounds
			dest_origin_x, dest_origin_y = dest_bounds.align_matrix[transform_origin.code]
			
			# Calculate the shift needed to realign the transformation origin
			realign_shift_x = source_origin_x - dest_origin_x
			realign_shift_y = source_origin_y - dest_origin_y
			
			# Apply the realignment shift
			result_layer.shift(realign_shift_x, realign_shift_y)
		
		return result_layer

	# Old destructive method kept for backward compatibility
	def delta_scale_to(self, virtual_axis, width, height, 
					   fix_scale_direction=-1, main="point_array", extrapolate=False):
		'''Delta Bruter: Brute-force to given dimensions (DESTRUCTIVE - modifies this layer).
		
		DEPRECATED: Use scale_with_axis() instead for non-destructive scaling.
		
		This method modifies the layer in place. For non-destructive scaling, use:
		    new_layer = layer.scale_with_axis(virtual_axis, target_width=width, target_height=height)
		'''
		# Call the new method and copy results back to self
		scaled_layer = self.scale_with_axis(virtual_axis, width, height, fix_scale_direction, main, extrapolate)
		
		# Copy the scaled data back to self (destructive)
		for attrib in virtual_axis.keys():
			setattr(self, attrib, getattr(scaled_layer, attrib))

	# -- SDF methods --------------------------------
	def compute_sdf(self, resolution=10.0, padding=50, steps_per_segment=64, verbose=False):
		'''Compute and cache a SignedDistanceField for all contours on this layer.

		The SDF is stored in self._sdf and can be accessed via the .sdf property.
		Subsequent calls recompute and replace the cached SDF.

		Args:
			resolution (float): Grid cell size in font units. 
				Lower = more precise but slower.
				Typical: 1.0 for production, 2-5 for preview.
			padding (float): Extra space around contour bounds.
			steps_per_segment (int): Polyline sampling density.
			verbose (bool): Print progress.

		Returns:
			SignedDistanceField: The computed SDF (also cached as self._sdf).
		'''
		self._sdf = SignedDistanceField(
			self.contours, 
			resolution=resolution, 
			padding=padding, 
			steps_per_segment=steps_per_segment
		)
		self._sdf.compute(verbose=verbose)
		return self._sdf

	def clear_sdf(self):
		'''Clear the cached SDF to free memory.'''
		self._sdf = None

	# -- Angle-compensated scaling --------------------------------
	def scale_compensated_inplace(self, sx, sy, intensity=1.0,
								  transform_origin=TransformOrigin.BASELINE):
		'''Scale layer in place with diagonal stroke weight compensation.

		Two-pass approach per contour:
		  1. Naive affine scale by (sx, sy) — preserves Bezier topology
		  2. Corrective normal offset — fixes diagonal stroke weights

		The correction direction depends on the scaling:
		  Condensing (sx < sy): diagonals get thinned
		  Expanding  (sx > sy): diagonals get grown

		Requires stems to be set on this layer (layer.stems = (stx, sty)).

		Args:
			sx (float): Horizontal scale factor (must be > 0)
			sy (float): Vertical scale factor (must be > 0)
			intensity (float): Correction strength. Default 1.0.
				0.0 = no correction (pure naive scaling)
				1.0 = standard correction
				>1.0 = amplified correction
				Typical range: 0.5 to 2.0
			transform_origin (TransformOrigin): Anchor point for scaling.
		'''
		assert self.has_stems, \
			'scale_compensated requires stems. Set layer.stems = (stx, sty) first.'

		stx, sty = self.stems

		# Get origin point before scaling
		if transform_origin != TransformOrigin.BASELINE:
			source_bounds = self.bounds
			ox, oy = source_bounds.align_matrix[transform_origin.code]
			self.shift(-ox, -oy)

		# Apply compensated scale to each contour
		for shape in self.shapes:
			for ci in range(len(shape.contours)):
				new_contour = shape.contours[ci].scale_compensated(
					sx, sy, stx, sty, intensity
				)
				# Write back node positions
				old_nodes = shape.contours[ci].nodes
				new_nodes = new_contour.nodes

				if len(new_nodes) == len(old_nodes):
					for i in range(len(old_nodes)):
						old_nodes[i].x = new_nodes[i].x
						old_nodes[i].y = new_nodes[i].y

		# Scale advance width proportionally
		self.advance_width *= sx

		# Restore origin
		if transform_origin != TransformOrigin.BASELINE:
			self.shift(ox, oy)

	# -- Per-contour compensated delta scaling --------------------------------
	def analyze_contours(self):
		'''Compute dominant orientation angle for each contour on this layer.

		Uses PCA on on-curve node positions to determine the overall
		stroke direction of each contour. Useful for diagnostics and
		for pre-computing angles before scaling.

		Returns:
			list[tuple]: List of (contour_index, angle_radians, angle_degrees)
				for each contour on this layer.
		'''
		from typerig.core.func.transform import contour_dominant_angle

		result = []

		for ci, contour in enumerate(self.contours):
			# Extract on-curve node positions only
			on_curve = [(n.x, n.y) for n in contour.nodes if n.type == 'on']
			angle = contour_dominant_angle(on_curve)
			result.append((ci, angle, math.degrees(angle)))

		return result

	def delta_scale_compensated(self, contour_deltas, scale,
								intensity=0.0, compensation=(0., 0.),
								shift=(0., 0.), italic_angle=False,
								extrapolate=False,
								metric_delta=None,
								transform_origin=TransformOrigin.BASELINE):
		'''Scale layer using per-contour DeltaMachine with diagonal compensation.
		Returns a NEW Layer — does not modify the original.

		Each contour is analyzed for its dominant stroke angle. Based on
		the angle and the scaling direction, the target stems are adjusted
		before feeding them to DeltaMachine:

		  Condensing (sx < sy): diagonal contours get lighter target stems
		    → DeltaMachine interpolates them thinner
		  Expanding (sx > sy): diagonal contours get heavier target stems
		    → DeltaMachine interpolates them fatter
		  Cardinal contours (H/V strokes): no adjustment, standard scaling

		This works on decomposed stroke contours where each closed path
		represents a single stroke. The contour_deltas should be built
		with glyph.build_contour_deltas() or build_contour_deltas_with_metrics().

		Args:
			contour_deltas (list[DeltaScale]): Per-contour DeltaScale objects,
				one per contour in layer.contours order.
				Build with: glyph.build_contour_deltas(layer_names)

			scale (tuple): (sx, sy) scale factors.
				sx < 1 = condense, sx > 1 = expand (width direction)
				sy typically stays at 1.0

			intensity (float): Diagonal compensation strength. Default 1.0.
				0.0 = no compensation (all contours get same stems)
				1.0 = standard compensation
				>1.0 = amplified (for strong anisotropy)
				Typical range: 0.3 to 1.5

			compensation (tuple): (cx, cy) DeltaMachine compensation factors.
				0.0 = no stem compensation, 1.0 = full compensation.

			shift (tuple): (dx, dy) translation after scaling.

			italic_angle: Italic shear angle in radians, or False.

			extrapolate (bool): Allow extrapolation beyond master range.

			metric_delta (DeltaScale, optional): DeltaScale for advance width.
				If provided, advance width is scaled using the global stems
				(not per-contour adjusted). Build with:
				glyph.build_delta(layer_names, 'metric_array')

			transform_origin (TransformOrigin): Anchor point for scaling.

		Returns:
			Layer: New layer with delta-scaled contours.
		'''
		assert self.has_stems, \
			'Layer requires stems. Set layer.stems = (stx, sty) first.'

		assert len(contour_deltas) == len(self.contours), \
			'contour_deltas count ({}) != contour count ({})'.format(
				len(contour_deltas), len(self.contours))

		sx, sy = scale
		target_stx, target_sty = self.stems

		# Get origin point before scaling
		if transform_origin != TransformOrigin.BASELINE:
			source_bounds = self.bounds
			ox, oy = source_bounds.align_matrix[transform_origin.code]

		# Process each shape with its slice of contour_deltas
		new_shapes = []
		contour_idx = 0

		for shape in self.shapes:
			n_contours = len(shape.contours)
			shape_deltas = contour_deltas[contour_idx:contour_idx + n_contours]

			new_shapes.append(shape.delta_scale_compensated(
				shape_deltas, (target_stx, target_sty), scale,
				intensity, compensation, shift, italic_angle, extrapolate))

			contour_idx += n_contours

		# Build new layer
		result = self.__class__(
			new_shapes,
			name=self.name,
			width=self.advance_width,
			height=self.advance_height,
			stx=self.stx,
			sty=self.sty,
			transform=self.transform.clone(),
			identifier=self.identifier,
			mark=self.mark
		)

		# Handle metrics (advance width) with global stems
		if metric_delta is not None:
			metric_result = list(metric_delta.scale_by_stem(
				(target_stx, target_sty),
				(sx, sy),
				compensation,
				shift,
				italic_angle,
				extrapolate
			))
			result.metric_array = metric_result

		# Realign to preserve transformation origin
		if transform_origin != TransformOrigin.BASELINE:
			dest_bounds = result.bounds
			dest_ox, dest_oy = dest_bounds.align_matrix[transform_origin.code]
			result.shift(ox - dest_ox, oy - dest_oy)

		return result

	def delta_scale_compensated_inplace(self, contour_deltas, scale,
										intensity=0.0, compensation=(0., 0.),
										shift=(0., 0.), italic_angle=False,
										extrapolate=False,
										metric_delta=None,
										transform_origin=TransformOrigin.BASELINE):
		'''Scale layer in place using per-contour DeltaMachine with diagonal compensation.

		Args: Same as delta_scale_compensated().
		'''
		result = self.delta_scale_compensated(
			contour_deltas, scale, intensity, compensation,
			shift, italic_angle, extrapolate,
			metric_delta, transform_origin)

		# Write back node positions
		old_nodes = self.nodes
		new_nodes = result.nodes

		if len(new_nodes) == len(old_nodes):
			for i in range(len(old_nodes)):
				old_nodes[i].x = new_nodes[i].x
				old_nodes[i].y = new_nodes[i].y

		# Copy metrics
		self.advance_width = result.advance_width
		self.advance_height = result.advance_height

	# - Directional shape interface ----------------------------
	# Adobe-style representation: each on-curve node owns its
	# outgoing and incoming off-curve positions expressed as a
	# direction vector (angle + magnitude) rather than absolute
	# coordinates. This makes angular interpolation, stem-aware
	# scaling and smooth-node enforcement much more natural.

	def to_directional(self):
		'''Export all shapes as a nested list of directional descriptions.

		Returns:
			list[list[list[DirectionalNode]]]  (layer → shape → contour → nodes)
		'''
		return [shape.to_directional() for shape in self.shapes]

	@classmethod
	def from_directional(cls, data, closed=True, **kwargs):
		'''Reconstruct a Layer from nested directional descriptions.

		Args:
			data   : list[list[list[DirectionalNode]]] — as returned by to_directional()
			closed : bool — passed down to each Contour (default True)

		Returns:
			Layer
		'''
		shapes = [Shape.from_directional(shape_data, closed=closed) for shape_data in data]
		return cls(shapes, **kwargs)

	def directional_lerp_function(self, other):
		'''Angular interpolation function between two compatible layers.

		Blends handle angles along the shorter arc and magnitudes linearly.
		When both layers have stems defined, magnitude blending is weighted
		by the stem ratio — handles on near-vertical strokes get Y-axis
		weighting, near-horizontal ones get X-axis weighting.

		Requires compatible shape/contour/node structure.

		Args:
			other (Layer): Master layer to interpolate toward.

		Returns:
			func(t, t_angle=None) — call with float 0..1.
				t_angle: optional separate time for angle blending.
				         Defaults to t when None.
		'''
		assert len(self.shapes) == len(other.shapes), 'Incompatible layers: {} vs {} shapes'.format(len(self.shapes), len(other.shapes))

		# Snapshot both masters at function-build time
		data_a = self.to_directional()
		data_b = other.to_directional()

		def func(t, t_angle=None):
			new_layer = self.__class__()

			for si, shape in enumerate(self.shapes):
				new_shape = Shape()

				for ci, contour in enumerate(shape.contours):
					blended = interpolate_directional(
						data_a[si][ci], data_b[si][ci], t, t_angle)
					
					new_shape.contours.append(Contour.from_directional(blended, closed=contour.closed))

				new_layer.shapes.append(new_shape)

			return new_layer
					
		return func

	def directional_lerp_stem_function(self, other):
		'''Stem-aware angular interpolation function between two compatible layers.

		Extends directional_lerp_function() by using each layer's stem values
		to split magnitude blending into separate X and Y components.
		A handle pointing near-vertical (angle close to pi/2) blends its
		magnitude along the Y-stem ratio; a near-horizontal handle uses the
		X-stem ratio. Handles at intermediate angles get a cosine-weighted mix.

		Both layers must have stems defined (layer.stems = (stx, sty)).
		Falls back to isotropic blending when stems are missing.

		Args:
			other (Layer): Master layer to interpolate toward.

		Returns:
			func(t, t_angle=None) — call with float 0..1.
		'''
		assert len(self.shapes) == len(other.shapes), \
			'Incompatible layers: {} vs {} shapes'.format(
				len(self.shapes), len(other.shapes))

		# Snapshot both masters at function-build time
		data_a = self.to_directional()
		data_b = other.to_directional()

		# Pre-compute stem ratios if available; fall back to 1.0 (neutral)
		if self.has_stems and other.has_stems:
			stx_a, sty_a = self.stems
			stx_b, sty_b = other.stems
			# Ratio of target stem to source stem — same logic as DeltaMachine
			rx = stx_b / float(stx_a) if stx_a else 1.
			ry = sty_b / float(sty_a) if sty_a else 1.
		else:
			rx = ry = 1.

		def _stem_t_for_angle(angle, t):
			'''Compute an effective magnitude-t biased by handle direction.
			Near-vertical handle  (angle ~ pi/2 or -pi/2) → use ry stem ratio.
			Near-horizontal handle (angle ~ 0 or pi)       → use rx stem ratio.
			Intermediate                                   → cosine mix.
			The stem ratio rescales t so that magnitudes grow proportionally
			to the stem rather than purely linearly.
			'''
			# sin²(angle) weights toward vertical, cos²(angle) toward horizontal
			sin2 = math.sin(angle) ** 2
			cos2 = math.cos(angle) ** 2
			effective_r = rx * cos2 + ry * sin2
			# Remap t so that t=1 lands at the stem ratio, not at 1.0
			return t * effective_r

		def func(t, t_angle=None):
			for si, shape in enumerate(self.shapes):
				for ci, contour in enumerate(shape.contours):
					da = data_a[si][ci]
					db = data_b[si][ci]

					blended = []

					for a, b in zip(da, db):
						# Position — plain linear
						x = a.x + (b.x - a.x) * t
						y = a.y + (b.y - a.y) * t

						# Angle — short-arc SLERP
						ta = t if t_angle is None else t_angle
						a_out = _slerp_angle(a.angle_out, b.angle_out, ta)
						a_in  = _slerp_angle(a.angle_in,  b.angle_in,  ta)

						# Magnitude — stem-weighted t per handle direction
						t_out = _stem_t_for_angle(a_out, t)
						t_in  = _stem_t_for_angle(a_in,  t)
						m_out = a.mag_out + (b.mag_out - a.mag_out) * t_out
						m_in  = a.mag_in  + (b.mag_in  - a.mag_in)  * t_in

						blended.append(DirectionalNode(
							x=x, y=y,
							angle_out=a_out, mag_out=m_out,
							angle_in=a_in,   mag_in=m_in,
							smooth=a.smooth,
						))

					rebuilt = Contour.from_directional(blended, closed=contour.closed)

					for node, src in zip(contour.nodes, rebuilt.nodes):
						node.x = src.x
						node.y = src.y

		return func

if __name__ == '__main__':
	from pprint import pprint
	section = lambda s: '\n+{0}\n+ {1}\n+{0}'.format('-'*30, s)

	test = [(200.0, 280.0),
			(760.0, 280.0),
			(804.0, 280.0),
			(840.0, 316.0),
			(840.0, 360.0),
			(840.0, 600.0),
			(840.0, 644.0),
			(804.0, 680.0),
			(760.0, 680.0),
			(200.0, 680.0),
			(156.0, 680.0),
			(120.0, 644.0),
			(120.0, 600.0),
			(120.0, 360.0),
			(120.0, 316.0),
			(156.0, 280.0)]

	new_test = [(t[0]+100, t[1]+100) for t in test]

	l = Layer([[test]])
	print(section('Layer'))
	pprint(l)
		
	print(section('Layer Bounds'))
	pprint(l)

	print(section('Layer Array'))
	pprint(l.point_array)


	print(l.has_stems)
	print(Bounds([(0,0),(100,200)]))

	print(l.to_XML())