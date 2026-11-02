#!/usr/bin/env python3
"""Claude Code PostToolUse hook: check JSON-LD right after an Edit/Write.

Registered by hooks/hooks.json. The edited path comes from argv or from the
hook event JSON on stdin (tool_input.file_path). The file is already written,
so the hook only reports:
- errors (invalid JSON, missing @context/@type, placeholders, deprecated types,
  clinic/FAQ required properties): exit 2, stderr is fed back to Claude;
- warnings only: exit 0 with hookSpecificOutput.additionalContext JSON.

Adapted from AgriciDaniel/claude-seo (MIT, Copyright (c) 2026 AgriciDaniel):
hooks/validate-schema.py. Validation logic lives in scripts/schema_check.py.
See NOTICE.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from schema_check import CHECKED_EXTENSIONS, validate_content  # noqa: E402

MAX_FILE_BYTES = 10 * 1024 * 1024


def resolve_filepath():
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        return sys.argv[1]
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    path = (event.get("tool_input") or {}).get("file_path") if isinstance(event, dict) else None
    return path if path and os.path.isfile(path) else None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    path = resolve_filepath()
    if not path or not path.lower().endswith(CHECKED_EXTENSIONS) or os.path.getsize(path) > MAX_FILE_BYTES:
        return 0
    result = validate_content(Path(path).read_text(encoding="utf-8", errors="replace"), path)
    if result["blocks"] == 0:
        return 0
    if result["errors"]:
        print("JSON-LD errors in %s (fix before shipping):" % path, file=sys.stderr)
        for message in result["errors"]:
            print("  - %s" % message, file=sys.stderr)
        for message in result["warnings"]:
            print("  - warning: %s" % message, file=sys.stderr)
        return 2
    if result["warnings"]:
        context = "JSON-LD warnings for %s:\n%s" % (path, "\n".join("- %s" % m for m in result["warnings"]))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
