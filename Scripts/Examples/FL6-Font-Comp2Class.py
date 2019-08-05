#FLM: Font: Kern Classes from composites
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
kerning_groups = font.kerning_groups()

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
	kerning_groups['%s_L' %key] = (sorted(value), 'KernLeft')
	kerning_groups['%s_R' %key] = (sorted(value), 'KernRight')

	print 'ADD:\t 1st and 2nd Classes: %s -> %s' %(key, ' '.join(sorted(value)))

font.update()
print 'DONE.'