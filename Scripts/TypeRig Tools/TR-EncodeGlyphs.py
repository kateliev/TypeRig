#FLM: TypeRig: Encoder
# ----------------------------------------
# (C) Vassil Kateliev, 2023-2025  (http://www.kateliev.com)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os
import json

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.core.fileio.nam import NAMparser
from typerig.core.fileio.textproto import TEXTPROTOparser

from typerig.core.base.message import *

# - Init --------------------------------
app_name, app_version = 'TypeRig | Encoder', '4.0'
app_id_key = 'com.typerig.data.encoding'
alt_suffix = '.'

root_dir = os.path.dirname(os.path.dirname(__file__))
file_formats = {'json':'JSON encoding (*.json)','nam':'FontLab Name File (*.nam)','textproto':'Protobuff (*.textproto)'}
common_suffix_separator = '.'

# - Interface -----------------------------
class dlg_encode_glyphs(QtGui.QDialog):
	def __init__(self):
		super(dlg_encode_glyphs, self).__init__()
	
		# - Init
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]
		self.font_encoding = {}

		# - Group box
		self.box_font = QtGui.QGroupBox('Process')
		self.box_source = QtGui.QGroupBox('Get Encoding')
		self.box_apply = QtGui.QGroupBox('Set Encoding')
		self.box_apply.setEnabled(False)

		# - Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_A.addItems(self.font_files)

		# - Radios
		self.rad_group_glyphs = QtGui.QButtonGroup()
		self.rad_group_source = QtGui.QButtonGroup()

		self.rad_glyphs_font = QtGui.QRadioButton('All glyphs')
		self.rad_glyphs_sellected = QtGui.QRadioButton('Selected only')

		self.rad_source_file = QtGui.QRadioButton('External file')
		self.rad_source_lib = QtGui.QRadioButton('Font Lib')
		
		self.rad_glyphs_font.setChecked(True)
		self.rad_source_file.setChecked(True)

		self.rad_group_glyphs.addButton(self.rad_glyphs_font, 1)
		self.rad_group_glyphs.addButton(self.rad_glyphs_sellected, 2)
		self.rad_group_source.addButton(self.rad_source_lib, 1)
		self.rad_group_source.addButton(self.rad_source_file, 2)

		# - Buttons
		self.btn_encode_glyphs = QtGui.QPushButton('Apply encoding')
		self.btn_encode_test = QtGui.QPushButton('Test encoding')
		self.btn_encode_import = QtGui.QPushButton('Load encoding')
		self.btn_encode_export = QtGui.QPushButton('Save encoding')
		self.btn_encode_import.clicked.connect(lambda: self.action_load_encoding())
		self.btn_encode_glyphs.clicked.connect(lambda: self.action_encode_glyphs())
		self.btn_encode_export.clicked.connect(lambda: self.action_export_encoding())
		self.btn_encode_test.clicked.connect(lambda: self.action_test_encoding())


		# -- Progress bar
		self.progress = QtGui.QProgressBar()
		self.progress.setMaximum(100)

		# - Build layouts 
		# -- Font 
		layout_src = QtGui.QGridLayout() 
		layout_src.addWidget(QtGui.QLabel('Font:'), 				1, 0, 1, 1)
		layout_src.addWidget(self.cmb_select_font_A,	 			1, 1, 1, 6)
		layout_src.addWidget(QtGui.QLabel('Process:'), 				4, 0, 1, 1)
		layout_src.addWidget(self.rad_glyphs_font,  				4, 1, 1, 3)
		layout_src.addWidget(self.rad_glyphs_sellected, 			4, 4, 1, 3)
		self.box_font.setLayout(layout_src)
		
		# -- Encoding Source 
		layout_enc = QtGui.QGridLayout() 
		layout_enc.addWidget(QtGui.QLabel('Source:'), 				1, 0, 1, 1)
		layout_enc.addWidget(self.rad_source_lib,  					1, 1, 1, 3)
		layout_enc.addWidget(self.rad_source_file, 					1, 4, 1, 3)
		layout_enc.addWidget(self.btn_encode_import,				2, 0, 1, 4)
		layout_enc.addWidget(self.btn_encode_export,				2, 4, 1, 4)
		self.box_source.setLayout(layout_enc)

		layout_app = QtGui.QGridLayout()
		layout_app.addWidget(self.btn_encode_glyphs,				2, 0, 1, 4)
		layout_app.addWidget(self.btn_encode_test,					2, 4, 1, 4)
		self.box_apply.setLayout(layout_app)
		
		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_font)
		layout_main.addWidget(self.box_source)
		layout_main.addWidget(self.box_apply)
		layout_main.addStretch()
		layout_main.addWidget(self.progress)


		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 200)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	# - Functions --------------------------------
	def __set_encoding(self, process_glyphs, enc_dict):
		# - Init
		all_glyph_counter = 0
		self.progress.setValue(all_glyph_counter)
		glyph_count = len(process_glyphs)
		done_glyphs = set()

		# - Process
		for glyph in process_glyphs:
			# - Set progress
			all_glyph_counter += 1
			current_progress = all_glyph_counter*100/glyph_count
			self.progress.setValue(current_progress)
			QtGui.QApplication.processEvents()
			
			if glyph.name in enc_dict:
				for value in enc_dict[glyph.name]:
					uni_int = int(value, 16) if isinstance(value, str) else value

					if not glyph.hasUnicode(uni_int):
						glyph.addUnicode(uni_int)
						done_glyphs.add(glyph.name)

		# - Apply
		if len(process_glyphs) > 0:
			output(0, app_name, 'Encoding for {} glyphs applied from {} unicode entries.'.format(len(done_glyphs), len(enc_dict.keys())))
			
			all_glyph_counter = 0 
			self.progress.setValue(all_glyph_counter)
			QtGui.QApplication.processEvents()

	def __test_encoding(self, process_glyphs, enc_dict):
		# - Init
		all_glyph_counter = 0
		self.progress.setValue(all_glyph_counter)
		glyph_count = len(process_glyphs)

		# - Process
		for glyph in process_glyphs:
			# - Set progress
			all_glyph_counter += 1
			current_progress = all_glyph_counter*100/glyph_count
			self.progress.setValue(current_progress)
			QtGui.QApplication.processEvents()

			if glyph.name in enc_dict:
				for value in enc_dict[glyph.name]:
					uni_int = int(value, 16) if isinstance(value, str) else value

					if not glyph.hasUnicode(uni_int):
						output(1, app_name, 'Glyph: /{}; Missing Unicode int: {}, hex: {};'.format(glyph.name, uni_int, hex(uni_int)))
						
		# - Apply
		if len(process_glyphs) > 0:
			output(0, app_name, 'Tested encoding for {} glyphs '.format(len(process_glyphs)))
			
			all_glyph_counter = 0 
			self.progress.setValue(all_glyph_counter)
			QtGui.QApplication.processEvents()

	def __get_encoding(self, process_glyphs):
		all_glyph_counter = 0
		self.progress.setValue(all_glyph_counter)
		glyph_count = len(process_glyphs)
		enc_dict = {}

		for glyph in process_glyphs:
			# - Set progress
			all_glyph_counter += 1
			current_progress = all_glyph_counter*100/glyph_count
			self.progress.setValue(current_progress)
			QtGui.QApplication.processEvents()

			# - Process
			# -- Probably an alternate - skip
			if common_suffix_separator in glyph.name: continue
			if not len(glyph.unicodes) or glyph.unicode is None: continue

			enc_dict[glyph.name] = glyph.unicodes

		# - Finish it
		all_glyph_counter = 0 
		self.progress.setValue(all_glyph_counter)
		QtGui.QApplication.processEvents()

		return enc_dict

	def file_save_encoding(self, enc_dict):
		load_path = QtGui.QFileDialog.getSaveFileName(None, 'Save glyph encoding to file', root_dir, ';;'.join(file_formats.values()))
		_, load_ext = os.path.splitext(load_path)

		if len(load_path):
			if load_ext == '.json':
				# - JSON dump format
				with open(load_path, 'w') as write_file:
					json.dump(enc_dict, write_file)
				
				output(0, app_name, 'Encoding for {} Glyphs saved to: {}'.format(len(enc_dict), load_path))

			else:
				raise NotImplementedError

		else:
			warnings.warn('No file selected!', FileImportWarning)

	def file_load_encoding(self):
		enc_dict = {}
		load_path = QtGui.QFileDialog.getOpenFileName(None, 'Load glyph encoding from file', root_dir, ';;'.join(file_formats.values()))
		_, load_ext = os.path.splitext(load_path)

		if len(load_path):
			if load_ext == '.json':
				# - JSON dump format
				with open(load_path ) as read_file:
					enc_dict = json.load(read_file)

				output(1, app_name, 'Encoding loaded from: {}.'.format(load_path))

			elif load_ext == '.nam':
				# - Fontlab NAM Format
				with NAMparser(load_path) as reader:
					for uni_int, glyph_name in reader:
						enc_dict[glyph_name] = uni_int

				output(1, app_name, 'Encoding loaded from: {}.'.format(load_path))

			elif load_ext == '.textproto':
				extract_pairs = []
				with TEXTPROTOparser(load_path) as reader:
					for line in reader:
						extract_pairs.append(line)

				enc_dict = dict(extract_pairs)
				output(1, app_name, 'Encoding loaded from: {}.'.format(load_path))

			else:
				warnings.warn('Unknown file type provided!\nPlease selecte one of the following filetypes: {}'.format('; '.join(file_formats.values())), FileImportWarning)
			

		else:
			warnings.warn('No file selected!', FileImportWarning)

		return enc_dict

	def action_export_encoding(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)

		if self.rad_glyphs_font.isChecked():
			process_glyphs = font_src.glyphs()
		else:
			process_glyphs = font_src.selectedGlyphs()

		enc_dict = self.__get_encoding(process_glyphs)
	
		if len(enc_dict.keys()):
			if self.rad_source_lib.isChecked():
				temp_lib = font_src.fl.packageLib
				temp_lib[app_id_key] = enc_dict
				font_src.fl.packageLib = temp_lib		
				output(0, app_name, 'Font:{}; Encoding for {} Glyphs saved to Font Lib.'.format(font_src.name, len(enc_dict)))
			else:
				self.file_save_encoding(enc_dict)

	def action_load_encoding(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)

		# - Get encoding data
		if self.rad_source_lib.isChecked():
			try:
				working_enc_dict = font_src.fl.packageLib[app_id_key]
			
			except KeyError:
				warnings.warn('Font Lib is missing required encoding data! Key: {}'.format(app_id_key), FontWarning)
				return

		else:
			working_enc_dict = self.file_load_encoding()

		if not len(working_enc_dict.keys()):
			warnings.warn('Empty Font encoding data provided! Aborting!', FontWarning)
			self.font_encoding = {}
		else:
			self.font_encoding = working_enc_dict
			self.box_apply.setEnabled(True)
			output(0, app_name, 'Font: {}; Loaded Encoding for {} Glyphs.'.format(font_src.name, len(working_enc_dict)))
		
	def action_encode_glyphs(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)
		
		if self.rad_glyphs_font.isChecked():
			process_glyphs = font_src.glyphs()
		else:
			process_glyphs = font_src.selectedGlyphs()
		
		# - Apply encoding
		self.__set_encoding(process_glyphs, self.font_encoding)

	def action_test_encoding(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)
		
		if self.rad_glyphs_font.isChecked():
			process_glyphs = font_src.glyphs()
		else:
			process_glyphs = font_src.selectedGlyphs()
		
		# - Apply encoding
		self.__test_encoding(process_glyphs, self.font_encoding)
		
# - RUN ------------------------------
dialog = dlg_encode_glyphs()