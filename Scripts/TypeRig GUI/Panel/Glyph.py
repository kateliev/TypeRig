#FLM: TR: Glyph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from PythonQt import QtCore

from typerig.core.base.message import *
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRGLineEdit, TRTransformCtrl, fontMarkColors

# - Init --------------------------
global pLayers
global pMode
global pUndo
pLayers = None
pMode = 0
pUndo = True
app_name, app_version = 'TypeRig | Glyph', '1.11'

number_token = '#'

# - String -----------------------------
help_numeration = 'Use # for sequential numeration.\n\nExample:\n#=1; ##=01; ###=001\nA.ss## will crearte A.ss01 to A.ss20'
help_setName = 'Set name for current glyph or multiple selected glyphs (TR Selection mode).\n' + help_numeration
help_duplicate = 'Duplicate current glyph or multiple selected glyphs (TR Selection mode).\n' + help_numeration
str_warning = '<p><b>NOTE</b>: Disabling UNDO will generate the new glyphs, but the font would not update.</p><p>New glyphs will NOT be visible in FontWidow< until your next operation.</p>'

# - Functions --------------------------
fromat_number = lambda x, i: '0'*(i - 1) + str(x) if len(str(x)) < i else str(x)

# - Tabs -------------------------------
class TRGlyphBasic(QtGui.QGridLayout):
	def __init__(self):
		super(TRGlyphBasic, self).__init__()

		# -- Edit fields
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

		# -- Hinting & Stems (Move to other panel later!)
		self.cmb_select_stem =  QtGui.QComboBox()
		self.cmb_select_stem.addItems(['PostScript', 'TrueType'])
		self.btn_setStemV = QtGui.QPushButton('Set &V-Stem')
		self.btn_setStemH = QtGui.QPushButton('Set &H-Stem')
		self.btn_setStemV.clicked.connect(lambda: self.setStem(False))
		self.btn_setStemH.clicked.connect(lambda: self.setStem(True))

		# -- Combo box
		#fontMarkColors = [(QtGui.QColor(name).hue(), name) for name in QtGui.QColor.fontMarkColors()]
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, value, discard in fontMarkColors}
		
		for i in range(len(fontMarkColors)):
			self.cmb_select_color.addItem(fontMarkColors[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

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
		self.addWidget(QtGui.QLabel('\nGlyph selection to Font Stems (Hinting):'),	5, 0, 1, 8)
		self.addWidget(QtGui.QLabel('Type:'), 					6, 0, 1, 1)
		self.addWidget(self.cmb_select_stem, 					6, 1, 1, 3)
		self.addWidget(self.btn_setStemV, 						6, 4, 1, 2)
		self.addWidget(self.btn_setStemH, 						6, 6, 1, 2)

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

		# - Finish operation
		global pUndo
		if pUndo:
			font.updateObject(font.fl, 'Set Glyph(s) %s | %s' %(mode, ', '.join(processed_glyphs)))
		else:
			output(1, app_name, 'Set Glyph(s) %s | %s' %(mode, ', '.join(processed_glyphs)))


	def setStem(self, horizontal=False):
		# - Init
		font = pFont()
		active_glyph = eGlyph()
		
		# - Prepare selection
		selection = {layer_name:active_glyph.selectedNodes(layer_name, True) for layer_name in active_glyph._prepareLayers(pLayers)}
		set_standard_stems = []
		
		# - Set name and metadata
		stem_name = '{}.{}'.format(['V','H'][horizontal], active_glyph.name)
		stem_type = self.cmb_select_stem.currentIndex

		# - Prepare stems
		for layer_name, layer_selection in selection.items():
			if horizontal:
				stem_width = int(abs(layer_selection[0].y - layer_selection[-1].y))
			else:
				stem_width = int(abs(layer_selection[0].x - layer_selection[-1].x))

			set_standard_stems.append((stem_width, stem_name, horizontal, stem_type, layer_name))
		
		# - Set stems
		for stem_data in set_standard_stems:
			font.setStem(*stem_data)

		# - Finish operation
		global pUndo
		if pUndo:
			font.updateObject(font.fl, 'Set Stem(s): {}; {}; {}.'.format(stem_name, stem_width, self.cmb_select_stem.currentText))
		else:
			output(1, app_name, 'Set Stem(s): {}; {}; {}.'.format(stem_name, stem_width, self.cmb_select_stem.currentText))


class TRGlyphCopyTools(QtGui.QGridLayout):
	def __init__(self):
		super(TRGlyphCopyTools, self).__init__()

		# -- Edit Fields
		self.edt_glyphsuffix = TRGLineEdit()
		self.edt_glyphsuffix.setPlaceholderText('Glyph Suffix')
		self.edt_glyphsuffix.setToolTip(help_numeration)

		self.edt_sourceName = TRGLineEdit()
		self.edt_sourceName.setPlaceholderText('Source name / Current')
		self.edt_sourceName.setToolTip('Source glyph name, or Active Glyph if Blank')

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

		self.btn_insert = QtGui.QPushButton('Insert')
		self.btn_insert.setToolTip('Copy contents of source glyph and insert them to current active glyph(s)')
		self.btn_insert.clicked.connect(lambda: self.glyph_insert(False))

		self.btn_insert_mask = QtGui.QPushButton('Mask')
		self.btn_insert_mask.setToolTip('Copy contents of source glyph and insert them as MASK to current active glyph(s)')
		self.btn_insert_mask.clicked.connect(lambda: self.glyph_insert(True))

		self.btn_duplicate.setToolTip(help_duplicate)
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

		# -- Custom controls
		self.tr_trans_ctrl = TRTransformCtrl()
	
		# -- Build
		self.addWidget(QtGui.QLabel('\nCopy and Duplicate Glyph(s) (Options): '), 	0, 0, 1, 4)
		#self.addWidget(self.chk_slot01, 				1, 0, 1, 1)
		#self.addWidget(self.chk_slot02, 				1, 1, 1, 1)
		#self.addWidget(self.chk_slot03, 				1, 2, 1, 1)
		#self.addWidget(self.chk_slot04, 				1, 3, 1, 1)
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
		self.addWidget(self.tr_trans_ctrl,				5, 0, 1, 4)
		self.addWidget(QtGui.QLabel('\nDuplicate Glyph(s) with suffix:'), 	6, 0, 1, 4)
		self.addWidget(self.edt_glyphsuffix, 			7, 0, 1, 2)
		self.addWidget(self.spb_duplicate, 				7, 2, 1, 1)
		self.addWidget(self.btn_duplicate, 				7, 3, 1, 1)
		self.addWidget(QtGui.QLabel('\nInsert contents from glyph source:'), 	8, 0, 1, 4)
		self.addWidget(self.edt_sourceName, 			9, 0, 1, 2)
		self.addWidget(self.btn_insert, 				9, 2, 1, 1)
		self.addWidget(self.btn_insert_mask, 			9, 3, 1, 1)

		self.tr_trans_ctrl.lay_controls.setMargin(0)
		
	def __getOptions(self):
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

		return copy_options

	def glyph_insert(self, asMask=False):
		font = pFont()
		src_glyph_name = self.edt_sourceName.text
		processed_glyphs = []
		
		if len(src_glyph_name) and font.hasGlyph(src_glyph_name):
			copy_options = self.__getOptions()
			process_glyphs = getProcessGlyphs(pMode)
			src_glyph = font.glyph(src_glyph_name)

			for dst_glyph in process_glyphs:
				for src_layer in src_glyph.layers():
					src_layer_name = src_layer.name
					
					if '#' not in src_layer_name:
						new_layer = dst_glyph.importLayer(src_glyph, src_layer_name, src_layer_name, copy_options, True, False, True, ('insert', 'mask')[asMask])
						new_transform, org_transform, rev_transform = self.tr_trans_ctrl.getTransform(new_layer.boundingBox)
						new_layer.applyTransform(org_transform)
						new_layer.applyTransform(new_transform)
						new_layer.applyTransform(rev_transform)

				processed_glyphs.append(dst_glyph.name)

			
			# - Finish operation
			global pUndo
			if pUndo:
				font.updateObject(font.fl, 'Insert Glyph: %s --> %s;' %(src_glyph_name, ', '.join(processed_glyphs)))
			else:
				output(1, app_name, 'Insert Glyph: %s --> %s;' %(src_glyph_name, ', '.join(processed_glyphs)))
		else:
			warnings.warn('Glyph not found: %s;' %(None, src_glyph_name)[1 if len(src_glyph_name) else 0], GlyphWarning)


	def glyph_duplicate(self):
		copy_options = self.__getOptions()
		
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

				new_glyph = font.duplicateGlyph(glyp_name, new_name, dst_unicode=None, options=copy_options)
				
				for layer in new_glyph.layers():
					new_transform, org_transform, rev_transform = self.tr_trans_ctrl.getTransform(layer.boundingBox)
					layer.applyTransform(org_transform)
					layer.applyTransform(new_transform)
					layer.applyTransform(rev_transform)

				processed_glyphs.append(new_name)

		'''
		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)
		'''
		# - Finish operation
		global pUndo
		if pUndo:
			font.updateObject(font.fl, 'Duplicate Glyph(s) | %s' %', '.join(processed_glyphs))
		else:
			output(1, app_name, 'Duplicate Glyph(s) | %s' %', '.join(processed_glyphs))
		
			
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		# - Set Undo controller
		# -- Warning Label
		self.lbl_warn = QtGui.QLabel(str_warning)
		self.lbl_warn.setWordWrap(True)
		self.lbl_warn.setStyleSheet('padding: 10; font-size: 10pt; background: lightpink;')
		self.lbl_warn.hide()

		# -- Buttons
		self.btn_disable_undo = QtGui.QPushButton('Disable UNDO') 
		self.btn_disable_undo.setCheckable(True)
		self.btn_disable_undo.setChecked(False)
		self.btn_disable_undo.clicked.connect(self.undo_set_state)
		
		# - Build ---------------------------
		layoutV.addLayout(TRGlyphBasic())
		layoutV.addLayout(TRGlyphCopyTools())
		layoutV.addWidget(QtGui.QLabel('Font UNDO state:'))
		layoutV.addWidget(self.btn_disable_undo)
		layoutV.addWidget(self.lbl_warn)

		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300, self.sizeHint.height())

	def undo_set_state(self):
		global pUndo
		pUndo = not pUndo
		warnings.warn('Font wide UNDO state changed! Undo Enabled: %s' %pUndo, FontWarning)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()