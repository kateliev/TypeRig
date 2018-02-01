#FLM: TAB Node Tools 1.0
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TAB Nodes', '0.10'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph
from typerig.node import eNode

#from typerig.utils import outputHere # Remove later!

# - Sub widgets ------------------------
class basicOps(QtGui.QGridLayout):
	# - Basic Node operations
	def __init__(self):
		super(basicOps, self).__init__()
		
		# - Basic operations
		self.btn_insert = QtGui.QPushButton('&Insert')
		self.btn_remove = QtGui.QPushButton('&Remove')
		
		#self.btn_insert.setMinimumWidth(80)
		#self.btn_remove.setMinimumWidth(80)

		self.btn_insert.setToolTip('Insert Node after Selection\nat given time T')
		self.btn_remove.setToolTip('Remove Selected Nodes!\nFor proper curve node deletion\nalso select the associated handles!')
		
		self.btn_insert.clicked.connect(self.insertNode)
		self.btn_remove.clicked.connect(self.removeNode)

		# - Inserion time
		self.edt_time = QtGui.QLineEdit('0.5')
		#self.edt_time.setMinimumWidth(30)
		self.edt_time.setToolTip('Insertion Time')

		# -- Build: Basic Ops
		self.addWidget(self.btn_insert, 0, 0, 1, 2)
		self.addWidget(QtGui.QLabel('T:'), 0, 2, 1, 1)
		self.addWidget(self.edt_time, 0, 3, 1, 1 )
		self.addWidget(self.btn_remove, 0, 4, 1, 2)

	def insertNode(self):
		'''
		import sys        
		sys.stdout = open(r'd:\\stdout.log', 'w')
		sys.stderr = open(r'd:\\stderr.log', 'w')
		'''

		glyph = eGlyph()
		selection = glyph.selectedAtContours(True)
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			nodeMap = glyph._mapOn(layer)
			
			for cID, nID in reversed(selection):
				glyph.insertNodeAt(cID, nodeMap[cID][nID] + float(self.edt_time.text), layer)

		glyph.update()

	def removeNode(self):
		glyph = eGlyph()
		selection = glyph.selectedAtContours()
		wLayers = glyph._prepareLayers(pLayers)

		for layer in wLayers:
			for cID, nID in reversed(selection):
				glyph.removeNodeAt(cID, nID, layer)
				#glyph.contours()[cID].clearNodes()

		glyph.update()


class breakContour(QtGui.QGridLayout):
	# - Split/Break contour 
	def __init__(self):
		super(breakContour, self).__init__()
			 
		# -- Split button
		self.btn_splitContour = QtGui.QPushButton('&Break')
		self.btn_splitContourClose = QtGui.QPushButton('Break && &Close')
		
		self.btn_splitContour.clicked.connect(self.splitContour)
		self.btn_splitContourClose.clicked.connect(self.splitContourClose)
		
		#self.btn_splitContour.setMinimumWidth(80)
		#self.btn_splitContourClose.setMinimumWidth(80)

		self.btn_splitContour.setToolTip('Break contour at selected Node(s).')
		self.btn_splitContourClose.setToolTip('Break contour and close open contours!\nUseful for cutting stems and etc.')

		# -- Extrapolate value
		self.edt_expand = QtGui.QLineEdit('0.0')
		#self.edt_expand.setMinimumWidth(30)

		self.edt_expand.setToolTip('Extrapolate endings.')
								
		# -- Build: Split/Break contour
		self.addWidget(self.btn_splitContour, 0, 0, 1, 2)
		self.addWidget(QtGui.QLabel('E:'), 0, 2, 1, 1)
		self.addWidget(self.edt_expand, 0, 3, 1, 1)
		self.addWidget(self.btn_splitContourClose, 0, 4, 1, 2)
				
	def splitContour(self):
		glyph = eGlyph()
		glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=False)
		glyph.update()

	def splitContourClose(self):
		glyph = eGlyph()
		glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=True)
		glyph.update()        

class convertHobby(QtGui.QHBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(convertHobby, self).__init__()

		# -- Convert button
		self.btn_convertNode = QtGui.QPushButton('C&onvert')
		self.btn_convertNode.setToolTip('Convert/Unconvert selected curve node to Hobby Knot')
		self.btn_convertNode.clicked.connect(self.convertHobby)

		#self.btn_convertNode.setFixedWidth(80)

		# -- Close contour checkbox
		#self.chk_Safe = QtGui.QCheckBox('Safe')

		# -- Tension value (not implemented yet)
		#self.edt_tension = QtGui.QLineEdit('0.0')
		#self.edt_tension.setDisabled(True)    
				
		# -- Build
		self.addWidget(self.btn_convertNode)
		#self.addWidget(QtGui.QLabel('T:'), 1, 1)
		#self.addWidget(self.edt_tension, 1, 2)
		#self.addWidget(self.chk_Safe, 1, 3)

	def convertHobby(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		selection = glyph.selected()

		for layerName in wLayers:
			pNodes = [glyph.nodes(layerName)[nID] for nID in selection]
			print pNodes

			for node in pNodes:
				if not node.hobby:
					node.hobby = True
				else:
					node.hobby = False
				node.update()

		glyph.update()
		
		#fl6.Update(fl6.CurrentGlyph())

class advMovement(QtGui.QVBoxLayout):
	def __init__(self):
		super(advMovement, self).__init__()

		# - Init
		self.methodList = ['Move', 'Interpolated Nudge', 'Slanted Space']
		
		# - Methods
		self.cmb_methodSelector = QtGui.QComboBox()
		self.cmb_methodSelector.addItems(self.methodList)
		self.cmb_methodSelector.setToolTip('Select movement method')
		self.addWidget(self.cmb_methodSelector)

		# - Arrow buttons
		self.lay_btn = QtGui.QGridLayout()
		
		self.btn_up = QtGui.QPushButton('Up')
		self.btn_down = QtGui.QPushButton('Down')
		self.btn_left = QtGui.QPushButton('Left')
		self.btn_right = QtGui.QPushButton('Right')
		
		self.btn_up.clicked.connect(self.onUp)
		self.btn_down.clicked.connect(self.onDown)
		self.btn_left.clicked.connect(self.onLeft)
		self.btn_right.clicked.connect(self.onRight)
		
		self.edt_offX = QtGui.QLineEdit('1.0')
		self.edt_offY = QtGui.QLineEdit('1.0')
		self.edt_offX.setToolTip('X offset')
		self.edt_offY.setToolTip('Y offset')

		self.lay_btn.addWidget(QtGui.QLabel('X:'), 0, 0, 1, 1)
		self.lay_btn.addWidget(self.edt_offX, 0, 1, 1, 1)
		self.lay_btn.addWidget(self.btn_up, 0, 2, 1, 2)
		self.lay_btn.addWidget(QtGui.QLabel('Y:'), 0, 4, 1, 1)
		self.lay_btn.addWidget(self.edt_offY, 0, 5, 1, 1)

		self.lay_btn.addWidget(self.btn_left, 1, 0, 1, 2)
		self.lay_btn.addWidget(self.btn_down, 1, 2, 1, 2)
		self.lay_btn.addWidget(self.btn_right, 1, 4, 1, 2)

		self.addLayout(self.lay_btn)

		
	def moveNodes(self, offset_x, offset_y, method):
		# - Init
		glyph = eGlyph()
		selectedNodes = glyph.selectedNodes()

		# - Process
		if method == self.methodList[0]:
			for node in selectedNodes:
				if node.isOn:
					node.smartMove(QtCore.QPointF(offset_x, offset_y))

		elif method == self.methodList[1]:
			for node in selectedNodes:
				wNode = eNode(node)
				wNode.interpMove(offset_x, offset_y)

		elif method == self.methodList[2]:
			pass

		# - Finish it
		glyph.update()

	def onUp(self):
		self.moveNodes(.0, float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText))

	def onDown(self):
		self.moveNodes(.0, -float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText))
			
	def onLeft(self):
		self.moveNodes(-float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText))
			
	def onRight(self):
		self.moveNodes(float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText))

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.KeyboardOverride = False
		
		# - Build		
		layoutV.addWidget(QtGui.QLabel('Basic Operations'))
		layoutV.addLayout(basicOps())

		layoutV.addWidget(QtGui.QLabel('Break/Knot Contour'))
		layoutV.addLayout(breakContour())

		layoutV.addWidget(QtGui.QLabel('Convert to Hobby'))
		layoutV.addLayout(convertHobby())    

		layoutV.addWidget(QtGui.QLabel('Movement'))
		self.advMovement = advMovement()
		layoutV.addLayout(self.advMovement)  

		# - Capture Kyaboard
		self.btn_capture = QtGui.QPushButton('Capture Keyboard')
		self.btn_capture.setCheckable(True)
		self.btn_capture.setToolTip('Click here to capture keyboard arrows input.\nNote:\n+10 SHIFT\n+100 CTRL\n Exit ESC')
		self.btn_capture.clicked.connect(self.captureKeyaboard)

		layoutV.addWidget(self.btn_capture)

		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)


	def keyPressEvent(self, eventQKeyEvent):
		#'''
		import sys        
		sys.stdout = open(r'd:\\stdout.log', 'w')
		sys.stderr = open(r'd:\\stderr.log', 'w')
		#'''
		
		#self.setFocus()
		key = eventQKeyEvent.key()
		modifier = int(eventQKeyEvent.modifiers())
		addon = .0
		
		if key == QtCore.Qt.Key_Escape:
			#self.close()
			self.releaseKeyboard()
			self.KeyboardOverride = False
			self.btn_capture.setChecked(False)
			self.btn_capture.setText('Capture Keyboard')
			
		# - Keyboard listener
		# -- Modifier addon
		if modifier == QtCore.Qt.ShiftModifier:
			addon = 10.0
		elif modifier == QtCore.Qt.ControlModifier:
			addon = 100.0
		else:
			addon = .0
		
		# -- Standard movement keys				
		if key == QtCore.Qt.Key_Up:
			shiftXY = (.0, float(self.advMovement.edt_offY.text) + addon)
		
		elif key == QtCore.Qt.Key_Down:
			shiftXY = (.0, -float(self.advMovement.edt_offY.text) - addon)
		
		elif key == QtCore.Qt.Key_Left:
			shiftXY = (-float(self.advMovement.edt_offX.text) - addon, .0)
		
		elif key == QtCore.Qt.Key_Right:
			shiftXY = (float(self.advMovement.edt_offX.text) + addon, .0)

		else:
			key.ignore() 

		# - Move
		self.advMovement.moveNodes(*shiftXY, method=str(self.advMovement.cmb_methodSelector.currentText))


	def captureKeyaboard(self):
		if not self.KeyboardOverride:
			self.KeyboardOverride = True
			self.btn_capture.setStyleSheet('''QPushButton: checked { background-color: red; }''')
			self.btn_capture.setChecked(True)
			self.btn_capture.setText('Keyboard Capture Active. [ESC] Exit')
			self.grabKeyboard()
		else:
			self.KeyboardOverride = False
			self.btn_capture.setChecked(False)
			self.btn_capture.setText('Capture Keyboard')
			self.releaseKeyboard()
	

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()