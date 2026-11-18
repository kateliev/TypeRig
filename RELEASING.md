---
this_file: RELEASING.md
---

# Releasing TypeRig

The package version comes from Git through `hatch-vcs`. Canonical stable tags
use `vMAJOR.MINOR.PATCH`; the new series starts at **v2.1.0**. Older tags such as
`v2.0.5-Py3.10` are ignored. Commits after a release get development versions.
No version files or library source files need editing for a release.

The distribution carries the whole `Lib/typerig` tree: `typerig.core` and
`typerig.proxy` (`fl`, `gs3`, `tr`), the GUI modules among them. `Scripts` and
`Docs` stay out of it. Decide the bump from the work, not from the commit count:
3.0.0 to 3.1.0 covered a relicense, three new panels and the `tr-kern` command.

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

With no tag at HEAD the script increments the patch version of the highest
stable tag; `v2.1.0` is only the floor for the first release of the series.
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

## Preview before you tag

Push the work to `master` and let **Check** finish. It runs the tooling tests,
the standalone object and action checks and the CLI help on macOS, Windows and
Linux. That is most of what the release job repeats, so a red Check is a release
that would fail. With `uv` and `gh` installed, `uv run release.py --dry-run`
is the real preview: it tests and builds the exact tag in a temporary clone and
validates both artifacts with Twine, and it creates no tag, push or upload.

A machine with neither tool can still reproduce the tag-shaped build by hand.
Install the tools into a throwaway environment outside the checkout, then build
a detached, tagged clone, exactly as `_artifacts.py` does:

```sh
python -m venv ../relenv
../relenv/Scripts/python -m pip install uv pytest pytest-cov twine fonttools \
  "fire>=0.7,<1" "gitnextver>=1.0.4,<2" packaging hatchling hatch-vcs
export PATH="$PWD/../relenv/Scripts:$PATH"   # the packaging tests call uv
git clone --no-hardlinks --no-checkout --config core.autocrlf=false . ../snap
cd ../snap && git checkout --detach master && git tag v3.1.1 HEAD
PYTHONPATH=Lib PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests
SOURCE_DATE_EPOCH=$(git show -s --format=%ct HEAD) uv build --out-dir dist
python -m twine check dist/*
```

Put that environment's `Scripts` directory on `PATH`. Several tests in
`tests/test_packaging.py` shell out to `uv`, and they fail with confusing
packaging errors when it is missing. Never tag your own checkout to test a
build. `_artifacts.py` stays the authority on the commands; if this preview and
that file disagree, the file is right.

A green preview proves the tests, the artifact names, their embedded metadata
and Twine. It proves nothing about the GitHub and PyPI steps, which need
credentials this machine may not have.

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

## Known failure modes

**Read the step duration first.** On GitHub's runners each Check job takes about
30 s and the release step about 27 s, of which roughly 20 s is the test suite
and the build. A release step that fails at 25 s or later failed at the GitHub
release stage, not in the tests or the packaging. One that fails in a few
seconds failed in `prepare`, before any build.

**`GitHub release creation failed:` with nothing after the colon.** `gh release
create` succeeded and printed the new draft on stdout, but the releases listing
did not contain it yet, so the script concluded that no release existed. Rerun
the workflow for the same tag: the draft is already there and the rerun resumes
it, uploads the assets and publishes. v3.0.0 took three attempts for this; after
v3.1.0 `ensure_release` rereads the listing for about 30 s before it gives up
and reports gh's own output, or its exit code, when creation really did fail.

**Two drafts for one tag.** `info` refuses to guess between them and asks you to
delete the extras. Check **Releases -> Drafts** before rerunning a failed
release, and delete all but one.

**The run sits at `waiting` and nothing happens.** The `publish` job deploys
into the `pypi` environment, which requires `kateliev` as a reviewer. Open the
run and choose **Review deployments -> pypi -> Approve and deploy**. The wait
timer is zero, so nothing approves itself, and an unapproved deployment expires
after 30 days and fails the run.

**PyPI still shows the old version.** `https://pypi.org/pypi/typerig/json` and
the project page are served from a cache for some minutes after an upload. The
simple index settles at once:

```sh
curl -H "Accept: application/vnd.pypi.simple.v1+json" https://pypi.org/simple/typerig/
```

**The Actions run has an unhelpful title.** `release.yml` sets `run-name`, so
runs read `Release vX.Y.Z`. `check.yml` is consumed as a called workflow, where
`run-name` is ignored, so its own runs still show the commit subject.

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
