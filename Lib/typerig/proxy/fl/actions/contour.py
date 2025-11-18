# MODULE: Typerig / Proxy / FontLab / Actions / Contour
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------------------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
from itertools import groupby

import fontlab as fl6
import fontgate as fgt

from typerig.core.base.message import *
from typerig.proxy.fl.objects.base import Coord
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.shape import eShape
from typerig.proxy.fl.objects.contour import eContour
from typerig.proxy.fl.objects.font import pFontMetrics
from typerig.proxy.fl.application.app import pWorkspace

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRTransformCtrl

# - Init ---------------------------------------------------
__version__ = '3.1'
active_workspace = pWorkspace()

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Actions ------------------------------------------------
class TRContourActionCollector(object):
	''' Collection of all curve related tools '''
	
	@staticmethod
	def contour_break(pMode:int, pLayers:tuple, expand:float=20., close:bool=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			glyph.splitContour(layers=pLayers, expand=expand, close=close)
			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tBreak contour @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()
    
	@staticmethod	
	def contour_close(pMode:int, pLayers:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers)
			selection = glyph.selectedAtContours()

			for layer_name in work_layers:
				contours = glyph.contours(layer_name)

				for cID, nID in reversed(selection):
					if not contours[cID].closed: contours[cID].closed = True

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tClose contour @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod	
	def contour_slice(pMode:int, pLayers:tuple, expanded=False):
		# - Helper
		def cut_contour(contour, nid, extend=expanded):
			if extend:
				return_contour = contour.breakContourExpanded(nid, 1.)
			else:
				return_contour = contour.breakContour(nid)

			return return_contour

		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			do_update = False
			work_layers = glyph._prepareLayers(pLayers)
			selection = [(layer_name, glyph.selectedAtShapes(layer_name)) for layer_name in work_layers]

			for layer_name, selected_data in selection:
				first_sid, first_cid, first_nid = selected_data[0]
				last_sid, last_cid, last_nid = selected_data[-1]
				
				if first_sid != last_sid: break

				first_shape = glyph.shapes(layer_name)[first_sid]

				if first_cid != last_cid: # Different contours
					new_contours = []
					
					first_contour = first_shape.contours[first_cid]
					last_contour = first_shape.contours[last_cid]
					
					first_contour_parts = cut_contour(first_contour, first_nid)
					last_contour_parts = cut_contour(last_contour, last_nid)
					
					if first_contour_parts is not None and last_contour_parts is not None:
						first_contour_parts.append(last_contour_parts)
						first_contour_parts.closed = True
						first_shape.addContours([first_contour_parts])
						first_shape.removeContours([last_contour_parts])
					
					first_contour.append(last_contour)
					first_contour.closed = True
					first_shape.removeContours([last_contour])
					do_update = False

				else: # Same contour
					first_contour = first_shape.contours[first_cid]
					first_contour_nodes = first_contour.nodes()

					first_node = first_contour_nodes[first_nid]
					last_node = first_contour_nodes[last_nid]

					cut_contour(first_contour, first_nid)
					cutout = cut_contour(first_contour, last_node.index)
					first_contour.closed = True

					if cutout is not None:
						cutout.closed = True
						first_shape.addContours([cutout], True)
					
					do_update = False
					
			if do_update:	
				glyph.updateObject(glyph.fl, '%s: Slice contour @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_bool(pMode:int, pLayers:tuple, operation:str='add', reverse_order:bool=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers)
			
			# - Prepare selection
			tmp = {}
			selection = glyph.selectedAtShapes()

			for sid, cid, nid in selection:
				tmp.setdefault(sid,[]).append(cid)

			selection = {key:list(set(value)) for key, value in tmp.items()}

			# - Get contours
			
			for layer_name in work_layers:
				layer_shapes = glyph.shapes(layer_name)
				layer_contours = glyph.contours(layer_name)
				process_shapes = []
				process_fg_shapes = []
				
				# - Prepare per shape contour list
				for sid, cid_list in selection.items():
					process_tuple = (layer_shapes[sid], [layer_contours[cid] for cid in cid_list])
					process_shapes.append(process_tuple)

				# - Cleanup and convert
				for shape, contours in process_shapes:
					new_fl_shape = fl6.flShape()
					shape.removeContours(contours)
					new_fl_shape.addContours(contours, True)

					new_fg_shape = fgt.fgShape()
					new_fl_shape.convertToFgShape(new_fg_shape)

					# - Convert each contour into a separate fgShape
					for contour in new_fg_shape.contours:
						temp_fg_shape = fgt.fgShape()
						temp_fg_shape.addContour(contour)
						process_fg_shapes.append(temp_fg_shape)

				# - Perform boolean operation
				process_fg_shapes = list(reversed(process_fg_shapes)) if reverse_order else process_fg_shapes
				base_fg_shape = process_fg_shapes[0]

				for bop_shape in process_fg_shapes[1:]:
					if operation == 'add':
						base_fg_shape.addShape(bop_shape)
					
					elif operation == 'subtract':
						base_fg_shape.subtractShape(bop_shape)

					elif operation == 'intersect':
						base_fg_shape.intersectShape(bop_shape)

					elif operation == 'exclude':
						base_fg_shape.excludeShape(bop_shape)
				
				# - Append the results to the first/last shape in selection
				base_fl_shape = process_shapes[[0, -1][reverse_order]][0]
				processed_fl_shape = fl6.flShape(base_fg_shape)
				base_fl_shape.addContours(processed_fl_shape.contours, True)

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\t{} contours @ {}.'.format(operation.title(), glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_set_start(pMode:int, pLayers:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers, False)
			
			selected_contours = {layer:glyph.selectedAtContours(layer)[0] for layer in work_layers}

			for layer, selection in selected_contours.items():
				cid, nid = selection
				glyph.contours(layer)[cid].setStartPoint(nid)

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tSet start point @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_set_start_next(pMode:int, pLayers:tuple, set_previous=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers, False)
			
			for layer in work_layers:
				for contour in glyph.selectedContours(layer):
					contour_nodes = contour.nodes()[1:]
					if set_previous: contour_nodes = reversed(contour_nodes)

					for node in contour_nodes:
						if node.isOn():
							contour.setStartPoint(node.index)
							break

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tMove start point @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_set_order(pMode:int, pLayers:tuple, sort_order:tuple, reverse_sort:bool=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers, False)

			reverse_order = []
			for item in sort_order:
				new_item = not item if item is not None else None
				reverse_order.append(new_item)

			for layer in work_layers:
				work_shapes = glyph.shapes(layer, extend=eShape)

				for shape in work_shapes:
					if reverse_sort:
						shape.contourOrder(reverse_order)
					else:
						shape.contourOrder(sort_order)

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tSet contour order @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_smart_start(pMode:int, pLayers:tuple, control:tuple=(0,0)):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers, False)

			if control == (0,0): 	# BL
				criteria = lambda node : (node.y, node.x)
			elif control == (0,1): 	# TL
				criteria = lambda node : (-node.y, node.x)
			elif control == (1,0): 	# BR
				criteria = lambda node : (node.y, -node.x)
			elif control == (1,1): 	# TR
				criteria = lambda node : (-node.y, -node.x)
			
			for layer_name in work_layers:
				contours = glyph.contours(layer_name)

				for contour in contours:
					onNodes = [node for node in contour.nodes() if node.isOn()]
					new_first_node = sorted(onNodes, key=criteria)[0]
					contour.setStartPoint(new_first_node.index)

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tSet start point (Smart) @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def contour_set_winding(pMode:int, pLayers:tuple, ccw:bool=True):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			selection = glyph.selectedAtContours()

			work_layers = glyph._prepareLayers(pLayers, False)

			for layer_name in work_layers:
				all_contours = glyph.contours(layer_name)

				if len(selection):
					process_contours = [eContour(all_contours[item[0]]) for item in selection]
				else:
					process_contours = [eContour(contour) for contour in all_contours]

				for contour in process_contours:
					if ccw:
						contour.setCCW()
					else:
						contour.setCW()

			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tSet contour winding @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()


	@staticmethod
	def contour_align(pMode:int, pLayers:tuple, align_mode:str, align_x:str, align_y:str, reverse_order:bool=False, contour_A:dict={}, contour_B:dict={}):
		# - Helpers
		def getContourBonds(work_contours):
			tmp_bounds = [contour.bounds for contour in work_contours]
			cont_min_X, cont_min_Y, cont_max_X, cont_max_Y = map(set, zip(*tmp_bounds))
			return (min(cont_min_X), min(cont_min_Y), max(cont_max_X), max(cont_max_Y))

		def getAlignDict(bounds_tuple):
			align_dict = {	'L': bounds_tuple[0], 
							'R': bounds_tuple[2],
							'C': bounds_tuple[0] + (bounds_tuple[2] - bounds_tuple[0])/2,
							'B': bounds_tuple[1], 
							'T': bounds_tuple[3], 
							'E': bounds_tuple[1] + (bounds_tuple[3] - bounds_tuple[1])/2
						}

			return align_dict

		# - Init
		keep_x, keep_y = True, True	

		if align_x == 'K': keep_x = False; align_x = 'L'
		if align_y == 'X': keep_y = False; align_y = 'B'		
		
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			selection = glyph.selectedAtContours()
			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				glyph_contours = glyph.contours(layer_name, extend=eContour)
				work_contours = [glyph_contours[index] for index in list(set([item[0] for item in selection]))]
				
				if align_mode =='CC': # Align contours to contours
					if 1 < len(work_contours) < 3:
						c1, c2 = work_contours
						if not reverse_order:
							c1.alignTo(c2, align_x + align_y, (keep_x, keep_y))
						else:
							c2.alignTo(c1, align_x + align_y, (keep_x, keep_y))

					elif len(work_contours) > 2:
						cont_bounds = getContourBonds(work_contours)
						align_type = getAlignDict(cont_bounds)
						target = Coord(align_type[align_x], align_type[align_y])

						if reverse_order: work_contours = reversed(work_contours)

						for contour in work_contours:
							contour.alignTo(target, align_x + align_y, (keep_x, keep_y))
					
				elif align_mode == 'CN': # Align contour to node
					target = work_contours.pop(0)
					target_node_index = selection[0][1] if not reverse_order else selection[-1][1]
					target_node = target.fl.nodes()[target_node_index]

					for contour in work_contours:
							contour.alignTo(target_node, align_x + align_y, (keep_x, keep_y))

				# !!! To be implemented
				elif align_mode == 'NN': # Align a node on contour to node on another
					pass

				elif align_mode == 'AB': # Align contours A to B
					if len(contour_A.keys()) and len(contour_B.keys()):
						cont_bounds_A = getContourBonds(contour_A[layer_name])
						align_type_A = getAlignDict(cont_bounds_A)

						cont_bounds_B = getContourBonds(contour_B[layer_name])
						align_type_B = getAlignDict(cont_bounds_B)
						
						target = Coord(align_type_B[align_x], align_type_B[align_y])
						group_base = Coord(align_type_A[align_x], align_type_A[align_y])

						for contour in reversed(contour_A[layer_name]):
							align_temp =  getAlignDict(contour.bounds)
							contour_base = Coord(align_temp[align_x], align_temp[align_y])
							contour_delta = group_base - contour_base

							contour.alignTo(target - contour_delta, align_x + align_y, (keep_x, keep_y))

				elif align_mode == 'DH': # Distribute contours horizontally
						cont_bounds = getContourBonds(work_contours)
						cont_width = cont_bounds[2] - cont_bounds[0]
						
						sorted_contours = sorted(work_contours, key=lambda c: c.x)
						
						cont_widths = [contour.width for contour in sorted_contours]
						cont_gap = (cont_width - sum(cont_widths))/(len(cont_widths) - 1)
						
						cont_x = []
						curr_width = cont_bounds[0]
						
						while len(cont_widths):
							cont_width = cont_widths.pop(0)
							curr_width += cont_width + cont_gap
							cont_x.append(curr_width)

						cont_x = [cont_bounds[0]] + cont_x[:-1]

						for cid in range(len(sorted_contours)):
							contour = sorted_contours[cid]
							align_temp =  getAlignDict(contour.bounds)
							align_target = Coord(cont_x[cid], align_temp['B'])
							contour.alignTo(align_target, 'LB', (True, False))

				elif align_mode == 'DV': # Distribute contours vertically
						cont_bounds = getContourBonds(work_contours)
						cont_height = cont_bounds[3] - cont_bounds[1]
						
						sorted_contours = sorted(work_contours, key=lambda c: c.y)
						
						cont_heights = [contour.height for contour in sorted_contours]
						cont_gap = (cont_height - sum(cont_heights))/(len(cont_heights) - 1)
						
						cont_y = []
						curr_height = cont_bounds[1]
						
						while len(cont_heights):
							cont_height = cont_heights.pop(0)
							curr_height += cont_height + cont_gap
							cont_y.append(curr_height)

						cont_y = [cont_bounds[1]] + cont_y[:-1]

						for cid in range(len(sorted_contours)):
							contour = sorted_contours[cid]
							align_temp =  getAlignDict(contour.bounds)
							align_target = Coord(align_temp['L'], cont_y[cid])
							contour.alignTo(align_target, 'LB', (False, True))

				else:
					metrics = pFontMetrics(glyph.package)
					max_layer_y = max([metrics.getXHeight(layer_name), metrics.getCapsHeight(layer_name), metrics.getAscender(layer_name)])
					min_layer_y = min([0, metrics.getDescender(layer_name)])
					layer_bounds = QtCore.QRect(0, 0, glyph.getAdvance(layer_name), abs(max_layer_y) + abs(min_layer_y))

					if align_mode == 'CL': # Align all contours in given Layer
						cont_bounds = (layer_bounds.x(), layer_bounds.y(), layer_bounds.x() + layer_bounds.width(), layer_bounds.y() + layer_bounds.height())
					
					elif align_mode == 'CMX': # Align all contours to X height
						height = metrics.getXHeight(layer_name)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif align_mode == 'CMC': # Align all contours to Caps height
						height = metrics.getCapsHeight(layer_name)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif align_mode == 'CMA': # Align all contours to Ascender height
						height = metrics.getAscender(layer_name)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif align_mode == 'CMD': # Align all contours to Descender depth
						height = metrics.getDescender(layer_name)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					align_type = getAlignDict(cont_bounds)
					target = Coord(align_type[align_x], align_type[align_y])					

					if len(contour_A): work_contours += contour_A[layer_name]
					if len(contour_B): work_contours += contour_B[layer_name]

					for contour in work_contours:
						contour.alignTo(target, align_x + align_y, (keep_x, keep_y))


			glyph.update()
			glyph.updateObject(glyph.fl, '{};\tAlign contours @ {}.'.format(glyph.name, '; '.join(work_layers)))

		active_workspace.getCanvas(True).refreshAll()

		# !!! Todo: Transform and copy?