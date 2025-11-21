# MODULE: Typerig / Proxy / FontLab / Actions / Node
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2024 	(http://www.kateliev.com)
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
from typerig.proxy.fl.objects.curve import eCurveEx
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import pFont, pFontMetrics
from typerig.proxy.fl.objects.base import Coord, Line, Vector, Curve

from typerig.core.func.collection import group_consecutive
from typerig.core.objects.point import Void
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init ----------------------------------------------------------------------------
__version__ = '3.0'
active_workspace = pWorkspace()

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

def scale_offset(node, offset_x, offset_y, width, height):
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
			
		active_workspace.getCanvas(True).refreshAll()


	@staticmethod
	def node_insert_dlg(pMode:int, pLayers:tuple, select_one_node=False):
		dlg_node_add = TRDialogs.TR1SliderDLG('Insert Node', 'Set time along bezier curve', (0., 100., 50., 1.))

		if dlg_node_add.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		TRNodeActionCollector.node_insert(pMode, pLayers, dlg_node_add.values/100., select_one_node)

	@staticmethod
	def node_insert_extreme(pMode:int, pLayers:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Handle selection	
			wLayers = glyph._prepareLayers(pLayers)
			selection_per_layer = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}
			extrema_added = False
			
			# - Process 
			for layer, selection in selection_per_layer.items():		
				if len(selection) == 2:
					# - Get selection and associated segment nodes
					node_A, node_B = selection
					segment_A = node_A.getSegmentNodes()
					
					# - Find and insert extrema
					if node_B.fl in segment_A: 	# Check whether the second node belongs to the same contour
						curve_A = Curve(segment_A)
						extremes = curve_A.solve_extremes()
						
						if len(extremes):
							first_extrema_point, first_exrtrema_t = extremes[0] # !!! Get only the first in list. Make smarter later !!!
							node_A.insertAfter(first_exrtrema_t)
							extrema_added = True

						elif extrema_added: # !!! Keep compatibility: Even if only one extrema is found add nodes to the rest of layers...
							node_A.insertAfter(0.)

			glyph.updateObject(glyph.fl, '{};\tInsert Node at Extreme @ {}.'.format(glyph.name, '; '.join(wLayers)))
			
		active_workspace.getCanvas(True).refreshAll()				

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
			
		active_workspace.getCanvas(True).refreshAll()

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
			
		active_workspace.getCanvas(True).refreshAll()

	def node_smooth(pMode:int, pLayers:tuple, set_smooth:bool=True):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			for work_layer in wLayers:
				# - Init
				selection = glyph.selectedNodes(work_layer)
				
				for node in selection:
					node.smooth = set_smooth

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tSet {} nodes to {} @ {}.'.format(glyph.name, len(selection), ['Sharp', 'Smooth'][set_smooth], '; '.join(wLayers)))
			
		active_workspace.getCanvas(True).refreshAll()

	# -- Corner tools -----------------------------------------------------------
	@staticmethod
	def corner_mitre(pMode:int, pLayers:tuple, radius:float):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)
			
			# - Process	
			selection = [glyph.selectedNodes(layer, filterOn=True, extend=eNode)[0] for layer in wLayers]
				
			for node in reversed(selection):
				node.cornerMitre(radius)

			glyph.updateObject(glyph.fl, '{};\tMitre Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def corner_mitre_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TR1SpinDLG('Mitre Corner', 'Please provide miter radius...', 'Radius:', (0., 200., 4., 1.))

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
			selection = [glyph.selectedNodes(layer, filterOn=True, extend=eNode)[0] for layer in wLayers]
			
			for node in selection:
				node.cornerRound(radius, curvature=curvature, isRadius=is_radius)

			glyph.updateObject(glyph.fl, '{};\tRound Corner @ {}.'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def corner_round_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TRNSpinDLG('Round Corner', 'Please provide radius and curvature for the new round corner...', {'Radius:':(0., 200., 5., 1.), 'Curvature:':(0., 2., 1., .1)})

		if dlg_get_input.values is None:
			warnings.warn('ABORT:\tNo user input provided! No Action taken!', UserInputWarning)
			return

		radius, curvature = dlg_get_input.values
		TRNodeActionCollector.corner_round(pMode, pLayers, radius, curvature)

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
		
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def corner_loop_dlg(pMode:int, pLayers:tuple):
		dlg_get_input = TRDialogs.TR1SpinDLG('Loop Corner', 'Please provide overlap length...', 'Overlap:', (0., 200., 20., 1.))

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
		
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def corner_trap_dlg(pMode:int, pLayers:tuple, smooth:bool=True):
		dlg_get_input = TRDialogs.TRNSpinDLG('Trap Corner', 'Create ink trap with the following parameters...', {'Incision:':(0., 200., 10., 1.), 'Depth:':(0., 200., 50., 1.), 'Mitre:':(0., 20., 2., 1.)})

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
			
		active_workspace.getCanvas(True).refreshAll()

	# -- Slope tools -----------------------------------------------------------------
	@staticmethod
	def slope_copy(glyph:eGlyph, pLayers:tuple) -> dict:
		wLayers = glyph._prepareLayers(pLayers)
		slope_dict = {}
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer)
			slope_dict[layer] = Vector(selection[0], selection[-1]).slope

		return slope_dict

	@staticmethod
	def angle_copy(glyph:eGlyph, pLayers:tuple) -> dict:
		wLayers = glyph._prepareLayers(pLayers)
		slope_dict = {}
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer)
			slope_dict[layer] = Vector(selection[0], selection[-1]).angle

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

			glyph.updateObject(glyph.fl, '{};\tPaste Slope @ {}.'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()


	# -- Nodes alignment ------------------------------------------------------
	@staticmethod
	def nodes_align(pMode:int, pLayers:tuple, mode:str, intercept:bool=False, keep_relations:bool=False, smart_shift:bool=False, ext_target:dict={}):
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
					container_mode = mode + 'B'

				# -- Right
				elif mode == 'R':
					target = max(selection, key=lambda item: item.x)
					control = (True, False)
					container_mode = mode + 'B'
				
				# -- Top
				elif mode == 'T':
					temp_target = max(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
					control = (False, True)
					container_mode = 'L' + mode
				
				# -- Bottom
				elif mode == 'B':
					temp_target = min(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
					control = (False, True)
					container_mode = 'L' + mode
				
				# -- Horizontal Center
				elif mode == 'C':
					newX = (min(selection, key=lambda item: item.x).x + max(selection, key=lambda item: item.x).x)/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)
					container_mode = mode + 'B'

				# -- Vertical Center
				elif mode == 'E':
					newY = (min(selection, key=lambda item: item.y).y + max(selection, key=lambda item: item.y).y)/2
					newX = 0.
					target = fl6.flNode(newX, newY)
					control = (False, True)
					container_mode = 'L' + mode

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
						control = (False, True)												
						target = fl6.flNode(newX, newY)
					
					if len(ext_target.keys()): 
							try:
								target = ext_target[layer]
							except KeyError:
								pass

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
						if len(ext_target.keys()): 
							try:
								target = ext_target[layer]
							except KeyError:
								pass
						
						# - Execute Align ----------
						node.alignTo(target, control, smart_shift)

			glyph.updateObject(glyph.fl, '{};\tAlign Nodes @ {}.'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	# -- Node clipboard ----------------------------------------------------
	@staticmethod
	def nodes_copy(glyph:eGlyph, pLayers:tuple):
		wLayers = glyph._prepareLayers(pLayers)
		node_bank = {layer : eNodesContainer([node.clone() for node in glyph.selectedNodes(layer)], extend=eNode) for layer in wLayers}
		return node_bank

	@staticmethod
	def nodes_paste(glyph:eGlyph, pLayers:tuple, node_bank:dict, align:str=None, mode:tuple=(False, False, False, False, False, False)):
		wLayers = glyph._prepareLayers(pLayers)
		flip_h, flip_v, reverse, inject_nodes, overwrite_nodes, overwrite_coordinates = mode
		update_flag = False
		
		# - FIRST PASS: Collect all data BEFORE any modifications 
		layer_operations = {}
		
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
						dX = src_container.x + src_container.width/2.
						dY = src_container.y + src_container.height/2.
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
					
					# Store operation data
					layer_operations[layer] = {
						'dst_container': dst_container,
						'src_container': src_container,
						'insert_index': dst_container[0].index,
						'insert_contour': dst_container[0].contour
					}
		
		# - SECOND PASS: Execute all modifications 
		for layer, op_data in layer_operations.items():
			dst_container = op_data['dst_container']
			src_container = op_data['src_container']
			
			if inject_nodes:
				op_data['insert_contour'].insert(op_data['insert_index'], [node.fl for node in src_container.nodes])
				update_flag = True
				
			elif overwrite_nodes:
				insert_contour = op_data['insert_contour']
				insert_index = op_data['insert_index']
				
				insert_contour.removeNodesBetween(dst_container[0].fl, dst_container[-1].getNextOn())
				insert_contour.insert(insert_index, [node.fl for node in src_container.nodes])
				insert_contour.removeAt(insert_index + len(src_container))
				update_flag = True
				
			elif overwrite_coordinates:
				for nid in range(len(dst_container)):
					dst_container.nodes[nid].x = src_container.nodes[nid].x
					dst_container.nodes[nid].y = src_container.nodes[nid].y
				update_flag = True
				
			else:  # - Paste mode
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
			glyph.updateObject(glyph.fl, '{};\nPaste Nodes @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

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
				for node in sorted(selectedNodes, key= lambda n: (n.x, n.y)):
					if node.isOn:
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
		glyph.updateObject(glyph.fl, '{};\tNode: {} @ {}.'.format(glyph.name, method, '; '.join(wLayers)))
		active_workspace.getCanvas(True).refreshAll()

	# -- Caps ---------------------------------------------------------------
	@staticmethod
	def new_cap_round(glyph:eGlyph, pLayers:tuple, keep_nodes:bool=False):
		'''Create round cap'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()
		
		selection_per_layer = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}
		do_update = False
		
		# - Process
		for layer, selection in selection_per_layer.items():		
			if len(selection) == 2:
				node_A, node_B = selection
				parent_contour = node_A.contour
				
				# - Get Angle and radius
				nextNode_A = node_A.getNextOn(False)
				prevNode_A = node_A.getPrevOn(False)
				nextNode_B = node_B.getNextOn(False)

				nextUnit = Coord(nextNode_A.asCoord() - node_A.asCoord()).unit
				prevUnit = Coord(prevNode_A.asCoord() - node_A.asCoord()).unit

				angle = math.atan2(nextUnit | prevUnit, nextUnit & prevUnit)
				radius = abs(node_A.distanceToNext()*math.sin(angle))/2.

				# - Build cap segments by rounding the corners
				cap_head_A, cap_fillet_A, cap_tail_A = node_A.cornerRound(radius, curvature=(1.,1.), isRadius=False, insert=False)
				cap_head_B, cap_fillet_B, cap_tail_B = node_B.cornerRound(radius-.1, curvature=(1.,1.), isRadius=False, insert=False) # Little hack -.1 

				# - Build cap contour 
				new_cap_contour = cap_head_A + cap_fillet_A + cap_tail_A[:1] + cap_head_B[2:] + cap_fillet_B + cap_tail_B
				
				# - Insert and cleanup
				parent_contour.insert(prevNode_A.index, new_cap_contour)
				parent_contour.removeOne(prevNode_A.fl)
				parent_contour.removeNodesBetween(new_cap_contour[-1], nextNode_B.fl)
				parent_contour.removeOne(nextNode_B.fl)
			
				do_update = True			

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tRound Cap @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def cap_round(glyph:eGlyph, pLayers:tuple, keep_nodes:bool=False):
		'''Create round cap'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()
		
		selection_per_layer = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}
		do_update = False
		
		# - Process
		for layer, selection in selection_per_layer.items():		
			if len(selection) == 2:
				# - Init
				node_A, node_B = selection
				parent_contour = node_A.contour
				
				nextNode_A = node_A.getNextOn(False)
				prevNode_A = node_A.getPrevOn(False)
				nextNode_B = node_B.getNextOn(False)

				# - Get Angle and radius
				nextUnit = Coord(nextNode_A.asCoord() - node_A.asCoord()).unit
				prevUnit = Coord(prevNode_A.asCoord() - node_A.asCoord()).unit

				angle = math.atan2(nextUnit | prevUnit, nextUnit & prevUnit)
				radius = abs(node_A.distanceToNext()*math.sin(angle))/2.

				segment_A = node_A.getPrevOn(False).getSegmentNodes(0)
				segment_B = node_B.getSegmentNodes(0)

				if len(segment_A) != 4 or len(segment_B) != 4:
					# - A straight segment: no Bezier curves
					# - Round segments
					segment_A = node_A.old_cornerRound(radius, curvature=1., isRadius=False)
					segment_B = node_B.old_cornerRound(radius-.1, curvature=1., isRadius=False) # Little hack -.1 

					# - Cleanup
					remove_node = segment_B[0]
					
					if not keep_nodes: # Keep nodes for compatibility
						segment_B[0].contour.removeOne(remove_node)

					do_update = True

				else:
					if modifiers == QtCore.Qt.ShiftModifier or modifiers == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
						# - Calculate radius differently
						curve_A = Curve(*segment_A)
						curve_B = Curve(*segment_B)
						
						# -- Initial segmentation
						time_A = curve_A.solve_distance_end(radius, .001)
						time_B = curve_B.solve_distance_start(radius, .001)
						
						# -- Find distance and normal
						normal_A = curve_A.solve_normal_at_time(1)
						normal_B = curve_B.solve_normal_at_time(0)
						
						line_normal_A = Line(curve_A.p3.tuple, (curve_A.p3 + normal_A).tuple)
						line_normal_B = Line(curve_B.p0.tuple, (curve_B.p0 + normal_B).tuple)

						# --- create two straight segments and intersect the normals to them (to get new radius)
						line_A = Line(curve_A.p3.tuple, curve_A.solve_point(time_A).tuple)
						line_B = Line(curve_B.p0.tuple, curve_B.solve_point(time_B).tuple)

						intersect_points_A = line_normal_A.intersect_line(line_B, True)
						intersect_points_B = line_normal_B.intersect_line(line_A, True)

						if not isinstance(intersect_points_A, Void):
							radius = Line(line_A.p0.tuple, intersect_points_A.tuple).length/2
							output(1, 'Round Cap', 'Calculated radius:{}'.format(radius))

						if not isinstance(intersect_points_B, Void):
							radius = Line(line_B.p0.tuple, intersect_points_B.tuple).length/2
							output(1, 'Round Cap', 'Calculated radius:{}'.format(radius))
						
					if modifiers == QtCore.Qt.ControlModifier or modifiers == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
						# - Using newer corner rounding algorithm
						# - Build cap segments by rounding the corners
						cap_head_A, cap_fillet_A, cap_tail_A = node_A.cornerRound(radius, curvature=(1.,1.), isRadius=False, insert=False)
						cap_head_B, cap_fillet_B, cap_tail_B = node_B.cornerRound(radius-.1, curvature=(1.,1.), isRadius=False, insert=False) # Little hack -.1 

						# - Build cap contour 
						new_cap_contour = cap_head_A + cap_fillet_A + cap_tail_A[:1] + cap_head_B[2:] + cap_fillet_B + cap_tail_B
						
						# - Insert and cleanup
						parent_contour.insert(prevNode_A.index, new_cap_contour)
						parent_contour.removeOne(prevNode_A.fl)
						parent_contour.removeNodesBetween(new_cap_contour[-1], nextNode_B.fl)
						parent_contour.removeOne(nextNode_B.fl)
					
					else:
						# - Using older corner rounding algorithm
						# - Round Cap 
						curve_A = Curve(*segment_A)
						curve_B = Curve(*segment_B)
						new_time_A = curve_A.solve_distance_end(radius, .001)
						new_time_B = curve_B.solve_distance_start(radius, .001)
						
						# -- Make the cap and update contour
						new_A = node_A.insertBefore(new_time_A)
						new_B = node_B.insertAfter(new_time_B)
						new_C = node_A.insertAfter(.5)
						new_C.contour.removeOne(node_A.fl)
						new_C.contour.removeOne(node_B.fl)
						new_C.smooth = True
						new_C.contour.update()
						
						handle_A = new_A.nextNode().nextNode()
						handle_B = new_A.nextNode().nextNode().nextNode().nextNode()

						handle_A.x = node_A.x
						handle_A.y = node_A.y
						handle_B.x = node_B.x
						handle_B.y = node_B.y

						# -- Optimize contour
						ext_A = eCurveEx(*eNode(new_A).getSegmentNodes(0))
						ext_C = eCurveEx(eNode(new_C).getSegmentNodes(0))
						ext_A.eqHobbySpline((1.,1.))
						ext_C.eqHobbySpline((1.,1.))

					do_update = True

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tRound Cap @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def cap_rebuild(glyph:eGlyph, pLayers:tuple, keep_nodes:bool=False):
		''' Rebuild/straighten a rounded/soft cap'''

		# - Helpers
		def rebuild_cap(node_list, keep_nodes):
			# - Get crossing for each rounded corner
			crossing_A = get_crossing_handles(node_list[:4])
			crossing_B = get_crossing_handles(node_list[3:])

			# - Reloacate nodes
			node_list[0].reloc(*crossing_A.tuple)
			node_list[1].reloc(*crossing_A.tuple)
			node_list[2].reloc(*node_list[3].tuple)
			# node_list[3] < mid node >
			node_list[4].reloc(*node_list[3].tuple)
			node_list[5].reloc(*crossing_B.tuple)
			node_list[6].reloc(*crossing_B.tuple)

			for node in node_list:
				node.fl.smooth = False

			if not keep_nodes:
				node_list[0].contour.removeNodesBetween(node_list[0].fl, node_list[6].fl)
				node_list[0].contour.update()

		def get_crossing_handles(node_list):
			fisrt_node, bcp_out, bcp_in, second_node = node_list

			line_out_A = Line(fisrt_node.tuple, bcp_out.tuple)
			line_in_B = Line(bcp_in.tuple, second_node.tuple)
			
			return line_out_A.intersect_line(line_in_B, True)

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		selection_per_layer = [glyph.selectedNodes(layer, extend=eNode) for layer in wLayers]
		
		# - Process
		for selection in selection_per_layer:	
			if len(selection) != 7: continue
			rebuild_cap(selection, keep_nodes)

		glyph.updateObject(glyph.fl, '{};\tRebuild Cap @ {}.'.format(glyph.name, '; '.join(wLayers)))
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def cap_normal(glyph:eGlyph, pLayers:tuple, keep_nodes:bool=False):
		'''Normalize a cap end so that the cap line coincides with the shortest normal at one of the two points selected'''
		# !!! Note: Should be made contour direction independent. Currently bit buggy.

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()
		
		selection_per_layer = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}
		do_update = False
		
		# - Process
		for layer, selection in selection_per_layer.items():		
			if len(selection) == 2:
				node_A, node_B = selection
				parent_contour = node_A.contour
				
				# - Get Nodes and segments they belong to
				prevNode_A = node_A.getPrevOn(False)
				nextNode_B = node_B.getNextOn(False)
				
				segment_A = prevNode_A.getSegmentNodes()
				segment_B = node_B.getSegmentNodes()
				
				if len(segment_A) >= 4 and len(segment_B) >= 4:
					# - Set curves and find normals
					curve_A = Curve(*segment_A)
					curve_B = Curve(*segment_B)
					
					normal_A = curve_A.solve_normal_at_time(1)
					normal_B = curve_B.solve_normal_at_time(0)
					
					
					# - Build normal lines and find intersections to juxtaposed curves
					normal_line_A = Line(node_A.tuple, (normal_A + node_A.tuple).tuple).solve_length(1000,0) # Extend the resulting line to 1000 u
					normal_line_B = Line(node_B.tuple, (normal_B + node_B.tuple).tuple).solve_length(1000,0)
					
					intersect_A_time, _ = curve_A.intersect_line(normal_line_B)
					intersect_B_time, _ = curve_B.intersect_line(normal_line_A)
					
					# -- Cleanup and sort intersection results [[x_crossing_times], [y_crossing_times]] reduced to single list.
					intersect_A_time = sorted(intersect_A_time[0] + intersect_A_time[1])
					intersect_B_time = sorted([1 - t for t in intersect_B_time[0]] + intersect_B_time[1]) # !!! Reverse the time because of contour direction !!! Find a better way
					
					# - Set flags that determine where nodes will be inserted and which of nodes A or B should be removed
					cap_flags = (False, False)
					
					# -- Flag heuristics
					if len(intersect_A_time) and len(intersect_B_time):
						cap_1 = Line(node_B.tuple, curve_A.solve_point(intersect_A_time[0]).tuple)
						cap_2 = Line(node_A.tuple, curve_B.solve_point(intersect_B_time[0]).tuple)
						cap_flags = (True, False) if cap_1.length < cap_2.length else (False, True)
						
					elif len(intersect_A_time):
						cap_flags = (True, False)
					
					elif len(intersect_B_time):
						cap_flags = (False, True)
					
					# - Process according to flag. Insert nodes and clean up redundant ones.
					if cap_flags[0]:
						new_node = node_A.insertBefore(intersect_A_time[0])
						new_node.smooth = False
						parent_contour.removeNodesBetween(new_node, node_B.fl)
						do_update = True
					
					if cap_flags[1]:
						new_node = node_B.insertAfter(intersect_B_time[0])
						new_node.smooth = False
						parent_contour.removeNodesBetween(node_A.fl, new_node)
						do_update = True

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tNormalize Cap @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def make_collinear(glyph:eGlyph, pLayers:tuple, keep_nodes:bool=False):
		'''Make two curves collinear'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()
		
		selection_per_layer = {layer:glyph.selectedNodes(layer, extend=eNode) for layer in wLayers}
		do_update = False
		
		# - Process
		for layer, selection in selection_per_layer.items():	
			print(layer, selection)	
			if len(selection) == 8:
				# - Set curves 
				curve_A = eCurveEx(selection[0].getSegmentNodes())
				curve_B = eCurveEx(selection[4].getSegmentNodes())
				new_curve_A, new_curve_B = curve_A.make_collinear(curve_B, mode=-1, equalize=True, target_width=None, apply=True)
			else:
				output(1, 'Make collinear', 'Selection must be 2 curves = 8 Nodes! Current = {}'.format(len(selection)))

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tMake collinear @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()
