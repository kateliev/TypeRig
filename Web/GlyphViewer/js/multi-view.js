// ===================================================================
// TypeRig Glyph Viewer — Multi-Layer Grid View
// ===================================================================
// Two rendering modes:
//   Split  — independent clipped cells, each a mini viewport
//   Joined — layers placed side by side on a shared baseline,
//            one continuous pan/zoom space (like glyphs in a line)
//
// Ribbon rotation: Ctrl+scroll columns, Alt+scroll rows.
// Layers loop infinitely (A,B,C,A,B,C...).
// ===================================================================
'use strict';

// -- Grid initialization --------------------------------------------
TRV.initMultiGrid = function() {
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const N = state.glyphData ? state.glyphData.layers.length : 1;

	state.gridLayers = [];
	let idx = 0;
	for (let r = 0; r < rows; r++) {
		const row = [];
		for (let c = 0; c < cols; c++) {
			row.push(idx % N);
			idx++;
		}
		state.gridLayers.push(row);
	}

	state.activeCell = { row: 0, col: 0 };
	TRV.syncActiveCellToLayer();
};

// -- Cell geometry (split mode) -------------------------------------
TRV.getCellRect = function(row, col) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cols = TRV.state.gridCols;
	const rows = TRV.state.gridRows;

	return {
		x: col * (w / cols),
		y: row * (h / rows),
		w: w / cols,
		h: h / rows,
	};
};

TRV.getCellAt = function(sx, sy) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cols = TRV.state.gridCols;
	const rows = TRV.state.gridRows;

	return {
		row: Math.max(0, Math.min(rows - 1, Math.floor(sy / (h / rows)))),
		col: Math.max(0, Math.min(cols - 1, Math.floor(sx / (w / cols)))),
	};
};

// -- Active cell management -----------------------------------------
TRV.setActiveCell = function(row, col) {
	const state = TRV.state;
	state.activeCell = { row, col };
	state.selectedNodeIds.clear();
	TRV.syncActiveCellToLayer();
	TRV.draw();
	TRV.updateStatusSelected();
};

TRV.syncActiveCellToLayer = function() {
	const state = TRV.state;
	if (!state.glyphData || !state.gridLayers) return;

	const layers = state.glyphData.layers;
	const N = layers.length;
	const layerIdx = state.gridLayers[state.activeCell.row][state.activeCell.col] % N;

	state.activeLayer = layers[layerIdx].name;
	TRV.dom.layerSelect.value = layers[layerIdx].name;
};

// -- Ribbon rotation ------------------------------------------------
TRV.rotateColumn = function(col, direction) {
	const state = TRV.state;
	const N = state.glyphData ? state.glyphData.layers.length : 1;

	for (let r = 0; r < state.gridRows; r++) {
		state.gridLayers[r][col] = ((state.gridLayers[r][col] + direction) % N + N) % N;
	}

	TRV.syncActiveCellToLayer();
};

TRV.rotateRow = function(row, direction) {
	const state = TRV.state;
	const N = state.glyphData ? state.glyphData.layers.length : 1;

	for (let c = 0; c < state.gridCols; c++) {
		state.gridLayers[row][c] = ((state.gridLayers[row][c] + direction) % N + N) % N;
	}

	TRV.syncActiveCellToLayer();
};


// ===================================================================
// JOINED MODE — shared canvas, layers in glyph space
// ===================================================================

// Gap between layers in glyph units
TRV.JOINED_GAP = 80;

// -- Layout computation ---------------------------------------------
// Returns glyph-space offsets for each cell and total bounding box
TRV.getJoinedLayout = function() {
	const state = TRV.state;
	const layers = state.glyphData ? state.glyphData.layers : [];
	const cols = state.gridCols;
	const rows = state.gridRows;
	const gap = TRV.JOINED_GAP;

	// Compute actual bounding box across all layers (not just advance metrics)
	let maxW = 0, maxH = 0;
	for (const layer of layers) {
		let minX = 0, minY = 0;
		let mxX = layer.width, mxY = layer.height;

		for (const shape of layer.shapes) {
			for (const contour of shape.contours) {
				for (const node of contour.nodes) {
					minX = Math.min(minX, node.x);
					minY = Math.min(minY, node.y);
					mxX = Math.max(mxX, node.x);
					mxY = Math.max(mxY, node.y);
				}
			}
		}

		maxW = Math.max(maxW, mxX - minX);
		maxH = Math.max(maxH, mxY - minY);
	}

	// Ensure minimum cell size
	maxW = Math.max(maxW, 100);
	maxH = Math.max(maxH, 100);

	const cellW = maxW + gap;
	const cellH = maxH + gap;

	// Glyph-space offset for each cell
	// Columns go left to right (+X), rows go top to bottom
	// Row 0 = top = highest glyph Y
	const offsets = [];
	for (let r = 0; r < rows; r++) {
		const row = [];
		for (let c = 0; c < cols; c++) {
			row.push({
				gx: c * cellW,
				gy: (rows - 1 - r) * cellH,
			});
		}
		offsets.push(row);
	}

	return {
		offsets: offsets,
		totalW: cols * cellW - gap,
		totalH: rows * cellH - gap,
		cellW: cellW,
		cellH: cellH,
		maxW: maxW,
		maxH: maxH,
		gap: gap,
	};
};

// -- Execute a function with pan shifted for a cell -----------------
// All existing draw/hit-test functions use glyphToScreen which reads
// state.pan, so shifting it is sufficient to relocate a layer.
TRV.withJoinedOffset = function(row, col, fn) {
	const layout = TRV.getJoinedLayout();
	const offset = layout.offsets[row][col];
	const state = TRV.state;
	const savedX = state.pan.x;
	const savedY = state.pan.y;

	state.pan.x += offset.gx * state.zoom;
	state.pan.y -= offset.gy * state.zoom;

	fn();

	state.pan.x = savedX;
	state.pan.y = savedY;
};

// -- Determine which cell a screen point falls in (joined mode) -----
TRV.getJoinedCellAt = function(sx, sy) {
	const state = TRV.state;
	const layout = TRV.getJoinedLayout();

	// Convert screen to glyph (using base pan, no offset)
	const gp = TRV.screenToGlyph(sx, sy);

	let col = Math.floor(gp.x / layout.cellW);
	col = Math.max(0, Math.min(state.gridCols - 1, col));

	let row = (state.gridRows - 1) - Math.floor(gp.y / layout.cellH);
	row = Math.max(0, Math.min(state.gridRows - 1, row));

	return { row, col };
};

// -- Joined view drawing --------------------------------------------
TRV.drawJoinedView = function(canvasW, canvasH) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const layers = state.glyphData ? state.glyphData.layers : [];
	if (layers.length === 0) return;

	const layout = TRV.getJoinedLayout();
	const savedSelection = state.selectedNodeIds;

	for (let r = 0; r < rows; r++) {
		for (let c = 0; c < cols; c++) {
			const layerIdx = state.gridLayers[r][c] % layers.length;
			const layer = layers[layerIdx];
			const isActive = (r === state.activeCell.row && c === state.activeCell.col);

			if (!isActive) {
				state.selectedNodeIds = new Set();
			}

			// Draw with pan shifted to place this layer
			TRV.withJoinedOffset(r, c, function() {
				if (state.showMetrics) TRV.drawMetrics(layer, canvasW, canvasH);
				TRV.drawContours(layer);
				if (state.showAnchors) TRV.drawAnchors(layer);
				if (state.showNodes) TRV.drawNodes(layer);

				if (isActive && state.isSelecting) {
					TRV.drawSelectionOverlay();
				}

				// Layer name above the glyph
				const labelPos = TRV.glyphToScreen(0, layer.height + 30);
				ctx.font = '11px "JetBrains Mono", monospace';
				ctx.fillStyle = isActive ? 'rgba(91,157,239,0.8)' : 'rgba(255,255,255,0.35)';
				ctx.textAlign = 'left';
				ctx.fillText(layer.name || '(unnamed)', labelPos.x, labelPos.y);
			});

			if (!isActive) {
				state.selectedNodeIds = savedSelection;
			}
		}
	}

	// Soft dividers between layers
	TRV.drawJoinedDividers(canvasW, canvasH, layout);

	// Active cell indicator — subtle highlight along the baseline area
	TRV.drawJoinedActiveIndicator(layout);
};

// -- Soft dividers for joined mode ----------------------------------
TRV.drawJoinedDividers = function(canvasW, canvasH, layout) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const fade = 28;

	// Vertical dividers between columns
	for (let c = 1; c < state.gridCols; c++) {
		// Midpoint of the gap in glyph space
		const gapMidX = c * layout.cellW - layout.gap / 2;
		const screenX = gapMidX * state.zoom + state.pan.x;

		// Left fade
		const gradL = ctx.createLinearGradient(screenX - fade, 0, screenX, 0);
		gradL.addColorStop(0, 'rgba(24,24,27,0)');
		gradL.addColorStop(1, 'rgba(24,24,27,0.55)');
		ctx.fillStyle = gradL;
		ctx.fillRect(screenX - fade, 0, fade, canvasH);

		// Right fade
		const gradR = ctx.createLinearGradient(screenX, 0, screenX + fade, 0);
		gradR.addColorStop(0, 'rgba(24,24,27,0.55)');
		gradR.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradR;
		ctx.fillRect(screenX, 0, fade, canvasH);

		// Hairline
		ctx.strokeStyle = 'rgba(255,255,255,0.05)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(Math.round(screenX) + 0.5, 0);
		ctx.lineTo(Math.round(screenX) + 0.5, canvasH);
		ctx.stroke();
	}

	// Horizontal dividers between rows
	for (let r = 1; r < state.gridRows; r++) {
		// Gap midpoint in glyph Y, converted to screen
		const gapMidY = (state.gridRows - r) * layout.cellH - layout.gap / 2;
		const screenY = -gapMidY * state.zoom + state.pan.y;

		// Top fade
		const gradT = ctx.createLinearGradient(0, screenY - fade, 0, screenY);
		gradT.addColorStop(0, 'rgba(24,24,27,0)');
		gradT.addColorStop(1, 'rgba(24,24,27,0.55)');
		ctx.fillStyle = gradT;
		ctx.fillRect(0, screenY - fade, canvasW, fade);

		// Bottom fade
		const gradB = ctx.createLinearGradient(0, screenY, 0, screenY + fade);
		gradB.addColorStop(0, 'rgba(24,24,27,0.55)');
		gradB.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradB;
		ctx.fillRect(0, screenY, canvasW, fade);

		// Hairline
		ctx.strokeStyle = 'rgba(255,255,255,0.05)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(0, Math.round(screenY) + 0.5);
		ctx.lineTo(canvasW, Math.round(screenY) + 0.5);
		ctx.stroke();
	}
};

// -- Active cell indicator for joined mode --------------------------
TRV.drawJoinedActiveIndicator = function(layout) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const r = state.activeCell.row;
	const c = state.activeCell.col;

	TRV.withJoinedOffset(r, c, function() {
		const layerIdx = state.gridLayers[r][c] % state.glyphData.layers.length;
		const layer = state.glyphData.layers[layerIdx];

		// Small tick marks at corners of the glyph's advance box
		const tl = TRV.glyphToScreen(0, layer.height);
		const br = TRV.glyphToScreen(layer.width, 0);
		const tick = 8;

		ctx.strokeStyle = 'rgba(91,157,239,0.35)';
		ctx.lineWidth = 1.5;

		// Top-left corner
		ctx.beginPath();
		ctx.moveTo(tl.x, tl.y + tick);
		ctx.lineTo(tl.x, tl.y);
		ctx.lineTo(tl.x + tick, tl.y);
		ctx.stroke();

		// Top-right corner
		ctx.beginPath();
		ctx.moveTo(br.x - tick, tl.y);
		ctx.lineTo(br.x, tl.y);
		ctx.lineTo(br.x, tl.y + tick);
		ctx.stroke();

		// Bottom-left corner
		ctx.beginPath();
		ctx.moveTo(tl.x, br.y - tick);
		ctx.lineTo(tl.x, br.y);
		ctx.lineTo(tl.x + tick, br.y);
		ctx.stroke();

		// Bottom-right corner
		ctx.beginPath();
		ctx.moveTo(br.x - tick, br.y);
		ctx.lineTo(br.x, br.y);
		ctx.lineTo(br.x, br.y - tick);
		ctx.stroke();
	});
};


// ===================================================================
// SPLIT MODE — clipped cells (existing)
// ===================================================================

TRV.drawSplitView = function(canvasW, canvasH) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const layers = state.glyphData ? state.glyphData.layers : [];
	if (layers.length === 0) return;

	const savedSelection = state.selectedNodeIds;

	for (let r = 0; r < rows; r++) {
		for (let c = 0; c < cols; c++) {
			const layerIdx = state.gridLayers[r][c] % layers.length;
			const layer = layers[layerIdx];
			const cell = TRV.getCellRect(r, c);
			const isActive = (r === state.activeCell.row && c === state.activeCell.col);

			ctx.save();

			// Clip to cell
			ctx.beginPath();
			ctx.rect(cell.x, cell.y, cell.w, cell.h);
			ctx.clip();
			ctx.translate(cell.x, cell.y);

			ctx.fillStyle = state.filled ? '#18181b' : '#1a1a1e';
			ctx.fillRect(0, 0, cell.w, cell.h);

			if (!isActive) state.selectedNodeIds = new Set();

			if (state.showMetrics) TRV.drawMetrics(layer, cell.w, cell.h);
			TRV.drawContours(layer);
			if (state.showAnchors) TRV.drawAnchors(layer);
			if (state.showNodes) TRV.drawNodes(layer);

			if (isActive && state.isSelecting) {
				TRV.drawSelectionOverlay();
			}

			if (!isActive) state.selectedNodeIds = savedSelection;

			// Layer name label
			ctx.font = '11px "JetBrains Mono", monospace';
			ctx.fillStyle = isActive ? 'rgba(91,157,239,0.8)' : 'rgba(255,255,255,0.35)';
			ctx.textAlign = 'left';
			ctx.fillText(layer.name || '(unnamed)', 8, 18);

			ctx.restore();
		}
	}

	// Soft fade dividers between cells
	TRV.drawSplitDividers(canvasW, canvasH);

	// Active cell border
	TRV.drawActiveCellBorder();
};

// -- Split mode fade dividers ---------------------------------------
TRV.drawSplitDividers = function(w, h) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const fade = 24;

	for (let c = 1; c < cols; c++) {
		const x = Math.round(c * w / cols);

		const gradL = ctx.createLinearGradient(x - fade, 0, x, 0);
		gradL.addColorStop(0, 'rgba(24,24,27,0)');
		gradL.addColorStop(1, 'rgba(24,24,27,0.6)');
		ctx.fillStyle = gradL;
		ctx.fillRect(x - fade, 0, fade, h);

		const gradR = ctx.createLinearGradient(x, 0, x + fade, 0);
		gradR.addColorStop(0, 'rgba(24,24,27,0.6)');
		gradR.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradR;
		ctx.fillRect(x, 0, fade, h);

		ctx.strokeStyle = 'rgba(255,255,255,0.06)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(x + 0.5, 0);
		ctx.lineTo(x + 0.5, h);
		ctx.stroke();
	}

	for (let r = 1; r < rows; r++) {
		const y = Math.round(r * h / rows);

		const gradT = ctx.createLinearGradient(0, y - fade, 0, y);
		gradT.addColorStop(0, 'rgba(24,24,27,0)');
		gradT.addColorStop(1, 'rgba(24,24,27,0.6)');
		ctx.fillStyle = gradT;
		ctx.fillRect(0, y - fade, w, fade);

		const gradB = ctx.createLinearGradient(0, y, 0, y + fade);
		gradB.addColorStop(0, 'rgba(24,24,27,0.6)');
		gradB.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradB;
		ctx.fillRect(0, y, w, fade);

		ctx.strokeStyle = 'rgba(255,255,255,0.06)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(0, y + 0.5);
		ctx.lineTo(w, y + 0.5);
		ctx.stroke();
	}
};

// -- Active cell border (split mode) --------------------------------
TRV.drawActiveCellBorder = function() {
	const ctx = TRV.dom.ctx;
	const cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);

	ctx.strokeStyle = 'rgba(91,157,239,0.35)';
	ctx.lineWidth = 2;
	ctx.strokeRect(cell.x + 1, cell.y + 1, cell.w - 2, cell.h - 2);
};
