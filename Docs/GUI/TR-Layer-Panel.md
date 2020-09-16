# TypeRig GUI 

## TypeRig Panel

### Layer Panel
The Layer tab/subpanel is a special purpose tool for dealing with layers in Glyph Window (GW) as well as Font Window (FW). All of its actions are independent from [TypeRig panel masthead (MH)](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Panel-Basics) and work only on current active glyph.

![](./img/TR-Node-Layer-00.png)
_A typical view of Layer panel_

The Layer panel consists of two planes:
- **Layer selector plane**: A spreadsheet like representation of all layers that belong to currently active glyph. The plane allows sorting of layers by name or type by clicking on column head as well as multiple item selections;
- **Actions plane**: A collection of tools below that affect one or more layers selected.

#### Basic Tools (Layers selected)
![](./img/TR-Node-Layer-01.png)
_Basic operations for selected layers_

This section offers the following tools:
- **Add**: Will add a new layer with name predefined in _Suffix/Name_ text field;
- **Remove**: Will remove all layers selected;
- **Duplicate**: Will duplicate selected layers with all their properties and contents while adding suffix to each duplicate name specified in _Suffix/Name_ field;
- **Service**: Will convert all selected layers to _Service layers_
- **Mask**: Will create mask layers filled with current content for all layers selected;
- **Wireframe**: Will set all selected layers as _Wireframe layers_.

#### Content Tools (Active layer to/from selection)
![](./img/TR-Node-Layer-02.png)
_Content operations for selected layer_

As the name implies this tool offers content interaction between current active layer and a layer selected in the _Layer selector plane_. There are several options (check boxes) indicating the type of interaction: Outline; Guidelines; Anchors; Left side bearing (LSB), Right side bearing (RSB) or Advance width.

- **Swap**: Will swap the content chosen (in options check boxes) between current active layer and a layer selected in the _Layer selector plane_;
- **Copy**: Will copy the content chosen **from** layer selected in the _Layer selector plane_ **to** current active layer;
- **Paste**: Will copy the content chosen **from** current active layer **to** layer selected in the _Layer selector plane_ ;
- **Empty**: Will erase all content chosen for all layers selected in _Layer selector plane_ ;
- **Unlock**: Will unlock all content chosen for all layers selected in _Layer selector plane_ ;
- **Expand**: Will expand transformations of all content chosen for all layers selected in _Layer selector plane_ .

#### Layer multi editing (Layers selected)
![](./img/TR-Node-Layer-03.png)
_Tools for editing multiple layers_

Here reside several tools that are different in nature, but are grouped together for convenience:
- **Unfold layers**: Will modify the LSB + Advance of each layer selected in _Layer selector plane_ so that all of them are arranged one ofter the other along the baseline (in order of selection). This together with _FL's Edit between layers_ option will allow you to edit layers side by side or check them for compatibility;
- **Fold layers**: Will undo the above side by side arrangement and return LSB + Advance to original values.

![](./img/TR-Node-Layer-03A.png)
_View of a glyph with layers unfolded_

_Please note that the above functions will only work if the glyph does not have linked metrics!_

- **Copy outline**: Will copy the GW selected outlines to clipboard for each of the layers selected in _Layer selector plane_;
- **Paste outline**: Will paste outlines from clipboard if the current glyph has all the layers stored previously by _Copy outline_ operation.
_Please note the TR uses its own clipboard for the operations described, thus using FL's internal copy/paste functions will not work in conjunction with the above mentioned tools!_

The second part grouped under this sub-panel deals with layer affine transformations. There are several basic fields for entering data, each one of them representing a coordinate tuple (X, Y): Translate, scale, shear (slant) and rotate. There are two options that affect all layers selected in  _Layer selector plane_:
- **Transform layer**: Will transform the layer as a whole in accordance to layer origin point;
- **Transform elements**: Will transform each of the elements (shapes) the layer contains in accordance to its own origin point.


#### Interpolate/Blend (Selection to Active Layer)
![](./img/TR-Node-Layer-04.png)
_A simple layer blend tool_

This is a simple layer blend tool. It will create a single axis between current active layer and a layer selected in _Layer selector plane_ as if they reside on positions 0 and 1000.
- **Set Axis**: Will create a virtual axis as explained above;
- **Swap**: Will swap positions of the layers ( 0 -> 1000 and 1000 -> 0).
- Moving the **Slider** will automatically blend the above layers into current active layer.



**Panel development notes**
- Stability: High - no known issues major issues.
- Development priority: Low - not likely to be changed often.
- Future improvements: Most of the operations above (especially basic ones) will be moved to contextual menus of the _Layer selector plane_  thus opening more space for future tools. 
