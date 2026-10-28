"""Guarded offline runner: python -B tests/run_solar_allocation_planning.py [tests...]."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

# Install both barriers before importing any application or test modules.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["STATE_DB_PATH"] = ":memory:"
from pydantic_settings import BaseSettings

_original_settings_init = BaseSettings.__init__
def _isolated_settings(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return _original_settings_init(self, *args, **kwargs)
BaseSettings.__init__ = _isolated_settings
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.state_store import StateStore

_original_store_init = StateStore.__init__
_temporary_root = Path(tempfile.gettempdir()).resolve()
_counts = {"memory": 0, "temporary": 0, "rejected": 0}
def _guarded_store(self, db_path):
    if str(db_path) == ":memory:":
        _counts["memory"] += 1
    else:
        resolved = Path(db_path).expanduser().resolve()
        if resolved == _temporary_root or not resolved.is_relative_to(_temporary_root):
            _counts["rejected"] += 1
            raise RuntimeError("StateStore path outside isolated temporary root")
        _counts["temporary"] += 1
    return _original_store_init(self, db_path)
StateStore.__init__ = _guarded_store

if __name__ == "__main__":
    import pytest
    targets = sys.argv[1:] or ["tests/test_solar_allocation_lifecycle_planning.py"]
    result = pytest.main(["-q", "-p", "no:cacheprovider", "--disable-warnings", *targets])
    print("STATESTORE_GUARD", _counts)
    raise SystemExit(result)