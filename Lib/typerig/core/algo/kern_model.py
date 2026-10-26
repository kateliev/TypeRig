# MODULE: TypeRig / Core / Algo / Kern Model
# -----------------------------------------------------------
# Host-neutral kerning model for TR Kern: per-master pair tables, one
# group set, pair resolution (glyph-glyph > glyph-group > group-glyph >
# group-group), flattening, and the ChangeSet every operation returns.
#
# Keys (same as delta_kerning_actions): '@name' is a kerning group, its
# side follows from its place in the pair; any other key is a glyph.
# Groups: {'left': {name: [glyphs]}, 'right': {name: [glyphs]}}; 'left'
# groups are used on the first side of a pair. A FontLab KernBothSide
# class is the same name on both sides.
#
#   KernSet                       masters, pairs, groups, locks, rules, sidebearings
#   KernSet.resolve(m, a, b)      (value, key, level) as the font renders it
#   KernSet.explain(a, b)         the whole chain, per master
#   KernSet.flatten(m)            {(glyph, glyph): value} for every covered pair
#   ChangeSet                     planned pair / group changes + report
#   apply(kset, cs)               write a ChangeSet, returns the undo ChangeSet
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

import copy

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
LEFT, RIGHT = 'left', 'right'
SIDES = (LEFT, RIGHT)
GROUP_MARK = '@'
FORMAT = 1

# Resolution levels, in the order a pair is looked up
LEVEL_GG, LEVEL_GC, LEVEL_CG, LEVEL_CC = 'GG', 'GC', 'CG', 'CC'
LEVELS = (LEVEL_GG, LEVEL_GC, LEVEL_CG, LEVEL_CC)


# - Keys -------------------------------------------------------------------
def is_group(key):
	return str(key).startswith(GROUP_MARK)


def group_name(key):
	return str(key)[len(GROUP_MARK):]


def group_key(name):
	return GROUP_MARK + str(name)


def pair_kind(pair):
	'''Kind of a stored pair: GG glyph-glyph, GC glyph-group, CG group-glyph, CC group-group.'''
	left, right = pair
	return ('C' if is_group(left) else 'G') + ('C' if is_group(right) else 'G')


def key_glyph(name, members):
	'''The member that stands for a group: the one named like the group,
	else the one named like the group without its suffix, else the first.'''
	if not members:
		return None
	if name in members:
		return name
	base = str(name).split('.')[0].split('_')[0]
	if base in members:
		return base
	return members[0]


def to_int(value):
	'''Kerning values are stored as int; floats round half to even (Python round).'''
	return int(round(float(value)))


# - Model ------------------------------------------------------------------
class KernSet(object):
	'''Kerning of a font: one pair table per master and one group set.

	Attributes:
		masters (list)       : master names, in font order
		pairs (dict)         : {master: {(left, right): int}}
		groups (dict)        : {'left': {name: [glyphs]}, 'right': {name: [glyphs]}}
		locks (set)          : pair keys that operations must never change (all masters)
		rules (list)         : stored analogy rule sets (dicts), kept for the host / later phases
		sidebearings (dict)  : {master: {glyph: (lsb, rsb)}} at snapshot time, for spacing compensation
	'''
	def __init__(self, masters=None, pairs=None, groups=None, locks=None, rules=None, sidebearings=None):
		self.masters = list(masters or [])
		self.pairs = {m: {} for m in self.masters}
		for master, table in (pairs or {}).items():
			if master not in self.pairs:
				self.masters.append(master)
			self.pairs[master] = {tuple(k): to_int(v) for k, v in table.items()}
		self.groups = {LEFT: {}, RIGHT: {}}
		for side in SIDES:
			for name, members in ((groups or {}).get(side) or {}).items():
				self.groups[side][str(name)] = [str(g) for g in members]
		self.locks = set(tuple(k) for k in (locks or ()))
		self.rules = list(rules or [])
		self.sidebearings = copy.deepcopy(sidebearings or {})
		self._inverse = None

	def __repr__(self):
		return '<KernSet: %d masters, %d pairs, %d/%d groups>' % (
			len(self.masters), sum(len(t) for t in self.pairs.values()),
			len(self.groups[LEFT]), len(self.groups[RIGHT]))

	# -- Groups ---------------------------------------------------------------
	def touch_groups(self):
		'''Call after editing self.groups directly: drops the cached glyph -> group index.'''
		self._inverse = None

	def inverse(self):
		'''{'left': {glyph: group}, 'right': {glyph: group}}. A glyph in two
		groups of one side keeps the first (see conflicts()).'''
		if self._inverse is None:
			inv = {LEFT: {}, RIGHT: {}}
			for side in SIDES:
				for name, members in self.groups[side].items():
					for glyph in members:
						inv[side].setdefault(glyph, name)
			self._inverse = inv
		return self._inverse

	def group_of(self, glyph, side):
		'''Group name of glyph on a side, or None.'''
		return self.inverse()[side].get(glyph)

	def side_key(self, glyph, side):
		'''The key a glyph kerns as on a side: '@group' or the glyph itself.'''
		name = self.group_of(glyph, side)
		return group_key(name) if name is not None else glyph

	def members(self, key, side):
		'''Glyphs a key stands for on a side: a group's members, or [glyph].'''
		if is_group(key):
			return list(self.groups[side].get(group_name(key), []))
		return [key]

	def conflicts(self):
		'''Glyphs in more than one group of the same side: {side: {glyph: [groups]}}.'''
		out = {LEFT: {}, RIGHT: {}}
		for side in SIDES:
			seen = {}
			for name, members in self.groups[side].items():
				for glyph in members:
					seen.setdefault(glyph, []).append(name)
			out[side] = {g: names for g, names in seen.items() if len(names) > 1}
		return out

	# -- Resolution -----------------------------------------------------------
	def resolve(self, master, a, b, table=None):
		'''Value of glyph pair (a, b) as the font renders it.
		Returns (value, key, level); (0, None, None) when nothing applies.'''
		table = self.pairs.get(master, {}) if table is None else table
		la, rb = self.side_key(a, LEFT), self.side_key(b, RIGHT)
		for key, level in (((a, b), LEVEL_GG), ((a, rb), LEVEL_GC), ((la, b), LEVEL_CG), ((la, rb), LEVEL_CC)):
			if level != LEVEL_GG and key == (a, b):
				continue	# side without a group: the glyph-glyph lookup already covered it
			if key in table:
				return table[key], key, level
		return 0, None, None

	def explain(self, a, b):
		'''The whole lookup chain for glyph pair (a, b), per master:
		{master: {'value', 'key', 'level', 'chain': [(level, key, value or None)]}}.'''
		la, rb = self.side_key(a, LEFT), self.side_key(b, RIGHT)
		chain_keys = [(LEVEL_GG, (a, b)), (LEVEL_GC, (a, rb)), (LEVEL_CG, (la, b)), (LEVEL_CC, (la, rb))]
		out = {}
		for master in self.masters:
			table = self.pairs[master]
			value, key, level = self.resolve(master, a, b)
			out[master] = {
				'value': value, 'key': key, 'level': level,
				'chain': [(lvl, k, table.get(k)) for lvl, k in chain_keys],
			}
		return out

	def flatten(self, master, table=None, keep_zero=False):
		'''Every glyph pair the table covers, with its rendered value:
		{(glyph, glyph): value}. Zero results are dropped unless keep_zero.'''
		table = self.pairs.get(master, {}) if table is None else table
		candidates = set()
		for left, right in table:
			for a in self.members(left, LEFT):
				for b in self.members(right, RIGHT):
					candidates.add((a, b))
		out = {}
		for a, b in candidates:
			value = self.resolve(master, a, b, table)[0]
			if value or keep_zero:
				out[(a, b)] = value
		return out

	# -- Masters --------------------------------------------------------------
	def table(self, master):
		'''Pair table of a master (created empty when missing).'''
		if master not in self.pairs:
			self.masters.append(master)
			self.pairs[master] = {}
		return self.pairs[master]

	# -- Serialization --------------------------------------------------------
	def to_dict(self, masters=None):
		'''JSON-ready dict; pair keys as [left, right, value] lists. masters limits the tables.'''
		masters = self.masters if masters is None else [m for m in self.masters if m in masters]
		return {
			'format': FORMAT,
			'masters': list(masters),
			'pairs': {m: [[l, r, v] for (l, r), v in sorted(self.pairs[m].items())] for m in masters},
			'groups': copy.deepcopy(self.groups),
			'locks': sorted([list(k) for k in self.locks]),
			'rules': copy.deepcopy(self.rules),
			'sidebearings': {m: {g: list(sb) for g, sb in t.items()}
			                 for m, t in self.sidebearings.items() if m in masters},
		}

	@classmethod
	def from_dict(cls, data):
		data = data or {}
		pairs = {m: {(l, r): v for l, r, v in rows} for m, rows in (data.get('pairs') or {}).items()}
		sidebearings = {m: {g: tuple(sb) for g, sb in t.items()} for m, t in (data.get('sidebearings') or {}).items()}
		return cls(masters=data.get('masters'), pairs=pairs, groups=data.get('groups'),
		           locks=[tuple(k) for k in (data.get('locks') or [])], rules=data.get('rules'),
		           sidebearings=sidebearings)

	def copy(self):
		return KernSet.from_dict(self.to_dict())


# - ChangeSet --------------------------------------------------------------
class ChangeSet(object):
	'''Planned changes: what an operation wants to write, before the host
	writes it. Hosts preview it, then apply.

	Attributes:
		pairs (dict)   : {master: {'set': {pair: value}, 'remove': set(pairs)}}
		groups (dict)  : {'left': {name: [members] or None}, 'right': {...}}; None removes
		locked (list)  : (master, pair) the operation wanted to change but is locked
		log (list)     : report lines
		label (str)    : operation name (snapshot / history)
	'''
	def __init__(self, label=''):
		self.label = label
		self.pairs = {}
		self.groups = {LEFT: {}, RIGHT: {}}
		self.locked = []
		self.log = []

	def __repr__(self):
		return '<ChangeSet %s: %d set, %d remove, %d group, %d locked>' % (
			self.label or '-', self.count('set'), self.count('remove'),
			len(self.groups[LEFT]) + len(self.groups[RIGHT]), len(self.locked))

	def _master(self, master):
		return self.pairs.setdefault(master, {'set': {}, 'remove': set()})

	def set(self, master, pair, value, locks=()):
		pair = tuple(pair)
		if pair in locks:
			self.locked.append((master, pair))
			return False
		entry = self._master(master)
		entry['remove'].discard(pair)
		entry['set'][pair] = to_int(value)
		return True

	def remove(self, master, pair, locks=()):
		pair = tuple(pair)
		if pair in locks:
			self.locked.append((master, pair))
			return False
		entry = self._master(master)
		entry['set'].pop(pair, None)
		entry['remove'].add(pair)
		return True

	def set_group(self, side, name, members):
		self.groups[side][name] = None if members is None else list(members)

	def count(self, what):
		return sum(len(e[what]) for e in self.pairs.values())

	def is_empty(self):
		return not (self.count('set') or self.count('remove') or self.groups[LEFT] or self.groups[RIGHT])

	def summary(self, kset):
		'''{master: {'added', 'changed', 'unchanged', 'removed'}} against the current kerning.'''
		out = {}
		for master, entry in self.pairs.items():
			table = kset.pairs.get(master, {})
			counts = {'added': 0, 'changed': 0, 'unchanged': 0, 'removed': 0}
			for pair, value in entry['set'].items():
				if pair not in table:
					counts['added'] += 1
				elif table[pair] != value:
					counts['changed'] += 1
				else:
					counts['unchanged'] += 1
			counts['removed'] = sum(1 for p in entry['remove'] if p in table)
			out[master] = counts
		return out

	def touched_masters(self):
		return [m for m, e in self.pairs.items() if e['set'] or e['remove']]


def apply(kset, cs):
	'''Write a ChangeSet into a KernSet (groups first, then pairs).
	Returns the undo ChangeSet that restores the previous state.'''
	undo = ChangeSet('undo ' + cs.label)
	for side in SIDES:
		for name, members in cs.groups[side].items():
			old = kset.groups[side].get(name)
			undo.set_group(side, name, None if old is None else list(old))
			if members is None:
				kset.groups[side].pop(name, None)
			else:
				kset.groups[side][name] = list(members)
	kset.touch_groups()
	for master, entry in cs.pairs.items():
		table = kset.table(master)
		for pair in entry['remove']:
			if pair in table:
				undo.set(master, pair, table.pop(pair))
		for pair, value in entry['set'].items():
			if pair in table:
				undo.set(master, pair, table[pair])
			else:
				undo.remove(master, pair)
			table[pair] = value
	return undo


def diff(before, after, masters=None):
	'''ChangeSet that turns pair tables before into after: {master: table} each.'''
	cs = ChangeSet('diff')
	for master in (masters or sorted(set(before) | set(after))):
		old, new = before.get(master, {}), after.get(master, {})
		for pair, value in new.items():
			if old.get(pair) != value:
				cs.set(master, pair, value)
		for pair in old:
			if pair not in new:
				cs.remove(master, pair)
	return cs
