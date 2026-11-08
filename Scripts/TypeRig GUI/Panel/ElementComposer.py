#FLM: TR: Element Composer
# SPDX-License-Identifier: AGPL-3.0-only
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Element composition: insert, replace and swap named elements across glyphs.
# Element management (merge, split, group, ungroup all, arrange, align, transform,
# round, style, rename, link, unlink...) lives in the Element panel.

# - Dependencies -------------------------
from __future__ import absolute_import, print_function
import os

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.base import Coord
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init ------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Element Composer', '2.1'

# - Syntax -------------------------------
syn_comment = '#'
syn_insert = '->'
syn_swap = '<>'
syn_label = '!'
syn_anchor = '$'
syn_pos = '@'
syn_swap_pair = '&'
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

# - Strings ------------------------------
str_help = '''Examples:
Inserting elements:

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

layer1 -> e1!BL@!foo e2!TL@!baz^-20,0 -> H N
layer2 -> e1!BL@!foo e2!TL@!baz^-50,0 -> H N
Inserts elements e1, e2, into every glyph (/H, /N) at specified node tags with correction different for every layer set explicitly.

Swapping elements:
_find_element_&_replace_element_ <> !glyph
Will find element _find_element_ in current active glyph (or multiple glyphs) and replace it with _replace_element_
'''

class TRPlainTextEdit(QtGui.QPlainTextEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(TRPlainTextEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)
		self.setToolTip('Hold F1 for Help')
		self.setStatusTip(str_help)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction('Operation: Insert', lambda: self.insertPlainText(syn_insert))
		menu.addAction('Operation: Swap', lambda: self.insertPlainText(syn_swap))
		menu.addSeparator()
		menu.addAction('Symbol: Attachment', lambda: self.insertPlainText(syn_pos))
		menu.addAction('Symbol: Node Label', lambda: self.insertPlainText(syn_label))
		menu.addAction('Symbol: Anchor Label', lambda: self.insertPlainText(syn_anchor))
		menu.addAction('Symbol: Transform', lambda: self.insertPlainText(syn_transform))
		menu.addAction('Symbol: Swap pair', lambda: self.insertPlainText(syn_swap_pair))
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
	# - Basic element operations not covered by the Element panel
	def __init__(self):
		super(basicOps, self).__init__()

		# - Widgets
		self.btn_delShape = QtGui.QPushButton('&Remove')
		self.btn_reorderShape = QtGui.QPushButton('&Auto Reorder Layer')

		self.btn_delShape.clicked.connect(self.shape_delete)
		self.btn_reorderShape.clicked.connect(self.shape_autoReorder)

		self.addWidget(self.btn_delShape, 			0, 0, 1, 3)
		self.addWidget(self.btn_reorderShape, 		0, 3, 1, 3)

	def shape_autoReorder(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)

			for layer in process_layers:
				glyph.reorder_shapes(layer)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Auto Shape Order @ %s.' %'; '.join(process_layers))

	def shape_delete(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			process_layers = glyph._prepareLayers(pLayers)
			process_shapes = {layer:glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0] for layer in process_layers}
				
			for layer, shape in process_shapes.items():
				glyph.layer(layer).removeShape(shape)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Remove Element @ %s.' %'; '.join(process_layers))

class glyphComposer(QtGui.QGridLayout):
	def __init__(self, parent):
		super(glyphComposer, self).__init__()
		
		# - Init
		self.parentWgt = parent
		self.active_font = pFont()

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

		self.txt_editor = TRPlainTextEdit()

		# - Build layouts 
		self.addWidget(QtGui.QLabel('Insert elements:'),			0, 0, 1, 4)
		self.addWidget(self.cmb_fontShapes,							1, 0, 1, 6)
		self.addWidget(self.btn_populateShapes,						1, 6, 1, 2)
		self.addWidget(self.btn_insertShape,						2, 0, 1, 4)
		self.addWidget(self.btn_replaceShape,						2, 4, 1, 4)
		self.addWidget(QtGui.QLabel('Advanced elements editor:'),	5, 0, 1, 4)
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

			output(6, app_name, 'Font:%s; Expressions loaded from: %s.' %(self.active_font.name, fname))

	def expr_toFile(self):
		self.active_font = pFont()
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.parentWgt, 'Save expressions from file', fontPath, '*.txt')
		
		if fname != None:
			with open(fname, 'w') as importFile:
				importFile.writelines(self.txt_editor.toPlainText().encode('utf-8'))

			output(7, app_name, 'Font:%s; Expressions saved to: %s.' %(self.active_font.name, fname))

	def populate_shapes(self):
		self.active_font = pFont()
		self.font_shapes = {}
		for glyph in self.active_font.pGlyphs():
			try:			
				for shape in glyph.shapes():
					if len(shape.shapeData.name):
						self.font_shapes.setdefault(shape.shapeData.name,[]).append(glyph.name)
			except AttributeError:
				pass
		
		self.cmb_fontShapes.clear()
		self.cmb_fontShapes.addItems(sorted(list(self.font_shapes.keys())))

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
					output(2, app_name, 'Glyph: %s\tElement: %s not found @Layer: %s' %(glyph.name, insert_shape_name,layer))

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
						output(2, app_name, 'Glyph: %s\tElement: %s not found @Layer: %s' %(glyph.name, insert_shape_name,layer))

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

			# - Parse Insertions
			if syn_insert in line and syn_comment not in line:
				init_parse = line.split(syn_insert)

				if len(init_parse) == 2: # No specific layer given
					left, rigth = init_parse
				
				elif len(init_parse) == 3: # Layer explicitly set
					w_layer, left, rigth = init_parse
					w_layer = w_layer.strip()
				
				else: 
					output(2, app_name, 'Invalid syntax! Skipping Line: %s\n' %line)
					continue

				# - Set basics
				#dst_store = [getUniGlyph(name) if syn_currglyph not in name else current_glyph.name for name in rigth.split()]
				dst_store = [name if syn_currglyph not in name else current_glyph.name for name in rigth.split()]
				src_temp = [item.strip().split(syn_pos) for item in left.split()]
				src_temp = [[item[0], item[1].split(syn_transform)] if len(item) > 1 else item for item in src_temp]
				
				process_glyphs = {glyph:src_temp for glyph in dst_store}
			
				# - Process ------------------------------------------------------------
				for glyph_name, insert_command in process_glyphs.items():
					
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
									output(2, app_name, 'Invalid command! Skipping insertion command: %s\n' %insert)
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
										output(2, app_name, 'Invalid positional tags! Skipping insertion command: %s\n' %insert)
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

					# - Finish
					w_glyph.updateObject(w_glyph.fl, 'Shapes inserted to glyph: %s' %w_glyph.name)

			# - Parse Swaps
			elif syn_swap in line and syn_comment not in line:
				init_parse = line.split(syn_swap)

				if len(init_parse) == 2: # No specific layer given
					left, rigth = init_parse
				
				elif len(init_parse) == 3: # Layer explicitly set
					w_layer, left, rigth = init_parse
					w_layer = w_layer.strip()
				
				else: 
					output(2, app_name, 'Invalid syntax! Skipping Line: %s\n' %line)
					continue

				# - Set basics
				if syn_currglyph in rigth:
					dst_store = getProcessGlyphs(pMode)
				else:
					dst_store = [eGlyph(self.active_font.glyph(glyph_name).fl) for glyph_name in rigth.split()]

				src_store = [item.strip().split(syn_swap_pair) for item in left.split()]
				process_glyphs = {glyph:src_store for glyph in dst_store}
			
				# - Process ------------------------------------------------------------
				for glyph, swap_command in process_glyphs.items():
					process_layers = glyph._prepareLayers(pLayers)
					do_update = False

					for layer in process_layers:
						for swap_pair in swap_command:
							if len(swap_pair):
								# - Init
								destination_shape_name, source_shape_name = swap_pair
								source_shape = self.active_font.findShape(source_shape_name, layer)
								destination_shape = glyph.findShape(destination_shape_name, layer)
								
								if source_shape is None:
									output(2, app_name, 'Element not found! Font Missing: %s' %source_shape_name)
									continue

								if destination_shape is None:
									output(2, app_name, 'Element not found! Glyph:%s Missing: %s' %(glyph.name, destination_shape_name))
									continue
								
								source_shape.transform =  destination_shape.transform # Apply transform
								glyph.replaceShapeAdv(destination_shape_name, source_shape, layer)
								do_update = True
								
							else:
								output(2, app_name, 'Invalid command! Skipping swap command: %s' %swap_pair)
								continue

					if do_update:
						glyph.updateObject(glyph.fl, 'Elements [%s ->> %s] swapped in glyph: %s' %(destination_shape_name, source_shape_name, glyph.name))


			# - Report and finish
			#output(0, app_name, 'Glyphs processed: %s' %' '.join(dst_store))
				
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
		# - Build		
		layoutV.addWidget(QtGui.QLabel('Basic Operations:'))
		layoutV.addLayout(basicOps())
		layoutV.addLayout(glyphComposer(self))
		layoutV.addStretch()

		# - Build ---------------------------
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()