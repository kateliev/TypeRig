#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fire>=0.7,<1", "packaging>=24", "twine>=6"]
# ///
# this_file: publish.py
"""Publish verified GitHub release assets using uv, on macOS or Windows."""

import json
import os
import sys
import tempfile
from pathlib import Path

import _github
from _artifacts import artifacts_ok
from _release import (
    ROOT,
    clean,
    git,
    lock,
    prepare,
    run,
    tagged_head,
    verify_remote,
    version,
)


def publish_command(paths: list[Path], test_pypi: bool, dry_run: bool) -> list[str]:
    """Use uv's hash-aware duplicate checks and exact files, never stale globs."""
    upload = (
        "https://test.pypi.org/legacy/"
        if test_pypi
        else "https://upload.pypi.org/legacy/"
    )
    check = "https://test.pypi.org/simple/" if test_pypi else "https://pypi.org/simple/"
    args = [
        "uv",
        "publish",
        "--no-config",
        "--publish-url",
        upload,
        "--check-url",
        check,
        "--trusted-publishing",
        "never" if dry_run else "automatic",
    ]
    if dry_run:
        args.append("--dry-run")
    return [*args, *map(str, paths)]


def main(
    tag: str = "", test_pypi: bool = False, dry_run: bool = False, verbose: bool = False
) -> None:
    """Download, verify and publish the existing release at HEAD.

    Args:
        tag: Existing stable tag at HEAD; otherwise infer its unique release tag.
        test_pypi: Use TestPyPI for both uploads and duplicate checking.
        dry_run: Download/verify and invoke uv publish --dry-run; upload nothing.
        verbose: Show subprocess commands and output on stderr.

    Authentication uses UV_PUBLISH_TOKEN or uv's trusted publishing (Actions
    OIDC). Tokens stay in the environment and never appear in command arguments.
    A rerun skips identical files already uploaded, but refuses different bytes.
    """
    if (
        not isinstance(tag, str)
        or type(dry_run) is not bool
        or type(test_pypi) is not bool
    ):
        raise ValueError(
            "tag must be a string; dry_run/test_pypi must be True or False"
        )
    if tag:
        version(tag)
    with lock(ROOT):
        state = prepare(ROOT, write=False, verbose=verbose)
        selected = tagged_head(ROOT, tag)
        verify_remote(ROOT, selected, state["head"])
        info = _github.info(state["repo"], selected, root=ROOT)
        if info is None or info["draft"] or info.get("prerelease"):
            raise RuntimeError(
                "Run release.py first; publishing needs a public stable GitHub release"
            )
        with tempfile.TemporaryDirectory(prefix="typerig-publish-") as tmp:
            number = str(version(selected))
            names = [f"typerig-{number}-py3-none-any.whl", f"typerig-{number}.tar.gz"]
            paths = [
                _github.download(state["repo"], selected, name, Path(tmp), ROOT)
                for name in names
            ]
            artifacts_ok(paths, selected)
            _github.verify_assets(state["repo"], selected, paths, ROOT)
            run(
                sys.executable,
                "-m",
                "twine",
                "check",
                *map(str, paths),
                verbose=verbose,
            )
            clean(ROOT)
            if git("rev-parse", "HEAD") != state["head"]:
                raise RuntimeError("HEAD changed during publication preflight")
            environment = {
                "UV_PUBLISH_TOKEN": os.environ.get("UV_PUBLISH_TOKEN") or None
            }
            result = run(
                *publish_command(paths, test_pypi, dry_run),
                env=environment,
                verbose=verbose,
                timeout=600,
            )
            print(result.stdout + result.stderr, file=sys.stderr, end="")
            print(
                json.dumps(
                    {
                        "tag": selected,
                        "dry_run": dry_run,
                        "index": "testpypi" if test_pypi else "pypi",
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    import fire

    try:
        fire.Fire(main)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
