# MODULE: TypeRig / Core / Font (Object)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

from typerig.core.objects.transform import Transform
from typerig.core.objects.utils import Bounds
from typerig.core.objects.delta import DeltaScale

from typerig.core.objects.atom import Container
from typerig.core.objects.layer import Layer
from typerig.core.objects.glyph import Glyph

# - Init -------------------------------
__version__ = '0.1.1'

# - Classes -----------------------------
class FontInfo(object):
	__slots__ = (	
				'ascender',
				'capHeight',
				'caretOffset',
				'copyright',
				'descender',
				'dict',
				'familyName',
				'italicAngle',
				'macintoshFONDFamilyID',
				'macintoshFONDName',
				'note',
				'openTypeHeadCreated',
				'openTypeHeadFlags',
				'openTypeHeadFontDirectionHint',
				'openTypeHeadLowestRecPPEM',
				'openTypeHeadModified',
				'openTypeHheaAscender',
				'openTypeHheaCaretOffset',
				'openTypeHheaCaretSlopeRise',
				'openTypeHheaCaretSlopeRun',
				'openTypeHheaDescender',
				'openTypeHheaLineGap',
				'openTypeNameCompatibleFullName',
				'openTypeNameDescription',
				'openTypeNameDesigner',
				'openTypeNameDesignerURL',
				'openTypeNameLicense',
				'openTypeNameLicenseURL',
				'openTypeNameManufacturer',
				'openTypeNameManufacturerURL',
				'openTypeNamePreferredFamilyName',
				'openTypeNamePreferredSubfamilyName',
				'openTypeNameSampleText',
				'openTypeNameUniqueID',
				'openTypeNameVersion',
				'openTypeNameWWSFamilyName',
				'openTypeNameWWSSubfamilyName',
				'openTypeOS2CodePageRanges',
				'openTypeOS2FamilyClass',
				'openTypeOS2Panose',
				'openTypeOS2Selection',
				'openTypeOS2StrikeoutPosition',
				'openTypeOS2StrikeoutSize',
				'openTypeOS2SubscriptXOffset',
				'openTypeOS2SubscriptXSize',
				'openTypeOS2SubscriptYOffset',
				'openTypeOS2SubscriptYSize',
				'openTypeOS2SuperscriptXOffset',
				'openTypeOS2SuperscriptXSize',
				'openTypeOS2SuperscriptYOffset',
				'openTypeOS2SuperscriptYSize',
				'openTypeOS2Type',
				'openTypeOS2TypoAscender',
				'openTypeOS2TypoDescender',
				'openTypeOS2TypoLineGap',
				'openTypeOS2UnicodeRanges',
				'openTypeOS2VendorID',
				'openTypeOS2WeightClass',
				'openTypeOS2WidthClass',
				'openTypeOS2WinAscent',
				'openTypeOS2WinDescent',
				'openTypeVheaCaretOffset',
				'openTypeVheaCaretSlopeRise',
				'openTypeVheaCaretSlopeRun',
				'openTypeVheaVertTypoAscender',
				'openTypeVheaVertTypoDescender',
				'openTypeVheaVertTypoLineGap',
				'postscriptBlueFuzz',
				'postscriptBlueScale',
				'postscriptBlueShift',
				'postscriptBlueValues',
				'postscriptDefaultCharacter',
				'postscriptDefaultWidthX',
				'postscriptFamilyBlues',
				'postscriptFamilyOtherBlues',
				'postscriptFontName',
				'postscriptForceBold',
				'postscriptFullName',
				'postscriptIsFixedPitch',
				'postscriptNominalWidthX',
				'postscriptOtherBlues',
				'postscriptSlantAngle',
				'postscriptStemSnapH',
				'postscriptStemSnapV',
				'postscriptUnderlinePosition',
				'postscriptUnderlineThickness',
				'postscriptUniqueID',
				'postscriptWeightName',
				'postscriptWindowsCharacterSet',
				'styleMapFamilyName',
				'styleMapStyleName',
				'styleName',
				'trademark',
				'unitsPerEm',
				'versionMajor',
				'versionMinor',
				'xHeight',
				'year'
				)

class Font(Container): 
	__slots__ = ('info', 'axes', 'masters', 'instances', 'features', 'classes', 'kerning', 'identifier')

	def __init__(self, data=None, **kwargs):
		factory = kwargs.pop('default_factory', Glyph)
		super(Font, self).__init__(data, default_factory=factory, **kwargs)
		
		# - Metadata
		if not kwargs.pop('proxy', False): # Initialize in proxy mode
			self.identifier = kwargs.pop('identifier', None)

			# - Basic
			self.info = kwargs.pop('info', FontInfo())

			# - Designspace
			self.axes = kwargs.pop('axes', set())
			self.masters = kwargs.pop('masters', set())
			self.instances = kwargs.pop('instances', set())

			# - Features
			self.features =  kwargs.pop('features', [])
			self.classes =  kwargs.pop('classes', [])

			# - Metrics and kern
			self.kerning = kwargs.pop('kerning', [])
		
	# !!! NOTE: Currently operates as list... 
	# !!! NOTE: In future consider reimplementing it as dict, so that font.glyphs[glyph_name] is possible.
	# !!! NPTE: Will requere making a custom dict in the way Container is implemented but based on MutableMapping.

	# -- Internals ------------------------------
	def __repr__(self):
		return '<{}: Name={}, Layers={}, Glyphs={}>'.format(self.__class__.__name__, self.name, self.masters, len(self.glyphs))

	# -- Properties -----------------------------
	@property
	def name(self):
		return self.info.familyName

	@property
	def glyphs(self):
		return self.data

	@property
	def selected_glyphs(self):
		return [glyph for glyph in self.glyphs if glyph.selected]

	# - Functions -------------------------------
	def get_marks(self, search_marks):
		if not isinstance(search_marks, (tuple, list)):
			search_marks = tuple(search_marks)

		return [glyph for glyph in self.glyphs if glyph.mark in search_marks]

	def get_unicodes(self, search_unicodes):
		if not isinstance(search_unicodes, (tuple, list)):
			search_unicodes = tuple(search_unicodes)

		return [glyph for glyph in self.glyphs if glyph.unicode in search_unicodes]

	# -- IO Format ------------------------------
	def to_VFJ(self):
		raise NotImplementedError

	@staticmethod
	def from_VFJ(string):
		raise NotImplementedError

	@staticmethod
	def to_XML(self):
		raise NotImplementedError

	@staticmethod
	def from_XML(string):
		raise NotImplementedError


if __name__ == '__main__':
	from pprint import pprint
	section = lambda s: '\n+{0}\n+ {1}\n+{0}'.format('-'*30, s)

	test = [(200.0, 280.0),
			(760.0, 280.0),
			(804.0, 280.0),
			(840.0, 316.0),
			(840.0, 360.0),
			(840.0, 600.0),
			(840.0, 644.0),
			(804.0, 680.0),
			(760.0, 680.0),
			(200.0, 680.0),
			(156.0, 680.0),
			(120.0, 644.0),
			(120.0, 600.0),
			(120.0, 360.0),
			(120.0, 316.0),
			(156.0, 280.0)]

	l = Layer([[test]], name='Regular')
	g = Glyph([l, [[test]]], name='Vassil')
	f = Font([g], name='Test')
	print(f)


	





	
	
