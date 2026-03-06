// ===================================================================
// TypeRig Glyph Viewer — Event Handlers
// ===================================================================
// DOM event wiring. Key/toolbar bindings defined in bindings.js.
// ===================================================================
'use strict';

(function() {

const state = TRV.state;
const dom = TRV.dom;

// -- Helpers for multi-view coordinate handling ----------------------

// Which cell was clicked (split or joined)
function getCellAtScreen(sx, sy) {
	if (!state.multiView) return null;
	if (state.joinedView) return TRV.getJoinedCellAt(sx, sy);
	return TRV.getCellAt(sx, sy);
}

// Get screen coords suitable for hit testing in active cell.
// Split mode: cell-relative. Joined/single/strip: absolute.
function interactionCoords(sx, sy) {
	if (state.multiView && !state.joinedView && !state.glyphViewMode) {
		const cell = TRV.getCellRect(state.activeCell.row, state.activeCell.col);
		return { sx: sx - cell.x, sy: sy - cell.y };
	}
	return { sx: sx, sy: sy };
}

// Execute fn with pan shifted for active cell (joined/strip mode)
function withActiveOffset(fn) {
	if (state.glyphViewMode && TRV.font) {
		TRV.withStripOffset(state.activeCell.row, state.activeCell.col, fn);
	} else if (state.multiView && state.joinedView) {
		TRV.withJoinedOffset(state.activeCell.row, state.activeCell.col, fn);
	} else {
		fn();
	}
}

// ===================================================================
// Mouse: click, drag, selection, pan
// ===================================================================
dom.canvasWrap.addEventListener('mousedown', function(e) {
	if (e.button !== 0) return;

	const rect = dom.canvas.getBoundingClientRect();
	const absSx = e.clientX - rect.left;
	const absSy = e.clientY - rect.top;

	// -- Spacebar held -> pan mode
	if (state.spaceDown) {
		state.isPanning = true;
		state.lastMouse = { x: e.clientX, y: e.clientY };
		dom.canvasWrap.style.cursor = 'grabbing';
		return;
	}

	// -- Glyph strip: click to switch glyph or layer cell
	if (state.glyphViewMode && TRV.font) {
		var stripHit = TRV.getStripSlotAt(absSx, absSy);
		if (stripHit) {
			// Check close button on non-active slots
			if (!stripHit.slot.active && TRV.workspace._closeRects) {
				var cr = TRV.workspace._closeRects[stripHit.slot.name];
				if (cr && absSx >= cr.x && absSx <= cr.x + cr.w &&
					absSy >= cr.y && absSy <= cr.y + cr.h) {
					TRV.removeGlyphFromStrip(stripHit.slot.name);
					TRV.updateGlyphPanelActive();
					return;
				}
			}

			if (stripHit.slot.active) {
				// Clicked active glyph — switch layer cell if different
				if (stripHit.row !== state.activeCell.row || stripHit.col !== state.activeCell.col) {
					TRV.setActiveCell(stripHit.row, stripHit.col);
				}
			} else {
				// Clicked non-active glyph — switch to it
				TRV.switchGlyph(stripHit.slot.name);
				return;
			}
		}
	}

	// -- Multi-view: switch active cell on click
	if (state.multiView && !state.glyphViewMode) {
		const clicked = getCellAtScreen(absSx, absSy);
		if (clicked && (clicked.row !== state.activeCell.row || clicked.col !== state.activeCell.col)) {
			TRV.setActiveCell(clicked.row, clicked.col);
		}
	}

	// Interaction coords (cell-relative in split, absolute in joined/single)
	const { sx, sy } = interactionCoords(absSx, absSy);

	// -- Check node hit (with pan offset in joined mode)
	if (state.showNodes) {
		let hit = null;
		withActiveOffset(function() {
			hit = TRV.hitTestNode(sx, sy);
		});
		if (hit) {
			if (e.shiftKey) {
				TRV.selectNode(hit.id, true);
			} else if (!state.selectedNodeIds.has(hit.id)) {
				TRV.selectNode(hit.id, false);
			}
			startDrag(sx, sy, e);
			return;
		}

		// -- Check segment hit: grab cubic segments for direct manipulation
		let segHit = null;
		withActiveOffset(function() {
			segHit = TRV.hitTestSegment(sx, sy);
		});
		if (segHit && segHit.seg.type === 'cubic') {
			let gp;
			withActiveOffset(function() { gp = TRV.screenToGlyph(sx, sy); });

			// Select the segment's nodes
			var seg = segHit.seg;
			var ci = segHit.ci;
			var ids = [
				'c' + ci + '_n' + seg.startIdx,
				'c' + ci + '_n' + seg.endIdx,
				'c' + ci + '_n' + seg.offIdx1,
				'c' + ci + '_n' + seg.offIdx2
			];
			TRV.selectNodes(ids, e.shiftKey);

			// Bernstein basis values at hit t
			var t = segHit.t;
			var u = 1 - t;
			var B1 = 3 * u * u * t;
			var B2 = 3 * u * t * t;
			var denom = B1 * B1 + B2 * B2;

			TRV.pushUndo();
			state.isDragging = true;
			state.segmentDrag = {
				ci: ci,
				seg: seg,
				t: t,
				B1: B1,
				B2: B2,
				denom: denom,
				h1Id: 'c' + ci + '_n' + seg.offIdx1,
				h2Id: 'c' + ci + '_n' + seg.offIdx2,
				h1Start: { x: segHit.contour.nodes[seg.offIdx1].x, y: segHit.contour.nodes[seg.offIdx1].y },
				h2Start: { x: segHit.contour.nodes[seg.offIdx2].x, y: segHit.contour.nodes[seg.offIdx2].y }
			};
			state.dragOriginGlyph = { x: gp.x, y: gp.y };
			dom.canvasWrap.style.cursor = 'move';
			return;
		}

		// Quadratic segment click: select all 3 nodes (no drag-reshape)
		if (segHit && segHit.seg.type === 'quadratic') {
			var seg = segHit.seg;
			var ci = segHit.ci;
			var ids = [
				'c' + ci + '_n' + seg.startIdx,
				'c' + ci + '_n' + seg.endIdx,
				'c' + ci + '_n' + seg.offIdx
			];
			TRV.selectNodes(ids, e.shiftKey);
			return;
		}
	}

	// -- Check anchor hit
	if (state.showAnchors) {
		let anchorIdx = null;
		withActiveOffset(function() {
			anchorIdx = TRV.hitTestAnchor(sx, sy);
		});
		if (anchorIdx !== null) {
			TRV.pushUndo();
			state.isDragging = true;
			state.dragAnchorIdx = anchorIdx;
			let gp;
			withActiveOffset(function() { gp = TRV.screenToGlyph(sx, sy); });
			state.dragOriginGlyph = { x: gp.x, y: gp.y };
			dom.canvasWrap.style.cursor = 'move';
			return;
		}
	}

	// -- No node hit: begin selection mode
	// Skip if this is the second click of a double-click (let dblclick handle it)
	if (e.detail >= 2) return;

	if (e.altKey) {
		// Alt+drag: lasso selection
		state.isSelecting = true;
		state.selectMode = 'lasso';
		state.selectLassoPoints = [{ x: sx, y: sy }];
		dom.canvasWrap.style.cursor = 'default';
	} else {
		// Plain drag on empty: rect selection
		state.isSelecting = true;
		state.selectMode = 'rect';
		state.selectStartScreen = { x: sx, y: sy };
		state.selectCurrentScreen = { x: sx, y: sy };
		dom.canvasWrap.style.cursor = 'crosshair';
	}

	// Clear existing selection unless shift held
	if (!e.shiftKey) {
		state.selectedNodeIds.clear();
		TRV.draw();
		TRV.updateStatusSelected();
	}
});

function startDrag(sx, sy, e) {
	TRV.pushUndo();
	let gp;
	withActiveOffset(function() { gp = TRV.screenToGlyph(sx, sy); });
	state.isDragging = true;
	state.dragOriginGlyph = { x: gp.x, y: gp.y };

	// Alt+drag: move on-curve only, handles stay put
	state.dragAltMode = !!(e && e.altKey);

	// Save start positions for all selected nodes
	state.dragStartPositions = new Map();
	for (const nodeId of state.selectedNodeIds) {
		const ref = TRV.findNodeById(nodeId);
		if (ref) {
			state.dragStartPositions.set(nodeId, { x: ref.node.x, y: ref.node.y });
		}
	}

	// Add follower handles unless Alt is held (detached mode)
	if (!state.dragAltMode) {
		var followers = TRV.getFollowerHandles(state.selectedNodeIds);
		for (const [id, pos] of followers) {
			if (!state.dragStartPositions.has(id)) {
				state.dragStartPositions.set(id, { x: pos.x, y: pos.y });
			}
		}
	}

	// Compute tangent constraints for smooth on-curves
	state.dragTangents = TRV.computeDragTangents(state.dragStartPositions);

	// Slide mode: if S/A/E is already held, initialize slide
	state.slideData = null;
	if (state.selectedNodeIds.size === 1) {
		var slideNodeId = state.selectedNodeIds.values().next().value;
		if (state.sKeyDown) {
			state.slideData = TRV.initSlideMode(slideNodeId, 'curve');
		} else if (state.aKeyDown) {
			state.slideData = TRV.initSlideMode(slideNodeId, 'line');
		}
	}

	dom.canvasWrap.style.cursor = 'move';
}

window.addEventListener('mousemove', function(e) {
	const rect = dom.canvas.getBoundingClientRect();
	const absSx = e.clientX - rect.left;
	const absSy = e.clientY - rect.top;

	// Preview mode: track cursor for proximity-reveal nodes
	state.previewMouse = { x: absSx, y: absSy };

	const { sx, sy } = interactionCoords(absSx, absSy);

	// Cursor position in glyph coords (offset-aware)
	let gp;
	withActiveOffset(function() { gp = TRV.screenToGlyph(sx, sy); });
	dom.statusCursor.textContent = Math.round(gp.x) + ', ' + Math.round(gp.y);

	// -- Rect selection
	if (state.isSelecting && state.selectMode === 'rect') {
		state.selectCurrentScreen = { x: sx, y: sy };

		let ids;
		withActiveOffset(function() {
			ids = TRV.hitTestRect(
				state.selectStartScreen.x, state.selectStartScreen.y,
				sx, sy
			);
		});
		if (!e.shiftKey) state.selectedNodeIds.clear();
		for (const id of ids) state.selectedNodeIds.add(id);

		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// -- Lasso selection
	if (state.isSelecting && state.selectMode === 'lasso') {
		state.selectLassoPoints.push({ x: sx, y: sy });

		let ids;
		withActiveOffset(function() {
			ids = TRV.hitTestLasso(state.selectLassoPoints);
		});
		if (!e.shiftKey) state.selectedNodeIds.clear();
		for (const id of ids) state.selectedNodeIds.add(id);

		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// -- Segment drag: reshape curve by distributing delta to handles
	if (state.isDragging && state.segmentDrag) {
		withActiveOffset(function() {
			const dgp = TRV.screenToGlyph(sx, sy);
			var dx = dgp.x - state.dragOriginGlyph.x;
			var dy = dgp.y - state.dragOriginGlyph.y;

			// Shift constraint: lock to dominant axis
			if (e.shiftKey) {
				if (Math.abs(dx) > Math.abs(dy)) dy = 0;
				else dx = 0;
			}

			var sd = state.segmentDrag;
			// Distribute delta to handles weighted by Bernstein basis
			var w1 = sd.B1 / sd.denom;
			var w2 = sd.B2 / sd.denom;

			TRV.updateNodePosition(sd.h1Id, sd.h1Start.x + dx * w1, sd.h1Start.y + dy * w1);
			TRV.updateNodePosition(sd.h2Id, sd.h2Start.x + dx * w2, sd.h2Start.y + dy * w2);

			// Enforce collinearity on smooth nodes at segment endpoints
			var movedHandles = new Set([sd.h1Id, sd.h2Id]);
			TRV.enforceSmoothCollinearity(movedHandles);
		});

		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// -- Anchor drag
	if (state.isDragging && state.dragAnchorIdx !== null) {
		withActiveOffset(function() {
			var gp = TRV.screenToGlyph(sx, sy);
			var layer = TRV.getActiveLayer();
			if (layer && layer.anchors && layer.anchors[state.dragAnchorIdx]) {
				var a = layer.anchors[state.dragAnchorIdx];
				// Shift constraint: lock to axis
				if (e.shiftKey) {
					var dx = Math.abs(gp.x - state.dragOriginGlyph.x);
					var dy = Math.abs(gp.y - state.dragOriginGlyph.y);
					if (dx > dy) gp.y = state.dragOriginGlyph.y;
					else gp.x = state.dragOriginGlyph.x;
				}
				a.x = Math.round(gp.x);
				a.y = Math.round(gp.y);
			}
		});
		TRV.draw();
		return;
	}

// -- Node drag (moves all selected + follower handles)
	// No XML sync during drag — canvas is source of truth
	if (state.isDragging && state.dragStartPositions) {
		withActiveOffset(function() {
			const dgp = TRV.screenToGlyph(sx, sy);

			// Slide mode: S held, project node along contour
			if (state.slideData) {
				TRV.performSlide(state.slideData, dgp.x, dgp.y);
				return;
			}

			var dx = dgp.x - state.dragOriginGlyph.x;
			var dy = dgp.y - state.dragOriginGlyph.y;

			// Shift constraint: lock to dominant axis
			if (e.shiftKey) {
				if (Math.abs(dx) > Math.abs(dy)) dy = 0;
				else dx = 0;
			}

			// Position all nodes absolutely (selected + followers)
			for (const [nodeId, startPos] of state.dragStartPositions) {
				var effDx = dx, effDy = dy;

				// Constrained smooth: project onto tangent direction
				// locked tangents (line-curve) always active; free tangents (curve-curve) need Ctrl
				var tan = state.dragTangents ? state.dragTangents.get(nodeId) : null;
				if (tan && (tan.locked || e.ctrlKey || e.metaKey)) {
					var proj = TRV.projectOntoTangent(dx, dy, tan);
					effDx = proj.dx;
					effDy = proj.dy;
				}

				TRV.updateNodePosition(nodeId, startPos.x + effDx, startPos.y + effDy);
			}

			// Follower handles of constrained nodes need the same projected delta
			if (state.dragTangents && state.dragTangents.size > 0) {
				for (const [onId, tangent] of state.dragTangents) {
					if (!tangent.locked && !e.ctrlKey && !e.metaKey) continue;
					var proj = TRV.projectOntoTangent(dx, dy, tangent);
					// Find follower handles for this on-curve and reposition them
					var m = onId.match(/^c(\d+)_n(\d+)$/);
					if (!m) continue;
					var ci = parseInt(m[1]), ni = parseInt(m[2]);
					var ref = TRV.findNodeById(onId);
					if (!ref) continue;
					var nodes = ref.contour.nodes;
					var n = nodes.length;
					var prevId = 'c' + ci + '_n' + ((ni - 1 + n) % n);
					var nextId = 'c' + ci + '_n' + ((ni + 1) % n);
					// Only reposition if they're followers (in dragStartPositions but not selected)
					if (state.dragStartPositions.has(prevId) && !state.selectedNodeIds.has(prevId)) {
						var sp = state.dragStartPositions.get(prevId);
						TRV.updateNodePosition(prevId, sp.x + proj.dx, sp.y + proj.dy);
					}
					if (state.dragStartPositions.has(nextId) && !state.selectedNodeIds.has(nextId)) {
						var sp = state.dragStartPositions.get(nextId);
						TRV.updateNodePosition(nextId, sp.x + proj.dx, sp.y + proj.dy);
					}
				}
			}

			// Enforce collinearity on smooth nodes (skip in Alt mode)
			if (!state.dragAltMode) {
				var allMoved = new Set(state.dragStartPositions.keys());
				TRV.enforceSmoothCollinearity(allMoved);
			}
		});

		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// -- Pan
	if (state.isPanning) {
		const dsx = e.clientX - state.lastMouse.x;
		const dsy = e.clientY - state.lastMouse.y;
		state.pan.x += dsx;
		state.pan.y += dsy;
		state.lastMouse = { x: e.clientX, y: e.clientY };
		TRV.draw();
		return;
	}

	// Preview mode / stem measurement: redraw on hover
	if (state.previewMode || state.showStem) {
		TRV.draw();
	}

	// -- Hover cursor hint
	if (!state.spaceDown) {
		let cursor = 'default';
		if (state.showNodes) {
			let hit = null;
			withActiveOffset(function() { hit = TRV.hitTestNode(sx, sy); });
			if (hit) cursor = 'move';
		}
		if (cursor === 'default' && state.showAnchors) {
			let aHit = null;
			withActiveOffset(function() { aHit = TRV.hitTestAnchor(sx, sy); });
			if (aHit !== null) cursor = 'move';
		}
		dom.canvasWrap.style.cursor = cursor;
	}
});

window.addEventListener('mouseup', function(e) {
	// -- Finalize rect selection
	if (state.isSelecting && state.selectMode === 'rect') {
		let ids;
		withActiveOffset(function() {
			ids = TRV.hitTestRect(
				state.selectStartScreen.x, state.selectStartScreen.y,
				state.selectCurrentScreen.x, state.selectCurrentScreen.y
			);
		});

		// Clear overlay state BEFORE draw so it disappears
		state.isSelecting = false;
		state.selectMode = null;
		state.selectStartScreen = null;
		state.selectCurrentScreen = null;

		TRV.selectNodes(ids, e.shiftKey);
		TRV.updateCanvasCursor();
		return;
	}

	// -- Finalize lasso selection
	if (state.isSelecting && state.selectMode === 'lasso') {
		let ids;
		withActiveOffset(function() {
			ids = TRV.hitTestLasso(state.selectLassoPoints);
		});

		// Clear overlay state BEFORE draw
		state.isSelecting = false;
		state.selectMode = null;
		state.selectLassoPoints = [];

		TRV.selectNodes(ids, e.shiftKey);
		TRV.updateCanvasCursor();
		return;
	}

	// -- Finalize drag (no XML sync — user clicks Refresh when needed)
	if (state.isDragging) {
		// Try joining open endpoints after drag (skip for anchors)
		if (state.dragAnchorIdx === null) TRV.tryJoinEndpoints();

		state.isDragging = false;
		state.dragStartPositions = null;
		state.dragOriginGlyph = null;
		state.dragAltMode = false;
		state.dragTangents = null;
		state.slideData = null;
		state.segmentDrag = null;
		state.dragAnchorIdx = null;
	}

	if (state.isPanning) {
		state.isPanning = false;
	}

	TRV.updateCanvasCursor();
});

// ===================================================================
// Double-click: select all nodes on clicked contour
// ===================================================================
dom.canvasWrap.addEventListener('dblclick', function(e) {
	const rect = dom.canvas.getBoundingClientRect();
	const absSx = e.clientX - rect.left;
	const absSy = e.clientY - rect.top;
	const { sx, sy } = interactionCoords(absSx, absSy);

	// Double-click on a node: select whole contour (existing behavior)
	var nodeHit = null;
	withActiveOffset(function() {
		nodeHit = TRV.hitTestNode(sx, sy);
	});

	if (nodeHit) {
		var ci = -1;
		withActiveOffset(function() {
			ci = TRV.hitTestContour(sx, sy);
		});
		if (ci >= 0) {
			var ids = TRV.getContourNodeIds(ci);
			TRV.selectNodes(ids, e.shiftKey);
		}
		return;
	}

	// Double-click on a segment: select that segment's nodes
	var segHit = null;
	withActiveOffset(function() {
		segHit = TRV.hitTestSegment(sx, sy);
	});

	if (segHit) {
		var seg = segHit.seg;
		var ci = segHit.ci;
		var ids = ['c' + ci + '_n' + seg.startIdx, 'c' + ci + '_n' + seg.endIdx];
		if (seg.type === 'cubic') {
			ids.push('c' + ci + '_n' + seg.offIdx1);
			ids.push('c' + ci + '_n' + seg.offIdx2);
		} else if (seg.type === 'quadratic') {
			ids.push('c' + ci + '_n' + seg.offIdx);
		}
		TRV.selectNodes(ids, e.shiftKey);
		return;
	}

	// Fallback: try contour hit
	var ci = -1;
	withActiveOffset(function() {
		ci = TRV.hitTestContour(sx, sy);
	});
	if (ci >= 0) {
		var ids = TRV.getContourNodeIds(ci);
		TRV.selectNodes(ids, e.shiftKey);
	}
});

// ===================================================================
// Scroll wheel: zoom / ribbon rotation
// ===================================================================
dom.canvasWrap.addEventListener('wheel', function(e) {
	e.preventDefault();

	const rect = dom.canvas.getBoundingClientRect();
	const absSx = e.clientX - rect.left;
	const absSy = e.clientY - rect.top;

	// Normal zoom (centred on cursor)
	const { sx: mx, sy: my } = interactionCoords(absSx, absSy);
	const factor = e.deltaY > 0 ? TRV.WHEEL_ZOOM_OUT : TRV.WHEEL_ZOOM_IN;
	const newZoom = state.zoom * factor;

	state.pan.x = mx - (mx - state.pan.x) * (newZoom / state.zoom);
	state.pan.y = my - (my - state.pan.y) * (newZoom / state.zoom);
	state.zoom = newZoom;

	TRV.updateZoomStatus();
	TRV.draw();
}, { passive: false });

// ===================================================================
// Resize
// ===================================================================
const resizeObserver = new ResizeObserver(function() { TRV.draw(); });
resizeObserver.observe(dom.canvasWrap);

// ===================================================================
// Toolbar: special buttons (exclusive pairs, panels, view modes)
// Simple toggle/action buttons are wired via TRV.wireToolbar().
// ===================================================================

// Fill / Outline (exclusive pair)
document.getElementById('btn-filled').addEventListener('click', function() {
	state.filled = true;
	this.classList.add('active');
	document.getElementById('btn-outline').classList.remove('active');
	TRV.draw();
});

document.getElementById('btn-outline').addEventListener('click', function() {
	state.filled = false;
	this.classList.add('active');
	document.getElementById('btn-filled').classList.remove('active');
	TRV.draw();
});

// XML panel (has panel show/hide logic)
document.getElementById('btn-panel').addEventListener('click', function() {
	state.showXml = !state.showXml;
	this.classList.toggle('active');

	const panel = dom.sidePanel;

	if (state.showXml) {
		const mainWidth = dom.main.clientWidth;
		panel.style.width = Math.round(mainWidth * 0.4) + 'px';
		panel.classList.add('visible');
		dom.splitHandle.classList.add('visible');
	} else {
		panel.classList.remove('visible');
		dom.splitHandle.classList.remove('visible');
		panel.style.width = '';
	}

	requestAnimationFrame(function() {
		TRV.draw();
		if (state.showXml && state.activePanel === 'xml') TRV.buildXmlPanel();
	});
});

// -- View mode buttons (1x1, 2x1, 2x2) -----------------------------
function setViewMode(cols, rows) {
	const btn1x1 = document.getElementById('btn-view-1x1');
	const btn2x1 = document.getElementById('btn-view-2x1');
	const btn2x2 = document.getElementById('btn-view-2x2');

	btn1x1.classList.remove('active');
	btn2x1.classList.remove('active');
	btn2x2.classList.remove('active');

	state.gridCols = cols;
	state.gridRows = rows;

	if (state.glyphViewMode) {
		// Strip mode: grid size controls active glyph expansion
		state.multiView = (cols > 1 || rows > 1);
		state.activeCell = { row: 0, col: 0 };
		// Force gridLayers rebuild on next draw
		state.gridLayers = null;
	} else if (cols === 1 && rows === 1) {
		state.multiView = false;
		state.gridLayers = null;
	} else {
		state.multiView = true;
		TRV.initMultiGrid();
	}

	if (cols === 1 && rows === 1) btn1x1.classList.add('active');
	if (cols === 2 && rows === 1) btn2x1.classList.add('active');
	if (cols === 2 && rows === 2) btn2x2.classList.add('active');

	TRV.fitToView();
}

document.getElementById('btn-view-1x1').addEventListener('click', function() { setViewMode(1, 1); });
document.getElementById('btn-view-2x1').addEventListener('click', function() { setViewMode(2, 1); });
document.getElementById('btn-view-2x2').addEventListener('click', function() { setViewMode(2, 2); });

// -- Join toggle (split vs joined canvas) ---------------------------
document.getElementById('btn-join').addEventListener('click', function() {
	// If glyph mode is active, clicking Join exits glyph mode
	if (state.glyphViewMode) {
		state.glyphViewMode = false;
		document.getElementById('btn-glyph-view').classList.remove('active');
		TRV.updateGlyphPanelActive();
	}

	state.joinedView = !state.joinedView;
	this.classList.toggle('active', state.joinedView);

	// Auto-enable multi-view if not active
	if (state.joinedView && !state.multiView) {
		setViewMode(2, 1);
	}

	TRV.fitToView();
});

// -- Glyph view toggle (glyph strip on shared baseline) -------------
document.getElementById('btn-glyph-view').addEventListener('click', function() {
	if (!TRV.font) return;

	state.glyphViewMode = !state.glyphViewMode;
	this.classList.toggle('active', state.glyphViewMode);

	if (state.glyphViewMode) {
		// Enter strip mode with 1x1 (no layer expansion)
		state.gridCols = 1;
		state.gridRows = 1;
		state.multiView = false;
		state.gridLayers = null;
		state.activeCell = { row: 0, col: 0 };

		// Update view buttons
		document.getElementById('btn-view-1x1').classList.add('active');
		document.getElementById('btn-view-2x1').classList.remove('active');
		document.getElementById('btn-view-2x2').classList.remove('active');

		TRV.updateWorkspaceStrip();
		TRV.fitGlyphStrip();
	} else {
		// Exit strip mode
		state.gridLayers = null;
		TRV.fitToView();
	}

	TRV.updateGlyphPanelActive();
	TRV.draw();
});

// -- Layer dropdown -------------------------------------------------
dom.layerSelect.addEventListener('change', function() {
	state.activeLayer = this.value;
	state.selectedNodeIds.clear();

	// In multi-view or expanded strip, update the active cell's gridLayers
	if (state.gridLayers && state.glyphData) {
		if (!TRV.isMaskLayer(this.value)) {
			var layers = state.glyphData.layers;
			var idx = -1;
			for (var i = 0; i < layers.length; i++) {
				if (layers[i].name === this.value) { idx = i; break; }
			}
			if (idx >= 0) {
				var r = state.activeCell.row;
				var c = state.activeCell.col;
				if (state.gridLayers[r] && state.gridLayers[r][c] !== undefined) {
					state.gridLayers[r][c] = idx;
				}
			}
		}
	}

	TRV.draw();
	TRV.buildXmlPanel();
});

// ===================================================================
// ===================================================================
// Glyph panel — click and search
// ===================================================================
(function() {
	var glyphList = document.getElementById('glyph-list');
	var glyphSearch = document.getElementById('glyph-search');
	var glyphCount = document.getElementById('glyph-count');

	if (glyphList) {
		// Single click: switch to glyph
		glyphList.addEventListener('click', function(e) {
			var entry = e.target.closest('.glyph-entry');
			if (!entry) return;
			var name = entry.dataset.name;
			if (name) TRV.switchGlyph(name);
		});

		// Double click: add glyph to workspace strip
		glyphList.addEventListener('dblclick', function(e) {
			var entry = e.target.closest('.glyph-entry');
			if (!entry) return;
			var name = entry.dataset.name;
			if (!name || !TRV.state.glyphViewMode) return;

			TRV.addGlyphToStrip(name);
			TRV.updateGlyphPanelActive();
		});
	}

	if (glyphSearch) {
		glyphSearch.addEventListener('input', function() {
			TRV.filterGlyphPanel(this.value);
			// Update visible count
			if (glyphCount && glyphList) {
				var visible = glyphList.querySelectorAll('.glyph-entry:not([style*="display: none"])');
				glyphCount.textContent = visible.length + '/' + (TRV.font ? TRV.font.manifest.length : 0);
			}
		});
	}
})();

// File input / Drag and drop
// ===================================================================
dom.fileInput.addEventListener('change', function(e) {
	const file = e.target.files[0];
	if (!file) return;
	const reader = new FileReader();
	reader.onload = function(ev) { TRV.loadXmlString(ev.target.result, file.name); };
	reader.readAsText(file);
	dom.fileInput.value = '';
});

document.addEventListener('dragover', function(e) {
	e.preventDefault();
	dom.dropOverlay.classList.add('visible');
});

document.addEventListener('dragleave', function(e) {
	if (e.relatedTarget === null || !document.contains(e.relatedTarget)) {
		dom.dropOverlay.classList.remove('visible');
	}
});

document.addEventListener('drop', function(e) {
	e.preventDefault();
	dom.dropOverlay.classList.remove('visible');
	const file = e.dataTransfer.files[0];
	if (!file) return;
	const reader = new FileReader();
	reader.onload = function(ev) { TRV.loadXmlString(ev.target.result, file.name); };
	reader.readAsText(file);
});

// ===================================================================
// Keyboard — dispatch via bindings.js keyMap
// ===================================================================
document.addEventListener('keydown', function(e) {
	// Backtick: preview mode (hold) - black on white, no decorations
	// Backtick + Space: toggle persistent preview lock
	if (e.code === 'Backquote' && e.target !== dom.xmlContent && e.target !== dom.pyInput) {
		if (state.spaceDown) {
			// Toggle persistent lock
			state.previewLocked = !state.previewLocked;
			state.previewMode = state.previewLocked;
			TRV.updatePreviewButton();
			TRV.draw();
		} else if (!state.previewLocked) {
			if (!state.previewMode) {
				state.previewMode = true;
				TRV.draw();
			}
		}
		e.preventDefault();
		return;
	}

	// Spacebar: panning mode (hold)
	if (e.code === 'Space' && e.target !== dom.xmlContent) {
		if (!state.spaceDown) {
			state.spaceDown = true;
			e.preventDefault();
			TRV.updateCanvasCursor();
		}
		return;
	}

	// S key: slide along curves (hold while dragging)
	if (e.code === 'KeyS' && !e.ctrlKey && !e.metaKey && e.target !== dom.xmlContent) {
		if (!state.sKeyDown) {
			state.sKeyDown = true;
			if (state.isDragging && state.selectedNodeIds.size === 1) {
				var nodeId = state.selectedNodeIds.values().next().value;
				state.slideData = TRV.initSlideMode(nodeId, 'curve');
			}
		}
		if (state.slideData) {
			e.preventDefault();
			return;
		}
	}

	// A key: slide along lines (hold while dragging)
	if (e.code === 'KeyA' && !e.ctrlKey && !e.metaKey && e.target !== dom.xmlContent) {
		if (!state.aKeyDown) {
			state.aKeyDown = true;
			if (state.isDragging && state.selectedNodeIds.size === 1) {
				var nodeId = state.selectedNodeIds.values().next().value;
				state.slideData = TRV.initSlideMode(nodeId, 'line');
			}
		}
		if (state.slideData) {
			e.preventDefault();
			return;
		}
	}

	// XML textarea: Ctrl+Enter applies, other typing is free-form
	if (e.target === dom.xmlContent) {
		if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
			e.preventDefault();
			TRV.pushUndo();
			TRV.xmlApply();
			return;
		}
		if (!(e.ctrlKey || e.metaKey)) return;
	}

	// Dispatch through key map
	TRV.dispatchKey(e);
});

document.addEventListener('keyup', function(e) {
	// Backtick released: exit preview mode (unless locked)
	if (e.code === 'Backquote') {
		if (!state.previewLocked) {
			state.previewMode = false;
			TRV.draw();
		}
		return;
	}

	if (e.code === 'Space') {
		state.spaceDown = false;
		if (state.isPanning) {
			state.isPanning = false;
		}
		TRV.updateCanvasCursor();
	}

	// S/A/E key released: exit slide mode
	if (e.code === 'KeyS') {
		state.sKeyDown = false;
		if (state.slideData && state.slideData.mode === 'curve') state.slideData = null;
	}
	if (e.code === 'KeyA') {
		state.aKeyDown = false;
		if (state.slideData && state.slideData.mode === 'line') state.slideData = null;
	}
});

// ===================================================================
// Split handle drag
// ===================================================================
(function initSplitHandle() {
	let isDragging = false;

	dom.splitHandle.addEventListener('mousedown', function(e) {
		e.preventDefault();
		isDragging = true;
		dom.splitHandle.classList.add('dragging');
		document.body.style.cursor = 'col-resize';
		document.body.style.userSelect = 'none';
	});

	window.addEventListener('mousemove', function(e) {
		if (!isDragging) return;

		const mainRect = dom.main.getBoundingClientRect();
		const panel = dom.sidePanel;

		const mouseX = e.clientX - mainRect.left;
		const panelWidth = mainRect.width - mouseX - dom.splitHandle.offsetWidth / 2;

		const minPanel = 200;
		const maxPanel = mainRect.width - minPanel - dom.splitHandle.offsetWidth;
		panel.style.width = Math.max(minPanel, Math.min(maxPanel, panelWidth)) + 'px';

		TRV.draw();
	});

	window.addEventListener('mouseup', function() {
		if (isDragging) {
			isDragging = false;
			dom.splitHandle.classList.remove('dragging');
			document.body.style.cursor = '';
			document.body.style.userSelect = '';
			TRV.draw();
		}
	});
})();

// ===================================================================
// XML panel: Refresh / Apply buttons (no live sync)
// ===================================================================
var xmlRefreshBtn = document.getElementById('xml-refresh-btn');
var xmlApplyBtn = document.getElementById('xml-apply-btn');

if (xmlRefreshBtn) {
	xmlRefreshBtn.addEventListener('click', function() {
		TRV.xmlRefresh();
	});
}

if (xmlApplyBtn) {
	xmlApplyBtn.addEventListener('click', function() {
		TRV.pushUndo();
		TRV.xmlApply();
	});
}

// XML textarea: click to highlight node on canvas (one-way)
dom.xmlContent.addEventListener('click', function() {
	var textarea = dom.xmlContent;
	var pos = textarea.selectionStart;
	var text = textarea.value.substring(0, pos);
	var lineIdx = text.split('\n').length - 1;
	var nodeId = TRV.xmlLineNodeMap[lineIdx];

	if (nodeId) {
		state.selectedNodeIds.clear();
		state.selectedNodeIds.add(nodeId);
		TRV.draw();
		TRV.updateStatusSelected();
	}
});

// ===================================================================
// Panel tabs + Python REPL
// ===================================================================
TRV.initPanelTabs();
TRV.wirePythonPanel();

// ===================================================================
// Wire simple toolbar buttons from bindings.js
// ===================================================================
TRV.wireToolbar();

// ===================================================================
// Context menu (right-click)
// ===================================================================
var ctxMenu = document.getElementById('context-menu');

function hideContextMenu() {
	if (ctxMenu) ctxMenu.classList.remove('visible');
}

// Stored segment hit for "Insert Node" action
var pendingSegmentHit = null;
var pendingContourIdx = -1;

dom.canvasWrap.addEventListener('contextmenu', function(e) {
	e.preventDefault();
	pendingSegmentHit = null;
	pendingContourIdx = -1;

	var rect = dom.canvas.getBoundingClientRect();
	var absSx = e.clientX - rect.left;
	var absSy = e.clientY - rect.top;
	var coords = interactionCoords(absSx, absSy);

	// Menu items
	var toggleItem = ctxMenu.querySelector('[data-action="toggleSmooth"]');
	var retractItem = ctxMenu.querySelector('[data-action="retractHandles"]');
	var insertItem = ctxMenu.querySelector('[data-action="insertNode"]');
	var toLineItem = ctxMenu.querySelector('[data-action="convertToLine"]');
	var toCurveItem = ctxMenu.querySelector('[data-action="convertToCurve"]');
	var toQuadItem = ctxMenu.querySelector('[data-action="convertToQuadratic"]');
	var selectContourItem = ctxMenu.querySelector('[data-action="selectContour"]');
	var joinItem = ctxMenu.querySelector('[data-action="joinContour"]');

	// Hit test: node first, then segment
	var nodeHit = null;
	var segHit = null;
	withActiveOffset(function() {
		nodeHit = TRV.hitTestNode(coords.sx, coords.sy);
		if (!nodeHit) {
			segHit = TRV.hitTestSegment(coords.sx, coords.sy);
		}
	});

	if (nodeHit) {
		// -- Right-clicked on a node --
		if (!state.selectedNodeIds.has(nodeHit.id)) {
			TRV.selectNode(nodeHit.id, false);
		}

		// Find which contour this node belongs to
		pendingContourIdx = TRV.getContourIndexForNode(nodeHit.id);

		// Show join only for open endpoints
		if (joinItem) {
			var epCheck = TRV.isOpenEndpoint(nodeHit.id);
			joinItem.style.display = epCheck ? '' : 'none';
		}

		// Show node items, hide segment items
		if (toggleItem) toggleItem.style.display = '';
		if (retractItem) retractItem.style.display = '';
		if (insertItem) insertItem.style.display = 'none';
		if (toLineItem) toLineItem.style.display = 'none';
		if (toCurveItem) toCurveItem.style.display = 'none';
		if (toQuadItem) toQuadItem.style.display = 'none';
		if (selectContourItem) selectContourItem.style.display = '';
		// Show/hide separators
		var seps = ctxMenu.querySelectorAll('.ctx-separator');
		if (seps[0]) seps[0].style.display = 'none';
		if (seps[1]) seps[1].style.display = '';
		if (seps[2]) seps[2].style.display = '';

		// Update smooth/sharp label
		if (toggleItem) {
			var hasSmooth = false, hasSharp = false;
			for (var id of state.selectedNodeIds) {
				var ref = TRV.findNodeById(id);
				if (ref && ref.node.type === 'on') {
					if (ref.node.smooth) hasSmooth = true;
					else hasSharp = true;
				}
			}
			if (hasSmooth && !hasSharp) {
				toggleItem.innerHTML = '<span class="tri">node_sharp</span>Convert to Sharp';
			} else if (hasSharp && !hasSmooth) {
				toggleItem.innerHTML = '<span class="tri">node_smooth</span>Convert to Smooth';
			} else {
				toggleItem.innerHTML = '<span class="tri">node_smooth</span>Toggle Smooth/Sharp';
			}
		}
	} else if (segHit) {
		// -- Right-clicked on a segment --
		pendingSegmentHit = segHit;

		// Show segment items, hide node items
		if (toggleItem) toggleItem.style.display = 'none';
		if (retractItem) retractItem.style.display = 'none';
		if (insertItem) insertItem.style.display = '';
		if (selectContourItem) selectContourItem.style.display = '';
		if (joinItem) joinItem.style.display = 'none';
		pendingContourIdx = segHit.ci;

		// Conversion items based on segment type
		var stype = segHit.seg.type;
		if (toLineItem) toLineItem.style.display = (stype === 'cubic' || stype === 'quadratic') ? '' : 'none';
		if (toCurveItem) toCurveItem.style.display = (stype === 'line' || stype === 'quadratic') ? '' : 'none';
		if (toQuadItem) toQuadItem.style.display = (stype === 'cubic') ? '' : 'none';

		// Separators: hide first two, show last
		var seps = ctxMenu.querySelectorAll('.ctx-separator');
		if (seps[0]) seps[0].style.display = 'none';
		if (seps[1]) seps[1].style.display = 'none';
		if (seps[2]) seps[2].style.display = '';
	} else {
		hideContextMenu();
		return;
	}

	// Position and show menu
	ctxMenu.style.left = e.clientX + 'px';
	ctxMenu.style.top = e.clientY + 'px';
	ctxMenu.classList.add('visible');

	// Clamp to viewport
	requestAnimationFrame(function() {
		var mr = ctxMenu.getBoundingClientRect();
		if (mr.right > window.innerWidth) {
			ctxMenu.style.left = (e.clientX - mr.width) + 'px';
		}
		if (mr.bottom > window.innerHeight) {
			ctxMenu.style.top = (e.clientY - mr.height) + 'px';
		}
	});
});

// Menu item click
if (ctxMenu) {
	ctxMenu.addEventListener('click', function(e) {
		var item = e.target.closest('.ctx-item');
		if (!item) return;

		var action = item.dataset.action;
		if (action === 'toggleSmooth') {
			TRV.pushUndo();
			TRV.toggleSmooth();
		} else if (action === 'retractHandles') {
			TRV.pushUndo();
			TRV.retractHandles();
		} else if (action === 'joinContour') {
			TRV.pushUndo();
			TRV.tryJoinEndpoints();
		} else if (action === 'selectContour') {
			if (pendingContourIdx >= 0) {
				var ids = TRV.getContourNodeIds(pendingContourIdx);
				TRV.selectNodes(ids, false);
				pendingContourIdx = -1;
			}
		} else if (action === 'insertNode') {
			if (pendingSegmentHit) {
				TRV.pushUndo();
				TRV.insertNodeOnSegment(pendingSegmentHit);
				pendingSegmentHit = null;
	pendingContourIdx = -1;
			}
		} else if (action === 'convertToLine') {
			if (pendingSegmentHit) {
				TRV.pushUndo();
				TRV.convertSegmentToLine(pendingSegmentHit);
				pendingSegmentHit = null;
				pendingContourIdx = -1;
			}
		} else if (action === 'convertToCurve') {
			if (pendingSegmentHit) {
				TRV.pushUndo();
				TRV.convertSegmentToCubic(pendingSegmentHit);
				pendingSegmentHit = null;
				pendingContourIdx = -1;
			}
		} else if (action === 'convertToQuadratic') {
			if (pendingSegmentHit) {
				TRV.pushUndo();
				TRV.convertSegmentToQuadratic(pendingSegmentHit);
				pendingSegmentHit = null;
				pendingContourIdx = -1;
			}
		}

		hideContextMenu();
	});
}

// Dismiss on click outside or Escape
window.addEventListener('mousedown', function(e) {
	if (ctxMenu && !ctxMenu.contains(e.target)) {
		hideContextMenu();
	}
});

document.addEventListener('keydown', function(e) {
	if (e.key === 'Escape' && ctxMenu && ctxMenu.classList.contains('visible')) {
		e.stopPropagation();
		hideContextMenu();
	}
}, true);

})();
