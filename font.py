# MODULE: Fontlab 6 Custom Font Objects | TypeRig
# VER 	: 0.01
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from FDK6.proxy import pFont

# - Classes -------------------------------
class eFont(pFont):
	'''
	Proxy Font extension, packing some useful tools.

	Constructor:
		eFont() - default represents the current glyph and current font
		eFont(fgFont)
	'''

	def copyZones(self, font):
		if isinstance(font, fgt.fgFont):
			srcFont = pFont(font)
		elif isinstance(font, pFont):
			srcFont = font

		pass # Current build 6578 offers no way to add/delete zones, as API functionality is lost!
		
