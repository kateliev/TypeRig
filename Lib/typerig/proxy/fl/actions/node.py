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

from collections import namedtuple

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
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.objects.metapen import fake_stroke_expand, CAP_BUTT, CAP_ROUND
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init ----------------------------------------------------------------------------
__version__ = '3.5'
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
	'''Crossing of the straight prev/next lines around a selection.

	NOTE: chord based and line only. Kept for callers that want the plain
	polygon crossing; corner rebuilding uses get_corner_rebuild() instead,
	which respects curve segments.
	'''
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

TRCornerRebuild = namedtuple('TRCornerRebuild',
	'node_first node_last new_in new_out corner in_seg_nodes next_on corner_size')

def get_corner_span(node_from, node_to, limit=1000):
	'''On-curve steps walking forward from node_from until node_to is reached.

	Returns None when node_to is not reachable that way - a different contour,
	or the walk coming back around to where it started.
	'''
	steps = 0
	cursor = node_from.getNextOn(False)

	while cursor is not None and cursor.fl != node_to.fl:
		if cursor.fl == node_from.fl or steps > limit:
			return None

		steps += 1
		cursor = cursor.getNextOn(False)

	if cursor is None:
		return None

	return steps + 1		# node_to collapses into the cusp as well

def resolve_corner_ends(node_a, node_b):
	'''Order two selected on-curve nodes so the corner lies between them.

	selectedNodes() reports in contour order, which says nothing about where the
	contour's start point sits: when it falls inside the corner, the node AFTER
	the corner is reported first. A corner is a short, local feature, so the
	shorter of the two ways round is the corner and the longer one is the rest
	of the glyph - without this the tool would take most of the contour for
	"the corner" and delete it.

	Returns (node_first, node_last, corner_size) or None.
	'''
	forward = get_corner_span(node_a, node_b)
	backward = get_corner_span(node_b, node_a)

	if forward is None and backward is None:
		return None

	if backward is not None and (forward is None or backward < forward):
		return node_b, node_a, backward

	return node_a, node_b, forward

def get_segment_ending_at(node):
	'''The segment that ENDS at the given on-curve node, by walking the ring.

	Returns a tuple of flNodes - 2 for a line, 4 for a cubic - or None when the
	run of nodes is not one this handles (TrueType off-curves, malformed runs).

	NOTE: this deliberately does NOT use eNode.getSegmentNodes(). That one
	decides line-vs-curve from contour.segment(contour.getT(node)) - a float
	parametric time - and only walks the ring afterwards. When the time lookup
	lands on the neighbouring segment the length test describes one segment
	while the walk builds another, so a line's on-curve nodes get handed back
	in the slots where BCPs are expected. Writing handle coordinates into those
	slots then moves real on-curve nodes elsewhere in the glyph. Walking the
	ring cannot land on the wrong segment.
	'''
	prev_node = node.getPrev(False)

	if prev_node is None:
		return None

	if prev_node.isOn:
		return (prev_node.fl, node.fl)

	bcp_in = prev_node
	bcp_out = bcp_in.getPrev(False)

	if bcp_out is None or bcp_out.isOn:
		return None

	prev_on = bcp_out.getPrev(False)

	if prev_on is None or not prev_on.isOn:
		return None

	return (prev_on.fl, bcp_out.fl, bcp_in.fl, node.fl)

def get_segment_starting_at(node):
	'''The segment that STARTS at the given on-curve node, by walking the ring.

	Mirror of get_segment_ending_at() - see its note on why the ring is walked
	rather than asking for the segment by parametric time.
	'''
	next_node = node.getNext(False)

	if next_node is None:
		return None

	if next_node.isOn:
		return (node.fl, next_node.fl)

	bcp_out = next_node
	bcp_in = bcp_out.getNext(False)

	if bcp_in is None or bcp_in.isOn:
		return None

	next_on = bcp_in.getNext(False)

	if next_on is None or not next_on.isOn:
		return None

	return (node.fl, bcp_out.fl, bcp_in.fl, next_on.fl)

def get_corner_segments(node_first, node_last):
	'''Geometry of the two segments that survive a corner collapse.

	node_first is the last node kept on the incoming side, node_last the first
	node kept on the outgoing side; everything between them is the corner.

	Returns (seg_in, seg_out, in_seg_nodes, next_on) where seg_in/seg_out are
	Line or Curve depending on what the contour actually holds, in_seg_nodes is
	the raw flNode tuple of the incoming segment and next_on is the on-curve
	node closing the outgoing segment.

	NOTE: the flNodes handed back are only good until the contour is
	restructured - write to them before any removal, never after.

	Returns None when a segment is TrueType or otherwise not handled here.
	'''
	in_seg_nodes = get_segment_ending_at(node_first)
	out_seg_nodes = get_segment_starting_at(node_last)

	if in_seg_nodes is None or out_seg_nodes is None:
		return None

	prev_on = in_seg_nodes[0]
	next_on = out_seg_nodes[-1]

	# - The corner must leave something outside it to rebuild from
	if next_on == node_first.fl or prev_on == node_last.fl:
		return None

	seg_in = Curve(in_seg_nodes) if len(in_seg_nodes) == 4 else Line((prev_on.x, prev_on.y), node_first.tuple)
	seg_out = Curve(out_seg_nodes) if len(out_seg_nodes) == 4 else Line(node_last.tuple, (next_on.x, next_on.y))

	return seg_in, seg_out, in_seg_nodes, next_on

def get_corner_rebuild(node_a, node_b):
	'''Solve the cusp that rebuilds the corner bracketed by two on-curve nodes.

	The corner is whichever of the two ways round between node_a and node_b is
	shorter, so the caller need not know which of the two the selection put
	first.

	Returns a TRCornerRebuild, or None when the two nodes do not bracket a
	single corner on one contour, or the two sides never cross - parallel, or
	a crossing too far off to be a corner.
	'''
	resolved = resolve_corner_ends(node_a, node_b)

	if resolved is None:
		return None

	node_first, node_last, corner_size = resolved
	segments = get_corner_segments(node_first, node_last)

	if segments is None:
		return None

	seg_in, seg_out, in_seg_nodes, next_on = segments
	new_in, new_out, corner = CubicBezier.corner_rebuild(seg_in, seg_out)

	if corner is None:
		return None

	return TRCornerRebuild(node_first, node_last, new_in, new_out, corner,
							in_seg_nodes, next_on, corner_size)

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
	def corner_loop_to_targets(pMode:int, pLayers:tuple):
		'''Loop corner extending to target segments.
		Select 3+ on-curve nodes: the corner is auto-detected (sharpest angle),
		the other two define bounding segments the loop should reach.
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)

				if len(selection) < 3:
					output(1, 'Loop to Target', 'Need 3 selected on-curve nodes: 2 bounds + 1 corner.')
					continue

				# - Find corner node by sharpest angle
				angles = []
				for node in selection:
					prev_on = node.getPrevOn(False)
					next_on = node.getNextOn(False)
					vp = (prev_on.x - node.x, prev_on.y - node.y)
					vn = (next_on.x - node.x, next_on.y - node.y)
					dot = vp[0] * vn[0] + vp[1] * vn[1]
					cross = abs(vp[0] * vn[1] - vp[1] * vn[0])
					angles.append(math.atan2(cross, dot))

				corner_idx = angles.index(min(angles))
				corner_node = selection[corner_idx]
				bound_nodes = [s for i, s in enumerate(selection) if i != corner_idx]

				# - Build target lines from bound nodes
				# -- Use the secant through each bound node's neighbors as the target
				target_lines = []
				for bnode in bound_nodes:
					bp = bnode.getPrevOn(False)
					bn = bnode.getNextOn(False)
					target_lines.append(Line(bp.tuple, bn.tuple))

				# - Assign targets to incoming/outgoing sides
				# -- Compare distance from each bound to corner's prev/next neighbors
				prev_on = corner_node.getPrevOn(False)
				next_on = corner_node.getNextOn(False)

				d0_prev = math.hypot(bound_nodes[0].x - prev_on.x, bound_nodes[0].y - prev_on.y)
				d0_next = math.hypot(bound_nodes[0].x - next_on.x, bound_nodes[0].y - next_on.y)

				if d0_prev < d0_next:
					target_in = target_lines[0]
					target_out = target_lines[1]
				else:
					target_in = target_lines[1]
					target_out = target_lines[0]

				# - Execute
				corner_node.cornerLoopToTargets(target_in, target_out)

			glyph.updateObject(glyph.fl, '{};\tLoop to Target @ {}.'.format(glyph.name, '; '.join(wLayers)))

		active_workspace.getCanvas(True).refreshAll()

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
		'''Collapse a rounded or multi-node corner back to a cusp.

		The selection brackets the corner: of the two outermost selected
		on-curve nodes, the one before the corner keeps the incoming side and
		the one after it keeps the outgoing side. Both are then run out along
		their own geometry until they cross and everything in between is
		dropped. Which node is which is worked out from the contour, so the
		tool does not care where the contour's start point sits.

		Either side may be a line or a curve. For LL--CC--AA the result is
		LL--AA meeting at the crossing of the line projection with the arc
		continuation, and AA keeps the curvature it had before the corner was
		rounded - its handles are recomputed by de Casteljau splitting at the
		solved time, not straightened.
		'''
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init
			wLayers = glyph._prepareLayers(pLayers)
			done_flag = False
			nodes_reduced = 0

			for layer in wLayers:
				selection = [node for node in glyph.selectedNodes(layer, extend=eNode) if node.isOn]

				if len(selection) < 2: continue

				# - One corner per run: a selection spanning two contours has no
				#   single crossing to solve for. Which of the two outermost
				#   nodes comes first is worked out from the contour, not from
				#   the selection order
				rebuild = get_corner_rebuild(selection[0], selection[-1])

				if rebuild is None:
					warnings.warn('SKIP:\tNo single corner to rebuild from this selection! Layer: {}'.format(layer), LayerWarning)
					continue

				node_first = rebuild.node_first
				new_in, new_out, corner = rebuild.new_in, rebuild.new_out, rebuild.corner
				is_curve_in = len(rebuild.in_seg_nodes) == 4
				is_curve_out = isinstance(new_out, CubicBezier)

				# - Refuse rather than corrupt: handle coordinates may only ever
				#   be written into off-curve slots. If anything ever hands back
				#   an on-curve node where a BCP belongs, writing to it would
				#   drag a real node across the glyph instead of moving a handle
				if is_curve_in and (rebuild.in_seg_nodes[1].isOn() or rebuild.in_seg_nodes[2].isOn()):
					warnings.warn('SKIP:\tIncoming segment is not a clean curve! Layer: {}'.format(layer), LayerWarning)
					continue

				if cleanup_nodes:
					parent_contour = node_first.contour

					# - Everything on the surviving geometry is written BEFORE
					#   the contour is restructured. removeNodesBetween()
					#   invalidates the flNodes captured above, so writing to
					#   them afterwards lands on whatever now sits at those
					#   positions - handles elsewhere in the glyph move instead.
					#   Every other corner tool here works in this order too.
					if is_curve_in:
						in_seg_nodes = rebuild.in_seg_nodes
						in_seg_nodes[1].x, in_seg_nodes[1].y = new_in.p1.x, new_in.p1.y
						in_seg_nodes[2].x, in_seg_nodes[2].y = new_in.p2.x, new_in.p2.y

					# - A rebuilt corner is a cusp. Clear the flag before the
					#   node moves, or FL mirrors the handles back
					node_first.fl.smooth = False
					node_first.reloc(corner.x, corner.y)

					# - Drop the corner. This flattens the outgoing segment too,
					#   so it is rebuilt from new_out below
					parent_contour.removeNodesBetween(node_first.fl, rebuild.next_on)
					nodes_reduced += rebuild.corner_size

					# - Outgoing side: give the arc its segment back. Every node
					#   here is walked fresh from node_first - nothing captured
					#   before the removal is touched again
					if is_curve_out:
						line_end = node_first.getNext(False)

						if line_end is not None and line_end.isOn:
							# - convertToCurve() acts on the segment ENDING at
							#   the node, so it is called on the far end
							line_end.fl.convertToCurve()

							bcp_out = node_first.getNext(False)
							bcp_in = bcp_out.getNext(False) if bcp_out is not None else None

							if bcp_out is not None and bcp_in is not None \
								and not bcp_out.isOn and not bcp_in.isOn:
								bcp_out.reloc(new_out.p1.x, new_out.p1.y)
								bcp_in.reloc(new_out.p2.x, new_out.p2.y)

				else:
					# - Keep the node count, just pull the selection onto the cusp
					for node in selection:
						node.smartReloc(corner.x, corner.y)

				done_flag = True

			if done_flag:
				glyph.updateObject(glyph.fl, '{};\tRebuild corner:\t{} nodes reduced @ {}'.format(glyph.name, nodes_reduced, '; '.join(wLayers)))

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
	def nodes_align(pMode:int, pLayers:tuple, mode:str, intercept:bool=False, keep_relations:bool=False, smart_shift:bool=False, ext_target:dict={}, lerp_shift:bool=False, extrapolate:bool=False):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		# Axis for extrapolation is determined by the alignment mode, not by delta heuristics.
		# X-moving modes: L, R, C, BBoxCenterX, peerCenterX, Y (vector)
		# Y-moving modes: T, B, E, BBoxCenterY, peerCenterY, FontMetrics*, X (vector)
		_extrap_x_modes = {'L', 'R', 'C', 'BBoxCenterX', 'peerCenterX'}
		_extrap_use_y   = mode not in _extrap_x_modes

		def _bezier_align(node, target_val, use_y):
			'''Slide node along its outgoing bezier segment (or its mathematical extension)
			to the position where B_y(t)==target_val (or B_x(t)).
			Updates the on-curve node and both outgoing off-curve handles via de Casteljau.
			node.getSegmentNodes() -> [node=p0(t=0), bcp1, bcp2, next_on=p3(t=1)]
			solve_slice(t).second -> [B(t), new_bcp1, new_bcp2, p3]
			'''
			use_prev = False
			seg = node.getSegmentNodes()
			prev_seg = node.getPrevOn(False).getSegmentNodes()

			# Linear segment
			if len(seg) < 4 and len(prev_seg) < 4:
					return

			if len(seg) < 4 and len(prev_seg) == 4:
				# Cubic segment
				curve = CubicBezier(
				(prev_seg[0].x, prev_seg[0].y),
				(prev_seg[1].x, prev_seg[1].y),
				(prev_seg[2].x, prev_seg[2].y),
				(prev_seg[3].x, prev_seg[3].y))
				use_prev = True
			else:
				# Cubic segment
				curve = CubicBezier(
				(seg[0].x, seg[0].y),
				(seg[1].x, seg[1].y),
				(seg[2].x, seg[2].y),
				(seg[3].x, seg[3].y))

			# - Config: guards against cubic extrapolation blow-up.
			# find_t_for_*() returns UNCLAMPED roots (t may be far outside [0,1]).
			# solve_slice() is de Casteljau (cubic in t), so evaluating it at an
			# extreme t explodes the handles and flips the curve. We therefore
			# only trust the exact slice inside a bounded window; beyond it we
			# fall back to a tame tangent-line slide that still hits the target.
			T_PARAM_MARGIN = 1.0    # allow |t - end| up to one segment beyond an end
			DIST_FACTOR    = 4.0    # ... and node travel up to N * curve chord

			# - Endpoint the node currently sits on (t=0 outgoing, t=1 prev)
			end_t = 1.0 if use_prev else 0.0
			target_nodes = prev_seg if use_prev else seg  # FL nodes to update
			n_idx = 3 if use_prev else 0                   # on-curve node index
			h_idx = 2 if use_prev else 1                   # near off-curve handle

			old_x = curve.p3.x if use_prev else curve.p0.x
			old_y = curve.p3.y if use_prev else curve.p0.y

			def _finite(*vals):
				return all(v == v and v not in (float('inf'), float('-inf')) for v in vals)

			# - Reference scale for the travel guard
			chord = math.hypot(curve.p3.x - curve.p0.x, curve.p3.y - curve.p0.y)
			ref = max(chord, curve.height if use_y else curve.width, 1.0)
			max_travel = DIST_FACTOR * ref

			def _tangent_slide():
				'''Fake, tame extension: slide the node along the endpoint tangent
				line until the solved axis equals target_val, translating its near
				handle by the same delta so the tangent (curve shape at the node)
				is preserved. Always finite; hits the target exactly.'''
				_, d1, _ = curve.solve_derivative_at_time(end_t)
				tx, ty = d1.x, d1.y

				# Retracted handle -> no tangent; use chord direction instead
				if math.hypot(tx, ty) < 1e-9:
					tx, ty = curve.p3.x - curve.p0.x, curve.p3.y - curve.p0.y

				denom = ty if use_y else tx

				if abs(denom) > 1e-6:
					s = (target_val - (old_y if use_y else old_x)) / denom
					dx, dy = s * tx, s * ty
				else:
					# Tangent parallel to the solved axis: move straight along it
					dx, dy = (0.0, target_val - old_y) if use_y else (target_val - old_x, 0.0)

				if not _finite(dx, dy):
					output(1, 'Align+Extrapolate', 'Node [{},{}]: degenerate tangent, skipped'.format(round(node.x), round(node.y)))
					return

				target_nodes[n_idx].x += dx; target_nodes[n_idx].y += dy
				target_nodes[h_idx].x += dx; target_nodes[h_idx].y += dy

			# - Solve (pick the root closest to the node's own endpoint)
			candidates = curve.find_t_for_y(target_val) if use_y else curve.find_t_for_x(target_val)
			valid = [t for t in candidates if abs(t - 0.0) > 1e-3 and abs(t - 1.0) > 1e-3]
			best_t = min(valid, key=lambda t: abs(t - end_t)) if valid else None

			# - Trust the exact de Casteljau slice only inside the window
			if best_t is not None and abs(best_t - end_t) <= T_PARAM_MARGIN:
				first, second = curve.solve_slice(best_t)

				if use_prev:
					# [prev_on=p0(fixed), outer_bcp, inner_bcp, node=B(t)]
					new_pts = (first.p3, first.p2, first.p1)  # node, inner, outer
					idx = (3, 2, 1)
				else:
					# [node=B(t), bcp1, bcp2, next_on=p3(fixed)]
					new_pts = (second.p0, second.p1, second.p2)  # node, bcp1, bcp2
					idx = (0, 1, 2)

				travel = math.hypot(new_pts[0].x - old_x, new_pts[0].y - old_y)
				coords_ok = _finite(*[c for p in new_pts for c in (p.x, p.y)])

				if coords_ok and travel <= max_travel:
					for k, p in zip(idx, new_pts):
						target_nodes[k].x = p.x
						target_nodes[k].y = p.y
					return

				# Slice blew up (extreme t) -> tame it below
				output(1, 'Align+Extrapolate', 'Node [{},{}]: extrapolation clamped -> tangent slide'.format(round(node.x), round(node.y)))

			# - Fallback: no usable root, out-of-window, or blow-up
			_tangent_slide()


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
						if extrapolate and node.isOn:
							target_val = target.y if _extrap_use_y else target.x
							_bezier_align(node, target_val, _extrap_use_y)
						else:
							node.alignTo(target, control, smart_shift, lerp_shift)

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

				# - Guard: a near-collinear corner yields a meaningless (and,
				# after the -.1 hack, negative) radius. Skip rather than build a
				# degenerate / exploding cap.
				if not (radius == radius) or radius < 1.0:
					output(1, 'Round Cap', 'Corner too shallow (r={}); skipped.'.format(round(radius, 2)))
					continue

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

				# - Guard: a near-collinear corner yields a meaningless (and,
				# after the -.1 hack, negative) radius. Skip rather than build a
				# degenerate / exploding cap.
				MIN_RADIUS = 1.0
				if not (radius == radius) or radius < MIN_RADIUS:
					output(1, 'Round Cap', 'Corner too shallow (r={}); skipped.'.format(round(radius, 2)))
					continue

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
					# Geometric radius kept as a safe fallback for the recompute below
					radius_geom = radius

					if modifiers == QtCore.Qt.ShiftModifier or modifiers == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
						# - Calculate radius differently
						curve_A = Curve(*segment_A)
						curve_B = Curve(*segment_B)

						# -- Initial segmentation (arc-length, clamped to [0,1])
						len_A = curve_A.get_arc_length()
						len_B = curve_B.get_arc_length()
						time_A = curve_A.solve_t_at_length(max(0., len_A - radius))
						time_B = curve_B.solve_t_at_length(min(len_B, radius))
						
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

						# - Bound the recomputed radius: a near-parallel / degenerate
						# crossing can inflate it into a glyph-spanning cap. Fall back
						# to the geometric radius when non-finite or non-positive.
						radius_max = 4. * node_A.distanceToNext()
						if not (radius == radius) or radius <= 0.:
							radius = radius_geom
						radius = min(max(radius, MIN_RADIUS), radius_max)

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
						# Arc-length, clamped to [0,1] — avoids negative / overshoot
						# times when radius exceeds the segment's reach.
						len_A = curve_A.get_arc_length()
						len_B = curve_B.get_arc_length()
						new_time_A = curve_A.solve_t_at_length(max(0., len_A - radius))
						new_time_B = curve_B.solve_t_at_length(min(len_B, radius))
						
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

			# - Parallel / collinear handles have no finite crossing; reloc'ing
			# with a Void (NaN, NaN) would write NaN coords and corrupt the
			# contour. Skip this cap instead.
			if (isinstance(crossing_A, Void) or isinstance(crossing_B, Void)
				or crossing_A.x != crossing_A.x or crossing_B.x != crossing_B.x):
				output(1, 'Rebuild Cap', 'Parallel handles; cap skipped.')
				return

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
					# - Config: guards against cap-normalize blow-up.
					# The old code (a) divided by a possibly-zero curve derivative
					# when building the normal, (b) mixed the spurious x-crossing
					# roots with the real ones and picked the SMALLEST time, and
					# (c) reversed only the x-times by 1-t. Any of these could land
					# the inserted node far from the cap end, so removeNodesBetween
					# swept across the glyph and the cap "exploded".
					NORMAL_LEN = 1000.   # half-length of the probe normal line
					DIST_FACTOR = 4.0    # max cap length as multiple of current opening

					# - Set curves
					curve_A = Curve(*segment_A)
					curve_B = Curve(*segment_B)

					# - Safe unit normal at a curve endpoint (falls back to the
					# chord normal when the handle is retracted / derivative ~0)
					def _unit_normal(curve, t):
						_, d1, _ = curve.solve_derivative_at_time(t)
						m = math.hypot(d1.x, d1.y)
						if m < 1e-9:
							dx, dy = curve.p3.x - curve.p0.x, curve.p3.y - curve.p0.y
							m = math.hypot(dx, dy)
							if m < 1e-9:
								return None
							return (-dy / m, dx / m)
						return (-d1.y / m, d1.x / m)

					normal_A = _unit_normal(curve_A, 1)  # at node_A
					normal_B = _unit_normal(curve_B, 0)  # at node_B

					if normal_A is None or normal_B is None:
						output(1, 'Normalize Cap', 'Degenerate curve tangent; skipped.')
						continue

					# - Symmetric probe lines (extend both ways so the hit can be
					# on either side of the endpoint)
					normal_line_A = Line((node_A.x - NORMAL_LEN * normal_A[0], node_A.y - NORMAL_LEN * normal_A[1]),
					                     (node_A.x + NORMAL_LEN * normal_A[0], node_A.y + NORMAL_LEN * normal_A[1]))
					normal_line_B = Line((node_B.x - NORMAL_LEN * normal_B[0], node_B.y - NORMAL_LEN * normal_B[1]),
					                     (node_B.x + NORMAL_LEN * normal_B[0], node_B.y + NORMAL_LEN * normal_B[1]))

					# - Pick the intersection on `curve` that lies on the finite
					# probe line and is nearest the cap end (prefer_t). The on-line
					# test discards spurious roots; nearest-endpoint keeps the
					# inserted node close to the cap so the cap stays short.
					def _pick_time(curve, probe_line, prefer_t):
						(times_x, times_y), _ = curve.intersect_line(probe_line)
						best, best_key = None, None
						for t in list(times_x) + list(times_y):
							if not (1e-3 < t < 1. - 1e-3):
								continue
							pt = curve.solve_point(t)
							if not probe_line.hasPoint(pt):
								continue
							key = abs(t - prefer_t)
							if best_key is None or key < best_key:
								best, best_key = t, key
						return best

					time_A = _pick_time(curve_A, normal_line_B, 1.)  # new node on A, near node_A
					time_B = _pick_time(curve_B, normal_line_A, 0.)  # new node on B, near node_B

					# - Candidate cap lengths, rejecting non-finite / over-long caps
					cap_ref = max(math.hypot(node_A.x - node_B.x, node_A.y - node_B.y), 1.)
					max_cap = DIST_FACTOR * cap_ref

					def _cap_len(anchor_node, curve, t):
						if t is None:
							return None
						p = curve.solve_point(t)
						length = math.hypot(anchor_node.x - p.x, anchor_node.y - p.y)
						if length != length or length in (float('inf'), float('-inf')) or length > max_cap:
							return None
						return length

					len_A = _cap_len(node_B, curve_A, time_A)  # cap = new A-node -> node_B
					len_B = _cap_len(node_A, curve_B, time_B)  # cap = node_A -> new B-node

					# - Choose the shorter valid cap
					cap_flags = (False, False)
					if len_A is not None and len_B is not None:
						cap_flags = (True, False) if len_A <= len_B else (False, True)
					elif len_A is not None:
						cap_flags = (True, False)
					elif len_B is not None:
						cap_flags = (False, True)
					else:
						output(1, 'Normalize Cap', 'No sane normal cap found; skipped.')

					# - Process according to flag. Insert node and clean up.
					if cap_flags[0]:
						new_node = node_A.insertBefore(time_A)
						new_node.smooth = False
						parent_contour.removeNodesBetween(new_node, node_B.fl)
						do_update = True

					if cap_flags[1]:
						new_node = node_B.insertAfter(time_B)
						new_node.smooth = False
						parent_contour.removeNodesBetween(node_A.fl, new_node)
						do_update = True

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tNormalize Cap @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def make_collinear(glyph:eGlyph, pLayers:tuple, equalize:bool=False,
	                   snap_lookup:dict=None, snap_tolerance:float=0.25):
		'''Make two curves collinear.

		snap_lookup: optional {master_name: preset_width} dict. When set and
		equalize=True, the per-layer width is snapped to the master's preset
		within snap_tolerance * measured.
		'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()

		selection_per_layer = {layer:glyph.selectedNodes(layer, extend=eNode) for layer in wLayers}
		do_update = False

		# - Process
		for layer, selection in selection_per_layer.items():
			segments_set = {}

			for node in selection:
				node_segment = node.getSegmentNodes()
				if len(node_segment) == 4:
					unique_key = hash(tuple([node.index for node in node_segment]))
					segments_set[unique_key] = node_segment

			if len(segments_set.keys()) >= 2:
				# In FL, layer == master name for masters.
				snap_to = None
				if snap_lookup:
					v = snap_lookup.get(layer)
					if v is not None:
						snap_to = [float(v)]

				data = list(segments_set.values())
				# - Set curves
				curve_A = eCurveEx(data[0])
				curve_B = eCurveEx(data[-1])
				new_curve_A, new_curve_B = curve_A.make_collinear(
					curve_B, mode=-1, equalize=equalize, target_width=None,
					snap_to=snap_to, snap_tolerance=snap_tolerance, apply=True)
				do_update = True
			else:
				output(1, 'Make collinear', 'Selection must be 2 curves = 8 Nodes! Current = {}'.format(len(selection)))

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tMake collinear @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def make_monoline(glyph:eGlyph, pLayers:tuple, preserve_taper:bool=False,
	                  snap_lookup:dict=None, snap_tolerance:float=0.25):
		'''Make two curves monoline (parallel offsets of a shared median skeleton).

		snap_lookup: optional {master_name: preset_width} dict. When set, the
		per-layer width snaps to the master's preset within
		snap_tolerance * measured.
		'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()

		selection_per_layer = {layer:glyph.selectedNodes(layer, extend=eNode) for layer in wLayers}
		do_update = False

		# - Process
		for layer, selection in selection_per_layer.items():
			segments_set = {}

			for node in selection:
				node_segment = node.getSegmentNodes()
				if len(node_segment) == 4:
					unique_key = hash(tuple([node.index for node in node_segment]))
					segments_set[unique_key] = node_segment

			if len(segments_set.keys()) >= 2:
				snap_to = None
				if snap_lookup:
					v = snap_lookup.get(layer)
					if v is not None:
						snap_to = [float(v)]

				data = list(segments_set.values())
				curve_A = eCurveEx(data[0])
				curve_B = eCurveEx(data[-1])
				new_curve_A, new_curve_B = curve_A.make_monoline(
					curve_B, target_width=None, preserve_taper=preserve_taper,
					snap_to=snap_to, snap_tolerance=snap_tolerance, apply=True)
				do_update = True
			else:
				output(1, 'Make monoline', 'Selection must be 2 curves = 8 Nodes! Current = {}'.format(len(selection)))

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tMake monoline @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def fake_stroke(glyph:eGlyph, pLayers:tuple, round_cap:bool=False, keep_cap_angle:bool=False):
		'''Rebuild a 'fake' stroke from its two selected side curves.

		Takes the same selection as make_collinear / make_monoline (two cubic
		side segments = 4 on + 4 off nodes), derives a simple median skeleton
		by control-point averaging, measures the two end cap widths from the
		side endpoints, re-expands a metapen circular-nib stroke along the
		median, and pastes the result as a new contour.

		This is a deliberately cheap approximation ('fake') — clean and
		minimal-node, not an exact reconstruction. Mid-path contrast is
		flattened; caps are perpendicular to the median.

		round_cap      : when True use a round cap, otherwise flat (butt).
		keep_cap_angle : when True keep the source's odd / slanted cap angles
		                 instead of cutting perpendicular (forces flat cap).
		'''

		# - Init
		wLayers = glyph._prepareLayers(pLayers)

		selection_per_layer = {layer:glyph.selectedNodes(layer, extend=eNode) for layer in wLayers}
		do_update = False

		# - Process
		for layer, selection in selection_per_layer.items():
			segments_set = {}

			for node in selection:
				node_segment = node.getSegmentNodes()
				if node_segment is not None and len(node_segment) == 4:
					unique_key = hash(tuple([node.index for node in node_segment]))
					segments_set[unique_key] = node_segment

			if len(segments_set.keys()) >= 2:
				data = list(segments_set.values())

				# - Two side segments as complex control-point tuples
				side_a = tuple(complex(n.x, n.y) for n in data[0])
				side_b = tuple(complex(n.x, n.y) for n in data[-1])

				result = fake_stroke_expand(
					side_a, side_b,
					cap=CAP_ROUND if round_cap else CAP_BUTT,
					keep_cap_angle=keep_cap_angle)

				# - Paste expanded outline as new contour(s)
				active_shape = glyph.shapes(layer)[0]

				for tr_contour in result.to_contours():
					fl_nodes = [fl6.flNode(float(nd.x), float(nd.y), nodeType=nd.type)
					            for nd in tr_contour.nodes]
					new_contour = fl6.flContour(fl_nodes, closed=tr_contour.closed)
					active_shape.addContour(new_contour, True)

				do_update = True
			else:
				output(1, 'Fake stroke', 'Selection must be 2 curves = 8 Nodes! Current = {}'.format(len(selection)))

		if do_update:
			glyph.updateObject(glyph.fl, '{};\tFake stroke @ {}.'.format(glyph.name, '; '.join(wLayers)))
			active_workspace.getCanvas(True).refreshAll()