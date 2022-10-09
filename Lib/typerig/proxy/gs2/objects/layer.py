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

import GlyphsApp

from typerig.proxy.gs2.objects.contour import trContour
from typerig.core.objects.layer import Layer

# - Init --------------------------------
__version__ = '0.1.3'

# - Classes -----------------------------
class trLayer(Layer):
	'''Proxy to GSLayer object

	Constructor:
		trLayer(GSLayer)

	Attributes:
		.host (GSLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	__meta__ = {'name':'name', 'advance_width':'width'} #, 'advance_height':'vertWidth'} !!! Missing in GS2, present in GS3
		
	# - Initialize 
	def __init__(self, layer, **kwargs):
		self.host = layer
		super(trLayer, self).__init__(self.host.paths, default_factory=trContour, proxy=True, **kwargs)

		# Hotfix for missing advance_height
		self.advance_height = 0.

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
