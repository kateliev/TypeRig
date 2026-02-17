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

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.tr.objects.node import trNode
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

# - Init --------------------------------
__version__ = '0.2.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Helpers ------------------------------
def _build_fl_node(core_node):
	'''Build an flNode from a core Node.'''
	fl_node = fl6.flNode(float(core_node.x), float(core_node.y), nodeType=core_node.type)
	fl_node.smooth = core_node.smooth

	if hasattr(core_node, 'name') and core_node.name:
		fl_node.name = core_node.name

	return fl_node

def _build_fl_contour(core_contour):
	'''Build an flContour from a core Contour.'''
	fl_nodes = [_build_fl_node(node) for node in core_contour.nodes]
	return fl6.flContour(fl_nodes, closed=core_contour.closed)

# - Classes -----------------------------
class trContour(Contour):
	'''Proxy to flContour object

	Constructor:
		trContour(flContour)

	Attributes:
		.host (flContour): Original flContour 
	'''
	# - Metadata and proxy model
	#__slots__ = ('host', 'name', 'closed', 'clockwise', 'transform', 'parent', 'lib')
	__meta__ = {'closed':'closed', 'clockwise':'clockwise', 'name':'name'}
	__meta_keys = frozenset(__meta__.keys())

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
		if name in trContour.__meta_keys:
			return self.host.__getattribute__(trContour.__meta__[name])
		else:
			return Contour.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trContour.__meta_keys:
			self.host.__setattr__(trContour.__meta__[name], value)
		else:
			Contour.__setattr__(self, name, value)

	# - Properties -----------------------------
	@property
	def nodes(self):
		self.data = [trNode(node, parent=self) for node in self.host.nodes()]
		return self.data

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

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Contour with current FL values.
		The returned Contour has no FL bindings and can be freely manipulated.
		'''
		core_nodes = [trNode(n).eject() for n in self.host.nodes()]
		return Contour(core_nodes, closed=self.closed, name=self.name)

	def mount(self, core_contour):
		'''Write core Contour data back into the FL host.
		If node count matches, updates nodes in place.
		Otherwise rebuilds the FL contour entirely.

		Args:
			core_contour (Contour): Pure core Contour with data to apply.

		Note:
			If structure changes (node count differs), the host flContour 
			is replaced. Parent shape host is synced automatically if 
			parent is a trShape.
		'''
		host_nodes = self.host.nodes()

		if len(core_contour.nodes) == len(host_nodes):
			# - Same structure: update nodes in place
			for fl_node, core_node in zip(host_nodes, core_contour.nodes):
				fl_node.x = float(core_node.x)
				fl_node.y = float(core_node.y)
				fl_node.type = core_node.type
				fl_node.smooth = core_node.smooth

				if hasattr(core_node, 'name') and core_node.name:
					fl_node.name = core_node.name

		else:
			# - Structure changed: rebuild entire contour
			self.host = _build_fl_contour(core_contour)

			# - Sync parent shape host if available
			if self.parent is not None and hasattr(self.parent, '_sync_host'):
				self.parent._sync_host()

		# - Update closed/name
		self.host.closed = core_contour.closed

		if hasattr(core_contour, 'name') and core_contour.name:
			self.host.name = core_contour.name

		# - Rebuild proxy data
		self.data = [trNode(n, parent=self) for n in self.host.nodes()]
