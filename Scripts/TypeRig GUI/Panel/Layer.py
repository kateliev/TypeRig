#FLM: TAB Layer Tools
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Layers', '0.27'

# - Sub widgets ------------------------
class QlayerSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QlayerSelect, self).__init__()

		# - Init

		# -- Head
		self.lay_head = QtGui.QHBoxLayout()
		self.edt_glyphName = QtGui.QLineEdit()
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_refresh.clicked.connect(self.refresh)

		self.lay_head.addWidget(QtGui.QLabel('G:'))
		self.lay_head.addWidget(self.edt_glyphName)
		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)

		# -- Layer List
		self.lst_layers = QtGui.QListWidget()
		self.lst_layers.setAlternatingRowColors(True)
		self.lst_layers.setMinimumHeight(100)
		#self.lst_layers.setMaximumHeight(100)
		self.lst_layers.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection) # Select multiple items call .selectedItems() to get a QList
		self.addWidget(self.lst_layers)
		self.refresh()

	def refresh(self):
		# - Init
		layerBanList = ['#', 'img']
		self.glyph = eGlyph()

		# - Prepare
		self.edt_glyphName.setText(eGlyph().name)
		self.selection = self.glyph.layer().name
		self.lst_layers.clear()
					
		# - Build List and style it
		self.lst_layers.addItems(sorted([layer.name for layer in self.glyph.layers() if all([item not in layer.name for item in layerBanList])]))
		
		for index in range(self.lst_layers.count):
			currItem = self.lst_layers.item(index)
			currLayer = self.glyph.layer(currItem.text())

			control = (currLayer.isService, currLayer.isMasterLayer, currLayer.isMaskLayer, currLayer.isWireframe)
			controlColor = [int(item)*255 for item in control[:-1]] + [150-int(control[-1])*100]
			text = 'Service Master Mask Wireframe'.split(' ')
			controlText = ' | '.join([text[pos] for pos in range(len(text)) if control[pos]])

			currItem.setData(QtCore.Qt.DecorationRole, QtGui.QColor(*controlColor))
			currItem.setData(QtCore.Qt.ToolTipRole, controlText)

	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			print '\nERRO:\tGlyph mismatch:\n\tCurrent active glyph: %s\n\tLayers panel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg)
			print 'WARN:\tNo action taken! Forcing refresh!' 
			self.refresh()
			#raise Exception('Glyph mismatch')
			return 0

		return 1

class QlayerBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QlayerBasic, self).__init__()

		# - Init
		self.aux = aux

		# -- Basic Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_add = QtGui.QPushButton('Add')
		self.btn_dup = QtGui.QPushButton('Duplicate')
		self.btn_setServ = QtGui.QPushButton('Service')
		self.btn_setWire = QtGui.QPushButton('Wireframe')
		self.btn_del = QtGui.QPushButton('Remove')
		#self.btn_dup.setEnabled(False)
				
		self.btn_add.setToolTip('Add new layer with name')
		self.btn_dup.setToolTip('Duplicate selected with suffix')
		self.btn_del.setToolTip('Delete selected layers')
		self.btn_setServ.setToolTip('Set selected layers as Service')
		self.btn_setWire.setToolTip('Set selected layers as Wireframe')

		self.edt_name = QtGui.QLineEdit('New')
		self.edt_name.setToolTip('Name or suffix')
	
		self.btn_add.clicked.connect(self.addLayer)
		self.btn_dup.clicked.connect(self.duplicateLayers)
		self.btn_del.clicked.connect(self.deleteLayers)

		self.btn_setServ.clicked.connect(lambda: self.setLayer('Service'))
		self.btn_setWire.clicked.connect(lambda: self.setLayer('Wireframe'))

		self.lay_buttons.addWidget(self.btn_add, 0, 0)
		self.lay_buttons.addWidget(QtGui.QLabel('N:'), 0, 1)
		self.lay_buttons.addWidget(self.edt_name, 0, 2)
		self.lay_buttons.addWidget(self.btn_dup, 0, 3)
		self.lay_buttons.addWidget(self.btn_setServ, 1, 0, 1, 2)
		self.lay_buttons.addWidget(self.btn_setWire, 1, 2, 1, 1)
		self.lay_buttons.addWidget(self.btn_del, 1, 3, 1, 1)
	 
		self.addLayout(self.lay_buttons)

	def addLayer(self):
		if self.aux.doCheck():
			newLayer = fl6.flLayer()
			newLayer.name = str(self.edt_name.text)
			self.aux.glyph.addLayer(newLayer)
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Add Layer: %s.' %newLayer.name)
			self.aux.glyph.update()
			self.aux.refresh()

	def duplicateLayers(self):	
		if self.aux.doCheck():	
			''' # This should work but it does not
			for item in self.aux.lst_layers.selectedItems():
				newLayer = fl6.flLayer(self.aux.glyph.layer(item.text()))
				newLayer.name += '.%s' #%str(self.edt_name.text)
				self.aux.glyph.addLayer(newLayer)
			'''
			# - Duplicate by layer copy solution		
			for item in self.aux.lst_layers.selectedItems():
				self.aux.glyph.duplicateLayer(item.text() , '%s.%s' %(item.text(), self.edt_name.text), True)			
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Duplicate Layer: %s.' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
			self.aux.glyph.update()
			self.aux.refresh()

	def deleteLayers(self):				
		if self.aux.doCheck():	
			for item in self.aux.lst_layers.selectedItems():
				self.aux.glyph.removeLayer(item.text())

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Delete Layer: %s.' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
			self.aux.glyph.update()
			self.aux.refresh()

	def setLayer(self, type):
		if self.aux.doCheck():	
			for item in self.aux.lst_layers.selectedItems():
				wLayer = self.aux.glyph.layer(item.text())

				if type is 'Service': wLayer.isService = not wLayer.isService
				if type is 'Wireframe': wLayer.isWireframe = not wLayer.isWireframe

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Set Layer as <%s>: %s.' %(type, '; '.join([item.text() for item in self.aux.lst_layers.selectedItems()])))
			self.aux.glyph.update()
			self.aux.refresh()

class QlayerTools(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QlayerTools, self).__init__()

		# - Init
		self.aux = aux

		# -- Mode checks
		self.lay_checks = QtGui.QGridLayout()
		self.chk_outline = QtGui.QCheckBox('Outline')
		self.chk_guides = QtGui.QCheckBox('Guides')
		self.chk_anchors = QtGui.QCheckBox('Anchors')
		self.chk_lsb = QtGui.QCheckBox('LSB')
		self.chk_adv = QtGui.QCheckBox('Advance')
		self.chk_rsb = QtGui.QCheckBox('RSB')
		
		# -- Set States
		self.chk_outline.setCheckState(QtCore.Qt.Checked)
		self.chk_adv.setCheckState(QtCore.Qt.Checked)
	
		# -- Build
		self.lay_checks.addWidget(self.chk_outline, 0, 0)
		self.lay_checks.addWidget(self.chk_guides, 0, 1)
		self.lay_checks.addWidget(self.chk_anchors, 0, 2)
		self.lay_checks.addWidget(self.chk_lsb, 1, 0)
		self.lay_checks.addWidget(self.chk_adv, 1, 1)
		self.lay_checks.addWidget(self.chk_rsb, 1, 2)
		
		self.addLayout(self.lay_checks)

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QHBoxLayout()
		self.btn_swap = QtGui.QPushButton('Swap')
		self.btn_copy = QtGui.QPushButton('Copy')
		self.btn_paste = QtGui.QPushButton('Paste')
		
		self.btn_swap.setToolTip('Swap Selected Layer with Active Layer')
		self.btn_copy.setToolTip('Copy Active Layer to Selected Layer')
		self.btn_paste.setToolTip('Paste Selected Layer to Active Layer')

		self.btn_swap.clicked.connect(self.swap)
		self.btn_copy.clicked.connect(self.copy)
		self.btn_paste.clicked.connect(self.paste)
				
		self.lay_buttons.addWidget(self.btn_swap)
		self.lay_buttons.addWidget(self.btn_copy)
		self.lay_buttons.addWidget(self.btn_paste)
		self.addLayout(self.lay_buttons)
					
	# - Helper Procedures ----------------------------------------------
	def Copy_Paste_Layer_Shapes(self, glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTShapes = None
		
		# -- Get shapes
		srcShapes = glyph.shapes(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup destination layers
		if cleanDST:
			exportDSTShapes = glyph.shapes(dstLayerName)
			glyph.layer(dstLayerName).removeAllShapes()
		
		# -- Copy/Paste
		for shape in srcShapes:
			glyph.layer(dstLayerName).addShape(shape)

		return exportDSTShapes

	def Copy_Paste_Layer_Metrics(self, glyph, layerName, copy=True, mode='ADV', impSRC=None):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		
		if 'LSB' in mode.upper():
			exportMetric = glyph.getLSB(dstLayerName) 
			glyph.setLSB(glyph.getLSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			return exportMetric

		if 'ADV' in mode.upper():
			exportMetric = glyph.getAdvance(dstLayerName)
			glyph.setAdvance(glyph.getAdvance(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			return exportMetric

		if 'RSB' in mode.upper():
			exportMetric = glyph.getRSB(dstLayerName)
			glyph.setRSB(glyph.getRSB(srcLayerName) if impSRC is None else impSRC, dstLayerName)
			return exportMetric

	def Copy_Paste_Layer_Guides(self, glyph, layerName, copy=True, cleanDST=False):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName

		# -- Cleanup !!! Not implementable for now?! Why
		if cleanDST:
			pass

		self.glyph.layer(dstLayerName).appendGuidelines(self.glyph.guidelines(srcLayerName))

	def Copy_Paste_Layer_Anchors(self, glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTAnchors = None

		# -- Get anchors
		srcAnchors = glyph.anchors(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup !!! Not working
		if cleanDST:
			exportDSTAnchors = glyph.anchors(dstLayerName)

			for anchor in self.glyph.anchors(dstLayerName):
					self.glyph.layer(dstLayerName).removeAnchor(anchor)

		for anchor in srcAnchors:
				self.glyph.anchors(dstLayerName).append(anchor)

		return exportDSTAnchors

	# - Button procedures ---------------------------------------------------
	def swap(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				exportSRC = self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, True)
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, True, exportSRC)

			if self.chk_guides.isChecked():
				pass

			if self.chk_anchors.isChecked():
				pass

			if self.chk_lsb.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'LSB')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'LSB', exportMetric)

			if self.chk_adv.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'ADV')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'ADV', exportMetric)

			if self.chk_rsb.isChecked():
				exportMetric = self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'RSB')
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'RSB', exportMetric)

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Swap Layers | %s <-> %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()


	def copy(self):
		if self.aux.doCheck():
			if self.chk_outline.isChecked():
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)
				
			if self.chk_guides.isChecked():
				self.Copy_Paste_Layer_Guides(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)

			if self.chk_anchors.isChecked():
				self.Copy_Paste_Layer_Anchors(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True)

			if self.chk_lsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'LSB')
				
			if self.chk_adv.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'ADV')
				
			if self.chk_rsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), True, 'RSB')
				
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Copy Layer | %s <- %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()

	def paste(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				self.Copy_Paste_Layer_Shapes(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)
				
			if self.chk_guides.isChecked():
				self.Copy_Paste_Layer_Guides(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)

			if self.chk_anchors.isChecked():
				self.Copy_Paste_Layer_Anchors(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False)

			if self.chk_lsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'LSB')
				
			if self.chk_adv.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'ADV')
				
			if self.chk_rsb.isChecked():
				self.Copy_Paste_Layer_Metrics(self.aux.glyph, self.aux.lst_layers.currentItem().text(), False, 'RSB')
				
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Paste Layer | %s -> %s.' %(self.aux.glyph.activeLayer().name, self.aux.lst_layers.currentItem().text()))
			self.aux.glyph.update()

class QlayerMultiEdit(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QlayerMultiEdit, self).__init__()

		# - Init
		self.aux = aux
		self.backup = {}

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QHBoxLayout()
		self.btn_unfold = QtGui.QPushButton('Unfold Layers')
		self.btn_restore = QtGui.QPushButton('Fold Layers')
		self.btn_restore.setEnabled(False)
		
		self.btn_unfold.setToolTip('Reposition selected layers side by side. Selection order does matter!')
		self.btn_restore.setToolTip('Restore Layer Metrics.')

		self.btn_unfold.clicked.connect(self.unfold)
		self.btn_restore.clicked.connect(self.restore)
				
		self.lay_buttons.addWidget(self.btn_unfold)
		self.lay_buttons.addWidget(self.btn_restore)
		self.addLayout(self.lay_buttons)

	# - Button procedures ---------------------------------------------------
	def unfold(self):
		if self.aux.doCheck() and len(self.aux.lst_layers.selectedItems()) > 1:
			# - Init
			wGlyph = self.aux.glyph

			# - Prepare Backup
			self.backup = {item.text():(wGlyph.getLSB(item.text()), wGlyph.getAdvance(item.text())) for item in self.aux.lst_layers.selectedItems()}
			self.btn_restore.setEnabled(True)

			# - Calculate metrics
			newLSB = 0
			nextLSB = 0
			newAdvance = sum([sum(item) for item in self.backup.values()])
			
			for item in self.aux.lst_layers.selectedItems():
				wLayer = item.text()
				
				newLSB += nextLSB + self.backup[wLayer][0]
				nextLSB = self.backup[wLayer][1]
				
				wGlyph.setLSB(newLSB, wLayer)
				wGlyph.setAdvance(newAdvance, wLayer)
				wGlyph.layer(wLayer).isVisible = True

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Unfold Layers (Side By Side): %s.' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
			self.aux.glyph.update()

	def restore(self):
		if self.aux.doCheck() and len(self.backup.keys()):
			# - Resore metrics
			wGlyph = self.aux.glyph

			for layer, metrics in self.backup.iteritems():
				wGlyph.setLSB(metrics[0], layer)
				wGlyph.setAdvance(metrics[1], layer)
				wGlyph.layer(layer).isVisible = False

			# - Reset
			self.backup = {}
			self.btn_restore.setEnabled(False)

			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Restore Layer metrics: %s.' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
			self.aux.glyph.update()


class QlayerBlend(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QlayerBlend, self).__init__()

		# - Init
		self.aux = aux
		self.currentTime = .0
		self.timeStep = .01

		# - Interface
		# -- Blend active layer to single selected layer
		self.lay_blend = QtGui.QHBoxLayout()
		self.btn_minus = QtGui.QPushButton(' - ')
		self.btn_plus = QtGui.QPushButton(' + ')
		self.btn_minus.setMinimumWidth(75)
		self.btn_plus.setMinimumWidth(75)
		self.btn_minus.clicked.connect(self.blendMinus)
		self.btn_plus.clicked.connect(self.blendPlus)

		self.edt_timeStep = QtGui.QLineEdit()
		self.edt_timeStep.setText(self.timeStep)

		self.btn_minus.setToolTip('Blend Active Layer to selected Layer.\nOriginal Active layer is lost!')
		self.btn_plus.setToolTip('Blend Active Layer to selected Layer.\nOriginal Active layer is lost!')
		self.edt_timeStep.setToolTip('Blend time (0.0 - 1.0) Step.')
		
		self.lay_blend.addWidget(self.btn_minus)
		self.lay_blend.addWidget(QtGui.QLabel('T:'))
		self.lay_blend.addWidget(self.edt_timeStep)
		self.lay_blend.addWidget(self.btn_plus)

		self.addLayout(self.lay_blend)

		# -- Build Axis from current selected layers and send result to active layer

		self.lay_opt = QtGui.QHBoxLayout()
		self.chk_multi = QtGui.QCheckBox('Use Selected Layers as Axis')
		self.chk_multi.stateChanged.connect(self.setCurrentTime)
		self.chk_width = QtGui.QCheckBox('Fixed Width')

		self.chk_multi.setToolTip('Blend selected layers to Active layer.\nUSAGE:\n- Create blank new layer;\n- Select two layers to build Interpolation Axis;\n- Use [+][-] to blend along axis.\nNote:\n- Selection order is important!\n- Checking/unchecking resets the blend position!')
		self.chk_width.setToolTip('Keep current Advance Width')
		
		self.lay_opt.addWidget(self.chk_multi)
		self.lay_opt.addWidget(self.chk_width)
		
		self.addLayout(self.lay_opt)
		
	def setCurrentTime(self):
		self.currentTime = (.0,.0) if isinstance(self.timeStep, tuple) else 0

	def simpleBlend(self, timeStep, currentTime):
		if self.chk_multi.isChecked():
			self.currentTime = tuple(map(sum, zip(self.currentTime, timeStep))) if isinstance(timeStep, tuple) else self.currentTime + timeStep
			blend = self.aux.glyph.blendLayers(self.aux.glyph.layer(self.aux.lst_layers.selectedItems()[0].text()), self.aux.glyph.layer(self.aux.lst_layers.selectedItems()[1].text()), self.currentTime)
		else:
			blend = self.aux.glyph.blendLayers(self.aux.glyph.layer(), self.aux.glyph.layer(self.aux.lst_layers.currentItem().text()), timeStep)
		
		self.aux.glyph.layer().removeAllShapes()
		self.aux.glyph.layer().addShapes(blend.shapes)
		
		if not self.chk_width.isChecked():
			self.aux.glyph.layer().advanceWidth = blend.advanceWidth 
		
		self.aux.glyph.updateObject(self.aux.glyph.fl, 'Blend <t:%s> @ %s.' %(self.currentTime + timeStep, self.aux.glyph.layer().name))
		self.aux.glyph.update()

	def blendMinus(self):
		if self.aux.doCheck():	
			temp_timeStep = self.edt_timeStep.text.replace(' ', '').split(',')
			self.timeStep = -float(temp_timeStep[0]) if len(temp_timeStep) == 1 else tuple([-float(value) for value in temp_timeStep])
			self.simpleBlend(self.timeStep, self.currentTime)

	def blendPlus(self):
		if self.aux.doCheck():	
			temp_timeStep = self.edt_timeStep.text.replace(' ', '').split(',')
			self.timeStep = float(temp_timeStep[0]) if len(temp_timeStep) == 1 else tuple([float(value) for value in temp_timeStep])
			self.simpleBlend(self.timeStep, self.currentTime)
		

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		self.layerSelector = QlayerSelect()
		self.quickTools = QlayerTools(self.layerSelector)
		self.blendTools = QlayerBlend(self.layerSelector)
		self.basicTools = QlayerBasic(self.layerSelector)
		self.unfoldLayers = QlayerMultiEdit(self.layerSelector)

		layoutV.addLayout(self.layerSelector)
		layoutV.addWidget(QtGui.QLabel('Basic Tools (Layers selected)'))
		layoutV.addLayout(self.basicTools)
		layoutV.addWidget(QtGui.QLabel('Content Tools (Active Layer to selection)'))
		layoutV.addLayout(self.quickTools)
		layoutV.addWidget(QtGui.QLabel('Layer Multi-editing'))
		layoutV.addLayout(self.unfoldLayers)
		layoutV.addWidget(QtGui.QLabel('Interpolate/Blend (Active Layer to selection)'))
		layoutV.addWidget(QtGui.QLabel('\nWARN: Disabled due FL6 6722 Bug!'))
		#layoutV.addLayout(self.blendTools)


		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()