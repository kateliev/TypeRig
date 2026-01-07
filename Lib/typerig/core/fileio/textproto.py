# MODULE: Typerig / IO / Protobuff Parser (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2024 	(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------
# NOTE: A oversimplified parser with limited functionality
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import os

# - Init -----------------------------
__version__ = '0.0.1'

# - Functions ------------------------
def is_hex(value, base=16):
	try:
		new_value = int(value, base)
	except TypeError:
		return False
	return True
	
def line_extractor(source, delimiter):
	return source.split(delimiter)[1].strip()

# - Classes --------------------------
class TEXTPROTOparser(object):
	def __init__(self, file_path, file_mode='r'):
		# - File
		self.__extension = '.textproto'
		self.__path = file_path
		self.__mode = file_mode
		self.__file_object = None
		self.__file_data = None
		self.__accumulator = []
		
		if not file_path.endswith(self.__extension):
			raise NameError('ERROR:\t{} extension missing in file name: {}'.format(self.__extension, file_path))
		
		# - Vocabulary
		self.__template = 'name_to_codepoint {{\n  key: "{key}"\n  value: {value}\n}}\n'
		self.__key = 'key'
		self.__value = 'value'
		self.__mark_sep = ':'
		self.__str_mark = '"'
				
	def __enter__(self):
		self.__file_object = open(self.__path, self.__mode)
		if self.__mode not in ('a', 'w'):
			self.__file_data = iter(self.__file_object.readlines())
		return self

	def __exit__(self, type, val, tb):
		self.__file_object.close()

	def __iter__(self):
		return self

	def __next__(self):
		new_line = next(self.__file_data)
		
		if self.__file_data is None or new_line == None:
			raise StopIteration
		else:
			if self.__key in new_line and len(self.__accumulator) == 0:
				self.__accumulator.append(line_extractor(new_line, self.__mark_sep))
				return self.__next__()

			elif self.__value in new_line and len(self.__accumulator) == 1:
				extract_key = self.__accumulator[0]
				extract_value = line_extractor(new_line, self.__mark_sep)
				self.__accumulator = []

				return (eval(extract_key), eval(extract_value))
				
			else:
				return self.__next__()

	def next(self):
		# Python 2 fixup
		return self.__next__()

	def dump(self, pair_list, user_info=''):
		if self.__mode in ('a', 'w'):
			# - Export using template
			for unicode_int, glyph_name in pair_list:
				
				if glyph_name[0] == '_':
					glyph_name = glyph_name[1:]

				if not isinstance(unicode_int, int):
					unicode_int = int(uni_hex, 16)

				self.__file_object.write(self.__template.format(key=glyph_name, value=unicode_int))

		else:
			raise FileExistsError('ERROR:\t File not in writable mode! Aborting!')
