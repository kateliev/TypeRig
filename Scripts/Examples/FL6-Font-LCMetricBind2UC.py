#FLM: Font: Bind LC metrics to UC
# VER: 1.0
#----------------------------------
# Foundry: 	The Font Maker
# Typeface: Bolyar Sans
# Date:		10.11.2018
#----------------------------------

# - Dependancies
import fontlab as fl6
from PythonQt import QtGui
from typerig.proxy import pFont, pGlyph
from typerig.utils import getLowercaseCodepoint, getUppercaseCodepoint


# - Init ------------------------------------------------
font = pFont()
work_layers = ['100', '900']
metric_comp = 0.6 #0.88
suffix = '.subs'
mode = 'suffix' # suffix, case

# - Process ------------------------------------------------
selection = font.selected_pGlyphs()

for glyph in selection:
	for layer in work_layers:
		if mode == 'case':
			glyph.setLSBeq('=%s*%s' %(getUppercaseCodepoint(glyph.name), metric_comp), layer)
			glyph.setRSBeq('=%s*%s' %(getUppercaseCodepoint(glyph.name), metric_comp), layer)

		elif mode == 'suffix':
			glyph.setLSBeq('=%s*%s' %(glyph.name.replace(suffix,''), metric_comp), layer)
			glyph.setRSBeq('=%s*%s' %(glyph.name.replace(suffix,''), metric_comp), layer)

	glyph.updateObject(glyph.fl, 'Set Metrics Equations @ %s.' %'; '.join(work_layers))


# - Finish
print 'DONE.'