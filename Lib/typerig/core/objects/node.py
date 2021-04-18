# MODULE: TypeRig / Core / Node (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.point import Point
from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.0.8'
node_types = ['move', 'line', 'offcurve', 'curve', 'qcurve']

# - Classes -----------------------------
class Node(Member): 
	def __init__(self, *args, **kwargs):
		super(Node, self).__init__(**kwargs)
		cloned = False

		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.x, self.y, self.type, self.smooth, self.name, self.identifier, self.g2 = args[0].tuple
				self.parent = args[0].parent
				cloned = True

			if isinstance(args[0], (tuple, list)):
				self.x, self.y = args[0]

		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				self.x, self.y = float(args[0]), float(args[1])
		
		else:
			self.x, self.y = 0., 0.

		if not cloned:
			self.type = kwargs.get('type','line')
			self.smooth = kwargs.get('smooth', False)
			self.name = kwargs.get('name', None)
			self.identifier = kwargs.get('identifier', None)
			self.g2 = kwargs.get('g2', False)

	def __repr__(self):
		return '<{}: x={}, y={}, type={}>'.format(self.__class__.__name__, self.x, self.y, self.type)

	# -- Properties
	@property
	def tuple(self):
		return (self.x, self.y, self.type, self.smooth, self.name, self.identifier, self.g2)

	@property
	def point(self):
		return Point(self.x, self.y)

	@point.setter
	def point(self, other):
		new_point = Point(other)
		self.x, self.y = new_point.tuple

	# -- IO Format
	def toVFJ(self):
		node_config = []
		x = int(self.x) if isinstance(self.x, float) and self.x.is_integer() else self.x
		y = int(self.y) if isinstance(self.y , float) and self.y.is_integer() else self.y
		
		node_config.append(str(x))
		node_config.append(str(y))

		if self.smooth: node_config.append('s')
		#if self.type == 'offcurve': node_config.append('o')
		if self.g2: node_config.append('g2')

		return ' '.join(node_config)

	@staticmethod
	def fromVFJ(string):
		string_list = string.split(' ')
		node_smooth = True if len(string_list) >= 3 and 's' in string_list else False
		node_type = 'offcurve' if len(string_list) >= 3 and 'o' in string_list else None
		node_g2 = True if len(string_list) >= 3 and 'g2' in string_list else False

		return Node(float(string_list[0]), float(string_list[1]), type=node_type, smooth=node_smooth, g2=node_g2, name=None, identifier=None)

	#!!!TODO: .xml, .toXML(), .fromXML() for UFO support

if __name__ == '__main__':
	n0 = Node.fromVFJ('10 20 s g2')
	n1 = Node.fromVFJ('20 30 s')
	n2 = Node(35, 55)
	n3 = Node(44, 67)
	n4 = Node(n3)
	
	print(n3)
	n3.point = Point(34,88)
	n3.point += 30
	print(n3.toVFJ())
	
	c = Container([n0, n1, n2, n3, n4], default_factory=Node)
	c.append((99,99))

	print(n0.next.next.toVFJ())
	print(type(n0.parent))
	
	for n in c:
		print(n.toVFJ())
