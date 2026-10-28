# MODULE: TypeRig / Core / Actions / Kern Engine
# -----------------------------------------------------------
# TR Kern engine (no UI): the state and steps of the TR Kern window, on a
# host — proxy/gs3/objects/kern.GlyphsKernHost (Glyphs), actions/kern_font
# .CoreFontKernHost (a core Font: UFO / designspace / .trfont, the tr-kern
# command line), or a fake one in tests. The logic is TypeRig core
# (algo/kern_*, actions/kern_actions); this module keeps the state between
# steps:
#   Pairs   every pair x every master (core kern_query rows), the query,
#           edits and bulk / master operations collected in a pending
#           ChangeSet, Apply (snapshot, write) / Discard, locks, explain.
#   Groups  kerning groups of a side, their members and leaders; edits
#           (core kern_groups) go to the pending changes, with preserve
#           rendering on by default; leaders, Copy leaders (CLA) and
#           Validate act at once (font lib / report).
#   Cleanup checks (core kern_cleanup) found on the kerning as it will be
#           (pending included); Plan fixes adds the fixes of the checked
#           checks to the pending changes. Groups > Auto: groups from
#           composites and suffixes (kern_groups.auto_groups), pending.
#   Analyze read-only analyses (core kern_analyze) of the kerning as it will
#           be (pending included); report lines carry links: a Pairs query
#           and the pairs behind it (Show in Pairs, Show pair in the edit tab).
#   Rules   analogy rule sets (FL Copy Kerning syntax, core kern_rules) kept
#           in the font lib; Plan adds them to the pending changes; live
#           sets re-run after every change of the kerning.
#   Strings proof strings / pair lists (core kern_strings): a new edit tab,
#           /name text, plain text, KPX lines.
#   Import  sources (AFM / KRN with values / OTF / TTF / UFO) -> masters ->
#           Preview -> Apply, snapshot before every write, Restore last,
#           self check after.
#   Job     KernMaster job: KRN per master + one CLA, into a folder.
# Options and the job are stored in the font lib (kern_actions.LIB_KEY)
# when the font is written anyway (Apply, Export job).
# Moved from TypeRig-Glyphs Plugins/TypeRig Kern.glyphsPlugin trk_engine.py
# (2026-10-27): the plugin's trk_engine is now a thin wrapper that supplies
# the Glyphs host.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import division, print_function, unicode_literals

__version__ = '0.1.0'

import os
import traceback

from typerig.core.algo import kern_model as km
from typerig.core.algo import kern_analyze as kan
from typerig.core.algo import kern_cleanup as kc
from typerig.core.algo import kern_groups as kg
from typerig.core.algo import kern_query as kq
from typerig.core.algo import kern_reclass as krc
from typerig.core.algo import kern_rules as kr
from typerig.core.algo import kern_strings as kst
from typerig.core.actions import kern_actions as ka
from typerig.core.fileio import cla, krn

PENDING_MARK = '\u2022'		# grid: a value that is pending (not written yet)
PATCH_MAX = 2000			# pairs one change may patch in place; more: rebuild every row
STRING_SOURCES = (('selected', 'Selected pairs (Pairs tab)'), ('shown', 'Shown pairs (Pairs tab)'),
                  ('master', 'All pairs of the master'), ('ab', 'A \u00d7 B'))
STRING_DEFAULTS = {'source': 'selected', 'master': '', 'a': '', 'b': '', 'suffix_a': '', 'suffix_b': '',
                   'pattern': 'FL A B A FR', 'fl': 'HH', 'fr': 'HH', 'join': 'newline'}
JOB_DEFAULTS = {'source': 'blocks', 'blocks': [], 'use_groups': True, 'masters': ''}	# masters '' = all
AB_BLOCK = 'A \u00d7 B'		# an old A x B job (source 'ab', fields a / b) becomes this block
ALL_MASTERS = ''


def _safe(text):
	return ''.join(c if c.isalnum() or c in '-_.' else '-' for c in str(text)).strip('-') or 'font'


class KernEngine(object):
	'''TR Kern state between clicks.'''

	def __init__(self, host, on_change=None):
		self.host = host
		self.on_change = on_change
		self.on_explain = None		# set: explain_pair calls it instead of on_change (only the explain text changed)
		self.font_key = None
		self.message = ''
		self._fresh()

	def _fresh(self):
		self.sources = []
		self.options = ka.import_options()
		self.strip = ''
		self.job = dict(JOB_DEFAULTS)
		self.results = None			# last Preview / Apply: list of per-master results
		self.applied = False
		self.report = ''			# Import tab report
		self.job_report = ''		# Job tab report
		self.undo = []				# [(label, undo ChangeSet, snapshot path or None)]
		self.lib = ka.lib_new()
		self.kset = None			# Pairs: the font's kerning, read on demand
		self.pending = km.ChangeSet('edits')
		self.query_text = ''
		self.query = kq.Query()
		self.query_error = ''
		self.explain = ''
		self._rows = None
		self._shown = None
		self._view = None			# kerning with the pending changes on top (explain)
		self._grid_cache = None		# (shown, masters, grid_items) — same list until the rows change
		self.grid_patched = set()	# grid_items indexes changed in place (take_grid_patched)
		self._row_index = None		# (rows, {pair: row}) for patching
		self._shown_index = None	# (shown, {id(row): index in shown})
		self._char_map = None
		self._names = None
		self._sets = None			# host glyph sets (*Uppercase ...), read on demand
		self.group_side = km.LEFT
		self.preserve = True		# Groups: keep every glyph pair's value through group edits
		self.groups_report = ''
		self.clean_opts = kc.options()
		self.clean_on = {key: keeps for key, _t, keeps in kc.CHECKS}	# rendering-safe checks on by default
		self.findings = {}
		self.cleanup_report = ''
		self.analyze_opts = kan.options()
		self.analyze_on = {key: True for key, _t in kan.ANALYSES}
		self.analysis = {}			# {key: result} of the last Run
		self.analyze_lines = []		# [(line, link or None)] of the report
		self.analyze_report = ''
		self.rules = []				# rule sets (kern_rules.rule_set dicts), font lib 'rules'
		self.rules_report = ''
		self.strings = dict(STRING_DEFAULTS)
		self.strings_text = ''

	def _changed(self):
		if self.on_change is not None:
			self.on_change()

	def _say(self, text):
		self.message = text
		self._changed()

	# - Font -----------------------------------------------------------------
	def sync_font(self):
		'''Font switched (or first call): start fresh from that font's lib.'''
		key = self.host.font_key()
		if key == self.font_key:
			return False
		self.font_key = key
		self._fresh()
		self.lib = ka.lib_normalize(self.host.load_data(ka.LIB_KEY))
		self.options = ka.import_options(self.lib['import'])
		self.strip = str(self.lib['import'].get('strip', ''))
		self.job.update(self._job_from_lib(self.lib['job']))
		self.rules = list(self.lib['rules'])
		self.strings.update({k: v for k, v in self.lib['strings'].items() if k in STRING_DEFAULTS})
		self.clean_opts = kc.options(self.lib['cleanup'].get('options'))
		self.clean_on.update({k: bool(v) for k, v in (self.lib['cleanup'].get('on') or {}).items() if k in self.clean_on})
		self.analyze_opts = kan.options(self.lib['analyze'].get('options'))
		self.analyze_on.update({k: bool(v) for k, v in (self.lib['analyze'].get('on') or {}).items() if k in self.analyze_on})
		self.message = '' if key is not None else 'No font open.'
		return True

	def _save_lib(self):
		self.lib['import'] = dict(self.options, strip=self.strip)
		self.lib['job'] = dict(self.job)
		self.lib['rules'] = [dict(r) for r in self.rules]
		self.lib['strings'] = dict(self.strings)
		self.lib['cleanup'] = {'options': dict(self.clean_opts), 'on': dict(self.clean_on)}
		self.lib['analyze'] = {'options': dict(self.analyze_opts), 'on': dict(self.analyze_on)}
		self.host.save_data(ka.LIB_KEY, self.lib)

	def masters(self):
		return self.host.master_names()

	def read_kernset(self, masters=None):
		kset = self.host.read_kernset(masters)
		kset.locks = set(tuple(p) for p in self.lib['locks'])
		kset.leaders = {side: dict(names) for side, names in self.lib['leaders'].items()}
		return kset

	@staticmethod
	def _job_from_lib(data):
		'''Job settings from the font lib; an old A x B job becomes one block.'''
		job = {k: v for k, v in (data or {}).items() if k in JOB_DEFAULTS}
		job['blocks'] = ka.normalize_blocks(job.get('blocks'))
		if (data or {}).get('source') == 'ab':
			a, b = str(data.get('a') or ''), str(data.get('b') or '')
			job['blocks'].append([AB_BLOCK, [i for i in ([a, True, False], [b, False, True]) if i[0].strip()]])
			job['source'] = 'blocks'
		if job.get('source') not in dict(ka.JOB_SOURCES):
			job['source'] = JOB_DEFAULTS['source']
		return job

	# - Sources ----------------------------------------------------------------
	def _map(self, src):
		'''Font glyph names for the source: flat pairs, coverage, unmapped names.'''
		names, production, unicodes = self.host.name_tables()
		raw = set(g for pair in src['kerning'] for g in pair) | set(src['glyphs'] or [])
		mapping, missing = krc.name_map(sorted(raw), names, production, unicodes)
		src['flat'] = krc.rename_pairs(src['kerning'], mapping)
		src['coverage'] = [mapping[g] for g in src['glyphs'] if g in mapping] if src['glyphs'] else None
		src['unmapped'] = missing

	def add_sources(self, paths):
		masters = self.masters()
		added, failed = 0, []
		for path in paths:
			if any(s['path'] == path for s in self.sources):
				continue
			try:
				src = ka.read_source(path)
			except Exception as e:
				failed.append('%s (%s)' % (os.path.basename(path), e))
				continue
			self._map(src)
			src['master'] = None
			self.sources.append(src)
			added += 1
		self._match(masters)
		self.results = None
		text = 'Added %d source(s).' % added
		if failed:
			text += ' Not read: ' + '; '.join(failed)
		self._say(text)

	def _match(self, masters=None, force=False):
		'''Give sources without a master the master named like the file
		(one master in the font: that master).'''
		masters = self.masters() if masters is None else masters
		todo = [s for s in self.sources if force or s['master'] not in masters]
		matched, _unmatched = ka.import_files_to_masters([s['path'] for s in todo], masters, self.strip)
		for src in todo:
			src['master'] = matched.get(src['path']) or (masters[0] if len(masters) == 1 else None)

	def set_strip(self, text):
		self.strip = str(text or '')
		self._match(force=True)
		self.results = None
		self._changed()

	def remove_sources(self, indices):
		self.sources = [s for i, s in enumerate(self.sources) if i not in set(indices)]
		self.results = None
		self._changed()

	def set_master(self, indices, master):
		for i in indices:
			if 0 <= i < len(self.sources):
				self.sources[i]['master'] = master
		self.results = None
		self._changed()

	def source_kind(self, src):
		if not src['flat']:
			return 'empty'
		return 'ready' if src['master'] in self.masters() else 'nomaster'

	def source_rows(self):
		return [{'kind': self.source_kind(s), 'file': s['name'], 'master': s['master'] or '—',
		         'pairs': len(s['flat']), 'glyphs': len(s['coverage']) if s['coverage'] else len(
		             set(g for p in s['flat'] for g in p)), 'missing': len(s['unmapped'])}
		        for s in self.sources]

	def set_option(self, key, value):
		self.options = ka.import_options(dict(self.options, **{key: value}))
		self.results = None
		self._changed()

	# - Import -----------------------------------------------------------------
	def _plans(self):
		'''One plan per master that has ready sources.'''
		by_master = {}
		for src in self.sources:
			if self.source_kind(src) == 'ready':
				by_master.setdefault(src['master'], []).append(src)
		kset = self.read_kernset(sorted(by_master))
		results = []
		for master in self.masters():
			srcs = by_master.get(master)
			if not srcs:
				continue
			flat, coverage = {}, set()
			for src in srcs:
				flat.update(src['flat'])
				coverage |= set(src['coverage'] or (g for p in src['flat'] for g in p))
			cs, report = ka.import_plan(kset, master, flat, self.options, coverage)
			if len(srcs) > 1:
				cs.log.append('%d sources merged (a later source wins on the same pair)' % len(srcs))
			unmapped = sorted(set(g for s in srcs for g in s['unmapped']))
			results.append({'master': master, 'sources': [s['name'] for s in srcs], 'cs': cs, 'report': report,
			                'summary': cs.summary(kset), 'unmapped': unmapped, 'mismatch': None})
		return kset, results

	def preview(self):
		if not any(self.source_kind(s) == 'ready' for s in self.sources):
			self.results, self.report = None, ''
			self._say('Nothing to preview: add sources and give them a master.')
			return None
		_kset, self.results = self._plans()
		self.applied = False
		self.report = ka.plan_text(self.results)
		self._say('Preview: %d master(s). Nothing written yet.' % len(self.results))
		return self.results

	def apply(self):
		'''Snapshot, write, read back, self check.'''
		if not any(self.source_kind(s) == 'ready' for s in self.sources):
			self._say('Nothing to apply: add sources and give them a master.')
			return None
		kset, results = self._plans()
		masters = [r['master'] for r in results]
		snapshot = None
		folder = ka.snapshot_folder(self.host.font_path())
		if folder:
			try:
				snapshot = ka.snapshot_write(folder, kset, masters, 'import')
			except (IOError, OSError) as e:
				self._say('Snapshot failed, nothing written: %s' % e)
				return None
		total = km.ChangeSet('import')
		for res in results:
			for master, entry in res['cs'].pairs.items():
				for pair, value in entry['set'].items():
					total.set(master, pair, value)
				for pair in entry['remove']:
					total.remove(master, pair)
		undo = km.apply(kset.copy(), total)
		written = self.host.apply(total)
		self.undo.append(('import ' + ', '.join(masters), undo, snapshot))
		after = self.read_kernset(masters)
		failed = 0
		for res in results:
			res['mismatch'], res['locked_diff'] = ka.split_locked(
				after, res['master'], ka.import_check(after, res['master'], res['report']))
			failed += (written.get(res['master']) or (0, 0, 0))[2]
		self.results, self.applied = results, True
		self.report = ka.plan_text(results, applied=True)
		if failed:
			self.report += 'Glyphs refused %d pair writes.\n' % failed
		self._save_lib()
		self._reload()
		self.host.redraw()
		live = self._run_live()
		where = ('Snapshot: %s' % os.path.basename(snapshot)) if snapshot else 'No snapshot file (font not saved)'
		self._say('Applied to %d master(s). %s.%s' % (len(results), where,
		          ' Live rules: %d change(s) pending (Pairs tab).' % live if live else ''))
		return results

	def can_restore(self):
		return bool(self.undo)

	def restore_last(self):
		if not self.undo:
			self._say('Nothing to restore.')
			return False
		label, undo, _snapshot = self.undo.pop()
		self.host.apply(undo)
		self.results, self.report = None, ''
		self._reload()
		self.host.redraw()
		self._say('Restored the kerning from before: %s.' % label)
		return True

	# - Job ----------------------------------------------------------------------
	def set_job(self, key, value):
		if key in JOB_DEFAULTS:
			self.job[key] = value
		self._changed()

	def job_masters(self):
		masters = self.masters()
		chosen = self.job.get('masters') or ALL_MASTERS
		return masters if chosen == ALL_MASTERS else [m for m in masters if m == chosen]

	def job_plan(self):
		'''({master: [(left, right)]}, classes, report or None), as Export job writes them.'''
		masters = self.job_masters()
		kset = self.read_kernset(masters)
		pairs, report = {}, None
		if self.job['source'] == 'blocks':
			sets = self.glyph_sets(self._blocks_need_sets())
			block_pairs, report = ka.job_pairs_blocks(kset, self.job['blocks'], bool(self.job['use_groups']), sets,
			                                          self.glyph_names(), self.char_map())
			pairs = {master: list(block_pairs) for master in masters}
		else:
			pairs = {master: ka.job_pairs_font(kset, master) for master in masters}
		return pairs, ka.job_classes(kset), report

	def preview_job(self):
		pairs, classes, report = self.job_plan()
		self.job_report = ka.job_preview_text(pairs, classes, report)
		total = len(next(iter(pairs.values()))) if pairs else 0
		self._say('Job preview: %d pairs, %d classes. Nothing written.' % (total, len(classes)))
		return pairs, classes, report

	# - Job blocks (compositions) -------------------------------------------------------
	def _blocks_changed(self):
		self.job['blocks'] = ka.normalize_blocks(self.job['blocks'])
		self._save_lib()
		self._changed()

	def add_block(self, name='Block'):
		names = set(b[0] for b in self.job['blocks'])
		new, n = name, 1
		while new in names:
			n += 1
			new = '%s %d' % (name, n)
		self.job['blocks'].append(ka.block_new(new))
		self._blocks_changed()
		return len(self.job['blocks']) - 1

	def remove_blocks(self, indices):
		self.job['blocks'] = [b for i, b in enumerate(self.job['blocks']) if i not in set(indices)]
		self._blocks_changed()

	def duplicate_block(self, index):
		if 0 <= index < len(self.job['blocks']):
			name, items = self.job['blocks'][index]
			new = self.add_block(name + ' copy')
			self.job['blocks'][new][1] = [list(i) for i in items]
			self._blocks_changed()
			return new
		return None

	def set_block_name(self, index, name):
		if 0 <= index < len(self.job['blocks']) and str(name).strip():
			self.job['blocks'][index][0] = str(name).strip()
			self._blocks_changed()

	def block_items(self, index):
		return self.job['blocks'][index][1] if 0 <= index < len(self.job['blocks']) else []

	def add_items(self, index, texts, first=True, second=True):
		'''Add items to a block (texts: one item each).'''
		if not 0 <= index < len(self.job['blocks']):
			return 0
		items = self.job['blocks'][index][1]
		added = 0
		for text in texts:
			text = str(text).strip()
			if text:
				items.append([text, bool(first), bool(second)])
				added += 1
		self._blocks_changed()
		return added

	def paste_items(self, index, text):
		'''Items from pasted text: "quoted","items", /slash/separated, comma, or one per line.'''
		import re
		text = str(text or '').strip()
		if '"' in text:
			parts = re.findall(r'"([^"]*)"', text)
		elif '/' in text and '\n' not in text:
			parts = text.split('/')
		elif ',' in text:
			parts = text.split(',')
		else:
			parts = text.splitlines()
		n = self.add_items(index, [p for p in parts if p.strip()])
		self._say('Pasted %d item(s).' % n)
		return n

	def remove_items(self, index, item_indices):
		if 0 <= index < len(self.job['blocks']):
			items = self.job['blocks'][index][1]
			self.job['blocks'][index][1] = [it for i, it in enumerate(items) if i not in set(item_indices)]
			self._blocks_changed()

	def set_items(self, index, rows):
		'''Items from the editor rows: [{'item', 'first', 'second'}].'''
		if 0 <= index < len(self.job['blocks']):
			self.job['blocks'][index][1] = [[str(r['item']).strip(), bool(r['first']), bool(r['second'])]
			                                for r in rows if str(r['item']).strip()]
			self._blocks_changed()

	def block_counts(self):
		'''Pairs per block (for the blocks list).'''
		try:
			_pairs, report = ka.job_pairs_blocks(self.pairs_kset(), self.job['blocks'], bool(self.job['use_groups']),
			                                     self.glyph_sets(self._blocks_need_sets()), self.glyph_names(),
			                                     self.char_map())
			return [count for _name, count in report['blocks']]
		except Exception:
			return [0] * len(self.job['blocks'])

	def load_composition(self, path, replace=False):
		'''Open a composition JSON (FontRig Kern Job Composer format).'''
		import json
		with open(path, 'r') as f:
			blocks = ka.normalize_blocks(json.load(f))
		self.job['blocks'] = blocks if replace else self.job['blocks'] + blocks
		self._blocks_changed()
		self._say('Composition: %d block(s) from %s.' % (len(blocks), os.path.basename(path)))
		return len(blocks)

	def save_composition(self, path):
		import json
		with open(path, 'w') as f:
			json.dump(self.job['blocks'], f, indent=1)
		self._say('Composition saved: %s.' % os.path.basename(path))

	def export_job(self, folder):
		'''KRN per master + one CLA into folder. The import strip string is set
		to "<family>-" so KernMaster's AFM files match their masters.'''
		try:
			pairs, classes, _report = self.job_plan()
			family = _safe((self.host.font_info() or {}).get('family') or 'font')
			written = []
			cla_path = os.path.join(folder, '%s.cla' % family)
			with cla.CLAparser(cla_path, 'w') as writer:
				writer.dump(classes, 'Font: %s' % family)
			written.append(cla_path)
			for master, rows in pairs.items():
				path = os.path.join(folder, '%s-%s.krn' % (family, _safe(master)))
				with krn.KRNparser(path, 'w') as writer:
					writer.dump(rows, 'Font: %s\nMaster: %s' % (family, master))
				written.append(path)
		except Exception as e:
			print(traceback.format_exc())
			self._say('Export failed: %s' % e)
			return []
		self.strip = family + '-'
		self._save_lib()
		lines = ['Job written to %s' % folder, '  %s: %d classes' % (os.path.basename(cla_path), len(classes))]
		lines += ['  %s-%s.krn: %d pairs' % (family, _safe(m), len(rows)) for m, rows in pairs.items()]
		lines.append('Import strip set to "%s": KernMaster AFM files named %s-<master>.afm match their masters.'
		             % (self.strip, family))
		self.job_report = '\n'.join(lines) + '\n'
		self._say('Job exported: %d file(s).' % len(written))
		return written

	# - Pairs --------------------------------------------------------------------------
	def _reload(self):
		'''Drop the cached kerning: the next grid access reads the font again.'''
		self.kset = None
		self._rows = self._shown = self._view = None

	def view_kset(self):
		'''The kerning as it will be after Apply (pending on top); the font's when nothing is pending.'''
		if not self.pending_count():
			return self.pairs_kset()
		if self._view is None:
			self._view = self.pairs_kset().copy()
			km.apply(self._view, self.pending)
		return self._view

	def _explain(self, a, b):
		text = kq.explain_text(self.view_kset(), a, b)
		if self.pending_count():
			text += '  (values include the pending changes)\n'
		return text

	def pairs_kset(self):
		if self.kset is None:
			self.kset = self.read_kernset()
			self._rows = self._shown = None
		return self.kset

	def char_map(self):
		if self._char_map is None:
			_names, _prod, unicodes = self.host.name_tables()
			self._char_map = {}
			for code, glyph in unicodes.items():
				try:
					self._char_map.setdefault(chr(code), glyph)
				except (ValueError, OverflowError):
					pass
		return self._char_map

	def rows(self):
		if self._rows is None:
			self._rows = kq.grid_rows(self.pairs_kset(), self.pending)
			self._shown = None
		return self._rows

	def shown(self):
		'''Rows that pass the query.'''
		if self._shown is None:
			self._shown = self.query.filter(self.rows(), self.pairs_kset())
		return self._shown

	def set_query(self, text):
		text = str(text or '')
		self.query_text = text
		try:
			self.query = kq.parse(text, self.char_map())
			self.query_error = ''
		except kq.QueryError as e:
			self.query = kq.Query()
			self.query_error = str(e)
		if self.query.explain is not None:
			self.explain = self._explain(*self.query.explain)
		self._shown = None
		self._say(self.query_error or '%d of %d pairs shown.' % (len(self.shown()), len(self.rows())))

	def set_filter_widgets(self, kind=None, missing=False):
		self.set_query(kq.set_widget_terms(self.query_text, kind, missing))

	def grid_items(self):
		'''Rows for the grid: kind (tint), left, right, type, one value per master, spread.
		The same list comes back until the shown rows change, so a host can
		compare with `is` instead of comparing every row.'''
		masters = self.pairs_kset().masters
		shown = self.shown()
		cached = self._grid_cache
		if cached is not None and cached[0] is shown and cached[1] == masters:
			return cached[2]
		items = [self._grid_item(row, masters) for row in shown]
		self._grid_cache = (shown, list(masters), items)
		self.grid_patched = set()		# indexes into the old list
		return items

	@staticmethod
	def _grid_item(row, masters):
		item = {'kind': 'locked' if row['locked'] else 'pending' if row['pending'] else row['kind'],
		        'left': row['pair'][0], 'right': row['pair'][1], 'type': row['kind']}
		vals = []
		for i, master in enumerate(masters):
			value = row['values'].get(master)
			text = '' if value is None else str(value)
			if master in row['pending']:
				text += PENDING_MARK
			item['m%d' % i] = text
			if value is not None:
				vals.append(value)
		item['spread'] = str(max(vals) - min(vals)) if len(vals) > 1 else ''
		return item

	def take_grid_patched(self):
		'''Indexes of grid_items() rows changed in place since the last call (same list).'''
		patched, self.grid_patched = sorted(self.grid_patched), set()
		return patched

	def _patch(self, cs):
		'''The pending changes grew by cs: rebuild only the rows it touched and
		apply it to the pending view, when that gives what a full rebuild
		gives; else drop them. Group changes re-key pairs: always a rebuild.'''
		if cs.groups[km.LEFT] or cs.groups[km.RIGHT]:
			self._rows = self._shown = self._view = None
			return
		if self._view is not None:
			km.apply(self._view, cs)		# == copy + apply(pending): later wins per (master, pair)
		pairs = set()
		for entry in cs.pairs.values():
			pairs.update(entry['set'])
			pairs.update(entry['remove'])
		if not self._patch_pairs(pairs):
			self._rows = self._shown = None

	def _patch_pairs(self, pairs):
		'''Rebuild the rows of these pairs in place (the grid items of shown
		rows too, their indexes into grid_patched). False: a row would appear
		or go, or too many pairs — rebuild every row instead. A patched row
		stays shown even if it no longer passes the query (no rows jumping
		away while nudging); the next search filters again.'''
		rows = self._rows
		if rows is None:
			return True		# nothing built yet
		if len(pairs) > PATCH_MAX:
			return False
		if self._row_index is None or self._row_index[0] is not rows:
			self._row_index = (rows, {row['pair']: row for row in rows})
		index = self._row_index[1]
		fresh = {}
		for pair in pairs:
			row = kq.grid_row(self.kset, pair, self.pending)
			if (row is None) != (pair not in index):
				return False
			if row is not None:
				fresh[pair] = row
		for pair, row in fresh.items():
			index[pair].update(row)
		cached, shown = self._grid_cache, self._shown
		if cached is None or shown is None or cached[0] is not shown:
			return True
		if self._shown_index is None or self._shown_index[0] is not shown:
			self._shown_index = (shown, {id(row): i for i, row in enumerate(shown)})
		where = self._shown_index[1]
		for pair in fresh:
			i = where.get(id(index[pair]))
			if i is not None:
				item = cached[2][i]
				item.clear()		# in place: the host's list may hold this dict
				item.update(self._grid_item(index[pair], cached[1]))
				self.grid_patched.add(i)
		return True

	def shown_pairs(self, indices=None):
		shown = self.shown()
		if indices is None:
			return [r['pair'] for r in shown]
		return [shown[i]['pair'] for i in indices if 0 <= i < len(shown)]

	def _add_pending(self, cs, what, live=True):
		ka.merge_changes(self.pending, cs)
		self._patch(cs)
		changed = cs.count('set') + cs.count('remove') + len(cs.groups[km.LEFT]) + len(cs.groups[km.RIGHT])
		text = '%s: %d change(s) pending.' % (what, changed)
		if cs.locked:
			text += ' %d locked cell(s) left as they are.' % len(cs.locked)
		ruled = self._run_live() if live and changed else 0
		if ruled:
			text += ' Live rules: %d more.' % ruled
		self._say(text)
		return changed

	def pending_count(self):
		return (self.pending.count('set') + self.pending.count('remove')
		        + len(self.pending.groups[km.LEFT]) + len(self.pending.groups[km.RIGHT]))

	def edit_cell(self, pair, master, text):
		'''A typed value: a number sets the cell, empty removes the pair from that master.'''
		text = str(text or '').replace(PENDING_MARK, '').strip()
		if text == '':
			cs = ka.bulk_plan(self.pairs_kset(), [(master, pair)], 'remove', base=self.pending)
		else:
			try:
				value = float(text)
			except ValueError:
				if not self._patch_pairs({tuple(pair)}):		# shows the value again instead of the typed text
					self._rows = self._shown = None
				self._say('Not a number: %s' % text)
				return 0
			cs = ka.bulk_plan(self.pairs_kset(), [(master, pair)], 'set', value, base=self.pending)
		return self._add_pending(cs, 'Edit')

	def bulk(self, op, a=0, b=0, pairs=(), masters=None):
		masters = self.pairs_kset().masters if masters is None else masters
		cells = [(m, p) for p in pairs for m in masters]
		cs = ka.bulk_plan(self.pairs_kset(), cells, op, a, b, base=self.pending)
		return self._add_pending(cs, dict(ka.BULK_OPS).get(op, op))

	def copy_master(self, src, dst, k=1., c=0., mode='fill', pairs=None):
		if src == dst:
			self._say('Copy: select two different masters.')
			return 0
		return self._add_pending(ka.copy_plan(self.pairs_kset(), src, dst, pairs, k, c, mode, self.pending), 'Copy %s > %s' % (src, dst))

	def interpolate_master(self, a, b, t, dst, mode='overwrite', pairs=None):
		if dst in (a, b):
			self._say('Interpolate: the target must differ from both masters.')
			return 0
		return self._add_pending(ka.interpolate_plan(self.pairs_kset(), a, b, t, dst, pairs, mode, self.pending),
		                         'Interpolate %s / %s > %s' % (a, b, dst))

	def discard_pending(self):
		n = self.pending_count()
		self.pending = km.ChangeSet('edits')
		self._rows = self._shown = self._view = None
		self._say('Discarded %d pending change(s).' % n)

	def apply_pending(self):
		'''Snapshot the touched masters, write the pending edits, reread.'''
		masters = self.pending.touched_masters()
		if self.pending.is_empty():
			self._say('Nothing pending.')
			return False
		masters = masters or list(self.masters())		# group changes only: snapshot every master
		kset = self.read_kernset()
		snapshot = None
		folder = ka.snapshot_folder(self.host.font_path())
		if folder:
			try:
				snapshot = ka.snapshot_write(folder, kset, masters, 'edits')
			except (IOError, OSError) as e:
				self._say('Snapshot failed, nothing written: %s' % e)
				return False
		undo = km.apply(kset.copy(), self.pending)
		written = self.host.apply(self.pending)
		failed = sum((w or (0, 0, 0))[2] for w in written.values())
		self.undo.append(('edits ' + ', '.join(masters), undo, snapshot))
		n = self.pending_count()
		self.pending = km.ChangeSet('edits')
		self._reload()
		self.host.redraw()
		self._say('Wrote %d change(s) to %s.%s' % (n, ', '.join(masters),
		                                           ' Glyphs refused %d.' % failed if failed else ''))
		return True

	def lock(self, pairs, on=True):
		locks = set(tuple(p) for p in self.lib['locks'])
		before = len(locks)
		if on:
			locks.update(tuple(p) for p in pairs)
		else:
			locks.difference_update(tuple(p) for p in pairs)
		self.lib['locks'] = [list(p) for p in sorted(locks)]
		self.host.save_data(ka.LIB_KEY, self.lib)
		if self.kset is not None:
			self.kset.locks = set(locks)
		self._rows = self._shown = None
		self._say('%s %d pair(s).' % ('Locked' if on else 'Unlocked', abs(len(locks) - before)))

	def explain_pair(self, pair):
		fresh = self.kset is not None		# else this reads the font: rows change too
		self.explain = self._explain(*kq.row_glyphs(self.pairs_kset(), pair))
		if fresh and self.on_explain is not None:
			self.on_explain()
		else:
			self._changed()

	# - Names ----------------------------------------------------------------------------
	def glyph_names(self):
		if self._names is None:
			self._names = list(self.host.name_tables()[0])
		return self._names

	def glyph_sets(self, needed=True):
		'''Host glyph sets, read once per font (None when not needed).'''
		if not needed:
			return None
		if self._sets is None:
			self._sets = self.host.glyph_sets()
		return self._sets

	def _blocks_need_sets(self):
		return any('*' in item[0].replace('@*', '') for _, items in self.job['blocks'] for item in items)

	def glyph_chars(self):
		out = {}
		for ch, glyph in self.char_map().items():
			out.setdefault(glyph, ch)
		return out

	# - Rules ----------------------------------------------------------------------------
	def add_rule_set(self, name=None, text='', save=True):
		names = set(r['name'] for r in self.rules)
		base = name or 'Rules'
		name, n = base, 1
		while name in names:
			n += 1
			name = '%s %d' % (base, n)
		self.rules.append(kr.rule_set(name=name, text=text))
		if save:
			self._save_lib()
		self._changed()
		return len(self.rules) - 1

	def remove_rule_sets(self, indices):
		self.rules = [r for i, r in enumerate(self.rules) if i not in set(indices)]
		self._save_lib()
		self._changed()

	def set_rule(self, index, key, value, save=True):
		if 0 <= index < len(self.rules) and key in kr.RULE_SET_DEFAULTS:
			self.rules[index][key] = value
			if save:
				self._save_lib()
			if key != 'text':
				self._changed()

	def save_rules(self):
		self._save_lib()

	def run_rules(self, indices=None):
		'''Plan the rule sets (all, or the given ones) on top of the pending changes.'''
		sets = self.rules if indices is None else [self.rules[i] for i in indices if 0 <= i < len(self.rules)]
		if not sets:
			self._say('No rule set to run.')
			return 0
		cs, report = kr.rules_plan(self.pairs_kset(), sets, base=self.pending, char_map=self.char_map(),
		                           glyphs=self.glyph_names())
		self.rules_report = kr.report_text(report)
		self._save_lib()
		return self._add_pending(cs, 'Rules', live=False)

	def _run_live(self):
		'''Live rule sets on top of the pending changes; returns the changes added.'''
		live = [r for r in self.rules if r.get('live')]
		if not live:
			return 0
		cs, report = kr.rules_plan(self.pairs_kset(), live, base=self.pending, char_map=self.char_map(),
		                           glyphs=self.glyph_names())
		self.rules_report = kr.report_text(report)
		if cs.is_empty():
			return 0
		ka.merge_changes(self.pending, cs)
		self._patch(cs)
		return cs.count('set') + cs.count('remove')

	def load_rules_file(self, path):
		with open(path, 'r') as f:
			text = f.read()
		index = self.add_rule_set(os.path.splitext(os.path.basename(path))[0], text)
		self._say('Rule set loaded: %s.' % os.path.basename(path))
		return index

	def save_rules_file(self, index, path):
		with open(path, 'w') as f:
			f.write(self.rules[index]['text'])
		self._say('Rule set saved: %s.' % os.path.basename(path))

	# - Strings --------------------------------------------------------------------------
	def set_string(self, key, value):
		if key in STRING_DEFAULTS:
			self.strings[key] = value
		self._changed()

	def string_pairs(self, selected=()):
		'''Glyph pairs for the proof string from the chosen source.'''
		st = self.strings
		kset = self.view_kset()
		master = st['master'] if st['master'] in kset.masters else (kset.masters[0] if kset.masters else None)
		if st['source'] == 'ab':
			sets = self.glyph_sets('*' in (st['a'] + st['b']).replace('@*', ''))
			lefts = kst.expand_side(st['a'], kset, km.LEFT, sets, self.char_map(), self.glyph_names())
			rights = kst.expand_side(st['b'], kset, km.RIGHT, sets, self.char_map(), self.glyph_names())
			return kst.ab_pairs(lefts, rights, (st['suffix_a'], st['suffix_b']))
		if master is None:
			return []
		if st['source'] == 'master':
			return kst.table_pairs(kset, master)
		pairs = list(selected) if st['source'] == 'selected' else self.shown_pairs()
		return kst.table_pairs(kset, master, pairs)

	def make_string(self, kind='tab', selected=()):
		'''Proof text: kind 'tab' (/names), 'plain' (characters) or 'kpx'.'''
		st = self.strings
		pairs = self.string_pairs(selected)
		if not pairs:
			self.strings_text = ''
			self._say('No pairs: select rows in the Pairs tab, or set the source.')
			return ''
		args = (st['pattern'], st['fl'], st['fr'], self.char_map(), self.glyph_chars(), st['join'])
		if kind == 'plain':
			text, dropped = kst.plain_text(pairs, *args)
			note = ' %d pair(s) without characters dropped.' % len(dropped) if dropped else ''
		elif kind == 'kpx':
			text, note = kst.kpx_text(pairs), ''
		else:
			text, note = kst.tab_text(pairs, *args), ''
		self.strings_text = text
		self._save_lib()
		self._say('%d pair(s).%s' % (len(pairs), note))
		return text

	def open_string_tab(self, selected=()):
		text = self.make_string('tab', selected)
		if text:
			self.host.open_tab(text)
		return text

	# - Current pair ---------------------------------------------------------------------
	def show_current_pair(self):
		'''Filter the grid to every pair that affects the glyph pair at the
		edit-view cursor, and explain it.'''
		pair = self.host.current_pair()
		if pair is None:
			self._say('No pair at the cursor: place the text cursor between two glyphs in an edit tab.')
			return None
		self.set_query('%s|%s; ?%s|%s' % (pair + pair))
		return pair

	def show_pairs(self, pairs):
		'''The opposite of show_current_pair: the glyph pairs standing for
		stored pairs (groups -> key glyphs, in the given order, no duplicates)
		go into the active edit tab, one per line, the text cursor between
		the first two. Returns the glyph pairs.'''
		pairs = [tuple(p) for p in (pairs or ())]
		if not pairs:
			self._say('No pair: select rows in the Pairs tab.')
			return []
		glyph_pairs = []
		for pair in pairs:		# table_pairs sorts: one at a time keeps the row order
			glyph_pair = kst.table_pairs(self.view_kset(), None, [pair])[0]
			if glyph_pair not in glyph_pairs:
				glyph_pairs.append(glyph_pair)
		self.host.show_pairs(glyph_pairs)
		self._say('Shown in the edit tab: %s' % ', '.join('%s %s' % p for p in glyph_pairs))
		return glyph_pairs

	# - Groups ----------------------------------------------------------------------------
	def set_group_side(self, side):
		if side in km.SIDES:
			self.group_side = side
		self._changed()

	def group_rows(self):
		return kg.group_rows(self.view_kset(), self.group_side)

	def group_members(self, name):
		view = self.view_kset()
		return view.ordered_members(name, self.group_side) if name in view.groups[self.group_side] else []

	def set_preserve(self, on):
		self.preserve = bool(on)
		self._changed()

	def _group_plan(self, cs, what):
		if cs.is_empty() and cs.log:
			self._say(cs.log[-1])
			return 0
		return self._add_pending(cs, what)

	def add_group(self, name, glyphs=()):
		name = str(name or '').strip().lstrip('@')
		if not name:
			self._say('Type a group name.')
			return 0
		if name in self.view_kset().groups[self.group_side]:
			self._say('A group %s exists on this side.' % name)
			return 0
		cs = kg.plan_members(self.pairs_kset(), self.group_side, name, list(glyphs), self.preserve, self.pending)
		return self._group_plan(cs, 'New group %s' % name)

	def rename_group(self, old, new):
		new = str(new or '').strip().lstrip('@')
		if new == old:
			return 0
		cs = kg.plan_rename(self.pairs_kset(), self.group_side, old, new, self.pending)
		if not cs.is_empty():
			leaders = self.lib['leaders'][self.group_side]
			if old in leaders:
				leaders[new] = leaders.pop(old)
				self._save_lib()
		return self._group_plan(cs, 'Rename %s' % old)

	def delete_groups(self, names):
		total = 0
		for name in names:
			cs = kg.plan_delete(self.pairs_kset(), self.group_side, name, self.preserve, self.pending)
			total += self._group_plan(cs, 'Delete %s' % name)
		return total

	def merge_groups(self, names, into=None):
		if len(names) < 2:
			self._say('Select two or more groups to merge.')
			return 0
		into = into or names[0]
		cs = kg.plan_merge(self.pairs_kset(), self.group_side, names, into, self.preserve, self.pending)
		return self._group_plan(cs, 'Merge into %s' % into)

	def move_glyphs(self, glyphs, name):
		'''Glyphs into group name (None: out of their groups).'''
		glyphs = [g for g in glyphs if g]
		if not glyphs:
			self._say('No glyphs: select members, or glyphs in Glyphs.')
			return 0
		cs = kg.plan_move(self.pairs_kset(), self.group_side, glyphs, name, self.preserve, self.pending)
		return self._group_plan(cs, ('Into %s' % name) if name else 'Out of the group')

	def add_selected_glyphs(self, name):
		return self.move_glyphs(self.host.selected_names(), name)

	def set_leader(self, name, glyph):
		'''The leader of a group (font lib; no kerning change).'''
		if glyph not in self.view_kset().groups[self.group_side].get(name, []):
			self._say('%s is not a member of %s.' % (glyph, name))
			return False
		self.lib['leaders'][self.group_side][name] = glyph
		self._save_lib()
		for kset in (self.kset, self._view):
			if kset is not None:
				kset.leaders[self.group_side][name] = glyph
		self._say('Leader of %s: %s.' % (name, glyph))
		return True

	def copy_leaders_from_cla(self, path):
		'''Leaders from a CLA file (its first members), for the groups of the same name.'''
		with cla.CLAparser(path) as reader:
			classes = list(reader)
		leaders, skipped = kg.leaders_from_cla(classes, self.view_kset())
		n = 0
		for side in km.SIDES:
			for name, glyph in leaders[side].items():
				if self.lib['leaders'][side].get(name) != glyph:
					self.lib['leaders'][side][name] = glyph
					n += 1
		self._save_lib()
		self._reload()
		lines = ['Leaders from %s: %d set.' % (os.path.basename(path), n)]
		lines += ['  %s: %s' % item for item in skipped[:30]]
		self.groups_report = '\n'.join(lines) + '\n'
		self._say('Copied %d leader(s); %d class(es) skipped.' % (n, len(skipped)))
		return n

	def validate_groups(self):
		report = kg.validate(self.view_kset(), self.glyph_names())
		self.groups_report = kg.validate_text(report)
		problems = (sum(len(v) for v in report['conflicts'].values()) + len(report['empty']) + len(report['missing'])
		            + len(report['glyph_named']) + len(report['orphans']))
		self._say('Validate: %d problem(s).' % problems)
		return report

	# - Cleanup ---------------------------------------------------------------------------
	def set_clean_option(self, key, value):
		self.clean_opts = kc.options(dict(self.clean_opts, **{key: value}))
		self.findings = {}
		self._save_lib()
		self._changed()

	def set_check(self, key, on):
		if key in self.clean_on:
			self.clean_on[key] = bool(on)
			self._save_lib()
		self._changed()

	def run_cleanup(self):
		'''Find with every checked check, on the kerning as it will be (pending included).'''
		view = self.view_kset()
		self.findings = {}
		parts = []
		for key, _title, _keeps in kc.CHECKS:
			if self.clean_on.get(key):
				self.findings[key] = kc.find(view, key, self.clean_opts, self.glyph_names())
				parts.append(kc.report_text(key, self.findings[key]))
		self.cleanup_report = '\n'.join(parts)
		total = sum(len(f) for f in self.findings.values())
		self._say('Cleanup: %d finding(s). Nothing changed yet.' % total)
		return self.findings

	def finding_count(self, key):
		return len(self.findings[key]) if key in self.findings else None

	def plan_cleanup(self):
		'''The fixes of the checked checks (last Find) as pending changes.'''
		if not self.findings:
			self._say('Click Find first.')
			return 0
		view = self.view_kset()
		total = km.ChangeSet('cleanup')
		for key, findings in self.findings.items():
			if findings and self.clean_on.get(key) and key != 'outliers':
				ka.merge_changes(total, kc.fix(view, key, findings, self.clean_opts))
		self.findings = {}
		self.cleanup_report += '\nFixes planned; click Find again to check the result.\n'
		return self._add_pending(total, 'Cleanup')

	# - Analyze ---------------------------------------------------------------------------
	def set_analyze_option(self, key, value):
		self.analyze_opts = kan.options(dict(self.analyze_opts, **{key: value}))
		self._save_lib()
		self._changed()

	def set_analysis(self, key, on):
		if key in self.analyze_on:
			self.analyze_on[key] = bool(on)
			self._save_lib()
		self._changed()

	def run_analyze(self):
		'''Every checked analysis on the kerning as it will be (pending included). Writes nothing.'''
		view = self.view_kset()
		self.analysis = {}
		self.analyze_lines = []
		for key, _title in kan.ANALYSES:
			if self.analyze_on.get(key):
				self.analysis[key] = kan.analyze(view, key, self.analyze_opts)
				if self.analyze_lines:
					self.analyze_lines.append(('', None))
				self.analyze_lines += kan.report(key, self.analysis[key], self.analyze_opts)
		self.analyze_report = kan.report_text(self.analyze_lines) if self.analyze_lines else ''
		found = sum(kan.count(k, r) or 0 for k, r in self.analysis.items())
		self._say('Analyze: %d finding(s). Nothing changed.' % found)
		return self.analysis

	def analysis_count(self, key):
		return kan.count(key, self.analysis[key]) if key in self.analysis else None

	def analyze_link(self, line):
		'''The link of report line number line (0 based), or None.'''
		return self.analyze_lines[line][1] if 0 <= line < len(self.analyze_lines) else None

	def show_analyze_query(self, line):
		'''The Pairs query of a report line. Returns the query text, or None.'''
		found = self.analyze_link(line)
		if not found or not found['query']:
			self._say('This line has no pairs to show.')
			return None
		self.set_query(found['query'])
		return found['query']

	def show_analyze_pairs(self, line):
		'''The pairs of a report line into the edit tab (groups -> key glyphs).'''
		found = self.analyze_link(line)
		if not found or not found['pairs']:
			self._say('This line has no pairs to show.')
			return []
		return self.show_pairs(found['pairs'])

	# - Auto groups ---------------------------------------------------------------------------
	def auto_groups(self, only_ungrouped=True):
		'''Groups from composites and suffixes, as pending changes (preserve rendering as set).'''
		sets = self.glyph_sets()
		workset = set(sets.get('Uppercase', [])) | set(sets.get('Lowercase', [])) | set(sets.get('Smallcaps', []))
		view = self.view_kset()
		proposal = kg.auto_groups(view, self.host.components(), workset, self.glyph_names(), only_ungrouped)
		cs = kg.plan_auto(self.pairs_kset(), proposal, self.preserve, self.pending)
		self.groups_report = kg.auto_text(proposal)
		if cs.is_empty():
			self._say('Auto groups: nothing to place.')
			return 0
		return self._add_pending(cs, 'Auto groups')
