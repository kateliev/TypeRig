# MODULE: Typerig / Proxy / Shape (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

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
from typerig.core.objects.transform import Transform

# - Init --------------------------------
__version__ = '0.3.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Helpers ------------------------------
# FontLab model (verified FL9, 2026-11): flShape.contours are in ELEMENT
# space and the placement lives only in flShape.transform. The element
# name lives on flShape.shapeData.name; flShape.name is normally ''.
# QTransform(m11, m12, m21, m22, dx, dy) has the same slot order as core
# Transform(xx, xy, yx, yy, dx, dy): x' = m11*x + m21*y + dx.

def _qt_to_transform(qt):
	'''QTransform -> core Transform.'''
	return Transform(qt.m11(), qt.m12(), qt.m21(), qt.m22(), qt.dx(), qt.dy())

def _transform_to_qt(transform):
	'''core Transform (or any 6-sequence) -> QTransform.'''
	return pqt.QtGui.QTransform(*[float(transform[i]) for i in range(6)])

def _element_name(fl_shape):
	'''Element name of an flShape: shapeData.name, else flShape.name.'''
	data = fl_shape.shapeData
	return (data.name if data is not None else '') or fl_shape.name or ''

def _set_element_name(fl_shape, name):
	if fl_shape.shapeData is not None:
		fl_shape.shapeData.name = name
	else:
		fl_shape.name = name

def _build_fl_shape(core_shape):
	'''Build an flShape from a core Shape: contours (element space), element
	name and placement transform.'''
	fl_shape = fl6.flShape()
	fl_shape.contours = [_build_fl_contour(c) for c in core_shape.contours]

	if getattr(core_shape, 'name', None):
		_set_element_name(fl_shape, core_shape.name)

	transform = getattr(core_shape, 'transform', None)
	if transform is not None:
		fl_shape.transform = _transform_to_qt(transform)

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
		# None contours (damaged FL data) are not wrapped; see eject().
		super(trShape, self).__init__([c for c in self.host.contours if c is not None], default_factory=trContour, proxy=True, **kwargs)

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
		# FontLab can hand back None for a damaged contour (BasilMM:
		# eogonek/Light). Skip it rather than lose the whole glyph; the
		# font-level eject reports it (trFontProxy._null_contours).
		core_contours = [trContour(c).eject() for c in self.host.contours if c is not None]
		return Shape(core_contours,
		             name=_element_name(self.host),
		             transform=_qt_to_transform(self.host.transform))

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

		# - Element name and placement
		if getattr(core_shape, 'name', None):
			_set_element_name(self.host, core_shape.name)

		transform = getattr(core_shape, 'transform', None)
		if transform is not None:
			self.host.transform = _transform_to_qt(transform)

		# - Rebuild proxy data
		self.data = [trContour(c, parent=self) for c in self.host.contours if c is not None]

		# - Sync parent layer host if available
		if self.parent is not None and hasattr(self.parent, '_sync_host'):
			self.parent._sync_host()
