---
this_file: WORK.md
---

# TypeRig: source and acceptance handoff

## 2026-11-05 — Issue 230 remote variant

Observed source: `e3f06f5cfdbc132255db44991e476066cf92ab7b`.

## Checks

The observed source base is `e3f06f5cfdbc132255db44991e476066cf92ab7b`.
It contains seven newer source commits than the canonical documentation checkpoint.
Earlier canonical test receipts do not qualify this newer source.
The exact CI recipe is in [.github/workflows/check.yml](.github/workflows/check.yml).
It tests Python 3.11 on Linux, macOS and Windows. From an isolated checkout:

```sh
PYTHONPATH=Lib PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --python 3.11 --with pytest --with pytest-cov --with gitnextver==1.0.4 --with packaging --with twine --with hatch-vcs --with hatchling --with fonttools python -m pytest -p pytest_cov -q tests Lib/typerig/core/algo/test_cjk.py Lib/typerig/core/algo/test_outline_cleanup.py --cov=release --cov=publish --cov=_release --cov=_github --cov=_artifacts --cov-report=term-missing --cov-fail-under=80
PYTHONPATH=Lib uv run --no-project --python 3.11 --with fonttools python Lib/typerig/core/objects/test_objects.py
PYTHONPATH=Lib uv run --no-project --python 3.11 python Lib/typerig/core/actions/test_actions.py
uv run release.py --help
uv run publish.py --help
```

These commands were inspected for this documentation variant, not executed.
Read [RELEASING.md](RELEASING.md) and [PYPI.md](PYPI.md) before release work.
The check workflow runs for `master` pushes and pull requests targeting `master`.
Release workflows have separate version-tag or explicit-dispatch triggers.

The remote README body is retained exactly. The owner’s unpublished November 3
handoff remains in canonical files and sealed private preimages. It is not
imported wholesale into this delivery. Current safety and pause constraints
come from the independently reviewed Issue 230 guidance.

The private variant manifest records remote, canonical and owner preimages,
proposal hashes and full diffs. Independent review precedes guarded application.
Later application, tests, commits, pushes and integration belong in the external
Issue 230 live ledger. No such result is claimed by this authoring entry.
Preserve Vassil Kateliev’s authorship and MPL-2.0 terms in LICENSE.
The geometry core runs outside FontLab. Host proxies and Scripts require
the corresponding host. Do not load an alternate Qt binding into FontLab.
