# this_file: _github.py
"""Resumable GitHub release assets without replacing any published bytes."""

import hashlib
import json
import tempfile
from pathlib import Path

from _release import ROOT, run


def info(repo: str, tag: str, *, root: Path = ROOT) -> dict | None:
    """Find the tag's release, drafts included; the releases/tags endpoint hides drafts.

    Distinguishes a missing release from authentication/network failure.
    """
    result = run(
        "gh",
        "api",
        "--paginate",
        f"repos/{repo}/releases",
        "--jq",
        f'.[] | select(.tag_name == "{tag}")',
        cwd=root,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Cannot read GitHub release: {result.stderr}")
    decoder, text, end, found = json.JSONDecoder(), result.stdout.strip(), 0, []
    while end < len(text):
        release, end = decoder.raw_decode(text, end)
        found.append(release)
        while end < len(text) and text[end].isspace():
            end += 1
    if len(found) > 1:
        raise RuntimeError(f"Several GitHub releases use {tag}; delete the extras")
    return found[0] if found else None


def download(repo: str, tag: str, name: str, directory: Path, root: Path) -> Path:
    """Download an exact asset name, never overwrite source files."""
    run(
        "gh",
        "release",
        "download",
        tag,
        "--repo",
        repo,
        "--pattern",
        name,
        "--dir",
        str(directory),
        cwd=root,
    )
    return directory / name


def digest(path: Path) -> str:
    """Use GitHub's SHA-256 asset digest representation."""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify_assets(repo: str, tag: str, paths: list[Path], root: Path) -> dict:
    """Check downloaded public bytes as well as optional API digests."""
    release = info(repo, tag, root=root)
    if release is None:
        raise RuntimeError("GitHub release is missing")
    assets = {a["name"]: a for a in release["assets"]}
    with tempfile.TemporaryDirectory(prefix="typerig-verify-") as tmp:
        for path in paths:
            if path.name not in assets:
                raise RuntimeError(f"GitHub release is missing {path.name}")
            expected = digest(path)
            advertised = assets[path.name].get("digest")
            if advertised and advertised != expected:
                raise RuntimeError(
                    f"Existing asset differs: {path.name}; never overwrite it"
                )
            copy = download(repo, tag, path.name, Path(tmp), root)
            if digest(copy) != expected:
                raise RuntimeError(f"Downloaded asset differs: {path.name}")
    return release


def ensure_release(repo: str, tag: str, paths: list[Path], root: Path) -> str:
    """Resume drafts and concurrent creators; publish only after asset verification."""
    release = info(repo, tag, root=root)
    if release is None:
        result = run(
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--verify-tag",
            "--draft",
            "--title",
            f"TypeRig {tag[1:]}",
            "--generate-notes",
            cwd=root,
            check=False,
        )
        release = info(repo, tag, root=root)
        if release is None:
            raise RuntimeError(f"GitHub release creation failed: {result.stderr}")
    if release.get("prerelease"):
        raise RuntimeError("A stable tag must not have a prerelease GitHub release")
    assets = {a["name"]: a for a in release["assets"]}
    for path in paths:
        if path.name in assets:
            continue
        if not release["draft"]:
            raise RuntimeError(
                f"Published release lacks {path.name}; inspect it manually"
            )
        result = run(
            "gh",
            "release",
            "upload",
            tag,
            str(path),
            "--repo",
            repo,
            cwd=root,
            check=False,
        )
        if result.returncode:
            # Another creator may have uploaded it, or a response may be lost.
            current = info(repo, tag, root=root)
            if current is None or path.name not in {
                a["name"] for a in current["assets"]
            }:
                raise RuntimeError(f"Asset upload failed: {result.stderr}")
    release = verify_assets(repo, tag, paths, root)
    if release["draft"]:
        run("gh", "release", "edit", tag, "--repo", repo, "--draft=false", cwd=root)
    release = info(repo, tag, root=root)
    if release is None or release["draft"]:
        raise RuntimeError("GitHub release publication is not confirmed; rerun --tag")
    return release["html_url"]
