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

column_names = ('Master Name',
				'Source [A]', 
				'Source [B]', 
				'V stem [A]',
				'V stem [B]',
				'H stem [A]',
				'H stem [B]', 
				'tX stem',
				'tY stem', 
				'Width', 
				'Height',
				'Adj. X', 
				'Adj. Y', 
				'Active') 

column_init = (None,[],[], 1., 2., 1., 2., 0., 0., 0., 0., 0.00, 0.00, False)
table_dict = {1:OrderedDict(zip(column_names, column_init))}

fileFormats = ['TypeRig Deltas (*.json)']

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

				if 2 < m < len(data[layer].keys()):
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

					if 10 <= m:
						spin.setMinimum(0)
						spin.setMaximum(1)
						spin.setSingleStep(0.01)

					spin.setValue(data[layer][key])
					self.setCellWidget(n, m, spin)

		
		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self, checked_only=True):
		returnDict = {}
		for row in range(self.rowCount):
			#if self.item(row, 1).checkState() == QtCore.Qt.Checked:
			returnDict[row] = [	self.item(row, 0).text(), 
								self.cellWidget(row, 1).currentText,
								self.cellWidget(row, 2).currentText,
								self.cellWidget(row, 3).value,
								self.cellWidget(row, 4).value,
								self.cellWidget(row, 5).value,
								self.cellWidget(row, 6).value,
								self.cellWidget(row, 7).value,
								self.cellWidget(row, 8).value, 
								self.cellWidget(row, 9).value, 
								self.cellWidget(row, 10).value, 
								self.cellWidget(row, 11).value, 
								self.cellWidget(row, 12).value,
								self.item(row, 0).checkState() == QtCore.Qt.Checked]
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
		self.btn_execute.clicked.connect(self.execute_table)
		self.btn_tableSave.clicked.connect(self.file_save_deltas) 
		self.btn_tableLoad.clicked.connect(self.file_load_deltas) 

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

	# - Functions ------------------------------------------------------------
	def file_save_deltas(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save Deltas to file', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				if exportRaw:
					json.dump(self.tab_masters.getTable(), exportFile)
				
				print 'SAVE:\t Font:%s; Deltas saved to: %s.' %(self.active_font.name, fname)

	def file_load_deltas(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upper_widget, 'Load Deltas from file', fontPath, fileFormats)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
								
				table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in enumerate(imported_data)}
				self.tab_masters.setTable(table_dict)
				print 'LOAD:\t Font:%s; Deltas loaded from: %s.' %(self.active_font.name, fname)

	def refreshMode(self):
		if self.rad_glyph.isChecked(): self.pMode = 0
		if self.rad_window.isChecked(): self.pMode = 1
		if self.rad_selection.isChecked(): self.pMode = 2
		if self.rad_font.isChecked(): self.pMode = 3
	
	def table_populate(self):
		init_data = [[master, self.active_font.pMasters.names, self.active_font.pMasters.names, 1., 2., 1., 2., 0., 0.,0., 0., 0.00, 0.00] for master in self.active_font.pMasters.names]
	 	table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in enumerate(init_data)}
		self.tab_masters.setTable(table_dict)
		
		#self.tab_masters.resizeColumnsToContents()		

	def execute_table(self):
		print self.tab_masters.getTable()[0]


# - RUN ------------------------------
dialog = dlg_DeltaMachine()