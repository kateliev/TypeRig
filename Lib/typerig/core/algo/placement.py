# MODULE: TypeRig / Core / Algo / Placement
# -----------------------------------------------------------
# General "fit a part into a target bounds" transforms for core
# Layer objects — the non-delta half of the Advanced Clipboard's
# paste pipeline, lifted so it is reusable outside CJK work.
#
# All functions mutate the given tr_layer in place (font units)
# and are pure TypeRig core: no FontLab, no Qt. They operate on
# the layer's own bounds centre, so they compose cleanly with the
# stem-preserving DeltaScale path (core/objects/delta.py,
# layer.scale_with_axis) — pick one fit method, then align.
#
#   flip_layer(layer, flip_h, flip_v)          mirror on axes
#   scale_fit_layer(layer, bounds, ...)         unconstrained affine fit
#   fit_inside_layer(layer, bounds, ...)        uniform (aspect) fit within
#   align_layer_to_bounds(layer, bounds, origin) snap origin onto bounds
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.objects.transform import TransformOrigin

__version__ = '1.0.0'


def flip_layer(tr_layer, flip_h=False, flip_v=False):
	'''Mirror layer around its own bounds centre on the requested axes.'''
	if not (flip_h or flip_v):
		return
	src = tr_layer.bounds
	cx = (src.x + src.xmax) / 2.0
	cy = (src.y + src.ymax) / 2.0
	sx = -1.0 if flip_h else 1.0
	sy = -1.0 if flip_v else 1.0
	for node in tr_layer.nodes:
		node.x = (node.x - cx) * sx + cx
		node.y = (node.y - cy) * sy + cy


def scale_fit_layer(tr_layer, target_bounds, flip_h=False, flip_v=False):
	'''Unconstrained affine scale of layer to fit target_bounds, around its own
	bounds centre. Optional mirror via flip_h/flip_v (sign of scale factors).
	Distorts aspect to fill both axes — use fit_inside_layer to preserve it.'''
	src = tr_layer.bounds
	if src.width == 0 or src.height == 0:
		return
	sx = target_bounds.width / float(src.width)
	sy = target_bounds.height / float(src.height)
	if flip_h: sx = -sx
	if flip_v: sy = -sy
	cx = (src.x + src.xmax) / 2.0
	cy = (src.y + src.ymax) / 2.0
	for node in tr_layer.nodes:
		node.x = (node.x - cx) * sx + cx
		node.y = (node.y - cy) * sy + cy


def fit_inside_layer(tr_layer, target_bounds, flip_h=False, flip_v=False):
	'''Uniform (aspect-preserving) scale of layer to fit *within* target_bounds,
	around its own bounds centre. Unlike scale_fit_layer this keeps the part's
	proportions (fills only the tighter axis), so a following align step then
	positions it inside the slot (top/center/bottom …) without distortion.'''
	src = tr_layer.bounds
	if src.width == 0 or src.height == 0:
		return
	s = min(target_bounds.width / float(src.width), target_bounds.height / float(src.height))
	sx = -s if flip_h else s
	sy = -s if flip_v else s
	cx = (src.x + src.xmax) / 2.0
	cy = (src.y + src.ymax) / 2.0
	for node in tr_layer.nodes:
		node.x = (node.x - cx) * sx + cx
		node.y = (node.y - cy) * sy + cy


def align_layer_to_bounds(tr_layer, target_bounds, align_origin=TransformOrigin.CENTER):
	'''Align the layer's align_origin point onto target_bounds' same point.

	align_origin : a TransformOrigin; its .code keys into Bounds.align_matrix
	(TOP_LEFT -> 'TL', CENTER -> 'C', BOTTOM_RIGHT -> 'BR', …). Falls back to the
	rect centre when the code is not in the matrix.'''
	code = align_origin.code
	target_xy = target_bounds.align_matrix.get(code)
	if target_xy is None:
		target_xy = (target_bounds.x + target_bounds.width / 2.0,
					 target_bounds.y + target_bounds.height / 2.0)
	tr_layer.align_to(target_xy, mode=(align_origin, align_origin), align=(True, True))
