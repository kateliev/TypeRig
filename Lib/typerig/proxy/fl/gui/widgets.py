# MODULE: Typerig / GUI / Widgets
# NOTE	: Assorted Gui Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
from __future__ import absolute_import
from platform import system
from math import radians

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

# - Init ----------------------------------
__version__ = '0.2.6'

# -- Colors ------------------------------
# Fontlab Name, Fontlab Value, QtColor Name
fontMarkColors = [
					(u'white', 0, u'white'),
					(u'red', 1, u'red'),
					(u'coral', 16, u'coral'),
					(u'sienna', 20, u'sienna'),
					(u'bisque', 37, u'bisque'),
					(u'gold', 50, u'gold'),
					(u'yellow', 61, u'yellow'),
					(u'yellow green', 79, u'yellowgreen'),
					(u'sulu', 90, u'chartreuse'),
					(u'green', 121, u'green'),
					(u'spring green', 145, u'springgreen'),
					(u'aquamarine', 151, u'aquamarine'),
					(u'turquoise', 174, u'turquoise'),
					(u'cyan', 181, u'cyan'),
					(u'skyblue', 195, u'skyblue'),
					(u'maya blue', 210, u'cornflowerblue'),
					(u'blue', 241, u'blue'),
					(u'heliotrope', 271, u'blueviolet'),
					(u'indigo', 274, u'indigo'),
					(u'magenta', 301, u'magenta'),
					(u'rose', 330, u'hotpink'),
					(u'pink', 350, u'pink'),
					(u'gray', 361, u'lightgray')
					]

# - Functions --------------------------
def getProcessGlyphs(mode=0, font=None, workspace=None):
	'''Returns a list of glyphs for processing in TypeRig gui apps

	Args:
		mode (int): 0 - Current active glyph; 1 - All glyphs in current window; 2 - All selected glyphs; 3 - All glyphs in font
		font (fgFont) - Font file (object)
		workspace (flWorkspace) - Workspace
	
	Returns:
		list(eGlyph)
	'''
	# - Init
	process_glyphs = []
	active_workspace = pWorkspace()
	active_font = pFont(font)
		
	# - Collect process glyphs
	if mode == 0: process_glyphs.append(eGlyph())
	if mode == 1: process_glyphs = [eGlyph(glyph) for glyph in active_workspace.getTextBlockGlyphs()]
	if mode == 2: process_glyphs = active_font.selectedGlyphs(extend=eGlyph) 
	if mode == 3: process_glyphs = active_font.glyphs(extend=eGlyph)
	
	return process_glyphs
	
# - Classes -------------------------------
# -- ListViews ----------------------------
class TRGlyphSelect(QtGui.QWidget):
	# - Split/Break contour 
	def __init__(self, font=None, parent=None):
		super(TRGlyphSelect, self).__init__()

		# - Init
		self.active_font = font
		self.parentWgt = self.parent if parent is None else parent

		# - Widgets
		# -- Buttons
		self.btn_filter = QtGui.QPushButton('Refresh')
		self.btn_filter.clicked.connect(self.refresh)

		self.chk_glyphName = QtGui.QCheckBox('Name')
		self.chk_glyphMark = QtGui.QCheckBox('Mark')
		self.chk_glyphUnicode = QtGui.QCheckBox('Unicode')
		self.chk_glyphChecked = QtGui.QCheckBox('Check all')

		self.chk_glyphName.setChecked(True)
		self.chk_glyphMark.setChecked(True)
		self.chk_glyphUnicode.setChecked(True)
		self.chk_glyphChecked.setChecked(True)
		
		# -- Fileds
		self.edt_filter = QtGui.QLineEdit()
		self.edt_filter.setPlaceholderText('Filter glyphnames')
		self.edt_filter.textChanged.connect(self.__filterClicked)

		self.lst_glyphNames = QtGui.QListView(self.parentWgt)
		self.model = QtGui.QStandardItemModel(self.lst_glyphNames)
		
		if self.active_font is not None:
			self.refresh()
		
		# -- Build Layout
		self.layout = QtGui.QGridLayout()
		self.layout.addWidget(QtGui.QLabel('Destination Glyphs:'),	0,0,1,4)
		self.layout.addWidget(self.edt_filter,			1,0,1,3)
		self.layout.addWidget(self.btn_filter,			1,3,1,1)
		self.layout.addWidget(self.chk_glyphName,		2,0,1,1)
		self.layout.addWidget(self.chk_glyphUnicode,	2,1,1,1)
		self.layout.addWidget(self.chk_glyphMark,		2,2,1,1)
		self.layout.addWidget(self.chk_glyphChecked,	2,3,1,1)
		self.layout.addWidget(self.lst_glyphNames,		3,0,1,4)
		
	def refresh(self):
		# - Init
		self.model.removeRows(0, self.model.rowCount())
		self.data_glyphs = getProcessGlyphs(pMode)

		# - Set Items
		for glyph in self.data_glyphs:
			glyph_name = ''

			# - GlyphName
			if self.chk_glyphUnicode.isChecked():
				try:
					glyph_name += str(hex(glyph.unicode)).upper() + '\t'
				except TypeError:
					glyph_name += ' '*6 + '\t'

			if self.chk_glyphName.isChecked():
				glyph_name += glyph.name			
			
			item = QtGui.QStandardItem(glyph_name)

			# - Set Mark
			if self.chk_glyphMark.isChecked():
				new_color = QtGui.QColor(fontMarkColors[glyph.mark])
				new_color.setAlpha(30)
				item.setBackground(QtGui.QBrush(new_color))
			
			# - Set Check
			item.setCheckable(True)
			if self.chk_glyphChecked.isChecked():
				item.setChecked(True)

			self.model.appendRow(item)
		
		self.lst_glyphNames.setModel(self.model)

	def __filterClicked(self):
		filter_text = self.edt_filter.text.lower()
		
		for row in range(self.model.rowCount()):
			if filter_text in self.model.item(row).text().lower():
				self.lst_glyphNames.setRowHidden(row, False)
			else:
				self.lst_glyphNames.setRowHidden(row, True)
				self.lst_glyphNames.item(row),setChecked(False)

	def getGlyphs(self):
		selected_glyphs = []
		for row in range(self.model.rowCount()):
			if self.model.item(row).checkState() == QtCore.Qt.Checked:
				selected_glyphs.append(self.model.item(row).text())

		return selected_glyphs

# -- Messages & Dialogs -------------------
class TRMsgSimple(QtGui.QVBoxLayout):
	def __init__(self, msg):
		super(TRMsgSimple, self).__init__()
		self.warnMessage = QtGui.QLabel(msg)
		self.warnMessage.setOpenExternalLinks(True)
		self.warnMessage.setWordWrap(True)
		self.addWidget(self.warnMessage)

class TR1FieldDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_size=(300, 300, 300, 100)):
		super(TR1FieldDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.edt_field_t = QtGui.QLineEdit() # Top field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		2, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	2, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = self.edt_field_t.text

class TR2FieldDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_field_b, dlg_size=(300, 300, 300, 100)):
		super(TR2FieldDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.lbl_field_b = QtGui.QLabel(dlg_field_b)
		
		self.edt_field_t = QtGui.QLineEdit() # Top field
		self.edt_field_b = QtGui.QLineEdit() # Bottom field

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.lbl_field_b,	2, 0, 1, 2)
		main_layout.addWidget(self.edt_field_b,	2, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = (self.edt_field_t.text, self.edt_field_b.text)

class TR2ComboDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_field_t, dlg_field_b, dlg_field_b_items, dlg_size=(300, 300, 300, 100)):
		super(TR2ComboDLG, self).__init__()
		# - Init
		self.values = (None, None)
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_field_t = QtGui.QLabel(dlg_field_t)
		self.lbl_field_b = QtGui.QLabel(dlg_field_b)
		
		self.edt_field_t = QtGui.QLineEdit() # Top field
		self.cmb_field_b = QtGui.QComboBox() # Bottom Combo Box
		self.cmb_field_b.addItems(dlg_field_b_items)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 	0, 0, 1, 4)
		main_layout.addWidget(self.lbl_field_t,	1, 0, 1, 2)
		main_layout.addWidget(self.edt_field_t,	1, 2, 1, 2)
		main_layout.addWidget(self.lbl_field_b,	2, 0, 1, 2)
		main_layout.addWidget(self.cmb_field_b,	2, 2, 1, 2)
		main_layout.addWidget(self.btn_ok,		3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,	3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		self.values = (self.edt_field_t.text, self.cmb_field_b.currentIndex)

class TRColorDLG(QtGui.QDialog):
	def __init__(self, dlg_name, dlg_msg, dlg_size=(300, 300, 300, 100)):
		super(TRColorDLG, self).__init__()
		
		# - Init
		from typerig.proxy.fl.gui.widgets import fontMarkColors
		self.values = (None, None)
		self.color_codes = {name:value for name, discard, value in fontMarkColors}
		
		# - Widgets
		self.lbl_main = QtGui.QLabel(dlg_msg)
		self.lbl_color = QtGui.QLabel('\nColor Presets:')
		
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, discard, value in fontMarkColors}
		
		for i in range(len(fontMarkColors)):
			self.cmb_select_color.addItem(fontMarkColors[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

		self.btn_ok = QtGui.QPushButton('OK', self)
		self.btn_cancel = QtGui.QPushButton('Cancel', self)

		self.btn_ok.clicked.connect(self.return_values)
		self.btn_cancel.clicked.connect(self.reject)
		
		# - Build 
		main_layout = QtGui.QGridLayout() 
		main_layout.addWidget(self.lbl_main, 			0, 0, 1, 4)
		main_layout.addWidget(self.lbl_color, 			1, 0, 1, 4)
		main_layout.addWidget(self.cmb_select_color,	2, 0, 1, 4)
		main_layout.addWidget(self.btn_ok,				3, 0, 1, 2)
		main_layout.addWidget(self.btn_cancel,			3, 2, 1, 2)

		# - Set 
		self.setLayout(main_layout)
		self.setWindowTitle(dlg_name)
		self.setGeometry(*dlg_size)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		self.exec_()

	def return_values(self):
		self.accept()
		selection_name = self.color_codes[self.cmb_select_color.currentText]
		self.values = (selection_name,  QtGui.QColor(selection_name))

# - Line Edit ----------------------------
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
		menu.addAction(u'.bak', lambda: self.setText('%s.bak' %self.text))

# -- Transform Controls ------------------
class TRTransformCtrl(QtGui.QWidget):
	def __init__(self):
		super(TRTransformCtrl, self).__init__()

		# - Combos 
		self.rad_or = QtGui.QRadioButton('ORG')
		self.rad_bl = QtGui.QRadioButton('BL')
		self.rad_tl = QtGui.QRadioButton('TL')
		self.rad_br = QtGui.QRadioButton('BR')
		self.rad_tr = QtGui.QRadioButton('TR')
		self.rad_ce = QtGui.QRadioButton('CEN')

		# - Spinboxes
		self.spb_scale_x = QtGui.QSpinBox()
		self.spb_scale_y = QtGui.QSpinBox()
		self.spb_translate_x = QtGui.QSpinBox()
		self.spb_translate_y = QtGui.QSpinBox()
		self.spb_shear = QtGui.QSpinBox()
		self.spb_rotate = QtGui.QSpinBox()

		self.spb_scale_x.setMinimum(0)
		self.spb_scale_y.setMinimum(0)
		self.spb_translate_x.setMinimum(-9999)
		self.spb_translate_y.setMinimum(-9999)
		self.spb_shear.setMinimum(-90)
		self.spb_rotate.setMinimum(-360)

		self.spb_scale_x.setMaximum(999)
		self.spb_scale_y.setMaximum(999)
		self.spb_translate_x.setMaximum(9999)
		self.spb_translate_y.setMaximum(9999)
		self.spb_shear.setMaximum(90)
		self.spb_rotate.setMaximum(360)

		self.reset()

		# - Build
		self.lay_controls = QtGui.QGridLayout()
		self.lay_controls.addWidget(QtGui.QLabel('Scale X:'),			0, 0, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Scale Y:'),			0, 1, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Trans. X:'),			0, 2, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Trans. Y:'),			0, 3, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Shear:'),				0, 4, 1, 1)
		self.lay_controls.addWidget(QtGui.QLabel('Rotate:'),			0, 5, 1, 1)
		self.lay_controls.addWidget(self.spb_scale_x,					1, 0, 1, 1)
		self.lay_controls.addWidget(self.spb_scale_y,					1, 1, 1, 1)
		self.lay_controls.addWidget(self.spb_translate_x,				1, 2, 1, 1)
		self.lay_controls.addWidget(self.spb_translate_y,				1, 3, 1, 1)
		self.lay_controls.addWidget(self.spb_shear,						1, 4, 1, 1)
		self.lay_controls.addWidget(self.spb_rotate,					1, 5, 1, 1)
		self.lay_controls.addWidget(self.rad_or,						2, 0, 1, 1)
		self.lay_controls.addWidget(self.rad_bl,						2, 1, 1, 1)
		self.lay_controls.addWidget(self.rad_tl,						2, 2, 1, 1)
		self.lay_controls.addWidget(self.rad_br,						2, 3, 1, 1)
		self.lay_controls.addWidget(self.rad_tr,						2, 4, 1, 1)
		self.lay_controls.addWidget(self.rad_ce,						2, 5, 1, 2)
				
		self.setLayout(self.lay_controls)
		
	def reset(self):
		self.spb_scale_x.setValue(100)
		self.spb_scale_y.setValue(100)
		self.spb_translate_x.setValue(0)
		self.spb_translate_y.setValue(0)
		self.spb_shear.setValue(0)
		self.spb_rotate.setValue(0)
		self.rad_or.setChecked(True)

	def getTransform(self, obj_rect=QtCore.QRectF(.0, .0, .0, .0)):
		# - Init
		origin_transform = QtGui.QTransform()
		rev_origin_transform = QtGui.QTransform()
		return_transform = QtGui.QTransform()
		
		m11 = float(self.spb_scale_x.value)/100.
		m13 = float(self.spb_translate_x.value)
		m22 = float(self.spb_scale_y.value)/100.
		m23 = float(self.spb_translate_y.value)

		# - Transform
		if self.rad_or.isChecked():	transform_origin = QtCore.QPointF(.0, .0)
		if self.rad_bl.isChecked():	transform_origin = obj_rect.topLeft()
		if self.rad_br.isChecked():	transform_origin = obj_rect.topRight()
		if self.rad_tl.isChecked():	transform_origin = obj_rect.bottomLeft()
		if self.rad_tr.isChecked():	transform_origin = obj_rect.bottomRight()
		if self.rad_ce.isChecked():	transform_origin = obj_rect.center()
		
		origin_transform.translate(-transform_origin.x(), -transform_origin.y())
		rev_origin_transform.translate(transform_origin.x(), transform_origin.y())

		return_transform.scale(m11, m22)
		return_transform.rotate(-float(self.spb_rotate.value))
		return_transform.shear(radians(float(self.spb_shear.value)), 0.)
		return_transform.translate(m13, m23)

		return return_transform, origin_transform, rev_origin_transform

# -- Sliders ------------------------------
class TRSliderCtrl(QtGui.QGridLayout):
	def __init__(self, edt_0, edt_1, edt_pos, spb_step):
		super(TRSliderCtrl, self).__init__()
		
		# - Init
		self.initValues = (edt_0, edt_1, edt_pos, spb_step)

		self.edt_0 = QtGui.QLineEdit(edt_0)
		self.edt_1 = QtGui.QLineEdit(edt_1)
		self.edt_pos = QtGui.QLineEdit(edt_pos)

		self.spb_step = QtGui.QSpinBox()
		self.spb_step.setValue(spb_step)

		self.sld_axis = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.sld_axis.valueChanged.connect(self.sliderChange)
		self.refreshSlider()
		
		self.edt_0.editingFinished.connect(self.refreshSlider)
		self.edt_1.editingFinished.connect(self.refreshSlider)
		self.spb_step.valueChanged.connect(self.refreshSlider)
		self.edt_pos.editingFinished.connect(self.refreshSlider)

		# - Layout		
		self.addWidget(self.sld_axis, 			0, 0, 1, 5)
		self.addWidget(self.edt_pos, 			0, 5, 1, 1)		
		self.addWidget(QtGui.QLabel('Min:'),	1, 0, 1, 1)
		self.addWidget(self.edt_0, 				1, 1, 1, 1)
		self.addWidget(QtGui.QLabel('Max:'), 	1, 2, 1, 1)
		self.addWidget(self.edt_1, 				1, 3, 1, 1)
		self.addWidget(QtGui.QLabel('Step:'),	1, 4, 1, 1)
		self.addWidget(self.spb_step, 			1, 5, 1, 1)


	def refreshSlider(self):
		self.sld_axis.blockSignals(True)
		self.sld_axis.setMinimum(float(self.edt_0.text.strip()))
		self.sld_axis.setMaximum(float(self.edt_1.text.strip()))
		self.sld_axis.setValue(float(self.edt_pos.text.strip()))
		self.sld_axis.setSingleStep(int(self.spb_step.value))
		self.sld_axis.blockSignals(False)
				
	def reset(self):
		self.edt_0.setText(self.initValues[0])
		self.edt_1.setText(self.initValues[1])
		self.edt_pos.setText(self.initValues[2])
		self.spb_step.setValue(self.initValues[3])
		self.refreshSlider()

	def sliderChange(self):
		self.edt_pos.setText(self.sld_axis.value)

# -- Tables ------------------------------------------------------
class TRTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(TRTableView, self).__init__()

		# - Init
		self.flag_valueChanged = QtGui.QColor('powderblue')

		# - Set 
		if data is not None: self.setTable(data)
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		self.setShowGrid(False)
		self.setSortingEnabled(False)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, sortData=(True, True), indexColCheckable=None):
		name_row, name_column = [], []
		self.blockSignals(True)

		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Populate
		for row, value in enumerate(sorted(data.keys()) if sortData[0] else data.keys()):
			name_row.append(value)
			
			for col, key in enumerate(sorted(data[value].keys()) if sortData[1] else data[value].keys()):
				name_column.append(key)
				rowData = data[value][key]
				
				if isinstance(rowData, basestring):
					newitem = QtGui.QTableWidgetItem(str(rowData))
				else:
					newitem = QtGui.QTableWidgetItem()
					newitem.setData(QtCore.Qt.EditRole, rowData)
									
				# - Make the columnt checkable
				if indexColCheckable is not None and col in indexColCheckable:
					newitem.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
					newitem.setCheckState(QtCore.Qt.Unchecked) 

				self.setItem(row, col, newitem)

		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self, raw=False):
		return_list = []

		for row in range(self.rowCount):
			if not raw:
				return_list.append((self.verticalHeaderItem(row).text(), {self.horizontalHeaderItem(col).text():float(self.item(row, col).text()) for col in range(self.columnCount)}))
			else:
				return_list.append((self.verticalHeaderItem(row).text(), [(self.horizontalHeaderItem(col).text(), self.item(row, col).text()) for col in range(self.columnCount)]))

		if raw:	return return_list			
		return dict(return_list)
		

	def markChange(self, item):
		item.setBackground(self.flag_valueChanged)


# - Folder/collapsible widgets
class TRCollapsibleBox(QtGui.QWidget):
	def __init__(self, title="", parent=None):
		super(TRCollapsibleBox, self).__init__(parent)

		self.toggle_button = QtGui.QToolButton()
		self.toggle_button.text = '  ' + title
		self.toggle_button.checkable = True
		self.toggle_button.checked = True
		self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; color: #505050; vertical-align: middle }")
		self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
		self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
		self.toggle_button.setIconSize(QtCore.QSize(5,5))
		self.toggle_button.clicked.connect(self.on_pressed)

		self.toggle_animation = QtCore.QParallelAnimationGroup(self)

		self.content_area = QtGui.QScrollArea()
		self.content_area.maximumHeight = 0
		self.content_area.minimumHeight = 0

		self.content_area.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
		self.content_area.setFrameShape(QtGui.QFrame.NoFrame)

		lay = QtGui.QVBoxLayout(self)
		lay.setSpacing(0)
		lay.setContentsMargins(0, 0, 0, 0)
		lay.addWidget(self.toggle_button)
		lay.addWidget(self.content_area)

		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
		self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self.content_area, b"maximumHeight"))

	def on_pressed(self):
		checked = self.toggle_button.isChecked()
		
		self.toggle_button.setArrowType(QtCore.Qt.DownArrow if not checked else QtCore.Qt.RightArrow)
		self.toggle_animation.setDirection(QtCore.QAbstractAnimation.Forward if not checked	else QtCore.QAbstractAnimation.Backward)
		self.toggle_animation.start()

	def setContentLayout(self, layout):
		lay = self.content_area.layout()
		del lay
		self.content_area.setLayout(layout)
		collapsed_height = (self.sizeHint.height() - self.content_area.maximumHeight)
		content_height = layout.sizeHint().height()

		for i in range(self.toggle_animation.animationCount()):
			animation = self.toggle_animation.animationAt(i)
			animation.setDuration(100)
			animation.setStartValue(collapsed_height)
			animation.setEndValue(collapsed_height + content_height)

		content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
		content_animation.setDuration(100)
		content_animation.setStartValue(0)
		content_animation.setEndValue(content_height)


# - Tab Widgets -----------------------------------------------------------
class TRHTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-bottom: 10px;
				padding: 5px 7px 4px 7px; 
				margin-right: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')

class TRVTabWidget(QtGui.QTabWidget):
	def __init__(self, *args, **kwargs):
		super(QtGui.QTabWidget, self).__init__(*args, **kwargs)
		self.setUsesScrollButtons(True)
		self.setTabPosition(QtGui.QTabWidget.East)
		if system() == 'Darwin':
			self.setStyleSheet('''
			QTabBar::tab { 
				margin-left: 11px;
				padding: 5px 4px 5px 5px; 
				margin-bottom: 1px;
				color: black; 
				background-color: white; 
				border: none; 
			}
			QTabBar::tab:selected { 
				color: white; 
				background-color: #808080; 
			}
			''')
