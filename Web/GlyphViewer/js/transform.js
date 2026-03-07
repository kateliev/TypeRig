// ===================================================================
// TypeRig Glyph Viewer — Transform Frame
// ===================================================================
// Scale, rotate, skew selected nodes via an interactive bounding frame.
// Modes: scale (default) → rotate → skew (cycle via double-click).
// Numeric controls in status bar for precise input.
'use strict';

// -- Transform state ------------------------------------------------
TRV.tf = {
	active: false,
	mode: 'scale',        // 'scale' | 'rotate' | 'skew'
	bbox: null,            // { minX, minY, maxX, maxY } glyph space
	origin: null,          // { x, y } transform center in glyph space
	startPositions: null,  // Map: nodeId → { x, y }
	dragType: null,        // 'handle' | 'origin' | null
	dragHandle: -1,        // handle index 0-7
	dragStart: null,       // { gx, gy } glyph coords at drag start
	cumRotation: 0,        // cumulative rotation in degrees
	cumSkewX: 0,           // cumulative skew X in degrees
	cumSkewY: 0,           // cumulative skew Y in degrees
};

TRV.TF_HANDLE_SIZE = 4;   // half-size in screen pixels
TRV.TF_ROTATE_MARGIN = 12; // screen pixels outside frame for rotate zone

// -- Handle layout --------------------------------------------------
// 0=TL, 1=TC, 2=TR, 3=MR, 4=BR, 5=BC, 6=BL, 7=ML
TRV._tfHandlePositions = function() {
	var b = TRV.tf.bbox;
	if (!b) return [];
	var cx = (b.minX + b.maxX) / 2;
	var cy = (b.minY + b.maxY) / 2;
	return [
		{ x: b.minX, y: b.maxY }, // 0 TL
		{ x: cx,     y: b.maxY }, // 1 TC
		{ x: b.maxX, y: b.maxY }, // 2 TR
		{ x: b.maxX, y: cy     }, // 3 MR
		{ x: b.maxX, y: b.minY }, // 4 BR
		{ x: cx,     y: b.minY }, // 5 BC
		{ x: b.minX, y: b.minY }, // 6 BL
		{ x: b.minX, y: cy     }, // 7 ML
	];
};

// -- Activate transform frame ---------------------------------------
TRV.activateTransform = function() {
	var sel = TRV.state.selectedNodeIds;
	if (sel.size < 2) return;

	TRV.pushUndo();

	// Compute bounding box of selected nodes
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	var startPos = new Map();

	for (var id of sel) {
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		startPos.set(id, { x: ref.node.x, y: ref.node.y });
		if (ref.node.x < minX) minX = ref.node.x;
		if (ref.node.y < minY) minY = ref.node.y;
		if (ref.node.x > maxX) maxX = ref.node.x;
		if (ref.node.y > maxY) maxY = ref.node.y;
	}

	if (startPos.size < 2) return;

	TRV.tf.active = true;
	TRV.tf.mode = 'scale';
	TRV.tf.bbox = { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
	TRV.tf.origin = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
	TRV.tf.startPositions = startPos;
	TRV.tf.dragType = null;
	TRV.tf.cumRotation = 0;
	TRV.tf.cumSkewX = 0;
	TRV.tf.cumSkewY = 0;

	TRV._tfUpdateStatus();
	TRV.draw();
};

// -- Deactivate transform frame -------------------------------------
TRV.deactivateTransform = function() {
	TRV.tf.active = false;
	TRV.tf.bbox = null;
	TRV.tf.startPositions = null;
	TRV.tf.dragType = null;
	TRV._tfClearStatus();
	TRV.draw();
};

// -- Cycle mode on double-click -------------------------------------
TRV.cycleTransformMode = function() {
	var modes = ['scale', 'rotate', 'skew'];
	var idx = modes.indexOf(TRV.tf.mode);
	TRV.tf.mode = modes[(idx + 1) % modes.length];
	TRV._tfUpdateStatus();
	TRV.draw();
};

// -- Hit test: which handle or zone was clicked ---------------------
// Returns { type: 'handle'|'origin'|'inside'|'rotate'|null, idx: n }
TRV.tfHitTest = function(sx, sy) {
	if (!TRV.tf.active || !TRV.tf.startPositions) return { type: null };

	var hs = TRV.TF_HANDLE_SIZE;

	// Check origin
	var osp = TRV.glyphToScreen(TRV.tf.origin.x, TRV.tf.origin.y);
	if (Math.abs(sx - osp.x) <= hs + 2 && Math.abs(sy - osp.y) <= hs + 2) {
		return { type: 'origin', idx: -1 };
	}

	// Compute live bbox
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	for (var id of TRV.tf.startPositions.keys()) {
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		if (ref.node.x < minX) minX = ref.node.x;
		if (ref.node.y < minY) minY = ref.node.y;
		if (ref.node.x > maxX) maxX = ref.node.x;
		if (ref.node.y > maxY) maxY = ref.node.y;
	}
	if (!isFinite(minX)) return { type: null };

	// Handle positions from live bbox
	var cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
	var handles = [
		{ x: minX, y: maxY }, { x: cx, y: maxY }, { x: maxX, y: maxY }, { x: maxX, y: cy },
		{ x: maxX, y: minY }, { x: cx, y: minY }, { x: minX, y: minY }, { x: minX, y: cy }
	];

	for (var i = 0; i < handles.length; i++) {
		var sp = TRV.glyphToScreen(handles[i].x, handles[i].y);
		if (Math.abs(sx - sp.x) <= hs + 2 && Math.abs(sy - sp.y) <= hs + 2) {
			return { type: 'handle', idx: i };
		}
	}

	// Check inside bbox
	var gp = TRV.screenToGlyph(sx, sy);
	if (gp.x >= minX && gp.x <= maxX && gp.y >= minY && gp.y <= maxY) {
		return { type: 'inside', idx: -1 };
	}

	// Check rotate zone (outside frame by margin)
	var rm = TRV.TF_ROTATE_MARGIN / TRV.state.zoom;
	if (gp.x >= minX - rm && gp.x <= maxX + rm &&
		gp.y >= minY - rm && gp.y <= maxY + rm) {
		return { type: 'rotate', idx: -1 };
	}

	return { type: null };
};

// -- Draw transform frame -------------------------------------------
TRV.drawTransformFrame = function() {
	if (!TRV.tf.active || !TRV.tf.startPositions) return;

	var ctx = TRV.dom.ctx;
	var hs = TRV.TF_HANDLE_SIZE;
	var tf = TRV.tf;

	// Compute live bbox from current node positions
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	for (var id of tf.startPositions.keys()) {
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		if (ref.node.x < minX) minX = ref.node.x;
		if (ref.node.y < minY) minY = ref.node.y;
		if (ref.node.x > maxX) maxX = ref.node.x;
		if (ref.node.y > maxY) maxY = ref.node.y;
	}

	if (!isFinite(minX)) return;

	// 8 handle positions from live bbox
	var cx = (minX + maxX) / 2;
	var cy = (minY + maxY) / 2;
	var pts = [
		{ x: minX, y: maxY }, // 0 TL
		{ x: cx,   y: maxY }, // 1 TC
		{ x: maxX, y: maxY }, // 2 TR
		{ x: maxX, y: cy   }, // 3 MR
		{ x: maxX, y: minY }, // 4 BR
		{ x: cx,   y: minY }, // 5 BC
		{ x: minX, y: minY }, // 6 BL
		{ x: minX, y: cy   }, // 7 ML
	];

	// Frame corners
	var corners = [pts[0], pts[2], pts[4], pts[6]]; // TL TR BR BL

	ctx.save();

	// Dashed frame
	ctx.strokeStyle = 'rgba(91,157,239,0.6)';
	ctx.lineWidth = 1;
	ctx.setLineDash([4, 3]);
	ctx.beginPath();
	for (var i = 0; i < corners.length; i++) {
		var sp = TRV.glyphToScreen(corners[i].x, corners[i].y);
		if (i === 0) ctx.moveTo(sp.x, sp.y);
		else ctx.lineTo(sp.x, sp.y);
	}
	ctx.closePath();
	ctx.stroke();
	ctx.setLineDash([]);

	// Handles
	for (var i = 0; i < pts.length; i++) {
		var sp = TRV.glyphToScreen(pts[i].x, pts[i].y);
		ctx.fillStyle = '#5b9def';
		ctx.strokeStyle = '#1a1a1e';
		ctx.lineWidth = 1;
		ctx.fillRect(sp.x - hs, sp.y - hs, hs * 2, hs * 2);
		ctx.strokeRect(sp.x - hs, sp.y - hs, hs * 2, hs * 2);
	}

	// Origin marker (crosshair + circle)
	var osp = TRV.glyphToScreen(tf.origin.x, tf.origin.y);
	ctx.strokeStyle = 'rgba(91,157,239,0.8)';
	ctx.lineWidth = 1;
	ctx.beginPath();
	ctx.arc(osp.x, osp.y, 5, 0, Math.PI * 2);
	ctx.stroke();
	ctx.beginPath();
	ctx.moveTo(osp.x - 8, osp.y); ctx.lineTo(osp.x + 8, osp.y);
	ctx.moveTo(osp.x, osp.y - 8); ctx.lineTo(osp.x, osp.y + 8);
	ctx.stroke();

	// Mode label near top-left
	var tlsp = TRV.glyphToScreen(minX, maxY);
	ctx.font = '9px "JetBrains Mono", monospace';
	ctx.fillStyle = 'rgba(91,157,239,0.7)';
	ctx.textAlign = 'left';
	ctx.fillText(tf.mode.toUpperCase(), tlsp.x, tlsp.y - 6);

	ctx.restore();
};

// ===================================================================
// Transform math
// ===================================================================

// -- Scale from handle drag -----------------------------------------
TRV._tfApplyScale = function(gx, gy) {
	var tf = TRV.tf;
	var b = tf.bbox;
	var hi = tf.dragHandle;
	var ox = tf.origin.x, oy = tf.origin.y;

	// Determine which axes this handle controls
	// Corners (0,2,4,6) = both axes; edges (1,5)=Y only; (3,7)=X only
	var isCorner = (hi % 2 === 0);
	var isHoriz = (hi === 3 || hi === 7); // MR, ML
	var isVert = (hi === 1 || hi === 5);  // TC, BC

	// Reference point is the handle's original position
	var handles = TRV._tfHandlePositions();
	var refPt = handles[hi];

	// Scale factor from origin
	var bw = refPt.x - ox;
	var bh = refPt.y - oy;
	var sx = Math.abs(bw) > 0.1 ? (gx - ox) / bw : 1;
	var sy = Math.abs(bh) > 0.1 ? (gy - oy) / bh : 1;

	if (isHoriz) sy = 1;
	if (isVert) sx = 1;

	// Apply to all selected nodes from their start positions
	for (var entry of tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;

		var nx = ox + (orig.x - ox) * sx;
		var ny = oy + (orig.y - oy) * sy;
		ref.node.x = Math.round(nx * 10) / 10;
		ref.node.y = Math.round(ny * 10) / 10;
	}

	TRV._tfUpdateStatus();
};

// -- Rotate from drag -----------------------------------------------
TRV._tfApplyRotate = function(gx, gy) {
	var tf = TRV.tf;
	var ox = tf.origin.x, oy = tf.origin.y;

	// Angle from origin to current point vs drag start
	var startAngle = Math.atan2(tf.dragStart.gy - oy, tf.dragStart.gx - ox);
	var curAngle = Math.atan2(gy - oy, gx - ox);
	var angle = curAngle - startAngle;

	// Shift: snap to 15 degrees
	if (TRV.tf._shiftKey) {
		var deg = angle * 180 / Math.PI;
		deg = Math.round(deg / 15) * 15;
		angle = deg * Math.PI / 180;
	}

	tf.cumRotation = angle * 180 / Math.PI;

	var cos = Math.cos(angle);
	var sin = Math.sin(angle);

	for (var entry of tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;

		var dx = orig.x - ox;
		var dy = orig.y - oy;
		ref.node.x = Math.round((ox + dx * cos - dy * sin) * 10) / 10;
		ref.node.y = Math.round((oy + dx * sin + dy * cos) * 10) / 10;
	}

	TRV._tfUpdateStatus();
};

// -- Skew from handle drag ------------------------------------------
TRV._tfApplySkew = function(gx, gy) {
	var tf = TRV.tf;
	var b = tf.bbox;
	var hi = tf.dragHandle;
	var ox = tf.origin.x, oy = tf.origin.y;
	var bw = b.maxX - b.minX;
	var bh = b.maxY - b.minY;

	// Horizontal edges (1=TC, 5=BC) → skew X
	// Vertical edges (3=MR, 7=ML) → skew Y
	// Corners → skew X
	var deltaGx = gx - tf.dragStart.gx;
	var deltaGy = gy - tf.dragStart.gy;

	var skewXrad = 0, skewYrad = 0;

	if (hi === 1 || hi === 5 || hi === 0 || hi === 2 || hi === 4 || hi === 6) {
		// Horizontal skew: X shift proportional to Y distance from origin
		if (Math.abs(bh) > 0.1) {
			skewXrad = Math.atan2(deltaGx, bh);
		}
	}
	if (hi === 3 || hi === 7) {
		// Vertical skew: Y shift proportional to X distance from origin
		if (Math.abs(bw) > 0.1) {
			skewYrad = Math.atan2(deltaGy, bw);
		}
	}

	// Clamp to ±75 degrees
	skewXrad = Math.max(-1.31, Math.min(1.31, skewXrad));
	skewYrad = Math.max(-1.31, Math.min(1.31, skewYrad));

	tf.cumSkewX = skewXrad * 180 / Math.PI;
	tf.cumSkewY = skewYrad * 180 / Math.PI;

	var tanX = Math.tan(skewXrad);
	var tanY = Math.tan(skewYrad);

	for (var entry of tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;

		var dx = orig.x - ox;
		var dy = orig.y - oy;
		ref.node.x = Math.round((ox + dx + dy * tanX) * 10) / 10;
		ref.node.y = Math.round((oy + dy + dx * tanY) * 10) / 10;
	}

	TRV._tfUpdateStatus();
};

// ===================================================================
// Mouse integration
// ===================================================================

// Called from events.js mousedown — returns true if handled
TRV.tfMouseDown = function(sx, sy, e) {
	if (!TRV.tf.active) return false;

	var hit = TRV.tfHitTest(sx, sy);
	if (hit.type === null) {
		// Click outside frame — deactivate
		TRV.deactivateTransform();
		return false; // let normal mousedown proceed
	}

	var gp = TRV.screenToGlyph(sx, sy);
	TRV.tf._shiftKey = e.shiftKey;

	if (hit.type === 'origin') {
		TRV.tf.dragType = 'origin';
		TRV.tf.dragStart = { gx: gp.x, gy: gp.y };
		return true;
	}

	if (hit.type === 'handle') {
		TRV.tf.dragType = 'handle';
		TRV.tf.dragHandle = hit.idx;
		TRV.tf.dragStart = { gx: gp.x, gy: gp.y };
		return true;
	}

	if (hit.type === 'rotate' && TRV.tf.mode === 'rotate') {
		TRV.tf.dragType = 'rotate';
		TRV.tf.dragStart = { gx: gp.x, gy: gp.y };
		return true;
	}

	if (hit.type === 'inside') {
		// Inside frame — let normal node drag handle it
		return false;
	}

	return false;
};

// Called from events.js mousemove — returns true if handled
TRV.tfMouseMove = function(sx, sy, e) {
	if (!TRV.tf.active || !TRV.tf.dragType) return false;

	var gp = TRV.screenToGlyph(sx, sy);
	TRV.tf._shiftKey = e.shiftKey;

	if (TRV.tf.dragType === 'origin') {
		TRV.tf.origin.x = Math.round(gp.x);
		TRV.tf.origin.y = Math.round(gp.y);
		TRV.draw();
		return true;
	}

	if (TRV.tf.dragType === 'handle') {
		if (TRV.tf.mode === 'scale') {
			TRV._tfApplyScale(gp.x, gp.y);
		} else if (TRV.tf.mode === 'skew') {
			TRV._tfApplySkew(gp.x, gp.y);
		} else if (TRV.tf.mode === 'rotate') {
			TRV._tfApplyRotate(gp.x, gp.y);
		}
		TRV.draw();
		return true;
	}

	if (TRV.tf.dragType === 'rotate') {
		TRV._tfApplyRotate(gp.x, gp.y);
		TRV.draw();
		return true;
	}

	return false;
};

// Called from events.js mouseup
TRV.tfMouseUp = function() {
	if (!TRV.tf.active) return false;
	if (!TRV.tf.dragType) return false;

	TRV.tf.dragType = null;

	// Recalculate bbox from new positions
	TRV._tfRecalcBbox();
	TRV._tfUpdateStatus();
	TRV.draw();
	return true;
};

// Called from events.js dblclick — cycle mode
TRV.tfDblClick = function(sx, sy) {
	if (!TRV.tf.active) return false;

	var hit = TRV.tfHitTest(sx, sy);
	if (hit.type === 'inside' || hit.type === 'handle' || hit.type === 'rotate') {
		TRV.cycleTransformMode();
		return true;
	}
	return false;
};

// -- Recalculate bbox from current node positions -------------------
TRV._tfRecalcBbox = function() {
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	var newStart = new Map();

	for (var id of TRV.tf.startPositions.keys()) {
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		newStart.set(id, { x: ref.node.x, y: ref.node.y });
		if (ref.node.x < minX) minX = ref.node.x;
		if (ref.node.y < minY) minY = ref.node.y;
		if (ref.node.x > maxX) maxX = ref.node.x;
		if (ref.node.y > maxY) maxY = ref.node.y;
	}

	TRV.tf.bbox = { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
	TRV.tf.startPositions = newStart;
	TRV.tf.cumRotation = 0;
	TRV.tf.cumSkewX = 0;
	TRV.tf.cumSkewY = 0;
};

// ===================================================================
// Status bar numeric controls
// ===================================================================

TRV._tfUpdateStatus = function() {
	var el = document.getElementById('tf-controls');
	if (!el) return;

	if (!TRV.tf.active) {
		el.style.display = 'none';
		return;
	}

	el.style.display = 'flex';
	var b = TRV.tf.bbox;
	var w = Math.round((b.maxX - b.minX) * 10) / 10;
	var h = Math.round((b.maxY - b.minY) * 10) / 10;

	document.getElementById('tf-w').value = w;
	document.getElementById('tf-h').value = h;
	document.getElementById('tf-r').value = Math.round(TRV.tf.cumRotation * 10) / 10;
	document.getElementById('tf-sx').value = Math.round(TRV.tf.cumSkewX * 10) / 10;
	document.getElementById('tf-sy').value = Math.round(TRV.tf.cumSkewY * 10) / 10;

	var modeEl = document.getElementById('tf-mode');
	if (modeEl) modeEl.textContent = TRV.tf.mode.charAt(0).toUpperCase() + TRV.tf.mode.slice(1);
};

TRV._tfClearStatus = function() {
	var el = document.getElementById('tf-controls');
	if (el) el.style.display = 'none';
};

// -- Numeric input handlers -----------------------------------------
TRV._tfApplyNumeric = function(field, value) {
	if (!TRV.tf.active || !TRV.tf.startPositions) return;

	var b = TRV.tf.bbox;
	var ox = TRV.tf.origin.x, oy = TRV.tf.origin.y;
	var bw = b.maxX - b.minX;
	var bh = b.maxY - b.minY;

	if (field === 'w' && Math.abs(bw) > 0.1) {
		var sx = value / bw;
		TRV._tfScaleAll(sx, 1);
	} else if (field === 'h' && Math.abs(bh) > 0.1) {
		var sy = value / bh;
		TRV._tfScaleAll(1, sy);
	} else if (field === 'r') {
		var angle = value * Math.PI / 180;
		TRV._tfRotateAll(angle);
	} else if (field === 'sx') {
		var rad = value * Math.PI / 180;
		TRV._tfSkewAll(rad, 0);
	} else if (field === 'sy') {
		var rad = value * Math.PI / 180;
		TRV._tfSkewAll(0, rad);
	}

	TRV._tfRecalcBbox();
	TRV._tfUpdateStatus();
	TRV.draw();
};

TRV._tfScaleAll = function(sx, sy) {
	var ox = TRV.tf.origin.x, oy = TRV.tf.origin.y;
	for (var entry of TRV.tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		ref.node.x = Math.round((ox + (orig.x - ox) * sx) * 10) / 10;
		ref.node.y = Math.round((oy + (orig.y - oy) * sy) * 10) / 10;
	}
};

TRV._tfRotateAll = function(angle) {
	var ox = TRV.tf.origin.x, oy = TRV.tf.origin.y;
	var cos = Math.cos(angle), sin = Math.sin(angle);
	for (var entry of TRV.tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		var dx = orig.x - ox, dy = orig.y - oy;
		ref.node.x = Math.round((ox + dx * cos - dy * sin) * 10) / 10;
		ref.node.y = Math.round((oy + dx * sin + dy * cos) * 10) / 10;
	}
};

TRV._tfSkewAll = function(radX, radY) {
	var ox = TRV.tf.origin.x, oy = TRV.tf.origin.y;
	var tanX = Math.tan(radX), tanY = Math.tan(radY);
	for (var entry of TRV.tf.startPositions) {
		var id = entry[0], orig = entry[1];
		var ref = TRV.findNodeById(id);
		if (!ref) continue;
		var dx = orig.x - ox, dy = orig.y - oy;
		ref.node.x = Math.round((ox + dx + dy * tanX) * 10) / 10;
		ref.node.y = Math.round((oy + dy + dx * tanY) * 10) / 10;
	}
};

// -- Wire numeric inputs --------------------------------------------
TRV.wireTransformInputs = function() {
	var fields = ['w', 'h', 'r', 'sx', 'sy'];
	for (var i = 0; i < fields.length; i++) {
		(function(f) {
			var el = document.getElementById('tf-' + f);
			if (!el) return;
			el.addEventListener('change', function() {
				var val = parseFloat(this.value);
				if (isNaN(val)) return;
				TRV._tfApplyNumeric(f, val);
			});
			el.addEventListener('keydown', function(e) {
				if (e.key === 'Enter') {
					e.preventDefault();
					var val = parseFloat(this.value);
					if (!isNaN(val)) TRV._tfApplyNumeric(f, val);
					this.blur();
				}
				if (e.key === 'Escape') {
					this.blur();
				}
				e.stopPropagation(); // prevent key bindings while typing
			});
		})(fields[i]);
	}
};
