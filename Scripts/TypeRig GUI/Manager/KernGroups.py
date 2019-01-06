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
app_name, app_version = 'TypeRig | Kern Classes', '1.4'
alt_mark = '.'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont
from typerig.utils import getUppercaseCodepoint, getLowercaseCodepoint

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

	def setTable(self, data):
		# - Init
		name_column = ['Class Name', 'Class Type', 'Class Members']
		
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

		self.setHorizontalHeaderLabels(name_column)
		self.blockSignals(False)
		self.setSortingEnabled(True)

	def getSelection(self):
		return [(i.row(), i.column()) for i in self.selectionModel().selection.indexes()]	

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
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
		lbl_name = QtGui.QLabel('Kerning classes (active layer)')
		lbl_act = QtGui.QLabel('Actions (selected items):')
		lbl_name.setMaximumHeight(20)
		lbl_act.setMaximumHeight(20)

		self.btn_apply = QtGui.QPushButton('Write changes')
		self.btn_reset = QtGui.QPushButton('Clear font classes')
		self.btn_import = QtGui.QPushButton('Open')
		self.btn_export = QtGui.QPushButton('Save')
		self.btn_fromFont = QtGui.QPushButton('Get from Font')
		self.btn_fromComp = QtGui.QPushButton('Build from References')

		self.btn_apply.clicked.connect(self.apply_changes)
		self.btn_reset.clicked.connect(self.reset_classes)
		self.btn_export.clicked.connect(self.export_groups)
		self.btn_import.clicked.connect(self.import_groups)
		self.btn_fromComp.clicked.connect(self.from_composites)

		self.tab_groupKern = GroupTableView()

		# - Menus & Actions
		# -- Main Class actions
		self.menu_class = QtGui.QMenu('Class Management', self)
		act_class_find = QtGui.QAction('Find and replace class names', self)
		act_class_copy = QtGui.QAction('Duplicate classes', self)
		act_class_merge = QtGui.QAction('Merge classes to new', self)
		act_class_mdel = QtGui.QAction('Merge and remove classes', self)
		act_class_del = QtGui.QAction('Remove classes', self)

		self.menu_class.addAction(act_class_find)
		self.menu_class.addAction(act_class_copy)
		self.menu_class.addAction(act_class_merge)
		self.menu_class.addAction(act_class_mdel)
		self.menu_class.addAction(act_class_del)

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
		
		act_type_Left.triggered.connect(lambda: self.set_type('KernLeft'))
		act_type_Right.triggered.connect(lambda: self.set_type('KernRight'))
		act_type_Both.triggered.connect(lambda: self.set_type('KernBothSide'))

		self.menu_type.addAction(act_type_Left)
		self.menu_type.addAction(act_type_Right)
		self.menu_type.addAction(act_type_Both)

		# -- Modify Members
		self.menu_memb = QtGui.QMenu('Class Members', self)
		act_memb_sel = QtGui.QAction('Select Glyphs', self)
		act_memb_clean = QtGui.QAction('Cleanup', self)
		act_memb_upper = QtGui.QAction('Members to uppercase', self)
		act_memb_lower = QtGui.QAction('Members to lowercase', self)
		act_memb_strip = QtGui.QAction('Strip member suffixes', self)
		act_memb_suff = QtGui.QAction('Add suffix to members', self)

		act_memb_clean.triggered.connect(lambda: self.memb_cleanup())
		act_memb_upper.triggered.connect(lambda: self.memb_change_case(True))
		act_memb_lower.triggered.connect(lambda: self.memb_change_case(False))
		act_memb_strip.triggered.connect(lambda: self.memb_stripSuffix())
		act_memb_suff.triggered.connect(lambda: self.memb_addSuffix())

		self.menu_memb.addAction(act_memb_sel)
		self.menu_memb.addAction(act_memb_clean)
		self.menu_memb.addAction(act_memb_upper)
		self.menu_memb.addAction(act_memb_lower)
		self.menu_memb.addAction(act_memb_strip)
		self.menu_memb.addAction(act_memb_suff)		
		
		# - Build 	
		self.lay_grid = QtGui.QGridLayout()
		self.lay_grid.addWidget(lbl_name,		 		0, 0, 1, 48)
		self.lay_grid.addWidget(self.tab_groupKern,		1, 0, 8, 42)
		self.lay_grid.addWidget(self.btn_export,		1, 42, 1, 3)
		self.lay_grid.addWidget(self.btn_import,		1, 45, 1, 3)
		self.lay_grid.addWidget(self.btn_fromFont,		2, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_fromComp,		3, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_reset,			7, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_apply,			8, 42, 1, 6)

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
	def class_find_replace(self):
		search = QtGui.QInputDialog.getText(self, 'Find and replace class names', 'Please enter SPACE separated pair:\n(SEARCH_string) (REPLACE_string).', QtGui.QLineEdit.Normal, 'Find Replace')
		mod_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

		find, replace = search.split()

		for row in range(self.tab_groupKern.rowCount):
			currItem = self.tab_groupKern.item(row, 0)
			
			if len(mod_keys) and currItem.text() in mod_keys:
					currItem.setText(currItem.text().replace(find, replace))

		self.update_data(self.tab_groupKern.getTable(), False)
		print 'DONE:\t Search and replace in class names.'

	def class_del(self):
		temp_data = self.tab_groupKern.getTable()
		del_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

		for key in del_keys: temp_data.pop(key, None)
			
		self.update_data(temp_data)
		print 'DONE:\t Removed Classes: %s'  %(', '.join(del_keys))

	def class_copy(self):
		prefix = QtGui.QInputDialog.getText(self, 'Duplicate classes', 'Please enter prefix for the new classes.', QtGui.QLineEdit.Normal, 'copy_')

		if len(prefix):
			temp_data = self.tab_groupKern.getTable()
			dup_keys = [self.tab_groupKern.item(row, 0).text() for row, col in self.tab_groupKern.getSelection()]

			for key in dup_keys:
				temp_data[prefix + key] = temp_data[key]
				print 'DONE:\t Class: %s; Duplicated with prefix: %s.' %(key, prefix)

			self.update_data(temp_data)

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

				self.update_data(temp_data)
		

	def set_type(self, typeStr):
		for row, col in self.tab_groupKern.getSelection():
			self.tab_groupKern.item(row, 1).setText(typeStr)
			print 'DONE:\t Class: %s; Type set to: %s.' %(self.tab_groupKern.item(row, 0).text(), typeStr)

		self.update_data(self.tab_groupKern.getTable(), False)

	def memb_cleanup(self):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = ' '.join(sorted(list(set(old_data.split()))))
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; Members cleanup.' %self.tab_groupKern.item(row, 0).text()

		self.update_data(self.tab_groupKern.getTable(), False)

	def memb_stripSuffix(self):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = ' '.join([item.split(alt_mark)[0] for item in old_data.split()])
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; All suffixes removed from members.' %self.tab_groupKern.item(row, 0).text()

		self.update_data(self.tab_groupKern.getTable(), False)

	def memb_addSuffix(self):
		suffix = QtGui.QInputDialog.getText(self, 'Add suffix', 'Please enter Suffix for all class members.')

		if len(suffix):
			for row, col in self.tab_groupKern.getSelection():
				old_data = self.tab_groupKern.item(row, 2).text()
				new_data = ' '.join([item + suffix for item in old_data.split()])
				self.tab_groupKern.item(row, 2).setText(new_data)
				print 'DONE:\t Class: %s; New suffix (%s) added to members.' %(self.tab_groupKern.item(row, 0).text(), suffix)

			self.update_data(self.tab_groupKern.getTable(), False)

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

		self.kern_group_data = self.tab_groupKern.getTable()
		print 'DONE:\t Class: %s; Members change case.' %self.tab_groupKern.item(row, 0).text()

	# - Main Procedures --------------------------------------------
	def update_data(self, source, updateTable=True):
		self.kern_group_data = source
		
		if updateTable:	
			self.tab_groupKern.clear()
			while self.tab_groupKern.rowCount > 0: self.tab_groupKern.removeRow(0)
			self.tab_groupKern.setTable(source)

	def apply_changes(self):
		self.kern_group_data = self.tab_groupKern.getTable()
		self.active_font.dict_to_kerning_groups(self.kern_group_data)
		
		print 'DONE:\t Font: %s - Kerning classes updated.' %self.active_font.name

	def reset_classes(self):
		self.active_font.reset_kerning_groups()
		print 'DONE:\t Font: %s - Kerning classes removed.' %self.active_font.name

	def export_groups(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save kerning classes to file', fontPath , '*.json')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tab_groupKern.getTable(), exportFile)

			print 'SAVE:\t Font:%s; Group Kerning classes saved to: %s.' %(self.active_font.name, fname)

	def import_groups(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upper_widget, 'Load kerning classes from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.update_data(json.load(importFile))			

			print 'LOAD:\t Font:%s; Group Kerning classes loaded from: %s.' %(self.active_font.name, fname)

	def from_composites(self):
		# - Init
		font_workset_names = [glyph.name for glyph in self.active_font.uppercase()] + [glyph.name for glyph in self.active_font.lowercase()] + [glyph.name for glyph in self.active_font.alternates()]
		ban_list = ['sups', 'subs', 'ss10', 'ss09', 'ss08', 'dnom', 'numr', 'notdef']
		class_dict = {}

		# - Process
		process_glyphs = self.active_font.pGlyphs()
		
		for glyph in process_glyphs:
			if all([banned_item not in glyph.name for banned_item in ban_list]):
				layer = '100'
				clear_comp = [comp.shapeData.name for comp in glyph.shapes(layer) + glyph.components(layer) if comp.shapeData.name in font_workset_names and comp.shapeData.name != glyph.name]
				
				if len(clear_comp) == 1:
					class_dict.setdefault(clear_comp[0], set([clear_comp[0]])).add(glyph.name)

				if len(clear_comp) == 0 and alt_mark in glyph.name:
					class_dict.setdefault(glyph.name.split(alt_mark)[0], set([glyph.name.split(alt_mark)[0]])).add(glyph.name)

				if len(clear_comp) > 1:
					print 'WARN:\t Glyph: %s; Multiple components: %s' %(glyph.name, clear_comp)
		
		for key, value in class_dict.iteritems():
			self.kern_group_data['%s_L' %key] = (sorted(value), 'KernLeft')
			self.kern_group_data['%s_R' %key] = (sorted(value), 'KernRight')

			#print 'ADD:\t 1st and 2nd Classes: %s -> %s' %(key, ' '.join(sorted(value)))

		# - Finish
		self.tab_groupKern.setTable(self.kern_group_data)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		layoutV = QtGui.QVBoxLayout()
		
		self.kernGroups = WKernGroups(self)
		self.ActionsMenu = QtGui.QMenuBar()

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