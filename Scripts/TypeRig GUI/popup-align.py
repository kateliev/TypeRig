#FLM: TypeRig: Popup Align
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init --------------------------
tool_version = '1.3'
tool_name = 'TR Popup Align'

TRToolFont_path = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont_path)
families = QtGui.QFontDatabase.applicationFontFamilies(font_loaded)

# -- Global parameters
global pMode
global pLayers
pMode = 0
pLayers = (True, True, False, False)

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

# -- Main Widget --------------------------
class TRPopupAlign(QtGui.QWidget):
	def __init__(self):
		super(TRPopupAlign, self).__init__()

		# - Init
		self.ext_target = {}

		# - Window setup for popup behavior
		self.setWindowFlags(
			QtCore.Qt.FramelessWindowHint | 
			QtCore.Qt.WindowStaysOnTopHint | 
			QtCore.Qt.Tool |
			QtCore.Qt.Popup
		)
		self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

		# - Main container with background
		self.container = QtGui.QFrame(self)
		self.container.setObjectName('popup_container')
		self.container.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)


		# - Flow layout for buttons
		self.lay_main = TRFlowLayout(spacing=6)
		self.lay_main.setContentsMargins(12, 12, 12, 12)

		# - Build toggle options
		self.grp_shift_options = QtGui.QButtonGroup()

		tooltip_button = 'Close popup'
		self.btn_close = CustomPushButton('close', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_close)
		self.btn_close.clicked.connect(lambda: self.close())

		tooltip_button = 'Simple Shift: Shift only selected nodes.'
		self.chk_shift_dumb = CustomPushButton('shift_dumb', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_shift_options.addButton(self.chk_shift_dumb, 1)
		self.lay_main.addWidget(self.chk_shift_dumb)

		tooltip_button = 'Smart Shift: Shift oncurve nodes together with their respective offcurve nodes.'
		self.chk_shift_smart = CustomPushButton('shift_smart', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.grp_shift_options.addButton(self.chk_shift_smart, 2)
		self.lay_main.addWidget(self.chk_shift_smart)

		tooltip_button = 'Keep relations between selected nodes'
		self.chk_shift_keep_dimension = CustomPushButton('shift_keep_dimension', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_main.addWidget(self.chk_shift_keep_dimension)

		tooltip_button =  "Interpolated shift"
		self.chk_shift_lerp = CustomPushButton("shift_interpolate", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_main.addWidget(self.chk_shift_lerp)

		tooltip_button = 'Pick target node for alignment'
		self.chk_node_target = CustomPushButton('node_target', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_main.addWidget(self.chk_node_target)
		self.chk_node_target.clicked.connect(self.target_set)

		tooltip_button = 'Collapse all selected nodes to target'
		self.btn_node_target_collapse = CustomPushButton('node_target_collapse', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_target_collapse)
		self.btn_node_target_collapse.clicked.connect(self.target_collapse)

		# - Build action buttons
		tooltip_button = 'Align selected nodes top'
		self.btn_node_align_top = CustomPushButton('node_align_top', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_top)
		self.btn_node_align_top.clicked.connect(lambda: self.do_align('T'))

		tooltip_button = 'Align selected nodes bottom'
		self.btn_node_align_bottom = CustomPushButton('node_align_bottom', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_bottom)
		self.btn_node_align_bottom.clicked.connect(lambda: self.do_align('B'))

		tooltip_button = 'Align selected nodes left'
		self.btn_node_align_left = CustomPushButton('node_align_left', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_left)
		self.btn_node_align_left.clicked.connect(lambda: self.do_align('L'))

		tooltip_button = 'Align selected nodes right'
		self.btn_node_align_right = CustomPushButton('node_align_right', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_right)
		self.btn_node_align_right.clicked.connect(lambda: self.do_align('R'))

		tooltip_button = 'Align selected node in the horizontal middle of its direct neighbors'
		self.btn_node_align_neigh_x = CustomPushButton('node_align_neigh_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_neigh_x)
		self.btn_node_align_neigh_x.clicked.connect(lambda: self.do_align('peerCenterX'))

		tooltip_button = 'Align selected node in the vertical middle of its direct neighbors'
		self.btn_node_align_neigh_y = CustomPushButton('node_align_neigh_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_neigh_y)
		self.btn_node_align_neigh_y.clicked.connect(lambda: self.do_align('peerCenterY'))

		tooltip_button = 'Align selected nodes to the horizontal middle of outline bounding box.'
		self.btn_node_align_outline_x = CustomPushButton('node_align_outline_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_outline_x)
		self.btn_node_align_outline_x.clicked.connect(lambda: self.do_align('BBoxCenterX'))

		tooltip_button = 'Align selected nodes to the vertical middle of outline bounding box.'
		self.btn_node_align_outline_y = CustomPushButton('node_align_outline_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_outline_y)
		self.btn_node_align_outline_y.clicked.connect(lambda: self.do_align('BBoxCenterY'))

		tooltip_button = 'Align selected nodes to horizontal center of selection'
		self.btn_node_align_selection_x = CustomPushButton('node_align_selection_x', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_selection_x)
		self.btn_node_align_selection_x.clicked.connect(lambda: self.do_align('C'))

		tooltip_button = 'Align selected nodes to vertical center of selection'
		self.btn_node_align_selection_y = CustomPushButton('node_align_selection_y', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_node_align_selection_y)
		self.btn_node_align_selection_y.clicked.connect(lambda: self.do_align('E'))

		# - Set container layout
		self.container.setLayout(self.lay_main)

		# - Main layout to hold container (small margin for border visibility)
		main_layout = QtGui.QVBoxLayout()
		#main_layout.setContentsMargins(2, 2, 2, 2)
		main_layout.addWidget(self.container)
		self.setLayout(main_layout)
		
		# - Size policy to fit content tightly
		self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)

		# - Apply styling
		self._apply_style()

		# - Position at cursor and show
		self.setGeometry(100,100,100,100)
		self._position_at_cursor()
		self.show()

	def _apply_style(self):
		'''Apply custom styling for popup appearance'''
		is_dark = fl6.flPreferences().isDark
		
		# Get base stylesheet (contains icon font settings)
		base_style = css_tr_button_dark if is_dark else css_tr_button
		
		# Additional popup-specific styling
		if is_dark:
			bg_color = 'rgba(45, 45, 45, 200)'
			border_color = 'rgba(80, 80, 80, 255)'
		else:
			bg_color = 'rgba(245, 245, 245, 200)'
			border_color = 'rgba(180, 180, 180, 255)'

		popup_style = '''
			QFrame#popup_container {{
				background-color: {bg};
				border: 1px solid {border};
				border-radius: 6px;
				padding: 4px;
			}}
		'''.format(
			bg=bg_color,
			border=border_color
		)

		# Combine base style with popup additions
		self.setStyleSheet(base_style + popup_style)

	def _position_at_cursor(self):
		'''Position the popup near the cursor'''
		cursor_pos = QtGui.QCursor.pos()
		
		# Resize to fit content tightly
		#self.container.adjustSize()
		#self.adjustSize()
		#self.resize(self.sizeHint)
		
		# Get screen geometry to avoid going off-screen
		screen = QtGui.QApplication.desktop().screenGeometry()
		
		# Calculate position (offset slightly from cursor)
		x = cursor_pos.x() + 5
		y = cursor_pos.y() + 5
		
		# Adjust if going off-screen
		screen_width = screen.width()
		screen_height = screen.height()
		
		if x + self.width > screen_width:
			x = cursor_pos.x() - self.width - 10
		if y + self.height > screen_height:
			y = cursor_pos.y() - self.height - 10
		
		self.move(x, y)

	# - Procedures -----------------------------------
	def do_align(self, mode):
		'''Execute alignment and close popup'''
		TRNodeActionCollector.nodes_align(
			pMode, 
			pLayers, 
			mode, 
			False,  # intercept
			self.chk_shift_keep_dimension.isChecked(), 
			self.chk_shift_smart.isChecked(), 
			self.ext_target,
			self.chk_shift_lerp.isChecked()
		)
		self.close()

	def target_set(self):
		'''Set or clear target node'''
		if self.chk_node_target.isChecked():
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer)

				if len(selection) > 1:
					# Set target in the middle of selection
					med_x = round(sum([n.x for n in selection])/len(selection))
					med_y = round(sum([n.y for n in selection])/len(selection))
					self.ext_target[layer] = fl6.flNode(QtCore.QPointF(med_x, med_y))
				elif len(selection) == 1:
					self.ext_target[layer] = selection[0]
		else:
			self.ext_target = {}

	def target_collapse(self):
		'''Collapse selected nodes to target and close popup'''
		if self.chk_node_target.isChecked() and len(self.ext_target.keys()):
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				if layer in self.ext_target.keys():
					for node in glyph.selectedNodes(layer):
						node.x = self.ext_target[layer].x
						node.y = self.ext_target[layer].y

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: {}; Nodes collapsed; Layers:\t {}'.format(glyph.name, '; '.join(wLayers)))
		
		self.close()

# - RUN ------------------------------
popup = TRPopupAlign()
