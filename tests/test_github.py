# this_file: tests/test_github.py
"""Idempotency and partial-failure cases for the GitHub service boundary."""

import json
import subprocess
from pathlib import Path

import pytest

import _github as github


@pytest.fixture
def service(tmp_path, monkeypatch):
    paths = [
        tmp_path / "typerig-2.1.0-py3-none-any.whl",
        tmp_path / "typerig-2.1.0.tar.gz",
    ]
    for path in paths:
        path.write_bytes(path.name.encode())
    state = {
        "release": None,
        "bytes": {},
        "calls": [],
        "lost_upload": False,
        "creation_conflict": False,
        "upload_failure": False,
    }

    def command(*args, **kwargs):
        state["calls"].append(args)
        code, out, err = 0, "", ""
        if args[1] == "api":
            if state["release"] is None:
                code, err = 1, "gh: Not Found (HTTP 404)"
            else:
                out = json.dumps(state["release"])
        elif args[2] == "create":
            state["release"] = {
                "draft": True,
                "prerelease": False,
                "assets": [],
                "html_url": "https://github.com/owner/repo/releases/tag/v2.1.0",
            }
            if state["creation_conflict"]:
                code, err = 1, "already exists"
        elif args[2] == "upload":
            path = Path(args[4])
            if state["upload_failure"]:
                return subprocess.CompletedProcess(args, 1, "", "upload failed")
            state["bytes"][path.name] = path.read_bytes()
            state["release"]["assets"].append(
                {"name": path.name, "digest": github.digest(path)}
            )
            if state["lost_upload"]:
                code, err = 1, "response lost"
        elif args[2] == "download":
            name = args[args.index("--pattern") + 1]
            directory = Path(args[args.index("--dir") + 1])
            (directory / name).write_bytes(state["bytes"][name])
        elif args[2] == "edit":
            state["release"]["draft"] = False
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, out, err)

    monkeypatch.setattr(github, "run", command)
    return state, paths


def test_creates_verifies_publishes_and_reruns_without_asset_writes(service, tmp_path):
    state, paths = service
    url = github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    assert url.endswith("/v2.1.0") and not state["release"]["draft"]
    before = len(state["calls"])
    assert github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path) == url
    assert all(
        call[2] not in ("create", "upload", "edit") for call in state["calls"][before:]
    )
    assert not any("--clobber" in call for call in state["calls"])


@pytest.mark.parametrize("failure", ["lost_upload", "creation_conflict"])
def test_resumes_after_concurrent_creation_or_lost_upload_response(
    service, tmp_path, failure
):
    state, paths = service
    state[failure] = True
    github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    assert not state["release"]["draft"]


def test_bad_existing_digest_is_never_overwritten(service, tmp_path):
    state, paths = service
    github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    state["release"]["assets"][0]["digest"] = "sha256:wrong"
    with pytest.raises(RuntimeError, match="differs"):
        github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)


def test_downloaded_bytes_are_checked_even_without_advertised_digest(service, tmp_path):
    state, paths = service
    github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    for asset in state["release"]["assets"]:
        asset.pop("digest")
    state["bytes"][paths[0].name] = b"corrupt"
    with pytest.raises(RuntimeError, match="Downloaded asset differs"):
        github.verify_assets("owner/repo", "v2.1.0", paths, tmp_path)


def test_missing_asset_in_published_release_requires_inspection(service, tmp_path):
    state, paths = service
    github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    state["release"]["assets"].pop()
    with pytest.raises(RuntimeError, match="Published release lacks"):
        github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)


def test_failed_upload_leaves_unpublished_draft_for_recovery(service, tmp_path):
    state, paths = service
    state["upload_failure"] = True
    with pytest.raises(RuntimeError, match="upload failed"):
        github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
    assert state["release"]["draft"]


def test_auth_failure_is_not_treated_as_missing_release(monkeypatch):
    monkeypatch.setattr(
        github,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "HTTP 401"),
    )
    with pytest.raises(RuntimeError, match="HTTP 401"):
        github.info("owner/repo", "v2.1.0")


def test_release_creation_failure_stops_before_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(github, "info", lambda *a, **kw: None)
    monkeypatch.setattr(
        github,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "permission denied"),
    )
    with pytest.raises(RuntimeError, match="creation failed"):
        github.ensure_release("owner/repo", "v2.1.0", [], tmp_path)


def test_prerelease_cannot_be_published_as_stable(service, tmp_path):
    state, paths = service
    state["release"] = {"prerelease": True}
    with pytest.raises(RuntimeError, match="prerelease"):
        github.ensure_release("owner/repo", "v2.1.0", paths, tmp_path)
