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

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.tr.objects.node import trNode
from typerig.core.objects.contour import Contour

# - Init --------------------------------
__version__ = '0.0.6'

# - Classes -----------------------------
class trContour(Contour):
	'''Proxy to flContour object

	Constructor:
		trContour(flContour)

	Attributes:
		.host (flContour): Original flContour 
	'''
	# - Metadata and proxy model
	__slots__ = ('host', 'name', 'closed', 'clockwise', 'transform', 'parent', 'lib')
	__meta__ = {'closed':'closed', 'clockwise':'clockwise', 'name':'name'}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{0} = property(lambda self: self.host.__getattribute__('{1}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, contour, **kwargs):
		self.host = contour
		super(trContour, self).__init__(self.host.nodes(), default_factory=trNode, proxy=True, **kwargs)
	
	# - Functions
	def insert(self, i, item):
		if not self._lock:
			if isinstance(item, self._subclass):
				item.parent = self
			
			elif not isinstance(item, (int, float, basestring)):
				item = self._subclass(item, parent=self) 

			if not hasattr(item, 'host'):
				item.host = fl6.flNode(item.x, item.y, nodeType=item.type)
				item.host.smooth = item.smooth

			self.data.insert(i, item)
			self.host.insert(i, item.host)

	def reverse(self):
		self.host.reverse()
		self.data = list(reversed(self.data))

	def clone(self):
		new_contour = self.host.clone()
		return self.__class__(new_contour)
