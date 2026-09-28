#!/usr/bin/env python3
"""Wait for the next event among a paseo-autopilot run's agents.

The orchestrator runs this between polls instead of idling. It exits as soon
as a run agent has a pending permission request, a run agent's status changes,
or the timeout elapses, and prints one JSON object describing the event. It
never answers a permission request and never changes an agent; it only wakes
the orchestrator. Permission names and descriptions are worker-controlled text
and are printed as data. Standard library only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import time
from typing import Any


MAX_TIMEOUT = 60.0


class WatchError(Exception):
    pass


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from exc
    if not seconds > 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return seconds


def _timeout_seconds(value: str) -> float:
    seconds = _positive_seconds(value)
    if seconds > MAX_TIMEOUT:
        raise argparse.ArgumentTypeError(f"must be at most {MAX_TIMEOUT:g} seconds, the poll interval")
    return seconds


def _paseo_json(paseo: str, args: list[str]) -> Any:
    try:
        result = subprocess.run([paseo, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WatchError(f"paseo {' '.join(args)} failed: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:500]
        raise WatchError(f"paseo {' '.join(args)} exited {result.returncode}: {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WatchError(f"paseo {' '.join(args)} returned invalid JSON: {exc}") from exc


def _agents(paseo: str, label: str) -> dict[str, str]:
    data = _paseo_json(paseo, ["ls", "--label", label, "-g", "-a", "--json"])
    if not isinstance(data, list):
        raise WatchError("paseo ls did not return a JSON list")
    agents: dict[str, str] = {}
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise WatchError("paseo ls returned an entry without a string id")
        agents[entry["id"]] = str(entry.get("status"))
    return agents


def _permissions(paseo: str, agent_ids: set[str]) -> list[dict[str, Any]]:
    data = _paseo_json(paseo, ["permit", "ls", "--json"])
    if not isinstance(data, list):
        raise WatchError("paseo permit ls did not return a JSON list")
    pending = []
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("agentId"), str):
            raise WatchError("paseo permit ls returned an entry without a string agentId")
        if entry["agentId"] in agent_ids:
            pending.append({key: entry.get(key) for key in ("agentId", "id", "name", "description")})
    return pending


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def watch(paseo: str, label: str, interval: float, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    baseline: dict[str, str] | None = None
    while True:
        agents = _agents(paseo, label)
        pending = _permissions(paseo, set(agents))
        if pending:
            return {"event": "permission", "permissions": pending, "agents": agents, "checked_at": _now()}
        if baseline is None:
            baseline = agents
        else:
            changes = [
                {"agentId": agent_id, "before": baseline.get(agent_id), "after": agents.get(agent_id)}
                for agent_id in sorted(set(baseline) | set(agents))
                if baseline.get(agent_id) != agents.get(agent_id)
            ]
            if changes:
                return {"event": "status", "changes": changes, "agents": agents, "checked_at": _now()}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"event": "timeout", "agents": agents, "checked_at": _now()}
        time.sleep(min(interval, remaining))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Wait until a run agent has a pending permission request or changes status, "
            "or the timeout elapses; print one JSON event."
        )
    )
    parser.add_argument("--label", required=True, help="run label, for example paseo-autopilot.run=<run-id>")
    parser.add_argument("--interval", type=_positive_seconds, default=5.0, help="seconds between checks (default 5)")
    parser.add_argument("--timeout", type=_timeout_seconds, default=60.0, help="seconds to wait, at most 60 (default 60)")
    parser.add_argument("--paseo", default="paseo", help="paseo executable (default: paseo)")
    args = parser.parse_args(argv)
    try:
        event = watch(args.paseo, args.label, args.interval, args.timeout)
    except WatchError as exc:
        print(json.dumps({"event": "error", "reason": str(exc), "checked_at": _now()}))
        return 1
    print(json.dumps(event))
    return 0


if __name__ == "__main__":
    sys.exit(main())
