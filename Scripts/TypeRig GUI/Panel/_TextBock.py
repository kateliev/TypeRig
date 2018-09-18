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
app_version = '0.02'
app_name = 'Text Block Control'
text_align = 'Left Right Center'.split(' ')

class QTextBlockSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QTextBlockSelect, self).__init__()

		# - Init

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
		self.refresh()

	def refresh(self):
		# - Init
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas() 
		self.active_textBlockList = self.active_workspace.getTextBlockList()

		# - Build List and style it
		self.lst_textBlocks.clear()
		self.lst_textBlocks.addItems(['T: %s...\tG: %s'%(item.symbolList().string(True)[:10], item.glyphsCount()) for item in self.active_textBlockList])		
				

	def doCheck(self):
		pass

class QTextBlockBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QTextBlockBasic, self).__init__()

		# - Init
		self.aux = aux
		self.active_textBlock = pTextBlock(self.aux.active_textBlockList[0])

		# - Widgets
		self.cmb_pageSizes = QtGui.QComboBox()
		self.cmb_text_align = QtGui.QComboBox()
		
		self.cmb_pageSizes.addItems(sorted(self.active_textBlock.pageSizes.keys()))
		self.cmb_text_align.addItems(text_align)

		self.cmb_pageSizes.currentTextChanged.connect(self.page_changed)
		self.cmb_text_align.currentTextChanged.connect(self.algn_changed)

		self.edt_font_waterfall = QtGui.QLineEdit()
		self.edt_font_waterfall.setPlaceholderText('Waterfall point sizes')

		self.spb_font_size = QtGui.QSpinBox()
		self.spb_font_size.setSuffix(' pt')
		self.spb_font_size.setValue(12)

		self.spb_size_w = QtGui.QSpinBox()
		self.spb_size_h = QtGui.QSpinBox()
		self.spb_size_w.setMaximum(9999)
		self.spb_size_h.setMaximum(9999)
		self.spb_size_w.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][1])

		self.spb_y = QtGui.QSpinBox()

		self.btn_apply = QtGui.QPushButton('Set Text Block(s)')
		self.btn_waterfall = QtGui.QPushButton('Build Waterfall')
		
		self.btn_apply.clicked.connect(self.block_apply)
		self.btn_waterfall.clicked.connect(self.block_waterfall)

		# - Disable for now
		self.edt_font_waterfall.setEnabled(False)
		self.btn_waterfall.setEnabled(False)
		self.cmb_text_align.setEnabled(False)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Block Formatting'),		0, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Page Size:'),			1, 0, 1, 2)
		layoutV.addWidget(self.cmb_pageSizes, 					1, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Width/Height:'),		2, 0, 1, 2)
		layoutV.addWidget(self.spb_size_w, 						2, 2, 1, 1)
		layoutV.addWidget(self.spb_size_h, 						2, 3, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Text alignment:'),		3, 0, 1, 2)
		layoutV.addWidget(self.cmb_text_align, 					3, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Font Size:'),			4, 0, 1, 2)
		layoutV.addWidget(self.spb_font_size,					4, 2, 1, 2)
		layoutV.addWidget(self.btn_apply, 						5, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Text Waterfall'),		6, 0, 1, 4)
		layoutV.addWidget(self.edt_font_waterfall,				7, 0, 1, 4)
		layoutV.addWidget(self.btn_waterfall,					8, 0, 1, 4)

		# - Set Widget
		self.addLayout(layoutV)

	def page_changed(self):
		self.spb_size_w.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][1])

	def algn_changed(self,value):
		pass

	def block_apply(self):
		for selectedItem in self.aux.lst_textBlocks.selectedIndexes():
			processBlock = pTextBlock(self.aux.active_textBlockList[selectedItem.row()])
			processBlock.setFrameSize(self.spb_size_w.value, self.spb_size_h.value)
			processBlock.setWrapState()
			processBlock.fl.setFixedHeight(True, True)
			processBlock.setFontSize(self.spb_font_size.value)
			processBlock.update()

	def block_waterfall(self):
		pointList = [int(item) for item in self.edt_font_waterfall.text.replace(' ', '').split(',')]

		# - Process: original block first
		self.active_textBlock.resetTransform()
		self.active_textBlock.setFontSize(pointList.pop(0))
		self.active_textBlock.fl.setFixedHeight(True, True)
		self.active_textBlock.setFrameWidth(float(self.spb_size_w.value))
		self.active_textBlock.setWrapState()
		self.active_textBlock.update()

		# - Process: Build additional blocks
		currentY = self.active_textBlock.y() + self.active_textBlock.height()
		
		for ptSize in pointList:
			# - Init new clone
			clonedBlock = self.active_textBlock.clone()
			self.active_canvas.addTextBlock(clonedBlock)
			print clonedBlock.frameRect
			clonedBlock.setFrameWidth(float(self.spb_size_w.value))
			#clonedBlock.formatMode = True
			#clonedBlock.setFixedHeight(True,True)
			#clonedBlock.locked = True
			clonedBlock.fontSize = ptSize
			clonedBlock.reformat()
			clonedBlock.formatChanged()
			
			# - Reposition
			oldRect = clonedBlock.frameRect
			oldRect.setX(self.active_textBlock.x())
			oldRect.setY(currentY)
			clonedBlock.frameRect = oldRect
			clonedBlock.update()
			print clonedBlock.frameRect

			currentY += clonedBlock.frameRect.x() + clonedBlock.frameRect.height()

			
			#clonedBlock.reloc(self.active_textBlock.x(), currentY)
			#clonedBlock.setFontSize(ptSize)
			#currentY += clonedBlock.height()
			
		
		self.active_canvas.update()
		
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