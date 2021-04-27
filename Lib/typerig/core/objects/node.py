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
import copy

from typerig.core.objects.point import Point
from typerig.core.objects.transform import Transform

from typerig.core.func.utils import isMultiInstance
from typerig.core.objects.atom import Member, Container

# - Init -------------------------------
__version__ = '0.2.2'
node_types = {'on':'on', 'off':'off', 'curve':'curve', 'move':'move'}

# - Classes -----------------------------
class Node(Member): 
	def __init__(self, *args, **kwargs):
		super(Node, self).__init__(*args, **kwargs)
		self.parent = kwargs.get('parent', None)

		# - Basics
		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.x, self.y = args[0].x, args[0].y

			if isinstance(args[0], (tuple, list)):
				self.x, self.y = args[0]

		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				self.x, self.y = float(args[0]), float(args[1])
		
		else:
			self.x, self.y = 0., 0.

		self.angle = kwargs.get('angle', 0)
		self.transform = kwargs.get('transform', Transform())
		self.complex_math = kwargs.get('complex', True)

		# - Metadata
		self.type = kwargs.get('type', node_types['on'])
		self.smooth = kwargs.get('smooth', False)
		self.name = kwargs.get('name', '')
		self.identifier = kwargs.get('identifier', None)
		self.g2 = kwargs.get('g2', False)

	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: x={}, y={}, type={}>'.format(self.__class__.__name__, self.x, self.y, self.type)

	# -- Properties -----------------------------
	@property
	def index(self):
		return self.idx

	@property
	def point(self):
		return Point(self.x, self.y, angle=self.angle, transform=self.transform, complex=self.complex_math)

	@point.setter
	def point(self, other):
		if isinstance(other, (self.__class__, Point)):
			self.x = other.x 
			self.y = other.y 
			self.angle = other.angle 
			self.transform = other.transform 
			self.complex_math = other.complex_math 
	
	@property
	def isOn(self):
		return self.type == node_types['on']

	@property
	def nextOn(self):
		assert self.parent is not None, 'Orphan Node: Cannot find Next on-curve node!'
		currentNode = self.next
		
		while currentNode is not None and not currentNode.isOn:
			currentNode = currentNode.next
		
		return currentNode

	@property
	def prevOn(self):
		assert self.parent is not None, 'Orphan Node: Cannot find Previous on-curve node!'
		currentNode = self.prev
		
		while currentNode is not None and not currentNode.isOn:
			currentNode = currentNode.prev
		
		return currentNode

	# -- IO Format ------------------------------
	@property
	def string(self):
		x = int(self.x) if isinstance(self.x, float) and self.x.is_integer() else self.x
		y = int(self.y) if isinstance(self.y, float) and self.y.is_integer() else self.y
		return '{0}{2}{1}'.format(x, y, ' ')

	def toVFJ(self):
		node_config = []
		node_config.append(self.string)
		if self.smooth: node_config.append('s')
		if not self.isOn: node_config.append('o')
		if self.g2: node_config.append('g2')

		return ' '.join(node_config)

	@staticmethod
	def fromVFJ(string):
		string_list = string.split(' ')
		node_smooth = True if len(string_list) >= 3 and 's' in string_list else False
		node_type = node_types['off'] if len(string_list) >= 3 and 'o' in string_list else node_types['on']
		node_g2 = True if len(string_list) >= 3 and 'g2' in string_list else False

		return Node(float(string_list[0]), float(string_list[1]), type=node_type, smooth=node_smooth, g2=node_g2, name=None, identifier=None)

	@staticmethod
	def toXML(self):
		raise NotImplementedError

	@staticmethod
	def fromXML(string):
		raise NotImplementedError


if __name__ == '__main__':
	# - Test initialization, normal and rom VFJ
	n0 = Node.fromVFJ('10 20 s g2')
	n1 = Node.fromVFJ('20 30 s')
	n2 = Node(35, 55.65)
	n3 = Node(44, 67, type='smooth')
	n4 = Node(n3)
	print(n3, n4)
	
	# - Test math and VFJ export
	n3.point = Point(34,88)
	n3.point += 30
	print(n3.toVFJ())
	
	# - Test Containers and VFJ export 
	c = Container([n0, n1, n2, n3, n4], default_factory=Node)
	c.append((99,99))
	print(n0.next)
	
