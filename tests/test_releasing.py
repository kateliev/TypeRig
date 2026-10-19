# this_file: tests/test_releasing.py
"""Release boundaries tested with owned Git fixtures and fake remote services."""

import subprocess
from pathlib import Path

import pytest

import _release as tools
import publish
import release


@pytest.mark.parametrize("tag", ["v2.1.0", "v2.10.123", "v3.0.0"])
def test_version_accepts_canonical_release_tags(tag):
    assert str(tools.version(tag)) == tag[1:]


@pytest.mark.parametrize(
    "tag",
    [
        "v2.0.9",
        "2.1.0",
        "v02.1.0",
        "v2.1.0rc1",
        "v2.1.0-Py3.10",
        "v2.1.0\n",
        "--bad",
        "",
    ],
)
def test_version_refuses_ambiguous_and_legacy_tags(tag):
    with pytest.raises(ValueError):
        tools.version(tag)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/kateliev/TypeRig.git",
        "git@github.com:kateliev/TypeRig.git",
        "ssh://git@github.com/kateliev/TypeRig.git",
    ],
)
def test_remote_url_resolves_consistently(url):
    assert tools.github_name(url) == "kateliev/TypeRig"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a/b",
        "file:///tmp/repo",
        "https://token@github.com/a/b",
        "github.com/a/b",
    ],
)
def test_remote_url_refuses_other_hosts_and_embedded_credentials(url):
    with pytest.raises(ValueError):
        tools.github_name(url)


def test_clean_check_refuses_untracked_files(repo):
    tools.clean(repo)
    (repo / "pending.py").write_text("pending")
    with pytest.raises(RuntimeError, match="clean"):
        tools.clean(repo)


def test_release_lock_excludes_second_operation_and_cleans_up(repo):
    with tools.lock(repo):
        with pytest.raises(RuntimeError, match="lock"):
            with tools.lock(repo):
                pass
    with tools.lock(repo):
        pass


def test_missing_tool_is_an_actionable_error(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="Install"):
        tools.run("uv", "--version")


def test_timeout_reports_unknown_completion(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="may have completed"):
        tools.run("git", "push")


def test_command_failure_is_not_success():
    import sys

    with pytest.raises(RuntimeError, match="failure"):
        tools.run(sys.executable, "-c", 'raise SystemExit("failure")')


def test_publish_uses_explicit_artifacts_and_uv_duplicate_check():
    artifacts = [Path("a.whl"), Path("a.tar.gz")]
    args = publish.publish_command(artifacts, test_pypi=False, dry_run=True)
    assert args[:2] == ["uv", "publish"]
    assert "--check-url" in args and "--dry-run" in args
    assert args[-2:] == ["a.whl", "a.tar.gz"]
    assert not any("*" in arg for arg in args)


def test_testpypi_has_matching_upload_and_check_urls():
    args = publish.publish_command([], test_pypi=True, dry_run=False)
    assert "https://test.pypi.org/legacy/" in args
    assert "https://test.pypi.org/simple/" in args
    assert "--dry-run" not in args


def test_next_tag_uses_published_gitnextver():
    assert release.next_tag(["v2.0.5-Py3.10"], "patch") == "v2.1.0"
    assert release.next_tag(["v2.1.9"], "minor") == "v2.2.0"
    assert release.next_tag(["v2.1.9"], "major") == "v3.0.0"
