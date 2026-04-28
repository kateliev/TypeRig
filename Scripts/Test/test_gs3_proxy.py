# TEST: TypeRig GS3 Proxy — run in Glyphs 3 Macro Panel
# Open a glyph in the Edit View before running.
# -----------------------------------------------------------

from __future__ import print_function
import traceback

# ----------------------------------------------------------- helpers
def section(title):
	print('\n--- {} {}'.format(title, '-' * (50 - len(title))))

def ok(msg):
	print('  PASS  {}'.format(msg))

def fail(msg, err=None):
	print('  FAIL  {}'.format(msg))
	if err:
		print('        {}'.format(err))

def check(label, condition, detail=''):
	if condition:
		ok('{}{}'.format(label, '  ({})'.format(detail) if detail else ''))
	else:
		fail('{}{}'.format(label, '  ({})'.format(detail) if detail else ''))
	return condition

# ----------------------------------------------------------- 1. import
section('1. Import')
try:
	from typerig.proxy.gs3.objects.node    import trNode
	from typerig.proxy.gs3.objects.anchor  import trAnchor
	from typerig.proxy.gs3.objects.contour import trContour
	from typerig.proxy.gs3.objects.shape   import trShape
	from typerig.proxy.gs3.objects.layer   import trLayer
	from typerig.proxy.gs3.objects.glyph   import trGlyph
	ok('all proxy classes imported')
except Exception as e:
	fail('import failed', traceback.format_exc())
	raise SystemExit

# ----------------------------------------------------------- 2. construct
section('2. Construct trGlyph from current glyph')
try:
	tr_g = trGlyph()
	check('trGlyph() constructed',            tr_g is not None)
	check('host is GSGlyph',                  tr_g.host.__class__.__name__ == 'GSGlyph')
	check('name is a string',                 isinstance(tr_g.name, str),        tr_g.name)
	check('unicodes is a list',               isinstance(tr_g.unicodes, list),   str(tr_g.unicodes))
	check('mark is hex string or None',       tr_g.mark is None or (isinstance(tr_g.mark, str) and tr_g.mark.startswith('#')),
	                                          str(tr_g.mark))
	check('active_layer is a string or None', tr_g.active_layer is None or isinstance(tr_g.active_layer, str),
	                                          str(tr_g.active_layer))
except Exception as e:
	fail('construction', traceback.format_exc())
	raise SystemExit

# ----------------------------------------------------------- 3. structure traversal
section('3. Structure traversal (layers > shapes > contours > nodes)')
try:
	layer_count   = len(tr_g.data)
	check('at least one layer',  layer_count >= 1, '{} layer(s)'.format(layer_count))

	tr_l = tr_g[0]
	check('tr_g[0] is trLayer',  isinstance(tr_l, trLayer), tr_l.name)
	check('advance_width >= 0',  tr_l.advance_width >= 0,   str(tr_l.advance_width))
	check('advance_height >= 0', tr_l.advance_height >= 0,  str(tr_l.advance_height))

	shape_count = len(tr_l.data)
	check('shape list accessible', shape_count >= 0, '{} shape(s)'.format(shape_count))

	if shape_count > 0:
		tr_s = tr_l[0]
		check('tr_l[0] is trShape', isinstance(tr_s, trShape))
		check('is_component is bool', isinstance(tr_s.is_component, bool),
		      'component={}'.format(tr_s.is_component))

		if not tr_s.is_component:
			contour_count = len(tr_s.data)
			check('contour list accessible', contour_count >= 0,
			      '{} contour(s)'.format(contour_count))

			if contour_count > 0:
				tr_c = tr_s[0]
				check('tr_s[0] is trContour',  isinstance(tr_c, trContour))
				check('closed is bool',         isinstance(tr_c.closed, bool),
				      'closed={}'.format(tr_c.closed))

				node_count = len(tr_c.nodes)
				check('node list accessible', node_count >= 0,
				      '{} node(s)'.format(node_count))

				if node_count > 0:
					tr_n = tr_c.nodes[0]
					check('node is trNode',     isinstance(tr_n, trNode))
					check('x is float',         isinstance(tr_n.x, float), str(tr_n.x))
					check('y is float',         isinstance(tr_n.y, float), str(tr_n.y))
					check('type in known set',  tr_n.type in ('on', 'off', 'curve', 'move'),
					      str(tr_n.type))
					check('smooth is bool',     isinstance(tr_n.smooth, bool),
					      str(tr_n.smooth))
		else:
			check('component_name is str', isinstance(tr_s.component_name, str),
			      str(tr_s.component_name))

except Exception as e:
	fail('structure traversal', traceback.format_exc())

# ----------------------------------------------------------- 4. anchors
section('4. Anchors')
try:
	tr_l      = tr_g[0]
	anchors   = tr_l.anchors
	check('anchors list returned', isinstance(anchors, list),
	      '{} anchor(s)'.format(len(anchors)))

	if anchors:
		tr_a = anchors[0]
		check('anchor is trAnchor',  isinstance(tr_a, trAnchor))
		check('anchor x is float',   isinstance(tr_a.x, float), str(tr_a.x))
		check('anchor y is float',   isinstance(tr_a.y, float), str(tr_a.y))
		check('anchor name is str',  isinstance(tr_a.name, str), tr_a.name)
	else:
		ok('no anchors on first layer — skipped anchor detail checks')
except Exception as e:
	fail('anchors', traceback.format_exc())

# ----------------------------------------------------------- 5. eject
section('5. Eject (trGlyph -> Core Glyph)')
core_g = None
try:
	core_g = tr_g.eject()

	from typerig.core.objects.glyph   import Glyph
	from typerig.core.objects.layer   import Layer
	from typerig.core.objects.contour import Contour
	from typerig.core.objects.node    import Node

	check('eject returns core Glyph', isinstance(core_g, Glyph))
	check('layer count preserved',
	      len(core_g.data) == len(tr_g.data),
	      '{} vs {}'.format(len(core_g.data), len(tr_g.data)))
	check('glyph name preserved',     core_g.name == tr_g.name,
	      '{!r} vs {!r}'.format(core_g.name, tr_g.name))

	if len(core_g.data) > 0:
		cl = core_g[0]
		tl = tr_g[0]
		check('first layer is core Layer',   isinstance(cl, Layer))
		check('advance_width preserved',
		      abs(cl.advance_width - tl.advance_width) < 0.01,
		      '{} vs {}'.format(cl.advance_width, tl.advance_width))

		# Count contours in proxy vs core
		def _count_contours(shape_list):
			return sum(len(s.data) for s in shape_list if not getattr(s, 'is_component', False))

		proxy_contours = _count_contours(tl.data)
		core_contours  = _count_contours(cl.data)
		check('contour count preserved',
		      proxy_contours == core_contours,
		      '{} vs {}'.format(proxy_contours, core_contours))

except Exception as e:
	fail('eject', traceback.format_exc())

# ----------------------------------------------------------- 6. eject / mount round-trip
section('6. Eject -> shift -> mount -> verify -> restore')
try:
	SHIFT = 13.0   # arbitrary offset that's easy to verify

	tr_l   = tr_g[0]
	core_l = tr_l.eject()

	# Record original first-node position (outline shape only)
	outline_shapes = [s for s in core_l.data if not s.lib.get('component_name')]
	if outline_shapes and len(outline_shapes[0].data) > 0:
		first_contour = outline_shapes[0][0]
		orig_x = first_contour[0].x
		orig_y = first_contour[0].y

		# Shift the whole layer
		core_l.shift(SHIFT, SHIFT)

		shifted_x = first_contour[0].x
		shifted_y = first_contour[0].y
		check('Core shift changes coordinates',
		      abs(shifted_x - (orig_x + SHIFT)) < 0.01,
		      'x: {} -> {} (expected {})'.format(orig_x, shifted_x, orig_x + SHIFT))

		# Mount back
		tr_l.mount(core_l)
		mounted_n = tr_l[0][0].nodes[0]   # trLayer[0]=trShape, [0]=trContour, nodes[0]
		check('mount writes shifted x to host',
		      abs(mounted_n.x - (orig_x + SHIFT)) < 0.01,
		      'got {}, expected {}'.format(mounted_n.x, orig_x + SHIFT))

		# Restore original
		core_l_orig = tr_g.eject()[0]   # fresh eject would give shifted; restore manually
		core_l_orig.shift(-SHIFT, -SHIFT)
		tr_l.mount(core_l_orig)
		restored_n = tr_l[0][0].nodes[0]
		check('restore returns to original x',
		      abs(restored_n.x - orig_x) < 0.01,
		      'got {}, expected {}'.format(restored_n.x, orig_x))

		tr_g.update()
		ok('update() called')

	else:
		ok('no outline contours on first layer — round-trip skipped')

except Exception as e:
	fail('eject/mount round-trip', traceback.format_exc())

# ----------------------------------------------------------- 7. find_layer / add_layer
section('7. find_layer / add_layer')
TEST_LAYER = '__tr_gs3_test__'
try:
	found = tr_g.find_layer(tr_g[0].name)
	check('find_layer finds first layer by name', found is not None)

	missing = tr_g.find_layer('____nonexistent____')
	check('find_layer returns None for missing',  missing is None)

	new_tr_l = tr_g.add_layer(TEST_LAYER)
	check('add_layer returns trLayer',            isinstance(new_tr_l, trLayer))
	check('new layer has correct name',           new_tr_l.name == TEST_LAYER,
	      new_tr_l.name)

	# Clean up — remove the test layer from the host glyph
	for gs_l in list(tr_g.host.layers):
		if gs_l.name == TEST_LAYER:
			tr_g.host.layers.remove(gs_l)
			break
	ok('test layer removed')

except Exception as e:
	fail('find_layer / add_layer', traceback.format_exc())

# ----------------------------------------------------------- done
section('Done')
print()
