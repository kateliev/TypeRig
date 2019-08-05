#FLM: Font: Bind Metrics
# VER: 1.0
#----------------------------------
# Foundry:  FontMaker
# Typeface: Bolyar Sans
# Date:     14.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph
from typerig.glyph import eGlyph

# - Init ------------------------------------------------
font = pFont()
layers = font.masters()

# - Process --------------------------------------------
for glyph in font.selectedGlyphs(extend=eGlyph):
	for layer in layers:
		status = glyph.bindCompMetrics(layer)

		if status:
			print 'DONE:\tBind metrics for Glyph: %s' %glyph.name 
		else: 
			print 'ERROR:\tCannot bind metrics for Glyph: %s' %glyph.name 

#glyph.update()

# - Finish --------------------------------------------
font.update()
print 'DONE.'
