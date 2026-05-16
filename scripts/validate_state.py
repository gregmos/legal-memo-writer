#!/usr/bin/env python3
"""Validate legal-memo-writer state.json.

This is intentionally conservative: it checks the fields the orchestrator,
continue skill, mediator, client-readiness gate, and export step depend on.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PHASES = {
    "intake_preliminary_research",
    "intake_questions_pending",
    "planning",
    "plan_approval_pending",
    "research",
    "research_sufficiency",
    "currency_check",
    "source_pack",
    "drafting",
    "revision_loop",
    "client_readiness",
    "export",
    "done",
    "failed",
    "cancelled_by_user",
}
LANGUAGES = {"ru", "en"}


def validate_state(state: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["top-level JSON value must be an object"]

    required = [
        "task_id",
        "user_query",
        "created_at",
        "language",
        "classification",
        "intake",
        "plan_approval",
        "current_phase",
        "current_iteration",
        "max_iterations",
        "max_plan_edit_iterations",
        "max_intake_iterations",
        "current_draft_path",
        "iterations",
        "client_readiness",
        "final_status",
        "final_docx_path",
    ]
    for key in required:
        if key not in state:
            errors.append(f"missing key: {key}")

    if state.get("language") not in LANGUAGES:
        errors.append("language must be ru or en")

    if state.get("current_phase") not in PHASES:
        errors.append(f"current_phase is invalid: {state.get('current_phase')!r}")

    current_iteration = state.get("current_iteration")
    max_iterations = state.get("max_iterations")
    if not isinstance(current_iteration, int) or current_iteration < 0:
        errors.append("current_iteration must be a non-negative integer")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        errors.append("max_iterations must be a positive integer")
    if isinstance(current_iteration, int) and isinstance(max_iterations, int):
        if current_iteration > max_iterations:
            errors.append("current_iteration cannot exceed max_iterations")

    if not isinstance(state.get("intake"), dict):
        errors.append("intake must be an object")
    else:
        intake_status = state["intake"].get("status")
        if intake_status not in {
            "preliminary_research",
            "questions_pending",
            "answered",
            "assumptions_accepted",
        }:
            errors.append(f"intake.status is invalid: {intake_status!r}")

    if not isinstance(state.get("plan_approval"), dict):
        errors.append("plan_approval must be an object")
    else:
        plan_status = state["plan_approval"].get("status")
        if plan_status not in {"not_started", "pending", "approved", "cancelled"}:
            errors.append(f"plan_approval.status is invalid: {plan_status!r}")
        if not isinstance(state["plan_approval"].get("iterations"), list):
            errors.append("plan_approval.iterations must be a list")

    if not isinstance(state.get("iterations"), list):
        errors.append("iterations must be a list")

    attempts = state.get("attempts")
    if attempts is not None:
        if not isinstance(attempts, dict):
            errors.append("attempts must be an object when present")
        else:
            for key in ("research_followup", "client_readiness_polish"):
                value = attempts.get(key, 0)
                if not isinstance(value, int) or value < 0:
                    errors.append(f"attempts.{key} must be a non-negative integer")
            for key in ("research_followup_pending_review", "client_readiness_polish_pending_review"):
                value = attempts.get(key, False)
                if not isinstance(value, bool):
                    errors.append(f"attempts.{key} must be a boolean")
            retry_budget = attempts.get("reviewer_json_retry", {})
            if not isinstance(retry_budget, dict):
                errors.append("attempts.reviewer_json_retry must be an object")
            elif not all(isinstance(value, int) and value >= 0 for value in retry_budget.values()):
                errors.append("attempts.reviewer_json_retry values must be non-negative integers")

    remaining = state.get("remaining_blocking_issues")
    if remaining is not None and not isinstance(remaining, list):
        errors.append("remaining_blocking_issues must be a list when present")

    final_status = state.get("final_status")
    if final_status is not None and not isinstance(final_status, str):
        errors.append("final_status must be null or string")

    client_readiness = state.get("client_readiness")
    if client_readiness is not None and not isinstance(client_readiness, dict):
        errors.append("client_readiness must be null or object")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate legal-memo-writer state.json.")
    parser.add_argument("--state", help="Path to state.json")
    parser.add_argument("--workdir", help="Task working directory containing state.json")
    args = parser.parse_args()

    if not args.state and not args.workdir:
        parser.error("provide --state or --workdir")

    state_path = Path(args.state) if args.state else Path(args.workdir) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "path": str(state_path),
                    "errors": [f"invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"],
                },
                indent=2,
            )
        )
        return 1
    except OSError as exc:
        print(json.dumps({"ok": False, "path": str(state_path), "errors": [str(exc)]}, indent=2))
        return 2

    errors = validate_state(state)
    print(json.dumps({"ok": not errors, "path": str(state_path), "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
