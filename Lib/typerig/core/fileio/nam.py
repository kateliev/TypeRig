# MODULE: Typerig / IO / Fontlab NAM Parser (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# - Dependencies -------------------------
from __future__ import print_function
import os, warnings

# - Init -----------------------------
__version__ = '0.0.3'

# - Classes --------------------------
class NAMparser(object):
	def __init__(self, file_path):
		# Ensure the file has the right extension
		if not file_path.endswith('.nam'):
			raise NameError('ERROR:\t.nam extension missing in file name:{}'.format(file_path))
		
		self.__path = file_path
		self.__file_object = None
		self.__ignored_line = '%'

	def __enter__(self):
		self.__file_object = open(self.__path, 'rb')
		return self

	def __exit__(self, type, val, tb):
		self.__file_object.close()

	def __iter__(self):
		return self

	def __next__(self):
		new_line = self.__file_object.readline().strip()

		if self.__file_object is None or new_line == b'':
			raise StopIteration
		else:
			if new_line[0] == self.__ignored_line:
				return self.__next__()
			else:
				uni_hex, char_name = new_line.split()
				return int(uni_hex,16), char_name

	def next(self):
		# Python 2 fixup
		return self.__next__()

# - Test -----------------------------
if __name__ == '__main__':
	import fontlab as fl6
	import fontgate as fgt
	from typerig.proxy import *

	# - Init
	font = pFont()
	root_dir = os.path.dirname(os.path.dirname(__file__))
	nam_filename = 'test.nam'
	nam_file = os.path.join(root_dir, nam_filename)

	append_glyphs = []
	with NAMparser(nam_file) as reader:
		for uni_int, glyph_name in reader:
			new_glyph = fgt.fgGlyph(glyph_name)
			new_glyph.setUnicode(uni_int)
			append_glyphs.append(new_glyph)
			print(uni_int, glyph_name)
			font.addGlyph(new_glyph)

	#font.update()
