# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — layer change toast (observer)
#
# Glyphs shows the current layer name only in the Layers panel and the
# master buttons. This observer shows a small label at the pointer when
# the active layer changes, then fades it out. Brace and bracket layers
# read "<layer>  ·  <master>". Switched from the TR Toolbar observer row.
#
#   from typerig.proxy.gs3.gui import layer_toast
#   layer_toast.restore()                 # once: install if it was on at quit
#   layer_toast.bind_button(btn)          # checkable button follows the state
#   layer_toast.set_enabled(True)         # install; remembered in Glyphs.defaults
#
# Canvas drawing (DRAWFOREGROUND) is fixed to glyph space and a corner
# overlay via tab.viewPort did not show, so the label is a borderless,
# non-activating NSPanel at the pointer.
#
# State lives on this module, not on a Toolbar: Glyphs makes one Toolbar
# per document window, so every bound button shows the same state. The
# callback is removed when Glyphs quits (an unremoved callback can crash
# Glyphs on quit, see toolbar_host.py).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import weakref

from GlyphsApp import Glyphs, UPDATEINTERFACE
from AppKit import (NSPanel, NSTextField, NSColor, NSFont, NSEvent, NSMakeRect,
                    NSBackingStoreBuffered, NSStatusWindowLevel, NSAnimationContext,
                    NSTimer, NSNotificationCenter, NSApplicationWillTerminateNotification)

from .palette_config import PALETTE

NSWindowStyleMaskBorderless         = 0
NSWindowStyleMaskNonactivatingPanel = 1 << 7

DEFAULTS_KEY = 'com.typerig.observer.layerToast'
TOAST        = PALETTE.TOAST

# - State ----------------------------------------------------------------
_callback = None	# installed UPDATEINTERFACE callback, None = off
_panel    = None
_label    = None
_timer    = None
_gen      = 0		# bumped per toast; a stale fade does nothing
_last     = None	# last text shown
_restored = False
_quit_obs = None	# NSApplicationWillTerminate observer token
_buttons  = weakref.WeakSet()	# bound checkable buttons (one per Toolbar)

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

def _on_update(sender=None):
	global _last
	try:
		text = current_text()
		if text and text != _last:
			_last = text
			show_toast(text)
	except Exception as e:
		print('[TypeRig] layer toast:', e)

# - On / off -------------------------------------------------------------
def is_enabled():
	return _callback is not None

def _on_quit(notification):
	set_enabled(False, remember=False)		# keep the saved choice for restore()

def _watch_quit():
	global _quit_obs
	if _quit_obs is None:
		_quit_obs = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
			NSApplicationWillTerminateNotification, None, None, _on_quit)

def set_enabled(on, remember=True):
	'''Install (on=True) or remove the observer and update bound buttons.
	remember=True stores the choice in Glyphs.defaults for restore().'''
	global _callback, _last
	if on and _callback is None:
		_last = current_text()		# don't fire on install
		Glyphs.addCallback(_on_update, UPDATEINTERFACE)
		_callback = _on_update
		_watch_quit()
	elif not on and _callback is not None:
		Glyphs.removeCallback(_callback)
		_callback = None
		if _panel is not None:
			_panel.orderOut_(None)
	if remember:
		Glyphs.defaults[DEFAULTS_KEY] = bool(on)
	for btn in list(_buttons):
		btn.setChecked(is_enabled())

def restore():
	'''Install the observer if it was on when Glyphs last quit. Runs once
	per session; later calls do nothing.'''
	global _restored
	if _restored:
		return
	_restored = True
	try:
		if Glyphs.defaults[DEFAULTS_KEY]:
			set_enabled(True, remember=False)
	except Exception as e:
		print('[TypeRig] layer toast restore:', e)

def bind_button(btn):
	'''Keep a checkable button (IconButton / GridIconButton) in step with
	the observer, in every Toolbar. Held weakly.'''
	_buttons.add(btn)
	btn.setChecked(is_enabled())

def toggle(btn):
	'''Button callback: switch the observer to the button's state.'''
	set_enabled(btn.isChecked())
