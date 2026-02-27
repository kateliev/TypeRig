# MODULE: Typerig / Proxy / Anchor (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.core.objects.anchor import Anchor

# - Init ---------------------------------
__version__ = '0.1.3'

# - Helper --------------------------------
def _build_fl_anchor(core_anchor):
	'''Build an flPinPoint from a core Anchor object.'''
	# NOTE: FL uses flPinPoint for anchors on flLayer
	anchor = fl6.flPinPoint(QtCore.QPointF(core_anchor.x, core_anchor.y))
	anchor.name = core_anchor.name or ''
	return anchor

# - Classes -------------------------------
class trAnchor(Anchor):
	'''Proxy to flPinPoint/flAnchor object

	Constructor:
		trAnchor(flPinPoint)

	Attributes:
		.host (flPinPoint): Original FL anchor object
	'''
	# - Metadata and proxy model
	__meta__ = {}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, *args, **kwargs):
		if len(args) == 1:
			host = args[0]

			if isinstance(host, (fl6.flPinPoint,)):
				self.host = host

			elif isinstance(host, self.__class__):
				self.host = host.host

			else:
				raise TypeError('Expected flPinPoint, got {}'.format(type(host)))

		super(trAnchor, self).__init__(
			self.host.point.x(), self.host.point.y(),
			name=self.host.name,
			proxy=True,
			**kwargs
		)

	# - Internals ------------------------------
	# - Hard Coded as there is no other way working with flPinPoint so far
	@property
	def x(self):
		return self.host.point.x()

	@x.setter
	def x(self, other):
		new_point = QtCore.QPointF(float(other), self.host.point.y())
		self.host.point = new_point

	@property
	def y(self):
		return self.host.point.y()

	@x.setter
	def y(self, other):
		new_point = QtCore.QPointF(self.host.point.x(), float(other))
		self.host.point = new_point

	@property
	def name(self):
		return self.host.name

	@name.setter
	def name(self, other):
		self.host.name = str(other)

	# - Basics ---------------------------------
	def clone(self):
		new_host = fl6.flPinPoint(self.host.x(), self.host.y())
		new_host.name = self.host.name
		return self.__class__(new_host)

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Anchor with current FL values.
		The returned Anchor has no FL bindings and can be freely manipulated.
		'''
		return Anchor(
			float(self.host.point.x()), float(self.host.point.y()),
			name=self.name
		)

	def mount(self, core_anchor):
		'''Write core Anchor values back into the FL host.

		Args:
			core_anchor (Anchor): Pure core Anchor with data to apply.
		'''
		self.host.point = QtCore.QPointF(float(core_anchor.x), float(core_anchor.y))
		self.host.name = core_anchor.name
