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
app_name, app_version = 'TypeRig | Kerning Overview', '1.5'
alt_mark = '.'

# - Dependencies -----------------
import os, json, re
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
pair_class = '@'
command_separator = ';'
command_operator = '== >= <= != > <'.split()

# - Functions ----------------------------------------------------------------
def parser_format(parse_string):
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

def parser_highlight(parse_string):
	parse_string = [item.strip() for item in parse_string.split(command_separator)]
	return_commands = []

	for item in parse_string:
		item_tuple = item.split(pair_delimiter)
		return_commands.append((item_tuple[0].strip(), item_tuple[1].strip()))

	return return_commands

# - Custom classes -----------------------------------------------------------
class KernTableWidget(QtGui.QTableWidget):
	def __init__(self, aux):
		super(KernTableWidget, self).__init__()

		# - Init
		self.aux = aux
		
		self.flag_valueDefault = QtGui.QColor('black')
		self.flag_valueChanged = QtGui.QColor('red')
		
		self.values_changed = []
		self.itemChanged.connect(self.kern_value_changed)


		# - Styling
		self.header = self.horizontalHeader()
		self.setShowGrid(True)
		#self.setSortingEnabled(True)
		#self.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)

	def setTable(self, data):
		# - Init
		font_layers, font_kerning, all_pairs = data
				
		self.blockSignals(True)

		self.setColumnCount(len(font_layers))
		self.setRowCount(len(all_pairs))
		#self.setSortingEnabled(False) # Great solution from: https://stackoverflow.com/questions/7960505/strange-qtablewidget-behavior-not-all-cells-populated-after-sorting-followed-b

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
		#self.setSortingEnabled(True)
		self.resizeRowsToContents()

	def getSelection(self):
		return [(i.row(), i.column()) for i in self.selectionModel().selection.indexes()]	

	def getTable(self, getNotes=False):
		pass

	def kern_value_changed(self, item):
		current_row, current_col = item.row(), item.column()
		#current_layer = self.horizontalHeaderItem(current_col).text()
		#current_pair = tuple(self.verticalHeaderItem(current_col).text().split(pair_delimiter))
		current_layer = self.aux.tab_fontKerning_data[0][current_col]
		current_pair = self.aux.tab_fontKerning_data[2][current_row]
		
		self.aux.active_font.kerning(current_layer)[current_pair] = int(item.text())
		item.setForeground(QtGui.QBrush(self.flag_valueChanged))
		
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
		self.edt_search_pair.setPlaceholderText('Pair serach example: A|V; @O|@A; Where A|V plain pair and @O|@A classes containing O and A.')
		self.edt_search_regex = QtGui.QLineEdit()
		self.edt_search_regex.setPlaceholderText('RegEx search example: .*.O.*.A.*; Note: Pair source is [space] separated!')

		self.btn_search_pair = QtGui.QPushButton('Find Pairs')
		self.btn_search_regex = QtGui.QPushButton('Find RegEx')

		self.btn_search_hide = QtGui.QPushButton('Hide others')
		self.btn_search_hide.setCheckable(True)
		
		self.btn_search_hide.clicked.connect(lambda: self.update_table_show_all())
		self.btn_search_pair_under.clicked.connect(lambda: self.update_table_hightlights(False))
		self.btn_search_pair.clicked.connect(lambda: self.update_table_hightlights(True))
		self.btn_search_regex.clicked.connect(lambda: self.update_table_regex())

		# -- Table ----------------------------
		self.btn_fontKerning_autoupdate = QtGui.QPushButton('Auto Update')
		self.btn_fontKerning_update = QtGui.QPushButton('Update Kerning')
		self.tab_fontKerning = KernTableWidget(self)
		self.btn_fontKerning_autoupdate.setCheckable(True)
		self.btn_fontKerning_autoupdate.setChecked(True)
		self.btn_fontKerning_update.clicked.connect(lambda: self.update_font())

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
		
		self.lay_grid.addWidget(self.edt_search_pair,						1, 0, 1, 20)	
		self.lay_grid.addWidget(self.btn_search_pair,						1, 20, 1, 5)	
		self.lay_grid.addWidget(self.btn_search_pair_under,					1, 25, 1, 5)
		self.lay_grid.addWidget(self.btn_search_hide,						2, 25, 1, 5)

		self.lay_grid.addWidget(self.edt_search_regex,						2, 0, 1, 20)	
		self.lay_grid.addWidget(self.btn_search_regex,						2, 20, 1, 5)
		
		self.lay_grid.addWidget(self.btn_fontKerning_autoupdate,			1, 35, 1, 5)
		self.lay_grid.addWidget(self.btn_fontKerning_update,				2, 35, 1, 5)
		
		self.lay_grid.addWidget(self.tab_fontKerning,						4, 0, 32, 40)

		self.lay_grid.addWidget(self.cmb_select_color,						36, 0, 1, 5)
		self.lay_grid.addWidget(self.btn_formatting_color,					36, 5, 1, 1)
		self.lay_grid.addWidget(self.edt_formatting,						36, 6, 1, 24)
		self.lay_grid.addWidget(self.btn_formatting_apply,					36, 30, 1, 5)
		self.lay_grid.addWidget(self.btn_formatting_clear,					36, 35, 1, 5)
		
		self.lay_grid.setSpacing(3)
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
	def update_font(self):
		'''
		for item in self.tab_fontKerning.values_changed:
			item.setForeground(QtGui.QBrush(self.tab_fontKerning.flag_valueDefault))
		'''
		self.active_font.update()
		#self.tab_fontKerning.values_changed = []

	def update_data(self, source, updateTable=True):
		self.tab_fontKerning_data = source
		
		if updateTable:
			self.tab_fontKerning.clear()
			while self.tab_fontKerning.rowCount > 0: self.tab_fontKerning.removeRow(0)
			self.tab_fontKerning.setTable(self.tab_fontKerning_data)

	def update_table_format(self, clearTable=False):
		formattig_list = parser_format(self.edt_formatting.text)
		self.tab_fontKerning.blockSignals(True)

		for row in xrange(self.tab_fontKerning.rowCount):
			for col in xrange(self.tab_fontKerning.columnCount):
				cell_item = self.tab_fontKerning.item(row, col)
				
				if cell_item is not None:	
					if not clearTable:
						for cell_rule, cell_color in formattig_list:
							if eval(cell_item.text() + cell_rule):
								cell_item.setBackground(cell_color)
					else:
						cell_item.setBackground(QtGui.QColor('white'))

		self.tab_fontKerning.blockSignals(False)
			
	def update_table_hightlights(self, search_field=False, hide_others=False):
		# !!! TODO: Use direct Vertical/Horizontal header indexing if columns/rows are moved
		show_items = []

		font_layers, font_kerning, all_pairs = self.tab_fontKerning_data
		col = font_layers.index(pGlyph().layer().name)
		proxy_kerning = pKerning(font_kerning[col])
		
		self.tab_fontKerning.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
		self.tab_fontKerning.clearSelection()

		if not search_field: 
			pairs_list = [self.application.getActiveKernPair()]
		else:
			pairs_list = parser_highlight(self.edt_search_pair.text)

		for pair in pairs_list:
			if pair is not None:
				left, right = pair
				left_is_group, right_is_group = False, False
				
				if pair_class in left:
					left = left.strip(pair_class)
					left_is_group = True

				if pair_class in right:
					right = right.strip(pair_class)
					right_is_group = True

				if not search_field:
					left_is_group = True
					right_is_group = True

				new_left, new_right = proxy_kerning.getPairGroups((left, right))
				new_left = new_left if left_is_group else left
				new_right = new_right if right_is_group else right

				row = all_pairs.index((new_left, new_right))
				
				selected_item = self.tab_fontKerning.item(row, col)
				show_items.append(row)
				
				if not search_field:
					self.tab_fontKerning.setRangeSelected(QtGui.QTableWidgetSelectionRange(row, col, row, col), True)
					self.tab_fontKerning.scrollToItem(selected_item, QtGui.QAbstractItemView.PositionAtCenter)
				else:
					self.tab_fontKerning.selectRow(row)

		if self.btn_search_hide.isChecked():
			for row in xrange(self.tab_fontKerning.rowCount):
				if row in show_items:
					self.tab_fontKerning.showRow(row)
				else:	
					self.tab_fontKerning.hideRow(row)

		self.tab_fontKerning.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection) # Back to regular selection

	def update_table_regex(self):
		all_pairs = self.tab_fontKerning_data[2]
		all_pairs_text = [' '.join(item) for item in all_pairs]
		results = re.findall(self.edt_search_regex.text, '\n'.join(all_pairs_text), re.UNICODE)
		show_items = []

		for search_result in results:
			if search_result in all_pairs_text:
				row = all_pairs_text.index(search_result)
				self.tab_fontKerning.selectRow(row)
				show_items.append(row)
			else:
				print 'RegEx:\tNot Found: %s' %search_result

		if self.btn_search_hide.isChecked():
			for row in xrange(self.tab_fontKerning.rowCount):
				if row in show_items:
					self.tab_fontKerning.showRow(row)
				else:	
					self.tab_fontKerning.hideRow(row)
		

	def update_table_show_all(self):
		for row in xrange(self.tab_fontKerning.rowCount):
			self.tab_fontKerning.showRow(row)

	def kerning_reset(self):
		self.active_font.reset_kerning_groups(self.cmb_layer.currentText)
		print 'DONE:\t Font: %s - Kerning classes removed.' %self.active_font.name
		print '\nPlease add a new empty class in FL6 Classes panel to preview changes!'
	
	def kerning_from_font(self):
		font_kerning = []
		font_layers = []
		pair_set = []
		print 'LOAD:\tPreparing kerning data...'
		import_empty = QtGui.QMessageBox.question(self, 'Import kerning from font', 'Do you want to import layers with empty/no kerning', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		
		for layer in self.active_font.masters():
			current_kerning = self.active_font.kerning(layer)
			if not len(current_kerning) and import_empty == QtGui.QMessageBox.No: continue
			
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