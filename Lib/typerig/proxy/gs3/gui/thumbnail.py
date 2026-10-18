# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — outline thumbnails
#
# Draws contours as images, for pickers that show the parts themselves
# (Clipboard bank, part / component pickers, ...).
#
#   thumb_image(source, ...)  -> NSImage (vector: sharp at any size, follows
#                                light / dark mode, drawn on demand by AppKit)
#   TRThumbGrid(posSize, ...) -> scrolling grid of toggle buttons, one per
#                                ThumbItem; click = select, Shift / Cmd-click
#                                = add / remove; reflows on resize
#
# A source is anything that holds contours, read by duck typing: a core
# Contour / Shape / Layer (or their trContour / trShape / trLayer proxies),
# a list of those, or a ready NSBezierPath (e.g. GSLayer.completeBezierPath).
# Nothing here reads GlyphsApp objects, so a bank loaded from XML draws the
# same way as a live selection. Sizes and colours: UI.THUMB in config.py.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import weakref

import vanilla
from AppKit import (
	NSAffineTransform,
	NSBezierPath,
	NSBitmapImageRep,
	NSColor,
	NSEvent,
	NSEventModifierFlagCommand,
	NSEventModifierFlagShift,
	NSGraphicsContext,
	NSImage,
	NSImageOnly,
	NSImageScaleProportionallyUpOrDown,
	NSLineBreakByTruncatingTail,
	NSMakeRect,
	NSPNGFileType,
	NSPushOnPushOffButton,
	NSViewFrameDidChangeNotification,
)
from Foundation import NSNotificationCenter

from .config import UI

# - Layout aliases — values live in config.py. Do NOT redeclare.
THUMB = UI.THUMB

_OFF_TYPES = ('curve', 'off')		# core BCP types: cubic handle, quadratic off-curve
_WINDING   = {'nonzero': 0, 'evenodd': 1}		# NSWindingRule


# - Contours -> NSBezierPath -------------------------------------------------
def iter_contours(source):
	'''Yield every contour held by source (see module header).'''
	if source is None:
		return
	if isinstance(source, (list, tuple)):
		for item in source:
			for contour in iter_contours(item):
				yield contour
	elif hasattr(source, 'nodes') and hasattr(source, 'closed'):
		yield source
	elif hasattr(source, 'shapes'):
		for shape in source.shapes:
			for contour in iter_contours(shape):
				yield contour
	elif hasattr(source, 'contours'):
		for contour in iter_contours(list(source.contours)):
			yield contour


def _lerp(a, b, t):
	return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _segment(path, p0, offs, p1):
	'''Append one on-curve to on-curve segment. offs: the off-curves between.'''
	if not offs:
		path.lineToPoint_(p1[:2])
		return
	if len(offs) == 2 and offs[0][2] == 'curve' and offs[1][2] == 'curve':
		path.curveToPoint_controlPoint1_controlPoint2_(p1[:2], offs[0][:2], offs[1][:2])
		return
	# Quadratic run (TrueType): implied on-curves halfway between off-curves,
	# each quadratic piece raised to a cubic.
	start = p0[:2]
	for i, q in enumerate(offs):
		end = _lerp(q, offs[i + 1], .5) if i + 1 < len(offs) else p1[:2]
		path.curveToPoint_controlPoint1_controlPoint2_(
			end, _lerp(start, q[:2], 2. / 3), _lerp(end, q[:2], 2. / 3))
		start = end


def contour_path(contour, path=None):
	'''Append a contour (nodes with x / y / type, plus closed) to path.
	Returns (path, [on-curve (x, y)]). Off-curves after the last on-curve of
	an open contour are dropped.'''
	if path is None:
		path = NSBezierPath.bezierPath()
	pts = [(float(n.x), float(n.y), n.type) for n in contour.nodes]
	closed = bool(contour.closed)
	ons = [i for i, p in enumerate(pts) if p[2] not in _OFF_TYPES]
	if ons:
		pts = pts[ons[0]:] + pts[:ons[0]]
	elif closed and pts:		# all off-curves: start on the implied point
		pts = [_lerp(pts[-1], pts[0], .5) + ('on',)] + pts
	else:
		return path, []
	if closed:
		pts.append(pts[0])
	path.moveToPoint_(pts[0][:2])
	prev, offs = pts[0], []
	for i, p in enumerate(pts[1:], 1):
		if p[2] in _OFF_TYPES:
			offs.append(p)
			continue
		if not (closed and i == len(pts) - 1 and not offs):		# closePath draws the closing line
			_segment(path, prev, offs, p)
		prev, offs = p, []
	if closed:
		path.closePath()
	return path, [p[:2] for p in pts if p[2] not in _OFF_TYPES]


def outline_paths(source):
	'''source -> (fill path: closed contours, stroke path: open contours,
	[on-curve (x, y) of the open contours]).'''
	fill, stroke, points = NSBezierPath.bezierPath(), NSBezierPath.bezierPath(), []
	items = source if isinstance(source, (list, tuple)) else [source]
	for item in items:
		if isinstance(item, NSBezierPath):
			fill.appendBezierPath_(item)
			continue
		for contour in iter_contours(item):
			if contour.closed:
				contour_path(contour, fill)
			else:
				points += contour_path(contour, stroke)[1]
	return fill, stroke, points


# - Image --------------------------------------------------------------------
def _color(tone):
	'''Tone name (UI.THUMB.TONES key or NSColor method name) or NSColor.'''
	if isinstance(tone, NSColor):
		return tone
	return getattr(NSColor, THUMB.TONES.get(tone, tone))()


def _union(paths):
	'''(xmin, ymin, xmax, ymax) over the non-empty paths, or None.'''
	box = None
	for path in paths:
		if path.isEmpty():
			continue
		(x, y), (w, h) = path.bounds()
		if box is None:
			box = [x, y, x + w, y + h]
		else:
			box = [min(box[0], x), min(box[1], y), max(box[2], x + w), max(box[3], y + h)]
	return box


def _placed(path, transform):
	path = path.copy()
	path.transformUsingAffineTransform_(transform)
	return path


def thumb_image(source, size=None, tone='label', context=None, fit=None, nodes=None, outline=False):
	'''Draw source into a square NSImage.

	size    : edge in pt; default UI.THUMB.SIZES[UI.THUMB.SIZE_INDEX]
	tone    : colour of source (UI.THUMB.TONES key, NSColor method name or NSColor)
	context : drawn behind source in the 'muted' tone and fitted with it —
	          e.g. the whole glyph behind a copied part
	fit     : (xmin, ymin, xmax, ymax) font units to fit instead of the drawn
	          bounds; pass the same box to a set of thumbnails to keep their
	          relative scale. xmin == xmax: centre x on the drawing, e.g.
	          (0, descender, 0, ascender)
	nodes   : dots on on-curve nodes of open contours; None = when there are any
	outline : stroke closed contours instead of filling them
	'''
	size = size or THUMB.SIZES[THUMB.SIZE_INDEX]
	fill, stroke, points = outline_paths(source)
	ctx_fill, ctx_stroke, _ = outline_paths(context) if context is not None else (
		NSBezierPath.bezierPath(), NSBezierPath.bezierPath(), [])
	drawn = _union((fill, stroke, ctx_fill, ctx_stroke))
	box = list(fit) if fit else drawn
	if box is None:		# nothing to draw
		box = [0, 0, 1, 1]
	elif fit and box[0] == box[2] and drawn:		# fit height only, x from the drawing
		box[0], box[2] = drawn[0], drawn[2]
	span = max(box[2] - box[0], box[3] - box[1]) or 1.
	scale = (size - 2. * THUMB.INSET) / span

	t = NSAffineTransform.transform()
	t.translateXBy_yBy_(size / 2., size / 2.)
	t.scaleBy_(scale)
	t.translateXBy_yBy_(-(box[0] + box[2]) / 2., -(box[1] + box[3]) / 2.)

	fill, stroke = _placed(fill, t), _placed(stroke, t)
	ctx_fill, ctx_stroke = _placed(ctx_fill, t), _placed(ctx_stroke, t)
	for path in (fill, ctx_fill):
		path.setWindingRule_(_WINDING[THUMB.WINDING])
	for path in (fill, stroke, ctx_fill, ctx_stroke):
		path.setLineWidth_(THUMB.STROKE)
	dots = NSBezierPath.bezierPath()
	if nodes or (nodes is None and points):
		r = THUMB.NODE
		for x, y in points:
			x, y = t.transformPoint_((x, y))
			dots.appendBezierPathWithOvalInRect_(NSMakeRect(x - r, y - r, 2 * r, 2 * r))

	def draw(rect):
		# Colours resolve here, so the image follows light / dark mode.
		_color('muted').set()
		ctx_fill.fill()
		ctx_stroke.stroke()
		_color(tone).set()
		if outline:
			fill.stroke()
		else:
			fill.fill()
		stroke.stroke()
		dots.fill()
		return True

	return NSImage.imageWithSize_flipped_drawingHandler_((size, size), False, draw)


def save_png(image, file_path, scale=2):
	'''Write an NSImage to PNG at scale x its size (tests, docs).'''
	w, h = image.size()
	rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
		None, int(w * scale), int(h * scale), 8, 4, True, False, 'NSCalibratedRGBColorSpace', 0, 0)
	rep.setSize_((w, h))
	NSGraphicsContext.saveGraphicsState()
	NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
	image.drawInRect_(NSMakeRect(0, 0, w, h))
	NSGraphicsContext.restoreGraphicsState()
	return rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(file_path, True)


# - Grid ---------------------------------------------------------------------
class ThumbItem(object):
	'''One grid cell. key: any hashable id; source / tone / context: as
	thumb_image(); caption under the cell; tooltip defaults to the caption.'''
	def __init__(self, key, source, caption='', tooltip=None, tone='label', context=None):
		self.key     = key
		self.source  = source
		self.caption = caption
		self.tooltip = tooltip
		self.tone    = tone
		self.context = context


def _cell_callback(grid_ref, key):
	'''Button callback that holds the grid weakly (no grid <-> button cycle).'''
	def callback(sender):
		grid = grid_ref()
		if grid is not None:
			grid._click(key)
	return callback


class TRThumbGrid(vanilla.Group):
	'''Scrolling grid of thumbnail toggle buttons.

	callback : function(grid) on every selection change
	captions : draw ThumbItem.caption under each cell
	fit      : shared fit box for every cell (see thumb_image)

	Click selects one cell; Shift- or Cmd-click adds / removes. Cells wrap
	to the width and reflow when the view is resized.
	'''
	def __init__(self, posSize, callback=None, captions=True, fit=None, size_index=None):
		super(TRThumbGrid, self).__init__(posSize)
		self._items    = []			# ThumbItem, in grid order
		self._cells    = {}			# key -> cell attribute name on the document group
		self._selected = set()
		self._serial   = 0
		self._busy     = False
		self._on_select = callback
		self._captions = captions
		self._fit      = fit
		self._size_i   = THUMB.SIZE_INDEX if size_index is None else size_index
		# Document group in a plain dict: a vanilla attribute would be added
		# to this Group as a subview; it must be the scroll's document view.
		doc = vanilla.Group((0, 0, 0, 0))
		self._doc_ref = {'doc': doc}
		self.scroll = vanilla.ScrollView((0, 0, -0, -0), doc.getNSView(),
			hasHorizontalScroller=False, autohidesScrollers=True, drawsBackground=False)
		self._observe_resize()

	# - Items -------------------------------------------------------------
	def set_items(self, items):
		'''Replace every cell. Keeps the selection of keys still present.'''
		for item in list(self._items):
			self._drop_cell(item.key)
		self._items = []
		for item in items:
			self._items.append(item)
			self._make_cell(item)
		self._selected &= set(self._cells)
		self._sync_states()
		self.reflow(to_top=True)

	def add(self, item, select=False):
		'''Append one cell; select=True makes it the only selected cell.'''
		self._items.append(item)
		self._make_cell(item)
		if select:
			self._selected = {item.key}
		self._sync_states()
		self.reflow()

	def remove(self, keys):
		keys = set(keys)
		for key in keys & set(self._cells):
			self._drop_cell(key)
		self._items = [item for item in self._items if item.key not in keys]
		self._selected -= keys
		self.reflow()

	def items(self):
		return list(self._items)

	def item(self, key):
		for item in self._items:
			if item.key == key:
				return item
		return None

	def update_item(self, key, **changes):
		'''Change ThumbItem fields (source, caption, tone, ...) and redraw the cell.'''
		item = self.item(key)
		if item is None:
			return
		for name, value in changes.items():
			setattr(item, name, value)
		self._render(item)

	# - Selection ---------------------------------------------------------
	def get_selection(self):
		'''Selected keys, in grid order.'''
		return [item.key for item in self._items if item.key in self._selected]

	def set_selection(self, keys):
		self._selected = set(keys) & set(self._cells)
		self._sync_states()

	def _click(self, key):
		flags = NSEvent.modifierFlags()
		if flags & (NSEventModifierFlagShift | NSEventModifierFlagCommand):
			self._selected ^= {key}
		else:
			self._selected = {key}
		self._sync_states()
		if self._on_select is not None:
			self._on_select(self)

	def _sync_states(self):
		doc = self._doc_ref['doc']
		for key, name in self._cells.items():
			getattr(doc, name).getNSButton().setState_(1 if key in self._selected else 0)

	# - Size --------------------------------------------------------------
	def cell_size(self):
		return THUMB.SIZES[self._size_i]

	def set_size_index(self, index):
		self._size_i = index % len(THUMB.SIZES)
		for item in self._items:
			self._render(item)
		self.reflow()

	def cycle_size(self):
		self.set_size_index(self._size_i + 1)

	def set_fit(self, fit):
		'''Shared fit box for every cell (see thumb_image); None = each its own.'''
		self._fit = fit
		for item in self._items:
			self._render(item)

	# - Cells -------------------------------------------------------------
	def _make_cell(self, item):
		doc, s = self._doc_ref['doc'], self.cell_size()
		name = 'cell_%d' % self._serial
		self._serial += 1
		btn = vanilla.ImageButton((0, 0, s, s), callback=_cell_callback(weakref.ref(self), item.key))
		ns = btn.getNSButton()
		ns.setButtonType_(NSPushOnPushOffButton)
		ns.setBezelStyle_(THUMB.BEZEL)
		ns.setImagePosition_(NSImageOnly)
		ns.setImageScaling_(NSImageScaleProportionallyUpOrDown)
		setattr(doc, name, btn)
		if self._captions and THUMB.CAP_H:
			cap = vanilla.TextBox((0, 0, s, THUMB.CAP_H), '', alignment='center', sizeStyle=THUMB.CAP_STYLE)
			cap.getNSTextField().cell().setLineBreakMode_(NSLineBreakByTruncatingTail)
			setattr(doc, name + '_cap', cap)
		self._cells[item.key] = name
		self._render(item)

	def _render(self, item):
		doc, name = self._doc_ref['doc'], self._cells[item.key]
		btn = getattr(doc, name)
		btn.setImage(imageObject=thumb_image(item.source, size=self.cell_size(),
			tone=item.tone, context=item.context, fit=self._fit))
		btn.getNSButton().setToolTip_(item.tooltip or item.caption or None)
		if hasattr(doc, name + '_cap'):
			getattr(doc, name + '_cap').set(item.caption or '')

	def _drop_cell(self, key):
		doc, name = self._doc_ref['doc'], self._cells.pop(key)
		delattr(doc, name)
		if hasattr(doc, name + '_cap'):
			delattr(doc, name + '_cap')

	# - Layout ------------------------------------------------------------
	def reflow(self, to_top=False):
		'''Wrap the cells to the current width. The document view is never
		shorter than the visible area (AppKit pins a short, unflipped
		document view to the bottom).'''
		if self._busy:
			return
		self._busy = True
		try:
			sv   = self.scroll.getNSScrollView()
			clip = sv.contentView()
			view_w, view_h = sv.contentSize()
			s    = self.cell_size()
			cap  = THUMB.CAP_H if self._captions else 0
			cell_h = s + cap
			cols = max(1, int((view_w - 2 * THUMB.PAD + THUMB.GAP) // (s + THUMB.GAP)))
			rows = -(-len(self._items) // cols)
			doc_h = max(view_h, 2 * THUMB.PAD + rows * (cell_h + THUMB.GAP) - THUMB.GAP)

			old_h = clip.documentRect().size.height
			from_top = old_h - clip.bounds().origin.y - view_h		# scrolled distance from the top
			doc = self._doc_ref['doc']
			doc.getNSView().setFrame_(((0, 0), (view_w, doc_h)))
			for i, item in enumerate(self._items):
				row, col = divmod(i, cols)
				x = THUMB.PAD + col * (s + THUMB.GAP)
				y = THUMB.PAD + row * (cell_h + THUMB.GAP)
				name = self._cells[item.key]
				getattr(doc, name).setPosSize((x, y, s, s))
				if hasattr(doc, name + '_cap'):
					getattr(doc, name + '_cap').setPosSize((x, y + s, s, cap))
			from_top = 0 if to_top else max(0, from_top)
			clip.scrollToPoint_((0, max(0, doc_h - view_h - from_top)))
			sv.reflectScrolledClipView_(clip)
		finally:
			self._busy = False

	def _observe_resize(self):
		'''Reflow when the visible area changes size. The block holds the
		grid weakly and unregisters itself once the grid is gone.'''
		clip = self.scroll.getNSScrollView().contentView()
		clip.setPostsFrameChangedNotifications_(True)
		center, grid_ref, token = NSNotificationCenter.defaultCenter(), weakref.ref(self), []

		def on_frame(note):
			grid = grid_ref()
			if grid is None:
				center.removeObserver_(token[0])
				return
			grid.reflow()

		token.append(center.addObserverForName_object_queue_usingBlock_(
			NSViewFrameDidChangeNotification, clip, None, on_frame))
