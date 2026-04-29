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
# CurveActions lives in typerig/core/actions/curve-actions.py.
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
