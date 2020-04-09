#FLM: Glyph: Glyph
# ----------------------------------------
# (C) Vassil Kateliev, 2020 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Glyph', '0.08'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui
from typerig.string import fontMarkColors as colorNames
from typerig.gui import getProcessGlyphs
from typerig.glyph import eGlyph
from typerig.proxy import pFontMetrics, pFont, pWorkspace

# - Init -------------------------------
number_token = '#'

# - String -----------------------------
help_numeration = 'Use # for sequential numeration.\n\nExample:\n#=1; ##=01; ###=001\nA.ss## will crearte A.ss01 to A.ss99'
help_setName = 'Set name for current glyph or multiple selected glyphs (TR Selection mode).\n' + help_numeration

# - Functions --------------------------
fromat_number = lambda x, i: '0'*(i - 1) + str(x) if len(str(x)) < i else str(x)

# - Sub widgets ------------------------
class TRGLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		
		super(TRGLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		curret_glyph = eGlyph()
		menu.addSeparator()
		menu.addAction(u'Get {Glyph Name}', lambda: self.setText(curret_glyph.name))
		menu.addAction(u'Get {Glyph Unicodes}', lambda: self.setText(' '.join(map(str,curret_glyph.unicodes))))
		menu.addAction(u'Get {Glyph Tags}', lambda: self.setText(' '.join(map(str,curret_glyph.tags))))
		menu.addSeparator()
		menu.addAction(u'To Lowercase', lambda: self.setText(self.text.lower()))
		menu.addAction(u'To Uppercase', lambda: self.setText(self.text.upper()))
		menu.addAction(u'To Titlecase', lambda: self.setText(self.text.title()))
		menu.addSeparator()
		menu.addAction(u'.salt', lambda: self.setText('%s.salt' %self.text))
		menu.addAction(u'.calt', lambda: self.setText('%s.calt' %self.text))
		menu.addAction(u'.ss0', lambda: self.setText('%s.ss0' %self.text))
		menu.addAction(u'.locl', lambda: self.setText('%s.locl' %self.text))
		menu.addAction(u'.smcp', lambda: self.setText('%s.smcp' %self.text))
		menu.addAction(u'.cscp', lambda: self.setText('%s.cscp' %self.text))
		menu.addAction(u'.onum', lambda: self.setText('%s.onum' %self.text))
		menu.addAction(u'.pnum', lambda: self.setText('%s.pnum' %self.text))
		menu.addAction(u'.tnum', lambda: self.setText('%s.tnum' %self.text))
		
# - Tabs -------------------------------
class TRGlyphBasic(QtGui.QGridLayout):
	def __init__(self):
		super(TRGlyphBasic, self).__init__()

		# -- Edit fileds
		self.edt_glyphName = TRGLineEdit()
		self.edt_glyphTags = TRGLineEdit()
		self.edt_glyphUnis = TRGLineEdit()

		self.edt_glyphName.setPlaceholderText('Glyph Name')
		self.edt_glyphTags.setPlaceholderText('Glyph Tags')
		self.edt_glyphUnis.setPlaceholderText('Glyph Unicodes')

		self.edt_glyphName.setToolTip(help_numeration)

		# -- Buttons 
		self.btn_setName = QtGui.QPushButton('Set &Name')
		self.btn_setFlag = QtGui.QPushButton('Set &Flag')
		self.btn_setTags = QtGui.QPushButton('Set &Tags')
		self.btn_setUnis = QtGui.QPushButton('Set &Unicode')
		self.btn_setUnis.setEnabled(False)

		self.btn_setName.clicked.connect(lambda: self.glyph_setBasics('name'))
		self.btn_setFlag.clicked.connect(lambda: self.glyph_setBasics('flag'))
		self.btn_setTags.clicked.connect(lambda: self.glyph_setBasics('tags'))

		self.btn_setName.setToolTip(help_setName)

		# -- Combo box
		#colorNames = [(QtGui.QColor(name).hue(), name) for name in QtGui.QColor.colorNames()]
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, value, discard in colorNames}
		
		for i in range(len(colorNames)):
			self.cmb_select_color.addItem(colorNames[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(colorNames[i][2]), QtCore.Qt.DecorationRole)

		self.cmb_select_color.setMinimumWidth(40)
		self.edt_glyphName.setMinimumWidth(40)

		# - Build
		self.addWidget(QtGui.QLabel('Glyph Basics:'), 			0, 0, 1, 8)
		self.addWidget(QtGui.QLabel('Name:'), 					1, 0, 1, 1)
		self.addWidget(self.edt_glyphName, 						1, 1, 1, 5)
		self.addWidget(self.btn_setName, 						1, 6, 1, 2)
		self.addWidget(QtGui.QLabel('Flag:'), 					2, 0, 1, 1)
		self.addWidget(self.cmb_select_color, 					2, 1, 1, 5)
		self.addWidget(self.btn_setFlag, 						2, 6, 1, 2)
		self.addWidget(QtGui.QLabel('Tags:'), 					3, 0, 1, 1)
		self.addWidget(self.edt_glyphTags, 						3, 1, 1, 5)
		self.addWidget(self.btn_setTags, 						3, 6, 1, 2)
		self.addWidget(QtGui.QLabel('Uni:'), 					4, 0, 1, 1)
		self.addWidget(self.edt_glyphUnis, 						4, 1, 1, 5)
		self.addWidget(self.btn_setUnis, 						4, 6, 1, 2)

	def glyph_setBasics(self, mode):
		font = pFont()
		process_glyphs = getProcessGlyphs(pMode)
		processed_glyphs = []
		
		for n, glyph in enumerate(process_glyphs):
			if mode == 'flag': 
				wLayers = glyph._prepareLayers(pLayers)
				for layer in wLayers:
					glyph.setMark(self.color_codes[self.cmb_select_color.currentText], None)

			if mode == 'name': 
				new_name = str(self.edt_glyphName.text)
				
				if number_token in new_name:
					token_count = new_name.count(number_token)
					new_name = new_name.replace('#'*token_count, '%s' ) %fromat_number(n, token_count)

				if font.hasGlyph(new_name):
					new_name = '%s.%s' %(new_name, str(n))
				
				glyph.setName(new_name)

			if mode == 'tags': glyph.setTags(str(self.edt_glyphTags.text).split(' '))
			
			processed_glyphs.append(glyph.name)

		font.updateObject(font.fl, 'Set Glyph(s) %s | %s' %(mode, ', '.join(processed_glyphs)))

class TRGlyphCopyTools(QtGui.QGridLayout):
	def __init__(self):
		super(TRGlyphCopyTools, self).__init__()

		# -- Edit Fields
		self.edt_glyphsuffix = TRGLineEdit()
		self.edt_glyphsuffix.setPlaceholderText('Glyph Suffix')
		self.edt_glyphsuffix.setToolTip(help_numeration)

		# -- Buttons
		self.btn_duplicate = QtGui.QPushButton('Duplicate')
		self.chk_slot01 = QtGui.QPushButton('')
		self.chk_slot01.setCheckable(True)
		self.chk_slot02 = QtGui.QPushButton('')
		self.chk_slot02.setCheckable(True)
		self.chk_slot03 = QtGui.QPushButton('')
		self.chk_slot03.setCheckable(True)
		self.chk_slot04 = QtGui.QPushButton('')
		self.chk_slot04.setCheckable(True)

		self.btn_duplicate.clicked.connect(self.glyph_duplicate)

		# -- Spin boxes 
		self.spb_duplicate =  QtGui.QSpinBox()
		self.spb_duplicate.setMaximum(20)
		self.spb_duplicate.setMinimum(1)

		# -- Mode checks
		self.chk_outline = QtGui.QCheckBox('Contours')
		self.chk_references = QtGui.QCheckBox('References')
		self.chk_guides = QtGui.QCheckBox('Guides')
		self.chk_anchors = QtGui.QCheckBox('Anchors')
		self.chk_lsb = QtGui.QCheckBox('LSB')
		self.chk_adv = QtGui.QCheckBox('Advance')
		self.chk_rsb = QtGui.QCheckBox('RSB')
		self.chk_links = QtGui.QCheckBox('Links')
		self.chk_tags = QtGui.QCheckBox('Tags')
		self.chk_flag = QtGui.QCheckBox('Flag')
		
		# -- Set States
		self.chk_outline.setCheckState(QtCore.Qt.Checked)
		#self.chk_references.setCheckState(QtCore.Qt.Checked)
		self.chk_guides.setCheckState(QtCore.Qt.Checked)
		self.chk_anchors.setCheckState(QtCore.Qt.Checked)
		self.chk_lsb.setCheckState(QtCore.Qt.Checked)
		self.chk_adv.setCheckState(QtCore.Qt.Checked)
		self.chk_rsb.setCheckState(QtCore.Qt.Checked)
		self.chk_links.setCheckState(QtCore.Qt.Checked)
		self.chk_tags.setCheckState(QtCore.Qt.Checked)
		self.chk_flag.setCheckState(QtCore.Qt.Checked)
	
		# -- Build
		self.addWidget(QtGui.QLabel('Glyph Copy & Duplicate:'), 	0, 0, 1, 2)
		self.addWidget(self.chk_slot01, 				1, 0, 1, 1)
		self.addWidget(self.chk_slot02, 				1, 1, 1, 1)
		self.addWidget(self.chk_slot03, 				1, 2, 1, 1)
		self.addWidget(self.chk_slot04, 				1, 3, 1, 1)
		self.addWidget(self.chk_outline, 				2, 0, 1, 2)
		self.addWidget(self.chk_references,				2, 2, 1, 2)
		self.addWidget(self.chk_lsb, 					3, 0, 1, 1)
		self.addWidget(self.chk_adv, 					3, 1, 1, 1)
		self.addWidget(self.chk_rsb, 					3, 2, 1, 1)
		self.addWidget(self.chk_links, 					3, 3, 1, 1)
		self.addWidget(self.chk_anchors,				4, 0, 1, 1)
		self.addWidget(self.chk_guides, 				4, 1, 1, 1)
		self.addWidget(self.chk_tags, 					4, 2, 1, 1)
		self.addWidget(self.chk_flag, 					4, 3, 1, 1)
		self.addWidget(self.edt_glyphsuffix, 			5, 0, 1, 2)
		self.addWidget(self.spb_duplicate, 				5, 2, 1, 1)
		self.addWidget(self.btn_duplicate, 				5, 3, 1, 1)
		
	def glyph_duplicate(self):
		copy_options = {'out': self.chk_outline.isChecked(),
		 				'gui': self.chk_guides.isChecked(),
		 				'anc': self.chk_anchors.isChecked(),
		 				'lsb': self.chk_lsb.isChecked(),
		 				'adv': self.chk_adv.isChecked(),
		 				'rsb': self.chk_rsb.isChecked(),
		 				'lnk': self.chk_links.isChecked(),
		 				'ref': self.chk_references.isChecked(),
		 				'flg': self.chk_flag.isChecked(),
		 				'tag': self.chk_tags.isChecked()
		 				}
		
		# - Init
		font = pFont()
		process_glyphs = getProcessGlyphs(pMode)
		processed_glyphs = []

		for glyph in process_glyphs:
			glyp_name = glyph.name
				
			for n in range(self.spb_duplicate.value):
				new_name = glyp_name + str(self.edt_glyphsuffix.text)
				token_count = new_name.count(number_token)
				
				if number_token in new_name:
					new_name = new_name.replace('#'*token_count, '%s' ) %fromat_number(n, token_count)

				if font.hasGlyph(new_name):
					new_name = '%s.%s' %(new_name, str(n))

				font.duplicateGlyph(glyp_name, new_name, dst_unicode=None, options=copy_options)						
				processed_glyphs.append(new_name)

		'''
		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)
		'''
		font.updateObject(font.fl, 'Duplicate Glyph(s) | %s' %', '.join(processed_glyphs))
		
			
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
		# - Build ---------------------------
		layoutV.addLayout(TRGlyphBasic())
		layoutV.addLayout(TRGlyphCopyTools())

		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300, self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()