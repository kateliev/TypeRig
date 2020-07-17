#FLM: TR: IMPEX
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | IMPEX', '0.5'

# - Dependencies -----------------
import os, json

import fontlab as fl6
import fontgate as fgt
from fontTools import afmLib

from PythonQt import QtCore
from typerig.gui import QtGui

from typerig.proxy import *

# - Configuration ------------------------------------------------------------
file_formats = {'afm':'Adobe Font Metrics (*.afm)',
				'svg': 'Scalable Vector Graphics (*.svg)'	
}

impex_actions = {
					'Adobe Font Metrics (AFM)':{
												'Import Metrics to Font layers':'action_empty',
												'Import Kerning to Font layers':'action_import_afm_kerning'

					},

					'Scalable Vector Graphics (SVG)':{	
												'Import SVG Graphics to Current Font Layer':'action_empty'

					}
}

# - Helpers ----------------------------------------------------------------------
def layout_clear_items(layout):
	'''Clear all widgets from a given layout.'''
	if layout is not None:
		while layout.count():
			item = layout.takeAt(0)
			widget = item.widget()
			
			if widget is not None:
				widget.setParent(None)
				 
			else:
				layout_clear_items(item.layout())

# - Main Import/Export tool -------------------------------------------------------
class TRImpEx(QtGui.QWidget):
	def __init__(self):
		super(TRImpEx, self).__init__()

		# - Interface
		# -- Layouts
		self.lay_base = QtGui.QGridLayout()
		self.plane_A = QtGui.QListWidget()
		self.plane_B = QtGui.QListWidget()
		self.plane_C = QtGui.QVBoxLayout()

		self.plane_A.setAlternatingRowColors(True)
		self.plane_B.setAlternatingRowColors(True)
		
		self.plane_A.addItems(sorted(impex_actions.keys()))
		self.plane_A.selectionModel().selectionChanged.connect(self.refresh_plane_B)
		self.plane_B.selectionModel().selectionChanged.connect(self.run_action)

		self.plane_C.addWidget(action_empty()) # Set empty widget at start

		# - Build
		self.lay_base.addWidget(QtGui.QLabel('Type:'), 		0,1)
		self.lay_base.addWidget(QtGui.QLabel('Action:'), 	0,2)
		self.lay_base.addWidget(QtGui.QLabel('Options:'), 	0,3)
		self.lay_base.addWidget(self.plane_A, 				1,1)
		self.lay_base.addWidget(self.plane_B, 				1,2)
		self.lay_base.addLayout(self.plane_C, 				1,3)
		
		self.lay_base.setColumnStretch(1,1)
		self.lay_base.setColumnStretch(2,1)
		self.lay_base.setColumnStretch(3,1)

		self.setLayout(self.lay_base)

	def refresh_plane_B(self):
		self.plane_B.blockSignals(True)
		self.plane_B.clear()
		self.plane_B.addItems(sorted(impex_actions[self.plane_A.currentItem().text()].keys()))
		self.plane_B.blockSignals(False)

	def run_action(self):
		# - Get action
		try:
			action_text = impex_actions[self.plane_A.currentItem().text()][self.plane_B.currentItem().text()]
		except KeyError:
			action_text = None

		if action_text is not None:
			# - Clear previous widget
			layout_clear_items(self.plane_C)
			
			# - Set new widget
			self.plane_C.addWidget(eval('%s()'%action_text))
			self.plane_C.addStretch()
		
	
# - Import/Export Actions ----------------------------------------------
class action_empty(QtGui.QWidget):
	# - Empty placeholder 
	def __init__(self):
		super(action_empty, self).__init__()
		
		# - Init
		self.active_font = None
		self.file_format = None

		# - Interface
		# ...

		# - Build
		lay_wgt = QtGui.QGridLayout()
		# ...
		self.setLayout(lay_wgt)
		
		print 'WARN:\t Action Not Implemented...'

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
		self.chk_kerning_clear = QtGui.QCheckBox('Clear Kerning')
		self.chk_kerning_expand = QtGui.QCheckBox('Expand Kerning')
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

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		layoutV = QtGui.QVBoxLayout()
		
		self.Importer = TRImpEx()
		layoutV.addWidget(self.Importer)
						
		# - Build ---------------------------
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 900, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

	test.show()