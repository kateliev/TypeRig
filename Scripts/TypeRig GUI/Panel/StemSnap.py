#FLM: TR: Stem Snap
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
# Two methods:
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
# NOTE: single glyph mode. The panel works on the current glyph only,
# whatever the masthead glyph mode (window / selection). Multi-glyph
# processing is planned for a later update.

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import time
import traceback

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import ps_master_stems
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.tr.objects.contour import trContour, _build_fl_contour
from typerig.proxy.tr.objects.shape import _build_fl_shape

from typerig.core.objects.shape import Shape
from typerig.core.algo._width_audit import WidthTarget, WidthAllowlist
from typerig.core.algo.stem_snap import snap_stems, StemDetector, Axis, DetectMode, Topology, Cascade
from typerig.core.algo.stroke_snap import snap_strokes, StrokeType

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, False, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Stem Snap', '0.1'

DEFAULT_TOL = 5.		# capture band, units (or %)
DIAGONAL_TYPES = (StrokeType.PIE, StrokeType.NA, StrokeType.DIAGONAL, StrokeType.DOT)

# Popups: (key, label, [(title, value), ...], default index, tooltip)
METHODS = [
	('Stems: H/V nodes (exact)',     'stems'),
	('Strokes: contour width (MAT)', 'strokes'),
]

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
	'''Italic angle of the master a layer belongs to; the current master
	for layers that are not masters. The current master is restored.'''
	back_master = package.master

	if layer != back_master and layer in list(package.masters):
		package.setMaster(layer)

	try:
		return float(package.italicAngle_value or 0.)
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

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		self.__build_targets()
		self.__build_method()
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
		lay.addWidget(text_button('Snap', 'Snap captured stems / strokes to their targets on every layer in scope.',
				lambda: self.on_snap(True)), 2, 0, 1, 6)

		box.setLayout(lay)
		self.lay_main.addWidget(box)

	# - Options -----------------------------------------
	def method(self):
		return METHODS[self.cmb_method.currentIndex][1]

	def on_method(self):
		self.stk_options.setCurrentIndex(0 if self.method() == 'stems' else 1)

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

	def collect(self, glyph):
		'''([_LayerItem], [notes]) plus the selection on the active layer:
		(set of (contour, node), set of contour indices).'''
		items, notes = [], []

		for name in self.layer_names(glyph):
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

		stems = self.method() == 'stems'
		if stems and self.checked('selected') and not sel_nodes:
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
			if not (v or h or (d and not stems)):
				no_targets.append(item.name)
				continue

			try:
				if stems:
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
		if select:
			lines.append('Selected {} {} to snap on "{}".'.format(total, what, active))
			pWorkspace().getCanvas(True).refreshAll()

		elif apply:
			if written:
				for name in written:
					glyph.update(name)
				glyph.updateObject(glyph.fl, '{} | {} @ {}'.format(app_name, glyph.name, '; '.join(written)), False)
			lines.append('Snapped {} {} ({:.2f}s).'.format(total, what, time.time() - started))

		else:
			lines.append('Analyze: {} {} to snap; nothing changed ({:.2f}s).'.format(total, what, time.time() - started))

		self.say(*lines)

	# -- Stems
	def snap_stems(self, glyph, package, item, v, h, sel_nodes, apply):
		detector = StemDetector(mode=self.choice('detect'),
								topology=Topology.STRICT if self.checked('strict') else Topology.PERMISSIVE)

		report = snap_stems(item.contours, self.allowlist({Axis.V: v, Axis.H: h}),
							detector=detector,
							axis=self.choice('axis'),
							anchor=self.choice('anchor'),
							scope=self.choice('cascade'),
							italic_angle=_italic_angle(package, item.name) if self.checked('italic') else 0.,
							selected=sel_nodes if self.checked('selected') else None,
							round_ints=self.checked('round'),
							pin_extremes=self.checked('pin'),
							apply=apply)

		for k in report.captured:
			c = k.source
			print('    {} {:>7.2f} -> {:g} ({:+.2f})  faces {:.1f} / {:.1f}  contours {} / {}'.format(
				k.key, k.measured, k.target.value, k.delta,
				c.edge_a.coord, c.edge_b.coord, c.edge_a.contour_idx, c.edge_b.contour_idx))

		on_target = len(report.captured) - len(report.moved)
		line = '{} | {}: {} stem(s): {} to snap, {} on target, {} outside bands'.format(
			glyph.name, item.name, len(report.candidates), len(report.moved), on_target, len(report.out_of_band))

		# write: (contours, only these indices or None = all, separated); select reads report.nodes()
		return line, len(report.moved), (item.contours, None, False, report)

	# -- Strokes
	def snap_strokes(self, glyph, item, v, h, d, sel_contours, apply):
		keyed = {StrokeType.VERTICAL: v, StrokeType.HORIZONTAL: h}
		keyed.update({t: d for t in DIAGONAL_TYPES})

		report = snap_strokes(item.contours, self.allowlist(keyed),
							  match_on=self.choice('match'),
							  mat_quality=self.choice('quality'),
							  separate=self.checked('separate'),
							  selected=sel_contours if self.checked('s_selected') else None,
							  round_ints=self.checked('s_round'),
							  apply=apply)

		for m in report.measurements:
			print('    {:<10} axis {:5.1f} deg  width min/med/max {:.1f} / {:.1f} / {:.1f}'.format(
				m.stroke_type, m.axis_angle_deg, m.width_min, m.width_median, m.width_max))

		for k in report.captured:
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

		if self.method() == 'stems':
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
