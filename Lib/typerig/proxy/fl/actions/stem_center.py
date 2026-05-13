# MODULE: Typerig / Proxy / FontLab / Actions / Stem Center Snap
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 	(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function

import fontlab as fl6

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.algo.stem_center import StemCenterSnap, StemCenterStatus

# - Init ------------------------------------------------------------------------
__version__ = '1.0'
active_workspace = pWorkspace()


# - Actions ---------------------------------------------------------------------
class TRStemCenterActionCollector(object):
	'''Snap selected nodes to the centerline of the perpendicular stem they
	sit inside. Pure consumer of stem_snap; runs on all masters in pLayers
	in a single undo block. Axis is decided once on the active layer and
	reused on all masters.

	force_axis: 'H' | 'V' | None
	  None -> auto from selection bbox (width >= height => H, else V).
	  'H'  -> stem horizontal, faces in Y, nodes move on Y.
	  'V'  -> stem vertical,   faces in X, nodes move on X.
	'''

	@staticmethod
	def snap_stem_center(pMode, pLayers, force_axis=None):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			active_layer = glyph.layer().name
			work_layers = glyph._prepareLayers(pLayers)

			# - Active-layer selection drives the axis decision. If absent,
			#   skip this glyph entirely.
			if not glyph.selectedAtContours(layer=active_layer):
				output(1, 'StemCenter', '{}: no selection on active layer {!r}'.format(
					glyph.name, active_layer))
				continue

			# - Bridge to Core: eject each work layer to feed the snapper.
			g = trGlyph(glyph.fl)
			contours_by_layer = {}
			selections_by_layer = {}
			layer_cores = {}
			fl_contours_by_layer = {}

			for name in work_layers:
				tr_layer = g.find_layer(name)
				if tr_layer is None:
					continue
				core = tr_layer.eject()
				if not core.contours:
					continue
				contours_by_layer[name] = core.contours
				selections_by_layer[name] = glyph.selectedAtContours(layer=name)
				layer_cores[name] = core
				fl_contours_by_layer[name] = glyph.contours(name)

			if not contours_by_layer:
				output(2, 'StemCenter', '{}: no usable layers'.format(glyph.name))
				continue

			snapper = StemCenterSnap(
				contours_by_layer, selections_by_layer,
				force_axis=force_axis, active_layer=active_layer,
			)
			plan = snapper.plan()

			active_entry = plan.get(active_layer)
			if active_entry is not None and active_entry.status == StemCenterStatus.AXIS_AMBIGUOUS:
				output(2, 'StemCenter',
					'{}: axis ambiguous — hold Shift for horizontal motion, Alt for vertical'.format(
						glyph.name))
				continue

			# - Write the per-layer target onto the FL nodes. We bypass
			#   StemCenterSnap.apply() so we mutate the live FL glyph
			#   directly (matches the rest of the popup's idioms).
			failed = []
			applied = []
			for name in work_layers:
				entry = plan.get(name)
				if entry is None:
					continue
				if entry.status != StemCenterStatus.OK:
					failed.append((name, entry.status))
					continue
				fl_contours = fl_contours_by_layer.get(name)
				if fl_contours is None:
					continue
				set_y = (entry.center_axis == 'Y')
				target = entry.target_coord
				sel_pairs = selections_by_layer.get(name, [])
				for ci, ni in sel_pairs:
					try:
						node = fl_contours[ci].nodes()[ni]
						if set_y:
							node.y = target
						else:
							node.x = target
					except Exception:
						pass
				applied.append(name)

			for name, status in failed:
				output(1, 'StemCenter', '{} [{}]: {}'.format(glyph.name, name, status))

			if applied:
				glyph.update()
				glyph.updateObject(glyph.fl, '{};\tStem-Center Snap; Layers: {}'.format(
					glyph.name, '; '.join(applied)))

		active_workspace.getCanvas(True).refreshAll()
