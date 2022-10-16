# MODULE: Typerig / Proxy / Font (Objects)
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

from typerig.proxy.tr.objects.glyph import trGlyph
from typerig.core.objects.font import Font

# - Init --------------------------------
__version__ = '0.0.1'

# - Classes -----------------------------
class trFont(Font):
	'''Proxy to flLayer object

	Constructor:
		trGlyph(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'unicodes', 'identifier', 'parent')
	__meta__ = {'info':'fgPackage.info'}
		
	# -- Some hardcoded properties
	active_layer = property(lambda self: self.host.activeLayer.name)
		
	# - Initialize 
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			self.host = fl6.flPackage(fl6.CurrentFont())

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgFont):
			self.host = fl6.flPackage((argv[0]))

		elif len(argv) == 1 and isinstance(argv[0], fl6.flPackage):
			self.host = argv[0]

		super(trFont, self).__init__([], default_factory=trGlyph, proxy=True, **kwargs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trFont.__meta__.keys():
			return self.host.__getattribute__(trFont.__meta__[name])
		else:
			return Font.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trFont.__meta__.keys():
			self.host.__setattr__(trFont.__meta__[name], value)
		else:
			Font.__setattr__(self, name, value)
	
	# - Properties --------------------------
	

	# - Functions ---------------------------
	def update(self):
		fl6.flItems.notifyChangesApplied(self.name, self.host, True)
	