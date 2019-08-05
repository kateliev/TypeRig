#FLM: Font: Clear Anchors
# VER: 1.0
#----------------------------------
# Foundry:  FontMaker
# Typeface: Bolyar Sans
# Date:     14.12.2018
#----------------------------------
# HOTFIX for MKMK and mark feature export bug?!

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
font = pFont()
layers = ['100','900']

# - Process --------------------------------------------
for glyph in font.pGlyphs():
	for layer in layers:
		if len(glyph.anchors(layer)):
			glyph.clearAnchors(layer)
			glyph.update()
			print 'DONE:\tClear Anchors: %s' %glyph.name
		
# - Finish --------------------------------------------
#font.update()
print 'DONE.'
