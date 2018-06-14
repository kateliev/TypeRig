#FLM: Copy Metric Expressions (TypeRig)
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
app_version = '0.05'
app_name = 'Copy Metric Bindings'
mark = 'Green'
fixedLayer = False

# - Interface -----------------------------
class dlg_copyMetricBinding(QtGui.QDialog):
	def __init__(self):
		super(dlg_copyMetricBinding, self).__init__()
	
		# - Init
		self.srcGlyphBounds = {}

		# - Label
		if fixedLayer:
			self.lbl_decription = QtGui.QLabel('Copy/Paste metric expressions from or to the ACTIVE layer. Export/Import to JSON file format.')
		else:
			self.lbl_decription = QtGui.QLabel('Copy/Paste metric expressions from or to ALL MASTER layers. Export/Import to JSON file format.')
		
		self.lbl_decription.setWordWrap(True)

		# - Buttons 
		self.btn_copy = QtGui.QPushButton('&Copy Expressions')
		self.btn_paste = QtGui.QPushButton('&Paste Expressions')
		self.btn_export = QtGui.QPushButton('&Export to File')
		self.btn_import = QtGui.QPushButton('&Import from File')
		
		self.btn_copy.clicked.connect(self.copyExpr)
		self.btn_paste.clicked.connect(self.pasteExpr)
		self.btn_export.clicked.connect(self.exportExpr)
		self.btn_import.clicked.connect(self.importExpr)
		
		self.btn_paste.setEnabled(False)
		#self.btn_export.setEnabled(False)
		#self.btn_import.setEnabled(False)
				
		# - Build layouts 
		layoutV = QtGui.QVBoxLayout() 
		layoutV.addWidget(self.lbl_decription)
		layoutV.addWidget(self.btn_copy)
		layoutV.addWidget(self.btn_paste)
		layoutV.addWidget(self.btn_export)
		layoutV.addWidget(self.btn_import)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 220, 120)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def copyExpr(self):
		font = pFont()
		
		if not fixedLayer:
			self.srcGlyphBounds = {glyph.name:{layer.name:(layer.metricsLeft, layer.metricsRight, layer.metricsWidth) for layer in glyph.masters()} for glyph in font.pGlyphs()}
			print 'COPY MM:\t Font:%s; Glyph Metric Expressions copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		else:
			self.srcGlyphBounds = {glyph.name:(glyph.layer(fixedLayer).metricsLeft, glyph.layer(fixedLayer).metricsRight, glyph.layer(fixedLayer).metricsWidth) for glyph in font.pGlyphs()}
			print 'COPY:\t Font:%s; Glyph Metric Expressions copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		
		self.btn_paste.setEnabled(True)

	def pasteExpr(self):
		font = pFont()
		dstGlyphs = {glyph.name:glyph for glyph in font.pGlyphs()}
		
		print 'WARN:\t Pasting Metric expressions to Font:%s;' %font.name
		for glyphName, glyphMetrics in self.srcGlyphBounds.iteritems():
			if glyphName in dstGlyphs:
				wGlyph = dstGlyphs[glyphName]

				if not fixedLayer:
					for layerName in wGlyph.masters():
						if glyphMetrics.hasKey(layerName):
							wGlyph.setLSBeq(glyphMetrics[layerName][0], layerName)
							wGlyph.setRSBeq(glyphMetrics[layerName][1], layerName)
							wGlyph.setADVeq(glyphMetrics[layerName][2], layerName)
							wGlyph.update()
							print 'PASTE MM:\t Glyph: /%s;\tLayer: %s;\tExp(LSB, RSB, ADV): %s.' %(glyphName, layerName, glyphMetrics)
						else:
							print 'WARN:\t Glyph /%s - Layer %s not found!' %glyphName, layerName
				else:
					wGlyph.setLSBeq(glyphMetrics[0])
					wGlyph.setRSBeq(glyphMetrics[1])
					wGlyph.setADVeq(glyphMetrics[2])
					wGlyph.update()
					print 'PASTE:\t Glyph: /%s;\tLayer: %s;\tExp(LSB, RSB, ADV): %s.' %(glyphName, wGlyph.layer().name, glyphMetrics)
			else:
				print 'SKIP:\t Glyph /%s not found.' %glyphName

	def exportExpr(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Metric Expressions to file', fontPath , '.json')
		
		if not fixedLayer:
			expGlyphBounds = {glyph.name:{layer.name:(layer.metricsLeft, layer.metricsRight, layer.metricsWidth) for layer in glyph.masters()} for glyph in font.pGlyphs()}
			print 'COPY MM:\t Font:%s; Glyph Metric Expressions copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		else:
			expGlyphBounds = {glyph.name:(glyph.layer(fixedLayer).metricsLeft, glyph.layer(fixedLayer).metricsRight, glyph.layer(fixedLayer).metricsWidth) for glyph in font.pGlyphs()}
			print 'COPY:\t Font:%s; Glyph Metric Expressions copied: %s.' %(font.name,len(self.srcGlyphBounds.keys()))
		
		with open(fname, 'w') as exportFile:
			json.dump(expGlyphBounds, exportFile)

		print 'SAVE:\t Font:%s; %s Glyph Metric Expressions saved to %s.' %(font.name, len(expGlyphBounds.keys()), fname)

	def importExpr(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]

		fname = QtGui.QFileDialog.getOpenFileName(self, 'Open Metric Expressions from file', fontPath)
		
		with open(fname, 'r') as importFile:
			self.srcGlyphBounds = json.load(importFile)

		print 'LOAD:\t Font:%s; %s Glyph Metric Expressions loaded from %s.' %(font.name, len(self.srcGlyphBounds.keys()), fname)
		print 'NOTE:\t Use < Paste Expressions > to apply loaded data to Active layer!'
		self.btn_paste.setEnabled(True)
	
# - RUN ------------------------------
dialog = dlg_copyMetricBinding()