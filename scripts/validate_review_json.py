#!/usr/bin/env python3
"""Validate legal-memo-writer reviewer JSON outputs.

The revision loop relies on five reviewer JSON files before the mediator can
make an exit decision. This script gives the main session and continue skill a
single deterministic validator so resume paths cannot accidentally skip schema
checks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REVIEWERS = ("logic", "clarity", "style", "citations", "counterarguments")
REQUIRED_KEYS = (
    "reviewer",
    "version_reviewed",
    "overall_score",
    "blocking_issues",
    "nice_to_have",
    "verdict",
)
VALID_VERDICTS = {"approved", "needs_revision"}


def reviewer_path(workdir: Path, iteration: int, reviewer: str) -> Path:
    return workdir / "reviews" / f"v{iteration}-{reviewer}.json"


def issue_stub(reviewer: str, reason: str) -> dict[str, Any]:
    base = {
        "section": "Pipeline",
        "issue": f"{reviewer} failed reviewer JSON validation: {reason}",
        "suggestion": "Re-run this reviewer or inspect the draft manually before relying on the memo.",
    }
    if reviewer == "citations":
        base["issue_category"] = "unsupported_claim"
        base["research_pointer"] = "not applicable"
    if reviewer == "counterarguments":
        base["attack_vector"] = "client_readiness"
        base["source_pack_pointer"] = "not applicable"
    return base


def failure_stub(reviewer: str, iteration: int, reason: str) -> dict[str, Any]:
    return {
        "reviewer": reviewer,
        "version_reviewed": iteration,
        "overall_score": 0,
        "blocking_issues": [issue_stub(reviewer, reason)],
        "nice_to_have": [],
        "verdict": "needs_revision",
        "status": "failed",
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def validate_payload(payload: Any, reviewer: str, iteration: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["top-level JSON value must be an object"]

    for key in REQUIRED_KEYS:
        if key not in payload:
            errors.append(f"missing key: {key}")

    if payload.get("reviewer") != reviewer:
        errors.append(f"reviewer must be {reviewer!r}")

    if payload.get("version_reviewed") != iteration:
        errors.append(f"version_reviewed must be {iteration}")

    score = payload.get("overall_score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        errors.append("overall_score must be an integer from 0 to 100")

    blocking = payload.get("blocking_issues")
    if not isinstance(blocking, list):
        errors.append("blocking_issues must be a list")

    nice = payload.get("nice_to_have")
    if not isinstance(nice, list):
        errors.append("nice_to_have must be a list")

    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append("verdict must be approved or needs_revision")
    elif verdict == "approved" and isinstance(blocking, list) and blocking:
        errors.append("approved verdict cannot have blocking_issues")

    if payload.get("status") == "failed" and verdict != "needs_revision":
        errors.append("failed reviewer stubs must use verdict needs_revision")

    return errors


def validate_file(path: Path, reviewer: str, iteration: int) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, ["file missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return False, [f"invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"]
    except OSError as exc:
        return False, [f"cannot read file: {exc}"]
    errors = validate_payload(payload, reviewer, iteration)
    return not errors, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate revision reviewer JSON files.")
    parser.add_argument("--workdir", required=True, help="Task working directory")
    parser.add_argument("--iteration", required=True, type=int, help="Draft iteration number")
    parser.add_argument(
        "--write-failure-stubs",
        action="store_true",
        help="Replace invalid or missing reviewer files with blocking failure stubs",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir)
    if not workdir.exists():
        print(json.dumps({"ok": False, "error": f"workdir not found: {workdir}"}, indent=2))
        return 2

    invalid: list[dict[str, Any]] = []
    valid: list[dict[str, str]] = []

    for reviewer in REVIEWERS:
        path = reviewer_path(workdir, args.iteration, reviewer)
        ok, errors = validate_file(path, reviewer, args.iteration)
        if ok:
            valid.append({"reviewer": reviewer, "path": str(path)})
            continue

        invalid.append({"reviewer": reviewer, "path": str(path), "errors": errors})
        if args.write_failure_stubs:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(path, failure_stub(reviewer, args.iteration, "; ".join(errors)))

    result = {
        "ok": not invalid,
        "iteration": args.iteration,
        "valid_reviewers": valid,
        "invalid_reviewers": invalid,
        "failure_stubs_written": bool(args.write_failure_stubs and invalid),
    }
    print(json.dumps(result, indent=2))
    return 0 if not invalid else 1


if __name__ == "__main__":
    sys.exit(main())
