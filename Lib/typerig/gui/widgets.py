# MODULE: Typerig / GUI / Widgets
# NOTE	: Assorted Gui Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.0.5'

# - Dependencies --------------------------
from platform import system

from PythonQt import QtCore
import QtGui

from typerig.proxy import *

# - Functions --------------------------
def getProcessGlyphs(mode=0, font=None, workspace=None):
	'''Returns a list of glyphs for processing in TypeRig gui apps

	Args:
		mode (int): 0 - Current active glyph; 1 - All glyphs in current window; 2 - All selected glyphs; 3 - All glyphs in font
		font (fgFont) - Font file (object)
		workspace (flWorkspace) - Workspace
	
	Returns:
		list(eGlyph)
	'''
	# - Init
	process_glyphs = []
	active_workspace = pWorkspace()
	active_font = pFont(font)
		
	# - Collect process glyphs
	if mode == 0: process_glyphs.append(eGlyph())
	if mode == 1: process_glyphs = [eGlyph(glyph) for glyph in active_workspace.getTextBlockGlyphs()]
	if mode == 2: process_glyphs = active_font.selectedGlyphs(extend=eGlyph) 
	if mode == 3: process_glyphs = active_font.glyphs(extend=eGlyph)
	
	return process_glyphs
	
# - Classes -------------------------------
# -- Messages & Dialogs -------------------
class TRMsgSimple(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(TRMsgSimple, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

class TR2FieldDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_field_b, dlg_size=(300, 300, 300, 100)):
		super(TR2FieldDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.lbl_field_b = QtGui.QLabel(dlg_field_b)
		
		self.edt_field_t = QtGui.QLineEdit() # Top field
		self.edt_field_b = QtGui.QLineEdit() # Bottom field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.lbl_field_b,	2, 0, 1, 2)
		main_layout.addWidget(self.edt_field_b,	2, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = (self.edt_field_t.text, self.edt_field_b.text)

# -- Sliders ------------------------------
class TRSliderCtrl(QtGui.QGridLayout):
	def __init__(self, edt_0, edt_1, edt_pos, spb_step):
		super(TRSliderCtrl, self).__init__()
		
		# - Init
		self.initValues = (edt_0, edt_1, edt_pos, spb_step)

		self.edt_0 = QtGui.QLineEdit(edt_0)
		self.edt_1 = QtGui.QLineEdit(edt_1)
		self.edt_pos = QtGui.QLineEdit(edt_pos)

		self.spb_step = QtGui.QSpinBox()
		self.spb_step.setValue(spb_step)

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.sld_axis.valueChanged.connect(self.sliderChange)
		self.refreshSlider()
		
		self.edt_0.editingFinished.connect(self.refreshSlider)
		self.edt_1.editingFinished.connect(self.refreshSlider)
		self.spb_step.valueChanged.connect(self.refreshSlider)
		self.edt_pos.editingFinished.connect(self.refreshSlider)

		# - Layout		
		self.addWidget(self.sld_axis, 			0, 0, 1, 5)
		self.addWidget(self.edt_pos, 			0, 5, 1, 1)		
		self.addWidget(QtGui.QLabel('Min:'),	1, 0, 1, 1)
		self.addWidget(self.edt_0, 				1, 1, 1, 1)
		self.addWidget(QtGui.QLabel('Max:'), 	1, 2, 1, 1)
		self.addWidget(self.edt_1, 				1, 3, 1, 1)
		self.addWidget(QtGui.QLabel('Step:'),	1, 4, 1, 1)
		self.addWidget(self.spb_step, 			1, 5, 1, 1)


	def refreshSlider(self):
		self.sld_axis.blockSignals(True)
		self.sld_axis.setMinimum(float(self.edt_0.text.strip()))
		self.sld_axis.setMaximum(float(self.edt_1.text.strip()))
		self.sld_axis.setValue(float(self.edt_pos.text.strip()))
		self.sld_axis.setSingleStep(int(self.spb_step.value))
		self.sld_axis.blockSignals(False)
				
	def reset(self):
		self.edt_0.setText(self.initValues[0])
		self.edt_1.setText(self.initValues[1])
		self.edt_pos.setText(self.initValues[2])
		self.spb_step.setValue(self.initValues[3])
		self.refreshSlider()

	def sliderChange(self):
		self.edt_pos.setText(self.sld_axis.value)

# -- Tables ------------------------------------------------------
class TRTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRTableView, self).__init__()

		# - Init
		self.flag_valueChanged = QtGui.QColor('powderblue')

		# - Set 
		if data is not None: self.setTable(data)
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)
		self.setSortingEnabled(False)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, sortData=(True, True), indexColCheckable=None):
		name_row, name_column = [], []
		self.blockSignals(True)

		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Populate
		for row, value in enumerate(sorted(data.keys()) if sortData[0] else data.keys()):
			name_row.append(value)
			
			for col, key in enumerate(sorted(data[value].keys()) if sortData[1] else data[value].keys()):
				name_column.append(key)
				rowData = data[value][key]
				
				if isinstance(rowData, basestring):
					newitem = QtGui.QTableWidgetItem(str(rowData))
				else:
					newitem = QtGui.QTableWidgetItem()
					newitem.setData(QtCore.Qt.EditRole, rowData)
									
				# - Make the columnt checkable
				if indexColCheckable is not None and col in indexColCheckable:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
					newitem.setCheckState(QtCore.Qt.Unchecked) 

				self.setItem(row, col, newitem)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self, raw=False):
		return_list = []

		for row in range(self.rowCount):
			if not raw:
				return_list.append((self.verticalHeaderItem(row).text(), {self.horizontalHeaderItem(col).text():float(self.item(row, col).text()) for col in range(self.columnCount)}))
			else:
				return_list.append((self.verticalHeaderItem(row).text(), [(self.horizontalHeaderItem(col).text(), self.item(row, col).text()) for col in range(self.columnCount)]))

		if raw:	return return_list			
		return dict(return_list)
		

	def markChange(self, item):
		item.setBackground(self.flag_valueChanged)

class TRHTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-bottom: 10px;
				padding: 5px 7px 4px 7px; 
				margin-right: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')

class TRVTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		self.setUsesScrollButtons(True)
		self.setTabPosition(QtGui.QTabWidget.East)
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-left: 11px;
				padding: 5px 4px 5px 5px; 
				margin-bottom: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')
