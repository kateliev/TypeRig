#FLM: TR: Copy Glyph Anchors
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
app_version = '0.01'
app_name = 'Copy Glyph Anchors'
fixedLayer = None

# - Interface -----------------------------
class dlg_copyGlyphAnchors(QtGui.QDialog):
	def __init__(self):
		super(dlg_copyGlyphAnchors, self).__init__()
	
		# - Init
		self.srcGlyphAnchors = {}

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

		self.cmb_flag.insertItem(0, 'None')
		self.cmb_flag.setCurrentIndex(0)

		# - Buttons 
		self.btn_copy = QtGui.QPushButton('&Copy Glyph Anchors')
		self.btn_paste = QtGui.QPushButton('&Paste Glyph Anchors')
		self.btn_export = QtGui.QPushButton('&Export Anchors to File')
		self.btn_import = QtGui.QPushButton('&Import Anchors from File')
		
		self.btn_copy.clicked.connect(self.copyAnchor)
		self.btn_paste.clicked.connect(self.pasteAnchor)
		self.btn_export.clicked.connect(self.exportAnchor)
		self.btn_import.clicked.connect(self.importAnchor)
		
		self.btn_paste.setEnabled(False)
		#self.btn_export.setEnabled(False)
		#self.btn_import.setEnabled(False)
				
		# - Build layouts 
		layoutV = QtGui.QVBoxLayout() 
		layoutV.addWidget(QtGui.QLabel('Copy/Paste Glyph Anchors to/from:'))
		layoutV.addWidget(self.cmb_mode)
		layoutV.addWidget(QtGui.QLabel('Mark modified glyphs with:'))
		layoutV.addWidget(self.cmb_flag)
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

	def copyAnchor(self):
		font = pFont()
		
		if self.cmb_mode.currentIndex == 1:
			self.srcGlyphAnchors = {}

			for glyph in font.pGlyphs():
				current_masters = glyph.masters()

				if len(current_masters):
					layer_anchors = {}
					
					for layer in current_masters:
						current_anchors = layer.anchors
						
						if len(current_anchors):
							layer_anchors[layer.name] = [(anchor.name, (int(anchor.point.x()), int(anchor.point.y()))) for anchor in current_anchors]
						
					
					if len(layer_anchors.keys()):
						self.srcGlyphAnchors[glyph.name] = layer_anchors

			print 'COPY MM:\t Font:%s; Glyph Anchors copied: %s.' %(font.name,len(self.srcGlyphAnchors.keys()))
		else:
			self.srcGlyphAnchors = {glyph.name:[(anchor.name, (int(anchor.point.x()), int(anchor.point.y()))) for anchor in glyph.anchors(fixedLayer)] for glyph in font.pGlyphs() if len(glyph.anchors(fixedLayer))}
			print 'COPY:\t Font:%s; Glyph Anchors copied: %s.' %(font.name,len(self.srcGlyphAnchors.keys()))
		
		self.btn_paste.setEnabled(True)
		
	def pasteAnchor(self):
		font = pFont()
		dst_glyphs = {glyph.name:glyph for glyph in font.pGlyphs()}
		
		print 'WARN:\t Pasting Glyph Anchors to Font:%s;' %font.name
		for glyph_name, layer_anchors in self.srcGlyphAnchors.iteritems():
			if glyph_name in dst_glyphs:
				w_glyph = dst_glyphs[glyph_name]

				if self.cmb_mode.currentIndex == 1:
					# - All master layers
					for layer in w_glyph.masters():
						if layer_anchors.has_key(layer.name):
							w_glyph.clearAnchors(layer.name)
						
							for anchor_name, anchor_pos in layer_anchors[layer.name]:
								w_glyph.addAnchor(anchor_pos, anchor_name, layer.name)

							print 'PASTE MM:\t Glyph: /%s;\tLayer: %s.' %(glyph_name, layer.name)
						else:
							print 'WARN:\t Glyph /%s - Layer %s not found!' %(glyph_name, layer.name)
				else:
					# - Active Layer only
					w_glyph.clearAnchors()
					
					for anchor_name, anchor_pos in layer_anchors:
						w_glyph.addAnchor(anchor_pos, anchor_name)

					print 'PASTE:\t Glyph: /%s;\tLayer: %s.' %(glyph_name, w_glyph.layer().name)

				if self.cmb_flag.currentText != 'None':
					w_glyph.setMark(QtGui.QColor(self.cmb_flag.currentText).hue())

			else:
				print 'SKIP:\t Glyph /%s not found.' %glyph_name

		fl6.Update(CurrentFont())

	def exportAnchor(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Metric Anchoressions to file', fontPath , '*.json')
		
		self.copyAnchor()
		print 'EXPORT:\t Font:%s; Glyph Anchors found: %s.' %(font.name, len(self.srcGlyphAnchors.keys()))
		
		with open(fname, 'w') as exportFile:
			json.dump(self.srcGlyphAnchors, exportFile)

		print 'SAVE:\t Font:%s; %s Glyph Anchors saved to %s.' %(font.name, len(self.srcGlyphAnchors.keys()), fname)

	def importAnchor(self):
		font = pFont()
		fontPath = os.path.split(font.fg.path)[0]

		fname = QtGui.QFileDialog.getOpenFileName(self, 'Open Glyph Anchors from file', fontPath, '*.json')
		
		with open(fname, 'r') as importFile:
			self.srcGlyphAnchors = json.load(importFile)

		print 'LOAD:\t Font:%s; %s Glyph Anchors loaded from %s.' %(font.name, len(self.srcGlyphAnchors.keys()), fname)
		print 'NOTE:\t Use < Paste Anchors > to apply loaded!'
		self.btn_paste.setEnabled(True)
	
# - RUN ------------------------------
dialog = dlg_copyGlyphAnchors()