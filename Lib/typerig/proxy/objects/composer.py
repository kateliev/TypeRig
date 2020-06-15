# MODULE: Typerig / Proxy / Composer (Objects)
# ------------------------------------------------------
# (C) Vassil Kateliev, 2017 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 	(http://www.karandash.eu)
#--------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from collections import defaultdict, OrderedDict

# - Init ---------------------------------
__version__ = '0.0.1'

# - Classes -------------------------------------------------------
class dictComposer(object):
	''' For CSV I/O'''
	
	def __init__(self, glyph):
		self.name = glyph.name
		self.data = defaultdict(list)

		for layer in glyph.masters():
			for shape in layer.shapes:
				if shape.shapeData.isComponent:
					sn = shape.shapeData.componentGlyph
					st =  shape.transform
					self.data[sn].append((layer.name, self.componentTransform(st.m31(), st.m32(), st.m11(), st.m22(), st.m21())))

	def  __getitem__(self, comp_name):
		return OrderedDict(self.data[comp_name])

	def __repr__(self):
		return '<{}: {}>'.format(self.__class__, self.components)

	@property
	def components(self):
		return self.data.keys()

	# - Helper
	class componentTransform(object):
		def __init__(self, x, y, sx, sy, i):
			self.x = x
			self.y = y
			self.sx = sx
			self.sy = sy
			self.i = i

		def __repr__(self):
			return str(self.tuple)

		@property
		def tuple(self):
			return (self.x, self.y, self.sx, self.sy, self.i)

		