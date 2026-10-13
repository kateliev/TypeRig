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

	def __undo_snapshot(self, what):
		if self.glyph is not None:
			self.glyph.updateObject(self.glyph.fl, '{} | {} {}'.format(app_name, what, self.glyph.name), False)

	def __report(self, lines):
		self.txt_report.setPlainText('\n'.join(lines))

	# -- Actions
	def capture(self, zero_controls=True):
		'''Snapshot the current glyph: the current state becomes the source.'''
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

	def changed(self):
		if not self.chk_live.isChecked():
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

			lines.append('[{}] {}'.format(item.name, ', '.join(sorted(report.flags)) or 'ok'))

			for axis, warp in (('X', report.warp_x), ('Y', report.warp_y)):
				lines.append('  {}: {}'.format(axis, ' '.join(kind[0] for kind in warp.kinds)))
				lines.append('    {}'.format(_fmt_knots(warp.src_knots)))
				lines.append('    {}'.format(_fmt_knots(warp.dst_knots)))

			for axis in sorted(report.gravity_solved):
				lines.append('  Centroid {}: gravity {:.2f} -> {:.0f}'.format(
					axis.upper(), report.gravity_solved[axis], report.centroid_achieved[axis]))

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
