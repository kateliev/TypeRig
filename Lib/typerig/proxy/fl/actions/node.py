# MODULE: Typerig / Proxy / FontLab / Actions / Node
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------------------------------------------------
from __future__ import absolute_import, print_function

import warnings
import math

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.node import eNode, eNodesContainer
from typerig.proxy.fl.objects.contour import pContour
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import pFont, pFontMetrics
from typerig.proxy.fl.objects.base import Line, Vector, Coord

from typerig.core.func.collection import group_consecutive
from typerig.core.objects.point import Void
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init ----------------------------------------------------------------------------
__version__ = '2.60'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Functions ------------------------------------------------------------------------
def filter_consecutive(selection):
	'''Group the results of selectedAtContours and filter out consecutive nodes.'''
	selection_dict = {}
	map_dict = {}
				
	for cID, nID in selection:
		selection_dict.setdefault(cID,[]).append(nID)
		map_dict.setdefault(cID, []).append(nID - 1 in selection_dict[cID])

	return {key: [value[i] for i in range(len(value)) if not map_dict[key][i]] for key, value in selection_dict.items()}

def scale_offset(node, off_x, off_y, width, height):
	'''Scaling move - coordinates as percent of position'''
	return (-node.x + width*(float(node.x)/width + offset_x), -node.y + height*(float(node.y)/height + offset_y))

def get_dummy_nodes(x, y):
	return [fl6.flNode(x,y, nodeType=1), fl6.flNode(x,y, nodeType=4), fl6.flNode(x,y, nodeType=4)]#, fl6.flNode(x,y, nodeType=1)]

def get_crossing(node_list):
	temp_nodes = [node for node in node_list if node.isOn]
	fisrt_node, second_node = temp_nodes[0], temp_nodes[-1]

	line_in_A = fisrt_node.getPrevLine() 
	line_in_B = fisrt_node.getNextLine()
	line_out_A = second_node.getNextLine() 
	line_out_B = second_node.getPrevLine()
	
	crossing_A = line_in_A.intersect_line(line_out_A, True)
	crossing_B = line_in_B.intersect_line(line_out_B, True)

	# - Get only real coordinates
	crossing = crossing_A if not isinstance(crossing_A, Void) else crossing_B

	return crossing

# - Actions ---------------------------------------------------------------------------
class TRNodeActionCollector(object):
	''' Collection of all node related tools '''

	# -- Basic node tools --------------------------------------------------------------
	@staticmethod
	def node_insert(pMode:int, pLayers:tuple, time:float, select_one_node=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			selection = glyph.selectedAtContours(True)
			wLayers = glyph._prepareLayers(pLayers)

			# - Get selected nodes. 
			# - NOTE: Only the fist node in every selected segment is important, so we filter for that
			selection = glyph.selectedAtContours(True, filterOn=True)
			selection_dict, selection_filtered = {}, {}
			
			for cID, nID in selection:
				selection_dict.setdefault(cID,[]).append(nID)
					
			if not select_one_node: 
				for cID, sNodes in selection_dict.items():
					onNodes = glyph.contours(extend=pContour)[cID].indexOn()
					segments = zip(onNodes, onNodes[1:] + [onNodes[0]]) # Shift and zip so that we have the last segment working
					onSelected = []

					for pair in segments:
						if pair[0] in sNodes and pair[1] in sNodes:
							onSelected.append(pair[0] )

					selection_filtered[cID] = onSelected
			else:
				selection_filtered = selection_dict

			# - Process
			for layer in wLayers:
				nodeMap = glyph._mapOn(layer)
								
				for cID, nID_list in selection_filtered.items():
					for nID in reversed(nID_list):
						glyph.insertNodeAt(cID, nodeMap[cID][nID] + time, layer)

			glyph.updateObject(glyph.fl, '{};\tInsert Node @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def node_insert_dlg(pMode:int, pLayers:tuple, select_one_node=False):
		dlg_node_add = TRDialogs.TR1SliderDLG('Insert Node', 'Set time along bezier curve', (0., 100., 50., 1.))
		dlg_node_add.return_values()

		if dlg_node_add.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		TRNodeActionCollector.node_insert(pMode, pLayers, dlg_node_add.values/100., select_one_node)

	@staticmethod
	def node_remove(pMode:int, pLayers:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			selection = glyph.selectedAtContours(filterOn=True)
			tempDict = {}

			for cID, nID in selection:
				tempDict.setdefault(cID, []).append(nID)

			for layer in wLayers:
				for cID, nidList in tempDict.items():
					for nID in reversed(nidList):
						nodeA = eNode(glyph.contours(layer)[cID].nodes()[nID]).getNextOn()
						nodeB = eNode(glyph.contours(layer)[cID].nodes()[nID]).getPrevOn()
						glyph.contours(layer)[cID].removeNodesBetween(nodeB, nodeA)

			glyph.updateObject(glyph.fl, '{};\tRemove Node @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def node_round(pMode:int, pLayers:tuple, round_up:bool=True, round_all:bool=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			for layer_name in wLayers:
				selection = glyph.selectedNodes(layer_name) if not round_all else glyph.nodes(layer_name)

				for node in selection:
					node.x = math.ceil(node.x) if round_up else math.floor(node.x)
					node.y = math.ceil(node.y) if round_up else math.floor(node.y)
			
			glyph.updateObject(glyph.fl, '{};\tRound {} nodes to integer coordinates @ {}.'.format(glyph.name, len(selection) if not round_all else 'ALL', '; '.join(wLayers)))

	# -- Corner tools -----------------------------------------------------------
	@staticmethod
	def corner_mitre(pMode:int, pLayers:tuple, radius:float):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
				
				for node in reversed(selection):
					node.cornerMitre(radius)

			glyph.updateObject(glyph.fl, '{};\tMitre Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def corner_mitre_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TR1SpinDLG('Mitre Corner', 'Please provide miter radius...', 'Radius:', (0., 200., 4., 1.))
		dlg_get_input.return_values()

		if dlg_get_input.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		TRNodeActionCollector.corner_mitre(pMode, pLayers, dlg_get_input.values)

	@staticmethod
	def corner_round(pMode:int, pLayers:tuple, radius:float, curvature:float=1., is_radius:bool=True):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init
			wLayers = glyph._prepareLayers(pLayers)

			# - Process				
			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
				
				for node in selection:
					node.cornerRound(radius, curvature=curvature, isRadius=is_radius)

			glyph.updateObject(glyph.fl, '{};\tRound Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def corner_round_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TRNSpinDLG('Round Corner', 'Please provide radius and curvature for the new round corner...', {'Radius:':(0., 200., 5., 1.), 'Curvature:':(0., 2., 1., .1)})
		dlg_get_input.return_values()

		if dlg_get_input.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		radius, curvature = dlg_get_input.values
		TRNodeActionCollector.corner_round(glyph, pLayers, radius, curvature)

	@staticmethod
	def corner_loop(pMode:int, pLayers:tuple, radius:float):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
				
				for node in reversed(selection):
					node.cornerMitre(-radius, True)

			glyph.updateObject(glyph.fl, '{};\tLoop Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def corner_loop_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TR1SpinDLG('Loop Corner', 'Please provide overlap length...', 'Overlap:', (0., 200., 20., 1.))
		dlg_get_input.return_values()

		if dlg_get_input.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		TRNodeActionCollector.corner_loop(pMode, pLayers, dlg_get_input.values)

	@staticmethod
	def corner_trap(pMode:int, pLayers:tuple, incision:int, depth:int, trap:int, smooth:bool=True):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init	
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
				
				for node in reversed(selection):
					node.cornerTrapInc(incision, depth, trap, smooth)

			glyph.updateObject(glyph.fl, '{};\tTrap Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))

	@staticmethod
	def corner_trap_dlg(pMode:int, pLayers:tuple, smooth:bool=True):
		dlg_get_input = TRDialogs.TRNSpinDLG('Trap Corner', 'Create ink trap with the following parameters...', {'Incision:':(0., 200., 10., 1.), 'Depth:':(0., 200., 50., 1.), 'Mitre:':(0., 20., 2., 1.)})
		dlg_get_input.return_values()

		if dlg_get_input.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		incision, depth, trap = dlg_get_input.values
		TRNodeActionCollector.corner_trap(pMode, pLayers, incision, depth, trap, smooth)

	@staticmethod
	def corner_rebuild(pMode:int, pLayers:tuple, cleanup_nodes:bool=True):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init	
			wLayers = glyph._prepareLayers(pLayers)
			selection_layers_all = {layer : glyph.selectedNodes(layer, extend=eNode) for layer in wLayers}
			selection_layers_on = {layer : [node for node in selection if node.isOn] for layer, selection in selection_layers_all.items()}
			done_flag = False

			for layer, selection in selection_layers_on.items():			
				if len(selection) > 1:
					node_first = selection[0]
					node_last = selection[-1]
					crossing = get_crossing(selection)

					if cleanup_nodes:
						node_first.smartReloc(*crossing.tuple)
						node_first.parent.removeNodesBetween(node_first.fl, node_last.getNextOn())

					else:
						for node in selection_layers_all:
							node.reloc(*crossing.tuple)

					done_flag = True

			if done_flag:
				glyph.updateObject(glyph.fl, '{};\tRebuild corner:\t{} nodes reduced @ {}'.format(glyph.name, len(selection), '; '.join(wLayers)))

	# -- Slope tools -----------------------------------------------------------------
	@staticmethod
	def slope_copy(glyph:eGlyph, pLayers:tuple) -> dict:
		wLayers = glyph._prepareLayers(pLayers)
		slope_dict = {}
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer)
			slope_dict[layer] = Vector(selection[0], selection[-1]).slope

		return slope_dict

	def slope_italic(glyph:eGlyph, pLayers:tuple) -> dict:
		wLayers = glyph._prepareLayers(pLayers)
		italicAngle = glyph.package.italicAngle_value
		slope_dict = {layer : -1*italicAngle for layer in wLayers}

		return slope_dict

	@staticmethod
	def slope_paste(pMode:int, pLayers:tuple, slope_dict:dict, mode:tuple):
		'''
		mode -> (max:bool, flip:bool) where
		minY = (False, False)
		MaXY = (True, False)
		FLminY = (False, True)
		FLMaxY = (True, True)
		'''
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init
			wLayers = glyph._prepareLayers(pLayers)
			control = (True, False)
			
			for layer in wLayers:
				selection = [eNode(node) for node in glyph.selectedNodes(layer)]

				if mode[0]:
					dstVector = Vector(max(selection, key=lambda item: item.y).fl, min(selection, key=lambda item: item.y).fl)
				else:
					dstVector = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					
				if mode[1]:
					dstVector.slope = -1.*slope_dict[layer]
				else:
					dstVector.slope = slope_dict[layer]

				for node in selection:
					node.alignTo(dstVector, control)

			glyph.updateObject(glyph.fl, '{};\tPaste Slope @ {}.'.fromat(glyph.name, '; '.join(wLayers)))
			glyph.update()


	# -- Nodes alignment ------------------------------------------------------
	@staticmethod
	def nodes_align(pMode:int, pLayers:tuple, mode:str, intercept:bool=False, keep_relations:bool=False, smart_shift:bool=False, ext_target:Coord=None):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)
			italicAngle = glyph.package.italicAngle_value
			
			for layer in wLayers:
				selection = glyph.selectedNodes(layer, extend=eNode)

				# - Contour/selection relative alignment
				# -- Left
				if mode == 'L':
					target = min(selection, key=lambda item: item.x)
					control = (True, False)

				# -- Right
				elif mode == 'R':
					target = max(selection, key=lambda item: item.x)
					control = (True, False)
				
				# -- Top
				elif mode == 'T':
					temp_target = max(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
					control = (False, True)
				
				# -- Bottom
				elif mode == 'B':
					temp_target = min(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
					control = (False, True)
				
				# -- Horizontal Center
				elif mode == 'C':
					newX = (min(selection, key=lambda item: item.x).x + max(selection, key=lambda item: item.x).x)/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)

				# -- Vertical Center
				elif mode == 'E':
					newY = (min(selection, key=lambda item: item.y).y + max(selection, key=lambda item: item.y).y)/2
					newX = 0.
					target = fl6.flNode(newX, newY)
					control = (False, True)

				# - To imaginary line between minimum and maximum of selection
				elif mode == 'Y':
					target = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					control = (True, False)

				elif mode == 'X':
					target = Vector(min(selection, key=lambda item: item.x).fl, max(selection, key=lambda item: item.x).fl)
					control = (False, True)

				# - Bounding box alignment
				elif mode == 'BBoxCenterX':
					newX = glyph.layer(layer).boundingBox.x() + glyph.layer(layer).boundingBox.width()/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)

				elif mode == 'BBoxCenterY':
					newX = 0.
					newY = glyph.layer(layer).boundingBox.y() + glyph.layer(layer).boundingBox.height()/2
					target = fl6.flNode(newX, newY)
					control = (False, True)

				# - Font Metrics alignment
				elif 'FontMetrics' in mode:
					layerMetrics = glyph.fontMetricsInfo(layer)
					italicAngle = glyph.package.italicAngle_value
					
					newX = 0.
					toMaxY = True

					# -- Ascender
					if '0' in mode:
						newY = layerMetrics.ascender
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					# -- Caps
					elif '1' in mode:
						newY = layerMetrics.capsHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					# -- Descender
					elif '2' in mode:
						newY = layerMetrics.descender
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					# -- xHeight
					elif '3' in mode:
						newY = layerMetrics.xHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					# -- Baseline
					elif '4' in mode:
						newY = 0
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					# -- Mesurment line Y position
					elif '5' in mode:
						newY = glyph.mLine()
						toMaxY = newY >= 0 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'
						if modifiers == QtCore.Qt.ShiftModifier: toMaxY = not toMaxY

				'''
				# !!! Turn this into standalone dialog >>>

				elif mode == 'Layer_V':
					if 'BBox' in parent.cmb_select_V.currentText:
						width = glyph.layer(layer).boundingBox.width()
						origin = glyph.layer(layer).boundingBox.x()
				
					elif 'Adv' in parent.cmb_select_V.currentText:
						width = glyph.getAdvance(layer)
						origin = 0.

					target = fl6.flNode(float(width)*parent.spb_prc_V.value/100 + origin + parent.spb_unit_V.value, 0)
					container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'RB'
					control = (True, False)

					container_mode_H = ['R','L'][modifiers == QtCore.Qt.ShiftModifier]
					container_mode_H = [container_mode_H,'C'][modifiers == QtCore.Qt.AltModifier]
					container_mode_V = 'B'
					container_mode = container_mode_H + container_mode_V

				elif mode == 'Layer_H':
					metrics = pFontMetrics(glyph.package)

					if 'BBox' in parent.cmb_select_H.currentText:
						height = glyph.layer(layer).boundingBox.height()
						origin = glyph.layer(layer).boundingBox.y()
					
					elif 'Adv' in parent.cmb_select_H.currentText:
						height = glyph.layer(layer).advanceHeight
						origin = 0.

					elif 'X-H' in parent.cmb_select_H.currentText:
						height = metrics.getXHeight(layer)
						origin = 0.

					elif 'Caps' in parent.cmb_select_H.currentText:
						height = metrics.getCapsHeight(layer)
						origin = 0.

					elif 'Ascender' in parent.cmb_select_H.currentText:
						height = metrics.getAscender(layer)
						origin = 0.			

					elif 'Descender' in parent.cmb_select_H.currentText:
						height = metrics.getDescender(layer)
						origin = 0.		

					target = fl6.flNode(0, float(height)*parent.spb_prc_H.value/100 + origin + parent.spb_unit_H.value)
					
					container_mode_H = 'L'
					container_mode_V = ['T','B'][modifiers == QtCore.Qt.ShiftModifier]
					container_mode_V = [container_mode_V,'E'][modifiers == QtCore.Qt.AltModifier]
					container_mode = container_mode_H + container_mode_V

					control = (False, True)
				
				# !!! End <<<
				'''

				if keep_relations:
					container = eNodesContainer(selection)
					
					if 'FontMetrics' in mode:
						target = fl6.flNode(newX, newY)
						control = (False, True)												
					
					container.alignTo(target, container_mode, control)

				else:
					for node in selection:
						if 'FontMetrics' in mode or mode == 'T' or mode == 'B':
							if italicAngle != 0 and not intercept:
								tempTarget = Coord(node.fl)
								tempTarget.setAngle(italicAngle)

								target = fl6.flNode(tempTarget.getWidth(newY), newY)
								control = (True, True)
							
							elif intercept:
								pairUp = node.getMaxY().position
								pairDown = node.getMinY().position
								pairPos = pairUp if toMaxY else pairDown
								newLine = Line(node.fl.position, pairPos)
								newX = newLine.solve_x(newY)

								target = fl6.flNode(newX, newY)
								control = (True, True)

							else:
								target = fl6.flNode(newX, newY)
								control = (False, True)

						if mode == 'peerCenterX':
							newX = node.x + (node.getPrevOn().x + node.getNextOn().x - 2*node.x)/2.
							newY = node.y
							target = fl6.flNode(newX, newY)
							control = (True, False)

						elif mode == 'peerCenterY':
							newX = node.x
							newY = node.y + (node.getPrevOn().y + node.getNextOn().y - 2*node.y)/2.
							target = fl6.flNode(newX, newY)
							control = (False, True)

						# - Switch to external target if provided
						if ext_target is not None: target = ext_target
						
						# - Execute Align ----------
						node.alignTo(target, control, smart_shift)

			glyph.updateObject(glyph.fl, '{};\tAlign Nodes @ {}.'.format(glyph.name, '; '.join(wLayers)))
			glyph.update()

	# -- Node clipboard ----------------------------------------------------
	@staticmethod
	def nodes_copy(glyph:eGlyph, pLayers:tuple):
		wLayers = glyph._prepareLayers(pLayers)
		node_bank = {layer : eNodesContainer([node.clone() for node in glyph.selectedNodes(layer)], extend=eNode) for layer in wLayers}
		return node_bank

	@staticmethod
	def nodes_paste(glyph:eGlyph, pLayers:tuple, node_bank:dict, align:str=None, mode:tuple=(False, False, False, False, False, False)):
		wLayers = glyph._prepareLayers(pLayers)
		flip_h, flip_v, reverse, inject_nodes, overwrite_nodes, overwrite_coordinates = flip_reverse
		
		for layer in wLayers:
			if layer in node_bank.keys():
				dst_container = eNodesContainer(glyph.selectedNodes(layer), extend=eNode)

				if len(dst_container):
					src_container = node_bank[layer].clone()
					src_transform = QtGui.QTransform()
																
					# - Transform
					if flip_h or flip_v:
						scaleX = -1 if flip_h else 1
						scaleY = -1 if flip_v else 1
						dX = src_container.x() + src_container.width()/2.
						dY = src_container.y() + src_container.height()/2.

						src_transform.translate(dX, dY)
						src_transform.scale(scaleX, scaleY)
						src_transform.translate(-dX, -dY)
						src_container.applyTransform(src_transform)
						

					# - Align source
					if align is None:
						src_container.shift(*src_container[0].diffTo(dst_container[0]))
					else:
						src_container.alignTo(dst_container, align, align=(True,True))

					if reverse: 
						src_container = src_container.reverse()

					# - Process
					if inject_nodes: # - Inject mode - insert source after first node index
						dst_container[0].contour.insert(dst_container[0].index, [node.fl for node in src_container.nodes])
						update_flag = True

					elif overwrite_nodes: # - Overwrite mode - delete all nodes in selection and replace with source
						insert_index = dst_container[0].index
						insert_contour = dst_container[0].contour
						insert_contour.removeNodesBetween(dst_container[0].fl, dst_container[-1].getNextOn())
						insert_contour.insert(dst_container[0].index, [node.fl for node in src_container.nodes])
						insert_contour.removeAt(insert_index + len(src_container))

						update_flag = True

					elif overwrite_coordinates: # - Overwrite mode - copy node coordinates only
						for nid in range(len(dst_container)):
							dst_container.nodes[nid].x = src_container.nodes[nid].x
							dst_container.nodes[nid].y = src_container.nodes[nid].y

						update_flag = True

					else: # - Paste mode - remap node by node
						if len(dst_container) == len(node_bank[layer]):
							for nid in range(len(dst_container)):
								dst_container[nid].fl.x = src_container[nid].x 
								dst_container[nid].fl.y = src_container[nid].y 

							update_flag = True
						else:
							update_flag = False
							warnings.warn('Layer: {};\tCount Mismatch: Selected nodes [{}]; Source nodes [{}].'.format(layer, len(dst_container), len(src_container)), NodeWarning)
							
		# - Done							
		if update_flag:
			glyph.update()
			glyph.updateObject(glyph.fl, '{};\nPaste Nodes @ {}.'.format(glyph.name, '; '.join(wLayers)))

	# -- Shift & Movement ------------------------------------------------
	@staticmethod
	def nodes_move(glyph:eGlyph, pLayers:tuple, offset_x:int, offset_y:int, method:str, slope_dict:dict={}, in_percent_of_advance:bool=False):
		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		italic_angle = glyph.package.italicAngle_value

		for layer in wLayers:
			selectedNodes = glyph.selectedNodes(layer=layer, extend=eNode)
			
			width = glyph.layer(layer).boundingBox.width() # glyph.layer().advanceWidth
			height = glyph.layer(layer).boundingBox.height() # glyph.layer().advanceHeight

			# - Process
			if method == 'SMART':
				for node in selectedNodes:
					if node.isOn:
						if in_percent_of_advance:						
							node.smartShift(*scale_offset(node, offset_x, offset_y, width, height))
						else:
							node.smartShift(offset_x, offset_y)

			elif method == 'MOVE':
				for node in selectedNodes:
					if in_percent_of_advance:						
						node.shift(*scale_offset(node, offset_x, offset_y, width, height))
					else:
						node.shift(offset_x, offset_y)

			elif method == 'LERP':
				for node in selectedNodes:
					if in_percent_of_advance:						
						node.interpShift(*scale_offset(node, offset_x, offset_y, width, height))
					else:
						node.interpShift(offset_x, offset_y)

			elif method == 'SLANT':
				if italic_angle != 0:
					for node in selectedNodes:
						if in_percent_of_advance:						
							node.slantShift(*scale_offset(node, offset_x, offset_y, width, height))
						else:
							node.slantShift(offset_x, offset_y, italic_angle)
				else:
					for node in selectedNodes:
						if in_percent_of_advance:						
							node.smartShift(*scale_offset(node, offset_x, offset_y, width, height))
						else:
							node.smartShift(offset_x, offset_y)

			elif method == 'SLOPE':			
				try:
					for node in selectedNodes:
						node.slantShift(offset_x, offset_y, -90 + slope_dict[layer])				
				except KeyError:
					warnings.warn('No slope information for layer found!\nNOTE:\tPlease <<Copy Slope>> first using TypeRig Node align toolbox.', LayerWarning)

		# - Finish it
		glyph.update()
		glyph.updateObject(glyph.fl, '{};\tNode: {} @ {}.'.format(glyph.name, method, '; '.join(wLayers)))