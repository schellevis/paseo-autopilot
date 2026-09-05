#!/usr/bin/env python3
"""Validate Paseo Autopilot run state without modifying it.

This intentionally uses only Python's standard library. JSON Schema is shipped
as portable documentation; the checks below are the executable contract.

``validate_with_warnings()`` returns a ``(errors, warnings)`` tuple in addition
to the existing ``validate()`` interface. Warnings are routing-diversity
advisories that do not block progression: they flag a routing entry whose first
fallback shares the primary's ``vendor_account_scope``, or whose fallback chain
contains no distinct scope. ``main()`` prints ``WARNING:`` lines to stderr and
keeps exit code 0 when only warnings are present.
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
ATTEMPT_ROLES = {"spec-reviewer", "plan-reviewer", "builder", "verifier", "repairer", "spike"}
ROUTING_MODES = {"automatic", "confirmed", "explicit"}
ROUTING_APPROVERS = {"user", "automatic"}
CHECKPOINTS = {"spec", "plan"}
DECISION_KINDS = {"material", "checkpoint", "spike"}
SPEC_CHECKPOINT_PHASES = {"PLAN", "PLAN_REVIEW", "BUILD_WAVES", "VERIFY", "REPAIR", "COMPLETE"}
PLAN_CHECKPOINT_PHASES = {"BUILD_WAVES", "VERIFY", "REPAIR", "COMPLETE"}
ATTEMPT_STATUSES = {"planned", "running", "completed", "interrupted", "failed"}
SCAN_DISPOSITIONS = {"clean", "reviewed", "suspected"}
LAUNCH_CHECK_STATUSES = {"pending", "started", "failed"}
ROUTING_AVAILABILITY = {"verified", "listed", "unavailable"}
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
    "spike": PurePosixPath("reports/spike"),
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


def _validate_launch_check(attempt: dict[str, Any], attempt_id: str, errors: list[str]) -> None:
    """A launched attempt must record whether its agent actually started.

    A returned agent ID only proves the create call was accepted. ``launch_check``
    forces the orchestrator to confirm a real start, or to record the provider's
    rejection (unknown model, model not allowed for this account type or plan,
    authentication failure) as explicit evidence instead of leaving it as silence.
    """

    status = attempt.get("status")
    check = attempt.get("launch_check")
    if status == "planned":
        if check is not None:
            errors.append(f"planned attempt {attempt_id} must not have a launch_check before launch")
        return
    if not isinstance(check, dict):
        errors.append(f"attempt {attempt_id} requires a launch_check object once launched")
        return
    check_status = check.get("status")
    if check_status not in LAUNCH_CHECK_STATUSES:
        errors.append(
            f"attempt {attempt_id} launch_check.status must be one of: "
            + ", ".join(sorted(LAUNCH_CHECK_STATUSES))
        )
        return
    evidence = check.get("evidence")
    if evidence is not None and not isinstance(evidence, str):
        errors.append(f"attempt {attempt_id} launch_check.evidence must be a string or null")
    checked_at = check.get("checked_at")
    if checked_at is not None and (not isinstance(checked_at, str) or not TIMESTAMP_RE.fullmatch(checked_at)):
        errors.append(f"attempt {attempt_id} launch_check.checked_at must be a UTC timestamp or null")
    if check_status == "failed":
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"attempt {attempt_id} launch_check failure requires the exact provider evidence")
        if status not in {"failed", "interrupted"}:
            errors.append(f"attempt {attempt_id} never started but is recorded as {status}")
    if check_status == "started" and not checked_at:
        errors.append(f"attempt {attempt_id} launch_check start requires checked_at")
    if status == "completed" and check_status != "started":
        errors.append(f"completed attempt {attempt_id} requires a confirmed launch_check start")
    if status in {"failed", "interrupted"} and check_status == "pending":
        errors.append(
            f"attempt {attempt_id} ended without deciding whether it ever started; "
            "launch_check must be started or failed"
        )


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
        "injection_scan",
        "launch_check",
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
        scan = attempt.get("injection_scan")
        if attempt.get("status") == "completed":
            if not isinstance(scan, dict):
                errors.append(f"completed attempt {attempt_id} requires an injection_scan record")
            else:
                flagged = scan.get("flagged")
                disposition = scan.get("disposition")
                if not isinstance(flagged, int) or isinstance(flagged, bool) or flagged < 0:
                    errors.append(f"attempt {attempt_id} injection_scan.flagged must be a non-negative integer")
                elif disposition not in SCAN_DISPOSITIONS:
                    errors.append(
                        f"attempt {attempt_id} injection_scan.disposition must be one of: clean, reviewed, suspected"
                    )
                elif flagged == 0 and disposition != "clean":
                    errors.append(f"attempt {attempt_id} injection_scan with zero flags must be clean")
                elif flagged > 0 and disposition == "clean":
                    errors.append(f"attempt {attempt_id} injection_scan with flags cannot be clean")
        elif scan is not None and not isinstance(scan, dict):
            errors.append(f"attempt {attempt_id} injection_scan must be an object or null")

        _validate_launch_check(attempt, attempt_id, errors)

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
        "routing_mode",
        "checkpoints",
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

    if config.get("routing_mode") not in ROUTING_MODES:
        errors.append("config.routing_mode must be one of: automatic, confirmed, explicit")

    checkpoints = config.get("checkpoints")
    if not isinstance(checkpoints, dict):
        errors.append("config.checkpoints must be an object with boolean spec and plan")
    else:
        for name in sorted(CHECKPOINTS):
            if not isinstance(checkpoints.get(name), bool):
                errors.append(f"config.checkpoints.{name} must be boolean")

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


def _has_left_intake(data: dict[str, Any]) -> bool:
    """True once the run has advanced beyond INTAKE, including paused non-intake states."""

    phase = data.get("phase")
    if phase == "INTAKE":
        return False
    if phase in {"AWAITING_USER", "RESUME_RECONCILIATION"} and data.get("resume_phase") == "INTAKE":
        return False
    return True


def _validate_routing_approval(data: dict[str, Any], errors: list[str]) -> None:
    """Confirmed/explicit runs need a complete, user-approved routing table after intake."""

    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    mode = config.get("routing_mode")
    if mode not in {"confirmed", "explicit"}:
        return
    routing_value = data.get("routing")
    routing = [route for route in routing_value if isinstance(route, dict)] if isinstance(routing_value, list) else []
    by_role = {route.get("role"): route for route in routing if isinstance(route.get("role"), str)}

    if _has_left_intake(data):
        missing_roles = ATTEMPT_ROLES - set(by_role)
        if missing_roles:
            errors.append(
                f"routing_mode {mode} requires a routing entry for every role after INTAKE; "
                "missing: " + ", ".join(sorted(missing_roles))
            )
        for route in routing:
            if route.get("approved_by") != "user":
                errors.append(
                    f"routing_mode {mode} requires approved_by 'user' for role {route.get('role')!r} after INTAKE"
                )

    attempts_value = data.get("attempts")
    attempts = [attempt for attempt in attempts_value if isinstance(attempt, dict)] if isinstance(attempts_value, list) else []
    for attempt in attempts:
        if attempt.get("paseo_agent_id") is None or attempt.get("initiated_by") != "automatic":
            continue
        route = by_role.get(attempt.get("role"))
        if route is None:
            continue
        identity = (
            attempt.get("transport_provider"),
            attempt.get("vendor_account_scope"),
            attempt.get("model"),
        )
        allowed = {(route.get("transport_provider"), route.get("vendor_account_scope"), route.get("model"))}
        fallbacks = route.get("fallbacks")
        for fallback in fallbacks if isinstance(fallbacks, list) else []:
            if isinstance(fallback, dict):
                allowed.add(
                    (fallback.get("transport_provider"), fallback.get("vendor_account_scope"), fallback.get("model"))
                )
        if identity not in allowed:
            errors.append(
                f"attempt {attempt.get('id')!r} uses {identity} outside the approved routing chain "
                f"for role {attempt.get('role')!r}"
            )


def _validate_model_availability(data: dict[str, Any], errors: list[str]) -> None:
    """Never relaunch automatically on a transport/scope/model the provider rejected."""

    routing_value = data.get("routing")
    routing = [route for route in routing_value if isinstance(route, dict)] if isinstance(routing_value, list) else []
    unavailable: dict[str, set[tuple[Any, Any, Any]]] = {}
    for route in routing:
        role = route.get("role")
        if not isinstance(role, str):
            continue
        options = [route]
        fallbacks = route.get("fallbacks")
        if isinstance(fallbacks, list):
            options.extend(fallback for fallback in fallbacks if isinstance(fallback, dict))
        for option in options:
            if option.get("availability") != "unavailable":
                continue
            unavailable.setdefault(role, set()).add(
                (
                    option.get("transport_provider"),
                    option.get("vendor_account_scope"),
                    option.get("model"),
                )
            )
    if not unavailable:
        return

    attempts_value = data.get("attempts")
    attempts = [attempt for attempt in attempts_value if isinstance(attempt, dict)] if isinstance(attempts_value, list) else []
    for attempt in attempts:
        if attempt.get("paseo_agent_id") is None or attempt.get("initiated_by") != "automatic":
            continue
        identity = (
            attempt.get("transport_provider"),
            attempt.get("vendor_account_scope"),
            attempt.get("model"),
        )
        if identity in unavailable.get(attempt.get("role"), set()):
            errors.append(
                f"attempt {attempt.get('id')!r} uses {identity}, recorded unavailable for role "
                f"{attempt.get('role')!r}"
            )


def _effective_phase(data: dict[str, Any]) -> Any:
    phase = data.get("phase")
    if phase in {"AWAITING_USER", "RESUME_RECONCILIATION"}:
        return data.get("resume_phase")
    return phase


def _validate_checkpoints(data: dict[str, Any], errors: list[str]) -> None:
    """Checkpoint decisions are well-formed and gate the phases the user asked to review."""

    decisions_value = data.get("material_decisions")
    decisions = (
        [decision for decision in decisions_value if isinstance(decision, dict)]
        if isinstance(decisions_value, list)
        else []
    )
    seen_rounds: set[tuple[str, int]] = set()
    approved: set[str] = set()
    for index, decision in enumerate(decisions):
        decision_id = decision.get("id")
        label = decision_id if isinstance(decision_id, str) and decision_id else f"index-{index}"
        kind = decision.get("kind", "material")
        if kind not in DECISION_KINDS:
            errors.append(f"decision {label} kind must be one of: checkpoint, material")
            continue
        if kind == "material":
            if "checkpoint" in decision or "round" in decision:
                errors.append(f"material decision {label} must not carry checkpoint or round")
            continue
        if kind == "spike":
            continue
        checkpoint = decision.get("checkpoint")
        round_number = decision.get("round")
        if checkpoint not in CHECKPOINTS:
            errors.append(f"checkpoint decision {label} requires checkpoint spec or plan")
        if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number < 1:
            errors.append(f"checkpoint decision {label} requires a positive integer round")
        elif checkpoint in CHECKPOINTS:
            key = (checkpoint, round_number)
            if key in seen_rounds:
                errors.append(f"duplicate checkpoint decision for {checkpoint} round {round_number}")
            seen_rounds.add(key)
        status = decision.get("status")
        if status == "approved" and checkpoint in CHECKPOINTS:
            approved.add(checkpoint)
        if status == "pending" and data.get("phase") != "AWAITING_USER":
            errors.append(f"checkpoint decision {label} is pending outside AWAITING_USER")

    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    checkpoints = config.get("checkpoints") if isinstance(config.get("checkpoints"), dict) else {}
    effective = _effective_phase(data)
    if checkpoints.get("spec") is True and effective in SPEC_CHECKPOINT_PHASES and "spec" not in approved:
        errors.append(f"phase {effective} requires an approved spec checkpoint decision")
    if checkpoints.get("plan") is True and effective in PLAN_CHECKPOINT_PHASES and "plan" not in approved:
        errors.append(f"phase {effective} requires an approved plan checkpoint decision")


def _validate_injection_findings(data: dict[str, Any], errors: list[str]) -> None:
    """A suspected injection must be escalated as a material security finding on that report."""

    attempts_value = data.get("attempts")
    attempts = [attempt for attempt in attempts_value if isinstance(attempt, dict)] if isinstance(attempts_value, list) else []
    findings_value = data.get("findings")
    findings = [finding for finding in findings_value if isinstance(finding, dict)] if isinstance(findings_value, list) else []
    for attempt in attempts:
        scan = attempt.get("injection_scan")
        if not isinstance(scan, dict) or scan.get("disposition") != "suspected":
            continue
        report = attempt.get("report_path")
        escalated = any(
            finding.get("source_report") == report
            and finding.get("material") is True
            and finding.get("category") == "security-privacy-compliance-data"
            for finding in findings
        )
        if not escalated:
            errors.append(
                f"attempt {attempt.get('id')!r} has a suspected injection without a material security finding on {report}"
            )


def _validate_spikes(data: dict[str, Any], errors: list[str]) -> None:
    """Spike decisions are well-formed and every spike attempt names an approved one."""

    decisions_value = data.get("material_decisions")
    decisions = (
        [decision for decision in decisions_value if isinstance(decision, dict)]
        if isinstance(decisions_value, list)
        else []
    )
    approved: set[str] = set()
    for index, decision in enumerate(decisions):
        if decision.get("kind") != "spike":
            continue
        decision_id = decision.get("id")
        label = decision_id if isinstance(decision_id, str) and decision_id else f"index-{index}"
        question = decision.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(f"spike decision {label} requires a non-empty question")
        access = decision.get("access")
        if not isinstance(access, dict) or not all(
            isinstance(access.get(field), bool) for field in ("repository", "network")
        ):
            errors.append(f"spike decision {label} requires access with boolean repository and network")
        limit = decision.get("limit")
        if not isinstance(limit, str) or not limit.strip():
            errors.append(f"spike decision {label} requires a non-empty limit")
        if "checkpoint" in decision or "round" in decision:
            errors.append(f"spike decision {label} must not carry checkpoint or round")
        status = decision.get("status")
        if status == "pending" and data.get("phase") != "AWAITING_USER":
            errors.append(f"spike decision {label} is pending outside AWAITING_USER")
        if status == "approved" and isinstance(decision_id, str) and decision_id:
            approved.add(decision_id)

    attempts_value = data.get("attempts")
    attempts = [attempt for attempt in attempts_value if isinstance(attempt, dict)] if isinstance(attempts_value, list) else []
    for attempt in attempts:
        if attempt.get("role") != "spike":
            continue
        decision_id = attempt.get("decision_id")
        if not isinstance(decision_id, str) or decision_id not in approved:
            errors.append(
                f"spike attempt {attempt.get('id')!r} requires decision_id naming an approved spike decision"
            )


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
    routing_required = {"role", "transport_provider", "vendor_account_scope", "model", "mode", "thinking", "approved_by"}
    routing_strings = {"role", "transport_provider", "vendor_account_scope", "model", "mode", "thinking"}
    seen_roles: set[str] = set()
    for index, route in enumerate(routing):
        missing = routing_required - route.keys()
        if missing:
            errors.append(f"routing[{index}] missing fields: {', '.join(sorted(missing))}")
        for field in routing_strings & route.keys():
            if not isinstance(route.get(field), str) or not route.get(field):
                errors.append(f"routing[{index}].{field} must be a non-empty string")
        role = route.get("role")
        if isinstance(role, str) and role:
            if role not in ATTEMPT_ROLES:
                errors.append(f"routing[{index}].role must be one of: {', '.join(sorted(ATTEMPT_ROLES))}")
            elif role in seen_roles:
                errors.append(f"routing[{index}].role {role!r} is duplicated")
            seen_roles.add(role)
        if "approved_by" in route and route.get("approved_by") not in ROUTING_APPROVERS:
            errors.append(f"routing[{index}].approved_by must be one of: automatic, user")
        if "availability" in route and route.get("availability") not in ROUTING_AVAILABILITY:
            errors.append(
                f"routing[{index}].availability must be one of: " + ", ".join(sorted(ROUTING_AVAILABILITY))
            )
        fallbacks = route.get("fallbacks", [])
        if not isinstance(fallbacks, list):
            errors.append(f"routing[{index}].fallbacks must be an array")
            continue
        for fallback_index, fallback in enumerate(fallbacks):
            if not isinstance(fallback, dict):
                errors.append(f"routing[{index}].fallbacks[{fallback_index}] must be an object")
                continue
            for field in ("transport_provider", "vendor_account_scope", "model"):
                if not isinstance(fallback.get(field), str) or not fallback.get(field):
                    errors.append(
                        f"routing[{index}].fallbacks[{fallback_index}].{field} must be a non-empty string"
                    )
            if "availability" in fallback and fallback.get("availability") not in ROUTING_AVAILABILITY:
                errors.append(
                    f"routing[{index}].fallbacks[{fallback_index}].availability must be one of: "
                    + ", ".join(sorted(ROUTING_AVAILABILITY))
                )

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
    _validate_routing_approval(data, errors)
    _validate_model_availability(data, errors)
    _validate_checkpoints(data, errors)
    _validate_injection_findings(data, errors)
    _validate_spikes(data, errors)
    _validate_phase(data, root, errors)
    _validate_attempts(data, root, errors)
    _validate_tasks(data, root, errors)
    _validate_material_decisions(data, root, errors)
    _validate_review_coverage(data, errors)
    _validate_agent_attempt_links(data, errors)
    return errors


def _validate_routing_diversity(data: dict[str, Any]) -> list[str]:
    """Return routing diversity warnings (never errors).

    Warns when the first fallback shares the primary's vendor_account_scope,
    or when no fallback has a distinct scope. Runs in all routing modes.
    Entries with no fallbacks are not warned.
    """

    warnings: list[str] = []
    routing = data.get("routing")
    if not isinstance(routing, list):
        return warnings
    for route in routing:
        if not isinstance(route, dict):
            continue
        role = route.get("role", "<unknown>")
        primary_scope = route.get("vendor_account_scope")
        fallbacks = route.get("fallbacks")
        if not isinstance(fallbacks, list) or not fallbacks:
            continue
        first_fallback = fallbacks[0] if isinstance(fallbacks[0], dict) else {}
        first_scope = first_fallback.get("vendor_account_scope")
        if first_scope == primary_scope:
            warnings.append(
                f"routing diversity warning for role {role}: first fallback shares "
                f"vendor_account_scope {primary_scope!r} with the primary"
            )
            continue
        has_distinct = any(
            isinstance(fb, dict) and fb.get("vendor_account_scope") != primary_scope
            for fb in fallbacks
        )
        if not has_distinct:
            warnings.append(
                f"routing diversity warning for role {role}: no fallback has a distinct "
                f"vendor_account_scope from the primary {primary_scope!r}"
            )
    return warnings


def validate_with_warnings(data: Any, root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a parsed run object.

    Errors are the same as ``validate()``. Warnings are routing diversity
    advisories that do not block progression.
    """

    errors = validate(data, root)
    warnings: list[str] = []
    if isinstance(data, dict):
        warnings = _validate_routing_diversity(data)
    return errors, warnings


def validate_path(path: str | Path) -> list[str]:
    """Load and validate one run file, without writing to it."""

    run_path = Path(path)
    try:
        data = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON from {run_path}: {exc}"]
    return validate(data, run_path.parent)


def validate_path_with_warnings(path: str | Path) -> tuple[list[str], list[str]]:
    """Load and validate one run file, returning (errors, warnings)."""

    run_path = Path(path)
    try:
        data = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return ([f"cannot read valid JSON from {run_path}: {exc}"], [])
    return validate_with_warnings(data, run_path.parent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_json", type=Path, help="path to .paseo-autopilot/<run-id>/run.json")
    args = parser.parse_args(argv)
    errors, warnings = validate_path_with_warnings(args.run_json)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"OK: {args.run_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
