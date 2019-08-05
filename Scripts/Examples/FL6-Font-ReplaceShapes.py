#FLM: Font: Replace Shapes
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     13.02.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
font = pFont()
layers = ['100','900']
old_name = 'u.1'
new_name = 'u'

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
	for layer in layers:
		new_shape = font.findShape(new_name, layer)
		old_shape = glyph.findShape(old_name, layer)
		glyph.layer(layer).replaceShape(old_shape, new_shape)

	glyph.update()
	glyph.updateObject(glyph.fl, 'Replace shape:\tGlyph: %s;\tShapes: %s -> %s .' %(glyph.name, old_name, new_name))
	
# - Finish --------------------------------------------
#font.update()
print 'DONE.'
