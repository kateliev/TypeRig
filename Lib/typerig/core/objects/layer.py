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
from typerig.core.objects.anchor import Anchor
from typerig.core.objects.sdf import SignedDistanceField

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.func.math import slerp_angle, interpolate_directional
from typerig.core.func.transform import adaptive_scale_directional, timer

# - Init -------------------------------
__version__ = '0.6.2'

# - Classes -----------------------------
@register_xml_class
class Layer(Container, XMLSerializable): 
	__slots__ = ('name', 'stx', 'sty', 'transform', 'mark', 'advance_width', 'advance_height', 'identifier', 'parent', 'lib', 'anchors', '_sdf')

	XML_TAG = 'layer'
	XML_ATTRS = ['name', 'identifier', 'width', 'height', 'stx', 'sty']
	XML_CHILDREN = {'shape': 'shapes', 'anchor': 'anchors'}
	XML_LIB_ATTRS = []
	
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
			self.anchors = kwargs.pop('anchors', [])

		# - SDF cache (not serialized)
		self._sdf = None

	
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Shapes={}>'.format(self.__class__.__name__, self.name, len(self.data))

	# -- Properties -----------------------------
	@property
	def width(self):
		'''XML alias for advance_width'''
		return self.advance_width

	@width.setter
	def width(self, value):
		self.advance_width = value

	@property
	def height(self):
		'''XML alias for advance_height'''
		return self.advance_height

	@height.setter
	def height(self, value):
		self.advance_height = value
	
	@property
	def sdf(self):
		'''Cached SignedDistanceField for this layer. 
		None if not yet computed. Use compute_sdf() to populate.
		'''
		return self._sdf

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

	@property
	def center_of_mass(self):
		'''Area-weighted centroid of the layer outline (center of gravity).
		Uses the shoelace formula (Green's theorem) over on-curve polygons.
		Counters (CCW contours) subtract from the area automatically.

		Returns:
			Point or None if no on-curve nodes exist
		'''
		total_area = 0.
		total_cx = 0.
		total_cy = 0.

		for contour in self.contours:
			pts = [(n.x, n.y) for n in contour.nodes if n.type == 'on']
			n = len(pts)

			if n < 3:
				continue

			# Shoelace: signed area and first moments
			a = 0.
			cx = 0.
			cy = 0.

			for i in range(n):
				j = (i + 1) % n
				cross = pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
				a += cross
				cx += (pts[i][0] + pts[j][0]) * cross
				cy += (pts[i][1] + pts[j][1]) * cross

			total_area += a
			total_cx += cx
			total_cy += cy

		if abs(total_area) < 1e-10:
			return None

		total_area *= 0.5
		total_cx /= (6. * total_area)
		total_cy /= (6. * total_area)

		return Point(total_cx, total_cy)

	@property
	def align_matrix(self):
		'''Layer-level alignment matrix — superset of Bounds.align_matrix.
		Contains bounding box positions, metrics positions and outline 
		analysis positions. Useful for alignment, transformation origins,
		anchor placement, guidelines and any position-dependent operations.
		'''
		# Tier 1: Bounding box positions
		matrix = dict(self.bounds.align_matrix)

		# Tier 2: Metrics positions (Layer knows advance width/height)
		matrix['LSB'] = (0., 0.)
		matrix['RSB'] = (self.ADV, 0.)
		matrix['ADV'] = (self.ADV, 0.)
		matrix['ADM'] = (self.ADV / 2., 0.)

		# Tier 3: Outline analysis positions (on-curve extrema centers)
		outline = self.outline_centers()

		if outline is not None:
			matrix['OBL'] = (outline['bottom_left'], outline['min_y'])
			matrix['OBR'] = (outline['bottom_right'], outline['min_y'])
			matrix['OBM'] = (outline['bottom_center'], outline['min_y'])
			matrix['OTL'] = (outline['top_left'], outline['max_y'])
			matrix['OTR'] = (outline['top_right'], outline['max_y'])
			matrix['OTM'] = (outline['top_center'], outline['max_y'])

		# Tier 4: Statistical positions (area-weighted centroid)
		com = self.center_of_mass

		if com is not None:
			matrix['COM'] = (com.x, com.y)

		return matrix

	# - Fucntions --------------------------
	def outline_centers(self, tolerance=5):
		'''Compute X centers at lowest and highest Y from on-curve nodes.
		Useful for determining diacritic/mark attachment positions and
		outline-aware alignment origins.

		Args:
			tolerance (float): Y-distance tolerance for grouping nodes at extremes

		Returns:
			dict with keys: min_y, max_y, bottom_left, bottom_right, bottom_center,
			top_left, top_right, top_center. Returns None if no on-curve nodes.
		'''
		from operator import itemgetter

		# Collect on-curve node coordinates
		on_curve = [(n.x, n.y) for n in self.nodes if n.type == 'on']

		if not on_curve:
			return None

		min_y = min(on_curve, key=itemgetter(1))[1]
		max_y = max(on_curve, key=itemgetter(1))[1]

		# Nodes within tolerance of min/max Y
		at_min_y = [pt for pt in on_curve if abs(pt[1] - min_y) < tolerance]
		at_max_y = [pt for pt in on_curve if abs(pt[1] - max_y) < tolerance]

		bottom_left = min(at_min_y, key=itemgetter(0))[0]
		bottom_right = max(at_min_y, key=itemgetter(0))[0]
		top_left = min(at_max_y, key=itemgetter(0))[0]
		top_right = max(at_max_y, key=itemgetter(0))[0]

		return {
			'min_y': min_y,
			'max_y': max_y,
			'bottom_left': bottom_left,
			'bottom_right': bottom_right,
			'bottom_center': (bottom_left + bottom_right) / 2.,
			'top_left': top_left,
			'top_right': top_right,
			'top_center': (top_left + top_right) / 2.
		}


	# - Anchors ---------------------------------
	def find_anchor(self, name):
		'''Find anchor by name.

		Args:
			name (str): Anchor name to search for

		Returns:
			Anchor or None
		'''
		return next((a for a in self.anchors if a.name == name), None)

	def add_anchor(self, name, position=(0., 0.), align=None, tolerance=5, italic_angle=0.):
		'''Add an anchor to this layer.

		Args:
			name (str): Anchor name
			position (tuple or Point): Base position or offset when align is used
			align (TransformOrigin, optional): Alignment origin from align_matrix.
				When provided, position is treated as an offset from that origin.
			tolerance (float): Tolerance for outline_centers analysis
			italic_angle (float): Italic angle in degrees for X correction

		Returns:
			Anchor: The newly created anchor
		'''
		x, y = self._resolve_anchor_position(position, align, tolerance, italic_angle)

		anchor = Anchor(x, y, name=name, parent=self)
		self.anchors.append(anchor)
		return anchor

	def move_anchor(self, name, offset=(0., 0.), align=None, tolerance=5, italic_angle=0.):
		'''Move an existing anchor by name.

		Args:
			name (str): Anchor name to find and move
			offset (tuple or Point): Position or offset
			align (TransformOrigin, optional): Alignment origin from align_matrix.
				When provided, offset is added to that origin (absolute repositioning).
				When None, offset is added to current position (relative shift).
			tolerance (float): Tolerance for outline_centers analysis
			italic_angle (float): Italic angle in degrees for X correction

		Returns:
			Anchor or None if not found
		'''
		anchor = self.find_anchor(name)

		if anchor is None:
			return None

		if align is not None:
			# Absolute repositioning relative to alignment origin
			x, y = self._resolve_anchor_position(offset, align, tolerance, italic_angle)
			anchor.x = x
			anchor.y = y
		else:
			# Relative shift from current position
			ox = offset[0] if isinstance(offset, (tuple, list)) else offset.x
			oy = offset[1] if isinstance(offset, (tuple, list)) else offset.y
			anchor.shift(ox, oy)

		return anchor

	def remove_anchor(self, name):
		'''Remove anchor by name.

		Args:
			name (str): Anchor name to remove

		Returns:
			Anchor or None if not found
		'''
		anchor = self.find_anchor(name)

		if anchor is not None:
			self.anchors.remove(anchor)

		return anchor

	def _resolve_anchor_position(self, offset, align=None, tolerance=5, italic_angle=0.):
		'''Resolve anchor position from offset and alignment origin.

		Args:
			offset (tuple or Point): (x, y) offset values
			align (TransformOrigin, optional): Alignment origin to use as base.
				When None, offset is returned as-is.
			tolerance (float): Tolerance for outline_centers analysis
			italic_angle (float): Italic angle in degrees

		Returns:
			tuple: (x, y) resolved position
		'''
		ox = offset[0] if isinstance(offset, (tuple, list)) else offset.x
		oy = offset[1] if isinstance(offset, (tuple, list)) else offset.y

		if align is None:
			return (ox, oy)

		# Get base position from align_matrix
		matrix = self.align_matrix
		code = align.code if hasattr(align, 'code') else align

		if code not in matrix:
			raise ValueError('Unknown alignment code: {}'.format(code))

		base_x, base_y = matrix[code]

		# Apply italic angle correction
		if italic_angle != 0.:
			italic_shift = math.tan(math.radians(italic_angle)) * (base_y + oy)
			x = ox + base_x + italic_shift
			y = oy + base_y
		else:
			x = ox + base_x
			y = oy + base_y

		return (x, y)

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
		return [(a.x, a.y) for a in self.anchors]

	@anchor_array.setter
	def anchor_array(self, other):
		if isinstance(other, (tuple, list)) and len(other) == len(self.anchors):
			for idx in range(len(self.anchors)):
				self.anchors[idx].x = other[idx][0]
				self.anchors[idx].y = other[idx][1]

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

		for anchor in self.anchors:
			anchor.x, anchor.y = self.transform.applyTransformation(anchor.x, anchor.y)

	def shift(self, delta_x, delta_y):
		'''Shift the layer by given amount'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

		for anchor in self.anchors:
			anchor.shift(delta_x, delta_y)

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
		align_matrix = self.align_matrix
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

	def delta_function(self, other):
		'''Adaptive scaling function between two compatible layers.

		Direct layer-level equivalent of contour.delta_function() and
		node.delta_function(). Snapshots node pairs from both masters at
		build time, returns a callable that applies adaptive_scale() over
		all nodes and produces a new Layer.

		Node weights (node.weight.x, node.weight.y) carry the stem values
		for each master. Set with layer.set_weight(wx, wy) before calling.

		Args:
			other (Layer): Second master layer. Must be structurally compatible.

		Returns:
			func(scale, time, translate, angle, compensate) -> Layer
				scale     : (sx, sy) scale factors
				time      : (tx, ty) interpolation times, anisotropic X/Y
				translate : (dx, dy) post-interpolation shift
				angle     : italic shear in radians
				compensate: (cx, cy) stem compensation 0.0=none 1.0=full
		'''
		from typerig.core.func.transform import adaptive_scale

		# Snapshot node pairs and their stem weights at build time
		node_array = [
			(n0.point.tuple, n1.point.tuple, n0.weight.tuple, n1.weight.tuple)
			for n0, n1 in zip(self.nodes, other.nodes)
		]

		def func(scale=(1., 1.), time=(0., 0.), translate=(0., 0.), angle=0., compensate=(0., 0.)):
			new_layer = self.clone()
			new_nodes = new_layer.nodes

			for idx in range(len(new_nodes)):
				p0, p1, w0, w1 = node_array[idx]
				new_nodes[idx].point = Point(adaptive_scale(
					(p0, p1),
					scale,
					translate,
					time,
					compensate,
					angle,
					(w0[0], w1[0], w0[1], w1[1])	# stx0, stx1, sty0, sty1
				))

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

	def directional_delta_function(self, other):
		'''Adaptive scaling function using directional (polar) handle geometry.

		Mirrors the DeltaMachine stem-compensation workflow:
		  - self.stems provides the TARGET stem value (where you want to be)
		  - node.weight on each master holds the master's stem values
		  - interpolation time is derived via timer() from the above,
		    exactly as DeltaScale.scale_by_stem() does it
		  - scale, compensate, translate, italic_angle are caller-controlled

		Difference from standard delta_function():
		  - handle angles transform geometrically (SLERP + anisotropic direction)
		  - handle magnitudes stretch geometrically in the handle's own direction
		  - on-curve positions use identical adaptive_scale stem compensation
		  - t_angle allows handle angles to lead or lag the position blend

		Requires:
		  - self.has_stems == True  (set layer.stems = (stx, sty) first)
		  - node.weight set on all nodes of both masters (set_weight or per-node)
		  - compatible shape/contour/node structure

		Args:
			other (Layer): Second master layer.

		Returns:
			func(scale, compensate, translate, italic_angle, extrapolate, t_angle) -> Layer
				scale        : (sx, sy) scale factors
				compensate   : (cx, cy) stem compensation 0.0=none 1.0=full
				translate    : (dx, dy) post-interpolation shift
				italic_angle : shear in radians for italic designs
				extrapolate  : bool — allow extrapolation beyond master range
				t_angle      : float or None — separate time for handle angle blending.
				               Defaults to the stem-derived tx when None.
		'''
		from typerig.core.func.transform import adaptive_scale_directional, timer

		assert self.has_stems, \
			'Layer requires stems. Set layer.stems = (stx, sty) first.'

		assert len(self.shapes) == len(other.shapes), \
			'Incompatible layers: {} vs {} shapes'.format(
				len(self.shapes), len(other.shapes))

		# Target stems: where on the interpolation axis this layer sits
		target_stx, target_sty = self.stems

		# Snapshot directional geometry from both masters at build time
		data_a = self.to_directional()
		data_b = other.to_directional()

		# Snapshot per-node stem weights from both masters.
		# weight.x = horizontal stem (stx), weight.y = vertical stem (sty)
		def _stem_weights(layer):
			result = []

			for shape in layer.shapes:
				for contour in shape.contours:
					for node in contour.nodes:
						if node.is_on:
							result.append((node.weight.x, node.weight.y))

			return result

		stems_a = _stem_weights(self)
		stems_b = _stem_weights(other)

		def func(scale=(1., 1.), compensate=(0., 0.), translate=(0., 0.), italic_angle=0., extrapolate=False, t_angle=None):
			new_layer = self.__class__()
			on_idx = 0

			for si, shape in enumerate(self.shapes):
				new_shape = Shape()

				for ci, contour in enumerate(shape.contours):
					da = data_a[si][ci]
					db = data_b[si][ci]
					scaled = []

					for dn_a, dn_b in zip(da, db):
						wx_a, wy_a = stems_a[on_idx]
						wx_b, wy_b = stems_b[on_idx]
						on_idx += 1

						# Derive interpolation time from target stem vs master stems —
						# identical logic to DeltaScale._stem_for_time() / scale_by_stem()
						tx = timer(target_stx, wx_a, wx_b, fix_boundry=extrapolate)
						ty = timer(target_sty, wy_a, wy_b, fix_boundry=extrapolate)

						# t_angle defaults to tx — angles follow position unless overridden
						ta = tx if t_angle is None else t_angle

						scaled.append(adaptive_scale_directional(
							dn_a, dn_b,
							scale,
							translate,
							(tx, ty),				# position time — stem derived
							compensate,
							italic_angle,
							(wx_a, wx_b, wy_a, wy_b),	# stx0, stx1, sty0, sty1
							ta,					# angle time — caller controlled
						))

					new_shape.contours.append(
						Contour.from_directional(scaled, closed=contour.closed))

				new_layer.shapes.append(new_shape)

			return new_layer

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