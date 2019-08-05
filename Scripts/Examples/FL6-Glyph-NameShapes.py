#FLM: Glyph: Name Shapes
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
glyph = pGlyph()
layers = ['100', '900']
exclude_shape = '_'

# - Process --------------------------------------------
for layer in layers:
  for shape in glyph.shapes(layer):
    if exclude_shape not in shape.shapeData.name:
      shape.shapeData.name = glyph.name

# - Finish --------------------------------------------
glyph.update()
glyph.updateObject(glyph.fl)
print 'DONE.'
