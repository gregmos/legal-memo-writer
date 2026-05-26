#!/usr/bin/env python3
"""Validate memoforge reviewer JSON outputs.

The revision loop runs N reviewers in parallel (N = 3 in Brief mode, 5 in
Full). This script reads the active reviewer set from
state.json.config.reviewer_list (or an explicit --reviewers override) and
validates only that set, so Brief-mode runs don't fail on missing clarity/style
files. Gives the main session and continue skill a single deterministic
validator so resume paths cannot accidentally skip schema checks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ALL_REVIEWERS = ("logic", "clarity", "style", "citations", "counterarguments")
REQUIRED_KEYS = (
    "reviewer",
    "version_reviewed",
    "overall_score",
    "blocking_issues",
    "nice_to_have",
    "verdict",
)
VALID_VERDICTS = {"approved", "needs_revision"}

# Per-reviewer extra-field enums. citations reviewer must classify each blocking
# issue with `issue_category`; counterarguments reviewer with `attack_vector`.
# Mediator preserves these labels when consolidating, so writer can distinguish
# "unsupported_claim" vs "source_drift" etc.
CITATIONS_ISSUE_CATEGORIES = {
    "unsupported_claim",
    "source_drift",
    "ignored_blocking_currency",
    "missing_in_sources_section",
    "source_pack_mismatch",
    "unverified_against_source",
    "length_overflow_disclosure",
}
COUNTERARGUMENTS_ATTACK_VECTORS = {
    "contrary_authority",
    "overconfidence",
    "missing_fact",
    "weak_application",
    "understated_risk",
}

# Soft limits on issue/suggestion text. Beyond these, emit a warning (not error)
# so the validator does not block the pipeline but the user can see runaway
# verbose reviewer output before it floods the writer's context.
MAX_ISSUE_CHARS = 1500
MAX_SUGGESTION_CHARS = 800


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
        base["attack_vector"] = "understated_risk"
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


def validate_payload(payload: Any, reviewer: str, iteration: int) -> tuple[list[str], list[str]]:
    """Validate a reviewer payload.

    Returns (errors, warnings). Errors block the pipeline; warnings are
    surfaced in the validator output but do not fail validation.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["top-level JSON value must be an object"], warnings

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

    # Per-reviewer category enforcement + length warnings on blocking_issues.
    if isinstance(blocking, list):
        for idx, item in enumerate(blocking):
            if not isinstance(item, dict):
                errors.append(f"blocking_issues[{idx}] must be an object")
                continue

            if reviewer == "citations":
                category = item.get("issue_category")
                if category not in CITATIONS_ISSUE_CATEGORIES:
                    errors.append(
                        f"blocking_issues[{idx}].issue_category must be one of {sorted(CITATIONS_ISSUE_CATEGORIES)}; got {category!r}"
                    )
            elif reviewer == "counterarguments":
                vector = item.get("attack_vector")
                if vector not in COUNTERARGUMENTS_ATTACK_VECTORS:
                    errors.append(
                        f"blocking_issues[{idx}].attack_vector must be one of {sorted(COUNTERARGUMENTS_ATTACK_VECTORS)}; got {vector!r}"
                    )

            issue_text = item.get("issue", "")
            if isinstance(issue_text, str) and len(issue_text) > MAX_ISSUE_CHARS:
                warnings.append(
                    f"blocking_issues[{idx}].issue exceeds {MAX_ISSUE_CHARS} chars ({len(issue_text)}); writer context may be flooded"
                )
            suggestion_text = item.get("suggestion", "")
            if isinstance(suggestion_text, str) and len(suggestion_text) > MAX_SUGGESTION_CHARS:
                warnings.append(
                    f"blocking_issues[{idx}].suggestion exceeds {MAX_SUGGESTION_CHARS} chars ({len(suggestion_text)})"
                )

    return errors, warnings


def validate_file(path: Path, reviewer: str, iteration: int) -> tuple[bool, list[str], list[str]]:
    """Validate a reviewer JSON file.

    Returns (ok, errors, warnings). `ok` is True iff errors is empty.
    """
    if not path.exists():
        return False, ["file missing"], []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return False, [f"invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"], []
    except OSError as exc:
        return False, [f"cannot read file: {exc}"], []
    errors, warnings = validate_payload(payload, reviewer, iteration)
    return not errors, errors, warnings


def resolve_reviewers(workdir: Path, explicit: str | None) -> tuple[list[str], str]:
    """Resolve the active reviewer set.

    Priority: --reviewers flag > state.json.config.reviewer_list > all five.
    Returns (reviewer_list, source_label).
    """
    if explicit:
        names = [r.strip() for r in explicit.split(",") if r.strip()]
        unknown = [r for r in names if r not in ALL_REVIEWERS]
        if unknown:
            raise SystemExit(
                f"unknown reviewer kind(s): {unknown}. Valid: {list(ALL_REVIEWERS)}"
            )
        return names, "cli --reviewers"

    state_path = workdir / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8-sig"))
            cfg_list = (state.get("config") or {}).get("reviewer_list")
            if isinstance(cfg_list, list) and cfg_list:
                unknown = [r for r in cfg_list if r not in ALL_REVIEWERS]
                if unknown:
                    raise SystemExit(
                        f"state.json.config.reviewer_list contains unknown reviewer "
                        f"kind(s): {unknown}. Valid: {list(ALL_REVIEWERS)}"
                    )
                return list(cfg_list), "state.json.config.reviewer_list"
        except (json.JSONDecodeError, OSError):
            pass

    return list(ALL_REVIEWERS), "default (all 5)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate revision reviewer JSON files.")
    parser.add_argument("--workdir", required=True, help="Task working directory")
    parser.add_argument("--iteration", required=True, type=int, help="Draft iteration number")
    parser.add_argument(
        "--reviewers",
        help="Comma-separated reviewer kinds to validate (overrides state.json.config.reviewer_list). "
             "Valid kinds: logic, clarity, style, citations, counterarguments.",
    )
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

    reviewers, source = resolve_reviewers(workdir, args.reviewers)

    invalid: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    for reviewer in reviewers:
        path = reviewer_path(workdir, args.iteration, reviewer)
        ok, errors, warnings = validate_file(path, reviewer, args.iteration)
        if warnings:
            all_warnings.append({"reviewer": reviewer, "path": str(path), "warnings": warnings})
        if ok:
            entry: dict[str, Any] = {"reviewer": reviewer, "path": str(path)}
            if warnings:
                entry["warnings"] = warnings
            valid.append(entry)
            continue

        invalid.append({"reviewer": reviewer, "path": str(path), "errors": errors})
        if args.write_failure_stubs:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(path, failure_stub(reviewer, args.iteration, "; ".join(errors)))

    result = {
        "ok": not invalid,
        "iteration": args.iteration,
        "reviewer_set": reviewers,
        "reviewer_set_source": source,
        "valid_reviewers": valid,
        "invalid_reviewers": invalid,
        "warnings": all_warnings,
        "failure_stubs_written": bool(args.write_failure_stubs and invalid),
    }
    print(json.dumps(result, indent=2))
    return 0 if not invalid else 1


if __name__ == "__main__":
    sys.exit(main())
