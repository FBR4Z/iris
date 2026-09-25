"""Portuguese labels for footer key bindings.

Bindings are declared in English all over the upstream code. Rather than editing
each declaration (and fighting merge conflicts with Toad), we translate the
descriptions when the footer builds its keys.
"""

from __future__ import annotations

PT_BR: dict[str, str] = {
    # Main screen
    "Sidebar": "Barra lateral",
    "Home": "Início",
    "Previous session": "Sessão anterior",
    "Next session": "Próxima sessão",
    "Dismiss sidebar": "Fechar barra lateral",
    # Conversation
    "Prompt": "Prompt",
    "Block cursor up": "Bloco acima",
    "Block cursor down": "Bloco abaixo",
    "Select": "Selecionar",
    "Expand": "Expandir",
    "Collapse": "Recolher",
    "Cancel": "Cancelar",
    "Focus": "Focar",
    "Modes": "Modos",
    "Interrupt": "Interromper",
    # Prompt
    "Send": "Enviar",
    "Line": "Nova linha",
    "Complete": "Completar",
    "Dismiss": "Fechar",
    "Dismiss mode switcher": "Fechar seletor de modos",
    # Launcher
    "Details": "Detalhes",
    "Quick launch": "Acesso rápido",
    "Resume": "Retomar",
    "Directory": "Pasta",
    "Launch": "Abrir",
    "Open agent details": "Ver detalhes do agente",
    "Launch highlighted agent": "Abrir o agente selecionado",
    "Remove": "Remover",
    "Settings": "Configurações",
    "Sessions": "Sessões",
    "Quit": "Sair",
    "Back": "Voltar",
    "Help": "Ajuda",
    "palette": "comandos",
}


def translate(text: str | None) -> str | None:
    if not text:
        return text
    return PT_BR.get(text, text)


def install() -> None:
    """Patch Textual's footer so key descriptions and group titles are translated."""
    from textual.widgets import _footer

    if getattr(_footer.FooterKey, "_iris_translated", False):
        return

    original_key_init = _footer.FooterKey.__init__

    def key_init(self, key, key_display, description, action, *args, **kwargs):
        if "tooltip" in kwargs:
            kwargs["tooltip"] = translate(kwargs["tooltip"])
        original_key_init(
            self, key, key_display, translate(description), action, *args, **kwargs
        )

    original_label_init = _footer.FooterLabel.__init__

    def label_init(self, content="", *args, **kwargs):
        if isinstance(content, str):
            content = translate(content)
        original_label_init(self, content, *args, **kwargs)

    _footer.FooterKey.__init__ = key_init
    _footer.FooterLabel.__init__ = label_init
    _footer.FooterKey._iris_translated = True
