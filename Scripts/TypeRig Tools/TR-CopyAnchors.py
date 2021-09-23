#FLM: TypeRig: Copy Anchors
#NOTE: Copy selected anchors between two fonts
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
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.core.base.message import *

# - Init --------------------------------
app_name, app_version = 'TR | Copy Anchors', '1.1'

# - Interface -----------------------------
class dlg_copy_anchors(QtGui.QDialog):
	def __init__(self):
		super(dlg_copy_anchors, self).__init__()
	
		# - Init
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]

		# - Group box
		self.box_src = QtGui.QGroupBox('Source')
		self.box_dst = QtGui.QGroupBox('Destination')

		# - Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_B = QtGui.QComboBox()
		self.cmb_select_font_A.addItems(self.font_files)
		self.cmb_select_font_B.addItems(self.font_files)

		self.cmb_select_color_A = QtGui.QComboBox()
		self.cmb_select_color_B = QtGui.QComboBox()
		
		# - Radios
		self.rad_group_copy = QtGui.QButtonGroup()
		self.rad_group_collide = QtGui.QButtonGroup()
		self.rad_group_rename = QtGui.QButtonGroup()
		self.rad_group_source = QtGui.QButtonGroup()

		self.rad_source_font = QtGui.QRadioButton('All glyphs')
		self.rad_source_sellected = QtGui.QRadioButton('Selected glyphs')
		self.rad_copy_all = QtGui.QRadioButton('All anchors')
		self.rad_copy_specific = QtGui.QRadioButton('Specific anchors')
		self.rad_collide_write = QtGui.QRadioButton('Overwrite')
		self.rad_collide_rename = QtGui.QRadioButton('Rename')
		self.rad_collide_src = QtGui.QRadioButton('Incoming')
		self.rad_collide_dst = QtGui.QRadioButton('Destination')
		
		self.rad_copy_all.setChecked(True)
		self.rad_collide_dst.setChecked(True)
		self.rad_source_font.setChecked(True)
		self.rad_collide_rename.setChecked(True)

		self.rad_group_source.addButton(self.rad_source_font, 1)
		self.rad_group_source.addButton(self.rad_source_sellected, 2)
		self.rad_group_copy.addButton(self.rad_copy_all, 1)
		self.rad_group_copy.addButton(self.rad_copy_specific, 2)
		self.rad_group_rename.addButton(self.rad_collide_src, 1)
		self.rad_group_rename.addButton(self.rad_collide_dst, 2)
		self.rad_group_collide.addButton(self.rad_collide_write, 1)
		self.rad_group_collide.addButton(self.rad_collide_rename, 2)

		# - Edit
		self.edt_anchors_list = QtGui.QLineEdit()
		self.edt_collide_suffix = QtGui.QLineEdit()
		self.edt_anchors_list.setPlaceholderText('Comma separated list of anchors: top, left')
		self.edt_collide_suffix.setPlaceholderText('Examples: .new, .bak, .1')
		self.edt_collide_suffix.setText('.bak')

		# - Buttons 
		self.btn_copy_anchors = QtGui.QPushButton('Copy Anchors')
		self.btn_copy_anchors.clicked.connect(self.action_copy_anchors)
				
		# - Build layouts 
		# -- Soource 
		layout_src = QtGui.QGridLayout() 
		#layout_src.addWidget(QtGui.QLabel('Source font:'), 			1, 0, 1, 6)
		layout_src.addWidget(self.cmb_select_font_A,	 			2, 0, 1, 7)
		layout_src.addWidget(QtGui.QLabel('Copy from:'), 			3, 0, 1, 1)
		layout_src.addWidget(self.rad_source_font,  				3, 1, 1, 3)
		layout_src.addWidget(self.rad_source_sellected, 			3, 4, 1, 3)
		layout_src.addWidget(QtGui.QLabel('Which anchors:'), 		5, 0, 1, 1)
		layout_src.addWidget(self.rad_copy_all,  					5, 1, 1, 3)
		layout_src.addWidget(self.rad_copy_specific, 				5, 4, 1, 3)
		layout_src.addWidget(QtGui.QLabel('Anchors list:'), 		7, 0, 1, 1)
		layout_src.addWidget(self.edt_anchors_list, 				7, 1, 1, 6)
		self.box_src.setLayout(layout_src)
		
		# -- Destination 
		layout_dst = QtGui.QGridLayout() 
		#layout_dst.addWidget(QtGui.QLabel('\nDestination font:'), 	1, 0, 1, 6)
		layout_dst.addWidget(self.cmb_select_font_B,	 			2, 0, 1, 7)
		layout_dst.addWidget(QtGui.QLabel('Handle Collision:'), 	3, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_write, 				3, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_rename, 				3, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Collision rename:'), 	4, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_src, 					4, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_dst, 					4, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Addon suffix:'), 		5, 0, 1, 1)
		layout_dst.addWidget(self.edt_collide_suffix, 				5, 1, 1, 6)
		self.box_dst.setLayout(layout_dst)

		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_src)
		layout_main.addWidget(self.box_dst)
		layout_main.addStretch()
		layout_main.addWidget(self.btn_copy_anchors)


		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 300)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def action_copy_anchors(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_dst_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)]
		
		mode_source = 3 if self.rad_source_font.isChecked() else 2  # if 3 for Font, 2 for selected glyphs
		mode_anchors = self.rad_copy_specific.isChecked()			# if True source for specific anchors
		mode_collide = self.rad_collide_rename.isChecked()			# if True rename 
		mode_rename = self.rad_collide_dst.isChecked()				# if True modify destination
		anchors_list = [item.strip() for item in self.edt_anchors_list.split(',').strip()] if mode_source else []
		replace_suffix = self.edt_collide_suffix.strip()

		glyphs_source = getProcessGlyphs(mode=mode_source, font=font_src_fl)
		font_dst = pFont(font_dst_fl)

		do_update = False

		# - Process 
		for glyph in glyphs_source:
			if font_dst.hasGlyph(glyph.name):
				pass
			else:
				output(2, 'Destination glyph not found! Font: {}; Glyph: {}'.format(self.cmb_select_font_B.currentText, glyph.name))

		

	
# - RUN ------------------------------
dialog = dlg_copy_anchors()