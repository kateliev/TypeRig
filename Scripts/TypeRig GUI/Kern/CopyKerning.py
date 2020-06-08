#FLM: TR: Copy Kerning
# ----------------------------------------
# (C) Vassil Kateliev, 2019-2020 (http://www.kateliev.com)
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
from typerig.core.objects.collection import extBiDict

# - Init --------------------------------
app_name, app_version = 'Copy Kernig', '1.60'

# -- Strings 
str_help = '''
Expressions:
 - Only one source pair (colon) separated;
 - Source adjustment is (bar) separated; 
 - Multiple destination pairs (space) separated;
 - Each pair is (colon) separated;
 - Group/class kerning is detected on the fly.

Example: Y:A A:Y A:V = V:A'
'''
fileFormats = ['TypeRig JSON Raw Classes (*.json)', 'FontLab VI JSON Classes (*.json)']

# - Functions ----------------------------------------------------------------
def json_class_dumb_decoder(jsonData):
	retund_dict = {}
	pos_dict = {(True, False):'KernLeft', (False, True):'KernRight', (True, True):'KernBothSide'}
	getPos = lambda d: (d['1st'] if d.has_key('1st') else False , d['2nd'] if d.has_key('2nd') else False)

	if len(jsonData.keys()):
		if jsonData.has_key('masters') and len(jsonData['masters']):
			for master in jsonData['masters']:
				if len(master.keys()):
					if master.has_key('kerningClasses') and len(master['kerningClasses']):
						temp_dict = {}

						for group in master['kerningClasses']:
							if group.has_key('names'):
								temp_dict[group['name']] = (group['names'], pos_dict[getPos(group)])

						retund_dict[master['name']] = temp_dict
	return retund_dict

# - Dialogs --------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
	
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
		self.btn_saveExpr.clicked.connect(self.expr_toFile)
		self.btn_loadExpr.clicked.connect(self.expr_fromFile)

		self.txt_editor = QtGui.QPlainTextEdit()
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Load class kerning data:'),	0, 0, 1, 4)
		layoutV.addWidget(self.btn_loadFont, 						1, 0, 1, 2)
		layoutV.addWidget(self.btn_loadFile, 						1, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Process font master:'),		2, 0, 1, 2)
		layoutV.addWidget(self.cmb_layer,							2, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel(str_help),					3, 0, 1, 4)
		layoutV.addWidget(self.txt_editor,							4, 0, 20, 4)
		layoutV.addWidget(self.btn_saveExpr, 						24, 0, 1, 2)
		layoutV.addWidget(self.btn_loadExpr, 						24, 2, 1, 2)
		layoutV.addWidget(self.btn_exec, 							25, 0, 1, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 250, 500)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def update_data(self, source):
		self.class_data, temp_data = {}, {}

		for layer in self.active_font.masters():
			if source.has_key(layer):
				for key, value in source[layer].iteritems():
					temp_data.setdefault(value[1], {}).update({key : value[0]})

				self.class_data[layer] = {key:extBiDict(value) for key, value in temp_data.iteritems()}
			else:
				print 'ERROR:\t Class kering not found for Master: %s' %layer

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
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning classes from file', fontPath, ';;'.join(fileFormats))
		
		if fname != None:
			with open(fname, 'r') as importFile:
				source_data = json.load(importFile)

				if source_data.has_key('masters'): # A Fontlab JSON Class kerning file
					self.update_data(json_class_dumb_decoder(source_data))
					print 'LOAD:\t Font:%s; Fontlab VI JSON Group Kerning classes loaded from: %s.' %(self.active_font.name, fname)
					
				else: # A TypeRig JSON Class kerning file
					self.update_data(source_data)
					print 'LOAD:\t Font:%s; TypeRig JSON Group Kerning classes loaded from: %s.' %(self.active_font.name, fname)

	def process(self):
		# - Init
		#getUniGlyph = lambda c: self.active_font.fl.findUnicode(ord(c)).name
		
		def getUniGlyph(char):
			if '/' in char and char != '//':
				return char.replace('/','')

			return self.active_font.fl.findUnicode(ord(char)).name
		
		process_layers = [self.cmb_layer.currentText] if self.cmb_layer.currentText != 'All masters' else self.active_font.masters()	
		
		# - Process
		for line in self.txt_editor.toPlainText().splitlines():
			if '=' in line and '#' not in line:
				for layer in process_layers:
					dst_pairs, src_pairs = [], []

					if self.class_data.has_key(layer):
						dst_names, src_names = line.split('=')
						
						dst_names = [item.split(':') for item in dst_names.strip().split(' ')]
						src_raw = [item.split(':') for item in src_names.strip().split('|')]

						# - Build Destination names from actual glyph names in the font
						dst_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in dst_names]
						src_names = [(getUniGlyph(src_raw[0][0]), getUniGlyph(src_raw[0][1]))]

						# - Build Destination pairs
						for pair in dst_names:
							left, right = pair
							modeLeft, modeRight = 0, 0
							
							if len(self.class_data[layer].keys()):
								if self.class_data[layer]['KernLeft'].inverse.has_key(left):
									left = self.class_data[layer]['KernLeft'].inverse[left]
									modeLeft = 1

								elif self.class_data[layer]['KernBothSide'].inverse.has_key(left):
									left = self.class_data[layer]['KernBothSide'].inverse[left]
									modeLeft = 1

								if self.class_data[layer]['KernRight'].inverse.has_key(right):
									right = self.class_data[layer]['KernRight'].inverse[right]
									modeRight = 1

								elif self.class_data[layer]['KernBothSide'].inverse.has_key(right):
									right = self.class_data[layer]['KernBothSide'].inverse[right]
									modeRight = 1

							dst_pairs.append(self.active_font.newKernPair(left[0], right[0], modeLeft, modeRight))

						# - Build Source pairs
						for pair in src_names: # Ugly boilerplate... but may be useful in future
							left, right = pair
							modeLeft, modeRight = 0, 0
							
							if len(self.class_data[layer].keys()):
								if self.class_data[layer]['KernLeft'].inverse.has_key(left):
									left = self.class_data[layer]['KernLeft'].inverse[left]
									modeLeft = 1

								elif self.class_data[layer]['KernBothSide'].inverse.has_key(left):
									left = self.class_data[layer]['KernBothSide'].inverse[left]
									modeLeft = 1

								if self.class_data[layer]['KernRight'].inverse.has_key(right):
									right = self.class_data[layer]['KernRight'].inverse[right]
									modeRight = 1

								elif self.class_data[layer]['KernBothSide'].inverse.has_key(right):
									right = self.class_data[layer]['KernBothSide'].inverse[right]
									modeRight = 1

							
							src_pairs.append(self.active_font.newKernPair(left[0], right[0], modeLeft, modeRight))

						# !!! Add only as plain pairs supported - No class kerning trough python in build 6927
						# !!! Syntax fgKerning.setPlainPairs([(('A','V'),-30)])
					
						layer_kerning = self.active_font.kerning(layer)
						src_value = layer_kerning.get(src_names[0])

						if src_pairs[0] in layer_kerning.keys():
							src_value = layer_kerning.values()[layer_kerning.keys().index(src_pairs[0])]

						if src_value is not None:
							if len(src_raw) > 1 and len(src_raw[1]):
								src_value = int(eval(str(src_value) + str(src_raw[1][0])))

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
						print 'ERROR:\t Class kering not found for Master: %s' %layer
				
		print 'Done.'

# - RUN ------------------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()