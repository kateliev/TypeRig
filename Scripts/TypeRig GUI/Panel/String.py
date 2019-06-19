#FLM: Text: String Generator
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0

app_name, app_version = 'TypeRig | String', '0.32'
glyphSep = '/'
joinOpt = {'Empty':'', 'Newline':'\n'}
filler_patterns = [	'FL A B A FR',
					'FL B A B FR',
					'FL A B FL FR B A FR',
					'FL A B FL A FL B A FL'
					]

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont
from typerig.string import stringGen, strRepDict, fillerList, baseGlyphset

# - Tabs -------------------------------
class QStringGen(QtGui.QGridLayout):
	def __init__(self):
		super(QStringGen, self).__init__()
		
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
		
		self.edt_sep.setText('/')

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
		self.btn_genUni = QtGui.QPushButton('Unicode Str.')
		self.btn_populate = QtGui.QPushButton('&Populate lists')
		self.btn_clear = QtGui.QPushButton('&Rest fields')

		self.btn_genCopy.setToolTip('Generate the pair string using Glyph Names and send it to the clipboard.')
		self.btn_genUni.setToolTip('Generate the pair string using Unicode Characters and send it to the clipboard.')
		self.btn_populate.setToolTip('Populate name lists with existing glyph names in active font.')
		self.btn_clear.setToolTip('Clear all manual input fields.')

		self.btn_clear.clicked.connect(self.clear)
		self.btn_populate.clicked.connect(self.populate)
		self.btn_genCopy.clicked.connect(self.generate)
		self.btn_genUni.clicked.connect(self.generateUni)
		
		# - Build
		self.addWidget(QtGui.QLabel('A:'), 		0, 0, 1, 1)
		self.addWidget(self.cmb_inputA, 		0, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Suffix:'), 0, 6, 1, 1)
		self.addWidget(self.edt_suffixA, 		0, 7, 1, 2)
		self.addWidget(self.edt_inputA, 		1, 1, 1, 8)
		self.addWidget(QtGui.QLabel('B:'), 		2, 0, 1, 1)
		self.addWidget(self.cmb_inputB, 		2, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Suffix:'), 2, 6, 1, 1)
		self.addWidget(self.edt_suffixB, 		2, 7, 1, 2)
		self.addWidget(self.edt_inputB, 		3, 1, 1, 8)
		self.addWidget(QtGui.QLabel('FL:'), 	4, 0, 1, 1)
		self.addWidget(self.cmb_fillerLeft, 	4, 1, 1, 8)
		self.addWidget(QtGui.QLabel('FR:'), 	5, 0, 1, 1)
		self.addWidget(self.cmb_fillerRight, 	5, 1, 1, 8)
		self.addWidget(QtGui.QLabel('E:'), 		6, 0, 1, 1)
		self.addWidget(self.cmb_fillerPattern, 	6, 1, 1, 8)
		self.addWidget(QtGui.QLabel('Join:'), 	7, 0, 1, 1)
		self.addWidget(self.cmb_join, 			7, 1, 1, 5)
		self.addWidget(QtGui.QLabel('Sep.:'), 	7, 6, 1, 1)
		self.addWidget(self.edt_sep, 			7, 7, 1, 2)
		self.addWidget(QtGui.QLabel(''), 		8, 0, 1, 1)
		self.addWidget(self.btn_populate, 		9, 1, 1, 5)
		self.addWidget(self.btn_clear, 			9, 6, 1, 3)
		self.addWidget(self.btn_genCopy, 		10, 1, 1, 5)
		self.addWidget(self.btn_genUni, 		10, 6, 1, 3)
		self.addWidget(QtGui.QLabel('OUT:'), 	11, 0, 1, 1)
		self.addWidget(self.edt_output, 		11, 1, 4, 8)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 2)
		self.setColumnStretch(6, 0)
		self.setColumnStretch(7, 1)
				
	# - Procedures
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
		self.edt_sep.setText('/')
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
		
		# - Copy to cliboard
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
		self.strGenerator = QStringGen()

		# - Build ---------------------------
		layoutV.addWidget(QtGui.QLabel('String generator:'))
		layoutV.addLayout(self.strGenerator)

		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 250, 500)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()