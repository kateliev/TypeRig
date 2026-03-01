// ===================================================================
// TypeRig Glyph Viewer — Sample Data & Init
// ===================================================================
'use strict';

// Provide a sample glyph so the viewer isn't empty on first load
TRV.loadSampleGlyph = function() {
	const sampleXml = `<?xml version="1.0" encoding="UTF-8"?>
<glyph mark="0" name="a" selected="False" unicodes="[97]">
	<layer height="0" name="Light" width="534">
		<shape name="">
			<contour clockwise="False" closed="True" name="">
				<node smooth="True" type="on" x="57" y="130"/>
				<node smooth="False" type="curve" x="57" y="55"/>
				<node smooth="False" type="curve" x="101" y="-10"/>
				<node smooth="True" type="on" x="228" y="-10"/>
				<node smooth="False" type="curve" x="250" y="-10"/>
				<node smooth="False" type="curve" x="288" y="-8"/>
				<node smooth="False" type="on" x="319" y="4"/>
				<node smooth="False" type="on" x="378" y="65"/>
				<node smooth="False" type="on" x="383" y="65"/>
				<node smooth="False" type="on" x="393" y="0"/>
				<node smooth="False" type="on" x="498" y="0"/>
				<node smooth="False" type="on" x="503" y="26"/>
				<node smooth="False" type="on" x="433" y="40"/>
				<node smooth="False" type="on" x="433" y="303"/>
				<node smooth="False" type="curve" x="433" y="417"/>
				<node smooth="False" type="curve" x="370" y="461"/>
				<node smooth="True" type="on" x="276" y="461"/>
				<node smooth="False" type="curve" x="227" y="461"/>
				<node smooth="False" type="curve" x="143" y="449"/>
				<node smooth="False" type="on" x="80" y="422"/>
				<node smooth="False" type="on" x="90" y="300"/>
				<node smooth="False" type="on" x="124" y="305"/>
				<node smooth="False" type="on" x="134" y="403"/>
				<node smooth="False" type="curve" x="162" y="416"/>
				<node smooth="False" type="curve" x="227" y="423"/>
				<node smooth="True" type="on" x="263" y="423"/>
				<node smooth="False" type="curve" x="356" y="423"/>
				<node smooth="False" type="curve" x="383" y="378"/>
				<node smooth="False" type="on" x="383" y="270"/>
				<node smooth="False" type="on" x="291" y="270"/>
				<node smooth="False" type="curve" x="197" y="270"/>
				<node smooth="False" type="curve" x="57" y="263"/>
			</contour>
			<contour clockwise="True" closed="True" name="">
				<node smooth="False" type="on" x="134" y="215"/>
				<node smooth="False" type="curve" x="175" y="228"/>
				<node smooth="False" type="curve" x="242" y="232"/>
				<node smooth="True" type="on" x="283" y="232"/>
				<node smooth="False" type="on" x="383" y="232"/>
				<node smooth="False" type="on" x="383" y="124"/>
				<node smooth="False" type="curve" x="352" y="62"/>
				<node smooth="False" type="curve" x="298" y="28"/>
				<node smooth="True" type="on" x="232" y="28"/>
				<node smooth="False" type="curve" x="149" y="28"/>
				<node smooth="False" type="curve" x="113" y="83"/>
				<node smooth="True" type="on" x="113" y="138"/>
				<node smooth="False" type="curve" x="113" y="156"/>
				<node smooth="False" type="curve" x="117" y="193"/>
			</contour>
		</shape>
		<anchor name="top" x="261" y="550"/>
		<anchor name="bottom" x="498" y="0"/>
	</layer>
	<layer height="0" name="Bold" width="624">
		<shape name="">
			<contour clockwise="False" closed="True" name="">
				<node smooth="True" type="on" x="45" y="144"/>
				<node smooth="False" type="curve" x="45" y="35"/>
				<node smooth="False" type="curve" x="138" y="-7"/>
				<node smooth="True" type="on" x="235" y="-7"/>
				<node smooth="False" type="curve" x="256" y="-7"/>
				<node smooth="False" type="curve" x="282" y="-5"/>
				<node smooth="False" type="on" x="311" y="0"/>
				<node smooth="False" type="on" x="375" y="78"/>
				<node smooth="False" type="on" x="385" y="78"/>
				<node smooth="False" type="on" x="398" y="0"/>
				<node smooth="False" type="on" x="590" y="0"/>
				<node smooth="False" type="on" x="595" y="94"/>
				<node smooth="False" type="on" x="545" y="104"/>
				<node smooth="False" type="on" x="545" y="309"/>
				<node smooth="False" type="curve" x="545" y="473"/>
				<node smooth="False" type="curve" x="424" y="491"/>
				<node smooth="True" type="on" x="324" y="491"/>
				<node smooth="False" type="curve" x="230" y="491"/>
				<node smooth="False" type="curve" x="156" y="475"/>
				<node smooth="False" type="on" x="74" y="443"/>
				<node smooth="False" type="on" x="84" y="315"/>
				<node smooth="False" type="on" x="224" y="325"/>
				<node smooth="False" type="on" x="234" y="372"/>
				<node smooth="False" type="curve" x="247" y="377"/>
				<node smooth="False" type="curve" x="273" y="381"/>
				<node smooth="True" type="on" x="300" y="381"/>
				<node smooth="False" type="curve" x="360" y="381"/>
				<node smooth="False" type="curve" x="375" y="361"/>
				<node smooth="False" type="on" x="375" y="295"/>
				<node smooth="False" type="on" x="301" y="295"/>
				<node smooth="False" type="curve" x="192" y="295"/>
				<node smooth="False" type="curve" x="45" y="281"/>
			</contour>
			<contour clockwise="True" closed="True" name="">
				<node smooth="False" type="on" x="229" y="197"/>
				<node smooth="False" type="curve" x="269" y="197"/>
				<node smooth="False" type="curve" x="291" y="197"/>
				<node smooth="True" type="on" x="323" y="197"/>
				<node smooth="False" type="on" x="375" y="197"/>
				<node smooth="False" type="on" x="375" y="164"/>
				<node smooth="False" type="curve" x="353" y="127"/>
				<node smooth="False" type="curve" x="317" y="103"/>
				<node smooth="True" type="on" x="272" y="103"/>
				<node smooth="False" type="curve" x="227" y="103"/>
				<node smooth="False" type="curve" x="216" y="128"/>
				<node smooth="True" type="on" x="216" y="151"/>
				<node smooth="False" type="curve" x="216" y="168"/>
				<node smooth="False" type="curve" x="222" y="184"/>
			</contour>
		</shape>
		<anchor name="top" x="297" y="550"/>
		<anchor name="bottom" x="590" y="0"/>
	</layer>
</glyph>`;

	TRV.loadXmlString(sampleXml, 'sample_A.trglyph');
};

// -- Init -----------------------------------------------------------
TRV.loadSampleGlyph();
