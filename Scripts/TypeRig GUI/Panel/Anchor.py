#FLM: TR: Anchor
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.core.base.message import *
from typerig.proxy.fl.objects.glyph import eGlyph

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRCollapsibleBox


# - Init -------------------------
global pLayers
global pMode
global clipboard_glyph_anchors
pLayers = None
pMode = 0
clipboard_glyph_anchors = {}
app_name, app_version = 'TypeRig | Anchors', '2.04'

# - Sub widgets ------------------------
class ALineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(ALineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'add UNDERSCORE', lambda: self.setText('_%s' %self.text))
		menu.addAction(u'add HALF', lambda: self.setText('%s/2' %self.text))
		menu.addSeparator()
		menu.addAction(u'top', lambda: self.setText('top'))
		menu.addAction(u'bottom', lambda: self.setText('bottom'))
		menu.addAction(u'left', lambda: self.setText('left'))
		menu.addAction(u'right', lambda: self.setText('right'))
		menu.addAction(u'width', lambda: self.setText('width'))
		menu.addSeparator()
		menu.addAction(u'baseline', lambda: self.setText('baseline'))
		menu.addAction(u'caps_height', lambda: self.setText('caps_height'))
		menu.addAction(u'x_height', lambda: self.setText('x_height'))
		menu.addAction(u'ascender', lambda: self.setText('ascender'))
		menu.addAction(u'descender', lambda: self.setText('descender'))
		menu.addAction(u'small_caps', lambda: self.setText('small_caps'))

class TRWAnchorTree(QtGui.QTreeWidget):
	def __init__(self, data=None, headers=None):
		super(TRWAnchorTree, self).__init__()
		
		if data is not None:
			self.setTree(data, headers)

		self.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
		self.expandAll()
		self.setAlternatingRowColors(True)

	def setTree(self, data, headers):
		self.blockSignals(True)
		self.clear()
		self.setHeaderLabels(headers)

		# - Insert 
		for key, value in data.items():
			master = QtGui.QTreeWidgetItem(self, [key])

			for sub in value:
				new_item = QtGui.QTreeWidgetItem(master, sub)
				new_item.setFlags(new_item.flags() | QtCore.Qt.ItemIsEditable)

		# - Fit data
		for c in range(self.columnCount):
			self.resizeColumnToContents(c)	

		self.expandAll()
		self.blockSignals(False)

	def getTree(self):
		returnDict = OrderedDict()
		root = self.invisibleRootItem()

		for i in range(root.childCount()):
			item = root.child(i)
			returnDict[item.text(0)] = [[item.child(n).text(c) for c in range(item.child(n).columnCount())] for n in range(item.childCount())]
		
		return returnDict

	def markDiff(self):
		#!!! Ineffecient but will do
		self.blockSignals(True)
		root = self.invisibleRootItem()
		init_diff = []

		for i in range(root.childCount()):
			item = root.child(i)
			init_diff.append([item.child(n).text(0) for n in range(item.childCount())])

		for i in range(root.childCount()):
			item = root.child(i)
			for n in range(item.childCount()):
				if all([item.child(n).text(0) in test for test in init_diff]):
					item.child(n).setData(0, QtCore.Qt.DecorationRole, QtGui.QColor('LimeGreen'))
				else:
					item.child(n).setData(0, QtCore.Qt.DecorationRole, QtGui.QColor('Crimson'))

		self.blockSignals(False)
	

# - Widgets ------------------------------------------------------------
class TRLayerSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(TRLayerSelect, self).__init__()

		# - Init
		self.header_names = ['Layer/Anchor'+' '*5, 'X', 'Y', 'X Exp.', 'Y Exp.']
		self.data = OrderedDict([('Refresh',[])])

		# -- Head
		self.lay_head = QtGui.QHBoxLayout()
		self.edt_glyphName = QtGui.QLineEdit()
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_refresh.clicked.connect(self.refresh)

		self.lay_head.addWidget(QtGui.QLabel('G:'))
		self.lay_head.addWidget(self.edt_glyphName)
		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)
		
		# -- Tree view
		self.tree_anchors = TRWAnchorTree(self.data, self.header_names)
		self.addWidget(self.tree_anchors)

	def refresh(self):
		# - Init
		self.glyph = eGlyph()
		self.edt_glyphName.setText(self.glyph.name)
				
		# - Build Tree and style it
		self.data = [((layer.name), [(anchor.name, int(anchor.point.x()), int(anchor.point.y()), anchor.expressionX, anchor.expressionY) for anchor in self.glyph.anchors(layer.name)]) for layer in self.glyph.masters()]
		self.tree_anchors.setTree(OrderedDict(reversed(self.data)), self.header_names)
		self.tree_anchors.markDiff()

	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			warnings.warn('Glyph mismatch! No action taken! Forcing refresh!', GlyphWarning)
			self.refresh()
			return 0
		return 1

class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		self.anchorSelector = TRLayerSelect()

		self.types = 'Anchor PinPoint'.split(' ')
		self.posY = 'Coord, Expression, Keep, Shift, Above, Below, Center, Baseline, Center of mass'.split(', ')
		self.posX = 'Coord, Expression, Keep, Shift, Left, Right, Center, LSB, RSB, Advance middle, Highest, Highest Left, Highest Right, Lowest, Lowest Left, Lowest Right, Center of mass'.split(', ')
		posYvals = (None, None, 'S', 'S', 'T', 'B', 'C', None, 'W')
		posXvals = (None, None, 'S', 'S', 'L', 'R', 'C', 'LSB', 'RSB', 'ADM', 'AT', 'ATL', 'ATR', 'A', 'AL', 'AR', 'M')
		self.posYctrl = dict(zip(self.posY, posYvals))
		self.posXctrl = dict(zip(self.posX, posXvals))

		# -- Basic Tool buttons
		self.btn_anchorCopy = QtGui.QPushButton('Copy')
		self.btn_anchorPaste = QtGui.QPushButton('Paste')
		self.btn_clearSel = QtGui.QPushButton('Remove')
		self.btn_clearAll = QtGui.QPushButton('Remove All')
		self.btn_anchorAdd = QtGui.QPushButton('Add')
		self.btn_anchorMov = QtGui.QPushButton('Move')
		self.btn_anchorRename = QtGui.QPushButton('Rename')
		self.btn_anchorSuffix = QtGui.QPushButton('Suffix')
		self.btn_anchorCopy.setToolTip('Copy selected Anchors from layers chosen.')
		self.btn_anchorPaste.setToolTip('Paste Anchors at layers chosen.')
		self.btn_anchorRename.setToolTip('Rename selected anchors.')
		self.btn_anchorSuffix.setToolTip('Extend the name of selected Anchors.')
		
		self.chk_italic = QtGui.QCheckBox('Use Italic Angle')

		# -- Edit fields
		self.edt_anchorName = ALineEdit()
		self.edt_simpleX = ALineEdit()
		self.edt_simpleY = ALineEdit()
		self.edt_autoT = QtGui.QLineEdit()

		self.edt_anchorName.setPlaceholderText('New Anchor')
		self.edt_simpleX.setText('0')
		self.edt_simpleY.setText('0')
		self.edt_autoT.setText('5')

		# -- Combo box
		self.cmb_posX = QtGui.QComboBox()
		self.cmb_posY = QtGui.QComboBox()
		self.cmb_type = QtGui.QComboBox()

		self.cmb_posX.addItems(self.posX)
		self.cmb_posY.addItems(self.posY)
		self.cmb_type.addItems(self.types)
		self.cmb_type.setEnabled(False)

		# -- Constrains
		self.btn_clearSel.setMinimumWidth(90)
		self.btn_clearAll.setMinimumWidth(90)
		self.edt_anchorName.setMinimumWidth(50)
		self.edt_simpleX.setMinimumWidth(30)
		self.edt_simpleY.setMinimumWidth(30)

		# -- Link functions
		self.btn_clearAll.clicked.connect(lambda: self.clearAnchors(True))
		self.btn_clearSel.clicked.connect(lambda: self.clearAnchors(False))
		self.btn_anchorAdd.clicked.connect(lambda: self.addAnchors(False))
		self.btn_anchorMov.clicked.connect(lambda: self.addAnchors(True))
		self.btn_anchorCopy.clicked.connect(lambda: self.copyAnchors(False))
		self.btn_anchorPaste.clicked.connect(lambda: self.copyAnchors(True))
		self.btn_anchorSuffix.clicked.connect(lambda: self.renameAnchors(False))
		self.btn_anchorRename.clicked.connect(lambda: self.renameAnchors(True))
		self.anchorSelector.tree_anchors.itemChanged.connect(self.processChange)

		# - Build layout
		layoutV = QtGui.QVBoxLayout()
		layoutV.addLayout(self.anchorSelector)

		self.fld_actions = TRCollapsibleBox('Anchor actions:')
		lay_actions = QtGui.QGridLayout()
		
		lay_actions.addWidget(self.btn_anchorCopy, 				0, 0, 1, 4) 
		lay_actions.addWidget(self.btn_anchorPaste, 			0, 4, 1, 4)
		lay_actions.addWidget(self.btn_clearSel, 				1, 0, 1, 4) 
		lay_actions.addWidget(self.btn_clearAll, 				1, 4, 1, 4)

		self.fld_actions.setContentLayout(lay_actions)
		layoutV.addWidget(self.fld_actions)

		self.fld_addmod = TRCollapsibleBox('Add/Move anchor:')
		lay_addmod = QtGui.QGridLayout()
		
		lay_addmod.addWidget(QtGui.QLabel('N:'),				0, 0, 1, 1)
		lay_addmod.addWidget(self.edt_anchorName, 				0, 1, 1, 3)
		lay_addmod.addWidget(self.cmb_type, 					0, 4, 1, 4)
		lay_addmod.addWidget(QtGui.QLabel('X:'),				1, 0, 1, 1)
		lay_addmod.addWidget(self.cmb_posX, 					1, 1, 1, 3)
		lay_addmod.addWidget(self.edt_simpleX, 					1, 4, 1, 4)
		lay_addmod.addWidget(QtGui.QLabel('Y:'),				2, 0, 1, 1)
		lay_addmod.addWidget(self.cmb_posY,						2, 1, 1, 3)
		lay_addmod.addWidget(self.edt_simpleY, 					2, 4, 1, 4)
		lay_addmod.addWidget(QtGui.QLabel('Tolerance:'),		3, 1, 1, 2)
		lay_addmod.addWidget(self.edt_autoT, 					3, 3, 1, 1)
		lay_addmod.addWidget(self.chk_italic,					3, 4, 1, 1)		
		lay_addmod.addWidget(self.btn_anchorAdd, 				4, 0, 1, 4)
		lay_addmod.addWidget(self.btn_anchorMov, 				4, 4, 1, 4)
		lay_addmod.addWidget(self.btn_anchorRename, 			5, 0, 1, 4)
		lay_addmod.addWidget(self.btn_anchorSuffix, 			5, 4, 1, 4)

		self.fld_addmod.setContentLayout(lay_addmod)
		layoutV.addWidget(self.fld_addmod)

		# - Finish
		self.setLayout(layoutV)
		self.setMinimumSize(300, self.sizeHint.height())

	# -- Procedures --------------------------
	def processChange(self, item):
		update = False
		parent = item.parent()
		change_index = parent.indexOfChild(item)
		data_dict = OrderedDict(reversed(self.anchorSelector.data))

		layer_name = parent.text(0)
		old_name, old_x, old_y, old_x_expr, old_y_expr = data_dict[layer_name][change_index]
		anchor_name, x, y, x_expr, y_expr = item.text(0), int(item.text(1)), int(item.text(2)), item.text(3), item.text(4)

		if anchor_name != old_name:
			self.anchorSelector.glyph.layer(layer_name).findAnchor(old_name).name = anchor_name
			update = True

		if x != old_x or y != old_y:
			self.anchorSelector.glyph.moveAnchor(anchor_name, layer_name, (x, y), (None, None), 5, False)
			update = True

		if x_expr != old_x_expr or y_expr != old_y_expr:
			self.anchorSelector.glyph.exprAnchor(anchor_name, layer_name, x_expr, y_expr)
			update = True

		if update:
			self.anchorSelector.glyph.update()
			self.anchorSelector.glyph.updateObject(self.anchorSelector.glyph.fl, 'Change anchor: %s @ %s.' %(anchor_name, layer_name))
			self.anchorSelector.refresh()
		
	def clearAnchors(self, clearAll=False):
		wLayers = self.anchorSelector.glyph._prepareLayers(pLayers)

		if self.anchorSelector.doCheck():			
			if clearAll:
				for layer in wLayers:
					self.anchorSelector.glyph.clearAnchors(layer)

			else:
				for item in self.anchorSelector.tree_anchors.selectedItems():
					cAnchorName = item.text(0)
					cLayerName = item.parent().text(0)
					
					findAnchor = self.anchorSelector.glyph.layer(cLayerName).findAnchor(cAnchorName)
										
					if findAnchor is not None:
						 self.anchorSelector.glyph.layer(cLayerName).removeAnchor(findAnchor)

			self.anchorSelector.glyph.updateObject(self.anchorSelector.glyph.fl, 'Clear anchors: %s.' %'; '.join(wLayers))
			self.anchorSelector.glyph.update()
			self.anchorSelector.refresh()

	def addAnchors(self, move=False):
		wLayers = self.anchorSelector.glyph._prepareLayers(pLayers)

		if self.anchorSelector.doCheck():			
			update = False

			# - Build coordinates for every layer
			x_coord = self.edt_simpleX.text.replace(' ','').split(',') if ',' in self.edt_simpleX.text else [self.edt_simpleX.text]*len(wLayers)
			y_coord = self.edt_simpleY.text.replace(' ','').split(',') if ',' in self.edt_simpleY.text else [self.edt_simpleY.text]*len(wLayers)

			# - Process
			autoTolerance = int(self.edt_autoT.text)

			for layer in wLayers:
				try:
					offsetX = int(x_coord[wLayers.index(layer)]) if self.cmb_posX.currentText != 'Expression' else 0
					offsetY = int(y_coord[wLayers.index(layer)]) if self.cmb_posY.currentText != 'Expression' else 0
				
				except ValueError:
					offsetX = 0
					offsetY = 0

				if not move:
					if len(self.edt_anchorName.text):
						self.anchorSelector.glyph.dropAnchor(self.edt_anchorName.text, layer, (offsetX, offsetY), (self.posXctrl[self.cmb_posX.currentText], self.posYctrl[self.cmb_posY.currentText]), autoTolerance, self.chk_italic.isChecked())
					
					if self.cmb_posX.currentText == 'Expression' or self.cmb_posY.currentText == 'Expression':
						self.anchorSelector.glyph.exprAnchor(self.edt_anchorName.text, layer, x_coord[wLayers.index(layer)], y_coord[wLayers.index(layer)])
					
						update = True
				else:
					cmb_sel = self.anchorSelector.tree_anchors.selectedItems()

					if len(cmb_sel):
						self.anchorSelector.glyph.moveAnchor(cmb_sel[0].text(0), layer, (offsetX, offsetY), (self.posXctrl[self.cmb_posX.currentText], self.posYctrl[self.cmb_posY.currentText]), autoTolerance, self.chk_italic.isChecked())
						
						if self.cmb_posX.currentText == 'Expression' or self.cmb_posX.currentText == 'Expression':
							self.anchorSelector.glyph.exprAnchor(cmb_sel[0].text(0), layer, x_coord[wLayers.index(layer)], y_coord[wLayers.index(layer)])

						update = True

			if update:
				self.anchorSelector.glyph.updateObject(self.anchorSelector.glyph.fl, '%s anchors: %s.' %('Add' if not move else 'Move', '; '.join(wLayers)))
				self.anchorSelector.glyph.update()
				self.anchorSelector.refresh()

	def copyAnchors(self, paste=False):
		global clipboard_glyph_anchors
		wLayers = self.anchorSelector.glyph._prepareLayers(pLayers)

		if self.anchorSelector.doCheck():			
			if not paste:
				update = False
				clipboard_glyph_anchors = {}
				
				for layer in wLayers:
					clipboard_glyph_anchors[layer] = []

					for anchor_name in self.anchorSelector.tree_anchors.selectedItems():
						anchor_obj = self.anchorSelector.glyph.findAnchor(anchor_name.text(0), layer)

						if anchor_obj is not None:
							clipboard_glyph_anchors[layer].append((anchor_name.text(0), (anchor_obj.point.x(), anchor_obj.point.y()), (anchor_obj.expressionX, anchor_obj.expressionY)))
				
			else:
				if len(clipboard_glyph_anchors.keys()):
					update = True

					for layer, layer_anchors in clipboard_glyph_anchors.items():

						for anchor_name, anchor_coords, anchor_expression in layer_anchors:
							if self.anchorSelector.glyph.findAnchor(anchor_name, layer) is None:
								self.anchorSelector.glyph.dropAnchor(anchor_name, layer, anchor_coords)
							else:
								self.anchorSelector.glyph.moveAnchor(anchor_name, layer, anchor_coords)
							
							self.anchorSelector.glyph.exprAnchor(anchor_name, layer, anchor_expression[0], anchor_expression[1])
			
			if update:
				self.anchorSelector.glyph.updateObject(self.anchorSelector.glyph.fl, '%s anchors: %s.' %('Copy' if not paste else 'Paste', '; '.join(wLayers)))
				self.anchorSelector.glyph.update()
				self.anchorSelector.refresh()

	def renameAnchors(self, rename=True):
		wLayers = self.anchorSelector.glyph._prepareLayers(pLayers)

		if self.anchorSelector.doCheck():	
			update = False		

			for layer in wLayers:
				
				for anchor_name in self.anchorSelector.tree_anchors.selectedItems():
					anchor = self.anchorSelector.glyph.findAnchor(anchor_name.text(0), layer)
					
					if anchor is not None:
						if len(self.edt_anchorName.text):
							anchor.name = self.edt_anchorName.text if rename else anchor.name + self.edt_anchorName.text
							update = True
						else:
							output(2,app_name, 'No input string given for anchor %s.' %anchor.name)
		
			if update:
				self.anchorSelector.glyph.updateObject(self.anchorSelector.glyph.fl, '%s anchors: %s.' %('Rename' if rename else 'Extend name of', '; '.join(wLayers)))
				self.anchorSelector.glyph.update()
				self.anchorSelector.refresh()

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()