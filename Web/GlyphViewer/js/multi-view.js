
// TypeRig Glyph Viewer — Multi-Layer Grid View
// Two rendering modes:
//   Split  — independent clipped cells, each a mini viewport
//   Joined — layers placed side by side on a shared baseline,
//            one continuous pan/zoom space (like glyphs in a line)
//
// Ribbon rotation: Ctrl+scroll columns, Alt+scroll rows.
// Layers loop infinitely (A,B,C,A,B,C...).
'use strict';

// -- Grid initialization --------------------------------------------
TRV.initMultiGrid = function() {
	const state = TRV.state;
	const cols = state.gridCols;
	const rows = state.gridRows;

	// Only non-mask layers participate in the grid
	const validIndices = TRV.getNonMaskLayerIndices();
	const N = validIndices.length || 1;

	state.gridLayers = [];
	let idx = 0;
	for (let r = 0; r < rows; r++) {
		const row = [];
		for (let c = 0; c < cols; c++) {
			row.push(validIndices[idx % N]);
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

	var r = state.activeCell.row;
	var c = state.activeCell.col;
	if (!state.gridLayers[r] || state.gridLayers[r][c] === undefined) return;

	const layers = state.glyphData.layers;
	const N = layers.length;
	const layerIdx = state.gridLayers[r][c] % N;

	state.activeLayer = layers[layerIdx].name;
	TRV.dom.layerSelect.value = layers[layerIdx].name;
};

// -- Ribbon rotation ------------------------------------------------
TRV.rotateColumn = function(col, direction) {
	const state = TRV.state;
	const validIndices = TRV.getNonMaskLayerIndices();
	const N = validIndices.length || 1;

	for (let r = 0; r < state.gridRows; r++) {
		// Find current position in validIndices
		let pos = validIndices.indexOf(state.gridLayers[r][col]);
		if (pos < 0) pos = 0;
		pos = ((pos + direction) % N + N) % N;
		state.gridLayers[r][col] = validIndices[pos];
	}

	TRV.syncActiveCellToLayer();
};

TRV.rotateRow = function(row, direction) {
	const state = TRV.state;
	const validIndices = TRV.getNonMaskLayerIndices();
	const N = validIndices.length || 1;

	for (let c = 0; c < state.gridCols; c++) {
		let pos = validIndices.indexOf(state.gridLayers[row][c]);
		if (pos < 0) pos = 0;
		pos = ((pos + direction) % N + N) % N;
		state.gridLayers[row][c] = validIndices[pos];
	}

	TRV.syncActiveCellToLayer();
};

TRV.withIsolatedSelection = function(isActive, fn) {
	const state = TRV.state;
	const saved = state.selectedNodeIds;

	if (!isActive) state.selectedNodeIds = new Set();

	fn();

	state.selectedNodeIds = saved;
};

// -- JOINED MODE — shared canvas, layers in glyph space -------------
// -- Layout computation ---------------------------------------------
// Returns glyph-space offsets for each cell and total bounding box
TRV.getJoinedLayout = function() {
	const state = TRV.state;
	const layers = state.glyphData ? state.glyphData.layers : [];
	const cols = state.gridCols;
	const rows = state.gridRows;
	const gap = TRV.theme.grid.joinedGap;

	// Compute actual bounding box across non-mask layers
	let maxW = 0, maxH = 0;
	for (const layer of layers) {
		if (TRV.isMaskLayer(layer.name)) continue;

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
	const state = TRV.state;
	const layers = state.glyphData ? state.glyphData.layers : [];
	if (!layers.length) return;

	const rows = state.gridRows;
	const cols = state.gridCols;

	for (let r = 0; r < rows; r++) {
		for (let c = 0; c < cols; c++) {

			const layerIdx = state.gridLayers[r][c] % layers.length;
			const layer = layers[layerIdx];
			const isActive = (
				r === state.activeCell.row &&
				c === state.activeCell.col
			);

			TRV.withJoinedOffset(r, c, () => {

				TRV.withIsolatedSelection(isActive, () => {
					TRV.renderLayer(layer, {
						isActive,
						canvasW,
						canvasH
					});
				});

			});
		}
	}

	if (!state.previewMode)
		TRV.drawJoinedActiveIndicator(TRV.getJoinedLayout());
};

// -- Soft dividers for joined mode ----------------------------------
TRV.drawJoinedDividers = function(canvasW, canvasH, layout) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const tg = TRV.theme.grid;
	const rgb = TRV.theme.bgFadeRgb;
	const a = tg.dividerFadeAlphaJ;
	const fade = 28;

	// Vertical dividers between columns
	for (let c = 1; c < state.gridCols; c++) {
		const gapMidX = c * layout.cellW - layout.gap / 2;
		const screenX = gapMidX * state.zoom + state.pan.x;

		const gradL = ctx.createLinearGradient(screenX - fade, 0, screenX, 0);
		gradL.addColorStop(0, 'rgba(' + rgb + ',0)');
		gradL.addColorStop(1, 'rgba(' + rgb + ',' + a + ')');
		ctx.fillStyle = gradL;
		ctx.fillRect(screenX - fade, 0, fade, canvasH);

		const gradR = ctx.createLinearGradient(screenX, 0, screenX + fade, 0);
		gradR.addColorStop(0, 'rgba(' + rgb + ',' + a + ')');
		gradR.addColorStop(1, 'rgba(' + rgb + ',0)');
		ctx.fillStyle = gradR;
		ctx.fillRect(screenX, 0, fade, canvasH);

		ctx.strokeStyle = tg.dividerHairlineJ;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(Math.round(screenX) + 0.5, 0);
		ctx.lineTo(Math.round(screenX) + 0.5, canvasH);
		ctx.stroke();
	}

	// Horizontal dividers between rows
	for (let r = 1; r < state.gridRows; r++) {
		const gapMidY = (state.gridRows - r) * layout.cellH - layout.gap / 2;
		const screenY = -gapMidY * state.zoom + state.pan.y;

		const gradT = ctx.createLinearGradient(0, screenY - fade, 0, screenY);
		gradT.addColorStop(0, 'rgba(' + rgb + ',0)');
		gradT.addColorStop(1, 'rgba(' + rgb + ',' + a + ')');
		ctx.fillStyle = gradT;
		ctx.fillRect(0, screenY - fade, canvasW, fade);

		const gradB = ctx.createLinearGradient(0, screenY, 0, screenY + fade);
		gradB.addColorStop(0, 'rgba(' + rgb + ',' + a + ')');
		gradB.addColorStop(1, 'rgba(' + rgb + ',0)');
		ctx.fillStyle = gradB;
		ctx.fillRect(0, screenY, canvasW, fade);

		ctx.strokeStyle = tg.dividerHairlineJ;
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

		ctx.strokeStyle = TRV.theme.grid.activeBorder;
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


// -- SPLIT MODE — clipped cells (existing) -------------------------------------
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

			var preview = state.previewMode;
			ctx.fillStyle = preview ? TRV.theme.bgPreview : TRV.getBgColor();
			ctx.fillRect(0, 0, cell.w, cell.h);

			if (!isActive) {
				state.selectedNodeIds = new Set();
				
			}

			TRV.renderLayer(layer, {
				isActive,
				canvasW: cell.w,
				canvasH: cell.h
			});

			ctx.restore();
			
			if (!isActive){
				state.selectedNodeIds = savedSelection;
			}
		}
	}

	// Drop shadow dividers between cells in CAD style multiview
	if (!state.previewMode) TRV.drawSplitDividers(canvasW, canvasH);

	// Active cell border
	TRV.drawActiveCellBorder();
};

// -- Drop shadow dividers between cells in CAD style multiview
TRV.drawSplitDividers = function(w, h) {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const grid = TRV.theme.grid;
	const rgb = TRV.theme.bgFadeRgb;
	const fade =  TRV.theme.grid.fade;
	const alpha = TRV.theme.grid.dividerFadeAlpha;
	const cols = state.gridCols;
	const rows = state.gridRows;

	for (let c = 1; c < cols; c++) {
		const x = Math.round(c * w / cols);

		const gradL = ctx.createLinearGradient(x - fade, 0, x, 0);
		gradL.addColorStop(0, 'rgba(' + rgb + ',0)');
		gradL.addColorStop(1, 'rgba(' + rgb + ',' + alpha + ')');
		ctx.fillStyle = gradL;
		ctx.fillRect(x - fade, 0, fade, h);

		const gradR = ctx.createLinearGradient(x, 0, x + fade, 0);
		gradR.addColorStop(0, 'rgba(' + rgb + ',' + alpha + ')');
		gradR.addColorStop(1, 'rgba(' + rgb + ',0)');
		ctx.fillStyle = gradR;
		ctx.fillRect(x, 0, fade, h);

		ctx.strokeStyle = grid.dividerHairline;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(x + 0.5, 0);
		ctx.lineTo(x + 0.5, h);
		ctx.stroke();
	}

	for (let r = 1; r < rows; r++) {
		const y = Math.round(r * h / rows);

		const gradT = ctx.createLinearGradient(0, y - fade, 0, y);
		gradT.addColorStop(0, 'rgba(' + rgb + ',0)');
		gradT.addColorStop(1, 'rgba(' + rgb + ',' + alpha + ')');
		ctx.fillStyle = gradT;
		ctx.fillRect(0, y - fade, w, fade);

		const gradB = ctx.createLinearGradient(0, y, 0, y + fade);
		gradB.addColorStop(0, 'rgba(' + rgb + ',' + alpha + ')');
		gradB.addColorStop(1, 'rgba(' + rgb + ',0)');
		ctx.fillStyle = gradB;
		ctx.fillRect(0, y, w, fade);

		ctx.strokeStyle = grid.dividerHairline;
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

	ctx.strokeStyle = TRV.theme.grid.activeBorder;
	ctx.lineWidth = 2;
	ctx.strokeRect(cell.x + 1, cell.y + 1, cell.w - 2, cell.h - 2);
};


// -- GLYPH STRIP — glyphs on a shared baseline ---------------------
// Active glyph can expand into a layer grid (2x1, 2x2, etc.).
// Non-active glyphs show one layer on the baseline.
// Future: any glyph can be expanded independently.

// -- Ensure active glyph is in the workspace strip ------------------
// Does NOT auto-populate neighbors. User adds glyphs via double-click.
TRV.updateWorkspaceStrip = function() {
	if (!TRV.font || !TRV.activeGlyph) return;

	var ws = TRV.workspace;
	var idx = ws.glyphs.indexOf(TRV.activeGlyph);

	if (idx < 0) {
		// Active glyph not in strip — add it
		ws.glyphs.push(TRV.activeGlyph);
		ws.activeIdx = ws.glyphs.length - 1;
	} else {
		ws.activeIdx = idx;
	}

	// Preload neighbors
	for (var i = 0; i < ws.glyphs.length; i++) {
		TRV._ensureGlyphLoaded(ws.glyphs[i]);
	}
};

// -- Add a glyph to the workspace strip -----------------------------
// Inserts after active glyph, or at end if not found.
TRV.addGlyphToStrip = function(name) {
	var ws = TRV.workspace;
	if (ws.glyphs.indexOf(name) >= 0) return; // already in strip

	// Insert after active position
	ws.glyphs.splice(ws.activeIdx + 1, 0, name);
	TRV._ensureGlyphLoaded(name);
	TRV.updateGlyphPanelActive();

	if (TRV.state.glyphViewMode) {
		TRV.draw();
	}
};

// -- Remove a glyph from the workspace strip ------------------------
TRV.removeGlyphFromStrip = function(name) {
	var ws = TRV.workspace;
	var idx = ws.glyphs.indexOf(name);
	if (idx < 0) return;
	if (name === TRV.activeGlyph) return; // can't remove active

	ws.glyphs.splice(idx, 1);
	// Fix activeIdx if needed
	if (ws.activeIdx >= ws.glyphs.length) {
		ws.activeIdx = ws.glyphs.length - 1;
	} else if (idx < ws.activeIdx) {
		ws.activeIdx--;
	}

	TRV.updateGlyphPanelActive();

	if (TRV.state.glyphViewMode) {
		TRV.draw();
	}
};

// -- Glyph strip layout computation ---------------------------------
// Returns { slots, totalW, rowH }
TRV.getGlyphStripLayout = function() {
	var state = TRV.state;
	var ws = TRV.workspace;
	var gap = TRV.theme.grid.stripGap;
	var upm = TRV.font ? TRV.font.metrics.upm : 1000;
	var rowH = upm + gap;

	// Active glyph expansion
	var aCols = (state.multiView && !state.glyphViewMode) ? 1 : state.gridCols;
	var aRows = (state.multiView && !state.glyphViewMode) ? 1 : state.gridRows;
	// In glyph strip mode: gridCols/gridRows apply to active glyph
	if (state.glyphViewMode) {
		aCols = state.gridCols;
		aRows = state.gridRows;
	} else {
		aCols = 1;
		aRows = 1;
	}

	var slots = [];
	var x = 0;

	for (var i = 0; i < ws.glyphs.length; i++) {
		var name = ws.glyphs[i];
		var isActive = (i === ws.activeIdx);

		// Get advance width from cached glyph using active layer
		var advW = upm * 0.6; // fallback
		var cacheEntry = TRV.glyphCache.get(name);
		if (cacheEntry) {
			// Try active layer first, then default
			var layer = TRV.getLayerByName(cacheEntry.glyphData, TRV.state.activeLayer);
			if (!layer) {
				var defLayer = TRV.getDefaultLayerName(cacheEntry.glyphData);
				layer = TRV.getLayerByName(cacheEntry.glyphData, defLayer);
			}
			if (layer) advW = layer.width || advW;
		}

		var cols = isActive ? aCols : 1;
		var rows = isActive ? aRows : 1;
		var slotW = advW * cols + (cols > 1 ? gap * (cols - 1) : 0);

		slots.push({
			name: name,
			x: x,
			w: slotW,
			advW: advW,
			active: isActive,
			cols: cols,
			rows: rows,
			cached: !!cacheEntry
		});

		x += slotW + gap;
	}

	return { slots: slots, totalW: x - gap, rowH: rowH };
};

// -- Draw glyph strip -----------------------------------------------
TRV.drawGlyphStrip = function(canvasW, canvasH) {
	var ctx = TRV.dom.ctx;
	var state = TRV.state;
	var theme = TRV.theme.activeCellHightlight;
	var preview = state.previewMode;
	var layout = TRV.getGlyphStripLayout();
	var upm = TRV.font ? TRV.font.metrics.upm : 1000;

	// Clear close button hit rects from previous draw
	TRV.workspace._closeRects = {};

	// Save global state we'll swap per slot
	var savedGlyphData = state.glyphData;
	var savedActiveLayer = state.activeLayer;
	var savedSelection = state.selectedNodeIds;
	var savedPanX = state.pan.x;
	var savedPanY = state.pan.y;

	// (gridLayers built on demand inside active slot when expanded)

	for (var si = 0; si < layout.slots.length; si++) {
		var slot = layout.slots[si];
		var cacheEntry = TRV.glyphCache.get(slot.name);
		if (!cacheEntry) {
			TRV._ensureGlyphLoaded(slot.name);
			continue;
		}

		// Reset pan to base for each slot (previous slot may have shifted it)
		state.pan.x = savedPanX;
		state.pan.y = savedPanY;

		var glyphData = cacheEntry.glyphData;

		if (slot.active) {
			// -- Active glyph: raised background highlight --
			if (!preview) {
				var xL = TRV.glyphToScreen(slot.x, 0).x;
				var xR = TRV.glyphToScreen(slot.x + slot.w, 0).x;
				var gTop = TRV.glyphToScreen(0, upm * 2).y;
				var gBot = TRV.glyphToScreen(0, -upm).y;
				var activeGrad = ctx.createLinearGradient(0, gTop, 0, gBot);
				theme.backgroundGradient.forEach(([p, c]) => activeGrad.addColorStop(p, c));
		
				ctx.fillStyle = activeGrad;
				ctx.fillRect(xL, gTop, xR - xL, gBot - gTop);
				ctx.strokeStyle = theme.strokeStyle;
				ctx.lineWidth = 1;
				ctx.beginPath();
				ctx.moveTo(xL, gTop); ctx.lineTo(xL, gBot);
				ctx.moveTo(xR, gTop); ctx.lineTo(xR, gBot);
				ctx.stroke();
			}

			state.glyphData = glyphData;
			var isExpanded = (slot.cols > 1 || slot.rows > 1);

			if (!isExpanded) {
				// -- Single cell (1x1): draw activeLayer directly --
				var layer = TRV.getLayerByName(glyphData, savedActiveLayer);
				if (!layer) layer = glyphData.layers[0];
				if (layer) {
					state.activeLayer = layer.name;
					state.pan.x = savedPanX + slot.x * state.zoom;
					state.pan.y = savedPanY;
					
					TRV.renderLayer(layer, {
						isActive: true,
						canvasW: canvasW,
						canvasH: canvasH
					});

				}
			} else {
				// -- Expanded grid: build gridLayers, draw per cell --
				TRV._ensureStripGrid();

				for (var r = 0; r < slot.rows; r++) {
					for (var c = 0; c < slot.cols; c++) {
						var layerIdx = 0;
						if (state.gridLayers && state.gridLayers[r] &&
							state.gridLayers[r][c] !== undefined) {
							layerIdx = state.gridLayers[r][c];
						}

						if (layerIdx >= glyphData.layers.length) layerIdx = 0;
						var layer = glyphData.layers[layerIdx];
						var isActiveCell = (r === state.activeCell.row && c === state.activeCell.col);

						state.activeLayer = layer.name;

						var cellOffX = slot.x + c * (slot.advW + TRV.theme.grid.stripGap);
						var cellOffY = r * layout.rowH;

						state.pan.x = savedPanX + cellOffX * state.zoom;
						state.pan.y = savedPanY - cellOffY * state.zoom;

						if (!isActiveCell) state.selectedNodeIds = new Set();

						TRV.renderLayer(layer, {
							isActive: true,
							canvasW: canvasW,
							canvasH: canvasH
						});

						state.selectedNodeIds = savedSelection;
					}
				}
			}

			// Active glyph info widget (below baseline)
			if (!preview) {
				state.pan.x = savedPanX + slot.x * state.zoom;
				state.pan.y = savedPanY;
				state.glyphData = glyphData;
				state.activeLayer = savedActiveLayer;
				var baseLayer = TRV.getLayerByName(glyphData, savedActiveLayer);
				if (!baseLayer) baseLayer = glyphData.layers[0];
				if (baseLayer) {
					// Show HTML widget instead of canvas widget
					TRV.updateGlyphWidget();
				}
			}
		} else {
			// -- Non-active glyph: same layer as active glyph --
			state.glyphData = glyphData;
			var layer = TRV.getLayerByName(glyphData, savedActiveLayer);
			if (!layer) {
				var defName = TRV.getDefaultLayerName(glyphData);
				layer = TRV.getLayerByName(glyphData, defName);
			}
			if (!layer) continue;

			state.activeLayer = layer.name;
			state.selectedNodeIds = new Set();

			state.pan.x = savedPanX + slot.x * state.zoom;
			state.pan.y = savedPanY;

			TRV.drawContours(layer);

			// Restore selection so active glyph sees it
			state.selectedNodeIds = savedSelection;
		}
	}

	// Restore global state
	state.glyphData = savedGlyphData;
	state.activeLayer = savedActiveLayer;
	state.selectedNodeIds = savedSelection;
	state.pan.x = savedPanX;
	state.pan.y = savedPanY;
};

// -- Ensure gridLayers is populated for strip expanded view ---------
TRV._ensureStripGrid = function() {
	var state = TRV.state;
	var cols = state.gridCols;
	var rows = state.gridRows;
	if (cols <= 1 && rows <= 1) return;

	var glyphData = state.glyphData;
	if (!glyphData) return;

	// Build valid (non-mask) layer indices
	var validIndices = [];
	for (var i = 0; i < glyphData.layers.length; i++) {
		if (!TRV.isMaskLayer(glyphData.layers[i].name)) validIndices.push(i);
	}
	if (validIndices.length === 0) return;

	// Find starting index from activeLayer
	var startLayerIdx = validIndices[0];
	for (var i = 0; i < validIndices.length; i++) {
		if (glyphData.layers[validIndices[i]].name === state.activeLayer) {
			startLayerIdx = validIndices[i];
			break;
		}
	}

	// Only rebuild if gridLayers doesn't match dimensions
	if (!state.gridLayers || state.gridLayers.length !== rows ||
		(state.gridLayers[0] && state.gridLayers[0].length !== cols)) {
		state.gridLayers = [];
		var idx = validIndices.indexOf(startLayerIdx);
		for (var r = 0; r < rows; r++) {
			var row = [];
			for (var c = 0; c < cols; c++) {
				row.push(validIndices[idx % validIndices.length]);
				idx++;
			}
			state.gridLayers.push(row);
		}
	}
};

// -- Fit glyph strip to view ----------------------------------------
TRV.fitGlyphStrip = function() {
	var layout = TRV.getGlyphStripLayout();
	var canvasW = TRV.dom.canvasWrap.clientWidth;
	var canvasH = TRV.dom.canvasWrap.clientHeight;
	var upm = TRV.font ? TRV.font.metrics.upm : 1000;
	var desc = TRV.font ? Math.abs(TRV.font.metrics.descender) : 200;
	var totalH = upm + desc * 0.5;

	// Find active slot for centering
	var activeSlot = null;
	for (var i = 0; i < layout.slots.length; i++) {
		if (layout.slots[i].active) { activeSlot = layout.slots[i]; break; }
	}

	// Zoom: fit total height + some extra rows if expanded
	var rows = activeSlot ? activeSlot.rows : 1;
	var viewH = totalH + (rows - 1) * layout.rowH;
	var padding = 40;
	var scaleY = (canvasH - padding * 2) / viewH;
	var scaleX = (canvasW - padding * 2) / layout.totalW;
	TRV.state.zoom = Math.min(scaleX, scaleY);

	// Center on active glyph
	if (activeSlot) {
		var cx = activeSlot.x + activeSlot.w / 2;
		TRV.state.pan.x = canvasW / 2 - cx * TRV.state.zoom;
		TRV.state.pan.y = canvasH * 0.75 + (rows - 1) * layout.rowH * TRV.state.zoom * 0.3;
	}

	TRV.updateZoomStatus();
};

// -- Strip offset for interaction -----------------------------------
// Temporarily shift pan to the active cell's position in the strip
TRV.withStripOffset = function(row, col, fn) {
	var layout = TRV.getGlyphStripLayout();
	var state = TRV.state;

	// Find active slot
	var activeSlot = null;
	for (var i = 0; i < layout.slots.length; i++) {
		if (layout.slots[i].active) { activeSlot = layout.slots[i]; break; }
	}
	if (!activeSlot) { fn(); return; }

	var cellOffX = activeSlot.x + col * (activeSlot.advW + TRV.theme.grid.stripGap);
	var cellOffY = row * layout.rowH;

	var savedPanX = state.pan.x;
	var savedPanY = state.pan.y;

	state.pan.x += cellOffX * state.zoom;
	state.pan.y -= cellOffY * state.zoom;

	fn();

	state.pan.x = savedPanX;
	state.pan.y = savedPanY;
};

// -- Glyph info widget (drawn below baseline in strip) ---------------
TRV._drawGlyphWidget = function(ctx, slot, layer, isActive, verticalOffset = 8, width = 250, height = 80) {
    // Init
    var advW = layer.width || 0;
    var lsb = TRV.glyphToScreen(0, 0);
    var rsb = TRV.glyphToScreen(advW, 0);
    var midX = (lsb.x + rsb.x) / 2;
    var widgetY = lsb.y + verticalOffset;

    // Glyp specific metadata
    var name = slot.name;
    var enc = TRV.font ? (TRV.font.encoding[name] || slot.unicode) : '';
    var dirty = TRV.dirtyGlyphs.has(name);
	var lsbVal = bounds ? Math.round(bounds.minX) : 0;
	var rsbVal = bounds ? Math.round(advW - bounds.maxX) : 0;
    var bounds = TRV._getLayerBounds(layer);
    
    // Set up fonts
    var font10 = '10px "JetBrains Mono", monospace';
    var font9 = '9px "JetBrains Mono", monospace';
    var font_icon = '16px "TypeRig Icons", monospace';
    var padX = 8, radius = 3;
    
    // Calculate widget position and size
    var boxW = width;
    var boxH = height;
    var boxX = midX - boxW / 2;
    var boxY = widgetY;
    
    // Background with different alpha for active/non-active
    if (isActive) {
        ctx.fillStyle = 'rgba(91,157,239,0.2)';
    } else {
        ctx.fillStyle = 'rgba(255,255,255,0.08)';
    }
    
    TRV._roundRect(ctx, boxX, boxY, boxW, boxH, radius);
    ctx.fill();
    
    // Grid layout: 3x3
    var cellW = boxW / 3;
    var cellH = boxH / 3;
    
    // Helper function to draw icon + field
    function drawIconField(ctx, iconChar, text, x, y, width, height, isActive) {
        // Draw background for the field
        ctx.fillStyle = 'rgba(0,0,0,0.1)';
        ctx.fillRect(x, y, width, height);
        
        // Draw icon
        ctx.font = font_icon;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = isActive ? 'rgba(91,157,239,0.7)' : 'rgba(255,255,255,0.3)';
        ctx.fillText(iconChar, x + 4, y + height / 2);
        
        // Draw text field
        ctx.font = font10;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = isActive ? 'rgba(91,157,239,0.9)' : 'rgba(255,255,255,0.45)';
        ctx.fillText(text, x + 24, y + height / 2);
    }
    
    // - Glyph info fields
    // -- Row 1
    drawIconField(ctx, 'label', 		name, 	boxX			, boxY, cellW, cellH, isActive);
    drawIconField(ctx, 'select_glyph', 	enc, 	boxX + 1 * cellW, boxY, cellW, cellH, isActive);
    drawIconField(ctx, 'close', 		'Close',boxX + 2 * cellW, boxY, cellW, cellH, isActive); // Close button
    
    // --- Store close button hit rect
	if (!TRV.workspace._closeRects) TRV.workspace._closeRects = {};
	
	TRV.workspace._closeRects[slot.name] = {
		x: boxX + 2 * cellW,
		y: boxY,
		w: cellW,
		h: cellH
	};
    
    // Row 2
    // Left side bearing (metrics_lsb)
    drawIconField(ctx, 'metrics_lsb', 		lsbVal, 	boxX			, boxY + 1 * cellH, cellW, cellH, isActive);
    drawIconField(ctx, 'metrics_advance', 	advW, 		boxX + 1 * cellW, boxY + 1 * cellH, cellW, cellH, isActive);
    drawIconField(ctx, 'metrics_rsb', 		rsbVal, 	boxX + 2 * cellW, boxY + 1 * cellH, cellW, cellH, isActive);
    
    // Restore text baseline
    ctx.textBaseline = 'alphabetic';
};

// -- Rounded rect helper --------------------------------------------
TRV._roundRect = function(ctx, x, y, w, h, r) {
	ctx.beginPath();
	ctx.moveTo(x + r, y);
	ctx.lineTo(x + w - r, y);
	ctx.quadraticCurveTo(x + w, y, x + w, y + r);
	ctx.lineTo(x + w, y + h - r);
	ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
	ctx.lineTo(x + r, y + h);
	ctx.quadraticCurveTo(x, y + h, x, y + h - r);
	ctx.lineTo(x, y + r);
	ctx.quadraticCurveTo(x, y, x + r, y);
	ctx.closePath();
};

// -- Glyph Widget HTML Overlay ---------------------------------------
TRV._widgetSlot = null;

TRV.showGlyphWidget = function(slot, layer) {
	var widget = TRV.dom.glyphWidget;
	if (!widget || !slot || !layer) return;

	var state = TRV.state;
	var bounds = TRV._getLayerBounds(layer);
	var advW = layer.width || 0;

	// Calculate LSB/RSB from bounds
	var lsbVal = bounds ? Math.round(bounds.minX) : 0;
	var rsbVal = bounds ? Math.round(advW - bounds.maxX) : 0;

	// Get glyph unicode
	var name = slot.name;
	var unicode = '';
	if (TRV.font && TRV.font.encoding) {
		var code = TRV.font.encoding[name];
		if (code) unicode = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
	}

	// Position widget below baseline
	var lsbScreen = TRV.glyphToScreen(0, 0);
	var rsbScreen = TRV.glyphToScreen(advW, 0);
	var midX = (lsbScreen.x + rsbScreen.x) / 2;
	var widgetY = lsbScreen.y + 12;

	// Get canvas-wrap dimensions for relative positioning
	var wrapRect = TRV.dom.canvasWrap.getBoundingClientRect();
	var relX = midX - wrapRect.left;
	var relY = widgetY - wrapRect.top;

	// Center the widget (width ~230px)
	var widgetW = 230;
	relX = relX - widgetW / 2;

	// Clamp to canvas bounds
	relX = Math.max(8, Math.min(relX, wrapRect.width - widgetW - 8));
	relY = Math.max(8, Math.min(relY, wrapRect.height - 80));

	// Position and populate
	widget.style.left = relX + 'px';
	widget.style.top = relY + 'px';

	TRV.dom.gwName.value = name;
	TRV.dom.gwUnicode.value = unicode;
	TRV.dom.gwLsb.value = lsbVal;
	TRV.dom.gwAdvance.value = advW;
	TRV.dom.gwRsb.value = rsbVal;

	// Store reference for close button
	TRV._widgetSlot = name;

	widget.classList.add('visible');
};

TRV.hideGlyphWidget = function() {
	if (TRV.dom.glyphWidget) {
		TRV.dom.glyphWidget.classList.remove('visible');
	}
	TRV._widgetSlot = null;
	// Clear non-active widgets
	if (TRV.dom.glyphWidgets) {
		TRV.dom.glyphWidgets.innerHTML = '';
	}
};

// -- Create a read-only widget for non-active glyph -------------
TRV._createReadonlyWidget = function(name, layer, slotX, slotAdvW) {
	var container = TRV.dom.glyphWidgets;
	if (!container) return;

	var bounds = TRV._getLayerBounds(layer);
	var advW = layer.width || 0;
	var lsbVal = bounds ? Math.round(bounds.minX) : 0;
	var rsbVal = bounds ? Math.round(advW - bounds.maxX) : 0;

	var unicode = '';
	if (TRV.font && TRV.font.encoding) {
		var code = TRV.font.encoding[name];
		if (code) unicode = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
	}

	// Calculate position
	var lsbScreen = TRV.glyphToScreen(0, 0);
	var rsbScreen = TRV.glyphToScreen(advW, 0);
	var midX = (lsbScreen.x + rsbScreen.x) / 2;
	var widgetY = lsbScreen.y + 12;

	var wrapRect = TRV.dom.canvasWrap.getBoundingClientRect();
	var relX = midX - wrapRect.left;
	var relY = widgetY - wrapRect.top;

	var widgetW = 230;
	relX = relX - widgetW / 2;
	relX = Math.max(8, Math.min(relX, wrapRect.width - widgetW - 8));
	relY = Math.max(8, Math.min(relY, wrapRect.height - 80));

	// Create widget HTML
	var widget = document.createElement('div');
	widget.className = 'glyph-widget glyph-widget--readonly';
	widget.style.left = relX + 'px';
	widget.style.top = relY + 'px';
	widget.innerHTML =
		'<div class="gw-row">' +
			'<div class="gw-field"><span class="tri">label</span><span class="gw-value">' + name + '</span></div>' +
			'<div class="gw-field"><span class="tri">select_glyph</span><span class="gw-value">' + unicode + '</span></div>' +
		'</div>' +
		'<div class="gw-row">' +
			'<div class="gw-field"><span class="tri">metrics_lsb</span><span class="gw-value">' + lsbVal + '</span></div>' +
			'<div class="gw-field"><span class="tri">metrics_advance</span><span class="gw-value">' + advW + '</span></div>' +
			'<div class="gw-field"><span class="tri">metrics_rsb</span><span class="gw-value">' + rsbVal + '</span></div>' +
		'</div>';
	container.appendChild(widget);
};

TRV.updateGlyphWidget = function() {
	var state = TRV.state;
	if (!state.glyphData || !state.glyphViewMode) {
		TRV.hideGlyphWidget();
		return;
	}

	var ws = TRV.workspace;
	if (ws.activeIdx < 0 || ws.activeIdx >= ws.glyphs.length) {
		TRV.hideGlyphWidget();
		return;
	}

	// Clear previous non-active widgets
	if (TRV.dom.glyphWidgets) {
		TRV.dom.glyphWidgets.innerHTML = '';
	}

	var layout = TRV.getGlyphStripLayout();

	// First pass: create read-only widgets for non-active glyphs
	for (var i = 0; i < layout.slots.length; i++) {
		var slot = layout.slots[i];
		if (slot.active) continue;

		var cacheEntry = TRV.glyphCache.get(slot.name);
		if (!cacheEntry) continue;

		var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
		if (!layer) layer = cacheEntry.glyphData.layers[0];
		if (!layer) continue;

		TRV._createReadonlyWidget(slot.name, layer);
	}

	// Second pass: show editable widget for active glyph
	var name = ws.glyphs[ws.activeIdx];
	var cacheEntry = TRV.glyphCache.get(name);
	if (!cacheEntry) {
		TRV.hideGlyphWidget();
		return;
	}

	var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
	if (!layer) layer = cacheEntry.glyphData.layers[0];
	if (!layer) {
		TRV.hideGlyphWidget();
		return;
	}

	var activeSlot = null;
	for (var i = 0; i < layout.slots.length; i++) {
		if (layout.slots[i].active) { activeSlot = layout.slots[i]; break; }
	}

	if (activeSlot) {
		TRV.showGlyphWidget(activeSlot, layer);
	}
};

// -- Handle widget input changes -------------------------------------
TRV.initGlyphWidget = function() {
	var nameInput = TRV.dom.gwName;
	var unicodeInput = TRV.dom.gwUnicode;
	var lsbInput = TRV.dom.gwLsb;
	var advInput = TRV.dom.gwAdvance;
	var rsbInput = TRV.dom.gwRsb;

	// Name change - rename glyph
	nameInput.addEventListener('change', function() {
		var oldName = TRV._widgetSlot;
		var newName = this.value.trim();
		if (!oldName || !newName || oldName === newName) return;

		// Update in workspace
		var ws = TRV.workspace;
		var idx = ws.glyphs.indexOf(oldName);
		if (idx >= 0) {
			ws.glyphs[idx] = newName;
			TRV.activeGlyph = newName;
			TRV.dirtyGlyphs.add(newName);
			TRV.dirtyGlyphs.delete(oldName);
			TRV._widgetSlot = newName;
			TRV.updateGlyphPanelActive();
		}
	});

	// Unicode change
	unicodeInput.addEventListener('change', function() {
		var glyphName = TRV._widgetSlot;
		var val = this.value.trim();
		if (!glyphName) return;

		var code = null;
		if (val.startsWith('U+') || val.startsWith('u+')) {
			code = parseInt(val.slice(2), 16);
		} else if (/^[0-9a-fA-F]+$/.test(val)) {
			code = parseInt(val, 16);
		}

		if (code !== null && code >= 0 && code <= 0x10FFFF) {
			if (TRV.font && TRV.font.encoding) {
				TRV.font.encoding[glyphName] = code;
				TRV.dirtyGlyphs.add(glyphName);
				this.value = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
			}
		} else {
			// Reset to current value
			if (TRV.font && TRV.font.encoding) {
				var current = TRV.font.encoding[glyphName];
				if (current) {
					this.value = 'U+' + current.toString(16).toUpperCase().padStart(4, '0');
				}
			}
		}
	});

	// Width changes (LSB, Advance, RSB)
	function updateWidths() {
		var glyphName = TRV._widgetSlot;
		if (!glyphName) return;

		var lsb = parseInt(lsbInput.value) || 0;
		var adv = parseInt(advInput.value) || 0;
		var rsb = parseInt(rsbInput.value) || 0;

		// Validate: lsb + rsb <= advance
		if (lsb + rsb > adv) {
			// Adjust RSB
			rsb = adv - lsb;
			rsbInput.value = rsb;
		}

		var cacheEntry = TRV.glyphCache.get(glyphName);
		if (!cacheEntry) return;

		var state = TRV.state;
		var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
		if (!layer) layer = cacheEntry.glyphData.layers[0];
		if (!layer) return;

		// Update layer width
		layer.width = adv;

		// Shift contour nodes if LSB changed
		var bounds = TRV._getLayerBounds(layer);
		if (bounds) {
			var currentLsb = Math.round(bounds.minX);
			var delta = lsb - currentLsb;
			if (delta !== 0) {
				for (var si = 0; si < layer.shapes.length; si++) {
					var shape = layer.shapes[si];
					for (var ki = 0; ki < shape.contours.length; ki++) {
						var nodes = shape.contours[ki].nodes;
						for (var ni = 0; ni < nodes.length; ni++) {
							nodes[ni].x += delta;
						}
					}
				}
			}
		}

		TRV.dirtyGlyphs.add(glyphName);
		TRV.draw();
		TRV.updateGlyphWidget();
	}

	lsbInput.addEventListener('change', updateWidths);
	advInput.addEventListener('change', updateWidths);
	rsbInput.addEventListener('change', updateWidths);

	// Close button
	var closeBtn = TRV.dom.glyphWidget.querySelector('[data-field="close"]');
	if (closeBtn) {
		closeBtn.addEventListener('click', function() {
			var name = TRV._widgetSlot;
			if (name) {
				TRV.removeGlyphFromStrip(name);
			}
		});
	}
};

// -- Get contour bounding box for a layer ---------------------------
TRV._getLayerBounds = function(layer) {
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	var found = false;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			for (var ni = 0; ni < nodes.length; ni++) {
				found = true;
				if (nodes[ni].x < minX) minX = nodes[ni].x;
				if (nodes[ni].y < minY) minY = nodes[ni].y;
				if (nodes[ni].x > maxX) maxX = nodes[ni].x;
				if (nodes[ni].y > maxY) maxY = nodes[ni].y;
			}
		}
	}
	return found ? { minX: minX, minY: minY, maxX: maxX, maxY: maxY } : null;
};

// -- Glyph rotation in strip ----------------------------------------
TRV.rotateGlyphColumn = function(col, direction) {
	// Rotate the glyph at a strip position
	var state = TRV.state;
	if (!TRV.font) return;
	var manifest = TRV.font.manifest;
	var N = manifest.length;
	if (N === 0) return;

	// Find which workspace slot to rotate
	var slotIdx = TRV.workspace.activeIdx;
	if (slotIdx < 0 || slotIdx >= TRV.workspace.glyphs.length) return;

	var current = TRV.workspace.glyphs[slotIdx];
	var idx = 0;
	for (var i = 0; i < N; i++) {
		if ((manifest[i].alias || manifest[i].name) === current) { idx = i; break; }
	}
	idx = ((idx + direction) % N + N) % N;
	var newName = manifest[idx].alias || manifest[idx].name;
	TRV.workspace.glyphs[slotIdx] = newName;
	TRV._ensureGlyphLoaded(newName);
};

TRV.rotateGlyphRow = function(row, direction) {
	TRV.rotateGlyphColumn(0, direction);
};

// -- Ensure glyph is loaded into cache (async, triggers redraw) -----
TRV._loadQueue = new Set();
TRV._loadRunning = false;

TRV._ensureGlyphLoaded = function(name) {
	if (TRV.glyphCache.has(name) || TRV._loadQueue.has(name)) return;
	TRV._loadQueue.add(name);
	TRV._processLoadQueue();
};

TRV._processLoadQueue = async function() {
	if (TRV._loadRunning) return;
	TRV._loadRunning = true;

	while (TRV._loadQueue.size > 0) {
		var name = TRV._loadQueue.values().next().value;
		TRV._loadQueue.delete(name);

		if (!TRV.glyphCache.has(name)) {
			var glyphData = await TRV.loadGlyphFile(name);
			if (glyphData) {
				TRV.glyphCache.set(name, {
					glyphData: glyphData,
					undoStack: [],
					redoStack: [],
					selection: new Set(),
					pan: null,
					zoom: null
				});
				TRV._evictCache();
			}
		}

		TRV.draw();
		await new Promise(function(r) { requestAnimationFrame(r); });
	}

	TRV._loadRunning = false;
};
