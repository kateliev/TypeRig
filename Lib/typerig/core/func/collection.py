# MODULE: TypeRig / Core / Collection (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
from itertools import islice

# - Init --------------------------------
__version__ = '0.26.7'

# - Functions ---------------------------
# -- Dictionary -------------------------
def mergeDicts(d1, d2, merge = lambda x, y : y):
	'''	Merges two dictionaries [d1, d2], combining values on duplicate keys as defined by the optional [merge] function.
	--------
	Example: merge(d1, d2, lambda x,y: x+y) -> {'a': 2, 'c': 6, 'b': 4}	'''
	mergeDict = dict(d1)
	for key, value in d2.items():
		
		if key in mergeDict:
			mergeDict[key] = merge(mergeDict[key], value)
		else:
			mergeDict[key] = value

	return mergeDict
# -- Lists ------------------------------
def flatten(listItems):
	'''	Unpacks all items form [listItems] containing other lists, sets and etc. '''
	from itertools import chain
	return list(chain(*listItems))

def group_recurring(listItems):
	'''	Combines recurring items in [listItems] and returns a list containing sets of grouped items	'''
	temp = [set(item) for item in listItems if item]

	for indexA, valueA in enumerate(temp) :
		for indexB, valueB in enumerate(temp[indexA + 1 :], indexA + 1): 
			if valueA & valueB:
				temp[indexA] = valueA.union(temp.pop(indexB))
				return group_recurring(temp)

	return [tuple(item) for item in temp]

def group_consecutive(listItems, step = 1):
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

def group_conditional(iterable, condition):
	'''Takes a sorted iterable and groups items according to condition and operator given
	Args: 
		iterable	list() or tuple(): Any iterable object
		condition 	lambda x: A function to check condition
	Returns:
		generator object

	Example:
		l = [123, 124, 128, 160, 167, 213, 215, 230, 245, 255, 257, 400, 401, 402, 430]
		g = grouper(l, lambda x: x <= 15)
		dict(enumerate(g))
		>>> {1: [123, 124, 128], 2: [160, 167], 3: [213, 215, 230, 245, 255, 257],....}
	'''
	prev = None
	group = []
	for item in iterable:
		if prev is None or condition(abs(item - prev)):
			group.append(item)
		else:
			yield group
			group = [item]
		prev = item
	if group:
		yield group

def sliding_window(sequence, window_size=2):
	'''Returns a sliding window (of window_size) over data from the iterable.
	Example: s -> (s0, s1, ... s[n-1]), (s1, s2, ... , sn), ... '''
	
	iterator = iter(sequence)
	result = tuple(islice(iterator, window_size))
	
	if len(result) == window_size:
		yield result
	
	for element in iterator:
		result = result[1:] + (element,)
		yield result


if __name__ == '__main__':
	d1 = {i:i+3 for i in range(10)}
	d2 = {i:i*3 for i in range(10)}
	print(mergeDicts(d1, d2, merge = lambda x, y : '%s+%s'%(x,y)))

	a = ((3, 4), (4, 5), (67, 12), (899, 234, 2345, 2, 3), (4, 5, 7))
	b = [123, 124, 128, 160, 167, 213, 215, 230, 245, 255, 257, 400, 401, 402, 430]
	print(flatten(a))
	print(group_recurring(a))
	print(group_consecutive(flatten(a), step = 1))
	print(list(sliding_window(flatten(a), window_size=2)))
	print(list(group_conditional(b, lambda x: x <= 15)))