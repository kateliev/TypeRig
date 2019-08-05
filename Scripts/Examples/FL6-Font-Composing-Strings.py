#FLM: Font: Get Composition Strings
# VER: 1.0
#----------------------------------
# Foundry: 	Borges Type
# Typeface: Future Tense
# Date:		22.10.2018
#----------------------------------

# - Dependancies
import fontlab as fl6
from PythonQt import QtGui
from typerig.proxy import pFont, pGlyph
from typerig.glyph import eGlyph


# - Init ------------------------------------------------
font = pFont()
glyph_set = font.selectedGlyphs(extend=pGlyph) #font.pGlyphs()
clear_anchors = True
work_layer = None
comp_dict = {}
comp_recipe = []

# - Process ------------------------------------------------
# -- Build a dict of composite diacritics that are already present
for glyph in glyph_set:
	comp_names = glyph.getCompositionNames()	

	if len(comp_names) > 2:
		comp_dict.setdefault(comp_names[1],[]).append(comp_names)

# -- Generate strings for all alternates of glyphs present in the above dictionary
alt_glyphs = font.alternates()

for glyph in alt_glyphs:
	name_parts = glyph.name.split('.')

	if len(name_parts) == 2:
		glyph_base, glyph_suffix = name_parts
		
		if glyph_base in comp_dict.keys():
			for recipe in comp_dict[glyph_base]:
				comp_recipe.append('%s+%s=%s.%s' %(glyph.name, recipe[-1], recipe[0], glyph_suffix))

	if len(name_parts) == 3:
		glyph_base, glyph_suff01, glyph_suff02 = name_parts
		
		if glyph_base in comp_dict.keys():
			for recipe in comp_dict[glyph_base]:
				comp_recipe.append('%s+%s=%s.%s.%s' %(glyph.name, recipe[-1], recipe[0], glyph_suff01, glyph_suff02))

# - Finish
# -- Output
print '--- Composing string ---'
print '\n'.join(comp_recipe)

# -- Copy to cliboard
clipboard = QtGui.QApplication.clipboard()
clipboard.setText('\n'.join(comp_recipe))
print '--- String sent to clipboard ---'

print 'DONE.'