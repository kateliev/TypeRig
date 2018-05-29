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
app_name, app_version = 'TypeRig | Metrics', '0.03'

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
		
class metrics_copy(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_copy, self).__init__()

		self.edt_lsb =  QtGui.QLineEdit()
		self.edt_adv = QtGui.QLineEdit()
		self.edt_rsb =   QtGui.QLineEdit()

		self.edt_lsb.setPlaceholderText('Glyph Name')
		self.edt_adv.setPlaceholderText('Glyph Name')
		self.edt_rsb.setPlaceholderText('Glyph Name')

		self.edt_lsb_percent =  QtGui.QLineEdit('100')
		self.edt_adv_percent = QtGui.QLineEdit('100')
		self.edt_rsb_percent = QtGui.QLineEdit('100')
		self.edt_lsb_units =  QtGui.QLineEdit('0')
		self.edt_adv_units = QtGui.QLineEdit('0')
		self.edt_rsb_units = QtGui.QLineEdit('0')

		self.edt_lsb_percent.setMaximumWidth(30)
		self.edt_adv_percent.setMaximumWidth(30)
		self.edt_rsb_percent.setMaximumWidth(30)
		self.edt_lsb_units.setMaximumWidth(30)
		self.edt_adv_units.setMaximumWidth(30)
		self.edt_rsb_units.setMaximumWidth(30)

		self.btn_copyMetrics = QtGui.QPushButton('&Copy Metrics')
		self.btn_copyMetrics.clicked.connect(self.copyMetrics)

		self.addWidget(QtGui.QLabel('LSB:'), 0, 0, 1, 1)
		self.addWidget(self.edt_lsb, 0, 1, 1, 3)
		self.addWidget(QtGui.QLabel('Adjust:'), 0, 4, 1, 1)
		self.addWidget(self.edt_lsb_percent, 0, 5, 1, 1)
		self.addWidget(QtGui.QLabel('%'), 0, 6, 1, 1)
		self.addWidget(self.edt_lsb_units, 0, 7, 1, 1)
		self.addWidget(QtGui.QLabel('U'), 0, 8, 1, 1)

		self.addWidget(QtGui.QLabel('RSB:'), 1, 0, 1, 1)
		self.addWidget(self.edt_rsb, 1, 1, 1, 3)
		self.addWidget(QtGui.QLabel('Adjust:'), 1, 4, 1, 1)
		self.addWidget(self.edt_rsb_percent, 1, 5, 1, 1)
		self.addWidget(QtGui.QLabel('%'), 1, 6, 1, 1)
		self.addWidget(self.edt_rsb_units, 1, 7, 1, 1)
		self.addWidget(QtGui.QLabel('U'), 1, 8, 1, 1)

		self.addWidget(QtGui.QLabel('ADV:'), 2, 0, 1, 1)
		self.addWidget(self.edt_adv, 2, 1, 1, 3)
		self.addWidget(QtGui.QLabel('Adjust:'), 2, 4, 1, 1)
		self.addWidget(self.edt_adv_percent, 2, 5, 1, 1)
		self.addWidget(QtGui.QLabel('%'), 2, 6, 1, 1)
		self.addWidget(self.edt_adv_units, 2, 7, 1, 1)
		self.addWidget(QtGui.QLabel('U'), 2, 8, 1, 1)

		self.addWidget(self.btn_copyMetrics, 3, 1, 1, 8)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(4, 0)
		self.setColumnStretch(6, 0)
		self.setColumnStretch(8, 0)
		self.setColumnStretch(1, 5)

	def reset_fileds(self):
		self.edt_lsb.setText('')
		self.edt_adv.setText('')
		self.edt_rsb.setText('')
		self.edt_lsb_percent.setText('100')
		self.edt_adv_percent.setText('100')
		self.edt_rsb_percent.setText('100')
		self.edt_lsb_units.setText('0')
		self.edt_adv_units.setText('0')
		self.edt_rsb_units.setText('0')

	def copyMetrics(self):
		glyph = eGlyph()
		
		copyOrder = ['--' in name for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text)]
		srcGlyphs = [str(name).replace('--', '') if len(name) else None for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text)]
		
		adjPercents = (int(self.edt_lsb_percent.text), int(self.edt_rsb_percent.text), int(self.edt_adv_percent.text))
		adjUnits = (int(self.edt_lsb_units.text), int(self.edt_rsb_units.text), int(self.edt_adv_units.text))
		
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
		self.btn_setMetrics.clicked.connect(self.setMetricEquations)

		self.addWidget(QtGui.QLabel('LSB:'), 0, 0, 1, 1)
		self.addWidget(self.edt_lsb, 0, 1, 1, 3)
		
		self.addWidget(QtGui.QLabel('RSB:'), 1, 0, 1, 1)
		self.addWidget(self.edt_rsb, 1, 1, 1, 3)
		
		self.addWidget(QtGui.QLabel('ADV:'), 2, 0, 1, 1)
		self.addWidget(self.edt_adv, 2, 1, 1, 3)
		
		self.addWidget(self.btn_setMetrics, 3, 1, 1, 3)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 5)

	def reset_fileds(self):
		self.edt_lsb.clear()
		self.edt_adv.clear()
		self.edt_rsb.clear()

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
				bbox_layer = glyph.layer(layer).boundingBox
				glyph.package.setMaster(layer)
								
				if metricName is 'ascender' or 'capsHeight' or 'xHeight':
					exec('glyph.package.%s_value = bbox_layer.y() + bbox_layer.height()' %metricName)

				elif 'descender':
					exec('glyph.package.%s_value = bbox_layer.y()' %metricName)
		
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
		layoutV.addWidget(QtGui.QLabel('Glyph: Copy Metric data'))
		layoutV.addLayout(metrics_copy())
		layoutV.addWidget(QtGui.QLabel('Glyph: Set metric expressions'))
		layoutV.addLayout(metrics_expr())
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