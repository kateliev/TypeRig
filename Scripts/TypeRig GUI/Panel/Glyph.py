#FLM: TR: Glyph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2025 	(http://www.kateliev.com)
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

from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
#from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRGLineEdit, TRTransformCtrl, fontMarkColors, getTRIconFontPath, CustomPushButton, TRFlowLayout, CustomLabel
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init --------------------------
global pLayers
global pMode
global pUndo
pLayers = None
pMode = 0
pUndo = True
app_name, app_version = 'TypeRig | Glyph', '2.2'

number_token = '#'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - String -----------------------------
help_numeration = 'Use # for sequential numeration.\n\nExample:\n#=1; ##=01; ###=001\nA.ss## will create A.ss01, A.ss02, A.ss03, etc.'
help_setName = 'Set name for current glyph or multiple selected glyphs (TR Selection mode).\n' + help_numeration
help_duplicate = 'Duplicate current glyph or multiple selected glyphs (TR Selection mode).\n' + help_numeration
str_warning = '<p><b>NOTE</b>: Disabling UNDO will generate new glyphs, but the font will not update immediately.</p><p>New glyphs will NOT be visible in Font Window until your next operation.</p>'

# - Functions --------------------------
fromat_number = lambda x, i: '0'*(i - 1) + str(x) if len(str(x)) < i else str(x)

# - Tabs -------------------------------
class TRGlyphBasic(QtGui.QWidget):
	def __init__(self):
		super(TRGlyphBasic, self).__init__()

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()

		# - Widgets and tools -------------------------------------------------
		# -- Glyph Basics -----------------------------------------------------
		box_basics = QtGui.QGroupBox()
		box_basics.setObjectName('box_group')
		
		lay_basics = QtGui.QGridLayout()
		lay_basics.setSpacing(6)
		lay_basics.addWidget(QtGui.QLabel('Glyph Basics'), 0, 0, 1, 4)

		# -- Name field
		self.edt_glyphName = TRGLineEdit()
		self.edt_glyphName.setPlaceholderText('Glyph Name')
		self.edt_glyphName.setToolTip(help_setName + '\n\n' + help_numeration)
		lay_basics.addWidget(self.edt_glyphName, 1, 0, 1, 3)

		self.btn_setName = CustomPushButton('glyph_active', tooltip=help_setName, obj_name='btn_panel')
		self.btn_setName.clicked.connect(lambda: self.glyph_setBasics('name'))
		lay_basics.addWidget(self.btn_setName, 1, 3, 1, 1)

		# -- Flag field
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, value, discard in fontMarkColors}
		
		for i in range(len(fontMarkColors)):
			self.cmb_select_color.addItem(fontMarkColors[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

		self.cmb_select_color.setMinimumWidth(40)
		self.cmb_select_color.setToolTip('Select flag color')
		lay_basics.addWidget(self.cmb_select_color, 2, 0, 1, 3)

		self.btn_setFlag = CustomPushButton('flag', tooltip='Set glyph flag color', obj_name='btn_panel')
		self.btn_setFlag.clicked.connect(lambda: self.glyph_setBasics('flag'))
		lay_basics.addWidget(self.btn_setFlag, 2, 3, 1, 1)

		# -- Tags field
		self.edt_glyphTags = TRGLineEdit()
		self.edt_glyphTags.setPlaceholderText('Set tags: comma separated')
		self.edt_glyphTags.setToolTip('Enter glyph tags (space separated)')
		lay_basics.addWidget(self.edt_glyphTags, 3, 0, 1, 3)

		self.btn_setTags = CustomPushButton('label', tooltip='Set glyph tags', obj_name='btn_panel')
		self.btn_setTags.clicked.connect(lambda: self.glyph_setBasics('tags'))
		lay_basics.addWidget(self.btn_setTags, 3, 3, 1, 1)

		# -- Unicode field
		self.edt_glyphUnis = TRGLineEdit()
		self.edt_glyphUnis.setPlaceholderText('Set unicodes: hex, integer, or character')
		self.edt_glyphUnis.setToolTip('Enter unicode values separated by comma\nFormats: hex (2C1C), integer (11292), or character (Ж)')
		lay_basics.addWidget(self.edt_glyphUnis, 4, 0, 1, 3)

		self.btn_setUnis = CustomPushButton('select_glyph', tooltip='Set glyph unicode values', obj_name='btn_panel')
		self.btn_setUnis.clicked.connect(lambda: self.glyph_setBasics('unicode'))
		lay_basics.addWidget(self.btn_setUnis, 4, 3, 1, 1)

		box_basics.setLayout(lay_basics)
		self.lay_main.addWidget(box_basics)

		# -- Glyph Stems (Hinting) -------------------------------------------
		box_stems = QtGui.QGroupBox()
		box_stems.setObjectName('box_group')
		
		lay_stems = QtGui.QGridLayout()
		lay_stems.setSpacing(6)
		lay_stems.addWidget(QtGui.QLabel('Standard Stems'), 0, 0, 1, 4)

		self.cmb_select_stem = QtGui.QComboBox()
		self.cmb_select_stem.addItems(['PostScript', 'TrueType'])
		self.cmb_select_stem.setToolTip('Select stem type')
		lay_stems.addWidget(self.cmb_select_stem, 1, 0, 1, 2)

		self.btn_setStemV = CustomPushButton('stem_vertical', tooltip='Set vertical stem from selection', obj_name='btn_panel')
		self.btn_setStemV.clicked.connect(lambda: self.setStem(False))
		lay_stems.addWidget(self.btn_setStemV, 1, 2, 1, 1)

		self.btn_setStemH = CustomPushButton('stem_horizontal', tooltip='Set horizontal stem from selection', obj_name='btn_panel')
		self.btn_setStemH.clicked.connect(lambda: self.setStem(True))
		lay_stems.addWidget(self.btn_setStemH, 1, 3, 1, 1)

		box_stems.setLayout(lay_stems)
		self.lay_main.addWidget(box_stems)

		# -- Finish it -------------------------------------------------------
		self.setLayout(self.lay_main)

	def __parse_unicodes(self, unicode_string):
		"""Parse unicode input from various formats: hex strings, integers, or single characters.
		Returns list of unicode integers."""
		unicode_list = []
		
		if not unicode_string or not len(unicode_string.strip()):
			return unicode_list
		
		# Split by comma and process each value
		values = [v.strip() for v in unicode_string.split(',')]
		
		for value in values:
			if not value:
				continue
			
			try:
				# Try as hex string (like "2C1C")
				if all(c in '0123456789ABCDEFabcdef' for c in value):
					uni_int = int(value, 16)
					unicode_list.append(uni_int)
				# Try as integer string (like "11292")
				elif value.isdigit():
					uni_int = int(value)
					unicode_list.append(uni_int)
				# Try as single character (like "Ж")
				elif len(value) == 1:
					uni_int = ord(value)
					unicode_list.append(uni_int)
				else:
					warnings.warn('Cannot parse unicode value: {}'.format(value), GlyphWarning)
			except ValueError as e:
				warnings.warn('Error parsing unicode value: {}; Error: {}'.format(value, e), GlyphWarning)
		
		return unicode_list

	def glyph_setBasics(self, mode):
		font = pFont()
		process_glyphs = getProcessGlyphs(pMode)
		processed_glyphs = []
		added_unicodes = []
		
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

			if mode == 'tags': 
				new_tags = [item.strip() for item in str(self.edt_glyphTags.text).split(',')]
				glyph.setTags(new_tags, append=False)

			if mode == 'unicode':
				unicode_values = self.__parse_unicodes(str(self.edt_glyphUnis.text))
				glyph_added = []
				glyph.unicodes = []
				
				for uni_int in unicode_values:
					if not glyph.fg.hasUnicode(uni_int):
						glyph.fg.addUnicode(uni_int)
						glyph_added.append('U+{:04X}'.format(uni_int))
				
				if glyph_added:
					added_unicodes.append('{}: {}'.format(glyph.name, ', '.join(glyph_added)))

				self.edt_glyphUnis.clear()
			
			processed_glyphs.append(glyph.name)

		# - Finish operation
		global pUndo
		if pUndo:
			font.updateObject(font.fl, 'Set Glyph(s) %s | %s' %(mode, ', '.join(processed_glyphs)))
		else:
			output(1, app_name, 'Set Glyph(s) %s | %s' %(mode, ', '.join(processed_glyphs)))
		
		# - Print added unicodes
		if mode == 'unicode' and added_unicodes:
			output(0, app_name, 'Added unicodes:\n' + '\n'.join(added_unicodes))


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


class TRGlyphCopyTools(QtGui.QWidget):
	def __init__(self):
		super(TRGlyphCopyTools, self).__init__()

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		
		# - Widgets and tools -------------------------------------------------
		# -- Duplicate Glyph --------------------------------------------------
		box_duplicate = QtGui.QGroupBox()
		box_duplicate.setObjectName('box_group')
		
		lay_duplicate = QtGui.QGridLayout()
		lay_duplicate.setSpacing(6)
		lay_duplicate.addWidget(QtGui.QLabel('Duplicate Glyph'), 0, 0, 1, 2)

		self.edt_glyphsuffix = TRGLineEdit()
		self.edt_glyphsuffix.setPlaceholderText('Set new glyph suffix')
		self.edt_glyphsuffix.setToolTip(help_duplicate + '\n\n' + help_numeration)
		lay_duplicate.addWidget(self.edt_glyphsuffix, 1, 0, 1, 2)

		self.spb_duplicate = QtGui.QSpinBox()
		self.spb_duplicate.setMaximum(20)
		self.spb_duplicate.setMinimum(1)
		self.spb_duplicate.setToolTip('Number of duplicates to create')
		lay_duplicate.addWidget(self.spb_duplicate, 1, 2, 1, 1)

		self.btn_duplicate = CustomPushButton('align_group_to_group', tooltip=help_duplicate, obj_name='btn_panel')
		self.btn_duplicate.clicked.connect(self.glyph_duplicate)
		lay_duplicate.addWidget(self.btn_duplicate, 1, 3, 1, 1)

		box_duplicate.setLayout(lay_duplicate)
		self.lay_main.addWidget(box_duplicate)

		# -- Copy Options -----------------------------------------------------
		box_options = QtGui.QGroupBox()
		box_options.setObjectName('box_group')
		
		lay_options = TRFlowLayout(spacing=10)

		# -- Checkable icon buttons for copy options
		self.chk_outline = CustomPushButton('contour', checkable=True, checked=True, tooltip='Copy contours', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_outline)

		self.chk_references = CustomPushButton('shape', checkable=True, checked=False, tooltip='Copy references', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_references)

		self.chk_lsb = CustomPushButton('metrics_lsb', checkable=True, checked=True, tooltip='Copy LSB', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_lsb)

		self.chk_adv = CustomPushButton('metrics_advance', checkable=True, checked=True, tooltip='Copy Advance', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_adv)

		self.chk_rsb = CustomPushButton('metrics_rsb', checkable=True, checked=True, tooltip='Copy RSB', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_rsb)

		self.chk_links = CustomPushButton('guide_zone', checkable=True, checked=True, tooltip='Copy links', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_links)

		self.chk_anchors = CustomPushButton('icon_anchor', checkable=True, checked=True, tooltip='Copy anchors', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_anchors)

		self.chk_guides = CustomPushButton('guide_horizontal', checkable=True, checked=True, tooltip='Copy guides', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_guides)

		self.chk_tags = CustomPushButton('label', checkable=True, checked=True, tooltip='Copy tags', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_tags)

		self.chk_flag = CustomPushButton('flag', checkable=True, checked=True, tooltip='Copy flag', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_flag)

		self.chk_disable_undo = CustomPushButton('alert', checkable=True, checked=False, tooltip='Disable UNDO for faster operation\n\nWARNING: Changes will not update immediately', obj_name='btn_panel_opt')
		self.chk_disable_undo.clicked.connect(self.__set_undo_state)
		lay_options.addWidget(self.chk_disable_undo)

		tooltip_button = 'Show transformation controls'
		self.chk_transform = CustomPushButton("diagonal_bottom_up", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_transform)

		box_options.setLayout(lay_options)
		self.lay_main.addWidget(box_options)

		# -- Warning Label
		self.lbl_warn = QtGui.QLabel(str_warning)
		self.lbl_warn.setWordWrap(True)
		self.lbl_warn.setStyleSheet('padding: 10; font-size: 10pt; background: lightpink;')
		self.lbl_warn.hide()
		self.lay_main.addWidget(self.lbl_warn)

		# -- Transform Controls -----------------------------------------------
		self.ctrl_transform = TRTransformCtrl()
		self.ctrl_transform.btn_transform.hide()
		self.lay_main.addWidget(self.ctrl_transform)

		self.ctrl_transform.hide()
		self.chk_transform.clicked.connect(lambda: self.__toggle(self.chk_transform, self.ctrl_transform))

		# -- Insert from Source -----------------------------------------------
		box_insert = QtGui.QGroupBox()
		box_insert.setObjectName('box_group')
		
		lay_insert = QtGui.QGridLayout()
		lay_insert.setSpacing(6)
		lay_insert.addWidget(QtGui.QLabel('Insert from source:'), 0, 0, 1, 2)

		self.edt_sourceName = TRGLineEdit()
		self.edt_sourceName.setPlaceholderText('Source name / Current')
		self.edt_sourceName.setToolTip('Source glyph name, or Active Glyph if Blank')
		lay_insert.addWidget(self.edt_sourceName, 1, 0, 1, 2)

		self.btn_insert = CustomPushButton('layer_add', tooltip='Copy contents of source glyph and insert them to current active glyph(s)', obj_name='btn_panel')
		self.btn_insert.clicked.connect(lambda: self.glyph_insert(False))
		lay_insert.addWidget(self.btn_insert, 1, 2, 1, 1)

		self.btn_insert_mask = CustomPushButton('layer_mask_add', tooltip='Copy contents of source glyph and insert them as MASK to current active glyph(s)', obj_name='btn_panel')
		self.btn_insert_mask.clicked.connect(lambda: self.glyph_insert(True))
		lay_insert.addWidget(self.btn_insert_mask, 1, 3, 1, 1)

		box_insert.setLayout(lay_insert)
		self.lay_main.addWidget(box_insert)

		# -- Finish it -------------------------------------------------------
		self.setLayout(self.lay_main)

	def __set_undo_state(self):
		global pUndo
		pUndo = not pUndo
		warnings.warn('Font wide UNDO state changed! Undo Enabled: %s' %pUndo, FontWarning)
		
		if not pUndo:
			self.lbl_warn.show()
		else:
			self.lbl_warn.hide()
	
	def __toggle(self, trigger, widget):
		if trigger.isChecked():
			widget.show()
		else:
			widget.hide()

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
						new_transform, org_transform, rev_transform = self.ctrl_transform.getTransform(new_layer.boundingBox)
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
					new_transform, org_transform, rev_transform = self.ctrl_transform.getTransform(layer.boundingBox)
					layer.applyTransform(org_transform)
					layer.applyTransform(new_transform)
					layer.applyTransform(rev_transform)

				processed_glyphs.append(new_name)

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
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)

		layoutV = QtGui.QVBoxLayout()
		layoutV.setContentsMargins(0, 0, 0, 0)
		
		# - Build ---------------------------
		layoutV.addWidget(TRGlyphBasic())
		layoutV.addWidget(TRGlyphCopyTools())
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