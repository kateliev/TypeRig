#FLM: TR: Kerning
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Kerning Overview', '1.1'
alt_mark = '.'

# - Dependencies -----------------
import os, json
from platform import system

import fontlab as fl6
import fontgate as fgt

from PythonQt import QtCore
from typerig.gui import QtGui

from typerig.proxy import *

# - Strings ------------------------------------------------------------------
fileFormats = ['TypeRig JSON Raw Kerning (*.json)', 'FontLab JSON Kernign (*.vfm)']
NOVAL = 'NOVAL'
pair_delimiter = '|'
command_separator = ';'
command_operator = '== >= <= != > <'.split()

# - Functions ----------------------------------------------------------------
def json_class_dumb_decoder(jsonData):
	retund_dict = {}
	pos_dict = {(True, False):'KernLeft', (False, True):'KernRight', (True, True):'KernBothSide'}
	getPos = lambda d: (d['1st'] if d.has_key('1st') else False , d['2nd'] if d.has_key('2nd') else False)

	if len(jsonData.keys()):
		if jsonData.has_key('masters') and len(jsonData['masters']):
			for master in jsonData['masters']:
				if len(master.keys()):
					if master.has_key('kerningClasses') and len(master['kerningClasses']):
						temp_dict = {}

						for group in master['kerningClasses']:
							if group.has_key('names'):
								temp_dict[group['name']] = (group['names'], pos_dict[getPos(group)])

						retund_dict[master['name']] = temp_dict
	return retund_dict

def parser_highlight(parse_string):
	parse_string = [item.strip() for item in parse_string.split(command_separator)]
	return_commands = []
	
	for item in parse_string:
		for operator in command_operator:
			if operator in item:
				opi = item.index(operator)
				color_rule = QtGui.QColor(item[:opi])
				color_rule.setAlpha(50)
				return_commands.append((item[opi:], color_rule))
	return return_commands

# - Custom classes -----------------------------------------------------------
class KernTableWidget(QtGui.QTableWidget):
	def __init__(self, aux):
		super(KernTableWidget, self).__init__()

		# - Init
		self.flag_valueChanged = QtGui.QColor('powderblue')
		self.header = self.horizontalHeader()
		self.aux = aux

		# - Behavior
		self.itemChanged.connect(self.kern_value_changed)

		# - Styling
		self.setShowGrid(True)
		self.setSortingEnabled(True)

	def setTable(self, data):
		# - Init
		font_layers, font_kerning, all_pairs = data
				
		self.blockSignals(True)

		self.setColumnCount(len(font_layers))
		self.setRowCount(len(all_pairs))
		self.setSortingEnabled(False) # Great solution from: https://stackoverflow.com/questions/7960505/strange-qtablewidget-behavior-not-all-cells-populated-after-sorting-followed-b

		# - Headers 
		self.setHorizontalHeaderLabels(font_layers)
		self.setVerticalHeaderLabels([pair_delimiter.join(pair) for pair in all_pairs])
		self.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft)
		self.verticalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft)

		# - Populate
		for row, pair in enumerate(all_pairs):
			for col, layer in enumerate(font_layers):
				kern_value = font_kerning[col][pair]
				
				if kern_value is None:
					kern_value = NOVAL

				new_item = QtGui.QTableWidgetItem(str(kern_value))
				self.setItem(row, col, new_item)

		self.blockSignals(False)
		self.setSortingEnabled(True)
		self.resizeRowsToContents()

	def getSelection(self):
		return [(i.row(), i.column()) for i in self.selectionModel().selection.indexes()]	

	def getTable(self, getNotes=False):
		pass

	def kern_value_changed(self, item):
		current_row, current_col = item.row(), item.column()
		current_layer = self.horizontalHeaderItem(current_col).text()
		current_pair = tuple(self.verticalHeaderItem(current_col).text().split(pair_delimiter))
		self.aux.active_font.kerning(current_layer)[current_pair] = int(item.text())
		item.setForeground(QtGui.QBrush(QtGui.QColor('red')))
		if self.aux.btn_fontKerning_autoupdate.isChecked():
			self.aux.active_font.update()
		


# - Font Group Kerning -------------------------------------------------------
class WKernGroups(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WKernGroups, self).__init__()

		# - Init
		self.upper_widget = parentWidget
		self.active_font = pFont()
		self.application = pWorkspace()
		self.tab_fontKerning_data = None

		# - Interface -------------------------
		# -- Conditional formatting -----------
		self.edt_formatting = QtGui.QLineEdit()
		self.edt_formatting.setPlaceholderText('Conditional formatting string. Example: red==None; green > 0; blue < 0; yellow => 100;')
		
		self.btn_formatting_apply = QtGui.QPushButton('Format')
		self.btn_formatting_clear = QtGui.QPushButton('Clear')
		self.btn_formatting_color = QtGui.QPushButton('>')
		self.btn_formatting_color.setMaximumWidth(20)
		
		self.btn_formatting_color.clicked.connect(lambda: self.edt_formatting.setText(self.edt_formatting.text + self.cmb_select_color.currentText))
		self.btn_formatting_apply.clicked.connect(lambda: self.update_table_format(False))
		self.btn_formatting_clear.clicked.connect(lambda: self.update_table_format(True))

		self.cmb_select_color = QtGui.QComboBox()

		colorNames = QtGui.QColor.colorNames()
		for i in range(len(colorNames)):
			self.cmb_select_color.addItem(colorNames[i])
			self.cmb_select_color.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

		self.cmb_select_color.setCurrentIndex(colorNames.index('red'))

		# -- Cell highlighter and search ------
		self.btn_search_pair_under = QtGui.QPushButton('Current Pair')
		self.edt_search_pair = QtGui.QLineEdit()
		self.btn_search_pair = QtGui.QPushButton('Find')
		self.btn_search_pair_under.clicked.connect(lambda: self.update_table_hightlights(False))

		# -- Table ----------------------------
		self.btn_fontKerning_autoupdate = QtGui.QPushButton('Auto Update')
		self.btn_fontKerning_update = QtGui.QPushButton('Update Kerning')
		self.tab_fontKerning = KernTableWidget(self)
		self.btn_fontKerning_autoupdate.setCheckable(True)
		self.btn_fontKerning_autoupdate.setChecked(True)
		self.btn_fontKerning_update.clicked.connect(lambda: self.active_font.update())

		# - Menus & Actions --------------------
		# -- Main Database actions
		self.menu_data = QtGui.QMenu('Kerning Data', self)
		act_data_import = QtGui.QAction('Import Kerning', self)
		act_data_export = QtGui.QAction('Export Kerning', self)
		act_data_font = QtGui.QAction('Load from Font', self)
		act_data_reset = QtGui.QAction('Reset Font Kerning Data', self)

		act_data_import.setEnabled(False)
		act_data_export.setEnabled(False)

		self.menu_data.addAction(act_data_font)
		self.menu_data.addSeparator()
		self.menu_data.addAction(act_data_import)
		self.menu_data.addAction(act_data_export)
		self.menu_data.addSeparator()
		self.menu_data.addSeparator()
		self.menu_data.addAction(act_data_reset)

		#act_data_import.triggered.connect(lambda: self.file_load_groups(True))
		#act_data_export.triggered.connect(lambda: self.file_export_groups(True))
		act_data_font.triggered.connect(lambda: self.kerning_from_font())
		#act_data_reset.triggered.connect(lambda: self.reset_classes())

		# -- Main Class actions
		self.menu_pair = QtGui.QMenu('Pair Management', self)
		act_pair_add = QtGui.QAction('Add new pair', self)

		self.menu_pair.addAction(act_pair_add)

		act_pair_add.triggered.connect(lambda: self.class_add_new())
		
		# -- Change class type
		self.menu_tools = QtGui.QMenu('Management Tools', self)

		# -- MACOS buttons menu
		self.btn_mac_data_import = QtGui.QPushButton('Import')
		self.btn_mac_data_export = QtGui.QPushButton('Export')
		self.btn_mac_data_font = QtGui.QPushButton('From Font')
		self.btn_mac_data_reset = QtGui.QPushButton('Reset Kerning')

		self.btn_mac_data_import.setEnabled(False)
		self.btn_mac_data_export.setEnabled(False)


		self.btn_mac_data_font.clicked.connect(lambda: self.kerning_from_font())

		# - Build ------------------------------------------
		self.lay_grid = QtGui.QGridLayout()
		# -- MAC buttons
		if system() == 'Darwin':
			self.lay_grid.addWidget(self.btn_mac_data_font,					0, 0, 1, 10)
			self.lay_grid.addWidget(self.btn_mac_data_import,				0, 10, 1, 5)	
			self.lay_grid.addWidget(self.btn_mac_data_export,				0, 15, 1, 5)	
			self.lay_grid.addWidget(self.btn_mac_data_reset,				0, 20, 1, 5)			

		# -- Regular interface
		self.lay_grid.addWidget(self.btn_search_pair_under,					1, 0, 1, 10)
		self.lay_grid.addWidget(self.edt_search_pair,						1, 10, 1, 10)	
		self.lay_grid.addWidget(self.btn_search_pair,						1, 20, 1, 5)	
		self.lay_grid.addWidget(self.btn_fontKerning_autoupdate,			1, 30, 1, 5)
		self.lay_grid.addWidget(self.btn_fontKerning_update,				1, 35, 1, 5)
		self.lay_grid.addWidget(self.tab_fontKerning,						4, 0, 32, 40)
		self.lay_grid.addWidget(self.cmb_select_color,						36, 0, 1, 5)
		self.lay_grid.addWidget(self.btn_formatting_color,					36, 5, 1, 1)
		self.lay_grid.addWidget(self.edt_formatting,						36, 6, 1, 24)
		self.lay_grid.addWidget(self.btn_formatting_apply,					36, 30, 1, 5)
		self.lay_grid.addWidget(self.btn_formatting_clear,					36, 35, 1, 5)
		
		self.setLayout(self.lay_grid)
	
	# - Context Menu Procedures --------------------------------------
	def contextMenuEvent(self, event):
		# - Init
		self.tab_fontKerning.menu = QtGui.QMenu(self)
		self.tab_fontKerning.menu.setTitle('Class Actions:')
		
		# - Build menus
		self.tab_fontKerning.menu.addMenu(self.menu_pair)
		self.tab_fontKerning.menu.addSeparator()	
		self.tab_fontKerning.menu.addMenu(self.menu_tools)

		self.tab_fontKerning.menu.popup(QtGui.QCursor.pos())				

	# -- Actions ---------------------------------------------------


	# - Main Procedures --------------------------------------------
	def update_data(self, source, updateTable=True):
		self.tab_fontKerning_data = source
		
		if updateTable:
			self.tab_fontKerning.clear()
			while self.tab_fontKerning.rowCount > 0: self.tab_fontKerning.removeRow(0)
			self.tab_fontKerning.setTable(self.tab_fontKerning_data)

	def update_table_format(self, clearTable=False):
		formattig_list = parser_highlight(self.edt_formatting.text)
		self.tab_fontKerning.blockSignals(True)

		for row in range(self.tab_fontKerning.rowCount):
			for col in range(self.tab_fontKerning.columnCount):
				cell_item = self.tab_fontKerning.item(row, col)
				
				if cell_item is not None:	
					if not clearTable:
						for cell_rule, cell_color in formattig_list:
							if eval(cell_item.text() + cell_rule):
								cell_item.setBackground(cell_color)
					else:
						cell_item.setBackground(QtGui.QColor('white'))

		self.tab_fontKerning.blockSignals(False)
			
	def update_table_hightlights(self, search_field=False):
		font_layers, font_kerning, all_pairs = self.tab_fontKerning_data
		self.tab_fontKerning.clearSelection()

		if not search_field: # !!! TODO: Use direct Vertical/Horizontal header indexing if columns/rows are moved
			pair_under_cursor = self.application.getActiveKernPair()

			if pair_under_cursor is not None:
				col = font_layers.index(pGlyph().layer().name)
				proxy_kerning = pKerning(font_kerning[col])
				row = all_pairs.index(proxy_kerning.getPairGroups(pair_under_cursor))
			 	
			 	selected_item = self.tab_fontKerning.item(row, col)
			 	self.tab_fontKerning.setRangeSelected(QtGui.QTableWidgetSelectionRange(row, col, row, col), True)
			 	self.tab_fontKerning.scrollToItem(selected_item, QtGui.QAbstractItemView.PositionAtCenter)

	def kerning_reset(self):
		self.active_font.reset_kerning_groups(self.cmb_layer.currentText)
		print 'DONE:\t Font: %s - Kerning classes removed.' %self.active_font.name
		print '\nPlease add a new empty class in FL6 Classes panel to preview changes!'
	
	def kerning_from_font(self):
		font_kerning = []
		font_layers = []
		pair_set = []
		print 'LOAD:\tPreparing kerning data...'
		
		for layer in self.active_font.masters():
			current_kerning = self.active_font.kerning(layer)
			temp_set = set()

			for pair in current_kerning.keys():
				left, right = pair.asTuple()
				temp_set.add((left.asTuple()[0], right.asTuple()[0]))

			pair_set.append(temp_set)
			font_kerning.append(current_kerning)
			font_layers.append(layer)
		
		all_pairs = sorted(list(reduce(set.union, pair_set))) # Get all pairs for all masters
		
		self.tab_fontKerning_data = (font_layers, font_kerning, all_pairs)
		self.update_data(self.tab_fontKerning_data, updateTable=True)
		print 'LOAD:\tKern table loaded! Font: %s;' %self.active_font.fg.path


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		layoutV = QtGui.QVBoxLayout()
		
		self.kernGroups = WKernGroups(self)
		
		if system() != 'Darwin': # - Menubar only on Windows
			self.ActionsMenu = QtGui.QMenuBar(self)
			self.ActionsMenu.addMenu(self.kernGroups.menu_data)
			self.ActionsMenu.addMenu(self.kernGroups.menu_pair)
			self.ActionsMenu.addMenu(self.kernGroups.menu_tools)
			layoutV.setMenuBar(self.ActionsMenu)
		
		layoutV.addWidget(self.kernGroups)
						
		# - Build ---------------------------
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 900, 600)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()