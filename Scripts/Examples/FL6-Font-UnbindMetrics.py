#FLM: Font: UN-Bind Metrics
# VER: 1.1
#----------------------------------
# Foundry:  Karandash
# Typeface: Achates
# Date:     14.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
font = pFont()
layers = ['Thin','Medium', 'Black']

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
	for layer in layers:
		glyph.setLSBeq('', layer)
		glyph.setRSBeq('', layer)
		#glyph.setLSB(0, layer)
		#glyph.setRSB(0, layer)
		glyph.update()

# - Finish --------------------------------------------
#font.update()
print 'DONE.'
