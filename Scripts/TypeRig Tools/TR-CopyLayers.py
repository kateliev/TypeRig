#FLM: TypeRig: Copy Layers
#NOTE: Copy selected layers between two fonts
# ----------------------------------------
# (C) Vassil Kateliev, 2021  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
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
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRColorCombo

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.core.base.message import *

# - Init --------------------------------
app_name, app_version = 'TR | Copy Layers', '1.7'

# - Interface -----------------------------
class dlg_copy_layers(QtGui.QDialog):
	def __init__(self):
		super(dlg_copy_layers, self).__init__()
	
		# - Init
		self.all_fonts = None
		self.font_files = None

		# - Group box
		self.box_src = QtGui.QGroupBox('Source')
		self.box_dst = QtGui.QGroupBox('Destination')

		# - Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_B = QtGui.QComboBox()
		self.cmb_mark = TRColorCombo()
		self.refresh_fonts_list()

		self.cmb_select_layer_A = QtGui.QComboBox()
		self.cmb_select_layer_B = QtGui.QComboBox()
		self.refresh_layers_list('A')
		self.refresh_layers_list('B')
		
		# - Radios
		self.rad_group_copy = QtGui.QButtonGroup()
		self.rad_group_collide = QtGui.QButtonGroup()
		self.rad_group_rename = QtGui.QButtonGroup()
		self.rad_group_source = QtGui.QButtonGroup()
		self.rad_group_type = QtGui.QButtonGroup()

		self.rad_source_font = QtGui.QRadioButton('All glyphs')
		self.rad_source_sellected = QtGui.QRadioButton('Selected glyphs')
		self.rad_collide_write = QtGui.QRadioButton('Overwrite')
		self.rad_collide_rename = QtGui.QRadioButton('Rename')
		self.rad_collide_src = QtGui.QRadioButton('Incoming')
		self.rad_collide_dst = QtGui.QRadioButton('Destination')
		self.rad_type_master = QtGui.QRadioButton('Layer + suffix')
		self.rad_type_mask = QtGui.QRadioButton('Mask')
		
		self.rad_collide_dst.setChecked(True)
		self.rad_source_sellected.setChecked(True)
		self.rad_collide_rename.setChecked(True)
		self.rad_type_mask.setChecked(True)

		self.rad_group_source.addButton(self.rad_source_font, 1)
		self.rad_group_source.addButton(self.rad_source_sellected, 2)
		self.rad_group_rename.addButton(self.rad_collide_src, 1)
		self.rad_group_rename.addButton(self.rad_collide_dst, 2)
		self.rad_group_collide.addButton(self.rad_collide_write, 1)
		self.rad_group_collide.addButton(self.rad_collide_rename, 2)
		self.rad_group_type.addButton(self.rad_type_master, 1)
		self.rad_group_type.addButton(self.rad_type_mask, 2)

		# - Edit
		self.edt_collide_suffix = QtGui.QLineEdit()
		self.edt_collide_suffix.setPlaceholderText('Examples: .new, .bak, .1')
		self.edt_collide_suffix.setText('.bak')

		# - Buttons 
		self.btn_cmb_font_A_refresh = QtGui.QPushButton('<<')
		self.btn_cmb_font_B_refresh = QtGui.QPushButton('<<')
		self.btn_cmb_layer_A_refresh = QtGui.QPushButton('<<')
		self.btn_cmb_layer_B_refresh = QtGui.QPushButton('<<')
		self.btn_copy_layers = QtGui.QPushButton('Copy layers')

		self.btn_cmb_layer_A_refresh.setToolTip('Refresh layers list')
		self.btn_cmb_layer_B_refresh.setToolTip('Refresh layers list')
		self.btn_cmb_layer_A_refresh.setMaximumWidth(30)
		self.btn_cmb_layer_B_refresh.setMaximumWidth(30)
		
		self.btn_copy_layers.clicked.connect(lambda: self.action_copy_layers())
		self.btn_cmb_layer_A_refresh.clicked.connect(lambda: self.refresh_layers_list('A'))
		self.btn_cmb_layer_B_refresh.clicked.connect(lambda: self.refresh_layers_list('B'))
		self.btn_cmb_font_A_refresh.clicked.connect(lambda: self.refresh_fonts_list())
		self.btn_cmb_font_B_refresh.clicked.connect(lambda: self.refresh_fonts_list())
				
		# - Build layouts 
		# -- Soource 
		layout_src = QtGui.QGridLayout() 
		#layout_src.addWidget(QtGui.QLabel('Source font:'), 			1, 0, 1, 6)
		layout_src.addWidget(self.cmb_select_font_A,	 			2, 0, 1, 6)
		layout_src.addWidget(self.btn_cmb_font_A_refresh,			2, 6, 1, 1)
		layout_src.addWidget(QtGui.QLabel('Source Layer:'), 		3, 0, 1, 1)
		layout_src.addWidget(self.cmb_select_layer_A, 				3, 1, 1, 5)
		layout_src.addWidget(self.btn_cmb_layer_A_refresh,			3, 6, 1, 1)
		layout_src.addWidget(QtGui.QLabel('Copy from:'), 			4, 0, 1, 1)
		layout_src.addWidget(self.rad_source_font,  				4, 1, 1, 3)
		layout_src.addWidget(self.rad_source_sellected, 			4, 4, 1, 3)
		self.box_src.setLayout(layout_src)
		
		# -- Destination 
		layout_dst = QtGui.QGridLayout() 
		#layout_dst.addWidget(QtGui.QLabel('\nDestination font:'), 	1, 0, 1, 6)
		layout_dst.addWidget(self.cmb_select_font_B,	 			2, 0, 1, 6)
		layout_dst.addWidget(self.btn_cmb_font_B_refresh,			2, 6, 1, 1)
		layout_dst.addWidget(QtGui.QLabel('Destination Layer:'), 	3, 0, 1, 1)
		layout_dst.addWidget(self.cmb_select_layer_B, 				3, 1, 1, 5)
		layout_dst.addWidget(self.btn_cmb_layer_B_refresh,			3, 6, 1, 1)
		layout_dst.addWidget(QtGui.QLabel('Handle Collision:'), 	4, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_write, 				4, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_rename, 				4, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Collision rename:'), 	5, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_src, 					5, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_dst, 					5, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Collision type:'), 		6, 0, 1, 1)
		layout_dst.addWidget(self.rad_type_master, 					6, 1, 1, 3)
		layout_dst.addWidget(self.rad_type_mask, 					6, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Addon suffix:'), 		7, 0, 1, 1)
		layout_dst.addWidget(self.edt_collide_suffix, 				7, 1, 1, 6)
		layout_dst.addWidget(QtGui.QLabel('Colorize:'), 			8, 0, 1, 1)
		layout_dst.addWidget(self.cmb_mark, 						8, 1, 1, 6)
		self.box_dst.setLayout(layout_dst)

		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_src)
		layout_main.addWidget(self.box_dst)
		layout_main.addStretch()
		layout_main.addWidget(self.btn_copy_layers)


		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 300)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	# - Functions --------------------------------
	def refresh_fonts_list(self):
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]
		self.cmb_select_font_A.clear()
		self.cmb_select_font_B.clear()
		self.cmb_select_font_A.addItems(self.font_files)
		self.cmb_select_font_B.addItems(self.font_files)

		output(0, app_name, 'Font lists updated!')


	def refresh_layers_list(self, control):
		if control == 'A':
			tmp_font = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)])
			self.cmb_select_layer_A.clear()
			self.cmb_select_layer_A.addItems(tmp_font.masters())
		else:
			tmp_font = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)])
			self.cmb_select_layer_B.clear()
			self.cmb_select_layer_B.addItems(tmp_font.masters())

		output(0, app_name, 'Layers list updated!')

	def action_copy_layers(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_dst_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)]

		font_src = pFont(font_src_fl)
		font_dst = pFont(font_dst_fl)
		
		mode_source = 3 if self.rad_source_font.isChecked() else 2  # if 3 for Font, 2 for selected glyphs
		mode_collide = self.rad_collide_rename.isChecked()			# if True rename 
		mode_destination =  self.rad_collide_dst.isChecked()
		mode_rename = self.rad_collide_dst.isChecked()				# if True modify destination
		mode_mask = 'mask' if self.rad_type_mask.isChecked() else 'new'
		
		replace_suffix = self.edt_collide_suffix.text.strip() if not self.rad_type_mask.isChecked() else ''
		new_layer_options = {'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': False}

		#glyphs_source = getProcessGlyphs(mode=mode_source, font=font_src_fl)
		glyphs_source_names = []

		for glyph in getProcessGlyphs(mode=mode_source):
			if font_src.hasGlyph(glyph.name):
				glyphs_source_names.append(glyph.name)
			else:
				output(2, app_name, 'Source glyph not found! Font: {}; Glyph: {}'.format(self.cmb_select_font_B.currentText, glyph.name))
		
		if len(glyphs_source_names):
			glyphs_source = font_src.pGlyphs(glyphs_source_names)
		else:
			output(3, app_name, 'Nothing to process! Font: {}.'.format(self.cmb_select_font_B.currentText))
			return
		
		layer_src = self.cmb_select_layer_A.currentText
		layer_dst = self.cmb_select_layer_B.currentText
		do_update = False

		# - Process 
		for src_glyph in glyphs_source:
			if font_dst.hasGlyph(src_glyph.name):
				dst_glyph = font_dst.glyph(src_glyph.name, extend=eGlyph)

				# - Handle collision
				if dst_glyph.layer(layer_dst) is not None:
					if mode_collide and mode_destination:  
						new_layer_name = layer_dst + replace_suffix if mode_rename else layer_src + replace_suffix  # Rename mode
						dst_glyph.importLayer(dst_glyph, layer_dst, new_layer_name, new_layer_options, addLayer=True, cleanDST=True, toBack=True, mode=mode_mask)
					
					if mode_destination:
						dst_glyph.removeLayer(layer_dst)

				if mode_collide and not mode_rename:
					layer_dst = layer_dst + replace_suffix

				# - Copy
				mode_mask = 'mask' if self.rad_type_mask.isChecked() and not mode_destination else 'new'
				dst_glyph.importLayer(src_glyph, layer_src, layer_dst, new_layer_options, addLayer=True, cleanDST=True, toBack=True, mode=mode_mask)
				dst_glyph.mark = self.cmb_mark.getValue()
				do_update = True

			else:
				output(2, app_name, 'Destination glyph not found! Font: {}; Glyph: {}'.format(self.cmb_select_font_B.currentText, src_glyph.name))

		# - Finish it
		if do_update:
			font_dst.updateObject(font_dst.fl, 'Copying layers! Glyphs processed: %s' %len(glyphs_source))
		

	
# - RUN ------------------------------
dialog = dlg_copy_layers()