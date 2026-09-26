"""A minimal fake ACP agent for testing Íris without spending real model quota.

It answers every prompt with a canned markdown reply, optionally preceded by a tool
call, then renames the session — the same sequence Claude Code sends.

    iris acp "python tools/fake_agent.py"

Options are reported like Claude Code (`configOptions`), or like Gemini CLI (`models`)
with `--models`. Prompts that mention "skill" run a skill, "eco" answer with the
prompt as received (plus the MCP servers of the session), "tchau" drops the connection.
"""

import json
import sys
import time

SESSION = "fake-session"
# Fixed per run, like the real reset times.
FIVE_HOUR_RESET = time.time() + 3600
SEVEN_DAY_RESET = time.time() + 5 * 86400
REPLY = (
    "## Resultado\n\nAnalisei o projeto e encontrei **dois problemas** em `main.py`.\n\n"
    "```python\nprint('oi')\n```\n\nQuer que eu corrija?"
)


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def update(payload: dict) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {"sessionId": SESSION, "update": payload},
        }
    )


GEMINI_SHAPE = "--models" in sys.argv
MODELS = [("auto", "Auto"), ("gemini-2.5-pro", "gemini-2.5-pro"), ("gemini-3-flash", "gemini-3-flash")]
config = {"model": "opus", "effort": "default"}
mcp_servers: list = []


def config_options() -> list[dict]:
    return [
        {
            "id": "model",
            "name": "Model",
            "category": "model",
            "type": "select",
            "currentValue": config["model"],
            "options": [
                {"value": "opus", "name": "Opus 5.5", "description": "Best for complex tasks"},
                {"value": "sonnet", "name": "Sonnet 5"},
                {"value": "haiku", "name": "Haiku 4.5"},
            ],
        },
        {
            "id": "effort",
            "name": "Effort",
            "category": "thought_level",
            "type": "select",
            "currentValue": config["effort"],
            "options": [{"value": value, "name": value.title()} for value in ("default", "low", "high", "max")],
        },
    ]


def session_options() -> dict:
    if GEMINI_SHAPE:
        return {
            "models": {
                "availableModels": [{"modelId": key, "name": name} for key, name in MODELS],
                "currentModelId": config["model"],
            }
        }
    return {"configOptions": config_options()}


def say(text: str) -> None:
    update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": text}})


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, request_id = request.get("method"), request.get("id")
        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": 1,
                        "agentCapabilities": {"loadSession": False},
                        "authMethods": [],
                    },
                }
            )
        elif method == "session/new":
            mcp_servers[:] = request["params"].get("mcpServers", [])
            if GEMINI_SHAPE:
                config["model"] = "auto"
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "sessionId": SESSION,
                        "modes": {
                            "currentModeId": "default",
                            "availableModes": [
                                {"id": "default", "name": "Default"},
                                {"id": "plan", "name": "Plan"},
                                {"id": "bypassPermissions", "name": "Bypass permissions"},
                            ],
                        },
                        **session_options(),
                    },
                }
            )
        elif method == "session/set_mode":
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "session/set_config_option" and not GEMINI_SHAPE:
            config[request["params"]["configId"]] = request["params"]["value"]
            send({"jsonrpc": "2.0", "id": request_id, "result": {"configOptions": config_options()}})
        elif method == "session/set_model" and GEMINI_SHAPE:
            config["model"] = request["params"]["modelId"]
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "session/prompt" and (
            text := " ".join(
                block.get("text", "") for block in request["params"].get("prompt", [])
            )
        ) and ("eco" in text or "tchau" in text or "skill" in text):
            if "tchau" in text:
                return
            if "skill" in text:
                update(
                    {
                        "sessionUpdate": "tool_call",
                        "toolCallId": "s1",
                        "_meta": {"claudeCode": {"toolName": "Skill"}},
                        "name": "Skill",
                        "title": "Skill",
                        "kind": "other",
                        "status": "in_progress",
                    }
                )
                time.sleep(float(text.split()[-1]) if text.split()[-1].isdigit() else 0.5)
            else:
                say(text + "\n\nMCP: " + ",".join(server["name"] for server in mcp_servers))
            send({"jsonrpc": "2.0", "id": request_id, "result": {"stopReason": "end_turn"}})
        elif method == "session/prompt":
            # Same shape Claude Code sends: context use plus the subscription limits.
            update(
                {
                    "sessionUpdate": "usage_update",
                    "used": 23206,
                    "size": 200000,
                    "_meta": {
                        "_claude/rateLimit": {
                            "status": "allowed",
                            "unifiedWindows": {
                                "five_hour": {
                                    "utilization": 0.83,
                                    "resetsAt": FIVE_HOUR_RESET,
                                },
                                "seven_day": {
                                    "utilization": 0.12,
                                    "resetsAt": SEVEN_DAY_RESET,
                                },
                            },
                        }
                    },
                }
            )
            update(
                {
                    "sessionUpdate": "tool_call",
                    "toolCallId": "t1",
                    "title": "git status",
                    "kind": "execute",
                    "status": "completed",
                    "rawInput": {"command": "git status"},
                }
            )
            time.sleep(0.2)
            for chunk in (REPLY[:40], REPLY[40:]):
                update(
                    {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": chunk},
                    }
                )
                time.sleep(0.1)
            send({"jsonrpc": "2.0", "id": request_id, "result": {"stopReason": "end_turn"}})
            update({"sessionUpdate": "session_info_update", "title": "Sessão de teste"})
        elif request_id is not None:
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})


if __name__ == "__main__":
    main()
