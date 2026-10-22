# ===================================================================
# TypeRig / Core / Actions / Node Panel Actions
# ===================================================================
# Multi-layer action dispatchers for the FontRig Node Panel.
# Each function iterates scope_layers and applies the corresponding
# NodeActions operation using mirrored selection from the active layer.
#
# All public npa_* functions receive (glyph, scope_layers, NodeActions)
# as their first three arguments, injected by the JS bridge wrapper.
# This avoids global state coupling between the module and the bridge.
# ===================================================================

from __future__ import absolute_import

from typerig.core.objects.shape import Shape

# -- Module-level state (slope bank, align target, hobby bank) -------
_slope_bank = 0
_align_targets = {} # layer_name -> Point target for npa_align / npa_collapse_to_target
_hobby_bank = {}    # layer_name -> (alpha, beta) Hobby curvature tuple
_loop_targets = {}  # layer_name -> (x, y) target for npa_corner_loop_to_target


# ===================================================================
# Internal helpers
# ===================================================================
def _selected_indices(contour):
    """Return list of indices of selected nodes in a contour."""
    return [i for i, n in enumerate(contour.data) if n.selected]


def _selected_segment_starts(contour, select_one_node=False):
    """Indices of on-curve nodes whose outgoing segment is selected.
    A segment counts when both its on-curve ends are selected (FL rule).
    select_one_node=True: every selected on-curve node counts (FL Alt).
    """
    on_idx = [i for i, n in enumerate(contour.data) if n.is_on]
    selected = set(i for i in on_idx if contour.data[i].selected)

    if select_one_node:
        return sorted(selected)

    pairs = list(zip(on_idx, on_idx[1:]))
    if contour.closed and len(on_idx) > 1:
        pairs.append((on_idx[-1], on_idx[0]))

    return [a for a, b in pairs if a in selected and b in selected]


def _selected_nodes(layer):
    """Gather all selected nodes on a layer."""
    return [n for s in layer.shapes for c in s.contours
            for n in c.data if n.selected]


def _selected_oncurve(layer):
    """Gather selected on-curve nodes on a layer."""
    return [n for s in layer.shapes for c in s.contours
            for n in c.data if n.selected and n.is_on]


def _iter_scope(glyph, scope_layers):
    """Yield layer objects for each name in scope_layers."""
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is not None:
            yield lyr


# ===================================================================
# 1. NODE TOOLS
# ===================================================================
def npa_insert(glyph, scope_layers, NodeActions, t=0.5, select_one_node=False):
    """Insert node at parametric position t on selected segments.
    A segment needs both on-curve ends selected; select_one_node=True
    (Alt) splits the outgoing segment of every selected on-curve node.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_segment_starts(c, select_one_node)
                if idx:
                    NodeActions.node_insert(c, idx, t)


def npa_insert_at_extremes(glyph, scope_layers, NodeActions, select_one_node=False):
    """Insert nodes at curve extremes of selected segments (same selection
    rule as npa_insert)."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_segment_starts(c, select_one_node)
                if idx:
                    NodeActions.node_insert_at_extremes(c, idx)


def npa_remove(glyph, scope_layers, NodeActions):
    """Remove selected nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.node_remove(c, idx)


def npa_set_smooth(glyph, scope_layers, NodeActions, smooth=True):
    """Set selected nodes smooth or sharp."""
    for lyr in _iter_scope(glyph, scope_layers):
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.node_set_smooth(nodes, smooth)


def npa_round_coordinates(glyph, scope_layers, NodeActions):
    """Round coordinates of selected nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.node_round_coordinates(nodes, True)


# ===================================================================
# 2. CORNER TOOLS
# ===================================================================
def npa_corner_mitre(glyph, scope_layers, NodeActions, value):
    """Apply mitre to selected on-curve nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                targets = [n for n in c.data if n.selected and n.is_on]
                for n in targets:
                    NodeActions.corner_mitre(n, value)


def npa_corner_round(glyph, scope_layers, NodeActions, value):
    """Apply rounding to selected on-curve nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                targets = [n for n in c.data if n.selected and n.is_on]
                for n in targets:
                    NodeActions.corner_round(n, value)


def npa_corner_loop(glyph, scope_layers, NodeActions, value):
    """Apply loop to selected on-curve nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                targets = [n for n in c.data if n.selected and n.is_on]
                for n in targets:
                    NodeActions.corner_loop(n, value)


def npa_loop_target_set(glyph, scope_layers, NodeActions):
    """Store the first selected on-curve node of each scope layer as that
    layer's loop target. Returns the number of layers with a target."""
    global _loop_targets
    _loop_targets = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        sel = _selected_oncurve(lyr)
        if sel:
            _loop_targets[name] = (sel[0].x, sel[0].y)
    return len(_loop_targets)


def npa_loop_target_clear(glyph, scope_layers, NodeActions):
    """Clear the stored loop targets."""
    global _loop_targets
    _loop_targets = {}


def npa_corner_loop_to_target(glyph, scope_layers, NodeActions, safe_distance=0.):
    """Loop the selected corners of each scope layer toward that layer's
    stored target (npa_loop_target_set), pulled back by safe_distance."""
    for name in scope_layers:
        target = _loop_targets.get(name)
        lyr = glyph.layer(name)
        if target is None or lyr is None:
            continue
        for node in reversed(_selected_oncurve(lyr)):
            NodeActions.corner_loop_to_target(node, target[0], target[1], safe_distance)


def npa_corner_trap(glyph, scope_layers, NodeActions):
    """Create ink trap at selected on-curve nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                targets = [n for n in c.data if n.selected and n.is_on]
                for n in targets:
                    NodeActions.corner_trap(n)


def npa_corner_rebuild(glyph, scope_layers, NodeActions):
    """Rebuild corner geometry at selected nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.corner_rebuild(c, idx)


# ===================================================================
# 2.5 CAP TOOLS
# ===================================================================
# Cap dispatchers operate on contours where exactly two on-curve nodes
# are selected as the cap-end stem corners (A, B). The contour walk
# handles cap_rebuild specially — it accepts any contiguous selection
# inside a cap and infers A, B from the selection's first/last on-curves.

def _cap_corner_indices(contour):
    """Find the two stem-corner indices for cap_butt/round/angular.

    Returns (idx_a, idx_b) — the FIRST and LAST selected on-curve indices
    in contour order — or None if there aren't exactly two selected
    on-curves bracketing a cap region.
    """
    on_indices = [i for i, n in enumerate(contour.data)
                  if n.selected and n.is_on]
    if len(on_indices) < 2:
        return None
    return on_indices[0], on_indices[-1]


def npa_cap_butt(glyph, scope_layers, NodeActions, side='auto'):
    """Build a perpendicular flat (butt) cap between two stem-corner nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                pair = _cap_corner_indices(c)
                if pair is not None:
                    NodeActions.cap_butt(c, pair[0], pair[1], side=side)


def npa_cap_round(glyph, scope_layers, NodeActions, curvature=1.0, keep_length=False):
    """Build an italic-aware circular cap between two stem-corner nodes.

    keep_length=True preserves overall path length (FL behaviour) by shortening
    each stem by the cap radius before fitting the cap inside.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                pair = _cap_corner_indices(c)
                if pair is not None:
                    NodeActions.cap_round(c, pair[0], pair[1],
                                          curvature=curvature, keep_length=keep_length)


def npa_cap_angular(glyph, scope_layers, NodeActions):
    """Build a pointed (miter) cap between two stem-corner nodes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                pair = _cap_corner_indices(c)
                if pair is not None:
                    NodeActions.cap_angular(c, pair[0], pair[1])


def npa_cap_rebuild(glyph, scope_layers, NodeActions, target='butt'):
    """Universal cap rebuilder — flatten any existing cap to a butt cut."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.cap_rebuild(c, idx, target=target)


# ===================================================================
# 2.6 CURVE ALIGNMENT TOOLS
# ===================================================================
def _layer_master_name(layer):
    """Best-effort master-name lookup that works across host glyph proxies.

    Probes (in order):
      * layer.master_name / masterName             (explicit attribute)
      * layer.master.name                          (FL pMaster, Glyphs trLayer wrapper)
      * layer.host.master.name                     (Glyphs trLayer -> GSLayer)
      * layer.name                                 (FL fallback: layer name == master name)
    """
    for attr in ('master_name', 'masterName'):
        v = getattr(layer, attr, None)
        if isinstance(v, str) and v:
            return v
    for path in (('master', 'name'), ('host', 'master', 'name')):
        obj = layer
        for step in path:
            obj = getattr(obj, step, None)
            if obj is None:
                break
        if isinstance(obj, str) and obj:
            return obj
    return getattr(layer, 'name', None)


def _snap_to_for_layer(layer, snap_lookup):
    """Resolve the snap_to list for a given layer from a master-name -> value
    dict. Returns None when no preset is configured for this master."""
    if not snap_lookup:
        return None
    name = _layer_master_name(layer)
    if name is None:
        return None
    v = snap_lookup.get(name)
    if v is None:
        return None
    return [float(v)]


def npa_make_collinear(glyph, scope_layers, NodeActions,
                       mode=-1, equalize=False, target_width=None,
                       snap_lookup=None, snap_tolerance=0.25):
    """Align two selected curve segments to be collinear (parallel-stem
    handle alignment, with optional stem-width equalization).

    snap_lookup: optional dict {master_name: preset_width}. When set and
    equalize=True, the equalized width is snapped to the master's preset
    within snap_tolerance * measured."""
    for lyr in _iter_scope(glyph, scope_layers):
        snap_to = _snap_to_for_layer(lyr, snap_lookup)
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.make_collinear(c, idx, mode=mode,
                                                equalize=equalize,
                                                target_width=target_width,
                                                snap_to=snap_to,
                                                snap_tolerance=snap_tolerance)


def npa_make_monoline(glyph, scope_layers, NodeActions,
                      target_width=None, preserve_taper=False,
                      snap_lookup=None, snap_tolerance=0.25):
    """Regularize two selected curve segments as +/- offsets of their shared
    control-polygon median (monoline-pen model). Both sides end up with
    matching tangents AND matching handle lengths -> truly parallel.

    snap_lookup: optional dict {master_name: preset_width}. When set and
    target_width is None, the resulting width snaps to the master's preset
    within snap_tolerance * measured."""
    for lyr in _iter_scope(glyph, scope_layers):
        snap_to = _snap_to_for_layer(lyr, snap_lookup)
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.make_monoline(c, idx,
                                              target_width=target_width,
                                              preserve_taper=preserve_taper,
                                              snap_to=snap_to,
                                              snap_tolerance=snap_tolerance)


# ===================================================================
# 3. ALIGN TOOLS
# ===================================================================
def npa_align(glyph, scope_layers, NodeActions, mode,
              smart_shift=True, keep_relations=False, lerp_shift=False,
              intercept=False, extrapolate=False, use_target=False):
    """Align selected nodes using the given mode string.

    Modifier kwargs are forwarded to NodeActions.nodes_align. When
    use_target=True, each layer's stored align target (set via
    npa_target_set) is passed in as the override target; layers without
    a stored target fall back to the mode-computed one.
    """
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        target = _align_targets.get(name) if use_target else None
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.nodes_align(
                nodes, mode,
                smart_shift=smart_shift,
                keep_relations=keep_relations,
                lerp_shift=lerp_shift,
                intercept=intercept,
                extrapolate=extrapolate,
                target=target,
            )


def npa_align_to_y(glyph, scope_layers, NodeActions, y_by_layer,
                   smart_shift=True, keep_relations=False, lerp_shift=False,
                   intercept=False, extrapolate=False):
    """Align selected nodes vertically to a per-layer Y value.

    y_by_layer: dict[layer_name -> y]. The host fills it from each layer's
    master metrics (ascender, cap height, x-height, baseline, descender).
    Layers missing from the dict are skipped. Modifier kwargs as npa_align.
    """
    from typerig.core.objects.point import Point
    for name in scope_layers:
        y = y_by_layer.get(name)
        lyr = glyph.layer(name)
        if y is None or lyr is None:
            continue
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.nodes_align(
                nodes, 'T',
                smart_shift=smart_shift,
                keep_relations=keep_relations,
                lerp_shift=lerp_shift,
                intercept=intercept,
                extrapolate=extrapolate,
                target=Point(0., float(y)),
            )


def npa_target_set(glyph, scope_layers, NodeActions, safe_distance=0):
    """Store a per-layer align target from the current selection.

    For each scope layer: one selected node -> that node's coordinates on
    the layer; several -> the centroid of the layer's selection. So the
    target follows the node across masters (FL popup-node-align target_set).
    Optional safe_distance is added to both X and Y (pull back from target
    on each axis). Returns True if any layer got a target.
    """
    global _align_targets
    from typerig.core.objects.point import Point
    _align_targets = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        sel = _selected_nodes(lyr)
        if not sel:
            continue
        if len(sel) == 1:
            tx, ty = sel[0].x, sel[0].y
        else:
            tx = sum(n.x for n in sel) / len(sel)
            ty = sum(n.y for n in sel) / len(sel)
        _align_targets[name] = Point(tx + safe_distance, ty + safe_distance)
    return bool(_align_targets)


def npa_target_clear(glyph, scope_layers, NodeActions):
    """Clear the stored align targets."""
    global _align_targets
    _align_targets = {}


def npa_collapse_to_target(glyph, scope_layers, NodeActions):
    """Move all selected nodes of each scope layer to that layer's stored
    align target."""
    for name in scope_layers:
        target = _align_targets.get(name)
        lyr = glyph.layer(name)
        if target is None or lyr is None:
            continue
        for s in lyr.shapes:
            for c in s.contours:
                for n in c.data:
                    if n.selected:
                        n.x = target.x
                        n.y = target.y


# ===================================================================
# 4. SLOPE TOOLS
# ===================================================================
def npa_slope_copy(glyph, scope_layers, NodeActions):
    """Copy slope from the first and last selected on-curve nodes.
    Returns the slope value (float)."""
    global _slope_bank
    active = glyph.layer(scope_layers[0] if scope_layers else None)
    if active is None:
        _slope_bank = 0
        return 0
    sel = _selected_oncurve(active)
    if len(sel) >= 2:
        _slope_bank = NodeActions.slope_from_nodes(sel[0], sel[-1])
    else:
        _slope_bank = 0
    return _slope_bank


def npa_slope_from_angle(glyph, scope_layers, NodeActions, angle):
    """Store the slope of an italic angle (degrees from vertical, positive
    leans right) in the slope bank, for npa_slope_paste. Returns the slope."""
    import math
    global _slope_bank
    _slope_bank = math.tan(math.radians(90. - float(angle)))
    return _slope_bank


def npa_slope_paste(glyph, scope_layers, NodeActions, pivot_is_max, flip):
    """Apply stored slope to selected nodes across scope layers."""
    for lyr in _iter_scope(glyph, scope_layers):
        nodes = _selected_nodes(lyr)
        if len(nodes) >= 2:
            NodeActions.slope_apply(nodes, _slope_bank, (pivot_is_max, flip))


# ===================================================================
# 5. MOVE TOOLS
# ===================================================================
def npa_move(glyph, scope_layers, NodeActions, dx, dy, method, angle=0., slope=None):
    """Move selected nodes across scope layers."""
    for lyr in _iter_scope(glyph, scope_layers):
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.nodes_move(nodes, dx, dy, method, angle, slope)


# ===================================================================
# 6. CURVE TOOLS
# ===================================================================
# All npa_curve_* functions receive CurveActions as the 4th positional
# argument (injected by the caller, same pattern as NodeActions).
# CurveActions lives in typerig/core/actions/curve_actions.py.
# ===================================================================

def npa_segment_convert(glyph, scope_layers, NodeActions, CurveActions, to_curve=True):
    """Convert selected segments between line and curve.

    Args:
        to_curve (bool): True converts line→curve; False converts curve→line.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    if to_curve:
                        CurveActions.segment_convert_to_curve(c, idx)
                    else:
                        CurveActions.segment_convert_to_line(c, idx)


def npa_curve_optimize(glyph, scope_layers, NodeActions, CurveActions,
                       method='tunni', curvature=(1., 1.), proportion=(0.3, 0.3)):
    """Optimize selected curve segments.

    Args:
        method (str): 'tunni', 'hobby', or 'proportional'.
        curvature (tuple): (alpha, beta) for Hobby method.
        proportion (tuple): (p0_ratio, p1_ratio) for proportional method.

    Note:
        Both endpoints of a segment must be selected for that segment to be
        processed (CurveActions.curve_optimize enforces this internally).
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    CurveActions.curve_optimize(c, idx, method=method,
                                                curvature=curvature,
                                                proportion=proportion)


def npa_hobby_copy(glyph, scope_layers, NodeActions, CurveActions):
    """Copy Hobby curvature from the first selected curve segment on each scope layer.

    Stores the result in the module-level _hobby_bank dict keyed by layer name.
    Returns the bank so the caller can inspect it (e.g. to toggle a button state).
    """
    global _hobby_bank
    _hobby_bank = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        found = False
        for s in lyr.shapes:
            if found:
                break
            for c in s.contours:
                if found:
                    break
                for i in _selected_indices(c):
                    cv = CurveActions.hobby_curvature_get(c, i)
                    if cv is not None:
                        _hobby_bank[name] = cv
                        found = True
                        break
    return _hobby_bank


def npa_hobby_paste(glyph, scope_layers, NodeActions, CurveActions, swap=False):
    """Apply stored Hobby curvature to all selected curve segments across scope layers.

    Uses the curvature stored per layer by the most recent npa_hobby_copy call.
    If a layer has no stored value, it is skipped.

    Args:
        swap (bool): If True, swaps alpha and beta before applying (mirrors the curve).
    """
    for name in scope_layers:
        cv = _hobby_bank.get(name)
        if cv is None:
            continue
        if swap:
            cv = (cv[1], cv[0])
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        for s in lyr.shapes:
            for c in s.contours:
                for i in _selected_indices(c):
                    CurveActions.hobby_curvature_apply(c, i, cv)


# ===================================================================
# 7. CONTOUR TOOLS
# ===================================================================
# All npa_contour_* functions receive ContourActions as the 4th
# positional argument, injected by the bridge dispatcher (same pattern
# as CurveActions — the dispatcher inspects params[3] by name).
# ===================================================================

def _selected_contours(layer):
    """Return list of contours (proxy or core) that have at least one selected node."""
    result = []
    for s in layer.shapes:
        for c in s.contours:
            if any(n.selected for n in c.data):
                result.append(c)
    return result


def _selected_or_all_contours(layer):
    """Selected contours, or all contours if nothing is selected.

    Mirrors FL contour_set_winding fallback: a click with no selection
    operates on every contour in the layer.
    """
    result = _selected_contours(layer)
    if result:
        return result
    return [c for s in layer.shapes for c in s.contours]


def npa_contour_close(glyph, scope_layers, NodeActions, ContourActions):
    """Close all selected contours."""
    for lyr in _iter_scope(glyph, scope_layers):
        for c in _selected_contours(lyr):
            ContourActions.contour_close(c)


def npa_contour_winding(glyph, scope_layers, NodeActions, ContourActions, ccw=True):
    """Set winding direction of selected contours (or all if none selected).

    Args:
        ccw (bool): True = counter-clockwise (default); False = clockwise.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for c in _selected_or_all_contours(lyr):
            ContourActions.contour_set_winding(c, ccw=ccw)


def npa_contour_reverse(glyph, scope_layers, NodeActions, ContourActions):
    """Reverse direction of selected contours (or all if none selected)."""
    for lyr in _iter_scope(glyph, scope_layers):
        for c in _selected_or_all_contours(lyr):
            ContourActions.contour_reverse(c)


def npa_contour_start_next(glyph, scope_layers, NodeActions, ContourActions, forward=True):
    """Move the start point one on-curve node forward (or backward).

    Args:
        forward (bool): True = next node; False = previous node.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for c in _selected_or_all_contours(lyr):
            ContourActions.contour_set_start_next(c, forward=forward)


def npa_contour_start_at_selection(glyph, scope_layers, NodeActions, ContourActions):
    """Set the start point to the first selected on-curve node on each contour."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                for i in idx:
                    if c.data[i].is_on:
                        ContourActions.contour_set_start(c, i)
                        break


def npa_contour_smart_start(glyph, scope_layers, NodeActions, ContourActions, control=(0, 0)):
    """Set the start point to the on-curve node closest to a bounding-box corner.

    Args:
        control (tuple): Corner selector:
            (0, 0) = Bottom-Left, (0, 1) = Top-Left,
            (1, 0) = Bottom-Right, (1, 1) = Top-Right.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for c in _selected_or_all_contours(lyr):
            ContourActions.contour_smart_start(c, control)


def npa_contour_order(glyph, scope_layers, NodeActions, ContourActions, direction=0, mode='BL', reverse=False):
    """Sort contour order within each shape.

    Args:
        direction (int): Axis selector — 0 = sort by X, 1 = sort by Y.
        mode (str): Reference corner: 'BL', 'TL', 'BR', 'TR'.
        reverse (bool): Descending on the primary axis. Ties still read
            left -> right / top -> bottom (a full list flip would break that).

    The order is computed ONCE on a reference layer (the active layer if in
    scope, else the first) and applied to every compatible layer, so masters
    cannot drift apart when contours are nearly level. Incompatible layers
    are sorted on their own and reported.
    """
    layers = list(_iter_scope(glyph, scope_layers))
    if not layers:
        return

    active = glyph.layer() if hasattr(glyph, 'active_layer') else None
    ref = next((lyr for lyr in layers if active is not None and lyr.name == active.name), layers[0])
    ref_shapes = list(ref.shapes)
    ref_orders = [s.sort_order(direction, mode, reverse) for s in ref_shapes]

    def shape_sig(shape):
        return [len(c.data) for c in shape.contours]

    # Signatures BEFORE any reordering (ref itself gets reordered in the loop)
    ref_sigs = [shape_sig(s) for s in ref_shapes]

    for lyr in layers:
        for k, s in enumerate(lyr.shapes):
            if k < len(ref_sigs) and shape_sig(s) == ref_sigs[k]:
                ContourActions.contour_apply_order(s, ref_orders[k])
            else:
                if len(s.contours) > 1:
                    print('[contour order] {} / {}: not compatible with {}, sorted on its own.'.format(
                        getattr(glyph, 'name', '?'), lyr.name, ref.name))
                ContourActions.contour_set_order(s, direction, mode, descending=reverse)


def npa_contour_order_reverse(glyph, scope_layers, NodeActions, ContourActions):
    """Reverse contour order within each shape."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            ContourActions.contour_reverse_order(s)


def npa_contour_align(glyph, scope_layers, NodeActions, ContourActions,
                      align_x='C', align_y='E', mode='CC',
                      contours_A_by_layer=None, contours_B_by_layer=None):
    """Align selected contours to each other or to a target.

    Args:
        align_x (str): Horizontal alignment: 'L', 'R', 'C', 'K' (keep).
        align_y (str): Vertical alignment: 'B', 'T', 'E', 'X' (keep).
        mode (str): One of:
            'CC' - selected contours to each other.
            'CL' - selected contours to the layer bounding box.
            'CN' - selected contours to a selected on-curve node;
                   the first selected contour hosts the target node.
            'AB' - group A to group B; pass `contours_A_by_layer`
                   and `contours_B_by_layer` as {layer_name: [contour, ...]}.
        contours_A_by_layer (dict|None): per-layer group A snapshots.
        contours_B_by_layer (dict|None): per-layer group B snapshots.

    When contours_A/B are None, uses module-level _contour_group_A/B.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        contours = _selected_contours(lyr)

        if mode == 'CC':
            if len(contours) >= 2:
                ContourActions.contour_align(contours, mode='CC',
                                             align_x=align_x, align_y=align_y)

        elif mode == 'CL':
            if not contours:
                contours = [c for s in lyr.shapes for c in s.contours]
            try:
                layer_bounds = lyr.bounds
            except Exception:
                continue
            if contours:
                ContourActions.contour_align(contours, mode='CL',
                                             align_x=align_x, align_y=align_y,
                                             layer_bounds=layer_bounds)

        elif mode == 'CN':
            if len(contours) < 2:
                continue
            # Find the first selected on-curve in the first selected contour.
            target_node = None
            for n in contours[0].data:
                if n.selected and n.is_on:
                    target_node = n
                    break
            if target_node is None:
                continue
            ContourActions.contour_align(contours, mode='CN',
                                         align_x=align_x, align_y=align_y,
                                         target_node=target_node)

        elif mode == 'AB':
            # Use passed groups or fall back to module-level banks.
            # Banks may store either live contour refs (Glyphs host) or
            # (shape_idx, contour_idx) tuples (FontRig — see _resolve_group).
            lname = getattr(lyr, 'name', None)
            a_src = (contours_A_by_layer or _contour_group_A).get(lname, [])
            b_src = (contours_B_by_layer or _contour_group_B).get(lname, [])
            a = _resolve_group(glyph, lname, a_src)
            b = _resolve_group(glyph, lname, b_src)
            if a and b:
                ContourActions.contour_align(None, mode='AB',
                                     align_x=align_x, align_y=align_y,
                                     contours_A=a, contours_B=b)


def npa_contour_transform(glyph, scope_layers, NodeActions, ContourActions,
                          scale_x=100., scale_y=100.,
                          translate_x=0., translate_y=0.,
                          rotate=0., skew_x=0., skew_y=0.,
                          origin='C'):
    """Apply an affine transform to selected contours (or all if none selected).

    Args:
        scale_x, scale_y (float): Percent scale.
        translate_x, translate_y (float): Translation in units.
        rotate (float): Rotation in degrees.
        skew_x, skew_y (float): Skew in degrees.
        origin (str): Origin code: 'O' (absolute origin) or one of
            'BL','BM','BR','TL','TM','TR','LM','C','RM'.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        contours = _selected_or_all_contours(lyr)
        if contours:
            ContourActions.contour_transform(contours,
                scale_x=scale_x, scale_y=scale_y,
                translate_x=translate_x, translate_y=translate_y,
                rotate=rotate, skew_x=skew_x, skew_y=skew_y,
                origin=origin)


def npa_contour_distribute_h(glyph, scope_layers, NodeActions, ContourActions):
    """Distribute selected contours evenly along the horizontal axis."""
    for lyr in _iter_scope(glyph, scope_layers):
        contours = _selected_contours(lyr)
        if len(contours) >= 3:
            ContourActions.contour_distribute_horizontal(contours)


def npa_contour_distribute_v(glyph, scope_layers, NodeActions, ContourActions):
    """Distribute selected contours evenly along the vertical axis."""
    for lyr in _iter_scope(glyph, scope_layers):
        contours = _selected_contours(lyr)
        if len(contours) >= 3:
            ContourActions.contour_distribute_vertical(contours)


def npa_contour_flip(glyph, scope_layers, NodeActions, ContourActions, horizontal=True):
    """Flip selected contours around their collective bounding-box centre.

    Args:
        horizontal (bool): True = flip left/right; False = flip top/bottom.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        contours = _selected_contours(lyr)
        if contours:
            ContourActions.contour_flip(contours, horizontal=horizontal)


# ===================================================================
# 8. DRAWING TOOLS
# ===================================================================
# Drawing tools receive DrawActions as the 4th argument.
# They create new contours from selected on-curve nodes and append
# them to the active layer.

def npa_draw_square(glyph, scope_layers, NodeActions, DrawActions, mode=0):
    """Draw a square using selected on-curve nodes as reference points.

    Args:
        mode (int): 0 = two-point diagonal; 1 = two-midpoint square.

    The result is appended per-layer for every layer in scope.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        selected_on = [n for s in lyr.shapes for c in s.contours
                       for n in c.data if n.selected and n.is_on]
        if len(selected_on) < 2:
            continue
        result = DrawActions.draw_square(selected_on, mode=mode)
        if result is not None:
            lyr.shapes.append(Shape([result]))


def npa_draw_circle(glyph, scope_layers, NodeActions, DrawActions, mode=0):
    """Draw a circle using selected on-curve nodes as reference points.

    Args:
        mode (int): 0 = two-point diameter; 1 = three-point circle.

    The result is appended per-layer for every layer in scope.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        selected_on = [n for s in lyr.shapes for c in s.contours
                       for n in c.data if n.selected and n.is_on]
        if len(selected_on) < 2:
            continue
        result = DrawActions.draw_circle(selected_on, mode=mode)
        if result is not None:
            lyr.shapes.append(Shape([result]))


def npa_trace_nodes(glyph, scope_layers, NodeActions, DrawActions, mode=1, closed=True):
    """Draw/trace selected on-curve nodes as line segments or Hobby splines.

    Args:
        mode (int): 1 = lines; 2 = Hobby splines.
        closed (bool): Whether to close the resulting contour.

    The result is appended per-layer for every layer in scope.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        selected_on = [n for s in lyr.shapes for c in s.contours
                       for n in c.data if n.selected and n.is_on]
        if len(selected_on) < 2:
            continue
        result = DrawActions.trace_nodes(selected_on, mode=mode, closed=closed)
        if result is not None:
            lyr.shapes.append(Shape([result]))


# ===================================================================
# 9. CONTOUR ALIGNMENT GROUP CAPTURE
# ===================================================================
# Module-level banks for contour groups A and B (per layer name).

_contour_group_A = {}
_contour_group_B = {}


def _resolve_group(glyph, layer_name, items):
    """Resolve a captured group to live Contour objects on the current glyph.

    `items` may be either a list of Contour objects (Glyphs/FL hosts where
    references survive across calls) or a list of (shape_idx, contour_idx)
    tuples (FontRig, where the glyph is rebuilt from XML on every call so
    references go stale). The two formats are auto-detected.
    """
    if not items:
        return []
    first = items[0]
    if isinstance(first, tuple) and len(first) == 2 and \
            isinstance(first[0], int) and isinstance(first[1], int):
        lyr = glyph.layer(layer_name) if layer_name else None
        if lyr is None:
            return []
        out = []
        shapes = list(lyr.shapes)
        for si, ci in items:
            if 0 <= si < len(shapes):
                contours = list(shapes[si].contours)
                if 0 <= ci < len(contours):
                    out.append(contours[ci])
        return out
    return list(items)


def _capture_group_indices(glyph, scope_layers):
    """Walk scope and return {layer_name: [(shape_idx, contour_idx), ...]}
    for every contour with at least one selected node. Stable across
    XML round-trips (FontRig) and cheap to resolve later."""
    out = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        ids = []
        for si, s in enumerate(lyr.shapes):
            for ci, c in enumerate(s.contours):
                if any(n.selected for n in c.data):
                    ids.append((si, ci))
        if ids:
            out[name] = ids
    return out


def npa_capture_group_A(glyph, scope_layers, NodeActions):
    """Capture currently selected contours as group A.

    Stores stable (shape_idx, contour_idx) tuples per layer name so the
    bank survives FontRig's per-call Glyph.from_XML rebuild. Resolved to
    live Contour objects at align time via _resolve_group.
    """
    global _contour_group_A
    _contour_group_A = _capture_group_indices(glyph, scope_layers)


def npa_capture_group_B(glyph, scope_layers, NodeActions):
    """Capture currently selected contours as group B.

    Stores stable (shape_idx, contour_idx) tuples per layer name so the
    bank survives FontRig's per-call Glyph.from_XML rebuild. Resolved to
    live Contour objects at align time via _resolve_group.
    """
    global _contour_group_B
    _contour_group_B = _capture_group_indices(glyph, scope_layers)
