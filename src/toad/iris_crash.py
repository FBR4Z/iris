"""Crash logging for Íris, so an unexpected exit leaves something to look at."""

from __future__ import annotations

import faulthandler
import traceback
from datetime import datetime
from pathlib import Path

_fault_file = None


def crash_log_path() -> Path:
    from toad import paths

    return paths.get_state() / "crash.log"


def install_fault_handler() -> None:
    """Dump native crashes (segfaults, aborts) with Python stacks to the crash log."""
    global _fault_file
    try:
        _fault_file = crash_log_path().open("a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
    except OSError:
        pass


def log_exception(error: BaseException) -> Path | None:
    """Append a Python exception to the crash log. Returns the log path."""
    try:
        path = crash_log_path()
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            log_file.write(
                "".join(traceback.format_exception(type(error), error, error.__traceback__))
            )
        return path
    except OSError:
        return None
