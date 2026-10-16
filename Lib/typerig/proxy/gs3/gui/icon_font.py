# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — icon font registration + ligature attributed-string helper
#
# The TypeRig icon font (TypeRig Icons / TypeRigIcons-Regular) maps named
# ligatures like "check", "fold_up", "node_align_left" to single glyphs.
# AppKit needs NSLigatureAttributeName=2 (all ligatures including
# discretionary) for those tokens to render as one glyph instead of letters.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import os

from AppKit import (
	NSAttributedString,
	NSFont,
	NSFontAttributeName,
	NSLigatureAttributeName,
	NSForegroundColorAttributeName,
	NSBaselineOffsetAttributeName,
	NSParagraphStyleAttributeName,
	NSMutableParagraphStyle,
	NSCenterTextAlignment,
	NSColor,
)
from CoreText import CTFontManagerRegisterFontsForURL, kCTFontManagerScopeProcess
from Foundation import NSURL

# Family + PostScript name baked into typerig-icons.ttf (verified via fontTools).
ICON_FAMILY  = 'TypeRig Icons'
ICON_PS_NAME = 'TypeRigIcons-Regular'

_REGISTERED = False

# Bundled default — the icon font ships inside this package's assets/
# folder. Plugins typically call register_icon_font() with no argument.
_DEFAULT_TTF = os.path.join(os.path.dirname(__file__), 'assets', 'typerig-icons.ttf')


def register_icon_font(ttf_path=None):
	'''Register the icon font with Core Text for the current process.

	Idempotent: registering the same URL twice raises a Core Text error
	(kCTFontManagerErrorAlreadyRegistered=105), which we swallow.
	If `ttf_path` is None the bundled default (assets/typerig-icons.ttf)
	inside this package is used.

	Returns True on success or already-registered, False otherwise.
	'''
	global _REGISTERED
	if _REGISTERED:
		return True
	if ttf_path is None:
		ttf_path = _DEFAULT_TTF
	if not os.path.isfile(ttf_path):
		print('[typerig.proxy.gs3.gui] icon font not found:', ttf_path)
		return False
	url = NSURL.fileURLWithPath_(ttf_path)
	ok, err = CTFontManagerRegisterFontsForURL(url, kCTFontManagerScopeProcess, None)
	if ok or (err is not None and err.code() == 105):
		_REGISTERED = True
		return True
	print('[TypeRig Panel] icon font registration failed:', err)
	return False


def tr_attr(token, size=16, color=None, baseline_offset=None):
	'''Build an NSAttributedString that renders the icon ligature `token`.

	Args:
		token (str): ligature name, e.g. 'check', 'fold_up', 'node_align_left'.
		size (float): point size.
		color (NSColor or None): optional fill colour.
		baseline_offset (float or None): vertical shift in points; positive = up.
			Defaults to size * 0.18 to compensate for the font's low baseline
			against NSButton's vertical-centre layout.

	Returns:
		NSAttributedString — assign to a button via setAttributedTitle_.
	'''
	font = NSFont.fontWithName_size_(ICON_PS_NAME, size)
	if font is None:
		# Font not registered or PS name wrong — fall back to system font + raw text.
		font = NSFont.systemFontOfSize_(size)

	if baseline_offset is None:
		baseline_offset = -size * 0.15

	# Centre the (single-glyph) string horizontally inside the button cell.
	para = NSMutableParagraphStyle.alloc().init()
	para.setAlignment_(NSCenterTextAlignment)

	attrs = {
		NSFontAttributeName: font,
		NSLigatureAttributeName: 2,
		NSBaselineOffsetAttributeName: float(baseline_offset),
		NSParagraphStyleAttributeName: para,
	}
	if color is not None:
		attrs[NSForegroundColorAttributeName] = color
	return NSAttributedString.alloc().initWithString_attributes_(token, attrs)
