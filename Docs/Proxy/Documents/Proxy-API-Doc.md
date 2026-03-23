# Typerig FontLab Proxy API Reference

This document provides a comprehensive API reference for the Typerig FontLab proxy module (`typerig.proxy.fl`), which wraps FontLab 6 API objects with enhanced functionality.

## Table of Contents
1. [Module Structure](#module-structure)
2. [Base Objects](#base-objects)
3. [Node Objects](#node-objects)
4. [Contour Objects](#contour-objects)
5. [Curve Objects](#curve-objects)
6. [Shape Objects](#shape-objects)
7. [Glyph Objects](#glyph-objects)
8. [Font Objects](#font-objects)
9. [Kerning Objects](#kerning-objects)
10. [Application/Workspace](#applicationworkspace)
11. [Action Collectors](#action-collectors)
12. [GUI Widgets](#gui-widgets)
13. [Pens](#pens)
14. [Design Patterns](#design-patterns)

---

## Module Structure

```
typerig.proxy.fl/
├── objects/          # Proxy classes for FontLab objects
│   ├── base.py       # Coord, Line, Vector, Curve (geometric primitives)
│   ├── node.py       # pNode, eNode, pNodesContainer, eNodesContainer
│   ├── contour.py    # pContour, eContour
│   ├── curve.py      # eCurveEx
│   ├── shape.py      # pShape, eShape
│   ├── glyph.py      # pGlyph, eGlyph
│   ├── font.py       # pFont, eFont, jFont, pFontMetrics
│   ├── kern.py       # pKerning
│   ├── string.py     # Constants and OTGen for OpenType features
│   ├── sampler.py     # GlyphSampler, MetricSampler
│   └── composer.py    # dictComposer
├── actions/          # Action collectors (tool implementations)
│   ├── node.py       # TRNodeActionCollector
│   ├── contour.py    # TRContourActionCollector
│   ├── curve.py      # TRCurveActionCollector
│   ├── layer.py      # TRLayerActionCollector
│   └── draw.py       # TRDrawActionCollector
├── gui/              # Qt GUI components
│   ├── widgets.py    # Custom widgets and controls
│   ├── dialogs.py    # Dialog classes
│   ├── styles.py     # CSS styles
│   ├── drawing.py    # Icon drawing utilities
│   ├── QtGui.py      # Qt compatibility layer
├── application/      # Application-level proxies
│   ├── app.py        # pWorkspace, pItems, pTextBlock
│   └── automat.py    # Automat (FL action runner)
└── pens/            # Pen protocol implementations
    ├── abstractPen.py # AbstractPen, AbstractPointPen
    └── outlinePen.py  # OutlinePen
```

---

## Base Objects

### Geometric Primitives (`objects/base.py`)

All geometric primitives extend Typerig core objects with FontLab conversion capabilities.

#### `Coord` (extends `trPoint`)
Coordinate point with FontLab and Qt conversions.

```python
from typerig.proxy.fl.objects.base import Coord

# Constructor variants
c1 = Coord(100, 200)                    # x, y
c2 = Coord((100, 200))                # tuple
c3 = Coord([100, 200])                # list
c4 = Coord(fl6.flNode)                # flNode
c5 = Coord(QPointF)                    # Qt point
```

**Methods:**
- `asQPointF() -> QPointF` - Convert to Qt QPointF
- `asQPoint() -> QPointF` - Convert to Qt QPointF
- `asflNode() -> flNode` - Convert to FontLab node

#### `Line` (extends `Line`)
Line segment with FontLab and Qt conversions.

```python
from typerig.proxy.fl.objects.base import Line

# Constructor variants
l1 = Line(0, 0, 100, 200)            # x1, y1, x2, y2
l2 = Line(coord1, coord2)             # two Coords
l3 = Line(curveEx)                  # flCurveEx
l4 = Line(node1, node2)              # two flNodes
```

**Methods:**
- `asQLineF() -> QLineF` - Convert to Qt QLineF
- `asQPoint() -> list[QPointF]` - Convert to Qt points
- `asflNode() -> list[flNode]` - Convert to FontLab nodes

#### `Vector` (extends `Vector`)
Direction vector with FontLab and Qt conversions.

#### `Curve` (extends `CubicBezier`)
Cubic Bezier curve with FontLab conversion.

```python
from typerig.proxy.fl.objects.base import Curve

# Constructor variants
cv1 = Curve(p0, bcp1, bcp2, p3)      # four points
cv2 = Curve([(x,y)...])            # list of tuples
cv3 = Curve(curveEx)                # flCurveEx
```

**Methods:**
- `asflNode() -> list[flNode]` - Convert to FontLab nodes (4 nodes)

---

## Node Objects

### `pNode` (`objects/node.py`)

Basic proxy to `flNode`.

```python
from typerig.proxy.fl.objects.node import pNode

node = pNode(fl_node)  # Wrap flNode
```

**Properties (read/write):**
- `x, y` - Node coordinates
- `index` - Node index in contour
- `name` - Node name/tag
- `smooth` - Smooth flag
- `type` - Node type
- `selected` - Selection state
- `time` - Position along contour (0-1)
- `isOn` - Whether node is on-curve
- `angle` - Node angle
- `tuple` - (x, y) tuple
- `parent, contour` - Parent contour

**Methods:**

```python
# Navigation
getNext(naked=True)           # Next node (True=raw flNode)
getPrev(naked=True)         # Previous node
getNextOn(naked=True)       # Next on-curve node
getPrevOn(naked=True)       # Previous on-curve node
getOn(naked=True)           # Get on-curve node

# Geometry
getTime()                   # Position along contour
getSegment(relativeTime=0)   # Get segment containing node
getSegmentNodes(relativeTime=0)  # Get all nodes in segment
distanceTo(node)             # Distance to another node
distanceToNext()            # Distance to next node
distanceToPrev()            # Distance to previous node
angleTo(node)               # Angle to another node
angleToNext()               # Angle to next node
angleToPrev()               # Angle to previous node

# Modification
reloc(newX, newY)           # Move to new coordinates
shift(deltaX, deltaY)       # Shift by delta
smartReloc(newX, newY)      # Move with BCPs
smartShift(deltaX, deltaY)  # Shift with BCPs
randomize(cx, cy, bleed_mode=0)  # Randomize with constraints
remove()                     # Remove node from contour
update()                     # Update node

# Insertion
insertAfter(time)            # Insert after this node
insertBefore(time)           # Insert before this node
insertAfterDist(distance)   # Insert at distance
insertBeforeDist(distance)   # Insert at distance from prev

# Smart angle
getSmartAngle()             # Get smart angle (radius)
setSmartAngle(radius)       # Enable smart angle
delSmartAngle()             # Disable smart angle
```

### `eNode` (extends `pNode`)

Extended node with advanced functionality.

```python
from typerig.proxy.fl.objects.node import eNode

node = eNode(fl_node)
```

**Additional Methods:**
```python
# Conversion
asCoord()                   # Return Coord object
getNextLine()               # Line to next on-curve
getPrevLine()               # Line from prev on-curve
getNextOffLine()            # Line to next (any)
getPrevOffLine()            # Line from prev (any)

# Delta operations
diffTo(node)                # (dx, dy) to node
diffToNext()                # (dx, dy) to next
diffToPrev()                # (dx, dy) to prev
shiftFromNext(diffX, diffY) # Shift relative to next
shiftFromPrev(diffX, diffY) # Shift relative to prev

# Polar operations
polarTo(node)               # (angle, distance) to node
polarToNext()               # (angle, distance) to next
polarToPrev()               # (angle, distance) to prev
polarReloc(angle, distance)  # Move by polar coords
smartPolarReloc(angle, distance)  # With BCPs

# Corner operations
cornerMitre(mitreSize=5, isRadius=False)  # Mitre corner
cornerRound(size=5., proportion=None, curvature=(1.,1.), isRadius=False, insert=True)  # Round corner
cornerTrap(aperture=10, depth=20, trap=2)  # Trap corner
cornerTrapInc(incision=10, depth=50, trap=2, smooth=True)  # Incision trap
cornerLoopToTargets(target_x, target_y, safe_distance=0.)  # Loop to target

# Movement
interpShift(shift_x, shift_y)   # Interpolated nudge
slantShift(shift_x, shift_y, angle)  # Slanted move
alignTo(entity, align=(True,True), smart=True, lerp=False)  # Align to node/line
```

### `pNodesContainer`

Container for multiple nodes with batch operations.

```python
from typerig.proxy.fl.objects.node import pNodesContainer

container = pNodesContainer([fl_node1, fl_node2], extend=pNode)
```

**Properties:**
- `bounds` - Bounding box
- `x, y, width, height` - Bounds components
- `naked` - List of raw flNodes

**Methods:**
```python
clone()                  # Deep copy
reverse()               # Reverse order
shift(dx, dy)           # Move all
smartShift(dx, dy)      # Move all with BCPs
applyTransform(t)        # Apply transform
cloneTransform(t)        # Copy, transform, return
```

### `eNodesContainer` (extends `pNodesContainer`)

Extended container with alignment.

```python
alignTo(entity, alignMode='', align=(True,True))  # L, R, C, T, B, E
```

---

## Contour Objects

### `pContour` (`objects/contour.py`)

Proxy to `flContour`.

```python
from typerig.proxy.fl.objects.contour import pContour

contour = pContour(fl_contour)
```

**Properties:**
- `bounds` - Bounding box
- `rect` - QRectF
- `x, y, width, height` - Bounds components
- `center` - Center point
- `closed` - Whether contour is closed
- `fg` - FontGate contour
- `area` - Contour area

**Methods:**
```python
indexOn()                  # List of on-curve node indices
reverse()                  # Reverse contour direction
isCW()                    # Clockwise?
isCCW()                   # Counter-clockwise?
setCW()                   # Make clockwise
setCCW()                  # Make counter-clockwise
isAllSelected()            # All nodes selected?
translate(dx, dy)         # Move
scale(sx, sy)             # Scale
slant(deg)                 # Slant
rotate(deg)                # Rotate
pointInPolygon(point)      # Point test
contains(other)            # Contains test
draw(pen, transform=None)  # Draw to pen
```

### `eContour` (extends `pContour`)

Extended contour with advanced operations.

```python
from typerig.proxy.fl.objects.contour import eContour

contour = eContour(fl_contour)
```

**Additional Methods:**
```python
asCoord()                  # Bottom-left corner as Coord
randomize(cx, cy, bleedMode=0)  # Randomize nodes
fragmentize(countOrLength, lengthThreshold, lengthMode=False, processIndexes=[])  # Split contour
linearize()                # Convert curves to lines
curverize(smooth=True)     # Convert lines to curves
alignTo(entity, alignMode='', align=(True,True))  # Align contour
```

---

## Curve Objects

### `eCurveEx` (`objects/curve.py`)

Extended curve segment with optimization methods.

```python
from typerig.proxy.fl.objects.curve import eCurveEx

# Constructor variants
curve1 = eCurveEx(flCurveEx)        # From flCurveEx
curve2 = eCurveEx([node1, node2, node3, node4])  # From nodes
curve3 = eCurveEx(contour, time)     # From contour and time
```

**Properties:**
- `nodes` - List of 4 (or 2) nodes
- `n0, n1, n2, n3` - Individual nodes
- `curve` - CubicBezier object
- `line` - Line object
- `isCurve` - True if cubic, False if line
- `contour` - Parent contour

**Methods:**
```python
updateNodes()              # Apply curve changes to nodes
eqTunni(apply=True)      # Equalize tunni (tau/opening)
eqProportionalHandles(proportion=.3, apply=True)  # Proportional handles
eqRatioHandles(ratio=.3, apply=True)  # Handle distance ratio
eqHobbySpline(curvature=(.9,.9), apply=True)  # Hobby spline optimization
make_collinear(other, mode=0, equalize=False, target_width=None, apply=True)  # Make collinear
```

---

## Shape Objects

### `pShape` (`objects/shape.py`)

Proxy to `flShape`.

```python
from typerig.proxy.fl.objects.shape import pShape

shape = pShape(fl_shape, layer=None, glyph=None)
```

**Properties:**
- `bounds` - Bounding box
- `x, y, width, height` - Bounds
- `refs` - Reference count
- `container` - Contained shapes
- `name` - Shape name

**Methods:**
```python
data()                    # flShapeData object
info()                    # flShapeInfo object
builder()                 # flShapeBuilder object
container()               # Shapes contained
tag(tagString)            # Add tag
isChanged()               # Has unsaved changes?
update()                  # Update shape
setName(shape_name)       # Rename
decompose()               # Decompose references
goUp/Down()               # Z-order
goFrontOf/backOf(shape)   # Z-order
goLayerFront/Back()       # Layer z-order
pointInShape(point)       # Point test
segments()                # Shape segments
contours()                # Shape contours
nodes()                   # All nodes
sortContours(criteria='y', ascending=True)  # Sort contours
reset_transform()         # Reset transform
shift(dx, dy, reset=False)  # Translate
rotate(angle, reset=False)  # Rotate
scale(sx, sy, reset=False)  # Scale
shear(sh, sv, reset=False)  # Shear
draw(pen)                 # Draw to pen
```

### `eShape` (extends `pShape`)

Extended shape with additional operations.

```python
from typerig.proxy.fl.objects.shape import eShape

shape = eShape(fl_shape)
```

**Additional Methods:**
```python
contourOrder(order=(True,True))  # Reorder contours
alignTo(entity, alignMode='', align=(True,True))  # Align shape
round()                   # Round transformation values
```

---

## Glyph Objects

### `pGlyph` (`objects/glyph.py`)

Proxy to `flGlyph` and `fgGlyph`.

```python
from typerig.proxy.fl.objects.glyph import pGlyph

# Constructor variants
g1 = pGlyph()                    # Current glyph
g2 = pGlyph(fl_glyph)           # From flGlyph
g3 = pGlyph(fg_font, fg_glyph)  # Explicit fonts
```

**Properties:**
- `name` - Glyph name
- `index` - Glyph index
- `id` - Glyph ID
- `unicode, unicodes` - Unicode values
- `mark` - Glyph mark color
- `tags` - Glyph tags

**Attributes:**
- `fl` - flGlyph object
- `fg` - fgGlyph object
- `parent` - Parent font

**Core Methods:**
```python
activeLayer()               # Current active layer
layers()                   # All layers (excluding #)
layer(name_or_index)       # Get specific layer
masters()                  # Master layers only
masks()                    # Mask layers only
services()                 # Service layers only
hasLayer(name)             # Has layer?

# Nodes, Contours, Shapes
nodes(layer=None, extend=None, deep=False)  # All nodes
contours(layer=None, deep=False, extend=None)  # All contours
shapes(layer=None, deep=False, extend=None)  # All shapes
containers(layer=None, extend=None)  # Complex shapes

# Components
components(layer=None, extend=None)  # Component shapes
elements(layer=None, extend=None)    # Element shapes
noncomplex(layer=None, extend=None) # Non-component shapes
decompose(layer=None)              # Decompose all

# Shape management
addShape(shape, layer=None, clone=False)  # Add shape
replaceShape(old, new, layer=None)         # Replace shape
replaceShapeAdv(name, new, layer=None)     # Advanced replace
removeShape(shape, layer=None)             # Remove shape
addShapeContainer(shapeList, layer=None)   # Group shapes
findShape(name, layer=None, deep=True)     # Find by name
dereference(layer=None)                   # Remove refs

# Glyph composition
addComponents(config, layer=None, useAnchors=True, colorize=False)  # Add components
getCompositionDict(layer=None)  # Component dictionary
getCompositionNames(layer=None)  # Component names
```

**Layer Operations:**
```python
addLayer(layer, toBack=False)        # Add layer
removeLayer(layer)                  # Remove layer
duplicateLayer(layer=None, newName='', references=False)  # Duplicate
importLayer(src, srcName, dstName, options, addLayer=False, ...)  # Copy layer
isEmpty(strong=True)                 # Empty test
isCompatible(strong=False)           # Interpolatable?
isMixedReference()                  # Mixed refs?
isHybridComponent(layer=None)       # Mixed contours/refs?
reportLayerComp(strong=False)       # Compatibility report
```

**Selection Methods:**
```python
selectedNodesOnCanvas(filterOn=False)  # Canvas selection
selectedNodeIndices(filterOn=False, deep=False)  # Indices
selectedNodes(layer=None, filterOn=False, extend=None, deep=False)  # Nodes
selectedContours(layer=None, allNodesSelected=False, deep=False)  # Contours
selectedAtContours(index=True, layer=None, filterOn=False, deep=False)  # Both
selectedAtShapes(index=True, filterOn=False, layer=None, deep=False)  # Shape+node
selectedCoords(layer=None, filterOn=False, applyTransform=False, deep=False)  # Coordinates
selectedSegments(layer=None, deep=False)  # Selected segments
findNode(name, layer=None)               # Find by name
findNodeCoords(name, layer=None)        # Find coords
```

**Outline Operations:**
```python
mapNodes2Times(layer=None)    # Node index -> contour time
mapTimes2Nodes(layer=None)    # Contour time -> node index
getSegment(cID, nID, layer=None)  # Segment at position
segments(cID, layer=None)     # All segments in contour
nodes4segments(cID, layer=None)  # Segments with nodes
insertNodesAt(cID, nID, nodeList, layer=None)  # Insert nodes
removeNodes(cID, nodeList, layer=None)  # Remove nodes
insertNodeAt(cID, time, layer=None)  # Insert at time
removeNodeAt(cID, nID, layer=None)  # Remove at index
translate(dx, dy, layer=None)  # Move
scale(sx, sy, layer=None)     # Scale
slant(deg, layer=None)       # Slant
rotate(deg, layer=None)      # Rotate
```

**Metrics:**
```python
getLSB(layer=None)           # Left side-bearing
getAdvance(layer=None)      # Advance width
getRSB(layer=None)          # Right side-bearing
getVSB(layer=None)          # Vertical SB (bottom)
getTSB(layer=None)          # Vertical SB (top)
getBounds(layer=None)       # Bounding box (QRectF)

setLSB(value, layer=None)   # Set LSB
setRSB(value, layer=None)  # Set RSB
setVSB(value, layer=None)  # Set VSB
setTSB(value, layer=None)  # Set TSB
setAdvance(value, layer=None)  # Set advance
setLSBeq/RsBeq/ADVeq(expr, layer=None)  # Metric equations
hasSBeq(layer=None)       # Has SB equations?
getSBeq(layer=None)       # Get SB equations
setSBeq(tuple, layer=None)  # Set SB equations
fontMetricsInfo(layer=None)  # FontMetrics object
```

**Anchors & Guidelines:**
```python
anchors(layer=None)         # List anchors
addAnchor(coordTuple, name, layer=None, isAnchor=True)  # Add anchor
newAnchor(coordTuple, name, anchorType=1)  # Create anchor
clearAnchors(layer=None)   # Remove all
findAnchor(name, layer=None)  # Find by name
findAnchorCoords(name, layer=None)  # Get coords

guidelines(layer=None)      # List guidelines
addGuideline(coordTuple, layer=None, angle=0, name='', ...)  # Add guideline
```

**Update:**
```python
update(layer=None)         # Update glyph
updateObject(flObject, undoMessage='TypeRig', verbose=True)  # With undo
```

**Pens:**
```python
draw(pen, layer=None)              # Draw to pen
drawPoints(pen, layer=None)        # PointPen protocol
drawContours(pen, layer=None)      # Selected contours only
```

### `eGlyph` (extends `pGlyph`)

Extended glyph with additional tools.

```python
from typerig.proxy.fl.objects.glyph import eGlyph

glyph = eGlyph()
```

**Internal Methods:**
```python
_prepareLayers(layers, compatible=True)  # Prepare layer list for tools
_compatibleLayers(layerName=None)        # Check compatibility
```

---

## Font Objects

### `pFont` (`objects/font.py`)

Proxy to `fgFont` and `flPackage`.

```python
from typerig.proxy.fl.objects.font import pFont

# Constructor variants
f1 = pFont()                    # Current font
f2 = pFont(fg_font)            # From fgFont
f3 = pFont('/path/to/font.vfc')  # Load from file
```

**Properties:**
- `info` - Font info
- `name, familyName` - Font name
- `path` - File path
- `italic_angle` - Italic angle
- `OTfullName, PSfullName` - Full names
- `ps_stems, tt_stems` - Stem values
- `font_lib` - Package library
- `pMasters, pDesignSpace` - Master/axis management

**Glyph Access:**
```python
glyph(name_or_index)       # Single glyph as pGlyph
glyphs(indexList=[], extend=None)  # List of glyphs
pGlyphs(fgGlyphList=[])    # As pGlyph list
selectedGlyphs(extend=None) # Selected glyphs
selected_pGlyphs()          # As pGlyph
hasGlyph(name)             # Exists?
findShape(name, master=None)  # Find shape in font
```

**Metrics:**
```python
fontMetrics()               # pFontMetrics object
fontMetricsInfo(layer)      # FontMetrics for layer
getItalicAngle()           # Italic angle
```

**Masters & Axes:**
```python
masters()                   # List master names
hasMaster(name)            # Has master?
axes()                     # Axis list
addEmptyMaster(name, location_dict=None)  # Add master
addSynthMaster(source, new, name=None)  # Synth master
addSynthMasters(config)    # Multiple synth masters
copyMaster(new, location={}, source=None)  # Copy master
instances()               # List instances
generateInstance(location_dict, round=True)  # Generate instance
```

**Glyph Management:**
```python
newGlyph(name, layers=[], unicode=None)  # Create glyph
newGlyphFromRecipe(name, recipe, layers=[], unicode=None, rtl=False)  # From recipe
duplicateGlyph(src, dst, dst_unicode=None)  # Duplicate
addGlyph(glyph)              # Add existing
addGlyphList(list)          # Add multiple
```

**Glyph Sets:**
```python
uppercase(namesOnly=False)      # Uppercase
lowercase(namesOnly=False)      # Lowercase
figures(namesOnly=False)        # Digits
symbols(namesOnly=False)        # Symbols
ligatures(namesOnly=False)      # Ligatures
alternates(namesOnly=False)     # Alternates
getGlyphNames()                 # All names
getGlyphNameDict()              # Grouped names
getGlyphUnicodeDict()           # Unicode grouped
```

**Kerning:**
```python
kerning(layer=None)             # Kerning object
kerning_to_list(layer=None)     # As list
kerning_dump(layer=None, mark_groups='@', pairs_only=False)  # Dump pairs
kerning_groups(layer=None)      # Group kerning
kerning_groups_to_dict(layer=None, byPosition=False)  # As dict
add_kerning_group(key, list, type, layer=None)  # Add group
remove_kerning_group(key, layer=None)  # Remove group
rename_kerning_group(old, new, layer=None)  # Rename
fl_kerning_groups(layer=None)  # FL groups
```

**Zones & Hinting:**
```python
getZones(layer=None, type=0)   # Alignment zones
setZones(zones, layer=None)   # Set zones
zonesToTuples(layer=None)     # Zone data
zonesFromTuples(tuples, layer=None)  # From tuples
addZone(position, width, layer=None)  # Add zone
guidelines(hostInf=False)     # Font guidelines
addGuideline(gl)              # Add guideline
delGuideline(gl)              # Remove guideline
clearGuidelines()             # Clear all
hinting()                     # Hinting data
setStem(value, name='', horizontal=False, type_TT=False, layer=None)  # Add stem
resetStems(horizontal=False, type_TT=False)  # Reset stems
```

**Features:**
```python
getFeatures()             # Feature table
getFeatureTags()           # Feature tag list
hasFeature(tag)           # Has feature?
getFeature(tag)           # Get feature
setFeature(tag, string)   # Set feature
delFeature(tag)          # Delete feature
getFeaPrefix()           # Get prefix
setFeaPrefix(string)     # Set prefix
```

**Groups:**
```python
getOTgroups()             # OpenType groups
newOTgroup(name, glyphs)  # Create group
addOTgroup(name, glyphs) # Add group
```

**Update:**
```python
updateObject(flObject, undoMessage='TypeRig', verbose=True)
update()
```

### `pFontMetrics`

Font metrics getter/setter.

```python
from typerig.proxy.fl.objects.font import pFontMetrics

metrics = pFontMetrics(fl_package)

# Getters
metrics.getAscender(layer=None)
metrics.getCapsHeight(layer=None)
metrics.getDescender(layer=None)
metrics.getLineGap(layer=None)
metrics.getUpm()
metrics.getXHeight(layer=None)
metrics.getItalicAngle(layer=None)
metrics.getCaretOffset(layer=None)

# Setters
metrics.setAscender(value, layer=None)
metrics.setCapsHeight(value, layer=None)
# ... (same pattern)

# Import/Export
asDict(layer=None)       # Export all as dict
fromDict(dict, layer=None)  # Import from dict
```

---

## Kerning Objects

### `pKerning` (`objects/kern.py`)

Proxy to `fgKerning`.

```python
from typerig.proxy.fl.objects.kern import pKerning

kern = pKerning(fg_kerning)
```

**Methods:**
```python
clear()                      # Clear all pairs
groups()                     # Kerning groups
setExternalGroupData(data)    # Use external groups
storeExternalGroupData()     # Save external groups
resetGroups()               # Clear groups

asDict()                     # As dictionary
asList()                     # As list
groupsAsDict()              # Groups as dict
groupsBiDict()               # Bi-directional groups
groupsFromDict(dict)         # Load groups

removeGroup(key)             # Remove group
renameGroup(old, new)        # Rename group
addGroup(key, glyphs, type) # Add group (L, R, B)
getPairGroups(pairTuple)     # Get group names for pair

setPair(pairTuple, modeTuple=(0,0))  # Set pair
setPairs(pairList, extend=False)      # Set multiple
getPairObject(pairTuple)    # Get pair object
getPair(pairTuple)          # Get pair value

getKerningForLeaders()      # Get kerning with leaders
newPair(left, right, modeL, modeR)  # Create pair
```

---

## Application/Workspace

### `pWorkspace` (`application/app.py`)

Proxy to `flWorkspace`.

```python
from typerig.proxy.fl.application.app import pWorkspace

ws = pWorkspace()
```

**Properties:**
- `fl` - flWorkspace
- `main` - Main window
- `name` - Workspace name

**Methods:**
```python
getCanvas(atCursor=False)      # Get active canvas
getCanvasList()                # All canvases
getSelectedNodes()             # Selected nodes
getTextBlockList(atCursor=False)  # Text blocks
getTextBlockGlyphs(tbi=0)      # Glyphs in block
getActiveGlyphInfo(tbi=0)     # Active glyph info
getActiveGlyph(tbi=0)        # Active glyph
getPrevGlyphInfo(tbi=0)       # Previous glyph
getNextGlyphInfo(tbi=0)       # Next glyph
getActiveKernPair(tbi=0)      # Kern pair at cursor
getActiveIndex(tbi=0)         # Active index
getActiveLine(tbi=0)          # Active line
createFrame(string, x, y)      # Create text frame
```

### `pItems` (`application/app.py`)

Proxy to `flItems`.

```python
from typerig.proxy.fl.application.app import pItems

items = pItems()
```

**Methods:**
```python
outputString(string, cursor=0)     # Output text
outputGlyphNames(names, layers=[], cursor=0)  # Output glyphs
openFont(package)                  # Open font
loadFont(file_path)               # Load from path
```

### `pTextBlock` (`application/app.py`)

Proxy to `flTextBlock`.

```python
from typerig.proxy.fl.application.app import pTextBlock

block = pTextBlock(fl_text_block)
```

**Properties:**
- `fl` - flTextBlock
- `fontSize` - Font size
- `textFrame` - Frame size
- `textWarp` - Wrap state

**Methods:**
```python
getFontSize() / setFontSize(size)      # Font size
getFrameSize() / setFrameSize(w, h)    # Frame dimensions
setPageSize(name)                      # Set page size
setFrameWidth(width)                   # Frame width
getGlyphBounds()                       # Glyph bounds
getWrapState() / setWrapState(wrap)    # Wrap state
getString()                            # Get text
update()                               # Update
clone()                                # Clone
getTransform() / setTransform(t)       # Transform
resetTransform()                       # Reset
x(), y()                               # Position
width(), height()                      # Dimensions
reloc(x, y)                            # Move
```

### `Automat` (`application/automat.py`)

FL action runner.

```python
from typerig.proxy.fl.application.automat import Automat

auto = Automat()

auto.run('action_code')        # Run action
auto.help('action_code')       # Get help
auto.helpAll()                 # All actions
auto.getQAction(code)          # Get QAction
```

---

## Action Collectors

Action collectors are static methods for batch glyph operations.

### Common Parameters:
- `pMode:int` - Processing mode (0=active glyph, 1=glyphs in window, 2=selected, 3=all in font)
- `pLayers:tuple` - Layer control tuple `(active, masters, masks, services)`

### `TRNodeActionCollector` (`actions/node.py`)

```python
from typerig.proxy.fl.actions.node import TRNodeActionCollector

# Node insertion
TRNodeActionCollector.node_insert(pMode, pLayers, time, select_one_node=False)
TRNodeActionCollector.node_insert_dlg(pMode, pLayers, select_one_node=False)
TRNodeActionCollector.node_insert_extreme(pMode, pLayers)

# Node removal
TRNodeActionCollector.node_remove(pMode, pLayers)

# Node rounding
TRNodeActionCollector.node_round(pMode, pLayers, round_up=True, round_all=False)

# Node smoothing
TRNodeActionCollector.node_smooth(pMode, pLayers, set_smooth=True)

# Corner operations
TRNodeActionCollector.corner_mitre(pMode, pLayers, radius)
TRNodeActionCollector.corner_mitre_dlg(pMode, pLayers)
TRNodeActionCollector.corner_round(pMode, pLayers, radius, curvature=1., is_radius=True)
TRNodeActionCollector.corner_round_dlg(pMode, pLayers)
TRNodeActionCollector.corner_loop(pMode, pLayers, radius)
TRNodeActionCollector.corner_loop_dlg(pMode, pLayers)
TRNodeActionCollector.corner_loop_to_targets(pMode, pLayers)
TRNodeActionCollector.corner_trap(pMode, pLayers, incision, depth, trap, smooth=True)
TRNodeActionCollector.corner_trap_dlg(pMode, pLayers, smooth=True)
TRNodeActionCollector.corner_rebuild(pMode, pLayers, cleanup_nodes=True)

# Slope operations
TRNodeActionCollector.slope_copy(glyph, pLayers) -> dict
TRNodeActionCollector.angle_copy(glyph, pLayers) -> dict
TRNodeActionCollector.slope_paste(pMode, pLayers, slope_dict, mode)

# Alignment
TRNodeActionCollector.nodes_align(pMode, pLayers, mode, intercept=False, 
                                  keep_relations=False, smart_shift=False,
                                  ext_target={}, lerp_shift=False, extrapolate=False)
# mode: 'L', 'R', 'T', 'B', 'C', 'E', 'Y', 'X', 'BBoxCenterX', 'BBoxCenterY'

# Clipboard
TRNodeActionCollector.nodes_copy(glyph, pLayers) -> dict
TRNodeActionCollector.nodes_paste(glyph, pLayers, node_bank, align=None, mode=())

# Movement
TRNodeActionCollector.nodes_move(glyph, pLayers, offset_x, offset_y, 
                                 method, slope_dict={}, in_percent_of_advance=False)
# method: 'SMART', 'MOVE', 'LERP', 'SLANT', 'SLOPE'

# Caps
TRNodeActionCollector.new_cap_round(glyph, pLayers, keep_nodes=False)
TRNodeActionCollector.cap_round(glyph, pLayers, keep_nodes=False)
TRNodeActionCollector.cap_rebuild(glyph, pLayers, keep_nodes=False)
TRNodeActionCollector.cap_normal(glyph, pLayers, keep_nodes=False)

# Curve
TRNodeActionCollector.make_collinear(glyph, pLayers, equalize=False)
```

### `TRContourActionCollector` (`actions/contour.py`)

```python
from typerig.proxy.fl.actions.contour import TRContourActionCollector

TRContourActionCollector.contour_break(pMode, pLayers, expand=20., close=False)
TRContourActionCollector.contour_close(pMode, pLayers)
TRContourActionCollector.contour_slice(pMode, pLayers, expanded=False)
TRContourActionCollector.contour_bool(pMode, pLayers, operation='add', reverse_order=False)
# operation: 'add', 'subtract', 'intersect', 'exclude'
TRContourActionCollector.contour_set_start(pMode, pLayers)
TRContourActionCollector.contour_set_start_next(pMode, pLayers, set_previous=False)
TRContourActionCollector.contour_set_order(pMode, pLayers, sort_order, reverse=False)
TRContourActionCollector.contour_smart_start(pMode, pLayers, control=(0,0))
TRContourActionCollector.contour_set_winding(pMode, pLayers, ccw=True)
TRContourActionCollector.contour_align(pMode, pLayers, align_mode, align_x, align_y,
                                       reverse=False, contour_A={}, contour_B={})
# align_mode: 'CC', 'CN', 'NN', 'AB', 'DH', 'DV', 'CL', 'CMX', 'CMC', 'CMA', 'CMD'
# align_x: 'L', 'R', 'C', 'K' (keep)
# align_y: 'T', 'B', 'E', 'X' (keep)
```

### `TRCurveActionCollector` (`actions/curve.py`)

```python
from typerig.proxy.fl.actions.curve import TRCurveActionCollector

TRCurveActionCollector.segment_convert(pMode, pLayers, to_curve=False)
TRCurveActionCollector.curve_optimize(pMode, pLayers, (method, p0, p1))
# method: 'tunni', 'hobby', 'proportional'
TRCurveActionCollector.curve_optimize_dlg(pMode, pLayers, method_name)
TRCurveActionCollector.curve_optimize_by_dict(pMode, pLayers, method_name, dict, swap=False)
TRCurveActionCollector.hobby_tension_copy(glyph, pLayers) -> dict
TRCurveActionCollector.hobby_tension_push(pMode, pLayers)
```

### `TRLayerActionCollector` (`actions/layer.py`)

```python
from typerig.proxy.fl.actions.layer import TRLayerActionCollector

TRLayerActionCollector.layer_toggle_visible(parent)
TRLayerActionCollector.layer_set_visible(parent, visible=False)
TRLayerActionCollector.layer_add(parent)
TRLayerActionCollector.layer_duplicate(parent, ask_user=False)
TRLayerActionCollector.layer_duplicate_mask(parent)
TRLayerActionCollector.layer_delete(parent)
TRLayerActionCollector.layer_set_type(parent, type)  # 'Service', 'Wireframe', 'Mask'

TRLayerActionCollector.layer_copy_shapes(glyph, layerName, copy=True, cleanDST=False)
TRLayerActionCollector.layer_copy_metrics(glyph, layerName, copy=True, mode='ADV')
TRLayerActionCollector.layer_copy_guides(glyph, layerName, copy=True, cleanDST=False)
TRLayerActionCollector.layer_copy_anchors(glyph, layerName, copy=True, cleanDST=False)
TRLayerActionCollector.layer_unlock(parent, locked_trigger=False)

TRLayerActionCollector.layer_swap(parent)
TRLayerActionCollector.layer_pull(parent)
TRLayerActionCollector.layer_push(parent)
TRLayerActionCollector.layer_clean(parent)

TRLayerActionCollector.layer_side_by_side(parent)
TRLayerActionCollector.layer_unfold(parent)
TRLayerActionCollector.layer_restore(parent)
TRLayerActionCollector.layer_copy_outline(parent)
TRLayerActionCollector.layer_paste_outline(parent)
TRLayerActionCollector.layer_paste_outline_selection(parent)
```

### `TRDrawActionCollector` (`actions/draw.py`)

```python
from typerig.proxy.fl.actions.draw import TRDrawActionCollector

TRDrawActionCollector.draw_circle_from_selection(pMode, pLayers, mode=1, rotated=False)
# mode: 0=2-point diameter, 1=3-point
TRDrawActionCollector.draw_square_from_selection(pMode, pLayers, mode=0)
# mode: 0=diagonal points, 1=midpoints

TRDrawActionCollector.nodes_collect(pMode, pLayers) -> dict
TRDrawActionCollector.nodes_trace(pMode, pLayers, nodes_bank, mode=0)
# mode: 0=keep nodes, 1=lines only, 2=hobby splines
```

---

## GUI Widgets

### `getProcessGlyphs`

```python
from typerig.proxy.fl.gui.widgets import getProcessGlyphs

glyphs = getProcessGlyphs(mode=0, font=None, workspace=None)
# mode: 0=active glyph, 1=glyphs in window, 2=selected, 3=all in font
# Returns: list[eGlyph]
```

### Dialogs (`gui/dialogs.py`)

```python
from typerig.proxy.fl.gui.dialogs import (
    TR1FieldDLG, TR2FieldDLG,
    TR1SpinDLG, TRNSpinDLG,
    TR1SliderDLG,
    TR2ComboDLG,
    TRColorDLG,
    TRLayerSelectDLG
)

# Usage
dlg = TR1SpinDLG('Title', 'Message', 'Label:', (0., 100., 50., 1.))
if dlg.values is not None:
    value = dlg.values

dlg = TRNSpinDLG('Title', 'Message', {'Radius:': (0., 200., 5., 1.), 'Depth:': (0., 100., 10., 1.)})
# dlg.values is a list of values

dlg = TRLayerSelectDLG(parent, mode=0)  # 0=glyph layers, 1=font masters
# Returns checked layer names via getTable()
```

### Custom Widgets (`gui/widgets.py`)

```python
from typerig.proxy.fl.gui.widgets import (
    CustomPushButton, CustomLabel, CustomSpinBox,
    CustomHorizontalSlider, CustomLineEdit,
    CustomSpinLabel, CustomSpinButton,
    TRCustomSpinController,
    TRTransformCtrl,
    TRGlyphSelect,
    TRTableView, TRCheckTableView,
    TRDeltaLayerTree,
    TRHTabWidget, TRVTabWidget,
    TRFlowLayout,
    TRColorCombo,
    TRGLineEdit,
    TREdit2Spin, TRCombo2Spin
)

# Transform control
ctrl = TRTransformCtrl()
transform, origin, rev = ctrl.getTransform(rect)
ctrl.reset()

# Glyph selector
selector = TRGlyphSelect(font=None)
glyphs = selector.getGlyphs()

# Tables
table = TRTableView(data)
data = table.getTable()

check_table = TRCheckTableView(data, color_dict=None, enable_check=True)
names = check_table.getTable()  # Returns checked items

# Layer tree
tree = TRDeltaLayerTree(data=data, headers=headers)
tree_data = tree.getTree()
```

---

## Pens

### `OutlinePen` (`pens/outlinePen.py`)

Pen for generating outline offsets.

```python
from typerig.proxy.fl.pens.outlinePen import OutlinePen

pen = OutlinePen(
    offset=10,              # Outline offset
    contrast=0,            # Contrast angle
    contrastAngle=0,       # Contrast angle
    connection='square',   # 'square', 'round', 'butt'
    cap='round',           # 'round', 'square', 'butt'
    closeOpenPaths=True,   # Close open paths
    optimizeCurve=False,   # Add mid-point
    filterDoubles=True,    # Remove doubles
    miterLimit=None        # Miter limit
)

glyph.draw(pen)
inner, outer, original = pen.getGlyphs()
inner_shape, outer_shape, orig_shape = pen.getShapes()
```

---

## Design Patterns

### Proxy Naming Convention

- `p*` - Basic proxy (e.g., `pNode`, `pGlyph`)
- `e*` - Extended proxy with advanced features (e.g., `eNode`, `eGlyph`)

### Pattern: Wrapping FL Objects

```python
# Wrap existing FL object
proxy = pNode(fl_node)
proxy.x = 100  # Modify via property

# Access underlying object
underlying = proxy.fl

# Convert back
raw_node = proxy.fl
```

### Pattern: Naked Mode

Many methods accept `naked=True/False` to return either raw FL objects or proxy objects:

```python
next_node = current.getNext(naked=True)   # Returns flNode
next_proxy = current.getNext(naked=False) # Returns pNode
```

### Pattern: Layer Defaults

Layer parameters default to `None` (active layer):

```python
glyph.nodes()           # Active layer
glyph.nodes(layer='Bold')  # Specific layer
glyph.nodes(layer=0)      # By index
```

### Pattern: Extend Parameter

Container methods accept `extend` to return proxy objects:

```python
nodes = glyph.nodes()                    # Raw flNodes
proxies = glyph.nodes(extend=pNode)     # pNode wrappers
extended = glyph.nodes(extend=eNode)     # eNode wrappers
```

### Pattern: Layer Control Tuple

Many operations accept a tuple for layer selection:

```python
layers = (True, True, False, False)  # (active, masters, masks, services)
```

### Pattern: Update with Undo

Always use `updateObject` for changes that should be undoable:

```python
glyph.updateObject(glyph.fl, 'My Change Message')
```

### Pattern: Selection Indexing

Nodes are referenced by `(contour_index, node_index)` tuples:

```python
for cID, nID in glyph.selectedAtContours():
    contour = glyph.contours()[cID]
    node = contour.nodes()[nID]
```

---

## Dependencies

The proxy module depends on:

- `fontlab as fl6` - FontLab 6 API
- `fontgate as fgt` - FontGate (font data)
- `PythonQt` - Qt bindings
- `typerig.core.*` - Typerig core utilities

---

## Version

Current version: `0.x.x` (see individual module `__version__` variables)
