# MODULE: TypeRig / Proxy / FL / Objects / CJK bridge
# -----------------------------------------------------------
# FontLab + Qt access for the pure CJK analysis in
# typerig.core.algo.cjk. Keeps all fl6 / PythonQt use here so the
# math stays importable and testable outside FontLab.
#
# Per glyph/layer:
#   geometry_of(pg, layer) -> Geometry(contours, path, frame, ...)
#   rasterize(path, frame, S) -> flat ink list (Qt fast path)
#   compute_gauges(geo, S) -> normalized gauge vector
#
# Whole-font runners (were balance/batch_stats.py + balance/idc_zones.py):
#   run_family_bands(...)          family mean/sd bands + outliers JSON
#   run_idc_zones(idc_lookup, ...) ⿰/⿱ split-zone JSON
#
# The zones runner takes an injected idc_lookup(pglyph, name) -> idc char
# so the IDS/CHISE database stays entirely in the calling app — this module
# never depends on it.
#
# geometry acquisition uses flLayer.getContours() (resolves components into
# layer-space flContours); flContour.path() -> QtGui.QPainterPath whose
# toSubpathPolygons() does Qt's own curve flattening. Nothing here mutates the
# font: no node edits, no glyph.update(), no undo entries.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, division, print_function

import os
import json

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import pGlyph
from typerig.proxy.fl.objects.node import eNodesContainer

from typerig.core.algo import cjk

__version__ = '1.0.0'

# Re-export so callers that only touch the bridge can read the gauge key list
# without also importing the pure core module.
GAUGE_KEYS = cjk.GAUGE_KEYS


# =====================================================================
# - Container ---------------------------------------------------------
# =====================================================================
class Geometry(object):
	'''Everything the analysis needs for one glyph/layer, font-unit space.'''
	__slots__ = ('contours', 'path', 'frame', 'advance', 'groups',
				 'glyph_name', 'layer_name', 'cache_key')

	def __init__(self, contours, path, frame, advance, groups,
				 glyph_name, layer_name, cache_key):
		self.contours   = contours		# list[list[(x, y)]]
		self.path       = path			# QtGui.QPainterPath (WindingFill)
		self.frame      = frame			# (x0, y0, x1, y1) em-square band
		self.advance    = advance		# float
		self.groups     = groups		# list[list[contour_index]] by component
		self.glyph_name = glyph_name
		self.layer_name = layer_name
		self.cache_key  = cache_key		# tuple; compare to skip recompute


def frame_for(package, layer_name, advance, upm):
	'''Em-square band in font units: x across the advance, y descender..ascender.

	Reads the *active layer's master* vertical metrics via
	FontMetrics(package, layer_name) - no setMaster, so the edit is undisturbed,
	and correct when the active layer differs from the active master. Falls back
	to the package's current master, then UPM-derived defaults.
	Returns (left, bottom, right, top).
	'''
	asc  = None
	desc = None

	if package is not None:
		# Cheap path: when the active layer IS the current master (the usual
		# case), read the package's metric values directly. Constructing
		# FontMetrics(package, layer_name) makes FontLab compute font-wide
		# metrics - slow and font-global on first use - so only pay that when
		# the edited layer differs from the current master.
		try:
			on_current_master = (str(package.master) == str(layer_name))
		except Exception:
			on_current_master = True

		if not on_current_master:
			try:
				fm   = fl6.FontMetrics(package, layer_name)
				asc  = float(fm.ascender)
				desc = float(fm.descender)
			except Exception:
				asc = desc = None

		if asc is None or desc is None:
			try:
				asc  = float(package.ascender_value)
				desc = float(package.descender_value)
			except Exception:
				asc = desc = None

	if asc is None or desc is None or (asc - desc) < 1.0:
		# Sensible default split of the em around the baseline.
		asc  = upm * 0.8
		desc = -upm * 0.2

	# Guard a zero-width advance (space-like / empty glyph) so the frame is
	# never degenerate - fall back to the em width.
	width = advance if advance > 1.0 else float(upm)

	return (0.0, desc, width, asc)


def _build_groups(layer, fl_contours, fl_to_my):
	'''Group resulting contour indices by source top-level shape (= component).

	layer.getContours() is the in-order concatenation of each top-level shape's
	contours; we slice that order by per-shape contour counts. Nested components
	collapse into their top-level shape's group. If the counts don't reconcile
	with the flat list, fall back to one group over everything - which the
	panel handles via the projection-valley path. Geometry always comes from
	getContours(), so a wrong grouping can only downgrade the second-line gauge;
	it can never corrupt positions.
	'''
	all_idx = [i for sub in fl_to_my for i in sub]

	try:
		shapes = list(layer.shapes)
	except Exception:
		shapes = []

	if len(shapes) <= 1:
		return [all_idx] if all_idx else []

	counts = []
	try:
		for shape in shapes:
			counts.append(len(shape.getContours()))
	except Exception:
		return [all_idx] if all_idx else []

	if sum(counts) != len(fl_contours):
		return [all_idx] if all_idx else []

	groups = []
	start = 0
	for cnt in counts:
		grp = []
		for fl_i in range(start, start + cnt):
			grp.extend(fl_to_my[fl_i])
		if grp:
			groups.append(grp)
		start += cnt

	return groups if groups else ([all_idx] if all_idx else [])


# =====================================================================
# - Geometry acquisition ----------------------------------------------
# =====================================================================
def get_geometry():
	'''Current glyph / active layer -> Geometry, or None when nothing to probe.

	Goes through TypeRig's pGlyph proxy: fl6.CurrentGlyph() returns an *fgGlyph*
	(fontgate) which has no getContours(); pGlyph builds the real flGlyph and the
	active flLayer. The extraction itself is in geometry_of() so batch runners and
	commands can reuse it on arbitrary glyphs/layers.
	'''
	try:
		pg = pGlyph()
	except Exception:
		return None

	if pg is None or pg.fg is None or pg.fl is None:
		return None

	layer = pg.activeLayer()			# flLayer
	if layer is None:
		return None

	return geometry_of(pg, layer)


def geometry_of(pg, layer):
	'''Build a Geometry from a given pGlyph + flLayer. Shared by the panel,
	the batch runners and commands.'''
	# Authoritative, fully-resolved flat contour list.
	try:
		fl_contours = layer.getContours()
	except Exception:
		fl_contours = []

	combined = QtGui.QPainterPath()
	combined.setFillRule(QtCore.Qt.WindingFill)

	contours = []
	cksum    = 0
	npts     = 0
	fl_to_my = []				# per fl-contour: list of resulting contour indices

	for c in fl_contours:
		my_here = []
		try:
			qp = c.path()
		except Exception:
			qp = None

		if qp is not None and not qp.isEmpty():
			combined.addPath(qp)

			# Qt flattens curves for us; each subpath -> one closed polygon.
			for poly in qp.toSubpathPolygons():
				cnt = poly.count()
				pts = []
				for i in range(cnt):
					p = poly.at(i)
					x = p.x()
					y = p.y()
					pts.append((x, y))
					cksum += int(x) + int(y)
					npts  += 1

				if len(pts) >= 3:
					my_here.append(len(contours))
					contours.append(pts)

		fl_to_my.append(my_here)

	groups = _build_groups(layer, fl_contours, fl_to_my)

	try:
		advance = float(layer.advanceWidth)
	except Exception:
		advance = 0.0

	package = None
	try:
		package = pg.package			# flPackage for the current font
	except Exception:
		package = None

	try:
		upm = float(package.upm) if package is not None else 1000.0
	except Exception:
		upm = 1000.0

	glyph_name = pg.name
	layer_name = layer.name

	frame = frame_for(package, layer_name, advance, upm)

	cache_key = (
		glyph_name,
		layer_name,
		len(contours),
		npts,
		cksum & 0xFFFFFFFF,
		int(advance),
		len(groups),
	)

	return Geometry(contours, combined, frame, advance, groups,
					glyph_name, layer_name, cache_key)


# =====================================================================
# - Rasterization (Qt fast path) --------------------------------------
# =====================================================================
def rasterize(path, frame, S):
	'''Antialiased raster of a QPainterPath over the em-square frame.

	path  : QtGui.QPainterPath in font units (WindingFill).
	frame : (x0, y0, x1, y1) font-space band mapped onto the S x S image.
	S     : raster edge length (32..64).

	returns flat list[float] of length S*S, ink = 255 - gray, row-major with
	the TOP image row first — the identical contract as
	typerig.core.algo.cjk.rasterize_contours, so bands/zones stay portable
	between the two rasterizers. All-zeros for an empty path or degenerate frame.
	'''
	ink = [0.0] * (S * S)

	if path is None or path.isEmpty():
		return ink

	x0, y0, x1, y1 = frame
	fw = x1 - x0
	fh = y1 - y0
	if fw <= 0.0 or fh <= 0.0:
		return ink

	# Grayscale8: 1 byte per pixel, white background, black ink.
	image = QtGui.QImage(S, S, QtGui.QImage.Format_Grayscale8)
	image.fill(255)

	painter = QtGui.QPainter(image)
	painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

	# Map font space -> image space. Qt's y points down, so flip: the top of
	# the image (row 0) must correspond to the ascender (y1).
	#   sx = (x - x0) / fw * S
	#   sy = (y1 - y) / fh * S
	t = QtGui.QTransform()
	t.scale(S / fw, -S / fh)
	t.translate(-x0, -y1)
	painter.setTransform(t)

	painter.setPen(QtCore.Qt.NoPen)
	painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
	painter.drawPath(path)
	painter.end()

	# Extract via the raw byte buffer, minding row padding (bytesPerLine).
	bpl  = image.bytesPerLine()
	bits = image.constBits()

	try:
		buf = bytes(bits)					# PythonQt -> bytes-like
	except Exception:
		buf = None

	if buf is not None and len(buf) >= bpl * S:
		for r in range(S):
			base = r * bpl
			out  = r * S
			for c in range(S):
				ink[out + c] = 255.0 - buf[base + c]
	else:
		# Fallback: per-pixel read (slower, but never wrong).
		for r in range(S):
			out = r * S
			for c in range(S):
				g = image.pixelColor(c, r).value() if hasattr(image, 'pixelColor') \
					else (image.pixel(c, r) & 0xFF)
				ink[out + c] = 255.0 - g

	return ink


def compute_gauges(geo, S=48, y_weight=1.05):
	'''Normalized gauge vector for one Geometry via the Qt raster + pure math.'''
	if geo is None:
		return {}
	x0, y0, x1, y1 = geo.frame
	if (x1 - x0) <= 0.0 or (y1 - y0) <= 0.0:
		return {}
	ink = rasterize(geo.path, geo.frame, S)
	return cjk.compute_gauges(geo.contours, ink, geo.frame, geo.groups, S, y_weight)


def measure_split(pg, layer, idc, S=64):
	'''Measured ⿰/⿱ split of one glyph/layer as a face fraction, or None.
	idc must be '⿰' or '⿱'. Thin wrapper: geometry -> raster -> boundary_ratio.'''
	geo = geometry_of(pg, layer)
	if geo is None:
		return None
	ink  = rasterize(geo.path, geo.frame, S)
	marg = cjk.marginals(ink, S)
	face = cjk.face_frame(ink, S, marg=marg)
	return cjk.boundary_ratio(marg, face, idc)


# =====================================================================
# - Region placement (face capture + per-master target bounds) --------
# =====================================================================
def layer_ink_bounds(pg, layer_name):
	'''(left, bottom, right, top) of a layer's ink, or None if empty.

	Reads geometry via flLayer.getContours() (resolves shapes/components across
	masters); pGlyph.contours(name) can come back empty for non-active,
	component-built masters — which would make those masters miss the face.'''
	fl_contours = None
	try:
		fl_layer = pg.layer(layer_name)
		if fl_layer is not None:
			fl_contours = fl_layer.getContours()
	except Exception:
		fl_contours = None
	if not fl_contours:
		try:
			fl_contours = pg.contours(layer_name) or []
		except Exception:
			fl_contours = []

	xs, ys = [], []
	for cnt in fl_contours:
		if cnt is None:
			continue
		try:
			nodes = cnt.nodes()
		except Exception:
			nodes = None
		if not nodes:
			continue
		for n in nodes:
			xs.append(n.x)
			ys.append(n.y)
	if not xs:
		return None
	return (min(xs), min(ys), max(xs), max(ys))


def capture_face_frames(pg, layers):
	'''Snapshot per-master face (ink) bounds: {layer_name: (left,bottom,right,top)}.
	Call this BEFORE deleting parts — it is the pre-deletion latch the region paste
	places against. Returns None if no layer had ink.'''
	frames = {}
	for name in layers:
		b = layer_ink_bounds(pg, name)
		if b is not None:
			frames[name] = b
	return frames or None


def region_bounds(pg, layers, frac_for_layer, captured_faces=None, use_face=True,
				  upm=None, default_face=None, margin=None):
	'''Per-master target Bounds for an IDC-region paste — one entry per layer.

	frac_for_layer : callable(layer_name) -> (fx0,fy0,fx1,fy1) y-UP slot fraction,
	                 or None to skip the layer. Lets the caller apply a per-master
	                 measured split.
	captured_faces : {layer_name: (l,b,r,t)} pre-deletion snapshot; a layer that is
	                 absent (or whose face is degenerate) falls back per the chain
	                 below.
	default_face   : a face rect used for masters lacking their own (e.g. the active
	                 layer's face — "a wrong face beats no face").
	margin         : imaginary-face inset (0..1 of the em) when nothing is measured.
	use_face       : when False, always use the em band.

	Per master the reference frame is: own captured face -> default_face -> imaginary
	(em inset by margin) -> em band (cjk.reference_frame). NEVER a live face of the
	glyph under construction. Returns {layer_name: Bounds} (eNodesContainer bounds —
	the same type the node-selection paste path produces, so downstream
	fit/align/flip are untouched).'''
	try:
		package = pg.package
	except Exception:
		package = None
	if upm is None:
		try:
			upm = float(package.upm)
		except Exception:
			upm = 1000.0

	out = {}
	for name in layers:
		frac = frac_for_layer(name)
		if frac is None:
			continue
		try:
			advance = float(pg.getAdvance(name))
		except Exception:
			advance = upm
		em = frame_for(package, name, advance, upm)
		face = captured_faces.get(name) if captured_faces else None
		frame = cjk.reference_frame(face, em, use_face, default_face=default_face, margin=margin)
		x0, y0, x1, y1 = cjk.rect_in_frame(frame, frac)
		corners = [
			fl6.flNode(QtCore.QPointF(x0, y0), nodeType='on'),
			fl6.flNode(QtCore.QPointF(x1, y0), nodeType='on'),
			fl6.flNode(QtCore.QPointF(x1, y1), nodeType='on'),
			fl6.flNode(QtCore.QPointF(x0, y1), nodeType='on'),
		]
		out[name] = eNodesContainer(corners).bounds
	return out


# =====================================================================
# - Output helpers ----------------------------------------------------
# =====================================================================
def _font_dir(font):
	try:
		return os.path.split(font.fg.path)[0]
	except Exception:
		return ''


def _safe_name(name):
	return ''.join(c if c.isalnum() or c in ' -_' else '_' for c in (name or 'font')).strip()


# =====================================================================
# - Whole-font runner : family bands ----------------------------------
# =====================================================================
def run_family_bands(layer=None, names=None, S=48, max_outliers=20, progress_every=500):
	'''Compute family mean/sd bands for the current font (was batch_stats.run).

	layer  - master/layer name (str) or None for each glyph's active layer.
	names  - iterable of glyph names to restrict to, or None for all glyphs.
	Writes <fontname>-balance-bands.json beside the font and returns its path.
	'''
	font = pFont()
	if font is None or font.fg is None:
		print('cjk.run_family_bands: no current font.')
		return None

	all_names = list(names) if names is not None else [g.name for g in font.fg.glyphs]
	total = len(all_names)
	print('cjk.run_family_bands: {} glyphs, layer={}, S={}'.format(
		total, layer if layer else '<active>', S))

	# Per gauge: list of (value, glyph_name) — kept so we can report outliers.
	collected = {k: [] for k in cjk.GAUGE_KEYS}
	processed = 0

	for i, gname in enumerate(all_names):
		if i % progress_every == 0:
			print('  ... {}/{}'.format(i, total))
		try:
			pg = font.glyph(gname)
			lyr = pg.layer(layer) if layer is not None else pg.activeLayer()
			if lyr is None:
				continue
			geo = geometry_of(pg, lyr)
			gauges = compute_gauges(geo, S)
		except Exception as e:
			print('  ! {} - {}'.format(gname, e))
			continue
		if not gauges:
			continue
		processed += 1
		for k, v in gauges.items():
			collected[k].append((v, gname))

	bands = {}
	outliers = {}
	for k, pairs in collected.items():
		if not pairs:
			continue
		vals = [v for v, _n in pairs]
		mean, sd, n = cjk.stats(vals)
		bands[k] = {'mean': mean, 'sd': sd, 'n': n}
		worst = sorted(pairs, key=lambda t: abs(t[0] - mean), reverse=True)[:max_outliers]
		outliers[k] = [nm for _v, nm in worst]

	out = {
		'font':     font.name,
		'source':   'family',
		'layer':    layer if layer else '<active>',
		'raster_S': S,
		'n':        processed,
		'gauges':   bands,
		'outliers': outliers,
	}

	fname = os.path.join(_font_dir(font) or os.getcwd(),
						 '{}-balance-bands.json'.format(_safe_name(font.name)))
	with open(fname, 'w') as fp:
		json.dump(out, fp, indent=1)

	print('cjk.run_family_bands: {} glyphs measured -> {}'.format(processed, fname))
	return fname


# =====================================================================
# - Whole-font runner : IDC split zones -------------------------------
# =====================================================================
def run_idc_zones(idc_lookup, layer=None, names=None, S=64, progress_every=500):
	'''Measure structural ⿰/⿱ split zones for the current font (was idc_zones.run).

	idc_lookup(pglyph, glyph_name) -> top-level IDC char or None. This is the ONLY
	seam to the caller's IDS/CHISE database; this module stays free of it. Return
	any IDC in cjk.IDC_SET; only ⿰/⿱ are measured (others are counted for coverage).

	layer  - master/layer name (str) or None for each glyph's active layer.
	names  - iterable of glyph names to restrict to, or None for all glyphs.
	Writes <fontname>-idc-zones.json beside the font and returns its path.
	'''
	font = pFont()
	if font is None or font.fg is None:
		print('cjk.run_idc_zones: no current font.')
		return None

	all_names = list(names) if names is not None else [g.name for g in font.fg.glyphs]
	total = len(all_names)
	print('cjk.run_idc_zones: {} glyphs, layer={}, S={}'.format(
		total, layer if layer else '<active>', S))

	present = {}					# idc -> count seen
	ratios  = {idc: [] for idc in cjk.MEASURABLE_IDC}
	n_with_ids = 0

	for i, gname in enumerate(all_names):
		if i % progress_every == 0:
			print('  ... {}/{}'.format(i, total))
		try:
			pg = font.glyph(gname)
			lyr = pg.layer(layer) if layer is not None else pg.activeLayer()
			if lyr is None:
				continue
			idc = idc_lookup(pg, gname)
			if idc is None:
				continue
			n_with_ids += 1
			present[idc] = present.get(idc, 0) + 1
			if idc not in cjk.MEASURABLE_IDC:
				continue
			ratio = measure_split(pg, lyr, idc, S)
			if ratio is not None:
				ratios[idc].append(ratio)
		except Exception as e:
			print('  ! {} - {}'.format(gname, e))
			continue

	structures = {}
	for idc in sorted(present, key=lambda k: -present[k]):
		entry = {'present': present[idc]}
		if idc in cjk.MEASURABLE_IDC:
			red = cjk.reduce_ratios(ratios[idc])
			if red is not None:
				entry.update(red)
				entry['coverage'] = red['measured'] / float(present[idc])
			else:
				entry['measured'] = 0
		structures[idc] = entry

	out = {
		'font':       font.name,
		'source':     'idc-zones',
		'layer':      layer if layer else '<active>',
		'raster_S':   S,
		'n_glyphs':   total,
		'n_with_ids': n_with_ids,
		'measurable': list(cjk.MEASURABLE_IDC),
		'structures': structures,
	}

	fname = os.path.join(_font_dir(font) or os.getcwd(),
						 '{}-idc-zones.json'.format(_safe_name(font.name)))
	with open(fname, 'w') as fp:
		json.dump(out, fp, indent=1)

	print('cjk.run_idc_zones: {} glyphs with IDS -> {}'.format(n_with_ids, fname))
	return fname
