# MODULE: String | Typerig
# VER 	: 0.16
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependancies -----------------


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

diactiricalMarks = ['grave', 'dieresis', 'macron', 'acute', 'cedilla', 'uni02BC', 'circumflex', 'caron', 'breve', 'dotaccent', 'ring', 'ogonek', 'tilde', 'hungarumlaut', 'caroncomma', 'commaaccent', 'cyrbreve'] # 'dotlessi', 'dotlessj'

fillerList = [('nn','nn'), ('HH','HH'), ('HOII', 'IIOH'), ('ll','ll'), ('dll','llb'), ('hoii', 'iioh')]

# -- Dicts
combiningMarks = {'uni030B': 'hungarumlaut', 'uni030C': 'caron', 'uni030A': 'ring', 'acutecomb': 'acute', 'uni0306': 'breve', 'uni0307': 'dotaccent', 'uni0304': 'macron', 'uni0302': 'circumflex', 'gravecomb': 'grave', 'tildecomb': 'tilde', 'uni0308': 'dieresis'}

# - Basic Functions ---------------------
# -- Workign with Strings ---------------
def strNormSpace(string):
	'''	Removes all mutiple /space characters from [string] '''
	return ' '.join(string.split())

def lst2str(listItems, separator):
	''' Converts [listItems] to 'String' using 'String separator'
	Example: lst2str([List], ',') '''
	return separator.join(str(n) for n in listItems)

def str2lst(stringItems, separator):
	'''	Converts 'stringItems' to [List] using 'String separator'
	Example: str2lst(String, ',') '''
	return [n for n in stringItems.split(separator)]

def lstcln(listItems, discard):
	'''	Cleans a [listItems] by removing [discard]
	Example: lstcln([List], '/space') '''
	return [n for n in listItems if n is not discard]

def strRepDict(stringItems, replacementDicionary, method = 'replace'):
	'''	Replaces every instance of [stringItems] according to [replacementDicionary] using 'replace' ('r') or 'consecutive' replacement ('c') [method]s
	Example: strRepDict('12', {'1':'/one', '2':'/two'}, 'r') '''
	if method is 'replace' or method is 'r':
		for key, value in replacementDicionary.iteritems():
			stringItems = stringItems.replace(key, value)
		return stringItems

	elif method is 'consecutive' or method is 'c':
		return lst2str([replacementDicionary[item] if item in replacementDicionary.keys() else item for item in stringItems], '')

	elif method is 'unicodeinteger' or method is 'i':
		return lst2str([replacementDicionary[ord(item)] for item in unicode(stringItems) if ord(item) in replacementDicionary.keys()], ' ')

# -- Dictionary ---------------
def mergeDicts(d1, d2, merge = lambda x, y : y):
	'''	Merges two dictionaries [d1, d2], combining values on duplicate keys as defined by the optional [merge] function.
	--------
	Example: merge(d1, d2, lambda x,y: x+y) -> {'a': 2, 'c': 6, 'b': 4}	'''
	mergeDict = dict(d1)
	for key, value in d2.iteritems():
		
		if key in mergeDict:
			mergeDict[key] = merge(mergeDict[key], value)
		else:
			mergeDict[key] = value

	return mergeDict

# -- Lists ---------------
def unpack(listItems):
	'''	Unpacks all items form [listItems] containing other lists, sets and etc. '''
	from itertools import chain
	return list(chain(*listItems))

def enumerateWithStart(sequence, start = 0):
	'''	Performs [enumerate] of a [sequence] with added [start] functionality (available in Python 2.6)	'''
	for element in sequence:
		yield start, element
		start += 1

def combineReccuringItems(listItems):
	'''	Combines recurring items in [listItems] and returns a list containing sets of grouped items	'''
	temp = [set(item) for item in listItems if item]

	for indexA, valueA in enumerate(temp) :
		for indexB, valueB in enumerateWithStart(temp[indexA+1 :], indexA+1): # REMOVE and REPLACE with enumerate(item,start) if using  Python 2.6 or above
		   if valueA & valueB:
			  temp[indexA] = valueA.union(temp.pop(indexB))
			  return combineReccuringItems(temp)

	return [tuple(item) for item in temp]

def groupConsecutives(listItems, step = 1):
	'''	Build a list of lists containig consecutive numbers from [listItems] (number list) within [step] '''
	tempList = []
	groupList = [tempList]
	expectedValue = None

	for value in listItems:
		if (value == expectedValue) or (expectedValue is None):
			tempList.append(value)
		
		else:
			tempList = [value]
			groupList.append(tempList)
		
		expectedValue = value + step
	
	return groupList

# -- Unicode ---------------
def getLowercaseInt(uniocdeInt):
	''' Based on given Uppercase Unicode (Integer) returns coresponding Lowercase Unicode (Integer) '''
	return ord(unicode(unichr(uniocdeInt)).lower())

def getUppercaseInt(uniocdeInt):
	''' Based on given Lowercase Uniocde (Integer) returns coresponding Uppercase Unicode (Integer) '''
	return ord(unicode(unichr(uniocdeInt)).upper())

def getLowercaseCodepoint(unicodeName):
	''' Based on given Uppercase Unicode Name (String) returns coresponding Lowercase Unicode Name! Names are in Adobe uniXXXX format'''
	if 'uni' in unicodeName:
		return 'uni' + unichr(ord(('\u' + unicodeName.replace('uni','')).decode("unicode_escape"))).lower().encode("unicode_escape").strip('\u').upper()
	else:
		if unicodeName.isupper() or unicodeName.istitle():
			return unicodeName.lower() # not encoded in Adobe uniXXXX format (output for mixed lists)
		else:
			return unicodeName

def getUppercaseCodepoint(unicodeName):
	''' Based on given Uppercase Unicode Name (String) returns coresponding Uppercase Unicode Name! Names are in Adobe uniXXXX format'''
	if 'uni' in unicodeName:
		return 'uni' + unichr(ord(('\u' + unicodeName.replace('uni','')).decode("unicode_escape"))).upper().encode("unicode_escape").strip('\u').upper()
	else:
		if unicodeName.islower():
			return unicodeName.title() # not encoded in Adobe uniXXXX format, capitalize fisrt letter (output for mixed lists)! Note: use .upper() for all upercase
		else:
			return unicodeName

# -- Generators ----------------------
def stringGen(inputA, inputB, filler=('HH','HH'), genPattern = 'FL A B A FR', suffix=('',''), sep='/'):
	''' Generate test text string
	Args:
		inputA, inputB (list/string) : Input lists to be paired
		filler (tuple(str)) : Filler string 
		genPattern (string): A SPACE separated ordering pattern, where FL, FR is Filler Left/Right and A, B are input strings
		suffix (tuple(str)) : Suffixes to be added to inputs A and B
		sep (str) : Glyph Separator to be used. '/' default for Fontlab
	
	Returns:
		list(str)
	'''
	from itertools import product	
	genPattern = '{1}{0}'.format(sep.join(['{%s}' %s for s in genPattern.split(' ')]), sep) 
	fillerLeft = sep.join([char for char in filler[0]])
	fillerRight = sep.join([char for char in filler[1]])
	return [genPattern.format(**{'FL':fillerLeft, 'FR': fillerRight, 'A':pair[0] + suffix[0], 'B':pair[1] + suffix[1]}) for pair in product(inputA, inputB)]

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