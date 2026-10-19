"""Exercise the add-on Dockerfile's source selection against local Git fixtures."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "sigenergy_optimizer_addon" / "Dockerfile"
BASH = (
    str(Path("C:/Program Files/Git/bin/bash.exe"))
    if os.name == "nt"
    else shutil.which("bash") or ""
)
if not Path(BASH).is_file():
    raise RuntimeError("Git Bash is required for Dockerfile source-pinning tests")


def _isolated_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("GIT_") or name in {"BASH_ENV", "ENV"}:
            env.pop(name, None)
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_COUNT="6",
        GIT_CONFIG_KEY_0="protocol.allow",
        GIT_CONFIG_VALUE_0="never",
        GIT_CONFIG_KEY_1="protocol.file.allow",
        GIT_CONFIG_VALUE_1="always",
        GIT_CONFIG_KEY_2="user.name",
        GIT_CONFIG_VALUE_2="Source pinning test",
        GIT_CONFIG_KEY_3="user.email",
        GIT_CONFIG_VALUE_3="source-pinning@example.invalid",
        GIT_CONFIG_KEY_4="init.defaultBranch",
        GIT_CONFIG_VALUE_4="main",
        GIT_CONFIG_KEY_5="core.hooksPath",
        GIT_CONFIG_VALUE_5=os.devnull,
        GIT_ALLOW_PROTOCOL="file",
    )
    return env


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_isolated_git_env(),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def source_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """Make an old tagged source and a newer default-branch source locally."""
    fixture_root = tmp_path_factory.mktemp("source-origin")
    origin = fixture_root / "origin.git"
    work = fixture_root / "work"
    _git(fixture_root, "init", "--bare", str(origin))
    _git(fixture_root, "init", str(work))
    (work / "VERSION_SOURCE").write_text("release-tag\n", encoding="utf-8")
    for relative, content in {
        "requirements.txt": "example-package==1.0\n",
        "app/__init__.py": "# fixture app\n",
        "app/VERSION_SOURCE": "release-tag\n",
        "app/release_version.txt": "2.3.61-haos72\n",
        "sigenergy_optimizer_addon/config.yaml": 'version: "2.3.61-haos72"\n',
        "templates/index.html": "fixture template\n",
        "static/site.css": "/* fixture */\n",
        ".env.example": "FIXTURE=1\n",
    }.items():
        path = work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "release source")
    tagged_commit = _git(work, "rev-parse", "HEAD")
    _git(work, "tag", "v2.3.61-haos72")

    (work / "VERSION_SOURCE").write_text("newer-default-branch\n", encoding="utf-8")
    (work / "app/VERSION_SOURCE").write_text("newer-default-branch\n", encoding="utf-8")
    (work / "app/release_version.txt").write_text("2.3.62-haos73\n", encoding="utf-8")
    (work / "sigenergy_optimizer_addon/config.yaml").write_text(
        'version: "2.3.62-haos73"\n', encoding="utf-8"
    )
    _git(work, "commit", "-am", "newer branch source")
    branch_commit = _git(work, "rev-parse", "HEAD")
    _git(work, "branch", "-M", "main")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "origin", "main", "refs/tags/v2.3.61-haos72")
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")
    return origin, tagged_commit, branch_commit


def _dockerfile_source_commands() -> str:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    start = dockerfile.find('RUN if [ -n "${SOURCE_REF:-}" ]')
    assert start >= 0, "Dockerfile source selection RUN block was not found"
    end = dockerfile.find("    && python3 -m pip install --upgrade pip", start)
    assert end >= 0, "Dockerfile source metadata boundary was not found"
    block = dockerfile[start + len("RUN ") : end].rstrip()
    assert block.endswith("\\")
    block = block[:-1].rstrip() + "\n"
    # Keep the actual selection/fetch/checkout/metadata/copy commands while
    # stopping before package installation.
    public_origin = "https://github.com/Belot77/sigenergy-optimizer"
    assert block.count(public_origin) == 1
    block = block.replace(public_origin, '"$FIXTURE_ORIGIN"')
    # Pin every Docker absolute path to a fixture-owned absolute directory.
    # Match only an absolute /app argument, never the /app suffix in /tmp/src/app.
    block = re.sub(r"(?<!\S)/app(?=/|\s|$)", '"$FIXTURE_APP"', block)
    block = block.replace("/tmp/src", '"$FIXTURE_SOURCE"')
    block = block.replace("/tmp/buildstamp.txt", '"$FIXTURE_BUILDSTAMP"')
    assert re.search(r"(?<!\S)/(?:app|tmp)(?:/|\s|$)", block) is None
    assert "https://" not in block and "http://" not in block
    return block


def _run_source_selection(
    tmp_path: Path,
    origin: Path,
    *,
    source_ref: str = "",
    build_version: str = "",
    git_failure: str = "",
    mismatch_sha: bool = False,
) -> subprocess.CompletedProcess[str]:
    app = tmp_path / "app"
    app.mkdir(exist_ok=True)
    (tmp_path / "buildstamp.txt").write_text("test-build\n", encoding="utf-8")
    env = _isolated_git_env()
    assert origin.as_uri().startswith("file://")
    env.update(
        SOURCE_REF=source_ref,
        BUILD_VERSION=build_version,
        FIXTURE_ORIGIN=origin.as_uri(),
        FIXTURE_APP=app.as_posix(),
        FIXTURE_SOURCE=(tmp_path / "src").as_posix(),
        FIXTURE_BUILDSTAMP=(tmp_path / "buildstamp.txt").as_posix(),
        GIT_FAILURE=git_failure,
        MISMATCH_SHA="1" if mismatch_sha else "",
    )
    git_wrapper = '''
git() {
    if [ -n "${GIT_FAILURE:-}" ] && [ "$1" = "$GIT_FAILURE" ]; then
        echo "injected git $1 failure" >&2
        return 73
    fi
    if [ -n "${MISMATCH_SHA:-}" ] && [ "$1" = rev-parse ] && [ "${2:-}" = HEAD ]; then
        printf '%040d\\n' 0
        return 0
    fi
    command git "$@"
}
'''
    return subprocess.run(
        [
            str(BASH),
            "--noprofile",
            "--norc",
            "-o",
            "pipefail",
            "-c",
            git_wrapper + _dockerfile_source_commands(),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_release_build_uses_tagged_source_not_newer_default_branch(
    tmp_path: Path, source_fixture: tuple[Path, str, str]
) -> None:
    origin, tagged_commit, branch_commit = source_fixture
    result = _run_source_selection(
        tmp_path, origin, build_version="2.3.61-haos72"
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "app" / ".source_commit").read_text().strip() == tagged_commit
    assert (tmp_path / "src" / "VERSION_SOURCE").read_text() == "release-tag\n"
    assert (tmp_path / "app" / "app" / "VERSION_SOURCE").read_text() == "release-tag\n"
    assert (
        tmp_path / "app" / "app" / "release_version.txt"
    ).read_text().strip() == "2.3.61-haos72"
    assert (
        tmp_path / "src" / "sigenergy_optimizer_addon" / "config.yaml"
    ).read_text() == 'version: "2.3.61-haos72"\n'
    assert (tmp_path / "app" / "requirements.txt").is_file()
    assert tagged_commit != branch_commit


def test_explicit_ci_sha_takes_priority_without_build_version(
    tmp_path: Path, source_fixture: tuple[Path, str, str]
) -> None:
    origin, tagged_commit, _ = source_fixture
    result = _run_source_selection(tmp_path, origin, source_ref=tagged_commit.upper())

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "app" / ".source_commit").read_text().strip() == tagged_commit
    assert (tmp_path / "src" / "VERSION_SOURCE").read_text() == "release-tag\n"


@pytest.mark.parametrize(
    ("source_ref", "build_version"),
    [
        ("", ""),
        ("", "main"),
        ("main", "2.3.61-haos72"),
        ("1234567", ""),
        ("g" * 40, ""),
        ("a" * 39, ""),
    ],
)
def test_rejects_missing_or_invalid_inputs(
    tmp_path: Path,
    source_fixture: tuple[Path, str, str],
    source_ref: str,
    build_version: str,
) -> None:
    origin, _, _ = source_fixture
    result = _run_source_selection(
        tmp_path, origin, source_ref=source_ref, build_version=build_version
    )

    assert result.returncode != 0
    assert not (tmp_path / "app" / ".source_commit").exists()


def test_missing_release_tag_fails_closed(
    tmp_path: Path, source_fixture: tuple[Path, str, str]
) -> None:
    origin, _, _ = source_fixture
    result = _run_source_selection(tmp_path, origin, build_version="2.3.62-haos73")

    assert result.returncode != 0
    assert not (tmp_path / "app" / ".source_commit").exists()


@pytest.mark.parametrize("failed_command", ["clone", "fetch", "checkout"])
def test_git_operation_failures_stop_build(
    tmp_path: Path,
    source_fixture: tuple[Path, str, str],
    failed_command: str,
) -> None:
    origin, tagged_commit, _ = source_fixture
    result = _run_source_selection(
        tmp_path,
        origin,
        source_ref=tagged_commit,
        git_failure=failed_command,
    )

    assert result.returncode != 0
    assert f"injected git {failed_command} failure" in result.stderr
    assert not (tmp_path / "app" / ".source_commit").exists()


def test_mismatched_resolved_sha_stops_build(
    tmp_path: Path, source_fixture: tuple[Path, str, str]
) -> None:
    origin, tagged_commit, _ = source_fixture
    result = _run_source_selection(
        tmp_path, origin, source_ref=tagged_commit, mismatch_sha=True
    )

    assert result.returncode != 0
    assert not (tmp_path / "app" / ".source_commit").exists()


def test_metadata_records_full_checked_out_commit(
    tmp_path: Path, source_fixture: tuple[Path, str, str]
) -> None:
    origin, _, branch_commit = source_fixture
    result = _run_source_selection(
        tmp_path, origin, source_ref=branch_commit, build_version="invalid-is-ignored"
    )

    assert result.returncode == 0, result.stderr
    metadata = (tmp_path / "app" / ".source_commit").read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", metadata)
    assert metadata == branch_commit
