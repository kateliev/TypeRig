# MODULE: Typerig / Proxy / FontLab / Actions / Node
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2024 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ---------------------------------------------
from __future__ import absolute_import, print_function

import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.base import *
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.curve import eCurveEx
from typerig.proxy.fl.objects.contour import pContour
from typerig.proxy.fl.actions.node import get_segment_starting_at

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.fl.application.app import pWorkspace
from typerig.core.base.message import *

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init -------------------------
__version__ = '2.73'
active_workspace = pWorkspace()

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Helpers --------------------------------------------------------
def get_selected_curves(glyph, layer):
	'''Cubic segments on layer with both on-curve ends selected, as eCurveEx.

	Segments are found by walking the ring from each selected node, not by
	parametric time (see get_segment_ending_at in actions.node). An open
	contour has no segment after its last node, so that node starts none.
	'''
	selection = glyph.selectedNodes(layer, filterOn=True)
	curves = []

	for node in selection:
		contour = node.contour

		if not contour.closed and node.index == len(contour.nodes()) - 1:
			continue

		segment_nodes = get_segment_starting_at(eNode(node))

		if segment_nodes is not None and len(segment_nodes) == 4 and segment_nodes[3] in selection:
			curves.append(eCurveEx(segment_nodes))

	return curves

# - Actions --------------------------------------------------------
class TRCurveActionCollector(object):
	''' Collection of all curve related tools '''

	# - Basic curve actions ----------------------------------------
	@staticmethod
	def segment_convert(pMode:int, pLayers:tuple, to_curve:bool=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)
		undo_msg = 'Convert Segment.'

		# - Process
		for glyph in process_glyphs:
			# - Init
			wLayers = glyph._prepareLayers(pLayers)
			
			# - Get selected nodes. 
			# - NOTE: Only the fist node in every selected segment is important, so we filter for that
			selection = glyph.selectedAtContours(True, filterOn=True)
			selection_dict, selection_filtered = {}, {}
					
			for cID, nID in selection:
				selection_dict.setdefault(cID,[]).append(nID)

			for cID, sNodes in selection_dict.items():
				onNodes = glyph.contours(extend=pContour)[cID].indexOn()
				segments = zip(onNodes, onNodes[1:] + [onNodes[0]]) # Shift and zip so that we have the last segment working
				onSelected = []

				for pair in segments:
					if pair[0] in sNodes and pair[1] in sNodes:
						onSelected.append(pair[1] )

				selection_filtered[cID] = onSelected

			# - Process
			for layer in wLayers:
				for cID, sNodes in selection_filtered.items():
					for nID in reversed(sNodes):
						if to_curve:
							glyph.contours(layer)[cID].nodes()[nID].convertToCurve()
						else:
							glyph.contours(layer)[cID].nodes()[nID].convertToLine()

				glyph.update(layer)

		# - Finish
		output(0, 'TypeRig Curve', undo_msg + '@ {}'.format('; '.join(wLayers)))
		fl6.flItems.notifyChangesApplied(undo_msg, [glyph.fl for glyph in process_glyphs], True)
		active_workspace.getCanvas(True).refreshAll()

	# - Contour optimization -------------------------------------------------
	@staticmethod
	def curve_optimize(pMode:int, pLayers:tuple, method_values:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)
		method_name, p0_value, p1_value = method_values
		undo_msg = 'Optimize curve: {} @ {}.'

		# - Process
		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				for work_segment in get_selected_curves(glyph, layer):
					if method_name == 'tunni':
						work_segment.eqTunni()

					elif method_name == 'hobby':
						curvature = (float(p0_value), float(p1_value))
						work_segment.eqHobbySpline(curvature)

					elif method_name == 'proportional':
						work_segment.eqProportionalHandles((p0_value, p1_value))

				glyph.update(layer)

		# - Finish it
		output(0, 'TypeRig Curve', undo_msg.format(method_name.title(), '; '.join(wLayers)))
		fl6.flItems.notifyChangesApplied(undo_msg, [glyph.fl for glyph in process_glyphs], True)
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def curve_optimize_dlg(pMode:int, pLayers:tuple, method_name:str):

		if method_name == 'tunni':
			value_config = {}
			method_values = (method_name, 0., 0.)

		elif method_name == 'hobby':
			value_config = {'Curvature at P0:':(0., 4., 1., .1), 'Curvature at P1:':(0., 4., 1., .1)}
			method_values = None

		elif method_name == 'proportional':
			value_config = {'Handle length at P0:':(0., 100., 30., 10.), 'Handle length at P1:':(0., 100., 30., 10.)}
			method_values = None

		if method_values is None and len(value_config.keys()):
			dlg_get_input = TRDialogs.TRNSpinDLG('{} optimize curve'.format(method_name.title()), 'Please set curve optimization parameters.', value_config)

			if dlg_get_input.values is None:
				warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
				return

			p0_value, p1_value = dlg_get_input.values
			method_values = (method_name, p0_value, p1_value)

		TRCurveActionCollector.curve_optimize(pMode, pLayers, method_values)

	@staticmethod
	def hobby_tension_copy(glyph:eGlyph, pLayers:tuple) -> dict:
		wLayers = glyph._prepareLayers(pLayers)
		hobby_tension_dict = {}
		
		for layer in wLayers:
			layer_curves = get_selected_curves(glyph, layer)

			if len(layer_curves):
				hobby_tension_dict[layer] = layer_curves[0].curve.solve_hobby_curvature()
		
		return hobby_tension_dict
	
	@staticmethod
	def curve_optimize_by_dict(pMode:int, pLayers:tuple, method_name:basestring, method_dict:dict, swap_values:bool=False):
		'''Layer specific curve optimization, best used together with copy'''
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)
		undo_msg = 'Optimize curve'

		# - Process
		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				for work_segment in get_selected_curves(glyph, layer):
					if method_name == 'hobby':
						if layer in method_dict and len(method_dict[layer]) == 2:
							curvature = method_dict[layer] if not swap_values else (method_dict[layer][1], method_dict[layer][0])
							work_segment.eqHobbySpline(curvature)

					elif method_name == 'proportional':
						if layer in method_dict and len(method_dict[layer]) == 2:
							tension = method_dict[layer] if not swap_values else (method_dict[layer][1], method_dict[layer][0])
							work_segment.eqProportionalHandles(tension)

				glyph.update(layer)

		# - Finish it
		output(0, 'TypeRig Curve', undo_msg + ': {} @ {}.'.format(method_name.title(), '; '.join(wLayers)))
		fl6.flItems.notifyChangesApplied(undo_msg, [glyph.fl for glyph in process_glyphs], True)
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def hobby_tension_push(pMode:int, pLayers:tuple):
		'''Push current curve proportions (handle lengths) to layers selected'''
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)
			base_curves = get_selected_curves(glyph, None)
			undo_msg = 'Copy curve tension'

			for layer in wLayers:
				for work_segment, base_segment in zip(get_selected_curves(glyph, layer), base_curves):
					base_tension = base_segment.curve.solve_hobby_curvature()
					work_segment.eqHobbySpline(base_tension)

				glyph.update(layer)

		# - Finish it
		output(0, 'TypeRig Curve', undo_msg + ' @ {}.'.format('; '.join(wLayers)))
		fl6.flItems.notifyChangesApplied(undo_msg, [glyph.fl for glyph in process_glyphs], True)
		active_workspace.getCanvas(True).refreshAll()


