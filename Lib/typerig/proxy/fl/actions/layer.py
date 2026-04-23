# MODULE: Typerig / Proxy / FontLab / Actions / Layer
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import os, warnings
from math import radians
from collections import OrderedDict
from itertools import groupby

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.core.func.math import linInterp as lerp
from typerig.core.base.message import *
from typerig.core.algo.matchmaker import apply_match_glyph, pair_contours
from typerig.proxy.tr.objects.glyph import trGlyph
from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import *
from typerig.proxy.fl.gui.dialogs import TRMsgSimple, TR2FieldDLG
from typerig.proxy.fl.application.app import pItems

# - Init ---------------------------------
__version__ = '3.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Actions ------------------------------------------------------------------
class TRLayerActionCollector(object):
	''' Collection of all layer based tools'''

	# - Layer: Basic tools ---------------------------------------------------
	@staticmethod
	def layer_toggle_visible(parent):	
		if parent.doCheck():	
			layer_list = parent.lst_layers.getTable()
			
			for layer_name in layer_list:
				parent.glyph.layer(layer_name).isVisible = not parent.glyph.layer(layer_name).isVisible

			parent.glyph.updateObject(parent.glyph.fl, 'Toggle Visibility Layer: %s.' %'; '.join(layer_list))

	@staticmethod
	def layer_set_visible(parent, visible=False):	
		if parent.doCheck():	
			layer_list = parent.lst_layers.getTable()
			
			for layer_name in layer_list:
				parent.glyph.layer(layer_name).isVisible = visible

			parent.glyph.updateObject(parent.glyph.fl, 'Set Visibility Layer: %s.' %'; '.join(layer_list))

	@staticmethod
	def layer_add(parent):
		if parent.doCheck():
			user_input = TR1FieldDLG('Add new layer ', 'Please enter a name for the layer created.', 'Name:').values
			newLayer = fl6.flLayer()
			newLayer.name = str(user_input)
			parent.glyph.addLayer(newLayer)
			parent.glyph.updateObject(parent.glyph.fl, 'Add Layer: %s.' %newLayer.name)
			parent.refresh()

	@staticmethod
	def layer_ditto(parent, reverse=False):	
		operation = ['Pull', 'Push'][reverse]

		if parent.doCheck():
			current_layer = parent.glyph.layer()
			current_selection = parent.glyph.selectedNodes()
			
			if not len(current_selection): 
				warnings.warn('No selection on active layer: %s.' %current_layer.name, TRPanelWarning)
				return
			
			# - Persistent bank of selected nodes
			process_selection = []

			for layer_name in parent.lst_layers.getTable():
				if layer_name != current_layer.name:
					process_layer = parent.glyph.layer(layer_name)
					
					if current_layer.isCompatible(process_layer, True):
						process_selection.append(parent.glyph.selectedNodes(layer_name))
					else:
						warnings.warn('Skiping Layer: %s. Layer not compatible to: %s.' %(layer_name,current_layer.name), LayerWarning)

			if len(process_selection):
				for nodes_selection in process_selection:
					for nid in range(len(current_selection)):
						if not reverse:
							current_selection[nid].x = nodes_selection[nid].x
							current_selection[nid].y = nodes_selection[nid].y
						else:
							nodes_selection[nid].x = current_selection[nid].x
							nodes_selection[nid].y = current_selection[nid].y
				
			
				parent.glyph.updateObject(parent.glyph.fl, '%s Contour; Layer: %s.' %(operation,'; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
				parent.refresh()

	@staticmethod
	def layer_duplicate(parent, ask_user=False):	
		if parent.doCheck():
			# - Ask user about rename pattern
			if ask_user:
				user_input = TR2FieldDLG('Duplicate Layer', 'Please enter prefix and/or suffix for duplicate layers', 'Prefix:', 'Suffix:').values
			
			layer_prefix = user_input[0] if ask_user else ''
			layer_suffux = user_input[1] if ask_user else parent.edt_name.text

			# - Duplicate 
			for layer_name in parent.lst_layers.getTable():
				parent.glyph.duplicateLayer(layer_name , '{1}{0}{2}'.format(layer_name, layer_prefix, layer_suffux))
			
			parent.glyph.updateObject(parent.glyph.fl, 'Duplicate Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_duplicate_mask(parent):	
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				# - Build mask layer
				srcShapes = parent.glyph.shapes(layer_name)
				newMaskLayer = parent.glyph.layer(layer_name).getMaskLayer(True)			

				# - Copy shapes to mask layer
				for shape in srcShapes:
					newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!
			
			parent.glyph.updateObject(parent.glyph.fl, 'New Mask Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_delete(parent):				
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				parent.glyph.removeLayer(layer_name)

			parent.glyph.updateObject(parent.glyph.fl, 'Delete Layer: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))
			parent.refresh()

	@staticmethod
	def layer_set_type(parent, type):
		if parent.doCheck():	
			for layer_name in parent.lst_layers.getTable():
				wLayer = parent.glyph.layer(layer_name)

				if type == 'Service': 
					wLayer.isService = not wLayer.isService

				if type == 'Wireframe': 
					wLayer.isWireframe = not wLayer.isWireframe
				
				if type == 'Mask': 
					if wLayer.isMaskLayer:
						wLayer.isService = False
						wLayer.isWireframe = False
					
						if 'mask.' in wLayer.name: 
							wLayer.name = wLayer.name.replace('mask.', '')
					
					else:
						wLayer.name = 'mask.' + wLayer.name
						wLayer.isService = True
						wLayer.isWireframe = True

			parent.glyph.updateObject(parent.glyph.fl, 'Set Layer as <%s>: %s.' %(type, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
			parent.refresh()

	# - Layer: Content tools ---------------------------------------------------
	@staticmethod
	def layer_copy_shapes(glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTShapes = None
		
		# -- Get shapes
		srcShapes = glyph.shapes(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup destination layers
		if cleanDST:
			exportDSTShapes = glyph.shapes(dstLayerName)
			glyph.layer(dstLayerName).removeAllShapes()
		
		# -- Copy/Paste
		for shape in srcShapes:
			glyph.layer(dstLayerName).addShape(shape.cloneTopLevel())

		return exportDSTShapes

	@staticmethod
	def layer_copy_metrics(glyph, layerName, copy=True, mode='ADV', impSRC=None):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		
		if 'LSB' in mode.upper():
			exportMetric = glyph.getLSB(dstLayerName) 
			glyph.setLSB(glyph.getLSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			glyph.setLSBeq(glyph.getSBeq(srcLayerName)[0], dstLayerName)
			return exportMetric

		if 'ADV' in mode.upper():
			exportMetric = glyph.getAdvance(dstLayerName)
			glyph.setAdvance(glyph.getAdvance(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			return exportMetric

		if 'RSB' in mode.upper():
			exportMetric = glyph.getRSB(dstLayerName)
			glyph.setRSB(glyph.getRSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			glyph.setRSBeq(glyph.getSBeq(srcLayerName)[1], dstLayerName)
			return exportMetric

	@staticmethod
	def layer_copy_guides(glyph, layerName, copy=True, cleanDST=False):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName

		# -- Cleanup !!! Not implementable for now?! Why
		if cleanDST:
			pass

		glyph.layer(dstLayerName).appendGuidelines(glyph.guidelines(srcLayerName))

	@staticmethod
	def layer_copy_anchors(glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTAnchors = None

		# -- Get anchors
		srcAnchors = glyph.anchors(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup !!! Not working
		if cleanDST:
			exportDSTAnchors = glyph.anchors(dstLayerName)

			for anchor in glyph.anchors(dstLayerName):
					glyph.layer(dstLayerName).removeAnchor(anchor)

		for anchor in srcAnchors:
				glyph.anchors(dstLayerName).append(anchor)

		return exportDSTAnchors

	@staticmethod
	def layer_unlock(parent, locked_trigger=False):
		if parent.doCheck():
			if parent.chk_outline.isChecked():
				for layer_name in parent.lst_layers.getTable():
					for shape in parent.glyph.shapes(layer_name):
						shape.contentLocked = locked_trigger

			parent.glyph.updateObject(parent.glyph.fl, '%s shapes on Layer(s) | %s' %(['Unlock', 'Lock'][locked_trigger],'; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))


	@staticmethod
	def layer_swap(parent):
		if parent.doCheck():	
			if parent.chk_outline.isChecked():
				exportSRC = TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), True, True)
				TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), False, True, exportSRC)

			if parent.chk_guides.isChecked():
				pass

			if parent.chk_anchors.isChecked():
				pass

			if parent.chk_lsb.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'LSB')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'LSB', exportMetric)

			if parent.chk_adv.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'ADV')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'ADV', exportMetric)

			if parent.chk_rsb.isChecked():
				exportMetric = TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'RSB')
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), False, 'RSB', exportMetric)

			parent.glyph.updateObject(parent.glyph.fl, 'Swap Layers | %s <-> %s.' %(parent.glyph.activeLayer().name, parent.lst_layers.currentItem().text()))


	@staticmethod
	def layer_pull(parent):
		if parent.doCheck():
			
			if parent.chk_outline.isChecked():
				TRLayerActionCollector.layer_copy_shapes(parent.glyph, parent.lst_layers.currentItem().text(), True)
				
			if parent.chk_guides.isChecked():
				TRLayerActionCollector.layer_copy_guides(parent.glyph, parent.lst_layers.currentItem().text(), True)

			if parent.chk_anchors.isChecked():
				TRLayerActionCollector.layer_copy_anchors(parent.glyph, parent.lst_layers.currentItem().text(), True)

			if parent.chk_lsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'LSB')
				
			if parent.chk_adv.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'ADV')
				
			if parent.chk_rsb.isChecked():
				TRLayerActionCollector.layer_copy_metrics(parent.glyph, parent.lst_layers.currentItem().text(), True, 'RSB')
				
			parent.glyph.updateObject(parent.glyph.fl, 'Pull Layer | %s <- %s.' %(parent.glyph.activeLayer().name, parent.lst_layers.currentItem().text()))


	@staticmethod
	def layer_push(parent):
		if parent.doCheck():	
			selected_layers = parent.lst_layers.getTable()
			for layer_name in selected_layers:

				if parent.chk_outline.isChecked():
					TRLayerActionCollector.layer_copy_shapes(parent.glyph, layer_name, False)
					
				if parent.chk_guides.isChecked():
					TRLayerActionCollector.layer_copy_guides(parent.glyph, layer_name, False)

				if parent.chk_anchors.isChecked():
					TRLayerActionCollector.layer_copy_anchors(parent.glyph, layer_name, False)

				if parent.chk_lsb.isChecked():
					TRLayerActionCollector.layer_copy_metrics(parent.glyph, layer_name, False, 'LSB')
					
				if parent.chk_adv.isChecked():
					TRLayerActionCollector.layer_copy_metrics(parent.glyph, layer_name, False, 'ADV')
					
				if parent.chk_rsb.isChecked():
					TRLayerActionCollector.layer_copy_metrics(parent.glyph, layer_name, False, 'RSB')
				
			parent.glyph.updateObject(parent.glyph.fl, 'Push Layer | %s -> %s.' %(parent.glyph.activeLayer().name, '; '.join(selected_layers)))

	@staticmethod
	def layer_clean(parent):
		if parent.doCheck():	
			if parent.chk_outline.isChecked():
				for layer_name in parent.lst_layers.getTable():
					parent.glyph.layer(layer_name).removeAllShapes()

			if parent.chk_guides.isChecked():
				pass # TODO!!!!!

			if parent.chk_anchors.isChecked():
				pass # TODO!!!!!
			
			parent.glyph.updateObject(parent.glyph.fl, 'Clean Layer(s) | %s' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	# - Layer: Multilayer tools ---------------------------------------------------
	@staticmethod
	def layer_side_by_side(parent):
		# - Init
		selected_layers = parent.lst_layers.getTable()
		wItems = pItems()
		
		if parent.doCheck() and len(selected_layers) > 1:
			wGlyph = parent.glyph
			wItems.outputGlyphNames([wGlyph.name]*len(selected_layers), selected_layers)
			
	@staticmethod
	def layer_unfold(parent):
		if parent.doCheck() and len(parent.lst_layers.getTable()) > 1:
			# - Init
			wGlyph = parent.glyph

			# - Prepare Backup
			parent.backup = {layer_name:(wGlyph.getLSB(layer_name), wGlyph.getAdvance(layer_name)) for layer_name in parent.lst_layers.getTable()}

			# - Calculate metrics
			newLSB = 0
			nextLSB = 0
			newAdvance = sum([sum(layer_name) for layer_name in parent.backup.values()])
			
			for layer_name in parent.lst_layers.getTable():
				wLayer = layer_name
				
				newLSB += nextLSB + parent.backup[wLayer][0]
				nextLSB = parent.backup[wLayer][1]
				
				wGlyph.setLSB(newLSB, wLayer)
				wGlyph.setAdvance(newAdvance, wLayer)
				wGlyph.layer(wLayer).isVisible = True

			parent.glyph.updateObject(parent.glyph.fl, 'Unfold Layers: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	@staticmethod
	def layer_restore(parent):
		if parent.doCheck() and len(parent.backup.keys()):
			# - Resore metrics
			wGlyph = parent.glyph

			for layer, metrics in parent.backup.items():
				wGlyph.setLSB(metrics[0], layer)
				wGlyph.setAdvance(metrics[1], layer)
				wGlyph.layer(layer).isVisible = False

			# - Reset
			parent.backup = {}
			parent.glyph.updateObject(parent.glyph.fl, 'Restore Layer metrics: %s.' %'; '.join([layer_name for layer_name in parent.lst_layers.getTable()]))

	@staticmethod
	def layer_copy_outline(parent):
		# - Init
		wGlyph = parent.glyph
		wContours = wGlyph.contours()
		parent.contourClipboard = OrderedDict()
		
		# - Build initial contour information
		selectionTuples = wGlyph.selectedAtContours()
		selection = {key:[layer_name[1] for layer_name in value] if not wContours[key].isAllNodesSelected() else [] for key, value in groupby(selectionTuples, lambda x:x[0])}

		# - Process
		if len(selection.keys()):
			for layer_name in parent.lst_layers.getTable():
				wLayer = layer_name
				parent.contourClipboard[wLayer] = []

				for cid, nList in selection.items():
					if len(nList):
						 parent.contourClipboard[wLayer].append(fl6.flContour([wGlyph.nodes(wLayer)[nid].clone() for nid in nList]))
					else:
						parent.contourClipboard[wLayer].append(wGlyph.contours(wLayer)[cid].clone())
			output(0, '', 'Copy outline; Glyph: %s; Layers: %s.' %(parent.glyph.fl.name, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
		
	@staticmethod
	def layer_paste_outline(parent):
		# - Init
		wGlyph = parent.glyph
		modifiers = QtGui.QApplication.keyboardModifiers()

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(parent.contourClipboard.keys()):
			for layerName, contours in parent.contourClipboard.items():
				wLayer = wGlyph.layer(layerName)

				if wLayer is not None:
					if modifiers == QtCore.Qt.ShiftModifier:
						# - Insert contours into currently selected shape
						selected_shapes_list = wGlyph.selectedAtShapes(index=False, layer=layerName, deep=False)

						if len(selected_shapes_list):
							selected_shape = selected_shapes_list[0][0]
							selected_shape.addContours(contours, True)
						else:
							add_new_shape(wLayer, contours)	# Fallback
					else:
						# - Create new shape
						add_new_shape(wLayer, contours)
		
			parent.glyph.updateObject(parent.glyph.fl, 'Paste outline; Glyph: %s; Layers: %s' %(parent.glyph.fl.name, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))

	# - Layer: Matchmaker tools ---------------------------------------------------
	@staticmethod
	def layer_matchmaker(parent, dry_run=False):
		def _on_count(contour):
			return sum(1 for n in contour.nodes if n.is_on)

		def _layer_contours(core_layer):
			out = []
			for shape in core_layer.shapes:
				for c in shape.contours:
					out.append(c)
			return out

		def _replace_layer_contours(core_layer, new_contours):
			new_shape = Shape(list(new_contours))
			return Layer(
				[new_shape],
				name=core_layer.name,
				width=core_layer.advance_width,
				height=core_layer.advance_height,
				mark=core_layer.mark,
				anchors=core_layer.anchors,
			)

		def _resolve_modes(parent):
			respect_order = parent.chk_respect_order.isChecked()
			respect_start = parent.chk_respect_start.isChecked()
			canonicalize = parent.chk_canonicalize.isChecked()

			pair_mode = 'respect' if respect_order else 'auto'
			if respect_start:
				align_start = 'respect'
			elif canonicalize:
				align_start = 'canonical'
			else:
				align_start = 'auto'
			return align_start, pair_mode

		if parent.doCheck():
			selected_layers = parent.lst_layers.getTable()
			if not selected_layers:
				warnings.warn('No layer selected in list.', TRPanelWarning)
				return

			src_layer = parent.glyph.activeLayer()
			target_layer_name = selected_layers[0]
			target_layer = parent.glyph.layer(target_layer_name)

			if src_layer.name == target_layer_name:
				warnings.warn('Source and target are the same layer.', TRPanelWarning)
				return

			align_start, pair_mode = _resolve_modes(parent)

			try:
				g = trGlyph()
			except Exception as e:
				warnings.warn('No current glyph: %s.' %e, TRPanelWarning)
				return

			tr_src = g.find_layer(src_layer.name)
			tr_tgt = g.find_layer(target_layer_name)
			if tr_src is None or tr_tgt is None:
				warnings.warn('Glyph missing source or target layer.', TRPanelWarning)
				return

			core_src = tr_src.eject()
			core_tgt = tr_tgt.eject()

			ca = _layer_contours(core_src)
			cb = _layer_contours(core_tgt)

			try:
				font = fl6.CurrentFont()
				em = float(font.upm) if font else 1000.0
			except Exception:
				em = 1000.0

			if len(ca) != len(cb):
				warnings.warn('Contour count mismatch: A=%d B=%d.' %(len(ca), len(cb)), TRPanelWarning)
				return

			if any(_on_count(c) < 3 for c in ca + cb):
				warnings.warn('Degenerate contours (<3 on-curves) found.', TRPanelWarning)
				return

			k_s = 1.0 / (em * em)
			k_b = 1.0

			try:
				new_a, new_b, total_cost, meta = apply_match_glyph(
					ca, cb, k_s=k_s, k_b=k_b,
					align_start=align_start, pair_mode=pair_mode)
			except Exception as e:
				warnings.warn('apply_match_glyph failed: %s.' %e, TRPanelWarning)
				return

			if dry_run:
				print('')
				print('=' * 60)
				print('TR | Matchmaker: glyph "%s"  source=%s  target=%s  em=%s' %(g.name, src_layer.name, target_layer_name, em))
				print('  modes: align_start=%r  pair_mode=%r' %(align_start, pair_mode))
				print('  contour counts: source=%d target=%d' %(len(ca), len(cb)))
				print('  total cost = %.4f' %total_cost)
				print('  inserts: source=%d target=%d' %(meta['total_insert_a'], meta['total_insert_b']))
				print('  promotions: source=%d target=%d' %(meta['total_promoted_a'], meta['total_promoted_b']))
				print('  pairs: %s' %meta['pairs'])
				print('(no changes written - click without Alt to apply)')
			else:
				try:
					out_src = _replace_layer_contours(core_src, new_a)
					out_tgt = _replace_layer_contours(core_tgt, new_b)

					tr_src.mount(out_src)
					tr_tgt.mount(out_tgt)
					g.update()

					output(0, 'TR | Matchmaker', 'glyph "%s" matched [%r/%r]. cost=%.4f inserts=%d/%d promotions=%d/%d pairs=%s' %(
						g.name, align_start, pair_mode, total_cost,
						meta['total_insert_a'], meta['total_insert_b'],
						meta['total_promoted_a'], meta['total_promoted_b'],
						meta['pairs']))
				except Exception as e:
					warnings.warn('Mount failed: %s.' %e, TRPanelWarning)
