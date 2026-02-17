# MODULE: Typerig / Proxy / Node (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import copy

import fontlab as fl6
from typerig.core.objects.node import Node
from typerig.core.func.utils import isMultiInstance

# - Init ---------------------------------
__version__ = '0.3.0'
	
# - Classes -------------------------------
class trNode(Node):
	'''Proxy to flNode object

	Constructor:
		trNode(flNode)

	Attributes:
		.host (flNode): Original flNode 
		.parent (trContour): parent contour
		.contour (trContour): parent contour
	'''
	# - Metadata and proxy model
	#__slots__ = ('host', 'x', 'y', 'type', 'name', 'smooth', 'g2', 'selected', 'angle', 'transform', 'identifier','complex_math', 'parent', 'lib')
	__meta__ = {'x':'x', 'y':'y', 'type':'type', 'g2':'g2', 'smooth':'smooth', 'name':'name', 'selected':'selected'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, *args, **kwargs):

		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.host = fl6.flNode(args[0].host)
				x, y = self.host.x, self.host.y, 
				
			if isinstance(args[0], fl6.flNode):
				self.host = args[0]
				x, y = self.host.x, self.host.y, 

			if isinstance(args[0], (tuple, list)):
				x, y = args[0]
				node_type = kwargs.get('type', 'on')
				self.host = fl6.flNode(x, y, nodeType=node_type)
				
		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				x, y = float(args[0]), float(args[1])
				node_type = kwargs.get('type', 'on')
				self.host = fl6.flNode(x, y, nodeType=node_type)

		super(trNode, self).__init__(x, y, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trNode.__meta_keys:
			return self.host.__getattribute__(trNode.__meta__[name])
		else:
			return Node.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trNode.__meta_keys:
			self.host.__setattr__(trNode.__meta__[name], value)
		else:
			Node.__setattr__(self, name, value)

	# - Basics ---------------------------------
	def clone(self):
		new_node = self.host.clone()
		return self.__class__(new_node)

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Node with current FL values.
		The returned Node has no FL bindings and can be freely manipulated.
		'''
		return Node(
			float(self.x), float(self.y),
			type=self.type,
			smooth=self.smooth,
			name=self.name,
			g2=self.g2,
			selected=self.selected
		)

	def mount(self, core_node):
		'''Write core Node values back into the FL host.
		
		Args:
			core_node (Node): Pure core Node with values to apply.
		'''
		self.host.x = float(core_node.x)
		self.host.y = float(core_node.y)
		self.host.type = core_node.type
		self.host.smooth = core_node.smooth

		if hasattr(core_node, 'name') and core_node.name:
			self.host.name = core_node.name

	# - Effects --------------------------------
	def getSmartAngle(self):
		return (self.host.isSmartAngle(), self.host.smartAngleR)

	def setSmartAngle(self, radius):
		self.host.smartAngleR = radius
		return self.host.setSmartAngleEnbl(True)

	def delSmartAngle(self):
		return self.host.setSmartAngleEnbl(False)

	def setSmartAngleRadius(self, radius):
		self.host.smartAngleR = radius

	def getSmartAngleRadius(self):
		return self.host.smartAngleR
