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

from typerig.core.func.math import three_point_circle, two_point_circle
from typerig.core.objects.contour import HobbySpline
from typerig.core.base.message import *

from PythonQt import QtCore, QtGui
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

import typerig.proxy.fl.gui.dialogs as TRDialogs

# - Init ----------------------------------------------------------------------------
__version__ = '1.10'
active_workspace = pWorkspace()

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Functions ------------------------------------------------------------------------
def make_contour_circle(center, radius):
	x, y = center
	new_spline = HobbySpline([Knot(x, y - radius), Knot(x + radius, y), Knot(x, y + radius), Knot(x - radius, y)], closed=True)
	new_contour = fl6.flContour([fl6.flNode(n.x, n.y, nodeType=n.type) for n in new_spline.nodes], closed=True)
	return new_contour

def make_contour_circle_from_points(node_list):
	if len(node_list) == 2:
		c, r = two_point_circle(node_list[0].tuple, node_list[1].tuple)
	
	if len(node_list) >= 3:
		c, r = three_point_circle(node_list[0].tuple, node_list[1].tuple, node_list[2].tuple)
	
	return make_contour_circle(c, r)

# - Actions ---------------------------------------------------------------------------
class TRDrawActionCollector(object):
	''' Collection of all drawing related tools '''

	# -- Primitive drawing tools ------------------------------------------------------
	@staticmethod
	def draw_circle_from_selection(pMode:int, pLayers:tuple):
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
					new_circle = make_contour_circle_from_points(node_selection)
					active_shape = glyph.shapes(layer_name)[0]
					active_shape.addContour(new_circle, True)
				
				else:
					break

			glyph.updateObject(glyph.fl, 'Glyph: {}; Created circle on: {}'.format(glyph.name, '; '.join(wLayers)))
		
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
			wLayers = wGlyph._prepareLayers(pLayers)

			for layer_name in wLayers:
				node_selection = wGlyph.selectedNodes(layer_name)
				nodes_bank.setdefault(layer_name, []).extend(node_selection)

		return nodes_bank

	@staticmethod
	def nodes_trace(pMode:int, pLayers:tuple, nodes_bank:dict):
		# - Get list of glyphs to be processed
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			# - Init		
			if not len(nodes_bank):
				nodes_bank = {layer_name : wGlyph.selectedNodes(layer_name) for layer_name in wLayers}

			for layer_name, layer_nodes	in nodes_bank.items():
				new_contour = fl6.flContour()
				new_contour.append([fl6.flNode(node.position, nodeType=node.type) for node in layer_nodes])
				new_contour.closed = True
				wGlyph.shapes(layer_name)[0].addContour(new_contour, True)

			wGlyph.updateObject(wGlyph.fl, 'Glyph: {}; Trace Nodes:\t Layers:\t {}'.format(wGlyph.name, '; '.join(wLayers)))
		
		active_workspace.getCanvas(True).refreshAll()

	