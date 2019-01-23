#FLM: Font: Kern Classes
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Kern Classes', '2.5'
alt_mark = '.'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont, pGlyph
from typerig.utils import getUppercaseCodepoint, getLowercaseCodepoint

# - Strings ------------------------------------------------------------------
fileFormats = ['TypeRig JSON Raw Classes (*.json)', 'FontLab VI JSON Classes (*.json)']

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

# - Custom classes -----------------------------------------------------------
class GroupTableView(QtGui.QTableWidget):
	def __init__(self):
		super(GroupTableView, self).__init__()
				
		# - Init
		self.flag_valueChanged = QtGui.QColor('powderblue')
		self.kern_pos_mods = ['KernLeft', 'KernRight', 'KernBothSide']

		# - Behavior
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.verticalHeader().hide()
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)
		#self.resizeRowsToContents()
		self.setSortingEnabled(True)

	def setTable(self, data, setNotes=False):
		# - Init
		name_column = ['Class Name', 'Class Type', 'Class Members', 'Note']
		
		self.blockSignals(True)
		self.setColumnCount(len(name_column))
		self.setRowCount(len(data.keys()))
		self.setSortingEnabled(False) # Great solution from: https://stackoverflow.com/questions/7960505/strange-qtablewidget-behavior-not-all-cells-populated-after-sorting-followed-b

		# - Populate
		for row, key in enumerate(sorted(data.keys())):
								
			item_groupName = QtGui.QTableWidgetItem(str(key))
			item_groupPos = QtGui.QTableWidgetItem(str(data[key][1]))
			item_groupMem = QtGui.QTableWidgetItem(' '.join(data[key][0]))
		
			self.setItem(row, 0, item_groupName)
			self.setItem(row, 1, item_groupPos)
			self.setItem(row, 2, item_groupMem)

			if setNotes:
				try:
					item_groupNote = QtGui.QTableWidgetItem(data[key][2])
					self.setItem(row, 3, item_groupNote)
				except IndexError:
					pass

		self.setHorizontalHeaderLabels(name_column)
		self.blockSignals(False)
		self.setSortingEnabled(True)

	def getSelection(self):
		return [(i.row(), i.column()) for i in self.selectionModel().selection.indexes()]	

	def getTable(self, getNotes=False):
		returnDict = {}
		for row in range(self.rowCount):
			if getNotes and self.item(row,3) is not None:
				returnDict[str(self.item(row, 0).text())] = (self.item(row, 2).text().split(), str(self.item(row,1).text()), str(self.item(row,3).text()))
			else:	
				returnDict[str(self.item(row, 0).text())] = (self.item(row, 2).text().split(), str(self.item(row,1).text()))

		return returnDict

	def markChange(self, item):
		item.setBackground(self.flag_valueChanged)


# - Font Group Kerning -------------------------------------------------------
class WKernGroups(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WKernGroups, self).__init__()

		# - Init
		self.upper_widget = parentWidget
		self.active_font = pFont()
		self.kern_group_data = {} #self.active_font.kerning_groups_to_dict()

		# - Interface
		lbl_name = QtGui.QLabel('Kerning classes')
		lbl_act = QtGui.QLabel('Actions (selected items):')
		lbl_name.setMaximumHeight(20)
		lbl_act.setMaximumHeight(20)

		self.cmb_layer = QtGui.QComboBox()
		self.cmb_layer.addItems(self.active_font.masters())
		self.cmb_layer.currentIndexChanged.connect(lambda: self.update_data(self.kern_group_data))

		self.btn_apply = QtGui.QPushButton('Apply changes')
		self.btn_write = QtGui.QPushButton('Write changes')
		self.btn_reset = QtGui.QPushButton('Clear font classes')

		self.btn_apply.clicked.connect(lambda: self.apply_changes(False))
		self.btn_write.clicked.connect(lambda: self.apply_changes(True))
		self.btn_reset.clicked.connect(lambda: self.reset_classes())

		self.tab_groupKern = GroupTableView()

		# - Menus & Actions
		# -- Main Database actions
		self.menu_data = QtGui.QMenu('Class Data', self)
		act_data_open = QtGui.QAction('Open TypeRig Classes (JSON)', self)
		act_data_save = QtGui.QAction('Save TypeRig Classes (JSON)', self)
		act_data_import = QtGui.QAction('Import FontLab Classes (JSON)', self)
		act_data_export = QtGui.QAction('Export FontLab Classes (JSON)', self)
		act_data_import_font = QtGui.QAction('Import Classes from Font', self)
		act_data_build_composite = QtGui.QAction('Build Classes from References', self)
		act_data_reset = QtGui.QAction('Reset Font Class Data', self)
		act_data_write = QtGui.QAction('Write class data to Font', self)

		self.menu_data.addAction(act_data_open)
		self.menu_data.addAction(act_data_save)
		self.menu_data.addSeparator()
		self.menu_data.addAction(act_data_import)
		self.menu_data.addAction(act_data_export)
		self.menu_data.addSeparator()
		self.menu_data.addAction(act_data_import_font)
		self.menu_data.addAction(act_data_build_composite)
		self.menu_data.addSeparator()
		self.menu_data.addAction(act_data_reset)
		self.menu_data.addAction(act_data_write)

		act_data_open.triggered.connect(lambda: self.file_load_groups(True))
		act_data_save.triggered.connect(lambda: self.file_save_groups(True))
		act_data_import.triggered.connect(lambda: self.file_load_groups(False))
		#act_data_export.triggered.connect()
		act_data_import_font.triggered.connect(lambda: self.from_font())
		act_data_build_composite.triggered.connect(lambda: self.from_composites())
		act_data_reset.triggered.connect(lambda: self.reset_classes())
		act_data_write.triggered.connect(lambda: self.apply_changes(True))

		# -- Main Class actions
		self.menu_class = QtGui.QMenu('Class Management', self)
		act_class_add = QtGui.QAction('Add new class', self)
		act_class_find = QtGui.QAction('Find and replace class names', self)
		act_class_copy = QtGui.QAction('Duplicate classes', self)
		act_class_merge = QtGui.QAction('Merge classes to new', self)
		act_class_mdel = QtGui.QAction('Merge and remove classes', self)
		act_class_del = QtGui.QAction('Remove classes', self)

		self.menu_class.addAction(act_class_add)
		self.menu_class.addAction(act_class_find)
		self.menu_class.addAction(act_class_copy)
		self.menu_class.addAction(act_class_merge)
		self.menu_class.addAction(act_class_mdel)
		self.menu_class.addAction(act_class_del)

		act_class_add.triggered.connect(lambda: self.class_add_new())
		act_class_find.triggered.connect(lambda: self.class_find_replace())
		act_class_copy.triggered.connect(lambda: self.class_copy())
		act_class_merge.triggered.connect(lambda: self.class_merge(False))
		act_class_mdel.triggered.connect(lambda: self.class_merge(True))
		act_class_del.triggered.connect(lambda: self.class_del())
		
		# -- Change class type
		self.menu_type = QtGui.QMenu('Class Type', self)
		act_type_Left = QtGui.QAction('Set KernLeft (1st)', self)
		act_type_Right = QtGui.QAction('Set KernRight (2nd)', self)
		act_type_Both = QtGui.QAction('Set KernBothSide (1st and 2nd)', self)
		act_type_toggle = QtGui.QAction('Toggle class type', self)
		
		act_type_Left.triggered.connect(lambda: self.set_type('KernLeft'))
		act_type_Right.triggered.connect(lambda: self.set_type('KernRight'))
		act_type_Both.triggered.connect(lambda: self.set_type('KernBothSide'))
		act_type_toggle.triggered.connect(lambda: self.toggle_type())

		self.menu_type.addAction(act_type_Left)
		self.menu_type.addAction(act_type_Right)
		self.menu_type.addAction(act_type_Both)
		self.menu_type.addAction(act_type_toggle)

		# -- Modify Members
		self.menu_memb = QtGui.QMenu('Class Members', self)
		act_memb_sel = QtGui.QAction('Select Glyphs', self)
		act_memb_clean = QtGui.QAction('Cleanup', self)
		act_memb_upper = QtGui.QAction('Members to uppercase', self)
		act_memb_lower = QtGui.QAction('Members to lowercase', self)
		act_memb_strip = QtGui.QAction('Strip member suffixes', self)
		act_memb_suff = QtGui.QAction('Add suffix to members', self)
		act_memb_addglyphs = QtGui.QAction('Selected glyphs to members', self)

		act_memb_sel.triggered.connect(lambda: self.memb_select())
		act_memb_clean.triggered.connect(lambda: self.memb_cleanup())
		act_memb_upper.triggered.connect(lambda: self.memb_change_case(True))
		act_memb_lower.triggered.connect(lambda: self.memb_change_case(False))
		act_memb_strip.triggered.connect(lambda: self.memb_stripSuffix())
		act_memb_suff.triggered.connect(lambda: self.memb_addSuffix())
		act_memb_addglyphs.triggered.connect(lambda: self.memb_addGlyphs())

		self.menu_memb.addAction(act_memb_sel)
		self.menu_memb.addAction(act_memb_clean)
		self.menu_memb.addAction(act_memb_upper)
		self.menu_memb.addAction(act_memb_lower)
		self.menu_memb.addAction(act_memb_strip)
		self.menu_memb.addAction(act_memb_suff)		
		self.menu_memb.addAction(act_memb_addglyphs)	


		# - Table auto preview selection
		self.chk_preview = QtGui.QCheckBox('Auto select/preview class.')
		self.tab_groupKern.selectionModel().selectionChanged.connect(lambda: self.auto_preview())
		
		# - Build 	
		self.lay_grid = QtGui.QGridLayout()
		self.lay_grid.addWidget(lbl_name,		 		0, 0, 1, 42)
		self.lay_grid.addWidget(QtGui.QLabel('Master:'),0, 40, 1, 2)
		self.lay_grid.addWidget(self.cmb_layer,			0, 42, 1, 6)
		self.lay_grid.addWidget(self.tab_groupKern,		1, 0, 9, 42)
		self.lay_grid.addWidget(self.chk_preview,		2, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_apply,			1, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_reset,			8, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_write,			9, 42, 1, 6)


		for i in range(1,8):
			self.lay_grid.setRowStretch(i,2)
		
		self.setLayout(self.lay_grid)
	
	# - Context Menu Procedures --------------------------------------
	def contextMenuEvent(self, event):
		# - Init
		self.tab_groupKern.menu = QtGui.QMenu(self)
		self.tab_groupKern.menu.setTitle('Class Actions:')
		
		# - Build menus
		self.tab_groupKern.menu.addMenu(self.menu_class)
		self.tab_groupKern.menu.addSeparator()	
		self.tab_groupKern.menu.addMenu(self.menu_type)
		self.tab_groupKern.menu.addSeparator()
		self.tab_groupKern.menu.addMenu(self.menu_memb)

		self.tab_groupKern.menu.popup(QtGui.QCursor.pos())				

	# -- Actions
	def auto_preview(self):
		if self.chk_preview.isChecked():
			self.memb_select()

	def class_add_new(self):
		if self.tab_groupKern.rowCount > 0:
			self.tab_groupKern.insertRow(0)
			item_groupName = QtGui.QTableWidgetItem('Class_%s' %self.tab_groupKern.rowCount)
			item_groupPos = QtGui.QTableWidgetItem('KernLeft')
			item_groupMem = QtGui.QTableWidgetItem('')

			self.tab_groupKern.setItem(0, 0, item_groupName)
			self.tab_groupKern.setItem(0, 1, item_groupPos)
			self.tab_groupKern.setItem(0, 2, item_groupMem)
		else:
			layer = self.cmb_layer.currentText
			empty_table = {layer:{'Class_1':[[''], 'KernLeft']}}
			self.update_data(empty_table)

	def class_find_replace(self):
		search = QtGui.QInputDialog.getText(self, 'Find and replace class names', 'Please enter SPACE separated pair:\n(SEARCH_string) (REPLACE_string).', QtGui.QLineEdit.Normal, 'Find Replace')
		mod_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

		find, replace = search.split()

		for row in range(self.tab_groupKern.rowCount):
			currItem = self.tab_groupKern.item(row, 0)
			
			if len(mod_keys) and currItem.text() in mod_keys:
					currItem.setText(currItem.text().replace(find, replace))

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)
		print 'DONE:\t Search and replace in class names.'

	def class_del(self):
		temp_data = self.tab_groupKern.getTable()
		del_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

		for key in del_keys: temp_data.pop(key, None)
			
		self.update_data(temp_data, layerUpdate=True)
		print 'DONE:\t Removed Classes: %s'  %(', '.join(del_keys))

	def class_copy(self):
		prefix = QtGui.QInputDialog.getText(self, 'Duplicate classes', 'Please enter prefix for the new classes.', QtGui.QLineEdit.Normal, 'copy_')

		if len(prefix):
			temp_data = self.tab_groupKern.getTable()
			dup_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

			for key in dup_keys:
				temp_data[prefix + key] = temp_data[key]
				print 'DONE:\t Class: %s; Duplicated with prefix: %s.' %(key, prefix)

			self.update_data(temp_data, layerUpdate=True)

	def class_merge(self, delete=False):
		merge_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]
		
		if len(merge_keys) > 1:
			merge_name = QtGui.QInputDialog.getText(self, 'Merge classes', 'Please enter name for the new class.', QtGui.QLineEdit.Normal, 'merge_' + '_'.join(merge_keys))
			temp_data = self.tab_groupKern.getTable()

			if len(merge_name) and merge_name not in temp_data.keys():
				temp_data[merge_name] = (sorted(list(set([item for key in merge_keys for item in temp_data[key][0]]))), 'KernLeft') # Do better!
				
				if delete:
					for key in merge_keys:
						temp_data.pop(key, None)
					print 'DONE:\t Removed Classes: %s; Merged to: %s.' %(', '.join(merge_keys), merge_name)
				else:
					print 'DONE:\t Classes: %s; Merged to: %s.' %(', '.join(merge_keys), merge_name)

				self.update_data(temp_data, layerUpdate=True)
		
	def set_type(self, typeStr):
		for row, col in self.tab_groupKern.getSelection():
			self.tab_groupKern.item(row, 1).setText(typeStr)
			print 'DONE:\t Class: %s; Type set to: %s.' %(self.tab_groupKern.item(row, 0).text(), typeStr)

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def toggle_type(self):
		replace_dict = {'KernLeft':'KernRight', 'KernRight':'KernLeft'}

		for row, col in self.tab_groupKern.getSelection():
			
			if self.tab_groupKern.item(row, 1).text() in replace_dict.keys():
				self.tab_groupKern.item(row, 1).setText(replace_dict[self.tab_groupKern.item(row, 1).text()])
				print 'DONE:\t Class: %s; Type set to: %s.' %(self.tab_groupKern.item(row, 0).text(), replace_dict[self.tab_groupKern.item(row, 1).text()])

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def memb_select(self):
		self.active_font.unselectAll()
		for row, col in self.tab_groupKern.getSelection():
			self.active_font.selectGlyphs(self.tab_groupKern.item(row, 2).text().split())			

	def memb_cleanup(self):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = ' '.join(sorted(list(set(old_data.split()))))
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; Members cleanup.' %self.tab_groupKern.item(row, 0).text()

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def memb_stripSuffix(self):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = ' '.join([item.split(alt_mark)[0] for item in old_data.split()])
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; All suffixes removed from members.' %self.tab_groupKern.item(row, 0).text()

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def memb_addSuffix(self):
		suffix = QtGui.QInputDialog.getText(self, 'Add suffix', 'Please enter Suffix for all class members.')

		if len(suffix):
			for row, col in self.tab_groupKern.getSelection():
				old_data = self.tab_groupKern.item(row, 2).text()
				new_data = ' '.join([item + suffix for item in old_data.split()])
				self.tab_groupKern.item(row, 2).setText(new_data)
				print 'DONE:\t Class: %s; New suffix (%s) added to members.' %(self.tab_groupKern.item(row, 0).text(), suffix)

			self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def memb_addGlyphs(self):
		selection = [glyph.name for glyph in self.active_font.selectedGlyphs()]

		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = old_data + ' ' + ' '.join(selection)
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; Added members: %s' %(self.tab_groupKern.item(row, 0).text(), ' '.join(selection))

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)

	def memb_change_case(self, toUpper=False):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = []
			
			for item in old_data.split():
				if alt_mark in item:
					temp_item = item.split(alt_mark)
					
					if toUpper:
						temp_item = [getUppercaseCodepoint(temp_item[0])] + temp_item[1:]
					else:
						temp_item = [getLowercaseCodepoint(temp_item[0])] + temp_item[1:]

					new_data.append(alt_mark.join(temp_item))

				else:
					if toUpper:
						new_data.append(getUppercaseCodepoint(item))
					else:
						new_data.append(getLowercaseCodepoint(item))
			
			self.tab_groupKern.item(row, 2).setText(' '.join(new_data))

		self.update_data(self.tab_groupKern.getTable(), False, layerUpdate=True)
		print 'DONE:\t Class: %s; Members change case.' %self.tab_groupKern.item(row, 0).text()

	# - Main Procedures --------------------------------------------
	def update_data(self, source, updateTable=True, setNotes=False, layerUpdate=False):
		layer = self.cmb_layer.currentText
		
		if not layerUpdate:
			self.kern_group_data = source
		else:
			self.kern_group_data[layer] = source
		
		if updateTable and self.kern_group_data.has_key(layer):	
			self.tab_groupKern.clear()
			while self.tab_groupKern.rowCount > 0: self.tab_groupKern.removeRow(0)
			self.tab_groupKern.setTable(self.kern_group_data[layer], setNotes)
			print 'DONE:\t Updating classes table for master: %s' %layer
		else:
			print 'ERROR:\t Updating classes table for master: %s' %layer

			msg = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'TypeRig: Warning', 'There is no kerning class information for current selected layer: %s.\n\n Do you want to add a new empty table into database for layer: %s?' %(layer, layer), QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel, self)
			if msg.exec_() == 1024:
				self.kern_group_data[layer] = {'Class_1':[[''], 'KernLeft']}
				# ! DO: Better
				self.tab_groupKern.clear()
				while self.tab_groupKern.rowCount > 0: self.tab_groupKern.removeRow(0)
				self.tab_groupKern.setTable(self.kern_group_data[layer], setNotes)
				print 'DONE:\t Updating classes table for master: %s' %layer

	def apply_changes(self, writeToFont=True):
		active_layer = self.cmb_layer.currentText
		self.kern_group_data[active_layer] = self.tab_groupKern.getTable()
		if not writeToFont: print 'DONE:\t Internal Database classes updated for layer: %s' %active_layer
		
		if writeToFont:	
			self.active_font.dict_to_kerning_groups(self.kern_group_data[active_layer], active_layer)
			
			print 'DONE:\t Font: %s - Kerning classes updated.' %self.active_font.name
			print '\nPlease add a new empty class in FL6 Classes panel to preview changes!'

	def reset_classes(self):
		self.active_font.reset_kerning_groups(self.cmb_layer.currentText)
		print 'DONE:\t Font: %s - Kerning classes removed.' %self.active_font.name
		print '\nPlease add a new empty class in FL6 Classes panel to preview changes!'

	def file_save_groups(self, exportRaw=True):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save kerning classes to file', fontPath , '*.json')

		layer = self.cmb_layer.currentText
		self.kern_group_data[layer] = self.tab_groupKern.getTable(getNotes=exportRaw)

		if fname != None:
			with open(fname, 'w') as exportFile:
				if exportRaw:
					json.dump(self.kern_group_data, exportFile)
				
				print 'SAVE:\t Font:%s; %s format Group Kerning classes saved to: %s.' %(self.active_font.name, ('FontLab','TypeRig')[exportRaw], fname)

	def file_load_groups(self, importRaw=True):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upper_widget, 'Load kerning classes from file', fontPath)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				if importRaw:
					imported_data = json.load(importFile)
				else:
					imported_data = json_class_dumb_decoder(json.load(importFile))
					
				self.update_data(imported_data, setNotes=False)
				print 'LOAD:\t Font:%s; %s Group Kerning classes loaded from: %s.' %(self.active_font.name, ('FontLab','TypeRig')[importRaw], fname)

	def from_font(self):
		temp_dict = {}
		msg = QtGui.QMessageBox(QtGui.QMessageBox.Warning, 'TypeRig: Warning', 'Due to fatal class kerning bug in FontLab VI (build 6927) the classes cannot be loaded reliably from font.\n\nPress OK to continue loading class information from font without predefined mode (1st, 2nd and etc.)', QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel, self)
				
		if msg.exec_() == 1024:
			for layer in self.active_font.masters():
				fl_kern_group_dict = self.active_font.fl_kerning_groups_to_dict(layer)
				temp_dict[layer] = {key: (value, 'UNKNOWN') for key,value in fl_kern_group_dict.iteritems()}
			
			self.update_data(temp_dict)
		

	def from_composites(self):
		# - Init
		font_workset_names = [glyph.name for glyph in self.active_font.uppercase()] + [glyph.name for glyph in self.active_font.lowercase()] + [glyph.name for glyph in self.active_font.alternates()]
		ban_list = ['sups', 'subs', 'ss10', 'ss09', 'ss08', 'dnom', 'numr', 'notdef']
		class_dict, temp_dict = {}, {}
		
		# - Process
		process_glyphs = self.active_font.pGlyphs()
		
		for glyph in process_glyphs:
			if all([banned_item not in glyph.name for banned_item in ban_list]):
				layer = self.cmb_layer.currentText
				clear_comp = [comp.shapeData.name for comp in glyph.shapes(layer) + glyph.components(layer) if comp.shapeData.name in font_workset_names and comp.shapeData.name != glyph.name]
				
				if len(clear_comp) == 1:
					class_dict.setdefault(clear_comp[0], set([clear_comp[0]])).add(glyph.name)

				if len(clear_comp) == 0 and alt_mark in glyph.name:
					class_dict.setdefault(glyph.name.split(alt_mark)[0], set([glyph.name.split(alt_mark)[0]])).add(glyph.name)

				if len(clear_comp) > 1:
					print 'WARN:\t Glyph: %s; Multiple components: %s' %(glyph.name, clear_comp)
		
		for key, value in class_dict.iteritems():
			temp_dict['%s_L' %key] = (sorted(value), 'KernLeft')
			temp_dict['%s_R' %key] = (sorted(value), 'KernRight')

			#print 'ADD:\t 1st and 2nd Classes: %s -> %s' %(key, ' '.join(sorted(value)))

		# - Finish
		self.update_data(temp_dict, layerUpdate=True)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		layoutV = QtGui.QVBoxLayout()
		
		self.kernGroups = WKernGroups(self)
		self.ActionsMenu = QtGui.QMenuBar()

		self.ActionsMenu.addMenu(self.kernGroups.menu_data)
		self.ActionsMenu.addMenu(self.kernGroups.menu_class)
		self.ActionsMenu.addMenu(self.kernGroups.menu_type)
		self.ActionsMenu.addMenu(self.kernGroups.menu_memb)

		layoutV.setMenuBar(self.ActionsMenu)
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