# MODULE: TypeRig / Core / String (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division, unicode_literals
from itertools import product

# - Init --------------------------------
__version__ = '0.26.4'


# - Functions ---------------------------
# -- Compatibility to Py 2.7+ 
try: unichr
except NameError: unichr = chr

try: unicode
except NameError: unicode = str

# -- Unicode ----------------------------
def getLowercaseInt(unicodeInt):
	''' Based on given Uppercase Unicode (Integer) returns coresponding Lowercase Unicode (Integer) '''
	return ord(unicode(unichr(unicodeInt)).lower())

def getUppercaseInt(unicodeInt):
	''' Based on given Lowercase Uniocde (Integer) returns coresponding Uppercase Unicode (Integer) '''
	return ord(unicode(unichr(unicodeInt)).upper())


def getLowercaseCodepoint(unicodeName):
	''' Based on given Uppercase Unicode Name (String) returns coresponding Lowercase Unicode Name! Names are in Adobe uniXXXX format'''
	if 'uni' in unicodeName:
		return 'uni0%X' %ord(unichr(int(unicodeName.replace('uni','0x'), 16)).lower())
	else:
		if unicodeName.isupper() or unicodeName.istitle():
			return unicodeName.lower() # not encoded in Adobe uniXXXX format (output for mixed lists)
		else:
			return unicodeName

def getUppercaseCodepoint(unicodeName):
	''' Based on given Uppercase Unicode Name (String) returns coresponding Uppercase Unicode Name! Names are in Adobe uniXXXX format'''
	if 'uni' in unicodeName:
		return 'uni0%X' %ord(unichr(int(unicodeName.replace('uni','0x'), 16)).upper())
	else:
		if unicodeName.islower():
			return unicodeName.title() # not encoded in Adobe uniXXXX format, capitalize fisrt letter (output for mixed lists)! Note: use .upper() for all upercase
		else:
			return unicodeName

# -- Generators ----------------------
def kpxGen(inputA, inputB, suffix=('','')):
	''' Generate AMF style KPX paris for kerning'''
	genPattern = 'KPX {0}{2} {1}{3}'
	return [genPattern.format(pair[0], pair[1], suffix[0], suffix[1]) for pair in product(inputA, inputB)]


def stringGen(inputA, inputB, filler=('HH','HH'), genPattern = 'FL A B A FR', suffix=('',''), sep='/'):
	''' Generate test text string for metrics, kerning and pairs/phrases
	Args:
		inputA, inputB (list/string) : Input lists to be paired
		filler (tuple(str)) : Filler string 
		genPattern (string): A SPACE separated ordering pattern, where FL, FR is Filler Left/Right and A, B are input strings
		suffix (tuple(str)) : Suffixes to be added to inputs A and B
		sep (str) : Glyph Separator to be used. '/' default for Fontlab
	
	Returns:
		list(str)
	'''
	genPattern = '{1}{0}'.format(sep.join(['{%s}' %s if s.isalpha() else '%s' %s for s in genPattern.split(' ')]), sep) 
	fillerLeft = sep.join([char for char in filler[0]]) if sep not in filler[0] else filler[0][1:] # fix that filler[0][1:] some day! It is a drity fix of double separator being inserted at the begining.
	fillerRight = sep.join([char for char in filler[1]]) if sep not in filler[1] else filler[1][1:]
	return [genPattern.format(**{'FL':fillerLeft, 'FR': fillerRight, 'A':pair[0] + suffix[0], 'B':pair[1] + suffix[1]}) for pair in product(inputA, inputB)]

def stringGenPairs(pairs_input, filler=('HH','HH'), genPattern = 'FL A B A FR', suffix=('',''), sep='/'):
	''' Generate test text string for metrics, kerning and pairs/phrases
	Args:
		pairs_input (list(tuple)): Input list contaiing pairs
		filler (tuple(str)) : Filler string 
		genPattern (string): A SPACE separated ordering pattern, where FL, FR is Filler Left/Right and A, B are input strings
		suffix (tuple(str)) : Suffixes to be added to inputs A and B
		sep (str) : Glyph Separator to be used. '/' default for Fontlab
	
	Returns:
		list(str)
	'''
	genPattern = ''.join(['/{%s}' %s if s.isalpha() else ' %s' %s for s in genPattern.split(' ')])
	fillerLeft = sep.join([char for char in filler[0]]) if sep not in filler[0] else filler[0][1:] # fix that filler[0][1:] some day! It is a drity fix of double separator being inserted at the begining.
	fillerRight = sep.join([char for char in filler[1]]) if sep not in filler[1] else filler[1][1:]
	return [genPattern.format(**{'FL':fillerLeft, 'FR': fillerRight, 'A':pair[0] + suffix[0], 'B':pair[1] + suffix[1]}) for pair in pairs_input]

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
	return [n for n in listItems if n != discard]

def strRepDict(stringItems, replacementDicionary, method = 'replace'):
	'''	Replaces every instance of [stringItems] according to [replacementDicionary] using 'replace' ('r') or 'consecutive' replacement ('c') [method]s
	Example: strRepDict('12', {'1':'/one', '2':'/two'}, 'r') '''
	if method == 'replace' or method == 'r':
		for key, value in replacementDicionary.items():
			stringItems = stringItems.replace(key, value)
		return stringItems

	elif method == 'consecutive' or method == 'c':
		return lst2str([replacementDicionary[item] if item in replacementDicionary.keys() else item for item in stringItems], '')

	elif method == 'unicodeinteger' or method == 'i':
		return lst2str([replacementDicionary[ord(item)] for item in unicode(stringItems) if ord(item) in replacementDicionary.keys()], ' ')

if __name__ == '__main__':
	ch = ord('E')
	uni_zhe_uc = 'uni0416'
	uni_zhe_lc = 'uni0436'
	inputA = 'ABC'
	inputB = 'DEF'
	pairs_input = zip('a b c d'.split(), 'e f g h'.split())

	print(chr(getLowercaseInt(ch)))
	print(chr(getUppercaseInt(getLowercaseInt(ch))))
	print(getLowercaseCodepoint(uni_zhe_uc) == uni_zhe_lc) 
	print(getUppercaseCodepoint(uni_zhe_lc) == uni_zhe_uc)
	print(kpxGen(inputA, inputB, suffix=('','')))
	print(stringGen(inputA, inputB, filler=('HH','HH'), genPattern = 'FL A B A FR', suffix=('',''), sep='/'))
	print(stringGenPairs(pairs_input, filler=('HH','HH'), genPattern = 'FL A B A FR', suffix=('',''), sep='/'))
	print(strNormSpace('a     f g   g r 1'))
	#print(lst2str(listItems, separator))
	#print(str2lst(stringItems, separator))
	#print(lstcln(listItems, discard))
	#print(strRepDict(stringItems, replacementDicionary, method = 'replace'))