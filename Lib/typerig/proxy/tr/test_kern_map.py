# MODULE: TypeRig / Proxy / TR / Kern Map — tests (pure Python, no FontLab)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# Run with: python test_kern_map.py

import os
import sys

try:
	import typerig.core
except ImportError:
	sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))

from typerig.proxy.tr.kern_map import (
	fl_groups_to_ufo, ufo_groups_to_fl, fl_pair_to_ufo, ufo_pair_to_fl,
	FL_LEFT, FL_RIGHT, FL_BOTH, FL_GLYPH, FL_GROUP, KERN1, KERN2,
)

fails, total = [], [0]

def check(name, ok, detail=''):
	total[0] += 1
	print('{}  {}{}'.format('PASS' if ok else 'FAIL', name, '' if ok else '  ' + str(detail)))
	if not ok:
		fails.append(name)

# FontLab classes as BasilMM names them
fl = {
	'_lc_a':      (['a', 'aacute'], FL_RIGHT),
	'_uc_A':      (['A', 'Aacute'], FL_BOTH),
	'_lc_f_left': (['f', 'f_f'], FL_LEFT),
}
ufo = fl_groups_to_ufo(fl)
check('KernRight -> kern2', ufo.get(KERN2 + '_lc_a') == ['a', 'aacute'])
check('KernLeft -> kern1 only', KERN1 + '_lc_f_left' in ufo and KERN2 + '_lc_f_left' not in ufo)
check('KernBothSide -> kern1 + kern2', ufo.get(KERN1 + '_uc_A') == ufo.get(KERN2 + '_uc_A') == ['A', 'Aacute'])

back, rename = ufo_groups_to_fl(ufo)
check('groups round trip FL -> UFO -> FL', back == fl and rename == {}, back)

# Pairs, both directions
pairs_fl = [('F', FL_GLYPH, '_lc_a', FL_GROUP, -70), ('_uc_A', FL_GROUP, 'V', FL_GLYPH, -50),
            ('_uc_A', FL_GROUP, '_uc_A', FL_GROUP, 10), ('T', FL_GLYPH, 'o', FL_GLYPH, -90)]
for l, lm, r, rm, v in pairs_fl:
	first, second = fl_pair_to_ufo(l, lm, r, rm)
	(l2, lm2), (r2, rm2) = ufo_pair_to_fl(first, second)
	check('pair {}/{} round trip'.format(l, r), (l2, lm2, r2, rm2) == (l, lm, r, rm), (first, second, l2, lm2, r2, rm2))

check('group pair names', fl_pair_to_ufo('F', FL_GLYPH, '_lc_a', FL_GROUP) == ('F', KERN2 + '_lc_a'))

# UFO font where kern1.O and kern2.O differ: FontLab needs two names
clash = {KERN1 + 'O': ['O', 'Q'], KERN2 + 'O': ['O', 'C', 'G'], 'smcp': ['a.sc']}
problems = []
fl2, rename2 = ufo_groups_to_fl(clash, problems)
check('clash: kern1 keeps the name', fl2.get('O') == (['O', 'Q'], FL_LEFT))
check('clash: kern2 renamed', rename2 == {'O': 'O.R'} and fl2.get('O.R') == (['O', 'C', 'G'], FL_RIGHT), (fl2, rename2))
check('clash: reported', len(problems) == 1)
check('clash: pair right side follows the rename',
	ufo_pair_to_fl('T', KERN2 + 'O', rename2) == (('T', FL_GLYPH), ('O.R', FL_GROUP)))
check('non-kerning groups ignored', 'smcp' not in fl2)

print()
print('ALL PASS ({} checks)'.format(total[0]) if not fails else '{} FAILED: {}'.format(len(fails), fails))
sys.exit(1 if fails else 0)
