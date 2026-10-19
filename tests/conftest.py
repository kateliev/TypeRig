# this_file: tests/conftest.py
"""Shared owned, local-only Git fixtures."""

import pytest

import _release as tools


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo with spaces"
    root.mkdir()
    tools.git("init", "-b", "master", cwd=root)
    tools.git("config", "user.name", "Test", cwd=root)
    tools.git("config", "user.email", "test@example.com", cwd=root)
    (root / "README.md").write_text("owned\n")
    tools.git("add", "README.md", cwd=root)
    tools.git("commit", "-m", "owned", cwd=root)
    return root
