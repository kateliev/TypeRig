# MODULE: TypeRig / Core / Node (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.point import Point

# - Init -------------------------------
__version__ = '0.0.4'
node_types = ['move', 'line', 'offcurve', 'curve', 'qcurve']

# - Classes -----------------------------
class Node(Point): 
	def __init__(self, *args, **kwargs):
		super(Node, self).__init__(*args)
		
		self.type = kwargs.get('type','line')
		self.smooth = kwargs.get('smooth', False)
		self.name = kwargs.get('name', None)
		self.id = kwargs.get('id', None)
		self.g2 = kwargs.get('g2', False)

	def __repr__(self):
		return '<Node: x={}, y={}, type={}>'.format(self.x, self.y, self.type)

	# -- Properties
	@property
	def tuple(self):
		return (self.x, self.y, self.type, self.smooth, self.name, self.id)

	@property
	def point(self):
		return Point(self.x, self.y)

	# -- Specials
	@property
	def string(self):
		node_config = []
		x = int(self.x) if self.x.is_integer() else self.x
		y = int(self.y) if self.y.is_integer() else self.y
		
		node_config.append(str(x))
		node_config.append(str(y))

		if self.smooth: node_config.append('s')
		#if self.type == 'offcurve': node_config.append('o')
		if self.g2: node_config.append('g2')

		return ' '.join(node_config)

	def dumps(self):
		return self.string

	@staticmethod
	def loads(string):
		string_list = string.split(' ')
		node_smooth = True if len(string_list) >= 3 and 's' in string_list else False
		node_type = 'offcurve' if len(string_list) >= 3 and 'o' in string_list else None
		node_g2 = True if len(string_list) >= 3 and 'g2' in string_list else False

		return Node(float(string_list[0]), float(string_list[1]), type=node_type, smooth=node_smooth, g2=node_g2, name=None, id=None)

	

	#!!!TODO: .xml, .toXML(), .fromXML() for UFO support


if __name__ == '__main__':
	n = Node.loads('10 20 s g2')
	print(n.dumps())