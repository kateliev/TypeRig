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
# State lives on the observer, not on a Toolbar: Glyphs makes one Toolbar
# per document window, so every bound button shows the same state. All
# callbacks are removed when Glyphs quits (an unremoved callback can crash
# Glyphs on quit, see toolbar_host.py).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import weakref

from GlyphsApp import Glyphs
from AppKit import NSNotificationCenter, NSApplicationWillTerminateNotification

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


class TRObserver(object):
	'''Base for Toolbar observers. Subclasses set `key` and implement
	callbacks(); installed() / removed() run after the callbacks go in / out.'''
	key  = None		# Glyphs.defaults key for the remembered on/off
	name = 'observer'	# for messages

	def __init__(self):
		self._on       = False
		self._restored = False
		self._buttons  = weakref.WeakSet()	# bound checkable buttons (one per Toolbar)
		self._hooks    = self.callbacks()	# built once: Glyphs removes a callback by str(target)
		_live.append(self)

	# - Subclass API ------------------------------------------------------
	def callbacks(self):
		'''[(callable, Glyphs callback type), ...]'''
		raise NotImplementedError

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
				self._on = True
				_watch_quit()
			elif not on and self._on:
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
