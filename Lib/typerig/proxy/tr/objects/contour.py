# MODULE: Typerig / Proxy / Contour (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import math 

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.tr.objects.node import trNode
from typerig.core.objects.contour import Contour

# - Init --------------------------------
__version__ = '0.0.2'

# - Classes -----------------------------
class trContour(Contour):
	'''Proxy to flContour object

	Constructor:
		trContour(flContour)

	Attributes:
		.host (flContour): Original flContour 
	'''
	# - Metadata and proxy model
	__meta__ = {}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{1} = property(lambda self: self.host.__getattribute__('{0}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, contour, **kwargs):
		self.host = contour
		super(trContour, self).__init__(self.host.nodes(), default_factory=trNode, **kwargs)