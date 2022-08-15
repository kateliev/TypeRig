# MODULE: Typerig / Proxy / Node (Object)
# NOTE: Experimental proxy approach
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import copy

import GlyphsApp

from typerig.core.objects.node import Node
from typerig.core.func.utils import isMultiInstance

# - Init ---------------------------------
__version__ = '0.1.1'
	
# - Classes -------------------------------
class trNode(Node):
	'''Proxy to GSNode object

	Constructor:
		trNode(GSNode)

	Attributes:
		.host (GSNode): Original GSNode 
		.parent (trContour): parent contour
		.contour (trContour): parent contour
	'''
	# - Metadata and proxy model
	__meta__ = {'x':'x', 'y':'y', 'type':'type', 'smooth':'smooth', 'name':'name', 'selected':'selected'}

	# - Initialize ---------------------------
	def __init__(self, *args, **kwargs):

		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.host = GlyphsApp.GSNode(args[0].host.position, args[0].type)
				x, y = self.host.x, self.host.y, 
				
			if isinstance(args[0], GlyphsApp.GSNode):
				self.host = args[0]
				x, y = self.host.x, self.host.y, 

			if isinstance(args[0], (tuple, list)):
				x, y = args[0]
				node_type = kwargs.get('type', 'LINE')
				self.host = GlyphsApp.GSNode(NSPoint(x, y), node_type)
				
		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				x, y = float(args[0]), float(args[1])
				node_type = kwargs.get('type', 'LINE')
				self.host = GlyphsApp.GSNode(NSPoint(x, y), node_type)

		super(trNode, self).__init__(x, y, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trNode.__meta__.keys():
			return self.host.__getattribute__(trNode.__meta__[name])
		else:
			return Node.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trNode.__meta__.keys():
			self.host.__setattr__(trNode.__meta__[name], value)
		else:
			Node.__setattr__(self, name, value)

	# - Basics ---------------------------------
	def clone(self):
		new_node = self.host.clone()
		return self.__class__(new_node)

	
	
	
