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
__version__ = '0.1.1'

# - Classes -----------------------------
class Contour(Container): 
	def __init__(self, data=None, **kwargs):
		super(Contour, self).__init__(data, default_factory=Node, **kwargs)
		self.name = kwargs.get('name', None)
		self.transform = kwargs.get('transform', Transform())
		self.identifier = kwargs.get('identifier', None)
		self.closed = kwargs.get('closed', False)
		self.ccw = kwargs.get('ccw', False)

	def __repr__(self):
		return '<{}: {}>'.format(self.__class__.__name__, self.data)
	
	# -- Properties -----------------------------
	@property
	def bounds(self):
		assert len(self.data) > 0, 'Cannot return bounds for contour with length {}'.format(len(self.data))
		return Bounds([node.tuple for node in self.data])

	@property
	def nodeSegments(self):
		return self.getSegments()

	@property
	def segments(self):
		obj_segments = []

		for segment in self.getSegments():
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
	def getSegments(self):
		assert len(self.data) > 1, 'Cannot return segments for contour with length {}'.format(len(self.data))
		contour_segments = []
		contour_nodes = self.data
		if self.closed: contour_nodes.append(contour_nodes[0])

		while len(contour_nodes):
			node = contour_nodes[0]
			contour_nodes= contour_nodes[1:]
			segment = [node]

			for node in contour_nodes:
				segment.append(node)
				if node.isOn: break

			contour_segments.append(segment)
			contour_nodes = contour_nodes[len(segment)-2:]

		return contour_segments[:-1]

	# -- IO Format ------------------------------
	def toVFJ(self):
		raise NotImplementedError

	@staticmethod
	def fromVFJ(string):
		raise NotImplementedError

	@staticmethod
	def toXML(self):
		raise NotImplementedError

	@staticmethod
	def fromXML(string):
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
			Node(760.0, 680.0, type='on'),
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
	pprint(c.nodeSegments)

	print(section('Object Segments'))
	pprint(c.segments)

	print(section('Truth tests'))
	print(c[0] == c.nodeSegments[0][0] == c.segments[0].p0)

	print(section('Value assignment'))
	tl = c.segments[0]
	tl.p0.x = 999.999999999
	print(tl, c[0])

	print(section('Change assignment'))
	pprint(c)
	c[0].point -= 900

	print(section('Next and previous on curve finder'))
	print(c[1],c[1].nextOn.prevOn)





	
	
