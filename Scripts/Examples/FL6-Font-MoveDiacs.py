#FLM: Font: Move Diacritical Marks
# VER: 1.0
#----------------------------------
# Foundry:  Karandash
# Typeface: Achates
# Date:     05.08.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph, pShape
from typerig.string import diactiricalMarks

# - Init ------------------------------------------------
font = pFont()
layers = ['Thin','Medium', 'Black']
delta = (0.,-10.) # X, Y delta

# - Process --------------------------------------------
for glyph in font.selected_pGlyphs():
	for layer in layers:
		glyph_components = glyph.getContainersDict(layer, pShape)
		updated_marks = []

		for comp_name, comp_shape in glyph_components.iteritems():
			if comp_name in diactiricalMarks:
				comp_shape.shift(*delta)
				updated_marks.append(comp_name)

	if len(updated_marks):
		glyph.update()
		glyph.updateObject(glyph.fl, 'MOVE:\tGlyph: %s;\tMarks: %s\tDelta: %s.' %(glyph.name, '; '.join(list(set(updated_marks))), delta))
	
# - Finish --------------------------------------------
#font.update()
print 'DONE.'
