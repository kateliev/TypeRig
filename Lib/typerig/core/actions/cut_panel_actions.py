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
    apply_cuts_to_layer,
    check_contour_compatibility,
)
from typerig.core.algo.mat_extract import extract_medial_axis


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
        # Read selection from the live layer (proxy nodes carry .selected).
        triples = _selected_triples(lyr)
        if len(triples) < 2:
            continue

        core_layer = _eject(lyr)
        if core_layer is None:
            continue

        # Re-read selection from the ejected pure-core layer to ensure
        # selection state survived the eject (it does for both gs3 and
        # pure-core paths).
        core_triples = _selected_triples(core_layer)
        if len(core_triples) < 2:
            # Fall back to the proxy-side triples (positions are identical).
            core_triples = triples

        by_shape = {}
        for sid, cid, nid in core_triples:
            by_shape.setdefault(sid, []).append((sid, cid, nid))

        mutated = False
        for sid, sh_triples in by_shape.items():
            if sid >= len(core_layer.shapes):
                continue
            if ContourActions.contour_slice(core_layer.shapes[sid],
                                            sh_triples, expanded=expanded):
                mutated = True

        if mutated:
            _mount(lyr, core_layer)


def npa_contour_auto_align(glyph, scope_layers, NodeActions, ContourActions):
    """Auto overlap align: classify and align two neighbor-pairs at a cut
    junction. Operates on selection of >=4 on-curve nodes per layer.

    Uses eject/mount so coordinate writes always land on the host. The
    pair classification reads contour traversal from the ejected core
    layer, so node neighbours are derived consistently regardless of
    host proxy quirks.
    """
    for lyr in _iter_scope(glyph, scope_layers):
        core_layer = _eject(lyr)
        if core_layer is None:
            continue

        by_contour = {}
        for s in core_layer.shapes:
            for c in s.contours:
                sel = [n for n in c.data if n.selected and n.is_on]
                if sel:
                    by_contour[id(c)] = (c, sel)

        all_nodes = [n for _, (_, sel) in by_contour.items() for n in sel]
        if len(all_nodes) < 4:
            continue

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
            continue

        for pair in pairs:
            mode = ContourActions.junction_align_mode(pair)
            ContourActions.contour_pair_align(pair, mode)

        _mount(lyr, core_layer)


def npa_contour_slice_align(glyph, scope_layers, NodeActions, ContourActions,
                            expanded=False):
    """Slice + auto-align in one step. Mirrors popup do_cut_align_auto.

    Two separate eject/mount round-trips: the slice changes contour
    membership and re-reads selection on the live layer between
    operations, matching the FL popup's two-step flow.
    """
    npa_contour_slice(glyph, scope_layers, NodeActions, ContourActions,
                      expanded=expanded)
    npa_contour_auto_align(glyph, scope_layers, NodeActions, ContourActions)


# ===================================================================
# 2. STROKE SEPARATE (V3) — MAT-based
# ===================================================================
def npa_stroke_separate(glyph, scope_layers, NodeActions, ContourActions,
                        sample_step=20.0, beta_min=1.5, overlap=0.0,
                        debug=False):
    """Stroke Separate (V3). Eject the analysis layer to pure core, run
    StrokeSep.analyze, then for each scope layer eject → apply cuts → mount.

    The first entry in `scope_layers` is the analysis (reference) layer;
    cuts are derived from its geometry and propagated to all other layers
    in scope. Selection on the analysis layer (per-contour) drives which
    contours are analysed; if no selection, all contours are processed.
    """
    if not scope_layers:
        return

    analysis_name = scope_layers[0]
    tr_analysis = glyph.layer(analysis_name)
    if tr_analysis is None:
        return

    analysis_core = _eject(tr_analysis)
    if analysis_core is None or not analysis_core.shapes:
        return
    all_core_contours = analysis_core.shapes[0].contours
    if not all_core_contours:
        return

    # Selection on analysis layer drives which contours are analysed.
    sel_cids_analysis = set()
    for c_idx, contour in enumerate(all_core_contours):
        for node in contour.data:
            if node.selected and node.is_on:
                sel_cids_analysis.add(c_idx)
                break

    if sel_cids_analysis:
        sel_cids = sorted(sel_cids_analysis)
        source_contours = [all_core_contours[i] for i in sel_cids
                           if i < len(all_core_contours)]
    else:
        sel_cids = None
        source_contours = list(all_core_contours)

    if not source_contours:
        return

    sep = StrokeSep(beta_min=beta_min, sample_step=sample_step, debug=debug)
    result = sep.analyze(source_contours)

    if not result.cuts:
        return

    for layer_name in scope_layers:
        tr_layer = glyph.layer(layer_name)
        if tr_layer is None:
            continue

        layer_core = _eject(tr_layer)
        if layer_core is None or not layer_core.shapes:
            continue
        target_all = layer_core.shapes[0].contours
        if not target_all:
            continue

        if sel_cids is not None:
            target_contours = [target_all[i] for i in sel_cids
                               if i < len(target_all)]
        else:
            target_contours = list(target_all)

        if layer_name == analysis_name:
            separated = sep.execute(result, source_contours, overlap=overlap)
        else:
            try:
                check_contour_compatibility(source_contours, target_contours)
            except ValueError:
                continue
            separated = apply_cuts_to_layer(
                result, source_contours, target_contours, overlap=overlap)

        # Replace source contours with separated; keep untouched ones intact.
        if sel_cids is not None:
            sel_set = set(sel_cids)
            new_contours = [c for i, c in enumerate(target_all)
                            if i not in sel_set]
            new_contours.extend(separated)
            layer_core.shapes[0].contours = new_contours
        else:
            layer_core.shapes[0].contours = separated

        _mount(tr_layer, layer_core)


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
