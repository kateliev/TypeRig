// ===================================================================
// TypeRig Glyph Viewer — Python Panel
// ===================================================================
// REPL interface: code input, output history, tab switching.
// Depends on pyodide-bridge.js for execution.
// ===================================================================
'use strict';

// -- Panel tab switching ------------------------------------------------
TRV.initPanelTabs = function() {
	const tabs = document.querySelectorAll('.panel-tab');
	tabs.forEach(function(tab) {
		tab.addEventListener('click', function() {
			TRV.switchPanelTab(this.dataset.panel);
		});
	});
};

TRV.switchPanelTab = function(tabName) {
	TRV.state.activePanel = tabName;

	// Update tab buttons
	document.querySelectorAll('.panel-tab').forEach(function(tab) {
		tab.classList.toggle('active', tab.dataset.panel === tabName);
	});

	// Update tab content
	document.querySelectorAll('.panel-content').forEach(function(panel) {
		panel.classList.toggle('active', panel.id === tabName + '-tab');
	});

	// Update tab-specific info in header
	const xmlInfo = document.getElementById('xml-tab-info');
	const pyInfo = document.getElementById('py-tab-info');
	if (xmlInfo) xmlInfo.style.display = tabName === 'xml' ? '' : 'none';
	if (pyInfo) pyInfo.style.display = tabName === 'python' ? '' : 'none';

	// Rebuild XML panel content if switching to XML tab
	if (tabName === 'xml' && TRV.state.showXml) {
		TRV.buildXmlPanel();
	}

	// Focus input if switching to Python
	if (tabName === 'python') {
		const input = document.getElementById('py-input');
		if (input) setTimeout(function() { input.focus(); }, 50);
	}
};

// -- Python REPL --------------------------------------------------------
TRV.pyPanel = {
	history: [],
	historyIdx: -1,

	// -- Initialize Pyodide (triggered by user) -------------------------
	init: async function() {
		const btn = document.getElementById('py-init-btn');
		const output = document.getElementById('py-output');
		const input = document.getElementById('py-input');

		if (TRV.pyBridge.ready) return;
		if (TRV.pyBridge.loading) return;

		btn.textContent = 'Loading…';
		btn.disabled = true;

		await TRV.pyBridge.init(function(msg) {
			TRV.pyPanel.appendOutput(msg, 'info');
		});

		if (TRV.pyBridge.ready) {
			btn.style.display = 'none';
			input.disabled = false;
			input.placeholder = '>>> Python — Shift+Enter to run';
			input.focus();

			// Sync current glyph if loaded
			if (TRV.state.glyphData) {
				TRV.pyBridge.syncToPython();
				TRV.pyPanel.appendOutput('glyph synced from viewer.', 'info');
			}

			TRV.pyPanel.updateStatus('ready');
		} else {
			btn.textContent = 'Retry Init';
			btn.disabled = false;
			TRV.pyPanel.updateStatus('error');
		}
	},

	// -- Execute code from input ----------------------------------------
	execute: function() {
		const input = document.getElementById('py-input');
		const code = input.value.trim();
		if (!code) return;

		// Show input in output area
		TRV.pyPanel.appendOutput(code, 'input');

		// Save to history
		this.history.push(code);
		this.historyIdx = this.history.length;

		// Run
		const result = TRV.pyBridge.run(code);

		if (result.output) {
			TRV.pyPanel.appendOutput(result.output, 'output');
		}

		if (result.error) {
			TRV.pyPanel.appendOutput(result.error, 'error');
		}

		if (result.glyphChanged) {
			TRV.pyPanel.appendOutput('↻ glyph updated in viewer', 'info');
		}

		// Clear input
		input.value = '';
		TRV.pyPanel.autoResize(input);
	},

	// -- Output helpers -------------------------------------------------
	appendOutput: function(text, type) {
		const output = document.getElementById('py-output');
		if (!output) return;

		const entry = document.createElement('div');
		entry.className = 'py-entry py-' + (type || 'output');

		if (type === 'input') {
			// Format as prompt
			const lines = text.split('\n');
			const formatted = lines.map(function(line, i) {
				return (i === 0 ? '>>> ' : '... ') + line;
			}).join('\n');
			entry.textContent = formatted;
		} else {
			entry.textContent = text;
		}

		output.appendChild(entry);

		// Auto-scroll to bottom
		output.scrollTop = output.scrollHeight;
	},

	clearOutput: function() {
		const output = document.getElementById('py-output');
		if (output) output.innerHTML = '';
	},

	// -- History navigation (up/down arrows) ----------------------------
	historyUp: function() {
		if (this.history.length === 0) return;
		if (this.historyIdx > 0) this.historyIdx--;

		const input = document.getElementById('py-input');
		input.value = this.history[this.historyIdx] || '';
		TRV.pyPanel.autoResize(input);
	},

	historyDown: function() {
		if (this.history.length === 0) return;
		this.historyIdx++;

		const input = document.getElementById('py-input');
		if (this.historyIdx >= this.history.length) {
			this.historyIdx = this.history.length;
			input.value = '';
		} else {
			input.value = this.history[this.historyIdx] || '';
		}
		TRV.pyPanel.autoResize(input);
	},

	// -- Status indicator -----------------------------------------------
	updateStatus: function(status) {
		const el = document.getElementById('py-status');
		if (!el) return;

		const labels = {
			'idle': 'Not loaded',
			'ready': 'Ready',
			'error': 'Error',
		};

		el.textContent = labels[status] || status;
		el.className = 'py-status py-status--' + status;
	},

	// -- Auto-resize input textarea -------------------------------------
	autoResize: function(textarea) {
		textarea.style.height = 'auto';
		const maxH = 160; // max ~8 lines
		textarea.style.height = Math.min(textarea.scrollHeight, maxH) + 'px';
	},
};

// -- Wire Python panel events -------------------------------------------
TRV.wirePythonPanel = function() {
	const input = document.getElementById('py-input');
	const initBtn = document.getElementById('py-init-btn');
	const clearBtn = document.getElementById('py-clear-btn');

	if (!input) return;

	// Shift+Enter to execute, Enter for newline
	input.addEventListener('keydown', function(e) {
		if (e.key === 'Enter' && e.shiftKey) {
			e.preventDefault();
			TRV.pyPanel.execute();
		}

		// Arrow up in empty single-line input → history
		if (e.key === 'ArrowUp' && !e.shiftKey && input.value.indexOf('\n') === -1) {
			const pos = input.selectionStart;
			if (pos === 0) {
				e.preventDefault();
				TRV.pyPanel.historyUp();
			}
		}

		// Arrow down in empty single-line input → history
		if (e.key === 'ArrowDown' && !e.shiftKey && input.value.indexOf('\n') === -1) {
			const pos = input.selectionStart;
			if (pos === input.value.length) {
				e.preventDefault();
				TRV.pyPanel.historyDown();
			}
		}
	});

	// Auto-resize on input
	input.addEventListener('input', function() {
		TRV.pyPanel.autoResize(this);
	});

	// Init button
	if (initBtn) {
		initBtn.addEventListener('click', function() {
			TRV.pyPanel.init();
		});
	}

	// Clear button
	if (clearBtn) {
		clearBtn.addEventListener('click', function() {
			TRV.pyPanel.clearOutput();
		});
	}
};
