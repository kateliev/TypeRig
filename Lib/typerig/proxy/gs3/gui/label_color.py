# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — label colour picker
#
# A pop-up of Glyphs' label colours only (glyph.color / layer.color index
# 0..11): a round swatch and the colour's name per item, no colour panel.
# The value is the index, so whatever is picked is a colour Glyphs knows
# (Font view colour filter, smart filters).
#
#     TRLabelColorPopUp((x, y, w, h), value=4, callback=..., sizeStyle='small')
#     .get() -> index, .set(index)
#
# Colours: core delta_machine_actions.LABEL_COLORS (names + approximate RGB
# for the swatches; Glyphs draws its own shades in the Font view).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import AppKit
import vanilla

from typerig.core.actions.delta_machine_actions import LABEL_COLORS

SWATCH = 12		# swatch diameter, px


def label_swatch(index, size=SWATCH):
	'''Round NSImage of label colour index (template off: drawn in colour).'''
	r, g, b = LABEL_COLORS[index][1]
	color = AppKit.NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, 1.)
	edge = AppKit.NSColor.colorWithDeviceWhite_alpha_(0., .25)
	image = AppKit.NSImage.alloc().initWithSize_((size, size))
	image.lockFocus()
	dot = AppKit.NSBezierPath.bezierPathWithOvalInRect_(((.5, .5), (size - 1, size - 1)))
	color.set()
	dot.fill()
	edge.set()
	dot.setLineWidth_(1.)
	dot.stroke()
	image.unlockFocus()
	return image


class TRLabelColorPopUp(vanilla.PopUpButton):
	'''vanilla.PopUpButton of the Glyphs label colours; value = index.'''
	def __init__(self, posSize, value=0, callback=None, sizeStyle='small'):
		super(TRLabelColorPopUp, self).__init__(posSize, [name for name, _rgb in LABEL_COLORS],
		                                        callback=callback, sizeStyle=sizeStyle)
		for i, item in enumerate(self.getNSPopUpButton().itemArray()):
			item.setImage_(label_swatch(i))
		self.set(value)

	def set(self, value):
		if isinstance(value, int) and 0 <= value < len(LABEL_COLORS):
			super(TRLabelColorPopUp, self).set(value)
