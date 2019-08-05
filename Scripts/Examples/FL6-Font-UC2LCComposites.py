#FLM: Font: UC 2 LC composites
# VER: 1.0
#----------------------------------
# Foundry: 	The FontMaker
# Typeface: Bolyar Sans
# Date:		12.11.2018
#----------------------------------

# - Dependancies
import fontlab as fl6
from PythonQt import QtGui
from typerig.proxy import pFont, pGlyph
from typerig.utils import getLowercaseCodepoint, getUppercaseCodepoint


# - Init ------------------------------------------------
font = pFont()
design_comp = [0.88, 0.84]

# - Process ------------------------------------------------
selection = font.selectedGlyphs()
for glyph in selection:
	print '{lc}={uc}@{sx},0,0,{sy},1,1^{uc},{uc}'.format(lc=getLowercaseCodepoint(glyph.name), uc=glyph.name, sx=design_comp[0], sy=design_comp[1] )

# - Finish
print 'DONE.'