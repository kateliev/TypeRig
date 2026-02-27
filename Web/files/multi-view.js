// ===================================================================
// TypeRig Glyph Viewer — Multi-Layer Grid View
// ===================================================================
// Rubik's ribbon model: 2x1 or 2x2 grid of layer viewports.
// Ctrl+scroll rotates a column, Alt+scroll rotates a row.
// Layers loop infinitely (A,B,C,A,B,C...).
// Cells share the same baseline — like glyphs side by side.
// ===================================================================
'use strict';

// -- Grid initialization --------------------------------------------
TRV.initMultiGrid = function() {
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const N = state.glyphData ? state.glyphData.layers.length : 1;

	// Fill grid row-major with sequential layer indices (mod N)
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

// -- Cell geometry --------------------------------------------------
TRV.getCellRect = function(row, col) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cols = TRV.state.gridCols;
	const rows = TRV.state.gridRows;
	const cellW = w / cols;
	const cellH = h / rows;

	return {
		x: col * cellW,
		y: row * cellH,
		w: cellW,
		h: cellH,
	};
};

TRV.getCellAt = function(sx, sy) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cols = TRV.state.gridCols;
	const rows = TRV.state.gridRows;

	const col = Math.max(0, Math.min(cols - 1, Math.floor(sx / (w / cols))));
	const row = Math.max(0, Math.min(rows - 1, Math.floor(sy / (h / rows))));

	return { row, col };
};

TRV.canvasToCellCoords = function(sx, sy) {
	if (!TRV.state.multiView) {
		return { sx, sy, row: 0, col: 0 };
	}

	const cell = TRV.getCellAt(sx, sy);
	const rect = TRV.getCellRect(cell.row, cell.col);

	return {
		sx: sx - rect.x,
		sy: sy - rect.y,
		row: cell.row,
		col: cell.col,
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
	const layer = layers[layerIdx];

	state.activeLayer = layer.name;
	TRV.dom.layerSelect.value = layer.name;
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

// -- Multi-view drawing ---------------------------------------------
TRV.drawMultiView = function(canvasW, canvasH) {
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

			// Translate so (0,0) is cell top-left
			ctx.translate(cell.x, cell.y);

			// Clear cell background
			ctx.fillStyle = state.filled ? '#18181b' : '#1a1a1e';
			ctx.fillRect(0, 0, cell.w, cell.h);

			// Hide selection markers in non-active cells
			if (!isActive) {
				state.selectedNodeIds = new Set();
			}

			// Draw layer contents
			if (state.showMetrics) TRV.drawMetrics(layer, cell.w, cell.h);
			TRV.drawContours(layer);
			if (state.showAnchors) TRV.drawAnchors(layer);
			if (state.showNodes) TRV.drawNodes(layer);

			// Selection overlay only in active cell
			if (isActive && state.isSelecting) {
				TRV.drawSelectionOverlay();
			}

			// Restore selection
			if (!isActive) {
				state.selectedNodeIds = savedSelection;
			}

			// Layer name label
			ctx.font = '11px "JetBrains Mono", monospace';
			ctx.fillStyle = isActive ? 'rgba(91,157,239,0.8)' : 'rgba(255,255,255,0.35)';
			ctx.textAlign = 'left';
			ctx.fillText(layer.name || '(unnamed)', 8, 18);

			ctx.restore();
		}
	}

	// Soft fade dividers between cells
	TRV.drawFadeDividers(canvasW, canvasH);

	// Active cell highlight border
	TRV.drawActiveCellBorder();
};

// -- Soft fade dividers ---------------------------------------------
// Gradient vignette at cell boundaries — subtle, not hard lines
TRV.drawFadeDividers = function(w, h) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;
	const bgColor = state.filled ? '#18181b' : '#1a1a1e';

	// Fade width in pixels
	const fade = 24;

	// Vertical dividers
	for (let c = 1; c < cols; c++) {
		const x = Math.round(c * w / cols);

		// Left fade: transparent → bg
		const gradL = ctx.createLinearGradient(x - fade, 0, x, 0);
		gradL.addColorStop(0, 'rgba(24,24,27,0)');
		gradL.addColorStop(1, 'rgba(24,24,27,0.6)');
		ctx.fillStyle = gradL;
		ctx.fillRect(x - fade, 0, fade, h);

		// Right fade: bg → transparent
		const gradR = ctx.createLinearGradient(x, 0, x + fade, 0);
		gradR.addColorStop(0, 'rgba(24,24,27,0.6)');
		gradR.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradR;
		ctx.fillRect(x, 0, fade, h);

		// Thin hairline at center
		ctx.strokeStyle = 'rgba(255,255,255,0.06)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(x + 0.5, 0);
		ctx.lineTo(x + 0.5, h);
		ctx.stroke();
	}

	// Horizontal dividers
	for (let r = 1; r < rows; r++) {
		const y = Math.round(r * h / rows);

		// Top fade
		const gradT = ctx.createLinearGradient(0, y - fade, 0, y);
		gradT.addColorStop(0, 'rgba(24,24,27,0)');
		gradT.addColorStop(1, 'rgba(24,24,27,0.6)');
		ctx.fillStyle = gradT;
		ctx.fillRect(0, y - fade, w, fade);

		// Bottom fade
		const gradB = ctx.createLinearGradient(0, y, 0, y + fade);
		gradB.addColorStop(0, 'rgba(24,24,27,0.6)');
		gradB.addColorStop(1, 'rgba(24,24,27,0)');
		ctx.fillStyle = gradB;
		ctx.fillRect(0, y, w, fade);

		// Thin hairline
		ctx.strokeStyle = 'rgba(255,255,255,0.06)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(0, y + 0.5);
		ctx.lineTo(w, y + 0.5);
		ctx.stroke();
	}
};

// -- Active cell border highlight -----------------------------------
TRV.drawActiveCellBorder = function() {
	const ctx = TRV.dom.ctx;
	const cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);

	ctx.strokeStyle = 'rgba(91,157,239,0.35)';
	ctx.lineWidth = 2;
	ctx.strokeRect(cell.x + 1, cell.y + 1, cell.w - 2, cell.h - 2);
};
