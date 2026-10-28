# ===================================================================
# TypeRig / Core / Actions / Cut Panel Actions
# ===================================================================
# Multi-layer action dispatchers for contour cut / stroke-separate /
# medial-axis extract operations. Host-agnostic: works on FL, GS3, and
# FontRig (pure core) via the ContourActions and core algo modules.
#
# All public npa_* functions receive (glyph, scope_layers, NodeActions,
# ContourActions) as their first four arguments, injected by the host
# bridge wrapper.
# ===================================================================

from __future__ import absolute_import

from typerig.core.objects.shape import Shape
from typerig.core.algo.stroke_sep import StrokeSep
from typerig.core.algo.stroke_sep_common import (
    apply_cuts_exact,
    check_contour_compatibility,
    contour_signature,
    plan_cut_nodes,
)
from typerig.core.algo.mat_extract import extract_medial_axis
from typerig.core.algo.stem_center import StemCenterSnap, StemCenterStatus


# ===================================================================
# Internal helpers
# ===================================================================
def _iter_scope(glyph, scope_layers):
    """Yield layer objects for each name in scope_layers."""
    for name in scope_layers:
        lyr = glyph.layer(name)
        if lyr is not None:
            yield lyr


def _eject(layer):
    """Eject `layer` to a pure-core ``Layer`` if it's a host proxy.

    On pure-core hosts (FontRig) the layer IS already a core ``Layer``;
    there is no ``eject`` method, so we return the layer directly.
    Mutations to the result update the live layer in place.
    """
    eject = getattr(layer, 'eject', None)
    if callable(eject):
        return eject()
    return layer


def _mount(layer, core_layer):
    """Write `core_layer` state back to a host-proxy `layer`.

    On pure-core hosts this is a no-op (mutations already landed on the
    live layer because ``eject`` returned identity).
    """
    mount = getattr(layer, 'mount', None)
    if callable(mount):
        mount(core_layer)


def _selected_triples(layer):
    """Return list of (sid, cid, nid) triples for selected on-curve nodes
    on `layer`. Mirrors eGlyph.selectedAtShapes() output ordering.

    Operates on either a host proxy or a pure-core ``Layer``.
    """
    triples = []
    for sid, shape in enumerate(layer.shapes):
        for cid, contour in enumerate(shape.contours):
            for nid, node in enumerate(contour.data):
                if node.selected and node.is_on:
                    triples.append((sid, cid, nid))
    return triples


def _selected_oncurve_nodes(layer):
    """Gather selected on-curve nodes on a layer (flat list)."""
    return [n for s in layer.shapes for c in s.contours
            for n in c.data if n.selected and n.is_on]


# ===================================================================
# 1. CONTOUR SLICE / WELD
# ===================================================================
def _slice_core_layer(core_layer, ContourActions, expanded=False,
                      fallback_triples=None):
    """Run the slice orchestrator on a pure-core layer in place. Returns
    True if any contour was sliced/welded.

    ``fallback_triples``: if no selection survived the eject, use these
    proxy-side triples. Positions in the ejected layer are identical to
    the proxy layer's, so the same (sid, cid, nid) coordinates apply.
    """
    triples = _selected_triples(core_layer)
    if len(triples) < 2 and fallback_triples and len(fallback_triples) >= 2:
        triples = fallback_triples
    if len(triples) < 2:
        return False

    by_shape = {}
    for sid, cid, nid in triples:
        by_shape.setdefault(sid, []).append((sid, cid, nid))

    mutated = False
    for sid, sh_triples in by_shape.items():
        if sid >= len(core_layer.shapes):
            continue
        if ContourActions.contour_slice(core_layer.shapes[sid],
                                        sh_triples, expanded=expanded):
            mutated = True
    return mutated


def _propagate_selection(core_layer, fallback_triples):
    """Mark core nodes selected based on (sid, cid, nid) triples — used
    when the eject path didn't propagate ``selected`` and we need core
    selection for downstream traversal (e.g. auto-align)."""
    if not fallback_triples:
        return
    for sid, cid, nid in fallback_triples:
        if sid >= len(core_layer.shapes):
            continue
        contours = core_layer.shapes[sid].contours
        if cid >= len(contours):
            continue
        if nid >= len(contours[cid].data):
            continue
        contours[cid].data[nid].selected = True


def _auto_align_core_layer(core_layer, ContourActions):
    """Run the auto-align orchestrator on a pure-core layer in place.
    Returns True if any pair was aligned."""
    by_contour = {}
    for s in core_layer.shapes:
        for c in s.contours:
            sel = [n for n in c.data if n.selected and n.is_on]
            if sel:
                by_contour[id(c)] = (c, sel)

    all_nodes = [n for _, (_, sel) in by_contour.items() for n in sel]
    if len(all_nodes) < 4:
        return False

    pairs = []
    for _, (contour, sel) in by_contour.items():
        if len(sel) >= 2:
            p_first, p_second = ContourActions.node_neighbor_pairs(
                contour, sel)
            if p_first:
                pairs.append(p_first)
            if p_second:
                pairs.append(p_second)

    if len(pairs) < 2 and len(all_nodes) >= 4:
        ref_contour = next(iter(by_contour.values()))[0]
        p_first, p_second = ContourActions.node_neighbor_pairs(
            ref_contour, all_nodes)
        pairs = [p for p in (p_first, p_second) if p]

    if not pairs:
        return False

    for pair in pairs:
        mode = ContourActions.junction_align_mode(pair)
        ContourActions.contour_pair_align(pair, mode)
    return True


def npa_contour_slice(glyph, scope_layers, NodeActions, ContourActions,
                      expanded=False):
    """Slice contours at selection. Same-contour selection extracts a
    closed piece between the two cut points; cross-contour selection welds
    the two contours into one closed contour at the cut points.

    Eject/mount: structural mutations (split/glue, contour add/remove)
    are not safely reflected through host proxies, so we always work on
    a pure-core copy and mount back. On pure-core hosts both helpers are
    identity, so this incurs no cost.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        live_triples = _selected_triples(lyr)
        core_layer = _eject(lyr)
        if core_layer is None:
            continue
        if _slice_core_layer(core_layer, ContourActions,
                             expanded=expanded,
                             fallback_triples=live_triples):
            _mount(lyr, core_layer)


def npa_contour_auto_align(glyph, scope_layers, NodeActions, ContourActions):
    """Auto overlap align: classify and align two neighbor-pairs at a cut
    junction. Operates on selection of >=4 on-curve nodes per layer."""
    for lyr in _iter_scope(glyph, scope_layers):
        live_triples = _selected_triples(lyr)
        core_layer = _eject(lyr)
        if core_layer is None:
            continue
        # If selection didn't survive the eject, restore it from the live
        # proxy triples before running pair detection.
        if not _selected_triples(core_layer):
            _propagate_selection(core_layer, live_triples)
        if _auto_align_core_layer(core_layer, ContourActions):
            _mount(lyr, core_layer)


def npa_contour_slice_align(glyph, scope_layers, NodeActions, ContourActions,
                            expanded=False):
    """Slice + auto-align in one step. Mirrors popup do_cut_align_auto.

    Performs both operations within a SINGLE eject/mount round-trip so
    selection state on the cloned cut nodes survives between the two
    steps. (A separate mount between slice and auto-align would rebuild
    the host paths from scratch, dropping the per-node ``selected``
    flag and leaving auto-align with no input.)
    """
    for lyr in _iter_scope(glyph, scope_layers):
        live_triples = _selected_triples(lyr)
        core_layer = _eject(lyr)
        if core_layer is None:
            continue
        # Restore selection on core if the eject path didn't carry it.
        if not _selected_triples(core_layer):
            _propagate_selection(core_layer, live_triples)
        sliced = _slice_core_layer(core_layer, ContourActions,
                                   expanded=expanded,
                                   fallback_triples=live_triples)
        aligned = _auto_align_core_layer(core_layer, ContourActions)
        if sliced or aligned:
            _mount(lyr, core_layer)


def npa_stem_center(glyph, scope_layers, NodeActions, ContourActions,
                    force_axis=None, active_layer=None):
    """Stem-Center Snap: snap the selected nodes of each scope layer to the
    centerline of the perpendicular stem they sit inside. Mirrors FL
    TRStemCenterActionCollector.snap_stem_center.

    force_axis: 'H' (horizontal stem, nodes move on Y), 'V' (vertical stem,
    nodes move on X) or None (decided from the active layer's selection
    bbox). active_layer: layer whose selection drives the axis; default
    the first scope layer. Only coordinates change, so the live layer is
    written directly (no mount).

    Returns dict[layer_name -> StemCenterStatus] (OK, AXIS_AMBIGUOUS,
    NO_CANDIDATE or NO_SELECTION).
    """
    contours_by_layer, selections_by_layer, live_by_layer = {}, {}, {}
    for name in scope_layers:
        lyr = glyph.layer(name)
        core_layer = _eject(lyr) if lyr is not None else None
        if core_layer is None:
            continue
        core_contours = [c for sh in core_layer.shapes for c in sh.contours]
        live_contours = [c for sh in lyr.shapes for c in sh.contours]
        if not core_contours or len(core_contours) != len(live_contours):
            continue
        sel = [(ci, ni) for ci, c in enumerate(live_contours)
               for ni, n in enumerate(c.data) if n.selected]
        contours_by_layer[name] = core_contours
        selections_by_layer[name] = sel
        live_by_layer[name] = live_contours
    if not contours_by_layer:
        return {}

    if active_layer not in contours_by_layer:
        active_layer = next((n for n in scope_layers if n in contours_by_layer), None)
    plan = StemCenterSnap(contours_by_layer, selections_by_layer,
                          force_axis=force_axis, active_layer=active_layer).plan()

    for name, entry in plan.items():
        if entry.status != StemCenterStatus.OK:
            continue
        set_y = entry.center_axis == 'Y'
        live = live_by_layer[name]
        for ci, ni in selections_by_layer[name]:
            node = live[ci].data[ni]
            if set_y:
                node.y = entry.target_coord
            else:
                node.x = entry.target_coord
    return dict((name, entry.status) for name, entry in plan.items())


# ===================================================================
# 2. STROKE SEPARATE (V3) — MAT-based
# ===================================================================
def npa_stroke_separate(glyph, scope_layers, NodeActions, ContourActions,
                        sample_step=20.0, beta_min=1.5, overlap=0.0,
                        debug=False):
    """Stroke Separate (V3). Analyse the first scope layer once, then cut
    every scope layer node-exact, all or nothing.

    The first entry in `scope_layers` is the analysis (reference) layer.
    Selection on it (per-contour) drives which contours are cut; with no
    selection, all contours are. Cut endpoints are planned once on the
    reference (plan_cut_nodes) and inserted as nodes at the same (contour,
    segment, t) on every layer, so no distance snap can diverge between
    masters. Nothing is written unless every layer is compatible before the
    cut and gives the same structure after it.

    Returns dict: {'status': 'OK' | 'NO_CUTS' | 'INCOMPATIBLE' |
    'DIVERGED' | 'EMPTY', 'layer': name or None, 'message': str,
    'cuts': int, 'pieces': int}.
    """
    def _status(status, layer=None, message='', cuts=0, pieces=0):
        return {'status': status, 'layer': layer, 'message': message,
                'cuts': cuts, 'pieces': pieces}

    if not scope_layers:
        return _status('EMPTY', message='No layers in scope')

    analysis_name = scope_layers[0]
    tr_analysis = glyph.layer(analysis_name)
    if tr_analysis is None:
        return _status('EMPTY', analysis_name, 'Reference layer not found')

    analysis_core = _eject(tr_analysis)
    if analysis_core is None or not analysis_core.shapes:
        return _status('EMPTY', analysis_name, 'Reference layer has no paths')
    all_core_contours = analysis_core.shapes[0].contours
    if not all_core_contours:
        return _status('EMPTY', analysis_name, 'Reference layer has no paths')

    # Selection on analysis layer drives which contours are analysed.
    sel_cids = sorted(c_idx for c_idx, contour in enumerate(all_core_contours)
                      if any(n.selected and n.is_on for n in contour.data)) or None
    if sel_cids is not None:
        source_contours = [all_core_contours[i] for i in sel_cids]
    else:
        source_contours = list(all_core_contours)

    # Every layer must be compatible before anything is analysed.
    targets = []
    for layer_name in scope_layers:
        tr_layer = glyph.layer(layer_name)
        layer_core = _eject(tr_layer) if tr_layer is not None else None
        if layer_core is None or not layer_core.shapes:
            return _status('INCOMPATIBLE', layer_name, 'Layer has no paths')
        target_all = layer_core.shapes[0].contours
        try:
            check_contour_compatibility(all_core_contours, target_all)
        except ValueError as error:
            return _status('INCOMPATIBLE', layer_name, str(error))
        targets.append((layer_name, tr_layer, layer_core, target_all))

    sep = StrokeSep(beta_min=beta_min, sample_step=sample_step, debug=debug)
    result = sep.analyze(source_contours)
    plan = plan_cut_nodes(result.cuts, source_contours)
    if not plan:
        return _status('NO_CUTS', analysis_name, 'No cuts found')

    # Cut every layer off-host first; compare structure before writing.
    outputs, ref_signature = [], None
    for layer_name, tr_layer, layer_core, target_all in targets:
        if sel_cids is not None:
            target_contours = [target_all[i] for i in sel_cids]
        else:
            target_contours = list(target_all)
        try:
            separated = apply_cuts_exact(plan, target_contours, overlap=overlap,
                                         reference=source_contours)
        except ValueError as error:
            return _status('INCOMPATIBLE', layer_name, str(error))

        signature = contour_signature(separated)
        if ref_signature is None:
            ref_signature = signature
        elif signature != ref_signature:
            return _status('DIVERGED', layer_name,
                           'Cut result differs from the reference layer '
                           '({} vs {} pieces)'.format(len(separated), len(ref_signature)),
                           cuts=len(plan))
        outputs.append((tr_layer, layer_core, target_all, separated))

    for tr_layer, layer_core, target_all, separated in outputs:
        # Replace source contours with separated; keep untouched ones intact.
        if sel_cids is not None:
            sel_set = set(sel_cids)
            new_contours = [c for i, c in enumerate(target_all) if i not in sel_set]
            new_contours.extend(separated)
            layer_core.shapes[0].contours = new_contours
        else:
            layer_core.shapes[0].contours = separated
        _mount(tr_layer, layer_core)

    return _status('OK', analysis_name, cuts=len(plan), pieces=len(ref_signature))


# ===================================================================
# 3. MEDIAL AXIS EXTRACT
# ===================================================================
def npa_mat_extract(glyph, scope_layers, NodeActions, ContourActions,
                    sample_step=5.0, beta_min=1.5, quality='normal',
                    smooth=True, drop_corner_legs=True,
                    corner_leg_ratio=0.35, simplify_tolerance=None,
                    prune_short=None):
    """Medial Axis Extract. Active-layer-only by design — MAT is a
    geometric derivative of the outline; propagating across masters is
    meaningless. The skeleton is appended as a new shape on the active
    layer; the original outline is left untouched.

    The first entry in `scope_layers` is treated as the active layer.
    """
    if not scope_layers:
        return

    active_name = scope_layers[0]
    tr_layer = glyph.layer(active_name)
    if tr_layer is None:
        return

    layer_core = _eject(tr_layer)
    if layer_core is None or not layer_core.shapes:
        return
    all_contours = layer_core.shapes[0].contours
    if not all_contours:
        return

    # Selection drives which contours feed the extractor.
    sel_cids = set()
    for c_idx, contour in enumerate(all_contours):
        for node in contour.data:
            if node.selected and node.is_on:
                sel_cids.add(c_idx)
                break

    if sel_cids:
        source_contours = [all_contours[i] for i in sorted(sel_cids)
                           if i < len(all_contours)]
    else:
        source_contours = list(all_contours)

    if not source_contours:
        return

    skeleton = extract_medial_axis(
        source_contours,
        sample_step=sample_step,
        beta_min=beta_min,
        quality=quality,
        smooth=smooth,
        drop_corner_legs=drop_corner_legs,
        corner_leg_ratio=corner_leg_ratio,
        simplify_tolerance=simplify_tolerance,
        prune_short=prune_short,
    )

    if not skeleton:
        return

    layer_core.shapes.append(Shape(contours=skeleton))
    _mount(tr_layer, layer_core)
