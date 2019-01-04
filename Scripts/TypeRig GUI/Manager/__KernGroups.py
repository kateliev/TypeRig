#FLM: Font: Kern Groups
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Kern Groups', '0.1'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pGlyph, pFont
from typerig.gui import trTableView

# - Custom classes -----------------------------------------------------------
class GroupTableView(trTableView):
	def setTable(self, data, indexColCheckable=None):
		name_row, name_column = [], ['Class Name', 'Class Type', 'Class Memebers']
		self.blockSignals(True)

		self.setColumnCount(len(name_column))
		self.setRowCount(len(data.keys()))

		# - Populate
		for row, key in enumerate(data.keys()):
			name_row.append(key)
								
			item_groupName = QtGui.QTableWidgetItem(str(key))
			item_groupPos = QtGui.QTableWidgetItem(str(data[key][1]))
			item_groupMem = QtGui.QTableWidgetItem(', '.join(data[key][0]))
														
			item_groupName.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
			item_groupName.setCheckState(QtCore.Qt.Unchecked) 

			self.setItem(row, 0, item_groupName)
			self.setItem(row, 1, item_groupPos)
			self.setItem(row, 2, item_groupMem)

		self.setHorizontalHeaderLabels(name_column)
		self.blockSignals(False)

	def getTable(self):
		pass


# - Font Group Kerning -------------------------------------------------------
class WKernGroups(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WKernGroups, self).__init__()

		# - Init
		self.grid = QtGui.QGridLayout()
		self.upperWidget = parentWidget
		self.activeFont = pFont()
		temp_krnGrp = self.activeFont.fl.kerning().groups
		self.kernData = {key: (list(set(temp_krnGrp[key][0])), temp_krnGrp[key][1]) for key in temp_krnGrp.keys()}

		# - Interface
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')
		self.btn_open = QtGui.QPushButton('Open')
		self.btn_save = QtGui.QPushButton('Save')

		self.btn_apply.clicked.connect(self.applyChanges)
		self.btn_reset.clicked.connect(self.resetChanges)
		self.btn_save.clicked.connect(self.exportGroups)
		self.btn_open.clicked.connect(self.importGroups)

		self.tab_fontMetrics = GroupTableView(self.kernData)

		# - Build
		lbl_name = QtGui.QLabel('Font Metrics (All Masters)')
		lbl_name.setMaximumHeight(20)
		self.grid.addWidget(lbl_name,		 		0, 0, 1, 24)
		self.grid.addWidget(self.tab_fontMetrics,	1, 0, 5, 21)
		self.grid.addWidget(self.btn_save,			1, 21, 1, 3)
		self.grid.addWidget(self.btn_open,			2, 21, 1, 3)
		self.grid.addWidget(self.btn_reset,			4, 21, 1, 3)
		self.grid.addWidget(self.btn_apply,			5, 21, 1, 3)

		for i in range(1,6):
			self.grid.setRowStretch(i,2)

		self.setLayout(self.grid)
	
	def applyChanges(self):
		pass

	def resetChanges(self):
		pass

	def exportGroups(self):
		pass

	def importGroups(self):
		pass

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		
		layoutV = QtGui.QVBoxLayout()
		self.kernGroups = WKernGroups(self)
		layoutV.addWidget(self.kernGroups)

						
		# - Build ---------------------------
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 900, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()