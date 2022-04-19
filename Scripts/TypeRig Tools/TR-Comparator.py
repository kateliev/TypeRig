#FLM: TypeRig: Comparator
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2022 		(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.font import pFont

from typerig.core.base.message import *
from typerig.core.objects.array import PointArray

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRLayerSelectDLG, fontMarkColors

# - Init ---------------------------
app_name, app_version = 'TR | Comparator', '0.8'

# - Configuration ----------------------
# -- Colors
color_background = QtGui.QColor('white')
color_foreground_A = QtGui.QColor('Blue')
color_foreground_B = QtGui.QColor('Red')
color_foreground_A.setAlpha(100) 
color_foreground_B.setAlpha(100) 

draw_padding = 0
draw_scale = 1.

# -- Strings and messages configuration
empty_record = {'Report':{'Glyph':['Layer']}}
column_delimiter = ' | '
glyph_suffix_separator = '.'
fileFormats = 'Audit Record (*.txt);;'

# - Helpers ----------------------------
def depth_test(tree_item):
	# Return the nesting depth of a QTreeWidgetItem
	depth_test = tree_item
	depth = 0

	while(depth_test is not None):
		depth += 1
		depth_test = depth_test.parent()

	return depth

def draw_diff(glyph_A, glyph_B, layer_name_A, layer_name_B):
	# - Init
	shape_A = fl6.flShape()
	shape_B = fl6.flShape()
	cloned_contours_A = [contour.clone() for contour in glyph_A.layer(layer_name_A).getContours()]
	cloned_contours_B = [contour.clone() for contour in glyph_B.layer(layer_name_B).getContours()]

	for cid in range(len(cloned_contours_A)):
		shape_A.addContour(cloned_contours_A[cid], True)

	for cid in range(len(cloned_contours_B)):
		shape_B.addContour(cloned_contours_B[cid], True)

	# - Prepare
	main_painter = QtGui.QPainter()
	draw_bbox_A = glyph_A.layer(layer_name_A).boundingBox #shape_A.boundingBox
	draw_bbox_B = glyph_B.layer(layer_name_B).boundingBox #shape_A.boundingBox
	draw_dimension_x = max(glyph_A.layer(layer_name_A).advanceWidth, glyph_B.layer(layer_name_B).advanceWidth)
	#draw_dimension_y = max(glyph_A.layer(layer_name_A).advanceHeight, glyph_B.layer(layer_name_B).advanceHeight)
	draw_dimension_y = max(draw_bbox_A.height(), draw_bbox_B.height())
	
	draw_dimension_x += 2*draw_padding
	draw_dimension_y += 2*draw_padding

	cont_painter= QtGui.QPainter()
	cont_pixmap = QtGui.QPixmap(draw_dimension_x, draw_dimension_y)
	
	# - Draw Background
	cont_painter.begin(cont_pixmap)
	cont_painter.setBrush(QtGui.QBrush(color_background))
	cont_painter.drawRect(QtCore.QRectF(0, 0, draw_dimension_x, draw_dimension_y))

	# - Draw Shapes
	# -- A
	cont_painter.setBrush(QtGui.QBrush(color_foreground_A))
	cont_painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
	new_transform = shape_A.transform.translate(draw_padding, draw_padding)
	shape_A.applyTransform(new_transform)
	shape_A.ensurePaths()
	cont_painter.drawPath(shape_A.closedPath)

	# -- B
	cont_painter.setBrush(QtGui.QBrush(color_foreground_B))
	cont_painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
	new_transform = shape_B.transform.translate(draw_padding, draw_padding)
	shape_B.applyTransform(new_transform)
	shape_B.ensurePaths()
	cont_painter.drawPath(shape_B.closedPath)

	return cont_pixmap.transformed(QtGui.QTransform().scale(1, -1))

# - Classes ----------------------------
class fontComparator(object):
	def __init__(self, font_A, font_B, report_hook, progress_hook):
		self.report = report_hook
		self.process_bank = {}
		self.progress = progress_hook
		self.font_A = font_A
		self.font_B = font_B
		self.font_A_filename = os.path.split(self.font_A.path)[1]
		self.font_B_filename = os.path.split(self.font_B.path)[1]

	# - Helpers -----------------------
	def __write_record(self, name, record):
		self.report.setdefault(name, {}).update(record)

	def __write_process(self, operation, record):
		self.process_bank.setdefault(operation, {}).update(record)

	def __iter_glyphs(self, process_glyphs, process_function, process_layers):
		# - Set progress bar
		all_glyph_counter = 0
		self.progress.setValue(all_glyph_counter)
		glyph_count = len(process_glyphs)
		
		# - Process glyphs
		for idx, glyph in enumerate(process_glyphs):
			work_glyph = eGlyph(glyph, self.font_A.fg)
			process_function(work_glyph, process_layers)
		
			# - Set progress
			current_progress = idx*100/glyph_count
			self.progress.setValue(current_progress)
			QtGui.QApplication.processEvents()

	# -- Functions --------------------------
	def __make_font_diff(self, glyph, process_layers, time_diff=False):	
		# - Init
		if not self.font_B.hasGlyph(glyph.name): return
		
		layers_different = []
		layers_missing = []
		layers_similar = []
		
		# - Get Other glyph
		other = self.font_B.glyph(glyph.name, extend=eGlyph)
		# - Get time of last modification
		datetime_modified = other.fl.lastModified

		# - Compare glyphs
		for layer_name in process_layers:
			# - Check if layer exists
			glyph_layer = glyph.layer(layer_name)
			other_layer = other.layer(layer_name)

			if glyph_layer is None or other_layer is None: 
				layers_missing.append(layer_name)
				continue

			# - Skip autolayers
			if glyph_layer.autoLayer or other_layer.autoLayer:
				continue

			# - Compare layers (by node coordinates)
			glyph_array = PointArray(glyph._getPointArray(layer_name))
			other_array = PointArray(other._getPointArray(layer_name))

			if glyph_array.tuple != other_array.tuple: 
				# - Normalize layers to the origin
				norm_glyph_array = glyph_array - (glyph_array.x, glyph_array.y)
				norm_other_array = other_array - (other_array.x, other_array.y)

				if norm_glyph_array.tuple == norm_other_array.tuple: 
					# - Layers are same just shifted
					if time_diff and glyph.fl.lastModified < other.fl.lastModified: continue
					
					# - Source is newer
					layers_similar.append(layer_name)
				else:
					# - Layers are different
					if time_diff and glyph.fl.lastModified < other.fl.lastModified: continue
					
					# - Source is newer
					layers_different.append(layer_name)

		return layers_different, layers_missing, layers_similar, datetime_modified
	
	def __make_layer_diff(self, glyph, process_layers):	
		# - Init
		layers_different = []
		layers_similar = []
		
		# - Compare layers
		first_layer = glyph.layer(process_layers[0])
		second_layer = glyph.layer(process_layers[1])

		# - Skip autolayers
		if not first_layer.autoLayer or not second_layer.autoLayer:
			# - Compare layers (by node coordinates)
			first_array = PointArray(glyph._getPointArray(process_layers[0]))
			second_array = PointArray(glyph._getPointArray(process_layers[1]))

			if first_array.tuple != second_array.tuple: 
				# - Normalize layers to the origin
				norm_first_array = first_array - (first_array.x, first_array.y)
				norm_second_array = second_array - (second_array.x, second_array.y)

				if norm_first_array.tuple == norm_second_array.tuple: 
					layers_similar.append('; '.join(process_layers))
				else:
					layers_different.append('; '.join(process_layers))

		return layers_different, layers_similar

	# -- Procedures follow ------------------
	# --- Fonts Diff: Compare glyphs between two fonts
	def compare_fonts(self, process_layers=[]):
		# - Helper
		def make_font_diff(glyph, process_layers):
			layers_different_msg = ('Layer >> Outlines', 'Source and Destination layers are different' )
			layers_similar_msg = ('Layer >> Metrics ', 'Source and Destination have identical outlines but different metrics')
			glyph_missing_msg = ('Glyph >> Missing ', 'Source glyph not found in destination')
			layers_missing_msg = ('Layer >> Missing ', 'Layer(s) missing in Source or destination')
		
			diff_report = self.__make_font_diff(glyph, process_layers)
			
			if diff_report is not None:
				layers_different, layers_missing, layers_similar, datetime_modified = diff_report
				datetime_modified = datetime_modified.toString('dd.MM.yyyy - hh:mm')

				# - Report
				if len(layers_different):
					self.__write_record(layers_different_msg, {(glyph.name, datetime_modified): layers_different})
					self.__write_process(layers_different_msg[0], {glyph.name: layers_different})

				if len(layers_missing):
					self.__write_record(layers_missing_msg, {(glyph.name, datetime_modified): layers_missing})
					self.__write_process(layers_missing_msg[0], {glyph.name: layers_missing})

				if len(layers_similar):
					self.__write_record(layers_similar_msg, {(glyph.name, datetime_modified): layers_similar})
					self.__write_process(layers_similar_msg[0], {glyph.name: layers_similar})
			else:
				# - Report missing glyph
				self.__write_record(glyph_missing_msg, {glyph.name: [self.font_B_filename]})
				self.__write_process(glyph_missing_msg[0], {glyph.name : None})
	
		# - Init
		source_glyphs = self.font_A.glyphs()

		# - Process
		self.__iter_glyphs(source_glyphs, make_font_diff, process_layers)

	# --- Layers Diff: Compare layers within single font
	def compare_layers(self, process_layers=[]):
		# - Helper
		def make_layer_diff(glyph, process_layers):
			layers_different_msg = ('Layer >> Outlines', 'Source and Destination layers are different' )
			layers_similar_msg = ('Layer >> Outlines ', 'Source and Destination have identical outlines but shifted')
		
			diff_report = self.__make_layer_diff(glyph, process_layers)
			
			if diff_report is not None:
				layers_different, layers_similar = diff_report

				# - Report
				if len(layers_different):
					self.__write_record(layers_different_msg, {(glyph.name, ''): layers_different})
					self.__write_process(layers_different_msg[0], {glyph.name: layers_different})

				if len(layers_similar):
					self.__write_record(layers_similar_msg, {(glyph.name, ''): layers_similar})
					self.__write_process(layers_similar_msg[0], {glyph.name: layers_similar})

		# - Init
		if len(process_layers) > 1:
			source_glyphs = self.font_A.glyphs()

			# - Process
			self.__iter_glyphs(source_glyphs, make_layer_diff, process_layers)
		else:
			output(1, app_name, 'Please select more than one layer! Current selection: %s.' %(process_layers))

# - Sub widgets ------------------------
class TRWDiffTree(QtGui.QTreeWidget):
	def __init__(self, data=None, headers=None):
		super(TRWDiffTree, self).__init__()
		
		if data is not None: self.setTree(data, headers)
		self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.setAlternatingRowColors(True)

	def setTree(self, data, headers):
		self.blockSignals(True)
		self.clear()
		self.setHeaderLabels(headers)

		# - Insert 
		for head, summary in data.items():
			parent = QtGui.QTreeWidgetItem(self, head)

			for glyph, data in summary.items():
				glyph_report = QtGui.QTreeWidgetItem(parent, glyph)
				
				for item in data:
					sub_report = QtGui.QTreeWidgetItem(glyph_report, [item])
					
		# - Fit data
		for c in range(self.columnCount):
			self.resizeColumnToContents(c)
		
		self.blockSignals(False)

	def getTree(self):
		returnDict ={}
		root = self.invisibleRootItem()

		for i in range(root.childCount()):
			item = root.child(i)

			returnDict[item.text(0)] = [[item.child(n).text(c) for c in range(item.child(n).columnCount())] for n in range(item.childCount())]
		
		return returnDict

class TRComparator(QtGui.QDialog):
	def __init__(self):
		super(TRComparator, self).__init__()

		# - Init
		self.pMode = 3
		self.pLayers = (True, False, False, False)
		self.all_fonts = fl6.AllFonts()
		self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]
		action_list = [func.replace('_', ' ').title() for func in dir(fontComparator) if callable(getattr(fontComparator, func)) if '__' not in func]
		self.font_src, self.font_dst = None, None
		
		# -- Boxes
		self.box_fonts = QtGui.QGroupBox('Fonts:')
		self.box_layers = QtGui.QGroupBox('Layers:')
		self.box_action = QtGui.QGroupBox('Actions:')
		self.box_audit = QtGui.QGroupBox('Summary:')
		self.box_preview = QtGui.QGroupBox('Preview:')

		# -- Progress bar
		self.progress = QtGui.QProgressBar()
		self.progress.setMaximum(100)

		# -- Report Tree
		self.audit_report = empty_record
		self.header_names = ['Glyph', 'Summary']
		self.audit_tree = TRWDiffTree(self.audit_report, self.header_names)
		self.audit_tree.selectionModel().selectionChanged.connect(self.auto_preview)
		
		# --- Combos
		self.cmb_select_font_A = QtGui.QComboBox()
		self.cmb_select_font_A.addItems(self.font_files)
		
		self.cmb_select_font_B = QtGui.QComboBox()
		self.cmb_select_font_B.addItems(self.font_files)
		
		self.cmb_select_action = QtGui.QComboBox()
		self.cmb_select_action.addItems(action_list)
		
		self.cmb_select_color = QtGui.QComboBox()
		self.color_codes = {name:value for name, value, discard in fontMarkColors}
		for i in range(len(fontMarkColors)):
			self.cmb_select_color.addItem(fontMarkColors[i][0])
			self.cmb_select_color.setItemData(i, QtGui.QColor(fontMarkColors[i][2]), QtCore.Qt.DecorationRole)

		# --- Dialogs
		self.layer_dialog = TRLayerSelectDLG(self, self.pMode, font=pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)]))
		self.layer_dialog.tab_masters.verticalHeader().setVisible(False)
		self.layer_dialog.setMinimumHeight(400)
		self.cmb_select_font_A.currentIndexChanged.connect(lambda: self.layer_dialog.table_populate(self.pMode, font=pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)])))

		# -- Action Buttons
		# --- Operations
		self.brn_process_actions = QtGui.QPushButton('Run')
		self.brn_process_actions.clicked.connect(self.font_process)

		# --- Audit
		self.btn_audit_reset = QtGui.QPushButton('Clear Record')
		self.btn_audit_select = QtGui.QPushButton('Select Glyphs')
		self.btn_audit_save = QtGui.QPushButton('Save Record')
		self.btn_audit_select.setCheckable(True)
		self.btn_audit_select.setChecked(False)
		self.btn_audit_reset.clicked.connect(self.reset)
		self.btn_audit_save.clicked.connect(self.save_audit)

		# --- Graphics scene and view
		self.gsn_diff_scene = QtGui.QGraphicsScene(self)
		self.gsv_diff_preview = QtGui.QGraphicsView(self.gsn_diff_scene)
		
		# - Build Layout
		# -- Left plane
		lay_main = QtGui.QVBoxLayout()
		lay_fonts = QtGui.QVBoxLayout()
		lay_fonts.addWidget(QtGui.QLabel('First:'))
		lay_fonts.addWidget(self.cmb_select_font_A)
		lay_fonts.addWidget(QtGui.QLabel('Second:'))
		lay_fonts.addWidget(self.cmb_select_font_B)
		self.box_fonts.setLayout(lay_fonts)

		lay_layers = QtGui.QVBoxLayout()
		lay_layers.addWidget(self.layer_dialog)
		lay_layers.setMargin(0)
		self.box_layers.setLayout(lay_layers)

		lay_actions = QtGui.QVBoxLayout()
		#lay_actions.addWidget(QtGui.QLabel('Process:'))
		lay_actions.addWidget(self.cmb_select_action)
		#lay_actions.addWidget(QtGui.QLabel('Mark processed glyphs with:'))
		#lay_actions.addWidget(self.cmb_select_color)
		lay_actions.addWidget(self.brn_process_actions)
		self.box_action.setLayout(lay_actions)

		lay_left = QtGui.QVBoxLayout()
		lay_left.addWidget(self.box_fonts)
		lay_left.addWidget(self.box_layers)
		lay_left.addWidget(self.box_action)

		# -- Middle plane
		lay_audit = QtGui.QGridLayout()
		lay_audit.addWidget(self.btn_audit_select, 				0,  6,  1, 2)
		lay_audit.addWidget(self.btn_audit_save, 				0,  8,  1, 2)
		lay_audit.addWidget(self.btn_audit_reset, 				0,  10, 1, 2)
		lay_audit.addWidget(self.audit_tree, 					1,  6, 20, 6)
		self.box_audit.setLayout(lay_audit)

		lay_mid = QtGui.QVBoxLayout()
		lay_mid.addWidget(self.box_audit)

		# -- Right plane
		lay_preview = QtGui.QVBoxLayout()
		lay_preview.addWidget(self.gsv_diff_preview)
		self.box_preview.setLayout(lay_preview)

		lay_right = QtGui.QVBoxLayout()
		lay_right.addWidget(self.box_preview)

		# -- Compose all
		lay_split = QtGui.QHBoxLayout()
		lay_split.addLayout(lay_left, 1)
		lay_split.addLayout(lay_mid, 3)
		lay_split.addLayout(lay_right, 2)

		lay_main.addLayout(lay_split)
		lay_main.addWidget(self.progress)
		self.setLayout(lay_main)

		# - Finish
		self.setMinimumSize(400, self.sizeHint.height())
		self.reset()

	# -- Procedures --------------------------
	def layers_refresh(self):
		self.pLayers = self.layer_dialog.tab_masters.getTable()

	def reset(self):
		self.audit_tree.clear()
		self.audit_report = {}
		self.active_font = pFont()
		self.audit_report = empty_record
		self.audit_tree.setTree(self.audit_report, self.header_names)

	def auto_preview(self):
		# - Preview glyphs using Preview panel
		if self.btn_audit_select.isChecked():
			self.active_font.unselectAll()
			selection = [item.text(0) for item in self.audit_tree.selectedItems()]
			self.active_font.selectGlyphs(selection)

		# - Drawing
		if self.font_src is not None and self.font_dst is not None:
			current_selection = self.audit_tree.selectedItems()[0]
			current_selection_parent = self.audit_tree.selectedItems()[0].parent()
			depth = depth_test(current_selection)

			if depth == 3: # Layer is selected
				self.gsn_diff_scene.clear()
				
				if self.font_src.fl != self.font_dst.fl:
					glyph_a = self.font_src.glyph(current_selection_parent.text(0))
					glyph_b = self.font_dst.glyph(current_selection_parent.text(0))

					diff_pixmap = draw_diff(glyph_a, glyph_b, current_selection.text(0), current_selection.text(0))
				else:
					glyph_a = self.font_src.glyph(current_selection_parent.text(0))
					layer_a, layer_b = current_selection.text(0).split('; ')
					diff_pixmap = draw_diff(glyph_a, glyph_a, layer_a, layer_b)

				add_pixmap = self.gsn_diff_scene.addPixmap(diff_pixmap)
				add_pixmap.setTransformationMode(QtCore.Qt.SmoothTransformation)
				self.gsv_diff_preview.fitInView(add_pixmap, QtCore.Qt.KeepAspectRatio)
			

	def save_audit(self):
		export_report = self.audit_tree.getTree()
		fontPath = os.path.split(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)].path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Audit Record', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				for key, value in export_report.items():
					export_glyph_names = '/'.join([item[0] for item in value]) 

					write_string = '\n{border}\n# {title}\n{border}\n'.format(border='#'*10, title=key + '/(%s)' %len(value))
					write_string += '\n# {title} >> Affected glyphs string:\n/'.format(title=key)
					write_string += export_glyph_names

					exportFile.writelines(write_string)

				output(7, app_name, 'Report saved to: %s.' %(fname))

	def font_process(self):
		# - Init
		self.pLayers = self.layer_dialog.tab_masters.getTable()
		self.font_src = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_A.currentText)])
		self.font_dst = pFont(self.all_fonts[self.font_files.index(self.cmb_select_font_B.currentText)])
		
		process_type = self.cmb_select_action.currentText.replace(' ','_').lower()
		self.audit_report = {}
		
		# - Run Tests
		compare_fonts = fontComparator(self.font_src, self.font_dst, self.audit_report, self.progress)
		getattr(compare_fonts, process_type)(self.pLayers)
		
		# - Set report plane
		if len(self.audit_report.keys()):
			
			self.audit_tree.setTree(self.audit_report, self.header_names)
			self.audit_tree.collapseAll()
		
		output(0, app_name, 'Destination Font: %s; Processing Finished!' %os.path.split(self.font_dst.path)[1])
		self.progress.setValue(0)

# - Run ----------------------
Preflight = TRComparator()
Preflight.setWindowTitle('%s %s' %(app_name, app_version))
Preflight.setGeometry(100, 100, 1600, 600)
Preflight.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
Preflight.show()
