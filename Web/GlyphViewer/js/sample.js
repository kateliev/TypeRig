// ===================================================================
// TypeRig Glyph Viewer — Sample Data & Init
// ===================================================================
'use strict';

// Provide a sample glyph so the viewer isn't empty on first load
TRV.loadSampleGlyph = function() {
	const sampleXml = `<?xml version="1.0" encoding="UTF-8"?>
<glyph name="A" unicodes="0041" mark="0">
  <layer name="Regular" width="680" height="700">
    <shape name="main">
      <contour>
        <node x="340" y="700" type="on"/>
        <node x="20" y="0" type="on"/>
        <node x="120" y="0" type="on"/>
        <node x="197" y="200" type="on"/>
        <node x="483" y="200" type="on"/>
        <node x="560" y="0" type="on"/>
        <node x="660" y="0" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
      <contour>
        <node x="222" y="270" type="on"/>
        <node x="340" y="580" type="on"/>
        <node x="458" y="270" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
    </shape>
    <shape name="crossbar">
      <contour>
        <node x="170" y="310" type="on"/>
        <node x="510" y="310" type="on"/>
        <node x="490" y="380" type="on"/>
        <node x="190" y="380" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
    </shape>
    <anchor name="top" x="340" y="710"/>
    <anchor name="bottom" x="340" y="-10"/>
    <lib>
      <dict>
        <key>stx</key>
        <integer>90</integer>
        <key>sty</key>
        <integer>80</integer>
      </dict>
    </lib>
  </layer>
  <layer name="Bold" width="750" height="700">
    <shape name="main">
      <contour>
        <node x="375" y="700" type="on"/>
        <node x="10" y="0" type="on"/>
        <node x="150" y="0" type="on"/>
        <node x="235" y="200" type="on"/>
        <node x="515" y="200" type="on"/>
        <node x="600" y="0" type="on"/>
        <node x="740" y="0" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
      <contour>
        <node x="267" y="275" type="on"/>
        <node x="375" y="545" type="on"/>
        <node x="483" y="275" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
    </shape>
    <shape name="crossbar">
      <contour>
        <node x="200" y="310" type="on"/>
        <node x="550" y="310" type="on"/>
        <node x="520" y="400" type="on"/>
        <node x="230" y="400" type="on"/>
        <lib>
          <dict>
            <key>closed</key>
            <true/>
          </dict>
        </lib>
      </contour>
    </shape>
    <anchor name="top" x="375" y="710"/>
    <anchor name="bottom" x="375" y="-10"/>
    <lib>
      <dict>
        <key>stx</key>
        <integer>140</integer>
        <key>sty</key>
        <integer>120</integer>
      </dict>
    </lib>
  </layer>
</glyph>`;

	TRV.loadXmlString(sampleXml, 'sample_A.trglyph');
};

// -- Init -----------------------------------------------------------
TRV.loadSampleGlyph();
