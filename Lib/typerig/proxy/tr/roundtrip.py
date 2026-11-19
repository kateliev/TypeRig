# MODULE: TypeRig / Proxy / TR / Round trip driver
# NOTE: VFC -> .trfont -> new FontLab font, plus the gate comparison
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# Long runs (a whole font) exceed the ~5 s limit of the fontlab MCP
# run_python (remopy has the same FontLab-side limit). Run them as a
# FontLab script instead: a .vfpy handed to the running FontLab, e.g.
#     "C:\Program Files\Fontlab\FontLab 9\FontLab 9.exe" build.vfpy
# with build.vfpy containing:
#     from typerig.proxy.tr import roundtrip
#     roundtrip.build(r'D:\work\rt', source_path=r'D:\fonts\My.vfc')
# Each phase writes <work_dir>/<phase>.json (result) or <phase>.error.txt.
#
# Phases:
#   build(work_dir, ...)    source package -> rt.trfont -> new FontLab font
#                           (left open; save it as <work_dir>/rt.vfc).
#   compare(work_dir, ...)  source vs the reopened rt.vfc: the GATE diff.
#
# Never open a file that may raise a modal dialog (e.g. "Duplicate Element
# Names") through an MCP call: a pending MCP request during a modal dialog
# crashed FontLab 9.0.9809's local-socket bridge. Open it on the command
# line and answer the dialog there.
# Plan: Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md

# - Dependencies ------------------------
import os
import json
import time
import traceback

import fontlab as fl6

# - Init --------------------------------
__version__ = '0.1.0'

# - Helpers -----------------------------
def packages():
	'''All open fonts as flPackage.'''
	return [fl6.flPackage(o) for o in fl6.flWorkspace.instance().packages()]

def _norm(path):
	return os.path.normcase(os.path.normpath(path or ''))

def package_by_path(path):
	'''The open font whose file is `path`, or None.'''
	want = _norm(path)
	for p in packages():
		if _norm(getattr(p.fgPackage, 'path', '')) == want:
			return p
	return None

def _write_json(work_dir, name, data):
	with open(os.path.join(work_dir, name + '.json'), 'w', encoding='utf-8') as fh:
		json.dump(data, fh, indent=1, sort_keys=True, default=str)

def _phase(work_dir, name, fn):
	'''Run fn(); write <name>.json or <name>.error.txt. Never raises.'''
	for suffix in ('.json', '.error.txt'):
		stale = os.path.join(work_dir, name + suffix)
		if os.path.exists(stale):
			os.remove(stale)
	try:
		_write_json(work_dir, name, fn())
	except Exception:
		with open(os.path.join(work_dir, name + '.error.txt'), 'w', encoding='utf-8') as fh:
			fh.write(traceback.format_exc())

# - Phases ------------------------------
def build(work_dir, source_path=None, glyph_names=None, include_features=False,
          include_kerning=False, include_groups=False, reload=True):
	'''Eject the source font to <work_dir>/rt.trfont and build a new font from it.'''
	os.makedirs(work_dir, exist_ok=True)

	def run():
		if reload:
			from typerig.proxy.tr import audit
			audit.reload_typerig()
		from typerig.proxy.tr.objects.font import trFontProxy
		from typerig.core.fileio.trfont import TrFontIO

		src = package_by_path(source_path) if source_path else fl6.flPackage(fl6.CurrentFont())
		if src is None:
			raise ValueError('source font not open: {}'.format(source_path))

		t0 = time.time()
		path = os.path.join(work_dir, 'rt.trfont')
		proxy = trFontProxy(src)
		proxy.save(path, glyph_names=glyph_names, include_features=include_features,
		           include_kerning=include_kerning, include_groups=include_groups)
		t1 = time.time()
		font = TrFontIO.read(path)
		t2 = time.time()
		new = trFontProxy.create_font(font, include_features=include_features,
		                              include_kerning=include_kerning, include_groups=include_groups,
		                              step_log=os.path.join(work_dir, 'build.step.log'))
		t3 = time.time()
		return {
			'source': getattr(src.fgPackage, 'path', ''),
			'glyphs': len(font),
			'masters': [m.name for m in font.masters.data],
			'eject_problems': list(getattr(proxy, 'problems', []) or []),
			'build_problems': list(new.problems),
			'seconds': {'eject_write': round(t1 - t0, 2), 'read': round(t2 - t1, 2), 'create_font': round(t3 - t2, 2)},
		}

	_phase(work_dir, 'build', run)

def compare(work_dir, source_path, rebuilt_path=None, stage='a', glyph_names=None, limit=2000):
	'''GATE: dump source and rebuilt fonts (both read from FontLab) and diff.'''
	os.makedirs(work_dir, exist_ok=True)
	rebuilt_path = rebuilt_path or os.path.join(work_dir, 'rt.vfc')

	def run():
		from typerig.proxy.tr import audit
		from typerig.core.fileio.trfont_audit import summarize

		src = package_by_path(source_path)
		new = package_by_path(rebuilt_path)
		if src is None or new is None:
			raise ValueError('not open: {}'.format([p for p, q in ((source_path, src), (rebuilt_path, new)) if q is None]))

		t0 = time.time()
		a = audit._jsonable(audit.dump_fl(src, stage, glyph_names))
		b = audit._jsonable(audit.dump_fl(new, stage, glyph_names))
		if glyph_names is not None:
			a.pop('glyph_order', None); b.pop('glyph_order', None)
		lines = audit.diff(a, b, limit=limit)
		# Glyph-order lines can be hundreds long for one moved glyph: list the
		# others first so the report shows what matters.
		lines = [l for l in lines if not l.startswith('$.glyph_order')] + 		        [l for l in lines if l.startswith('$.glyph_order')]
		return {
			'stage': stage,
			'glyphs_compared': len(a.get('glyphs', {})),
			'diff_lines': len(lines),
			'summary': summarize(lines),
			'first_lines': lines[:200],
			'seconds': round(time.time() - t0, 2),
		}

	_phase(work_dir, 'compare', run)
