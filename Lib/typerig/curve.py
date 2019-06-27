# MODULE: Fontlab 6 Custom Curve Objects | Typerig
# VER 	: 0.03
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import fontlab as fl6
#import fontgate as fgt
import PythonQt as pqt

#from typerig.proxy import pNode

class eCurveEx(object):
	'''Extended representation of flCurveEx, adding some advanced functionality

	Constructor:
		eCurveEx(flCurveEx, list[flNode])
		eCurveEx(list[flNode])
		eCurveEx(flContour, time (int))
		...
	'''
	def __init__(self, *argv):
		from typerig.brain	import Coord, Curve, Line
		from typerig.node import eNode
		from fontlab import CurveEx, flNode, flContour
		
		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])

		if isinstance(argv[0], CurveEx) and multiCheck(argv[1], flNode):
			self.fl = self.CurveEx = argv[0]
			self.nodes = argv[1]
			
		elif (isinstance(argv[0], list) or isinstance(argv[0], tuple)) and multiCheck(argv[0], flNode):
			self.nodes = argv[0]
			self.fl = None
				
		
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
		return '<%s Curve=%s; Nodes=%s;>' % (self.__class__.__name__, self.isCurve, self.nodes)

	def __riseCurveWaring(self):
		import warnings
		warnings.warn('WARN:\tA Curve method applied on Line!')
		return None

	def updateNodes(self):
		for node, newLoc in zip(self.nodes, self.curve.asList()):
			node.x, node.y = newLoc.asTuple()

	def updateCurve(self):
		if isCurve:	
			self.CurveEx = self.n0.getSegment()
			self.curve = Curve(self.CurveEx)

	# - Curve optimization ----------------------------
	def eqTunni(self, apply=True):
		if self.isCurve:
			self.curve = self.curve.eqTunni()
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()			

	def eqProportionalHandles(self, proportion=.3, apply=True):
		if self.isCurve:	
			self.curve = self.curve.eqProportionalHandles(proportion)
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()

	def	eqHobbySpline(self, curvature=(.9,.9), apply=True):
		if self.isCurve:
			self.curve = self.curve.eqHobbySpline(curvature)
			if apply: self.updateNodes()
			return self.curve
		else:
			return self.__riseCurveWaring()
