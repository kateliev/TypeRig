#FLM: Report: Incompatible glyphs
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     27.02.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph
from PythonQt import QtGui

# - Init ------------------------------------------------
font = pFont()
process_glyphs = font.pGlyphs()
serach_result = set()

# - Process --------------------------------------------
for work_glyph in process_glyphs:
	if not work_glyph.isCompatible(): serach_result.add(work_glyph.name)

result_string = '/'+' /'.join(list(serach_result))

# - Finish --------------------------------------------
print '--- Incompatible Glyphs (string) ---'
print result_string

# -- Copy to cliboard
clipboard = QtGui.QApplication.clipboard()
clipboard.setText(result_string)
print '--- String sent to clipboard ---'
print 'DONE.'
