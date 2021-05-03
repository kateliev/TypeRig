# MODULE: Typerig / Proxy / Node (Object)
# NOTE: Experimental proxy approach
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
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
__version__ = '0.1.9'
	
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
	__meta__ = {'x':'x', 'y':'y', 'type':'type', 'g2':'g2', 'smooth':'smooth', 'name':'name', 'selected':'selected'}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{1} = property(lambda self: self.host.__getattribute__('{0}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, *args, **kwargs):
		init_dict = kwargs if kwargs is not None else {}

		if len(args) == 1:
			if isinstance(args[0], self.__class__): # Clone
				self.host = fl6.flNode(args[0].host)
				x, y = self.host.x, self.host.y, 
				add_dict = {'type':self.host.type, 
							'smooth':self.host.smooth, 
							'g2':self.host.g2, 
							'selected':self.host.selected}

				init_dict.update(add_dict)
				
			if isinstance(args[0], fl6.flNode):
				self.host = args[0]
				x, y = self.host.x, self.host.y, 
				add_dict = {'type':self.host.type, 
							'smooth':self.host.smooth, 
							'g2':self.host.g2, 
							'selected':self.host.selected}

				init_dict.update(add_dict)

			if isinstance(args[0], (tuple, list)):
				x, y = args[0]
				node_type = kwargs.get('type', 'on')
				self.host = fl6.flNode(x, y, nodeType=node_type)
				self.smooth = self.host.smooth

		elif len(args) == 2:
			if isMultiInstance(args, (float, int)):
				x, y = float(args[0]), float(args[1])
				node_type = kwargs.get('type', 'on')
				self.host = fl6.flNode(x, y, nodeType=node_type)
				self.smooth = self.host.smooth

		super(trNode, self).__init__(x, y, **init_dict)

	def clone(self):
		new_node = self.host.clone()
		return self.__class__(new_node)


	
	
	
