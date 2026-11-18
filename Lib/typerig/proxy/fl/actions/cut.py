# MODULE: Typerig / Proxy / FontLab / Actions / Cut
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function

import fontlab as fl6
import fontgate as fgt

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.algo.stroke_sep import StrokeSep
from typerig.core.algo.stroke_sep_common import apply_cuts_to_layer, check_contour_compatibility

# - Init ------------------------------------------------------------------------
__version__ = '1.2'
active_workspace = pWorkspace()

# - Helpers ---------------------------------------------------------------------
def group_nodes_by_neighbors(nodes):
	'''Group nodes into pairs of neighbors using eNode wrapper'''
	if len(nodes) < 4:
		return [], []
	
	pairs = []
	used = set()
	
	for i, node in enumerate(nodes):
		if i in used:
			continue
		
		# Wrap in eNode for neighbor detection
		en = eNode(node)
		
		# Find the neighbor of this node among remaining nodes
		for j, other in enumerate(nodes):
			if j in used or i == j:
				continue
			
			# Check if nodes are neighbors using eNode methods
			next_on = en.getNextOn(False)
			prev_on = en.getPrevOn(False)
			
			if (next_on is not None and next_on.fl == other) or \
			   (prev_on is not None and prev_on.fl == other):
				pairs.append((node, other))
				used.add(i)
				used.add(j)
				break
	
	# Return two pairs (or as many as we found)
	if len(pairs) >= 2:
		return list(pairs[0]), list(pairs[1])
	elif len(pairs) == 1:
		return list(pairs[0]), []
	return [], []

def align_pair(nodes, mode):
	'''Align a pair of nodes based on mode (T=top, B=bottom, C=center)'''
	if len(nodes) != 2:
		return
	
	n1, n2 = nodes
	
	if mode == 'T':
		# Align both to top (max Y)
		target_y = max(n1.y, n2.y)
		n1.y = target_y
		n2.y = target_y
	
	elif mode == 'B':
		# Align both to bottom (min Y)
		target_y = min(n1.y, n2.y)
		n1.y = target_y
		n2.y = target_y
	
	elif mode == 'C':
		# Align both to vertical center
		target_x = (n1.x + n2.x) / 2.0
		n1.x = target_x
		n2.x = target_x

def auto_align_mode(pair):
	'''Detect the correct alignment mode for a node pair at a cut junction.

	Uses the direction of the segment leaving each junction node into the
	contour interior (away from the other pair node) as the signal:

	  - Interior segments predominantly horizontal -> arm side -> 'C'
	  - Interior segments predominantly vertical   -> stem side:
	      Both interior neighbours above the pair  -> bottom L-junction -> 'B'
	      Both interior neighbours below the pair  -> top L-junction    -> 'T'
	      Interior neighbours on opposite sides    -> T-junction        -> 'C'

	Arguments:
		pair (list): Two FL on-curve node objects that are neighbors.

	Returns:
		str: 'C', 'T', or 'B'.
	'''
	n1, n2 = pair
	total_dx    = 0.0
	total_dy    = 0.0
	interior_ys = []

	for node, other in ((n1, n2), (n2, n1)):
		en      = eNode(node)
		next_on = en.getNextOn(False)
		prev_on = en.getPrevOn(False)

		# Pick the neighbour that is NOT the other pair node
		interior = None
		if next_on is not None and next_on.fl != other:
			interior = next_on.fl
		elif prev_on is not None and prev_on.fl != other:
			interior = prev_on.fl

		if interior is None:
			continue

		total_dx += abs(interior.x - node.x)
		total_dy += abs(interior.y - node.y)
		interior_ys.append(interior.y)

	# Horizontal interior segments -> arm side -> center X
	if not interior_ys or total_dx >= total_dy:
		return 'C'

	# Vertical interior segments -> stem side
	# L-junction: both interior neighbours on the same side of the pair
	# T-junction: interior neighbours on opposite sides -> no vertical snap
	avg_y_pair = (n1.y + n2.y) / 2.0

	if all(y > avg_y_pair for y in interior_ys):
		return 'B'   # all interior above -> junction is at the bottom
	elif all(y < avg_y_pair for y in interior_ys):
		return 'T'   # all interior below -> junction is at the top
	else:
		return 'C'   # T-junction: interior nodes on both sides, no snap

# - Actions ---------------------------------------------------------------------
class TRCutActionCollector(object):
	'''Collection of cut and stroke separation tools operating via the FontLab proxy.

	All methods are static. They operate on eGlyph objects (via getProcessGlyphs)
	and bridge to the TypeRig Core API through the trGlyph eject/mount pattern.
	'''

	@staticmethod
	def stroke_separate_v3(pMode, pLayers, sample_step=20.0, beta_min=1.5, overlap=0, debug=False):
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

			# - Run analysis on the reference layer
			sep = StrokeSep(beta_min=beta_min, sample_step=sample_step, debug=debug)
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

	@staticmethod
	def align_auto(pMode, pLayers):
		'''Auto overlap align: classify and align two neighbor-pairs at a cut junction.

		Select 4 on-curve nodes (2 pairs) across two contours at a cut boundary. Each pair is aligned
		independently based on its parent contour's aspect ratio - no cut is performed.
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer)
				if len(selection) < 4: continue

				pair_first, pair_second = group_nodes_by_neighbors(selection)

				if len(pair_first) == 2: align_pair(pair_first, auto_align_mode(pair_first))
				if len(pair_second) == 2: align_pair(pair_second, auto_align_mode(pair_second))

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: {}; Auto Overlap Align; Layers: {}'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def cut_align_auto(pMode, pLayers, expanded=False):
		'''Slice the contour at the selected nodes, then auto-align the neighbor pairs at the cut junction.'''
		from typerig.proxy.fl.actions.contour import TRContourActionCollector

		TRContourActionCollector.contour_slice(pMode, pLayers, expanded)
		TRCutActionCollector.align_auto(pMode, pLayers)
