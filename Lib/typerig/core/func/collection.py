# MODULE: TypeRig / Core / Collection (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import

# - Init --------------------------------
__version__ = '0.26.1'

# - Functions ---------------------------
# -- Dictionary -------------------------
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
# -- Lists ------------------------------
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