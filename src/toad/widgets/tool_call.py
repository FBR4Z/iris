import re  # re2 doesn't have MULTILINE
from typing import Iterable
from rich.text import Text

from textual import on
from textual import events
from textual.app import ComposeResult
from textual import getters

from textual.content import Content
from textual.reactive import reactive, var
from textual.css.query import NoMatches
from textual import containers
from textual.widgets import Static, Markdown

from toad.app import ToadApp
from toad.acp import protocol
from toad.menus import MenuItem
from toad.pill import pill


class TextContent(Static):
    DEFAULT_CSS = """
    TextContent 
    {
        height: auto;
    }
    """


class MarkdownContent(Markdown):
    pass


class TerminalOutput(Static):
    DEFAULT_CSS = """
    TerminalOutput {
        height: auto;
        padding: 0 1;
        background: $boost;
    }
    """


def elapsed_seconds(tool_call: protocol.ToolCall) -> str:
    """How long a running tool has taken ("42s", "3min 05s"), from Claude Code's progress."""
    meta = tool_call.get("_meta") or {}
    response = (meta.get("claudeCode") or {}).get("toolResponse") or {}
    seconds = response.get("elapsedTimeSeconds") if isinstance(response, dict) else None
    if not isinstance(seconds, (int, float)) or seconds < 1:
        return ""
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"


class ToolCallItem(containers.HorizontalGroup):
    def compose(self) -> ComposeResult:
        yield Static(classes="icon")


class ToolCallDiff(Static):
    DEFAULT_CSS = """
    ToolCallDiff {
        height: auto;
    }
    """


class ToolCallHeader(Static):
    ALLOW_SELECT = False
    DEFAULT_CSS = """
    ToolCallHeader {
        width: auto;
        max-width: 1fr;        
        &:hover {
            background: $panel;
        }
    }
    """


class ToolCall(containers.VerticalGroup):
    DEFAULT_CLASSES = "block"

    app = getters.app(ToadApp)
    has_content: var[bool] = var(False, toggle_class="-has-content")
    expanded: var[bool] = var(False, toggle_class="-expanded")
    tool_call: var[protocol.ToolCall | None] = var(None)

    def __init__(
        self,
        tool_call: protocol.ToolCall,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self.set_reactive(ToolCall.tool_call, tool_call)
        super().__init__(id=id, classes=classes)

    async def update_tool_call(self, tool_call: protocol.ToolCall) -> None:
        """Update the tool call and recompose the widget.

        Args:
            tool_call: New Tool call data.
        """
        self.tool_call = tool_call
        await self.recompose()

    def get_block_menu(self) -> Iterable[MenuItem]:
        if self.expanded:
            yield MenuItem("Collapse", "block.collapse", "x")
        else:
            yield MenuItem("Expand", "block.expand", "x")

    def action_collapse(self) -> None:
        self.expanded = False

    def action_expand(self) -> None:
        self.expanded = True

    def get_block_content(self, destination: str) -> str | None:
        return None

    def can_expand(self) -> bool:
        return self.has_content

    def expand_block(self) -> None:
        self.expanded = True

    def collapse_block(self) -> None:
        self.expanded = False

    def is_block_expanded(self) -> bool:
        return self.expanded

    def compose(self) -> ComposeResult:
        tool_call = self.tool_call
        assert tool_call is not None
        content: list[protocol.ToolCallContent] = tool_call.get("content", None) or []

        self.set_class(tool_call.get("status") == "failed", "-failed")

        self.has_content = False
        content_update = list(self._compose_content(content))

        yield ToolCallHeader(self.tool_call_header_content, markup=False).with_tooltip(
            "Expand to see full title"
        )
        with containers.VerticalGroup(id="tool-content"):
            yield from content_update
        self.check_expand()

    def on_mount(self) -> None:
        self.check_expand()

    def check_expand(self) -> None:
        """Check if the tool call should auto-expand."""
        if not self.has_content:
            return
        tool_call = self.tool_call
        assert tool_call is not None
        if tool_call.get("kind", "") == "read":
            # Don't auto expand reads, as it can generate a lot of noise
            return
        tool_call_expand = self.app.settings.get("tools.expand", str, expand=False)
        status = tool_call.get("status")
        if tool_call_expand == "always":
            self.expanded = True
        elif tool_call_expand != "never" and status is not None:
            if tool_call_expand == "success":
                self.expanded = status == "completed"
            elif tool_call_expand == "fail":
                self.expanded = status == "failed"
            elif tool_call_expand == "both":
                self.expanded = status in ("completed", "failed")

    @property
    def tool_call_header_content(self) -> Content:
        tool_call = self.tool_call
        assert tool_call is not None
        _kind = tool_call.get("kind", "tool")
        title = tool_call.get("title", "title")
        status = tool_call.get("status", "pending")

        expand_icon: Content = Content()
        if self.has_content:
            expand_icon = Content.from_markup(
                "[$text-secondary]▼ " if self.expanded else "[$text-secondary]▶ "
            )
        else:
            expand_icon = Content.from_markup(
                "[$text-secondary 30%]▼ "
                if self.expanded
                else "[$text-secondary 30%]▶ "
            )

        header = Content.assemble(expand_icon, "🔧 ", title)

        if status == "pending":
            header += Content.assemble(" ⌛")
        elif status == "in_progress":
            pass
        elif status == "failed":
            header += Content.assemble(" ", pill("failed", "$error-muted", "$error"))
        elif status == "completed":
            header += Content.from_markup(" [$success]✔")

        if status in ("pending", "in_progress") and (elapsed := elapsed_seconds(tool_call)):
            # Long commands (a flash waiting for BOOT) show they are still running.
            header += Content.from_markup(f" [$text-secondary]⏱ {elapsed}")
        exit_code = (tool_call.get("_iris_terminal") or {}).get("exit_code")
        if isinstance(exit_code, int) and exit_code:
            header += Content.from_markup(f" [$error](código {exit_code})")
        return header

    def watch_expanded(self) -> None:
        try:
            self.query_one(ToolCallHeader).update(self.tool_call_header_content)
        except NoMatches:
            pass
        from toad.widgets.conversation import Conversation

        try:
            conversation = self.query_ancestor(Conversation)
        except NoMatches:
            pass
        else:
            self.call_after_refresh(conversation.cursor.update_follow)

    @on(events.Click, "ToolCallHeader")
    def on_click_tool_call_header(self, event: events.Click) -> None:
        event.stop()
        if self.has_content:
            self.expanded = not self.expanded
        else:
            self.app.bell()

    def _compose_content(
        self, tool_call_content: list[protocol.ToolCallContent]
    ) -> ComposeResult:
        def compose_content_block(
            content_block: protocol.ContentBlock,
        ) -> ComposeResult:
            match content_block:
                # TODO: This may need updating
                # Docs claim this should be "plain" text
                # However, I have seen simple text, text with ansi escape sequences, and Markdown returned
                # I think this is a flaw in the spec.
                # For now I will attempt a heuristic to guess what the content actually contains
                # https://agentclientprotocol.com/protocol/schema#param-text
                case {"type": "text", "text": text}:
                    assert isinstance(text, str)
                    if "\x1b" in text:
                        parsed_ansi_text = Text.from_ansi(text)
                        yield TextContent(Content.from_rich_text(parsed_ansi_text))
                    elif "```" in text or re.search(
                        r"^#{1,6}\s.*$", text, re.MULTILINE
                    ):
                        yield MarkdownContent(text)
                    else:
                        yield TextContent(text, markup=False)

        for content in tool_call_content:
            match content:
                case {"type": "content", "content": sub_content}:
                    yield from compose_content_block(sub_content)
                    self.has_content = True
                case {
                    "type": "diff",
                    "path": path,
                    "oldText": old_text,
                    "newText": new_text,
                }:
                    from toad.widgets.diff_view import make_diff

                    yield (diff_view := make_diff(path, path, old_text, new_text))

                    if isinstance(self.app, ToadApp):
                        diff_view_setting = self.app.settings.get("diff.view", str)
                        diff_view.split = diff_view_setting == "split"
                        diff_view.auto_split = diff_view_setting == "auto"

                    self.has_content = True

                case {"type": "terminal", "terminalId": terminal_id}:
                    # A command the agent ran itself; its output comes as terminal metadata.
                    terminal = (self.tool_call or {}).get("_iris_terminal") or {}
                    if output := terminal.get("output", "").replace("\r\n", "\n").rstrip():
                        yield TerminalOutput(Content.from_rich_text(Text.from_ansi(output)))
                        self.has_content = True


if __name__ == "__main__":
    from textual.app import App, ComposeResult

    TOOL_CALL_READ: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "write_file-1759480341499",
        "status": "completed",
        "title": "Foo",
        "content": [
            {
                "type": "diff",
                "path": "fib.py",
                "oldText": "",
                "newText": 'def fibonacci(n):\n    """Generates the Fibonacci sequence up to n terms."""\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n\nif __name__ == "__main__":\n    for number in fibonacci(10):\n        print(number)\n',
            }
        ],
    }

    TOOL_CALL_CONTENT: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "run_shell_command-1759480356886",
        "status": "completed",
        "title": "Bar",
        "content": [
            {
                "type": "content",
                "content": {
                    "type": "text",
                    "text": "0\n1\n1\n2\n3\n5\n8\n13\n21\n34",
                },
            }
        ],
    }

    TOOL_CALL_EMPTY: protocol.ToolCall = {
        "sessionUpdate": "tool_call",
        "toolCallId": "run_shell_command-1759480356886",
        "status": "completed",
        "title": "Bar",
        "content": [],
    }

    class ToolApp(App):
        def on_mount(self) -> None:
            self.theme = "dracula"

        def compose(self) -> ComposeResult:
            yield ToolCall(TOOL_CALL_READ)
            yield ToolCall(TOOL_CALL_CONTENT)
            yield ToolCall(TOOL_CALL_EMPTY)

    ToolApp().run()
