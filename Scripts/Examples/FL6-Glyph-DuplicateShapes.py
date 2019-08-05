#FLM: Glyph: Duplicate Shapes
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
font_metrics = font.fontMetrics()
glyph = pGlyph()
layers = {'100':(0, 128), '900':(0, 91)} #layer_name : translate shape
find_shape = '_gp_underline'

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
  for layer, shift in layers.iteritems():
    for shape in glyph.shapes(layer):
      if shape.shapeData.name == find_shape:
        new_shape = glyph.layer(layer).addShape(shape)
        new_shape.transform = shape.transform.translate(shift[0], shift[1] + font_metrics.getXHeight(layer))

    glyph.update()
    print 'DONE:\t Glyph: %s; Shape: %s' %(glyph.name, find_shape)

# - Finish --------------------------------------------
font.update()
print 'DONE.'
