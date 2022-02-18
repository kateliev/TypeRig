#FLM: TR: Metrics
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

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph, eGlyph
from typerig.proxy.fl.objects.node import eNodesContainer, eNode
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init ------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Metrics', '1.40'

# - Sub widgets ------------------------
class TRMLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(TRMLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'{Glyph Name}', lambda: self.setText(eGlyph().name))
		menu.addSeparator()
		menu.addAction(u'To Lowercase', lambda: self.setText(self.text.lower()))
		menu.addAction(u'To Uppercase', lambda: self.setText(self.text.upper()))
		menu.addSeparator()
		menu.addAction(u'EQ', lambda: self.setText('=%s' %self.text))
		menu.addAction(u'LSB', lambda: self.setText('=lsb("%s")' %self.text))
		menu.addAction(u'RSB', lambda: self.setText('=rsb("%s")' %self.text))
		menu.addAction(u'ADV', lambda: self.setText('=width("%s")' %self.text))
		menu.addAction(u'L', lambda: self.setText('=l("%s")' %self.text))
		menu.addAction(u'R', lambda: self.setText('=r("%s")' %self.text))
		menu.addAction(u'W', lambda: self.setText('=w("%s")' %self.text))
		menu.addAction(u'G', lambda: self.setText('=g("%s")' %self.text))
		menu.addSeparator()
		menu.addAction(u'.salt', lambda: self.setText('%s.salt' %self.text))
		menu.addAction(u'.calt', lambda: self.setText('%s.calt' %self.text))
		menu.addAction(u'.ss0', lambda: self.setText('%s.ss0' %self.text))
		menu.addAction(u'.locl', lambda: self.setText('%s.locl' %self.text))
		menu.addAction(u'.smcp', lambda: self.setText('%s.smcp' %self.text))
		menu.addAction(u'.cscp', lambda: self.setText('%s.cscp' %self.text))
		menu.addAction(u'.onum', lambda: self.setText('%s.onum' %self.text))
		menu.addAction(u'.pnum', lambda: self.setText('%s.pnum' %self.text))
		menu.addAction(u'.tnum', lambda: self.setText('%s.tnum' %self.text))

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
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:	
			wLayers = glyph._prepareLayers(pLayers)
			
			copyOrder = [False]*3
			srcGlyphs = [glyph.name]*3
					
			adjPercents = (self.spb_lsb_percent.value, self.spb_rsb_percent.value, self.spb_adv_percent.value)
			adjUnits = (self.spb_lsb_units.value, self.spb_rsb_units.value, self.spb_adv_units.value)
			
			for layer in wLayers:
				glyph.setLSB(glyph.getLSB(layer)*adjPercents[0]/100 + adjUnits[0], layer)
				glyph.setRSB(glyph.getRSB(layer)*adjPercents[1]/100 + adjUnits[1], layer)
				glyph.setAdvance(glyph.getAdvance(layer)*adjPercents[2]/100 + adjUnits[2], layer)

			glyph.updateObject(glyph.fl, 'Adjust Metrics @ %s | %s' %('; '.join(wLayers), zip(('LSB','RSB','ADV'), adjPercents, adjUnits)))
			glyph.update()

class metrics_copy(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_copy, self).__init__()

		# - Edit Fields
		self.edt_lsb = TRMLineEdit()
		self.edt_adv = TRMLineEdit()
		self.edt_rsb = TRMLineEdit()
		self.edt_vsb = TRMLineEdit()

		self.edt_lsb.setToolTip('Set Left Side-bearing')
		self.edt_adv.setToolTip('Set Right Side-bearing')
		self.edt_rsb.setToolTip('Set Advance width')
		self.edt_vsb.setToolTip('Set Vertical location as measured from Baseline - Vertical Side-bearing')

		self.edt_lsb.setPlaceholderText('Glyph Name')
		self.edt_adv.setPlaceholderText('Glyph Name')
		self.edt_rsb.setPlaceholderText('Glyph Name')
		self.edt_vsb.setPlaceholderText('Glyph Name')

		# - Spin Box
		self.spb_lsb_percent =  QtGui.QSpinBox()
		self.spb_adv_percent = QtGui.QSpinBox()
		self.spb_rsb_percent = QtGui.QSpinBox()
		self.spb_vsb_percent = QtGui.QSpinBox()

		self.spb_lsb_units =  QtGui.QSpinBox()
		self.spb_adv_units = QtGui.QSpinBox()
		self.spb_rsb_units = QtGui.QSpinBox()
		self.spb_vsb_units = QtGui.QSpinBox()

		self.spb_lsb_percent.setMaximum(200)
		self.spb_adv_percent.setMaximum(200)
		self.spb_rsb_percent.setMaximum(200)
		self.spb_vsb_percent.setMaximum(200)
		self.spb_lsb_units.setMaximum(200)
		self.spb_adv_units.setMaximum(200)
		self.spb_rsb_units.setMaximum(200)
		self.spb_vsb_units.setMaximum(200)
		self.spb_lsb_units.setMinimum(-200)
		self.spb_adv_units.setMinimum(-200)
		self.spb_rsb_units.setMinimum(-200)
		self.spb_vsb_units.setMinimum(-200)

		self.spb_lsb_percent.setSuffix('%')
		self.spb_adv_percent.setSuffix('%')
		self.spb_rsb_percent.setSuffix('%')
		self.spb_vsb_percent.setSuffix('%')
		self.spb_lsb_units.setSuffix(' u')
		self.spb_adv_units.setSuffix(' u')
		self.spb_rsb_units.setSuffix(' u')
		self.spb_vsb_units.setSuffix(' u')

		self.spb_lsb_percent.setMaximumWidth(50)
		self.spb_adv_percent.setMaximumWidth(50)
		self.spb_rsb_percent.setMaximumWidth(50)
		self.spb_vsb_percent.setMaximumWidth(50)
		self.spb_lsb_units.setMaximumWidth(50)
		self.spb_adv_units.setMaximumWidth(50)
		self.spb_rsb_units.setMaximumWidth(50)
		self.spb_vsb_units.setMaximumWidth(50)

		self.reset_fileds()

		# - Buttons
		self.btn_copyMetrics = QtGui.QPushButton('&Copy Metrics')
		self.btn_copyMetrics.clicked.connect(self.copyMetrics)

		# - Build
		self.addWidget(QtGui.QLabel('ADV:'), 	0, 0, 1, 1)
		self.addWidget(self.edt_adv, 			0, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 		0, 4, 1, 1)
		self.addWidget(self.spb_adv_percent, 	0, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 		0, 6, 1, 1)
		self.addWidget(self.spb_adv_units, 		0, 7, 1, 1)

		self.addWidget(QtGui.QLabel('LSB:'), 	1, 0, 1, 1)
		self.addWidget(self.edt_lsb, 			1, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 		1, 4, 1, 1)
		self.addWidget(self.spb_lsb_percent,	1, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 		1, 6, 1, 1)
		self.addWidget(self.spb_lsb_units, 		1, 7, 1, 1)

		self.addWidget(QtGui.QLabel('RSB:'), 	2, 0, 1, 1)
		self.addWidget(self.edt_rsb, 			2, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 		2, 4, 1, 1)
		self.addWidget(self.spb_rsb_percent, 	2, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 		2, 6, 1, 1)
		self.addWidget(self.spb_rsb_units, 		2, 7, 1, 1)

		self.addWidget(QtGui.QLabel('VSB:'), 	3, 0, 1, 1)
		self.addWidget(self.edt_vsb, 			3, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 		3, 4, 1, 1)
		self.addWidget(self.spb_vsb_percent, 	3, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 		3, 6, 1, 1)
		self.addWidget(self.spb_vsb_units, 		3, 7, 1, 1)

		self.addWidget(self.btn_copyMetrics, 	4, 0, 1, 8)

	def reset_fileds(self):
		# - Reset text fields
		self.edt_lsb.setText('')
		self.edt_adv.setText('')
		self.edt_rsb.setText('')
		self.edt_vsb.setText('')
		
		# - Reset spin-box
		self.spb_lsb_percent.setValue(100)
		self.spb_adv_percent.setValue(100)
		self.spb_rsb_percent.setValue(100)
		self.spb_vsb_percent.setValue(100)
		
		self.spb_lsb_units.setValue(0)
		self.spb_adv_units.setValue(0)
		self.spb_rsb_units.setValue(0)
		self.spb_vsb_units.setValue(0)

	def copyMetrics(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:			
			copyOrder = ['--' in name for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text, self.edt_vsb.text)]
			srcGlyphs = [str(name).replace('--', '') if len(name) else None for name in (self.edt_lsb.text, self.edt_rsb.text, self.edt_adv.text, self.edt_vsb.text)]
			
			adjPercents = (self.spb_lsb_percent.value, self.spb_rsb_percent.value, self.spb_adv_percent.value, self.spb_vsb_percent.value)
			adjUnits = (self.spb_lsb_units.value, self.spb_rsb_units.value, self.spb_adv_units.value, self.spb_vsb_units.value)
			
			glyph.copyMetricsbyName(srcGlyphs, pLayers, copyOrder, adjPercents, adjUnits)

			glyph.updateObject(glyph.fl, 'Copy Metrics | LSB: %s; RSB: %s; ADV:%s.' %(srcGlyphs[0], srcGlyphs[1], srcGlyphs[2]))
			glyph.update()
		
		self.reset_fileds()


class bbox_copy(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(bbox_copy, self).__init__()

		# - Edit Fields
		self.edt_width = QtGui.QLineEdit()
		self.edt_height = QtGui.QLineEdit()

		self.edt_width.setPlaceholderText('Glyph Name')
		self.edt_height.setPlaceholderText('Glyph Name')

		# - Spin Box
		self.spb_bbox_percent =  QtGui.QSpinBox()
		self.spb_bbox_units =  QtGui.QSpinBox()

		self.spb_bbox_percent.setMaximum(200)
		self.spb_bbox_units.setMaximum(200)
		self.spb_bbox_units.setMinimum(-200)

		self.spb_bbox_percent.setSuffix('%')
		self.spb_bbox_units.setSuffix(' u')

		self.spb_bbox_percent.setMaximumWidth(50)
		self.spb_bbox_units.setMaximumWidth(50)

		self.reset_fileds()

		# - Buttons
		self.btn_copyBBox_width = QtGui.QPushButton('&Copy Width')
		self.btn_copyBBox_height = QtGui.QPushButton('&Copy Height')
		self.btn_copyBBox_width.clicked.connect(lambda: self.copy_bbox(False))
		self.btn_copyBBox_height.clicked.connect(lambda: self.copy_bbox(True))
		
		# - Build
		self.addWidget(QtGui.QLabel('SRC:'), 		0, 0, 1, 1)
		self.addWidget(self.edt_width, 				0, 1, 1, 3)
		self.addWidget(QtGui.QLabel('@'), 			0, 4, 1, 1)
		self.addWidget(self.spb_bbox_percent, 		0, 5, 1, 1)
		self.addWidget(QtGui.QLabel('+'), 			0, 6, 1, 1)
		self.addWidget(self.spb_bbox_units, 		0, 7, 1, 1)
			
		self.addWidget(self.btn_copyBBox_width,		2, 0, 1, 5)
		self.addWidget(self.btn_copyBBox_height,	2, 5, 1, 4)
		
	def reset_fileds(self):
		# - Reset text fields
		self.edt_width.setText('')
		self.edt_height.setText('')
		
		# - Reset spin-box
		self.spb_bbox_percent.setValue(100)
		self.spb_bbox_units.setValue(0)

	def copy_bbox(self, copy_height=False):
		dst_glyph = eGlyph()

		if len(dst_glyph.selectedNodes()):
			font = pFont()
			src_glyph = font.glyph(self.edt_width.text)
			
			adjPercent = self.spb_bbox_percent.value
			adjUnits = self.spb_bbox_units.value
			
			wLayers = dst_glyph._prepareLayers(pLayers)
			
			for layer in wLayers:
				selection = eNodesContainer(dst_glyph.selectedNodes(layer))
				
				if copy_height:
					dst_glyph_height = dst_glyph.getBounds(layer).height()
					src_glyph_height = src_glyph.getBounds(layer).height()

					dst_glyph_y = dst_glyph.getBounds(layer).y()
					src_glyph_y = src_glyph.getBounds(layer).y()

					process_shift = src_glyph_height*adjPercent/100  - dst_glyph_height + adjUnits
					process_y = src_glyph_y*adjPercent/100 - dst_glyph_y + adjUnits

					selection.shift(0, process_shift)
					
					if process_y != 0:
						selection = eNodesContainer(dst_glyph.nodes(layer))
						selection.shift(0, process_y)

				else:
					dst_glyph_width = dst_glyph.getBounds(layer).width()
					src_glyph_width = src_glyph.getBounds(layer).width()

					process_shift = src_glyph_width*adjPercent/100 - dst_glyph_width + adjUnits
					selection.shift(process_shift, 0)


			dst_glyph.updateObject(dst_glyph.fl, 'Copy BBox | SRC: %s; DST: %s @ %s.' %(src_glyph.name, dst_glyph.name, '; '.join(wLayers)))
			dst_glyph.update()
		
		else:
			warnings.warn('Glyph: %s\tNo nodes selected.' %dst_glyph.name, GlyphWarning)

class metrics_expr(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(metrics_expr, self).__init__()

		self.edt_lsb = TRMLineEdit()
		self.edt_adv = TRMLineEdit()
		self.edt_rsb = TRMLineEdit()

		self.edt_lsb.setPlaceholderText('Metric expression')
		self.edt_adv.setPlaceholderText('Metric expression')
		self.edt_rsb.setPlaceholderText('Metric expression')

		self.btn_setMetrics = QtGui.QPushButton('&Set')
		self.btn_getMetrics = QtGui.QPushButton('&Get')
		self.btn_getShapeParent = QtGui.QPushButton('&Reference')
		self.btn_delMetrics = QtGui.QPushButton('&Unlink')
		self.btn_autoBind = QtGui.QPushButton('&Auto Link')
		
		self.btn_getMetrics.setToolTip('Get Metric expressions for current layer')
		self.btn_setMetrics.setToolTip('Set Metric expressions.\n\n - Click: Set\n - SHIFT + Click: Set LSB with distance between selected two nodes removed from the expression.\n - Alt + Click: Set RSB with distance between selected two nodes removed from the expression.\n - All above + CTRL: - Negate operation (distance added)')
		self.btn_autoBind.setToolTip('Automatically bind metric expressions from available element references.')

		self.btn_getMetrics.clicked.connect(lambda: self.getMetricEquations())
		self.btn_setMetrics.clicked.connect(lambda: self.setMetricEquations(False))
		self.btn_delMetrics.clicked.connect(lambda: self.setMetricEquations(True))
		self.btn_getShapeParent.clicked.connect(self.bindShapeParent)
		self.btn_autoBind.clicked.connect(self.autoMetricEquations)

		self.spb_shapeIndex = QtGui.QSpinBox()

		self.addWidget(QtGui.QLabel('ADV:'), 	0, 0, 1, 1)
		self.addWidget(self.edt_adv, 			0, 1, 1, 5)
		self.addWidget(QtGui.QLabel('LSB:'), 	1, 0, 1, 1)
		self.addWidget(self.edt_lsb, 			1, 1, 1, 5)
		self.addWidget(QtGui.QLabel('RSB:'), 	2, 0, 1, 1)
		self.addWidget(self.edt_rsb, 			2, 1, 1, 5)
		self.addWidget(self.btn_getMetrics, 	3, 0, 1, 2)
		self.addWidget(self.btn_setMetrics, 	3, 2, 1, 4)

		self.addWidget(QtGui.QLabel('Composite Glyph: Metric expressions'), 	4, 0, 1, 5)
		self.addWidget(self.btn_getShapeParent, 5, 0, 1, 2)
		self.addWidget(self.spb_shapeIndex, 	5, 2, 1, 1)
		self.addWidget(self.btn_autoBind, 		5, 3, 1, 1)
		self.addWidget(self.btn_delMetrics, 	5, 4, 1, 1)

		self.setColumnStretch(0, 0)
		self.setColumnStretch(1, 5)

	def reset_fileds(self):
		self.edt_adv.clear()
		self.edt_lsb.clear()
		self.edt_rsb.clear()

	def bindShapeParent(self):
		glyph = eGlyph()
		layer = None 	# Static! Make it smart, so it detects on all layers, dough unnecessary
		shapeIndex = self.spb_shapeIndex.value 	# Static! Make it smart, so it detects...
		namedShapes = [shape for shape in glyph.shapes() + glyph.components() if len(shape.shapeData.name)] 
		
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
			warnings.warn('Glyph: %s\tNo named shape with index: %s' %(glyph.name, shapeIndex), GlyphWarning)

	def getMetricEquations(self):
		glyph = eGlyph()
		lsbEq, rsbEq = glyph.getSBeq()

		self.reset_fileds()
		self.edt_lsb.setText(lsbEq)
		self.edt_rsb.setText(rsbEq)

	def setMetricEquations(self, clear=False):
		process_glyphs = getProcessGlyphs(pMode)
		modifiers = QtGui.QApplication.keyboardModifiers()

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)

			for layer in wLayers:
				if not clear:
					if len(self.edt_lsb.text): 
						eq_set = self.edt_lsb.text
						
						if modifiers == QtCore.Qt.ShiftModifier :
							selection = glyph.selectedNodes(layer, extend=eNode)
							diffX = selection[0].diffTo(selection[-1])[0]
							eq_set += '%s%s' %(['-','+'][modifiers == QtCore.Qt.ControlModifier], abs(diffX))
						
						glyph.setLSBeq(eq_set, layer)
					
					if len(self.edt_rsb.text): 
						eq_set = self.edt_rsb.text
						
						if modifiers == QtCore.Qt.AltModifier :
							selection = glyph.selectedNodes(layer, extend=eNode)
							diffX = selection[0].diffTo(selection[-1])[0]
							eq_set += '%s%s' %(['-','+'][modifiers == QtCore.Qt.ControlModifier], abs(diffX))

						glyph.setRSBeq(eq_set, layer)
					
					if len(self.edt_adv.text): 
						eq_set = self.edt_adv.text
						glyph.setADVeq(eq_set, layer)
				else:
					glyph.setLSBeq('', layer)
					glyph.setRSBeq('', layer)
					glyph.setADVeq('', layer)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Set Metrics Equations @ %s.' %'; '.join(wLayers))
		
		self.reset_fileds()

	def autoMetricEquations(self):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			wLayers = glyph._prepareLayers(pLayers)
			glyph_stat = []

			for layer in wLayers:
				status = glyph.bindCompMetrics(layer)
				glyph_stat.append(status)

			glyph.update()
			glyph.updateObject(glyph.fl, 'Glyph: %s;\tAuto Metrics Equations @ %s.' %(glyph.name, '; '.join('%s: %s' %item for item in zip(wLayers, glyph_stat))))


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
		layoutV.addWidget(QtGui.QLabel('Glyph: Copy BBox data'))
		layoutV.addLayout(bbox_copy())
		layoutV.addSpacing(10)
		layoutV.addWidget(QtGui.QLabel('Glyph: Set metric expressions'))
		layoutV.addLayout(metrics_expr())
		layoutV.addSpacing(10)
		layoutV.addWidget(QtGui.QLabel('\nFont: Set Font Metrics'))
		layoutV.addLayout(metrics_font())

		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(100, 100, 300, 600)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()