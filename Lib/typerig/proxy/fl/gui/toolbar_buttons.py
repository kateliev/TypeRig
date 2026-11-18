# MODULE: TypeRig / Proxy / FontLab / GUI / Toolbar Buttons
# NOTE	: The declarative button table of the unified TypeRig Toolbar + the widget builder.
#	  Order and grouping follow the Glyphs sidebar palette (TypeRig-Glyphs tr_toolbar.py).
#	  Parity with Glyphs: Docs/Proxy/Documents/FL-toolbar-parity.md
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
from __future__ import absolute_import, print_function
from collections import namedtuple
from functools import partial

from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFont
from typerig.proxy.fl.gui.dialogs import TRLayerSelectNEW
from typerig.proxy.fl.gui.toolbar_actions import TRToolbarState, TRToolbarActions, guarded

# - Init ----------------------------------
__version__ = '1.0'

# One button: token = icon font ligature name (an unknown token renders as literal text)
Button = namedtuple('Button', 'token tip callback checkable name exclusive checked')
Field = namedtuple('Field', 'name default tip')

def B(token, tip, callback=None, checkable=False, name=None, exclusive=None, checked=False):
	'''callback None = disabled placeholder cell'''
	return Button(token, tip, callback, checkable, name or token, exclusive, checked)

# - Button table --------------------------
def toolbar_sections(act):
	'''The toolbar in Glyphs order: a tuple of (key, caption, groups). Each group is one flow() call of the
	Glyphs palette (a row / a cluster), tuple order = button order. A Field entry is a one-cell text field.

	Foldable sections are NOT built (the keys + captions below are the fold targets). The Glyphs palette
	can also cut sections down through toolbar-sections.json ([["node", true], ["align", false], ...];
	see TypeRig-Glyphs Lib/toolbar_guide.md) - not built here either.
	'''
	alt_one = '\n+Alt: one selected node is enough'

	return (
		# SECTION 'observers' - Glyphs-only sidebar helpers (never folds). GLYPHS-ONLY: they are built on
		# Glyphs observers and FontLab has no equivalent hook (canvas_overlay needs one tool per helper).
		# Disabled placeholder cells - owner decision pending. See FL-toolbar-parity.md.
		('observers', None, (
			(
				B('visible', 'Layer toast (Glyphs only: not available in FontLab)', None, True),
				B('stem_vertical_alt', 'Stem probe (Glyphs only: not available in FontLab)', None, True),
				B('interpolate', 'Node slide (Glyphs only: not available in FontLab)', None, True),
				B('node_add', 'Node add ghost (Glyphs only: not available in FontLab)', None, True),
				B('keyboard_arows', 'Key nudge (Glyphs only: not available in FontLab)', None, True),
			),
		)),

		# SECTION 'node' - Nodes & Corners (fold target)
		('node', 'Nodes & Corners', (
			(
				B('node_add_bgn', 'Insert node at the beginning of a Bezier (select both ends)' + alt_one + '\n+Ctrl: FL dialog', partial(act.node_insert, 0.)),
				B('node_add_mid', 'Insert node at the middle of a Bezier (select both ends)' + alt_one + '\n+Ctrl: FL dialog', partial(act.node_insert, .5)),
				B('node_add_end', 'Insert node at the end of a Bezier (select both ends)' + alt_one + '\n+Ctrl: FL dialog', partial(act.node_insert, 1.)),
				B('node_add_extreme_alt', 'Add nodes at extremes (select both ends)', act.node_insert_extreme),
				B('node_remove', 'Remove selected nodes', act.node_remove),
				B('node_round', 'Round selected nodes to integer coordinates\nClick: ceil. +Alt: floor. +Shift: round all nodes', act.node_round),
			),
			(
				B('corner_mitre', 'Corner mitre (size: corner field)\n+Ctrl: FL dialog', act.corner_mitre),
				B('corner_round', 'Corner round (size: corner field)\n+Ctrl: FL dialog', act.corner_round),
				B('corner_loop', 'Corner loop (overlap: corner field)\n+Ctrl: FL dialog', act.corner_loop),
				B('corner_trap', 'Create ink trap\n+Alt: non-smooth basic trap', act.corner_trap),
				B('corner_rebuild', 'Rebuild corner', act.corner_rebuild),
				Field('fld_corner', '20', 'Corner size: mitre / round size, loop overlap'),
			),
		)),

		# SECTION 'align' - Align (fold target)
		('align', 'Align', (
			( # Options. FL defaults: Simple shift on, everything else off
				B('shift_dumb', 'Simple shift: shift only selected nodes', act.noop, True, exclusive='shift', checked=True),
				B('shift_smart', 'Smart shift: shift on-curve nodes together with their off-curve nodes', act.noop, True, exclusive='shift'),
				B('shift_keep_dimension', 'Keep relations between selected nodes', act.noop, True),
				B('shift_interpolate', 'Interpolated shift (Interpolated Nudge)', act.noop, True),
				B('shift_intercept', 'Intercept vertical position', act.noop, True),
				B('extrapolate', 'Extrapolate: slide on-curve nodes along their curve', act.noop, True),
			),
			(
				B('node_align_left', 'Align selected nodes left', partial(act.align, 'L')),
				B('node_align_right', 'Align selected nodes right', partial(act.align, 'R')),
				B('node_align_top', 'Align selected nodes top', partial(act.align, 'T')),
				B('node_align_bottom', 'Align selected nodes bottom', partial(act.align, 'B')),
				B('node_align_selection_x', 'Align selected nodes to horizontal center of selection', partial(act.align, 'C')),
				B('node_align_selection_y', 'Align selected nodes to vertical center of selection', partial(act.align, 'E')),
			),
			(
				B('node_align_outline_x', 'Align selected nodes to the horizontal middle of outline bounding box', partial(act.align, 'BBoxCenterX')),
				B('node_align_outline_y', 'Align selected nodes to the vertical middle of outline bounding box', partial(act.align, 'BBoxCenterY')),
				B('node_align_neigh_x', 'Align selected node in the horizontal middle of its direct neighbors', partial(act.align, 'peerCenterX')),
				B('node_align_neigh_y', 'Align selected node in the vertical middle of its direct neighbors', partial(act.align, 'peerCenterY')),
				B('node_align_min_max_Y', 'Align selected nodes to a line between highest and lowest node in selection', partial(act.align, 'Y')),
				B('node_align_min_max_X', 'Align selected nodes to a line between lowest and highest node in selection', partial(act.align, 'X')),
			),
			(
				B('dimension_ascender', 'Align selected nodes to Font metrics: Ascender', partial(act.align, 'FontMetrics_0')),
				B('dimension_caps', 'Align selected nodes to Font metrics: Caps height', partial(act.align, 'FontMetrics_1')),
				B('dimension_xheight', 'Align selected nodes to Font metrics: X height', partial(act.align, 'FontMetrics_3')),
				B('dimension_baseline', 'Align selected nodes to Font metrics: Baseline', partial(act.align, 'FontMetrics_4')),
				B('dimension_descender', 'Align selected nodes to Font metrics: Descender', partial(act.align, 'FontMetrics_2')),
				B('dimension_guide', 'Align selected nodes to Measurement line (FL only)', partial(act.align, 'FontMetrics_5')),
				B('node_target', 'Pick align target per master: 1 node = that node, several = center of selection; align actions then use it', act.target_toggle, True),
			),
			(
				B('node_target_collapse', 'Collapse all selected nodes to target', act.target_collapse),
			),
		)),

		# SECTION 'curve' - Curves (fold target)
		('curve', 'Curves', (
			(
				B('node_smooth', 'Convert node to smooth', partial(act.node_smooth, True)),
				B('node_sharp', 'Convert node to sharp', partial(act.node_smooth, False)),
				B('line_to_curve', 'Convert selected segment to curve (select both ends)', partial(act.segment_convert, True)),
				B('curve_to_line', 'Convert selected segment to line (select both ends)', partial(act.segment_convert, False)),
				B('curve_tunni', 'Optimize curve: Tunni (select both ends)', partial(act.curve_optimize, 'tunni')),
				B('curve_retract_alt', 'Retract curve handles (select both ends)', partial(act.curve_optimize, 'proportional', 0., 0.)),
			),
			(
				B('curve_hobby', 'Optimize curve: Set Hobby curvature at P0 / P1 in a dialog (select both ends)', partial(act.curve_optimize_dlg, 'hobby')),
				B('curve_hobby_1', 'Optimize curve: Set Hobby curvature to 1. (select both ends)', partial(act.curve_optimize, 'hobby', 1., 1.)),
				B('curve_hobby_95', 'Optimize curve: Set Hobby curvature to .95 (select both ends)', partial(act.curve_optimize, 'hobby', .95, .95)),
				B('curve_hobby_90', 'Optimize curve: Set Hobby curvature to .90 (select both ends)', partial(act.curve_optimize, 'hobby', .90, .90)),
				B('curve_prop_alt', 'Optimize curve: Set handle proportion at P0 / P1 in a dialog (select both ends)', partial(act.curve_optimize_dlg, 'proportional')),
				B('curve_prop_30', 'Optimize curve: Set handle proportion to 30% of curve length (select both ends)', partial(act.curve_optimize, 'proportional', .3, .3)),
				B('curve_prop_50', 'Optimize curve: Set handle proportion to 50% of curve length (select both ends)', partial(act.curve_optimize, 'proportional', .5, .5)),
			),
			(
				B('curve_hobby_copy', 'Copy Hobby curvature from the first selected curve segment (select both ends)', act.hobby_copy),
				B('curve_hobby_paste', 'Paste stored Hobby curvature onto selected curve segments (select both ends)', partial(act.hobby_paste, False)),
				B('curve_hobby_paste', 'Paste Hobby curvature with alpha/beta swapped (mirrored tension)', partial(act.hobby_paste, True), name='hobby_paste_swap'),
				B('curve_copy', 'Optimize curve: Copy handle proportions to masters (FL only)', act.curve_tension_push),
			),
		)),

		# SECTION 'contour' - Contours (fold target)
		('contour', 'Contours', (
			(
				B('contour_close', 'Close selected contours', act.contour_close),
				B('contour_cw_alt', 'Set clockwise winding direction (TrueType)', partial(act.contour_winding, False)),
				B('contour_ccw_alt', 'Set counterclockwise winding direction (PostScript)', partial(act.contour_winding, True)),
				B('node_start', 'Set start node', act.contour_start),
				B('node_previous', 'Move start to previous node', partial(act.contour_start_next, True)),
				B('node_next', 'Move start to next node', partial(act.contour_start_next, False)),
			),
			(
				B('node_bottom_left', 'Set start node to bottom left', partial(act.contour_smart_start, (0, 0))),
				B('node_bottom_right', 'Set start node to bottom right', partial(act.contour_smart_start, (1, 0))),
				B('node_top_left', 'Set start node to top left', partial(act.contour_smart_start, (0, 1))),
				B('node_top_right', 'Set start node to top right', partial(act.contour_smart_start, (1, 1))),
			),
			(
				B('contour_sort_y', 'Reorder contours from top to bottom', partial(act.contour_order, (None, True), True)),
				B('contour_sort_x', 'Reorder contours from left to right', partial(act.contour_order, (True, None), False)),
				B('contour_sort_y_rev', 'Reorder contours from bottom to top', partial(act.contour_order, (None, True), False)),
				B('contour_sort_x_rev', 'Reorder contours from right to left', partial(act.contour_order, (True, None), True)),
			),
		)),

		# SECTION 'bool' - Booleans (fold target)
		('bool', 'Booleans', (
			(
				B('contour_union', 'Boolean Add selected contours\nAlt: Reverse order', partial(act.contour_bool, 'add')),
				B('contour_subtract', 'Boolean Subtract selected contours\nAlt: Reverse order', partial(act.contour_bool, 'subtract')),
				B('contour_intersect', 'Boolean Intersect selected contours\nAlt: Reverse order', partial(act.contour_bool, 'intersect')),
				B('contour_difference', 'Boolean Exclude selected contours\nAlt: Reverse order', partial(act.contour_bool, 'exclude')),
			),
		)),

		# SECTION 'cut' - Cut (fold target)
		('cut', 'Cut', (
			(
				B('contour_cut', 'Slice selected contours\nAlt: Overlap', act.contour_cut),
				B('cut_stem_overlap', 'Cut contour, then auto overlap align both neighbor pairs\nat the cut junction.\nAlt: Overlap', act.cut_align_auto),
				B('auto_stem_overlap', 'Auto overlap align\nSelect 4 nodes (2 neighbor pairs) at a cut junction.', act.align_auto),
				B('node_middle_top', 'Stem-Center Snap\nSnap selection to the centerline of the perpendicular stem.\nAxis auto from selection bbox.\nShift: force horizontal motion (V-stem).\nAlt: force vertical motion (H-stem).', act.stem_center),
				B('node_target', 'Pick target node for loop extension.\nSelect 1 on-curve node, then toggle on.\nToggle off to clear target.', act.loop_target_toggle, True, name='loop_target'),
				B('corner_loop', 'Corner Loop\nNo target: loop by the corner field size.\nWith target: extend corner toward stored target position.', act.cut_corner_loop, name='cut_corner_loop'),
				Field('fld_loop_safe', '5', 'Safe distance: pull back from target by this amount on each axis.'),
			),
			( # FL only
				B('cutter_auto', 'Stroke Separate (V3)\nSplit stroke glyph into components via MAT analysis.\nApplies to active layer; propagates cuts to all masters. (FL only)', act.stroke_separate),
				B('centerline', 'Medial Axis Extract\nEmit a clean medial-axis skeleton as a new shape on the active layer. (FL only)', act.medial_axis),
			),
		)),

		# SECTION 'cap' - End Caps (fold target)
		('cap', 'End Caps', (
			(
				B('cap_normal', 'Butt cap - perpendicular flat cut between two stem corners', act.cap_normal),
				B('cap_round', 'Round cap - italic-aware circular cap between two stem corners\nAlt: keep overall path length (cap fits inside stems)', act.cap_round),
				B('cap_restore', 'Rebuild cap - flatten any existing cap to a butt cut', act.cap_rebuild),
			),
		)),

		# SECTION 'stroke' - Collinear & Monoline (fold target)
		('stroke', 'Collinear & Monoline', (
			(
				B('curve_collinear', 'Make two selected curve segments collinear\nAlt: also equalize stem width\nCtrl: edit per-master snap targets\nShift: no snap', act.make_collinear),
				B('channel_process', 'Make two selected curve segments monoline (truly parallel offsets of a shared median skeleton)\nAlt: preserve per-end taper instead of uniform width\nCtrl: edit per-master snap targets\nShift: no snap', act.make_monoline),
			),
		)),

		# SECTION 'slope' - Slope (fold target)
		('slope', 'Slope', (
			(
				B('slope_copy', 'Copy slope between selected nodes', act.slope_copy),
				B('slope_italic', "Use the master's italic angle as slope", act.slope_italic),
				B('slope_paste_min', 'Paste slope to selected nodes pivoting around the one with lowest vertical coordinates', partial(act.slope_paste, False, False)),
				B('slope_paste_max', 'Paste slope to selected nodes pivoting around the one with highest vertical coordinates', partial(act.slope_paste, True, False)),
				B('slope_paste_min_flip', 'Paste horizontally flipped slope pivoting around the lowest node', partial(act.slope_paste, False, True)),
				B('slope_paste_max_flip', 'Paste horizontally flipped slope pivoting around the highest node', partial(act.slope_paste, True, True)),
			),
		)),
	)

# - Widgets -------------------------------
def make_button(page, spec, font):
	'''Flat icon-font tool button (looks like a toolbar action)'''
	button = QtGui.QToolButton(page)
	button.setText(spec.token)
	button.setFont(font)
	button.setToolTip(spec.tip or '')
	button.setAutoRaise(True)
	button.setFocusPolicy(QtCore.Qt.NoFocus)
	button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
	button.setCheckable(spec.checkable)
	if spec.checkable and spec.checked: button.setChecked(True)
	if spec.callback is None: button.setEnabled(False)
	else: button.clicked.connect(guarded(spec.callback, spec.name))
	return button

def make_field(page, spec):
	edit = QtGui.QLineEdit(page)
	edit.setText(spec.default)
	edit.setToolTip(spec.tip)
	edit.setFixedWidth(44)
	edit.setAlignment(QtCore.Qt.AlignCenter)
	return edit

class TRToolbarMasthead(object):
	'''Layer scope (Active / Masters / Selected + layer dialog) and glyph scope (active glyph / glyph window /
	font window selection) - the full TypeRig FL controller. Writes into the shared TRToolbarState.'''
	layer_buttons = (('layer_active', 'Active layer', 'active'), ('layer_master', 'Master layers', 'masters'), ('select_option', 'Select layers', 'selected'))
	glyph_buttons = (('glyph_active', 'Active Glyph', 0), ('select_window', 'Glyph window', 1), ('select_glyph', 'Font window selection', 2))

	def __init__(self, state, page, font):
		self.state = state
		self.refs = []
		self.dlg_layer = TRLayerSelectNEW(self, state.mode) # The dialog calls self.layers_refresh() on edits
		self.dlg_layer.hide()
		state.dlg_layer = self.dlg_layer

		self.layers = self.make_group(page, font, self.layer_buttons, state.layer_scope, self.set_layer_scope)
		self.glyphs = self.make_group(page, font, self.glyph_buttons, state.mode, self.set_glyph_mode)

	def make_group(self, page, font, entries, current, handler):
		group = QtGui.QButtonGroup(page)
		group.setExclusive(True)
		buttons = []

		for token, tip, value in entries:
			button = make_button(page, B(token, tip, partial(handler, value), True, checked=(value == current)), font)
			group.addButton(button)
			buttons.append(button)

		self.refs.append(group)
		return buttons

	def set_layer_scope(self, scope):
		self.state.layer_scope = scope

		if scope == 'selected':
			self.dlg_layer.table_populate(self.state.mode)
			self.dlg_layer.show()
		else:
			self.dlg_layer.hide()

	def set_glyph_mode(self, mode):
		self.state.mode = mode
		self.dlg_layer.table_populate(mode)

	def layers_refresh(self):
		'''Called by the layer dialog when a check box changes. The state reads the table live: nothing to do'''
		pass

class TRToolbarBuilder(object):
	'''content_builder for TRNativePanel: masthead + all sections. Returns (page, buttons, refs)'''
	def __init__(self, state=None, actions=None):
		self.state = state or TRToolbarState()
		self.actions = actions or TRToolbarActions(self.state)

	def __call__(self, panel=None):
		page = QtGui.QWidget()
		font = getTRIconFont()
		refs, buttons, groups = [], [], {}
		act = self.actions
		act.widgets.clear()

		def add(widget, group_start, section_start):
			if group_start: widget.setProperty('trGroupStart', True)
			if section_start: widget.setProperty('trSectionStart', True)
			buttons.append(widget)

		# - Masthead (layer scope, glyph scope)
		masthead = TRToolbarMasthead(self.state, page, font)
		refs.append(masthead)
		for group in (masthead.layers, masthead.glyphs):
			for index, widget in enumerate(group): add(widget, index == 0, False)

		# - Sections
		for key, caption, section_groups in toolbar_sections(act):
			for group_index, group in enumerate(section_groups):
				for index, spec in enumerate(group):
					if isinstance(spec, Field):
						widget = make_field(page, spec)
					else:
						widget = make_button(page, spec, font)
						if spec.exclusive:
							if spec.exclusive not in groups:
								groups[spec.exclusive] = QtGui.QButtonGroup(page)
								groups[spec.exclusive].setExclusive(True)
								refs.append(groups[spec.exclusive])
							groups[spec.exclusive].addButton(widget)

					act.widgets[spec.name] = widget
					add(widget, index == 0, group_index == 0 and index == 0)

		refs.append(act)
		return page, buttons, refs
