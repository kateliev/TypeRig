#FLM: Font: Auto Anchors Drop
# VER: 1.0
#----------------------------------
# Foundry: 	Borges Type
# Typeface: Future Tense
# Date:		22.10.2018
#----------------------------------

# - Dependancies
import fontlab as fl6

from typerig.proxy import pFont
from typerig.glyph import eGlyph

# - Init ------------------------------------------------
font = pFont()
clear_anchors = True
work_layer = None

# -- Diacritic creation pattern (config dictionary)
diac_cfg_all = {
			'A':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'C':[('top', work_layer, (0, 800), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'D':[('top', work_layer, (0, 800), ('A', None), 5, False, False)		],
			'E':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'G':[('top', work_layer, (0, 800), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'H':[('top', work_layer, (0, 800), ('AT', None), 5, False, False)		],
			'I':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'J':[('top', work_layer, (0, 800), ('AT', None), 5, False, False)		],
			'K':[('top', work_layer, (-30, 800), ('AT', None), 5, False, False), 	('bottom', work_layer, (-10, 0), ('C', None), 5, False, False)],
			'L':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'N':[('top', work_layer, (0, 800), ('A', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'O':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'R':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'S':[('top', work_layer, (0, 800), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'T':[('top', work_layer, (0, 800), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'U':[('top', work_layer, (0, 800), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'W':[('top', work_layer, (0, 800), ('A', None), 5, False, False)		],
			'Y':[('top', work_layer, (0, 800), ('C', None), 5, False, False)	 	],
			'Z':[('top', work_layer, (0, 800), ('AT', None), 5, False, False) 		],
			'a':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'c':[('top', work_layer, (0, 695), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'd':[('top', work_layer, (0, 695), ('A', None), 5, False, False)	 	],
			'e':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'g':[('top', work_layer, (0, 695), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'h':[('top', work_layer, (0, 695), ('AT', None), 5, False, False) 		],
			'i':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'j':[('top', work_layer, (0, 695), ('AT', None), 5, False, False) 		],
			'k':[('top', work_layer, (-20, 695), ('AT', None), 5, False, False),	('bottom', work_layer, (-10, 0), ('C', None), 5, False, False)],
			'l':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'n':[('top', work_layer, (0, 695), ('A', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'o':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'r':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			's':[('top', work_layer, (0, 695), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			't':[('top', work_layer, (0, 695), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'u':[('top', work_layer, (0, 695), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'w':[('top', work_layer, (0, 695), ('A', None), 5, False, False)	 	],
			'y':[('top', work_layer, (0, 695), ('C', None), 5, False, False)	 	],
			'z':[('top', work_layer, (0, 695), ('AT', None), 5, False, False) 		]
		}

diac_cfg_smcp = {
			'a':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'c':[('top', work_layer, (0, 625), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'd':[('top', work_layer, (0, 625), ('A', None), 5, False, False)	 	],
			'e':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'g':[('top', work_layer, (0, 625), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'h':[('top', work_layer, (0, 625), ('AT', None), 5, False, False) 		],
			'i':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('R', None), 5, False, False)],
			'j':[('top', work_layer, (0, 625), ('AT', None), 5, False, False) 		],
			'k':[('top', work_layer, (-20, 625), ('AT', None), 5, False, False),	('bottom', work_layer, (-10, 0), ('C', None), 5, False, False)],
			'l':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'n':[('top', work_layer, (0, 625), ('A', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'o':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'r':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			's':[('top', work_layer, (0, 625), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			't':[('top', work_layer, (0, 625), ('AT', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('A', None), 5, False, False)],
			'u':[('top', work_layer, (0, 625), ('C', None), 5, False, False), 		('bottom', work_layer, (0, 0), ('C', None), 5, False, False)],
			'w':[('top', work_layer, (0, 625), ('A', None), 5, False, False)	 	],
			'y':[('top', work_layer, (0, 625), ('C', None), 5, False, False)	 	],
			'z':[('top', work_layer, (0, 625), ('AT', None), 5, False, False) 		]
		}
	
# - Procedures ---------------------------------------------
def dropAnchors(glyph, control):
	# - Init
	work_name = glyph.name.split('.')[0] 
	
	# - Process
	if work_name in control.keys():
		
		work_glyph = eGlyph(font.fg, glyph)
		#work_glyph.clearAnchors(work_layer)

		for ctr_tuple in control[work_name]:
			work_glyph.dropAnchor(*ctr_tuple)

		work_glyph.update()
		work_glyph.updateObject(work_glyph.fl, 'Drop anchors: %s.' %work_glyph.name)

# - Process ------------------------------------------------
for glyph in font.glyphs():
	if 'smcp' not in glyph.name:
		dropAnchors(glyph, diac_cfg_all)

	if 'smcp' in glyph.name:
		dropAnchors(glyph, diac_cfg_smcp)	
		


# - Finish
font.update()
print 'DONE.'