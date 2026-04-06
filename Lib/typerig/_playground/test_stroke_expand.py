#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Test: Stroke expansion on a simple horizontal line
# Run standalone (no FontLab needed)

from __future__ import print_function
import sys, os

# Add typerig to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from typerig.core.objects.metapen import (
	PenStroke, Nib, StrokeResult,
	CAP_ROUND, CAP_BUTT, JOIN_ROUND, JOIN_MITER, JOIN_BEVEL
)
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour

# ---- Test 1: Simple horizontal line, 80u circle nib, round cap ----
print('=' * 60)
print('TEST 1: Horizontal line, circle nib 80u, CAP_ROUND')
print('=' * 60)

# Horizontal line from (100, 300) to (500, 300)
# As a degenerate cubic: (z0, z0, z3, z3)
z0 = complex(100, 300)
z3 = complex(500, 300)
seg = (z0, z0, z3, z3)

nib = Nib.circle(80)
print('Nib:', nib)
print('Nib path:', nib.path)
print('Nib segments:', nib.segments)
print()

# Test tangent_point for key directions
for label, d in [('right (1,0)', 1+0j), ('left (-1,0)', -1+0j),
                 ('up (0,1)', 0+1j), ('down (0,-1)', 0-1j)]:
	tp = nib.tangent_point(complex(d))
	print('tangent_point(%s) = (%.1f, %.1f)' % (label, tp.real, tp.imag))
print()

stroke = PenStroke([seg], nib, closed=False, cap=CAP_ROUND, join=JOIN_ROUND)
result = stroke.expand()

print('Right edge: %d points' % len(result.right))
for i, (z, t) in enumerate(zip(result.right, result.right_types)):
	print('  R[%d] (%s) = (%.1f, %.1f)' % (i, t, z.real, z.imag))

print('Left edge: %d points' % len(result.left))
for i, (z, t) in enumerate(zip(result.left, result.left_types)):
	print('  L[%d] (%s) = (%.1f, %.1f)' % (i, t, z.real, z.imag))

print('End cap: %d points' % len(result.end))
for i, (z, t) in enumerate(zip(result.end, result.end_types)):
	print('  E[%d] (%s) = (%.1f, %.1f)' % (i, t, z.real, z.imag))

print('Begin cap: %d points' % len(result.begin))
for i, (z, t) in enumerate(zip(result.begin, result.begin_types)):
	print('  B[%d] (%s) = (%.1f, %.1f)' % (i, t, z.real, z.imag))

print()
print('Full outline: %d points' % len(result.outline))
nodes = result.to_nodes()
for i, n in enumerate(nodes):
	print('  [%d] (%s) = (%.1f, %.1f)' % (i, n.type, n.x, n.y))

# ---- Verify expected geometry ----
print()
print('--- EXPECTED GEOMETRY ---')
print('Line: (100,300) -> (500,300), nib radius = 40')
print('Right edge: (100,260) -> (500,260)  [below, since right side of rightward path]')
print('Left edge (end->start): (500,340) -> (100,340)  [above]')
print('End cap: semicircle at x=500, from (500,260) around to (500,340), bulging right to (540,300)')
print('Begin cap: semicircle at x=100, from (100,340) around to (100,260), bulging left to (60,300)')
print()

# ---- Verify: check for doubled nodes ----
print('--- CHECKING FOR DOUBLED NODES ---')
outline = result.outline
for i in range(len(outline)):
	j = (i + 1) % len(outline)
	dist = abs(outline[i] - outline[j])
	if dist < 0.1:
		print('  WARNING: nodes %d and %d are coincident (dist=%.4f)' % (i, j, dist))
		print('    [%d] = (%.1f, %.1f)  [%d] = (%.1f, %.1f)' % (
			i, outline[i].real, outline[i].imag,
			j, outline[j].real, outline[j].imag))

# ---- Test 2: Same line, butt cap ----
print()
print('=' * 60)
print('TEST 2: Same line, CAP_BUTT')
print('=' * 60)

stroke2 = PenStroke([seg], nib, closed=False, cap=CAP_BUTT, join=JOIN_ROUND)
result2 = stroke2.expand()

print('Full outline: %d points' % len(result2.outline))
nodes2 = result2.to_nodes()
for i, n in enumerate(nodes2):
	print('  [%d] (%s) = (%.1f, %.1f)' % (i, n.type, n.x, n.y))

# ---- Test 3: Two-segment path with corner, round join ----
print()
print('=' * 60)
print('TEST 3: L-shaped path (two segments), round join')
print('=' * 60)

seg_a = (complex(100, 100), complex(100, 100), complex(300, 100), complex(300, 100))  # horizontal
seg_b = (complex(300, 100), complex(300, 100), complex(300, 300), complex(300, 300))  # vertical up

stroke3 = PenStroke([seg_a, seg_b], nib, closed=False, cap=CAP_BUTT, join=JOIN_ROUND)
result3 = stroke3.expand()

print('Full outline: %d points' % len(result3.outline))
nodes3 = result3.to_nodes()
for i, n in enumerate(nodes3):
	print('  [%d] (%s) = (%.1f, %.1f)' % (i, n.type, n.x, n.y))

print()
print('--- CHECKING FOR DOUBLED NODES ---')
outline3 = result3.outline
for i in range(len(outline3)):
	j = (i + 1) % len(outline3)
	dist = abs(outline3[i] - outline3[j])
	if dist < 0.1:
		print('  WARNING: nodes %d and %d are coincident (dist=%.4f)' % (i, j, dist))

print()
print('DONE')
