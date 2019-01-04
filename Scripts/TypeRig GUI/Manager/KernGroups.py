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
app_name, app_version = 'TypeRig | Kern Classes', '0.9'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont

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

	def setTable(self, data, indexColCheckable=None):
		# - Init
		name_row, name_column = [], ['Class Name', 'Class Type', 'Class Members']
		
		self.blockSignals(True)

		self.setColumnCount(len(name_column))
		self.setRowCount(len(data.keys()))

		# - Populate
		for row, key in enumerate(data.keys()):
			'''
			# - Combo and check boxes !!
			name_row.append(key)
								
			item_groupName = QtGui.QTableWidgetItem(str(key))
			_item_groupPos = QtGui.QTableWidgetItem(str(data[key][1]))
			
			item_groupPos = QtGui.QComboBox()
			item_groupPos.addItems(self.kern_pos_mods)
			item_groupPos.setCurrentIndex(self.kern_pos_mods.index(str(data[key][1])))

			item_groupMem = QtGui.QTableWidgetItem(' '.join(data[key][0]))
														
			item_groupName.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
			item_groupName.setCheckState(QtCore.Qt.Unchecked) 

			self.setItem(row, 0, item_groupName)
			self.setCellWidget(row, 1, item_groupPos)
			self.setItem(row, 2, item_groupMem)
			'''
			# - Simple table
			name_row.append(key)
								
			item_groupName = QtGui.QTableWidgetItem(str(key))
			item_groupPos = QtGui.QTableWidgetItem(str(data[key][1]))
			item_groupMem = QtGui.QTableWidgetItem(' '.join(data[key][0]))

			#item_groupName.setTextAlignment(QtCore.Qt.AlignTop)
			#item_groupPos.setTextAlignment(QtCore.Qt.AlignTop)
			#item_groupMem.setTextAlignment(QtCore.Qt.AlignTop)
														
			#item_groupName.setFlags(QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
			#item_groupName.setCheckState(QtCore.Qt.Unchecked) 

			self.setItem(row, 0, item_groupName)
			self.setItem(row, 1, item_groupPos)
			self.setItem(row, 2, item_groupMem)

		self.setHorizontalHeaderLabels(name_column)
		self.blockSignals(False)

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
		self.btn_import = QtGui.QPushButton('Import')
		self.btn_export = QtGui.QPushButton('Export')
		self.btn_fromFont = QtGui.QPushButton('Populate from Font')
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
		act_class_copy = QtGui.QAction('Duplicate', self)
		act_class_merge = QtGui.QAction('Merge to new', self)
		act_class_mdel = QtGui.QAction('Merge and remove', self)
		act_class_del = QtGui.QAction('Remove', self)

		self.menu_class.addAction(act_class_copy)
		self.menu_class.addAction(act_class_merge)
		self.menu_class.addAction(act_class_mdel)
		self.menu_class.addAction(act_class_del)
		
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
		act_memb_sel = QtGui.QAction('Select', self)
		act_memb_clean = QtGui.QAction('Cleanup', self)
		act_memb_upper = QtGui.QAction('Members to uppercase', self)
		act_memb_lower = QtGui.QAction('Members to lowercase', self)
		act_memb_strip = QtGui.QAction('Strip member suffixes', self)
		act_memb_suff = QtGui.QAction('Add suffix to members', self)

		act_memb_clean.triggered.connect(lambda: self.memb_cleanup())

		self.menu_memb.addAction(act_memb_sel)
		self.menu_memb.addAction(act_memb_clean)
		self.menu_memb.addAction(act_memb_upper)
		self.menu_memb.addAction(act_memb_lower)
		self.menu_memb.addAction(act_memb_strip)
		self.menu_memb.addAction(act_memb_suff)		
		
		# - Toolbar
		# Note: Disabled for now
		'''
		self.tbar_actions = QtGui.QToolBar('Class Actions', self)
		self.tbar_actions.setOrientation(QtCore.Qt.Vertical)

		for action in self.menu_class.actions() + self.menu_type.actions() + self.menu_memb.actions():
			self.tbar_actions.addAction(action)

		for i in range(self.tbar_actions.layout().count()):
			self.tbar_actions.layout().itemAt(i).setAlignment(QtCore.Qt.AlignLeft)

		for i in [self.menu_type.actions()[0], self.menu_memb.actions()[0]]:
			self.tbar_actions.insertSeparator(i)\
		'''

		# - Build 	
		self.lay_grid = QtGui.QGridLayout()
		self.lay_grid.addWidget(lbl_name,		 		0, 0, 1, 48)
		self.lay_grid.addWidget(self.tab_groupKern,		1, 0, 8, 42)
		self.lay_grid.addWidget(self.btn_export,		1, 42, 1, 3)
		self.lay_grid.addWidget(self.btn_import,		1, 45, 1, 3)
		self.lay_grid.addWidget(self.btn_fromFont,		2, 42, 1, 6)
		self.lay_grid.addWidget(self.btn_fromComp,		3, 42, 1, 6)
		#self.lay_grid.addWidget(lbl_act,				4, 42, 1, 6)
		#self.lay_grid.addWidget(self.tbar_actions,		5, 42, 1, 6)
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
	def set_type(self, typeStr):
		for row, col in self.tab_groupKern.getSelection():
			self.tab_groupKern.item(row, 1).setText(typeStr)
			print 'DONE:\t Class: %s; Type set to: %s.' %(self.tab_groupKern.item(row, 0).text(), typeStr)

	def memb_cleanup(self):
		for row, col in self.tab_groupKern.getSelection():
			old_data = self.tab_groupKern.item(row, 2).text()
			new_data = ' '.join(sorted(list(set(old_data.split()))))
			self.tab_groupKern.item(row, 2).setText(new_data)
			print 'DONE:\t Class: %s; Members cleanup.' %self.tab_groupKern.item(row, 0).text()

	# - Main Procedures --------------------------------------------
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
				self.kern_group_data = json.load(importFile)

			self.tab_groupKern.setTable(self.kern_group_data)

			print 'LOAD:\t Font:%s; Group Kerning classes loaded from: %s.' %(self.active_font.name, fname)

	def from_composites(self):
		# - Init
		font_workset_names = [glyph.name for glyph in self.active_font.uppercase()] + [glyph.name for glyph in self.active_font.lowercase()] + [glyph.name for glyph in self.active_font.alternates()]
		ban_list = ['sups', 'subs', 'ss10', 'ss09', 'ss08', 'dnom', 'numr', 'notdef']
		alt_mark = '.'
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

			print 'ADD:\t 1st and 2nd Classes: %s -> %s' %(key, ' '.join(sorted(value)))

		# - Finish
		self.tab_groupKern.setTable(self.kern_group_data)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		layoutV = QtGui.QVBoxLayout()
		self.kernGroups = WKernGroups(self)
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