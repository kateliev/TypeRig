// ===================================================================
// TypeRig Glyph Viewer — Pyodide Bridge
// ===================================================================
// Loads CPython via WebAssembly (Pyodide CDN), fetches TypeRig core
// from GitHub, and provides the JS ↔ Python interface.
// ===================================================================
'use strict';

TRV.pyBridge = {
	pyodide: null,
	ready: false,
	loading: false,
	error: null,

	// -- Configuration ---------------------------------------------------
	config: {
		repo: 'kateliev/TypeRig',
		branch: 'master',
		basePath: 'Lib',
	},

	// -- File manifest: only pure-Python core files ----------------------
	// Package __init__ files are stubbed to avoid pulling proxy/FL deps.
	manifest: [
		// Core objects
		'typerig/core/objects/atom.py',
		'typerig/core/objects/collection.py',
		'typerig/core/objects/point.py',
		'typerig/core/objects/line.py',
		'typerig/core/objects/cubicbezier.py',
		'typerig/core/objects/quadraticbezier.py',
		'typerig/core/objects/transform.py',
		'typerig/core/objects/utils.py',
		'typerig/core/objects/array.py',
		'typerig/core/objects/matrix.py',
		'typerig/core/objects/node.py',
		'typerig/core/objects/contour.py',
		'typerig/core/objects/shape.py',
		'typerig/core/objects/sdf.py',
		'typerig/core/objects/anchor.py',
		'typerig/core/objects/layer.py',
		'typerig/core/objects/glyph.py',
		'typerig/core/objects/delta.py',
		'typerig/core/objects/hobbyspline.py',

		// Core functions
		'typerig/core/func/math.py',
		'typerig/core/func/transform.py',
		'typerig/core/func/utils.py',
		'typerig/core/func/geometry.py',

		// File I/O
		'typerig/core/fileio/xmlio.py',
	],

	// -- Stub __init__.py contents ---------------------------------------
	// We stub these to avoid importing proxy/FL-dependent subpackages
	stubs: {
		'typerig/__init__.py':
			'# TypeRig — browser stub\n__version__ = "web"\n',

		'typerig/core/__init__.py':
			'# TypeRig / Core — browser stub\n',

		'typerig/core/objects/__init__.py':
			'from .node import Node\n' +
			'from .contour import Contour\n' +
			'from .shape import Shape\n' +
			'from .layer import Layer\n' +
			'from .glyph import Glyph\n' +
			'from .anchor import Anchor\n' +
			'__all__ = ["Node", "Contour", "Shape", "Layer", "Glyph", "Anchor"]\n',

		'typerig/core/func/__init__.py':
			'# TypeRig / Core / Func — browser stub\n',

		'typerig/core/fileio/__init__.py':
			'# TypeRig / Core / FileIO — browser stub\n',
	},

	// -- Build raw GitHub URL -------------------------------------------
	_rawUrl: function(filePath) {
		const c = this.config;
		return 'https://raw.githubusercontent.com/' +
			c.repo + '/' + c.branch + '/' + c.basePath + '/' + filePath;
	},

	// -- Initialize Pyodide + TypeRig -----------------------------------
	init: async function(onProgress) {
		if (this.ready || this.loading) return;
		this.loading = true;
		this.error = null;

		const log = onProgress || function() {};

		try {
			// 1. Load Pyodide runtime from CDN
			log('Loading Python runtime…');
			this.pyodide = await loadPyodide();
			log('Python runtime loaded.');

			// 2. Detect site-packages path dynamically
			const sitePackages = this.pyodide.runPython(
				'import site; site.getsitepackages()[0]'
			) + '/';

			// 3. Create directory structure in Pyodide virtual FS
			const dirs = [
				'typerig',
				'typerig/core',
				'typerig/core/objects',
				'typerig/core/func',
				'typerig/core/fileio',
			];

			for (const d of dirs) {
				try { this.pyodide.FS.mkdirTree(sitePackages + d); }
				catch (e) { /* already exists */ }
			}

			// 4. Write stub __init__.py files
			for (const [path, content] of Object.entries(this.stubs)) {
				this.pyodide.FS.writeFile(sitePackages + path, content);
			}

			// 5. Fetch real module files from GitHub (parallel)
			log('Fetching TypeRig core (' + this.manifest.length + ' files)…');

			const fetches = this.manifest.map(function(filePath) {
				return fetch(TRV.pyBridge._rawUrl(filePath))
					.then(function(r) {
						if (!r.ok) throw new Error(filePath + ': ' + r.status);
						return r.text();
					})
					.then(function(text) {
						return { path: filePath, text: text };
					});
			});

			const results = await Promise.all(fetches);

			for (const r of results) {
				this.pyodide.FS.writeFile(sitePackages + r.path, r.text);
			}

			log('TypeRig core installed (' + results.length + ' modules).');

			// 6. Bootstrap: import core, set up helpers
			this.pyodide.runPython(
				'import sys\n' +
				'from typerig.core.objects import Node, Contour, Shape, Layer, Glyph, Anchor\n' +
				'from typerig.core.objects.transform import Transform\n' +
				'from typerig.core.objects.delta import DeltaScale\n' +
				'from typerig.core.objects.point import Point\n' +
				'from typerig.core.objects.line import Line\n' +
				'from typerig.core.objects.array import PointArray\n' +
				'from typerig.core.fileio.xmlio import XMLSerializable\n' +
				'\n' +
				'# Glyph variable — synced with viewer\n' +
				'glyph = None\n' +
				'\n' +
				'print("TypeRig core ready — Python", sys.version.split()[0])\n' +
				'print("Available: Node, Contour, Shape, Layer, Glyph, Anchor")\n' +
				'print("           Transform, DeltaScale, Point, Line, PointArray")\n' +
				'print()\n'
			);

			this.ready = true;
			this.loading = false;
			log('Ready.');

		} catch (e) {
			this.error = e.message || String(e);
			this.loading = false;
			log('Error: ' + this.error);
			console.error('Pyodide bridge init failed:', e);
		}
	},

	// -- Sync viewer glyph → Python glyph variable ----------------------
	syncToPython: function() {
		if (!this.ready || !TRV.state.glyphData) return;

		const xml = TRV.glyphToXml(TRV.state.glyphData);
		this.pyodide.globals.set('_xml_in', xml);

		this.pyodide.runPython(
			'glyph = Glyph.from_XML(_xml_in)\n' +
			'del _xml_in\n'
		);
	},

	// -- Sync Python glyph → viewer state --------------------------------
	syncFromPython: function() {
		if (!this.ready) return false;

		try {
			const xml = this.pyodide.runPython('glyph.to_XML() if glyph else ""');
			if (!xml) return false;

			const newGlyph = TRV.parseGlyphXML(xml);
			TRV.state.glyphData = newGlyph;
			TRV.state.rawXml = xml;

			// Update layer selector
			const currentLayer = TRV.state.activeLayer;
			TRV.dom.layerSelect.innerHTML = '';
			for (const layer of newGlyph.layers) {
				const opt = document.createElement('option');
				opt.value = layer.name;
				opt.textContent = layer.name || '(unnamed)';
				TRV.dom.layerSelect.appendChild(opt);
			}

			if (newGlyph.layers.find(function(l) { return l.name === currentLayer; })) {
				TRV.dom.layerSelect.value = currentLayer;
			} else if (newGlyph.layers.length > 0) {
				TRV.state.activeLayer = newGlyph.layers[0].name;
				TRV.dom.layerSelect.value = TRV.state.activeLayer;
			}

			// Update glyph info
			let infoHtml = '<span>' + (newGlyph.name || '?') + '</span>';
			if (newGlyph.unicodes) infoHtml += ' U+' + newGlyph.unicodes;
			TRV.dom.glyphInfo.innerHTML = infoHtml;

			// Refresh XML panel if visible
			if (TRV.state.showXml && TRV.state.activePanel === 'xml') {
				TRV.buildXmlPanel();
			}

			TRV.draw();
			return true;

		} catch (e) {
			console.error('syncFromPython failed:', e);
			return false;
		}
	},

	// -- Execute user code -----------------------------------------------
	// Returns { output: string, error: string|null, glyphChanged: bool }
	run: function(code) {
		if (!this.ready) {
			return { output: '', error: 'Python not ready. Click Init to load.', glyphChanged: false };
		}

		// Sync current viewer state to Python
		this.syncToPython();

		// Capture stdout/stderr
		this.pyodide.runPython(
			'import io as _io, sys as _sys\n' +
			'_capture = _io.StringIO()\n' +
			'_old_stdout = _sys.stdout\n' +
			'_old_stderr = _sys.stderr\n' +
			'_sys.stdout = _capture\n' +
			'_sys.stderr = _capture\n'
		);

		var output = '';
		var error = null;
		var glyphChanged = false;

		try {
			this.pyodide.runPython(code);
			output = this.pyodide.runPython('_capture.getvalue()');

			// Try to get last expression value (REPL-style)
			// Only if there's no output already and code is a single expression
			if (!output) {
				const trimmed = code.trim();
				const lines = trimmed.split('\n');
				const lastLine = lines[lines.length - 1].trim();

				// If last line looks like an expression (not assignment, not keyword)
				if (lastLine &&
					!lastLine.startsWith('#') &&
					!lastLine.includes('=') &&
					!lastLine.startsWith('import ') &&
					!lastLine.startsWith('from ') &&
					!lastLine.startsWith('def ') &&
					!lastLine.startsWith('class ') &&
					!lastLine.startsWith('for ') &&
					!lastLine.startsWith('while ') &&
					!lastLine.startsWith('if ') &&
					!lastLine.startsWith('try:') &&
					!lastLine.startsWith('with ') &&
					!lastLine.startsWith('del ') &&
					!lastLine.startsWith('print(')) {
					try {
						const val = this.pyodide.runPython('repr(' + lastLine + ')');
						if (val && val !== 'None') output = val + '\n';
					} catch (_) { /* ignore — not a valid expression */ }
				}
			}

			// Sync glyph back if it changed
			glyphChanged = this.syncFromPython();

		} catch (e) {
			// Get any partial output
			try { output = this.pyodide.runPython('_capture.getvalue()'); }
			catch (_) { /* ignore */ }

			error = String(e.message || e);
			// Clean up Pyodide traceback noise
			error = error.replace(/^PythonError:\s*/i, '');
		}

		// Restore stdout/stderr
		try {
			this.pyodide.runPython(
				'_sys.stdout = _old_stdout\n' +
				'_sys.stderr = _old_stderr\n' +
				'del _capture, _old_stdout, _old_stderr, _io, _sys\n'
			);
		} catch (_) { /* safety net */ }

		return { output: output, error: error, glyphChanged: glyphChanged };
	},
};
