#!/usr/bin/env python3
"""Validate Paseo Autopilot run state without modifying it.

This intentionally uses only Python's standard library. JSON Schema is shipped
as portable documentation; the checks below are the executable contract.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "phase",
    "previous_phase",
    "resume_phase",
    "controller",
    "preset",
    "config",
    "permissions",
    "routing",
    "agents",
    "tasks",
    "attempts",
    "material_decisions",
    "findings",
    "updated_at",
)

PHASES = (
    "INTAKE",
    "SPEC",
    "SPEC_REVIEW",
    "PLAN",
    "PLAN_REVIEW",
    "BUILD_WAVES",
    "VERIFY",
    "REPAIR",
    "COMPLETE",
    "AWAITING_USER",
    "RESUME_RECONCILIATION",
    "ABANDONED",
    "CANCELLED",
)

ACTIVE_PHASES = {
    "INTAKE",
    "SPEC",
    "SPEC_REVIEW",
    "PLAN",
    "PLAN_REVIEW",
    "BUILD_WAVES",
    "VERIFY",
    "REPAIR",
}

TERMINAL_PHASES = {"COMPLETE", "ABANDONED", "CANCELLED"}
INTERRUPT_TRANSITIONS = {"AWAITING_USER", "RESUME_RECONCILIATION", "ABANDONED", "CANCELLED"}
ALLOWED_TRANSITIONS = {
    "INTAKE": {"SPEC", *INTERRUPT_TRANSITIONS},
    "SPEC": {"SPEC_REVIEW", *INTERRUPT_TRANSITIONS},
    "SPEC_REVIEW": {"PLAN", *INTERRUPT_TRANSITIONS},
    "PLAN": {"PLAN_REVIEW", *INTERRUPT_TRANSITIONS},
    "PLAN_REVIEW": {"BUILD_WAVES", *INTERRUPT_TRANSITIONS},
    "BUILD_WAVES": {"VERIFY", *INTERRUPT_TRANSITIONS},
    "VERIFY": {"COMPLETE", "REPAIR", *INTERRUPT_TRANSITIONS},
    "REPAIR": {"VERIFY", *INTERRUPT_TRANSITIONS},
    "COMPLETE": set(),
    "ABANDONED": set(),
    "CANCELLED": set(),
    "AWAITING_USER": {"RESUME_RECONCILIATION", "ABANDONED", "CANCELLED"},
    "RESUME_RECONCILIATION": {*ACTIVE_PHASES, "AWAITING_USER", "COMPLETE", "ABANDONED", "CANCELLED"},
}

PRESETS = {"lean", "balanced", "deep", "custom"}
ATTEMPT_ROLES = {"spec-reviewer", "plan-reviewer", "builder", "verifier", "repairer"}
ATTEMPT_STATUSES = {"planned", "running", "completed", "interrupted", "failed"}
TASK_STATUSES = {"planned", "running", "completed", "blocked", "failed"}
INITIATORS = {"automatic", "user"}
MATERIAL_CATEGORIES = {
    "scope-outcome",
    "public-interface-data-compatibility",
    "security-privacy-compliance-data",
    "visible-ux",
    "cost-external-deployment-destructive-elevated",
}
PRESET_CONFIG = {
    "lean": {"spec_reviews": 1, "plan_reviews": 1, "builder_cap": 2, "verifiers": 1},
    "balanced": {"spec_reviews": 2, "plan_reviews": 2, "builder_cap": 4, "verifiers": 1},
    "deep": {"spec_reviews": 3, "plan_reviews": 3, "builder_cap": 6, "verifiers": 2},
}
ROLE_REPORT_DIRECTORIES = {
    "spec-reviewer": PurePosixPath("reviews/spec"),
    "plan-reviewer": PurePosixPath("reviews/plan"),
    "builder": PurePosixPath("reports/build"),
    "verifier": PurePosixPath("reviews/verification"),
    "repairer": PurePosixPath("reports/repair"),
}
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[a-z0-9]+(?:-[a-z0-9]+)*$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

PHASE_ARTIFACTS = {
    "SPEC": ("00-brief.md",),
    "SPEC_REVIEW": ("00-brief.md", "01-spec.md"),
    "PLAN": ("00-brief.md", "01-spec.md", "02-spec-resolution.md"),
    "PLAN_REVIEW": ("00-brief.md", "01-spec.md", "02-spec-resolution.md", "03-plan.md"),
    "BUILD_WAVES": (
        "00-brief.md",
        "01-spec.md",
        "02-spec-resolution.md",
        "03-plan.md",
        "04-plan-resolution.md",
    ),
    "VERIFY": (
        "00-brief.md",
        "01-spec.md",
        "02-spec-resolution.md",
        "03-plan.md",
        "04-plan-resolution.md",
    ),
    "REPAIR": (
        "00-brief.md",
        "01-spec.md",
        "02-spec-resolution.md",
        "03-plan.md",
        "04-plan-resolution.md",
    ),
    "COMPLETE": (
        "00-brief.md",
        "01-spec.md",
        "02-spec-resolution.md",
        "03-plan.md",
        "04-plan-resolution.md",
        "05-verification-resolution.md",
        "06-final.md",
    ),
}


def is_transition_allowed(old_phase: str, new_phase: str) -> bool:
    """Return whether a distinct lifecycle transition is allowed."""

    return old_phase in ALLOWED_TRANSITIONS and new_phase in ALLOWED_TRANSITIONS[old_phase]


def _objects(value: Any, field: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return []
    if not all(isinstance(item, dict) for item in value):
        errors.append(f"every {field} item must be an object")
        return []
    return value


def _safe_relative_path(value: Any, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty relative path")
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field} must stay within the run directory")
        return None
    return value


def _validate_attempts(data: dict[str, Any], root: Path, errors: list[str]) -> None:
    attempts = _objects(data.get("attempts"), "attempts", errors)
    by_id: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    agent_ids: dict[str, str] = {}

    required = {
        "id",
        "assignment",
        "role",
        "paseo_agent_id",
        "transport_provider",
        "vendor_account_scope",
        "model",
        "report_path",
        "status",
        "initiated_by",
        "failure_evidence",
        "replacement_for",
        "replacement_attempt_id",
    }
    for index, attempt in enumerate(attempts):
        missing = sorted(required - attempt.keys())
        if missing:
            errors.append(f"attempts[{index}] missing fields: {', '.join(missing)}")
            continue
        attempt_id = attempt.get("id")
        if not isinstance(attempt_id, str) or not attempt_id:
            errors.append(f"attempts[{index}].id must be a non-empty string")
            continue
        if attempt_id in by_id:
            errors.append(f"duplicate attempt id: {attempt_id}")
        by_id[attempt_id] = attempt

        assignment = attempt.get("assignment")
        if not isinstance(assignment, str) or not assignment:
            errors.append(f"attempt {attempt_id} assignment must be a non-empty string")

        if attempt.get("role") not in ATTEMPT_ROLES:
            errors.append(f"attempt {attempt_id} has unknown role")
        if attempt.get("status") not in ATTEMPT_STATUSES:
            errors.append(f"attempt {attempt_id} has unknown status")
        if attempt.get("initiated_by") not in INITIATORS:
            errors.append(f"attempt {attempt_id} has invalid initiated_by")

        agent_id = attempt.get("paseo_agent_id")
        if attempt.get("status") == "planned":
            if agent_id is not None:
                errors.append(f"planned attempt {attempt_id} must not have paseo_agent_id before launch")
        elif not isinstance(agent_id, str) or not agent_id:
            errors.append(f"attempt {attempt_id} requires paseo_agent_id")
        elif agent_id in agent_ids:
            errors.append(f"attempt {attempt_id} reuses paseo_agent_id from {agent_ids[agent_id]}")
        else:
            agent_ids[agent_id] = attempt_id

        report_path = _safe_relative_path(attempt.get("report_path"), f"attempt {attempt_id} report_path", errors)
        if report_path:
            if report_path in paths:
                errors.append(f"duplicate report_path: {report_path}")
            else:
                paths[report_path] = attempt_id
            if not PurePosixPath(report_path).name.endswith(f"--{attempt_id}.md"):
                errors.append(f"attempt {attempt_id} report basename must contain the exact attempt id")
            expected_directory = ROLE_REPORT_DIRECTORIES.get(attempt.get("role"))
            if expected_directory is not None and PurePosixPath(report_path).parent != expected_directory:
                errors.append(f"attempt {attempt_id} report_path is outside its role directory {expected_directory}")
            if attempt.get("status") == "completed" and not (root / report_path).is_file():
                errors.append(f"completed attempt {attempt_id} is missing report {report_path}")

        if attempt.get("status") == "interrupted":
            if not attempt.get("failure_evidence"):
                errors.append(f"interrupted attempt {attempt_id} requires failure_evidence")
        if attempt.get("status") == "failed" and not attempt.get("failure_evidence"):
            errors.append(f"failed attempt {attempt_id} requires failure_evidence")

    for attempt_id, attempt in by_id.items():
        replacement_id = attempt.get("replacement_attempt_id")
        if replacement_id:
            replacement = by_id.get(replacement_id)
            if replacement is None:
                errors.append(f"attempt {attempt_id} replacement {replacement_id} does not exist")
            elif replacement.get("replacement_for") != attempt_id:
                errors.append(f"replacement {replacement_id} does not link back to {attempt_id}")
            elif replacement.get("paseo_agent_id") == attempt.get("paseo_agent_id"):
                errors.append(f"replacement {replacement_id} must use a fresh Paseo agent")
        replaced_id = attempt.get("replacement_for")
        if replaced_id:
            replaced = by_id.get(replaced_id)
            if replaced is None:
                errors.append(f"attempt {attempt_id} replaces unknown attempt {replaced_id}")
            elif replaced.get("replacement_attempt_id") != attempt_id:
                errors.append(f"attempt {attempt_id} replacement link is not reciprocal")

    automatic_replacements: dict[str, int] = {}
    for attempt in attempts:
        assignment = attempt.get("assignment")
        if (
            isinstance(assignment, str)
            and attempt.get("replacement_for")
            and attempt.get("initiated_by") == "automatic"
        ):
            automatic_replacements[assignment] = automatic_replacements.get(assignment, 0) + 1
    for assignment, count in automatic_replacements.items():
        if count > 2:
            errors.append(f"assignment {assignment} has more than two automatic replacements")

    pending_decision = any(
        isinstance(decision, dict) and decision.get("status") == "pending"
        for decision in data.get("material_decisions", [])
    ) if isinstance(data.get("material_decisions"), list) else False
    for attempt in attempts:
        if not isinstance(attempt, dict) or attempt.get("status") != "interrupted":
            continue
        if attempt.get("replacement_attempt_id"):
            continue
        assignment = attempt.get("assignment")
        cap_exhausted_pause = (
            isinstance(assignment, str)
            and automatic_replacements.get(assignment, 0) >= 2
            and data.get("phase") == "AWAITING_USER"
            and pending_decision
        )
        if data.get("phase") not in {"ABANDONED", "CANCELLED"} and not cap_exhausted_pause:
            errors.append(f"interrupted attempt {attempt.get('id')} requires a replacement link")


def _validate_tasks(data: dict[str, Any], root: Path, errors: list[str]) -> None:
    tasks = _objects(data.get("tasks"), "tasks", errors)
    attempts = data.get("attempts") if isinstance(data.get("attempts"), list) else []
    attempt_by_id = {
        item.get("id"): item for item in attempts if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    by_id: dict[str, dict[str, Any]] = {}
    required = {
        "id",
        "status",
        "wave",
        "dependencies",
        "owned_files",
        "shared_mutable_paths",
        "exclusive_resources",
        "consumed_interfaces",
        "produced_interfaces",
        "attempt_ids",
    }
    for index, task in enumerate(tasks):
        missing = sorted(required - task.keys())
        if missing:
            errors.append(f"tasks[{index}] missing fields: {', '.join(missing)}")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"tasks[{index}].id must be a non-empty string")
            continue
        if task_id in by_id:
            errors.append(f"duplicate task id: {task_id}")
        by_id[task_id] = task
        if task.get("status") not in TASK_STATUSES:
            errors.append(f"task {task_id} has unknown status")
        if not isinstance(task.get("wave"), int) or task["wave"] < 1:
            errors.append(f"task {task_id} wave must be a positive integer")
        for field in (
            "dependencies",
            "owned_files",
            "shared_mutable_paths",
            "exclusive_resources",
            "consumed_interfaces",
            "produced_interfaces",
            "attempt_ids",
        ):
            if not isinstance(task.get(field), list) or not all(isinstance(v, str) for v in task.get(field, [])):
                errors.append(f"task {task_id} {field} must be an array of strings")

        if task.get("status") == "completed":
            completed = [
                attempt
                for attempt in attempts
                if isinstance(attempt, dict)
                and attempt.get("assignment") == task_id
                and attempt.get("status") == "completed"
            ]
            report_exists = any(
                isinstance(attempt.get("report_path"), str) and (root / attempt["report_path"]).is_file()
                for attempt in completed
            )
            if not report_exists:
                errors.append(f"completed task {task_id} has no completed attempt report")

        for attempt_id in task.get("attempt_ids", []):
            if attempt_id not in attempt_by_id:
                errors.append(f"task {task_id} references unknown attempt {attempt_id}")

    for task in tasks:
        if not isinstance(task, dict) or task.get("id") not in by_id:
            continue
        for dependency in task.get("dependencies", []):
            if dependency not in by_id:
                errors.append(f"task {task['id']} references unknown dependency {dependency}")
            elif dependency == task["id"]:
                errors.append(f"task {task['id']} cannot depend on itself")
            elif isinstance(task.get("wave"), int) and isinstance(by_id[dependency].get("wave"), int):
                if by_id[dependency]["wave"] >= task["wave"]:
                    errors.append(
                        f"task {task['id']} dependency {dependency} must be in an earlier wave"
                    )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            errors.append(f"task dependency cycle includes {task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id].get("dependencies", []):
            if dependency in by_id:
                visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)

    collision_fields = ("owned_files", "shared_mutable_paths", "exclusive_resources")
    for left_index, left in enumerate(tasks):
        if not isinstance(left, dict) or not isinstance(left.get("wave"), int):
            continue
        for right in tasks[left_index + 1 :]:
            if not isinstance(right, dict) or right.get("wave") != left.get("wave"):
                continue
            for field in collision_fields:
                overlap = set(left.get(field, [])) & set(right.get(field, []))
                if overlap:
                    errors.append(
                        f"same-wave tasks {left.get('id')} and {right.get('id')} collide in {field}: "
                        + ", ".join(sorted(overlap))
                    )
            left_consumed = set(left.get("consumed_interfaces", []))
            left_produced = set(left.get("produced_interfaces", []))
            right_consumed = set(right.get("consumed_interfaces", []))
            right_produced = set(right.get("produced_interfaces", []))
            interface_overlap = (left_produced & (right_consumed | right_produced)) | (
                right_produced & left_consumed
            )
            if interface_overlap:
                errors.append(
                    f"same-wave tasks {left.get('id')} and {right.get('id')} have an interface collision: "
                    + ", ".join(sorted(interface_overlap))
                )

    task_ids = set(by_id)
    for attempt in attempts:
        if not isinstance(attempt, dict) or attempt.get("role") != "builder":
            continue
        assignment = attempt.get("assignment")
        if isinstance(assignment, str) and assignment not in task_ids:
            errors.append(f"builder attempt {attempt.get('id')} references unknown task assignment {assignment}")
        elif isinstance(assignment, str) and attempt.get("id") not in by_id[assignment].get("attempt_ids", []):
            errors.append(f"builder attempt {attempt.get('id')} is not linked from task {assignment}")


def _validate_material_decisions(data: dict[str, Any], root: Path, errors: list[str]) -> None:
    decisions = _objects(data.get("material_decisions"), "material_decisions", errors)
    decision_by_id: dict[str, dict[str, Any]] = {}
    for index, decision in enumerate(decisions):
        decision_id = decision.get("id")
        if not isinstance(decision_id, str) or not decision_id:
            errors.append(f"material_decisions[{index}].id must be a non-empty string")
            continue
        if decision_id in decision_by_id:
            errors.append(f"duplicate material decision id: {decision_id}")
        decision_by_id[decision_id] = decision
        if decision.get("status") not in {"approved", "rejected", "pending"}:
            errors.append(f"material decision {decision_id} has invalid status")
        artifact = _safe_relative_path(decision.get("artifact"), f"material decision {decision_id} artifact", errors)
        if artifact and not (root / artifact).is_file():
            errors.append(f"material decision {decision_id} is missing artifact {artifact}")

    findings = _objects(data.get("findings", []), "findings", errors)
    for index, finding in enumerate(findings):
        finding_id = finding.get("id", f"index-{index}")
        required = {"id", "source_report", "outcome", "reason", "material", "category", "decision_id"}
        missing = required - finding.keys()
        if missing:
            errors.append(f"finding {finding_id} missing fields: {', '.join(sorted(missing))}")
        source_report = _safe_relative_path(
            finding.get("source_report"), f"finding {finding_id} source_report", errors
        )
        if source_report and not (root / source_report).is_file():
            errors.append(f"finding {finding_id} source report does not exist: {source_report}")
        if finding.get("outcome") not in {"accepted", "rejected", "deferred", "no-findings"}:
            errors.append(f"finding {finding_id} has invalid outcome")
        if not isinstance(finding.get("reason"), str) or not finding.get("reason"):
            errors.append(f"finding {finding_id} requires a reason")
        material = finding.get("material")
        if not isinstance(material, bool):
            errors.append(f"finding {finding_id} material must be boolean")
            continue
        category = finding.get("category")
        decision_id = finding.get("decision_id")
        if material:
            if category not in MATERIAL_CATEGORIES:
                errors.append(f"material finding {finding_id} has invalid gate category")
            decision = decision_by_id.get(decision_id)
            if decision is None:
                errors.append(f"material finding {finding_id} lacks a matching user decision")
            elif decision.get("status") == "pending":
                if data.get("phase") != "AWAITING_USER" or finding.get("outcome") != "deferred":
                    errors.append(
                        f"material finding {finding_id} has a pending decision outside a deferred AWAITING_USER gate"
                    )
        elif category is not None or decision_id is not None:
            errors.append(f"non-material finding {finding_id} must not claim a gate category or user decision")

    if data.get("phase") == "COMPLETE":
        pending = [decision.get("id") for decision in decisions if decision.get("status") == "pending"]
        if pending:
            errors.append("COMPLETE cannot contain pending material decisions: " + ", ".join(pending))


def _validate_review_coverage(data: dict[str, Any], errors: list[str]) -> None:
    attempts = data.get("attempts") if isinstance(data.get("attempts"), list) else []
    findings = data.get("findings") if isinstance(data.get("findings"), list) else []
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    phase = data.get("phase")
    effective_phase = data.get("resume_phase") if phase in {"AWAITING_USER", "RESUME_RECONCILIATION"} else phase
    spec_done = effective_phase in {"PLAN", "PLAN_REVIEW", "BUILD_WAVES", "VERIFY", "REPAIR", "COMPLETE"}
    plan_done = effective_phase in {"BUILD_WAVES", "VERIFY", "REPAIR", "COMPLETE"}
    covered_reports = {
        finding.get("source_report") for finding in findings if isinstance(finding, dict)
    }
    for role, should_be_done, config_field in (
        ("spec-reviewer", spec_done, "spec_reviews"),
        ("plan-reviewer", plan_done, "plan_reviews"),
    ):
        if not should_be_done:
            continue
        reports = [
            attempt.get("report_path")
            for attempt in attempts
            if isinstance(attempt, dict)
            and attempt.get("role") == role
            and attempt.get("status") == "completed"
        ]
        required_count = config.get(config_field)
        if isinstance(required_count, int) and len(reports) < required_count:
            errors.append(f"phase {effective_phase} requires {required_count} completed {role} reports")
        for report in reports:
            if report not in covered_reports:
                errors.append(f"completed review report {report} has no findings audit record")


def _validate_phase(data: dict[str, Any], root: Path, errors: list[str]) -> None:
    phase = data.get("phase")
    if phase not in PHASES:
        errors.append(f"unknown phase: {phase!r}")
        return
    previous = data.get("previous_phase")
    if previous is None and phase != "INTAKE":
        errors.append("previous_phase may be null only for the first INTAKE state")
    elif previous is not None:
        if previous not in PHASES:
            errors.append(f"unknown previous_phase: {previous!r}")
        elif previous != phase and not is_transition_allowed(previous, phase):
            errors.append(f"illegal phase transition: {previous} -> {phase}")
    for relative_path in PHASE_ARTIFACTS.get(phase, ()):
        if not (root / relative_path).is_file():
            errors.append(f"phase {phase} requires artifact {relative_path}")

    if phase in {"AWAITING_USER", "RESUME_RECONCILIATION"}:
        resume_phase = data.get("resume_phase")
        if resume_phase not in ACTIVE_PHASES:
            errors.append(f"phase {phase} requires an active resume_phase")
        else:
            for relative_path in PHASE_ARTIFACTS.get(resume_phase, ()):
                if not (root / relative_path).is_file():
                    errors.append(f"resume_phase {resume_phase} requires artifact {relative_path}")
    if phase == "AWAITING_USER":
        decisions = data.get("material_decisions")
        has_pending = isinstance(decisions, list) and any(
            isinstance(decision, dict) and decision.get("status") == "pending" for decision in decisions
        )
        if not has_pending:
            errors.append("AWAITING_USER requires at least one pending material decision")
    if phase not in {"AWAITING_USER", "RESUME_RECONCILIATION"} and data.get("resume_phase") is not None:
        errors.append(f"resume_phase must be null outside AWAITING_USER and RESUME_RECONCILIATION")

    if phase == "COMPLETE":
        attempts = data.get("attempts") if isinstance(data.get("attempts"), list) else []
        verifier_paths = [
            attempt.get("report_path")
            for attempt in attempts
            if isinstance(attempt, dict)
            and attempt.get("role") == "verifier"
            and attempt.get("status") == "completed"
        ]
        config = data.get("config") if isinstance(data.get("config"), dict) else {}
        required_verifiers = config.get("verifiers")
        if not isinstance(required_verifiers, int) or required_verifiers < 1:
            errors.append("COMPLETE requires a positive configured verifier count")
        elif len(verifier_paths) < required_verifiers or len(set(verifier_paths)) < required_verifiers:
            errors.append(
                f"COMPLETE requires {required_verifiers} configured verifiers with unique completed reports"
            )
        if not (root / "05-verification-resolution.md").is_file():
            errors.append("COMPLETE requires 05-verification-resolution.md")
        tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
        unfinished = [
            task.get("id", "<unknown>")
            for task in tasks
            if isinstance(task, dict) and task.get("status") != "completed"
        ]
        if unfinished:
            errors.append("COMPLETE contains unfinished task(s): " + ", ".join(unfinished))


def _validate_configuration(data: dict[str, Any], errors: list[str]) -> None:
    config = data.get("config")
    if not isinstance(config, dict):
        errors.append("config must be an object")
        return
    required = {
        "spec_reviews",
        "plan_reviews",
        "builder_cap",
        "user_cap",
        "effective_concurrency",
        "verifiers",
    }
    missing = required - config.keys()
    if missing:
        errors.append("config missing fields: " + ", ".join(sorted(missing)))
        return
    for field in ("spec_reviews", "plan_reviews", "builder_cap", "effective_concurrency", "verifiers"):
        if not isinstance(config.get(field), int) or isinstance(config.get(field), bool) or config[field] < 1:
            errors.append(f"config.{field} must be a positive integer")
    user_cap = config.get("user_cap")
    if user_cap is not None and (
        not isinstance(user_cap, int) or isinstance(user_cap, bool) or user_cap < 1
    ):
        errors.append("config.user_cap must be a positive integer or null")

    builder_cap = config.get("builder_cap")
    effective = config.get("effective_concurrency")
    if isinstance(builder_cap, int) and not isinstance(builder_cap, bool):
        expected_effective = min(builder_cap, user_cap) if isinstance(user_cap, int) else builder_cap
        if effective != expected_effective:
            errors.append(f"config.effective_concurrency must equal {expected_effective}")

    preset = data.get("preset")
    expected = PRESET_CONFIG.get(preset)
    if expected:
        for field, value in expected.items():
            if config.get(field) != value:
                errors.append(f"preset {preset} requires config.{field}={value}")


def _validate_nested_structure(data: dict[str, Any], errors: list[str]) -> None:
    controller = data.get("controller")
    if not isinstance(controller, dict):
        errors.append("controller must be an object")
    else:
        missing = {"agent_id", "session_id", "status"} - controller.keys()
        if missing:
            errors.append("controller missing fields: " + ", ".join(sorted(missing)))
        if controller.get("agent_id") is not None and not isinstance(controller.get("agent_id"), str):
            errors.append("controller.agent_id must be a string or null")
        if not isinstance(controller.get("session_id"), str) or not controller.get("session_id"):
            errors.append("controller.session_id must be a non-empty string")
        if controller.get("status") not in {"active", "handed-off", "stale", "complete"}:
            errors.append("controller.status has an invalid value")

    permissions = data.get("permissions")
    permission_fields = {"local_write", "external", "destructive", "deployment", "docker"}
    if not isinstance(permissions, dict):
        errors.append("permissions must be an object")
    else:
        for field in sorted(permission_fields):
            if not isinstance(permissions.get(field), bool):
                errors.append(f"permissions.{field} must be boolean")

    routing = _objects(data.get("routing"), "routing", errors)
    routing_required = {"role", "transport_provider", "vendor_account_scope", "model"}
    for index, route in enumerate(routing):
        missing = routing_required - route.keys()
        if missing:
            errors.append(f"routing[{index}] missing fields: {', '.join(sorted(missing))}")
        for field in routing_required & route.keys():
            if not isinstance(route.get(field), str) or not route.get(field):
                errors.append(f"routing[{index}].{field} must be a non-empty string")
        if "fallbacks" in route and not isinstance(route["fallbacks"], list):
            errors.append(f"routing[{index}].fallbacks must be an array")

    agents = _objects(data.get("agents"), "agents", errors)
    agent_required = {"paseo_agent_id", "role", "attempt_id", "status"}
    seen_agents: set[str] = set()
    for index, agent in enumerate(agents):
        missing = agent_required - agent.keys()
        if missing:
            errors.append(f"agents[{index}] missing fields: {', '.join(sorted(missing))}")
        agent_id = agent.get("paseo_agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            errors.append(f"agents[{index}].paseo_agent_id must be a non-empty string")
        elif agent_id in seen_agents:
            errors.append(f"duplicate agents paseo_agent_id: {agent_id}")
        else:
            seen_agents.add(agent_id)

    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str) or not TIMESTAMP_RE.fullmatch(updated_at):
        errors.append("updated_at must be a UTC RFC 3339 timestamp ending in Z")
    else:
        try:
            datetime.fromisoformat(updated_at.removesuffix("Z") + "+00:00")
        except ValueError:
            errors.append("updated_at is not a valid UTC timestamp")


def _validate_agent_attempt_links(data: dict[str, Any], errors: list[str]) -> None:
    attempts = data.get("attempts") if isinstance(data.get("attempts"), list) else []
    agents = data.get("agents") if isinstance(data.get("agents"), list) else []
    valid_attempts = [attempt for attempt in attempts if isinstance(attempt, dict)]
    valid_agents = [agent for agent in agents if isinstance(agent, dict)]
    attempt_by_id = {
        attempt.get("id"): attempt for attempt in valid_attempts if isinstance(attempt.get("id"), str)
    }
    agent_pairs = {
        (agent.get("paseo_agent_id"), agent.get("attempt_id"))
        for agent in valid_agents
        if isinstance(agent.get("paseo_agent_id"), str) and isinstance(agent.get("attempt_id"), str)
    }
    for attempt in valid_attempts:
        if attempt.get("status") == "planned":
            continue
        pair = (attempt.get("paseo_agent_id"), attempt.get("id"))
        if pair not in agent_pairs:
            errors.append(f"attempt {attempt.get('id')} has no matching agents record")
    for agent in valid_agents:
        attempt = attempt_by_id.get(agent.get("attempt_id"))
        if attempt is None:
            errors.append(f"agent {agent.get('paseo_agent_id')} references unknown attempt {agent.get('attempt_id')}")
        elif attempt.get("paseo_agent_id") != agent.get("paseo_agent_id"):
            errors.append(f"agent {agent.get('paseo_agent_id')} does not match attempt {agent.get('attempt_id')}")


def validate(data: Any, root: Path) -> list[str]:
    """Return all validation errors for a parsed run object."""

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["run state must be a JSON object"]
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))

    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if not isinstance(data.get("run_id"), str) or not RUN_ID_RE.fullmatch(data["run_id"]):
        errors.append("run_id must match YYYYMMDDTHHMMSSZ-<short-slug>")
    else:
        timestamp = data["run_id"].split("-", 1)[0]
        try:
            datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
        except ValueError:
            errors.append("run_id timestamp is not a valid UTC date and time")
    if data.get("preset") not in PRESETS:
        errors.append(f"unknown preset: {data.get('preset')!r}")
    _validate_nested_structure(data, errors)
    _validate_configuration(data, errors)
    _validate_phase(data, root, errors)
    _validate_attempts(data, root, errors)
    _validate_tasks(data, root, errors)
    _validate_material_decisions(data, root, errors)
    _validate_review_coverage(data, errors)
    _validate_agent_attempt_links(data, errors)
    return errors


def validate_path(path: str | Path) -> list[str]:
    """Load and validate one run file, without writing to it."""

    run_path = Path(path)
    try:
        data = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON from {run_path}: {exc}"]
    return validate(data, run_path.parent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_json", type=Path, help="path to .paseo-autopilot/<run-id>/run.json")
    args = parser.parse_args(argv)
    errors = validate_path(args.run_json)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.run_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
