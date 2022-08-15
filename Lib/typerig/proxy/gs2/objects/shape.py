# MODULE: Typerig / Proxy / Shape (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import math 

from typerig.proxy.gs.objects.node import trNode
from typerig.proxy.gs.objects.contour import trContour
from typerig.core.objects.shape import Shape

# - Init --------------------------------
__version__ = '0.1.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Classes -----------------------------
class trShape(Shape):
	'''Proxy to flShape object

	Constructor:
		trShape(GSShape)

	Attributes:
		.host (GSShape): Original GSShape 
	'''
	# - Metadata and proxy model
	__meta__ = {'locked':'locked', 'type':'shapeType'}

	# - Initialize ------------------------------
	def __init__(self, shape, **kwargs):
		self.host = shape
		super(trShape, self).__init__(self.host.paths, default_factory=trContour, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trShape.__meta__.keys():
			return self.host.__getattribute__(trShape.__meta__[name])
		else:
			return Shape.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trShape.__meta__.keys():
			self.host.__setattr__(trShape.__meta__[name], value)
		else:
			Shape.__setattr__(self, name, value)

	# - Functions -------------------------------
	def reverse(self):
		self.data = list(reversed(self.data))
		self.host.paths = list(reversed(self.host.paths))

	