# MODULE: Fontlab 6 Custom Node Objects | Typerig
# VER 	: 0.05
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
		eNode(flNode)
		
	'''
	# - Extension -----------------------
	def asCoord(self):
		'''Returns Coord object of the node.'''
		from typerig.brain import Coord
		return Coord(float(self.x), float(self.y))

	# - Corner operations ---------------
	def cornerMitre(self, mitreRadius=(1,1)):
		from typerig.brain import Coord

		# - Calculate unit vectors and shifts
		nextNode = self.__class__(self.getNextOn())
		prevNode = self.__class__(self.getPrevOn())

		nextUnit = Coord(nextNode.asCoord() - self.asCoord()).getUnit()
		prevUnit = Coord(prevNode.asCoord() - self.asCoord()).getUnit()
		
		nextShift = nextUnit * mitreRadius
		prevShift = prevUnit * mitreRadius

		#print (nextUnit, prevUnit), (nextShift, prevShift)
		
		# - Insert Node and process
		self.insertAfter(0)
		self.contour.updateIndices()

		self.fl.smartMove(prevShift.asQPointF())
		self.getNextOn().smartMove(nextShift.asQPointF())

	# - Movement ------------------------
	def interpMove(self, shift_x, shift_y):
		'''Interpolated move aka Interpolated Nudge.
		
		Arguments:
			shift_x, shift_y (float)
		'''
		if self.isOn:
			from typerig.brain import Coord, Curve

			# - Init 
			shift = Coord(shift_x, shift_y)
			currSegmet, prevSegment = self.getSegment(), self.getSegment(-1)

			if prevSegment == None:
				prevSegment = self.contour.segments()[-1]
			
			# - Process segments
			if len(currSegmet) == 4:
				currCurve = Curve(currSegmet)
				new_currCurve = currCurve.interpolateFirst(shift)
				
				currNode_bcpOut = self.fl.getNext()
				nextNode_bcpIn = currNode_bcpOut.getNext()
				nextNode = nextNode_bcpIn.getOn()

				currSegmetNodes = [self.fl, currNode_bcpOut, nextNode_bcpIn, nextNode]
				
				# - Set node positions
				for i in range(len(currSegmetNodes)):
					currSegmetNodes[i].smartSetXY(new_currCurve.asList()[i].asQPointF())

			if len(prevSegment) == 4:
				prevCurve = Curve(prevSegment)
				new_prevCurve = prevCurve.interpolateLast(shift)

				currNode_bcpIn = self.fl.getPrev()
				prevNode_bcpOut = currNode_bcpIn.getPrev()
				prevNode = prevNode_bcpOut.getOn()

				prevSegmentNodes = [prevNode, prevNode_bcpOut, currNode_bcpIn, self.fl]
				
				# - Set node positions
				for i in range(len(prevSegmentNodes)-1,-1,-1):
					prevSegmentNodes[i].smartSetXY(new_prevCurve.asList()[i].asQPointF())

			if len(currSegmet) == 2 and len(prevSegment) == 2:
				self.fl.smartSetXY((Coord(self.fl) + shift).asQPointF())

	def slantMove(self, shift_x, shift_y, italic_angle):
		'''Slanted move - move a node (in inclined space) according to Y coordinate slanted at given angle.
		
		Arguments:
			shift_x, shift_y (float)
			italic_angle (float): Angle in degrees
		'''
		if self.isOn:
			from typerig.brain import Coord
			from PythonQt.QtCore import QPointF
			
			# - Init
			cNode = Coord((self.x + shift_x, self.y))
			cNode.setAngle(italic_angle)
			
			# - Calculate & set
			newX = cNode.getWidth(cNode.y + shift_y)
			self.fl.smartSetXY(QPointF(newX, self.y + shift_y))

	def alignTo(self, entity, align=(True, True)):
		'''Align current node to a node or line given.
		Arguments:
			entity (flNode, pNode, eNode or Line)
			align (tuple(Align_X (bool), Align_Y (bool)) 
		'''
		from typerig.proxy import pNode
		from typerig.brain import Line
		from PythonQt.QtCore import QPointF

		if any([isinstance(entity, item) for item in [fl6.flNode, pNode, self.__class__]]):
			newX = entity.x if align[0] else self.fl.x
			newY = entity.y if align[1] else self.fl.y
				
			self.fl.smartSetXY(QPointF(newX, newY))

		elif isinstance(entity, Line):
			newX = entity.solveX(self.fl.y) if align[0] else self.fl.x
			newY = entity.solveY(self.fl.x) if align[1] else self.fl.y

			self.fl.smartSetXY(QPointF(newX, newY))

