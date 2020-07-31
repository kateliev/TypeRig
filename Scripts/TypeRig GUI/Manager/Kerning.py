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
app_name, app_version = 'TypeRig | Kerning Overview', '3.0'
alt_mark = '.'

# - Dependencies -----------------
import os, json, re
from platform import system

import fontlab as fl6
import fontgate as fgt

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import TR2FieldDLG

from typerig.proxy import *

# - Strings ------------------------------------------------------------------
fileFormats = ['TypeRig JSON Raw Kerning (*.json)', 'FontLab JSON Kernign (*.vfm)']
NOVAL = 'NOVAL'
pair_delimiter = '|'
special_rule = '!'
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
				format_rule = item[:opi]
				return_commands.append((item[opi:], format_rule))
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
		self.selectionModel().selectionChanged.connect(self.selection_status_changed)


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
				else:
					kern_value = int(kern_value)

				new_item = QtGui.QTableWidgetItem(str(kern_value))
				self.setItem(row, col, new_item)

		self.blockSignals(False)
		#self.setSortingEnabled(True)
		self.resizeRowsToContents()

	def getSelection(self):
		return [(i.row(), i.column()) for i in self.selectionModel().selection.indexes()]	

	def getTable(self, getNotes=False):
		pass

	def selection_status_changed(self):
		selected_items = [float(item.text()) for item in self.selectedItems() if item.text() != NOVAL]
		selected_items_len = len(selected_items)
		if selected_items_len:
			selected_items_mean = sum(selected_items)/float(selected_items_len)
			self.aux.lbl_status_selection_len.setText(selected_items_len)
			self.aux.lbl_status_selection_med.setText(selected_items_mean)

			if self.aux.btn_fontKerning_preview.isChecked():
				self.aux.pair_preview_string(self.aux.btn_layer_preview.isChecked())

	def kern_value_changed(self, item):
		current_row, current_col = item.row(), item.column()
		current_layer = self.aux.data_fontKerning[0][current_col]
		current_pair = self.aux.data_fontKerning[2][current_row]
		#left, right = self.aux.data_fontKerning[2][current_row]
		#current_pair = (left.encode('ascii','ignore'), right.encode('ascii','ignore'))
		
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
		self.data_fontKerning = None
		self.data_clipboard = []

		# - Interface -------------------------
		# -- Conditional formatting -----------
		self.edt_formatting = QtGui.QLineEdit()
		self.edt_formatting.setPlaceholderText('Conditional formatting example: red==None; green > 0; blue < 0; yellow => 100;!hide<-50; !show==30;')
		
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
		self.edt_search_pair = QtGui.QLineEdit()
		self.edt_search_regex = QtGui.QLineEdit()
		
		self.edt_search_pair.setPlaceholderText('Pair search example: A|V; @O|@A; Where A|V plain pair and @O|@A classes containing O and A.')
		self.edt_search_regex.setPlaceholderText('RegEx search example: .*.O.*.A.*; Note: Pair source is [space] separated!')

		self.btn_search_pair_under = QtGui.QPushButton('Current Pair')
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
		self.btn_fontKerning_preview = QtGui.QPushButton('Preview pairs')
		self.btn_layer_preview = QtGui.QPushButton('Preview layers')
		self.btn_fontKerning_update = QtGui.QPushButton('Update Font')
		self.tab_fontKerning = KernTableWidget(self)
		
		self.btn_fontKerning_autoupdate.setCheckable(True)
		self.btn_fontKerning_preview.setCheckable(True)
		self.btn_layer_preview.setCheckable(True)
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
		act_data_reset.triggered.connect(lambda: self.kerning_reset())

		# -- Pairs
		self.menu_pair = QtGui.QMenu('Pairs', self)
		act_pair_add = QtGui.QAction('Add new pair', self)
		act_pair_del = QtGui.QAction('Remove pair', self)
		act_pair_update = QtGui.QAction('Update from Font', self)
		act_pair_copy = QtGui.QAction('Copy value(s)', self)
		act_pair_paste = QtGui.QAction('Paste value(s)', self)
		act_pair_copy_string = QtGui.QAction('Copy pair(s) string', self)
		act_pair_copy_leader = QtGui.QAction('Copy pair(s) string as Glyph Names', self)

		self.menu_pair.addAction(act_pair_add)
		self.menu_pair.addAction(act_pair_del)
		self.menu_pair.addAction(act_pair_update)
		self.menu_pair.addSeparator()
		self.menu_pair.addAction(act_pair_copy)
		self.menu_pair.addAction(act_pair_paste)
		self.menu_pair.addSeparator()
		self.menu_pair.addAction(act_pair_copy_string)
		self.menu_pair.addAction(act_pair_copy_leader)

		act_pair_add.setEnabled(False)
		
		#act_pair_add.triggered.connect(lambda: self.pair_add())
		act_pair_del.triggered.connect(lambda: self.pair_del())
		act_pair_update.triggered.connect(lambda: self.pair_update_from_source())
		act_pair_copy.triggered.connect(lambda: self.pair_copy_paste(False))
		act_pair_paste.triggered.connect(lambda: self.pair_copy_paste(True))
		act_pair_copy_string.triggered.connect(lambda: self.pair_copy_string(False))
		act_pair_copy_leader.triggered.connect(lambda: self.pair_copy_string(True))

		# -- Tools
		self.menu_tools = QtGui.QMenu('Tools', self)
		act_tools_fl_extend = QtGui.QAction('Extend Kerning', self)
		act_tools_fl_match = QtGui.QAction('Match Kerning', self)
		act_tools_tr_replace = QtGui.QAction('Find && Replace', self)
		act_tools_tr_round = QtGui.QAction('Quantize', self)
		act_tools_tr_scale = QtGui.QAction('Scale', self)
		act_tools_tr_filter = QtGui.QAction('Filter', self) # High-pass, low-pass, band-pass
		act_tools_tr_clean = QtGui.QAction('Cleanup', self)
		act_tools_tr_patchboard = QtGui.QAction('Patchboard', self)

		self.menu_tools.addAction(act_tools_fl_extend)
		self.menu_tools.addAction(act_tools_fl_match)
		self.menu_tools.addSeparator()
		self.menu_tools.addAction(act_tools_tr_replace)
		self.menu_tools.addSeparator()
		self.menu_tools.addAction(act_tools_tr_round)
		self.menu_tools.addAction(act_tools_tr_scale)
		self.menu_tools.addAction(act_tools_tr_filter)
		self.menu_tools.addAction(act_tools_tr_clean)
		self.menu_tools.addSeparator()
		self.menu_tools.addAction(act_tools_tr_patchboard)

		act_tools_fl_extend.setEnabled(False)
		act_tools_fl_match.setEnabled(False)
		act_tools_tr_round.setEnabled(False)
		act_tools_tr_scale.setEnabled(False)
		act_tools_tr_filter.setEnabled(False)
		act_tools_tr_clean.setEnabled(False)
		act_tools_tr_patchboard.setEnabled(False)

		act_tools_tr_replace.triggered.connect(lambda: self.tools_replace())

		# -- View
		self.menu_view = QtGui.QMenu('View', self)
		act_view_show_all = QtGui.QAction('Show hidden rows', self)
		act_view_hide_selected = QtGui.QAction('Hide selected rows', self)
		act_view_hide_matching = QtGui.QAction('Hide matching pairs', self)
		act_view_hide_nonmatching = QtGui.QAction('Hide non-matching pairs', self)
		act_view_pair_preview = QtGui.QAction('Preview selected pairs', self)

		self.menu_view.addAction(act_view_show_all)
		self.menu_view.addAction(act_view_pair_preview)
		self.menu_view.addSeparator()
		self.menu_view.addAction(act_view_hide_selected)
		self.menu_view.addAction(act_view_hide_matching)
		self.menu_view.addAction(act_view_hide_nonmatching)

		act_view_pair_preview.triggered.connect(lambda: self.pair_preview_string(self.btn_layer_preview.isChecked()))
		act_view_show_all.triggered.connect(lambda: self.update_table_show_all())
		act_view_hide_selected.triggered.connect(lambda: self.update_table_hide_selected())
		act_view_hide_matching.triggered.connect(lambda: self.update_table_hide_matching(True))
		act_view_hide_nonmatching.triggered.connect(lambda: self.update_table_hide_matching(False))

		# -- Status bar
		self.lbl_status_selection_len = QtGui.QLabel('0')
		self.lbl_status_selection_med = QtGui.QLabel('0')
		self.lbl_status_pairs_len = QtGui.QLabel('0')
		self.lbl_status_pairs_hidden = QtGui.QLabel('0')
		self.lbl_status_masters_len = QtGui.QLabel('0')

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
		self.lay_grid.addWidget(self.btn_fontKerning_preview,				1, 30, 1, 5)
		self.lay_grid.addWidget(self.btn_search_hide,						2, 25, 1, 5)
		self.lay_grid.addWidget(self.btn_layer_preview,						2, 30, 1, 5)

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
		self.lay_grid.addWidget(self.btn_formatting_clear,					36, 35, 1, 5)
		
		self.lay_grid.addWidget(QtGui.QLabel('SELECTION:'),					37, 0, 1, 4)
		self.lay_grid.addWidget(self.lbl_status_selection_len,				37, 4, 1, 4)
		self.lay_grid.addWidget(QtGui.QLabel('MEAN:'),					37, 8, 1, 4)	
		self.lay_grid.addWidget(self.lbl_status_selection_med,				37, 12, 1, 4)
		self.lay_grid.addWidget(QtGui.QLabel('PAIRS:'),						37, 16, 1, 4)	
		self.lay_grid.addWidget(self.lbl_status_pairs_len,					37, 20, 1, 4)
		self.lay_grid.addWidget(QtGui.QLabel('HIDDEN:'),					37, 24, 1, 4)	
		self.lay_grid.addWidget(self.lbl_status_pairs_hidden,				37, 28, 1, 4)
		self.lay_grid.addWidget(QtGui.QLabel('MASTERS:'),					37, 32, 1, 4)	
		self.lay_grid.addWidget(self.lbl_status_masters_len,				37, 36, 1, 4)

		
		self.lay_grid.setSpacing(3)
		self.setLayout(self.lay_grid)
	
	# - Context Menu Procedures --------------------------------------
	def contextMenuEvent(self, event):
		# - Init
		self.tab_fontKerning.menu = QtGui.QMenu(self)
		self.tab_fontKerning.menu.setTitle('Actions:')
		
		# - Build menus
		self.tab_fontKerning.menu.addMenu(self.menu_pair)
		self.tab_fontKerning.menu.addSeparator()	
		self.tab_fontKerning.menu.addMenu(self.menu_tools)
		self.tab_fontKerning.menu.addSeparator()	
		self.tab_fontKerning.menu.addMenu(self.menu_view)

		self.tab_fontKerning.menu.popup(QtGui.QCursor.pos())				

	# -- Helpers ---------------------------------------------------
	def getSelectedPairs(self, return_leaders=False):
		selected_pairs = set()
		selected_layers = set()
		all_layers, all_pairs = self.data_fontKerning[0], self.data_fontKerning[2]
		groups_dict = self.active_font.kerning_groups_to_dict(byPosition=True,sortUnicode=True)

		for item in self.tab_fontKerning.selectedItems():
			current_pair = all_pairs[item.row()]
			current_layer = all_layers[item.column()]
			
			if return_leaders:
				left, right = current_pair
				left_in_group, right_in_group = current_pair

				try:
					left_in_group = dict(groups_dict['KernLeft'])[left][0]
				except KeyError:
					try:
						left_in_group = dict(groups_dict['KernBothSide'])[left][0]
					except KeyError:
						left_in_group = left

				try:
					right_in_group = dict(groups_dict['KernRight'])[right][0]
				except KeyError:
					try:
						right_in_group = dict(groups_dict['KernBothSide'])[right][0]
					except KeyError:
						right_in_group = right

				current_pair = (left_in_group, right_in_group)
				
			selected_pairs.add(current_pair)
			selected_layers.add(current_layer)

		return selected_pairs, selected_layers

	# -- Actions ---------------------------------------------------
	# --- Pairs ----------------------------------------------------
	def pair_del(self):
		self.tab_fontKerning.blockSignals(True)
		selected_rows = set(sorted([item.row() for item in self.tab_fontKerning.selectedItems()]))
		pairs_removed = []

		for current_row in reversed(list(selected_rows)):
			# - Find and remove pair
			current_pair = self.data_fontKerning[2][current_row]
			pairs_removed.append('|'.join(current_pair))
			self.data_fontKerning[2].pop(self.data_fontKerning[2].index(current_pair))
			
			# - Find and remove actual kern data
			for kern_obj in self.data_fontKerning[1]:
				kern_obj.remove(current_pair)

			# - Find and remove rows from table
			self.tab_fontKerning.removeRow(current_row)
		
		print 'DONE:\tPairs removed: {}; Pairs: {}!\nWARN:\tAuto update was disabled during the process! Please update font manually!'.format(len(pairs_removed), ' '.join(pairs_removed))
		self.lbl_status_pairs_len.setText(len(self.data_fontKerning[2]))
		self.tab_fontKerning.blockSignals(False)

	def pair_copy_paste(self, paste_values=False):
		selected_items = self.tab_fontKerning.selectedItems()

		if not paste_values:
			self.data_clipboard = [item.text() for item in selected_items]
			print 'COPY:\tValues: {} to clipboard!'.format(len(self.data_clipboard))
		else:
			self.btn_fontKerning_autoupdate.setChecked(False)

			if len(self.data_clipboard) == 1 and len(selected_items):
				for item in selected_items:
					item.setText(self.data_clipboard[0])

				print 'PASTE:\tSINGLE value to Pairs: {}\nWARN:\tAuto update was disabled during the process! Please update font manually!'.format(len(selected_items))

			elif len(self.data_clipboard) == len(selected_items):
				for idx in range(len(selected_items)):
					selected_items[idx].setText(self.data_clipboard[idx])

				print 'PASTE:\tMULTIPLE values to Pairs: {}\nWARN:\tAuto update was disabled during the process! Please update font manually!'.format(len(selected_items))
			else:
				print 'ERROR:\tData in Clipboard and Selection do not match: {}/{}!'.format(len(self.data_clipboard),len(selected_items))

	def pair_copy_string(self, return_leaders=False):
		selected_pairs, _discard = self.getSelectedPairs(return_leaders)
		clipboard = QtGui.QApplication.clipboard()
		
		if return_leaders:
			clipboard.setText('/space'.join(['/'+'/'.join(current_pair) for current_pair in selected_pairs]))
		else:
			clipboard.setText(str(list(selected_pairs)))

		print 'DONE:\t Generated string sent to clipboard!\t Pairs: {}'.format(len(selected_pairs))

	def pair_preview_string(self, use_layer=False):
		selected_pairs, selected_layers = self.getSelectedPairs(True)
		selected_pairs = sum([[item[0], item[1], 'space'] for item in selected_pairs], [])
		'''
		selected_pairs = sum([[fl6.fgSymbol(item[0]), fl6.fgSymbol(item[1]), fl6.fgSymbol('space')] for item in selected_pairs],[])
		fg_symbols = fl6.fgSymbolList(selected_pairs)
		fl6.flItems.requestContent(fg_symbols,1)
		'''
		current_layer = list(selected_layers)[:1] if use_layer else ''
		pItems().outputGlyphNames(selected_pairs, current_layer)

	def pair_update_from_source(self):
		self.tab_fontKerning.blockSignals(True)
		selected_items = self.tab_fontKerning.selectedItems()
		
		for item in selected_items:
			current_row, current_col = item.row(), item.column()
			current_layer = self.data_fontKerning[0][current_col]
			current_pair = self.data_fontKerning[2][current_row]
			update_value = int(self.active_font.kerning(current_layer)[current_pair])
			item.setText(update_value)

		self.tab_fontKerning.blockSignals(False)
		print 'UPDATE:\tPair values updated from source: {}'.format(len(selected_items))

	# --- Actions Tools --------------------------------------------
	def tools_replace(self):
		search, replace = TR2FieldDLG('Find & Replace', 'Enter kern pair values.', 'Find value:', 'Replace value:').values
		work_done = 0

		if search is not None and replace is not None:
			self.btn_fontKerning_autoupdate.setChecked(False)

			for row in xrange(self.tab_fontKerning.rowCount):
				for col in xrange(self.tab_fontKerning.columnCount):
					cell_item = self.tab_fontKerning.item(row, col)
					
					if cell_item is not None:	
						if cell_item.text() == search: 
							cell_item.setText(replace)
							work_done += 1

			print 'REPLACE:\tKern pairs changed: {}\nWARN:\tAuto update was disabled during the process! Please update font manually!'.format(work_done)

	# - Main Procedures --------------------------------------------
	def update_font(self):
		self.active_font.update()
		print 'DONE:\tKerning updated! Font: %s;' %self.active_font.fg.path

	def update_data(self, source, updateTable=True):
		self.data_fontKerning = source
		self.lbl_status_masters_len.setText(len(self.data_fontKerning[0]))
		self.lbl_status_pairs_len.setText(len(self.data_fontKerning[2]))
		
		if updateTable:
			self.tab_fontKerning.clear()
			while self.tab_fontKerning.rowCount > 0: self.tab_fontKerning.removeRow(0)
			self.tab_fontKerning.setTable(self.data_fontKerning)

	def update_table_format(self, clearTable=False):
		hidden_rows = 0
		formattig_list = parser_format(self.edt_formatting.text)
		self.tab_fontKerning.blockSignals(True)

		for row in xrange(self.tab_fontKerning.rowCount):
			for col in xrange(self.tab_fontKerning.columnCount):
				cell_item = self.tab_fontKerning.item(row, col)
				
				if cell_item is not None:	
					if not clearTable:
						for cell_rule, format_rule in formattig_list:
							if eval(cell_item.text() + cell_rule):
								if special_rule in format_rule:
									if format_rule[1:].upper() == 'HIDE':
										self.tab_fontKerning.hideRow(row)
										hidden_rows += 1
										break
									elif format_rule[1:].upper() == 'SHOW':
										self.tab_fontKerning.showRow(row)
										break
								else:
									color_rule = QtGui.QColor(format_rule)
									color_rule.setAlpha(50)
									cell_item.setBackground(color_rule)
					else:
						cell_item.setBackground(QtGui.QColor('white'))						

		self.tab_fontKerning.blockSignals(False)
		self.lbl_status_pairs_hidden.setText(hidden_rows)
			
	def update_table_hightlights(self, search_field=False, hide_others=False):
		# !!! TODO: Use direct Vertical/Horizontal header indexing if columns/rows are moved
		show_items = []
		hidden_rows = 0

		font_layers, font_kerning, all_pairs = self.data_fontKerning
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
				new_left, new_right = proxy_kerning.getPairGroups((left, right))
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
					hidden_rows += 1

		self.lbl_status_pairs_hidden.setText(hidden_rows)
		self.tab_fontKerning.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection) # Back to regular selection

	def update_table_regex(self):
		all_pairs = self.data_fontKerning[2]
		all_pairs_text = [' '.join(item) for item in all_pairs]
		results = re.findall(self.edt_search_regex.text, '\n'.join(all_pairs_text), re.UNICODE)
		show_items = []
		hidden_rows = 0

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
					hidden_rows += 1

		self.lbl_status_pairs_hidden.setText(hidden_rows)

	def update_table_hide_selected(self):
		hidden_rows = int(self.lbl_status_pairs_hidden.text)
		rows_to_hide = sorted(list(set([item.row() for item in self.tab_fontKerning.selectedItems()])))
		hidden_rows += len(rows_to_hide)
		
		for row in rows_to_hide:
			self.tab_fontKerning.hideRow(row)

		self.lbl_status_pairs_hidden.setText(hidden_rows)

	def update_table_hide_matching(self, hide_matching=True):
		hidden_rows = 0

		for row in xrange(self.tab_fontKerning.rowCount):
			if hide_matching:
				self.tab_fontKerning.hideRow(row)
				hidden_rows += 1
			else:
				self.tab_fontKerning.showRow(row)

			for col in xrange(self.tab_fontKerning.columnCount):
				if self.tab_fontKerning.item(row,col).text() == NOVAL:
					if not hide_matching:
						self.tab_fontKerning.hideRow(row)
						hidden_rows += 1
					else:
						self.tab_fontKerning.showRow(row)
					break

		self.lbl_status_pairs_hidden.setText(hidden_rows)

	def update_table_show_all(self):
		for row in xrange(self.tab_fontKerning.rowCount):
			self.tab_fontKerning.showRow(row)

		self.lbl_status_pairs_hidden.setText('0')

	def kerning_reset(self):
		ask_clear_kerning = QtGui.QMessageBox.question(self, 'Clear font Kerning', 'Are you shure you want to delete all kerning pairs for:\n%s'%self.active_font.fg.path, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		
		if ask_clear_kerning == QtGui.QMessageBox.Yes:
			for layer in self.active_font.masters():
				tmp_proxy = pKerning(self.active_font.kerning(layer))
				tmp_len = len(tmp_proxy.fg)
				tmp_proxy.clear()
				print 'DEL:\t Layer: %s;\tPairs: %s' %(layer, tmp_len)

			self.active_font.kerning(layer)
			self.active_font.update()
			self.tab_fontKerning.clear()
			while self.tab_fontKerning.rowCount > 0: self.tab_fontKerning.removeRow(0)
			print 'DONE:\t Font: %s - Kerning removed!' %self.active_font.fg.path	
	
	def kerning_from_font(self, ask_user=True):
		font_kerning = []
		font_layers = []
		pair_set = []
		import_empty = False
		print 'LOAD:\tPreparing kerning data...'
		
		if ask_user:
			ask_import_empty = QtGui.QMessageBox.question(self, 'Import kerning from font', 'Do you want to import layers with empty/no kerning', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
			import_empty = ask_import_empty == QtGui.QMessageBox.No 

		for layer in self.active_font.masters():
			current_kerning = self.active_font.kerning(layer)
			if not len(current_kerning) and import_empty: continue
			
			temp_set = set()
			for pair in current_kerning.keys():
				left, right = pair.asTuple()
				temp_set.add((left.asTuple()[0], right.asTuple()[0]))

			pair_set.append(temp_set)
			font_kerning.append(current_kerning)
			font_layers.append(layer)
		
		all_pairs = sorted(list(reduce(set.union, pair_set))) # Get all pairs for all masters
		
		self.data_fontKerning = (font_layers, font_kerning, all_pairs)
		self.update_data(self.data_fontKerning, updateTable=True)
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
			self.ActionsMenu.addMenu(self.kernGroups.menu_view)
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