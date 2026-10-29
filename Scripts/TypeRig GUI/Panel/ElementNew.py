#FLM: TR: Elements New
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.actions.element import TRElementActionCollector
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, TRTransformCtrl, CustomPushButton, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, False, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Elements New', '0.2'

brush_weight_presets = ['10', '20', '30', '40', '50', '60', '80', '100', '120', '160']

TRToolFont_path = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont_path)

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

def text_button(caption, tooltip, action):
	button = QtGui.QPushButton(caption)
	button.setToolTip(tooltip)
	button.clicked.connect(action)
	return button

# - Sub widgets ------------------------
class TRElementBasics(QtGui.QWidget):
	def __init__(self):
		super(TRElementBasics, self).__init__()

		# - Init
		self.style_clipboard = {}

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()

		# - Merge and separate ------------------------------------------------
		box_merge = QtGui.QGroupBox()
		box_merge.setObjectName('box_group')
		lay_merge = QtGui.QGridLayout()

		self.chk_whole = QtGui.QCheckBox('Whole elements')
		self.chk_whole.setToolTip('Merge takes every contour of each touched element,\nnot only the contours with selected nodes.')

		lay_merge.addWidget(QtGui.QLabel('Merge:'), 0, 0, 1, 3)
		lay_merge.addWidget(self.chk_whole, 0, 3, 1, 3)

		lay_merge.addWidget(text_button('New', 'Merge selected contours into a new element\nabove the topmost touched element.\nIt takes the style and transform of the topmost element.',
				lambda: TRElementActionCollector.element_merge(pMode, pLayers, 'new', self.chk_whole.isChecked())), 1, 0, 1, 2)
		lay_merge.addWidget(text_button('Top', 'Merge selected contours into the topmost touched element.',
				lambda: TRElementActionCollector.element_merge(pMode, pLayers, 'top', self.chk_whole.isChecked())), 1, 2, 1, 2)
		lay_merge.addWidget(text_button('Bottom', 'Merge selected contours into the bottommost touched element.',
				lambda: TRElementActionCollector.element_merge(pMode, pLayers, 'bottom', self.chk_whole.isChecked())), 1, 4, 1, 2)

		lay_merge.addWidget(QtGui.QLabel('Separate:'), 2, 0, 1, 6)
		lay_merge.addWidget(text_button('Eject', 'Move the selected contours of every element\ninto a new element right above it.\nIt keeps the style and transform of its source.',
				lambda: TRElementActionCollector.element_eject(pMode, pLayers)), 3, 0, 1, 2)
		lay_merge.addWidget(text_button('Islands', 'Split touched elements into one element per island:\nan outer contour together with its counters.',
				lambda: TRElementActionCollector.element_split(pMode, pLayers, True)), 3, 2, 1, 2)
		lay_merge.addWidget(text_button('Contours', 'Split touched elements into one element per contour.',
				lambda: TRElementActionCollector.element_split(pMode, pLayers, False)), 3, 4, 1, 2)

		lay_merge.addWidget(QtGui.QLabel('Group:'), 4, 0, 1, 6)
		lay_merge.addWidget(text_button('Group', 'Group touched elements.\nThe group takes the place of the topmost one.',
				lambda: TRElementActionCollector.element_group(pMode, pLayers)), 5, 0, 1, 2)
		lay_merge.addWidget(text_button('Ungroup', 'Ungroup touched groups.\nMouse Left + Alt: Eject members without applying the group transform.',
				lambda: TRElementActionCollector.element_ungroup(pMode, pLayers, not get_modifier())), 5, 2, 1, 2)
		lay_merge.addWidget(text_button('From selection', 'New group from selection:\nselected contours leave their elements, keeping each source\'s style and transform,\nand are grouped together.',
				lambda: TRElementActionCollector.element_group_contours(pMode, pLayers)), 5, 4, 1, 2)

		box_merge.setLayout(lay_merge)
		self.lay_main.addWidget(box_merge)

		# - Arrange ------------------------------------------------------------
		box_arrange = QtGui.QGroupBox()
		box_arrange.setObjectName('box_group')
		lay_arrange = QtGui.QGridLayout()

		lay_arrange.addWidget(QtGui.QLabel('Arrange:'), 0, 0, 1, 6)
		lay_arrange.addWidget(text_button('Forward', 'Move touched elements one step up the stack.',
				lambda: TRElementActionCollector.element_reorder(pMode, pLayers, 'up')), 1, 0, 1, 2)
		lay_arrange.addWidget(text_button('Backward', 'Move touched elements one step down the stack.',
				lambda: TRElementActionCollector.element_reorder(pMode, pLayers, 'down')), 1, 2, 1, 2)
		lay_arrange.addWidget(text_button('Reverse', 'Reverse the stacking order of touched elements.',
				lambda: TRElementActionCollector.element_reorder(pMode, pLayers, 'reverse')), 1, 4, 1, 2)
		lay_arrange.addWidget(text_button('To front', 'Bring touched elements to the front.',
				lambda: TRElementActionCollector.element_reorder(pMode, pLayers, 'front')), 2, 0, 1, 3)
		lay_arrange.addWidget(text_button('To back', 'Send touched elements to the back.',
				lambda: TRElementActionCollector.element_reorder(pMode, pLayers, 'back')), 2, 3, 1, 3)

		box_arrange.setLayout(lay_arrange)
		self.lay_main.addWidget(box_arrange)

		# - Align ----------------------------------------------------------------
		box_align = QtGui.QGroupBox()
		box_align.setObjectName('box_group')

		self.grp_align_options = QtGui.QButtonGroup()
		self.grp_align_options.setExclusive(True)

		lay_align = TRFlowLayout(spacing=10)

		self.align_options = []
		for icon_name, align_mode, tooltip_button, checked in [
				('align_contour_to_contour', 'SEL', 'Align to the bounds of all touched elements', True),
				('align_group_to_group', 'KEY', 'Align to the topmost touched element (key element)\nMouse Left + Alt: bottommost', False),
				('align_contour_to_layer', 'LAY', 'Align to the layer: advance width, descender to ascender', False),
				('dimension_caps', 'CMC', 'Align to Caps Height', False),
				('dimension_ascender', 'CMA', 'Align to Ascender', False),
				('dimension_xheight', 'CMX', 'Align to X Height', False),
				('dimension_descender', 'CMD', 'Align to Descender', False)]:

			button = CustomPushButton(icon_name, checkable=True, checked=checked, tooltip=tooltip_button, obj_name='btn_panel_opt')
			self.grp_align_options.addButton(button)
			self.align_options.append((button, align_mode))
			lay_align.addWidget(button)

		for icon_name, align_x, align_y, tooltip_button in [
				('contour_align_left', 'L', None, 'Align left'),
				('contour_align_center_horizontal', 'C', None, 'Align horizontal centers'),
				('contour_align_right', 'R', None, 'Align right'),
				('contour_align_bottom', None, 'B', 'Align bottom'),
				('contour_align_center_vertical', None, 'E', 'Align vertical centers'),
				('contour_align_top', None, 'T', 'Align top')]:

			button = CustomPushButton(icon_name, tooltip=tooltip_button, obj_name='btn_panel')
			button.clicked.connect(lambda checked=False, ax=align_x, ay=align_y: self.align_elements(ax, ay))
			lay_align.addWidget(button)

		tooltip_button = 'Distribute touched elements horizontally'
		self.btn_distribute_h = CustomPushButton('contour_distribute_h', tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_distribute_h.clicked.connect(lambda: TRElementActionCollector.element_distribute(pMode, pLayers, False))
		lay_align.addWidget(self.btn_distribute_h)

		tooltip_button = 'Distribute touched elements vertically'
		self.btn_distribute_v = CustomPushButton('contour_distribute_v', tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_distribute_v.clicked.connect(lambda: TRElementActionCollector.element_distribute(pMode, pLayers, True))
		lay_align.addWidget(self.btn_distribute_v)

		tooltip_button = 'Flip touched elements horizontally'
		self.btn_flip_h = CustomPushButton('flip_horizontal', tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_flip_h.clicked.connect(lambda: TRElementActionCollector.element_flip(pMode, pLayers, False))
		lay_align.addWidget(self.btn_flip_h)

		tooltip_button = 'Flip touched elements vertically'
		self.btn_flip_v = CustomPushButton('flip_vertical', tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_flip_v.clicked.connect(lambda: TRElementActionCollector.element_flip(pMode, pLayers, True))
		lay_align.addWidget(self.btn_flip_v)

		box_align.setLayout(lay_align)
		self.lay_main.addWidget(box_align)

		# - Transform --------------------------------------------------------
		self.ctrl_transform = TRTransformCtrl()
		self.ctrl_transform.btn_transform.setToolTip('Transform touched elements.\nNon-destructive: only the element transform changes.')
		self.ctrl_transform.btn_transform.clicked.connect(lambda: TRElementActionCollector.element_transform_ctrl(pMode, pLayers, self.ctrl_transform))
		self.lay_main.addWidget(self.ctrl_transform)

		# - Style ------------------------------------------------------------
		box_style = QtGui.QGroupBox()
		box_style.setObjectName('box_group')
		lay_style = QtGui.QGridLayout()

		self.chk_fill = QtGui.QCheckBox('Fill')
		self.chk_stroke = QtGui.QCheckBox('Stroke')
		self.chk_opacity = QtGui.QCheckBox('Opacity')
		self.chk_style = QtGui.QCheckBox('Style')

		self.chk_fill.setToolTip('Element brush (fill color)')
		self.chk_stroke.setToolTip('Element pen (stroke)')
		self.chk_opacity.setToolTip('Element opacity')
		self.chk_style.setToolTip('FontLab element style (assignStyle): flags such as non-spacing and the rest FontLab keeps with it')

		for column, check in enumerate((self.chk_fill, self.chk_stroke, self.chk_opacity, self.chk_style)):
			check.setChecked(True)
			lay_style.addWidget(check, 1, column, 1, 1)

		lay_style.addWidget(QtGui.QLabel('Properties:'), 0, 0, 1, 4)
		lay_style.addWidget(text_button('Copy', 'Copy properties of the topmost touched element.',
				lambda: self.style_copy()), 2, 0, 1, 1)
		lay_style.addWidget(text_button('Paste', 'Paste copied properties onto touched elements.',
				lambda: TRElementActionCollector.element_style_paste(pMode, pLayers, self.style_clipboard, self.style_parts())), 2, 1, 1, 1)
		lay_style.addWidget(text_button('Match', 'Give all touched elements the properties of the topmost one.\nMouse Left + Alt: of the bottommost one.',
				lambda: TRElementActionCollector.element_style_match(pMode, pLayers, get_modifier(), self.style_parts())), 2, 2, 1, 2)

		box_style.setLayout(lay_style)
		self.lay_main.addWidget(box_style)

		# - Brush --------------------------------------------------------------
		box_brush = QtGui.QGroupBox()
		box_brush.setObjectName('box_group')
		lay_brush = QtGui.QGridLayout()

		self.cmb_brush_weight = QtGui.QComboBox()
		self.cmb_brush_weight.setEditable(True)
		self.cmb_brush_weight.addItems(brush_weight_presets)
		self.cmb_brush_weight.setToolTip('Brush weight: pick a preset or type any value.')

		self.spb_brush_step = QtGui.QDoubleSpinBox()
		self.spb_brush_step.setRange(0.1, 1000.)
		self.spb_brush_step.setValue(5.)
		self.spb_brush_step.setToolTip('Step for decrease / increase.')

		lay_brush.addWidget(QtGui.QLabel('Brush weight:'), 0, 0, 1, 6)
		lay_brush.addWidget(self.cmb_brush_weight, 1, 0, 1, 2)
		lay_brush.addWidget(text_button('Set', 'Set the brush weight of touched elements on all processed layers.',
				lambda: self.brush_weight_set()), 1, 2, 1, 2)
		lay_brush.addWidget(text_button('Pick', 'Read the brush weight of the topmost touched element.',
				lambda: self.brush_weight_pick()), 1, 4, 1, 2)
		lay_brush.addWidget(self.spb_brush_step, 2, 0, 1, 2)
		lay_brush.addWidget(text_button('-', 'Decrease the brush weight of touched elements by step.\nEach layer keeps its own weight, only the step is subtracted.',
				lambda: TRElementActionCollector.element_stroke_width(pMode, pLayers, -self.spb_brush_step.value, True)), 2, 2, 1, 2)
		lay_brush.addWidget(text_button('+', 'Increase the brush weight of touched elements by step.\nEach layer keeps its own weight, only the step is added.',
				lambda: TRElementActionCollector.element_stroke_width(pMode, pLayers, self.spb_brush_step.value, True)), 2, 4, 1, 2)

		box_brush.setLayout(lay_brush)
		self.lay_main.addWidget(box_brush)

		# - Manage -----------------------------------------------------------
		box_manage = QtGui.QGroupBox()
		box_manage.setObjectName('box_group')
		lay_manage = QtGui.QGridLayout()

		self.edt_name = QtGui.QLineEdit()
		self.edt_name.setPlaceholderText('Element name')

		lay_manage.addWidget(QtGui.QLabel('Manage:'), 0, 0, 1, 6)
		lay_manage.addWidget(self.edt_name, 1, 0, 1, 4)
		lay_manage.addWidget(text_button('Rename', 'Name touched elements. Several get numbered: name.1, name.2 ...',
				lambda: TRElementActionCollector.element_rename(pMode, pLayers, self.edt_name.text)), 1, 4, 1, 2)

		lay_manage.addWidget(text_button('Duplicate', 'Duplicate touched elements as independent copies right above them.',
				lambda: TRElementActionCollector.element_duplicate(pMode, pLayers)), 2, 0, 1, 2)
		lay_manage.addWidget(text_button('Unlink', 'Replace shared (referenced) elements with independent copies.\nNeeded before moving contours in or out of them.',
				lambda: TRElementActionCollector.element_unlink(pMode, pLayers)), 2, 2, 1, 2)
		lay_manage.addWidget(text_button('Select all', 'Select every node of the touched elements.',
				lambda: TRElementActionCollector.element_select_whole()), 2, 4, 1, 2)

		lay_manage.addWidget(text_button('Apply TX', 'Apply the element transform onto its contours and reset it.',
				lambda: TRElementActionCollector.element_bake_transform(pMode, pLayers)), 3, 0, 1, 2)
		lay_manage.addWidget(text_button('Reset TX', 'Reset the element transform, contours stay as they are.',
				lambda: TRElementActionCollector.element_reset_transform(pMode, pLayers)), 3, 2, 1, 2)
		lay_manage.addWidget(text_button('Clean', 'Remove empty elements.',
				lambda: TRElementActionCollector.element_clean_empty(pMode, pLayers)), 3, 4, 1, 2)

		lay_manage.addWidget(text_button('Report element stack', 'Print the element stack of the active layer, front to back, to the Output panel.\nTouched elements are marked with *.',
				lambda: TRElementActionCollector.element_report()), 4, 0, 1, 6)

		box_manage.setLayout(lay_manage)
		self.lay_main.addWidget(box_manage)

		# - Finish it ---------------------------------------------------------
		self.lay_main.addStretch()
		self.setLayout(self.lay_main)

	# - Procedures -----------------------------------------------
	def align_elements(self, align_x, align_y):
		align_mode = [mode for button, mode in self.align_options if button.isChecked()][0]
		TRElementActionCollector.element_align(pMode, pLayers, align_mode, align_x, align_y, get_modifier())

	def style_parts(self):
		return tuple(part for part, check in (('fill', self.chk_fill), ('stroke', self.chk_stroke), ('opacity', self.chk_opacity), ('style', self.chk_style)) if check.isChecked())

	def style_copy(self):
		self.style_clipboard = TRElementActionCollector.element_style_copy(pMode, pLayers)

	def brush_weight_set(self):
		try:
			weight = float(self.cmb_brush_weight.currentText)
		except ValueError:
			output(2, app_name, 'Brush weight is not a number: {}'.format(self.cmb_brush_weight.currentText))
			return

		TRElementActionCollector.element_stroke_width(pMode, pLayers, weight)

	def brush_weight_pick(self):
		weight = TRElementActionCollector.element_stroke_width_get()
		if weight is not None: self.cmb_brush_weight.setEditText('{:g}'.format(weight))

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)

		layoutV = QtGui.QVBoxLayout()
		layoutV.setContentsMargins(0, 0, 0, 0)

		# - Add widgets to main dialog
		layoutV.addWidget(TRElementBasics())

		# - Build
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

	test.show()
