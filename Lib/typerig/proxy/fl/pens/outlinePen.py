#FLM: Refactor: Outline Pen
# MODULE: Typerig / Proxy / Pen / Outline Pen (Pen)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function, absolute_import
import math

from fontlab_private.fontTools.pens.basePen import BasePen

import fontlab as fl6
import fontgate as fgt

from typerig.core.func.math import roundFloat
from typerig.core.func.geometry import checkSmooth, checkInnerOuter
from typerig.core.objects.point import Point
from typerig.core.objects.line import Line
from typerig.core.objects.cubicbezier import CubicBezier

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph

# - Init ---------------------------------
__version__ = '0.1.9'

# - Classes ------------------------------
class altPoint(Point):
	def __init__(self, x, y=None):
		if y is None: x, y = x
		super(altPoint, self).__init__(x,y)
		self.complex_math = False

	def __eq__(self, p):  # if p == p
		if not isinstance(p, self.__class__):
			return False
		return roundFloat(self.x) == roundFloat(p.x) and roundFloat(self.y) == roundFloat(p.y)

	def __ne__(self, p):  # if p != p
		return not self.__eq__(p)

	def __getitem__(self, index):
		return self.tuple[index]
	
	@property
	def fgPoint(self):
		return fgt.fgPoint(self.x, self.y)

# - Pens --------------------------------------------
class OutlinePen(BasePen):
	'''
	OutlinePen (protocol)
	Adapted from: Frederik Berlaen's (Typemytype) outlinerRoboFontExtension
	Original Source: https://github.com/typemytype/outlinerRoboFontExtension

	Attribs:
	- offset (float): Outline offset
	- contrast (float): Outline Contrast
	- contrastAngle (float): Outline contrast angle
	- connection (string): Connection type - square; 
	- cap (string): Cap type - round
	- closeOpenPaths (bool): Close open paths
	- optimizeCurve (bool): Optimize curve (adds an extra point of every curve at .5 time)
	- filterDoubles (bool): Filter double nodes
	- miterLimit (float): Sets miter limit

	Returns:
	- getGlyphs(): innerGlyph, outerGlyph, originalGlyph,(fgGlyph)
	- getShapes(): 	innerShape, outerShape, originalShape (flShape)
	- getContours(): innerContour, outerContour, originalContour (flShape)

	'''

	# - Internals
	pointClass = altPoint
	magicCurve = 0.5522847498

	def __init__(self, **kwargs):
		super(OutlinePen, self).__init__(self)

		# -- Input parameters
		self.offset = 			abs(kwargs.get('offset', 10))
		self.contrast = 		abs(kwargs.get('contrast', 0))
		self.contrastAngle = 	kwargs.get('contrastAngle', 0)
		self.connection = 		kwargs.get('connection', 'square')
		self.cap = 				kwargs.get('cap', 'round')
		self.closeOpenPaths = 	kwargs.get('closeOpenPaths', True)
		self.optimizeCurve = 	kwargs.get('optimizeCurve', False)
		self.filterDoubles = 	kwargs.get('filterDoubles', True)
		self._inputmiterLimit = kwargs.get('miterLimit', None)
		
		# - Init
		if self._inputmiterLimit is None: self._inputmiterLimit = self.offset * 2
		self.miterLimit = abs(self._inputmiterLimit)
		self.connectionCallback = getattr(self, "connection%s" % (self.connection.title()))
		self.capCallback = getattr(self, "cap%s" % (self.cap.title()))
		self.shouldHandleMove = True

		# -- Glyphs
		self.originalGlyph = fgt.fgGlyph()
		self.originalPen = self.originalGlyph.getPen()

		self.outerGlyph = fgt.fgGlyph()
		self.outerPen = self.outerGlyph.getPen()
		self.outerCurrentPoint = None
		self.outerFirstPoint = None
		self.outerPrevPoint = None

		self.innerGlyph = fgt.fgGlyph()
		self.innerPen = self.innerGlyph.getPen()
		self.innerCurrentPoint = None
		self.innerFirstPoint = None
		self.innerPrevPoint = None

		# -- Points
		self.prevPoint = None
		self.firstPoint = None
		self.firstAngle = None
		self.prevAngle = None
		
	def _moveTo(self, pt):
		x, y = pt
		if self.offset == 0:
			self.outerPen.moveTo((x, y))
			self.innerPen.moveTo((x, y))
			return

		self.originalPen.moveTo((x, y))

		p = self.pointClass(x, y)
		self.prevPoint = p
		self.firstPoint = p
		self.shouldHandleMove = True

	def _lineTo(self, pt):
		x, y = pt
		if self.offset == 0:
			self.outerPen.lineTo((x, y))
			self.innerPen.lineTo((x, y))
			return

		self.originalPen.lineTo((x, y))

		currentPoint = self.pointClass(x, y)
		if currentPoint == self.prevPoint:
			return

		self.currentAngle = self.prevPoint.angle_to(currentPoint)
		thickness = self.getThickness(self.currentAngle)

		self.innerCurrentPoint = self.prevPoint - self.pointClass(math.cos(self.currentAngle), math.sin(self.currentAngle)) * thickness
		self.outerCurrentPoint = self.prevPoint + self.pointClass(math.cos(self.currentAngle), math.sin(self.currentAngle)) * thickness

		if self.shouldHandleMove:
			self.shouldHandleMove = False

			self.innerPen.moveTo(self.innerCurrentPoint.fgPoint)
			self.innerFirstPoint = self.innerCurrentPoint

			self.outerPen.moveTo(self.outerCurrentPoint.fgPoint)
			self.outerFirstPoint = self.outerCurrentPoint

			self.firstAngle = self.currentAngle
		else:
			self.buildConnection()

		self.innerCurrentPoint = currentPoint - self.pointClass(math.cos(self.currentAngle), math.sin(self.currentAngle)) * thickness
		self.innerPen.lineTo(self.innerCurrentPoint.fgPoint)
		self.innerPrevPoint = self.innerCurrentPoint

		self.outerCurrentPoint = currentPoint + self.pointClass(math.cos(self.currentAngle), math.sin(self.currentAngle)) * thickness
		self.outerPen.lineTo(self.outerCurrentPoint.fgPoint)
		self.outerPrevPoint = self.outerCurrentPoint

		self.prevPoint = currentPoint
		self.prevAngle = self.currentAngle

	def _curveToOne(self, pt1, pt2, pt3):
		if self.optimizeCurve:
			b0 = CubicBezier((self.prevPoint.x, self.prevPoint.y), (pt1.x, pt1.y), (pt2.x, pt2.y), (pt3.x, pt3.y))
			curves = [c.tuple for c in b0.solve_slice(.5)]
		else:
			curves = [(self.prevPoint, pt1, pt2, pt3)]
		
		for curve in curves:
			p1, h1, h2, p2 = curve
			self._processCurveToOne(h1, h2, p2)

	def _processCurveToOne(self, pt1, pt2, pt3):
		if self.offset == 0:
			self.outerPen.curveTo(pt1, pt2, pt3)
			self.innerPen.curveTo(pt1, pt2, pt3)
			return
		self.originalPen.curveTo(pt1, pt2, pt3)

		p1 = self.pointClass(*pt1)
		p2 = self.pointClass(*pt2)
		p3 = self.pointClass(*pt3)

		if p1 == self.prevPoint:
			b0 = CubicBezier(self.prevPoint, p1, p2, p3)
			p1 = b0.solve_point(0.01)

		if p2 == p3:
			b1 = CubicBezier(self.prevPoint, p1, p2, p3)
			p2 = b1.solve_point(0.99)

		a1 = self.prevPoint.angle_to(p1)
		a2 = p2.angle_to(p3)

		self.currentAngle = a1
		tickness1 = self.getThickness(a1)
		tickness2 = self.getThickness(a2)

		a1bis = self.prevPoint.angle_to(p1, 0)
		a2bis = p3.angle_to(p2, 0)
		
		l00 = Line(self.prevPoint, self.prevPoint + self.pointClass(math.cos(a1), math.sin(a1)) * 100)
		l01 = Line(p3, p3 + self.pointClass(math.cos(a2), math.sin(a2)) * 100)
		intersectPoint = self.pointClass(l00.intersect_line(l01, True))

		self.innerCurrentPoint = self.prevPoint - self.pointClass(math.cos(a1), math.sin(a1)) * tickness1
		self.outerCurrentPoint = self.prevPoint + self.pointClass(math.cos(a1), math.sin(a1)) * tickness1

		if self.shouldHandleMove:
			self.shouldHandleMove = False

			self.innerPen.moveTo(self.innerCurrentPoint.fgPoint)
			self.innerFirstPoint = self.innerPrevPoint = self.innerCurrentPoint

			self.outerPen.moveTo(self.outerCurrentPoint.fgPoint)
			self.outerFirstPoint = self.outerPrevPoint = self.outerCurrentPoint

			self.firstAngle = a1
		else:
			self.buildConnection()

		h1 = None
		if intersectPoint is not None:
			l10 = Line(self.innerCurrentPoint, self.innerCurrentPoint + self.pointClass(math.cos(a1bis), math.sin(a1bis)) * tickness1)
			l11 = Line(intersectPoint, p1)
			h1 = self.pointClass(l10.intersect_line(l11, True))
		
		if h1 is None:
			h1 = p1 - self.pointClass(math.cos(a1), math.sin(a1)) * tickness1

		self.innerCurrentPoint = p3 - self.pointClass(math.cos(a2), math.sin(a2)) * tickness2

		h2 = None
		if intersectPoint is not None:
			l20 = Line(self.innerCurrentPoint, self.innerCurrentPoint + self.pointClass(math.cos(a2bis), math.sin(a2bis)) * tickness2)
			l21 = Line(intersectPoint, p2)
			h2 = self.pointClass(l20.intersect_line(l21, True))
		
		if h2 is None:
			h2 = p2 - self.pointClass(math.cos(a1), math.sin(a1)) * tickness1

		self.innerPen.curveTo(h1.fgPoint, h2.fgPoint, self.innerCurrentPoint.fgPoint)
		self.innerPrevPoint = self.innerCurrentPoint

		# ----------------------------
		h1 = None
		if intersectPoint is not None:
			l30 = Line(self.outerCurrentPoint, self.outerCurrentPoint + self.pointClass(math.cos(a1bis), math.sin(a1bis)) * tickness1)
			l31 = Line(intersectPoint, p1)
			h1 = self.pointClass(l30.intersect_line(l31, True))

		if h1 is None:
			h1 = p1 + self.pointClass(math.cos(a1), math.sin(a1)) * tickness1

		self.outerCurrentPoint = p3 + self.pointClass(math.cos(a2), math.sin(a2)) * tickness2

		h2 = None
		if intersectPoint is not None:
			l40 = Line(self.outerCurrentPoint, self.outerCurrentPoint + self.pointClass(math.cos(a2bis), math.sin(a2bis)) * tickness2)
			l41 = Line(intersectPoint, p2)
			h2 = self.pointClass(l40.intersect_line(l41, True))
		
		if h2 is None:
			h2 = p2 + self.pointClass(math.cos(a1), math.sin(a1)) * tickness1

		self.outerPen.curveTo(h1.fgPoint, h2.fgPoint, self.outerCurrentPoint.fgPoint)
		self.outerPrevPoint = self.outerCurrentPoint

		self.prevPoint = p3
		self.currentAngle = a2
		self.prevAngle = a2

	def _closePath(self):
		if self.shouldHandleMove:
			return
		if self.offset == 0:
			self.outerPen.closePath()
			self.innerPen.closePath()
			return

		if not self.prevPoint == self.firstPoint:
			self._lineTo(self.firstPoint)

		self.originalPen.closePath()

		self.innerPrevPoint = self.innerCurrentPoint
		self.innerCurrentPoint = self.innerFirstPoint

		self.outerPrevPoint = self.outerCurrentPoint
		self.outerCurrentPoint = self.outerFirstPoint

		self.prevAngle = self.currentAngle
		self.currentAngle = self.firstAngle

		self.buildConnection(close=True)

		self.innerPen.closePath()
		self.outerPen.closePath()

	def _endPath(self):
		if self.shouldHandleMove:
			return

		self.originalPen.endPath()
		self.innerPen.endPath()
		self.outerPen.endPath()

		if self.closeOpenPaths:
			innerContour = self.innerGlyph[-1]
			outerContour = self.outerGlyph[-1]

			innerContour.reverse()

			innerContour[0].segmentType = "line"
			outerContour[0].segmentType = "line"

			self.buildCap(outerContour, innerContour)

			for point in innerContour:
				outerContour.addPoint((point.x, point.y), segmentType=point.segmentType, smooth=point.smooth)

			self.innerGlyph.removeContour(innerContour)

	# -- Thickness
	def getThickness(self, angle):
		a2 = angle + math.pi * .5
		f = abs(math.sin(a2 + math.radians(self.contrastAngle)))
		f = f ** 5
		return self.offset + self.contrast * f

	# -- Connections --------------------------------
	def buildConnection(self, close=False):
		if not checkSmooth(self.prevAngle, self.currentAngle):
			if checkInnerOuter(self.prevAngle, self.currentAngle):
				self.connectionCallback(self.outerPrevPoint, self.outerCurrentPoint, self.outerPen, close)
				self.connectionInnerCorner(self.innerPrevPoint, self.innerCurrentPoint, self.innerPen, close)
			else:
				self.connectionCallback(self.innerPrevPoint, self.innerCurrentPoint, self.innerPen, close)
				self.connectionInnerCorner(self.outerPrevPoint, self.outerCurrentPoint, self.outerPen, close)
		
		elif not self.filterDoubles:
			self.innerPen.lineTo(self.innerCurrentPoint)
			self.outerPen.lineTo(self.outerCurrentPoint)

	def connectionSquare(self, first, last, pen, close):
		angle_1 = math.radians(math.degrees(self.prevAngle)+90)
		angle_2 = math.radians(math.degrees(self.currentAngle)+90)

		tempFirst = first - self.pointClass(math.cos(angle_1), math.sin(angle_1)) * self.miterLimit
		tempLast = last + self.pointClass(math.cos(angle_2), math.sin(angle_2)) * self.miterLimit

		l0 = Line(first, tempFirst)
		l1 = Line(last, tempLast)
		newPoint = self.pointClass(l0.intersect_line(l1,True))

		if newPoint is not None:

			if self._inputmiterLimit is not None and roundFloat(newPoint.diff_to(first)) > self._inputmiterLimit:
				pen.lineTo(tempFirst.fgPoint)
				pen.lineTo(tempLast.fgPoint)
			else:
				pen.lineTo(newPoint.fgPoint)

		if not close:
			pen.lineTo(last.fgPoint)

	def connectionRound(self, first, last, pen, close):
		angle_1 = math.radians(math.degrees(self.prevAngle)+90)
		angle_2 = math.radians(math.degrees(self.currentAngle)+90)

		tempFirst = first - self.pointClass(math.sin(angle_1), -math.cos(angle_1))
		tempLast = last + self.pointClass(math.sin(angle_2), -math.cos(angle_2))

		l0 = Line(first, tempFirst)
		l1 = Line(last, tempLast)

		centerPoint = self.pointClass(l0.intersect_line(l1, True))

		if centerPoint is None:
			# the lines are parallel, let's just take the middle
			centerPoint = (first + last) / 2

		angle_diff = (angle_1 - angle_2) % (2 * math.pi)
		if angle_diff > math.pi:
			angle_diff = 2 * math.pi - angle_diff
		angle_half = angle_diff / 2

		radius = centerPoint.diff_to(first)
		D = radius * (1 - math.cos(angle_half))
		handleLength = (4 * D / 3) / math.sin(angle_half)  # length of the bcp line

		bcp1 = first - self.pointClass(math.cos(angle_1), math.sin(angle_1)) * handleLength
		bcp2 = last + self.pointClass(math.cos(angle_2), math.sin(angle_2)) * handleLength
		pen.curveTo(bcp1.fgPoint, bcp2.fgPoint, last.fgPoint)

	def connectionButt(self, first, last, pen, close):
		if not close:
			pen.lineTo(last.fgPoint)

	def connectionInnerCorner(self, first, last, pen, close):
		if not close:
			pen.lineTo(last.fgPoint)

	# - Line Caps --------------------------------
	def buildCap(self, firstContour, lastContour):
		first = firstContour[-1]
		last = lastContour[0]
		first = self.pointClass(first.x, first.y)
		last = self.pointClass(last.x, last.y)

		self.capCallback(firstContour, lastContour, first, last, self.prevAngle)

		first = lastContour[-1]
		last = firstContour[0]
		first = self.pointClass(first.x, first.y)
		last = self.pointClass(last.x, last.y)

		angle = math.radians(math.degrees(self.firstAngle) + 180)
		self.capCallback(lastContour, firstContour, first, last, angle)

	def capButt(self, firstContour, lastContour, first, last, angle):
		# not nothing
		pass

	def capRound(self, firstContour, lastContour, first, last, angle):
		hookedAngle = math.radians(math.degrees(angle) + 90)

		p1 = first - self.pointClass(math.cos(hookedAngle), math.sin(hookedAngle)) * self.offset

		p2 = last - self.pointClass(math.cos(hookedAngle), math.sin(hookedAngle)) * self.offset

		oncurve = p1 + (p2 - p1) * .5

		roundness = self.magicCurve

		h1 = first - self.pointClass(math.cos(hookedAngle), math.sin(hookedAngle)) * self.offset * roundness
		h2 = oncurve + self.pointClass(math.cos(angle), math.sin(angle)) * self.offset * roundness

		firstContour[-1].smooth = True

		firstContour.addPoint((h1.x, h1.y))
		firstContour.addPoint((h2.x, h2.y))
		firstContour.addPoint((oncurve.x, oncurve.y), smooth=True, segmentType="curve")

		h1 = oncurve - self.pointClass(math.cos(angle), math.sin(angle)) * self.offset * roundness
		h2 = last - self.pointClass(math.cos(hookedAngle), math.sin(hookedAngle)) * self.offset * roundness

		firstContour.addPoint((h1.x, h1.y))
		firstContour.addPoint((h2.x, h2.y))

		lastContour[0].segmentType = "curve"
		lastContour[0].smooth = True

	def capSquare(self, firstContour, lastContour, first, last, angle):
		angle = math.radians(math.degrees(angle) + 90)

		firstContour[-1].smooth = True
		lastContour[0].smooth = True

		p1 = first - self.pointClass(math.cos(angle), math.sin(angle)) * self.offset
		firstContour.addPoint((p1.x, p1.y), smooth=False, segmentType="line")

		p2 = last - self.pointClass(math.cos(angle), math.sin(angle)) * self.offset
		firstContour.addPoint((p2.x, p2.y), smooth=False, segmentType="line")

	# - Output -----------------------------------------------
	def getGlyphs(self):
		return self.innerGlyph, self.outerGlyph, self.originalGlyph

	def getShapes(self):
		fgGlyphs = self.getGlyphs()
		return [fl6.flShape(glyph.layer[0]) for glyph in fgGlyphs]

	def getContours(self):
		fgGlyphs = self.getGlyphs()
		return [fl6.flShape(glyph.layer[0]).getContours() for glyph in fgGlyphs]
