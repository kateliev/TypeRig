# MODULE: Typerig / Proxy / String (Constants)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependancies --------------------------------------------
#from typerig.core.func.string import *

# - Init ----------------------------------------------------
__version__ = '0.18.5'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Collections (Static)
# -- Values
ligatureMark, alternateMark = '_', '.'
metricClass, kerningClass, opentypeClass = '.', '-', '' # Fontlab Class prefixes

# -- Lists
uppercaseLAT = [ 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
lowercaseLAT = [ 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
lowercaseDIA = ['a', 'agrave', 'aacute', 'acircumflex', 'atilde', 'adieresis', 'aring', 'ae', 'amacron', 'abreve', 'aogonek', 'o', 'ograve', 'oacute', 'ocircumflex', 'otilde', 'odieresis', 'oslash', 'omacron', 'obreve', 'ohungarumlaut', 'oe', 'i', 'uni0457', 'igrave', 'iacute', 'icircumflex', 'idieresis', 'itilde', 'imacron', 'ibreve', 'iogonek', 'ij', 'e', 'egrave', 'eacute', 'ecircumflex', 'edieresis', 'uni0450', 'uni0451', 'eth', 'emacron', 'ebreve', 'edotaccent', 'eogonek', 'ecaron', 'eng', 'c', 'ccedilla', 'cacute', 'ccircumflex', 'cdotaccent', 'ccaron', 'g', 'gcircumflex', 'gbreve', 'gdotaccent', 'gcommaaccent', 's', 'sacute', 'scircumflex', 'scedilla', 'scaron', 'uni0453', 'd', 'dcaron', 'dcroat', 'l', 'lacute', 'lcommaaccent', 'lcaron', 'ldot', 'lslash', 'f', 'longs', 'germandbls', 't', 'tcaron', 'tbar', 'p', 'b', 'thorn', 'u', 'ugrave', 'uacute', 'ucircumflex', 'udieresis', 'utilde', 'umacron', 'ubreve', 'uring', 'uhungarumlaut', 'y', 'yacute', 'ydieresis', 'ycircumflex', 'z', 'zacute', 'zdotaccent', 'zcaron', 'w', 'wcircumflex', 'n', 'ntilde', 'nacute', 'ncommaaccent', 'ncaron', 'napostrophe', 'k', 'kcommaaccent', 'kgreenlandic', 'uni045C', 'h', 'hcircumflex', 'hbar', 'uni045B', 'uni0452']
uppercaseCYR = ['uni0410', 'uni0411', 'uni0412', 'uni0413', 'uni0414', 'uni0415', 'uni0416', 'uni0417', 'uni0418', 'uni0419', 'uni041A', 'uni041B', 'uni041C', 'uni041D', 'uni041E', 'uni041F', 'uni0420', 'uni0421', 'uni0422', 'uni0423', 'uni0424', 'uni0425', 'uni0426', 'uni0427', 'uni0428', 'uni0429', 'uni042A', 'uni042B', 'uni042C', 'uni042D', 'uni042E', 'uni042F']
lowercaseCYR = ['uni0430', 'uni0431', 'uni0432', 'uni0433', 'uni0434', 'uni0435', 'uni0436', 'uni0437', 'uni0438', 'uni0439', 'uni043A', 'uni043B', 'uni043C', 'uni043D', 'uni043E', 'uni043F', 'uni0440', 'uni0441', 'uni0442', 'uni0443', 'uni0444', 'uni0445', 'uni0446', 'uni0447', 'uni0448', 'uni0449', 'uni044A', 'uni044B', 'uni044C', 'uni044D', 'uni044E', 'uni044F']
figureNames = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

baseGlyphsetKeys = ('Latin_Upper', 'Latin_Lower', 'Cyrillic_Upper', 'Cyrillic_Lower', 'Figures')
baseGlyphsetNames = (uppercaseLAT, lowercaseLAT, uppercaseCYR, lowercaseCYR, figureNames)
baseGlyphset = dict(zip(baseGlyphsetKeys, baseGlyphsetNames))

upper_diac_marks = ['grave', 'dieresis', 'macron', 'acute', 'circumflex', 'caron', 'breve', 'dotaccent', 'ring', 'tilde', 'hungarumlaut', 'cyrbreve'] # 'dotlessi', 'dotlessj'
lower_diac_marks= ['cedilla', 'ogonek', 'commaaccent'] # 'dotlessi', 'dotlessj'
diactiricalMarks = list(set(lower_diac_marks + upper_diac_marks + ['uni02BC', 'caroncomma']))

fillerList = [('nn','nn'), ('oo','oo'), ('HH','HH'), ('OO','OO'), ('HOII', 'IIOH'), ('ll','ll'), ('dll','llb'), ('hoii', 'iioh')]

# -- Dicts
combiningMarks = {'uni030B': 'hungarumlaut', 'uni030C': 'caron', 'uni030A': 'ring', 'acutecomb': 'acute', 'uni0306': 'breve', 'uni0307': 'dotaccent', 'uni0304': 'macron', 'uni0302': 'circumflex', 'gravecomb': 'grave', 'tildecomb': 'tilde', 'uni0308': 'dieresis'}

# - Classes --------------------------------------------------
class OTGen(object):
	''' Generate OpenType features '''
	def __init__(self):
		# - Templates
		self.simple_fea = 'feature {tag} {{ # {com}\n{body}\n}} {tag};'
		self.simple_sub = '\tsub {glyph_in} by {glyph_out};'
		self.simple_liga = '\tsub {glyph_in} by {glyph_out};'

		self.sub_suffix = '\tsub {glyph} by {glyph}.{suffix};'
		self.sub_multiple = '\tsub {glyph} from [{glyph_list}];'
		
		self.lookup_fea = 'lookup {tag} {{\n{body}\n}} {tag};'
		self.lookup_use = 'lookup {tag};'