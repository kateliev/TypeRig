// ===================================================================
// TypeRig Glyph Viewer — Panel Bridge
// ===================================================================
// BroadcastChannel communication between main window and detached panel.
// Both windows load this file. Role determined by TRV.panelBridge.role.
// ===================================================================
'use strict';

(function() {

var CHANNEL_NAME = 'trv-panel-bridge';
var channel = null;
var detachedWindow = null;

// -- Bridge state on main window ------------------------------------
if (typeof TRV !== 'undefined') {
	TRV.panelBridge = {
		role: 'main',
		channel: null,
		detachedWindow: null,
		isDetached: false,
	};

	// -- Open detached panel ----------------------------------------
	TRV.detachPanel = function() {
		if (TRV.panelBridge.isDetached && TRV.panelBridge.detachedWindow &&
			!TRV.panelBridge.detachedWindow.closed) {
			TRV.panelBridge.detachedWindow.focus();
			return;
		}

		// Open the panel page
		var w = 500, h = window.innerHeight;
		var left = window.screenX + window.innerWidth;
		var top = window.screenY;
		TRV.panelBridge.detachedWindow = window.open(
			'panel.html', 'trv-panel',
			'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top +
			',menubar=no,toolbar=no,status=no'
		);

		// Create channel
		if (!TRV.panelBridge.channel) {
			TRV.panelBridge.channel = new BroadcastChannel(CHANNEL_NAME);
			TRV.panelBridge.channel.onmessage = function(e) {
				TRV._panelReceive(e.data);
			};
		}

		TRV.panelBridge.isDetached = true;

		// Hide inline panel
		TRV.state.showXml = false;
		TRV.dom.sidePanel.classList.remove('visible');
		TRV.dom.splitHandle.classList.remove('visible');
		TRV.dom.sidePanel.style.width = '';

		// Update button state
		var btn = document.getElementById('btn-panel');
		btn.classList.add('detached');
		btn.classList.remove('active');

		requestAnimationFrame(function() { TRV.draw(); });

		// Send initial state after a short delay (panel needs to load)
		setTimeout(function() { TRV._panelSendState(); }, 500);
	};

	// -- Reattach panel to inline -----------------------------------
	TRV.attachPanel = function() {
		if (TRV.panelBridge.detachedWindow && !TRV.panelBridge.detachedWindow.closed) {
			TRV.panelBridge.detachedWindow.close();
		}
		TRV.panelBridge.detachedWindow = null;
		TRV.panelBridge.isDetached = false;

		var btn = document.getElementById('btn-panel');
		btn.classList.remove('detached');

		// Close channel
		if (TRV.panelBridge.channel) {
			TRV.panelBridge.channel.close();
			TRV.panelBridge.channel = null;
		}
	};

	// -- Send current glyph state to detached panel -----------------
	TRV._panelSendState = function() {
		if (!TRV.panelBridge.isDetached || !TRV.panelBridge.channel) return;

		// Generate fresh XML
		var xml = '';
		if (TRV.state.glyphData) {
			xml = TRV.formatXml(TRV.glyphToXml(TRV.state.glyphData));
		}

		var layer = TRV.getActiveLayer();
		var allNodes = layer ? TRV.getAllNodes(layer) : [];
		var onCount = allNodes.filter(function(n) { return n.type === 'on'; }).length;

		TRV.panelBridge.channel.postMessage({
			type: 'stateUpdate',
			xml: xml,
			glyphName: TRV.state.glyphData ? (TRV.state.glyphData.name || '?') : '',
			activeLayer: TRV.state.activeLayer || '',
			nodeCount: { on: onCount, off: allNodes.length - onCount },
		});
	};

	// -- Send selection highlight to detached panel ------------------
	TRV._panelSendSelection = function() {
		if (!TRV.panelBridge.isDetached || !TRV.panelBridge.channel) return;

		var ids = [];
		for (var id of TRV.state.selectedNodeIds) ids.push(id);

		TRV.panelBridge.channel.postMessage({
			type: 'selectionChanged',
			ids: ids,
		});
	};

	// -- Receive messages from detached panel ------------------------
	TRV._panelReceive = function(msg) {
		if (msg.type === 'xmlApply') {
			// Panel edited XML → apply to glyph
			TRV.dom.xmlContent.value = msg.xml;
			TRV.xmlApply();
		} else if (msg.type === 'xmlRefresh') {
			// Panel requests fresh XML
			TRV._panelSendState();
		} else if (msg.type === 'panelReady') {
			// Panel loaded, send initial state
			TRV._panelSendState();
		} else if (msg.type === 'panelClosed') {
			TRV.attachPanel();
		}
	};

	// -- Hook into existing functions to broadcast changes -----------
	var origBuildXmlPanel = TRV.buildXmlPanel;
	TRV.buildXmlPanel = function() {
		origBuildXmlPanel.call(TRV);
		if (TRV.panelBridge.isDetached) TRV._panelSendState();
	};

	var origHighlightXmlNode = TRV.highlightXmlNode;
	TRV.highlightXmlNode = function(nodeId) {
		origHighlightXmlNode.call(TRV, nodeId);
		// Send to detached panel even if inline panel is hidden
		if (TRV.panelBridge.isDetached) TRV._panelSendSelection();
	};
}

})();
