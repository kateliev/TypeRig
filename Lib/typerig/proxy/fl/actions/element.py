# MODULE: Typerig / Proxy / FontLab / Actions / Element
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# Element (flShape) management: merge, eject, split, group,
# arrange, align, transform and style copy.
#
# Selection: nodes selected on the active layer pick the contours
# and the elements they sit in. With no nodes selected the elements
# picked with the Element tool (flShape.selected) are used whole.
# The selection is mapped by index (element, contour) onto every
# processed layer, so all processed layers must be compatible.
#
# Contours are only moved between simple elements: groups, glyph
# components and elements shared by reference are refused, because
# editing their data would change other glyphs as well.

# - Dependencies --------------------------------------------
from __future__ import absolute_import, print_function
from collections import OrderedDict

import fontlab as fl6

from typerig.core.base.message import *
from typerig.core.algo import element_ops as eo
from typerig.proxy.fl.objects.font import pFontMetrics
from typerig.proxy.fl.application.app import pWorkspace

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

# - Init ---------------------------------------------------
__version__ = '1.0'
app_name = 'TypeRig | Elements'
active_workspace = pWorkspace()

style_parts_all = ('fill', 'stroke', 'opacity', 'style')

# - Helpers: transforms ------------------------------------
def _qt_to_affine(transform):
	return (transform.m11(), transform.m12(), transform.m21(), transform.m22(), transform.dx(), transform.dy())

def _affine_to_qt(affine):
	return QtGui.QTransform(*affine)

def _shape_affine(shape):
	return _qt_to_affine(shape.transform)

def _set_shape_affine(shape, affine):
	shape.transform = _affine_to_qt(affine)

def _contour_apply(contour, affine):
	contour.transform = _affine_to_qt(affine)
	contour.applyTransform()

def _rect_to_bounds(rect):
	return (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())

def _bounds_to_rect(bounds):
	return QtCore.QRectF(bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1])

def _shape_bounds(shape, parent=eo.IDENTITY):
	'''Bounds of an element in glyph space, groups included.'''
	affine = eo.compose(_shape_affine(shape), parent)

	if len(shape.includesList):
		return eo.union_bounds([_shape_bounds(include, affine) for include in shape.includesList])

	qt_affine = _affine_to_qt(affine)
	return eo.union_bounds([_rect_to_bounds(contour.boundingBox(qt_affine)) for contour in shape.contours])

# - Helpers: selection -------------------------------------
def _contour_selected(contour):
	return any(node.selected for node in contour.nodes())

def _shape_selected_deep(shape):
	return any(_contour_selected(contour) for contour in shape.contours) or any(_shape_selected_deep(include) for include in shape.includesList)

def _get_selection(glyph):
	'''Selection on the active layer as {element index: [contour index, ...]}, back to front.
	Groups picked through a nested node map to an empty contour list.'''
	selection = OrderedDict()
	layer_shapes = glyph.layer().shapes

	for sid, shape in enumerate(layer_shapes):
		if len(shape.includesList):
			if _shape_selected_deep(shape): selection[sid] = []
			continue

		cids = [cid for cid, contour in enumerate(shape.contours) if _contour_selected(contour)]
		if len(cids): selection[sid] = cids

	if not len(selection): # Element tool: whole elements, no nodes
		for sid, shape in enumerate(layer_shapes):
			if shape.selected: selection[sid] = list(range(len(shape.contours)))

	return selection

def _kind(shape):
	'''Why contours of this element can not be edited, or None.'''
	if len(shape.includesList): return 'group'
	if shape.isComponent or shape.shapeData.isComponent: return 'component'
	if shape.shapeData.referenceCount > 1: return 'shared'
	return None

def _refuse(glyph, selection):
	'''Report elements that can not take contour edits. Returns True to skip the glyph.'''
	layer_shapes = glyph.layer().shapes
	issues = ['#{} {}'.format(sid, _kind(layer_shapes[sid])) for sid in selection if _kind(layer_shapes[sid]) is not None]

	if len(issues):
		output(1, app_name, 'Glyph: {}; Skipped, contours of these elements can not be moved: {}. Ungroup, decompose or unlink them first.'.format(glyph.name, ', '.join(issues)))
		return True

	return False

def _layer_shapes(glyph, layer_name, selection):
	layer = glyph.layer(layer_name)
	layer_shapes = layer.shapes

	if len(selection) and max(selection.keys()) >= len(layer_shapes):
		output(1, app_name, 'Glyph: {}; Layer: {}; Element structure differs from the active layer. Skipped.'.format(glyph.name, layer_name))
		return layer, None

	return layer, layer_shapes

def _index_of(layer, shape):
	return [item.id for item in layer.shapes].index(shape.id)

def _finish(glyph, work_layers, message):
	glyph.update()
	glyph.updateObject(glyph.fl, '{};\t{} @ {}.'.format(glyph.name, message, '; '.join(work_layers)))

# - Helpers: elements --------------------------------------
def _style_take(shape, clone=False):
	return {'fill': QtGui.QBrush(shape.brush),
			'stroke': QtGui.QPen(shape.pen),
			'opacity': shape.opacity,
			'style': shape.cloneTopLevel() if clone else shape}

def _style_give(shape, style, parts=style_parts_all):
	keep_transform = shape.transform # assignStyle may carry the transform along, keep ours

	if 'style' in parts: shape.assignStyle(style['style'])
	if 'fill' in parts: shape.brush = QtGui.QBrush(style['fill'])
	if 'stroke' in parts: shape.pen = QtGui.QPen(style['stroke'])
	if 'opacity' in parts: shape.opacity = style['opacity']

	shape.transform = keep_transform

def _new_shape(layer, index, contours, source, affine):
	'''Insert a new element at stack index carrying contours, source's style and given transform.'''
	new_shape = fl6.flShape()
	if len(contours): new_shape.addContours(contours, True)
	new_shape = layer.insertShape(index, new_shape) or new_shape
	_style_give(new_shape, _style_take(source))
	_set_shape_affine(new_shape, affine)
	new_shape.update()
	return new_shape

def _take_contours(shape, cids, move_affine=None):
	'''Clone contours out of shape, optionally remapped, and remove the originals.'''
	originals = [shape.contours[cid] for cid in cids]
	clones = []

	for contour in originals:
		clone = contour.clone()
		if move_affine is not None and not eo.is_identity(move_affine): _contour_apply(clone, move_affine)
		clones.append(clone)

	for contour in originals:
		shape.removeContour(contour)

	return clones

def _drop_if_empty(layer, shape):
	if not len(shape.contours) and not len(shape.includesList):
		layer.removeShape(shape)

def _group(layer, shapes):
	'''Wrap shapes into a group placed where the topmost of them was.'''
	indices = sorted(_index_of(layer, shape) for shape in shapes)
	slot = indices[-1] - (len(indices) - 1)

	container = fl6.flShape()
	container.include(shapes, layer) # Takes the shapes off the layer, the container is added below
	container = layer.insertShape(slot, container) or container
	container.update()
	return container

def _move_affine(source, target):
	'''Remap contours from source element space into target element space. None if target is singular.'''
	target_inverse = eo.invert(_shape_affine(target))
	if target_inverse is None: return None
	return eo.compose(_shape_affine(source), target_inverse)

# - Actions ------------------------------------------------
class TRElementActionCollector(object):
	''' Collection of all element (shape) related tools '''

	# - Merge, eject, split -----------------------------------
	@staticmethod
	def element_merge(pMode:int, pLayers:tuple, target:str='new', whole:bool=False):
		'''Merge selected contours of several elements.
		Args:
			target (str): 'new' - into a new element above the topmost one;
				'top' / 'bottom' - into the topmost / bottommost selected element
			whole (bool): take every contour of each touched element, not only the selected ones
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection) or _refuse(glyph, selection): continue

			sids = list(selection.keys())
			if target != 'new' and len(sids) < 2:
				output(1, app_name, 'Glyph: {}; Select contours in at least two elements.'.format(glyph.name))
				continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				top_shape = layer_shapes[sids[-1]]
				sources = [(layer_shapes[sid], list(range(len(layer_shapes[sid].contours))) if whole else selection[sid]) for sid in sids]

				if target == 'new':
					destination = _new_shape(layer, sids[-1] + 1, [], top_shape, _shape_affine(top_shape))
				else:
					destination = top_shape if target == 'top' else layer_shapes[sids[0]]
					sources = [item for item in sources if item[0].id != destination.id]

				for shape, cids in sources:
					move_affine = _move_affine(shape, destination)

					if move_affine is None:
						output(1, app_name, 'Glyph: {}; Layer: {}; Target element transform is singular. Reset it first.'.format(glyph.name, layer_name))
						break

					destination.addContours(_take_contours(shape, cids, move_affine), True)

				destination.update()

				for shape, cids in sources:
					_drop_if_empty(layer, shape)

			_finish(glyph, work_layers, 'Merge elements: {}'.format(target))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_eject(pMode:int, pLayers:tuple):
		'''Eject selected contours of every element into a new element right above it.
		The new element keeps the style and transform of its source.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection) or _refuse(glyph, selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in reversed(list(selection.keys())): # Top down keeps lower indices valid
					shape = layer_shapes[sid]
					_new_shape(layer, sid + 1, _take_contours(shape, selection[sid]), shape, _shape_affine(shape))
					_drop_if_empty(layer, shape)

			_finish(glyph, work_layers, 'Eject contours')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_split(pMode:int, pLayers:tuple, islands:bool=True):
		'''Split every selected element into one element per island (outer contour plus its counters)
		or per contour. The first part stays in the original element, the rest stack right above it.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection) or _refuse(glyph, selection): continue

			# - Parts are decided on the active layer, so all layers split the same way
			active_shapes = glyph.layer().shapes
			parts = {}

			for sid in selection.keys():
				contours = active_shapes[sid].contours

				if islands:
					polygons = [[(node.x, node.y) for node in contour.nodes()] for contour in contours]
					probes = [next(((node.x, node.y) for node in contour.nodes() if node.isOn()), polygon[0]) for contour, polygon in zip(contours, polygons)]
					parts[sid] = eo.group_islands(polygons, probes)
				else:
					parts[sid] = [[cid] for cid in range(len(contours))]

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in reversed(list(selection.keys())):
					shape = layer_shapes[sid]
					shape_contours = shape.contours
					ejected = [[shape_contours[cid] for cid in part] for part in parts[sid][1:]]

					# - Last part first, each inserted right above the source, ends in original order
					for part in reversed(ejected):
						clones = [contour.clone() for contour in part]
						for contour in part: shape.removeContour(contour)
						_new_shape(layer, sid + 1, clones, shape, _shape_affine(shape))

					shape.update()

			_finish(glyph, work_layers, 'Split elements')

		active_workspace.getCanvas(True).refreshAll()

	# - Groups ----------------------------------------------
	@staticmethod
	def element_group(pMode:int, pLayers:tuple):
		'''Group the selected elements, the group takes the place of the topmost one.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				_group(layer, [layer_shapes[sid] for sid in selection.keys()])

			_finish(glyph, work_layers, 'Group elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_group_contours(pMode:int, pLayers:tuple):
		'''New group from selection: selected contours leave their elements (keeping each source's
		style and transform) and are wrapped together into a new group.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection) or _refuse(glyph, selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				new_shapes = []

				for sid in reversed(list(selection.keys())):
					shape = layer_shapes[sid]
					new_shapes.append(_new_shape(layer, sid + 1, _take_contours(shape, selection[sid]), shape, _shape_affine(shape)))
					_drop_if_empty(layer, shape)

				_group(layer, list(reversed(new_shapes)))

			_finish(glyph, work_layers, 'Group contours')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_ungroup(pMode:int, pLayers:tuple, apply_transform:bool=True):
		'''Ungroup the selected groups, their members take the group's place in the stack.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in reversed(list(selection.keys())):
					group = layer_shapes[sid]
					if not len(group.includesList): continue

					members = group.ejectTo(False, apply_transform)
					layer.removeShape(group)

					for offset, member in enumerate(members):
						layer.insertShape(sid + offset, member)

			_finish(glyph, work_layers, 'Ungroup elements')

		active_workspace.getCanvas(True).refreshAll()

	# - Arrange ---------------------------------------------
	@staticmethod
	def element_reorder(pMode:int, pLayers:tuple, mode:str='up'):
		'''Move selected elements in the stack. Mode: up, down, front, back, reverse.'''
		reorder = {	'up': eo.reorder_up,
					'down': eo.reorder_down,
					'front': eo.reorder_front,
					'back': eo.reorder_back,
					'reverse': eo.reorder_reverse}[mode]

		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				new_order = reorder(len(layer_shapes), selection.keys())
				layer.reorderShapes([layer_shapes[index].id for index in new_order])

			_finish(glyph, work_layers, 'Reorder elements: {}'.format(mode))

		active_workspace.getCanvas(True).refreshAll()

	# - Align and transform ---------------------------------
	@staticmethod
	def element_align(pMode:int, pLayers:tuple, align_mode:str, align_x:str=None, align_y:str=None, reverse:bool=False):
		'''Align selected elements by moving their transforms.
		Args:
			align_mode (str): SEL - selection bounds; KEY - topmost element (bottommost if reverse);
				LAY - advance x descender..ascender; CMC/CMA/CMX - advance x baseline..caps/ascender/x-height;
				CMD - advance x descender..baseline
			align_x (str or None): L, C, R or None to keep
			align_y (str or None): B, E, T or None to keep
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				work_shapes = [layer_shapes[sid] for sid in selection.keys()]

				if align_mode == 'SEL':
					target = eo.union_bounds([_shape_bounds(shape) for shape in work_shapes])

				elif align_mode == 'KEY':
					key_shape = work_shapes.pop(0 if reverse else -1)
					target = _shape_bounds(key_shape)

				else:
					metrics = pFontMetrics(glyph.package)
					advance = glyph.getAdvance(layer_name)
					target = {	'LAY': (0, metrics.getDescender(layer_name), advance, metrics.getAscender(layer_name)),
								'CMC': (0, 0, advance, metrics.getCapsHeight(layer_name)),
								'CMA': (0, 0, advance, metrics.getAscender(layer_name)),
								'CMX': (0, 0, advance, metrics.getXHeight(layer_name)),
								'CMD': (0, metrics.getDescender(layer_name), advance, 0)}[align_mode]

				if target is None: continue

				work_bounds = [_shape_bounds(shape) for shape in work_shapes]

				for shape, bounds, shift in zip(work_shapes, work_bounds, eo.align_shifts(work_bounds, target, align_x, align_y)):
					if bounds is None: continue
					_set_shape_affine(shape, eo.compose(_shape_affine(shape), eo.translate(*shift)))

			_finish(glyph, work_layers, 'Align elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_distribute(pMode:int, pLayers:tuple, vertical:bool=False):
		'''Equal gaps between three or more selected elements, outermost stay put.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if len(selection) < 3: continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				work_shapes = [layer_shapes[sid] for sid in selection.keys()]
				work_bounds = [_shape_bounds(shape) for shape in work_shapes]
				if None in work_bounds: continue

				for shape, shift in zip(work_shapes, eo.distribute_shifts(work_bounds, vertical)):
					_set_shape_affine(shape, eo.compose(_shape_affine(shape), eo.translate(*shift)))

			_finish(glyph, work_layers, 'Distribute elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_transform(pMode:int, pLayers:tuple, affine_for_bounds):
		'''Apply a transform to the selected elements (non-destructive, through the element transform).
		Args:
			affine_for_bounds (callable): bounds of the selection -> affine 6-tuple in glyph space
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				work_shapes = [layer_shapes[sid] for sid in selection.keys()]
				bounds = eo.union_bounds([_shape_bounds(shape) for shape in work_shapes])
				if bounds is None: continue

				affine = affine_for_bounds(bounds)

				for shape in work_shapes:
					_set_shape_affine(shape, eo.compose(_shape_affine(shape), affine))

			_finish(glyph, work_layers, 'Transform elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_flip(pMode:int, pLayers:tuple, vertical:bool=False):
		'''Mirror the selected elements about the center of the selection.'''
		def flip_affine(bounds):
			cx, cy = (bounds[0] + bounds[2])/2., (bounds[1] + bounds[3])/2.
			return eo.scale_about(1, -1, cx, cy) if vertical else eo.scale_about(-1, 1, cx, cy)

		TRElementActionCollector.element_transform(pMode, pLayers, flip_affine)

	@staticmethod
	def element_transform_ctrl(pMode:int, pLayers:tuple, transform_ctrl):
		'''Apply a TRTransformCtrl widget transform to the selected elements.'''
		def ctrl_affine(bounds):
			new_transform, org_transform, rev_transform = transform_ctrl.getTransform(_bounds_to_rect(bounds))
			return eo.compose(eo.compose(_qt_to_affine(org_transform), _qt_to_affine(new_transform)), _qt_to_affine(rev_transform))

		TRElementActionCollector.element_transform(pMode, pLayers, ctrl_affine)

	@staticmethod
	def element_bake_transform(pMode:int, pLayers:tuple):
		'''Apply the element transform onto its contours and reset it.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection) or _refuse(glyph, selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in selection.keys():
					shape = layer_shapes[sid]
					affine = _shape_affine(shape)
					if eo.is_identity(affine): continue

					for contour in shape.contours:
						_contour_apply(contour, affine)

					shape.transform = QtGui.QTransform()
					shape.update()

			_finish(glyph, work_layers, 'Apply element transform')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_reset_transform(pMode:int, pLayers:tuple):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in selection.keys():
					layer_shapes[sid].transform = QtGui.QTransform()

			_finish(glyph, work_layers, 'Reset element transform')

		active_workspace.getCanvas(True).refreshAll()

	# - Style -------------------------------------------------
	@staticmethod
	def element_style_copy(pMode:int, pLayers:tuple):
		'''Copy the style of the topmost selected element per layer. Returns {layer name: style}.'''
		glyph = getProcessGlyphs(0)[0]
		selection = _get_selection(glyph)
		clipboard = {}

		if not len(selection): return clipboard

		for layer_name in glyph._prepareLayers(pLayers):
			layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
			if layer_shapes is None: continue
			clipboard[layer_name] = _style_take(layer_shapes[list(selection.keys())[-1]], clone=True)

		output(0, app_name, 'Glyph: {}; Copied element style @ {}.'.format(glyph.name, '; '.join(clipboard.keys())))
		return clipboard

	@staticmethod
	def element_style_paste(pMode:int, pLayers:tuple, clipboard:dict, parts:tuple=style_parts_all):
		'''Paste a copied style onto the selected elements. A layer missing from the clipboard
		takes the style copied from the first layer.'''
		if not len(clipboard): return
		fallback = list(clipboard.values())[0]
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in selection.keys():
					_style_give(layer_shapes[sid], clipboard.get(layer_name, fallback), parts)

			_finish(glyph, work_layers, 'Paste element style')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_style_match(pMode:int, pLayers:tuple, from_bottom:bool=False, parts:tuple=style_parts_all):
		'''Give all selected elements the style of the topmost (or bottommost) one.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if len(selection) < 2: continue

			work_layers = glyph._prepareLayers(pLayers)
			sids = list(selection.keys())
			key_sid = sids[0] if from_bottom else sids[-1]

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				style = _style_take(layer_shapes[key_sid])

				for sid in sids:
					if sid != key_sid: _style_give(layer_shapes[sid], style, parts)

			_finish(glyph, work_layers, 'Match element style')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_stroke_width(pMode:int, pLayers:tuple, value:float, relative:bool=False):
		'''Set the brush (pen) weight of the selected elements.
		Args:
			value (float): new weight, or the amount to add when relative
			relative (bool): add value to every element's own weight, so masters keep their differences
		'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in selection.keys():
					shape = layer_shapes[sid]
					pen = QtGui.QPen(shape.pen)
					pen.setWidthF(max(0., pen.widthF() + value if relative else value))
					shape.pen = pen

			_finish(glyph, work_layers, 'Brush weight {}{}'.format('+' if relative and value >= 0 else '', value))

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_stroke_width_get():
		'''Brush (pen) weight of the topmost selected element on the active layer, or None.'''
		glyph = getProcessGlyphs(0)[0]
		selection = _get_selection(glyph)
		if not len(selection): return None
		return glyph.layer().shapes[list(selection.keys())[-1]].pen.widthF()

	# - Management -------------------------------------------
	@staticmethod
	def element_duplicate(pMode:int, pLayers:tuple):
		'''Duplicate selected elements as independent copies right above the originals.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in reversed(list(selection.keys())):
					shape = layer_shapes[sid]
					clone = layer.insertShape(sid + 1, shape.cloneTopLevel())
					if clone is not None: clone.transform = shape.transform

			_finish(glyph, work_layers, 'Duplicate elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_unlink(pMode:int, pLayers:tuple):
		'''Replace shared (referenced) elements with independent copies in place.'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for sid in reversed(list(selection.keys())):
					shape = layer_shapes[sid]
					if shape.shapeData.referenceCount < 2: continue

					clone = layer.insertShape(sid, shape.cloneTopLevel())
					if clone is not None: clone.transform = shape.transform
					layer.removeShape(shape)

			_finish(glyph, work_layers, 'Unlink elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_rename(pMode:int, pLayers:tuple, name:str):
		'''Name the selected elements; several get numbered: name.1, name.2 ...'''
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			selection = _get_selection(glyph)
			if not len(selection): continue

			work_layers = glyph._prepareLayers(pLayers)
			sids = list(selection.keys())

			for layer_name in work_layers:
				layer, layer_shapes = _layer_shapes(glyph, layer_name, selection)
				if layer_shapes is None: continue

				for number, sid in enumerate(sids):
					layer_shapes[sid].shapeData.name = name if len(sids) == 1 else '{}.{}'.format(name, number + 1)

			_finish(glyph, work_layers, 'Rename elements')

	@staticmethod
	def element_clean_empty(pMode:int, pLayers:tuple):
		process_glyphs = getProcessGlyphs(pMode)

		for glyph in process_glyphs:
			work_layers = glyph._prepareLayers(pLayers)

			for layer_name in work_layers:
				glyph.layer(layer_name).cleanEmptyShapes()

			_finish(glyph, work_layers, 'Remove empty elements')

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_select_whole():
		'''Grow the node selection to every node of the touched elements (active glyph and layer).'''
		glyph = getProcessGlyphs(0)[0]
		layer_shapes = glyph.layer().shapes

		for sid in _get_selection(glyph).keys():
			for contour in layer_shapes[sid].contours:
				for node in contour.nodes():
					node.selected = True

		active_workspace.getCanvas(True).refreshAll()

	@staticmethod
	def element_report():
		'''Print the element stack of the active layer, front to back.'''
		glyph = getProcessGlyphs(0)[0]
		layer_shapes = glyph.layer().shapes
		selection = _get_selection(glyph)

		print('\n{}: {} @ {}; {} elements, front to back:'.format(app_name, glyph.name, glyph.layer().name, len(layer_shapes)))

		for sid in reversed(range(len(layer_shapes))):
			shape = layer_shapes[sid]
			kind = _kind(shape) or 'simple'
			members = len(shape.includesList)
			affine = _shape_affine(shape)
			print('{} #{:<3} {:<24} {:<9} contours: {:<3} {}refs: {:<2} fill: {} {}'.format(
					'*' if sid in selection else ' ',
					sid,
					shape.shapeData.name or '<unnamed>',
					kind,
					len(shape.contours),
					'members: {} '.format(members) if members else '',
					shape.shapeData.referenceCount,
					shape.brush.color().name(),
					'' if eo.is_identity(affine) else 'transform: ({})'.format(', '.join('{:.2f}'.format(v) for v in affine))))
