# MODULE: TypeRig / Core / Point Array (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.25.9'

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
		return zip(self.x, self.y)

	def asList(self):
		return [self.x, self.y]

	def flatten(self):
		return self.x + self.y

	def bounds(self):
		return (min(self.x), min(self.y), max(self.x), max(self.y))

	def items(self):
		return zip(self.x, self.y, self.type)