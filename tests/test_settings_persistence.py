"""Exercise the settings writers with synthetic files in temporary directories."""

import json
import os
import stat
from pathlib import Path

import pytest

from app import settings_persistence


ORIGINAL = "# Original settings\nDEMO_VALUE=15\nDEMO_OTHER=7\n"
UPDATED = "# Updated settings\nDEMO_VALUE=18\nDEMO_OTHER=7\n"
STARTUP_RUNNER = Path(__file__).resolve().parents[1] / "sigenergy_optimizer_addon" / "run.sh"


def test_atomic_settings_write_replaces_complete_file(tmp_path, monkeypatch):
    target = tmp_path / ".env"
    target.write_text(ORIGINAL, encoding="utf-8")
    replace = os.replace

    def check_replacement(staged, destination):
        assert Path(staged).parent == target.parent
        assert Path(staged).read_text(encoding="utf-8") == UPDATED
        assert Path(destination).read_text(encoding="utf-8") == ORIGINAL
        replace(staged, destination)

    monkeypatch.setattr(settings_persistence.os, "replace", check_replacement)
    settings_persistence.write_settings_atomically(target, UPDATED)

    assert target.read_text(encoding="utf-8") == UPDATED
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_settings_write_keeps_original_when_staging_sync_fails(tmp_path, monkeypatch):
    target = tmp_path / ".env"
    target.write_text(ORIGINAL, encoding="utf-8")

    def fail_sync(_descriptor):
        raise OSError("synthetic staging sync failure")

    monkeypatch.setattr(settings_persistence.os, "fsync", fail_sync)
    with pytest.raises(OSError, match="synthetic staging sync failure"):
        settings_persistence.write_settings_atomically(target, UPDATED)

    assert target.read_text(encoding="utf-8") == ORIGINAL
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_settings_write_stages_beside_resolved_target(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alias = app_dir / ".env"
    target = data_dir / ".env"
    target.write_text(ORIGINAL, encoding="utf-8")
    resolve = Path.resolve
    replace = os.replace

    def resolve_alias(path, *args, **kwargs):
        return resolve(target if path == alias else path, *args, **kwargs)

    def check_destination(staged, destination):
        assert Path(staged).parent == target.parent
        assert Path(destination) == target
        replace(staged, destination)

    # Exercise the destination choice even on platforms that restrict symlink creation.
    monkeypatch.setattr(Path, "resolve", resolve_alias)
    monkeypatch.setattr(settings_persistence.os, "replace", check_destination)
    settings_persistence.write_settings_atomically(alias, UPDATED)

    assert target.read_text(encoding="utf-8") == UPDATED
    assert list(data_dir.iterdir()) == [target]
    assert not list(app_dir.iterdir())


def test_atomic_settings_write_preserves_relative_symlink(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    target = data_dir / ".env"
    target.write_text(ORIGINAL, encoding="utf-8")
    alias = tmp_path / ".env"
    try:
        alias.symlink_to(Path("data") / ".env")
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows requires symlink creation privileges")
        raise

    settings_persistence.write_settings_atomically(alias, UPDATED)

    assert alias.is_symlink()
    assert alias.readlink() == Path("data") / ".env"
    assert target.read_text(encoding="utf-8") == UPDATED
    assert list(data_dir.iterdir()) == [target]


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_atomic_settings_write_creates_private_file_and_retains_existing_mode(tmp_path):
    target = tmp_path / ".env"

    settings_persistence.write_settings_atomically(target, ORIGINAL)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600

    target.chmod(0o640)
    settings_persistence.write_settings_atomically(target, UPDATED)
    assert target.read_text(encoding="utf-8") == UPDATED
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


@pytest.mark.skipif(os.name != "posix", reason="POSIX directory sync")
def test_directory_sync_failure_after_replacement_keeps_committed_result(
    tmp_path, monkeypatch, caplog,
):
    target = tmp_path / ".env"
    target.write_text(ORIGINAL, encoding="utf-8")
    fsync = os.fsync

    def fail_directory_sync(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("synthetic directory sync failure")
        fsync(descriptor)

    monkeypatch.setattr(settings_persistence.os, "fsync", fail_directory_sync)
    settings_persistence.write_settings_atomically(target, UPDATED)

    assert target.read_text(encoding="utf-8") == UPDATED
    assert "synthetic directory sync failure" in caplog.text
    assert list(tmp_path.iterdir()) == [target]


def _run_startup_settings(env_file, template_file, options_file):
    """Execute the actual startup Python body, redirecting its fixed HAOS paths."""
    source = STARTUP_RUNNER.read_text(encoding="utf-8")
    startup_python = source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    for live_name, scratch_file in (
        ("/data/.env", env_file),
        ("/app/.env.example", template_file),
        ("/data/options.json", options_file),
    ):
        assert f'"{live_name}"' in startup_python
        startup_python = startup_python.replace(f'"{live_name}"', repr(str(scratch_file)))
    exec(compile(startup_python, str(STARTUP_RUNNER), "exec"), {})


@pytest.mark.parametrize("existing", [False, True], ids=["first-start", "restart"])
def test_startup_preserves_prior_file_until_final_overlaid_settings_commit(
    tmp_path, monkeypatch, existing,
):
    target = tmp_path / ".env"
    template = tmp_path / ".env.example"
    options = tmp_path / "options.json"
    template.write_text("# Seed\nDEMO_VALUE=10\nDEMO_OTHER=4\n", encoding="utf-8")
    options.write_text(json.dumps({"extra_env": "DEMO_VALUE=33\nDEMO_NEW=1"}), encoding="utf-8")
    if existing:
        target.write_text(ORIGINAL, encoding="utf-8")
    expected = (
        "# Original settings\nDEMO_VALUE=33\nDEMO_OTHER=7\nDEMO_NEW=1\n" if existing
        else "# Seed\nDEMO_VALUE=33\nDEMO_OTHER=4\nDEMO_NEW=1\n"
    )

    def fail_replacement(staged, destination):
        assert Path(destination) == target
        assert Path(staged).read_text(encoding="utf-8") == expected
        raise OSError("synthetic startup replace failure")

    with monkeypatch.context() as failure:
        failure.setattr(settings_persistence.os, "replace", fail_replacement)
        with pytest.raises(OSError, match="synthetic startup replace failure"):
            _run_startup_settings(target, template, options)

    if existing:
        assert target.read_text(encoding="utf-8") == ORIGINAL
        assert set(tmp_path.iterdir()) == {target, template, options}
    else:
        assert not target.exists()
        assert set(tmp_path.iterdir()) == {template, options}

    _run_startup_settings(target, template, options)
    assert target.read_text(encoding="utf-8") == expected
    assert set(tmp_path.iterdir()) == {target, template, options}
