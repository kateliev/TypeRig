#FLM: Metrics: Copy Metrics (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont, pGlyph

# - Init --------------------------------
app_version = '0.02'
app_name = 'Copy Metrics'
fixedLayer = None

# - Interface -----------------------------
class dlg_copyMetrics(QtGui.QDialog):
	def __init__(self):
		super(dlg_copyMetrics, self).__init__()
	
		# - Init
		self.srcGlyphBounds = {}

		# - Combos
		# -- Mode of operation
		self.cmb_mode = QtGui.QComboBox()
		self.cmb_mode.addItems(['Active Layer', 'All Master Layers'])

		# -- Flag color slector
		self.cmb_flag = QtGui.QComboBox()
		colorNames = QtGui.QColor.colorNames()

		for i in range(len(colorNames)):
			self.cmb_flag.addItem(colorNames[i])
			self.cmb_flag.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

		self.cmb_flag.setCurrentIndex(colorNames.index('lime'))

		# - Buttons 
		self.btn_copy = QtGui.QPushButton('&Copy Metric values')
		self.btn_paste = QtGui.QPushButton('&Paste Metric values')
		self.btn_export = QtGui.QPushButton('&Export to File')
		self.btn_import = QtGui.QPushButton('&Import from File')
		self.btn_importFLC = QtGui.QPushButton('&Import from .FLC')
		
		self.btn_copy.clicked.connect(self.copyExpr)
		self.btn_paste.clicked.connect(self.pasteExpr)
		self.btn_export.clicked.connect(self.exportExpr)
		self.btn_import.clicked.connect(self.importExpr)
		self.btn_importFLC.clicked.connect(self.importExprFLC)
		
		self.btn_paste.setEnabled(False)
		#self.btn_export.setEnabled(False)
		#self.btn_import.setEnabled(False)
				
		# - Build layouts 
		layoutV = QtGui.QVBoxLayout() 
		layoutV.addWidget(QtGui.QLabel('Copy/Paste metrics to/from:'))
		layoutV.addWidget(self.cmb_mode)
		#layoutV.addWidget(QtGui.QLabel('Mark modified glyphs with:'))
		#layoutV.addWidget(self.cmb_flag)
		layoutV.addWidget(self.btn_copy)
		layoutV.addWidget(self.btn_paste)
		layoutV.addWidget(self.btn_export)
		layoutV.addWidget(self.btn_import)
		layoutV.addWidget(self.btn_importFLC)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 120)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def copyExpr(self):
		font = pFont()
		
		if self.cmb_mode.currentIndex == 1:
			self.srcGlyphBounds = {glyph.name:{layer.name:(glyph.getLSB(layer.name), glyph.getRSB(layer.name), glyph.getAdvance(layer.name)) for layer in glyph.masters()} for glyph in font.pGlyphs()}
			print 'COPY MM:\t Font:%s; Glyph Metric Values copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		else:
			self.srcGlyphBounds = {glyph.name:(glyph.getLSB(fixedLayer), glyph.getRSB(fixedLayer), glyph.getAdvance(fixedLayer)) for glyph in font.pGlyphs()}
			print 'COPY:\t Font:%s; Glyph Metric Values copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		
		self.btn_paste.setEnabled(True)

	def pasteExpr(self):
		font = pFont()
		dstGlyphs = {glyph.name:glyph for glyph in font.pGlyphs()}
		
		print 'WARN:\t Pasting Metrics to Font:%s;' %font.name
		for glyphName, glyphMetrics in self.srcGlyphBounds.iteritems():
			if glyphName in dstGlyphs:
				wGlyph = dstGlyphs[glyphName]

				if self.cmb_mode.currentIndex == 1:
					for layer in wGlyph.masters():
						if glyphMetrics.has_key(layer.name):
							wGlyph.setLSB(glyphMetrics[layer.name][0], layer.name)
							#wGlyph.setRSB(glyphMetrics[layer.name][1], layer.name)
							wGlyph.setAdvance(glyphMetrics[layer.name][2], layer.name)
							wGlyph.update()
							print 'PASTE MM:\t Glyph: /%s;\tLayer: %s;\tValues(LSB, RSB, ADV): %s.' %(glyphName, layer.name, glyphMetrics)
						else:
							print 'WARN:\t Glyph /%s - Layer %s not found!' %glyphName, layerName
				else:
					wGlyph.setLSB(glyphMetrics[0])
					#wGlyph.setRSB(glyphMetrics[1])
					wGlyph.setAdvance(glyphMetrics[2])
					wGlyph.update()
					print 'PASTE:\t Glyph: /%s;\tLayer: %s;\tValues(LSB, RSB, ADV): %s.' %(glyphName, wGlyph.layer().name, glyphMetrics)
			else:
				print 'SKIP:\t Glyph /%s not found.' %glyphName

		fl6.Update(CurrentFont())

	def exportExpr(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Metrics to file', fontPath , '*.json')
		
		if self.cmb_mode.currentIndex == 1:
			expGlyphBounds = {glyph.name:{layer.name:(layer.metricsLeft, layer.metricsRight, layer.metricsWidth) for layer in glyph.masters()} for glyph in font.pGlyphs()}
			print 'EXPORT MM:\t Font:%s; Glyph Metrics found: %s.' %(font.name, len(expGlyphBounds.keys()))
		else:
			expGlyphBounds = {glyph.name:(glyph.layer(fixedLayer).metricsLeft, glyph.layer(fixedLayer).metricsRight, glyph.layer(fixedLayer).metricsWidth) for glyph in font.pGlyphs()}
			print 'EXPORT:\t Font:%s; Glyph Metrics found: %s.' %(font.name, len(expGlyphBounds.keys()))
		
		with open(fname, 'w') as exportFile:
			json.dump(expGlyphBounds, exportFile)

		print 'SAVE:\t Font:%s; %s Glyph Metrics saved to %s.' %(font.name, len(expGlyphBounds.keys()), fname)

	def importExpr(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]

		fname = QtGui.QFileDialog.getOpenFileName(self, 'Open Metrics from file', fontPath, '*.json')
		
		with open(fname, 'r') as importFile:
			self.srcGlyphBounds = json.load(importFile)

		print 'LOAD:\t Font:%s; %s Glyph Metrics loaded from %s.' %(font.name, len(self.srcGlyphBounds.keys()), fname)
		print 'NOTE:\t Use < Pastes > to apply loaded!'
		self.btn_paste.setEnabled(True)

	def importExprFLC(self):
		from typerig.utils import fontClassesFromFile as importFLC
		
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]

		fname = QtGui.QFileDialog.getOpenFileName(self, 'Open Fontlab class file', fontPath, '*.flc')
		
		classesFLC = importFLC(fname)
		print classesFLC.classPosition

		#print 'LOAD:\t Font:%s; %s Glyph Metrics loaded from %s.' %(font.name, len(self.srcGlyphBounds.keys()), fname)
		#print 'NOTE:\t Use < Paste > to apply loaded!'
		#self.btn_paste.setEnabled(True)
	
# - RUN ------------------------------
dialog = dlg_copyMetrics()