# MODULE: TypeRig / Proxy / FontLab / GUI / Toolbar Actions
# NOTE	: Scope state + button callbacks of the unified TypeRig Toolbar
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
import traceback

import fontlab as fl6
from PythonQt import QtCore

from typerig.core.base.lib_keys import NODE_COLLINEAR_LIB_KEY, NODE_MONOLINE_LIB_KEY

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.actions.curve import TRCurveActionCollector
from typerig.proxy.fl.actions.contour import TRContourActionCollector

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.dialogs import TRMasterValuesDLG

# - Init ----------------------------------
__version__ = '1.3'
tool_name = 'TypeRig Toolbar'

# - Helpers -------------------------------
class Modifiers(object):
	'''Keyboard modifiers at the moment of the click. Read it BEFORE opening any dialog.
	On macOS Qt reports Cmd as Control and Ctrl as Meta: both count as <ctrl>.'''
	def __init__(self):
		mods = QtGui.QApplication.keyboardModifiers()
		self.alt = bool(mods & QtCore.Qt.AltModifier)
		self.shift = bool(mods & QtCore.Qt.ShiftModifier)
		self.ctrl = bool(mods & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier))

def guarded(callback, name=''):
	'''Wrap a button callback: an exception prints a traceback and never breaks the panel'''
	def run(*args):
		try:
			callback()
		except Exception:
			print('{}: "{}" failed:\n{}'.format(tool_name, name, traceback.format_exc()))
	return run

# - Shared scope state --------------------
class TRToolbarState(object):
	'''The scope every FL action is called with (replaces the old module global pMode / pLayers trick).

	mode  : 0 active glyph | 1 glyph window | 2 font window selection  (pMode)
	layers: property, the pLayers value: (active, masters, masks, services) tuple, or - with the layer
	        selection dialog - the live list of checked layer names
	'''
	def __init__(self):
		self.mode = 0
		self.layer_scope = 'masters' # 'active' | 'masters' | 'selected'
		self.dlg_layer = None # TRLayerSelectNEW, set by the masthead

	@property
	def layers(self):
		if self.layer_scope == 'selected' and self.dlg_layer is not None:
			try:
				return self.dlg_layer.tab_masters.getTable() # Read live: edits in the dialog apply at once
			except Exception:
				pass
		return (self.layer_scope == 'active', self.layer_scope == 'masters', False, False)

# - Callbacks -----------------------------
class TRToolbarActions(object):
	'''Everything the toolbar buttons do. Every method is a no-argument callback; scope comes from the state.'''
	def __init__(self, state):
		self.state = state
		self.widgets = {} # button name -> widget (filled by the builder)

		# - Data banks for copy / paste operations
		self.ext_target = {} # Align target: layer -> node
		self.slope_bank = {}
		self.curve_bank = {}

	def noop(self):
		'''Option buttons only hold a state that the actions read from the widget'''
		pass

	# - Scope / widget access ----------------
	@property
	def mode(self): return self.state.mode

	@property
	def layers(self): return self.state.layers

	def checked(self, name):
		widget = self.widgets.get(name)
		return bool(widget.isChecked()) if widget is not None else False

	def uncheck(self, name):
		widget = self.widgets.get(name)
		if widget is not None: widget.setChecked(False)

	# - Nodes --------------------------------
	def node_insert(self, time):
		mods = Modifiers()
		if mods.ctrl: TRNodeActionCollector.node_insert_dlg(self.mode, self.layers, mods.alt) # FL dialog (time slider)
		else: TRNodeActionCollector.node_insert(self.mode, self.layers, time, mods.alt)

	def node_insert_extreme(self):
		TRNodeActionCollector.node_insert_extreme(self.mode, self.layers)

	def node_remove(self):
		TRNodeActionCollector.node_remove(self.mode, self.layers)

	def node_round(self):
		mods = Modifiers()
		TRNodeActionCollector.node_round(self.mode, self.layers, mods.alt, mods.shift)

	def node_smooth(self, set_smooth):
		TRNodeActionCollector.node_smooth(self.mode, self.layers, set_smooth)

	# - Corners (values come from the FL popup dialogs) ---
	def corner_mitre(self):
		TRNodeActionCollector.corner_mitre_dlg(self.mode, self.layers)

	def corner_round(self):
		TRNodeActionCollector.corner_round_dlg(self.mode, self.layers)

	def corner_loop(self):
		TRNodeActionCollector.corner_loop_dlg(self.mode, self.layers)

	def corner_trap(self):
		smooth = not Modifiers().alt # Alt: non-smooth basic trap
		TRNodeActionCollector.corner_trap_dlg(self.mode, self.layers, smooth)

	def corner_rebuild(self):
		TRNodeActionCollector.corner_rebuild(self.mode, self.layers)

	# - Align --------------------------------
	def align(self, align_mode):
		TRNodeActionCollector.nodes_align(self.mode, self.layers, align_mode,
			intercept=self.checked('shift_intercept'),
			keep_relations=self.checked('shift_keep_dimension'),
			smart_shift=self.checked('shift_smart'),
			ext_target=self.ext_target,
			lerp_shift=self.checked('shift_interpolate'),
			extrapolate=self.checked('extrapolate'))

	def target_toggle(self):
		'''Pick (1 node = that node, several = center of selection) / clear the per-master align target'''
		self.ext_target = {}
		if not self.checked('node_target'): return

		glyph = eGlyph()
		for layer in glyph._prepareLayers(self.layers):
			selection = glyph.selectedNodes(layer)

			if len(selection) > 1:
				med_x = round(sum([node.x for node in selection]) / len(selection))
				med_y = round(sum([node.y for node in selection]) / len(selection))
				self.ext_target[layer] = fl6.flNode(QtCore.QPointF(med_x, med_y))
			elif len(selection) == 1:
				self.ext_target[layer] = selection[0]

		if not self.ext_target:
			print('{}: No nodes selected for the align target.'.format(tool_name))
			self.uncheck('node_target')

	def target_collapse(self):
		if not (self.checked('node_target') and self.ext_target): return

		glyph = eGlyph()
		wLayers = glyph._prepareLayers(self.layers)

		for layer in wLayers:
			if layer in self.ext_target:
				for node in glyph.selectedNodes(layer):
					node.x = self.ext_target[layer].x
					node.y = self.ext_target[layer].y

		glyph.update()
		glyph.updateObject(glyph.fl, 'Glyph: {}; Nodes collapsed; Layers:\t {}'.format(glyph.name, '; '.join(wLayers)))

	# - Curves -------------------------------
	def segment_convert(self, to_curve):
		TRCurveActionCollector.segment_convert(self.mode, self.layers, to_curve)

	def curve_optimize(self, method, p0=0., p1=0.):
		TRCurveActionCollector.curve_optimize(self.mode, self.layers, (method, p0, p1))

	def curve_optimize_dlg(self, method):
		TRCurveActionCollector.curve_optimize_dlg(self.mode, self.layers, method)

	def curve_tension_push(self):
		TRCurveActionCollector.hobby_tension_push(self.mode, self.layers)

	def hobby_copy(self):
		self.curve_bank = TRCurveActionCollector.hobby_tension_copy(eGlyph(), self.layers)

	def hobby_paste(self, swap):
		TRCurveActionCollector.curve_optimize_by_dict(self.mode, self.layers, 'hobby', self.curve_bank, swap)

	# - Contours -----------------------------
	def contour_close(self):
		TRContourActionCollector.contour_close(self.mode, self.layers)

	def contour_winding(self, ccw):
		TRContourActionCollector.contour_set_winding(self.mode, self.layers, ccw)

	def contour_start(self):
		TRContourActionCollector.contour_set_start(self.mode, self.layers)

	def contour_start_next(self, set_previous):
		TRContourActionCollector.contour_set_start_next(self.mode, self.layers, set_previous)

	def contour_smart_start(self, control):
		TRContourActionCollector.contour_smart_start(self.mode, self.layers, control)

	def contour_order(self, sort_order, reverse):
		TRContourActionCollector.contour_set_order(self.mode, self.layers, sort_order, reverse)

	def contour_bool(self, operation):
		TRContourActionCollector.contour_bool(self.mode, self.layers, operation, Modifiers().alt) # Alt: reverse order

	# - End caps -----------------------------
	def cap_normal(self):
		TRNodeActionCollector.cap_normal(eGlyph(), self.layers)

	def cap_round(self):
		TRNodeActionCollector.cap_round(eGlyph(), self.layers, Modifiers().alt) # Alt: keep path length

	def cap_rebuild(self):
		TRNodeActionCollector.cap_rebuild(eGlyph(), self.layers)

	# - Collinear & monoline (per-master snap targets in the font lib) ---
	def read_snap_lib(self, font, lib_key):
		'''{master name: width} stored in the font lib, {} when absent or malformed'''
		try:
			data = font.fl.packageLib[lib_key]
			if isinstance(data, dict): return {k: float(v) for k, v in data.items()}
		except Exception:
			pass
		return {}

	def resolve_snap_lookup(self, mods, lib_key, title, message):
		'''Returns (snap_lookup, proceed). Shift: no snap. Ctrl: edit targets in the master values dialog.
		Otherwise the targets stored in the font. Modifiers are read BEFORE the dialog opens.'''
		font = pFont()
		if mods.shift: return None, True

		if mods.ctrl:
			dlg = TRMasterValuesDLG(font=font, lib_key=lib_key, title=title, message=message, value_label='Width',
				value_type=float, value_default=100.0, value_range=(1.0, 10000.0, 1.0), autoload=True)
			dlg.exec_()
			return (dlg.values, True) if dlg.values is not None else (None, False) # Cancel aborts the action

		return self.read_snap_lib(font, lib_key), True

	def make_collinear(self):
		mods = Modifiers()
		snap_lookup, proceed = self.resolve_snap_lookup(mods, NODE_COLLINEAR_LIB_KEY, 'Collinear - per-master target widths',
			'Per-master target stem width for the equalize step.\nSnap kicks in within +/-25% of the measured width.')
		if proceed: TRNodeActionCollector.make_collinear(eGlyph(), self.layers, equalize=mods.alt, snap_lookup=snap_lookup)

	def make_monoline(self):
		mods = Modifiers()
		snap_lookup, proceed = self.resolve_snap_lookup(mods, NODE_MONOLINE_LIB_KEY, 'Monoline - per-master target widths',
			'Per-master target stem width for the monoline regularization.\nSnap kicks in within +/-25% of the measured width.')
		if proceed: TRNodeActionCollector.make_monoline(eGlyph(), self.layers, preserve_taper=mods.alt, snap_lookup=snap_lookup)

	# - Slope --------------------------------
	def slope_copy(self):
		self.slope_bank = TRNodeActionCollector.slope_copy(eGlyph(), self.layers)

	def slope_italic(self):
		self.slope_bank = TRNodeActionCollector.slope_italic(eGlyph(), self.layers)

	def slope_paste(self, flip):
		pivot_max = Modifiers().alt # Alt swaps the pivot: highest instead of lowest node
		TRNodeActionCollector.slope_paste(self.mode, self.layers, self.slope_bank, (pivot_max, flip))
