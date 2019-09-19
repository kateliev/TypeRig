# MODULE: Brain | Typerig
# ----------------------------------------
# (C) Vassil Kateliev, 2018  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# NOTE:
# Re-adaptation of the original FontBrain for FL5 from FDK5 by Vassil Kateliev, 2015
# Parts of this library were inspired or adapted from various authors (in no particular order) including:
# Eduardo Tunni (Tunni equalizer), Jens Kutilek (proportional curve equalizer), Simon Egli (Hobby Splines)

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.25.8'

# - Dependancies -----------------
import math

# - Functions -------------------------------------------------
# -- Math -----------------------------------------------------
def calcsb(counterWidth, step=5):
	return [(val, float(counterWidth*val)/100) for val in range(25, 50, step)]

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
	if abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol):
		return True

def round2base(x, base = 5):
	'''Rounds a value using given base increments'''
	return int(base * round(float(x)/base))

def getAngle(x,y, inDeg=True):
	'''Return angle for given X,Y displacement from origin'''
	from math import degrees, atan2
	
	if inDeg:
		return degrees(atan2(float(x), float(y)))
	else:
		return atan2(float(x), float(y))

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
	from math import sqrt
	yield float(start)

	georate = sqrt(start*end)/start

	for i in range(1, count-1):
		yield start*(georate**(float(i*2)/(count-1)))

	yield float(end)

def randomize(value, constrain):
	'''Returns a random value within given constrain'''
	import random, math

	randomAngle = random.uniform(0.0,2*math.pi)
	value += int(math.cos(randomAngle)*constrain)

	return value  

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
# -- Contour tests ----------------------------------------------------------
def ccw(A, B, C):
	'''Tests whether the turn formed by A, B, and C is Counter clock wise (CCW)'''
	return (B.x - A.x) * (C.y - A.y) > (B.y - A.y) * (C.x - A.x)

def intersect(A,B,C,D):
	'''Tests whether A,B and C,D intersect'''
	return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

# - Classes --------------------------------------------------------------------
class bounds(object):
	def __init__(self, tupleList):
		self.x, self.xmax = 0, 0
		self.y, self.ymax = 0, 0
		self.width, self.height = 0, 0
		self.refresh(tupleList)

	def recalc(self, tupleList):
		from operator import itemgetter
		min_x_tup = min(tupleList,key=itemgetter(0))
		min_y_tup = min(tupleList,key=itemgetter(1))
		max_x_tup = max(tupleList,key=itemgetter(0))
		max_y_tup = max(tupleList,key=itemgetter(1))
		return (min_x_tup, min_y_tup, max_x_tup, max_y_tup)

	def refresh(self, tupleList):
		min_x_tup, min_y_tup, max_x_tup, max_y_tup = self.recalc(tupleList)
		self.x = min_x_tup[0]
		self.y = min_y_tup[1]
		self.xmax = max_x_tup[0]
		self.ymax = max_y_tup[1]
		self.width = abs(self.xmax - self.x)
		self.height = abs(self.ymax - self.y)
		
class biDict(dict):
	'''
	Bi-directioanl dictionary partly based on Basj answer st:
	https://stackoverflow.com/questions/3318625/efficient-bidirectional-hash-table-in-python
	'''
	def __init__(self, *args, **kwargs):
		super(biDict, self).__init__(*args, **kwargs)

		self.inverse = {}

		for key, value in self.iteritems():
			self.inverse.setdefault(value,[]).append(key) 

	def __setitem__(self, key, value):
		if key in self:
			self.inverse[self[key]].remove(key) 

		super(biDict, self).__setitem__(key, value)
		self.inverse.setdefault(value,[]).append(key)        

	def __delitem__(self, key):
		self.inverse.setdefault(self[key],[]).remove(key)

		if self[key] in self.inverse and not self.inverse[self[key]]: 
			del self.inverse[self[key]]

		super(biDict, self).__delitem__(key)

class extBiDict(dict):
	'''
	Bi-directioanl dictionary with lists for values
	'''
	def __init__(self, *args, **kwargs):
		super(extBiDict, self).__init__(*args, **kwargs)

		self.inverse = {}

		for key, value in self.iteritems():
			assert isinstance(value, list), 'Value for key %s is not of type list()' %key

			for item in value:
				self.inverse.setdefault(item,[]).append(key) 

	def __setitem__(self, key, value):
		if key in self:
			self.inverse[self[key]].remove(key) 

		super(extBiDict, self).__setitem__(key, value)
		self.inverse.setdefault(value,[]).append(key)        

	def __delitem__(self, key):
		self.inverse.setdefault(self[key],[]).remove(key)

		if self[key] in self.inverse and not self.inverse[self[key]]: 
			del self.inverse[self[key]]

		super(extBiDict, self).__delitem__(key)
		
# -- General font classes ------------------------------------------------------
class fontFamilly():
	'''Font familly class:
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
		from typerig.brain import linspread, geospread, ratfrac

		self.wt_stems =  [int(round(item)) for item in geospread(self.wt0, self.wt1, self.wt_steps)]
		self.wt_instances = [int(ratfrac(item - self.wt0, self.wt1 - self.wt0, 1000)) for item in self.wt_stems]
		self.wd_instances = []
		
		if self.wd_steps >= 2:
			from itertools import product

			self.wd_instances = [int(item) for item in list(linspread(0,1000, self.wd_steps))]
			self.instances = list(product(self.wt_instances, self.wd_instances))
		else:
			self.instances = self.wt_instances

class linAxis(object):
	'''A linear series axis instance and stem calculator

	Usage linAxis(masterDict, instanceCount), where:
	*	masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
	*	instanceCount = number of instances to be calculated
	'''
	def __init__(self, masterDict, instanceCount):
		self.steps = instanceCount
		self.masters = masterDict

		self.update()			

	def update(self):
		from typerig.brain import linspread, geospread, ratfrac

		minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
		minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
		
		self.stems = [int(round(item)) for item in list(linspread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
		self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
		self.instances = sorted(self.data.keys())

class geoAxis(object):
	'''A geometric series axis instance and stem calculator

	Usage linAxis(masterDict, instanceCount), where:
	*   masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
	*   instanceCount = number of instances to be calculated
	'''
	def __init__(self, masterDict, instanceCount):
		self.steps = instanceCount
		self.masters = masterDict

		self.update()           

	def update(self):
		from typerig.brain import linspread, geospread, ratfrac

		minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
		minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
		
		self.stems = [int(round(item)) for item in list(geospread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
		self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
		self.instances = sorted(self.data.keys())

# -- Custom Data types -------------------------------------------------------------------
class coordArray(object):
	def __init__(self, *argv):
		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])

		if not len(argv):		
			self.x, self.y = [[],[]]

		elif len(argv) == 2 and multiCheck(argv, list):
			self.x, self.y = argv

		elif len(argv) == 1 and len(argv[0]) % 2 == 0: # and isinstance(argv[0], list):
			split = len(argv[0])/2
			self.x = argv[0][0:split]
			self.y = argv[0][split:]

		self.type = []

	def __getitem__(self, i):
		return (self.x[i], self.y[i])

	def __getslice__(i, j):
		return self.__class__(self.x[i:j], self.y[i:j])

	def __len__(self):
		return len(self.x)

	def __setitem__(self, i, coordTuple):
		self.x[i], self.y[i] = coordTuple

	def __str__(self):
		return str(zip(self.x, self.y))

	def __repr__(self):
		return '<Coordinate Array: Lenght=%s;>' %len(self.x)

	def append(self, coordTuple, nodeType=-1):
		x, y = coordTuple
		self.x.append(x)
		self.y.append(y)
		self.type.append(nodeType)

	def extend(self, coordList):
		if isinstance(coordList, self.__class__):
			self.x.extend(coordList.x)
			self.y.extend(coordList.y)

		elif isinstance(coordList, list):
			self.x.extend(coordList[0])
			self.y.extend(coordList[1])

	def insert(self, index, coordTuple):
		x, y = coordTuple
		self.x.insert(index, x)
		self.y.insert(index, y)

	def remove(self, coordTuple):
		x, y = coordTuple
		self.x.remove(x)
		self.y.remove(y)

	def pop(self, index=None):
		return (self.x.pop(index), self.y.pop(index))

	def reverse(self):
		self.x.reverse()
		self.y.reverse()

	def asPairs(self):
		return [zip(self.x, self.y)]

	def asList(self):
		return [self.x, self.y]

	def flatten(self):
		return self.x + self.y

	def bounds(self):
		return (min(self.x), min(self.y), max(self.x), max(self.y))

	def items(self):
		return zip(self.x, self.y, self.type)


# -- Geometry classes --------------------------------------------------------------------
# --- Transformations --------------------------------------------------------------------
class transform(object):
	'''	Affine transformations '''

	def __init__(self, xx=1.0, xy=0.0, yx=0.0, yy=1.0, dx=0.0, dy=0.0):
		self.__affine = map(float, (xx, xy, yx, yy, dx, dy))

	def __normSinCos(self, v):
		EPSILON = 1e-15
		ONE_EPSILON = 1.0 - EPSILON
		MINUS_ONE_EPSILON = -1.0 + EPSILON

		if abs(v) < EPSILON:
			v = 0.0
		elif v > ONE_EPSILON:
			v = 1.0
		elif v < MINUS_ONE_EPSILON:
			v = -1.0
		return v

	def applyTransformation(self, x, y):
		x, y = float(x), float(y)
		xx, xy, yx, yy, dx, dy = map(float, self.__affine)
		return (xx * x + yx * y + dx, xy * x + yy * y + dy)

	def translate(self, dx, dy):
		return self.transform((1.0, 0.0, 0.0, 1.0, float(dx), float(dy)))

	def scale(self, sx, sy):
		return self.transform((float(sx), 0.0, 0.0, float(sy), 0.0, 0.0))

	def rotate(self, angle):
		from math import sin, cos, radians
		c = self.__normSinCos(cos(radians(angle)))
		s = self.__normSinCos(sin(radians(angle)))
		return self.transform((c, s, -s, c, 0.0, 0.0))

	def skew(self, ax, ay):
		from math import tan, radians
		return self.transform((1.0, tan(radians(ay)), tan(radians(ax)), 1.0, 0.0, 0.0))

	def transform(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float, other)
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float, self.__affine)
		return self.__class__(
				xx1 * xx2 + xy1 * yx2,
				xx1 * xy2 + xy1 * yy2,
				yx1 * xx2 + yy1 * yx2,
				yx1 * xy2 + yy1 * yy2,
				xx2 * dx1 + yx2 * dy1 + dx2,
				xy2 * dx1 + yy2 * dy1 + dy2)

	def reverseTransform(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float, self.__affine)
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float, other)
		return self.__class__(
				xx1 * xx2 + xy1 * yx2,
				xx1 * xy2 + xy1 * yy2,
				yx1 * xx2 + yy1 * yx2,
				yx1 * xy2 + yy1 * yy2,
				xx2 * dx1 + yx2 * dy1 + dx2,
				xy2 * dx1 + yy2 * dy1 + dy2)

	def inverse(self):
		if self.__affine == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
			return self

		xx, xy, yx, yy, dx, dy = self.__affine
		det = float(xx*yy - yx*xy)

		xx, xy, yx, yy = yy / det, -xy / det, -yx / det, xx / det
		dx, dy = -xx * dx - yx * dy, - xy * dx - yy * dy

		return self.__class__(xx, xy, yx, yy, dx, dy)

	def __len__(self):
		return 6

	def __getitem__(self, index):
		return self.__affine[index]

	def __getslice__(self, i, j):
		return self.__affine[i:j]

	def __cmp__(self, other):
		xx1, xy1, yx1, yy1, dx1, dy1 = map(float(self.__affine))
		xx2, xy2, yx2, yy2, dx2, dy2 = map(float(other))
		return cmp((xx1, xy1, yx1, yy1, dx1, dy1), (xx2, xy2, yx2, yy2, dx2, dy2))

	def __hash__(self):
		return hash(self.__affine)

	def __repr__(self):
		return '<%s [%s %s %s %s %s %s]>' %((self.__class__.__name__,) + tuple(map(str, self.__affine)))

# --- Abstractions -----------------------------------------------------------------------
class _Point(object): 
	def __init__(self, *argv):
		from typerig.brain import transform

		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])

		if len(argv):
			if isinstance(argv[0], self.__class__):
				self.x, self.y = argv[0].x, argv[0].y

			if multiCheck(argv, float) or multiCheck(argv, int) :
				self.x, self.y = argv[0], argv[1]
			
			if multiCheck(argv, tuple) or multiCheck(argv, list) :
				self.x, self.y = argv[0]
		else:
			self.x, self.y = 0., 0.

		self.setAngle(0)
		self.setTransform()

	# -- Operators
	def __add__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(self.x + other.x, self.y + other.y)
		
		elif isinstance(other, int):
			return self.__class__(self.x + other, self.y + other)

		elif isinstance(other, float):
			return self.__class__(self.x + other, self.y + other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x + other[0], self.y + other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print 'ERRO\t Cannot evaluate Coordinate Object <<%s,%s>> with %s' %(self.x, self.y, type(other))

	def __sub__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(self.x - other.x, self.y - other.y)
		
		elif isinstance(other, int):
			return self.__class__(self.x - other, self.y - other)

		elif isinstance(other, float):
			return self.__class__(self.x - other, self.y - other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x - other[0], self.y - other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print 'ERRO\t Cannot evaluate Coordinate Object <<%s,%s>> with %s' %(self.x, self.y, type(other))

	def __mul__(self, other):
		if isinstance(other, self.__class__):
			a = complex(self.x , self.y)
			b = complex(other.x, other.y)
			product = a * b
			return self.__class__(product.real, product.imag)
		
		elif isinstance(other, int):
			return self.__class__(self.x * other, self.y * other)

		elif isinstance(other, float):
			return self.__class__(self.x * other, self.y * other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x * other[0], self.y * other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print 'ERRO\t Cannot evaluate Coordinate Object <<%s,%s>> with %s' %(self.x, self.y, type(other))

	__rmul__ = __mul__

	def __div__(self, other):
		if isinstance(other, self.__class__):
			a = complex(self.x , self.y)
			b = complex(other.x, other.y)
			product = a / b
			return self.__class__(product.real, product.imag)
		
		elif isinstance(other, int):
			return self.__class__(self.x / other, self.y / other)

		elif isinstance(other, float):
			return self.__class__(self.x // other, self.y // other)
		
		elif isinstance(other, tuple):
			return self.__class__(self.x // other[0], self.y // other[1])
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

		else:
			print 'ERRO\t Cannot evaluate Coordinate Object <<%s,%s>> with %s' %(self.x, self.y, type(other))

	__rdiv__ = __div__

	# - Scalar product and cross product --------------------
	# -- Usable in determing angle between unit vectors 
	# -- example: atan2(nextUnit|prevUnit, nextUnit & prevUnit)

	def __and__(self, other):
		'''self & other: Used as for Scalar product'''
		if isinstance(other, self.__class__):
			return self.x * other.x + self.y * other.y
		
		elif isinstance(other, int):
			return self.x * other + self.y * other

		elif isinstance(other, float):
			return self.x * other + self.y * other
		
		elif isinstance(other, tuple):
			return self.x * other[0] + self.y * other[1]
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

	def __or__(self, other):
		'''self | other: Used as for Cross product'''
		if isinstance(other, self.__class__):
			return self.x * other.y - self.y * other.x
		
		elif isinstance(other, int):
			return self.x * other - self.y * other

		elif isinstance(other, float):
			return self.x * other - self.y * other
		
		elif isinstance(other, tuple):
			return self.x * other[1] - self.y * other[0]
		
		elif isinstance(other, list):
			pass

		elif isinstance(other, str):
			pass

	def __abs__(self):
		from math import sqrt
		return sqrt(self.x**2 + self.y**2)

	def __repr__(self):
		return '<Point: %s,%s>' %(self.x, self.y)

	# -- Setters 
	def setAngle(self, angle):
		self.angle = angle

	def setTransform(self, transformObject=None):
		from typerig.brain import transform
		
		self.transform = transform() if transformObject is None else transformObject
	
	# -- Getters
	def getMagnitude(self):
		from math import hypot
		self.magnitude = hypot(self.x, self.y)
		return self.magnitude 

	def getUnit(self):
		self.getMagnitude()
		return self*(1.0/self.magnitude) if self.magnitude != 0 else self.__class__(0,0)

	def getSlope(self):
		from math import tan, radians
		return float(tan(radians(90 - self.angle))) #float(self.y)/math.sin(math.radians(self.angle))

	def getYintercept(self):
		return float(self.y - self.getSlope() * self.x)

	def getWidth(self, y=0):
		'''Get width - find adjacent X by opposite Y'''
		return self.x + float(self.y - y)/self.getSlope()

	def solveY(self, x):
		return self.getSlope() * x + self.getYintercept()

	def solveX(self, y):
		return (float(y) - self.getYintercept()) / self.getSlope()

	# -- Modifiers
	def doSwap(self):
		return self.__class__(self.y, self.x)

	def doFlip(self, sign=(True,True)):
		return self.__class__(self.x * [1,-1][sign[0]], self.y * [1,-1][sign[1]])

	def doTransform(self, transform=None):
		if transform is None:
			transform = self.transform

		self.x, self.y = transform.applyTransformation(self.x, self.y)

	# -- Represent
	def asTuple(self, toInt=False):
		return (self.x, self.y) if not toInt else (int(self.x), int(self.y))

class _Line(object):
	def __init__(self, *argv):
		self.p0, self.p1 = argv
		self.update()
		
	def __add__(self, other):
		return self.__class__(self.p0 + other, self.p1 + other)

	def __sub__(self, other):
		return self.__class__(self.p0 - other, self.p1 - other)

	def __mul__(self, other):
		return self.__class__(self.p0 * other, self.p1 * other)

	__rmul__ = __mul__

	def __div__(self, other):
		return self.__class__(self.p0 / other, self.p1 / other)	

	def __and__(self, other):
		return self.lineIntercept(other)

	def __repr__(self):
		return '<Line: (%s,%s),(%s,%s)>' %(self.p0.x, self.p0.y, self.p1.x, self.p1.y)

	def getLenght(self):
		from math import hypot
		return hypot(self.p0.x - self.p1.x, self.p0.y - self.p1.y)

	def getSlope(self):
		try:
			return self.yDiff / float(self.xDiff)

		except ZeroDivisionError:
			return float('nan')

	def getAngle(self):
		from math import degrees, atan2
		return degrees(atan2(self.yDiff, self.xDiff))

	def setAngle(self, angle):
		'''Force Set Angle and change slope'''
		from math import tan, radians
		self.angle = angle
		self.slope = float(tan(radians(90 - self.angle)))

	def getYintercept(self):
		'''Get the Y intercept of a line segment'''
		return self.p0.y - self.slope * self.p0.x if not math.isnan(self.slope) and self.slope != 0 else self.p0.y

	def solveY(self, x):
		'''Solve line equation for Y coordinate.'''
		from math import isnan
		return self.slope * x + self.getYintercept() if not isnan(self.slope) and self.slope != 0 else self.p0.y
					
	def solveX(self, y):
		'''Solve line equation for X coordinate.'''
		from math import isnan
		return (float(y) - self.getYintercept()) / float(self.slope) if not isnan(self.slope) and self.slope != 0 else self.p0.x
		
	def lineIntercept(self, other_line):
		'''Find interception point (X, Y) for two lines.
		Returns (None, None) if lines do not intercept.'''
		xdiff = _Point(self.p0.x - self.p1.x, other_line.p0.x - other_line.p1.x)
		ydiff = _Point(self.p0.y - self.p1.y, other_line.p0.y - other_line.p1.y)

		div = xdiff | ydiff
		if div == 0: return (None, None)

		d = _Point(self.p0 | self.p1, other_line.p0 | other_line.p1)
		x = (d | xdiff) / div
		y = (d | ydiff) / div
		return (x, y)

	def shift(self, dx, dy):
		'''Shift coordinates by dx,dy'''
		self.p0.x += dx
		self.p1.x += dx
		self.p0.y += dy
		self.p1.y += dy

		self.update()

	def update(self):
		self.xDiff = self.p1.x - self.p0.x
		self.yDiff = self.p1.y - self.p0.y
		self.angle = self.getAngle()
		self.slope = self.getSlope()

class _Curve(object):
	def __init__(self, data):
		self.p0, self.p1, self.p2, self.p3 = data
				
	def __repr__(self):
		return '<Curve: %s,%s,%s,%s>' %(self.p0.asTuple(), self.p1.asTuple(), self.p2.asTuple(), self.p3.asTuple())

	def asList(self):
		return [self.p0, self.p1, self.p2, self.p3]

	def doSwap(self):
		return self.__class__(self.p3, self.p2, self.p1, self.p0)
		
	def getNode(self, time):
		'''Returns Base Node integer/float (x,y) coordinates at given [time]
		Output: tuple (x,y)
		'''

		from typerig.brain import Coord

		rtime = 1 - time
		x = (rtime**3)*self.p0.x + 3*(rtime**2)*time*self.p1.x + 3*rtime*(time**2)*self.p2.x + (time**3)*self.p3.x
		y = (rtime**3)*self.p0.y + 3*(rtime**2)*time*self.p1.y + 3*rtime*(time**2)*self.p2.y + (time**3)*self.p3.y

		return Coord(x, y)

	def sliceNode(self, time, resultInt = True):
		'''Returns integer/float coordinates of curve sliced at given [time]. 
		Output: list [(Start), (Start_BCP_out), (Slice_BCP_in), (Slice), (Slice_BCP_out), (End_BCP_in), (End)] of tuples (x,y)
		'''

		x1, y1 = self.p0.x, self.p0.y
		x2, y2 = self.p1.x, self.p1.y
		x3, y3 = self.p2.x, self.p2.y
		x4, y4 = self.p3.x, self.p3.y

		x12 = (x2 - x1)*time + x1
		y12 = (y2 - y1)*time + y1

		x23 = (x3 - x2)*time + x2
		y23 = (y3 - y2)*time + y2

		x34 = (x4 - x3)*time + x3
		y34 = (y4 - y3)*time + y3

		x123 = (x23 - x12)*time + x12
		y123 = (y23 - y12)*time + y12

		x234 = (x34 - x23)*time + x23
		y234 = (y34 - y23)*time + y23

		x1234 = (x234 - x123)*time + x123
		y1234 = (y234 - y123)*time + y123

		
		slices = [(x1,y1), (x12,y12), (x123,y123), (x1234,y1234), (x234,y234), (x34,y34), (x4,y4)] 
		
		if resultInt:
			return map(lambda x, y : (int(x), int(y)), slices)
		else:
			return slices

	def solveDistance2Start(self, distance, timeStep = .01 ):
		'''Returns [time] at which the given [distance] to [FIRST curve node] is met. 
		Probing is executred withing [timeStep] in range from 0 to 1. The finer the step the preciser the results.
		'''

		from math import hypot
		
		measure = 0
		time = 0

		while measure < distance and time < 1:
			cNode = self.getNode(time, False)
			measure = hypot(-self.p0.x + cNode[0], -self.p0.y + cNode[1])
			#print 'S', measure, time			
			time += timeStep

		return time

	def solveDistance2End(self, distance, timeStep = .01 ):
		'''Returns [time] at which the given [distance] to [LAST curve node] is met. 
		Probing is executred withing [timeStep] in range from 0 to 1. The finer the step the preciser the results.
		'''

		from math import hypot
		
		measure = 0
		time = 1

		while measure < distance and time > 0:
			cNode = self.getNode(time, False)
			measure = hypot(-self.p3.x + cNode[0], -self.p3.y + cNode[1])
			#print 'E', measure, time
			time -= timeStep

		return time

	def getExtremes(self): # (x0, y0, x1, y1, x2, y2, x3, y3)
		'''Finds curve extremes and returns [(extreme_01_x, extreme_01_y, extreme_01_t)...(extreme_n_x, extreme_n_y, extreme_n_t)]'''

		tvalues, points = [], []
		x0, y0 = self.p0.x, self.p0.y
		x1, y1 = self.p1.x, self.p1.y
		x2, y2 = self.p2.x, self.p2.y
		x3, y3 = self.p3.x, self.p3.y

		for i in range(0,2):
			if i == 0:
				b = float(6 * x0 - 12 * x1 + 6 * x2)
				a = float(-3 * x0 + 9 * x1 - 9 * x2 + 3 * x3)
				c = float(3 * x1 - 3 * x0)

			else:
				b = float(6 * y0 - 12 * y1 + 6 * y2)
				a = float(-3 * y0 + 9 * y1 - 9 * y2 + 3 * y3)
				c = float(3 * y1 - 3 * y0)

			if abs(a) < 1e-12:        # Numerical robustness
				if abs(b) < 1e-12:    # Numerical robustness
					continue

				t = -c / b

				if 0 < t and t < 1:
					tvalues.append(t)

				continue

			b2ac = float(b * b - 4 * c * a)

			if b2ac < 0:
				continue
			else:
				sqrtb2ac = math.sqrt(b2ac)

			t1 = (-b + sqrtb2ac) / (2 * a)
			if 0 < t1 and t1 < 1:
				tvalues.append(t1)

			t2 = (-b - sqrtb2ac) / (2 * a)
			if 0 < t2 and t2 < 1:
				tvalues.append(t2)

		for j in range(0,len(tvalues)):
			t = tvalues[j]
			mt = 1 - t
			x = (mt * mt * mt * x0) + (3 * mt * mt * t * x1) + (3 * mt * t * t * x2) + (t * t * t * x3)
			y = (mt * mt * mt * y0) + (3 * mt * mt * t * y1) + (3 * mt * t * t * y2) + (t * t * t * y3)

			points.append((int(x), int(y), t))

		return points


	def solveParallelT(self, vector, fullOutput = False):
		'''Finds the t value along a cubic Bezier where a tangent (1st derivative) is parallel with the direction vector.
		vector: a pair of values representing the direction of interest (magnitude is ignored).
		returns 0.0 <= t <= 1.0 or None
		
		# Solving the dot product of cubic beziers first derivate to the vector given B'(t) x V. Two vectors are perpendicular if their dot product is zero. 
		# So if you could find the (1) perpendicular of V it will be collinear == tangent of the curve so the equation to be solved is:
		# B'(t) x V(x,y) = 0; -(a*t^2 + b*t + c)*x + (g*t^2 + h*t + i)*y = 0 solved for t, where a,b,c are coefs for X and g,h,i for Y B'(t) derivate of curve
		# 
		# Inspired by answer given by 'unutbu' on the stackoverflow question: http://stackoverflow.com/questions/20825173/how-to-find-a-point-if-any-on-quadratic-bezier-with-a-given-tangent-direction
		# Recoded and recalculated for qubic beziers. Used 'Rearrange It' app at http://www.wolframalpha.com/widgets/view.jsp?id=4be4308d0f9d17d1da68eea39de9b2ce was invaluable.
		#
		# DOTO: Fix calculation optimization error - will yield false positive result in cases #1 and #2 if vector is 45 degrees
		'''
		from math import sqrt

		def polyCoef(p): # Helper function
			a = float(-3 * p[0] + 9 * p[1] - 9 * p[2] + 3 * p[3])
			b = float(6 * p[0] - 12 * p[1] + 6 * p[2])
			c = float(3 * p[1] - 3 * p[0])
			return a, b, c

		# - Get Coefs
		x , y = vector[0], vector[1]
		a, b, c = polyCoef([self.p0.x, self.p1.x, self.p2.x, self.p3.x])
		g, h, i = polyCoef([self.p0.y, self.p1.y, self.p2.y, self.p3.y])

		# -- Support eq
		bx_hy = float(b*x - h*y)
		cx_iy = float(c*x - i*y)
		ax_gy = float(a*x - g*i)

		if x == 0 and y != 0 and g == 0 and h != 0 : #1 Optimisation
			t = -i/h
			return t

		elif x != 0 and a == (g*y)/x and bx_hy != 0: #2 Optimisation
			t = -cx_iy/bx_hy
			return t

		elif ax_gy != 0: #3 Regular result
			longPoly = float(bx_hy*bx_hy - 4*cx_iy*ax_gy)
			
			if longPoly > 0:
				sqrtLongPoly = sqrt(longPoly)
				
				numrPos = sqrtLongPoly - bx_hy
				numrNeg = -sqrtLongPoly - bx_hy
				
				dnom = 2*ax_gy

				ts = [numrPos/dnom, numrNeg/dnom] # solved t's for numrPos and numrNeg
				tc = [t for t in ts if 0 <= t <= 1] # get correct t
				
				if fullOutput:
					return ts
				else:
					if len(tc) and len(tc) < 2:
						return tc[0]
					else:
						return None # Undefined point of intersection - two t's		
				
			else:
				return None

	def eqProportionalHandles(self, proportion=.3):
		'''Equalizes handle length to given float(proportion)'''
		from math import hypot, atan2, cos, sin

		def getNewCoordinates(targetPoint, referencePoint, alternateReferencePoint, distance):
			if targetPoint.y == referencePoint.y and targetPoint.x == referencePoint.x:
				phi = atan2(alternateReferencePoint.y - referencePoint.y, alternateReferencePoint.x - referencePoint.x)
			else:
				phi = atan2(targetPoint.y - referencePoint.y, targetPoint.x - referencePoint.x)
			
			x = referencePoint.x + cos(phi) * distance
			y = referencePoint.y + sin(phi) * distance

			return (x, y)
		
		# - Get distances
		a = hypot(self.p0.x - self.p1.x, self.p0.y - self.p1.y) 
		b = hypot(self.p1.x - self.p2.x, self.p1.y - self.p2.y)
		c = hypot(self.p2.x - self.p3.x, self.p2.y - self.p3.y)

		#- Calculate equal distance
		eqDistance = (a + b + c) * proportion

		new_p1 = getNewCoordinates(self.p1, self.p0, self.p2, eqDistance)
		new_p2 = getNewCoordinates(self.p2, self.p3, self.p1, eqDistance)
		#	self.p1.x, self.p1.y = new_p1[0], new_p1[1]
		#	self.p2.x, self.p2.y = new_p2[0], new_p2[1]

		return self.__class__(self.p0.asTuple(), new_p1, new_p2, self.p3.asTuple())

	def eqHobbySpline(self, curvature=(.9,.9)):
		'''Calculates and applies John Hobby's mock-curvature-smoothness by given curvature - tuple(float,float) or (float)
		Based on Metapolator's Hobby Spline by Juraj Sukop, Lasse Fister, Simon Egli
		'''
		from math import atan2, degrees, pi, sin, cos, radians, e, sqrt
		
		def arg(x): # Phase
			return atan2(x.imag, x.real)

		def hobby(theta, phi):
			st, ct = sin(theta), cos(theta)
			sp, cp = sin(phi), cos(phi)
			velocity = (2 + sqrt(2) * (st - 1/16*sp) * (sp - 1/16*st) * (ct - cp)) / (3 * (1 + 0.5*(sqrt(5) - 1) * ct + 0.5*(3 - sqrt(5)) * cp))
			return velocity

		def controls(z0, w0, alpha, beta, w1, z1):
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			u = z0 + e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / alpha
			v = z1 - e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / beta
			return u, v

		def getCurvature(z0, w0, u, v, w1, z1):
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			alpha=  e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / (u - z0)
			beta =  -e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / (v - z1)
			return alpha, beta

		
		delta0 = complex(self.p1.x, self.p1.y) - complex(self.p0.x, self.p0.y)
		rad0 = atan2(delta0.real, delta0.imag)
		w0 = complex(sin(rad0), cos(rad0))
		
		delta1 = complex(self.p3.x, self.p3.y) - complex(self.p2.x, self.p2.y)
		rad1 = atan2(delta1.real, delta1.imag)
		w1 = complex(sin(rad1), cos(rad1))
		
		if isinstance(curvature, tuple):
			alpha, beta = curvature[0], curvature[1]
		else:
			alpha, beta = curvature, curvature
		u, v = controls(complex(self.p0.x, self.p0.y), w0, alpha, beta, w1, complex(self.p3.x, self.p3.y))
		
		#self.p1.x, self.p1.y = u.real, u.imag
		#self.p2.x, self.p2.y = v.real, v.imag
		
		return self.__class__(self.p0.asTuple(), (u.real, u.imag), (v.real, v.imag), self.p3.asTuple())		

	def getHobbyCurvature(self):
		'''Returns current curvature coefficients (complex(alpha), complex(beta)) for 
		both handles according to John Hobby's mock-curvature calculation
		'''
		from math import atan2, degrees, pi, sin, cos, radians, e, sqrt
		
		def arg(x): # Phase
			return atan2(x.imag, x.real)

		def hobby(theta, phi):
			st, ct = sin(theta), cos(theta)
			sp, cp = sin(phi), cos(phi)
			velocity = (2 + sqrt(2) * (st - 1/16*sp) * (sp - 1/16*st) * (ct - cp)) / (3 * (1 + 0.5*(sqrt(5) - 1) * ct + 0.5*(3 - sqrt(5)) * cp))
			return velocity

		def getCurvature(z0, w0, u, v, w1, z1):
			theta = arg(w0 / (z1 - z0))
			phi = arg((z1 - z0) / w1)
			alpha=  e**(0+1j * theta) * (z1 - z0) * hobby(theta, phi) / (u - z0)
			beta =  -e**(0-1j * phi) * (z1 - z0) * hobby(phi, theta) / (v - z1)
			return alpha, beta

		
		delta0 = complex(self.p1.x, self.p1.y) - complex(self.p0.x, self.p0.y)
		rad0 = atan2(delta0.real, delta0.imag)
		w0 = complex(sin(rad0), cos(rad0))
		
		delta1 = complex(self.p3.x, self.p3.y) - complex(self.p2.x, self.p2.y)
		rad1 = atan2(delta1.real, delta1.imag)
		w1 = complex(sin(rad1), cos(rad1))

		u = complex(self.p1.x, self.p1.y)
		v = complex(self.p2.x, self.p2.y)
		
		alpha, beta = getCurvature(complex(self.p0.x, self.p0.y), w0, u, v, w1, complex(self.p3.x, self.p3.y))
		return alpha, beta

	def eqTunni(self):
		'''		Make proportional handles keeping curvature and on-curve point positions 
		Based on modified Andres Torresi implementation of Eduardo Tunni's method for control points

		TODO/NOTES:
			1) FL Point class dependent - could be rewritten without it, or just build new Point class
			2) Fix the case with (practicalInfinity) - should it use Fall-back or Tunnier should be rewritten
			3) Fix the case with with BCPs crossing behind the curve - causes flip, could be reverse calculated?!
		'''
		from FL import Point
		from math import hypot
		from typerig.brain import Coord

		practicalInfinity = Coord(100000, 100000) # Infinite coordinate for FL5

		# - Helper functions
		def getCrossing(p0, p1, p2, p3):
			# - Init
			diffA = p1 - p0 						# p1.x - p0.x, p1.y - p0.y
			prodA = p1 & Coord(p0.y,-p0.x) 		# p1.x * p0.y - p0.x * p1.y
			
			diffB = p3 - p2 								
			prodB = p3 & Coord(p2.y,-p2.x) 

			# - Get intersection
			det = diffA & Coord(diffB.y, -diffB.x) 	# diffA.x * diffB.y - diffB.x * diffA.y
			x = diffB.x * prodA - diffA.x * prodB
			y = diffB.y * prodA - diffA.y * prodB

			try:
				return Coord(x / det, y / det)

			except ZeroDivisionError:
				return practicalInfinity

		def setProportion(pointA, pointB, prop):
			# - Set proportions according to Edaurdo Tunni
			sign = lambda x: (1, -1)[x < 0] # Helper function
			xDiff = max(pointA.x, pointB.x) - min(pointA.x, pointB.x)
			yDiff = max(pointA.y, pointB.y) - min(pointA.y, pointB.y)
			xEnd = pointA.x + xDiff * prop * sign(pointB.x - pointA.x)
			yEnd = pointA.y + yDiff * prop * sign(pointB.y - pointA.y)

			return Coord(xEnd, yEnd)

		# - Run ------------------
		# -- Init
		crossing = getCrossing(self.p3, self.p2, self.p0, self.p1)
		
		if crossing != practicalInfinity:
			node2extrema = hypot(self.p3.x - crossing.x, self.p3.y - crossing.y)
			node2bcp = hypot(self.p3.x - self.p2.x, self.p3.y - self.p2.y)
			proportion = (node2bcp / node2extrema)

			# -- Calculate
			bcp2b = setProportion(self.p0, crossing, proportion)
			propA = hypot(self.p0.x - self.p1.x , self.p0.y - self.p1.y) / hypot(self.p0.x - crossing.x, self.p0.y - crossing.y)
			propB = hypot(self.p0.x - bcp2b.x, self.p0.y - bcp2b.y) / hypot(self.p0.x - crossing.x, self.p0.y - crossing.y)
			propMean = (propA + propB) / 2

			bcp2c = setProportion(self.p0, crossing, propMean)
			bcp1b = setProportion(self.p3, crossing, propMean)

			return self.__class__(self.p0.asTuple(), (bcp2c.x, bcp2c.y), (bcp1b.x, bcp1b.y), self.p3.asTuple())
		else:
			return None

	def interpolateFirst(self, shift):
		diffBase = self.p3 - self.p0
		diffP1 = self.p3 - self.p1
		diffP2 = self.p3 - self.p2

		if diffBase.x != 0:
			self.p1.x += (diffP1.x/diffBase.x)*shift.x
			self.p2.x += (diffP2.x/diffBase.x)*shift.x

		if diffBase.y != 0:
			self.p1.y += (diffP1.y/diffBase.y)*shift.y
			self.p2.y += (diffP2.y/diffBase.y)*shift.y

		self.p0 += shift

		return self.__class__(self.p0, self.p1, self.p2, self.p3)

	def interpolateLast(self, shift):
		diffBase = self.p0 - self.p3
		diffP1 = self.p0 - self.p1
		diffP2 = self.p0 - self.p2

		if diffBase.x != 0:
			self.p1.x += (diffP1.x/diffBase.x)*shift.x
			self.p2.x += (diffP2.x/diffBase.x)*shift.x
			
		if diffBase.y != 0:
			self.p1.y += (diffP1.y/diffBase.y)*shift.y
			self.p2.y += (diffP2.y/diffBase.y)*shift.y

		self.p3 += shift

		return self.__class__(self.p0, self.p1, self.p2, self.p3)


# --- Real world ----------------------------------------------------------------------
class Coord(_Point): # Dumb Name but avoids name collision with FL6/FL5 Point object
	def __init__(self, *argv):
		from fontlab import flNode
		from PythonQt.QtCore import QPointF, QPoint

		self.angle = 0
		self.parent = argv
		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])

		if isinstance(argv[0], self.__class__):
			self.x, self.y = argv[0].x, argv[0].y

		if multiCheck(argv, float) or multiCheck(argv, int) :
			self.x, self.y = argv[0], argv[1]
		
		if multiCheck(argv, flNode):
			self.x, self.y = argv[0].x, argv[0].y
						
		if multiCheck(argv, QPointF) or multiCheck(argv, QPoint):
			self.x, self.y = argv[0].x(), argv[0].y()
		
		if multiCheck(argv, tuple) or multiCheck(argv, list) :
			self.x, self.y = argv[0]
		
	def __repr__(self):
		return '<Coord: %s,%s>' %(self.x, self.y)

	def asQPointF(self):
		from PythonQt.QtCore import QPointF
		return QPointF(self.x, self.y)

	def asQPoint(self):
		from PythonQt.QtCore import QPoint
		return QPointF(int(self.x), int(self.y))

class Line(_Line):
	def __init__(self, *argv):
		from fontlab import flNode, CurveEx
		from PythonQt.QtCore import QPoint, QPointF, QLine, QLineF
		from typerig.brain import Coord

		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])
		self.parent = argv

		if len(argv) == 4:
			self.p0 = Coord(argv[:2])
			self.p1 = Coord(argv[2:])

		if len(argv) == 2:
			if multiCheck(argv, Coord):
				self.p0, self.p1 = argv
			else:
				self.p0 = Coord(argv[0])
				self.p1 = Coord(argv[1])

		if len(argv) == 1 and isinstance(argv[0], CurveEx):
			self.p0 = Coord(argv[0].p0)
			self.p1 = Coord(argv[0].p1)			

		if multiCheck(argv, QLineF) or multiCheck(argv, QLine) and len(argv) == 1:
			self.p0 = Coord(argv[0].p1())
			self.p1 = Coord(argv[0].p2())

		self.update()

	def asTuple(self, toInt=False):
		return (self.p0.x, self.p0.y, self.p1.x, self.p1.y) if not toInt else (int(self.p0.x), int(self.p0.y), int(self.p1.x), int(self.p1.y))

	def asQLineF(self):
		from PythonQt.QtCore import QLineF
		return QLineF(*self.asTuple(False))

	def asQPoint(self):
		from PythonQt.QtCore import QLine
		return QPointF(*self.asTuple(True))

class Curve(_Curve):
	def __init__(self, *argv):
		from fontlab import flNode, CurveEx
		from PythonQt.QtCore import QPoint, QPointF
		from typerig.brain import Coord

		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])
		self.parent = argv

		if len(argv) == 4:
			if multiCheck(argv, Coord) or multiCheck(argv, flNode) or multiCheck(argv, tuple) or multiCheck(argv, list):
				self.p0, self.p1, self.p2, self.p3 = [Coord(item) for item in argv]

		if len(argv) == 1 and isinstance(argv[0], CurveEx):
			self.p0 = Coord(argv[0].p0)
			self.p1 = Coord(argv[0].bcp0)		
			self.p2 = Coord(argv[0].bcp1)
			self.p3 = Coord(argv[0].p1)

		