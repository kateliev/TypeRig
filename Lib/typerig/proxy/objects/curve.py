# MODULE: Typerig / Proxy / Curve (Objects)
# ----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import warnings

import fontlab as fl6
import PythonQt as pqt

from typerig.proxy.objects.base import *
from typerig.proxy.objects.node import *

from typerig.core.func.utils import isMultiInstance

# - Init -----------------------------------
__version__ = '0.3.7'

# - Classes ---------------------------------
class eCurveEx(object):
	'''Extended representation of flCurveEx, adding some advanced functionality

	Constructor:
		eCurveEx(flCurveEx, list[flNode])
		eCurveEx(list[flNode])
		eCurveEx(flContour, time (int))
		...
	'''
	def __init__(self, *argv):
		
		if isinstance(argv[0], fl6.CurveEx):
			self.fl = self.CurveEx = argv[0]
			self.nodes = argv[1]
		
		elif isinstance(argv[0], (list, tuple)) and isMultiInstance(argv[0], fl6.flNode):
			self.fl = None
			self.nodes = argv[0]

		elif isMultiInstance(argv, fl6.flNode):
			self.fl = None			
			self.nodes = argv
		
		if len(self.nodes) == 4:
			self.n0, self.n1, self.n2, self.n3 = [eNode(node) for node in self.nodes]
			if self.fl is None: self.fl = self.CurveEx = self.n0.getSegment()

			self.curve = Curve(self.CurveEx)
			self.line = Line(self.n0.asCoord(), self.n3.asCoord())
			self.isCurve = True

		elif len(self.nodes) == 2:
			self.n0, self.n1 = [eNode(node) for node in self.nodes]
			if self.fl is None: self.fl = self.CurveEx = self.n0.getSegment()
			self.curve = None
			self.line = Line(self.CurveEx)
			self.isCurve = False

		self.contour = self.n0.contour


	# - Basic functionality ----------------------------
	def __repr__(self):
		return '<{} Curve={}; Nodes={};>'.format(self.__class__.__name__, self.isCurve, self.nodes)

	def __riseCurveWaring(self):
		warnings.warn('WARN:\tA Curve method applied on Line!')
		return None

	def updateNodes(self):
		for node, newLoc in zip(self.nodes, self.curve.points):
			node.x, node.y = newLoc.tuple

	def updateCurve(self):
		if isCurve:	
			self.CurveEx = self.n0.getSegment()
			self.curve = Curve(self.CurveEx)

	# - Curve optimization ----------------------------
	def eqTunni(self, apply=True):
		if self.isCurve:
			self.curve = self.curve.solve_tunni()
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()			

	def eqProportionalHandles(self, proportion=.3, apply=True):
		if self.isCurve:	
			self.curve = self.curve.solve_proportional_handles(proportion)
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()

	def eqRatioHandles(self, ratio=.3, apply=True):
		if self.isCurve:	
			self.curve = self.curve.solve_handle_distance_from_base((ratio, ratio))
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()

	def	eqHobbySpline(self, curvature=(.9,.9), apply=True):
		if self.isCurve:
			self.curve = self.curve.solve_hobby(curvature)
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()
