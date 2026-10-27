# MODULE: TypeRig / IO / Kerning from compiled fonts and UFOs (import sources)
# -----------------------------------------------------------
# Flat glyph-glyph kerning from:
#   - a compiled font (.otf / .ttf): GPOS PairPos lookups of the 'kern'
#     feature, flattened as a shaper applies them: within a lookup the first
#     subtable that covers a pair wins (also with 0; a class subtable covers
#     every second glyph of its first glyphs); lookups add up. No GPOS kern
#     feature: the legacy 'kern' table (format 0). fontTools, imported lazily.
#     A variable font gives its default instance.
#   - a UFO (folder): kerning.plist flattened with its own groups.plist in
#     UFO order (glyph+glyph > glyph+group > group+glyph > group+group).
#     Plain plistlib: no fontTools, so it runs in FontRig too.
# Both return the same dict as fileio/afm.read: {'font_name', 'glyphs'
# (every glyph: the coverage), 'kerning': {(a, b): value}, 'skipped': {}}.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function

import os
import plistlib

__version__ = '0.1.0'

KERN1, KERN2 = 'public.kern1.', 'public.kern2.'


# - Compiled fonts -------------------------------------------------------------
def _value(record):
	return getattr(record, 'XAdvance', 0) or 0 if record is not None else 0


def _pairpos_subtables(lookup):
	'''PairPos subtables of a lookup (Extension lookups unwrapped).'''
	for sub in lookup.SubTable:
		if lookup.LookupType == 9:
			if sub.ExtensionLookupType != 2:
				continue
			sub = sub.ExtSubTable
		elif lookup.LookupType != 2:
			continue
		yield sub


def _flatten_lookup(lookup, glyph_order):
	'''{(a, b): value} of one PairPos lookup; the first subtable covering a pair wins.'''
	out = {}
	claimed_first = set()		# first glyphs a class subtable took (every second glyph)
	for sub in _pairpos_subtables(lookup):
		coverage = sub.Coverage.glyphs
		if sub.Format == 1:
			for first, pair_set in zip(coverage, sub.PairSet):
				if first in claimed_first:
					continue
				for record in pair_set.PairValueRecord:
					key = (first, record.SecondGlyph)
					if key not in out:
						out[key] = _value(record.Value1)
		elif sub.Format == 2:
			class1 = sub.ClassDef1.classDefs if sub.ClassDef1 else {}
			class2 = sub.ClassDef2.classDefs if sub.ClassDef2 else {}
			by_class2 = {}
			for glyph in glyph_order:
				by_class2.setdefault(class2.get(glyph, 0), []).append(glyph)
			for first in coverage:
				if first in claimed_first:
					continue
				row = sub.Class1Record[class1.get(first, 0)]
				for c2, record in enumerate(row.Class2Record):
					value = _value(record.Value1)
					for second in by_class2.get(c2, []):
						key = (first, second)
						if key not in out and value:
							out[key] = value
						elif key not in out:
							out[key] = 0		# covered with 0: a later subtable must not apply
				claimed_first.add(first)
	return out


def read_font(path):
	'''Flat kerning of a compiled font (.otf / .ttf).'''
	from fontTools.ttLib import TTFont
	font = TTFont(path, lazy=True)
	glyph_order = font.getGlyphOrder()
	out = {'font_name': '', 'glyphs': list(glyph_order), 'kerning': {}, 'skipped': {}}
	try:
		names = font['name']
		name = names.getDebugName(4) or names.getDebugName(6) or ' '.join(
			n for n in (names.getDebugName(1), names.getDebugName(2)) if n)		# full, PostScript, family + style
		out['font_name'] = name or ''
	except Exception:
		pass
	total = {}
	if 'GPOS' in font and font['GPOS'].table.FeatureList is not None:
		gpos = font['GPOS'].table
		indices = set()
		for record in gpos.FeatureList.FeatureRecord:
			if record.FeatureTag == 'kern':
				indices.update(record.Feature.LookupListIndex)
		for index in sorted(indices):
			for pair, value in _flatten_lookup(gpos.LookupList.Lookup[index], glyph_order).items():
				total[pair] = total.get(pair, 0) + value
	if not total and 'kern' in font:
		for table in font['kern'].kernTables:
			for pair, value in getattr(table, 'kernTable', {}).items():
				total[tuple(pair)] = total.get(tuple(pair), 0) + value
	out['kerning'] = {pair: value for pair, value in total.items() if value}
	font.close()
	return out


# - UFO --------------------------------------------------------------------------------
def _plist(path):
	if not os.path.exists(path):
		return {}
	with open(path, 'rb') as f:
		return plistlib.load(f)


def read_ufo(path):
	'''Flat kerning of a UFO folder, through its own groups.'''
	from typerig.core.algo.kern_model import KernSet, LEFT, RIGHT
	kerning = _plist(os.path.join(path, 'kerning.plist'))
	groups = _plist(os.path.join(path, 'groups.plist'))
	layers = _plist(os.path.join(path, 'layercontents.plist')) or [['public.default', 'glyphs']]
	glyph_dir = dict((n, d) for n, d in layers).get('public.default', 'glyphs')
	contents = _plist(os.path.join(path, glyph_dir, 'contents.plist'))
	info = _plist(os.path.join(path, 'fontinfo.plist'))
	kset_groups = {LEFT: {}, RIGHT: {}}
	for name, members in groups.items():
		if name.startswith(KERN1):
			kset_groups[LEFT][name[len(KERN1):]] = list(members)
		elif name.startswith(KERN2):
			kset_groups[RIGHT][name[len(KERN2):]] = list(members)

	def key(k, prefix):
		return '@' + k[len(prefix):] if k.startswith(prefix) else k

	table = {}
	for first, rights in kerning.items():
		for second, value in rights.items():
			table[(key(first, KERN1), key(second, KERN2))] = value
	kset = KernSet(['ufo'], pairs={'ufo': table}, groups=kset_groups)
	name = ' '.join(str(info.get(k) or '') for k in ('familyName', 'styleName')).strip()
	return {'font_name': name, 'glyphs': list(contents) or None,
	        'kerning': kset.flatten('ufo'), 'skipped': {}}
