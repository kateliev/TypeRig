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

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.utils import jsontree, vfj_encoder, vfj_decoder
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
		

class jFont(object):
	'''
	Proxy VFJ Font (Fontlab JSON Font format)

	Constructor:
		jFont(): Construct an empty jFont
		jFont(vfj_file_path): Load VFJ form vfj_file_path (STR)
		jFont(pFont): Load VFJ from pFont.path. VFJ Font has to be in the same path as the VFC

	Methods:
		.data(): Access to VFJ font
		.load(file_path): Load VFJ font from path
		.save_as(file_path): Save VFJ font to path
		.save(): Save VFJ (overwrite)
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