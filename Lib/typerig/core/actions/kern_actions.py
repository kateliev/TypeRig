# MODULE: TypeRig / Core / Actions / Kern
# -----------------------------------------------------------
# TR Kern operations. Each one reads a KernSet and returns a ChangeSet
# (core/algo/kern_model.py); the host previews it, snapshots the touched
# masters, then applies. Nothing here talks to an editor.
#
# Phase 0: import external kerning onto the font's groups.
#   import_plan(kset, master, flat, ...)   -> (ChangeSet, report)
#   import_files_to_masters(names, masters, strip)  file -> master matching
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import os

from typerig.core.algo import kern_reclass as krc
from typerig.core.algo.kern_model import ChangeSet, LEFT, RIGHT, is_group, group_name

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
SCOPE_MERGE_CLEAR, SCOPE_REPLACE, SCOPE_MERGE = 'merge_clear', 'replace', 'merge'
SCOPES = ((SCOPE_MERGE_CLEAR, 'Merge + clear stale'), (SCOPE_REPLACE, 'Replace master'), (SCOPE_MERGE, 'Merge'))
SCOPE_DEFAULT = SCOPE_MERGE_CLEAR
FILL_WARNING = .5	# absent = 0 on a source that fills less of its group pairs: warn (partial source?)

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
	Locked pairs that kept their old value show up here by design.'''
	opts = report['options']
	return krc.self_check(kset, master, report['flat'], opts['tolerance'], opts['absent'], report['coverage'])


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
