# MODULE: TypeRig / Core / Actions / Kern CLI (tr-kern)
# -----------------------------------------------------------
# TR Kern on the command line, for UFO, designspace and .trfont files: the
# same core engine as the Glyphs window (actions/kern_engine) on a core Font
# (fileio/kerndoc, actions/kern_font.CoreFontKernHost). UFO / designspace:
# only kerning.plist, groups.plist and the TR Kern lib key are written.
# Every write keeps a snapshot next to the font (<font>.trkern/); restore
# brings one back.
#
#   tr-kern info FONT
#   tr-kern import FONT SOURCE... [--master M] [--strip S] [--rule key|mode|median]
#           [--tolerance N] [--absent zero|none] [--scope merge_clear|replace|merge]
#           [--round N] [--drop N] [--clamp N] [--dry-run]
#   tr-kern cleanup FONT [--check NAME ...] [--tolerance N] [--small N] [--spread N]
#           [--missing fill|copy|nearest|interpolate|remove] [--copy-from M] [--apply]
#   tr-kern analyze FONT [--analysis NAME ...] [--master M] [--bin N] [--extreme N] [--spike N]
#           [--shape N] [--pressure N] [--culprit N] [--fragile N] [--divergence N] [--members N]
#           [--json PATH]   (read only)
#   tr-kern job FONT FOLDER [--composition JSON | --font-kerning] [--master M]
#           [--no-groups] [--preview]
#   tr-kern rules FONT RULES.txt [--no-class] [--master M] [--dry-run]
#   tr-kern restore FONT [--list] [--snapshot PATH]
#   tr-kern pairs FONT [--query Q] [--explain A|V] [--limit N]
#           [--op set|add|add_abs|scale|round|clamp|drop|remove|replace --value N [--value2 N]]
#           [--copy FROM TO [--k K] [--c C]] [--interpolate A B T TO] [--mode fill|overwrite]
#           [--master M ...] [--lock | --unlock] [--apply]
#   tr-kern groups FONT [--side left|right] [--members NAME] [--auto] [--validate]
#           [--leaders-from CLA] [--leader NAME GLYPH] [--move GLYPH... --to NAME | --out GLYPH...]
#           [--new NAME GLYPH...] [--rename OLD NEW] [--delete NAME...] [--merge NAME...]
#           [--no-preserve] [--apply]
#
#   python -m typerig.core.actions.kern_cli ...   or   main(argv) -> exit code
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function

import argparse
import json
import os
import sys

from typerig.core.algo import kern_analyze as kan
from typerig.core.algo import kern_cleanup as kc
from typerig.core.algo import kern_model as km
from typerig.core.algo import kern_reclass as krc
from typerig.core.actions import kern_actions as ka
from typerig.core.actions.kern_engine import KernEngine
from typerig.core.fileio.kerndoc import KernDocument

__version__ = '0.1.0'

PROG = 'tr-kern'


# - Helpers ---------------------------------------------------------------------
def _open(path):
	doc = KernDocument.load(path)
	engine = KernEngine(doc.host())
	engine.sync_font()
	return doc, engine


def _out(text, stream=None):
	(stream or sys.stdout).write(text if text.endswith('\n') else text + '\n')


def _save(doc, engine):
	written = doc.save()
	_out('Saved: %s' % ', '.join(os.path.basename(p) for p in written))
	if engine.message:
		_out(engine.message)


# - Commands --------------------------------------------------------------------
def cmd_info(args):
	doc, engine = _open(args.font)
	kset = engine.pairs_kset()
	_out('%s (%s): %d glyphs, %d masters' % (os.path.basename(doc.path), doc.kind, len(doc.font.glyphs), len(kset.masters)))
	for master in kset.masters:
		kinds = {}
		for pair in kset.pairs[master]:
			kinds[km.pair_kind(pair)] = kinds.get(km.pair_kind(pair), 0) + 1
		loc = kset.locations.get(master) or {}
		_out('  %-20s %6d pairs  (%s)%s' % (master, len(kset.pairs[master]),
		                                   ', '.join('%s %d' % kv for kv in sorted(kinds.items())) or 'none',
		                                   '  ' + ' '.join('%s=%g' % kv for kv in sorted(loc.items())) if loc else ''))
	_out('Groups: %d left, %d right; leaders set: %d' % (len(kset.groups[km.LEFT]), len(kset.groups[km.RIGHT]),
	     sum(len(v) for v in kset.leaders.values())))
	conflicts = kset.conflicts()
	if any(conflicts.values()):
		_out('Glyphs in two groups of one side: %d' % sum(len(v) for v in conflicts.values()))
	_out('Locked pairs: %d' % len(kset.locks))
	return 0


def cmd_import(args):
	doc, engine = _open(args.font)
	options = {k: getattr(args, k) for k in ('rule', 'tolerance', 'absent', 'scope', 'round_to', 'min_abs', 'clamp')
	           if getattr(args, k) is not None}
	for key, value in options.items():
		engine.set_option(key, value)
	if args.strip is not None:
		engine.set_strip(args.strip)
	engine.add_sources([os.path.abspath(p) for p in args.sources])
	if args.master:
		if args.master not in engine.masters():
			_out('No master %s (masters: %s)' % (args.master, ', '.join(engine.masters())), sys.stderr)
			return 1
		engine.set_master(range(len(engine.sources)), args.master)
	for row in engine.source_rows():
		_out('Source %-30s -> %-12s %6s pairs, %s glyphs, %s not in the font' % (
			row['file'], row['master'], row['pairs'], row['glyphs'], row['missing']))
	if args.dry_run:
		results = engine.preview()
		_out(engine.report or engine.message)
		return 0 if results is not None else 1
	results = engine.apply()
	if results is None:
		_out(engine.message, sys.stderr)
		return 1
	_out(engine.report)
	_save(doc, engine)
	return 0


def cmd_cleanup(args):
	doc, engine = _open(args.font)
	keys = [k for k, _t, _s in kc.CHECKS]
	if args.check:
		bad = [c for c in args.check if c not in keys]
		if bad:
			_out('Unknown check: %s (checks: %s)' % (', '.join(bad), ', '.join(keys)), sys.stderr)
			return 1
		for key in keys:
			engine.set_check(key, key in args.check)
	for key, attr in (('tolerance', 'tolerance'), ('small', 'small'), ('spread', 'spread'),
	                  ('mismatch_fix', 'missing'), ('copy_from', 'copy_from')):
		if getattr(args, attr) is not None:
			engine.set_clean_option(key, getattr(args, attr))
	engine.run_cleanup()
	_out(engine.cleanup_report)
	if not args.apply:
		_out('Nothing changed (use --apply to write the fixes).')
		return 0
	if not engine.plan_cleanup():
		_out('Nothing to fix.')
		return 0
	engine.apply_pending()
	_save(doc, engine)
	return 0


def cmd_analyze(args):
	doc, engine = _open(args.font)
	keys = [k for k, _t in kan.ANALYSES]
	if args.analysis:
		bad = [a for a in args.analysis if a not in keys]
		if bad:
			_out('Unknown analysis: %s (analyses: %s)' % (', '.join(bad), ', '.join(keys)), sys.stderr)
			return 1
	if args.master and args.master not in engine.masters():
		_out('Unknown master: %s (masters: %s)' % (args.master, ', '.join(engine.masters())), sys.stderr)
		return 1
	# options for this run only: the font lib is not written (analyze is read only)
	engine.analyze_on = dict((k, not args.analysis or k in args.analysis) for k in keys)
	opts = dict(engine.analyze_opts)
	for key in kan.OPTION_DEFAULTS:
		if getattr(args, key, None) is not None:
			opts[key] = getattr(args, key)
	engine.analyze_opts = kan.options(opts)
	engine.run_analyze()
	_out(engine.analyze_report)
	if args.json:
		data = {'font': os.path.basename(doc.path), 'options': engine.analyze_opts,
		        'results': dict((k, kan.to_data(r)) for k, r in engine.analysis.items())}
		with open(args.json, 'w') as f:
			json.dump(data, f, indent=1)
		_out('Written: %s' % args.json)
	return 0


def cmd_job(args):
	doc, engine = _open(args.font)
	if args.font_kerning:
		engine.set_job('source', 'font')
	else:
		engine.set_job('source', 'blocks')
		if args.composition:
			engine.load_composition(args.composition, replace=True)
		if not engine.job['blocks']:
			_out('No composition: give --composition JSON, or --font-kerning.', sys.stderr)
			return 1
	engine.set_job('use_groups', not args.no_groups)
	if args.master:
		engine.set_job('masters', args.master)
	if args.preview:
		engine.preview_job()
		_out(engine.job_report)
		return 0
	folder = os.path.abspath(args.folder)
	if not os.path.isdir(folder):
		os.makedirs(folder)
	written = engine.export_job(folder)
	_out(engine.job_report)
	if not written:
		return 1
	doc.save()		# the import strip is kept in the font
	return 0


def cmd_rules(args):
	doc, engine = _open(args.font)
	with open(args.rules, 'r') as f:
		text = f.read()
	index = engine.add_rule_set(os.path.splitext(os.path.basename(args.rules))[0], text, save=False)
	engine.set_rule(index, 'class', not args.no_class, save=False)
	if args.master:
		engine.set_rule(index, 'masters', args.master, save=False)
	engine.run_rules([index])
	engine.remove_rule_sets([index])		# a command line run does not keep the set in the font
	_out(engine.rules_report)
	if args.dry_run or not engine.pending_count():
		_out('%d change(s) planned; nothing written.' % engine.pending_count())
		return 0
	engine.apply_pending()
	_save(doc, engine)
	return 0


def cmd_restore(args):
	doc, engine = _open(args.font)
	folder = ka.snapshot_folder(os.path.abspath(doc.path))
	snapshots = ka.snapshot_list(folder)
	if args.list or not snapshots:
		_out('Snapshots in %s:' % folder if snapshots else 'No snapshots next to the font.')
		for path in snapshots:
			_out('  ' + os.path.basename(path))
		return 0 if (snapshots or args.list) else 1
	path = args.snapshot or snapshots[0]
	snapshot = ka.snapshot_read(path)
	kset = engine.pairs_kset()
	cs = ka.restore_plan(kset, snapshot)
	for side in km.SIDES:
		if snapshot.groups[side] != kset.groups[side]:
			for name in set(kset.groups[side]) | set(snapshot.groups[side]):
				if kset.groups[side].get(name) != snapshot.groups[side].get(name):
					cs.set_group(side, name, snapshot.groups[side].get(name))
	if cs.is_empty():
		_out('The font already matches %s.' % os.path.basename(path))
		return 0
	doc.host().apply(cs)
	_out('Restored from %s: %d pair change(s), %d group change(s).' % (
		os.path.basename(path), cs.count('set') + cs.count('remove'),
		len(cs.groups[km.LEFT]) + len(cs.groups[km.RIGHT])))
	_save(doc, engine)
	return 0


def _finish(doc, engine, apply, what):
	n = engine.pending_count()
	if not n:
		_out('%s: nothing to change.' % what)
		return 0
	if not apply:
		_out('%s: %d change(s) planned; nothing written (use --apply).' % (what, n))
		return 0
	engine.apply_pending()
	_save(doc, engine)
	return 0


def cmd_pairs(args):
	doc, engine = _open(args.font)
	if args.explain:
		engine.set_query('?' + args.explain)
		_out(engine.explain)
		return 0
	engine.set_query(args.query or '')
	if engine.query_error:
		_out('Query: %s' % engine.query_error, sys.stderr)
		return 1
	pairs = engine.shown_pairs()
	masters = args.master or None
	if masters and any(m not in engine.masters() for m in masters):
		_out('Masters: %s' % ', '.join(engine.masters()), sys.stderr)
		return 1
	acting = args.op or args.copy or args.interpolate or args.lock or args.unlock
	if not acting:
		kset = engine.pairs_kset()
		_out('%-22s %-22s %-4s %s' % ('left', 'right', 'kind', '  '.join('%8s' % m[:8] for m in kset.masters)))
		for row in engine.shown()[:args.limit]:
			_out('%-22s %-22s %-4s %s' % (row['pair'][0], row['pair'][1], row['kind'], '  '.join(
				'%8s' % ('' if row['values'].get(m) is None else row['values'][m]) for m in kset.masters)))
		_out('%d of %d pairs%s' % (len(engine.shown()), len(engine.rows()),
		     '' if len(engine.shown()) <= args.limit else ' (first %d listed; --limit)' % args.limit))
		return 0
	if args.lock or args.unlock:
		engine.lock(pairs, bool(args.lock))
		doc.save()
		_out(engine.message)
		return 0
	if args.op:
		engine.bulk(args.op, args.value or 0, args.value2 or 0, pairs, masters)
	if args.copy:
		engine.copy_master(args.copy[0], args.copy[1], args.k, args.c, args.mode or 'fill',
		                   pairs if args.query else None)
	if args.interpolate:
		a, b, t, dst = args.interpolate
		engine.interpolate_master(a, b, float(t), dst, args.mode or 'overwrite', pairs if args.query else None)
	_out(engine.message)
	return _finish(doc, engine, args.apply, 'Pairs')


def cmd_groups(args):
	doc, engine = _open(args.font)
	engine.set_group_side(args.side)
	engine.set_preserve(not args.no_preserve)
	did = False
	if args.leaders_from:
		engine.copy_leaders_from_cla(args.leaders_from)
		doc.save()
		_out(engine.groups_report)
		did = True
	if args.leader:
		if not engine.set_leader(args.leader[0], args.leader[1]):
			_out(engine.message, sys.stderr)
			return 1
		doc.save()
		_out(engine.message)
		did = True
	if args.validate:
		engine.validate_groups()
		_out(engine.groups_report)
		did = True
	if args.members:
		members = engine.group_members(args.members)
		_out('%s (%s): %s' % (args.members, args.side, ' '.join(members) if members else 'no such group'))
		did = True
	planned = False
	if args.auto:
		engine.auto_groups()
		_out(engine.groups_report)
		planned = True
	if args.new:
		engine.add_group(args.new[0], args.new[1:])
		planned = True
	if args.move:
		if not args.to:
			_out('--move needs --to GROUP', sys.stderr)
			return 1
		engine.move_glyphs(args.move, args.to)
		planned = True
	if args.out:
		engine.move_glyphs(args.out, None)
		planned = True
	if args.rename:
		engine.rename_group(args.rename[0], args.rename[1])
		planned = True
	if args.delete:
		engine.delete_groups(args.delete)
		planned = True
	if args.merge:
		engine.merge_groups(args.merge)
		planned = True
	if planned:
		_out(engine.message)
		return _finish(doc, engine, args.apply, 'Groups')
	if not did:
		for row in engine.group_rows():
			_out('%-24s %4d glyphs %5d pairs  leader %s' % (row['name'], row['members'], row['pairs'], row['leader']))
	return 0


# - Parser ------------------------------------------------------------------------
def parser():
	p = argparse.ArgumentParser(prog=PROG, description='TR Kern: kerning of UFO, designspace and .trfont files.')
	sub = p.add_subparsers(dest='command')

	s = sub.add_parser('info', help='masters, pairs, groups')
	s.add_argument('font')
	s.set_defaults(func=cmd_info)

	s = sub.add_parser('import', help='import external kerning (AFM, KRN, OTF, TTF, UFO) onto the font groups')
	s.add_argument('font')
	s.add_argument('sources', nargs='+')
	s.add_argument('--master', help='the master every source goes to (default: matched by file name)')
	s.add_argument('--strip', help='text removed from source file names before they are matched to masters')
	s.add_argument('--rule', choices=[k for k, _t in krc.VALUE_RULES])
	s.add_argument('--tolerance', type=int)
	s.add_argument('--absent', choices=[k for k, _t in krc.ABSENT_RULES])
	s.add_argument('--scope', choices=[k for k, _t in ka.SCOPES])
	s.add_argument('--round', dest='round_to', type=int)
	s.add_argument('--drop', dest='min_abs', type=int)
	s.add_argument('--clamp', type=int)
	s.add_argument('--dry-run', action='store_true', help='report the plan, write nothing')
	s.set_defaults(func=cmd_import)

	s = sub.add_parser('cleanup', help='find (and with --apply fix) kerning to remove or simplify')
	s.add_argument('font')
	s.add_argument('--check', nargs='+', help='checks to run: %s (default: the ones that keep the spacing)'
	               % ', '.join(k for k, _t, _s in kc.CHECKS))
	s.add_argument('--tolerance', type=int)
	s.add_argument('--small', type=int)
	s.add_argument('--spread', type=int)
	s.add_argument('--missing', choices=[k for k, _t in kc.MISMATCH_FIXES])
	s.add_argument('--copy-from', dest='copy_from')
	s.add_argument('--apply', action='store_true', help='write the fixes')
	s.set_defaults(func=cmd_cleanup)

	s = sub.add_parser('analyze', help='read-only analytics: health, histogram, exception pressure, shadowed pairs, '
	                                   'member divergence')
	s.add_argument('font')
	s.add_argument('--analysis', nargs='+', help='analyses to run: %s (default: all)'
	               % ', '.join(k for k, _t in kan.ANALYSES))
	s.add_argument('--master', help='one master (default: all)')
	for key in kan.OPTION_DEFAULTS:
		if key != 'master':
			s.add_argument('--' + key, type=int, help='default %s' % kan.OPTION_DEFAULTS[key])
	s.add_argument('--json', help='also write the results as JSON to this file')
	s.set_defaults(func=cmd_analyze)

	s = sub.add_parser('job', help='DTL KernMaster job: KRN per master + CLA')
	s.add_argument('font')
	s.add_argument('folder')
	s.add_argument('--composition', help='composition JSON (FontRig Kern Job Composer format)')
	s.add_argument('--font-kerning', action='store_true', help='the pairs each master has now')
	s.add_argument('--master')
	s.add_argument('--no-groups', action='store_true', help='compositions: keep glyphs (not their groups)')
	s.add_argument('--preview', action='store_true', help='print what the files would hold, write nothing')
	s.set_defaults(func=cmd_job)

	s = sub.add_parser('rules', help='kerning by analogy (FL Copy Kerning rule file)')
	s.add_argument('font')
	s.add_argument('rules')
	s.add_argument('--no-class', action='store_true', help='write destination glyphs as glyphs, not their groups')
	s.add_argument('--master')
	s.add_argument('--dry-run', action='store_true')
	s.set_defaults(func=cmd_rules)

	s = sub.add_parser('pairs', help='list / explain pairs, bulk operations, master to master, locks')
	s.add_argument('font')
	s.add_argument('--query', help='search, as in the Pairs tab: T|*  @O|@A  <-50  missing:Bold  kind:GG')
	s.add_argument('--explain', metavar='A|V', help='how the font finds the value of a glyph pair')
	s.add_argument('--limit', type=int, default=200, help='rows listed (default 200)')
	s.add_argument('--op', choices=[k for k, _t in ka.BULK_OPS], help='bulk operation on the found pairs')
	s.add_argument('--value', type=float)
	s.add_argument('--value2', type=float, help='replace: the new value')
	s.add_argument('--master', nargs='+', help='masters the operation changes (default: all)')
	s.add_argument('--copy', nargs=2, metavar=('FROM', 'TO'), help='master to master (the found pairs with --query)')
	s.add_argument('--k', type=float, default=1., help='copy: multiply')
	s.add_argument('--c', type=float, default=0., help='copy: add')
	s.add_argument('--interpolate', nargs=4, metavar=('A', 'B', 'T', 'TO'))
	s.add_argument('--mode', choices=[k for k, _t in ka.COPY_MODES])
	s.add_argument('--lock', action='store_true', help='lock the found pairs')
	s.add_argument('--unlock', action='store_true')
	s.add_argument('--apply', action='store_true', help='write the changes')
	s.set_defaults(func=cmd_pairs)

	s = sub.add_parser('groups', help='kerning groups: list, members, auto, validate, leaders, edits')
	s.add_argument('font')
	s.add_argument('--side', choices=list(km.SIDES), default=km.LEFT)
	s.add_argument('--members', metavar='NAME')
	s.add_argument('--auto', action='store_true', help='groups from composites and suffixes')
	s.add_argument('--validate', action='store_true')
	s.add_argument('--leaders-from', metavar='CLA', help='leaders from a CLA file (written at once)')
	s.add_argument('--leader', nargs=2, metavar=('NAME', 'GLYPH'), help='set a leader (written at once)')
	s.add_argument('--new', nargs='+', metavar='NAME', help='NAME GLYPH...: a new group')
	s.add_argument('--move', nargs='+', metavar='GLYPH')
	s.add_argument('--to', metavar='NAME')
	s.add_argument('--out', nargs='+', metavar='GLYPH', help='glyphs out of their groups')
	s.add_argument('--rename', nargs=2, metavar=('OLD', 'NEW'))
	s.add_argument('--delete', nargs='+', metavar='NAME')
	s.add_argument('--merge', nargs='+', metavar='NAME', help='merge into the first')
	s.add_argument('--no-preserve', action='store_true', help='glyphs take the values of their new groups')
	s.add_argument('--apply', action='store_true', help='write the group edits')
	s.set_defaults(func=cmd_groups)

	s = sub.add_parser('restore', help='bring back a snapshot (the latest by default)')
	s.add_argument('font')
	s.add_argument('--list', action='store_true')
	s.add_argument('--snapshot')
	s.set_defaults(func=cmd_restore)
	return p


def main(argv=None):
	p = parser()
	args = p.parse_args(argv)
	if not getattr(args, 'func', None):
		p.print_help()
		return 1
	try:
		return args.func(args)
	except (IOError, OSError, ValueError) as e:
		_out('%s: %s' % (PROG, e), sys.stderr)
		return 1


if __name__ == '__main__':
	sys.exit(main())
