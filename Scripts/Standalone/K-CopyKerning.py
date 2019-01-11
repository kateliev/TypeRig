#FLM: Kerning: Copy Kerning (TypeRig)
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
app_version = '0.9'
app_name = 'Copy Kernig'

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
		#self.btn_loadFile.setEnabled(False)
		
		self.btn_loadFile.clicked.connect(self.classes_fromFile)
		self.btn_exec.clicked.connect(self.process)
		self.btn_saveExpr.clicked.connect(self.expr_toFile)
		self.btn_loadExpr.clicked.connect(self.expr_fromFile)

		self.txt_editor = QtGui.QPlainTextEdit()
		
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
		self.setGeometry(300, 300, 250, 500)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def update_data(self, source):
		temp_data = {}

		for key, value in source.iteritems():
			temp_data.setdefault(value[1], {}).update({key : value[0]})

		self.class_data = {key:extBiDict(value) for key, value in temp_data.iteritems()}

	def expr_fromFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning expressions from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.txt_editor.setPlainText(importFile.read().decode('utf8'))			

			print 'LOAD:\t Font:%s; Group Kerning expressions loaded from: %s.' %(self.active_font.name, fname)

	def expr_toFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save kerning expressions from file', fontPath, '*.txt')
		
		if fname != None:
			with open(fname, 'w') as importFile:
				importFile.writelines(self.txt_editor.toPlainText().encode('utf-8'))

			print 'SAVE:\t Font:%s; Group Kerning expressions saved to: %s.' %(self.active_font.name, fname)

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
		process_layers = [self.cmb_layer.currentText] if self.cmb_layer.currentText != 'All masters' else self.active_font.masters()	
		# - Process
		for line in self.txt_editor.toPlainText().splitlines():
			dst_pairs, src_pairs = [], []

			if '=' in line and '#' not in line:
				dst_names, src_names = line.split('=')
				
				dst_names = [item.split(':') for item in dst_names.strip().split(' ')]
				src_names = [src_names.strip().split(':')]

				if '@' not in line:
					# - Build Destination names from actual glyph names in the font
					dst_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in dst_names]
					src_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in src_names]

					# - Build Destination pairs
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

						dst_pairs.append(self.active_font.newKernPair(left[0], right[0], modeLeft, modeRight))

					# - Build Source pairs
					for pair in src_names:
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

						
						src_pairs.append(self.active_font.newKernPair(left[0], right[0], modeLeft, modeRight))

					# !!! Add only as plain pairs supported - No class kerning trough python in build 6927
					# !!! Syntax fgKerning.setPlainPairs([(('A','V'),-30)])
					for layer in process_layers:
						layer_kerning = self.active_font.kerning(layer)
						src_value = layer_kerning.get(src_names[0]) # use only single source for now

						if src_pairs[0] in layer_kerning.keys():
							src_value = layer_kerning.values()[layer_kerning.keys().index(src_pairs[0])]

						if src_value is not None:
							for wID in range(len(dst_pairs)):
								work_pair = dst_pairs[wID]
								work_name = dst_names[wID]
								
								# - Check if class already exists and change value
								if work_pair in layer_kerning.keys():
									if layer_kerning[layer_kerning.keys().index(work_pair)] != src_value:
										layer_kerning[layer_kerning.keys().index(work_pair)] = src_value
										print 'CHANGE:\t Kern pair: %s; Value: %s; Layer: %s.' %(work_name, src_value, layer)

								else: # Class does not exist, add as plain pair due to FL6 limitation 
									layer_kerning.setPlainPairs([(work_name, src_value)])
									print 'ADD:\t Plain Kern pair: %s; Value: %s; Layer: %s.' %(work_name, src_value, layer)
				else:
					# Special symbol @ found
					# !!! Works with whole sets but only in plain part mode. No group kering heuristic found!
					# - Init
					glyph_names = {'UC':self.active_font.uppercase(True), 'LC':self.active_font.lowercase(True), 'FIG':self.active_font.figures(True), 'LIGA':self.active_font.ligatures(True), 'ALT':self.active_font.alternates(True), 'SYM':self.active_font.symbols(True)}
					src_names_expand = []
					
					# - Process
					for layer in process_layers:
						layer_kerning_plain = self.active_font.kerning(layer).getPlainPairs()
						src_left, src_right = src_names[0] # use only single source for now

						for kern_pair in layer_kerning_plain:
							left, right = kern_pair[0]
							left_test, right_test = False, False

							if '@' in src_left and left in glyph_names[src_left.strip('@')]:
								left_test = True

							elif '@' not in src_left and left == src_left:
								left_test = True

							if '@' in src_right and right in glyph_names[src_right.strip('@')]:
								right_test = True

							elif '@' not in src_right and right == src_right:
								right_test = True

							if left_test and right_test:
								src_names_expand.append(left, right)

								
		print 'Done.'

# - RUN ------------------------------
dialog = dlg_copyKerning()