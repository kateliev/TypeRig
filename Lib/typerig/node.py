# MODULE: Fontlab 6 Custom Node Objects | Typerig
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.15.3'

# - Dependencies -------------------------
import fontlab as fl6
#import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pNode, pContour, pNodesContainer

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

	def getNextLine(self):
		from typerig.brain import Line
		return Line(self.fl, self.getNextOn())

	def getPrevLine(self):
		from typerig.brain import Line
		return Line(self.getPrevOn(), self.fl)

	def diffTo(self, node):
		cPos = self.fl.position
		nPos = node.fl.position if isinstance(node, self.__class__) else node.position
		
		xdiff = nPos.x() - float(cPos.x())
		ydiff = nPos.y() - float(cPos.y())
		return xdiff, ydiff

	def diffToNext(self):
		return self.diffTo(self.getNext())

	def diffToPrev(self):
		return self.diffTo(self.getPrev())

	def shiftFromNext(self, diffX, diffY):
		newX = self.getNext().x + diffX
		newY = self.getNext().y + diffY
		self.reloc(newX, newY)	

	def shiftFromPrev(self, diffX, diffY):
		newX = self.getPrev().x + diffX
		newY = self.getPrev().y + diffY
		self.reloc(newX, newY)		

	def polarTo(self, node):
		return self.angleTo(node), self.distanceTo(node)

	def polarToNext(self):
		return self.angleToNext(), self.distanceToNext()

	def polarToPrev(self):
		return self.angleToPrev(), self.distanceToPrev()

	def polarReloc(self, angle, distance):
		from math import sin, cos
		newX = distance * cos(angle) + self.x
		newY = distance * sin(angle) + self.y
		self.reloc(newX, newY)

	def smartPolarReloc(self, angle, distance):
		from math import sin, cos
		newX = distance * cos(angle) + self.x
		newY = distance * sin(angle) + self.y
		self.smartReloc(newX, newY)

	def polarRelocFromPrev(self, distance):
		from math import sin, cos
		newX = distance * cos(angle + pi/2*[-1,1][self.contour.clockwise]) + self.getPrev().x
		newY = distance * sin(angle + pi/2*[-1,1][self.contour.clockwise]) + self.getPrev().y

		self.reloc(newX, newY)

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

	def cornerRound(self, size=5, curvature=(.9,.9), isRadius=False):
		from typerig.brain import Coord
		from typerig.curve import eCurveEx

		# - Calculate unit vectors and shifts
		nextNode = self.getNextOn(False)
		prevNode = self.getPrevOn(False)

		nextUnit = Coord(nextNode.asCoord() - self.asCoord()).getUnit()
		prevUnit = Coord(prevNode.asCoord() - self.asCoord()).getUnit()
		
		if not isRadius:
			from math import atan2, sin
			angle = atan2(nextUnit | prevUnit, nextUnit & prevUnit)
			radius = abs((float(size)/2)/sin(angle/2))
		else:
			radius = size

		nextShift = nextUnit * radius
		prevShift = prevUnit * radius

		# - Insert Nodes and process
		nextNode = self.__class__(self.insertAfter(.01)) # Was 0?, something went wrong in 6871
		nextNode.smartReloc(self.x, self.y) # Go back because something went wrong in 6871

		self.smartShift(*prevShift.asTuple())
		nextNode.smartShift(*nextShift.asTuple())
		
		# -- Make round corner
		nextNode.fl.convertToCurve(True)
		segment = self.getSegmentNodes()
		curve = eCurveEx(segment)
		curve.eqHobbySpline(curvature)

		return segment

	def cornerTrap(self, aperture=10, depth=20, trap=2):
		'''Trap a corner by given aperture.

		Arguments:
			aperture (float): Width of the traps mouth (opening);
			depth (float): Length of the traps sides;
			trap (float): Width of the traps bottom.

		Returns:
			tuple(flNode, flNode, flNode, flNode)
		'''

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

	def cornerTrapInc(self, incision=10, depth=50, trap=2, smooth=True):
		'''Trap a corner by given incision into the glyph flesh.
		
		Arguments:
			incision (float): How much to cut into glyphs flesh based from that corner inward;
			depth (float): Length of the traps sides;
			trap (float): Width of the traps bottom;
			smooth (bool): Creates a smooth trap.

		Returns:
			tuple(flNode, flNode, flNode, flNode) four base (ON) nodes of the trap.
		'''

		from typerig.brain import Coord, Line
		from math import atan2, sin, cos, radians

		# - Init
		remains = depth - incision
		base_coord = self.asCoord()

		# - Calculate for aperture postision and structure
		nextNode = self.getNextOn(False)
		prevNode = self.getPrevOn(False)

		nextUnit = Coord(nextNode.asCoord() - self.asCoord()).getUnit()
		prevUnit = Coord(prevNode.asCoord() - self.asCoord()).getUnit()

		angle = atan2(nextUnit | prevUnit, nextUnit & prevUnit)
		aperture = abs(2*(remains/sin(radians(90) - angle/2)*sin(angle/2)))
		adjust = float(aperture - trap)/2
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

		# - Make smooth trap transition
		if smooth: 
			# -- Convert nodes and extend bpc-s
			b.fl.convertToCurve()
			d.fl.convertToCurve()

			# -- Set nodes as smooth
			self.fl.smooth = True
			d.fl.smooth = True

			# -- Align bpc-s to the virtual lines connection sides of the trap with the original base node
			side_ab = Line(self.asCoord(), base_coord)
			side_cd = Line(base_coord, d.asCoord())
			control = (True, False)
			
			bpc_a, bpc_c = self.getNext(False), c.getNext(False)
			bpc_b, bpc_d = b.getPrev(False), d.getPrev(False)

			bpc_a.alignTo(side_ab, control)
			bpc_b.alignTo(side_ab, control)
			bpc_c.alignTo(side_cd, control)
			bpc_d.alignTo(side_cd, control)
			
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


class eNodesContainer(pNodesContainer):
	'''Extended representation of Abstract nodes container

	Constructor:
		eNodesContainer(list(flNode))
			
	'''
	def alignTo(self, entity, alignMode='', align=(True,True)):
		'''Align Abstract nodes container to.
		Arguments:
			entity ()
			alignMode (String) : L(left), R(right), C(center), T(top), B(bottom), E(vertical center) !ORDER MATTERS
		'''
		from typerig.proxy import pNode
		from typerig.node import eNode
		from PythonQt.QtCore import QPointF
		from typerig.brain import Coord
		
		# - Helper
		def getAlignDict(item):
			align_dict = {	'L': item.x(), 
							'R': item.x() + item.width(), 
							'C': item.x() + item.width()/2,
							'B': item.y(), 
							'T': item.y() + item.height(), 
							'E': item.y() + item.height()/2
						}

			return align_dict

		# - Init
		if len(alignMode)==2:
			alignX, alignY = alignMode.upper()

			# -- Get target for alignment
			if any([isinstance(entity, item) for item in [fl6.flNode, pNode, eNode, Coord, QPointF]]):
				target = Coord(entity.x, entity.y)

			elif any([isinstance(entity, item) for item in [fl6.flContour, pContour, self.__class__]]):
				
				if isinstance(entity, fl6.flContour):
					temp_entity = self.__class__(fl6.flContour.nodes())
				else:
					temp_entity = entity

				align_dict = getAlignDict(temp_entity)
				target = Coord(align_dict[alignX], align_dict[alignY])

			# -- Get source for alignment
			align_dict = getAlignDict(self)
			source =  Coord(align_dict[alignX], align_dict[alignY])

			# - Process
			shift = source - target
			shift_dx = abs(shift.x)*[1,-1][source.x > target.x] if align[0] else 0.
			shift_dy = abs(shift.y)*[1,-1][source.y > target.y] if align[1] else 0.
			
			self.shift(shift_dx, shift_dy)

		else:
			print 'ERROR:\t Invalid Align Mode: %s' %alignMode