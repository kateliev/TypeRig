# this_file: _artifacts.py
"""Build and inspect immutable, tag-derived TypeRig distribution artifacts."""

import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

from _release import git, run, tagged_head, version


def artifacts_ok(paths: list[Path], tag: str) -> None:
    """Validate both distribution names and embedded release metadata."""
    expected = str(version(tag))
    if {p.name for p in paths} != {
        f"typerig-{expected}.tar.gz",
        f"typerig-{expected}-py3-none-any.whl",
    }:
        raise RuntimeError("Expected exactly the release wheel and source archive")
    for path in paths:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                names = [
                    n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
                ]
                data = archive.read(names[0]) if len(names) == 1 else b""
        else:
            with tarfile.open(path) as archive:
                names = [
                    m
                    for m in archive.getmembers()
                    if m.name == f"typerig-{expected}/PKG-INFO"
                ]
                data = archive.extractfile(names[0]).read() if len(names) == 1 else b""
        metadata = BytesParser().parsebytes(data)
        if metadata.get("Name") != "typerig" or metadata.get("Version") != expected:
            raise RuntimeError(f"{path.name} has incorrect name/version metadata")


def build(root: Path, tag: str, directory: Path, verbose: bool) -> list[Path]:
    """Build a tagged, isolated LF checkout, never tag the user's source to test."""
    snapshot = directory / "source"
    git(
        "clone",
        "--no-hardlinks",
        "--no-checkout",
        "--config",
        "core.autocrlf=false",
        str(root),
        str(snapshot),
        cwd=directory,
        verbose=verbose,
    )
    head = git("rev-parse", "HEAD", cwd=root)
    git("checkout", "--detach", head, cwd=snapshot)
    if tag not in git("tag", "--list", cwd=snapshot).splitlines():
        git("tag", tag, head, cwd=snapshot)
    tagged_head(snapshot, tag)
    run_checks(snapshot, verbose)
    output = directory / "dist"
    run(
        "uv",
        "build",
        "--out-dir",
        str(output),
        cwd=snapshot,
        verbose=verbose,
        timeout=600,
        env={
            "SOURCE_DATE_EPOCH": git("show", "-s", "--format=%ct", "HEAD", cwd=snapshot)
        },
    )
    paths = sorted(p for p in output.iterdir() if p.name.endswith((".whl", ".tar.gz")))
    artifacts_ok(paths, tag)
    run(
        sys.executable,
        "-m",
        "twine",
        "check",
        *map(str, paths),
        cwd=snapshot,
        verbose=verbose,
    )
    return paths


def run_checks(root: Path, verbose: bool) -> None:
    """Run tooling and standalone core regressions without loading host APIs."""
    env = {"PYTHONPATH": str(root / "Lib"), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    run(
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests",
        "Lib/typerig/core/algo/test_cjk.py",
        "Lib/typerig/core/algo/test_outline_cleanup.py",
        cwd=root,
        env=env,
        verbose=verbose,
        timeout=600,
    )
    for module in ("objects/test_objects.py", "actions/test_actions.py"):
        run(
            sys.executable,
            str(root / "Lib/typerig/core" / module),
            cwd=root,
            env=env,
            verbose=verbose,
            timeout=120,
        )
