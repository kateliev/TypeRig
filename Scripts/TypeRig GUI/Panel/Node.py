#FLM: TR: Nodes
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!



# - Dependencies -----------------
from __future__ import absolute_import, print_function

import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.node import eNode, eNodesContainer
from typerig.proxy.fl.objects.contour import pContour
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.base import Line, Vector

from typerig.core.func.collection import groupConsecutives
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Nodes', '2.05'

# - Helpers ----------------------------
def filter_consecutive(selection):
	'''Group the results of selectedAtContours and filter out consecutive nodes.'''
	selection_dict = {}
	map_dict = {}
				
	for cID, nID in selection:
		selection_dict.setdefault(cID,[]).append(nID)
		map_dict.setdefault(cID, []).append(nID - 1 in selection_dict[cID])

	return {key: [value[i] for i in range(len(value)) if not map_dict[key][i]] for key, value in selection_dict.items()}

# - Sub widgets ------------------------
class basicOps(QtGui.QGridLayout):
	# - Basic Node operations
	def __init__(self):
		super(basicOps, self).__init__()
		
		# - Basic operations
		self.btn_insert = QtGui.QPushButton('&Insert')
		self.btn_remove = QtGui.QPushButton('&Remove')
		self.btn_mitre = QtGui.QPushButton('&Mitre')
		self.btn_knot = QtGui.QPushButton('&Overlap')
		self.btn_trapA = QtGui.QPushButton('&Trap')
		self.btn_rebuild = QtGui.QPushButton('Rebuil&d')
						
		self.btn_insert.setMinimumWidth(80)
		self.btn_remove.setMinimumWidth(80)
		self.btn_mitre.setMinimumWidth(80)
		self.btn_knot.setMinimumWidth(80)
		self.btn_trapA.setMinimumWidth(80)
		self.btn_rebuild.setMinimumWidth(80)

		self.btn_insert.setToolTip('Insert Node:\n- Click - Insert between selected nodes at given time T;\n- Click + ALT - Insert after each node in selection at given time T.')
		self.btn_remove.setToolTip('Remove Selected Nodes!\nFor proper curve node deletion\nalso select the associated handles!')
		self.btn_mitre.setToolTip('Mitre corner using size X.')
		self.btn_knot.setToolTip('Overlap corner using radius -X.')
		self.btn_trapA.setToolTip('Insert Angular (generic) Ink Trap at node selected')
		self.btn_rebuild.setToolTip('Rebuild corner from nodes selected.')
		
		self.btn_insert.clicked.connect(self.insertNode)
		self.btn_remove.clicked.connect(self.removeNode)
		self.btn_mitre.clicked.connect(lambda: self.cornerMitre(False))
		self.btn_knot.clicked.connect(lambda: self.cornerMitre(True))
		self.btn_trapA.clicked.connect(lambda: self.cornerTrap())
		self.btn_rebuild.clicked.connect(lambda: self.cornerRebuild())

		# - Edit fields
		self.edt_time = QtGui.QLineEdit('0.5')
		self.edt_radius = QtGui.QLineEdit('5')
		self.edt_trap = QtGui.QLineEdit('5, 30, 2')
		
		self.edt_time.setToolTip('Insertion Time.')
		self.edt_radius.setToolTip('Mitre size/Overlap or Round Radius.')
		self.edt_trap.setToolTip('Ink trap: Incision into glyphs flesh, Side depth, Trap size')

		# -- Build: Basic Ops
		self.addWidget(self.btn_insert, 	0, 0, 1, 1)
		self.addWidget(QtGui.QLabel('T:'), 	0, 1, 1, 1)
		self.addWidget(self.edt_time, 		0, 2, 1, 1)
		self.addWidget(self.btn_remove, 	0, 3, 1, 1)

		self.addWidget(self.btn_mitre,		1, 0, 1, 1)
		self.addWidget(QtGui.QLabel('X:'), 	1, 1, 1, 1)
		self.addWidget(self.edt_radius,		1, 2, 1, 1)
		self.addWidget(self.btn_knot,		1, 3, 1, 1)

		self.addWidget(self.btn_trapA,		2, 0, 1, 1)
		self.addWidget(QtGui.QLabel('P:'),	2, 1, 1, 1)
		self.addWidget(self.edt_trap,		2, 2, 1, 1)
		self.addWidget(self.btn_rebuild,	2, 3, 1, 1)

	def insertNode(self):
		glyph = eGlyph()
		selection = glyph.selectedAtContours(True)
		wLayers = glyph._prepareLayers(pLayers)
		modifiers = QtGui.QApplication.keyboardModifiers()

		# - Get selected nodes. 
		# - NOTE: Only the fist node in every selected segment is important, so we filter for that
		selection = glyph.selectedAtContours(True, filterOn=True)
		selection_dict, selection_filtered = {}, {}
		
		for cID, nID in selection:
			selection_dict.setdefault(cID,[]).append(nID)
				
		if modifiers != QtCore.Qt.AltModifier: 
			for cID, sNodes in selection_dict.items():
				onNodes = glyph.contours(extend=pContour)[cID].indexOn()
				segments = zip(onNodes, onNodes[1:] + [onNodes[0]]) # Shift and zip so that we have the last segment working
				onSelected = []

				for pair in segments:
					if pair[0] in sNodes and pair[1] in sNodes:
						onSelected.append(pair[0] )

				selection_filtered[cID] = onSelected
		else:
			selection_filtered = selection_dict

		# - Process
		for layer in wLayers:
			nodeMap = glyph._mapOn(layer)
							
			for cID, nID_list in selection_filtered.items():
				for nID in reversed(nID_list):
					glyph.insertNodeAt(cID, nodeMap[cID][nID] + float(self.edt_time.text), layer)

		glyph.updateObject(glyph.fl, 'Insert Node @ %s.' %'; '.join(wLayers))
		glyph.update()

	def removeNode(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)

		selection = glyph.selectedAtContours(filterOn=True)
		tempDict = {}

		for cID, nID in selection:
			tempDict.setdefault(cID, []).append(nID)

		for layer in wLayers:
			for cID, nidList in tempDict.iteritems():
				for nID in reversed(nidList):
					nodeA = eNode(glyph.contours(layer)[cID].nodes()[nID]).getNextOn()
					nodeB = eNode(glyph.contours(layer)[cID].nodes()[nID]).getPrevOn()
					glyph.contours(layer)[cID].removeNodesBetween(nodeB, nodeA)

		glyph.update()
		glyph.updateObject(glyph.fl, 'Remove Node @ %s.' %'; '.join(wLayers))

	def cornerMitre(self, doKnot=False):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in reversed(selection):
				if not doKnot:
					node.cornerMitre(float(self.edt_radius.text))
				else:
					node.cornerMitre(-float(self.edt_radius.text), True)


		action = 'Mitre Corner' if not doKnot else 'Overlap Corner'
		glyph.update()
		glyph.updateObject(glyph.fl, '%s @ %s.' %(action, '; '.join(wLayers)))

	def cornerTrap(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		parameters = tuple([float(value.strip()) for value in self.edt_trap.text.split(',')])
		
		for layer in wLayers:
			selection = glyph.selectedNodes(layer, filterOn=True, extend=eNode)
			
			for node in reversed(selection):
				node.cornerTrapInc(*parameters)

		glyph.update()
		glyph.updateObject(glyph.fl, '%s @ %s.' %('Trap Corner', '; '.join(wLayers)))

	def cornerRebuild(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		selection_layers = {layer:glyph.selectedNodes(layer, filterOn=True, extend=eNode) for layer in wLayers}

		for layer, selection in selection_layers.items():			
			if len(selection) > 1:
				node_first = selection[0]
				node_last = selection[-1]
				
				line_in = node_first.getPrevLine() if node_first.getPrevOn(False) not in selection else node_first.getNextLine()
				line_out = node_last.getNextLine() if node_last.getNextOn(False) not in selection else node_last.getPrevLine()

				crossing = line_in.intersect_line(line_out, True)

				node_first.smartReloc(*crossing.tuple)
				node_first.parent.removeNodesBetween(node_first.fl, node_last.getNextOn())

		glyph.update()
		glyph.updateObject(glyph.fl, 'Rebuild corner: %s nodes reduced; At layers: %s' %(len(selection), '; '.join(wLayers)))


class alignNodes(QtGui.QGridLayout):
	# - Basic Node operations
	def __init__(self):
		super(alignNodes, self).__init__()
		
		# - Init
		self.copyLine = {}

		# - Buttons
		self.btn_left = QtGui.QPushButton('Left')
		self.btn_centerX = QtGui.QPushButton('Selection: Center X')
		self.btn_right = QtGui.QPushButton('Right')
		self.btn_top = QtGui.QPushButton('Top')
		self.btn_centerY = QtGui.QPushButton('Selection: Center Y')
		self.btn_bottom = QtGui.QPushButton('Bottom')
		self.btn_bboxCenterX = QtGui.QPushButton('Outline: Center X')
		self.btn_bboxCenterY = QtGui.QPushButton('Outline: Center Y')
		self.btn_peerCenterX = QtGui.QPushButton('Neighbors: Center X')
		self.btn_peerCenterY = QtGui.QPushButton('Neighbors: Center Y')
		self.btn_toAscender = QtGui.QPushButton('Asc.')
		self.btn_toCapsHeight = QtGui.QPushButton('Caps')
		self.btn_toDescender = QtGui.QPushButton('Desc.')
		self.btn_toXHeight = QtGui.QPushButton('X Hgt.')
		self.btn_toBaseline = QtGui.QPushButton('Base')
		self.btn_toYpos = QtGui.QPushButton('Y Pos')
		self.btn_toMpos = QtGui.QPushButton('Measure')
		self.btn_solveY = QtGui.QPushButton('Lineup Min/Max Y')
		self.btn_solveX = QtGui.QPushButton('Lineup Min/Max X')
		
		self.btn_pasteMinY = QtGui.QPushButton('Min Y')
		self.btn_pasteMaxY = QtGui.QPushButton('Max Y')
		self.btn_pasteFMinY = QtGui.QPushButton('Flip Min')
		self.btn_pasteFMaxY = QtGui.QPushButton('Flip Max')
		self.btn_alignLayer_V = QtGui.QPushButton('Vertical')
		self.btn_alignLayer_H = QtGui.QPushButton('Horizontal')

		# - Check buttons
		self.chk_intercept = QtGui.QPushButton('Intercept')
		self.chk_relations = QtGui.QPushButton('Keep Relations')
		self.chk_copy = QtGui.QPushButton('Copy Slope')
		self.chk_italic = QtGui.QPushButton('Italic')
		
		self.chk_copy.setCheckable(True)
		self.chk_italic.setCheckable(True)
		self.chk_intercept.setCheckable(True)
		self.chk_relations.setCheckable(True)
		
		# - Help 
		self.btn_left.setToolTip('Align nodes LEFT.')
		self.btn_centerX.setToolTip('Align nodes CENTER Horizontally.')
		self.btn_right.setToolTip('Align nodes RIGHT.')
		self.btn_top.setToolTip('Align nodes TOP.')
		self.btn_centerY.setToolTip('Align nodes CENTER Verticallylly.')
		self.btn_bottom.setToolTip('Align nodes BOTTOM.')
		self.chk_intercept.setToolTip('Find intersections of selected font metric\nwith slopes on which selected nodes resign.')
		self.chk_relations.setToolTip('Keep relations between selected nodes.')

		self.btn_solveY.setToolTip('Channel Process selected nodes according to Y values')
		self.btn_solveX.setToolTip('Channel Process selected nodes according to X values')

		self.chk_copy.setToolTip('Copy slope between lowest and highest of selected nodes.')
		self.chk_italic.setToolTip('Use Italic Angle as slope.')

		self.btn_pasteMinY.setToolTip('Apply slope to selected nodes.\nReference at MIN Y value.')
		self.btn_pasteMaxY.setToolTip('Apply slope to selected nodes.\nReference at MAX Y value.')
		self.btn_pasteFMinY.setToolTip('Apply X flipped slope to selected nodes.\nReference at MIN Y value.')
		self.btn_pasteFMaxY.setToolTip('Apply X flipped slope to selected nodes.\nReference at MAX Y value.')

		
		self.btn_toAscender.setToolTip('Send selected nodes to Ascender height.')
		self.btn_toCapsHeight.setToolTip('Send selected nodes to Caps Height.')
		self.btn_toDescender.setToolTip('Send selected nodes to Descender height.')
		self.btn_toXHeight.setToolTip('Send selected nodes to X Height.')
		self.btn_toBaseline.setToolTip('Send selected nodes to Baseline.')
		self.btn_toYpos.setToolTip('Send selected nodes to Y coordinate.')
		self.btn_toMpos.setToolTip('Send selected nodes to Measurment Line.\nSHIFT + Click switch intercept.')

		self.btn_alignLayer_V.setToolTip('If Keep Relations is on:\n - Click: Align Top\n - SHIFT + Click: Align Bottom\n - Alt + Click: Align Center')
		self.btn_alignLayer_H.setToolTip('If Keep Relations is on:\n - Click: Align Right\n - SHIFT + Click: Align Left\n - Alt + Click: Align Center')

		# - Combo boxes
		self.cmb_select_V = QtGui.QComboBox()
		self.cmb_select_H = QtGui.QComboBox()
		self.cmb_select_V.addItems(['BBox width', 'Adv. width'])
		self.cmb_select_H.addItems(['BBox height', 'X-Height', 'Caps Height', 'Ascender', 'Descender', 'Adv. height'])

		# - Spin Boxes
		self.edt_toYpos = QtGui.QSpinBox()
		self.edt_toYpos.setToolTip('Destination Y Coordinate')
		self.edt_toYpos.setMaximum(3000)
		self.edt_toYpos.setMinimum(-3000)

		self.spb_prc_V =  QtGui.QSpinBox()
		self.spb_prc_V.setMaximum(100)
		self.spb_prc_V.setSuffix('%')
		self.spb_prc_V.setMinimumWidth(40)

		self.spb_prc_H =  QtGui.QSpinBox()
		self.spb_prc_H.setMaximum(100)
		self.spb_prc_H.setSuffix('%')
		self.spb_prc_H.setMinimumWidth(40)

		self.spb_unit_V =  QtGui.QSpinBox()
		self.spb_unit_V.setMaximum(100)
		self.spb_unit_V.setMinimum(-100)
		self.spb_unit_V.setSuffix(' U')
		self.spb_unit_V.setMinimumWidth(40)

		self.spb_unit_H =  QtGui.QSpinBox()
		self.spb_unit_H.setMaximum(100)
		self.spb_unit_H.setMinimum(-100)
		self.spb_unit_H.setSuffix(' U')
		self.spb_unit_H.setMinimumWidth(40)

		# - Properties
		self.btn_left.setMinimumWidth(40)
		self.btn_right.setMinimumWidth(40)
		self.btn_top.setMinimumWidth(40)
		self.btn_bottom.setMinimumWidth(40)
		self.btn_pasteFMinY.setMinimumWidth(40)
		self.btn_pasteFMaxY.setMinimumWidth(40)
		self.btn_pasteMinY.setMinimumWidth(40)
		self.btn_pasteMaxY.setMinimumWidth(40)
		self.btn_toAscender.setMinimumWidth(40)
		self.btn_toCapsHeight.setMinimumWidth(40)
		self.btn_toDescender.setMinimumWidth(40)
		self.btn_toXHeight.setMinimumWidth(40)
		self.btn_toYpos.setMinimumWidth(40)
		self.edt_toYpos.setMinimumWidth(40)
				
		self.chk_copy.clicked.connect(self.copySlope)
		self.btn_left.clicked.connect(lambda: self.alignNodes('L'))
		self.btn_right.clicked.connect(lambda: self.alignNodes('R'))
		self.btn_top.clicked.connect(lambda: self.alignNodes('T'))
		self.btn_bottom.clicked.connect(lambda: self.alignNodes('B'))
		self.btn_centerX.clicked.connect(lambda: self.alignNodes('C'))
		self.btn_centerY.clicked.connect(lambda: self.alignNodes('E'))
		self.btn_solveY.clicked.connect(lambda: self.alignNodes('Y'))
		self.btn_solveX.clicked.connect(lambda: self.alignNodes('X'))
		self.btn_pasteMinY.clicked.connect(lambda: self.pasteSlope('MinY'))
		self.btn_pasteMaxY.clicked.connect(lambda: self.pasteSlope('MaxY'))
		self.btn_pasteFMinY.clicked.connect(lambda: self.pasteSlope('FLMinY'))
		self.btn_pasteFMaxY.clicked.connect(lambda: self.pasteSlope('FLMaxY'))
		self.btn_bboxCenterX.clicked.connect(lambda: self.alignNodes('BBoxCenterX'))
		self.btn_bboxCenterY.clicked.connect(lambda: self.alignNodes('BBoxCenterY'))
		self.btn_peerCenterX.clicked.connect(lambda: self.alignNodes('peerCenterX'))
		self.btn_peerCenterY.clicked.connect(lambda: self.alignNodes('peerCenterY'))
		self.btn_toAscender.clicked.connect(lambda: self.alignNodes('FontMetrics_0'))
		self.btn_toCapsHeight.clicked.connect(lambda: self.alignNodes('FontMetrics_1'))
		self.btn_toDescender.clicked.connect(lambda: self.alignNodes('FontMetrics_2'))
		self.btn_toXHeight.clicked.connect(lambda: self.alignNodes('FontMetrics_3'))
		self.btn_toBaseline.clicked.connect(lambda: self.alignNodes('FontMetrics_4'))
		self.btn_toYpos.clicked.connect(lambda: self.alignNodes('FontMetrics_5'))
		self.btn_toMpos.clicked.connect(lambda: self.alignNodes('FontMetrics_6'))
		self.btn_alignLayer_V.clicked.connect(lambda: self.alignNodes('Layer_V'))
		self.btn_alignLayer_H.clicked.connect(lambda: self.alignNodes('Layer_H'))

		# - Build Layout
		self.addWidget(self.btn_left, 			0, 0, 1, 1)
		self.addWidget(self.btn_right, 			0, 1, 1, 1)
		self.addWidget(self.btn_top, 			0, 2, 1, 1)
		self.addWidget(self.btn_bottom,	 		0, 3, 1, 1)
		self.addWidget(self.btn_centerX,		1, 0, 1, 2)
		self.addWidget(self.btn_centerY,		1, 2, 1, 2)
		self.addWidget(self.btn_bboxCenterX,	2, 0, 1, 2)
		self.addWidget(self.btn_bboxCenterY,	2, 2, 1, 2)
		self.addWidget(self.btn_peerCenterX,	3, 0, 1, 2)
		self.addWidget(self.btn_peerCenterY,	3, 2, 1, 2)
		
		self.addWidget(QtGui.QLabel('Nodes: Align to Font and Glyph metrics'), 4, 0, 1, 4)
		self.addWidget(self.btn_toAscender,		5, 0, 1, 1)
		self.addWidget(self.btn_toCapsHeight,	5, 1, 1, 1)
		self.addWidget(self.btn_toDescender,	5, 2, 1, 1)
		self.addWidget(self.btn_toXHeight,		5, 3, 1, 1)
		self.addWidget(self.btn_toBaseline,		6, 0, 1, 1)
		self.addWidget(self.edt_toYpos,			6, 1, 1, 1)
		self.addWidget(self.btn_toYpos,			6, 2, 1, 1)
		self.addWidget(self.btn_toMpos, 		6, 3, 1, 1)
		self.addWidget(self.chk_relations, 		7, 0, 1, 2)
		self.addWidget(self.chk_intercept, 		7, 2, 1, 2)

		#self.addWidget(QtGui.QLabel('Align to Glyph Layer'), 	6, 0, 1, 4)
		self.addWidget(self.cmb_select_V, 		8, 0, 1, 1)
		self.addWidget(self.spb_prc_V, 			8, 1, 1, 1)
		self.addWidget(self.spb_unit_V, 		8, 2, 1, 1)
		self.addWidget(self.btn_alignLayer_V, 	8, 3, 1, 1)
		self.addWidget(self.cmb_select_H, 		9, 0, 1, 1)
		self.addWidget(self.spb_prc_H, 			9, 1, 1, 1)
		self.addWidget(self.spb_unit_H, 		9, 2, 1, 1)
		self.addWidget(self.btn_alignLayer_H, 	9, 3, 1, 1)
		
		self.addWidget(QtGui.QLabel('Nodes: Channel processing and slopes'), 10,0,1,4)
		self.addWidget(self.btn_solveY, 		11, 0, 1, 2)
		self.addWidget(self.btn_solveX, 		11, 2, 1, 2)
		self.addWidget(self.chk_copy,			12, 0, 1, 3)
		self.addWidget(self.chk_italic,			12, 3, 1, 1)
		self.addWidget(self.btn_pasteMinY,		13, 0, 1, 1)
		self.addWidget(self.btn_pasteMaxY,		13, 1, 1, 1)
		self.addWidget(self.btn_pasteFMinY,		13, 2, 1, 1)
		self.addWidget(self.btn_pasteFMaxY,		13, 3, 1, 1)

	def copySlope(self):
		if self.chk_copy.isChecked():
			self.chk_copy.setText('Reset Slope')
			self.chk_italic.setChecked(False)

			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				selection = glyph.selectedNodes(layer)
				self.copyLine[layer] = Vector(selection[0], selection[-1])
		else:
			self.chk_copy.setText('Copy Slope')
			self.chk_italic.setChecked(False)

	def pasteSlope(self, mode):
		if self.chk_copy.isChecked() or self.chk_italic.isChecked():
			glyph = eGlyph()
			wLayers = glyph._prepareLayers(pLayers)
			italicAngle = glyph.package.italicAngle_value
			control = (True, False)
			
			for layer in wLayers:
				selection = [eNode(node) for node in glyph.selectedNodes(layer)]
				srcLine = self.copyLine[layer] if not self.chk_italic.isChecked() else None

				if mode == 'MinY':
					dstVector = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					
					if not self.chk_italic.isChecked():
						dstVector.slope = srcLine.slope
					else:
						dstVector.angle = -1*italicAngle

				elif mode == 'MaxY':
					dstVector = Vector(max(selection, key=lambda item: item.y).fl, min(selection, key=lambda item: item.y).fl)
					
					if not self.chk_italic.isChecked():
						dstVector.slope = srcLine.slope
					else:
						dstVector.angle = -1*italicAngle

				elif mode == 'FLMinY':
					dstVector = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					
					if not self.chk_italic.isChecked():
						dstVector.slope = -1.*srcLine.slope
					else:
						dstVector.angle = italicAngle

				elif mode == 'FLMaxY':
					dstVector = Vector(max(selection, key=lambda item: item.y).fl, min(selection, key=lambda item: item.y).fl)
					
					if not self.chk_italic.isChecked():
						dstVector.slope = -1.*srcLine.slope
					else:
						dstVector.angle = italicAngle
				
				for node in selection:
					node.alignTo(dstVector, control)

			glyph.updateObject(glyph.fl, 'Paste Slope @ %s.' %'; '.join(wLayers))
			glyph.update()


	def alignNodes(self, mode):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				extend_nodes = None if self.chk_relations.isChecked() else eNode
				selection = glyph.selectedNodes(layer, extend=extend_nodes)
				italicAngle = glyph.package.italicAngle_value

				if mode == 'L':
					target = min(selection, key=lambda item: item.x)
					control = (True, False)

				elif mode == 'R':
					target = max(selection, key=lambda item: item.x)
					control = (True, False)
				
				elif mode == 'T':
					temp_target = max(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
					control = (False, True)
				
				elif mode == 'B':
					temp_target = min(selection, key=lambda item: item.y)
					newX = temp_target.x
					newY = temp_target.y
					toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
					control = (False, True)
				
				elif mode == 'C':
					newX = (min(selection, key=lambda item: item.x).x + max(selection, key=lambda item: item.x).x)/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)

				elif mode == 'E':
					newY = (min(selection, key=lambda item: item.y).y + max(selection, key=lambda item: item.y).y)/2
					newX = 0.
					target = fl6.flNode(newX, newY)
					control = (False, True)

				elif mode == 'Y':
					target = Vector(min(selection, key=lambda item: item.y).fl, max(selection, key=lambda item: item.y).fl)
					control = (True, False)

				elif mode == 'X':
					target = Vector(min(selection, key=lambda item: item.x).fl, max(selection, key=lambda item: item.x).fl)
					control = (False, True)

				elif mode == 'BBoxCenterX':
					newX = glyph.layer(layer).boundingBox.x() + glyph.layer(layer).boundingBox.width()/2
					newY = 0.
					target = fl6.flNode(newX, newY)
					control = (True, False)

				elif mode == 'BBoxCenterY':
					newX = 0.
					newY = glyph.layer(layer).boundingBox.y() + glyph.layer(layer).boundingBox.height()/2
					target = fl6.flNode(newX, newY)
					control = (False, True)

				elif 'FontMetrics' in mode:
					layerMetrics = glyph.fontMetricsInfo(layer)
					italicAngle = glyph.package.italicAngle_value
					
					newX = 0.
					toMaxY = True

					if '0' in mode:
						newY = layerMetrics.ascender
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '1' in mode:
						newY = layerMetrics.capsHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '2' in mode:
						newY = layerMetrics.descender
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '3' in mode:
						newY = layerMetrics.xHeight
						toMaxY = True if modifiers == QtCore.Qt.ShiftModifier else False 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'

					elif '4' in mode:
						newY = 0
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '5' in mode:
						newY = self.edt_toYpos.value
						toMaxY = False if modifiers == QtCore.Qt.ShiftModifier else True 
						container_mode = 'LT' if modifiers == QtCore.Qt.ShiftModifier else 'LB'

					elif '6' in mode:
						newY = glyph.mLine()
						toMaxY = newY >= 0 
						container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'LT'
						if modifiers == QtCore.Qt.ShiftModifier: toMaxY = not toMaxY

				elif mode == 'Layer_V':
					if 'BBox' in self.cmb_select_V.currentText:
						width = glyph.layer(layer).boundingBox.width()
						origin = glyph.layer(layer).boundingBox.x()
				
					elif 'Adv' in self.cmb_select_V.currentText:
						width = glyph.getAdvance(layer)
						origin = 0.

					target = fl6.flNode(float(width)*self.spb_prc_V.value/100 + origin + self.spb_unit_V.value, 0)
					container_mode = 'LB' if modifiers == QtCore.Qt.ShiftModifier else 'RB'
					control = (True, False)

					container_mode_H = ['R','L'][modifiers == QtCore.Qt.ShiftModifier]
					container_mode_H = [container_mode_H,'C'][modifiers == QtCore.Qt.AltModifier]
					container_mode_V = 'B'
					container_mode = container_mode_H + container_mode_V

				elif mode == 'Layer_H':
					metrics = pFontMetrics(glyph.package)

					if 'BBox' in self.cmb_select_H.currentText:
						height = glyph.layer(layer).boundingBox.height()
						origin = glyph.layer(layer).boundingBox.y()
					
					elif 'Adv' in self.cmb_select_H.currentText:
						height = glyph.layer(layer).advanceHeight
						origin = 0.

					elif 'X-H' in self.cmb_select_H.currentText:
						height = metrics.getXHeight(layer)
						origin = 0.

					elif 'Caps' in self.cmb_select_H.currentText:
						height = metrics.getCapsHeight(layer)
						origin = 0.

					elif 'Ascender' in self.cmb_select_H.currentText:
						height = metrics.getAscender(layer)
						origin = 0.			

					elif 'Descender' in self.cmb_select_H.currentText:
						height = metrics.getDescender(layer)
						origin = 0.		

					target = fl6.flNode(0, float(height)*self.spb_prc_H.value/100 + origin + self.spb_unit_H.value)
					
					container_mode_H = 'L'
					container_mode_V = ['T','B'][modifiers == QtCore.Qt.ShiftModifier]
					container_mode_V = [container_mode_V,'E'][modifiers == QtCore.Qt.AltModifier]
					container_mode = container_mode_H + container_mode_V

					control = (False, True)

				if self.chk_relations.isChecked():
					container = eNodesContainer(selection)
					
					if 'FontMetrics' in mode:
						target = fl6.flNode(newX, newY)
						control = (False, True)												
					
					container.alignTo(target, container_mode, control)

				else:
					for node in selection:
						if 'FontMetrics' in mode or mode == 'T' or mode == 'B':
							if italicAngle != 0 and not self.chk_intercept.isChecked():
								tempTarget = Coord(node.fl)
								tempTarget.setAngle(italicAngle)

								target = fl6.flNode(tempTarget.getWidth(newY), newY)
								control = (True, True)
							
							elif self.chk_intercept.isChecked():
								pairUp = node.getMaxY().position
								pairDown = node.getMinY().position
								pairPos = pairUp if toMaxY else pairDown
								newLine = Line(node.fl.position, pairPos)
								newX = newLine.solve_x(newY)

								target = fl6.flNode(newX, newY)
								control = (True, True)

							else:
								target = fl6.flNode(newX, newY)
								control = (False, True)

						if mode == 'peerCenterX':
							newX = node.x + (node.getPrevOn().x + node.getNextOn().x - 2*node.x)/2.
							newY = node.y
							target = fl6.flNode(newX, newY)
							control = (True, False)

						elif mode == 'peerCenterY':
							newX = node.x
							newY = node.y + (node.getPrevOn().y + node.getNextOn().y - 2*node.y)/2.
							target = fl6.flNode(newX, newY)
							control = (False, True)

						# - Execute Align ----------
						node.alignTo(target, control)

			glyph.updateObject(glyph.fl, 'Align Nodes @ %s.' %'; '.join(wLayers))
			glyph.update()


class copyNodes(QtGui.QGridLayout):
	# - Split/Break contour 
	def __init__(self):
		super(copyNodes, self).__init__()

		# - Init
		self.copy_align_state = None
		self.node_bank = {}

		# - Buttons
		self.chk_BL = QtGui.QPushButton('B L')
		self.chk_TL = QtGui.QPushButton('T L')
		self.chk_BR = QtGui.QPushButton('B R')
		self.chk_TR = QtGui.QPushButton('T R')

		self.chk_flipH = QtGui.QPushButton('Flip H')
		self.chk_flipV = QtGui.QPushButton('Flip V')
		self.chk_reverse = QtGui.QPushButton('Reverse')

		self.chk_copy = QtGui.QPushButton('Copy')
		self.btn_paste = QtGui.QPushButton('Paste')
		self.btn_inject = QtGui.QPushButton('Inject')

		self.btn_inject.setEnabled(False)

		self.chk_BL.setCheckable(True)
		self.chk_TL.setCheckable(True)
		self.chk_BR.setCheckable(True)
		self.chk_TR.setCheckable(True)
		self.chk_copy.setCheckable(True)
		self.chk_flipH.setCheckable(True)
		self.chk_flipV.setCheckable(True)
		self.chk_reverse.setCheckable(True)

		self.chk_BL.setChecked(False)
		self.chk_TL.setChecked(False)
		self.chk_BR.setChecked(False)
		self.chk_TR.setChecked(False)
		self.chk_flipH.setChecked(False)
		self.chk_flipV.setChecked(False)
		self.chk_reverse.setChecked(False)
		
		self.chk_BL.setMinimumWidth(40)
		self.chk_TL.setMinimumWidth(40)
		self.chk_BR.setMinimumWidth(40)
		self.chk_TR.setMinimumWidth(40)
		self.chk_flipH.setMinimumWidth(40)
		self.chk_flipV.setMinimumWidth(40)
		self.chk_reverse.setMinimumWidth(40)
		self.chk_copy.setMinimumWidth(80)
		self.btn_paste.setMinimumWidth(80)
		self.btn_inject.setMinimumWidth(80)

		self.chk_BL.setToolTip('Align:\nTo Bottom Left bounding box of selection.') 
		self.chk_TL.setToolTip('Align:\nTo Top Left bounding box of selection.') 
		self.chk_BR.setToolTip('Align:\nTo Bottom Right bounding box of selection.') 
		self.chk_TR.setToolTip('Align:\nTo Top Right bounding box of selection.') 
		self.chk_copy.setToolTip('Copy selected nodes to memory.')
		self.btn_paste.setToolTip('Paste nodes.\nAdvanced operations:\n - Shift + Click: Inject source behind first node selected;\n - Alt + Click: Replace selection with source;') 
		self.btn_inject.setToolTip('Inject nodes') 
		
		self.chk_BL.clicked.connect(lambda: self.setAlignStates('LB'))
		self.chk_TL.clicked.connect(lambda: self.setAlignStates('LT'))
		self.chk_BR.clicked.connect(lambda: self.setAlignStates('RB'))
		self.chk_TR.clicked.connect(lambda: self.setAlignStates('RT'))
		
		self.chk_copy.clicked.connect(lambda: self.copyNodes())
		self.btn_paste.clicked.connect(lambda: self.pasteNodes())
		#self.btn_inject.clicked.connect(lambda : self.setDirection(True))

		#self.addWidget(self.btn_inject, 0, 3, 1, 1)

		self.addWidget(self.chk_TL, 		0, 0, 1, 1)
		self.addWidget(self.chk_TR, 		0, 1, 1, 1)
		self.addWidget(self.chk_flipH, 		0, 2, 1, 1)
		self.addWidget(self.chk_flipV, 		0, 3, 1, 1)
		self.addWidget(self.chk_BL, 		1, 0, 1, 1)
		self.addWidget(self.chk_BR, 		1, 1, 1, 1)
		self.addWidget(self.chk_reverse,	1, 2, 1, 2)
	
		self.addWidget(self.chk_copy, 		3, 0, 1, 2)
		self.addWidget(self.btn_paste, 		3, 2, 1, 2)

	def setAlignStates(self, align_state):
		self.copy_align_state = align_state
		if align_state != 'LB' and self.chk_BL.isChecked(): self.chk_BL.setChecked(False)
		if align_state != 'LT' and self.chk_TL.isChecked(): self.chk_TL.setChecked(False)
		if align_state != 'RB' and self.chk_BR.isChecked(): self.chk_BR.setChecked(False)
		if align_state != 'RT' and self.chk_TR.isChecked(): self.chk_TR.setChecked(False)
		
		if all([not self.chk_BL.isChecked(), 
				not self.chk_TL.isChecked(), 
				not self.chk_BR.isChecked(), 
				not self.chk_TR.isChecked()]): 
			self.copy_align_state = None

	def copyNodes(self):
		if self.chk_copy.isChecked():
			glyph = eGlyph()
			self.chk_copy.setText('Reset')
			wLayers = glyph._prepareLayers(pLayers)
			self.node_bank = {layer : eNodesContainer([node.clone() for node in glyph.selectedNodes(layer)], extend=eNode) for layer in wLayers}
		else:
			self.node_bank = {}
			self.chk_copy.setText('Copy')

	def pasteNodes(self):
		if self.chk_copy.isChecked():
			process_glyphs = getProcessGlyphs(pMode)
			modifiers = QtGui.QApplication.keyboardModifiers()
			update_flag = False

			for glyph in process_glyphs:
				wLayers = glyph._prepareLayers(pLayers)
				
				for layer in wLayers:
					if self.node_bank.has_key(layer):
						dst_container = eNodesContainer(glyph.selectedNodes(layer), extend=eNode)

						if len(dst_container):
							src_countainer = self.node_bank[layer].clone()
							src_transform = QtGui.QTransform()
																		
							# - Transform
							if self.chk_flipH.isChecked() or self.chk_flipV.isChecked():
								scaleX = -1 if self.chk_flipH.isChecked() else 1
								scaleY = -1 if self.chk_flipV.isChecked() else 1
								dX = src_countainer.x() + src_countainer.width()/2.
								dY = src_countainer.y() + src_countainer.height()/2.

								src_transform.translate(dX, dY)
								src_transform.scale(scaleX, scaleY)
								src_transform.translate(-dX, -dY)
								src_countainer.applyTransform(src_transform)
								

							# - Align source
							if self.copy_align_state is None:
								src_countainer.shift(*src_countainer[0].diffTo(dst_container[0]))
							else:
								src_countainer.alignTo(dst_container, self.copy_align_state, align=(True,True))

							if self.chk_reverse.isChecked(): 
								src_countainer = src_countainer.reverse()

							# - Process
							if modifiers == QtCore.Qt.ShiftModifier: # - Inject mode - insert source after first node index
								dst_container[0].contour.insert(dst_container[0].index, [node.fl for node in src_countainer.nodes])
								update_flag = True

							elif modifiers == QtCore.Qt.AltModifier: # - Overwrite mode - delete all nodes in selection and replace with source
								insert_index = dst_container[0].index
								insert_contour = dst_container[0].contour
								insert_contour.removeNodesBetween(dst_container[0].fl, dst_container[-1].getNextOn())
								insert_contour.insert(dst_container[0].index, [node.fl for node in src_countainer.nodes])
								insert_contour.removeAt(insert_index + len(src_countainer))

								update_flag = True

							else: # - Paste mode - remap node by node
								if len(dst_container) == len(self.node_bank[layer]):
									for nid in range(len(dst_container)):
										dst_container[nid].fl.x = src_countainer[nid].x 
										dst_container[nid].fl.y = src_countainer[nid].y 

									update_flag = True
								else:
									update_flag = False
									warnings.warn('Layer: {};\tCount Mismatch: Selected nodes [{}]; Source nodes [{}].'.format(layer, len(dst_container), len(src_countainer)), NodeWarning)
							
				# - Done							
				if update_flag:	
					glyph.updateObject(glyph.fl, 'Paste Nodes @ %s.' %'; '.join(wLayers))
					glyph.update()

class advMovement(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(advMovement, self).__init__()

		# - Init
		self.aux = aux
		self.methodList = ['Move', 'Simple Move', 'Interpolated Move', 'Slanted Grid Move', 'Slope walker']
		
		# - Methods
		self.cmb_methodSelector = QtGui.QComboBox()
		self.cmb_methodSelector.addItems(self.methodList)
		self.cmb_methodSelector.setToolTip('Select movement method')
		self.chk_percent = QtGui.QCheckBox('% of BBox')
		self.chk_percent.setToolTip('Interpret new positional coordinates as if they were scaled by percent given in (X,Y)\nEquivalent to affine scaling of selected nodes in respect to the Layers BoundingBox')
		
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
		self.chk_percent.clicked.connect(self.toggleInput)
		
		self.edt_offX = QtGui.QLineEdit('1.0')
		self.edt_offY = QtGui.QLineEdit('1.0')
		self.edt_offX.setToolTip('X offset')
		self.edt_offY.setToolTip('Y offset')

		# - Layout
		self.lay_btn = QtGui.QGridLayout()

		self.lay_btn.addWidget(self.cmb_methodSelector, 0, 0, 1, 5)
		self.lay_btn.addWidget(self.chk_percent, 		0, 5, 1, 1)
		self.lay_btn.addWidget(QtGui.QLabel('X:'), 		1, 0, 1, 1)
		self.lay_btn.addWidget(self.edt_offX, 			1, 1, 1, 1)
		self.lay_btn.addWidget(self.btn_up, 			1, 2, 1, 2)
		self.lay_btn.addWidget(QtGui.QLabel('Y:'), 		1, 4, 1, 1)
		self.lay_btn.addWidget(self.edt_offY, 			1, 5, 1, 1)
		self.lay_btn.addWidget(self.btn_left, 			2, 0, 1, 2)
		self.lay_btn.addWidget(self.btn_down, 			2, 2, 1, 2)
		self.lay_btn.addWidget(self.btn_right, 			2, 4, 1, 2)

		self.addLayout(self.lay_btn)

		
	def toggleInput(self):
		if self.chk_percent.isChecked():
			self.edt_offX.setText(str(float(self.edt_offX.text)/100)) 
			self.edt_offY.setText(str(float(self.edt_offY.text)/100))
		else:
			self.edt_offX.setText(str(float(self.edt_offX.text)*100)) 
			self.edt_offY.setText(str(float(self.edt_offY.text)*100))

	def moveNodes(self, offset_x, offset_y, method, inPercent):
		# - Init
		font = pFont()
		glyph = eGlyph()
		italic_angle = font.getItalicAngle()

		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				selectedNodes = glyph.selectedNodes(layer=layer, extend=eNode)
				
				
				# -- Scaling move - coordinates as percent of position
				def scaleOffset(node, off_x, off_y):
					return (-node.x + width*(float(node.x)/width + offset_x), -node.y + height*(float(node.y)/height + offset_y))

				width = glyph.layer(layer).boundingBox.width() # glyph.layer().advanceWidth
				height = glyph.layer(layer).boundingBox.height() # glyph.layer().advanceHeight

				# - Process
				if method == self.methodList[0]:
					for node in selectedNodes:
						if node.isOn:
							if inPercent:						
								node.smartShift(*scaleOffset(node, offset_x, offset_y))
							else:
								node.smartShift(offset_x, offset_y)

				elif method == self.methodList[1]:
					for node in selectedNodes:
						if inPercent:						
							node.shift(*scaleOffset(node, offset_x, offset_y))
						else:
							node.shift(offset_x, offset_y)

				elif method == self.methodList[2]:
					for node in selectedNodes:
						if inPercent:						
							node.interpShift(*scaleOffset(node, offset_x, offset_y))
						else:
							node.interpShift(offset_x, offset_y)

				elif method == self.methodList[3]:
					if italic_angle != 0:
						for node in selectedNodes:
							if inPercent:						
								node.slantShift(*scaleOffset(node, offset_x, offset_y))
							else:
								node.slantShift(offset_x, offset_y, italic_angle)
					else:
						for node in selectedNodes:
							if inPercent:						
								node.smartShift(*scaleOffset(node, offset_x, offset_y))
							else:
								node.smartShift(offset_x, offset_y)

				elif method == self.methodList[4]:			
					current_layer = glyph.activeLayer().name

					if len(self.aux.copyLine) and current_layer in self.aux.copyLine:
						for node in selectedNodes:
							node.slantShift(offset_x, offset_y, -90 + self.aux.copyLine[current_layer].angle)				
					else:
						warnings.warn('No slope information for layer found!\nNOTE:\tPlease <<Copy Slope>> first using TypeRig Node align toolbox.', LayerWarning)

			# - Finish it
			glyph.update()
			glyph.updateObject(glyph.fl, 'Node: %s @ %s.' %(method, '; '.join(wLayers)))

	def onUp(self):
		self.moveNodes(.0, float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText), inPercent=self.chk_percent.isChecked())

	def onDown(self):
		self.moveNodes(.0, -float(self.edt_offY.text), method=str(self.cmb_methodSelector.currentText), inPercent=self.chk_percent.isChecked())
			
	def onLeft(self):
		self.moveNodes(-float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText), inPercent=self.chk_percent.isChecked())
			
	def onRight(self):
		self.moveNodes(float(self.edt_offX.text), .0, method=str(self.cmb_methodSelector.currentText), inPercent=self.chk_percent.isChecked())

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.KeyboardOverride = False
		
		# - Add widgets to main dialog -------------------------
		layoutV.addWidget(QtGui.QLabel('Nodes: Basic Operations'))
		layoutV.addLayout(basicOps())

		layoutV.addWidget(QtGui.QLabel('Nodes: Align'))
		self.alignNodes = alignNodes()
		layoutV.addLayout(self.alignNodes)

		layoutV.addWidget(QtGui.QLabel('Nodes: Copy/Paste'))
		layoutV.addLayout(copyNodes())

		layoutV.addWidget(QtGui.QLabel('Nodes: Movement'))
		self.advMovement = advMovement(self.alignNodes)
		layoutV.addLayout(self.advMovement)  

		# - Capture Kyaboard ----------------------------------
		self.btn_capture = QtGui.QPushButton('Capture Keyboard')
		self.btn_capture.setCheckable(True)
		self.btn_capture.setToolTip('Click to capture keyboard arrows input.\nNote:\n+10 SHIFT\n+100 CTRL\n Exit ESC')
		self.btn_capture.clicked.connect(self.captureKeyaboard)

		layoutV.addWidget(self.btn_capture)

		# - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

	# - Capture keyboard -------------------------------------
	def keyPressEvent(self, eventQKeyEvent):
		if self.KeyboardOverride:
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
				addon = 10.0 if not self.advMovement.chk_percent.isChecked() else 0.1
			elif modifier == QtCore.Qt.ControlModifier:
				addon = 100.0 if not self.advMovement.chk_percent.isChecked() else 1.0
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
				shiftXY = (.0,.0)
			
			# - Move
			self.advMovement.moveNodes(*shiftXY, method=str(self.advMovement.cmb_methodSelector.currentText),  inPercent=self.advMovement.chk_percent.isChecked())

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
	test.setGeometry(100, 100, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()