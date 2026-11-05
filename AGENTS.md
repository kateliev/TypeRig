---
this_file: AGENTS.md
---

# TypeRig: agent guide

A Python library for font geometry, interpolation and editor tools.

`Lib/typerig/` contains the package, `Scripts/` contains host tools,
`Docs/` contains reference material and `tests/` contains automated tests.

## Checks

The current observed source base is `960d25f99a022faaa5ca85e691363148be90d3b4`.
It contains eight newer source commits than canonical `46a0f0b`.
The earlier handoff observed `e3f06f5` at a seven-commit offset;
the additional commit adds the Cleanup panel and enables it in configuration.
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

Pages is configured as legacy `master:/`. The six root guides are in its
publishing source, so their integration changes the site payload. Before
default delivery, bind the new exact integration SHA to independent review,
graph analysis, ordinary checks/hooks and the applicable D29 decision.
Retain actual triggered CI/Pages and required publication/browser proof
for that SHA. The successful `960d25f` baseline does not qualify it.

## Review and delivery

Read README, PLAN, TODO, WORK and CHANGELOG before work. Use an isolated checkout.
Preserve the owner's branches, index, edits, archives and licences.
Choose one small complete MVP. Name its callers, tests, fixtures, configuration
and exports. Use graph context and impact before source symbol changes.
Confirm stale, empty or unknown graph results against the actual source.

Run the exact repository checks. Keep the unchanged 80% coverage gate for each
complete changed production module where the milestone gate applies.
Documentation checks cover headers, fences, links, privacy and the exact diff.
Keep ordinary installed hooks active. Do not bypass a failed gate.
Obtain independent specification and quality review before a milestone commit.
Stage only the approved paths after checking their preimage hashes.
Run graph change analysis before committing.

Issue 230 authorizes reviewed, passing documentation milestone commits and pushes.
Verify the actual remote branch SHA after a push. Refresh remote refs before
integration. Reconcile concurrent work and consumers before primary-branch
integration. Run the applicable combined-source and CI checks.
Do not infer publication, installation or native acceptance from a branch push.
Do not create release tags, dispatch release workflows or publish packages for
this documentation milestone.

Before obsolete branch or file removal, verify recovery and integration.
Check fresh owner/worktree attachments and unique work. Preserve sealed evidence
and protected tags. Do not force-push or rewrite history by implication.
Keep PLAN future-facing and TODO flat with unchecked open tasks.
Record only verified scope in CHANGELOG and current checks in WORK.

Issue 123 remains paused. Issue 207 candidates require reconciliation with newer
source. Keep source tests, complete archives, installed origins/RECORD, native
workflows, canonical promotion, remote delivery and publication separate.
Do not read or mutate owner fonts, preferences, Output or global update queues.
Do not install or uninstall in the owner's FontLab user folder.
Preserve private configuration and source boundaries. Native work requires a
separate safe owned-fixture session under the workspace D30 checks and fences.
The D31 zone/master lane remains reserved. D29 generation/publication gates apply.

This repository integrates qualified work into `master`.

Preserve Vassil Kateliev’s authorship and MPL-2.0 terms in LICENSE.
The geometry core runs outside FontLab. Host proxies and Scripts require
the corresponding host. Do not load an alternate Qt binding into FontLab.
