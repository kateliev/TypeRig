#FLM: TR: Pairs
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt

from typerig.proxy import *

from PythonQt import QtCore
from typerig.gui import QtGui

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0

app_name, app_version = 'TypeRig | Pairs', '0.42'
glyphSep = '/'
pairSep = '|'
joinOpt = {'Empty':'', 'Newline':'\n'}
filler_patterns = [	'FL A FR',
					'FL B FR',
					'FL A B A FR',
					'FL B A B FR',
					'FL A FL FR A FR',
					'FL B FL FR B FR',
					'FL A B FL FR B A FR',
					'FL A B FL A FL B A FL',
					'FL A B FL B FL B A FL',
					'FL A | B FR',
					'FL B | A FR',
					'FL A | B FR \\n FR B A FL',
					]

# - Tabs -------------------------------
class TRStringGen(QtGui.QGridLayout):
	def __init__(self):
		super(TRStringGen, self).__init__()
		
		# - Init data
		val_fillerLeft, val_fillerRight = zip(*fillerList)
		self.defEncoding = 'utf-8'
		self.glyphNames = baseGlyphset
		
		# -- Init Interface 
		self.edt_inputA = QtGui.QLineEdit()
		self.edt_inputB = QtGui.QLineEdit()
		self.edt_suffixA = QtGui.QLineEdit()
		self.edt_suffixB = QtGui.QLineEdit()
		
		self.edt_output = QtGui.QTextEdit()
		self.edt_sep = QtGui.QLineEdit()

		self.edt_inputA.setToolTip('Manual Glyph names input. [SPACE] delimited.\nNOTE: This field overrides the input combo box!')
		self.edt_inputB.setToolTip('Manual Glyph names input. [SPACE] delimited.\nNOTE: This field overrides the input combo box!')
		self.edt_suffixA.setToolTip('Suffix to be added to each glyph name.')
		self.edt_suffixB.setToolTip('Suffix to be added to each glyph name.')
		
		self.edt_sep.setText(glyphSep)

		#self.edt_inputA.setEnabled(False)
		#self.edt_inputB.setEnabled(False)
		
		self.cmb_fillerPattern = QtGui.QComboBox()
		self.cmb_inputA = QtGui.QComboBox()
		self.cmb_inputB = QtGui.QComboBox()
		self.cmb_fillerLeft = QtGui.QComboBox()
		self.cmb_fillerRight = QtGui.QComboBox()
		self.cmb_join = QtGui.QComboBox()

		self.cmb_inputA.addItems(sorted(self.glyphNames.keys()))
		self.cmb_inputB.addItems(sorted(self.glyphNames.keys()))

		self.cmb_fillerPattern.setEditable(True)
		self.cmb_fillerLeft.setEditable(True)
		self.cmb_fillerRight.setEditable(True)

		self.cmb_join.addItems(joinOpt.keys())
		self.cmb_fillerPattern.addItems(filler_patterns)

		self.cmb_inputA.setToolTip('Glyph names list.')
		self.cmb_inputB.setToolTip('Glyph names list.')
		self.cmb_fillerLeft.setToolTip('Left Filler String.')
		self.cmb_fillerRight.setToolTip('Right Filler String.')
		self.cmb_join.setToolTip('Joining method for generated string pairs.')
		self.edt_sep.setToolTip('Glyph Separator.')
		self.cmb_fillerPattern.setToolTip('Generator pattern expression.\n<< Filed names >> in any order, [SPACE] separated.')

		self.cmb_fillerLeft.addItems(val_fillerLeft)
		self.cmb_fillerRight.addItems(val_fillerRight)
				
		self.btn_genCopy = QtGui.QPushButton('Generate')
		self.btn_genUni = QtGui.QPushButton('Unicode')
		self.btn_populate = QtGui.QPushButton('&Populate lists')
		self.btn_clear = QtGui.QPushButton('&Rest')
		self.btn_kernPairs = QtGui.QPushButton('String')
		self.btn_kernPairsUni = QtGui.QPushButton('Unicode')
		self.btn_genAMF = QtGui.QPushButton('AFM string')
		self.btn_genOTgroups = QtGui.QPushButton('Kern Groups')

		self.btn_genCopy.setToolTip('Generate the pair string using Glyph Names and send it to the clipboard.')
		self.btn_genUni.setToolTip('Generate the pair string using Unicode Characters and send it to the clipboard.')
		self.btn_populate.setToolTip('Populate name lists with existing glyph names in active font.')
		self.btn_clear.setToolTip('Clear all manual input fields.')
		self.btn_kernPairs.setToolTip('Get string containing pairs from fonts kerning for current layer.\n SHIFT+Click discard filler - pure pairs.')
		self.btn_kernPairsUni.setToolTip('Get Unicode pairs list from fonts kerning for current layer.\n SHIFT+Click use auto filler.')

		self.btn_clear.clicked.connect(self.clear)
		self.btn_populate.clicked.connect(self.populate)
		self.btn_genCopy.clicked.connect(self.generate)
		self.btn_genUni.clicked.connect(self.generateUni)
		self.btn_genAMF.clicked.connect(self.generateAMF)
		self.btn_genOTgroups.clicked.connect(self.generateOTGroups)
		self.btn_kernPairs.clicked.connect(lambda: self.getKerning(False))
		self.btn_kernPairsUni.clicked.connect(lambda: self.getKerning(True))
		
		# - Build
		self.addWidget(QtGui.QLabel('A:'), 					1, 0, 1, 1)
		self.addWidget(self.cmb_inputA, 					1, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Suffix:'), 			1, 6, 1, 1)
		self.addWidget(self.edt_suffixA, 					1, 7, 1, 2)
		self.addWidget(self.edt_inputA, 					2, 1, 1, 8)
		self.addWidget(QtGui.QLabel('B:'), 					3, 0, 1, 1)
		self.addWidget(self.cmb_inputB, 					3, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Suffix:'), 			3, 6, 1, 1)
		self.addWidget(self.edt_suffixB, 					3, 7, 1, 2)
		self.addWidget(self.edt_inputB, 					4, 1, 1, 8)
		self.addWidget(QtGui.QLabel('String from pattern:'),5, 0, 1, 4)
		self.addWidget(QtGui.QLabel('FL:'), 				6, 0, 1, 1)
		self.addWidget(self.cmb_fillerLeft, 				6, 1, 1, 8)
		self.addWidget(QtGui.QLabel('FR:'), 				7, 0, 1, 1)
		self.addWidget(self.cmb_fillerRight, 				7, 1, 1, 8)
		self.addWidget(QtGui.QLabel('Pat.:'), 					8, 0, 1, 1)
		self.addWidget(self.cmb_fillerPattern, 				8, 1, 1, 8)
		self.addWidget(QtGui.QLabel('Join:'), 				9, 0, 1, 1)
		self.addWidget(self.cmb_join, 						9, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Sep.:'), 				9, 6, 1, 1)
		self.addWidget(self.edt_sep, 						9, 7, 1, 2)
		self.addWidget(self.btn_populate, 					10, 0, 1, 6)
		self.addWidget(self.btn_clear, 						10, 6, 1, 4)
		self.addWidget(self.btn_genCopy, 					11, 0, 1, 6)
		self.addWidget(self.btn_genUni, 					11, 6, 1, 4)
		self.addWidget(QtGui.QLabel('String from pairs in kerning:'), 	12, 0, 1, 9)
		self.addWidget(self.btn_kernPairs, 					13, 0, 1, 6)
		self.addWidget(self.btn_kernPairsUni,				13, 6, 1, 4)
		self.addWidget(QtGui.QLabel('Export pairs:'), 	14, 0, 1, 9)
		self.addWidget(self.btn_genAMF,						15, 0, 1, 6)
		self.addWidget(self.btn_genOTgroups,				15, 6, 1, 4)
		self.addWidget(QtGui.QLabel('Output'), 			16, 0, 1, 9)
		self.addWidget(self.edt_output, 					17, 0, 12, 9)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 2)
		self.setColumnStretch(6, 0)
		self.setColumnStretch(7, 1)
				
	# - Procedures
	def getKerning(self, getUnicodeString=False):
		# - Init
		modifiers = QtGui.QApplication.keyboardModifiers()
		fillerLeft = self.cmb_fillerLeft.currentText
		fillerRight = self.cmb_fillerRight.currentText
		
		self.font = pFont()
		class_kern_dict = self.font.fl_kerning_groups_to_dict()
		layer_kernig = self.font.kerning()
		
		kern_list, drop_list = [], []

		# - Convert kerning to list
		for kern_pair in layer_kernig.asDict().keys():
			current_pair = kern_pair.asTuple()
			a = current_pair[0].asTuple()
			b = current_pair[1].asTuple()
			
			a = min(class_kern_dict[a[0]], key=len) if a[1] == 'groupMode' else a[0] # If class kerning then take the glyph with the shortest name* from group kerning...
			b = min(class_kern_dict[b[0]], key=len) if b[1] == 'groupMode' else b[0] # ...else just return the glyph name /* Avoid uniXXXX names as much as possible
			
			if getUnicodeString:
				try:
					new_a = unichr(self.font.fg[a].unicode)
					new_b = unichr(self.font.fg[b].unicode)
					
					if modifiers == QtCore.Qt.ShiftModifier:
						fillerLeft = 'HOH' if new_a.isupper() else 'non'
						fillerRight = 'HOH' if new_b.isupper() else 'non'

					kern_list.append(u'{0}{1}|{2}{3}'.format(fillerLeft, new_a, new_b, fillerRight))
					
				except TypeError:
					drop_list.append((a,b))
			else:
				kern_list.append((a,b))

		# - Build string
		if getUnicodeString:
			generatedString = sorted(kern_list)
		else:
			generatedString = stringGenPairs(sorted(kern_list), (fillerLeft, fillerRight), self.cmb_fillerPattern.currentText, (self.edt_suffixA.text, self.edt_suffixB.text), self.edt_sep.text)

		self.edt_output.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		
		# - Copy to clipboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		
		if len(drop_list):
			print 'WARN:\t %s Non-Unicode pairs dropped from string.' %len(drop_list)

		print 'DONE:\t Generated string sent to clipboard.'

	def clear(self):
		self.glyphNames = baseGlyphset
		self.edt_inputA.clear()
		self.edt_inputB.clear()
		self.cmb_inputA.clear()
		self.cmb_inputB.clear()
		self.cmb_inputA.addItems(sorted(self.glyphNames.keys()))
		self.cmb_inputB.addItems(sorted(self.glyphNames.keys()))

		self.edt_suffixA.clear()
		self.edt_suffixB.clear()
		self.edt_output.clear()
		self.cmb_fillerPattern.clear()
		self.cmb_fillerPattern.addItems(filler_patterns)
		self.edt_sep.setText(glyphSep)
		self.cmb_join.clear()
		self.cmb_join.addItems(joinOpt.keys())

	def populate(self):
		self.font = pFont()
		self.glyphNames = self.font.getGlyphNameDict()
		self.glyphUnicodes = self.font.getGlyphUnicodeDict(self.defEncoding)
		
		self.cmb_inputA.clear()
		self.cmb_inputB.clear()
		self.cmb_inputA.addItems(sorted(self.glyphNames.keys()))
		self.cmb_inputB.addItems(sorted(self.glyphNames.keys()))	

		print 'DONE:\t Active font glyph names loaded into generator.'	

	def generate(self):
		# - Get Values
		if len(self.edt_inputA.text) > 0:
			try:
				inputA = [self.font.fl.findUnicode(ord(item)).name for item in self.edt_inputA.text.split(' ')] 
			except AttributeError:
				print 'WARN:\t Unicode (Input A) to current font glyph names mapping is not activated! Please populate lists first.'
				inputA = self.edt_inputA.text.split(' ')
		else:
			inputA = sorted(self.glyphNames[self.cmb_inputA.currentText])

		if len(self.edt_inputB.text) > 0:
			try:
				inputB = [self.font.fl.findUnicode(ord(item)).name for item in self.edt_inputB.text.split(' ')]  
			except AttributeError:
				print 'WARN:\t Unicode (Input B) to current font glyph names mapping is not activated! Please populate lists first.'
				inputB = self.edt_inputB.text.split(' ')
		else:
			inputB = sorted(self.glyphNames[self.cmb_inputB.currentText])

		fillerLeft = self.cmb_fillerLeft.currentText
		fillerRight = self.cmb_fillerRight.currentText

		# - Generate
		generatedString = stringGen(inputA, inputB, (fillerLeft, fillerRight), self.cmb_fillerPattern.currentText, (self.edt_suffixA.text, self.edt_suffixB.text), self.edt_sep.text)
		self.edt_output.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		
		# - Copy to clipboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		print 'DONE:\t Generated string sent to clipboard.'

	def generateAMF(self):
		# - Get Values
		if len(self.edt_inputA.text) > 0:
			try:
				inputA = [self.font.fl.findUnicode(ord(item)).name for item in self.edt_inputA.text.split(' ')] 
			except AttributeError:
				print 'WARN:\t Unicode (Input A) to current font glyph names mapping is not activated! Please populate lists first.'
				inputA = self.edt_inputA.text.split(' ')
		else:
			inputA = sorted(self.glyphNames[self.cmb_inputA.currentText])

		if len(self.edt_inputB.text) > 0:
			try:
				inputB = [self.font.fl.findUnicode(ord(item)).name for item in self.edt_inputB.text.split(' ')]  
			except AttributeError:
				print 'WARN:\t Unicode (Input B) to current font glyph names mapping is not activated! Please populate lists first.'
				inputB = self.edt_inputB.text.split(' ')
		else:
			inputB = sorted(self.glyphNames[self.cmb_inputB.currentText])

		# - Generate
		generatedString = kpxGen(inputA, inputB, (self.edt_suffixA.text, self.edt_suffixB.text))
		self.edt_output.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		
		# - Copy to clipboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		print 'DONE:\t Generated string sent to clipboard.'

	def generateOTGroups(self):
		# - Init
		gen_pattern = '@{0} = [{1}];'
		self.font = pFont()

		# - Generate
		generatedString = [gen_pattern.format(key, ' '.join(value)) for key, value in self.font.fl_kerning_groups_to_dict().items()]
		self.edt_output.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		
		# - Copy to clipboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(joinOpt[self.cmb_join.currentText].join(generatedString))
		print 'DONE:\t Generated string sent to clipboard.'

	def generateUni(self):
		# - Get Values
		if len(self.edt_inputA.text) > 0:
			inputA = self.edt_inputA.text.split(' ')
		else:
			inputA = sorted(self.glyphUnicodes[self.cmb_inputA.currentText])

		if len(self.edt_inputB.text) > 0:
			inputB = self.edt_inputB.text.split(' ')
		else:
			inputB = sorted(self.glyphUnicodes[self.cmb_inputB.currentText])

		fillerLeft = self.cmb_fillerLeft.currentText.encode(self.defEncoding)
		fillerRight = self.cmb_fillerRight.currentText.encode(self.defEncoding)

		# - Generate
		generatedString = stringGen(inputA, inputB, (fillerLeft, fillerRight), self.cmb_fillerPattern.currentText, (self.edt_suffixA.text.encode(self.defEncoding), self.edt_suffixB.text.encode(self.defEncoding)), '')
		self.edt_output.setText(joinOpt[self.cmb_join.currentText].join(generatedString).decode(self.defEncoding))

		# - Copy to cliboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(joinOpt[self.cmb_join.currentText].join(generatedString).decode(self.defEncoding))
		print 'DONE:\t Generated string sent to clipboard.'
					
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.strGenerator = TRStringGen()

		# - Build ---------------------------
		layoutV.addWidget(QtGui.QLabel('Pairs generator:'))
		layoutV.addLayout(self.strGenerator)

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