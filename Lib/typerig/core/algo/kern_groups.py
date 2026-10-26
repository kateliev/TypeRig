# MODULE: TypeRig / Core / Algo / Kern Groups
# -----------------------------------------------------------
# Kerning group edits as ChangeSets, with "preserve rendering": after a
# group change, exceptions are written so that every glyph pair the edit
# touches keeps the value it had (the edit changes the structure, not the
# spacing). Without it the members take the values of their new groups.
#
# A glyph is in at most one group per side (Glyphs keeps the group on the
# glyph); putting it in a group takes it out of its old group.
#
#   plan_members(kset, side, name, members, preserve)   set a group's members (new group too)
#   plan_move(kset, side, glyphs, name, preserve)       glyphs into a group (None: out of any group)
#   plan_rename(kset, side, old, new)                   group + every pair key, all masters
#   plan_delete(kset, side, name, preserve)             group + its pairs (preserve: as exceptions)
#   plan_merge(kset, side, names, new, preserve)        groups into one
#   group_rows(kset, side) / validate(kset, glyphs)     tables and checks for the window
#   leaders_from_cla(classes, kset)                     leaders read from a CLA file
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2026  (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.algo.kern_model import (ChangeSet, KernSet, LEFT, RIGHT, SIDES, is_group, group_name,
                                         group_key, apply)

__version__ = '0.1.0'

OTHER = {LEFT: RIGHT, RIGHT: LEFT}
JOB_SUFFIX = {LEFT: '_1', RIGHT: '_2'}	# CLA side suffixes (kern_actions.JOB_SIDE_SUFFIX)


# - Helpers ------------------------------------------------------------------
def _effective(kset, base):
	'''A copy of the kerning with a pending ChangeSet on top.'''
	view = kset.copy()
	if base is not None and not base.is_empty():
		apply(view, base)
	return view


def _row_values(kset, master, glyph, side):
	'''{other glyph: value} for every glyph pair of glyph on side that a stored pair covers.'''
	table = kset.pairs.get(master, {})
	keys = {glyph, kset.side_key(glyph, side)}
	other = OTHER[side]
	out = {}
	for pair in table:
		if pair[0 if side == LEFT else 1] not in keys:
			continue
		for g in kset.members(pair[1 if side == LEFT else 0], other):
			a, b = (glyph, g) if side == LEFT else (g, glyph)
			out[g] = kset.resolve(master, a, b)[0]
	return out


def _preserve(before, after, cs, touched, label='preserve'):
	'''Add exceptions to cs (already applied to after) so that every glyph
	pair of the touched glyphs ({side: [glyphs]}) renders as in before.
	Returns the number of exceptions written.'''
	written = 0
	for master in before.masters:
		for side in SIDES:
			for glyph in touched.get(side, []):
				want = _row_values(before, master, glyph, side)
				got = _row_values(after, master, glyph, side)
				others = set(want) | set(got)
				# glyph against each key of the other side (group or glyph), as after;
				# a group key is judged on all its members (a group fix reaches them all)
				keys = set(after.side_key(g, OTHER[side]) for g in others)
				for key in sorted(keys):
					members = after.members(key, OTHER[side])
					values = [_pair_value(before, master, glyph, g, side) for g in members]
					now = [_pair_value(after, master, glyph, g, side) for g in members]
					if values == now:
						continue
					pair = (glyph, key) if side == LEFT else (key, glyph)
					if is_group(key) and len(set(values)) == 1:
						_set(after, cs, master, pair, values[0])
						written += 1
					# Members with a pair of higher precedence (glyph + group of the
					# other side) are not reached by a group fix: glyph + glyph for them
					for g, value in zip(members, values):
						if _pair_value(after, master, glyph, g, side) != value:
							_set(after, cs, master, (glyph, g) if side == LEFT else (g, glyph), value)
							written += 1
	return written


def _pair_value(kset, master, glyph, other, side):
	a, b = (glyph, other) if side == LEFT else (other, glyph)
	return kset.resolve(master, a, b)[0]


def _set(view, cs, master, pair, value):
	if cs.set(master, pair, value, view.locks):
		view.table(master)[pair] = int(value)


def _group_change(kset, cs, side, name, members):
	'''Record a group's new members in cs and apply it to kset (a view copy).'''
	cs.set_group(side, name, members)
	if members is None:
		kset.groups[side].pop(name, None)
	else:
		kset.groups[side][name] = list(members)
	kset.touch_groups()


def _take_out(view, cs, side, glyphs, keep=None):
	'''Remove glyphs from their current groups on a side (except keep).'''
	for glyph in glyphs:
		old = view.group_of(glyph, side)
		if old is not None and old != keep:
			_group_change(view, cs, side, old, [g for g in view.groups[side][old] if g != glyph])


# - Plans --------------------------------------------------------------------
def plan_members(kset, side, name, members, preserve=True, base=None):
	'''Set the members of group name on side (creates it). Glyphs leave their old groups.'''
	before = _effective(kset, base)
	view = before.copy()
	cs = ChangeSet('group %s' % name)
	old = list(view.groups[side].get(name, []))
	members = [g for g in dict.fromkeys(members)]
	_take_out(view, cs, side, members, keep=name)
	_group_change(view, cs, side, name, members)
	touched = sorted(set(old) ^ set(members)) if old else sorted(members)
	if preserve:
		_preserve(before, view, cs, {side: touched})
	cs.log.append('Group %s (%s): %d members%s' % (name, side, len(members), ', rendering kept' if preserve else ''))
	return cs


def plan_move(kset, side, glyphs, name, preserve=True, base=None):
	'''Glyphs into group name (None: out of their groups).'''
	before = _effective(kset, base)
	view = before.copy()
	cs = ChangeSet('move')
	glyphs = list(dict.fromkeys(glyphs))
	_take_out(view, cs, side, glyphs, keep=name)
	if name is not None:
		members = list(view.groups[side].get(name, []))
		_group_change(view, cs, side, name, members + [g for g in glyphs if g not in members])
	if preserve:
		_preserve(before, view, cs, {side: glyphs})
	cs.log.append('%d glyph(s) %s%s' % (len(glyphs), 'to %s' % name if name else 'out of their groups',
	                                    ', rendering kept' if preserve else ''))
	return cs


def plan_rename(kset, side, old, new, base=None):
	'''Rename a group and every pair key that uses it (all masters). Rendering never changes.'''
	view = _effective(kset, base)
	cs = ChangeSet('rename %s > %s' % (old, new))
	if old not in view.groups[side] or not new or new in view.groups[side]:
		cs.log.append('Rename refused: %s' % ('no group %s' % old if old not in view.groups[side]
		                                      else 'a group %s exists' % new if new else 'empty name'))
		return cs
	cs.set_group(side, new, view.groups[side][old])
	cs.set_group(side, old, None)
	ok, nk = group_key(old), group_key(new)
	pos = 0 if side == LEFT else 1
	for master in view.masters:
		for pair, value in view.pairs[master].items():
			if pair[pos] == ok:
				new_pair = (nk, pair[1]) if pos == 0 else (pair[0], nk)
				cs.remove(master, pair)
				cs.set(master, new_pair, value)
	cs.log.append('Renamed %s to %s (%s)' % (old, new, side))
	return cs


def plan_delete(kset, side, name, preserve=True, base=None):
	'''Delete a group and the pairs that use it; preserve: its members keep their values as exceptions.'''
	before = _effective(kset, base)
	view = before.copy()
	cs = ChangeSet('delete %s' % name)
	members = list(view.groups[side].get(name, []))
	key = group_key(name)
	pos = 0 if side == LEFT else 1
	for master in view.masters:
		for pair in list(view.pairs[master]):
			if pair[pos] == key and cs.remove(master, pair, view.locks):
				view.pairs[master].pop(pair)
	_group_change(view, cs, side, name, None)
	if preserve:
		_preserve(before, view, cs, {side: members})
	cs.log.append('Deleted %s (%s)%s' % (name, side, ', members keep their values' if preserve else ''))
	return cs


def plan_merge(kset, side, names, new, preserve=True, base=None):
	'''Merge groups into new (may be one of them). Pairs of the merged groups go,
	the kept group's pairs stay; preserve keeps every member's values.'''
	before = _effective(kset, base)
	view = before.copy()
	cs = ChangeSet('merge > %s' % new)
	members = []
	for name in names:
		members += [g for g in view.groups[side].get(name, []) if g not in members]
	pos = 0 if side == LEFT else 1
	for name in names:
		if name == new:
			continue
		key = group_key(name)
		for master in view.masters:
			for pair in list(view.pairs[master]):
				if pair[pos] == key and cs.remove(master, pair, view.locks):
					view.pairs[master].pop(pair)
		_group_change(view, cs, side, name, None)
	_group_change(view, cs, side, new, members)
	if preserve:
		_preserve(before, view, cs, {side: members})
	cs.log.append('Merged %s into %s (%s)' % (', '.join(names), new, side))
	return cs


# - Tables and checks ----------------------------------------------------------------
def group_rows(kset, side):
	'''[{'name', 'members', 'pairs', 'leader'}] for the groups of a side.'''
	pos = 0 if side == LEFT else 1
	counts = {}
	for table in kset.pairs.values():
		for pair in table:
			if is_group(pair[pos]):
				counts[group_name(pair[pos])] = counts.get(group_name(pair[pos]), 0) + 1
	return [{'name': name, 'members': len(members), 'pairs': counts.get(name, 0),
	         'leader': kset.leader(name, side)} for name, members in sorted(kset.groups[side].items())]


def validate(kset, glyphs=None):
	'''Problems: {'conflicts': {side: {glyph: [groups]}}, 'empty': [(side, name)],
	'missing': [(side, name, glyph)], 'glyph_named': [(side, name)], 'orphans': [(master, pair)]}.'''
	glyphs = set(glyphs) if glyphs is not None else None
	out = {'conflicts': kset.conflicts(), 'empty': [], 'missing': [], 'glyph_named': [], 'orphans': []}
	for side in SIDES:
		for name, members in sorted(kset.groups[side].items()):
			if not members:
				out['empty'].append((side, name))
			if glyphs is not None:
				out['missing'] += [(side, name, g) for g in members if g not in glyphs]
				if name in glyphs and name not in members:
					out['glyph_named'].append((side, name))
	for master in kset.masters:
		for pair in kset.pairs[master]:
			for key, side in zip(pair, SIDES):
				if is_group(key) and group_name(key) not in kset.groups[side]:
					out['orphans'].append((master, pair))
					break
				if not is_group(key) and glyphs is not None and key not in glyphs:
					out['orphans'].append((master, pair))
					break
	return out


def validate_text(report):
	lines = []
	conflicts = sum(len(v) for v in report['conflicts'].values())
	lines.append('Glyphs in two groups of one side: %d' % conflicts)
	for side in SIDES:
		for glyph, names in sorted(report['conflicts'][side].items())[:20]:
			lines.append('  %s %s: %s' % (side, glyph, ', '.join(names)))
	lines.append('Empty groups: %d%s' % (len(report['empty']), ('  ' + ', '.join('%s %s' % e for e in report['empty'][:20]))
	                                     if report['empty'] else ''))
	lines.append('Members not in the font: %d%s' % (len(report['missing']), ('  ' + ', '.join(
		'%s:%s' % (n, g) for _s, n, g in report['missing'][:20])) if report['missing'] else ''))
	lines.append('Groups named like a glyph that is not a member: %d%s' % (len(report['glyph_named']), (
		'  ' + ', '.join(n for _s, n in report['glyph_named'][:20])) if report['glyph_named'] else ''))
	lines.append('Pairs with a missing group or glyph: %d%s' % (len(report['orphans']), ('  ' + ', '.join(
		'%s %s (%s)' % (p[0], p[1], m) for m, p in report['orphans'][:12])) if report['orphans'] else ''))
	return '\n'.join(lines) + '\n'


def leaders_from_cla(classes, kset):
	'''Leaders from CLA classes [(name, members)]: the first member, for the
	group of the same name (a _1 / _2 suffix picks the side; no suffix: both
	sides). Returns ({side: {group: glyph}}, [skipped (name, reason)]).'''
	out = {LEFT: {}, RIGHT: {}}
	skipped = []
	for name, members in classes:
		if not members:
			continue
		sides = list(SIDES)
		for side in SIDES:
			if name.endswith(JOB_SUFFIX[side]) and name[:-2] in kset.groups[side]:
				sides, name = [side], name[:-2]
				break
		found = False
		for side in sides:
			group = kset.groups[side].get(name)
			if group is None:
				continue
			found = True
			if members[0] in group:
				out[side][name] = members[0]
			else:
				skipped.append((name, 'leader %s is not a member' % members[0]))
		if not found:
			skipped.append((name, 'no such group'))
	return out, skipped
