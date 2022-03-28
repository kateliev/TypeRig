#FLM: TR: Curve
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.base import *
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.curve import eCurveEx
from typerig.proxy.fl.objects.contour import pContour

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init -------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Curves', '0.17'

# - Sub widgets ------------------------
class curveEq(QtGui.QGridLayout):
	# - Curve optimization
	def __init__(self):
		super(curveEq, self).__init__()
		
		# - Basic operations
		self.btn_toLine = QtGui.QPushButton('To &Line')
		self.btn_toCurve = QtGui.QPushButton('To &Curve')

		self.btn_tunni = QtGui.QPushButton('&Tunni')
		
		self.btn_prop = QtGui.QPushButton('Set &Handles')
		self.btn_prop_30 = QtGui.QPushButton('30%')
		self.btn_prop_50 = QtGui.QPushButton('50%')
		self.btn_prop_00 = QtGui.QPushButton('Retract')
		
		self.btn_hobby = QtGui.QPushButton('&Set Curvature')
		self.btn_hobby_get = QtGui.QPushButton('Get')
		self.btn_hobby_swap = QtGui.QPushButton('Swap')
		self.btn_hobby_90 = QtGui.QPushButton('.90')
		self.btn_hobby_80 = QtGui.QPushButton('.80')
		self.btn_hobby_85 = QtGui.QPushButton('.85')
		
		self.spn_hobby0 = QtGui.QDoubleSpinBox()
		self.spn_hobby1 = QtGui.QDoubleSpinBox()
		self.spn_hobby0.setValue(0.95)
		self.spn_hobby1.setValue(0.95)
		self.spn_hobby0.setSingleStep(0.05)
		self.spn_hobby1.setSingleStep(0.05)

		self.spn_prop_p1 = QtGui.QSpinBox()
		self.spn_prop_p1.setValue(30)
		self.spn_prop_p1.setSuffix(' %')
		self.spn_prop_p1.setMaximum(100)

		self.spn_prop_p2 = QtGui.QSpinBox()
		self.spn_prop_p2.setValue(30)
		self.spn_prop_p2.setSuffix(' %')
		self.spn_prop_p2.setMaximum(100)
		
		self.btn_tunni.setToolTip('Apply Tunni curve optimization')
		self.btn_hobby.setToolTip('Set Hobby spline curvature')
		self.btn_hobby_swap.setToolTip('Swap START, END curvatures')
		self.btn_hobby_get.setToolTip('Get curvature for current selected\nsegment at active layer.')
		self.btn_prop.setToolTip('Set handle length in proportion to bezier node distance')
		self.spn_hobby0.setToolTip('Curvature at the START of Bezier segment.')
		self.spn_hobby1.setToolTip('Curvature at the END of Bezier segment.')
		self.spn_prop_p1.setToolTip('Handle length in proportion to curve length.')
		self.spn_prop_p2.setToolTip('Handle length in proportion to curve length.')

		self.btn_toLine.clicked.connect(lambda: self.convert_segment(False))
		self.btn_toCurve.clicked.connect(lambda: self.convert_segment(True))
		self.btn_tunni.clicked.connect(lambda: self.eqContour('tunni'))
		self.btn_prop.clicked.connect(lambda: self.eqContour('prop'))
		self.btn_prop_00.clicked.connect(lambda: self.eqContour('prop_value', value=0))
		self.btn_prop_30.clicked.connect(lambda: self.eqContour('prop_value', value=.30))
		self.btn_prop_50.clicked.connect(lambda: self.eqContour('prop_value', value=.50))

		self.btn_hobby_swap.clicked.connect(self.hobby_swap)
		self.btn_hobby_get.clicked.connect(self.hobby_get)
		self.btn_hobby.clicked.connect(lambda: self.eqContour('hobby'))
		self.btn_hobby_90.clicked.connect(lambda: self.eqContour('hobby_value', value=.90))
		self.btn_hobby_80.clicked.connect(lambda: self.eqContour('hobby_value', value=.80)) 
		self.btn_hobby_85.clicked.connect(lambda: self.eqContour('hobby_value', value=.85))

		# -- Build: Curve optimization
		self.addWidget(self.btn_toLine,						 					0, 0, 1, 2)    
		self.addWidget(self.btn_tunni,						 					0, 2, 1, 2)    
		self.addWidget(self.btn_toCurve,						 				0, 4, 1, 2)    
		self.addWidget(QtGui.QLabel('Curve: Handles proportion (BCP length)'), 	2, 0, 1, 6)
		self.addWidget(self.spn_prop_p1,						 				3, 0, 1, 2)
		self.addWidget(self.btn_prop,						 					3, 2, 1, 2)
		self.addWidget(self.spn_prop_p2,						 				3, 4, 1, 2)
		self.addWidget(self.btn_prop_50,					 					4, 0, 1, 2)
		self.addWidget(self.btn_prop_00,					 					4, 2, 1, 2)
		self.addWidget(self.btn_prop_30,					 					4, 4, 1, 2)
		self.addWidget(QtGui.QLabel('Curve: Hobby curvature (Curve tension)'),	5, 0, 1, 6)
		self.addWidget(self.btn_hobby_get,					 					6, 0, 1, 2)  
		self.addWidget(self.spn_hobby0,						 					6, 2, 1, 1)    
		self.addWidget(self.spn_hobby1,						 					6, 3, 1, 1)  
		self.addWidget(self.btn_hobby_swap,					 					6, 4, 1, 2)
		self.addWidget(self.btn_hobby,						 					7, 0, 1, 6)
		self.addWidget(self.btn_hobby_90,					 					8, 0, 1, 2)
		self.addWidget(self.btn_hobby_85,					 					8, 2, 1, 2)
		self.addWidget(self.btn_hobby_80,					 					8, 4, 1, 2)

	def convert_segment(self, toCurve=False):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		
		# - Get selected nodes. 
		# - NOTE: Only the fist node in every selected segment is important, so we filter for that
		selection = glyph.selectedAtContours(True, filterOn=True)
		selection_dict, selection_filtered = {}, {}
				
		for cID, nID in selection:
			selection_dict.setdefault(cID,[]).append(nID)

		for cID, sNodes in selection_dict.items():
			onNodes = glyph.contours(extend=pContour)[cID].indexOn()
			segments = zip(onNodes, onNodes[1:] + [onNodes[0]]) # Shift and zip so that we have the last segment working
			onSelected = []

			for pair in segments:
				if pair[0] in sNodes and pair[1] in sNodes:
					onSelected.append(pair[1] )

			selection_filtered[cID] = onSelected

		# - Process
		for layer in wLayers:
			for cID, sNodes in selection_filtered.items():
				for nID in reversed(sNodes):
					if toCurve:
						glyph.contours(layer)[cID].nodes()[nID].convertToCurve()
					else:
						glyph.contours(layer)[cID].nodes()[nID].convertToLine()

		glyph.updateObject(glyph.fl, 'Convert Segment @ %s.' %'; '.join(wLayers))
		glyph.update()

	def hobby_swap(self):
		temp = self.spn_hobby0.value
		self.spn_hobby0.setValue(self.spn_hobby1.value)
		self.spn_hobby1.setValue(temp)

	def hobby_get(self):
		glyph = eGlyph()
		selSegment = eCurveEx(eNode(glyph.selectedNodes()[0]).getSegmentNodes())
		c0, c1 = selSegment.curve.solve_hobby_curvature()

		self.spn_hobby0.setValue(c0.real)
		self.spn_hobby1.setValue(c1.real)

	def eqContour(self, method, value=None):
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
					
					if method == 'tunni':
						wSegment.eqTunni()

					elif method == 'hobby':
						curvature = (float(self.spn_hobby0.value), float(self.spn_hobby1.value))
						wSegment.eqHobbySpline(curvature)

					elif method == 'hobby_value':
						wSegment.eqHobbySpline((float(value), float(value)))

					elif method == 'prop':
						ratio = (float(self.spn_prop_p1.value/100.), float(self.spn_prop_p2.value/100.))
						wSegment.eqProportionalHandles(ratio)

					elif method == 'prop_value':
						wSegment.eqProportionalHandles(value)

		glyph.updateObject(glyph.fl, 'Optimize %s @ %s.' %(method, '; '.join(wLayers)))
		glyph.update()


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
				
		# - Build   
		layoutV.addWidget(QtGui.QLabel('Curve: Basic tools'))
		layoutV.addLayout(curveEq())

		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)
		
		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 100, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()