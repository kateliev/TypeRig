#FLM: Text: Layout (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

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

# -- Strings
class dlg_textFormat(QtGui.QDialog):
	def __init__(self):
		super(dlg_textFormat, self).__init__()
	
		# - Init
		self.active_workspace = pWorkspace()
		self.active_canvas = self.active_workspace.getCanvas() 
		self.active_textBlock = pTextBlock(self.active_workspace.getTextBlockList()[0])

		# - Widgets
		self.cmb_textBox = QtGui.QComboBox()
		self.cmb_pageSizes = QtGui.QComboBox()
		self.cmb_text_align = QtGui.QComboBox()
		
		self.cmb_textBox.addItems([tb.id for tb in self.active_workspace.getTextBlockList()])
		self.cmb_pageSizes.addItems(sorted(self.active_textBlock.pageSizes.keys()))
		self.cmb_text_align.addItems(text_align)

		self.cmb_textBox.currentIndexChanged.connect(self.block_changed)
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

		self.btn_refresh = QtGui.QPushButton('Refresh list')
		self.btn_apply = QtGui.QPushButton('Set Text Box')
		self.btn_waterfall = QtGui.QPushButton('Build Waterfall')
		
		self.btn_apply.clicked.connect(self.block_apply)
		self.btn_refresh.clicked.connect(self.block_refresh)
		self.btn_waterfall.clicked.connect(self.block_waterfall)

		# - Disable for now
		self.edt_font_waterfall.setEnabled(False)
		self.btn_waterfall.setEnabled(False)
		self.cmb_text_align.setEnabled(False)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Text Blocks on canvas:'),	0, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Selected block:'),			1, 0, 1, 2)
		layoutV.addWidget(self.cmb_textBox,						1, 2, 1, 2)
		layoutV.addWidget(self.btn_refresh, 					2, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('\nSelected block: Formatting'),	3, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Page Size:'),			4, 0, 1, 2)
		layoutV.addWidget(self.cmb_pageSizes, 					4, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Width/Height:'),		5, 0, 1, 2)
		layoutV.addWidget(self.spb_size_w, 						5, 2, 1, 1)
		layoutV.addWidget(self.spb_size_h, 						5, 3, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Text alignment:'),		6, 0, 1, 2)
		layoutV.addWidget(self.cmb_text_align, 					6, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Font Size:'),			7, 0, 1, 2)
		layoutV.addWidget(self.spb_font_size,					7, 2, 1, 2)
		layoutV.addWidget(self.btn_apply, 						8, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('\nSelected block: Waterfall'),	9, 0, 1, 4)
		layoutV.addWidget(self.edt_font_waterfall,				10, 0, 1, 4)
		layoutV.addWidget(self.btn_waterfall,					11, 0, 1, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 120)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def block_changed(self, value):
		self.active_textBlock = pTextBlock(self.active_workspace.getTextBlockList()[value])

	def page_changed(self):
		self.spb_size_w.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][1])

	def algn_changed(self,value):
		pass

	def block_refresh(self):
		self.cmb_textBox.clear()
		self.cmb_textBox.addItems([tb.id for tb in self.active_workspace.getTextBlockList()])

	def block_apply(self):
		self.active_textBlock.setFrameSize(self.spb_size_w.value, self.spb_size_h.value)
		self.active_textBlock.setWrapState()
		self.active_textBlock.fl.setFixedHeight(True, True)
		self.active_textBlock.setFontSize(self.spb_font_size.value)
		self.active_textBlock.update()

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
			

	
# - RUN ------------------------------
dialog = dlg_textFormat()