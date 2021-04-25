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
__version__ = '0.0.4'

# - Classes -------------------------------
class trNode(Node):
	def __init__(self, node):
		self.host = node
		super(trNode, self).__init__(self.host.x, self.host.y, type=self.host.type)

	# - Metadata and proxy model ---------
	meta = {'x':'x',
			'y':'y',
			'type':'type'
			}
	
	# -- Build and connect to host dynamically	
	for key, value in meta.items():
		exec("{dst} = property(lambda self: self.host.__getattribute__('{src}'), lambda self, value: self.host.__setattr__('{src}', value))".format(src=value, dst=key))
		