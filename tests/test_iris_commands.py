"""Voice commands: parsing (pure) and execution in the UI (fake agent)."""

import pytest

from toad.app import ToadApp
from toad.iris_commands import Command, normalize, parse_command
from toad.widgets.conversation import Conversation

from conftest import agent_data, wait_until, write_settings

SIZE = (130, 40)


def test_normalize():
    assert normalize("Íris, Modo de Execução!") == "iris modo de execucao"


@pytest.mark.parametrize(
    "spoken, expected",
    [
        ("Íris, modo planejamento.", Command("modo_planejamento")),
        ("Iris modo de planejamento", Command("modo_planejamento")),
        ("Íris, vamos planejar", Command("modo_planejamento")),
        ("Íris, modo de execução", Command("modo_execucao")),
        ("Íris, sai do planejamento", Command("modo_execucao")),
        ("Íris, modo normal", Command("modo_execucao")),
        ("Íris, abre o Gemini", Command("abrir", "geminicli.com")),
        ("Íris, abrir o Claude.", Command("abrir", "claude.com")),
        ("Íris, abre o cloud", Command("abrir", "claude.com")),  # Whisper mishearing
        ("Íris, usar o Codex", Command("abrir", "openai.com")),
        ("Íris, nova sessão", Command("nova_sessao")),
        ("Íris, abre uma sessão", Command("nova_sessao")),
        ("Íris, próxima sessão", Command("proxima_sessao")),
        ("Íris, sessão anterior", Command("sessao_anterior")),
        ("Íris, fechar sessão", Command("fechar")),
        ("Íris, fecha essa sessão", Command("fechar")),
        ("Íris, pode mandar", Command("enviar")),
        ("Íris, envia", Command("enviar")),
        ("Íris, apaga o texto", Command("limpar")),
        ("Íris, para.", Command("cancelar")),
        ("Íris, cancela tudo", Command("cancelar")),
        ("Íris, para de falar", Command("silencio")),
        ("Íris, silêncio", Command("silencio")),
        ("Íris, repete", Command("repetir")),
        ("Íris, que horas são?", Command("horas")),
        ("Íris, status", Command("status")),
        ("Íris, o que você está fazendo?", Command("status")),
        ("Íris, ajuda", Command("ajuda")),
        ("Íris, sair", Command("sair")),
        ("Ei Íris, modo planejamento", Command("modo_planejamento")),
        ("Íris.", Command("vazio")),
    ],
)
def test_parse_command(spoken, expected):
    assert parse_command(spoken) == expected


def test_unrecognized_command_keeps_text():
    assert parse_command("Íris, refatora o main.py") == Command(
        "desconhecido", "refatora o main py"
    )


@pytest.mark.parametrize(
    "spoken",
    [
        "Refatora o main.py e roda os testes",
        "Preciso de ajuda com o modo de planejamento",  # no wake word: plain dictation
        "",
    ],
)
def test_plain_dictation_is_not_a_command(spoken):
    assert parse_command(spoken) is None


# ------------------------------------------------------------------------ UI


async def start(pilot) -> Conversation:
    app = pilot.app
    assert await wait_until(pilot, lambda: app.screen.query_one_optional(Conversation) is not None)
    conversation = app.screen.query_one(Conversation)
    assert await wait_until(pilot, lambda: conversation.agent_ready and conversation.modes)
    return conversation


async def test_voice_commands_in_conversation(spoken):
    write_settings({"voz": {"modo": "ditado_avisos"}})
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start(pilot)
        voice = app.iris_voice

        voice.handle_transcript("Íris, modo planejamento.", conversation)
        assert await wait_until(pilot, lambda: conversation.current_mode.id == "plan")
        assert await wait_until(pilot, lambda: "Modo de planejamento." in spoken)

        voice.handle_transcript("Íris, modo de execução", conversation)
        assert await wait_until(pilot, lambda: conversation.current_mode.id == "default")

        voice.handle_transcript("Íris, status", conversation)
        assert await wait_until(
            pilot, lambda: "Claude Code está aguardando você, no modo Default." in spoken
        )

        # Plain dictation goes to the prompt; a command can then clear it.
        voice.handle_transcript("explica o main.py", conversation)
        assert conversation.prompt.prompt_text_area.text == "explica o main.py"
        voice.handle_transcript("Íris, apaga o texto", conversation)
        assert await wait_until(pilot, lambda: conversation.prompt.prompt_text_area.text == "")

        # Unrecognized command: the words aren't lost.
        voice.handle_transcript("Íris, refatora o main", conversation)
        assert conversation.prompt.prompt_text_area.text == "refatora o main"


async def test_voice_command_sends_prompt(spoken):
    write_settings({"voz": {"modo": "ditado_avisos"}})
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start(pilot)
        voice = app.iris_voice
        voice.handle_transcript("olá", conversation)
        voice.handle_transcript("Íris, pode mandar", conversation)
        assert await wait_until(pilot, lambda: conversation._turn_count >= 1)


async def test_voice_commands_can_be_disabled(spoken):
    write_settings({"voz": {"modo": "ditado_avisos", "comandos": False}})
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start(pilot)
        app.iris_voice.handle_transcript("Íris, modo planejamento", conversation)
        await pilot.pause(0.3)
        assert conversation.current_mode.id == "default"
        assert conversation.prompt.prompt_text_area.text == "Íris, modo planejamento"
