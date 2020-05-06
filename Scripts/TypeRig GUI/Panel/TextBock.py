#FLM: TR: Text Block
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import cPickle, os

import fontlab as fl6
import fontgate as fgt

from typerig.proxy import *

from PythonQt import QtCore
from typerig.gui import QtGui

# - Init --------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_version = '0.07'
app_name = 'Text Block Control'

text_align = 'Left Right Center'.split(' ')
page_sizes = { 
			'Letter':(612, 792),
			'Tabloid':(792, 1224), 
			'Ledger':(1224, 792), 
			'Legal':(612, 1008), 
			'Statement':(396, 612), 
			'Executive':(540, 720), 
			'A0':(2384, 3371), 
			'A1':(1685, 2384), 
			'A2':(1190, 1684), 
			'A3':(842, 1190), 
			'A4':(595, 842), 
			'A5':(420, 595), 
			'B4':(729, 1032), 
			'B5':(516, 729), 
			'Folio':(612, 936), 
			'Quarto':(610, 780),
			'A0.96':(3179, 4494),
			'A1.96':(2245, 3179),
			'A2.96':(1587, 2245),
			'A3.96':(1123, 1587),
			'A4.96':(794, 1123),
			'A5.96':(559, 794),
			'A6.96':(397, 559),
			'A7.96':(280, 397),
			'A8.96':(197, 280),
			'A9.96':(140, 197)
			}

class TRTextBlockSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(TRTextBlockSelect, self).__init__()

		# -- Head
		self.lay_head = QtGui.QHBoxLayout()
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_refresh.clicked.connect(self.refresh)

		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)

		# -- TextBlock List
		self.lst_textBlocks = QtGui.QListWidget()
		self.lst_textBlocks.setAlternatingRowColors(True)
		self.lst_textBlocks.setMinimumHeight(100)
		self.lst_textBlocks.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.addWidget(self.lst_textBlocks)

	def refresh(self):
		# - Init
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas() 
		self.active_textBlockList = self.active_workspace.getTextBlockList()

		# - Build List and style it
		self.lst_textBlocks.clear()
		self.lst_textBlocks.addItems(['T: %s...\tG: %s\tS: %s pt\t F: %s'.expandtabs(12) %(item.symbolList().string(True)[:10], item.glyphsCount(), item.fontSize, item.frameRect) for item in self.active_textBlockList])		

	def doCheck(self):
		pass

class TRTextBlockBasic(QtGui.QVBoxLayout):
	def __init__(self, aux, upperWidget):
		super(TRTextBlockBasic, self).__init__()

		# - Init
		self.aux = aux
		#self.activeFont = pFont()
		self.upperWidget = upperWidget
		
		'''
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas() 
		self.active_textBlock = pTextBlock(self.active_workspace.getTextBlockList()[0])
		'''

		# - Widgets
		self.chk_page = QtGui.QCheckBox('Page size:')
		self.chk_size = QtGui.QCheckBox('Width/Height:')
		self.chk_pos = QtGui.QCheckBox('Position X/Y:')
		self.chk_align = QtGui.QCheckBox('Text alignment:')
		self.chk_kegel = QtGui.QCheckBox('Font Size:')
		
		self.chk_page.setCheckState(QtCore.Qt.Checked)
		self.chk_size.setCheckState(QtCore.Qt.Checked) 
		#self.chk_pos.setCheckState(QtCore.Qt.Checked) 
		#self.chk_align.setCheckState(QtCore.Qt.Checked) 
		self.chk_kegel.setCheckState(QtCore.Qt.Checked) 
		
		self.cmb_pageSizes = QtGui.QComboBox()
		self.cmb_text_align = QtGui.QComboBox()
		
		self.cmb_pageSizes.addItems(sorted(page_sizes.keys()))
		self.cmb_text_align.addItems(text_align)

		self.cmb_pageSizes.currentTextChanged.connect(self.page_changed)
		self.cmb_text_align.currentTextChanged.connect(self.algn_changed)

		self.spb_font_size = QtGui.QSpinBox()
		self.spb_font_size.setSuffix(' pt')
		self.spb_font_size.setValue(12)

		self.spb_size_w = QtGui.QSpinBox()
		self.spb_size_h = QtGui.QSpinBox()
		self.spb_pos_x = QtGui.QSpinBox()
		self.spb_pos_y = QtGui.QSpinBox()

		self.spb_size_w.setMaximum(9999)
		self.spb_size_h.setMaximum(9999)
		self.spb_pos_x.setMaximum(9999)
		self.spb_pos_y.setMaximum(9999)
		self.spb_pos_x.setMinimum(-9999)
		self.spb_pos_y.setMinimum(-9999)

		self.spb_size_w.setValue(page_sizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(page_sizes[self.cmb_pageSizes.currentText][1])

		self.btn_apply = QtGui.QPushButton('Set Text Block(s)')
		self.btn_clone = QtGui.QPushButton('Clone')
		self.btn_lock = QtGui.QPushButton('Lock')
		self.btn_reformat = QtGui.QPushButton('Reformat')
		self.btn_remove = QtGui.QPushButton('Remove')
		self.btn_stack_v = QtGui.QPushButton('Stack Vertically')
		self.btn_stack_h = QtGui.QPushButton('Stack Horizontally')
		#self.btn_save = QtGui.QPushButton('Save Layout')
		#self.btn_load = QtGui.QPushButton('Load Layout')

		self.btn_apply.clicked.connect(lambda: self.block_action('format'))
		self.btn_clone.clicked.connect(lambda: self.block_action('clone'))
		self.btn_remove.clicked.connect(lambda: self.block_action('remove'))
		self.btn_lock.clicked.connect(lambda: self.block_action('lock'))
		self.btn_reformat.clicked.connect(lambda: self.block_action('reformat'))
		self.btn_stack_v.clicked.connect(lambda: self.block_action('stack_v'))
		self.btn_stack_h.clicked.connect(lambda: self.block_action('stack_h'))
		#self.btn_save.clicked.connect(self.save) 
		#self.btn_load.clicked.connect(self.load) 

		# - Disable for now
		self.cmb_text_align.setEnabled(False)
		self.chk_align.setEnabled(False)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Text Block: Formatting'),		0, 0, 1, 4)
		layoutV.addWidget(self.chk_page,			1, 0, 1, 2)
		layoutV.addWidget(self.cmb_pageSizes, 		1, 2, 1, 2)
		layoutV.addWidget(self.chk_size,			2, 0, 1, 2)
		layoutV.addWidget(self.spb_size_w, 			2, 2, 1, 1)
		layoutV.addWidget(self.spb_size_h, 			2, 3, 1, 1)
		layoutV.addWidget(self.chk_pos,				3, 0, 1, 2)
		layoutV.addWidget(self.spb_pos_x, 			3, 2, 1, 1)
		layoutV.addWidget(self.spb_pos_y, 			3, 3, 1, 1)
		layoutV.addWidget(self.chk_align,			4, 0, 1, 2)
		layoutV.addWidget(self.cmb_text_align, 		4, 2, 1, 2)
		layoutV.addWidget(self.chk_kegel,			5, 0, 1, 2)
		layoutV.addWidget(self.spb_font_size,		5, 2, 1, 2)
		layoutV.addWidget(self.btn_apply, 			6, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Text Block: Tools'),		7, 0, 1, 4)
		layoutV.addWidget(self.btn_clone, 			8, 0, 1, 2)
		layoutV.addWidget(self.btn_remove, 			8, 2, 1, 2)
		layoutV.addWidget(self.btn_lock, 			9, 0, 1, 2)
		layoutV.addWidget(self.btn_reformat, 		9, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Text Block: Alignment'),		10, 0, 1, 4)
		layoutV.addWidget(self.btn_stack_h, 		11, 0, 1, 2)
		layoutV.addWidget(self.btn_stack_v, 		11, 2, 1, 2)
		'''
		layoutV.addWidget(QtGui.QLabel('Text Block: Layout'),		12, 0, 1, 4)
		layoutV.addWidget(self.btn_save, 		13, 0, 1, 2)
		layoutV.addWidget(self.btn_load, 		13, 2, 1, 2)
		'''

		# - Set Widget
		self.addLayout(layoutV)

	def page_changed(self):
		self.spb_size_w.setValue(page_sizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(page_sizes[self.cmb_pageSizes.currentText][1])

	def algn_changed(self,value):
		pass

	def block_action(self, mode):
		# - Init
		accumulator = 0.
		leader = 0.
		first_run = True

		# - Process
		for selectedItem in self.aux.lst_textBlocks.selectedIndexes():
			processBlock = self.aux.active_textBlockList[selectedItem.row()]

			if mode == 'format':
				processBlockAdv = pTextBlock(processBlock)
				
				if self.chk_size.isChecked(): 
					processBlockAdv.setFrameSize(self.spb_size_w.value, self.spb_size_h.value)
					processBlockAdv.setWrapState()
					processBlockAdv.fl.setFixedHeight(True, True)
				
				if self.chk_pos.isChecked(): processBlockAdv.reloc(self.spb_pos_x.value, self.spb_pos_y.value)
				if self.chk_kegel.isChecked(): processBlockAdv.setFontSize(self.spb_font_size.value)
				
				processBlockAdv.update()

			elif mode == 'clone':
				clonedBlock = processBlock.clone()
				print processBlock == clonedBlock
				self.aux.active_canvas.addTextBlock(clonedBlock)

			elif mode == 'remove':
				self.aux.active_canvas.removeTextBlock(processBlock)

			elif mode == 'lock':
				processBlock.locked = not processBlock.locked
				processBlock.update()

			elif mode == 'reformat':
				processBlock.reformat()
				processBlock.update()

			elif mode == 'stack_v':
				processBlockAdv = pTextBlock(processBlock)
				#if first_run: leader = processBlockAdv.y(); first_run = False
				processBlockAdv.reloc(leader, accumulator)
				accumulator += processBlockAdv.x() + processBlockAdv.height()

			elif mode == 'stack_h':
				processBlockAdv = pTextBlock(processBlock)
				#if first_run: leader = processBlockAdv.x(); first_run = False
				processBlockAdv.reloc(accumulator, leader)
				accumulator += processBlockAdv.y() + processBlockAdv.width()
				

		self.aux.active_canvas.update()
		self.aux.refresh()

	'''
	# !!! FL Objects cannot be pickled. To Do Later!
	def save(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upperWidget, 'Save Text Block layout', fontPath , '*.cp')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				cPickle.dump(self.aux.active_workspace.getTextBlockList(), exportFile)

			print 'SAVE:\t Font:%s; Layout saved to %s.' %(self.activeFont.name, fname)

	def load(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upperWidget, 'Load Text Block layout from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				loadedData = cPickle.load(importFile)

			for item in loadedData:
				print item

			print 'LOAD:\t Font:%s; Layout loaded from %s.' %(self.activeFont.name, fname)
	'''
		
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		self.blockSelector = TRTextBlockSelect()
		self.basicTools = TRTextBlockBasic(self.blockSelector, self)
		
		layoutV.addLayout(self.blockSelector)
		layoutV.addLayout(self.basicTools)
		
		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()