#FLM: TR: IMPEX | AFM
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json

import fontlab as fl6
import fontgate as fgt
from fontTools import afmLib

from PythonQt import QtCore
from typerig.gui import QtGui

from typerig.proxy import pFont

# - Init ---------------------------------------------------
file_formats = {'afm':'Adobe Font Metrics (*.afm)',
				'svg': 'Scalable Vector Graphics (*.svg)'
}

# - Action Objects ---------------
class action_import_afm_kerning(QtGui.QWidget):
	def __init__(self):
		super(action_import_afm_kerning, self).__init__()
		
		# - Init
		self.active_font = None
		self.file_format = 'afm'

		# - Interface
		self.btn_file_open = QtGui.QPushButton('Open')
		self.btn_file_open.clicked.connect(self.afm_import_kerning)

		self.chk_name_replace = QtGui.QCheckBox('Strip Filename')
		self.chk_kerning_clear = QtGui.QCheckBox('Clear existing kerning')
		self.chk_kerning_expand = QtGui.QCheckBox('Expand to class kerning after import')
		self.chk_name_replace.setChecked(True)
		self.chk_kerning_clear.setChecked(True)
		self.chk_kerning_expand.setChecked(True)
		
		self.edt_name_replace = QtGui.QLineEdit()
		self.edt_name_replace.setPlaceholderText('Drop String')

		# - Build
		lay_wgt = QtGui.QGridLayout()
		lay_wgt.addWidget(QtGui.QLabel('(AFM) Kerning Import:'),	0, 0, 1, 10)
		lay_wgt.addWidget(self.chk_name_replace,	1, 0, 1, 2)
		lay_wgt.addWidget(self.edt_name_replace,	1, 2, 1, 8)
		lay_wgt.addWidget(self.chk_kerning_clear,	2, 0, 1, 10)
		lay_wgt.addWidget(self.chk_kerning_expand,	3, 0, 1, 10)
		lay_wgt.addWidget(self.btn_file_open,		4, 0, 1, 10)
		
		self.setLayout(lay_wgt)

	def afm_import_kerning(self):
		# - Init
		kerning_changed = False
		kerning_count = 0
		active_font = pFont()
		root_dir = active_font.fg.path
		afm_loadpath = QtGui.QFileDialog.getOpenFileNames(None, 'Import Artwork', root_dir, file_formats[self.file_format])
		font_masters = active_font.masters()
		no_whitespace_masters = {master.replace(' ','') : master for master in font_masters} #Whitespace removed from master names

		for work_file in afm_loadpath:
			current_afm = None
			layer_name = os.path.splitext(os.path.split(work_file)[1])[0]

			if self.chk_name_replace.isChecked() and len(self.edt_name_replace.text):
				layer_name = layer_name.replace(self.edt_name_replace.text,'')

			if layer_name in font_masters or layer_name in no_whitespace_masters:
				# - Load
				current_afm = afmLib.AFM(work_file)
				kerning_afm = current_afm._kerning.items()

				# - Whitespace fix				
				if layer_name in no_whitespace_masters:
					layer_name = no_whitespace_masters[layer_name]

				kerning_current = active_font.kerning(layer_name)
				
				# - Process
				if len(kerning_afm):
					if self.chk_kerning_clear.isChecked():
						kerning_current.clear()

					kerning_changed = True
					kerning_count += 1
					kerning_current.setPlainPairs(kerning_afm)
					print 'DONE:\t Layer: %s\t Import AFM plain pairs kerning from: %s' %(layer_name, work_file)

		if kerning_changed:
			print 'DONE:\t AFM Files processed for kerning data: %s' %(kerning_count)			
			active_font.update()