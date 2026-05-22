#!/usr/bin/env python3
"""Validate legal-memo-writer state.json.

Phase-aware: enforces only the fields that must exist by the current phase.
The canonical schema is `skills/memo/state-schema.md` — see that file for the
field ownership table. Field categories:

- ALWAYS required (write-once at Phase 1): task_id, user_query, created_at,
  language, work_dir, rel_work_dir, output_folder, intake, plan_approval,
  current_phase, current_iteration, max_plan_edit_iterations,
  max_intake_iterations, exit_threshold_score, iterations, attempts,
  remaining_blocking_issues, events_path, mode, config, heartbeat_choice,
  revision_gate_choice, client_readiness_gate_choice, polish_gate_choice,
  fallback_banners, classification, current_draft_path, client_readiness,
  final_status, final_docx_path.

- Required to be POPULATED (non-null / non-empty config) from `planning` onward
  (after Phase 1.5 mode pick): mode, config (with required shape keys).

- Required to be set from `drafting` onward: current_draft_path.

- Required to be set from `export` onward: final_status (and final_docx_path
  after Phase 11 export step).

No top-level `max_iterations` — single source of truth is
`state.config.max_iterations`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PHASES_ORDERED = [
    "intake_preliminary_research",
    "intake_questions_pending",
    "mode_pick_pending",
    "planning",
    "plan_approval_pending",
    "research",
    "research_sufficiency",
    "currency_check",
    "source_pack",
    "source_review_pending",  # v0.0.43+; replaces heartbeat_pending
    "heartbeat_pending",      # legacy v0.0.42-and-earlier; continue/SKILL.md migrates to source_review_pending on resume
    "drafting",
    "revision_loop",
    "client_readiness",
    "export",
    "done",
    "failed",
    "cancelled_by_user",
]
PHASES = set(PHASES_ORDERED)
PHASE_INDEX = {p: i for i, p in enumerate(PHASES_ORDERED)}

LANGUAGES = {"en"}

ALWAYS_REQUIRED = [
    "task_id",
    "user_query",
    "created_at",
    "language",
    "work_dir",
    "rel_work_dir",
    "output_folder",
    "mode",
    "config",
    # "heartbeat_choice" was removed from ALWAYS_REQUIRED in v0.0.44 — the field
    # is deprecated (Phase 7.5 became the text-parsed source-review checkpoint
    # in v0.0.43; full/summary semantics removed). Legacy v0.0.42-and-earlier
    # tasks may still carry it; if present, it is validated against
    # ACCEPTED_HEARTBEAT_CHOICES below (read-time tolerance), but new tasks
    # never write it.
    "revision_gate_choice",
    "client_readiness_gate_choice",
    "polish_gate_choice",
    "fallback_banners",
    "classification",
    "intake",
    "plan_approval",
    "current_phase",
    "current_iteration",
    "max_plan_edit_iterations",
    "max_intake_iterations",
    "exit_threshold_score",
    "current_draft_path",
    "iterations",
    "client_readiness",
    "final_status",
    "final_docx_path",
    "attempts",
    "remaining_blocking_issues",
    "events_path",
]

# After Phase 1.5 mode pick, these config keys must be present and well-typed.
# v0.0.45: simplified from the 7-key Quick/Standard/Deep schema. `template_constraint`
# (object with forced/bounded/open semantics) and `targeted_followup_forced`
# (Deep-mode override of sufficiency verdict) were removed; `template_id`
# replaces template_constraint as a direct mode→template binding.
CONFIG_SHAPE_KEYS = (
    "researcher_set",
    "reviewer_list",
    "max_iterations",
    "client_polish_enabled",
    "max_client_polish",
    "template_id",
)
VALID_REVIEWERS = {"logic", "clarity", "style", "citations", "counterarguments"}
VALID_RESEARCHERS = {"statutory", "case-law", "doctrinal"}
VALID_TEMPLATE_IDS = {"executive-brief", "classical-memo"}
VALID_HEARTBEAT_CHOICES = {"pending", "continue_full", "research_summary_only"}
# Pre-0.0.39 tasks may have heartbeat_choice="switch_to_quick" persisted; the
# active set above no longer includes it because Phase 8 branching never
# differentiated it from continue_full. The validator tolerates legacy values
# so that resuming such a task does not fail validation BEFORE continue/SKILL.md
# can normalize the value (heartbeat_pending branch rewrites
# switch_to_quick → continue_full on resume). Normalizers MUST run before any
# write — the validator only tolerates legacy values during read-time.
DEPRECATED_HEARTBEAT_CHOICES = {"switch_to_quick"}
ACCEPTED_HEARTBEAT_CHOICES = VALID_HEARTBEAT_CHOICES | DEPRECATED_HEARTBEAT_CHOICES
VALID_MODES = {"brief", "full"}

# Mode → required reviewer_list mapping (canonical from skills/memo/references/modes.md).
# Brief mode runs 3 reviewers; Full runs all 5.
BRIEF_REVIEWERS = {"logic", "citations", "counterarguments"}
FULL_REVIEWERS = {"logic", "clarity", "style", "citations", "counterarguments"}

# Mode → required researcher_set (candidate set; doctrinal in Full is
# conditional on plan.doctrine_required at dispatch time — that conditional
# filtering is reflected in `state.json.dispatched_researchers`, not in the
# candidate `config.researcher_set`).
MODE_RESEARCHER_SET = {
    "brief": {"statutory"},
    "full": {"statutory", "case-law", "doctrinal"},
}

# Mode → required template_id (canonical from modes.md).
# Brief always uses executive-brief; Full always uses classical-memo.
MODE_TEMPLATE_ID = {
    "brief": "executive-brief",
    "full": "classical-memo",
}

# Canonical per-mode config values (also from modes.md). Cross-field validation
# enforces these so misconfigured tasks (e.g. Brief with max_iterations=99,
# or Full with client_polish_enabled=false) fail validation.
MODE_CANONICAL_CONFIG = {
    "brief": {
        "max_iterations": 1,
        "client_polish_enabled": False,
        "max_client_polish": 0,
    },
    "full": {
        "max_iterations": 3,
        "client_polish_enabled": True,
        "max_client_polish": 1,
    },
}

# Terminal error phases — current_phase in this set means the task ended
# (was cancelled or failed) and phase-aware "by phase X you must have Y"
# checks do not apply. Only the always-required shape matters.
TERMINAL_ERROR_PHASES = {"failed", "cancelled_by_user"}

# Canonical final_status enum per state-schema.md. The four
# `<verb>_on_v<N>` variants take an integer iteration suffix; the two
# `fallback_*` variants are literal strings.
FINAL_STATUS_REGEX = re.compile(
    r"^("
    r"approved_on_v\d+"
    r"|forced_exit_on_v\d+_with_remaining_issues"
    r"|manual_review_required_on_v\d+"
    r"|accepted_early_on_v\d+"
    r"|fallback_research_summary_delivered"
    r"|fallback_summary_delivered"
    r")$"
)

# research-summary-only is a heartbeat-driven escape valve — the
# classifier never picks it. Legacy v0.0.42/v0.0.43 tasks could land on it via
# Phase 8 branch A when heartbeat_choice == "research_summary_only".
# In v0.0.44+ new tasks never set this value. The validator honours the
# carve-out so legacy tasks resume cleanly.
HEARTBEAT_TEMPLATE_OVERRIDE = "research-summary-only"


def phase_at_or_after(state_phase: str, target_phase: str) -> bool:
    if state_phase not in PHASE_INDEX or target_phase not in PHASE_INDEX:
        return False
    return PHASE_INDEX[state_phase] >= PHASE_INDEX[target_phase]


def validate_config_shape(config: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["config must be an object after Phase 1.5"]
    for key in CONFIG_SHAPE_KEYS:
        if key not in config:
            errors.append(f"config.{key} missing (required after Phase 1.5)")

    reviewer_list = config.get("reviewer_list")
    if isinstance(reviewer_list, list):
        unknown = [r for r in reviewer_list if r not in VALID_REVIEWERS]
        if unknown:
            errors.append(f"config.reviewer_list contains unknown kinds: {unknown}; valid: {sorted(VALID_REVIEWERS)}")
        if not reviewer_list:
            errors.append("config.reviewer_list cannot be empty")
    elif reviewer_list is not None:
        errors.append("config.reviewer_list must be a list")

    researcher_set = config.get("researcher_set")
    if isinstance(researcher_set, list):
        unknown = [r for r in researcher_set if r not in VALID_RESEARCHERS]
        if unknown:
            errors.append(f"config.researcher_set contains unknown kinds: {unknown}; valid: {sorted(VALID_RESEARCHERS)}")
    elif researcher_set is not None:
        errors.append("config.researcher_set must be a list")

    max_iter = config.get("max_iterations")
    if not isinstance(max_iter, int) or max_iter < 1:
        errors.append("config.max_iterations must be a positive integer")

    template_id = config.get("template_id")
    if template_id is not None and template_id not in VALID_TEMPLATE_IDS:
        errors.append(
            f"config.template_id is invalid: {template_id!r}; must be one of {sorted(VALID_TEMPLATE_IDS)}"
        )

    return errors


def validate_state(state: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["top-level JSON value must be an object"]

    for key in ALWAYS_REQUIRED:
        if key not in state:
            errors.append(f"missing key: {key}")

    # Reject the deprecated top-level max_iterations to keep the
    # single-source-of-truth invariant.
    if "max_iterations" in state:
        errors.append(
            "top-level max_iterations is deprecated; the only source of truth is "
            "state.config.max_iterations (mode-dependent). Remove the top-level field."
        )

    if state.get("language") not in LANGUAGES:
        errors.append("language must be en")

    current_phase = state.get("current_phase")
    if current_phase not in PHASES:
        errors.append(f"current_phase is invalid: {current_phase!r}")

    current_iteration = state.get("current_iteration")
    if not isinstance(current_iteration, int) or current_iteration < 0:
        errors.append("current_iteration must be a non-negative integer")

    mode = state.get("mode")
    if mode is not None and mode not in VALID_MODES:
        errors.append(
            f"mode is invalid: {mode!r}; must be null or one of {sorted(VALID_MODES)}. "
            "Legacy values 'quick'|'standard'|'deep' are no longer accepted; "
            "they must be migrated to brief|full via continue/SKILL.md on resume."
        )

    # v0.0.44: heartbeat_choice is OPTIONAL. New tasks don't write it (the
    # Phase 7.5 heartbeat gate was replaced by the source-review checkpoint in
    # v0.0.43 and the full/summary semantics dropped). When the field is
    # absent, no validation fires. When present (legacy tasks), it must still
    # be one of the accepted values so continue/SKILL.md can normalize it on
    # resume.
    if "heartbeat_choice" in state:
        heartbeat_choice = state["heartbeat_choice"]
        if heartbeat_choice not in ACCEPTED_HEARTBEAT_CHOICES:
            errors.append(
                f"heartbeat_choice is invalid: {heartbeat_choice!r}; must be one of "
                f"{sorted(VALID_HEARTBEAT_CHOICES)} "
                f"(legacy {sorted(DEPRECATED_HEARTBEAT_CHOICES)} tolerated for "
                "pre-0.0.39 tasks pending normalization). New tasks (v0.0.44+) "
                "should not write this field at all."
            )

    if not isinstance(state.get("fallback_banners"), list):
        errors.append("fallback_banners must be a list (use [] when empty)")

    # Terminal error states: skip ALL phase-aware checks. A task cancelled
    # before Phase 1.5 has mode=null, config={}, no current_draft_path, etc. —
    # requiring "by phase X you must have Y" against the terminal phase
    # position in PHASES_ORDERED would fail the cancellation incorrectly.
    if isinstance(current_phase, str) and current_phase in TERMINAL_ERROR_PHASES:
        return errors

    # Phase-aware: config must be populated from `planning` onward (after Phase 1.5)
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "planning"):
        if mode is None:
            errors.append(f"mode must be set by phase '{current_phase}' (post Phase 1.5)")
        errors.extend(validate_config_shape(state.get("config")))
        # Cross-field: mode ↔ reviewer_list canonical mapping
        cfg = state.get("config")
        if isinstance(cfg, dict) and mode in VALID_MODES:
            reviewer_list = cfg.get("reviewer_list")
            if isinstance(reviewer_list, list):
                rset = set(reviewer_list)
                if mode == "brief" and rset != BRIEF_REVIEWERS:
                    errors.append(
                        f"config.reviewer_list for mode=brief must be exactly {sorted(BRIEF_REVIEWERS)}; got {sorted(rset)}"
                    )
                elif mode == "full" and rset != FULL_REVIEWERS:
                    errors.append(
                        f"config.reviewer_list for mode=full must be exactly {sorted(FULL_REVIEWERS)}; got {sorted(rset)}"
                    )
            # Cross-field: mode ↔ canonical config values (max_iterations,
            # client_polish_enabled, max_client_polish)
            canonical = MODE_CANONICAL_CONFIG.get(mode)
            if canonical is not None:
                for key, expected in canonical.items():
                    actual = cfg.get(key)
                    if actual != expected:
                        errors.append(
                            f"config.{key} for mode={mode} must be {expected!r}; got {actual!r} (per modes.md canonical mapping)"
                        )

            # Cross-field: mode ↔ canonical researcher_set (candidate set).
            expected_researchers = MODE_RESEARCHER_SET.get(mode)
            actual_researcher_set = cfg.get("researcher_set")
            if expected_researchers is not None and isinstance(actual_researcher_set, list):
                actual_researchers = set(actual_researcher_set)
                if actual_researchers != expected_researchers:
                    errors.append(
                        f"config.researcher_set for mode={mode} must be exactly {sorted(expected_researchers)}; "
                        f"got {sorted(actual_researchers)} (per modes.md canonical mapping)"
                    )

            # Cross-field: mode ↔ canonical template_id
            expected_tid = MODE_TEMPLATE_ID.get(mode)
            actual_tid = cfg.get("template_id")
            if expected_tid is not None and actual_tid != expected_tid:
                errors.append(
                    f"config.template_id for mode={mode} must be {expected_tid!r}; "
                    f"got {actual_tid!r} (per modes.md canonical mapping)"
                )

            # Cross-field: classification.selected_template_id (if set) must
            # equal config.template_id. This catches a classifier that ignored
            # the direct mode→template binding.
            #
            # Heartbeat carve-out: legacy v0.0.42/0.0.43 tasks could land on
            # `selected_template_id == "research-summary-only"` when the user
            # picked "Research summary only" at the heartbeat. The validator
            # accepts that combination ONLY when state.heartbeat_choice ==
            # "research_summary_only" (legacy carve-out). New tasks never set
            # this template.
            classification = state.get("classification")
            heartbeat_choice = state.get("heartbeat_choice")
            if isinstance(classification, dict):
                selected = classification.get("selected_template_id")
                if selected == HEARTBEAT_TEMPLATE_OVERRIDE:
                    if heartbeat_choice != "research_summary_only":
                        errors.append(
                            f"classification.selected_template_id={selected!r} is only "
                            "valid on legacy v0.0.42/0.0.43 tasks where "
                            "state.heartbeat_choice=='research_summary_only' "
                            "(heartbeat-driven override per legacy always-deliver.md Phase 7→8 "
                            f"row); got heartbeat_choice={heartbeat_choice!r}. New tasks "
                            "should not set this template — the research-summary mode was "
                            "removed in v0.0.44."
                        )
                elif selected is not None and actual_tid is not None and selected != actual_tid:
                    errors.append(
                        f"classification.selected_template_id={selected!r} does not match "
                        f"config.template_id={actual_tid!r} "
                        "(per modes.md the classifier copies template_id from config — "
                        "they must agree)"
                    )

    # Phase-aware: current_draft_path must be set from `drafting` onward
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "drafting"):
        cdp = state.get("current_draft_path")
        if not isinstance(cdp, str) or not cdp:
            errors.append(f"current_draft_path must be set by phase '{current_phase}'")

    # Phase-aware: current_iteration must be >= 1 in revision_loop
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "revision_loop"):
        if isinstance(current_iteration, int) and current_iteration < 1:
            errors.append("current_iteration must be >= 1 once in revision_loop")
        cfg = state.get("config")
        if isinstance(cfg, dict):
            max_iter = cfg.get("max_iterations")
            if isinstance(current_iteration, int) and isinstance(max_iter, int) and current_iteration > max_iter:
                errors.append("current_iteration cannot exceed config.max_iterations")

    # Phase-aware: final_status must be set by `export` onward
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "export"):
        if state.get("final_status") is None:
            errors.append(f"final_status must be set by phase '{current_phase}'")

    # Phase-aware: final_docx_path must be a non-empty string by `done`,
    # AND the file must actually exist on disk (per always-deliver.md the user
    # never reaches `done` without a deliverable, even if Phase 11 fell back to
    # markdown). Path must be absolute (per state-schema.md final_docx_path
    # contract; relative paths cannot be reliably re-resolved from validator CWD).
    if current_phase == "done":
        fdp = state.get("final_docx_path")
        if not isinstance(fdp, str) or not fdp:
            errors.append("final_docx_path must be a non-empty string in phase 'done'")
        elif not Path(fdp).is_absolute():
            errors.append(
                f"final_docx_path must be an absolute path in phase 'done'; got {fdp!r} "
                "(per state-schema.md — work_dir-rooted absolute)"
            )
        elif not Path(fdp).is_file():
            errors.append(
                f"final_docx_path file does not exist on disk: {fdp!r} "
                "(per always-deliver.md the user must always see a real artifact)"
            )

    # Phase-aware: dispatched_researchers must be set from research_sufficiency onward
    # (memo Phase 5 writes it after the parallel Agent dispatch). It must be a
    # subset of config.researcher_set.
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "research_sufficiency"):
        dispatched = state.get("dispatched_researchers")
        if not isinstance(dispatched, list):
            errors.append(
                f"dispatched_researchers must be a list by phase '{current_phase}' "
                "(memo Phase 5 writes it after the parallel Agent dispatch)"
            )
        else:
            unknown_dispatched = [r for r in dispatched if r not in VALID_RESEARCHERS]
            if unknown_dispatched:
                errors.append(
                    f"dispatched_researchers contains unknown kinds: {unknown_dispatched}; "
                    f"valid: {sorted(VALID_RESEARCHERS)}"
                )
            cfg = state.get("config")
            if isinstance(cfg, dict):
                candidate = cfg.get("researcher_set")
                if isinstance(candidate, list):
                    extras = set(dispatched) - set(candidate)
                    if extras:
                        errors.append(
                            f"dispatched_researchers={sorted(set(dispatched))} contains researchers "
                            f"not in config.researcher_set={sorted(set(candidate))}: {sorted(extras)}"
                        )

    # Phase-aware: research-sufficiency.json must exist by source_pack onward
    # (source-pack-builder consumes it; absence indicates the sufficiency gate was skipped).
    # We check existence relative to work_dir if work_dir is a valid string.
    if isinstance(current_phase, str) and phase_at_or_after(current_phase, "source_pack"):
        work_dir = state.get("work_dir")
        if isinstance(work_dir, str) and work_dir:
            sufficiency_path = Path(work_dir) / "research" / "research-sufficiency.json"
            if not sufficiency_path.exists():
                errors.append(
                    f"research/research-sufficiency.json must exist by phase '{current_phase}' "
                    "(produced by research-sufficiency-reviewer in Phase 6)"
                )

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
            # sufficiency_regate is bounded at max 1 — Phase 6.5 re-gates the
            # sufficiency reviewer at most once when currency invalidates sources.
            regate = attempts.get("sufficiency_regate", 0)
            if not isinstance(regate, int) or regate < 0:
                errors.append("attempts.sufficiency_regate must be a non-negative integer")
            elif regate > 1:
                errors.append(
                    f"attempts.sufficiency_regate is bounded to 1; got {regate} "
                    "(memo Phase 6.5 re-gates sufficiency at most once after currency invalidation)"
                )
            # research_followup is bounded at max 1 — memo Phase 6 allows at
            # most one targeted follow-up cycle (see continue/SKILL.md
            # research_sufficiency branch). The orchestrator increments to 1
            # on the first follow-up; >= 1 means no further re-dispatch.
            followup = attempts.get("research_followup", 0)
            if isinstance(followup, int) and followup > 1:
                errors.append(
                    f"attempts.research_followup is bounded to 1; got {followup} "
                    "(memo Phase 6 allows at most one targeted follow-up cycle)"
                )
            # client_readiness_polish ≤ config.max_client_polish (mode-dependent
            # cap: Brief=0, Full=1 — per modes.md). Validator skips this check
            # before phase `planning` because config is still {} there.
            polish = attempts.get("client_readiness_polish", 0)
            cfg_for_polish = state.get("config")
            if (
                isinstance(cfg_for_polish, dict)
                and isinstance(polish, int)
                and polish > 0
            ):
                max_polish = cfg_for_polish.get("max_client_polish")
                if isinstance(max_polish, int) and polish > max_polish:
                    errors.append(
                        f"attempts.client_readiness_polish={polish} exceeds "
                        f"config.max_client_polish={max_polish} "
                        "(mode-dependent cap per modes.md)"
                    )
            retry_budget = attempts.get("reviewer_json_retry", {})
            if not isinstance(retry_budget, dict):
                errors.append("attempts.reviewer_json_retry must be an object")
            elif not all(isinstance(value, int) and value >= 0 for value in retry_budget.values()):
                errors.append("attempts.reviewer_json_retry values must be non-negative integers")
            else:
                # Per kind, continue/SKILL.md revision_loop branch allows
                # one re-dispatch + one --write-failure-stubs pass, so the
                # per-kind counter never exceeds 2 in normal operation.
                for kind, value in retry_budget.items():
                    if isinstance(value, int) and value > 2:
                        errors.append(
                            f"attempts.reviewer_json_retry[{kind!r}]={value} exceeds 2 "
                            "(continue/SKILL.md allows one retry + one failure-stub pass)"
                        )

    remaining = state.get("remaining_blocking_issues")
    if remaining is not None and not isinstance(remaining, list):
        errors.append("remaining_blocking_issues must be a list when present")

    final_status = state.get("final_status")
    if final_status is not None:
        if not isinstance(final_status, str):
            errors.append("final_status must be null or string")
        elif not FINAL_STATUS_REGEX.match(final_status):
            errors.append(
                f"final_status={final_status!r} is not in the canonical enum "
                "(per state-schema.md): expected one of approved_on_v<N>, "
                "forced_exit_on_v<N>_with_remaining_issues, "
                "manual_review_required_on_v<N>, accepted_early_on_v<N>, "
                "fallback_research_summary_delivered, "
                "or fallback_summary_delivered"
            )

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
