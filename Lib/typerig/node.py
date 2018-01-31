# MODULE: Fontlab 6 Custom Node Objects | Typerig
# VER 	: 0.02
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

from typerig.proxy import pNode

class eNode(pNode):
	'''Extended representation of the Proxy Node, adding some advanced functionality

	Constructor:
		pNode(flNode)
		
	'''
	# - Movement ------------------------
	def interpMove(self, shift_x, shift_y):
		if self.isOn:
			from typerig.brain import Coord, Curve

			# - Init 
			shift = Coord(shift_x, shift_y)
			currSegmet, prevSegment = self.getSegment(), self.getSegment(-1)
			
			if len(currSegmet) == 4:
				currCurve = Curve(currSegmet)
				new_currCurve = currCurve.interpolateFirst(shift)

				currNode_bcpOut = self.fl.getNext()
				nextNode_bcpIn = currNode_bcpOut.getNext()
				nextNode = nextNode_bcpIn.getOn()

				currSegmetNodes = [self.fl, currNode_bcpOut, nextNode_bcpIn, nextNode]
				
				for i in range(len(currSegmetNodes)):
					currSegmetNodes[i].smartSetXY(new_currCurve.asList()[i].asQPointF())

			if len(prevSegment) == 4:
				prevCurve = Curve(prevSegment)
				new_prevCurve = prevCurve.interpolateLast(shift)

				currNode_bcpIn = self.fl.getPrev()
				prevNode_bcpOut = currNode_bcpIn.getPrev()
				prevNode = prevNode_bcpOut.getOn()

				prevSegmentNodes = [prevNode, prevNode_bcpOut, currNode_bcpIn, self.fl]
				
				for i in range(len(currSegmetNodes)):
					prevSegmentNodes[i].smartSetXY(new_prevCurve.asList()[i].asQPointF())