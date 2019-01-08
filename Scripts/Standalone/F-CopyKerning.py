#FLM: Font: Copy Kerning (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy import pFont
from typerig.brain import extBiDict

# - Init --------------------------------
app_version = '0.5'
app_name = 'Copy Kernig'

# -- Strings

# - Dialogs --------------------------------
class dlg_copyKerning(QtGui.QDialog):
	def __init__(self):
		super(dlg_copyKerning, self).__init__()
	
		# - Init
		self.active_font = pFont()
		self.class_data = {}
		
		# - Widgets
		self.cmb_layer = QtGui.QComboBox()
		self.cmb_layer.addItems(self.active_font.masters() + ['All masters'])

		self.btn_loadFile = QtGui.QPushButton('From File')
		self.btn_loadFont = QtGui.QPushButton('From Font')
		self.btn_saveExpr = QtGui.QPushButton('Save')
		self.btn_loadExpr = QtGui.QPushButton('Load')
		self.btn_exec = QtGui.QPushButton('Execute')

		self.btn_loadFont.setEnabled(False)		
		
		self.btn_loadFile.clicked.connect(self.classes_fromFile)
		self.btn_exec.clicked.connect(self.process)
		
		self.txt_editor = QtGui.QPlainTextEdit()
		#self.txt_editor.setFontPointSize(10)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Load class kerning data:'),	0, 0, 1, 4)
		layoutV.addWidget(self.btn_loadFont, 		1, 0, 1, 2)
		layoutV.addWidget(self.btn_loadFile, 		1, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Process font master:'),	2, 0, 1, 2)
		layoutV.addWidget(self.cmb_layer,			2, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('\nExpressions:\n - Only one source pair (colon) separated;\n - Multiple destination pairs (space) separated;\n - Each pair is (colon) separated;\n - Group/class kerning is detected on the fly.\n\nExample: Y:A A:Y A:V = V:A'),		3, 0, 1, 4)
		layoutV.addWidget(self.txt_editor,			4, 0, 20, 4)
		layoutV.addWidget(self.btn_saveExpr, 		24, 0, 1, 2)
		layoutV.addWidget(self.btn_loadExpr, 		24, 2, 1, 2)
		layoutV.addWidget(self.btn_exec, 			25, 0, 1, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 300, 500)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def update_data(self, source):
		temp_data = {}

		for key, value in source.iteritems():
			temp_data.setdefault(value[1], {}).update({key : value[0]})

		self.class_data = {key:extBiDict(value) for key, value in temp_data.iteritems()}

	def classes_fromFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning classes from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.update_data(json.load(importFile))			

			print 'LOAD:\t Font:%s; Group Kerning classes loaded from: %s.' %(self.active_font.name, fname)

	def process(self):
		# - Init
		getUniGlyph = lambda c: self.active_font.fl.findUnicode(ord(c)).name
		dst_pairs, src_pairs = [], []
		process_layers = [self.cmb_layer.currentText]

		# - Process
		for line in self.txt_editor.toPlainText().splitlines():
			if '=' in line:
				dst_names, src_names = line.split('=')
				
				dst_names = [item.split(':') for item in dst_names.strip().split(' ')]
				src_names = [src_names.strip().split(':')]

				# - Decode unicode and find glyph names needed
				#dst_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1]), modeLeft, modeRight) for pair in dst_names]
				#src_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1]), modeLeft, modeRight) for pair in src_names]

				dst_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in dst_names]
				src_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in src_names]

				# - Build pairs
				for pair in dst_names:
					left, right = pair
					modeLeft, modeRight = 0, 0
					
					if len(self.class_data.keys()):
						if self.class_data['KernLeft'].inverse.has_key(left):
							left = self.class_data['KernLeft'].inverse[left]
							modeLeft = 1

						elif self.class_data['KernBothSide'].inverse.has_key(left):
							left = self.class_data['KernBothSide'].inverse[left]
							modeLeft = 1

						if self.class_data['KernRight'].inverse.has_key(right):
							right = self.class_data['KernRight'].inverse[right]
							modeRight = 1

						elif self.class_data['KernBothSide'].inverse.has_key(right):
							right = self.class_data['KernBothSide'].inverse[right]
							modeRight = 1

					dst_pairs.append(self.active_font.newKernPair(left, right, modeLeft, modeRight))

				# - Set pairs
				for layer in process_layers:
					layer_kerning = self.active_font.kerning(layer)

					for pair in dst_pairs:
						#.setPlainPairs([(('A','V'),-30)])
						layer_kerning[pair] = layer_kerning.get(src_names[0])



# - RUN ------------------------------
dialog = dlg_copyKerning()