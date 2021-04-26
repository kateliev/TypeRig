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

import fontlab as fl6
from typerig.core.objects.node import Node

# - Init ---------------------------------
__version__ = '0.0.8'
	
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
	__meta__ = {'x':'x', 'y':'y', 'type':'type', 'g2':'g2', 'smooth':'smooth', 'name':'name'}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{1} = property(lambda self: self.host.__getattribute__('{0}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, node, **kwargs):
		self.host = node
		super(trNode, self).__init__(self.host.x, self.host.y, type=self.host.type, **kwargs)

	
	
	
