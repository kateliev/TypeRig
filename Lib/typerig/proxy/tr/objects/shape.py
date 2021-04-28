# MODULE: Typerig / Proxy / Shape (Objects)
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

from typerig.proxy.tr.objects.contour import trContour
from typerig.core.objects.shape import Shape

# - Init --------------------------------
__version__ = '0.0.1'

# - Classes -----------------------------
class trShape(Shape):
	'''Proxy to flShape object

	Constructor:
		trShape(flShape)

	Attributes:
		.host (flShape): Original flShape 
	'''
	# - Metadata and proxy model
	__meta__ = {'name':'name'}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{1} = property(lambda self: self.host.__getattribute__('{0}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, shape, **kwargs):
		self.host = shape
		super(trShape, self).__init__(self.host.contours, name=self.host.name, default_factory=trContour, **kwargs)