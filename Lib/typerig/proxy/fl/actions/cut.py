# MODULE: Typerig / Proxy / FontLab / Actions / Cut
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function

import fontlab as fl6
import fontgate as fgt

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.algo.stroke_sep_v3 import StrokeSepV3
from typerig.core.algo.stroke_sep_common import apply_cuts_to_layer, check_contour_compatibility

# - Init ------------------------------------------------------------------------
__version__ = '1.1'
active_workspace = pWorkspace()

# - Actions ---------------------------------------------------------------------
class TRCutActionCollector(object):
	'''Collection of cut and stroke separation tools operating via the FontLab proxy.

	All methods are static. They operate on eGlyph objects (via getProcessGlyphs)
	and bridge to the TypeRig Core API through the trGlyph eject/mount pattern.
	'''

	@staticmethod
	def stroke_separate_v3(pMode, pLayers, sample_step=20.0, beta_min=1.5, overlap=10, debug=False):
		'''Separate a stroke glyph into its component strokes using the V3 hybrid pipeline.

		Analyzes the active layer with the MAT-based stroke separator, then propagates
		the derived cuts to all compatible layers specified by pLayers.

		Selected contours are processed if a selection exists; otherwise all contours
		on the glyph are processed.

		Arguments:
			pMode (int): Glyph processing scope.
				0 - Current active glyph
				1 - All glyphs in current text window
				2 - All selected glyphs
				3 - All glyphs in font
			pLayers (tuple): Layer filter (active, masters, specific, special).
			sample_step (float): MAT sampling step in font units (default 20.0).
			beta_min (float): Minimum concavity angle threshold in radians (default 1.5).
			overlap (float): Overlap extension past cut boundaries in font units (default 20).
			debug (bool): Emit verbose debug output from the separator (default False).
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			# - Active layer is the analysis reference
			analysis_layer = glyph.layer().name
			work_layers = glyph._prepareLayers(pLayers)

			# - Bridge to TR proxy for Core API access
			g = trGlyph(glyph.fl)

			# - Get all core contours on the analysis layer
			tr_analysis = g.find_layer(analysis_layer)
			if tr_analysis is None:
				output(2, 'StrokeSep', '{}: analysis layer {!r} not found'.format(
					glyph.name, analysis_layer))
				continue

			analysis_core = tr_analysis.eject()
			all_core_contours = analysis_core.contours

			if not all_core_contours:
				output(2, 'StrokeSep', '{}: no contours on layer {!r}'.format(
					glyph.name, analysis_layer))
				continue

			# - Detect selected contours (selection drives which contours are analysed)
			selection = glyph.selectedAtContours(analysis_layer)

			if selection:
				sel_cids = sorted(set(cid for cid, nid in selection))
				source_contours = [all_core_contours[i] for i in sel_cids
				                   if i < len(all_core_contours)]
			else:
				sel_cids = None
				source_contours = all_core_contours

			# - Run V3 analysis on the reference layer
			sep = StrokeSepV3(beta_min=beta_min, sample_step=sample_step, debug=debug)
			result = sep.analyze(source_contours)

			if not result.cuts:
				output(1, 'StrokeSep', '{}: no cuts found on layer {!r}'.format(
					glyph.name, analysis_layer))
				continue

			# - Apply cuts to each target layer
			layers_done = []
			layers_skipped = []

			for layer_name in work_layers:
				tr_layer = g.find_layer(layer_name)
				if tr_layer is None:
					layers_skipped.append((layer_name, 'layer not found'))
					continue

				layer_core = tr_layer.eject()
				target_all = layer_core.contours

				if not target_all:
					layers_skipped.append((layer_name, 'empty'))
					continue

				if sel_cids is not None:
					target_contours = [target_all[i] for i in sel_cids
					                   if i < len(target_all)]
				else:
					target_contours = target_all

				if layer_name == analysis_layer:
					separated = sep.execute(result, source_contours, overlap=overlap)
				else:
					try:
						check_contour_compatibility(source_contours, target_contours)
					except ValueError as e:
						layers_skipped.append((layer_name, str(e)))
						continue

					separated = apply_cuts_to_layer(
						result, source_contours, target_contours, overlap=overlap)

				# - Replace source contours with separated results; keep untouched ones intact
				if sel_cids is not None:
					sel_set = set(sel_cids)
					new_contours = [c for i, c in enumerate(target_all) if i not in sel_set]
					new_contours.extend(separated)
					layer_core.shapes[0].contours = new_contours
				else:
					layer_core.shapes[0].contours = separated

				tr_layer.mount(layer_core)
				layers_done.append((layer_name, len(separated)))

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tStroke Separate (V3) @ {}.'.format(
				glyph.name, '; '.join(name for name, _ in layers_done)))

			# - Report
			for layer_name, piece_count in layers_done:
				output(0, 'StrokeSep', '{} [{}]: {} pieces'.format(
					glyph.name, layer_name, piece_count))
			for layer_name, reason in layers_skipped:
				output(1, 'StrokeSep', '{} [{}]: skipped ({})'.format(
					glyph.name, layer_name, reason))

		active_workspace.getCanvas(True).refreshAll()
