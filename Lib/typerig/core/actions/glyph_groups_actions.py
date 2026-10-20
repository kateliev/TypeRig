# MODULE: TypeRig / Core / Actions / Glyph groups
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020-2026	(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
# ----------------------------------------------------------
'''Glyph groups: auto sort, export for an agent, import with a coverage check.

Delta Machine groups (Uppercase, Lowercase, Small caps, ...) decide which
target settings a glyph gets. A glyph in no group is never baked by a
named row, so every operation here accounts for every glyph of the font:

	auto_groups(records)            every glyph into one group by its Glyphs
	                                category / case / name suffix; the rest
	                                into Uncategorized
	groups_export(records, groups)  the groups + Uncategorized (glyphs in no
	                                group) + a read-only glyph table (Unicode,
	                                character, category, case, script,
	                                components, OpenType features / classes,
	                                auto group) + instructions for an agent
	                                that sorts them by name; groups_dump()
	                                writes it one glyph per line
	groups_import(raw, font_names)  groups back from that file (or a plain
	                                {group: [names]}); names not in the font
	                                are dropped, font glyphs the file misses
	                                go to Uncategorized; a report says so

Glyph records are host neutral dicts (the host fills them, Glyphs:
gs3/gui/glyph_filters.glyph_record):
	{'name', 'unicodes': ['0061'], 'category', 'subCategory', 'case',
	 'script', 'export', 'shape': outline | composite | mixed | empty,
	 'components': [names]}
Missing keys are empty.
'''

from __future__ import absolute_import, print_function, unicode_literals

import json
import re

# - Init -------------------------------------------------------------------
FORMAT        = 'typerig-glyph-groups/1'
UNCATEGORIZED = 'Uncategorized'
RESERVED      = ('Selection',)		# Delta Machine: rows without a group (dma.SELECTION_LABEL)

SMALLCAP_SUFFIXES = ('.sc', '.smcp', '.c2sc')
MINOR_SUFFIXES    = ('.sups', '.subs', '.sinf', '.numr', '.dnom', '.superior', '.inferior')
CASES             = ('Uppercase', 'Lowercase', 'Smallcaps', 'Minor')

# Auto groups, in order: (name, reference glyph candidates, test(record)).
# The first group whose test takes a glyph gets it; the rest: Uncategorized.
def _cat(r):
	return r.get('category') or ''

def _case(r):
	return r.get('case') or ''

def _suffixed(r, suffixes):
	'''A dot suffix of the name is one of suffixes ('a.sc.ss01' has .sc).'''
	parts = (r.get('name') or '').split('.')
	return bool(parts[0]) and any('.' + p in suffixes for p in parts[1:])

AUTO_RULES = (
	('Small caps',  ('h.sc', 'h.smcp', 'H.sc', 'H.c2sc', 'x.sc'),
	                lambda r: _case(r) == 'Smallcaps' or _suffixed(r, SMALLCAP_SUFFIXES)),
	('Sups & subs', (),
	                lambda r: _case(r) == 'Minor' or _suffixed(r, MINOR_SUFFIXES)),
	('Uppercase',   ('H',),  lambda r: _cat(r) == 'Letter' and _case(r) == 'Uppercase'),
	('Lowercase',   ('x',),  lambda r: _cat(r) == 'Letter' and _case(r) == 'Lowercase'),
	('Other letters', (),    lambda r: _cat(r) == 'Letter'),
	('Figures',     (),      lambda r: _cat(r) == 'Number'),
	('Punctuation', (),      lambda r: _cat(r) == 'Punctuation'),
	('Symbols',     (),      lambda r: _cat(r) == 'Symbol'),
	('Marks',       (),      lambda r: _cat(r) == 'Mark'),
)

INSTRUCTIONS = (
	'This file lists every glyph of the font, sorted into TypeRig Delta Machine glyph groups. '
	'A group is a set of glyphs that take the same Delta targets (stems and sizes per layer), '
	'for example Uppercase, Lowercase, Small caps, Figures.',
	'Task: sort the glyphs into groups by their names, helped by glyph_info. Move glyphs out of '
	'Uncategorized where you can; add, split, merge or rename groups when the design needs it.',
	'Edit only "groups". "glyph_info" and "check" are read-only help; the importer ignores them.',
	'No glyph is left behind: every glyph name of the font must be in exactly one group. A glyph '
	'you cannot place stays in Uncategorized. Do not drop, rename or invent glyph names.',
	'Before you return the file, count: the glyphs of all groups together (no name twice) must '
	'equal check.glyphs_in_font. Keep each group\'s "count" right as your own check. The importer checks it again: names not in the font are dropped, '
	'font glyphs missing from the file go to Uncategorized, and the user is told.',
	'A group has a name (unique, not "Selection") and optionally a "reference": one flat glyph of '
	'the group whose stems and heights stand for the group (H for capitals, x for lowercase, h.sc '
	'for small caps). Sizes in units are measured on it. Leave it empty when no glyph fits.',
	'Name hints: alternates (a.ss01, a.alt, a.cv01) follow their base glyph; composites follow their '
	'components (Aacute = A + acutecomb); .sc .smcp .c2sc are small caps; .sups .subs .sinf .numr '
	'.dnom are superiors / inferiors; .tf .lf .osf .tosf are figures; f_i style names are ligatures '
	'of their parts; names starting with _ are component parts (sort them with what uses them).',
)

GLYPH_INFO_KEYS = (	# key in glyph_info: what it is
	('unicode',    'Unicode code points (hex)'),
	('char',       'the character of the first code point'),
	('category',   'Glyphs category / subcategory'),
	('case',       'Glyphs case: Uppercase, Lowercase, Smallcaps, Minor'),
	('script',     'Glyphs script'),
	('shape',      'first master: outline (paths), composite (components), mixed, empty'),
	('components', 'component base glyphs (first master)'),
	('features',   'OpenType features whose code names the glyph (also through a class)'),
	('classes',    'OpenType classes that list the glyph'),
	('not_exported', 'true: the glyph does not export'),
	('auto',       'group the Auto button would give it'),
)


# - Records ----------------------------------------------------------------
def _str(value):
	return '' if value is None else str(value)


def norm_record(record):
	'''A glyph record with every key (host records may miss some).'''
	r = dict(record or {})
	unicodes = r.get('unicodes')
	if not unicodes and r.get('unicode'):
		unicodes = [r.get('unicode')]
	return {
		'name':        _str(r.get('name')),
		'unicodes':    [_str(u).upper() for u in (unicodes or []) if u],
		'category':    _str(r.get('category')),
		'subCategory': _str(r.get('subCategory')),
		'case':        _str(r.get('case')) if r.get('case') in CASES else '',
		'script':      _str(r.get('script')),
		'export':      r.get('export') is not False,
		'shape':       _str(r.get('shape')),
		'components':  [_str(c) for c in (r.get('components') or []) if c],
	}


def _char(code):
	try:
		c = chr(int(code, 16))
	except (TypeError, ValueError, OverflowError):
		return ''
	return c if c.isprintable() and not c.isspace() else ''


# - Auto -------------------------------------------------------------------
def auto_group(record):
	'''Group name the auto sort gives a record (UNCATEGORIZED: none fits).'''
	r = norm_record(record)
	for name, _, test in AUTO_RULES:
		if test(r):
			return name
	return UNCATEGORIZED


def auto_groups(records):
	'''Every glyph into one group, font order kept; empty groups left out.
	Returns [{'name', 'reference', 'glyphs'}], Uncategorized last.'''
	records = [norm_record(r) for r in records]
	names = set(r['name'] for r in records)
	buckets = dict((name, []) for name, _, _ in AUTO_RULES)
	buckets[UNCATEGORIZED] = []
	for r in records:
		if r['name']:
			buckets[auto_group(r)].append(r['name'])
	out = []
	for name, refs, _ in AUTO_RULES + ((UNCATEGORIZED, (), None),):
		glyphs = buckets[name]
		if glyphs:
			ref = next((g for g in refs if g in names and g in glyphs), '')
			out.append({'name': name, 'reference': ref, 'glyphs': glyphs})
	return out


# - OpenType ---------------------------------------------------------------
_COMMENT = re.compile(r'#[^\n]*')
_CLASS_DEF = re.compile(r'@([A-Za-z_][\w.\-]*)\s*=\s*\[([^\]]*)\]')
_SPLIT = re.compile(r"[\s\[\](){};,'<>=\"]+")


def _tokens(code):
	return [t.lstrip('\\') for t in _SPLIT.split(_COMMENT.sub(' ', code or '')) if t]


def ot_index(names, ot):
	'''{glyph: {'features': [tags], 'classes': [names]}} from feature code.

	ot: {'features': [(tag, code)], 'classes': [(name, code)],
	'prefixes': [code]} (any may be missing). A feature that names a class
	(@lc) counts for the glyphs of that class. Best effort: token match,
	not a feature parser.'''
	ot = ot or {}
	names = set(names)
	classes = {}
	for cname, code in ot.get('classes', []) or []:
		classes.setdefault(str(cname).lstrip('@'), set()).update(t for t in _tokens(code) if t in names)
	for code in [c for _, c in ot.get('features', []) or []] + list(ot.get('prefixes', []) or []):
		for cname, body in _CLASS_DEF.findall(_COMMENT.sub(' ', code or '')):
			classes.setdefault(cname, set()).update(t for t in _tokens(body) if t in names)
	out = {}
	for cname, members in classes.items():
		for g in members:
			out.setdefault(g, {'features': [], 'classes': []})['classes'].append('@' + cname)
	for tag, code in ot.get('features', []) or []:
		hit = set()
		for t in _tokens(code):
			if t in names:
				hit.add(t)
			elif t.startswith('@') and t[1:] in classes:
				hit.update(classes[t[1:]])
		for g in hit:
			entry = out.setdefault(g, {'features': [], 'classes': []})
			if tag not in entry['features']:
				entry['features'].append(str(tag))
	for entry in out.values():
		entry['classes'].sort()
	return out


# - Coverage ---------------------------------------------------------------
def coverage(groups, font_names):
	'''How groups cover the font. Returns
	{'glyphs_in_font', 'listed' (font glyphs in some group), 'missing' (font
	 glyphs in no group, font order), 'not_in_font' (names, file order),
	 'in_two_groups' {name: [groups]}, 'ok'}.'''
	font_names = list(font_names)
	in_font = set(font_names)
	where = {}
	not_in_font = []
	for g in groups:
		for name in g.get('glyphs', []):
			if name in in_font:
				seen = where.setdefault(name, [])
				if g['name'] not in seen:
					seen.append(g['name'])
			elif name not in not_in_font:
				not_in_font.append(name)
	missing = [n for n in font_names if n not in where]
	twice = dict((n, gs) for n, gs in where.items() if len(gs) > 1)
	return {'glyphs_in_font': len(font_names), 'listed': len(where), 'missing': missing,
	        'not_in_font': not_in_font, 'in_two_groups': twice,
	        'ok': not missing and not not_in_font and not twice}


def _is_uncategorized(name):
	return (name or '').strip().lower() == UNCATEGORIZED.lower()


def with_uncategorized(groups, font_names):
	'''Groups (font names only) + Uncategorized with every font glyph that
	is in no group (a group named Uncategorized is merged into it).'''
	in_font = set(font_names)
	out, rest = [], []
	for g in groups:
		glyphs = [n for n in g.get('glyphs', []) if n in in_font]
		if _is_uncategorized(g.get('name')):
			rest.extend(n for n in glyphs if n not in rest)
		else:
			out.append(dict(g, glyphs=glyphs))
	listed = set(n for g in out for n in g['glyphs'])
	rest_set = set(rest)
	rest.extend(n for n in font_names if n not in listed and n not in rest_set)
	rest = [n for n in rest if n not in listed]
	out.append({'name': UNCATEGORIZED, 'reference': '', 'glyphs': rest})
	return out


# - Export -----------------------------------------------------------------
def glyph_info(record, ot=None):
	'''Compact read-only row of glyph_info (empty values left out).'''
	r = norm_record(record)
	info = {}
	if r['unicodes']:
		info['unicode'] = ' '.join(r['unicodes'])
		char = _char(r['unicodes'][0])
		if char:
			info['char'] = char
	cat = '/'.join(x for x in (r['category'], r['subCategory']) if x)
	if cat:
		info['category'] = cat
	for key in ('case', 'script', 'shape'):
		if r[key]:
			info[key] = r[key]
	if r['components']:
		info['components'] = r['components']
	ot = ot or {}
	if ot.get('features'):
		info['features'] = ot['features']
	if ot.get('classes'):
		info['classes'] = ot['classes']
	if not r['export']:
		info['not_exported'] = True
	info['auto'] = auto_group(r)
	return info


def groups_export(records, groups, font=None, ot=None):
	'''The export document: groups (+ Uncategorized), glyph_info, check.

	records: glyph records, font order (all glyphs of the font)
	groups:  [{'name', 'reference', 'glyphs', ...}] (Delta Machine groups)
	font:    {'family', 'version', 'file'} (optional)
	ot:      feature / class code for ot_index (optional)'''
	records = [norm_record(r) for r in records]
	names = [r['name'] for r in records]
	full = with_uncategorized(groups, names)
	cov = coverage(groups, names)
	index = ot_index(names, ot)
	doc = {
		'format': FORMAT,
		'instructions': list(INSTRUCTIONS),
		'font': dict(font or {}, glyphs=len(names)),
		'check': {
			'glyphs_in_font': len(names),
			'glyphs_in_file': sum(len(g['glyphs']) for g in full),
			'uncategorized': len(full[-1]['glyphs']),
			'in_two_groups': cov['in_two_groups'],
			'dropped_not_in_font': cov['not_in_font'],
		},
		'glyph_info_keys': dict(GLYPH_INFO_KEYS),
		'groups': [{'name': g['name'], 'reference': g.get('reference', '') or '',
		            'count': len(g['glyphs']), 'glyphs': list(g['glyphs'])} for g in full],
		'glyph_info': dict((r['name'], glyph_info(r, index.get(r['name']))) for r in records),
	}
	return doc


def _wrap(names, indent, width=100):
	lines, line = [], ''
	for n in names:
		item = json.dumps(n, ensure_ascii=False)
		if line and len(line) + len(item) + 2 > width:
			lines.append(line + ',')
			line = item
		else:
			line = line + ', ' + item if line else item
	if line:
		lines.append(line)
	return ('\n' + indent).join(lines)


def groups_dump(doc):
	'''The export as JSON text for people and agents: group glyph lists
	wrapped, one glyph per line in glyph_info. Valid JSON.'''
	j = lambda v: json.dumps(v, ensure_ascii=False)
	out = ['{']
	for key in ('format', 'instructions', 'font', 'check', 'glyph_info_keys'):
		value = json.dumps(doc[key], ensure_ascii=False, indent='\t', sort_keys=False)
		out.append('\t{}: {},'.format(j(key), value.replace('\n', '\n\t')))
	out.append('\t"groups": [')
	for i, g in enumerate(doc['groups']):
		head = '\t\t{{"name": {}, "reference": {}, "count": {}, "glyphs": ['.format(
			j(g['name']), j(g['reference']), g['count'])
		body = _wrap(g['glyphs'], '\t\t\t')
		tail = ']}' + (',' if i < len(doc['groups']) - 1 else '')
		out.append(head + ('\n\t\t\t' + body + '\n\t\t' if body else '') + tail)
	out.append('\t],')
	out.append('\t"glyph_info": {')
	rows = ['\t\t{}: {}'.format(j(name), j(row)) for name, row in doc['glyph_info'].items()]
	out.append(',\n'.join(rows))
	out.append('\t}')
	out.append('}')
	return '\n'.join(out) + '\n'


# - Import -----------------------------------------------------------------
_FENCE = re.compile(r'^\s*```[\w-]*\s*\n|\n\s*```\s*$')


def _parse(raw):
	if isinstance(raw, (dict, list)):
		return raw
	text = _FENCE.sub('', raw.strip()) if isinstance(raw, str) else raw
	return json.loads(text)


def _raw_groups(data):
	'''[(name, reference, [names])] from the export shape, a list of groups,
	or a plain {group: [names]} map.'''
	if isinstance(data, dict) and 'groups' in data:
		data = data['groups']
	if isinstance(data, dict):
		data = [{'name': k, 'glyphs': v} for k, v in data.items()]
	if not isinstance(data, list):
		raise ValueError('no "groups" list in the file')
	out = []
	for g in data:
		if not isinstance(g, dict):
			continue
		glyphs = []
		for n in g.get('glyphs', []) or []:
			if isinstance(n, dict):
				n = n.get('name')
			if n:
				glyphs.append(str(n).strip())
		out.append((str(g.get('name', '') or '').strip(), str(g.get('reference', '') or '').strip(), glyphs))
	return out


def groups_import(raw, font_names):
	'''Groups from an export file (or {group: [names]}), checked against the
	font. Returns (groups, report).

	groups: [{'name', 'reference', 'glyphs'}], file order, font names only,
	        Uncategorized last (only when it has glyphs): what the file put
	        there + font glyphs the file does not list
	report: {'groups', 'glyphs_in_font', 'listed', 'uncategorized',
	         'added_missing', 'not_in_font', 'in_two_groups', 'renamed',
	         'merged', 'bad_reference', 'ok'}'''
	font_names = list(font_names)
	in_font = set(font_names)
	merged, renamed, bad_ref = [], [], []
	by_name, order = {}, []
	for name, ref, glyphs in _raw_groups(_parse(raw)):
		if not name:
			name = 'Group'
		if _is_uncategorized(name):
			name = UNCATEGORIZED
		elif name in RESERVED:
			renamed.append((name, name + ' (imported)'))
			name += ' (imported)'
		if name in by_name:
			merged.append(name)
			g = by_name[name]
			g['glyphs'].extend(n for n in glyphs if n not in g['glyphs'])
			g['reference'] = g['reference'] or ref
		else:
			by_name[name] = {'name': name, 'reference': ref, 'glyphs': []}
			by_name[name]['glyphs'] = [n for i, n in enumerate(glyphs) if n not in glyphs[:i]]
			order.append(name)
	parsed = [by_name[n] for n in order]
	cov = coverage(parsed, font_names)
	groups = with_uncategorized(parsed, font_names)
	for g in groups:
		ref = g['reference']
		if ref and (ref not in in_font or ref not in g['glyphs']):
			bad_ref.append((g['name'], ref, ref in in_font))
			if ref not in in_font:
				g['reference'] = ''
	unc = groups[-1]
	# what the file put into Uncategorized itself (font glyphs only)
	filed = set(n for g in parsed if _is_uncategorized(g['name']) for n in g['glyphs'] if n in in_font)
	if not unc['glyphs']:
		groups.pop()
	report = {
		'groups': len(groups),
		'glyphs_in_font': len(font_names),
		'listed': cov['listed'],
		'uncategorized': len(unc['glyphs']),
		'added_missing': [n for n in unc['glyphs'] if n not in filed],
		'not_in_font': cov['not_in_font'],
		'in_two_groups': cov['in_two_groups'],
		'renamed': renamed,
		'merged': merged,
		'bad_reference': bad_ref,
	}
	covered = set(n for g in groups for n in g['glyphs'])
	report['covered'] = len(covered & in_font)
	report['ok'] = report['covered'] == len(font_names) and not report['added_missing'] \
		and not report['not_in_font'] and not report['in_two_groups']
	return groups, report


def _names(names, limit=12):
	names = list(names)
	text = ' '.join(names[:limit])
	return text + (' … (+{})'.format(len(names) - limit) if len(names) > limit else '')


def report_lines(report):
	'''Report of groups_import as text lines (first line: the summary).'''
	r = report
	lines = ['{} of {} font glyphs in {} group(s), {} uncategorized{}.'.format(
		r['covered'], r['glyphs_in_font'], r['groups'], r['uncategorized'],
		'' if r['covered'] == r['glyphs_in_font'] else ' — COUNT MISMATCH')]
	if r['added_missing']:
		lines.append('{} font glyph(s) were not in the file, put in {}: {}'.format(
			len(r['added_missing']), UNCATEGORIZED, _names(r['added_missing'])))
	if r['not_in_font']:
		lines.append('{} name(s) not in the font, dropped: {}'.format(len(r['not_in_font']), _names(r['not_in_font'])))
	if r['in_two_groups']:
		lines.append('{} glyph(s) in more than one group (kept in each; the first target row wins): {}'.format(
			len(r['in_two_groups']), _names('{} ({})'.format(n, ', '.join(g)) for n, g in r['in_two_groups'].items())))
	for old, new in r['renamed']:
		lines.append('Group "{}" renamed "{}" (reserved name).'.format(old, new))
	if r['merged']:
		lines.append('Groups with the same name merged: {}'.format(', '.join(r['merged'])))
	for name, ref, kept in r['bad_reference']:
		lines.append('Group {}: reference {} is not {}.'.format(
			name, ref, 'in the group (kept)' if kept else 'in the font (cleared)'))
	return lines
