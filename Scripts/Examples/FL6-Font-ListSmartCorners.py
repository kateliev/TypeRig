#FLM: Font: Find smart corners
# VER: 1.0
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     27.02.2019
#----------------------------------

# - Dependancies
import fontlab as fl6
from typerig.proxy import pFont, pGlyph
from typerig.node import eNode

# - Init ------------------------------------------------
font = pFont()
process_glyphs = font.pGlyphs()

filter_name = 'Smart corner'
wLayers = ['100', '900']
smart_radius = [6.,8.]
active_preset = dict(zip(wLayers, smart_radius))
serach_result = set()

# - Process --------------------------------------------
for work_glyph in process_glyphs:
	if work_glyph is not None:
		# - Init
		smart_corners = []
		
		# - Get all smart nodes/corners
		for layer in wLayers:
			wBuilders = work_glyph.getBuilders(layer)
			#print work_glyph.name, work_glyph.getBuilders(layer)

			if wBuilders is not None and filter_name in wBuilders.keys():
				if len(wBuilders[filter_name]):
					for builder in wBuilders[filter_name]:
						if builder.getSmartNodes() is not None:
							smart_corners += builder.getSmartNodes()

					if len(smart_corners):
						for node in smart_corners:
							wNode = eNode(node)

							if wNode.getSmartAngleRadius() <= float(active_preset[layer]):
								serach_result.add(work_glyph.name)
								#print 'FOUND:\t Glyph: %s; Layer: %s; Radius: %s' %(work_glyph.name, layer, active_preset[layer])

print '/'+' /'.join(list(serach_result))
# - Finish --------------------------------------------
print 'DONE.'
