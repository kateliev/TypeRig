#FLM: Delta Machine
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
from PythonQt import QtCore, QtGui

import os
from collections import OrderedDict
from typerig.gui import getProcessGlyphs
from typerig.proxy import pFont, pGlyph

# - Init --------------------------------
app_version = '0.01'
app_name = 'Delta Machine'

# - Style -------------------------
ss_Toolbox_none = """
QDoubleSpinBox { 
		background-color: transparent;
		border: 0px;
	}
QComboBox{ 
		background-color: transparent;
	} 
QComboBox QAbstractItemView {
		border: 0px;
	}
"""

# -- GUI related -------------------------
table_dict = {1:OrderedDict([	('Master Name', None), 
								('Source [A]', []), 
								('Source [B]', []),
								('V stem [A]', 1.),
								('V stem [B]', 2.),
								('H stem [A]', 1.),
								('H stem [B]', 2.),
								('tX stem', 0.),
								('tY stem', 0.),
								('Width', 0.),
								('Height', 0.),
								('Adj. X', 0.00),
								('Adj. Y', 0.00),
								('Note', ''),
							])}

# - Widgets --------------------------------
class WTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(WTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Set 
		self.setTable(data)		
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)
		#self.resizeColumnsToContents()
		#self.resizeRowsToContents()

	def setTable(self, data, data_check=[], reset=False):
		name_row, name_column = [], []
		self.blockSignals(True)

		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Populate
		for n, layer in enumerate(sorted(data.keys())):
			name_row.append(layer)

			for m, key in enumerate(data[layer].keys()):
				# -- Build name column
				name_column.append(key)
				
				# -- Selectively add data
				if m == 0:
					newitem = QtGui.QTableWidgetItem(str(data[layer][key]))

					if len(data_check) and data[layer][key] not in data_check:
						newitem.setBackground(QtGui.QColor('lightpink'))
						newitem.setFlags(QtCore.Qt.ItemIsUserCheckable)
						newitem.setCheckState(QtCore.Qt.Unchecked) 
						self.setItem(n, m, newitem)

					else: 					
						newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
						newitem.setCheckState(QtCore.Qt.Unchecked) 
						self.setItem(n, m, newitem)

				if 0 < m < 3:
					combo = QtGui.QComboBox()
					combo.addItems(data[layer][key])
					self.setCellWidget(n, m, combo)

				if 2 < m < len(data[layer].keys())-1:
					#newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
					#self.setItem(n, m, newitem)
					spin = QtGui.QDoubleSpinBox()
					
					if m <= 8: 
						spin.setSuffix(' u')
						spin.setMinimum(0.)
						spin.setMaximum(1000.)

					if 9 <= m <= 10: 
						spin.setSuffix(' %')
						spin.setMinimum(-500)
						spin.setMaximum(500.)

					if 10 < m:
						spin.setMinimum(0)
						spin.setMaximum(1)
						spin.setSingleStep(0.01)

					spin.setValue(data[layer][key])
					self.setCellWidget(n, m, spin)

				if  m == len(data[layer].keys()):
					newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
					self.setItem(n, m, newitem)

		
		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
			#returnDict[self.item(row, 0).text()] = (self.item(row, 1).checkState() == QtCore.Qt.Checked, self.item(row, 2).checkState() == QtCore.Qt.Checked)
			if self.item(row, 1).checkState() == QtCore.Qt.Checked:
				returnDict.setdefault('SRC',[]).append(self.item(row, 0).text())
			
			if self.item(row, 2).checkState() == QtCore.Qt.Checked:
				returnDict.setdefault('DST',[]).append(self.item(row, 0).text())

		return returnDict

	def markChange(self, item):
		item.setBackground(QtGui.QColor('powderblue'))

# - Dialogs --------------------------------
class dlg_DeltaMachine(QtGui.QDialog):
	def __init__(self):
		super(dlg_DeltaMachine, self).__init__()
	
		# - Init
		self.active_font = pFont()
		self.pMode = 0
		self.setStyleSheet(ss_Toolbox_none)
		
		# - Basic Widgets
		self.tab_masters = WTableView(table_dict)
		self.table_populate()

		self.btn_execute = QtGui.QPushButton('Execute transformation')
		self.btn_tableRefresh = QtGui.QPushButton('Refresh table')
		self.btn_getVstems = QtGui.QPushButton('Get V Stems')
		self.btn_getHstems = QtGui.QPushButton('Get H Stems')
		self.btn_getArrays = QtGui.QPushButton('Get Master Sources')
		self.btn_tableSave = QtGui.QPushButton('Save')
		self.btn_tableLoad = QtGui.QPushButton('Load')

		self.btn_tableRefresh.clicked.connect(self.table_populate)

		self.rad_glyph = QtGui.QRadioButton('Glyph')
		self.rad_window = QtGui.QRadioButton('Window')
		self.rad_selection = QtGui.QRadioButton('Selection')
		self.rad_font = QtGui.QRadioButton('Font')
		
		self.rad_glyph.setChecked(True)
		self.rad_glyph.setEnabled(True)
		self.rad_window.setEnabled(False)
		self.rad_selection.setEnabled(False)
		self.rad_font.setEnabled(False)

		self.rad_glyph.toggled.connect(self.refreshMode)
		self.rad_window.toggled.connect(self.refreshMode)
		self.rad_selection.toggled.connect(self.refreshMode)
		self.rad_font.toggled.connect(self.refreshMode)
				
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		
		layoutV.addWidget(self.btn_tableRefresh, 			1, 0, 1, 2)
		layoutV.addWidget(self.btn_getArrays, 				1, 2, 1, 4)
		layoutV.addWidget(self.btn_getVstems, 				1, 6, 1, 2)
		layoutV.addWidget(self.btn_getHstems, 				1, 8, 1, 2)
		layoutV.addWidget(self.btn_tableSave, 				1, 11, 1, 2)
		layoutV.addWidget(self.btn_tableLoad, 				1, 13, 1, 2)
		layoutV.addWidget(self.tab_masters, 				2, 0, 15, 15)
		layoutV.addWidget(QtGui.QLabel('Process Mode:'),	22, 0, 1, 2)
		layoutV.addWidget(self.rad_glyph, 					22, 2, 1, 2)
		layoutV.addWidget(self.rad_window, 					22, 4, 1, 2)
		layoutV.addWidget(self.rad_selection, 				22, 6, 1, 2)
		layoutV.addWidget(self.rad_font, 					22, 8, 1, 2)
		layoutV.addWidget(self.btn_execute, 				22, 10, 1,5)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 900, 700)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def refreshMode(self):
		if self.rad_glyph.isChecked(): self.pMode = 0
		if self.rad_window.isChecked(): self.pMode = 1
		if self.rad_selection.isChecked(): self.pMode = 2
		if self.rad_font.isChecked(): self.pMode = 3
	
	def table_populate(self):
		table_dict = {n:OrderedDict([	('Master Name', master), 
							('Source [A]', self.active_font.pMasters.names), 
							('Source [B]', self.active_font.pMasters.names),
							('V stem [A]', 1.),
							('V stem [B]', 2.),
							('H stem [A]', 1.),
							('H stem [B]', 2.),
							('tX stem', 0.),
							('tY stem', 0.),
							('Width', 0.),
							('Height', 0.),
							('Adj. X', 0.00),
							('Adj. Y', 0.00),
							('Note', ''),
						])

						for n, master in enumerate(self.active_font.pMasters.names)}

		self.tab_masters.setTable(table_dict)
		#self.tab_masters.resizeColumnsToContents()		

	def execute_table(self):
		pass


# - RUN ------------------------------
dialog = dlg_DeltaMachine()