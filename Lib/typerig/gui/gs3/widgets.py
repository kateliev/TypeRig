# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — vanilla widget wrappers
#
# IconButton: a fixed-size square vanilla.Button that renders an icon-font
# ligature as its title (via NSAttributedString). Supports checkable
# (toggle) mode for masthead pills.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import vanilla
from AppKit import (
	NSButton,
	NSPushOnPushOffButton,
	NSMomentaryPushInButton,
	NSCenterTextAlignment,
)

from .icon_font import tr_attr
from .config    import UI


class IconButton(vanilla.Button):
	'''Square button rendered with the TypeRig icon font.

	Args:
		posSize: standard vanilla 4-tuple (x, y, w, h).
		token (str): icon ligature name.
		callback: function(sender) -> None.
		tooltip (str | None): hover tooltip.
		checkable (bool): if True, behaves as a toggle.
		size (float): icon point size. Defaults to `UI.BTN.ICON_PT` — do
			not pass a literal at call sites; if a variant size is
			needed, add a new field on `UI` and reference it here.
	'''
	def __init__(self, posSize, token, callback=None, tooltip=None,
	             checkable=False, size=None):
		if size is None:
			size = UI.BTN.ICON_PT
		super().__init__(posSize, '', callback=callback)
		ns = self.getNSButton()
		# Resolve frame height for baseline-offset math. Negative h (right-
		# anchored, rare for IconButton) falls back to the canonical size.
		h = posSize[3]
		if not isinstance(h, (int, float)) or h <= 0:
			h = UI.BTN.SIZE
		# Square-family bezels (2/3/4) honor frame height, but NSAttributedString
		# text centres on font baseline, not glyph visual centre — so the icon
		# rides high in a tall bezel. Push it down by half the extra vertical
		# space plus the icon-font glyph-asymmetry kick.
		baseline_offset = -((h - size) / 2.0) - size * UI.BTN.ICON_KICK
		ns.setAttributedTitle_(tr_attr(token, size=size, baseline_offset=baseline_offset))
		ns.setBezelStyle_(UI.BTN.BEZEL)
		ns.setAlignment_(NSCenterTextAlignment)
		if checkable:
			ns.setButtonType_(NSPushOnPushOffButton)
		else:
			ns.setButtonType_(NSMomentaryPushInButton)
		if tooltip:
			ns.setToolTip_(tooltip)
		self._token           = token
		self._size            = size
		self._baseline_offset = baseline_offset

	def setToken(self, token):
		'''Swap the rendered icon (e.g. fold_up <-> fold_down).'''
		self._token = token
		self.getNSButton().setAttributedTitle_(
			tr_attr(token, size=self._size,
			        baseline_offset=self._baseline_offset))

	def isChecked(self):
		return bool(self.getNSButton().state())

	def setChecked(self, value):
		self.getNSButton().setState_(1 if value else 0)
