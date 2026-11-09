#FLM: TR: Stem Snap
# SPDX-License-Identifier: AGPL-3.0-only
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 	(http://www.kateliev.com)
# (C) TypeRig 					(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Stem Snap: find stems or strokes whose width is close to one of
# the font's standard stems and snap them onto it. Stems outside
# every capture band are left alone. All geometry runs in TypeRig
# core (typerig.core.algo.stem_snap / stroke_snap); this module is
# the FontLab shell. Port of the TypeRig-Glyphs panel (v0.1), which
# replaced the BlackOps dev/Stemsnap test dialogs.
#
# Three methods:
#   Uncommon stems - makes the stems of an element equal among themselves
#             (dominant width, else the median), V and H apart, and lands
#             them on the targets (a standard stem within Tolerance). With
#             none in reach they land on a width of the group, never on a
#             value in between. Stems further apart than the Step stay
#             separate groups, so a deliberately lighter inner stem keeps
#             its weight. Same options and cascade as Stems. Core:
#             equalize_stems().
#   Stems   - node-level H/V stems (extrema or coincident faces). Exact:
#             the faces land on the target. Corrections cascade IUP-style
#             over the stem's contour family, so nothing tears.
#   Strokes - one closed contour = one stroke (CJK stroke builds), width
#             from the medial axis, any angle; fixed by a symmetric
#             offset. Optional MAT stroke separation first (replaces the
#             layer's contour elements with one element of strokes).
#
# Targets: each layer's master PostScript stems (Font Info > Hinting),
# or typed lists for an axis the master has none for; tolerance in
# units or percent of the target. Layers follow the masthead (active /
# masters / selected); the active layer comes first and holds the
# selection for "Selected stems".
#
# Only plain elements are read and written: groups, components and
# shared (referenced) elements are skipped and reported. A layer with
# a transformed element is skipped with a warning: its contours are in
# element space, so stems across elements would be measured wrong.
# Apply the transforms first (Elements New > Apply TX).
#
# Show on canvas: TRStemSnapCanvas draws the analysis of the active layer
# on the glyph itself (like Delta's Live Edit): stems / strokes to snap in
# red with "measured -> target", optionally the ones on target (green)
# and outside every band (grey). It follows the panel options, the glyph
# and layer, outside edits (re-analysed once the edit settles) and the
# selection when "Selected stems / contours" is on. Icons: close,
# re-analyse, show all, select, snap.
#
# NOTE: single glyph mode. The panel works on the current glyph only,
# whatever the masthead glyph mode (window / selection). Multi-glyph
# processing is planned for a later update.

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import math
import time
import traceback

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import ps_master_stems
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.fl.gui import canvas_overlay as co
from typerig.proxy.fl.gui import overlay_math as om
from typerig.proxy.fl.gui.canvas_controls import CanvasIconStrip
from typerig.proxy.tr.objects.contour import trContour, _build_fl_contour
from typerig.proxy.tr.objects.shape import _build_fl_shape

from typerig.core.objects.shape import Shape
from typerig.core.algo._width_audit import WidthTarget, WidthAllowlist
from typerig.core.algo.stem_snap import (snap_stems, equalize_stems, family_selection, StemDetector,
										 Axis, DetectMode, Topology, Cascade, DEFAULT_EQUALIZE_STEP)
from typerig.core.algo.stroke_snap import snap_strokes, StrokeType

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, False, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Stem Snap', '0.3'

DEFAULT_TOL = 5.		# capture band, units (or %)
DIAGONAL_TYPES = (StrokeType.PIE, StrokeType.NA, StrokeType.DIAGONAL, StrokeType.DOT)

# Popups: (key, label, [(title, value), ...], default index, tooltip)
METHODS = [
	('Stems: H/V nodes (exact)',     'stems'),
	('Strokes: contour width (MAT)', 'strokes'),
	('Uncommon stems: equalize',     'uncommon'),
]

UNCOMMON_POPUPS = (
	('scope', 'Work on:', [('Selected contours', 'selected'), ('Each element apart', 'element'), ('Whole layer', 'layer')], 0,
	 'Which stems are compared with each other.\nSelected contours: contours with a selected node, plus their outer / counters.\n'
	 'Each element apart: one common width per element.\nWhole layer: all stems together.'),
)

STEM_POPUPS = (
	('axis', 'Axis:', [('Vertical + horizontal', None), ('Vertical stems', Axis.V), ('Horizontal stems', Axis.H)], 0,
	 'Which stems to snap. Vertical stems are measured along x (hinting "V stems").'),
	('anchor', 'Anchor:', [('Center', 'center'), ('Left / bottom face', 'lower'), ('Right / top face', 'upper')], 0,
	 'The point of the stem that stays put.\nCenter: both faces move by half the correction.'),
	('cascade', 'Cascade:', [('Contour family', Cascade.FAMILY), ('Stem contours', Cascade.STEM), ('Whole layer', Cascade.LAYER)], 0,
	 'Which contours follow the correction (IUP: beyond a face they move with it,\nbetween the faces they are interpolated).\n'
	 'Contour family: outer + counters, so an "o" keeps both walls.\nStem contours: only the contour(s) with the faces.\n'
	 'Whole layer: every contour (keeps spacing of separate strokes).'),
	('detect', 'Detect:', [('Extrema / line faces', DetectMode.EXTREMA), ('Coincident nodes', DetectMode.COINCIDENT)], 0,
	 'Extrema: straight H/V faces and curve extrema (needs nodes at extrema).\nCoincident: on-curves sharing an x or y, no tangent test.'),
)

STEM_CHECKS = (
	('strict',   'Strict topology', True,  'Only pair faces of one contour or of an outer and its counter.\nUnchecked: gaps between separate contours count as stems too.'),
	('italic',   'Italic angle',    True,  'Deslant by the layer master\'s italic angle before measuring:\nslanted stems are measured and moved horizontally.'),
	('selected', 'Selected stems',  False, 'Only stems with a selected face node on the active layer\n(other layers: the same node indices).'),
	('round',    'Round',           True,  'Round moved nodes to integers.'),
	('pin',      'Keep extremes',   True,  'Glyph extremes that are not stem faces stay put (baseline, cap height,\n'
	                                       'the side beyond the last stem): the counters absorb the change.\n'
	                                       'Unchecked: parts beyond a stem move with it.'),
	('aligned',  'Keep aligned',    True,  'Center anchor only: a stem face level with another part stays put and the\n'
	                                       'other face takes the whole correction, so aligned strokes do not drift apart.'),
)

STROKE_POPUPS = (
	('match', 'Match on:', [('Median width', 'median'), ('Min. width', 'min'), ('Max. width', 'max')], 0,
	 'Which width of the stroke is compared with the targets.\nMedian: forgiving on tapers. Min: catches thin tapers. Max: catches swellings.'),
	('quality', 'Quality:', [('Normal', 'normal'), ('Draft (fast)', 'draft'), ('Fine (slow)', 'fine')], 0,
	 'Medial-axis sampling quality.'),
)

STROKE_CHECKS = (
	('s_selected', 'Selected contours', False, 'Only contours with a selected node on the active layer.'),
	('s_round',    'Round',             True,  'Round snapped strokes to integers.'),
	('separate',   'Separate strokes',  False, 'Split the outline into strokes first (medial axis).\n'
	                                          'Experimental: replaces the layer\'s contour elements with one element of\n'
	                                          'overlapping strokes; the masters can become incompatible.'),
)

TARGET_FIELDS = (
	('v_stems', 'V stems:', 'Vertical stem targets (x widths), comma separated. Used when\n"Master stems" is off or the master has no vertical stems.'),
	('h_stems', 'H stems:', 'Horizontal stem targets (y widths), comma separated. Used when\n"Master stems" is off or the master has no horizontal stems.'),
)

# - Helpers ----------------------------
def _fmt(value):
	return '{:g}'.format(round(value, 2))

def _parse_list(text):
	'''"80, 88 92" -> [80.0, 88.0, 92.0]; junk is dropped.'''
	out = []
	for token in str(text or '').replace(';', ',').replace(',', ' ').split():
		try:
			value = float(token)
		except ValueError:
			continue
		if value > 0:
			out.append(value)
	return out

def _aligned_note(report):
	'''Report suffix: how many moved stems the "Keep aligned" option affected.'''
	meta = report.plan.meta
	kept, both = len(meta.get('aligned_kept', ())), len(meta.get('aligned_both', ()))
	parts = []
	if kept: parts.append('{} kept an aligned face'.format(kept))
	if both: parts.append('{} centred, both faces aligned'.format(both))
	return '; ' + ', '.join(parts) if parts else ''

def text_button(caption, tooltip, action):
	button = QtGui.QPushButton(caption)
	button.setToolTip(tooltip)
	button.clicked.connect(action)
	return button

def _kind(shape):
	'''Why the contours of this element are not processed, or None.'''
	if len(shape.includesList): return 'group'
	if shape.isComponent or shape.shapeData.isComponent: return 'component'
	if shape.shapeData.referenceCount > 1: return 'shared'
	return None

def _transformed(shape, eps=1e-9):
	t = shape.transform
	return any(abs(a - b) > eps for a, b in zip((t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()), (1., 0., 0., 1., 0., 0.)))

def _italic_angle(package, layer):
	'''Italic angle (degrees, + leans right, as core stem_snap expects) of
	the master a layer belongs to; the current master for layers that are
	not masters. FontLab stores a right lean as a negative angle (as Delta
	does, the sign is flipped). The current master is restored.'''
	back_master = package.master

	if layer != back_master and layer in list(package.masters):
		package.setMaster(layer)

	try:
		return -float(package.italicAngle_value or 0.)
	finally:
		if package.master != back_master: package.setMaster(back_master)

class _LayerItem(object):
	'''One layer: its plain elements, their FL contours (flat, in element
	order) and core contours ejected from them in the same order.'''
	def __init__(self, name, fl_layer, shapes):
		self.name = name
		self.fl_layer = fl_layer
		self.shapes = shapes
		self.fl_contours = [contour for shape in shapes for contour in shape.contours]
		self.contours = [trContour(contour).eject() for contour in self.fl_contours]

# - Panel ------------------------------
class TRStemSnapPanel(QtGui.QWidget):
	def __init__(self):
		super(TRStemSnapPanel, self).__init__()

		# - Init
		self.fields = {}		# key -> QLineEdit
		self.checks = {}		# key -> (QCheckBox, default)
		self.popups = {}		# key -> (QComboBox, [(title, value)], default)

		# - Canvas (Show on canvas)
		self.live_tool = None	# TRStemSnapCanvas while it is on
		self._live_key = None	# key of the cached analysis
		self._live_st = None	# cached live_state() result
		self._live_rev = 0		# bumped by live_invalidate()

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		self.__build_targets()
		self.__build_method()
		self.__build_uncommon()
		self.__build_actions()

		self.txt_report = QtGui.QTextEdit()
		self.txt_report.setReadOnly(True)
		self.txt_report.setMaximumHeight(140)
		self.txt_report.setToolTip('Last result. Per-stem details: Output panel.')
		self.lay_main.addWidget(self.txt_report)

		self.lay_main.addStretch()
		self.setLayout(self.lay_main)
		self.on_method()

	# - Build -------------------------------------------
	def __check(self, key, title, value, tooltip):
		chk = QtGui.QCheckBox(title)
		chk.setChecked(value)
		chk.setToolTip(tooltip)
		self.checks[key] = (chk, value)
		return chk

	def __field(self, key, tooltip):
		edt = QtGui.QLineEdit()
		edt.setToolTip(tooltip)
		self.fields[key] = edt
		return edt

	def __popup_rows(self, lay, row, rows):
		for key, label, items, default, tooltip in rows:
			cmb = QtGui.QComboBox()
			cmb.addItems([title for title, _ in items])
			cmb.setCurrentIndex(default)
			cmb.setToolTip(tooltip)
			self.popups[key] = (cmb, items, default)

			lay.addWidget(QtGui.QLabel(label), row, 0, 1, 2)
			lay.addWidget(cmb, row, 2, 1, 4)
			row += 1
		return row

	def __check_grid(self, lay, row, rows):
		for i, (key, title, value, tooltip) in enumerate(rows):
			lay.addWidget(self.__check(key, title, value, tooltip), row + i // 2, (i % 2) * 3, 1, 3)
		return row + (len(rows) + 1) // 2

	def __build_targets(self):
		box = QtGui.QGroupBox()
		box.setObjectName('box_group')
		lay = QtGui.QGridLayout()

		lay.addWidget(QtGui.QLabel('Targets (font units):'), 0, 0, 1, 6)
		lay.addWidget(self.__check('master', 'Master stems', True,
				'Use each layer\'s master PostScript stems (Font Info > Hinting).\n'
				'Typed values below are used for an axis the master has no stems for.'), 1, 0, 1, 3)
		lay.addWidget(text_button('Fetch master', 'Copy the current master\'s stems into the fields below.',
				lambda: self.on_fetch()), 1, 3, 1, 3)

		row = 2
		for key, label, tooltip in TARGET_FIELDS:
			lay.addWidget(QtGui.QLabel(label), row, 0, 1, 2)
			lay.addWidget(self.__field(key, tooltip), row, 2, 1, 4)
			row += 1

		self.spn_tol = QtGui.QDoubleSpinBox()
		self.spn_tol.setRange(0., 1000.)
		self.spn_tol.setDecimals(1)
		self.spn_tol.setValue(DEFAULT_TOL)
		self.spn_tol.setToolTip('Capture band: a width within +/- this of a target snaps to it.\nWidths outside every band are left alone.')

		lay.addWidget(QtGui.QLabel('Tolerance:'), row, 0, 1, 2)
		lay.addWidget(self.spn_tol, row, 2, 1, 2)
		lay.addWidget(self.__check('percent', 'Percent', False,
				'Tolerance is a percentage of each target (scales from light to bold).'), row, 4, 1, 2)

		box.setLayout(lay)
		self.lay_main.addWidget(box)

	def __build_method(self):
		box = QtGui.QGroupBox()
		box.setObjectName('box_group')
		lay = QtGui.QGridLayout()

		self.cmb_method = QtGui.QComboBox()
		self.cmb_method.addItems([title for title, _ in METHODS])
		self.cmb_method.setToolTip('Stems: straight and round H/V stems, node accurate; corrections cascade.\n'
				'Strokes: each closed contour is a stroke (CJK builds); any angle; symmetric offset.')
		self.cmb_method.currentIndexChanged.connect(lambda: self.on_method())

		lay.addWidget(QtGui.QLabel('Snap:'), 0, 0, 1, 2)
		lay.addWidget(self.cmb_method, 0, 2, 1, 4)

		# - Stem and stroke options: one page shown at a time
		self.stk_options = QtGui.QStackedWidget()

		page_stems = QtGui.QWidget()
		lay_stems = QtGui.QGridLayout()
		lay_stems.setContentsMargins(0, 0, 0, 0)
		row = self.__popup_rows(lay_stems, 0, STEM_POPUPS)
		self.__check_grid(lay_stems, row, STEM_CHECKS)
		page_stems.setLayout(lay_stems)

		page_strokes = QtGui.QWidget()
		lay_strokes = QtGui.QGridLayout()
		lay_strokes.setContentsMargins(0, 0, 0, 0)
		lay_strokes.addWidget(QtGui.QLabel('Diagonal:'), 0, 0, 1, 2)
		lay_strokes.addWidget(self.__field('d_stems',
				'Targets for diagonal strokes and dots (pie, na, dots), comma separated.\n'
				'Horizontal / vertical strokes use the H / V targets. Empty: diagonals are left alone.'), 0, 2, 1, 4)
		row = self.__popup_rows(lay_strokes, 1, STROKE_POPUPS)
		self.__check_grid(lay_strokes, row, STROKE_CHECKS)
		lay_strokes.setRowStretch(row + (len(STROKE_CHECKS) + 1) // 2, 1)
		page_strokes.setLayout(lay_strokes)

		self.stk_options.addWidget(page_stems)
		self.stk_options.addWidget(page_strokes)
		lay.addWidget(self.stk_options, 1, 0, 1, 6)

		box.setLayout(lay)
		self.lay_main.addWidget(box)

	def __build_uncommon(self):
		box = self.box_uncommon = QtGui.QGroupBox()
		box.setObjectName('box_group')
		lay = QtGui.QGridLayout()

		row = self.__popup_rows(lay, 0, UNCOMMON_POPUPS)

		self.spn_step = QtGui.QDoubleSpinBox()
		self.spn_step.setRange(0., 1000.)
		self.spn_step.setDecimals(1)
		self.spn_step.setValue(DEFAULT_EQUALIZE_STEP)
		self.spn_step.setToolTip('Largest difference between neighbouring stem widths in one group.\n'
				'Wider apart: separate groups, each equalized on its own (a light inner\n'
				'stem keeps its weight). A stem alone in its group is not changed.')

		lay.addWidget(QtGui.QLabel('Step:'), row, 0, 1, 2)
		lay.addWidget(self.spn_step, row, 2, 1, 2)
		lay.addWidget(self.__check('step_percent', 'Percent', True,
				'Step is a percentage of the thinner of two neighbouring stems\n(scales from light to bold). Off: font units.'), row, 4, 1, 2)

		box.setLayout(lay)
		self.lay_main.addWidget(box)

	def __build_actions(self):
		box = QtGui.QGroupBox()
		box.setObjectName('box_group')
		lay = QtGui.QGridLayout()

		lay.addWidget(QtGui.QLabel('Actions:'), 0, 0, 1, 6)
		lay.addWidget(text_button('Analyze', 'Report every measured stem and what a snap would do. Changes nothing.',
				lambda: self.on_snap(False)), 1, 0, 1, 2)
		lay.addWidget(text_button('Select', 'Select the stems (faces) or strokes a snap would move, on the active layer.',
				lambda: self.on_select()), 1, 2, 1, 2)
		lay.addWidget(text_button('Defaults', 'Reset all options to their defaults.',
				lambda: self.on_reset()), 1, 4, 1, 2)
		self.btn_canvas = QtGui.QPushButton('Show on canvas')
		self.btn_canvas.setCheckable(True)
		self.btn_canvas.setToolTip('Draw the stems / strokes of the active layer on the glyph canvas:\n'
				'red: to snap (measured -> target); show all adds green: on target, grey: outside every band.\n'
				'Follows the options, glyph, layer and edits.')
		self.btn_canvas.clicked.connect(lambda: self.live_edit())
		lay.addWidget(self.btn_canvas, 2, 0, 1, 6)

		self.btn_snap = text_button('Snap', 'Snap captured stems / strokes to their targets on every layer in scope.',
				lambda: self.on_snap(True))
		lay.addWidget(self.btn_snap, 3, 0, 1, 6)

		box.setLayout(lay)
		self.lay_main.addWidget(box)

	# - Options -----------------------------------------
	def method(self):
		return METHODS[self.cmb_method.currentIndex][1]

	def on_method(self):
		'''Show the options of the method. Uncommon stems share the Stems page,
		minus the options that the Work on popup replaces.'''
		method = self.method()
		uncommon = method == 'uncommon'
		self.stk_options.setCurrentIndex(1 if method == 'strokes' else 0)
		self.box_uncommon.setVisible(uncommon)
		self.btn_snap.setText('Equalize' if uncommon else 'Snap')
		for key in ('strict', 'selected'):
			self.checks[key][0].setEnabled(not uncommon)

	def choice(self, key):
		cmb, items, default = self.popups[key]
		index = cmb.currentIndex
		return items[index if 0 <= index < len(items) else default][1]

	def checked(self, key):
		return self.checks[key][0].isChecked()

	def on_fetch(self):
		try:
			glyph = eGlyph()
		except Exception:
			self.say('No current glyph.')
			return

		package = glyph.package
		name = glyph.layer().name
		if name not in list(package.masters):
			name = package.master

		v, h = ps_master_stems(package, name)
		if not v and not h:
			self.say('Master "{}" has no PostScript stems (Font Info > Hinting).'.format(name))
			return

		self.fields['v_stems'].setText(', '.join(_fmt(x) for x in v))
		self.fields['h_stems'].setText(', '.join(_fmt(x) for x in h))
		self.say('Master "{}": V {} | H {}'.format(name, ', '.join(_fmt(x) for x in v) or '-', ', '.join(_fmt(x) for x in h) or '-'))

	def on_reset(self):
		for edt in self.fields.values():
			edt.setText('')
		self.spn_tol.setValue(DEFAULT_TOL)
		self.spn_step.setValue(DEFAULT_EQUALIZE_STEP)
		for chk, value in self.checks.values():
			chk.setChecked(value)
		for cmb, items, default in self.popups.values():
			cmb.setCurrentIndex(default)
		self.cmb_method.setCurrentIndex(0)
		self.on_method()
		self.say('Defaults restored.')

	def targets(self, package, layer):
		'''(v, h, d) target lists for one layer.'''
		v = _parse_list(self.fields['v_stems'].text)
		h = _parse_list(self.fields['h_stems'].text)
		if self.checked('master'):
			mv, mh = ps_master_stems(package, layer)
			v, h = mv or v, mh or h
		return v, h, _parse_list(self.fields['d_stems'].text)

	def allowlist(self, keyed):
		'''{key: [values]} -> WidthAllowlist with the panel tolerance.'''
		tol, percent = max(0., float(self.spn_tol.value)), self.checked('percent')
		al = WidthAllowlist()
		for key, values in keyed.items():
			for value in values:
				band = value * tol / 100. if percent else tol
				al.add(key, WidthTarget(value, band, band))
		return al

	def italic(self, package, layer):
		'''Italic angle passed to core for this layer (0 with "Italic angle" off).'''
		return _italic_angle(package, layer) if self.checked('italic') else 0.

	def options_signature(self):
		'''Cheap signature of every option (the canvas re-analyses when it changes).'''
		return (self.cmb_method.currentIndex, float(self.spn_tol.value), float(self.spn_step.value),
				tuple(sorted((key, edt.text) for key, edt in self.fields.items())),
				tuple(sorted((key, chk.isChecked()) for key, (chk, _) in self.checks.items())),
				tuple(sorted((key, cmb.currentIndex) for key, (cmb, _, _) in self.popups.items())))

	# - Messages ----------------------------------------
	def say(self, *lines):
		for line in lines:
			print('{}: {}'.format(app_name, line))
		self.txt_report.setPlainText('\n'.join(lines))

	# - Collect -----------------------------------------
	def layer_names(self, glyph):
		'''Active layer first (holds the selection), then the other masthead layers.'''
		active = glyph.layer().name
		names = glyph._prepareLayers(pLayers, compatible=False) if pLayers is not None else [active]
		return [active] + sorted(name for name in names if name != active)

	def collect(self, glyph, names=None):
		'''([_LayerItem], [notes]) plus the selection on the active layer:
		(set of (contour, node), set of contour indices). names: layers to
		read (default: the masthead layers, active first).'''
		items, notes = [], []

		for name in (names if names is not None else self.layer_names(glyph)):
			fl_layer = glyph.layer(name)
			if fl_layer is None:
				continue

			shapes, skipped, transformed = [], [], []
			for sid, shape in enumerate(fl_layer.shapes):
				kind = _kind(shape)
				if kind is not None:
					skipped.append('#{} {}'.format(sid, kind))
				elif len(shape.contours):
					shapes.append(shape)
					if _transformed(shape):
						transformed.append('#{}'.format(sid))

			if transformed:
				notes.append('{}: skipped, transformed elements {}. Apply the transforms first.'.format(name, ', '.join(transformed)))
				continue

			if skipped:
				notes.append('{}: not processed: {}.'.format(name, ', '.join(skipped)))

			items.append(_LayerItem(name, fl_layer, shapes))

		nodes, contours = set(), set()
		if items and items[0].name == glyph.layer().name:
			for ci, c in enumerate(items[0].contours):
				for ni, n in enumerate(c.nodes):
					if n.selected:
						nodes.add((ci, ni))
						contours.add(ci)

		return items, notes, nodes, contours

	# - Actions -----------------------------------------
	def on_snap(self, apply):
		self.process(apply)

	def on_select(self):
		self.process(False, select=True)

	def process(self, apply, select=False):
		try:
			glyph = eGlyph()
		except Exception:
			self.say('No current glyph.')
			return

		try:
			self.snap(glyph, apply, select)
		except Exception:
			output(2, app_name, 'Failed:')
			print(traceback.format_exc())
			self.say('Glyph "{}": failed, see the Output panel.'.format(glyph.name))

		if self.live_on():
			self.live_tool.panel_wrote()

	def snap(self, glyph, apply, select):
		items, notes, sel_nodes, sel_contours = self.collect(glyph)
		active = glyph.layer().name
		if select:
			items = [item for item in items if item.name == active]

		lines = list(notes)
		if pMode != 0:
			lines.append('Single glyph mode: only the current glyph is processed.')

		if not items:
			lines.append('Glyph "{}": no layers to process.'.format(glyph.name))
			self.say(*lines)
			return

		uncommon = self.method() == 'uncommon'
		stems = self.method() != 'strokes'
		if uncommon:
			if self.choice('scope') == 'selected' and not sel_contours:
				self.say('Glyph "{}": select a node on the contours to equalize.'.format(glyph.name))
				return

		elif stems and self.checked('selected') and not sel_nodes:
			self.say('Glyph "{}": select a node on the stems to snap.'.format(glyph.name))
			return

		if not stems and self.checked('s_selected') and not sel_contours:
			self.say('Glyph "{}": select a node on the strokes to snap.'.format(glyph.name))
			return

		package = glyph.package
		started = time.time()
		total, no_targets, written = 0, [], []

		print('\n{}: {} @ {}'.format(app_name, glyph.name, ', '.join(item.name for item in items)))

		for item in items:
			v, h, d = self.targets(package, item.name)
			if not uncommon and not (v or h or (d and not stems)):
				no_targets.append(item.name)
				continue

			try:
				if uncommon:
					line, moved, write = self.equalize_stems(glyph, package, item, v, h, sel_contours, apply)
				elif stems:
					line, moved, write = self.snap_stems(glyph, package, item, v, h, sel_nodes, apply)
				else:
					line, moved, write = self.snap_strokes(glyph, item, v, h, d, sel_contours, apply)

			except Exception as error:
				lines.append('{} | {}: failed ({}).'.format(glyph.name, item.name, error))
				print(traceback.format_exc())
				continue

			lines.append(line)
			total += moved

			if select:
				self.select(item, write)
			elif apply and moved:
				self.write(item, *write)
				written.append(item.name)

		if no_targets:
			lines.append('No targets for {}: set master stems or type values.'.format(', '.join(no_targets)))

		what = 'stem(s)' if stems else 'stroke(s)'
		verb, done = ('equalize', 'Equalized') if uncommon else ('snap', 'Snapped')
		if select:
			lines.append('Selected {} {} to {} on "{}".'.format(total, what, verb, active))
			pWorkspace().getCanvas(True).refreshAll()

		elif apply:
			if written:
				for name in written:
					glyph.update(name)
				glyph.updateObject(glyph.fl, '{} | {} @ {}'.format(app_name, glyph.name, '; '.join(written)), False)
			lines.append('{} {} {} ({:.2f}s).'.format(done, total, what, time.time() - started))

		else:
			lines.append('Analyze: {} {} to {}; nothing changed ({:.2f}s).'.format(total, what, verb, time.time() - started))

		self.say(*lines)

	# -- Uncommon stems
	def equalize_scope(self, item, sel_contours):
		'''(selected nodes or None, pools or None) for the "Work on" option.'''
		scope = self.choice('scope')

		if scope == 'selected':
			return family_selection(item.contours, sel_contours), None

		if scope == 'element':
			pools, first = [], 0
			for shape in item.shapes:
				count = len(shape.contours)
				pools.append(range(first, first + count))
				first += count
			return None, pools

		return None, None

	def equalize_stems(self, glyph, package, item, v, h, sel_contours, apply, verbose=True):
		selected, pools = self.equalize_scope(item, sel_contours)

		report = equalize_stems(item.contours, self.allowlist({Axis.V: v, Axis.H: h}),
								step=float(self.spn_step.value),
								percent=self.checked('step_percent'),
								pools=pools,
								detector=StemDetector(mode=self.choice('detect'), topology=Topology.INK),
								axis=self.choice('axis'),
								anchor=self.choice('anchor'),
								scope=self.choice('cascade'),
								italic_angle=self.italic(package, item.name),
								selected=selected,
								round_ints=self.checked('round'),
								pin_extremes=self.checked('pin'),
								protect_aligned=self.checked('aligned'),
								apply=apply)

		for g in (report.groups if verbose else []):
			print('    {} {:>7g}  {:<8}  from {}'.format(g.axis, g.target, g.source,
				', '.join(_fmt(w) for w in sorted(g.widths))))

		summary = ' | '.join('{} {}'.format(axis, ', '.join('{}x{}'.format(len(g.stems), _fmt(g.target))
							 for g in report.groups if g.axis == axis))
							 for axis in (Axis.V, Axis.H) if any(g.axis == axis for g in report.groups))

		line = '{} | {}: {} stem(s): {} to equalize, {} unchanged, {} not stems; {}'.format(
			glyph.name, item.name, len(report.captured), len(report.moved),
			len(report.captured) - len(report.moved), len(report.out_of_band), summary or 'no groups') + _aligned_note(report)

		return line, len(report.moved), (item.contours, None, False, report)

	# -- Stems
	def snap_stems(self, glyph, package, item, v, h, sel_nodes, apply, verbose=True):
		detector = StemDetector(mode=self.choice('detect'),
								topology=Topology.STRICT if self.checked('strict') else Topology.PERMISSIVE)

		report = snap_stems(item.contours, self.allowlist({Axis.V: v, Axis.H: h}),
							detector=detector,
							axis=self.choice('axis'),
							anchor=self.choice('anchor'),
							scope=self.choice('cascade'),
							italic_angle=self.italic(package, item.name),
							selected=sel_nodes if self.checked('selected') else None,
							round_ints=self.checked('round'),
							pin_extremes=self.checked('pin'),
							protect_aligned=self.checked('aligned'),
							apply=apply)

		for k in (report.captured if verbose else []):
			c = k.source
			print('    {} {:>7.2f} -> {:g} ({:+.2f})  faces {:.1f} / {:.1f}  contours {} / {}'.format(
				k.key, k.measured, k.target.value, k.delta,
				c.edge_a.coord, c.edge_b.coord, c.edge_a.contour_idx, c.edge_b.contour_idx))

		on_target = len(report.captured) - len(report.moved)
		line = '{} | {}: {} stem(s): {} to snap, {} on target, {} outside bands'.format(
			glyph.name, item.name, len(report.candidates), len(report.moved), on_target, len(report.out_of_band)) + _aligned_note(report)

		# write: (contours, only these indices or None = all, separated); select reads report.nodes()
		return line, len(report.moved), (item.contours, None, False, report)

	# -- Strokes
	def snap_strokes(self, glyph, item, v, h, d, sel_contours, apply, verbose=True):
		keyed = {StrokeType.VERTICAL: v, StrokeType.HORIZONTAL: h}
		keyed.update({t: d for t in DIAGONAL_TYPES})

		report = snap_strokes(item.contours, self.allowlist(keyed),
							  match_on=self.choice('match'),
							  mat_quality=self.choice('quality'),
							  separate=self.checked('separate'),
							  selected=sel_contours if self.checked('s_selected') else None,
							  round_ints=self.checked('s_round'),
							  apply=apply)

		for m in (report.measurements if verbose else []):
			print('    {:<10} axis {:5.1f} deg  width min/med/max {:.1f} / {:.1f} / {:.1f}'.format(
				m.stroke_type, m.axis_angle_deg, m.width_min, m.width_median, m.width_max))

		for k in (report.captured if verbose else []):
			print('    {:<10} {:>7.2f} -> {:g} ({:+.2f})'.format(k.key, k.measured, k.target.value, k.delta))

		on_target = len(report.captured) - len(report.moved)
		line = '{} | {}: {} stroke(s): {} to snap, {} on target, {} outside bands'.format(
			glyph.name, item.name, len(report.measurements), len(report.moved), on_target,
			len(report.measurements) - len(report.captured))

		if report.separated:
			line += '; separated into {} stroke(s)'.format(len(report.strokes))
			return line, len(report.moved), (report.contours, None, True, report)

		# Unseparated: write back only the moved strokes; the others keep
		# their host contours untouched (no quadratic -> cubic conversion).
		moved = set(id(viol.source.stroke) for viol in report.moved)
		indices = set(ci for ci, stroke in self.stroke_sources(report) if id(stroke) in moved)
		return line, len(report.moved), (report.contours, indices, False, report)

	@staticmethod
	def stroke_sources(report):
		'''(contour index, stroke) pairs for unseparated stroke reports.'''
		skipped = set(report.skipped)
		indices = [i for i in range(len(report.contours)) if i not in skipped]
		return list(zip(indices, report.strokes))

	# - Host write / select -----------------------------
	def write(self, item, contours, only, separated, report):
		'''Mount the result back into the layer's plain elements.
		Same node count: nodes in place. Otherwise the contour is rebuilt
		inside its element. Separated strokes: the processed elements are
		replaced by one new element; other elements are kept.'''
		if separated:
			for shape in item.shapes:
				item.fl_layer.removeShape(shape)
			item.fl_layer.addShape(_build_fl_shape(Shape(list(contours))))
			return

		k = 0
		for shape in item.shapes:
			new_contours, rebuilt = [], False

			for fl_contour in shape.contours:
				core = contours[k]

				if only is not None and k not in only:
					new_contours.append(fl_contour)

				elif len(core.nodes) == len(fl_contour.nodes()):
					trContour(fl_contour).mount(core)
					new_contours.append(fl_contour)

				else:
					new_contours.append(_build_fl_contour(core))
					rebuilt = True

				k += 1

			if rebuilt:
				shape.contours = new_contours

	def select(self, item, result):
		contours, only, separated, report = result

		for fl_contour in item.fl_contours:
			for node in fl_contour.nodes():
				node.selected = False

		if self.method() != 'strokes':
			picked = report.nodes('moved')
		else:
			if separated:
				return		# separated strokes have no host nodes yet
			picked = set((ci, ni) for ci in only for ni in range(len(item.contours[ci].nodes)))

		for ci, ni in picked:
			if ci < len(item.fl_contours):
				fl_nodes = item.fl_contours[ci].nodes()
				if ni < len(fl_nodes):
					fl_nodes[ni].selected = True

	# - Canvas (Show on canvas) -------------------------
	# The canvas asks live_state() for the analysis of the layer it shows.
	# It is a dry run of the same Stems / Strokes code as Analyze, cached
	# until the target, an option, the selection (when used) or the
	# outline changes (live_invalidate). Nothing here writes the glyph.
	def live_on(self):
		return self.live_tool is not None and self.live_tool.alive

	def live_edit(self):
		'''Show on canvas button: start or stop the canvas overlay.'''
		if self.btn_canvas.isChecked():
			self.live_invalidate()
			self.live_tool = TRStemSnapCanvas.start(self)
		else:
			self.live_tool = None
			TRStemSnapCanvas.stop()

	def live_closed(self):
		'''Close icon on the canvas.'''
		self.btn_canvas.setChecked(False)
		self.live_edit()

	def live_invalidate(self):
		'''The outline changed: analyse again on the next live_state().'''
		self._live_rev += 1

	def live_uses_selection(self):
		if self.method() == 'uncommon':
			return self.choice('scope') == 'selected'
		return self.checked('selected' if self.method() == 'stems' else 's_selected')

	def live_state(self, target, selection=None):
		'''Analysis of the canvas layer, or None without a target.
		Args:
			target (tuple): (glyph name, layer name) shown on the canvas
			selection: selection signature (used only when an option needs it)
		Returns:
			dict: target, method, problem (str or None), notes, slant (radians,
			+ leans right), items (see live_stem_items / live_stroke_items) and
			counts (to snap, on target, outside).
		'''
		if target is None:
			return None

		key = (target, self.options_signature(), self._live_rev, selection if self.live_uses_selection() else None)
		if key != self._live_key:
			self._live_key = key
			try:
				self._live_st = self.live_analyze(target)
			except Exception:
				print(traceback.format_exc())
				self._live_st = self.live_result(target, problem='analysis failed, see the Output panel')

		return self._live_st

	def live_result(self, target, problem=None, notes=(), slant=0., items=()):
		items = list(items)
		counts = tuple(sum(1 for item in items if item['status'] == status) for status in ('snap', 'ok', 'out'))
		return {'target': target, 'method': self.method(), 'problem': problem, 'notes': list(notes),
				'slant': slant, 'items': items, 'counts': counts}

	def live_analyze(self, target):
		glyph = eGlyph()
		if (glyph.name, glyph.layer().name) != tuple(target):
			return self.live_result(target, problem='the panel sees glyph "{}"'.format(glyph.name))

		active = target[1]
		layers, notes, sel_nodes, sel_contours = self.collect(glyph, [active])
		if not layers or not layers[0].contours:
			return self.live_result(target, problem=notes[0] if notes else 'no contours on this layer', notes=notes[1:])

		item, package = layers[0], glyph.package

		if self.method() == 'uncommon':
			if self.choice('scope') == 'selected' and not sel_contours:
				return self.live_result(target, problem='select a node on the contours to check', notes=notes)

			v, h, _ = self.targets(package, active)
			result = self.equalize_stems(glyph, package, item, v, h, sel_contours, False, verbose=False)[2]
			return self.live_result(target, notes=notes, slant=math.radians(self.italic(package, active)),
									items=self.live_stem_items(result[3]))

		v, h, d = self.targets(package, active)
		stems = self.method() == 'stems'

		if not (v or h or (d and not stems)):
			return self.live_result(target, problem='no targets: set master stems or type values', notes=notes)

		if stems and self.checked('selected') and not sel_nodes:
			return self.live_result(target, problem='select a node on the stems to check', notes=notes)

		if not stems and self.checked('s_selected') and not sel_contours:
			return self.live_result(target, problem='select a node on the strokes to check', notes=notes)

		if stems:
			result = self.snap_stems(glyph, package, item, v, h, sel_nodes, False, verbose=False)[2]
			return self.live_result(target, notes=notes, slant=math.radians(self.italic(package, active)),
									items=self.live_stem_items(result[3]))

		result = self.snap_strokes(glyph, item, v, h, d, sel_contours, False, verbose=False)[2]
		return self.live_result(target, notes=notes, items=self.live_stroke_items(result[3]))

	@staticmethod
	def live_stem_items(report):
		'''One dict per detected stem, in deslanted font units: axis, lo / hi
		(face coordinates), span (overlap of the faces along the stem),
		width, target (or None), delta, status ('snap' / 'ok' / 'out').'''
		captured = dict((id(v.source), v) for v in report.captured)
		moved = set(id(v.source) for v in report.moved)
		items = []

		for c in report.candidates:
			v = captured.get(id(c))
			lo, hi = sorted((c.edge_a.coord, c.edge_b.coord))
			span = (max(c.edge_a.span[0], c.edge_b.span[0]), min(c.edge_a.span[1], c.edge_b.span[1]))
			items.append({'kind': 'stem', 'axis': c.axis, 'lo': lo, 'hi': hi, 'span': span,
						  'width': c.measured_width, 'target': v.target.value if v is not None else None,
						  'delta': v.delta if v is not None else 0.,
						  'status': 'snap' if id(c) in moved else 'ok' if v is not None else 'out'})
		return items

	def live_stroke_items(self, report):
		'''One dict per measured stroke: contour (core), type, width (the
		matched one), target (or None), delta, status.'''
		captured = dict((id(v.source), v) for v in report.captured)
		moved = set(id(v.source) for v in report.moved)
		match = self.choice('match')
		items = []

		for m in report.measurements:
			v = captured.get(id(m))
			width = v.measured if v is not None else {'min': m.width_min, 'max': m.width_max}.get(match, m.width_median)
			items.append({'kind': 'stroke', 'contour': m.stroke, 'type': m.stroke_type, 'width': width,
						  'target': v.target.value if v is not None else None, 'delta': v.delta if v is not None else 0.,
						  'status': 'snap' if id(m) in moved else 'ok' if v is not None else 'out'})
		return items

# - Canvas -----------------------------
STATUS_OK_COLOR = QtGui.QColor(40, 170, 90)		# green: on target

class TRStemSnapCanvas(co.CanvasOverlay):
	'''Stem Snap analysis drawn on the glyph canvas, driven by TRStemSnapPanel.

	Stems     band between the two faces over their common span (a
	          parallelogram in italic); curve extrema get a short band
	Strokes   the stroke contour, filled
	Colors    red: to snap, label "measured -> target"; with Show all
	          also green: on target, grey dashed: outside every band
	Icons     close, re-analyse, show all, select, snap; with the banner
	          they sit LIFT_UNITS above the glyph's top left and follow it

	Outside edits are re-analysed once the outline settles (mouse up and
	SETTLE seconds without change); the bands are hidden meanwhile.
	'''
	NAME = 'tr_stem_snap'
	POLL_INTERVAL = .15			# seconds between panel / selection checks
	SETTLE = .25				# seconds an outside edit must rest before re-analysis
	MIN_SPAN_PX = 14.			# shortest band on screen (curve extrema)
	LIFT_UNITS = 100.			# icon strip + banner: this far above the glyph's top left (font units)
	STRIP_ORIGIN = (16., 16.)	# icon strip on an empty layer: top left of the viewport

	def __init__(self, panel):
		co.CanvasOverlay.__init__(self)
		self.panel = panel
		self.st = None				# panel.live_state()
		self.show_all = False
		self._dirty_at = None		# time of the last outside edit not yet analysed
		self._sel_sig = None
		self._poll = om.Throttle(self.POLL_INTERVAL)

		self.strip = CanvasIconStrip(self, self._strip_origin, [
			('close', None, 'Close: stop showing Stem Snap on the canvas', self._close, True),
			('refresh', 'refresh', 'Analyse the layer again', self._reanalyse, True),
			('all', 'search', 'Show all: also stems on target (green) and outside every band (grey)',
			 self._toggle_all, True, lambda: self.show_all),
			('select', 'selection_basic', 'Select what a snap would move (active layer)', lambda: self._run('on_select'), True),
			('snap', 'action_play', 'Snap: as the panel Snap button (every layer in scope)', lambda: self._run('on_snap', True), True),
		])
		self.handles = list(self.strip.handles)

	# - Panel link ----------------------
	def _call(self, name, *args):
		try:
			return getattr(self.panel, name)(*args)
		except Exception:
			co._log.exception('{}.{}'.format(self.NAME, name))
			return None

	def _panel_alive(self):
		try:
			co.qv(self.panel, 'objectName')
			return True
		except Exception:
			return False

	def _refresh(self):
		st = self._call('live_state', self.target, self._sel_sig)
		if st is not self.st:
			self.st = st
			self.request_repaint()

	def panel_wrote(self):
		'''Called by the panel after Snap / Select: our own edit, analyse now.'''
		try:
			self.accept_geometry()
			self._dirty_at = None
			self._sel_sig = self._selection_signature()
			self._call('live_invalidate')
			self._refresh()
			self.request_repaint()
		except Exception:
			co._log.exception('{}.panel_wrote'.format(self.NAME))

	def _selection_signature(self):
		'''Cheap selection signature of the active layer (see TRDeltaCanvas):
		per contour with a selection, its index, count and selected bounds.'''
		layer = self.fl_layer
		if layer is None: return None
		try:
			sig = []
			for index, contour in enumerate(layer.getContours() or []):
				selected = contour.getSelectedNodes()
				if not selected: continue
				r = contour.getSelectedBoundingBox()
				sig.append((index, len(selected)) + om.round_sig((r.x(), r.y(), r.width(), r.height()), 1))
			return tuple(sig)
		except Exception:
			co._log.exception('{}.selection_signature'.format(self.NAME))
			return None

	@staticmethod
	def _mouse_down():
		buttons = co.qv(QtGui.QApplication, 'mouseButtons')
		try:
			return bool(int(buttons) & int(QtCore.Qt.LeftButton))
		except TypeError:
			return bool(buttons & QtCore.Qt.LeftButton)

	def _ready(self):
		return self.st is not None and self.st['target'] == self.target and self._dirty_at is None

	def _glyph_corner(self):
		'''Top left (xmin, ymax) of the active layer's bounds in font units, or None if empty.'''
		if self.fl_layer is None: return None
		try:
			r = co.qv(self.fl_layer, 'boundingBox')
		except Exception:
			return None
		if r.width() <= 0 and r.height() <= 0: return None
		return (float(r.x()), float(r.y() + r.height()))

	def _strip_origin(self, mapping):
		'''Close icon slot: LIFT_UNITS above the glyph's top left, its left
		edge on the glyph's left; the strip extends right, the banner after it.'''
		corner = self._glyph_corner()
		if corner is None:
			return self.STRIP_ORIGIN + (1., True)
		x, y = mapping.to_view_xy(corner[0], corner[1] + self.LIFT_UNITS)
		return (x + CanvasIconStrip.RADIUS, y, 1., True)

	# - Overlay hooks -------------------
	def on_attach(self):
		self._sel_sig = self._selection_signature()
		self._refresh()

	def on_target_changed(self, mapping):
		self._dirty_at = None
		self._sel_sig = self._selection_signature()
		self._refresh()
		self.request_repaint()

	def on_geometry_changed(self):
		self._dirty_at = time.time()		# edited outside: wait for it to settle
		self.request_repaint()

	def on_tick(self):
		if not self._panel_alive():
			type(self).stop()				# the panel is gone
			return

		if self._dirty_at is not None:
			if time.time() - self._dirty_at < self.SETTLE or self._mouse_down(): return
			self._dirty_at = None
			self._call('live_invalidate')
			self._refresh()
			self.request_repaint()
			return

		if self._poll.ready():
			self._sel_sig = self._selection_signature()
			self._refresh()					# options, selection (cached in the panel)

	def on_handle_click(self, handle, drag):
		self.strip.click(handle)

	# - Strip actions -------------------
	def _close(self):
		if self._panel_alive():
			self.panel.live_closed()
		else:
			type(self).stop()

	def _reanalyse(self):
		self._dirty_at = None
		self._call('live_invalidate')
		self._refresh()
		self.request_repaint()

	def _toggle_all(self):
		self.show_all = not self.show_all
		self.request_repaint()

	def _run(self, name, *args):
		'''Panel action from the canvas; the panel calls panel_wrote() after.'''
		self._call(name, *args)

	# - Painting ------------------------
	def _status_colors(self, status):
		'''(pen, brush) for a status.'''
		c = self.colors
		if status == 'snap':
			return co.cosmetic_pen(c['error'], 1.5), co.solid_brush(c['error'], 70)
		if status == 'ok':
			return co.cosmetic_pen(STATUS_OK_COLOR, 1.), co.solid_brush(STATUS_OK_COLOR, 35)
		return co.cosmetic_pen(c['muted'], 1., QtCore.Qt.DashLine), co.no_brush()

	def _stem_corners(self, item, mapping):
		'''Band corners in font units (re-slanted). A span shorter than
		MIN_SPAN_PX on screen (curve extrema, faces that barely overlap)
		is widened about its middle.'''
		s0, s1 = item['span']
		least = mapping.len_to_font(self.MIN_SPAN_PX)
		if s1 - s0 < least:
			mid = (s0 + s1) * .5
			s0, s1 = mid - least * .5, mid + least * .5

		lo, hi, a = item['lo'], item['hi'], self.st['slant']
		if item['axis'] == Axis.V:
			corners = ((lo, s0), (hi, s0), (hi, s1), (lo, s1))
		else:
			corners = ((s0, lo), (s1, lo), (s1, hi), (s0, hi))
		return [om.reslant(x, y, a) for x, y in corners]

	def _label_text(self, item):
		if item['status'] == 'snap':
			return '{} → {}'.format(_fmt(item['width']), _fmt(item['target']))
		return _fmt(item['width'])

	def _banner(self):
		st = self.st
		if st is None:
			return 'open a glyph', True
		if self._dirty_at is not None:
			return 'outline changed, analysing when it settles', False
		if st['problem']:
			return st['problem'], True

		what = 'stem(s)' if st['method'] != 'strokes' else 'stroke(s)'
		snap, ok, out = st['counts']
		if st['method'] == 'uncommon':
			text = '{} | {}: {} {} to equalize, {} unchanged, {} not stems'.format(st['target'][0], st['target'][1], snap, what, ok, out)
		else:
			text = '{} | {}: {} {} to snap, {} on target, {} outside bands'.format(st['target'][0], st['target'][1], snap, what, ok, out)
		if abs(st['slant']) > 1e-9:
			text += '   italic {:g}°'.format(round(math.degrees(st['slant']), 1))
		return text, False

	def paint_overlay(self, p, mapping):
		c = self.colors

		# - Banner right of the icon strip; notes as a second line
		text, problem = self._banner()
		ox, oy = self._strip_origin(mapping)[:2]
		x = ox + self.strip.width(True) - 4.
		rect = self.draw_label(p, QtCore.QPointF(x, oy), '{}: {}'.format(app_name, text), 'LM',
							   color=c['error'] if problem else None, offset=0.)
		if self.st is not None and self.st['notes'] and self.st['target'] == self.target:
			self.draw_label(p, QtCore.QPointF(rect.left(), rect.bottom()), '   '.join(self.st['notes']), 'TL',
							color=c['error'], offset=4.)

		if not self._ready():
			return

		# - Bands: outside first, to-snap last (on top)
		order = {'out': 0, 'ok': 1, 'snap': 2}
		shown = [item for item in self.st['items'] if self.show_all or item['status'] == 'snap']

		for item in sorted(shown, key=lambda item: order[item['status']]):
			pen, brush = self._status_colors(item['status'])

			if item['kind'] == 'stem':
				corners = self._stem_corners(item, mapping)
				path = QtGui.QPainterPath()
				path.moveTo(*corners[0])
				for point in corners[1:]:
					path.lineTo(*point)
				path.closeSubpath()
				center = (sum(x for x, y in corners) * .25, sum(y for x, y in corners) * .25)
			else:
				path = self.core_layer_to_path(item['contour'])
				r = path.boundingRect()
				center = (r.center().x(), r.center().y())

			self.draw_font_path(p, path, pen, brush)

			if item['status'] != 'out':
				self.draw_label(p, mapping.to_view(*center), self._label_text(item), 'C',
								color=c['error'] if item['status'] == 'snap' else STATUS_OK_COLOR, offset=0.)

	def paint_handle(self, p, handle, x, y, hot):
		return self.strip.paint(p, handle, x, y, hot)

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
		layoutV.addWidget(TRStemSnapPanel())

		# - Build
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

	test.show()
