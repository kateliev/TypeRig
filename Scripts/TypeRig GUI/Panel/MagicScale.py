#FLM: TR: Magic Scale
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 	(http://www.kateliev.com)
# (C) TypeRig 					(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Magic Scale: stem-preserving 1D warp of the current glyph,
# per axis (typerig.core.algo.magic_scale). Stems keep their thickness;
# the whitespace absorbs the change. Counter (中宫) and gravity
# (重心) redistribute the whitespace.
#
# Live editing works like the Delta panel: the panel keeps
# references to the glyph's own FL nodes and writes x/y into
# them in place, then glyph.update() and a canvas refresh.
#
#   first control change -> capture: snapshot coords, detect
#                           stems ONCE (knot refs), undo snapshot
#   control changes      -> restore source, warp, write nodes
#   Reset                -> write the source back
#   Apply                -> undo snapshot; result becomes source
#
# Layers follow the panel masthead (active / masters / selected);
# the active layer is the reference for stem detection. Switching
# glyph or layers re-captures and resets the controls (as Delta).
#
# Live Edit (canvas): draws the controls on the glyph itself and
# drives the panel's own controls (frame quad = scale, inner quad =
# counter, stem ring = stem thickness, cross = origin). Writing,
# layers and undo stay the panel's: it is another way to move the
# same controls. Editing the outline with FontLab's tools while
# Live Edit is on re-captures it as the new source.

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import warnings

import fontlab as fl6

from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, TRFlowLayout, TRCustomSpinController
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.tr.objects.contour import trContour
from typerig.proxy.fl.gui import canvas_overlay as co
from typerig.proxy.fl.gui import overlay_math as om

from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer
from typerig.core.algo.stem_snap import DetectMode, Topology
from typerig.core.algo import magic_scale

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Magic Scale', '1.0'

_LIVE_KEYS = ('scale_x', 'scale_y', 'stem_v', 'stem_h', 'counter_x', 'counter_y')

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Helpers ----------------------------
class _Item(object):
	'''One layer: FL node references, source coords, and a core Layer
	built from the same contours in the same node order.'''
	def __init__(self, name, fl_contours, advance_width=0.):
		self.name = name
		self.fl_nodes = []
		core_contours = []

		for fl_contour in fl_contours:
			self.fl_nodes.extend(fl_contour.nodes())
			core_contours.append(trContour(fl_contour).eject())

		self.core = Layer([Shape(core_contours)], width=float(advance_width))
		self.src = [(float(n.x), float(n.y)) for n in self.fl_nodes]
		assert len(self.src) == len(self.core.nodes), 'Node order mismatch on layer {}'.format(name)
		self.centroid = magic_scale.ink_centroid(self.core.contours)

	def restore(self):
		for node, (x, y) in zip(self.core.nodes, self.src):
			node.x, node.y = x, y


def _fmt_knots(values):
	return ' | '.join('{:.0f}'.format(v) for v in values)

# - Panel ------------------------------
class TRMagicScalePanel(QtGui.QWidget):
	def __init__(self):
		super(TRMagicScalePanel, self).__init__()

		# - Init
		self.glyph = None			# eGlyph
		self.items = []				# [_Item]; items[0] is the reference (active layer)
		self.refs = None			# magic_scale.detect_knot_refs on the reference
		self.signature = None		# (glyph, active layer, layer names) at capture
		self.live_ref = None		# (frame, warp_x, warp_y) of the reference layer, last execute
		self.live_tool = None		# TRMagicScaleCanvas while Live Edit is on

		# - Build Layout
		lay_main = QtGui.QVBoxLayout()

		# -- Actions
		box_actions = QtGui.QGroupBox()
		box_actions.setObjectName('box_group')
		lay_actions = TRFlowLayout(spacing=10)

		tooltip_button = 'Capture glyph: snapshot the current outline and detect stems'
		self.btn_capture = CustomPushButton('node_target', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_capture)
		self.btn_capture.clicked.connect(lambda: self.capture(True))

		tooltip_button = 'Live Edit: show the controls on the glyph canvas'
		self.btn_live = CustomPushButton('selection_basic', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_actions.addWidget(self.btn_live)
		self.btn_live.clicked.connect(lambda: self.live_edit())

		tooltip_button = 'Update: warp the captured outline with the current controls'
		self.btn_update = CustomPushButton('action_play', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_update)
		self.btn_update.clicked.connect(lambda: self.execute())

		tooltip_button = 'Reset: write the captured outline back'
		self.btn_reset = CustomPushButton('undo', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_reset)
		self.btn_reset.clicked.connect(lambda: self.reset())

		tooltip_button = 'Defaults: set every control to identity and revert'
		self.btn_defaults = CustomPushButton('refresh', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_defaults)
		self.btn_defaults.clicked.connect(lambda: self.defaults())

		tooltip_button = 'Apply: make undo snapshot; the result becomes the new source'
		self.btn_apply = CustomPushButton('undo_snapshot', tooltip=tooltip_button, obj_name='btn_panel')
		lay_actions.addWidget(self.btn_apply)
		self.btn_apply.clicked.connect(lambda: self.apply())

		box_actions.setLayout(lay_actions)
		lay_main.addWidget(box_actions)

		# -- Options
		box_options = QtGui.QGroupBox()
		box_options.setObjectName('box_group')
		lay_options = TRFlowLayout(spacing=10)

		tooltip_button = 'Live: apply on every control change'
		self.chk_live = CustomPushButton('sync', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_live)

		tooltip_button = 'Anchored handles: keep smooth nodes collinear (off = map handles like nodes)'
		self.chk_anchored = CustomPushButton('icon_anchor', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_anchored)
		self.chk_anchored.clicked.connect(lambda: self.changed())

		tooltip_button = 'Frame: advance width (off = outline bounds)'
		self.chk_advance = CustomPushButton('metrics_advance_alt', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_advance)
		self.chk_advance.clicked.connect(lambda: self.redetect())

		tooltip_button = 'Show extended controls'
		self.chk_toggle_controls = CustomPushButton('value_controls', checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_toggle_controls)
		self.chk_toggle_controls.clicked.connect(lambda: self.__toggle_controls())

		tooltip_button = 'Show stem detection settings and report'
		self.chk_toggle_detect = CustomPushButton('search', checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_toggle_detect)
		self.chk_toggle_detect.clicked.connect(lambda: self.__toggle_detect())

		box_options.setLayout(lay_options)
		lay_main.addWidget(box_options)

		# -- Alignment (frame point that stays fixed)
		box_align = QtGui.QGroupBox()
		box_align.setObjectName('box_group')
		lay_align = TRFlowLayout(spacing=10)

		self.grp_align = QtGui.QButtonGroup()
		self.grp_align.setExclusive(True)
		self.align_codes = {}

		align_buttons = [
			('node_center', 'C', 'Keep frame center'),
			('node_bottom_left', 'BL', 'Keep frame bottom left'),
			('node_middle_bottom', 'BM', 'Keep frame bottom middle'),
			('node_bottom_right', 'BR', 'Keep frame bottom right'),
			('node_middle_left', 'LM', 'Keep frame left middle'),
			('node_middle_right', 'RM', 'Keep frame right middle'),
			('node_top_left', 'TL', 'Keep frame top left'),
			('node_middle_top', 'TM', 'Keep frame top middle'),
			('node_top_right', 'TR', 'Keep frame top right'),
			('node_align_bottom_left', 'B', 'Keep origin (0, 0)'),
		]

		for bid, (icon, code, tooltip_button) in enumerate(align_buttons):
			btn = CustomPushButton(icon, checkable=True, checked=(code == 'C'), tooltip=tooltip_button, obj_name='btn_panel_opt')
			self.grp_align.addButton(btn, bid)
			self.align_codes[bid] = code
			lay_align.addWidget(btn)

		self.grp_align.buttonClicked.connect(lambda: self.changed())

		box_align.setLayout(lay_align)
		lay_main.addWidget(box_align)

		# -- Detection settings (hidden by default)
		self.box_detect = QtGui.QGroupBox()
		self.box_detect.setObjectName('box_group')
		lay_detect = QtGui.QGridLayout()

		self.cmb_mode = QtGui.QComboBox()
		self.cmb_mode.addItem('Coincident (geometry)', DetectMode.COINCIDENT)
		self.cmb_mode.addItem('Extrema (tangents)', DetectMode.EXTREMA)

		self.cmb_topology = QtGui.QComboBox()
		self.cmb_topology.addItem('Strict (no sibling gaps)', Topology.STRICT)
		self.cmb_topology.addItem('Permissive (any pair)', Topology.PERMISSIVE)

		self.spn_max_stem = QtGui.QDoubleSpinBox()
		self.spn_max_stem.setRange(0., 2000.)
		self.spn_max_stem.setDecimals(0)
		self.spn_max_stem.setSpecialValueText('Auto (0.3 x extent)')
		self.spn_max_stem.setSuffix(' u')
		self.spn_max_stem.setValue(0.)

		self.cmb_mode.currentIndexChanged.connect(lambda: self.redetect())
		self.cmb_topology.currentIndexChanged.connect(lambda: self.redetect())
		self.spn_max_stem.valueChanged.connect(lambda: self.redetect())

		self.txt_report = QtGui.QTextEdit()
		self.txt_report.setReadOnly(True)
		self.txt_report.setMaximumHeight(140)

		lay_detect.addWidget(QtGui.QLabel('Detect:'), 0, 0);	lay_detect.addWidget(self.cmb_mode, 0, 1)
		lay_detect.addWidget(QtGui.QLabel('Topology:'), 1, 0);	lay_detect.addWidget(self.cmb_topology, 1, 1)
		lay_detect.addWidget(QtGui.QLabel('Max stem:'), 2, 0);	lay_detect.addWidget(self.spn_max_stem, 2, 1)
		lay_detect.addWidget(self.txt_report, 3, 0, 1, 2)

		self.box_detect.setLayout(lay_detect)
		lay_main.addWidget(self.box_detect)

		# -- Warp controls (integers; factors are in %)
		lay_controls = TRFlowLayout(spacing=10)

		control_specs = [
			('scale_x',    'scale_x',             (10, 300, 100, 1),    ' %', 'Scale X: new frame width'),
			('scale_y',    'scale_y',             (10, 300, 100, 1),    ' %', 'Scale Y: new frame height'),
			('stem_v',     'stem_vertical_alt',   (25, 300, 100, 1),    ' %', 'Vertical stems: thickness factor'),
			('stem_h',     'stem_horizontal_alt', (25, 300, 100, 1),    ' %', 'Horizontal stems: thickness factor'),
			('counter_x',  'contour_distribute_h',           (10, 500, 100, 1),    ' %', 'Counter X: interior gaps vs side margins'),
			('counter_y',  'contour_distribute_v',           (10, 500, 100, 1),    ' %', 'Counter Y: interior gaps vs top/bottom margins'),
			('gravity_x',  'wave',                (-600, 600, 0, 5),    '',   'Gravity X (x0.01): + moves ink left, - moves ink right'),
			('gravity_y',  'wave',                (-600, 600, 0, 5),    '',   'Gravity Y (x0.01): + moves ink down, - moves ink up'),
			('centroid_x', 'delta_x',             (-500, 500, 0, 1),    ' u', 'Centroid shift X: solve gravity X so the ink centroid moves by this (0 = off)'),
			('centroid_y', 'delta_y',             (-500, 500, 0, 1),    ' u', 'Centroid shift Y: solve gravity Y so the ink centroid moves by this (0 = off)'),
			('min_gap',    'distance',            (0, 500, 0, 1),       ' u', 'Minimum gap after warp'),
		]

		self.ctrl = {}
		self.ctrl_defaults = {}

		for key, icon, values, suffix, tooltip_button in control_specs:
			cpn = TRCustomSpinController(icon, values, suffix, tooltip_button)
			cpn.spin_box.valueChanged.connect(lambda: self.changed())
			lay_controls.addWidget(cpn)
			self.ctrl[key] = cpn
			self.ctrl_defaults[key] = values[2]

		lay_main.addLayout(lay_controls)

		self.__toggle_controls()
		self.__toggle_detect()
		lay_main.addStretch()

		# --- Set styling
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())

	# - Functions -----------------------------------------
	# -- Internal
	def __toggle_controls(self):
		for cpn in self.ctrl.values():
			if self.chk_toggle_controls.isChecked():
				cpn.expand()
			else:
				cpn.contract()

	def __toggle_detect(self):
		self.box_detect.setVisible(self.chk_toggle_detect.isChecked())

	def __data(self, combo):
		return combo.itemData(combo.currentIndex)

	def __value(self, key):
		return float(self.ctrl[key].getValue())

	def __frame(self, core):
		b = core.bounds
		if self.chk_advance.isChecked() and core.advance_width > 0:
			return (0., float(b.y), float(core.advance_width), float(b.ymax))
		return (float(b.x), float(b.y), float(b.xmax), float(b.ymax))

	def __params(self, core, centroid):
		max_stem = self.spn_max_stem.value
		kw = dict(
			scale_x=self.__value('scale_x') / 100., scale_y=self.__value('scale_y') / 100.,
			stem_v=self.__value('stem_v') / 100., stem_h=self.__value('stem_h') / 100.,
			counter_x=self.__value('counter_x') / 100., counter_y=self.__value('counter_y') / 100.,
			gravity_x=self.__value('gravity_x') / 100., gravity_y=self.__value('gravity_y') / 100.,
			align=self.align_codes[self.grp_align.checkedId()],
			frame=self.__frame(core),
			max_stem=max_stem if max_stem > 0 else None,
			min_gap=self.__value('min_gap'),
			handle_mode='anchored' if self.chk_anchored.isChecked() else 'direct',
			detect_mode=self.__data(self.cmb_mode),
			topology=self.__data(self.cmb_topology),
		)

		if centroid is not None:
			if self.__value('centroid_x') != 0.:
				kw['centroid_x'] = centroid[0] + self.__value('centroid_x')
			if self.__value('centroid_y') != 0.:
				kw['centroid_y'] = centroid[1] + self.__value('centroid_y')

		return magic_scale.WarpParams(**kw)

	def __zero_controls(self):
		for key, cpn in self.ctrl.items():
			cpn.blockSignals(True)
			cpn.setValue(self.ctrl_defaults[key])
			cpn.blockSignals(False)

	def __layer_names(self, glyph):
		'''Active layer first (the reference), then the other masthead layers.'''
		active = glyph.layer().name
		names = glyph._prepareLayers(pLayers, compatible=False) if pLayers is not None else [active]
		return [active] + sorted(name for name in names if name != active)

	def __signature(self):
		try:
			glyph = eGlyph()
			return (glyph.name, glyph.layer().name, tuple(self.__layer_names(glyph)))
		except Exception:
			return None

	def __write(self, coords_per_item):
		'''Write coordinates into the FL nodes in place, then notify (Delta style).'''
		for item, coords in zip(self.items, coords_per_item):
			for fl_node, (x, y) in zip(item.fl_nodes, coords):
				fl_node.x = x
				fl_node.y = y

			self.glyph.update(item.name)

		try:
			pWorkspace().getCanvas(True).refreshAll()
		except Exception:
			pass

		if self.live_tool is not None and self.live_tool.alive:
			self.live_tool.panel_wrote()

	def __undo_snapshot(self, what):
		if self.glyph is not None:
			self.glyph.updateObject(self.glyph.fl, '{} | {} {}'.format(app_name, what, self.glyph.name), False)

	def __report(self, lines):
		self.txt_report.setPlainText('\n'.join(lines))

	# -- Actions
	def capture(self, zero_controls=True, snapshot=True):
		'''Snapshot the current glyph: the current state becomes the source.'''
		self.live_ref = None

		try:
			glyph = eGlyph()
		except Exception:
			self.glyph, self.items = None, []
			return False

		items, skipped = [], []

		for name in self.__layer_names(glyph):
			fl_layer = glyph.layer(name)
			fl_contours = glyph.contours(name) if fl_layer is not None else []

			if not fl_contours:
				skipped.append(name)
				continue

			items.append(_Item(name, fl_contours, getattr(fl_layer, 'advanceWidth', 0.)))

		if not items or items[0].name != glyph.layer().name:
			self.glyph, self.items = None, []
			self.__report(['Active layer is empty. Nothing captured.'])
			return False

		# - Compatibility against the reference (node-index refs must line up)
		base = items[0].core.contours
		compatible = [items[0]]

		for item in items[1:]:
			contours = item.core.contours
			if len(contours) != len(base) or any(len(a.nodes) != len(b.nodes) for a, b in zip(contours, base)):
				skipped.append(item.name)
			else:
				compatible.append(item)

		self.glyph, self.items = glyph, compatible
		self.signature = self.__signature()

		if zero_controls:
			self.__zero_controls()

		if snapshot:
			self.__undo_snapshot('Capture')
		self.__detect()

		if skipped:
			warnings.warn('Magic Scale: skipped empty or incompatible layers: {}'.format(', '.join(skipped)), LayerWarning)

		output(0, app_name, 'Glyph: {}; Layers: {}; Captured.'.format(glyph.name, ', '.join(item.name for item in compatible)))
		self.execute()
		return True

	def __detect(self):
		ref = self.items[0]
		ref.restore()
		params = self.__params(ref.core, None)
		self.refs = magic_scale.detect_knot_refs(ref.core.contours, params.frame, params)

	def redetect(self):
		'''Frame or detector settings changed: detect again on the captured source.'''
		if not self.items:
			return

		self.__detect()
		self.execute()

	def changed(self, force=False):
		if not (force or self.chk_live.isChecked()):
			return

		signature = self.__signature()

		if not self.items:
			self.capture(False)		# first touch: keep the value that was just set
			return

		if signature != self.signature:
			self.capture(True)		# glyph or layers switched: Delta-style refresh
			return

		self.execute()

	def execute(self):
		if not self.items:
			if not self.capture(False):
				return

		# - Warp every layer first; write only if all succeed
		results, lines = [], []
		live_ref = None

		for item in self.items:
			item.restore()

			try:
				params = self.__params(item.core, item.centroid)
				report = magic_scale.warp_layer(item.core, params, knot_refs=self.refs)

			except ValueError as e:
				self.__report(['[{}] {}'.format(item.name, e), 'Nothing written.'])
				warnings.warn('Magic Scale: {}: {}'.format(item.name, e), GlyphWarning)
				return

			results.append([(n.x, n.y) for n in item.core.nodes])

			if item is self.items[0]:
				live_ref = (params.frame, report.warp_x, report.warp_y)

			lines.append('[{}] {}'.format(item.name, ', '.join(sorted(report.flags)) or 'ok'))

			for axis, warp in (('X', report.warp_x), ('Y', report.warp_y)):
				lines.append('  {}: {}'.format(axis, ' '.join(kind[0] for kind in warp.kinds)))
				lines.append('    {}'.format(_fmt_knots(warp.src_knots)))
				lines.append('    {}'.format(_fmt_knots(warp.dst_knots)))

			for axis in sorted(report.gravity_solved):
				lines.append('  Centroid {}: gravity {:.2f} -> {:.0f}'.format(
					axis.upper(), report.gravity_solved[axis], report.centroid_achieved[axis]))

		self.live_ref = live_ref
		self.__write(results)
		self.__report(lines)

	def reset(self):
		if not self.items:
			return

		self.__write([item.src for item in self.items])
		self.__report(['Reverted to the captured outline.'])

	def defaults(self):
		self.__zero_controls()
		self.reset()

	def apply(self):
		if not self.items:
			return

		self.__undo_snapshot('Apply')
		self.capture(True)

	# -- Live Edit (canvas) --------------------------------
	def live_edit(self):
		'''Live Edit button: start or stop the canvas controls.'''
		if self.btn_live.isChecked():
			self.live_tool = TRMagicScaleCanvas.start(self)
		else:
			self.live_tool = None
			TRMagicScaleCanvas.stop()

	def live_closed(self):
		'''Close icon on the canvas.'''
		self.btn_live.setChecked(False)
		self.live_edit()

	def live_state(self):
		'''Reference layer state for the canvas, or None if nothing is captured.
		Returns dict: target (glyph, layer), frame, warp_x, warp_y, params.'''
		if not self.items or self.glyph is None or self.live_ref is None:
			return None

		frame, warp_x, warp_y = self.live_ref
		return {'target': (self.glyph.name, self.items[0].name), 'frame': frame,
				'warp_x': warp_x, 'warp_y': warp_y, 'params': self.live_params()}

	def live_params(self):
		'''Canvas-controlled values: factors (1.0 = 100 %) and the align code.'''
		params = {key: self.__value(key) / 100. for key in _LIVE_KEYS}
		params['align'] = self.align_codes[self.grp_align.checkedId()]
		return params

	def live_set(self, values):
		'''Set controls from the canvas (factors, align code) and apply once.'''
		for key, value in values.items():
			if key == 'align':
				for bid, code in self.align_codes.items():
					if code == value and self.grp_align.checkedId() != bid:
						self.grp_align.button(bid).setChecked(True)
				continue

			cpn = self.ctrl[key]
			cpn.blockSignals(True)
			cpn.setValue(int(round(value * 100.)))
			cpn.blockSignals(False)

		self.changed(True)

	def live_capture(self):
		'''Canvas switched to another glyph or layer: capture it (Delta style).'''
		return self.capture(True)

	def live_recapture(self):
		'''Outline edited outside the panel: it becomes the new source. No undo
		snapshot here (that would break FontLab's undo/redo after Ctrl+Z).'''
		return self.capture(True, snapshot=False)

# - Canvas -----------------------------
# Frame points: code -> (sx, sy) side signs; -1 = left/bottom, 0 = middle, +1 = right/top
_FRAME_POINTS = [('TL', -1, 1), ('TM', 0, 1), ('TR', 1, 1), ('RM', 1, 0),
				 ('BR', 1, -1), ('BM', 0, -1), ('BL', -1, -1), ('LM', -1, 0)]
_ALIGN_POINTS = _FRAME_POINTS + [('C', 0, 0)]		# plus 'B' = origin (0, 0)

_CURSORS = {(-1, 1): QtCore.Qt.SizeFDiagCursor, (1, -1): QtCore.Qt.SizeFDiagCursor,
			(1, 1): QtCore.Qt.SizeBDiagCursor, (-1, -1): QtCore.Qt.SizeBDiagCursor,
			(0, 1): QtCore.Qt.SizeVerCursor, (0, -1): QtCore.Qt.SizeVerCursor,
			(1, 0): QtCore.Qt.SizeHorCursor, (-1, 0): QtCore.Qt.SizeHorCursor}

_LIMITS = {'scale': (0.1, 3.), 'stem': (0.25, 3.), 'counter': (0.1, 5.)}

def _side_coord(lo, hi, side):
	return lo if side < 0 else hi if side > 0 else (lo + hi) * .5

def _has_stems(warp):
	return 'ink' in warp.kinds

def _counter_works(warp):
	'''Counter trades interior gaps against margins: it needs both.'''
	inks = [i for i, kind in enumerate(warp.kinds) if kind == 'ink']
	return len(inks) >= 2 and 'gap' in (warp.kinds[0], warp.kinds[-1])

class TRMagicScaleCanvas(co.CanvasOverlay):
	'''Magic Scale controls on the glyph canvas, driving TRMagicScalePanel.

	Frame quad (8)  scale X / Y about the transform origin
	Inner quad (8)  counter X / Y; centred on the stem ring, its size shows
	                the value (ring + a band growing with counter)
	Stem ring (4)   left / right: vertical stems; top / bottom: horizontal
	Origin cross    snaps to the 9 frame points or the origin (0, 0)
	(x)             close (unchecks Live Edit)

	All values go through the panel (live_set); the panel warps and writes.
	The ring and inner quad scale with the frame.
	'''
	NAME = 'tr_magic_scale'
	PAD_PX = 16.				# frame quad sits this far outside the outline frame
	STEM_RING_PX = (40., 110.)	# stem ring radius range on screen (before following the scale)
	COUNTER_BAND = .6			# inner quad = ring + this * ring at counter 1 ...
	COUNTER_GAMMA = .5			# ... with the band growing as counter ** gamma
	CLOSE_OFFSET_PX = 22.
	PUSH_INTERVAL = .033		# seconds between live applies during a drag

	def __init__(self, panel):
		co.CanvasOverlay.__init__(self)
		self.panel = panel
		self.st = None				# panel.live_state() (params overridden during a drag)
		self._press = None			# (params, warp_x, warp_y, ring_px) at drag start
		self._drag_params = None	# params being dragged (ahead of the panel)
		self._pending = None		# params waiting for the throttle
		self._origin_view = None	# cursor while dragging the origin cross
		self._throttle = om.Throttle(self.PUSH_INTERVAL)
		self._build_handles()

	# - Panel link ----------------------
	def _refresh(self):
		try:
			st = self.panel.live_state()
		except Exception:
			st = None
			co._log.exception('{}.live_state'.format(self.NAME))

		if st is not None and self._drag_params is not None:
			st = dict(st)
			st['params'] = dict(self._drag_params)

		self.st = st
		self._update_enabled()

	def _push(self, params, now=False):
		'''Send params to the panel (throttled unless now).'''
		if now or self._throttle.ready():
			self._pending = None
			try:
				self.panel.live_set(params)
			except Exception:
				co._log.exception('{}.live_set'.format(self.NAME))
		else:
			self._pending = dict(params)

	def panel_wrote(self):
		'''Called by the panel after every write: our own edit, not an outside one.'''
		self.accept_geometry()
		self._refresh()
		self.request_repaint()

	def _panel_alive(self):
		try:
			co.qv(self.panel, 'objectName')
			return True
		except Exception:
			return False

	# - Handles -------------------------
	def _build_handles(self):
		H = co.Handle
		handles = []

		for code, sx, sy in _FRAME_POINTS:
			shape = om.SHAPE_SQUARE if sx and sy else om.SHAPE_BAR_V if sx else om.SHAPE_BAR_H
			axis = om.AXIS_XY if sx and sy else om.AXIS_X if sx else om.AXIS_Y
			handles.append(H('scale_' + code, self._scale_anchor(sx, sy), shape, 6., axis, _CURSORS[(sx, sy)], 'primary',
							 tooltip='Scale {}'.format('X / Y' if sx and sy else 'X' if sx else 'Y')))

		for code, sx, sy in _FRAME_POINTS:
			axis = om.AXIS_XY if sx and sy else om.AXIS_X if sx else om.AXIS_Y
			handles.append(H('counter_' + code, self._counter_anchor(sx, sy), om.SHAPE_CIRCLE, 5., axis, _CURSORS[(sx, sy)], 'secondary',
							 tooltip='Counter {}'.format('X / Y' if sx and sy else 'X' if sx else 'Y')))

		for code, sx, sy in (('T', 0, 1), ('R', 1, 0), ('B', 0, -1), ('L', -1, 0)):
			handles.append(H('stem_' + code, self._stem_anchor(sx, sy), om.SHAPE_CIRCLE, 5.5, om.AXIS_X if sx else om.AXIS_Y,
							 _CURSORS[(sx, sy)], 'stem', tooltip='Vertical stems' if sx else 'Horizontal stems'))

		handles.append(H('origin', self._origin_anchor, om.SHAPE_CIRCLE, 7., om.AXIS_XY, QtCore.Qt.CrossCursor, 'primary', tooltip='Transform origin'))
		handles.append(H('close', self._close_anchor, om.SHAPE_CIRCLE, 8., om.AXIS_XY, QtCore.Qt.PointingHandCursor, 'muted', tooltip='Close Live Edit'))
		self.handles = handles
		self.handle = dict((h.key, h) for h in handles)

	def _ready(self):
		return self.st is not None and self.target == self.st['target']

	def _warped_frame(self):
		wx, wy = self.st['warp_x'], self.st['warp_y']
		return (wx.dst_knots[0], wy.dst_knots[0], wx.dst_knots[-1], wy.dst_knots[-1])

	def _ring_px(self, mapping):
		'''Stem ring radius (view px): sized from the source frame (clamped on
		screen), then following the scale of the frame (uniformly).'''
		frame = self.st['frame']
		w, h = frame[2] - frame[0], frame[3] - frame[1]
		x0, y0, x1, y1 = self._warped_frame()
		follow = min(x1 - x0, y1 - y0) / min(w, h) if min(w, h) > 0 else 1.
		lo, hi = self.STEM_RING_PX
		return om.clamp(.2 * min(w, h) * mapping.px_per_unit, lo, hi) * max(follow, 0.)

	def _view_center(self, mapping):
		x0, y0, x1, y1 = self._warped_frame()
		return mapping.to_view((x0 + x1) * .5, (y0 + y1) * .5)

	def _scale_anchor(self, sx, sy):
		def anchor(mapping):
			if not self._ready(): return None
			x0, y0, x1, y1 = self._warped_frame()
			v = mapping.to_view(_side_coord(x0, x1, sx), _side_coord(y0, y1, sy))
			return (v.x() + sx * self.PAD_PX, v.y() - sy * self.PAD_PX)
		return anchor

	def _counter_band(self, ring, counter):
		'''Whitespace band (view px) between the stem ring and the inner quad.'''
		return ring * self.COUNTER_BAND * counter ** self.COUNTER_GAMMA

	def _counter_view_rect(self, mapping):
		'''Inner quad: centred on the stem ring and always enclosing it.'''
		c = self._view_center(mapping)
		ring = self._ring_px(mapping)
		pr = self.st['params']
		hx = ring * pr['stem_v'] + self._counter_band(ring, pr['counter_x'])
		hy = ring * pr['stem_h'] + self._counter_band(ring, pr['counter_y'])
		return QtCore.QRectF(c.x() - hx, c.y() - hy, 2. * hx, 2. * hy)

	def _counter_anchor(self, sx, sy):
		def anchor(mapping):
			if not self._ready(): return None
			r = self._counter_view_rect(mapping)
			return (_side_coord(r.left(), r.right(), sx), _side_coord(r.bottom(), r.top(), sy))
		return anchor

	def _stem_anchor(self, sx, sy):
		def anchor(mapping):
			if not self._ready(): return None
			c = self._view_center(mapping)
			r = self._ring_px(mapping)
			pr = self.st['params']
			return (c.x() + sx * r * pr['stem_v'], c.y() - sy * r * pr['stem_h'])
		return anchor

	def _origin_anchor(self, mapping):
		if not self._ready(): return None
		if self._origin_view is not None:
			return (self._origin_view.x(), self._origin_view.y())
		return self._align_point(mapping, self.st['params']['align'])

	def _close_anchor(self, mapping):
		if not self._ready():
			return (16., 16.)		# next to the banner
		x0, y0, x1, y1 = self._warped_frame()
		v = mapping.to_view(x1, y1)
		return (v.x() + self.PAD_PX + self.CLOSE_OFFSET_PX, v.y() - self.PAD_PX - self.CLOSE_OFFSET_PX)

	def _align_codes(self):
		return [code for code, _sx, _sy in _ALIGN_POINTS] + ['B']

	def _align_point(self, mapping, code):
		if code == 'B':
			v = mapping.to_view(0., 0.)
			return (v.x(), v.y())
		x0, y0, x1, y1 = self._warped_frame()
		for c, sx, sy in _ALIGN_POINTS:
			if c == code:
				v = mapping.to_view(_side_coord(x0, x1, sx), _side_coord(y0, y1, sy))
				return (v.x(), v.y())
		return None

	def _update_enabled(self):
		'''Controls that would do nothing on this glyph are shown disabled.'''
		if self.st is None: return
		wx, wy = self.st['warp_x'], self.st['warp_y']
		counter_x, counter_y = _counter_works(wx), _counter_works(wy)

		for code, sx, sy in _FRAME_POINTS:
			self.handle['counter_' + code].enabled = bool((sx and counter_x) or (sy and counter_y))
		self.handle['stem_L'].enabled = self.handle['stem_R'].enabled = _has_stems(wx)
		self.handle['stem_T'].enabled = self.handle['stem_B'].enabled = _has_stems(wy)

	# - Overlay hooks -------------------
	def on_attach(self):
		self._refresh()

	def on_target_changed(self, mapping):
		self._refresh()
		if self.target is not None and (self.st is None or self.target != self.st['target']):
			try:
				self.panel.live_capture()		# glyph or layer switched: capture it (Delta style)
			except Exception:
				co._log.exception('{}.live_capture'.format(self.NAME))
			self._refresh()
		self.request_repaint()

	def on_geometry_changed(self):
		if self.drag is None and self._ready():
			try:
				self.panel.live_recapture()		# edited with FontLab's tools (or undo)
			except Exception:
				co._log.exception('{}.live_recapture'.format(self.NAME))
			self._refresh()
			self.request_repaint()

	def on_tick(self):
		if not self._panel_alive():
			type(self).stop()					# the panel is gone
			return
		if self._pending is not None:
			self._push(self._pending, now=True)
		elif self.drag is None:
			self._refresh()						# pick up changes made in the panel

	def on_handle_click(self, handle, drag):
		if handle.key == 'close':
			if self._panel_alive():
				self.panel.live_closed()
			else:
				type(self).stop()

	def on_drag_start(self, handle, drag):
		params = dict(self.st['params'])
		self._press = (params, self.st['warp_x'], self.st['warp_y'], self._ring_px(self.mapping))
		self._drag_params = dict(params)

	def on_drag_move(self, handle, drag):
		key = handle.key
		if key == 'close' or self._press is None: return
		if key == 'origin':
			self._origin_view = drag.cur_view
			return

		params0, wx0, wy0, ring = self._press
		params = dict(params0)
		group, code = key.split('_')

		if group == 'scale':
			sx, sy = self._sides(code)
			dx, dy = drag.delta_font
			if sx: params['scale_x'] = self._drag_scale('x', sx, dx, params0, wx0)
			if sy: params['scale_y'] = self._drag_scale('y', sy, dy, params0, wy0)

		elif group == 'counter':
			sx, sy = self._sides(code)
			dvx, dvy = drag.delta_view
			if sx and _counter_works(wx0):
				params['counter_x'] = self._drag_counter('x', dvx * sx, params0, ring)
			if sy and _counter_works(wy0):
				params['counter_y'] = self._drag_counter('y', -dvy * sy, params0, ring)

		elif group == 'stem':
			lo, hi = _LIMITS['stem']
			dvx, dvy = drag.delta_view
			if code in ('L', 'R'):
				out_px = dvx if code == 'R' else -dvx
				params['stem_v'] = om.clamp(params0['stem_v'] + out_px / ring, lo, hi)
			else:
				out_px = -dvy if code == 'T' else dvy
				params['stem_h'] = om.clamp(params0['stem_h'] + out_px / ring, lo, hi)

		self._drag_params = params
		self.st['params'] = dict(params)
		self._push(params)

	def on_drag_end(self, handle, drag):
		key = handle.key
		if key == 'close' or self._press is None: return
		if key == 'origin':
			self._drag_params['align'] = self._nearest_align(drag.cur_view)
			self._origin_view = None
		else:
			self.on_drag_move(handle, drag)

		params = self._drag_params
		self._press = self._drag_params = None
		self._push(params, now=True)
		self._refresh()

	def on_drag_cancel(self, handle, drag):
		self._origin_view = None
		if self._press is not None:
			params = self._press[0]
			self._press = self._drag_params = None
			self._push(params, now=True)
		self._refresh()

	# - Drag mappings -------------------
	@staticmethod
	def _sides(code):
		for c, sx, sy in _FRAME_POINTS:
			if c == code: return sx, sy
		return 0, 0

	def _anchor_coord(self, axis, params):
		'''Coordinate of the transform origin on this axis; the warp keeps it
		fixed in the warped frame too.'''
		if params['align'] == 'B':
			return 0.
		frame = self.st['frame']
		for c, sx, sy in _ALIGN_POINTS:
			if c == params['align']:
				if axis == 'x': return _side_coord(frame[0], frame[2], sx)
				return _side_coord(frame[1], frame[3], sy)
		return _side_coord(frame[0], frame[2], 0) if axis == 'x' else _side_coord(frame[1], frame[3], 0)

	def _drag_scale(self, axis, side, delta, params0, warp0):
		'''New scale so the dragged frame edge lands under the cursor.'''
		key = 'scale_' + axis
		edge0 = warp0.dst_knots[-1] if side > 0 else warp0.dst_knots[0]
		ratio = om.scale_from_drag(self._anchor_coord(axis, params0), edge0, edge0 + delta)
		return om.clamp(params0[key] * ratio, *_LIMITS['scale'])

	def _drag_counter(self, axis, out_px, params0, ring):
		'''New counter so the dragged inner-quad edge lands under the cursor:
		inverts band = ring * COUNTER_BAND * counter ** COUNTER_GAMMA.'''
		unit = ring * self.COUNTER_BAND
		band = max(self._counter_band(ring, params0['counter_' + axis]) + out_px, 1e-6)
		return om.clamp((band / unit) ** (1. / self.COUNTER_GAMMA), *_LIMITS['counter'])

	def _nearest_align(self, view_point):
		best, best_d = self.st['params']['align'], None
		for code in self._align_codes():
			x, y = self._align_point(self.mapping, code)
			d = (x - view_point.x())**2 + (y - view_point.y())**2
			if best_d is None or d < best_d:
				best, best_d = code, d
		return best

	# - Painting ------------------------
	def paint_overlay(self, p, mapping):
		c = self.colors

		if not self._ready():
			self.draw_label(p, QtCore.QPointF(32., 16.), '{}: nothing captured on this layer'.format(app_name), 'LM', offset=0.)
			return

		x0, y0, x1, y1 = self._warped_frame()
		frame = mapping.rect_to_view(x0, y0, x1, y1).adjusted(-self.PAD_PX, -self.PAD_PX, self.PAD_PX, self.PAD_PX)

		# - Frame quad (scale)
		p.setPen(co.cosmetic_pen(c['active'], 1.))
		p.setBrush(co.solid_brush(c['active'], 12))
		p.drawRoundedRect(frame, 6., 6.)

		# - Inner quad (counter)
		p.setPen(co.cosmetic_pen(c['frame'], 1., QtCore.Qt.DashLine))
		p.setBrush(co.no_brush())
		p.drawRect(self._counter_view_rect(mapping))

		# - Stem ring
		center = self._view_center(mapping)
		ring = self._ring_px(mapping)
		pr = self.st['params']
		p.setPen(co.cosmetic_pen(c['stem'], 1., QtCore.Qt.DashLine))
		p.setBrush(co.no_brush())
		co.draw_ellipse(p, center.x(), center.y(), ring * pr['stem_v'], ring * pr['stem_h'])

		# - Origin snap targets while dragging the cross
		if self._origin_view is not None:
			nearest = self._nearest_align(self._origin_view)
			for code in self._align_codes():
				x, y = self._align_point(mapping, code)
				hot = code == nearest
				p.setPen(co.cosmetic_pen(c['active'], 1.5 if hot else 1.))
				p.setBrush(co.solid_brush(c['active'], 255 if hot else 60))
				co.draw_ellipse(p, x, y, 4., 4.)

		# - Values under the frame
		hud = 'W {:.0f}%  H {:.0f}%   stem V {:.0f}%  H {:.0f}%   counter X {:.0f}%  Y {:.0f}%   origin {}'.format(
			pr['scale_x'] * 100, pr['scale_y'] * 100, pr['stem_v'] * 100, pr['stem_h'] * 100,
			pr['counter_x'] * 100, pr['counter_y'] * 100, pr['align'])
		self.draw_label(p, frame.bottomLeft(), hud, 'TL', offset=10.)

	def paint_handle(self, p, handle, x, y, hot):
		c = self.colors
		if handle.key == 'origin':
			r = handle.radius + (1.5 if hot else 0.)
			p.setPen(co.cosmetic_pen(c['active'], 2. if hot else 1.5))
			p.setBrush(co.solid_brush(c['label_bg']))
			co.draw_ellipse(p, x, y, r * .55, r * .55)
			p.drawLine(QtCore.QPointF(x - r * 1.6, y), QtCore.QPointF(x + r * 1.6, y))
			p.drawLine(QtCore.QPointF(x, y - r * 1.6), QtCore.QPointF(x, y + r * 1.6))
			return True

		if handle.key == 'close':
			r = handle.radius + (1. if hot else 0.)
			p.setPen(co.cosmetic_pen(c['error'] if hot else c['muted'], 1.))
			p.setBrush(co.solid_brush(c['label_bg']))
			co.draw_ellipse(p, x, y, r, r)
			p.setPen(co.cosmetic_pen(c['error'] if hot else c['text'], 1.5))
			k = r * .45
			p.drawLine(QtCore.QPointF(x - k, y - k), QtCore.QPointF(x + k, y + k))
			p.drawLine(QtCore.QPointF(x - k, y + k), QtCore.QPointF(x + k, y - k))
			return True

		return False

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)

		lay_main = QtGui.QVBoxLayout()
		lay_main.setContentsMargins(0, 0, 0, 0)

		# - Add widgets to main dialog
		lay_main.addWidget(TRMagicScalePanel())

		# - Build
		self.setLayout(lay_main)

# - Test ----------------------
if __name__ == '__main__':
	magic_scale_panel = tool_tab()
	magic_scale_panel.setWindowTitle('%s %s' %(app_name, app_version))
	magic_scale_panel.setGeometry(100, 100, 300, 400)
	magic_scale_panel.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
	magic_scale_panel.show()
