# MODULE: Typerig / Proxy / Layer (Objects)
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

from typerig.proxy.tr.objects.shape import trShape
from typerig.core.objects.layer import Layer

# - Init --------------------------------
__version__ = '0.0.5'

# - Classes -----------------------------
class trLayer(Layer):
	'''Proxy to flLayer object

	Constructor:
		trLayer(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'transform', 'identifier', 'parent')
	__meta__ = {'name':'name', 'mark':'mark', 'advance':'advanceWidth', 'advance_width':'advanceWidth', 'advance_height':'advanceHeight'}
		
	# - Initialize 
	def __init__(self, layer, **kwargs):
		self.host = layer
		super(trLayer, self).__init__(self.host.shapes, default_factory=trShape, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trLayer.__meta__.keys():
			return self.host.__getattribute__(trLayer.__meta__[name])
		else:
			return Layer.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trLayer.__meta__.keys():
			self.host.__setattr__(trLayer.__meta__[name], value)
		else:
			Layer.__setattr__(self, name, value)