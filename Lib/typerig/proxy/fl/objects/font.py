# MODULE: Typerig / Proxy / Font (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import json
import json.scanner

import FL as legacy
import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.core.objects.collection import treeDict
from typerig.core.objects.collection import extBiDict
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph

# - Init ---------------------------------
__version__ = '0.28.3'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Classes -------------------------------
class pFontMetrics(object):
	'''
	An Abstract Font Metrics getter/setter of a flPackage.

	Constructor:
		pFontMetrics() - default represents the current glyph and current font
		pFontMetrics(flPackage)
	
	'''
	def __init__(self, font):
		self.fl = font
		
	# - Getters
	def getAscender (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.ascender_value

	def getCapsHeight (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.capsHeight_value

	def getDescender (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.descender_value

	def getLineGap (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.lineGap_value

	def getUpm (self, layer=None):
		return self.fl.upm

	def getXHeight (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.xHeight_value

	def getItalicAngle (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.italicAngle_value

	def getCaretOffset (self, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		return self.fl.caretOffset_value

	'''
	cornerTension_value
	curveTension_value
	inktrapLen_value
	measurement_value
	underlinePosition_value
	underlineThickness_value
	'''

	# - Setters
	def setAscender (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.ascender_value = value

	def setCapsHeight (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.capsHeight_value = value

	def setDescender (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.descender_value = value

	def setLineGap (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.lineGap_value = value

	def setUpm(self, value, scale=False):
		self.fl.setUpm(value, scale)

	def setXHeight (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.xHeight_value = value

	def setItalicAngle (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.italicAngle_value = value

	def setCaretOffset (self, value, layer=None):
		if layer is not None:
			self.fl.setMaster(layer)
		self.fl.caretOffset_value = value

	# - Export & Import
	def asDict(self, layer=None):
		# - Genius!!!!
		getterFunctions = [func for func in dir(self) if callable(getattr(self, func)) and not func.startswith("__") and 'get' in func]
		return {getter.replace('get',''):getattr(self, getter)(layer) for getter in getterFunctions} 

	def fromDict(self, metricDict, layer=None):
		for func, value in metricDict.iteritems():
			eval("self.set{}({}, '{}')".format(func, value, layer))


class pMaster(treeDict):
	def __init__(self, *args, **kwargs):
		super(pMaster, self).__init__(*args)
		self.name = kwargs.get('name', None)

	def __repr__(self):
		return '<{} name={}; axes={}>'.format(self.__class__.__name__, self.name, '; '.join(self.keys()).replace('name',''))


class pMasters(object):
# -- Aliasing some master related commands in common group
	def __init__(self, parent):
		self.parent = parent
		self.add = self.parent.fl.addMaster
		self.clear = self.parent.fl.clearMasters
		self.container = self.parent.fl.mastersContainer
		self.count = self.parent.fl.mastersCount
		self.default = self.parent.fl.defaultMaster
		self.has = self.parent.fl.hasMaster
		self.isActive = self.parent.fl.can_interpolate
		self.location = self.parent.fl.location
		self.names = self.parent.fl.masters
		self.remove = self.parent.fl.removeMaster
		self.rename = self.parent.fl.renameMaster
		self.setActive = self.parent.fl.set_interpolate
		self.setLocation = self.parent.fl.setLocation
		self.setMaster = self.parent.fl.setMaster

	def locate(self, master_name, axes_list=None):
		axes_list = axes_list if axes_list is not None else self.parent.pDesignSpace.axes_list
		master_location = self.location(master_name)
		location_list = []

		for axis in axes_list:
			location_list.append((axis.tag.lower(), (axis.valueWeight(master_location, 0.), axis.valueWidth(master_location, 0.))))

		return pMaster(location_list, name=master_name)

	def locateAxis(self, master_name, axis_tag, width=False):
		axes_dict = self.parent.pDesignSpace.axes_dict
		if not axes_dict.has_key(axis_tag): return
		selected_axis = axes_dict[axis_tag]
		
		master_location = self.location(master_name)
		master_weight = selected_axis.valueWeight(master_location, 0.)
		master_width = selected_axis.valueWidth(master_location, 0.)

		master_neighbors = [pMaster([(selected_axis.tag.lower(), (master_weight, master_width))], name=master_name)]

		for name in self.names:
			if name != master_name:
				temp_location = self.location(name)
				temp_weight = selected_axis.valueWeight(temp_location, 0.)
				temp_width = selected_axis.valueWidth(temp_location, 0.)
				if (temp_width == master_width, temp_weight == master_weight)[width]:
					master_neighbors.append(pMaster([(selected_axis.tag.lower(), (temp_weight, temp_width))], name=name))

		return selected_axis, sorted(master_neighbors, key=lambda m: m[axis_tag])

	def groupByWidth(self, double=0.):
		master_dict = {}
		axes_dict = {}

		for axis_name, axis in self.parent.pDesignSpace.axes_dict.items():
			for name in self.names:
				temp_location = self.location(name)
				temp_weight = axis.valueWeight(temp_location, double)
				temp_width = axis.valueWidth(temp_location, double)
				#master_storage.append((name, temp_weight, temp_width, temp_location))
				master_dict.setdefault(temp_width, []).append((name, temp_weight))

			axes_dict[axis_name] = {key:set(sorted(value, key=lambda i:i[1])) for key, value in master_dict.items()}

		return axes_dict

	@property
	def masters(self):
		return [self.locate(master_name) for master_name in self.names]

	def __repr__(self):
		return '<{} masters={}>'.format(self.__class__.__name__, '; '.join(self.names))


class pDesignSpace(object):
# -- Aliasing some axis related commands
	def __init__(self, parent):
		self.parent = parent
		self.add = parent.fl.addAxis
		self.prepare = parent.fl.prepareAxes
		
	def __repr__(self):
		return '<{} axes={}>'.format(self.__class__.__name__, '; '.join([axis.name for axis in self.axes_list]))

	@property		
	def axes(self):
		return treeDict([(axis.tag, axis) for axis in self.axes_list])

	@property
	def axes_list(self):
		return self.parent.fl.axes

	@property
	def axes_dict(self):
		return {axis.tag: axis for axis in self.parent.fl.axes}


class pFont(object):
	'''
	A Proxy Font representation of Fonlab fgFont and flPackage.

	Constructor:
		pFont(None) : Default represents the current glyph and current font
		pFont(fgFont) : Creates a pFont object from FontGate fgFont object
		pFont(file_path) : Loats a existing font form file_path (str) and creates a pFont object
	
	'''

	def __init__(self, font=None):

		if font is not None:
			if isinstance(font, fgt.fgFont):
				self.fg = font
				self.fl = fl6.flPackage(font)

			elif isinstance(font, basestring):
				fl6.flItems.requestLoadingFont(font)
				self.fg = fl6.CurrentFont()
				self.fl = fl6.flPackage(fl6.CurrentFont())
			
		else:
			self.fg = fl6.CurrentFont()
			self.fl = fl6.flPackage(fl6.CurrentFont())

		# - Special 
		self.__altMarks = {'liga':'_', 'alt':'.', 'hide':'__'}
		self.__diactiricalMarks = ['grave', 'dieresis', 'macron', 'acute', 'cedilla', 'uni02BC', 'circumflex', 'caron', 'breve', 'dotaccent', 'ring', 'ogonek', 'tilde', 'hungarumlaut', 'caroncomma', 'commaaccent', 'cyrbreve'] # 'dotlessi', 'dotlessj'
		self.__specialGlyphs = ['.notdef', 'CR', 'NULL', 'space', '.NOTDEF']
		self.__kern_group_type = {'L':'KernLeft', 'R':'KernRight', 'B': 'KernBothSide'}
		self.__kern_pair_mode = ('glyphMode', 'groupMode')
		
		# -- Design space related 
		self.pMastersContainer = pMasters(self)
		self.pDesignSpace = pDesignSpace(self)
		self.pMasters = self.pMastersContainer
		self.pSpace = self.pDesignSpace
		
	def __repr__(self):
		return '<{} name={} glyphs={} path={}>'.format(self.__class__.__name__, self.fg.info.familyName, len(self.fg), self.fg.path)

	# - Properties ----------------------------------------------
	# -- Basics -------------------------------------------------
	@property
	def italic_angle(self):
		return self.getItalicAngle()
	
	@property
	def info(self):
		return self.fg.info
	
	@property
	def familyName(self):
		return self.fl.tfn
	
	@property
	def name(self):
		return self.familyName 
	
	@property
	def OTfullName(self):
		return self.info.openTypeNameCompatibleFullName
	
	@property
	def PSfullName(self):
		return self.info.postscriptFullName
	
	@property
	def path(self):
		return self.fg.path

	@property
	def ps_stems(self):
		return self.fl.stems(0, True)

	@property
	def tt_stems(self):
		return self.fl.stems(1, True)
	

	# Functions ---------------------------------------------------
	# - Font Basics -----------------------------------------------
	def getSelectedIndices(self):
		# WARN: Legacy syntax used, as of current 6722 build there is no way to get the selected glyphs in editor
		return [index for index in range(len(legacy.fl.font)) if legacy.fl.Selected(index)]

	def setSelectedIndices(self, indList):
		# WARN: Legacy syntax used, as of current 6722 build there is no way to get the selected glyphs in editor
		for index in indList:
			legacy.fl.Select(index)

	def selectGlyphs(self, glyphNameList):
		for glyphName in glyphNameList:
			if self.fg.has_key(glyphName):
				legacy.fl.Select(self.fg[glyphName].index)

	def unselectAll(self):
		legacy.fl.Unselect()

	def selected_pGlyphs(self):
		'''Return TypeRig proxy glyph object for each selected glyph'''
		selection = self.getSelectedIndices()
		return self.pGlyphs(self.selectedGlyphs()) if len(selection) else []

	def selectedGlyphs(self, extend=None):
		'''Return TypeRig proxy glyph object for each selected glyph'''
		selection = self.getSelectedIndices()
		return self.glyphs(selection, extend) if len(selection) else []
		
	def glyph(self, glyph, extend=None):
		'''Return TypeRig proxy glyph object (pGlyph) by index (int) or name (str).'''
		if isinstance(glyph, int) or isinstance(glyph, basestring):
			return pGlyph(self.fg, self.fg[glyph]) if extend is None else extend(self.fg, self.fg[glyph])
		else:
			return pGlyph(self.fg, glyph) if extend is None else extend(self.fg, self.fg[glyph])

	def symbol(self, gID):
		'''Return fgSymbol by glyph index (int)'''
		return fl6.fgSymbol(gID, self.fg)

	def glyphs(self, indexList=[], extend=None):
		'''Return list of FontGate glyph objects (list[fgGlyph]).'''
		if extend is None:
			return self.fg.glyphs if not len(indexList) else [self.fg.glyphs[index] for index in indexList]
		else:
			if not len(indexList):
				return [extend(glyph, self.fg) for glyph in self.fg.glyphs]
			else:
				return [extend(glyph, self.fg) for glyph in [self.fg.glyphs[index] for index in indexList]]

	def symbols(self):
		'''Return list of FontGate symbol objects (list[fgSymbol]).'''
		return [self.symbol(gID) for gID in range(len(self.fg.glyphs))]
	
	def pGlyphs(self, fgGlyphList=[]):
		'''Return list of TypeRig proxy Glyph objects glyph objects (list[pGlyph]).'''
		return [self.glyph(glyph) for glyph in self.fg] if not len(fgGlyphList) else [self.glyph(glyph) for glyph in fgGlyphList]

	def findShape(self, shapeName, master=None, deep=True):
		'''Search for element (flShape) in font and return it'''
		for glyph in self.pGlyphs():
			if glyph.layer(master) is not None:
				foundShape = glyph.findShape(shapeName, master, deep=deep)
				if foundShape is not None:
					return foundShape
	
	def hasGlyph(self, glyphName):
		return self.fg.has_key(glyphName)

	# - Font metrics -----------------------------------------------
	def getItalicAngle(self):
		return self.fl.italicAngle_value

	def fontMetricsInfo(self, layer):
		'''Returns Font(layer) metrics no matter the reference.
		Args:
			layer (int or str): Layer index or name. If None returns ActiveLayer
		Returns:
			FontMetrics (object)
		'''
		if isinstance(layer, int):
			return fl6.FontMetrics(self.fl, self.fl.masters[layer]) 

		elif isinstance(layer, basestring):
			return fl6.FontMetrics(self.fl, layer)

	def fontMetrics(self):
		'''Returns pFontMetrics Object with getter/setter functionality'''
		return pFontMetrics(self.fl)

	def updateObject(self, flObject, undoMessage='TypeRig', verbose=True):
		'''Updates a flObject sends notification to the editor as well as undo/history item.
		Args:
			flObject (flGlyph, flLayer, flShape, flNode, flContour): Object to be update and set undo state
			undoMessage (string): Message to be added in undo/history list.
		'''
		fl6.flItems.notifyChangesApplied(undoMessage, flObject, True)
		fl6.flItems.notifyPackageContentUpdated(self.fl.fgPackage.id)
		if verbose: print('DONE:\t{}'.format(undoMessage))

	def update(self):
		self.updateObject(self.fl, verbose=False)

	# - Hinting --------------------------------------------------------
	def setStem(self, stem_value, stem_name='', stem_is_horizontal=False, stem_type_TT=False):
		new_stem = fl6.flStem(stem_value, stem_name)
		
		if stem_type_TT:
			if stem_is_horizontal:
				self.fl.tt_stemsH = self.fl.tt_stemsH + [new_stem]
			else:
				self.fl.tt_stemsV = self.fl.tt_stemsV + [new_stem]
		else:
			if stem_is_horizontal:
				self.fl.ps_stemsH = self.fl.ps_stemsH + [new_stem]
			else:
				self.fl.ps_stemsV = self.fl.ps_stemsV + [new_stem]

		return new_stem

	def resetStems(self, stems_horizontal=False, type_TT=False):
		if type_TT:
			if stems_horizontal:
				self.fl.tt_stemsH = []
			else:
				self.fl.tt_stemsV = []
		else:
			if stems_horizontal:
				self.fl.ps_stemsH = []
			else:
				self.fl.ps_stemsV = []

	# - Axes and MM ----------------------------------------------------
	def axes(self):
		return self.fl.axes

	def masters(self):
		return self.fl.masters

	def hasMaster(self, layerName):
		return self.fl.hasMaster(layerName)

	def instances(self):
		return self.fl.instances

	# - Guides & Hinting Basics ----------------------------------------
	def guidelines(self, hostInf=False, fontgate=False):
		'''Return font guidelines
		Args:
			hostInf (bool): If True Return flHostInfo guidelines host objects
			fontgate (bool): If True return FontGate font guideline objects
		Returns
			list[flGuideline] or list[fgGuideline]
		'''
		if not fontgate:
			return self.fl.guidelines if not hostInf else self.fl.guidelinesHost.guidelines
		else:
			return self.fg.guides

	def addGuideline(self, flGuide):
		'''Adds a guideline (flGuide) to font guidelines'''
		self.fl.guidelinesHost.appendGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def delGuideline(self, flGuide):
		'''Removes a guideline (flGuide) from font guidelines'''
		self.fl.guidelinesHost.removeGuideline(flGuide)
		self.fl.guidelinesHost.guidelinesChanged()

	def clearGuidelines(self):
		'''Removes all font guidelines'''
		self.fl.guidelinesHost.clearGuidelines()
		self.fl.guidelinesHost.guidelinesChanged()

	def getZones(self, layer=None, HintingDataType=0):
		'''Returns font alignment (blue) zones (list[flGuideline]). Note: HintingDataType = {'HintingPS': 0, 'HintingTT': 1}'''
		backMasterName = self.fl.master
		if layer is not None: self.fl.setMaster(layer)
		zoneQuery = (self.fl.zones(HintingDataType, True), self.fl.zones(HintingDataType, False)) # tuple(top, bottom) zones
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)	
		return zoneQuery

	def setZones(self, fontZones, layer=None):
		backMasterName = self.fl.master

		if layer is not None: self.fl.setMaster(layer)
		self.fl.convertZonesToGuidelines(*fontZones) # Dirty register zones	
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)

		self.update()

	def zonesToTuples(self, layer=None, HintingDataType=0):
		fontZones = self.getZones(layer, HintingDataType)
		return [(zone.position, zone.width, zone.name) for zone in fontZones[0]] + [(zone.position, -zone.width, zone.name) for zone in fontZones[1]]

	def zonesFromTuples(self, zoneTupleList, layer=None, forceNames=False):
		fontZones = ([], [])

		for zoneData in zoneTupleList:
			isTop = zoneData[1] >= 0
			newZone = fl6.flZone(zoneData[0], abs(zoneData[1]))
			
			if forceNames and len(zoneData) > 2: newZone.name = zoneData[2]
			newZone.guaranteeName(isTop)
			
			fontZones[not isTop].append(newZone)

		if not len(fontZones[1]):
			fontZones[1].append(fl6.flZone())

		self.setZones(fontZones, layer)

	def addZone(self, position, width, layer=None):
		''' A very dirty way to add a new Zone to Font'''
		isTop = width >= 0
		backMasterName = self.fl.master
		fontZones = self.getZones(layer)
		
		newZone, killZone = fl6.flZone(position, abs(width)), fl6.flZone()
		newZone.guaranteeName(isTop)

		fontZones[not isTop].append([newZone, killZone][not isTop])
		fontZones[isTop].append([newZone, killZone][isTop])
				
		if layer is not None: self.fl.setMaster(layer)
		self.fl.convertZonesToGuidelines(*fontZones)
		if self.fl.master != backMasterName: self.fl.setMaster(backMasterName)	

		self.update()
		
	def hinting(self):
		'''Returns fonts hinting'''
		return self.fg.hinting

	# - Charset -----------------------------------------------
	# -- Return Names
	def getGlyphNames(self):
		return [glyph.name for glyph in self.glyphs()]

	def getGlyphNameDict(self):
		# -- Init
		nameDict = {}

		# --- Controls and basic latin: 0000 - 0080
		nameDict['Latin_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin 1 Supplement: 0080 - 00FF
		nameDict['Latin1_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin1_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin A: unicode range 0100 - 017F
		nameDict['LatinA_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinA_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin B: unicode range 0180 - 024F
		nameDict['LatinB_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinB_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Cyrillic: unicode range 0400 - 04FF
		nameDict['Cyrillic_Upper'] = [self.fl.findUnicode(uni).name for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Cyrillic_Lower'] = [self.fl.findUnicode(uni).name for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]
		
		return nameDict

	def getGlyphUnicodeDict(self, encoding='utf-8'):
		# -- Init
		nameDict = {}

		# --- Controls and basic latin: 0000 - 0080
		nameDict['Latin_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0000, 0x0080) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin 1 Supplement: 0080 - 00FF
		nameDict['Latin1_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Latin1_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0080, 0x00FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin A: unicode range 0100 - 017F
		nameDict['LatinA_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinA_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0100, 0x017F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Latin B: unicode range 0180 - 024F
		nameDict['LatinB_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['LatinB_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0180, 0x024F) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]

		# --- Cyrillic: unicode range 0400 - 04FF
		nameDict['Cyrillic_Upper'] = [unichr(uni).encode(encoding) for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).isupper()]
		nameDict['Cyrillic_Lower'] = [unichr(uni).encode(encoding) for uni in range(0x0400, 0x04FF) if isinstance(self.fl.findUnicode(uni), fl6.flGlyph) and unichr(uni).islower()]
		
		return nameDict	
	
	# -- Return Glyphs
	def uppercase(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isupper()] # Skip Private ranges - glyph.unicode < 10000

	def lowercase(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).islower()]		

	def figures(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and unichr(glyph.unicode).isdigit()]	

	def symbols(self, namesOnly=False):
		'''Returns all uppercase characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if glyph.unicode is not None and glyph.unicode < 10000 and not unichr(glyph.unicode).isdigit() and not unichr(glyph.unicode).isalpha()]

	def ligatures(self, namesOnly=False):
		'''Returns all ligature characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if self.__altMarks['liga'] in glyph.name and not self.__altMarks['hide'] in glyph.name and glyph.name not in self.__specialGlyphs]

	def alternates(self, namesOnly=False):
		'''Returns all alternate characters (list[fgGlyph])'''
		return [glyph if not namesOnly else glyph.name for glyph in self.fg if self.__altMarks['alt'] in glyph.name and not self.__altMarks['hide'] in glyph.name and glyph.name not in self.__specialGlyphs]

	# - Glyph generation ------------------------------------------
	def addGlyph(self, glyph):
		'''Adds a Glyph (fgGlyph or flGlyph) to font'''
		if isinstance(glyph, fgt.fgGlyph):
			glyph = fl6.flGlyph(glyph)
		
		self.fl.addGlyph(glyph)

	def addGlyphList(self, glyphList):
		'''Adds a List of Glyphs [fgGlyph or flGlyph] to font'''
		for glyph in glyphList:
			self.addGlyph(glyph)

	def newGlyph(self, glyph_name, layers=[], unicode_int=None):
		'''Creates new glyph and adds it to the font
		Args:
			glyph_name (str): New glyph name
			layers (list(str) or list(flLayer)): List of layers to be added to the new glyph
			unicode_int (int): Unicode int of the new glyph
		Returns:
			pGlyph
		'''

		# - Build
		base_glyph = fl6.flGlyph()
		base_glyph.name = glyph_name
		self.addGlyph(base_glyph)

		# - Get the newly added glyph (all sane methods exhausted)
		new_glyph = self.glyph(glyph_name)

		# - Set Unicode
		if unicode_int is not None: new_glyph.fg.setUnicode(unicode_int)
		
		# - Add layers
		if len(layers):
			for layer in layers:
				if isinstance(layer, basestring):
					new_layer = fl6.flLayer()
					new_layer.name = layer
					new_glyph.addLayer(new_layer)
				
				elif isinstance(layer, fl6.flLayer):
					new_glyph.addLayer(layer)

		# - Add to font
		return new_glyph

	def newGlyphFromRecipe(self, glyph_name, recipe, layers=[], unicode_int=None, rtl=False):
		''' Generate new glyph (glyph_name) using String Recipe (recipe)
		Args:
			glyph_name (str): New glyph name
			recipe (str): Glyph composition recipe using OLD Fontlab syntax (ex. A+acute=Aacute)
			layers (list(str)): List of layer names to be added
			unicode_int (int): Unicode int of the new glyph
			rtl (bool): Right to left
		Returns:
			pGlyph
		'''		
		
		# - Prepare
		advanceWidth = 0 #!!! Figure it out later
		prepared_layers = []

		for layer_name in layers:
			layer_fontMetrics = fl6.FontMetrics(self.fl, layer_name)
			new_layer = fl6.flLayer(layer_name)
			gen_component = self.fl.generateGlyph(recipe, layer_name, layer_fontMetrics, rtl)
			new_layer.setGlyphComponents(gen_component, advanceWidth, self.fl, True)
			prepared_layers.append(new_layer)

		new_glyph = self.newGlyph(glyph_name, prepared_layers, unicode_int)
		return new_glyph

	def duplicateGlyph(self, src_name, dst_name, dst_unicode=None, options={'out': True, 'gui': True, 'anc': True, 'lsb': True, 'adv': True, 'rsb': True, 'lnk': True, 'ref': True, 'flg': True, 'tag': True}):
		'''Duplicates a glyph and adds it to the font
		Args:
			src_name, dst_name (str): Source and destination names
			dst_unicode (int): Unicode int of the new glyph
			references (bool): Keep existing element references (True) or decompose (False)
		Returns:
			pGlyph
		'''
		# - Init
		src_glyph = self.glyph(src_name)
		
		# - Copy Layer data
		prepared_layers = []

		for layer in src_glyph.layers():
			new_layer = src_glyph.copyLayer(layer.name, layer.name + '.duplicate', options, False, False, True)
			new_layer.name = new_layer.name.replace('.duplicate', '')
			prepared_layers.append(new_layer)

		new_glyph = self.newGlyph(dst_name, prepared_layers, dst_unicode)

		# - Copy Glyph specific stuff
		if options['tag']: new_glyph.tags = src_glyph.tags # Copy tags
		if options['flg']: new_glyph.mark = src_glyph.mark # Copy glyph flag/mark

		return new_glyph

	# - OpenType and features -------------------------------------
	def getFeatures(self):
		return self.fg.features

	def clearFeatures(self):
		return self.fg.features.clear()

	def getFeatureTags(self):
		return self.fg.features.keys()

	def getFeaPrefix(self):
		return self.fg.features.get_prefix()

	def setFeaPrefix(self, feaString):
		return self.fg.features.get_prefix(feaString)

	def hasFeature(self, tag):
		return self.fg.features.has_key(tag)

	def getFeature(self, tag):
		return self.fg.features.get_feature(tag)

	def setFeature(self, tag, feaString):
		return self.fg.features.set_feature(tag, feaString)

	def delFeature(self, tag):
		return self.fg.features.remove(tag)

	def newOTgroup(self, groupName, glyphList):
		return fgt.fgGroup(groupName, glyphList,'FeaClassGroupMode', 'mainglyphname')

	def addOTgroup(self, groupName, glyphList):
		temp_groups = self.fg.groups.asDict()
		new_group = self.newOTgroup(groupName, glyphList)
		temp_groups[groupName] = new_group
		self.fg.groups.fromDict(temp_groups)

	def getOTgroups(self):
		return self.fg.groups

	# - Kerning and Groups -------------------------------------
	def kerning(self, layer=None):
		'''Return the fonts kerning object (fgKerning) no matter the reference.'''
		if layer is None:
			return self.fl.kerning()
		else:
			if isinstance(layer, int):
				return self.fl.kerning(self.masters[layer])

			elif isinstance(layer, basestring):
				return self.fl.kerning(layer)

	def kerning_to_list(self, layer=None):
		# Structure:
		# 	fgKerning{fgKernigPair(fgKerningObject(glyph A, mode), fgKerningObject(glyph B, mode)) : kern value, ...}
		layer_kernig = self.kerning(layer)
		kern_list = []

		for key, value in layer_kernig.asDict().iteritems():
			kern_list.append([[item.asTuple() for item in key.asTuple()], value])

		return kern_list

	def kerning_dump(self, layer=None, mark_groups='@', pairs_only=False):
		'''Dump layer kerning to simple tuples.
		Args:
			layer (None, Int, String): Extract kerning data for layer specified;
			mark_groups (String): Mark group kerning with special symbol
			pairs_only (Bool): Export pairs without value
		
		Returns:
			pairs_only is False:	list(tuple(tuple(str(First), str(Second))), Int(Value)))
			pairs_only is True:		list(tuple(str(First), str(Second)))
		'''
		layer_kernig = self.kerning(layer)
		save_pairs = []

		for kern_pair, value in layer_kernig.items():
			current_pair = kern_pair.asTuple()
			a_tup = current_pair[0].asTuple()
			b_tup = current_pair[1].asTuple()

			a = mark_groups + a_tup[0] if a_tup[1] == 'groupMode' else a_tup[0]
			b = mark_groups + b_tup[0] if b_tup[1] == 'groupMode' else b_tup[0]
			
			if pairs_only:
				save_pairs.append((a, b))
			else:
				save_pairs.append(((a, b), value))

		return save_pairs

	def kerning_groups(self, layer=None):
		'''Return the fonts kerning groups object (fgKerningGroups) no matter the reference.'''
		return self.kerning(layer).groups

	def fl_kerning_groups(self, layer=None):
		return list(filter(lambda x: x[0], self.fl.getAllGroups()))

	def fl_kerning_groups_to_dict(self, layer=None):
		return extBiDict({item[1]: item[-1] for item in self.fl_kerning_groups(layer)})

	def kerning_groups_to_dict(self, layer=None, byPosition=False, sortUnicode=False):
		'''Return dictionary containing kerning groups 
		Args:
			layer (None, Int, String): Extract kerning data for layer specified;
			byPosition (bool): Dictionary by class kerning positions - KernLeft(1st), KernRight(2nd) or KernBothSide(Both);
			sortUnicode (bool): Sort members of kern group according to their Unicode value.
		
		Returns:
			dict
		'''
		kern_groups = self.kerning_groups(layer).asDict()
		if sortUnicode:
			temp_groups = {}
			for groupName, groupData in kern_groups.items():
				temp_groups[groupName] = (sorted(groupData[0], key=lambda glyph_name: self.glyph(glyph_name).unicode), groupData[1])

			kern_groups = temp_groups

		if not byPosition:
			return kern_groups			
		else:
			sortedByPosition = {}
			for groupName, groupData in kern_groups.items():
				sortedByPosition.setdefault(groupData[1], []).append((groupName, groupData[0]))
			return sortedByPosition

	def dict_to_kerning_groups (self, groupDict, layer=None):
		# - Build Group kerning from dictionary
		kerning_groups = self.kerning_groups(layer)
		
		for key, value in groupDict.iteritems():
			kerning_groups[key] = value

	def reset_kerning_groups(self, layer=None):
		# - Delete all group kerning at given layer
		self.kerning_groups(layer).clear()		

	def add_kerning_group(self, key, glyphNameList, type, layer=None):
		'''Adds a new group to fonts kerning groups.
		Args:
			key (string): Group name
			glyphNameList (list(string)): List of glyph names
			type (string): Kern group types: L - Left group (1st), R - Right group (2nd), B - Both (1st and 2nd)
			layer (None, Int, String)
		
		Returns:
			None
		'''
		self.kerning_groups(layer)[key] = (glyphNameList, self.__kern_group_type[type.upper()])

	def remove_kerning_group(self, key, layer=None):
		'''Remove a group from fonts kerning groups at given layer.'''
		del self.kerning_groups(layer)[key]

	def rename_kerning_group(self, oldkey, newkey, layer=None):
		'''Rename a group in fonts kerning groups at given layer.'''
		self.kerning_groups(layer).rename(oldkey, newkey)

	def newKernPair(self, glyphLeft, glyphRight, modeLeft, modeRight):
		if not isinstance(modeLeft, str): modeLeft = self.__kern_pair_mode[modeLeft]
		if not isinstance(modeRight, str): modeRight = self.__kern_pair_mode[modeRight]
		return fgt.fgKerningObjectPair(glyphLeft, glyphRight, modeLeft, modeRight)


# - Extensions ----------------------------
class eFont(pFont):
	'''
	Proxy Font extension, packing some useful tools.

	Constructor:
		eFont() - default represents the current glyph and current font
		eFont(fgFont)
	'''

	def copyZones(self, font):
		if isinstance(font, fgt.fgFont):
			srcFont = pFont(font)
		elif isinstance(font, pFont):
			srcFont = font

		pass # TODO!
		

class jFont(object):
	'''
	Proxy VFJ Font (Fontlab JSON Font format)

	Constructor:
		jFont(): Construct an empty jFont
		jFont(vfj_file_path): Load VFJ form vfj_file_path (STR)
		jFont(pFont): Load VFJ from pFont.path. VFJ Font has to be in the same path as the VFC

	Methods:
		.data(): Access to VFJ font
		.load(file_path): Load VFJ font from path
		.save_as(file_path): Save VFJ font to path
		.save(): Save VFJ (overwrite)
	'''

	def __init__(self, source=None):
		# - Init
		self.data = None
		self.source = None
		self.path = None

		if source is not None:
			if isinstance(source, basestring):
				self.path = source

			elif isinstance(source, pFont):
				self.path = source.path.replace('vfc', 'vfj')
			
			self.load(self.path)

	def load(self, file_path):
		with open(file_path, 'r') as importFile:
			self.data = json.load(importFile, cls=vfj_decoder)
		
		self.path = file_path
		return True

	def save_as(self, file_path):
		with open(file_path, 'w') as exportFile:
			json.dump(self.data, exportFile, cls=vfj_encoder)
		return True

	def save(self):
		return self.save_as(self.path)