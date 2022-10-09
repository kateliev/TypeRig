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

from typerig.core.objects.atom import Container
from typerig.core.objects.layer import Layer

# - Init -------------------------------
__version__ = '0.1.5'

# - Classes -----------------------------
class Glyph(Container): 
	__slots__ = ('name', 'mark', 'unicodes', 'identifier', 'parent')

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Layer)
		super(Glyph, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.identifier = kwargs.pop('identifier', None)
			self.mark = kwargs.pop('mark', 0)
			self.name = kwargs.pop('name', hash(self))
			self.unicodes = kwargs.pop('unicodes', [])

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
		data_array = []
		stem_array = []
		
		for layer_name in layer_names_list:
			work_layer = self.layer(layer_name)
			if hasattr(work_layer, attrib):
				data_array.append(getattr(work_layer, attrib))
				stem_array.append([work_layer.stems])

		return DeltaScale(data_array, stem_array)

	def virtual_axis(self, layer_names_list):
		process_attrib_list = ('node_array', 'metric_array') # 'anchor_array'
		return {attrib: self.build_delta(layer_names_list, attrib) for attrib in process_attrib_list}

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

	# -- IO Format ------------------------------
	def to_VFJ(self):
		raise NotImplementedError

	@staticmethod
	def from_VFJ(string):
		raise NotImplementedError

	@staticmethod
	def to_XML(self):
		raise NotImplementedError

	@staticmethod
	def from_XML(string):
		raise NotImplementedError


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
	print(g.virtual_axis(('Regular', 'Regular')))


	





	
	
