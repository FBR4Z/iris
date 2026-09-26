"""A minimal fake ACP agent for testing Íris without spending real model quota.

It answers every prompt with a canned markdown reply, optionally preceded by a tool
call, then renames the session — the same sequence Claude Code sends.

    iris acp "python tools/fake_agent.py"
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
                            ],
                        },
                    },
                }
            )
        elif method == "session/set_mode":
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
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
