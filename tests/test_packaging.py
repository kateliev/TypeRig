# this_file: tests/test_packaging.py
"""Real builds and pip installs, from owned repository copies only."""

import io
import os
import shutil
import subprocess
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

import _artifacts
import _release as tools


@pytest.fixture
def package_repo(repo):
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(
        source / "Lib",
        repo / "Lib",
        ignore=shutil.ignore_patterns("__pycache__", ".claude", ".DS_Store"),
    )
    for name in (
        ".gitignore",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "DEPENDENCIES.md",
        "RELEASING.md",
        "release.py",
        "publish.py",
        "_release.py",
        "_artifacts.py",
        "_github.py",
    ):
        shutil.copyfile(source / name, repo / name)
    # An intentionally tracked tooling file must stay outside distribution scope.
    (repo / ".omc").mkdir()
    (repo / ".omc/local.json").write_text('{"private": true}')
    tools.git("add", "-A", cwd=repo)
    tools.git("commit", "-m", "owned package fixture", cwd=repo)
    tools.git("tag", "v2.0.5-Py3.10", cwd=repo)
    return repo


def test_build_has_exact_payload_and_both_formats_install_with_pip(
    package_repo, tmp_path, monkeypatch
):
    monkeypatch.setattr(_artifacts, "run_checks", lambda *a: None)
    work = tmp_path / "build with spaces"
    work.mkdir()
    paths = _artifacts.build(package_repo, "v2.1.0", work, False)
    assert tools.git("tag", cwd=package_repo) == "v2.0.5-Py3.10", (
        "Build must not tag source"
    )
    tracked = tools.git("ls-files", "Lib", cwd=package_repo).splitlines()
    assert tracked
    for path in paths:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            assert all(
                name.startswith(("typerig/", "typerig-2.1.0.dist-info/"))
                for name in files
            )
            for name in tracked:
                assert files[name.removeprefix("Lib/")] == subprocess.check_output(
                    ["git", "show", f"HEAD:{name}"], cwd=package_repo
                ), name
        else:
            with tarfile.open(path) as archive:
                files = {
                    m.name.split("/", 1)[1]: archive.extractfile(m).read()
                    for m in archive.getmembers()
                    if m.isfile()
                }
            for name in tracked:
                assert files[name] == subprocess.check_output(
                    ["git", "show", f"HEAD:{name}"], cwd=package_repo
                ), name
        assert not any(
            ".omc/" in name or "Scripts/" in name or ".claude/" in name
            for name in files
        )
        venv = tmp_path / ("wheel-venv" if path.suffix == ".whl" else "sdist-venv")
        tools.run("uv", "venv", "--seed", "--python", "3.11", str(venv), cwd=tmp_path)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        tools.run(str(python), "-m", "pip", "install", str(path), cwd=tmp_path)
        smoke = """
from pathlib import Path
from importlib.metadata import version
from importlib.resources import files
import typerig
from typerig.core.objects.point import Point
from typerig.core.fileio import trfont, ufo, designspace
assert version('typerig') == '2.1.0'
assert (Point(1, 2) + Point(3, 4)).x == 4
assert files('typerig').joinpath('proxy/fl/gui/resource/typerig-icons.ttf').is_file()
assert files('typerig').joinpath('proxy/gs3/gui/assets/typerig-icons.ttf').is_file()
print(Path(typerig.__file__).resolve())
"""
        installed = tools.run(
            str(python), "-c", smoke, cwd=tmp_path, env={"PYTHONPATH": ""}
        ).stdout.strip()
        assert Path(installed).is_relative_to(venv.resolve()), installed


@pytest.mark.parametrize(
    "nearer_tag",
    [
        "v9.9.9-Py3.10",
        "v9.9.9rc1",
        "v9.9.9.9",
        "vv9.9.9",
        "v09.9.9",
        "v9.09.9",
        "v9.9.09",
    ],
)
def test_hatch_vcs_ignores_newer_nonrelease_tags(package_repo, tmp_path, nearer_tag):
    tools.git("tag", "v2.1.0", cwd=package_repo)
    tools.git("commit", "--allow-empty", "-m", "development", cwd=package_repo)
    tools.git("tag", nearer_tag, cwd=package_repo)
    output = tmp_path / "development-dist"
    tools.run(
        "uv",
        "build",
        "--wheel",
        "--out-dir",
        str(output),
        cwd=package_repo,
        timeout=180,
    )
    with zipfile.ZipFile(next(output.glob("*.whl"))) as archive:
        metadata = BytesParser().parsebytes(
            archive.read(
                next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            )
        )
    assert metadata["Version"].startswith("2.1.1.dev1+"), metadata["Version"]


def test_artifact_metadata_refuses_wrong_version_and_file_selection(tmp_path):
    wheel = tmp_path / "typerig-2.1.0-py3-none-any.whl"
    sdist = tmp_path / "typerig-2.1.0.tar.gz"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "typerig-2.1.0.dist-info/METADATA", b"Name: typerig\nVersion: 2.1.1\n"
        )
    with tarfile.open(sdist, "w:gz") as archive:
        data = b"Name: typerig\nVersion: 2.1.0\n"
        member = tarfile.TarInfo("typerig-2.1.0/PKG-INFO")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    with pytest.raises(RuntimeError, match="incorrect name/version"):
        _artifacts.artifacts_ok([wheel, sdist], "v2.1.0")
    with pytest.raises(RuntimeError, match="exactly"):
        _artifacts.artifacts_ok([wheel], "v2.1.0")
