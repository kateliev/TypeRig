#FLM: Font: Get Metrics
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     14.12.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont, pGlyph
from typerig.glyph import eGlyph

# - Init ------------------------------------------------
font = pFont()
layers = ['100','900']


# - Process --------------------------------------------
for glyph in font.selectedGlyphs(extend=pGlyph):
	for layer in layers:
		'''
		# - By metric bindings
		first, second = glyph.getSBeq(layer)
		
		if 'RSB' not in first: 
			if 'LSB' in first: first = first.relace('LSB','')
			first = filter(lambda x: x.isalpha(), first)
		else:
			first = None
		
		if 'LSB' not in second:
			if 'LSB' in second: second = second.relace('RSB','')
			second = filter(lambda x: x.isalpha(), second)
		else:
			second = None

		#assert first is not None, 'Warn! Fisrt cannot be set: %s' %glyph.name
		#assert second is not None, 'Warn! second cannot be set: %s' %glyph.name

		print 'G:%s\t%s < G > %s'%(glyph.name, first, second)
		'''
		print glyph.components(layer)


#glyph.update()

# - Finish --------------------------------------------
font.update()
print 'DONE.'
