#FLM: TR: Delta Machine
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import print_function
import os, json
from math import radians
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.core.func.math import linInterp, ratfrac
from typerig.core.func import transform
from typerig.core.objects.array import PointArray

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRSliderCtrl, TRMsgSimple


# - Init --------------------------------
app_version = '1.15'
app_name = 'TypeRig | Delta Machine'

ss_controls = """
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

QTableView::item:selected

{		color:black;
		background-color:yellow;
}

"""

column_names = ('Master Name',
				'Source [A]', 
				'Source [B]', 
				'V-stem [A]',
				'V-stem [B]',
				'H-stem [A]',
				'H-stem [B]', 
				'V[dX]',
				'H[dY]', 
				'Width', 
				'Height',
				'Adj. X', 
				'Adj. Y', 
				'Active') 

column_init = (None,[],[], 1., 2., 1., 2., 0., 0., 0., 0., 0.00, 0.00, False)
table_dict = {1:OrderedDict(zip(column_names, column_init))}

fileFormats = 'TypeRig Deltas (*.json);;'

# - Helpers --------------------------------
global probe_stem
global probe_ratio

'''
Example usage of probe_stem:
Assignment: Desired stem weight = lowercase + 15% of the difference between lowercase and caps
Solution:
	py> uc = _get_stem() #/H get vertical stems
	py> lc = _get_stem() #/n get vertical stems
	py> probe_stem = lc + (uc-lc)*0.15 
	py> probe_stem = probe_stem.round_values()
'''

class probe_dict(dict):
	'''A dict extension that allows for simple math. For stem measuring purpouses and more.'''
	def __add__(self, other):
		result = self.__class__()

		for key, value in self.items():
			if isinstance(other, self.__class__):
				if other.has_key(key):
					result[key] = self[key] + other[key]

			elif isinstance(other, (float, int)):
				result[key] = self[key] + other

		return result
		
	def __sub__(self, other):
		result = self.__class__()

		for key, value in self.items():
			if isinstance(other, self.__class__):
				if other.has_key(key):
					result[key] = self[key] - other[key]

			elif isinstance(other, (float, int)):
				result[key] = self[key] - other

		return result

	def __mul__(self, other):
		result = self.__class__()

		for key, value in self.items():
			if isinstance(other, self.__class__):
				if other.has_key(key):
					result[key] = self[key] * other[key]

			elif isinstance(other, (float, int)):
				result[key] = self[key] * other

		return result

	def __div__(self, other):
		result = self.__class__()

		for key, value in self.items():
			if isinstance(other, self.__class__):
				if other.has_key(key):
					result[key] = self[key] / other[key]

			elif isinstance(other, (float, int)):
				result[key] = self[key] / other

		return result

	def round_values(self):
		result = self.__class__()

		for key, value in self.items():
			result[key] = round(self[key])

		return result

def _get_stem(vertical=True, glyphName=None):
	'''Get the stem measurement at glyph'''
	# - Init
	font = pFont()
	glyph = eGlyph() if glyphName is None else font.glyph(glyphName)
	stem_dict = probe_dict()

	for layer in font.masters():
		selection = glyph.selectedNodes(layer)
		stem_dict[layer] = (abs(selection[0].x - selection[-1].x), abs(selection[0].y - selection[-1].y))[not vertical]
		
	return stem_dict


# - Widgets --------------------------------
class WTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(WTableView, self).__init__()
		
		# - Init
		self.setStyleSheet(ss_controls)
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))
	
		# - Set 
		self.setTable(data)		
		#self.itemChanged.connect(self.markChange)
	
		# - Styling
		self.horizontalHeader().setStretchLastSection(False)
		self.setAlternatingRowColors(True)
		self.setShowGrid(True)
		#self.resizeColumnsToContents()
		#self.resizeRowsToContents()

	def setTable(self, data, reset=False):
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
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
					newitem.setCheckState(QtCore.Qt.Unchecked) 
					self.setItem(n, m, newitem)

				if 0 < m < 3:
					combo = QtGui.QComboBox()

					if m%2:
						combo.setStyleSheet('QComboBox { background-color: rgba(255, 0, 0, 15); }')
					else:
						combo.setStyleSheet('QComboBox { background-color: rgba(0, 255, 0, 15); }')

					combo.addItems(data[layer][key])
					self.setCellWidget(n, m, combo)

				if 2 < m < len(data[layer].keys()):
					spin = QtGui.QDoubleSpinBox()
					
					if m <= 6: 
						spin.setSuffix(' u')

						if m%2:
							spin.setStyleSheet('QDoubleSpinBox { background-color: rgba(255, 0, 0, 15); }')
						else:
							spin.setStyleSheet('QDoubleSpinBox { background-color: rgba(0, 255, 0, 15); }')

						spin.setMinimum(0.)
						spin.setMaximum(1000.)

					if 7 <= m <= 8: 
						spin.setSuffix(' u')

						if m%2:
							spin.setStyleSheet('QDoubleSpinBox { background-color: rgba(255, 200, 0, 25); }')
						else:
							spin.setStyleSheet('QDoubleSpinBox { background-color: rgba(255, 200, 0, 25); }')

						spin.setMinimum(0.)
						spin.setMaximum(1000.)

					if 9 <= m <= 10: 
						spin.setSuffix(' %')
						spin.setStyleSheet('QDoubleSpinBox { background-color: rgba(0, 0, 255, 15); }')
						spin.setMinimum(0.)
						spin.setMaximum(500.)

					if 10 < m:
						spin.setMinimum(0)
						spin.setMaximum(1)
						spin.setSingleStep(0.01)

					spin.setValue(data[layer][key])
					self.setCellWidget(n, m, spin)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def updateTable(self, data):
		name_row, name_column = [], []
		self.blockSignals(True)

		# - Populate
		for n, layer in enumerate(sorted(data.keys())):
			for m, key in enumerate(data[layer].keys()):
								
				# -- Selectively update data
				if m == 0:
					self.item(n,m).setText(str(data[layer][key]))
					self.item(n,m).setCheckState(QtCore.Qt.Unchecked) 
					
				if 0 < m < 3:
					index = self.cellWidget(n, m).findText(str(data[layer][key]))
					self.cellWidget(n, m).setCurrentIndex(index)

				if 2 < m < len(data[layer].keys())-1:
					self.cellWidget(n, m).setValue(data[layer][key])

		self.blockSignals(False)

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
			returnDict[row] = self.getRow(row)
		return returnDict

	def getRow(self, row=None):
		if row is None: row = self.currentRow()
		
		data_row = [self.item(row, 0).text(), 
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
		
		return data_row

	def lockTable(self):
		for col in range(self.columnCount):
			for row in range(self.rowCount):
				try:
					self.cellWidget(row, col).setEnabled(not self.cellWidget(row, col).isEnabled())
				except AttributeError:
					pass


	def markChange(self, item):
		item.setBackground(QtGui.QColor('powderblue'))


# - Dialogs --------------------------------
class dlg_DeltaMachine(QtGui.QDialog):
	def __init__(self):
		super(dlg_DeltaMachine, self).__init__()
	
		# - Init
		#self.setStyleSheet(ss_controls)
		
		self.pMode = 0
		self.active_font = pFont()
		#self.data_glyphs = getProcessGlyphs(self.pMode)
		self.data_PointArrays = {}
		self.data_stems = {}
		self.ratio_source = {}
		self.ratio_target = {}
		self.italic_angle = 0
		
		# - Basic Widgets
		# -- Master table
		self.tab_masters = WTableView(table_dict)
		self.table_populate()
		self.tab_masters.selectionModel().selectionChanged.connect(self.set_sliders)
		
		# -- Combos
		self.cmb_infoArrays = QtGui.QComboBox()

		# -- Buttons
		self.btn_execute = QtGui.QPushButton('Execute transformation')
		self.btn_tableRefresh = QtGui.QPushButton('Reset')
		self.chk_tableLock = QtGui.QPushButton('Lock')
		self.btn_tableSave = QtGui.QPushButton('Save')
		self.btn_tableLoad = QtGui.QPushButton('Load')
		self.btn_getVstems = QtGui.QPushButton('Get V-stems')
		self.btn_getHstems = QtGui.QPushButton('Get H-stems')
		self.btn_tableCheck = QtGui.QPushButton('Check All')
		self.btn_resetT = QtGui.QPushButton('Reset dX dY')
		self.btn_getTx = QtGui.QPushButton('Get V[dX]')
		self.btn_getTy = QtGui.QPushButton('Get H[dY]')
		self.btn_getArrays = QtGui.QPushButton('Get Master Sources')

		self.btn_getPart = QtGui.QPushButton('Get Part')
		self.btn_getWhole = QtGui.QPushButton('Get Whole')
		self.btn_pushWidthPW = QtGui.QPushButton('Eval Width')
		self.btn_pushHeightPW = QtGui.QPushButton('Eval Height')
		self.btn_pushWidth = QtGui.QPushButton('Set Width Ratio')
		self.btn_pushHeight = QtGui.QPushButton('Set Height Ratio')
		
		self.btn_tableCheck.clicked.connect(self.table_check_all)
		self.btn_tableRefresh.clicked.connect(self.table_populate)
		self.btn_tableSave.clicked.connect(self.file_save_deltas) 
		self.btn_tableLoad.clicked.connect(self.file_load_deltas) 
		self.btn_execute.clicked.connect(self.table_execute)
		self.chk_tableLock.clicked.connect(lambda: self.tab_masters.lockTable())

		self.btn_getPart.clicked.connect(lambda: self.get_ratio(True))
		self.btn_getWhole.clicked.connect(lambda: self.get_ratio(False))
		self.btn_pushWidthPW.clicked.connect(lambda: self.push_ratio(False, True))
		self.btn_pushHeightPW.clicked.connect(lambda: self.push_ratio(True, True))
		self.btn_pushWidth.clicked.connect(lambda: self.push_ratio(False, False))
		self.btn_pushHeight.clicked.connect(lambda: self.push_ratio(True, False))

		self.btn_getArrays.clicked.connect(lambda: self.get_PointArrays(None)) 
		self.btn_getVstems.clicked.connect(lambda: self.get_Stems(True))
		self.btn_getHstems.clicked.connect(lambda: self.get_Stems(False))
		self.btn_getTx.clicked.connect(lambda: self.get_Stems(True, False))
		self.btn_getTy.clicked.connect(lambda: self.get_Stems(False, False))

		# -- Check buttons
		self.chk_italic = QtGui.QPushButton('Italic')
		self.chk_single = QtGui.QPushButton('Anisotropic')
		self.chk_preview = QtGui.QPushButton('Live Preview')
		self.chk_boundry = QtGui.QPushButton('Fix Boundry')
		self.chk_single.setToolTip('Active: Use X and Y to control interpolation.')
		self.chk_tableLock.setCheckable(True)
		self.chk_single.setCheckable(True)
		self.chk_italic.setCheckable(True)
		self.chk_preview.setCheckable(True)
		self.chk_boundry.setCheckable(True)
		self.chk_single.setChecked(False)
		self.chk_italic.setChecked(False)
		self.chk_preview.setChecked(False)
		self.chk_boundry.setChecked(True)

		# -- Radio
		self.rad_glyph = QtGui.QRadioButton('Glyph')
		self.rad_window = QtGui.QRadioButton('Window')
		self.rad_selection = QtGui.QRadioButton('Selection')
		self.rad_font = QtGui.QRadioButton('Font')
		
		self.rad_glyph.setChecked(True)
		self.rad_glyph.setEnabled(True)
		self.rad_window.setEnabled(True)
		self.rad_selection.setEnabled(True)
		self.rad_font.setEnabled(True)

		self.rad_glyph.toggled.connect(self.table_refresh)
		self.rad_window.toggled.connect(self.table_refresh)
		self.rad_selection.toggled.connect(self.table_refresh)
		self.rad_font.toggled.connect(self.table_refresh)

		# -- Sliders
		self.mixer_dx = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dy = TRSliderCtrl('1', '1000', '0', 1)
		self.scaler_dx = TRSliderCtrl('1', '200', '100', 1)
		self.scaler_dy = TRSliderCtrl('1', '200', '100', 1)

		self.mixer_dx.sld_axis.valueChanged.connect(lambda: self.process_scale(eGlyph(), anisotropic=self.chk_single.isChecked(), live_update=self.chk_preview.isChecked()))		
		self.mixer_dy.sld_axis.valueChanged.connect(lambda: self.process_scale(eGlyph(), anisotropic=self.chk_single.isChecked(), live_update=self.chk_preview.isChecked()))		
		self.scaler_dx.sld_axis.valueChanged.connect(lambda: self.process_scale(eGlyph(), anisotropic=self.chk_single.isChecked(), live_update=self.chk_preview.isChecked()))		
		self.scaler_dy.sld_axis.valueChanged.connect(lambda: self.process_scale(eGlyph(), anisotropic=self.chk_single.isChecked(), live_update=self.chk_preview.isChecked()))		
		
		# - Build layout
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Preferences:'), 	0, 0, 1, 1)
		layoutV.addWidget(self.btn_tableCheck, 				0, 1, 1, 2)
		layoutV.addWidget(self.chk_tableLock, 				0, 3, 1, 2)
		layoutV.addWidget(self.btn_tableSave, 				0, 5, 1, 1)
		layoutV.addWidget(self.btn_tableLoad, 				0, 6, 1, 2)
		layoutV.addWidget(self.btn_tableRefresh, 			0, 8, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Source:'),			0, 10, 1, 1, QtCore.Qt.AlignRight)
		layoutV.addWidget(self.btn_getVstems, 				0, 11, 1, 2)
		layoutV.addWidget(self.btn_getHstems, 				0, 13, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Ratio BBOX:'),		0, 15, 1, 1, QtCore.Qt.AlignRight)
		layoutV.addWidget(self.btn_getPart, 				0, 16, 1, 1)
		layoutV.addWidget(self.btn_getWhole, 				0, 17, 1, 1)
		layoutV.addWidget(self.btn_pushWidthPW, 			0, 18, 1, 1)
		layoutV.addWidget(self.btn_pushHeightPW, 			0, 19, 1, 1)


		layoutV.addWidget(QtGui.QLabel('Master data:'), 	1, 0, 1, 1)
		layoutV.addWidget(self.cmb_infoArrays, 				1, 1, 1, 4)
		layoutV.addWidget(self.btn_getArrays, 				1, 5, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Target:'),			1, 10, 1, 1, QtCore.Qt.AlignRight)
		layoutV.addWidget(self.btn_getTx, 					1, 11, 1, 2)
		layoutV.addWidget(self.btn_getTy, 					1, 13, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Populate:'),		1, 15, 1, 1, QtCore.Qt.AlignRight)
		layoutV.addWidget(self.btn_pushWidth, 				1, 16, 1, 2)
		layoutV.addWidget(self.btn_pushHeight, 				1, 18, 1, 2)

		layoutV.addWidget(self.tab_masters, 				2, 0, 15, 20)

		layoutV.addWidget(QtGui.QLabel('LERP [dX]:'),		23, 0, 1, 1, QtCore.Qt.AlignTop)
		layoutV.addLayout(self.mixer_dx,					23, 1, 1, 4)
		layoutV.addWidget(QtGui.QLabel('[dY]:'),			23, 5, 1, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
		layoutV.addLayout(self.mixer_dy,					23, 6, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Width:'),			23, 10, 1, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
		layoutV.addLayout(self.scaler_dx,					23, 11, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Height:'),			23, 15, 1, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
		layoutV.addLayout(self.scaler_dy,					23, 16, 1, 4)

		layoutV.addWidget(QtGui.QLabel('Process:'),			25, 0, 1, 1)
		layoutV.addWidget(self.rad_glyph, 					25, 1, 1, 1)
		layoutV.addWidget(self.rad_window, 					25, 2, 1, 1)
		layoutV.addWidget(self.rad_selection, 				25, 3, 1, 1)
		layoutV.addWidget(self.rad_font, 					25, 4, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Mode:'),			25, 5, 1, 1)
		layoutV.addWidget(self.chk_single,					25, 6, 1, 2)
		layoutV.addWidget(self.chk_italic,					25, 8, 1, 2)
		layoutV.addWidget(self.chk_boundry,					25, 10, 1, 2)
		layoutV.addWidget(self.chk_preview,					25, 12, 1, 3)
		layoutV.addWidget(self.btn_execute, 				25, 15, 1, 5)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 1150, 700)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(980,self.sizeHint.height())

		self.show()

	# - Functions ------------------------------------------------------------
	# - File operations
	def file_save_deltas(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Deltas to file', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tab_masters.getTable(), exportFile)
				print('SAVE:\t| Delta Machine | Font:%s; Deltas saved to: %s.' %(self.active_font.name, fname))

	def file_load_deltas(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load Deltas from file', fontPath, fileFormats)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
								
				table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in imported_data.items()}
				self.tab_masters.updateTable(table_dict)
				print('LOAD:\t| Delta Machine | Font:%s; Deltas loaded from: %s.' %(self.active_font.name, fname))

	# - Table operations
	def table_refresh(self):
		if self.rad_glyph.isChecked(): self.pMode = 0
		if self.rad_window.isChecked(): self.pMode = 1
		if self.rad_selection.isChecked(): self.pMode = 2
		if self.rad_font.isChecked(): self.pMode = 3
		self.data_glyphs = getProcessGlyphs(self.pMode)

	def table_check_all(self):
		for row in range(self.tab_masters.rowCount):
			if self.tab_masters.item(row,0).checkState() == QtCore.Qt.Unchecked:
				self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Checked)
				self.btn_tableCheck.setText('Uncheck all')
			else:
				self.tab_masters.item(row,0).setCheckState(QtCore.Qt.Unchecked)
				self.btn_tableCheck.setText('Check all')
	
	def table_populate(self):
		init_data = [[master, self.active_font.pMasters.names, self.active_font.pMasters.names, 1., 2., 1., 2., 0., 0.,100, 100, 0.00, 0.00] for master in self.active_font.pMasters.names]
		table_dict = {n:OrderedDict(zip(column_names, data)) for n, data in enumerate(init_data)}
		self.tab_masters.setTable(table_dict)
		
	# - Stem operations
	def get_PointArrays(self, glyph=None):
		if glyph is None: glyph = eGlyph()
		self.data_PointArrays.update({glyph.name:{master_name:PointArray(glyph._getPointArray(master_name)) for master_name in self.active_font.masters()}})
		
		self.cmb_infoArrays.clear()
		self.cmb_infoArrays.addItems(sorted(self.data_PointArrays.keys()))

		print('Done:\t| Delta Machine | Updated PointArrays.\tGlyph:%s' %glyph.name)

	def get_Stems(self, vertical=True, source=True):
		# - Helper
		def helper_calc_stem(glyph, master_name, vertical):
			selection = glyph.selectedNodes(master_name)
			
			if vertical:
				return abs(selection[0].x - selection[-1].x)
			else:
				return abs(selection[0].y - selection[-1].y)

		# - Init
		fill_colA = (3,1) if vertical else (5,1)
		fill_colB = (4,2) if vertical else (6,2)
		fill_colT = (7,8)[not vertical]

		# - Make it current glyph only for now...
		#data_stems = {glyph.name:{ master_name:helper_calc_stem(glyph, master_name, vertical) for master_name in self.active_font.masters()} for glyph in self.data_glyphs}
		
		glyph = eGlyph()
		modifiers = QtGui.QApplication.keyboardModifiers() # Listen to Shift - reverses the ratio
		
		if modifiers == QtCore.Qt.AltModifier:
			data_stems = probe_stem
		else:
			data_stems = { master_name:helper_calc_stem(glyph, master_name, vertical) for master_name in self.active_font.masters()}
		
		for row in range(self.tab_masters.rowCount):
			if source:
				self.tab_masters.cellWidget(row, fill_colA[0]).setValue(data_stems[self.tab_masters.cellWidget(row, fill_colA[1]).currentText])
				self.tab_masters.cellWidget(row, fill_colB[0]).setValue(data_stems[self.tab_masters.cellWidget(row, fill_colB[1]).currentText])
				self.tab_masters.cellWidget(row, fill_colT).setValue(data_stems[self.tab_masters.cellWidget(row, fill_colA[1]).currentText])
			else:
				self.tab_masters.cellWidget(row, fill_colT).setValue(data_stems[self.tab_masters.item(row, 0).text()])

	# - Sliders operations
	def set_sliders(self):
		if self.chk_preview.isChecked():
			data = self.tab_masters.getRow()

			self.mixer_dx.edt_0.setText(data[3])
			self.mixer_dx.edt_1.setText(data[4])
			self.mixer_dx.edt_pos.setText(data[7])

			self.mixer_dy.edt_0.setText(data[5])
			self.mixer_dy.edt_1.setText(data[6])
			self.mixer_dy.edt_pos.setText(data[8])

			self.scaler_dx.edt_0.setText(0)
			self.scaler_dx.edt_1.setText(200)
			self.scaler_dx.edt_pos.setText(data[9])

			self.scaler_dy.edt_0.setText(0)
			self.scaler_dy.edt_1.setText(200)
			self.scaler_dy.edt_pos.setText(data[10])

			self.mixer_dx.refreshSlider()
			self.mixer_dy.refreshSlider()
			self.scaler_dx.refreshSlider()
			self.scaler_dy.refreshSlider()

	def get_ratio(self, target=False):
		glyph = eGlyph()
		if target:
			self.ratio_target = {layerName:glyph.getBounds(layerName) for layerName in self.active_font.masters()}
		else:
			self.ratio_source = {layerName:glyph.getBounds(layerName) for layerName in self.active_font.masters()}

		print('Done:\t| Delta Machine | Stored BBOX data for Glyph: %s' %glyph.name)

	def push_ratio(self, height=False, bbox=False):
		modifiers = QtGui.QApplication.keyboardModifiers() # Listen to Shift - reverses the ratio
		
		if bbox:
			if modifiers == QtCore.Qt.AltModifier:
				target = QtGui.QInputDialog.getDouble(self, 'Ratio Calculator','Set Target Ratio:', 100, 0, 500, 2)

			for row in range(self.tab_masters.rowCount):
				layerName = self.tab_masters.item(row, 0).text()
				
				if height:
					ratio_height = ratfrac(self.ratio_target[layerName].height(), self.ratio_source[layerName].height(), 100)
					
					if modifiers == QtCore.Qt.ShiftModifier: # Reverse ratio
						ratio_height = ratfrac(self.ratio_source[layerName].height(), self.ratio_target[layerName].height(), 100) # Reverse ratio

					elif modifiers == QtCore.Qt.AltModifier:
						ratio_height = 100 + target - ratio_height # Target ratio
					
					self.tab_masters.cellWidget(row, 10).setValue(ratio_height)
				else:
					ratio_width = ratfrac(self.ratio_target[layerName].width(), self.ratio_source[layerName].width(), 100)
					
					if modifiers == QtCore.Qt.ShiftModifier: # Reverse ratio
						ratio_width = ratfrac(self.ratio_source[layerName].width(), self.ratio_target[layerName].width(), 100)
						
					elif modifiers == QtCore.Qt.AltModifier:
						ratio_width = 100 + target - ratio_width # Target ratio

					self.tab_masters.cellWidget(row, 9).setValue(ratio_width)

		else:
			ratio = QtGui.QInputDialog.getDouble(self, 'Ratio','Enter Ratio:', 100, -500, 500, 2)
			for row in range(self.tab_masters.rowCount):
				self.tab_masters.cellWidget(row, [9, 10][height]).setValue(ratio)
		

		
		print('Done:\t| Delta Machine | Pushed Ratio data per master.')

	# - Processing --------------------------
	def table_execute(self):
		process_glyphs = getProcessGlyphs(self.pMode)
		
		for wGlyph in process_glyphs:
			if self.pMode != 0: self.get_PointArrays(wGlyph)
			process_out = []
			
			for layerIndex in range(self.tab_masters.rowCount):
				if self.tab_masters.item(layerIndex, 0).checkState() == QtCore.Qt.Checked:
					process_out.append(self.tab_masters.item(layerIndex, 0).text())
					self.process_scale(wGlyph, layerIndex, anisotropic=self.chk_single.isChecked(), live_update=False)	

			wGlyph.update()
			wGlyph.updateObject(wGlyph.fl, '| Delta Machine | Glyph: %s\tLayers procesed: %s' %(wGlyph.name, '; '.join(process_out)))

	def process_scale(self, glyph, layerIndex=None, anisotropic=False, live_update=False, keep_metrics=False):
		wGlyph = glyph
		config_data = self.tab_masters.getRow(layerIndex)
	
		if len(self.data_PointArrays.keys()) and wGlyph.name in self.data_PointArrays.keys():
			# - Backup Metrics
			if keep_metrics:
				data_lsb, data_rsb = wGlyph.getLSB(config_data[0]), wGlyph.getRSB(config_data[0])
				data_lsb_eq, data_rsb_eq = wGlyph.getSBeq(config_data[0])

			# - Axis
			a = self.data_PointArrays[wGlyph.name][config_data[1]]
			b = self.data_PointArrays[wGlyph.name][config_data[2]]
			
			# - Compensation
			scmp = float(config_data[11]), float(config_data[12])
			
			# - Italic Angle
			if self.chk_italic.isChecked():
				angle = radians(float(self.italic_angle))
			else:
				angle = 0
			
			# - Stems
			sw_dx = [float(config_data[3]), float(config_data[4])]
			sw_dy = [float(config_data[5]), float(config_data[6])]

			if live_update:
				curr_sw_dx = float(self.mixer_dx.sld_axis.value)
				curr_sw_dy = float(self.mixer_dy.sld_axis.value)
			else:
				curr_sw_dx = float(config_data[7])
				curr_sw_dy = float(config_data[8])

			# - Stem values
			sw_dx0, sw_dx1 = sorted(sw_dx)
			sw_dy0, sw_dy1 = sorted(sw_dy)
		
			# - Interpolation times
			tx = transform.timer(curr_sw_dx, sw_dx0, sw_dx1, self.chk_boundry.isChecked())
			ty = transform.timer(curr_sw_dy, sw_dy0, sw_dy1, self.chk_boundry.isChecked())

			# - Scaling
			if live_update:
				sx = 100./float(self.scaler_dx.edt_1.text) + float(self.scaler_dx.sld_axis.value)/float(self.scaler_dx.edt_1.text)
				sy = 100./float(self.scaler_dy.edt_1.text) + float(self.scaler_dy.sld_axis.value)/float(self.scaler_dy.edt_1.text)
			else:
				sx = float(config_data[9])/100 	# scale X
				sy = float(config_data[10])/100 # scale Y
			
			dx, dy = 0.0, 0.0 # shift X, Y

			# - Build
			# -- Numpy
			#mm_scaler = lambda sx, sy, tx, ty : transform.adaptive_scale_array([a.x, a.y], [b.x, b.y], sx, sy, dx, dy, tx, ty, scmp[0], scmp[1], angle, [sw_dx0, sw_dx1, sw_dy0, sw_dy1])
			
			# -- Native
			joined_array = zip(a.tuple, b.tuple)
			mm_scaler = lambda sx, sy, tx, ty : transform.adaptive_scale_array(joined_array, (sx, sy), (dx, dy), (tx, ty), (scmp[0], scmp[1]), angle, [sw_dx0, sw_dx1, sw_dy0, sw_dy1])

			if anisotropic:
				# - Dual axis mixer - anisotropic 
				wGlyph._setPointArray(mm_scaler(sx, sy, tx, ty), layer=config_data[0])
			else:
				# - Single axis mixer
				wGlyph._setPointArray(mm_scaler(sx, sy, tx, tx), layer=config_data[0])
			
			if live_update:
				wGlyph.update()
				fl6.Update(wGlyph.fl)

			# - Restore metrics
			if keep_metrics:
				wGlyph.setLSB(data_lsb)	
				wGlyph.setRSB(data_rsb)	
				wGlyph.setLSBeq(data_lsb_eq)
				wGlyph.setRSBeq(data_rsb_eq)


# - RUN ------------------------------
dialog = dlg_DeltaMachine()