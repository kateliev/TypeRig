# this_file: _release.py
"""Shared release boundaries. No Git or network operations run on import."""

import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from packaging.version import Version

ROOT = Path(__file__).resolve().parent
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def version(tag: str) -> Version:
    """Require a canonical stable release tag, starting with v2.1.0."""
    if (
        not isinstance(tag, str)
        or not TAG.fullmatch(tag)
        or Version(tag[1:]) < Version("2.1.0")
    ):
        raise ValueError("Expected vMAJOR.MINOR.PATCH, starting at v2.1.0")
    return Version(tag[1:])


def run(
    *args: str,
    cwd: Path = ROOT,
    check: bool = True,
    verbose: bool = False,
    timeout: int = 120,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Use argument arrays on every platform, with noninteractive deadlines."""
    if verbose:
        print("+ " + " ".join(map(str, args)), file=sys.stderr)
    environment = dict(
        os.environ,
        GIT_TERMINAL_PROMPT="0",
        GH_PROMPT_DISABLED="1",
        GCM_INTERACTIVE="Never",
        UV_NO_PROGRESS="1",
    )
    if env is not None:
        for key, value in env.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
    try:
        result = subprocess.run(
            list(map(str, args)),
            cwd=cwd,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Install {args[0]} and put it on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{args[0]} timed out; remote writes may have completed. "
            "Inspect the tag and rerun with --tag to resume."
        ) from exc
    if check and result.returncode:
        raise RuntimeError(
            f"{args[0]} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
    if verbose:
        print(result.stdout + result.stderr, file=sys.stderr, end="")
    return result


def git(*args: str, cwd: Path = ROOT, **kwargs) -> str:
    """Return checked Git output without shell parsing."""
    return run("git", *args, cwd=cwd, **kwargs).stdout.strip()


def clean(root: Path) -> None:
    """Fail before touching dirty source work or SCM override environments."""
    if git("status", "--porcelain", "--untracked-files=all", cwd=root):
        raise RuntimeError("Release requires a clean checkout; commit your work first")
    if any(k.startswith("SETUPTOOLS_SCM_PRETEND_VERSION") for k in os.environ):
        raise RuntimeError("Remove SETUPTOOLS_SCM_PRETEND_VERSION overrides first")


@contextmanager
def lock(root: Path):
    """Serialize scripts in this checkout, including Windows Git worktrees."""
    path = Path(git("rev-parse", "--git-path", "typerig-release.lock", cwd=root))
    if not path.is_absolute():
        path = root / path
    try:
        handle = path.open("x")
    except FileExistsError as exc:
        raise RuntimeError(
            f"Release lock exists: {path}. Check its process before "
            "removing a stale lock."
        ) from exc
    try:
        with handle:
            handle.write(str(os.getpid()))
            handle.flush()
            yield
    finally:
        path.unlink()


def github_name(url: str) -> str:
    """Resolve common GitHub HTTPS/SSH remotes; reject embedded HTTP secrets."""
    if url.startswith("git@github.com:"):
        name = url.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(url)
        if (
            parsed.hostname != "github.com"
            or parsed.port is not None
            or parsed.scheme not in ("https", "ssh")
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (
                parsed.username
                and not (parsed.scheme == "ssh" and parsed.username == "git")
            )
        ):
            raise ValueError(
                "origin must be a GitHub HTTPS or SSH URL without credentials"
            )
        name = parsed.path.lstrip("/")
    name = name.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
        raise ValueError("origin must identify exactly one GitHub owner/repository")
    return name


def prepare(root: Path, *, write: bool, verbose: bool) -> dict:
    """Check source and remote identity, fetch tags, and verify GitHub access."""
    import json

    clean(root)
    if Path(git("rev-parse", "--show-toplevel", cwd=root)).resolve() != root.resolve():
        raise RuntimeError("Scripts must live at the Git repository root")
    if git("rev-parse", "--is-shallow-repository", cwd=root) == "true":
        raise RuntimeError("Fetch full history first: git fetch --unshallow origin")
    repo = github_name(git("remote", "get-url", "origin", cwd=root))
    pushes = git(
        "remote", "get-url", "--push", "--all", "origin", cwd=root
    ).splitlines()
    if len(pushes) != 1 or github_name(pushes[0]) != repo:
        raise RuntimeError(
            "origin fetch/push destinations differ; choose one repository"
        )
    info = json.loads(
        run(
            "gh",
            "repo",
            "view",
            repo,
            "--json",
            "nameWithOwner,defaultBranchRef,viewerPermission",
            cwd=root,
            verbose=verbose,
        ).stdout
    )
    if info["nameWithOwner"].casefold() != repo.casefold():
        raise RuntimeError("GitHub repository identity does not match origin")
    # Actions' GITHUB_TOKEN reports an empty viewerPermission; its access is
    # granted by the workflow's `permissions:` block, so trust that instead.
    permission = info["viewerPermission"]
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true" and not permission
    if write and not in_actions and permission not in ("WRITE", "MAINTAIN", "ADMIN"):
        raise RuntimeError("GitHub write access is required")
    git("fetch", "--tags", "origin", cwd=root, verbose=verbose)
    return {
        "repo": repo,
        "branch": info["defaultBranchRef"]["name"],
        "head": git("rev-parse", "HEAD", cwd=root),
    }


def tagged_head(root: Path, tag: str = "") -> str:
    """Require a unique stable tag at HEAD, or validate the requested one."""
    if not tag:
        tags = [
            t
            for t in git("tag", "--points-at", "HEAD", cwd=root).splitlines()
            if TAG.fullmatch(t) and Version(t[1:]) >= Version("2.1.0")
        ]
        if len(tags) != 1:
            raise RuntimeError("Use --tag=vX.Y.Z to select an existing release at HEAD")
        tag = tags[0]
    version(tag)
    if git("rev-parse", f"refs/tags/{tag}^{{commit}}", cwd=root) != git(
        "rev-parse", "HEAD", cwd=root
    ):
        raise RuntimeError(f"{tag} does not point at HEAD")
    return tag


def verify_remote(root: Path, tag: str, head: str) -> None:
    """Resolve both lightweight and annotated tags on the actual remote."""
    refs = dict(
        line.split()[::-1]
        for line in git(
            "ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}", cwd=root
        ).splitlines()
    )
    if refs.get(f"refs/tags/{tag}^{{}}", refs.get(f"refs/tags/{tag}")) != head:
        raise RuntimeError(f"origin {tag} is missing or does not match HEAD")
