# MODULE: Misc Utils | Typerig
# VER   : 0.03
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Note: Revisit as most of these are redundant as they were needed for FDK5, some are even from Python 2.4 times

# - Dependencies -------------------------
import json
import json.scanner
from collections import defaultdict

# - Classes -------------------------------------------------------
# -- VFJ Font: Fontlab 6 JSON File format -------------------------
# --- VFJ Font helper classes
class jsontree(defaultdict):
	'''
	Default dictionary where keys can be accessed as attributes
	----
	Adapted from JsonTree by Doug Napoleone: https://github.com/dougn/jsontree
	'''
	def __init__(self, *args, **kwdargs):
		super(jsontree, self).__init__(jsontree, *args, **kwdargs)
		
	def __getattribute__(self, name):
		try:
			return object.__getattribute__(self, name)
		except AttributeError:
			return self[name]
	
	def __setattr__(self, name, value):
		self[name] = value
		return value
	
	def __repr__(self):
	  return str(self.keys())


class vfj_decoder(json.JSONDecoder):
	'''
	VFJ (JSON) decoder class for deserializing to a jsontree object structure.
	----
	Parts adapted from JsonTree by Doug Napoleone: https://github.com/dougn/jsontree
	'''
	def __init__(self, *args, **kwdargs):
		super(vfj_decoder, self).__init__(*args, **kwdargs)
		self.__parse_object = self.parse_object
		self.parse_object = self._parse_object
		self.scan_once = json.scanner.py_make_scanner(self)
		self.__jsontreecls = jsontree
	
	def _parse_object(self, *args, **kwdargs):
		result = self.__parse_object(*args, **kwdargs)
		return self.__jsontreecls(result[0]), result[1]


class vfj_encoder(json.JSONEncoder):
	'''
	VFJ (JSON) encoder class that serializes out jsontree object structures.
	----
	Parts adapted from JsonTree by Doug Napoleone: https://github.com/dougn/jsontree
	'''
	def __init__(self, *args, **kwdargs):
		super(vfj_encoder, self).__init__(*args, **kwdargs)
	
	def default(self, obj):
		return super(vfj_encoder, self).default(obj)

# - Functions ----------------------------------------------
# -- Units -------------------------------------------------
def point2pixel(points):
	return points*1.333333

def pixel2point(pixels):
	return pixels*0.75

def inch2point(inches):
	return inches*71.999999999999

def point2inch(points):
	return points*0.013888888888889

# -- Workign with Strings ----------------------------------
def strNormSpace(string):
	'''
	Removes all mutiple /space characters from [string]
	'''
	return ' '.join(string.split())

def lst2str(listItems, separator):
	'''
	Converts [listItems] to 'String' using 'String separator'
	Example: lst2str([List], ',')
	'''
	return separator.join(str(n) for n in listItems)

def str2lst(stringItems, separator):
	'''
	Converts 'stringItems' to [List] using 'String separator'
	Example: str2lst(String, ',')
	'''
	return [n for n in stringItems.split(separator)]

def lstcln(listItems, discard):
	'''
	Cleans a [listItems] by removing [discard]
	Example: lstcln([List], '/space')
	'''
	return [n for n in listItems if n is not discard]

def strRepDict(stringItems, replacementDicionary, method = 'replace'):
	'''
	Replaces every instance of [stringItems] according to [replacementDicionary] using 'replace' ('r') or 'consecutive' replacement ('c') [method]s
	Example: strRepDict('12', {'1':'/one', '2':'/two'}, 'r')
	'''
	if method is 'replace' or method is 'r':
		for key, value in replacementDicionary.iteritems():
			stringItems = stringItems.replace(key, value)
		return stringItems

	elif method is 'consecutive' or method is 'c':
		return lst2str([replacementDicionary[item] if item in replacementDicionary.keys() else item for item in stringItems], '')

	elif method is 'unicodeinteger' or method is 'i':
		return lst2str([replacementDicionary[ord(item)] for item in unicode(stringItems) if ord(item) in replacementDicionary.keys()], ' ')

# -- Dictionary operations ----------------------------------
def mergeDicts(d1, d2, merge = lambda x, y : y):
	'''
	Merges two dictionaries [d1, d2], combining values on duplicate keys as defined by the optional [merge] function.
	--------
	Example: merge(d1, d2, lambda x,y: x+y) -> {'a': 2, 'c': 6, 'b': 4}
	
	'''
	mergeDict = dict(d1)
	for key, value in d2.iteritems():
		
		if key in mergeDict:
			mergeDict[key] = merge(mergeDict[key], value)
		else:
			mergeDict[key] = value

	return mergeDict

# -- Lists ------------------------------------------------
def unpack(listItems):
	'''
	Unpacks all items form [listItems] containing other lists, sets and etc.
	'''
	from itertools import chain
	return list(chain(*listItems))

def enumerateWithStart(sequence, start = 0):
	'''
	Performs [enumerate] of a [sequence] with added [start] functionality (available in Python 2.6)
	'''
	for element in sequence:
		yield start, element
		start += 1

def combineReccuringItems(listItems):
	'''
	Combines recurring items in [listItems] and returns a list containing sets of grouped items
	'''
	temp = [set(item) for item in listItems if item]

	for indexA, valueA in enumerate(temp) :
		for indexB, valueB in enumerateWithStart(temp[indexA+1 :], indexA+1): # REMOVE and REPLACE with enumerate(item,start) if using  Python 2.6 or above
		   if valueA & valueB:
			  temp[indexA] = valueA.union(temp.pop(indexB))
			  return combineReccuringItems(temp)

	return [tuple(item) for item in temp]

def groupConsecutives(listItems, step = 1):
	'''
	Build a list of lists containig consecutive numbers from [listItems] (number list) within [step]
	'''
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

# -- Unicode ---------------------------------------------------------
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

# - Internals ---------------------------------------------------------
def getFunctionName():
	'''Return the name of current function (def)'''
	from inspect import stack
	return stack()[1][3]

# - Legacy FL5 related ------------------------------------------------
class fontClassesFromFile(object):
	'''Loads a Fontlab class file (.flc) and parses it. 
	Args:
		fileName (str) : a path to Fontlab class file
	Returns:
		Object with methods:
			.fontClasses (dict -> class_name:class_contents)
			.metricClasses (dict -> class_name:class_contents)
			.kernClasses (dict -> class_name:class_contents)
			.otClasses (dict -> class_name:class_contents)
			.classPosition (Left and/or Right pair(s)); Metric (Left, Width, Right)
			.classLeader (dict -> class_name:class_leader)
	
		'''
	def __init__(self, fileName):       
		# - Init
		self.fontClasses, self.metricClasses, self.kernClasses, self.otClasses, self.classPosition, self.classLeader = {}, {}, {}, {}, {}, {}

		# - Parse file
		# -- Fontlab class file internal commands
		cBegin = '%%CLASS'
		cGlyphs = '%%GLYPHS'
		cKern = '%%KERNING'
		cMetric = '%%METRICS'
		cEnd = '%%END'

		with open(fileName) as classData:
			className, classGlyphs, classPos = '', '', ''
			 
			for line in classData:
				if cBegin in line: 
					className = line.replace(cBegin, '').strip()
					
				if cGlyphs in line:
					classGlyphs = [item for item in line.replace(cGlyphs, '').strip().split(' ') if len(item)]
					self.fontClasses[className] = classGlyphs

				if cKern in line: 
					classPos = line.replace(cKern, '').strip()
					self.classPosition[className] = classPos[:-1].strip() if len(classPos) else None

				if cMetric in line: 
					classPos = line.replace(cMetric, '').strip()
					self.classPosition[className] = classPos[:-1].strip() if len(classPos) else None
			
				if cEnd in line: 
					pass
					
		# - Finish 
		for key, value in self.fontClasses.iteritems():
			findLeader = [item for item in value if "'" in item]
			self.classLeader[key] = findLeader[0].replace("'", '') if len(findLeader) else value[0]

			if key[0] is '.':
				self.metricClasses[key] = value
			elif key[0] is '_':
				self.kernClasses[key] = value
			else:
				self.otClasses[key] = value
				del self.classLeader[key]