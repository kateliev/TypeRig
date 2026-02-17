# MODULE: TypeRig / Core / Contour (Object)
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

from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.array import PointArray
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.transform import Transform, TransformOrigin
from typerig.core.objects.utils import Bounds

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.func.utils import isMultiInstance
from typerig.core.func.transform import adaptive_scale, lerp
from typerig.core.func.math import zero_matrix, solve_equations, hobby_control_points

from typerig.core.objects.atom import Container
from typerig.core.objects.node import Node, Knot

# - Init -------------------------------
__version__ = '0.5.0'

# - Classes -----------------------------
@register_xml_class
class Contour(Container, XMLSerializable): 
	__slots__ = ('name', 'closed', 'clockwise', 'transform', 'parent', 'lib')

	XML_TAG = 'contour'
	XML_ATTRS = ['name', 'identifier']
	XML_CHILDREN = {'node': 'nodes'}
	XML_LIB_ATTRS = ['transform', 'closed', 'clockwise']

	def __init__(self, nodes=None, **kwargs):
		factory = kwargs.pop('default_factory', Node)
		super(Contour, self).__init__(nodes, default_factory=factory, **kwargs)
		
		self.transform = kwargs.pop('transform', Transform())
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.name = kwargs.pop('name', '')
			self.closed = kwargs.pop('closed', False)
			self.clockwise = kwargs.pop('clockwise', self.get_winding())

	# -- Properties -----------------------------
	@property
	def nodes(self):
		return self.data

	@nodes.setter
	def nodes(self, other):
		if isinstance(other, self.__class__):
			self.data = other

		if isinstance(other, (tuple, list)):
			for item in other:
				if not isinstance(item, self._subclass):
					item = self._subclass(item, parent=self)
					self.data.append(item)

	@property
	def selected_nodes(self):
		return [node for node in self.nodes if node.selected]

	@property
	def selected_indices(self):
		return [idx for idx in range(len(self.nodes)) if self.nodes[idx].selected]
	
	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.data))
		return Bounds([node.point.tuple for node in self.data])

	@property
	def node_segments(self):
		return self.get_segments(get_point=False)

	@property
	def point_segments(self):
		return self.get_segments(get_point=True)

	@property
	def segments(self):
		obj_segments = []

		for segment in self.point_segments:
			if len(segment) == 2:
				obj_segments.append(Line(*segment))

			elif len(segment) == 3:
				# Placeholder for simple TT curves
				raise NotImplementedError

			elif len(segment) == 4:
				obj_segments.append(CubicBezier(*segment))

			else:
				# Placeholder for complex TT curves
				raise NotImplementedError

		return obj_segments

	@property
	def point_array(self):
		return PointArray([node.point for node in self.nodes])

	@point_array.setter
	def point_array(self, other):
		contour_nodes = self.nodes

		if isinstance(other, PointArray) and len(other) == len(contour_nodes):
			for idx in range(len(contour_nodes)):
				contour_nodes[idx].point = other[idx]

	@property 
	def on_curve_points(self):
		'''Return list of on-curve points (segment start points).'''
		return [seg.p0 for seg in self.segments]

	@property
	def all_points_flat(self):
		'''Return flat list of all coordinates for polyline rendering.'''
		pts = self.sample(steps_per_segment=100)
		if pts:
			pts.append(pts[0])  # close
		return pts
		
	@property
	def signed_area(self):
		'''Signed area via shoelace on sampled polyline.
		Positive = CCW, Negative = CW.
		More accurate than get_on_area() for curved contours.
		'''
		pts = self.sample(steps_per_segment=100)
		n = len(pts)
		area = 0.0

		for i in range(n):
			x0, y0 = pts[i]
			x1, y1 = pts[(i + 1) % n]
			area += x0 * y1 - x1 * y0

		return area / 2.0

	@property
	def is_ccw(self):
		'''True if contour winds counter-clockwise (outer in PS convention).'''
		return self.signed_area > 0

	# -- Functions ------------------------------
	def set_start(self, index):
		index = self.nodes[index].prev_on.idx if not self.nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index] 

	def get_winding(self):
		'''Check if contour has clockwise winding direction'''
		return self.get_on_area() > 0

	def get_on_area(self):
		'''Get contour area using on curve points only'''
		polygon_area = []

		for node in self.nodes:
			edge_sum = (node.next_on.x - node.x)*(node.next_on.y + node.y)
			polygon_area.append(edge_sum)

		return sum(polygon_area)*0.5

	def get_segments(self, get_point=False):
		assert len(self.data) > 1, 'Cannot return segments for contour with length {}'.format(len(self.data))
		contour_segments = []
		contour_nodes = self.data[:]
		if self.closed: contour_nodes.append(contour_nodes[0])

		while len(contour_nodes):
			node = contour_nodes[0]
			contour_nodes= contour_nodes[1:]
			segment = [node.point] if get_point else [node]

			for node in contour_nodes:
				segment.append(node.point if get_point else node)
				if node.is_on: break

			contour_segments.append(segment)
			contour_nodes = contour_nodes[len(segment)-2:]

		return contour_segments[:-1]

	def reverse(self):
		reversed_data = list(reversed(self.data))
		self.clockwise = not self.clockwise
		# - An offcurve could never be first node
		on_index = next(i for i, node in enumerate(reversed_data) if node.type == 'on')
		self.data = reversed_data[on_index:] + reversed_data[:on_index]
		
	def set_weight(self, wx, wy):
		'''Set x and y weights (a.k.a. stems) for all nodes'''
		for node in self.nodes:
			node.weight.x = wx
			node.weight.y = wy

	# - Transformation --------------------------
	def apply_transform(self):
		for node in self.nodes:
			node.x, node.y = self.transform.applyTransformation(node.x, node.y)

	def shift(self, delta_x, delta_y):
		'''Shift the contour by given amout'''
		for node in self.nodes:
			node.point += Point(delta_x, delta_y)

	def align_to(self, entity, mode=(TransformOrigin.CENTER, TransformOrigin.CENTER), 
	             align=(True, True)):
		'''Align contour to another entity using transformation origins.
		
		Arguments:
			entity (Contour, Point, tuple(x,y)):
				Object to align to

			mode (tuple(TransformOrigin, TransformOrigin)):
				Alignment origins for (self, other). Must use TransformOrigin enum.

			align (tuple(bool, bool)):
				Align X, Align Y. Set to False to disable alignment on that axis.
		
		Returns:
			Nothing (modifies contour in place)
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

	def lerp_function(self, other):
		'''Linear interpolation function to Node or Point
		Args:
			other -> Contour
			
		Returns:
			lerp function(tx, ty) with parameters:
			tx, ty (float, float) : Interpolation times (anisotropic X, Y) 
		'''
		node_array = [(n0.point, n1.point) for n0, n1 in zip(self.nodes, other.nodes)]

		def func(tx, ty):
			for idx in range(len(self.nodes)):
				self.nodes[idx].point = Point(lerp(node_array[idx][0].x, node_array[idx][1].x, tx), lerp(node_array[idx][0].y, node_array[idx][1].y, ty))

		return func	

	def delta_function(self, other):
		'''Adaptive scaling function to Node
		Args:
			other -> Contour

		Returns:
			Delta function(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)) with parameters:
				scale(sx, sy) -> tuple((float, float) : Scale factors (X, Y)
				time(tx, ty) -> tuple((float, float) : Interpolation times (anisotropic X, Y) 
				translate(dx, dy) -> tuple((float, float) : Translate values (X, Y) 
				angle -> (radians) : Angle of sharing (for italic designs)  
				compensate(cx, cy) -> tuple((float, float) : Compensation factor 0.0 (no compensation) to 1.0 (full compensation) (X,Y)
		'''
		node_array = [(n0.point.tuple, n1.point.tuple, n0.weight.tuple, n1.weight.tuple) for n0, n1 in zip(self.nodes, other.nodes)]
		
		def func(scale=(1.,1.), time=(0.,0.), transalte=(0.,0.), angle=0., compensate=(0.,0.)):
			for idx in range(len(self.nodes)):
				self.nodes[idx].point = Point(adaptive_scale((node_array[idx][0], node_array[idx][1]), scale, transalte, time, compensate, angle, (node_array[idx][2][0], node_array[idx][3][0], node_array[idx][2][1], node_array[idx][3][1])))

		return func

	# -- SDF / Offset related -------------------------
	def sample(self, steps_per_segment=64):
		'''Sample contour into a polyline of (x, y) tuples.
		Args:
			steps_per_segment (int): samples per bezier segment
		Returns:
			list of tuple(x, y)
		'''
		points = []

		for segment in self.segments:
			for j in range(steps_per_segment):
				t = j / float(steps_per_segment)
				pt = segment.solve_point(t)
				points.append((pt.x, pt.y))

		return points

	def sample_with_normals(self, steps_per_segment=64):
		'''Sample contour points paired with outward unit normals.

		Normal convention: right-hand normal (dy, -dx).
		For CCW (outer) contours this points outward.
		For CW (inner) contours this points inward into filled area.

		Args:
			steps_per_segment (int): samples per bezier segment

		Returns:
			list of ((px, py), (nx, ny))
		'''
		result = []

		for segment in self.segments:
			if isinstance(segment, CubicBezier):
				for j in range(steps_per_segment):
					t = j / float(steps_per_segment)
					pt = segment.solve_point(t)
					_pt, d1, _d2 = segment.solve_derivative_at_time(t)
					mag = math.sqrt(d1.x * d1.x + d1.y * d1.y)

					if mag > 1e-10:
						nx, ny = d1.y / mag, -d1.x / mag
					else:
						nx, ny = 0.0, 0.0

					result.append(((pt.x, pt.y), (nx, ny)))

			elif isinstance(segment, Line):
				dx = segment.p1.x - segment.p0.x
				dy = segment.p1.y - segment.p0.y
				mag = math.sqrt(dx * dx + dy * dy)

				if mag > 1e-10:
					nx, ny = dy / mag, -dx / mag
				else:
					nx, ny = 0.0, 0.0

				for j in range(steps_per_segment):
					t = j / float(steps_per_segment)
					pt = segment.solve_point(t)
					result.append(((pt.x, pt.y), (nx, ny)))

		return result

	@staticmethod
	def _segment_normals(segment, epsilon=0.5):
		'''Compute outward normals and curvature at segment endpoints.

		Handles degenerate (zero-length / collapsed) segments gracefully:
		returns None for normals that cannot be determined, letting the 
		caller resolve them from neighboring segments.

		Args:
			segment: CubicBezier or Line object
			epsilon (float): Below this chord length, segment is degenerate.

		Returns:
			tuple: (n_start, n_end, k_start, k_end)
				n_start, n_end: (nx, ny) unit normal or None if degenerate
				k_start, k_end: curvature float (0.0 if degenerate)
		'''
		if isinstance(segment, CubicBezier):
			# Check if fully collapsed (all points within epsilon)
			chord = abs(segment.p3 - segment.p0)

			if chord < epsilon:
				# Also check if handles extend meaningfully
				h_out = abs(segment.p1 - segment.p0)
				h_in = abs(segment.p2 - segment.p3)

				if h_out < epsilon and h_in < epsilon:
					return None, None, 0., 0.

			# Start normal from P0->P1 tangent
			tan0 = segment.p1 - segment.p0
			m0 = abs(tan0)

			if m0 < 1e-10:
				tan0 = segment.p3 - segment.p0
				m0 = abs(tan0)

			n0 = (tan0.y / m0, -tan0.x / m0) if m0 > 1e-10 else None

			# End normal from P2->P3 tangent
			tan3 = segment.p3 - segment.p2
			m3 = abs(tan3)

			if m3 < 1e-10:
				tan3 = segment.p3 - segment.p0
				m3 = abs(tan3)

			n3 = (tan3.y / m3, -tan3.x / m3) if m3 > 1e-10 else None

			# Curvature: safe against zero-length
			k0 = 0.
			k3 = 0.

			if n0 is not None:
				try:
					k0 = segment.solve_curvature(0.0)
				except (ZeroDivisionError, ValueError):
					k0 = 0.

			if n3 is not None:
				try:
					k3 = segment.solve_curvature(1.0)
				except (ZeroDivisionError, ValueError):
					k3 = 0.

			return n0, n3, k0, k3

		elif isinstance(segment, Line):
			dx = segment.p1.x - segment.p0.x
			dy = segment.p1.y - segment.p0.y
			m = math.sqrt(dx * dx + dy * dy)

			if m < epsilon:
				return None, None, 0., 0.

			n = (dy / m, -dx / m)
			return n, n, 0., 0.

		return None, None, 0., 0.

	def _compute_miter_displacements(self, distance):
		'''Compute miter displacement vectors for all on-curve junction nodes.

		Handles degenerate (zero-length) segments: their None normals are 
		filtered out, and orphaned nodes inherit displacement from the 
		nearest resolved neighbor along the contour.

		Args:
			distance (float): Offset amount in font units.

		Returns:
			tuple: (seg_info, on_disp)
				seg_info: list of (n_start, n_end, k_start, k_end) per segment
				on_disp: dict {id(node): (dx, dy)} for all on-curve nodes
		'''
		segments = self.segments
		node_segs = self.node_segments
		num_seg = len(segments)

		# --- Pass 1: per-segment normals and curvature ---
		seg_info = []

		for segment in segments:
			seg_info.append(self._segment_normals(segment))

		# --- Pass 2: collect non-None normals per junction node ---
		on_normals = {}

		for si in range(num_seg):
			nodes = node_segs[si]
			n_start, n_end, _, _ = seg_info[si]

			for node, normal in [(nodes[0], n_start), (nodes[-1], n_end)]:
				nid = id(node)

				if nid not in on_normals:
					on_normals[nid] = []

				if normal is not None:
					on_normals[nid].append(normal)

		# --- Miter formula for nodes with normals ---
		on_disp = {}

		for nid, normals in on_normals.items():
			if len(normals) == 0:
				continue

			elif len(normals) == 1:
				n = normals[0]
				on_disp[nid] = (n[0] * distance, n[1] * distance)

			elif len(normals) == 2:
				n1, n2 = normals
				dot = n1[0] * n2[0] + n1[1] * n2[1]
				denom = 1.0 + dot

				if denom < 0.15:
					denom = 0.15

				sx = n1[0] + n2[0]
				sy = n1[1] + n2[1]
				on_disp[nid] = (distance * sx / denom, distance * sy / denom)

			else:
				sx = sum(n[0] for n in normals)
				sy = sum(n[1] for n in normals)
				mag = math.sqrt(sx * sx + sy * sy)

				if mag > 1e-10:
					on_disp[nid] = (sx / mag * distance, sy / mag * distance)
				else:
					on_disp[nid] = (0., 0.)

		# --- Propagate to orphaned nodes (degenerate segments only) ---
		if len(on_disp) < len(on_normals):
			junction_ids = []

			for si in range(num_seg):
				nodes = node_segs[si]
				nid = id(nodes[0])

				if not junction_ids or junction_ids[-1] != nid:
					junction_ids.append(nid)

			n_junctions = len(junction_ids)

			for ji, nid in enumerate(junction_ids):
				if nid in on_disp:
					continue

				fwd_disp = None
				bwd_disp = None

				for step in range(1, n_junctions):
					fwd_nid = junction_ids[(ji + step) % n_junctions]

					if fwd_nid in on_disp:
						fwd_disp = on_disp[fwd_nid]
						break

				for step in range(1, n_junctions):
					bwd_nid = junction_ids[(ji - step) % n_junctions]

					if bwd_nid in on_disp:
						bwd_disp = on_disp[bwd_nid]
						break

				if fwd_disp is not None and bwd_disp is not None:
					on_disp[nid] = (
						(fwd_disp[0] + bwd_disp[0]) * 0.5,
						(fwd_disp[1] + bwd_disp[1]) * 0.5
					)
				elif fwd_disp is not None:
					on_disp[nid] = fwd_disp
				elif bwd_disp is not None:
					on_disp[nid] = bwd_disp
				else:
					on_disp[nid] = (0., 0.)

		return seg_info, on_disp

	@staticmethod
	def _build_offset_nodes(segments, node_segs, seg_info, on_disp, distance, curvature_correction, closed):
		'''Build new node list from computed displacements.

		Shared by offset_outline, offset_outline_sdf, etc.

		Args:
			segments: list of segment objects
			node_segs: list of node lists per segment
			seg_info: list of (n_start, n_end, k_start, k_end) per segment
			on_disp: dict {id(node): (dx, dy)} displacement per on-curve node
			distance: original signed offset distance (for curvature sign)
			curvature_correction: bool
			closed: bool

		Returns:
			Contour: New offset contour.
		'''
		new_node_list = []

		for si in range(len(segments)):
			segment = segments[si]
			nodes = node_segs[si]
			_, _, k_start, k_end = seg_info[si]

			if isinstance(segment, CubicBezier) and len(nodes) == 4:
				p0, bcp_out, bcp_in, p3 = nodes
				d0 = on_disp.get(id(p0), (0., 0.))
				d3 = on_disp.get(id(p3), (0., 0.))

				new_p0x = p0.x + d0[0]
				new_p0y = p0.y + d0[1]
				new_bcp_out_x = bcp_out.x + d0[0]
				new_bcp_out_y = bcp_out.y + d0[1]
				new_bcp_in_x = bcp_in.x + d3[0]
				new_bcp_in_y = bcp_in.y + d3[1]

				if curvature_correction and (k_start != 0. or k_end != 0.):
					s0 = max(0.1, min(1.0 + distance * k_start, 5.0))

					if abs(s0 - 1.0) > 1e-6:
						hx = new_bcp_out_x - new_p0x
						hy = new_bcp_out_y - new_p0y
						new_bcp_out_x = new_p0x + hx * s0
						new_bcp_out_y = new_p0y + hy * s0

					s3 = max(0.1, min(1.0 + distance * k_end, 5.0))

					if abs(s3 - 1.0) > 1e-6:
						new_p3x = p3.x + d3[0]
						new_p3y = p3.y + d3[1]
						hx = new_bcp_in_x - new_p3x
						hy = new_bcp_in_y - new_p3y
						new_bcp_in_x = new_p3x + hx * s3
						new_bcp_in_y = new_p3y + hy * s3

				new_node_list.append(Node(new_p0x, new_p0y, type='on', smooth=p0.smooth))
				new_node_list.append(Node(new_bcp_out_x, new_bcp_out_y, type='curve', smooth=bcp_out.smooth))
				new_node_list.append(Node(new_bcp_in_x, new_bcp_in_y, type='curve', smooth=bcp_in.smooth))

			elif isinstance(segment, Line) and len(nodes) == 2:
				p0 = nodes[0]
				d0 = on_disp.get(id(p0), (0., 0.))
				new_node_list.append(Node(p0.x + d0[0], p0.y + d0[1], type='on', smooth=p0.smooth))

		return Contour(new_node_list, closed=closed, proxy=False)

	def offset_outline(self, distance, curvature_correction=True):
		'''Offset contour using analytical Bezier normals with miter joins.
		Returns a NEW Contour — does not modify the original.

		At each junction between segments, the miter formula is used:
		  disp = d * (n_in + n_out) / (1 + dot(n_in, n_out))
		This guarantees perpendicular distance = d to each adjacent edge,
		keeping lines parallel and curves at correct distance.

		Handles degenerate (zero-length / collapsed) segments: their nodes
		inherit displacement from the nearest non-degenerate neighbor,
		preserving point compatibility for Multiple Master workflows.

		Normal convention: right-hand normal (tan.y, -tan.x).
		  - Positive distance = expand (thicken strokes)
		  - Negative distance = contract (thin strokes)

		Args:
			distance (float): Offset amount in font units. 
			curvature_correction (bool): Scale handles by (1 + d * kappa).

		Returns:
			Contour: New offset contour with same node structure.
		'''
		if len(self.segments) == 0:
			return self.clone()

		seg_info, on_disp = self._compute_miter_displacements(distance)

		return self._build_offset_nodes(
			self.segments, self.node_segments, seg_info, on_disp,
			distance, curvature_correction, self.closed
		)

	def offset_outline_inplace(self, distance, curvature_correction=True):
		'''Offset contour in place using analytical Bezier normals.

		Convenience wrapper: computes offset_outline() then applies 
		the result back to this contour's nodes.

		Args:
			distance (float): Offset amount in font units.
			curvature_correction (bool): Scale handles by (1 + d * kappa).
		'''
		new_contour = self.offset_outline(distance, curvature_correction)
		new_nodes = new_contour.nodes

		if len(new_nodes) == len(self.nodes):
			for i in range(len(self.nodes)):
				self.nodes[i].x = new_nodes[i].x
				self.nodes[i].y = new_nodes[i].y

	def offset_outline_sdf(self, distance, sdf, curvature_correction=True, clamp_factor=0.9):
		'''Offset contour using analytical normals with SDF distance clamping.
		Returns a NEW Contour — does not modify the original.

		Direction: identical to offset_outline() — analytical normals with
		miter formula at junctions. This is geometrically exact.

		Distance: the SDF provides topology-aware clamping. At each on-curve
		node, the SDF value tells us the distance to the nearest OTHER 
		contour edge. If the requested offset would overshoot the medial 
		axis (i.e. collide with another stroke or counter), the displacement 
		is reduced to prevent self-intersection.

		Handles degenerate (zero-length / collapsed) segments identically
		to offset_outline().

		The clamp_factor (0.0-1.0) controls how much of the available space 
		to use: 0.9 means stop at 90% of the medial axis distance.

		Falls back to analytical offset if no SDF is available.

		Args:
			distance (float): Offset amount in font units.
			sdf (SignedDistanceField): Precomputed SDF for the layer.
			curvature_correction (bool): Scale handles by (1 + d * kappa).
			clamp_factor (float): Fraction of medial axis to allow (0.0-1.0).

		Returns:
			Contour: New offset contour.
		'''
		if sdf is None or not sdf.is_computed:
			return self.offset_outline(distance, curvature_correction)

		if len(self.segments) == 0:
			return self.clone()

		# --- Passes 1-2: identical to offset_outline ---
		seg_info, on_disp = self._compute_miter_displacements(distance)

		# --- Pass 3: SDF distance clamping ---
		# Build nid -> node lookup for coordinate access
		node_segs = self.node_segments
		nid_to_node = {}

		for si in range(len(self.segments)):
			nodes = node_segs[si]

			for node in [nodes[0], nodes[-1]]:
				nid_to_node[id(node)] = node

		on_disp_clamped = {}

		for nid, disp in on_disp.items():
			disp_mag = math.sqrt(disp[0] * disp[0] + disp[1] * disp[1])

			if disp_mag < 1e-10:
				on_disp_clamped[nid] = disp
				continue

			node = nid_to_node.get(nid)

			if node is None:
				on_disp_clamped[nid] = disp
				continue

			dx_unit = disp[0] / disp_mag
			dy_unit = disp[1] / disp_mag
			max_safe = disp_mag

			for step_frac in (0.25, 0.5, 0.75, 1.0):
				test_x = node.x + dx_unit * disp_mag * step_frac
				test_y = node.y + dy_unit * disp_mag * step_frac
				sdf_val = sdf.query(test_x, test_y)

				if distance < 0 and sdf_val > 0:
					max_safe = min(max_safe, disp_mag * step_frac * clamp_factor)
					break

				if distance > 0 and sdf_val < 0:
					max_safe = min(max_safe, disp_mag * step_frac * clamp_factor)
					break

			if max_safe < disp_mag:
				scale = max_safe / disp_mag
				on_disp_clamped[nid] = (disp[0] * scale, disp[1] * scale)
			else:
				on_disp_clamped[nid] = disp

		# --- Pass 4: build new contour ---
		# Use clamped effective distance for curvature correction
		return self._build_offset_nodes(
			self.segments, node_segs, seg_info, on_disp_clamped,
			distance, curvature_correction, self.closed
		)

	# -- Angle-compensated scaling via corrective offset ----------------
	@staticmethod
	def _segment_tangent_angles(segment, epsilon=0.5):
		'''Compute tangent angles at segment endpoints.

		Convention:
			theta = 0      -> horizontal tangent
			theta = pi/2   -> vertical tangent

		Args:
			segment: CubicBezier or Line object
			epsilon (float): Below this chord length, segment is degenerate.

		Returns:
			tuple: (theta_start, theta_end) or (None, None) if degenerate
		'''
		if isinstance(segment, CubicBezier):
			chord = abs(segment.p3 - segment.p0)

			if chord < epsilon:
				h_out = abs(segment.p1 - segment.p0)
				h_in = abs(segment.p2 - segment.p3)

				if h_out < epsilon and h_in < epsilon:
					return None, None

			# Start tangent from P0->P1 (or chord as fallback)
			tan0 = segment.p1 - segment.p0
			m0 = abs(tan0)

			if m0 < 1e-10:
				tan0 = segment.p3 - segment.p0
				m0 = abs(tan0)

			theta0 = math.atan2(tan0.y, tan0.x) if m0 > 1e-10 else None

			# End tangent from P2->P3 (or chord as fallback)
			tan3 = segment.p3 - segment.p2
			m3 = abs(tan3)

			if m3 < 1e-10:
				tan3 = segment.p3 - segment.p0
				m3 = abs(tan3)

			theta3 = math.atan2(tan3.y, tan3.x) if m3 > 1e-10 else None

			return theta0, theta3

		elif isinstance(segment, Line):
			dx = segment.p1.x - segment.p0.x
			dy = segment.p1.y - segment.p0.y
			m = math.sqrt(dx * dx + dy * dy)

			if m < epsilon:
				return None, None

			theta = math.atan2(dy, dx)
			return theta, theta

		return None, None

	def scale_compensated(self, sx, sy, stx, sty, intensity=1.0):
		'''Scale contour with diagonal stroke weight compensation.
		Returns a NEW Contour — does not modify the original.

		Two-pass approach:
		  1. Naive affine scale by (sx, sy) — preserves Bezier topology
		  2. Corrective normal offset — fixes diagonal stroke weights

		The correction direction depends on the scaling:
		  Condensing (sx < sy): diagonals get thinned (they were too fat)
		  Expanding  (sx > sy): diagonals get grown (they were too thin)
		  Uniform    (sx == sy): no correction

		Uses the existing miter/normal infrastructure from offset_outline.

		Args:
			sx (float): Horizontal scale factor (must be > 0)
			sy (float): Vertical scale factor (must be > 0)
			stx (float): Horizontal stem width (vertical stroke width)
			sty (float): Vertical stem width (horizontal stroke width)
			intensity (float): Correction strength. Default 1.0.
				0.0 = no correction (pure naive scaling)
				1.0 = standard correction
				>1.0 = amplified correction
				Typical range: 0.5 to 2.0

		Returns:
			Contour: New contour with compensated scaling applied.
		'''
		from typerig.core.func.transform import diagonal_correction_offset

		if len(self.segments) == 0:
			return self.clone()

		segments = self.segments
		node_segs = self.node_segments
		num_seg = len(segments)

		# --- Pass 1: compute tangent angles from ORIGINAL geometry ---
		orig_angles = []

		for segment in segments:
			orig_angles.append(self._segment_tangent_angles(segment))

		# Resolve None angles from degenerate segments
		for si in range(num_seg):
			ts, te = orig_angles[si]

			if ts is None:
				for step in range(1, num_seg):
					ns, ne = orig_angles[(si + step) % num_seg]

					if ns is not None:
						ts = ns
						break

			if te is None:
				for step in range(1, num_seg):
					ns, ne = orig_angles[(si - step) % num_seg]

					if ne is not None:
						te = ne
						break

			orig_angles[si] = (ts if ts is not None else 0.,
							   te if te is not None else 0.)

		# --- Pass 2: clone and naive scale ---
		result = self.clone()

		for node in result.nodes:
			node.x *= sx
			node.y *= sy

		# Early out: no correction needed
		if abs(sx - sy) < 1e-12 or abs(intensity) < 1e-12:
			return result

		# --- Pass 3: compute normals from SCALED geometry ---
		scaled_segments = result.segments
		scaled_node_segs = result.node_segments

		scaled_seg_info = []

		for segment in scaled_segments:
			scaled_seg_info.append(self._segment_normals(segment))

		# --- Pass 4: per-node correction displacements ---
		on_data = {}  # nid -> list of (normal, correction_d)

		for si in range(num_seg):
			nodes = scaled_node_segs[si]
			n_start, n_end, _, _ = scaled_seg_info[si]
			theta_start, theta_end = orig_angles[si]

			d_start = diagonal_correction_offset(
				theta_start, sx, sy, stx, sty, intensity)
			d_end = diagonal_correction_offset(
				theta_end, sx, sy, stx, sty, intensity)

			for node, normal, d in [(nodes[0], n_start, d_start), 
									(nodes[-1], n_end, d_end)]:
				nid = id(node)

				if nid not in on_data:
					on_data[nid] = []

				if normal is not None:
					on_data[nid].append((normal, d))

		# Miter formula with per-node distance
		on_disp = {}

		for nid, entries in on_data.items():
			if len(entries) == 0:
				continue

			elif len(entries) == 1:
				n, d = entries[0]
				on_disp[nid] = (n[0] * d, n[1] * d)

			elif len(entries) == 2:
				(n1, d1), (n2, d2) = entries
				d_avg = (d1 + d2) * 0.5
				dot = n1[0] * n2[0] + n1[1] * n2[1]
				denom = 1.0 + dot

				if denom < 0.15:
					denom = 0.15

				mx = n1[0] + n2[0]
				my = n1[1] + n2[1]
				on_disp[nid] = (d_avg * mx / denom, d_avg * my / denom)

			else:
				d_avg = sum(e[1] for e in entries) / len(entries)
				mx = sum(e[0][0] for e in entries)
				my = sum(e[0][1] for e in entries)
				mag = math.sqrt(mx * mx + my * my)

				if mag > 1e-10:
					on_disp[nid] = (mx / mag * d_avg, my / mag * d_avg)
				else:
					on_disp[nid] = (0., 0.)

		# --- Propagate to orphaned nodes (degenerate segments) ---
		if len(on_disp) < len(on_data):
			junction_ids = []

			for si in range(num_seg):
				nodes = scaled_node_segs[si]
				nid = id(nodes[0])

				if not junction_ids or junction_ids[-1] != nid:
					junction_ids.append(nid)

			n_junctions = len(junction_ids)

			for ji, nid in enumerate(junction_ids):
				if nid in on_disp:
					continue

				fwd_disp = None
				bwd_disp = None

				for step in range(1, n_junctions):
					fwd_nid = junction_ids[(ji + step) % n_junctions]

					if fwd_nid in on_disp:
						fwd_disp = on_disp[fwd_nid]
						break

				for step in range(1, n_junctions):
					bwd_nid = junction_ids[(ji - step) % n_junctions]

					if bwd_nid in on_disp:
						bwd_disp = on_disp[bwd_nid]
						break

				if fwd_disp is not None and bwd_disp is not None:
					on_disp[nid] = (
						(fwd_disp[0] + bwd_disp[0]) * 0.5,
						(fwd_disp[1] + bwd_disp[1]) * 0.5)
				elif fwd_disp is not None:
					on_disp[nid] = fwd_disp
				elif bwd_disp is not None:
					on_disp[nid] = bwd_disp
				else:
					on_disp[nid] = (0., 0.)

		# --- Pass 5: apply correction offsets ---
		return self._build_offset_nodes(
			scaled_segments, scaled_node_segs, scaled_seg_info, on_disp,
			0., False, self.closed
		)

	def scale_compensated_inplace(self, sx, sy, stx, sty, intensity=1.0):
		'''Scale contour in place with diagonal stroke weight compensation.

		Args:
			sx, sy (float): Scale factors (must be > 0)
			stx (float): Horizontal stem width (vertical stroke width)
			sty (float): Vertical stem width (horizontal stroke width)
			intensity (float): Correction strength (0.0=none, 1.0=standard, >1.0=amplified)
		'''
		new_contour = self.scale_compensated(sx, sy, stx, sty, intensity)
		new_nodes = new_contour.nodes

		if len(new_nodes) == len(self.nodes):
			for i in range(len(self.nodes)):
				self.nodes[i].x = new_nodes[i].x
				self.nodes[i].y = new_nodes[i].y

	def delta_scale_compensated(self, delta, stems, scale,
								intensity=1.0, compensation=(0., 0.),
								shift=(0., 0.), italic_angle=False,
								extrapolate=False):
		'''Scale contour using DeltaMachine with diagonal compensation.
		Returns a NEW Contour — does not modify the original.

		Analyzes this contour's dominant stroke angle and adjusts
		the target stems before feeding to DeltaMachine:

		  Condensing (sx < sy): diagonal contours get lighter target stems
		  Expanding  (sx > sy): diagonal contours get heavier target stems
		  Cardinal contours (H/V strokes): no adjustment

		Args:
			delta (DeltaScale): DeltaScale object for this contour.
			stems (tuple): (stx, sty) target stem widths.
			scale (tuple): (sx, sy) scale factors.
			intensity (float): Diagonal compensation strength. Default 1.0.
			compensation (tuple): (cx, cy) DeltaMachine compensation factors.
			shift (tuple): (dx, dy) translation after scaling.
			italic_angle: Italic shear angle in radians, or False.
			extrapolate (bool): Allow extrapolation beyond master range.

		Returns:
			Contour: New contour with delta-scaled coordinates.
		'''
		from typerig.core.func.transform import contour_dominant_angle, adjust_stems_for_angle

		sx, sy = scale
		target_stx, target_sty = stems

		# Analyze contour orientation from on-curve nodes
		on_curve = [(n.x, n.y) for n in self.nodes if n.type == 'on']
		angle = contour_dominant_angle(on_curve)

		# Adjust stems for this contour's angle
		adj_stx, adj_sty = adjust_stems_for_angle(
			target_stx, target_sty, angle, sx, sy, intensity)

		# Apply delta scaling with adjusted stems
		result = list(delta.scale_by_stem(
			(adj_stx, adj_sty),
			(sx, sy),
			compensation,
			shift,
			italic_angle,
			extrapolate
		))

		# Build new contour with scaled coordinates
		new_contour = self.clone()
		new_nodes = new_contour.nodes

		if len(result) == len(new_nodes):
			for i in range(len(new_nodes)):
				new_nodes[i].x = result[i][0]
				new_nodes[i].y = result[i][1]

		return new_contour

	def delta_scale_compensated_inplace(self, delta, stems, scale,
										intensity=1.0, compensation=(0., 0.),
										shift=(0., 0.), italic_angle=False,
										extrapolate=False):
		'''Scale contour in place using DeltaMachine with diagonal compensation.

		Args: Same as delta_scale_compensated().
		'''
		new_contour = self.delta_scale_compensated(
			delta, stems, scale, intensity,
			compensation, shift, italic_angle, extrapolate)

		new_nodes = new_contour.nodes

		if len(new_nodes) == len(self.nodes):
			for i in range(len(self.nodes)):
				self.nodes[i].x = new_nodes[i].x
				self.nodes[i].y = new_nodes[i].y


class HobbySpline(Container): 
	'''Adapted from mp2tikz.py (c) 2012 JL Diaz'''

	def __init__(self, data=None, **kwargs):
		# - Init
		factory = kwargs.pop('default_factory', Knot)

		super(HobbySpline, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		self.tension = kwargs.pop('tension', 1.)
		self.transform = kwargs.pop('transform', Transform())
		self.name = kwargs.pop('name', '')
		self.closed = kwargs.pop('closed', False)
		self.clockwise = kwargs.pop('clockwise', self.get_winding())
		self.curl_start = kwargs.pop('curl_start', 1.)
		self.curl_end = kwargs.pop('curl_end', self.curl_start)

	# - Internals ------------------------------
	def __getitem__(self, index):
		"""Gets the point [i] of the list, but assuming the list is
		circular and thus allowing for indexes greater than the list
		length"""
		index %= len(self.data)
		return self.data[index]

	# - Functions ------------------------------
	def __build_coefficients(self):
		'''This function creates five vectors which are coefficients of a
		linear system which allows finding the right values of 'theta' at
		each point of the path (being 'theta' the angle of departure of the
		path at each point). The theory is from METAFONT book.'''
		
		# - Init
		A=[]; B=[]; C=[]; D=[]; R=[];

		if not self.closed:
			A.append(0) 
			B.append(0)
			
			xi_0 = (self[0].alpha**2) * self.curl_start / (self[1].beta**2)
			
			C.append(xi_0*self[0].alpha + 3 - self[1].beta)
			D.append((3 - self[0].alpha)*xi_0 + self[1].beta)
			R.append(-D[0]*self[1].xi)
		
		for k in self.knot_count:
			A.append(   self[k-1].alpha  / ((self[k].beta**2)  * self[k].d_ant))
			B.append((3-self[k-1].alpha) / ((self[k].beta**2)  * self[k].d_ant))
			C.append((3-self[k+1].beta)  / ((self[k].alpha**2) * self[k].d_post))
			D.append(   self[k+1].beta   / ((self[k].alpha**2) * self[k].d_post))
			R.append(-B[k] * self[k].xi  - D[k] * self[k+1].xi)
		
		if not self.closed:
			n = len(R)
			C.append(0)
			D.append(0)

			xi_n = (self[n].beta**2) * self.curl_end / (self[n-1].alpha**2)

			A.append((3 - self[n].beta)*xi_n + self[n-1].alpha)
			B.append(self[n].beta*xi_n + 3 - self[n-1].alpha)
			R.append(0)

		return (A, B, C, D, R)
		
	# - Procedures ----------------------------
	def __solve_for_thetas(self, A, B, C, D, R):
		'''This function receives the five vectors created by
		__build_coefficients() and uses them to build a linear system with N
		unknonws (being N the number of points in the path). Solving the system
		finds the value for theta (departure angle) at each point'''
		L=len(R)
		a = zero_matrix(L, L)
		b = [[i] for i in R]
		
		for k in range(L):
			prev = (k-1)%L
			post = (k+1)%L
			a[k][prev] = A[k]
			a[k][k]    = B[k]+C[k]
			a[k][post] = D[k]
			
		v = solve_equations(a, b)

		return sum(v,[])

	def __solve_angles(self):
		'''This function receives a path in which each point is 'open', i.e. it
		does not specify any direction of departure or arrival at each node,
		and finds these directions in such a way which minimizes 'mock
		curvature'. The theory is from METAFONT book.'''

		# Basically it solves
		# a linear system which finds all departure angles (theta), and from
		# these and the turning angles at each point, the arrival angles (phi)
		# can be obtained, since theta + phi + xi = 0  at each knot'''

		x = self.__solve_for_thetas(*self.__build_coefficients())
		L = len(self)

		for k in range(L):
			self[k].theta = x[k]

		for k in range(L):
			self[k].phi = - self[k].theta - self[k].xi

	def __find_controls(self):
		'''This function receives a path in which, for each point, the values
		of theta and phi (leave and enter directions) are known, either because
		they were previously stored in the structure, or because it was
		computed by function __solve_angles(). From this path description
		this function computes the control points for each knot and stores
		it in the path. After this, it is possible to print path to get
		a string suitable to be feed to tikz.'''

		# - Calculate bezier control points
		for kid in range(len(self.knots)):
			z0 = self[kid].complex
			z1 = self[kid + 1].complex
			theta = self[kid].theta
			phi = self[kid + 1].phi
			alpha = self[kid].alpha
			beta = self[kid + 1].beta

			u, v = hobby_control_points(z0, z1, theta, phi, alpha, beta)

			self[kid].u_right = u
			self[kid + 1].v_left = v

	def reverse(self):
		self.data = list(reversed(self.data))
		#self.clockwise = self.get_winding()
		self.clockwise = not self.clockwise

	def set_start(self, index):
		index = self.nodes[index].prev_on.idx if not self.nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index] 

	def get_winding(self):
		'''Check if contour has clockwise winding direction'''
		return self.get_area() > 0

	def get_area(self):
		'''Get contour area using on curve points only'''
		polygon_area = []

		for knot in self.knots:
			edge_sum = (knot.next.x - knot.x)*(knot.next.y + knot.y)
			polygon_area.append(edge_sum)

		return sum(polygon_area)*0.5

	# - Transformation --------------------------
	def apply_transform(self):
		for knot in self.knots:
			knot.x, knot.y = self.transform.applyTransformation(knot.x, knot.y)

	def shift(self, delta_x, delta_y):
		for knot in self.knots:
			knot.point += Point(delta_x, delta_y)

	# - Properties -----------------------------------
	@property
	def knots(self):
		return self.data

	@knots.setter
	def knots(self, other):
		if isinstance(other, self.__class__):
			self.data = other

		if isinstance(other, (tuple, list)):
			for item in other:
				if not isinstance(item, self._subclass):
					item = self._subclass(item, parent=self)
					self.data.append(item)

	@property
	def knot_count(self):
		if self.closed:
			return range(len(self.data))
		else:
			return range(1, len(self.data) - 1)

	@property
	def tension(self):
		return self.global_tension

	@tension.setter
	def tension(self, other):
		self.global_tension = other
		
		for knot in self.knots:
			knot.alpha = other
			knot.beta = other

	@property
	def bounds(self):
		assert len(self.knots) > 0, 'Cannot return bounds for <{}> with length {}'.format(self.__class__.__name__, len(self.knots))
		return Bounds([knot.point.tuple for knot in self.knots])

	@property
	def nodes(self):
		self.__solve_angles()
		self.__find_controls()

		# - Init
		return_nodes = []
		count = len(self.knots)
		last = 1

		# - Calculate beziers
		if self.closed:
			last = 0

		for kid in range(count - last):
			post = (kid + 1) %count
			z = self.knots[kid].point
			u = Point(self.knots[kid].u_right.real, self.knots[kid].u_right.imag)
			v = Point(self.knots[post].v_left.real, self.knots[post].v_left.imag)
			return_nodes.append([Node(z.x, z.y, type='on'), Node(u.x, u.y, type='curve'), Node(v.x, v.y, type='curve')])
		
		if self.closed:
			last_z = self[0].point
		else:
			last_z = self[-1].point
		
		return_nodes.append([Node(last_z.x, last_z.y, type='on')])
		
		return sum(return_nodes, [])



if __name__ == '__main__':
	from pprint import pprint
	section = lambda s: '\n+{0}\n+ {1}\n+{0}'.format('-'*30, s)

	# - Test Sources
	src_frame = [	Node(200.0, 280.0, type='on'),
					Node(760.0, 280.0, type='on'),
					Node(804.0, 280.0, type='curve'),
					Node(840.0, 316.0, type='curve'),
					Node(840.0, 360.0, type='on'),
					Node(840.0, 600.0, type='on'),
					Node(840.0, 644.0, type='curve'),
					Node(804.0, 680.0, type='curve'),
					Node(760.0, 680.0, type='on', selected=True),
					Node(200.0, 680.0, type='on'),
					Node(156.0, 680.0, type='curve'),
					Node(120.0, 644.0, type='curve'),
					Node(120.0, 600.0, type='on'),
					Node(120.0, 360.0, type='on'),
					Node(120.0, 316.0, type='curve'),
					Node(156.0, 280.0, type='curve')]

	src_square = [	Node(200.0, 280.0, type='on'),
					Node(280.0, 280.0, type='on', selected=True),
					Node(280.0, 200.0, type='on'),
					Node(200.0, 200.0, type='on')]

	src_circle = [	Node(161.0, 567.0, type='on'),
					Node(161.0, 435.0, type='curve'),
					Node(268.0, 328.0, type='curve'),
					Node(400.0, 328.0, type='on', selected=True),
					Node(531.0, 328.0, type='curve'),
					Node(638.0, 435.0, type='curve'),
					Node(638.0, 567.0, type='on'),
					Node(638.0, 698.0, type='curve'),
					Node(531.0, 805.0, type='curve'),
					Node(400.0, 805.0, type='on'),
					Node(268.0, 805.0, type='curve'),
					Node(161.0, 698.0, type='curve')]

	# - Tests
	frame = Contour(src_frame, closed=True)
	square = Contour(src_square, closed=True)
	circle = Contour(src_circle, closed=True)
	print(section('Contour'))
	pprint(frame)
	
	# - rounded_frame segments
	print(section('Segments Nodes'))
	pprint(frame.node_segments)

	print(section('Object Segments'))
	pprint(frame.segments)

	print(section('Truth rounded_frames'))
	print(frame[0] == frame.node_segments[0][0] == frame.segments[0].p0)

	'''
	print(section('Value assignment'))
	tl = frame.segments[0]
	tl.p0.x = 999.999999999
	print(tl, c[0])

	print(section('Change assignment'))
	pprint(c)
	c[0].point -= 900

	print(section('Next and previous on curve finder'))
	print(c[1],c[1].next_on.prev_on)
	'''

	print(section('Bounds'))
	print(frame.bounds)

	print(section('Node operations'))
	print(frame.selected_nodes[0].clockwise)
	print(frame.selected_nodes[0].segment)

	'''
	print(section('Node operations'))
	print(c.selected_nodes[0].triad)
	c.selected_nodes[0].smart_shift(10,10)
	print(c.selected_nodes[0].triad)
	'''
	'''
	print(section('Corner Mitre'))
	pprint(c.nodes)
	print(c.selected_nodes[0].corner_mitre(10))
	pprint(c.nodes)

	print(section('Corner Round'))
	pprint(square.nodes)
	ss = square.selected_nodes[0].corner_round(10, proportion=.5)
	pprint(square.nodes)
	'''
	'''
	print(section('Insert After'))
	#pprint(circle.nodes)
	print(circle[0].next)

	print(section('Contour winding'))
	print(frame)
	print(frame.clockwise)
	frame.reverse()
	print(frame.clockwise)
	print(frame)

	hobby_test = HobbySpline([(0,320), (320,640), (640,320), (320,0)])
	hobby_test.tension = 1.1
	print(hobby_test.knots)
	print(hobby_test.nodes)
	'''
	print(section('Serialization'))
	print(frame.to_XML())