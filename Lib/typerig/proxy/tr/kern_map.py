# MODULE: TypeRig / Proxy / TR / Kern Map
# NOTE: FontLab kerning names <-> UFO kerning names (pure, no FontLab import)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# FontLab keeps kerning classes per master on the kerning object:
#   flPackage.kerning(master).groups.asDict()
#     -> {name: (glyph names, 'KernLeft' | 'KernRight' | 'KernBothSide')}
# and pairs as (name, mode) on each side, mode 'glyphMode' | 'groupMode'.
# (API as used by the FL-tested pFont / pKerning code in proxy/fl/objects.)
#
# .trfont uses the UFO model: one flat Groups table where kerning classes
# carry the reserved prefixes public.kern1. (first/left side) and
# public.kern2. (second/right side), and pairs name classes by those keys.
#
# This module is the whole name mapping, kept pure so it is unit-tested
# outside FontLab (test_kern_map.py). The FontLab glue lives in
# proxy/tr/objects/font.py.
#
# Mapping:
#   FL 'X' KernLeft      <-> public.kern1.X
#   FL 'X' KernRight     <-> public.kern2.X
#   FL 'X' KernBothSide  <-> public.kern1.X + public.kern2.X (same members)
#   pair left  ('X', groupMode) <-> public.kern1.X
#   pair right ('X', groupMode) <-> public.kern2.X
# A UFO font may have kern1.X and kern2.X with DIFFERENT members; FontLab
# has one name space for classes, so the second side is renamed (X -> X.R)
# and the rename is applied to the pairs as well (reported as a problem).

# - Init --------------------------------
__version__ = '0.1.0'

KERN1 = 'public.kern1.'
KERN2 = 'public.kern2.'

FL_LEFT  = 'KernLeft'
FL_RIGHT = 'KernRight'
FL_BOTH  = 'KernBothSide'

FL_GLYPH = 'glyphMode'
FL_GROUP = 'groupMode'

RIGHT_SUFFIX = '.R'

# - FontLab -> UFO ----------------------
def fl_groups_to_ufo(fl_groups):
	'''{name: (members, mode)} -> {ufo name: [members]} (kerning classes only).'''
	out = {}
	for name, (members, mode) in sorted(fl_groups.items()):
		members = [str(m) for m in members]
		if mode in (FL_LEFT, FL_BOTH):
			out[KERN1 + name] = list(members)
		if mode in (FL_RIGHT, FL_BOTH):
			out[KERN2 + name] = list(members)
	return out

def fl_side_to_ufo(name, mode, side):
	'''One side of an FL pair -> UFO key. side: 1 (first/left) or 2 (second/right).'''
	if mode == FL_GROUP:
		return (KERN1 if side == 1 else KERN2) + name
	return name

def fl_pair_to_ufo(left, left_mode, right, right_mode):
	return fl_side_to_ufo(left, left_mode, 1), fl_side_to_ufo(right, right_mode, 2)

# - UFO -> FontLab ----------------------
def ufo_groups_to_fl(ufo_groups, problems=None):
	'''{ufo name: [members]} -> ({fl name: (members, mode)}, right_rename).

	Only public.kern1./kern2. groups are considered. right_rename maps a
	kern2 class name to the FL name it got when it clashed with a kern1
	class of the same name but different members.
	'''
	problems = problems if problems is not None else []
	first  = {k[len(KERN1):]: list(v) for k, v in ufo_groups.items() if k.startswith(KERN1)}
	second = {k[len(KERN2):]: list(v) for k, v in ufo_groups.items() if k.startswith(KERN2)}

	fl_groups, right_rename = {}, {}
	for name, members in sorted(first.items()):
		if name in second and second[name] == members:
			fl_groups[name] = (members, FL_BOTH)
		else:
			fl_groups[name] = (members, FL_LEFT)

	for name, members in sorted(second.items()):
		if name in first and first[name] == members:
			continue		# already a KernBothSide class
		fl_name = name
		if fl_name in fl_groups:
			fl_name = name + RIGHT_SUFFIX
			while fl_name in fl_groups or fl_name in second:
				fl_name += RIGHT_SUFFIX
			right_rename[name] = fl_name
			problems.append('kern2 class "{}" clashes with a different kern1 class; FontLab name "{}"'.format(name, fl_name))
		fl_groups[fl_name] = (members, FL_RIGHT)

	return fl_groups, right_rename

def ufo_side_to_fl(key, side, right_rename=None):
	'''UFO pair key -> (FL name, FL mode).'''
	prefix = KERN1 if side == 1 else KERN2
	if key.startswith(prefix):
		name = key[len(prefix):]
		if side == 2 and right_rename:
			name = right_rename.get(name, name)
		return name, FL_GROUP
	return key, FL_GLYPH

def ufo_pair_to_fl(first, second, right_rename=None):
	return ufo_side_to_fl(first, 1, right_rename), ufo_side_to_fl(second, 2, right_rename)
