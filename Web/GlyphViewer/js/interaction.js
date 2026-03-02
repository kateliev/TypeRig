// ===================================================================
// TypeRig Glyph Viewer — Interaction Helpers
// ===================================================================
'use strict';

// -- Selection (multi-node) -----------------------------------------
TRV.clearSelection = function() {
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// Select a single node (replaces selection unless shift is held)
TRV.selectNode = function(nodeId, additive) {
	const sel = TRV.state.selectedNodeIds;

	if (!nodeId) {
		if (!additive) sel.clear();
	} else if (additive) {
		// Toggle: add if missing, remove if present
		if (sel.has(nodeId)) {
			sel.delete(nodeId);
		} else {
			sel.add(nodeId);
		}
	} else {
		sel.clear();
		sel.add(nodeId);
	}

	// Highlight first selected in XML panel (canvas → XML, one way)
	if (sel.size > 0) {
		const first = sel.values().next().value;
		TRV.highlightXmlNode(first);
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

// Select multiple nodes (from rect/lasso), replacing or adding
TRV.selectNodes = function(nodeIds, additive) {
	const sel = TRV.state.selectedNodeIds;

	if (!additive) sel.clear();
	for (const id of nodeIds) {
		sel.add(id);
	}

	if (sel.size > 0) {
		const first = sel.values().next().value;
		TRV.highlightXmlNode(first);
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

TRV.updateStatusSelected = function() {
	const sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) {
		TRV.dom.statusSelected.textContent = '\u2013';
		return;
	}

	if (sel.size === 1) {
		const nodeId = sel.values().next().value;
		const ref = TRV.findNodeById(nodeId);
		if (ref) {
			TRV.dom.statusSelected.textContent =
				nodeId + ' (' + ref.node.x + ', ' + ref.node.y + ') ' + ref.node.type;
		}
	} else {
		TRV.dom.statusSelected.textContent = sel.size + ' nodes';
	}
};

// -- Contour walk (PageUp / PageDown) -------------------------------
// Walk selection forward/backward along the contour. If nothing is
// selected, selects the first on-curve node of the first contour.
TRV.walkContour = function(direction) {
	const layer = TRV.getActiveLayer();
	if (!layer) return;

	const sel = TRV.state.selectedNodeIds;
	const allNodes = TRV.getAllNodes(layer);
	if (allNodes.length === 0) return;

	// Nothing selected — pick first on-curve of first contour
	if (sel.size === 0) {
		for (var i = 0; i < allNodes.length; i++) {
			if (allNodes[i].type === 'on') {
				TRV.selectNode(allNodes[i].id, false);
				return;
			}
		}
		TRV.selectNode(allNodes[0].id, false);
		return;
	}

	// Find the contour of the first selected node
	const firstId = sel.values().next().value;
	const m = firstId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return;
	const ci = parseInt(m[1]);
	const ni = parseInt(m[2]);

	// Collect nodes belonging to this contour
	const contourNodes = allNodes.filter(function(n) { return n.contourIdx === ci; });
	if (contourNodes.length === 0) return;

	// Find current position in contour node list
	var curIdx = -1;
	for (var j = 0; j < contourNodes.length; j++) {
		if (contourNodes[j].nodeIdx === ni) { curIdx = j; break; }
	}
	if (curIdx < 0) curIdx = 0;

	// Step forward or backward, wrapping around
	var newIdx = (curIdx + direction + contourNodes.length) % contourNodes.length;
	TRV.selectNode(contourNodes[newIdx].id, false);
};

// Get contour index (ci) from a node ID like 'c2_n5'
TRV.getContourIndexForNode = function(nodeId) {
	var m = nodeId.match(/^c(\d+)/);
	return m ? parseInt(m[1]) : -1;
};

// -- Insert node on contour ------------------------------------------
// Segment iteration: walks contour nodes and yields segments.
// Each segment is { type, startIdx, endIdx, nodes[] } where nodes
// are the control points (2 for line, 4 for cubic).
TRV.getContourSegments = function(contour) {
	var nodes = contour.nodes;
	var n = nodes.length;
	var segments = [];
	var i = 0;

	while (i < n) {
		if (nodes[i].type !== 'on') { i++; continue; }

		var next1 = (i + 1) % n;
		if (nodes[next1].type === 'on') {
			// Line segment: on → on
			segments.push({
				type: 'line',
				startIdx: i,
				endIdx: next1,
				pts: [
					{ x: nodes[i].x, y: nodes[i].y },
					{ x: nodes[next1].x, y: nodes[next1].y }
				]
			});
			i++;
			continue;
		}

		// Cubic segment: on → off → off → on
		var next2 = (i + 2) % n;
		var next3 = (i + 3) % n;
		if (nodes[next1].type === 'curve' && nodes[next2].type === 'curve' && nodes[next3].type === 'on') {
			segments.push({
				type: 'cubic',
				startIdx: i,
				endIdx: next3,
				offIdx1: next1,
				offIdx2: next2,
				pts: [
					{ x: nodes[i].x, y: nodes[i].y },
					{ x: nodes[next1].x, y: nodes[next1].y },
					{ x: nodes[next2].x, y: nodes[next2].y },
					{ x: nodes[next3].x, y: nodes[next3].y }
				]
			});
			i += 3;
			continue;
		}

		i++;
	}
	return segments;
};

// Evaluate a cubic bezier at parameter t (de Casteljau)
TRV._evalCubic = function(pts, t) {
	var u = 1 - t;
	var uu = u * u, tt = t * t;
	var uuu = uu * u, ttt = tt * t;
	return {
		x: uuu * pts[0].x + 3 * uu * t * pts[1].x + 3 * u * tt * pts[2].x + ttt * pts[3].x,
		y: uuu * pts[0].y + 3 * uu * t * pts[1].y + 3 * u * tt * pts[2].y + ttt * pts[3].y
	};
};

// Evaluate a line at parameter t
TRV._evalLine = function(pts, t) {
	return {
		x: pts[0].x + t * (pts[1].x - pts[0].x),
		y: pts[0].y + t * (pts[1].y - pts[0].y)
	};
};

// Find nearest point on a segment, returns { t, dist, x, y }
TRV._nearestOnSegment = function(seg, gx, gy) {
	var evalFn = seg.type === 'cubic' ? TRV._evalCubic : TRV._evalLine;
	var pts = seg.pts;
	var bestT = 0, bestDist = Infinity;

	// Coarse search: sample at 50 points
	var steps = 50;
	for (var i = 0; i <= steps; i++) {
		var t = i / steps;
		var p = evalFn(pts, t);
		var dx = p.x - gx, dy = p.y - gy;
		var d = dx * dx + dy * dy;
		if (d < bestDist) { bestDist = d; bestT = t; }
	}

	// Refine with bisection
	var lo = Math.max(0, bestT - 1 / steps);
	var hi = Math.min(1, bestT + 1 / steps);
	for (var iter = 0; iter < 20; iter++) {
		var mid1 = lo + (hi - lo) / 3;
		var mid2 = hi - (hi - lo) / 3;
		var p1 = evalFn(pts, mid1);
		var p2 = evalFn(pts, mid2);
		var d1 = (p1.x - gx) * (p1.x - gx) + (p1.y - gy) * (p1.y - gy);
		var d2 = (p2.x - gx) * (p2.x - gx) + (p2.y - gy) * (p2.y - gy);
		if (d1 < d2) hi = mid2; else lo = mid1;
	}

	var t = (lo + hi) / 2;
	var pt = evalFn(pts, t);
	var dx = pt.x - gx, dy = pt.y - gy;
	return { t: t, dist: Math.sqrt(dx * dx + dy * dy), x: pt.x, y: pt.y };
};

// Hit-test all segments in active layer, return best match or null.
// Returns { ci, segIdx, seg, t, x, y, dist }
TRV.hitTestSegment = function(sx, sy) {
	var layer = TRV.getActiveLayer();
	if (!layer) return null;

	var gp = TRV.screenToGlyph(sx, sy);
	var hitRadius = 8 / TRV.state.zoom; // 8 screen pixels in glyph space
	var best = null;
	var ci = 0;

	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var segs = TRV.getContourSegments(shape.contours[ki]);
			for (var gi = 0; gi < segs.length; gi++) {
				var hit = TRV._nearestOnSegment(segs[gi], gp.x, gp.y);
				if (hit.dist < hitRadius && (!best || hit.dist < best.dist)) {
					best = {
						ci: ci, segIdx: gi, seg: segs[gi],
						t: hit.t, x: hit.x, y: hit.y, dist: hit.dist,
						contour: shape.contours[ki]
					};
				}
			}
			ci++;
		}
	}
	return best;
};

// De Casteljau split: split cubic at t, returns { left, right }
// Each is an array of 4 points: [on, off, off, on]
TRV._splitCubic = function(pts, t) {
	var p0 = pts[0], p1 = pts[1], p2 = pts[2], p3 = pts[3];
	var u = 1 - t;

	// Level 1
	var a = { x: u * p0.x + t * p1.x, y: u * p0.y + t * p1.y };
	var b = { x: u * p1.x + t * p2.x, y: u * p1.y + t * p2.y };
	var c = { x: u * p2.x + t * p3.x, y: u * p2.y + t * p3.y };

	// Level 2
	var d = { x: u * a.x + t * b.x, y: u * a.y + t * b.y };
	var e = { x: u * b.x + t * c.x, y: u * b.y + t * c.y };

	// Level 3 — point on curve
	var m = { x: u * d.x + t * e.x, y: u * d.y + t * e.y };

	return {
		left:  [p0, a, d, m],
		right: [m, e, c, p3]
	};
};

// Insert a node on the segment identified by hitTestSegment result.
// Modifies the contour's node array in place.
TRV.insertNodeOnSegment = function(hit) {
	if (!hit || !hit.contour) return;

	var nodes = hit.contour.nodes;
	var seg = hit.seg;
	var round = function(v) { return Math.round(v * 10) / 10; };

	if (seg.type === 'line') {
		// Insert new on-curve at the interpolated position
		var newNode = {
			type: 'on', smooth: false,
			x: round(hit.x), y: round(hit.y)
		};
		// Insert after startIdx
		var insertAt = seg.startIdx + 1;
		// Handle wraparound: if endIdx < startIdx, insert at end
		if (seg.endIdx < seg.startIdx) insertAt = nodes.length;
		nodes.splice(insertAt, 0, newNode);
	} else if (seg.type === 'cubic') {
		var split = TRV._splitCubic(seg.pts, hit.t);
		var L = split.left;   // [p0, a, d, m]
		var R = split.right;  // [m, e, c, p3]

		// New nodes to replace the segment interior:
		// Original: [on(start), off1, off2, on(end)]
		// New:      [on(start), offL1, offL2, on(new), offR1, offR2, on(end)]
		// We replace off1, off2 with offL1, offL2, on(new), offR1, offR2

		var newOff1  = { type: 'curve', x: round(L[1].x), y: round(L[1].y) };
		var newOff2  = { type: 'curve', x: round(L[2].x), y: round(L[2].y) };
		var newOn    = { type: 'on', smooth: true, x: round(L[3].x), y: round(L[3].y) };
		var newOff3  = { type: 'curve', x: round(R[1].x), y: round(R[1].y) };
		var newOff4  = { type: 'curve', x: round(R[2].x), y: round(R[2].y) };

		// Find the actual positions of offIdx1 and offIdx2
		// They may wrap around, so we need to handle that carefully
		var idx1 = seg.offIdx1;
		var idx2 = seg.offIdx2;

		// Replace the two off-curves with the 5 new nodes
		if (idx2 === idx1 + 1) {
			// Normal case: consecutive indices
			nodes.splice(idx1, 2, newOff1, newOff2, newOn, newOff3, newOff4);
		} else {
			// Wraparound case: off1 is near end, off2 wraps to start
			// Remove from idx1 to end, then from 0 to idx2+1
			// Insert the new nodes at idx1
			nodes.splice(idx1, nodes.length - idx1, newOff1, newOff2, newOn, newOff3, newOff4);
			nodes.splice(0, idx2 + 1);
		}
	}

	// Rebuild IDs and redraw
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Retract handles -------------------------------------------------
// If on-curve selected: retract both adjacent handles to on-curve pos.
// If handle selected: retract only that handle.
TRV.retractHandles = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) return;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!sel.has(id)) continue;

				if (nodes[ni].type === 'on') {
					// On-curve: retract adjacent handles
					var prevIdx = (ni - 1 + n) % n;
					var nextIdx = (ni + 1) % n;
					if (nodes[prevIdx].type !== 'on') {
						nodes[prevIdx].x = nodes[ni].x;
						nodes[prevIdx].y = nodes[ni].y;
					}
					if (nodes[nextIdx].type !== 'on') {
						nodes[nextIdx].x = nodes[ni].x;
						nodes[nextIdx].y = nodes[ni].y;
					}
				} else {
					// Handle: find parent on-curve, retract to it
					var prevIdx = (ni - 1 + n) % n;
					var nextIdx = (ni + 1) % n;
					var parentIdx = -1;
					if (nodes[prevIdx].type === 'on') parentIdx = prevIdx;
					else if (nodes[nextIdx].type === 'on') parentIdx = nextIdx;
					if (parentIdx >= 0) {
						nodes[ni].x = nodes[parentIdx].x;
						nodes[ni].y = nodes[parentIdx].y;
					}
				}
			}
			ci++;
		}
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Constrained smooth movement -------------------------------------
// Compute unit tangent vectors for smooth on-curve nodes at drag start.
// Tangent = direction through the two adjacent handles (from their
// start positions). Returns Map<nodeId, {tx, ty}>.
TRV.computeDragTangents = function(dragStartPositions) {
	var tangents = new Map();
	var layer = TRV.getActiveLayer();
	if (!layer) return tangents;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!dragStartPositions.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;
				if (!nodes[ni].smooth) continue;

				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;
				var prevIsOn = (nodes[prevIdx].type === 'on');
				var nextIsOn = (nodes[nextIdx].type === 'on');

				// Both sides are lines — no tangent constraint
				if (prevIsOn && nextIsOn) continue;

				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;
				var onStart = dragStartPositions.get(id);
				var dx, dy;
				var isLocked = true; // line-curve: always constrained

				if (!prevIsOn && !nextIsOn) {
					// Curve on both sides: tangent from handle to handle
					// Active only with Ctrl held (locked: false)
					var prevPos = dragStartPositions.has(prevId) ? dragStartPositions.get(prevId) : nodes[prevIdx];
					var nextPos = dragStartPositions.has(nextId) ? dragStartPositions.get(nextId) : nodes[nextIdx];
					dx = nextPos.x - prevPos.x;
					dy = nextPos.y - prevPos.y;
					isLocked = false;
				} else {
					// Line on one side, curve on the other:
					// tangent locked to line direction
					var lineIdx, lineId;
					if (prevIsOn) {
						lineIdx = prevIdx; lineId = prevId;
					} else {
						lineIdx = nextIdx; lineId = nextId;
					}
					// Line neighbor's start position (or current if not dragged)
					var linePos = dragStartPositions.has(lineId) ? dragStartPositions.get(lineId) : nodes[lineIdx];
					// Direction from line neighbor to this on-curve
					dx = onStart.x - linePos.x;
					dy = onStart.y - linePos.y;
				}

				var len = Math.sqrt(dx * dx + dy * dy);
				if (len < 0.001) continue;

				tangents.set(id, { tx: dx / len, ty: dy / len, locked: isLocked });
			}
			ci++;
		}
	}
	return tangents;
};

// Project a delta (dx, dy) onto a unit tangent (tx, ty).
// Returns { dx, dy } along the tangent direction.
TRV.projectOntoTangent = function(dx, dy, tangent) {
	var dot = dx * tangent.tx + dy * tangent.ty;
	return { dx: dot * tangent.tx, dy: dot * tangent.ty };
};

// -- Toggle smooth / sharp on selected on-curve nodes ---------------
// When converting to smooth, enforces collinearity by adjusting the
// shorter handle to match the longer handle's direction.
TRV.toggleSmooth = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) return;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!sel.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				nodes[ni].smooth = !nodes[ni].smooth;

				// When making smooth, enforce collinearity immediately
				if (nodes[ni].smooth) {
					TRV._makeSmoothAt(nodes, n, ni);
				}
			}
			ci++;
		}
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

// Enforce collinearity at on-curve node onIdx by rotating the shorter
// handle to be collinear with the longer one (preserving both lengths).
TRV._makeSmoothAt = function(nodes, n, onIdx) {
	var prevIdx = (onIdx - 1 + n) % n;
	var nextIdx = (onIdx + 1) % n;
	var prevIsHandle = (nodes[prevIdx].type !== 'on');
	var nextIsHandle = (nodes[nextIdx].type !== 'on');

	// Both sides are lines — nothing to enforce
	if (!prevIsHandle && !nextIsHandle) return;

	var ox = nodes[onIdx].x, oy = nodes[onIdx].y;

	if (prevIsHandle && nextIsHandle) {
		// Curve on both sides: keep longer handle, rotate shorter one
		var pDx = nodes[prevIdx].x - ox, pDy = nodes[prevIdx].y - oy;
		var nDx = nodes[nextIdx].x - ox, nDy = nodes[nextIdx].y - oy;
		var pLen = Math.sqrt(pDx * pDx + pDy * pDy);
		var nLen = Math.sqrt(nDx * nDx + nDy * nDy);
		if (pLen < 0.001 || nLen < 0.001) return;

		var fixDx, fixDy, fixLen, adjIdx, adjLen;
		if (pLen >= nLen) {
			fixDx = pDx; fixDy = pDy; fixLen = pLen;
			adjIdx = nextIdx; adjLen = nLen;
		} else {
			fixDx = nDx; fixDy = nDy; fixLen = nLen;
			adjIdx = prevIdx; adjLen = pLen;
		}

		var scale = -adjLen / fixLen;
		nodes[adjIdx].x = Math.round((ox + fixDx * scale) * 10) / 10;
		nodes[adjIdx].y = Math.round((oy + fixDy * scale) * 10) / 10;
	} else {
		// Line on one side, curve on the other:
		// align handle to the line direction (opposite sense)
		var lineIdx = prevIsHandle ? nextIdx : prevIdx;
		var handleIdx = prevIsHandle ? prevIdx : nextIdx;

		// Line direction: from line neighbor to this on-curve
		var lDx = ox - nodes[lineIdx].x;
		var lDy = oy - nodes[lineIdx].y;
		var lLen = Math.sqrt(lDx * lDx + lDy * lDy);
		if (lLen < 0.001) return;

		// Preserve handle length, place along line direction (away from line neighbor)
		var hDx = nodes[handleIdx].x - ox;
		var hDy = nodes[handleIdx].y - oy;
		var hLen = Math.sqrt(hDx * hDx + hDy * hDy);
		if (hLen < 0.001) return;

		var scale = hLen / lLen;
		nodes[handleIdx].x = Math.round((ox + lDx * scale) * 10) / 10;
		nodes[handleIdx].y = Math.round((oy + lDy * scale) * 10) / 10;
	}
};

// -- Smooth node constraint ------------------------------------------
// Two mechanisms, used in different contexts:
//
// A) Mouse drag (absolute positioning):
//    1. startDrag saves follower handles in dragStartPositions
//    2. Drag handler positions ALL entries from their start + delta
//    3. enforceSmoothCollinearity adjusts opposite handles
//
// B) Arrow keys (incremental):
//    1. moveSelectedNodes adds step to selected nodes
//    2. enforceSmoothForKeys translates adjacent handles, then
//       enforces collinearity

// Get non-selected handles adjacent to selected on-curves.
// These should follow their parent during drag (rigid body).
// Returns Map<nodeId, {x, y}> of current positions.
TRV.getFollowerHandles = function(selectedIds) {
	var followers = new Map();
	var layer = TRV.getActiveLayer();
	if (!layer) return followers;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!selectedIds.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				// Check adjacent nodes
				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;
				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;

				if (nodes[prevIdx].type !== 'on' && !selectedIds.has(prevId)) {
					followers.set(prevId, { x: nodes[prevIdx].x, y: nodes[prevIdx].y });
				}
				if (nodes[nextIdx].type !== 'on' && !selectedIds.has(nextId)) {
					followers.set(nextId, { x: nodes[nextIdx].x, y: nodes[nextIdx].y });
				}
			}
			ci++;
		}
	}
	return followers;
};

// Enforce collinearity on smooth nodes after positioning.
// Called after all nodes (selected + followers) have been placed.
// movedIds: Set of all node IDs that were repositioned this frame.
TRV.enforceSmoothCollinearity = function(movedIds) {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!movedIds.has(id)) continue;
				if (nodes[ni].type === 'on') continue; // only handles

				TRV._enforceOppositeSmooth(nodes, n, ni, ci, movedIds);
			}
			ci++;
		}
	}
};

// Arrow key variant: translate adjacent handles then enforce collinearity.
// dx, dy are the incremental step (called once per keypress, so no drift).
TRV.enforceSmoothForKeys = function(draggedIds, dx, dy) {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	// First pass: translate non-selected handles adjacent to selected on-curves
	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!draggedIds.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;
				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;

				if (nodes[prevIdx].type !== 'on' && !draggedIds.has(prevId)) {
					nodes[prevIdx].x = Math.round((nodes[prevIdx].x + dx) * 10) / 10;
					nodes[prevIdx].y = Math.round((nodes[prevIdx].y + dy) * 10) / 10;
				}
				if (nodes[nextIdx].type !== 'on' && !draggedIds.has(nextId)) {
					nodes[nextIdx].x = Math.round((nodes[nextIdx].x + dx) * 10) / 10;
					nodes[nextIdx].y = Math.round((nodes[nextIdx].y + dy) * 10) / 10;
				}
			}
			ci++;
		}
	}

	// Second pass: enforce collinearity for moved handles
	ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!draggedIds.has(id)) continue;
				if (nodes[ni].type === 'on') continue;

				TRV._enforceOppositeSmooth(nodes, n, ni, ci, draggedIds);
			}
			ci++;
		}
	}
};

// For handle at handleIdx, find parent on-curve. If smooth, adjust
// the opposite handle to maintain collinearity (same angle, opposite
// direction, preserving the opposite handle's original length).
TRV._enforceOppositeSmooth = function(nodes, n, handleIdx, ci, movedIds) {
	var prevIdx = (handleIdx - 1 + n) % n;
	var nextIdx = (handleIdx + 1) % n;

	// Find parent on-curve (adjacent to this handle)
	var parentIdx = -1;
	if (nodes[prevIdx].type === 'on') parentIdx = prevIdx;
	else if (nodes[nextIdx].type === 'on') parentIdx = nextIdx;
	else return; // no adjacent on-curve

	var parent = nodes[parentIdx];
	if (!parent.smooth) return; // corner node — nothing to enforce

	// Opposite side of parent
	var oppositeIdx;
	if (parentIdx === prevIdx) {
		oppositeIdx = (parentIdx - 1 + n) % n;
	} else {
		oppositeIdx = (parentIdx + 1) % n;
	}

	var ox = parent.x, oy = parent.y;

	if (nodes[oppositeIdx].type === 'on') {
		// Opposite is a line segment: constrain dragged handle to line direction.
		// Line direction: from line neighbor to parent on-curve
		var lDx = ox - nodes[oppositeIdx].x;
		var lDy = oy - nodes[oppositeIdx].y;
		var lLen = Math.sqrt(lDx * lDx + lDy * lDy);
		if (lLen < 0.001) return;

		// Handle extends along lDx,lDy (continuing the line past parent)
		var ux = lDx / lLen, uy = lDy / lLen;
		var hx = nodes[handleIdx].x - ox;
		var hy = nodes[handleIdx].y - oy;
		var dot = hx * ux + hy * uy;
		var hLen = Math.max(dot, 0); // clamp: don't flip past parent

		nodes[handleIdx].x = Math.round((ox + ux * hLen) * 10) / 10;
		nodes[handleIdx].y = Math.round((oy + uy * hLen) * 10) / 10;
		return;
	}

	// Skip if opposite handle is also being moved (user controls both)
	var oppositeId = 'c' + ci + '_n' + oppositeIdx;
	if (movedIds.has(oppositeId)) return;

	// Vector from parent to dragged handle
	var hx = nodes[handleIdx].x, hy = nodes[handleIdx].y;
	var vx = hx - ox, vy = hy - oy;
	var dist = Math.sqrt(vx * vx + vy * vy);
	if (dist < 0.001) return;

	// Preserve opposite handle's distance from parent
	var opDx = nodes[oppositeIdx].x - ox;
	var opDy = nodes[oppositeIdx].y - oy;
	var opLen = Math.sqrt(opDx * opDx + opDy * opDy);
	if (opLen < 0.001) return;

	// Place opposite at reversed direction, scaled to its length
	var scale = -opLen / dist;
	nodes[oppositeIdx].x = Math.round((ox + vx * scale) * 10) / 10;
	nodes[oppositeIdx].y = Math.round((oy + vy * scale) * 10) / 10;
};

// -- Fit to view ----------------------------------------------------
TRV.fitToView = function() {
	const layer = TRV.getActiveLayer();
	if (!layer) return;

	const canvasW = TRV.dom.canvasWrap.clientWidth;
	const canvasH = TRV.dom.canvasWrap.clientHeight;

	// Joined multi-view: fit the entire joined layout
	if (TRV.state.multiView && TRV.state.joinedView) {
		const layout = TRV.getJoinedLayout();

		const padding = 40;
		const scaleX = (canvasW - padding * 2) / layout.totalW;
		const scaleY = (canvasH - padding * 2) / layout.totalH;
		TRV.state.zoom = Math.min(scaleX, scaleY);

		// Center of the joined layout in glyph space
		const cx = layout.totalW / 2;
		const cy = layout.totalH / 2;
		TRV.state.pan.x = canvasW / 2 - cx * TRV.state.zoom;
		TRV.state.pan.y = canvasH / 2 + cy * TRV.state.zoom;

		TRV.updateZoomStatus();
		TRV.draw();
		return;
	}

	// Split multi-view: fit to cell dimensions
	var w, h;
	if (TRV.state.multiView) {
		const cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);
		w = cell.w;
		h = cell.h;
	} else {
		w = canvasW;
		h = canvasH;
	}

	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			for (const node of contour.nodes) {
				minX = Math.min(minX, node.x);
				minY = Math.min(minY, node.y);
				maxX = Math.max(maxX, node.x);
				maxY = Math.max(maxY, node.y);
			}
		}
	}

	minX = Math.min(minX, 0);
	maxX = Math.max(maxX, layer.width);
	minY = Math.min(minY, 0);
	maxY = Math.max(maxY, layer.height);

	if (layer.anchors) {
		for (const a of layer.anchors) {
			minX = Math.min(minX, a.x);
			minY = Math.min(minY, a.y);
			maxX = Math.max(maxX, a.x);
			maxY = Math.max(maxY, a.y);
		}
	}

	const glyphW = maxX - minX || 1;
	const glyphH = maxY - minY || 1;

	const padding = TRV.state.multiView ? 30 : 60;
	const scaleX = (w - padding * 2) / glyphW;
	const scaleY = (h - padding * 2) / glyphH;
	TRV.state.zoom = Math.min(scaleX, scaleY);

	const cx = (minX + maxX) / 2;
	const cy = (minY + maxY) / 2;
	TRV.state.pan.x = w / 2 - cx * TRV.state.zoom;
	TRV.state.pan.y = h / 2 + cy * TRV.state.zoom;

	TRV.updateZoomStatus();
	TRV.draw();
};

TRV.updateZoomStatus = function() {
	TRV.dom.statusZoom.textContent = Math.round(TRV.state.zoom * 100) + '%';
};

// Zoom centred on the viewport middle (for keyboard zoom)
TRV.zoomAtCenter = function(factor) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cx = w / 2;
	const cy = h / 2;
	const newZoom = TRV.state.zoom * factor;

	TRV.state.pan.x = cx - (cx - TRV.state.pan.x) * (newZoom / TRV.state.zoom);
	TRV.state.pan.y = cy - (cy - TRV.state.pan.y) * (newZoom / TRV.state.zoom);
	TRV.state.zoom = newZoom;

	TRV.updateZoomStatus();
	TRV.draw();
};

// -- File I/O -------------------------------------------------------
TRV.loadXmlString = function(xmlString, filename) {
	try {
		TRV.state.glyphData = TRV.parseGlyphXML(xmlString);
		TRV.state.rawXml = xmlString;

		TRV.dom.layerSelect.innerHTML = '';
		for (const layer of TRV.state.glyphData.layers) {
			const opt = document.createElement('option');
			opt.value = layer.name;
			opt.textContent = layer.name || '(unnamed)';
			TRV.dom.layerSelect.appendChild(opt);
		}

		if (TRV.state.glyphData.layers.length > 0) {
			TRV.state.activeLayer = TRV.state.glyphData.layers[0].name;
			TRV.dom.layerSelect.value = TRV.state.activeLayer;
		}

		const g = TRV.state.glyphData;
		var infoHtml = '<span>' + (g.name || '?') + '</span>';
		if (g.unicodes) infoHtml += ' U+' + g.unicodes;
		TRV.dom.glyphInfo.innerHTML = infoHtml;

		TRV.dom.emptyState.classList.add('hidden');
		TRV.state.selectedNodeIds.clear();

		// Re-init grid if multi-view is active
		if (TRV.state.multiView) TRV.initMultiGrid();

		TRV.fitToView();
		TRV.buildXmlPanel();
	} catch (e) {
		alert('Error loading XML: ' + e.message);
	}
};

TRV.saveXml = function() {
	// Always serialize fresh from data for saving
	var xmlString = TRV.state.glyphData ? TRV.glyphToXml(TRV.state.glyphData) : TRV.state.rawXml;
	if (!xmlString) return;

	const blob = new Blob([xmlString], { type: 'application/xml' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	const name = TRV.state.glyphData ? TRV.state.glyphData.name : 'glyph';
	a.download = name + '.trglyph';
	a.click();
	URL.revokeObjectURL(url);
};

// -- Cursor helpers -------------------------------------------------
TRV.updateCanvasCursor = function() {
	const wrap = TRV.dom.canvasWrap;
	const state = TRV.state;
	if (state.spaceDown) {
		wrap.style.cursor = state.isPanning ? 'grabbing' : 'grab';
	} else if (state.isDragging) {
		wrap.style.cursor = 'move';
	} else if (state.isSelecting) {
		wrap.style.cursor = state.selectMode === 'lasso' ? 'default' : 'crosshair';
	} else {
		wrap.style.cursor = 'default';
	}
};

// -- Node movement by keyboard (moves all selected) -----------------
TRV.ARROW_STEP = 1;
TRV.ARROW_STEP_SHIFT = 10;
TRV.ARROW_STEP_CTRL = 100;

TRV.moveSelectedNodes = function(dx, dy) {
	const sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) return;

	for (const nodeId of sel) {
		const ref = TRV.findNodeById(nodeId);
		if (!ref) continue;
		ref.node.x = Math.round((ref.node.x + dx) * 10) / 10;
		ref.node.y = Math.round((ref.node.y + dy) * 10) / 10;
	}

	// Enforce smooth tangent continuity on neighbors
	TRV.enforceSmoothForKeys(sel, dx, dy);

	// No XML sync here — user clicks Refresh when needed
	TRV.draw();
	TRV.updateStatusSelected();
};
