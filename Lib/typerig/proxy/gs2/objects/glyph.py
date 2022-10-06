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

import GlyphsApp

from typerig.proxy.gs2.objects.layer import trLayer
from typerig.core.objects.glyph import Glyph

# - Init --------------------------------
__version__ = '0.1.2'

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
	__meta__ = {'name':'name', 'mark':'color'}
		
	# -- Some hardcoded properties
	active_layer = property(lambda self: self.host.activeLayer.name)
		
	# - Initialize 
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			self.host = GlyphsApp.Glyphs.font.selectedLayers[0].parent
		
		elif len(argv) == 1 and isinstance(argv[0], GlyphsApp.GSGlyph):
			self.host = argv[0]

		super(trGlyph, self).__init__(self.host.layers, default_factory=trLayer, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trGlyph.__meta__.keys():
			return self.host.__getattribute__(trGlyph.__meta__[name])
		else:
			return Glyph.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trGlyph.__meta__.keys():
			self.host.__setattr__(trGlyph.__meta__[name], value)
		else:
			Glyph.__setattr__(self, name, value)
	
	