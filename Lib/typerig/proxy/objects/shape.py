# MODULE: Typerig / Proxy / Shape (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.proxy.objects.base import *
from typerig.proxy.objects.node import *

# - Init ---------------------------------
__version__ = '0.26.1'

# - Classes -------------------------------
class pShape(object):
	'''Proxy to flShape, flShapeData and flShapeInfo objects

	Constructor:
		pShape(flShape)

	Attributes:
		.fl (flNode): Original flNode 
		.parent (flContour): parent contour
		.contour (flContour): parent contour
	'''
	def __init__(self, shape, layer=None, glyph=None):
		self.fl = shape
		self.shapeData = self.data()
		self.refs = self.shapeData.referenceCount
		self.container = self.includesList = self.fl.includesList
		
		self.currentName = self.fl.name
		self.name = self.shapeData.name

		self.bounds = lambda: self.fl.boundingBox
		self.x = lambda : self.bounds().x()
		self.y = lambda : self.bounds().y()
		self.width = lambda : self.bounds().width()
		self.height  = lambda : self.bounds().height()

		self.parent = glyph
		self.layer = layer

	def __repr__(self):
		return '<{} name={} references={} contours={} contains={}>'.format(self.__class__.__name__, self.name, self.refs, len(self.contours()), len(self.container))

	# - Basics -----------------------------------------------
	def data(self):
		''' Return flShapeData Object'''
		return self.fl.shapeData

	def info(self):
		''' Return flShapeInfo Object'''
		pass

	def builder(self):
		''' Return flShapeBuilder Object'''
		return self.fl.shapeBuilder

	def container(self):
		''' Returns a list of flShape Objects that are contained within this shape.'''
		return self.fl.includesList

	def tag(self, tagString):
		self.data().tag(tagString)

	def isChanged(self):
		return self.data().hasChanges

	def update(self):
		return self.fl.update()

	# - Management ---------------------------------
	def setName(self, shape_name):
		self.data().name = shape_name

	# - Position, composition ---------------------------------
	def decompose(self):
		self.fl.decomposite()

	def goUp(self):
		return self.data().goUp()

	def goDown(self):
		return self.data().goDown()

	def goFrontOf(self, flShape):
		return self.data().sendToFront(flShape)

	def goBackOf(self, flShape):
		return self.data().sendToBack(flShape)

	def goLayerBack(self):
		if self.layer is not None:
			return self.goBackOf(self.layer.shapes[0])
		return False

	def goLayerFront(self):
		if self.layer is not None:
			return self.goFrontOf(self.layer.shapes[-1])
		return False

	# - Contours, Segmets, Nodes ------------------------------
	def segments(self):
		return self.data().segments

	def contours(self):
		return self.data().contours

	def nodes(self):
		return [node for contour in self.contours() for node in contour.nodes()]

	# - Complex shapes, builders and etc. ---------------------
	def copyBuilder(self, source):
		if isinstance(source, fl6.flShapeBuilder):
			self.fl.shapeBuilder = source.clone()
		elif isinstance(source, fl6.flShape):
			self.fl.shapeBuilder = source.flShapeBuilder.clone()

		self.fl.update()

	# - Transformation ----------------------------------------
	def reset_transform(self):
		temp_transform = self.fl.transform
		temp_transform.reset()
		self.fl.transform = temp_transform

	def shift(self, dx, dy, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.translate(dx, dy)

	def rotate(self, angle, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.rotate(angle)

	def scale(self, sx, sy, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.scale(sx, sy)

	def shear(self, sh, sv, reset=False):
		if reset: self.reset_transform()
		self.fl.transform = self.fl.transform.shear(sh, sv)

	# - Pens -----------------------------------------------
	def draw(self, pen):
		''' Utilizes the Pen protocol'''
		for contour in self.fl.contours:
			contour.convertToFgContour(shape.fl_transform.transform).draw(pen)

# -- Extensions ---------------------------
class eShape(pShape):
	'''Extended representation of the Proxy Shape, adding some advanced functionality.

	Constructor:
		eShape(flShape)
		
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
			if any([isinstance(entity, item) for item in [fl6.flNode, pNode, Coord, pqt.QPointF]]):
				target = Coord(entity.x, entity.y)

			elif any([isinstance(entity, item) for item in [fl6.flShape, pShape, self.__class__]]):
				
				if isinstance(entity, fl6.flShape):
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

			self.shift(shift_dx, shift_dy, True)
		else:
			print('ERROR:\t Invalid Align Mode: {}'.fromat(alignMode))

	def _round_transformations(self, shape):
		rm11 = round(shape.fl_transform.transform.m11()*100)/100.
		rm12 = round(shape.fl_transform.transform.m12()*100)/100.
		rm13 = round(shape.fl_transform.transform.m13()*100)/100.
		rm21 = round(shape.fl_transform.transform.m21()*100)/100.
		rm22 = round(shape.fl_transform.transform.m22()*100)/100.
		rm23 = round(shape.fl_transform.transform.m23()*100)/100.
		rm31 = round(shape.fl_transform.transform.m31())
		rm32 = round(shape.fl_transform.transform.m32())
		rm33 = round(shape.fl_transform.transform.m33()*100)/100.
		
		new_transform = pqt.QtGui.QTransform(rm11, rm12, rm13, rm21, rm22, rm23, rm31, rm32, rm33)
		shape.fl_transform.transform = new_transform
		shape.update()

		if len(shape.includesList):
			for icluded_shape in shape.includesList:
				self._round_transformations(icluded_shape)

	def round(self):
		self._round_transformations(self.fl)




			

