"""The Íris theme: deep navy with cyan (planning) and orange (execution) accents."""

from textual.theme import Theme

IRIS_THEME = Theme(
    name="iris",
    primary="#29c7ff",
    secondary="#ff8a1f",
    accent="#7fe3ff",
    warning="#ffb020",
    error="#ff4d5e",
    success="#3ddc97",
    foreground="#d6e6f5",
    background="#070d17",
    surface="#0d1726",
    panel="#13223a",
    dark=True,
    variables={
        "block-cursor-foreground": "#070d17",
        "block-cursor-background": "#29c7ff",
        "input-selection-background": "#29c7ff 35%",
        "footer-key-foreground": "#29c7ff",
        "footer-background": "#0a1320",
    },
)
