#FLM: TypeRig: Delta Preview
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026		(http://www.kateliev.com)
# (C) TypeRig					(http://www.typerig.com)
# -----------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Left panel  : Delta axis setup (tree + controls, from TR | Delta)
# Right panel : Two QListViews with a vector delegate — no pixmaps.
#               QSplitter (H) separates panels.
#               QSplitter (V) separates source masters / target results.
#
# Rendering:
#   core_contour.segments -> Line/CubicBezier -> QtGui.QPainterPath
#   GlyphPathDelegate.paint() applies fit + Y-flip QTransform every call.
#   Zoom slider and padding slider update the delegate; views repaint live.
#   Splitter drag repaints automatically at zero cost.
#
#   fl_shape.closedPath is NOT used — it returns an FL-internal C++ object
#   that PythonQt wraps as void* and QPainter.drawPath() rejects it.
#   QPainterPath objects built from core geometry are genuine Qt types.
#
# Delta pipeline (Execute):
#   trGlyph().eject()                              -> core_glyph
#   stamp stems from Virtual Axis onto core layers
#   core_glyph.build_contour_deltas_with_metrics() -> contour_deltas, metric_delta
#   for each Target Layer:
#       stamp target stems, delta_scale_compensated() -> result core Layer
#       _core_layer_to_qpaths()                    -> list[QPainterPath]
#
# Nothing is written to the font.
#
# -----------------------------------------------------------

from __future__ import absolute_import, print_function
import json
import math
import os
import warnings
import random
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.fl.gui.widgets import (
	getTRIconFontPath, CustomPushButton,
	TRFlowLayout, TRDeltaLayerTree
)

from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.base.message import *
from typerig.core.objects.transform import TransformOrigin

# - Init
app_name, app_version = 'TR | Delta Preview', '2.0'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Strings (identical to Delta.py)
app_id_key				= 'com.typerig.delta.machine.axissetup'
tree_column_names		= ('Master Layers', 'V st.', 'H st.', 'Width', 'Height', 'Color')
tree_masters_group_name	= 'Master Layers'
tree_axis_group_name	= 'Virtual Axis'
tree_axis_target_name	= 'Target Layers'
fileFormats				= 'TypeRig Delta Panel Target (*.json);;'

default_sx = '100.'
default_sy = '100.'

# - Cell sizing
_CELL_SIZE_DEFAULT	= 96
_CELL_SIZE_MIN		= 16
_CELL_SIZE_MAX		= 512
_CELL_SIZE_STEP		= 8

_PAD_DEFAULT		= 10		# percent, 0-40
_LABEL_H			= 14		# pixels reserved for name label at bottom
_LABEL_FONT_SIZE	= 8

# Path data is stored in GlyphPathDelegate._path_data, a plain Python dict:
#   { id(QStandardItemModel): [(paths, bbox), ...] }  indexed by row.
# This bypasses QVariant serialization which turns Python objects into void*.

# - Colors
_CLR_BG			= QtGui.QColor(255, 255, 255)
_CLR_FILL		= QtGui.QColor(30,  30,  40)
_CLR_STROKE		= QtGui.QColor(30,  30,  40)
_CLR_EMPTY_BG	= QtGui.QColor(210, 210, 215)
_CLR_LABEL		= QtGui.QColor(40,  40,  40)
_CLR_LABEL_SHD	= QtGui.QColor(255, 255, 255)
_CLR_SEL_BORDER	= QtGui.QColor(80,  120, 200)


# - QPainterPath extraction -------------------------------------
# FL8 API: flContour.path() returns a genuine QtGui.QPainterPath directly.
# Pipeline: fl_layer.shapes -> fl_shape.getContours() -> contour.path()
# No ensurePaths(), no closedPath, no core eject needed for source layers.
# Delta results: _build_fl_shape(core_shape) -> getContours() -> path().

def _fl_contours_to_qpaths(fl_contours):
	'''(list[fl6.flContour], ...) -> (list[QPainterPath], QRectF).
	flContour.path() returns a genuine QtGui.QPainterPath (FL8 API).
	Returns ([], None) on empty input.
	'''
	paths = []
	bbox  = None

	for contour in fl_contours:
		qp = contour.path()

		if qp is None or qp.isEmpty():
			continue

		paths.append(qp)
		r    = qp.boundingRect()
		bbox = r if bbox is None else bbox.united(r)

	return paths, bbox


def _fl_layer_to_qpaths(fl_layer):
	'''Extract QPainterPaths from a live FL proxy layer.
	Returns (list[QPainterPath], QRectF) or ([], None).
	'''
	fl_contours = []

	for fl_shape in fl_layer.shapes:
		fl_contours.extend(fl_shape.getContours())

	return _fl_contours_to_qpaths(fl_contours)


def _core_contour_to_qpath(contour):
	'''Build a QtGui.QPainterPath from a core Contour via its segments.

	This is the fast path for delta results — avoids _build_fl_shape,
	getContours(), and flContour.path() entirely.  Paths built here are
	genuine Python/Qt objects stored directly in the delegate._path_data
	dict, never serialized through QVariant, so no void* corruption.

	Segment types (from typerig.core):
	  Line        — p0 (on), p1 (on)
	  CubicBezier — p0 (on), p1 (bcp-out), p2 (bcp-in), p3 (on)
	'''
	path     = QtGui.QPainterPath()
	segments = contour.segments

	if not segments:
		return path

	path.moveTo(segments[0].p0.x, segments[0].p0.y)

	for seg in segments:
		if hasattr(seg, 'p3'):
			path.cubicTo(seg.p1.x, seg.p1.y,
						 seg.p2.x, seg.p2.y,
						 seg.p3.x, seg.p3.y)
		else:
			path.lineTo(seg.p1.x, seg.p1.y)

	path.closeSubpath()
	return path


def _core_layer_to_qpaths(core_layer):
	'''Convert a core Layer (post-delta) to (list[QPainterPath], QRectF).

	Builds QPainterPaths directly from core contour segments — no FL
	object reconstruction, no PythonQt boundary crossings per node.
	Returns ([], None) if the layer has no drawable geometry.
	'''
	paths = []
	bbox  = None

	for shape in core_layer.shapes:
		for contour in shape.contours:
			qp = _core_contour_to_qpath(contour)

			if qp.isEmpty():
				continue

			paths.append(qp)
			r    = qp.boundingRect()
			bbox = r if bbox is None else bbox.united(r)

	return paths, bbox




# - Model item helpers -------------------------------------------

def _make_error_item(label, message='Error'):
	item = QtGui.QStandardItem('{}\n{}'.format(label, message))
	item.setEditable(False)
	item.setDropEnabled(False)
	return item, [], None


def _make_glyph_item(label, paths, bbox):
	item = QtGui.QStandardItem(label)
	item.setEditable(False)
	item.setDropEnabled(False)
	return item, paths, bbox


# - Vector delegate ----------------------------------------------

class GlyphPathDelegate(QtGui.QStyledItemDelegate):
	'''Renders QtGui.QPainterPath lists stored on model items.

	Paths are built once from core contour geometry (plain floats, no FL
	types) and stored on each item. paint() computes a fresh fit + Y-flip
	QTransform every call — zoom, padding, splitter drag are all free.
	'''

	def __init__(self, parent=None):
		QtGui.QStyledItemDelegate.__init__(self, parent)
		self.cell_size    = _CELL_SIZE_DEFAULT
		self.padding_frac = _PAD_DEFAULT / 100.0
		# Keyed by id(QStandardItemModel) -> list of (paths, bbox) per row.
		# Python dict — avoids QVariant serialization that corrupts Qt objects.
		self._path_data   = {}
		# Shared reference bbox — union of all item bboxes in the current model.
		# All cells scale to this so relative glyph sizes are preserved.
		self._ref_bbox    = None

	def sizeHint(self, option, index):
		s = self.cell_size
		return QtCore.QSize(s, s + _LABEL_H)

	def paint(self, painter, option, index):
		rect  = option.rect
		label = index.data(QtCore.Qt.DisplayRole) or ''
		row   = index.row()
		data  = self._path_data.get(id(index.model()), [])
		paths, bbox = data[row] if row < len(data) else ([], None)

		cell_w = rect.width()
		cell_h = rect.height()

		# -- Background
		if option.state & QtGui.QStyle.State_Selected:
			painter.fillRect(rect, option.palette.highlight())
		else:
			painter.fillRect(rect, _CLR_BG)

		# -- Glyph area (everything above label strip)
		glyph_h = cell_h - _LABEL_H

		ref  = self._ref_bbox if self._ref_bbox is not None else bbox
		if paths and bbox is not None and bbox.width() > 0 and bbox.height() > 0 \
				and ref is not None and ref.width() > 0 and ref.height() > 0:
			pad     = max(1.0, cell_w * self.padding_frac)
			avail_w = cell_w  - 2.0 * pad
			avail_h = glyph_h - 2.0 * pad

			# Scale from shared ref bbox — preserves relative glyph sizes
			scale = min(avail_w / ref.width(), avail_h / ref.height())

			# Center from item's own bbox — each glyph sits in its own position
			bcx = bbox.x() + bbox.width()  / 2.0
			bcy = bbox.y() + bbox.height() / 2.0

			scx = rect.x() + cell_w  / 2.0
			scy = rect.y() + glyph_h / 2.0

			# screen_xy = font_xy * scale + (tx, ty)  with Y negated
			tx = scx - bcx *  scale
			ty = scy + bcy *  scale		# + because scale is negated

			t = QtGui.QTransform()
			t.translate(tx, ty)
			t.scale(scale, -scale)		# Y-flip: font-up -> screen-down

			painter.save()
			painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
			painter.setTransform(t)
			painter.setBrush(QtGui.QBrush(_CLR_FILL))
			painter.setPen(QtGui.QPen(_CLR_STROKE, max(0.2, 0.5 / scale)))

			for path in paths:
				painter.drawPath(path)

			painter.restore()

		else:
			# Empty / error cell
			painter.fillRect(
				QtCore.QRect(rect.x(), rect.y(), cell_w, glyph_h),
				_CLR_EMPTY_BG
			)
			painter.setPen(_CLR_LABEL)
			painter.setFont(QtGui.QFont('Arial', 8))
			painter.drawText(
				QtCore.QRect(rect.x(), rect.y(), cell_w, glyph_h),
				QtCore.Qt.AlignCenter, label
			)

		# -- Label strip at bottom
		lbl_rect = QtCore.QRect(rect.x(), rect.y() + glyph_h, cell_w, _LABEL_H)
		painter.fillRect(lbl_rect, QtGui.QColor(240, 240, 245))

		painter.setFont(QtGui.QFont('Arial', _LABEL_FONT_SIZE))
		painter.setPen(_CLR_LABEL_SHD)
		painter.drawText(lbl_rect.adjusted(5, 0, 0, 0), QtCore.Qt.AlignVCenter, label)
		painter.setPen(_CLR_LABEL)
		painter.drawText(lbl_rect.adjusted(4, -1, 0, 0), QtCore.Qt.AlignVCenter, label)

		# Selection border
		if option.state & QtGui.QStyle.State_Selected:
			painter.setPen(QtGui.QPen(_CLR_SEL_BORDER, 2))
			painter.drawRect(rect.adjusted(1, 1, -1, -1))


# - List view setup ----------------------------------------------

def _setup_list_view(view, delegate):
	view.setItemDelegate(delegate)
	view.setViewMode(QtGui.QListView.IconMode)
	view.setResizeMode(QtGui.QListView.Adjust)
	view.setMovement(QtGui.QListView.Snap)
	view.setWrapping(True)
	view.setUniformItemSizes(True)
	view.setWordWrap(False)

	view.setDragEnabled(True)
	view.setAcceptDrops(True)
	view.setDropIndicatorShown(True)
	view.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
	view.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
	view.setDefaultDropAction(QtCore.Qt.MoveAction)


# - Main dialog --------------------------------------------------

class VariationsPreview(QtGui.QDialog):
	def __init__(self):
		super(VariationsPreview, self).__init__()

		self.active_font  = pFont()
		self.active_glyph = eGlyph()

		self.masters_data = OrderedDict()
		self.axis_data    = []
		self.axis_stems   = []

		# Cache: built by __set_axis(), reused by execute_target().
		# Cleared when glyph changes (refresh) or axis is reset.
		self._delta_cache = None

		self._delegate = GlyphPathDelegate()

		self._build_ui()
		self.refresh()

	# - UI -------------------------------------------------------

	def _build_ui(self):
		self.setWindowTitle('{} {}'.format(app_name, app_version))
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

		set_ss = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_ss)

		self._splitter_h = QtGui.QSplitter(QtCore.Qt.Horizontal)

		# ---- Left panel ----------------------------------------
		left = QtGui.QWidget()
		left.setMinimumWidth(200)
		lay_left = QtGui.QVBoxLayout(left)
		lay_left.setContentsMargins(2, 2, 2, 2)
		lay_left.setSpacing(4)

		# Tree
		self.tree_layer = TRDeltaLayerTree()
		act_reset = QtGui.QAction('Clear all', self)
		act_vstem = QtGui.QAction('Get Vertical Stems', self)
		act_hstem = QtGui.QAction('Get Horizontal Stems', self)
		self.tree_layer.menu.addSeparator()
		self.tree_layer.menu.addAction(act_vstem)
		self.tree_layer.menu.addAction(act_hstem)
		self.tree_layer.menu.addSeparator()
		self.tree_layer.menu.addAction(act_reset)
		act_reset.triggered.connect(lambda: self.__reset_all())
		act_vstem.triggered.connect(lambda: self.get_stem(False))
		act_hstem.triggered.connect(lambda: self.get_stem(True))
		self.tree_layer.setTree(self.__init_tree(), tree_column_names)
		lay_left.addWidget(self.tree_layer)

		# Actions group
		box_actions = QtGui.QGroupBox()
		box_actions.setObjectName('box_group')
		lay_actions = TRFlowLayout(spacing=10)

		self.btn_execute = CustomPushButton('action_play', tooltip='Execute delta to Target Layers', enabled=False, obj_name='btn_panel')
		self.btn_execute.clicked.connect(lambda: self.execute_target())
		lay_actions.addWidget(self.btn_execute)

		for icon, tip, slot in [
			('stem_vertical_alt',	'Get vertical stems',				lambda: self.get_stem(False)),
			('stem_horizontal_alt',	'Get horizontal stems',				lambda: self.get_stem(True)),
			('axis_set',			'Set axis',							lambda: self.__set_axis(True)),
			('axis_remove',			'Reset axis',						lambda: self.__reset_axis(True)),
			('refresh',				'Reset all data',					lambda: self.__reset_all(True)),
			('file_save',			'Save axis data to external file',	lambda: self.file_save_axis_data()),
			('file_open',			'Load axis data from external file',lambda: self.file_open_axis_data()),
			('font_save',			'Save axis data to font file',		lambda: self.font_save_axis_data()),
			('font_open',			'Load axis data from font file',	lambda: self.font_open_axis_data()),
		]:
			btn = CustomPushButton(icon, tooltip=tip, obj_name='btn_panel')
			btn.clicked.connect(slot)
			lay_actions.addWidget(btn)

		box_actions.setLayout(lay_actions)
		lay_left.addWidget(box_actions)

		# Options group
		box_options = QtGui.QGroupBox()
		box_options.setObjectName('box_group')
		lay_options = TRFlowLayout(spacing=10)

		self.chk_metrics     = CustomPushButton('metrics_advance_alt', checkable=True, checked=True, tooltip='Process metrics',     obj_name='btn_panel_opt')
		self.chk_anchors     = CustomPushButton('icon_anchor',         checkable=True, checked=True, tooltip='Process anchors',     obj_name='btn_panel_opt')
		self.chk_extrapolate = CustomPushButton('extrapolate',         checkable=True, checked=True, tooltip='Allow extrapolation', obj_name='btn_panel_opt')

		for w in (self.chk_metrics, self.chk_anchors, self.chk_extrapolate):
			lay_options.addWidget(w)

		box_options.setLayout(lay_options)
		lay_left.addWidget(box_options)

		# Transform origin group
		box_transform = QtGui.QGroupBox()
		box_transform.setObjectName('box_group')
		lay_transform = TRFlowLayout(spacing=10)

		self.grp_transform = QtGui.QButtonGroup()
		self.grp_transform.setExclusive(True)

		for icon_name, tip, btn_id, checked in [
			('node_align_bottom_left', 'Transform at Origin',       1, True),
			('node_bottom_left',       'Transform at Bottom Left',  2, False),
			('node_bottom_right',      'Transform at Bottom Right', 4, False),
			('node_center',            'Transform at Center',       6, False),
			('node_top_left',          'Transform at Top Left',     3, False),
			('node_top_right',         'Transform at Top Right',    5, False),
		]:
			btn = CustomPushButton(icon_name, checkable=True, checked=checked, tooltip=tip, obj_name='btn_panel_opt')
			self.grp_transform.addButton(btn, btn_id)
			lay_transform.addWidget(btn)

		box_transform.setLayout(lay_transform)
		lay_left.addWidget(box_transform)

		# Status bar: label icon | glyph name | search icon | zoom spin |
		#             view_icons | pad spin | refresh
		lay_status = QtGui.QHBoxLayout()
		lay_status.setSpacing(4)
		lay_status.setContentsMargins(0, 0, 0, 0)

		# "label" icon + glyph name
		icn_label = CustomPushButton('label', tooltip='Current glyph', enabled=False, obj_name='btn_panel')
		self.lbl_glyph = QtGui.QLabel('No glyph')

		# "search" icon + zoom spinbox
		icn_zoom = CustomPushButton('search', tooltip='Cell size (px)', enabled=False, obj_name='btn_panel')
		self.spn_zoom = QtGui.QSpinBox()
		self.spn_zoom.setRange(_CELL_SIZE_MIN, _CELL_SIZE_MAX)
		self.spn_zoom.setSingleStep(_CELL_SIZE_STEP)
		self.spn_zoom.setValue(_CELL_SIZE_DEFAULT)
		self.spn_zoom.setSuffix(' px')
		self.spn_zoom.setFixedWidth(68)
		self.spn_zoom.valueChanged.connect(self.__on_zoom_spin)

		# "view_icons" icon + padding spinbox
		icn_pad = CustomPushButton('view_icons', tooltip='Padding (%)', enabled=False, obj_name='btn_panel')
		self.spn_pad = QtGui.QSpinBox()
		self.spn_pad.setRange(0, 40)
		self.spn_pad.setSingleStep(1)
		self.spn_pad.setValue(_PAD_DEFAULT)
		self.spn_pad.setSuffix(' %')
		self.spn_pad.setFixedWidth(52)
		self.spn_pad.valueChanged.connect(self.__on_pad_spin)

		# Refresh
		self.btn_refresh = CustomPushButton('refresh', tooltip='Refresh current glyph', obj_name='btn_panel')
		self.btn_refresh.clicked.connect(lambda: self.refresh())

		lay_status.addWidget(icn_label)
		lay_status.addWidget(self.lbl_glyph, 1)
		lay_status.addWidget(icn_zoom)
		lay_status.addWidget(self.spn_zoom)
		lay_status.addWidget(icn_pad)
		lay_status.addWidget(self.spn_pad)
		lay_status.addWidget(self.btn_refresh)

		lay_left.addLayout(lay_status)

		# ---- Right panel — single wrapping list for all layers
		self.mod_glyphs = QtGui.QStandardItemModel()
		self.lst_glyphs = QtGui.QListView()
		self.lst_glyphs.setModel(self.mod_glyphs)
		_setup_list_view(self.lst_glyphs, self._delegate)
		self.lst_glyphs.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.lst_glyphs.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

		self._splitter_h.addWidget(left)
		self._splitter_h.addWidget(self.lst_glyphs)
		self._splitter_h.setStretchFactor(0, 0)
		self._splitter_h.setStretchFactor(1, 1)
		self._splitter_h.setSizes([320, 700])

		lay_root = QtGui.QVBoxLayout()
		lay_root.setContentsMargins(4, 4, 4, 4)
		lay_root.addWidget(self._splitter_h)
		self.setLayout(lay_root)

		self._apply_cell_size(_CELL_SIZE_DEFAULT)
		self.show()

	# - Zoom / padding -------------------------------------------

	def __on_zoom_spin(self, value):
		self._apply_cell_size(value)

	def __on_pad_spin(self, value):
		self._delegate.padding_frac = value / 100.0
		self.lst_glyphs.viewport().update()

	def _apply_cell_size(self, size):
		self._delegate.cell_size = size

		spacing = max(2, size // 20)
		grid_sz = QtCore.QSize(size + spacing * 2, size + _LABEL_H + spacing * 2)

		self.lst_glyphs.setGridSize(grid_sz)
		self.lst_glyphs.setSpacing(spacing)
		self.lst_glyphs.doItemsLayout()

	# - Model population -----------------------------------------

	def _fill_model(self, model, items, append=False):
		'''items: list of (QStandardItem, paths, bbox) tuples.
		Paths/bbox stored in delegate._path_data keyed by id(model),
		avoiding QVariant serialization that corrupts Python Qt objects.
		append=True adds to existing rows rather than clearing first.
		'''
		if not append:
			model.clear()
			path_list = []
		else:
			path_list = self._delegate._path_data.get(id(model), [])

		for item, paths, bbox in items:
			model.appendRow(item)
			path_list.append((paths, bbox))

		self._delegate._path_data[id(model)] = path_list

		# Recompute shared ref bbox from all entries in this model.
		# Skips error items (bbox is None) — they render as grey cells.
		ref = None
		for _, bbox in path_list:
			if bbox is not None and bbox.width() > 0 and bbox.height() > 0:
				ref = bbox if ref is None else ref.united(bbox)
		self._delegate._ref_bbox = ref

	# - Show axis masters ----------------------------------------

	def _show_axis_masters(self):
		self.__refresh_options()

		masters_data = self.tree_layer.getTree()
		axis_entries = masters_data.get(tree_axis_group_name, [])

		if not axis_entries:
			axis_entries = masters_data.get(tree_masters_group_name, [])

		try:
			glyph = eGlyph()
			self.lbl_glyph.setText(glyph.name)
			items = []

			for entry in axis_entries:
				layer_name = entry[0]
				fl_layer   = glyph.layer(layer_name)

				if fl_layer is None:
					items.append(_make_error_item(layer_name, 'Not found'))
					continue

				paths, bbox = _fl_layer_to_qpaths(fl_layer)

				if not paths:
					items.append(_make_error_item(layer_name, 'Empty'))
					continue

				items.append(_make_glyph_item(layer_name, paths, bbox))

			self._fill_model(self.mod_glyphs, items)

		except Exception as e:
			print('{}: _show_axis_masters error - {}'.format(app_name, e))


	# - Execute --------------------------------------------------

	def execute_target(self):
		self.__refresh_options()

		self.masters_data = self.tree_layer.getTree()
		axis_entries   = self.masters_data.get(tree_axis_group_name, [])
		target_entries = self.masters_data.get(tree_axis_target_name, [])

		if len(axis_entries) < 2:
			warnings.warn('Need at least 2 Virtual Axis layers.', UserWarning)
			return

		if not target_entries:
			warnings.warn('No Target Layers defined.', UserWarning)
			return

		self._show_axis_masters()

		# Rebuild cache if missing (e.g. glyph refreshed after set_axis)
		if self._delta_cache is None:
			self._build_delta_cache()

		if self._delta_cache is None:
			warnings.warn('Cache build failed — cannot execute.', UserWarning)
			return

		try:
			core_glyph     = self._delta_cache['core_glyph']
			axis_names     = self._delta_cache['axis_names']
			contour_deltas = self._delta_cache['contour_deltas']
			metric_delta   = self._delta_cache['metric_delta']
			source_name    = self._delta_cache['source_name']
			it             = math.radians(-float(self.active_font.italic_angle))

			items = []


			for entry in target_entries:
				target_name = entry[0]

				try:
					target_stx = float(entry[1])
					target_sty = float(entry[2])
					sx         = float(entry[3]) / 100.
					sy         = float(entry[4]) / 100.
				except (ValueError, IndexError):
					items.append(_make_error_item(target_name, 'Bad data'))
					continue

				try:
					source_layer = core_glyph.layer(source_name)

					if source_layer is None:
						items.append(_make_error_item(target_name, 'No source'))
						continue

					source_layer.stems = (target_stx, target_sty)

					result_layer = source_layer.delta_scale_compensated(
						contour_deltas,
						scale            = (sx, sy),
						intensity        = 0.0,
						compensation     = (0., 0.),
						shift            = (0., 0.),
						italic_angle     = it,
						extrapolate      = self.opt_extrapolate,
						metric_delta     = metric_delta,
						transform_origin = self.transform_origin
					)

					paths, bbox = _core_layer_to_qpaths(result_layer)

					if not paths:
						items.append(_make_error_item(target_name, 'Empty result'))
						continue

					items.append(_make_glyph_item(target_name, paths, bbox))

				except Exception as e:
					items.append(_make_error_item(target_name, 'Error'))
					print('{}: target "{}" - {}'.format(app_name, target_name, e))

			self._fill_model(self.mod_glyphs, items, append=True)

		except Exception as e:
			print('{}: execute_target error - {}'.format(app_name, e))

	# - Internal: Delta panel helpers ----------------------------

	def __init_tree(self):
		masters_data = []
		active_glyph = eGlyph()

		for layer_name in self.active_font.masters():
			temp_layer = active_glyph.layer(layer_name)
			deco_color = temp_layer.wireframeColor if temp_layer is not None \
						 else QtGui.QColor(random.randint(0,255), random.randint(0,255), random.randint(0,255))
			masters_data.append((layer_name, '', '', default_sx, default_sy, deco_color))

		return OrderedDict([
			(tree_masters_group_name, masters_data),
			(tree_axis_group_name,    []),
			(tree_axis_target_name,   []),
		])

	# - Delta cache --------------------------------------------

	def _build_delta_cache(self):
		'''Eject current glyph to core, stamp Virtual Axis stems, compute
		contour deltas and metric delta. Stores everything in self._delta_cache.
		Called by __set_axis() and lazily by execute_target() if cache is None.
		'''
		self._delta_cache = None

		try:
			masters_data = self.tree_layer.getTree()
			axis_entries = masters_data.get(tree_axis_group_name, [])

			if len(axis_entries) < 2:
				return

			core_glyph = trGlyph().eject()
			axis_names = []

			for entry in axis_entries:
				layer_name = entry[0]

				try:
					stx = float(entry[1])
					sty = float(entry[2])
				except (ValueError, IndexError):
					warnings.warn('Invalid stems for "{}".'.format(layer_name), UserWarning)
					return

				layer = core_glyph.layer(layer_name)

				if layer is None:
					warnings.warn('Axis layer "{}" not found.'.format(layer_name), UserWarning)
					return

				layer.stems = (stx, sty)
				axis_names.append(layer_name)

			contour_deltas, metric_delta = \
				core_glyph.build_contour_deltas_with_metrics(axis_names)

			self._delta_cache = {
				'core_glyph'     : core_glyph,
				'axis_names'     : axis_names,
				'source_name'    : axis_names[0],
				'contour_deltas' : contour_deltas,
				'metric_delta'   : metric_delta,
			}

		except Exception as e:
			print('{}: _build_delta_cache error - {}'.format(app_name, e))
			self._delta_cache = None

	# - Internal: Delta panel helpers ----------------------------

	def __set_axis(self, verbose=False):
		self.masters_data = self.tree_layer.getTree()
		self.axis_data    = self.masters_data[tree_axis_group_name]
		self.axis_stems   = []

		if not len(self.axis_data):
			warnings.warn('Axis not set! Please add two or more layers.', UserWarning)
			return

		for layer_data in self.axis_data:
			try:
				x_stem, y_stem = float(layer_data[1]), float(layer_data[2])
				self.axis_stems.append([(x_stem, y_stem)])
			except ValueError:
				warnings.warn('Missing or invalid stem data!', UserWarning)
				return

		# Build delta cache now — eject + stamp stems + build deltas.
		# execute_target() reuses this; only rebuilt when axis changes.
		self._build_delta_cache()

		self.btn_execute.setEnabled(True)
		self._show_axis_masters()

		if verbose:
			output(0, app_name, 'Font: {}; Axis set.'.format(self.active_font.name))

	def __reset_axis(self, verbose=False):
		self.axis_data    = []
		self.axis_stems   = []
		self._delta_cache = None
		self.btn_execute.setEnabled(False)

		if verbose:
			output(0, app_name, 'Font: {}; Axis cleared.'.format(self.active_font.name))

	def __reset_all(self, verbose=False):
		self.tree_layer.setTree(self.__init_tree(), tree_column_names)
		self.__reset_axis()
		self._show_axis_masters()

		if verbose:
			output(0, app_name, 'Reset.')

	def __refresh_options(self):
		self.opt_extrapolate = self.chk_extrapolate.isChecked()
		self.opt_metrics     = self.chk_metrics.isChecked()
		self.opt_anchors     = self.chk_anchors.isChecked()

		btn_id = self.grp_transform.checkedId()
		self.transform_origin = {
			2: TransformOrigin.BOTTOM_LEFT,
			4: TransformOrigin.BOTTOM_RIGHT,
			3: TransformOrigin.TOP_LEFT,
			5: TransformOrigin.TOP_RIGHT,
			6: TransformOrigin.CENTER,
		}.get(btn_id, TransformOrigin.BASELINE)

	def contextMenuEvent(self, event):
		self.tree_layer.menu.popup(QtGui.QCursor.pos())

	def get_stem(self, get_y=False):
		self.masters_data = self.tree_layer.getTree()
		self.active_glyph = eGlyph()

		for group, data in self.masters_data.items():
			for layer_data in data:
				try:
					selection = self.active_glyph.selectedNodes(layer_data[0], True)

					if get_y:
						layer_data[2] = round(abs(selection[0].y - selection[-1].y), 2)
					else:
						layer_data[1] = round(abs(selection[0].x - selection[-1].x), 2)

				except (AttributeError, IndexError):
					warnings.warn('Missing or incompatible layer: {}!'.format(layer_data[0]), UserWarning)

		self.tree_layer.setTree(OrderedDict(self.masters_data), tree_column_names)

	# - Font / file IO -------------------------------------------

	def font_save_axis_data(self):
		temp_lib = self.active_font.fl.packageLib
		temp_lib[app_id_key] = self.tree_layer.getTree()
		self.active_font.fl.packageLib = temp_lib
		output(7, app_name, 'Font: {}; Axis saved to Font Lib.'.format(self.active_font.name))

	def font_open_axis_data(self):
		temp_lib          = self.active_font.fl.packageLib
		self.masters_data = temp_lib[app_id_key]
		self.tree_layer.setTree(self.masters_data, tree_column_names)
		output(6, app_name, 'Font: {}; Axis loaded from Font Lib.'.format(self.active_font.name))

	def file_save_axis_data(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save axis data to file', fontPath, fileFormats)

		if fname is not None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tree_layer.getTree(), exportFile)
			output(7, app_name, 'Font: {}; Axis saved to: {}.'.format(self.active_font.name, fname))

	def file_open_axis_data(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load axis data from file', fontPath, fileFormats)

		if fname is not None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
			self.masters_data = imported_data
			self.tree_layer.setTree(self.masters_data, tree_column_names)
			output(6, app_name, 'Font: {}; Axis loaded from: {}.'.format(self.active_font.name, fname))

	# - Public ---------------------------------------------------

	def refresh(self):
		self.active_glyph = eGlyph()
		self._delta_cache = None		# glyph changed — stale cache
		self._show_axis_masters()


# - Run ----------------------------------------------------------

dialog = VariationsPreview()
