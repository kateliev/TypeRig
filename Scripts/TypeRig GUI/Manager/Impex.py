#FLM: TR: IMPEX
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
from __future__ import absolute_import
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Import & Export', '0.5'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui

from . import ImpexActions

# - Configuration ------------------------------------------------------------
file_formats = {'afm':'Adobe Font Metrics (*.afm)',
				'svg': 'Scalable Vector Graphics (*.svg)'	
}

impex_actions_db = {
					'Adobe Font Metrics (AFM)':{
												'Import Metrics to Font layers':ImpexActions.action_empty(),
												'Import Kerning to Font layers':ImpexActions.afm.action_import_afm_kerning(),

					},

					'Scalable Vector Graphics (SVG)':{	
												'Import SVG Graphics to Current Font Layer':ImpexActions.action_empty()

					},

					'Comma Separated Values (CSV)':{	
												'Export Components':ImpexActions.action_empty(),
												'Export Anchors':ImpexActions.action_empty(),
												'Export Kerning':ImpexActions.action_empty(),
												'Export Metrics':ImpexActions.action_empty(),
												'Import Components':ImpexActions.action_empty(),
												'Import Anchors':ImpexActions.action_empty(),
												'Import Kerning':ImpexActions.action_empty(),
												'Import Metrics':ImpexActions.action_empty()

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
		
		self.plane_A.addItems(sorted(impex_actions_db.keys()))
		self.plane_A.selectionModel().selectionChanged.connect(self.refresh_plane_B)
		self.plane_B.selectionModel().selectionChanged.connect(self.run_action)

		self.plane_C.addWidget(ImpexActions.action_empty()) # Set empty widget at start

		# - Build
		self.lay_base.addWidget(QtGui.QLabel('Import/Export type:'), 		0,1)
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
		self.plane_B.addItems(sorted(impex_actions_db[self.plane_A.currentItem().text()].keys()))
		self.plane_B.blockSignals(False)

	def run_action(self):
		# - Get action
		try:
			action_widget = impex_actions_db[self.plane_A.currentItem().text()][self.plane_B.currentItem().text()]
		except KeyError:
			action_widget = None

		if action_widget is not None:
			# - Clear previous widget
			layout_clear_items(self.plane_C)
			
			# - Set new widget
			self.plane_C.addWidget(action_widget)
			self.plane_C.addStretch()
		
	
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