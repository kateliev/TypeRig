---
this_file: RELEASING.md
---

# Releasing TypeRig

The package version comes from Git through `hatch-vcs`. Canonical stable tags
use `vMAJOR.MINOR.PATCH`; the new series starts at **v2.1.0**. Older tags such as
`v2.0.5-Py3.10` are ignored. Commits after a release get development versions.
No version files or library source files need editing for a release.

## Requirements

Install Git, [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[GitHub CLI](https://cli.github.com/), then run `gh auth login`.
The scripts require Python 3.11+; uv manages their inline Python dependencies.
The library itself supports Python 3.10+.

These commands work in macOS Terminal and Windows PowerShell:

```sh
uv run release.py --help
uv run publish.py --help
```

On macOS the executable scripts also run as `./release.py` and `./publish.py`.
Each script locates its checkout from its own path, so it can run from another
working directory. Keep the adjacent `_release.py`, `_artifacts.py` and
`_github.py` helpers beside them.

## Make a release

Commit the intended changes on the repository's default branch, then run:

```sh
uv run release.py --dry-run
uv run release.py
```

The first release selects `v2.1.0`; later releases increment the patch version.
Use `--bump=minor` or `--bump=major` for larger changes. `gitnextver` provides
the pure version selector; its stash/commit/pull/push workflow is never invoked.
Rerunning at the same tagged commit resumes that release; commit new work before
selecting another automatically incremented version.

The script requires a clean, full-history checkout and GitHub write access.
Dry runs also work on a feature branch descended from the current default branch.
It fetches origin's tags, checks the branch is not behind/diverged, clones an
isolated LF checkout, runs tooling and standalone core tests, builds wheel and
sdist with uv, and validates their metadata with Twine. Only then does it create
the annotated tag and atomically push that tag plus the current branch.
No unrelated tags are pushed. It never stages, commits, stashes or merges work.

Next it creates a draft GitHub release, uploads both distributions, verifies
downloaded bytes, and publishes the release. A dry run performs the read/fetch,
test and build steps but creates no source tags, pushes, releases or uploads.

## Publish to PyPI

Publish the exact files from the completed GitHub release:

```sh
uv run publish.py --dry-run
uv run publish.py
```

Authenticate with `UV_PUBLISH_TOKEN` in the environment, or use uv's trusted
publishing inside GitHub Actions. Tokens are never command-line arguments.
Use `--test-pypi` with a TestPyPI token to test that separate registry.
For first publication, configure a pending trusted publisher; if `typerig`
already exists, arrange project access. [PYPI.md](PYPI.md) gives Vassil the
complete Windows setup, including both cases.

Publishing requires an exact stable tag at HEAD and the same tag on origin.
It downloads just that release's wheel and sdist into a temporary directory,
checks hashes and metadata, then invokes `uv publish` on those two exact files.
`uv publish --check-url` skips already-uploaded identical files, making a
partial upload resumable. Different bytes under an existing filename fail.

## Recover a partial release

Rerun the original command while HEAD still points at the release commit, or
select the existing tag explicitly (also works on a detached tag checkout):

```sh
uv run release.py --tag=v2.1.0
uv run publish.py --tag=v2.1.0
```

Existing tags are never moved or deleted. Draft releases resume; existing
assets must match exactly and are never overwritten. A published release that
is missing an asset requires manual inspection. Network/authentication failures
exit nonzero, and timeouts warn that a remote write may already have completed.
After killing a process, inspect the PID recorded in Git's
`typerig-release.lock` before removing a stale lock.

## GitHub Actions

`.github/workflows/check.yml` tests the tooling and package installations on
macOS, Windows and Linux. `.github/workflows/release.yml` runs those checks for
pushed tags, calls `release.py --tag=...`, then `publish.py --tag=...`.
The CLI enforces canonical semver after GitHub's broader tag filter.
Manual workflow dispatch can resume an existing tag. Runs for a tag are
serialized, and published release assets are reused rather than rebuilt for PyPI.

Follow [PYPI.md](PYPI.md) before pushing the first tag. It covers the pending
publisher needed for a new PyPI project and the existing-project alternative.
Configure one publishing authentication method:

- Preferred: add a PyPI trusted publisher for repository `kateliev/TypeRig`,
  workflow `release.yml`, environment `pypi`, owned by the GitHub account
  `kateliev`. The workflow grants `id-token: write` only to its publishing job.
- Alternatively: add a GitHub Actions secret named `PYPI_TOKEN` containing a
  PyPI token scoped to `typerig`. The workflow passes it as `UV_PUBLISH_TOKEN`.

The built-in `GITHUB_TOKEN` handles GitHub releases with `contents: write`.
Local releases need your own Git push and GitHub CLI credentials. A manually
pushed tag starts Actions automatically; the local scripts also work without
Actions and tolerate an identical concurrent GitHub release.
