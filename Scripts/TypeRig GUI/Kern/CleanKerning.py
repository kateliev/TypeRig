#FLM: TR: Kerning cleanup
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Cleanup', '1.1'

# - Dependencies -----------------
from os import path
import fontlab as fl6
import fontgate as fgt

from typerig.proxy import *

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import getProcessGlyphs

# - Sub widgets ------------------------
class TRkernClean(QtGui.QGridLayout):
	# - Curve optimization
	def __init__(self):
		super(TRkernClean, self).__init__()
		# - Basic operations
		self.btn_font_refresh = QtGui.QPushButton('Refresh')
		self.btn_exceptions_report = QtGui.QPushButton('Report')
		self.btn_exceptions_remove = QtGui.QPushButton('Clear')
		self.btn_exceptions_flats = QtGui.QPushButton('Report Extendable Flat Pairs')

		self.cmb_all_fonts = QtGui.QComboBox()
		self.cmb_layers = QtGui.QComboBox()

		self.spn_exceptions_delta = QtGui.QSpinBox()
		self.spn_exceptions_delta.setValue(5)
		self.spn_exceptions_delta.setMaximum(1000)
		
		self.btn_exceptions_report.setToolTip('Report exceptions of class kerning within value given')
		self.btn_exceptions_remove.setToolTip('Remove exceptions of class kerning within value given')

		self.btn_font_refresh.clicked.connect(self.fonts_refresh)
		self.cmb_all_fonts.currentIndexChanged.connect(self.fonts_changed)
		self.btn_exceptions_report.clicked.connect(lambda: self.kern_exceptions(False, False))
		self.btn_exceptions_remove.clicked.connect(lambda: self.kern_exceptions(True, False))
		self.btn_exceptions_flats.clicked.connect(lambda: self.kern_exceptions(False, True))

		# -- Build
		self.addWidget(QtGui.QLabel('Process Font:'),				0, 0, 1, 6)
		self.addWidget(self.cmb_all_fonts, 							1, 0, 1, 5)
		self.addWidget(self.btn_font_refresh, 						1, 5, 1, 1)
		self.addWidget(QtGui.QLabel('\nKerning: Flat pairs'), 		2, 0, 1, 6)
		self.addWidget(self.btn_exceptions_flats, 					3, 0, 1, 6)
		self.addWidget(QtGui.QLabel('\nKerning: Clean exceptions'), 4, 0, 1, 6)
		self.addWidget(QtGui.QLabel('Layer:'), 						5, 0, 1, 1)
		self.addWidget(self.cmb_layers, 							5, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Difference:'),					6, 0, 1, 1)
		self.addWidget(self.spn_exceptions_delta, 					6, 1, 1, 5)
		self.addWidget(self.btn_exceptions_report, 					7, 0, 1, 3)
		self.addWidget(self.btn_exceptions_remove, 					7, 3, 1, 3)

		# - Init
		self.fonts_refresh()

	def fonts_refresh(self):
		self.all_fonts = fl6.AllFonts()
		self.font_files = [path.split(font.path)[1] for font in self.all_fonts]
		self.cmb_all_fonts.clear()
		self.cmb_all_fonts.addItems(self.font_files)
		self.fonts_changed()
		
	def fonts_changed(self):
		currentFont = self.all_fonts[self.font_files.index(self.cmb_all_fonts.currentText)]
		self.font = pFont(currentFont)
		self.cmb_layers.clear()
		self.cmb_layers.addItems(['All masters'] + self.font.masters())
		print '\nWARN:\t Active font changed to: %s;\t Path: %s' %(self.font.PSfullName, currentFont.path)

	def kern_exceptions(self, clear_exceptions=False, report_flats=False):
		# - Init
		work_layers = self.font.masters() if self.cmb_layers.currentIndex == 0 else [self.cmb_layers.currentText]
		delete_pairs = []

		for layer in work_layers:
			layer_kerning = pKerning(self.font.kerning(layer))
			layer_groups = layer_kerning.groupsBiDict()
			print '\nFONT: %s;\tLAYER:\t %s\n' %(self.font.PSfullName, layer) + '-'*60 

			for pair, value in layer_kerning.fg.items():
				left_in_group = None
				right_in_group = None

				if pair.left.mode == 'groupMode' and pair.right.mode == 'groupMode':
					pass
				else:
					try:
						left_in_group = layer_groups['KernLeft'].inverse[pair.left.id]
					except KeyError:
						try:
							left_in_group = layer_groups['KernBothSide'].inverse[pair.left.id]
						except KeyError:
							left_in_group = None

					try:
						right_in_group = layer_groups['KernRight'].inverse[pair.right.id]
					except KeyError:
						try:
							right_in_group = layer_groups['KernBothSide'].inverse[pair.right.id]
						except KeyError:
							right_in_group = None

					if left_in_group is not None and right_in_group is not None:
						group_value = layer_kerning.fg[left_in_group[0], right_in_group[0]]
						
						if group_value is not None:
							if abs(group_value - value) <= self.spn_exceptions_delta.value:
								delete_pairs.append((pair.left.id, pair.right.id))
								
								if not clear_exceptions and not report_flats:
									print 'FOUND:\t Exception: %s|%s %s;\tFrom: %s|%s %s.' %(pair.left.id, pair.right.id, value, left_in_group[0], right_in_group[0], group_value)
						else:
							if report_flats:
								print 'WARN:\t Plain pair: %s|%s %s;\tCould be EXTENDED to class kerning: %s|%s.' %(pair.left.id, pair.right.id, value, left_in_group[0], right_in_group[0])

			if clear_exceptions:
				for pair in delete_pairs:
					layer_kerning.fg.remove(pair)

				print 'DONE:\t Removed exception pairs: %s;\tLayer: %s.\n' %(len(delete_pairs), layer)

		if clear_exceptions:
			self.font.update()
	
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
		# - Build   
		layoutV.addLayout(TRkernClean())

		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)
		
		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300, self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 100, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()