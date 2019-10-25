#FLM: Glyph: Curve
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Curves', '0.10'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.curve import eCurveEx

# - Sub widgets ------------------------
class curveEq(QtGui.QGridLayout):
	# - Curve optimization
	def __init__(self):
		super(curveEq, self).__init__()
		
		# - Basic operations
		self.btn_tunni = QtGui.QPushButton('&Tunni (Auto)')
		self.btn_hobby = QtGui.QPushButton('Set &Curvature')
		self.btn_hobby_get = QtGui.QPushButton('Get')
		self.btn_hobby_swap = QtGui.QPushButton('Swap')
		self.btn_prop = QtGui.QPushButton('Set &Handles')
		
		self.btn_tunni.setToolTip('Apply Tunni curve optimization')
		self.btn_hobby.setToolTip('Set Hobby spline curvature')
		self.btn_hobby_swap.setToolTip('Swap C0, C1 curvatures')
		self.btn_hobby_get.setToolTip('Get curvature for current selected\nsegment at active layer.')
		self.btn_prop.setToolTip('Set handle length in proportion to bezier node distance')
		
		self.spn_hobby0 = QtGui.QDoubleSpinBox()
		self.spn_hobby1 = QtGui.QDoubleSpinBox()
		self.spn_hobby0.setValue(0.95)
		self.spn_hobby1.setValue(0.95)
		self.spn_hobby0.setSingleStep(0.05)
		self.spn_hobby1.setSingleStep(0.05)

		self.spn_prop = QtGui.QDoubleSpinBox()
		self.spn_prop.setValue(0.30)
		self.spn_prop.setSingleStep(0.1)

		self.btn_tunni.clicked.connect(lambda: self.eqContour('tunni'))
		self.btn_hobby_swap.clicked.connect(self.hobby_swap)
		self.btn_hobby_get.clicked.connect(self.hobby_get)
		self.btn_hobby.clicked.connect(lambda: self.eqContour('hobby'))
		self.btn_prop.clicked.connect(lambda: self.eqContour('prop'))

		# -- Build: Curve optimization
		self.addWidget(self.btn_tunni,						 0, 0, 1, 5)    
		self.addWidget(QtGui.QLabel('Proportional handles'), 1, 0, 1, 5)
		self.addWidget(self.btn_prop,						 2, 0, 1, 3)
		self.addWidget(QtGui.QLabel('P:'),					 2, 3, 1, 1)
		self.addWidget(self.spn_prop,						 2, 4, 1, 1)
		self.addWidget(QtGui.QLabel('Hobby curvature'),		 3, 0, 1, 5)
		self.addWidget(self.btn_hobby_swap,					 4, 0, 1, 1)
		self.addWidget(QtGui.QLabel('C0'),					 4, 1, 1, 1)
		self.addWidget(self.spn_hobby0,						 4, 2, 1, 1)    
		self.addWidget(QtGui.QLabel('C1'),					 4, 3, 1, 1)
		self.addWidget(self.spn_hobby1,						 4, 4, 1, 1)  
		self.addWidget(self.btn_hobby_get,					 5, 0, 1, 1)  
		self.addWidget(self.btn_hobby,						 5, 1, 1, 4)

		self.setColumnStretch(0,1)
		self.setColumnStretch(4,0)
		self.setColumnStretch(5,0)
		self.setColumnStretch(6,0)
		self.setColumnStretch(7,0)

		#self.setColumnMinimumWidth(0, 40)


	def hobby_swap(self):
		temp = self.spn_hobby0.value
		self.spn_hobby0.setValue(self.spn_hobby1.value)
		self.spn_hobby1.setValue(temp)

	def hobby_get(self):
		glyph = eGlyph()
		selSegment = eCurveEx(eNode(glyph.selectedNodes()[0]).getSegmentNodes())
		c0, c1 = selSegment.curve.getHobbyCurvature()

		self.spn_hobby0.setValue(c0.real)
		self.spn_hobby1.setValue(c1.real)

	def eqContour(self, method):
		glyph = eGlyph()
		selection = glyph.selected(True)
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			# !!! Fixed the problem, but with too many loops - rethink
			nodes_fl = [glyph.nodes(layer)[nid] for nid in selection]
			nodes = [eNode(node) for node in nodes_fl]
			conNodes = [node for node in nodes if node.getNextOn() in nodes_fl]
			segmentNodes = [node.getSegmentNodes() for node in conNodes]
		 
			for segment in reversed(segmentNodes):
				if len(segment) == 4:
					wSegment = eCurveEx(segment)
					
					if method is 'tunni':
						wSegment.eqTunni()

					elif method is 'hobby':
						curvature = (float(self.spn_hobby0.value), float(self.spn_hobby1.value))
						wSegment.eqHobbySpline(curvature)

					elif method is 'prop':
						proportion = float(self.spn_prop.value)
						wSegment.eqProportionalHandles(proportion)

		glyph.updateObject(glyph.fl, 'Optimize %s @ %s.' %(method, '; '.join(wLayers)))
		glyph.update()


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
				
		# - Build   
		layoutV.addWidget(QtGui.QLabel('Curve optimization'))
		layoutV.addLayout(curveEq())

		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()