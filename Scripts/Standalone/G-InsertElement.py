#FLM: Glyph: Insert elements (TypeRig)
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
app_version = '1.1'
app_name = 'Insert elements'

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
syn_passlayer = syn_label + 'passlayer'

# -- Strings 
str_help = '''Examples:
_element_ -> A B C D 
Inserts _element_ into glyphs with names /A, /B, /C, /D at the layer specified using the layer selector.

_element_ -> !glyph
Inserts _element_ into current ACTIVE GLYPH at layer selected.

_element_@-30,20 -> A
Inserts _element_ at COORDINATES -30,20 into glyph A at layer selected.

_element_@!foo -> A
Inserts _element_ at coordinates of node with TAG 'foo' at glyph /A

_element_@$bar -> A
Inserts _element_ at coordinates of ANCHOR named 'bar' at glyph /A

_element_@!node -> !glyph
Inserts _element_ at coordinates of the currently SELECTED NODE of current active glyph.

_element_@!node^40,0 -> !glyph
Inserts _element_ at coordinates with CORRECTION 40,0 of the currently selected node of current active glyph.

_element_@!TL -> A
Inserts _element_ at Top Left BBOX coordinates of the of glyph /A
Valid positional tags are !BL, !BR, !TL, !TR; 

_element_!TL@!TL^-20,10 -> A
Inserts _element_ by matching the (TL) BBOX coordinates of _element_ to the -20,10 adjusted (TL) BBOX coordinates of the of glyph /A

e1@!foo e2@!baz e3@!bar -> H I K
Inserts elements e1, e2, e3 into every glyph (/H, /I, /K) at specified node tags

layer1 - > e1!BL@!foo e2!TL@!baz^-20,0 -> H N
layer2 - > e1!BL@!foo e2!TL@!baz^-50,0 -> H N
Inserts elements e1, e2, into every glyph (/H, /N) at specified node tags with correction different for every layer set explicitly.
'''

# - Classes --------------------------------
class TrPlainTextEdit(QtGui.QPlainTextEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(TrPlainTextEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction('Symbol: Insert', lambda: self.insertPlainText(syn_insert))
		menu.addAction('Symbol: Attachment', lambda: self.insertPlainText(syn_pos))
		menu.addAction('Symbol: Node Label', lambda: self.insertPlainText(syn_label))
		menu.addAction('Symbol: Anchor Label', lambda: self.insertPlainText(syn_anchor))
		menu.addAction('Symbol: Transform', lambda: self.insertPlainText(syn_transform))
		menu.addAction('Symbol: Comment', lambda: self.insertPlainText(syn_comment))
		menu.addSeparator()
		menu.addAction('Tag: Current Glyph', lambda: self.insertPlainText(syn_currglyph))
		menu.addAction('Tag: Current Node', lambda: self.insertPlainText(syn_currnode))
		menu.addSeparator()
		menu.addAction('Tag: BBoX Bottom Left', lambda: self.insertPlainText(syn_bboxBL))
		menu.addAction('Tag: BBoX Bottom Right', lambda: self.insertPlainText(syn_bboxBR))
		menu.addAction('Tag: BBoX Top Left', lambda: self.insertPlainText(syn_bboxTL))
		menu.addAction('Tag: BBoX Top Right', lambda: self.insertPlainText(syn_bboxTR))
		menu.addSeparator()
		menu.addAction('Action: Insert selected glyph names', lambda: self.__add_names())

	def __add_names(self):
		temp_font = pFont()
		selection = [g.name for g in temp_font.selectedGlyphs()]
		self.insertPlainText(' '.join(selection))

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

		self.txt_editor = TrPlainTextEdit()
		#self.lbl_help = QtGui.QLabel(str_help)
		self.lbl_help = QtGui.QLabel('Help: TODO!')
		self.lbl_help.setWordWrap(True)
		
		# - Build layouts 
		layoutV = QtGui.QGridLayout() 
		layoutV.addWidget(QtGui.QLabel('Process font master:'),	2, 0, 1, 2)
		layoutV.addWidget(self.cmb_layer,			2, 2, 1, 2)
		layoutV.addWidget(self.lbl_help,			3, 0, 1, 4)
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
		self.active_font = pFont()
		current_glyph = pGlyph()
		getUniGlyph = lambda c: self.active_font.fl.findUnicode(ord(c)).name if all(['uni' not in c, '.' not in c, '_' not in c]) else c
		process_layers = [self.cmb_layer.currentText] if self.cmb_layer.currentText != 'All masters' else self.active_font.masters()	
		
		# - Parse input ------------------------------------------------------------
		for line in self.txt_editor.toPlainText().splitlines():
			# - Init
			process_glyphs = {}
			dst_store, src_store = [], []
			w_layer = syn_passlayer # Pass all commands - no specific layer selected

			if syn_insert in line and syn_comment not in line:
				init_parse = line.split(syn_insert)

				if len(init_parse) == 2: # No specific layer given
					left, rigth = init_parse
				
				elif len(init_parse) == 3: # Layer explicitly set
					w_layer, left, rigth = init_parse
					w_layer = w_layer.strip()
				
				else: 
					print 'ERROR:\tInvalid syntax! Skipping Line: %s\n' %line
					continue

				# - Set basics
				#dst_store = [getUniGlyph(name) if syn_currglyph not in name else current_glyph.name for name in rigth.split()]
				dst_store = [name if syn_currglyph not in name else current_glyph.name for name in rigth.split()]
				src_temp = [item.strip().split(syn_pos) for item in left.split()]
				src_temp = [[item[0], item[1].split(syn_transform)] if len(item) > 1 else item for item in src_temp]
				
				process_glyphs = {glyph:src_temp for glyph in dst_store}
			
			# - Process ------------------------------------------------------------
			for layer in process_layers:
				# - Process only specified layer or all
				if layer == w_layer or w_layer == syn_passlayer:
					
					for glyph_name, insert_command in process_glyphs.iteritems():
						# - Set working glyph
						w_glyph = self.active_font.glyph(glyph_name)

						# - Process insertions
						for insert in insert_command:
							if len(insert):
								# - Init
								# -- Shape retrieval and origin determination
								if len(insert[0]):
									if syn_bboxBL in insert[0]: # Shape origin: measured at Shapes BBox Bottom Left
										insert_name = insert[0].replace(syn_bboxBL, '')
										w_shape = self.active_font.findShape(insert_name, layer)
										insert_origin = Coord(w_shape.boundingBox.x(), w_shape.boundingBox.y())

									elif syn_bboxBR in insert[0]: # Shape origin: measured at Shapes BBox Bottom Right
										insert_name = insert[0].replace(syn_bboxBR, '')
										w_shape = self.active_font.findShape(insert_name, layer)
										insert_origin = Coord(w_shape.boundingBox.x() + w_shape.boundingBox.width(), w_shape.boundingBox.y())

									elif syn_bboxTL in insert[0]: # Shape origin: measured at Shapes BBox Top Left
										insert_name = insert[0].replace(syn_bboxTL, '')
										w_shape = self.active_font.findShape(insert_name, layer)
										insert_origin = Coord(w_shape.boundingBox.x(), w_shape.boundingBox.y() + w_shape.boundingBox.height())

									elif syn_bboxTR in insert[0]: # Shape origin: measured at Shapes BBox Top Right
										insert_name = insert[0].replace(syn_bboxTR, '')
										w_shape = self.active_font.findShape(insert_name, layer)
										insert_origin = Coord(w_shape.boundingBox.x() + w_shape.boundingBox.height(), w_shape.boundingBox.y() + w_shape.boundingBox.width())
									
									else: # Shape origin: Not set
										insert_name = insert[0]
										w_shape = self.active_font.findShape(insert_name, layer)
										insert_origin = Coord(0,0)
								else:
									print 'ERROR:\tInvalid command! Skipping insertion command: %s\n' %insert
									continue

								# -- In-glyph positioning
								insert_position = None

								if len(insert) == 1: # Position: Simplest case no positional tags
									insert_coord = Coord((0,0))
								else:
									if len(insert[1]):
										w_bbox = w_glyph.getBounds(layer)

										if syn_currnode == insert[1][0]: # Position: Destination Glyphs Currently selected node
											position = w_glyph.selectedCoords(layer, applyTransform=True)
											insert_position = position[0] if len(position) else None

										elif syn_bboxBL == insert[1][0]: # Position: Destination Glyphs BBox Bottom Left
											insert_position = (w_bbox.x(), w_bbox.y())

										elif syn_bboxBR == insert[1][0]: # Position: Destination Glyphs BBox Bottom Right
											insert_position = (w_bbox.x() + w_bbox.width(), w_bbox.y())

										elif syn_bboxTL == insert[1][0]: # Position: Destination Glyphs BBox Top Left
											insert_position = (w_bbox.x(), w_bbox.y() + w_bbox.height())

										elif syn_bboxTR == insert[1][0]: # Position: Destination Glyphs BBox Top Right
											insert_position = (w_bbox.x() + w_bbox.height(), w_bbox.y() + w_bbox.width())
										
										elif syn_label in insert[1][0]: # Position: Destination Glyphs Labeled Node
											insert_position = w_glyph.findNodeCoords(insert[1][0].strip(syn_label), layer)

										elif syn_anchor in insert[1][0]: # Position: Destination Glyphs Anchor
											insert_position = w_glyph.findAnchorCoords(insert[1][0].strip(syn_anchor), layer)

										elif syn_coordsep in insert[1][0]: # Position: Destination Glyphs Coordinates
											insert_position = eval('(%s)' %insert[1][0])

										if len(insert[1]) > 1: # Positional correction in format (x,y)
											insert_correction = Coord(eval('(%s)' %insert[1][1]))
										else:
											insert_correction = Coord((0,0))

									if insert_position is None: 
										print 'ERROR:\tInvalid positional tags! Skipping insertion command: %s\n' %insert
										continue

									# - Set insertion coordinates	
									insert_coord = Coord(insert_position) + insert_correction
																	
								# - Insert and reposition
								# !!! A quirky way of adding shapes follows
								# !!! This is so very wrong - adding the shape twice and removing the first,
								# !!! forces FL to make a proper clone of the shape!?
								temp_shape = w_glyph.addShape(w_shape, layer) # A dummy that helps ??!
								new_shape = w_glyph.addShape(w_shape, layer)
								w_glyph.layer(layer).removeShape(temp_shape)

								#new_shape.assignStyle(w_shape) # The only way to copy the 'non-spacing' property for now

								new_position = insert_coord - insert_origin
								new_transform = QtGui.QTransform(1, 0, 0, 0, 1, 0, new_position.x, new_position.y, 1)
								new_shape.transform = new_transform
								
								w_glyph.update()
								#print 'New: %s; Insert: %s; Origin: %s' %(new_position, insert_coord, insert_origin)

						# - Finish
						w_glyph.updateObject(w_glyph.fl, 'Shapes inserted to glyph: %s' %w_glyph.name, verbose=False)

			print 'DONE:\t Glyphs processed: %s' %dst_store
				
		print 'Done.'

# - RUN ------------------------------
dialog = dlg_glyphComposer()