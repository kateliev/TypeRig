#FLM: Font: Find Advanced Metric Expressions
# VER: 1.0
#----------------------------------
# Foundry:  Karandash
# Typeface: Achates
# Date:   17.06.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
import fontgate as fgt

import typerig.proxy as proxy
import typerig.glyph as gl
from typerig.brain import Coord

from py_expression_eval import Parser

# - Tools ---------- -----------
def recalcEQ(font, glyph, parser, layer=None):
	lsb_eq, rsb_eq = g.getSBeq(layer)
	italic_angle = glyph.italicAngle()

	# - Parse LSB
	if '/' in lsb_eq or '*' in lsb_eq:
		
		
		if 'sb' not in lsb_eq:
			lsb_eq_vars = [var for var in parser.parse(lsb_eq.strip('=')).variables()]
			lsb_calc_vars = {src_glyph.name:src_glyph.getLSB(layer) for src_glyph in font.pGlyphs(lsb_eq_vars)}
			
			re_val = int(lsb_calc_vars[lsb_eq_vars[0]] - parser.parse(lsb_eq.strip('=')).evaluate(lsb_calc_vars))
			print 'REVAL:\tGlyph:%s\t-- LSB -->\t%s\t-- NEW --> %s;' %(g.name, lsb_eq, '%s%+d'%(lsb_eq_vars[0], re_val))
			
		else:
			print 'WARN:\tGlyph:%s\t-- LSB --x\t%s;' %(g.name, lsb_eq)

	
	# - Parse RSB
	if '/' in rsb_eq or '*' in lsb_eq:
		

		if 'sb' not in lsb_eq:
			rsb_eq_vars = [var.strip('"') for var in parser.parse(rsb_eq.strip('=')).variables() if 'sb' not in var]
			rsb_calc_vars = {src_glyph.name:src_glyph.getRSB(layer) for src_glyph in font.pGlyphs(rsb_eq_vars)}
			
			re_val = int(rsb_calc_vars[rsb_eq_vars[0]] - parser.parse(rsb_eq.strip('=')).evaluate(rsb_calc_vars))
			print 'REVAL:\tGlyph:%s\t-- RSB -->\t%s\t-- NEW --> %s;' %(g.name, rsb_eq, '%s%+d'%(rsb_eq_vars[0], re_val))
		else:
			print 'WARN:\tGlyph:%s\t-- RSB --x\t%s;' %(g.name, rsb_eq)



# - Init -----------------------------
font = proxy.pFont()
parser = Parser()

print 'Begin: Find advanced metric expressions that contain Multiplication or Division.\n'

for g in font.pGlyphs():
	recalcEQ(font, g, parser)

# - Finish ---------------------------
print '\nDone.'