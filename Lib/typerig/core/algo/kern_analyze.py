# MODULE: TypeRig / Core / Algo / Kern Analyze
# -----------------------------------------------------------
# TR Kern analytics (Analyze tab, tr-kern analyze): read-only views that
# show problems in a kerning table. Nothing here writes: an analysis
# returns a result, report() turns it into lines, and a line may carry a
# link (a Pairs query and the stored pairs behind it) for the host to show.
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
#
#   ANALYSES, options(data), analyze(kset, key, opts) -> result
#   count(key, result), report(key, result) -> [(line, link or None)]
#   to_data(result) -> JSON-ready (tuples -> lists, keys -> str)
#   Link: {'query': Pairs query text, 'pairs': [stored pair]}
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

__version__ = '0.1.0'

# - Init -------------------------------------------------------------------
ANALYSES = (	# (key, title)
	('health', 'Health card'),
	('histogram', 'Value histogram'),
	('pressure', 'Exception pressure'),
	('shadowed', 'Shadowed and fragile pairs'),
	('divergence', 'Member divergence'),
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
}
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
		if key == 'master':
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


# - Run / report -----------------------------------------------------------------------
_RUN = {'health': health, 'histogram': histogram, 'pressure': pressure, 'shadowed': shadowed,
        'divergence': divergence}


def analyze(kset, key, opts=None):
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
	return len(result)


def _pct(x):
	return '—' if x is None else '%d%%' % round(100 * x)


def _report_health(result):
	lines = []
	for master, h in result.items():
		lines.append(('  %s: %d pairs, %d exceptions (%s of class pairs), class pairs fill %s of %d group regions'
		              % (master, h['pairs'], h['exceptions'], _pct(h['ratio']), _pct(h['fill']), h['regions']),
		              {'query': 'master:%s' % master, 'pairs': []}))
		kinds = ', '.join('%s %d' % (k, h['kinds'][k]) for k in KINDS)
		lines.append(('    kinds: %s' % kinds, None))
		lines.append(('    values: min %d, median %s, max %d, mean |v| %.1f; zero values %d'
		              % (h['min'], ('%g' % h['median']), h['max'], h['mean_abs'], h['zeros']),
		              {'query': 'master:%s ==0' % master, 'pairs': []} if h['zeros'] else None))
	return lines


def _report_histogram(result, opts, limit):
	lines = []
	width = opts['bin']
	for master, r in result['masters'].items():
		lines.append(('  %s: %d nonzero values; on the 10 grid %d, on the 5 grid %d, other %d; font grid %d'
		              % (master, r['count'], r['steps'][10], r['steps'][5], r['steps'][1], r['grid']), None))
		if r['bins']:
			peak = max(r['bins'].values())
			for low in range(min(r['bins']), max(r['bins']) + width, width):
				n = r['bins'].get(low, 0)
				if not n:
					continue
				bar = '#' * max(1, int(round(30. * n / peak)))
				lines.append(('    %5d..%-5d %5d %s' % (low, low + width - 1, n, bar),
				              {'query': 'master:%s >=%d <%d' % (master, low, low + width), 'pairs': []}))
		for low, n, med in r['spikes']:
			lines.append(('    spike %d..%d: %d values (neighbours %g)' % (low, low + width - 1, n, med),
			              {'query': 'master:%s >=%d <%d' % (master, low, low + width), 'pairs': []}))
		if r['off_grid']:
			lines.append(('    off the %d grid: %d (hand edits?)' % (r['grid'], len(r['off_grid'])),
			              link([p for p, _v in r['off_grid']])))
			for pair, value in r['off_grid'][:limit]:
				lines.append(('      %s %s = %d' % (pair[0], pair[1], value), link([pair])))
			if len(r['off_grid']) > limit:
				lines.append(('      … %d more' % (len(r['off_grid']) - limit), None))
		if r['extremes']:
			lines.append(('    extreme (|v| > %d): %d' % (opts['extreme'], len(r['extremes'])),
			              {'query': 'master:%s <-%d; master:%s >%d' % (master, opts['extreme'], master, opts['extreme']),
			               'pairs': [p for p, _v in r['extremes']][:LINK_PAIRS]}))
			for pair, value in r['extremes'][:limit]:
				lines.append(('      %s %s = %d' % (pair[0], pair[1], value), link([pair])))
			if len(r['extremes']) > limit:
				lines.append(('      … %d more' % (len(r['extremes']) - limit), None))
	if result['shape']:
		lines.append(('  shape (normalised quantiles, distance from the other masters):', None))
		for master, dist in result['shape'].items():
			flag = '  <- differs' if master in result['shape_flags'] else ''
			lines.append(('    %s %d%%%s' % (master, round(dist * 100), flag), None))
	return lines


def _report_pressure(result, limit):
	lines = []
	regions, culprits = result['regions'], result['culprits']
	lines.append(('  regions: %d' % len(regions), None))
	for master, left, right, taken, total, share, cc, pairs in regions[:limit]:
		lines.append(('    %s %s  (%s): %d of %d glyph pairs by exceptions (%s), class pair %s'
		              % (left, right, master, taken, total, _pct(share), '—' if cc is None else cc), link(pairs)))
	if len(regions) > limit:
		lines.append(('    … %d more' % (len(regions) - limit), None))
	lines.append(('  glyphs with many exceptions: %d' % len(culprits), None))
	for side, glyph, group, partners, n, masters, pairs in culprits[:limit]:
		where = '%s|*' % glyph if side == LEFT else '*|%s' % glyph
		lines.append(('    %s (%s, group %s): exceptions against %d partner(s), %d pair(s) in %s'
		              % (glyph, side, group, partners, n, ', '.join(masters)),
		              {'query': where + ' kind:GG,GC,CG', 'pairs': pairs[:LINK_PAIRS]}))
	if len(culprits) > limit:
		lines.append(('    … %d more' % (len(culprits) - limit), None))
	return lines


def _report_shadowed(result, limit):
	lines = []
	for master, pair, value, taken, total, state, takers in result[:limit]:
		lines.append(('  %s %s = %d  (%s): %s, %d of %d glyph pairs taken by %d other pair(s)'
		              % (pair[0], pair[1], value, master, state, taken, total, len(takers)), link([pair] + takers)))
	if len(result) > limit:
		lines.append(('  … %d more' % (len(result) - limit), None))
	return lines


def _report_divergence(result, limit):
	lines = []
	for master, side, group, glyph, dist, best, best_dist, diffs in result[:limit]:
		move = ', closer to @%s (%.0f)' % (best, best_dist) if best else ''
		where = '%s|*' % glyph if side == LEFT else '*|%s' % glyph
		proof = []
		for key, _v, _m in diffs[:5]:
			proof.append((glyph, key) if side == LEFT else (key, glyph))
		lines.append(('  %s in @%s (%s, %s): %.0f units from the group median%s'
		              % (glyph, group, side, master, dist, move), {'query': where, 'pairs': proof}))
		for key, v, m in diffs[:3]:
			lines.append(('      vs %s: %d, group median %g' % (key, v, m), None))
	if len(result) > limit:
		lines.append(('  … %d more' % (len(result) - limit), None))
	return lines


def report(key, result, opts=None, limit=40):
	'''[(line, link or None)] for one analysis; the first line is its title and count.'''
	opts = options(opts)
	title = dict(ANALYSES)[key]
	found = count(key, result)
	lines = [('%s%s' % (title, '' if found is None else ': %d' % found), None)]
	if key == 'health':
		lines += _report_health(result)
	elif key == 'histogram':
		lines += _report_histogram(result, opts, limit)
	elif key == 'pressure':
		lines += _report_pressure(result, limit)
	elif key == 'shadowed':
		lines += _report_shadowed(result, limit)
	elif key == 'divergence':
		lines += _report_divergence(result, limit)
	return lines


def to_data(value):
	'''A result as JSON-ready data: tuples / sets -> lists, dict keys -> str.'''
	if isinstance(value, dict):
		return dict((str(k), to_data(v)) for k, v in value.items())
	if isinstance(value, (list, tuple, set)):
		items = sorted(value) if isinstance(value, set) else value
		return [to_data(v) for v in items]
	return value


def report_text(lines):
	return '\n'.join(text for text, _link in lines) + '\n'
