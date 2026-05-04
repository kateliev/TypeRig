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
_align_target = None
_hobby_bank = {}    # layer_name -> (alpha, beta) Hobby curvature tuple


# ===================================================================
# Internal helpers
# ===================================================================
def _selected_indices(contour):
    """Return list of indices of selected nodes in a contour."""
    return [i for i, n in enumerate(contour.data) if n.selected]


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
def npa_insert(glyph, scope_layers, NodeActions, t=0.5):
    """Insert node at parametric position t on selected segments."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.node_insert(c, idx, t)


def npa_insert_at_extremes(glyph, scope_layers, NodeActions):
    """Insert nodes at curve extremes."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
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
def npa_make_collinear(glyph, scope_layers, NodeActions,
                       mode=-1, equalize=False, target_width=None):
    """Align two selected curve segments to be collinear (parallel-stem
    handle alignment, with optional stem-width equalization)."""
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                idx = _selected_indices(c)
                if idx:
                    NodeActions.make_collinear(c, idx, mode=mode,
                                                equalize=equalize,
                                                target_width=target_width)


# ===================================================================
# 3. ALIGN TOOLS
# ===================================================================
def npa_align(glyph, scope_layers, NodeActions, mode):
    """Align selected nodes using the given mode string."""
    for lyr in _iter_scope(glyph, scope_layers):
        nodes = _selected_nodes(lyr)
        if nodes:
            NodeActions.nodes_align(nodes, mode)


def npa_target_set(glyph, scope_layers, NodeActions):
    """Store the centroid of the current selection as align target.
    Returns True if target was set, False otherwise."""
    global _align_target
    active = glyph.layer(scope_layers[0] if scope_layers else None)
    if active is None:
        _align_target = None
        return False
    sel = _selected_nodes(active)
    if not sel:
        _align_target = None
        return False
    from typerig.core.objects.point import Point
    _align_target = Point(
        sum(n.x for n in sel) / len(sel),
        sum(n.y for n in sel) / len(sel)
    )
    return True


def npa_target_clear(glyph, scope_layers, NodeActions):
    """Clear the stored align target."""
    global _align_target
    _align_target = None


def npa_collapse_to_target(glyph, scope_layers, NodeActions):
    """Move all selected nodes to the stored align target."""
    if _align_target is None:
        return
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            for c in s.contours:
                for n in c.data:
                    if n.selected:
                        n.x = _align_target.x
                        n.y = _align_target.y


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
        reverse (bool): Reverse the resulting order (descending instead of ascending).
    """
    for lyr in _iter_scope(glyph, scope_layers):
        for s in lyr.shapes:
            ContourActions.contour_set_order(s, direction, mode)
            if reverse:
                ContourActions.contour_reverse_order(s)


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
            # Use passed groups or fall back to module-level banks
            a = (contours_A_by_layer or _contour_group_A).get(getattr(lyr, 'name', None), [])
            b = (contours_B_by_layer or _contour_group_B).get(getattr(lyr, 'name', None), [])
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

    The result is appended to the active layer via glyph.shapes.
    """
    active = glyph.layer(scope_layers[0] if scope_layers else None)
    if active is None:
        return
    selected_on = [n for s in active.shapes for c in s.contours
                  for n in c.data if n.selected and n.is_on]
    if len(selected_on) < 2:
        return
    result = DrawActions.draw_square(selected_on, mode=mode)
    if result is not None:
        active.shapes.append(Shape([result]))


def npa_draw_circle(glyph, scope_layers, NodeActions, DrawActions, mode=0):
    """Draw a circle using selected on-curve nodes as reference points.

    Args:
        mode (int): 0 = two-point diameter; 1 = three-point circle.

    The result is appended to the active layer via glyph.shapes.
    """
    active = glyph.layer(scope_layers[0] if scope_layers else None)
    if active is None:
        return
    selected_on = [n for s in active.shapes for c in s.contours
                  for n in c.data if n.selected and n.is_on]
    if len(selected_on) < 2:
        return
    result = DrawActions.draw_circle(selected_on, mode=mode)
    if result is not None:
        active.shapes.append(Shape([result]))


def npa_trace_nodes(glyph, scope_layers, NodeActions, DrawActions, mode=1, closed=True):
    """Draw/trace selected on-curve nodes as line segments or Hobby splines.

    Args:
        mode (int): 1 = lines; 2 = Hobby splines.
        closed (bool): Whether to close the resulting contour.

    The result is appended to the active layer via glyph.shapes.
    """
    active = glyph.layer(scope_layers[0] if scope_layers else None)
    if active is None:
        return
    selected_on = [n for s in active.shapes for c in s.contours
                  for n in c.data if n.selected and n.is_on]
    if len(selected_on) < 2:
        return
    result = DrawActions.trace_nodes(selected_on, mode=mode, closed=closed)
    if result is not None:
        active.shapes.append(Shape([result]))


# ===================================================================
# 9. CONTOUR ALIGNMENT GROUP CAPTURE
# ===================================================================
# Module-level banks for contour groups A and B (per layer name).

_contour_group_A = {}
_contour_group_B = {}


def npa_capture_group_A(glyph, scope_layers, NodeActions):
    """Capture currently selected contours as group A, keyed by layer name."""
    global _contour_group_A
    _contour_group_A = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        selected = _selected_contours(lyr)
        if selected:
            _contour_group_A[name] = list(selected)


def npa_capture_group_B(glyph, scope_layers, NodeActions):
    """Capture currently selected contours as group B, keyed by layer name."""
    global _contour_group_B
    _contour_group_B = {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        selected = _selected_contours(lyr)
        if selected:
            _contour_group_B[name] = list(selected)
