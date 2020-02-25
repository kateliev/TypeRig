#FLM: Glyph: Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.shape import eShape
from typerig.proxy import pFont, pFontMetrics, pContour, pShape
from typerig.gui import getProcessGlyphs
from typerig.brain import Coord, Line
from math import radians
import os

# - Syntax -------------------------------
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

# - Init ------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Elements', '0.28'

# - Strings ------------------------------
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

# - Sub-widgets --------------------
class MLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(MLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def smartSetText(self, prefix):
		currentText = self.text
		if currentText[0] != '.' and currentText[0] != '_': currentText = '.' + currentText
		self.setText(prefix + currentText)

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'{Glyph Name}', lambda: self.setText(eGlyph().name))
		menu.addAction(u'_part', lambda: self.smartSetText('_part'))
		menu.addAction(u'_UC', lambda: self.smartSetText('_UC'))
		menu.addAction(u'_LC', lambda: self.smartSetText('_LC'))
		menu.addAction(u'_LAT', lambda: self.smartSetText('_LAT'))
		menu.addAction(u'_CYR', lambda: self.smartSetText('_CYR'))

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
		
class basicOps(QtGui.QGridLayout):
	# - Basic Node operations
	def __init__(self):
		super(basicOps, self).__init__()

		# - Widgets
		self.edt_shapeName = MLineEdit()
		self.edt_shapeName.setPlaceholderText('Element name')

		self.btn_setShapeName = QtGui.QPushButton('&Set Name')
		self.btn_unlinkShape = QtGui.QPushButton('&Unlink References')
		self.btn_delShape = QtGui.QPushButton('&Remove')
		self.btn_resetShape = QtGui.QPushButton('&Reset transform')
		self.btn_lockShape = QtGui.QPushButton('&Lock')

		self.btn_setShapeName.clicked.connect(self.shape_setname)
		self.btn_unlinkShape.clicked.connect(self.shape_unlink)
		self.btn_delShape.clicked.connect(self.shape_delete)
		self.btn_resetShape.clicked.connect(self.shape_resetTransform)

		self.addWidget(self.edt_shapeName, 		0, 0, 1, 6)
		self.addWidget(self.btn_setShapeName, 	1, 0, 1, 3)
		self.addWidget(self.btn_unlinkShape, 	1, 3, 1, 3)
		self.addWidget(self.btn_resetShape, 	2, 0, 1, 3)
		self.addWidget(self.btn_delShape, 		2, 3, 1, 3)

	def reset_fileds(self):
		self.edt_shapeName.clear()

	def shape_resetTransform(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)

			for layer in process_layers:
				wShape = pShape(glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0])
				wShape.reset_transform()

			glyph.update()
			glyph.updateObject(glyph.fl, 'Reset Element transformation data @ %s.' %'; '.join(process_layers))

		self.reset_fileds()

	def shape_setname(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)

			for layer in process_layers:
				#print glyph.selectedAtShapes(index=False, layer=layer, deep=False)
				wShape = pShape(glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0])
				wShape.setName(self.edt_shapeName.text)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Set Element Name @ %s.' %'; '.join(process_layers))

		self.reset_fileds()

	def shape_delete(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)
			process_shapes = {layer:glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0] for layer in process_layers}
				
			for layer, shape in process_shapes.items():
				glyph.layer(layer).removeShape(shape)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Remove Element @ %s.' %'; '.join(process_layers))

	def shape_unlink(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)
			process_shapes = {layer:glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0] for layer in process_layers}
				
			for layer, shape in process_shapes.items():
				glyph.addShape(shape, layer, clone=True)
				glyph.layer(layer).removeShape(shape)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Unlink Element @ %s.' %'; '.join(process_layers))

class alignShapes(QtGui.QGridLayout):
	# - Align Contours
	def __init__(self):
		super(alignShapes, self).__init__()
		from collections import OrderedDict
		
		# - Init
		self.align_x = OrderedDict([('Left','L'), ('Right','R'), ('Center','C'), ('Keep','K')])
		self.align_y = OrderedDict([('Top','T'), ('Bottom','B'), ('Center','E'), ('Keep','X')])
		self.align_mode = OrderedDict([('Layer','CL'), ('Shape to Shape','CC'), ('Shape to Shape (REV)','RC')])
		
		# !!! To be implemented
		#self.align_mode = OrderedDict([('Layer','CL'), ('Shape to Shape','CC'), ('Shape to Shape (REV)','RC'), ('Shape to Node','CN'),('Node to Node','NN')])

		# - Widgets
		self.cmb_align_x = QtGui.QComboBox()
		self.cmb_align_y = QtGui.QComboBox()
		self.cmb_align_mode = QtGui.QComboBox()
		self.cmb_align_x.addItems(self.align_x.keys())
		self.cmb_align_y.addItems(self.align_y.keys())
		self.cmb_align_mode.addItems(self.align_mode.keys())

		self.cmb_align_x.setToolTip('Horizontal Alignment')
		self.cmb_align_y.setToolTip('Vertical Alignment')
		self.cmb_align_mode.setToolTip('Alignment Mode')

		self.btn_align = QtGui.QPushButton('Align')
		self.btn_align.clicked.connect(self.alignShapes)

		self.addWidget(self.cmb_align_mode, 	0, 0, 1, 2)
		self.addWidget(self.cmb_align_x, 		0, 2, 1, 1)
		self.addWidget(self.cmb_align_y, 		0, 3, 1, 1)
		self.addWidget(self.btn_align, 			1, 0, 1, 4)

	def alignShapes(self):
		# - Helpers
		def getShapeBounds(work_shapes):
			tmp_bounds = [shape.bounds() for shape in work_shapes]
			shape_min_X, shape_min_Y, shape_max_X, shape_max_Y = map(set, zip(*tmp_bounds))
			return (min(shape_min_X), min(shape_min_Y), max(shape_max_X), max(shape_max_Y))

		def getAlignDict(bounds_tuple):
			align_dict = {	'L': bounds_tuple[0], 
							'R': bounds_tuple[2],
							'C': bounds_tuple[2]/2,
							'B': bounds_tuple[1], 
							'T': bounds_tuple[3], 
							'E': bounds_tuple[3]/2
						}

			return align_dict

		# - Init
		user_mode =  self.align_mode[self.cmb_align_mode.currentText]
		user_x = self.align_x[self.cmb_align_x.currentText]
		user_y = self.align_y[self.cmb_align_y.currentText]
		keep_x, keep_y = True, True	

		if user_x == 'K': keep_x = False; user_x = 'L'
		if user_y == 'X': keep_y = False; user_y = 'B'		
		
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			selection = glyph.selectedAtShapes(deep=False)
			wLayers = glyph._prepareLayers(pLayers)

			for layerName in wLayers:
				glyph_shapes = glyph.shapes(layerName, extend=eShape)
				work_shapes = [glyph_shapes[index] for index in list(set([item[0] for item in selection]))]
				
				if user_mode == 'CL': # Align all shapes in given Layer
					layer_bounds = glyph.getBounds(layerName)
					shape_bounds = (layer_bounds.x(), layer_bounds.y(), layer_bounds.x() + layer_bounds.width(), layer_bounds.y() + layer_bounds.height())
					align_type = getAlignDict(shape_bounds)
					target = Coord(align_type[user_x], align_type[user_y])

					for shape in glyph_shapes:
						shape.alignTo(target, user_x + user_y, (keep_x, keep_y))					

				elif user_mode =='CC': # Align shapes to shapes
					if 1 < len(work_shapes) < 3:
						sh1, sh2 = work_shapes
						sh1.alignTo(sh2, user_x + user_y, (keep_x, keep_y))

					elif len(work_shapes) > 2:
						shape_bounds = getShapeBounds(work_shapes)
						align_type = getAlignDict(shape_bounds)
						target = Coord(align_type[user_x], align_type[user_y])

						for shape in work_shapes:
							shape.alignTo(target, user_x + user_y, (keep_x, keep_y))
					
				elif user_mode == 'RC': # Align shapes to shapes in reverse order
					if 1 < len(work_shapes) < 3:
						sh1, sh2 = work_shapes
						sh2.alignTo(sh1, user_x + user_y, (keep_x, keep_y))

					elif len(work_shapes) > 2:
						shape_bounds = getShapeBounds(work_shapes)
						align_type = getAlignDict(shape_bounds)
						target = Coord(align_type[user_x], align_type[user_y])

						for shape in reversed(work_shapes):
							shape.alignTo(target, user_x + user_y, (keep_x, keep_y))	

				# !!! To be implemented
				elif user_mode == 'CN': # Align shape to node
					pass

				elif user_mode == 'NN': # Align a node on shape to node on another
					pass

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Align Shapes @ %s.' %(glyph.name, '; '.join(wLayers)))

class glyphComposer(QtGui.QGridLayout):
	def __init__(self, parent):
		super(glyphComposer, self).__init__()
		
		# - Init
		self.parentWgt = parent

		# - Widgets
		self.cmb_fontShapes = QtGui.QComboBox()
		self.btn_populateShapes = QtGui.QPushButton('Populate')
		self.btn_insertShape = QtGui.QPushButton('Insert')
		self.btn_replaceShape = QtGui.QPushButton('Replace')
		self.btn_help = QtGui.QPushButton('Help')
		self.btn_saveExpr = QtGui.QPushButton('Save')
		self.btn_loadExpr = QtGui.QPushButton('Load')
		self.btn_exec = QtGui.QPushButton('Execute')

		self.cmb_fontShapes.setEditable(True)

		self.btn_populateShapes.clicked.connect(self.populate_shapes)
		self.btn_insertShape.clicked.connect(self.shape_insert)
		self.btn_replaceShape.clicked.connect(self.shape_replace)
		self.btn_exec.clicked.connect(self.process_insert)
		self.btn_saveExpr.clicked.connect(self.expr_toFile)
		self.btn_loadExpr.clicked.connect(self.expr_fromFile)
		self.btn_help.clicked.connect(lambda: QtGui.QMessageBox.information(self.parentWgt, 'Help', str_help))

		self.txt_editor = TrPlainTextEdit()
		
		# - Build layouts 
		self.addWidget(QtGui.QLabel('Insert elements:'),			0, 0, 1, 4)
		self.addWidget(self.cmb_fontShapes,							1, 0, 1, 6)
		self.addWidget(self.btn_populateShapes,						1, 6, 1, 2)
		self.addWidget(self.btn_insertShape,						2, 0, 1, 4)
		self.addWidget(self.btn_replaceShape,						2, 4, 1, 4)
		self.addWidget(QtGui.QLabel('Advanced Insert elements:'),	5, 0, 1, 4)
		self.addWidget(self.txt_editor,								7, 0, 30, 8)
		self.addWidget(self.btn_saveExpr, 							37, 0, 1, 4)
		self.addWidget(self.btn_loadExpr, 							37, 4, 1, 4)
		self.addWidget(self.btn_help,								38, 0, 1, 2)
		self.addWidget(self.btn_exec, 								38, 2, 1, 6)

	def expr_fromFile(self):
		self.active_font = pFont()
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.parentWgt, 'Load expressions from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				self.txt_editor.setPlainText(importFile.read().decode('utf8'))			

			print 'LOAD:\t Font:%s; Expressions loaded from: %s.' %(self.active_font.name, fname)

	def expr_toFile(self):
		self.active_font = pFont()
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.parentWgt, 'Save expressions from file', fontPath, '*.txt')
		
		if fname != None:
			with open(fname, 'w') as importFile:
				importFile.writelines(self.txt_editor.toPlainText().encode('utf-8'))

			print 'SAVE:\t Font:%s; Expressions saved to: %s.' %(self.active_font.name, fname)

	def populate_shapes(self):
		self.active_font = pFont()
		self.font_shapes = {}
		for glyph in self.active_font.pGlyphs():
			for shape in glyph.shapes():
				if len(shape.shapeData.name):
					self.font_shapes.setdefault(shape.shapeData.name,[]).append(glyph.name)
		
		self.cmb_fontShapes.clear()
		self.cmb_fontShapes.addItems(sorted(self.font_shapes.keys()))

	def shape_insert(self):
		process_glyphs = getProcessGlyphs(pMode)
		insert_shape_name = self.cmb_fontShapes.currentText

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)

			for layer in process_layers:
				insert_shape = self.active_font.findShape(insert_shape_name, layer)
				
				if insert_shape is not None:
					glyph.addShape(insert_shape, layer)
				else:
					print 'ERROR:\t Glyph: %s\tElement: %s not found @Layer: %s' %(glyph.name, insert_shape_name,layer)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tInsert Element:%s @ %s.' %(glyph.name, insert_shape_name,'; '.join(process_layers)))

	def shape_replace(self):
		process_glyphs = getProcessGlyphs(pMode)
		replace_shape_name = self.cmb_fontShapes.currentText

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)
			process_shapes_dict = {}

			for layer in process_layers:
				replace_shape = self.active_font.findShape(replace_shape_name, layer)
				selected_shape = glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0]
				
				if selected_shape is not None:
					if replace_shape is not None:
						process_shapes_dict[layer] = (selected_shape, replace_shape, selected_shape.transform)
					else:
						print 'ERROR:\t Glyph: %s\tElement: %s not found @Layer: %s' %(glyph.name, replace_shape_name,layer)

			for layer, shape_triple in process_shapes_dict.items():
					replace_shape.transform =  shape_triple[2] # Apply transform
					glyph.replaceShape(shape_triple[0], shape_triple[1], layer)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tInsert Element:%s @ %s.' %(glyph.name, replace_shape_name,'; '.join(process_layers)))

	def process_insert(self):
		# - Init
		self.active_font = pFont()
		current_glyph = eGlyph()
		getUniGlyph = lambda c: self.active_font.fl.findUnicode(ord(c)).name if all(['uni' not in c, '.' not in c, '_' not in c]) else c
				
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
				for glyph_name, insert_command in process_glyphs.iteritems():
					
					# - Set working glyph
					w_glyph = eGlyph(self.active_font.glyph(glyph_name).fl)
					process_layers = w_glyph._prepareLayers(pLayers)

					for layer in process_layers:
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
									
									elif syn_label in insert[0]: # Shape origin: At source Glyphs Labeled Node
										insert_name, node_label = insert[0].split(syn_label)
										for glyph in self.active_font.pGlyphs():
											w_shape = glyph.findShape(insert_name, layer)
											
											if w_shape is not None:
												insert_origin = Coord(glyph.findNodeCoords(node_label, layer))
												break											

										
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

								new_shape.assignStyle(w_shape) # The only way to copy the 'non-spacing' property for now

								new_position = insert_coord - insert_origin
								new_transform = QtGui.QTransform(1, 0, 0, 0, 1, 0, new_position.x, new_position.y, 1)
								new_shape.transform = new_transform
								
								w_glyph.update()
								#print 'New: %s; Insert: %s; Origin: %s' %(new_position, insert_coord, insert_origin)

					# - Finish
					w_glyph.updateObject(w_glyph.fl, 'Shapes inserted to glyph: %s' %w_glyph.name)

			print 'DONE:\t Glyphs processed: %s' %' '.join(dst_store)
				
		print 'Done.'

class shapeMovement(QtGui.QVBoxLayout):
	def __init__(self):
		super(shapeMovement, self).__init__()

		# - Init
		self.methodList = ['Shift', 'Scale', 'Shear']
		
		# - Methods
		self.cmb_methodSelector = QtGui.QComboBox()
		self.cmb_methodSelector.addItems(self.methodList)
		self.cmb_methodSelector.setToolTip('Select transformation method')
		
		# - Arrow buttons
		self.btn_up = QtGui.QPushButton('Up')
		self.btn_down = QtGui.QPushButton('Down')
		self.btn_left = QtGui.QPushButton('Left')
		self.btn_right = QtGui.QPushButton('Right')
		
		self.btn_up.setMinimumWidth(80)
		self.btn_down.setMinimumWidth(80)
		self.btn_left.setMinimumWidth(80)
		self.btn_right.setMinimumWidth(80)

		self.btn_up.clicked.connect(self.onUp)
		self.btn_down.clicked.connect(self.onDown)
		self.btn_left.clicked.connect(self.onLeft)
		self.btn_right.clicked.connect(self.onRight)
		
		self.edt_offX = QtGui.QLineEdit('1.0')
		self.edt_offY = QtGui.QLineEdit('1.0')
		self.edt_offX.setToolTip('X offset')
		self.edt_offY.setToolTip('Y offset')

		# - Layout
		self.lay_btn = QtGui.QGridLayout()

		self.lay_btn.addWidget(self.cmb_methodSelector, 0, 0, 1, 6)
		self.lay_btn.addWidget(QtGui.QLabel('X:'), 		1, 0, 1, 1)
		self.lay_btn.addWidget(self.edt_offX, 			1, 1, 1, 1)
		self.lay_btn.addWidget(self.btn_up, 			1, 2, 1, 2)
		self.lay_btn.addWidget(QtGui.QLabel('Y:'), 		1, 4, 1, 1)
		self.lay_btn.addWidget(self.edt_offY, 			1, 5, 1, 1)
		self.lay_btn.addWidget(self.btn_left, 			2, 0, 1, 2)
		self.lay_btn.addWidget(self.btn_down, 			2, 2, 1, 2)
		self.lay_btn.addWidget(self.btn_right, 			2, 4, 1, 2)

		self.addLayout(self.lay_btn)

	def moveElement(self, offset_x, offset_y, method):
		# - Init
		glyph = eGlyph()
		font = pFont()
		
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selected_shapes = glyph.selectedAtShapes(index=False, layer=layer, deep=False)
								
				for shape, contour, node in selected_shapes:
					wShape = pShape(shape)
					if method =='Shift':
						wShape.shift(offset_x, offset_y)

					elif method == 'Scale':
						wShape.scale(1. + offset_x/100., 1. + offset_y/100.)

					elif method == 'Shear':
						wShape.shear(radians(offset_x), radians(offset_y))				

			glyph.update()
			glyph.updateObject(glyph.fl, 'Element: %s @ %s.' %(method, '; '.join(wLayers)))
		
		# - Set Undo
		#glyph.updateObject(glyph.activeLayer(), '%s @ %s.' %(method, glyph.activeLayer().name), verbose=False)

		# - Finish it
		glyph.update()

	def onUp(self):
		self.moveElement(.0, float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText))

	def onDown(self):
		self.moveElement(.0, -float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText))
			
	def onLeft(self):
		self.moveElement(-float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText))
			
	def onRight(self):
		self.moveElement(float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText))

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.KeyboardOverride = False
		
		# - Build		
		layoutV.addWidget(QtGui.QLabel('Basic Operations:'))
		layoutV.addLayout(basicOps())
		layoutV.addLayout(glyphComposer(self))

		layoutV.addWidget(QtGui.QLabel('Align Shapes:'))
		self.alignShapes = alignShapes()
		layoutV.addLayout(self.alignShapes)

		layoutV.addStretch()
		layoutV.addWidget(QtGui.QLabel('Transformation:'))
		self.shapeMovement = shapeMovement()
		layoutV.addLayout(self.shapeMovement)  
		
		# - Capture Kyaboard
		self.btn_capture = QtGui.QPushButton('Capture Keyboard')

		self.btn_capture.setCheckable(True)
		self.btn_capture.setToolTip('Click here to capture keyboard arrows input.\nNote:\n+10 SHIFT\n+100 CTRL\n Exit ESC')
		self.btn_capture.clicked.connect(lambda: self.captureKeyaboard())

		layoutV.addWidget(self.btn_capture)

		# - Build ---------------------------
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

	def keyPressEvent(self, eventQKeyEvent):
		if self.KeyboardOverride:	
			key = eventQKeyEvent.key()
			modifier = int(eventQKeyEvent.modifiers())
			addon = .0
			
			if key == QtCore.Qt.Key_Escape:
				#self.close()
				self.releaseKeyboard()
				self.KeyboardOverride = False
				self.btn_capture.setChecked(False)
				self.btn_capture.setText('Capture Keyboard')
				
			# - Keyboard listener
			# -- Modifier addon
			if modifier == QtCore.Qt.ShiftModifier:
				addon = 10.0
			elif modifier == QtCore.Qt.ControlModifier:
				addon = 100.0
			else:
				addon = .0
			
			# -- Standard movement keys	
			if key == QtCore.Qt.Key_Up:
				shiftXY = (.0, float(self.shapeMovement.edt_offY.text) + addon)
			
			elif key == QtCore.Qt.Key_Down:
				shiftXY = (.0, -float(self.shapeMovement.edt_offY.text) - addon)
			
			elif key == QtCore.Qt.Key_Left:
				shiftXY = (-float(self.shapeMovement.edt_offX.text) - addon, .0)
			
			elif key == QtCore.Qt.Key_Right:
				shiftXY = (float(self.shapeMovement.edt_offX.text) + addon, .0)
			
			else:
				shiftXY = (.0,.0)
			
			# - Move
			self.shapeMovement.moveElement(*shiftXY, method=str(self.shapeMovement.cmb_methodSelector.currentText))

	def captureKeyaboard(self):
		if not self.KeyboardOverride:
			self.KeyboardOverride = True
			self.btn_capture.setChecked(True)
			self.btn_capture.setText('Keyboard Capture Active. [ESC] Exit')
			self.grabKeyboard()
		else:
			self.KeyboardOverride = False
			self.btn_capture.setChecked(False)
			self.btn_capture.setText('Capture Keyboard')
			self.releaseKeyboard()
	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()