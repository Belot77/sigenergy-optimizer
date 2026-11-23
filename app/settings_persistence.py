"""Write settings without exposing a partly written file."""

import logging
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile


logger = logging.getLogger(__name__)


def write_settings_atomically(path: Path, content: str) -> None:
    # Home Assistant OS links the app's .env to persistent storage.
    target = path.resolve()
    mode = None
    if os.name == "posix":
        try:
            mode = stat.S_IMODE(target.stat().st_mode)
        except FileNotFoundError:
            pass

    staging_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f"{target.name}.", suffix=".tmp", delete=False,
        ) as staging:
            staging_path = Path(staging.name)
            staging.write(content)
            staging.flush()
            if mode is not None:
                os.fchmod(staging.fileno(), mode)
            os.fsync(staging.fileno())
        os.replace(staging_path, target)
    except BaseException:
        if staging_path is not None:
            try:
                staging_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove the temporary settings file", exc_info=True)
        raise

    if os.name == "posix":
        try:
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            # Replacement committed the new settings. Allow runtime activation.
            logger.warning("Settings were saved but syncing their directory failed", exc_info=True)
