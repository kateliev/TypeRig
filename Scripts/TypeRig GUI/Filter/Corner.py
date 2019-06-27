#FLM: Filter: Corner
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json
from itertools import groupby
from operator import itemgetter
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont, pShape, pNode, pWorkspace
from typerig.node import eNode
from typerig.glyph import eGlyph
from typerig.gui import trTableView, trSliderCtrl, getProcessGlyphs

# - Init
global pLayers
global pMode
pLayers = (True, True, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Corner', '1.97'

# -- Strings
filter_name = 'Smart corner'

# - Sub widgets ------------------------
class QSmartCorner(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self, parentWidget):
		super(QSmartCorner, self).__init__()
		self.upper_widget = parentWidget

		# -- Init
		self.active_font = pFont()
		self.builder = None
		self.font_masters = self.active_font.masters()
		self.empty_preset = lambda row: OrderedDict([(row, OrderedDict([('Preset', 'Preset %s' %row)] + [(master, '0') for master in self.font_masters]))])
		self.table_dict = self.empty_preset(0)
		self.last_preset = 0

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()

		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_glyphName.setPlaceholderText('Glyph name')

		# -- Buttons
		self.btn_getBuilder = QtGui.QPushButton('Set &Builder')
		self.btn_findBuilder = QtGui.QPushButton('&From Font')
		self.btn_addPreset = QtGui.QPushButton('Add')
		self.btn_delPreset = QtGui.QPushButton('Remove')
		self.btn_resetPreset = QtGui.QPushButton('Reset')
		self.btn_loadPreset = QtGui.QPushButton('&Load Presets')
		self.btn_savePreset = QtGui.QPushButton('&Save Presets')
		self.btn_apply_smartCorner = QtGui.QPushButton('&Apply Smart Corner')
		self.btn_remove_smartCorner = QtGui.QPushButton('R&emove Smart Corner')
		self.btn_remove_presetCorner = QtGui.QPushButton('&Find and Remove')

		self.btn_apply_smartCorner.setToolTip('Apply Smart Corner preset on SELECTED nodes.')
		self.btn_remove_smartCorner.setToolTip('Remove Smart Corner on SELECTED nodes.')
		self.btn_remove_presetCorner.setToolTip('Find and remove all Smart Corners that equal the currently selected preset.')


		self.btn_apply_round = QtGui.QPushButton('&Round')
		self.btn_apply_mitre = QtGui.QPushButton('&Mitre')
		self.btn_apply_overlap = QtGui.QPushButton('&Overlap')
		self.btn_apply_trap = QtGui.QPushButton('&Trap')
		self.btn_rebuild = QtGui.QPushButton('Rebuild corner')

		self.btn_getBuilder.setMinimumWidth(70)
		self.btn_findBuilder.setMinimumWidth(70)
		self.btn_apply_round.setMinimumWidth(70)
		self.btn_apply_mitre.setMinimumWidth(70)
		self.btn_apply_overlap.setMinimumWidth(70)
		self.btn_apply_trap.setMinimumWidth(70)
		self.btn_rebuild.setMinimumWidth(70)

		self.btn_addPreset.setMinimumWidth(70)
		self.btn_delPreset.setMinimumWidth(70)
		self.btn_loadPreset.setMinimumWidth(140)
		self.btn_savePreset.setMinimumWidth(140)
		self.btn_apply_smartCorner.setMinimumWidth(140)
		self.btn_remove_smartCorner.setMinimumWidth(140)
		self.btn_remove_presetCorner.setMinimumWidth(140)

		self.btn_getBuilder.setCheckable(True)
		self.btn_getBuilder.setChecked(False)
		self.btn_findBuilder.setEnabled(False)
		self.btn_apply_round.setEnabled(False)

		self.btn_getBuilder.clicked.connect(lambda: self.getBuilder())
		self.btn_addPreset.clicked.connect(lambda: self.preset_modify(False))
		self.btn_delPreset.clicked.connect(lambda: self.preset_modify(True))
		self.btn_resetPreset.clicked.connect(lambda: self.preset_reset())
		self.btn_loadPreset.clicked.connect(lambda: self.preset_load())
		self.btn_savePreset.clicked.connect(lambda: self.preset_save())

		self.btn_apply_smartCorner.clicked.connect(lambda: self.apply_SmartCorner(False))
		self.btn_remove_smartCorner.clicked.connect(lambda: self.apply_SmartCorner(True))
		self.btn_remove_presetCorner.clicked.connect(lambda: self.remove_SmartCorner())
		
		#self.btn_apply_round.clicked.connect(lambda: self.apply_round())
		self.btn_apply_mitre.clicked.connect(lambda: self.apply_mitre(False))
		self.btn_apply_overlap.clicked.connect(lambda: self.apply_mitre(True))
		self.btn_apply_trap.clicked.connect(lambda: self.apply_trap())
		self.btn_rebuild.clicked.connect(lambda: self.rebuild())

		# -- Preset Table
		self.tab_presets = trTableView(None)
		self.preset_reset()			

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('Value Presets:'), 0,0,1,8)
		self.lay_head.addWidget(self.btn_loadPreset,			1,0,1,4)
		self.lay_head.addWidget(self.btn_savePreset,			1,4,1,4)
		self.lay_head.addWidget(self.btn_addPreset,				2,0,1,2)
		self.lay_head.addWidget(self.btn_delPreset,				2,2,1,2)
		self.lay_head.addWidget(self.btn_resetPreset,			2,4,1,4)
		self.lay_head.addWidget(self.tab_presets,				3,0,5,8)

		self.lay_head.addWidget(QtGui.QLabel('Corner Actions:'),10, 0, 1, 8)
		self.lay_head.addWidget(self.btn_apply_round,			11, 0, 1, 2)
		self.lay_head.addWidget(self.btn_apply_mitre,			11, 2, 1, 2)
		self.lay_head.addWidget(self.btn_apply_overlap,			11, 4, 1, 2)
		self.lay_head.addWidget(self.btn_apply_trap,			11, 6, 1, 2)
		self.lay_head.addWidget(self.btn_rebuild,				12, 0, 1, 8)

		self.lay_head.addWidget(QtGui.QLabel('Smart Corner:'),	13,0,1,8)
		self.lay_head.addWidget(QtGui.QLabel('Builder: '),		14,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,				14,1,1,3)
		self.lay_head.addWidget(self.btn_getBuilder,			14,4,1,2)
		self.lay_head.addWidget(self.btn_findBuilder,			14,6,1,2)
		self.lay_head.addWidget(self.btn_remove_smartCorner,	15,0,1,4)
		self.lay_head.addWidget(self.btn_remove_presetCorner,	15,4,1,4)
		self.lay_head.addWidget(self.btn_apply_smartCorner,		16,0,1,8)

		self.addLayout(self.lay_head)

	# - Presets management ------------------------------------------------
	def preset_reset(self):
		self.builder = None
		self.active_font = pFont()
		self.font_masters = self.active_font.masters()
		
		self.table_dict = self.empty_preset(0)
		self.tab_presets.clear()
		self.tab_presets.setTable(self.table_dict, sortData=(False, False))
		self.tab_presets.horizontalHeader().setStretchLastSection(False)
		self.tab_presets.verticalHeader().hide()
		#self.tab_presets.resizeColumnsToContents()

	def preset_modify(self, delete=False):
		table_rawList = self.tab_presets.getTable(raw=True)
		
		if delete:
			for selection in self.tab_presets.selectionModel().selectedIndexes:
				table_rawList.pop(selection.row())
				print selection.row()

		new_entry = OrderedDict()
		
		for key, data in table_rawList:
			new_entry[key] = OrderedDict(data)

		if not delete: new_entry[len(table_rawList)] = self.empty_preset(len(table_rawList)).items()[0][1]
		self.tab_presets.setTable(new_entry, sortData=(False, False))

	def preset_load(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upper_widget, 'Load presets from file', fontPath, 'TypeRig JSON (*.json)')
		
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = json.load(importFile)
			
			# - Convert Data
			new_data = OrderedDict()
			for key, data in imported_data:
				new_data[key] = OrderedDict(data)

			self.tab_presets.setTable(new_data, sortData=(False, False))
			print 'LOAD:\t Font:%s; Presets loaded from: %s.' %(self.active_font.name, fname)

	def preset_save(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save presets to file', fontPath, 'TypeRig JSON (*.json)')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tab_presets.getTable(raw=True), exportFile)

			print 'SAVE:\t Font:%s; Presets saved to: %s.' %(self.active_font.name, fname)

	def getPreset(self):
		table_raw = self.tab_presets.getTable(raw=True)
		'''
		try:
			active_preset_index = self.tab_presets.selectionModel().selectedIndexes[0].row()
		except IndexError:
			active_preset_index = None
		'''
		active_preset_index = self.tab_presets.selectionModel().selectedIndexes[0].row()

		if active_preset_index is None: 
			active_preset_index = self.last_preset
		else:
			self.last_preset = active_preset_index

		return dict(table_raw[active_preset_index][1][1:])

	# - Basic Corner ------------------------------------------------
	def apply_mitre(self, doKnot=False):
		# - Init
		process_glyphs = getProcessGlyphs(pMode)
		active_preset = self.getPreset()	

		# - Process
		if len(process_glyphs):
			for glyph in process_glyphs:
				if glyph is not None:
					wLayers = glyph._prepareLayers(pLayers)
		
					for layer in reversed(wLayers):
						if layer in active_preset.keys():
							selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode, deep=True)
							
							for node in reversed(selection):
								if not doKnot:
									node.cornerMitre(float(active_preset[layer]))
								else:
									node.cornerMitre(-float(active_preset[layer]), True)
					
					action = 'Mitre Corner' if not doKnot else 'Overlap Corner'
					glyph.update()
					glyph.updateObject(glyph.fl, '%s @ %s.' %(action, '; '.join(active_preset.keys())))

	def apply_trap(self):
		# - Init
		process_glyphs = getProcessGlyphs(pMode)
		active_preset = self.getPreset()	

		# - Process
		if len(process_glyphs):
			for glyph in process_glyphs:
				if glyph is not None:
					wLayers = glyph._prepareLayers(pLayers)
		
					for layer in reversed(wLayers):
						if layer in active_preset.keys():
							selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode, deep=True)
							
							for node in reversed(selection):
								preset_values = tuple([float(item.strip()) for item in active_preset[layer].split(',')])
								node.cornerTrapInc(*preset_values)
					
					glyph.update()
					glyph.updateObject(glyph.fl, '%s @ %s.' %('Ink Trap', '; '.join(active_preset.keys())))

	def rebuild(self):
		# - Init
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		if len(process_glyphs):
			for glyph in process_glyphs:
				if glyph is not None:
					wLayers = glyph._prepareLayers(pLayers)
		
					for layer in wLayers:
						selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode, deep=True)
						
						if len(selection) > 1:
							node_first = selection[0]
							node_last = selection[-1]
							
							line_in = node_first.getPrevLine() if node_first.getPrevOn(False) not in selection else node_first.getNextLine()
							line_out = node_last.getNextLine() if node_last.getNextOn(False) not in selection else node_last.getPrevLine()

							crossing = line_in & line_out

							node_first.smartReloc(*crossing)
							node_first.parent.removeNodesBetween(node_first.fl, node_last.getNextOn())
			
					glyph.update()
					glyph.updateObject(glyph.fl, 'Rebuild corner: %s nodes reduced; At layers: %s' %(len(selection), '; '.join(wLayers)))

	# - Smart Corner ------------------------------------------------
	def getBuilder(self):
		if self.btn_getBuilder.isChecked():
			if len(self.edt_glyphName.text):
				builder_glyph = self.active_font.glyph(self.edt_glyphName.text)
			else:
				builder_glyph = eGlyph()
				self.edt_glyphName.setText(builder_glyph.name)

			if builder_glyph is not None:
				temp_builder = builder_glyph.getBuilders()

				if len(temp_builder.keys()) and filter_name in temp_builder.keys():
					self.builder = temp_builder[filter_name][0]
					self.btn_getBuilder.setText('Release')
		else:
			self.builder = None
			self.edt_glyphName.clear()
			self.btn_getBuilder.setText('Set Builder')	

	def process_setFilter(self, glyph, shape, layer, builder, suffix='.old'):
		new_container = fl6.flShape()
		new_container.shapeData.name = shape.shapeData.name
		if len(shape.shapeData.name): shape.shapeData.name += suffix
		
		#!!!! TODO: transformation copy and delete

		new_container.include(shape, glyph.layer(layer))
		new_container.shapeBuilder = builder.clone()
		new_container.update()
		
		glyph.layer(layer).addShape(new_container)
		#glyph.layer(layer).update()

	def process_smartCorner(self, glyph, preset):
		wLayers = glyph._prepareLayers(pLayers)	
		nodes_at_shapes = {}	

		# - Build selection
		for work_layer in wLayers:
			if work_layer in preset.keys():
				# - Init
				selection_deep = [(item[0], item[2]) for item in glyph.selectedAtShapes(layer=work_layer, index=False, deep=True)]
				selection_shallow = [(item[0], item[2]) for item in glyph.selectedAtShapes(layer=work_layer, index=False, deep=False)]
				selection = selection_deep + selection_shallow
								
				# - Build note to shape reference
				nodes_at_shapes[work_layer] = [(shape, [node for shape, node in list(nodes)]) for shape, nodes in groupby(selection, key=itemgetter(0))]

		# - Process glyph
		for work_layer in wLayers:
			if work_layer in nodes_at_shapes.keys():

				# - Build filter if not present
				for work_shape, node_list in nodes_at_shapes[work_layer]:
					if len(glyph.containers(work_layer)):
						for container in glyph.containers(work_layer):
							if work_shape not in container.includesList: 
								self.process_setFilter(glyph, work_shape, work_layer, self.builder)
					else:
						self.process_setFilter(glyph, work_shape, work_layer, self.builder)


				# - Process the nodes
				process_nodes = [pNode(node) for shape, node_list in nodes_at_shapes[work_layer] for node in node_list]
				
				for work_node in process_nodes:
					angle_value = preset[work_layer]
					
					if 'DEL' not in angle_value.upper():
						work_node.setSmartAngle(float(angle_value))
					else:
						work_node.delSmartAngle()

		#glyph.update()
		#glyph.updateObject(glyph.fl, 'DONE:\t Glyph: %s; Filter: Smart corner; Parameters: %s' %(glyph.name, preset))

	def apply_SmartCorner(self, remove=False):
		# NOTE: apply and remove here apply only to soelected nodes.
		if self.builder is not None:
			# - Init
			process_glyphs = getProcessGlyphs(pMode)
			active_preset = self.getPreset()

			if remove: # Build a special preset that deletes
				active_preset = {key:'DEL' for key in active_preset.keys()} 
		
			# - Process
			if len(process_glyphs):
				for work_glyph in process_glyphs:
					if work_glyph is not None: 
						self.process_smartCorner(work_glyph, active_preset)
						
				self.update_glyphs(process_glyphs, True)
				print 'DONE:\t Filter: Smart Corner; Glyphs: %s' %'; '.join([g.name for g in process_glyphs])

		else:
			print 'ERROR:\t Please specify a Glyph with suitable Shape Builder (Smart corner) first!'

	def remove_SmartCorner(self):
		# Finds active preset in glyphs smart corners and removes them
		# - Init
		process_glyphs = getProcessGlyphs(pMode)
		active_preset = self.getPreset()

		# - Process
		if len(process_glyphs):
			for work_glyph in process_glyphs:
				if work_glyph is not None:
					# - Init
					wLayers = work_glyph._prepareLayers(pLayers)	
					smart_corners, target_corners = [], []
					
					# - Get all smart nodes/corners
					for layer in wLayers:
						for builder in work_glyph.getBuilders(layer)[filter_name]:
							smart_corners += builder.getSmartNodes()

						if len(smart_corners):
							for node in smart_corners:
								wNode = eNode(node)

								if wNode.getSmartAngleRadius() == float(active_preset[layer]):
									wNode.delSmartAngle()

			self.update_glyphs(process_glyphs, True)
			print 'DONE:\t Filter: Remove Smart Corner; Glyphs: %s' %'; '.join([g.name for g in process_glyphs])

	def update_glyphs(self, glyphs, complete=False):
		for glyph in glyphs:
			glyph.update()
			
			if not complete: # Partial update - contour only
				for contour in glyph.contours():
					contour.changed()
			else: # Full update - with undo snapshot
				glyph.updateObject(glyph.fl, verbose=False)						

class QCornerControl(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self, parentWidget):
		super(QCornerControl, self).__init__()
		self.upper_widget = parentWidget

		# - Init
		self.active_font = pFont()
		self.font_masters = self.active_font.masters()
		self.sliders = []
		self.process_glyphs = []

		# - Widgets
		self.__build()

	
	def __build(self):
		# - Init
		self.sliders = []
		self.process_glyphs = []

		# - Buttons
		self.btn_capture = QtGui.QPushButton('Capture Smart Angles')
		self.btn_capture.clicked.connect(lambda: self.capture())

		# - Set layout
		self.addWidget(QtGui.QLabel('\nRound: Smart corner control'))
		self.addWidget(self.btn_capture)

	def __clear(self):
		'''
		for i in reversed(range(0, self.count())):
			self.itemAt(i).widget().setParent(None)
		'''
		def deleteItems(layout): 
			if layout is not None: 
				while layout.count(): 
					item = layout.takeAt(0) 
					widget = item.widget() 
					if widget is not None: 
						widget.deleteLater() 
					else: 
						deleteItems(item.layout()) 
			
		deleteItems(self) 

	def __processNodes(self):
		# Bad, primitive, but working!
		for sID in range(len(self.sliders)):
			slider, last_value, nodes = self.sliders[sID]

			if slider.sld_axis.value != last_value:
				for node in nodes:
					node.setSmartAngleRadius(slider.sld_axis.value)

				self.sliders[sID][1] = slider.sld_axis.value # Reset value

		self.update_glyphs(self.process_glyphs)

	def update_glyphs(self, glyphs, complete=False):
		for glyph in glyphs:
			glyph.update()
			
			if not complete: # Partial update - contour only
				for contour in glyph.contours():
					contour.changed()
			else: # Full update - with undo snapshot
				glyph.updateObject(glyph.fl, verbose=False)

		if complete: print 'DONE:\t Update/Snapshot for glyphs: %s' %'; '.join([g.name for g in glyphs])

	def capture(self):
		# - Init
		process_angles = {}
		active_workspace = pWorkspace()
		
		# - Rebuild
		self.__clear()
		self.__build()
				
		# - Collect process glyphs
		if pMode == 0: self.process_glyphs.append(eGlyph()) # Current Active Glyph
		if pMode == 1: self.process_glyphs = [eGlyph(glyph) for glyph in active_workspace.getTextBlockGlyphs()] # All glyphs in current window
		if pMode == 2: self.process_glyphs = self.active_font.selectedGlyphs(extend=eGlyph) # Selected glyphs in font window
		if pMode > 2: return

		# - Get nodes grouped by smart angle value
		if len(self.process_glyphs):
			for glyph in self.process_glyphs:
				#wLayers = glyph._prepareLayers(pLayers)
				layer = None
				pNodes = glyph.nodes(layer=layer, extend=pNode)
				
				for node in pNodes:
					smart_angle = node.getSmartAngle()
					
					if smart_angle[0]:
						process_angles.setdefault(smart_angle[1], []).append(node)

		# - Build sliders
		for angle_value, angle_nodes in process_angles.iteritems():
			new_slider = trSliderCtrl('0', '100', angle_value, 5)
			new_slider.sld_axis.valueChanged.connect(self.__processNodes)
			self.addLayout(new_slider)
			self.sliders.append([new_slider, angle_value, angle_nodes])

		# - Set undo snapshot
		self.update_glyphs(self.process_glyphs, True)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.smart_corner = QSmartCorner(self)
		self.corner_control = QCornerControl(self)
		layoutV.addLayout(self.smart_corner)
		layoutV.addLayout(self.corner_control)
		
		# - Build
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()