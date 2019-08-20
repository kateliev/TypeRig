#FLM: Glyph: Layers
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
from typerig.gui import trSliderCtrl
from itertools import groupby
from math import radians

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Layers', '0.36'

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
		self.btn_del = QtGui.QPushButton('Remove')
		self.btn_dup = QtGui.QPushButton('Duplicate')
		self.btn_setServ = QtGui.QPushButton('Service')
		self.btn_setMask = QtGui.QPushButton('Mask')
		self.btn_setWire = QtGui.QPushButton('Wireframe')
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
		self.btn_setMask.clicked.connect(self.addMaskLayers)

		self.btn_setServ.clicked.connect(lambda: self.setLayer('Service'))
		self.btn_setWire.clicked.connect(lambda: self.setLayer('Wireframe'))

		self.lay_buttons.addWidget(QtGui.QLabel('Suffix/Name:'),	0, 0, 1, 1)
		self.lay_buttons.addWidget(self.edt_name, 					0, 1, 1, 2)
		self.lay_buttons.addWidget(self.btn_add, 					1, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_del, 					1, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_dup, 					1, 2, 1, 1)
		self.lay_buttons.addWidget(self.btn_setServ, 				2, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_setMask, 				2, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_setWire, 				2, 2, 1, 1)
	 
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

	def addMaskLayers(self):	
		if self.aux.doCheck():	
			for item in self.aux.lst_layers.selectedItems():
				# - Build mask layer
				srcShapes = self.aux.glyph.shapes(item.text())
				newMaskLayer = self.aux.glyph.layer(item.text()).getMaskLayer(True)			

				# - Copy shapes to mask layer
				for shape in srcShapes:
					newMaskLayer.addShape(shape.cloneTopLevel()) # Clone so that the shapes are NOT referenced, but actually copied!
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'New Mask Layer: %s.' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
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
		self.lay_checks.addWidget(self.chk_guides, 	0, 1)
		self.lay_checks.addWidget(self.chk_anchors, 0, 2)
		self.lay_checks.addWidget(self.chk_lsb, 	1, 0)
		self.lay_checks.addWidget(self.chk_adv, 	1, 1)
		self.lay_checks.addWidget(self.chk_rsb, 	1, 2)
		
		self.addLayout(self.lay_checks)

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_swap = QtGui.QPushButton('Swap')
		self.btn_copy = QtGui.QPushButton('Copy')
		self.btn_paste = QtGui.QPushButton('Paste')
		self.btn_clean = QtGui.QPushButton('Remove')
		self.btn_unlock = QtGui.QPushButton('Unlock')
		self.btn_expand = QtGui.QPushButton('Expand')

		#self.btn_unlock.setEnabled(False)
		self.btn_expand.setEnabled(False)
		
		self.btn_swap.setToolTip('Swap Selected Layer with Active Layer')
		self.btn_copy.setToolTip('Copy Active Layer to Selected Layer')
		self.btn_paste.setToolTip('Paste Selected Layer to Active Layer')
		self.btn_clean.setToolTip('Remove contents from selected layers')
		self.btn_unlock.setToolTip('Unlock all locked references.\nSHIFT+Click will lock all references.')
		self.btn_expand.setToolTip('Expand transformations for selected layers')

		self.btn_swap.clicked.connect(self.swap)
		self.btn_copy.clicked.connect(self.copy)
		self.btn_paste.clicked.connect(self.paste)
		self.btn_clean.clicked.connect(self.clean)
		self.btn_unlock.clicked.connect(self.unlock)
		#self.btn_expand.clicked.connect(self.expand)
				
		self.lay_buttons.addWidget(self.btn_swap,	0, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_copy,	0, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_paste,	0, 2, 1, 1)
		self.lay_buttons.addWidget(self.btn_clean,	1, 0, 1, 1)
		self.lay_buttons.addWidget(self.btn_unlock,	1, 1, 1, 1)
		self.lay_buttons.addWidget(self.btn_expand,	1, 2, 1, 1)

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
			glyph.layer(dstLayerName).addShape(shape.cloneTopLevel())

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

		glyph.layer(dstLayerName).appendGuidelines(glyph.guidelines(srcLayerName))

	def Copy_Paste_Layer_Anchors(self, glyph, layerName, copy=True, cleanDST=False, impSRC=[]):
		srcLayerName = layerName if copy else None # Note: None refers to activeLayer
		dstLayerName = None if copy else layerName
		exportDSTAnchors = None

		# -- Get anchors
		srcAnchors = glyph.anchors(srcLayerName) if len(impSRC) == 0 else impSRC

		# -- Cleanup !!! Not working
		if cleanDST:
			exportDSTAnchors = glyph.anchors(dstLayerName)

			for anchor in glyph.anchors(dstLayerName):
					glyph.layer(dstLayerName).removeAnchor(anchor)

		for anchor in srcAnchors:
				glyph.anchors(dstLayerName).append(anchor)

		return exportDSTAnchors

	# - Button procedures ---------------------------------------------------
	def unlock(self):
		if self.aux.doCheck():
			modifiers = QtGui.QApplication.keyboardModifiers()

			if self.chk_outline.isChecked():
				for item in self.aux.lst_layers.selectedItems():
					for shape in self.aux.glyph.shapes(item.text()):
						
						if modifiers == QtCore.Qt.ShiftModifier: # Shift + Click will lock
							shape.contentLocked = True
						else:
							shape.contentLocked = False

			self.aux.glyph.updateObject(self.aux.glyph.fl, '%s shapes on Layer(s) | %s' %(['Unlock', 'Lock'][modifiers == QtCore.Qt.ShiftModifier],'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()])))
			self.aux.glyph.update()


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

	def clean(self):
		if self.aux.doCheck():	
			if self.chk_outline.isChecked():
				for item in self.aux.lst_layers.selectedItems():
					self.aux.glyph.layer(item.text()).removeAllShapes()

			if self.chk_guides.isChecked():
				pass # TODO!!!!!

			if self.chk_anchors.isChecked():
				pass # TODO!!!!!
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Clean Layer(s) | %s' %'; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
			self.aux.glyph.update()

class QlayerMultiEdit(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QlayerMultiEdit, self).__init__()

		# - Init
		self.aux = aux
		self.backup = {}
		self.contourClipboard = {}

		# -- Edit fileds
		self.edt_shift = QtGui.QLineEdit('0.0, 0.0')
		self.edt_scale = QtGui.QLineEdit('100, 100')
		self.edt_slant = QtGui.QLineEdit('0.0')
		self.edt_rotate = QtGui.QLineEdit('0.0')

		self.edt_shift.setToolTip('Translate Layer by X, Y (comma separated)')
		self.edt_scale.setToolTip('Scale Layer by X percent, Y percent(comma separated)')
		self.edt_slant.setToolTip('Slant/Shear degrees')
		self.edt_rotate.setToolTip('Rotate degrees')

		# -- Quick Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_unfold = QtGui.QPushButton('Unfold Layers')
		self.btn_restore = QtGui.QPushButton('Fold Layers')
		self.btn_copy = QtGui.QPushButton('Copy Outline')
		self.btn_paste = QtGui.QPushButton('Paste Outline')
		self.btn_transform = QtGui.QPushButton('Transform Layer')
		self.btn_transform_shape = QtGui.QPushButton('Transform Elements')

		self.btn_restore.setEnabled(False)
		self.btn_paste.setEnabled(False)
		
		self.btn_unfold.setToolTip('Reposition selected layers side by side. Selection order does matter!')
		self.btn_restore.setToolTip('Restore Layer Metrics.')
		self.btn_copy.setToolTip('Copy selected outline to cliboard for each of selected layers.')
		self.btn_paste.setToolTip('Paste outline from cliboard layer by layer (by name). Non existing layers are discarded! New Element is created upon Paste!')
		self.btn_transform.setToolTip('Affine transform selected layers')

		self.btn_unfold.clicked.connect(self.unfold)
		self.btn_restore.clicked.connect(self.restore)
		self.btn_copy.clicked.connect(self.copy)
		self.btn_paste.clicked.connect(self.paste)
		self.btn_transform.clicked.connect(lambda: self.transform(False))
		self.btn_transform_shape.clicked.connect(lambda: self.transform(True))
				
		self.lay_buttons.addWidget(self.btn_unfold,				0, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_restore,			0, 4, 1, 4)
		self.lay_buttons.addWidget(self.btn_copy,				1, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_paste,				1, 4, 1, 4)
		self.lay_buttons.addWidget(QtGui.QLabel('Translate:'),	2, 0, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Scale:'),		2, 2, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Shear:'),		2, 4, 1, 2)
		self.lay_buttons.addWidget(QtGui.QLabel('Rotate:'),		2, 6, 1, 2)
		self.lay_buttons.addWidget(self.edt_shift,				3, 0, 1, 2)
		self.lay_buttons.addWidget(self.edt_scale,				3, 2, 1, 2)
		self.lay_buttons.addWidget(self.edt_slant,				3, 4, 1, 2)
		self.lay_buttons.addWidget(self.edt_rotate,				3, 6, 1, 2)
		self.lay_buttons.addWidget(self.btn_transform,			4, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_transform_shape,	4, 4, 1, 4)

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

	def copy(self):
		# - Init
		wGlyph = self.aux.glyph
		wContours = wGlyph.contours()
		self.contourClipboard = {}
		
		# - Build initial contour information
		selectionTuples = wGlyph.selectedAtContours()
		selection = {key:[item[1] for item in value] if not wContours[key].isAllNodesSelected() else [] for key, value in groupby(selectionTuples, lambda x:x[0])}

		
		if len(selection.keys()):
			self.btn_paste.setEnabled(True)
						
			for item in self.aux.lst_layers.selectedItems():
				wLayer = item.text()
				self.contourClipboard[wLayer] = []

				for cid, nList in selection.iteritems():
					if len(nList):
						 self.contourClipboard[wLayer].append(fl6.flContour([wGlyph.nodes(wLayer)[nid].clone() for nid in nList]))
					else:
						self.contourClipboard[wLayer].append(wGlyph.contours(wLayer)[cid].clone())


			print 'DONE:\t Copy outline; Glyph: %s; Layers: %s.' %(self.aux.glyph.fl.name, '; '.join([item.text() for item in self.aux.lst_layers.selectedItems()]))
		
	def paste(self):
		wGlyph = self.aux.glyph

		if len(self.contourClipboard.keys()):
			for layerName, contours in self.contourClipboard.iteritems():
				wLayer = wGlyph.layer(layerName)

				if wLayer is not None:
					newShape = fl6.flShape()
					newShape.addContours(contours, True)
					wLayer.addShape(newShape)			
			
			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Paste outline; Glyph: %s; Layers: %s' %(self.aux.glyph.fl.name, '; '.join([item.text() for item in self.aux.lst_layers.selectedItems()])))
			self.aux.glyph.update()

	def transform(self, shapes=False):
		if self.aux.doCheck() and len(self.aux.lst_layers.selectedItems()):
			
			# - Init
			wGlyph = self.aux.glyph

			inpShift = self.edt_shift.text.split(',') if len(self.edt_shift.text) and ',' in self.edt_shift.text else '0.0, 0.0'
			inpScale = self.edt_scale.text.split(',') if len(self.edt_scale.text) and ',' in self.edt_scale.text else '100, 100'

			wSift_x = float(inpShift[0].strip())
			wSift_y = float(inpShift[1].strip())

			wScale_x = float(inpScale[0].strip())/100
			wScale_y = float(inpScale[1].strip())/100

			wSlant =  radians(float(self.edt_slant.text.strip())) if len(self.edt_slant.text) else 0.
			wRotate =  -float(self.edt_rotate.text.strip()) if len(self.edt_rotate.text) else 0.
			
			# m11, m12, m13, m21, m22, m23, m31, m32, m33 = 1
			# ! Note: wrong but will do...
			new_transform = QtGui.QTransform().scale(wScale_x, wScale_y).rotate(wRotate).shear(wSlant, 0).translate(wSift_x, wSift_y)
			
			for item in self.aux.lst_layers.selectedItems():
				wLayer = wGlyph.layer(item.text())
				
				if not shapes:
					# - Transform at origin
					wBBox = wLayer.boundingBox
					wCenter = (wBBox.width()/2 + wBBox.x(), wBBox.height()/2 + wBBox.y())
					transform_to_origin = QtGui.QTransform().translate(-wCenter[0], -wCenter[1])
					transform_from_origin = QtGui.QTransform().translate(*wCenter)
					
					# - Transform
					wLayer.applyTransform(transform_to_origin)
					wLayer.applyTransform(new_transform)
					wLayer.applyTransform(transform_from_origin)
				else:
					wShapes = wGlyph.shapes(item.text())
					
					for shape in wShapes:
						# - Transform at origin and move to new location according to transformation
						wBBox = shape.boundingBox
						wCenter = (wBBox.width()/2 + wBBox.x(), wBBox.height()/2 + wBBox.y())
						newCenter = new_transform.map(QtCore.QPointF(*wCenter))

						transform_to_origin = QtGui.QTransform().translate(-wCenter[0], -wCenter[1])
						transform_from_origin = QtGui.QTransform().translate(newCenter.x(), wCenter[1])
						#transform_from_origin = QtGui.QTransform().translate(*wCenter)

						# - Transform
						shape.applyTransform(transform_to_origin)
						shape.applyTransform(new_transform)
						shape.applyTransform(transform_from_origin)


			self.aux.glyph.updateObject(self.aux.glyph.fl, ' Glyph: %s; Transform Layers: %s' %(self.aux.glyph.fl.name, '; '.join([item.text() for item in self.aux.lst_layers.selectedItems()])))
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
		layoutV.addWidget(QtGui.QLabel('Layer Multi-editing (Layers selected)'))
		layoutV.addLayout(self.unfoldLayers)
		layoutV.addWidget(QtGui.QLabel('Interpolate/Blend (Active Layer to selection)'))
		#layoutV.addWidget(QtGui.QLabel('\nWARN: Disabled due FL6 6722 Bug!'))
		layoutV.addLayout(self.blendTools)


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