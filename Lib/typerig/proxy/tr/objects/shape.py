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

from typerig.proxy.tr.objects.node import trNode
from typerig.proxy.tr.objects.contour import trContour
from typerig.core.objects.shape import Shape

# - Init --------------------------------
__version__ = '0.0.4'

# - Classes -----------------------------
class trShape(Shape):
	'''Proxy to flShape object

	Constructor:
		trShape(flShape)

	Attributes:
		.host (flShape): Original flShape 
	'''
	# - Metadata and proxy model
	__slots__ = ('host', 'name', 'transform', 'identifier', 'parent', 'lib')
	__meta__ = {'name':'name'}

	# - Connect to host dynamically	
	for src, dst in __meta__.items():
		exec("{0} = property(lambda self: self.host.__getattribute__('{1}'), lambda self, value: self.host.__setattr__('{1}', value))".format(src, dst))
		
	# - Initialize 
	def __init__(self, shape, **kwargs):
		self.host = shape
		super(trShape, self).__init__(self.host.contours, default_factory=trContour, proxy=True, **kwargs)

	# - Functions -------------------------------
	def insert(self, i, item):
		if not self._lock:
			if isinstance(item, self._subclass):
				item.parent = self
			
			elif not isinstance(item, (int, float, basestring)):
				item = self._subclass(item, parent=self) 

			if not hasattr(item, 'host'):
				flNode_list = []
				for node in item.nodes:
					if not isinstance(node, fl6.flNode):
						current_node = fl6.flNode(node.x, node.y, nodeType=node.type)
						current_node.smooth = node.smooth
					else: 
						current_node = node

					flNode_list.append(current_node)

				item.host = fl6.flContour(flNode_list, closed=item.closed)

			self.data.insert(i, item)
			self.host.insert(i, item.host)

	def reverse(self):
		self.data = list(reversed(self.data))
		self.host.contours = list(reversed(self.host.contours))

	def sort(self, direction=0, mode='BL'):
		contour_bounds = [(contour, contour.bounds.align_matrix[mode.upper()]) for contour in self.contours]
		self.data = [contour_pair[0] for contour_pair in sorted(contour_bounds, key=lambda d: d[1][direction])]
		self.host.contours = [contour.host for contour in self.data]