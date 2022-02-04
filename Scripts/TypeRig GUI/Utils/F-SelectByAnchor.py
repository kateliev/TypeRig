#FLM: TR: Select By Anchor
# VER : 1.0
# ----------------------------------------
# (C) Vassil Kateliev, 2020 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependancies
from typerig.proxy.fl import pFont, pGlyph

# - Helper
def contains(listA, listB, mode):
	if len(listA) > 1:
		return True if eval('%s([item in listB for item in listA])'%mode) else False
	elif len(listA) == 1:
		return True if listA[0] in listB else False

	return False

# - Init ------------------------------
font = pFont()
selection = []

# - Configuration
# -- Add the list of your anchors here -> list(str(anchor_name)) -> example: ['top', 'bottom']
search_anchors = ['top', 'bottom'] 

# - Search mode -> str() 'any' or 'all -> Does the glyph contain 'any' of the anchors or 'all'?
search_mode = 'any' 

# -- Add here layers you would like to check -> list(str(layer_name)) -> example: ['regular', 'bold'];
# -- or use font.masters() to get list of all master layers.
working_layers = font.masters() 

# - Process ----------------------------
for glyph in font.pGlyphs():
	for layer in working_layers:
		try:
			layer_anchors = glyph.anchors(layer)
			
			if len(layer_anchors):
				layer_anchor_names = [anchor.name for anchor in layer_anchors]
				
				if contains(search_anchors, layer_anchor_names, search_mode):
					selection.append(glyph.name)
					print 'FOUND:\tGlyph: %s;\tAnchors: %s' %(glyph.name, search_anchors)
					break
		
		except AttributeError:
			break

font.unselectAll()
font.selectGlyphs(selection)
print 'DONE:\tFind Anchors...'
