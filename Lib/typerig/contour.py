# MODULE: Fontlab 6 Custom Contour Objects | Typerig
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.4.0'

# - Dependencies -------------------------
import fontlab as fl6
#import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pContour

class eContour(pContour):
	'''Extended representation of the Proxy Contour, adding some advanced functionality.

	Constructor:
		eContour(flContour)
		
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
			print 'ERROR:\t Invalid Align Mode: %s' %alignMode




			

