# MODULE: Fontlab 6 Custom Font Objects | Typerig
# VER 	: 0.02
# ----------------------------------------
# (C) Vassil Kateliev, 2017 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import json
import json.scanner
from collections import defaultdict

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pFont


# - Classes -------------------------------
class eFont(pFont):
	'''
	Proxy Font extension, packing some useful tools.

	Constructor:
		eFont() - default represents the current glyph and current font
		eFont(fgFont)
	'''

	def copyZones(self, font):
		if isinstance(font, fgt.fgFont):
			srcFont = pFont(font)
		elif isinstance(font, pFont):
			srcFont = font

		pass # TODO!
		
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

# --- VFJ Font Object
class jFont(object):
	'''
	Proxy VFJ Font

	Constructor:
		jFont()
		jFont(vfj_file_path)
		jFont(pFont)
		
	'''

	def __init__(self, source=None):
		# - Init
		self.data = None
		self.source = None
		self.path = None

		if source is not None:
			if isinstance(source, basestring):
				self.path = source

			elif isinstance(source, pFont):
				self.path = source.path.replace('vfc', 'vfj')
			
			self.load(self.path)

	def load(self, file_path):
		with open(file_path, 'r') as importFile:
			self.data = json.load(importFile, cls=vfj_decoder)
		
		self.path = file_path
		return True

	def save_as(self, file_path):
		with open(file_path, 'w') as exportFile:
			json.dump(self.data, exportFile, cls=vfj_encoder)
		return True

	def save(self):
		return self.save_as(self.path)