# -*- coding: utf-8 -*-
# MODULE: Typerig / GUI / IconDraw
# NOTE	: Assorted Gui Elements
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
import fontlab as fl6
from PythonQt import QtCore, QtGui

# - Init ----------------------------------
__version__ = '0.1.0'

# - Constants ---------------------------
BASE_PADDING = 16
SELECTION_LINE_WIDTH = 8.0
NODE_SIZE_RATIO = 0.08
MIN_NODE_SIZE = 2

# - Main Function -----------------------
def TRDrawIcon(contours, selection=None, foreground='black', background='gray'):
	'''
	Draw icon for gallery showing contours and optionally selected nodes.
	
	Args:
		contours (list): List of fl6.flContour objects to draw
		selection (list, optional): List of selected nodes. If None or empty, 
								   draws full contours only
		foreground (str): Color name for selection lines and node markers
		background (str): Color name for full contour background in selection mode
	
	Returns:
		QtGui.QIcon: Icon with the rendered shape
	
	'''
	# - Prepare shape
	shape = prepare_shape(contours)
	bbox = shape.boundingBox
	dimension = max(bbox.width(), bbox.height())
	
	# - Calculate padding based on what we're drawing
	has_selection = bool(selection)
	
	if has_selection:
		# Account for stroke width and node markers
		node_size = max(MIN_NODE_SIZE, dimension * NODE_SIZE_RATIO)
		extra_padding = max(SELECTION_LINE_WIDTH, node_size)
	else:
		extra_padding = 4  # Minimal padding for contour mode
	
	total_padding = BASE_PADDING + extra_padding
	
	# - Create canvas
	canvas_size = dimension + (total_padding * 2)
	pixmap = QtGui.QPixmap(canvas_size, canvas_size)
	pixmap.fill(QtGui.QColor('white'))
	
	# - Setup painter
	painter = QtGui.QPainter(pixmap)
	painter.setRenderHint(QtGui.QPainter.Antialiasing)
	
	# - Transform shape to canvas coordinates (centered with padding)
	transform_shape_to_canvas(shape, bbox, total_padding)
	
	# - Draw based on mode
	if has_selection:
		draw_selection_mode(painter, shape, selection, bbox, 
						   foreground, background, dimension, total_padding)
	else:
		draw_contour_mode(painter, shape, foreground)
	
	painter.end()
	
	# - Create icon (flip vertically for correct orientation)
	icon = QtGui.QIcon()
	icon.addPixmap(pixmap.transformed(QtGui.QTransform().scale(1, -1)))
	
	return icon


# - Helper Functions --------------------
def prepare_shape(contours):
	'''
	Clone contours and create a new shape.
	
	Args:
		contours (list): List of fl6.flContour objects
	
	Returns:
		fl6.flShape: Shape containing cloned contours
	'''
	shape = fl6.flShape()
	for contour in contours:
		shape.addContour(contour.clone(), True)
	return shape


def transform_shape_to_canvas(shape, bbox, padding):
	'''
	Center shape on canvas by removing bbox offset and adding padding.
	
	Args:
		shape (fl6.flShape): Shape to transform
		bbox (fl6.flBoundingBox): Bounding box of the shape
		padding (float): Padding amount in pixels
	'''
	transform = shape.transform.translate(-bbox.x() + padding, -bbox.y() + padding)
	shape.applyTransform(transform)
	shape.ensurePaths()


def draw_contour_mode(painter, shape, color):
	'''
	Draw full closed contours in solid color.
	
	Args:
		painter (QtGui.QPainter): QPainter instance
		shape (fl6.flShape): Shape to draw
		color (str): Color name for the fill
	'''
	painter.setBrush(QtGui.QBrush(QtGui.QColor(color)))
	painter.setPen(QtCore.Qt.NoPen)
	painter.drawPath(shape.closedPath)


def draw_selection_mode(painter, shape, selection, bbox, foreground, background, dimension, padding):
	'''
	Draw selection mode with:
	1. Full contour as gray background
	2. Selected nodes path as colored line
	3. Node markers as circles
	
	Args:
		painter (QtGui.QPainter): QPainter instance
		shape (fl6.flShape): Shape to draw
		selection (list): List of selected nodes
		bbox (fl6.flBoundingBox): Bounding box of the shape
		foreground (str): Color for selection lines and markers
		background (str): Color for background contour
		dimension (float): Maximum dimension of the shape
		padding (float): Padding amount in pixels
	'''
	# - Draw background (full contour in gray)
	painter.setBrush(QtGui.QBrush(QtGui.QColor(background)))
	painter.setPen(QtCore.Qt.NoPen)
	painter.drawPath(shape.closedPath)
	
	# - Build selection contour (nodes only)
	selection_contour = build_selection_contour(selection, bbox, padding)
	
	# - Draw selection path (connecting line)
	selection_pen = create_selection_pen(foreground)
	painter.setPen(selection_pen)
	painter.setBrush(QtGui.QColor(0, 0, 0, 0))  # Transparent brush
	painter.drawPath(selection_contour.path())
	
	# - Draw node markers (circles)
	draw_node_markers(painter, selection, bbox, dimension, foreground, padding)


def build_selection_contour(selection, bbox, padding):
	'''
	Create contour from selected nodes, adjusted for canvas coordinates.
	
	Args:
		selection (list): List of selected nodes
		bbox (fl6.flBoundingBox): Bounding box of the shape
		padding (float): Padding amount in pixels
	
	Returns:
		fl6.flContour: Contour containing adjusted nodes
	'''
	selection_contour = fl6.flContour()
	for node in selection:
		adjusted_node = node.clone()
		adjusted_node.moveBy(-bbox.x() + padding, -bbox.y() + padding)
		selection_contour.add(adjusted_node)
	return selection_contour


def create_selection_pen(color):
	'''
	Create pen for drawing selection path.
	
	Args:
		color (str): Color name for the pen
	
	Returns:
		QtGui.QPen: Configured pen for selection drawing
	'''
	pen = QtGui.QPen(QtGui.QColor(color))
	pen.setWidthF(SELECTION_LINE_WIDTH)
	pen.setStyle(QtCore.Qt.SolidLine)
	pen.setCapStyle(QtCore.Qt.RoundCap)
	pen.setJoinStyle(QtCore.Qt.RoundJoin)
	return pen


def draw_node_markers(painter, selection, bbox, dimension, color, padding):
	'''
	Draw circular markers at each selected node.
	
	Args:
		painter (QtGui.QPainter): QPainter instance
		selection (list): List of selected nodes
		bbox (fl6.flBoundingBox): Bounding box of the shape
		dimension (float): Maximum dimension of the shape
		color (str): Color name for the markers
		padding (float): Padding amount in pixels
	'''
	node_size = max(MIN_NODE_SIZE, dimension * NODE_SIZE_RATIO)
	half_size = node_size / 2.0
	
	painter.setBrush(QtGui.QBrush(QtGui.QColor(color)))
	painter.setPen(QtGui.QPen(QtGui.QColor(color)))
	
	for node in selection:
		x = node.x - bbox.x() + padding - half_size
		y = node.y - bbox.y() + padding - half_size
		painter.drawEllipse(QtCore.QRectF(x, y, node_size, node_size))