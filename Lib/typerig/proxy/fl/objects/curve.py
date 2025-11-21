# MODULE: Typerig / Proxy / Curve (Objects)
# ----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2024	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import warnings

import fontlab as fl6
import PythonQt as pqt

from typerig.proxy.fl.objects.base import *
from typerig.proxy.fl.objects.node import eNode

from typerig.core.func.utils import isMultiInstance

# - Init -----------------------------------
__version__ = '0.3.95'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

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
		self.nodes = []
		
		if isinstance(argv[0], fl6.CurveEx):
			self.fl = self.CurveEx = argv[0]
			# WRONG!!!! 
			self.nodes = [eNode(self.fl.p0), eNode(self.fl.bcp0), eNode(self.fl.bcp1), eNode(self.fl.p1)]
		
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
		ratio = proportion if isinstance(proportion, tuple) else (proportion, proportion)

		if self.isCurve:	
			self.curve = self.curve.solve_proportional_handles(ratio)
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

	def make_collinear(self, other, mode=0, equalize=False, target_width=None, apply=True):
		if self.isCurve and other.isCurve:
			self.curve, other.curve = self.curve.make_collinear(other.curve, mode, equalize, target_width)
			if apply: 
				self.updateNodes()
				other.updateNodes()
			return self.curve, other.curve
		else:
			return self.__riseCurveWaring()

