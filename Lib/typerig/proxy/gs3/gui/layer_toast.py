# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — layer change toast (observer)
#
# Glyphs shows the current layer name only in the Layers panel and the
# master buttons. This observer shows a small label at the pointer when
# the active layer changes, then fades it out. Brace and bracket layers
# read "<layer>  ·  <master>". Switched from the TR Toolbar observer row.
#
#   from typerig.proxy.gs3.gui.layer_toast import observer
#   observer.restore(); observer.bind_button(btn); observer.toggle(btn)
#   (see observer.py, TRObserver)
#
# Canvas drawing (DRAWFOREGROUND) is fixed to glyph space and a corner
# overlay via tab.viewPort did not show, so the label is a borderless,
# non-activating NSPanel at the pointer.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

from GlyphsApp import Glyphs, UPDATEINTERFACE
from AppKit import (NSPanel, NSTextField, NSColor, NSFont, NSEvent, NSMakeRect,
                    NSBackingStoreBuffered, NSStatusWindowLevel, NSAnimationContext,
                    NSTimer)

from .observer       import TRObserver
from .palette_config import PALETTE

NSWindowStyleMaskBorderless         = 0
NSWindowStyleMaskNonactivatingPanel = 1 << 7

TOAST = PALETTE.TOAST

# - Text -----------------------------------------------------------------
def current_text():
	font = Glyphs.font
	if not font or not font.selectedLayers:
		return None
	layer  = font.selectedLayers[0]
	master = layer.master
	if master is None:
		return layer.name
	return master.name if layer.isMasterLayer else '{}  ·  {}'.format(layer.name, master.name)

# - Toast ----------------------------------------------------------------
_panel = None
_label = None
_timer = None
_gen   = 0		# bumped per toast; a stale fade does nothing

def _make_panel():
	panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
		NSMakeRect(0, 0, TOAST.FONT_PT, TOAST.FONT_PT),	# sized per toast
		NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
		NSBackingStoreBuffered, False)
	panel.setOpaque_(False)
	panel.setBackgroundColor_(NSColor.clearColor())
	panel.setLevel_(NSStatusWindowLevel)
	panel.setIgnoresMouseEvents_(True)
	panel.setHasShadow_(True)
	panel.setHidesOnDeactivate_(True)

	view = panel.contentView()
	view.setWantsLayer_(True)
	view.layer().setCornerRadius_(TOAST.RADIUS)
	bg = getattr(NSColor, TOAST.BG)().colorWithAlphaComponent_(TOAST.BG_ALPHA)
	view.layer().setBackgroundColor_(bg.CGColor())

	label = NSTextField.labelWithString_('')
	label.setFont_(NSFont.boldSystemFontOfSize_(TOAST.FONT_PT))
	label.setTextColor_(getattr(NSColor, TOAST.FG)())
	view.addSubview_(label)
	return panel, label

def show_toast(text):
	global _panel, _label, _timer, _gen
	if _panel is None:
		_panel, _label = _make_panel()
	panel, label = _panel, _label

	_gen += 1
	gen = _gen
	if _timer is not None:
		_timer.invalidate()

	label.setStringValue_(text)
	label.sizeToFit()
	lw, lh = label.frame().size.width, label.frame().size.height
	w, h = lw + 2 * TOAST.PAD_X, lh + 2 * TOAST.PAD_Y
	label.setFrameOrigin_((TOAST.PAD_X, TOAST.PAD_Y))

	mx, my = NSEvent.mouseLocation()		# screen coords, y up
	dx, dy = TOAST.OFFSET
	panel.setFrame_display_(NSMakeRect(mx + dx, my - dy - h, w, h), True)
	panel.setAlphaValue_(1.0)
	panel.orderFrontRegardless()

	def start_fade(timer):
		if gen != _gen:
			return
		def changes(ctx):
			ctx.setDuration_(TOAST.FADE)
			panel.animator().setAlphaValue_(0.0)
		def done():
			if gen == _gen:
				panel.orderOut_(None)
		NSAnimationContext.runAnimationGroup_completionHandler_(changes, done)

	_timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(TOAST.HOLD, False, start_fade)

def hide_toast():
	if _panel is not None:
		_panel.orderOut_(None)

# - Observer -------------------------------------------------------------
class LayerToast(TRObserver):
	key  = 'com.typerig.observer.layerToast'
	name = 'layer toast'

	def callbacks(self):
		return [(self._on_update, UPDATEINTERFACE)]

	def installed(self):
		self._last = current_text()		# don't fire on install

	def removed(self):
		hide_toast()

	def _on_update(self, sender=None):
		try:
			text = current_text()
			if text and text != self._last:
				self._last = text
				show_toast(text)
		except Exception as e:
			print('[TypeRig] layer toast:', e)


observer = LayerToast()
