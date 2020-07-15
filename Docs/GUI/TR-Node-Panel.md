# TypeRig GUI 

## TypeRig Panel

### Node Panel
The Node tab/subpanel is a special purpose tool for dealing with outlines in Glyph Window (GW). All of its actions are governed by the [TypeRig panel masthead (MH)](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Panel-Basics).

![](./img/TR-Node-Panel-00.png)
_A typical view of Node panel_

#### Nodes: Basic operations
![](./img/TR-Node-Panel-01.png)
_Basic operations section of Node panel_

This section offers the following tools:
- **Insert**: Will insert a node after the currently selected one at time **T**_(set in the editing field next to the button)_;
- **Remove**: Will remove a the currently selected node;
- **Mitre**: Will create a corner miter at the currently selected node with length **X** _(set in the editing field next to the button)_;
- **Overlap**: Will create a corner overlap (knot) at selected node with length **X** _(set in the editing field before to the button)_;
- **Trap**: Will create an ink-trap at the currently selected node with parameters **P** - a comma separated list containing incision into glyphs flesh, side depth and trap bottom size;
- **Rebuild**: Will rebuild any _structure_ into a proper corner. Requires all nodes that should collapse into a corner to be selected. _For example will rebuild a mitered corner or an ink-trap_.

#### Nodes: Align
![](./img/TR-Node-Panel-02.png)
_Node alignment operations section of Node panel_

- **Left**: Will align all selected nodes to the leftmost node in selection;
- **Right**: Will align all selected nodes to the rightmost node in selection;
- **Top**: Will align all selected nodes to the highest node in selection;
- **Bottom**: Will align all selected nodes to the lowest node in selection;
- **Selection: Center X**: Aligns to the X center of all selected nodes;
- **Selection: Center Y**: Aligns to the Y center of all selected nodes;
- **Outline: Center X**: Aligns to the X center of the whole outline;
- **Outline: Center Y**: Aligns to the Y center of the whole outline;
- **Neighbors: Center X**: Aligns each selected node to the X center of its neighboring nodes _(prev node + next node)_;
- **Neighbors: Center Y**: Aligns each selected node to the Y center of its neighboring nodes _(prev node + next node)_.

#### Nodes: Align to Font and Glyph metrics
![](./img/TR-Node-Panel-03.png)
_Advanced alignment options with Node panel_

This section allows alignment of selected nodes to known glyph and font metrics. In addition to the TR Masthead control options there are two more special modes:
- **Keep relations**: Allows for keeping the relations between all selected nodes. _For example selecting all nodes that make the horizontal stem of an /H and clicking "Caps" will move the selected nodes keeping the stem in tact until its upper part is aligned with Caps Height thus transforming the /H into /Pe-cyr_;
- **Intercept**: Will extend any selected node until it intercepts the desired metric target. _Imagine just deleting the serif of the /K's leg. Clicking "Base" with this option active will extend the leg until it reaches the baseline_;
- **None of the above**: All nodes will be just shifted to the desired position.

Alignment options are:
- **Asc.**: Ascender position;
- **Caps**: Caps height position;
- **Desc.**: Descender position;
- **X Hgt.**: X-height;
- **Base**: Baseline;
- **Y Pos**: Will align to any Y position specified with the spin-box before the button;
- **Measure**: Will align to the Y position of the measurement line.
- **Vertical** _(row)_: Aligns to a percent + adjustment (in units) of measured _BBox_ or _advance width_ of the currently active glyph;
- **Horizontal** _(row)_: offers the same functionality as explained above, but for _BBox height_, _vertical font metrics_ and _advance height_.



**Panel development notes**
- Stability: High - no known issues major issues.
- Development priority: Low - not likely to be changed often.
- Future improvements: Better and smarter nodes copy/paste tools.
