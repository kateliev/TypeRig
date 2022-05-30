#FLM: TypeRig: Rename Anchors
# ----------------------------------------
# (C) Vassil Kateliev, 2022  (http://www.kateliev.com)
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
app_name, app_version = 'TR | Rename Anchors', '1.2'
str_all_masters = '*All masters*'

# - Interface -----------------------------
class dlg_copy_anchors(QtGui.QDialog):
	def __init__(self):
		super(dlg_copy_anchors, self).__init__()
	
		# - Init
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]

		# - Group box
		self.box_src = QtGui.QGroupBox('Font')
		self.box_dst = QtGui.QGroupBox('Operation')

		# - Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_A.addItems(self.font_files)

		self.cmb_select_layer_A = QtGui.QComboBox()
		self.cmb_select_layer_A.addItems([str_all_masters])
		
		# - Radios
		self.rad_group_source = QtGui.QButtonGroup()

		self.rad_source_font = QtGui.QRadioButton('All glyphs')
		self.rad_source_sellected = QtGui.QRadioButton('Selected glyphs')
		
		self.rad_source_font.setChecked(True)

		self.rad_group_source.addButton(self.rad_source_font, 1)
		self.rad_group_source.addButton(self.rad_source_sellected, 2)

		# - Edit
		self.edt_anchor_find = QtGui.QLineEdit()
		self.edt_anchor_find.setPlaceholderText('Anchor name: top, _bottom and etc.')
		self.edt_anchor_replace = QtGui.QLineEdit()
		self.edt_anchor_replace.setPlaceholderText('Anchor name: top, _bottom and etc.')

		# - Buttons 
		self.btn_cmb_layer_A_refresh = QtGui.QPushButton('<<')
		self.btn_rename_anchors = QtGui.QPushButton('Rename Anchors')

		self.btn_cmb_layer_A_refresh.setToolTip('Refresh layers list')
		self.btn_cmb_layer_A_refresh.setMaximumWidth(30)
		
		self.btn_rename_anchors.clicked.connect(lambda: self.action_rename_anchors())
		self.btn_cmb_layer_A_refresh.clicked.connect(lambda: self.refresh_layers_list())
				
		# - Build layouts 
		# -- Soource 
		layout_src = QtGui.QGridLayout() 
		#layout_src.addWidget(QtGui.QLabel('Source font:'), 			1, 0, 1, 6)
		layout_src.addWidget(self.cmb_select_font_A,	 			2, 0, 1, 7)
		layout_src.addWidget(QtGui.QLabel('Layer:'), 				3, 0, 1, 1)
		layout_src.addWidget(self.cmb_select_layer_A, 				3, 1, 1, 5)
		layout_src.addWidget(self.btn_cmb_layer_A_refresh,			3, 6, 1, 1)
		layout_src.addWidget(QtGui.QLabel('Affect:'), 				4, 0, 1, 1)
		layout_src.addWidget(self.rad_source_font,  				4, 1, 1, 3)
		layout_src.addWidget(self.rad_source_sellected, 			4, 4, 1, 3)
		self.box_src.setLayout(layout_src)
		
		# -- Destination 
		layout_dst = QtGui.QGridLayout() 
		layout_dst.addWidget(QtGui.QLabel('Find:'), 				1, 0, 1, 1)
		layout_dst.addWidget(self.edt_anchor_find, 					1, 1, 1, 6)
		layout_dst.addWidget(QtGui.QLabel('Replace:'), 				3, 0, 1, 1)
		layout_dst.addWidget(self.edt_anchor_replace, 				3, 1, 1, 6)
		self.box_dst.setLayout(layout_dst)

		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_src)
		layout_main.addWidget(self.box_dst)
		layout_main.addStretch()
		layout_main.addWidget(self.btn_rename_anchors)


		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 300)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	# - Functions --------------------------------
	def refresh_layers_list(self):
		tmp_font = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)])
		self.cmb_select_layer_A.clear()
		self.cmb_select_layer_A.addItems([str_all_masters] + tmp_font.masters())
		output(0, app_name, 'Layers list updated!')

	def action_rename_anchors(self):
		# - Init
		font_src_fl = self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]
		font_src = pFont(font_src_fl)
		
		mode_layers_src = font_src.masters() if '*' in self.cmb_select_layer_A.currentText else [self.cmb_select_layer_A.currentText]
		mode_source = 3 if self.rad_source_font.isChecked() else 2  # if 3 for Font, 2 for selected glyphs
		
		anchor_name_find = str(self.edt_anchor_find.text)
		anchor_name_replace = str(self.edt_anchor_replace.text)
		
		process_glyphs = set()

		for glyph in getProcessGlyphs(mode=mode_source):
			try:
				for layer_name in mode_layers_src:
					for anchor in glyph.anchors(layer_name):
						if anchor.name == anchor_name_find:
							anchor.name = anchor_name_replace
							process_glyphs.add(glyph.name)
			
			except AttributeError:
				pass
				
		# - Finish it
		if process_glyphs > 0:
			font_src.updateObject(font_src.fl, 'Renaming anchors\tFind: %s; Replace: %s\tGlyphs processed: %s' %(anchor_name_find, anchor_name_replace, len(process_glyphs)))
		

	
# - RUN ------------------------------
dialog = dlg_copy_anchors()