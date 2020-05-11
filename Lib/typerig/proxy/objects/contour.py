# MODULE: Typerig / Proxy / Contour (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import math 

import fontlab as fl6
import PythonQt as pqt

from typerig.proxy.objects.base import Coord
from typerig.proxy.objects.node import pNode

# - Init --------------------------------
__version__ = '0.26.1'

# - Classes -----------------------------
class pContour(object):
	'''Proxy to flContour object

	Constructor:
		pContour(flContour)

	Attributes:
		.fl (flContour): Original flContour 
	'''
	def __init__(self, contour):
		# - Properties
		self.fl = contour
		self.id = self.fl.id
		self.name = self.fl.name
		self.closed = self.fl.closed
		self.start = self.fl.first
		self.glyph = self.fl.glyph
		self.font = self.fl.font
		self.layer = self.fl.layer
		self.reversed = self.fl.reversed
		self.transform = self.fl.transform

		# - Functions
		self.bounds = lambda : self.fl.bounds # (xMin, yMin, xMax, yMax)
		self.x = lambda : self.bounds()[0]
		self.y = lambda : self.bounds()[1]
		self.width = lambda : self.bounds()[2] - self.bounds()[0]
		self.height  = lambda : self.bounds()[3] - self.bounds()[1]

		self.selection = lambda : self.fl.selection
		self.setStart = self.fl.setStartPoint
		self.segments = self.fl.segments
		self.nodes = self.fl.nodes
		self.update = self.fl.update
		self.applyTransform = self.fl.applyTransform
		self.shift = lambda dx, dy: self.fl.move(pqt.QtCore.QPointF(dx, dy))

	def __repr__(self):
		return '<{} ({}, {}) nodes={} ccw={} closed={}>'.format(self.__class__.__name__, self.x(), self.y(), len(self.nodes()), self.isCCW(), self.closed)

	def reverse(self):
		self.fl.reverse()

	def isCW(self):
		# FL has an error here or.... just misnamed the method?
		return not self.fl.clockwise

	def isCCW(self):
		return self.fl.clockwise

	def setCW(self):
		if not self.isCW(): self.reverse()

	def setCCW(self):
		if not self.isCCW(): self.reverse()

	def isAllSelected(self):
		'''Is the whole contour selected '''
		return all(self.selection())

	def translate(self, dx, dy):
		self.fl.transform = self.fl.transform.translate(dx, dy)
		self.fl.applyTransform()

	def scale(self, sx, sy):
		self.fl.transform = self.fl.transform.scale(dx, dy)
		self.fl.applyTransform()

	def slant(self, deg):
		self.fl.transform = self.fl.transform.shear(math.tan(math.radians((deg)), 0))
		self.fl.applyTransform()
		
	def rotate(self, deg):
		self.fl.transform = self.fl.transform.rotate(math.tan(math.radians((deg))))
		self.fl.applyTransform()

	def draw(self, pen, transform=None):
		''' Utilizes the Pen protocol'''
		self.fl.convertToFgContour(transform).draw(pen)

# -- Extensions -------------------------
class eContour(pContour):
	'''Extended representation of the Proxy Contour, adding some advanced functionality.

	Constructor:
		eContour(flContour)
		
	'''
	# - Extension -----------------------
	def asCoord(self):
		'''Returns Coord object of the Bottom lest corner.'''
		return Coord(float(self.x()), float(self.y()))

	def getNext(self):
		pass

	def getPrev(self):
		pass

	# - Align and distribute
	def alignTo(self, entity, alignMode='', align=(True,True)):
		'''Align current contour.
		Arguments:
			entity ()
			alignMode (String) : L(left), R(right), C(center), T(top), B(bottom), E(vertical center) !ORDER MATTERS
		'''
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
			if any([isinstance(entity, item) for item in [fl6.flNode, pNode, Coord, pqt.QtCore.QPointF]]):
				target = Coord(entity.x, entity.y)

			elif any([isinstance(entity, item) for item in [fl6.flContour, pContour, self.__class__]]):
				
				if isinstance(entity, fl6.flContour):
					temp_entity = self.__class__(entity)
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
			print('ERROR:\t Invalid Align Mode: {}'.format(alignMode))