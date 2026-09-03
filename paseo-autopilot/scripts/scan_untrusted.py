#!/usr/bin/env python3
"""Flag instruction-like content in untrusted inputs.

Untrusted inputs are worker reports, target-repository files, and anything
fetched from outside. This scanner is heuristic and standard-library only. A
flag means "a person or the orchestrator must read this passage"; it never
means the passage is malicious, and a clean result never proves safety.
Nothing is modified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


EXCERPT_LIMIT = 200

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override-instructions",
        re.compile(
            r"\b(?:ignore|disregard|forget)\b[^.\n]{0,40}?\b(?:previous|prior|above|earlier|all|your|the)\b"
            r"[^.\n]{0,20}?\b(?:instructions?|rules?|prompts?|guidelines?)\b"
            r"|\byou are now\b"
            r"|\bnew instructions?\b"
            r"|\bsystem prompt\b",
            re.IGNORECASE,
        ),
    ),
    (
        "orchestrator-control",
        re.compile(
            r"\brun\.json\b"
            r"|\borchestrator\.lock\b"
            r"|\bAWAITING_USER\b"
            r"|\bmark(?:ed|ing)?\b[^.\n]{0,30}?\bcomplete\b"
            r"|\bset\b[^.\n]{0,20}?\bphase\b"
            r"|\bapprove\b[^.\n]{0,20}?\b(?:all|every|everything|this|the)\b"
            r"|\bskip\b[^.\n]{0,30}?\b(?:reviews?|verification|verifiers?|checkpoints?|tests?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "permission-escalation",
        re.compile(
            r"bypass[ -]?permissions"
            r"|--dangerously"
            r"|\bfull[- ]access\b"
            r"|docker\.sock"
            r"|\bsudo\b"
            r"|chmod\s+777"
            r"|\bauto-approve\b",
            re.IGNORECASE,
        ),
    ),
    (
        "external-action",
        re.compile(
            r"\bgit\s+push\b"
            r"|--force\b"
            r"|\bforce-with-lease\b"
            r"|\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z)?sh\b"
            r"|\brm\s+-rf\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hidden-content",
        re.compile(
            r"<!--"
            r"|[​‌‍⁠﻿]"
            r"|[‪-‮⁦-⁩]"
            r"|[A-Za-z0-9+/]{80,}={0,2}"
        ),
    ),
    (
        "agent-address",
        re.compile(
            r"\b(?:assistant|claude|codex|gpt|gemini|orchestrator|agent|ai)\b[,:]?\s+"
            r"(?:you\s+must|must\s+now|should\s+now|please|ignore|do\s+not)\b",
            re.IGNORECASE,
        ),
    ),
)


def scan_text(text: str) -> list[dict[str, Any]]:
    """Return one flag per (line, pattern) match, in file order."""

    flags: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern_id, pattern in PATTERNS:
            if pattern.search(line):
                flags.append({"line": number, "pattern": pattern_id, "excerpt": line.strip()[:EXCERPT_LIMIT]})
    return flags


def scan_paths(paths: list[str]) -> dict[str, Any]:
    """Scan each path; unreadable paths are reported in ``errors`` and skipped."""

    files: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in paths:
        path = Path(raw)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"cannot read {path}: {exc}")
            continue
        files.append({"path": str(path), "flags": scan_text(text)})
    flagged = sum(len(entry["flags"]) for entry in files)
    return {"files": files, "flagged": flagged, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="files to scan (reports, repository instruction files, fetched text)")
    parser.add_argument("--json", action="store_true", help="print a JSON object instead of one line per flag")
    args = parser.parse_args(argv)

    result = scan_paths(args.paths)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for entry in result["files"]:
            for flag in entry["flags"]:
                print(f"{entry['path']}:{flag['line']}:{flag['pattern']}: {flag['excerpt']}")
    for error in result["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    if result["errors"]:
        return 1
    return 2 if result["flagged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
