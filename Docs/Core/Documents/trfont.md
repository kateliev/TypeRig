# TypeRig — .trfont Format: Concept and Implementation Summary

## Background

TypeRig is a Python framework for font design and engineering, built around a clean hierarchy of pure-Python geometric objects: `Node → Contour → Shape → Layer → Glyph`. Each level is a `Container` of the one below it, all sharing a common `XMLSerializable` mixin that handles per-element XML serialization through a declarative schema (`XML_TAG`, `XML_ATTRS`, `XML_CHILDREN`, `XML_LIB_ATTRS`).

The `.trfont` format extends this hierarchy upward: `Glyph → Font`, and introduces the file-level objects needed to describe a multi-master font project on disk.

---

## Design Goals

The format is explicitly a **work format**, not a build format. The distinction matters:

- A build format (UFO, Glyphs, designspace+UFO) is optimized for compilation — turning source files into binaries. It expects all data to be complete and consistent.
- A work format is optimized for the designer's active workflow — iterating, sharing assets across projects, and managing a design space without being locked into a single application.

Concretely this means:

- Glyphs are **assets**, not font members. A `.trglyph` file belongs to no specific font. Multiple `.trfont` projects can reference the same file.
- The font project is a **view** over a pool of glyph files — like a game engine's asset pipeline, but for type.
- File structure is **version-control friendly**: one glyph per file, separate XML files for axes/masters/encoding/kerning, no monolithic blobs.
- Sparse masters are **allowed**: a glyph missing a master layer falls back to the default master, following UFO convention.

---

## Folder Structure

```
MyFont.trfont/
├── font.xml          font descriptor: info, metrics, axes, masters,
│                     instances, encoding, kerning
├── glyphs.xml        glyph manifest: name → file path, optional alias,
│                     search paths for shared pools
└── glyphs/           embedded glyph files (optional)
    ├── A.trglyph
    ├── B.trglyph
    └── ...
```

`font.xml` is intentionally thin — it is the project lens, not a font dump. Glyphs are always external, even when embedded in the `glyphs/` subfolder.

---

## Shared Glyph Pools

A `.trfont` manifest can reference glyph files anywhere on the filesystem:

```xml
<glyphs>
  <search>
    <path value="../SharedGlyphs"/>
  </search>
  <glyph name="A"       src="glyphs/A.trglyph"/>
  <glyph name="uni4E00" src="/shared/CJK/uni4E00.trglyph" alias="CJK_1"/>
</glyphs>
```

- `src` can be a relative path (relative to the `.trfont` folder) or an absolute path.
- `alias` gives the glyph a project-local name without renaming the file. `uni4E00` is known as `CJK_1` in this project.
- `search` provides fallback directories: if a glyph entry has no `src`, the manifest walks search paths looking for `<glyph_name>.trglyph`.

This enables CJK font projects to share a large common character pool across multiple optical sizes or weight families without duplicating any glyph files.

---

## .trglyph Files

Each `.trglyph` file is the XML serialization of a single `Glyph` object — one file, all masters. This is the central architectural difference from UFO:

| Format           | Storage model                                              |
|------------------|------------------------------------------------------------|
| UFO + designspace | One `.glif` per glyph **per master** — duplicate files     |
| .trfont           | One `.trglyph` per glyph — all masters as named layers     |

A `.trglyph` file looks like a standard TypeRig glyph XML with multiple layers:

```xml
<glyph name="A" unicodes="[65]">
  <layer name="Regular" width="560">
    <shape> ... </shape>
  </layer>
  <layer name="Bold" width="610">
    <shape> ... </shape>
  </layer>
</glyph>
```

The `layer name` must match the `layer` attribute of a master definition in `font.xml`. This is the master-layer contract.

---

## Python Object Model

The implementation follows the existing TypeRig pattern throughout. Every new object inherits from either `Member` (atomic, non-container) or `Container` (holds children of a known type), and mixes in `XMLSerializable`.

### New `core/objects/` modules

| File           | Classes                          | Role                                          |
|----------------|----------------------------------|-----------------------------------------------|
| `axis.py`      | `Axis(Member)`                   | One design axis: name, tag, min/default/max   |
| `master.py`    | `Master(Member)`, `Masters(Container)` | Master definition + ordered list        |
| `instance.py`  | `Instance(Member)`, `Instances(Container)` | Named instance + ordered list      |
| `encoding.py`  | `EncodingEntry(Member)`, `Encoding(Container)` | Unicode assignments, authoritative over glyph-baked values |
| `kern.py`      | `KernPair(Member)`, `KernClass(Member)`, `Kerning(Container)` | Pairs, classes, full kern table |
| `font.py`      | `FontInfo(Member)`, `FontMetrics(Member)`, `Font(Container)` | Full font descriptor, Container of Glyph |

`Font` is a `Container` of `Glyph` — completing the hierarchy `Node → Contour → Shape → Layer → Glyph → Font`. It holds all metadata objects directly as attributes and provides a name→index cache for O(1) glyph lookup by name.

### Master / Instance location

Both `Master` and `Instance` carry a `location` dict — `{axis_name: value}`. Since this does not flatten naturally into XML attributes, both classes override `_to_xml_element` / `from_XML` to produce a nested `<location><dim name="..." value="..."/></location>` structure. Everything else goes through the standard xmlio machinery.

### Encoding priority

The `Encoding` object is the authoritative unicode source for the project. When `TrFontIO.read()` loads a glyph from a `.trglyph` file, any encoding entry in `font.xml` overrides the `unicodes` attribute baked into the file. This allows a shared glyph to be re-encoded per project without modifying the asset.

### Kern classes

`Kerning` stores pairs and classes separately. Class names use the `@prefix` convention (`@H_left`, `@A_right`). The `Kerning` object stores raw data — pair resolution against classes is left to the caller, keeping the data model simple.

---

## New `core/fileio/` module

| File         | Classes / functions        | Role                                              |
|--------------|---------------------------|---------------------------------------------------|
| `trfont.py`  | `GlyphEntry`, `GlyphManifest`, `TrFontIO` | Folder structure, manifest, write/read |

`TrFontIO` only handles what xmlio cannot: the folder layout and one-file-per-glyph dispatch. Per-element serialization is entirely delegated to the objects' own `_to_xml_element` / `from_XML` methods.

```python
# Write
TrFontIO.write(font, '/path/to/MyFont.trfont')

# Read
font = TrFontIO.read('/path/to/MyFont.trfont')

# Shared-pool glyphs: reference externally, don't embed
TrFontIO.write(font, path, glyph_paths={'uni4E00': '/shared/CJK/uni4E00.trglyph'})

# Empty project skeleton
font = TrFontIO.new('/path/to/NewFont.trfont', 'My Family', 'Regular')
```

---

## FontLab Proxy (trFontFile)

`trFontFile` wraps an `flPackage` and provides the bridge from a live FontLab session to `.trfont` and back.

```python
from typerig.proxy.tr.objects.trfontfile import trFontFile

tr = trFontFile()                                    # CurrentFont()
font = tr.eject()                                    # → pure FontFile, no FL dependency
font.save('/path/to/MyFont.trfont')

# Or in one call:
font = tr.save('/path/to/MyFont.trfont', verbose=True)

# Geometry changes back into FL:
tr.inject(font, verbose=True)
```

`eject()` walks all FL layers via the existing `trGlyph → trLayer → trShape → trContour → trNode` proxy chain to produce a fully self-contained `Font` object. `inject()` is the reverse: it finds each glyph in the live session by name and mounts modified layers back using the existing proxy `.mount()` infrastructure.

FL axes, masters, and instances are extracted from `flPackage.axes` / `.masters` / `.instances` with a graceful fallback for single-master fonts that have no explicit designspace definition.

---

## Comparison with Existing Formats

| Aspect                        | UFO + designspace         | Glyphs.app             | .trfont                    |
|-------------------------------|---------------------------|------------------------|----------------------------|
| Glyph storage                 | One GLIF per master       | Monolithic file        | One file, all masters      |
| Cross-project glyph reuse     | Not supported             | Not supported          | Core feature (shared pool) |
| Version control               | Good (many small files)   | Poor (one large file)  | Good                       |
| Encoding authority            | In glyph GLIF             | In glyph               | Separate encoding map wins |
| Multi-master                  | Via designspace file       | Integrated             | Axes/masters in font.xml   |
| Application compatibility     | Broad (UFO ecosystem)      | Glyphs only            | TypeRig only (for now)     |
| Design intent                 | Build format               | Work format            | Work format                |

---

## Pending / Future

- `groups.xml` — glyph groups and class tags (file pointer registered, no backing code yet)
- Exporter: `Font → UFO + designspace` for build pipeline handoff
- Exporter: `Font → Glyphs.app` (.glyphs)
- Full `trFontFile.inject()` test coverage across masters in FontLab
- Manifest search path UI in tooling
- Kerning: class-based pair resolution helper
