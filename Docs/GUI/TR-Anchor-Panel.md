# TypeRig GUI 

## TypeRig Panel

### Anchor Panel
The Anchor tab/subpanel is a special purpose tool for dealing with anchors on glyph level. It works in Glyph Window (GW) as well as Font Window (FW) and most of its actions are governed by the TypeRig panel masthead (MH) unless specially noted. Use _Refresh button_ when moving onto another glyph. Trying to apply any action onto different glyph than the one shown will discard that action, rise a warning and refresh the panel. The Anchor tab consists of three main sections: anchor tree; anchor tree actions; Add/move/modify anchor;

![](./img/TR-Anchor-Panel-00.png)
_A typical view of Anchor panel_

#### The Anchor tree
The Anchor tree shows all of the glyph's master layers and their associated anchors in a spreadsheet like view. Anchors that are compatible (present) in all of the masters are marked green, those that are missing in one or several layers are marked red. 

![](./img/TR-Anchor-Panel-01.png)
_A typical view of Anchor tree with some anchors missing_

Fields showing anchor position across layers are editable and upon entry **will change** the coordinates of the anchor modified.

#### The Anchor tree actions
![](./img/TR-Anchor-Panel-02.png)

This part represents some basic actions:
- Copy: Will copy the selected anchors in memory so that they can be pasted/inserted into another glyph. Anchors are organized per layer. The action will not allow copy and pasting anchors between layers;
- Paste: Will paste the anchors found in memory into another glyph;
- Remove: Will remove the selected anchors in Anchor tree;
- Remove All: Will remove all anchors according to panel MH. For example running the action with _Active Glyph_ selected in MH will delete the anchors in the current active layer, while having _Masters_ selected in MH will delete all anchors on all masters.

#### Add/move/modify anchor
![](./img/TR-Anchor-Panel-03.png)
_An overlook of the Add/move/modify anchor part_

![](./img/TR-Anchor-Panel-03-A.png)
_Right click options of the Anchor name-filed_

![](./img/TR-Anchor-Panel-03-B.png)
_X positioning options_

![](./img/TR-Anchor-Panel-03-C.png)
_Y positioning options_




