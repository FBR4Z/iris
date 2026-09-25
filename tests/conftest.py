"""Shared fixtures for the Íris test suite.

Everything runs against a throwaway config/data/state directory and a fake ACP
agent, so tests never touch your real settings nor spend model quota.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Must happen before `toad` is imported: paths are resolved from these variables.
_sandbox = Path(tempfile.mkdtemp(prefix="iris-tests-"))
for _name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
    os.environ[_name] = str(_sandbox / _name.lower())

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FAKE_AGENT = ROOT / "tools" / "fake_agent.py"


def agent_data(name: str = "Claude Code", identity: str = "claude.com") -> dict:
    """Agent definition that launches the fake ACP agent."""
    return {
        "identity": identity,
        "name": name,
        "short_name": name.split()[0].lower(),
        "url": "",
        "protocol": "acp",
        "type": "coding",
        "author_name": "",
        "author_url": "",
        "publisher_name": "",
        "publisher_url": "",
        "description": "",
        "tags": [],
        "help": "",
        "run_command": {"*": f'"{sys.executable}" "{FAKE_AGENT}"'},
        "actions": {},
    }


class FakeVoice:
    """Stands in for the iris-voz process: records what would have been said."""

    def __init__(self, voice) -> None:
        self.spoken: list[str] = []
        voice.ready = True
        voice.say = lambda text, cache=False: self.spoken.append(text)

        async def no_sync() -> None:
            return None

        voice.sync = no_sync


@pytest.fixture
def sandbox() -> Path:
    return _sandbox


@pytest.fixture(autouse=True)
def fresh_settings():
    """Each test starts from default settings."""
    from toad import paths

    settings_file = paths.get_config() / "toad.json"
    settings_file.unlink(missing_ok=True)
    yield
    settings_file.unlink(missing_ok=True)


async def wait_until(pilot, predicate, timeout: float = 20.0) -> bool:
    """Pause the pilot until `predicate()` is true (or time runs out)."""
    steps = int(timeout / 0.1)
    for _ in range(steps):
        if predicate():
            return True
        await pilot.pause(0.1)
    return predicate()
