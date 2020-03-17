# MODULE: Fontlab 6 Custom Shape Objects | Typerig
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.4.3'

# - Dependencies -------------------------
import fontlab as fl6
#import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pShape

class eShape(pShape):
	'''Extended representation of the Proxy Shape, adding some advanced functionality.

	Constructor:
		eShape(flShape)
		
	'''
	# - Extension -----------------------
	def asCoord(self):
		'''Returns Coord object of the Bottom lest corner.'''
		from typerig.brain import Coord
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
		from typerig.proxy import pNode
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
			if any([isinstance(entity, item) for item in [fl6.flNode, pNode, Coord, QPointF]]):
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
			print 'ERROR:\t Invalid Align Mode: %s' %alignMode

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




			

