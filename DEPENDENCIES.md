---
this_file: DEPENDENCIES.md
---

# Dependencies

- **fonttools >=4**: runtime dependency for UFO/designspace and TypeRig font I/O.
  Geometry alone needs no third-party libraries. FontLab/Glyphs proxies require
  their host's APIs; those APIs are not installed from PyPI.
- **hatchling >=1.27**, **hatch-vcs >=0.4**: isolated PEP 517 builds and versions
  inferred from canonical Git tags. They are build dependencies, not runtime APIs.
- **fire**: command-line parsing for the two standalone release scripts.
- **gitnextver >=1.0.4,<2**: pure semantic-tag calculation in release.py; its
  repository-mutating CLI is not called.
- **packaging**, **twine**: release-version and distribution-metadata checks.
- **pytest**: pre-release tooling/core regressions; **pytest-cov** is used only
  for development/Actions coverage checks, with an 80% tooling threshold.
- **Git**, **gh**, **uv**: external executables used by the release scripts.
  Commands use argument arrays, deadlines and explicit artifact paths on all OSes.

The scripts declare their own Python dependencies as PEP 723 metadata. Running
them through uv does not add the release toolchain to the library's dependencies.
