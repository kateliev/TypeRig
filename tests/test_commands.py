# this_file: tests/test_commands.py
"""Full CLI orchestration with real local tags, no public remote writes."""

import json
import subprocess

import pytest

import _release as tools
import publish
import release


@pytest.mark.parametrize("module", [release, publish])
@pytest.mark.parametrize("tag", [0, False, None])
def test_fire_literal_tags_cannot_accidentally_select_automatic_mode(module, tag):
    with pytest.raises(ValueError, match="tag must be a string"):
        module.main(tag=tag)


@pytest.fixture
def control(repo, monkeypatch):
    head = tools.git("rev-parse", "HEAD", cwd=repo)
    state = {"repo": "owner/repo", "branch": "master", "head": head}
    calls = []

    def local_git(*args, **kwargs):
        if args[0] == "push":
            calls.append(args)
            return ""
        return tools.git(*args, cwd=repo, **kwargs)

    def build(root, tag, temp, verbose):
        paths = [temp / "a.whl", temp / "a.tar.gz"]
        for path in paths:
            path.write_bytes(b"owned")
        return paths

    for module in (release, publish):
        monkeypatch.setattr(module, "ROOT", repo)
        monkeypatch.setattr(module, "git", local_git)
        monkeypatch.setattr(module, "prepare", lambda *a, **kw: state)
        monkeypatch.setattr(
            module, "verify_remote", lambda *a, **kw: calls.append(("verify",))
        )
    monkeypatch.setattr(release, "build", build)
    monkeypatch.setattr(
        release, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "", "")
    )
    monkeypatch.setattr(
        release._github,
        "ensure_release",
        lambda *a: (
            calls.append(("github",))
            or "https://github.com/owner/repo/releases/tag/v2.1.0"
        ),
    )
    return state, calls


def test_release_dry_run_builds_without_tag_or_push(repo, control, capsys):
    release.main(dry_run=True)
    result = json.loads(capsys.readouterr().out)
    assert result["tag"] == "v2.1.0" and result["dry_run"]
    assert not tools.git("tag", cwd=repo)
    assert control[1] == []


def test_release_creates_only_first_tag_and_reuses_it_on_retry(repo, control):
    release.main()
    assert tools.git("tag", cwd=repo) == "v2.1.0"
    assert tools.git("cat-file", "-t", "v2.1.0", cwd=repo) == "tag"
    release.main()
    assert tools.git("tag", cwd=repo) == "v2.1.0"
    pushes = [args for args in control[1] if args[0] == "push"]
    assert all(
        args
        == (
            "push",
            "--atomic",
            "origin",
            "HEAD:refs/heads/master",
            "refs/tags/v2.1.0:refs/tags/v2.1.0",
        )
        for args in pushes
    )


def test_existing_tag_mode_handles_detached_head_without_push(repo, control):
    tools.git("tag", "v2.1.0", cwd=repo)
    tools.git("checkout", "--detach", "HEAD", cwd=repo)
    release.main(tag="v2.1.0")
    assert not any(args[0] == "push" for args in control[1])


def test_release_refuses_non_default_branch(repo, control):
    tools.git("switch", "-c", "feature", cwd=repo)
    with pytest.raises(RuntimeError, match="default branch"):
        release.main()
    assert not tools.git("tag", cwd=repo)


def test_dry_run_can_preview_feature_branch(repo, control):
    tools.git("switch", "-c", "feature", cwd=repo)
    release.main(dry_run=True)
    assert not tools.git("tag", cwd=repo)


def test_build_failure_does_not_leave_source_tag(repo, control, monkeypatch):
    def fail(*args):
        raise RuntimeError("build failure")

    monkeypatch.setattr(release, "build", fail)
    with pytest.raises(RuntimeError, match="build failure"):
        release.main()
    assert not tools.git("tag", cwd=repo)


def test_changed_head_is_detected_before_source_tag(repo, control, monkeypatch):
    control[0]["head"] = "not-the-current-commit"
    with pytest.raises(RuntimeError, match="HEAD changed"):
        release.main()
    assert not tools.git("tag", cwd=repo)


@pytest.mark.parametrize(
    "metadata", [None, {"draft": True}, {"draft": False, "prerelease": True}]
)
def test_publish_refuses_unreleased_or_draft_tag(repo, control, monkeypatch, metadata):
    tools.git("tag", "v2.1.0", cwd=repo)
    monkeypatch.setattr(publish._github, "info", lambda *a, **kw: metadata)
    with pytest.raises(RuntimeError, match="Run release.py first"):
        publish.main()


def test_publish_downloads_verified_assets_and_invokes_uv(
    repo, control, monkeypatch, capsys
):
    tools.git("tag", "v2.1.0", cwd=repo)
    calls = []
    monkeypatch.setattr(publish._github, "info", lambda *a, **kw: {"draft": False})

    def download(owner, tag, name, directory, root):
        path = directory / name
        path.write_bytes(b"owned")
        return path

    monkeypatch.setattr(publish._github, "download", download)
    monkeypatch.setattr(
        publish._github, "verify_assets", lambda *a: calls.append(("verify-assets",))
    )
    monkeypatch.setattr(publish, "artifacts_ok", lambda *a: calls.append(("metadata",)))

    def command(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(publish, "run", command)
    publish.main(tag="v2.1.0", dry_run=True)
    result = json.loads(capsys.readouterr().out)
    assert result == {"tag": "v2.1.0", "dry_run": True, "index": "pypi"}
    uv = next(args for args in calls if args[0] == "uv")
    assert "--dry-run" in uv
    assert uv[-2].endswith(".whl") and uv[-1].endswith(".tar.gz")
