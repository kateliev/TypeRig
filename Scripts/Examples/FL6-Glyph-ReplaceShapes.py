#FLM: Glyph: Replace Shapes
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     13.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
font = pFont()
layers = ['100','900']
src_glyph = 'A.ss08'
old_shape = '_gp_diamond_mid'
new_shape = '_gp_circle_mid'

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
	for layer in layers:
		new = [shape for shape in font.glyph(src_glyph).shapes(layer) if shape.shapeData.name == new_shape][0]
		old = [shape for shape in glyph.shapes(layer) if shape.shapeData.name == old_shape][0]
		glyph.layer(layer).replaceShape(old, new)

	glyph.update()
	print 'DONE:\t Glyph: %s;'

# - Finish --------------------------------------------
font.update()
print 'DONE.'
