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

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.node import eNode, eNodesContainer
from typerig.proxy.fl.objects.contour import pContour
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.base import Line, Vector

from typerig.core.func.collection import group_consecutive
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init ----------------------------------------------------------------------------
__version__ = '2.20.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Helpers ---------------------------------------------------------------------------
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
	def node_insert(glyph:eGlyph, pLayers:tuple, single_mode=False):
		selection = glyph.selectedAtContours(True)
		wLayers = glyph._prepareLayers(pLayers)

		# - Get selected nodes. 
		# - NOTE: Only the fist node in every selected segment is important, so we filter for that
		selection = glyph.selectedAtContours(True, filterOn=True)
		selection_dict, selection_filtered = {}, {}
		
		for cID, nID in selection:
			selection_dict.setdefault(cID,[]).append(nID)
				
		if single_mode: 
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
					glyph.insertNodeAt(cID, nodeMap[cID][nID] + float(parent.edt_time.text), layer)

		glyph.updateObject(glyph.fl, 'Insert Node @ {}.'.format('; '.join(wLayers)))

	@staticmethod
	def node_remove(glyph:eGlyph, pLayers:tuple):
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

		glyph.updateObject(glyph.fl, 'Remove Node @ {}.'.format('; '.join(wLayers)))

	# -- Corner tools -----------------------------------------------------------
	@staticmethod
	def corner_mitre(glyph:eGlyph, pLayers:tuple, radius:float):
		wLayers = glyph._prepareLayers(pLayers)
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in reversed(selection):
				node.cornerMitre(radius)

		glyph.updateObject(glyph.fl, 'Mitre Corner @ {}.'.format('; '.join(wLayers)))

	@staticmethod
	def corner_round(glyph:eGlyph, pLayers:tuple, radius:float, curvature:float=1., is_radius:bool=True):
		# - Init
		wLayers = glyph._prepareLayers(pLayers)

		# - Process				
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in selection:
				node.cornerRound(radius, curvature=curvature, isRadius=is_radius)

		glyph.updateObject(glyph.fl, 'Round Corner @ {}.'.format('; '.join(wLayers)))

	@staticmethod
	def corner_loop(glyph:eGlyph, pLayers:tuple, radius:float):
		wLayers = glyph._prepareLayers(pLayers)
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in reversed(selection):
				node.cornerMitre(-radius, True)

		glyph.updateObject(glyph.fl, 'Loop Corner @ {}.'.format('; '.join(wLayers)))

	@staticmethod
	def corner_trap(glyph:eGlyph, pLayers:tuple, incision:int, depth:int, trap:int, smooth:bool=True):
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in reversed(selection):
				node.cornerTrapInc(incision, depth, trap, smooth)

		glyph.updateObject(glyph.fl, 'Trap Corner @ {}.'.format('Trap Corner', '; '.join(wLayers)))

	@staticmethod
	def corner_rebuild(glyph:eGlyph, pLayers:tuple):
		selection_layers = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}

		for layer, selection in selection_layers.items():			
			if len(selection) > 1:
				node_first = selection[0]
				node_last = selection[-1]
				crossing = get_crossing(selection)

				node_first.smartReloc(*crossing.tuple)
				node_first.parent.removeNodesBetween(node_first.fl, node_last.getNextOn())

		glyph.updateObject(glyph.fl, 'Rebuild corner:\t{} nodes reduced @ {}'.format(len(selection), '; '.join(wLayers)))

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
	def slope_paste(glyph:eGlyph, pLayers:tuple, slope_dict:dict, mode:tuple):
		'''
		mode -> (max:bool, flip:bool) where
		minY = (False, False)
		MaXY = (True, False)
		FLminY = (False, True)
		FLMaxY = (True, True)
		'''
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

		glyph.updateObject(glyph.fl, 'Paste Slope @ %s.' %'; '.join(wLayers))
		glyph.update()


	# -- Nodes alignment ------------------------------------------------------
	@staticmethod
	def nodes_align(glyph:eGlyph, pLayers:tuple, mode:str):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				selection = glyph.selectedNodes(layer, extend=eNode)
				italicAngle = glyph.package.italicAngle_value

				if mode == 'L':
					target = min(selection, key=lambda item: item.x)
					control = (True, False)

				elif mode == 'R':
					target = max(selection, key=lambda item: item.x)
					control = (True, False)
				
				elif mode == 'T':
					temp_target = max(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
					control = (False, True)
				
				elif mode == 'B':
					temp_target = min(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
					control = (False, True)
				
				elif mode == 'C':
					newX = (min(selection, key=lambda item: item.x).x + max(selection, key=lambda item: item.x).x)/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)

				elif mode == 'E':
					newY = (min(selection, key=lambda item: item.y).y + max(selection, key=lambda item: item.y).y)/2
					newX = 0.
					target = fl6.flNode(newX, newY)
					control = (False, True)

				elif mode == 'Y':
					target = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					control = (True, False)

				elif mode == 'X':
					target = Vector(min(selection, key=lambda item: item.x).fl, max(selection, key=lambda item: item.x).fl)
					control = (False, True)

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

				elif 'FontMetrics' in mode:
					layerMetrics = glyph.fontMetricsInfo(layer)
					italicAngle = glyph.package.italicAngle_value
					
					newX = 0.
					toMaxY = True

					if '0' in mode:
						newY = layerMetrics.ascender
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '1' in mode:
						newY = layerMetrics.capsHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '2' in mode:
						newY = layerMetrics.descender
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '3' in mode:
						newY = layerMetrics.xHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '4' in mode:
						newY = 0
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '5' in mode:
						newY = parent.edt_toYpos.value
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '6' in mode:
						newY = glyph.mLine()
						toMaxY = newY >= 0 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'
						if modifiers == QtCore.Qt.ShiftModifier: toMaxY = not toMaxY

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

				if parent.chk_relations.isChecked():
					container = eNodesContainer(selection)
					
					if 'FontMetrics' in mode:
						target = fl6.flNode(newX, newY)
						control = (False, True)												
					
					container.alignTo(target, container_mode, control)

				else:
					for node in selection:
						if 'FontMetrics' in mode or mode == 'T' or mode == 'B':
							if italicAngle != 0 and not parent.chk_intercept.isChecked():
								tempTarget = Coord(node.fl)
								tempTarget.setAngle(italicAngle)

								target = fl6.flNode(tempTarget.getWidth(newY), newY)
								control = (True, True)
							
							elif parent.chk_intercept.isChecked():
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

						# - Execute Align ----------
						node.alignTo(target, control, parent.chk_smartShift.isChecked())

			glyph.updateObject(glyph.fl, 'Align Nodes @ %s.' %'; '.join(wLayers))
			glyph.update()

	# -- Node clipboard ----------------------------------------------------
	@staticmethod
	def nodes_copy(parent):
		if parent.chk_copy.isChecked():
			glyph = eGlyph()
			parent.chk_copy.setText('Reset')
			wLayers = glyph._prepareLayers(pLayers)
			parent.node_bank = {layer : eNodesContainer([node.clone() for node in glyph.selectedNodes(layer)], extend=eNode) for layer in wLayers}
		else:
			parent.node_bank = {}
			parent.chk_copy.setText('Copy')

	@staticmethod
	def nodes_paste(parent):
		if parent.chk_copy.isChecked():
			process_glyphs = getProcessGlyphs(pMode)
			modifiers = QtGui.QApplication.keyboardModifiers()
			update_flag = False

			for glyph in process_glyphs:
				wLayers = glyph._prepareLayers(pLayers)
				
				for layer in wLayers:
					if layer in parent.node_bank.keys():
						dst_container = eNodesContainer(glyph.selectedNodes(layer), extend=eNode)

						if len(dst_container):
							src_container = parent.node_bank[layer].clone()
							src_transform = QtGui.QTransform()
																		
							# - Transform
							if parent.chk_flipH.isChecked() or parent.chk_flipV.isChecked():
								scaleX = -1 if parent.chk_flipH.isChecked() else 1
								scaleY = -1 if parent.chk_flipV.isChecked() else 1
								dX = src_container.x() + src_container.width()/2.
								dY = src_container.y() + src_container.height()/2.

								src_transform.translate(dX, dY)
								src_transform.scale(scaleX, scaleY)
								src_transform.translate(-dX, -dY)
								src_container.applyTransform(src_transform)
								

							# - Align source
							if parent.copy_align_state is None:
								src_container.shift(*src_container[0].diffTo(dst_container[0]))
							else:
								src_container.alignTo(dst_container, parent.copy_align_state, align=(True,True))

							if parent.chk_reverse.isChecked(): 
								src_container = src_container.reverse()

							# - Process
							if modifiers == QtCore.Qt.ShiftModifier: # - Inject mode - insert source after first node index
								dst_container[0].contour.insert(dst_container[0].index, [node.fl for node in src_container.nodes])
								update_flag = True

							elif modifiers == QtCore.Qt.AltModifier: # - Overwrite mode - delete all nodes in selection and replace with source
								insert_index = dst_container[0].index
								insert_contour = dst_container[0].contour
								insert_contour.removeNodesBetween(dst_container[0].fl, dst_container[-1].getNextOn())
								insert_contour.insert(dst_container[0].index, [node.fl for node in src_container.nodes])
								insert_contour.removeAt(insert_index + len(src_container))

								update_flag = True

							elif modifiers == QtCore.Qt.ControlModifier: # - Overwrite mode - copy node coordinates only
								for nid in range(len(dst_container)):
									dst_container.nodes[nid].x = src_container.nodes[nid].x
									dst_container.nodes[nid].y = src_container.nodes[nid].y

								update_flag = True

							else: # - Paste mode - remap node by node
								if len(dst_container) == len(parent.node_bank[layer]):
									for nid in range(len(dst_container)):
										dst_container[nid].fl.x = src_container[nid].x 
										dst_container[nid].fl.y = src_container[nid].y 

									update_flag = True
								else:
									update_flag = False
									warnings.warn('Layer: {};\tCount Mismatch: Selected nodes [{}]; Source nodes [{}].'.format(layer, len(dst_container), len(src_container)), NodeWarning)
							
				# - Done							
				if update_flag:	
					glyph.updateObject(glyph.fl, 'Paste Nodes @ %s.' %'; '.join(wLayers))
					glyph.update()

	# -- Shift & Movement ------------------------------------------------
	@staticmethod
	def nodes_move(parent, offset_x, offset_y, method, inPercent):
		# - Init
		font = pFont()
		glyph = eGlyph()
		italic_angle = font.getItalicAngle()

		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selectedNodes = glyph.selectedNodes(layer=layer, extend=eNode)
				
				width = glyph.layer(layer).boundingBox.width() # glyph.layer().advanceWidth
				height = glyph.layer(layer).boundingBox.height() # glyph.layer().advanceHeight

				# - Process
				if method == parent.methodList[0]:
					for node in selectedNodes:
						if node.isOn:
							if inPercent:						
								node.smartShift(*scale_offset(node, offset_x, offset_y, width, height))
							else:
								node.smartShift(offset_x, offset_y)

				elif method == parent.methodList[1]:
					for node in selectedNodes:
						if inPercent:						
							node.shift(*scale_offset(node, offset_x, offset_y, width, height))
						else:
							node.shift(offset_x, offset_y)

				elif method == parent.methodList[2]:
					for node in selectedNodes:
						if inPercent:						
							node.interpShift(*scale_offset(node, offset_x, offset_y, width, height))
						else:
							node.interpShift(offset_x, offset_y)

				elif method == parent.methodList[3]:
					if italic_angle != 0:
						for node in selectedNodes:
							if inPercent:						
								node.slantShift(*scale_offset(node, offset_x, offset_y, width, height))
							else:
								node.slantShift(offset_x, offset_y, italic_angle)
					else:
						for node in selectedNodes:
							if inPercent:						
								node.smartShift(*scale_offset(node, offset_x, offset_y, width, height))
							else:
								node.smartShift(offset_x, offset_y)

				elif method == parent.methodList[4]:			
					current_layer = glyph.activeLayer().name

					if len(parent.aux.copyLine) and current_layer in parent.aux.copyLine:
						for node in selectedNodes:
							node.slantShift(offset_x, offset_y, -90 + parent.aux.copyLine[current_layer].angle)				
					else:
						warnings.warn('No slope information for layer found!\nNOTE:\tPlease <<Copy Slope>> first using TypeRig Node align toolbox.', LayerWarning)

			# - Finish it
			glyph.update()
			glyph.updateObject(glyph.fl, 'Node: %s @ %s.' %(method, '; '.join(wLayers)))