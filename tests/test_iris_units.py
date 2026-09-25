"""Unit tests for Íris helpers that don't need the UI."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from toad import paths
from toad.iris_voice import (
    DEFAULT_PHRASES,
    _Blank,
    file_from_tool,
    greeting,
    parse_phrases,
    program_from_tool,
    spoken_duration,
    summarize_response,
    tidy,
)


@pytest.mark.parametrize(
    "tool_call, expected",
    [
        ({"title": "`git status`", "rawInput": {"command": "git status"}}, "git"),
        ({"title": "Shell", "rawInput": {"command": "powershell -Command Get-ChildItem"}}, "PowerShell"),
        ({"title": "Get-Process | Select -First 5 (PowerShell)"}, "PowerShell"),
        ({"title": "npm run build", "rawInput": {"command": ["npm", "run", "build"]}}, "npm"),
        ({"title": r"C:\Python313\python.exe -m pytest"}, "Python"),
        ({"title": "dotnet build"}, "dotnet"),
        ({"title": "ls -la"}, "um comando"),
        ({}, "um comando"),
    ],
)
def test_program_from_tool(tool_call, expected):
    assert program_from_tool({"kind": "execute", **tool_call}) == expected


def test_file_from_tool():
    assert file_from_tool({"locations": [{"path": "C:/proj/src/main.py"}]}) == "main.py"
    assert file_from_tool({"rawInput": {"file_path": "/a/b/app.tsx"}}) == "app.tsx"
    assert file_from_tool({}) == "um arquivo"


def test_default_phrases_cover_all_events():
    phrases = parse_phrases(DEFAULT_PHRASES)
    for event in (
        "saudacao", "conectado", "falha", "modo_planejamento", "modo_execucao",
        "executando", "editando", "permissao", "concluido", "erro", "tchau",
    ):
        assert phrases[event], event
    # Noisy events ship silenced.
    for event in ("trabalhando", "lendo", "pesquisando", "plano"):
        assert phrases[event] == "", event


def test_parse_phrases_user_override_can_silence():
    phrases = parse_phrases(DEFAULT_PHRASES)
    phrases.update(parse_phrases("executando =\nconectado = Pronto para trabalhar."))
    assert phrases["executando"] == ""
    assert phrases["conectado"] == "Pronto para trabalhar."


@pytest.mark.parametrize(
    "name, expected",
    [("", "Bom dia."), ("Ana", "Bom dia, Ana.")],
)
def test_greeting_phrase_without_name(name, expected):
    template = parse_phrases(DEFAULT_PHRASES)["saudacao"]
    assert tidy(template.format_map(_Blank(saudacao="Bom dia", nome=name))) == expected


def test_greeting_matches_time_of_day():
    assert greeting() in {"Bom dia", "Boa tarde", "Boa noite"}


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (5, "5 segundos"),
        (60, "1 minuto"),
        (95, "1 minuto e 35 segundos"),
        (180, "3 minutos"),
    ],
)
def test_spoken_duration(seconds, expected):
    assert spoken_duration(seconds) == expected


def test_summarize_response_strips_code_and_markdown():
    markdown = (
        "## Análise\n\n"
        "Encontrei **dois problemas** no `main.py`. "
        "A função `get_user_by_id` não trata o caso nulo.\n\n"
        "- Import duplicado\n\n"
        "```python\nprint('segredo')\n```\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "Quer que eu corrija?"
    )
    summary = summarize_response(markdown, 500)
    assert summary.startswith("Análise. Encontrei dois problemas no main.py.")
    assert "get user by id" in summary
    assert "segredo" not in summary
    assert "|" not in summary and "**" not in summary and "`" not in summary
    assert summary.endswith("Deixei o código na tela.")


def test_summarize_response_respects_limit():
    text = " ".join(f"Frase número {n}." for n in range(100))
    assert len(summarize_response(text, 120)) <= 121


def test_path_to_name_windows_paths_stay_relative():
    """Regression: on Windows, per-project data used to be written inside the project."""
    name = paths.path_to_name(Path("."))
    assert ":" not in name and "\\" not in name and "/" not in name
    data_dir = paths.get_project_data(Path("."))
    assert data_dir.parent == paths.get_data()


@dataclass
class _Mode:
    id: str
    name: str


def test_is_planning_mode():
    from toad.iris_voice import is_planning_mode

    class _Settings:
        def get(self, key, expect_type=object):
            return "plan, read-only"

    class _App:
        settings = _Settings()

    assert is_planning_mode(_App(), _Mode("plan", "Plan"))
    assert is_planning_mode(_App(), _Mode("read-only", "Read Only"))
    assert not is_planning_mode(_App(), _Mode("default", "Default"))
    assert not is_planning_mode(_App(), None)
