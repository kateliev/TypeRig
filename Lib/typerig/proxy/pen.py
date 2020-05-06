# MODULE: Typerig / Proxy / Pen (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies --------------------------
import fontlab as fl6
import fontgate as fgt

# - Init ---------------------------------
__version__ = '0.0.1'

# - Classes -------------------------------
class AbstractPen(object):
	'''AbstractPen as specified by FontTools (fontTools.pens.basePen.py)
	'''
	def moveTo(self, pt):
		'''Begin a new sub path, set the current point to 'pt'. You must
		end each sub path with a call to pen.closePath() or pen.endPath().
		'''
		raise NotImplementedError

	def lineTo(self, pt):
		'''Draw a straight line from the current point to 'pt'.'''
		raise NotImplementedError

	def curveTo(self, *points):
		'''Draw a cubic bezier with an arbitrary number of control points.

		The last point specified is on-curve, all others are off-curve
		(control) points. If the number of control points is > 2, the
		segment is split into multiple bezier segments. This works
		like this:

		Let n be the number of control points (which is the number of
		arguments to this call minus 1). If n==2, a plain vanilla cubic
		bezier is drawn. If n==1, we fall back to a quadratic segment and
		if n==0 we draw a straight line. It gets interesting when n>2:
		n-1 PostScript-style cubic segments will be drawn as if it were
		one curve. See decomposeSuperBezierSegment().

		The conversion algorithm used for n>2 is inspired by NURB
		splines, and is conceptually equivalent to the TrueType "implied
		points" principle. See also decomposeQuadraticSegment().
		'''
		raise NotImplementedError

	def qCurveTo(self, *points):
		'''Draw a whole string of quadratic curve segments.

		The last point specified is on-curve, all others are off-curve
		points.

		This method implements TrueType-style curves, breaking up curves
		using 'implied points': between each two consequtive off-curve points,
		there is one implied point exactly in the middle between them. See
		also decomposeQuadraticSegment().

		The last argument (normally the on-curve point) may be None.
		This is to support contours that have NO on-curve points (a rarely
		seen feature of TrueType outlines).
		'''
		raise NotImplementedError

	def closePath(self):
		'''Close the current sub path. You must call either pen.closePath()
		or pen.endPath() after each sub path.
		'''
		pass

	def endPath(self):
		'''End the current sub path, but don't close it. You must call
		either pen.closePath() or pen.endPath() after each sub path.
		'''
		pass

	def addComponent(self, glyphName, transformation):
		'''Add a sub glyph. The 'transformation' argument must be a 6-tuple
		containing an affine transformation, or a Transform object from the
		fontTools.misc.transform module. More precisely: it should be a
		sequence containing 6 numbers.
		'''
		raise NotImplementedError

class AbstractPointPen(object):
	'''Baseclass for all PointPens as specified by FontTools (fontTools.pens.pointPen.py)
	'''

	def beginPath(self, identifier=None, **kwargs):
		'''Start a new sub path.'''
		raise NotImplementedError

	def endPath(self):
		'''End the current sub path.'''
		raise NotImplementedError

	def addPoint(self, pt, segmentType=None, smooth=False, name=None,
				 identifier=None, **kwargs):
		'''Add a point to the current sub path.'''
		raise NotImplementedError

	def addComponent(self, baseGlyphName, transformation, identifier=None,
					 **kwargs):
		'''Add a sub glyph.'''
		raise NotImplementedError