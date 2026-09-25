"""Headless UI tests for Íris, driven by the fake ACP agent (no model quota used)."""

from __future__ import annotations

from textual.widgets._footer import FooterKey

from toad.app import ToadApp
from toad.widgets.conversation import Conversation
from toad.widgets.iris_orb import DEFAULT_EXEC_COLOR, DEFAULT_PLAN_COLOR, IrisOrb
from textual.color import Color

from conftest import agent_data, wait_until, write_settings

SIZE = (130, 40)


def close_to(color: Color, hex_color: str, tolerance: int = 8) -> bool:
    target = Color.parse(hex_color)
    return all(abs(a - b) <= tolerance for a, b in zip(color.rgb, target.rgb))


def footer_labels(app: ToadApp) -> set[str]:
    return {key.description for key in app.screen.query(FooterKey) if key.description}


async def start_conversation(pilot) -> Conversation:
    app = pilot.app
    assert await wait_until(
        pilot, lambda: app.screen.query_one_optional(Conversation) is not None
    )
    conversation = app.screen.query_one(Conversation)
    assert await wait_until(pilot, lambda: conversation.agent_ready and conversation.modes)
    return conversation


# ------------------------------------------------------------------- launcher


async def test_launcher_branding_and_defaults():
    app = ToadApp(mode="store", agent_data=None, project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        assert app.theme == "iris"
        assert app.terminal_title == "Íris"
        assert app.settings.get("statistics.allow_collect", bool) is False

        from toad.screens.store import AgentItem, LauncherItem

        names = sorted(item._agent["name"] for item in app.screen.query(AgentItem))
        assert names == ["Claude Code", "Codex CLI", "Gemini CLI"]
        assert len(list(app.screen.query(LauncherItem))) == 3

        info = app.screen.query_one("#info").render().plain
        assert "Íris" in info and "Toad" in info  # own name + credit to upstream
        assert app.screen.query_one(IrisOrb)

        assert {"Detalhes", "Abrir", "Configurações", "Sessões"} <= footer_labels(app)


# --------------------------------------------------------------- conversation


async def test_conversation_layout_in_portuguese():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        await start_conversation(pilot)
        titles = [c.title for c in app.screen.query("SideBarCollapsible")]
        assert titles == ["Íris", "Plano", "Projeto"]
        assert app.settings.get("ui.prompt_message", str) == "Como posso ajudar hoje?"
        assert {"Enviar", "Modos", "Barra lateral", "Início"} <= footer_labels(app)


async def test_orb_and_borders_follow_mode():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        orb = app.screen.query_one(IrisOrb)
        prompt = app.screen.query_one("PromptContainer")

        assert await wait_until(pilot, lambda: close_to(orb._color, DEFAULT_EXEC_COLOR))
        assert close_to(prompt.styles.border_top[1], DEFAULT_EXEC_COLOR)
        # (after the power-up animation)
        assert await wait_until(pilot, lambda: "EXECUÇÃO" in orb.render().plain)

        conversation.current_mode = conversation.modes["plan"]
        assert await wait_until(pilot, lambda: close_to(orb._color, DEFAULT_PLAN_COLOR))
        assert await wait_until(
            pilot, lambda: close_to(prompt.styles.border_top[1], DEFAULT_PLAN_COLOR)
        )
        assert "PLANEJAMENTO" in orb.render().plain
        # Inner ring takes Claude's color.
        assert await wait_until(pilot, lambda: close_to(orb._agent_color, "#d97757"))


async def test_orb_reacts_to_permission_and_failure():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        orb = app.screen.query_one(IrisOrb)

        app.session_tracker.update_session(app.screen.id, state="asking")
        assert await wait_until(pilot, lambda: "AGUARDANDO VOCÊ" in orb.render().plain)

        app.session_tracker.update_session(app.screen.id, state="idle")
        conversation._agent_fail = True
        assert await wait_until(pilot, lambda: "ERRO" in orb.render().plain)


async def test_prompt_round_trip_with_fake_agent():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        orb = app.screen.query_one(IrisOrb)
        conversation.prompt.append("olá")
        conversation.prompt.prompt_text_area.action_submit()
        assert await wait_until(pilot, lambda: conversation.turn == "client" and conversation._turn_count >= 1)
        assert await wait_until(pilot, lambda: "concluído" in orb.render().plain, timeout=3)


async def test_slash_fechar_closes_session():
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        assert app.session_tracker.session_count == 1
        assert await conversation.slash_command("/fechar")
        assert await wait_until(pilot, lambda: app.session_tracker.session_count == 0)
        assert type(app.screen).__name__ == "StoreScreen"


# ----------------------------------------------------------------------- voice


async def test_voice_announcements(spoken):
    write_settings({"voz": {"modo": "avisos"}})
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        voice = app.iris_voice

        conversation.current_mode = conversation.modes["plan"]
        await pilot.pause(0.1)
        conversation.current_mode = conversation.modes["default"]
        await pilot.pause(0.1)
        voice.announce_tool({"kind": "execute", "rawInput": {"command": "pwsh -c ls"}})
        voice.announce_tool({"kind": "edit", "locations": [{"path": "main.py"}]})  # too soon
        voice.turn_over("Claude Code", "Feito.", 45)
        voice.turn_over("Claude Code", "Feito.", 2)  # too short to announce

        assert spoken == [
            "Claude Code conectado.",
            "Modo de planejamento.",
            "Modo de execução.",
            "Executando PowerShell.",
            "Pronto. Terminei em 45 segundos.",
        ]


async def test_voice_completa_reads_summary(spoken):
    write_settings({"voz": {"modo": "completa"}})
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        conversation.prompt.append("olá")
        conversation.prompt.prompt_text_area.action_submit()
        assert await wait_until(pilot, lambda: any("Resultado" in text for text in spoken))
        summary = next(text for text in spoken if "Resultado" in text)
        assert "print(" not in summary
        assert summary.endswith("Deixei o código na tela.")


async def test_voice_off_by_default_says_nothing(spoken):
    app = ToadApp(agent_data=agent_data(), project_dir=".")
    async with app.run_test(size=SIZE) as pilot:
        conversation = await start_conversation(pilot)
        conversation.current_mode = conversation.modes["plan"]
        await pilot.pause(0.2)
        assert spoken == []
