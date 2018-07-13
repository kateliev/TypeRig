#FLM: TAB Metric Tools
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Metrics', '0.13'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Sub widgets ------------------------
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

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'EQ', lambda: self.setText('=%s' %self.text))
		menu.addAction(u'LSB', lambda: self.setText('=lsb("%s")' %self.text))
		menu.addAction(u'RSB', lambda: self.setText('=rsb("%s")' %self.text))
		menu.addAction(u'ADV', lambda: self.setText('=width("%s")' %self.text))
		menu.addAction(u'L', lambda: self.setText('=l("%s")' %self.text))
		menu.addAction(u'R', lambda: self.setText('=r("%s")' %self.text))
		menu.addAction(u'W', lambda: self.setText('=w("%s")' %self.text))
		menu.addAction(u'G', lambda: self.setText('=g("%s")' %self.text))	
		
class metrics_adjust(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_adjust, self).__init__()
		# - Spin Boxes
		self.spb_lsb_percent =  QtGui.QSpinBox()
		self.spb_adv_percent = QtGui.QSpinBox()
		self.spb_rsb_percent = QtGui.QSpinBox()
		self.spb_lsb_units =  QtGui.QSpinBox()
		self.spb_adv_units = QtGui.QSpinBox()
		self.spb_rsb_units = QtGui.QSpinBox()

		self.spb_lsb_percent.setMaximum(200)
		self.spb_adv_percent.setMaximum(200)
		self.spb_rsb_percent.setMaximum(200)
		self.spb_lsb_units.setMaximum(200)
		self.spb_adv_units.setMaximum(200)
		self.spb_rsb_units.setMaximum(200)
		self.spb_lsb_units.setMinimum(-200)
		self.spb_adv_units.setMinimum(-200)
		self.spb_rsb_units.setMinimum(-200)

		self.spb_lsb_percent.setSuffix('%')
		self.spb_adv_percent.setSuffix('%')
		self.spb_rsb_percent.setSuffix('%')
		self.spb_lsb_units.setSuffix(' u')
		self.spb_adv_units.setSuffix(' u')
		self.spb_rsb_units.setSuffix(' u')

		self.resetSpinBox()

		# - Buttons
		self.btn_adjMetrics = QtGui.QPushButton('&Adjust Metrics')
		self.btn_resetSpinBox = QtGui.QPushButton('&Reset')
		self.btn_adjMetrics.clicked.connect(self.adjMetrics)
		self.btn_resetSpinBox.clicked.connect(self.resetSpinBox)

		self.addWidget(QtGui.QLabel('LSB adjust:'), 	0, 0, 1, 1)
		self.addWidget(QtGui.QLabel('RSB adjust:'), 	0, 1, 1, 1)
		self.addWidget(QtGui.QLabel('ADV adjust:'), 	0, 2, 1, 1)
		self.addWidget(self.spb_lsb_percent, 	1, 0, 1, 1)
		self.addWidget(self.spb_rsb_percent, 	1, 1, 1, 1)
		self.addWidget(self.spb_adv_percent, 	1, 2, 1, 1)

		self.addWidget(self.spb_lsb_units, 		2, 0, 1, 1)
		self.addWidget(self.spb_rsb_units, 		2, 1, 1, 1)
		self.addWidget(self.spb_adv_units, 		2, 2, 1, 1)

		self.addWidget(self.btn_resetSpinBox, 	3, 0, 1, 1)
		self.addWidget(self.btn_adjMetrics, 	3, 1, 1, 2)

	def resetSpinBox(self):
		# - Reset spin-box values
		self.spb_lsb_percent.setValue(100)
		self.spb_adv_percent.setValue(100)
		self.spb_rsb_percent.setValue(100)
		self.spb_lsb_units.setValue(0)
		self.spb_adv_units.setValue(0)
		self.spb_rsb_units.setValue(0)

	def adjMetrics(self):
		# - Dumb but working - next time do better!
		glyph = eGlyph()
		
		copyOrder = [False]*3
		srcGlyphs = [glyph.name]*3
				
		adjPercents = (self.spb_lsb_percent.value, self.spb_rsb_percent.value, self.spb_adv_percent.value)
		adjUnits = (self.spb_lsb_units.value, self.spb_rsb_units.value, self.spb_adv_units.value)
		
		glyph.copyMetricsbyName(srcGlyphs, pLayers, copyOrder, adjPercents, adjUnits)

		glyph.updateObject(glyph.fl, 'Adjust Metrics | LSB: %s; RSB: %s; ADV:%s.' %adjUnits)
		glyph.update()

class metrics_copy(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_copy, self).__init__()

		# - Edit Fields
		self.edt_lsb =  QtGui.QLineEdit()
		self.edt_adv = QtGui.QLineEdit()
		self.edt_rsb =   QtGui.QLineEdit()

		self.edt_lsb.setPlaceholderText('Glyph Name')
		self.edt_adv.setPlaceholderText('Glyph Name')
		self.edt_rsb.setPlaceholderText('Glyph Name')

		# - Spin Box
		self.spb_lsb_percent =  QtGui.QSpinBox()
		self.spb_adv_percent = QtGui.QSpinBox()
		self.spb_rsb_percent = QtGui.QSpinBox()
		self.spb_lsb_units =  QtGui.QSpinBox()
		self.spb_adv_units = QtGui.QSpinBox()
		self.spb_rsb_units = QtGui.QSpinBox()

		self.spb_lsb_percent.setMaximum(200)
		self.spb_adv_percent.setMaximum(200)
		self.spb_rsb_percent.setMaximum(200)
		self.spb_lsb_units.setMaximum(200)
		self.spb_adv_units.setMaximum(200)
		self.spb_rsb_units.setMaximum(200)
		self.spb_lsb_units.setMinimum(-200)
		self.spb_adv_units.setMinimum(-200)
		self.spb_rsb_units.setMinimum(-200)

		self.spb_lsb_percent.setSuffix('%')
		self.spb_adv_percent.setSuffix('%')
		self.spb_rsb_percent.setSuffix('%')
		self.spb_lsb_units.setSuffix(' u')
		self.spb_adv_units.setSuffix(' u')
		self.spb_rsb_units.setSuffix(' u')

		self.spb_lsb_percent.setMaximumWidth(50)
		self.spb_adv_percent.setMaximumWidth(50)
		self.spb_rsb_percent.setMaximumWidth(50)
		self.spb_lsb_units.setMaximumWidth(50)
		self.spb_adv_units.setMaximumWidth(50)
		self.spb_rsb_units.setMaximumWidth(50)

		self.reset_fileds()

		# - Buttons
		self.btn_copyMetrics = QtGui.QPushButton('&Copy Metrics')
		self.btn_copyMetrics.clicked.connect(self.copyMetrics)

		# - Build

		self.addWidget(QtGui.QLabel('LSB:'), 0, 0, 1, 1)
		self.addWidget(self.edt_lsb, 0, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 0, 4, 1, 1)
		self.addWidget(self.spb_lsb_percent, 0, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 0, 6, 1, 1)
		self.addWidget(self.spb_lsb_units, 0, 7, 1, 1)

		self.addWidget(QtGui.QLabel('RSB:'), 1, 0, 1, 1)
		self.addWidget(self.edt_rsb, 1, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 1, 4, 1, 1)
		self.addWidget(self.spb_rsb_percent, 1, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 1, 6, 1, 1)
		self.addWidget(self.spb_rsb_units, 1, 7, 1, 1)

		self.addWidget(QtGui.QLabel('ADV:'), 2, 0, 1, 1)
		self.addWidget(self.edt_adv, 2, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 2, 4, 1, 1)
		self.addWidget(self.spb_adv_percent, 2, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 2, 6, 1, 1)
		self.addWidget(self.spb_adv_units, 2, 7, 1, 1)

		self.addWidget(self.btn_copyMetrics, 3, 1, 1, 8)

	def reset_fileds(self):
		# - Reset text fields
		self.edt_lsb.setText('')
		self.edt_adv.setText('')
		self.edt_rsb.setText('')
		
		# - Reset spin-box
		self.spb_lsb_percent.setValue(100)
		self.spb_adv_percent.setValue(100)
		self.spb_rsb_percent.setValue(100)
		self.spb_lsb_units.setValue(0)
		self.spb_adv_units.setValue(0)
		self.spb_rsb_units.setValue(0)

	def copyMetrics(self):
		glyph = eGlyph()
		
		copyOrder = ['--' in name for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text)]
		srcGlyphs = [str(name).replace('--', '') if len(name) else None for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text)]
		
		adjPercents = (self.spb_lsb_percent.value, self.spb_rsb_percent.value, self.spb_adv_percent.value)
		adjUnits = (self.spb_lsb_units.value, self.spb_rsb_units.value, self.spb_adv_units.value)
		
		glyph.copyMetricsbyName(srcGlyphs, pLayers, copyOrder, adjPercents, adjUnits)

		self.reset_fileds()
		glyph.updateObject(glyph.fl, 'Copy Metrics | LSB: %s; RSB: %s; ADV:%s.' %(srcGlyphs[0], srcGlyphs[1], srcGlyphs[2]))
		glyph.update()

class metrics_expr(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_expr, self).__init__()

		self.edt_lsb = MLineEdit()
		self.edt_adv = MLineEdit()
		self.edt_rsb = MLineEdit()

		self.edt_lsb.setPlaceholderText('Metric expression')
		self.edt_adv.setPlaceholderText('Metric expression')
		self.edt_rsb.setPlaceholderText('Metric expression')

		self.btn_setMetrics = QtGui.QPushButton('&Set Metric expressions')
		self.btn_getShapeParent = QtGui.QPushButton('&Get Element reference')
		self.btn_setMetrics.clicked.connect(self.setMetricEquations)
		self.btn_getShapeParent.clicked.connect(self.bindShapeParent)

		self.spb_shapeIndex = QtGui.QSpinBox()

		self.addWidget(QtGui.QLabel('LSB:'), 	0, 0, 1, 1)
		self.addWidget(self.edt_lsb, 			0, 1, 1, 5)
		self.addWidget(QtGui.QLabel('RSB:'), 	1, 0, 1, 1)
		self.addWidget(self.edt_rsb, 			1, 1, 1, 5)
		self.addWidget(QtGui.QLabel('ADV:'), 	2, 0, 1, 1)
		self.addWidget(self.edt_adv, 			2, 1, 1, 5)
		self.addWidget(self.btn_setMetrics, 	3, 1, 1, 5)
		self.addWidget(QtGui.QLabel('E:'), 		4, 0, 1, 1)
		self.addWidget(self.btn_getShapeParent, 4, 1, 1, 4)
		self.addWidget(self.spb_shapeIndex, 	4, 5, 1, 1)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 5)

	def reset_fileds(self):
		self.edt_lsb.clear()
		self.edt_adv.clear()
		self.edt_rsb.clear()

	def bindShapeParent(self):
		glyph = eGlyph()
		layer = None 	# Static! Make it smart, so it detects on all layers, dough unnecessary
		shapeIndex = self.spb_shapeIndex.value 	# Static! Make it smart, so it detects...
		namedShapes = [shape for shape in glyph.shapes() if len(shape.shapeData.name)]
		
		try:
			wShape = namedShapes[shapeIndex]
			transform = wShape.transform
			
			if len(wShape.shapeData.name):
				if transform.m11() > 0:
					self.edt_lsb.setText('=%s' %wShape.shapeData.name)
					self.edt_rsb.setText('=%s' %wShape.shapeData.name)
				else:
					self.edt_lsb.setText('=rsb("%s")' %wShape.shapeData.name)
					self.edt_rsb.setText('=lsb("%s")' %wShape.shapeData.name)

		except IndexError:
			print 'ERROR: Glyph /%s - No NAMED SHAPE with INDEX [%s] found!' %(glyph.name, shapeIndex)

	def setMetricEquations(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			if len(self.edt_lsb.text): glyph.setLSBeq(self.edt_lsb.text, layer)
			if len(self.edt_rsb.text): glyph.setRSBeq(self.edt_rsb.text, layer)
			if len(self.edt_adv.text): glyph.setADVeq(self.edt_adv.text, layer)

		self.reset_fileds()
		glyph.update()
		glyph.updateObject(glyph.fl, 'Set Metrics Equations @ %s.' %'; '.join(wLayers))

class metrics_font(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_font, self).__init__()

		self.btn_setAscender = QtGui.QPushButton('Asc.')
		self.btn_setCapsHeight = QtGui.QPushButton('Caps')
		self.btn_setDescender = QtGui.QPushButton('Desc.')
		self.btn_setXHeight = QtGui.QPushButton('X Hgt.')

		self.btn_togSelection = QtGui.QPushButton('Selection')
		self.btn_togBBOX = QtGui.QPushButton('Glyph BBOX')

		self.btn_togSelection.setCheckable(True)
		self.btn_togBBOX.setCheckable(True)
		#self.btn_togBBOX.setEnabled(False)
		
		self.btn_setAscender.setToolTip('Set Ascender height ')
		self.btn_setCapsHeight.setToolTip('Set Caps Height')
		self.btn_setDescender.setToolTip('Set Descender height')
		self.btn_setXHeight.setToolTip('Set X Height')

		self.btn_togSelection.setToolTip('Set Font metrics using the selected node')
		self.btn_togBBOX.setToolTip('Set Font metrics using the active glyph bounding box')

		self.btn_setAscender.setMinimumWidth(40)
		self.btn_setCapsHeight.setMinimumWidth(40)
		self.btn_setDescender.setMinimumWidth(40)
		self.btn_setXHeight.setMinimumWidth(40)

		self.btn_setAscender.clicked.connect(lambda: self.setFontMetrics('ascender'))
		self.btn_setCapsHeight.clicked.connect(lambda: self.setFontMetrics('capsHeight'))
		self.btn_setDescender .clicked.connect(lambda: self.setFontMetrics('descender'))
		self.btn_setXHeight.clicked.connect(lambda: self.setFontMetrics('xHeight'))

		self.addWidget(self.btn_togSelection,	0,0,1,2)
		self.addWidget(self.btn_togBBOX,		0,2,1,2)
		self.addWidget(self.btn_setAscender,	1,0,1,1)
		self.addWidget(self.btn_setCapsHeight,	1,1,1,1)
		self.addWidget(self.btn_setDescender,	1,2,1,1)
		self.addWidget(self.btn_setXHeight,		1,3,1,1)

	def setFontMetrics(self, metricName):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			if self.btn_togSelection.isChecked():
				selection = glyph.selectedNodes(layer)

				if len(selection):
					glyph.package.setMaster(layer)
					exec('glyph.package.%s_value = selection[0].y' %metricName)

			if self.btn_togBBOX.isChecked():
				glyph.package.setMaster(layer)
				bbox_layer = glyph.layer(layer).boundingBox
								
				if metricName in ['ascender', 'capsHeight', 'xHeight']:
					exec('glyph.package.%s_value = int(bbox_layer.y() + bbox_layer.height())' %metricName)

				elif metricName == 'descender':
					glyph.package.descender_value = int(bbox_layer.y())
		
		self.btn_togSelection.setChecked(False)
		self.btn_togBBOX.setChecked(False)

		glyph.update()
		glyph.updateObject(glyph.package, 'Set Font Metrics: %s @ %s.' %(metricName, '; '.join(wLayers)))


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
			
		# - Build 
		#layoutV.addWidget(QtGui.QLabel('Glyph: Adjust Metric data'))
		layoutV.addLayout(metrics_adjust())
		layoutV.addSpacing(10)
		layoutV.addWidget(QtGui.QLabel('Glyph: Copy Metric data'))
		layoutV.addLayout(metrics_copy())
		layoutV.addSpacing(10)
		layoutV.addWidget(QtGui.QLabel('Glyph: Set metric expressions'))
		layoutV.addLayout(metrics_expr())
		layoutV.addSpacing(10)
		layoutV.addWidget(QtGui.QLabel('\nFont: Set Font Metrics'))
		layoutV.addLayout(metrics_font())

		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 280, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()