# MODULE: TypeRig / Core / Collection (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.27.0'

# - Dependencies ------------------------
import json
from collections import defaultdict

# - Objects ----------------------------
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