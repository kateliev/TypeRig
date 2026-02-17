# MODULE: Typerig / Proxy / Glyph (Objects)
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

from typerig.proxy.tr.objects.layer import trLayer
from typerig.core.objects.glyph import Glyph

# - Init --------------------------------
__version__ = '0.1.0'

# - Classes -----------------------------
class trGlyph(Glyph):
	'''Proxy to flLayer object

	Constructor:
		trGlyph(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'unicodes', 'identifier', 'parent')
	__meta__ = {'name':'name', 'mark':'mark'}
	__meta_keys = frozenset(__meta__.keys())
		
	# -- Some hardcoded properties
	active_layer = property(lambda self: self.host.activeLayer.name)
		
	# - Initialize 
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			self.host = fl6.flGlyph(fl6.CurrentGlyph(), fl6.CurrentFont())
		
		elif len(argv) == 1 and isinstance(argv[0], fl6.flGlyph):
			#font, glyph = argv[0].fgPackage, argv[0].fgPackage[argv[0].name]
			self.host = argv[0]

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgGlyph):
			font, glyph = argv[0].parent, argv[0]
			self.host = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[0], fgt.fgFont) and isinstance(argv[1], fgt.fgGlyph):
			font, glyph = argv
			self.host = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[1], fgt.fgFont) and isinstance(argv[0], fgt.fgGlyph):
			glyph, font = argv
			self.host = fl6.flGlyph(glyph, font)

		super(trGlyph, self).__init__(self.host.layers, default_factory=trLayer, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trGlyph.__meta_keys:
			return self.host.__getattribute__(trGlyph.__meta__[name])
		else:
			return Glyph.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trGlyph.__meta_keys:
			self.host.__setattr__(trGlyph.__meta__[name], value)
		else:
			Glyph.__setattr__(self, name, value)
	
	# - Properties --------------------------
	@property
	def unicodes(self):
		return self.host.fgGlyph.unicodes

	# - Functions ---------------------------
	def update(self):
		fl6.flItems.notifyChangesApplied(self.name, self.host, True)

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Glyph with current FL values.
		The returned Glyph has no FL bindings and can be freely manipulated.

		Returns:
			Glyph: Pure core Glyph with all layers, geometry and metadata.

		Example:
			>>> tr_g = trGlyph()
			>>> core_g = tr_g.eject()
			>>> layer = core_g.layer('Regular')
			>>> layer.shift(10, 20)
			>>> tr_g.layer('Regular').mount(layer)  # mount at layer level
			>>> tr_g.update()
		'''
		core_layers = [trLayer(l).eject() for l in self.host.layers]

		return Glyph(
			core_layers,
			name=self.name,
			mark=self.mark,
			unicodes=list(self.unicodes)
		)
