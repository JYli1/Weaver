from __future__ import annotations

import json
import sys


def reply(message: dict[str, object], result: dict[str, object]) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}, ensure_ascii=False), flush=True)


def main() -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in message:
            continue

        method = message.get("method")
        if method == "initialize":
            reply(
                message,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "local-echo", "version": "1.0.0"},
                },
            )
        elif method == "tools/list":
            reply(
                message,
                {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo a text argument.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"}
                                },
                            },
                        }
                    ]
                },
            )
        elif method == "tools/call":
            args = message.get("params", {}).get("arguments", {})
            reply(message, {"content": [{"type": "text", "text": f"echo:{args.get('text', '')}"}]})
        else:
            reply(message, {})


if __name__ == "__main__":
    main()
