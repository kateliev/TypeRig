# MODULE: TypeRig / Core / Collection (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import print_function
from collections import MutableSequence, MutableMapping, defaultdict
import json

# - Init -------------------------------
__version__ = '0.28.6'

# - Objects ----------------------------
# -- Lists -----------------------------
class CustomList(MutableSequence):
	'''A more or less complete user-defined wrapper around list objects.
	Adapted from Source: https://github.com/enthought/Python-2.7.3/blob/master/Lib/UserList.py
	'''
	def __init__(self, initlist=None):
		self.data = []
		if initlist is not None:
			# XXX should this accept an arbitrary sequence?
			if type(initlist) == type(self.data):
				self.data[:] = initlist
			elif isinstance(initlist, self.__class__):
				self.data[:] = initlist.data[:]
			else:
				self.data = list(initlist)

	def __repr__(self): 
		return repr(self.data)

	def __lt__(self, other): 
		return self.data <  self.__cast(other)

	def __le__(self, other): 
		return self.data <= self.__cast(other)

	def __eq__(self, other): 
		return self.data == self.__cast(other)

	def __ne__(self, other): 
		return self.data != self.__cast(other)

	def __gt__(self, other): 
		return self.data >  self.__cast(other)

	def __ge__(self, other): 
		return self.data >= self.__cast(other)

	def __cmp__(self, other):
		return cmp(self.data, self.__cast(other))

	__hash__ = None # Mutable sequence, so not hashable

	def __contains__(self, item): 
		return item in self.data

	def __len__(self): 
		return len(self.data)

	def __getitem__(self, i): 
		return self.data[i]

	def __setitem__(self, i, item): 
		self.data[i] = item

	def __delitem__(self, i): 
		del self.data[i]

	def __getslice__(self, i, j):
		i = max(i, 0); j = max(j, 0)
		return self.__class__(self.data[i:j])

	def __setslice__(self, i, j, other):
		i = max(i, 0); j = max(j, 0)
		if isinstance(other, self.__class__):
			self.data[i:j] = other.data
		elif isinstance(other, type(self.data)):
			self.data[i:j] = other
		else:
			self.data[i:j] = list(other)

	def __delslice__(self, i, j):
		i = max(i, 0); j = max(j, 0)
		del self.data[i:j]

	def __add__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(self.data + other.data)
		elif isinstance(other, type(self.data)):
			return self.__class__(self.data + other)
		else:
			return self.__class__(self.data + list(other))

	def __radd__(self, other):
		if isinstance(other, self.__class__):
			return self.__class__(other.data + self.data)
		elif isinstance(other, type(self.data)):
			return self.__class__(other + self.data)
		else:
			return self.__class__(list(other) + self.data)

	def __iadd__(self, other):
		if isinstance(other, self.__class__):
			self.data += other.data
		elif isinstance(other, type(self.data)):
			self.data += other
		else:
			self.data += list(other)
		return self

	def __mul__(self, n):
		return self.__class__(self.data*n)

	__rmul__ = __mul__

	def __imul__(self, n):
		self.data *= n
		return self

	def __cast(self, other):
		if isinstance(other, self.__class__): return other.data
		else: return other

	def append(self, item): 
		self.data.append(item)

	def insert(self, i, item): 
		self.data.insert(i, item)

	def pop(self, i=-1): 
		return self.data.pop(i)

	def remove(self, item): 
		self.data.remove(item)

	def count(self, item): 
		return self.data.count(item)

	def index(self, item, *args): 
		return self.data.index(item, *args)

	def reverse(self): 
		self.data.reverse()

	def sort(self, *args, **kwds): 
		self.data.sort(*args, **kwds)

	def extend(self, other):
		if isinstance(other, self.__class__):
			self.data.extend(other.data)
		else:
			self.data.extend(other)

class dimList(CustomList):
	'''Custom list object that supports multiple dimensions
	Example: 
		a = dimList([[[1, 2, 3, 4], ['a', 'b', 'c', 'd']], [[5, 6, 7, 8], ['e', 'f', 'g', 'h']]])
		print(a[0,1,2])
	'''
	def __init__(self, *args, **kwargs):
		super(ndList, self).__init__(*args, **kwargs)
	
	def __nest_level(self, obj): # Nesting level of the object
		if not isinstance(obj, (self.__class__, list, tuple)):
			return 0

		max_level = 0

		for item in obj:
			max_level = max(max_level, self.__nest_level(item))

		return max_level + 1

	@property
	def dim(self): # Dimensions
		return len(self.data), self.__nest_level(self.data) 

	def __getitem__(self, *args): 
		if isinstance(args[0], tuple):
			retrieve = ''
			
			for i in args[0]:
				retrieve += '[{}]'.format(i)

			return eval('self.data{}'.format(retrieve))
		else:
			return self.data[args[0]]

	def __setitem__(self, *args): 
		if isinstance(args[0], tuple):
			retrieve = ''
			
			for i in args[0]:
				retrieve += '[{}]'.format(i)

			exec('self.data{}=args[1]'.format(retrieve))
		else:
			self.data[args[0]] = args[1]

# -- Dicts -----------------------------
class CustomDict(MutableMapping):
	'''A more or less complete user-defined wrapper around dictionary objects.
	Adapted from Source: https://github.com/enthought/Python-2.7.3/blob/master/Lib/self.__class__.py
	'''
	def __init__(self, dict=None, **kwargs):
		self.data = {}
		if dict is not None:
			self.update(dict)
			
		if len(kwargs):
			self.update(kwargs)

	def __repr__(self): 
		return repr(self.data)

	def __cmp__(self, dict):
		if isinstance(dict, self.__class__):
			return cmp(self.data, dict.data)
		else:
			return cmp(self.data, dict)

	__hash__ = None

	def __len__(self): 
		return len(self.data)

	def __getitem__(self, key):
		if key in self.data:
			return self.data[key]
		if hasattr(self.__class__, "__missing__"):
			return self.__class__.__missing__(self, key)
		raise KeyError(key)

	def __setitem__(self, key, item): 
		self.data[key] = item

	def __delitem__(self, key): 
		del self.data[key]

	def __iter__(self):
		return iter(self.data)

	def clear(self): 
		self.data.clear()

	def copy(self):
		if self.__class__ is self.__class__:
			return self.__class__(self.data.copy())
		import copy
		data = self.data
		try:
			self.data = {}
			c = copy.copy(self)
		finally:
			self.data = data
		c.update(self)
		return c

	def keys(self): 
		return self.data.keys()

	def items(self): 
		return self.data.items()

	def iteritems(self): 
		return self.data.iteritems()

	def iterkeys(self): 
		return self.data.iterkeys()

	def itervalues(self): 
		return self.data.itervalues()

	def values(self): 
		return self.data.values()

	def has_key(self, key): 
		return key in self.data

	def update(self, dict=None, **kwargs):
		if dict is None:
			pass
		elif isinstance(dict, self.__class__):
			self.data.update(dict.data)
		elif isinstance(dict, type({})) or not hasattr(dict, 'items'):
			self.data.update(dict)
		else:
			for k, v in dict.items():
				self[k] = v
		if len(kwargs):
			self.data.update(kwargs)

	def get(self, key, failobj=None):
		if key not in self:
			return failobj
		return self[key]

	def setdefault(self, key, failobj=None):
		if key not in self:
			self[key] = failobj
		return self[key]

	def pop(self, key, *args):
		return self.data.pop(key, *args)

	def popitem(self):
		return self.data.popitem()

	def __contains__(self, key):
		return key in self.data

	@classmethod
	def fromkeys(cls, iterable, value=None):
		d = cls()
		for key in iterable:
			d[key] = value
		return d


class biDict(CustomDict):
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



class extBiDict(CustomDict):
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

class attribdict(defaultdict):
	'''Default dictionary where keys can be accessed as attributes.'''
	def __init__(self, *args, **kwdargs):
		super(attribdict, self).__init__(attribdict, *args, **kwdargs)

	def __getattribute__(self, name):
		try:
			return object.__getattribute__(self, name)
		except AttributeError:
			try:
				return self[name]
			except KeyError:
				raise AttributeError(name)
		
	def __setattr__(self, name, value):
		if name in self.keys():
			self[name] = value
			return value
		else:
			object.__setattr__(self, name, value)

	def __delattr__(self, name):
		try:
			return object.__delattr__(self, name)
		except AttributeError:
			return self.pop(name, None)
					
	def __repr__(self):
		return '<%s: %s>' %(self.__class__.__name__, len(self.keys()))

	def __hash__(self):
		import copy
		
		def hash_helper(obj):
			if isinstance(obj, (set, tuple, list)):
				return tuple([hash_helper(element) for element in obj])    

			elif not isinstance(obj, dict):
				return hash(obj)

			new_obj = {}

			for key, value in obj.items():
				new_obj[key] = hash_helper(value)

			return hash(tuple(frozenset(sorted(new_obj.items()))))

		return hash_helper(self)

	def dir(self):
		tree_map = ['   .%s\t%s' %(key, type(value)) for key, value in self.items()]
		print('Attributes (Keys) map:\n%s' %('\n'.join(tree_map).expandtabs(30)))

	def factory(self, factory_type):
		self.default_factory = factory_type

	def lock(self):
		self.default_factory = None

	def extract(self, search):
		'''Pull all values of specified key (search)
		
		Attributes:
			search (Str): Search string

		Returns:
			generator
		'''
		
		def extract_helper(obj, search):
			if isinstance(obj, dict):
				for key, value in obj.items():
					if key == search:
						yield value
					else:	
						if isinstance(value, (dict, list)):
							for result in extract_helper(value, search):
								yield result

			elif isinstance(obj, list):
				for item in obj:
					for result in extract_helper(item, search):
						yield result

		return extract_helper(self, search)

	def where(self, search, search_type=None):
		'''Pull all objects that contain values of specified search.
		
		Attributes:
			search (Str): Search string
			search_type (type) : Value type
		Returns:
			generator
		'''
		def isisntance_plus(entity, test_type):
			if test_type is not None:
				return isinstance(entity, test_type)
			else:
				return True

		def where_helper(obj, search):
			if isinstance(obj, dict):
				for key, value in obj.items():
					if key == search and isisntance_plus(value, search_type):
						yield obj
					else:	
						if isinstance(value, (dict, list)):
							for result in where_helper(value, search):
								yield result

			elif isinstance(obj, list):
				for item in obj:
					for result in where_helper(item, search):
						yield result

		return where_helper(self, search)

	def contains(self, search, search_type=None):
		'''Does the object contain ANY value or nested object with given name (search)
		
		Attributes:
			search (Str): Search string
			search_type (type) : Value type

		Returns:
			Bool
		'''
		def isisntance_plus(entity, test_type):
			if test_type is not None:
				return isinstance(entity, test_type)
			else:
				return True
		
		def contains_helper(obj, search):
			if isinstance(obj, dict):
				for key, value in obj.items():
					if search in key and isisntance_plus(value, search_type):
						yield True
					else:
						if isinstance(value, (dict, list)):
							for result in contains_helper(value, search):
								yield result

			elif isinstance(obj, list):
				for item in obj:
					for result in contains_helper(item, search):
						yield result
			
			
		return any(list(contains_helper(self, search)))

class treeDict(defaultdict):
	'''
	Default dictionary where keys can be accessed as attributes. Light Version
	----
	Adapted from JsonTree by Doug Napoleone: https://github.com/dougn/jsontree
	'''
	def __init__(self, *args, **kwargs):
		super(treeDict, self).__init__(treeDict, *args, **kwargs)
		
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

jsontree = treeDict

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


# -- Test --------------------------------------
if __name__ == '__main__':
	a = CustomList([1,2,3,4,])
	b = CustomDict({1:1, 2:2})
	c = biDict({1:'a', 2:'b'})
	print(a,b,c,c.inverse['a'])
	c[1] = '44a'
	print(c)