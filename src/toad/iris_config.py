"""Session settings the agent lets the client change: model, effort, fast mode...

Agents report these in two shapes:

- `configOptions` (Claude Code): a list of select options, changed with
  `session/set_config_option`. Updates arrive as `config_option_update`.
- `models` (Gemini CLI): the available models, changed with `session/set_model`.

Both are turned into `ConfigOption`, so `/model` works the same for every agent.
"""

from __future__ import annotations

import unicodedata
from typing import Any, NamedTuple

MODEL = "model"
EFFORT = "thought_level"


class ConfigChoice(NamedTuple):
    value: str
    name: str
    description: str = ""


class ConfigOption(NamedTuple):
    id: str
    name: str
    category: str
    current: str
    choices: tuple[ConfigChoice, ...]
    via_models: bool = False
    """Set with `session/set_model` (the `models` shape) instead of `set_config_option`."""

    @property
    def current_name(self) -> str:
        for choice in self.choices:
            if choice.value == self.current:
                return choice.name
        return self.current

    def with_current(self, value: str) -> ConfigOption:
        return self._replace(current=value)


def _fold(text: str) -> str:
    """Lowercase without accents, so "esforço" matches "esforco"."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def parse_config_options(options: Any) -> list[ConfigOption]:
    """Parse the `configOptions` list (only select options can be offered as a menu)."""
    parsed: list[ConfigOption] = []
    if not isinstance(options, list):
        return parsed
    for option in options:
        if not isinstance(option, dict) or option.get("type", "select") != "select":
            continue
        choices = tuple(
            ConfigChoice(
                str(choice.get("value", "")),
                str(choice.get("name") or choice.get("value", "")),
                str(choice.get("description") or ""),
            )
            for choice in option.get("options") or []
            if isinstance(choice, dict) and "value" in choice
        )
        if not choices or "id" not in option:
            continue
        parsed.append(
            ConfigOption(
                str(option["id"]),
                str(option.get("name") or option["id"]),
                str(option.get("category") or ""),
                str(option.get("currentValue", "")),
                choices,
            )
        )
    return parsed


def parse_models(models: Any) -> ConfigOption | None:
    """Parse the `models` object into a model option."""
    if not isinstance(models, dict):
        return None
    choices = tuple(
        ConfigChoice(
            str(model["modelId"]),
            str(model.get("name") or model["modelId"]),
            str(model.get("description") or ""),
        )
        for model in models.get("availableModels") or []
        if isinstance(model, dict) and "modelId" in model
    )
    if not choices:
        return None
    return ConfigOption(
        MODEL, "Model", MODEL, str(models.get("currentModelId", "")), choices, True
    )


def parse_session_options(response: Any) -> list[ConfigOption] | None:
    """Options from a `session/new` or `session/load` response (`None` if absent)."""
    if not isinstance(response, dict):
        return None
    if "configOptions" in response:
        return parse_config_options(response["configOptions"])
    if (model := parse_models(response.get("models"))) is not None:
        return [model]
    return None


def by_category(options: list[ConfigOption], category: str) -> ConfigOption | None:
    for option in options:
        if option.category == category:
            return option
    # Some agents may leave the category out: fall back on the id.
    for option in options:
        if option.id == category or (category == EFFORT and option.id == "effort"):
            return option
    return None


def find_choice(option: ConfigOption, text: str) -> ConfigChoice | None:
    """Pick a choice from what the user typed: exact value/name, then prefix, then part."""
    wanted = _fold(text)
    if not wanted:
        return None
    for choice in option.choices:
        if wanted in (_fold(choice.value), _fold(choice.name)):
            return choice
    for test in (str.startswith, str.__contains__):
        matches = [
            choice
            for choice in option.choices
            if test(_fold(choice.name), wanted) or test(_fold(choice.value), wanted)
        ]
        if len(matches) == 1:
            return matches[0]
    return None
