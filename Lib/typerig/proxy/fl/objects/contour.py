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
import fontgate as fgt
import PythonQt as pqt

from typerig.core.func.math import linspread
from typerig.proxy.fl.objects.base import Coord
from typerig.proxy.fl.objects.node import pNode

# - Init --------------------------------
__version__ = '0.26.8'

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

		# - Functions/ properties !!! OLD convert to properties!
		self.selection = lambda : self.fl.selection
		self.setStart = self.fl.setStartPoint
		self.segments = self.fl.segments
		self.nodes = self.fl.nodes
		self.update = self.fl.update
		self.applyTransform = self.fl.applyTransform
		self.shift = lambda dx, dy: self.fl.move(pqt.QtCore.QPointF(dx, dy))

	def __repr__(self):
		return '<{} ({}, {}) nodes={} ccw={} closed={}>'.format(self.__class__.__name__, self.x, self.y, len(self.nodes()), self.isCCW(), self.closed)

	# - Properties -----------------------------------------------
	@property
	def bounds(self):
		return self.fl.bounds

	@property
	def rect(self):
		return self.fl.boundingBox()

	@property
	def x(self):
		return self.bounds[0]
	
	@property
	def y(self):
		return self.bounds[1]

	@property
	def width(self):
		return self.rect.width()

	@property
	def height(self):
		return self.rect.height()	
	
	@property
	def center(self):
		return self.rect.center()

	@property
	def fg(self):
		return self.fl.convertToFgContour(self.fl.transform)

	@property
	def area(self):
		return self.fg.area()
	
	# - Functions ------------------------------------------------
	def indexOn(self):
		'''Return list of indexes of all on curve points'''
		return [node.index for node in self.nodes() if node.isOn()]

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

	def pointInPolygon(self, point, use_fg=False, winding=False):
		''' Performs point in polygon test for given point (QPointF)'''
		if not use_fg:
			return self.fl.pointInside(point)
		else:
			return self.fg.contains(fgt.fgPoint(point.x(), point.y()), winding)

	def contains(self, other):
		''' Performs point in polygon and polygon in polygon test for given entity (QPointF or flContour)'''
		if isinstance(other, self.__class__):
			other = other.fl

		return self.fl.contains(other)

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

	# - Procedures ----------------------
	# -- Nodes --------------------------
	def randomize(self, cx, cy, bleedMode=0):
		'''Randomizes the contour node coordinates within given contrains cx and cy.
		Bleed control trough bleedMode parameter: 0 - any; 1 - positive bleed; 2 - negative bleed;
		'''
		for node in self.nodes():
			wNode = pNode(node)
			wNode.randomize(cx, cy, bleedMode)

	def fragmentize(self, countOrLength, lengthThreshold, lengthMode=False, processIndexes=[]):
		'''Split contour in multiple fragments:
		Args:
			countOrLength (int): Number of nodes to insert or length of the resulting segment.
			lengthThreshold (int/float): Minimum distances threshold for processing. Segments below will be skipped.
			lengthMode (bool): Controls countOrLength. False = insert a specified number of nodes; True = split into segments of specified length.
			processIndexes (list(int)): Specify node indexes to be processed. If empty - process whole contour.

		Returns:
			None
		'''
		if len(processIndexes):
			process_nodes = [pNode(self.nodes()[nid]) for nid in processIndexes]
		else:
			process_nodes = [pNode(node) for node in self.nodes() if node.isOn()]

		while len(process_nodes):
			wNode = process_nodes.pop(0)
			distance_to_next = wNode.distanceTo(wNode.getNextOn())
			
			if distance_to_next > lengthThreshold:
				if lengthMode:
					insertNodesCount = int(distance_to_next/float(countOrLength))
				else:
					insertNodesCount = countOrLength

				for insert in range(insertNodesCount):
					self.fl.insertNodeTo(1 + wNode.time - 1/float(insertNodesCount - insert + 1))

	def linearize(self):
		'''Convert curves to lines'''
		for node in self.nodes():
			node.convertToLine()

	def curverize(self, smooth=True):
		'''Convert curves to lines'''
		for node in self.nodes():
			node.convertToCurve(smooth)

	# -- Align and distribute -----------
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