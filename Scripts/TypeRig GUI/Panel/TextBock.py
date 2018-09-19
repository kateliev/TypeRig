#FLM: TAB TextBlock Tools
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy import pWorkspace, pTextBlock

# - Init --------------------------------
app_version = '0.04'
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

class QTextBlockSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QTextBlockSelect, self).__init__()

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

class QTextBlockBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QTextBlockBasic, self).__init__()

		# - Init
		self.aux = aux

		# - Widgets
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas() 
		self.active_textBlock = pTextBlock(self.active_workspace.getTextBlockList()[0])

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

		self.btn_apply.clicked.connect(lambda: self.block_action('format'))
		self.btn_clone.clicked.connect(lambda: self.block_action('clone'))
		self.btn_remove.clicked.connect(lambda: self.block_action('remove'))
		self.btn_lock.clicked.connect(lambda: self.block_action('lock'))
		self.btn_reformat.clicked.connect(lambda: self.block_action('reformat'))
		self.btn_stack_v.clicked.connect(lambda: self.block_action('stack_v'))
		self.btn_stack_h.clicked.connect(lambda: self.block_action('stack_h'))

		# - Disable for now
		self.cmb_text_align.setEnabled(False)
		self.chk_align.setEnabled(False)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Block Formatting'),		0, 0, 1, 4)
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
		layoutV.addWidget(QtGui.QLabel('Block Tools'),		7, 0, 1, 4)
		layoutV.addWidget(self.btn_clone, 			8, 0, 1, 2)
		layoutV.addWidget(self.btn_remove, 			8, 2, 1, 2)
		layoutV.addWidget(self.btn_lock, 			9, 0, 1, 2)
		layoutV.addWidget(self.btn_reformat, 		9, 2, 1, 2)
		layoutV.addWidget(self.btn_stack_h, 		10, 0, 1, 2)
		layoutV.addWidget(self.btn_stack_v, 		10, 2, 1, 2)


		# - Set Widget
		self.addLayout(layoutV)

	def page_changed(self):
		self.spb_size_w.setValue(page_sizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(page_sizes[self.cmb_pageSizes.currentText][1])

	def algn_changed(self,value):
		pass

	def block_action(self, mode):
		for selectedItem in self.aux.lst_textBlocks.selectedIndexes():
			processBlock = self.aux.active_textBlockList[selectedItem.row()]

			if mode == 'format':
				processBlockAdv = pTextBlock(self.aux.active_textBlockList[selectedItem.row()])
				
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

		self.aux.active_canvas.update()
		self.aux.refresh()
		
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		self.blockSelector = QTextBlockSelect()
		self.basicTools = QTextBlockBasic(self.blockSelector)
		
		layoutV.addLayout(self.blockSelector)
		layoutV.addLayout(self.basicTools)
		
		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 250, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()