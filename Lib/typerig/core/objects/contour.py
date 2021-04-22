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
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.utils import Bounds

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.0.1'

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
		return Bounds([node.point.tuple for node in self.data])

	@property
	def segments(self):
		segments = []
		
		for node in self.data:
			accum = []

			if node.isOn and len(accum) < 2:
				accum.append(node.point)



	# -- IO Format ------------------------------
	def toVFJ(self):
		pass

	@staticmethod
	def fromVFJ(string):
		pass

if __name__ == '__main__':
	n0 = Node.fromVFJ('10 20 s g2')
	n1 = Node.fromVFJ('20 30 s')
	n2 = Node(35, 55.65)
	n3 = Node(44, 67, type='smooth')
	n4 = Node(n3)
	
	print(n3, n4)
	n3.point = Point(34,88)
	n3.point += 30
	print(n3.toVFJ())
	
	c = Contour([(1,2), (44, 534)])
	c.append((99,99))
	c.append(n0)
	print(c.bounds)

	
	
