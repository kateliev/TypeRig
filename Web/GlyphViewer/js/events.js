// ===================================================================
// TypeRig Glyph Viewer — Event Handlers
// ===================================================================
'use strict';

(function() {

const state = TRV.state;
const dom = TRV.dom;

// -- Mouse: node dragging and spacebar panning ----------------------
dom.canvasWrap.addEventListener('mousedown', function(e) {
	if (e.button !== 0) return;

	const rect = dom.canvas.getBoundingClientRect();
	const sx = e.clientX - rect.left;
	const sy = e.clientY - rect.top;

	// Spacebar held → pan mode
	if (state.spaceDown) {
		state.isPanning = true;
		state.lastMouse = { x: e.clientX, y: e.clientY };
		dom.canvasWrap.style.cursor = 'grabbing';
		return;
	}

	// Check node hit
	if (state.showNodes) {
		const hit = TRV.hitTestNode(sx, sy);
		if (hit) {
			TRV.selectNode(hit.id);

			// Begin drag — store origin for relative/constrained movement
			const gp = TRV.screenToGlyph(sx, sy);
			state.isDragging = true;
			state.dragNodeId = hit.id;
			state.dragOriginGlyph = { x: gp.x, y: gp.y };
			state.dragNodeStart = { x: hit.x, y: hit.y };
			dom.canvasWrap.style.cursor = 'move';
			return;
		}
	}

	// Click on empty space → deselect
	TRV.selectNode(null);
});

window.addEventListener('mousemove', function(e) {
	const rect = dom.canvas.getBoundingClientRect();
	const sx = e.clientX - rect.left;
	const sy = e.clientY - rect.top;
	const gp = TRV.screenToGlyph(sx, sy);
	dom.statusCursor.textContent = `${Math.round(gp.x)}, ${Math.round(gp.y)}`;

	// Node drag
	if (state.isDragging && state.dragNodeId && state.dragNodeStart) {
		const dx = gp.x - state.dragOriginGlyph.x;
		const dy = gp.y - state.dragOriginGlyph.y;

		let newX = state.dragNodeStart.x + dx;
		let newY = state.dragNodeStart.y + dy;

		// Shift: constrain to dominant axis
		if (e.shiftKey) {
			if (Math.abs(dx) > Math.abs(dy)) {
				newY = state.dragNodeStart.y;
			} else {
				newX = state.dragNodeStart.x;
			}
		}

		TRV.updateNodePosition(state.dragNodeId, newX, newY);
		TRV.draw();
		TRV.updateStatusSelected();
		return;
	}

	// Pan
	if (state.isPanning) {
		const dsx = e.clientX - state.lastMouse.x;
		const dsy = e.clientY - state.lastMouse.y;
		state.pan.x += dsx;
		state.pan.y += dsy;
		state.lastMouse = { x: e.clientX, y: e.clientY };
		TRV.draw();
		return;
	}

	// Hover cursor hint
	if (!state.spaceDown && state.showNodes) {
		const hit = TRV.hitTestNode(sx, sy);
		dom.canvasWrap.style.cursor = hit ? 'move' : 'default';
	}
});

window.addEventListener('mouseup', function() {
	if (state.isDragging) {
		// Finalize drag: sync XML from live data
		TRV.syncXmlFromData();
		if (state.selectedNodeId) TRV.highlightXmlNode(state.selectedNodeId);
		state.isDragging = false;
		state.dragNodeId = null;
		state.dragOriginGlyph = null;
		state.dragNodeStart = null;
	}
	if (state.isPanning) {
		state.isPanning = false;
	}
	TRV.updateCanvasCursor();
});

// -- Zoom -----------------------------------------------------------
dom.canvasWrap.addEventListener('wheel', function(e) {
	e.preventDefault();
	const rect = dom.canvas.getBoundingClientRect();
	const mx = e.clientX - rect.left;
	const my = e.clientY - rect.top;

	const factor = e.deltaY > 0 ? 0.9 : 1.1;
	const newZoom = state.zoom * factor;

	state.pan.x = mx - (mx - state.pan.x) * (newZoom / state.zoom);
	state.pan.y = my - (my - state.pan.y) * (newZoom / state.zoom);
	state.zoom = newZoom;

	TRV.updateZoomStatus();
	TRV.draw();
}, { passive: false });

// -- Resize ---------------------------------------------------------
const resizeObserver = new ResizeObserver(function() { TRV.draw(); });
resizeObserver.observe(dom.canvasWrap);

// -- Toolbar buttons ------------------------------------------------
document.getElementById('btn-load').addEventListener('click', function() {
	dom.fileInput.click();
});

document.getElementById('btn-save').addEventListener('click', TRV.saveXml);

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

document.getElementById('btn-nodes').addEventListener('click', function() {
	state.showNodes = !state.showNodes;
	this.classList.toggle('active');
	TRV.draw();
});

document.getElementById('btn-metrics').addEventListener('click', function() {
	state.showMetrics = !state.showMetrics;
	this.classList.toggle('active');
	TRV.draw();
});

document.getElementById('btn-anchors').addEventListener('click', function() {
	state.showAnchors = !state.showAnchors;
	this.classList.toggle('active');
	TRV.draw();
});

document.getElementById('btn-xml').addEventListener('click', function() {
	state.showXml = !state.showXml;
	this.classList.toggle('active');

	const xmlPanel = document.getElementById('xml-panel');

	if (state.showXml) {
		const mainWidth = dom.main.clientWidth;
		xmlPanel.style.width = Math.round(mainWidth * 0.4) + 'px';
		xmlPanel.classList.add('visible');
		dom.splitHandle.classList.add('visible');
	} else {
		xmlPanel.classList.remove('visible');
		dom.splitHandle.classList.remove('visible');
		xmlPanel.style.width = '';
	}

	requestAnimationFrame(function() {
		TRV.draw();
		if (state.showXml) TRV.buildXmlPanel();
	});
});

document.getElementById('btn-fit').addEventListener('click', TRV.fitToView);

dom.layerSelect.addEventListener('change', function() {
	state.activeLayer = this.value;
	state.selectedNodeId = null;
	TRV.fitToView();
	TRV.buildXmlPanel();
});

// -- File input -----------------------------------------------------
dom.fileInput.addEventListener('change', function(e) {
	const file = e.target.files[0];
	if (!file) return;
	const reader = new FileReader();
	reader.onload = function(ev) { TRV.loadXmlString(ev.target.result, file.name); };
	reader.readAsText(file);
	dom.fileInput.value = '';
});

// -- Drag and drop --------------------------------------------------
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

// -- Keyboard -------------------------------------------------------
document.addEventListener('keydown', function(e) {
	// Spacebar: panning mode
	if (e.code === 'Space' && e.target !== dom.xmlContent) {
		if (!state.spaceDown) {
			state.spaceDown = true;
			e.preventDefault();
			TRV.updateCanvasCursor();
		}
		return;
	}

	// Don't intercept normal typing in the XML textarea
	if (e.target === dom.xmlContent) {
		if (!(e.ctrlKey || e.metaKey)) return;
	}

	// Ctrl/Cmd shortcuts
	if (e.ctrlKey || e.metaKey) {
		if (e.key === 'o') { e.preventDefault(); dom.fileInput.click(); }
		if (e.key === 's') { e.preventDefault(); TRV.saveXml(); }
		if (e.key === 'e') {
			e.preventDefault();
			document.getElementById('btn-xml').click();
		}
	}

	// Arrow keys: move selected node
	if (state.selectedNodeId && e.target !== dom.xmlContent) {
		let step = TRV.ARROW_STEP;
		if (e.shiftKey) step = TRV.ARROW_STEP_SHIFT;
		if (e.ctrlKey || e.metaKey) step = TRV.ARROW_STEP_CTRL;

		switch (e.key) {
			case 'ArrowUp':
				e.preventDefault();
				TRV.moveSelectedNode(0, step);
				return;
			case 'ArrowDown':
				e.preventDefault();
				TRV.moveSelectedNode(0, -step);
				return;
			case 'ArrowRight':
				e.preventDefault();
				TRV.moveSelectedNode(step, 0);
				return;
			case 'ArrowLeft':
				e.preventDefault();
				TRV.moveSelectedNode(-step, 0);
				return;
		}
	}

	if (e.key === 'Home' && e.target !== dom.xmlContent) {
		e.preventDefault();
		TRV.fitToView();
	}
	if (e.key === 'Escape') { TRV.selectNode(null); }
});

document.addEventListener('keyup', function(e) {
	if (e.code === 'Space') {
		state.spaceDown = false;
		if (state.isPanning) {
			state.isPanning = false;
		}
		TRV.updateCanvasCursor();
	}
});

// -- Split handle drag ----------------------------------------------
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
		const xmlPanel = document.getElementById('xml-panel');

		const mouseX = e.clientX - mainRect.left;
		const panelWidth = mainRect.width - mouseX - dom.splitHandle.offsetWidth / 2;

		const minPanel = 200;
		const maxPanel = mainRect.width - minPanel - dom.splitHandle.offsetWidth;
		xmlPanel.style.width = Math.max(minPanel, Math.min(maxPanel, panelWidth)) + 'px';

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

// -- XML textarea events --------------------------------------------
dom.xmlContent.addEventListener('input', TRV.onXmlEdit);
dom.xmlContent.addEventListener('click', TRV.onXmlClick);

})();
