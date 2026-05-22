"""Smoke tests for scripts/validate_state.py.

Run from the plugin root:
    python3 -m unittest scripts.tests.test_validate_state

These tests target the behaviour the pipeline depends on:
- Phase 1 initial state passes.
- Phase-aware required fields catch missing mode/config after Phase 1.5.
- Top-level max_iterations is rejected (single source of truth is config.max_iterations).
- counterargument(s) plural enforcement in config.reviewer_list.
- research_summary_only heartbeat_choice value is accepted.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate_state.py"


def run_validator(state: dict, *, create_sufficiency: bool = False) -> tuple[int, dict]:
    """Run validate_state.py against a temporary state.json.

    If create_sufficiency=True, also creates an empty research/research-sufficiency.json
    inside the tempdir and points state.work_dir at the tempdir. This satisfies the
    phase-aware existence check for phases ≥ source_pack without requiring tests to
    juggle filesystem state manually.
    """
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        if create_sufficiency:
            (td_path / "research").mkdir(parents=True, exist_ok=True)
            (td_path / "research" / "research-sufficiency.json").write_text(
                json.dumps({"reviewer": "research_sufficiency", "overall_verdict": "sufficient"}),
                encoding="utf-8",
            )
            state = {**state, "work_dir": str(td_path)}
        p = td_path / "state.json"
        p.write_text(json.dumps(state), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--state", str(p)],
            capture_output=True,
            text=True,
        )
        return result.returncode, json.loads(result.stdout) if result.stdout else {}


def phase1_initial_state() -> dict:
    """Mirror of the Phase 1 initial state.json template in skills/memo/SKILL.md."""
    return {
        "task_id": "memo-test-001",
        "user_query": "test",
        "created_at": "2026-05-20T00:00:00Z",
        "language": "en",
        "work_dir": "/tmp/test",
        "rel_work_dir": "outputs/test",
        "output_folder": "/tmp",
        "mode": None,
        "config": {},
        "heartbeat_choice": "pending",
        "revision_gate_choice": None,
        "client_readiness_gate_choice": None,
        "polish_gate_choice": None,
        "fallback_banners": [],
        "classification": None,
        "intake": {
            "status": "preliminary_research",
            "questions_iteration": 1,
            "user_response": None,
            "assumptions_accepted": False,
        },
        "plan_approval": {"status": "not_started", "iterations": [], "final_plan_iteration": None},
        "current_phase": "intake_preliminary_research",
        "current_iteration": 0,
        "max_plan_edit_iterations": 5,
        "max_intake_iterations": 2,
        "exit_threshold_score": 85,
        "current_draft_path": None,
        "iterations": [],
        "client_readiness": None,
        "final_status": None,
        "final_docx_path": None,
        "attempts": {
            "research_followup": 0,
            "research_followup_pending_review": False,
            "client_readiness_polish": 0,
            "client_readiness_polish_pending_review": False,
            "reviewer_json_retry": {},
        },
        "remaining_blocking_issues": [],
        "events_path": "events.jsonl",
    }


def full_mode_config() -> dict:
    return {
        "researcher_set": ["statutory", "case-law", "doctrinal"],
        "reviewer_list": ["logic", "clarity", "style", "citations", "counterarguments"],
        "max_iterations": 3,
        "client_polish_enabled": True,
        "max_client_polish": 1,
        "template_id": "classical-memo",
    }


def brief_mode_config() -> dict:
    return {
        "researcher_set": ["statutory"],
        "reviewer_list": ["logic", "citations", "counterarguments"],
        "max_iterations": 1,
        "client_polish_enabled": False,
        "max_client_polish": 0,
        "template_id": "executive-brief",
    }


class ValidateStateTests(unittest.TestCase):

    def test_phase1_initial_state_passes(self):
        code, out = run_validator(phase1_initial_state())
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_empty_state_fails_with_missing_keys(self):
        code, out = run_validator({})
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertIn("missing key: task_id", out["errors"])
        self.assertIn("missing key: mode", out["errors"])
        self.assertIn("missing key: config", out["errors"])
        self.assertIn("missing key: fallback_banners", out["errors"])
        # v0.0.44: heartbeat_choice is no longer ALWAYS_REQUIRED (deprecated
        # field, optional on read). The validator does NOT report it as a
        # missing key.
        self.assertNotIn("missing key: heartbeat_choice", out["errors"])

    def test_top_level_max_iterations_rejected(self):
        s = phase1_initial_state()
        s["max_iterations"] = 3
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertTrue(any("top-level max_iterations is deprecated" in e for e in out["errors"]))

    def test_revision_loop_without_mode_config_fails(self):
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertIn("mode must be set by phase 'revision_loop' (post Phase 1.5)", out["errors"])

    def test_revision_loop_full_mode_passes(self):
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_revision_loop_brief_mode_passes(self):
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        s["mode"] = "brief"
        s["config"] = brief_mode_config()
        s["dispatched_researchers"] = ["statutory"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_revision_loop_current_iteration_exceeds_max(self):
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 4
        s["current_draft_path"] = "drafts/v4.md"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertIn("current_iteration cannot exceed config.max_iterations", out["errors"])

    def test_revision_loop_current_iteration_at_max_passes(self):
        """Boundary documentation: current_iteration == config.max_iterations
        is valid (it's the LAST iteration). The next-iteration gate (6b in
        memo Phase 9) uses strict `current_iteration < max_iterations`, so once
        we hit the boundary the mediator emits `forced_exit_on_v<N>` instead of
        offering "Continue iter N+1". This test pins that boundary so a future
        edit that accidentally writes `>=` (instead of `>`) in the validator
        rejection branch is caught."""
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 3  # at the Full mode cap
        s["current_draft_path"] = "drafts/v3.md"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_singular_counterargument_in_reviewer_list_rejected(self):
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        s["mode"] = "full"
        cfg = full_mode_config()
        cfg["reviewer_list"] = ["logic", "clarity", "style", "citations", "counterargument"]
        s["config"] = cfg
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("reviewer_list contains unknown kinds: ['counterargument']" in e for e in out["errors"]),
            msg=out,
        )

    def test_heartbeat_choice_research_summary_only_accepted(self):
        s = phase1_initial_state()
        s["heartbeat_choice"] = "research_summary_only"
        code, out = run_validator(s)
        self.assertEqual(code, 0, msg=out)

    def test_heartbeat_choice_invalid_rejected(self):
        s = phase1_initial_state()
        s["heartbeat_choice"] = "skip_everything"
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(any("heartbeat_choice is invalid" in e for e in out["errors"]))

    def test_heartbeat_choice_legacy_switch_to_quick_tolerated(self):
        """Pre-0.0.39 tasks may persist heartbeat_choice='switch_to_quick'.
        The active enum no longer includes it, but the validator must
        tolerate it so /continue can resume the task and normalize the
        value to 'continue_full' on the heartbeat_pending branch. The
        normalization itself is in continue/SKILL.md, not the validator."""
        s = phase1_initial_state()
        s["heartbeat_choice"] = "switch_to_quick"
        code, out = run_validator(s)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_legacy_mode_quick_rejected(self):
        """Pre-2-mode tasks have mode='quick'/'standard'/'deep'. The validator
        no longer accepts these — continue/SKILL.md migrates them to brief/full
        on resume BEFORE validation runs. Catching a legacy value here means a
        task slipped past the migration."""
        s = phase1_initial_state()
        s["mode"] = "quick"
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(any("mode is invalid: 'quick'" in e for e in out["errors"]))

    def test_export_phase_requires_final_status(self):
        s = phase1_initial_state()
        s["current_phase"] = "export"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["current_draft_path"] = "drafts/v1.md"
        s["current_iteration"] = 1
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(any("final_status must be set" in e for e in out["errors"]))

    # Wave 3 — terminal-phase bypass (issue 4)

    def test_cancelled_before_mode_pick_passes(self):
        """A task cancelled before Phase 1.5 mode pick has mode=null, config={},
        no current_draft_path, no final_status. Without terminal-phase bypass,
        the validator would require mode/config/etc because cancelled_by_user
        is positioned after `done` in PHASES_ORDERED."""
        s = phase1_initial_state()
        s["current_phase"] = "cancelled_by_user"
        code, out = run_validator(s)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_failed_phase_skips_phase_aware_checks(self):
        """Same as above for `failed` terminal state."""
        s = phase1_initial_state()
        s["current_phase"] = "failed"
        code, out = run_validator(s)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    # Wave 3 — mode↔config integrity (issue 5)

    def test_brief_mode_max_iterations_99_rejected(self):
        """Brief mode with non-canonical max_iterations=99 must fail; modes.md
        is authoritative for the per-mode config values."""
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        s["mode"] = "brief"
        cfg = brief_mode_config()
        cfg["max_iterations"] = 99
        s["config"] = cfg
        s["dispatched_researchers"] = ["statutory"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("config.max_iterations for mode=brief must be 1" in e for e in out["errors"]),
            msg=out,
        )

    def test_brief_mode_client_polish_enabled_rejected(self):
        """Brief mode with client_polish_enabled=true must fail."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        s["mode"] = "brief"
        cfg = brief_mode_config()
        cfg["client_polish_enabled"] = True
        s["config"] = cfg
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("config.client_polish_enabled for mode=brief must be False" in e for e in out["errors"]),
            msg=out,
        )

    def test_full_mode_correct_config_passes(self):
        """Full mode with the canonical config — 5 reviewers, 3 iterations,
        1 polish pass, classical-memo template — must pass."""
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["current_iteration"] = 1
        s["current_draft_path"] = "drafts/v1.md"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_done_without_final_docx_path_rejected(self):
        """current_phase=done with final_docx_path=null must fail. Done is the
        terminal success state and always implies a real artifact exists."""
        s = phase1_initial_state()
        s["current_phase"] = "done"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["current_draft_path"] = "drafts/v3.md"
        s["current_iteration"] = 3
        s["final_status"] = "approved_on_v3"
        s["final_docx_path"] = None
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("final_docx_path must be a non-empty string in phase 'done'" in e for e in out["errors"]),
            msg=out,
        )

    # Wave 4 — Fix 1 (mode_pick_pending), Fix 3 (researcher_set / template_id
    # canonical mappings + selected_template == config.template_id), Fix 6
    # (dispatched_researchers subset of candidate), Fix 8 (final_docx_path
    # absolute + on-disk existence).

    def test_mode_pick_pending_with_null_mode_passes(self):
        """mode_pick_pending is the hard gate for Phase 1.5 mode choice. By
        contract `mode` is null in this phase — validator must NOT require it
        until `planning` onward."""
        s = phase1_initial_state()
        s["current_phase"] = "mode_pick_pending"
        # mode is null; config is {} (visualize precheck may have populated keys, but not required)
        code, out = run_validator(s)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_planning_with_null_mode_rejected(self):
        """Once current_phase advances to `planning`, `mode` MUST be set. This
        is the guard against /continue jumping past Phase 1.5."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        # mode remains null
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("mode must be set by phase 'planning'" in e for e in out["errors"]),
            msg=out,
        )

    def test_brief_mode_wrong_researcher_set_rejected(self):
        """Brief mode with researcher_set including case-law must fail; modes.md
        canonical mapping requires exactly ['statutory'] for Brief."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        s["mode"] = "brief"
        cfg = brief_mode_config()
        cfg["researcher_set"] = ["statutory", "case-law"]
        s["config"] = cfg
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("config.researcher_set for mode=brief must be exactly" in e for e in out["errors"]),
            msg=out,
        )

    def test_full_mode_wrong_template_id_rejected(self):
        """Full mode must carry template_id='classical-memo'. A mismatch is a
        misconfiguration the validator catches before the writer is dispatched."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        s["mode"] = "full"
        cfg = full_mode_config()
        cfg["template_id"] = "executive-brief"  # mismatched with mode=full
        s["config"] = cfg
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any(
                "config.template_id for mode=full must be 'classical-memo'" in e
                for e in out["errors"]
            ),
            msg=out,
        )

    def test_brief_mode_wrong_template_id_rejected(self):
        """Brief mode must carry template_id='executive-brief'. A mismatch is a
        misconfiguration."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        s["mode"] = "brief"
        cfg = brief_mode_config()
        cfg["template_id"] = "classical-memo"  # mismatched with mode=brief
        s["config"] = cfg
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any(
                "config.template_id for mode=brief must be 'executive-brief'" in e
                for e in out["errors"]
            ),
            msg=out,
        )

    def test_selected_template_mismatched_with_config_rejected(self):
        """If classifier writes selected_template_id different from config.template_id
        (e.g. Full mode but classifier set 'executive-brief'), validator must catch it."""
        s = phase1_initial_state()
        s["current_phase"] = "planning"
        s["mode"] = "full"
        s["config"] = full_mode_config()  # template_id = classical-memo
        s["classification"] = {
            "type": "regulatory_analysis",
            "jurisdictions": ["EU"],
            "doctrine_required": True,
            "estimated_complexity": "high",
            "selected_template_id": "executive-brief",  # mismatch with config.template_id
        }
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any(
                "classification.selected_template_id='executive-brief' does not match" in e
                for e in out["errors"]
            ),
            msg=out,
        )

    def test_dispatched_researchers_not_subset_of_candidate_rejected(self):
        """dispatched_researchers must be a subset of config.researcher_set.
        A Brief task that somehow recorded case-law as dispatched is malformed."""
        s = phase1_initial_state()
        s["current_phase"] = "research_sufficiency"
        s["mode"] = "brief"
        s["config"] = brief_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law"]
        code, out = run_validator(s)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("dispatched_researchers" in e and "not in config.researcher_set" in e
                for e in out["errors"]),
            msg=out,
        )

    def test_sufficiency_regate_over_budget_rejected(self):
        """attempts.sufficiency_regate is bounded to 1 — Phase 6.5 may re-gate
        sufficiency at most once after currency invalidation."""
        s = phase1_initial_state()
        s["current_phase"] = "source_pack"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        s["attempts"]["sufficiency_regate"] = 2
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("attempts.sufficiency_regate is bounded to 1" in e for e in out["errors"]),
            msg=out,
        )

    # Wave 5 — final_status canonical enum (D5), retry budgets (D2/W1),
    # research-summary-only heartbeat carve-out (C1).

    def test_invalid_final_status_rejected(self):
        """final_status must match the canonical enum from state-schema.md.
        A typo like 'approved' (missing _on_v<N>) must fail."""
        s = phase1_initial_state()
        s["current_phase"] = "export"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["current_draft_path"] = "drafts/v3.md"
        s["current_iteration"] = 3
        s["final_status"] = "approved"  # missing _on_v<N> suffix
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("not in the canonical enum" in e for e in out["errors"]),
            msg=out,
        )

    def test_canonical_final_status_strings_accepted(self):
        """All six canonical final_status forms from state-schema.md must
        pass validation when the rest of the state is consistent."""
        for status in (
            "approved_on_v1",
            "forced_exit_on_v3_with_remaining_issues",
            "manual_review_required_on_v2",
            "accepted_early_on_v1",
            "fallback_research_summary_delivered",
            "fallback_summary_delivered",
        ):
            with self.subTest(final_status=status):
                s = phase1_initial_state()
                s["current_phase"] = "export"
                s["mode"] = "full"
                s["config"] = full_mode_config()
                s["current_draft_path"] = "drafts/v1.md"
                s["current_iteration"] = 1
                s["final_status"] = status
                s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
                code, out = run_validator(s, create_sufficiency=True)
                self.assertEqual(code, 0, msg=out)

    def test_research_followup_over_budget_rejected(self):
        """attempts.research_followup is bounded to 1 — memo Phase 6 allows
        at most one targeted follow-up cycle."""
        s = phase1_initial_state()
        s["current_phase"] = "source_pack"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        s["attempts"]["research_followup"] = 2
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("attempts.research_followup is bounded to 1" in e for e in out["errors"]),
            msg=out,
        )

    def test_client_readiness_polish_exceeds_max_rejected(self):
        """attempts.client_readiness_polish must never exceed
        config.max_client_polish (Brief=0, Full=1)."""
        s = phase1_initial_state()
        s["current_phase"] = "client_readiness"
        s["mode"] = "brief"
        s["config"] = brief_mode_config()  # max_client_polish=0
        s["current_draft_path"] = "drafts/v1.md"
        s["current_iteration"] = 1
        s["dispatched_researchers"] = ["statutory"]
        s["attempts"]["client_readiness_polish"] = 1  # > 0 cap
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("client_readiness_polish=1 exceeds config.max_client_polish=0"
                in e for e in out["errors"]),
            msg=out,
        )

    def test_reviewer_json_retry_per_kind_over_budget_rejected(self):
        """attempts.reviewer_json_retry[<kind>] must not exceed 2
        (one retry + one failure-stub pass per continue/SKILL.md)."""
        s = phase1_initial_state()
        s["current_phase"] = "revision_loop"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["current_draft_path"] = "drafts/v1.md"
        s["current_iteration"] = 1
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        s["attempts"]["reviewer_json_retry"] = {"v1-logic": 3}
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("reviewer_json_retry" in e and "exceeds 2" in e for e in out["errors"]),
            msg=out,
        )

    def test_research_summary_only_heartbeat_carveout_passes(self):
        """Full mode + heartbeat='research_summary_only' +
        selected_template_id='research-summary-only' is the documented
        legacy v0.0.42/0.0.43 Phase 8 branch A path. Validator must NOT flag
        the template mismatch with config.template_id — research-summary-only
        is a heartbeat-driven escape valve, not a classifier pick."""
        s = phase1_initial_state()
        s["current_phase"] = "drafting"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["heartbeat_choice"] = "research_summary_only"
        s["classification"] = {
            "type": "regulatory_analysis",
            "jurisdictions": ["EU"],
            "doctrine_required": False,
            "estimated_complexity": "medium",
            "selected_template_id": "research-summary-only",
        }
        s["current_draft_path"] = "drafts/v1.md"
        s["current_iteration"] = 1
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 0, msg=out)
        self.assertTrue(out["ok"])

    def test_research_summary_only_without_heartbeat_rejected(self):
        """If selected_template_id='research-summary-only' but
        heartbeat_choice is anything other than 'research_summary_only',
        that's a contract violation — the template is only valid via the
        heartbeat-driven path."""
        s = phase1_initial_state()
        s["current_phase"] = "drafting"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["heartbeat_choice"] = "continue_full"  # NOT research_summary_only
        s["classification"] = {
            "type": "regulatory_analysis",
            "jurisdictions": ["EU"],
            "doctrine_required": False,
            "estimated_complexity": "medium",
            "selected_template_id": "research-summary-only",
        }
        s["current_draft_path"] = "drafts/v1.md"
        s["current_iteration"] = 1
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("'research-summary-only' is only valid on legacy v0.0.42/0.0.43 tasks where" in e
                for e in out["errors"]),
            msg=out,
        )

    def test_done_with_nonexistent_docx_file_rejected(self):
        """`done` requires final_docx_path to point at an existing file on disk
        (per always-deliver.md: the user never reaches `done` without an artifact)."""
        s = phase1_initial_state()
        s["current_phase"] = "done"
        s["mode"] = "full"
        s["config"] = full_mode_config()
        s["current_draft_path"] = "drafts/v3.md"
        s["current_iteration"] = 3
        s["final_status"] = "approved_on_v3"
        # Use a platform-absolute path that we know will not exist. The
        # tempdir fixture lives at create_sufficiency=True, so we point at a
        # subpath of it that we deliberately do NOT create.
        # On Windows absolute = drive-rooted (e.g. C:\...); on POSIX = /...
        # We build the path via Path.cwd() + a unique suffix to guarantee absoluteness.
        nonexistent = str(Path.cwd() / "this_should_definitely_not_exist_memo_xyz.docx")
        s["final_docx_path"] = nonexistent
        s["dispatched_researchers"] = ["statutory", "case-law", "doctrinal"]
        code, out = run_validator(s, create_sufficiency=True)
        self.assertEqual(code, 1)
        self.assertTrue(
            any("final_docx_path file does not exist on disk" in e for e in out["errors"]),
            msg=out,
        )


if __name__ == "__main__":
    unittest.main()
