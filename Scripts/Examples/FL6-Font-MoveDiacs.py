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
from typerig.string import upper_diac_marks

# - Init ------------------------------------------------
font = pFont()
layers_delta = {'Thin':(0.,-20.),'Medium':(0.,-10.), 'Black':(0.,0.)}
shift_marks = upper_diac_marks
process_glyphs = font.selected_pGlyphs()

# - Process --------------------------------------------
for glyph in process_glyphs:
	for layer, delta in layers_delta.iteritems():
		glyph_components = glyph.getContainersDict(layer, pShape)
		updated_marks = []

		for comp_name, comp_shape in glyph_components.iteritems():
			if comp_name in shift_marks:
				comp_shape.shift(*delta)
				updated_marks.append(comp_name)

	if len(updated_marks):
		glyph.update()
		glyph.updateObject(glyph.fl, 'MOVE:\tGlyph: %s;\tMarks: %s\tDelta: %s.' %(glyph.name, '; '.join(list(set(updated_marks))), layers_delta))
	
# - Finish --------------------------------------------
#font.update()
print 'DONE.'
