#FLM: TR: Stroke Expand MWE
# MODULE: TypeRig / Playground / Stroke Expansion Minimal Working Example
# -----------------------------------------------------------
# Minimal working example:
#   1. Get current FontLab glyph contours
#   2. Convert to TypeRig core via proxy (eject)
#   3. Expand each contour with 80u circular stroke using MetaPen
#   4. Push results back to FontLab (mount)
# -----------------------------------------------------------

import fontlab as fl6
import fontgate as fgt
import FL as legacy
import PythonQt as pqt

from typerig.proxy.tr.objects.glyph import trGlyph

from typerig.core.objects.contour import Contour
from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer
from typerig.core.objects.node import Node

from typerig.core.objects.metapen import PenStroke, Nib, CAP_ROUND, JOIN_ROUND

# - Configuration -------------------------
layer_name = 'Regular'
stroke_width = 80  # units

# - Init ----------------------------------
g = trGlyph()
print('INIT:\tPlayground >> %s !' % g.name)

# - Get the working layer -----------------
tr_layer = g.find_layer(layer_name)

if tr_layer is None:
	print('ERROR:\tLayer <%s> not found!' % layer_name)

else:
	# - Eject core layer (FL-independent copy)
	core_layer = tr_layer.eject()
	print('EJECT:\tLayer <%s> with %d shape(s)' % (core_layer.name, len(core_layer.shapes)))

	# - Create circular nib (uniform 80u stroke)
	nib = Nib.circle(stroke_width)
	print('NIB:\tCircular, diameter=%d' % stroke_width)

	# - Process each contour ------------------
	expanded_contours = []

	for shape in core_layer.shapes:
		for contour in shape.contours:
			print('CONTOUR:\t%d nodes, closed=%s' % (len(contour.nodes), contour.closed))

			# - Get segments as CubicBezier/Line objects
			segments = contour.segments

			if len(segments) == 0:
				print('SKIP:\tEmpty contour')
				continue

			# - Build PenStroke expander
			stroke = PenStroke(
				segments,
				nib,
				closed=contour.closed,
				method=0,
				cap=CAP_ROUND,
				join=JOIN_ROUND
			)

			# - Expand
			result = stroke.expand()

			# - Convert result to core Contour
			outline_nodes = result.to_nodes()

			if len(outline_nodes) > 0:
				expanded_contour = Contour(outline_nodes, closed=True)
				expanded_contours.append(expanded_contour)
				print('EXPAND:\t%d nodes in expanded outline' % len(outline_nodes))
			else:
				print('WARN:\tExpansion produced empty result')

	# - Build new layer content from expanded contours
	if len(expanded_contours) > 0:
		new_shape = Shape(expanded_contours)
		new_layer = Layer(
			[new_shape],
			name=core_layer.name,
			width=core_layer.advance_width,
			height=core_layer.advance_height
		)

		# - Mount back to FontLab
		tr_layer.mount(new_layer)
		g.update()
		print('DONE:\tMounted %d expanded contour(s) back to FL' % len(expanded_contours))
	else:
		print('WARN:\tNo contours were expanded')

print('FINISH:\tStroke Expand MWE complete')
