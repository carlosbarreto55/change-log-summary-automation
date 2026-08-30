#!/usr/bin/env python3
"""Deterministic, sanitized Claude Code executable used by subprocess tests."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


SUPPORTED_VERSION = "2.1.251"
RECORD_PATH_ENV_VAR = "FAKE_CLAUDE_RECORD_PATH"
MODE_ENV_VAR = "FAKE_CLAUDE_MODE"

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string", "minLength": 1}},
    "required": ["summary"],
    "additionalProperties": False,
}

VALUE_FLAGS = {
    "--output-format",
    "--json-schema",
    "--model",
    "--tools",
    "--system-prompt",
}


def _argument_names(arguments: list[str]) -> list[str]:
    names: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument.startswith("-"):
            names.append(argument)
            if argument in VALUE_FLAGS:
                index += 1
        index += 1
    return names


def _record(arguments: list[str], payload: bytes) -> None:
    record_path_value = os.environ.get(RECORD_PATH_ENV_VAR)
    if not record_path_value:
        raise RuntimeError(f"{RECORD_PATH_ENV_VAR} is required")

    working_directory = Path.cwd()
    entries = tuple(working_directory.iterdir())
    record = {
        "version": SUPPORTED_VERSION,
        "argument_names": _argument_names(arguments),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_size": len(payload),
        "process_id": os.getpid(),
        "working_directory": {
            "exists": working_directory.exists(),
            "is_directory": working_directory.is_dir(),
            "is_empty": not entries,
            "contains_git_entry": any(entry.name == ".git" for entry in entries),
        },
    }
    record_path = Path(record_path_value)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with record_path.open("a", encoding="utf-8") as record_file:
        record_file.write(json.dumps(record, sort_keys=True) + "\n")


def _valid_request(arguments: list[str]) -> bool:
    if len(arguments) != 15:
        return False
    if arguments[:4] != ["-p", "--output-format", "json", "--json-schema"]:
        return False
    try:
        schema = json.loads(arguments[4])
    except json.JSONDecodeError:
        return False
    return (
        schema == SUMMARY_SCHEMA
        and arguments[5] == "--model"
        and bool(arguments[6])
        and arguments[7:10]
        == ["--safe-mode", "--disable-slash-commands", "--tools"]
        and arguments[10] == ""
        and arguments[11:14]
        == [
            "--strict-mcp-config",
            "--no-session-persistence",
            "--system-prompt",
        ]
        and bool(arguments[14])
    )


def main() -> int:
    arguments = sys.argv[1:]
    payload = sys.stdin.buffer.read()
    _record(arguments, payload)

    if arguments == ["--version"]:
        print(f"{SUPPORTED_VERSION} (Claude Code)")
        return 0
    if not _valid_request(arguments):
        print("invalid restricted invocation", file=sys.stderr)
        return 64

    mode = os.environ.get(MODE_ENV_VAR, "success")
    if mode == "timeout":
        time.sleep(5)
        return 70
    if mode == "nonzero":
        print("FAKE-SENSITIVE-DIAGNOSTIC process failure", file=sys.stderr)
        return 70
    if mode == "login_failure":
        print("FAKE-SENSITIVE-ACCOUNT is not logged in", file=sys.stderr)
        return 71
    if mode == "usage_limit":
        print("FAKE-SENSITIVE-QUOTA usage limit reached", file=sys.stderr)
        return 72
    if mode == "malformed":
        print("FAKE-SENSITIVE-RAW-OUTPUT is not JSON")
        return 0
    if mode != "success":
        print("unsupported fake mode", file=sys.stderr)
        return 64

    digest = hashlib.sha256(payload).hexdigest()
    summary = f"- Deterministic summary {digest[:16]}"
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": json.dumps({"summary": summary}),
                "structured_output": {"summary": summary},
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError):
        print("fake Claude harness setup failed", file=sys.stderr)
        raise SystemExit(70) from None
