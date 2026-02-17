# MODULE: Typerig / Proxy / Layer (Objects)
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

from typerig.proxy.tr.objects.shape import trShape, _build_fl_shape
from typerig.core.objects.layer import Layer

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
class trLayer(Layer):
	'''Proxy to flLayer object

	Constructor:
		trLayer(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'transform', 'identifier', 'parent')
	__meta__ = {'name':'name', 'mark':'mark', 'advance':'advanceWidth', 'advance_width':'advanceWidth', 'advance_height':'advanceHeight'}
	__meta_keys = frozenset(__meta__.keys())
		
	# - Initialize 
	def __init__(self, layer, **kwargs):
		self.host = layer
		super(trLayer, self).__init__(self.host.shapes, default_factory=trShape, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trLayer.__meta_keys:
			return self.host.__getattribute__(trLayer.__meta__[name])
		else:
			return Layer.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trLayer.__meta_keys:
			self.host.__setattr__(trLayer.__meta__[name], value)
		else:
			Layer.__setattr__(self, name, value)

	# - Host sync --------------------------------
	def _sync_host(self):
		'''Sync host layer shapes with proxy data.
		Call after individual shape.mount() changes structure.
		'''
		self.host.shapes = [s.host for s in self.data]

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Layer with current FL values.
		The returned Layer has no FL bindings and can be freely manipulated.

		Returns:
			Layer: Pure core Layer with geometry and metrics copied from host.
		'''
		core_shapes = [trShape(s).eject() for s in self.host.shapes]

		return Layer(
			core_shapes,
			name=self.name,
			width=self.advance_width,
			height=self.advance_height,
			mark=self.mark
		)

	def mount(self, core_layer):
		'''Write core Layer data back into the FL host.
		Rebuilds all FL shapes from core data and updates metrics.

		Args:
			core_layer (Layer): Pure core Layer with data to apply.

		Example:
			>>> tr_g = trGlyph()
			>>> core_layer = tr_g[0].eject()     # eject first layer
			>>> core_layer.shift(10, 20)          # manipulate
			>>> tr_g[0].mount(core_layer)        # push back
			>>> tr_g.update()                     # notify FL
		'''
		# - Remove existing shapes from host
		for shape in list(self.host.shapes):
			self.host.removeShape(shape)

		# - Build and add new shapes from core data
		for core_shape in core_layer.shapes:
			fl_shape = _build_fl_shape(core_shape)
			self.host.addShape(fl_shape)

		# - Copy metrics
		self.host.advanceWidth = core_layer.advance_width
		self.host.advanceHeight = core_layer.advance_height

		# - Rebuild proxy data
		self.data = [trShape(s, parent=self) for s in self.host.shapes]
