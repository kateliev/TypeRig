# MODULE: Typerig / Proxy / Base (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2024	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.core.func.utils import isMultiInstance

from typerig.core.objects.point import Point as trPoint
from typerig.core.objects.line import Line, Vector
from typerig.core.objects.cubicbezier import CubicBezier

# - Init ----------------------------------------------------
__version__ = '0.26.6'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - FL Proxy model -------------------------------------------
class Coord(trPoint): # Dumb Name but avoids name collision with FL Point object
	def __init__(self, *argv):
		super(Coord, self).__init__(0., 0.)

		if isinstance(argv[0], self.__class__):
			self.x, self.y = argv[0].x, argv[0].y

		if isMultiInstance(argv, (float, int)) :
			self.x, self.y = argv[0], argv[1]
		
		if isMultiInstance(argv, fl6.flNode):
			self.x, self.y = argv[0].x, argv[0].y
						
		if isMultiInstance(argv, (pqt.QtCore.QPointF, pqt.QtCore.QPoint)):
			self.x, self.y = argv[0].x(), argv[0].y()
		
		if isMultiInstance(argv, (tuple, list)) :
			self.x, self.y = argv[0]
		
		self.parent = argv

	def __repr__(self):
		return '<Coord: {},{}>'.format(self.x, self.y)

	def asQPointF(self):
		return pqt.QtCore.QPointF(*self.tuple)

	def asQPoint(self):
		return pqt.QtCore.QPointF(*self.tuple)

class Line(Line):
	def __init__(self, *argv):
		super(Line, self).__init__((0., 0.), (0., 0.))

		if len(argv) == 4:
			self.p0 = Coord(argv[:2])
			self.p1 = Coord(argv[2:])

		if len(argv) == 2:
			if isMultiInstance(argv, Coord):
				self.p0, self.p1 = argv
			else:
				self.p0 = Coord(argv[0])
				self.p1 = Coord(argv[1])

		if len(argv) == 1:
			if isinstance(argv[0], fl6.CurveEx):
				self.p0 = Coord(argv[0].p0)
				self.p1 = Coord(argv[0].p1)			

			if isMultiInstance(argv[0], fl6.flNode):
				self.p0 = Coord(argv[0][0])
				self.p1 = Coord(argv[0][1])

		if isMultiInstance(argv, (pqt.QtCore.QLineF, pqt.QtCore.QLine)) and len(argv) == 1:
			self.p0 = Coord(argv[0].p1())
			self.p1 = Coord(argv[0].p2())

		self.parent = argv		

	def asQLineF(self):
		return pqt.QtCore.QLineF(*self.tuple)

	def asQPoint(self):
		return [pqt.QtCore.QPointF(*n) for n in self.tuple] 

	def asflNode(self):
		return [fl6.flNode(*self.p0.tuple, nodeType=1), fl6.flNode(*self.p1.tuple, nodeType=1)]

class Vector(Vector):
	def __init__(self, *argv):
		temp_line = Line(*argv)
		super(Vector, self).__init__(*temp_line.tuple)	

		self.parent = argv		

	def asQLineF(self):
		return pqt.QtCore.QLineF(*self.tuple)

	def asQPoint(self):
		return pqt.QtCore.QPointF(*self.tuple)

class Curve(CubicBezier):
	def __init__(self, *argv):
		points = []

		if len(argv) == 4:
			if isMultiInstance(argv, (Coord, fl6.flNode)):
				points = [(item.x, item.y) for item in argv]

			if isMultiInstance(argv, (tuple, list)):
				points = argv

		if len(argv) == 1:
			if isMultiInstance(argv[0], (Coord, fl6.flNode)):
				points = [(item.x, item.y) for item in argv[0]]

			if isMultiInstance(argv[0], (tuple, list)):
				points = argv[0]

			if isinstance(argv[0], fl6.CurveEx):
				points = [(argv[0].p0.x(), argv[0].p0.y()), 
						(argv[0].bcp0.x(), argv[0].bcp0.y()),
						(argv[0].bcp1.x(), argv[0].bcp1.y()),
						(argv[0].p1.x(), argv[0].p1.y())]

		super(Curve, self).__init__(points)
		self.parent = argv

	def asflNode(self):
		return [fl6.flNode(*self.p0.tuple, nodeType=1), fl6.flNode(*self.p1.tuple, nodeType=4), fl6.flNode(*self.p2.tuple, nodeType=4), fl6.flNode(*self.p3.tuple, nodeType=1)]