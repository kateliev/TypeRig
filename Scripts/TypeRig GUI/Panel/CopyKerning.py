#FLM: TR: Copy Kerning
# ----------------------------------------
# (C) Vassil Kateliev, 2019-2021 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import os, json, warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.core.objects.collection import extBiDict
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui

# - Init --------------------------------
app_name, app_version = 'Copy Kernig', '2.9'

# -- Strings 
str_help = '''
Expressions:
 - Only one source pair (bar) separated;
 - Source adjustment is (at) separated; 
 - Multiple destination pairs (bar) separated;
 - Each pair is (bar) separated;
 - Group/class kerning is detected on the fly.

Example: Y|A A|Y A|V = V|A
'''
syn_pair = '|'
syn_adjust = '@'
syn_comment = '#'
syn_equal = '='

fileFormats = ['TypeRig JSON Raw Classes (*.json)', 'FontLab JSON Classes (*.json)']

# - Functions ----------------------------------------------------------------
def json_class_dumb_decoder(jsonData):
	retund_dict = {}
	pos_dict = {(True, False):'KernLeft', (False, True):'KernRight', (True, True):'KernBothSide'}
	getPos = lambda d: (d['1st'] if '1st' in d else False , d['2nd'] if '2nd' in d else False)

	if len(jsonData.keys()):
		if 'masters' in jsonData and len(jsonData['masters']):
			for master in jsonData['masters']:
				if len(master.keys()):
					if 'kerningClasses' in master and len(master['kerningClasses']):
						temp_dict = {}

						for group in master['kerningClasses']:
							if 'names' in group:
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
		self.cmb_layer.addItems(['All masters'] + self.active_font.masters())

		self.btn_loadFile = QtGui.QPushButton('From File')
		self.btn_loadFont = QtGui.QPushButton('From Font')
		self.btn_saveExpr = QtGui.QPushButton('Save')
		self.btn_loadExpr = QtGui.QPushButton('Load')
		self.btn_exec = QtGui.QPushButton('Execute')
		self.btn_help = QtGui.QPushButton('Help')
		self.btn_classKern = QtGui.QPushButton('Class Kerning')

		self.btn_classKern.setCheckable(True)
		self.btn_loadFile.setCheckable(True)
		self.btn_loadFont.setCheckable(True)
		
		self.btn_loadFile.setChecked(False)
		self.btn_loadFont.setChecked(False)
		self.btn_classKern.setChecked(True)
			
		self.btn_help.clicked.connect(lambda: QtGui.QMessageBox.information(None, 'Help', str_help))
		self.btn_loadFile.clicked.connect(self.classes_fromFile)
		self.btn_loadFont.clicked.connect(self.classes_fromFont)
		self.btn_exec.clicked.connect(self.process)
		self.btn_saveExpr.clicked.connect(self.expr_toFile)
		self.btn_loadExpr.clicked.connect(self.expr_fromFile)

		self.txt_editor = QtGui.QPlainTextEdit()
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Class kerning data:'),		0, 0, 1, 4)
		layoutV.addWidget(self.btn_loadFont, 						1, 0, 1, 2)
		layoutV.addWidget(self.btn_loadFile, 						1, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel('Process:'),					2, 0, 1, 4)
		layoutV.addWidget(self.cmb_layer,							3, 0, 1, 2)
		layoutV.addWidget(self.btn_classKern,						3, 2, 1, 2)
		layoutV.addWidget(self.txt_editor,							5, 0, 30, 4)
		layoutV.addWidget(self.btn_saveExpr, 						36, 0, 1, 2)
		layoutV.addWidget(self.btn_loadExpr, 						36, 2, 1, 2)
		layoutV.addWidget(self.btn_help,							37, 0, 1, 2)
		layoutV.addWidget(self.btn_exec, 							37, 2, 1, 2)

		# - Set Widget
		self.setLayout(layoutV)
		
	def update_data(self, source):
		self.class_data, temp_data = {}, {}

		for layer in self.active_font.masters():
			if layer in source:
				for key, value in source[layer].items():
					temp_data.setdefault(value[1], {}).update({key : value[0]})

				self.class_data[layer] = {key:extBiDict(value) for key, value in temp_data.items()}
			else:
				warnings.warn('Class kering not found for Master: %s' %layer, KernClassWarning)

	def expr_fromFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning expressions from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.txt_editor.setPlainText(importFile.read())			

			output(6, app_name, 'Font:%s; Class Kerning expressions loaded from: %s.' %(self.active_font.name, fname))
			
	def expr_toFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save kerning expressions from file', fontPath, '*.txt')
		
		if fname != None:
			with open(fname, 'w') as importFile:
				importFile.writelines(self.txt_editor.toPlainText())

			output(7, app_name, 'Font:%s; Class Kerning expressions saved to: %s.' %(self.active_font.name, fname))

	def classes_fromFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning classes from file', fontPath, ';;'.join(fileFormats))
		
		if fname != None:
			with open(fname, 'r') as importFile:
				source_data = json.load(importFile)

				if 'masters' in source_data: # A Fontlab JSON Class kerning file
					self.update_data(json_class_dumb_decoder(source_data))
					output(6, app_name, 'Font:%s; Fontlab JSON Kerning classes loaded from: %s.' %(self.active_font.name, fname))

				else: # A TypeRig JSON Class kerning file
					self.update_data(source_data)
					output(6, app_name, 'Font:%s; TypeRig JSON Kerning classes loaded from: %s.' %(self.active_font.name, fname))

				self.btn_loadFile.setChecked(True)
				self.btn_loadFont.setChecked(False)

	def classes_fromFont(self):
		temp_dict = {}
		
		for layer in self.active_font.masters():
			fl_kern_group_dict = self.active_font.kerning_groups_to_dict(layer, False, False)
			temp_dict[layer] = fl_kern_group_dict
			
		self.update_data(temp_dict)
		output(6, app_name, 'Font:%s; Kerning classes loaded: %s.' %(self.active_font.name, len(fl_kern_group_dict.keys())))
		self.btn_loadFile.setChecked(False)
		self.btn_loadFont.setChecked(True)

	def process(self):
		# - Helper
		def getUniGlyph(char):
			if '/' in char and char != '//':
				return char.replace('/','')

			return self.active_font.fl.findUnicode(ord(char)).name
		
		# - Init
		do_update = False
		process_layers = [self.cmb_layer.currentText] if self.cmb_layer.currentText != 'All masters' else self.active_font.masters()	
		
		# - Process
		for line in self.txt_editor.toPlainText().splitlines():
			if syn_equal in line and syn_comment not in line:
				for layer in process_layers:
					dst_pairs = []
					src_pair = None

					# - Init
					layer_kerning = self.active_font.kerning(layer)
					dst_names, src_names = line.split(syn_equal)
					
					dst_names = [item.split(syn_pair) for item in dst_names.strip().split(' ')]
					src_raw = [item.split(syn_pair) for item in src_names.strip().split(syn_adjust)]

					# - Build Destination names from actual glyph names in the font
					dst_names = [(getUniGlyph(pair[0]), getUniGlyph(pair[1])) for pair in dst_names]
					src_names = (getUniGlyph(src_raw[0][0]), getUniGlyph(src_raw[0][1]))

					# - Build Destination pairs
					for pair in dst_names:
						left, right = pair
						modeLeft, modeRight = False, False
						
						if len(self.class_data.keys()) and len(self.class_data[layer].keys()):
							if left in self.class_data[layer]['KernLeft'].inverse:
								left = self.class_data[layer]['KernLeft'].inverse[left][0]
								modeLeft = True

							elif 'KernBothSide' in self.class_data and left in self.class_data[layer]['KernBothSide'].inverse:
								left = self.class_data[layer]['KernBothSide'].inverse[left][0]
								modeLeft = True

							if right in self.class_data[layer]['KernRight'].inverse:
								right = self.class_data[layer]['KernRight'].inverse[right][0]
								modeRight = True

							elif 'KernBothSide' in self.class_data and right in self.class_data[layer]['KernBothSide'].inverse:
								right = self.class_data[layer]['KernBothSide'].inverse[right][0]
								modeRight = True

						if self.btn_classKern.isChecked(): 
							dst_pairs.append(((left, modeLeft), (right, modeRight)))
						else:
							dst_pairs.append((left, right))

					# - Build Source pair for group kerning
					src_left, src_right = src_names
					src_mode_left, src_mode_right = False, False
					
					if  len(self.class_data.keys()) and len(self.class_data[layer].keys()):
						if src_left in self.class_data[layer]['KernLeft'].inverse:
							src_left = self.class_data[layer]['KernLeft'].inverse[src_left][0]
							src_mode_left = True

						elif 'KernBothSide' in self.class_data and src_left in self.class_data[layer]['KernBothSide'].inverse:
							src_left = self.class_data[layer]['KernBothSide'].inverse[src_left][0]
							src_mode_left = True

						if src_right in self.class_data[layer]['KernRight'].inverse:
							src_right = self.class_data[layer]['KernRight'].inverse[src_right][0]
							src_mode_right = True

						elif 'KernBothSide' in self.class_data and src_right in self.class_data[layer]['KernBothSide'].inverse:
							src_right = self.class_data[layer]['KernBothSide'].inverse[src_right][0]
							src_mode_right = True

						src_pair = ((src_left, src_mode_left), (src_right, src_mode_right))
					
					# - Get source kern value
					if self.btn_classKern.isChecked() and src_pair is not None:
						src_value = layer_kerning.get(src_pair)
					else:
						src_value = layer_kerning.get(src_names)

					# - Copy kerning value to destination
					if src_value is not None:
						if len(src_raw) > 1 and len(src_raw[1]):
							src_value = int(eval(str(src_value) + str(src_raw[1][0])))

						for wID in range(len(dst_pairs)):
							work_pair = dst_pairs[wID]
							work_name = dst_names[wID]
							
							layer_kerning.set(work_pair, src_value)
							output(4, app_name, 'Kern pair: %s; Value: %s; Layer: %s.' %(work_name, src_value, layer))
							
						do_update = True
					
					else:
						warnings.warn('Layer: %s; Value not found: %s;' %(layer, src_names), KernClassWarning)

		if do_update:
			self.active_font.updateObject(self.active_font.fl, 'Font kerning updated!', verbose=True)
			output(4, app_name, 'Font kerning updated!')

# - RUN ------------------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()