#FLM: TR: Contour
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Contour', '0.28'

# - Dependencies -----------------
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl import *
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Sub widgets ------------------------
class breakContour(QtGui.QGridLayout):
	# - Split/Break contour 
	def __init__(self):
		super(breakContour, self).__init__()
			 
		# -- Split button
		self.btn_splitContour = QtGui.QPushButton('&Break')
		self.btn_splitContourClose = QtGui.QPushButton('&Break && Close')
		
		self.btn_splitContour.clicked.connect(self.splitContour)
		self.btn_splitContourClose.clicked.connect(self.splitContourClose)
		
		self.btn_splitContour.setMinimumWidth(80)
		self.btn_splitContourClose.setMinimumWidth(80)

		self.btn_splitContour.setToolTip('Break contour at selected Node(s).')
		self.btn_splitContourClose.setToolTip('Break contour and close open contours!\nUseful for cutting stems and etc.')

		# -- Extrapolate value
		self.edt_expand = QtGui.QLineEdit('0.0')
		#self.edt_expand.setMinimumWidth(30)

		self.edt_expand.setToolTip('Extrapolate endings.')
								
		# -- Build: Split/Break contour
		self.addWidget(self.btn_splitContour, 0, 0)
		self.addWidget(QtGui.QLabel('E:'), 0, 1)
		self.addWidget(self.edt_expand, 0, 2)
		self.addWidget(self.btn_splitContourClose, 0, 3)
				
	def splitContour(self):
		glyph = eGlyph()
		glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=False)
		glyph.updateObject(glyph.fl, 'Break Contour @ %s.' %'; '.join(glyph._prepareLayers(pLayers)))
		glyph.update()

	def splitContourClose(self):
		glyph = eGlyph()
		glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=True)
		glyph.updateObject(glyph.fl, 'Break Contour & Close @ %s.' %'; '.join(glyph._prepareLayers(pLayers)))
		glyph.update()        

class basicContour(QtGui.QGridLayout):
	# - Split/Break contour 
	def __init__(self):
		super(basicContour, self).__init__()
		self.btn_BL = QtGui.QPushButton('B L')
		self.btn_TL = QtGui.QPushButton('T L')
		self.btn_BR = QtGui.QPushButton('B R')
		self.btn_TR = QtGui.QPushButton('T R')
		self.btn_sort_x = QtGui.QPushButton('Sort X')
		self.btn_sort_y = QtGui.QPushButton('Sort Y')
		self.btn_close = QtGui.QPushButton('C&lose')
		self.btn_start = QtGui.QPushButton('&Start')
		self.btn_CW = QtGui.QPushButton('CW')
		self.btn_CCW = QtGui.QPushButton('CCW')
		self.btn_overlap = QtGui.QPushButton('Remove Overlap')

		self.btn_close.setMinimumWidth(40)
		self.btn_BL.setMinimumWidth(40)
		self.btn_TL.setMinimumWidth(40)
		self.btn_BR.setMinimumWidth(40)
		self.btn_TR.setMinimumWidth(40)
		self.btn_start.setMinimumWidth(40)
		self.btn_CW.setMinimumWidth(40)
		self.btn_CCW.setMinimumWidth(40)

		self.btn_close.setToolTip('Close selected contour')
		self.btn_start.setToolTip('Set start point:\n Selected Node') 
		self.btn_BL.setToolTip('Set start point:\nBottom Left Node') 
		self.btn_TL.setToolTip('Set start point:\nTop Left Node') 
		self.btn_BR.setToolTip('Set start point:\nBottom Right Node') 
		self.btn_TR.setToolTip('Set start point:\nTop Right Node') 
		self.btn_CW.setToolTip('Set direction:\nClockwise (TT)') 
		self.btn_CCW.setToolTip('Set direction:\nCounterclockwise (PS)') 
		self.btn_sort_x.setToolTip('Reorder contours within shapes based on their X coordinate.\nSHIFT+Click reverses order!')
		self.btn_sort_y.setToolTip('Reorder contours within shapes based on their Y coordinate.\nSHIFT+Click reverses order!')
		
		self.btn_start.clicked.connect(lambda : self.setStartSelection())
		self.btn_BL.clicked.connect(lambda : self.setStart((0,0)))
		self.btn_TL.clicked.connect(lambda : self.setStart((0,1)))
		self.btn_BR.clicked.connect(lambda : self.setStart((1,0)))
		self.btn_TR.clicked.connect(lambda : self.setStart((1,1)))
		self.btn_CW.clicked.connect(lambda : self.setDirection(False))
		self.btn_CCW.clicked.connect(lambda : self.setDirection(True))
		self.btn_close.clicked.connect(self.closeContour)
		self.btn_overlap.clicked.connect(self.removeOverlap)
		self.btn_sort_x.clicked.connect(lambda : self.setOrder(False))
		self.btn_sort_y.clicked.connect(lambda : self.setOrder(True))

		self.addWidget(self.btn_close, 	0, 0, 1, 1)
		self.addWidget(self.btn_start, 	0, 1, 1, 1)
		self.addWidget(self.btn_CW, 	1, 0, 1, 1)
		self.addWidget(self.btn_CCW, 	1, 1, 1, 1)

		self.addWidget(self.btn_TL, 	0, 2, 1, 1)
		self.addWidget(self.btn_TR, 	0, 3, 1, 1)
		self.addWidget(self.btn_BL, 	1, 2, 1, 1)
		self.addWidget(self.btn_BR, 	1, 3, 1, 1)
		self.addWidget(self.btn_sort_x, 2, 0, 1, 2)
		self.addWidget(self.btn_sort_y, 2, 2, 1, 2)
		self.addWidget(self.btn_overlap, 3, 0, 1, 4)
		

	def closeContour(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		selection = glyph.selectedAtContours()

		for layerName in wLayers:
			contours = glyph.contours(layerName)

			for cID, nID in reversed(selection):
				if not contours[cID].closed: contours[cID].closed = True

		glyph.updateObject(glyph.fl, 'Close Contour @ %s.' %'; '.join(wLayers))
		glyph.update()

	def removeOverlap(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		
		# - Prepare selection
		tmp = {}
		selection = glyph.selectedAtShapes()

		for sid, cid, nid in selection:
			tmp.setdefault(sid,[]).append(cid)

		selection = {key:list(set(value)) for key, value in tmp.items()}

		# - Get contours
		process_shapes = []
		
		for layerName in wLayers:
			for sid, cid_list in selection.items():
				process_shapes.append((glyph.shapes(layerName)[sid], [glyph.contours(layerName)[cid] for cid in cid_list]))

		for shape, contours in process_shapes:
			shape.removeContours(contours)
			new_shape = fl6.flShape()
			new_fg_shape = fgt.fgShape()
			new_shape.contours = contours
			new_shape.convertToFgShape(new_fg_shape)
			new_fg_shape.removeOverlap()
			shape.addContours(fl6.flShape(new_fg_shape).contours, True)

		glyph.updateObject(glyph.fl, 'Remove Overlap @ %s.' %'; '.join(wLayers))
		glyph.update()

	def setStartSelection(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)
			
			selected_contours = {layer:glyph.selectedAtContours(layer)[0] for layer in wLayers}

			for layer, selection in selected_contours.iteritems():
				cid, nid = selection
				glyph.contours(layer)[cid].setStartPoint(nid)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tManual: Set Start Point @ %s.' %(glyph.name, '; '.join(wLayers)))

	def setOrder(self, sort_y=False):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layerName in wLayers:
				wShapes = glyph.shapes(layerName, extend=eShape)

				for shape in wShapes:
					if sort_y:
						shape.contourOrder((None, not modifiers == QtCore.Qt.ShiftModifier)) # Shift reverses
					else:
						shape.contourOrder((True, not modifiers == QtCore.Qt.ShiftModifier))

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Reorder contours @ %s.' %(glyph.name, '; '.join(wLayers)))

	def setStart(self, control=(0,0)):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			if control == (0,0): 	# BL
				criteria = lambda node : (node.y, node.x)
			elif control == (0,1): 	# TL
				criteria = lambda node : (-node.y, node.x)
			elif control == (1,0): 	# BR
				criteria = lambda node : (node.y, -node.x)
			elif control == (1,1): 	# TR
				criteria = lambda node : (-node.y, -node.x)
			
			for layerName in wLayers:
				contours = glyph.contours(layerName)

				for contour in contours:
					onNodes = [node for node in contour.nodes() if node.isOn()]
					newFirstNode = sorted(onNodes, key=criteria)[0]
					contour.setStartPoint(newFirstNode.index)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Set Start Points @ %s.' %(glyph.name, '; '.join(wLayers)))

	def setDirection(self, ccw=True):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = glyph.selectedAtContours()

			wLayers = glyph._prepareLayers(pLayers)

			for layerName in wLayers:
				all_contours = glyph.contours(layerName)

				if len(selection):
					process_contours = [pContour(all_contours[item[0]]) for item in selection]
				else:
					process_contours = [pContour(contour) for contour in all_contours]

				for contour in process_contours:
					if ccw:
						contour.setCCW()
					else:
						contour.setCW()

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Set contour direction @ %s.' %(glyph.name, '; '.join(wLayers)))

class alignContours(QtGui.QGridLayout):
	# - Align Contours
	def __init__(self):
		super(alignContours, self).__init__()
				
		# - Init
		self.align_x = OrderedDict([('Left','L'), ('Right','R'), ('Center','C'), ('Keep','K')])
		self.align_y = OrderedDict([('Top','T'), ('Bottom','B'), ('Center','E'), ('Keep','X')])
		self.align_mode = OrderedDict([	('Layer','CL'), 
										('Base to X-Height','CMX'),
										('Base to Caps','CMC'),
										('Base Ascender','CMA'),
										('Descender to Base','CMD'),
										('Contour to Contour','CC'),
										('Contour to Contour (REV)','RC'),
										('Contour to Node','CN'),
										('Contour to Node (REV)','RN')
									])
		
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
		self.btn_align.clicked.connect(self.alignContours)

		self.addWidget(self.cmb_align_mode, 	0, 0, 1, 2)
		self.addWidget(self.cmb_align_x, 		0, 2, 1, 1)
		self.addWidget(self.cmb_align_y, 		0, 3, 1, 1)
		self.addWidget(self.btn_align, 			1, 0, 1, 4)

	def alignContours(self):
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
				
				if user_mode =='CC': # Align contours to contours
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
					target = work_contours.pop(0)
					target_node_index = selection[0][1]
					target_node = target.fl.nodes()[target_node_index]

					for contour in work_contours:
							contour.alignTo(target_node, user_x + user_y, (keep_x, keep_y))

				elif user_mode == 'RN': # Align contour to node reversed
					target = work_contours.pop()
					target_node_index = selection[-1][1]
					target_node = target.fl.nodes()[target_node_index]

					for contour in work_contours:
							contour.alignTo(target_node, user_x + user_y, (keep_x, keep_y))

				elif user_mode == 'NN': # Align a node on contour to node on another
					pass

				else:
					metrics = pFontMetrics(glyph.package)
					layer_bounds = glyph.getBounds(layerName)

					if user_mode == 'CL': # Align all contours in given Layer
						cont_bounds = (layer_bounds.x(), layer_bounds.y(), layer_bounds.x() + layer_bounds.width(), layer_bounds.y() + layer_bounds.height())
					
					elif user_mode == 'CMX': # Align all contours to X height
						height = metrics.getXHeight(layerName)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif user_mode == 'CMC': # Align all contours to Caps height
						height = metrics.getCapsHeight(layerName)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif user_mode == 'CMA': # Align all contours to Ascender height
						height = metrics.getAscender(layerName)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					elif user_mode == 'CMD': # Align all contours to Ascender height
						height = metrics.getDescender(layerName)
						cont_bounds = (layer_bounds.x(), 0., layer_bounds.x() + layer_bounds.width(), height)

					align_type = getAlignDict(cont_bounds)
					target = Coord(align_type[user_x], align_type[user_y])					

					for contour in work_contours:
						contour.alignTo(target, user_x + user_y, (keep_x, keep_y))

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAction: Align Contours @ %s.' %(glyph.name, '; '.join(wLayers)))

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		
		layoutV.addWidget(QtGui.QLabel('Contour: Basic Operations'))
		layoutV.addLayout(basicContour())

		#layoutV.addWidget(QtGui.QLabel('Break/Knot Contour'))
		#layoutV.addLayout(breakContour())

		layoutV.addWidget(QtGui.QLabel('Contour: Align '))
		layoutV.addLayout(alignContours())

		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())


# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()