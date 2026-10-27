# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — observer base (TR Toolbar observer row)
#
# An observer is a Glyphs-wide helper (layer toast, stem probe, ...) that
# hooks Glyphs callbacks while it is on, switched from a checkable button
# on the Toolbar observer row.
#
#   class MyObserver(TRObserver):
#       key = 'com.typerig.observer.my'          # Glyphs.defaults key
#       def callbacks(self):
#           return [(self._on_update, UPDATEINTERFACE)]
#
#   observer = MyObserver()                      # one per Glyphs session
#   observer.restore()                           # once: on if it was on at quit
#   observer.bind_button(btn)                    # button follows the state
#   btn callback -> observer.toggle(btn)
#
# Pointer observers set `event_mask` and implement on_event(event): an
# AppKit local event monitor runs while the observer is on (one path for
# GS3 and GS4; Glyphs' MOUSEMOVED did not reach a GS3 observer).
# on_event returns the event to pass it on, or None to swallow it.
# edit_view_at(event) maps an event to (view, layer, point in layer).
#
# Masthead scope: a Toolbar registers its TRScopeState (register_scope);
# scope_for(font) returns the one whose window shows that font, so an
# observer can follow the Active / Masters pills of the window it acts in.
#
# State lives on the observer, not on a Toolbar: Glyphs makes one Toolbar
# per document window, so every bound button shows the same state. All
# callbacks are removed when Glyphs quits (an unremoved callback can crash
# Glyphs on quit, see toolbar_host.py).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import weakref

from GlyphsApp import Glyphs
from AppKit import (NSEvent, NSNotificationCenter, NSApplicationWillTerminateNotification,
                    NSPointInRect)

# - Quit watch (one for every observer) ----------------------------------
_live     = []		# observers created this session
_quit_obs = None	# NSApplicationWillTerminate observer token

def _on_quit(notification):
	for obs in _live:
		obs.set_enabled(False, remember=False)		# keep the saved choice for restore()

def _watch_quit():
	global _quit_obs
	if _quit_obs is None:
		_quit_obs = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
			NSApplicationWillTerminateNotification, None, None, _on_quit)


# - Masthead scope (one TRScopeState per Toolbar, held weakly) -----------
_scopes = weakref.WeakSet()

def register_scope(state):
	_scopes.add(state)

def scope_for(font):
	'''TRScopeState of the Toolbar whose window shows `font`, or None.'''
	for state in list(_scopes):
		if state.owns_font(font):
			return state
	return None

def scope_masters(font):
	'''True if that Toolbar's masthead has the Masters pill on.'''
	state = scope_for(font)
	if state is None:
		return False
	p_layers = state.pLayers
	return isinstance(p_layers, tuple) and len(p_layers) > 1 and isinstance(p_layers[0], bool) and bool(p_layers[1])


# - Edit view ------------------------------------------------------------
def edit_view_at(event, inside=True):
	'''(view, layer, point) for a mouse event in the current edit tab's view:
	point in active layer coordinates. None when the event is in another
	window, there is no active layer or (inside=True) the pointer is outside
	the visible part of the view. inside=False keeps a drag that left it.'''
	font = Glyphs.font
	tab = font.currentTab if font is not None else None
	if tab is None:
		return None
	view = tab.graphicView()
	if event.window() != view.window():
		return None
	if inside and not NSPointInRect(view.convertPoint_fromView_(event.locationInWindow(), None), view.visibleRect()):
		return None
	layer = view.activeLayer()
	if layer is None:
		return None
	return view, layer, view.getActiveLocation_(event)


class TRObserver(object):
	'''Base for Toolbar observers. Subclasses set `key`, implement
	callbacks() and, for pointer work, event_mask + on_event(event).
	installed() / removed() run after the callbacks go in / out.'''
	key        = None		# Glyphs.defaults key for the remembered on/off
	name       = 'observer'	# for messages
	event_mask = 0			# NSEventMask... bits for the local event monitor; 0 = none

	def __init__(self):
		self._on       = False
		self._restored = False
		self._monitor  = None		# NSEvent local monitor token
		self._error    = None		# last message printed (no flood per event)
		self._buttons  = weakref.WeakSet()	# bound checkable buttons (one per Toolbar)
		self._hooks    = self.callbacks()	# built once: Glyphs removes a callback by str(target)
		_live.append(self)

	# - Subclass API ------------------------------------------------------
	def callbacks(self):
		'''[(callable, Glyphs callback type), ...]'''
		return []

	def on_event(self, event):
		'''Monitored event; return it to pass it on, None to swallow it.'''
		return event

	def report(self, e):
		'''Print an error once (not again until it changes).'''
		msg = str(e)
		if msg != self._error:
			self._error = msg
			print('[TypeRig] %s:' % self.name, msg)

	def _event(self, event):
		try:
			return self.on_event(event)
		except Exception as e:
			self.report(e)
			return event		# never eat an event on an error

	def installed(self):
		pass

	def removed(self):
		pass

	# - On / off ----------------------------------------------------------
	def is_enabled(self):
		return self._on

	def set_enabled(self, on, remember=True):
		'''Install (on=True) or remove the callbacks and update bound buttons.
		remember=True stores the choice in Glyphs.defaults for restore().'''
		on = bool(on)
		try:
			if on and not self._on:
				self.installed()
				for fn, kind in self._hooks:
					Glyphs.addCallback(fn, kind)
				if self.event_mask and self._monitor is None:
					self._monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
						self.event_mask, self._event)
				self._on = True
				_watch_quit()
			elif not on and self._on:
				if self._monitor is not None:
					NSEvent.removeMonitor_(self._monitor)
					self._monitor = None
				for fn, kind in self._hooks:
					Glyphs.removeCallback(fn)		# one form for GS3 + GS4: every type fn is on
				self._on = False
				self.removed()
		except Exception as e:
			print('[TypeRig] %s:' % self.name, e)
		if remember and self.key:
			Glyphs.defaults[self.key] = self._on
		for btn in list(self._buttons):
			btn.setChecked(self._on)

	def restore(self):
		'''Switch on if it was on when Glyphs last quit. Runs once per
		session; later calls do nothing.'''
		if self._restored:
			return
		self._restored = True
		try:
			if self.key and Glyphs.defaults[self.key]:
				self.set_enabled(True, remember=False)
		except Exception as e:
			print('[TypeRig] %s restore:' % self.name, e)

	# - Buttons -----------------------------------------------------------
	def bind_button(self, btn):
		'''Keep a checkable button (IconButton / GridIconButton) in step with
		the observer, in every Toolbar. Held weakly.'''
		self._buttons.add(btn)
		btn.setChecked(self._on)

	def toggle(self, btn):
		'''Button callback: switch to the button's state.'''
		self.set_enabled(btn.isChecked())
