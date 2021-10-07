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
app_name, app_version = 'TR | Copy Anchors', '1.7'
str_all_masters = '*All masters*'

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

		self.cmb_select_layer_A = QtGui.QComboBox()
		self.cmb_select_layer_B = QtGui.QComboBox()
		self.cmb_select_layer_A.addItems([str_all_masters])
		self.cmb_select_layer_B.addItems([str_all_masters])
		
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
		self.btn_cmb_layer_A_refresh = QtGui.QPushButton('<<')
		self.btn_cmb_layer_B_refresh = QtGui.QPushButton('<<')
		self.btn_copy_anchors = QtGui.QPushButton('Copy Anchors')

		self.btn_cmb_layer_A_refresh.setToolTip('Refresh layers list')
		self.btn_cmb_layer_B_refresh.setToolTip('Refresh layers list')
		self.btn_cmb_layer_A_refresh.setMaximumWidth(30)
		self.btn_cmb_layer_B_refresh.setMaximumWidth(30)
		
		self.btn_copy_anchors.clicked.connect(lambda: self.action_copy_anchors())
		self.btn_cmb_layer_A_refresh.clicked.connect(lambda: self.refresh_layers_list('A'))
		self.btn_cmb_layer_B_refresh.clicked.connect(lambda: self.refresh_layers_list('B'))
				
		# - Build layouts 
		# -- Soource 
		layout_src = QtGui.QGridLayout() 
		#layout_src.addWidget(QtGui.QLabel('Source font:'), 			1, 0, 1, 6)
		layout_src.addWidget(self.cmb_select_font_A,	 			2, 0, 1, 7)
		layout_src.addWidget(QtGui.QLabel('Source Layer:'), 		3, 0, 1, 1)
		layout_src.addWidget(self.cmb_select_layer_A, 				3, 1, 1, 5)
		layout_src.addWidget(self.btn_cmb_layer_A_refresh,			3, 6, 1, 1)
		layout_src.addWidget(QtGui.QLabel('Copy from:'), 			4, 0, 1, 1)
		layout_src.addWidget(self.rad_source_font,  				4, 1, 1, 3)
		layout_src.addWidget(self.rad_source_sellected, 			4, 4, 1, 3)
		layout_src.addWidget(QtGui.QLabel('Which anchors:'), 		6, 0, 1, 1)
		layout_src.addWidget(self.rad_copy_all,  					6, 1, 1, 3)
		layout_src.addWidget(self.rad_copy_specific, 				6, 4, 1, 3)
		layout_src.addWidget(QtGui.QLabel('Anchors list:'), 		8, 0, 1, 1)
		layout_src.addWidget(self.edt_anchors_list, 				8, 1, 1, 6)
		self.box_src.setLayout(layout_src)
		
		# -- Destination 
		layout_dst = QtGui.QGridLayout() 
		#layout_dst.addWidget(QtGui.QLabel('\nDestination font:'), 	1, 0, 1, 6)
		layout_dst.addWidget(self.cmb_select_font_B,	 			2, 0, 1, 7)
		layout_dst.addWidget(QtGui.QLabel('Destination Layer:'), 	3, 0, 1, 1)
		layout_dst.addWidget(self.cmb_select_layer_B, 				3, 1, 1, 5)
		layout_dst.addWidget(self.btn_cmb_layer_B_refresh,			3, 6, 1, 1)
		layout_dst.addWidget(QtGui.QLabel('Handle Collision:'), 	4, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_write, 				4, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_rename, 				4, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Collision rename:'), 	5, 0, 1, 1)
		layout_dst.addWidget(self.rad_collide_src, 					5, 1, 1, 3)
		layout_dst.addWidget(self.rad_collide_dst, 					5, 4, 1, 3)
		layout_dst.addWidget(QtGui.QLabel('Addon suffix:'), 		6, 0, 1, 1)
		layout_dst.addWidget(self.edt_collide_suffix, 				6, 1, 1, 6)
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

	# - Functions --------------------------------
	def refresh_layers_list(self, control):
		if control == 'A':
			tmp_font = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)])
			self.cmb_select_layer_A.clear()
			self.cmb_select_layer_A.addItems([str_all_masters] + tmp_font.masters())
		else:
			tmp_font = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)])
			self.cmb_select_layer_B.clear()
			self.cmb_select_layer_B.addItems([str_all_masters] + tmp_font.masters())

		output(0, app_name, 'Layers list updated!')

	def action_copy_anchors(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_dst_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)]

		font_src = pFont(font_src_fl)
		font_dst = pFont(font_dst_fl)
		
		mode_source = 3 if self.rad_source_font.isChecked() else 2  # if 3 for Font, 2 for selected glyphs
		mode_anchors = self.rad_copy_specific.isChecked()			# if True source for specific anchors
		mode_collide = self.rad_collide_rename.isChecked()			# if True rename 
		mode_rename = self.rad_collide_dst.isChecked()				# if True modify destination

		anchors_list = [item.strip() for item in self.edt_anchors_list.text.strip().split(',')] if mode_source else []
		replace_suffix = self.edt_collide_suffix.text.strip()

		#glyphs_source = getProcessGlyphs(mode=mode_source, font=font_src_fl)
		glyphs_source_names = [glyph.name for glyph in getProcessGlyphs(mode=mode_source)]
		glyphs_source = font_src.pGlyphs(glyphs_source_names)
		
		mode_layers_src = font_src.masters() if '*' in self.cmb_select_layer_A.currentText else [self.cmb_select_layer_A.currentText]
		mode_layers_dst = font_dst.masters() if '*' in self.cmb_select_layer_B.currentText else [self.cmb_select_layer_B.currentText]

		if len(mode_layers_src) != len(mode_layers_dst):
			output(3, app_name, 'Unequal Source to Destination layers count!')
			return

		do_update = False

		# - Process 
		for src_glyph in glyphs_source:
			if font_dst.hasGlyph(src_glyph.name):
				dst_glyph = font_dst.glyph(src_glyph.name, extend=eGlyph)
				process_layers = []

				# - Setup
				if len(mode_layers_src) > 1:
					# - Pair layer to layer if only present in both fonts
					for layer_name in mode_layers_src:
						if layer_name in mode_layers_dst:
							process_layers.append((layer_name, layer_name))
				else:
					process_layers = [(mode_layers_src[0], mode_layers_dst[0])]

				# - Process layers
				for layer_source, layer_destination in process_layers:
					# - Skip empty layers
					if src_glyph.layer(layer_source) is None or dst_glyph.layer(layer_destination) is None:	continue

					# - Setup
					if not mode_anchors: # Copy all anchors
						process_anchors_list = src_glyph.anchors(layer_source)
					else:
						process_anchors_list = [anchor for anchor in src_glyph.anchors(layer_source) if anchor.name in anchors_list]
					
					# - Process anchors
					for anchor in process_anchors_list:
						tmp_anchor = anchor.clone()
						
						# - Handle collision
						if mode_collide: # Rename mode
							dst_anchor_names = [a.name for a in dst_glyph.anchors(layer_destination)]
							
							if tmp_anchor.name in dst_anchor_names:
								if not mode_rename: # Rename incoming
									tmp_anchor.name += replace_suffix
								
								else: # Rename destination
									dst_anchor = dst_glyph.layer(layer_destination).findAnchor(tmp_anchor.name)
									dst_anchor.name += replace_suffix
						else: # Overwrite mode
							dst_anchor = dst_glyph.layer(layer_destination).findAnchor(tmp_anchor.name)
							dst_glyph.layer(layer_destination).removeAnchor(dst_anchor)

						# - Do Copy
						dst_glyph.layer(layer_destination).addAnchor(tmp_anchor)
						do_update = True

			else:
				output(2, app_name, 'Destination glyph not found! Font: {}; Glyph: {}'.format(self.cmb_select_font_B.currentText, src_glyph.name))

		# - Finish it
		if do_update:
			font_dst.updateObject(font_dst.fl, 'Copying anchors! Glyphs processed: %s' %len(glyphs_source))
		

	
# - RUN ------------------------------
dialog = dlg_copy_anchors()