# this_file: tests/test_boundaries.py
"""Preflight and native Git ref checks against isolated repositories."""

import json
import subprocess

import pytest

import _artifacts
import _release as tools


@pytest.fixture
def prepared(repo, monkeypatch):
    tools.git("remote", "add", "origin", "https://github.com/owner/repo.git", cwd=repo)
    payload = {
        "nameWithOwner": "owner/repo",
        "defaultBranchRef": {"name": "master"},
        "viewerPermission": "WRITE",
    }
    original = tools.run
    calls = []

    def command(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("gh", "repo"):
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
        if args[:2] == ("git", "fetch"):
            return subprocess.CompletedProcess(args, 0, "", "")
        return original(*args, **kwargs)

    monkeypatch.setattr(tools, "run", command)
    return payload, calls


def test_prepare_checks_identity_access_and_fetches(repo, prepared):
    state = tools.prepare(repo, write=True, verbose=False)
    assert state["repo"] == "owner/repo"
    assert state["head"] == tools.git("rev-parse", "HEAD", cwd=repo)
    assert ("git", "fetch", "--tags", "origin") in prepared[1]


def test_prepare_refuses_wrong_identity_before_fetch(repo, prepared):
    prepared[0]["nameWithOwner"] = "someone/else"
    with pytest.raises(RuntimeError, match="identity"):
        tools.prepare(repo, write=True, verbose=False)
    assert ("git", "fetch", "--tags", "origin") not in prepared[1]


def test_prepare_read_only_permission_cannot_release(repo, prepared):
    prepared[0]["viewerPermission"] = "READ"
    with pytest.raises(RuntimeError, match="write access"):
        tools.prepare(repo, write=True, verbose=False)
    assert tools.prepare(repo, write=False, verbose=False)["repo"] == "owner/repo"


def test_prepare_refuses_different_push_repository(repo, prepared):
    tools.git(
        "remote",
        "set-url",
        "--push",
        "origin",
        "https://github.com/other/repo",
        cwd=repo,
    )
    with pytest.raises(RuntimeError, match="destinations differ"):
        tools.prepare(repo, write=True, verbose=False)


def test_prepare_refuses_shallow_history(repo, monkeypatch):
    original = tools.git

    def git(*args, **kwargs):
        if args == ("rev-parse", "--is-shallow-repository"):
            return "true"
        return original(*args, **kwargs)

    monkeypatch.setattr(tools, "git", git)
    with pytest.raises(RuntimeError, match="unshallow"):
        tools.prepare(repo, write=True, verbose=False)


def test_clean_refuses_version_override(repo, monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION_FOR_TYPERIG", "9.0.0")
    with pytest.raises(RuntimeError, match="overrides"):
        tools.clean(repo)


@pytest.mark.parametrize("annotated", [False, True])
def test_remote_check_resolves_lightweight_and_annotated_tags(
    repo, tmp_path, annotated
):
    remote = tmp_path / "remote.git"
    tools.git("init", "--bare", str(remote), cwd=tmp_path)
    tools.git("remote", "add", "origin", str(remote), cwd=repo)
    args = ["tag", "v2.1.0"]
    if annotated:
        args += ["-a", "-m", "owned release"]
    tools.git(*args, cwd=repo)
    tools.git("push", "origin", "refs/tags/v2.1.0", cwd=repo)
    head = tools.git("rev-parse", "HEAD", cwd=repo)
    tools.verify_remote(repo, "v2.1.0", head)
    assert tools.tagged_head(repo) == "v2.1.0"
    with pytest.raises(RuntimeError, match="does not match"):
        tools.verify_remote(repo, "v2.1.0", "wrong")


def test_tag_selection_refuses_ambiguity_and_wrong_commit(repo):
    with pytest.raises(RuntimeError, match="select"):
        tools.tagged_head(repo)
    tools.git("tag", "v2.1.0", cwd=repo)
    tools.git("tag", "v2.1.1", cwd=repo)
    with pytest.raises(RuntimeError, match="select"):
        tools.tagged_head(repo)
    tools.git("commit", "--allow-empty", "-m", "new commit", cwd=repo)
    with pytest.raises(RuntimeError, match="does not point"):
        tools.tagged_head(repo, "v2.1.0")


def test_run_verbose_keeps_output_on_stderr(capsys):
    import sys

    result = tools.run(sys.executable, "-c", 'print("owned")', verbose=True)
    assert result.stdout.strip() == "owned"
    captured = capsys.readouterr()
    assert not captured.out and "owned" in captured.err


def test_empty_token_is_removed_for_oidc(monkeypatch):
    import sys

    monkeypatch.setenv("UV_PUBLISH_TOKEN", "")
    result = tools.run(
        sys.executable,
        "-c",
        'import os; print("UV_PUBLISH_TOKEN" in os.environ)',
        env={"UV_PUBLISH_TOKEN": None},
    )
    assert result.stdout.strip() == "False"


def test_regression_commands_include_every_standalone_suite(repo, monkeypatch):
    calls = []
    monkeypatch.setattr(
        _artifacts, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    _artifacts.run_checks(repo, False)
    assert len(calls) == 3
    assert "tests" in calls[0][0]
    assert "Lib/typerig/core/algo/test_outline_cleanup.py" in calls[0][0]
    assert all(call[1]["env"]["PYTHONPATH"] == str(repo / "Lib") for call in calls)
