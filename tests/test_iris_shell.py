"""The integrated shell (ConPTY on Windows, pty elsewhere), driven headless."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from toad.app import ToadApp
from toad.shell import shell_kind, windows_shell_command
from toad.widgets.terminal import Terminal

from conftest import agent_data, wait_until
from test_iris_ui import SIZE, start_conversation


def terminal_lines(app: ToadApp) -> list[list[str]]:
    """Text of each shell terminal on screen (trailing blank lines dropped)."""
    result = []
    for terminal in app.screen.query(Terminal):
        lines = [line.content.plain.rstrip() for line in terminal.state.scrollback_buffer.lines]
        while lines and not lines[-1]:
            lines.pop()
        result.append(lines)
    return result


def shown(app: ToadApp, text: str) -> bool:
    return any(text in line for lines in terminal_lines(app) for line in lines)


@pytest.mark.parametrize(
    "command, kind",
    [
        ("powershell.exe -NoLogo", "powershell"),
        ('"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -NoLogo', "powershell"),
        ("cmd.exe", "cmd"),
        ("CMD", "cmd"),
        ('"C:\\Program Files\\Git\\bin\\bash.exe" --login', "posix"),
        ("", "powershell"),
    ],
)
def test_shell_kind(command, kind):
    assert shell_kind(command) == kind


def test_windows_shell_command_ignores_unix_defaults():
    assert windows_shell_command("/bin/sh") == "powershell.exe -NoLogo"
    assert windows_shell_command("  ") == "powershell.exe -NoLogo"
    assert windows_shell_command("cmd.exe") == "cmd.exe"


async def test_shell_runs_commands_and_follows_cd():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        start = Path(conversation.working_directory)

        await conversation.post_shell("echo iris-shell-ok")
        assert await wait_until(pilot, lambda: shown(app, "iris-shell-ok"), timeout=20)
        lines = terminal_lines(app)[-1]
        # Only the output: no echoed command or prompt.
        assert [line for line in lines if line] == ["iris-shell-ok"], lines
        if sys.platform == "win32":
            # ConPTY's absolute cursor moves must not leave blank lines above it.
            assert lines == ["iris-shell-ok"], lines

        await conversation.post_shell("cd tests")
        assert await wait_until(
            pilot,
            lambda: Path(conversation.working_directory) == start / "tests",
            timeout=20,
        )
        await conversation.post_shell("echo second-ok")
        assert await wait_until(pilot, lambda: shown(app, "second-ok"), timeout=20)
        assert not any("echo" in line for lines in terminal_lines(app) for line in lines)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shell (ConPTY)")
async def test_windows_shell_is_powershell_and_closes():
    import psutil

    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        await conversation.post_shell("$PSVersionTable.PSEdition")
        assert await wait_until(
            pilot, lambda: shown(app, "Desktop") or shown(app, "Core"), timeout=20
        )
        # Output taller than the screen scrolls without losing or mangling lines.
        await conversation.post_shell("1..120 | ForEach-Object { \"linha $_\" }")
        assert await wait_until(pilot, lambda: shown(app, "linha 120"), timeout=20)
        lines = [line for line in terminal_lines(app)[-1] if line]
        assert lines == [f"linha {n}" for n in range(1, 121)], lines[:5]

        # A long command shows as busy and stops with Ctrl+C.
        await conversation.post_shell("ping -n 30 127.0.0.1")
        assert await wait_until(pilot, lambda: shown(app, "127.0.0.1"), timeout=20)
        assert await conversation.shell.is_busy()
        await conversation.shell.interrupt()
        busy = True
        for _ in range(50):
            busy = await conversation.shell.is_busy()
            if not busy:
                break
            await pilot.pause(0.1)
        assert not busy

        pid = conversation.shell._pid
        assert pid is not None and psutil.pid_exists(pid)
        assert await conversation.slash_command("/fechar")
        assert await wait_until(pilot, lambda: not psutil.pid_exists(pid), timeout=10)
