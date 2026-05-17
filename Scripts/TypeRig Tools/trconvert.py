#!/usr/bin/env python
# MODULE: TypeRig / Tools / trconvert
# NOTE: CLI converter between .trfont and UFO 3.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
# ----------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# Pure-Python CLI: ufo2tr, tr2ufo, roundtrip.
# Requires fontTools (UFO and designspace support).
#
#   python trconvert.py ufo2tr input.ufo output.trfont [--verbose]
#   python trconvert.py tr2ufo input.trfont output.ufo [--verbose]
#   python trconvert.py roundtrip input.trfont|input.ufo [--keep-tmp]
#
# `roundtrip` runs both directions on a temporary copy and prints
# PASS / FAIL with a structural diff summary; exit code is non-zero
# on failure.

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division

import argparse
import os
import shutil
import sys
import tempfile

# Wire the lib path when run from inside the repo (no install needed)
HERE = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.normpath(os.path.join(HERE, '..', '..', 'Lib'))
if os.path.isdir(LIB_PATH) and LIB_PATH not in sys.path:
	sys.path.insert(0, LIB_PATH)

from typerig.core.fileio.trfont import TrFontIO
from typerig.core.fileio.ufo import UfoConverter


# - Diff helpers ------------------------
def _num(v):
	'''Normalize a value for comparison — coerce all numerics to float.'''
	if isinstance(v, bool):
		return v
	if isinstance(v, (int, float)):
		return float(v)
	return v


def _guide_key(g):
	return (_num(g.x), _num(g.y), _num(g.angle), g.name or '')


def _layer_signature(layer):
	'''Compact comparable structure for a TR layer. Closed flag is not
	included because TR<->UFO loses it for contours without a 'move' point —
	UFO open contours are signalled by a leading 'move' segment, not by a flag.
	'''
	shapes = []
	for shape in layer.shapes:
		if shape.is_component:
			t = shape.transform
			try:
				tx = round(float(t[4]), 3)
				ty = round(float(t[5]), 3)
			except (TypeError, IndexError):
				tx = ty = 0.0
			shapes.append(('component', shape.component, tx, ty))
			continue

		contour_data = []
		for contour in shape.contours:
			nodes = tuple(
				(round(float(n.x), 3), round(float(n.y), 3), n.type)
				for n in contour.nodes
			)
			contour_data.append(nodes)
		shapes.append(('outline', tuple(contour_data)))

	anchors = tuple(sorted(
		(round(float(a.x), 3), round(float(a.y), 3), a.name or '')
		for a in layer.anchors
	))

	return {
		'name':    layer.name,
		'width':   _num(layer.advance_width),
		'height':  _num(layer.advance_height),
		'shapes':  tuple(shapes),
		'anchors': anchors,
	}


def _glyph_signature(glyph):
	# UFO has no glyph-vs-layer guideline distinction — all guidelines live
	# in .glif files. Combine glyph-level + every-layer guidelines into one
	# sorted set so the round-trip is comparable.
	all_guides = set(_guide_key(g) for g in (glyph.guidelines or []))
	for l in glyph.layers:
		for g in l.guidelines:
			all_guides.add(_guide_key(g))

	return {
		'name':       glyph.name,
		'unicodes':   tuple(sorted(int(u) for u in (glyph.unicodes or []))),
		'note':       (glyph.note or '').strip(),
		'mark':       (glyph.mark or '').upper(),
		'guidelines': tuple(sorted(all_guides, key=lambda x: tuple(str(v) for v in x))),
		'layers':     {l.name: _layer_signature(l) for l in glyph.layers},
	}


def _font_signature(font):
	groups = {g.name: tuple(g.members) for g in font.groups.data}
	kern = sorted((p.first, p.second, int(p.value)) for p in font.kerning.pairs)

	info_fields = {}
	for tr_attr in FontInfo_attr_iter():
		val = getattr(font.info, tr_attr, None)
		if val not in (None, ''):
			info_fields[tr_attr] = _num(val)

	metrics = {
		'upm':        _num(font.metrics.upm),
		'ascender':   _num(font.metrics.ascender),
		'descender':  _num(font.metrics.descender),
		'x_height':   _num(font.metrics.x_height),
		'cap_height': _num(font.metrics.cap_height),
		'line_gap':   _num(font.metrics.line_gap),
	}

	axes = tuple((a.name, a.tag, _num(a.minimum), _num(a.default), _num(a.maximum))
	             for a in font.axes)

	# Masters: is_default is a TR convention not preserved through UFO
	# designspace except when it coincides with axis defaults. Don't include.
	masters = tuple(
		(m.name, m.layer_name,
		 tuple(sorted((k, _num(v)) for k, v in m.location.items())))
		for m in font.masters.data
	)

	instances = tuple(
		(i.name, tuple(sorted((k, _num(v)) for k, v in i.location.items())))
		for i in font.instances.data
	)

	return {
		'info':      info_fields,
		'metrics':   metrics,
		'axes':      axes,
		'masters':   masters,
		'instances': instances,
		'groups':    {k: tuple(sorted(v)) for k, v in groups.items()},
		'kerning':   tuple(kern),
		'features':  (font.features or '').strip(),
		'glyphs':    [_glyph_signature(g) for g in font.glyphs],
	}


def FontInfo_attr_iter():
	from typerig.core.objects.font import FontInfo
	for attr in FontInfo.__slots__:
		if attr in ('identifier', 'parent', 'lib'):
			continue
		yield attr


def _diff(a, b, path='', diffs=None):
	if diffs is None:
		diffs = []

	if type(a) != type(b):
		diffs.append('{}: type mismatch {} vs {}'.format(path, type(a).__name__, type(b).__name__))
		return diffs

	if isinstance(a, dict):
		keys = set(a) | set(b)
		for k in sorted(keys, key=str):
			sub = '{}.{}'.format(path, k) if path else str(k)
			if k not in a:
				diffs.append('{}: only in B'.format(sub))
			elif k not in b:
				diffs.append('{}: only in A'.format(sub))
			else:
				_diff(a[k], b[k], sub, diffs)

	elif isinstance(a, (list, tuple)):
		if len(a) != len(b):
			diffs.append('{}: length mismatch {} vs {}'.format(path, len(a), len(b)))
			return diffs
		for i, (x, y) in enumerate(zip(a, b)):
			_diff(x, y, '{}[{}]'.format(path, i), diffs)

	else:
		if a != b:
			diffs.append('{}: {!r} vs {!r}'.format(path, a, b))

	return diffs


# - Commands ----------------------------
def cmd_ufo2tr(args):
	converter = UfoConverter(verbose=args.verbose)
	font = converter.to_tr(args.input)
	TrFontIO.write(font, args.output)
	if args.verbose:
		print('Wrote: {}'.format(args.output))
	return 0


def cmd_tr2ufo(args):
	font = TrFontIO.read(args.input)
	converter = UfoConverter(verbose=args.verbose)
	out_path = converter.to_ufo(font, args.output)
	if args.verbose:
		print('Wrote: {}'.format(out_path))
		# If we wrote to .ufo, the sibling .designspace is informational
		if args.output.lower().endswith('.ufo'):
			ds = os.path.splitext(args.output)[0] + '.designspace'
			if os.path.isfile(ds):
				print('Wrote: {}'.format(ds))
		# If we wrote to .designspace, list its sibling UFOs
		elif args.output.lower().endswith('.designspace'):
			ds_dir = os.path.dirname(os.path.abspath(args.output))
			stem   = os.path.splitext(os.path.basename(args.output))[0]
			for entry in sorted(os.listdir(ds_dir)):
				if entry.startswith(stem + '-') and entry.endswith('.ufo'):
					print('Wrote: {}'.format(os.path.join(ds_dir, entry)))
	return 0


def cmd_roundtrip(args):
	src = args.input
	src_low = src.rstrip(os.sep).lower()

	tmp = tempfile.mkdtemp(prefix='trconvert_')

	try:
		converter = UfoConverter(verbose=args.verbose)

		def _is_trfont(p):
			return p.lower().endswith('.trfont') or os.path.isfile(os.path.join(p, 'font.xml'))

		def _is_designspace(p):
			return p.lower().endswith('.designspace') and os.path.isfile(p)

		def _is_ufo(p):
			return p.lower().endswith('.ufo') or os.path.isfile(os.path.join(p, 'metainfo.plist'))

		if _is_trfont(src):
			# trfont → designspace + UFOs → trfont
			original = TrFontIO.read(src)

			ds_path = os.path.join(tmp, 'mid.designspace')
			converter.to_ufo(original, ds_path)

			back = converter.to_tr(ds_path)

		elif _is_designspace(src):
			# designspace → trfont → designspace
			original = converter.to_tr(src)

			tr_path = os.path.join(tmp, 'mid.trfont')
			TrFontIO.write(original, tr_path)

			reread = TrFontIO.read(tr_path)
			ds_back = os.path.join(tmp, 'back.designspace')
			converter.to_ufo(reread, ds_back)
			back = converter.to_tr(ds_back)

		elif _is_ufo(src):
			# Single-UFO → trfont → ufo
			original = converter.to_tr(src)

			tr_path = os.path.join(tmp, 'mid.trfont')
			TrFontIO.write(original, tr_path)

			reread = TrFontIO.read(tr_path)
			ufo_back = os.path.join(tmp, 'back.ufo')
			converter.tr_to_ufo(reread, ufo_back)
			back = converter.ufo_to_tr(ufo_back)

		else:
			print('roundtrip: unknown input format: {}'.format(src), file=sys.stderr)
			return 2

		sig_a = _font_signature(original)
		sig_b = _font_signature(back)
		diffs = _diff(sig_a, sig_b)

		# Case-insensitive filesystem regression: glyph names that differ
		# only by case (e.g. 'A' and 'a') must both survive the round-trip
		# with distinct content. Before the filename mangler in TrFontIO,
		# the second write clobbered the first on NTFS/APFS.
		case_diffs = _case_collision_check(original, back)
		diffs.extend(case_diffs)

		# Filter known-lossy fields that the format intentionally does not
		# preserve verbatim through the inverse trip (e.g. version padding).
		filtered = [d for d in diffs if not _is_known_lossy(d)]

		if not filtered:
			print('PASS')
			return 0

		print('FAIL: {} structural differences'.format(len(filtered)))
		for d in filtered[:30]:
			print('  - {}'.format(d))
		if len(filtered) > 30:
			print('  ... {} more'.format(len(filtered) - 30))
		return 1

	finally:
		if args.keep_tmp:
			print('Kept temp dir: {}'.format(tmp))
		else:
			shutil.rmtree(tmp, ignore_errors=True)


def _case_collision_check(original, back):
	'''Verify that glyph-name pairs differing only by case survive
	the round-trip with distinct content on both sides.'''
	diffs = []
	by_lower = {}
	for g in original.glyphs:
		by_lower.setdefault(g.name.lower(), []).append(g.name)

	back_by_name = {g.name: g for g in back.glyphs}
	for lower, names in by_lower.items():
		if len(names) < 2:
			continue
		sigs = {}
		for n in names:
			if n not in back_by_name:
				diffs.append('case-collision: glyph {!r} lost in round-trip'.format(n))
				continue
			sigs[n] = _glyph_signature(back_by_name[n])
		# Any two surviving siblings must be distinct
		survived = list(sigs.items())
		for i in range(len(survived)):
			for j in range(i + 1, len(survived)):
				ni, si = survived[i]
				nj, sj = survived[j]
				if si == sj:
					diffs.append(
						'case-collision: {!r} and {!r} have identical content after round-trip'
						.format(ni, nj))
	return diffs


_LOSSY_PATTERNS = (
	# UFO loses the original version string formatting, we re-emit '<maj>.<min:03d>'
	'info.version:',
)

def _is_known_lossy(diff_line):
	for pat in _LOSSY_PATTERNS:
		if pat in diff_line:
			return True
	return False


# - Entry point -------------------------
def build_parser():
	p = argparse.ArgumentParser(
		prog='trconvert',
		description='Convert between TypeRig .trfont and UFO 3 packages.',
	)
	subs = p.add_subparsers(dest='cmd', required=True)

	sp = subs.add_parser('ufo2tr', help='UFO 3 / designspace → .trfont')
	sp.add_argument('input',   help='Input .designspace file or .ufo folder')
	sp.add_argument('output',  help='Output .trfont folder')
	sp.add_argument('--verbose', '-v', action='store_true')
	sp.set_defaults(func=cmd_ufo2tr)

	sp = subs.add_parser('tr2ufo', help='.trfont → UFO 3 / designspace')
	sp.add_argument('input',   help='Input .trfont folder')
	sp.add_argument('output',
		help='Output .designspace file (preferred — produces designspace + one UFO per master) or .ufo folder (single-UFO layout)')
	sp.add_argument('--verbose', '-v', action='store_true')
	sp.set_defaults(func=cmd_tr2ufo)

	sp = subs.add_parser('roundtrip',
		help='Round-trip a font through both formats and diff against the original')
	sp.add_argument('input',   help='Input .trfont folder, .designspace file, or .ufo folder')
	sp.add_argument('--keep-tmp', action='store_true',
		help='Do not delete the temporary intermediate folder')
	sp.add_argument('--verbose', '-v', action='store_true')
	sp.set_defaults(func=cmd_roundtrip)

	return p


def main(argv=None):
	parser = build_parser()
	args = parser.parse_args(argv)
	return args.func(args)


if __name__ == '__main__':
	sys.exit(main())
