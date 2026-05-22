"""Smoke tests for scripts/validate_review_json.py.

Tests the mode-aware behaviour:
- Brief mode (3 reviewers) validates with only 3 JSON files present.
- Full mode (5 reviewers) requires all 5.
- --reviewers CLI flag overrides state.json.config.reviewer_list.
- Missing reviewer in the configured set fails validation.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate_review_json.py"

ALL_REVIEWERS = ("logic", "clarity", "style", "citations", "counterarguments")


def valid_review_payload(reviewer: str, iteration: int) -> dict:
    return {
        "reviewer": reviewer,
        "version_reviewed": iteration,
        "overall_score": 90,
        "blocking_issues": [],
        "nice_to_have": [],
        "verdict": "approved",
    }


def make_workdir(reviewers_present: list[str], iteration: int, reviewer_list_in_state: list[str] | None) -> Path:
    td = Path(tempfile.mkdtemp())
    (td / "reviews").mkdir()
    if reviewer_list_in_state is not None:
        (td / "state.json").write_text(json.dumps({"config": {"reviewer_list": reviewer_list_in_state}}))
    for r in reviewers_present:
        (td / "reviews" / f"v{iteration}-{r}.json").write_text(json.dumps(valid_review_payload(r, iteration)))
    return td


def run_validator(workdir: Path, iteration: int, reviewers: str | None = None) -> tuple[int, dict]:
    args = [sys.executable, str(VALIDATOR), "--workdir", str(workdir), "--iteration", str(iteration)]
    if reviewers is not None:
        args += ["--reviewers", reviewers]
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout) if result.stdout else {}


class ValidateReviewJsonTests(unittest.TestCase):

    def test_quick_mode_3_reviewers_passes(self):
        quick = ["logic", "citations", "counterarguments"]
        workdir = make_workdir(quick, iteration=1, reviewer_list_in_state=quick)
        code, out = run_validator(workdir, iteration=1)
        self.assertEqual(code, 0, msg=out)
        self.assertEqual(out["reviewer_set"], quick)
        self.assertEqual(out["reviewer_set_source"], "state.json.config.reviewer_list")
        self.assertEqual(len(out["valid_reviewers"]), 3)
        self.assertFalse(out["invalid_reviewers"])

    def test_standard_mode_requires_all_5(self):
        standard = list(ALL_REVIEWERS)
        # Only 3 files present, but state declares all 5 — should fail
        workdir = make_workdir(["logic", "citations", "counterarguments"], iteration=1, reviewer_list_in_state=standard)
        code, out = run_validator(workdir, iteration=1)
        self.assertEqual(code, 1)
        self.assertEqual(set(out["reviewer_set"]), set(standard))
        missing = {r["reviewer"] for r in out["invalid_reviewers"]}
        self.assertEqual(missing, {"clarity", "style"})

    def test_standard_mode_all_5_files_pass(self):
        standard = list(ALL_REVIEWERS)
        workdir = make_workdir(standard, iteration=1, reviewer_list_in_state=standard)
        code, out = run_validator(workdir, iteration=1)
        self.assertEqual(code, 0, msg=out)
        self.assertEqual(len(out["valid_reviewers"]), 5)

    def test_cli_reviewers_flag_overrides_state(self):
        # State says Standard (5), CLI flag says Quick (3) → only 3 are checked
        workdir = make_workdir(["logic", "citations", "counterarguments"], iteration=1, reviewer_list_in_state=list(ALL_REVIEWERS))
        code, out = run_validator(workdir, iteration=1, reviewers="logic,citations,counterarguments")
        self.assertEqual(code, 0, msg=out)
        self.assertEqual(out["reviewer_set"], ["logic", "citations", "counterarguments"])
        self.assertEqual(out["reviewer_set_source"], "cli --reviewers")

    def test_no_state_falls_back_to_all_5(self):
        # No state.json, no --reviewers — default to all 5
        workdir = make_workdir(list(ALL_REVIEWERS), iteration=1, reviewer_list_in_state=None)
        code, out = run_validator(workdir, iteration=1)
        self.assertEqual(code, 0, msg=out)
        self.assertEqual(out["reviewer_set_source"], "default (all 5)")

    def test_unknown_reviewer_kind_rejected(self):
        workdir = make_workdir([], iteration=1, reviewer_list_in_state=None)
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--workdir", str(workdir), "--iteration", "1", "--reviewers", "logic,foo"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown reviewer kind", result.stderr)


if __name__ == "__main__":
    unittest.main()
