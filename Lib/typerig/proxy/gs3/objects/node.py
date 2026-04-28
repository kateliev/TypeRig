# MODULE: Typerig / Proxy / GS3 / Node (Objects)
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

from typerig.core.objects.node import Node
from typerig.core.func.utils import isMultiInstance

# - Init ---------------------------------
__version__ = '0.1.0'

# GS3 node type string <-> Core node type
# GlyphsApp 3 GSNode.type returns lowercase strings: 'line', 'curve', 'offcurve', 'qcurve'.
# Both cases are kept for safety (GS2 / scripted contexts may use uppercase).
_GS3_TO_CORE = {
	'line':     'on',
	'curve':    'curve',
	'offcurve': 'off',
	'qcurve':   'on',
	# legacy / GS2 uppercase variants
	'LINE':     'on',
	'CURVE':    'curve',
	'OFFCURVE': 'off',
	'QCURVE':   'on',
}
_CORE_TO_GS3 = {
	'on':    'line',
	'curve': 'curve',
	'off':   'offcurve',
	'move':  'line',
}

# - Helpers ------------------------------
def _build_gs_node(core_node):
	'''Build a GSNode from a core Node.'''
	node = GlyphsApp.GSNode()
	node.position = (float(core_node.x), float(core_node.y))
	node.type     = _CORE_TO_GS3.get(core_node.type, 'line')
	node.smooth   = bool(core_node.smooth)

	if hasattr(core_node, 'name') and core_node.name:
		node.name = core_node.name

	return node

# - Classes ------------------------------
class trNode(Node):
	'''Proxy to GSNode object.

	Constructor:
		trNode(GSNode)
		trNode(trNode)        — clone
		trNode((x, y))
		trNode(x, y)

	Attributes:
		.host (GSNode): wrapped GlyphsApp node
		.parent (trContour): parent contour
	'''
	# smooth, name, selected map directly; x, y, type need conversion so they
	# are explicit properties below rather than in __meta__
	__meta__ = {'smooth': 'smooth', 'name': 'name', 'selected': 'selected'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, *args, **kwargs):

		if len(args) == 1:
			if isinstance(args[0], self.__class__):
				src = args[0].host
				node = GlyphsApp.GSNode()
				node.position = src.position
				node.type     = src.type
				node.smooth   = src.smooth
				self.host     = node

			elif isinstance(args[0], GlyphsApp.GSNode):
				self.host = args[0]

			elif isinstance(args[0], (tuple, list)):
				x, y      = float(args[0][0]), float(args[0][1])
				gs_type   = _CORE_TO_GS3.get(kwargs.get('type', 'on'), 'line')
				node      = GlyphsApp.GSNode()
				node.position = (x, y)
				node.type     = gs_type
				self.host     = node

		elif len(args) == 2 and isMultiInstance(args, (float, int)):
			x, y    = float(args[0]), float(args[1])
			gs_type = _CORE_TO_GS3.get(kwargs.get('type', 'on'), 'line')
			node    = GlyphsApp.GSNode()
			node.position = (x, y)
			node.type     = gs_type
			self.host     = node

		super(trNode, self).__init__(
			float(self.host.position.x),
			float(self.host.position.y),
			proxy=True,
			**kwargs
		)

	# - Internals ----------------------------
	def __getattribute__(self, name):
		if name in trNode.__meta_keys:
			return self.host.__getattribute__(trNode.__meta__[name])
		else:
			return Node.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trNode.__meta_keys:
			self.host.__setattr__(trNode.__meta__[name], value)
		else:
			Node.__setattr__(self, name, value)

	# - Properties ---------------------------
	# x/y live at node.position in GS3; type needs string <-> Core mapping
	@property
	def x(self):
		return float(self.host.position.x)

	@x.setter
	def x(self, value):
		self.host.position = (float(value), float(self.host.position.y))

	@property
	def y(self):
		return float(self.host.position.y)

	@y.setter
	def y(self, value):
		self.host.position = (float(self.host.position.x), float(value))

	@property
	def type(self):
		return _GS3_TO_CORE.get(self.host.type, 'on')

	@type.setter
	def type(self, value):
		self.host.type = _CORE_TO_GS3.get(value, 'line')

	# - Basics --------------------------------
	def clone(self):
		return self.__class__(self)

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Node.'''
		return Node(
			float(self.x), float(self.y),
			type=self.type,
			smooth=self.smooth,
			name=self.name,
		)

	def mount(self, core_node):
		'''Write core Node values back into the GS3 host.

		Args:
			core_node (Node): Pure core Node with values to apply.
		'''
		self.host.position = (float(core_node.x), float(core_node.y))
		self.host.type     = _CORE_TO_GS3.get(core_node.type, 'line')
		self.host.smooth   = bool(core_node.smooth)

		if hasattr(core_node, 'name') and core_node.name:
			self.host.name = core_node.name
