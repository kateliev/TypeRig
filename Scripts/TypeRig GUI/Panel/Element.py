#FLM: Glyph: Elements
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
app_name, app_version = 'TypeRig | Elements', '0.02'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.contour import eContour
from typerig.proxy import pFont, pFontMetrics, pContour, pShape
from typerig.gui import getProcessGlyphs
from typerig.brain import Coord, Line
from math import radians

# - Sub-widgets --------------------
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

	def smartSetText(self, prefix):
		currentText = self.text
		if currentText[0] != '.' and currentText[0] != '_': currentText = '.' + currentText
		self.setText(prefix + currentText)

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'{Glyph Name}', lambda: self.setText(eGlyph().name))
		menu.addAction(u'_part', lambda: self.smartSetText('_part'))
		menu.addAction(u'_UC', lambda: self.smartSetText('_UC'))
		menu.addAction(u'_LC', lambda: self.smartSetText('_LC'))
		menu.addAction(u'_LAT', lambda: self.smartSetText('_LAT'))
		menu.addAction(u'_CYR', lambda: self.smartSetText('_CYR'))
		

class basicOps(QtGui.QGridLayout):
	# - Basic Node operations
	def __init__(self):
		super(basicOps, self).__init__()

		# - Widgets
		self.edt_shapeName = MLineEdit()
		self.edt_shapeName.setPlaceholderText('Element name')

		self.btn_setShapeName = QtGui.QPushButton('&Set Name')
		self.btn_delShapeName = QtGui.QPushButton('&Unlink References')

		self.btn_setShapeName.clicked.connect(lambda: self.setShapeName())
		self.btn_delShapeName.clicked.connect(lambda: self.delShapeName())

		self.addWidget(self.edt_shapeName, 		0, 0, 1, 6)
		self.addWidget(self.btn_setShapeName, 	1, 0, 1, 3)
		self.addWidget(self.btn_delShapeName, 	1, 3, 1, 3)

	def reset_fileds(self):
		self.edt_shapeName.clear()

	def setShapeName(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				#print glyph.selectedAtShapes(index=False, layer=layer, deep=False)
				wShape = pShape(glyph.selectedAtShapes(index=False, layer=layer, deep=False)[0][0])
				wShape.setName(self.edt_shapeName.text)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Set Element Name @ %s.' %'; '.join(wLayers))
		
		self.reset_fileds()

class alignShapes(QtGui.QGridLayout):
	# - Align Contours
	def __init__(self):
		super(alignShapes, self).__init__()
		from collections import OrderedDict
		
		# - Init
		self.align_x = OrderedDict([('Left','L'), ('Right','R'), ('Center','C'), ('Keep','K')])
		self.align_y = OrderedDict([('Top','T'), ('Bottom','B'), ('Center','E'), ('Keep','X')])
		self.align_mode = OrderedDict([('Layer','CL'), ('Contour to Contour','CC'), ('Contour to Contour (REV)','RC')])
		
		# !!! To be implemented
		#self.align_mode = OrderedDict([('Layer','CL'), ('Contour to Contour','CC'), ('Contour to Contour (REV)','RC'), ('Contour to Node','CN'),('Node to Node','NN')])

		# - Widgets
		self.cmb_align_x = QtGui.QComboBox()
		self.cmb_align_y = QtGui.QComboBox()
		self.cmb_align_mode = QtGui.QComboBox()
		self.cmb_align_x.addItems(self.align_x.keys())
		self.cmb_align_y.addItems(self.align_y.keys())
		self.cmb_align_mode.addItems(self.align_mode.keys())

		self.cmb_align_x.setToolTip('Horizontal Alignment')
		self.cmb_align_y.setToolTip('Vertical Alignment')
		self.cmb_align_mode.setToolTip('Alignment Mode')

		self.btn_align = QtGui.QPushButton('Align')
		self.btn_align.clicked.connect(self.alignShapes)

		self.addWidget(self.cmb_align_mode, 	0, 0, 1, 2)
		self.addWidget(self.cmb_align_x, 		0, 2, 1, 1)
		self.addWidget(self.cmb_align_y, 		0, 3, 1, 1)
		self.addWidget(self.btn_align, 			1, 0, 1, 4)

	def alignShapes(self):
		# - Helpers
		def getContourBonds(work_contours):
			tmp_bounds = [contour.bounds() for contour in work_contours]
			cont_min_X, cont_min_Y, cont_max_X, cont_max_Y = map(set, zip(*tmp_bounds))
			return (min(cont_min_X), min(cont_min_Y), max(cont_max_X), max(cont_max_Y))

		def getAlignDict(bounds_tuple):
			align_dict = {	'L': bounds_tuple[0], 
							'R': bounds_tuple[2],
							'C': bounds_tuple[2]/2,
							'B': bounds_tuple[1], 
							'T': bounds_tuple[3], 
							'E': bounds_tuple[3]/2
						}

			return align_dict

		# - Init
		user_mode =  self.align_mode[self.cmb_align_mode.currentText]
		user_x = self.align_x[self.cmb_align_x.currentText]
		user_y = self.align_y[self.cmb_align_y.currentText]
		keep_x, keep_y = True, True	

		if user_x == 'K': keep_x = False; user_x = 'L'
		if user_y == 'X': keep_y = False; user_y = 'B'		
		
		process_glyphs = getProcessGlyphs(pMode)

		# - Process
		for glyph in process_glyphs:
			selection = glyph.selectedAtContours()
			wLayers = glyph._prepareLayers(pLayers)

			for layerName in wLayers:
				glyph_contours = glyph.contours(layerName, extend=eContour)
				work_contours = [glyph_contours[index] for index in list(set([item[0] for item in selection]))]
				
				if user_mode == 'CL': # Align all contours in given Layer
					layer_bounds = glyph.getBounds(layerName)
					cont_bounds = (layer_bounds.x(), layer_bounds.y(), layer_bounds.x() + layer_bounds.width(), layer_bounds.y() + layer_bounds.height())
					align_type = getAlignDict(cont_bounds)
					target = Coord(align_type[user_x], align_type[user_y])

					for contour in glyph_contours:
						contour.alignTo(target, user_x + user_y, (keep_x, keep_y))					

				elif user_mode =='CC': # Align contours to contours
					if 1 < len(work_contours) < 3:
						c1, c2 = work_contours
						c1.alignTo(c2, user_x + user_y, (keep_x, keep_y))

					elif len(work_contours) > 2:
						cont_bounds = getContourBonds(work_contours)
						align_type = getAlignDict(cont_bounds)
						target = Coord(align_type[user_x], align_type[user_y])

						for contour in work_contours:
							contour.alignTo(target, user_x + user_y, (keep_x, keep_y))
					
				elif user_mode == 'RC': # Align contours to contours in reverse order
					if 1 < len(work_contours) < 3:
						c1, c2 = work_contours
						c2.alignTo(c1, user_x + user_y, (keep_x, keep_y))

					elif len(work_contours) > 2:
						cont_bounds = getContourBonds(work_contours)
						align_type = getAlignDict(cont_bounds)
						target = Coord(align_type[user_x], align_type[user_y])

						for contour in reversed(work_contours):
							contour.alignTo(target, user_x + user_y, (keep_x, keep_y))	

				# !!! To be implemented
				elif user_mode == 'CN': # Align contour to node
					pass

				elif user_mode == 'NN': # Align a node on contour to node on another
					pass

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Align Contours @ %s.' %(glyph.name, '; '.join(wLayers)))

class shapeMovement(QtGui.QVBoxLayout):
	def __init__(self):
		super(shapeMovement, self).__init__()

		# - Init
		self.methodList = ['Shift', 'Scale', 'Shear']
		
		# - Methods
		self.cmb_methodSelector = QtGui.QComboBox()
		self.cmb_methodSelector.addItems(self.methodList)
		self.cmb_methodSelector.setToolTip('Select transformation method')
		
		# - Arrow buttons
		self.btn_up = QtGui.QPushButton('Up')
		self.btn_down = QtGui.QPushButton('Down')
		self.btn_left = QtGui.QPushButton('Left')
		self.btn_right = QtGui.QPushButton('Right')
		
		self.btn_up.setMinimumWidth(80)
		self.btn_down.setMinimumWidth(80)
		self.btn_left.setMinimumWidth(80)
		self.btn_right.setMinimumWidth(80)

		self.btn_up.clicked.connect(self.onUp)
		self.btn_down.clicked.connect(self.onDown)
		self.btn_left.clicked.connect(self.onLeft)
		self.btn_right.clicked.connect(self.onRight)
		
		self.edt_offX = QtGui.QLineEdit('1.0')
		self.edt_offY = QtGui.QLineEdit('1.0')
		self.edt_offX.setToolTip('X offset')
		self.edt_offY.setToolTip('Y offset')

		# - Layout
		self.lay_btn = QtGui.QGridLayout()

		self.lay_btn.addWidget(self.cmb_methodSelector, 0, 0, 1, 6)
		self.lay_btn.addWidget(QtGui.QLabel('X:'), 		1, 0, 1, 1)
		self.lay_btn.addWidget(self.edt_offX, 			1, 1, 1, 1)
		self.lay_btn.addWidget(self.btn_up, 			1, 2, 1, 2)
		self.lay_btn.addWidget(QtGui.QLabel('Y:'), 		1, 4, 1, 1)
		self.lay_btn.addWidget(self.edt_offY, 			1, 5, 1, 1)
		self.lay_btn.addWidget(self.btn_left, 			2, 0, 1, 2)
		self.lay_btn.addWidget(self.btn_down, 			2, 2, 1, 2)
		self.lay_btn.addWidget(self.btn_right, 			2, 4, 1, 2)

		self.addLayout(self.lay_btn)

	def moveNodes(self, offset_x, offset_y, method):
		# - Init
		glyph = eGlyph()
		font = pFont()
		
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selected_shapes = glyph.selectedAtShapes(index=False, layer=layer, deep=False)
								
				for shape, contour, node in selected_shapes:
					wShape = pShape(shape)
					if method =='Shift':
						wShape.shift(offset_x, offset_y)

					elif method == 'Scale':
						wShape.scale(1. - offset_x/100., 1. - offset_y/100.)

					elif method == 'Shear':
						wShape.shear(radians(offset_x), radians(offset_y))				

			glyph.update()
			glyph.updateObject(glyph.fl, 'Element: %s @ %s.' %(method, '; '.join(wLayers)))
		
		# - Set Undo
		#glyph.updateObject(glyph.activeLayer(), '%s @ %s.' %(method, glyph.activeLayer().name), verbose=False)

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

		#layoutV.addWidget(QtGui.QLabel('Align Shapes'))
		#self.alignShapes = alignShapes()
		#layoutV.addLayout(self.alignShapes)

		layoutV.addWidget(QtGui.QLabel('Transformation'))
		self.shapeMovement = shapeMovement()
		layoutV.addLayout(self.shapeMovement)  
		
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
			shiftXY = (.0, float(self.shapeMovement.edt_offY.text) + addon)
		
		elif key == QtCore.Qt.Key_Down:
			shiftXY = (.0, -float(self.shapeMovement.edt_offY.text) - addon)
		
		elif key == QtCore.Qt.Key_Left:
			shiftXY = (-float(self.shapeMovement.edt_offX.text) - addon, .0)
		
		elif key == QtCore.Qt.Key_Right:
			shiftXY = (float(self.shapeMovement.edt_offX.text) + addon, .0)
		
		else:
			shiftXY = (.0,.0)
		
		# - Move
		self.shapeMovement.moveNodes(*shiftXY, method=str(self.shapeMovement.cmb_methodSelector.currentText))

	def captureKeyaboard(self):
		if not self.KeyboardOverride:
			self.KeyboardOverride = True
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