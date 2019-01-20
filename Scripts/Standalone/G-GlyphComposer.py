#FLM: Glyph: Composer (TypeRig)
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy import pFont, pGlyph
from typerig.brain import Coord

# - Init --------------------------------
app_version = '0.5'
app_name = 'Glyph Composer'

# -- Strings 
str_help = 'Help: TODO!'

# -- Syntax
syn_comment = '#'
syn_insert = '->'
syn_label = '!'
syn_anchor = '$'
syn_pos = '@'
syn_transform = '^'
syn_exprbegin = '('
syn_exprend = ')'
syn_coordsep =','
syn_namesep = ' '
syn_currglyph = syn_label + 'glyph'
syn_currnode = syn_label + 'node'
syn_bboxTL = syn_label + 'TL'
syn_bboxTR = syn_label + 'TR'
syn_bboxBL = syn_label + 'BL'
syn_bboxBR = syn_label + 'BR'

# - Dialogs --------------------------------
class dlg_glyphComposer(QtGui.QDialog):
	def __init__(self):
		super(dlg_glyphComposer, self).__init__()
	
		# - Init
		self.active_font = pFont()
		self.class_data = {}
		
		# - Widgets
		self.cmb_layer = QtGui.QComboBox()
		self.cmb_layer.addItems(self.active_font.masters() + ['All masters'])

		self.btn_saveExpr = QtGui.QPushButton('Save')
		self.btn_loadExpr = QtGui.QPushButton('Load')
		self.btn_exec = QtGui.QPushButton('Execute')

		self.btn_exec.clicked.connect(self.process)
		self.btn_saveExpr.clicked.connect(self.expr_toFile)
		self.btn_loadExpr.clicked.connect(self.expr_fromFile)

		self.txt_editor = QtGui.QPlainTextEdit()
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Process font master:'),	2, 0, 1, 2)
		layoutV.addWidget(self.cmb_layer,			2, 2, 1, 2)
		layoutV.addWidget(QtGui.QLabel(str_help),	3, 0, 1, 4)
		layoutV.addWidget(self.txt_editor,			4, 0, 20, 4)
		layoutV.addWidget(self.btn_saveExpr, 		24, 0, 1, 2)
		layoutV.addWidget(self.btn_loadExpr, 		24, 2, 1, 2)
		layoutV.addWidget(self.btn_exec, 			25, 0, 1, 4)

		# - Set Widget
		self.setLayout(layoutV)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 250, 500)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def expr_fromFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load expressions from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.txt_editor.setPlainText(importFile.read().decode('utf8'))			

			print 'LOAD:\t Font:%s; Expressions loaded from: %s.' %(self.active_font.name, fname)

	def expr_toFile(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save expressions from file', fontPath, '*.txt')
		
		if fname != None:
			with open(fname, 'w') as importFile:
				importFile.writelines(self.txt_editor.toPlainText().encode('utf-8'))

			print 'SAVE:\t Font:%s; Expressions saved to: %s.' %(self.active_font.name, fname)

	def process(self):
		# - Init
		current_glyph = pGlyph()
		getUniGlyph = lambda c: self.active_font.fl.findUnicode(ord(c)).name
		process_layers = [self.cmb_layer.currentText] if self.cmb_layer.currentText != 'All masters' else self.active_font.masters()	
		
		# - Process
		for line in self.txt_editor.toPlainText().splitlines():
			process_glyphs = {}
			dst_store, src_store = [], []

			if syn_insert in line and syn_comment not in line:
				left, rigth = line.split(syn_insert)
				dst_store = [getUniGlyph(name) if syn_currglyph not in name else current_glyph.name for name in rigth.split()]
				src_temp = [item.strip().split(syn_pos) for item in left.split()]
				src_temp = [[part, mark.split(syn_transform)] for part, mark in src_temp]
				
				process_glyphs = {glyph:src_temp for glyph in dst_store}
			
			for layer in process_layers:
				for glyph_name, insert_comm in process_glyphs.iteritems():
					w_glyph = self.active_font.glyph(glyph_name)

					for insert in insert_comm:
						if len(insert):
							# - Init
							# -- Insert & origin
							if len(insert[0]):
								if syn_bboxBL in insert[0]:
									insert_name = insert[0].replace(syn_bboxBL, '')
									w_shape = self.active_font.findShape(insert_name)
									insert_origin = (w_shape.boundingBox.x(), w_shape.boundingBox.y())

								elif syn_bboxBR in insert[0]:
									insert_name = insert[0].replace(syn_bboxBR, '')
									w_shape = self.active_font.findShape(insert_name)
									insert_origin = (w_shape.boundingBox.x() + w_shape.boundingBox.width(), w_shape.boundingBox.y())

								elif syn_bboxTL in insert[0]:
									insert_name = insert[0].replace(syn_bboxTL, '')
									w_shape = self.active_font.findShape(insert_name)
									insert_origin = (w_shape.boundingBox.x(), w_shape.boundingBox.y() + w_shape.boundingBox.height())

								elif syn_bboxTR in insert[0]:
									insert_name = insert[0].replace(syn_bboxTR, '')
									w_shape = self.active_font.findShape(insert_name)
									insert_origin = (w_shape.boundingBox.x() + w_shape.boundingBox.height(), w_shape.boundingBox.y() + w_shape.boundingBox.width())
								
								else:
									insert_name = insert[0]
									w_shape = self.active_font.findShape(insert_name)
									insert_origin = (0,0)

							else:
								continue

							
							# -- Positioning
							insert_position = None

							if len(insert) == 1:
								#w_glyph.addShape(w_shape, layer)
								pass

							else:
								if len(insert[1]):
									w_bbox = w_glyph.getBounds(layer)

									if syn_currnode == insert[1][0]:
										position = w_glyph.selectedCoords(layer)
										insert_position = position[0] if len(position) else None

									elif syn_bboxBL == insert[1][0]:
										insert_position = (w_bbox.x(), w_bbox.y())

									elif syn_bboxBR == insert[1][0]:
										insert_position = (w_bbox.x() + w_bbox.width(), w_bbox.y())

									elif syn_bboxTL == insert[1][0]:
										insert_position = (w_bbox.x(), w_bbox.y() + w_bbox.height())

									elif syn_bboxTR == insert[1][0]:
										insert_position = (w_bbox.x() + w_bbox.height(), w_bbox.y() + w_bbox.width())
									
									elif syn_label in insert[1][0]:
										insert_position = w_glyph.findNodeCoords(insert[1][0].strip(syn_label), layer)

									elif syn_anchor in insert[1][0]:	
										insert_position = w_glyph.findAnchorCoords(insert[1][0].strip(syn_anchor), layer)

									elif syn_coordsep in insert[1][0]:
										insert_position = eval('(%s)' %insert[1][0])

									if len(insert[1]) > 1:
										insert_correction = Coord(eval('(%s)' %insert[1][1]))
									else:
										insert_correction = Coord((0,0))

								if insert_position is None: continue

								insert_coord = Coord(insert_position) + insert_correction
									
								print w_glyph.name, 'Add shape: ', insert_name, '|', insert_origin, '@ Coord:', insert_coord
								



				
				

				
								
		print 'Done.'

# - RUN ------------------------------
dialog = dlg_glyphComposer()