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
import copy

from typerig.core.objects.point import Point
from typerig.core.objects.node import Node
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.2.0'

# - Classes -----------------------------
class Contour(Container): 
	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Node)
		super(Contour, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		self.name = kwargs.pop('name', '')
		self.transform = kwargs.pop('transform', Transform())
		self.identifier = kwargs.pop('identifier', None)
		self.closed = kwargs.pop('closed', False)
		self.ccw = kwargs.pop('ccw', False)
		
	# -- Properties -----------------------------
	@property
	def nodes(self):
		return self.data

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
		
	# -- Functions ------------------------------
	def get_segments(self, get_point=False):
		assert len(self.data) > 1, 'Cannot return segments for contour with length {}'.format(len(self.data))
		contour_segments = []
		contour_nodes = self.data
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

	test = [Node(200.0, 280.0, type='on'),
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

	c = Contour(test, closed=True)
	print(section('Contour'))
	pprint(c)
	
	# - Test segments
	print(section('Segments Nodes'))
	pprint(c.node_segments)

	print(section('Object Segments'))
	pprint(c.segments)

	print(section('Truth tests'))
	print(c[0] == c.node_segments[0][0] == c.segments[0].p0)

	print(section('Value assignment'))
	tl = c.segments[0]
	tl.p0.x = 999.999999999
	print(tl, c[0])

	print(section('Change assignment'))
	pprint(c)
	c[0].point -= 900

	print(section('Next and previous on curve finder'))
	print(c[1],c[1].next_on.prev_on)

	print(section('Bounds'))
	print(c.bounds)

	print(section('Node operations'))
	print(c.selected_nodes[0].clockwise)

	print(section('Node operations'))
	print(c.selected_nodes[0].triad)
	c.selected_nodes[0].smart_shift(10,10)
	print(c.selected_nodes[0].triad)





	
	
