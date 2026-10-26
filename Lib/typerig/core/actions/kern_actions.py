# MODULE: TypeRig / Core / Actions / Kern
# -----------------------------------------------------------
# TR Kern operations. Each one reads a KernSet and returns a ChangeSet
# (core/algo/kern_model.py); the host previews it, snapshots the touched
# masters, then applies. Nothing here talks to an editor.
#
# Import external kerning onto the font's groups:
#   read_source(path)                      AFM / KRN with values -> flat pairs + coverage
#   import_plan(kset, master, flat, ...)   -> (ChangeSet, report)
#   import_files_to_masters(names, masters, strip)  file -> master matching
#   plan_text(...)                         the report shown before / after Apply
# Snapshots (sidecar folder next to the font, user decision 2026-10-26):
#   snapshot_folder / snapshot_write / snapshot_list / snapshot_read
# KernMaster job (KRN pair list + CLA classes, leader first):
#   job_classes(kset), job_pairs_font(kset, master), job_pairs_ab(kset, a, b)
#   compositions (FontRig Kern Job Composer JSON): normalize_blocks,
#   job_pairs_blocks(kset, blocks, ...), job_preview_text(...)
# Font lib (locks, jobs, rule sets, strings settings, group leaders): LIB_KEY, lib_normalize
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import io
import json
import os
from datetime import datetime

from typerig.core.algo import kern_reclass as krc
from typerig.core.algo.kern_model import (ChangeSet, KernSet, LEFT, RIGHT, is_group, group_name,
                                         group_key, to_int)
from typerig.core.fileio import afm, krn

__version__ = '0.4.0'

# - Init -------------------------------------------------------------------
SCOPE_MERGE_CLEAR, SCOPE_REPLACE, SCOPE_MERGE = 'merge_clear', 'replace', 'merge'
SCOPES = ((SCOPE_MERGE_CLEAR, 'Merge + clear stale'), (SCOPE_REPLACE, 'Replace master'), (SCOPE_MERGE, 'Merge'))
SCOPE_DEFAULT = SCOPE_MERGE_CLEAR
FILL_WARNING = .5	# absent = 0 on a source that fills less of its group pairs: warn (partial source?)

LIB_KEY = 'com.typerig.kern'	# font lib: locks, saved jobs
LIB_FORMAT = 1
SNAPSHOT_SUFFIX = '.trkern'		# sidecar folder next to the font: <font file>.trkern/
SOURCE_TYPES = ('afm', 'krn')	# import sources (KRN: only pairs that carry a value)

# KernMaster job: CLA has no sides, so a group gets the side in its name.
# Same convention as the FL Kern Classes auto build (name_1 = 1st / left, name_2 = 2nd / right).
JOB_SIDE_SUFFIX = {LEFT: '_1', RIGHT: '_2'}
JOB_SOURCES = (('blocks', 'Compositions'), ('font', 'Font kerning (pairs as stored)'))
JOB_PREVIEW_LINES = 3000	# preview: KRN lines shown at most (the files hold all)

IMPORT_DEFAULTS = {
	'rule': krc.RULE_DEFAULT,		# key | mode | median
	'tolerance': 0,
	'absent': krc.ABSENT_DEFAULT,	# zero | none
	'scope': SCOPE_DEFAULT,
	'round_to': 0,
	'min_abs': 0,
	'clamp': 0,
}


def import_options(options=None):
	'''Import options with defaults filled and bad values replaced.'''
	opts = dict(IMPORT_DEFAULTS)
	opts.update(options or {})
	if opts['rule'] not in dict(krc.VALUE_RULES):
		opts['rule'] = krc.RULE_DEFAULT
	if opts['absent'] not in dict(krc.ABSENT_RULES):
		opts['absent'] = krc.ABSENT_DEFAULT
	if opts['scope'] not in dict(SCOPES):
		opts['scope'] = SCOPE_DEFAULT
	for key in ('tolerance', 'round_to', 'min_abs', 'clamp'):
		try:
			opts[key] = max(0, int(opts[key] or 0))
		except (TypeError, ValueError):
			opts[key] = 0
	return opts


# - Coverage ---------------------------------------------------------------
def _key_covered(kset, key, side, coverage):
	'''A glyph side is covered when the glyph is; a group side when any member is.'''
	if is_group(key):
		return any(g in coverage for g in kset.groups[side].get(group_name(key), []))
	return key in coverage


# - Import -----------------------------------------------------------------
def import_plan(kset, master, flat, options=None, coverage=None, keys=None):
	'''Plan writing flat external kerning into a master, on the font's groups.

	Args:
		kset (KernSet)   : the font's kerning (groups are read only)
		master (str)     : target master
		flat (dict)      : {(glyph, glyph): value}, names already mapped to the font
		options (dict)   : see IMPORT_DEFAULTS
		coverage (iter)  : glyphs the source knows (AFM CharMetrics); default: glyphs in flat
		keys (dict)      : optional key glyphs per group, see kern_reclass.reclass

	Returns:
		(ChangeSet, report) - report: {'table', 'reclass', 'locked', 'flat', 'coverage', 'options'}
	'''
	opts = import_options(options)
	flat = krc.prefilter(flat, opts['round_to'], opts['min_abs'], opts['clamp'])
	if coverage is None:
		coverage = set(g for pair in flat for g in pair)
	else:
		coverage = set(coverage)

	table, rep = krc.reclass(flat, kset, opts['rule'], opts['tolerance'], opts['absent'], coverage, keys)

	cs = ChangeSet('import %s' % master)
	current = kset.pairs.get(master, {})
	for pair, value in sorted(table.items()):
		cs.set(master, pair, value, kset.locks)

	scope = opts['scope']
	for pair in sorted(current):
		if pair in table:
			continue
		if scope == SCOPE_REPLACE or (scope == SCOPE_MERGE_CLEAR
		        and _key_covered(kset, pair[0], LEFT, coverage)
		        and _key_covered(kset, pair[1], RIGHT, coverage)):
			cs.remove(master, pair, kset.locks)

	kinds = rep['kinds']
	cs.log.append('Import into %s: %d pairs (CC %d, CG %d, GC %d, GG %d) from %d flat pairs, %d buckets'
	              % (master, len(table), kinds['CC'], kinds['CG'], kinds['GC'], kinds['GG'], len(flat), rep['buckets']))
	cs.log.append('Rules: class value %s, tolerance %d, absent %s, scope %s'
	              % (opts['rule'], opts['tolerance'], opts['absent'], scope))
	fill = rep['present'] / float(rep['cells']) if rep['cells'] else 1.
	if opts['absent'] == krc.ABSENT_ZERO and fill < FILL_WARNING:
		cs.log.append('Warning: the source fills only %d%% of the group pairs it touches; absent members were set '
		              'to 0. If the source is partial, use Absent = No opinion' % int(round(fill * 100)))
	if rep['key_fallback']:
		cs.log.append('Key pair missing, mode used: %d buckets' % len(rep['key_fallback']))
	if cs.locked:
		cs.log.append('Locked, not changed: %d pairs' % len(cs.locked))

	report = {'table': table, 'reclass': rep, 'locked': list(cs.locked), 'flat': flat,
	          'coverage': coverage, 'options': opts, 'fill': fill}
	return cs, report


def import_check(kset, master, report):
	'''Self check after the ChangeSet was applied: [(a, b, expected, got)].
	Locked pairs that kept their old value show up here by design (split_locked).'''
	opts = report['options']
	return krc.self_check(kset, master, report['flat'], opts['tolerance'], opts['absent'], report['coverage'])


def split_locked(kset, master, mismatch):
	'''(real, locked): self check differences, the ones a locked pair causes apart.'''
	real, locked = [], []
	for item in mismatch:
		key = kset.resolve(master, item[0], item[1])[1]
		(locked if key in kset.locks else real).append(item)
	return real, locked


# - Files to masters -------------------------------------------------------
def import_files_to_masters(paths, masters, strip=''):
	'''Match source files to masters by file name (AFM import, KernMaster
	results): optional string stripped, white space and case ignored.
	Returns ({path: master}, [unmatched paths]).'''
	def norm(text):
		return ''.join(str(text).split()).lower()

	by_norm = {norm(m): m for m in masters}
	matched, unmatched = {}, []
	for path in paths:
		name = os.path.splitext(os.path.basename(path))[0]
		if strip:
			name = name.replace(strip, '')
		master = by_norm.get(norm(name))
		if master is None:
			unmatched.append(path)
		else:
			matched[path] = master
	return matched, unmatched


# - Sources ----------------------------------------------------------------
def read_source(path):
	'''Read an import source file. AFM: KPX / KP pairs, CharMetrics as coverage.
	KRN: KPX lines that carry a value (a job list without values gives nothing).
	Returns {'path', 'name', 'font_name', 'kerning': {(a, b): value}, 'glyphs': [names] or None}.'''
	ext = os.path.splitext(path)[1].lower().lstrip('.')
	out = {'path': path, 'name': os.path.basename(path), 'font_name': '', 'kerning': {}, 'glyphs': None}
	if ext == 'krn':
		with krn.KRNparser(path) as reader:
			for row in reader:
				if len(row) >= 3:
					try:
						out['kerning'][(row[0], row[1])] = float(row[2])
					except ValueError:
						pass
	else:
		data = afm.read(path)
		out['font_name'] = data['font_name']
		out['kerning'] = data['kerning']
		out['glyphs'] = data['glyphs'] or None
	return out


def plan_text(results, applied=False):
	'''Report of an import for the window: results is a list of
	{'master', 'sources', 'cs', 'report', 'summary', 'unmapped', 'mismatch' (after apply) or None}.'''
	lines = []
	for res in results:
		summ = res['summary'].get(res['master'], {'added': 0, 'changed': 0, 'unchanged': 0, 'removed': 0})
		lines.append('%s  ←  %s' % (res['master'], ', '.join(res['sources'])))
		lines.append('  %s: %d added, %d changed, %d unchanged, %d removed'
		             % ('Written' if applied else 'Plan', summ['added'], summ['changed'], summ['unchanged'], summ['removed']))
		for line in res['cs'].log:
			lines.append('  ' + line)
		if res['unmapped']:
			shown = ', '.join(res['unmapped'][:12]) + (' …' if len(res['unmapped']) > 12 else '')
			lines.append('  Not in the font (pairs dropped): %d glyphs: %s' % (len(res['unmapped']), shown))
		outside = res['report']['reclass']['outside']
		if outside:
			lines.append('  Outside coverage (not judged): %d glyphs' % len(outside))
		if res.get('mismatch') is not None:
			mism = res['mismatch']
			if mism:
				lines.append('  Self check: %d pairs differ from the source, e.g. %s'
				             % (len(mism), ', '.join('%s %s %s→%s' % m for m in mism[:5])))
			else:
				lines.append('  Self check: the master renders the source exactly.')
			if res.get('locked_diff'):
				lines.append('  Locked pairs kept their value (differ from the source): %s'
				             % ', '.join('%s %s' % m[:2] for m in res['locked_diff'][:8]))
		lines.append('')
	return '\n'.join(lines).rstrip() + '\n'


# - Snapshots --------------------------------------------------------------
def snapshot_folder(font_path):
	'''Sidecar folder of a saved font file: <font file>.trkern next to it; None if unsaved.'''
	if not font_path:
		return None
	return os.path.join(os.path.dirname(font_path), os.path.basename(font_path) + SNAPSHOT_SUFFIX)


def snapshot_write(folder, kset, masters, label):
	'''Write the touched masters (+ groups, locks) as a time stamped JSON. Returns the path.'''
	if not os.path.isdir(folder):
		os.makedirs(folder)
	stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
	safe = ''.join(c if c.isalnum() or c in '-_' else '-' for c in label)[:40] or 'snapshot'
	path = os.path.join(folder, '%s-%s.json' % (stamp, safe))
	data = kset.to_dict(masters)
	data['label'] = label
	data['created'] = datetime.now().isoformat()
	with io.open(path, 'w', encoding='utf-8') as target:
		target.write(json.dumps(data, ensure_ascii=False, indent=1))
	return path


def snapshot_list(folder):
	'''Snapshot files of a folder, newest first.'''
	if not folder or not os.path.isdir(folder):
		return []
	names = sorted((n for n in os.listdir(folder) if n.endswith('.json')), reverse=True)
	return [os.path.join(folder, n) for n in names]


def snapshot_read(path):
	with io.open(path, 'r', encoding='utf-8') as source:
		return KernSet.from_dict(json.loads(source.read()))


def restore_plan(kset, snapshot):
	'''ChangeSet that brings the snapshot's masters back to their saved pairs.'''
	cs = ChangeSet('restore')
	for master in snapshot.masters:
		old, new = kset.pairs.get(master, {}), snapshot.pairs.get(master, {})
		for pair, value in new.items():
			if old.get(pair) != value:
				cs.set(master, pair, value)
		for pair in old:
			if pair not in new:
				cs.remove(master, pair)
	return cs


# - KernMaster job ---------------------------------------------------------
def job_name(key, side):
	'''Job (KRN / CLA) name of a pair side: groups get the side suffix.'''
	if is_group(key):
		return group_key(group_name(key) + JOB_SIDE_SUFFIX[side])
	return key


def job_classes(kset):
	'''[(class name, members)] for the CLA file, both sides, side suffixed,
	the group leader first (KernMaster kerns a class by its first member).'''
	out = []
	for side in (LEFT, RIGHT):
		for name in sorted(kset.groups[side]):
			members = kset.ordered_members(name, side)
			if members:
				out.append((name + JOB_SIDE_SUFFIX[side], members))
	return out


def job_pairs_font(kset, master):
	'''The master's pairs as stored, in job names: [(left, right)].'''
	return sorted((job_name(l, LEFT), job_name(r, RIGHT)) for l, r in kset.pairs.get(master, {}))


def _job_tokens(kset, text, side, use_groups):
	'''Side keys from a text: glyph names, @group, @* (all groups of the side).
	A glyph in a group becomes its group when use_groups.'''
	keys = []
	for token in str(text or '').split():
		if token == '@*':
			found = [group_key(n) for n in sorted(kset.groups[side])]
		elif token.startswith('@'):
			found = [token] if group_name(token) in kset.groups[side] else []
		else:
			found = [kset.side_key(token, side) if use_groups else token]
		for key in found:
			if key not in keys:
				keys.append(key)
	return keys


def job_pairs_ab(kset, a_text, b_text, use_groups=True):
	'''A × B pairs in job names: [(left, right)], no duplicates, in input order.'''
	lefts = _job_tokens(kset, a_text, LEFT, use_groups)
	rights = _job_tokens(kset, b_text, RIGHT, use_groups)
	return [(job_name(l, LEFT), job_name(r, RIGHT)) for l in lefts for r in rights]


# - Font lib -----------------------------------------------------------------
def lib_new():
	return {'format': LIB_FORMAT, 'locks': [], 'job': {}, 'import': {}, 'rules': [], 'strings': {},
	        'leaders': {LEFT: {}, RIGHT: {}}}


def lib_normalize(data):
	'''Font lib entry with defaults; junk gives an empty entry.'''
	out = lib_new()
	if isinstance(data, dict):
		locks = data.get('locks') or []
		out['locks'] = [list(p) for p in locks if isinstance(p, (list, tuple)) and len(p) == 2]
		for key in ('job', 'import', 'strings'):
			if isinstance(data.get(key), dict):
				out[key] = dict(data[key])
		from typerig.core.algo.kern_rules import normalize_sets
		out['rules'] = normalize_sets(data.get('rules'))
		leaders = data.get('leaders') if isinstance(data.get('leaders'), dict) else {}
		out['leaders'] = {side: {str(k): str(v) for k, v in (leaders.get(side) or {}).items()} for side in (LEFT, RIGHT)}
	return out


# - Bulk value operations (Pairs tab) -------------------------------------------
# cells: [(master, pair)]. Missing cells (the pair is not in that master)
# are only written by 'set'; every other operation skips them.
BULK_OPS = (
	('set', 'Set to'), ('add', 'Add'), ('add_abs', 'Add away from 0'), ('scale', 'Scale %'),
	('round', 'Round to'), ('clamp', 'Clamp to ±'), ('drop', 'Remove if |v| <'),
	('remove', 'Remove'), ('replace', 'Replace value'),
)
COPY_MODES = (('fill', 'Fill missing only'), ('overwrite', 'Overwrite'))


def _bulk_value(op, value, a, b):
	'''New value for one cell, None = remove, False = leave as is.'''
	if op == 'set':
		return a
	if value is None:
		return False
	if op == 'add':
		return value + a
	if op == 'add_abs':
		return value + a if value > 0 else value - a if value < 0 else value
	if op == 'scale':
		return value * a / 100.
	if op == 'round':
		return a * round(value / a) if a else value
	if op == 'clamp':
		return max(-abs(a), min(abs(a), value))
	if op == 'drop':
		return None if abs(value) < a else False
	if op == 'remove':
		return None
	if op == 'replace':
		return b if value == a else False
	raise ValueError('Unknown operation: %s' % op)


def bulk_plan(kset, cells, op, a=0, b=0, base=None):
	'''ChangeSet for a bulk operation on cells. base: a ChangeSet whose
	values count as current (pending edits), else the kerning itself.'''
	cs = ChangeSet(op)
	pending = base.pairs if base is not None else {}
	for master, pair in cells:
		pair = tuple(pair)
		entry = pending.get(master, {})
		if pair in entry.get('remove', ()):
			value = None
		else:
			value = entry.get('set', {}).get(pair, kset.pairs.get(master, {}).get(pair))
		new = _bulk_value(op, value, float(a or 0), float(b or 0))
		if new is False:
			continue
		if new is None:
			if value is not None:
				cs.remove(master, pair, kset.locks)
		elif value is None or to_int(new) != value:
			cs.set(master, pair, new, kset.locks)
	return cs


def effective_table(kset, master, base=None):
	'''A master's pairs with a pending ChangeSet (base) on top.'''
	table = dict(kset.pairs.get(master, {}))
	entry = base.pairs.get(master) if base is not None else None
	if entry:
		for pair in entry['remove']:
			table.pop(pair, None)
		table.update(entry['set'])
	return table


def copy_plan(kset, src, dst, pairs=None, k=1., c=0., mode='fill', base=None):
	'''Master to master: dst = src * k + c, for pairs (default: all of src).
	fill: only pairs dst does not have; overwrite: every pair. base: pending
	changes that count as current.'''
	cs = ChangeSet('copy %s > %s' % (src, dst))
	source, target = effective_table(kset, src, base), effective_table(kset, dst, base)
	for pair in sorted(source if pairs is None else [tuple(p) for p in pairs]):
		if pair not in source or (mode == 'fill' and pair in target):
			continue
		value = to_int(source[pair] * float(k) + float(c))
		if target.get(pair) != value:
			cs.set(dst, pair, value, kset.locks)
	return cs


def interpolate_plan(kset, a, b, t, dst, pairs=None, mode='overwrite', base=None):
	'''dst = a + (b - a) * t per pair (t 0 = a, 1 = b, outside: extrapolate).
	A pair missing in a or b counts as 0 there, as Glyphs interpolates.
	base: pending changes that count as current.'''
	cs = ChangeSet('interpolate %s %s > %s' % (a, b, dst))
	ta, tb, target = (effective_table(kset, m, base) for m in (a, b, dst))
	keys = (set(ta) | set(tb)) if pairs is None else set(tuple(p) for p in pairs)
	for pair in sorted(keys):
		if pair not in ta and pair not in tb:
			continue
		if mode == 'fill' and pair in target:
			continue
		va, vb = ta.get(pair, 0), tb.get(pair, 0)
		value = to_int(va + (vb - va) * float(t))
		if target.get(pair) != value:
			cs.set(dst, pair, value, kset.locks)
	return cs


def merge_changes(into, cs):
	'''Add a ChangeSet on top of another (later wins, groups too); locked lists add up.'''
	for side in (LEFT, RIGHT):
		for name, members in cs.groups[side].items():
			into.set_group(side, name, members)
	for master, entry in cs.pairs.items():
		for pair in entry['remove']:
			into.remove(master, pair)
		for pair, value in entry['set'].items():
			into.set(master, pair, value)
	into.locked.extend(cs.locked)
	into.log.extend(cs.log)
	return into



# - KernMaster job: compositions ----------------------------------------------------
# A composition block (FontRig Kern Job Composer format, JSON compatible):
#   [name, [[item, first, second], ...]]
# item: glyph names, @group (a _1 / _2 side suffix is accepted), @* (every
# group of the side), *Set (host glyph set), characters; several space
# separated. A block gives every 1ST item x every 2ND item.

def block_new(name='Block'):
	return [str(name), []]


def normalize_blocks(data):
	'''Composer JSON (or our own) -> [[name, [[item, first, second], ...]], ...]; junk dropped.'''
	out = []
	for block in data or []:
		if not isinstance(block, (list, tuple)) or len(block) != 2 or not isinstance(block[1], (list, tuple)):
			continue
		items = []
		for item in block[1]:
			if isinstance(item, (list, tuple)) and len(item) >= 3 and str(item[0]).strip():
				items.append([str(item[0]).strip(), bool(item[1]), bool(item[2])])
		out.append([str(block[0]), items])
	return out


def _job_keys(kset, text, side, use_groups, sets, glyphs, char_map, report):
	'''Side keys for an item text. Unknown names and glyphs turned into
	groups are noted in report.'''
	keys = []
	for token in str(text or '').split():
		if token == '@*':
			found = [group_key(n) for n in sorted(kset.groups[side])]
		elif token.startswith('@'):
			name = group_name(token)
			suffix = JOB_SIDE_SUFFIX[side]
			if name not in kset.groups[side] and name.endswith(suffix) and name[:-len(suffix)] in kset.groups[side]:
				name = name[:-len(suffix)]
			found = [group_key(name)] if name in kset.groups[side] else []
		elif token.startswith('*') and sets is not None:
			found = list(sets.get(token[1:], []))
		else:
			glyph = char_map.get(token, token) if (char_map and len(token) == 1) else token
			found = [glyph] if glyphs is None or glyph in glyphs else []
		if not found:
			report['unknown'].add(token)
		for key in found:
			if not is_group(key) and use_groups:
				grouped = kset.side_key(key, side)
				if grouped != key:
					report['grouped'].add('%s \u2192 %s' % (key, job_name(grouped, side)))
					key = grouped
			if key not in keys:
				keys.append(key)
	return keys


def job_pairs_blocks(kset, blocks, use_groups=True, sets=None, glyphs=None, char_map=None):
	'''Pairs of composition blocks in job names, unique, in block order.
	Returns (pairs, report): report {'blocks': [(name, pairs)], 'duplicates', 'unknown': set,
	'grouped': set, 'empty': [block names without 1ST or 2ND items]}.'''
	glyphs = set(glyphs) if glyphs is not None else None
	report = {'blocks': [], 'duplicates': 0, 'unknown': set(), 'grouped': set(), 'empty': []}
	pairs, seen = [], set()
	for name, items in normalize_blocks(blocks):
		lefts, rights = [], []
		for text, first, second in items:
			if first:
				lefts += [k for k in _job_keys(kset, text, LEFT, use_groups, sets, glyphs, char_map, report) if k not in lefts]
			if second:
				rights += [k for k in _job_keys(kset, text, RIGHT, use_groups, sets, glyphs, char_map, report) if k not in rights]
		if not lefts or not rights:
			report['empty'].append(name)
		count = 0
		for left in lefts:
			for right in rights:
				pair = (job_name(left, LEFT), job_name(right, RIGHT))
				count += 1
				if pair in seen:
					report['duplicates'] += 1
					continue
				seen.add(pair)
				pairs.append(pair)
		report['blocks'].append((name, count))
	return pairs, report


def job_preview_text(pairs_by_master, classes, report=None, limit=JOB_PREVIEW_LINES):
	'''What Export job writes: blocks, warnings, CLA (leader first), KRN.'''
	masters = list(pairs_by_master)
	lines = ['JOB PREVIEW: %d master(s): %s' % (len(masters), ', '.join(masters)), '']
	if report is not None:
		lines.append('Blocks:')
		for name, count in report['blocks']:
			lines.append('  %-28s %d pairs' % (name, count))
		total = len(next(iter(pairs_by_master.values()))) if pairs_by_master else 0
		lines.append('Total: %d pairs%s' % (total, ' (%d repeated across blocks, written once)' % report['duplicates']
		                                       if report['duplicates'] else ''))
		warnings = []
		if report['unknown']:
			warnings.append('Not found (ignored): ' + ', '.join(sorted(report['unknown'])))
		if report['empty']:
			warnings.append('Blocks without 1ST or 2ND items (no pairs): ' + ', '.join(report['empty']))
		if report['grouped']:
			shown = sorted(report['grouped'])
			warnings.append('Written as their groups (Use groups): ' + ', '.join(shown[:30])
			                + (' \u2026' if len(shown) > 30 else ''))
		if warnings:
			lines.append('')
			lines.append('Warnings:')
			lines += ['  ' + w for w in warnings]
	lines += ['', 'CLA: %d classes (leader first)' % len(classes)]
	lines += ['  @%s = [%s];' % (name, ' '.join(members)) for name, members in classes]
	same = len(set(tuple(p) for p in pairs_by_master.values())) <= 1
	groups = [('all masters', next(iter(pairs_by_master.values())))] if same and pairs_by_master else list(pairs_by_master.items())
	for title, pairs in groups:
		lines += ['', 'KRN (%s): %d pairs' % (title, len(pairs))]
		lines += ['  KPX %s %s' % p for p in pairs[:limit]]
		if len(pairs) > limit:
			lines.append('  \u2026 %d more (all are written)' % (len(pairs) - limit))
	return '\n'.join(lines) + '\n'
