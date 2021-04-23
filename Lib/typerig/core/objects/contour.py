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
from typerig.core.objects.transform import Transform
from typerig.core.objects.node import Node
from typerig.core.objects.utils import Bounds

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.0.5'

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
		return Bounds([node.point.tuple for node in self.data])

	@property
	def segments(self):
		return self.getSegments(False)
		
	# -- Functions ------------------------------
	def getSegments(self, asPoint=False):
		assert len(self.data) > 1, 'Cannot return segments for contour with length {}'.format(len(self.data))
		contour_segments = []
		contour_nodes = self.data
		if self.closed: contour_nodes.append(contour_nodes[0])

		while len(contour_nodes):
			node = contour_nodes.pop(0)
			segment = [node.point if asPoint else node]

			for node in contour_nodes:
				segment.append(node.point if asPoint else node)
				if node.isOn: break

			contour_segments.append(segment)
			contour_nodes = contour_nodes[len(segment)-2:]

		return contour_segments[:-1]


	# -- IO Format ------------------------------
	def toVFJ(self):
		pass

	@staticmethod
	def fromVFJ(string):
		pass

if __name__ == '__main__':
	from pprint import pprint
	from typerig.core.objects.line import Line
	from typerig.core.objects.cubicbezier import CubicBezier

	# - Test initialization 
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
	
	# - Test segments
	print(c.segments)
	print(c.getSegments(True))

	# - Test segment creation
	obj_segments = []
	for segment in c.getSegments(True):
		if len(segment) == 2:
			obj_segments.append(Line(*segment))
		if len(segment) == 4:
			obj_segments.append(CubicBezier(*segment))

	print(obj_segments)




	
	
