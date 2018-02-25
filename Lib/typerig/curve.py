# MODULE: Fontlab 6 Custom Curve Objects | Typerig
# VER 	: 0.01
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
		from typerig.brain	import Coord, Curve
		from typerig.node import eNode
		from fontlab import CurveEx, flNode, flContour
		
		multiCheck = lambda t, type: all([isinstance(i, type) for i in t])

		
		if isinstance(argv[0], CurveEx) and multiCheck(argv[1], flNode):
			self.fl = self.CurveEx = argv[0]
			self.nodes = argv[1]
			self.n0, self.n1, self.n2, self.n3 = [eNode(node) for node in self.nodes]
			self.contour = self.n0.contour

		elif (isinstance(argv[0], list) or isinstance(argv[0], tuple)) and multiCheck(argv[0], flNode):
			self.nodes = argv[0]
			self.n0, self.n1, self.n2, self.n3 = [eNode(node) for node in self.nodes]
			self.fl = self.CurveEx = self.n0.getSegment()
			self.contour = self.n0.contour

		elif isinstance(argv[0], flContour) and isinstance(argv[1], int):
			self.contour = argv[0]
			self.fl = self.CurveEx = self.contour.segment(argv[1])
			
			time = argv[1]
			onNodes = [node for node in self.contour.nodes() if node.isOn]
			
			currNode = onNodes[time]
			currNode_bcpOut = currNode.getNext()
			nextNode_bcpIn = currNode_bcpOut.getNext()
			nextNode = nextNode_bcpIn.getOn()

			self.nodes = [currNode, currNode_bcpOut, nextNode_bcpIn, nextNode]
			self.n0, self.n1, self.n2, self.n3 = [eNode(node) for node in self.nodes]


		self.curve = Curve(self.CurveEx)

	# - Basic functionality ----------------------------
	def __repr__(self):
		return '<%s Nodes=%s>' % (self.__class__.__name__, self.nodes)

	def updateNodes(self):
		for i in range(len(self.nodes)):
			self.nodes[i].smartSetXY(self.curve.asList()[i].asQPointF())

	def updateCurve(self):
		self.CurveEx = self.n0.getSegment()
		self.curve = Curve(self.CurveEx)

	# - Curve optimization ----------------------------
	def eqTunni(self, apply=True):
		self.curve = self.curve.eqTunni()
		if apply: self.updateNodes()
		return self.curve

	def eqProportionalHandles(self, proportion=.3, apply=True):
		self.curve = self.curve.eqProportionalHandles(proportion)
		if apply: self.updateNodes()
		return self.curve

	def	eqHobbySpline(self, curvature=(.9,.9), apply=True):
		self.curve = self.curve.eqHobbySpline(curvature)
		if apply: self.updateNodes()
		return self.curve
