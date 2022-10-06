# MODULE: Typerig / Proxy / Contour (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

from typerig.proxy.gs2.objects.node import trNode
from typerig.core.objects.contour import Contour

# - Init --------------------------------
__version__ = '0.1.2'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Classes -----------------------------
class trContour(Contour):
	'''Proxy to GSContour object

	Constructor:
		trContour(GSContour)

	Attributes:
		.host (GSContour): Original GSContour 
	'''
	# - Metadata and proxy model
	__meta__ = {'closed':'closed', 'selected':'selected'}

	# - Initialize -----------------------------
	def __init__(self, contour, **kwargs):
		self.host = contour
		super(trContour, self).__init__(self.host.nodes, default_factory=trNode, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trContour.__meta__.keys():
			return self.host.__getattribute__(trContour.__meta__[name])
		else:
			return Contour.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trContour.__meta__.keys():
			self.host.__setattr__(trContour.__meta__[name], value)
		else:
			Contour.__setattr__(self, name, value)

	# - Basics ---------------------------------
	def reverse(self):
		self.host.reverse()
		self.data = list(reversed(self.data))

