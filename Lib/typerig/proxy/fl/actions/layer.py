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

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import *

# - Init ---------------------------------
__version__ = '2.32.0'

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

				if type == 'Service': wLayer.isService is not wLayer.isService
				if type == 'Wireframe': wLayer.isWireframe is not wLayer.isWireframe

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
			output(0, app_name, 'Copy outline; Glyph: %s; Layers: %s.' %(parent.glyph.fl.name, '; '.join([layer_name for layer_name in parent.lst_layers.getTable()])))
		
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
	
	@staticmethod
	def layer_paste_outline_selection(parent):
		# - Init
		wGlyph = parent.glyph
		modifiers = QtGui.QApplication.keyboardModifiers()
		selected_layers = parent.lst_layers.getTable()

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(parent.contourClipboard.keys()) == len(selected_layers):
			for i in range(len(selected_layers)):
				layerName = selected_layers[i]
				contours = list(parent.contourClipboard.values())[i]
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
