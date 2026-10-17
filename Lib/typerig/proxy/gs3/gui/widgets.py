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
	NSLineBreakByClipping,
	NSButton,
	NSPushOnPushOffButton,
	NSMomentaryPushInButton,
	NSCenterTextAlignment,
)

from .icon_font import tr_attr
from .config    import UI
from .palette_config import PALETTE


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


# Bezels that fill their frame: drawn rect == alignment rect, room for the icon.
_FILL_BEZELS = (10,)		# .smallSquare


class GridIconButton(IconButton):
	'''IconButton for Toolbar grids (sidebar palettes, palette_config.PALETTE).

	Two modes, chosen by PALETTE.BEZEL:
	  - TR Panel bezels (2 GS3, 16 glass GS4): exactly TR Panel's IconButton
	    — same bezel, vanilla's frame padding, no extra cell calls. Extra
	    calls on the cell broke the ligatures on GS3 (seen 2026-10-17), so
	    nothing is added here. The grid GAP must cover the padding (>= 12).
	  - fill bezels (10 .smallSquare): no padding; the frame is derived so the
	    drawn bezel is exactly posSize, square; the title never wraps.
	'''
	def __init__(self, posSize, token, callback=None, tooltip=None,
	             checkable=False, size=None):
		self._fill = PALETTE.BEZEL in _FILL_BEZELS
		if self._fill:
			self.frameAdjustments = None
		super().__init__(posSize, token, callback=callback, tooltip=tooltip,
		                 checkable=checkable, size=size)
		ns = self.getNSButton()
		if not self._fill:
			if PALETTE.BEZEL != UI.BTN.BEZEL:		# same call IconButton makes
				ns.setBezelStyle_(PALETTE.BEZEL)
			return
		ns.setBezelStyle_(PALETTE.BEZEL)
		cell = ns.cell()
		cell.setWraps_(False)
		cell.setLineBreakMode_(NSLineBreakByClipping)

	def _adjustPosSize(self, frame):
		if not self._fill:
			return super()._adjustPosSize(frame)		# vanilla padding, as TR Panel
		# posSize is the drawn bezel; ask AppKit which frame draws it.
		(x, y), (w, h) = frame
		r = self._nsObject.frameForAlignmentRect_(((x, y), (w, h)))
		return ((r.origin.x, r.origin.y), (r.size.width, r.size.height))
