#FLM: Glyph: Scale Layer
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     11.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph
from typerig.brain import ratfrac

# - Init ------------------------------------------------
font = pFont()
font_metrics = font.fontMetrics()
glyph = pGlyph()
layers = ['100','900'] 

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
  for layer in layers:
    scale = ratfrac(font_metrics.getCapsHeight(layer), glyph.getBounds(layer).height(), 1)
    glyph.layer(layer).transform = glyph.layer(layer).transform.scale(scale, scale)

  glyph.update()
  print 'DONE:\t Glyph: %s; Scale: %s' %(glyph.name, scale)

# - Finish --------------------------------------------
font.update()
print 'DONE.'
