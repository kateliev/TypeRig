#FLM: JSON: Classes from composites
# VER: 1.0
#----------------------------------
# Foundry: 	The Font Maker
# Typeface: Bolyar Sans
# Date:		18.11.2018
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph
from typerig.string import diactiricalMarks as diacMark
from typerig.utils import jsontree
from typerig.font import jFont


# - Init ------------------------------------------------
font = pFont()
jfont = jFont(font)

font_workset_names = [glyph.name for glyph in font.uppercase()] + [glyph.name for glyph in font.lowercase()] + [glyph.name for glyph in font.alternates()]
ban_list = ['sups', 'subs', 'ss10', 'ss09', 'ss08', 'dnom', 'numr']
layers = ['100', '900']
alt_mark = '.'

class_dict = {}

# - Process ------------------------------------------------
process_glyphs = font.pGlyphs() #font.selectedGlyphs(extend=pGlyph)
for glyph in process_glyphs:
	if all([banned_item not in glyph.name for banned_item in ban_list]):
		layer = '100'
		clear_comp = [comp.shapeData.name for comp in glyph.shapes(layer) + glyph.components(layer) if comp.shapeData.name in font_workset_names and comp.shapeData.name != glyph.name]
		
		if len(clear_comp) == 1:
			class_dict.setdefault(clear_comp[0], set([clear_comp[0]])).add(glyph.name)

		if len(clear_comp) == 0 and alt_mark in glyph.name:
			class_dict.setdefault(glyph.name.split(alt_mark)[0], set([glyph.name.split(alt_mark)[0]])).add(glyph.name)

		if len(clear_comp) > 1:
			print 'WARN:\t Glyph: %s; Multiple components: %s' %(glyph.name, clear_comp)

# - Finish ------------------------------------------------
print '- Suggested glyph classes ----'

for key, value in class_dict.iteritems():
	#new_json_class = jsontree({'1st': True, 'names': sorted(value), 'name': key, '2nd':True})
	new_json_1st_class = jsontree({'1st': True, 'names': sorted(value), 'name': '%s_1st' %key, '2nd':False})
	new_json_2nd_class = jsontree({'1st': False, 'names': sorted(value), 'name': '%s_2nd' %key, '2nd':True})
		
	#jfont.data.font.masters[1].fontMaster.kerning.kerningClasses.append(new_json_class)
	jfont.data.font.masters[1].fontMaster.kerning.kerningClasses.append(new_json_1st_class)
	jfont.data.font.masters[1].fontMaster.kerning.kerningClasses.append(new_json_2nd_class)
	print 'ADD:\t 1st and 2nd Classes: %s -> %s' %(key, ' '.join(sorted(value)))

jfont.save()
print 'DONE.'