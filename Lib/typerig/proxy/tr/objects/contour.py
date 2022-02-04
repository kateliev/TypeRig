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
__version__ = '0.0.9'

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

	# - Initialize -----------------------------
	def __init__(self, contour, **kwargs):
		self.host = contour
		super(trContour, self).__init__(self.host.nodes(), default_factory=trNode, proxy=True, **kwargs)
	
	# - Functions ------------------------------
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

	def clone(self):
		new_contour = self.host.clone()
		return self.__class__(new_contour)

	def set_start(self, index):
		index = self.nodes[index].prev_on.idx if not self.nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index] 
		return self.host.setStartPoint(index)
