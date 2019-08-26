#FLM: Font: Instances
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Font Metrics', '0.11'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui
from typerig.proxy import pGlyph, pFont

# - Sub widgets ------------------------
class WAxisTable(QtGui.QTableWidget):
	def __init__(self, data):
		super(WAxisTable, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Set 
		self.setTable(data)		
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, reset=False):
		name_row, name_column = [], []
		self.blockSignals(True)

		# - Populate
		for n, layer in enumerate(sorted(data.keys())):
			name_row.append(layer)

			for m, key in enumerate(sorted(data[layer].keys())):
				name_column.append(key)
				newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
				self.setItem(n, m, newitem)
				
		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
			returnDict[self.verticalHeaderItem(row).text()] = {self.horizontalHeaderItem(col).text():int(self.item(row, col).text()) for col in range(self.columnCount)}

		return returnDict

	def markChange(self, item):
		item.setBackground(QtGui.QColor('powderblue'))

class WFontInstances(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WFontInstances, self).__init__()

		# - Init
		self.upperWidget = parentWidget

		self.gridPlane = QtGui.QGridLayout()
		self.axisPlane = QtGui.QVBoxLayout()

		# - Interface
		self.btn_axis_add = QtGui.QPushButton('New Axis Table')
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')
		self.btn_open = QtGui.QPushButton('Open')
		self.btn_save = QtGui.QPushButton('Save')

		self.btn_apply.setEnabled(False)
		self.btn_reset.setEnabled(False)
		self.btn_open.setEnabled(False)
		self.btn_save.setEnabled(False)

		self.btn_axis_add.clicked.connect(self.add_AxisTable)

		# - Build
		# -- Main Grid
		self.gridPlane.addWidget(self.btn_axis_add,		0, 0, 1, 3)
		self.gridPlane.addWidget(self.btn_save,			0, 3, 1, 3)
		self.gridPlane.addWidget(self.btn_open,			0, 6, 1, 3)
		self.gridPlane.addWidget(self.btn_reset,		0, 9, 1, 3)
		self.gridPlane.addWidget(self.btn_apply,		0, 12, 1, 3)
		self.gridPlane.addLayout(self.axisPlane,		1, 0, 5, 15)
		
		self.setLayout(self.gridPlane)

	def add_AxisTable(self):
		# - Init
		self.activeFont = pFont()
		self.metricData = {layer:{'Stem':0, 'Location':0} for layer in self.activeFont.masters()}
		
		self.tab_fontMetrics = WAxisTable(self.metricData)
		
		self.axisPlane.addWidget(self.tab_fontMetrics)
		

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		
		# - Build
		'''
		main = QtGui.QVBoxLayout()
		scroll = QtGui.QScrollArea()
		scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
		scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		scroll.setWidgetResizable(True)
		
		'''
		layoutV = QtGui.QVBoxLayout()
		self.font_instances = WFontInstances(self)
		layoutV.addWidget(self.font_instances)

						
		# - Build ---------------------------
		layoutV.addStretch()
		#scroll.setLayout(layoutV)
		#main.addWidget(scroll)
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 900, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()