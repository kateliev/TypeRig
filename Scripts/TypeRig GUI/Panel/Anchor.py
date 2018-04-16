#FLM: TAB Anchor Tools
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
app_name, app_version = 'TypeRig | Anchors', '0.06'

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
		menu.addAction(u'top', lambda: self.setText('top'))
		menu.addAction(u'bottom', lambda: self.setText('bottom'))
		menu.addAction(u'left', lambda: self.setText('left'))
		menu.addAction(u'right', lambda: self.setText('right'))
		menu.addAction(u'baseline', lambda: self.setText('baseline'))
		menu.addAction(u'caps', lambda: self.setText('caps'))
		menu.addAction(u'xheight', lambda: self.setText('xheight'))
		menu.addAction(u'ascender', lambda: self.setText('ascender'))
		menu.addAction(u'descender', lambda: self.setText('descender'))		

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
		self.lst_anchors = QtGui.QListWidget()
		self.lst_anchors.setAlternatingRowColors(True)
		self.lst_anchors.setMinimumHeight(100)
		self.lst_anchors.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.addWidget(self.lst_anchors)
		self.refresh()

	def refresh(self):
		# - Init
		self.glyph = eGlyph()
		self.wLayers = self.glyph._prepareLayers(pLayers)
		
		# - Prepare
		self.wAnchors = {}
		self.wAnchorNames = []		
		for layer in self.wLayers:
			currAnchors = self.glyph.anchors(layer) 
			self.wAnchors[layer] = currAnchors
			self.wAnchorNames.append([anchor.name for anchor in currAnchors])
		
		self.edt_glyphName.setText(self.glyph.name)
		self.lst_anchors.clear()
					
		# - Build List and style it
		self.lst_anchors.addItems(list(set(sum(self.wAnchorNames, []))))		

		for index in range(self.lst_anchors.count):
			currItem = self.lst_anchors.item(index)
			
			checkLayers = [currItem.text() in name for name in self.wAnchorNames]
			toolTip = 'Anchor present in all selected layers.' if all(checkLayers) else 'Anchor NOT present in all selected layers.'

			currItem.setData(QtCore.Qt.DecorationRole, QtGui.QColor('LimeGreen' if all(checkLayers) else 'Crimson'))
			currItem.setData(QtCore.Qt.ToolTipRole, toolTip)		

	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			print '\nERRO:\tGlyph mismatch:\n\tCurrent active glyph: %s\n\tLayers panel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg)
			print 'WARN:\tNo action taken! Forcing refresh!' 
			self.refresh()
			#raise Exception('Glyph mismatch')
			return 0
		return 1

class QanchorBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QanchorBasic, self).__init__()

		# - Init
		self.aux = aux
		self.positions = ['above', 'baseline', 'below']
		self.types = ['anchor']

		# -- Basic Tool buttons
		self.lay_buttons = QtGui.QGridLayout()
		self.btn_clearSel = QtGui.QPushButton('Clear Selected')
		self.btn_clearAll = QtGui.QPushButton('Clear All')
		self.btn_simpleAdd = QtGui.QPushButton('Add (&Exact)')
		self.btn_autoAdd = QtGui.QPushButton('Add (&Auto)')

		# -- Edit fields
		self.edt_anchorName = ALineEdit()
		self.edt_simpleX = QtGui.QLineEdit()
		self.edt_simpleY = QtGui.QLineEdit()
		self.edt_autoY = QtGui.QLineEdit()
		self.edt_autoT = QtGui.QLineEdit()

		self.edt_anchorName.setPlaceholderText('Name')
		self.edt_simpleX.setText('0')
		self.edt_simpleY.setText('0')
		self.edt_autoY.setText('0')
		self.edt_autoT.setText('5')

		# -- Combo box
		self.cmb_pos = QtGui.QComboBox()
		self.cmb_type = QtGui.QComboBox()

		self.cmb_pos.addItems(self.positions)
		self.cmb_type.addItems(self.types)
		self.cmb_type.setEnabled(False)

		# -- Constrains
		self.btn_clearSel.setMinimumWidth(100)
		self.btn_clearAll.setMinimumWidth(100)
		self.edt_anchorName.setMinimumWidth(90)
		self.edt_simpleX.setMinimumWidth(30)
		self.edt_simpleY.setMinimumWidth(30)
		self.edt_autoY.setMinimumWidth(30)
		self.edt_autoT.setMaximumWidth(30)
		#self.btn_autoAdd.setMinimumWidth(80)

		# -- Tooltips
		self.cmb_pos.setToolTip('New Anchor vertical position according to glyph outline.')
		self.edt_autoY.setToolTip('Vertical offset from selected position. ')
		self.edt_autoT.setToolTip('Feature search tolerance.\nEverything above the given value is not considered "horizontal"')
		self.btn_autoAdd.setToolTip('Add Anchor to all selected layers, by:\n- Detecting prominent horizontal based features - Stem/stem cap, Apex, Vertex, Extreme and etc.)\n- Filtering the features within given offset (drawing errors or stroke incline and etc.)\n- Vertical placing the anchor with given offset to feature selected, according to outline BBOX')
		self.btn_simpleAdd.setToolTip('Add Anchor to all selected layers at given exact coordinates.')

		# -- Link functions
		self.btn_clearAll.clicked.connect(lambda: self.clearAnchors(True))
		self.btn_clearSel.clicked.connect(lambda: self.clearAnchors(False))
		self.btn_simpleAdd.clicked.connect(lambda: self.addAnchors(False))
		self.btn_autoAdd.clicked.connect(lambda: self.addAnchors(True))

		# - Build layout
		self.lay_buttons.addWidget(self.btn_clearSel, 		0, 0, 1, 4)
		self.lay_buttons.addWidget(self.btn_clearAll, 		0, 4, 1, 4)

		self.lay_buttons.addWidget(QtGui.QLabel('New:'),	1, 0, 1, 1)
		self.lay_buttons.addWidget(self.edt_anchorName, 	1, 1, 1, 3)
		self.lay_buttons.addWidget(self.cmb_type, 			1, 4, 1, 4)

		self.lay_buttons.addWidget(QtGui.QLabel('At X:'),	2, 0, 1, 1)
		self.lay_buttons.addWidget(self.edt_simpleX, 		2, 1, 1, 1)
		self.lay_buttons.addWidget(QtGui.QLabel('Y:'),	2, 2, 1, 1)
		self.lay_buttons.addWidget(self.edt_simpleY, 		2, 3, 1, 1)
		self.lay_buttons.addWidget(self.btn_simpleAdd, 		2, 4, 1, 4)

		self.lay_buttons.addWidget(QtGui.QLabel('At Y:'),		3, 0, 1, 1)
		self.lay_buttons.addWidget(self.edt_autoY, 			3, 1, 1, 1)
		self.lay_buttons.addWidget(self.cmb_pos,			3, 2, 1, 2)
		#self.lay_buttons.addWidget(QtGui.QLabel('T:'),		3, 4, 1, 1)
		self.lay_buttons.addWidget(self.edt_autoT, 			3, 4, 1, 1)
		self.lay_buttons.addWidget(self.btn_autoAdd, 		3, 5, 1, 3)

		# - Build
		self.addLayout(self.lay_buttons)

	def clearAnchors(self, clearAll=False):
		if self.aux.doCheck():			
			if clearAll:
				for layer in self.aux.wLayers:
					self.aux.glyph.clearAnchors(layer)

			else:
				for item in self.aux.lst_anchors.selectedItems():
					cAnchorName = item.text()
					
					for layer in self.aux.wLayers:
						findAnchor = self.aux.glyph.layer(layer).findAnchor(cAnchorName)
											
						if findAnchor is not None:
							 self.aux.glyph.layer(layer).removeAnchor(findAnchor)


			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Clear anchors: %s.' %'; '.join(self.aux.wLayers))
			self.aux.glyph.update()
			self.aux.refresh()

	def addAnchors(self, auto=False):
		if self.aux.doCheck():
			if len(self.edt_anchorName.text):
				if not auto:
					for layer in self.aux.wLayers:
						coords = (int(self.edt_simpleX.text), int(self.edt_simpleY.text))
						self.aux.glyph.addAnchor(coords, self.edt_anchorName.text, layer)
				else:
					offsetY = int(self.edt_autoY.text)
					autoTolerance = int(self.edt_autoT.text)

					for layer in self.aux.wLayers:
						bbox = self.aux.glyph.layer(layer).boundingBox

						if self.cmb_pos.currentText == self.positions[0]:
							currPos = bbox.height() + bbox.y() + offsetY
							alignTop = True

						elif self.cmb_pos.currentText == self.positions[1]:
							currPos = offsetY
							alignTop = False

						elif self.cmb_pos.currentText == self.positions[2]:
							currPos = bbox.y() + offsetY*[1,-1][bbox.y() < 0]
							alignTop = False

						self.aux.glyph.dropAnchor(currPos, self.edt_anchorName.text, alignTop, layer, autoTolerance)

				self.aux.glyph.updateObject(self.aux.glyph.fl, 'Add anchors: %s.' %'; '.join(self.aux.wLayers))
				self.aux.glyph.update()
				self.aux.refresh()
		
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		self.anchorSelector = QlayerSelect()
		self.basicTools = QanchorBasic(self.anchorSelector)
		
		layoutV.addLayout(self.anchorSelector)
		#layoutV.addWidget(QtGui.QLabel('Basic Tools:'))
		layoutV.addLayout(self.basicTools)
		
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