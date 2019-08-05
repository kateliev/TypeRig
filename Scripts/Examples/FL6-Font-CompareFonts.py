#FLM: Font: Compare Fonts
# VER: 1.0
#----------------------------------
# Foundry:  Karandash
# Typeface: Achates
# Date:     09.05.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph

# - Init ------------------------------------------------
all_fonts = [pFont(font) for font in fl6.AllFonts()]
compare_names = [font.PSfullName for font in all_fonts]
compare_glyphs = [set(font.getGlyphNames()) for font in all_fonts]

# - Process --------------------------------------------
f1n, f2n = compare_names
f1, f2 = compare_glyphs

print 'Font:\t%s;\nMissing:\n%s\n\n' %(f2n, '/'+' /'.join(f1.difference(f2)))
print 'Font:\t%s;\nMissing:\n%s\n\n' %(f1n, '/'+' /'.join(f2.difference(f1)))
		
# - Finish --------------------------------------------
#font.update()
print 'DONE.'

