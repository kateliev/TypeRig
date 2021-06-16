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
from typerig.proxy.fl.gui import QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.kern import pKerning
from typerig.core.func.math import round2base

# - Init --------------------------
app_name, app_version = 'TypeRig | AFM Import & Export', '1.0'
file_formats = {'afm':'Adobe Font Metrics (*.afm)'}

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

		self.chk_name_replace = QtGui.QCheckBox('Strip Filename:')
		self.chk_kerning_clear = QtGui.QCheckBox('Clear existing kerning')
		self.chk_kerning_extend = QtGui.QCheckBox('Expand to class kerning')
		self.chk_kerning_round = QtGui.QCheckBox('Round kerning:')
		self.chk_kerning_posit = QtGui.QCheckBox('Drop Positive pairs above:')
		self.chk_kerning_negat = QtGui.QCheckBox('Drop Negative pairs below:')

		self.spn_kerning_rbase = QtGui.QSpinBox()
		self.spn_kerning_posit = QtGui.QSpinBox()
		self.spn_kerning_negat = QtGui.QSpinBox()

		self.spn_kerning_rbase.setValue(5)
		self.spn_kerning_rbase.setMaximum(10)
		self.spn_kerning_posit.setMaximum(1000)
		self.spn_kerning_negat.setMaximum(1000)

		self.spn_kerning_rbase.setSuffix(' u')
		self.spn_kerning_posit.setSuffix(' u')
		self.spn_kerning_negat.setSuffix(' u')

		self.chk_name_replace.setChecked(True)
		self.chk_kerning_clear.setChecked(True)
		self.chk_kerning_extend.setChecked(False)
		self.chk_kerning_round.setChecked(False)
		
		self.edt_name_replace = QtGui.QLineEdit()
		self.edt_name_replace.setPlaceholderText('Drop String')

		# - Build
		lay_wgt = QtGui.QGridLayout()
		lay_wgt.addWidget(QtGui.QLabel('(AFM) Kerning Import:'),	0, 0, 1, 10)
		lay_wgt.addWidget(self.chk_name_replace,	1, 0, 1, 2)
		lay_wgt.addWidget(self.edt_name_replace,	1, 2, 1, 8)
		lay_wgt.addWidget(self.chk_kerning_round,	2, 0, 1, 5)
		lay_wgt.addWidget(self.spn_kerning_rbase,	2, 5, 1, 5)
		lay_wgt.addWidget(self.chk_kerning_posit,	3, 0, 1, 5)
		lay_wgt.addWidget(self.spn_kerning_posit,	3, 5, 1, 5)
		lay_wgt.addWidget(self.chk_kerning_negat,	4, 0, 1, 5)
		lay_wgt.addWidget(self.spn_kerning_negat,	4, 5, 1, 5)
		lay_wgt.addWidget(self.chk_kerning_clear,	5, 0, 1, 10)
		lay_wgt.addWidget(self.chk_kerning_extend,	6, 0, 1, 10)
		lay_wgt.addWidget(self.btn_file_open,		7, 0, 1, 10)
		
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

				kerning_current = pKerning(active_font.kerning(layer_name))
				
				# - Process
				if len(kerning_afm):
					# - Init
					if self.chk_kerning_clear.isChecked():
						kerning_current.clear()

					# - Modify
					new_kerning_afm = []

					if any([self.chk_kerning_round.isChecked(), self.chk_kerning_negat.isChecked(), self.chk_kerning_posit.isChecked()]):
						for pair, value in kerning_afm:
							if self.chk_kerning_negat.isChecked() and value <= self.spn_kerning_negat.value:
								continue

							if self.chk_kerning_posit.isChecked() and value >= self.spn_kerning_posit.value:
								continue

							if self.chk_kerning_round.isChecked():
								value = round2base(value, self.spn_kerning_rbase.value)

							new_kerning_afm.append((pair, value))

					else:
						new_kerning_afm = kerning_afm

					# - Set
					kerning_changed = True
					kerning_count += 1
					if self.chk_kerning_extend.isChecked():
						kerning_current.setPairs(new_kerning_afm, True)
					else:
						kerning_current.fg.setPlainPairs(new_kerning_afm)
					print 'DONE:\t Layer: %s\t Import AFM plain pairs kerning from: %s' %(layer_name, work_file)

		if kerning_changed:
			print 'DONE:\t AFM Files processed for kerning data: %s' %(kerning_count)			
			active_font.update()