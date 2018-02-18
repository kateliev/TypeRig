#FLM: TAB Metrics
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Metrics', '0.01'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Sub widgets ------------------------
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
		glyph.updateObject(glyph.fl, 'Copy Metrics | LSB: %s; RSB: %s; ADV:%s;' %(srcGlyphs[0], srcGlyphs[1], srcGlyphs[2]))
		glyph.update()


class metrics_expr(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_expr, self).__init__()

		self.edt_lsb =  QtGui.QLineEdit()
		self.edt_adv = QtGui.QLineEdit()
		self.edt_rsb =   QtGui.QLineEdit()

		self.edt_lsb.setPlaceholderText('Metric expression')
		self.edt_adv.setPlaceholderText('Metric expression')
		self.edt_rsb.setPlaceholderText('Metric expression')

		self.btn_setMetrics = QtGui.QPushButton('&Set Metric expressions')
		#self.btn_setMetrics.clicked.connect(self.setMetrics)

		self.addWidget(QtGui.QLabel('LSB='), 0, 0, 1, 1)
		self.addWidget(self.edt_lsb, 0, 1, 1, 3)
		
		self.addWidget(QtGui.QLabel('RSB='), 1, 0, 1, 1)
		self.addWidget(self.edt_rsb, 1, 1, 1, 3)
		
		self.addWidget(QtGui.QLabel('ADV='), 2, 0, 1, 1)
		self.addWidget(self.edt_adv, 2, 1, 1, 3)
		
		self.addWidget(self.btn_setMetrics, 3, 1, 1, 3)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 5)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
			
		# - Build   
		layoutV.addWidget(QtGui.QLabel('Copy Metric data'))
		layoutV.addLayout(metrics_copy())
		layoutV.addWidget(QtGui.QLabel('Set metric expressions'))
		layoutV.addLayout(metrics_expr())

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