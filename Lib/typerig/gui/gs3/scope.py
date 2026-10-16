# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — scope resolver
#
# Translates the masthead state (pMode, pLayers) for a given trGlyph into a
# concrete list of layer names that npa_* dispatchers iterate.
#
# pLayers is *polymorphic* (FL parity, see typerig-panel.py:355–367):
#   * tuple form  : (active_bool, masters_bool, False, False)
#       Resolved from the masthead's Active/Masters/Selected radio.
#   * checked-rows form (Selected mode):
#       [(layer_name, layer_type), ...]   — only the *checked* rows from
#       TRLayerSelectDialog.get_table().
#
# Behaviour rules (per project decisions):
#   - In Selected mode with NO ticked rows → return []  (no-op the action).
#   - Phantom names (ticked but not present on this glyph) → silently
#     dropped at intersection time.
#   - In tuple mode with both flags False → fall back to active layer.
#
# v1 coverage:
#   pMode  — only 0 (active glyph) is implemented; window/font-selection
#            deferred. Callers operate on a single glyph.
# -------------------------------------------------------------------------

from __future__ import division, print_function


def _is_checked_rows(pLayers):
	'''True if pLayers is the dialog's [(name, type), ...] form.'''
	return isinstance(pLayers, (list,)) or (
		isinstance(pLayers, tuple)
		and len(pLayers) > 0
		and isinstance(pLayers[0], (list, tuple))
		and not isinstance(pLayers[0], bool)
	)


def scope_layers(pMode, pLayers, tr_glyph):
	'''Return the ordered, de-duplicated list of layer names to process.'''
	gs_glyph = tr_glyph.host

	# ---- Selected mode (polymorphic checked-rows) -----------------------
	if _is_checked_rows(pLayers):
		# Empty pick → no-op (deliberate, per spec).
		if not pLayers:
			return []
		picked = [row[0] for row in pLayers if row]
		# Intersect with this glyph's actual layers — phantoms are dropped.
		valid = {layer.name for layer in gs_glyph.layers if layer.name}
		out, seen = [], set()
		for name in picked:
			if name in valid and name not in seen:
				out.append(name)
				seen.add(name)
		return out

	# ---- Tuple form -----------------------------------------------------
	try:
		active_flag, masters_flag, _selected_flag, _ = pLayers
	except Exception:
		# Defensive fallback for malformed input — treat as active-only.
		active_flag, masters_flag = True, False

	names = []

	if active_flag:
		name = tr_glyph.active_layer
		if name:
			names.append(name)

	if masters_flag:
		font = gs_glyph.parent
		if font is not None:
			master_ids = {m.id for m in font.masters}
			for layer in gs_glyph.layers:
				if layer.layerId in master_ids and layer.name not in names:
					names.append(layer.name)

	# Last-resort fallback so a tuple with both flags off still does
	# *something* sensible (active layer). Selected mode is handled above
	# and intentionally returns [] when nothing is ticked.
	if not names:
		name = tr_glyph.active_layer
		if name:
			names.append(name)

	return names
