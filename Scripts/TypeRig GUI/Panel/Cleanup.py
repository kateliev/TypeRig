#FLM: TR: Cleanup
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 	(http://www.kateliev.com)
# (C) TypeRig 					(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Outline Cleanup: remove redundant nodes and debris from glyph
# outlines. All geometry runs in TypeRig core
# (typerig.core.algo.outline_cleanup); this module is the FontLab
# shell. Port of the TypeRig-Glyphs Cleanup panel (v0.1), which came
# from the BlackOps demo dialog TR-Outline-Cleanup.py.
#
# Contours of the plain elements of each layer in scope are ejected,
# cleaned one contour at a time and mounted back: in place when the
# node types are unchanged, rebuilt inside their element otherwise.
# A contour that is dropped (tiny area) is removed from its element;
# an element left without contours is removed from the layer.
#
# Layers follow the masthead (active / masters / selected layers);
# the active layer comes first and holds the selection. "Synchronize
# layers" applies when more than one layer is in scope. Glyphs follow
# the masthead glyph mode (glyph / window / selection); Show Locks
# works on the current glyph only.
#
# Groups, components and shared (referenced) elements are never
# touched; groups and shared elements are reported.
#
# Differences from the Glyphs panel:
#   - Output curves can be cubic, quadratic or same as input (auto),
#     with a quadratic tolerance: FontLab keeps TrueType curves.
#     Quadratic output needs fontTools (cu2qu).
#   - "Font italic" flips the FontLab italic angle sign (FL stores a
#     right lean as negative; core expects + = right lean).

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import time
import traceback

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.tr.objects.contour import trContour, _build_fl_contour

from typerig.core.algo.outline_cleanup import (
	clean, locked_nodes, contour_deviation, CleanOptions, IncompatibleMasters
)

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, False, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Cleanup', '0.1'

DEFAULTS = CleanOptions()
OUTPUTS = ('cubic', 'quad', 'auto')

# (key, label, CleanOptions field, low, high, step, decimals, tooltip)
TOLERANCES = (
	('fit',       'Fit:',       'fit_tol',          0., 50.,    .25, 2, 'Max distance between the source and the simplified outline.'),
	('point',     'Point:',     'eps_point',        0., 10.,    .1,  2, 'Two on-curves closer than this are merged.'),
	('handle',    'Handle:',    'eps_handle',       0., 10.,    .1,  2, 'Handles shorter than this are retracted; a cubic with both retracted becomes a line.'),
	('collinear', 'Collinear:', 'eps_collinear',    0., 10.,    .05, 2, 'Max distance of a point from a line to count as on it\n(collinear nodes, flat curves).'),
	('area',      'Min. area:', 'min_contour_area', 0., 10000., 1.,  1, 'Contours with a smaller area (square units) are dropped.'),
	('quad',      'Quadratic:', 'quad_tol',         0., 10.,    .1,  2, 'Max error of the cubic -> TrueType conversion (quadratic output).'),
)

ANGLES = (
	('corner', 'Corner:', 'corner_angle', 0.,   90., .5, 1, 'In/out tangent difference above this (deg) is a corner: never removed.'),
	('hv',     'H/V:',    'hv_angle',     0.,   10., .1, 2, 'Tangents and handles this close (deg) to horizontal/vertical count as H/V and are locked.'),
	('italic', 'Italic:', 'italic_angle', -45., 45., .5, 1, 'Italic angle (deg, + leans right): H/V and extremum tests run in the upright frame.'),
)

# (key, title, default, tooltip)
SCOPE_CHECKS = (
	('sync',     'Synchronize layers', True,  'Checked: decide every removal for all layers in scope at once (layers must be compatible).\nUnchecked: clean each layer on its own. Use it to make near-identical but\nincompatible masters compatible (stray duplicate nodes and the like).'),
	('selected', 'Selected contours',  False, 'Clean only contours that have a selected node on the active layer\n(other layers: the contours with the same index).'),
	('lock_sel', 'Lock selected',      False, 'Selected on-curve nodes (active layer) are never removed or moved.\nSynchronized: the lock holds in all layers.'),
	('upm',      'Scale to UPM',       True,  'Tolerances are given for 1000 UPM and scaled to the font UPM.'),
)

# (key, title, CleanOptions field, tooltip)
OPTION_CHECKS = (
	('extrema', 'Keep extrema',     'keep_extrema',     'Lock x/y extrema nodes, and never let a merge create a new extremum.'),
	('inflect', 'Keep inflections', 'keep_inflections', 'Lock nodes where the curvature changes sign.'),
	('round',   'Round',            'round_ints',       'Round the result to integers and re-clean what rounding breaks.'),
)

# - Helpers ----------------------------
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

def _types(contour):
	return [node.type for node in contour.nodes]

class _LayerItem(object):
	'''One layer: its plain elements, their FL contours (flat, in element
	order) and core contours ejected from them in the same order.'''
	def __init__(self, name, fl_layer, shapes):
		self.name = name
		self.fl_layer = fl_layer
		self.shapes = shapes
		self.fl_contours = [list(shape.contours) for shape in shapes]
		self.contours = [trContour(contour).eject() for contours in self.fl_contours for contour in contours]

# - Panel ------------------------------
class TRCleanupPanel(QtGui.QWidget):
	def __init__(self):
		super(TRCleanupPanel, self).__init__()

		# - Init
		self.spins = {}		# key -> (QDoubleSpinBox, CleanOptions field)
		self.checks = {}	# key -> (QCheckBox, default)

		# - Layout
		self.lay_main = QtGui.QVBoxLayout()
		self.__build_scope()
		self.__build_grid('Tolerances (units @ 1000 UPM):', TOLERANCES)
		self.__build_angles()
		self.__build_actions()

		self.txt_report = QtGui.QTextEdit()
		self.txt_report.setReadOnly(True)
		self.txt_report.setMaximumHeight(120)
		self.txt_report.setToolTip('Last result. Per-glyph details: Output panel.')
		self.lay_main.addWidget(self.txt_report)

		self.lay_main.addStretch()
		self.setLayout(self.lay_main)

	# - Build -------------------------------------------
	def __box(self):
		box = QtGui.QGroupBox()
		box.setObjectName('box_group')
		lay = QtGui.QGridLayout()
		box.setLayout(lay)
		self.lay_main.addWidget(box)
		return lay

	def __check(self, key, title, value, tooltip):
		chk = QtGui.QCheckBox(title)
		chk.setChecked(value)
		chk.setToolTip(tooltip)
		self.checks[key] = (chk, value)
		return chk

	def __spin(self, key, opt, low, high, step, decimals, tooltip):
		spn = QtGui.QDoubleSpinBox()
		spn.setRange(low, high)
		spn.setSingleStep(step)
		spn.setDecimals(decimals)
		spn.setValue(getattr(DEFAULTS, opt))
		spn.setToolTip(tooltip)
		self.spins[key] = (spn, opt)
		return spn

	def __spin_grid(self, lay, row, rows):
		for i, (key, label, opt, low, high, step, decimals, tooltip) in enumerate(rows):
			col = (i % 2) * 2
			lay.addWidget(QtGui.QLabel(label), row + i // 2, col)
			lay.addWidget(self.__spin(key, opt, low, high, step, decimals, tooltip), row + i // 2, col + 1)
		return row + (len(rows) + 1) // 2

	def __build_scope(self):
		lay = self.__box()
		lay.addWidget(QtGui.QLabel('Scope (layers and glyphs: masthead):'), 0, 0, 1, 4)
		for i, (key, title, value, tooltip) in enumerate(SCOPE_CHECKS):
			lay.addWidget(self.__check(key, title, value, tooltip), 1 + i // 2, (i % 2) * 2, 1, 2)

	def __build_grid(self, title, rows):
		lay = self.__box()
		lay.addWidget(QtGui.QLabel(title), 0, 0, 1, 4)
		self.__spin_grid(lay, 1, rows)

	def __build_angles(self):
		lay = self.__box()
		lay.addWidget(QtGui.QLabel('Angles and locks:'), 0, 0, 1, 4)
		row = self.__spin_grid(lay, 1, ANGLES)

		# - "Font italic" next to the Italic spin (3rd item: row 2, column 0)
		lay.addWidget(text_button('Font italic', 'Take the italic angle from the current master.',
				lambda: self.on_font_italic()), row - 1, 2, 1, 2)

		for i, (key, title, opt, tooltip) in enumerate(OPTION_CHECKS):
			lay.addWidget(self.__check(key, title, getattr(DEFAULTS, opt), tooltip), row + i // 2, (i % 2) * 2, 1, 2)
		row += (len(OPTION_CHECKS) + 1) // 2

		self.cmb_output = QtGui.QComboBox()
		self.cmb_output.addItems(['Cubic (PostScript)', 'Quadratic (TrueType)', 'Same as input'])
		self.cmb_output.setCurrentIndex(OUTPUTS.index(DEFAULTS.output))
		self.cmb_output.setToolTip('Output curves. Cubic: PostScript curves (default).\n'
				'Quadratic / same as input (on TrueType contours): via cu2qu, needs fontTools.')
		lay.addWidget(QtGui.QLabel('Curves:'), row, 0)
		lay.addWidget(self.cmb_output, row, 1, 1, 3)

	def __build_actions(self):
		lay = self.__box()
		lay.addWidget(QtGui.QLabel('Actions:'), 0, 0, 1, 6)
		lay.addWidget(text_button('Analyze', 'Dry run of the full cleanup: report node counts and deviation, change nothing.',
				lambda: self.on_clean(simplify=True, dry_run=True)), 1, 0, 1, 2)
		lay.addWidget(text_button('Show Locks', 'Select the nodes the simplifier will keep (corners, junctions,\n'
				'extrema, H/V handles, caller locks) on the active layer of the current glyph.',
				lambda: self.on_locks()), 1, 2, 1, 2)
		lay.addWidget(text_button('Defaults', 'Reset all options to their defaults.',
				lambda: self.on_reset()), 1, 4, 1, 2)
		lay.addWidget(text_button('Fix Degeneracies', 'Degeneracy passes only: zero segments, coincident nodes, zero handles,\n'
				'flat curves, collinear nodes, spikes, tiny contours. No curve fitting.',
				lambda: self.on_clean(simplify=False, dry_run=False)), 2, 0, 1, 6)
		lay.addWidget(text_button('Clean && Simplify', 'Full pipeline: degeneracies, then remove every smooth node the outline\n'
				'does not need within the fit tolerance (Levien / Schneider refit).',
				lambda: self.on_clean(simplify=True, dry_run=False)), 3, 0, 1, 6)

	# - Options -----------------------------------------
	def checked(self, key):
		return self.checks[key][0].isChecked()

	def options(self, glyph, simplify=True):
		kwargs = {opt: float(spn.value) for spn, opt in self.spins.values()}
		kwargs.update({opt: self.checked(key) for key, _, opt, _ in OPTION_CHECKS})
		index = self.cmb_output.currentIndex
		output_mode = OUTPUTS[index if 0 <= index < len(OUTPUTS) else 0]
		opts = CleanOptions(output=output_mode, simplify=simplify, **kwargs)

		if self.checked('upm'):
			opts = opts.for_upm(float(glyph.package.upm))
		return opts

	def on_reset(self):
		for spn, opt in self.spins.values():
			spn.setValue(getattr(DEFAULTS, opt))
		for chk, value in self.checks.values():
			chk.setChecked(value)
		self.cmb_output.setCurrentIndex(OUTPUTS.index(DEFAULTS.output))
		self.say('Defaults restored.')

	def on_font_italic(self):
		'''Italic angle of the current master. FontLab stores a right lean
		as a negative angle; core expects + = right lean: flip the sign.'''
		try:
			glyph = eGlyph()
			angle = -float(glyph.package.italicAngle_value or 0.)
		except Exception:
			self.say('No current font.')
			return
		self.spins['italic'][0].setValue(angle)

	# - Messages ----------------------------------------
	def say(self, *lines):
		for line in lines:
			print('{}: {}'.format(app_name, line))
		self.txt_report.setPlainText('\n'.join(lines))

	# - Collect -----------------------------------------
	def layer_names(self, glyph):
		'''Masthead layers, the active one first (it holds the selection).'''
		active = glyph.layer().name
		names = glyph._prepareLayers(pLayers, compatible=False) if pLayers is not None else [active]
		names = sorted(names or [active])
		return [active] + [n for n in names if n != active] if active in names else names

	def synchronized(self, items):
		return len(items) > 1 and self.checked('sync')

	def collect(self, glyph):
		'''Returns (items, jobs, notes); items/jobs empty when there is
		nothing to do. items: [_LayerItem], the active layer first.
		jobs: [(job items, contour indices)]. Synchronized: one job across
		all layers; otherwise one job per layer.'''
		items, notes = [], []

		for name in self.layer_names(glyph):
			fl_layer = glyph.layer(name)
			if fl_layer is None:
				continue

			shapes, skipped = [], []
			for sid, shape in enumerate(fl_layer.shapes):
				kind = _kind(shape)
				if kind is not None:
					if kind != 'component':		# components are expected: not reported
						skipped.append('#{} {}'.format(sid, kind))
				elif len(shape.contours):
					shapes.append(shape)

			if skipped:
				notes.append('{} | {}: not processed: {}.'.format(glyph.name, name, ', '.join(skipped)))

			items.append(_LayerItem(name, fl_layer, shapes))

		if not items:
			notes.append('Glyph "{}": no layers in scope.'.format(glyph.name))
			return [], [], notes

		# - Selection lives on the first layer (the active one when in scope)
		selected = []
		for i, c in enumerate(items[0].contours):
			if any(n.selected for n in c.nodes):
				selected.append(i)
			if self.checked('lock_sel'):
				for node in c.nodes:
					if node.selected and node.is_on:
						node.lib = {'locked': True}

		def todo(item):
			count = len(item.contours)
			if not self.checked('selected'):
				return list(range(count))
			return [i for i in selected if i < count]

		if self.synchronized(items):
			if any(len(item.contours) != len(items[0].contours) for item in items):
				notes.append('Glyph "{}": layers have different contour counts. '
							 'Uncheck "Synchronize layers" to clean each layer on its own.'.format(glyph.name))
				return [], [], notes
			jobs = [(items, todo(items[0]))]
		else:
			jobs = [([item], todo(item)) for item in items]

		jobs = [job for job in jobs if job[1]]
		return items, jobs, notes

	@staticmethod
	def compatibility(items, after):
		'''Several layers: compare node structure before and after.'''
		def state(layers):
			ref = [_types(c) for c in layers[0]]
			odd = [item.name for item, contours in zip(items[1:], layers[1:]) if [_types(c) for c in contours] != ref]
			return 'compatible' if not odd else 'INCOMPATIBLE ({})'.format(', '.join(odd))

		before = [item.contours for item in items]
		return 'Layers {} -> {} (vs. "{}")'.format(state(before), state(after), items[0].name)

	# - Actions -----------------------------------------
	def on_clean(self, simplify=True, dry_run=False):
		try:
			glyphs = getProcessGlyphs(pMode)
		except Exception:
			glyphs = []

		if not glyphs:
			self.say('No glyphs to process.')
			return

		mode = 'Analyze' if dry_run else ('Clean & Simplify' if simplify else 'Fix Degeneracies')
		started = time.time()
		lines, done, failed, before, after = [], [], [], 0, 0

		for glyph in glyphs:
			try:
				glyph_lines, counts = self.clean_glyph(glyph, simplify, dry_run, mode)
			except Exception:
				output(2, app_name, 'Glyph "{}" failed:'.format(glyph.name))
				print(traceback.format_exc())
				failed.append(glyph.name)
				continue

			lines += glyph_lines
			if counts is not None:
				done.append(glyph.name)
				before += counts[0]
				after += counts[1]

		verdict = '{}: {} glyph(s), nodes {} -> {}'.format(mode, len(done), before, after)
		if failed:
			verdict += '; {} failed (Output panel)'.format(len(failed))
		verdict += '; nothing changed' if dry_run else ''
		verdict += ' ({:.2f}s).'.format(time.time() - started)

		if len(glyphs) == 1:
			self.say(*(lines + [verdict]))
		else:
			for line in lines:
				print('{}: {}'.format(app_name, line))
			self.say(verdict)

		if not dry_run and done:
			pWorkspace().getCanvas(True).refreshAll()

	def clean_glyph(self, glyph, simplify, dry_run, mode):
		'''Returns (report lines, (nodes before, nodes after) or None).'''
		items, jobs, lines = self.collect(glyph)
		if not jobs:
			if items:
				lines.append('Glyph "{}": nothing to clean.'.format(glyph.name))
			return lines, None

		opts = self.options(glyph, simplify)
		before = dict.fromkeys(range(len(items)), 0)
		after = dict.fromkeys(range(len(items)), 0)
		deviation = dict.fromkeys(range(len(items)), 0.)
		result = [list(item.contours) for item in items]		# None marks a dropped contour
		touched = {}	# item index -> {contour index}
		dropped = 0

		for job_items, indices in jobs:
			slots = [items.index(item) for item in job_items]

			for i in indices:
				try:
					out = clean([[item.contours[i]] for item in job_items], opts)
				except (IncompatibleMasters, ImportError) as error:
					lines.append('Glyph "{}" ({}): {}'.format(glyph.name, ', '.join(item.name for item in job_items), error))
					if isinstance(error, IncompatibleMasters):
						lines.append('Uncheck "Synchronize layers" to clean each layer on its own.')
					return lines, None

				for m, s in enumerate(slots):
					source = items[s].contours[i]
					before[s] += len(source.nodes)
					touched.setdefault(s, set()).add(i)

					if out[m]:
						after[s] += len(out[m][0].nodes)
						deviation[s] = max(deviation[s], contour_deviation(source, out[m][0]))
						result[s][i] = out[m][0]
					else:
						result[s][i] = None
						dropped += 1

		lines += ['{} | {}: nodes {} -> {}; max dev. {:.2f}u'.format(glyph.name, items[s].name, before[s], after[s], deviation[s])
				  for s in sorted(touched)]
		if dropped:
			lines.append('{}: dropped {} tiny contour(s).'.format(glyph.name, dropped))
		if len(items) > 1:
			lines.append(self.compatibility(items, [[c for c in contours if c is not None] for contours in result]))

		counts = (sum(before.values()), sum(after.values()))
		if dry_run:
			return lines, counts

		written = []
		for s, indices in touched.items():
			self.write(items[s], result[s], indices)
			written.append(items[s].name)

		for name in written:
			glyph.update(name)
		sync = 'synchronized' if self.synchronized(items) else 'per layer'
		glyph.updateObject(glyph.fl, '{} | {} ({}) @ {}'.format(app_name, mode, sync, '; '.join(written)), False)
		return lines, counts

	def write(self, item, contours, indices):
		'''Mount cleaned contours back into their elements. Same node types:
		nodes in place; otherwise the contour is rebuilt. None (dropped)
		contours are removed; an element left empty is removed.'''
		k = 0
		for shape, fl_contours in zip(item.shapes, item.fl_contours):
			new_contours, changed = [], False

			for fl_contour in fl_contours:
				core = contours[k]

				if k not in indices:
					new_contours.append(fl_contour)

				elif core is None:
					changed = True

				elif _types(core) == _types(item.contours[k]):
					trContour(fl_contour).mount(core)
					new_contours.append(fl_contour)

				else:
					new_contours.append(_build_fl_contour(core))
					changed = True

				k += 1

			if changed:
				if new_contours:
					shape.contours = new_contours
				else:
					item.fl_layer.removeShape(shape)

	def on_locks(self):
		try:
			glyph = eGlyph()
		except Exception:
			self.say('No current glyph.')
			return

		try:
			self.say(*self.locks(glyph))
		except Exception:
			output(2, app_name, 'Show Locks failed:')
			print(traceback.format_exc())
			self.say('Glyph "{}": Show Locks failed, see the Output panel.'.format(glyph.name))

	def locks(self, glyph):
		'''Synchronized: locks decided across all layers in scope; otherwise
		the active layer alone. Shown as a selection on the active layer.'''
		items, jobs, lines = self.collect(glyph)
		if not jobs:
			return lines + ['Glyph "{}": nothing to show.'.format(glyph.name)]

		job_items, indices = jobs[0]
		if job_items[0] is not items[0] or items[0].name != glyph.layer().name:
			return lines + ['Glyph "{}": the active layer is not in scope.'.format(glyph.name)]

		try:
			locks = locked_nodes([[item.contours[i] for i in indices] for item in job_items], self.options(glyph, True))
		except IncompatibleMasters as error:
			return lines + ['Glyph "{}": {}'.format(glyph.name, error)]

		fl_contours = [contour for contours in items[0].fl_contours for contour in contours]
		for fl_contour in fl_contours:
			for node in fl_contour.nodes():
				node.selected = False

		total = 0
		for i, nodes in zip(indices, locks):
			fl_nodes = fl_contours[i].nodes()
			for n in nodes:
				if n < len(fl_nodes):
					fl_nodes[n].selected = True
			total += len(nodes)

		glyph.update()
		pWorkspace().getCanvas(True).refreshAll()
		return lines + ['{}: {} locked node(s) selected on layer "{}".'.format(glyph.name, total, items[0].name)]

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
		layoutV.addWidget(TRCleanupPanel())

		# - Build
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!

	test.show()
