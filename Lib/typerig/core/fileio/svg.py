# MODULE: Typerig / IO / SVG Parser (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2025 	(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from fontlab_private.fontTools.misc import etree
from fontlab_private.fontTools.misc.py23 import SimpleNamespace

from fontlab_private.fontTools.svgLib.path.parser import parse_path
from fontlab_private.fontTools.svgLib.path.shapes import PathBuilder

from fontlab_private.fontTools.pens.transformPen import TransformPen
from fontlab_private.fontTools.pens.pointPen import SegmentToPointPen

# - Init -----------------------------
__version__ = '0.0.6'

# - Classes --------------------------
class SVGPathFilter(object):
	'''Parse SVG ``path`` elements from a file or string, and draw them
	onto a glyph object that supports the FontTools Pen protocol. 
	Readapted from FontTools suite with additional contour filtering options
	using exlude_dict={'tag_name_string':['seach_string_0',...'seach_string_n']}
	
	Usage example:

	import fontgate as fgt
	with open('your_filename.svg', "r") as file: 
		svg = file.read()

	outline = SVGPathFilter.fromstring(svg, transform=[20.0, 0.0, 0.0, 20.0, 0.0, 0.0])
	destination_glyph = fgt.fgGlyph()
	pen = fgt.fgPen(destination_glyph)
	outline.draw(pen)

	Both constructors can optionally take a 'transform' matrix (6-float
	tuple, or a FontTools Transform object) to modify the draw output.
	'''

	def __init__(self, filename=None, transform=None, exlude_dict={}):
		if filename is None:
			self.root = etree.ElementTree()
		else:
			tree = etree.parse(filename)
			self.root = tree.getroot()
		
		self.transform = transform
		self.exlude_dict = exlude_dict

	@classmethod
	def fromstring(cls, data, transform=None, exlude_dict={}):
		self = cls(transform=transform, exlude_dict=exlude_dict)
		self.root = etree.fromstring(data)
		return self

	def filtertags(self, obj, filter_dict, test_any=False):
		if not len(filter_dict.keys()): 
			return False
		
		bool_table = []
		
		for tag, test in filter_dict.items():
			if obj.get(tag) is not None:
				test_result = [item.lower() not in obj.get(tag).lower() for item in test]
			else:
				test_result = [True] # was [Fasle], but this does not load unnamed/taged elements

			bool_table.append(any(test_result) if test_any else all(test_result))

		return any(bool_table) if test_any else all(bool_table)

	def draw(self, pen):
		if self.transform:
			pen = TransformPen(pen, self.transform)
		pb = PathBuilder()
						
		for child in self.root:
			if self.filtertags(child, self.exlude_dict): # Filter unwanted SVG elements
				for el in child.iter():
					pb.add_path_from_element(el)
		
		original_pen = pen
		
		for path, transform in zip(pb.paths, pb.transforms):
			if transform:
				pen = TransformPen(original_pen, transform)
			else:
				pen = original_pen

			parse_path(path, pen)

# - Test -----------------------------
if __name__ == '__main__':
	import fontlab as fl6
	import fontgate as fgt
	from typerig.proxy import *

	# - Init
	font = pFont()
	g = eGlyph()
	exclude_svg_elements = {'id':['guide']}

	# - Load File
	with open(r'd:\1.svg', "r") as f:
		svg = f.read()

	# - Run
	outline = SVGPathFilter.fromstring(svg, transform=[20.0, 0.0, 0.0, 20.0, 0.0, 0.0], exlude_dict=exclude_svg_elements)
	dest_glyph = fgt.fgGlyph()
	pen = fgt.fgPen(dest_glyph)
	outline.draw(pen)
	g.addShape(fl6.flShape(dest_glyph.layer[0]))

	g.updateObject(g.fl)

