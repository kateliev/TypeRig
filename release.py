#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fire>=0.7,<1", "gitnextver>=1.0.4,<2", "packaging>=24", "twine>=6", "pytest>=8", "hatch-vcs>=0.4", "hatchling>=1.27", "fonttools>=4"]
# ///
# this_file: release.py
"""Test, build, tag and create a GitHub release. Run uv run release.py --help."""

import json
import sys
import tempfile
from pathlib import Path

from gitnextver.versioning import next_version

import _github
from _artifacts import build
from _release import (
    ROOT,
    TAG,
    clean,
    git,
    lock,
    prepare,
    run,
    tagged_head,
    verify_remote,
    version,
)


def next_tag(tags: list[str], bump: str) -> str:
    """Use gitnextver's pure API, with v2.1.0 as this project's release floor."""
    eligible = [tag for tag in tags if TAG.fullmatch(tag) and version_floor(tag)]
    return next_version(eligible, bump=bump, initial="v2.1.0")


def version_floor(tag: str) -> bool:
    """Ignore pre-migration stable tags when selecting the first new release."""
    from packaging.version import Version

    return Version(tag[1:]) >= Version("2.1.0")


def main(
    bump: str = "patch", tag: str = "", dry_run: bool = False, verbose: bool = False
) -> None:
    """Autonomously test/build and release the current clean checkout.

    Args:
        bump: patch (default), minor or major. First release is always v2.1.0.
        tag: Resume/release this existing tag at HEAD, including detached Actions
            checkouts. Omit to automatically choose/increment the version.
        dry_run: Fetch/read and run all tests/builds in temporary directories;
            create no source tags, pushes, releases or uploads.
        verbose: Show subprocess commands and their output on stderr.
    """
    if not isinstance(tag, str) or type(dry_run) is not bool:
        raise ValueError("tag must be a string; dry_run must be True or False")
    next_tag([], bump)  # Validate options before Git mutations.
    if tag:
        version(tag)
    with lock(ROOT):
        state = prepare(ROOT, write=not dry_run, verbose=verbose)
        if tag:
            selected = tagged_head(ROOT, tag)
            verify_remote(ROOT, selected, state["head"])
        else:
            branch = git("branch", "--show-current")
            if not dry_run and branch != state["branch"]:
                raise RuntimeError(
                    f"Automatic tagging requires the default branch {state['branch']}"
                )
            run(
                "git",
                "merge-base",
                "--is-ancestor",
                f"origin/{state['branch']}",
                "HEAD",
            )
            current = [
                t
                for t in git("tag", "--points-at", "HEAD").splitlines()
                if TAG.fullmatch(t) and version_floor(t)
            ]
            if len(current) > 1:
                raise RuntimeError(
                    "Multiple release tags at HEAD; select --tag explicitly"
                )
            selected = (
                current[0]
                if current
                else next_tag(git("tag", "--list").splitlines(), bump)
            )
        print(f"Preparing {selected} at {state['head']}", file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix="typerig-release-") as tmp:
            paths = build(ROOT, selected, Path(tmp), verbose)
            clean(ROOT)
            if git("rev-parse", "HEAD") != state["head"]:
                raise RuntimeError(
                    "HEAD changed while building; rerun from the new commit"
                )
            if dry_run:
                print(
                    json.dumps(
                        {
                            "tag": selected,
                            "commit": state["head"],
                            "dry_run": True,
                            "artifacts": [p.name for p in paths],
                        },
                        indent=2,
                    )
                )
                return
            if not tag:
                if selected not in git("tag", "--list").splitlines():
                    git("tag", "-a", selected, "-m", f"TypeRig {selected}")
                # Keep a tag after push failure so the same command can resume.
                git(
                    "push",
                    "--atomic",
                    "origin",
                    f"HEAD:refs/heads/{state['branch']}",
                    f"refs/tags/{selected}:refs/tags/{selected}",
                    verbose=verbose,
                )
            verify_remote(ROOT, selected, state["head"])
            url = _github.ensure_release(state["repo"], selected, paths, ROOT)
            print(
                json.dumps(
                    {"tag": selected, "commit": state["head"], "url": url}, indent=2
                )
            )


if __name__ == "__main__":
    import fire

    try:
        fire.Fire(main)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
