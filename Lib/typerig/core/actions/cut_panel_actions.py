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


def _selected_triples(layer):
    """Return list of (sid, cid, nid) triples for selected on-curve nodes
    on `layer`. Mirrors eGlyph.selectedAtShapes() output ordering."""
    triples = []
    for sid, shape in enumerate(layer.shapes):
        for cid, contour in enumerate(shape.contours):
            for nid, node in enumerate(contour.data):
                if node.selected and node.is_on:
                    triples.append((sid, cid, nid))
    return triples


def _selected_contours_per_shape(layer):
    """Return dict {sid: set(cid)} for shapes/contours that have any
    selected on-curve node."""
    sel = {}
    for sid, shape in enumerate(layer.shapes):
        for cid, contour in enumerate(shape.contours):
            for node in contour.data:
                if node.selected and node.is_on:
                    sel.setdefault(sid, set()).add(cid)
                    break
    return sel


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
    the two contours into one closed contour at the cut points."""
    for lyr in _iter_scope(glyph, scope_layers):
        triples = _selected_triples(lyr)
        if len(triples) < 2:
            continue

        # Group by shape index — orchestrator processes one shape at a time.
        by_shape = {}
        for sid, cid, nid in triples:
            by_shape.setdefault(sid, []).append((sid, cid, nid))

        for sid, sh_triples in by_shape.items():
            if sid >= len(lyr.shapes):
                continue
            ContourActions.contour_slice(lyr.shapes[sid], sh_triples,
                                         expanded=expanded)


def npa_contour_auto_align(glyph, scope_layers, NodeActions, ContourActions):
    """Auto overlap align: classify and align two neighbor-pairs at a cut
    junction. Operates on selection of >=4 on-curve nodes per layer."""
    for lyr in _iter_scope(glyph, scope_layers):
        # Group selected on-curve nodes by their parent contour, then pair
        # within each contour.
        by_contour = {}
        for s in lyr.shapes:
            for c in s.contours:
                sel = [n for n in c.data if n.selected and n.is_on]
                if sel:
                    by_contour[id(c)] = (c, sel)

        all_nodes = [n for _, (_, sel) in by_contour.items() for n in sel]
        if len(all_nodes) < 4:
            continue

        # Pair within each contour first; if neither contour has enough
        # selected nodes for a full pair-of-pairs, fall back to a flat pass.
        pairs = []
        for cid_key, (contour, sel) in by_contour.items():
            if len(sel) >= 2:
                p_first, p_second = ContourActions.node_neighbor_pairs(
                    contour, sel)
                if p_first:
                    pairs.append(p_first)
                if p_second:
                    pairs.append(p_second)

        # If contour-grouped pairing didn't yield two pairs, try flat pairing
        # across the layer's selection (fallback for legacy single-contour
        # selections that span an apparent junction).
        if len(pairs) < 2 and len(all_nodes) >= 4:
            # Use the first contour's traversal as the reference for pairing
            # — the popup behaviour: pair across 4 selected nodes.
            ref_contour = next(iter(by_contour.values()))[0]
            p_first, p_second = ContourActions.node_neighbor_pairs(
                ref_contour, all_nodes)
            pairs = [p for p in (p_first, p_second) if p]

        for pair in pairs:
            mode = ContourActions.junction_align_mode(pair)
            ContourActions.contour_pair_align(pair, mode)


def npa_contour_slice_align(glyph, scope_layers, NodeActions, ContourActions,
                            expanded=False):
    """Slice + auto-align in one step. Mirrors popup do_cut_align_auto.

    Selection is captured BEFORE the slice (the slice mutates contour
    membership; node references remain valid because we duplicate cut
    nodes rather than discard them)."""
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

    analysis_core = tr_analysis.eject()
    if not analysis_core.shapes:
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

        layer_core = tr_layer.eject()
        if not layer_core.shapes:
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

        tr_layer.mount(layer_core)


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

    layer_core = tr_layer.eject()
    if not layer_core.shapes:
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
    tr_layer.mount(layer_core)
