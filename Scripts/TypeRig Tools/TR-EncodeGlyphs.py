#FLM: TypeRig: Encode Glyphs
# ----------------------------------------
# (C) Vassil Kateliev, 2023  (http://www.kateliev.com)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.core.base.message import *
from typerig.core.fileio.nam import *

# - Init --------------------------------
app_name, app_version = 'TR | Encode glyphs', '1.1'
str_all_masters = '*All masters*'

root_dir = os.path.dirname(os.path.dirname(__file__))
file_formats = {'nam':'FontLab Name File (*.nam);;'}
common_suffix_separator = '.'

# - Interface -----------------------------
class dlg_encode_glyphs(QtGui.QDialog):
	def __init__(self):
		super(dlg_encode_glyphs, self).__init__()
	
		# - Init
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]
		self.nam_table = {}

		# - Group box
		self.box_src = QtGui.QGroupBox('Process')
		self.box_dst = QtGui.QGroupBox('Encoding')

		# - Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_A.addItems(self.font_files)

		# - Radios
		self.rad_group_source = QtGui.QButtonGroup()
		self.rad_group_encode = QtGui.QButtonGroup()

		self.rad_source_font = QtGui.QRadioButton('All glyphs')
		self.rad_source_sellected = QtGui.QRadioButton('Selected only')

		self.rad_encode_all = QtGui.QRadioButton('All glyphs')
		self.rad_encode_none = QtGui.QRadioButton('Non encoded only')
		
		self.rad_encode_all.setEnabled(False)
		self.rad_encode_none.setEnabled(False)

		self.rad_source_font.setChecked(True)
		self.rad_encode_none.setChecked(True)

		self.rad_group_source.addButton(self.rad_source_font, 1)
		self.rad_group_source.addButton(self.rad_source_sellected, 2)
		self.rad_group_encode.addButton(self.rad_encode_all, 1)
		self.rad_group_encode.addButton(self.rad_encode_none, 2)

		# - Edit
		self.edt_nam_file = QtGui.QLineEdit()
		self.edt_nam_file.setPlaceholderText('*.nam')

		# - Buttons
		self.btn_load_nam = QtGui.QPushButton('Open')
		self.btn_load_nam.clicked.connect(self.file_load_nam)
		self.btn_encode_glyphs = QtGui.QPushButton('Apply encoding')
		self.btn_encode_glyphs.clicked.connect(lambda: self.action_encode_glyphs())

		# -- Progress bar
		self.progress = QtGui.QProgressBar()
		self.progress.setMaximum(100)

		# - Build layouts 
		# -- Soource 
		layout_src = QtGui.QGridLayout() 
		layout_src.addWidget(QtGui.QLabel('Font:'), 				1, 0, 1, 1)
		layout_src.addWidget(self.cmb_select_font_A,	 			1, 1, 1, 6)
		layout_src.addWidget(QtGui.QLabel('Process:'), 				4, 0, 1, 1)
		layout_src.addWidget(self.rad_source_font,  				4, 1, 1, 3)
		layout_src.addWidget(self.rad_source_sellected, 			4, 4, 1, 3)
		self.box_src.setLayout(layout_src)
		
		# -- Destination 
		layout_enc = QtGui.QGridLayout() 
		layout_enc.addWidget(QtGui.QLabel('File:'), 				1, 0, 1, 1)
		layout_enc.addWidget(self.edt_nam_file, 					1, 1, 1, 4)
		layout_enc.addWidget(self.btn_load_nam, 					1, 5, 1, 2)
		layout_enc.addWidget(QtGui.QLabel('Encode:'), 				2, 0, 1, 1)
		layout_enc.addWidget(self.rad_encode_all,  					2, 1, 1, 3)
		layout_enc.addWidget(self.rad_encode_none, 					2, 4, 1, 3)
		self.box_dst.setLayout(layout_enc)

		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_src)
		layout_main.addWidget(self.box_dst)
		layout_main.addStretch()
		layout_main.addWidget(self.btn_encode_glyphs)
		layout_main.addWidget(self.progress)

		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 200)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	# - Functions --------------------------------
	def __build_names(self, nam_filename):
		enc_dict = {}
		with NAMparser(nam_filename) as reader:
			for uni_int, glyph_name in reader:
				enc_dict[glyph_name] = uni_int
		return enc_dict

	def file_load_nam(self):
		nam_loadpath = QtGui.QFileDialog.getOpenFileName(None, 'Load Glyph names from file', root_dir, file_formats['nam'])
			
		if len(nam_loadpath):
			self.edt_nam_file.setText(nam_loadpath)
			self.nam_table = self.__build_names(nam_loadpath)
			output(3, app_name, 'FontLab Names file (.nam) loaded from: %s.' %nam_loadpath)

		else:
			warnings.warn('No file selected!', NAMimportWarning)

	def action_encode_glyphs(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)
		
		mode_source = 3 if self.rad_source_font.isChecked() else 2  # if 3 for Font, 2 for selected glyphs
		process_glyphs = getProcessGlyphs(mode=mode_source)

		all_glyph_counter = 0
		self.progress.setValue(all_glyph_counter)
		glyph_count = len(process_glyphs)

		for glyph in process_glyphs:
			# - Set progress
			all_glyph_counter += 1
			current_progress = all_glyph_counter*100/glyph_count
			self.progress.setValue(current_progress)
			QtGui.QApplication.processEvents()

			# - Process
			try:
				# - Probably an alternate - skip
				if common_suffix_separator in glyph.name: continue

				if glyph.name in self.nam_table:
					if self.rad_encode_none.isChecked() and len(glyph.unicodes): 
						# - Probably already encoded - skip
						warnings.warn('Glyph already encoded: %s' %glyph.name, GlyphWarning)
						continue 
					
					glyph.unicode = self.nam_table[glyph.name]
				else:
					warnings.warn('Unicode value not found!\tGlyph: %s' %glyph.name, NAMdataMissing)

			
			except AttributeError:
				warnings.warn('Glyph missing required attribute: %s' %glyph.name, GlyphWarning)

			
				
		# - Finish it
		if len(process_glyphs) > 0:
			font_src.updateObject(font_src.fl, 'Encoded glyphs: %s' %(len(process_glyphs)))

			all_glyph_counter = 0 
			self.progress.setValue(all_glyph_counter)
			QtGui.QApplication.processEvents()
		
# - RUN ------------------------------
dialog = dlg_encode_glyphs()