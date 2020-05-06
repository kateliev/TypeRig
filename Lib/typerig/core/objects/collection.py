# MODULE: TypeRig / Core / Collection (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.26.0'

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