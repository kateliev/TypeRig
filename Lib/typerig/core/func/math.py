# MODULE: TypeRig / Core / Math (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2015-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math, random

# - Init --------------------------------
__version__ = '0.26.4'

epsilon = 0.000001

# - Functions ---------------------------
# -- Math -------------------------------
def normalize2max(values):
	'''Normalize all values to the maximum value in a given list. 
	
	Arguments:
		values (list(int of float));
	Returns: 
		list(float)
	'''
	return sorted([float(item)/max(values) for item in values])

def normalize2sum(values):
	'''Normalize all values to the sum of given list so the resuting sum is always 1.0 or close as possible. 
	
	Arguments: 
		values (list(int of float));
	Returns: 
		list(float)
	'''
	valSum = sum(values)
	return sorted([float(item)/valSum for item in values])

def renormalize(values, newRange, oldRange=None):
	'''Normalize all values to the maximum value in a given list and remap them in a new given range. 
	
	Arguments: 
		values (list(int of float)) : a list of values to be normalized
		newRange (tuple(float,float)): a new range for remapping (20,250)
		oldRange (tuple(float,float)) or None: the original range of values if None range is auto extracted from values given.
	Returns:
		list(float)
	'''
	if oldRange is not None:
		return sorted([(max(newRange) - min(newRange))*item + min(newRange) for item in [float(item - min(oldRange))/(max(oldRange) - min(oldRange)) for item in values]])
	else:
		return sorted([(max(newRange) - min(newRange))*item + min(newRange) for item in [float(item - min(values))/(max(values) - min(values)) for item in values]])

def isclose(a, b, abs_tol = 1, rel_tol = 0.0):
	'''Tests approximate equality for values [a] and [b] within relative [rel_tol*] and/or absolute tolerance [abs_tol]

	*[rel_tol] is the amount of error allowed,relative to the larger absolute value of a or b. For example,
	to set a tolerance of 5%, pass tol=0.05. The default tolerance is 1e-9, which assures that the
	two values are the same within about9 decimal digits. rel_tol must be greater than 0.0
	'''
	if abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol):	return True
	return False

def isBetween(x, a, b):
	'''A broader test if a value is between two others'''
	return True if a <= x <= b or isclose(x, a, abs_tol=epsilon) or isclose(x, b, abs_tol=epsilon) else False

def roundFloat(f, error=1000000.):
	return round(f*error)/error

def round2base(x, base = 5):
	'''Rounds a value using given base increments'''
	return int(base * round(float(x)/base))

# -- Progressions & Fractions ----------------------------
def ratfrac(part, whole, fraction = 100):
	'''Calculates the ratio of part to whole expressed as fraction (percentage: 100 (default); mileage: 1000) '''
	return fraction*(float(part)/float(whole))

def linspread(start, end, count):
	'''Linear space generator object: will generate equally spaced numbers within given range'''
	yield float(start)

	for i in range(1, count-1):
		yield float(start + i*(end-start)/float((count-1))) #Adapted from NumPy.linespace

	yield float(end)

def geospread(start, end, count):
	'''Geometric space generator object: will generate elements of geometric progression within given range'''
	yield float(start)

	georate = math.sqrt(start*end)/start

	for i in range(1, count-1):
		yield start*(georate**(float(i*2)/(count-1)))

	yield float(end)

def randomize(value, constrain):
	'''Returns a random value within given constrain'''
	randomAngle = random.uniform(0.0,2*math.pi)
	value += int(math.cos(randomAngle)*constrain)

	return value  

# -- Interpolation --------------------------------------------------
def linInterp(t0, t1, t):
	'''Linear Interpolation: Returns value for given normal value (time) t within the range t0-t1.'''
	#return (max(t0,t1)-min(t0,t1))*t + min(t0,t1)
	return (t1 - t0)*t + t0

def bilinInterp(x, y, points):
	'''Bilinear Interpolate (x,y) from values associated with four points.

	The four points are a list of four triplets:  (x, y, value).
	The four points can be in any order.  They should form a rectangle.

		>>> bilinear_interpolation(12, 5.5,
		...                        [(10, 4, 100),
		...                         (20, 4, 200),
		...                         (10, 6, 150),
		...                         (20, 6, 300)])
		165.0

	'''
	# See formula at:  http://en.wikipedia.org/wiki/Bilinear_interpolation
	# Copy from https://stackoverflow.com/questions/8661537/how-to-perform-bilinear-interpolation-in-python
	# Note: ReAdapt!

	points = sorted(points)               # order points by x, then by y
	(x1, y1, q11), (_x1, y2, q12), (x2, _y1, q21), (_x2, _y2, q22) = points

	if x1 != _x1 or x2 != _x2 or y1 != _y1 or y2 != _y2:
		raise ValueError('points do not form a rectangle')
	if not x1 <= x <= x2 or not y1 <= y <= y2:
		raise ValueError('(x, y) not within the rectangle')

	return (q11 * (x2 - x) * (y2 - y) +
			q21 * (x - x1) * (y2 - y) +
			q12 * (x2 - x) * (y - y1) +
			q22 * (x - x1) * (y - y1)
		   ) / ((x2 - x1) * (y2 - y1) + 0.0)
	

if __name__ == '__main__':
	r = range(105,415,10)
	a = 0.5
	b = 0.7
	x = 8.0000008
	points = [(10, 4, 100), (20, 4, 200), (10, 6, 150), (20, 6, 300)]

	print(normalize2max(r))
	print(normalize2sum(r))
	print(renormalize(r, (20,500), oldRange=None))
	print(isclose(a, b, abs_tol = 0.1, rel_tol = 0.0))
	print(isBetween(0.67, a, b))
	print(roundFloat(x, error=1000000.))
	print(round2base(x, base = 5))
	print(ratfrac(a, b, fraction = 100))
	print(list(linspread(100, 700, 11)))
	print(list(geospread(100, 700, 11)))
	print(randomize(a, 2))
	print(linInterp(10, 20, .5))
	print(bilinInterp(12, 5.5, points))

