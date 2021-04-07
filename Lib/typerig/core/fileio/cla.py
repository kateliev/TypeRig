# MODULE: Typerig / IO / DTL CLA Parser (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# - Dependencies -------------------------
from __future__ import print_function
import os, warnings
from datetime import datetime

from typerig.core.base import message

# - Init -----------------------------
__version__ = '0.1.0'

# - Classes --------------------------
class CLAparser(object):
	def __init__(self, file_path, file_mode='r'):
		# - File
		self.__extension = '.cla'
		self.__path = file_path
		self.__mode = file_mode
		self.__file_object = None
		self.__file_data = None
		
		if not file_path.endswith(self.__extension):
			raise NameError('ERROR:\t{} extension missing in file name: {}'.format(self.__extension, file_path))
		
		# - Vocabulary
		self.__head_info = 		'# DTL Kern class file (CLA)\n# Generated by TypeRig (www.typerig.com)\n'
		self.__comment_line = 	'#'
		self.__end_line = 		';'
		self.__class_line = 	'@'
		self.__gen_pattern = 	'@{} = [{}];\n'
				
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
			if self.__class_line in new_line:
				class_name, class_members = new_line.strip().split('=')
				class_name = class_name.strip().replace(self.__class_line, '')
				class_members = class_members.strip().replace('[', '').replace(']', '').replace(self.__end_line,'').split(' ')
				return (class_name, class_members)
			else:
				return self.__next__()

	def next(self):
		# Python 2 fixup
		return self.__next__()

	def dump(self, pair_list, user_info=''):
		if self.__mode in ('a', 'w'):
			# - Prepare
			user_header = '\n'.join([self.__comment_line + ' ' + info for info in user_info.split('\n')])
			creation_date = self.__comment_line + ' Created on: ' + datetime.now().strftime('%d/%m/%Y %H:%M:%S') +'\n'
			
			file_head = self.__head_info + user_header + '\n' +	creation_date + '\n'
						
			# - Dump
			self.__file_object.writelines(file_head)

			for class_name, class_members in sorted(pair_list):
				self.__file_object.write(self.__gen_pattern.format(class_name, ' '.join(class_members)))

		else:
			warnings.warn('File not in writable mode! Aborting!', message.FileSaveWarning)


# - Test -----------------------------
if __name__ == '__main__':
	root_dir = os.path.dirname(os.path.dirname(__file__))
	guz_siti = '1.cla'
	guz_siti_out = 'test.cla'
	guz_file = os.path.join(root_dir, krn_siti)
	guz_file_out = os.path.join(root_dir, krn_filename_out)

	append_glyphs = []
	with CLAparser(krn_file) as reader:
		for a in reader:
			append_glyphs.append(a)
	
	with CLAparser(krn_file_out, 'w') as writer:
		writer.dump(append_glyphs)
			