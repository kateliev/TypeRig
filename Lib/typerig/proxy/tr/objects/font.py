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
__version__ = '0.0.4'

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
	__meta__ = {'masters':'masters', 'info':'info' } #, 'axes':'axes', 'instances':'instances'}
	__meta_keys = frozenset(__meta__.keys())
		
	# -- Some hardcoded properties
	active_layer = property(lambda self: self.host.activeLayer.name)
	
	# - Helpers
	def __proxy_getattr(self, base_attr, str_attr):
		''' Nested Attributes retriever'''
		if '.' in str_attr:
			for attribute in str_attr.split('.'):
				base_attr = base_attr.__getattribute__(attribute)

			return base_attr
		
		else:
			return base_attr.__getattribute__(str_attr)

	def __proxy_setattr(self, base_attr, str_attr, value):
		if '.' in str_attr:
			proc_string = str_attr.split('.')

			for attribute in proc_string[:1]:
				base_attr = base_attr.__getattribute__(attribute)

			base_attr.__setattr__(proc_string[-1], value)
		
		else:
			base_attr.__setattr__(str_attr, value)

	# - Initialize 
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			self.host = fl6.flPackage(fl6.CurrentFont())

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgFont):
			self.host = fl6.flPackage((argv[0]))

		elif len(argv) == 1 and isinstance(argv[0], fl6.flPackage):
			self.host = argv[0]

		# - The regular way:
		#super(trFont, self).__init__(self.host.fgPackage.glyphs, default_factory=trGlyph, proxy=True, **kwargs)
		
		# - Reduce overhead: add as simple list use on demand casting for speed
		super(trFont, self).__init__([], default_factory=trGlyph, proxy=True, **kwargs)
		self.data = list(self.host.fgPackage.glyphs)

	# - Internals ------------------------------
	def __getattribute__(self, name):
		if name in trFont.__meta_keys:
			return self.__proxy_getattr(self.host, trFont.__meta__[name])
		else:
			return Font.__getattribute__(self, name)

	def __setattr__(self, name, value):
		#print('!!!!SET: {}'.format(name))
		try:
			if name in trFont.__meta_keys:
				self.__proxy_setattr(self.host, trFont.__meta__[name], value)
			else:
				Font.__setattr__(self, name, value)
		
		except AttributeError:
			pass

	def __getitem__(self, ik):
		return self._subclass(self.host.fgPackage[ik])
	
	def __setitem__(self, ik, item): 
		if isinstance(item, self._subclass):
			item = item.host.fgGlyph

		if isinstance(item, fgt.fgGlyph):
			self.host.fgPackage[ik] = item
	
	# - Properties --------------------------
	

	# - Functions ---------------------------
	def update(self):
		fl6.flItems.notifyChangesApplied(self.name, self.host, True)
	