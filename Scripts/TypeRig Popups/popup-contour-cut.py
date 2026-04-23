#FLM: TypeRig: Popup Contour Cut
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026  	(http://www.kateliev.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import math

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.actions.contour import TRContourActionCollector
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.actions.cut import TRCutActionCollector
from typerig.proxy.fl.actions.mat_extract import TRMatExtractActionCollector
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, CustomSpinLabel, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.core.base.message import *

# - Init --------------------------
tool_version = '1.5'
tool_name = 'TR Popup Contour Cut'

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

def group_nodes_by_neighbors(nodes):
	'''Group nodes into pairs of neighbors using eNode wrapper'''
	if len(nodes) < 4:
		return [], []
	
	pairs = []
	used = set()
	
	for i, node in enumerate(nodes):
		if i in used:
			continue
		
		# Wrap in eNode for neighbor detection
		en = eNode(node)
		
		# Find the neighbor of this node among remaining nodes
		for j, other in enumerate(nodes):
			if j in used or i == j:
				continue
			
			# Check if nodes are neighbors using eNode methods
			next_on = en.getNextOn(False)
			prev_on = en.getPrevOn(False)
			
			if (next_on is not None and next_on.fl == other) or \
			   (prev_on is not None and prev_on.fl == other):
				pairs.append((node, other))
				used.add(i)
				used.add(j)
				break
	
	# Return two pairs (or as many as we found)
	if len(pairs) >= 2:
		return list(pairs[0]), list(pairs[1])
	elif len(pairs) == 1:
		return list(pairs[0]), []
	return [], []

# -- Main Widget --------------------------
class TRPopupContourCut(QtGui.QWidget):
	def __init__(self):
		super(TRPopupContourCut, self).__init__()

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

		# - Flow layout for buttons
		self.lay_main = TRFlowLayout(spacing=6)
		self.lay_main.setContentsMargins(0, 0, 0, 0)

		# - Build buttons
		# -- Close button
		tooltip_button = 'Close popup'
		self.btn_close = CustomPushButton('close', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_close)
		self.btn_close.clicked.connect(lambda: self.close())

		# -- Regular cut button
		tooltip_button = 'Slice selected contours\nAlt: Overlap'
		self.btn_contour_cut = CustomPushButton('contour_cut', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_contour_cut)
		self.btn_contour_cut.clicked.connect(self.do_cut)

		# -- Cut + auto-align (replaces the four directional cut+align buttons)
		tooltip_button = 'Cut contour, then auto overlap align both neighbor pairs\nat the cut junction.'
		self.btn_cut_align_auto = CustomPushButton('cut_stem_overlap', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_cut_align_auto)
		self.btn_cut_align_auto.clicked.connect(self.do_cut_align_auto)

		# -- Auto overlap align (standalone, no cut)
		tooltip_button = 'Auto overlap align\nSelect 4 nodes (2 neighbor pairs) at a cut junction.'
		self.btn_align_auto = CustomPushButton('auto_stem_overlap', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_align_auto)
		self.btn_align_auto.clicked.connect(self.do_align_auto)

		# -- Corner tools
		tooltip_button = 'Pick target node for loop extension.\nSelect 1 on-curve node, then toggle on.\nToggle off to clear target.'
		self.chk_node_target = CustomPushButton('node_target', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		self.lay_main.addWidget(self.chk_node_target)
		self.chk_node_target.clicked.connect(self.target_set)

		tooltip_button = 'Corner Loop\nNo target: loop with radius (dialog).\nWith target: extend corner toward stored target position.'
		self.btn_corner_loop = CustomPushButton('corner_loop', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_corner_loop)
		self.btn_corner_loop.clicked.connect(self.do_corner_loop)

		tooltip_button = 'Safe distance: pull back from target by this amount on each axis.'
		self.spn_safe_distance = CustomSpinLabel('distance', (0, 100, 5, 5), tooltip=tooltip_button, obj_name=('spn_panel', 'lbl_icon'))
		self.lay_main.addWidget(self.spn_safe_distance)

		# -- Stroke separator (V3)
		tooltip_button = 'Stroke Separate (V3)\nSplit stroke glyph into components via MAT analysis.\nApplies to active layer; propagates cuts to all masters.'
		self.btn_stroke_sep = CustomPushButton('cutter_auto', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_stroke_sep)
		self.btn_stroke_sep.clicked.connect(self.do_stroke_sep)

		# -- Medial axis extract
		tooltip_button = 'Medial Axis Extract\nEmit a clean medial-axis skeleton as a new shape\non the active layer. Active layer only (single master).'
		self.btn_mat_extract = CustomPushButton('centerline', tooltip=tooltip_button, obj_name='btn_panel')
		self.lay_main.addWidget(self.btn_mat_extract)
		self.btn_mat_extract.clicked.connect(self.do_mat_extract)

		# - Set container layout
		self.container.setLayout(self.lay_main)

		# - Main layout to hold container
		main_layout = QtGui.QVBoxLayout()
		main_layout.addWidget(self.container)
		self.setLayout(main_layout)
		
		# - Size policy to fit content tightly
		#self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)

		# - Apply styling
		self._apply_style()

		# - Position at cursor and show
		self.setGeometry(100, 100, 420, 20)
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
	def do_cut(self):
		'''Execute cut and close popup'''
		TRContourActionCollector.contour_slice(pMode, pLayers, get_modifier())
		self.close()

	def _align_pair(self, nodes, mode):
		'''Align a pair of nodes based on mode (T=top, B=bottom, C=center)'''
		if len(nodes) != 2:
			return
		
		n1, n2 = nodes
		
		if mode == 'T':
			# Align both to top (max Y)
			target_y = max(n1.y, n2.y)
			n1.y = target_y
			n2.y = target_y
		
		elif mode == 'B':
			# Align both to bottom (min Y)
			target_y = min(n1.y, n2.y)
			n1.y = target_y
			n2.y = target_y
		
		elif mode == 'C':
			# Align both to vertical center
			target_x = (n1.x + n2.x) / 2.0
			n1.x = target_x
			n2.x = target_x

	def _auto_align_mode(self, pair):
		'''Detect the correct alignment mode for a node pair at a cut junction.

		Uses the direction of the segment leaving each junction node into the
		contour interior (away from the other pair node) as the signal:

		  - Interior segments predominantly horizontal -> arm side -> 'C'
		  - Interior segments predominantly vertical   -> stem side:
		      Both interior neighbours above the pair  -> bottom L-junction -> 'B'
		      Both interior neighbours below the pair  -> top L-junction    -> 'T'
		      Interior neighbours on opposite sides    -> T-junction        -> 'C'

		Arguments:
			pair (list): Two FL on-curve node objects that are neighbors.

		Returns:
			str: 'C', 'T', or 'B'.
		'''
		n1, n2 = pair
		total_dx    = 0.0
		total_dy    = 0.0
		interior_ys = []

		for node, other in ((n1, n2), (n2, n1)):
			en      = eNode(node)
			next_on = en.getNextOn(False)
			prev_on = en.getPrevOn(False)

			# Pick the neighbour that is NOT the other pair node
			interior = None
			if next_on is not None and next_on.fl != other:
				interior = next_on.fl
			elif prev_on is not None and prev_on.fl != other:
				interior = prev_on.fl

			if interior is None:
				continue

			total_dx += abs(interior.x - node.x)
			total_dy += abs(interior.y - node.y)
			interior_ys.append(interior.y)

		# Horizontal interior segments -> arm side -> center X
		if not interior_ys or total_dx >= total_dy:
			return 'C'

		# Vertical interior segments -> stem side
		# L-junction: both interior neighbours on the same side of the pair
		# T-junction: interior neighbours on opposite sides -> no vertical snap
		avg_y_pair = (n1.y + n2.y) / 2.0

		if all(y > avg_y_pair for y in interior_ys):
			return 'B'   # all interior above -> junction is at the bottom
		elif all(y < avg_y_pair for y in interior_ys):
			return 'T'   # all interior below -> junction is at the top
		else:
			return 'C'   # T-junction: interior nodes on both sides, no snap

	def do_align_auto(self):
		'''Auto overlap align: classify and align two neighbor-pairs at a cut junction.

		Select 4 on-curve nodes (2 pairs) across two contours at a cut boundary,
		then run this tool.  Each pair is aligned independently based on its
		parent contour's aspect ratio — no cut is performed.
		'''
		glyph   = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			selection = glyph.selectedNodes(layer)

			if len(selection) < 4:
				continue

			pair_first, pair_second = group_nodes_by_neighbors(selection)

			if len(pair_first) == 2:
				self._align_pair(pair_first,  self._auto_align_mode(pair_first))

			if len(pair_second) == 2:
				self._align_pair(pair_second, self._auto_align_mode(pair_second))

		glyph.update()
		glyph.updateObject(glyph.fl, 'Glyph: {}; Auto Overlap Align; Layers: {}'.format(
			glyph.name, '; '.join(wLayers)))
		self.close()

	def do_cut_align_auto(self):
		'''Execute cut, then auto-align the resulting neighbor pairs.

		Combines ``do_cut`` and ``do_align_auto`` into one step: slice the
		contour at the selected nodes, then classify and align the two
		neighbor pairs at the resulting cut junction via the same
		orientation-aware logic used by the standalone auto-align tool.
		'''
		# - Perform the cut
		TRContourActionCollector.contour_slice(pMode, pLayers, get_modifier())

		# - Re-acquire the glyph after the cut and auto-align the pairs
		glyph   = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			selection = glyph.selectedNodes(layer)

			if len(selection) < 4:
				continue

			pair_first, pair_second = group_nodes_by_neighbors(selection)

			if len(pair_first) == 2:
				self._align_pair(pair_first,  self._auto_align_mode(pair_first))

			if len(pair_second) == 2:
				self._align_pair(pair_second, self._auto_align_mode(pair_second))

		glyph.update()
		glyph.updateObject(glyph.fl, 'Glyph: {}; Cut + Auto Align; Layers: {}'.format(
			glyph.name, '; '.join(wLayers)))
		self.close()

	# - Corner procedures ----------------------------
	def target_set(self):
		'''Store or clear target position from selected node.'''
		if self.chk_node_target.isChecked():
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True)

				if len(selection) >= 1:
					node = selection[0]
					self.ext_target[layer] = (node.x, node.y)
					output(0, tool_name, 'Target set @ {}: ({}, {})'.format(layer, node.x, node.y))
				else:
					output(1, tool_name, 'No node selected for target.')
		else:
			self.ext_target = {}
			output(0, tool_name, 'Target cleared.')

	def do_corner_loop(self):
		'''Corner loop in two modes:
		- No target: loop with radius (dialog).
		- With target: extend corner toward stored target position.
		'''
		if self.chk_node_target.isChecked() and len(self.ext_target):
			# - Advanced mode: loop toward stored target position
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				if layer not in self.ext_target:
					continue

				target_x, target_y = self.ext_target[layer]
				safe_distance = self.spn_safe_distance.value
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)

				for node in reversed(selection):
					node.cornerLoopToTargets(target_x, target_y, safe_distance)

			glyph.updateObject(glyph.fl, '{};\tLoop to Target @ {}.'.format(glyph.name, '; '.join(wLayers)))
		else:
			# - Standard mode: radius dialog
			TRNodeActionCollector.corner_loop_dlg(pMode, pLayers)

		self.close()

	def do_corner_mitre(self):
		'''Standard corner mitre via radius dialog'''
		TRNodeActionCollector.corner_mitre_dlg(pMode, pLayers)
		self.close()

	def do_stroke_sep(self):
		'''Stroke Separate (V3): split stroke glyph via MAT analysis.'''
		TRCutActionCollector.stroke_separate_v3(pMode, pLayers)
		self.close()

	def do_mat_extract(self):
		'''Medial Axis Extract: emit a clean skeleton as a new shape.

		Active layer only — MAT is a geometric derivative of the outline,
		so it makes no sense to propagate across masters. The skeleton is
		appended as a new shape; the original outline is not modified.
		'''
		TRMatExtractActionCollector.extract_medial_axis(pMode)
		self.close()

# - RUN ------------------------------
popup = TRPopupContourCut()
