# MODULE: Typerig / Proxy / FontLab / Actions / MAT Extract
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
from typerig.core.objects.shape import Shape
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.algo.mat_extract import extract_medial_axis

# - Init ------------------------------------------------------------------------
__version__ = '1.0'
active_workspace = pWorkspace()


# - Actions ---------------------------------------------------------------------
class TRMatExtractActionCollector(object):
	'''Medial-axis skeleton extraction tools operating via the FontLab proxy.

	Unlike the stroke-separation action, MAT extraction is a geometric
	derivative of the outline itself — so it runs on the active layer only.
	Propagating the skeleton across masters would produce meaningless
	results because each master has its own geometry and its own MAT.
	'''

	@staticmethod
	def extract_medial_axis(pMode,
							sample_step=5.0,
							beta_min=1.5,
							quality='normal',
							smooth=True,
							drop_corner_legs=True,
							corner_leg_ratio=0.35,
							
							prune_short=None):
		'''Extract the medial axis of each target glyph on its active layer.

		The resulting skeleton is emitted as a NEW shape appended to the
		active layer — the original outline is left untouched. Each output
		on-curve node carries ``lib['radius']`` (local stroke half-width).

		Selected contours are processed if a selection exists; otherwise
		all contours on the active layer are processed.

		Arguments:
			pMode (int): Glyph processing scope.
				0 - Current active glyph
				1 - All glyphs in current text window
				2 - All selected glyphs
				3 - All glyphs in font
			sample_step (float): MAT boundary sampling step, font units.
			beta_min (float): MAT pruning threshold (paper default 1.5).
			quality (str): 'draft' | 'normal' | 'fine'.
			smooth (bool): True emits cubic Beziers; False emits polylines.
			drop_corner_legs (bool): Drop short MAT branches that bisect
				convex outline corners (terminal radius → 0).
			corner_leg_ratio (float): terminal-radius / branch-max-radius
				cutoff used by the corner-leg filter.
			dedupe_eps (float): Source-node projections closer than this
				(font units) collapse to a single output node.
			prune_short (float | None): Drop terminal branches shorter
				than this arc length. None disables.
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			active_layer = glyph.layer().name

			# - Bridge to TR proxy for Core API access
			g = trGlyph(glyph.fl)
			tr_layer = g.find_layer(active_layer)
			if tr_layer is None:
				output(2, 'MatExtract', '{}: active layer {!r} not found'.format(
					glyph.name, active_layer))
				continue

			layer_core = tr_layer.eject()
			all_contours = layer_core.contours

			if not all_contours:
				output(2, 'MatExtract', '{}: no contours on layer {!r}'.format(
					glyph.name, active_layer))
				continue

			# - Selection drives which contours are analysed
			selection = glyph.selectedAtContours(active_layer)
			if selection:
				sel_cids = sorted(set(cid for cid, nid in selection))
				source_contours = [all_contours[i] for i in sel_cids
				                   if i < len(all_contours)]
			else:
				source_contours = all_contours

			if not source_contours:
				output(2, 'MatExtract', '{}: empty source selection'.format(
					glyph.name))
				continue

			# - Extract skeleton
			skeleton = extract_medial_axis(
				source_contours,
				sample_step=sample_step,
				beta_min=beta_min,
				quality=quality,
				smooth=smooth,
				drop_corner_legs=drop_corner_legs,
				corner_leg_ratio=corner_leg_ratio,
				
				prune_short=prune_short,
			)

			if not skeleton:
				output(1, 'MatExtract', '{}: no skeleton produced'.format(
					glyph.name))
				continue

			# - Append as a NEW shape on the active layer — leaves the
			#   original outline intact. Users can move/delete the
			#   skeleton shape independently.
			layer_core.shapes.append(Shape(contours=skeleton))
			tr_layer.mount(layer_core)

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tMAT Extract @ {}.'.format(
				glyph.name, active_layer))

			output(0, 'MatExtract', '{} [{}]: {} skeleton contours'.format(
				glyph.name, active_layer, len(skeleton)))

		active_workspace.getCanvas(True).refreshAll()
