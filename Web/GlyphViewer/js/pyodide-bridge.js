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
		var c = this.config;
		return 'https://raw.githubusercontent.com/' +
			c.repo + '/' + c.branch + '/' + c.basePath + '/' + filePath;
	},

	// -- Initialize Pyodide + TypeRig -----------------------------------
	init: async function(onProgress) {
		if (this.ready || this.loading) return;
		this.loading = true;
		this.error = null;

		var log = onProgress || function() {};

		try {
			// 1. Load Pyodide runtime from CDN
			log('Loading Python runtime…');
			this.pyodide = await loadPyodide();
			log('Python runtime loaded.');

			// 2. Detect site-packages path dynamically
			var sitePackages = this.pyodide.runPython(
				'import site; site.getsitepackages()[0]'
			) + '/';

			// 3. Create directory structure in Pyodide virtual FS
			var dirs = [
				'typerig',
				'typerig/core',
				'typerig/core/objects',
				'typerig/core/func',
				'typerig/core/fileio',
			];

			for (var i = 0; i < dirs.length; i++) {
				try { this.pyodide.FS.mkdirTree(sitePackages + dirs[i]); }
				catch (e) { /* already exists */ }
			}

			// 4. Write stub __init__.py files
			for (var path in this.stubs) {
				this.pyodide.FS.writeFile(sitePackages + path, this.stubs[path]);
			}

			// 5. Fetch real module files from GitHub (parallel)
			log('Fetching TypeRig core (' + this.manifest.length + ' files)…');

			var fetches = this.manifest.map(function(filePath) {
				return fetch(TRV.pyBridge._rawUrl(filePath))
					.then(function(r) {
						if (!r.ok) throw new Error(filePath + ': ' + r.status);
						return r.text();
					})
					.then(function(text) {
						return { path: filePath, text: text };
					});
			});

			var results = await Promise.all(fetches);

			for (var j = 0; j < results.length; j++) {
				this.pyodide.FS.writeFile(sitePackages + results[j].path, results[j].text);
			}

			log('TypeRig core installed (' + results.length + ' modules).');

			// 6. Bootstrap: import core, set up bridge helpers
			this.pyodide.runPython([
				'import sys',
				'from typerig.core.objects import Node, Contour, Shape, Layer, Glyph, Anchor',
				'from typerig.core.objects.transform import Transform',
				'from typerig.core.objects.delta import DeltaScale',
				'from typerig.core.objects.point import Point',
				'from typerig.core.objects.line import Line',
				'from typerig.core.objects.array import PointArray',
				'from typerig.core.fileio.xmlio import XMLSerializable',
				'',
				'# Glyph variable — synced with viewer',
				'glyph = None',
				'',
				'# -- Selection bridge helpers --',
				'def _set_selection(id_list, layer_name=None):',
				'\t"""Set node selection from JS id list [\'c0_n3\', ...]"""',
				'\tif glyph is None: return',
				'\t# Clear all selection first',
				'\tfor layer in glyph.layers:',
				'\t\tfor shape in layer.shapes:',
				'\t\t\tfor contour in shape.contours:',
				'\t\t\t\tfor node in contour.data:',
				'\t\t\t\t\tnode.selected = False',
				'\t# Set selection on active layer only',
				'\tlayer = glyph.layer(layer_name) if layer_name else (glyph.layers[0] if glyph.layers else None)',
				'\tif layer is None: return',
				'\tselected = set(id_list)',
				'\tci = 0',
				'\tfor shape in layer.shapes:',
				'\t\tfor contour in shape.contours:',
				'\t\t\tfor ni, node in enumerate(contour.data):',
				'\t\t\t\tnode.selected = ("c%d_n%d" % (ci, ni)) in selected',
				'\t\t\tci += 1',
				'',
				'def _get_selection(layer_name=None):',
				'\t"""Get selected node ids as list [\'c0_n3\', ...]"""',
				'\tif glyph is None: return []',
				'\tlayer = glyph.layer(layer_name) if layer_name else (glyph.layers[0] if glyph.layers else None)',
				'\tif layer is None: return []',
				'\tresult = []',
				'\tci = 0',
				'\tfor shape in layer.shapes:',
				'\t\tfor contour in shape.contours:',
				'\t\t\tfor ni, node in enumerate(contour.data):',
				'\t\t\t\tif getattr(node, "selected", False):',
				'\t\t\t\t\tresult.append("c%d_n%d" % (ci, ni))',
				'\t\t\tci += 1',
				'\treturn result',
				'',
				'print("TypeRig core ready — Python", sys.version.split()[0])',
				'print("Available: Node, Contour, Shape, Layer, Glyph, Anchor")',
				'print("           Transform, DeltaScale, Point, Line, PointArray")',
				'print("Selection: glyph.selected_nodes, node.selected")',
				'print()',
			].join('\n'));

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
	// Also syncs selection state (not in XML, passed separately)
	syncToPython: function() {
		if (!this.ready || !TRV.state.glyphData) return;

		// Serialize current viewer glyph to XML
		var xml = TRV.glyphToXml(TRV.state.glyphData);
		this.pyodide.globals.set('_xml_in', xml);

		this.pyodide.runPython(
			'glyph = Glyph.from_XML(_xml_in)\n' +
			'del _xml_in\n'
		);

		// Sync selection: JS selectedNodeIds → Python node.selected
		var selIds = Array.from(TRV.state.selectedNodeIds);
		var activeName = TRV.state.activeLayer || '';
		this.pyodide.globals.set('_sel_ids', selIds);
		this.pyodide.globals.set('_sel_layer', activeName);
		this.pyodide.runPython(
			'_set_selection(_sel_ids.to_py(), _sel_layer)\n' +
			'del _sel_ids, _sel_layer\n'
		);
	},

	// -- Sync Python glyph → viewer state --------------------------------
	// Reads XML and selection back from Python, updates viewer + canvas
	syncFromPython: function() {
		if (!this.ready) return false;

		try {
			var xml = this.pyodide.runPython(
				'glyph.to_XML() if glyph is not None else ""'
			);

			if (!xml) return false;

			var newGlyph = TRV.parseGlyphXML(xml);

			TRV.state.glyphData = newGlyph;
			TRV.state.rawXml = xml;

			// Sync selection: Python node.selected → JS selectedNodeIds
			var activeName = TRV.state.activeLayer || '';
			this.pyodide.globals.set('_sel_layer', activeName);
			var pySelRaw = this.pyodide.runPython(
				'_get_selection(_sel_layer)'
			);
			this.pyodide.runPython('del _sel_layer');
			// Pyodide may return a JsProxy for lists — convert to native JS
			var pySel = pySelRaw && pySelRaw.toJs ? pySelRaw.toJs() : pySelRaw;
			if (Array.isArray(pySel)) {
				TRV.state.selectedNodeIds = new Set(pySel);
			}

			// Update layer selector
			var currentLayer = TRV.state.activeLayer;
			TRV.dom.layerSelect.innerHTML = '';
			for (var i = 0; i < newGlyph.layers.length; i++) {
				var layer = newGlyph.layers[i];
				var opt = document.createElement('option');
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
			var infoHtml = '<span>' + (newGlyph.name || '?') + '</span>';
			if (newGlyph.unicodes) infoHtml += ' U+' + newGlyph.unicodes;
			TRV.dom.glyphInfo.innerHTML = infoHtml;

			// Refresh XML panel if visible
			if (TRV.state.showXml && TRV.state.activePanel === 'xml') {
				TRV.buildXmlPanel();
			}

			// Force canvas redraw on next frame
			requestAnimationFrame(function() { TRV.draw(); });

			// Update status bar selection count
			if (TRV.updateStatusSelected) TRV.updateStatusSelected();

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

		// Sync current viewer state → Python (glyph + selection)
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
			// Use AST to separate exec from final expression eval.
			// This avoids re-executing the last line for repr display.
			this.pyodide.globals.set('_user_code', code);

			this.pyodide.runPython([
				'_user_result = None',
				'import ast as _ast',
				'try:',
				'\t_tree = _ast.parse(_user_code)',
				'\t# If last statement is a bare expression, eval it separately',
				'\tif _tree.body and isinstance(_tree.body[-1], _ast.Expr):',
				'\t\t_last_expr = _tree.body.pop()',
				'\t\t# Exec everything before the last expression',
				'\t\tif _tree.body:',
				'\t\t\texec(compile(_tree, "<repl>", "exec"))',
				'\t\t# Eval last expression for display',
				'\t\t_expr_tree = _ast.Expression(body=_last_expr.value)',
				'\t\t_user_result = eval(compile(_expr_tree, "<repl>", "eval"))',
				'\telse:',
				'\t\texec(compile(_tree, "<repl>", "exec"))',
				'except SyntaxError:',
				'\t# Fallback: just exec the whole thing',
				'\texec(compile(_user_code, "<repl>", "exec"))',
				'del _user_code, _ast',
			].join('\n'));

			output = this.pyodide.runPython('_capture.getvalue()');

			// Show REPL result (last expression value) if no print output
			if (!output) {
				try {
					var result = this.pyodide.runPython(
						'repr(_user_result) if _user_result is not None else ""'
					);
					if (result) output = result + '\n';
				} catch (_) { /* no result */ }
			}

		} catch (e) {
			// Get any partial output
			try { output = this.pyodide.runPython('_capture.getvalue()'); }
			catch (_) { /* ignore */ }

			error = String(e.message || e);
			// Clean up Pyodide traceback noise
			error = error.replace(/^PythonError:\s*/i, '');
		}

		// Restore stdout/stderr (always, even after error)
		try {
			this.pyodide.runPython(
				'_sys.stdout = _old_stdout\n' +
				'_sys.stderr = _old_stderr\n' +
				'del _capture, _old_stdout, _old_stderr, _io, _sys\n' +
				'try:\n\tdel _user_result\nexcept: pass\n'
			);
		} catch (_) { /* safety net */ }

		// Always sync back — even after errors, partial mutations
		// may have occurred before the exception
		glyphChanged = this.syncFromPython();

		return { output: output, error: error, glyphChanged: glyphChanged };
	},
};
