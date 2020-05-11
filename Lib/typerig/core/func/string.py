# MODULE: TypeRig / Core / String (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------

# - Init --------------------------------
__version__ = '0.26.1'

# - Functions ---------------------------
# -- Unicode ----------------------------
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
	from itertools import product	
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
	from itertools import product	
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