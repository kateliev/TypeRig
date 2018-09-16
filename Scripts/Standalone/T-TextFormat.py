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
app_version = '0.01'
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

		self.spb_font_size = QtGui.QSpinBox()
		self.spb_font_size.setSuffix(' pt')
		self.spb_font_size.setValue(12)

		self.spb_size_w = QtGui.QSpinBox()
		self.spb_size_h = QtGui.QSpinBox()
		self.spb_size_w.setMaximum(9999)
		#self.spb_size_w.setSuffix(' px')
		self.spb_size_h.setMaximum(9999)
		#self.spb_size_h.setSuffix(' px')
		self.spb_size_w.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][0])
		self.spb_size_h.setValue(self.active_textBlock.pageSizes[self.cmb_pageSizes.currentText][1])


		self.spb_y = QtGui.QSpinBox()

		self.btn_refresh = QtGui.QPushButton('Refresh')
		self.btn_apply = QtGui.QPushButton('Set Text Box')
		#self.btn_apply.clicked.connect(self.applyTransform)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Formatting options:'),	0, 0, 1, 4)
		layoutV.addWidget(QtGui.QLabel('Text Box:'),			1, 0, 1, 2)
		layoutV.addWidget(self.cmb_textBox,						1, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Page Size:'),			2, 0, 1, 2)
		layoutV.addWidget(self.cmb_pageSizes, 					2, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Width/Height:'),		3, 0, 1, 2)
		layoutV.addWidget(self.spb_size_w, 						3, 2, 1, 1)
		layoutV.addWidget(self.spb_size_h, 						3, 3, 1, 1)
		layoutV.addWidget(QtGui.QLabel('Text alignment:'),		4, 0, 1, 2)
		layoutV.addWidget(self.cmb_text_align, 					4, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Font Size:'),			5, 0, 1, 2)
		layoutV.addWidget(self.spb_font_size,					5, 2, 1, 2)
		layoutV.addWidget(self.btn_refresh, 					6, 0, 1, 2)
		layoutV.addWidget(self.btn_apply, 						6, 2, 1, 2)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 120)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	

	
# - RUN ------------------------------
dialog = dlg_textFormat()