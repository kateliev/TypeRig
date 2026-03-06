// ===================================================================
// TypeRig Glyph Viewer — Interaction Helpers
// ===================================================================
'use strict';

// -- Undo / Redo (snapshot-based) -----------------------------------
TRV.undoStack = [];
TRV.redoStack = [];
TRV.UNDO_MAX = 99;
TRV._nudgeTimer = null;
TRV._nudgeUndoPushed = false;

// Deep-clone the active layer's shape tree (shapes → contours → nodes)
TRV._snapshotLayer = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return null;
	return JSON.parse(JSON.stringify(layer.shapes));
};

// Restore a snapshot into the active layer
TRV._restoreSnapshot = function(snapshot) {
	var layer = TRV.getActiveLayer();
	if (!layer || !snapshot) return;
	layer.shapes = JSON.parse(JSON.stringify(snapshot));
};

// Push current state onto undo stack (call before modifying)
TRV.pushUndo = function() {
	var snapshot = TRV._snapshotLayer();
	if (!snapshot) return;
	TRV.undoStack.push(snapshot);
	if (TRV.undoStack.length > TRV.UNDO_MAX) {
		TRV.undoStack.shift();
	}
	// Any new action clears redo
	TRV.redoStack.length = 0;
};

// Push undo for nudge with timer coalescing.
// Multiple nudges within 400ms count as one undo step.
TRV.pushUndoNudge = function() {
	if (!TRV._nudgeUndoPushed) {
		TRV.pushUndo();
		TRV._nudgeUndoPushed = true;
	}
	clearTimeout(TRV._nudgeTimer);
	TRV._nudgeTimer = setTimeout(function() {
		TRV._nudgeUndoPushed = false;
	}, 400);
};

TRV.undo = function() {
	if (TRV.undoStack.length === 0) return;
	// Save current state to redo
	var current = TRV._snapshotLayer();
	if (current) TRV.redoStack.push(current);
	// Restore previous
	var snapshot = TRV.undoStack.pop();
	TRV._restoreSnapshot(snapshot);
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
	TRV.xmlRefresh();
};

TRV.redo = function() {
	if (TRV.redoStack.length === 0) return;
	// Save current state to undo
	var current = TRV._snapshotLayer();
	if (current) TRV.undoStack.push(current);
	// Restore next
	var snapshot = TRV.redoStack.pop();
	TRV._restoreSnapshot(snapshot);
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
	TRV.xmlRefresh();
};

// Clear undo history (e.g. when loading new glyph)
TRV.clearUndo = function() {
	TRV.undoStack.length = 0;
	TRV.redoStack.length = 0;
};

// -- Preview button sync --------------------------------------------
TRV.updatePreviewButton = function() {
	var btn = document.getElementById('btn-preview');
	if (btn) btn.classList.toggle('active', TRV.state.previewLocked);
};

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

// -- Open contour at selected node (Del) ----------------------------
// Splits the contour at the selected on-curve node: duplicates it,
// sets contour.closed = false. The original node becomes the end,
// the duplicate becomes the new start.
TRV.openContourAtNode = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size !== 1) return; // only works on single node

	var nodeId = sel.values().next().value;
	var ref = TRV.findNodeById(nodeId);
	if (!ref || ref.node.type !== 'on') return;

	var contour = ref.contour;
	var nodes = contour.nodes;
	var n = nodes.length;

	var m = nodeId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return;
	var ni = parseInt(m[2]);

	if (contour.closed) {
		// -- Closed contour: open at this node --
		// Rotate so selected node is at position 0
		var rotated = nodes.slice(ni).concat(nodes.slice(0, ni));

		// Duplicate the start node at the end (endpoint)
		var startNode = rotated[0];
		var endNode = {
			type: startNode.type,
			smooth: false,
			x: startNode.x,
			y: startNode.y
		};
		startNode.smooth = false;
		rotated.push(endNode);

		contour.nodes = rotated;
		contour.closed = false;
	} else {
		// -- Open contour: split into two at this node --
		// Don't split at the very first or last on-curve (endpoints)
		var ep = TRV.getOpenEndpoints(contour);
		if (!ep) return;
		if (ni === ep.startIdx || ni === ep.endIdx) return;

		// First part: nodes from start to ni (inclusive)
		var firstNodes = nodes.slice(0, ni + 1);
		// Second part: nodes from ni to end (inclusive — duplicate the split node)
		var secondNodes = nodes.slice(ni);

		// Make the split node sharp at both new endpoints
		firstNodes[firstNodes.length - 1] = {
			type: 'on', smooth: false,
			x: nodes[ni].x, y: nodes[ni].y
		};
		secondNodes[0] = {
			type: 'on', smooth: false,
			x: nodes[ni].x, y: nodes[ni].y
		};

		// Validate: each part needs at least 2 on-curves to be a contour
		var firstOnCount = 0, secondOnCount = 0;
		for (var i = 0; i < firstNodes.length; i++) {
			if (firstNodes[i].type === 'on') firstOnCount++;
		}
		for (var i = 0; i < secondNodes.length; i++) {
			if (secondNodes[i].type === 'on') secondOnCount++;
		}
		if (firstOnCount < 2 || secondOnCount < 2) return;

		// Replace original contour with first part
		contour.nodes = firstNodes;
		contour.closed = false;

		// Create new contour for second part and add to the same shape
		var newContour = {
			nodes: secondNodes,
			closed: false,
			clockwise: contour.clockwise
		};
		var shape = ref.shape;
		var ci = shape.contours.indexOf(contour);
		shape.contours.splice(ci + 1, 0, newContour);
	}

	sel.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Delete selected node (Backspace) ------------------------------
// Removes the selected on-curve and reconstructs adjacent beziers.
// Curve-Curve: merges two cubics into one, keeping outer handles
//   with proportionally scaled lengths.
// Curve-Line or Line-Curve: converts to a single cubic using the
//   surviving handle and a synthetic one for the line side.
// Line-Line: simple removal, straight line remains.
TRV.deleteNode = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size !== 1) return;

	var nodeId = sel.values().next().value;
	var ref = TRV.findNodeById(nodeId);
	if (!ref) return;

	var contour = ref.contour;
	var nodes = contour.nodes;
	var n = nodes.length;

	var m = nodeId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return;
	var ni = parseInt(m[2]);
	var node = nodes[ni];

	if (node.type !== 'on') {
		// Off-curve selected: convert parent segment to line
		// Find segment containing this off-curve node
		var segs = TRV.getContourSegments(contour);
		for (var gi = 0; gi < segs.length; gi++) {
			var seg = segs[gi];
			var isInSeg = false;
			if (seg.type === 'cubic' && (ni === seg.offIdx1 || ni === seg.offIdx2)) isInSeg = true;
			if (seg.type === 'quadratic' && ni === seg.offIdx) isInSeg = true;
			if (isInSeg) {
				// Build a synthetic hit for convertSegmentToLine
				TRV.convertSegmentToLine({ contour: contour, seg: seg });
				return;
			}
		}
		// Fallback: just clear selection
		sel.clear();
		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// -- On-curve node deletion --
	// Analyze incoming and outgoing segments
	var incoming = TRV._analyzeIncoming(nodes, n, ni);
	var outgoing = TRV._analyzeOutgoing(nodes, n, ni);

	// Collect dense samples from both segments BEFORE removing anything.
	// Skip duplicate at the junction (the deleted node itself).
	var samplesIn = TRV._sampleSegment(nodes, n, ni, 'incoming', 40);
	var samplesOut = TRV._sampleSegment(nodes, n, ni, 'outgoing', 40);
	// Merge: incoming ends at deleted node, outgoing starts there — skip first of outgoing
	if (samplesOut.length > 0) samplesOut.shift();
	TRV._pendingSamples = samplesIn.concat(samplesOut);

	// Build replacement nodes to insert between prev on-curve and next on-curve
	var replacement = TRV._buildReplacement(nodes, incoming, outgoing);
	TRV._pendingSamples = null;

	// Collect all indices to remove (the on-curve + its adjacent handles)
	var toRemove = new Set();
	toRemove.add(ni);
	for (var i = 0; i < incoming.handleIndices.length; i++) {
		toRemove.add(incoming.handleIndices[i]);
	}
	for (var i = 0; i < outgoing.handleIndices.length; i++) {
		toRemove.add(outgoing.handleIndices[i]);
	}

	// Build new node array
	var newNodes = [];
	for (var i = 0; i < n; i++) {
		if (toRemove.has(i)) {
			// At the position of the deleted on-curve, insert replacement
			if (i === ni) {
				for (var j = 0; j < replacement.length; j++) {
					newNodes.push(replacement[j]);
				}
			}
			continue;
		}
		newNodes.push(nodes[i]);
	}

	contour.nodes = newNodes;

	// If fewer than 2 on-curve nodes remain, remove contour
	var onCount = 0;
	for (var i = 0; i < contour.nodes.length; i++) {
		if (contour.nodes[i].type === 'on') onCount++;
	}
	if (onCount < 2) {
		var shape = ref.shape;
		var ci = shape.contours.indexOf(contour);
		if (ci >= 0) shape.contours.splice(ci, 1);
	}

	sel.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// Analyze the incoming segment (ending at onIdx).
// Returns { type, prevOnIdx, handleIndices, outerHandle }
TRV._analyzeIncoming = function(nodes, n, onIdx) {
	var result = { type: 'line', prevOnIdx: -1, handleIndices: [], outerHandle: null };
	var i = (onIdx - 1 + n) % n;

	if (nodes[i].type === 'on') {
		// Line segment: prev on-curve directly
		result.prevOnIdx = i;
		return result;
	}

	// Walk backwards past handles
	var handles = [];
	while (nodes[i].type !== 'on') {
		handles.push(i);
		i = (i - 1 + n) % n;
	}
	result.prevOnIdx = i;
	result.handleIndices = handles;

	if (handles.length >= 2) {
		result.type = 'cubic';
		// Outer handle is the one closest to prevOnIdx (first in the segment)
		result.outerHandle = { x: nodes[handles[handles.length - 1]].x, y: nodes[handles[handles.length - 1]].y };
	} else if (handles.length === 1) {
		result.type = 'quad';
		result.outerHandle = { x: nodes[handles[0]].x, y: nodes[handles[0]].y };
	}

	return result;
};

// Analyze the outgoing segment (starting at onIdx).
// Returns { type, nextOnIdx, handleIndices, outerHandle }
TRV._analyzeOutgoing = function(nodes, n, onIdx) {
	var result = { type: 'line', nextOnIdx: -1, handleIndices: [], outerHandle: null };
	var i = (onIdx + 1) % n;

	if (nodes[i].type === 'on') {
		// Line segment: next on-curve directly
		result.nextOnIdx = i;
		return result;
	}

	// Walk forward past handles
	var handles = [];
	while (nodes[i].type !== 'on') {
		handles.push(i);
		i = (i + 1) % n;
	}
	result.nextOnIdx = i;
	result.handleIndices = handles;

	if (handles.length >= 2) {
		result.type = 'cubic';
		// Outer handle is the one closest to nextOnIdx (last in the segment)
		result.outerHandle = { x: nodes[handles[handles.length - 1]].x, y: nodes[handles[handles.length - 1]].y };
	} else if (handles.length === 1) {
		result.type = 'quad';
		result.outerHandle = { x: nodes[handles[0]].x, y: nodes[handles[0]].y };
	}

	return result;
};

// Build replacement nodes between prevOn and nextOn after deleting
// the node between incoming and outgoing segments.
TRV._buildReplacement = function(nodes, incoming, outgoing) {
	var round = function(v) { return Math.round(v * 10) / 10; };
	var prevOn = nodes[incoming.prevOnIdx];
	var nextOn = nodes[outgoing.nextOnIdx];

	var inType = incoming.type;
	var outType = outgoing.type;

	// Line-Line: no replacement nodes needed, straight line
	if (inType === 'line' && outType === 'line') {
		return [];
	}

	// Curve-Curve: merge into single cubic with scaled outer handles
	if (inType === 'cubic' && outType === 'cubic') {
		return TRV._mergeCubics(prevOn, incoming.outerHandle, outgoing.outerHandle, nextOn);
	}

	// Curve-Line: cubic from prevOn with incoming outer handle → nextOn
	if (inType === 'cubic' && outType === 'line') {
		return TRV._curveToLine(prevOn, incoming.outerHandle, nextOn);
	}

	// Line-Curve: cubic from prevOn → nextOn with outgoing outer handle
	if (inType === 'line' && outType === 'cubic') {
		return TRV._lineToCurve(prevOn, outgoing.outerHandle, nextOn);
	}

	// Fallback for quad or mixed: just line
	return [];
};

// -- Least-squares cubic Bezier fitting ------------------------------
// Sample a cubic at parameter t
TRV._sampleCubic = function(p0, p1, p2, p3, t) {
	var u = 1 - t;
	var uu = u * u, tt = t * t;
	return {
		x: uu * u * p0.x + 3 * uu * t * p1.x + 3 * u * tt * p2.x + tt * t * p3.x,
		y: uu * u * p0.y + 3 * uu * t * p1.y + 3 * u * tt * p2.y + tt * t * p3.y
	};
};

// Sample a line at parameter t
TRV._sampleLine = function(p0, p1, t) {
	return {
		x: p0.x + t * (p1.x - p0.x),
		y: p0.y + t * (p1.y - p0.y)
	};
};

// Collect dense samples from a segment, returns [{ x, y }]
TRV._sampleSegment = function(nodes, n, onIdx, direction, numSamples) {
	var samples = [];
	var i, pts;

	if (direction === 'incoming') {
		// Walk backward from onIdx to find segment start
		i = (onIdx - 1 + n) % n;
		if (nodes[i].type === 'on') {
			// Line
			for (var s = 0; s <= numSamples; s++) {
				var t = s / numSamples;
				samples.push(TRV._sampleLine(nodes[i], nodes[onIdx], t));
			}
			return samples;
		}
		// Cubic: walk back to find start on-curve
		var handles = [];
		while (nodes[i].type !== 'on') {
			handles.unshift(i);
			i = (i - 1 + n) % n;
		}
		// i is the start on-curve, handles go toward onIdx
		if (handles.length >= 2) {
			var p0 = nodes[i];
			var p1 = nodes[handles[0]];
			var p2 = nodes[handles[1]];
			var p3 = nodes[onIdx];
			for (var s = 0; s <= numSamples; s++) {
				samples.push(TRV._sampleCubic(p0, p1, p2, p3, s / numSamples));
			}
		}
		return samples;
	} else {
		// Outgoing: walk forward from onIdx
		i = (onIdx + 1) % n;
		if (nodes[i].type === 'on') {
			for (var s = 0; s <= numSamples; s++) {
				samples.push(TRV._sampleLine(nodes[onIdx], nodes[i], s / numSamples));
			}
			return samples;
		}
		var handles = [];
		while (nodes[i].type !== 'on') {
			handles.push(i);
			i = (i + 1) % n;
		}
		if (handles.length >= 2) {
			var p0 = nodes[onIdx];
			var p1 = nodes[handles[0]];
			var p2 = nodes[handles[1]];
			var p3 = nodes[i];
			for (var s = 0; s <= numSamples; s++) {
				samples.push(TRV._sampleCubic(p0, p1, p2, p3, s / numSamples));
			}
		}
		return samples;
	}
};

// Arc-length parameterization: assign t values to samples based on
// cumulative distance, normalized to [0, 1].
TRV._arcLengthParameterize = function(samples) {
	var params = [0];
	var total = 0;
	for (var i = 1; i < samples.length; i++) {
		var dx = samples[i].x - samples[i - 1].x;
		var dy = samples[i].y - samples[i - 1].y;
		total += Math.sqrt(dx * dx + dy * dy);
		params.push(total);
	}
	if (total > 0.001) {
		for (var i = 0; i < params.length; i++) {
			params[i] /= total;
		}
	}
	return params;
};

// Unconstrained least-squares: fit cubic P0→P1→P2→P3 to samples.
// P0 and P3 are fixed endpoints. Solves for P1, P2.
TRV._fitCubicUnconstrained = function(samples, params, P0, P3) {
	var round = function(v) { return Math.round(v * 10) / 10; };

	// Build normal equations for: A1*P1 + A2*P2 = R
	// A1i = 3(1-t)²t,  A2i = 3(1-t)t²
	var C00 = 0, C01 = 0, C11 = 0;
	var Rx0 = 0, Ry0 = 0, Rx1 = 0, Ry1 = 0;

	for (var i = 0; i < samples.length; i++) {
		var t = params[i];
		var u = 1 - t;
		var A1 = 3 * u * u * t;
		var A2 = 3 * u * t * t;

		// Residual: sample minus endpoint contribution
		var rx = samples[i].x - (u * u * u * P0.x + t * t * t * P3.x);
		var ry = samples[i].y - (u * u * u * P0.y + t * t * t * P3.y);

		C00 += A1 * A1;
		C01 += A1 * A2;
		C11 += A2 * A2;
		Rx0 += A1 * rx;
		Ry0 += A1 * ry;
		Rx1 += A2 * rx;
		Ry1 += A2 * ry;
	}

	// Solve 2x2 system: [C00, C01; C01, C11] * [p1, p2] = [R0, R1]
	var det = C00 * C11 - C01 * C01;
	if (Math.abs(det) < 1e-12) {
		// Degenerate: fall back to 1/3 rule
		return {
			P1: { x: round(P0.x + (P3.x - P0.x) / 3), y: round(P0.y + (P3.y - P0.y) / 3) },
			P2: { x: round(P3.x - (P3.x - P0.x) / 3), y: round(P3.y - (P3.y - P0.y) / 3) }
		};
	}

	var invDet = 1 / det;
	return {
		P1: {
			x: round((C11 * Rx0 - C01 * Rx1) * invDet),
			y: round((C11 * Ry0 - C01 * Ry1) * invDet)
		},
		P2: {
			x: round((C00 * Rx1 - C01 * Rx0) * invDet),
			y: round((C00 * Ry1 - C01 * Ry0) * invDet)
		}
	};
};

// Tangent-constrained least-squares: P1 = P0 + α₁·T1, P2 = P3 + α₂·T2.
// Solves for scalar distances α₁, α₂ (preserves G1 continuity).
TRV._fitCubicConstrained = function(samples, params, P0, P3, T1, T2) {
	var round = function(v) { return Math.round(v * 10) / 10; };
	var dot12 = T1.x * T2.x + T1.y * T2.y;

	var C00 = 0, C01 = 0, C11 = 0;
	var R0 = 0, R1 = 0;

	for (var i = 0; i < samples.length; i++) {
		var t = params[i];
		var u = 1 - t;
		var b1 = 3 * u * u * t;
		var b2 = 3 * u * t * t;

		// With P1 = P0 + α₁T1 and P2 = P3 + α₂T2, the fixed part is
		// (B0+B1)·P0 + (B2+B3)·P3, not just B0·P0 + B3·P3
		var fixedP0 = u * u * u + b1;   // B0 + B1
		var fixedP3 = b2 + t * t * t;   // B2 + B3
		var rx = samples[i].x - (fixedP0 * P0.x + fixedP3 * P3.x);
		var ry = samples[i].y - (fixedP0 * P0.y + fixedP3 * P3.y);

		C00 += b1 * b1;           // T1·T1 = 1
		C01 += b1 * b2 * dot12;   // T1·T2
		C11 += b2 * b2;           // T2·T2 = 1
		R0  += b1 * (T1.x * rx + T1.y * ry);
		R1  += b2 * (T2.x * rx + T2.y * ry);
	}

	var det = C00 * C11 - C01 * C01;
	var alpha1, alpha2;

	if (Math.abs(det) < 1e-12) {
		// Degenerate: use chord thirds
		var chordDx = P3.x - P0.x;
		var chordDy = P3.y - P0.y;
		var chordLen = Math.sqrt(chordDx * chordDx + chordDy * chordDy);
		alpha1 = chordLen / 3;
		alpha2 = chordLen / 3;
	} else {
		alpha1 = (C11 * R0 - C01 * R1) / det;
		alpha2 = (C00 * R1 - C01 * R0) / det;
	}

	// Clamp: prevent degenerate negative or extreme handles
	var chordDx = P3.x - P0.x;
	var chordDy = P3.y - P0.y;
	var chordLen = Math.sqrt(chordDx * chordDx + chordDy * chordDy);
	var maxLen = chordLen * 4; // large arcs need long handles
	alpha1 = Math.max(0.01, Math.min(alpha1, maxLen));
	alpha2 = Math.max(0.01, Math.min(alpha2, maxLen));

	return {
		P1: {
			x: round(P0.x + alpha1 * T1.x),
			y: round(P0.y + alpha1 * T1.y)
		},
		P2: {
			x: round(P3.x + alpha2 * T2.x),
			y: round(P3.y + alpha2 * T2.y)
		}
	};
};

// Newton-Raphson reparameterization: improve t values for each sample
// by projecting onto the current fitted curve.
TRV._reparameterize = function(samples, params, P0, P1, P2, P3) {
	var newParams = [];
	for (var i = 0; i < samples.length; i++) {
		var t = params[i];
		var Q = samples[i];

		// Evaluate curve and derivative at t
		var u = 1 - t;
		var Bt = {
			x: u*u*u*P0.x + 3*u*u*t*P1.x + 3*u*t*t*P2.x + t*t*t*P3.x,
			y: u*u*u*P0.y + 3*u*u*t*P1.y + 3*u*t*t*P2.y + t*t*t*P3.y
		};
		// First derivative
		var Bd = {
			x: 3*u*u*(P1.x-P0.x) + 6*u*t*(P2.x-P1.x) + 3*t*t*(P3.x-P2.x),
			y: 3*u*u*(P1.y-P0.y) + 6*u*t*(P2.y-P1.y) + 3*t*t*(P3.y-P2.y)
		};
		// Second derivative
		var Bdd = {
			x: 6*u*(P2.x-2*P1.x+P0.x) + 6*t*(P3.x-2*P2.x+P1.x),
			y: 6*u*(P2.y-2*P1.y+P0.y) + 6*t*(P3.y-2*P2.y+P1.y)
		};

		var dx = Bt.x - Q.x, dy = Bt.y - Q.y;
		var num = dx * Bd.x + dy * Bd.y;
		var den = Bd.x*Bd.x + Bd.y*Bd.y + dx*Bdd.x + dy*Bdd.y;

		var newT = (Math.abs(den) > 1e-12) ? t - num / den : t;
		newParams.push(Math.max(0, Math.min(1, newT)));
	}
	return newParams;
};

// High-level: merge two cubics by sampling + least-squares fitting
// with tangent-constrained optimization and Newton refinement.
TRV._mergeCubics = function(prevOn, inHandle, outHandle, nextOn) {
	return TRV._fitMergedSegments(prevOn, nextOn, inHandle, outHandle, true);
};

TRV._curveToLine = function(prevOn, inHandle, nextOn) {
	return TRV._fitMergedSegments(prevOn, nextOn, inHandle, null, false);
};

TRV._lineToCurve = function(prevOn, outHandle, nextOn) {
	return TRV._fitMergedSegments(prevOn, nextOn, null, outHandle, false);
};

// Unified fitting: collects samples from both segments around the
// deleted node, then fits a single cubic.
// inHandle/outHandle may be null for line sides.
TRV._fitMergedSegments = function(P0, P3, inHandle, outHandle, bothCurves) {
	var round = function(v) { return Math.round(v * 10) / 10; };

	// Collect samples from the deleteNode caller — we stored them
	var samples = TRV._pendingSamples;
	var params = TRV._arcLengthParameterize(samples);

	if (samples.length < 4) {
		// Not enough data — 1/3 rule fallback
		return [
			{ type: 'curve', x: round(P0.x + (P3.x - P0.x) / 3), y: round(P0.y + (P3.y - P0.y) / 3) },
			{ type: 'curve', x: round(P3.x - (P3.x - P0.x) / 3), y: round(P3.y - (P3.y - P0.y) / 3) }
		];
	}

	var fit;

	if (bothCurves && inHandle && outHandle) {
		// Tangent-constrained: preserve G1 at endpoints
		var t1dx = inHandle.x - P0.x, t1dy = inHandle.y - P0.y;
		var t1len = Math.sqrt(t1dx * t1dx + t1dy * t1dy);
		var t2dx = outHandle.x - P3.x, t2dy = outHandle.y - P3.y;
		var t2len = Math.sqrt(t2dx * t2dx + t2dy * t2dy);

		if (t1len < 0.001 || t2len < 0.001) {
			fit = TRV._fitCubicUnconstrained(samples, params, P0, P3);
		} else {
			var T1 = { x: t1dx / t1len, y: t1dy / t1len };
			var T2 = { x: t2dx / t2len, y: t2dy / t2len };

			fit = TRV._fitCubicConstrained(samples, params, P0, P3, T1, T2);

			// Newton-Raphson refinement: 3 iterations
			for (var iter = 0; iter < 3; iter++) {
				params = TRV._reparameterize(samples, params, P0, fit.P1, fit.P2, P3);
				fit = TRV._fitCubicConstrained(samples, params, P0, P3, T1, T2);
			}
		}
	} else {
		// Unconstrained for mixed line/curve
		fit = TRV._fitCubicUnconstrained(samples, params, P0, P3);

		// Newton-Raphson refinement: 3 iterations
		for (var iter = 0; iter < 3; iter++) {
			params = TRV._reparameterize(samples, params, P0, fit.P1, fit.P2, P3);
			fit = TRV._fitCubicUnconstrained(samples, params, P0, P3);
		}
	}

	return [
		{ type: 'curve', x: fit.P1.x, y: fit.P1.y },
		{ type: 'curve', x: fit.P2.x, y: fit.P2.y }
	];
};

// -- Join open contour endpoints -------------------------------------
// Returns the open endpoints of a contour:
// { startIdx, endIdx, startNode, endNode } or null if closed.
TRV.getOpenEndpoints = function(contour) {
	if (contour.closed) return null;
	var nodes = contour.nodes;
	if (nodes.length < 2) return null;

	// Find first and last on-curve
	var startIdx = -1, endIdx = -1;
	for (var i = 0; i < nodes.length; i++) {
		if (nodes[i].type === 'on') { startIdx = i; break; }
	}
	for (var i = nodes.length - 1; i >= 0; i--) {
		if (nodes[i].type === 'on') { endIdx = i; break; }
	}
	if (startIdx < 0 || endIdx < 0 || startIdx === endIdx) return null;

	return {
		startIdx: startIdx, endIdx: endIdx,
		startNode: nodes[startIdx], endNode: nodes[endIdx]
	};
};

// Check if a node ID refers to an endpoint of an open contour.
// Returns { contour, shape, ci, end: 'start'|'end' } or null.
TRV.isOpenEndpoint = function(nodeId) {
	var layer = TRV.getActiveLayer();
	if (!layer) return null;

	var m = nodeId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return null;
	var targetCi = parseInt(m[1]);
	var targetNi = parseInt(m[2]);

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			if (ci === targetCi) {
				var ep = TRV.getOpenEndpoints(shape.contours[ki]);
				if (!ep) return null;
				if (targetNi === ep.startIdx) {
					return { contour: shape.contours[ki], shape: shape, ci: ci, ki: ki, end: 'start' };
				}
				if (targetNi === ep.endIdx) {
					return { contour: shape.contours[ki], shape: shape, ci: ci, ki: ki, end: 'end' };
				}
				return null;
			}
			ci++;
		}
	}
	return null;
};

// Find the nearest open endpoint within threshold (glyph units).
// Excludes endpoints belonging to excludeCi contour index (the dragged one).
// Returns { ci, ki, end, contour, shape, dist } or null.
TRV.findNearOpenEndpoint = function(gx, gy, threshold, excludeCi, excludeEnd) {
	var layer = TRV.getActiveLayer();
	if (!layer) return null;

	var best = null;
	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var ep = TRV.getOpenEndpoints(shape.contours[ki]);
			if (ep) {
				// Check start endpoint
				if (!(ci === excludeCi && 'start' === excludeEnd)) {
					var dx = ep.startNode.x - gx, dy = ep.startNode.y - gy;
					var d = Math.sqrt(dx * dx + dy * dy);
					if (d <= threshold && (!best || d < best.dist)) {
						best = { ci: ci, ki: ki, end: 'start', contour: shape.contours[ki], shape: shape, dist: d };
					}
				}
				// Check end endpoint
				if (!(ci === excludeCi && 'end' === excludeEnd)) {
					var dx = ep.endNode.x - gx, dy = ep.endNode.y - gy;
					var d = Math.sqrt(dx * dx + dy * dy);
					if (d <= threshold && (!best || d < best.dist)) {
						best = { ci: ci, ki: ki, end: 'end', contour: shape.contours[ki], shape: shape, dist: d };
					}
				}
			}
			ci++;
		}
	}
	return best;
};

// Try to join at the currently selected endpoint.
// Called after drag or manually. Returns true if joined.
TRV.tryJoinEndpoints = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return false;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size !== 1) return false;

	var nodeId = sel.values().next().value;
	var epInfo = TRV.isOpenEndpoint(nodeId);
	if (!epInfo) return false;

	var node = epInfo.end === 'start'
		? TRV.getOpenEndpoints(epInfo.contour).startNode
		: TRV.getOpenEndpoints(epInfo.contour).endNode;

	var threshold = 2; // glyph units

	// Find nearby endpoint (excluding self)
	var target = TRV.findNearOpenEndpoint(node.x, node.y, threshold, epInfo.ci, epInfo.end);

	if (!target) {
		// Check if same contour's other end is nearby → close
		var selfEp = TRV.getOpenEndpoints(epInfo.contour);
		if (selfEp) {
			var otherNode = epInfo.end === 'start' ? selfEp.endNode : selfEp.startNode;
			var dx = otherNode.x - node.x, dy = otherNode.y - node.y;
			if (Math.sqrt(dx * dx + dy * dy) <= threshold) {
				return TRV._closeContour(epInfo.contour, epInfo.end);
			}
		}
		return false;
	}

	// Same contour, other end → close
	if (target.ci === epInfo.ci) {
		return TRV._closeContour(epInfo.contour, epInfo.end);
	}

	// Different contour → merge
	return TRV._mergeContours(epInfo, target);
};

// Close an open contour: snap endpoint, remove duplicate, set closed.
TRV._closeContour = function(contour, draggedEnd) {
	var ep = TRV.getOpenEndpoints(contour);
	if (!ep) return false;

	if (draggedEnd === 'start') {
		// Snap start to end position
		ep.startNode.x = ep.endNode.x;
		ep.startNode.y = ep.endNode.y;
		// Remove the end duplicate
		contour.nodes.splice(ep.endIdx, 1);
	} else {
		// Snap end to start position
		ep.endNode.x = ep.startNode.x;
		ep.endNode.y = ep.startNode.y;
		// Remove the end node (the dragged one snapped to start)
		contour.nodes.splice(ep.endIdx, 1);
	}

	contour.closed = true;
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
	return true;
};

// Merge two open contours by connecting their endpoints.
// srcInfo: { contour, shape, ci, ki, end } — the dragged endpoint
// tgtInfo: { contour, shape, ci, ki, end } — the target endpoint
TRV._mergeContours = function(srcInfo, tgtInfo) {
	var srcContour = srcInfo.contour;
	var tgtContour = tgtInfo.contour;
	var srcNodes = srcContour.nodes.slice(); // copy
	var tgtNodes = tgtContour.nodes.slice();

	// Orient both so the joining ends are adjacent:
	// srcNodes should end at the joining point
	// tgtNodes should start at the joining point
	if (srcInfo.end === 'start') {
		srcNodes.reverse();
	}
	if (tgtInfo.end === 'end') {
		tgtNodes.reverse();
	}

	// Snap the joining node: remove last of src (duplicate of first of tgt)
	var srcLast = srcNodes[srcNodes.length - 1];
	var tgtFirst = tgtNodes[0];
	// Average position for clean join
	tgtFirst.x = (srcLast.x + tgtFirst.x) / 2;
	tgtFirst.y = (srcLast.y + tgtFirst.y) / 2;
	tgtFirst.x = Math.round(tgtFirst.x * 10) / 10;
	tgtFirst.y = Math.round(tgtFirst.y * 10) / 10;
	srcNodes.pop(); // remove the duplicate

	// Merged nodes
	var mergedNodes = srcNodes.concat(tgtNodes);

	// Replace src contour with merged, remove tgt contour
	srcContour.nodes = mergedNodes;

	// Remove target contour from its shape
	var tgtIdx = tgtInfo.shape.contours.indexOf(tgtContour);
	if (tgtIdx >= 0) {
		tgtInfo.shape.contours.splice(tgtIdx, 1);
	}

	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
	return true;
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

		// Cubic segment: on → curve → curve → on
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

		// Quadratic segment: on → off → on
		if (nodes[next1].type === 'off') {
			var next2q = (i + 2) % n;
			if (nodes[next2q].type === 'on') {
				segments.push({
					type: 'quadratic',
					startIdx: i,
					endIdx: next2q,
					offIdx: next1,
					pts: [
						{ x: nodes[i].x, y: nodes[i].y },
						{ x: nodes[next1].x, y: nodes[next1].y },
						{ x: nodes[next2q].x, y: nodes[next2q].y }
					]
				});
				i += 2;
				continue;
			}
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

// Evaluate a quadratic bezier at parameter t
TRV._evalQuadratic = function(pts, t) {
	var u = 1 - t;
	return {
		x: u * u * pts[0].x + 2 * u * t * pts[1].x + t * t * pts[2].x,
		y: u * u * pts[0].y + 2 * u * t * pts[1].y + t * t * pts[2].y
	};
};

// Find nearest point on a segment, returns { t, dist, x, y }
TRV._nearestOnSegment = function(seg, gx, gy) {
	var evalFn = seg.type === 'cubic' ? TRV._evalCubic :
	             seg.type === 'quadratic' ? TRV._evalQuadratic : TRV._evalLine;
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
	} else if (seg.type === 'quadratic') {
		// De Casteljau split for quadratic: P0,Q1,P2 at t
		var t = hit.t, u = 1 - t;
		var p0 = seg.pts[0], q1 = seg.pts[1], p2 = seg.pts[2];
		var a = { x: u * p0.x + t * q1.x, y: u * p0.y + t * q1.y };
		var b = { x: u * q1.x + t * p2.x, y: u * q1.y + t * p2.y };
		var m = { x: u * a.x + t * b.x, y: u * a.y + t * b.y };

		// Replace single off-curve with: offL, on(new), offR
		var newOffL = { type: 'off', smooth: false, x: round(a.x), y: round(a.y) };
		var newOn   = { type: 'on', smooth: true, x: round(m.x), y: round(m.y) };
		var newOffR = { type: 'off', smooth: false, x: round(b.x), y: round(b.y) };

		nodes.splice(seg.offIdx, 1, newOffL, newOn, newOffR);
	}

	// Rebuild IDs and redraw
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Segment type conversions ----------------------------------------
// Helper: remove off-curve nodes from a segment, leaving on-curves as a line.
// Works for both cubic (2 off-curves) and quadratic (1 off-curve).
TRV.convertSegmentToLine = function(hit) {
	if (!hit || !hit.contour) return;
	var nodes = hit.contour.nodes;
	var seg = hit.seg;
	if (seg.type === 'line') return;

	// Collect off-curve indices to remove (descending order for safe splice)
	var toRemove = [];
	if (seg.type === 'cubic') {
		toRemove = [seg.offIdx1, seg.offIdx2];
	} else if (seg.type === 'quadratic') {
		toRemove = [seg.offIdx];
	}
	toRemove.sort(function(a, b) { return b - a; });
	for (var i = 0; i < toRemove.length; i++) {
		nodes.splice(toRemove[i], 1);
	}

	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// Convert line or quadratic segment to cubic bezier.
// Line: insert two cubic handles at 1/3 and 2/3.
// Quadratic: degree elevation — replace single off with two curve nodes.
TRV.convertSegmentToCubic = function(hit) {
	if (!hit || !hit.contour) return;
	var nodes = hit.contour.nodes;
	var seg = hit.seg;
	if (seg.type === 'cubic') return;

	var round = function(v) { return Math.round(v * 10) / 10; };

	if (seg.type === 'line') {
		var p0 = seg.pts[0], p3 = seg.pts[1];
		var h1 = { type: 'curve', smooth: false,
			x: round(p0.x + (p3.x - p0.x) / 3),
			y: round(p0.y + (p3.y - p0.y) / 3)
		};
		var h2 = { type: 'curve', smooth: false,
			x: round(p0.x + 2 * (p3.x - p0.x) / 3),
			y: round(p0.y + 2 * (p3.y - p0.y) / 3)
		};
		// Insert after startIdx
		var insertAt = seg.startIdx + 1;
		if (seg.endIdx < seg.startIdx) insertAt = nodes.length;
		nodes.splice(insertAt, 0, h1, h2);

	} else if (seg.type === 'quadratic') {
		// Degree elevation: Q0,Q1,Q2 → P0,P1,P2,P3
		// P1 = Q0 + 2/3*(Q1-Q0), P2 = Q2 + 2/3*(Q1-Q2)
		var q0 = seg.pts[0], q1 = seg.pts[1], q2 = seg.pts[2];
		var p1 = {
			x: round(q0.x + 2/3 * (q1.x - q0.x)),
			y: round(q0.y + 2/3 * (q1.y - q0.y))
		};
		var p2 = {
			x: round(q2.x + 2/3 * (q1.x - q2.x)),
			y: round(q2.y + 2/3 * (q1.y - q2.y))
		};
		// Replace the single off-curve with two curve nodes
		nodes.splice(seg.offIdx, 1,
			{ type: 'curve', smooth: false, x: p1.x, y: p1.y },
			{ type: 'curve', smooth: false, x: p2.x, y: p2.y }
		);
	}

	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// Convert cubic segment to quadratic bezier.
// Approximation: Q1 = (3*(P1+P2) - (P0+P3)) / 4
TRV.convertSegmentToQuadratic = function(hit) {
	if (!hit || !hit.contour) return;
	var nodes = hit.contour.nodes;
	var seg = hit.seg;
	if (seg.type !== 'cubic') return;

	var round = function(v) { return Math.round(v * 10) / 10; };
	var p0 = seg.pts[0], p1 = seg.pts[1], p2 = seg.pts[2], p3 = seg.pts[3];

	var q1 = {
		x: round((3 * (p1.x + p2.x) - (p0.x + p3.x)) / 4),
		y: round((3 * (p1.y + p2.y) - (p0.y + p3.y)) / 4)
	};

	// Replace two curve nodes with one off node
	// Remove in descending index order, then insert
	var idx1 = seg.offIdx1, idx2 = seg.offIdx2;
	if (idx2 === idx1 + 1) {
		nodes.splice(idx1, 2, { type: 'off', smooth: false, x: q1.x, y: q1.y });
	} else {
		// Wraparound: remove from end first, then start
		nodes.splice(idx1, nodes.length - idx1, { type: 'off', smooth: false, x: q1.x, y: q1.y });
		nodes.splice(0, idx2 + 1);
	}

	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Slide node along contour ----------------------------------------
// Hold S while dragging an on-curve node to slide it along the path
// defined by its two adjacent segments. Both segments are re-split
// at the new position using de Casteljau + least-squares fitting.

// -- Slide node along contour ----------------------------------------
// Two modes:
//   'curve' (S): slide along bezier segments only
//   'line'  (A): slide along line segments (with extrapolation beyond endpoints)
//
// Each mode only considers segment types it cares about.
// When a node connects a line and a curve, only the matching side is
// used for sliding; the other side is reconstructed via least-squares.

TRV.initSlideMode = function(nodeId, mode) {
	mode = mode || 'curve';
	var ref = TRV.findNodeById(nodeId);
	if (!ref || ref.node.type !== 'on') return null;

	var contour = ref.contour;
	var nodes = contour.nodes;
	var n = nodes.length;

	var m = nodeId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return null;
	var ci = parseInt(m[1]);
	var ni = parseInt(m[2]);

	var incoming = TRV._analyzeIncoming(nodes, n, ni);
	var outgoing = TRV._analyzeOutgoing(nodes, n, ni);

	// Determine which sides are active based on mode
	var activeIn = false, activeOut = false;
	if (mode === 'curve') {
		activeIn = (incoming.type === 'cubic');
		activeOut = (outgoing.type === 'cubic');
	} else if (mode === 'line') {
		activeIn = (incoming.type === 'line');
		activeOut = (outgoing.type === 'line');
	}

	// Need at least one active side
	if (!activeIn && !activeOut) return null;

	// Build original control points for cubic sides (needed for reconstruction)
	var inH = incoming.handleIndices;
	var outH = outgoing.handleIndices;
	var inPts = null, outPts = null;

	if (incoming.type === 'cubic' && inH.length >= 2) {
		inPts = [
			{ x: nodes[incoming.prevOnIdx].x, y: nodes[incoming.prevOnIdx].y },
			{ x: nodes[inH[inH.length - 1]].x, y: nodes[inH[inH.length - 1]].y },
			{ x: nodes[inH[0]].x, y: nodes[inH[0]].y },
			{ x: nodes[ni].x, y: nodes[ni].y }
		];
	}
	if (outgoing.type === 'cubic' && outH.length >= 2) {
		outPts = [
			{ x: nodes[ni].x, y: nodes[ni].y },
			{ x: nodes[outH[0]].x, y: nodes[outH[0]].y },
			{ x: nodes[outH[outH.length - 1]].x, y: nodes[outH[outH.length - 1]].y },
			{ x: nodes[outgoing.nextOnIdx].x, y: nodes[outgoing.nextOnIdx].y }
		];
	}

	// Endpoints for line segments
	var prevOn = { x: nodes[incoming.prevOnIdx].x, y: nodes[incoming.prevOnIdx].y };
	var onNode = { x: nodes[ni].x, y: nodes[ni].y };
	var nextOn = { x: nodes[outgoing.nextOnIdx].x, y: nodes[outgoing.nextOnIdx].y };

	// Build polyline from active sides only
	var numSamples = 60;
	var polyline = [];

	// When only one curve side is active (line-curve node), allow extrapolation.
	// Two curves: strict [0,1] to avoid boundary jitter between segments.
	var canExtrapolate = (mode === 'curve') && (activeIn !== activeOut);

	if (activeIn) {
		if (mode === 'line') {
			// Straight line: prevOn → node, extended 50% beyond each end
			for (var i = 0; i <= numSamples; i++) {
				var t = -0.5 + 2.0 * i / numSamples;
				polyline.push({
					x: prevOn.x + t * (onNode.x - prevOn.x),
					y: prevOn.y + t * (onNode.y - prevOn.y),
					seg: 0, t: t
				});
			}
		} else {
			// Cubic: extend range if single active side
			var tMin = canExtrapolate ? -0.4 : 0;
			var tMax = canExtrapolate ? 1.4 : 1;
			for (var i = 0; i <= numSamples; i++) {
				var t = tMin + (tMax - tMin) * i / numSamples;
				var pt = TRV._sampleCubic(inPts[0], inPts[1], inPts[2], inPts[3], t);
				polyline.push({ x: pt.x, y: pt.y, seg: 0, t: t });
			}
		}
	}

	if (activeOut) {
		var skip = (activeIn) ? 1 : 0; // skip junction duplicate
		if (mode === 'line') {
			for (var i = skip; i <= numSamples; i++) {
				var t = -0.5 + 2.0 * i / numSamples;
				polyline.push({
					x: onNode.x + t * (nextOn.x - onNode.x),
					y: onNode.y + t * (nextOn.y - onNode.y),
					seg: 1, t: t
				});
			}
		} else {
			// Cubic: extend range if single active side
			var tMin = canExtrapolate ? -0.4 : 0;
			var tMax = canExtrapolate ? 1.4 : 1;
			for (var i = skip; i <= numSamples; i++) {
				var t = tMin + (tMax - tMin) * i / numSamples;
				var pt = TRV._sampleCubic(outPts[0], outPts[1], outPts[2], outPts[3], t);
				polyline.push({ x: pt.x, y: pt.y, seg: 1, t: t });
			}
		}
	}

	if (polyline.length < 2) return null;

	// Arc-length parameterize
	var arcLens = [0];
	for (var i = 1; i < polyline.length; i++) {
		var dx = polyline[i].x - polyline[i - 1].x;
		var dy = polyline[i].y - polyline[i - 1].y;
		arcLens.push(arcLens[i - 1] + Math.sqrt(dx * dx + dy * dy));
	}

	return {
		contour: contour,
		nodeIdx: ni,
		ci: ci,
		mode: mode,
		incoming: incoming,
		outgoing: outgoing,
		activeIn: activeIn,
		activeOut: activeOut,
		inPts: inPts,
		outPts: outPts,
		prevOn: prevOn,
		onNode: onNode,
		nextOn: nextOn,
		inHandleIndices: inH,
		outHandleIndices: outH,
		polyline: polyline,
		arcLens: arcLens,
		totalLen: arcLens[arcLens.length - 1],
		canExtrapolate: canExtrapolate
	};
};

// Project glyph point onto the slide polyline.
TRV._projectOntoSlidePolyline = function(slideData, gx, gy) {
	var poly = slideData.polyline;
	var bestDist = Infinity;
	var bestIdx = 0;

	for (var i = 0; i < poly.length; i++) {
		var dx = poly[i].x - gx, dy = poly[i].y - gy;
		var d = dx * dx + dy * dy;
		if (d < bestDist) { bestDist = d; bestIdx = i; }
	}

	// Refine between adjacent vertices
	var lo = Math.max(0, bestIdx - 1);
	var hi = Math.min(poly.length - 1, bestIdx + 1);
	var bestFrac = bestIdx;
	bestDist = Infinity;
	for (var f = lo; f <= hi; f += 0.05) {
		var fi = Math.floor(f);
		var ff = f - fi;
		if (fi >= poly.length - 1) { fi = poly.length - 2; ff = 1; }
		var px = poly[fi].x + ff * (poly[fi + 1].x - poly[fi].x);
		var py = poly[fi].y + ff * (poly[fi + 1].y - poly[fi].y);
		var dx = px - gx, dy = py - gy;
		var d = dx * dx + dy * dy;
		if (d < bestDist) { bestDist = d; bestFrac = f; }
	}

	var fi = Math.floor(bestFrac);
	var ff = bestFrac - fi;
	if (fi >= poly.length - 1) { fi = poly.length - 2; ff = 1; }
	var p = poly[fi], pn = poly[fi + 1];

	var seg, t;
	if (p.seg === pn.seg) {
		seg = p.seg;
		t = p.t + ff * (pn.t - p.t);
	} else {
		if (ff < 0.5) { seg = p.seg; t = p.t; }
		else { seg = pn.seg; t = pn.t; }
	}

	// No clamping here — polyline range controls bounds,
	// performSlide handles in-range vs extrapolated

	// Evaluate exact position
	var pt;
	if (seg === 0) {
		if (slideData.mode === 'line' && slideData.activeIn) {
			pt = TRV._sampleLine(slideData.prevOn, slideData.onNode, t);
		} else if (slideData.inPts) {
			pt = TRV._sampleCubic(slideData.inPts[0], slideData.inPts[1], slideData.inPts[2], slideData.inPts[3], t);
		} else {
			pt = { x: poly[fi].x + ff * (pn.x - poly[fi].x), y: poly[fi].y + ff * (pn.y - poly[fi].y) };
		}
	} else {
		if (slideData.mode === 'line' && slideData.activeOut) {
			pt = TRV._sampleLine(slideData.onNode, slideData.nextOn, t);
		} else if (slideData.outPts) {
			pt = TRV._sampleCubic(slideData.outPts[0], slideData.outPts[1], slideData.outPts[2], slideData.outPts[3], t);
		} else {
			pt = { x: poly[fi].x + ff * (pn.x - poly[fi].x), y: poly[fi].y + ff * (pn.y - poly[fi].y) };
		}
	}

	return { seg: seg, t: t, x: pt.x, y: pt.y };
};

// Perform the slide: move node, reconstruct handles on both sides.
TRV.performSlide = function(slideData, gx, gy) {
	var proj = TRV._projectOntoSlidePolyline(slideData, gx, gy);
	var nodes = slideData.contour.nodes;
	var round = function(v) { return Math.round(v * 10) / 10; };
	var ni = slideData.nodeIdx;
	var inH = slideData.inHandleIndices;
	var outH = slideData.outHandleIndices;

	// Move node to projected position
	nodes[ni].x = round(proj.x);
	nodes[ni].y = round(proj.y);
	var newNode = { x: proj.x, y: proj.y };

	// -- LINE mode: just move the on-curve, nothing else --
	if (slideData.mode === 'line') {
		return;
	}

	// -- CURVE mode: de Casteljau for all t values --
	// Works for extrapolated t too — pure polynomial math
	if (slideData.mode === 'curve') {
		var t = proj.t;

		// Two curves: clamp to safe range (no extrapolation allowed)
		if (!slideData.canExtrapolate) {
			t = Math.max(0.02, Math.min(0.98, t));
		}

		if (proj.seg === 0 && slideData.inPts) {
			// De Casteljau works for any t — exact even when extrapolated
			var split = TRV._splitCubic(slideData.inPts, t);
			nodes[ni].x = round(split.left[3].x);
			nodes[ni].y = round(split.left[3].y);
			newNode = { x: split.left[3].x, y: split.left[3].y };

			nodes[inH[inH.length - 1]].x = round(split.left[1].x);
			nodes[inH[inH.length - 1]].y = round(split.left[1].y);
			nodes[inH[0]].x = round(split.left[2].x);
			nodes[inH[0]].y = round(split.left[2].y);

			// Outgoing cubic (only exists in two-curve case): combined refit
			if (slideData.outgoing.type === 'cubic' && slideData.outPts && outH.length >= 2) {
				var samples = [];
				for (var i = 0; i <= 30; i++) {
					samples.push(TRV._sampleCubic(split.right[0], split.right[1], split.right[2], split.right[3], i / 30));
				}
				for (var i = 1; i <= 30; i++) {
					samples.push(TRV._sampleCubic(slideData.outPts[0], slideData.outPts[1], slideData.outPts[2], slideData.outPts[3], i / 30));
				}
				TRV._fitSamplesToSide(nodes, outH, samples, newNode, slideData.nextOn, 'out');
			}
		} else if (proj.seg === 1 && slideData.outPts) {
			var split = TRV._splitCubic(slideData.outPts, t);
			nodes[ni].x = round(split.right[0].x);
			nodes[ni].y = round(split.right[0].y);
			newNode = { x: split.right[0].x, y: split.right[0].y };

			nodes[outH[0]].x = round(split.right[1].x);
			nodes[outH[0]].y = round(split.right[1].y);
			nodes[outH[outH.length - 1]].x = round(split.right[2].x);
			nodes[outH[outH.length - 1]].y = round(split.right[2].y);

			// Incoming cubic (only exists in two-curve case): combined refit
			if (slideData.incoming.type === 'cubic' && slideData.inPts && inH.length >= 2) {
				var samples = [];
				for (var i = 0; i <= 30; i++) {
					samples.push(TRV._sampleCubic(slideData.inPts[0], slideData.inPts[1], slideData.inPts[2], slideData.inPts[3], i / 30));
				}
				for (var i = 1; i <= 30; i++) {
					samples.push(TRV._sampleCubic(split.left[0], split.left[1], split.left[2], split.left[3], i / 30));
				}
				TRV._fitSamplesToSide(nodes, inH, samples, slideData.prevOn, newNode, 'in');
			}
		}
		return;
	}

};

// Fit a set of samples into a cubic between startPt and endPt,
// then assign the result to the handle nodes.
TRV._fitSamplesToSide = function(nodes, handleIndices, samples, startPt, endPt, direction) {
	if (samples.length < 4) return;

	var params = TRV._arcLengthParameterize(samples);
	var fit = TRV._fitCubicUnconstrained(samples, params, startPt, endPt);
	for (var iter = 0; iter < 3; iter++) {
		params = TRV._reparameterize(samples, params, startPt, fit.P1, fit.P2, endPt);
		fit = TRV._fitCubicUnconstrained(samples, params, startPt, endPt);
	}

	if (direction === 'in') {
		// incoming handleIndices: [0] = closer to node, [last] = closer to prevOn
		nodes[handleIndices[handleIndices.length - 1]].x = fit.P1.x;
		nodes[handleIndices[handleIndices.length - 1]].y = fit.P1.y;
		nodes[handleIndices[0]].x = fit.P2.x;
		nodes[handleIndices[0]].y = fit.P2.y;
	} else {
		// outgoing handleIndices: [0] = closer to node, [last] = closer to nextOn
		nodes[handleIndices[0]].x = fit.P1.x;
		nodes[handleIndices[0]].y = fit.P1.y;
		nodes[handleIndices[handleIndices.length - 1]].x = fit.P2.x;
		nodes[handleIndices[handleIndices.length - 1]].y = fit.P2.y;
	}
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
					// If the line neighbor is also selected, both ends
					// move together — constraint is meaningless, skip
					if (TRV.state.selectedNodeIds.has(lineId)) continue;
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
		TRV.clearUndo();
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
