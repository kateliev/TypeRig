// ===================================================================
// TypeRig Glyph Viewer — Input Bindings
// ===================================================================
// All keyboard shortcuts, mouse actions, and toolbar button bindings
// in one place. Events.js wires DOM listeners that dispatch here.
// ===================================================================
'use strict';

// -- Zoom factors ---------------------------------------------------
TRV.ZOOM_IN_FACTOR  = 1.15;
TRV.ZOOM_OUT_FACTOR = 1 / 1.15;
TRV.WHEEL_ZOOM_IN   = 1.1;
TRV.WHEEL_ZOOM_OUT  = 0.9;

// -- Actions --------------------------------------------------------
// Named functions that keyboard/mouse/toolbar bindings reference.
// Each receives an optional event context object { e, sx, sy }.
TRV.actions = {
	// -- File ---
	openFile: function() {
		TRV.dom.fileInput.click();
	},

	saveFile: function() {
		TRV.saveXml();
	},

	// -- View ---
	fitToView: function() {
		TRV.fitToView();
	},

	zoomIn: function() {
		TRV.zoomAtCenter(TRV.ZOOM_IN_FACTOR);
	},

	zoomOut: function() {
		TRV.zoomAtCenter(TRV.ZOOM_OUT_FACTOR);
	},

	// -- Selection ---
	selectAll: function() {
		var layer = TRV.getActiveLayer();
		if (!layer) return;
		var allNodes = TRV.getAllNodes(layer);
		TRV.state.selectedNodeIds.clear();
		for (var i = 0; i < allNodes.length; i++) {
			TRV.state.selectedNodeIds.add(allNodes[i].id);
		}
		TRV.draw();
		TRV.updateStatusSelected();
	},

	clearSelection: function() {
		TRV.clearSelection();
	},

	// -- Node movement (arrow keys) ---
	moveUp: function(ctx) {
		var step = TRV.ARROW_STEP;
		if (ctx.e.shiftKey) step = TRV.ARROW_STEP_SHIFT;
		if (ctx.e.ctrlKey || ctx.e.metaKey) step = TRV.ARROW_STEP_CTRL;
		TRV.moveSelectedNodes(0, step);
	},

	moveDown: function(ctx) {
		var step = TRV.ARROW_STEP;
		if (ctx.e.shiftKey) step = TRV.ARROW_STEP_SHIFT;
		if (ctx.e.ctrlKey || ctx.e.metaKey) step = TRV.ARROW_STEP_CTRL;
		TRV.moveSelectedNodes(0, -step);
	},

	moveRight: function(ctx) {
		var step = TRV.ARROW_STEP;
		if (ctx.e.shiftKey) step = TRV.ARROW_STEP_SHIFT;
		if (ctx.e.ctrlKey || ctx.e.metaKey) step = TRV.ARROW_STEP_CTRL;
		TRV.moveSelectedNodes(step, 0);
	},

	moveLeft: function(ctx) {
		var step = TRV.ARROW_STEP;
		if (ctx.e.shiftKey) step = TRV.ARROW_STEP_SHIFT;
		if (ctx.e.ctrlKey || ctx.e.metaKey) step = TRV.ARROW_STEP_CTRL;
		TRV.moveSelectedNodes(-step, 0);
	},

	// -- Panels ---
	toggleXml: function() {
		document.getElementById('btn-panel').click();
	},
};

// -- Keyboard map ---------------------------------------------------
// Each entry: { key, ctrl, shift, alt, action, hasSelection, desc }
//   key:          KeyboardEvent.key value
//   ctrl:         requires Ctrl/Cmd (default: false)
//   hasSelection: only fires when nodes are selected (default: false)
//   action:       key into TRV.actions
//   desc:         human-readable description
TRV.keyMap = [
	// File
	{ key: 'o',         ctrl: true,  action: 'openFile',       desc: 'Open file' },
	{ key: 's',         ctrl: true,  action: 'saveFile',       desc: 'Save file' },
	{ key: 'e',         ctrl: true,  action: 'toggleXml',      desc: 'Toggle XML panel' },
	{ key: 'a',         ctrl: true,  action: 'selectAll',      desc: 'Select all nodes' },

	// View
	{ key: 'Home',                   action: 'fitToView',      desc: 'Fit to view' },
	{ key: 'a',                      action: 'zoomIn',         desc: 'Zoom in' },
	{ key: 'x',                      action: 'zoomOut',        desc: 'Zoom out' },

	// Selection
	{ key: 'Escape',                 action: 'clearSelection', desc: 'Clear selection' },

	// Node movement (only when nodes selected)
	{ key: 'ArrowUp',    hasSelection: true, action: 'moveUp',    desc: 'Move selected up' },
	{ key: 'ArrowDown',  hasSelection: true, action: 'moveDown',  desc: 'Move selected down' },
	{ key: 'ArrowRight', hasSelection: true, action: 'moveRight', desc: 'Move selected right' },
	{ key: 'ArrowLeft',  hasSelection: true, action: 'moveLeft',  desc: 'Move selected left' },
];

// -- Keyboard dispatch ----------------------------------------------
// Called from events.js keydown handler. Returns true if handled.
TRV.dispatchKey = function(e) {
	var isCtrl = e.ctrlKey || e.metaKey;
	var isTyping = (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT');

	for (var i = 0; i < TRV.keyMap.length; i++) {
		var b = TRV.keyMap[i];

		// Match key
		if (e.key !== b.key) continue;

		// Match modifier requirements
		if (b.ctrl && !isCtrl) continue;
		if (!b.ctrl && isCtrl) continue;

		// Skip if requires selection but none active
		if (b.hasSelection && TRV.state.selectedNodeIds.size === 0) continue;

		// Skip plain keys when typing in any text field
		if (isTyping && !b.ctrl) continue;

		e.preventDefault();
		var action = TRV.actions[b.action];
		if (action) action({ e: e });
		return true;
	}

	return false;
};

// -- Mouse action map -----------------------------------------------
// Descriptive reference; actual wiring in events.js.
//
//   Click         — select/deselect node
//   Shift+click   — additive node selection
//   Double-click  — select all nodes on clicked contour
//   Drag node     — move selected nodes
//   Shift+drag    — constrain to axis
//   Drag empty    — rectangle selection
//   Alt+drag      — lasso selection
//   Spacebar+drag — pan canvas
//   Scroll wheel  — zoom in/out
//   Ctrl+scroll   — rotate grid column (multi-view)
//   Alt+scroll    — rotate grid row (multi-view)

// -- Toolbar button map ---------------------------------------------
// { id, toggle, stateKey, action, desc }
// Buttons with toggle:true flip a state boolean and toggle .active class.
// Buttons with action call TRV.actions[action].
TRV.toolbarMap = [
	{ id: 'btn-load',    action: 'openFile',  desc: 'Load .trglyph file' },
	{ id: 'btn-save',    action: 'saveFile',  desc: 'Save .trglyph file' },
	{ id: 'btn-fit',     action: 'fitToView', desc: 'Fit glyph to view' },

	// Toggle buttons
	{ id: 'btn-nodes',   toggle: true, stateKey: 'showNodes',   desc: 'Toggle nodes' },
	{ id: 'btn-metrics', toggle: true, stateKey: 'showMetrics', desc: 'Toggle metrics' },
	{ id: 'btn-anchors', toggle: true, stateKey: 'showAnchors', desc: 'Toggle anchors' },
	{ id: 'btn-mask',    toggle: true, stateKey: 'showMask',    desc: 'Toggle mask' },

	// Fill/outline are exclusive pair — handled specially in events.js
	// View mode buttons (1×1, 2×1, 2×2) — handled specially in events.js
	// Join button — handled specially in events.js
	// XML button — has panel logic, handled specially in events.js
];

// -- Toolbar dispatch -----------------------------------------------
// Wire simple toolbar buttons. Call once during init.
TRV.wireToolbar = function() {
	for (var i = 0; i < TRV.toolbarMap.length; i++) {
		(function(entry) {
			var el = document.getElementById(entry.id);
			if (!el) return;

			el.addEventListener('click', function() {
				if (entry.toggle) {
					TRV.state[entry.stateKey] = !TRV.state[entry.stateKey];
					this.classList.toggle('active');
					TRV.draw();
				} else if (entry.action) {
					TRV.actions[entry.action]();
				}
			});
		})(TRV.toolbarMap[i]);
	}
};
