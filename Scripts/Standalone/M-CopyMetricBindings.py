#FLM: TypeRig - Copy Metric Bindings
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont, pGlyph

# - Init --------------------------------
app_version = '0.01'
app_name = 'Copy Metric Bindings'
mark = 'Green'
fixedLayer = None

srcGlyphBounds = {}

# - Interface -----------------------------
class dlg_copyMetricBinding(QtGui.QDialog):
	def __init__(self):
		super(dlg_copyMetricBinding, self).__init__()
	
		# - Init
		self.btn_copy = QtGui.QPushButton('&Copy Bindings')
		self.btn_paste = QtGui.QPushButton('&Paste Bindings')
		self.btn_export = QtGui.QPushButton('&Export Bindings')
		self.btn_import = QtGui.QPushButton('&Import Bindings')
		
		self.btn_copy.clicked.connect(self.copy)
		self.btn_paste.clicked.connect(self.paste)
		
		self.btn_paste.setEnabled(False)
		self.btn_export.setEnabled(False)
		self.btn_import.setEnabled(False)
				
		# -- Build layouts -------------------------------
		layoutV = QtGui.QVBoxLayout() 
		layoutV.addWidget(self.btn_copy)
		layoutV.addWidget(self.btn_paste)
		layoutV.addWidget(self.btn_export)
		layoutV.addWidget(self.btn_import)

		# - Set Widget -------------------------------
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 200, 300)
		self.show()

	def copy(self):
		font = pFont()
		srcGlyphBounds = {glyph.name:(glyph.layer(fixedLayer).metricsLeft, glyph.layer(fixedLayer).metricsRight, glyph.layer(fixedLayer).metricsWidth) for glyph in font.pGlyphs()}
		print 'COPY:\t %s Glyph Metric Expressions copied.' %len(srcGlyphBounds.keys())
		self.btn_paste.setEnabled(True)

	def paste(self):
		font = pFont()
		dstGlyphs = {glyph.name:glyph for glyph in font.pGlyphs()}

		for glyphName, glyphMetrics in srcGlyphBounds.iteritems():
			try:
				wGlyph = dstGlyphs[glyphName]
				wGlyph.setLSBeq(glyphMetrics[0], fixedLayer)
				wGlyph.setRSBeq(glyphMetrics[1], fixedLayer)
				wGlyph.setADVeq(glyphMetrics[2], fixedLayer)
				wGlyph.update()
				print 'PASTE:\t Glyph /%s metric equations set to %s.' %(glyphName, glyphMetrics)
			
			except KeyError:
				pass


	
	
# - RUN ------------------------------
dialog = dlg_copyMetricBinding()