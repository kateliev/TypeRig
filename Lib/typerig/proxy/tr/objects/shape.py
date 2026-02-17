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

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.tr.objects.node import trNode
from typerig.proxy.tr.objects.contour import trContour, _build_fl_contour
from typerig.core.objects.shape import Shape

# - Init --------------------------------
__version__ = '0.2.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Helpers ------------------------------
def _build_fl_shape(core_shape):
	'''Build an flShape from a core Shape.'''
	fl_shape = fl6.flShape()
	fl_shape.contours = [_build_fl_contour(c) for c in core_shape.contours]

	if hasattr(core_shape, 'name') and core_shape.name:
		fl_shape.name = core_shape.name

	return fl_shape

# - Classes -----------------------------
class trShape(Shape):
	'''Proxy to flShape object

	Constructor:
		trShape(flShape)

	Attributes:
		.host (flShape): Original flShape 
	'''
	# - Metadata and proxy model
	#__slots__ = ('host', 'name', 'transform', 'identifier', 'parent', 'lib')
	__meta__ = {'name':'name'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ------------------------------
	def __init__(self, shape, **kwargs):
		self.host = shape
		super(trShape, self).__init__(self.host.contours, default_factory=trContour, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trShape.__meta_keys:
			return self.host.__getattribute__(trShape.__meta__[name])
		else:
			return Shape.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trShape.__meta_keys:
			self.host.__setattr__(trShape.__meta__[name], value)
		else:
			Shape.__setattr__(self, name, value)

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

	# - Host sync --------------------------------
	def _sync_host(self):
		'''Sync host shape contours with proxy data.
		Call after individual contour.mount() changes structure.
		'''
		self.host.contours = [c.host for c in self.data]

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Shape with current FL values.
		The returned Shape has no FL bindings and can be freely manipulated.
		'''
		core_contours = [trContour(c).eject() for c in self.host.contours]
		return Shape(core_contours, name=self.name)

	def mount(self, core_shape):
		'''Write core Shape data back into the FL host.
		Rebuilds all FL contours from core data and syncs the host.

		Args:
			core_shape (Shape): Pure core Shape with data to apply.

		Note:
			If parent is a trLayer, its host is synced automatically.
		'''
		# - Build new FL contours from core data
		fl_contours = [_build_fl_contour(c) for c in core_shape.contours]

		# - Replace host contours
		self.host.contours = fl_contours

		# - Copy shape name
		if hasattr(core_shape, 'name') and core_shape.name:
			self.host.name = core_shape.name

		# - Rebuild proxy data
		self.data = [trContour(c, parent=self) for c in self.host.contours]

		# - Sync parent layer host if available
		if self.parent is not None and hasattr(self.parent, '_sync_host'):
			self.parent._sync_host()
