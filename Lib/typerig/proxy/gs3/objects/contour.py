# MODULE: Typerig / Proxy / GS3 / Contour (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import GlyphsApp

from typerig.proxy.gs3.objects.node import trNode, _build_gs_node, _CORE_TO_GS3
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

# - Init ---------------------------------
__version__ = '0.1.0'

# - Helpers ------------------------------
def _build_gs_path(core_contour):
	'''Build a GSPath from a core Contour.'''
	path = GlyphsApp.GSPath()

	for core_node in core_contour.nodes:
		path.nodes.append(_build_gs_node(core_node))

	path.closed = bool(core_contour.closed)
	return path

# - Classes ------------------------------
class trContour(Contour):
	'''Proxy to GSPath object.

	Constructor:
		trContour(GSPath)

	Attributes:
		.host (GSPath): wrapped GlyphsApp path
		.parent (trShape): parent shape
	'''
	__meta__ = {'closed': 'closed'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, path, **kwargs):
		self.host = path
		super(trContour, self).__init__(list(self.host.nodes), default_factory=trNode, proxy=True, **kwargs)

	# - Internals ----------------------------
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

	# - Properties ---------------------------
	@property
	def nodes(self):
		self.data = [trNode(n, parent=self) for n in self.host.nodes]
		return self.data

	# - Functions ----------------------------
	def insert(self, i, item):
		if not self._lock:
			if not isinstance(item, trNode):
				item = trNode(item) if isinstance(item, GlyphsApp.GSNode) else trNode(item.x, item.y, type=item.type)

			item.parent = self

			nodes = list(self.host.nodes)
			nodes.insert(i, item.host)
			self.host.nodes = nodes

			self.data.insert(i, item)

	def reverse(self):
		self.host.reverse()
		self.data = list(reversed(self.data))

	def set_start(self, index):
		# Ensure index points to an on-curve node
		nodes = self.nodes
		index = nodes[index].prev_on.idx if not nodes[index].is_on else index
		self.data = self.data[index:] + self.data[:index]
		self.host.nodes = [n.host for n in self.data]

	# - Host sync ----------------------------
	def _sync_host(self):
		'''Rebuild host node list from proxy data.'''
		self.host.nodes = [n.host for n in self.data]

	# - Basics --------------------------------
	def clone(self):
		return self.__class__(_build_gs_path(self.eject()))

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Contour.'''
		core_nodes = [trNode(n).eject() for n in self.host.nodes]
		return Contour(core_nodes, closed=self.closed)

	def mount(self, core_contour):
		'''Write core Contour data back into the GS3 host.
		Updates nodes in-place when count matches, otherwise rebuilds.

		Args:
			core_contour (Contour): Pure core Contour with data to apply.
		'''
		host_nodes = list(self.host.nodes)

		if len(core_contour.nodes) == len(host_nodes):
			for gs_node, core_node in zip(host_nodes, core_contour.nodes):
				gs_node.position = (float(core_node.x), float(core_node.y))
				gs_node.type     = _CORE_TO_GS3.get(core_node.type, 'line')
				gs_node.smooth   = bool(core_node.smooth)

				if hasattr(core_node, 'name') and core_node.name:
					gs_node.name = core_node.name

		else:
			# Structure changed: rebuild entire path
			self.host = _build_gs_path(core_contour)

			if self.parent is not None and hasattr(self.parent, '_sync_host'):
				self.parent._sync_host()

		self.host.closed = bool(core_contour.closed)
		self.data = [trNode(n, parent=self) for n in self.host.nodes]
