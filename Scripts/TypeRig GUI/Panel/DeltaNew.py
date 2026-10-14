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
from typerig.core.objects.delta import DeltaScale
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.transform import Transform, TransformOrigin
from typerig.core.objects.utils import Bounds

from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.proxy.fl.gui.widgets import (
	getTRIconFontPath, getTRIconFont, CustomPushButton, TRFlowLayout,
	TRDeltaMultiAxisTree, TRCustomSpinController,
)
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.fl.gui import canvas_overlay as co
from typerig.proxy.fl.gui import overlay_math as om


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
# grp_btn_transform button id -> origin code (Live Edit canvas)
LIVE_ORIGIN_CODES = {1: 'BS', 2: 'BL', 3: 'TL', 4: 'BR', 5: 'TR', 6: 'CE',
                     7: 'BM', 8: 'TM', 9: 'LM', 10: 'RM'}


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

		# Live Edit (canvas) — all inert until btn_live is pressed.
		self.live_tool = None        # TRDeltaCanvas while Live Edit is on
		self.live_keep_axis = False  # keep the Live Axis snapshot on layer switch
		self.live_info = None        # capture info for the canvas (None = nothing captured)
		self.live_frame = None       # output frame (xmin, ymin, xmax, ymax), x deslanted
		self.live_seed = None        # (vstem, hstem) seeded for the active layer
		self._live_glyph = None      # glyph name of the last Live Edit capture
		self._live_fail = None       # why the last Live Edit capture failed
		self._live_sel_saved = None  # chk_selection state before Live Edit

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

		self.btn_live = CustomPushButton('delta_machine',
			checkable=True, checked=False,
			tooltip='Live Edit: show the Live Axis controls on the glyph canvas',
			obj_name='btn_panel_opt')
		self.btn_live.clicked.connect(lambda: self.live_edit())
		lay_actions.addWidget(self.btn_live)

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
		self.chk_metrics.clicked.connect(lambda: self.__live_setup_changed())
		lay_options.addWidget(self.chk_metrics)

		self.chk_anchors = CustomPushButton('icon_anchor',
			checkable=True, checked=True, tooltip='Process anchors', obj_name='btn_panel_opt')
		self.chk_anchors.clicked.connect(lambda: self.__live_setup_changed())
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

		self.chk_bm = CustomPushButton('node_middle_bottom',
			checkable=True, checked=False, tooltip='Transform at Bottom Middle',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_bm, 7)
		lay_transform.addWidget(self.chk_bm)

		self.chk_br = CustomPushButton('node_bottom_right',
			checkable=True, checked=False, tooltip='Transform at Bottom Right',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_br, 4)
		lay_transform.addWidget(self.chk_br)

		self.chk_lm = CustomPushButton('node_middle_left',
			checkable=True, checked=False, tooltip='Transform at Left Middle',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_lm, 9)
		lay_transform.addWidget(self.chk_lm)

		self.chk_ce = CustomPushButton('node_center',
			checkable=True, checked=False, tooltip='Transform at Center',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_ce, 6)
		lay_transform.addWidget(self.chk_ce)

		self.chk_rm = CustomPushButton('node_middle_right',
			checkable=True, checked=False, tooltip='Transform at Right Middle',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_rm, 10)
		lay_transform.addWidget(self.chk_rm)

		self.chk_tl = CustomPushButton('node_top_left',
			checkable=True, checked=False, tooltip='Transform at Top Left',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_tl, 3)
		lay_transform.addWidget(self.chk_tl)

		self.chk_tm = CustomPushButton('node_middle_top',
			checkable=True, checked=False, tooltip='Transform at Top Middle',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_tm, 8)
		lay_transform.addWidget(self.chk_tm)

		self.chk_tr = CustomPushButton('node_top_right',
			checkable=True, checked=False, tooltip='Transform at Top Right',
			obj_name='btn_panel_opt')
		self.grp_btn_transform.addButton(self.chk_tr, 5)
		lay_transform.addWidget(self.chk_tr)

		# Toggling the origin re-fires the live drive so the user sees the
		# new alignment immediately — applies to selection mode in particular.
		# buttonClicked fires once per user click (whereas buttonToggled
		# fires twice — once for the old button off, once for the new on).
		self.grp_btn_transform.buttonClicked.connect(
			lambda *_: self.execute_scale())

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
		if self.chk_bm.isChecked(): self.transform_origin = TransformOrigin.BOTTOM_MIDDLE
		if self.chk_tm.isChecked(): self.transform_origin = TransformOrigin.TOP_MIDDLE
		if self.chk_lm.isChecked(): self.transform_origin = TransformOrigin.CENTER_LEFT
		if self.chk_rm.isChecked(): self.transform_origin = TransformOrigin.CENTER_RIGHT

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
		self.__live_setup_changed()

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
		self.__live_setup_changed()
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

		self.__live_setup_changed()

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
		'''Measure |Δ| between selected nodes and broadcast to every row in
		the tree whose layer name matches a layer in the current glyph.
		Covers Master Layers, Live Axis inputs, and every Virtual Axis's
		inputs. Mirrors how the FontRig panel broadcasts measurements.
		'''
		current = host_current_glyph()
		if current is None: return

		axis_label = 'y' if get_y else 'x'
		col_idx = 2 if get_y else 1

		def _measure(layer_name):
			return host_selected_nodes_stem(current, layer_name, axis_label)

		def _walk_group(group):
			if group is None: return
			for k in range(group.childCount()):
				row = group.child(k)
				val = _measure(row.text(0))
				if val is not None: row.setText(col_idx, str(val))

		root = self.tree.invisibleRootItem()
		self.tree.blockSignals(True)
		try:
			# Master Layers pool.
			_walk_group(self.tree._find_top(self.tree.ROLE_MASTER,
				self.tree.GROUP_MASTERS_NAME))

			# Live Axis inputs.
			_walk_group(self.tree._find_top(self.tree.ROLE_LIVE_AXIS,
				self.tree.GROUP_LIVE_AXIS_NAME))

			# Virtual Axes' Inputs sub-groups.
			for i in range(root.childCount()):
				axis_item = root.child(i)
				if self.tree._role(axis_item) != self.tree.ROLE_AXIS: continue
				_walk_group(self.tree._find_subgroup(axis_item,
					self.tree.ROLE_INPUTS))
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

		# Selection / per-contour mode — Delta.py pattern: when chk_selection
		# is on, build the DeltaScale from ONLY the selected nodes' positions.
		# We don't go through create_virtual_axis (which insists on the full
		# point_array via Layer.point_array setter constraints); instead we
		# slice each input layer's point_array by the indices selected on
		# the active layer, then construct DeltaScale directly. The drive
		# path mutates flNodes in place — no mount needed.
		sel_indices = None
		if self.opt_selection:
			active_tr = current.find_layer(current.active_layer)
			if active_tr is not None:
				ej = active_tr.eject()
				# trNode.eject already mirrors flNode.selected — see
				# proxy/tr/objects/node.py __meta__.
				sel_indices = [i for i, n in enumerate(ej.nodes)
				               if getattr(n, 'selected', False)]
				if not sel_indices:
					sel_indices = None     # nothing selected → fall through

		vaxis = None
		if sel_indices:
			try:
				data_array = []
				stem_array = []
				for layer in core_glyph.layers:
					pa = list(layer.point_array.tuple)
					data_array.append([pa[i] for i in sel_indices if i < len(pa)])
					stem_array.append([layer.stems])
				# Single-attribute vaxis — selection mode is geometry-only.
				vaxis = {'point_array': DeltaScale(data_array, stem_array)}
			except Exception as e:
				if not silent:
					warnings.warn('Live snapshot (selection mode): %s' % e,
						TRDeltaArrayWarning)
				self._live_snapshot = {}
				return False
		else:
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
			'sel_indices': sel_indices,
			'sel_count': len(sel_indices) if sel_indices else None,
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
			if self.live_keep_axis:
				# Live Edit: keep the axis; the new active layer is only the
				# new output target. Reseed the sliders for it, no re-eject.
				entry['last_layer'] = current.active_layer
				self.__seed_live_sliders_from_layer(current.active_layer)
				return True
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

		# Neutral stems for this layer: the canvas stem ring is relative to them.
		self.live_seed = (float(vx) if vx is not None else 100.,
		                  float(hx) if hx is not None else 100.)

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

		# ----- Selection-mode short-circuit -----------------------
		# Mirrors original Delta.py's _setPointArray(selection=True): the
		# snapshot's DeltaScale was built from the selected-node positions
		# only; the slider output has the same length; we write directly
		# to the destination's currently-selected flNodes. No core.Layer,
		# no mount — flNode identity is preserved, so .selected survives.
		#
		# Transform origin: the chosen origin point of the *current*
		# selection bounds is held fixed — we shift the new positions so
		# that origin lands where it started. This makes the radio buttons
		# behave live (rebuilds happen on every slider/origin tick).
		if entry.get('sel_indices'):
			stem = (float(self.cpn_value_stem_x.getValue()),
			        float(self.cpn_value_stem_y.getValue()))
			try:
				result = list(vaxis['point_array'].scale_by_stem(
					stem, (sx / 100.0, sy / 100.0),
					(0., 0.), (0., 0.),
					italic_rad, self.opt_extrapolate))
			except Exception as e:
				warnings.warn('Live (selection): %s' % e, TRDeltaArrayWarning)
				return

			target_name = current.active_layer
			fl_layer = None
			for l in current.host.layers:
				if l.name == target_name:
					fl_layer = l; break
			if fl_layer is None: return

			selected_fl_nodes = []
			for shape in fl_layer.shapes:
				for contour in shape.contours:
					for node in contour.nodes():
						if node.selected:
							selected_fl_nodes.append(node)

			if len(selected_fl_nodes) != entry.get('sel_count', 0):
				warnings.warn('Selection changed since snapshot — toggle '
					'Selection off/on to re-snapshot.',
					TRDeltaArrayWarning)
				return

			# Origin realignment — keep the chosen point on the selection
			# bounds fixed. Matches original Delta.py's _setPointArray
			# realign-shift logic.
			ox, oy = 0.0, 0.0
			if self.transform_origin is not None \
			   and self.transform_origin != TransformOrigin.BASELINE:
				try:
					src_pts = [(n.x, n.y) for n in selected_fl_nodes]
					src_b = Bounds(src_pts)
					dst_b = Bounds(result)
					sx0, sy0 = src_b.align_matrix[self.transform_origin.code]
					dx0, dy0 = dst_b.align_matrix[self.transform_origin.code]
					ox = sx0 - dx0
					oy = sy0 - dy0
				except Exception:
					ox, oy = 0.0, 0.0

			for fl_node, pos in zip(selected_fl_nodes, result):
				try:
					fl_node.x = pos[0] + ox
					fl_node.y = pos[1] + oy
				except Exception:
					pass

			current.update()
			host_refresh_canvas()
			if self.__live_on():
				self.__live_wrote(current, [(pos[0] + ox, pos[1] + oy) for pos in result])
			return
		# ----- end selection-mode short-circuit -------------------

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
		# Output frame for the canvas (the mount may replace FL nodes).
		live_points = [(n.x, n.y) for n in new_layer.nodes] if self.__live_on() else None
		try:
			_ensure_and_mount(current, new_layer, base_input)
		except Exception as e:
			warnings.warn('Mount failed: %s' % e, LayerWarning)
			return

		current.update()
		host_refresh_canvas()
		if live_points is not None:
			self.__live_wrote(current, live_points)

	# - Live Edit (canvas) ------------------------------------
	# The canvas tool (TRDeltaCanvas) is a second front-end for the slider
	# controls: it sets them through live_set() and execute_scale() writes.
	# Lifecycle while it runs: capture on activation; a layer switch keeps
	# the Live Axis (live_keep_axis) and only reseeds; a glyph switch, an
	# outside node edit, a selection change or the recapture icon rebuild
	# the snapshot. The selection decides the mode (nodes selected ->
	# selection mode; none -> whole glyph); chk_selection mirrors it.
	def live_edit(self):
		'''Live Edit button: start or stop the canvas controls.'''
		if self.btn_live.isChecked():
			self.live_keep_axis = True
			self._live_sel_saved = self.chk_selection.isChecked()
			self.__live_build(True)		# capture on activation
			self.live_tool = TRDeltaCanvas.start(self)
		else:
			self.live_tool = None
			TRDeltaCanvas.stop()
			self.__live_end()

	def live_closed(self):
		'''Close icon on the canvas.'''
		self.btn_live.setChecked(False)
		self.live_edit()

	def live_problem(self):
		'''Why the canvas cannot drive (banner text), or None.'''
		if self.chk_target.isChecked():
			return 'Target mode is on: the sliders do not drive'
		live = self.setup.live_axis
		if not live or len(live.inputs) < 2:
			return 'Live Axis needs at least 2 inputs (set axes first)'
		if self.live_info is None:
			return self._live_fail or 'nothing captured'
		return None

	def live_state(self):
		'''Captured state for the canvas, or None (see live_problem).
		Returns dict: target (glyph, layer), frame and src_frame (x deslanted),
		slant (radians, + leans right), seed (vstem, hstem), params,
		proportional, selection (node count or None), warnings,
		options {'metrics', 'anchors'} (panel buttons) and process (what the
		snapshot really drives besides outlines: 'metrics', 'anchors').'''
		if self.live_problem() is not None:
			return None

		info = self.live_info
		return {'target': (info['glyph'], info['layer']), 'frame': self.live_frame,
		        'src_frame': info['src_frame'], 'slant': info['slant'], 'seed': self.live_seed,
		        'params': self.live_params(), 'proportional': self.chk_proportional.isChecked(),
		        'selection': info['selection'], 'warnings': info['warnings'],
		        'options': {'metrics': self.chk_metrics.isChecked(), 'anchors': self.chk_anchors.isChecked()},
		        'process': info['process']}

	def live_params(self):
		'''Canvas values: width/height factors (1.0 = 100 %), stems in units, origin code.'''
		width = float(self.cpn_value_width.getValue()) / 100.
		height = width if self.chk_proportional.isChecked() else float(self.cpn_value_height.getValue()) / 100.
		return {'width': width, 'height': height,
		        'stem_x': float(self.cpn_value_stem_x.getValue()),
		        'stem_y': float(self.cpn_value_stem_y.getValue()),
		        'origin': LIVE_ORIGIN_CODES.get(self.grp_btn_transform.checkedId(), 'BS')}

	def live_set(self, values):
		'''Set controls from the canvas (factors, units, origin code) and apply once.'''
		controls = {'width': self.cpn_value_width, 'height': self.cpn_value_height,
		            'stem_x': self.cpn_value_stem_x, 'stem_y': self.cpn_value_stem_y}

		for key, value in values.items():
			if key == 'origin':
				for bid, code in LIVE_ORIGIN_CODES.items():
					if code == value and self.grp_btn_transform.checkedId() != bid:
						self.grp_btn_transform.button(bid).setChecked(True)
				continue

			if key not in controls: continue
			if key in ('width', 'height'):
				value = int(round(value * 100.))
			else:
				value = max(1, int(round(value)))

			cpn = controls[key]
			cpn.blockSignals(True)
			cpn.setValue(value)
			cpn.blockSignals(False)

		self.execute_scale()

	def live_capture(self):
		'''Canvas moved to another layer or glyph. Same glyph: keep the Live
		Axis and reseed for the new active layer. Other glyph: capture it.'''
		return self.__live_build(False)

	def live_recapture(self):
		'''Outside node edit, selection change or recapture icon: rebuild the
		Live Axis snapshot from the current outline. No undo snapshot.'''
		return self.__live_build(True)

	def live_toggle(self, option):
		'''Canvas metrics / anchors icon: flip the panel option. The kept
		Live Axis was built with the old attributes, so this recaptures.'''
		chk = {'metrics': self.chk_metrics, 'anchors': self.chk_anchors}[option]
		chk.setChecked(not chk.isChecked())
		self.__live_setup_changed()

	def live_reset(self):
		'''Axis reset icon: neutral controls for the active layer, applied once.
		On a Live Axis input this writes its captured state back.'''
		if self.live_info is None: return
		self.__seed_live_sliders_from_layer(self.live_info['layer'])
		self.execute_scale()

	def __live_on(self):
		return self.live_tool is not None and self.live_tool.alive

	def __live_setup_changed(self):
		'''Live Axis setup or target mode changed while Live Edit is on.'''
		if self.__live_on():
			self.live_recapture()

	def __live_wrote(self, current, points):
		'''After every live write: keep the output frame, notify the canvas.'''
		info = self.live_info
		if info is not None and points and (info['glyph'], info['layer']) == (current.name, current.active_layer):
			self.live_frame = om.slant_bounds(points, info['slant'])

		if self.__live_on():
			self.live_tool.panel_wrote()

	def __live_build(self, rebuild):
		'''Capture for Live Edit: pick the mode from the selection, build (or
		keep) the Live Axis snapshot, seed the controls for the active layer
		and measure the frame. Writes nothing.
		Args:
			rebuild (bool): always re-eject; False keeps the snapshot when the
				glyph and the selection mode are unchanged (layer switch).
		'''
		self.live_info = None
		self._live_fail = None
		if self.chk_target.isChecked(): return False
		live = self.setup.live_axis
		if not live or len(live.inputs) < 2: return False

		current = host_current_glyph()
		if current is None:
			self._live_fail = 'no current glyph'
			return False

		active = current.active_layer
		active_tr = current.find_layer(active)
		nodes = active_tr.eject().nodes if active_tr is not None else []
		if not nodes:
			self._live_fail = 'active layer {} is empty'.format(active)
			return False

		sel = [i for i, n in enumerate(nodes) if getattr(n, 'selected', False)]
		self.chk_selection.setChecked(bool(sel))
		self.__refresh_options()

		entry = self._live_snapshot.get(current.name)
		keep = (not rebuild and entry is not None and self._live_glyph == current.name
		        and (entry.get('sel_indices') or None) == (sel or None))

		if keep:
			entry['last_layer'] = active
		elif not self._refresh_live_snapshot(silent=True):
			self._live_fail = 'Live Axis snapshot failed on {} (missing, empty or incompatible inputs)'.format(current.name)
			return False

		entry = self._live_snapshot[current.name]
		self.__seed_live_sliders_from_layer(active)

		sel_indices = entry.get('sel_indices')
		points = [(nodes[i].x, nodes[i].y) for i in sel_indices if i < len(nodes)] if sel_indices else [(n.x, n.y) for n in nodes]
		slant = math.radians(-float(host_font_italic_angle()))
		frame = om.slant_bounds(points, slant)

		usable = [l.name for l in entry['core_glyph'].layers]
		warns = []
		skipped = [name for name in live.inputs if name not in usable]
		if skipped:
			warns.append('skipped inputs: {}'.format(', '.join(skipped)))
		if active not in usable:
			warns.append('{} is not a Live Axis input: neutral = seed stems'.format(active))

		self._live_glyph = current.name
		self.live_frame = frame
		vaxis = entry['vaxis']
		process = [label for attrib, label in (('metric_array', 'metrics'), ('anchor_array', 'anchors')) if attrib in vaxis]

		self.live_info = {'glyph': current.name, 'layer': active, 'slant': slant, 'src_frame': frame,
		                  'selection': len(sel_indices) if sel_indices else None, 'warnings': warns,
		                  'process': process}
		return True

	def __live_end(self):
		'''Live Edit stopped: give slider mode back its own options.'''
		self.live_keep_axis = False
		self.live_info = self.live_frame = None
		self._live_glyph = None

		if self._live_sel_saved is not None:
			self.chk_selection.setChecked(self._live_sel_saved)
			if not self._live_sel_saved:
				# A selection snapshot would keep driving in selection mode
				for name in [n for n, e in self._live_snapshot.items() if e.get('sel_indices')]:
					del self._live_snapshot[name]
			self._live_sel_saved = None

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
		self.__live_setup_changed()

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


# =====================================================================
# Live Edit canvas
# =====================================================================
# Frame points: code -> (sx, sy) side signs; -1 = left/bottom, 0 = middle, +1 = right/top
_FRAME_POINTS = [('TL', -1, 1), ('TM', 0, 1), ('TR', 1, 1), ('RM', 1, 0),
                 ('BR', 1, -1), ('BM', 0, -1), ('BL', -1, -1), ('LM', -1, 0)]
# Delta's transform origins: the 9 frame points; 'BS' (baseline) is the font origin (0, 0)
_ORIGIN_POINTS = [('BL', -1, -1), ('TL', -1, 1), ('BR', 1, -1), ('TR', 1, 1), ('CE', 0, 0),
                  ('BM', 0, -1), ('TM', 0, 1), ('LM', -1, 0), ('RM', 1, 0)]

_CURSORS = {(-1, 1): QtCore.Qt.SizeFDiagCursor, (1, -1): QtCore.Qt.SizeFDiagCursor,
            (1, 1): QtCore.Qt.SizeBDiagCursor, (-1, -1): QtCore.Qt.SizeBDiagCursor,
            (0, 1): QtCore.Qt.SizeVerCursor, (0, -1): QtCore.Qt.SizeVerCursor,
            (1, 0): QtCore.Qt.SizeHorCursor, (-1, 0): QtCore.Qt.SizeHorCursor}

_LIVE_LIMITS = {'scale': (0.1, 9.99), 'stem': (0.05, 5.)}


def _side_coord(lo, hi, side):
	return lo if side < 0 else hi if side > 0 else (lo + hi) * .5


class CanvasIconStrip(object):
	'''Row of icon buttons on a CanvasOverlay. Slot 0 sits at origin(mapping);
	the other slots follow in its direction (-1 = to the left). Self-contained
	(handles, layout, paint, click) so it can move to a shared module.

	Entries: (key, icon, tooltip, callback, always[, checked]). icon is a
	TypeRig Icons ligature name, or None for the close cross; always=False
	entries show only while the owner is ready; checked() -> bool makes the
	entry a toggle, drawn lit while on. Adding an icon is adding one entry.
	'''
	SLOT_PX = 24.
	RADIUS = 9.
	ICON_PX = 14

	def __init__(self, owner, origin, entries):
		self.owner = owner
		self.origin = origin		# origin(mapping) -> (x, y, direction, ready) or None
		self.entries = [tuple(e) + (None,) * (6 - len(e)) for e in entries]
		self.actions = {}			# handle key -> (icon, callback, checked)
		self.handles = []
		self._font = None

		for index, (key, icon, tooltip, callback, always, checked) in enumerate(self.entries):
			handle = co.Handle('strip_' + key, self._anchor(index), om.SHAPE_CIRCLE, self.RADIUS, om.AXIS_XY,
			                   QtCore.Qt.PointingHandCursor, 'muted', tooltip=tooltip)
			self.handles.append(handle)
			self.actions[handle.key] = (icon, callback, checked)

	def handle(self, key):
		for h in self.handles:
			if h.key == 'strip_' + key: return h
		return None

	def is_checked(self, handle):
		checked = self.actions[handle.key][2]
		if checked is None: return False
		try:
			return bool(checked())
		except Exception:
			co._log.exception('{}.strip[{}].checked'.format(self.owner.NAME, handle.key))
			return False

	def _shown(self, entry, ready):
		return ready or entry[4]

	def _anchor(self, index):
		def anchor(mapping):
			o = self.origin(mapping)
			if o is None: return None
			x, y, direction, ready = o
			if not self._shown(self.entries[index], ready): return None
			slot = sum(1 for e in self.entries[:index] if self._shown(e, ready))
			return (x + direction * slot * self.SLOT_PX, y)
		return anchor

	def owns(self, handle):
		return handle is not None and handle.key in self.actions

	def width(self, ready):
		'''Screen px taken by the visible slots.'''
		return sum(1 for e in self.entries if self._shown(e, ready)) * self.SLOT_PX

	def click(self, handle):
		if not self.owns(handle): return False
		try:
			self.actions[handle.key][1]()
		except Exception:
			co._log.exception('{}.strip[{}]'.format(self.owner.NAME, handle.key))
		return True

	def _icon_font(self):
		if self._font is None:
			try:
				self._font = getTRIconFont(self.ICON_PX)
			except Exception:
				self._font = False
		return self._font if self._font is not False else None

	def paint(self, p, handle, x, y, hot):
		if not self.owns(handle): return False
		c = self.owner.colors
		icon = self.actions[handle.key][0]
		on = handle.enabled and self.is_checked(handle)
		r = handle.radius + (1. if hot else 0.)
		accent = c['error'] if icon is None else c['active']
		rect = QtCore.QRectF(x - r, y - r, 2. * r, 2. * r)

		p.setPen(co.cosmetic_pen(accent if hot or on else c['muted'], 1.5 if on else 1.))
		p.setBrush(co.solid_brush(c['label_bg']))
		p.drawRoundedRect(rect, 4., 4.)
		if on:
			p.setBrush(co.solid_brush(accent, 70))
			p.drawRoundedRect(rect, 4., 4.)

		ink = c['muted'] if not handle.enabled else accent if hot else c['text']
		if icon is None:
			p.setPen(co.cosmetic_pen(ink, 1.5))
			k = r * .45
			p.drawLine(QtCore.QPointF(x - k, y - k), QtCore.QPointF(x + k, y + k))
			p.drawLine(QtCore.QPointF(x - k, y + k), QtCore.QPointF(x + k, y - k))
			return True

		flags = QtCore.Qt.AlignCenter
		try:
			flags = int(flags)
		except TypeError:
			pass

		font = self._icon_font()
		p.save()
		if font is not None:
			p.setFont(font)
		p.setPen(QtGui.QPen(ink))
		p.drawText(rect, flags, icon if font is not None else icon[:1].upper())
		p.restore()
		return True


class TRDeltaCanvas(co.CanvasOverlay):
	'''Delta Live Axis controls on the glyph canvas, driving TRDeltaNewPanel.

	Frame quad (8)  width / height about the transform origin; drawn in the
	                deslanted frame, so it is a parallelogram in italic fonts
	Stem ring (4)   left / right: vertical stem; top / bottom: horizontal
	                (radius x stem / seed stem of the active layer)
	Origin cross    snaps to baseline (0, 0), BL, TL, BR, TR, CE
	Icon strip      close, recapture, axis reset

	All values go through the panel (live_set); the panel bakes and writes.
	Stems are compensated, so the output extent is affine in width %, not
	proportional: frame drags start from the proportional guess and refine
	by secant on the measured output (om.EdgeSecant), at most
	MAX_CORRECTIONS extra applies per push.
	'''
	NAME = 'tr_delta_live'
	PAD_PX = 16.				# frame quad sits this far outside the output frame
	STEM_RING_PX = (40., 110.)	# stem ring radius range on screen (before following the scale)
	STRIP_OFFSET_PX = 22.		# icon strip: diagonal offset from the frame's top-right handle
	PUSH_INTERVAL = .033		# seconds between live applies during a drag
	MAX_CORRECTIONS = 2			# secant re-applies per push (frame drags)
	SELECTION_INTERVAL = .15	# seconds between selection checks

	def __init__(self, panel):
		co.CanvasOverlay.__init__(self)
		self.panel = panel
		self.st = None				# panel.live_state() (params overridden during a drag)
		self.applied = None			# params as the panel holds them
		self.problem = None			# panel.live_problem() while st is None
		self._press = None			# {'params', 'ring'} at drag start
		self._drag_params = None	# params being dragged (ahead of the panel)
		self._models = {}			# frame drag: param key -> [axis, side, edge0, EdgeSecant, target]
		self._pending = None		# params waiting for the throttle
		self._origin_view = None	# cursor while dragging the origin cross
		self._sel_sig = None		# selection signature at the last capture or write
		self._state_key = None
		self._throttle = om.Throttle(self.PUSH_INTERVAL)
		self._sel_throttle = om.Throttle(self.SELECTION_INTERVAL)
		self._build_handles()

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
		st = self._call('live_state')
		self.applied = dict(st['params']) if st is not None else None
		self.problem = self._call('live_problem') if st is None else None

		if st is not None and self._drag_params is not None:
			st = dict(st)
			st['params'] = dict(self._drag_params)
		self.st = st
		self._update_options()

		# Repaint when the panel changed something (spin boxes, options)
		if st is None:
			key = (self.problem,)
		else:
			key = (st['target'], st['frame'], st['proportional'], st['selection'], tuple(sorted(st['params'].items())),
			       tuple(sorted(st['options'].items())), tuple(st['process']))
		if key != self._state_key:
			self._state_key = key
			self.request_repaint()

	def _push(self, params, now=False):
		'''Send params to the panel (throttled unless now), then refine frame
		drags against the measured output.'''
		if not (now or self._throttle.ready()):
			self._pending = dict(params)
			return

		self._pending = None
		self._call('live_set', dict(params))

		for _ in range(self.MAX_CORRECTIONS):
			fixed = self._correct(params)
			if fixed is None: break
			params = fixed
			self._call('live_set', dict(params))

		if self._drag_params is not None:
			self._set_drag_params(params)

	def _correct(self, params):
		'''Observe the written frame; new params if the secant moves a value
		by at least one panel step (1 %), else None.'''
		if not self._models or self.st is None or self.applied is None: return None
		out, changed = dict(params), False

		for key, (axis, side, edge0, model, target) in self._models.items():
			model.observe(self.applied[key], self._frame_edge(axis, side))
			value = om.clamp(model.solve(target), *_LIVE_LIMITS['scale'])
			if int(round(value * 100.)) != int(round(self.applied[key] * 100.)):
				out[key] = value
				changed = True

		return out if changed else None

	def _set_drag_params(self, params):
		self._drag_params = dict(params)
		if self.st is not None:
			self.st['params'] = dict(params)

	def panel_wrote(self):
		'''Called by the panel after every write: our own edit, not an outside one.'''
		try:
			self.accept_geometry()
			self._refresh()
			self._sel_sig = self._selection_signature()
			self.request_repaint()
		except Exception:
			co._log.exception('{}.panel_wrote'.format(self.NAME))

	def _selection_signature(self):
		'''Cheap selection signature of the active layer: for each contour with
		a selection, its index, selected-node count and selected bounding box.
		(Reading every node's .selected through PythonQt is too slow per tick.)
		Note: flContour.hasSelected needs a SelectionMode argument in FL8 (no
		argument fails); getSelectedNodes() takes none and returns list or None.'''
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

	# - Handles -------------------------
	def _build_handles(self):
		H = co.Handle
		handles = []

		for code, sx, sy in _FRAME_POINTS:
			shape = om.SHAPE_SQUARE if sx and sy else om.SHAPE_BAR_V if sx else om.SHAPE_BAR_H
			axis = om.AXIS_XY if sx and sy else om.AXIS_X if sx else om.AXIS_Y
			handles.append(H('scale_' + code, self._frame_anchor(sx, sy), shape, 6., axis, _CURSORS[(sx, sy)], 'primary',
			                 tooltip='Width / Height' if sx and sy else 'Width' if sx else 'Height'))

		for code, sx, sy in (('T', 0, 1), ('R', 1, 0), ('B', 0, -1), ('L', -1, 0)):
			handles.append(H('stem_' + code, self._stem_anchor(sx, sy), om.SHAPE_CIRCLE, 5.5, om.AXIS_X if sx else om.AXIS_Y,
			                 _CURSORS[(sx, sy)], 'stem', tooltip='Vertical stem' if sx else 'Horizontal stem'))

		handles.append(H('origin', self._origin_anchor, om.SHAPE_CIRCLE, 7., om.AXIS_XY, QtCore.Qt.CrossCursor, 'primary', tooltip='Transform origin'))

		self.strip = CanvasIconStrip(self, self._strip_origin, [
			('close', None, 'Close Live Edit', self._close, True),
			('recapture', 'refresh', 'Recapture: rebuild the Live Axis from the current outline', self._recapture, True),
			('reset', 'axis_remove', 'Axis reset: neutral controls for this layer', self._reset, False),
			('metrics', 'metrics_advance_alt', '', lambda: self._toggle('metrics'), False, lambda: self._option('metrics')),
			('anchors', 'icon_anchor', '', lambda: self._toggle('anchors'), False, lambda: self._option('anchors')),
		])
		handles.extend(self.strip.handles)

		self.handles = handles
		self.handle = dict((h.key, h) for h in handles)

	def _ready(self):
		return self.st is not None and self.target == self.st['target']

	def _frame_point(self, mapping, sx, sy, pad_px=0.):
		'''View (x, y) of a frame point. The frame is deslanted: the point is
		re-slanted, so the quad is a parallelogram in italic fonts. pad_px
		pushes it outward (screen px).'''
		x0, y0, x1, y1 = self.st['frame']
		pad = mapping.len_to_font(pad_px) if pad_px else 0.
		x = _side_coord(x0 - pad, x1 + pad, sx)
		y = _side_coord(y0 - pad, y1 + pad, sy)
		return mapping.to_view_xy(*om.reslant(x, y, self.st['slant']))

	def _frame_anchor(self, sx, sy):
		def anchor(mapping):
			if not self._ready(): return None
			return self._frame_point(mapping, sx, sy, self.PAD_PX)
		return anchor

	def _ring_px(self, mapping):
		'''Stem ring radius (view px): sized from the captured frame (clamped
		on screen), then following the scale of the output frame.'''
		src, cur = self.st['src_frame'], self.st['frame']
		side0 = min(src[2] - src[0], src[3] - src[1])
		side1 = min(cur[2] - cur[0], cur[3] - cur[1])
		follow = side1 / side0 if side0 > 0 else 1.
		lo, hi = self.STEM_RING_PX
		return max(om.clamp(.2 * side0 * mapping.px_per_unit, lo, hi) * follow, 1.)

	def _seed(self):
		seed = self.st['seed'] or (100., 100.)
		return max(seed[0], 1.), max(seed[1], 1.)

	def _stem_anchor(self, sx, sy):
		def anchor(mapping):
			if not self._ready(): return None
			cx, cy = self._frame_point(mapping, 0, 0)
			r = self._ring_px(mapping)
			seed_v, seed_h = self._seed()
			pr = self.st['params']
			return (cx + sx * r * pr['stem_x'] / seed_v, cy - sy * r * pr['stem_y'] / seed_h)
		return anchor

	def _origin_point(self, mapping, code):
		if code == 'BS':
			return mapping.to_view_xy(0., 0.)
		for c, sx, sy in _ORIGIN_POINTS:
			if c == code:
				return self._frame_point(mapping, sx, sy)
		return None

	def _origin_anchor(self, mapping):
		if not self._ready(): return None
		if self._origin_view is not None:
			return (self._origin_view.x(), self._origin_view.y())
		return self._origin_point(mapping, self.st['params']['origin'])

	def _nearest_origin(self, view_point):
		best, best_d = self.st['params']['origin'], None
		for code in LIVE_ORIGIN_CODES.values():
			x, y = self._origin_point(self.mapping, code)
			d = (x - view_point.x())**2 + (y - view_point.y())**2
			if best_d is None or d < best_d:
				best, best_d = code, d
		return best

	def _strip_origin(self, mapping):
		'''Close icon slot: diagonally off the frame's top-right handle, the
		strip extending left; next to the banner when nothing is captured.'''
		if not self._ready():
			return (16., 16., 1., False)
		x, y = self._frame_point(mapping, 1, 1, self.PAD_PX)
		return (x + self.STRIP_OFFSET_PX, y - self.STRIP_OFFSET_PX, -1., True)

	# - Overlay hooks -------------------
	def on_attach(self):
		self._refresh()

	def on_target_changed(self, mapping):
		self._refresh()
		if self.target is not None and (self.st is None or self.target != self.st['target']):
			self._call('live_capture')		# layer switch keeps the axis; glyph switch captures
			self._refresh()
		self._sel_sig = self._selection_signature()
		self.request_repaint()

	def on_geometry_changed(self):
		if self.drag is None and self._ready():
			self._recapture()				# edited with FontLab's tools (or undo)

	def on_tick(self):
		if not self._panel_alive():
			type(self).stop()				# the panel is gone
			return
		if self._pending is not None:
			self._push(self._pending, now=True)
		elif self.drag is None:
			if self._ready() and self._sel_throttle.ready():
				if self._selection_signature() != self._sel_sig:
					self._recapture()		# selection decides the mode
					return
			self._refresh()					# pick up changes made in the panel

	def on_handle_click(self, handle, drag):
		self.strip.click(handle)

	# - Strip actions -------------------
	def _close(self):
		if self._panel_alive():
			self.panel.live_closed()
		else:
			type(self).stop()

	def _recapture(self):
		self._call('live_recapture')
		self._refresh()
		self._sel_sig = self._selection_signature()
		self.request_repaint()

	def _reset(self):
		self._call('live_reset')
		self._refresh()

	def _toggle(self, option):
		self._call('live_toggle', option)	# the panel recaptures with the new attributes
		self._refresh()
		self._sel_sig = self._selection_signature()
		self.request_repaint()

	def _option(self, option):
		return self.st is not None and self.st['options'][option]

	def _update_options(self):
		'''Metrics / anchors icons: lit while the panel option is on; disabled
		in selection mode, which drives geometry only.'''
		whole = self.st is not None and self.st['selection'] is None
		for option, label in (('metrics', 'metrics'), ('anchors', 'anchors')):
			handle = self.strip.handle(option)
			handle.enabled = whole
			if not whole:
				handle.tooltip = 'Process {}: not used in selection mode'.format(label)
			else:
				on = self.st['options'][option]
				active = option in self.st['process']
				handle.tooltip = 'Process {}: {}{} (click to turn {})'.format(
					label, 'ON' if on else 'off',
					'' if active or not on else ' - nothing to process on this glyph',
					'off' if on else 'on')

	# - Drag ----------------------------
	def on_drag_start(self, handle, drag):
		self._press = None
		if self.strip.owns(handle) or not self._ready(): return

		params = dict(self.st['params'])
		self._press = {'params': params, 'ring': self._ring_px(self.mapping)}
		self._drag_params = dict(params)
		self._models = {}

		if handle.key.startswith('scale_'):
			sx, sy = self._sides(handle.key[len('scale_'):])
			for key, axis, side in self._frame_keys(sx, sy):
				edge0 = self._frame_edge(axis, side)
				anchor = self._origin_coord(axis, params['origin'])
				model = om.EdgeSecant.proportional(params[key], edge0, anchor)
				self._models[key] = [axis, side, edge0, model, edge0]

	def on_drag_move(self, handle, drag):
		if self._press is None: return
		if handle.key == 'origin':
			self._origin_view = drag.cur_view
			return

		params = self._params_for(handle, drag)
		self._set_drag_params(params)
		self._push(params)

	def on_drag_end(self, handle, drag):
		if self._press is None: return
		if handle.key == 'origin':
			params = dict(self._drag_params)
			params['origin'] = self._nearest_origin(drag.cur_view)
			self._origin_view = None
		else:
			params = self._params_for(handle, drag)

		self._set_drag_params(params)
		self._push(params, now=True)
		self._press = self._drag_params = None
		self._models = {}
		self._refresh()

	def on_drag_cancel(self, handle, drag):
		self._origin_view = None
		if self._press is not None:
			params = self._press['params']
			self._press = self._drag_params = None
			self._models = {}
			self._pending = None
			self._push(params, now=True)
		self._refresh()

	# - Drag mappings -------------------
	@staticmethod
	def _sides(code):
		for c, sx, sy in _FRAME_POINTS:
			if c == code: return sx, sy
		return 0, 0

	def _frame_keys(self, sx, sy):
		'''(param key, axis, side) driven by a frame handle. Proportional:
		every handle drives width only (the panel copies it to height).'''
		if self.st['proportional']:
			return [('width', 'x', sx)] if sx else [('width', 'y', sy)]
		keys = []
		if sx: keys.append(('width', 'x', sx))
		if sy: keys.append(('height', 'y', sy))
		return keys

	def _frame_edge(self, axis, side):
		x0, y0, x1, y1 = self.st['frame']
		if axis == 'x':
			return x0 if side < 0 else x1
		return y0 if side < 0 else y1

	def _origin_coord(self, axis, code):
		'''Origin coordinate on this axis (deslanted frame): the starting
		guess of the edge model; the secant corrects for Delta's realignment.'''
		if code == 'BS': return 0.
		x0, y0, x1, y1 = self.st['frame']
		for c, sx, sy in _ORIGIN_POINTS:
			if c == code:
				return _side_coord(x0, x1, sx) if axis == 'x' else _side_coord(y0, y1, sy)
		return 0.

	def _params_for(self, handle, drag):
		'''Params for the current drag position, from the press state (never accumulated).'''
		params = dict(self._press['params'])
		group, code = handle.key.split('_', 1)

		if group == 'scale':
			dx, dy = drag.delta_font
			dxs = dx - dy * math.tan(self.st['slant'])		# horizontal component, deslanted
			for key, m in self._models.items():
				axis, side, edge0, model = m[:4]
				m[4] = edge0 + (dxs if axis == 'x' else dy)
				params[key] = om.clamp(model.solve(m[4]), *_LIVE_LIMITS['scale'])

		elif group == 'stem':
			ring = self._press['ring']
			seed_v, seed_h = self._seed()
			lo, hi = _LIVE_LIMITS['stem']
			dvx, dvy = drag.delta_view
			if code in ('L', 'R'):
				out_px = dvx if code == 'R' else -dvx
				factor = om.clamp(params['stem_x'] / seed_v + out_px / ring, lo, hi)
				params['stem_x'] = max(1., seed_v * factor)
			else:
				out_px = -dvy if code == 'T' else dvy
				factor = om.clamp(params['stem_y'] / seed_h + out_px / ring, lo, hi)
				params['stem_y'] = max(1., seed_h * factor)

		return params

	# - Painting ------------------------
	def _value_line(self):
		pr = self.st['params']
		if self.st['proportional']:
			parts = ['W=H {:.0f}%'.format(pr['width'] * 100.)]
		else:
			parts = ['W {:.0f}%  H {:.0f}%'.format(pr['width'] * 100., pr['height'] * 100.)]
		parts.append('stem V {:.0f} u  H {:.0f} u'.format(pr['stem_x'], pr['stem_y']))
		parts.append('origin {}'.format(pr['origin']))
		if abs(self.st['slant']) > 1e-9:
			parts.append('italic {:g}°'.format(round(math.degrees(self.st['slant']), 1)))
		if self.st['selection']:
			parts.append('[selection: {} nodes]'.format(self.st['selection']))
		elif self.st['process']:
			parts.append('also moves: {}'.format(' + '.join(self.st['process'])))
		return '   '.join(parts)

	def paint_overlay(self, p, mapping):
		c = self.colors

		if not self._ready():
			text = self.problem if self.st is None else 'nothing captured on this glyph or layer'
			x = 16. + self.strip.width(False) - 4.
			self.draw_label(p, QtCore.QPointF(x, 16.), '{}: {}'.format(app_name, text), 'LM',
			                color=c['error'] if self.st is None else None, offset=0.)
			return

		# - Frame quad (parallelogram in italic)
		quad = [self._frame_point(mapping, sx, sy, self.PAD_PX) for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1))]
		path = QtGui.QPainterPath()
		path.moveTo(quad[0][0], quad[0][1])
		for x, y in quad[1:]:
			path.lineTo(x, y)
		path.closeSubpath()
		p.setPen(co.cosmetic_pen(c['active'], 1.))
		p.setBrush(co.solid_brush(c['active'], 12))
		p.drawPath(path)

		# - Stem ring
		cx, cy = self._frame_point(mapping, 0, 0)
		ring = self._ring_px(mapping)
		seed_v, seed_h = self._seed()
		pr = self.st['params']
		p.setPen(co.cosmetic_pen(c['stem'], 1., QtCore.Qt.DashLine))
		p.setBrush(co.no_brush())
		co.draw_ellipse(p, cx, cy, ring * pr['stem_x'] / seed_v, ring * pr['stem_y'] / seed_h)

		# - Origin snap targets while dragging the cross
		if self._origin_view is not None:
			nearest = self._nearest_origin(self._origin_view)
			for code in LIVE_ORIGIN_CODES.values():
				x, y = self._origin_point(mapping, code)
				hot = code == nearest
				p.setPen(co.cosmetic_pen(c['active'], 1.5 if hot else 1.))
				p.setBrush(co.solid_brush(c['active'], 255 if hot else 60))
				co.draw_ellipse(p, x, y, 4., 4.)

		# - Values under the frame; warnings as a red second line
		left = min(x for x, y in quad)
		bottom = max(y for x, y in quad)
		rect = self.draw_label(p, QtCore.QPointF(left, bottom), self._value_line(), 'TL', offset=10.)
		if self.st['warnings']:
			self.draw_label(p, QtCore.QPointF(rect.left() - 4., rect.bottom()), '   '.join(self.st['warnings']), 'TL',
			                color=c['error'], offset=4.)

	def paint_handle(self, p, handle, x, y, hot):
		if self.strip.paint(p, handle, x, y, hot):
			return True

		if handle.key == 'origin':
			c = self.colors
			r = handle.radius + (1.5 if hot else 0.)
			p.setPen(co.cosmetic_pen(c['active'], 2. if hot else 1.5))
			p.setBrush(co.solid_brush(c['label_bg']))
			co.draw_ellipse(p, x, y, r * .55, r * .55)
			p.drawLine(QtCore.QPointF(x - r * 1.6, y), QtCore.QPointF(x + r * 1.6, y))
			p.drawLine(QtCore.QPointF(x, y - r * 1.6), QtCore.QPointF(x, y + r * 1.6))
			return True

		return False


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
