# MODULE: Typerig / Proxy / FontLab / Actions / Draw
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2023 	(http://www.kateliev.com)
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

from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.objects.contour import pContour
from typerig.proxy.fl.objects.curve import eCurveEx
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.base import Coord, Line, Vector, Curve

from typerig.core.func.math import three_point_circle, two_point_circle, two_point_square, two_mid_square
from typerig.core.objects.contour import HobbySpline
from typerig.core.objects.node import Knot
from typerig.core.base.message import *

from PythonQt import QtCore, QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init ----------------------------------------------------------------------------
__version__ = '1.18'
active_workspace = pWorkspace()

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Functions ------------------------------------------------------------------------
def make_contour_circle(center:tuple, radius:float):
	x, y = center
	new_spline = HobbySpline([Knot(x, y - radius), Knot(x + radius, y), Knot(x, y + radius), Knot(x - radius, y)], closed=True)
	new_contour = fl6.flContour([fl6.flNode(n.x, n.y, nodeType=n.type) for n in new_spline.nodes], closed=True)
	new_contour.removeOne(new_contour.nodes()[-1])
	return new_contour

def make_contour_circle_from_points(node_list:list, mode:int=1):
	if len(node_list) == 2 or mode == 0: # Two point circle (diameter)
		c, r = two_point_circle(node_list[0].tuple, node_list[1].tuple)
	
	if len(node_list) >= 3 and mode > 0: # Three point circle
		c, r = three_point_circle(node_list[0].tuple, node_list[1].tuple, node_list[2].tuple)
	
	return make_contour_circle(c, r), c, r

def make_contour_square_from_points(node_list:list, mode:int=0):
	if len(node_list) >= 2:
		if mode == 0: # From two nodes forming the square's diagonal
			square_points = two_point_square(node_list[0].tuple, node_list[1].tuple)	
		elif mode == 1:  # From midpoints of two adjacent sides
			square_points = two_mid_square(node_list[0].tuple, node_list[1].tuple)

		new_contour = fl6.flContour([fl6.flNode(n[0], n[1]) for n in square_points], closed=True)
		return new_contour

# - Actions ---------------------------------------------------------------------------
class TRDrawActionCollector(object):
	''' Collection of all drawing related tools '''

	# -- Primitive drawing tools ------------------------------------------------------
	@staticmethod
	def draw_circle_from_selection(pMode:int, pLayers:tuple, mode:int=1, rotated=False):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			# - Draw
			for layer_name in wLayers:
				node_selection = glyph.selectedNodes(layer_name, filterOn=True, extend=eNode)

				if len(node_selection) >= 2:
					new_circle, center, radius = make_contour_circle_from_points(node_selection, mode)
					
					# - Rotate circle so that it matches the angle of the imaginary line between the nodes selected
					if rotated:
						new_line = Line(node_selection[0].tuple, node_selection[-1].tuple)
						
						origin_transform = QtGui.QTransform()
						origin_transform = origin_transform.translate(-center[0], -center[1])
						new_circle.transform = origin_transform
						new_circle.applyTransform()

						temp_transform = QtGui.QTransform()
						temp_transform = temp_transform.rotate(new_line.angle)
						new_circle.transform = temp_transform
						new_circle.applyTransform()
						
						return_transform = QtGui.QTransform()
						return_transform = return_transform.translate(center[0], center[1])
						new_circle.transform = return_transform
						new_circle.applyTransform()

					# - Add contour to shape
					active_shape = glyph.shapes(layer_name)[0]
					active_shape.addContour(new_circle, True)
				
				else:
					break

			glyph.updateObject(glyph.fl, 'Glyph: {}; Created circle on: {}'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def draw_square_from_selection(pMode:int, pLayers:tuple, mode:int=0):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			# - Draw
			for layer_name in wLayers:
				node_selection = glyph.selectedNodes(layer_name, filterOn=True, extend=eNode)

				if len(node_selection) >= 2:
					new_square = make_contour_square_from_points(node_selection, mode)
					active_shape = glyph.shapes(layer_name)[0]
					active_shape.addContour(new_square, True)
				
				else:
					break

			glyph.updateObject(glyph.fl, 'Glyph: {}; Created square on: {}'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	# -- Trace and outline tools --------------------------------------------------------
	@staticmethod
	def nodes_collect(pMode:int, pLayers:tuple):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)
		nodes_bank = {}

		# - Process
		for glyph in process_glyphs:	
			# - Init		
			wLayers = glyph._prepareLayers(pLayers)

			for layer_name in wLayers:
				node_selection = glyph.selectedNodes(layer_name)
				nodes_bank.setdefault(layer_name, []).extend(node_selection)

		return nodes_bank

	@staticmethod
	def nodes_trace(pMode:int, pLayers:tuple, nodes_bank:dict, mode:int=0):
		'''Where mode:
			0 = Keep nodes as they are
			1 = Draw lines only
			2 = Draw hobby splines
		'''

		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			# - Init		
			if not len(nodes_bank.keys()):
				nodes_bank = {layer_name : glyph.selectedNodes(layer_name) for layer_name in wLayers}

			for layer_name, layer_nodes	in nodes_bank.items():
				new_contour = fl6.flContour()
				
				if mode == 0: #
					new_nodes_list = [fl6.flNode(node.position, nodeType=node.type) for node in layer_nodes]
				if mode == 1:
					new_nodes_list = [fl6.flNode(node.position, nodeType=node.type) for node in layer_nodes if node.isOn()]
				if mode == 2:
					new_spline = HobbySpline([Knot(node.x, node.y) for node in layer_nodes if node.isOn()], closed=True)
					new_nodes_list =[fl6.flNode(n.x, n.y, nodeType=n.type) for n in new_spline.nodes]

				new_contour.append(new_nodes_list)
				new_contour.closed = True
				glyph.shapes(layer_name)[0].addContour(new_contour, True)

			glyph.updateObject(glyph.fl, 'Glyph: {}; Trace Nodes:\t Layers:\t {}'.format(glyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	