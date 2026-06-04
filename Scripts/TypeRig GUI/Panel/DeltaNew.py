#FLM: TR: Delta New
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import hashlib
import json
import math
import os
import random
import warnings
from collections import namedtuple

import fontlab as fl6
import fontgate as fgt

from PythonQt import QtCore, QtGui

from typerig.core.base.message import (
	output, GlyphWarning, LayerWarning,
	TRDeltaAxisWarning, TRDeltaStemWarning, TRDeltaArrayWarning,
)
from typerig.core.objects.array import PointArray
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.transform import Transform, TransformOrigin

from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.proxy.fl.gui.widgets import (
	getTRIconFontPath, CustomPushButton, TRFlowLayout,
	TRDeltaMultiAxisTree, TRCustomSpinController,
)
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark


# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Delta New', '0.2'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Strings ---------------------------
app_id_key = 'com.typerig.delta.machine.axissetup'
# Columns mirror the original Delta exactly.
tree_column_names = ('Master Layers', 'V st.', 'H st.', 'Width', 'Height', 'Color')
file_formats = 'TypeRig Delta Panel Setup (*.json);;'

# - Defaults — same shape as legacy Delta -----------
default_sx = '100.'
default_sy = '100.'


# =====================================================================
# FL Host shim — everything that talks to live FL lives here.
# Replace this block to port the panel to another host application.
# =====================================================================
def host_current_glyph():
	fl_g = fl6.CurrentGlyph()
	return trGlyph(fl_g) if fl_g is not None else None


def host_current_font():
	return pFont() if fl6.CurrentFont() is not None else None


def host_process_glyphs(mode):
	'''Return list[trGlyph] for the given pMode:
	   0 = current glyph in editor
	   1 = all glyphs in current text block
	   2 = all selected glyphs in font window
	   3 = all glyphs in font
	'''
	if mode == 0:
		current = host_current_glyph()
		return [current] if current is not None else []

	workspace = pWorkspace()
	if mode == 1:
		fg_glyphs = workspace.getTextBlockGlyphs() or []
		return [trGlyph(fg) for fg in fg_glyphs]

	font = host_current_font()
	if font is None: return []

	if mode == 2:
		return [trGlyph(eg.fl) for eg in font.selectedGlyphs(extend=eGlyph)]
	if mode == 3:
		return [trGlyph(eg.fl) for eg in font.glyphs(extend=eGlyph)]
	return []


def host_refresh_canvas():
	try:
		pWorkspace().getCanvas(True).refreshAll()
	except Exception:
		pass


def host_font_lib_get(key, default=None):
	font = host_current_font()
	if font is None: return default
	try:
		lib = font.fl.packageLib
		return lib[key] if key in lib else default
	except Exception:
		return default


def host_font_lib_set(key, value):
	font = host_current_font()
	if font is None: return False
	lib = font.fl.packageLib
	lib[key] = value
	font.fl.packageLib = lib
	return True


def host_selected_nodes_stem(tr_glyph_obj, layer_name, axis):
	'''Read live FL selection on layer_name and measure |Δ| along axis.
	axis: 'x' or 'y'. Returns rounded float or None if no usable selection.
	'''
	try:
		sel = eGlyph(tr_glyph_obj.host).selectedNodes(layer_name, True)
		if not sel or len(sel) < 2: return None
		if axis == 'y':
			return round(abs(sel[0].y - sel[-1].y), 2)
		return round(abs(sel[0].x - sel[-1].x), 2)
	except (AttributeError, IndexError):
		return None


def host_undo_snapshot(tr_glyphs, message, verbose=True):
	if not tr_glyphs: return
	if len(tr_glyphs) > 2:
		font = host_current_font()
		if font is not None:
			font.updateObject(font.fl, message, verbose)
	else:
		g = tr_glyphs[0]
		pg = pGlyph(g.host)
		pg.updateObject(pg.fl, message, verbose)


def host_font_italic_angle():
	font = host_current_font()
	return font.italic_angle if font is not None else 0.0


def host_font_name():
	font = host_current_font()
	return font.name if font is not None else '<no font>'


def host_font_master_names():
	font = host_current_font()
	if font is None: return []
	return font.masters()


def host_path_for_dialog():
	font = host_current_font()
	if font is None: return ''
	try:
		return os.path.split(font.fg.path)[0]
	except Exception:
		return ''


def host_layer_exists(tr_glyph_obj, layer_name):
	return tr_glyph_obj.find_layer(layer_name) is not None


def host_duplicate_layer(tr_glyph_obj, src_layer_name, dst_layer_name):
	'''Duplicate src layer as dst (master, no references). Matches the
	semantics legacy Delta uses to spawn a target layer on the fly.
	'''
	pg = pGlyph(tr_glyph_obj.host)
	pg.duplicateLayer(layer=src_layer_name,
		newLayerName=dst_layer_name, references=False)


def host_active_layer_name():
	current = host_current_glyph()
	return current.active_layer if current is not None else None


def host_layer_wireframe_color(layer_name):
	'''FL's per-layer wireframe color as a QColor, or None if the active
	glyph doesn't have that layer (e.g. masters that aren't drawn yet).
	Mirrors legacy Delta's master-pool color seeding.
	'''
	current = host_current_glyph()
	if current is None: return None
	try:
		tr_layer = current.find_layer(layer_name)
		if tr_layer is None: return None
		return tr_layer.host.wireframeColor
	except (AttributeError, RuntimeError):
		return None


# =====================================================================
# Data model — pure planning state, no FL bindings.
# =====================================================================
MasterEntry = namedtuple('MasterEntry', 'name vstem hstem color')
TargetEntry = namedtuple('TargetEntry', 'name mode stem scale dims origin color')
# input_colors is parallel to inputs/stems — preserves the swatch a row
# inherited when the user dragged it from the Master Layers pool.
VirtualAxis = namedtuple('VirtualAxis', 'name inputs stems input_colors targets')
# Live Axis — distinct from the bake axes. Inputs only; the implicit
# target is whatever layer is currently active in the editor. Drives
# the slider section. Mirrors the FontRig setup.liveAxis slot.
LiveAxis    = namedtuple('LiveAxis',    'name inputs stems input_colors')
DeltaSetup  = namedtuple('DeltaSetup',  'masters live_axis axes')


def _empty_live_axis():
	return LiveAxis('Live', [], [], [])


# - Transform-origin code map (kept compact for serialisation) -----------
ORIGIN_FROM_CODE = {
	'BL': TransformOrigin.BOTTOM_LEFT,
	'BR': TransformOrigin.BOTTOM_RIGHT,
	'TL': TransformOrigin.TOP_LEFT,
	'TR': TransformOrigin.TOP_RIGHT,
	'CE': TransformOrigin.CENTER,
	'BS': TransformOrigin.BASELINE,
}
ORIGIN_TO_CODE = {v: k for k, v in ORIGIN_FROM_CODE.items()}


def _suggest_axis_name(input_names):
	key = '|'.join(sorted(input_names))
	h = hashlib.blake2s(key.encode('utf-8'), digest_size=2).hexdigest()
	return 'axis_%s' % h


def _rand_hex():
	rand = lambda: random.randint(0, 255)
	return '#%02X%02X%02X' % (rand(), rand(), rand())


# =====================================================================
# Setup <-> tree dict serialisation
# =====================================================================
def _tree_dict_from_setup(setup):
	d = {'masters': [], 'live_axis': {'inputs': []}, 'axes': []}
	for m in setup.masters:
		# Row shape mirrors legacy Delta: blank stems on masters,
		# 100/100 in Width/Height, color in col 5.
		d['masters'].append([m.name, str(m.vstem), str(m.hstem),
		                     default_sx, default_sy, m.color])

	# Live Axis — same row shape as a regular axis's inputs, but no targets.
	la = setup.live_axis
	live_colors = list(la.input_colors) + [''] * max(0, len(la.inputs) - len(la.input_colors))
	for (name, (vx, hx), col) in zip(la.inputs, la.stems, live_colors):
		d['live_axis']['inputs'].append(
			[name, str(vx), str(hx), default_sx, default_sy, col])

	for ax in setup.axes:
		ax_d = {'name': ax.name, 'inputs': [], 'targets': []}
		colors = list(ax.input_colors) + [''] * max(0, len(ax.inputs) - len(ax.input_colors))
		for (name, (vx, hx), col) in zip(ax.inputs, ax.stems, colors):
			ax_d['inputs'].append([name, str(vx), str(hx),
			                       default_sx, default_sy, col])
		for t in ax.targets:
			if t.mode == 'stems':
				ax_d['targets'].append({
					'mode': 'stems',
					'name': t.name,
					'vstem': str(t.stem[0]), 'hstem': str(t.stem[1]),
					'sx': str(t.scale[0]), 'sy': str(t.scale[1]),
					'color': t.color,
				})
			else:
				ax_d['targets'].append({
					'mode': 'dimensions',
					'name': t.name,
					'w': str(t.dims[0]), 'h': str(t.dims[1]),
					'origin': ORIGIN_TO_CODE.get(t.origin, 'BL'),
					'color': t.color,
				})
		d['axes'].append(ax_d)
	return d


def _parse_float(value, default=0.0):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _setup_from_tree_dict(d):
	'''Validate + parse a tree-dict into a DeltaSetup.
	Returns (setup, errors). If errors non-empty, caller should abort.
	'''
	errors = []

	masters = []
	for row in d.get('masters', []):
		name = row[0] if len(row) > 0 else ''
		if name in (None, '', 'Master Layers'): continue
		# Masters keep stems as raw strings (may be blank). They're just
		# the pool — the engine never reads them.
		vstem = row[1] if len(row) > 1 else ''
		hstem = row[2] if len(row) > 2 else ''
		color = row[5] if len(row) > 5 else ''
		masters.append(MasterEntry(name, vstem, hstem, color))

	axes = []
	used_axis_names = set()
	for ax_d in d.get('axes', []):
		name = ax_d.get('name', '').strip()
		if not name:
			errors.append('Axis has no name.')
			continue
		if name in used_axis_names:
			errors.append('Duplicate axis name: %s' % name)
			continue
		used_axis_names.add(name)

		input_names = []
		input_stems = []
		input_colors = []
		for row in ax_d.get('inputs', []):
			n = row[0] if len(row) > 0 else ''
			if not n: continue
			try:
				vx = float(row[1]); hx = float(row[2])
			except (ValueError, IndexError):
				errors.append('Axis "%s": input "%s" has invalid stems.' % (name, n))
				continue
			input_names.append(n)
			input_stems.append((vx, hx))
			input_colors.append(row[5] if len(row) > 5 else '')

		if len(input_names) < 2:
			errors.append('Axis "%s" needs at least 2 inputs.' % name)
			continue

		targets = []
		used_target_names = set()
		for t_d in ax_d.get('targets', []):
			t_name = t_d.get('name', '').strip()
			if not t_name:
				errors.append('Axis "%s": target without a name.' % name)
				continue
			if t_name in used_target_names:
				errors.append('Axis "%s": duplicate target "%s".' % (name, t_name))
				continue
			used_target_names.add(t_name)

			mode = t_d.get('mode', 'stems')
			if mode == 'stems':
				stem = (_parse_float(t_d.get('vstem'), 100.0),
				        _parse_float(t_d.get('hstem'), 100.0))
				scale = (_parse_float(t_d.get('sx'), 100.0),
				         _parse_float(t_d.get('sy'), 100.0))
				targets.append(TargetEntry(t_name, 'stems', stem, scale,
				                           None, None, t_d.get('color', '')))
			else:
				dims = (_parse_float(t_d.get('w'), 600.0),
				        _parse_float(t_d.get('h'), 700.0))
				origin = ORIGIN_FROM_CODE.get(t_d.get('origin', 'BL'),
				                              TransformOrigin.BOTTOM_LEFT)
				targets.append(TargetEntry(t_name, 'dimensions', None, None,
				                           dims, origin, t_d.get('color', '')))

		axes.append(VirtualAxis(name, input_names, input_stems, input_colors, targets))

	# Live Axis parse.
	la_d = d.get('live_axis', {}) or {}
	la_input_names, la_stems, la_colors = [], [], []
	for row in la_d.get('inputs', []):
		n = row[0] if len(row) > 0 else ''
		if not n: continue
		try:
			vx = float(row[1]); hx = float(row[2])
		except (ValueError, IndexError):
			errors.append('Live Axis: input "%s" has invalid stems.' % n)
			continue
		la_input_names.append(n)
		la_stems.append((vx, hx))
		la_colors.append(row[5] if len(row) > 5 else '')
	live_axis = LiveAxis('Live', la_input_names, la_stems, la_colors)

	return DeltaSetup(masters, live_axis, axes), errors


# =====================================================================
# Legacy single-axis format migration (old Delta.py saves).
# =====================================================================
def _is_legacy_shape(d):
	if not isinstance(d, dict): return False
	keys = set(d.keys())
	return ('Virtual Axis' in keys) and ('Master Layers' in keys)


def _migrate_legacy(d):
	# New shape includes a Live Axis slot — seeded empty for legacy saves.
	new = {'masters': [], 'live_axis': {'inputs': []}, 'axes': []}
	masters_rows = d.get('Master Layers', [])
	axis_rows    = d.get('Virtual Axis', [])
	target_rows  = d.get('Target Layers', [])

	for r in masters_rows:
		new['masters'].append([r[0], str(r[1]), str(r[2]), '', '', r[5] if len(r) > 5 else ''])

	axis_d = {'name': 'Virtual Axis', 'inputs': [], 'targets': []}
	for r in axis_rows:
		axis_d['inputs'].append([r[0], str(r[1]), str(r[2]), '', '', ''])

	for r in target_rows:
		axis_d['targets'].append({
			'mode': 'stems',
			'name': r[0],
			'vstem': str(r[1]), 'hstem': str(r[2]),
			'sx': str(r[3]), 'sy': str(r[4]),
			'color': r[5] if len(r) > 5 else '',
		})

	new['axes'].append(axis_d)
	return new


def _migrate_new_shape(d):
	'''Patch a DeltaNew dict missing the live_axis slot (e.g. saved
	before this field was introduced). Mutates and returns the dict.
	'''
	if isinstance(d, dict):
		if 'live_axis' not in d or not isinstance(d['live_axis'], dict):
			d['live_axis'] = {'inputs': []}
		if 'inputs' not in d['live_axis']:
			d['live_axis']['inputs'] = []
	return d


# =====================================================================
# Core engine — build virtual axes from a trGlyph + bake targets.
# =====================================================================
def _eject_input_layers(tr_glyph_obj, axis):
	'''Eject input layers from tr_glyph_obj into a fresh core.Glyph
	with stems pre-set, ready for create_virtual_axis.

	Returns (core_glyph, missing, empty).
	  missing — input names not present as FL layers on this glyph
	  empty   — input names whose FL layer exists but has no outline
	            (DeltaScale.__init__ would otherwise fail on these with
	             a cryptic IndexError).
	'''
	missing, empty = [], []
	layers = []
	for name, (vx, hx) in zip(axis.inputs, axis.stems):
		tr_layer = tr_glyph_obj.find_layer(name)
		if tr_layer is None:
			missing.append(name)
			continue
		core_layer = tr_layer.eject()
		if len(core_layer.shapes) == 0 or len(core_layer.nodes) == 0:
			empty.append(name)
			continue
		core_layer.stems = (vx, hx)
		layers.append(core_layer)
	return Glyph(layers, name=tr_glyph_obj.name), missing, empty


def _bake_target_stems(base_layer, vaxis, target, italic_rad, extrapolate,
                       global_origin, source_bounds_for_origin):
	'''Stems-mode bake: drive DeltaScale.scale_by_stem on every attribute
	in vaxis, write results into a clone of base_layer, then realign for
	the chosen global transform origin (mirrors core.Layer.scale_with_axis
	post-scale realignment). vaxis may legitimately omit attribs that were
	filtered out as empty/mismatched upstream — that's fine.
	'''
	new_layer = base_layer.clone()

	for attrib, delta_scale in vaxis.items():
		try:
			result = list(delta_scale.scale_by_stem(
				target.stem,
				(target.scale[0] / 100.0, target.scale[1] / 100.0),
				(0., 0.), (0., 0.),
				italic_rad,
				extrapolate,
			))
		except (IndexError, ValueError, AssertionError):
			continue
		if attrib == 'point_array':
			new_layer.point_array = PointArray(result)
		else:
			setattr(new_layer, attrib, result)

	# Realign to preserve the chosen transform origin (skip for BASELINE).
	if global_origin is not None and global_origin != TransformOrigin.BASELINE:
		try:
			source_x, source_y = source_bounds_for_origin.align_matrix[global_origin.code]
			dest_bounds = new_layer.bounds
			dest_x, dest_y = dest_bounds.align_matrix[global_origin.code]
			new_layer.shift(source_x - dest_x, source_y - dest_y)
		except Exception:
			pass

	return new_layer


def _bake_target_dims(base_layer, vaxis, target, extrapolate):
	return base_layer.scale_with_axis(
		vaxis,
		target_width=target.dims[0],
		target_height=target.dims[1],
		transform_origin=target.origin or TransformOrigin.BOTTOM_LEFT,
		extrapolate=extrapolate,
	)


def _resolve_inputs(axis, produced_so_far):
	'''Cascade hook (stub) — identity for now.'''
	return list(axis.inputs)


def _attr_len(layer, attrib):
	'''Length of a layer's delta-relevant attribute. Safe over the three
	we care about: point_array, metric_array, anchor_array.
	'''
	value = getattr(layer, attrib, None)
	if value is None: return 0
	try:
		return len(value)
	except TypeError:
		return 0


def _viable_attribs(core_glyph, layer_names, requested):
	'''Filter requested attribs down to those that core.DeltaScale can
	actually consume across all input layers. Skips attribs where any
	layer has zero entries (cause of the "list index out of range" inside
	DeltaScale) or where layers disagree on count (cause of an assertion).

	Returns (viable_attribs, warnings).
	'''
	viable = []
	warnings_list = []

	for attrib in requested:
		lengths = [_attr_len(core_glyph.layer(n), attrib) for n in layer_names]
		if not lengths or min(lengths) == 0:
			warnings_list.append(
				'attribute "%s" empty on at least one input — skipped.' % attrib)
			continue
		if max(lengths) != min(lengths):
			warnings_list.append(
				'attribute "%s" count mismatch across inputs %s — skipped.'
				% (attrib, lengths))
			continue
		viable.append(attrib)

	return viable, warnings_list


def _ensure_and_mount(tr_glyph_obj, new_core_layer, base_input_name):
	'''Ensure an FL layer named new_core_layer.name exists on tr_glyph_obj.
	If it doesn't, duplicate the base input layer so the new layer inherits
	master flag / metrics / anchors / link state. Then mount the scaled
	core data on top.
	'''
	target_tr_layer = tr_glyph_obj.find_layer(new_core_layer.name)
	if target_tr_layer is None:
		host_duplicate_layer(tr_glyph_obj, base_input_name, new_core_layer.name)
		target_tr_layer = tr_glyph_obj.find_layer(new_core_layer.name)
		if target_tr_layer is None:
			raise RuntimeError('Could not create FL layer "%s"' % new_core_layer.name)
	target_tr_layer.mount(new_core_layer)


# =====================================================================
# Panel
# =====================================================================
class TRDeltaNewPanel(QtGui.QWidget):
	def __init__(self):
		super(TRDeltaNewPanel, self).__init__()

		# - State
		self.setup = DeltaSetup(masters=[], live_axis=_empty_live_axis(), axes=[])
		# Per-glyph live snapshots, keyed by glyph name. Mirrors original
		# Delta.py's `glyph_arrays`: each entry holds the frozen DeltaScale
		# objects built from the Live Axis inputs at snapshot time.
		# {glyph_name: {'delta_outline', 'delta_service', 'last_layer'}}
		self._live_snapshot = {}
		self.glyph_arrays = {}     # (glyph_name, axis_name) -> {core_glyph, vaxis, tr_glyph}
		self.active_layer_name = None
		self.active_canvas = None

		# - Build layout
		lay_main = QtGui.QVBoxLayout()

		# -- Tree
		self.tree = TRDeltaMultiAxisTree()
		self.tree.setTree(_tree_dict_from_setup(self._fresh_setup()), tree_column_names)
		lay_main.addWidget(self.tree)

		# -- Tree context: stem helpers + clear-all
		self.tree.menu.addSeparator()
		act_get_vstem = QtGui.QAction('Measure V stem on selection', self)
		act_get_hstem = QtGui.QAction('Measure H stem on selection', self)
		act_clear_all = QtGui.QAction('Clear all (reset masters from font)', self)
		self.tree.menu.addAction(act_get_vstem)
		self.tree.menu.addAction(act_get_hstem)
		self.tree.menu.addSeparator()
		self.tree.menu.addAction(act_clear_all)
		act_get_vstem.triggered.connect(lambda: self.get_stem(False))
		act_get_hstem.triggered.connect(lambda: self.get_stem(True))
		act_clear_all.triggered.connect(lambda: self.__reset_all(True))

		# -- Action buttons (full original layout)
		box_actions = QtGui.QGroupBox()
		box_actions.setObjectName('box_group')
		lay_actions = TRFlowLayout(spacing=10)

		self.btn_execute_scale = CustomPushButton('action_play',
			tooltip='Execute delta (bake targets)', enabled=False, obj_name='btn_panel')
		self.btn_execute_scale.clicked.connect(lambda: self.execute_target())
		lay_actions.addWidget(self.btn_execute_scale)

		self.btn_get_stem_x = CustomPushButton('stem_vertical_alt',
			tooltip='Get vertical stems', obj_name='btn_panel')
		self.btn_get_stem_x.clicked.connect(lambda: self.get_stem(False))
		lay_actions.addWidget(self.btn_get_stem_x)

		self.btn_get_stem_y = CustomPushButton('stem_horizontal_alt',
			tooltip='Get horizontal stems', obj_name='btn_panel')
		self.btn_get_stem_y.clicked.connect(lambda: self.get_stem(True))
		lay_actions.addWidget(self.btn_get_stem_y)

		self.btn_undo_snapshot = CustomPushButton('undo_snapshot',
			tooltip='Make undo snapshot', obj_name='btn_panel')
		self.btn_undo_snapshot.clicked.connect(lambda: self.__undo_snapshot('Manual snapshot'))
		lay_actions.addWidget(self.btn_undo_snapshot)

		self.btn_axis_set = CustomPushButton('axis_set',
			tooltip='Set axes (commit tree → setup)', obj_name='btn_panel')
		self.btn_axis_set.clicked.connect(lambda: self.__set_axis(True))
		lay_actions.addWidget(self.btn_axis_set)

		self.btn_axis_reset = CustomPushButton('axis_remove',
			tooltip='Reset all axes (keep masters)', obj_name='btn_panel')
		self.btn_axis_reset.clicked.connect(lambda: self.__reset_axis(True))
		lay_actions.addWidget(self.btn_axis_reset)

		self.btn_axis_reset_all = CustomPushButton('refresh',
			tooltip='Reset all data (re-seed masters from font)', obj_name='btn_panel')
		self.btn_axis_reset_all.clicked.connect(lambda: self.__reset_all(True))
		lay_actions.addWidget(self.btn_axis_reset_all)

		self.btn_file_save = CustomPushButton('file_save',
			tooltip='Save setup to external JSON', obj_name='btn_panel')
		self.btn_file_save.clicked.connect(lambda: self.file_save_axis_data())
		lay_actions.addWidget(self.btn_file_save)

		self.btn_file_open = CustomPushButton('file_open',
			tooltip='Load setup from external JSON', obj_name='btn_panel')
		self.btn_file_open.clicked.connect(lambda: self.file_open_axis_data())
		lay_actions.addWidget(self.btn_file_open)

		self.btn_font_save = CustomPushButton('font_save',
			tooltip='Save setup to font lib', obj_name='btn_panel')
		self.btn_font_save.clicked.connect(lambda: self.font_save_axis_data())
		lay_actions.addWidget(self.btn_font_save)

		self.btn_font_open = CustomPushButton('font_open',
			tooltip='Load setup from font lib', obj_name='btn_panel')
		self.btn_font_open.clicked.connect(lambda: self.font_open_axis_data())
		lay_actions.addWidget(self.btn_font_open)

		box_actions.setLayout(lay_actions)
		lay_main.addWidget(box_actions)

		# -- Options
		box_options = QtGui.QGroupBox()
		box_options.setObjectName('box_group')
		lay_options = TRFlowLayout(spacing=10)

		self.chk_metrics = CustomPushButton('metrics_advance_alt',
			checkable=True, checked=True, tooltip='Process metrics', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_metrics)

		self.chk_anchors = CustomPushButton('icon_anchor',
			checkable=True, checked=True, tooltip='Process anchors', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_anchors)

		self.chk_extrapolate = CustomPushButton('extrapolate',
			checkable=True, checked=True, tooltip='Allow extrapolation', obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_extrapolate)

		self.chk_target = CustomPushButton('node_target',
			checkable=True, checked=False, tooltip='Use target (bake mode)', obj_name='btn_panel_opt')
		self.chk_target.clicked.connect(lambda: self.__prepare_target())
		lay_options.addWidget(self.chk_target)

		self.chk_proportional = CustomPushButton('scale_lock',
			checkable=True, checked=False, tooltip='Proportional scale mode (sliders)',
			obj_name='btn_panel_opt')
		self.chk_proportional.clicked.connect(lambda: self.__toggle_proportional_scale())
		lay_options.addWidget(self.chk_proportional)

		self.chk_selection = CustomPushButton('selection_basic',
			checkable=True, checked=False, tooltip='Selection mode (live, advanced)',
			obj_name='btn_panel_opt')
		lay_options.addWidget(self.chk_selection)

		self.chk_toggle_controls = CustomPushButton('value_controls',
			checkable=True, checked=True, tooltip='Show extended controls (sliders)',
			obj_name='btn_panel_opt')
		self.chk_toggle_controls.clicked.connect(lambda: self.__toggle_controls())
		lay_options.addWidget(self.chk_toggle_controls)

		box_options.setLayout(lay_options)
		lay_main.addWidget(box_options)

		# -- Transformation origin radio group (global, for stems & live mode)
		box_transform = QtGui.QGroupBox()
		box_transform.setObjectName('box_group')
		lay_transform = TRFlowLayout(spacing=10)

		self.grp_btn_transform = QtGui.QButtonGroup()
		self.grp_btn_transform.setExclusive(True)

		self.chk_or = CustomPushButton('node_align_bottom_left',
			checkable=True, checked=True, tooltip='Transform at Origin (baseline)',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_or, 1)
		lay_transform.addWidget(self.chk_or)

		self.chk_bl = CustomPushButton('node_bottom_left',
			checkable=True, checked=False, tooltip='Transform at Bottom Left',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_bl, 2)
		lay_transform.addWidget(self.chk_bl)

		self.chk_br = CustomPushButton('node_bottom_right',
			checkable=True, checked=False, tooltip='Transform at Bottom Right',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_br, 4)
		lay_transform.addWidget(self.chk_br)

		self.chk_ce = CustomPushButton('node_center',
			checkable=True, checked=False, tooltip='Transform at Center',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_ce, 6)
		lay_transform.addWidget(self.chk_ce)

		self.chk_tl = CustomPushButton('node_top_left',
			checkable=True, checked=False, tooltip='Transform at Top Left',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_tl, 3)
		lay_transform.addWidget(self.chk_tl)

		self.chk_tr = CustomPushButton('node_top_right',
			checkable=True, checked=False, tooltip='Transform at Top Right',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_tr, 5)
		lay_transform.addWidget(self.chk_tr)

		box_transform.setLayout(lay_transform)
		lay_main.addWidget(box_transform)

		# -- Live slider controls
		lay_controls = TRFlowLayout(spacing=10)

		self.cpn_value_width = TRCustomSpinController('width',
			(-999, 999, 100, 1), ' %', 'Width')
		self.cpn_value_width.spin_box.valueChanged.connect(lambda: self.execute_scale())
		lay_controls.addWidget(self.cpn_value_width)

		self.cpn_value_height = TRCustomSpinController('height',
			(-999, 999, 100, 1), ' %', 'Height')
		self.cpn_value_height.spin_box.valueChanged.connect(lambda: self.execute_scale())
		lay_controls.addWidget(self.cpn_value_height)

		self.cpn_value_stem_x = TRCustomSpinController('stem_vertical_alt',
			(-999, 999, 1, 1), ' u', 'Vertical stem width')
		self.cpn_value_stem_x.spin_box.valueChanged.connect(lambda: self.execute_scale())
		lay_controls.addWidget(self.cpn_value_stem_x)

		self.cpn_value_stem_y = TRCustomSpinController('stem_horizontal_alt',
			(-999, 999, 1, 1), ' u', 'Horizontal stem width')
		self.cpn_value_stem_y.spin_box.valueChanged.connect(lambda: self.execute_scale())
		lay_controls.addWidget(self.cpn_value_stem_y)

		self.cpn_value_lerp_t = TRCustomSpinController('interpolate',
			(-999, 999, 0, 1), ' %', 'Time along axis')
		self.cpn_value_lerp_t.spin_box.valueChanged.connect(lambda: self.execute_scale(True))
		lay_controls.addWidget(self.cpn_value_lerp_t)

		self.cpn_value_ital = TRCustomSpinController('slope_italic',
			(-20, 20, host_font_italic_angle(), 1), ' °', 'Italic angle')
		self.cpn_value_ital.spin_box.valueChanged.connect(lambda: self.execute_scale())
		lay_controls.addWidget(self.cpn_value_ital)

		lay_main.addLayout(lay_controls)

		self.__refresh_options()
		self.__toggle_controls()

		# - Final
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())
		self.setWindowTitle('%s %s' % (app_name, app_version))
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

	# - Events ------------------------------------------------
	def contextMenuEvent(self, event):
		self.tree.menu.popup(QtGui.QCursor.pos())

	# - Helpers -----------------------------------------------
	def _fresh_setup(self):
		'''Empty setup populated with the active font's masters as the pool,
		mirroring legacy Delta's initial seeding.'''
		# Original Delta seeded masters with blank stems (the user fills these
		# in when they drag the layer into a Virtual Axis) and 100/100 for
		# Width/Height. Color comes from the layer's wireframeColor when
		# available, otherwise random.
		masters = []
		for name in host_font_master_names():
			color = host_layer_wireframe_color(name)
			color_hex = color.name() if color is not None else _rand_hex()
			masters.append(MasterEntry(name, '', '', color_hex))
		return DeltaSetup(masters=masters,
		                  live_axis=_empty_live_axis(),
		                  axes=[])

	def __refresh_options(self):
		# - Mirror legacy semantics
		self.opt_extrapolate = self.chk_extrapolate.isChecked()
		self.opt_metrics = self.chk_metrics.isChecked()
		self.opt_anchors = self.chk_anchors.isChecked()
		self.opt_selection = self.chk_selection.isChecked()

		# - Transform origin (global, for live + stems-mode bake)
		self.transform_origin = TransformOrigin.BASELINE
		if self.chk_bl.isChecked(): self.transform_origin = TransformOrigin.BOTTOM_LEFT
		if self.chk_br.isChecked(): self.transform_origin = TransformOrigin.BOTTOM_RIGHT
		if self.chk_tl.isChecked(): self.transform_origin = TransformOrigin.TOP_LEFT
		if self.chk_tr.isChecked(): self.transform_origin = TransformOrigin.TOP_RIGHT
		if self.chk_ce.isChecked(): self.transform_origin = TransformOrigin.CENTER

	def __toggle_controls(self):
		expand = self.chk_toggle_controls.isChecked()
		for cpn in (self.cpn_value_width, self.cpn_value_height,
		            self.cpn_value_ital, self.cpn_value_stem_x,
		            self.cpn_value_stem_y, self.cpn_value_lerp_t):
			(cpn.expand if expand else cpn.contract)()

	def __toggle_proportional_scale(self):
		self.cpn_value_height.setEnabled(not self.chk_proportional.isChecked())

	def __prepare_target(self):
		'''Target mode toggle — when on, sliders disabled and bake button live.
		When off, sliders drive (single-axis only).
		'''
		target_mode = self.chk_target.isChecked()
		for cpn in (self.cpn_value_width, self.cpn_value_height,
		            self.cpn_value_stem_x, self.cpn_value_stem_y,
		            self.cpn_value_lerp_t, self.cpn_value_ital):
			cpn.setEnabled(not target_mode)
		self.btn_execute_scale.setEnabled(target_mode or self._slider_can_drive())

	def _slider_can_drive(self):
		return len(self.setup.axes) == 1

	def __undo_snapshot(self, message):
		host_undo_snapshot(host_process_glyphs(pMode),
			'%s %s | %s' % (app_name, app_version, message))

	# - Axis lifecycle (mirrors legacy btn_axis_set / reset / reset_all) -
	def __set_axis(self, verbose=False):
		'''Commit tree state to self.setup. Build per-(glyph, axis) deltas.'''
		setup, errors = _setup_from_tree_dict(self.tree.getTree())
		if errors:
			for e in errors: warnings.warn(e, TRDeltaAxisWarning)
			return False

		self.setup = setup
		# Setup changed — drop the live snapshot so the next slider tick
		# captures the new Live Axis state.
		self._live_snapshot = {}
		if not setup.axes:
			warnings.warn('No axes defined! Add at least one Virtual Axis.',
				TRDeltaAxisWarning)
			self.glyph_arrays = {}
			self.btn_execute_scale.setEnabled(False)
			return False

		ok = self.__refresh_arrays()
		self.btn_execute_scale.setEnabled(ok)
		self.__refresh_ui()

		if verbose and ok:
			output(0, '%s %s' % (app_name, app_version),
				'Font: %s; %d axis/axes set.' % (host_font_name(), len(setup.axes)))
		return ok

	def __reset_axis(self, verbose=False):
		'''Clear axes and built arrays. Keep the master pool in the tree.'''
		# Rebuild tree without axes, masters preserved.
		current_dict = self.tree.getTree()
		current_dict['axes'] = []
		self.tree.setTree(current_dict, tree_column_names)

		self.setup = DeltaSetup(masters=self.setup.masters,
		                        live_axis=self.setup.live_axis,
		                        axes=[])
		self.glyph_arrays = {}
		# Keep the Live Axis snapshot — only bake axes were cleared.
		self.btn_execute_scale.setEnabled(False)

		if verbose:
			output(0, '%s %s' % (app_name, app_version),
				'Font: %s; All axes cleared.' % host_font_name())

	def __reset_all(self, verbose=False):
		'''Full reset: re-seed masters from font, drop everything else.'''
		self.tree.setTree(_tree_dict_from_setup(self._fresh_setup()), tree_column_names)
		self.setup = self._fresh_setup()
		self.glyph_arrays = {}
		self._live_snapshot = {}   # full reset includes the Live Axis
		self.btn_execute_scale.setEnabled(False)

		for cpn, default in ((self.cpn_value_width, 100),
		                     (self.cpn_value_height, 100),
		                     (self.cpn_value_stem_x, 100),
		                     (self.cpn_value_stem_y, 100),
		                     (self.cpn_value_lerp_t, 0),
		                     (self.cpn_value_ital, host_font_italic_angle())):
			cpn.blockSignals(True)
			cpn.setValue(default)
			cpn.blockSignals(False)

		if verbose:
			output(0, '%s %s' % (app_name, app_version),
				'Font: %s; Full reset.' % host_font_name())

	def __refresh_ui(self):
		'''Reset slider defaults after a setup change.'''
		self.cpn_value_width.blockSignals(True)
		self.cpn_value_height.blockSignals(True)
		self.cpn_value_width.setValue(100)
		self.cpn_value_height.setValue(100)
		self.cpn_value_width.blockSignals(False)
		self.cpn_value_height.blockSignals(False)

		# For the single-axis case, seed stem sliders from the first input.
		if len(self.setup.axes) == 1 and self.setup.axes[0].stems:
			vx, hx = self.setup.axes[0].stems[0]
			self.cpn_value_stem_x.blockSignals(True)
			self.cpn_value_stem_y.blockSignals(True)
			self.cpn_value_stem_x.setValue(vx)
			self.cpn_value_stem_y.setValue(hx)
			self.cpn_value_stem_x.blockSignals(False)
			self.cpn_value_stem_y.blockSignals(False)

		self.cpn_value_ital.blockSignals(True)
		self.cpn_value_ital.setValue(host_font_italic_angle())
		self.cpn_value_ital.blockSignals(False)

	# - Stem measurement --------------------------------------
	def get_stem(self, get_y=False):
		current = host_current_glyph()
		if current is None: return

		axis_label = 'y' if get_y else 'x'
		col_idx = 2 if get_y else 1

		root = self.tree.invisibleRootItem()
		self.tree.blockSignals(True)
		try:
			# Master rows
			masters_group = self.tree._find_top(self.tree.ROLE_MASTER,
				self.tree.GROUP_MASTERS_NAME)
			if masters_group is not None:
				for i in range(masters_group.childCount()):
					row = masters_group.child(i)
					val = host_selected_nodes_stem(current, row.text(0), axis_label)
					if val is not None: row.setText(col_idx, str(val))

			# Per-axis inputs
			for i in range(root.childCount()):
				axis_item = root.child(i)
				if self.tree._role(axis_item) != self.tree.ROLE_AXIS: continue
				inputs = self.tree._find_subgroup(axis_item, self.tree.ROLE_INPUTS)
				if inputs is None: continue
				for k in range(inputs.childCount()):
					row = inputs.child(k)
					val = host_selected_nodes_stem(current, row.text(0), axis_label)
					if val is not None: row.setText(col_idx, str(val))
		finally:
			self.tree.blockSignals(False)

	# - Engine ------------------------------------------------
	def __refresh_arrays(self, silent=False):
		'''Build per-(glyph, axis) virtual axes ready for the executor.'''
		setup = self.setup
		if not setup.axes:
			self.glyph_arrays = {}
			return False

		process_glyphs = host_process_glyphs(pMode)
		if not process_glyphs:
			if not silent: warnings.warn('No glyphs to process.', GlyphWarning)
			return False

		attribs = ['point_array']
		if self.opt_metrics: attribs.append('metric_array')
		if self.opt_anchors: attribs.append('anchor_array')

		new_arrays = {}
		produced = {}     # cascade-ready (always empty in stub)

		for tr_g in process_glyphs:
			produced.setdefault(tr_g.name, set())

			for axis in setup.axes:
				resolved_inputs = _resolve_inputs(axis, produced[tr_g.name])
				axis_for_eject = VirtualAxis(axis.name, resolved_inputs,
				                             axis.stems, axis.input_colors,
				                             axis.targets)

				core_glyph, missing, empty = _eject_input_layers(tr_g, axis_for_eject)
				if missing:
					if not silent:
						warnings.warn(
							'Glyph "%s" / axis "%s": missing layers %s — skipping.'
							% (tr_g.name, axis.name, ', '.join(missing)),
							LayerWarning)
					continue
				if empty:
					if not silent:
						warnings.warn(
							'Glyph "%s" / axis "%s": empty input layers %s '
							'(no outline). Cannot build deltas — fill these '
							'layers or remove them from the axis.'
							% (tr_g.name, axis.name, ', '.join(empty)),
							LayerWarning)
					continue
				if len(core_glyph.layers) < 2:
					if not silent:
						warnings.warn(
							'Glyph "%s" / axis "%s": fewer than 2 usable inputs.'
							% (tr_g.name, axis.name),
							LayerWarning)
					continue

				usable_inputs = [l.name for l in core_glyph.layers]

				viable, skip_reasons = _viable_attribs(core_glyph,
					usable_inputs, attribs)
				if 'point_array' not in viable:
					if not silent:
						warnings.warn(
							'Glyph "%s" / axis "%s": no usable point_array — %s'
							% (tr_g.name, axis.name, '; '.join(skip_reasons)),
							TRDeltaArrayWarning)
					continue
				if skip_reasons and not silent:
					for reason in skip_reasons:
						warnings.warn(
							'Glyph "%s" / axis "%s": %s'
							% (tr_g.name, axis.name, reason),
							TRDeltaArrayWarning)

				try:
					vaxis = core_glyph.create_virtual_axis(
						usable_inputs, attributes=viable)
				except Exception as e:
					if not silent:
						warnings.warn(
							'Glyph "%s" / axis "%s": create_virtual_axis failed: %s'
							% (tr_g.name, axis.name, e),
							TRDeltaArrayWarning)
					continue

				new_arrays[(tr_g.name, axis.name)] = {
					'core_glyph': core_glyph,
					'vaxis': vaxis,
					'tr_glyph': tr_g,
				}

		self.glyph_arrays = new_arrays
		return bool(new_arrays)

	def execute_target(self):
		'''Bake target layers across all axes.'''
		self.__refresh_options()
		ok = self.__refresh_arrays(silent=False)
		if not ok: return

		italic_rad = math.radians(-float(host_font_italic_angle()))
		extrapolate = self.opt_extrapolate
		glyphs_done = set()
		touched = []

		for axis in self.setup.axes:
			for tr_g in host_process_glyphs(pMode):
				entry = self.glyph_arrays.get((tr_g.name, axis.name))
				if entry is None: continue

				core_glyph = entry['core_glyph']
				vaxis = entry['vaxis']
				# Use the first usable input — may differ from axis.inputs[0]
				# when empty layers were filtered out upstream.
				base_input = core_glyph.layers[0].name
				base_layer = core_glyph.layer(base_input)

				source_bounds = base_layer.bounds  # for stems-mode origin realignment

				for target in axis.targets:
					try:
						if target.mode == 'stems':
							new_layer = _bake_target_stems(
								base_layer, vaxis, target,
								italic_rad, extrapolate,
								self.transform_origin, source_bounds)
						else:
							new_layer = _bake_target_dims(
								base_layer, vaxis, target, extrapolate)
					except Exception as e:
						warnings.warn(
							'Glyph "%s" / axis "%s" / target "%s": bake failed: %s'
							% (tr_g.name, axis.name, target.name, e),
							TRDeltaArrayWarning)
						continue

					new_layer.name = target.name
					try:
						_ensure_and_mount(tr_g, new_layer, base_input)
					except Exception as e:
						warnings.warn(
							'Glyph "%s" target "%s": mount failed: %s'
							% (tr_g.name, target.name, e),
							LayerWarning)
						continue

				tr_g.update()
				glyphs_done.add(tr_g.name)
				if tr_g not in touched: touched.append(tr_g)

		host_refresh_canvas()
		host_undo_snapshot(touched, '%s %s | Bake' % (app_name, app_version), False)
		output(0, '%s %s' % (app_name, app_version),
			'Font: %s; Glyph(s): %s.' % (host_font_name(), '; '.join(sorted(glyphs_done))))

	# - Live snapshot management ---------------------------
	def _refresh_live_snapshot(self, silent=False):
		'''Eject the Live Axis inputs from the active glyph into a frozen
		core.Glyph + DeltaScale dict, and cache it per glyph in
		self._live_snapshot. Mirrors original Delta.py's __refresh_arrays
		but scoped to the Live Axis only. Snapshot reads happen here;
		slider ticks read from the cache and never re-eject.
		'''
		live = self.setup.live_axis
		if not live or len(live.inputs) < 2:
			self._live_snapshot = {}
			return False

		current = host_current_glyph()
		if current is None: return False

		# Build a fake VirtualAxis for the eject helper.
		live_as_axis = VirtualAxis(live.name, live.inputs, live.stems,
		                           live.input_colors, [])
		core_glyph, missing, empty = _eject_input_layers(current, live_as_axis)
		if missing or empty:
			if not silent:
				warnings.warn('Live Axis: missing/empty inputs %s'
					% ', '.join(missing + empty), LayerWarning)
		if len(core_glyph.layers) < 2:
			self._live_snapshot = {}
			return False

		usable_inputs = [l.name for l in core_glyph.layers]
		attribs = ['point_array']
		if self.opt_metrics: attribs.append('metric_array')
		if self.opt_anchors: attribs.append('anchor_array')
		viable, _skipped = _viable_attribs(core_glyph, usable_inputs, attribs)
		if 'point_array' not in viable:
			self._live_snapshot = {}
			return False

		try:
			vaxis = core_glyph.create_virtual_axis(
				usable_inputs, attributes=viable)
		except Exception as e:
			if not silent:
				warnings.warn('Live snapshot: create_virtual_axis failed: %s'
					% e, TRDeltaArrayWarning)
			self._live_snapshot = {}
			return False

		self._live_snapshot[current.name] = {
			'core_glyph': core_glyph,
			'vaxis': vaxis,
			'tr_glyph': current,
			'last_layer': current.active_layer,
		}
		return True

	def _ensure_live_snapshot_for_active_layer(self):
		'''Watcher equivalent: if the editor's active layer has changed
		since the last snapshot for this glyph, re-snapshot. The new
		snapshot captures each input layer at its *current* state — so
		prior driving is baked into the baseline used by future driving.
		Also resets the slider section to neutral for the new active layer.
		'''
		current = host_current_glyph()
		if current is None: return False
		entry = self._live_snapshot.get(current.name)
		if entry is None:
			# Fresh snapshot.
			if not self._refresh_live_snapshot(silent=True): return False
			self.__seed_live_sliders_from_layer(current.active_layer)
			return True
		if entry.get('last_layer') != current.active_layer:
			# Re-snapshot at current state of all inputs.
			if not self._refresh_live_snapshot(silent=True): return False
			# Reset sliders to neutral for the new active layer.
			self.__seed_live_sliders_from_layer(current.active_layer)
			return True
		return True

	def __seed_live_sliders_from_layer(self, layer_name):
		'''Set the slider state to neutral for the named layer: V/H read
		from whichever Live Axis input matches the name (or master pool
		fallback); Wt/Ht reset to 100.
		'''
		vx = hx = None
		for (n, (a, b)) in zip(self.setup.live_axis.inputs,
		                       self.setup.live_axis.stems):
			if n == layer_name:
				vx, hx = a, b; break
		if vx is None:
			for m in self.setup.masters:
				if m.name == layer_name:
					try:
						vx = float(m.vstem); hx = float(m.hstem)
					except (ValueError, TypeError):
						pass
					break

		for cpn, val in ((self.cpn_value_width, 100),
		                 (self.cpn_value_height, 100),
		                 (self.cpn_value_stem_x, vx if vx is not None else 100),
		                 (self.cpn_value_stem_y, hx if hx is not None else 100),
		                 (self.cpn_value_lerp_t, 0)):
			cpn.blockSignals(True)
			cpn.setValue(val)
			cpn.blockSignals(False)

	def execute_scale(self, use_time=False):
		'''Live slider mode — driven by the Live Axis (the permanent slot,
		not the bake axes). Each tick reads the cached snapshot and
		writes only to the editor's currently active layer.

		Cascade-proof: the inputs come from the frozen snapshot, never
		from the live glyph. Active-layer change triggers a re-snapshot
		and a slider reset before this method runs (see
		_ensure_live_snapshot_for_active_layer).
		'''
		self.__refresh_options()

		# Target mode active? Sliders shouldn't drive.
		if self.chk_target.isChecked(): return

		# Need a current glyph and an initialised Live Axis.
		current = host_current_glyph()
		if current is None: return

		live = self.setup.live_axis
		if not live or len(live.inputs) < 2:
			warnings.warn('Live Axis needs at least 2 inputs. Drag '
				'masters into the Live Axis section.',
				TRDeltaAxisWarning)
			return

		# Snapshot — re-takes if layer changed, builds if missing.
		if not self._ensure_live_snapshot_for_active_layer(): return
		entry = self._live_snapshot.get(current.name)
		if entry is None: return

		vaxis = entry['vaxis']
		base_input = entry['core_glyph'].layers[0].name
		base_layer = entry['core_glyph'].layer(base_input)
		source_bounds = base_layer.bounds

		# Scale ratios.
		sx = float(self.cpn_value_width.getValue())
		if self.chk_proportional.isChecked():
			sy = sx
			self.cpn_value_height.blockSignals(True)
			self.cpn_value_height.setValue(sx)
			self.cpn_value_height.blockSignals(False)
		else:
			sy = float(self.cpn_value_height.getValue())

		italic_rad = math.radians(-float(host_font_italic_angle()))
		intervals = len(vaxis['point_array'])

		if use_time:
			# Time-along-axis drives the stem readouts back to the user.
			t = float(self.cpn_value_lerp_t.getValue()) * intervals / 100.0
			try:
				stem_point = list(vaxis['point_array'].scale_by_time(
					(t, t), (1., 1.), (0., 0.), (0., 0.),
					False, self.opt_extrapolate))
				# Pull a sample stem from the result if shape is right.
				if stem_point:
					self.cpn_value_stem_x.blockSignals(True)
					self.cpn_value_stem_y.blockSignals(True)
					self.cpn_value_stem_x.setValue(round(stem_point[0][0]))
					self.cpn_value_stem_y.setValue(round(stem_point[0][1]))
					self.cpn_value_stem_x.blockSignals(False)
					self.cpn_value_stem_y.blockSignals(False)
			except Exception:
				pass

		stem = (float(self.cpn_value_stem_x.getValue()),
		        float(self.cpn_value_stem_y.getValue()))

		target_name = current.active_layer
		live_target = TargetEntry(target_name, 'stems', stem, (sx, sy),
		                          None, None, '')

		try:
			new_layer = _bake_target_stems(
				base_layer, vaxis, live_target,
				italic_rad, self.opt_extrapolate,
				self.transform_origin, source_bounds)
		except Exception as e:
			warnings.warn('Live bake failed: %s' % e, TRDeltaArrayWarning)
			return

		new_layer.name = target_name
		try:
			_ensure_and_mount(current, new_layer, base_input)
		except Exception as e:
			warnings.warn('Mount failed: %s' % e, LayerWarning)
			return

		current.update()
		host_refresh_canvas()

	# - Persistence -------------------------------------------
	def _load_tree_dict(self, raw):
		if _is_legacy_shape(raw):
			raw = _migrate_legacy(raw)
		else:
			raw = _migrate_new_shape(raw)
		self.tree.setTree(raw, tree_column_names)
		# Re-commit setup from the loaded tree (silent — load is the cue).
		self.setup, _errs = _setup_from_tree_dict(self.tree.getTree())
		# Loaded a fresh tree — drop any stale live snapshot.
		self._live_snapshot = {}

	def font_save_axis_data(self):
		setup, errors = _setup_from_tree_dict(self.tree.getTree())
		if errors:
			for e in errors: warnings.warn(e, TRDeltaAxisWarning)
			return
		host_font_lib_set(app_id_key, self.tree.getTree())
		output(7, app_name, 'Font: %s; Setup saved to font lib key %s.'
			% (host_font_name(), app_id_key))

	def font_open_axis_data(self):
		raw = host_font_lib_get(app_id_key)
		if raw is None:
			warnings.warn('No setup stored under %s.' % app_id_key, TRDeltaAxisWarning)
			return
		self._load_tree_dict(raw)
		output(6, app_name, 'Font: %s; Setup loaded from font lib.' % host_font_name())

	def file_save_axis_data(self):
		setup, errors = _setup_from_tree_dict(self.tree.getTree())
		if errors:
			for e in errors: warnings.warn(e, TRDeltaAxisWarning)
			return
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save setup',
			host_path_for_dialog(), file_formats)
		if not fname: return
		with open(fname, 'w') as f:
			json.dump(self.tree.getTree(), f, indent=2)
		output(7, app_name, 'Font: %s; Setup saved to %s.' % (host_font_name(), fname))

	def file_open_axis_data(self):
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load setup',
			host_path_for_dialog(), file_formats)
		if not fname: return
		with open(fname, 'r') as f:
			raw = json.load(f)
		self._load_tree_dict(raw)
		output(6, app_name, 'Font: %s; Setup loaded from %s.' % (host_font_name(), fname))


# - Tab wrapper ----------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)

		lay_main = QtGui.QVBoxLayout()
		lay_main.setContentsMargins(0, 0, 0, 0)
		lay_main.addWidget(TRDeltaNewPanel())
		self.setLayout(lay_main)


# - Test -----------------------------------
if __name__ == '__main__':
	delta_panel = tool_tab()
	delta_panel.setWindowTitle('%s %s' % (app_name, app_version))
	delta_panel.setGeometry(100, 100, 320, 480)
	delta_panel.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
	delta_panel.show()
