# MODULE: TypeRig / IO / TrFont — round-trip regression tests
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# Pure-core gate for the .trfont round trip. No FontLab, no pytest.
# Run with: python test_trfont.py
# Builds a synthetic 2-master font in code, writes it, reads it back,
# writes again, and checks:
#   - the dump (trfont_audit schema) of source and read-back are equal,
#   - the two written folders are XML-identical (idempotence),
#   - package hygiene (portable manifest paths, metainfo).
#
# XFAIL lists checks that are known to fail, each tied to a handout task.
# An XFAIL that starts passing is reported as XPASS so the list is pruned.
# Plan: Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md

# - Dependencies ------------------------
import os
import sys
import shutil
import tempfile

# - Path bootstrap (repo checkout without install) ---
try:
	import typerig.core
except ImportError:
	_LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
	sys.path.insert(0, _LIB_DIR)

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.anchor import Anchor
from typerig.core.objects.guideline import Guideline
from typerig.core.objects.transform import Transform
from typerig.core.objects.font import Font, FontInfo, FontMetrics
from typerig.core.objects.axis import Axis
from typerig.core.objects.master import Master, Masters
from typerig.core.objects.instance import Instance, Instances
from typerig.core.objects.encoding import Encoding
from typerig.core.objects.kern import Kerning
from typerig.core.objects.groups import Groups

from typerig.core.fileio.trfont import TrFontIO, GlyphManifest, FILE_GLYPHS, FILE_META
from typerig.core.fileio.trfont_audit import dump_font, diff, xml_dir_diff

# - Init -------------------------------
__version__ = '0.1.0'

# Known failures: check name -> handout task that fixes it.
XFAIL = {
}

# - Harness ----------------------------
fails, xfails, xpasses, total = [], [], [], [0]

def check(name, ok, detail=None):
	total[0] += 1
	if name in XFAIL:
		if ok:
			xpasses.append(name)
			print('XPASS  {}  (remove from XFAIL: {})'.format(name, XFAIL[name]))
		else:
			xfails.append(name)
			print('XFAIL  {}  [{}]'.format(name, XFAIL[name]))
		return
	print('{}  {}'.format('PASS' if ok else 'FAIL', name))
	if not ok:
		fails.append(name)
		for line in (detail or [])[:12]:
			print('         ' + line)

# - Synthetic font ----------------------
def _box(x0, y0, x1, y1):
	return Contour([Node(x0, y0, type='on'), Node(x1, y0, type='on'),
	                Node(x1, y1, type='on'), Node(x0, y1, type='on')], closed=True)

def _bowl(dx=0):
	'''Closed curve contour with smooth on-curves (exercises type + smooth).'''
	return Contour([
		Node(100+dx, 0,   type='on', smooth=True, name='hr00'),
		Node(155+dx, 0,   type='curve'), Node(200+dx, 45,  type='curve'),
		Node(200+dx, 100, type='on', smooth=True),
		Node(200+dx, 155, type='curve'), Node(155+dx, 200, type='curve'),
		Node(100+dx, 200, type='on', smooth=True),
		Node(45+dx,  200, type='curve'), Node(0+dx,   155, type='curve'),
		Node(0+dx,   100, type='on', smooth=True),
		Node(0+dx,   45,  type='curve'), Node(45+dx,  0,   type='curve'),
	], closed=True)

def _layer(name, width, shapes, anchors=(), guides=()):
	return Layer(shapes, name=name, width=width,
	             anchors=[Anchor(x, y, name=n) for n, x, y in anchors],
	             guidelines=[Guideline(x=x, y=y, angle=a, name=n) for x, y, a, n in guides])

def build_font():
	A = Glyph([
		_layer('Light', 560, [Shape([_box(0, 0, 40, 700), _box(520, 0, 560, 700)], name='A')],
		       anchors=[('top', 280, 700)], guides=[(0, 350, 0, 'mid')]),
		_layer('Bold', 620, [Shape([_box(0, 0, 120, 700), _box(500, 0, 620, 700)], name='A')],
		       anchors=[('top', 310, 700)], guides=[(0, 350, 0, 'mid')]),
	], name='A', unicodes=[0x41], mark='#FF3B30', note='Two stems.\nSecond line.')

	acute = Glyph([
		_layer('Light', 200, [Shape([_box(60, 550, 140, 700)], name='acute')]),
		_layer('Bold', 220, [Shape([_box(50, 550, 170, 700)], name='acute')]),
	], name='acute', unicodes=[0xB4])

	# Element reference written as outline + placement (Stage A model):
	# acute shape in element space, moved by a translate transform.
	Aacute = Glyph([
		_layer('Bold', 620, [Shape([_box(0, 0, 120, 700), _box(500, 0, 620, 700)], name='A'),
		                     Shape([_box(50, 550, 170, 700)], name='acute', transform=Transform(1, 0, 0, 1, 308, 190))]),
		_layer('Light', 560, [Shape([_box(0, 0, 40, 700), _box(520, 0, 560, 700)], name='A'),
		                      Shape([_box(60, 550, 140, 700)], name='acute', transform=Transform(1, 0, 0, 1, 280, 180))]),
	], name='Aacute', unicodes=[0xC1])

	o = Glyph([
		_layer('Light', 220, [Shape([_bowl()])]),
		_layer('Bold', 260, [Shape([_bowl(20)])]),
	], name='o', unicodes=[0x6F])

	# Case-colliding name with 'A' (filename mangling) and an empty glyph.
	a = Glyph([_layer('Light', 500, []), _layer('Bold', 540, [])], name='a', unicodes=[0x61])
	space = Glyph([_layer('Light', 250, []), _layer('Bold', 260, [])], name='space', unicodes=[0x20])
	# Names that a type-guessing XML reader would turn into float/int/bool
	tricky = [Glyph([_layer('Light', 500, []), _layer('Bold', 500, [])], name=n) for n in ('infinity', 'nan', 'no', '1')]

	encoding = Encoding()
	for g in (A, acute, Aacute, o, a, space):
		encoding.set(g.name, *g.unicodes)

	kern_light = Kerning(); kern_light.add_pair('A', 'V', -50); kern_light.add_pair('public.kern1.A', 'public.kern2.O', -20)
	kern_bold  = Kerning(); kern_bold.add_pair('A', 'V', -70);  kern_bold.add_pair('public.kern1.A', 'public.kern2.O', -30)

	groups = Groups()
	groups.set('public.kern1.A', ['A', 'Aacute'])
	groups.set('public.kern2.O', ['o'])

	info = FontInfo('Synth', 'Light', designer='TR Test', copyright='(C) nobody',
	                version='1.002', weight_class=300, italic_angle=0)
	# Extra font-info fields (UFO names) with their real types, as FL hands them over
	info.lib = {'openTypeOS2Panose': [2, 0, 5, 3, 0, 0, 0, 0, 0, 0], 'openTypeOS2Selection': [7],
	            'postscriptBlueScale': 0.048, 'openTypeHheaAscender': 926.0,
	            'openTypeOS2VendorID': 'KRND', 'postscriptIsFixedPitch': False}

	font = Font([A, acute, Aacute, o, a, space] + tricky,
		info      = info,
		metrics   = FontMetrics(1000, 674, -174, 450, 674, 200),
		axes      = [Axis('weight', 'wght', 0, 0, 1000, short_name='wt',
		                  design_minimum=20, design_default=20, design_maximum=180,
		                  map=[(0, 20), (500, 90), (1000, 180)]),
		             Axis('width', 'wdth', 75, 100, 100)],
		masters   = Masters([
			Master('Light', 'Light', {'weight': 0, 'width': 100}, is_default=True,
			       metrics=FontMetrics(1000, 674, -174, 450, 674, 200)),
			Master('Bold',  'Bold',  {'weight': 1000, 'width': 100},
			       metrics=FontMetrics(1000, 674, -184, 477.5, 674, 200)),
		]),
		instances = Instances([
			Instance('Light',  location={'weight': 0,   'width': 100}),
			Instance('Medium', location={'weight': 500, 'width': 100}),
		]),
		encoding  = encoding,
		kerning   = kern_light,
		master_kerning = {'Bold': kern_bold},
		groups    = groups,
		features  = 'languagesystem DFLT dflt;\r\n\r\nfeature kern {\r\n\tpos A V -50; # <&>\r\n} kern;\r\n',
	)
	return font

# - Run --------------------------------
tmp = tempfile.mkdtemp(prefix='trfont_test_')
try:
	src = build_font()
	path_1 = os.path.join(tmp, 'one.trfont')
	path_2 = os.path.join(tmp, 'two.trfont')

	TrFontIO.write(src, path_1)
	back = TrFontIO.read(path_1)
	TrFontIO.write(back, path_2)
	again = TrFontIO.read(path_2)

	# -- 1. Object round trip, per stage field set
	for stage in ('a', 'b'):
		d = diff(dump_font(src, stage), dump_font(back, stage))
		check('dump stage {}: source == read-back'.format(stage), not d, d)

	# Narrow checks, so a regression names its field instead of hiding in the bulk diff
	ds, db = dump_font(src, 'b'), dump_font(back, 'b')
	for key in ('upm', 'metrics', 'info', 'axes', 'masters', 'instances', 'glyph_order', 'kerning', 'groups', 'features'):
		d = diff(ds[key], db[key])
		check('field {}'.format(key), not d, d)

	for gname in ds['glyphs']:
		gs, gb = ds['glyphs'][gname], db['glyphs'].get(gname, {})
		for key in ('unicodes', 'mark', 'note', 'layers'):
			d = diff(gs.get(key), gb.get(key))
			check('glyph {} {}'.format(gname, key), not d, d)

	# -- 2. Second generation is stable
	d = diff(dump_font(back, 'b'), dump_font(again, 'b'))
	check('dump stable across two read/write generations', not d, d)

	d = xml_dir_diff(path_1, path_2)
	check('written folders XML-identical (idempotence)', not d, d)

	# -- 3. Package hygiene
	with open(os.path.join(path_1, FILE_GLYPHS), encoding='utf-8') as fh:
		manifest = fh.read()
	check('manifest paths use "/" (portable Windows <-> macOS)', '\\' not in manifest)
	check('metainfo.xml written', os.path.isfile(os.path.join(path_1, FILE_META)))
	check('glyph names read back as str (infinity, nan, no, 1)',
		all(isinstance(g.name, str) for g in back.glyphs) and back.glyph('infinity') is not None,
		[repr(g.name) for g in back.glyphs if not isinstance(g.name, str)])
	check('case-colliding names "A"/"a" get distinct files',
		len(os.listdir(os.path.join(path_1, 'glyphs'))) == len(src))

	# A manifest written on Windows ("glyphs\\A.trglyph") must still load elsewhere.
	legacy = os.path.join(tmp, 'legacy.trfont')
	shutil.copytree(path_1, legacy)
	gpath = os.path.join(legacy, FILE_GLYPHS)
	with open(gpath, encoding='utf-8') as fh:
		text = fh.read()
	with open(gpath, 'w', encoding='utf-8') as fh:
		fh.write(text.replace('src="glyphs/', 'src="glyphs\\'))
	legacy_font = TrFontIO.read(legacy)
	check('backslash manifest (written on Windows) loads every glyph',
		all(len(g.layers) for g in legacy_font.glyphs))
	# On Windows the OS would accept "\\" anyway; prove the reader normalizes,
	# which is what makes the same package load on macOS.
	check('backslash manifest paths normalized to "/" on read',
		all('\\' not in e.path for e in GlyphManifest.read(gpath).entries))

	# File-name mangling: local copy must match fontTools (when installed)
	from typerig.core.fileio.trfont import user_name_to_file_name
	_corpus = ['A', 'a', 'A.sc', 'Aacute', '.notdef', 'con', 'CON.alt', 'aux.ss01', 'com1',
	           'a/b', 'x"y*z', 'f_f_i', 'Ω', 'uni4E00', 'T' * 300, 'tab\there', 'a:b']
	try:
		from fontTools.ufoLib.filenames import userNameToFileName as _ft
	except ImportError:
		_ft = None
	if _ft is None:
		print('SKIP   filename mangling vs fontTools (fontTools not installed)')
	else:
		_mine, _theirs, _seen_m, _seen_t = [], [], set(), set()
		for _n in _corpus + ['a', 'A', 'A.sc']:		# repeats force the clash counter
			_m = user_name_to_file_name(_n, existing=_seen_m, suffix='.trglyph'); _seen_m.add(_m.lower())
			_t = _ft(_n, existing=_seen_t, suffix='.trglyph'); _seen_t.add(_t.lower())
			_mine.append(_m); _theirs.append(_t)
		check('filename mangling matches fontTools on corpus',
			_mine == _theirs, ['{!r}: {!r} != {!r}'.format(n, m, t) for n, m, t in zip(_corpus + ['a', 'A', 'A.sc'], _mine, _theirs) if m != t])

	# Features: one source of truth on disk
	with open(os.path.join(path_1, 'font.xml'), encoding='utf-8') as fh:
		font_xml = fh.read()
	check('features live only in features.fea (not duplicated in font.xml)', '<features' not in font_xml)
finally:
	shutil.rmtree(tmp, ignore_errors=True)

# - Finish -----------------------------
print()
print('{} checks: {} failed, {} xfail, {} xpass'.format(total[0], len(fails), len(xfails), len(xpasses)))
if fails:
	print('FAILED:')
	for name in fails:
		print('  FAIL -', name)
else:
	print('ALL PASS' + (' (with known XFAILs)' if xfails else ''))

sys.exit(1 if (fails or xpasses) else 0)
