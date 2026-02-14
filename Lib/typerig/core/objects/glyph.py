# MODULE: TypeRig / Core / Glyph (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds
from typerig.core.objects.delta import DeltaScale

from typerig.core.fileio.xmlio import XMLSerializable, register_xml_class

from typerig.core.objects.atom import Container
from typerig.core.objects.layer import Layer

# - Init -------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
@register_xml_class
class Glyph(Container, XMLSerializable): 
	__slots__ = ('name', 'mark', 'unicodes', 'identifier', 'parent', 'selected')

	XML_TAG = 'glyph'
	XML_ATTRS = ['name', 'identifier', 'unicodes', 'selected', 'mark']
	XML_CHILDREN = {'layer': 'layers'}
	XML_LIB_ATTRS = []

	def __init__(self, layers=None, **kwargs):
		factory = kwargs.pop('default_factory', Layer)
		super(Glyph, self).__init__(layers, default_factory=factory, **kwargs)
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.identifier = kwargs.pop('identifier', None)
			self.mark = kwargs.pop('mark', 0)
			self.name = kwargs.pop('name', hash(self))
			self.unicodes = kwargs.pop('unicodes', [])
			self.selected = kwargs.pop('selected', False)

		#self.active_layer = kwargs.pop('active_layer', None)
		
	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Unicode={}, Layers={}>'.format(self.__class__.__name__,self.name, self.unicode, repr(self.data))

	# -- Functions ------------------------------
	def layer(self, layer_name=None):
		if layer_name is None and hasattr(self, 'active_layer'): 
			layer_name = self.active_layer 

		for layer in self.layers:
			if layer.name == layer_name: return layer
		return

	def shapes(self, layer_name=None):
		return self.layer(layer_name).shapes

	def contours(self, layer_name=None):
		return self.layer(layer_name).contours

	def nodes(self, layer_name=None):
		return self.layer(layer_name).nodes

	def selected_nodes(self, layer_name=None):
		return self.layer(layer_name).selected_nodes

	# -- Delta related ----------------------------
	def build_delta(self, layer_names_list, attrib):
		'''Build a DeltaScale object for a specific attribute across multiple layers.
		
		Args:
			layer_names_list (list): List of layer names to include in the delta
			attrib (str): Attribute name to extract ('point_array', 'metric_array', etc.)
			
		Returns:
			DeltaScale: Delta scale object for interpolation/extrapolation
		'''
		data_array = []
		stem_array = []
		
		for layer_name in layer_names_list:
			work_layer = self.layer(layer_name)
			
			if work_layer is None:
				raise ValueError('Layer "{}" not found in glyph "{}"'.format(layer_name, self.name))
			
			if not hasattr(work_layer, attrib):
				raise AttributeError('Layer "{}" does not have attribute "{}"'.format(layer_name, attrib))
			
			# Get the attribute data
			attr_data = getattr(work_layer, attrib)
			
			# Convert PointArray to list of tuples if needed
			if hasattr(attr_data, 'tuple'):
				data_array.append(list(attr_data.tuple))
			else:
				data_array.append(attr_data)
			
			# Get stems for this layer
			if work_layer.has_stems:
				stem_array.append([work_layer.stems])
			else:
				raise ValueError('Layer "{}" does not have stems defined. Use layer.stems = (stx, sty)'.format(layer_name))

		return DeltaScale(data_array, stem_array)

	def create_virtual_axis(self, layer_names, attributes=None):
		'''Create a virtual axis from a list of layer names.
		
		This is the main method to set up interpolation/extrapolation between layers.
		
		Args:
			layer_names (list): List of layer names in order (e.g., ['Light', 'Regular', 'Bold'])
			attributes (list, optional): Attributes to process. Defaults to ['point_array', 'metric_array']
			
		Returns:
			dict: Dictionary with attribute names as keys and DeltaScale objects as values
			
		Example:
			>>> glyph = Glyph(...)
			>>> # Set stems for each layer first
			>>> glyph.layer('Light').stems = (80, 80)
			>>> glyph.layer('Regular').stems = (100, 100)
			>>> glyph.layer('Bold').stems = (140, 140)
			>>> 
			>>> # Create the virtual axis
			>>> axis = glyph.create_virtual_axis(['Light', 'Regular', 'Bold'])
			>>> 
			>>> # Scale a layer using the axis (non-destructive)
			>>> new_layer = glyph.layer('Regular').scale_with_axis(axis, target_width=600)
		'''
		if attributes is None:
			attributes = ['point_array', 'metric_array']
		
		if not isinstance(layer_names, (list, tuple)) or len(layer_names) < 2:
			raise ValueError('layer_names must be a list of at least 2 layer names')
		
		return {attrib: self.build_delta(layer_names, attrib) for attrib in attributes}
	
	# Keep old name for backward compatibility
	def virtual_axis(self, layer_names_list, process_attrib_list=('point_array','metric_array')):
		'''Deprecated: Use create_virtual_axis() instead.'''
		return self.create_virtual_axis(layer_names_list, process_attrib_list)

	# -- Properties -----------------------------
	@property
	def layers(self):
		return self.data

	@property
	def unicode(self):
		return self.unicodes[0] if len(self.unicodes) else None

	@unicode.setter
	def unicode(self, value):
		try:
			self.unicodes[0] = values
		except (IndexError, AttributeError):
			self.unicodes = [value]

	@property
	def is_compatible(self):
		return all([layer.is_compatible(self.layers[0]) for layer in self.layers])

	# - Functions -------------------------------
	def set_mark(self, value):
		self.mark = value

		for layer in self.layers:
			layer.mark = value

	# -- Per-contour delta building --------------------------------
	def build_contour_deltas(self, layer_names):
		'''Build per-contour DeltaScale objects from master layers.

		Instead of a single DeltaScale for all points on the layer,
		this creates one DeltaScale per contour. Each contour delta
		can then be scaled with its own stems, enabling angle-dependent
		weight compensation for diagonal strokes.

		Requires compatible contour structure across all listed layers
		(same number of contours, same number of nodes per contour — 
		standard MM compatibility).

		All layers must have stems defined (layer.stems = (stx, sty)).

		Args:
			layer_names (list): Layer names in order (e.g., ['Regular', 'Bold']).
				Must be at least 2 layers.

		Returns:
			list[DeltaScale]: One DeltaScale per contour, in contour order
				matching layer.contours.
		'''
		assert len(layer_names) >= 2, \
			'Need at least 2 layers, got {}'.format(len(layer_names))

		# Collect per-layer contour data
		layers = []

		for name in layer_names:
			layer = self.layer(name)
			assert layer is not None, \
				'Layer "{}" not found in glyph "{}"'.format(name, self.name)
			assert layer.has_stems, \
				'Layer "{}" has no stems. Set layer.stems = (stx, sty)'.format(name)
			layers.append(layer)

		# Verify contour compatibility
		num_contours = len(layers[0].contours)

		for li, layer in enumerate(layers[1:], 1):
			assert len(layer.contours) == num_contours, \
				'Contour count mismatch: "{}" has {}, "{}" has {}'.format(
					layer_names[0], num_contours,
					layer_names[li], len(layer.contours))

		# Build per-contour DeltaScale objects
		contour_deltas = []

		for ci in range(num_contours):
			contour_points = []
			contour_stems = []

			for layer in layers:
				contour = layer.contours[ci]
				points = [(n.x, n.y) for n in contour.nodes]
				contour_points.append(points)
				contour_stems.append([layer.stems])

			contour_deltas.append(DeltaScale(contour_points, contour_stems))

		return contour_deltas

	def build_contour_deltas_with_metrics(self, layer_names):
		'''Build per-contour DeltaScale objects plus a metric DeltaScale.

		Same as build_contour_deltas but also returns a DeltaScale for
		the metric_array (advance width, advance height), which should
		be scaled with the global stems (not per-contour adjusted stems).

		Args:
			layer_names (list): Layer names in order.

		Returns:
			tuple: (list[DeltaScale], DeltaScale)
				First element: per-contour DeltaScales
				Second element: metric DeltaScale for advance width/height
		'''
		contour_deltas = self.build_contour_deltas(layer_names)
		metric_delta = self.build_delta(layer_names, 'metric_array')

		return contour_deltas, metric_delta

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

	l = Layer([[test]], name='Regular')
	g = Glyph([l, [[test]]], name='Vassil')
	print(section('Segments'))
	print(g.layers[0].shapes[0].contours[0].segments)
		
	print(section('Glyph Layers'))
	print(g.nodes('Regular')[0].parent)
	g.layer('Regular').stems = (100,50)
	#print(g.virtual_axis(('Regular', 'Regular')))

	print(g.to_XML())
