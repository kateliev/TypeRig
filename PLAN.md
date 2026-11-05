---
this_file: PLAN.md
---

# TypeRig: remaining plan

1. Qualify the exact newer source with the tracked CI and standalone checks.
2. Verify changed host proxies and tools separately with owned fixtures in the applicable host.
3. Qualify the reviewed documentation milestone, verify its remote SHA and integrate into `master` under the applicable gates.
4. After integration and recovery checks, remove only proven obsolete items without unique or attached owner work.

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

Preserve Vassil Kateliev’s authorship and MPL-2.0 terms in LICENSE.
The geometry core runs outside FontLab. Host proxies and Scripts require
the corresponding host. Do not load an alternate Qt binding into FontLab.

Follow [AGENTS.md](AGENTS.md) for independent review and qualified milestone delivery.
Keep Issue 123 paused and native/installation/publication gates separate.
