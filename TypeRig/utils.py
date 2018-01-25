# MODULE: Misc Utils | Typerig
# VER   : 0.02
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Note: Revisit as most of these are redundant as they were needed for FDK5, some are even from Python 2.4 times

# - Functions ----------------------------------------------
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

# -- Math -----------------------------------------------------
def isclose(a, b, abs_tol = 1, rel_tol = 0.0):
	'''
	Tests approximate equality for values [a] and [b] within relative [rel_tol*] and/or absolute tolerance [abs_tol]

    *[rel_tol] is the amount of error allowed,relative to the larger absolute value of a or b. For example,
	to set a tolerance of 5%, pass tol=0.05. The default tolerance is 1e-9, which assures that the
    two values are the same within about9 decimal digits. rel_tol must be greater than 0.0
	'''
	if abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol):
		return True

def round2base(x, base = 5):
    '''
    Rounds [x] using given [base] increments
    '''
    return int(base * round(float(x)/base))

def ratfrac(part, whole, fraction = 100):
    '''
    Calculates the ratio - [part] to [whole] - expressed as [fraction] (percentage: 100 (default); milliage: 1000)
    '''
    return fraction*(float(part)/float(whole))

def linspread(start, end, count):
    '''
    Linear space generator object: will generate [count] equally spaced numbers within given range [start]-[end]
    '''
    yield float(start)

    for i in range(1, count-1):
        yield float(start + i*(end-start)/float((count-1))) #Adapted from NumPy.linespace

    yield float(end)

def geospread(start, end, count):
    '''
    Geometric space generator object: will generate [count] elements of geometric progression within given range [start]-[end]
    '''
    from math import sqrt
    yield float(start)

    georate = sqrt(start*end)/start

    for i in range(1, count-1):
        yield start*(georate**(float(i*2)/(count-1)))

    yield float(end)

def randomize(value, constrain):
    '''
    Returns a random [value] within given [constrain]
    '''
    import random, math

    randomAngle = random.uniform(0.0,2*math.pi)
    value += int(math.cos(randomAngle)*constrain)

    return value  

def linInterp(t0, t1, t):
    '''
    Linear Interpolation: Returns value for given normal value (time) t within the range t0-t1.
    '''
    return (max(t0,t1)-min(t0,t1))*t + min(t0,t1)

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

# - Classes -------------------------------------------
# -- Font & Failies -----------------------------------
class fontFamilly():
	'''
	Font familly class:
	*   generates weight stems [.wt_stems] and MM weight instances [.wt_instances]
		using given masters/layers wt0, wt1, and number of weight members [wt_steps].
		Uses geometric growth (progression) algorithm to determine stem weight

	*   generates MM width instances [.wd_instances] using given number
		of width members [wd_steps]. Uses linear growth.

	*   generates all MM isntaces/vectors for instance generation [.instances]
	---
	ex: fontFamilyName = fontFamilly(wt0 = 56, wt1 = 178, wt_steps = 7, wd_steps = 3)
	'''

	def __init__(self, **kwargs):
		# - Input
		self.wt0 = kwargs.get('wt0', 1)
		self.wt1 = kwargs.get('wt1', 2)
		self.wt_steps = kwargs.get('wt_steps', 2)
		self.wd_steps = kwargs.get('wd_steps', 2)

		# - Calculate on init
		self.update()

	def update(self):
		from math import sqrt
		from BasicTools import linspread, geospread, ratfrac

		self.wt_stems =  [int(round(item)) for item in geospread(self.wt0, self.wt1, self.wt_steps)]
		self.wt_instances = [int(ratfrac(item - self.wt0, self.wt1 - self.wt0, 1000)) for item in self.wt_stems]
		self.wd_instances = [int(item) for item in list(linspread(0,1000, self.wd_steps))]

		if len(self.wd_instances) > 2:
			from itertools import product
			self.instances = list(product(self.wt_instances, self.wd_instances))
		else:
			self.instances = self.wt_instances

class linAxis(object):
	'''
	A linear series axis instance and stem calculator

	Usage linAxis(masterDict, instanceCount), where:
	*	masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
	*	instanceCount = number of instances to be calculated
	'''
	def __init__(self, masterDict, instanceCount):
		self.steps = instanceCount
		self.masters = masterDict

		self.update()			

	def update(self):
		from typerig.utils import linspread, geospread, ratfrac

		minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
		minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
		
		self.stems = [int(round(item)) for item in list(linspread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
		self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
		self.instances = sorted(self.data.keys())

class geoAxis(object):
    '''
    A geometric series axis instance and stem calculator

    Usage linAxis(masterDict, instanceCount), where:
    *   masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
    *   instanceCount = number of instances to be calculated
    '''
    def __init__(self, masterDict, instanceCount):
        self.steps = instanceCount
        self.masters = masterDict

        self.update()           

    def update(self):
        from typerig.utils import linspread, geospread, ratfrac

        minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
        minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
        
        self.stems = [int(round(item)) for item in list(geospread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
        self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
        self.instances = sorted(self.data.keys())

# - Procedures ------------------------------
def outputHere():
    ''' Dump stdout, stderr to log files in the current working path. Usable for FL6 nested widgets bug that breaks output. '''
    import sys, os
    dir = os.path.dirname(__file__)
    sys.stdout = open(os.path.join(dir,'stdout.log'), 'w')
    sys.stderr = open(os.path.join(dir,'stderr.log'), 'w')