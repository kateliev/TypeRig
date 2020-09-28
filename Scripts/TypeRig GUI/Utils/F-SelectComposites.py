#FLM: TR: Select Composites
# VER : 1.0
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependancies
from typerig.proxy.fl import pFont, pGlyph

# - Init
font = pFont()
mark_color = 120 # Green

# - Process
selection = [glyph.name for glyph in font.pGlyphs() if len(glyph.layers()) and len(glyph.components())]
font.selectGlyphs(selection)
print 'Done.'
