#FLM: Font: Rename Glyphs
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     11.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
font = pFont()
replace = ('.salt','.ss07')

# - Process --------------------------------------------
for glyph in font.selectedGlyphs():
  glyph.name = glyph.name.replace(*replace)
  glyph.update()

# - Finish --------------------------------------------
font.update()
print 'DONE.'
