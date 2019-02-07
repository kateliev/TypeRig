#FLM: Glyph: Round corner
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
from typerig.glyph import eGlyph
from typerig.gui import trTableView, trSliderCtrl



# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Round', '1.1'

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

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()

		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_glyphName.setPlaceholderText('Glyph name')

		self.btn_getBuilder = QtGui.QPushButton('Set &Builder')
		self.btn_findBuilder = QtGui.QPushButton('&From Font')
		self.btn_addPreset = QtGui.QPushButton('Add &Preset')
		self.btn_delPreset = QtGui.QPushButton('&Remove Preset')
		self.btn_loadPreset = QtGui.QPushButton('&Load Presets')
		self.btn_savePreset = QtGui.QPushButton('&Save Presets')
		self.btn_applyPreset = QtGui.QPushButton('&Apply Preset')

		self.btn_getBuilder.setMinimumWidth(70)
		self.btn_findBuilder.setMinimumWidth(70)
		self.btn_addPreset.setMinimumWidth(140)
		self.btn_delPreset.setMinimumWidth(140)
		self.btn_loadPreset.setMinimumWidth(140)
		self.btn_savePreset.setMinimumWidth(140)
		self.btn_applyPreset.setMinimumWidth(140)

		self.btn_getBuilder.setCheckable(True)
		self.btn_getBuilder.setChecked(False)
		self.btn_findBuilder.setEnabled(False)

		self.btn_getBuilder.clicked.connect(self.getBuilder)
		self.btn_addPreset.clicked.connect(lambda: self.preset_modify(False))
		self.btn_delPreset.clicked.connect(lambda: self.preset_modify(True))
		self.btn_loadPreset.clicked.connect(lambda: self.preset_load())
		self.btn_savePreset.clicked.connect(lambda: self.preset_save())
		self.btn_applyPreset.clicked.connect(lambda: self.preset_apply())

		# -- Rounding recipe Table
		self.tab_roundValues = trTableView(None)		
		self.tab_roundValues.clear()
		self.tab_roundValues.setTable(self.table_dict, sortData=(False, False))
		self.tab_roundValues.horizontalHeader().setStretchLastSection(False)
		self.tab_roundValues.verticalHeader().hide()
		#self.tab_roundValues.resizeColumnsToContents()

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('Round: Smart corner'), 0,0,1,8)
		self.lay_head.addWidget(QtGui.QLabel('B: '),			1,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,				1,1,1,3)
		self.lay_head.addWidget(self.btn_getBuilder,			1,4,1,2)
		self.lay_head.addWidget(self.btn_findBuilder,			1,6,1,2)
		self.lay_head.addWidget(self.btn_loadPreset,			2,0,1,4)
		self.lay_head.addWidget(self.btn_savePreset,			2,4,1,4)
		self.lay_head.addWidget(self.btn_addPreset,				3,0,1,4)
		self.lay_head.addWidget(self.btn_delPreset,				3,4,1,4)
		self.lay_head.addWidget(self.tab_roundValues,			4,0,2,8)
		self.lay_head.addWidget(self.btn_applyPreset,			6,0,1,8)

		self.addLayout(self.lay_head)

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
					self.builder = temp_builder[filter_name]
					self.btn_getBuilder.setText('Release')
		else:
			self.builder = None
			self.edt_glyphName.clear()
			self.btn_getBuilder.setText('Set Builder')			

	def preset_modify(self, delete=False):
		table_rawList = self.tab_roundValues.getTable(raw=True)
		
		if delete:
			for selection in self.tab_roundValues.selectionModel().selectedIndexes:
				table_rawList.pop(selection.row())
				print selection.row()

		new_entry = OrderedDict()
		
		for key, data in table_rawList:
			new_entry[key] = OrderedDict(data)

		if not delete: new_entry[len(table_rawList)] = self.empty_preset(len(table_rawList)).items()[0][1]
		self.tab_roundValues.setTable(new_entry, sortData=(False, False))

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

			self.tab_roundValues.setTable(new_data, sortData=(False, False))
			print 'LOAD:\t Font:%s; Presets loaded from: %s.' %(self.active_font.name, fname)

	def preset_save(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upper_widget, 'Save presets to file', fontPath, 'TypeRig JSON (*.json)')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.tab_roundValues.getTable(raw=True), exportFile)

			print 'SAVE:\t Font:%s; Presets saved to: %s.' %(self.active_font.name, fname)

	def __setFilter(self, glyph, shape, layer, builder, suffix='.old'):
		new_container = fl6.flShape()
		new_container.shapeData.name = shape.shapeData.name
		shape.shapeData.name = shape.shapeData.name + suffix
		
		#!!!! TODO: transformation copy and delete

		new_container.include(shape, glyph.layer(layer))
		new_container.shapeBuilder = builder.clone()
		new_container.update()
		glyph.layer(layer).addShape(new_container)

	def __processGlyph(self, glyph, preset):
		wLayers = glyph._prepareLayers(pLayers)					
		
		for layer in wLayers:
			if layer in preset.keys():
				# - Init
				selection_deep = [(item[0], item[2]) for item in glyph.selectedAtShapes(layer=layer, index=False, deep=True)]
				selection_shallow = [(item[0], item[2]) for item in glyph.selectedAtShapes(layer=layer, index=False, deep=False)]
				selection = selection_deep + selection_shallow

				# - Build note to shape reference
				nodes_at_shapes = [(shape, [node for shape, node in list(nodes)]) for shape, nodes in groupby(selection, key=itemgetter(0))]
				
				# - Build filter if not present
				for shape, node_list in nodes_at_shapes:
					if len(glyph.containers(layer)):
						for container in glyph.containers(layer):
							if shape not in container.includesList: 
								self.__setFilter(glyph, shape, layer, self.builder)
					else:
						self.__setFilter(glyph, shape, layer, self.builder)

				# - Process the nodes
				process_nodes = [pNode(node) for shape, node_list in nodes_at_shapes for node in node_list]
				
				for node in process_nodes:
					angle_value = preset[layer]
					
					if 'DEL' not in angle_value.upper():
						node.setSmartAngle(float(angle_value))
					else:
						node.delSmartAngle()

		glyph.update()
		glyph.updateObject(glyph.fl, 'DONE:\t Glyph: %s; Filter: Smart corner; Parameters: %s' %(glyph.name, preset))

	def preset_apply(self):
		if self.builder is not None:
			# - Init
			process_glyphs = []
			table_raw = self.tab_roundValues.getTable(raw=True)
			active_preset_index = self.tab_roundValues.selectionModel().selectedIndexes[0].row()
			if active_preset_index is None: active_preset_index = 0
			active_preset = dict(table_raw[active_preset_index][1][1:])
			active_workspace = pWorkspace()
			
			# - Collect process glyphs
			if pMode == 0: process_glyphs.append(eGlyph()) # Current Active Glyph
			if pMode == 1: process_glyphs = [eGlyph(glyph) for glyph in active_workspace.getTextBlockGlyphs()] # All glyphs in current window
			if pMode > 1: return # Not allowed - exit!
			
			# - Process
			if len(process_glyphs):
				for glyph in process_glyphs:
					if glyph is not None: self.__processGlyph(glyph, active_preset)

		else:
			print 'ERROR:\t Please specify a Glyph with suitable Shape Builder (Smart corner) first!'
						

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

		self.__updateGlyphs(self.process_glyphs)

	def __updateGlyphs(self, glyphs, complete=False):
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
		self.__updateGlyphs(self.process_glyphs, True)


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