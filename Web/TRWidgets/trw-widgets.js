// ===================================================================
// TypeRig Widgets (TRW) — Reusable UI Gadget Library
// ===================================================================
// Qt-style widget factories for dark-themed web UIs.
// All widgets return plain DOM elements; no framework dependency.
//
// Icon system: TRW.icon(name) returns an SVG element.
// To switch to a custom icon font later, override TRW.icon().
// ===================================================================
'use strict';

var TRW = TRW || {};

// -- Configuration --------------------------------------------------
TRW.config = {
	iconFont: null,  // Set to font-family string to use icon font instead of SVG
};

// ===================================================================
// ICON SYSTEM
// ===================================================================
// SVG icon paths. Each is a viewBox="0 0 24 24" stroke path.
// To add a custom icon font: set TRW.config.iconFont and map
// glyph codepoints in TRW.iconGlyphs.
TRW.iconPaths = {
	plus:            'M12 5v14M5 12h14',
	minus:           'M5 12h14',
	chevronDown:     'M6 9l6 6 6-6',
	chevronRight:    'M9 6l6 6-6 6',
	chevronUp:       'M6 15l6-6 6 6',
	close:           'M18 6L6 18M6 6l12 12',
	check:           'M5 12l5 5L20 7',
	search:          'M11 4a7 7 0 110 14 7 7 0 010-14zM18 18l3 3',
	sliders:         'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
	doubleLeft:      'M11 17l-5-5 5-5M18 17l-5-5 5-5',
	doubleRight:     'M13 7l5 5-5 5M6 7l5 5-5 5',
	arrowLeft:       'M19 12H5M12 5l-7 7 7 7',
	arrowRight:      'M5 12h14M12 5l7 7-7 7',
};

// Future icon font glyph map (codepoints)
TRW.iconGlyphs = {};

// Create an icon element by name
TRW.icon = function(name) {
	// If icon font is configured, use a span
	if (TRW.config.iconFont && TRW.iconGlyphs[name]) {
		var span = document.createElement('span');
		span.className = 'trw-icon trw-icon-font';
		span.style.fontFamily = TRW.config.iconFont;
		span.textContent = TRW.iconGlyphs[name];
		return span;
	}

	// Default: inline SVG
	var path = TRW.iconPaths[name];
	if (!path) return null;

	var wrap = document.createElement('span');
	wrap.className = 'trw-icon';
	wrap.innerHTML = '<svg viewBox="0 0 24 24">' +
		'<path d="' + path + '"/>' +
		'</svg>';
	return wrap;
};

// ===================================================================
// LABEL
// ===================================================================
TRW.Label = function(text, opts) {
	opts = opts || {};
	var el = document.createElement('span');
	el.className = 'trw-label';
	el.textContent = text;

	if (opts.heading) el.classList.add('trw-label--heading');
	if (opts.mono)    el.classList.add('trw-label--mono');
	if (opts.dim)     el.classList.add('trw-label--dim');
	if (opts.tooltip) el.title = opts.tooltip;

	return el;
};

// ===================================================================
// BUTTON
// ===================================================================
TRW.Button = function(text, opts) {
	opts = opts || {};
	var el = document.createElement('button');
	el.className = 'trw-btn';
	el.type = 'button';

	if (opts.icon) {
		var ic = TRW.icon(opts.icon);
		if (ic) el.appendChild(ic);
	}

	if (text) {
		var span = document.createElement('span');
		span.textContent = text;
		el.appendChild(span);
	}

	if (!text && opts.icon) el.classList.add('trw-btn--icon');
	if (opts.primary)       el.classList.add('trw-btn--primary');
	if (opts.compact)       el.classList.add('trw-btn--compact');
	if (opts.tooltip)       el.title = opts.tooltip;
	if (opts.disabled)      el.disabled = true;
	if (opts.onClick)       el.addEventListener('click', opts.onClick);

	return el;
};

// ===================================================================
// TOGGLE BUTTON
// ===================================================================
TRW.ToggleButton = function(text, opts) {
	opts = opts || {};
	var el = TRW.Button(text, opts);
	el.classList.add('trw-toggle');

	if (opts.active) el.classList.add('active');

	var _onChange = opts.onChange || null;

	el.addEventListener('click', function() {
		el.classList.toggle('active');
		if (_onChange) _onChange(el.classList.contains('active'));
	});

	// API
	el.getValue = function() { return el.classList.contains('active'); };
	el.setValue = function(v) { el.classList.toggle('active', !!v); };

	return el;
};

// ===================================================================
// SPIN BOX (integer)
// ===================================================================
TRW.SpinBox = function(opts) {
	opts = opts || {};
	var min  = opts.min !== undefined ? opts.min : 0;
	var max  = opts.max !== undefined ? opts.max : 100;
	var val  = opts.value !== undefined ? opts.value : 0;
	var step = opts.step || 1;
	var _onChange = opts.onChange || null;

	var wrap = document.createElement('div');
	wrap.className = 'trw-spinbox';

	var btnDec = document.createElement('button');
	btnDec.className = 'trw-spinbox__btn trw-spinbox__btn--dec';
	btnDec.type = 'button';
	btnDec.textContent = '\u2212'; // minus sign

	var input = document.createElement('input');
	input.className = 'trw-spinbox__input';
	input.type = 'text';
	input.value = val;

	var suffixEl = null;
	if (opts.suffix) {
		suffixEl = document.createElement('span');
		suffixEl.className = 'trw-spinbox__suffix';
		suffixEl.textContent = opts.suffix;
	}

	var btnInc = document.createElement('button');
	btnInc.className = 'trw-spinbox__btn trw-spinbox__btn--inc';
	btnInc.type = 'button';
	btnInc.textContent = '+';

	wrap.appendChild(btnDec);
	wrap.appendChild(input);
	if (suffixEl) wrap.appendChild(suffixEl);
	wrap.appendChild(btnInc);

	function clamp(v) { return Math.max(min, Math.min(max, v)); }

	function setValue(v, notify) {
		v = clamp(Math.round(v));
		input.value = v;
		if (notify !== false && _onChange) _onChange(v);
	}

	btnDec.addEventListener('click', function() { setValue(parseInt(input.value, 10) - step); });
	btnInc.addEventListener('click', function() { setValue(parseInt(input.value, 10) + step); });

	input.addEventListener('change', function() {
		var v = parseInt(input.value, 10);
		if (isNaN(v)) v = val;
		setValue(v);
	});

	input.addEventListener('keydown', function(e) {
		if (e.key === 'ArrowUp')   { e.preventDefault(); setValue(parseInt(input.value, 10) + step); }
		if (e.key === 'ArrowDown') { e.preventDefault(); setValue(parseInt(input.value, 10) - step); }
	});

	// API
	wrap.getValue = function() { return parseInt(input.value, 10); };
	wrap.setValue = function(v) { setValue(v, false); };
	wrap.setRange = function(mn, mx) { min = mn; max = mx; setValue(clamp(parseInt(input.value, 10))); };
	wrap.input = input;

	if (opts.tooltip) wrap.title = opts.tooltip;
	return wrap;
};

// ===================================================================
// DOUBLE SPIN BOX (float)
// ===================================================================
TRW.DoubleSpinBox = function(opts) {
	opts = opts || {};
	var min  = opts.min !== undefined ? opts.min : 0;
	var max  = opts.max !== undefined ? opts.max : 100;
	var val  = opts.value !== undefined ? opts.value : 0;
	var step = opts.step || 0.1;
	var decimals = opts.decimals !== undefined ? opts.decimals : 2;
	var _onChange = opts.onChange || null;

	var wrap = document.createElement('div');
	wrap.className = 'trw-spinbox';

	var btnDec = document.createElement('button');
	btnDec.className = 'trw-spinbox__btn trw-spinbox__btn--dec';
	btnDec.type = 'button';
	btnDec.textContent = '\u2212';

	var input = document.createElement('input');
	input.className = 'trw-spinbox__input';
	input.type = 'text';
	input.value = val.toFixed(decimals);

	var suffixEl = null;
	if (opts.suffix) {
		suffixEl = document.createElement('span');
		suffixEl.className = 'trw-spinbox__suffix';
		suffixEl.textContent = opts.suffix;
	}

	var btnInc = document.createElement('button');
	btnInc.className = 'trw-spinbox__btn trw-spinbox__btn--inc';
	btnInc.type = 'button';
	btnInc.textContent = '+';

	wrap.appendChild(btnDec);
	wrap.appendChild(input);
	if (suffixEl) wrap.appendChild(suffixEl);
	wrap.appendChild(btnInc);

	function clamp(v) { return Math.max(min, Math.min(max, v)); }

	function setValue(v, notify) {
		v = clamp(parseFloat(v.toFixed(decimals)));
		input.value = v.toFixed(decimals);
		if (notify !== false && _onChange) _onChange(v);
	}

	btnDec.addEventListener('click', function() { setValue(parseFloat(input.value) - step); });
	btnInc.addEventListener('click', function() { setValue(parseFloat(input.value) + step); });

	input.addEventListener('change', function() {
		var v = parseFloat(input.value);
		if (isNaN(v)) v = val;
		setValue(v);
	});

	input.addEventListener('keydown', function(e) {
		if (e.key === 'ArrowUp')   { e.preventDefault(); setValue(parseFloat(input.value) + step); }
		if (e.key === 'ArrowDown') { e.preventDefault(); setValue(parseFloat(input.value) - step); }
	});

	// API
	wrap.getValue = function() { return parseFloat(input.value); };
	wrap.setValue = function(v) { setValue(v, false); };
	wrap.setRange = function(mn, mx) { min = mn; max = mx; setValue(clamp(parseFloat(input.value))); };
	wrap.input = input;

	if (opts.tooltip) wrap.title = opts.tooltip;
	return wrap;
};

// ===================================================================
// EDIT FIELD (line edit)
// ===================================================================
TRW.EditField = function(opts) {
	opts = opts || {};

	var wrap = document.createElement('div');
	wrap.className = 'trw-edit';

	var input = document.createElement('input');
	input.className = 'trw-edit__input';
	input.type = 'text';
	if (opts.value)       input.value = opts.value;
	if (opts.placeholder) input.placeholder = opts.placeholder;
	if (opts.mono)        input.classList.add('trw-edit__input--mono');
	if (opts.onChange)    input.addEventListener('input', function() { opts.onChange(input.value); });

	wrap.appendChild(input);
	wrap.style.width = opts.width || '';

	// API
	wrap.getValue = function() { return input.value; };
	wrap.setValue = function(v) { input.value = v; };
	wrap.input = input;

	if (opts.tooltip) wrap.title = opts.tooltip;
	return wrap;
};

// ===================================================================
// COMBO BOX
// ===================================================================
TRW.ComboBox = function(opts) {
	opts = opts || {};

	var wrap = document.createElement('div');
	wrap.className = 'trw-combo';

	var select = document.createElement('select');
	select.className = 'trw-combo__select';

	var items = opts.items || [];
	for (var i = 0; i < items.length; i++) {
		var opt = document.createElement('option');
		if (typeof items[i] === 'object') {
			opt.value = items[i].value;
			opt.textContent = items[i].label;
		} else {
			opt.value = items[i];
			opt.textContent = items[i];
		}
		select.appendChild(opt);
	}

	if (opts.value !== undefined) select.value = opts.value;
	if (opts.onChange) select.addEventListener('change', function() { opts.onChange(select.value); });

	wrap.appendChild(select);
	wrap.style.minWidth = opts.width || '';

	// API
	wrap.getValue = function() { return select.value; };
	wrap.setValue = function(v) { select.value = v; };
	wrap.select = select;

	if (opts.tooltip) wrap.title = opts.tooltip;
	return wrap;
};

// ===================================================================
// LIST WIDGET
// ===================================================================
TRW.ListWidget = function(opts) {
	opts = opts || {};

	var wrap = document.createElement('div');
	wrap.className = 'trw-list';
	if (opts.height) wrap.style.maxHeight = opts.height;

	var _selected = -1;
	var _items = [];
	var _onChange = opts.onChange || null;

	function render() {
		wrap.innerHTML = '';
		var data = opts.items || [];
		_items = [];

		if (data.length === 0) {
			var empty = document.createElement('div');
			empty.className = 'trw-list__item trw-list__item--empty';
			empty.textContent = opts.emptyText || '(empty)';
			wrap.appendChild(empty);
			return;
		}

		for (var i = 0; i < data.length; i++) {
			(function(idx) {
				var item = document.createElement('div');
				item.className = 'trw-list__item';
				item.textContent = data[idx];
				if (idx === _selected) item.classList.add('active');

				item.addEventListener('click', function() {
					_selected = idx;
					render();
					if (_onChange) _onChange(idx, data[idx]);
				});

				wrap.appendChild(item);
				_items.push(item);
			})(i);
		}
	}

	render();

	// API
	wrap.getSelected = function() { return _selected; };
	wrap.setItems = function(items) { opts.items = items; _selected = -1; render(); };
	wrap.refresh = render;

	return wrap;
};

// ===================================================================
// SLIDER CONTROLLER
// Mirrors TRSliderCtrl + TRCustomSpinController from Qt.
// Layout: [label] [spinbox] [−10] [−1] [+1] [+10]
//         [min] [=====slider=====] [max]
// ===================================================================
TRW.SliderCtrl = function(opts) {
	opts = opts || {};
	var min  = opts.min !== undefined ? opts.min : 0;
	var max  = opts.max !== undefined ? opts.max : 100;
	var val  = opts.value !== undefined ? opts.value : 50;
	var step = opts.step || 1;
	var decimals = opts.decimals || 0;
	var _onChange = opts.onChange || null;

	var wrap = document.createElement('div');
	wrap.className = 'trw-slider-ctrl';

	// -- Top row: label + spinbox + ±1/±10 buttons
	var topRow = document.createElement('div');
	topRow.className = 'trw-slider-ctrl__top';

	if (opts.label) {
		var lbl = document.createElement('span');
		lbl.className = 'trw-slider-ctrl__label';
		lbl.textContent = opts.label;
		topRow.appendChild(lbl);
	}

	var spinOpts = {
		min: min, max: max, value: val, step: step,
		suffix: opts.suffix,
		onChange: function(v) { updateAll(v, 'spin'); }
	};

	var spin = decimals > 0
		? TRW.DoubleSpinBox(Object.assign(spinOpts, { decimals: decimals }))
		: TRW.SpinBox(spinOpts);
	topRow.appendChild(spin);

	// Increment buttons: −10, −1, +1, +10
	var btnDec10 = TRW.Button('\u226210', { compact: true, tooltip: '-10',
		onClick: function() { updateAll(getCurrentVal() - 10, 'btn'); }
	});
	var btnDec1 = TRW.Button('\u22121', { compact: true, tooltip: '-1',
		onClick: function() { updateAll(getCurrentVal() - step, 'btn'); }
	});
	var btnInc1 = TRW.Button('+1', { compact: true, tooltip: '+1',
		onClick: function() { updateAll(getCurrentVal() + step, 'btn'); }
	});
	var btnInc10 = TRW.Button('+10', { compact: true, tooltip: '+10',
		onClick: function() { updateAll(getCurrentVal() + 10, 'btn'); }
	});

	topRow.appendChild(btnDec10);
	topRow.appendChild(btnDec1);
	topRow.appendChild(btnInc1);
	topRow.appendChild(btnInc10);
	wrap.appendChild(topRow);

	// -- Bottom row: min field + slider + max field
	var trackRow = document.createElement('div');
	trackRow.className = 'trw-slider-ctrl__track-row';

	var edtMin = document.createElement('input');
	edtMin.className = 'trw-slider-ctrl__minmax';
	edtMin.type = 'text';
	edtMin.value = min;

	var slider = document.createElement('input');
	slider.className = 'trw-slider-ctrl__slider';
	slider.type = 'range';
	slider.min = min;
	slider.max = max;
	slider.step = decimals > 0 ? step : step;
	slider.value = val;

	var edtMax = document.createElement('input');
	edtMax.className = 'trw-slider-ctrl__minmax';
	edtMax.type = 'text';
	edtMax.value = max;

	trackRow.appendChild(edtMin);
	trackRow.appendChild(slider);
	trackRow.appendChild(edtMax);
	wrap.appendChild(trackRow);

	// -- Wiring
	function getCurrentVal() {
		return decimals > 0 ? parseFloat(spin.getValue()) : parseInt(spin.getValue(), 10);
	}

	function clamp(v) { return Math.max(min, Math.min(max, v)); }

	function updateAll(v, source) {
		v = clamp(decimals > 0 ? parseFloat(v.toFixed(decimals)) : Math.round(v));
		if (source !== 'spin') spin.setValue(v);
		if (source !== 'slider') slider.value = v;
		if (_onChange) _onChange(v);
	}

	slider.addEventListener('input', function() {
		updateAll(decimals > 0 ? parseFloat(slider.value) : parseInt(slider.value, 10), 'slider');
	});

	edtMin.addEventListener('change', function() {
		min = parseFloat(edtMin.value) || 0;
		slider.min = min;
		spin.setRange(min, max);
		updateAll(clamp(getCurrentVal()), 'minmax');
	});

	edtMax.addEventListener('change', function() {
		max = parseFloat(edtMax.value) || 100;
		slider.max = max;
		spin.setRange(min, max);
		updateAll(clamp(getCurrentVal()), 'minmax');
	});

	// API
	wrap.getValue = function() { return getCurrentVal(); };
	wrap.setValue = function(v) { updateAll(v, 'api'); };
	wrap.spin = spin;
	wrap.slider = slider;

	if (opts.tooltip) wrap.title = opts.tooltip;
	return wrap;
};

// ===================================================================
// TREE WIDGET (planned — basic expandable structure)
// ===================================================================
TRW.TreeWidget = function(opts) {
	opts = opts || {};
	var wrap = document.createElement('div');
	wrap.className = 'trw-tree';

	var _data = opts.data || [];
	var _onChange = opts.onChange || null;

	function render() {
		wrap.innerHTML = '';

		for (var i = 0; i < _data.length; i++) {
			var node = _data[i];
			var isExpanded = node.expanded !== false;

			// Parent node
			var row = document.createElement('div');
			row.className = 'trw-tree__node';

			if (node.children && node.children.length > 0) {
				var toggle = document.createElement('span');
				toggle.className = 'trw-tree__toggle' + (isExpanded ? ' expanded' : '');
				toggle.textContent = '\u25B6'; // right triangle
				row.appendChild(toggle);

				(function(idx) {
					toggle.addEventListener('click', function(e) {
						e.stopPropagation();
						_data[idx].expanded = !_data[idx].expanded;
						render();
					});
				})(i);
			} else {
				var spacer = document.createElement('span');
				spacer.className = 'trw-tree__toggle';
				row.appendChild(spacer);
			}

			var label = document.createElement('span');
			label.textContent = node.label || node.text || '';
			row.appendChild(label);

			(function(idx) {
				row.addEventListener('click', function() {
					if (_onChange) _onChange(idx, _data[idx]);
				});
			})(i);

			wrap.appendChild(row);

			// Children
			if (isExpanded && node.children) {
				for (var c = 0; c < node.children.length; c++) {
					var child = node.children[c];
					var childRow = document.createElement('div');
					childRow.className = 'trw-tree__node trw-tree__node--child';

					var childLabel = document.createElement('span');
					childLabel.textContent = child.label || child.text || '';
					childRow.appendChild(childLabel);

					(function(pi, ci) {
						childRow.addEventListener('click', function() {
							if (_onChange) _onChange(pi, child, ci);
						});
					})(i, c);

					wrap.appendChild(childRow);
				}
			}
		}
	}

	render();

	// API
	wrap.setData = function(data) { _data = data; render(); };
	wrap.refresh = render;

	return wrap;
};

// ===================================================================
// TABLE WIDGET (planned — basic structure)
// ===================================================================
TRW.TableWidget = function(opts) {
	opts = opts || {};
	var table = document.createElement('table');
	table.className = 'trw-table';

	var _columns = opts.columns || [];
	var _rows = opts.rows || [];
	var _onChange = opts.onChange || null;

	function render() {
		table.innerHTML = '';

		// Header
		if (_columns.length > 0) {
			var thead = document.createElement('thead');
			var tr = document.createElement('tr');
			for (var c = 0; c < _columns.length; c++) {
				var th = document.createElement('th');
				th.textContent = _columns[c];
				tr.appendChild(th);
			}
			thead.appendChild(tr);
			table.appendChild(thead);
		}

		// Body
		var tbody = document.createElement('tbody');
		for (var r = 0; r < _rows.length; r++) {
			var row = document.createElement('tr');
			for (var c2 = 0; c2 < (_rows[r].length || 0); c2++) {
				var td = document.createElement('td');
				td.textContent = _rows[r][c2];
				row.appendChild(td);
			}
			(function(idx) {
				row.addEventListener('click', function() {
					// Toggle active
					var rows = tbody.querySelectorAll('tr');
					for (var k = 0; k < rows.length; k++) rows[k].classList.remove('active');
					row.classList.add('active');
					if (_onChange) _onChange(idx, _rows[idx]);
				});
			})(r);
			tbody.appendChild(row);
		}
		table.appendChild(tbody);
	}

	render();

	// API
	table.setData = function(columns, rows) { _columns = columns; _rows = rows; render(); };
	table.refresh = render;

	return table;
};

// ===================================================================
// COMBINED: SPIN BUTTON (spinbox + action button)
// ===================================================================
TRW.SpinButton = function(buttonText, opts) {
	opts = opts || {};

	var wrap = document.createElement('div');
	wrap.className = 'trw-spin-button';

	var spin = TRW.SpinBox({
		min: opts.min, max: opts.max,
		value: opts.value, step: opts.step,
		suffix: opts.suffix,
		onChange: opts.onSpinChange,
	});

	var btn = document.createElement('button');
	btn.className = 'trw-spin-button__action';
	btn.type = 'button';
	btn.textContent = buttonText;
	if (opts.onClick) btn.addEventListener('click', function() {
		opts.onClick(spin.getValue());
	});

	wrap.appendChild(spin);
	wrap.appendChild(btn);

	// API
	wrap.getValue = function() { return spin.getValue(); };
	wrap.setValue = function(v) { spin.setValue(v); };
	wrap.spin = spin;
	wrap.button = btn;

	return wrap;
};

// ===================================================================
// COMBINED: FLOW RIBBON (stretchable, reflowable button strip)
// ===================================================================
TRW.FlowRibbon = function(opts) {
	opts = opts || {};

	var wrap = document.createElement('div');
	wrap.className = 'trw-ribbon';

	// API: add widgets to the ribbon
	wrap.addWidget = function(widget) {
		wrap.appendChild(widget);
		return wrap;
	};

	wrap.addSeparator = function() {
		var sep = document.createElement('div');
		sep.className = 'trw-separator';
		wrap.appendChild(sep);
		return wrap;
	};

	return wrap;
};

// ===================================================================
// DIALOG (simple modal)
// ===================================================================
TRW.Dialog = function(opts) {
	opts = opts || {};

	var backdrop = document.createElement('div');
	backdrop.className = 'trw-dialog-backdrop';

	var dialog = document.createElement('div');
	dialog.className = 'trw-dialog';

	// Header
	var header = document.createElement('div');
	header.className = 'trw-dialog__header';

	var title = document.createElement('span');
	title.className = 'trw-dialog__title';
	title.textContent = opts.title || 'Dialog';

	var closeBtn = document.createElement('button');
	closeBtn.className = 'trw-dialog__close';
	closeBtn.type = 'button';
	closeBtn.textContent = '\u00D7'; // ×

	header.appendChild(title);
	header.appendChild(closeBtn);
	dialog.appendChild(header);

	// Body
	var body = document.createElement('div');
	body.className = 'trw-dialog__body';

	if (typeof opts.body === 'string') {
		body.innerHTML = opts.body;
	} else if (opts.body instanceof HTMLElement) {
		body.appendChild(opts.body);
	}

	dialog.appendChild(body);

	// Footer (optional buttons)
	if (opts.buttons) {
		var footer = document.createElement('div');
		footer.className = 'trw-dialog__footer';

		for (var i = 0; i < opts.buttons.length; i++) {
			var bCfg = opts.buttons[i];
			var btn = TRW.Button(bCfg.text, {
				primary: bCfg.primary,
				onClick: (function(cb) {
					return function() { if (cb) cb(); api.close(); };
				})(bCfg.onClick),
			});
			footer.appendChild(btn);
		}

		dialog.appendChild(footer);
	}

	backdrop.appendChild(dialog);

	// Close logic
	closeBtn.addEventListener('click', function() { api.close(); });
	backdrop.addEventListener('click', function(e) {
		if (e.target === backdrop) api.close();
	});

	// API
	var api = {
		el: backdrop,
		body: body,
		open: function() {
			document.body.appendChild(backdrop);
			requestAnimationFrame(function() {
				backdrop.classList.add('visible');
			});
		},
		close: function() {
			backdrop.classList.remove('visible');
			setTimeout(function() {
				if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
			}, 180);
			if (opts.onClose) opts.onClose();
		},
	};

	return api;
};

// ===================================================================
// UTILITY: Row (label + widget helper)
// ===================================================================
TRW.Row = function(labelText, widget) {
	var row = document.createElement('div');
	row.className = 'trw-row';
	row.appendChild(TRW.Label(labelText));
	row.appendChild(widget);
	return row;
};

TRW.Section = function(titleText) {
	var sec = document.createElement('div');
	sec.className = 'trw-section';
	var t = document.createElement('span');
	t.className = 'trw-section__title';
	t.textContent = titleText;
	sec.appendChild(t);
	return sec;
};
