# MODULE: Typerig / Proxy / Sampler (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020         (http://www.kateliev.com)
# (C) Karandash Type Foundry        (http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ----------------------
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

#from typerig.proxy import *
from typerig.core.objects.point import Point, Void
from typerig.proxy.objects.base import Line, Curve
from typerig.core.func.math import linspread

# - Init -----------------------------
__version__ = '0.1.2'

# - Classes --------------------------
class GlyphSampler(object):
	'''Glyph sampler for area analysis.
	Partially inspired by Huerta Tipografica Letterspacer (https://github.com/huertatipografica/HTLetterspacer)

	Constructor:
		GlyphSampler()
		GlyphSampler(sample window, sample frequency)

	Attributes:
		.data_samples (dict) -> {glyph_name:{layer:(left_samples, mid_samples, right_samples)}}: Cached data of Glyph samples 
		.data_area (dict) -> {glyph_name:{layer:(left_area, mid_area, right_area)}}: Cached data of Glyph area regions

		.sample_window (list/tuple) -> [min_y, max_y]: Window of scanning
		.sample_frequency (int) : Sampling frequency
		.sample_range range(window_min, window_max, sample_frequency): Sampling range
		.sample_quantas list(int): Quantized sampling rage - the window is split in "sample_frequency" number of regions
		.use_quantizer (bool): Use Quantized sampling range

		.margin_growth (int): Grow margin outside the glyph BBoX
		.cutout_x, .cutout_y: Cutout values defining how deep (x) or hight (y) the probing is done

	Methods:
		...

	TODO: Italics - slat/deslat or slanted zones?!
	'''
	def __init__(self, sample_window=[0, 1000], sample_frequency=20):
		self._delta_error = 100
		self._practical_infinity = 10000
		self._mask_layer_prefix = 'mask.'
		self._mask_layer_suffix = '.area'
		
		self.data_samples = {}
		self.data_area = {}
		
		self.use_quantizer = False
		self.margin_growth = 0
		self.cutout_x = 100
		self.cutout_y = self._practical_infinity

		self.updateRange(sample_window, sample_frequency)

	# - Functions ---------------------
	# - Range -------------------------
	def updateRange(self, sample_window=None, sample_frequency=None):
		if sample_window is not None: self.sample_window = [int(sample_window[0]), int(sample_window[1])]
		if sample_frequency is not None: self.sample_frequency = int(sample_frequency)

		# - Regular Range
		self.sample_range = range(self.sample_window[0], self.sample_window[1], self.sample_frequency)
		
		# - Quantized Range -> predefined number of samples = sample_frequency
		self.sample_quantas = list(linspread(self.sample_window[0], self.sample_window[1], self.sample_frequency))

	def getRange(self, quantized=False):
		return self.sample_quantas if quantized else self.sample_range

	# - Filters -----------------------
	@staticmethod   
	def filterBandPass(point_list, cutout_depth=(10000, 10000), in_reverse=False):
		min_x, max_x, min_y, max_y = GlyphSampler.getBounds(point_list)
		cutout_depth_x, cutout_depth_y = cutout_depth
		return_list = []

		cutout_value_x = [min_x, max_x][in_reverse] + cutout_depth_x*[1, -1][in_reverse]
		cutout_value_y = [min_y, max_y][in_reverse] + cutout_depth_y*[1, -1][in_reverse]
		
		for p in point_list:
			px, py = p.tuple
			if [px > cutout_value_x, px < cutout_value_x][in_reverse]: px = cutout_value_x
			if [py > cutout_value_y, py < cutout_value_y][in_reverse]: py = cutout_value_y

			return_list.append(Point(px, py))

		return return_list

	@staticmethod
	def filterClosePoly(point_list, in_reverse=False, grow_value=0):
		min_x, max_x, min_y, max_y = GlyphSampler.getBounds(point_list)
		x = min_x - grow_value if not in_reverse else max_x + grow_value

		point_list.insert(0, Point(x, min_y))
		point_list.append(Point(x, max_y))

		return point_list

	# - Getters ---------------------------------
	@staticmethod
	def getArea(point_list):
		corners = len(point_list) 
		area = 0.0
		
		for i in range(corners):
			j = (i + 1) % corners
			area += abs(point_list[i].x*point_list[j].y - point_list[j].x*point_list[i].y)

		return area*0.5

	@staticmethod
	def getBounds(point_list):
		min_x = min(point_list, key= lambda p: p.x).x
		max_x = max(point_list, key= lambda p: p.x).x
		min_y = min(point_list, key= lambda p: p.y).y
		max_y = max(point_list, key= lambda p: p.y).y
		
		return min_x, max_x, min_y, max_y

	@staticmethod
	def getContour(point_list, get_fg_contour=False):
		new_contour = fl6.flContour([pqt.QtCore.QPointF(*p.tuple) for p in point_list], closed=True)
		new_fg_contour = new_contour.convertToFgContour()   
		return new_contour if not get_fg_contour else new_fg_contour

	# - Glyph sampling ------------------------------------ 
	@staticmethod
	def getSamples(glyph, layer, sampling_range):
		layer_bounds = glyph.getBounds(layer)
		layer_contours = glyph.contours(layer)

		min_x = int(layer_bounds.x()) #- delta
		max_x = int(layer_bounds.width() + min_x)  
		mid_x = (min_x + max_x)*0.5
		
		max_x += 100 # Boundary error compensation?! TO FIX! Presumable problem with Line().hasPoint()
		
		min_y = int(layer_bounds.y())
		max_y = int(layer_bounds.height() + min_y)

		ipoi_left, ipoi_right = [], [] # Intersections points of interest

		probe_list = [Line((min_x, y), (max_x, y)) for y in sampling_range if min_y <= y <= max_y] # Create all horizontal slicing lines (proves)
		prepare_segments = sum([contour.segments() for contour in layer_contours],[])
		tr_segments = []

		for segment in prepare_segments:
			if segment.countPoints == 2:
				temp_tr_segment = Line(segment)
			elif segment.countPoints == 4:
				temp_tr_segment = Curve(segment)

			tr_segments.append(temp_tr_segment)

		for probe in probe_list:
			temp_probe_poi = []

			for tr_segment in tr_segments:
				intersection = tr_segment & probe

				if len(intersection) and not isinstance(intersection, Void):
					if isinstance(intersection, list):
						temp_probe_poi += intersection
					else:
						temp_probe_poi.append(intersection)
			
			if len(temp_probe_poi) >= 2:
				ipoi_left.append(min(temp_probe_poi, key= lambda p: p.x))
				ipoi_right.append(max(temp_probe_poi, key= lambda p: p.x))
			
			elif len(temp_probe_poi) == 1: # Single intersection fix
				qpoi = temp_probe_poi[0]   # Questionable poi
				if qpoi.x < mid_x: 
					ipoi_left.append(qpoi)
				else:
					ipoi_right.append(qpoi)

		return ipoi_left, ipoi_right

	def sampleGlyph(self, glyph, layer=None, cache_data=True):
		# - Get initial data
		layer_data = {}
		layer_name = layer if layer is not None else glyph.layer(layer).name
		sample_left, sample_right = self.getSamples(glyph, layer, self.getRange(self.use_quantizer))
		
		# - Process samples
		sample_left = GlyphSampler.filterBandPass(sample_left, (self.cutout_x, self.cutout_y), False)
		sample_right = GlyphSampler.filterBandPass(sample_right, (self.cutout_x, self.cutout_y), True)
		sample_mid = sample_left + list(reversed(sample_right))
		
		sample_left = GlyphSampler.filterClosePoly(sample_left, False, self.margin_growth)
		sample_right = GlyphSampler.filterClosePoly(sample_right, True, self.margin_growth)

		layer_data[layer_name] = (sample_left, sample_mid, sample_right)

		# - Cache
		if cache_data: self.data_samples.setdefault(glyph.name, {}).update(layer_data)

		return layer_data[layer_name]

	def sampleGlyphArea(self, glyph, layer=None, resample=False, cache_data=True):
		glyph_name = glyph.name
		layer_name = layer if layer is not None else glyph.layer(layer).name
		layer_area = {}
		
		if self.data_samples.has_key(glyph_name) and not resample:
			if self.data_samples[glyph_name].has_key(layer_name):
				layer_data = self.data_samples[glyph_name][layer_name]
			else:
				layer_data = self.sampleGlyph(glyph, layer_name, True)
		else:
			layer_data = self.sampleGlyph(glyph, layer_name, True)

		left, mid, right = layer_data
		contour_left =  GlyphSampler.getContour(left, True)
		contour_mid =   GlyphSampler.getContour(mid, True)
		contour_right = GlyphSampler.getContour(right, True)

		area_left = abs(contour_left.area())
		area_mid = abs(contour_mid.area())
		area_right = abs(contour_right.area())

		layer_area[layer_name] = (area_left, area_mid, area_right)

		if cache_data: self.data_area.setdefault(glyph_name, {}).update(layer_area)

		return layer_area[layer_name]

	# - Represent ----------------------------------------------------
	def drawGlyphArea(self, glyph, layer=None):
		glyph_name = glyph.name
		layer_name = layer if layer is not None else glyph.layer(layer).name
		mask_layer_name = self._mask_layer_prefix + layer_name + self._mask_layer_suffix
		
		if self.data_samples.has_key(glyph_name) and self.data_samples[glyph_name].has_key(layer_name):
			
			if glyph.hasLayer(mask_layer_name):
				mask_layer = glyph.layer(mask_layer_name)
				mask_layer.removeAllShapes()
			else:
				mask_layer = glyph.layer(layer_name).getMaskLayer(True)
				mask_layer.name += self._mask_layer_suffix
				
			left, mid, right = self.data_samples[glyph_name][layer_name]
			 
			contour_left =  GlyphSampler.getContour(left, False)
			contour_mid =   GlyphSampler.getContour(mid, False)
			contour_right = GlyphSampler.getContour(right, False)
			
			new_shape = fl6.flShape()
			new_shape.addContours([contour_left, contour_mid, contour_right], True)
			mask_layer.addShape(new_shape)
		else:
			print 'ABORT:\t Draw Area;\t Glyph: %s; Layer: %s;\tGlyphSampler data not found!' %(glyph_name, layer_name)

# - Test ----------------------
if __name__ == '__main__':

	font = pFont()
	g = eGlyph()

	# - Configure 
	font_descender = min([font.fontMetrics().getDescender(layer) for layer in font.masters()])
	font_ascender =  max([font.fontMetrics().getAscender(layer) for layer in font.masters()])
	font_x_height = max([font.fontMetrics().getXHeight(layer) for layer in font.masters()])
	font_upm = font.fontMetrics().getUpm()

	# - Prepare GlyphSampler
	sample_window = (font_descender, font_ascender)
	gsmp = GlyphSampler(sample_window)
	gsmp.cutout_x = font_x_height*0.15
	gsmp.sampleGlyphArea(g)
	gsmp.drawGlyphArea(g)

	g.updateObject(g.fl)

	# - Finish ---------------------------
	print 'SAMPLER: %s;' %g.name