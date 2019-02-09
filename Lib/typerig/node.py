# MODULE: Fontlab 6 Custom Node Objects | Typerig
# VER 	: 0.11
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
	def cornerMitre(self, mitreSize=5, isRadius=False):
		from typerig.brain import Coord

		# - Calculate unit vectors and shifts
		nextNode = self.getNextOn(False)
		prevNode = self.getPrevOn(False)

		nextUnit = Coord(nextNode.asCoord() - self.asCoord()).getUnit()
		prevUnit = Coord(prevNode.asCoord() - self.asCoord()).getUnit()
		
		if not isRadius:
			from math import atan2, sin
			angle = atan2(nextUnit | prevUnit, nextUnit & prevUnit)
			radius = abs((float(mitreSize)/2)/sin(angle/2))
		else:
			radius = mitreSize

		nextShift = nextUnit * radius
		prevShift = prevUnit * radius

		# - Insert Node and process
		nextNode = self.__class__(self.insertAfter(.01)) # Was 0?, something went wrong in 6871
		nextNode.smartReloc(self.x, self.y) # Go back because something went wrong in 6871

		self.smartShift(*prevShift.asTuple())
		nextNode.smartShift(*nextShift.asTuple())

		return (self.fl, nextNode.fl)

	def cornerTrap(self, aperture=10, depth=20, trap=2):
		from typerig.brain import Coord
		from math import atan2, sin, cos

		# - Init
		adjust = float(aperture - trap)/2

		# - Calculate for aperture postision and structure
		nextNode = self.getNextOn(False)
		prevNode = self.getPrevOn(False)

		nextUnit = Coord(nextNode.asCoord() - self.asCoord()).getUnit()
		prevUnit = Coord(prevNode.asCoord() - self.asCoord()).getUnit()

		angle = atan2(nextUnit | prevUnit, nextUnit & prevUnit)
		radius = abs((float(aperture)/2)/sin(angle/2))
		
		bCoord = self.asCoord() + (nextUnit * -radius)
		cCoord = self.asCoord() + (prevUnit * -radius)

		aCoord = self.asCoord() + (prevUnit * radius)
		dCoord = self.asCoord() + (nextUnit * radius)

		# - Calculate for depth
		abUnit = Coord(aCoord - bCoord).getUnit()
		dcUnit = Coord(dCoord - cCoord).getUnit()

		bCoord = aCoord + abUnit*-depth
		cCoord = dCoord + dcUnit*-depth

		# - Calculate for trap (size)
		bcUnit = (bCoord - cCoord).getUnit()
		cbUnit = (cCoord - bCoord).getUnit()

		bCoord += bcUnit*-adjust
		cCoord += cbUnit*-adjust

		# - Insert Nodes and cleanup
		b = self.__class__(self.insertAfter(0.01)) # .01 quickfix - should be 0
		c = self.__class__(b.insertAfter(0.01))
		d = self.__class__(c.insertAfter(0.01))

		b.fl.convertToLine()
		c.fl.convertToLine()
		d.fl.convertToLine()

		# - Position nodes
		self.smartReloc(*aCoord.asTuple())
		b.smartReloc(*bCoord.asTuple())
		d.smartReloc(*dCoord.asTuple())
		c.smartReloc(*cCoord.asTuple())

		return (self.fl, b.fl, c.fl, d.fl)

	# - Movement ------------------------
	def interpShift(self, shift_x, shift_y):
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
				
				currNode_bcpOut = self.getNext(False)
				nextNode_bcpIn = currNode_bcpOut.getNext(False)
				nextNode = nextNode_bcpIn.getOn(False)

				currSegmetNodes = [self, currNode_bcpOut, nextNode_bcpIn, nextNode]
				
				# - Set node positions
				for i in range(len(currSegmetNodes)):
					currSegmetNodes[i].smartReloc(*new_currCurve.asList()[i].asTuple())

			if len(prevSegment) == 4:
				prevCurve = Curve(prevSegment)
				new_prevCurve = prevCurve.interpolateLast(shift)

				currNode_bcpIn = self.getPrev(False)
				prevNode_bcpOut = currNode_bcpIn.getPrev(False)
				prevNode = prevNode_bcpOut.getOn(False)

				prevSegmentNodes = [prevNode, prevNode_bcpOut, currNode_bcpIn, self]
				
				# - Set node positions
				for i in range(len(prevSegmentNodes)-1,-1,-1):
					prevSegmentNodes[i].smartReloc(*new_prevCurve.asList()[i].asTuple())

			if len(currSegmet) == 2 and len(prevSegment) == 2:
				self.smartShift(*shift.asTuple())

	def slantShift(self, shift_x, shift_y, angle):
		'''Slanted move - move a node (in inclined space) according to Y coordinate slanted at given angle.
		
		Arguments:
			shift_x, shift_y (float)
			angle (float): Angle in degrees
		'''
		from typerig.brain import Coord
		from PythonQt.QtCore import QPointF
		
		# - Init
		cNode = Coord((self.x + shift_x, self.y))
		cNode.setAngle(angle)
		
		# - Calculate & set
		newX = cNode.getWidth(cNode.y + shift_y)
		#self.fl.smartSetXY(QPointF(newX, self.y + shift_y))
		self.smartReloc(newX, self.y + shift_y)

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
				
			#self.fl.smartSetXY(QPointF(newX, newY))
			self.smartReloc(newX, newY)

		elif isinstance(entity, Line):
			newX = entity.solveX(self.fl.y) if align[0] else self.fl.x
			newY = entity.solveY(self.fl.x) if align[1] else self.fl.y

			#self.fl.smartSetXY(QPointF(newX, newY))
			self.smartReloc(newX, newY)

