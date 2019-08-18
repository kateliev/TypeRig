# MODULE: Fontlab 6 Custom Contour Objects | Typerig
# VER 	: 0.01
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import fontlab as fl6
#import fontgate as fgt
import PythonQt as pqt

from typerig.proxy import pContour

class eContour(pContour):
	'''Extended representation of the Proxy Contour, adding some advanced functionality

	Constructor:
		eContour(flContour)
		
	'''
	# - Extension -----------------------
	def asCoord(self):
		'''Returns Coord object of the node.'''
		from typerig.brain import Coord
		return Coord(float(self.x), float(self.y))

	def getNext(self):
		pass

	def getPrev(self):
		pass

	# - Align and distribute
	def alignTo(self, entity, alignX='', alignY='', coord=None):
		'''Align current contour.
		Arguments:
			entity ()
			alignMode (String) : L(left), R(right), C(center), T(top), B(bottom), E(vertical center)
		'''
		from typerig.proxy import pNode
		from PythonQt.QtCore import QPointF
		from typerig.brain import Coord

		
		# - Helper
		def getAlignDict(item)
			align_dict_x = {	'L': item.x, 
								'R': item.x + item.width, 
								'C': item.x + item.width/2
							}

			align_dict_y = {					
								'B': item.y, 
								'T': item.y + item.height, 
								'E': item.y + item.height/2,
							}

			return align_dict_x, align_dict_y

		# - Init
		# -- Get target for alignment
		if any([isinstance(entity, item) for item in [fl6.flNode, pNode]]):
			target = Coord(entity.x, entity.y)

		elif any([isinstance(entity, item) for item in [fl6.flContour, pContour, self.__class__]]):
			
			if isinstance(entity, fl6.flContour):
				temp_entity = self.__class__(entity)
			else:
				temp_entity = entity

			align_dict_x, align_dict_y = getAlignDict(temp_entity)
			target = Coord(align_dict_x[alignX], align_dict_y[alignX])

		# -- Get source for alignment
		self_dict_x, self_dict_y = getAlignDict(self)
		source =  Coord(self_dict_x[alignX], self_dict_y[alignX])




			

