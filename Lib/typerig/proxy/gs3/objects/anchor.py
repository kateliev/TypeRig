# MODULE: Typerig / Proxy / GS3 / Anchor (Objects)
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

from typerig.core.objects.anchor import Anchor

# - Init ---------------------------------
__version__ = '0.1.0'

# - Helpers ------------------------------
def _build_gs_anchor(core_anchor):
	'''Build a GSAnchor from a core Anchor.'''
	anchor          = GlyphsApp.GSAnchor()
	anchor.position = (float(core_anchor.x), float(core_anchor.y))
	anchor.name     = core_anchor.name or ''
	return anchor

# - Classes ------------------------------
class trAnchor(Anchor):
	'''Proxy to GSAnchor object.

	Constructor:
		trAnchor(GSAnchor)
		trAnchor(trAnchor)    — clone

	Attributes:
		.host (GSAnchor): wrapped GlyphsApp anchor
	'''
	# name maps directly; x/y live at .position so they are explicit properties
	__meta__ = {'name': 'name'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, *args, **kwargs):
		if len(args) == 1:
			host = args[0]

			if isinstance(host, GlyphsApp.GSAnchor):
				self.host = host

			elif isinstance(host, self.__class__):
				new_anchor          = GlyphsApp.GSAnchor()
				new_anchor.position = host.host.position
				new_anchor.name     = host.host.name
				self.host           = new_anchor

			else:
				raise TypeError('Expected GSAnchor, got {}'.format(type(host)))

		super(trAnchor, self).__init__(
			float(self.host.position.x),
			float(self.host.position.y),
			name=self.host.name,
			proxy=True,
			**kwargs
		)

	# - Internals ----------------------------
	def __getattribute__(self, name):
		if name in trAnchor.__meta_keys:
			return self.host.__getattribute__(trAnchor.__meta__[name])
		else:
			return Anchor.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trAnchor.__meta_keys:
			self.host.__setattr__(trAnchor.__meta__[name], value)
		else:
			Anchor.__setattr__(self, name, value)

	# - Properties ---------------------------
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

	# - Basics --------------------------------
	def clone(self):
		return self.__class__(self)

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Anchor.'''
		return Anchor(float(self.x), float(self.y), name=self.name)

	def mount(self, core_anchor):
		'''Write core Anchor values back into the GS3 host.

		Args:
			core_anchor (Anchor): Pure core Anchor with data to apply.
		'''
		self.host.position = (float(core_anchor.x), float(core_anchor.y))
		self.host.name     = core_anchor.name or ''
