# MODULE: TypeRig / Core / Algo / Kern Analyze
# -----------------------------------------------------------
# TR Kern analytics (Analyze tab, tr-kern analyze): read-only views that
# show problems in a kerning table. Nothing here writes: an analysis
# returns a result, report_tree() turns it into a tree (analysis > section
# > finding), and a node may carry a link (a Pairs query and the stored
# pairs behind it) for the host to show. tree_text() renders trees as plain
# text (tr-kern, Copy report).
# All values are resolved in the font's own lookup order (glyph + glyph >
# glyph + group > group + glyph > group + group), as everywhere in TR Kern.
#
#   health       per master: pairs by kind, exception ratio, class-pair
#                fill, min / max / median, zero pairs
#   histogram    per master: value bins, spikes, step mix (values off the
#                font's grid: hand edits in an autokerned table), extremes,
#                a master whose distribution shape differs from the others
#   pressure     group x group regions where many glyph pairs are taken by
#                exceptions; the glyphs that own exceptions against many
#                groups (often a glyph in the wrong group)
#   shadowed     class pairs (and glyph + group pairs) that never apply:
#                every glyph pair they reach is taken by a more specific
#                pair (shadowed), or most of them are (fragile)
#   divergence   group members whose kerning against the other side differs
#                from their group's median (badly grouped), with the group
#                they are closer to
#   rules        rule lint: the font's rule sets in check mode (a pair that
#                renders away from what its rule gives)
#   consistency  pairs that should agree: mirrored punctuation around
#                symmetric glyphs, small caps vs capitals (by the master's
#                ratio), Latin vs Cyrillic / Greek lookalikes, tabular figures
#   scope        pairs across scripts (never apply), groups of several
#                scripts, small caps against lowercase, glyphs with no script
# rules / consistency / scope take a host context (see Context).
#
#   ANALYSES, options(data), analyze(kset, key, opts, context) -> result
#   count(key, result), report_tree(key, result) -> node tree, tree_text(roots)
#   to_data(result) -> JSON-ready (tuples -> lists, keys -> str)
#   Node: {'title', 'detail', 'kind', 'link', 'children', 'fix'}; link: {'query', 'pairs'}
#   fix_items(nodes), fix_summary(items), plan_fixes(kset, items, choices) -> (ChangeSet, log)
#   (the analyses never write; a fix is a separate, explicit step that only plans changes)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.algo.kern_model import LEFT, RIGHT, is_group, group_name, pair_kind

__version__ = '0.4.0'

# - Init -------------------------------------------------------------------
ANALYSES = (	# (key, title)
	('health', 'Health card'),
	('histogram', 'Value histogram'),
	('pressure', 'Exception pressure'),
	('shadowed', 'Shadowed and fragile pairs'),
	('divergence', 'Member divergence'),
	('rules', 'Rule lint'),
	('consistency', 'Consistency families'),
	('scope', 'Kerning scope'),
)
OPTION_DEFAULTS = {
	'master': '',		# '' = every master
	'bin': 10,			# histogram bin width (units)
	'extreme': 150,		# histogram: |value| over this is extreme (units)
	'spike': 3,			# histogram: a bin this many times its neighbours' median is a spike
	'shape': 25,		# histogram: a master whose tails differ by more than this % of the IQR from the others
	'pressure': 30,		# pressure: regions with at least this % of glyph pairs taken by exceptions
	'culprit': 3,		# pressure: glyphs with exceptions against at least this many groups / glyphs
	'fragile': 50,		# shadowed: a pair taken over for at least this % of its glyph pairs is fragile
	'divergence': 15,	# divergence: mean distance (units) from the group median that flags a member
	'members': 3,		# divergence: groups with fewer members are not judged
	'tolerance': 5,		# rules, consistency: pairs that should agree may differ this much (units)
	'symmetric': 'AHIMOTUVWXYovwx',	# consistency: characters whose two sides mirror each other
}
STR_OPTIONS = ('master', 'symmetric')
KINDS = ('CC', 'CG', 'GC', 'GG')
SPIKE_MIN = 5			# a spike needs at least this many values
GRID_SHARE = .8			# the font's grid: the coarsest step (10, 5) at least this share of values sit on
SHAPE_QUANTILES = (.1, .25, .5, .75, .9)
SHAPE_MIN = 10			# shape: masters with fewer nonzero values are not compared
SHAPE_OUTLIER = 3		# shape: a flagged master is also this many times the family's median distance away
LINK_PAIRS = 200		# pairs carried by one link at most (the query stays short)
_ORDER = {'GG': 0, 'GC': 1, 'CG': 2, 'CC': 3}


def options(data=None):
	out = dict(OPTION_DEFAULTS)
	out.update({k: v for k, v in (data or {}).items() if k in OPTION_DEFAULTS})
	for key, default in OPTION_DEFAULTS.items():
		if key in STR_OPTIONS:
			out[key] = str(out[key] or '')
			continue
		try:
			out[key] = max(0, int(float(out[key] or 0)))
		except (TypeError, ValueError):
			out[key] = default
	out['bin'] = max(1, out['bin'])
	out['members'] = max(2, out['members'])
	return out


# - Helpers -------------------------------------------------------------------
def _masters(kset, opts):
	master = opts.get('master')
	return [master] if master in kset.masters else list(kset.masters)


def _median(values):
	values = sorted(values)
	n = len(values)
	if not n:
		return 0
	mid = n // 2
	return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2.


def _weighted_median(samples):
	'''Median of (value, weight) samples: the value where half of the weight is reached.'''
	samples = sorted(samples)
	half = sum(w for _v, w in samples) / 2.
	run = 0.
	for value, weight in samples:
		run += weight
		if run >= half:
			return value
	return samples[-1][0] if samples else 0


def _quantile(values, q):
	'''Linear-interpolated quantile of sorted values.'''
	if not values:
		return 0
	pos = (len(values) - 1) * q
	lo = int(pos)
	hi = min(lo + 1, len(values) - 1)
	return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _bucket(kset, pair):
	'''The group pair region of a stored pair: (left key, right key) of its sides' groups.'''
	left = pair[0] if is_group(pair[0]) else kset.side_key(pair[0], LEFT)
	right = pair[1] if is_group(pair[1]) else kset.side_key(pair[1], RIGHT)
	return left, right


def _cells(kset, pair):
	return [(a, b) for a in kset.members(pair[0], LEFT) for b in kset.members(pair[1], RIGHT)]


def link(pairs, query=None):
	'''A report link: the stored pairs (in order, no duplicates, at most LINK_PAIRS)
	and a Pairs query that shows them (one clause per pair).'''
	seen, out = set(), []
	for pair in pairs:
		pair = tuple(pair)
		if pair not in seen:
			seen.add(pair)
			out.append(pair)
		if len(out) >= LINK_PAIRS:
			break
	if query is None:
		query = '; '.join('%s|%s' % (a, b) for a, b in out)
	return {'query': query, 'pairs': out}


# - Health card ---------------------------------------------------------------------
def health(kset, opts=None):
	'''{master: {'pairs', 'kinds': {kind: n}, 'exceptions', 'ratio', 'fill', 'class_pairs', 'regions',
	'min', 'max', 'median', 'mean_abs', 'zeros'}} — ratio = exceptions / class pairs (None without
	class pairs); fill = class pairs / (left groups x right groups) (None without groups).'''
	opts = options(opts)
	n_left = len([g for g, m in kset.groups[LEFT].items() if m])
	n_right = len([g for g, m in kset.groups[RIGHT].items() if m])
	regions = n_left * n_right
	out = {}
	for master in _masters(kset, opts):
		table = kset.pairs[master]
		kinds = dict((k, 0) for k in KINDS)
		for pair in table:
			kinds[pair_kind(pair)] += 1
		values = sorted(table.values())
		cc = kinds['CC']
		exceptions = len(table) - cc
		out[master] = {
			'pairs': len(table), 'kinds': kinds, 'exceptions': exceptions,
			'ratio': (exceptions / float(cc)) if cc else None,
			'class_pairs': cc, 'regions': regions,
			'fill': (cc / float(regions)) if regions else None,
			'min': values[0] if values else 0, 'max': values[-1] if values else 0,
			'median': _median(values), 'mean_abs': (sum(abs(v) for v in values) / float(len(values))) if values else 0,
			'zeros': sum(1 for v in values if v == 0),
		}
	return out


# - Histogram ------------------------------------------------------------------------
def _grid(values):
	'''The font's value grid: 10 or 5 when at least GRID_SHARE of the values sit on it, else 1.'''
	if not values:
		return 1
	for step in (10, 5):
		if sum(1 for v in values if v % step == 0) >= GRID_SHARE * len(values):
			return step
	return 1


def histogram(kset, opts=None):
	'''{'masters': {master: {...}}, 'shape': {master: distance}, 'shape_flags': [master]}.
	Per master: 'bins' {low: n} (zero values left out), 'steps' {10: n, 5: n, 1: n} (nonzero values by
	the coarsest grid they sit on), 'grid', 'off_grid' [(pair, value)], 'spikes' [(low, n, neighbours
	median)], 'extremes' [(pair, value)], 'quantiles' (standardised: (q - median) / IQR, so a master that only kerns
	tighter or looser has the same shape). Shape: masters with SHAPE_MIN values or more;
	flags need three such masters (with two there is no telling which one differs).'''
	opts = options(opts)
	width = opts['bin']
	result = {'masters': {}, 'shape': {}, 'shape_flags': []}
	for master in _masters(kset, opts):
		table = kset.pairs[master]
		nonzero = [(p, v) for p, v in table.items() if v]
		values = [v for _p, v in nonzero]
		bins = {}
		for v in values:
			low = (v // width) * width
			bins[low] = bins.get(low, 0) + 1
		spikes = []
		for low, n in sorted(bins.items()):
			near = [bins.get(low + k * width, 0) for k in (-2, -1, 1, 2)]
			med = _median(near)
			if n >= SPIKE_MIN and opts['spike'] and n >= opts['spike'] * max(med, 1):
				spikes.append((low, n, med))
		steps = {10: 0, 5: 0, 1: 0}
		for v in values:
			steps[10 if v % 10 == 0 else 5 if v % 5 == 0 else 1] += 1
		grid = _grid(values)
		off = sorted(((p, v) for p, v in nonzero if v % grid), key=lambda pv: (pv[1], pv[0])) if grid > 1 else []
		extremes = sorted(((p, v) for p, v in nonzero if opts['extreme'] and abs(v) > opts['extreme']),
		                  key=lambda pv: (-abs(pv[1]), pv[0]))
		ordered = sorted(values)
		mid = _quantile(ordered, .5)
		iqr = (_quantile(ordered, .75) - _quantile(ordered, .25)) or 1
		result['masters'][master] = {
			'bins': bins, 'steps': steps, 'grid': grid, 'off_grid': off, 'spikes': spikes, 'extremes': extremes,
			'quantiles': [(_quantile(ordered, q) - mid) / float(iqr) for q in SHAPE_QUANTILES] if ordered else None,
			'count': len(values),
		}
	shaped = dict((m, r['quantiles']) for m, r in result['masters'].items() if r['count'] >= SHAPE_MIN)
	if len(shaped) >= 2:
		family = [_median([q[i] for q in shaped.values()]) for i in range(len(SHAPE_QUANTILES))]
		for master, quant in shaped.items():
			result['shape'][master] = max(abs(a - b) for a, b in zip(quant, family))
		typical = _median(result['shape'].values())
		if len(shaped) >= 3 and opts['shape']:		# two masters: no telling which one differs
			result['shape_flags'] = [m for m, d in result['shape'].items()
			                         if d * 100 > opts['shape'] and d > SHAPE_OUTLIER * typical]
	return result


# - Exception pressure --------------------------------------------------------------
def pressure(kset, opts=None):
	'''{'regions': [(master, left key, right key, taken, total, share, class value or None, [pairs])],
	'culprits': [(side, glyph, group, partners, pairs, [masters], [stored pairs])]}.
	A region is a group pair (a side without a group is its glyph); taken = its glyph pairs that an
	exception (any stored pair of the region other than the region's own pair) decides. Regions at or over the pressure %
	are listed. A culprit is a grouped glyph that owns exceptions against at least `culprit` partners.'''
	opts = options(opts)
	regions = []
	owners = {}		# (side, glyph) -> {'partners': set, 'pairs': [], 'masters': set}
	for master in _masters(kset, opts):
		table = kset.pairs[master]
		taken = {}
		stored = {}
		for pair in table:
			bucket = _bucket(kset, pair)
			if not (is_group(bucket[0]) or is_group(bucket[1])):
				continue		# glyph + glyph without groups: no class to except from
			stored.setdefault(bucket, []).append(pair)
			if pair == bucket:
				continue		# the region's own pair (group + group, or glyph + group for a glyph without a group)
			taken.setdefault(bucket, set()).update(_cells(kset, pair))
			for side, key, partner in ((LEFT, pair[0], bucket[1]), (RIGHT, pair[1], bucket[0])):
				if not is_group(key) and kset.group_of(key, side) is not None:
					own = owners.setdefault((side, key), {'partners': set(), 'pairs': [], 'masters': set()})
					own['partners'].add(partner)
					own['pairs'].append(pair)
					own['masters'].add(master)
		for bucket, cells in taken.items():
			total = len(kset.members(bucket[0], LEFT)) * len(kset.members(bucket[1], RIGHT))
			if not total:
				continue
			share = len(cells) / float(total)
			if share * 100 >= opts['pressure']:
				pairs = sorted(stored[bucket], key=lambda p: (_ORDER[pair_kind(p)], p), reverse=True)
				regions.append((master, bucket[0], bucket[1], len(cells), total, share, table.get(bucket), pairs))
	regions.sort(key=lambda r: (-r[5], -r[4], r[1], r[2], r[0]))
	culprits = []
	for (side, glyph), own in owners.items():
		if len(own['partners']) >= max(1, opts['culprit']):
			culprits.append((side, glyph, kset.group_of(glyph, side), len(own['partners']), len(own['pairs']),
			                 [m for m in kset.masters if m in own['masters']], sorted(set(own['pairs']))))
	culprits.sort(key=lambda c: (-c[3], -c[4], c[0], c[1]))
	return {'regions': regions, 'culprits': culprits}


# - Shadowed and fragile ---------------------------------------------------------------
def shadowed(kset, opts=None):
	'''[(master, pair, value, taken, total, state, [pairs that take over])] for stored pairs with a
	group side (CC, GC, CG): state 'shadowed' when every glyph pair it reaches is decided by a more
	specific pair (it never applies; Cleanup > Pairs that change nothing also removes it), 'fragile'
	when at least `fragile` % are.'''
	opts = options(opts)
	out = []
	for master in _masters(kset, opts):
		table = kset.pairs[master]
		for pair, value in table.items():
			if pair_kind(pair) == 'GG':
				continue
			cells = _cells(kset, pair)
			if not cells:
				continue		# empty group: Cleanup > orphans
			takers = []
			taken = 0
			for a, b in cells:
				key = kset.resolve(master, a, b, table)[1]
				if key != pair:
					taken += 1
					takers.append(key)
			if not taken:
				continue
			share = taken / float(len(cells))
			if taken == len(cells):
				state = 'shadowed'
			elif opts['fragile'] and share * 100 >= opts['fragile']:
				state = 'fragile'
			else:
				continue
			out.append((master, pair, value, taken, len(cells), state, sorted(set(takers))))
	out.sort(key=lambda r: (r[5] != 'shadowed', -r[3] / float(r[4]), _ORDER[pair_kind(r[1])], r[1], r[0]))
	return out


# - Member divergence -------------------------------------------------------------------
def _partners(kset, table, side):
	'''The glyphs that stand for the other side's keys of a table: a group -> its leader.'''
	other = RIGHT if side == LEFT else LEFT
	index = 1 if side == LEFT else 0
	keys = set()
	for pair in table:
		key = pair[index]
		keys.add(key if is_group(key) else kset.side_key(key, other))
	out = []
	for key in sorted(keys):
		glyph = kset.leader(group_name(key), other) if is_group(key) else key
		if glyph:
			out.append((key, glyph))
	return out


def divergence(kset, opts=None):
	'''[(master, side, group, glyph, distance, closer group or None, its distance, [(partner, value,
	group median)])]: members whose resolved kerning against the other side's keys is on average
	`divergence` units or more from their group's median. closer group: a group of the same side whose
	median is nearer to the member than its own (a move to consider).'''
	opts = options(opts)
	out = []
	for master in _masters(kset, opts):
		table = kset.pairs[master]
		for side in (LEFT, RIGHT):
			partners = _partners(kset, table, side)
			if not partners:
				continue
			def vector(glyph):
				if side == LEFT:
					return [kset.resolve(master, glyph, b, table)[0] for _k, b in partners]
				return [kset.resolve(master, a, glyph, table)[0] for _k, a in partners]
			medians = {}
			vectors = {}
			for name, members in kset.groups[side].items():
				if len(members) < 2:
					continue
				vecs = [vector(g) for g in members]
				vectors[name] = dict(zip(members, vecs))
				medians[name] = [_median(col) for col in zip(*vecs)]
			n = float(len(partners))
			for name, vecs in vectors.items():
				if len(vecs) < opts['members']:
					continue
				med = medians[name]
				for glyph, vec in vecs.items():
					dist = sum(abs(a - b) for a, b in zip(vec, med)) / n
					if not opts['divergence'] or dist < opts['divergence']:
						continue
					best, best_dist = None, dist
					for other, omed in medians.items():
						if other == name:
							continue
						d = sum(abs(a - b) for a, b in zip(vec, omed)) / n
						if d < best_dist:
							best, best_dist = other, d
					diffs = sorted(((k, v, m) for (k, _g), v, m in zip(partners, vec, med) if v != m),
					               key=lambda t: -abs(t[1] - t[2]))
					out.append((master, side, name, glyph, dist, best, best_dist if best else None, diffs))
	out.sort(key=lambda r: (-r[4], r[1], r[2], r[3], r[0]))
	return out


# - Context (Phase B) -------------------------------------------------------------------
# Tools 6-8 need more than the kerning: a context dict from the host
#   'glyphs'   [glyph names]          'char_map' {char: glyph}
#   'unicodes' {glyph: code}          'scripts'  {glyph: script} (kern_script.glyph_scripts)
#   'rules'    [rule sets] (kern_rules.rule_set dicts, the font lib)
# A missing entry makes the tool report less, never fail.
_NEUTRAL = ('Zyyy', 'Zinh', 'Zzzz')		# kern_script.NEUTRAL (kern with every script)
MIRRORS = (('(', ')'), ('[', ']'), ('{', '}'), ('«', '»'), ('‹', '›'), ('‘', '’'),
           ('“', '”'), ('/', '\\'))
SMALLCAP_SUFFIXES = ('sc', 'c2sc')
TABULAR_SUFFIXES = ('tf', 'tosf')
CASE_MIN = 5			# small caps: ratio samples needed before pairs are judged
# Lookalikes across scripts: (Latin, Cyrillic, Greek); None = no lookalike in that script
LOOKALIKES = (
	('A', 'А', 'Α'), ('B', 'В', 'Β'), ('C', 'С', None), ('E', 'Е', 'Ε'),
	('H', 'Н', 'Η'), ('I', 'І', 'Ι'), ('J', 'Ј', None), ('K', 'К', 'Κ'),
	('M', 'М', 'Μ'), ('N', None, 'Ν'), ('O', 'О', 'Ο'), ('P', 'Р', 'Ρ'),
	('S', 'Ѕ', None), ('T', 'Т', 'Τ'), ('X', 'Х', 'Χ'), ('Y', 'Ү', 'Υ'),
	('Z', None, 'Ζ'),
	('a', 'а', None), ('c', 'с', None), ('e', 'е', None), ('i', 'і', None), ('j', 'ј', None),
	('o', 'о', 'ο'), ('p', 'р', 'ρ'), ('s', 'ѕ', None), ('x', 'х', None),
	('y', 'у', None),
)
LOOKALIKE_SCRIPTS = ('Latn', 'Cyrl', 'Grek')


def _ctx(context):
	ctx = dict(context or {})
	for key in ('glyphs', 'rules'):
		ctx[key] = list(ctx.get(key) or [])
	for key in ('char_map', 'unicodes', 'scripts'):
		ctx[key] = dict(ctx.get(key) or {})
	return ctx


def _suffix_parts(glyph):
	return glyph.split('.')[1:]


def _rule_side_text(side):
	return '*' + side[1] if isinstance(side, tuple) else str(side)


# - Rule lint (tool 6) ------------------------------------------------------------------
def rule_lint(kset, opts=None, context=None):
	'''Rule sets of the font lib in check mode: where a destination pair renders more than `tolerance`
	away from what its rule gives. {'findings': [(set, line, master, dst pair, actual, expected, rule text)],
	'no_source': [(set, line, master, source pair)], 'errors': [(set, line, message)], 'sets': n,
	'class': {set: class mode}}.'''
	from typerig.core.algo import kern_rules as kr
	opts, ctx = options(opts), _ctx(context)
	glyph_set = set(ctx['glyphs']) if ctx['glyphs'] else None
	out = {'findings': [], 'no_source': [], 'errors': [], 'sets': len(ctx['rules']),
	       'class': dict((rs.get('name', ''), bool(rs.get('class', True))) for rs in ctx['rules'])}
	for rs in ctx['rules']:
		name = rs.get('name', '')
		rules, errors = kr.parse_rules(rs.get('text', ''), ctx['char_map'], glyph_set)
		out['errors'] += [(name, n, m) for n, m in errors]
		chosen = rs.get('masters') or ''
		for master in _masters(kset, opts):
			if chosen and master != chosen:
				continue
			table = kset.pairs[master]
			for rule in rules:
				text = '%s = %s%s' % (' '.join('%s|%s' % (_rule_side_text(a), _rule_side_text(b)) for a, b in rule['dst']),
				                      '%s|%s' % tuple(_rule_side_text(s) for s in rule['src']),
				                      '' if (rule['k'], rule['c']) == (1., 0.) else ' (adjusted)')
				if isinstance(rule['src'][0], tuple):
					writes = kr._wild_writes(kset, master, table, rule, glyph_set)
				else:
					a, b = kr._glyph_of(kset, rule['src'][0], LEFT), kr._glyph_of(kset, rule['src'][1], RIGHT)
					value, key, _level = kset.resolve(master, a, b, table)
					if key is None:
						out['no_source'].append((name, rule['line'], master, (a, b)))
						continue
					expected = int(round(value * rule['k'] + rule['c']))
					writes = [(pair, expected) for pair in rule['dst']]
				for (da, db), expected in writes:
					ga, gb = kr._glyph_of(kset, da, LEFT), kr._glyph_of(kset, db, RIGHT)
					actual = kset.resolve(master, ga, gb, table)[0]
					if abs(actual - expected) > opts['tolerance']:
						out['findings'].append((name, rule['line'], master, (da, db), actual, expected, text))
	return out


# - Consistency families (tool 7) ----------------------------------------------------------
def _smallcaps(ctx):
	'''{small cap glyph: its capital glyph}: x.sc -> the capital of x (by Unicode), X.c2sc -> X.'''
	out = {}
	for glyph in ctx['glyphs']:
		parts = _suffix_parts(glyph)
		if not any(p in SMALLCAP_SUFFIXES for p in parts):
			continue
		base = glyph.split('.')[0]
		if 'c2sc' in parts:
			out[glyph] = base
			continue
		code = ctx['unicodes'].get(base)
		if code is None:
			continue
		capital = ctx['char_map'].get(chr(code).upper())
		if capital and capital != base:
			out[glyph] = capital
	return out


def consistency(kset, opts=None, context=None):
	'''Pairs that should agree but do not (more than `tolerance` apart), per master:
	'mirror'    [(master, (open, X), v1, (X, close), v2)] for the symmetric glyphs (option `symmetric`)
	'case'      [(master, small cap key pair, value, capital key pair, capital value, expected, glyph pairs, sample
	            glyph pair)], one per region (the pairs that decide the values); expected = the master's
	            small cap / capital ratio (median of the regions, weighted by the capital value) x the capital
	            value; the last item is the region's small cap glyph pairs; 'ratios' {master: ratio or None}
	'case_missing' [(master, capital key pair, value, glyph pairs, [small cap glyph pairs])]: capitals kern,
	            small caps not at all
	'case_own'  {master: n}: small cap pairs kerned where the capitals are not (not judged; information)
	'lookalike' [(master, script, (L1, L2), latin value, (S1, S2), value)] Latin vs Cyrillic / Greek lookalikes
	'tabular'   [(master, pair, value)] stored nonzero pairs that reach a tabular figure (.tf, .tosf)'''
	opts, ctx = options(opts), _ctx(context)
	tol = opts['tolerance']
	cm = ctx['char_map']
	out = {'mirror': [], 'case': [], 'case_missing': [], 'lookalike': [], 'tabular': [], 'ratios': {}, 'case_own': {}}
	masters = _masters(kset, opts)
	def val(master, a, b):
		return kset.resolve(master, a, b)[0]
	# mirror
	symmetric = [cm[c] for c in opts['symmetric'] if c.strip() and c in cm]
	brackets = [(cm[o], cm[c]) for o, c in MIRRORS if o in cm and c in cm]
	for master in masters:
		for o, c in brackets:
			for x in symmetric:
				for p1, p2 in (((o, x), (x, c)), ((x, o), (c, x))):
					v1, v2 = val(master, *p1), val(master, *p2)
					if abs(v1 - v2) > tol:
						out['mirror'].append((master, p1, v1, p2, v2))
	# small caps vs capitals: one finding per (small cap key, capital key) region, not per glyph pair
	smallcaps = _smallcaps(ctx)
	sc = sorted(smallcaps)
	scripts = ctx['scripts']
	def one_script(a, b):		# pairs of two scripts never apply: not compared, never fixed
		sa, sb = scripts.get(a), scripts.get(b)
		return not (sa and sb and sa != sb and sa not in _NEUTRAL and sb not in _NEUTRAL)
	for master in masters:
		regions, missing, unpaired = {}, {}, set()
		for s1 in sc:
			for s2 in sc:
				b1, b2 = smallcaps[s1], smallcaps[s2]
				if not (one_script(s1, s2) and one_script(b1, b2)):
					continue
				vs, key_s, _l = kset.resolve(master, s1, s2)
				vb, key_b, _l = kset.resolve(master, b1, b2)
				if not (vs or vb):
					continue
				if key_s is None:		# the small caps are not kerned at all here
					missing.setdefault(key_b, [vb, []])[1].append((s1, s2))
					continue
				if key_b is None:		# small caps kerned on their own: nothing to compare with
					unpaired.add(key_s)
					continue
				regions.setdefault((key_s, key_b), [vs, vb, []])[2].append((s1, s2))
		# one sample per region, weighted by the capital value: small values give noisy ratios (5 / 1)
		samples = [(vs / float(vb), abs(vb)) for vs, vb, _c in regions.values() if vs and vb and (vs > 0) == (vb > 0)]
		ratio = _weighted_median(samples) if len(samples) >= CASE_MIN else None
		out['ratios'][master] = ratio
		out['case_own'][master] = len(unpaired)
		for key_b, (vb, cells) in sorted(missing.items()):
			out['case_missing'].append((master, key_b, vb, len(cells), cells))
		if ratio is None:
			continue
		for (key_s, key_b), (vs, vb, cells) in sorted(regions.items()):
			expected = int(round(vb * ratio))
			if abs(vs - expected) > tol:
				out['case'].append((master, key_s, vs, key_b, vb, expected, len(cells), cells))
	out['case'].sort(key=lambda r: (-abs(r[2] - r[5]), -r[6], r[0]))		# largest differences first
	# lookalikes across scripts
	rows = []
	for chars in LOOKALIKES:
		row = dict((s, cm.get(ch)) for s, ch in zip(LOOKALIKE_SCRIPTS, chars) if ch)
		if row.get('Latn'):
			rows.append(row)
	for master in masters:
		for r1 in rows:
			for r2 in rows:
				latin = (r1['Latn'], r2['Latn'])
				vl = None
				for script in LOOKALIKE_SCRIPTS[1:]:
					if not (r1.get(script) and r2.get(script)):
						continue
					if vl is None:
						vl = val(master, *latin)
					pair = (r1[script], r2[script])
					vs = val(master, *pair)
					if abs(vl - vs) > tol:
						out['lookalike'].append((master, script, latin, vl, pair, vs))
	# tabular figures
	tabular = set(g for g in ctx['glyphs'] if any(p in TABULAR_SUFFIXES for p in _suffix_parts(g)))
	out['tabular_glyphs'] = sorted(tabular)
	if tabular:
		for master in masters:
			for pair, value in sorted(kset.pairs[master].items()):
				if value and (tabular.intersection(kset.members(pair[0], LEFT))
				              or tabular.intersection(kset.members(pair[1], RIGHT))):
					out['tabular'].append((master, pair, value))
	return out


# - Scope (tool 8) ----------------------------------------------------------------------
def scope(kset, opts=None, context=None):
	'''Pairs outside the font's kerning scope:
	'cross'     [(pair, cross cells, cells, left scripts, right scripts, {master: value})]: glyph pairs of two
	            scripts (OpenType looks kerning up per script: they never apply; Glyphs does not export them).
	            cross == cells: the pair never applies (a finding); fewer: a group of several scripts (shape
	            group, information: Glyphs needs it split per script)
	'mixed'     [(side, group, {script: members})]: groups with members of several scripts (shape groups:
	            Glyphs needs them split per script)
	'sc_lower'  [(pair, sc x lowercase cells, cells, {master: value})]: small caps against lowercase; all cells:
	            a finding, fewer: groups that mix small caps and lowercase (information)
	'unknown'   [glyph]: kerned glyphs with no script (unencoded, no base)'''
	from typerig.core.algo.kern_script import side_scripts, UNKNOWN
	opts, ctx = options(opts), _ctx(context)
	scripts = ctx['scripts']
	out = {'cross': [], 'mixed': [], 'sc_lower': [], 'unknown': []}
	masters = _masters(kset, opts)
	values = {}
	for master in masters:
		for pair, value in kset.pairs[master].items():
			values.setdefault(pair, {})[master] = value
	smallcaps = set(_smallcaps(ctx)) | set(g for g in ctx['glyphs'] if any(p in SMALLCAP_SUFFIXES for p in _suffix_parts(g)))
	lower = set()
	for glyph, code in ctx['unicodes'].items():
		try:
			if chr(code).islower() and glyph not in smallcaps:
				lower.add(glyph)
		except (ValueError, OverflowError, TypeError):
			pass
	kerned = set()
	for pair in sorted(values):
		lm, rm = kset.members(pair[0], LEFT), kset.members(pair[1], RIGHT)
		kerned.update(lm)
		kerned.update(rm)
		if scripts:
			ls, rs = side_scripts(lm, scripts), side_scripts(rm, scripts)
			same = sum(n * rs.get(s, 0) for s, n in ls.items())
			cross = sum(ls.values()) * sum(rs.values()) - same
			if cross:
				out['cross'].append((pair, cross, len(lm) * len(rm), sorted(ls), sorted(rs), values[pair]))
		cells = (len(smallcaps.intersection(lm)) * len(lower.intersection(rm))
		         + len(lower.intersection(lm)) * len(smallcaps.intersection(rm)))
		if cells and any(values[pair].values()):
			out['sc_lower'].append((pair, cells, len(lm) * len(rm), values[pair]))
	if scripts:
		for side in (LEFT, RIGHT):
			for name, members in sorted(kset.groups[side].items()):
				counts = side_scripts(members, scripts)
				if len(counts) > 1:
					out['mixed'].append((side, name, counts))
		out['unknown'] = sorted(g for g in kerned if scripts.get(g, UNKNOWN) == UNKNOWN and not is_group(g))
	out['cross'].sort(key=lambda r: (r[1] < r[2], -r[1], r[0]))
	return out


# - Run / report -----------------------------------------------------------------------
_RUN = {'health': health, 'histogram': histogram, 'pressure': pressure, 'shadowed': shadowed,
        'divergence': divergence}
_RUN_CONTEXT = {'rules': rule_lint, 'consistency': consistency, 'scope': scope}	# need the host context
CONTEXT_ANALYSES = tuple(_RUN_CONTEXT)


def analyze(kset, key, opts=None, context=None):
	if key in _RUN_CONTEXT:
		return _RUN_CONTEXT[key](kset, opts, context)
	if key not in _RUN:
		raise ValueError('Unknown analysis: %s' % key)
	return _RUN[key](kset, opts)


def count(key, result):
	'''Findings of a result (the health card has none: None).'''
	if key == 'health':
		return None
	if key == 'histogram':
		return (sum(len(r['spikes']) + len(r['off_grid']) + len(r['extremes']) for r in result['masters'].values())
		        + len(result['shape_flags']))
	if key == 'pressure':
		return len(result['regions']) + len(result['culprits'])
	if key == 'rules':
		return len(result['findings']) + len(result['no_source']) + len(result['errors'])
	if key == 'consistency':
		return sum(len(result[k]) for k in ('mirror', 'case', 'case_missing', 'lookalike', 'tabular'))
	if key == 'scope':		# partial ones come from groups of several scripts / cases: information
		return (sum(1 for r in result['cross'] if r[1] == r[2])
		        + sum(1 for r in result['sc_lower'] if r[1] == r[2]))
	return len(result)


# - Fixes -----------------------------------------------------------------------------
# A finding that can be fixed carries a fix item on its report node; the
# host collects the items of the selected nodes (fix_items), asks the user
# the choices that fix_summary names, and plan_fixes turns them into one
# ChangeSet (pending; nothing is written here). Items:
#   {'type': 'remove', 'pairs': [(master, pair)]}
#   {'type': 'set', 'master', 'pair', 'value', 'class'}        rule lint: as Rules writes it
#   {'type': 'cells', 'master', 'family', 'variants': {choice: [([glyph pairs], value)]}}
#                                                               glyph pairs that must render value
#   {'type': 'tabular', 'master', 'pair', 'glyphs'}             tabular figures: no kerning
# Choices (FIX_CHOICES): mirror = left | right | median, case = ratio | capital,
# where = exact (only the finding's glyph pairs; exceptions where a kerning
# pair reaches more) | pair (at the kerning pair that decides it: its whole
# group changes).
FIX_CHOICES = {
	'mirror': (('left', 'Left side wins: ( X is copied to X )'), ('right', 'Right side wins: X ) is copied to ( X'),
	           ('median', 'Median: both get the middle value')),
	'case':   (('ratio', 'Ratio x capitals (the master\'s small cap ratio)'), ('capital', 'Same as the capitals')),
	'where':  (('exact', 'Only the glyph pairs of the finding (exceptions where needed)'),
	           ('pair', 'At the kerning pair that decides it (its whole group changes)')),
}
FIX_DEFAULTS = {'mirror': 'left', 'case': 'ratio', 'where': 'exact'}
FIX_TITLES = {'remove': 'Remove pairs', 'set': 'Rule values', 'mirror': 'Mirrored punctuation',
              'case': 'Small caps', 'lookalike': 'Lookalikes (Latin value)', 'tabular': 'Tabular figures (no kerning)'}


def fix_remove(pairs):
	return {'type': 'remove', 'pairs': [(m, tuple(p)) for m, p in pairs]}


def fix_cells(master, variants, family):
	return {'type': 'cells', 'master': master, 'family': family,
	        'variants': dict((k, [([tuple(c) for c in cells], int(v)) for cells, v in items]) for k, items in variants.items())}


def fix_items(nodes):
	'''The fix items of report nodes: a node with a fix gives it, a node without one gives its children's
	(selecting a section or an analysis fixes all of it). No item twice.'''
	out, seen = [], set()
	def collect(item):
		if item.get('fix') is not None:
			if id(item['fix']) not in seen:
				seen.add(id(item['fix']))
				out.append(item['fix'])
			return
		for sub in item.get('children') or ():
			collect(sub)
	for item in nodes or ():
		collect(item)
	return out


def fix_family(item):
	return item['family'] if item['type'] == 'cells' else item['type']


def fix_summary(items):
	'''{'counts': {family: n}, 'choices': [choice keys to ask]} for a list of fix items.'''
	counts = {}
	for item in items:
		counts[fix_family(item)] = counts.get(fix_family(item), 0) + 1
	choices = [key for key in ('mirror', 'case') if key in counts]
	if any(item['type'] == 'cells' for item in items):
		choices.append('where')
	return {'counts': counts, 'choices': choices}


def fix_choices(data=None):
	out = dict(FIX_DEFAULTS)
	for key, value in (data or {}).items():
		if key in FIX_CHOICES and value in dict(FIX_CHOICES[key]):
			out[key] = value
	return out


def _write_cells(work, master, cells, value, where, cs):
	'''Make glyph pairs render value in work (and record it in cs). exact: the most general pair (group +
	group, glyph + group, group + glyph) whose glyph pairs are all in cells, else a glyph + glyph exception,
	so no other glyph pair changes; pair: the deciding
	pair (or the group pair when nothing decides) is set. Returns the pairs that a lock refused.'''
	table = work.table(master)
	target = set(cells)
	plan = {}
	for a, b in cells:
		if kset_value(work, master, a, b) == value:
			continue
		if where == 'pair':
			key = work.resolve(master, a, b, table)[1] or (work.side_key(a, LEFT), work.side_key(b, RIGHT))
			plan[key] = value
		else:		# the most general level whose glyph pairs are all in target: CC, GC, CG (GG below)
			la, rb = work.side_key(a, LEFT), work.side_key(b, RIGHT)
			for key in ((la, rb), (a, rb), (la, b)):
				if key in plan:
					break
				if key != (a, b) and set(_cells(work, key)) <= target:
					plan[key] = value
					break
	refused = []
	for key, v in plan.items():
		if cs.set(master, key, v, work.locks):
			table[key] = v
		else:
			refused.append(key)
	for a, b in cells:		# whatever a more specific pair still decides: an exception
		if kset_value(work, master, a, b) != value and (a, b) not in refused:
			if cs.set(master, (a, b), value, work.locks):
				table[(a, b)] = value
			else:
				refused.append((a, b))
	return refused


def kset_value(kset, master, a, b):
	return kset.resolve(master, a, b)[0]


def plan_fixes(kset, items, choices=None):
	'''(ChangeSet, log lines) for fix items on kset (not changed). Locked pairs are refused and logged.'''
	from typerig.core.algo.kern_model import ChangeSet
	choices = fix_choices(choices)
	work = kset.copy()
	cs = ChangeSet('analyze fixes')
	done, refused = {}, []
	for item in items:
		family = fix_family(item)
		if item['type'] == 'remove':
			for master, pair in item['pairs']:
				if pair in work.pairs.get(master, {}):
					if cs.remove(master, pair, work.locks):
						del work.pairs[master][pair]
					else:
						refused.append((master, pair))
		elif item['type'] == 'set':
			master, (da, db) = item['master'], item['pair']
			a = da if (is_group(da) or not item.get('class', True)) else work.side_key(da, LEFT)
			b = db if (is_group(db) or not item.get('class', True)) else work.side_key(db, RIGHT)
			if cs.set(master, (a, b), item['value'], work.locks):
				work.table(master)[(a, b)] = item['value']
			else:
				refused.append((master, (a, b)))
			# a more specific pair may still decide the rule's glyph pair: make it render the value
			ga = work.leader(group_name(da), LEFT) if is_group(da) else da
			gb = work.leader(group_name(db), RIGHT) if is_group(db) else db
			if ga and gb:
				refused += [(master, p) for p in _write_cells(work, master, [(ga, gb)], item['value'], 'exact', cs)]
		elif item['type'] == 'tabular':
			master, pair = item['master'], item['pair']
			tabular = set(item.get('glyphs') or ())
			cells = _cells(work, pair)
			if cells and all(a in tabular or b in tabular for a, b in cells):
				if cs.remove(master, pair, work.locks):
					del work.pairs[master][pair]
				else:
					refused.append((master, pair))
			else:		# the pair also kerns other glyphs: zero exceptions for the tabular ones
				zero = [(a, b) for a, b in cells if a in tabular or b in tabular]
				refused += [(master, p) for p in _write_cells(work, master, zero, 0, 'exact', cs)]
		else:
			variants = item['variants']
			choice = choices.get(family) if family in ('mirror', 'case') else None
			for cells, value in variants.get(choice, variants.get(None, [])):
				refused += [(item['master'], p) for p in _write_cells(work, item['master'], cells, value,
				                                                       choices['where'], cs)]
		done[family] = done.get(family, 0) + 1
	log = ['%s: %d' % (FIX_TITLES.get(f, f), n) for f, n in sorted(done.items())]
	log.append('%d pair(s) to set, %d to remove' % (cs.count('set'), cs.count('remove')))
	if refused:
		log.append('Locked, not changed: %s' % ', '.join('%s %s (%s)' % (p[0], p[1], m) for m, p in refused[:20]))
	cs.log += log
	return cs, log


def _pct(x):
	return '—' if x is None else '%d%%' % round(100 * x)


# - Report tree ---------------------------------------------------------------------
# A report is a tree of nodes, one root per analysis:
#   {'title', 'detail', 'kind', 'link', 'children'}
# title: what was found; detail: where / how much (masters, counts);
# kind: KIND_WARN (a finding), KIND_OK (looked, nothing found), KIND_INFO
# (numbers, no judgement); link: None or {'query', 'pairs'} (see link());
# fix: None or a fix item (see Fixes) that plan_fixes() turns into changes.
KIND_WARN, KIND_OK, KIND_INFO = 'warn', 'ok', 'info'
TREE_LIMIT = 500		# children of one node at most; the rest become one "… n more" node


def node(title, detail='', kind=KIND_INFO, link=None, children=None, fix=None):
	return {'title': str(title), 'detail': str(detail), 'kind': kind, 'link': link, 'children': list(children or []),
	        'fix': fix}


def _capped(children):
	if len(children) <= TREE_LIMIT:
		return children
	return children[:TREE_LIMIT] + [node('… %d more' % (len(children) - TREE_LIMIT))]


def _section(title, children, link_=None):
	'''A group of findings: warn with its count, or ok when empty.'''
	return node(title, '%d' % len(children), KIND_WARN if children else KIND_OK, link_, _capped(children))


def _pair_node(pair, value):
	return node('%s %s' % pair, '%d' % value, KIND_WARN, link([pair]))


def _query(text):
	return {'query': text, 'pairs': []}


def _tree_health(result):
	out = []
	for master, h in result.items():
		kinds = ', '.join('%s %d' % (k, h['kinds'][k]) for k in KINDS)
		out.append(node(master, '%d pairs' % h['pairs'], KIND_INFO, _query('master:%s' % master), [
			node('Kinds', kinds),
			node('Exceptions', '%d  (%s of class pairs)' % (h['exceptions'], _pct(h['ratio'])),
			     link=_query('master:%s kind:GG,GC,CG' % master) if h['exceptions'] else None),
			node('Class pair fill', '%s of %d group regions' % (_pct(h['fill']), h['regions'])),
			node('Values', 'min %d, median %g, max %d, mean |v| %.1f' % (h['min'], h['median'], h['max'], h['mean_abs'])),
			node('Zero values', '%d' % h['zeros'], KIND_WARN if h['zeros'] else KIND_OK,
			     _query('master:%s ==0' % master) if h['zeros'] else None),
		]))
	return out


def _tree_histogram(result, opts):
	width = opts['bin']
	out = []
	for master, r in result['masters'].items():
		bins = []
		if r['bins']:
			peak = max(r['bins'].values())
			for low in range(min(r['bins']), max(r['bins']) + width, width):
				n = r['bins'].get(low, 0)
				if n:
					bins.append(node('%d .. %d' % (low, low + width - 1),
					                 '%5d  %s' % (n, '#' * max(1, int(round(30. * n / peak)))),
					                 link=_query('master:%s >=%d <%d' % (master, low, low + width))))
		spikes = [node('%d .. %d' % (low, low + width - 1), '%d values, neighbours %g' % (n, med), KIND_WARN,
		               _query('master:%s >=%d <%d' % (master, low, low + width)))
		          for low, n, med in r['spikes']]
		off = [_pair_node(p, v) for p, v in r['off_grid']]
		extreme = [_pair_node(p, v) for p, v in r['extremes']]
		off_title = ('Off the %d grid (hand edits?)' % r['grid'] if r['grid'] > 1
		             else 'Off the grid (no 10 / 5 grid in this master)')
		extreme_link = {'query': 'master:%s <-%d; master:%s >%d' % (master, opts['extreme'], master, opts['extreme']),
		                'pairs': [p for p, _v in r['extremes']][:LINK_PAIRS]}
		found = len(spikes) + len(off) + len(extreme)
		out.append(node(master, '%d values; steps of 10: %d, 5: %d, other: %d'
		                % (r['count'], r['steps'][10], r['steps'][5], r['steps'][1]),
		                KIND_WARN if found else KIND_OK, None, [
			node('Distribution', 'bins of %d' % width, KIND_INFO, None, bins),
			_section('Spikes', spikes),
			_section(off_title, off, link([p for p, _v in r['off_grid']])),
			_section('Extreme (|v| > %d)' % opts['extreme'], extreme, extreme_link),
		]))
	if result['shape']:
		shapes = [node(m, '%d%%%s' % (round(d * 100), '  differs' if m in result['shape_flags'] else ''),
		               KIND_WARN if m in result['shape_flags'] else KIND_INFO) for m, d in result['shape'].items()]
		out.append(node('Shape (tails vs the other masters, % of IQR)', '%d differ' % len(result['shape_flags']),
		                KIND_WARN if result['shape_flags'] else KIND_OK, None, shapes))
	return out


def _pairs_children(pairs, detail=''):
	return [node('%s %s' % p, detail, KIND_INFO, link([p])) for p in pairs[:TREE_LIMIT]]


def _tree_pressure(result):
	regions = [node('%s %s' % (left, right), '%d of %d by exceptions (%s), class pair %s  (%s)'
	                % (taken, total, _pct(share), '—' if cc is None else cc, master), KIND_WARN, link(pairs),
	                _pairs_children(pairs))
	           for master, left, right, taken, total, share, cc, pairs in result['regions']]
	culprits = []
	for side, glyph, group, partners, n, masters, pairs in result['culprits']:
		where = '%s|*' % glyph if side == LEFT else '*|%s' % glyph
		culprits.append(node('%s  (%s side of @%s)' % (glyph, side, group),
		                     'against %d partners, %d pairs  (%s)' % (partners, n, ', '.join(masters)), KIND_WARN,
		                     {'query': where + ' kind:GG,GC,CG', 'pairs': pairs[:LINK_PAIRS]}, _pairs_children(pairs)))
	return [_section('Group regions taken by exceptions', regions),
	        _section('Glyphs with many exceptions (wrong group?)', culprits)]


def _tree_shadowed(result):
	by_state = {'shadowed': [], 'fragile': []}
	for master, pair, value, taken, total, state, takers in result:
		by_state[state].append(node('%s %s = %d' % (pair[0], pair[1], value),
		                            '%d of %d glyph pairs taken by %d pair(s)  (%s)' % (taken, total, len(takers), master),
		                            KIND_WARN, link([pair] + takers), _pairs_children(takers, 'takes over'),
		                            fix_remove([(master, pair)]) if state == 'shadowed' else None))
	return [_section('Shadowed (never applies)', by_state['shadowed']),
	        _section('Fragile (seldom applies)', by_state['fragile'])]


def _tree_divergence(result):
	out = []
	for master, side, group, glyph, dist, best, best_dist, diffs in result:
		where = '%s|*' % glyph if side == LEFT else '*|%s' % glyph
		def pair(key):
			return (glyph, key) if side == LEFT else (key, glyph)
		move = ', closer to @%s (%.0f)' % (best, best_dist) if best else ''
		out.append(node('%s in @%s' % (glyph, group), '%.0f units from the group%s  (%s, %s)' % (dist, move, side, master),
		                KIND_WARN, {'query': where, 'pairs': [pair(k) for k, _v, _m in diffs[:5]]},
		                [node('vs %s' % key, '%d, group %g' % (v, m), KIND_INFO, link([pair(key)]))
		                 for key, v, m in diffs[:20]]))
	return _capped(out)


def _values_text(values):
	return ', '.join('%s %d' % mv for mv in values.items())


def _tree_rules(result):
	if not result['sets']:
		return [node('No rule sets in the font', 'make them in the Rules tab', KIND_INFO)]
	by_set = {}
	for name, line, master, pair, actual, expected, text in result['findings']:
		by_set.setdefault(name, []).append(node('%s %s' % pair, '%d, rule gives %d  (line %d: %s; %s)'
		                                        % (actual, expected, line, text, master), KIND_WARN, link([pair]),
		                                        fix={'type': 'set', 'master': master, 'pair': pair, 'value': expected,
		                                             'class': result.get('class', {}).get(name, True)}))
	out = [_section('Set "%s"' % name, items) for name, items in sorted(by_set.items())]
	if not out:
		out.append(node('Every destination pair agrees with its rule', '%d set(s)' % result['sets'], KIND_OK))
	out.append(_section('Rules whose source pair is not kerned', [
		node('%s %s' % pair, 'set "%s", line %d  (%s)' % (name, line, master), KIND_WARN, link([pair]))
		for name, line, master, pair in result['no_source']]))
	out.append(_section('Rule errors', [node('Set "%s", line %d' % (name, line), message, KIND_WARN)
	                                    for name, line, message in result['errors']]))
	return out


def _tree_consistency(result):
	mirror = [node('%s %s  vs  %s %s' % (p1 + p2), '%d vs %d  (%s)' % (v1, v2, master), KIND_WARN, link([p1, p2]),
	               fix=fix_cells(master, {'left': [([p2], v1)], 'right': [([p1], v2)],
	                                      'median': [([p1, p2], int(round((v1 + v2) / 2.)))]}, 'mirror'))
	          for master, p1, v1, p2, v2 in result['mirror']]
	case = [node('%s %s' % key_s, '%d, expected %d (capitals %s %s = %d); %d glyph pair(s), e.g. %s %s  (%s)'
	             % (vs, expected, key_b[0], key_b[1], vb, n, cells[0][0], cells[0][1], master), KIND_WARN, link([key_s, key_b]),
	             fix=fix_cells(master, {'ratio': [(cells, expected)], 'capital': [(cells, vb)]}, 'case'))
	        for master, key_s, vs, key_b, vb, expected, n, cells in result['case']]
	def ratio_value(master, vb):
		ratio = result['ratios'].get(master)
		return int(round(vb * (1. if ratio is None else ratio)))
	missing = [node('%s %s' % key_b, 'capitals %d, small caps not kerned; %d glyph pair(s), e.g. %s %s  (%s)'
	                % (vb, n, cells[0][0], cells[0][1], master), KIND_WARN, link([key_b, cells[0]]),
	                fix=fix_cells(master, {'ratio': [(cells, ratio_value(master, vb))], 'capital': [(cells, vb)]}, 'case'))
	           for master, key_b, vb, n, cells in result['case_missing']]
	ratios = ', '.join('%s %s' % (m, '—' if r is None else '%.2f' % r) for m, r in result['ratios'].items())
	look = [node('%s %s  vs  %s %s' % (latin + pair), '%d vs %d  (%s, %s)' % (vl, vs, script, master), KIND_WARN,
	             link([latin, pair]), fix=fix_cells(master, {None: [([pair], vl)]}, 'lookalike'))
	        for master, script, latin, vl, pair, vs in result['lookalike']]
	tab = [node('%s %s' % pair, '%d  (%s)' % (value, master), KIND_WARN, link([pair]),
	            fix={'type': 'tabular', 'master': master, 'pair': pair, 'glyphs': result.get('tabular_glyphs', [])})
	       for master, pair, value in result['tabular']]
	case_node = _section('Small caps vs capitals', case)
	own = sum(result['case_own'].values())
	case_node['detail'] = '%d  (ratio %s%s)' % (len(case), ratios or '—',
	                                            '; %d small cap pairs kerned where capitals are not: not judged' % own if own else '')
	return [_section('Mirrored punctuation (symmetric glyphs)', mirror), case_node,
	        _section('Small caps not kerned where capitals are', missing),
	        _section('Lookalikes across scripts (vs Latin)', look), _section('Tabular figures with kerning', tab)]


def _tree_scope(result):
	from typerig.core.algo.kern_script import SCRIPT_NAMES
	def names(codes):
		return '/'.join(SCRIPT_NAMES.get(c, c) for c in codes)
	never = [node('%s %s' % pair, '%d glyph pairs, %s | %s  (%s)' % (total, names(ls), names(rs), _values_text(values)),
	              KIND_WARN, link([pair]), fix=fix_remove([(m, pair) for m in values]))
	         for pair, n, total, ls, rs, values in result['cross'] if n == total]
	partly = [node('%s %s' % pair, '%d of %d glyph pairs across scripts (%s | %s)' % (n, total, names(ls), names(rs)),
	               KIND_INFO, link([pair])) for pair, n, total, ls, rs, _values in result['cross'] if n < total]
	mixed = [node('@%s  (%s)' % (name, side), ', '.join('%s %d' % (SCRIPT_NAMES.get(s, s), n) for s, n in sorted(counts.items())),
	              KIND_INFO, {'query': 'in:@%s' % name, 'pairs': []}) for side, name, counts in result['mixed']]
	sc_lower = [node('%s %s' % pair, '%d glyph pairs  (%s)' % (cells, _values_text(values)), KIND_WARN, link([pair]),
	                 fix=fix_remove([(m, pair) for m in values]))
	            for pair, cells, total, values in result['sc_lower'] if cells == total]
	sc_mixed = [node('%s %s' % pair, '%d of %d glyph pairs' % (cells, total), KIND_INFO, link([pair]))
	            for pair, cells, total, _values in result['sc_lower'] if cells < total]
	unknown = [node(g, 'no Unicode, no base glyph', KIND_INFO) for g in result['unknown']]
	mixed_node = node('Groups with several scripts (shape groups)', '%d  (Glyphs: split per script)' % len(mixed),
	                  KIND_INFO, None, _capped(mixed))
	unknown_node = node('Kerned glyphs with no script', '%d' % len(unknown), KIND_INFO, None, _capped(unknown))
	return [_section('Pairs that never apply (sides of two scripts)', never),
	        node('Pairs partly across scripts (groups of several scripts)', '%d' % len(partly), KIND_INFO, None, _capped(partly)),
	        mixed_node,
	        _section('Small caps against lowercase', sc_lower),
	        node('Small caps partly against lowercase (mixed groups)', '%d' % len(sc_mixed), KIND_INFO, None, _capped(sc_mixed)),
	        unknown_node]


def report_tree(key, result, opts=None):
	'''The report of one analysis as a tree (see node()); the root is the analysis.'''
	opts = options(opts)
	found = count(key, result)
	if key == 'health':
		children = _tree_health(result)
	elif key == 'histogram':
		children = _tree_histogram(result, opts)
	elif key == 'pressure':
		children = _tree_pressure(result)
	elif key == 'shadowed':
		children = _tree_shadowed(result)
	elif key == 'rules':
		children = _tree_rules(result)
	elif key == 'consistency':
		children = _tree_consistency(result)
	elif key == 'scope':
		children = _tree_scope(result)
	else:
		children = _tree_divergence(result)
	kind = KIND_INFO if found is None else KIND_WARN if found else KIND_OK
	return node(dict(ANALYSES)[key], '' if found is None else '%d found' % found, kind, None, children)


def walk(nodes, depth=0):
	'''(depth, node) for every node, depth first.'''
	for item in nodes:
		yield depth, item
		for sub in walk(item['children'], depth + 1):
			yield sub


def tree_text(roots, limit=40, indent='  '):
	'''Plain text of report trees: each analysis under a rule, a blank line before
	every section with children, at most `limit` children shown per node.'''
	lines = []
	def emit(item, depth):
		if 0 < depth <= 2 and item['children'] and lines[-1] != '':
			lines.append('')
		text = indent * (depth - 1) + item['title'] if depth else item['title'].upper()
		if item['detail']:
			text += ('  (%s)' if not depth else ':  %s') % item['detail']
		lines.append(text)
		if not depth:
			lines.append('=' * min(len(text), 72))
		for sub in item['children'][:limit]:
			emit(sub, depth + 1)
		if len(item['children']) > limit:
			lines.append(indent * depth + '… %d more' % (len(item['children']) - limit))
	for root in roots:
		if lines:
			lines += ['', '']
		emit(root, 0)
	return '\n'.join(lines).rstrip() + '\n'


def to_data(value):
	'''A result as JSON-ready data: tuples / sets -> lists, dict keys -> str.'''
	if isinstance(value, dict):
		return dict((str(k), to_data(v)) for k, v in value.items())
	if isinstance(value, (list, tuple, set)):
		items = sorted(value) if isinstance(value, set) else value
		return [to_data(v) for v in items]
	return value

