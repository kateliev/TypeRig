# ===================================================================
# TypeRig / Core / Actions / Layer Panel Actions
# ===================================================================
# Layer dispatchers for the TypeRig Layer panel (FL Panel/Layer.py).
#
# Every public npa_* function receives (glyph, scope_layers, LayerActions)
# first. Unlike the node dispatchers, scope_layers here are the layers
# picked in the panel's own layer list (FL parity), and `source` is the
# active layer: pull = list -> active, push = active -> list.
#
# Host writes. Geometry (node coordinates, metrics, transforms) goes
# through the core object API, which host proxies write through. Shape,
# anchor, guide and lock writes need the host's own write surface: when
# a layer offers the proxy method (copy_shapes_from, swap_shapes,
# copy_guides_from, clear_guides, set_locked, append_contour, eject /
# mount) it is used, otherwise the pure-core LayerActions fallback runs.
#
# Module state: the outline clipboard and the interpolation axis.
# ===================================================================

from __future__ import absolute_import, print_function, division

import copy
from collections import OrderedDict

from typerig.core.objects.shape import Shape
from typerig.core.objects.layer import Layer
from typerig.core.objects.contour import Contour
from typerig.core.func.math import linInterp as lerp

# -- Module-level state ---------------------------------------------
_outline_bank = OrderedDict()	# layer_name -> [core Contour]
_lerp_axis = []					# [((x0, y0), (x1, y1)), ...] per node

# Copy options: which parts of a layer pull / push / swap / clean touch
DEFAULT_OPTIONS = {'outline': True, 'guides': False, 'anchors': False,
                   'lsb': False, 'adv': True, 'rsb': False}
_METRICS = (('lsb', 'LSB'), ('adv', 'ADV'), ('rsb', 'RSB'))


# ===================================================================
# Internal helpers
# ===================================================================
def _layers(glyph, names):
    """Yield (name, layer) for each name that exists on the glyph."""
    for name in names:
        lyr = glyph.layer(name)
        if lyr is not None:
            yield name, lyr


def _opts(options):
    out = dict(DEFAULT_OPTIONS)
    out.update(options or {})
    return out


def _detach(obj):
    """Pure core copy of a proxy (eject) or core object (deep copy)."""
    return obj.eject() if hasattr(obj, 'eject') else copy.deepcopy(obj)


def _copy_shapes(LayerActions, src, dst, clean):
    if hasattr(dst, 'copy_shapes_from'):
        return dst.copy_shapes_from(src, clean)
    return LayerActions.layer_copy_shapes(src, dst, clean)


def _copy_guides(src, dst, clean):
    if hasattr(dst, 'copy_guides_from'):
        return dst.copy_guides_from(src, clean)
    src_guides = list(getattr(src, 'guidelines', []) or [])
    kept = [] if clean else list(getattr(dst, 'guidelines', []) or [])
    dst.guidelines = kept + [copy.deepcopy(g) for g in src_guides]
    return bool(src_guides)


def _copy_metrics(LayerActions, src, dst, opts):
    done = False
    for key, mode in _METRICS:
        if opts[key]:
            try:
                done = LayerActions.layer_copy_metrics(src, dst, mode) or done
            except AssertionError:	# empty layer: no bounds for LSB / RSB
                pass
    return done


def _copy_layer(LayerActions, src, dst, opts):
    """Copy the optioned parts of src into dst. Returns True if any part ran."""
    done = False
    if opts['outline']:
        done = _copy_shapes(LayerActions, src, dst, False) or done
    if opts['guides']:
        done = _copy_guides(src, dst, False) or done
    if opts['anchors']:
        done = LayerActions.layer_copy_anchors(src, dst) or done
    return _copy_metrics(LayerActions, src, dst, opts) or done


def _append_contour(layer, contour):
    if hasattr(layer, 'append_contour'):
        layer.append_contour(contour)
        return
    outlines = [s for s in layer.shapes if not getattr(s, 'is_component', False)]
    if outlines:
        outlines[0].append(contour)
    else:
        layer.append(Shape([contour]))


def _selected_node_indices(layer):
    """Indices into layer.nodes of the selected nodes."""
    return [i for i, n in enumerate(layer.nodes) if n.selected]


def _selected_contour_map(layer):
    """{contour index: [selected node indices]}, [] meaning the whole contour."""
    out = OrderedDict()
    for ci, contour in enumerate(layer.contours):
        nodes = contour.data
        idx = [i for i, n in enumerate(nodes) if n.selected]
        if idx:
            out[ci] = [] if len(idx) == len(nodes) else idx
    return out


# ===================================================================
# 1. CONTENT: pull / push / swap / clean / lock
# ===================================================================
def npa_layer_pull(glyph, scope_layers, LayerActions, source, options=None):
    """Pull the optioned parts of the first picked layer into source (active)."""
    opts = _opts(options)
    dst = glyph.layer(source)
    for name, src in _layers(glyph, scope_layers):
        if name == source or dst is None:
            continue
        return _copy_layer(LayerActions, src, dst, opts)
    return False


def npa_layer_push(glyph, scope_layers, LayerActions, source, options=None):
    """Push the optioned parts of source (active) into every picked layer.

    Returns the list of layer names written."""
    opts = _opts(options)
    src = glyph.layer(source)
    done = []
    if src is None:
        return done
    for name, dst in _layers(glyph, scope_layers):
        if name != source and _copy_layer(LayerActions, src, dst, opts):
            done.append(name)
    return done


def npa_layer_swap(glyph, scope_layers, LayerActions, source, options=None):
    """Swap outline and/or metrics between source and the first picked layer."""
    opts = _opts(options)
    a = glyph.layer(source)
    for name, b in _layers(glyph, scope_layers):
        if name == source or a is None:
            continue
        if opts['outline']:
            if hasattr(a, 'swap_shapes'):
                a.swap_shapes(b)
            else:
                LayerActions.layer_swap_shapes(a, b)
        for key, mode in _METRICS:
            if opts[key]:
                try:
                    LayerActions.layer_swap_metrics(a, b, mode)
                except AssertionError:
                    pass
        return True
    return False


def npa_layer_clean(glyph, scope_layers, LayerActions, options=None):
    """Remove outline / guides / anchors (per options) from the picked layers."""
    opts = _opts(options)
    done = []
    for name, lyr in _layers(glyph, scope_layers):
        if opts['outline']:
            if hasattr(lyr, 'clear_shapes'):
                lyr.clear_shapes()
            else:
                LayerActions.layer_clean_shapes(lyr)
        if opts['guides']:
            if hasattr(lyr, 'clear_guides'):
                lyr.clear_guides()
            else:
                lyr.guidelines = []
        if opts['anchors']:
            lyr.anchors = []
        done.append(name)
    return done


def npa_layer_lock(glyph, scope_layers, LayerActions, locked=True):
    """Lock / unlock the shapes of the picked layers (hosts with shape locks)."""
    done = []
    for name, lyr in _layers(glyph, scope_layers):
        if hasattr(lyr, 'set_locked'):
            lyr.set_locked(locked)
            done.append(name)
    return done


# ===================================================================
# 2. NODES: pull / push selection, outline clipboard
# ===================================================================
def npa_layer_ditto(glyph, scope_layers, LayerActions, source, push=False):
    """Copy the coordinates of the nodes selected on source between layers.

    pull (push=False): picked layer -> source; push: source -> every picked
    layer. Layers whose node count differs from source are skipped.
    Returns (done_names, skipped_names)."""
    src = glyph.layer(source)
    done, skipped = [], []
    if src is None:
        return done, skipped
    idx = _selected_node_indices(src)
    if not idx:
        return done, skipped
    for name, other in _layers(glyph, scope_layers):
        if name == source:
            continue
        a, b = (src, other) if push else (other, src)
        if LayerActions.layer_pull_coordinates(a, b, idx):
            done.append(name)
        else:
            skipped.append(name)
    return done, skipped


def npa_layer_copy_outline(glyph, scope_layers, LayerActions, source):
    """Copy the contours (or partial node runs) selected on source, taken
    from every picked layer, into the outline clipboard. Returns the names
    copied."""
    _outline_bank.clear()
    src = glyph.layer(source)
    if src is None:
        return []
    selection = _selected_contour_map(src)
    if not selection:
        return []
    for name, lyr in _layers(glyph, scope_layers):
        contours = lyr.contours
        out = []
        for ci, idx in selection.items():
            if ci >= len(contours):
                continue
            core = _detach(contours[ci])
            if not idx:
                out.append(core)
            elif max(idx) < len(core.data):
                out.append(Contour([copy.deepcopy(core.data[i]) for i in idx], closed=False))
        if out:
            _outline_bank[name] = out
    return list(_outline_bank.keys())


def npa_layer_paste_outline(glyph, scope_layers, LayerActions, by_name=True):
    """Paste the outline clipboard as new contours.

    by_name: each clipboard entry goes to the layer of the same name.
    Otherwise entries go to the picked layers in order (counts must match).
    Returns the names pasted into."""
    if not _outline_bank:
        return []
    if by_name:
        pairs = [(name, contours) for name, contours in _outline_bank.items()]
    else:
        if len(_outline_bank) != len(scope_layers):
            return []
        pairs = list(zip(scope_layers, _outline_bank.values()))
    done = []
    for name, contours in pairs:
        lyr = glyph.layer(name)
        if lyr is None:
            continue
        for contour in contours:
            _append_contour(lyr, copy.deepcopy(contour))
        done.append(name)
    return done


def npa_layer_outline_bank():
    """Names held in the outline clipboard (for status display)."""
    return list(_outline_bank.keys())


# ===================================================================
# 3. TRANSFORM
# ===================================================================
def npa_layer_transform(glyph, scope_layers, LayerActions, **params):
    """Transform every picked layer around its own bounds (see
    LayerActions.layer_transform for params). Returns the names done."""
    done = []
    for name, lyr in _layers(glyph, scope_layers):
        try:
            if LayerActions.layer_transform(lyr, **params):
                done.append(name)
        except AssertionError:	# empty layer
            pass
    return done


# ===================================================================
# 4. INTERPOLATION AXIS
# ===================================================================
def npa_layer_axis_set(glyph, scope_layers, LayerActions):
    """Capture the node positions of the first two picked layers as the
    axis masters. Returns True if the axis is set."""
    del _lerp_axis[:]
    picked = list(_layers(glyph, scope_layers))
    if len(picked) < 2:
        return False
    a, b = picked[0][1].nodes, picked[1][1].nodes
    if not a or len(a) != len(b):
        return False
    _lerp_axis.extend(zip([n.tuple for n in a], [n.tuple for n in b]))
    return True


def npa_layer_axis_reset():
    del _lerp_axis[:]


def npa_layer_axis_is_set():
    return bool(_lerp_axis)


def npa_layer_axis_apply(glyph, scope_layers, LayerActions, target, tx, ty, swap=False):
    """Write the axis interpolated at (tx, ty) into the target layer.
    Returns False if no axis or the target is not compatible."""
    lyr = glyph.layer(target)
    if not _lerp_axis or lyr is None:
        return False
    nodes = lyr.nodes
    if len(nodes) != len(_lerp_axis):
        return False
    for node, (t0, t1) in zip(nodes, _lerp_axis):
        if swap:
            t0, t1 = t1, t0
        node.x = lerp(t0[0], t1[0], tx)
        node.y = lerp(t0[1], t1[1], ty)
    return True


# ===================================================================
# 5. MATCHMAKER
# ===================================================================
def _on_count(contour):
    return sum(1 for n in contour.nodes if n.is_on)


def _detach_layer(lyr):
    return lyr.eject() if hasattr(lyr, 'eject') else lyr.clone()


def _host_start_last(lyr):
    """True when the host keeps a closed contour's start node LAST (GS3:
    nodes[0] is the node after the start). Core matchmaker works start
    first (core / FL), so its output written as is lands the start one
    node early on such hosts."""
    for c in getattr(lyr, 'contours', []):
        n = len(c.nodes)
        if c.closed and n > 1:
            return getattr(c, 'start_index', 0) == n - 1
    return False


def _rotate_start(contours, to_first):
    """Move closed contours' start node first (to_first) or back last."""
    for c in contours:
        if c.closed and len(c.data) > 1:
            c.data = c.data[-1:] + c.data[:-1] if to_first else c.data[1:] + c.data[:1]


def _attach_layer(lyr, core_layer):
    if hasattr(lyr, 'mount'):
        lyr.mount(core_layer)
    else:
        lyr.data = core_layer.data


def _rebuild_layer(core_layer, new_contours):
    """core_layer with its outline replaced by new_contours; components kept."""
    components = [s for s in core_layer.shapes if getattr(s, 'is_component', False)]
    return Layer([Shape(list(new_contours))] + components,
                 name=core_layer.name,
                 width=core_layer.advance_width,
                 height=core_layer.advance_height,
                 anchors=core_layer.anchors)


def npa_layer_matchmaker(glyph, scope_layers, LayerActions, source,
                         align_start='auto', pair_mode='auto',
                         contour_mode=False, dry_run=False, upm=1000.):
    """Make source (active) and the first picked layer compatible
    (core.algo.matchmaker). contour_mode matches only the contours with a
    selection on source. dry_run reports without writing.

    The picked layer is the reference (matchmaker A): it keeps its contour
    order, starts and directions; the active layer is the one reordered,
    reversed or rotated. Either side may still get nodes inserted.

    Returns (ok, report_lines)."""
    from typerig.core.algo.matchmaker import apply_match, apply_match_glyph

    target = next((n for n in scope_layers if n != source), None)
    tr_src, tr_tgt = glyph.layer(source), glyph.layer(target) if target else None
    if tr_src is None or tr_tgt is None:
        return False, ['Matchmaker: pick a target layer other than the active one.']

    core_src, core_tgt = _detach_layer(tr_src), _detach_layer(tr_tgt)
    ca, cb = list(core_src.contours), list(core_tgt.contours)
    last_src, last_tgt = _host_start_last(tr_src), _host_start_last(tr_tgt)
    if last_src:
        _rotate_start(ca, True)
    if last_tgt:
        _rotate_start(cb, True)
    em = float(upm or 1000.)
    k_s, k_b = 1. / (em * em), 1.
    head = 'Matchmaker: %s <-> %s' % (source, target)

    if contour_mode:
        sel_ids = [ci for ci, c in enumerate(tr_src.contours) if any(n.selected for n in c.data)]
        if not sel_ids:
            return False, [head, 'Contour mode: no contour selected on the active layer.']
        bad = [i for i in sel_ids if i >= len(cb)]
        if bad:
            return False, [head, 'Contour mode: contours %s missing on target.' % bad]
        if any(_on_count(ca[i]) < 3 or _on_count(cb[i]) < 3 for i in sel_ids):
            return False, [head, 'Contour mode: degenerate contours (<3 on-curves).']
        new_a, new_b, total = list(ca), list(cb), 0.
        lines = [head + ' [contours %s, start %s]' % (sel_ids, align_start)]
        for i in sel_ids:
            nb, na, cost, meta = apply_match(cb[i], ca[i], k_s=k_s, k_b=k_b, align_start=align_start)
            new_a[i], new_b[i] = na, nb
            total += cost
            lines.append('  contour %d: cost=%.4f inserts=%d/%d promotions=%d/%d' % (
                i, cost, meta['n_insert_b'], meta['n_insert_a'],
                meta['n_promoted_b'], meta['n_promoted_a']))
        lines.append('  total cost = %.4f' % total)
    else:
        if len(ca) != len(cb):
            return False, [head, 'Contour count mismatch: %d / %d.' % (len(ca), len(cb))]
        if any(_on_count(c) < 3 for c in ca + cb):
            return False, [head, 'Degenerate contours (<3 on-curves).']
        new_b, new_a, total, meta = apply_match_glyph(
            cb, ca, k_s=k_s, k_b=k_b, align_start=align_start, pair_mode=pair_mode)
        lines = [head + ' [start %s, order %s]' % (align_start, pair_mode),
                 '  cost=%.4f inserts=%d/%d promotions=%d/%d pairs=%s' % (
                     total, meta['total_insert_b'], meta['total_insert_a'],
                     meta['total_promoted_b'], meta['total_promoted_a'],
                     [(j, i) for i, j in meta['pairs']])]

    if dry_run:
        lines.append('  (dry run: nothing written)')
        return True, lines

    if last_src:
        _rotate_start(new_a, False)
    if last_tgt:
        _rotate_start(new_b, False)
    _attach_layer(tr_src, _rebuild_layer(core_src, new_a))
    _attach_layer(tr_tgt, _rebuild_layer(core_tgt, new_b))
    return True, lines
